# LightNode

LightNode is a storage-first file system service for single-node Raspberry Pi-class hardware.

This repository implements the microkernel core service (kernel monolith) that powers authentication, storage, metadata, audit, and API behavior.

## Quick Start

The current implementation focuses on storage preparation and inspection from the terminal.

### Install in your virtual environment

Before running `python -m lightnode`, install the project once in editable mode:

```powershell
python -m pip install -e .
```

This avoids `No module named lightnode` errors.

### Prepare an empty storage drive

Windows:

```powershell
python -m lightnode storage init --root E:\lightnode-storage
```

Linux:

```bash
python -m lightnode storage init --root /srv/lightnode/storage
```

### Inspect a prepared storage drive

Windows:

```powershell
python -m lightnode storage status --root E:\lightnode-storage
```

Linux:

```bash
python -m lightnode storage status --root /srv/lightnode/storage
```

### Run the API service

After storage has been initialized, start the FastAPI service with Uvicorn. Point `LIGHTNODE_STORAGE_ROOT` at the prepared storage directory first:

Windows:

```powershell
$env:LIGHTNODE_STORAGE_ROOT = "D:\lightnode"
uvicorn lightnode.app:app --reload
```

Linux:

```bash
export LIGHTNODE_STORAGE_ROOT=/srv/lightnode/storage
uvicorn lightnode.app:app --reload
```

By default the service listens on `http://127.0.0.1:8000`. The OpenAPI docs are available at `http://127.0.0.1:8000/docs`.

If you want to use a different storage directory, initialize it first with `python -m lightnode storage init --root <storage-path>` and then start the API with the same path in `LIGHTNODE_STORAGE_ROOT`.

## User and Token Management

After storage is prepared, create users and access tokens using the host admin CLI. All commands require `--root` to point to your storage directory.

### Create a User

```bash
python -m lightnode admin user create --root <storage-path> --username <username> --password <password>
```

Returns JSON with `id` and `username`.

### Create an Access Token

```bash
python -m lightnode admin token create --root <storage-path> --username <username>
```

Returns JSON with `token_id` and the raw `token`. **Save the token** — it's hashed in the database and cannot be retrieved later.

### List Tokens for a User

```bash
python -m lightnode admin token list --root <storage-path> --username <username>
```

### Revoke a Token

```bash
python -m lightnode admin token revoke --root <storage-path> --token-id <token_id>
```

### Manage User Status

```bash
# Reset a user's password
python -m lightnode admin user reset-password --root <storage-path> --username <username> --password <password>

# Activate a deactivated user
python -m lightnode admin user activate --root <storage-path> --username <username>

# Deactivate a user (blocks login)
python -m lightnode admin user deactivate --root <storage-path> --username <username>
```

### Example Workflow

```powershell
# Point to your storage directory (e.g., from storage init)
$ROOT = "E:\lightnode-storage"

# Create a user
python -m lightnode admin user create --root $ROOT --username alice --password secret123

# Generate a token for that user
python -m lightnode admin token create --root $ROOT --username alice
```

## Using Access Tokens with the API

Once you have a bearer token, use it to authenticate API requests:

```bash
curl -H "Authorization: Bearer <your_token>" http://localhost:8000/auth/me
```

All protected endpoints require a valid, active bearer token via the `Authorization: Bearer` header.

## Notes

- The storage root must contain a `.lightnode` marker file after initialization.
- SQLite metadata and file payloads live on the same storage drive.
- Admin CLI commands require local database access (host-only, no network auth).
- The terminal commands work on both Windows and Linux; the default storage root is OS-aware, but you can always pass `--root` explicitly.
