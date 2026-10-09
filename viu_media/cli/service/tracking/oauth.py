"""Loopback OAuth callback handling for tracker logins."""

import logging
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

_SUCCESS_PAGE = b"""<!doctype html><html><head><meta charset="utf-8">
<title>nviu login</title></head><body style="font-family:sans-serif;padding:3rem">
<h2>Login received.</h2><p>You can close this tab and return to the terminal.</p>
</body></html>"""

_ERROR_PAGE = b"""<!doctype html><html><head><meta charset="utf-8">
<title>nviu login</title></head><body style="font-family:sans-serif;padding:3rem">
<h2>Login failed.</h2><p>Return to the terminal for details.</p>
</body></html>"""


@dataclass(frozen=True)
class OAuthCallback:
    code: Optional[str] = None
    state: Optional[str] = None
    error: Optional[str] = None


def parse_callback(value: str) -> OAuthCallback:
    """Parses a pasted callback URL, query string, or bare authorization code."""
    value = value.strip()
    if not value:
        return OAuthCallback(error="Nothing was pasted.")
    if "code=" not in value and "error=" not in value:
        return OAuthCallback(code=value)
    query = urlparse(value).query if "?" in value else value
    params = parse_qs(query)
    error = params.get("error", [None])[0]
    if error:
        description = (
            params.get("error_description") or params.get("message") or [""]
        )[0]
        return OAuthCallback(error=f"{error}: {description}" if description else error)
    return OAuthCallback(
        code=params.get("code", [None])[0], state=params.get("state", [None])[0]
    )


def wait_for_callback(
    port: int,
    timeout: float = 180,
    cancel: Optional[threading.Event] = None,
) -> Optional[OAuthCallback]:
    """Serves one OAuth redirect on 127.0.0.1:<port>.

    Returns ``None`` on timeout or cancellation. Raises ``OSError`` if the port
    cannot be bound, so callers can fall back to the paste flow.
    """
    received: list[OAuthCallback] = []

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - http.server API
            callback = parse_callback(self.path)
            if not callback.error and (not callback.code or "code=" not in self.path):
                self.send_response(404)
                self.end_headers()
                return
            received.append(callback)
            self.send_response(200 if callback.code else 400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(_SUCCESS_PAGE if callback.code else _ERROR_PAGE)

        def log_message(self, format, *args):
            logger.debug("oauth callback: " + format, *args)

    server = HTTPServer(("127.0.0.1", port), _Handler)
    server.timeout = 0.5
    deadline = time.monotonic() + timeout
    try:
        while not received and time.monotonic() < deadline:
            if cancel and cancel.is_set():
                return None
            server.handle_request()
    finally:
        server.server_close()
    return received[0] if received else None
