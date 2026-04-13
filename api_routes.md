# LightNode Core API Routes

This document describes the currently implemented HTTP routes in the microkernel core service.

## Base

- Default local base URL: `http://127.0.0.1:8000`
- Protected routes require header: `Authorization: Bearer <token>`
- Optional audit correlation header: `X-Request-Id: <id>`
- Optional extension identity header: `X-Extension-Id: <extension-id>`

## Public Routes

### GET /health
Returns overall service and storage state.

Response shape:
- `status`: `starting` | `ready` | `degraded`
- `ready`: boolean
- `storage`: mount, marker, db, free-space details

### GET /health/live
Liveness probe.

Response:
- `{ "status": "alive" }`

### GET /health/ready
Readiness probe with storage details.

Response shape:
- `status`: `starting` | `ready` | `degraded`
- `ready`: boolean
- `storage`: storage state object

### POST /auth/login
Creates a bearer token using username/password.

Request body:
```json
{
  "username": "alice",
  "password": "secret123"
}
```

Response:
```json
{
  "access_token": "<token>",
  "token_type": "bearer",
  "user": {
    "id": "<user-id>",
    "username": "alice",
    "role": "admin"
  }
}
```

Errors:
- `401` invalid credentials
- `403` inactive user

## Protected Auth Routes

### POST /auth/logout
Revokes the current bearer token.

Response:
```json
{
  "status": "ok"
}
```

### GET /auth/me
Returns authenticated identity context.

Response:
```json
{
  "id": "<user-id>",
  "username": "alice",
  "role": "admin",
  "token_id": "<token-id>",
  "extension_id": null
}
```

## Protected Folder Routes

### POST /folders
Creates a folder.

Request body:
```json
{
  "name": "docs",
  "parent_folder_id": null
}
```

Response:
```json
{
  "id": "<folder-id>",
  "name": "docs",
  "parent_folder_id": null,
  "full_path": "/docs"
}
```

Errors:
- `400` invalid path segment
- `404` parent folder not found
- `409` folder conflict

### GET /root
Lists root folders and files.

Response:
```json
{
  "folders": [ ... ],
  "files": [ ... ]
}
```

### GET /folders/{folder_id}/contents
Lists one folder plus child folders/files.

Response:
```json
{
  "folder": { ... },
  "folders": [ ... ],
  "files": [ ... ]
}
```

Errors:
- `404` folder not found

### PATCH /folders/{folder_id}
Updates folder metadata (rename/move).

Request body:
```json
{
  "name": "docs-renamed",
  "parent_folder_id": null
}
```

Response:
```json
{
  "id": "<folder-id>",
  "name": "docs-renamed",
  "parent_folder_id": null,
  "full_path": "/docs-renamed"
}
```

Errors:
- `400` invalid self-parent or invalid segment
- `404` folder or parent not found
- `409` path conflict

### DELETE /folders/{folder_id}
Soft-deletes an empty folder.

Response:
```json
{
  "status": "deleted",
  "id": "<folder-id>"
}
```

Errors:
- `404` folder not found
- `409` folder is not empty

## Protected File Routes

### POST /upload
Uploads a file as stream.

Query params:
- `folder_id` (optional)

Multipart form:
- `file` (required)

Response:
```json
{
  "id": "<file-id>",
  "folder_id": "<folder-id-or-null>",
  "filename": "hello.txt",
  "storage_path": "<generated-storage-name>",
  "size_bytes": 11,
  "sha256_hash": "<sha256>"
}
```

Errors:
- `404` folder not found

### GET /files
Lists active files.

Response:
```json
{
  "files": [ ... ]
}
```

### GET /files/{file_id}/download
Downloads file payload by ID.

Response:
- Binary file response (`FileResponse`)

Errors:
- `404` file metadata missing or payload missing

### PATCH /files/{file_id}
Updates file metadata (rename and/or folder assignment).

Request body:
```json
{
  "filename": "renamed.txt",
  "folder_id": null
}
```

Response:
```json
{
  "id": "<file-id>",
  "folder_id": null,
  "filename": "renamed.txt",
  "storage_path": "<generated-storage-name>",
  "size_bytes": 11,
  "sha256_hash": "<sha256>"
}
```

Errors:
- `404` file or target folder not found
- `400` invalid filename

### DELETE /files/{file_id}
Deletes file payload and soft-deletes metadata.

Response:
```json
{
  "status": "deleted",
  "id": "<file-id>"
}
```

Errors:
- `404` file not found

### GET /search?q=<term>
Filename-only search (case-insensitive).

Response:
```json
{
  "query": "hello",
  "results": [ ... ]
}
```

Notes:
- Requires `q` with minimum length 1.

## Auth and Audit Notes

- All protected routes enforce bearer token validation.
- Tokens are hashed in SQLite and checked against `auth_tokens`.
- Protected actions are audit-logged into `audit_logs` with status and request id.

## Current Scope Notes

- This repo is the microkernel core service implementation.
- Host-level user/token bootstrap and management is terminal-only via CLI (`python -m lightnode admin ...`), not public API routes.
