# LightNode Second Plan (Merged PRD + Technical Specification)

## 1. Product Intent
LightNode is a lightweight, AI-ready NAS application for constrained hardware (Raspberry Pi 5 class devices). It provides:
- Human file management through a web UI
- Agentic AI access through MCP tools
- Searchable filename metadata
- Reliable storage with redundancy awareness

This version merges the original plan with added scope for redundancy protection, Elastic compatibility, role-based access, and internet accessibility.

## 2. Non-Negotiable Architecture Constraints
- Single compiled monolith only (no separately deployed microservices).
- Single-node deployment only (no multi-computer distributed system).
- Microkernel pattern inside the monolith (core engine + plugin interface).
- RAM-conscious processing (<8 GB total system assumptions).
- Stream-based file handling only; never load full file into memory.

Microkernel ownership split (clarified):
- Core kernel responsibilities: metadata database, logical file/folder lifecycle, storage-adapter orchestration, auth policy enforcement, and plugin runtime.
- Extension service responsibilities (in-process modules): MCP endpoint, web UI delivery/API facade, and Windows filesystem connector.
- Terminology note: these are service modules/plugins, not independent network-deployed microservices.

## 3. Scope Boundary
### In Scope
- Redundancy file protection
- Elastic compatibility for metadata indexing sync
- AI MCP server and tool surface
- Web user interface
- Windows filesystem connection module
- Internet-accessible deployment mode
- External USB hard drive support on Raspberry Pi
- Universal file-type storage support (binary and text)
- Third-party storage backend for physical file/folder operations
- Native folder hierarchy (create/move/rename/delete) like Linux/Windows

### Out of Scope
- Multi-node clustering
- Distributed file replication across multiple machines
- Microservice split architecture

## 4. Users, Roles, and Permissions
## 4.1 Storage User (human; expected to be mostly single-user)
Responsibilities:
- Manage own files

Permissions:
- Create, read, update, delete own files
- Search own files and files shared with them

## 4.2 Agentic AI
Responsibilities:
- Manage files under delegated user context

Permissions:
- Same file permissions as the delegated human user
- Access to MCP tools based on scoped token

## 4.3 Admin / Hoster
Responsibilities:
- Operate and maintain hosting
- Manage all users and all files

Permissions:
- Full access to all files and system settings

## 4.4 Authorization Model
- Enforce role-based access control (RBAC) in API and MCP layer.
- Every request resolves an identity and role before file access.
- Agentic AI requests must carry owner/delegation context.
- Admin override is explicit and audit-logged.

## 5. Infrastructure Assumptions
- Physical storage provider: third-party hierarchical file system service via adapter.
- Selected provider profile: WebDAV-compatible backend (for example Nextcloud) as primary target.
- External USB HDD/SSD support is delegated to storage provider host configuration.
- Metadata source of truth: local SQLite.
- Optional Elastic side-index for compatibility and filename index integration.

External drive operational requirements:
- On startup, verify third-party storage endpoint is reachable and writable.
- If storage provider becomes unavailable, block writes with clear retryable errors.
- Provide admin-visible health status for storage connectivity, latency, and free-space/quota (if provider exposes it).

Notes on redundancy:
- Primary redundancy is handled by the chosen third-party storage system.
- Application-level integrity is enforced through SHA-256 content hash and metadata consistency checks.

## 6. Technology Decisions
- Runtime: TypeScript on Node.js (recommended for MCP and plugin ergonomics).
- Database: SQLite3 (with indexed filename search).
- Frontend: React compiled to static assets served by the monolith.
- Plugin mechanism: dynamic imports (in-process plugin loading).
- Optional integration: Elasticsearch-compatible client adapter.

(Alternative Go stack remains viable if implementation priorities shift to lower runtime overhead.)

## 7. Core Engine Modules
Core kernel (always loaded):
- Metadata engine (SQLite schema, repositories, transaction boundaries)
- File management engine (ingestion, dedup, storage path resolution, integrity)
- Authorization engine (RBAC policy checks used by all extensions)
- Plugin runtime (module registration, lifecycle, health state)

