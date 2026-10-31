# workspace-monitor

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
<!-- CI badge: add after the workflow has run green on main, e.g.
     [![CI](https://github.com/enonymous1/workspace-monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/enonymous1/workspace-monitor/actions/workflows/ci.yml) -->

## Description

workspace-monitor is a workspace dashboard for small teams:
attendance clock-in/out with geolocation, a schedule calendar,
a mileage log with bulk upload, an organization directory, and
a driving-distance calculator with a local route cache.

The backend is **FastAPI** with SQLite storage, JWT
authentication (with server-side logout revocation and
failed-login rate limiting), and role-based access
(Admin, Supervisor, Standard). The frontend is **Streamlit**: one home page plus
five tool pages. The two processes are launched together by
`run_app.py` for local use; see Deployment for running them
as separate services.

<!-- VISUAL 1 — home dashboard, admin view (see REVIEW.md §5).
     Capture: fresh demo run, logged in as admin@example.com. -->
![Home dashboard, logged in as Admin, showing user, attendance, and pending-mileage metrics](docs/assets/home-dashboard.png)

**What this is not.** This is a demo, not a live Google
Workspace or ADP integration. The model names mention Google
and ADP because the project was shaped around them, but
nothing here calls Google or ADP — all data comes from a
local SQLite database seeded with fictional `@example.com`
users, and the Virginia hub locations are sample coordinates
for the demo map. Do not point it at real employees without
reading Security model below and Deployment first.

### Features

- **Attendance** — clock in/out from browser geolocation,
  with a reverse-geocoded address preview, a map of clock-in
  points, and per-user hours. Admins and supervisors see
  everyone; standard users see only themselves.

  <!-- VISUAL 3 — attendance page, admin view. -->
  ![Attendance page as Admin, with the clock-in card and All Users filter](docs/assets/attendance-admin.png)

- **Schedule** — read-only week/month calendar
  (FullCalendar) with multi-user comparison for admins.
  The API supports `start`/`end` date filters. There is
  currently no way to create, edit, or delete events
  through the API or UI; events come from the seed data
  (or from direct database edits).

  <!-- VISUAL 4 — schedule week view. -->
  ![Schedule calendar in Week view, with demo shifts](docs/assets/schedule-calendar.png)

- **Mileage** — manual entry, CSV/Excel bulk upload
  (one request, one transaction via `POST /api/mileage/bulk`),
  CSV export, and a pending/verified status column. There is
  currently no approve/reject action in the API: entries
  start as `pending`, and the status column reflects the
  stored value only.

  <!-- VISUAL 5 — mileage bulk-upload flow (GIF). -->
  ![Mileage log view, with the demo entries table](docs/assets/mileage-view.png)

- **Directory** — searchable contacts with universal vs
  assigned visibility. Admins may create contacts for
  anyone and delete any contact; other users may only
  create contacts for themselves.

- **Distance calculator** — Nominatim geocoding + OSRM
  routing, with results cached in the backend database.
  These are public demo endpoints with a usage policy
  (roughly 1 request/second, identifying User-Agent) —
  suitable for the demo, not a production routing
  dependency.

  <!-- VISUAL 6 — distance route map. -->
  ![Distance calculator showing Stafford Courthouse to Culpeper Courthouse: 43.11 miles, 62.66 minutes](docs/assets/distance-route.png)

### Architecture

```mermaid
flowchart LR
    Browser --> Streamlit["Streamlit frontend\n(home + 5 pages)"]
    Streamlit -->|utils/api_client\n(JWT Bearer)| API["FastAPI backend\n(auth, routers, repositories)"]
    API --> SQLite[(SQLite\nsrc/api/monitor.db)]
    Streamlit -.->|distance page only| Nominatim["Nominatim\n(geocoding)"]
    Streamlit -.->|distance page only| OSRM["OSRM\n(routing)"]
    Seed["scripts/seed_demo.py"] --> SQLite
```

<!-- VISUAL 2 — exported SVG of the diagram above, for docs/. -->
![Architecture diagram: Streamlit frontend, FastAPI backend, SQLite, and external geocoding/routing services](docs/assets/architecture.svg)

## Prerequisites

- **Python 3.11 or 3.12** (3.13 is not yet tested in CI;
  see Local Development). Check with `python --version`.
- **Git** (to clone the repository).
- **A browser with location permission**, only if you want
  to try geolocation clock-in; everything else works
  without it.
- **No external accounts or API keys.** Geocoding/routing
  use the public Nominatim/OSRM demo endpoints; no key is
  needed, but their usage policy applies (see Features).
- **For deployment only:** a secret key for JWT signing
  (see Deployment — never use the demo default in
  production) and a reverse proxy if the API will be
  reachable beyond localhost.

Operating systems: developed on Windows and Linux; the
launcher (`run_app.py`) handles both `.venv/Scripts` and
`.venv/bin` layouts. macOS should work the same way but is
not CI-tested.

## Installation

```bash
git clone https://github.com/enonymous1/workspace-monitor.git
cd workspace-monitor

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# Runtime install:
pip install -e .
```

That installs the FastAPI backend, the Streamlit frontend,
and all runtime dependencies with pinned versions from
`pyproject.toml`. For development (tests, linting), install
the test extras instead:

```bash
pip install -e ".[test]"
pip install ruff==0.8.4
```

### First run

```bash
# Recommended: set a stable signing secret before first login.
# Without it, the backend generates an ephemeral secret on each
# start and existing tokens stop working on restart.
# Windows (PowerShell): $env:WORKSPACE_MONITOR_SECRET_KEY = "a-long-random-secret"
export WORKSPACE_MONITOR_SECRET_KEY="a-long-random-secret"

python run_app.py
```

Then open:

- Frontend: http://localhost:8501
- API docs (Swagger UI): http://localhost:8000/docs

On first start the backend creates an empty database. Seed
the demo dataset into it (15 fictional users, attendance,
schedule, mileage, and contacts) with:

```bash
python scripts/seed_demo.py
```

Auto-seed on startup is **off by default** (v2.1). It runs
only when `WORKSPACE_MONITOR_AUTO_SEED=1` is set — never
enable it on a production database.

### Demo credentials

All demo users share the demo password **`Demo1234!`**
(override before seeding with
`WORKSPACE_MONITOR_DEMO_PASSWORD`). Try:

| User | Role | What you will see |
| --- | --- | --- |
| `admin@example.com` | Admin | Everyone's data; contact management |
| `jane.doe@example.com` | Supervisor | Everyone's data, read-only for contacts |
| `user@example.com` | Standard | Only your own data |

**Do not seed demo data in production, and do not use the
demo password anywhere real.** Demo users, locations, and
credentials exist only so the dashboard can be run and
reviewed without real HR data.

## Local Development

### Running the pieces separately

```bash
# Backend only (from the repo root, venv active):
python -m uvicorn src.api.main:app --port 8000
# Frontend only (in a second terminal):
streamlit run src/frontend/app.py --server.port 8501
```

`run_app.py` is a convenience launcher for local use: it
starts both, waits for the backend's `/health` endpoint
instead of sleeping, and terminates both children on
Ctrl+C. It is not a production process manager.

### Tests and linting

```bash
ruff check src tests scripts run_app.py
python -m pytest -q
```

Tests use a throwaway database and a fixed test secret
(see `tests/conftest.py` — the env vars must be set before
`api.main` is imported, which conftest handles). The suite
covers auth (including forged-token rejection), role
visibility, mileage attribution, contact permissions,
clock-in/out rules, route-cache round-trips, seed
idempotence, and the frontend API client. There are
currently **no frontend (Streamlit page) tests**: pages are
scripts, not importable units, so testable logic belongs
in `utils/` and in the API, and pages should stay thin.

To add a feature, follow the existing shape:

- **New API endpoint:** add the Pydantic schema and route
  in `src/api/main.py` (see REVIEW.md for the planned
  router/repository split), add the role rule to the
  handler — never rely on the frontend to enforce it —
  and add a test in `tests/test_api.py` for each role.
- **New Streamlit page:** add it under
  `src/frontend/pages/`, use `utils.api_client` (never
  raw `requests` with a hand-built header) and
  `enforce_login()` at the top, and use `current_role()`
  from `utils.ui_helpers` for role gates — do not compare
  role strings by hand.
- **New demo data:** edit `DEMO_USERS` / `seed_demo_data`
  in `src/api/database.py`, keeping the seed deterministic
  (no `random`) and idempotent (no-op on a non-empty
  database).

### Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `WORKSPACE_MONITOR_SECRET_KEY` | Ephemeral per-process secret (with a warning) | JWT signing key |
| `WORKSPACE_MONITOR_DB` | `src/api/monitor.db` | SQLite path (gitignored) |
| `WORKSPACE_MONITOR_API_URL` | `http://127.0.0.1:8000/api` | Frontend's backend URL |
| `WORKSPACE_MONITOR_DEMO_PASSWORD` | `Demo1234!` | Demo seed password |
| `WORKSPACE_MONITOR_AUTO_SEED` | `0` (no auto-seed) | Set to `1` only for a demo run; never in production |
| `WORKSPACE_MONITOR_LOGIN_MAX_FAILURES` | `5` | Failed logins per IP before a 429 |
| `WORKSPACE_MONITOR_LOGIN_WINDOW_SECONDS` | `900` | Window for the failed-login count |
| `WORKSPACE_MONITOR_API_TIMEOUT` | `10` | Frontend API timeout, seconds |
| `WORKSPACE_MONITOR_API_PORT` / `WORKSPACE_MONITOR_FRONTEND_PORT` | `8000` / `8501` | `run_app.py` ports |

### Troubleshooting

| Symptom | Likely cause / fix |
| --- | --- |
| "Backend unreachable" on the home page | Backend not running, or on a different port. Start it with `python run_app.py` and check http://localhost:8000/health |
| Login fails with the demo password on a fresh install | The database was never seeded (auto-seed is off by default). Run `python scripts/seed_demo.py`, then try again |
| Login fails after a backend restart | No `WORKSPACE_MONITOR_SECRET_KEY` was set, so the secret changed. Set a stable secret and log in again |
| "Session expired" on a page | JWT expired (8 hours) or the user was suspended. Log in again |
| Port already in use | `run_app.py` skips the process on a busy port and prints a warning — stop the other process or set the port env vars |
| `ModuleNotFoundError: api` / `utils` | The venv is not active, or the install step was skipped. Activate `.venv` and `pip install -e .` |
| Mileage CSV upload fails | Check the header row: it must be `date, start_location, end_location, miles, purpose`. Dates must parse as dates; see the upload tab's format note |

## Deployment

This section describes the minimal production shape. The
demo defaults are **not** production defaults — read the
checklist before deploying anywhere beyond your own machine.

### Checklist (do all of these)

1. **Keep auto-seed off.** It defaults to off in v2.1;
   confirm `WORKSPACE_MONITOR_AUTO_SEED` is unset or `0`,
   and seed only deliberately with `scripts/seed_demo.py` —
   on a development machine, never on a production database.
   A fresh production database must never contain the
   demo users.
2. **Set a real secret.** Generate a long random
   `WORKSPACE_MONITOR_SECRET_KEY` (e.g.
   `python -c "import secrets; print(secrets.token_hex(32))"`)
   and store it in your environment/secret manager — never
   in git, never in a committed `.env` file. Rotate it
   knowing that rotation invalidates all existing tokens.
3. **Create real users with real passwords** (bcrypt
   hashes) and delete or suspend the demo accounts.
   There is currently no user-management endpoint or
   password-change/reset flow — create users directly in
   the database or add that endpoint first (see REVIEW.md).
4. **Put the API behind a reverse proxy** (nginx or
   Caddy) with TLS, and rate-limit `POST /api/login`
   there (e.g. nginx `limit_req_zone`). The API itself
   has no rate limiting yet.
5. **Run the processes as services, not with
   `run_app.py`.** Example shape: uvicorn (one or more
   workers) behind the proxy for the API, and Streamlit
   as a separate service. `run_app.py` is for local
   development only.
6. **Back up the SQLite file** (copy it with the app
   stopped, or use SQLite's backup API). SQLite is fine
   for a small single-server deployment; if you expect
   concurrent writers, multiple servers, or more than
   ~100k rows per table, move to PostgreSQL before
   launch — the repository split in REVIEW.md is the
   planned seam for that move, and it is not done yet.

### What is not yet production-ready

Be explicit with anyone deploying this: the in-app
login rate limit is per-process (it resets on restart
and does not span workers), there is no audit log for
admin actions, no password-reset flow, and no
geolocation-consent or data-retention policy. If real
employees' location data will flow through attendance
clock-ins, add consent, retention, and access policies
first — the demo has none because its data is fictional.

### API reference

Interactive docs are always available at `/docs`
(Swagger UI) and `/openapi.json` when the backend is
running. The surface, briefly:

| Method & path | Who can call it | Notes |
| --- | --- | --- |
| `GET /health` | Anyone | Liveness check, no auth |
| `POST /api/login` | Anyone | Email + password → JWT (8 h); rate-limited on failed attempts |
| `POST /api/logout` | Any logged-in user | Revokes the caller's JWT server-side |
| `GET /api/stats` | Any logged-in user | Dashboard counts (users, attendance, pending mileage) without row transfer |
| `GET /api/users` | Admin/Supervisor: all; Standard: self | `?email=`, `?limit=`, `?offset=` |
| `GET /api/activity` | Same visibility as users | Drive-activity-shaped rows (local data) |
| `GET /api/hr-status` | Same visibility as users | HR-shaped rows (local data) |
| `GET /api/attendance` | Privileged: all; Standard: self | Clock-in/out history |
| `POST /api/attendance/clock-in` | Any logged-in user | One open shift per user, enforced by a pre-check (a concurrent-request race is noted in REVIEW.md) |
| `POST /api/attendance/clock-out` | Any logged-in user | Closes the latest open shift |
| `GET /api/schedule` | Privileged: all/filterable; Standard: self | Read-only; `?user_emails=` (repeatable), `?start=`/`?end=` date filters |
| `GET /api/mileage` | Same visibility as users | `?user_email=` |
| `POST /api/mileage` | Any logged-in user | Standard users are recorded as themselves; `status` in the body is a 422 |
| `POST /api/mileage/bulk` | Any logged-in user | Up to 500 entries, one transaction, returns `inserted` count |
| `GET /api/contacts` | Privileged: all; Standard: universal + own | |
| `POST /api/contacts` | Admin: anyone; others: self only | |
| `DELETE /api/contacts/{id}` | Admin: any; others: own only | |
| `GET /api/route-cache` | Any logged-in user | Cached route lookup (addresses normalized to lowercase) |
| `POST /api/route-cache` | Any logged-in user | Store a calculated route |

## Security model

- Login requires email **and** a bcrypt-hashed password;
  the API returns a signed JWT (8-hour expiry).
- Every request re-checks the user in the database, so
  suspension or a role change takes effect immediately.
  Forged tokens (including v1's literal `email:role`
  string) are rejected.
- Roles are a single enum (`Admin`, `Supervisor`,
  `Standard`):

  <!-- VISUAL 7 — sign-in card + role sidebars. -->
  ![Workspace Sign In card, with the demo-credentials panel](docs/assets/login.png)

  | Action | Admin | Supervisor | Standard |
  | --- | --- | --- | --- |
  | Read all users / attendance / schedule / mileage / contacts | ✅ | ✅ | Own only |
  | File mileage for another user | ✅ | ✅ | Own only (forced) |
  | Create/delete contacts for another user | ✅ | Own only | Own only |
  | Clock in/out | ✅ | ✅ | ✅ |

- Tokens live in Streamlit session state only — closing
  the tab logs you out, and `POST /api/logout` revokes
  the token server-side, so it stops working immediately.
- Failed logins are rate-limited per IP in the API
  (5 failures in 15 minutes → 429); production
  deployments should also rate-limit at the proxy.
- Geolocation attendance data is sensitive by nature.
  See Deployment for the consent/retention warning.

## Project structure

```text
src/api/         FastAPI app (main.py), auth (auth.py), SQLite (database.py),
                 security (security.py: AuthContext), pagination, rate limiting
src/models/      Pydantic shapes for the local tables
src/utils/       Frontend config, shared API client, Streamlit helpers
src/frontend/    Streamlit home page + pages/ (attendance, schedule,
                 mileage, directory, distance_calculator)
scripts/         seed_demo.py — deterministic demo dataset
tests/           pytest suite (auth, API, seed, frontend client)
docs/assets/     Screenshots and diagrams used by this README
run_app.py       Local launcher: backend + frontend, waits for /health,
                 terminates both children on Ctrl+C
```

## Contributing

Issues and pull requests are welcome. Please:

1. Run `ruff check src tests scripts run_app.py` and
   `python -m pytest -q` before opening a PR.
2. Add a test for any new endpoint or authorization rule,
   covering each role — not just the happy path.
3. Keep page code thin: logic belongs in `utils/` or the
   API, not in Streamlit page scripts.
4. Do not commit `*.db` files, secrets, or demo
   credentials beyond the documented demo password.
   The `.gitignore` already excludes databases and
   caches; check `git status` before committing.

## License

MIT — see [LICENSE](LICENSE). See
[CHANGELOG.md](CHANGELOG.md) for what changed in v2.1.0
and what breaks from v2.0 (auto-seed is now opt-in;
pre-v2.1 tokens without a `jti` are rejected;
posting `status` on mileage is now a 422).
