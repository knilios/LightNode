# LightNode AI Handoff Spec

## 1. System Summary
LightNode is a single-node file storage system for Raspberry Pi-class hardware. It is a monolithic application with internal module boundaries, not a distributed system or microservice architecture.

Primary goals:
- Accountable authenticated file storage
- Hierarchical folder support
- Streaming uploads and downloads
- Filename-only search
- Audit logging for protected actions
- External-drive-backed runtime storage
- Drive registration via `.lightnode`

## 2. Core Design Rules
- Do not store runtime files or SQLite DB in the repository.
- Store all operational data on an external storage drive.
- Use SQLite as the metadata source of truth.
- Use stream-based file handling only.
- Use bearer token auth for all protected routes.
- API is the source of truth for identity and accountability.
- Extensions may add security, but API must enforce auth and audit.

## 3. Storage Architecture
### Required storage layout
- `/srv/lightnode/storage/.lightnode`
- `/srv/lightnode/storage/lightnode.db`
- `/srv/lightnode/storage/files/`
- `/srv/lightnode/storage/backups/`

### `.lightnode` marker file
The drive must contain a `.lightnode` JSON marker file.

Suggested fields:
- `format_version`
- `instance_id`
- `created_at`
- `last_seen_at`
- `lightnode_version`
- `db_path`
- `storage_mode`

Purpose:
- Identify the drive as registered LightNode storage
- Detect wrong-drive/mismatched-drive use
- Support format upgrades and startup validation

### Startup rules
- Verify mount exists and is writable.
- Verify `.lightnode` exists and is valid.
- Fail fast if the drive is missing or mismatched.
- Write a probe file to confirm write access.
- Expose storage readiness in `/health`.

## 4. Data Model
### users
- `id`
- `username`
- `password_hash`
- `role`
- `is_active`
- `created_at`

### auth_tokens
- `id`
- `token_hash`
- `user_id`
- `extension_id`
- `issued_at`
- `expires_at`
- `revoked_at`

### audit_logs
- `id`
- `actor_user_id`
- `action`
- `target_type`
- `target_id`
- `status`
- `request_id`
- `extension_id`
- `metadata_json`
- `created_at`

### folders
- `id`
- `name`
- `parent_folder_id`
- `full_path`
- `created_at`

### files
- `id`
- `folder_id`
- `filename`
- `storage_path`
- `size_bytes`
- `sha256_hash`
- `created_at`

## 5. Auth Model
Support two interchangeable bearer credential flows:
1. Username/password login
2. Host-issued access token

Both must be accepted by the same `Authorization: Bearer <token>` validation path.

Rules:
- Password login is for interactive use.
- Access token is for machine/service use.
- Token values are stored hashed in SQLite.
- Tokens must be revocable.
- Extension identity may be bound using `X-Extension-Id`.
- Auth context must expose user id, username, role, token id, and extension id when available.

## 6. API Surface
### Public
- `GET /health`
- `POST /auth/login`

### Protected
- `POST /auth/logout`
- `GET /auth/me`
- `POST /folders`
- `GET /root`
- `GET /folders/{folder_id}/contents`
- `POST /upload`
- `GET /files`
- `GET /files/{file_id}/download`
- `GET /search?q=...`

## 7. Folder and File Behavior
### Folders
- Create folder
- List folder contents
- List root contents
- Support nested hierarchy
- Support safe path normalization

### Files
- Upload as stream
- Download by id
- List files
- Search by filename only
- Store binary and text files without content extraction

### Write flow
1. Stream upload to temp file on external drive
2. Flush and fsync
3. Atomically rename to final path
4. Commit SQLite metadata
5. Emit audit log

## 8. Accountability Rules
Every protected action must create an audit log entry.

Capture at minimum:
- actor user id
- action name
- target type and id
- success/denied/error status
- request id
- extension id if present
- UTC timestamp

## 9. Host-Only Management
Provide host CLI commands for:
- create user
- reset password
- activate/deactivate user
- create access token
- list tokens
- revoke token

No public signup endpoint.

## 10. Raspberry Pi Deployment Assumptions
- Use external SSD or dedicated storage drive.
- Do not store runtime data on the SD card.
- Mount by UUID to a stable path.
- SQLite DB and file payloads live on the same external drive.
- Refuse writes if the drive is unavailable.
- Report mount, writability, and free-space health.

## 11. Non-Goals
- No distributed cluster
- No microservices
- No multi-node replication
- No public signup
- No content extraction search in MVP
- No repository-local runtime data in production

## 12. Reimplementation Order
1. Storage config and validation
2. `.lightnode` marker handling
3. SQLite DB on external drive
4. Auth and token flow
5. Folder and file APIs
6. Audit logging
7. Host CLI user/token management
8. Health reporting and failure handling
9. Migration from repo-local dev storage to external-drive production storage
