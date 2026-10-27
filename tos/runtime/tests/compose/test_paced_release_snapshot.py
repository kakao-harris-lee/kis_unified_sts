"""Issue #970 — the release snapshot under the app key pacer.

Every request on the ``kis_mock.*`` key is now ``min_send_interval_ms`` apart, the witness's
included. The fill observer's FETCH reads the planned order inquiry first and the release
snapshot (balance + order inquiry) right after, so the snapshot's first GET waits a full interval
in the pacer before it reads anything. That wait is not broker-state age: the snapshot is aged
from its first GET's pacer grant (``fill_fetch.SnapshotRead``), and compose refuses a
``release_snapshot_max_age_ms`` below two intervals.

The fake clock moves only when the pacer sleeps (its ``sleep`` is patched), so every grant
instant below is exact.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from typing import Any

import pytest
import tos_runtime.transport.kis_mock.pacer as pacer_module
import yaml
from tos.engine.records import InstrumentKey
from tos_runtime.compose._broker_posttrade_wiring import DeferredKisWitness
from tos_runtime.posttrade.fill_fetch import FetchPlan, run_fetch
from tos_runtime.posttrade.fill_observer import FillObserverConfigError
from tos_runtime.recon.ports import WitnessScope, WitnessSnapshot
from tos_runtime.recon.witness_kis import KisStockBrokerWitness, KisWitnessHttpClient
from tos_runtime.transport.kis_mock.credential_session import KisCredentialSessions
from tos_runtime.transport.kis_mock.pacer import KisPacing

from ..recon._fake_kis_get_server import FakeKisGetServer
from ..recon._witness_kis_fakes import FakeKstDateSource
from ..recon.test_witness_kis import ACCOUNT, BALANCE_PATH, ORDER_PATH, _config
from ..transport.kis_mock._fake_kis_server import FakeKisServer
from ..transport.kis_mock._fakes import InMemoryCredentialCustody, RecordingEvidenceSink
from .test_kis_mock_e2e_honesty import _boot, _sealed_mock_deployment

_DATE = "20261023"
_INTERVAL_MS = 2_000  # the approved kis_mock_transport.yaml::min_send_interval_ms
_LOOP_PASS_MS = 400  # marketfeed.yaml poll_interval_ms — FETCH done to APPLY


class _SleepClock:
    """Moves only when the pacer sleeps. Thread-safe."""

    def __init__(self, start_ms: int) -> None:
        self._now_ms = start_ms
        self._lock = threading.Lock()

    def now_ms(self) -> int:
        with self._lock:
            return self._now_ms

    def sleep(self, seconds: float) -> None:
        with self._lock:
            self._now_ms += round(seconds * 1000)

    def advance(self, delta_ms: int) -> None:
        with self._lock:
            self._now_ms += delta_ms


class _TokenClient:
    def issue_token(
        self, app_key: bytes, app_secret: bytes, *, path: str  # noqa: ARG002
    ) -> dict[str, Any]:
        return {"access_token": "tok-1", "expires_in": 86_400}


@pytest.fixture
def get_server() -> Iterator[FakeKisGetServer]:
    srv = FakeKisGetServer()
    srv.start()
    try:
        yield srv
    finally:
        srv.stop()


def _paced_witness(server: FakeKisGetServer, clock: _SleepClock) -> DeferredKisWitness:
    session = KisCredentialSessions(
        custody=InMemoryCredentialCustody(
            {"kis_mock.app_key": b"key", "kis_mock.app_secret": b"secret"}
        ),
        monotonic=clock,
        evidence_sink=RecordingEvidenceSink(),
    ).session_for(
        client=_TokenClient(),
        app_key_scope="kis_mock.app_key",
        app_secret_scope="kis_mock.app_secret",
        token_endpoint_base=server.rest_base,
        token_path="/oauth2/tokenP",
        token_reissue_min_interval_s=60,
        pacing=KisPacing(min_interval_ms=_INTERVAL_MS, wait_budget_ms=2 * _INTERVAL_MS),
    )
    config = _config(server)
    witness = DeferredKisWitness(lambda: _DATE)
    witness.inner = KisStockBrokerWitness(
        config=config,
        client=KisWitnessHttpClient(
            rest_base=config.endpoint_rest_base,
            request_timeout_s=config.request_timeout_s,
            allow_plaintext_for_tests=True,
        ),
        credential_session=session,
        date_source=FakeKstDateSource(_DATE),
    )
    return witness


def _queue_broker(server: FakeKisGetServer) -> None:
    empty_orders: dict[str, object] = {"rt_cd": "0", "output1": []}
    server.queue_response(ORDER_PATH, status=200, body=empty_orders)  # the plan's read
    server.queue_response(
        BALANCE_PATH,
        status=200,
        body={
            "rt_cd": "0",
            "output1": [],
            "output2": [{"dnca_tot_amt": "10000000"}],
            "ctx_area_fk100": "",
            "ctx_area_nk100": "",
        },
        headers={"tr_cont": "D"},
    )
    server.queue_response(ORDER_PATH, status=200, body=empty_orders)  # the snapshot's


def test_a_healthy_paced_snapshot_is_aged_from_its_first_get_and_served(
    get_server: FakeKisGetServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One FETCH at S = 2000: token POST + the plan's order GET, then the snapshot's balance and
    order GETs, each a full interval after the previous one. APPLY comes one loop pass later and
    asks with the smallest age limit compose admits (2 x S): the snapshot is SERVED, and its
    read start is the balance GET's grant — not the instant FETCH called the prefetch, which was
    an interval earlier.

    Mutation: age from the prefetch call (the #969 origin) -> 4400 ms > 4000 -> "expired",
    the release holds forever -> red.
    """
    clock = _SleepClock(start_ms=10_000)
    monkeypatch.setattr(pacer_module, "sleep", clock.sleep)
    witness = _paced_witness(get_server, clock)
    _queue_broker(get_server)
    scope = WitnessScope(
        account=ACCOUNT,
        instrument_keys=(InstrumentKey(account=ACCOUNT, instrument="005930"),),
        order_dates=(_DATE,),
    )
    plan = FetchPlan(
        reads=((_DATE, scope),),
        targets=frozenset(),
        instrument="005930",
        deadline_ms=10**12,
        snapshot_scope=scope,
        today=_DATE,
        reproject_ids=("attempt-due-for-finality",),
    )

    result = run_fetch(
        plan, orders=witness, snapshots=witness, monotonic=clock, stop=lambda: False
    )

    snapshot = result.snapshot
    assert snapshot is not None
    assert isinstance(snapshot.outcome, WitnessSnapshot)
    # token 10000 · plan order GET 12000 · snapshot balance GET 14000 · its order GET 16000
    assert snapshot.read_started_ms == 14_000
    assert snapshot.read_finished_ms == 16_000
    assert len(get_server.all_requests) == 3

    clock.advance(_LOOP_PASS_MS)
    with witness.serving(
        snapshot, max_age_ms=2 * _INTERVAL_MS, now_ms=clock.now_ms
    ) as uses:
        assert isinstance(witness.observe(scope), WitnessSnapshot)
    assert [(u.verdict, u.age_ms) for u in uses] == [("served", 2_400)]
    assert len(get_server.all_requests) == 3  # served, not read live


@pytest.fixture
def server() -> Iterator[FakeKisServer]:
    srv = FakeKisServer()
    srv.start()
    try:
        yield srv
    finally:
        srv.stop()


def test_a_snapshot_age_limit_below_two_intervals_refuses_the_boot(
    tmp_path, config_dir, data_dir, custody_root, monkeypatch, server
) -> None:
    """Compose refuses ``release_snapshot_max_age_ms < 2 x min_send_interval_ms`` — the
    combination in which every release snapshot is served expired (R5 incident: #969's 2000
    under #970's 2000-ms pacing). Exactly 2 x S boots (the boundary is admitted)."""
    _sealed_mock_deployment(config_dir, custody_root, server, monkeypatch)
    transport = yaml.safe_load(
        (config_dir / "kis_mock_transport.yaml").read_text("utf-8")
    )
    interval = transport["min_send_interval_ms"]
    path = config_dir / "fill_observer.yaml"
    raw = yaml.safe_load(path.read_text("utf-8"))
    raw["release_snapshot_max_age_ms"] = 2 * interval - 1
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")

    with pytest.raises(FillObserverConfigError, match="two app-key request intervals"):
        _boot(tmp_path, config_dir, data_dir, custody_root)
