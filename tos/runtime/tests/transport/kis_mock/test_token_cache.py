"""The cross-process shared token cache (#1125 — 2026-11-20's three-tenant token collision)."""

from __future__ import annotations

import json
import stat
import threading
from pathlib import Path
from typing import Any

import pytest
from tos_runtime.transport.kis_mock.credential_session import (
    KisCredentialSession,
    KisCredentialSessions,
)
from tos_runtime.transport.kis_mock.pacer import KisPacing, KisPacingRefused
from tos_runtime.transport.kis_mock.token import TokenResponseError, TokenStale
from tos_runtime.transport.kis_mock.token_cache import (
    SharedTokenCache,
    app_key_fingerprint,
)

from ._fakes import (
    FakeMonotonicSource,
    InMemoryCredentialCustody,
    RecordingEvidenceSink,
)

_KEY_SCOPE = "kis_mock.app_key"
_SECRET_SCOPE = "kis_mock.app_secret"
_APP_KEY = b"app-key-bytes"
_BASE = "https://openapivts.koreainvestment.com:29443"
_TOKEN_PATH = "/oauth2/tokenP"
_PACING = KisPacing(min_interval_ms=1, wait_budget_ms=60_000)
_MARGIN_S = 600
_LIFETIME_S = 86_400


class _CountingTokenClient:
    """One issuance per call, with a distinct token each time."""

    def __init__(self, *, name: str = "t", expires_in: int = _LIFETIME_S) -> None:
        self.issued = 0
        self._name = name
        self._expires_in = expires_in

    def issue_token(
        self, app_key: bytes, app_secret: bytes, *, path: str
    ) -> dict[str, Any]:
        del app_key, app_secret, path
        self.issued += 1
        return {
            "access_token": f"{self._name}-token-{self.issued}",
            "expires_in": self._expires_in,
        }


class _RefusingTokenClient:
    """KIS's answer when this app key already issued a token this minute."""

    def __init__(self) -> None:
        self.calls = 0

    def issue_token(
        self, app_key: bytes, app_secret: bytes, *, path: str
    ) -> dict[str, Any]:
        del app_key, app_secret, path
        self.calls += 1
        return {
            "error_code": "EGW00133",
            "error_description": "접근토큰 발급 잠시 후 다시 시도하세요(1분당 1회)",
        }


class _Clock:
    """A wall clock the test moves, shared by every cache instance in that test."""

    def __init__(self, start: int = 1_700_000_000) -> None:
        self.now = start

    def __call__(self) -> int:
        return self.now


def _custody() -> InMemoryCredentialCustody:
    return InMemoryCredentialCustody(
        {_KEY_SCOPE: _APP_KEY, _SECRET_SCOPE: b"app-secret-bytes"}
    )


def _cache(
    path: Path,
    clock: _Clock,
    *,
    lock_wait_s: float = 5.0,
    endpoint_base: str = _BASE,
) -> SharedTokenCache:
    return SharedTokenCache(
        path=path,
        refresh_margin_s=_MARGIN_S,
        lock_wait_s=lock_wait_s,
        endpoint_base=endpoint_base,
        now_epoch_s=clock,
    )


def _tenant(
    cache: SharedTokenCache,
    client: Any,
    *,
    sink: RecordingEvidenceSink | None = None,
    reissue_cooldown_s: int = 65,
    endpoint_base: str = _BASE,
) -> tuple[KisCredentialSession, RecordingEvidenceSink]:
    """One tenant PROCESS: its own registry, its own lifecycle, the shared cache file."""
    evidence = sink or RecordingEvidenceSink()
    registry = KisCredentialSessions(
        custody=_custody(),
        monotonic=FakeMonotonicSource(start_ms=1_000),
        evidence_sink=evidence,
        token_cache=cache,
    )
    session = registry.session_for(
        client=client,
        app_key_scope=_KEY_SCOPE,
        app_secret_scope=_SECRET_SCOPE,
        token_endpoint_base=endpoint_base,
        token_path=_TOKEN_PATH,
        token_reissue_min_interval_s=reissue_cooldown_s,
        pacing=_PACING,
    )
    return session, evidence


def _entry(path: Path, *, endpoint_base: str = _BASE) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["version"] == 1
    key = _cache(path, _Clock(), endpoint_base=endpoint_base).entry_key(
        app_key_fingerprint(_APP_KEY)
    )
    entry = document["entries"][key]
    assert isinstance(entry, dict)
    return entry


