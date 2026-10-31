"""workspace-monitor API v2.1 (FastAPI).

v2.1 changes on top of v2.0 (see CHANGELOG.md):

* Auth is a typed ``AuthContext`` (``api.security``), not a dict,
  and list pagination is one shared dependency (``api.pagination``).
* ``POST /api/logout`` revokes the token's ``jti``; revoked and
  pre-v2.1 tokens (no ``jti``) are rejected on every request.
* Failed-login rate limiting per IP (``api.rate_limit``; the
  reverse proxy is still the production limit).
* Demo auto-seed is opt-in: it runs only when
  ``WORKSPACE_MONITOR_AUTO_SEED=1``. A fresh production DB must
  never get demo users by default.
* Clock-in is atomic: a partial unique index on open shifts
  makes concurrent clock-ins fail closed (see database schema).
* ``GET /api/stats`` (counts, no row transfer) and
  ``POST /api/mileage/bulk`` (one transaction, per-row report).
* ``GET /api/schedule`` accepts ``start``/``end`` date filters.
* ``hr_data.clock_in_status`` is derived from open attendance
  shifts instead of a stale stored flag, and successful logins
  update ``last_login_time``.
* Clock-in/out timestamps are UTC (``YYYY-MM-DD HH:MM:SS``).
"""

from __future__ import annotations

import os
import sqlite3
import sys
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, EmailStr, Field

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from api.auth import (  # noqa: E402
    Role,
    create_access_token,
    decode_access_token,
    is_privileged,
    verify_password,
)
from api.database import get_db_connection, init_db, seed_demo_data  # noqa: E402
from api.pagination import Pagination, pagination  # noqa: E402
from api.rate_limit import login_limiter  # noqa: E402
from api.security import AuthContext, get_current_user  # noqa: E402
from models.models import ADPHRWorker, GoogleAdminUser, GoogleDriveActivity  # noqa: E402


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    # v2.1: opt-in only. v2.0 seeded any empty DB by default, which
    # meant a misconfigured production deploy got demo users.
    if os.environ.get("WORKSPACE_MONITOR_AUTO_SEED", "0") == "1":
        seed_demo_data()
    yield


app = FastAPI(
    title="workspace-monitor API",
    description="Workspace dashboard API: attendance, schedule, mileage, directory, and route cache.",
    version="2.1.0",
    lifespan=lifespan,
)


# --- Auth models ---


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str


class StatsResponse(BaseModel):
    """Counts for the home dashboard. No row transfer, so the
    metrics stay correct past the list endpoints' limit of 100."""

    users: int
    attendance_records: int
    pending_mileage: int


class RouteCacheRequest(BaseModel):
    addr_start: str
    addr_end: str
    distance_miles: float
    duration_minutes: float
    # A driving polyline is rarely over ~100 KB; cap it so an
    # authenticated client cannot stuff megabytes into SQLite.
    geometry_polyline: str = Field(..., max_length=1_000_000)


class RouteCacheResponse(BaseModel):
    distance_miles: float
    duration_minutes: float
    geometry_polyline: str


class AttendanceRecord(BaseModel):
    id: Optional[int] = None
    user_email: str
    clock_in_time: str
    clock_out_time: Optional[str] = None
    latitude: float
    longitude: float
    location_name: str


class ClockRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    location_name: str = "Unknown"


class ScheduleEvent(BaseModel):
    id: int
    user_email: str
    event_title: str
    start_time: str
    end_time: str
    event_type: str


class MileageCreate(BaseModel):
    """Fields a client may supply when creating mileage.

    ``status`` is deliberately absent: v2.0 accepted it on POST
    and silently dropped it (rows always became ``pending``).
    Extra fields are forbidden, so posting ``status`` now gets
    a 422 instead of a misleading 200.
    """

    model_config = ConfigDict(extra="forbid")

    user_email: str
    date: date
    start_location: str
    end_location: str
    miles: float = Field(..., gt=0)
    purpose: str


class MileageEntry(MileageCreate):
    id: Optional[int] = None
    status: str = "pending"


class MileageBulkRequest(BaseModel):
    entries: List[MileageCreate] = Field(..., max_length=500)


class MileageBulkResponse(BaseModel):
    inserted: int
    errors: List[dict] = []


