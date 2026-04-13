# LightNode Core Handoff Summary

## 1. Project Goal
LightNode is a single-node file storage system for Raspberry Pi-class hardware. It is built as a lightweight monolith with internal module boundaries, not as distributed microservices. The main purpose is to provide accountable, authenticated file storage with folder hierarchy, streaming uploads, filename search, audit logging, and external-drive-backed persistence.

## 2. Core Responsibilities
The core is responsible for:
- Authentication and identity resolution
- Authorization and request protection
- Folder and file lifecycle management
- Streaming file upload and download
- SQLite metadata storage
- Audit logging for protected actions
- Storage drive validation and health reporting
- Host-level user and token management
- Drive registration using a `.lightnode` marker file

## 3. Functional Areas

### Authentication and Identity
- Supports username/password login.
- Supports host-issued access tokens for services or extensions.
- Both auth modes are interchangeable at request time because both produce bearer credentials.
- All protected API routes require `Authorization: Bearer <token>`.
- Authentication context should identify:
  - user id
  - username
  - role
  - optional extension id
  - token id

### Authorization and Accountability
- API is the source of truth for identity and accountability.
- Every protected action must be audited.
- Audit logs should record:
  - actor user id
  - action name
  - target type and id
  - success/denied/error status
  - request id
  - extension id if present
  - timestamp
  - optional metadata JSON

### Folder Management
- Create folders
- List folders
- View folder contents
- Support hierarchical folder structure
- Support root listing
- Folder semantics should behave like a normal filesystem:
  - create
  - rename
  - move
  - delete
- Folder paths must be normalized and safe

### File Management
- Upload files as streamed input
- Never load full file into memory
- Download files by id
- List files
- Search files by filename only
- Keep original filename and storage metadata
- Store file contents on external storage, not in the repository

### Metadata Database
- SQLite is the metadata source of truth.
- On Raspberry Pi, the DB should live on the external storage drive.
- DB must track:
  - folders
  - files
  - users
  - auth tokens
  - audit logs
- Use SQLite WAL mode for reliability.
- Use transactions for metadata changes.

### Storage System
- Storage root must be configurable.
- Production storage should be on a dedicated external drive.
- The repository should not store runtime payloads or the database.
- Storage layer must:
  - verify mount/writability on startup
  - reject writes if unavailable
  - support atomic writes using temp file + rename
  - expose health status
  - optionally enforce free-space thresholds

### Drive Registration and Marker File
- The storage drive should contain a `.lightnode` file.
- `.lightnode` identifies the drive as a registered LightNode drive.
- It should store:
  - format version
  - instance id
  - created at
  - last seen at
  - LightNode version
  - DB path
  - storage mode
- Startup must verify `.lightnode`.
- If missing or mismatched, the system should fail fast or enter safe mode depending on config.

## 4. Data Model Summary

### Users
- id
- username
- password hash
- role
- active flag
- created at

### Auth Tokens
- id
- token hash
- user id
- extension id
- issued at
- expires at
- revoked at

### Audit Logs
- id
- actor user id
- action
- target type
- target id
- status
- request id
- extension id
- metadata JSON
- created at

### Folders
- id
- name
- parent folder id
- full path
- created at

### Files
- id
- folder id
- filename
- storage path
- size bytes
- sha256 hash
- created at

## 5. API Features

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

## 6. Host-Only Management Commands
The host machine should support CLI commands to:
- create user
- reset password
- activate/deactivate user
- create access token
- list tokens
- revoke token

These commands are for admin bootstrap and extension credential management, not public API users.

## 7. Raspberry Pi Deployment Assumptions
- Use an external SSD or drive as the main runtime storage.
- The SD card should not hold operational data.
- Mount should be stable and UUID-based.
- App should fail fast if storage is missing or not writable.
- Health endpoints should show:
  - storage mounted
  - storage writable
  - database reachable
  - free space remaining
  - `.lightnode` presence and version

## 8. Non-Goals
- No distributed cluster
- No multi-node replication
- No microservices
- No content extraction for search in MVP
- No repository-local runtime storage in production
- No open public signup

## 9. Important Design Principle
Identity and accountability must be enforced at the API boundary, not left to extensions alone. Extensions may add their own security, but the API must remain the authoritative gatekeeper and audit source.

## 10. Suggested Reimplementation Order
1. Storage configuration and startup validation
2. `.lightnode` marker file creation and verification
3. SQLite DB on external drive
4. Auth and token flows
5. Folder and file lifecycle APIs
6. Audit logging
7. Host CLI management commands
8. Health reporting and failure handling
9. Migration from repository-local development storage to production storage
