"""Version single-source check: pyproject.toml and the FastAPI app
must agree, so a bump in one place cannot silently drift from the
other (a v2.0 review finding: version lived in two places).
"""

import tomllib
from pathlib import Path

from api.main import app

ROOT = Path(__file__).resolve().parent.parent


def test_pyproject_and_app_versions_agree():
    with open(ROOT / "pyproject.toml", "rb") as handle:
        pyproject = tomllib.load(handle)
    assert pyproject["project"]["version"] == app.version