## Phase 1: Metadata and Index Layer
Implement SQLite initialization and repository layer first.

Required tables:
- folders: id (UUID), owner_id, name, parent_folder_id nullable, full_path, created_at, updated_at, deleted_at nullable
- files: id (UUID), owner_id, folder_id nullable, filename, full_path, size_bytes, mime_type, sha256_hash, provider_object_id nullable, created_at, updated_at, deleted_at nullable
- tags: id, name, created_at
- file_tags: file_id, tag_id
- shares: id, file_id, grantee_id, permission (read/write), created_at
- audit_logs: id, actor_id, actor_type (human/agent/admin), action, target_file_id nullable, metadata_json, created_at

Required indexes:
- Unique on files.sha256_hash
- Index on files.owner_id
- Index on files.filename
- Unique on folders(owner_id, full_path)
- Index on folders.parent_folder_id

Elastic compatibility layer:
- Build an indexing adapter interface with two implementations:
  - LocalSQLiteFilenameSearchAdapter (default)
  - ElasticFilenameSearchAdapter (optional)
- Write-through strategy: SQLite commit first, Elastic sync second (best-effort retry queue).

## Phase 2: Streaming Ingestion Pipeline
Strict processing flow for upload endpoint:
1. Accept multipart stream.
2. Stream through SHA-256 hasher.
3. Query hash existence in SQLite.
4. If duplicate exists:
  - Skip duplicate payload upload to storage provider
  - Link metadata to existing provider object reference
   - Return success with duplicate_of reference
5. Accept and persist all file types without content extraction.
6. Stream upload to storage provider path (/root/YYYY/MM/UUID.ext or equivalent provider path).
7. On successful provider write completion:
   - Commit SQLite metadata in one transaction
  - Emit async indexing event for Elastic filename adapter

Memory and reliability requirements:
- Backpressure-aware streams.
- Configurable chunk size.
- Use provider-compatible multipart/chunked upload where available.
- Optional local temp file spool with cleanup recovery only when provider upload API requires retries.
- Pre-write check for provider connectivity and quota/capacity when exposed.

## Phase 3: MCP Server
Implement MCP as an extension service module loaded by the kernel plugin runtime.
Expose MCP via SSE endpoint (primary) with optional stdio mode for local tooling.

Initial MCP tools:
- search_files(query, scope, limit, offset)
  - Searches filename only (and optionally mirrored filename index in Elastic)
  - Enforces role + ownership filtering
- get_file_metadata(id)
  - Returns owner, tags, size, hash, created_at, permissions
- read_file_chunk(id, offset, byte_count)
  - Streams byte ranges from storage provider with authorization checks

MCP security controls:
- Token-based authentication for AI clients
- Tool-level permission checks
- Per-tool rate limits
- Audit logging for all MCP actions

## Phase 4: Microkernel Plugin System
Define in-process plugin lifecycle contract:
- Init(coreContext)
- Start()
- Stop()

coreContext should provide:
- db handle
- file repository
- auth/permission service
- filename search adapter
- storage provider adapter
- logger and metrics hooks

Initial plugins:
- HelloPlugin: health endpoint + startup log
- ElasticSyncPlugin: async retry queue for failed Elastic sync operations

## Phase 5: API + UI Server
Implement UI/API as an extension service module loaded by the kernel plugin runtime.
Serve static frontend from /public and expose REST API.

Core endpoints:
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

Internet access requirements:
- TLS required for remote access
- Reverse-proxy friendly headers support
- Secure session handling (httpOnly, secure cookies or bearer tokens)
- CSRF protection for browser session flows

UI requirements:
- File list, upload, delete, search, metadata view
- Role-aware actions (hide unauthorized actions)
- Basic admin panel for user/agent token management

## Phase 6: Windows Filesystem Connector
Implement Windows filesystem connectivity as an extension service module (no separate deployment).

Responsibilities:
- Connect to Windows shared storage (for example SMB share) for import/export workflows.
- Mirror metadata references into SQLite without bypassing kernel authorization.
- Perform stream-based transfer only; no full-file buffering.

