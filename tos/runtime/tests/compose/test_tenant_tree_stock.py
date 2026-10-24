"""CP-3 stock tenant tree ``cp3-setup-d-stock-005930`` (rescope M2, 2026-10-22).

Two things are pinned here:

1. **Drift against the LONG tree.** The stock tree is the LONG tree with the stock facts
   swapped in. Every file is either byte-identical to LONG, or differs ONLY at the parsed-YAML
   leaf paths declared below — so a later edit to LONG that is not carried over (or a stray
   edit here) is a named failure, not a silent fork.
2. **It boots with kis-mock and fails closed.** With the tree's own calendar and filled
   policies, the compose root binds the stock venue policy (KRX tick ladder at ×100, 1 share,
   ``krx-stock`` CONTINUOUS 09:00-15:30) under ``--transport kis-mock`` — the only transport
   this MOCK order tree pairs with — and an attempt during the stock session sends nothing:
   the band is unsourced, so the venue step cannot admit (``VENUE_CONSTRAINT_POLICY`` header).
   The tree's OWN ``order_construction_policy.yaml`` is what boots (generation 4, B3): the
   fixture helper that writes ``kis_mock_transport.yaml`` also rewrites the OCP, so the stock
   OCP is installed after it.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine.vocabulary import CommitmentStep, StageOutcome
from tos.venue import OrderAdmissibilityResult, OrderShapeFields
from tos.venue.predicates import order_shape_admissible
from tos_runtime.calendar.ports import FixedWallClockReference
from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.compose._venue_wiring import VenuePolicyScopeMismatch
from tos_runtime.compose.root import compose_paper_runtime
from tos_runtime.venue import (
    load_order_construction_policy,
    load_venue_constraint_policy,
)

from ..transport.kis_mock._fake_kis_server import FakeKisServer
from . import _fixtures as fx
from .conftest import (
    _VENUE_POLICY_ACCOUNT,
    _VENUE_POLICY_ENVIRONMENT,
    _VENUE_POLICY_INSTRUMENT,
)
from .test_compose_root import _action_flow_inputs, _aggregate_inputs, _reach_trusted
from .test_deploy_config import _kst_unix_ms
from .test_deploy_policies import _filled
from .test_kis_mock_e2e_honesty import _sealed_mock_deployment
from .test_venue_wiring import _kind_count, _rewrite_activation, _rows

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_REPO_ROOT = Path(__file__).resolve().parents[4]
_LONG = _REPO_ROOT / "config" / "tos_runtime" / "cp3-setup-d-long"
_STOCK = _REPO_ROOT / "config" / "tos_runtime" / "cp3-setup-d-stock-005930"
_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: file -> the parsed-YAML leaf paths allowed to differ from LONG. ``None`` = prose file.
_DIFFERS_FROM_LONG: dict[str, frozenset[str] | None] = {
    "README.md": None,
    "RENDER.yaml": frozenset(
        {
            "tree_id",
            "account.env_key",
            # the one stock code --instrument must match (#926 LOW, #936 MEDIUM)
            "instrument",
            # the producer market feeding the tree (#936 review LOW-1)
            "market",
            # B2: broker_scopes.yaml::instance_path, rewritten to the source checkout's file
            # (the slot LONG does not have — LONG's boot never reads the INSTANCE)
            "slots.23",
        }
    ),
    # PR-3a (운영자 결정 2026-10-23): this tree, and only this tree, is the MOCK order tree.
    "broker_scopes.yaml": frozenset({"active_scope", "scopes.2.profile_evidence_ok"}),
    "coordinator_preconditions.yaml": frozenset({"nonlive_broker_consuming.admitted"}),
    "egress_coordinates.yaml": frozenset({"endpoint.value", "route_identity.value"}),
    "construction.yaml": frozenset({"instrument_class"}),
    "marketfeed.yaml": frozenset({"instrument_class", "unit"}),
    "aggregate_risk_policy.yaml": frozenset(
        {"policy_id", "_runtime.unit", "risk_dimensions.0"}
    ),
    "action_flow_policy.yaml": frozenset({"policy_id"}),
    "critical_input_policy.yaml": frozenset({"policy_id", "issuer_principal_id"}),
    "safety_envelope.yaml": frozenset({"envelope.governed_dimensions.0.unit"}),
    "safety_profile.yaml": frozenset({"profile.governed_dimensions.0.unit"}),
    "order_construction_policy.yaml": frozenset(
        {
            "policy_id",
            "unit_multiplier_currency_and_numeric_rules.0",
            "_runtime.construction.effect_dimensions.0.unit",
            # B3, generation 4: the kis-mock wire codec — and the generation bump and approval
            # line that a content change to an issued policy carries (header PROVENANCE).
            "_runtime.wire_codec",
            "policy_generation",
            "_model_view.policy_generation",
            "approved_by.3",
        }
    ),
    "venue_constraint_policy.yaml": frozenset(
        {
            "policy_id",
            "approved_by",
            "effective_from",
            "scope.market_segments.0",
            "approved_sources",
            "session_phase_state_machines.0",
            "instrument_and_contract_rules.0",
            "price_band_tick_and_lot_rules",
            "residual_risks",
            "_model_view.shape_constraints.tick_size",
            "_model_view.shape_constraints.price_band_ticks",
            "_model_view.shape_constraints.max_quantity",
            "_runtime.instrument_class",
            "_runtime.quantity_unit",
        }
    ),
}


def _files(tree: Path) -> set[str]:
    return {str(p.relative_to(tree)) for p in tree.rglob("*") if p.is_file()}


def _leaves(node: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(node, dict):
        out: dict[str, Any] = {}
        for key, value in node.items():
            out.update(_leaves(value, f"{prefix}{key}."))
        return out or {prefix.rstrip("."): {}}
    if isinstance(node, list):
        out = {}
        for index, value in enumerate(node):
            out.update(_leaves(value, f"{prefix}{index}."))
        return out or {prefix.rstrip("."): []}
    return {prefix.rstrip("."): node}


def _differing_paths(name: str) -> set[str]:
    long_leaves = _leaves(yaml.safe_load((_LONG / name).read_text(encoding="utf-8")))
    stock_leaves = _leaves(yaml.safe_load((_STOCK / name).read_text(encoding="utf-8")))
    return {
        key
        for key in set(long_leaves) | set(stock_leaves)
        if long_leaves.get(key, object()) != stock_leaves.get(key, object())
    }


def _covered(path: str, allowed: frozenset[str]) -> bool:
    return any(path == a or path.startswith(a + ".") for a in allowed)


#: Files only the stock tree carries: item 12's GET-only mock-account facts (PR-3a) and the
#: post-ACK fill observer / stock broker witness config (PR-3b).
_STOCK_ONLY = {"broker_facts.yaml", "fill_observer.yaml"}


def test_the_stock_tree_has_exactly_the_long_trees_files() -> None:
    assert _files(_STOCK) == _files(_LONG) | _STOCK_ONLY


@pytest.mark.parametrize("name", sorted(_files(_LONG)))
def test_every_file_is_a_byte_copy_or_differs_only_where_declared(name: str) -> None:
    long_bytes = (_LONG / name).read_bytes()
    stock_bytes = (_STOCK / name).read_bytes()
    if name not in _DIFFERS_FROM_LONG:
        assert stock_bytes == long_bytes, f"{name} must stay a byte copy of LONG"
        return
    assert stock_bytes != long_bytes, f"{name} is declared different but is identical"
    allowed = _DIFFERS_FROM_LONG[name]
    if allowed is None:
        return
    differing = _differing_paths(name)
    stray = sorted(p for p in differing if not _covered(p, allowed))
    assert stray == [], f"{name}: undeclared differences {stray}"
    unused = sorted(
        a for a in allowed if not any(_covered(p, frozenset({a})) for p in differing)
    )
    assert unused == [], f"{name}: declared but not different {unused}"


def test_the_stock_tree_carries_the_operator_decisions() -> None:
    """005930 · Setup D LONG as-is · 1 share · krx-stock 09:00-15:30 · MOCK order (PR-3a)."""
    vcp = yaml.safe_load((_STOCK / "venue_constraint_policy.yaml").read_text("utf-8"))
    shape = vcp["_model_view"]["shape_constraints"]
    assert (shape["tick_size"], shape["lot_size"], shape["max_quantity"]) == (
        None,
        1,
        1,
    )
    assert vcp["_runtime"] == {
        "instrument_class": "krx-stock",
        "quantity_unit": "SHARES",
        "currency": "KRW",
        # Kept from LONG (PR #927 review M1): a kis-mock boot refuses unless the transport's
        # `price_scale` equals this one.
        "price_scale": 100,
        # PR-3a: the LONG tree's producer_journal band block, fed by the stock band probe.
        "band_source": yaml.safe_load(
            (_LONG / "venue_constraint_policy.yaml").read_text("utf-8")
        )["_runtime"]["band_source"],
    }
    calendar = yaml.safe_load((_STOCK / "calendar.yaml").read_text("utf-8"))
    continuous = [
        w for w in calendar["sessions"]["krx-stock"] if w["phase"] == "CONTINUOUS"
    ]
    assert [(w["start"], w["end"]) for w in continuous] == [("09:00", "15:30")]
    ocp = yaml.safe_load((_STOCK / "order_construction_policy.yaml").read_text("utf-8"))
    sizing = ocp["_runtime"]["construction"]["sizing"]
    assert (sizing["max_quantity"], sizing["min_quantity"]) == (1, 1)
    scopes = yaml.safe_load((_STOCK / "broker_scopes.yaml").read_text("utf-8"))
    assert scopes["active_scope"] == "MOCK_STOCK_ORDER"
    (mock,) = [s for s in scopes["scopes"] if s["name"] == "MOCK_STOCK_ORDER"]
    assert mock["profile_evidence_ok"] is True
    pre = yaml.safe_load((_STOCK / "coordinator_preconditions.yaml").read_text("utf-8"))
    assert pre == {
        "live_authorization_state": "NOT_AUTHORIZED",
        "nonlive_broker_consuming": {"admitted": True},
    }
    # the LONG/SHORT trees stay synthetic and unadmitted
    for tree in ("cp3-setup-d-long", "cp3-setup-d-short"):
        other = _REPO_ROOT / "config" / "tos_runtime" / tree
        assert (
            yaml.safe_load((other / "broker_scopes.yaml").read_text("utf-8"))[
                "active_scope"
            ]
            == "SYNTHETIC_FUTURES_ORDER"
        )
    render = yaml.safe_load((_STOCK / "RENDER.yaml").read_text("utf-8"))
    assert render["account"] == {"env_key": "KIS_STOCK_ACCOUNT_NO"}
    assert render["direction"] == {"mode": "declared", "value": "LONG"}
    assert (_STOCK / "strategies/setup_d_long.strategy.yaml").read_bytes() == (
        _LONG / "strategies/setup_d_long.strategy.yaml"
    ).read_bytes()


def _stock_policy(tmp_path: Path) -> Any:
    raw = _filled(
        _STOCK / "venue_constraint_policy.yaml",
        environment=_VENUE_POLICY_ENVIRONMENT,
        account=_VENUE_POLICY_ACCOUNT,
        instrument=_VENUE_POLICY_INSTRUMENT,
    )
    path = tmp_path / "venue_constraint_policy.yaml"
    path.write_text(
        yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return load_venue_constraint_policy(path, scheme=_SCHEME)


@pytest.mark.parametrize(
    ("won", "expected"),
    [
        # 199,900원 — the 100원 rung. The old flat 500원 tick refused this legal price.
        ("199900", OrderAdmissibilityResult.ADMISSIBLE),
        ("199950", OrderAdmissibilityResult.INADMISSIBLE),
        ("270000", OrderAdmissibilityResult.ADMISSIBLE),  # 005930's own rung, 500원
        ("270100", OrderAdmissibilityResult.INADMISSIBLE),
        # Exact rung edges (#929 review LOW): each first price of a rung sits on the new,
        # coarser tick; the next price up is off it.
        ("1999", OrderAdmissibilityResult.ADMISSIBLE),  # top of the 1원 rung
        ("2001", OrderAdmissibilityResult.INADMISSIBLE),  # 5원 rung starts at 2,000
        ("200000", OrderAdmissibilityResult.ADMISSIBLE),  # 500원 rung's first price
        ("200100", OrderAdmissibilityResult.INADMISSIBLE),
        ("500000", OrderAdmissibilityResult.ADMISSIBLE),  # 1,000원 rung's first price
        ("500500", OrderAdmissibilityResult.INADMISSIBLE),
        ("1001000", OrderAdmissibilityResult.ADMISSIBLE),  # 1,000원 rung
        ("1000500", OrderAdmissibilityResult.INADMISSIBLE),
        (
            "10000000",
            OrderAdmissibilityResult.UNKNOWN,
        ),  # above the table — never widened
    ],
)
def test_the_stock_tree_tick_ladder_resolves_each_rung(
    tmp_path: Path, won: str, expected: OrderAdmissibilityResult
) -> None:
    """The REAL stock file's ``price_band_ticks`` (×100), through the kernel predicate. The
    band is unsourced on this tree, so it is filled here: the TICK is what is under test.
    """
    loaded = _stock_policy(tmp_path)
    assert loaded.policy.shape_constraints.tick_size is None
    constraints = loaded.policy.shape_constraints.model_copy(
        update={"price_min": 0, "price_max": 10**12}
    )
    shape = OrderShapeFields(
        price=int(won) * loaded.price_scale,
        quantity=1,
        order_type="LIMIT",
        tif="DAY",
        side="BUY",
        position_effect="OPEN",
        silently_rounded=False,
    )
    assert order_shape_admissible(shape, constraints) is expected


def test_the_stock_tree_tick_ladder_is_contiguous_from_one_won(tmp_path: Path) -> None:
    """No gap between rungs: every ×100 integer from 1원 to the top row's bound has a row."""
    rows = _stock_policy(tmp_path).policy.shape_constraints.price_band_ticks
    assert rows is not None and rows[0].band_min == 100
    for below, above in zip(rows, rows[1:]):
        assert above.band_min == below.band_max + 1


