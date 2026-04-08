# Product Requirements Document (PRD) & Technical Spec: AI-Ready Edge NAS

## 1. System Overview
This project is a lightweight, AI-ready Network Attached Storage (NAS) application designed explicitly for the hardware constraints of a Raspberry Pi 5. It acts as both a user-facing file manager and a Model Context Protocol (MCP) server for LLMs.

**Architectural Constraints (STRICT):**
* **NO Microservices.** The core system MUST be a single compiled Monolith.
* **NO Distributed Systems.** It runs on a single node.
* **Architecture Pattern:** Microkernel (Core Engine + dynamically loaded Plugins).
* **Memory Limits:** Must assume severe RAM constraints (<8GB total system RAM). All file processing MUST use memory-efficient streams. Never load entire files into memory.

## 2. Infrastructure & Hardware Assumptions
* **Storage Mount:** The application reads/writes payload data exclusively to a single logical directory (`/mnt/storage`), which is managed at the OS level by MergerFS over multiple ext4 NVMe drives.
* **Metadata Store:** A local `SQLite` database acts as the single source of truth for file metadata, search, and MCP context.

## 3. Technology Stack
* **Language/Runtime:** [Insert your choice here: TypeScript (Bun/Node.js) OR Go 1.22+]
* **Database:** SQLite3
* **Frontend:** React or Svelte (compiled to static assets and served by the core engine)
* **Plugin Mechanism:** Dynamic Imports (if TypeScript) OR WebAssembly/wazero (if Go)

## 4. Core Engine Modules (To Be Implemented)

### Phase 1: SQLite Metadata Layer
Create the database initialization and query logic. Do not scan the physical disk for reads; query SQLite.

**Schema Requirements:**
* `files`: `id` (UUID), `filename`, `path` (relative to `/mnt/storage`), `size_bytes`, `mime_type`, `sha256_hash`, `extracted_text` (TEXT), `created_at`, `updated_at`.
* `tags`: `id`, `name`.
* `file_tags`: `file_id`, `tag_id`.

### Phase 2: In-Process Streaming Pipeline (File Ingestion)
Implement a pipeline to handle incoming file uploads via HTTP. 
**Execution Flow (Strict Order):**
1. Receive multipart HTTP stream.
2. Pass stream through a pass-through hasher (calculates SHA-256 on the fly).
3. Check DB if `sha256_hash` exists. If yes, abort stream, link existing file, return success.
4. Pass stream through a metadata extractor (if PDF/txt, strip raw text for AI context. Limit extraction to first 50KB to save CPU).
5. Sink the stream directly to `/mnt/storage/YYYY/MM/UUID.ext`.
6. On successful write, commit metadata and extracted text to SQLite.

### Phase 3: Model Context Protocol (MCP) Server
Implement an SSE (Server-Sent Events) or stdio endpoint that adheres to the MCP specification. 
**Exposed Tools:**
1. `search_files`: Accepts a query string. Performs a full-text search against the SQLite `extracted_text` and `filename` columns. Returns JSON metadata.
2. `get_file_metadata`: Accepts a file `id`. Returns tags, size, and hash.
3. `read_file_chunk`: Accepts a file `id`, `offset`, and `byte_count`. Reads directly from the physical disk and returns raw bytes or text.

### Phase 4: Microkernel Plugin System
Define the Interface/Contract that the Core Engine uses to load background tasks or extra endpoints.
**Plugin Contract (Interface):**
* `Init(coreContext)`: Called when the plugin is loaded. Injects DB connection and filesystem access.
* `Start()`: Begins the plugin's background loop or registers its HTTP routes.
* `Stop()`: Graceful shutdown to release memory.
*(Implementation details depend on TS Dynamic Imports or Go Wasm. Set up the plugin registry first.)*

### Phase 5: API & UI Server
* Serve the static HTML/JS/CSS frontend assets from a `/public` directory.
* Expose REST endpoints for the UI: `GET /api/files`, `POST /api/upload`, `DELETE /api/files/:id`.

## 5. Development Milestones for Copilot
1. Scaffold the project structure and SQLite initialization.
2. Build the Streaming Pipeline and verify memory usage during a 1GB file mock upload.
3. Build the REST API and wire it to the Pipeline.
4. Build the MCP Server and expose the SQLite search tool.
5. Define the Plugin interface and write one dummy "Hello World" plugin to test dynamic loading.