"""Hermetic tests for ``tos_runtime.transport.kis_mock.credential_session`` — the C-2 decision
(C) pins (``docs/plans/2026-09-23-tos-kis-credential-ownership-decision-c2.md`` §4.3):

1. Two consumers of one app key share one session, so their first calls in the same
   millisecond issue exactly ONE token (each building its own lifecycle issued two — the
   collision KIS answers with HTTP 403).
2. No module under ``tos_runtime`` other than the session and its lifecycle loads from custody.
3. The key/secret handed out by ``request_credentials()`` are unreadable once the block exits.
"""

from __future__ import annotations

import ast
import threading
from pathlib import Path
from typing import Any

import pytest
from tos_runtime.custody.ports import CustodyError
from tos_runtime.transport.kis_mock.credential_session import (
    KisCredentialSession,
    KisCredentialSessionConflict,
    KisCredentialSessions,
)
from tos_runtime.transport.kis_mock.token import TokenStale

from ._fakes import (
    FakeMonotonicSource,
    InMemoryCredentialCustody,
    RecordingEvidenceSink,
)

_KEY_SCOPE = "kis_mock.app_key"
_SECRET_SCOPE = "kis_mock.app_secret"
_BASE = "https://openapivts.koreainvestment.com:29443"
_TOKEN_PATH = "/oauth2/tokenP"


class _CountingTokenClient:
    def __init__(self, *, expires_in: int = 86_400) -> None:
        self.issued = 0
        self._expires_in = expires_in

    def issue_token(
        self, app_key: bytes, app_secret: bytes, *, path: str
    ) -> dict[str, Any]:
        assert app_key == b"key-bytes" and app_secret == b"secret-bytes"
        assert path == _TOKEN_PATH
        self.issued += 1
        return {"access_token": f"token-{self.issued}", "expires_in": self._expires_in}


def _custody() -> InMemoryCredentialCustody:
    return InMemoryCredentialCustody(
        {_KEY_SCOPE: b"key-bytes", _SECRET_SCOPE: b"secret-bytes"}
    )


def _registry(
    custody: InMemoryCredentialCustody | None = None,
    monotonic: FakeMonotonicSource | None = None,
) -> KisCredentialSessions:
    return KisCredentialSessions(
        custody=custody or _custody(),
        monotonic=monotonic or FakeMonotonicSource(start_ms=1_000),
        evidence_sink=RecordingEvidenceSink(),
    )


def _session_for(
    registry: KisCredentialSessions,
    client: _CountingTokenClient,
    **overrides: Any,
) -> KisCredentialSession:
    terms: dict[str, Any] = {
        "app_key_scope": _KEY_SCOPE,
        "app_secret_scope": _SECRET_SCOPE,
        "token_endpoint_base": _BASE,
        "token_path": _TOKEN_PATH,
        "token_reissue_min_interval_s": 61,
    }
    terms.update(overrides)
    return registry.session_for(client=client, **terms)


# -- pin 1: one app key, one token lifecycle -------------------------------------------------


def test_two_consumers_of_one_app_key_issue_exactly_one_token() -> None:
    """Order transport and quote intake ask in the same millisecond (the fake clock never
    moves). Mutation: make ``session_for`` build a fresh session each call -> 2 issues and a
    ``TokenStale`` for nobody, but a real broker 403 for the second -> red."""
    registry = _registry()
    order_client, quote_client = _CountingTokenClient(), _CountingTokenClient()
    order_session = _session_for(registry, order_client)
    quote_session = _session_for(registry, quote_client)

    assert order_session is quote_session
    assert order_session.ensure_token_string() == "token-1"
    assert quote_session.ensure_token_string() == "token-1"
    assert order_client.issued + quote_client.issued == 1


@pytest.mark.parametrize(
    "override",
    [
        {"token_endpoint_base": "https://other.example:29443"},
        {"token_path": "/oauth2/other"},
        {"token_reissue_min_interval_s": 5},
    ],
)
def test_a_second_consumer_with_different_terms_is_refused(
    override: dict[str, Any],
) -> None:
    registry = _registry()
    _session_for(registry, _CountingTokenClient())
    with pytest.raises(KisCredentialSessionConflict):
        _session_for(registry, _CountingTokenClient(), **override)


def test_a_different_app_key_gets_its_own_session() -> None:
    registry = _registry()
    first = _session_for(registry, _CountingTokenClient())
    other = _session_for(
        registry,
        _CountingTokenClient(),
        app_key_scope="other.app_key",
        app_secret_scope="other.app_secret",
    )
    assert first is not other


# -- pin 2: custody is loaded only by the session and its lifecycle --------------------------

_RUNTIME_SRC = Path(__file__).resolve().parents[3] / "src" / "tos_runtime"
_ALLOWED_LOADERS = {
    _RUNTIME_SRC / "transport" / "kis_mock" / "credential_session.py",
    _RUNTIME_SRC / "transport" / "kis_mock" / "token.py",
}


def _custody_load_calls(path: Path) -> list[int]:
    """Line numbers of ``<...custody>.load(...)`` calls in ``path``."""
    lines: list[int] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "load"
        ):
            continue
        target = node.func.value
        name = (
            target.id
            if isinstance(target, ast.Name)
            else target.attr if isinstance(target, ast.Attribute) else ""
        )
        if name.lstrip("_").endswith("custody"):
            lines.append(node.lineno)
    return lines


