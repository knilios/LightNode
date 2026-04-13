from __future__ import annotations

import json
from pathlib import Path

from lightnode.cli import main


def test_admin_user_and_token_commands(tmp_path: Path, capsys) -> None:
    assert main(["storage", "init", "--root", str(tmp_path), "--instance-id", "instance-1"]) == 0
    capsys.readouterr()

    assert main(
        [
            "admin",
            "user",
            "create",
            "--root",
            str(tmp_path),
            "--instance-id",
            "instance-1",
            "--username",
            "bob",
            "--password",
            "pass1234",
            "--role",
            "admin",
        ]
    ) == 0
    user_out = json.loads(capsys.readouterr().out)
    assert user_out["status"] == "created"

    assert main(
        [
            "admin",
            "token",
            "create",
            "--root",
            str(tmp_path),
            "--instance-id",
            "instance-1",
            "--username",
            "bob",
        ]
    ) == 0
    token_out = json.loads(capsys.readouterr().out)
    assert token_out["status"] == "created"
    token_id = token_out["token_id"]

    assert main(
        [
            "admin",
            "token",
            "revoke",
            "--root",
            str(tmp_path),
            "--instance-id",
            "instance-1",
            "--token-id",
            token_id,
        ]
    ) == 0
    revoke_out = json.loads(capsys.readouterr().out)
    assert revoke_out["status"] == "revoked"
