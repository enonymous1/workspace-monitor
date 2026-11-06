# Changelog

## 3.2.1 — 2026-11-06

### Fixed

- **Freeze banner in dark mode:** the "Static demo freeze"
  banner was a hardcoded pale-yellow box (`#fff8e1`), which
  was unreadable in dark mode — light text on a pale
  background. It is now Bootstrap's `alert-warning`, whose
  colours follow `data-bs-theme`, so it reads in light and
  dark alike.
- **Stacked cards touched:** AdminLTE sets
  `.card { margin-bottom: 0 }`, so the vertical card stacks
  on every sub-page had no gap between them. `style.css`
  (loaded after `adminlte.min.css`) now restores
  `.card { margin-bottom: 1rem }`.

## 3.2.0 — 2026-11-02

### Changed

- **AdminLTE 4 shell:** the whole app now renders in an
  AdminLTE 4.10.0 shell on Bootstrap 5.3.8 (vanilla JS, no
  jQuery, MIT) with a collapsible sidebar grouped as Main /
  People / Operations, role-gated exactly as before (Users
  Admin-only, Classroom Admin/Supervisor). Every page's
  sections are AdminLTE cards via a reusable Jinja macro
  (`templates/components/cards.html`: `card()` and
  `widget_card()`), and Home's three counts are AdminLTE
  small-box widgets. All tables use Bootstrap table styling
  and all forms use Bootstrap controls; routes, session
  auth, CSRF, SQLite schema, and demo data are unchanged.
- **Theme via `data-bs-theme`:** the light/dark toggle now
  flips Bootstrap/AdminLTE's `data-bs-theme` instead of a
  custom `data-theme`. Behaviour is unchanged: system
  preference by default, saved choice wins, no flash before
  load, and the saved `wm-theme` localStorage key carries
  over from v3.0.1/v3.1.0.
- **Vendor, don't CDN, the shell:** AdminLTE, Bootstrap,
  and Bootstrap Icons are vendored under
  `static/vendor/` (with a `THIRD_PARTY_NOTICES.md`
  recording their MIT licences), so the app and the Pages
  freeze work offline. Leaflet maps on Attendance/Distance
  still use their CDN, as before.
- **Screenshots:** all README screenshots re-captured
  from the real Flask app on the demo dataset, showing the
  AdminLTE shell.

### Still open (unchanged)

- Schedule write endpoints, mileage approval workflow,
  audit log, self-service password reset (admin reset
  above is not self-service), Alembic migrations.

## 3.1.0 — 2026-11-02

### Added

- **Users (Admin only):** `/users` — list internal login
  accounts, create users (bcrypt, min 8 characters), update
  role/department/title, suspend/reactivate, and
  admin-initiated password reset. No delete (suspend
  instead, so history stays intact); admins cannot suspend
  themselves and the last Admin cannot be demoted.
  External people stay in Directory, not here.
- **Collateral:** `/collateral` — CRUD for pamphlets,
  business cards, and flyers (quantity, reorder level,
  unit cost, vendor, status), a below-reorder-level list,
  and a mail-out log that reduces stock by recipients
  sent. Items with mail-out history cannot be deleted.
- **HR & hiring:** `/hr` — employee roster (pay-cycle
  hours Admin-only; Supervisors see the roster without
  pay data; Standard users see only their own row),
  job-description CRUD, and links to the Indeed
  Employer Dashboard and Indeed's post-a-job page.
  No Indeed sync (partner approval required) and no
  scraping — application counts are manual.
- **Voice (manual only):** `/voice` — staff-entered
  call/voicemail log with an open follow-up count and a
  link to Google Voice. No live sync: Google Voice has
  no public API, and the page says so.
