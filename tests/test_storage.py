from __future__ import annotations

import json
from pathlib import Path

import pytest

from lightnode.app import create_app
from lightnode.config import LightNodeSettings
from lightnode.storage import StorageError, StorageService


def write_marker(root: Path, *, format_version: int = 1, storage_mode: str = "external-drive") -> None:
    marker = {
        "format_version": format_version,
        "instance_id": "instance-1",
        "created_at": "2026-04-13T00:00:00Z",
        "last_seen_at": "2026-04-13T00:00:00Z",
        "lightnode_version": "0.1.0",
        "db_path": "lightnode.db",
        "storage_mode": storage_mode,
    }
    (root / ".lightnode").write_text(json.dumps(marker), encoding="utf-8")


def test_storage_prepare_creates_database_and_health_state(tmp_path: Path) -> None:
    write_marker(tmp_path)
    settings = LightNodeSettings(
        storage_root=tmp_path,
        allow_storage_bootstrap=False,
    )

    storage = StorageService(settings)
    state = storage.prepare()

    assert state.mounted is True
    assert state.writable is True
    assert state.marker_present is True
    assert state.marker_valid is True
    assert state.database_open is True
    assert (tmp_path / "lightnode.db").exists()
    assert (tmp_path / "files").exists()
    assert (tmp_path / "backups").exists()
    storage.close()


def test_storage_prepare_rejects_missing_marker_without_bootstrap(tmp_path: Path) -> None:
    settings = LightNodeSettings(storage_root=tmp_path, allow_storage_bootstrap=False)
    storage = StorageService(settings)

    with pytest.raises(StorageError, match="Missing marker file"):
        storage.prepare()


def test_storage_prepare_rejects_invalid_marker_version(tmp_path: Path) -> None:
    write_marker(tmp_path, format_version=2)
    settings = LightNodeSettings(storage_root=tmp_path)
    storage = StorageService(settings)

    with pytest.raises(StorageError, match=r"Unsupported \.lightnode format version"):
        storage.prepare()


def test_health_endpoint_reports_storage_state(tmp_path: Path) -> None:
    write_marker(tmp_path)
    app = create_app(LightNodeSettings(storage_root=tmp_path))

    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["storage"]["marker_valid"] is True
