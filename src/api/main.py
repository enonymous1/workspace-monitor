"""ss-workspaceMonitor API v2 (FastAPI).

Changes from v1, which this module replaces wholesale:

* Real auth: ``POST /api/login`` now takes ``email`` + ``password``
  and returns a signed JWT (see ``api.auth``). The v1 token
  ``email:role`` is rejected, and every request re-validates the
  user against the database (unknown or suspended users get 401).
* Role handling goes through ``api.auth.Role`` everywhere, fixing
  v1's case bugs (``"admin"`` vs ``"Admin"``) that silently broke
  admin-only views and contact management.
* Mileage writes are attributed to the token holder: a Standard
  user can no longer file mileage under someone else's email by
  putting that email in the request body.
* List endpoints accept ``limit``/``offset`` pagination.
* Startup creates the schema and, unless
  ``WORKSPACE_MONITOR_AUTO_SEED=0``, seeds the deterministic demo
  dataset into an empty database (see ``api.database``).

All endpoints are still under ``/api``; ``GET /health`` is public.
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from api.auth import (  # noqa: E402
    Role,
    create_access_token,
    decode_access_token,
    is_privileged,
    verify_password,
)
from api.database import get_db_connection, init_db, seed_demo_data  # noqa: E402
from models.models import ADPHRWorker, GoogleAdminUser, GoogleDriveActivity  # noqa: E402


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    if os.environ.get("WORKSPACE_MONITOR_AUTO_SEED", "1") != "0":
        seed_demo_data()
    yield


app = FastAPI(
    title="ss-workspaceMonitor API",
    description="Workspace dashboard API: attendance, schedule, mileage, directory, and route cache.",
    version="2.0.0",
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


class RouteCacheRequest(BaseModel):
    addr_start: str
    addr_end: str
    distance_miles: float
    duration_minutes: float
    geometry_polyline: str


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


class MileageEntry(BaseModel):
    id: Optional[int] = None
    user_email: str
    date: str
    start_location: str
    end_location: str
    miles: float = Field(..., gt=0)
    purpose: str
    status: str = "pending"


class ContactRecord(BaseModel):
    id: Optional[int] = None
    owner_email: str
    full_name: str
    job_title: str
    email: str
    phone: str
    category: str


# --- Security ---


def verify_token(authorization: Optional[str] = Header(None)) -> dict:
    """Validate a JWT and return {'email': ..., 'role': Role}.

    The role comes from the database, not the token payload, so a
    role change or suspension takes effect without re-login.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    try:
        payload = decode_access_token(authorization.split(" ", 1)[1])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token")
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT role, is_suspended FROM users WHERE email = ?", (email,)
        ).fetchone()
    finally:
        conn.close()
    if row is None or row["is_suspended"]:
        raise HTTPException(status_code=401, detail="Invalid or suspended user")
    return {"email": email, "role": Role.normalize(row["role"])}


def _visible_to(auth: dict, requested_email: Optional[str]) -> Optional[str]:
    """Resolve which email filter applies: privileged users may filter,
    Standard users always see only their own rows."""
    if is_privileged(auth["role"]):
        return requested_email
    return auth["email"]


# --- Health / auth ---


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}


@app.post("/api/login", response_model=TokenResponse, tags=["Auth"])
async def login(request: LoginRequest):
    conn = get_db_connection()
    try:
        user = conn.execute(
            "SELECT full_name, role, password_hash, is_suspended FROM users WHERE email = ?",
            (request.email,),
        ).fetchone()
    finally:
        conn.close()
    if user is None or user["is_suspended"] or not verify_password(request.password, user["password_hash"]):
        # Same response for unknown user / bad password: no user enumeration.
        raise HTTPException(status_code=401, detail="Invalid email or password")
    role = Role.normalize(user["role"])
    return TokenResponse(
        access_token=create_access_token(request.email, role),
        role=role.value,
        full_name=user["full_name"],
    )


# --- Google Workspace-shaped reads (local data) ---


