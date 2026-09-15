"""``KisMockHttpClient`` — a single-request-per-call stdlib HTTP shim over KIS's REST API
(plan §2 결정 1/2).

**stdlib only.** ``http.client`` + ``ssl.create_default_context()`` — no ``requests``/``httpx``
(design D1.3 "서드파티 0"). Plaintext (``http.client.HTTPConnection``) is admitted ONLY when the
caller explicitly opts in (:class:`~tos_runtime.transport.kis_mock.config.KisMockTransportConfig
.allow_plaintext_for_tests`) — every other path uses ``HTTPSConnection`` with a default TLS
context.

**Exactly one request per method call — no loop over it anywhere in this module.** A resend is a
new *attempt* at the adapter layer (design #34 §5.4), never a retry this client performs on its
own; :func:`tos_runtime.transport.kis_mock.adapter`'s own negative-grep test scans this module's
source for a loop/retry primitive to prove it, alongside its own.

**Fault mapping (plan §2 결정 2).** A connection failure or reset raises
:class:`KisMockConnectionError`; a socket timeout raises :class:`KisMockTimeoutError`. Neither
is caught here — the caller (the adapter) maps both to the honest, non-rejecting
``EgressResultKind`` the design calls for (``UNKNOWN``/``TIMEOUT`` respectively). A well-formed
HTTP response (any status code) is returned as a plain :class:`RawResponse` — this client never
interprets ``rt_cd``/``msg_cd`` itself; that is the adapter's job (RFC-002 §10.8:739, broker
behaviour stays behind the adapter boundary).

**One sanctioned construction path (review disposition F3).** :func:`build_client` is the ONLY
way production code (the adapter, T2's compose root) should ever obtain a
:class:`KisMockHttpClient` — it derives every constructor argument from a validated
:class:`~tos_runtime.transport.kis_mock.config.KisMockTransportConfig`, never from a
caller-supplied URL. The bare :class:`KisMockHttpClient` constructor stays a public, directly
testable primitive (this module's own test suite constructs it against a fake server's own
dynamically-assigned port, which is not itself the config's ``endpoint_rest_base``), but nothing
outside this package's tests should call it directly.

Firewall: stdlib (``http.client``, ``json``, ``ssl``, ``socket``, ``dataclasses``,
``urllib.parse``) + this package's own sibling :mod:`~tos_runtime.transport.kis_mock.config`
(for :func:`build_client`'s type) — no ``tos`` import, no ``os.environ``.
"""

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
    """Base class for every error this client itself raises (not a connection/timeout fault —
    see the two subclasses below for those)."""


class KisMockConnectionError(KisMockClientError):
    """The connection could not be established, or was reset mid-request.

    Never retried by this client — the caller maps this to ``EgressResultKind.UNKNOWN`` (a
    missing acknowledgement is not a non-acceptance, RFC-005 §11:322-323).
    """


class KisMockTimeoutError(KisMockClientError):
    """The request timed out waiting for a response — mapped by the caller to
    ``EgressResultKind.TIMEOUT``."""


@dataclass(frozen=True)
class RawResponse:
    """One HTTP response, exactly as received — no KIS-specific interpretation.

    ``json`` is ``None`` when the body is empty or fails to parse as JSON (the caller treats
    that as ``UNKNOWN`` — a malformed body is not evidence of rejection).
    """

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
        """Parse and pin the target host/port/scheme once, at construction.

        Args:
            rest_base: The KIS REST base URL (``https://host:port`` normally; ``http://...``
                only when ``allow_plaintext_for_tests`` is true).
            request_timeout_s: The per-request socket timeout, in seconds.
            allow_plaintext_for_tests: Whether an ``http://`` scheme is admitted (test-only
                escape hatch — the config loader already refuses this combination for a
                production config, this is the client's own independent check).

        Raises:
            KisMockClientError: The scheme is neither ``http`` nor ``https``, or is ``http``
                without ``allow_plaintext_for_tests``.
        """
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
            # socket.timeout is a TimeoutError alias as of Python 3.10 — one except clause
            # catches both a raw socket timeout and the stdlib's own alias.
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
        """POST ``path`` (KIS's ``/oauth2/tokenP``) exactly once; return the raw parsed body.

        The adapter (never this client) decides whether the response is usable — this method
        performs no retry and interprets nothing beyond "did the body parse as JSON".

        Args:
            app_key: The KIS app key, as raw bytes (never logged — this method does not
                stringify it into any exception message).
            app_secret: The KIS app secret, as raw bytes (same non-disclosure discipline).
            path: The token endpoint's path (``KisMockTransportConfig.token_path``).

        Returns:
            The parsed JSON response body.

        Raises:
            KisMockConnectionError: The connection failed or was reset.
            KisMockTimeoutError: The request timed out.
            KisMockClientError: The response body did not parse as a JSON object.
        """
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
        """POST ``path`` (KIS's ``order_cash``) exactly once with the given pre-built body bytes.

        Args:
            tr_id: The KIS transaction id (``tr_id_buy``/``tr_id_sell`` — 'V'-prefixed only,
                enforced by the config loader).
            body: The exact, already-digest-verified request body bytes.
            access_token: The bearer token string (never logged by this method).
            app_key: The KIS app key bytes (sent as a header, per KIS's own convention — every
                order call carries appkey/appsecret alongside the bearer token, not only token
                issuance).
            app_secret: The KIS app secret bytes (same non-disclosure discipline).
            path: The order endpoint's path (``KisMockTransportConfig.order_path``).

        Returns:
            The raw response — the adapter maps it to an ``EgressResultKind``.

        Raises:
            KisMockConnectionError: The connection failed or was reset.
            KisMockTimeoutError: The request timed out.
        """
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {access_token}",
            "appkey": app_key.decode("utf-8"),
            "appsecret": app_secret.decode("utf-8"),
            "tr_id": tr_id,
            "custtype": "P",
        }
        return self._do_request("POST", path, headers=headers, body=body)


def build_client(config: KisMockTransportConfig) -> KisMockHttpClient:
    """The one sanctioned way to build a :class:`KisMockHttpClient` for real use (review F3).

    Every argument comes from ``config`` — never a caller-supplied URL — so a client can never
    be pointed anywhere the config loader's own host-seal check
    (:func:`tos_runtime.transport.kis_mock.config.load_kis_mock_transport_config`) did not
    already validate.

    Args:
        config: The fail-closed-loaded config.

    Returns:
        A client targeting exactly ``config.endpoint_rest_base``.
    """
    return KisMockHttpClient(
        rest_base=config.endpoint_rest_base,
        request_timeout_s=config.request_timeout_s,
        allow_plaintext_for_tests=config.allow_plaintext_for_tests,
    )
