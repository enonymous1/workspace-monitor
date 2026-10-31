"""Pages freeze gallery builder: index.html must reference every
shot by a relative path and load no external resources (Pages
serves the gallery standalone, and external URLs would break
under the repo subpath)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from capture_freeze import SHOTS, build_index


def test_build_index_references_all_shots_relatively(tmp_path):
    shots = [
        {"file": filename, "title": title, "caption": caption}
        for _, filename, title, caption in SHOTS
    ]
    shots.insert(
        0,
        {"file": "login.png", "title": "Sign in", "caption": "The sign-in card."},
    )
    build_index(tmp_path, shots)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    for shot in shots:
        assert f'assets/{shot["file"]}' in html
        assert shot["title"] in html
    assert "http://" not in html.replace("https://github.com/enonymous1/workspace-monitor", "")
    assert "cdn." not in html
    assert "not the app" in html


def test_shots_cover_every_page():
    filenames = {filename for _, filename, _, _ in SHOTS}
    assert filenames == {
        "home-dashboard.png",
        "attendance-admin.png",
        "schedule-calendar.png",
        "mileage-view.png",
        "directory.png",
        "distance-route.png",
    }
