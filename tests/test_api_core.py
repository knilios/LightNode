from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from lightnode.app import create_app
from lightnode.auth import hash_password
from lightnode.config import LightNodeSettings
from lightnode.storage import StorageService


def setup_storage(tmp_path: Path) -> LightNodeSettings:
    settings = LightNodeSettings(
        storage_root=tmp_path,
        allow_storage_bootstrap=True,
        instance_id="instance-1",
    )
    storage = StorageService(settings)
    storage.initialize()
    db = storage.connection()
    db.execute(
        """
        INSERT INTO users (id, username, password_hash, role, is_active, created_at, updated_at, deleted_at)
        VALUES ('u1', 'alice', ?, 'admin', 1, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', NULL)
        """,
        (hash_password("secret123"),),
    )
    db.commit()
    storage.close()
    return LightNodeSettings(
        storage_root=tmp_path,
        allow_storage_bootstrap=False,
        instance_id="instance-1",
    )


def test_auth_and_file_folder_crud_flow(tmp_path: Path) -> None:
    settings = setup_storage(tmp_path)
    app = create_app(settings)

    with TestClient(app) as client:
        login = client.post("/auth/login", json={"username": "alice", "password": "secret123"})
        assert login.status_code == 200
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Request-Id": "req-1"}

        me = client.get("/auth/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["username"] == "alice"

        create_folder = client.post("/folders", headers=headers, json={"name": "docs"})
        assert create_folder.status_code == 200
        folder_id = create_folder.json()["id"]

        update_folder = client.patch(f"/folders/{folder_id}", headers=headers, json={"name": "docs-renamed"})
        assert update_folder.status_code == 200
        assert update_folder.json()["name"] == "docs-renamed"

        upload = client.post(
            f"/upload?folder_id={folder_id}",
            headers=headers,
            files={"file": ("hello.txt", b"hello world", "text/plain")},
        )
        assert upload.status_code == 200
        file_id = upload.json()["id"]

        files = client.get("/files", headers=headers)
        assert files.status_code == 200
        assert len(files.json()["files"]) == 1

        search = client.get("/search", headers=headers, params={"q": "hello"})
        assert search.status_code == 200
        assert len(search.json()["results"]) == 1

        file_update = client.patch(f"/files/{file_id}", headers=headers, json={"filename": "renamed.txt"})
        assert file_update.status_code == 200
        assert file_update.json()["filename"] == "renamed.txt"

        download = client.get(f"/files/{file_id}/download", headers=headers)
        assert download.status_code == 200
        assert download.content == b"hello world"

        delete_file = client.delete(f"/files/{file_id}", headers=headers)
        assert delete_file.status_code == 200

        delete_folder = client.delete(f"/folders/{folder_id}", headers=headers)
        assert delete_folder.status_code == 200

        logout = client.post("/auth/logout", headers=headers)
        assert logout.status_code == 200


def test_cors_preflight_uses_configured_origins(tmp_path: Path) -> None:
    settings = setup_storage(tmp_path)
    settings.cors_allow_origins = ["http://localhost:3000"]
    settings.cors_allow_methods = ["GET", "POST"]
    settings.cors_allow_headers = ["Authorization", "Content-Type"]
    settings.cors_allow_credentials = True

    app = create_app(settings)

    with TestClient(app) as client:
        response = client.options(
            "/auth/me",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
        assert response.headers["access-control-allow-credentials"] == "true"
