"""TLS configuration helpers for Redis connections.

Centralizes TLS parameter building from environment variables to avoid
duplication across consumers. All boolean env vars accept "true", "1", "yes"
(case-insensitive).

Usage:
    from shared.config.tls import build_redis_tls_params

    tls_params = build_redis_tls_params()
    client = redis.Redis(host=host, port=port, **tls_params)
"""

import os
import ssl

_TRUTHY_VALUES = ("true", "1", "yes")


def build_redis_tls_params() -> dict:
    """Build Redis TLS connection parameters from environment variables.

    Reads:
        REDIS_TLS_ENABLED: Enable TLS ("true", "1", "yes")
        REDIS_TLS_CERT_REQS: Certificate requirements ("none", "optional", "required")
        REDIS_TLS_CA_CERTS: Path to CA certificate bundle

    Returns:
        Dict of kwargs to pass to redis.Redis() constructor.
        Empty dict if TLS is not enabled.
    """
    tls_enabled = os.environ.get("REDIS_TLS_ENABLED", "false").lower() in _TRUTHY_VALUES
    if not tls_enabled:
        return {}

    cert_reqs_str = os.environ.get("REDIS_TLS_CERT_REQS", "required").lower()
    cert_reqs_map = {
        "none": ssl.CERT_NONE,
        "optional": ssl.CERT_OPTIONAL,
        "required": ssl.CERT_REQUIRED,
    }
    cert_reqs = cert_reqs_map.get(cert_reqs_str, ssl.CERT_REQUIRED)

    params: dict = {
        "ssl": True,
        "ssl_cert_reqs": cert_reqs,
    }
    ca_certs = os.environ.get("REDIS_TLS_CA_CERTS")
    if ca_certs:
        params["ssl_ca_certs"] = ca_certs
    return params


def is_redis_tls_enabled() -> bool:
    """Check if Redis TLS is enabled via env var."""
    return os.environ.get("REDIS_TLS_ENABLED", "false").lower() in _TRUTHY_VALUES