@app.get("/api/users", response_model=List[GoogleAdminUser], tags=["Google Workspace"])
async def get_users(
    auth=Depends(verify_token),
    email: Optional[EmailStr] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    visible = _visible_to(auth, email)
    conn = get_db_connection()
    try:
        if visible:
            rows = conn.execute(
                "SELECT * FROM users WHERE email = ? LIMIT ? OFFSET ?", (visible, limit, offset)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM users LIMIT ? OFFSET ?", (limit, offset)).fetchall()
    finally:
        conn.close()
    return [GoogleAdminUser(**{k: v for k, v in dict(u).items() if k != "password_hash"}) for u in rows]


@app.get("/api/activity", response_model=List[GoogleDriveActivity], tags=["Google Workspace"])
async def get_activity(
    auth=Depends(verify_token),
    email: Optional[EmailStr] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    visible = _visible_to(auth, email)
    conn = get_db_connection()
    try:
        if visible:
            rows = conn.execute(
                "SELECT * FROM drive_activity WHERE viewer_email = ? LIMIT ? OFFSET ?",
                (visible, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM drive_activity LIMIT ? OFFSET ?", (limit, offset)).fetchall()
    finally:
        conn.close()
    return [GoogleDriveActivity(**dict(a)) for a in rows]


@app.get("/api/hr-status", response_model=List[ADPHRWorker], tags=["HR Data"])
async def get_hr_status(
    auth=Depends(verify_token),
    email: Optional[EmailStr] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    visible = _visible_to(auth, email)
    conn = get_db_connection()
    try:
        if visible:
            rows = conn.execute(
                "SELECT * FROM hr_data WHERE primary_email = ? LIMIT ? OFFSET ?",
                (visible, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM hr_data LIMIT ? OFFSET ?", (limit, offset)).fetchall()
    finally:
        conn.close()
    return [ADPHRWorker(**dict(h)) for h in rows]


# --- Route caching ---


@app.get("/api/route-cache", response_model=Optional[RouteCacheResponse], tags=["Utils"])
async def get_cached_route(addr_start: str, addr_end: str, auth=Depends(verify_token)):
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
async def save_route_to_cache(request: RouteCacheRequest, auth=Depends(verify_token)):
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
    auth=Depends(verify_token),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    conn = get_db_connection()
    try:
        if is_privileged(auth["role"]):
            rows = conn.execute(
                "SELECT * FROM attendance ORDER BY clock_in_time DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM attendance WHERE user_email = ? ORDER BY clock_in_time DESC LIMIT ? OFFSET ?",
                (auth["email"], limit, offset),
            ).fetchall()
    finally:
        conn.close()
    return [AttendanceRecord(**dict(row)) for row in rows]


@app.post("/api/attendance/clock-in", tags=["Attendance"])
async def clock_in(request: ClockRequest, auth=Depends(verify_token)):
    user_email = auth["email"]
    now = datetime.now().isoformat()
    conn = get_db_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM attendance WHERE user_email = ? AND clock_out_time IS NULL", (user_email,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="User is already clocked in.")
        conn.execute(
            "INSERT INTO attendance (user_email, clock_in_time, latitude, longitude, location_name)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_email, now, request.latitude, request.longitude, request.location_name),
        )
        conn.commit()
    finally:
        conn.close()
    return {"status": "success", "clock_in_time": now}


@app.post("/api/attendance/clock-out", tags=["Attendance"])
async def clock_out(request: ClockRequest, auth=Depends(verify_token)):
    user_email = auth["email"]
    now = datetime.now().isoformat()
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
    auth=Depends(verify_token),
    user_emails: Optional[List[str]] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    conn = get_db_connection()
    try:
        if is_privileged(auth["role"]):
            if user_emails:
                placeholders = ",".join(["?"] * len(user_emails))
                rows = conn.execute(
                    f"SELECT * FROM schedule WHERE user_email IN ({placeholders})"
                    " ORDER BY start_time ASC LIMIT ? OFFSET ?",
                    (*user_emails, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM schedule ORDER BY start_time ASC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM schedule WHERE user_email = ? ORDER BY start_time ASC LIMIT ? OFFSET ?",
                (auth["email"], limit, offset),
            ).fetchall()
    finally:
        conn.close()
    return [ScheduleEvent(**dict(row)) for row in rows]


# --- Mileage ---


@app.get("/api/mileage", response_model=List[MileageEntry], tags=["Mileage"])
async def get_mileage(
    auth=Depends(verify_token),
    user_email: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    visible = _visible_to(auth, user_email)
    conn = get_db_connection()
    try:
        if visible:
            rows = conn.execute(
                "SELECT * FROM mileage_log WHERE user_email = ? ORDER BY date DESC LIMIT ? OFFSET ?",
                (visible, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM mileage_log ORDER BY date DESC LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
    finally:
        conn.close()
    return [MileageEntry(**dict(row)) for row in rows]


@app.post("/api/mileage", tags=["Mileage"])
async def add_mileage(request: MileageEntry, auth=Depends(verify_token)):
    # v1 trusted request.user_email, letting any user file mileage for
    # anyone. Standard users are now always attributed to themselves;
    # privileged users may file for a named user.
    owner = request.user_email if is_privileged(auth["role"]) else auth["email"]
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO mileage_log (user_email, date, start_location, end_location, miles, purpose)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (owner, request.date, request.start_location, request.end_location, request.miles, request.purpose),
        )
        conn.commit()
    finally:
        conn.close()
    return {"status": "success"}


# --- Contacts / directory ---


@app.get("/api/contacts", response_model=List[ContactRecord], tags=["Contacts"])
async def get_contacts(
    auth=Depends(verify_token),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    conn = get_db_connection()
    try:
        if is_privileged(auth["role"]):
            rows = conn.execute(
                "SELECT * FROM contacts ORDER BY full_name ASC LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM contacts WHERE owner_email = 'universal' OR owner_email = ?"
                " ORDER BY full_name ASC LIMIT ? OFFSET ?",
                (auth["email"], limit, offset),
            ).fetchall()
    finally:
        conn.close()
    return [ContactRecord(**dict(row)) for row in rows]


@app.post("/api/contacts", tags=["Contacts"])
async def create_contact(request: ContactRecord, auth=Depends(verify_token)):
    # Admin may create for anyone; others only for themselves.
    # v1 compared role to lowercase "admin", so real Admins were denied.
    if auth["role"] != Role.ADMIN and request.owner_email != auth["email"]:
        raise HTTPException(status_code=403, detail="Not authorized to create contacts for other users")
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO contacts (owner_email, full_name, job_title, email, phone, category)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                request.owner_email,
                request.full_name,
                request.job_title,
                request.email,
                request.phone,
                request.category,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return {"status": "success"}


@app.delete("/api/contacts/{contact_id}", tags=["Contacts"])
async def delete_contact(contact_id: int, auth=Depends(verify_token)):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT owner_email FROM contacts WHERE id = ?", (contact_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Contact not found")
        if auth["role"] != Role.ADMIN and row["owner_email"] != auth["email"]:
            raise HTTPException(status_code=403, detail="Not authorized to delete this contact")
        conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
        conn.commit()
    finally:
        conn.close()
    return {"status": "success"}


@app.get("/", include_in_schema=False)
async def root():
    return {"message": "ss-workspaceMonitor API is running. Visit /docs for documentation."}
