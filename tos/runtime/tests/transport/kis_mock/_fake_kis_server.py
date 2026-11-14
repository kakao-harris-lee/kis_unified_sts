"""A hermetic, ``127.0.0.1``-only fake KIS server (``http.server``) for the client/adapter"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

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
    on_request: Callable[[], None] | None = None


class FakeKisServer:
    """A threaded HTTP server bound to ``127.0.0.1`` with per-path scripted responses."""

    def __init__(self) -> None:
        self._account: tuple[str, str] | None = None
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
        on_request: Callable[[], None] | None = None,
    ) -> None:
        """Script one route."""
        self._routes[path] = _Route(
            status=status,
            body=body,
            delay_s=delay_s,
            reset=reset,
            on_request=on_request,
        )

    def require_account(self, cano: str, acnt_prdt_cd: str) -> None:
        """Reject any order POST body or GET query whose account fields are not exactly"""
        assert len(cano) == 8 and cano.isdigit(), cano
        assert len(acnt_prdt_cd) == 2 and acnt_prdt_cd.isdigit(), acnt_prdt_cd
        self._account = (cano, acnt_prdt_cd)

    def _account_rejected(self, path: str, raw_body: bytes) -> bool:
        if self._account is None:
            return False
        fields: dict[str, Any] = {}
        query = parse_qs(urlsplit(path).query)
        fields.update({k: v[0] for k, v in query.items() if v})
        if raw_body:
            try:
                body = json.loads(raw_body)
            except ValueError:
                body = None
            if isinstance(body, dict):
                fields.update(body)
        if "CANO" not in fields and "ACNT_PRDT_CD" not in fields:
            return False
        return (fields.get("CANO"), fields.get("ACNT_PRDT_CD")) != self._account

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

            def log_message(self, format: str, *_args: Any) -> None:  # noqa: A002
                del format
                return

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                raw_body = self.rfile.read(length) if length else b""
                self._handle("POST", self.path, raw_body)

            def do_GET(self) -> None:  # noqa: N802
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
                if server._account_rejected(path, raw_body):
                    route = _Route(
                        status=200,
                        body={
                            "rt_cd": "1",
                            "msg_cd": "FAKE_INVALID_ACCOUNT",
                            "msg1": "CANO/ACNT_PRDT_CD do not name the expected 8-2 account",
                        },
                    )
                if route is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                if route.on_request is not None:
                    route.on_request()
                if route.delay_s:
                    time.sleep(route.delay_s)
                if route.reset:
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
