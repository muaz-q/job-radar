"""FastAPI entry point.  Run from backend/:  uvicorn app.main:create_app --factory --reload

An app factory (rather than a module-level `app`) keeps imports side-effect free, so
tests can build an app against a temporary database.
"""

import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Config, get_config
from app.database import Database
from app.cli import configure_logging
from app.notifications import NotificationService, build_channels
from app.routes import jobs, notifications, settings, sources
from app.scanner import Scanner
from app.scheduler import run_scheduler
from app.sources import build_sources


def create_app(config: Config | None = None, scanner: Scanner | None = None) -> FastAPI:
    config = config or get_config()
    configure_logging(config.log_level)

    db = scanner.db if scanner else Database(config.database_url)
    db.create_all()
    scanner = scanner or Scanner(db, build_sources(config), NotificationService(build_channels(config)))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = None
        if config.scheduler_enabled:
            task = asyncio.create_task(run_scheduler(scanner, config.scan_interval_minutes))
        yield
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title="Job Radar", version="0.1.0", lifespan=lifespan)
    app.state.config = config
    app.state.db = db
    app.state.scanner = scanner

    app.add_middleware(
        CORSMiddleware, allow_origins=[config.frontend_origin], allow_methods=["GET", "PUT", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.get("/health", tags=["health"])
    def health():
        return {"status": "ok", "sources": [s.name for s in scanner.sources], "scan_running": scanner.is_running}

    for module in (jobs, sources, settings, notifications):
        app.include_router(module.router)
    return app
