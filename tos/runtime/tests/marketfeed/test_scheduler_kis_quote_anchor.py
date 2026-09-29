"""The ``kis_quote`` intake driven through the REAL :class:`~tos_runtime.marketfeed.scheduler
.TickScheduler`, against the in-repo fake KIS server — the three chain-level consequences of
#810 that neither the adapter's own tests nor the scheduler's pure ones can show (plan
``docs/plans/2026-09-28-tos-kis-quote-request-anchor-plan.md`` §4 T-3).

**Why a separate module.** ``tests/transport/kis_quote/test_adapter.py`` owns what one ``poll``
returns; ``tests/marketfeed/test_scheduler.py`` owns what ``tick_once`` does with a double. The
claims here are about the two of them TOGETHER plus the REAL durable store — "unconsumed, so
re-emitted, so the next pass ticks" is a statement about the store's high-water mark travelling
back into the intake, and a test that faked either end would not make it.

``poll_interval_ms`` defaults to 1000 — the spacing the 모의 quote rate limit admits (1.0 rps
clean, probe P-13) — because that is the value a real deployment of this intake would carry. The
one test that needs consecutive passes to be judged on their observations rather than on the tick
interval sets it to 0 and says so; ``test_scheduler.py`` owns the interval gate itself.

Everything load-bearing is real: the :class:`~tos_runtime.time.service.TrustworthyTimeService`
(on this process's own monotonic clock and the local system clock reader), the
:class:`~tos_runtime.marketfeed.store.SqliteSnapshotStore`, the Critical Input Policy, the
issuers, the kernel resolver, and the HTTP round trip to ``127.0.0.1``. The session owner and the
engine driver are doubles — the session gate and engine dispatch are not what these tests are
about, and both already have their own coverage.

Hermetic (D1.4): loopback HTTP only, every file under ``tmp_path``, no ambient env.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from tos.time import HealthState
from tos_runtime.marketfeed.ports import TickOutcome
from tos_runtime.marketfeed.scheduler import TickScheduler
from tos_runtime.marketfeed.store import SqliteSnapshotStore
from tos_runtime.marketfeed.time_projection import RuntimeTimeProjection
from tos_runtime.time.config import TrustworthyTimeConfig, load_time_config
from tos_runtime.time.service import TrustworthyTimeService
from tos_runtime.time.sources import LocalSystemClockReader, ProcessMonotonicSource
from tos_runtime.transport.kis_quote.adapter import (
    KisQuoteObservationIntake,
    build_quote_client,
)
from tos_runtime.transport.kis_quote.config import KisQuoteTransportConfig

from ..transport.kis_mock._fake_kis_server import FakeKisServer
from ..transport.kis_quote._fakes import (
    InMemoryCredentialCustody,
    InMemoryEvidencePort,
    RecordingEvidenceSink,
    runtime_identity,
)
from ._fixtures import INSTRUMENT, SCHEME, loaded_policy
from .test_scheduler import _CapturingDriver, _OpenSessionOwner

QUOTE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-price"
TOKEN_PATH = "/oauth2/tokenP"
MARKET_DIV = "J"
QUOTE_ROUTE = (
    f"{QUOTE_PATH}?FID_COND_MRKT_DIV_CODE={MARKET_DIV}&FID_INPUT_ISCD={INSTRUMENT}"
)
INSTRUMENT_CLASS = "krx-index-futures"

#: The DEPLOYED paper bounds, read from the file an operator ships rather than re-typed —
#: parents: [0]=marketfeed, [1]=tests, [2]=runtime, [3]=tos, [4]=repo root.
_PAPER_TIME_YAML = (
    Path(__file__).resolve().parents[4]
    / "config"
    / "tos_runtime"
    / "paper"
    / "time.yaml"
)


@pytest.fixture
def server() -> Iterator[FakeKisServer]:
    srv = FakeKisServer()
    srv.start()
    try:
        yield srv
    finally:
        srv.stop()


def _set_token(server: FakeKisServer) -> None:
    server.set_response(
        TOKEN_PATH, status=200, body={"access_token": "tok-1", "expires_in": 86400}
    )


def _set_quote(server: FakeKisServer, *, price: str = "71300") -> None:
    server.set_response(
        QUOTE_ROUTE,
        status=200,
        body={
            "rt_cd": "0",
            "msg1": "정상처리 되었습니다",
            "output": {"stck_prpr": price},
        },
    )


def _quote_config(server: FakeKisServer) -> KisQuoteTransportConfig:
    """``stck_prpr`` maps onto the policy fixture's own ``close`` field; the fixture's second
    field (``session``) is deliberately left unmapped, so it floors to ``UNKNOWN`` — which is
    still a real tick (``scheduler.py``'s own "every field UNKNOWN is still a tick" note) and
    keeps this module's claims about OUTCOMES, not about value admission."""
    return KisQuoteTransportConfig(
        endpoint_rest_base=server.rest_base,
        quote_path=QUOTE_PATH,
        token_path=TOKEN_PATH,
        tr_id="FHKST01010100",
        instrument=INSTRUMENT,
        market_div_code=MARKET_DIV,
        field_mapping={"stck_prpr": "close"},
        source_id="kis_quote_chain_test",
        token_reissue_min_interval_s=60,
        request_timeout_s=2.0,
        allow_plaintext_for_tests=True,
    )


def _paper_time_config() -> TrustworthyTimeConfig:
    return load_time_config(_PAPER_TIME_YAML)


class _Chain:
    """One wired (time service, intake, store, driver, scheduler) set — built together because
    the SAME ``MonotonicSource`` object has to reach both the time service and the intake (the
    adapter's own "one clock, two jobs" note; the composed runtime does the same, pinned by
    ``tests/compose/test_marketfeed_intake_kind_wiring.py``)."""

    def __init__(
        self, server: FakeKisServer, tmp_path: Path, *, poll_interval_ms: int = 1_000
    ) -> None:
        config = _paper_time_config()
        self.monotonic = ProcessMonotonicSource()
        self.time_service = TrustworthyTimeService(
            monotonic=self.monotonic,
            references=(LocalSystemClockReader(),),
            config=config,
            identity=runtime_identity(),
            evidence=InMemoryEvidencePort(),
        )
        self.time_service.start()
        quote_config = _quote_config(server)
        client = build_quote_client(quote_config)
        self.intake = KisQuoteObservationIntake(
            config=quote_config,
            client=client,
            custody=InMemoryCredentialCustody(
                {"kis_mock.app_key": b"key", "kis_mock.app_secret": b"secret"}
            ),
            monotonic=self.monotonic,
            evidence_sink=RecordingEvidenceSink(),
        )
        self.store = SqliteSnapshotStore(tmp_path / "marketfeed.sqlite3")
        self.driver = _CapturingDriver()
        session_owner = _OpenSessionOwner()
        self.admit = True
        self.scheduler = TickScheduler(
            instruments=(INSTRUMENT,),
            instrument_class=INSTRUMENT_CLASS,
            account="acct-kis-quote-chain",
            direction="LONG",
            quantity_basis="RISK",
            unit="contract",
            policy=loaded_policy(tmp_path),
            scheme=SCHEME,
            intake=self.intake,
            store=self.store,
            time_projection=RuntimeTimeProjection(
                config=config,
                time_service=self.time_service,
                session_owner=session_owner,
                instrument_class=INSTRUMENT_CLASS,
                snapshot_age_bound=20,  # config/tos_runtime/paper/marketfeed.yaml
                interval_width=10,  # config/tos_runtime/paper/marketfeed.yaml
            ),
            time_service=self.time_service,
            # Hand-rolled doubles (structural, not subclasses) — cast for the nominal types.
            session_owner=cast(Any, session_owner),
            driver=cast(Any, self.driver),
            inbox=MagicMock(),
            evidence_store=MagicMock(),
            poll_interval_ms=poll_interval_ms,
            before_decide=self._before_decide,
        )

    def _before_decide(self) -> bool:
        """The pacer's own shape: evaluate, then admit — with ``admit`` a test can flip to
        ``False`` to stand in for an evaluation that was due and FAILED."""
        self.time_service.evaluate()
        return self.admit

    def latest_as_of(self) -> int | None:
        mark: int | None = self.store.latest_as_of(instrument=INSTRUMENT)
        return mark

    def close(self) -> None:
        self.store.close()


def test_a_pass_whose_time_is_not_yet_trusted_is_unanchored_not_fatal(
    server: FakeKisServer, tmp_path: Path
) -> None:
    """D-3 (plan §0). Before #810 the adapter read the wall clock inside ``poll`` and RAISED
    ``KisQuoteWallClockUntrusted`` when time was not yet ``TRUSTED`` — out of ``tick_once``,
    out of ``run_forever``, and the loop was gone. Now the first pass (whose own evaluation only
    reaches ``SYNCHRONIZING``) is a named absence that consumes nothing, and the second pass —
    whose evaluation reaches ``TRUSTED`` — ticks on the very same quote.

    Mutations: anchor anyway when the mapping is ``None`` -> the first pass ticks with a
    fabricated stamp -> red; commit the digest inside ``poll`` -> the second pass sees nothing
    new -> red.
    """
    _set_token(server)
    _set_quote(server)
    chain = _Chain(server, tmp_path)
    try:
        first = chain.scheduler.tick_once()

        assert chain.time_service.health_state is HealthState.SYNCHRONIZING
        assert first.outcome is TickOutcome.SKIPPED_TIME_UNANCHORED
        assert chain.driver.events == []
        assert chain.latest_as_of() is None

        second = chain.scheduler.tick_once()

        assert chain.time_service.health_state is HealthState.TRUSTED
        assert second.outcome is TickOutcome.TICKED
        assert len(chain.driver.events) == 1
        assert chain.latest_as_of() is not None
        # Two REAL quote GETs — the second pass re-fetched rather than replaying a cache.
        assert len(server.requests_for(QUOTE_ROUTE)) == 2
    finally:
        chain.close()


def test_the_loop_survives_an_untrusted_pass(
    server: FakeKisServer, tmp_path: Path
) -> None:
    """The same fact through ``run_forever``, which is where the old exception actually killed
    the process: two passes, no exception, exactly one tick once trust arrives."""
    _set_token(server)
    _set_quote(server)
    chain = _Chain(server, tmp_path)
    passes = {"n": 0}

    def stop() -> bool:
        if passes["n"] >= 2:
            return True
        passes["n"] += 1
        return False

    try:
        chain.scheduler.run_forever(sleep=lambda _: None, stop=stop)

        assert passes["n"] == 2
        assert len(chain.driver.events) == 1
        assert chain.latest_as_of() is not None
    finally:
        chain.close()


def test_a_failed_evaluation_leaves_the_quote_for_the_next_pass(
    server: FakeKisServer, tmp_path: Path
) -> None:
    """D-2 (plan §0), through the REAL store. The pass polls, its evaluation fails, nothing is
    consumed — and because the store's high-water mark did not move, the intake holds its
    digest pending and re-emits the same quote on the next pass, which ticks.

    Before #810 that observation was lost until the PRICE changed (the behaviour #811 pinned).
    Mutation: commit the digest inside ``poll`` -> the second pass is
    ``SKIPPED_NO_OBSERVATION`` -> red.
    """
    _set_token(server)
    _set_quote(server)
    chain = _Chain(server, tmp_path)
    try:
        chain.scheduler.tick_once()  # SYNCHRONIZING -> unanchored
        chain.admit = False
        second = chain.scheduler.tick_once()

        assert second.outcome is TickOutcome.SKIPPED_TIME_NOT_EVALUATED
        assert chain.latest_as_of() is None

        chain.admit = True
        third = chain.scheduler.tick_once()

        assert third.outcome is TickOutcome.TICKED
        assert len(chain.driver.events) == 1
        assert chain.latest_as_of() is not None
    finally:
        chain.close()


def test_an_unchanged_quote_after_a_tick_is_no_observation_at_all(
    server: FakeKisServer, tmp_path: Path
) -> None:
    """The phantom-churn guarantee survives the deferred digest: once an emission IS consumed
    (the high-water mark advanced), an unchanged quote is ``SKIPPED_NO_OBSERVATION`` — the
    scheduler is not handed a second observation for a market that has not moved.

    Mutation: never commit the pending digest -> the same quote is re-emitted forever, the
    second pass answers ``SKIPPED_NOT_NEWER`` instead (``decide_tick``'s own independent
    re-derivation catches it downstream) -> red.
    """
    _set_token(server)
    _set_quote(server)
    # 0 ms: these passes run back to back in wall-clock terms, and SKIPPED_INTERVAL would mask
    # the outcome under test (module docstring).
    chain = _Chain(server, tmp_path, poll_interval_ms=0)
    try:
        chain.scheduler.tick_once()  # SYNCHRONIZING -> unanchored
        ticked = chain.scheduler.tick_once()
        assert ticked.outcome is TickOutcome.TICKED
        consumed_as_of = chain.latest_as_of()

        quiet = chain.scheduler.tick_once()

        assert quiet.outcome is TickOutcome.SKIPPED_NO_OBSERVATION
        assert chain.latest_as_of() == consumed_as_of
        assert len(chain.driver.events) == 1

        # ...and a genuine price change still ticks.
        _set_quote(server, price="71400")
        moved = chain.scheduler.tick_once()

        assert moved.outcome is TickOutcome.TICKED
        assert len(chain.driver.events) == 2
    finally:
        chain.close()
