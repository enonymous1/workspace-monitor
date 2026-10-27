"""Launch the FastAPI backend and the Streamlit frontend together.

v2 fixes v1's launcher bugs: it waits for the backend's ``/health``
endpoint instead of sleeping a fixed 2 seconds, and Ctrl+C now
terminates both child processes (v1 left them orphaned despite its
comment claiming otherwise). Ports are overridable via
``WORKSPACE_MONITOR_API_PORT`` / ``WORKSPACE_MONITOR_FRONTEND_PORT``.

Usage:  python run_app.py
Then:   backend  http://127.0.0.1:8000/docs
        frontend http://127.0.0.1:8501
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API_PORT = int(os.environ.get("WORKSPACE_MONITOR_API_PORT", "8000"))
FRONTEND_PORT = int(os.environ.get("WORKSPACE_MONITOR_FRONTEND_PORT", "8501"))
API_HOST = "127.0.0.1"


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex((API_HOST, port)) == 0


def venv_executable(name: str) -> Path:
    """The venv's executable, Windows (.venv/Scripts) or POSIX (.venv/bin)."""
    scripts = ROOT / ".venv" / "Scripts" / name
    if scripts.exists():
        return scripts
    return ROOT / ".venv" / "bin" / name


def wait_for_health(timeout_seconds: float = 30.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://{API_HOST}:{API_PORT}/health", timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def terminate(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def run_workspace_app() -> None:
    print("🚀 Starting ss-workspaceMonitor System...")
    children: list[subprocess.Popen] = []
    try:
        if is_port_in_use(API_PORT):
            print(f"⚠️  Port {API_PORT} (Backend) is already in use. Skipping backend launch.")
        else:
            python = venv_executable("python.exe" if os.name == "nt" else "python")
            python = python if python.exists() else Path(sys.executable)
            print(f"✅ Launching FastAPI Backend on port {API_PORT}...")
            children.append(
                subprocess.Popen(
                    [str(python), "-m", "uvicorn", "src.api.main:app", "--port", str(API_PORT)],
                    cwd=ROOT,
                )
            )
            if not wait_for_health():
                print("⚠️  Backend did not report healthy within 30s; check its output above.")
        if is_port_in_use(FRONTEND_PORT):
            print(f"⚠️  Port {FRONTEND_PORT} (Frontend) is already in use. Skipping frontend launch.")
        else:
            streamlit = venv_executable("streamlit.exe" if os.name == "nt" else "streamlit")
            if not streamlit.exists():
                print("⚠️  Streamlit executable not found in .venv; skipping frontend launch.")
            else:
                print(f"✅ Launching Streamlit Frontend on port {FRONTEND_PORT}...")
                children.append(
                    subprocess.Popen(
                        [str(streamlit), "run", "src/frontend/app.py", "--server.port", str(FRONTEND_PORT)],
                        cwd=ROOT,
                    )
                )
        print(f"\n🔗 Backend: http://localhost:{API_PORT}/docs")
        print(f"🔗 Frontend: http://localhost:{FRONTEND_PORT}")
        print("\n(System is running. Press Ctrl+C to terminate all processes)")
        while True:
            time.sleep(1)
            if children and all(child.poll() is not None for child in children):
                print("All child processes exited; shutting down.")
                break
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    finally:
        for child in children:
            terminate(child)


if __name__ == "__main__":
    # Reap children cleanly on SIGTERM as well as Ctrl+C.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    run_workspace_app()
