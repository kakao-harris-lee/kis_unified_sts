"""``KisWitnessHttpClient`` — a single-request-per-call stdlib GET-only HTTP shim over
KIS's REST API (W3 lane).

**stdlib only**, mirroring :mod:`tos_runtime.transport.kis_mock.client`'s own construction
exactly (``http.client`` + ``ssl.create_default_context()`` — no ``requests``/``httpx``):
this module is that client's read-only sibling, GET instead of POST, with one addition the
order client does not need — **response headers are returned**, because the KIS
continuation protocol's ``tr_cont`` signal travels in a response header on at least one
balance TR (measured:
``docs/broker-profiles/evidence/2026-09-11-p02-t3-campaign/P-BAL-20260911T002427Z.json``
``observations[].tr_cont_response`` / ``tools/broker_probes/probes_balance.py``'s own
``_get()``, which this method's shape mirrors).

**Exactly one request per method call — no loop, no retry, anywhere in this module.** The
continuation WALK (multiple GETs) lives one layer up, in
:mod:`tos_runtime.recon.witness_kis` — this client only ever issues the one HTTP round trip
it is asked for, same discipline as
:meth:`tos_runtime.transport.kis_mock.client.KisMockHttpClient._do_request`.

**Fault mapping.** A connection failure raises :class:`KisWitnessConnectionError`; a socket
timeout raises :class:`KisWitnessTimeoutError`. Neither is caught here — the caller
(:mod:`tos_runtime.recon.witness_kis`) maps both to :class:`~tos_runtime.recon.ports
.WitnessUnavailable` (an unanswerable witness, never a silently empty snapshot — ports.py's
own contract).

Firewall (RUNTIME scope R1): stdlib (``http.client``, ``json``, ``ssl``, ``urllib.parse``)
+ this package's own sibling :mod:`~tos_runtime.recon.witness_kis_config` — no ``tos``
import, no ``os.environ``.
"""

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
    """Base class for every error this client itself raises (not a connection/timeout
    fault — see the two subclasses below)."""


class KisWitnessConnectionError(KisWitnessClientError):
    """The connection could not be established, or was reset mid-request."""


class KisWitnessTimeoutError(KisWitnessClientError):
    """The request timed out waiting for a response."""


@dataclass(frozen=True)
class RawGetResponse:
    """One HTTP GET response, exactly as received — no KIS-specific interpretation.

    ``headers`` is included (unlike a plain balance/order interpretation would need)
    because the ``tr_cont`` continuation signal travels there on at least one TR (module
    docstring) — dropping headers, the way
    :meth:`tos_runtime.transport.kis_mock.client.KisMockHttpClient` does not need to avoid,
    would make a broker-signalled continuation invisible to the caller.
    """

    status: int
    json: dict[str, Any] | None
    headers: Mapping[str, str]
    text: str


class KisWitnessHttpClient:
    """Issues exactly one read-only HTTP GET per method call against one configured KIS
    REST base (module docstring)."""

    def __init__(
        self,
        *,
        rest_base: str,
        request_timeout_s: float,
        allow_plaintext_for_tests: bool,
    ) -> None:
        """Parse and pin the target host/port/scheme once, at construction.

        Raises:
            KisWitnessClientError: The scheme is neither ``http`` nor ``https``, or is
                ``http`` without ``allow_plaintext_for_tests``, or the host is missing.
        """
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
        """A fresh connection for exactly one request — never reused across calls (mirrors
        ``kis_mock/client.py``'s own ``_connection``)."""
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
        """Perform exactly one GET round trip. No loop, no resend, anywhere in this method.

        Args:
            path: The URL path (``KisWitnessConfig.balance_path`` /
                ``order_inquiry_path``).
            headers: Request headers — the caller sets ``authorization``/``appkey``/
                ``appsecret``/``tr_id``/``tr_cont``/``custtype``, this method adds none of
                its own (mirrors ``kis_mock/client.py``'s own separation of concerns: this
                client interprets nothing, it only transports).
            params: Query parameters, url-encoded onto ``path``.

        Returns:
            The raw response, headers included (module docstring).

        Raises:
            KisWitnessConnectionError: The connection failed or was reset.
            KisWitnessTimeoutError: The request timed out.
        """
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
    """The one sanctioned way to build a :class:`KisWitnessHttpClient` for real use
    (mirrors ``kis_mock/client.py``'s ``build_client`` — review disposition F3's
    "one sanctioned construction path" pattern).

    Every argument comes from ``config`` — never a caller-supplied URL — so a client can
    never be pointed anywhere ``load_kis_witness_config``'s own host-seal check did not
    already validate.
    """
    return KisWitnessHttpClient(
        rest_base=config.endpoint_rest_base,
        request_timeout_s=config.request_timeout_s,
        allow_plaintext_for_tests=config.allow_plaintext_for_tests,
    )