def test_two_tenants_sharing_a_cache_issue_exactly_one_token(tmp_path: Path) -> None:
    """The fix: 005930 boots second and uses the token 000660 already paid for."""
    clock, path = _Clock(), tmp_path / "tokens" / "stock-mock.json"
    first_client, second_client = (
        _CountingTokenClient(name="a"),
        _CountingTokenClient(name="b"),
    )
    first, _ = _tenant(_cache(path, clock), first_client)
    second, second_evidence = _tenant(_cache(path, clock), second_client)

    assert first.ensure_token_string() == "a-token-1"
    assert second.ensure_token_string() == "a-token-1"
    assert first_client.issued == 1
    assert second_client.issued == 0
    hits = [
        row
        for row in second_evidence.of_kind("TRANSPORT_TOKEN_CACHE")
        if row["outcome"] == "hit"
    ]
    assert len(hits) == 1 and hits[0]["remaining_s"] == _LIFETIME_S


def test_an_expired_cache_entry_is_reissued(tmp_path: Path) -> None:
    clock, path = _Clock(), tmp_path / "stock-mock.json"
    first_client = _CountingTokenClient(name="a")
    first, _ = _tenant(_cache(path, clock), first_client)
    assert first.ensure_token_string() == "a-token-1"

    clock.now += _LIFETIME_S + 1
    second_client = _CountingTokenClient(name="b")
    second, _ = _tenant(_cache(path, clock), second_client)
    assert second.ensure_token_string() == "b-token-1"
    assert second_client.issued == 1
    assert _entry(path)["access_token"] == "b-token-1"


def test_an_entry_inside_the_refresh_margin_is_reissued(tmp_path: Path) -> None:
    """Not yet expired, but close enough that a session should not start on it."""
    clock, path = _Clock(), tmp_path / "stock-mock.json"
    first, _ = _tenant(_cache(path, clock), _CountingTokenClient(name="a"))
    first.ensure_token_string()

    clock.now += _LIFETIME_S - _MARGIN_S
    second_client = _CountingTokenClient(name="b")
    second, _ = _tenant(_cache(path, clock), second_client)
    assert second.ensure_token_string() == "b-token-1"
    assert second_client.issued == 1


@pytest.mark.parametrize(
    "content",
    [
        "",
        "not json at all",
        '{"version":1,"entries":[]}',
        '{"version":99,"entries":{}}',
        '{"version":1,"entries":{"x":{"access_token":"","expires_in_s":1}}}',
        '{"version":1',
    ],
)
def test_a_corrupted_cache_is_reissued_not_crashed(
    tmp_path: Path, content: str
) -> None:
    clock, path = _Clock(), tmp_path / "stock-mock.json"
    path.write_text(content, encoding="utf-8")
    client = _CountingTokenClient(name="a")
    session, evidence = _tenant(_cache(path, clock), client)

    assert session.ensure_token_string() == "a-token-1"
    assert client.issued == 1
    assert _entry(path)["access_token"] == "a-token-1"
    misses = [
        row["reason"]
        for row in evidence.of_kind("TRANSPORT_TOKEN_CACHE")
        if row["outcome"] == "miss"
    ]
    assert misses in (["malformed"], ["absent"])


