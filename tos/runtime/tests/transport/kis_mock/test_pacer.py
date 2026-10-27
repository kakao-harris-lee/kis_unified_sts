"""Issue #970 — one request pacer per KIS app key (``tos_runtime.transport.kis_mock.pacer``),
owned by the app key's credential session and taken by every request on the key: order POST,
witness GET, token POST.

The fake clock advances only when the pacer sleeps (``time.sleep`` is patched in the pacer
module), so every wait is exact and every grant instant is deterministic, even from two threads.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest
import tos_runtime.transport.kis_mock.pacer as pacer_module
from tos_runtime.time.sources import ProcessMonotonicSource
from tos_runtime.transport.kis_mock.credential_session import (
    KisCredentialSession,
    KisCredentialSessions,
)
from tos_runtime.transport.kis_mock.pacer import (
    KisAppKeyPacer,
    KisPacing,
    KisPacingRefused,
)
from tos_runtime.transport.kis_mock.token import TokenStale

from ._fakes import InMemoryCredentialCustody, RecordingEvidenceSink

_KEY_SCOPE = "kis_mock.app_key"
_SECRET_SCOPE = "kis_mock.app_secret"


class _SleepClock:
    """A monotonic clock that moves only when someone sleeps on it. Thread-safe."""

    def __init__(self, start_ms: int = 10_000) -> None:
        self._now_ms = start_ms
        self._lock = threading.Lock()
        self.sleeps_ms: list[int] = []

    def now_ms(self) -> int:
        with self._lock:
            return self._now_ms

    def sleep(self, seconds: float) -> None:
        delta_ms = round(seconds * 1000)
        with self._lock:
            self.sleeps_ms.append(delta_ms)
            self._now_ms += delta_ms

    def advance(self, delta_ms: int) -> None:
        with self._lock:
            self._now_ms += delta_ms


class _TokenClient:
    """Records the clock reading at each token POST."""

    def __init__(self, clock: _SleepClock) -> None:
        self._clock = clock
        self.issued_at_ms: list[int] = []

    def issue_token(
        self, app_key: bytes, app_secret: bytes, *, path: str  # noqa: ARG002
    ) -> dict[str, Any]:
        self.issued_at_ms.append(self._clock.now_ms())
        return {
            "access_token": f"token-{len(self.issued_at_ms)}",
            "expires_in": 86_400,
        }


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Iterator[_SleepClock]:
    fake = _SleepClock()
    monkeypatch.setattr(pacer_module, "sleep", fake.sleep)
    yield fake


@pytest.fixture
def grants(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Every grant instant, as :meth:`KisAppKeyPacer.acquire` returned it."""
    recorded: list[int] = []
    original = KisAppKeyPacer.acquire

    def _spy(self: KisAppKeyPacer) -> int:
        granted = int(original(self))
        recorded.append(granted)
        return granted

    monkeypatch.setattr(KisAppKeyPacer, "acquire", _spy)
    return recorded


def _session(
    clock: _SleepClock,
    *,
    min_interval_ms: int = 2_000,
    wait_budget_ms: int = 4_000,
    client: _TokenClient | None = None,
    custody: InMemoryCredentialCustody | None = None,
) -> KisCredentialSession:
    registry = KisCredentialSessions(
        custody=custody
        or InMemoryCredentialCustody({_KEY_SCOPE: b"key", _SECRET_SCOPE: b"secret"}),
        monotonic=clock,
        evidence_sink=RecordingEvidenceSink(),
    )
    return registry.session_for(
        client=client or _TokenClient(clock),
        app_key_scope=_KEY_SCOPE,
        app_secret_scope=_SECRET_SCOPE,
        token_endpoint_base="https://openapivts.koreainvestment.com:29443",
        token_path="/oauth2/tokenP",
        token_reissue_min_interval_s=60,
        pacing=KisPacing(
            min_interval_ms=min_interval_ms, wait_budget_ms=wait_budget_ms
        ),
    )


# -- the pacer itself -------------------------------------------------------------------------


def test_the_first_slot_is_immediate_and_the_next_waits_out_the_interval(
    clock: _SleepClock,
) -> None:
    pacer = KisAppKeyPacer(
        pacing=KisPacing(min_interval_ms=2_000, wait_budget_ms=4_000), monotonic=clock
    )
    first = pacer.acquire()
    clock.advance(500)
    second = pacer.acquire()

    assert clock.sleeps_ms == [1_500]
    assert second - first == 2_000


