"""Shared KIS auth stand-in for the broker-probe test battery.

Seven probe test modules carried a byte-identical copy of ``_StubAuth`` and of
the ``shared.kis.auth.KISAuthManager`` monkeypatch. They live here so the auth
seam those probes depend on is described in one place.
"""

from __future__ import annotations

import pytest


class StubAuth:
    """``KISAuthManager`` stand-in that yields headers without a token round-trip."""

    def get_auth_headers(self) -> dict[str, str]:
        return {"authorization": "Bearer stub"}


def install_stub_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point ``shared.kis.auth.KISAuthManager`` at :class:`StubAuth`."""
    monkeypatch.setattr(
        "shared.kis.auth.KISAuthManager", lambda *a, **k: StubAuth(), raising=True
    )
