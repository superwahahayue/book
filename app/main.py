"""FastAPI application factory and lifecycle wiring."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.config import get_settings
from app.db import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_FRONTEND_DIST = _PROJECT_ROOT / "frontend" / "dist"
_SPA_SKIP_PREFIXES = ("api", "docs", "redoc", "openapi.json")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="剧情导演 · 小说生成器", lifespan=lifespan)

    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    if _FRONTEND_DIST.is_dir():
        assets_dir = _FRONTEND_DIST / "assets"
        if assets_dir.is_dir():
            app.mount(
                "/assets",
                StaticFiles(directory=str(assets_dir)),
                name="spa-assets",
            )

        index_file = _FRONTEND_DIST / "index.html"

        @app.get("/")
        def spa_index():
            if not index_file.is_file():
                raise HTTPException(
                    status_code=404, detail="前端未构建,请先 npm run build"
                )
            return FileResponse(index_file)

        @app.get("/{full_path:path}")
        def spa_fallback(full_path: str):
            first = full_path.split("/", 1)[0]
            if first in _SPA_SKIP_PREFIXES or full_path in _SPA_SKIP_PREFIXES:
                raise HTTPException(status_code=404, detail="Not Found")
            candidate = _FRONTEND_DIST / full_path
            if candidate.is_file():
                return FileResponse(candidate)
            if index_file.is_file():
                return FileResponse(index_file)
            raise HTTPException(status_code=404, detail="前端未构建")
    else:

        @app.get("/")
        def no_frontend():
            return {
                "message": "API 运行中。请构建前端: cd frontend && npm run build",
                "docs": "/docs",
            }

    return app


app = create_app()
