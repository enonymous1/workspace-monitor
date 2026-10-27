"""SQLite storage for ss-workspaceMonitor.

Schema creation and demo seeding are deliberately separate in v2.
v1 mixed them in one ``init_db()`` and seeded with ``random`` on
every empty database, so two fresh checkouts never had the same
data. Here ``init_db()`` only creates tables (and adds the v2
``password_hash`` column to an existing v1 database), while
``seed_demo_data()`` inserts one fixed, deterministic demo dataset
and is a no-op once any user exists.

The database path is ``WORKSPACE_MONITOR_DB`` or, by default,
``src/api/monitor.db`` next to this file. The file is gitignored:
it is runtime state, not source, and must never be committed again.

Demo data is fictional (``@example.com`` users, Virginia hub
locations used as sample coordinates). It exists so the dashboard
can be run and screenshotted without real HR or Workspace data.
Do not seed it in production.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime, time, timedelta
from pathlib import Path

from api.auth import Role, hash_password

DB_PATH = Path(
    os.environ.get("WORKSPACE_MONITOR_DB", Path(__file__).resolve().parent / "monitor.db")
)

DEMO_USERS = [
    # (email, full name, department, title, role)
    ("admin@example.com", "System Administrator", "IT", "Lead Admin", Role.ADMIN),
    ("user@example.com", "Standard User", "Operations", "Associate", Role.STANDARD),
    ("jane.doe@example.com", "Jane Doe", "Engineering", "Software Architect", Role.SUPERVISOR),
    ("john.smith@example.com", "John Smith", "Sales", "Regional Manager", Role.SUPERVISOR),
    ("michael.v@example.com", "Michael Vance", "Engineering", "Developer", Role.STANDARD),
    ("sarah.w@example.com", "Sarah Wright", "Billing", "Analyst", Role.STANDARD),
    ("david.m@example.com", "David Miller", "Stafford Operations", "Supervisor", Role.SUPERVISOR),
    ("emily.r@example.com", "Emily Rogers", "Culpeper Data", "Data Tech", Role.STANDARD),
    ("chris.j@example.com", "Chris Jones", "HR", "Coordinator", Role.STANDARD),
    ("jessica.b@example.com", "Jessica Bell", "IT", "Support Tech", Role.STANDARD),
    ("brian.t@example.com", "Brian Taylor", "Sales", "Rep", Role.STANDARD),
    ("nancy.k@example.com", "Nancy King", "Marketing", "Manager", Role.SUPERVISOR),
    ("kevin.l@example.com", "Kevin Lee", "Facilities", "C-Ville Lead", Role.SUPERVISOR),
    ("amanda.s@example.com", "Amanda Scott", "Customer Success", "Lead", Role.STANDARD),
    ("robert.p@example.com", "Robert Perry", "Engineering", "QA Engineer", Role.STANDARD),
]

# Fixed sample locations (Virginia hubs, demo coordinates only).
VA_LOCATIONS = [
    ("Stafford Hub", 38.4232, -77.4080),
    ("Quantico Office", 38.5218, -77.2911),
    ("North Stafford Annex", 38.4520, -77.4200),
    ("Culpeper Data Center", 38.4732, -77.9961),
    ("Culpeper West Wing", 38.4800, -78.0100),
    ("Garrisonville Branch", 38.4682, -77.4475),
    ("Charlottesville HQ", 38.0293, -78.4767),
    ("UVA Innovation Lab", 38.0350, -78.5030),
    ("Downtown C-ville", 38.0299, -78.4790),
    ("Orange Tech Space", 38.2458, -78.1102),
    ("Fredericksburg Hub", 38.3032, -77.4605),
    ("Locust Grove Office", 38.3022, -77.8189),
    ("Waynesboro Point", 38.0685, -78.8895),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    email TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    department TEXT,
    title TEXT,
    last_login_time DATETIME,
    is_suspended BOOLEAN DEFAULT 0,
    role TEXT DEFAULT 'Standard',
    password_hash TEXT
);
CREATE TABLE IF NOT EXISTS drive_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL,
    document_name TEXT NOT NULL,
    view_timestamp DATETIME NOT NULL,
    viewer_email TEXT NOT NULL,
    FOREIGN KEY (viewer_email) REFERENCES users (email)
);
CREATE TABLE IF NOT EXISTS hr_data (
    worker_id TEXT PRIMARY KEY,
    primary_email TEXT NOT NULL,
    clock_in_status BOOLEAN DEFAULT 0,
    current_pay_cycle_hours REAL DEFAULT 0.0,
    FOREIGN KEY (primary_email) REFERENCES users (email)
);
CREATE TABLE IF NOT EXISTS route_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    addr_start TEXT NOT NULL,
    addr_end TEXT NOT NULL,
    distance_miles REAL,
    duration_minutes REAL,
    geometry_polyline TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(addr_start, addr_end)
);
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT,
    clock_in_time TEXT,
    clock_out_time TEXT,
    latitude REAL,
    longitude REAL,
    location_name TEXT
);
CREATE TABLE IF NOT EXISTS schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT,
    event_title TEXT,
    start_time TEXT,
    end_time TEXT,
    event_type TEXT
);
CREATE TABLE IF NOT EXISTS mileage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT,
    date TEXT,
    start_location TEXT,
    end_location TEXT,
    miles REAL,
    purpose TEXT,
    status TEXT DEFAULT 'pending'
);
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_email TEXT,
    full_name TEXT,
    job_title TEXT,
    email TEXT,
    phone TEXT,
    category TEXT
);
"""


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables; add ``password_hash`` to a pre-v2 database in place."""
    conn = get_db_connection()
    try:
        conn.executescript(SCHEMA)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
        if "password_hash" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
        conn.commit()
    finally:
        conn.close()


def demo_password() -> str:
    """Demo-seed password. Override with WORKSPACE_MONITOR_DEMO_PASSWORD.

    This is demo-only by design: every demo user shares it, and the
    README says to change it and never seed demo data in production.
    """
    return os.environ.get("WORKSPACE_MONITOR_DEMO_PASSWORD", "Demo1234!")


def seed_demo_data() -> int:
    """Insert the deterministic demo dataset. Returns users inserted.

    A no-op when the users table is non-empty, so re-running the
    seeder (or restarting the API) never duplicates demo rows.
    """
    init_db()
    conn = get_db_connection()
    try:
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
            return 0
        password_hash = hash_password(demo_password())
        now = datetime.now()
        users = [
            (email, name, dept, title, (now - timedelta(hours=1 + i)).isoformat(), 0, role.value, password_hash)
            for i, (email, name, dept, title, role) in enumerate(DEMO_USERS)
        ]
        conn.executemany("INSERT INTO users VALUES (?,?,?,?,?,?,?,?)", users)

        conn.executemany(
            "INSERT INTO drive_activity (document_id, document_name, view_timestamp, viewer_email)"
            " VALUES (?,?,?,?)",
            [
                ("doc-1", "Q1 Financials", (now - timedelta(minutes=45)).isoformat(), "admin@example.com"),
                ("doc-2", "VA Expansion Plan", (now - timedelta(hours=3)).isoformat(), "jane.doe@example.com"),
                ("doc-3", "Stafford Site Logistics", (now - timedelta(minutes=10)).isoformat(), "david.m@example.com"),
            ],
        )
        conn.executemany(
            "INSERT INTO hr_data VALUES (?,?,?,?)",
            [
                ("WID-ADM01", "admin@example.com", 1, 40.0),
                ("WID-JD01", "jane.doe@example.com", 0, 32.5),
                ("WID-DM01", "david.m@example.com", 1, 38.0),
            ],
        )

        # Deterministic attendance: user i, day d -> location (i + d) % len.
        attendance = []
        for i, (email, *_rest) in enumerate(DEMO_USERS):
            for d in range(5):
                loc_name, lat, lon = VA_LOCATIONS[(i + d) % len(VA_LOCATIONS)]
                day = now - timedelta(days=d)
                attendance.append(
                    (
                        email,
                        datetime.combine(day.date(), time(9, 0)).strftime("%Y-%m-%d %H:%M:%S"),
                        datetime.combine(day.date(), time(17, 0)).strftime("%Y-%m-%d %H:%M:%S"),
                        lat,
                        lon,
                        loc_name,
                    )
                )
        conn.executemany(
            "INSERT INTO attendance (user_email, clock_in_time, clock_out_time, latitude, longitude, location_name)"
            " VALUES (?,?,?,?,?,?)",
            attendance,
        )

        # Schedule: weekday shifts for the first four users, plus a
        # meeting every third day and a fortnightly weekend on-call.
        schedule = []
        today = date.today()
        for email in [u[0] for u in DEMO_USERS[:4]]:
            for offset in range(-7, 21):
                target = today + timedelta(days=offset)
                if target.weekday() < 5:
                    schedule.append((email, "Regular Shift", f"{target} 09:00:00", f"{target} 17:00:00", "Work"))
                    if offset % 3 == 0:
                        schedule.append((email, "Project Sync", f"{target} 11:00:00", f"{target} 12:00:00", "Meeting"))
                elif offset % 14 == 0:
                    schedule.append((email, "Weekend Support", f"{target} 10:00:00", f"{target} 14:00:00", "On-Call"))
        conn.executemany(
            "INSERT INTO schedule (user_email, event_title, start_time, end_time, event_type)"
            " VALUES (?,?,?,?,?)",
            schedule,
        )

        conn.executemany(
            "INSERT INTO mileage_log (user_email, date, start_location, end_location, miles, purpose, status)"
            " VALUES (?,?,?,?,?,?,?)",
            [
                ("admin@example.com", "2023-10-01", "Office", "Client Site A", 15.5, "Project Consultation", "verified"),
                ("user@example.com", "2023-10-01", "Home", "Office", 12.0, "Daily Commute", "pending"),
                ("user@example.com", "2023-10-02", "Office", "Post Office", 2.5, "Mailing documents", "pending"),
                ("jane.doe@example.com", "2023-10-01", "Home", "Airport", 25.0, "Business Travel", "verified"),
            ],
        )

        contacts = [
            ("universal", "Workspace Support", "IT Support", "support@workspace.com", "555-0100", "Universal"),
            ("universal", "HR Benefits", "HR Main", "hr@workspace.com", "555-0101", "Universal"),
        ]
        for i, (email, name, _dept, title, role) in enumerate(DEMO_USERS):
            contacts.append(("universal", name, title, email, f"555-{1000 + i}", role.value))
        conn.executemany(
            "INSERT INTO contacts (owner_email, full_name, job_title, email, phone, category)"
            " VALUES (?,?,?,?,?,?)",
            contacts,
        )
        conn.commit()
        return len(users)
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized successfully at {DB_PATH}.")
