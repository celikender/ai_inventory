# app/main.py
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routes.projects import router as projects_router
from capture.camera_service import cam_service

PROJECT_ROOT = Path(__file__).resolve().parents[1]
UI_DIR = PROJECT_ROOT / "app" / "ui"
PHOTOS_DIR = PROJECT_ROOT / "storage" / "photos"
PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

CAMERA_ENABLED = os.getenv("CAMERA_ENABLED", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

app = FastAPI(
    title="Edge AI Inventory Monitor",
    version="0.1.0",
    description="Local inventory prototype using camera capture, motion detection, and structured Gemini vision output.",
)

@app.on_event("startup")
def _startup():
    if CAMERA_ENABLED:
        cam_service.start()

@app.on_event("shutdown")
def _shutdown():
    cam_service.stop()

# API
app.include_router(projects_router, prefix="/projects")

# UI
app.mount("/ui-static", StaticFiles(directory=UI_DIR, html=False), name="ui-static")
app.mount("/photos", StaticFiles(directory=PHOTOS_DIR), name="photos")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "camera_enabled": CAMERA_ENABLED,
        "camera_running": cam_service.running,
    }

@app.get("/ui")
def ui():
    return FileResponse(UI_DIR / "index.html")

@app.get("/ui/dash")
def ui_dash():
    return FileResponse(UI_DIR / "dash.html")