class ContactRecord(BaseModel):
    id: Optional[int] = None
    owner_email: str
    full_name: str
    job_title: str
    email: EmailStr
    phone: str
    category: str


# --- Security helpers ---


def _visible_to(auth: AuthContext, requested_email: Optional[str]) -> Optional[str]:
    """Resolve which email filter applies: privileged users may filter,
    Standard users always see only their own rows."""
    if is_privileged(auth.role):
        return requested_email
    return auth.email


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# --- Health / auth ---


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}


@app.post("/api/login", response_model=TokenResponse, tags=["Auth"])
async def login(request: LoginRequest, http_request: Request):
    """Authenticate with email + password and return a JWT.

    Failed attempts are rate-limited per client IP (see
    ``api.rate_limit``); the production limit belongs at the
    reverse proxy. Successful logins clear the IP's failure
    history and update ``last_login_time`` (v2.0 never did,
    so that column held the seed timestamp).
    """
    ip = _client_ip(http_request)
    if login_limiter.is_blocked(ip):
        raise HTTPException(
            status_code=429, detail="Too many failed login attempts. Try again later."
        )
    conn = get_db_connection()
    try:
        user = conn.execute(
            "SELECT full_name, role, password_hash, is_suspended FROM users WHERE email = ?",
            (request.email,),
        ).fetchone()
        if (
            user is None
            or user["is_suspended"]
            or not verify_password(request.password, user["password_hash"])
        ):
            # Same response for unknown user / bad password: no user enumeration.
            login_limiter.record_failure(ip)
            raise HTTPException(status_code=401, detail="Invalid email or password")
        conn.execute(
            "UPDATE users SET last_login_time = ? WHERE email = ?",
            (datetime.now(timezone.utc).isoformat(), request.email),
        )
        conn.commit()
    finally:
        conn.close()
    login_limiter.record_success(ip)
    role = Role.normalize(user["role"])
    return TokenResponse(
        access_token=create_access_token(request.email, role),
        role=role.value,
        full_name=user["full_name"],
    )


