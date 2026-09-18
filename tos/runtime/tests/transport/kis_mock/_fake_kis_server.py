"""A hermetic, ``127.0.0.1``-only fake KIS server (``http.server``) for the client/adapter
suites (plan §4 슬라이스 T1). No third-party dependency; stdlib only.

Records every request it receives (method, path, headers, body) so a test can assert exactly
how many requests were made and inspect their contents (e.g. "the seal digest never appears on
the wire", "the app secret never appears in a header").
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

__all__ = ["FakeKisServer", "RecordedRequest"]


@dataclass(frozen=True)
class RecordedRequest:
    method: str
    path: str
    headers: dict[str, str]
    body: bytes


@dataclass
class _Route:
    status: int
    body: dict[str, Any] | None
    delay_s: float = 0.0
    reset: bool = False


class FakeKisServer:
    """A threaded HTTP server bound to ``127.0.0.1`` with per-path scripted responses.

    Handles both POST (order/token) and GET (quote) requests. A GET route is matched by its
    FULL path, query string included (``set_response("/…/inquire-price?FID_INPUT_ISCD=005930",
    ...)``) — a test that wants to distinguish two quote calls scripts two distinct full paths,
    the same way it would script two distinct POST bodies via two separate assertions.

    Usage::

        server = FakeKisServer()
        server.set_response("/oauth2/tokenP", status=200, body={...})
        server.start()
        ...
        server.stop()
    """

    def __init__(self) -> None:
        self._requests: list[RecordedRequest] = []
        self._routes: dict[str, _Route] = {}
        self._lock = threading.Lock()
        handler = self._make_handler()
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._thread: threading.Thread | None = None

    @property
    def rest_base(self) -> str:
        host, port = self._httpd.server_address[:2]
        assert isinstance(host, str), f"expected a str host, got {type(host)!r}"
        return f"http://{host}:{port}"

    def set_response(
        self,
        path: str,
        *,
        status: int,
        body: dict[str, Any] | None,
        delay_s: float = 0.0,
        reset: bool = False,
    ) -> None:
        self._routes[path] = _Route(
            status=status, body=body, delay_s=delay_s, reset=reset
        )

    def requests_for(self, path: str) -> list[RecordedRequest]:
        with self._lock:
            return [r for r in self._requests if r.path == path]

    @property
    def all_requests(self) -> list[RecordedRequest]:
        with self._lock:
            return list(self._requests)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _make_handler(self) -> Callable[..., BaseHTTPRequestHandler]:
        server = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            # Overrides BaseHTTPRequestHandler.log_message (fixed signature) to silence
            # per-request stderr logging in the test run.
            def log_message(self, format: str, *_args: Any) -> None:  # noqa: A002
                del format
                return

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                raw_body = self.rfile.read(length) if length else b""
                self._handle("POST", self.path, raw_body)

            def do_GET(self) -> None:  # noqa: N802
                # A quote GET carries no body — recorded with an empty one for symmetry with
                # RecordedRequest's shape. Route lookup, like recording, uses the FULL path
                # (query string included): a quote adapter's own routing distinguishes requests
                # by their query string (e.g. a different FID_INPUT_ISCD), unlike the order
                # transport's POST routes, which never carry one.
                self._handle("GET", self.path, b"")

            def _handle(self, method: str, path: str, raw_body: bytes) -> None:
                route = server._routes.get(path)
                with server._lock:
                    server._requests.append(
                        RecordedRequest(
                            method=method,
                            path=path,
                            headers={k.lower(): v for k, v in self.headers.items()},
                            body=raw_body,
                        )
                    )
                if route is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                if route.delay_s:
                    time.sleep(route.delay_s)
                if route.reset:
                    # Force a connection reset — no response, abort the socket.
                    self.close_connection = True
                    try:
                        self.connection.shutdown(1)
                    except OSError:
                        pass
                    return
                payload = (
                    b""
                    if route.body is None
                    else json.dumps(route.body).encode("utf-8")
                )
                self.send_response(route.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                if payload:
                    self.wfile.write(payload)

        return Handler
