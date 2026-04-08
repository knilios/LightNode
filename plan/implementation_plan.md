# LightNode Implementation Plan

## 1. Goal
Build LightNode as a single-node Microkernel monolith where:
- Core kernel owns metadata, file/folder lifecycle, storage-adapter orchestration, authorization, and plugin runtime.
- Extension service modules provide MCP, Web UI/API, and Windows filesystem connectivity.
- System supports Raspberry Pi external USB storage and internet access with secure controls.
- System accepts all file types for storage and retrieval.
- Physical storage operations are delegated to a third-party hierarchical file system backend.

## 2. Architecture Principles
- One deployable service process (no independently deployed microservices).
- Strict kernel-extension boundary: extensions cannot bypass kernel auth or metadata rules.
- Stream-first design for all file transfer operations.
- SQLite is source of truth for metadata and permissions.
- Search behavior is filename-only.
- Optional Elastic filename indexing remains secondary and eventually consistent.

## 3. Recommended Tech Stack
## 3.1 Runtime and Language
- TypeScript 5.x
- Node.js 22 LTS

Reasoning:
- Strong MCP and ecosystem support
- Good stream APIs for low-memory pipelines
- Simpler plugin loading with dynamic imports

## 3.2 Backend Libraries
- HTTP framework: Fastify
- Multipart upload: @fastify/multipart
- Validation and schema: zod
- SQLite: better-sqlite3 (synchronous and fast for local embedded DB)
- Auth tokens: jose (JWT/JWK handling)
- Password hashing (if local login is needed): argon2
- Logging: pino
- Metrics: prom-client
- File type detection: file-type
- WebDAV client (storage provider adapter): webdav
- SMB/Windows share connector: smb2 (or alternative SMB client wrapper)

## 3.3 Frontend
- React + Vite + TypeScript
- UI components: shadcn/ui or lightweight custom components
- Data fetching: TanStack Query

## 3.4 Testing and Quality
- Unit/integration: Vitest
- API tests: supertest
- End-to-end UI: Playwright
- Lint: ESLint
- Format: Prettier

## 3.5 Operations
- Reverse proxy: Caddy or Nginx for TLS termination
- Process supervisor: systemd on Raspberry Pi OS
- Optional filename index backend: Elasticsearch-compatible endpoint

## 4. High-Level Module Design
## 4.1 Core Kernel Modules
- MetadataEngine
  - Owns SQLite schema, migrations, repositories, and transaction boundaries.
- FileEngine
  - Upload pipeline, dedup by SHA-256, folder-aware path resolution, integrity checks.
- FolderEngine
  - Create/list/move/rename/delete folder logic and path normalization.
- StorageAdapterEngine
  - Provider-agnostic API for put/get/delete/move/list operations.
- AuthEngine
  - RBAC policies for user, agentic AI, and admin/hoster roles.
- PluginRuntime
  - Discovers, initializes, starts, stops extension modules.
- StorageHealthService
  - Verifies mount presence, writability, and free-space thresholds.

## 4.2 Extension Service Modules
- ApiUiModule
  - Hosts REST endpoints and serves static UI assets.
- McpModule
  - Exposes MCP tools over SSE (and optional stdio mode).
- WindowsFsConnectorModule
  - Handles import/export or sync with Windows SMB shares.
- WebDavStorageAdapterModule
  - Implements StorageAdapterEngine against WebDAV-compatible backend.
- ElasticSyncModule (optional)
  - Mirrors filename index content from SQLite to Elastic.

## 5. Data Model (SQLite)
## 5.1 Core Tables
- folders
  - id, owner_id, name, parent_folder_id, full_path, created_at, updated_at, deleted_at
- files
  - id, owner_id, folder_id, filename, full_path, size_bytes, mime_type, sha256_hash, provider_object_id, created_at, updated_at, deleted_at
- tags
  - id, name, created_at
- file_tags
  - file_id, tag_id
- shares
  - id, file_id, grantee_id, permission, created_at
- users
  - id, username, role, created_at, updated_at
- agent_tokens
  - id, owner_id, token_hash, scopes_json, expires_at, created_at
- audit_logs
  - id, actor_id, actor_type, action, target_file_id, metadata_json, created_at

## 5.2 Indexes
- Unique index: files.sha256_hash
- Index: files.owner_id
- Index: files.filename
- Unique index: folders(owner_id, full_path)
- Index: folders.parent_folder_id

## 6. File and Storage Design
## 6.1 Storage Paths
- Configurable STORAGE_PROVIDER_URL and STORAGE_PROVIDER_ROOT_PATH
- Canonical file location format: /<folder_path>/<filename> in provider namespace

## 6.2 External USB Drive Support
- Validate provider endpoint and write access during startup.
- Reject writes safely if provider is unreachable.
- Expose provider health (connectivity/latency/quota) in health endpoints and admin UI.

## 6.3 Upload Pipeline
1. Receive multipart stream.
2. Stream through SHA-256 hasher.
3. Check duplicate hash in DB.
4. If duplicate, skip payload write and link metadata.
5. Persist all file types without content extraction.
6. Stream upload to storage provider through StorageAdapterEngine.
7. If provider requires retries, use temp spool + resumable retry strategy.
8. Commit metadata and audit log in one transaction.

