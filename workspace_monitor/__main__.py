"""Console entry point: ``workspace-monitor`` runs the Flask app."""

from __future__ import annotations

from workspace_monitor import create_app
from workspace_monitor.config import Settings


def main() -> None:
    settings = Settings.from_env()
    app = create_app(settings)
    app.run(host="127.0.0.1", port=settings.port, debug=False)


if __name__ == "__main__":
    main()