Safety requirements:
- Connector outages must not crash kernel or corrupt metadata transactions.
- All connector actions must emit audit logs with actor and path context.
- Mount/share credentials must be stored securely and rotated.

## 8. Redundancy and Data Protection Strategy
Storage-level redundancy:
- Use mirrored/parity-capable underlying layout in host configuration.
- Run periodic drive health checks (SMART) and filesystem scrubs where applicable.

Application-level protection:
- Content-addressable dedup by SHA-256.
- Optional periodic integrity re-hash jobs.
- Metadata backup job for SQLite (hot backup + retention policy).

Recovery expectations:
- Restore SQLite from backup.
- Reconcile metadata-to-file references through integrity scan utility.

## 9. Search Strategy
Primary search:
- Filename-only matching in SQLite (case-insensitive), backed by files.filename index.

Elastic compatibility mode:
- Optional secondary filename index for larger search workloads.
- Non-blocking sync from SQLite to Elastic.
- If Elastic unavailable, system remains fully functional on SQLite.

## 10. Security and Access Model
- RBAC enforced uniformly across REST and MCP.
- Every action logged to audit_logs.
- Admin actions produce elevated audit entries.
- Agentic AI operates under explicit delegated identity.
- Configurable CORS allowlist for internet-facing clients.

## 11. Observability and Operations
- Structured logs (JSON) with request_id and actor_id.
- Basic metrics: upload throughput, search latency, MCP calls, sync failures.
- Storage metrics: mount status, free space, and write failures by storage path.
- Health endpoints:
  - /health/live
  - /health/ready
- Graceful shutdown with stream drain and plugin stop timeout.

## 12. Delivery Milestones
1. Project scaffold, SQLite schema, RBAC skeleton, health endpoints.
2. Storage provider adapter (WebDAV profile) and health checks.
3. Streaming upload pipeline through provider adapter with dedup and metadata commit.
4. Plugin runtime stabilization and kernel/extension boundary tests.
5. REST API + UI extension module with authenticated file and folder operations.
6. MCP extension module with three core tools and authorization.
7. Windows filesystem connector extension module (SMB path integration).
8. ElasticSync extension module + internet hardening (TLS/proxy/auth/CSRF/CORS/audit).
9. Reliability validation: 1 GB streaming test, backup/restore drill, integrity check pass.

## 13. Acceptance Criteria
- Monolith kernel runs on single node and loads extension modules for UI/API, MCP, and Windows filesystem connector.
- Upload path processes large files via streaming without memory spikes.
- System accepts and stores all file types without format-based rejection (except explicit policy/security blocks).
- System supports hierarchical folder operations (create, list, move/rename, delete) like Linux/Windows semantics.
- Duplicate files are detected by hash and linked without duplicate payload writes.
- Role checks prevent unauthorized CRUD/search across both REST and MCP.
- Search behavior is filename-only across UI, REST, and MCP.
- Windows connector operations are authorized through the same RBAC checks as local storage operations.
- Local SQLite search works independently of Elastic availability.
- Internet access works securely over TLS with authenticated sessions/tokens.
- System can read/write data through a third-party storage backend configured on Raspberry Pi host storage.
- If storage backend becomes unavailable, uploads are blocked safely and errors are reported without data corruption.
- Backup and restore process is documented and successfully tested.

## 14. Risks and Mitigations
- Risk: Elastic sync drift from SQLite.
  - Mitigation: SQLite as source of truth + retry queue + periodic reconciliation job.
- Risk: Corruption or sudden power loss.
  - Mitigation: Atomic writes, fsync, journaling, SQLite backup schedule.
- Risk: Over-permissioned agent tokens.
  - Mitigation: Scoped MCP tokens, least privilege, short TTL where possible.

## 15. Suggested Repository Structure
- /cmd or /src/core
- /src/api
- /src/mcp
- /src/connectors/windows-fs
- /src/storage-adapters/webdav
- /src/pipeline
- /src/plugins
- /src/auth
- /src/search
- /src/ui (frontend source)
- /public (compiled assets)
- /migrations
- /docs

This structure keeps implementation modular while preserving a single deployable monolith.