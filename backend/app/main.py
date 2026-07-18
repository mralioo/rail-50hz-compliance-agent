"""FastAPI entrypoint.

Local dev:  uvicorn app.main:app --reload   (from backend/)
Cloud Run:  see deployment/Dockerfile
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings


def create_app() -> FastAPI:
    app = FastAPI(title="Rail50Hz.ai Compliance Gateway", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
