"""Tiny HTTP server for uptime monitors / hosting platforms (standard library only)."""
from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import config
from stats import stats

log = logging.getLogger(__name__)


class _Handler(BaseHTTPRequestHandler):
    def _respond(self, send_body: bool) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/":
            body, ctype, code = b"Bot is alive", "text/plain; charset=utf-8", 200
        elif path == "/health":
            body = json.dumps(stats.snapshot()).encode()
            ctype, code = "application/json", 200
        else:
            body, ctype, code = b"Not found", "text/plain; charset=utf-8", 404

        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if send_body:
            self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (http.server naming)
        self._respond(True)

    def do_HEAD(self) -> None:  # noqa: N802 - uptime monitors often use HEAD
        self._respond(False)

    def log_message(self, format, *args) -> None:  # silence per-request logging
        pass


def start_keepalive(port: int | None = None) -> ThreadingHTTPServer | None:
    """Serve `/` and `/health` on a background daemon thread."""
    port = config.PORT if port is None else port
    try:
        server = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
    except OSError as exc:
        log.error("Keepalive server could not start on port %s: %s", port, exc)
        return None
    threading.Thread(target=server.serve_forever, name="keepalive", daemon=True).start()
    return server
