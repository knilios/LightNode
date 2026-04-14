from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import uuid

from fastapi import Depends, FastAPI, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from .auth import AuthContext, hash_token, utc_now, verify_password
from .config import LightNodeSettings
from .storage import StorageService


security = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    username: str
    password: str


class FolderCreateRequest(BaseModel):
    name: str
    parent_folder_id: str | None = None


class FolderUpdateRequest(BaseModel):
    name: str | None = None
    parent_folder_id: str | None = None


class FileUpdateRequest(BaseModel):
    filename: str | None = None
    folder_id: str | None = None


def _normalize_segment(name: str) -> str:
    cleaned = name.strip()
    if not cleaned or cleaned in {".", ".."} or "/" in cleaned or "\\" in cleaned:
        raise HTTPException(status_code=400, detail="Invalid path segment")
    return cleaned


def _join_folder_path(parent_path: str | None, name: str) -> str:
    seg = _normalize_segment(name)
    if not parent_path or parent_path == "/":
        return f"/{seg}"
    return f"{parent_path.rstrip('/')}/{seg}"


def _audit(
    db: sqlite3.Connection,
    *,
    actor_user_id: str | None,
    action: str,
    status: str,
    request_id: str | None,
    extension_id: str | None,
    target_type: str | None = None,
    target_id: str | None = None,
    metadata: dict[str, object] | None = None,
) -> None:
    db.execute(
        """
        INSERT INTO audit_logs (
            id, actor_user_id, action, target_type, target_id,
            status, request_id, extension_id, metadata_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            actor_user_id,
            action,
            target_type,
            target_id,
            status,
            request_id,
            extension_id,
            json.dumps(metadata or {}, sort_keys=True),
            utc_now(),
        ),
    )


def _request_id(request: Request) -> str:
    return request.headers.get("X-Request-Id") or str(uuid.uuid4())


def _auth_context(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> AuthContext:
    storage: StorageService = request.app.state.storage
    db = storage.connection()
    request_id = _request_id(request)
    ext_id = request.headers.get("X-Extension-Id")
    if credentials is None:
        _audit(
            db,
            actor_user_id=None,
            action=f"{request.method} {request.url.path}",
            status="denied",
            request_id=request_id,
            extension_id=ext_id,
            metadata={"reason": "missing_bearer_token"},
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token_hash = hash_token(credentials.credentials)
    row = db.execute(
        """
        SELECT t.id AS token_id, t.user_id, t.extension_id, t.expires_at, t.revoked_at,
               u.username, u.role, u.is_active
        FROM auth_tokens t
        JOIN users u ON u.id = t.user_id
        WHERE t.token_hash = ?
        """,
        (token_hash,),
    ).fetchone()

    if row is None:
        _audit(
            db,
            actor_user_id=None,
            action=f"{request.method} {request.url.path}",
            status="denied",
            request_id=request_id,
            extension_id=ext_id,
            metadata={"reason": "invalid_token"},
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid token")

    if row["revoked_at"] is not None:
        _audit(
            db,
            actor_user_id=row["user_id"],
            action=f"{request.method} {request.url.path}",
            status="denied",
            request_id=request_id,
            extension_id=ext_id,
            metadata={"reason": "revoked_token", "token_id": row["token_id"]},
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Token revoked")

    if row["is_active"] != 1:
        _audit(
            db,
            actor_user_id=row["user_id"],
            action=f"{request.method} {request.url.path}",
            status="denied",
            request_id=request_id,
            extension_id=ext_id,
            metadata={"reason": "inactive_user", "token_id": row["token_id"]},
        )
        db.commit()
        raise HTTPException(status_code=403, detail="User is inactive")

    return AuthContext(
        token_id=row["token_id"],
        user_id=row["user_id"],
        username=row["username"],
        role=row["role"],
        extension_id=ext_id or row["extension_id"],
    )


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

    if runtime_settings.cors_allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=runtime_settings.cors_allow_origins,
            allow_methods=runtime_settings.cors_allow_methods or ["*"],
            allow_headers=runtime_settings.cors_allow_headers or ["*"],
            expose_headers=runtime_settings.cors_expose_headers or [],
            allow_credentials=runtime_settings.cors_allow_credentials,
            max_age=runtime_settings.cors_max_age,
        )

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

    @app.post("/auth/login")
    def login(payload: LoginRequest, request: Request) -> dict[str, object]:
        storage: StorageService = app.state.storage
        db = storage.connection()
        request_id = _request_id(request)
        row = db.execute(
            "SELECT id, username, password_hash, role, is_active FROM users WHERE username = ?",
            (payload.username,),
        ).fetchone()

        if row is None or not verify_password(payload.password, row["password_hash"]):
            _audit(
                db,
                actor_user_id=None,
                action="auth.login",
                status="denied",
                request_id=request_id,
                extension_id=request.headers.get("X-Extension-Id"),
                metadata={"username": payload.username, "reason": "invalid_credentials"},
            )
            db.commit()
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if row["is_active"] != 1:
            _audit(
                db,
                actor_user_id=row["id"],
                action="auth.login",
                status="denied",
                request_id=request_id,
                extension_id=request.headers.get("X-Extension-Id"),
                metadata={"username": payload.username, "reason": "inactive_user"},
            )
            db.commit()
            raise HTTPException(status_code=403, detail="User is inactive")

        token = uuid.uuid4().hex + uuid.uuid4().hex
        token_id = str(uuid.uuid4())
        db.execute(
            """
            INSERT INTO auth_tokens (id, token_hash, user_id, extension_id, issued_at, expires_at, revoked_at)
            VALUES (?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                token_id,
                hash_token(token),
                row["id"],
                request.headers.get("X-Extension-Id"),
                utc_now(),
                None,
            ),
        )
        _audit(
            db,
            actor_user_id=row["id"],
            action="auth.login",
            status="success",
            request_id=request_id,
            extension_id=request.headers.get("X-Extension-Id"),
            target_type="auth_token",
            target_id=token_id,
        )
        db.commit()
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": row["id"],
                "username": row["username"],
                "role": row["role"],
            },
        }

    @app.post("/auth/logout")
    def logout(request: Request, auth: AuthContext = Depends(_auth_context)) -> dict[str, object]:
        storage: StorageService = app.state.storage
        db = storage.connection()
        request_id = _request_id(request)
        db.execute("UPDATE auth_tokens SET revoked_at = ? WHERE id = ?", (utc_now(), auth.token_id))
        _audit(
            db,
            actor_user_id=auth.user_id,
            action="auth.logout",
            status="success",
            request_id=request_id,
            extension_id=auth.extension_id,
            target_type="auth_token",
            target_id=auth.token_id,
        )
        db.commit()
        return {"status": "ok"}

    @app.get("/auth/me")
    def me(auth: AuthContext = Depends(_auth_context)) -> dict[str, object]:
        return {
            "id": auth.user_id,
            "username": auth.username,
            "role": auth.role,
            "token_id": auth.token_id,
            "extension_id": auth.extension_id,
        }

    @app.post("/folders")
    def create_folder(payload: FolderCreateRequest, request: Request, auth: AuthContext = Depends(_auth_context)) -> dict[str, object]:
        storage: StorageService = app.state.storage
        db = storage.connection()
        request_id = _request_id(request)

        parent_path = "/"
        if payload.parent_folder_id:
            parent = db.execute("SELECT id, full_path FROM folders WHERE id = ? AND deleted_at IS NULL", (payload.parent_folder_id,)).fetchone()
            if parent is None:
                raise HTTPException(status_code=404, detail="Parent folder not found")
            parent_path = parent["full_path"]

        folder_id = str(uuid.uuid4())
        full_path = _join_folder_path(parent_path, payload.name)
        now = utc_now()
        try:
            db.execute(
                "INSERT INTO folders (id, name, parent_folder_id, full_path, created_at, updated_at, deleted_at) VALUES (?, ?, ?, ?, ?, ?, NULL)",
                (folder_id, _normalize_segment(payload.name), payload.parent_folder_id, full_path, now, now),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Folder already exists")

        _audit(
            db,
            actor_user_id=auth.user_id,
            action="folder.create",
            status="success",
            request_id=request_id,
            extension_id=auth.extension_id,
            target_type="folder",
            target_id=folder_id,
            metadata={"full_path": full_path},
        )
        db.commit()
        return {"id": folder_id, "name": payload.name, "parent_folder_id": payload.parent_folder_id, "full_path": full_path}

    @app.get("/root")
    def root_contents(auth: AuthContext = Depends(_auth_context)) -> dict[str, object]:
        storage: StorageService = app.state.storage
        db = storage.connection()
        folders = db.execute(
            "SELECT id, name, full_path, created_at, updated_at FROM folders WHERE parent_folder_id IS NULL AND deleted_at IS NULL ORDER BY name"
        ).fetchall()
        files = db.execute(
            "SELECT id, filename, storage_path, size_bytes, sha256_hash, created_at, updated_at FROM files WHERE folder_id IS NULL AND deleted_at IS NULL ORDER BY filename"
        ).fetchall()
        return {
            "folders": [dict(row) for row in folders],
            "files": [dict(row) for row in files],
        }

    @app.get("/folders/{folder_id}/contents")
    def folder_contents(folder_id: str, auth: AuthContext = Depends(_auth_context)) -> dict[str, object]:
        storage: StorageService = app.state.storage
        db = storage.connection()
        folder = db.execute("SELECT id, name, full_path FROM folders WHERE id = ? AND deleted_at IS NULL", (folder_id,)).fetchone()
        if folder is None:
            raise HTTPException(status_code=404, detail="Folder not found")
        folders = db.execute(
            "SELECT id, name, full_path, created_at, updated_at FROM folders WHERE parent_folder_id = ? AND deleted_at IS NULL ORDER BY name",
            (folder_id,),
        ).fetchall()
        files = db.execute(
            "SELECT id, filename, storage_path, size_bytes, sha256_hash, created_at, updated_at FROM files WHERE folder_id = ? AND deleted_at IS NULL ORDER BY filename",
            (folder_id,),
        ).fetchall()
        return {
            "folder": dict(folder),
            "folders": [dict(row) for row in folders],
            "files": [dict(row) for row in files],
        }

    @app.patch("/folders/{folder_id}")
    def update_folder(folder_id: str, payload: FolderUpdateRequest, request: Request, auth: AuthContext = Depends(_auth_context)) -> dict[str, object]:
        storage: StorageService = app.state.storage
        db = storage.connection()
        request_id = _request_id(request)
        folder = db.execute("SELECT id, name, parent_folder_id, full_path FROM folders WHERE id = ? AND deleted_at IS NULL", (folder_id,)).fetchone()
        if folder is None:
            raise HTTPException(status_code=404, detail="Folder not found")

        new_name = _normalize_segment(payload.name) if payload.name is not None else folder["name"]
        new_parent = payload.parent_folder_id if payload.parent_folder_id is not None else folder["parent_folder_id"]
        parent_path = "/"
        if new_parent is not None:
            if new_parent == folder_id:
                raise HTTPException(status_code=400, detail="Folder cannot be parent of itself")
            parent = db.execute("SELECT id, full_path FROM folders WHERE id = ? AND deleted_at IS NULL", (new_parent,)).fetchone()
            if parent is None:
                raise HTTPException(status_code=404, detail="Parent folder not found")
            parent_path = parent["full_path"]

        new_full_path = _join_folder_path(parent_path, new_name)
        try:
            db.execute(
                "UPDATE folders SET name = ?, parent_folder_id = ?, full_path = ?, updated_at = ? WHERE id = ?",
                (new_name, new_parent, new_full_path, utc_now(), folder_id),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Folder path conflict")

        _audit(
            db,
            actor_user_id=auth.user_id,
            action="folder.update",
            status="success",
            request_id=request_id,
            extension_id=auth.extension_id,
            target_type="folder",
            target_id=folder_id,
            metadata={"full_path": new_full_path},
        )
        db.commit()
        return {
            "id": folder_id,
            "name": new_name,
            "parent_folder_id": new_parent,
            "full_path": new_full_path,
        }

    @app.delete("/folders/{folder_id}")
    def delete_folder(folder_id: str, request: Request, auth: AuthContext = Depends(_auth_context)) -> dict[str, object]:
        storage: StorageService = app.state.storage
        db = storage.connection()
        request_id = _request_id(request)
        folder = db.execute("SELECT id FROM folders WHERE id = ? AND deleted_at IS NULL", (folder_id,)).fetchone()
        if folder is None:
            raise HTTPException(status_code=404, detail="Folder not found")

        has_children = db.execute(
            "SELECT 1 FROM folders WHERE parent_folder_id = ? AND deleted_at IS NULL LIMIT 1",
            (folder_id,),
        ).fetchone()
        has_files = db.execute(
            "SELECT 1 FROM files WHERE folder_id = ? AND deleted_at IS NULL LIMIT 1",
            (folder_id,),
        ).fetchone()
        if has_children or has_files:
            raise HTTPException(status_code=409, detail="Folder is not empty")

        db.execute("UPDATE folders SET deleted_at = ?, updated_at = ? WHERE id = ?", (utc_now(), utc_now(), folder_id))
        _audit(
            db,
            actor_user_id=auth.user_id,
            action="folder.delete",
            status="success",
            request_id=request_id,
            extension_id=auth.extension_id,
            target_type="folder",
            target_id=folder_id,
        )
        db.commit()
        return {"status": "deleted", "id": folder_id}

    @app.post("/upload")
    async def upload_file(
        request: Request,
        file: UploadFile,
        folder_id: str | None = Query(default=None),
        auth: AuthContext = Depends(_auth_context),
    ) -> dict[str, object]:
        storage: StorageService = app.state.storage
        db = storage.connection()
        request_id = _request_id(request)

        if folder_id is not None:
            folder = db.execute("SELECT id FROM folders WHERE id = ? AND deleted_at IS NULL", (folder_id,)).fetchone()
            if folder is None:
                raise HTTPException(status_code=404, detail="Folder not found")

        filename = _normalize_segment(file.filename or "upload.bin")
        file_id = str(uuid.uuid4())
        suffix = Path(filename).suffix
        final_name = f"{file_id}{suffix}"
        final_path = storage.settings.files_path / final_name

        hasher = hashlib.sha256()
        size = 0
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, dir=storage.settings.files_path, prefix=".upload-", suffix=".tmp") as tmp:
                temp_path = Path(tmp.name)
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    hasher.update(chunk)
                    size += len(chunk)
                    tmp.write(chunk)
                tmp.flush()
                os.fsync(tmp.fileno())

            os.replace(temp_path, final_path)

            now = utc_now()
            db.execute(
                """
                INSERT INTO files (id, folder_id, filename, storage_path, size_bytes, sha256_hash, created_at, updated_at, deleted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (file_id, folder_id, filename, final_name, size, hasher.hexdigest(), now, now),
            )
            _audit(
                db,
                actor_user_id=auth.user_id,
                action="file.upload",
                status="success",
                request_id=request_id,
                extension_id=auth.extension_id,
                target_type="file",
                target_id=file_id,
                metadata={"filename": filename, "size_bytes": size},
            )
            db.commit()
            return {
                "id": file_id,
                "folder_id": folder_id,
                "filename": filename,
                "storage_path": final_name,
                "size_bytes": size,
                "sha256_hash": hasher.hexdigest(),
            }
        except Exception as exc:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink(missing_ok=True)
            if final_path.exists():
                final_path.unlink(missing_ok=True)
            _audit(
                db,
                actor_user_id=auth.user_id,
                action="file.upload",
                status="error",
                request_id=request_id,
                extension_id=auth.extension_id,
                metadata={"reason": str(exc)},
            )
            db.commit()
            raise
        finally:
            await file.close()

    @app.get("/files")
    def list_files(auth: AuthContext = Depends(_auth_context)) -> dict[str, object]:
        storage: StorageService = app.state.storage
        db = storage.connection()
        rows = db.execute(
            "SELECT id, folder_id, filename, storage_path, size_bytes, sha256_hash, created_at, updated_at FROM files WHERE deleted_at IS NULL ORDER BY created_at DESC"
        ).fetchall()
        return {"files": [dict(row) for row in rows]}

    @app.get("/files/{file_id}/download")
    def download_file(file_id: str, auth: AuthContext = Depends(_auth_context)) -> FileResponse:
        storage: StorageService = app.state.storage
        db = storage.connection()
        row = db.execute(
            "SELECT id, filename, storage_path FROM files WHERE id = ? AND deleted_at IS NULL",
            (file_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="File not found")
        full_path = storage.settings.files_path / row["storage_path"]
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="File payload missing")
        return FileResponse(path=full_path, filename=row["filename"])

    @app.patch("/files/{file_id}")
    def update_file(file_id: str, payload: FileUpdateRequest, request: Request, auth: AuthContext = Depends(_auth_context)) -> dict[str, object]:
        storage: StorageService = app.state.storage
        db = storage.connection()
        request_id = _request_id(request)
        row = db.execute(
            "SELECT id, folder_id, filename, storage_path, size_bytes, sha256_hash FROM files WHERE id = ? AND deleted_at IS NULL",
            (file_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="File not found")

        new_filename = _normalize_segment(payload.filename) if payload.filename is not None else row["filename"]
        new_folder_id = payload.folder_id if payload.folder_id is not None else row["folder_id"]
        if new_folder_id is not None:
            folder = db.execute("SELECT id FROM folders WHERE id = ? AND deleted_at IS NULL", (new_folder_id,)).fetchone()
            if folder is None:
                raise HTTPException(status_code=404, detail="Folder not found")

        db.execute(
            "UPDATE files SET filename = ?, folder_id = ?, updated_at = ? WHERE id = ?",
            (new_filename, new_folder_id, utc_now(), file_id),
        )
        _audit(
            db,
            actor_user_id=auth.user_id,
            action="file.update",
            status="success",
            request_id=request_id,
            extension_id=auth.extension_id,
            target_type="file",
            target_id=file_id,
            metadata={"filename": new_filename, "folder_id": new_folder_id},
        )
        db.commit()
        return {
            "id": file_id,
            "folder_id": new_folder_id,
            "filename": new_filename,
            "storage_path": row["storage_path"],
            "size_bytes": row["size_bytes"],
            "sha256_hash": row["sha256_hash"],
        }

    @app.delete("/files/{file_id}")
    def delete_file(file_id: str, request: Request, auth: AuthContext = Depends(_auth_context)) -> dict[str, object]:
        storage: StorageService = app.state.storage
        db = storage.connection()
        request_id = _request_id(request)
        row = db.execute(
            "SELECT id, storage_path FROM files WHERE id = ? AND deleted_at IS NULL",
            (file_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="File not found")

        payload_path = storage.settings.files_path / row["storage_path"]
        if payload_path.exists():
            payload_path.unlink()

        db.execute("UPDATE files SET deleted_at = ?, updated_at = ? WHERE id = ?", (utc_now(), utc_now(), file_id))
        _audit(
            db,
            actor_user_id=auth.user_id,
            action="file.delete",
            status="success",
            request_id=request_id,
            extension_id=auth.extension_id,
            target_type="file",
            target_id=file_id,
        )
        db.commit()
        return {"status": "deleted", "id": file_id}

    @app.get("/search")
    def search_files(q: str = Query(min_length=1), auth: AuthContext = Depends(_auth_context)) -> dict[str, object]:
        storage: StorageService = app.state.storage
        db = storage.connection()
        pattern = f"%{q}%"
        rows = db.execute(
            "SELECT id, folder_id, filename, storage_path, size_bytes, sha256_hash, created_at, updated_at FROM files WHERE deleted_at IS NULL AND filename LIKE ? COLLATE NOCASE ORDER BY filename",
            (pattern,),
        ).fetchall()
        return {"query": q, "results": [dict(row) for row in rows]}

    return app


app = create_app()


__all__ = ["create_app", "app"]
