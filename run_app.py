"""Run workspace-monitor locally (Flask build).

    python run_app.py

Listens on 127.0.0.1:5000 by default (override with
``WORKSPACE_MONITOR_PORT``). Set
``WORKSPACE_MONITOR_SECRET_KEY`` for stable logins, and seed
the demo dataset first with ``python scripts/seed_demo.py``
(auto-seed is opt-in via ``WORKSPACE_MONITOR_AUTO_SEED=1``).
This is the development server; see README Deployment for
running behind a real WSGI server and reverse proxy.
"""

from __future__ import annotations

from workspace_monitor.__main__ import main

if __name__ == "__main__":
    main()