def test_another_app_keys_entry_is_never_used(tmp_path: Path) -> None:
    clock, path = _Clock(), tmp_path / "stock-mock.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "entries": {
                    app_key_fingerprint(b"a-different-app-key"): {
                        "access_token": "not-ours",
                        "issued_at_epoch_s": clock.now,
                        "expires_in_s": _LIFETIME_S,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    client = _CountingTokenClient(name="a")
    session, _ = _tenant(_cache(path, clock), client)

    assert session.ensure_token_string() == "a-token-1"
    document = json.loads(path.read_text(encoding="utf-8"))
    assert len(document["entries"]) == 2


def test_a_still_valid_token_survives_a_refused_reissue(tmp_path: Path) -> None:
    """2026-11-20's failing input, with the fix: the refresh is refused (KIS 1/min) and the"""
    clock, path = _Clock(), tmp_path / "stock-mock.json"
    first, _ = _tenant(_cache(path, clock), _CountingTokenClient(name="a"))
    assert first.ensure_token_string() == "a-token-1"

    clock.now += _LIFETIME_S - _MARGIN_S + 1
    refusing = _RefusingTokenClient()
    second, evidence = _tenant(_cache(path, clock), refusing)
    assert second.ensure_token_string() == "a-token-1"
    assert refusing.calls == 1
    fallbacks = [
        row
        for row in evidence.of_kind("TRANSPORT_TOKEN_CACHE")
        if row["outcome"] == "fallback"
    ]
    assert len(fallbacks) == 1 and 0 < fallbacks[0]["remaining_s"] <= _MARGIN_S
    fault = evidence.of_kind("TRANSPORT_TOKEN_RESPONSE_ERROR")
    assert len(fault) == 1 and fault[0]["error_code"] == "EGW00133"


def test_a_token_response_error_names_the_kis_fault(tmp_path: Path) -> None:
    """With no cached token to fall back on, the refusal surfaces — and says why."""
    clock, path = _Clock(), tmp_path / "stock-mock.json"
    session, evidence = _tenant(_cache(path, clock), _RefusingTokenClient())
    with pytest.raises(TokenResponseError) as caught:
        session.ensure_token_string()

    message = str(caught.value)
    assert "EGW00133" in message and "1분당 1회" in message
    row = evidence.of_kind("TRANSPORT_TOKEN_RESPONSE_ERROR")[0]
    assert row["error_code"] == "EGW00133"
    assert row["body_keys"] == ["error_code", "error_description"]


def test_the_cooldown_does_not_block_a_peers_cached_token(tmp_path: Path) -> None:
    """Today's 005930: its own cooldown is running, and a usable token is in the cache."""
    clock, path = _Clock(), tmp_path / "stock-mock.json"
    stuck, _ = _tenant(_cache(path, clock), _RefusingTokenClient())
    with pytest.raises(TokenResponseError):
        stuck.ensure_token_string()
    with pytest.raises(TokenStale):
        stuck.ensure_token_string()

    peer, _ = _tenant(_cache(path, clock), _CountingTokenClient(name="b"))
    assert peer.ensure_token_string() == "b-token-1"
    assert stuck.ensure_token_string() == "b-token-1"


def test_the_token_never_reaches_evidence_or_an_error(tmp_path: Path) -> None:
    clock, path = _Clock(), tmp_path / "stock-mock.json"
    sink = RecordingEvidenceSink()
    session, _ = _tenant(_cache(path, clock), _CountingTokenClient(name="a"), sink=sink)
    assert session.ensure_token_string() == "a-token-1"
    clock.now += _LIFETIME_S + 1
    refusing = _RefusingTokenClient()
    second, _ = _tenant(_cache(path, clock), refusing, sink=sink)
    with pytest.raises(TokenResponseError) as caught:
        second.ensure_token_string()

    rendered = repr(sink.records) + str(caught.value)
    assert "a-token-1" not in rendered
    assert _APP_KEY.decode() not in rendered
    assert app_key_fingerprint(_APP_KEY) not in rendered


def test_the_cache_file_and_its_directory_are_private(tmp_path: Path) -> None:
    clock, path = _Clock(), tmp_path / "tokens" / "stock-mock.json"
    session, _ = _tenant(_cache(path, clock), _CountingTokenClient(name="a"))
    session.ensure_token_string()

    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert not list(path.parent.glob("*.tmp"))
    assert _APP_KEY.decode() not in path.read_text(encoding="utf-8")


def test_a_held_lock_refuses_within_the_budget_and_sends_nothing(
    tmp_path: Path,
) -> None:
    """A peer wedged mid-issue must not wedge this process: refuse like a paced-out send."""
    clock, path = _Clock(), tmp_path / "stock-mock.json"
    cache = _cache(path, clock, lock_wait_s=0.1)
    client = _CountingTokenClient(name="a")
    session, _ = _tenant(cache, client)
    held = threading.Event()
    done = threading.Event()

    def _hold_the_lock() -> None:
        with _cache(path, clock).exclusive():
            held.set()
            done.wait(5.0)

    holder = threading.Thread(target=_hold_the_lock)
    holder.start()
    try:
        assert held.wait(5.0)
        with pytest.raises(KisPacingRefused):
            session.ensure_token_string()
    finally:
        done.set()
        holder.join(5.0)
    assert client.issued == 0


def test_the_lock_file_is_a_sibling_and_is_not_the_cache(tmp_path: Path) -> None:
    clock, path = _Clock(), tmp_path / "stock-mock.json"
    with _cache(path, clock).exclusive():
        pass
    lock = path.with_name(path.name + ".lock")
    assert lock.is_file() and lock.stat().st_size == 0
    assert stat.S_IMODE(lock.stat().st_mode) & ~0o600 == 0
    assert not path.exists()


def _uncached_tenant(client: Any) -> KisCredentialSession:
    """A tenant whose transport config names no cache — the pre-#1125 wiring."""
    return KisCredentialSessions(
        custody=_custody(),
        monotonic=FakeMonotonicSource(start_ms=1_000),
        evidence_sink=RecordingEvidenceSink(),
    ).session_for(
        client=client,
        app_key_scope=_KEY_SCOPE,
        app_secret_scope=_SECRET_SCOPE,
        token_endpoint_base=_BASE,
        token_path=_TOKEN_PATH,
        token_reissue_min_interval_s=65,
        pacing=_PACING,
    )


def test_without_a_cache_each_lifecycle_issues_its_own() -> None:
    """The pre-#1125 behaviour is still what an unconfigured tenant gets."""
    first_client, second_client = (
        _CountingTokenClient(name="a"),
        _CountingTokenClient(name="b"),
    )
    assert _uncached_tenant(first_client).ensure_token_string() == "a-token-1"
    assert _uncached_tenant(second_client).ensure_token_string() == "b-token-1"


def test_the_cache_survives_a_concurrent_writer(tmp_path: Path) -> None:
    """Eight threads over one file: one issuance, one entry, no torn read."""
    clock, path = _Clock(), tmp_path / "stock-mock.json"
    clients = [_CountingTokenClient(name=f"c{i}") for i in range(8)]
    sessions = [_tenant(_cache(path, clock), client)[0] for client in clients]
    tokens: list[str] = []
    errors: list[BaseException] = []
    barrier = threading.Barrier(len(sessions))

    def _ask(session: KisCredentialSession) -> None:
        barrier.wait(5.0)
        try:
            tokens.append(session.ensure_token_string())
        except BaseException as exc:  # noqa: BLE001 - surfaced by the assert below
            errors.append(exc)

    threads = [threading.Thread(target=_ask, args=(s,)) for s in sessions]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10.0)

    assert errors == []
    assert sum(client.issued for client in clients) == 1
    assert len(set(tokens)) == 1 and len(tokens) == len(sessions)
    assert _entry(path)["access_token"] == tokens[0]


