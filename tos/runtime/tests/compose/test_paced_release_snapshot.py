"""Issue #970 — the release snapshot under the app key pacer."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from typing import Any

import pytest
import tos_runtime.transport.kis_mock.pacer as pacer_module
import yaml
from tos.engine.records import InstrumentKey
from tos_runtime.compose._broker_posttrade_wiring import DeferredKisWitness
from tos_runtime.posttrade.fill_fetch import (
    FetchPlan,
    PrefetchedSnapshot,
    run_fetch,
    snapshot_key,
)
from tos_runtime.posttrade.fill_observer import FillObserverConfigError
from tos_runtime.recon.ports import WitnessScope, WitnessSnapshot, WitnessUnavailable
from tos_runtime.recon.witness_kis import KisStockBrokerWitness, KisWitnessHttpClient
from tos_runtime.transport.kis_mock.credential_session import KisCredentialSessions
from tos_runtime.transport.kis_mock.pacer import KisPacing

from ..recon._fake_kis_get_server import FakeKisGetServer
from ..recon._witness_kis_fakes import FakeKstDateSource
from ..recon.test_witness_kis import ACCOUNT, BALANCE_PATH, ORDER_PATH, _config
from ..transport.kis_mock._fakes import InMemoryCredentialCustody, RecordingEvidenceSink
from .test_kis_mock_e2e_honesty import _boot, _sealed_mock_deployment

_DATE = "20261023"
_INTERVAL_MS = 2_000
_LOOP_PASS_MS = 400


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
    server.queue_response(ORDER_PATH, status=200, body=empty_orders)
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
    server.queue_response(ORDER_PATH, status=200, body=empty_orders)


def test_a_healthy_paced_snapshot_is_aged_from_its_first_get_and_served(
    get_server: FakeKisGetServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One FETCH at S = 2000: token POST + the plan's order GET, then the snapshot's balance and"""
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
    assert snapshot.read_started_ms == 14_000
    assert snapshot.read_finished_ms == 16_000
    assert len(get_server.all_requests) == 3

    clock.advance(_LOOP_PASS_MS)
    with witness.serving(
        snapshot, max_age_ms=2 * _INTERVAL_MS, now_ms=clock.now_ms
    ) as uses:
        assert isinstance(witness.observe(scope), WitnessSnapshot)
    assert [(u.verdict, u.age_ms) for u in uses] == [("served", 2_400)]
    assert len(get_server.all_requests) == 3


_OLD_1 = "20261021"
_OLD_2 = "20261022"
_ORPHAN_B = {
    "pdno": "005930",
    "odno": "0000099999",
    "ord_dt": _DATE,
    "ord_qty": "1",
    "tot_ccld_qty": "1",
    "rmn_qty": "0",
    "cncl_yn": "N",
}


def _balance_page(*, last: bool) -> dict[str, Any]:
    return {
        "body": {
            "rt_cd": "0",
            "output1": [],
            "output2": [{"dnca_tot_amt": "10000000"}],
            "ctx_area_fk100": "" if last else "fk-1",
            "ctx_area_nk100": "" if last else "nk-1",
        },
        "headers": {"tr_cont": "D" if last else "M"},
    }


