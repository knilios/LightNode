from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import shutil
import sqlite3
import uuid

from .config import LightNodeSettings
from .schema import SCHEMA_SQL


logger = logging.getLogger(__name__)


class StorageError(RuntimeError):
    pass


@dataclass(slots=True)
class StorageState:
    mounted: bool
    writable: bool
    marker_present: bool
    marker_valid: bool
    database_open: bool
    degraded: bool
    ready: bool
    free_bytes: int
    total_bytes: int
    storage_root: str
    database_path: str
    marker_path: str
    message: str = ""


class StorageService:
    def __init__(self, settings: LightNodeSettings) -> None:
        self.settings = settings
        self._connection: sqlite3.Connection | None = None
        self._state: StorageState | None = None

    def prepare(self) -> StorageState:
        self._validate_storage_root()
        self._ensure_directories()

        marker = self._load_marker()
        if marker is None:
            if not self.settings.allow_storage_bootstrap:
                raise StorageError(f"Missing marker file: {self.settings.marker_path}")
            marker = self._create_marker()

        self._validate_marker(marker)
        self._probe_writability()
        connection = self._open_database()
        self._initialize_schema(connection)

        free_bytes, total_bytes = self._space_info()
        degraded = free_bytes < self.settings.minimum_free_bytes
        self._state = StorageState(
            mounted=True,
            writable=True,
            marker_present=True,
            marker_valid=True,
            database_open=True,
            degraded=degraded,
            ready=not degraded,
            free_bytes=free_bytes,
            total_bytes=total_bytes,
            storage_root=str(self.settings.storage_root),
            database_path=str(self.settings.database_path),
            marker_path=str(self.settings.marker_path),
            message="storage ready" if not degraded else "storage ready but low on free space",
        )
        logger.info("storage prepared", extra={"state": asdict(self._state)})
        return self._state

    def state(self) -> StorageState:
        if self._state is None:
            free_bytes, total_bytes = self._space_info()
            return StorageState(
                mounted=self.settings.storage_root.exists(),
                writable=self.settings.storage_root.exists() and os.access(self.settings.storage_root, os.W_OK),
                marker_present=self.settings.marker_path.exists(),
                marker_valid=False,
                database_open=self._connection is not None,
                degraded=free_bytes < self.settings.minimum_free_bytes,
                ready=False,
                free_bytes=free_bytes,
                total_bytes=total_bytes,
                storage_root=str(self.settings.storage_root),
                database_path=str(self.settings.database_path),
                marker_path=str(self.settings.marker_path),
                message="storage not prepared",
            )
        return self._state

    def inspect(self) -> StorageState:
        self._validate_storage_root()
        self._ensure_directories()

        marker = self._load_marker()
        if marker is None:
            raise StorageError(f"Missing marker file: {self.settings.marker_path}")

        self._validate_marker(marker)
        self._probe_writability()
        connection = self._open_database()
        self._initialize_schema(connection)

        free_bytes, total_bytes = self._space_info()
        degraded = free_bytes < self.settings.minimum_free_bytes
        self._state = StorageState(
            mounted=True,
            writable=True,
            marker_present=True,
            marker_valid=True,
            database_open=True,
            degraded=degraded,
            ready=not degraded,
            free_bytes=free_bytes,
            total_bytes=total_bytes,
            storage_root=str(self.settings.storage_root),
            database_path=str(self.settings.database_path),
            marker_path=str(self.settings.marker_path),
            message="storage ready" if not degraded else "storage ready but low on free space",
        )
        logger.info("storage inspected", extra={"state": asdict(self._state)})
        return self._state

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def _validate_storage_root(self) -> None:
        root = self.settings.storage_root
        if self.settings.require_external_storage and not root.exists():
            raise StorageError(f"Storage root does not exist: {root}")
        if not root.exists():
            root.mkdir(parents=True, exist_ok=True)
        if not root.is_dir():
            raise StorageError(f"Storage root is not a directory: {root}")
        if not os.access(root, os.W_OK):
            raise StorageError(f"Storage root is not writable: {root}")

    def _ensure_directories(self) -> None:
        self.settings.files_path.mkdir(parents=True, exist_ok=True)
        self.settings.backups_path.mkdir(parents=True, exist_ok=True)

    def _load_marker(self) -> dict[str, object] | None:
        if not self.settings.marker_path.exists():
            return None
        with self.settings.marker_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _create_marker(self) -> dict[str, object]:
        marker = {
            "format_version": self.settings.supported_marker_format_version,
            "instance_id": self.settings.resolved_instance_id(),
            "created_at": self._utc_now(),
            "last_seen_at": self._utc_now(),
            "lightnode_version": self.settings.lightnode_version,
            "db_path": self.settings.database_filename,
            "storage_mode": self.settings.storage_mode,
        }
        with self.settings.marker_path.open("w", encoding="utf-8") as handle:
            json.dump(marker, handle, indent=2, sort_keys=True)
            handle.write("\n")
        return marker

    def initialize(self) -> StorageState:
        self._validate_storage_root()
        self._ensure_directories()

        marker = self._load_marker()
        if marker is None:
            marker = self._create_marker()

        self._validate_marker(marker)
        self._probe_writability()
        connection = self._open_database()
        self._initialize_schema(connection)

        free_bytes, total_bytes = self._space_info()
        degraded = free_bytes < self.settings.minimum_free_bytes
        self._state = StorageState(
            mounted=True,
            writable=True,
            marker_present=True,
            marker_valid=True,
            database_open=True,
            degraded=degraded,
            ready=not degraded,
            free_bytes=free_bytes,
            total_bytes=total_bytes,
            storage_root=str(self.settings.storage_root),
            database_path=str(self.settings.database_path),
            marker_path=str(self.settings.marker_path),
            message="storage ready" if not degraded else "storage ready but low on free space",
        )
        logger.info("storage initialized", extra={"state": asdict(self._state)})
        return self._state

    def _validate_marker(self, marker: dict[str, object]) -> None:
        if int(marker.get("format_version", 0)) != self.settings.supported_marker_format_version:
            raise StorageError("Unsupported .lightnode format version")
        if marker.get("storage_mode") != self.settings.storage_mode:
            raise StorageError("Storage mode mismatch in .lightnode")
        if marker.get("db_path") != self.settings.database_filename:
            raise StorageError("Database path mismatch in .lightnode")
        expected_instance_id = self.settings.instance_id
        if expected_instance_id and marker.get("instance_id") != expected_instance_id:
            raise StorageError("Instance id mismatch in .lightnode")

    def _probe_writability(self) -> None:
        probe_path = self.settings.storage_root / f".lightnode-probe-{uuid.uuid4().hex}"
        try:
            with probe_path.open("w", encoding="utf-8") as handle:
                handle.write(self._utc_now())
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            if probe_path.exists():
                probe_path.unlink()

    def _open_database(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.settings.database_path, timeout=30, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        self._connection = connection
        return connection

    def _initialize_schema(self, connection: sqlite3.Connection) -> None:
        with connection:
            connection.executescript(SCHEMA_SQL)

    def _space_info(self) -> tuple[int, int]:
        if not self.settings.storage_root.exists():
            return 0, 0
        usage = shutil.disk_usage(self.settings.storage_root)
        return usage.free, usage.total

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()


__all__ = ["StorageError", "StorageService", "StorageState"]
