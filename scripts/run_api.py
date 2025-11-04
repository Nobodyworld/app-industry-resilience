"""Launch the Idiot Index API service using the bundled lightweight server."""

from __future__ import annotations

try:
    from scripts import _bootstrap  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - allow `python scripts/run_api.py`
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts import _bootstrap  # noqa: F401

import argparse
import os
import socket
from socketserver import ThreadingMixIn
from typing import Sequence

from wsgiref.simple_server import WSGIServer, make_server

from src.interfaces.api.app import app


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.getenv("API_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("API_PORT", "9000")))
    parser.add_argument("--reload", action="store_true", default=_env_flag("API_RELOAD"))
    parser.add_argument("--workers", type=int, default=int(os.getenv("API_WORKERS", "1")))
    parser.add_argument("--log-level", default=os.getenv("API_LOG_LEVEL", "info"))
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    if args.reload:
        print("[idiot-index] Hot reload is not supported; ignoring --reload flag.")
    if args.workers != 1:
        print("[idiot-index] Multi-worker mode is not supported; forcing workers=1.")
    print(f"[idiot-index] Log level set to {args.log_level}")

    class _ThreadingWSGIServer(ThreadingMixIn, WSGIServer):  # pragma: no cover - exercised via CLI
        daemon_threads = True

    with make_server(args.host, args.port, app, server_class=_ThreadingWSGIServer) as server:
        server_address = server.server_address
        if isinstance(server_address, tuple) and len(server_address) >= 2:
            host, port = server_address[0], server_address[1]
        else:
            host, port = "localhost", args.port
        # Ensure host and port are strings
        host = host.decode() if isinstance(host, bytes) else str(host)
        port = port if isinstance(port, int) else int(port)
        if host in {"0.0.0.0", "::"}:
            try:
                host = socket.gethostbyname(socket.gethostname())
            except OSError:
                host = "localhost"
        print(f"[idiot-index] Serving API on http://{host}:{port}")
        print(f"[idiot-index] Metrics available at http://{host}:{port}/metrics")
        try:
            server.serve_forever()
        except KeyboardInterrupt:  # pragma: no cover - CLI convenience
            print("[idiot-index] Shutting down")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())

