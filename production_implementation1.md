# LightNode Production Implementation Plan 1

## 1. Goal
Move LightNode from prototype storage to a Raspberry Pi-ready production storage layout where:
- File payloads are stored on a dedicated external drive.
- The SQLite metadata database is stored on the same drive.
- The drive is registered and verified by LightNode using a `.lightnode` marker file.
- The API remains accountable, authenticated, and auditable.

## 2. Production Storage Principles
- Never store operational files or the metadata database in the repository.
- Use an external SSD or other dedicated storage device for all runtime data.
- Treat the storage drive as a first-class LightNode dependency.
- Fail fast if the drive is missing, unmounted, read-only, or not writable.
- Prefer deterministic mount paths and UUID-based mounting on Raspberry Pi.

## 3. Target Storage Layout
Recommended layout on the storage drive:
- `/srv/lightnode/storage/.lightnode`
- `/srv/lightnode/storage/lightnode.db`
- `/srv/lightnode/storage/files/`
- `/srv/lightnode/storage/backups/`

## 4. `.lightnode` Marker File
The `.lightnode` file identifies the drive as a LightNode-registered drive and stores storage metadata.

Recommended content shape:
```json
{
  "format_version": 1,
  "instance_id": "<uuid>",
  "created_at": "<utc timestamp>",
  "last_seen_at": "<utc timestamp>",
  "lightnode_version": "0.1.0",
  "db_path": "lightnode.db",
  "storage_mode": "external-drive"
}
```

Purpose:
- Bind the drive to a specific LightNode instance.
- Detect accidental use of the wrong drive.
- Track storage format version for migrations.
- Provide a clear place for future storage metadata.

## 5. Startup Behavior
On startup, LightNode should:
1. Read configuration for the storage root path.
2. Verify the path exists and is writable.
3. Read `.lightnode` from the storage root.
4. If missing and bootstrap is allowed, initialize the drive and create `.lightnode`.
5. If missing and bootstrap is not allowed, refuse to start.
6. Compare `format_version` against supported version.
7. Compare `instance_id` against the expected registered instance when configured.
8. Write a probe file and remove it to verify write access.
9. Open the SQLite database on the storage drive.
10. Expose storage readiness status in `/health`.

## 6. Configuration Values
Suggested environment variables:
- `STORAGE_MODE=external-drive`
- `STORAGE_ROOT_PATH=/srv/lightnode/storage`
- `FILES_DIR=/srv/lightnode/storage/files`
- `DB_PATH=/srv/lightnode/storage/lightnode.db`
- `REQUIRE_EXTERNAL_STORAGE=true`
- `ALLOW_STORAGE_BOOTSTRAP=false`
- `STORAGE_MIN_FREE_BYTES=5368709120`

## 7. Raspberry Pi Deployment Rules
- Mount the storage drive by UUID, not device name.
- Use a stable mount point such as `/srv/lightnode/storage`.
- Keep the SD card free of application data.
- Prefer USB 3 SSD storage over SD card storage.
- Add a systemd dependency so LightNode starts after the storage mount is available.
- Refuse write operations if the drive becomes unavailable at runtime.

## 8. SQLite Placement and Behavior
- Store `lightnode.db` on the external storage drive.
- Keep SQLite in WAL mode.
- Commit metadata only after file writes complete successfully.
- Backup the database regularly to a backup subdirectory on the same drive.
- Optionally mirror backups to a second location for disaster recovery.

## 9. File Write Flow
1. Accept upload as a stream.
2. Validate the request identity.
3. Write to a temporary file under the storage drive.
4. Flush and fsync the temp file.
5. Atomically rename it into final location.
6. Commit metadata to SQLite.
7. Write an audit log entry.

## 10. Migration Plan From Prototype Storage
If existing files or DB live inside the repository during development:
1. Create a migration script.
2. Copy files to the external storage drive.
3. Copy or move the SQLite DB to the external drive.
4. Verify file hashes and sizes.
5. Write `.lightnode` once validation succeeds.
6. Keep the old repo data read-only until migration is confirmed.
7. Remove any remaining repository-local runtime data after verification.

## 11. Failure Handling
- If the storage drive is missing, startup should fail or enter read-only mode depending on configuration.
- If the drive is read-only, block uploads and destructive operations.
- If free space is below the configured threshold, expose degraded health.
- If `.lightnode` does not match the expected instance, require manual intervention.
- If the SQLite DB cannot be opened, refuse service startup.

## 12. Health and Observability
Health checks should report:
- storage mounted or not
- storage writable or not
- database open or not
- free bytes remaining
- `.lightnode` presence and version

Operational logs should include:
- storage root path
- mount status
- database path
- any bootstrap or migration action taken

## 13. Security and Accountability
- Keep bearer authentication for API access.
- Preserve audit logs for every protected action.
- Include extension identity where available.
- Do not store raw secrets in `.lightnode`.
- If a marker signature is added later, verify it on startup.

## 14. Implementation Order
1. Add storage configuration loading.
2. Move SQLite DB path to external drive.
3. Add `.lightnode` marker file creation and verification.
4. Add startup storage validation and fail-fast behavior.
5. Update file upload/download paths to use the external storage root.
6. Add health reporting for storage and DB location.
7. Add migration script from repository-local runtime data.
8. Document Raspberry Pi deployment and mount requirements.

## 15. Exit Criteria
- LightNode starts only when the registered storage drive is present and writable.
- Both SQLite metadata and file payloads live on the external drive.
- `.lightnode` is created and validated during initialization.
- Uploads, downloads, and metadata operations continue to work after reboot.
- Storage health clearly reports mount and writable state.
- Migration from repository-local data to production storage is documented and tested.
