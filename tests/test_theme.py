"""Theme: toggle present on every page, system preference honoured.

Since v3.2.0 the theme is AdminLTE 4 / Bootstrap 5.3's data-bs-theme
on <html>, set before the stylesheets load from localStorage key
wm-theme (unchanged from v3.0.1) or prefers-color-scheme. The shell
CSS/JS are vendored under static/vendor/, never a CDN.
"""

from __future__ import annotations

from pathlib import Path

from conftest import login


def test_toggle_present_on_login_and_home(client):
    login_html = client.get("/login").get_data(as_text=True)
    assert 'id="theme-toggle"' in login_html
    assert "prefers-color-scheme" in login_html
    assert "data-bs-theme" in login_html
    assert "wm-theme" in login_html
    login(client)
    home_html = client.get("/").get_data(as_text=True)
    assert 'id="theme-toggle"' in home_html
    assert "app-sidebar" in home_html
    assert "app-header" in home_html


def test_adminlte_assets_vendored():
    static = Path(__file__).resolve().parent.parent / "workspace_monitor" / "static"
    adminlte = (static / "vendor" / "adminlte.min.css").read_text(encoding="utf-8")
    assert "AdminLTE v4.10.0" in adminlte
    assert (static / "vendor" / "adminlte.min.js").exists()
    assert (static / "vendor" / "bootstrap.min.css").exists()
    assert (static / "vendor" / "bootstrap.bundle.min.js").exists()
    assert (static / "vendor" / "bootstrap-icons.min.css").exists()
    assert (static / "vendor" / "fonts" / "bootstrap-icons.woff2").exists()
    base = (
        Path(__file__).resolve().parent.parent / "workspace_monitor" / "templates" / "base.html"
    ).read_text(encoding="utf-8")
    assert "vendor/adminlte.min.css" in base
    assert "vendor/bootstrap.bundle.min.js" in base
    # No CDN shell assets: the AdminLTE shell must work offline and
    # in the Pages freeze. (Leaflet maps on Attendance/Distance
    # still use their CDN, as before, and are not part of the shell.)
    assert "cdn.jsdelivr.net/npm/admin-lte" not in base
    assert "cdn.jsdelivr.net/npm/bootstrap" not in base
