"""FastAPI entrypoint.

Local dev:  uvicorn app.main:app --reload   (from backend/)
Cloud Run:  see deployment/Dockerfile
"""
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.core.debug_log import debug_log


def create_app() -> FastAPI:
    app = FastAPI(title="Rail50Hz.ai Compliance Gateway", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def record_traffic(request: Request, call_next):
        # Feeds the Debug Console's "Traffic" panel (docs/CRAFTSMAN_AGENT.md)
        # - every request, not just Craftsman's, so a stuck live session is
        # visible alongside everything else hitting the backend at the time.
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000
        debug_log.record_request(request.method, request.url.path, response.status_code, duration_ms)
        return response

    app.include_router(router)
    return app


app = create_app()
