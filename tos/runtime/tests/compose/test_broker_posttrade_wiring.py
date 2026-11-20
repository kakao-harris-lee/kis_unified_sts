"""Which boots take post-trade facts from the broker (PR-3b) — and which keep the synthetic ones."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from tos.brokercap import mock_order_without_position_or_cash
from tos.engine.records import EgressResultPayload, InstrumentKey
from tos.engine.vocabulary import EgressResultKind
from tos_runtime.brokercap import load_broker_scopes
from tos_runtime.compose._broker_posttrade_wiring import (
    DeferredKisWitness,
    _refuse_unreachable_held_position_age,
)
from tos_runtime.posttrade.broker_finality import BrokerFinalityProducer
from tos_runtime.posttrade.config import FinalityConfig
from tos_runtime.posttrade.fill_fetch import PrefetchedSnapshot, snapshot_key
from tos_runtime.posttrade.fill_observer import (
    FillObserverConfigError,
    load_fill_observer_config,
    odno_key,
)
from tos_runtime.posttrade.finality import SyntheticFinalityProducer
from tos_runtime.recon.ports import WitnessScope, WitnessSnapshot, WitnessUnavailable
from tos_runtime.recon.witness_kis_config import KisWitnessConfigError
from tos_runtime.recon.witness_synthetic import SyntheticLedgerWitness
from tos_runtime.recovery.reconciliation import _build_reconciliation_service

from ._fixtures import SCHEME
from .test_compose_root import _compose, _reach_trusted
from .test_kis_mock_e2e_honesty import _boot, _sealed_mock_deployment

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_TREES = Path(__file__).resolve().parents[4] / "config/tos_runtime"
_STOCK = _TREES / "cp3-setup-d-stock-005930"


@pytest.mark.parametrize(
    ("tree", "broker"),
    [
        ("paper", False),
        ("cp3-setup-d-long", False),
        ("cp3-setup-d-short", False),
        ("cp3-setup-d-stock-005930", True),
    ],
)
def test_only_the_stock_tree_is_a_broker_posttrade_tree(
    tree: str, broker: bool
) -> None:
    """The committed trees: only the stock one has the mock-order class AND a"""
    raw = yaml.safe_load((_TREES / tree / "broker_scopes.yaml").read_text("utf-8"))
    (active,) = [s for s in raw["scopes"] if s["name"] == raw["active_scope"]]
    scopes = load_broker_scopes(
        _TREES / tree / "broker_scopes.yaml", environment_label="paper"
    )
    assert scopes.active_scope.name == active["name"]
    assert (
        mock_order_without_position_or_cash(scopes.active_scope.capability_tuples)
        is broker
    )
    assert (_TREES / tree / "fill_observer.yaml").is_file() is broker


def test_synthetic_boot_keeps_the_synthetic_witness_and_producer(
    tmp_path, config_dir, data_dir, custody_root
) -> None:
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    _reach_trusted(runtime)
    consumer = runtime.driver._release_consumer  # noqa: SLF001
    assert isinstance(
        consumer.recon_service._witness, SyntheticLedgerWitness
    )  # noqa: SLF001
    assert type(consumer.finality_producer) is SyntheticFinalityProducer
    assert (
        type(runtime.driver._finality_producer) is SyntheticFinalityProducer
    )  # noqa: SLF001
    assert runtime.fill_observer is None
    assert runtime.broker_witness_provenance == "synthetic-ledger"
    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_stock_mock_boot_refuses_without_fill_observer_yaml(
    tmp_path, config_dir, data_dir, custody_root, monkeypatch, server
) -> None:
    _sealed_mock_deployment(config_dir, custody_root, server, monkeypatch)
    (config_dir / "fill_observer.yaml").unlink()
    with pytest.raises(FillObserverConfigError):
        _boot(tmp_path, config_dir, data_dir, custody_root)


def test_stock_mock_boot_refuses_a_real_tr_id(
    tmp_path, config_dir, data_dir, custody_root, monkeypatch, server
) -> None:
    _sealed_mock_deployment(config_dir, custody_root, server, monkeypatch)
    path = config_dir / "fill_observer.yaml"
    raw = yaml.safe_load(path.read_text("utf-8"))
    raw["order_inquiry_tr_id"] = "TTTC0081R"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(KisWitnessConfigError, match="TTTC0081R"):
        _boot(tmp_path, config_dir, data_dir, custody_root)


def test_the_shipped_held_position_bounds_clear_the_boot_floors() -> None:
    """The shipped CLOSE-proof bounds clear both boot floors at the operator-approved pacing,"""
    approved_interval_ms = 2_000
    path = _STOCK / "fill_observer.yaml"
    config = load_fill_observer_config(path)
    max_age_ms = config.held_position_max_age_ms
    poll_interval_ms = config.held_position_poll_interval_ms
    assert max_age_ms is not None and poll_interval_ms is not None

    _refuse_unreachable_held_position_age(
        max_age_ms, poll_interval_ms, approved_interval_ms, path
    )
    with pytest.raises(
        FillObserverConfigError, match="poll period plus the double read"
    ):
        _refuse_unreachable_held_position_age(
            poll_interval_ms, poll_interval_ms, approved_interval_ms, path
        )


def test_the_committed_fill_observer_config_loads() -> None:
    config = load_fill_observer_config(_STOCK / "fill_observer.yaml")
    assert config.witness_fields["order_inquiry_tr_id"] == "VTTC0081R"
    assert config.poll_interval_ms > 0 and config.overdue_after_ms > 0
    # 2026-11-19: 5.0 (fresh TLS per GET); still well under the order path's 10 s.
    assert 0 < config.witness_request_timeout_s <= 5.0


@pytest.mark.parametrize(
    "key", ["poll_interval_ms", "overdue_after_ms", "witness_request_timeout_s"]
)
@pytest.mark.parametrize("value", [0, -1, None, True])
def test_a_non_positive_bound_refuses(tmp_path, key, value) -> None:
    raw = yaml.safe_load((_STOCK / "fill_observer.yaml").read_text("utf-8"))
    raw[key] = value
    path = tmp_path / "fill_observer.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(FillObserverConfigError, match=key):
        load_fill_observer_config(path)


@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ("0000004470", "4470"),
        ("        4470", "4470"),
        ("4470", "4470"),
        ("0000000000", None),
        ("", None),
        (None, None),
        ("PR3A-ODNO-1", None),
        ("４４７０", None),
    ],
)
def test_odno_key(raw, key) -> None:
    assert odno_key(raw) == key


def _finality_config() -> FinalityConfig:
    return FinalityConfig(
        currency="KRW",
        value_date="T+1",
        source_revision="rev",
        proof_recipe_id="recipe",
        release_proof_wait_ms=1,
    )


def _full_fill(**overrides: object) -> EgressResultPayload:
    fields: dict[str, Any] = {
        "instrument_key": InstrumentKey(account="1234567801", instrument="005930"),
        "attempt_id": "attempt-x",
        "kind": EgressResultKind.FULL_FILL,
        "filled_quantity": Decimal(1),
        "remaining_quantity": Decimal(0),
        "broker_execution_id": "0000004470",
        "trading_date": "20261023",
    }
    fields.update(overrides)
    return EgressResultPayload(**fields)


def test_broker_producer_labels_its_proof_and_never_says_synthetic() -> None:
    produced = BrokerFinalityProducer(config=_finality_config(), scheme=SCHEME).produce(
        _full_fill()
    )
    assert produced is not None
    assert produced.record.obligation_type == "BROKER_ORDER_FQP"
    assert produced.proof.idempotency_key == "broker-fqp-proof:attempt-x"
    assert (produced.proof.proof_id or "").startswith("broker-fqp-proof")


@pytest.mark.parametrize(
    "overrides", [{"broker_execution_id": None}, {"trading_date": None}]
)
def test_broker_producer_needs_the_broker_order_identity(overrides) -> None:
    producer = BrokerFinalityProducer(config=_finality_config(), scheme=SCHEME)
    assert producer.produce(_full_fill(**overrides)) is None


def test_reconciliation_service_takes_the_injected_witness(tmp_path) -> None:
    sentinel = object()
    service = _build_reconciliation_service(
        None, None, account="a", instrument="i", witness=sentinel  # type: ignore[arg-type]
    )
    assert service._witness is sentinel  # noqa: SLF001


_ACCOUNT = "5000000001"


class _CountingWitness:
    """Stands in for the live ``KisStockBrokerWitness``: counts live reads."""

    def __init__(self) -> None:
        self.live_reads = 0

    def observe(self, scope: Any, **_kwargs: Any) -> Any:
        del scope
        self.live_reads += 1
        return WitnessSnapshot(observed_at_generation=None, orders=())


def _prefetched(scope: WitnessScope, *, started_ms: int) -> PrefetchedSnapshot:
    return PrefetchedSnapshot(
        key=snapshot_key(scope),
        today="20260914",
        outcome=WitnessSnapshot(observed_at_generation=None, orders=()),
        read_started_ms=started_ms,
        read_finished_ms=started_ms + 5,
    )


def test_an_expired_prefetched_snapshot_is_refused_without_a_live_read() -> None:
    """Past ``max_age_ms`` a matching snapshot is refused as unavailable (the release holds)"""
    scope = WitnessScope(
        account=_ACCOUNT,
        instrument_keys=(InstrumentKey(account=_ACCOUNT, instrument="005930"),),
        order_dates=("20260914",),
    )
    witness = DeferredKisWitness(lambda: "20260914")
    live = _CountingWitness()
    witness.inner = live  # type: ignore[assignment]
    now = {"ms": 10_000}

    with witness.serving(
        _prefetched(scope, started_ms=7_000), max_age_ms=2_000, now_ms=lambda: now["ms"]
    ) as uses:
        with pytest.raises(WitnessUnavailable, match="expired"):
            witness.observe(scope)
    assert live.live_reads == 0
    assert [(u.verdict, u.age_ms) for u in uses] == [("expired", 3_000)]

    with witness.serving(
        _prefetched(scope, started_ms=9_000), max_age_ms=2_000, now_ms=lambda: now["ms"]
    ) as uses:
        witness.observe(scope)
    assert live.live_reads == 0
    assert [(u.verdict, u.age_ms) for u in uses] == [("served", 1_000)]


class _DeadlineWitness:
    """Records the deadline a loop-side live read was given."""

    def __init__(self) -> None:
        self.deadlines: list[Any] = []

    def observe(self, scope: Any, **kwargs: Any) -> Any:
        del scope
        self.deadlines.append(kwargs.get("deadline_expired"))
        return WitnessSnapshot(observed_at_generation=None, orders=())


def test_a_loop_side_live_read_uses_its_own_witness_and_deadline() -> None:
    """review-1114 M2: an unserved observe on the loop is bounded by the loop's own terms."""
    scope = WitnessScope(account=_ACCOUNT)
    witness = DeferredKisWitness(lambda: "20260914", loop_deadline_ms=0)
    worker, loop = _DeadlineWitness(), _DeadlineWitness()
    witness.inner = worker  # type: ignore[assignment]
    witness.loop_inner = loop  # type: ignore[assignment]
    witness.observe(scope)
    assert worker.deadlines == []
    (deadline,) = loop.deadlines
    assert deadline is not None and deadline() is True

    unbounded = DeferredKisWitness(lambda: "20260914")
    unbounded.inner = worker  # type: ignore[assignment]
    unbounded.observe(scope)
    assert worker.deadlines == [None]


