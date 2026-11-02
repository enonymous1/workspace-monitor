"""Google Classroom read-only client (optional, token-based).

Classroom *does* have a public API, unlike Google Voice, so
this page can pull real data — but only with the business's
own Google credentials, which this app never stores in the
repo. The app takes a short-lived OAuth access token from
the environment (``WORKSPACE_MONITOR_CLASSROOM_TOKEN``) and
calls the Classroom REST API with it, read-only scopes only:
courses, coursework, and rosters. No grades are written, no
assignments are created, and no token is ever written to the
database or to disk by this app.

If the token is missing or expired, the page reports
"not connected" with setup steps instead of showing fake
courses. Getting a token is a Google Cloud Console step
(OAuth client, Classroom read-only scopes, consent) — see
the Classroom template and README. Token refresh is the
owner's responsibility until a full OAuth flow is added;
do not commit a token, and do not reuse a personal
account's token for a business's classes.
"""

from __future__ import annotations

import os

import requests

API_BASE = "https://classroom.googleapis.com/v1"
TIMEOUT = 10


class ClassroomNotConfigured(Exception):
    """No token is configured, so no Classroom data can be read."""


class ClassroomError(Exception):
    """The Classroom API returned an error (bad token, no access, etc.)."""


def get_token() -> str | None:
    return os.environ.get("WORKSPACE_MONITOR_CLASSROOM_TOKEN") or None


def fetch_courses(token: str) -> list[dict]:
    """List courses visible to the token holder, read-only."""
    response = requests.get(
        f"{API_BASE}/courses",
        params={"pageSize": 100},
        headers={"Authorization": f"Bearer {token}"},
        timeout=TIMEOUT,
    )
    if response.status_code == 401:
        raise ClassroomError("Token rejected (401). Re-authorize and set a fresh token.")
    if response.status_code == 403:
        raise ClassroomError("Token lacks Classroom access (403). Check scopes and class access.")
    response.raise_for_status()
    return response.json().get("courses", [])


def fetch_coursework(token: str, course_id: str) -> list[dict]:
    """List coursework for one course, read-only."""
    response = requests.get(
        f"{API_BASE}/courses/{course_id}/courseWork",
        params={"pageSize": 100},
        headers={"Authorization": f"Bearer {token}"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.json().get("courseWork", [])


def get_overview() -> tuple[list[dict], str | None]:
    """Return (courses-with-coursework, error-or-None).

    Each course dict gains a ``coursework`` list. On any
    failure the error string is returned and courses is [] —
    the page shows the error, never partial or invented data.
    """
    token = get_token()
    if not token:
        return [], "not_configured"
    try:
        courses = fetch_courses(token)
    except ClassroomError as exc:
        return [], str(exc)
    except requests.RequestException as exc:
        return [], f"Classroom request failed: {exc}"
    overview: list[dict] = []
    for course in courses:
        try:
            coursework = fetch_coursework(token, course["id"])
        except requests.RequestException:
            coursework = []
        overview.append({**course, "coursework": coursework})
    return overview, None
