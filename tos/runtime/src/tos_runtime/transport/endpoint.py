"""One normalizer for every broker-host comparison (#932 final review MEDIUM)."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

__all__ = [
    "EndpointOrigin",
    "EndpointOriginError",
    "endpoint_origin",
    "real_host_problem",
]

_DEFAULT_PORTS = {"https": 443, "http": 80}
_HOSTNAME = re.compile(
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*"
)
_URL_CHARS = re.compile(r"[\x21-\x7e]+")


class EndpointOriginError(ValueError):
    """A ``rest_base`` that cannot be reduced to one honest ``(scheme, host, port)``."""


@dataclass(frozen=True)
class EndpointOrigin:
    """The normalized origin a client connects to: lowercase scheme and host, the host's one"""

    scheme: str
    host: str
    port: int


def endpoint_origin(rest_base: str) -> EndpointOrigin:
    """Normalize ``rest_base`` to its :class:`EndpointOrigin`."""
    if not isinstance(rest_base, str) or not _URL_CHARS.fullmatch(rest_base):
        raise EndpointOriginError(
            f"rest_base {rest_base!r} is empty or carries whitespace / control / non-ASCII "
            "characters"
        )
    parts = urlsplit(rest_base)
    scheme = parts.scheme.lower()
    if scheme not in _DEFAULT_PORTS:
        raise EndpointOriginError(
            f"rest_base {rest_base!r} has unsupported scheme {parts.scheme!r}"
        )
    if "@" in parts.netloc:
        raise EndpointOriginError(f"rest_base {rest_base!r} carries userinfo")
    if "?" in rest_base or "#" in rest_base:
        raise EndpointOriginError(
            f"rest_base {rest_base!r} carries a query or fragment"
        )
    if parts.path not in ("", "/"):
        raise EndpointOriginError(f"rest_base {rest_base!r} carries a path")
    host = parts.hostname
    if not host:
        raise EndpointOriginError(f"rest_base {rest_base!r} has no host")
    if "[" in parts.netloc:
        try:
            host = ipaddress.IPv6Address(host).compressed
        except ValueError as exc:
            raise EndpointOriginError(
                f"rest_base {rest_base!r} has a bad IPv6 host"
            ) from exc
    else:
        if host.endswith("."):
            host = host[:-1]
        if not _HOSTNAME.fullmatch(host):
            raise EndpointOriginError(
                f"rest_base {rest_base!r} host {host!r} is not a hostname"
            )
    try:
        port = parts.port
    except ValueError as exc:
        raise EndpointOriginError(
            f"rest_base {rest_base!r} has an invalid port"
        ) from exc
    return EndpointOrigin(
        scheme, host, _DEFAULT_PORTS[scheme] if port is None else port
    )


def real_host_problem(
    endpoint_rest_base: str,
    *,
    instance_mock_rest_base: str,
    instance_real_rest_base: str,
) -> str | None:
    """The MOCK-only seals' REAL-host exclusion, on normalized origins: why"""
    try:
        endpoint = endpoint_origin(endpoint_rest_base)
        mock = endpoint_origin(instance_mock_rest_base)
        real = endpoint_origin(instance_real_rest_base)
    except EndpointOriginError as exc:
        return (
            f"{exc} — a host that cannot be normalized cannot be proven not to be REAL"
        )
    if mock.host == real.host:
        return (
            f"instance_mock_rest_base {instance_mock_rest_base!r} and instance_real_rest_base "
            f"{instance_real_rest_base!r} must differ, but both name the REAL host {real.host!r} — a caller that "
            "cannot distinguish the two instance facts cannot honestly exclude the real host"
        )
    if endpoint.host == real.host:
        return (
            f"endpoint_rest_base={endpoint_rest_base!r} equals the INSTANCE REAL_PROD document's "
            f"own host {real.host!r} — a MOCK-only adapter refuses to boot "
            "against a real host under any spelling"
        )
    return None