def test_the_committed_loop_side_bounds_are_tighter_than_the_worker_ones() -> None:
    config = load_fill_observer_config(_STOCK / "fill_observer.yaml")
    assert config.loop_witness_request_timeout_s is not None
    assert config.loop_witness_deadline_ms is not None
    assert config.loop_witness_request_timeout_s < config.witness_request_timeout_s
    # #1115 N1: the cap exists and leaves room above the one-date deadline for more dates.
    assert config.loop_witness_deadline_max_ms is not None
    assert config.loop_witness_deadline_max_ms > config.loop_witness_deadline_ms


class _StepClock:
    """A monotonic_ns source the test moves by hand."""

    def __init__(self) -> None:
        self.ms = 0

    def __call__(self) -> int:
        return self.ms * 1_000_000


def _multi_date_scope(*dates: str) -> WitnessScope:
    return WitnessScope(
        account=_ACCOUNT,
        instrument_keys=(InstrumentKey(account=_ACCOUNT, instrument="005930"),),
        order_dates=dates,
    )


def test_the_loop_deadline_admits_one_paced_page_per_receipt_date() -> None:
    """#1115 N1: the release reconciliation reads every receipt date, so a 3-date scope needs

    four paced GETs and its last page starts at ~6 s. The one-date deadline (3000) refused it on
    every pass, which made the loop fallback WitnessUnavailable by construction on a leaf older
    than one trading date. The deadline now scales per date, capped.
    """
    clock = _StepClock()
    witness = DeferredKisWitness(
        lambda: "20261119",
        loop_deadline_ms=3_000,
        loop_deadline_max_ms=9_000,
        loop_deadline_per_date_ms=2_000,
        monotonic_ns=clock,
    )
    loop = _DeadlineWitness()
    witness.loop_inner = loop  # type: ignore[assignment]

    three_dates = _multi_date_scope("20261117", "20261118", "20261119")
    assert witness.loop_deadline_ms_for(three_dates) == 7_000
    witness.observe(three_dates)
    (deadline,) = loop.deadlines
    assert deadline is not None
    clock.ms = 6_000  # the third order page's pacer grant
    assert deadline() is False
    clock.ms = 7_000
    assert deadline() is True

    # One date is unchanged, and the cap bounds the stall rather than the date count.
    assert witness.loop_deadline_ms_for(_multi_date_scope("20261119")) == 3_000
    assert witness.loop_deadline_ms_for(_multi_date_scope()) == 3_000
    assert (
        witness.loop_deadline_ms_for(
            _multi_date_scope("1", "2", "3", "4", "5", "6", "7")
        )
        == 9_000
    )
    # A repeated date is one page, not two (the snapshot key dedupes them the same way).
    assert witness.loop_deadline_ms_for(_multi_date_scope("1", "1")) == 3_000


def test_without_a_cap_or_a_pacing_interval_the_base_deadline_is_used_unchanged() -> (
    None
):
    """The pre-#1115 shape stays reachable: no cap configured, no scaling."""
    witness = DeferredKisWitness(lambda: "20261119", loop_deadline_ms=3_000)
    assert witness.loop_deadline_ms_for(_multi_date_scope("1", "2", "3")) == 3_000
    assert (
        DeferredKisWitness(lambda: "x").loop_deadline_ms_for(_multi_date_scope("1"))
        is None
    )


def test_a_deadline_cap_below_its_base_is_refused(tmp_path: Path) -> None:
    """A cap that would SHORTEN the one-date deadline is a misconfiguration, not a tightening."""
    raw = yaml.safe_load((_STOCK / "fill_observer.yaml").read_text("utf-8"))
    raw["loop_witness_deadline_max_ms"] = raw["loop_witness_deadline_ms"] - 1
    path = tmp_path / "fill_observer.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(FillObserverConfigError, match="below loop_witness_deadline_ms"):
        load_fill_observer_config(path)

    raw.pop("loop_witness_deadline_ms")
    raw["loop_witness_deadline_max_ms"] = 9_000
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(FillObserverConfigError, match="needs it"):
        load_fill_observer_config(path)
