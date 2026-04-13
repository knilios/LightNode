from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI

from .config import LightNodeSettings
from .storage import StorageService


def create_app(settings: LightNodeSettings | None = None) -> FastAPI:
    runtime_settings = settings or LightNodeSettings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        storage = StorageService(runtime_settings)
        try:
            app.state.settings = runtime_settings
            app.state.storage = storage
            app.state.storage_state = storage.prepare()
            yield
        finally:
            storage.close()

    app = FastAPI(title="LightNode", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, object]:
        storage: StorageService | None = getattr(app.state, "storage", None)
        if storage is None:
            return {
                "status": "starting",
                "ready": False,
                "storage": None,
            }

        state = storage.state()
        status = "degraded" if state.degraded else ("ready" if state.ready else "starting")
        return {
            "status": status,
            "ready": state.ready,
            "storage": {
                "mounted": state.mounted,
                "writable": state.writable,
                "marker_present": state.marker_present,
                "marker_valid": state.marker_valid,
                "database_open": state.database_open,
                "degraded": state.degraded,
                "free_bytes": state.free_bytes,
                "total_bytes": state.total_bytes,
                "storage_root": state.storage_root,
                "database_path": state.database_path,
                "marker_path": state.marker_path,
                "message": state.message,
            },
        }

    @app.get("/health/live")
    def live() -> dict[str, object]:
        return {"status": "alive"}

    @app.get("/health/ready")
    def ready() -> dict[str, object]:
        storage: StorageService | None = getattr(app.state, "storage", None)
        if storage is None:
            return {"status": "starting", "ready": False}
        state = storage.state()
        return {"status": "ready" if state.ready else "degraded", "ready": state.ready, "storage": asdict(state)}

    return app


__all__ = ["create_app"]