## 7. API and MCP Surface
## 7.1 REST API (ApiUiModule)
- GET /api/files
- POST /api/upload
- DELETE /api/files/:id
- GET /api/files/:id/metadata
- GET /api/search?q=...
- POST /api/files/:id/share
- GET /api/folders
- POST /api/folders
- PATCH /api/folders/:id
- DELETE /api/folders/:id
- GET /health/live
- GET /health/ready

## 7.2 MCP Tools (McpModule)
- search_files(query, scope, limit, offset)
- get_file_metadata(id)
- read_file_chunk(id, offset, byte_count)

Rules:
- Every tool call passes through AuthEngine checks.
- Every tool call writes audit logs.
- read_file_chunk must support arbitrary binary files and return bytes safely.
- search_files matches filename only (not file content/body text).

## 8. Security Plan
- RBAC enforced in kernel, not in extensions only.
- Scoped agent tokens with expiration and revocation.
- TLS for internet access.
- CSRF protection for cookie-based browser sessions.
- CORS allowlist for trusted frontends.
- Structured audit logs for sensitive actions.

## 9. Repository Structure
- src/core/bootstrap/
- src/core/config/
- src/core/plugin-runtime/
- src/core/auth/
- src/core/storage/
- src/core/files/
- src/core/folders/
- src/core/storage-adapter/
- src/core/metadata/
- src/core/audit/
- src/extensions/api-ui/
- src/extensions/mcp/
- src/extensions/windows-fs-connector/
- src/extensions/webdav-storage-adapter/
- src/extensions/elastic-sync/
- src/shared/types/
- src/shared/errors/
- src/shared/utils/
- ui/
- public/
- migrations/
- tests/unit/
- tests/integration/
- tests/e2e/
- docs/

## 10. Delivery Phases
## Phase 0: Foundation
- Initialize TypeScript monorepo-style foldering in one process project.
- Add lint/test/build scripts.
- Add configuration loader and environment schema validation.

Exit criteria:
- App boots and logs startup configuration safely.

## Phase 1: Kernel Core
- Implement MetadataEngine with migrations.
- Implement FolderEngine for hierarchical path rules.
- Implement AuthEngine with RBAC model.
- Implement StorageAdapterEngine interface.
- Implement PluginRuntime lifecycle.
- Implement StorageHealthService checks.

Exit criteria:
- Kernel boots, validates storage provider connectivity, and can load a dummy extension.

## Phase 2: File Engine
- Implement WebDAV storage adapter module.
- Implement stream upload pipeline through adapter and dedup.
- Implement retry-safe provider write flow.
- Implement metadata commit and audit logging.

Exit criteria:
- 1 GB upload test passes without memory spikes.

## Phase 3: API/UI Extension
- Build REST endpoints (files + folders) and role-aware enforcement.
- Build minimal React UI for list/upload/delete/search.

Exit criteria:
- Human user can complete end-to-end file and folder lifecycle from browser.

## Phase 4: MCP Extension
- Implement SSE MCP endpoint and three core tools.
- Add token auth and tool-level rate limits.

Exit criteria:
- Agentic AI can search/read metadata/chunks under delegated scope.

## Phase 5: Windows FS Connector Extension
- Implement SMB connector and import/export operations.
- Enforce kernel auth and full audit coverage.

Exit criteria:
- Connector operations work without bypassing kernel policies.

## Phase 6: Elastic Compatibility Extension
- Add optional ElasticSyncModule with retry queue.
- Add reconciliation job and drift detection.

Exit criteria:
- Filename search works with SQLite only and optionally with Elastic sync.

## Phase 7: Hardening and Ops
- TLS and reverse proxy deployment profile.
- Backup/restore drill for SQLite + metadata reconciliation.
- Observability dashboards and alert thresholds.

Exit criteria:
- Recovery and operational runbook validated.

## 11. Testing Plan
- Unit tests
  - Hashing and dedup logic
  - RBAC policy evaluator
  - Folder path normalization and move/rename rules
  - Plugin lifecycle behavior
- Integration tests
  - Upload pipeline with large files
  - Folder CRUD and move operations
  - MCP tool authorization
  - Storage provider outage behavior
  - Windows SMB connector failure handling
- E2E tests
  - UI upload/search/delete flows
  - Role-restricted actions in UI and API

## 12. Key Risks and Mitigations
- Risk: Extensions bypass kernel logic.
  - Mitigation: Expose only kernel service interfaces to extensions.
- Risk: External drive disconnect during write.
  - Mitigation: temp-file strategy, transactional metadata commit, fail-safe write lock.
- Risk: SMB connector instability.
  - Mitigation: retries, circuit breaker, explicit timeout and dead-letter logging.
- Risk: Elastic drift.
  - Mitigation: SQLite authority plus periodic reconciliation.

## 13. Definition of Done
- Kernel manages all metadata and file system operations.
- MCP/UI/Windows connector are loaded as extension modules.
- RBAC and audit are consistently enforced for REST, MCP, and connector operations.
- Any file type can be uploaded, stored, retrieved, and deleted through authorized flows.
- Hierarchical folders behave like Linux/Windows semantics in UI/API/MCP flows.
- Third-party storage provider behavior is verified for both normal and failure paths.
- Deployment and recovery documentation is complete and tested.
