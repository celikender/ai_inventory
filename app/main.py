from fastapi import FastAPI
from app.routes.projects import router as projects_router

app = FastAPI(title="AI Inventory")

@app.get("/health")
def health():
    return {"ok": True}

app.include_router(projects_router, prefix="/projects", tags=["projects"])