def test_the_stock_tree_states_the_price_scale_a_kis_mock_boot_checks(
    tmp_path: Path,
) -> None:
    """PR #927 review M1: ``ORD_UNPR = price / price_scale`` must divide by the scale the
    sealed price is in. The loaded policy — what ``_cross_check_price_scale`` reads — says
    100 (×100, ``close_x100``)."""
    raw = _filled(
        _STOCK / "venue_constraint_policy.yaml",
        environment=_VENUE_POLICY_ENVIRONMENT,
        account=_VENUE_POLICY_ACCOUNT,
        instrument=_VENUE_POLICY_INSTRUMENT,
    )
    path = tmp_path / "venue_constraint_policy.yaml"
    path.write_text(
        yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    assert load_venue_constraint_policy(path, scheme=_SCHEME).price_scale == 100


# ---------------------------------------------------------------------------
# boot + one stock-session attempt
# ---------------------------------------------------------------------------


def _install_stock_tree(config_dir: Path) -> str:
    """The stock tree's calendar + its two filled venue policies over the fixture tree."""
    calendar_text = (_STOCK / "calendar.yaml").read_text(encoding="utf-8")
    (config_dir / "calendar.yaml").write_text(calendar_text, encoding="utf-8")
    time_path = config_dir / "time.yaml"
    time_cfg = yaml.safe_load(time_path.read_text(encoding="utf-8"))
    time_cfg["trading_calendar_version"] = yaml.safe_load(calendar_text)[
        "calendar_version"
    ]
    time_path.write_text(yaml.safe_dump(time_cfg, sort_keys=False), encoding="utf-8")
    for name in ("venue_constraint_policy.yaml", "order_construction_policy.yaml"):
        raw = _filled(
            _STOCK / name,
            environment=_VENUE_POLICY_ENVIRONMENT,
            account=_VENUE_POLICY_ACCOUNT,
            instrument=_VENUE_POLICY_INSTRUMENT,
        )
        (config_dir / name).write_text(
            yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
    venue = load_venue_constraint_policy(
        config_dir / "venue_constraint_policy.yaml", scheme=_SCHEME
    )
    ocp = load_order_construction_policy(
        config_dir / "order_construction_policy.yaml", scheme=_SCHEME
    )
    _rewrite_activation(
        config_dir,
        [
            {
                "kind": kind,
                "member_id": loaded.policy.policy_id,
                "generation": loaded.policy.policy_generation,
                "digest": loaded.policy.canonical_digest,
                "resolved": True,
                "immutable": True,
            }
            for kind, loaded in (
                ("VENUE_CONSTRAINT_POLICY", venue),
                ("ORDER_CONSTRUCTION_POLICY", ocp),
            )
        ],
    )
    digest = venue.policy.canonical_digest
    assert digest is not None, "the loaded stock VCP carries no canonical_digest"
    return digest


def _boot(config_dir, data_dir, custody_root, *, hour: int, minute: int):
    """``test_compose_root._compose`` with the construction's class set to ``krx-stock`` and
    the kis-mock transport (PR-3a: the stock tree is the MOCK order tree).

    The venue wiring requires the construction's ``instrument_class`` to equal the policy's,
    so the fixture's futures class would refuse the stock policy at boot.
    """
    fx.write_band_strategy_file(config_dir)
    return compose_paper_runtime(
        config_dir,
        data_dir,
        custody_root,
        "non-live-test",
        construction=fx.construction_config(instrument_class="krx-stock"),
        aggregate_risk_inputs_provider=_aggregate_inputs,
        action_flow_inputs_provider=_action_flow_inputs,
        transport_kind=TransportKind.KIS_MOCK,
        wall_clock=FixedWallClockReference(_kst_unix_ms(2026, 10, 19, hour, minute)),
    )


@pytest.fixture()
def server() -> Iterator[FakeKisServer]:
    srv = FakeKisServer()
    srv.start()
    try:
        yield srv
    finally:
        srv.stop()


def _mock_stock_deployment(config_dir, custody_root, server, monkeypatch) -> str:
    """The fixture tree sealed to the fake KIS host (dry_run), THEN the stock tree's files."""
    _sealed_mock_deployment(
        config_dir, custody_root, server, monkeypatch, mode="dry_run"
    )
    return _install_stock_tree(config_dir)


def test_the_stock_tree_boots_and_a_session_attempt_sends_nothing(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
    server,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    venue_digest = _mock_stock_deployment(config_dir, custody_root, server, monkeypatch)
    # Monday 2026-10-19 10:00 KST — inside krx-stock CONTINUOUS.
    runtime = _boot(config_dir, data_dir, custody_root, hour=10, minute=0)
    _reach_trusted(runtime)

    bound = _rows(runtime, "VENUE_POLICY_BOUND")
    assert [row["canonical_digest"] for row in bound] == [venue_digest]
    # The booted service carries the ladder, not a flat tick (the table is the one source).
    assert runtime.venue.shape_constraints.tick_size is None
    ticks = runtime.venue.shape_constraints.price_band_ticks
    assert ticks is not None and len(ticks) == 7
    assert runtime.venue.quantity_constraint.max_quantity == 1
    assert runtime.session_facts.phase_for_step3("krx-stock") == "CONTINUOUS"

    results = runtime.run_once((fx.crossing_event(),))
    flow = results[0].flow
    assert flow is not None
    verdicts = {v.step: v for v in flow.verdicts}
    # Construction admits (1 share, krx-stock), then the venue step is UNKNOWN — the band is
    # unsourced in this tree — so the sequence halts there and nothing is sealed or sent.
    assert verdicts[CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION].outcome is (
        StageOutcome.ADMIT
    )
    assert verdicts[CommitmentStep.VENUE_ADMISSIBILITY_DECISION].outcome is (
        StageOutcome.UNKNOWN
    )
    assert set(verdicts) == {
        CommitmentStep.DECISION_PROPOSAL,
        CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION,
        CommitmentStep.VENUE_ADMISSIBILITY_DECISION,
    }
    assert _kind_count(runtime, "SEND_SEALED") == 0

    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_at_0850_the_futures_session_is_open_but_the_stock_one_is_not(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
    server,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The stock tree's session is ``krx-stock``: 08:50 is futures CONTINUOUS, stock not."""
    _mock_stock_deployment(config_dir, custody_root, server, monkeypatch)
    runtime = _boot(config_dir, data_dir, custody_root, hour=8, minute=50)
    assert runtime.session_facts.phase_for_step3("krx-index-futures") == "CONTINUOUS"
    assert runtime.session_facts.phase_for_step3("krx-stock") != "CONTINUOUS"
    runtime.rcl_log.close()
    runtime.evidence_store.close()


def test_the_stock_ocp_declares_the_kis_mock_wire_codec_and_a_null_one_refuses_the_boot(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    server,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B3 (2026-10-24 dry-run). Generation 3 of this tree's OCP said ``wire_codec: null``, and
    a kis-mock boot of it refused. Generation 4 declares the codec the transport checks —
    kind and the codec module's own nine fields, compared as a set exactly as the boot does.
    The red half is the measured failure: the same tree with the leaf put back to ``null``.
    """
    from tos_runtime.transport.kis_mock.codec import KIS_ORDER_CASH_WIRE_FIELDS

    ocp = load_order_construction_policy(
        _write_filled(config_dir.parent, "order_construction_policy.yaml"),
        scheme=_SCHEME,
    )
    assert ocp.wire_codec_kind == "kis-order-cash-v1"
    assert ocp.wire_fields == KIS_ORDER_CASH_WIRE_FIELDS
    assert ocp.policy.policy_generation == 4

    _mock_stock_deployment(config_dir, custody_root, server, monkeypatch)
    path = config_dir / "order_construction_policy.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw["_runtime"]["wire_codec"] = None
    path.write_text(
        yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    with pytest.raises(VenuePolicyScopeMismatch, match="kis-order-cash-v1"):
        _boot(config_dir, data_dir, custody_root, hour=10, minute=0)


def _write_filled(directory: Path, name: str) -> Path:
    raw = _filled(
        _STOCK / name,
        environment=_VENUE_POLICY_ENVIRONMENT,
        account=_VENUE_POLICY_ACCOUNT,
        instrument=_VENUE_POLICY_INSTRUMENT,
    )
    path = directory / name
    path.write_text(
        yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return path


# ---------------------------------------------------------------------------
# PR-3a: the committed MOCK posture is self-consistent
# ---------------------------------------------------------------------------


def test_the_stock_trees_mock_scope_egress_and_broker_facts_agree() -> None:
    """The three facts item 5 / item 6 / item 12 read off this tree, pinned against their own
    sources: the active scope is the kernel's mock class; the sealed egress endpoint is the
    MOCK_VTS INSTANCE host's order-cash URL (the runbook's ``order_path`` proposal); and the
    GET-only broker-facts config loads."""
    from tos.brokercap import mock_order_without_position_or_cash
    from tos_runtime.brokercap import load_broker_scopes
    from tos_runtime.brokercap.instance import load_instance_documents
    from tos_runtime.transport.kis_mock.broker_facts import load_broker_facts_config

    scopes = load_broker_scopes(
        _STOCK / "broker_scopes.yaml", environment_label="paper"
    )
    assert scopes.active_scope.name == "MOCK_STOCK_ORDER"
    assert mock_order_without_position_or_cash(scopes.active_scope.capability_tuples)

    assert scopes.instance_path is not None
    (mock_doc,) = [
        d
        for d in load_instance_documents(scopes.instance_path)
        if d.environment == "MOCK_VTS"
    ]
    egress = yaml.safe_load((_STOCK / "egress_coordinates.yaml").read_text("utf-8"))
    assert egress["endpoint"]["value"] == (
        f"{mock_doc.rest_base}/uapi/domestic-stock/v1/trading/order-cash"
    )
    assert (
        "openapivts" in egress["endpoint"]["value"]
    )  # the 모의 host, never the real one

    facts = load_broker_facts_config(_STOCK / "broker_facts.yaml")
    assert facts.balance_tr_id.startswith("V")