@app.post("/api/logout", tags=["Auth"])
async def logout(
    auth: AuthContext = Depends(get_current_user), authorization: Optional[str] = Header(None)
):
    """Revoke the caller's token so logout actually ends the session.

    v2.0 logout only cleared frontend session state and the JWT
    stayed valid until expiry. The token's ``jti`` is inserted
    into ``revoked_tokens``; ``get_current_user`` rejects it
    on every subsequent request.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    try:
        payload = decode_access_token(authorization.split(" ", 1)[1])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token") from None
    jti = payload.get("jti")
    if not jti:
        raise HTTPException(status_code=401, detail="Invalid token")
    conn = get_db_connection()
    try:
        conn.execute("INSERT OR IGNORE INTO revoked_tokens (jti) VALUES (?)", (jti,))
        conn.commit()
    finally:
        conn.close()
    return {"status": "success"}


@app.get("/api/stats", response_model=StatsResponse, tags=["Health"])
async def get_stats(auth: AuthContext = Depends(get_current_user)):
    """Dashboard counts without transferring rows.

    The home page previously fetched list endpoints capped at
    100 rows and reported their lengths as totals, which went
    silently wrong past 100 rows. Counts come from COUNT(*).
    Standard users get their own counts (users = 1).
    """
    conn = get_db_connection()
    try:
        if is_privileged(auth.role):
            users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            attendance = conn.execute("SELECT COUNT(*) FROM attendance").fetchone()[0]
            pending = conn.execute(
                "SELECT COUNT(*) FROM mileage_log WHERE status = 'pending'"
            ).fetchone()[0]
        else:
            users = 1
            attendance = conn.execute(
                "SELECT COUNT(*) FROM attendance WHERE user_email = ?", (auth.email,)
            ).fetchone()[0]
            pending = conn.execute(
                "SELECT COUNT(*) FROM mileage_log WHERE user_email = ? AND status = 'pending'",
                (auth.email,),
            ).fetchone()[0]
    finally:
        conn.close()
    return StatsResponse(users=users, attendance_records=attendance, pending_mileage=pending)


# --- Google Workspace-shaped reads (local data) ---


@app.get("/api/users", response_model=List[GoogleAdminUser], tags=["Google Workspace"])
async def get_users(
    auth: AuthContext = Depends(get_current_user),
    email: Optional[EmailStr] = Query(None),
    page: Pagination = Depends(pagination),
):
    visible = _visible_to(auth, email)
    conn = get_db_connection()
    try:
        if visible:
            rows = conn.execute(
                "SELECT * FROM users WHERE email = ? LIMIT ? OFFSET ?",
                (visible, page.limit, page.offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM users LIMIT ? OFFSET ?", (page.limit, page.offset)
            ).fetchall()
    finally:
        conn.close()
    return [
        GoogleAdminUser(**{k: v for k, v in dict(u).items() if k != "password_hash"}) for u in rows
    ]


@app.get("/api/activity", response_model=List[GoogleDriveActivity], tags=["Google Workspace"])
async def get_activity(
    auth: AuthContext = Depends(get_current_user),
    email: Optional[EmailStr] = Query(None),
    page: Pagination = Depends(pagination),
):
    visible = _visible_to(auth, email)
    conn = get_db_connection()
    try:
        if visible:
            rows = conn.execute(
                "SELECT * FROM drive_activity WHERE viewer_email = ? LIMIT ? OFFSET ?",
                (visible, page.limit, page.offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM drive_activity LIMIT ? OFFSET ?", (page.limit, page.offset)
            ).fetchall()
    finally:
        conn.close()
    return [GoogleDriveActivity(**dict(a)) for a in rows]


@app.get("/api/hr-status", response_model=List[ADPHRWorker], tags=["HR Data"])
async def get_hr_status(
    auth: AuthContext = Depends(get_current_user),
    email: Optional[EmailStr] = Query(None),
    page: Pagination = Depends(pagination),
):
    """HR rows with clock-in status derived from attendance.

    v2.0 returned the stored ``hr_data.clock_in_status`` flag,
    which clock-in/out never updated — it was seed data forever.
    The flag is now computed: a user is clocked in iff they have
    an open attendance shift. The stored column is ignored here
    and should be dropped in a future schema migration.
    """
    visible = _visible_to(auth, email)
    query = (
        "SELECT h.worker_id, h.primary_email,"
        " CASE WHEN EXISTS (SELECT 1 FROM attendance a WHERE a.user_email = h.primary_email"
        " AND a.clock_out_time IS NULL) THEN 1 ELSE 0 END AS clock_in_status,"
        " h.current_pay_cycle_hours FROM hr_data h"
    )
    conn = get_db_connection()
    try:
        if visible:
            rows = conn.execute(
                query + " WHERE h.primary_email = ? LIMIT ? OFFSET ?",
                (visible, page.limit, page.offset),
            ).fetchall()
        else:
            rows = conn.execute(query + " LIMIT ? OFFSET ?", (page.limit, page.offset)).fetchall()
    finally:
        conn.close()
    return [ADPHRWorker(**dict(h)) for h in rows]


# --- Route caching ---


@app.get("/api/route-cache", response_model=Optional[RouteCacheResponse], tags=["Utils"])
async def get_cached_route(
    addr_start: str, addr_end: str, auth: AuthContext = Depends(get_current_user)
):
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT distance_miles, duration_minutes, geometry_polyline FROM route_cache"
            " WHERE addr_start = ? AND addr_end = ?",
            (addr_start.strip().lower(), addr_end.strip().lower()),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


@app.post("/api/route-cache", tags=["Utils"])
async def save_route_to_cache(
    request: RouteCacheRequest, auth: AuthContext = Depends(get_current_user)
):
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO route_cache (addr_start, addr_end, distance_miles, duration_minutes, geometry_polyline)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                request.addr_start.strip().lower(),
                request.addr_end.strip().lower(),
                request.distance_miles,
                request.duration_minutes,
                request.geometry_polyline,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return {"status": "success"}


# --- Attendance ---


@app.get("/api/attendance", response_model=List[AttendanceRecord], tags=["Attendance"])
async def get_attendance(
    auth: AuthContext = Depends(get_current_user),
    page: Pagination = Depends(pagination),
):
    conn = get_db_connection()
    try:
        if is_privileged(auth.role):
            rows = conn.execute(
                "SELECT * FROM attendance ORDER BY clock_in_time DESC LIMIT ? OFFSET ?",
                (page.limit, page.offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM attendance WHERE user_email = ? ORDER BY clock_in_time DESC LIMIT ? OFFSET ?",
                (auth.email, page.limit, page.offset),
            ).fetchall()
    finally:
        conn.close()
    return [AttendanceRecord(**dict(row)) for row in rows]


@app.post("/api/attendance/clock-in", tags=["Attendance"])
async def clock_in(request: ClockRequest, auth: AuthContext = Depends(get_current_user)):
    """Open a shift for the caller, if they do not already have one.

    The pre-check exists for a friendly error message only. The
    real guarantee is the partial unique index on open shifts
    (see database schema): two concurrent clock-ins must not
    both succeed, and only a database constraint can enforce
    that across processes. Timestamps are UTC.
    """
    user_email = auth.email
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM attendance WHERE user_email = ? AND clock_out_time IS NULL",
            (user_email,),
        ).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="User is already clocked in.")
        try:
            conn.execute(
                "INSERT INTO attendance (user_email, clock_in_time, latitude, longitude, location_name)"
                " VALUES (?, ?, ?, ?, ?)",
                (user_email, now, request.latitude, request.longitude, request.location_name),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            # Lost a race with another clock-in for the same user.
            raise HTTPException(status_code=400, detail="User is already clocked in.") from None
    finally:
        conn.close()
    return {"status": "success", "clock_in_time": now}


@app.post("/api/attendance/clock-out", tags=["Attendance"])
async def clock_out(request: ClockRequest, auth: AuthContext = Depends(get_current_user)):
    """Close the caller's latest open shift.

    Note: the request's latitude/longitude/location are accepted
    for API compatibility but are not stored — clock-out
    location is not recorded in the current schema. Do not
    treat clock-out payloads as location evidence until a
    schema migration adds those columns.
    """
    user_email = auth.email
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT id FROM attendance WHERE user_email = ? AND clock_out_time IS NULL"
            " ORDER BY clock_in_time DESC LIMIT 1",
            (user_email,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="No active clock-in found.")
        conn.execute("UPDATE attendance SET clock_out_time = ? WHERE id = ?", (now, row["id"]))
        conn.commit()
    finally:
        conn.close()
    return {"status": "success", "clock_out_time": now}


# --- Schedule ---


@app.get("/api/schedule", response_model=List[ScheduleEvent], tags=["Schedule"])
async def get_schedule(
    auth: AuthContext = Depends(get_current_user),
    user_emails: Optional[List[str]] = Query(None),
    start: Optional[date] = Query(
        None, description="Include events starting on or after this date"
    ),
    end: Optional[date] = Query(None, description="Include events ending on or before this date"),
    page: Pagination = Depends(pagination),
):
    """Schedule events, optionally filtered by user and date range.

    Standard users always see only their own events, even if
    they pass ``user_emails``. Date filters compare against the
    stored ``YYYY-MM-DD HH:MM:SS`` strings, so a date filter
    covers the whole day.
    """
    conditions: list[str] = []
    params: list = []
    if is_privileged(auth.role):
        if user_emails:
            placeholders = ",".join(["?"] * len(user_emails))
            conditions.append(f"user_email IN ({placeholders})")
            params.extend(user_emails)
    else:
        conditions.append("user_email = ?")
        params.append(auth.email)
    if start:
        conditions.append("start_time >= ?")
        params.append(f"{start.isoformat()} 00:00:00")
    if end:
        conditions.append("end_time <= ?")
        params.append(f"{end.isoformat()} 23:59:59")
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            f"SELECT * FROM schedule {where} ORDER BY start_time ASC LIMIT ? OFFSET ?",
            (*params, page.limit, page.offset),
        ).fetchall()
    finally:
        conn.close()
    return [ScheduleEvent(**dict(row)) for row in rows]


# --- Mileage ---


@app.get("/api/mileage", response_model=List[MileageEntry], tags=["Mileage"])
async def get_mileage(
    auth: AuthContext = Depends(get_current_user),
    user_email: Optional[str] = Query(None),
    page: Pagination = Depends(pagination),
):
    visible = _visible_to(auth, user_email)
    conn = get_db_connection()
    try:
        if visible:
            rows = conn.execute(
                "SELECT * FROM mileage_log WHERE user_email = ? ORDER BY date DESC LIMIT ? OFFSET ?",
                (visible, page.limit, page.offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM mileage_log ORDER BY date DESC LIMIT ? OFFSET ?",
                (page.limit, page.offset),
            ).fetchall()
    finally:
        conn.close()
    return [MileageEntry(**dict(row)) for row in rows]


def _mileage_owner(request_user_email: str, auth: AuthContext) -> str:
    """Attribute a mileage entry: privileged users may file for a
    named user; Standard users are always recorded as themselves
    (v2.0 trusted the request body, letting any user file for
    anyone)."""
    return request_user_email if is_privileged(auth.role) else auth.email


@app.post("/api/mileage", tags=["Mileage"])
async def add_mileage(request: MileageCreate, auth: AuthContext = Depends(get_current_user)):
    owner = _mileage_owner(request.user_email, auth)
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO mileage_log (user_email, date, start_location, end_location, miles, purpose)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                owner,
                request.date.isoformat(),
                request.start_location,
                request.end_location,
                request.miles,
                request.purpose,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return {"status": "success"}


@app.post("/api/mileage/bulk", response_model=MileageBulkResponse, tags=["Mileage"])
async def add_mileage_bulk(
    request: MileageBulkRequest, auth: AuthContext = Depends(get_current_user)
):
    """Insert many mileage entries in one transaction.

    v2.0's frontend uploaded one HTTP request per row, so a bad
    row halfway through left a half-imported file with no
    report of what landed. This endpoint validates all rows
    with Pydantic before any insert, then inserts in a single
    transaction: either all rows land, or none do, and the
    response reports how many.
    """
    conn = get_db_connection()
    try:
        for entry in request.entries:
            owner = _mileage_owner(entry.user_email, auth)
            conn.execute(
                "INSERT INTO mileage_log (user_email, date, start_location, end_location, miles, purpose)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    owner,
                    entry.date.isoformat(),
                    entry.start_location,
                    entry.end_location,
                    entry.miles,
                    entry.purpose,
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return MileageBulkResponse(inserted=len(request.entries), errors=[])


# --- Contacts / directory ---


@app.get("/api/contacts", response_model=List[ContactRecord], tags=["Contacts"])
async def get_contacts(
    auth: AuthContext = Depends(get_current_user),
    page: Pagination = Depends(pagination),
):
    conn = get_db_connection()
    try:
        if is_privileged(auth.role):
            rows = conn.execute(
                "SELECT * FROM contacts ORDER BY full_name ASC LIMIT ? OFFSET ?",
                (page.limit, page.offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM contacts WHERE owner_email = 'universal' OR owner_email = ?"
                " ORDER BY full_name ASC LIMIT ? OFFSET ?",
                (auth.email, page.limit, page.offset),
            ).fetchall()
    finally:
        conn.close()
    return [ContactRecord(**dict(row)) for row in rows]


@app.post("/api/contacts", tags=["Contacts"])
async def create_contact(request: ContactRecord, auth: AuthContext = Depends(get_current_user)):
    # Admin may create for anyone; others only for themselves.
    if auth.role != Role.ADMIN and request.owner_email != auth.email:
        raise HTTPException(
            status_code=403, detail="Not authorized to create contacts for other users"
        )
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO contacts (owner_email, full_name, job_title, email, phone, category)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                request.owner_email,
                request.full_name,
                request.job_title,
                str(request.email),
                request.phone,
                request.category,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return {"status": "success"}


@app.delete("/api/contacts/{contact_id}", tags=["Contacts"])
async def delete_contact(contact_id: int, auth: AuthContext = Depends(get_current_user)):
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT owner_email FROM contacts WHERE id = ?", (contact_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Contact not found")
        if auth.role != Role.ADMIN and row["owner_email"] != auth.email:
            raise HTTPException(status_code=403, detail="Not authorized to delete this contact")
        conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
        conn.commit()
    finally:
        conn.close()
    return {"status": "success"}


@app.get("/", include_in_schema=False)
async def root():
    return {"message": "workspace-monitor API is running. Visit /docs for documentation."}
