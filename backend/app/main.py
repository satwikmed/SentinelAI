"""SentinelAI FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.config import get_settings
from app.db import init_db
from app.observability.tracing import init_tracing
from app.rag.retriever import ingest_documents

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sentinelai")

# backend/app/main.py → parents[2] == repo root
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
ALT_FRONTEND = Path("/usr/share/nginx/html")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_tracing()
    await init_db()
    info = ingest_documents()
    logger.info(
        "SentinelAI started demo_mode=%s providers_docs=%s",
        settings.demo_mode,
        info,
    )
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="SentinelAI",
        description="Enterprise GenAI governance and orchestration gateway",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list + ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")

    dist = FRONTEND_DIST.resolve()
    if not dist.exists() and ALT_FRONTEND.exists():
        dist = ALT_FRONTEND
    if dist.exists():
        assets = dist / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{full_path:path}")
        async def spa(full_path: str):
            if full_path.startswith("api/"):
                return {"detail": "Not Found"}
            candidate = dist / full_path
            if full_path and candidate.exists() and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
