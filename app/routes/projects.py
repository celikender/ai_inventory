# app/routes/projects.py  (full file)

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional
import json
import time
import threading
from datetime import datetime

from core.motion import ChangeDetector
from capture.usb_cam import take_photo
from capture.camera_service import cam_service

from storage.db import (
    init_db,
    create_project,
    list_projects,
    create_shelf,
    list_shelves,
    create_bin,
    list_bins,
    save_shelf_photo,
    replace_bins_for_shelf,
    update_bin_qty_by_code,
    update_bin_by_id,
    project_exists,
    get_last_scan_map,
    get_shelf_last_scan_time,
    upsert_last_scan_shift,
)

from storage.models import ProjectCreate, ShelfCreate, BinCreate, BinPatch
from ai.gemini_client import gemini_analyze_image
from ai.prompts import SETUP_PROMPT, SCAN_PROMPT_TEMPLATE
from ai.config import load_ai_config

router = APIRouter()
init_db()

SCAN_COOLDOWN_SECONDS = 8
_last_scan_monotonic: dict[int, float] = {}

_autoscan_enabled: dict[int, bool] = {}
_autoscan_thread: dict[int, threading.Thread] = {}
_autoscan_cfg: dict[int, dict] = {}
_autoscan_last_event: dict[int, dict] = {}

_scan_locks: dict[int, threading.Lock] = {}


def _get_scan_lock(shelf_id: int) -> threading.Lock:
    lock = _scan_locks.get(shelf_id)
    if lock is None:
        lock = threading.Lock()
        _scan_locks[shelf_id] = lock
    return lock


def _get_frame():
    # Prefer camera service (fast). Fallback to one-shot if needed.
    frame = None
    try:
        frame = cam_service.get_frame(max_age_s=1.0)
    except Exception:
        frame = None

    if frame is not None:
        return frame

    return take_photo(device_index=0, width=1280, height=720)


def extract_json_array(text: str) -> str:
    if not text:
        return ""
    s = text.strip()

    start = s.find("[")
    if start == -1:
        return ""

    depth = 0
    for i in range(start, len(s)):
        ch = s[i]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]

    return ""


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def _check_cooldown_or_raise(shelf_id: int):
    now = time.monotonic()
    last = _last_scan_monotonic.get(shelf_id, 0.0)
    remaining = SCAN_COOLDOWN_SECONDS - (now - last)
    if remaining > 0:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "cooldown",
                "retry_after_seconds": round(remaining, 1),
                "message": "Scan cooldown active",
            },
        )
    _last_scan_monotonic[shelf_id] = now


def _scan_shelf_core(project_id: int, shelf_id: int, frame):
    # Always save the photo used for the scan
    photo_path = save_shelf_photo(project_id, shelf_id, frame)

    bins = list_bins(shelf_id)
    if not bins:
        return {
            "photo_path": photo_path,
            "error": "No bins initialized for this shelf. Run setup_analyze first.",
        }

    known = [
        {
            "bin_code": b["bin_code"],
            "product_name": b.get("product_name"),
            "description": b.get("description"),
        }
        for b in bins
    ]
    known_map = {b["bin_code"]: b for b in known}
    known_codes = {b["bin_code"] for b in known}

    prompt = SCAN_PROMPT_TEMPLATE.format(
        known_bins_json=json.dumps(known, ensure_ascii=False)
    )

    cfg = load_ai_config()
    model = cfg["gemini"]["model"]

    text = gemini_analyze_image(prompt, photo_path, model=model)

    if not text or not text.strip():
        return {"photo_path": photo_path, "error": "Empty Gemini response", "raw": text, "model": model}

    json_str = extract_json_array(text)
    if not json_str:
        return {"photo_path": photo_path, "error": "Could not extract JSON array", "raw": text, "model": model}

    data = json.loads(json_str)
    if not isinstance(data, list):
        return {"photo_path": photo_path, "error": "Gemini did not return a JSON list", "raw": text, "model": model}

    warnings = []
    updated = []
    scanned_at = datetime.utcnow().isoformat()

    for item in data:
        code = (item.get("bin_code") or "").strip()
        if code not in known_codes:
            continue

        qty = item.get("qty", None)
        if qty is not None and not isinstance(qty, int):
            qty = None

        obs = item.get("observed_product", None)

        exp = known_map.get(code, {})
        exp_text = f'{exp.get("product_name","")} {exp.get("description","")}'.strip()

        mismatch = 0
        if exp_text and obs:
            exp_norm = _norm(exp_text)
            obs_norm = _norm(obs)
            if (obs_norm not in exp_norm) and (exp_norm.split()[0] not in obs_norm):
                mismatch = 1
                warnings.append(
                    {
                        "bin_code": code,
                        "warning": "product_mismatch",
                        "expected": exp_text,
                        "observed": obs,
                    }
                )

        update_bin_qty_by_code(shelf_id, code, qty)

        # Keep dashboard correct
        upsert_last_scan_shift(
            shelf_id=shelf_id,
            bin_code=code,
            qty=qty,
            observed_product=obs,
            mismatch=mismatch,
            scanned_at=scanned_at,
        )

        updated.append(
            {
                "bin_code": code,
                "qty": qty,
                "observed_product": obs,
                "mismatch": mismatch,
            }
        )

    return {
        "photo_path": photo_path,
        "updated": updated,
        "warnings": warnings,
        "model": model,
    }