def test_no_wait_once_the_interval_has_passed(clock: _SleepClock) -> None:
    pacer = KisAppKeyPacer(
        pacing=KisPacing(min_interval_ms=2_000, wait_budget_ms=4_000), monotonic=clock
    )
    pacer.acquire()
    clock.advance(2_500)
    pacer.acquire()

    assert clock.sleeps_ms == []


def test_a_slot_beyond_the_budget_is_refused_without_waiting_or_taking_it(
    clock: _SleepClock,
) -> None:
    """Fail closed, never send late: the refusal does not sleep and does not move the next
    caller's slot (mutation: record the grant before the budget check -> the later acquire
    waits again -> red)."""
    pacer = KisAppKeyPacer(
        pacing=KisPacing(min_interval_ms=2_000, wait_budget_ms=1_000), monotonic=clock
    )
    first = pacer.acquire()
    with pytest.raises(KisPacingRefused):
        pacer.acquire()
    assert clock.sleeps_ms == []

    clock.advance(1_200)  # 800 ms left now — inside the budget
    assert pacer.acquire() == first + 2_000
    assert clock.sleeps_ms == [800]


@pytest.mark.parametrize(
    ("min_interval_ms", "wait_budget_ms"), [(0, 1), (1, 0), (-1, 5)]
)
def test_pacing_terms_must_be_positive(
    min_interval_ms: int, wait_budget_ms: int
) -> None:
    with pytest.raises(ValueError):
        KisPacing(min_interval_ms=min_interval_ms, wait_budget_ms=wait_budget_ms)


# -- through the credential session (the app key's one owner) ---------------------------------


def test_concurrent_order_post_and_witness_get_never_closer_than_the_interval(
    clock: _SleepClock, grants: list[int]
) -> None:
    """Issue #970 acceptance: the loop thread's order POSTs (``app_credentials()``, as
    ``KisMockTransport`` takes it) and the FETCH worker's witness GETs (``request_credentials()``,
    as ``KisStockBrokerWitness`` takes it) run at the same time on one app key. Every request —
    the token POST included — starts at least the interval after the previous one.

    Mutation: drop ``self._pacer.acquire()`` from ``app_credentials`` -> 11 requests, 1 grant
    -> red; release the pacer lock before the sleep -> two grants share an instant -> red.
    """
    session = _session(clock, min_interval_ms=2_000, wait_budget_ms=4_000)
    sent: list[tuple[str, int]] = []
    errors: list[BaseException] = []
    start = threading.Barrier(2)

    def _orders() -> None:
        try:
            start.wait()
            for _ in range(5):
                with session.app_credentials() as creds:
                    assert creds.app_key() == b"key"
                    sent.append(("order", clock.now_ms()))
        except BaseException as exc:  # noqa: BLE001 - surfaced by the assert below
            errors.append(exc)

    def _witness() -> None:
        try:
            start.wait()
            for _ in range(5):
                with session.request_credentials() as creds:
                    assert creds.access_token.startswith("token-")
                    sent.append(("witness", clock.now_ms()))
        except BaseException as exc:  # noqa: BLE001 - surfaced by the assert below
            errors.append(exc)

    threads = [threading.Thread(target=_orders), threading.Thread(target=_witness)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10.0)

    assert errors == []
    assert sorted(kind for kind, _ in sent) == ["order"] * 5 + ["witness"] * 5
    assert len(grants) == 11  # ten requests and the witness's one token POST
    ordered = sorted(grants)
    assert all(b - a >= 2_000 for a, b in zip(ordered, ordered[1:], strict=False))


