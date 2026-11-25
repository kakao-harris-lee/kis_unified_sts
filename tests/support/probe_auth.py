"""Shared KIS auth stand-in for the broker-probe test battery."""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

DEFAULT_LIFE_S = 86400.0


class StubAuth:
    """``KISAuthManager`` stand-in that yields headers without a token round-trip.

    It keeps the one piece of state its callers read: when the token it handed
    out expires. ``get_auth_headers`` issues a new one whenever the current one
    is inside the refresh buffer, exactly as the real manager does, and counts
    the issues so a test can see one happen.
    """

    def __init__(self, *, life_s: float = DEFAULT_LIFE_S) -> None:
        self.config = SimpleNamespace(token_expiry_buffer_seconds=600)
        self.life_s = life_s
        self.issues = 0
        self._expires_at = 0.0

    @property
    def token_expires_at(self) -> float:
        return self._expires_at

    def invalidate(self) -> None:
        self._expires_at = 0.0

    def get_auth_headers(self) -> dict[str, str]:
        if self._expires_at - time.time() <= self.config.token_expiry_buffer_seconds:
            self.issues += 1
            self._expires_at = time.time() + self.life_s
        return {"authorization": "Bearer stub"}


def install_stub_auth(
    monkeypatch: pytest.MonkeyPatch, *, life_s: float = DEFAULT_LIFE_S
) -> StubAuth:
    """Point ``shared.kis.auth.KISAuthManager`` at one :class:`StubAuth`."""
    stub = StubAuth(life_s=life_s)
    monkeypatch.setattr(
        "shared.kis.auth.KISAuthManager", lambda *a, **k: stub, raising=True
    )
    return stub
