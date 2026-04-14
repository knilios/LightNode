from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import uuid


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_csv_list(value: str | None) -> list[str] | None:
    if value is None:
        return None
    items = [item.strip() for item in value.split(",")]
    filtered = [item for item in items if item]
    return filtered or None


def _default_storage_root() -> Path:
    if os.name == "nt":
        return Path(r"C:\lightnode\storage")
    return Path("/srv/lightnode/storage")


@dataclass(slots=True)
class LightNodeSettings:
    storage_root: Path
    minimum_free_bytes: int = 5 * 1024 * 1024 * 1024
    allow_storage_bootstrap: bool = False
    require_external_storage: bool = True
    storage_mode: str = "external-drive"
    marker_filename: str = ".lightnode"
    database_filename: str = "lightnode.db"
    files_directory: str = "files"
    backups_directory: str = "backups"
    lightnode_version: str = "0.1.0"
    supported_marker_format_version: int = 1
    instance_id: str | None = None
    cors_allow_origins: list[str] | None = None
    cors_allow_methods: list[str] | None = None
    cors_allow_headers: list[str] | None = None
    cors_expose_headers: list[str] | None = None
    cors_allow_credentials: bool = False
    cors_max_age: int = 600

    @classmethod
    def from_env(cls) -> "LightNodeSettings":
        storage_root = Path(os.getenv("LIGHTNODE_STORAGE_ROOT", str(_default_storage_root())))
        instance_id = os.getenv("LIGHTNODE_INSTANCE_ID")
        return cls(
            storage_root=storage_root,
            minimum_free_bytes=int(os.getenv("LIGHTNODE_MIN_FREE_BYTES", str(5 * 1024 * 1024 * 1024))),
            allow_storage_bootstrap=_parse_bool(os.getenv("LIGHTNODE_ALLOW_STORAGE_BOOTSTRAP"), False),
            require_external_storage=_parse_bool(os.getenv("LIGHTNODE_REQUIRE_EXTERNAL_STORAGE"), True),
            storage_mode=os.getenv("LIGHTNODE_STORAGE_MODE", "external-drive"),
            marker_filename=os.getenv("LIGHTNODE_MARKER_FILENAME", ".lightnode"),
            database_filename=os.getenv("LIGHTNODE_DATABASE_FILENAME", "lightnode.db"),
            files_directory=os.getenv("LIGHTNODE_FILES_DIRECTORY", "files"),
            backups_directory=os.getenv("LIGHTNODE_BACKUPS_DIRECTORY", "backups"),
            lightnode_version=os.getenv("LIGHTNODE_VERSION", "0.1.0"),
            supported_marker_format_version=int(os.getenv("LIGHTNODE_MARKER_FORMAT_VERSION", "1")),
            instance_id=instance_id or None,
            cors_allow_origins=_parse_csv_list(os.getenv("LIGHTNODE_CORS_ALLOW_ORIGINS")),
            cors_allow_methods=_parse_csv_list(os.getenv("LIGHTNODE_CORS_ALLOW_METHODS")),
            cors_allow_headers=_parse_csv_list(os.getenv("LIGHTNODE_CORS_ALLOW_HEADERS")),
            cors_expose_headers=_parse_csv_list(os.getenv("LIGHTNODE_CORS_EXPOSE_HEADERS")),
            cors_allow_credentials=_parse_bool(os.getenv("LIGHTNODE_CORS_ALLOW_CREDENTIALS"), False),
            cors_max_age=int(os.getenv("LIGHTNODE_CORS_MAX_AGE", "600")),
        )

    @property
    def marker_path(self) -> Path:
        return self.storage_root / self.marker_filename

    @property
    def database_path(self) -> Path:
        return self.storage_root / self.database_filename

    @property
    def files_path(self) -> Path:
        return self.storage_root / self.files_directory

    @property
    def backups_path(self) -> Path:
        return self.storage_root / self.backups_directory

    def resolved_instance_id(self) -> str:
        return self.instance_id or str(uuid.uuid4())
