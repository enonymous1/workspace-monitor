"""Capture a static Pages freeze of workspace-monitor.

This script runs a real Streamlit frontend against a real backend
seeded with the demo dataset, logs in as the demo admin, and
screenshots each page. It then builds a static gallery
(``index.html`` + ``assets/*.png``) that GitHub Pages can serve.

What this is, and is not: the gallery is a *viewing* freeze,
not the interactive app. Pages serves static files only, so no
login, clock-in, or calculation works from the gallery — run
``python run_app.py`` locally for the real app. Nothing here is
mocked up: if a page fails to load, the script raises instead
of writing a screenshot of an error page (except the distance
page, whose route depends on the public Nominatim/OSRM demo
endpoints — it is captured as-is and the caption says so).

Two Streamlit quirks this script works around, both found while
capturing the README screenshots headlessly:

* A password filled with Playwright's ``fill()`` is not
  committed to Streamlit's widget state until the field loses
  focus, so the script presses Tab after filling it. Without
  that, login posts an empty password and fails with 401.
* A direct URL goto to a multipage route creates a new
  Streamlit session and loses the login, so navigation uses
  the sidebar links, which preserve the session.

Usage (servers already running, backend seeded):

    python scripts/capture_freeze.py --out freeze-site

Local preview: open ``freeze-site/index.html`` in a browser.
In CI, ``.github/workflows/pages-freeze.yml`` starts both
servers, runs this script, and deploys ``freeze-site``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

# (sidebar link text, filename, title, caption) — post-login pages only.
# The sign-in shot is taken before login, in main().
SHOTS = [
    (
        "app",
        "home-dashboard.png",
        "Home dashboard (Admin)",
        "Counts from the demo seed: 15 users, 75 attendance records.",
    ),
    (
        "attendance",
        "attendance-admin.png",
        "Attendance",
        "Clock-in card and the All Users filter, as Admin "
        "(cropped above the map section, whose tiles fail in headless capture).",
    ),
    (
        "schedule",
        "schedule-calendar.png",
        "Schedule",
        "Week view of the demo calendar, as Admin.",
    ),
    (
        "mileage",
        "mileage-view.png",
        "Mileage log",
        "Demo mileage entries, with pending/verified status.",
    ),
    (
        "directory",
        "directory.png",
        "Directory",
        "Searchable contacts, as Admin.",
    ),
    (
        "distance calculator",
        "distance-route.png",
        "Distance calculator",
        "Stafford Courthouse to Culpeper Courthouse via Nominatim/OSRM; "
        "cropped above the map section, whose tiles fail in headless capture.",
    ),
]


# Map sections fail in headless capture (Streamlit Mapbox token
# fetch errors in this environment, not in a real browser), so
# these two shots are cropped above the map. Cropping frames the
# shot; it does not alter the captured content.
CROP_HEIGHTS = {
    "attendance-admin.png": 600,
    "distance-route.png": 460,
}


def crop_image(path: Path, height: int) -> None:
    try:
        from PIL import Image
    except ImportError:
        print(f"warning: Pillow not available, leaving {path.name} uncropped")
        return
    with Image.open(path) as image:
        if image.height > height:
            image.crop((0, 0, image.width, height)).save(path)


def build_index(out_dir: Path, shots: list[dict]) -> None:
    figures = "\n".join(
        f'    <figure>\n      <h2>{s["title"]}</h2>\n'
        f'      <img src="assets/{s["file"]}" alt="{s["title"]}">\n'
        f'      <figcaption>{s["caption"]}</figcaption>\n    </figure>'
        for s in shots
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>workspace-monitor — screenshot freeze</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 1100px; padding: 0 1rem; color: #1f1f1f; }}
  img {{ max-width: 100%; border: 1px solid #ddd; border-radius: 8px; }}
  figure {{ margin: 2rem 0; }}
  figcaption {{ color: #555; margin-top: 0.5rem; }}
  .note {{ background: #fff8e1; border: 1px solid #f0d060; border-radius: 8px; padding: 1rem; }}
</style>
</head>
<body>
<h1>workspace-monitor — screenshot freeze</h1>
<div class="note">
<p><strong>This is a static gallery, not the app.</strong> These screenshots were
captured by CI from a real run of the app against the fictional demo seed
(<code>@example.com</code> users, no real employees). Nothing here is clickable or
logged in. To run the real app locally, see the
<a href="https://github.com/enonymous1/workspace-monitor">README</a> and run
<code>python run_app.py</code>.</p>
</div>
{figures}
</body>
</html>
"""
    (out_dir / "index.html").write_text(html, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture the workspace-monitor Pages freeze.")
    parser.add_argument("--base", default="http://127.0.0.1:8501", help="Streamlit frontend URL")
    parser.add_argument("--out", default="freeze-site", help="Output directory for the static site")
    parser.add_argument("--email", default="admin@example.com", help="Demo login email")
    parser.add_argument("--password", default="Demo1234!", help="Demo login password")
    parser.add_argument(
        "--chromium-executable",
        default=None,
        help="Chromium binary to use instead of Playwright's bundled one "
        "(local runs only; CI uses `playwright install chromium`)",
    )
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright

    out_dir = Path(args.out)
    assets_dir = out_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    captured: list[dict] = [
        {
            "file": "login.png",
            "title": "Sign in",
            "caption": "The sign-in card, with the demo-credentials panel.",
        }
    ]

    with sync_playwright() as pw:
        launch_kwargs: dict = {"headless": True, "args": ["--no-proxy-server"]}
        if args.chromium_executable:
            launch_kwargs["executable_path"] = args.chromium_executable
        browser = pw.chromium.launch(**launch_kwargs)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(args.base, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)
        page.screenshot(path=str(assets_dir / "login.png"), full_page=True)
        print("captured login.png")

        # Log in. Tab after filling the password commits it to
        # Streamlit's widget state (see module docstring).
        page.locator("input").first.fill(args.email)
        password_input = page.locator("input[type='password']").first
        password_input.fill(args.password)
        password_input.press("Tab")
        page.wait_for_timeout(2000)
        page.locator("button").filter(has_text="Sign In").first.click()
        page.wait_for_timeout(8000)
        if "Welcome" not in page.locator("body").inner_text():
            raise RuntimeError("Login failed: dashboard greeting not found after sign-in")

        for link_text, filename, title, caption in SHOTS:
            page.locator("a").filter(has_text=link_text).first.click()
            page.wait_for_timeout(6000)
            if "Workspace Sign In" in page.locator("body").inner_text():
                raise RuntimeError(f"Lost login while navigating to {link_text!r}")
            if link_text == "distance calculator":
                page.locator("button").filter(has_text="Calculate Driving Distance").first.click()
                page.wait_for_timeout(25000)
            page.screenshot(path=str(assets_dir / filename), full_page=True)
            if filename in CROP_HEIGHTS:
                crop_image(assets_dir / filename, CROP_HEIGHTS[filename])
            captured.append({"file": filename, "title": title, "caption": caption})
            print(f"captured {filename}")
        browser.close()

    build_index(out_dir, captured)
    print(f"wrote {out_dir / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