- **Classroom (read-only, Admin/Supervisor only):**
  `/classroom` — with
  `WORKSPACE_MONITOR_CLASSROOM_TOKEN` set, lists courses
  and coursework live from the Classroom API (read-only
  scopes, nothing stored in this app's database);
  without a token it shows setup steps, never fake
  courses. Live Google verification is still the owner's
  gate (their Cloud project and token).
- Pages freeze now covers all 12 frozen files (11 content
  pages + login), including the five new ones; demo seed
  includes collateral, job postings, and voice logs.

### Still open (unchanged)

- Schedule write endpoints, mileage approval workflow,
  audit log, self-service password reset (admin reset
  above is not self-service), Alembic migrations.

## 3.0.1 — 2026-10-31

### Added

- Light/dark theme: pages follow the device's
  `prefers-color-scheme` by default, and a Dark/Light button in
  the header toggles it. The toggle saves to `localStorage`
  (`wm-theme`); a saved choice always beats the system
  preference, and with no saved choice the page keeps
  following system changes. The theme is set before the
  stylesheet loads, so there is no light flash on a
  dark-preferring device. It works on the login page and on
  the static Pages freeze too. All colours are CSS variables;
  Leaflet map tiles stay light (they come from OpenStreetMap).

## 3.0.0 — 2026-10-31

### Changed — BREAKING: Flask rebuild, supersedes the FastAPI + Streamlit build

- **Stack:** Flask + Jinja2, app factory, one process
  (`workspace_monitor` top-level package, no `sys.path` hacks),
  replacing FastAPI + Streamlit (two processes). The database
  schema, demo seed (15 users, 75 attendance rows), role
  rules, and feature set are carried over unchanged; only the
  web layer changed. FastAPI endpoints (`/api/*`, `/docs`) and
  Streamlit pages are removed.
- **Auth:** server-side Flask sessions (signed cookie holding
  only the email, re-checked against the database on every
  request) + per-session CSRF tokens on all POST forms,
  replacing JWTs. Logout clears the session; no token
  revocation table is needed. Failed-login rate limiting
  (5 per IP per 15 minutes) and suspended-user blocking are
  kept.
- **Pages freeze:** `scripts/freeze.py` replaces the v2
  screenshot gallery. The Flask test client renders real HTML
  for login, home, attendance, schedule, mileage, directory,
  and distance (plus `mileage.csv`) from a throwaway demo
  database — no browser, no running server. Navigation and
  reading work on Pages; forms are disabled and a banner says
  so. The workflow no longer installs Playwright/Chromium.
- **Schedule:** server-rendered week view instead of a
  JavaScript calendar widget, which is what makes the freeze
  work (the table is in the HTML).
- **Mileage bulk upload:** still one transaction, now via
  CSV/Excel parsing in the Flask route (no pandas, no per-row
  HTTP requests).
- **Screenshots:** all README screenshots re-captured from
  the real Flask app on the demo dataset, including a new
  directory shot; distance shot is a real Nominatim/OSRM
  route (43.11 miles, 62.66 minutes).
- **Tests:** 21 tests via the Flask test client (throwaway
  app + database per test), covering the same ground as v2
  plus CSRF and the freeze build. The stale-cache bug that
  cleared the session on every login, and the empty-token
  CSRF bypass (empty form token matching an empty session
  token), were both found by these tests and fixed.
- **Dependencies:** Flask, bcrypt, openpyxl, polyline,
  requests, email-validator only. FastAPI, uvicorn, PyJWT,
  Streamlit, streamlit-calendar, streamlit-js-eval, and pandas
  are gone.

### Still open (unchanged from v2)

- Schedule write endpoints, mileage approval workflow, audit
  log, password reset, Alembic migrations, single settings
  object for the database path (currently env-driven at
  import for the database module, config-driven in the app).

## 2.2.1 — 2026-10-31

### Fixed

- README Architecture diagram did not render on GitHub: the
  Mermaid labels contained literal `\n` sequences, which
  GitHub's Mermaid parser rejects (parse error at the
  `API["FastAPI backend..."]` node). All labels are now
  single-line, with no `\n` in the diagram. No code changed.


## 2.2.0 — 2026-10-31

### Added

- Pages screenshot freeze: `scripts/capture_freeze.py` runs the
  real app against the demo seed, screenshots sign-in, home,
  attendance, schedule, mileage, directory, and distance pages,
  and builds a static gallery (`freeze-site/index.html`).
  `.github/workflows/pages-freeze.yml` runs it on every push to
  `main` and deploys to GitHub Pages. The gallery is viewing
  only — it is not the interactive app. One-time setup: repo
  Settings → Pages → Source: GitHub Actions; published URL is
  https://enonymous1.github.io/workspace-monitor/
- `freeze-site/` is gitignored (generated by CI, never committed).

### Notes

- Freeze screenshots are cropped above the map sections on the
  attendance and distance pages: Streamlit's Mapbox tiles fail
  in headless capture, and the captions say so. The route
  result itself (e.g. 43.11 miles Stafford → Culpeper) is real
  Nominatim/OSRM output, not mocked.
