"""``KisMockHttpClient`` — a single-request-per-call stdlib HTTP shim over KIS's REST API"""

from __future__ import annotations

import http.client
import json
import ssl
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from tos_runtime.transport.kis_mock.config import KisMockTransportConfig

__all__ = [
    "KisMockClientError",
    "KisMockConnectionError",
    "KisMockHttpClient",
    "KisMockTimeoutError",
    "RawResponse",
    "build_client",
]


class KisMockClientError(Exception):
    """Base class for every error this client itself raises (not a connection/timeout fault —"""


class KisMockConnectionError(KisMockClientError):
    """The connection could not be established, or was reset mid-request."""


class KisMockTimeoutError(KisMockClientError):
    """The request timed out waiting for a response — mapped by the caller to"""


@dataclass(frozen=True)
class RawResponse:
    """One HTTP response, exactly as received — no KIS-specific interpretation."""

    status: int
    json: dict[str, Any] | None
    text: str


class KisMockHttpClient:
    """Issues exactly one HTTP request per method call against one configured KIS REST base."""

    def __init__(
        self,
        *,
        rest_base: str,
        request_timeout_s: float,
        allow_plaintext_for_tests: bool,
    ) -> None:
        """Parse and pin the target host/port/scheme once, at construction."""
        parts = urlsplit(rest_base)
        if parts.scheme not in ("http", "https"):
            raise KisMockClientError(
                f"KisMockHttpClient: unsupported scheme {parts.scheme!r} in rest_base "
                f"{rest_base!r} — only http (test-only) and https are supported"
            )
        if parts.scheme == "http" and not allow_plaintext_for_tests:
            raise KisMockClientError(
                "KisMockHttpClient: http:// scheme requires allow_plaintext_for_tests=True"
            )
        if not parts.hostname:
            raise KisMockClientError(
                f"KisMockHttpClient: rest_base {rest_base!r} has no host"
            )
        self._scheme = parts.scheme
        self._host = parts.hostname
        self._port = parts.port or (443 if parts.scheme == "https" else 80)
        self._timeout_s = request_timeout_s

    def _connection(self) -> http.client.HTTPConnection:
        """A fresh connection for exactly one request — never reused across calls."""
        if self._scheme == "https":
            context = ssl.create_default_context()
            return http.client.HTTPSConnection(
                self._host, self._port, timeout=self._timeout_s, context=context
            )
        return http.client.HTTPConnection(
            self._host, self._port, timeout=self._timeout_s
        )

    def _do_request(
        self, method: str, path: str, *, headers: Mapping[str, str], body: bytes
    ) -> RawResponse:
        """Perform exactly one HTTP round trip. No loop, no resend, anywhere in this method."""
        connection = self._connection()
        try:
            connection.request(method, path, body=body, headers=dict(headers))
            response = connection.getresponse()
            raw = response.read()
            status = response.status
        except TimeoutError as exc:
            raise KisMockTimeoutError(
                f"KisMockHttpClient: request to {path} timed out after {self._timeout_s}s"
            ) from exc
        except OSError as exc:
            raise KisMockConnectionError(
                f"KisMockHttpClient: connection to {self._host}:{self._port} failed for "
                f"{path}: {exc}"
            ) from exc
        finally:
            connection.close()

        text = raw.decode("utf-8", errors="replace")
        parsed: dict[str, Any] | None
        try:
            candidate = json.loads(text) if text else None
        except json.JSONDecodeError:
            candidate = None
        parsed = candidate if isinstance(candidate, dict) else None
        return RawResponse(status=status, json=parsed, text=text)

    def issue_token(
        self, app_key: bytes, app_secret: bytes, *, path: str
    ) -> dict[str, Any]:
        """POST ``path`` (KIS's ``/oauth2/tokenP``) exactly once; return the raw parsed body."""
        body = json.dumps(
            {
                "grant_type": "client_credentials",
                "appkey": app_key.decode("utf-8"),
                "appsecret": app_secret.decode("utf-8"),
            },
            separators=(",", ":"),
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/plain",
            "charset": "UTF-8",
        }
        response = self._do_request("POST", path, headers=headers, body=body)
        if response.json is None:
            raise KisMockClientError(
                f"KisMockHttpClient.issue_token: response body did not parse as a JSON "
                f"object (status={response.status})"
            )
        return response.json

    def post_order(
        self,
        tr_id: str,
        body: bytes,
        *,
        access_token: str,
        app_key: bytes,
        app_secret: bytes,
        path: str,
    ) -> RawResponse:
        """POST ``path`` (KIS's ``order_cash``) exactly once with the given pre-built body bytes."""
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {access_token}",
            "appkey": app_key.decode("utf-8"),
            "appsecret": app_secret.decode("utf-8"),
            "tr_id": tr_id,
            "custtype": "P",
        }
        return self._do_request("POST", path, headers=headers, body=body)

    def get_quote(
        self,
        tr_id: str,
        query: str,
        *,
        access_token: str,
        app_key: bytes,
        app_secret: bytes,
        path: str,
    ) -> RawResponse:
        """GET ``path?query`` (a KIS quotations TR, e.g. ``inquire-price``) exactly once."""
        headers = {
            "authorization": f"Bearer {access_token}",
            "appkey": app_key.decode("utf-8"),
            "appsecret": app_secret.decode("utf-8"),
            "tr_id": tr_id,
            "custtype": "P",
        }
        full_path = f"{path}?{query}" if query else path
        return self._do_request("GET", full_path, headers=headers, body=b"")


def build_client(config: KisMockTransportConfig) -> KisMockHttpClient:
    """The one sanctioned way to build a :class:`KisMockHttpClient` for real use (review F3)."""
    return KisMockHttpClient(
        rest_base=config.endpoint_rest_base,
        request_timeout_s=config.request_timeout_s,
        allow_plaintext_for_tests=config.allow_plaintext_for_tests,
    )
