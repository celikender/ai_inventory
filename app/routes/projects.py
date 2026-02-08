from fastapi import APIRouter, Query, HTTPException
import json
import time

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
)
from storage.models import ProjectCreate, ShelfCreate, BinCreate, BinPatch
from capture.usb_cam import take_photo
from ai.gemini_client import gemini_analyze_image
from ai.prompts import SETUP_PROMPT, SCAN_PROMPT_TEMPLATE
from ai.config import load_ai_config

router = APIRouter()

init_db()

SCAN_COOLDOWN_SECONDS = 8  # change to 5-10 as you want
_last_scan_monotonic: dict[int, float] = {}


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
                return s[start:i + 1]

    return ""



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
    frame = take_photo(device_index=0, width=1280, height=720)
    path = save_shelf_photo(project_id, shelf_id, frame)
    return {"path": path}



@router.post("/{project_id}/shelves/{shelf_id}/setup_analyze")
def setup_analyze(
    project_id: int,
    shelf_id: int,
    expected_bins: int = Query(1, ge=1, le=200),
):
    frame = take_photo(device_index=0, width=1280, height=720)
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

def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


@router.post("/{project_id}/shelves/{shelf_id}/scan")
def scan_shelf(project_id: int, shelf_id: int):
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

# set immediately to block double-click / concurrent calls
    _last_scan_monotonic[shelf_id] = now

    
    frame = take_photo(device_index=0, width=1280, height=720)
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
    warnings = []

    prompt = SCAN_PROMPT_TEMPLATE.format(
        known_bins_json=json.dumps(known, ensure_ascii=False)
    )

    cfg = load_ai_config()
    model = cfg["gemini"]["model"]

    try:
        text = gemini_analyze_image(prompt, photo_path, model=model)

        if not text or not text.strip():
            return {
                "photo_path": photo_path,
                "error": "Empty Gemini response",
                "raw": text,
                "model": model,
            }

        json_str = extract_json_array(text)
        if not json_str:
            return {
                "photo_path": photo_path,
                "error": "Could not extract JSON array",
                "raw": text,
                "model": model,
            }

        data = json.loads(json_str)
        if not isinstance(data, list):
            return {
                "photo_path": photo_path,
                "error": "Gemini did not return a JSON list",
                "raw": text,
                "model": model,
            }

        updated = []
        known_codes = {b["bin_code"] for b in known}

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

            if exp_text and obs:
                exp_norm = _norm(exp_text)
                obs_norm = _norm(obs)

                if (obs_norm not in exp_norm) and (exp_norm.split()[0] not in obs_norm):
                    warnings.append(
                        {
                            "bin_code": code,
                            "warning": "product_mismatch",
                            "expected": exp_text,
                            "observed": obs,
                        }
                    )

            update_bin_qty_by_code(shelf_id, code, qty)
            updated.append({"bin_code": code, "qty": qty, "observed_product": obs})

        return {
            "photo_path": photo_path,
            "updated": updated,
            "warnings": warnings,
            "model": model,
        }

    except Exception as e:
        return {"photo_path": photo_path, "error": f"scan crashed: {e}"}

@router.patch("/bins/{bin_id}")
def patch_bin(bin_id: int, payload: BinPatch):
    updated = update_bin_by_id(bin_id, payload.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Bin not found or no fields updated")
    return updated
