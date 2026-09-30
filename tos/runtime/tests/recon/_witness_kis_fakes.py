"""Shared fakes for the ``KisStockBrokerWitness`` test suite."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

__all__ = [
    "FakeCredentialSession",
    "FakeKstDateSource",
    "RaisingCredentialSession",
]


class _FakeRequestCredentials:
    """A :class:`~tos_runtime.recon.witness_kis.KisWitnessRequestCredentials` double whose
    key/secret become unreadable once its block exits (the real session zeroes its handles).
    """

    def __init__(self, *, access_token: str, app_key: str, app_secret: str) -> None:
        self.access_token = access_token
        self._app_key = app_key
        self._app_secret = app_secret
        self.closed = False

    def _read(self, value: str) -> bytes:
        if self.closed:
            raise RuntimeError("fake credentials read after their block exited")
        return value.encode()

    def app_key(self) -> bytes:
        return self._read(self._app_key)

    def app_secret(self) -> bytes:
        return self._read(self._app_secret)


class FakeCredentialSession:
    """A minimal :class:`~tos_runtime.recon.witness_kis.KisWitnessCredentialSession` double."""

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
        self.request_credentials_calls = 0
        self.open_blocks = 0

    @contextmanager
    def request_credentials(self) -> Iterator[_FakeRequestCredentials]:
        self.request_credentials_calls += 1
        credentials = _FakeRequestCredentials(
            access_token=self._access_token,
            app_key=self._app_key,
            app_secret=self._app_secret,
        )
        self.open_blocks += 1
        try:
            yield credentials
        finally:
            credentials.closed = True
            self.open_blocks -= 1


class RaisingCredentialSession:
    """A credential session whose ``request_credentials()`` always raises — for the
    ``WitnessUnavailable``-wrapping test."""

    @contextmanager
    def request_credentials(self) -> Iterator[_FakeRequestCredentials]:
        raise RuntimeError("credential session: reissue failed (fake)")
        yield  # pragma: no cover - makes this a generator


class FakeKstDateSource:
    """A fixed :class:`~tos_runtime.recon.witness_kis.KstDateSource` double."""

    def __init__(self, today: str = "20260917") -> None:
        self._today = today

    def today(self) -> str:
        return self._today