@router.get("")
def get_projects():
    return list_projects()


@router.post("")
def post_project(payload: ProjectCreate):
    return create_project(payload.name)


@router.get("/{project_id}/shelves")
def get_shelves(project_id: int):
    return list_shelves(project_id)


@router.post("/{project_id}/shelves")
def post_shelf(project_id: int, payload: ShelfCreate):
    if not project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return create_shelf(project_id, payload.name)


@router.get("/{project_id}/shelves/{shelf_id}/bins")
def get_bins(project_id: int, shelf_id: int):
    return list_bins(shelf_id)


@router.post("/{project_id}/shelves/{shelf_id}/bins")
def post_bin(project_id: int, shelf_id: int, payload: BinCreate):
    return create_bin(
        shelf_id,
        payload.bin_code,
        payload.label,
        payload.product_name,
        payload.description,
        payload.qty,
    )


@router.post("/{project_id}/shelves/{shelf_id}/photo")
def post_photo(project_id: int, shelf_id: int):
    frame = _get_frame()
    path = save_shelf_photo(project_id, shelf_id, frame)
    return {"path": path}


@router.post("/{project_id}/shelves/{shelf_id}/setup_analyze")
def setup_analyze(
    project_id: int,
    shelf_id: int,
    expected_bins: int = Query(1, ge=1, le=200),
):
    frame = _get_frame()
    photo_path = save_shelf_photo(project_id, shelf_id, frame)

    try:
        cfg = load_ai_config()
        model = cfg["gemini"]["model"]

        text = gemini_analyze_image(SETUP_PROMPT, photo_path, model=model)

        if not text or not text.strip():
            return {"photo_path": photo_path, "error": "Empty Gemini response", "raw": text, "model": model}

        json_str = extract_json_array(text)
        if not json_str:
            return {"photo_path": photo_path, "error": "Could not extract JSON array", "raw": text, "model": model}

        try:
            data = json.loads(json_str)
        except Exception:
            return {"photo_path": photo_path, "error": "Gemini response was not valid JSON", "raw": text, "model": model}

        if not isinstance(data, list):
            return {"photo_path": photo_path, "error": "Gemini did not return a JSON list", "raw": text, "model": model}

        clean = []
        seen = set()
        for b in data:
            code = (b.get("bin_code") or "").strip()
            if not code:
                continue
            if code in seen:
                continue
            seen.add(code)
            clean.append(b)

        if len(clean) < expected_bins:
            return {
                "photo_path": photo_path,
                "error": f"Detected {len(clean)} bins, expected {expected_bins}. Retake photo.",
                "raw": text,
                "model": model,
                "detected": clean,
            }

        saved = replace_bins_for_shelf(shelf_id, clean)
        return {"photo_path": photo_path, "bins": saved, "model": model}

    except Exception as e:
        return {"photo_path": photo_path, "error": f"setup_analyze crashed: {e}"}


@router.get("/{project_id}/shelves/{shelf_id}/photos_latest")
def photos_latest(project_id: int, shelf_id: int):
    from pathlib import Path
    folder = Path("storage") / "photos" / str(project_id) / str(shelf_id)
    files = sorted(folder.glob("*.jpg"), reverse=True)
    return {"latest": str(files[0]) if files else None, "count": len(files)}


@router.post("/{project_id}/shelves/{shelf_id}/scan")
def scan_shelf(project_id: int, shelf_id: int):
    lock = _get_scan_lock(shelf_id)
    if not lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail={"error": "scan_busy"})

    try:
        _check_cooldown_or_raise(shelf_id)
        frame = _get_frame()
        return _scan_shelf_core(project_id, shelf_id, frame)
    finally:
        lock.release()


