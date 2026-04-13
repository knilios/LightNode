from __future__ import annotations

from argparse import ArgumentParser, Namespace
from dataclasses import asdict
import json
import sys
from pathlib import Path

from .config import LightNodeSettings
from .storage import StorageError, StorageService


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(prog="lightnode", description="LightNode terminal tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    storage_parser = subparsers.add_parser("storage", help="Storage lifecycle commands")
    storage_subparsers = storage_parser.add_subparsers(dest="storage_command", required=True)

    init_parser = storage_subparsers.add_parser("init", help="Prepare an empty storage drive")
    add_storage_arguments(init_parser)

    status_parser = storage_subparsers.add_parser("status", help="Inspect a prepared storage drive")
    add_storage_arguments(status_parser)

    return parser


def add_storage_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("--root", required=True, type=Path, help="Storage root path")
    parser.add_argument("--instance-id", default=None, help="Expected storage instance id")
    parser.add_argument("--min-free-bytes", type=int, default=5 * 1024 * 1024 * 1024, help="Minimum free bytes before degraded status")
    parser.add_argument("--storage-mode", default="external-drive", help="Expected storage mode")
    parser.add_argument("--lightnode-version", default="0.1.0", help="LightNode version to record in the marker")
    parser.add_argument("--marker-format-version", type=int, default=1, help="Supported marker format version")
    parser.add_argument("--bootstrap", action="store_true", help="Allow initializing an empty drive")


def settings_from_args(args: Namespace) -> LightNodeSettings:
    return LightNodeSettings(
        storage_root=args.root,
        minimum_free_bytes=args.min_free_bytes,
        allow_storage_bootstrap=args.bootstrap,
        require_external_storage=True,
        storage_mode=args.storage_mode,
        lightnode_version=args.lightnode_version,
        supported_marker_format_version=args.marker_format_version,
        instance_id=args.instance_id,
    )


def print_state(state) -> None:
    print(json.dumps(asdict(state), indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "storage" and args.storage_command == "init" and not args.bootstrap:
            args.bootstrap = True

        settings = settings_from_args(args)
        storage = StorageService(settings)

        if args.command == "storage" and args.storage_command == "init":
            state = storage.initialize()
        elif args.command == "storage" and args.storage_command == "status":
            state = storage.inspect()
        else:
            parser.error("Unsupported command")
            return 2

        print_state(state)
        return 0
    except StorageError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
