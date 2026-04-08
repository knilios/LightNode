# LightNode Mock Design (UI + UX)

## 1. Design Intent
LightNode should feel like a local-first, reliable storage console with simple folder navigation, fast filename search, and clear role-based controls.

Primary goals:
- Make file and folder actions obvious and low-friction.
- Keep search simple: filename-only search with immediate results.
- Expose storage health clearly (provider online/offline, quota/free space).
- Avoid clutter for single-user flows, but still support admin capabilities.

## 2. Information Architecture
Top-level navigation:
- Files
- Shared
- Search
- MCP Access
- Storage Health
- Admin (visible for admin role only)

Global layout zones:
- Left sidebar: navigation + quick actions
- Main panel: current page content
- Right utility drawer (optional): metadata preview and activity log

## 3. Visual Direction
Style direction:
- Clean utility console, low visual noise
- High contrast for filenames and actions
- Soft status color system for health and permission states

Typography:
- Heading: Space Grotesk
- Body/UI: IBM Plex Sans
- Monospace (IDs/hashes): IBM Plex Mono

Color tokens:
- Background: #F5F7F2
- Surface: #FFFFFF
- Text primary: #1E2A22
- Text secondary: #5C6B61
- Accent primary: #2F7D4A
- Accent warning: #C58C1A
- Accent danger: #B43A2A
- Border: #D9E0D8

## 4. Core Screens
## 4.1 Files Page (Primary)
Purpose:
- Browse folders
- Manage files/folders
- Upload and bulk actions

Desktop wireframe:
+--------------------------------------------------------------------------------+
| Top Bar: LightNode | Filename Search [_____________] | Upload | New Folder      |
+----------------------+---------------------------------------------------------+
| Sidebar              | Breadcrumb: Home / Projects / AI                        |
| - Files              +---------------------------------------------------------+
| - Shared             | Toolbar: Sort | View: List/Grid | Select | Refresh      |
| - Search             +---------------------------------------------------------+
| - MCP Access         | Name                Size      Type      Modified    ... |
| - Storage Health     | docs/               --        Folder    Today          |
| - Admin              | design.png          2.1 MB    image     Today          |
|                      | notes.txt           11 KB     text      Yesterday      |
|                      | model.bin           1.3 GB    binary    Yesterday      |
+----------------------+---------------------------------------------------------+
| Footer status: Provider Online | Quota 42% used | Last sync 12:42             |
+--------------------------------------------------------------------------------+

Mobile wireframe:
+----------------------------------------------+
| LightNode            [Search icon] [Menu]    |
+----------------------------------------------+
| Breadcrumb: Home / Projects                  |
| [Upload] [New Folder]                        |
+----------------------------------------------+
| docs/                                        |
| design.png                2.1 MB             |
| notes.txt                 11 KB              |
| model.bin                 1.3 GB             |
+----------------------------------------------+
| Provider Online | 42% used                   |
+----------------------------------------------+

## 4.2 Search Page (Filename-only)
Purpose:
- Fast lookup by filename only
- No content search controls shown

Wireframe:
+--------------------------------------------------------------------------------+
| Search Files                                                                     |
| Query: [ report ] [Search] [Clear]                                              |
| Filters: Scope (My files / Shared) | Type | Date modified                        |
+--------------------------------------------------------------------------------+
| Results (23)                                                                     |
| report-q1.xlsx      /Finance/2026     1.2 MB    Updated 2d ago                   |
| report-final.docx   /Finance/2026     0.8 MB    Updated 5d ago                   |
+--------------------------------------------------------------------------------+

Behavior:
- Debounced search after 250 ms while typing
- Exact and partial filename matching, case-insensitive
- Enter key forces immediate query
- Empty query returns recent files

## 4.3 Upload Flow
Entry points:
- Upload button in top bar
- Drag and drop area in files page

Upload modal states:
- Idle: select file(s)
- Uploading: per-file progress bars
- Completed: success list
- Partial fail: retry failed files

Rules shown in UI:
- Any file type accepted
- Duplicate file content may be deduplicated automatically
- Upload blocked when storage provider is unavailable

## 4.4 Folder Management
Supported actions:
- Create folder
- Rename folder
- Move folder
- Delete folder (with confirmation)

Interaction details:
- Rename inline in list row
- Move via dialog with folder tree picker
- Delete confirmation includes child item count

## 4.5 File Details Drawer
Displayed fields:
- Name
- Path
- Type
- Size
- SHA-256
- Owner
- Created/Updated time
- Share status

Actions:
- Copy path
- Download
- Share
- Delete

## 4.6 MCP Access Page
Purpose:
- Manage agent tokens and scopes

Contents:
- Token list (name, scope, created, expiry, last used)
- Create token form
- Revoke token action

Important note text:
- MCP search supports filename-only matching.

## 4.7 Storage Health Page
Widgets:
- Provider status: Online/Offline
- Latency (p50/p95)
- Quota used/free (if provider exposes it)
- Recent storage errors

Status colors:
- Green: healthy
- Amber: degraded latency
- Red: unavailable

## 5. Role-based UX Rules
Storage User:
- Sees Files, Shared, Search, MCP Access, Storage Health
- Can CRUD own files/folders and shared resources per permission

Agentic AI:
- No direct UI login by default (token-based MCP use)
- If shown in admin panel, display token scopes only

Admin/Hoster:
- Sees Admin section
- Can view/manage all files/folders and token policies

## 6. Micro-interactions
- Row hover reveals quick actions (download, share, delete)
- Keyboard shortcuts:
  - Ctrl+K opens filename search
  - Del triggers delete confirm for selected item
  - Ctrl+Shift+N creates folder
- Non-blocking toast notifications for success/fail states

## 7. Empty and Error States
Empty folder state:
- Message: This folder is empty
- Actions: Upload File, Create Folder

Provider offline state:
- Banner on top: Storage provider unavailable. Upload and write actions are paused.
- Read operations continue where possible from metadata and accessible objects.

Permission denied state:
- Message: You do not have permission for this action.
- Action: Request access (for shared workflow)

## 8. API to UI Mapping
Files page:
- GET /api/files
- GET /api/folders
- POST /api/upload
- POST /api/folders
- PATCH /api/folders/:id
- DELETE /api/files/:id
- DELETE /api/folders/:id

Search page:
- GET /api/search?q=<filename>

Health page:
- GET /health/ready
- GET /health/live

## 9. Implementation-ready Component List
- AppShell
- SidebarNav
- TopSearchBar
- BreadcrumbTrail
- FileTable
- FileGrid
- FolderTreePicker
- UploadModal
- FileDetailsDrawer
- TokenManagerPanel
- StorageHealthPanel
- ConfirmDialog
- ToastCenter

## 10. First Clickable Prototype Scope
Prototype v1 screens:
- Files page
- Search page
- Upload modal
- Storage health page

Prototype v1 interactions:
- Browse folders
- Filename search
- Upload flow states
- Folder create/rename/delete

Success criteria for prototype:
- A user can navigate folders, find files by filename, and complete upload without guidance.
- Storage offline behavior is understandable within 3 seconds.
