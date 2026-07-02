#!/usr/bin/env python3
from __future__ import annotations

import argparse
import http.server
import json
import os
import shutil
import socket
import socketserver
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from archive_tasks import archive_tasks


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "public"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8766
LIVE_REFRESH_MIN_INTERVAL_SECONDS = 3.0


class DashboardPreviewServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class PreviewError(Exception):
    pass


def run_command(args: list[str]) -> None:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    completed = subprocess.run(args, cwd=ROOT, env=env, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
        raise PreviewError(f"command failed: {' '.join(args)}: {detail}")


def prepare_preview_dir(target: Path) -> Path:
    if not PUBLIC_DIR.is_dir():
        raise PreviewError(f"missing public dashboard directory: {PUBLIC_DIR}")

    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    for item in PUBLIC_DIR.iterdir():
        destination = target / item.name
        if item.name == "status":
            continue
        if item.is_dir():
            shutil.copytree(item, destination)
        elif item.is_file():
            shutil.copy2(item, destination)

    run_command(["python3", "scripts/generate_dashboard_status.py", "--output-dir", str(target / "status")])
    return target


def refresh_status(directory: Path) -> None:
    run_command(["python3", "scripts/generate_dashboard_status.py", "--output-dir", str(directory / "status")])


def make_handler(
    directory: Path, live: bool, allow_archive: bool = False
) -> type[http.server.SimpleHTTPRequestHandler]:
    refresh_lock = threading.Lock()
    last_refresh_at = 0.0

    class DashboardPreviewHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)

        def end_headers(self) -> None:
            # Never let the browser cache the dashboard assets/snapshots, so UI changes
            # (and live status) always reach the page without a hard refresh.
            self.send_header("Cache-Control", "no-store, max-age=0")
            super().end_headers()

        def _send_json(self, payload: dict, code: int = 200) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            # Capability probe: the dashboard shows archive controls only when this
            # returns archive:true (i.e. local server started with --allow-archive).
            # On static Vercel there is no such endpoint, so controls stay hidden.
            if self.path.split("?", 1)[0] == "/api/capabilities":
                self._send_json({"archive": bool(allow_archive)})
                return
            if live and self.path.startswith("/status/"):
                with refresh_lock:
                    nonlocal last_refresh_at
                    now = time.monotonic()
                    should_refresh = now - last_refresh_at >= LIVE_REFRESH_MIN_INTERVAL_SECONDS
                    try:
                        if should_refresh:
                            refresh_status(directory)
                            last_refresh_at = time.monotonic()
                    except PreviewError as exc:
                        self.send_error(500, str(exc))
                        return
            super().do_GET()

        def do_POST(self) -> None:
            if self.path.split("?", 1)[0] != "/api/archive":
                self.send_error(404, "not found")
                return
            if not allow_archive:
                self._send_json(
                    {"error": "archive is disabled; restart the server with --allow-archive"},
                    code=403,
                )
                return
            try:
                length = int(self.headers.get("Content-Length", 0) or 0)
                raw = self.rfile.read(length) if length else b"{}"
                payload = json.loads(raw or b"{}")
                task_ids = payload.get("task_ids", [])
                if not isinstance(task_ids, list):
                    raise ValueError("task_ids must be a list")
            except (ValueError, json.JSONDecodeError) as exc:
                self._send_json({"error": f"bad request: {exc}"}, code=400)
                return

            result = archive_tasks([str(task_id) for task_id in task_ids])
            # Regenerate status so the dashboard reflects the change on its next poll.
            try:
                refresh_status(directory)
            except PreviewError:
                pass
            self._send_json(result)

    return DashboardPreviewHandler


def serve(
    directory: Path, host: str, port: int, live: bool = False, allow_archive: bool = False
) -> None:
    handler = make_handler(directory, live, allow_archive)
    with DashboardPreviewServer((host, port), handler) as server:
        suffix = "?live=1" if live else ""
        print(f"dashboard preview: http://{host}:{port}/{suffix}")
        print(f"serving temporary directory: {directory}")
        if live:
            print("live mode: regenerating status snapshots on /status/*.json requests")
        if allow_archive:
            print("archive mode: POST /api/archive can move .queue/done tasks to .queue/archive/done")
        server.serve_forever()


def choose_available_port(host: str, preferred_port: int) -> int:
    for port in range(preferred_port, preferred_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((host, port))
            except OSError:
                continue
            return port
    raise PreviewError(f"no available port from {preferred_port} to {preferred_port + 49}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate and serve a local read-only dashboard preview.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Bind host")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Bind port")
    parser.add_argument("--output-dir", help="Use this preview directory instead of a temporary directory")
    parser.add_argument("--no-server", action="store_true", help="Prepare preview files and exit without serving")
    parser.add_argument("--live", action="store_true", help="Regenerate status snapshots whenever status JSON is requested")
    parser.add_argument(
        "--allow-archive",
        action="store_true",
        help="Enable the local-only POST /api/archive endpoint (moves .queue/done tasks to .queue/archive/done)",
    )
    args = parser.parse_args()
    port = choose_available_port(args.host, args.port)
    if port != args.port:
        print(f"port {args.port} is busy; using {port}")

    try:
        if args.output_dir:
            preview_dir = prepare_preview_dir(Path(args.output_dir).resolve())
            if args.no_server:
                print(f"dashboard preview prepared: {preview_dir}")
                return 0
            serve(preview_dir, args.host, port, live=args.live, allow_archive=args.allow_archive)
            return 0

        with tempfile.TemporaryDirectory(prefix="agentic-dashboard-preview-") as temp_name:
            preview_dir = prepare_preview_dir(Path(temp_name))
            if args.no_server:
                print(f"dashboard preview prepared: {preview_dir}")
                return 0
            serve(preview_dir, args.host, port, live=args.live, allow_archive=args.allow_archive)
    except (KeyboardInterrupt, PreviewError) as exc:
        if isinstance(exc, KeyboardInterrupt):
            print("\ndashboard preview stopped")
            return 0
        print(f"error: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
