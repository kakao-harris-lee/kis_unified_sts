"""Shared fakes for the ``KisStockBrokerWitness`` test suite."""

from __future__ import annotations

__all__ = ["FakeKstDateSource", "FakeTokenSession", "RaisingTokenSession"]


class FakeTokenSession:
    """A minimal :class:`~tos_runtime.recon.witness_kis.KisWitnessTokenSession` double."""

    def __init__(
        self,
        *,
        access_token: str = "fake-access-token",
        app_key: str = "fake-app-key",
        app_secret: str = "fake-app-secret",
    ) -> None:
        self._access_token = access_token
        self._app_key = app_key
        self._app_secret = app_secret
        self.access_token_calls = 0

    def access_token(self) -> str:
        self.access_token_calls += 1
        return self._access_token

    def app_key_header(self) -> str:
        return self._app_key

    def app_secret_header(self) -> str:
        return self._app_secret


class RaisingTokenSession:
    """A token session whose ``access_token()`` always raises — for the
    ``WitnessUnavailable``-wrapping test."""

    def access_token(self) -> str:
        raise RuntimeError("token session: reissue failed (fake)")

    def app_key_header(self) -> str:
        return "unused"

    def app_secret_header(self) -> str:
        return "unused"


class FakeKstDateSource:
    """A fixed :class:`~tos_runtime.recon.witness_kis.KstDateSource` double."""

    def __init__(self, today: str = "20260917") -> None:
        self._today = today

    def today(self) -> str:
        return self._today
