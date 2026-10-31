"""Freeze: the script builds a real-HTML static site whose
internal links all resolve, with the static-demo banner present
and forms disabled. No live server is involved."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def test_freeze_builds_resolvable_site(tmp_path, monkeypatch):
    repo_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo_root / "scripts"))
    import freeze

    out_dir = tmp_path / "freeze-site"
    monkeypatch.setattr(sys, "argv", ["freeze.py", "--out", str(out_dir)])
    assert freeze.main() == 0

    expected = {
        "index.html",
        "login.html",
        "attendance.html",
        "schedule.html",
        "mileage.html",
        "directory.html",
        "distance.html",
        "mileage.csv",
    }
    actual = {p.name for p in out_dir.iterdir() if p.is_file()}
    assert expected.issubset(actual)
    assert (out_dir / "static" / "style.css").exists()

    for page in expected - {"mileage.csv"}:
        html = (out_dir / page).read_text(encoding="utf-8")
        assert "Static demo freeze" in html
        assert 'onsubmit="return false;"' in html
        # No absolute internal links may survive (Pages subpath).
        assert not re.search(r'(?:href|action)="/', html), page
        for link in re.findall(r'href="([^"]+)"', html):
            if link.startswith("http") or link.startswith("#"):
                continue
            assert (out_dir / link).exists(), f"{page} links to missing {link}"


def test_freeze_home_shows_demo_data(tmp_path, monkeypatch):
    repo_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo_root / "scripts"))
    import freeze

    out_dir = tmp_path / "freeze-site"
    monkeypatch.setattr(sys, "argv", ["freeze.py", "--out", str(out_dir)])
    freeze.main()
    html = (out_dir / "index.html").read_text(encoding="utf-8")
    assert "System Administrator" in html
    assert "Attendance records" in html
