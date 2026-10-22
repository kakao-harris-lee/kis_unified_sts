"""CP-3 stock tenant tree ``cp3-setup-d-stock-005930`` (rescope M2, 2026-10-22).

Two things are pinned here:

1. **Drift against the LONG tree.** The stock tree is the LONG tree with the stock facts
   swapped in. Every file is either byte-identical to LONG, or differs ONLY at the parsed-YAML
   leaf paths declared below — so a later edit to LONG that is not carried over (or a stray
   edit here) is a named failure, not a silent fork.
2. **It boots and fails closed.** With the tree's own calendar and filled policies, the compose
   root binds the stock venue policy (tick 500원 = 50000 at ×100, 1 share, ``krx-stock``
   CONTINUOUS 09:00-15:30) and an attempt during the stock session sends nothing: the band is
   unsourced, so the venue step cannot admit (``VENUE_CONSTRAINT_POLICY`` header).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine.vocabulary import CommitmentStep, StageOutcome
from tos_runtime.calendar.ports import FixedWallClockReference
from tos_runtime.compose.root import compose_paper_runtime
from tos_runtime.venue import (
    load_order_construction_policy,
    load_venue_constraint_policy,
)

from . import _fixtures as fx
from .conftest import (
    _VENUE_POLICY_ACCOUNT,
    _VENUE_POLICY_ENVIRONMENT,
    _VENUE_POLICY_INSTRUMENT,
)
from .test_compose_root import _action_flow_inputs, _aggregate_inputs, _reach_trusted
from .test_deploy_config import _kst_unix_ms
from .test_deploy_policies import _filled
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
            # the three LONG-only band slots are gone, so the slot list shifts
            "slots",
        }
    ),
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
            "_model_view.shape_constraints.max_quantity",
            "_runtime.instrument_class",
            "_runtime.quantity_unit",
            "_runtime.band_source",
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


def test_the_stock_tree_has_exactly_the_long_trees_files() -> None:
    assert _files(_STOCK) == _files(_LONG)


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
    """005930 · Setup D LONG as-is · 1 share · krx-stock 09:00-15:30 · still SYNTHETIC."""
    vcp = yaml.safe_load((_STOCK / "venue_constraint_policy.yaml").read_text("utf-8"))
    shape = vcp["_model_view"]["shape_constraints"]
    assert (shape["tick_size"], shape["lot_size"], shape["max_quantity"]) == (
        50000,
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
    assert scopes["active_scope"] == "SYNTHETIC_FUTURES_ORDER"
    render = yaml.safe_load((_STOCK / "RENDER.yaml").read_text("utf-8"))
    assert render["account"] == {"env_key": "KIS_STOCK_ACCOUNT_NO"}
    assert render["direction"] == {"mode": "declared", "value": "LONG"}
    assert (_STOCK / "strategies/setup_d_long.strategy.yaml").read_bytes() == (
        _LONG / "strategies/setup_d_long.strategy.yaml"
    ).read_bytes()


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
    """``test_compose_root._compose`` with the construction's class set to ``krx-stock``.

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
        wall_clock=FixedWallClockReference(_kst_unix_ms(2026, 10, 19, hour, minute)),
    )


def test_the_stock_tree_boots_and_a_session_attempt_sends_nothing(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    venue_digest = _install_stock_tree(config_dir)
    # Monday 2026-10-19 10:00 KST — inside krx-stock CONTINUOUS.
    runtime = _boot(config_dir, data_dir, custody_root, hour=10, minute=0)
    _reach_trusted(runtime)

    bound = _rows(runtime, "VENUE_POLICY_BOUND")
    assert [row["canonical_digest"] for row in bound] == [venue_digest]
    assert runtime.venue.shape_constraints.tick_size == 50000
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
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """The stock tree's session is ``krx-stock``: 08:50 is futures CONTINUOUS, stock not."""
    _install_stock_tree(config_dir)
    runtime = _boot(config_dir, data_dir, custody_root, hour=8, minute=50)
    assert runtime.session_facts.phase_for_step3("krx-index-futures") == "CONTINUOUS"
    assert runtime.session_facts.phase_for_step3("krx-stock") != "CONTINUOUS"
    runtime.rcl_log.close()
    runtime.evidence_store.close()
