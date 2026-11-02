"""Version agreement: pyproject and the package must match."""

from __future__ import annotations

import re
from pathlib import Path

import workspace_monitor


def test_version_matches_pyproject():
    pyproject = (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    match = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE)
    assert match
    assert workspace_monitor.__version__ == match.group(1) == "3.2.0"
