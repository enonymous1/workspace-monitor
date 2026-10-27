# ss-workspaceMonitor

A workspace dashboard for viewing activity, HR data, and operational
tools: attendance clock-in/out with geolocation, a schedule calendar,
a mileage log with CSV/Excel upload, an organization directory, and
a driving-distance calculator with a local route cache.

Backend: **FastAPI** (SQLite, JWT auth, role-based access).
Frontend: **Streamlit** (one home page plus five tool pages).

> Demo, not a real integration. The model names mention Google
> Workspace and ADP because v1 was shaped around them, but nothing
> here calls Google or ADP — all data comes from a local SQLite
> database seeded with fictional `@example.com` users. The Virginia
> hub locations are sample coordinates for the demo map.

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[test]"

# Optional but recommended: a stable signing secret for logins.
# Without it, tokens stop working when the backend restarts.
export WORKSPACE_MONITOR_SECRET_KEY="a-long-random-secret"

python run_app.py
```

Then open:

- Frontend: http://localhost:8501
- API docs: http://localhost:8000/docs

The backend seeds the demo dataset into an empty database on first
start. To seed explicitly, or to re-seed after deleting the DB file:

```bash
python scripts/seed_demo.py
```

### Demo credentials

All 15 demo users share the demo password **`Demo1234!`**
(override before seeding with `WORKSPACE_MONITOR_DEMO_PASSWORD`).
Try `admin@example.com` for the admin view, `jane.doe@example.com`
for supervisor, and `user@example.com` for standard.

**Do not seed demo data in production, and do not use the demo
password anywhere real.** Demo users, demo locations, and demo
credentials exist only so the dashboard can be run and reviewed
without real HR data.

## What it does

- **Attendance** — clock in/out from browser geolocation (with a
  reverse-geocoded address preview), a map of clock-in points, and
  per-user hours. Admins/supervisors see everyone; standard users
  see only themselves.
- **Schedule** — week/month calendar (FullCalendar) with multi-user
  comparison for admins.
- **Mileage** — manual entry, CSV/Excel bulk upload, CSV export,
  and a pending/verified status column.
- **Directory** — searchable contacts with universal vs assigned
  visibility, plus admin-only create/delete.
- **Distance calculator** — Nominatim geocoding + OSRM routing
  (public demo endpoints, so don't hammer them), with results
  cached in the backend database.

## Security model (v2)

- Login requires email **and** a bcrypt-hashed password; the API
  returns a signed JWT (8-hour expiry, `WORKSPACE_MONITOR_SECRET_KEY`).
- Every request re-checks the user in the database, so suspension
  or a role change takes effect immediately. Forged tokens
  (including v1's literal `email:role` string) are rejected.
- Roles are a single enum (`Admin`, `Supervisor`, `Standard`).
  Admins manage contacts for anyone; other users only for
  themselves. Mileage posts are always attributed to the token
  holder for standard users — v1 trusted the email in the request
  body, which let any user file mileage for anyone.
- Tokens live in Streamlit session state only. v1 persisted them
  in browser `localStorage` and restored sessions from unverified
  localStorage JSON; that mechanism is removed.
- Geolocation attendance data is sensitive by nature. If you ever
  point this at real people, add consent, retention, and access
  policies before collecting anything — the demo has none, because
  its data is fictional.

## Project structure

```text
src/api/         FastAPI app (main.py), auth (auth.py), SQLite (database.py)
src/models/      Pydantic shapes for the local tables
src/utils/       Frontend config, shared API client, Streamlit helpers
src/frontend/    Streamlit home page + pages/ (attendance, schedule,
                 mileage, directory, distance_calculator)
scripts/         seed_demo.py — deterministic demo dataset
tests/           pytest suite (auth, API, seed, frontend client)
run_app.py       Launches backend + frontend, waits for /health,
                 terminates both children on Ctrl+C
```

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `WORKSPACE_MONITOR_SECRET_KEY` | ephemeral per-process secret | JWT signing key |
| `WORKSPACE_MONITOR_DB` | `src/api/monitor.db` | SQLite path (gitignored) |
| `WORKSPACE_MONITOR_API_URL` | `http://127.0.0.1:8000/api` | Frontend's backend URL |
| `WORKSPACE_MONITOR_DEMO_PASSWORD` | `Demo1234!` | Demo seed password |
| `WORKSPACE_MONITOR_AUTO_SEED` | `1` | Seed demo data on empty DB (`0` disables) |
| `WORKSPACE_MONITOR_API_PORT` / `WORKSPACE_MONITOR_FRONTEND_PORT` | `8000` / `8501` | `run_app.py` ports |

## Development

```bash
ruff check src tests scripts run_app.py
python -m pytest -q
```

See [CHANGELOG.md](CHANGELOG.md) for what changed in v2.0.0 and
what breaks from v1 (login now requires a password; v1 tokens no
longer work; the database file is no longer tracked in git).