- CI for the freeze needs Playwright + Chromium; the regular
  test workflow (`ci.yml`) is unchanged and does not run the
  freeze.


## 2.1.0 — 2026-10-31

Staff-review implementation (from the 2026-10-31 staff review,
delivered separately and not part of this repo). Verified:
ruff clean, ruff format clean, 39/39 pytest tests pass from
a fresh extraction.

### Breaking changes

- **Auto-seed is now opt-in.** `WORKSPACE_MONITOR_AUTO_SEED`
  defaults to `0`; a fresh database is empty until you run
  `python scripts/seed_demo.py` (or set the variable to `1`
  for a demo run). v2.0 seeded any empty database by default,
  which could silently put demo users into a production DB.
- **Pre-v2.1 JWTs are rejected.** Tokens issued before this
  release have no `jti` and cannot be revoked; they are
  refused outright. Re-login after upgrading (old tokens
  expire within 8 hours anyway).
- **Posting `status` on mileage is now a 422.** v2.0 accepted
  it and silently dropped it; the create schema forbids extra
  fields so the contract is explicit.

### Security

- `POST /api/logout` revokes the token's `jti` server-side;
  revoked tokens are rejected on every request.
- Failed-login rate limiting per IP (5 failures in 15
  minutes → 429; configurable via
  `WORKSPACE_MONITOR_LOGIN_MAX_FAILURES` /
  `WORKSPACE_MONITOR_LOGIN_WINDOW_SECONDS`). This is
  per-process — production deployments should also
  rate-limit at the reverse proxy.
- Clock-in/out timestamps are UTC, not naive local time.

### Added

- `GET /api/stats` — dashboard counts via `COUNT(*)`, fixing
  home-page metrics that previously capped at the list limit
  of 100 rows.
- `POST /api/mileage/bulk` — up to 500 entries in one
  transaction, replacing the frontend's one-request-per-row
  upload (which left half-imported files on failure).
- `GET /api/schedule` now accepts `start`/`end` date filters.
- Typed `AuthContext` (frozen dataclass) replaces the untyped
  auth `dict`; shared `Pagination` dependency replaces seven
  copy-pasted limit/offset blocks.
- Frontend `ApiError` taxonomy: 401 → "session expired",
  429 → rate-limit message, backend-down → a clear message;
  raw exception text is no longer shown to users.
- Distance page: Nominatim/OSRM calls now have 10 s timeouts,
  use HTTPS for OSRM, and cache only successes (failures are
  no longer cached for an hour).
- Indexes on all list-query columns, a partial unique index
  on open attendance shifts (concurrent clock-ins now fail
  closed), WAL mode, and per-connection foreign-key
  enforcement. `ruff format` is now enforced in CI.

### Fixed

- `hr_data.clock_in_status` is derived from open attendance
  shifts instead of a stale stored flag that clock-in/out
  never updated.
- Successful logins now update `last_login_time` (v2.0 left
  the seed timestamp in place).
- Mileage bulk upload normalizes Excel timestamps to
  `YYYY-MM-DD` (v2.0 stored them as datetime strings) and
  validates required columns before uploading.
- Attendance page uses the shared `api_client` for backend
  calls instead of raw `requests` (the last page still doing
  so); mileage date and contact email are validated by
  Pydantic (`date` type, `EmailStr`); route polylines are
  capped at 1,000,000 characters.
- `pyproject.toml` version and the FastAPI app version are
  pinned together by `tests/test_version.py`, so a bump in
  one place cannot drift from the other.

### Still open (not in this release)

- Full router + repository split (endpoints still live in
  `main.py`, now with typed auth and pagination), Alembic
  migrations (the hand-rolled `ALTER TABLE` check in
  `init_db` remains), a single settings object (config is
  still read from `os.environ` in several modules), the
  `src/` + `sys.path` package layout, and a schedule/mileage
  approval workflow. These are the next review items, not
  hidden gaps — see the review's §3.2 order.

## 2.0.0 — 2026-10-26

Full modernization of the v1 FastAPI + Streamlit dashboard. The
stack is unchanged (Streamlit kept, rather than rewritten in
Flask/Jinja, to keep the change reviewable); everything below is
what was actually changed and verified.

