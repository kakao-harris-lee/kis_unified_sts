"""A hermetic, ``127.0.0.1``-only fake KIS GET server (``http.server``) for the W3"""

from __future__ import annotations

import json
import threading
from collections import deque
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

__all__ = ["FakeKisGetServer", "GetResponseSpec", "RecordedGetRequest"]


@dataclass(frozen=True)
class RecordedGetRequest:
    path: str
    query: dict[str, str]
    headers: dict[str, str]


@dataclass(frozen=True)
class GetResponseSpec:
    status: int
    body: dict[str, Any] | None
    headers: dict[str, str] = field(default_factory=dict)


class FakeKisGetServer:
    """A threaded HTTP server bound to ``127.0.0.1`` serving a per-path QUEUE of scripted"""

    def __init__(self) -> None:
        self._requests: list[RecordedGetRequest] = []
        self._queues: dict[str, deque[GetResponseSpec]] = {}
        self._lock = threading.Lock()
        handler = self._make_handler()
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._thread: threading.Thread | None = None

    @property
    def rest_base(self) -> str:
        host, port = self._httpd.server_address[:2]
        assert isinstance(host, str), f"expected a str host, got {type(host)!r}"
        return f"http://{host}:{port}"

    def queue_response(
        self,
        path: str,
        *,
        status: int,
        body: dict[str, Any] | None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._queues.setdefault(path, deque()).append(
            GetResponseSpec(status=status, body=body, headers=dict(headers or {}))
        )

    def requests_for(self, path: str) -> list[RecordedGetRequest]:
        with self._lock:
            return [r for r in self._requests if r.path == path]

    @property
    def all_requests(self) -> list[RecordedGetRequest]:
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

    def _make_handler(self) -> Any:
        server = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, format: str, *_args: Any) -> None:  # noqa: A002
                del format
                return

            def do_GET(self) -> None:  # noqa: N802
                split = urlsplit(self.path)
                query = {k: v[0] for k, v in parse_qs(split.query).items()}
                with server._lock:
                    server._requests.append(
                        RecordedGetRequest(
                            path=split.path,
                            query=query,
                            headers={k.lower(): v for k, v in self.headers.items()},
                        )
                    )
                    queue = server._queues.get(split.path)
                    spec = queue.popleft() if queue else None
                if spec is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                payload = (
                    b"" if spec.body is None else json.dumps(spec.body).encode("utf-8")
                )
                self.send_response(spec.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                for name, value in spec.headers.items():
                    self.send_header(name, value)
                self.end_headers()
                if payload:
                    self.wfile.write(payload)

        return Handler
