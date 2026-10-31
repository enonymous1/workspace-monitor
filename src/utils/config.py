"""Frontend configuration. All values are overridable via environment.

API_BASE_URL previously had two different hardcoded values across
the frontend (``127.0.0.1:8000`` in config, ``localhost:8000`` in
every page). There is now exactly one source, and pages must use
``utils.api_client`` instead of redefining it.
"""

import os

API_BASE_URL = os.environ.get("WORKSPACE_MONITOR_API_URL", "http://127.0.0.1:8000/api")
API_TIMEOUT_SECONDS = float(os.environ.get("WORKSPACE_MONITOR_API_TIMEOUT", "10"))
PROJECT_TITLE = "workspace-monitor"
PROJECT_ICON = "🔐"