### Breaking changes

- **Login now requires a password.** `POST /api/login` takes
  `email` + `password` and returns a signed JWT. v1 accepted an
  email alone and returned the literal token `email:role`; those
  tokens are now rejected with 401.
- **Demo credentials are explicit.** All demo users share
  `Demo1234!` unless `WORKSPACE_MONITOR_DEMO_PASSWORD` is set
  before seeding. Do not seed demo data in production.
- **The database file is no longer tracked.** `monitor.db` was
  committed in v1; it is gitignored now and created/seeded at
  runtime. Existing deployments should delete the tracked copy
  and let the backend recreate it, or keep it and run the
  automatic `password_hash` column migration (see below).
- **Tokens are no longer persisted in browser localStorage.**
  Closing the tab logs you out.

### Security fixes

- Real auth: bcrypt password hashes + HS256 JWTs
  (`WORKSPACE_MONITOR_SECRET_KEY`, ephemeral per-process secret
  when unset, with a warning). Every request re-validates the
  user against the database (unknown/suspended users get 401).
- One `Role` enum (`Admin`/`Supervisor`/`Standard`) with
  case-insensitive normalization, fixing v1's case bugs:
  admin-only views in attendance, schedule, and mileage compared
  against lowercase `"admin"` and never matched, and contact
  create/delete denied real Admins for the same reason.
- Mileage attribution: standard users are always recorded as
  themselves, regardless of `user_email` in the request body.
- Coordinate validation on clock-in/out (latitude/longitude
  ranges) and `miles > 0` on mileage entries.
- Nominatim User-Agent is now an honest app identifier instead
  of a browser string.

### Fixed

- Schedule Previous/Next buttons: they read the view-mode radio's
  variable before the widget was created, so clicking them raised
  a NameError on that rerun. The persisted radio value is now
  read before the buttons.
- Distance calculator auth: it read session key `token` while
  every other page used `auth_token`, so its API calls went out
  unauthenticated. All pages now share `utils.api_client`.
- Schedule admin filter no longer uses a hardcoded 4-user list;
  it fetches the user list from the API (same for mileage).
- `run_app.py`: waits for `/health` instead of sleeping 2s, and
  terminates both child processes on Ctrl+C (v1 orphaned them).
- README converted from UTF-16LE (which git treated as binary)
  to UTF-8, and rewritten as a landing page.
- Home dashboard is no longer a stub: it shows live user,
  attendance, and pending-mileage counts, or a backend-unreachable
  warning.

### Structure / hygiene

- Restored `.gitignore` (v1's last commit deleted it) and removed
  tracked `__pycache__/` and `monitor.db` from version control.
- Added `.gitattributes` (LF line endings), `pyproject.toml`
  (pinned dependencies, ruff, pytest config), and a pinned
  `requirements.txt` that now includes the previously missing
  `pandas`, `polyline`, `streamlit-js-eval`, `streamlit-calendar`,
  and `openpyxl` — a fresh v1 install could not run the pages.
- Schema and seed split: `init_db()` creates tables only and
  adds `password_hash` to a pre-v2 database; `seed_demo_data()`
  (also `scripts/seed_demo.py`) inserts one deterministic dataset
  and is a no-op on a non-empty database. v1 seeded randomly on
  every empty database.
- List endpoints accept `limit` (1–500, default 100) and `offset`.
- Added `GET /health`, a startup lifespan (schema + optional
  auto-seed), and `GET /` unchanged.
- Tests: 24 pytest tests (auth unit tests, API behaviour
  including forged tokens, role visibility, mileage spoofing,
  contact permissions, clock-in/out rules, route-cache
  round-trip, seed idempotence, frontend client headers),
  plus ruff and GitHub Actions CI. One test caught a real v2 bug
  during development: normalizing a `Role` enum re-stringified
  it to `"Role.ADMIN"` and demoted privileged users — fixed, with
  a regression test.
- MIT LICENSE (holder enonymous1).

### Not changed

- Feature set: attendance, schedule, mileage, directory, and
  distance calculator behave as in v1 for legitimate users.
- The Google/ADP-flavoured model names are kept for
  compatibility, with a note that they describe local rows, not
  live integrations — v1 never called Google or ADP, and v2
  doesn't either.
- Distance routing still uses the public Nominatim/OSRM demo
  endpoints; it is not a production routing service.
