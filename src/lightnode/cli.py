from __future__ import annotations

from argparse import ArgumentParser, Namespace
from dataclasses import asdict
import json
import secrets
import sqlite3
import sys
from pathlib import Path
import uuid

from .auth import hash_password, hash_token, utc_now
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

    admin_parser = subparsers.add_parser("admin", help="Host-only user and token management")
    admin_subparsers = admin_parser.add_subparsers(dest="admin_command", required=True)

    user_parser = admin_subparsers.add_parser("user", help="Manage users")
    user_subparsers = user_parser.add_subparsers(dest="user_command", required=True)

    user_create = user_subparsers.add_parser("create", help="Create a user")
    add_storage_arguments(user_create)
    user_create.add_argument("--username", required=True)
    user_create.add_argument("--password", required=True)
    user_create.add_argument("--role", default="user")

    user_reset = user_subparsers.add_parser("reset-password", help="Reset a user password")
    add_storage_arguments(user_reset)
    user_reset.add_argument("--username", required=True)
    user_reset.add_argument("--password", required=True)

    user_activate = user_subparsers.add_parser("activate", help="Activate a user")
    add_storage_arguments(user_activate)
    user_activate.add_argument("--username", required=True)

    user_deactivate = user_subparsers.add_parser("deactivate", help="Deactivate a user")
    add_storage_arguments(user_deactivate)
    user_deactivate.add_argument("--username", required=True)

    token_parser = admin_subparsers.add_parser("token", help="Manage access tokens")
    token_subparsers = token_parser.add_subparsers(dest="token_command", required=True)

    token_create = token_subparsers.add_parser("create", help="Create access token")
    add_storage_arguments(token_create)
    token_create.add_argument("--username", required=True)
    token_create.add_argument("--extension-id", default=None)

    token_list = token_subparsers.add_parser("list", help="List tokens")
    add_storage_arguments(token_list)
    token_list.add_argument("--username", default=None)

    token_revoke = token_subparsers.add_parser("revoke", help="Revoke token")
    add_storage_arguments(token_revoke)
    token_revoke.add_argument("--token-id", required=True)

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


def _ensure_db_ready(settings: LightNodeSettings) -> sqlite3.Connection:
    storage = StorageService(settings)
    storage.inspect()
    return storage.connection()


def _print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "storage" and args.storage_command == "init" and not args.bootstrap:
            args.bootstrap = True

        settings = settings_from_args(args)

        if args.command == "storage" and args.storage_command == "init":
            storage = StorageService(settings)
            state = storage.initialize()
            print_state(state)
            return 0
        elif args.command == "storage" and args.storage_command == "status":
            storage = StorageService(settings)
            state = storage.inspect()
            print_state(state)
            return 0
        elif args.command == "admin":
            db = _ensure_db_ready(settings)
            now = utc_now()

            if args.admin_command == "user" and args.user_command == "create":
                user_id = str(uuid.uuid4())
                db.execute(
                    "INSERT INTO users (id, username, password_hash, role, is_active, created_at, updated_at, deleted_at) VALUES (?, ?, ?, ?, 1, ?, ?, NULL)",
                    (user_id, args.username, hash_password(args.password), args.role, now, now),
                )
                db.commit()
                _print_json({"status": "created", "id": user_id, "username": args.username, "role": args.role})
                return 0

            if args.admin_command == "user" and args.user_command == "reset-password":
                row = db.execute("SELECT id FROM users WHERE username = ?", (args.username,)).fetchone()
                if row is None:
                    raise StorageError("User not found")
                db.execute(
                    "UPDATE users SET password_hash = ?, updated_at = ? WHERE username = ?",
                    (hash_password(args.password), now, args.username),
                )
                db.commit()
                _print_json({"status": "updated", "username": args.username})
                return 0

            if args.admin_command == "user" and args.user_command in {"activate", "deactivate"}:
                active = 1 if args.user_command == "activate" else 0
                db.execute("UPDATE users SET is_active = ?, updated_at = ? WHERE username = ?", (active, now, args.username))
                if db.total_changes == 0:
                    raise StorageError("User not found")
                db.commit()
                _print_json({"status": "updated", "username": args.username, "is_active": bool(active)})
                return 0

            if args.admin_command == "token" and args.token_command == "create":
                user = db.execute("SELECT id FROM users WHERE username = ?", (args.username,)).fetchone()
                if user is None:
                    raise StorageError("User not found")
                raw = secrets.token_urlsafe(48)
                token_id = str(uuid.uuid4())
                db.execute(
                    "INSERT INTO auth_tokens (id, token_hash, user_id, extension_id, issued_at, expires_at, revoked_at) VALUES (?, ?, ?, ?, ?, NULL, NULL)",
                    (token_id, hash_token(raw), user["id"], args.extension_id, now),
                )
                db.commit()
                _print_json({"status": "created", "token_id": token_id, "token": raw, "username": args.username})
                return 0

            if args.admin_command == "token" and args.token_command == "list":
                if args.username:
                    rows = db.execute(
                        """
                        SELECT t.id, u.username, t.extension_id, t.issued_at, t.expires_at, t.revoked_at
                        FROM auth_tokens t
                        JOIN users u ON u.id = t.user_id
                        WHERE u.username = ?
                        ORDER BY t.issued_at DESC
                        """,
                        (args.username,),
                    ).fetchall()
                else:
                    rows = db.execute(
                        """
                        SELECT t.id, u.username, t.extension_id, t.issued_at, t.expires_at, t.revoked_at
                        FROM auth_tokens t
                        JOIN users u ON u.id = t.user_id
                        ORDER BY t.issued_at DESC
                        """
                    ).fetchall()
                _print_json({"tokens": [dict(row) for row in rows]})
                return 0

            if args.admin_command == "token" and args.token_command == "revoke":
                db.execute("UPDATE auth_tokens SET revoked_at = ? WHERE id = ?", (now, args.token_id))
                if db.total_changes == 0:
                    raise StorageError("Token not found")
                db.commit()
                _print_json({"status": "revoked", "token_id": args.token_id})
                return 0
        else:
            parser.error("Unsupported command")
            return 2
        return 2
    except StorageError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
