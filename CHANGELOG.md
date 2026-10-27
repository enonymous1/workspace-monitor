# Changelog

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