def test_two_threads_on_the_real_clock_are_spaced_by_the_grants_themselves(
    grants: list[int],
) -> None:
    """The same race on the process clock with a real sleep (50 ms interval, ~0.5 s). The fake
    clock above sums every sleep, so it cannot see two threads sleeping AT THE SAME TIME; this
    one can. Grants are clock readings taken under the pacer lock after the wait, so correct
    code spaces them by at least the interval exactly (whole-ms truncation cannot shrink a gap
    that the sleep already covered). Mutation: release the lock around the sleep -> both
    threads wait out the same previous grant and are granted together -> red."""
    pacer = KisAppKeyPacer(
        pacing=KisPacing(min_interval_ms=50, wait_budget_ms=5_000),
        monotonic=ProcessMonotonicSource(),
    )
    start = threading.Barrier(2)
    errors: list[BaseException] = []

    def _five() -> None:
        try:
            start.wait()
            for _ in range(5):
                pacer.acquire()
        except BaseException as exc:  # noqa: BLE001 - surfaced by the assert below
            errors.append(exc)

    threads = [threading.Thread(target=_five) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10.0)

    assert errors == []
    ordered = sorted(grants)
    assert len(ordered) == 10
    assert all(b - a >= 50 for a, b in zip(ordered, ordered[1:], strict=False))


def test_the_token_post_takes_a_slot_before_it_is_sent(
    clock: _SleepClock, grants: list[int]
) -> None:
    """A token POST is a request on the key: it gets a slot, and the request it was fetched
    for waits the interval after it (mutation: drop the lifecycle's ``acquire`` -> one grant,
    no sleep -> red)."""
    client = _TokenClient(clock)
    session = _session(clock, min_interval_ms=2_000, client=client)

    with session.request_credentials():
        request_at = clock.now_ms()

    assert len(grants) == 2
    assert client.issued_at_ms == [grants[0]]
    assert request_at == grants[1] == grants[0] + 2_000
    assert clock.sleeps_ms == [2_000]


def test_a_refused_request_loads_nothing_from_custody(clock: _SleepClock) -> None:
    custody = InMemoryCredentialCustody({_KEY_SCOPE: b"key", _SECRET_SCOPE: b"secret"})
    session = _session(
        clock, min_interval_ms=2_000, wait_budget_ms=1_000, custody=custody
    )
    with session.app_credentials():
        pass
    loads_before = list(custody.load_calls)

    with pytest.raises(KisPacingRefused):
        with session.app_credentials():
            pytest.fail("the block must not run when the slot is refused")

    assert custody.load_calls == loads_before


def test_a_refused_token_slot_does_not_start_the_reissue_cooldown(
    clock: _SleepClock,
) -> None:
    """Nothing was POSTed, so the next ask after the interval issues the token instead of
    raising ``TokenStale`` for a minute (mutation: record the issue attempt before the slot ->
    ``TokenStale`` below -> red)."""
    client = _TokenClient(clock)
    session = _session(
        clock, min_interval_ms=2_000, wait_budget_ms=1_000, client=client
    )
    with session.app_credentials():
        pass

    with pytest.raises(KisPacingRefused):
        session.ensure_token_string()
    assert client.issued_at_ms == []

    clock.advance(2_000)
    try:
        assert session.ensure_token_string() == "token-1"
    except TokenStale:  # pragma: no cover - the mutation's failure mode
        pytest.fail("a refused (unsent) token POST started the reissue cooldown")


def test_a_token_issue_in_flight_elsewhere_refuses_after_the_wait_budget() -> None:
    """review-979 r1 MEDIUM: while the FETCH worker's token issue holds the lifecycle lock (its
    pacer wait plus the POST), a loop-thread caller waits at most the pacer's wait budget for it
    and is then refused unsent — not blocked for the worker's whole POST before its own budget
    even starts. Mutation: an unbounded ``with self._lock`` -> the second caller blocks until
    the release below -> red on the elapsed bound."""
    clock = _SleepClock()
    entered, release = threading.Event(), threading.Event()

    class _SlowTokenClient:
        def issue_token(
            self, app_key: bytes, app_secret: bytes, *, path: str  # noqa: ARG002
        ) -> dict[str, Any]:
            entered.set()
            release.wait(10.0)
            return {"access_token": "tok-slow", "expires_in": 86_400}

    session = _session(
        clock, min_interval_ms=1, wait_budget_ms=200, client=_SlowTokenClient()  # type: ignore[arg-type]
    )
    worker = threading.Thread(target=session.ensure_token_string)
    worker.start()
    assert entered.wait(5.0)
    try:
        started = time.monotonic()
        with pytest.raises(KisPacingRefused, match="token"):
            session.ensure_token_string()
        elapsed = time.monotonic() - started
    finally:
        release.set()
        worker.join(5.0)

    assert 0.15 <= elapsed < 2.0
    assert (
        session.ensure_token_string() == "tok-slow"
    )  # the worker's issue still landed