def test_the_same_app_key_against_another_endpoint_is_another_entry(
    tmp_path: Path,
) -> None:
    """Issue #1129 LOW 5: one cache file, one app key, two REST bases — a mock-issued token"""
    clock, path = _Clock(), tmp_path / "stock-mock.json"
    mock_client = _CountingTokenClient(name="mock")
    mock, _ = _tenant(_cache(path, clock), mock_client)
    assert mock.ensure_token_string() == "mock-token-1"

    other_base = "https://openapi.koreainvestment.com:9443"
    other_client = _CountingTokenClient(name="other")
    other, _ = _tenant(
        _cache(path, clock, endpoint_base=other_base),
        other_client,
        endpoint_base=other_base,
    )

    assert other.ensure_token_string() == "other-token-1"
    assert other_client.issued == 1, "the mock endpoint's token was reused elsewhere"
    assert _entry(path)["access_token"] == "mock-token-1"
    assert _entry(path, endpoint_base=other_base)["access_token"] == "other-token-1"


def test_a_cached_token_inside_the_last_seconds_is_not_handed_out(
    tmp_path: Path,
) -> None:
    """Issue #1129 LOW 1: the reissue is refused and the cached token has seconds left —"""
    clock, path = _Clock(), tmp_path / "stock-mock.json"
    cache = _cache(path, clock)
    cache.write(
        app_key_fingerprint(_APP_KEY), access_token="about-to-die", expires_in_s=5
    )
    refusing = _RefusingTokenClient()
    session, evidence = _tenant(_cache(path, clock), refusing)

    with pytest.raises(TokenResponseError):
        session.ensure_token_string()

    assert refusing.calls == 1
    assert [
        row
        for row in evidence.of_kind("TRANSPORT_TOKEN_CACHE")
        if row["outcome"] == "fallback"
    ] == []


def test_a_cached_token_with_room_to_spare_is_still_the_fallback(
    tmp_path: Path,
) -> None:
    """The margin is a few seconds, not the whole refresh margin — the fallback still works."""
    clock, path = _Clock(), tmp_path / "stock-mock.json"
    _cache(path, clock).write(
        app_key_fingerprint(_APP_KEY), access_token="still-good", expires_in_s=60
    )
    session, evidence = _tenant(_cache(path, clock), _RefusingTokenClient())

    assert session.ensure_token_string() == "still-good"
    (fallback,) = [
        row
        for row in evidence.of_kind("TRANSPORT_TOKEN_CACHE")
        if row["outcome"] == "fallback"
    ]
    assert fallback["remaining_s"] == 60
