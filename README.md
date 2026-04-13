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

## Notes

- The storage root must contain a `.lightnode` marker file after initialization.
- SQLite metadata and file payloads live on the same storage drive.
- The terminal commands work on both Windows and Linux; the default storage root is OS-aware, but you can always pass `--root` explicitly.
