"""Theme: toggle present on every page, system preference honoured."""

from __future__ import annotations

from pathlib import Path

from conftest import login


def test_toggle_present_on_login_and_home(client):
    login_html = client.get("/login").get_data(as_text=True)
    assert 'id="theme-toggle"' in login_html
    assert "prefers-color-scheme" in login_html
    login(client)
    home_html = client.get("/").get_data(as_text=True)
    assert 'id="theme-toggle"' in home_html


def test_stylesheet_defines_both_themes():
    css = (
        Path(__file__).resolve().parent.parent / "workspace_monitor" / "static" / "style.css"
    ).read_text(encoding="utf-8")
    assert "prefers-color-scheme: dark" in css
    assert 'html[data-theme="dark"]' in css
    assert 'html[data-theme="light"]' in css
    # No hardcoded page background/text colours left outside variables.
    assert "background: #f0f0f0" not in css
    assert "color: #1f1f1f" not in css.replace("var(--text)", "")