@router.patch("/bins/{bin_id}")
def patch_bin(bin_id: int, payload: BinPatch):
    updated = update_bin_by_id(bin_id, payload.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Bin not found or no fields updated")
    return updated


@router.get("/{project_id}/dash")
def dash(project_id: int):
    shelves = list_shelves(project_id)
    out = {"shelves": []}

    today = datetime.utcnow().date().isoformat()

    for sh in shelves:
        shelf_id = sh["id"]
        shelf_name = sh["name"]

        bins = list_bins(shelf_id)
        scan_map = get_last_scan_map(shelf_id)
        last_scan_time = get_shelf_last_scan_time(shelf_id)

        dash_bins = []
        for b in bins:
            code = b["bin_code"]
            rec = scan_map.get(code)

            last_qty = rec["last_qty"] if rec else None
            prev_qty = rec["prev_qty"] if rec else None
            delta = None
            if last_qty is not None and prev_qty is not None:
                delta = last_qty - prev_qty

            dash_bins.append(
                {
                    "bin_code": code,
                    "product_name": b.get("product_name"),
                    "qty": last_qty if last_qty is not None else b.get("qty"),
                    "delta_today": delta,
                    "mismatch": (rec.get("last_mismatch") if rec else 0) or 0,
                    "last_scanned_at": (rec.get("last_scanned_at") if rec else None),
                }
            )

        out["shelves"].append(
            {
                "shelf_id": shelf_id,
                "shelf_name": shelf_name,
                "day_utc": today,
                "last_scan_utc": last_scan_time,
                "bins": dash_bins,
            }
        )

    return out


class AutoScanConfig(BaseModel):
    enabled: bool
    threshold: float = 0.06
    interval_s: float = 0.5
    roi: Optional[list[int]] = None  # [x,y,w,h]

    # Stability tuning
    stable_time_s: float = 3.0
    post_motion_delay_s: float = 0.8

    # Option A additions
    min_scan_gap_s: float = 20.0      # minimum time between autoscan-triggered scans
    max_in_motion_s: float = 15.0     # if motion persists this long, do not scan (blocked)


def _autoscan_worker(project_id: int, shelf_id: int):
    det = ChangeDetector()

    in_motion = False
    stable_count = 0

    motion_started_at = None  # monotonic timestamp
    last_autoscan_scan_at = 0.0  # monotonic timestamp

    while _autoscan_enabled.get(shelf_id, False):
        cfg = _autoscan_cfg.get(shelf_id, {})
        roi = cfg.get("roi")
        threshold = float(cfg.get("threshold", 0.06))
        interval_s = float(cfg.get("interval_s", 0.5))

        stable_time_s = float(cfg.get("stable_time_s", 3.0))
        post_motion_delay_s = float(cfg.get("post_motion_delay_s", 0.8))

        min_scan_gap_s = float(cfg.get("min_scan_gap_s", 20.0))
        max_in_motion_s = float(cfg.get("max_in_motion_s", 15.0))

        # Convert stable_time_s -> frames needed (ceil)
        stable_frames_needed = max(1, int((stable_time_s / interval_s) + 0.999))

        det.roi = roi

        try:
            frame = _get_frame()
            s = det.score(frame)

            now_m = time.monotonic()

            _autoscan_last_event[shelf_id] = {
                "type": "motion_score",
                "score": round(float(s), 4),
                "threshold": round(float(threshold), 4),
                "in_motion": in_motion,
                "stable_count": stable_count,
                "stable_frames_needed": stable_frames_needed,
                "stable_time_s": stable_time_s,
                "min_scan_gap_s": min_scan_gap_s,
                "max_in_motion_s": max_in_motion_s,
                "ts_utc": datetime.utcnow().isoformat(),
            }

            # Motion state tracking
            if s >= threshold:
                if not in_motion:
                    in_motion = True
                    stable_count = 0
                    motion_started_at = now_m
                else:
                    stable_count = 0
            else:
                if in_motion:
                    stable_count += 1

            # If motion persists too long, consider it "blocked" and do not scan.
            if in_motion and motion_started_at is not None:
                dur = now_m - motion_started_at
                if dur >= max_in_motion_s:
                    _autoscan_last_event[shelf_id] = {
                        "type": "blocked_person_or_busy_scene",
                        "score": round(float(s), 4),
                        "threshold": round(float(threshold), 4),
                        "in_motion_s": round(dur, 2),
                        "max_in_motion_s": max_in_motion_s,
                        "result": "skip_scan_wait_for_clear",
                        "ts_utc": datetime.utcnow().isoformat(),
                    }
                    # Stay in motion until we see stable again; do not trigger scan here.

            # If we were in motion, and now stable long enough, trigger scan
            if in_motion and stable_count >= stable_frames_needed:
                in_motion = False
                stable_count = 0
                motion_started_at = None

                # Enforce min scan gap
                if (now_m - last_autoscan_scan_at) < min_scan_gap_s:
                    _autoscan_last_event[shelf_id] = {
                        "type": "stable_but_rate_limited",
                        "min_scan_gap_s": min_scan_gap_s,
                        "since_last_scan_s": round(now_m - last_autoscan_scan_at, 2),
                        "result": "skip",
                        "ts_utc": datetime.utcnow().isoformat(),
                    }
                else:
                    if post_motion_delay_s > 0:
                        time.sleep(post_motion_delay_s)

                    stable_frame = _get_frame()

                    _autoscan_last_event[shelf_id] = {
                        "type": "trigger_scan_after_stable",
                        "threshold": round(float(threshold), 4),
                        "stable_time_s": stable_time_s,
                        "stable_frames_needed": stable_frames_needed,
                        "post_motion_delay_s": post_motion_delay_s,
                        "ts_utc": datetime.utcnow().isoformat(),
                    }

                    lock = _get_scan_lock(shelf_id)
                    if not lock.acquire(blocking=False):
                        _autoscan_last_event[shelf_id]["result"] = "blocked_busy"
                    else:
                        try:
                            _check_cooldown_or_raise(shelf_id)
                            res = _scan_shelf_core(project_id, shelf_id, stable_frame)
                            last_autoscan_scan_at = time.monotonic()
                            _autoscan_last_event[shelf_id]["result"] = "scan_ok"
                            _autoscan_last_event[shelf_id]["scan_meta"] = {
                                "updated": len(res.get("updated") or []),
                                "warnings": len(res.get("warnings") or []),
                            }
                        except HTTPException as e:
                            _autoscan_last_event[shelf_id]["result"] = f"blocked_http_{e.status_code}"
                            _autoscan_last_event[shelf_id]["detail"] = getattr(e, "detail", None)
                        except Exception as e:
                            _autoscan_last_event[shelf_id]["result"] = "error"
                            _autoscan_last_event[shelf_id]["error"] = str(e)
                        finally:
                            lock.release()

        except Exception as e:
            _autoscan_last_event[shelf_id] = {
                "type": "camera_or_motion_error",
                "ts_utc": datetime.utcnow().isoformat(),
                "error": str(e),
            }

        time.sleep(interval_s)


@router.post("/{project_id}/shelves/{shelf_id}/autoscan")
def set_autoscan(project_id: int, shelf_id: int, payload: AutoScanConfig):
    _autoscan_cfg[shelf_id] = {
        "threshold": max(0.0, min(1.0, float(payload.threshold))),
        "interval_s": max(0.2, float(payload.interval_s)),
        "roi": payload.roi,

        "stable_time_s": max(0.0, float(payload.stable_time_s)),
        "post_motion_delay_s": max(0.0, float(payload.post_motion_delay_s)),

        "min_scan_gap_s": max(0.0, float(payload.min_scan_gap_s)),
        "max_in_motion_s": max(0.0, float(payload.max_in_motion_s)),
    }

    if payload.enabled:
        _autoscan_enabled[shelf_id] = True
        t = _autoscan_thread.get(shelf_id)
        if not t or not t.is_alive():
            th = threading.Thread(
                target=_autoscan_worker, args=(project_id, shelf_id), daemon=True
            )
            _autoscan_thread[shelf_id] = th
            th.start()
    else:
        _autoscan_enabled[shelf_id] = False

    return {
        "shelf_id": shelf_id,
        "enabled": bool(_autoscan_enabled.get(shelf_id, False)),
        "cfg": _autoscan_cfg.get(shelf_id),
    }


@router.get("/{project_id}/shelves/{shelf_id}/autoscan_status")
def autoscan_status(project_id: int, shelf_id: int):
    return {
        "enabled": bool(_autoscan_enabled.get(shelf_id, False)),
        "cfg": _autoscan_cfg.get(shelf_id, {}),
        "last_event": _autoscan_last_event.get(shelf_id),
    }