def _fetch_with(
    server: FakeKisGetServer,
    clock: _SleepClock,
    *,
    older_dates: tuple[str, ...],
    balance_pages: int,
    todays_snapshot_rows: list[dict[str, str]] | None = None,
) -> tuple[DeferredKisWitness, WitnessScope, Any]:
    """One paced FETCH: the plan's order read of today, then the release snapshot over today"""
    witness = _paced_witness(server, clock)
    empty: dict[str, object] = {"rt_cd": "0", "output1": []}
    server.queue_response(ORDER_PATH, status=200, body=empty)
    for _date in sorted(older_dates):
        server.queue_response(ORDER_PATH, status=200, body=empty)
    for page in range(balance_pages):
        server.queue_response(
            BALANCE_PATH, status=200, **_balance_page(last=page == balance_pages - 1)
        )
    server.queue_response(
        ORDER_PATH,
        status=200,
        body={"rt_cd": "0", "output1": todays_snapshot_rows or []},
    )
    scope = WitnessScope(
        account=ACCOUNT,
        instrument_keys=(InstrumentKey(account=ACCOUNT, instrument="005930"),),
        order_dates=(_DATE, *older_dates),
    )
    plan = FetchPlan(
        reads=((_DATE, WitnessScope(account=ACCOUNT, order_dates=(_DATE,))),),
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
    return witness, scope, result.snapshot


def _serve_one_pass_later(
    witness: DeferredKisWitness, scope: WitnessScope, snapshot: Any, clock: _SleepClock
) -> list[tuple[str, int]]:
    clock.advance(_LOOP_PASS_MS)
    with witness.serving(snapshot, max_age_ms=6_000, now_ms=clock.now_ms) as uses:
        try:
            witness.observe(scope)
        except Exception:  # noqa: BLE001 - the verdict below is the assertion
            pass
    return [(u.verdict, u.age_ms) for u in uses]


def test_three_receipt_dates_at_S_2000_are_served_under_the_shipped_6000(
    get_server: FakeKisGetServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """review-979 r1 HIGH (i). Receipt dates accumulate in the evidence store, and every one is"""
    clock = _SleepClock(start_ms=10_000)
    monkeypatch.setattr(pacer_module, "sleep", clock.sleep)
    witness, scope, snapshot = _fetch_with(
        get_server, clock, older_dates=(_OLD_1, _OLD_2), balance_pages=1
    )

    assert snapshot is not None and isinstance(snapshot.outcome, WitnessSnapshot)
    assert snapshot.first_request_ms == 14_000
    assert snapshot.read_started_ms == 18_000
    assert _serve_one_pass_later(witness, scope, snapshot, clock) == [("served", 2_400)]


def test_two_balance_pages_and_two_dates_are_served(
    get_server: FakeKisGetServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """review-979 r1 HIGH (ii): more than 20 holdings is a second balance page. older 14000 ·"""
    clock = _SleepClock(start_ms=10_000)
    monkeypatch.setattr(pacer_module, "sleep", clock.sleep)
    witness, scope, snapshot = _fetch_with(
        get_server, clock, older_dates=(_OLD_1,), balance_pages=2
    )

    assert snapshot is not None and isinstance(snapshot.outcome, WitnessSnapshot)
    assert (snapshot.first_request_ms, snapshot.read_started_ms) == (14_000, 16_000)
    assert _serve_one_pass_later(witness, scope, snapshot, clock) == [("served", 4_400)]


def test_older_dates_are_read_first_and_today_last_so_a_new_order_is_inside_the_window(
    get_server: FakeKisGetServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """review-979 r1 HIGH (iv), at the witness: the only rows read before the age window opens"""
    clock = _SleepClock(start_ms=10_000)
    monkeypatch.setattr(pacer_module, "sleep", clock.sleep)
    _witness, _scope, snapshot = _fetch_with(
        get_server,
        clock,
        older_dates=(_OLD_1,),
        balance_pages=1,
        todays_snapshot_rows=[_ORPHAN_B],
    )

    order = [(r.path, r.query.get("INQR_STRT_DT")) for r in get_server.all_requests]
    assert order == [
        (ORDER_PATH, _DATE),
        (ORDER_PATH, _OLD_1),
        (BALANCE_PATH, None),
        (ORDER_PATH, _DATE),
    ]
    assert snapshot is not None and isinstance(snapshot.outcome, WitnessSnapshot)
    assert any(
        (o.broker_execution_id or "").endswith("99999") for o in snapshot.outcome.orders
    )


def test_an_expiry_says_whether_the_read_itself_outran_the_limit() -> None:
    """review-979 r1 HIGH: the HOLD stays (fail closed), but the evidence row tells an operator"""
    scope = WitnessScope(account=ACCOUNT, order_dates=(_DATE,))
    witness = DeferredKisWitness(lambda: _DATE)

    def _snap(started: int, finished: int) -> PrefetchedSnapshot:
        return PrefetchedSnapshot(
            key=snapshot_key(scope),
            today=_DATE,
            outcome=WitnessSnapshot(observed_at_generation=None, orders=()),
            read_started_ms=started,
            read_finished_ms=finished,
            first_request_ms=started - 2_000,
        )

    reasons = []
    for snap in (_snap(1_000, 8_000), _snap(1_000, 3_000)):
        with witness.serving(snap, max_age_ms=6_000, now_ms=lambda: 9_000) as uses:
            with pytest.raises(WitnessUnavailable):
                witness.observe(scope)
        reasons.append([(u.verdict, u.reason) for u in uses])

    assert reasons == [
        [("expired", "read_span_exceeds_max_age")],
        [("expired", "aged_before_apply")],
    ]


def test_a_snapshot_age_limit_below_two_intervals_refuses_the_boot(
    tmp_path, config_dir, data_dir, custody_root, monkeypatch, server
) -> None:
    """Compose refuses ``release_snapshot_max_age_ms < 2 x min_send_interval_ms`` — the"""
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


@pytest.mark.parametrize(
    ("bounds", "message"),
    [
        (lambda s: (3 * s - 1, 2 * s), "the double read that refreshes it"),
        (lambda s: (3 * s, 3 * s + 1), "poll period plus the double read"),
        (lambda _s: (12_000, 12_000), "poll period plus the double read"),
        (lambda _s: (6_000, 6_000), "poll period plus the double read"),
    ],
    ids=[
        "below-the-double-read",
        "below-one-poll-period-plus-the-read",
        "the-1010-stock-tree",
        "max-age-equal-to-poll",
    ],
)
def test_an_unreachable_held_position_age_limit_refuses_the_boot(
    tmp_path,
    config_dir,
    data_dir,
    custody_root,
    monkeypatch,
    server,
    bounds,
    message,
) -> None:
    """The CLOSE proof's bound is read from the same pacer as its release sibling above, so it"""
    _sealed_mock_deployment(config_dir, custody_root, server, monkeypatch)
    transport = yaml.safe_load(
        (config_dir / "kis_mock_transport.yaml").read_text("utf-8")
    )
    max_age_ms, poll_interval_ms = bounds(transport["min_send_interval_ms"])
    path = config_dir / "fill_observer.yaml"
    raw = yaml.safe_load(path.read_text("utf-8"))
    raw["held_position_max_age_ms"] = max_age_ms
    raw["held_position_poll_interval_ms"] = poll_interval_ms
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")

    with pytest.raises(FillObserverConfigError, match=message):
        _boot(tmp_path, config_dir, data_dir, custody_root)
