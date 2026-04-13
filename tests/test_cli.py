from __future__ import annotations

import json
from pathlib import Path

from lightnode.cli import main


def test_storage_init_and_status(tmp_path: Path, capsys) -> None:
    exit_code = main(["storage", "init", "--root", str(tmp_path), "--instance-id", "instance-1"])
    assert exit_code == 0

    init_output = capsys.readouterr().out
    assert "storage_root" in init_output
    assert (tmp_path / "lightnode.db").exists()

    exit_code = main(["storage", "status", "--root", str(tmp_path), "--instance-id", "instance-1"])
    assert exit_code == 0

    status_output = capsys.readouterr().out
    assert "marker_valid" in status_output
