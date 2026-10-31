"""Seed the deterministic demo dataset (idempotent).

Usage, from the repo root:
    python scripts/seed_demo.py
Override the demo password first if you do not want the default:
    WORKSPACE_MONITOR_DEMO_PASSWORD='...' python scripts/seed_demo.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from workspace_monitor.database import seed_demo_data


def main() -> None:
    inserted = seed_demo_data()
    print(f"Seeded {inserted} demo users (0 = database already had users).")


if __name__ == "__main__":
    main()
