"""Which boots take post-trade facts from the broker (PR-3b) — and which keep the synthetic ones.

Only the stock MOCK order tree (``kis-mock`` + ``MOCK_STOCK_ORDER``) reconciles against
``KisStockBrokerWitness`` and proves fills with ``BrokerFinalityProducer``; the paper, CP-3 LONG
and SHORT trees keep ``SyntheticLedgerWitness`` and ``SyntheticFinalityProducer``. Plus the boot
refusals of the stock wiring and the small pure pieces it rests on.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from tos.brokercap import mock_order_without_position_or_cash
from tos.engine.records import EgressResultPayload, InstrumentKey
from tos.engine.vocabulary import EgressResultKind
from tos_runtime.brokercap import load_broker_scopes
from tos_runtime.compose._broker_posttrade_wiring import DeferredKisWitness
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

from ..transport.kis_mock._fake_kis_server import FakeKisServer
from ._fixtures import SCHEME
from .test_compose_root import _compose, _reach_trusted
from .test_kis_mock_e2e_honesty import _boot, _sealed_mock_deployment

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_TREES = Path(__file__).resolve().parents[4] / "config/tos_runtime"
_STOCK = _TREES / "cp3-setup-d-stock-005930"


@pytest.fixture()
def server() -> Iterator[FakeKisServer]:
    srv = FakeKisServer()
    srv.start()
    try:
        yield srv
    finally:
        srv.stop()


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
    """The committed trees: only the stock one has the mock-order class AND a
    ``fill_observer.yaml``; the other three keep synthetic post-trade by construction.
    """
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
    raw["order_inquiry_tr_id"] = "TTTC0081R"  # the REAL 주식일별주문체결조회
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(KisWitnessConfigError, match="TTTC0081R"):
        _boot(tmp_path, config_dir, data_dir, custody_root)


def test_the_committed_fill_observer_config_loads() -> None:
    config = load_fill_observer_config(_STOCK / "fill_observer.yaml")
    assert config.witness_fields["order_inquiry_tr_id"] == "VTTC0081R"
    assert config.poll_interval_ms > 0 and config.overdue_after_ms > 0
    # #949 review HIGH (a): the observer's GETs are bounded by ITS OWN timeout, and that bound
    # has to be well under the order path's (kis_mock_transport.yaml's 10 s) — the observer is
    # read from inside the session loop's tick-to-tick window and the order path is not.
    assert 0 < config.witness_request_timeout_s <= 3.0


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
        ("        4470", "4470"),  # the measured futures inquiry padding
        ("4470", "4470"),
        ("0000000000", None),
        ("", None),
        (None, None),
        ("PR3A-ODNO-1", None),
        ("４４７０", None),  # full-width digits are not an order number
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


# -- #969 review r1 HIGH: the prefetched release snapshot has an age limit --------------------


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
    """Past ``max_age_ms`` a matching snapshot is refused as unavailable (the release holds)
    and the live witness is NOT asked — expiry must not put the broker back on the loop.
    Inside the limit it is served, also without a live read."""
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
