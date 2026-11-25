"""``KisWitnessHttpClient`` — a single-request-per-call stdlib GET-only HTTP shim over"""

from __future__ import annotations

import http.client
import json
import ssl
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlsplit

from tos_runtime.recon.witness_kis_config import KisWitnessConfig

__all__ = [
    "KisWitnessClientError",
    "KisWitnessConnectionError",
    "KisWitnessHttpClient",
    "KisWitnessTimeoutError",
    "RawGetResponse",
    "build_witness_client",
]


class KisWitnessClientError(Exception):
    """Base class for every error this client itself raises (not a connection/timeout"""


class KisWitnessConnectionError(KisWitnessClientError):
    """The connection could not be established, or was reset mid-request."""


class KisWitnessTimeoutError(KisWitnessClientError):
    """The request timed out waiting for a response."""


@dataclass(frozen=True)
class RawGetResponse:
    """One HTTP GET response, exactly as received — no KIS-specific interpretation."""

    status: int
    json: dict[str, Any] | None
    headers: Mapping[str, str]
    text: str


class KisWitnessHttpClient:
    """Issues exactly one read-only HTTP GET per method call against one configured KIS"""

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
            raise KisWitnessClientError(
                f"KisWitnessHttpClient: unsupported scheme {parts.scheme!r} in rest_base "
                f"{rest_base!r} — only http (test-only) and https are supported"
            )
        if parts.scheme == "http" and not allow_plaintext_for_tests:
            raise KisWitnessClientError(
                "KisWitnessHttpClient: http:// scheme requires "
                "allow_plaintext_for_tests=True"
            )
        if not parts.hostname:
            raise KisWitnessClientError(
                f"KisWitnessHttpClient: rest_base {rest_base!r} has no host"
            )
        self._scheme = parts.scheme
        self._host = parts.hostname
        self._port = parts.port or (443 if parts.scheme == "https" else 80)
        self._timeout_s = request_timeout_s

    def _connection(self) -> http.client.HTTPConnection:
        """A fresh connection for exactly one request — never reused across calls (mirrors"""
        if self._scheme == "https":
            context = ssl.create_default_context()
            return http.client.HTTPSConnection(
                self._host, self._port, timeout=self._timeout_s, context=context
            )
        return http.client.HTTPConnection(
            self._host, self._port, timeout=self._timeout_s
        )

    def get(
        self,
        path: str,
        *,
        headers: Mapping[str, str],
        params: Mapping[str, str],
    ) -> RawGetResponse:
        """Perform exactly one GET round trip. No loop, no resend, anywhere in this method."""
        query = urlencode(params)
        full_path = f"{path}?{query}" if query else path
        connection = self._connection()
        try:
            connection.request("GET", full_path, headers=dict(headers))
            response = connection.getresponse()
            raw = response.read()
            status = response.status
            response_headers = {k.lower(): v for k, v in response.getheaders()}
        except TimeoutError as exc:
            raise KisWitnessTimeoutError(
                f"KisWitnessHttpClient: request to {path} timed out after "
                f"{self._timeout_s}s"
            ) from exc
        except OSError as exc:
            raise KisWitnessConnectionError(
                f"KisWitnessHttpClient: connection to {self._host}:{self._port} failed "
                f"for {path}: {exc}"
            ) from exc
        finally:
            connection.close()

        text = raw.decode("utf-8", errors="replace")
        try:
            candidate = json.loads(text) if text else None
        except json.JSONDecodeError:
            candidate = None
        parsed = candidate if isinstance(candidate, dict) else None
        return RawGetResponse(
            status=status, json=parsed, headers=response_headers, text=text
        )


def build_witness_client(config: KisWitnessConfig) -> KisWitnessHttpClient:
    """The one sanctioned way to build a :class:`KisWitnessHttpClient` for real use"""
    return KisWitnessHttpClient(
        rest_base=config.endpoint_rest_base,
        request_timeout_s=config.request_timeout_s,
        allow_plaintext_for_tests=config.allow_plaintext_for_tests,
    )
