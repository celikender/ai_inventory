# app/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.routes.projects import router as projects_router
from capture.camera_service import cam_service  # ADD

app = FastAPI()

@app.on_event("startup")  # ADD
def _startup():
    cam_service.start()

@app.on_event("shutdown")  # ADD
def _shutdown():
    cam_service.stop()

# API
app.include_router(projects_router, prefix="/projects")

# UI
app.mount("/ui-static", StaticFiles(directory="app/ui", html=False), name="ui-static")
app.mount("/photos", StaticFiles(directory="storage/photos"), name="photos")

@app.get("/ui")
def ui():
    return FileResponse(Path("app/ui/index.html"))

@app.get("/ui/dash")
def ui_dash():
    return FileResponse(Path("app/ui/dash.html"))
