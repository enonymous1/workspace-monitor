"""Build a static Pages freeze of workspace-monitor (Flask build).

Unlike the v2 screenshot gallery, this freeze is real HTML:
the Flask test client logs in as the demo admin, requests each
page, and writes the rendered templates to ``freeze-site/``.
Visitors can click through home, attendance, schedule,
mileage, directory, distance, collateral, HR, Voice,
Classroom, and Users pages and read the demo
data — navigation, tables, and the Leaflet maps work in the
browser (map tiles and Leaflet come from their CDNs).

What still does not work, because Pages has no server:
login/logout, clock-in/out, mileage add/upload, contact
add/delete, and distance calculation. Forms in the frozen
copy are disabled and a banner says so; nothing is faked
as interactive. The frozen database is a throwaway temp
file seeded with the fictional demo dataset, never the
user's real database.

Usage, from the repo root:

    python scripts/freeze.py --out freeze-site

Local preview: serve the output directory (do not just open
the file, so relative links resolve the same way Pages does):

    python -m http.server --directory freeze-site 8000

In CI, ``.github/workflows/pages-freeze.yml`` runs this
script and deploys ``freeze-site`` to GitHub Pages.
"""

from __future__ import annotations

import argparse
import re
import shutil
import tempfile
from pathlib import Path

# (route, output file)
PAGES = [
    ("/login", "login.html"),
    ("/", "index.html"),
    ("/attendance", "attendance.html"),
    ("/schedule", "schedule.html"),
    ("/mileage", "mileage.html"),
    ("/directory", "directory.html"),
    ("/distance", "distance.html"),
    ("/collateral", "collateral.html"),
    ("/hr", "hr.html"),
    ("/voice", "voice.html"),
    ("/classroom", "classroom.html"),
    ("/users", "users.html"),
]

HREF_MAP = {
    "/": "index.html",
    "/login": "login.html",
    "/logout": "login.html",
    "/attendance": "attendance.html",
    "/schedule": "schedule.html",
    "/mileage": "mileage.html",
    "/directory": "directory.html",
    "/distance": "distance.html",
    "/collateral": "collateral.html",
    "/hr": "hr.html",
    "/voice": "voice.html",
    "/classroom": "classroom.html",
    "/users": "users.html",
    "/mileage/export": "mileage.csv",
}

BANNER = (
    '<div style="background:#fff8e1;border:1px solid #f0d060;border-radius:8px;padding:1rem;margin:1rem 0;">'
    "<strong>Static demo freeze — not the live app.</strong> "
    "These pages were rendered from the fictional demo dataset. "
    "Navigation and reading work; login, clock-in/out, mileage "
    "add/upload, contact changes, and distance calculation do "
    "not submit here. Run the app locally with "
    "<code>python run_app.py</code> for the real thing.</div>"
)


def rewrite_html(html: str) -> str:
    """Rewrite absolute Flask URLs to flat relative freeze URLs,
    disable forms, and inject the static-demo banner."""
    # Forms cannot submit on Pages: disable them, banner explains why.
    html = html.replace("<form", '<form onsubmit="return false;"')
    # Query-string links (schedule week nav, mileage filter) point
    # at the frozen page for that view; only the default view is frozen.
    html = re.sub(
        r'href="(/schedule|/mileage|/directory|/attendance)(\?[^"]*)?"', r'href="\1"', html
    )
    html = re.sub(
        r'action="(/schedule|/mileage|/directory|/attendance)(\?[^"]*)?"', r'action="\1"', html
    )
    for route, target in HREF_MAP.items():
        html = html.replace(f'href="{route}"', f'href="{target}"')
        html = html.replace(f'action="{route}"', f'action="{target}"')
    html = html.replace('href="/static/', 'href="static/')
    # Any remaining internal URL is a POST-only route (clock-in,
    # clock-out, contact delete, etc.): forms are disabled in the
    # freeze, so point them at "#" rather than a dead Pages path.
    html = re.sub(r'href="/[^"]*"', 'href="#"', html)
    html = re.sub(r'action="/[^"]*"', 'action="#"', html)
    html = re.sub(r"<body([^>]*)>", r"<body\1>" + BANNER, html, count=1)
    leftover = re.findall(r'(?:href|action)="/(?!static)', html)
    if leftover:
        raise RuntimeError(f"Unrewritten internal links remain: {leftover}")
    return html


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the workspace-monitor static freeze.")
    parser.add_argument("--out", default="freeze-site", help="Output directory for the static site")
    args = parser.parse_args()

    from workspace_monitor import create_app
    from workspace_monitor.config import Settings

    out_dir = Path(args.out)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    with tempfile.TemporaryDirectory(prefix="workspace-monitor-freeze-") as tmp:
        db_path = Path(tmp) / "freeze.db"
        settings = Settings(
            secret_key="freeze-secret-not-a-real-secret",
            db_path=db_path,
            auto_seed=True,
            login_max_failures=1000,
            login_window_seconds=900,
            api_timeout_seconds=10,
            port=5000,
        )
        app = create_app(settings)
        client = app.test_client()

        login_page = client.get("/login")
        assert login_page.status_code == 200
        # Freeze the login page now: after logging in, GET /login
        # redirects to home (by design), so it cannot be frozen later.
        (out_dir / "login.html").write_text(
            rewrite_html(login_page.get_data(as_text=True)), encoding="utf-8"
        )
        print("froze /login -> login.html (pre-login)")
        match = re.search(r'name="csrf_token" value="([^"]+)"', login_page.get_data(as_text=True))
        assert match, "CSRF token not found on login page"
        login_response = client.post(
            "/login",
            data={
                "email": "admin@example.com",
                "password": "Demo1234!",
                "csrf_token": match.group(1),
            },
            follow_redirects=True,
        )
        assert (
            login_response.status_code == 200
        ), f"Freeze login failed: {login_response.status_code}"
        assert "Welcome" in login_response.get_data(
            as_text=True
        ), "Freeze login did not reach the dashboard"

        for route, filename in PAGES:
            if route == "/login":
                continue  # already frozen pre-login above
            response = client.get(route)
            assert response.status_code == 200, f"{route} returned {response.status_code}"
            (out_dir / filename).write_text(
                rewrite_html(response.get_data(as_text=True)), encoding="utf-8"
            )
            print(f"froze {route} -> {filename}")

        export = client.get("/mileage/export")
        assert export.status_code == 200
        (out_dir / "mileage.csv").write_bytes(export.data)
        print("froze /mileage/export -> mileage.csv")

    static_src = Path(__file__).resolve().parent.parent / "workspace_monitor" / "static"
    shutil.copytree(static_src, out_dir / "static")
    print(f"wrote {out_dir / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
