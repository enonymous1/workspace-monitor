"""Seed the deterministic demo dataset (idempotent, see api.database).

Usage, from the repo root:
    python scripts/seed_demo.py
Override the demo password first if you do not want the default:
    WORKSPACE_MONITOR_DEMO_PASSWORD='...' python scripts/seed_demo.py
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from api.database import seed_demo_data  # noqa: E402

if __name__ == "__main__":
    inserted = seed_demo_data()
    if inserted:
        print(f"Seeded {inserted} demo users (see api.database for the full dataset).")
    else:
        print("Database already has users; nothing seeded.")