def test_only_the_credential_session_and_its_lifecycle_load_from_custody() -> None:
    """Mutation: restore an adapter's inline ``with self._custody.load(...)`` -> red."""
    offenders = {
        str(path.relative_to(_RUNTIME_SRC)): lines
        for path in sorted(_RUNTIME_SRC.rglob("*.py"))
        if path not in _ALLOWED_LOADERS and (lines := _custody_load_calls(path))
    }
    assert offenders == {}
    # The scan itself is live: the session module is found by the same predicate.
    assert _custody_load_calls(next(iter(sorted(_ALLOWED_LOADERS))))


# -- pin 3: handles die with the block ---------------------------------------------------------


def test_credentials_are_unreadable_after_the_block_exits() -> None:
    session = _session_for(_registry(), _CountingTokenClient())
    with session.request_credentials() as credentials:
        assert credentials.access_token == "token-1"
        assert credentials.app_key() == b"key-bytes"
        assert credentials.app_secret() == b"secret-bytes"
    with pytest.raises(CustodyError):
        credentials.app_key()
    with pytest.raises(CustodyError):
        credentials.app_secret()


def test_app_credentials_are_unreadable_after_the_block_exits() -> None:
    session = _session_for(_registry(), _CountingTokenClient())
    with session.app_credentials() as credentials:
        assert credentials.app_key() == b"key-bytes"
    with pytest.raises(CustodyError):
        credentials.app_key()


def test_a_stale_token_refuses_before_any_key_is_loaded() -> None:
    """``request_credentials`` asks for the token first — inside the reissue cooldown with an
    expired token nothing is loaded from custody."""
    custody = _custody()
    monotonic = FakeMonotonicSource(start_ms=1_000)
    session = _session_for(
        _registry(custody, monotonic), _CountingTokenClient(expires_in=1)
    )
    with session.request_credentials():
        pass
    loads_after_first = len(custody.load_calls)
    monotonic.advance(2_000)  # token expired, cooldown (61 s) not elapsed
    with pytest.raises(TokenStale), session.request_credentials():
        pass
    assert len(custody.load_calls) == loads_after_first


# -- issue #950: the session is shared across threads ----------------------------------------


class _SlowTokenClient:
    """A token POST that holds the issuing thread until released — so a second thread asks
    while the first is mid-issue, the exact race a FETCH thread and the loop thread make.
    """

    def __init__(self) -> None:
        self.issued = 0
        self.entered = threading.Event()
        self.release = threading.Event()

    def issue_token(
        self, app_key: bytes, app_secret: bytes, *, path: str
    ) -> dict[str, Any]:
        del app_key, app_secret, path
        self.issued += 1
        self.entered.set()
        assert self.release.wait(5.0), "the test never released the token POST"
        return {"access_token": f"token-{self.issued}", "expires_in": 86_400}


def test_concurrent_token_refresh_from_two_threads_issues_exactly_one_post() -> None:
    """Issue #950 acceptance: two threads ask for the token at once (fill observer FETCH thread
    and the loop's order send) -> exactly one POST, both get the same token, and the state is
    consistent afterwards. Mutation: drop the lifecycle's lock -> the second thread sees no
    token and POSTs again (KIS answers a second issue inside a minute with 403) -> red.
    """
    client = _SlowTokenClient()
    session = _session_for(_registry(), client)  # type: ignore[arg-type]
    tokens: list[str] = []
    errors: list[BaseException] = []

    def _ask() -> None:
        try:
            tokens.append(session.ensure_token_string())
        except BaseException as exc:  # noqa: BLE001 - surfaced by the assert below
            errors.append(exc)

    first = threading.Thread(target=_ask)
    first.start()
    assert client.entered.wait(5.0)
    second = threading.Thread(target=_ask)
    second.start()
    second.join(0.2)
    assert second.is_alive(), "the second asker must wait for the in-flight issue"
    client.release.set()
    first.join(5.0)
    second.join(5.0)

    assert errors == []
    assert client.issued == 1
    assert tokens == ["token-1", "token-1"]
    assert session.ensure_token_string() == "token-1"


def test_concurrent_stale_refusals_record_whole_rows() -> None:
    """Two threads refused inside the cooldown each record one complete
    ``TRANSPORT_TOKEN_STALE`` row — no lost or half-built record."""
    custody = _custody()
    monotonic = FakeMonotonicSource(start_ms=1_000)
    sink = RecordingEvidenceSink()
    registry = KisCredentialSessions(
        custody=custody, monotonic=monotonic, evidence_sink=sink
    )
    session = _session_for(registry, _CountingTokenClient(expires_in=1))
    session.ensure_token_string()
    monotonic.advance(2_000)
    start = threading.Barrier(2)
    stale: list[int] = []

    def _ask() -> None:
        start.wait()
        try:
            session.ensure_token_string()
        except TokenStale:
            stale.append(1)

    threads = [threading.Thread(target=_ask) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(5.0)

    assert len(stale) == 2
    rows = sink.of_kind("TRANSPORT_TOKEN_STALE")
    assert len(rows) == 2
    assert all(
        set(r) == {"reissue_cooldown_s", "elapsed_ms", "cooldown_remaining_ms"}
        for r in rows
    )
