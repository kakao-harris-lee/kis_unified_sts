"""The stock tenant trees added for the operator's 2026-11-19 directive."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.dsl import POSITION_NAMESPACE
from tos.dsl.serialization import parse_strategy
from tos.dsl.vocabulary import DecisionKind, evaluate_policy
from tos.engine.admission import policy_work_steps, strategy_admissible
from tos.engine.vocabulary import AdmissionVerdict, CommitmentStep, StageOutcome
from tos_runtime.compose._marketfeed_wiring import load_position_context_config
from tos_runtime.strategy.bindings import (
    STRATEGY_BINDINGS_FILE_NAME,
    load_strategy_bindings,
)
from tos_runtime.strategy.loader import load_strategies
from tos_runtime.strategy.resolve import (
    POSITION_DSL_FIELDS,
    StrategyLoadError,
    _refuse_unresolvable_position_refs,
    _resolve_bindings_or_refuse,
)
from tos_runtime.venue import load_venue_constraint_policy

from . import _fixtures as fx
from .conftest import (
    _VENUE_POLICY_ACCOUNT,
    _VENUE_POLICY_ENVIRONMENT,
    _VENUE_POLICY_INSTRUMENT,
)
from .test_compose_root import _reach_trusted
from .test_deploy_policies import _filled
from .test_tenant_tree_stock import (
    _STOCK,
    _boot,
    _files,
    _leaves,
    _mock_stock_deployment,
)
from .test_venue_wiring import _kind_count, _rows

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_REPO_ROOT = Path(__file__).resolve().parents[4]
_CONFIG_ROOT = _REPO_ROOT / "config" / "tos_runtime"
_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

_PRIMARY_SYMBOL = "005930"
#: The usage plan's role split (``docs/plans/2026-11-19-tos-usage-plan.md`` §4.1, operator
#: decision 2026-11-19 §8-②): 005930 is the canary, these two carry an experiment each.
_EXPERIMENT_A = "000660"  # Setup D LONG with the M2 probe binding OFF
_EXPERIMENT_B = "005380"  # RSI / Williams %R reversion — its own strategy file

#: 실험 A's two declared position exits (P4 S4). The ids are read back off the shipped file
#: by `test_experiment_a_rule_order_*`, so a renamed rule goes red rather than untested.
_STOP_RULE_ID = "R5-EXIT-STOP-LOSS"
_TARGET_RULE_ID = "R6-EXIT-TAKE-PROFIT"

#: The DSL-visible shape of a proven-flat position, exactly as
#: ``PositionContext.as_environment_mapping`` projects it: no entry field at all.
_FLAT: dict[str, Any] = {"side": "FLAT", "held_qty": 0}


def _held(unrealized_bp: int, *, side: str = "LONG") -> dict[str, Any]:
    """One held bar's position namespace at ``unrealized_bp``, in the projected shape."""
    return {
        "side": side,
        "held_qty": 1,
        "entry_price": 10_000_000,
        "entry_price_basis": "ORDER",
        "unrealized": unrealized_bp * 1_000,
        "unrealized_bp": unrealized_bp,
        "bars_held": 3,
    }


#: What EVERY sibling differs in, because only the symbol moved.
_DIFFERS: dict[str, frozenset[str] | None] = {
    "README.md": None,
    "RENDER.yaml": frozenset({"tree_id", "instrument.pattern"}),
    "fields.yaml": frozenset(),
    "critical_input_policy.yaml": frozenset({"policy_id", "issuer_principal_id"}),
    "venue_constraint_policy.yaml": frozenset(
        {
            "policy_id",
            "approved_by",
            "effective_from",
            "instrument_and_contract_rules.0",
        }
    ),
}

#: What ONE sibling differs in because of its role. An entry here REPLACES the file's
#: :data:`_DIFFERS` row for that symbol, so a role change has to be written down twice:
#: once as the config edit and once here.
_DIFFERS_BY_SYMBOL: dict[str, dict[str, frozenset[str] | None]] = {
    _EXPERIMENT_A: {
        # P4 S4 (`docs/plans/2026-11-27-tos-p4-position-fields-plan.md` §3): this tenant is
        # the first to declare stop-loss / take-profit exits in YAML, so four of its files
        # move off 005930's. Each difference below is checked key-path by key-path, and the
        # rule content itself is pinned by `test_experiment_a_*` further down this file —
        # these entries say WHICH files may differ, not that their content is unchecked.
        #
        # The R4 probe rule stays in the strategy file and still cannot fire
        # (`test_experiment_a_is_setup_d_with_the_probe_binding_off`); it now also carries
        # the same `side EQ "FLAT"` guard as R1 so the two entry rules cannot diverge.
        "strategy_bindings.yaml": frozenset(
            {
                "strategies.setup_d_long.strategy.bindings.m2_probe_entry_enabled",
                "strategies.setup_d_long.strategy.bindings.stop_loss_bp",
                "strategies.setup_d_long.strategy.bindings.take_profit_bp",
            }
        ),
        # The position namespace is opt-in per tree and OFF by default (plan §2 D5). Only
        # this tree turns it on; a strategy that reads `capsule.position.*` while it is off
        # is a boot refusal, which
        # `test_experiment_a_declares_the_position_namespace_its_rules_read` proves here.
        "marketfeed.yaml": frozenset({"position_context"}),
        # Two new FLAT rules (R5 stop · R6 target) and the `side EQ "FLAT"` guard on both
        # entry rules. R1 keeps rule index 0 because its target DEFINES the `&account` /
        # `&instrument` anchors the new rules alias — a YAML alias before its anchor fails
        # to load at all. Listing the rule indices here only says this file may differ from
        # 005930's; the order, the rule ids and the boundary values are pinned separately by
        # `test_experiment_a_rule_order_*` below, against the SHIPPED file.
        "strategies/setup_d_long.strategy.yaml": frozenset(
            {
                "policy.rules.0.all_of",
                "policy.rules.1",
                "policy.rules.2",
                "policy.rules.3",
                "policy.rules.4",
                "policy.rules.5",
            }
        ),
        # Comment only — the static step count the budget is justified against (31 -> 51).
        "engine.yaml": frozenset(),
    },
    _EXPERIMENT_B: {
        # A different strategy altogether, so the declaration, the field list its consumers
        # apply freshness bounds to, and the bindings are all its own. The policy IDENTITY
        # keys stay pinned as everywhere else — only the lists below them move.
        "fields.yaml": frozenset({"fields", "publish"}),
        "critical_input_policy.yaml": frozenset(
            {"policy_id", "issuer_principal_id", "fields"}
        ),
        "strategy_bindings.yaml": frozenset({"strategies"}),
        # Comment only — the static step count the budget is justified against (31 -> 18).
        "engine.yaml": frozenset(),
        "RENDER.yaml": frozenset(
            {
                "tree_id",
                "instrument.pattern",
                "slots.15.file",
                "slots.16.file",
                "slots.17.file",
            }
        ),
    },
}

#: symbol -> (files the sibling has and 005930 does not, files 005930 has and it does not).
_FILE_SET_DELTA: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    _EXPERIMENT_B: (
        frozenset({"strategies/rsi_wr_reversion_long.strategy.yaml"}),
        frozenset({"strategies/setup_d_long.strategy.yaml"}),
    ),
}


def _sibling_symbols() -> tuple[str, ...]:
    """Every shipped stock tenant tree except the one the siblings derive from."""
    found = sorted(
        path.name.removeprefix("cp3-setup-d-stock-")
        for path in _CONFIG_ROOT.glob("cp3-setup-d-stock-*")
        if path.is_dir()
    )
    assert _PRIMARY_SYMBOL in found, found
    return tuple(symbol for symbol in found if symbol != _PRIMARY_SYMBOL)


_SIBLINGS = _sibling_symbols()


def _tree(symbol: str) -> Path:
    return _CONFIG_ROOT / f"cp3-setup-d-stock-{symbol}"


def _differing_paths(name: str, symbol: str) -> set[str]:
    primary = _leaves(yaml.safe_load((_STOCK / name).read_text(encoding="utf-8")))
    sibling = _leaves(
        yaml.safe_load((_tree(symbol) / name).read_text(encoding="utf-8"))
    )
    return {
        key
        for key in set(primary) | set(sibling)
        if primary.get(key, object()) != sibling.get(key, object())
    }


def _covered(path: str, allowed: frozenset[str]) -> bool:
    return any(path == a or path.startswith(a + ".") for a in allowed)


def _declared_differences(symbol: str) -> dict[str, frozenset[str] | None]:
    """The files ``symbol`` may differ in, with the role overrides applied."""
    return {**_DIFFERS, **_DIFFERS_BY_SYMBOL.get(symbol, {})}


def _expected_files(symbol: str) -> set[str]:
    added, removed = _FILE_SET_DELTA.get(symbol, (frozenset(), frozenset()))
    primary = _files(_STOCK)
    assert (
        removed <= primary
    ), f"{symbol}: declared-removed files are not in the primary tree"
    assert not (
        added & primary
    ), f"{symbol}: declared-added files already exist in the primary tree"
    return (primary - removed) | added


def test_three_stock_tenants_ship() -> None:
    """The directive's own shape: three slots need three symbols."""
    assert len(_SIBLINGS) >= 2, _SIBLINGS
    assert all(symbol.isdigit() and len(symbol) == 6 for symbol in _SIBLINGS), _SIBLINGS


@pytest.mark.parametrize("symbol", _SIBLINGS)
def test_a_sibling_tree_has_exactly_the_primary_trees_files(symbol: str) -> None:
    """Same file set as 005930, except where :data:`_FILE_SET_DELTA` says otherwise."""
    assert _files(_tree(symbol)) == _expected_files(symbol)


@pytest.mark.parametrize("symbol", _SIBLINGS)
@pytest.mark.parametrize("name", sorted(_files(_STOCK)))
def test_every_file_is_a_byte_copy_or_differs_only_where_declared(
    name: str, symbol: str
) -> None:
    _, removed = _FILE_SET_DELTA.get(symbol, (frozenset(), frozenset()))
    if name in removed:
        assert not (
            _tree(symbol) / name
        ).exists(), f"{name} is declared absent from the {symbol} tree but is present"
        return
    differs = _declared_differences(symbol)
    primary_bytes = (_STOCK / name).read_bytes()
    sibling_bytes = (_tree(symbol) / name).read_bytes()
    if name not in differs:
        assert (
            sibling_bytes == primary_bytes
        ), f"{name} must stay a byte copy of the {_PRIMARY_SYMBOL} tree"
        return
    assert (
        sibling_bytes != primary_bytes
    ), f"{name} is declared different but is identical"
    allowed = differs[name]
    if allowed is None:
        return
    differing = _differing_paths(name, symbol)
    stray = sorted(path for path in differing if not _covered(path, allowed))
    assert stray == [], f"{name}: undeclared differences {stray}"
    unused = sorted(
        a for a in allowed if not any(_covered(p, frozenset({a})) for p in differing)
    )
    assert unused == [], f"{name}: declared but not different {unused}"


@pytest.mark.parametrize("symbol", _SIBLINGS)
def test_a_sibling_tree_names_its_own_symbol_everywhere_it_matters(symbol: str) -> None:
    """Three places decide which instrument a session touches; all three must agree."""
    tree = _tree(symbol)
    render = yaml.safe_load((tree / "RENDER.yaml").read_text(encoding="utf-8"))
    assert render["tree_id"] == f"cp3-setup-d-stock-{symbol}"
    assert render["instrument"]["pattern"] == symbol
    assert render["market"] == "stock"
    assert render["account"] == {"env_key": "KIS_STOCK_ACCOUNT_NO"}
    producer = (
        _REPO_ROOT / "config" / "tos_probes" / f"cp3-live-producer-stock-{symbol}.yaml"
    )
    raw = yaml.safe_load(producer.read_text(encoding="utf-8"))
    assert raw["market"] == "stock"
    assert (
        raw["calendar_yaml"]
        == f"config/tos_runtime/cp3-setup-d-stock-{symbol}/calendar.yaml"
    )
    assert (
        raw["venue_policy_yaml"]
        == f"config/tos_runtime/cp3-setup-d-stock-{symbol}/venue_constraint_policy.yaml"
    )
    assert raw["front_month_product"] is None
    assert raw["open_anchor"] == "09:00"


@pytest.mark.parametrize("symbol", _SIBLINGS)
def test_a_sibling_has_a_contract_spec_the_producer_can_resolve(symbol: str) -> None:
    """``resolve_contract_spec`` matches by ``symbol_prefix``; without a block the"""
    execution = yaml.safe_load(
        (_REPO_ROOT / "config" / "execution.yaml").read_text(encoding="utf-8")
    )
    specs = execution["stock_contract_spec"]
    (block,) = [value for value in specs.values() if value["symbol_prefix"] == symbol]
    primary = next(
        value for value in specs.values() if value["symbol_prefix"] == _PRIMARY_SYMBOL
    )
    assert {k: v for k, v in block.items() if k != "symbol_prefix"} == {
        k: v for k, v in primary.items() if k != "symbol_prefix"
    }


@pytest.mark.parametrize("symbol", _SIBLINGS)
def test_a_sibling_tree_carries_the_same_tick_ladder_and_quantity_cap(
    symbol: str,
) -> None:
    """The ladder is chosen by price, so it is the SAME table — and 1 share stays 1."""
    primary = yaml.safe_load(
        (_STOCK / "venue_constraint_policy.yaml").read_text(encoding="utf-8")
    )
    sibling = yaml.safe_load(
        (_tree(symbol) / "venue_constraint_policy.yaml").read_text(encoding="utf-8")
    )
    assert sibling["_model_view"] == primary["_model_view"]
    assert sibling["_runtime"] == primary["_runtime"]
    assert sibling["_model_view"]["shape_constraints"]["max_quantity"] == 1
    assert sibling["scope"]["market_segments"] == ["KRX_STOCK"]
    assert sibling["policy_id"] != primary["policy_id"]
    assert symbol in sibling["policy_id"]


@pytest.mark.parametrize("symbol", _SIBLINGS)
def test_a_sibling_trees_venue_policy_loads_with_its_own_symbol(
    symbol: str, tmp_path: Path
) -> None:
    raw: Any = _filled(
        _tree(symbol) / "venue_constraint_policy.yaml",
        environment=_VENUE_POLICY_ENVIRONMENT,
        account=_VENUE_POLICY_ACCOUNT,
        instrument=symbol,
    )
    path = tmp_path / "venue_constraint_policy.yaml"
    path.write_text(
        yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    loaded = load_venue_constraint_policy(path, scheme=_SCHEME)
    assert loaded.price_scale == 100
    assert loaded.scope.instrument == symbol
    shape = loaded.policy.shape_constraints
    assert shape.tick_size is None
    assert shape.price_band_ticks is not None and len(shape.price_band_ticks) == 7


def _install_sibling_tree(config_dir: Path, symbol: str) -> str:
    """``_install_stock_tree`` for a sibling: its calendar + its two filled policies."""
    tree = _tree(symbol)
    calendar_text = (tree / "calendar.yaml").read_text(encoding="utf-8")
    (config_dir / "calendar.yaml").write_text(calendar_text, encoding="utf-8")
    time_path = config_dir / "time.yaml"
    time_cfg = yaml.safe_load(time_path.read_text(encoding="utf-8"))
    time_cfg["trading_calendar_version"] = yaml.safe_load(calendar_text)[
        "calendar_version"
    ]
    time_path.write_text(yaml.safe_dump(time_cfg, sort_keys=False), encoding="utf-8")
    for name in ("venue_constraint_policy.yaml", "order_construction_policy.yaml"):
        raw = _filled(
            tree / name,
            environment=_VENUE_POLICY_ENVIRONMENT,
            account=_VENUE_POLICY_ACCOUNT,
            instrument=_VENUE_POLICY_INSTRUMENT,
            admits_flat_exit=name == "order_construction_policy.yaml",
        )
        (config_dir / name).write_text(
            yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
    venue = load_venue_constraint_policy(
        config_dir / "venue_constraint_policy.yaml", scheme=_SCHEME
    )
    digest = venue.policy.canonical_digest
    assert digest is not None, "the loaded sibling VCP carries no canonical_digest"
    return digest


@pytest.mark.parametrize("symbol", _SIBLINGS)
def test_a_sibling_tree_boots_and_a_session_attempt_sends_nothing(
    symbol: str,
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    server,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same end as 005930's own boot test, per sibling tree."""
    _mock_stock_deployment(config_dir, custody_root, server, monkeypatch)
    venue_digest = _install_sibling_tree(config_dir, symbol)
    runtime = _boot(config_dir, data_dir, custody_root, hour=10, minute=0)
    _reach_trusted(runtime)

    assert [
        row["canonical_digest"] for row in _rows(runtime, "VENUE_POLICY_BOUND")
    ] == [venue_digest]
    assert runtime.venue.shape_constraints.tick_size is None
    ticks = runtime.venue.shape_constraints.price_band_ticks
    assert ticks is not None and len(ticks) == 7
    assert runtime.venue.quantity_constraint.max_quantity == 1
    assert runtime.session_facts.phase_for_step3("krx-stock") == "CONTINUOUS"

    results = runtime.run_once((fx.crossing_event(),))
    flow = results[0].flow
    assert flow is not None
    verdicts = {verdict.step: verdict for verdict in flow.verdicts}
    assert verdicts[CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION].outcome is (
        StageOutcome.ADMIT
    )
    assert verdicts[CommitmentStep.VENUE_ADMISSIBILITY_DECISION].outcome is (
        StageOutcome.UNKNOWN
    )
    assert _kind_count(runtime, "SEND_SEALED") == 0

    runtime.rcl_log.close()
    runtime.evidence_store.close()


# ---------------------------------------------------------------------------
# The role split: one strategy per tenant (usage plan §4.1)
# ---------------------------------------------------------------------------


def _loaded_strategy_source(symbol: str, tmp_path: Path) -> tuple[Any, Any]:
    """``symbol``'s strategies + bindings through the PRODUCTION loader.

    The committed tree carries the render's ``"TBD"`` coordinate slots, which the loader
    refuses by design, so this fills them the way ``render_paper_config.py`` does and then
    runs the real boot path — including ``_resolve_bindings_or_refuse``, the rule that
    refuses an unused or orphan binding.
    """
    tree = _tree(symbol)
    rendered = tmp_path / symbol
    (rendered / "strategies").mkdir(parents=True)
    for path in (tree / "strategies").iterdir():
        text = path.read_text(encoding="utf-8")
        text = text.replace('&account "TBD"', f'&account "{_VENUE_POLICY_ACCOUNT}"')
        text = text.replace('&instrument "TBD"', f'&instrument "{symbol}"')
        (rendered / "strategies" / path.name).write_text(text, encoding="utf-8")
    (rendered / STRATEGY_BINDINGS_FILE_NAME).write_text(
        (tree / STRATEGY_BINDINGS_FILE_NAME).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    loaded = load_strategies(
        rendered / "strategies", parse=parse_strategy, admit=strategy_admissible
    )
    bindings = load_strategy_bindings(rendered / STRATEGY_BINDINGS_FILE_NAME)
    _resolve_bindings_or_refuse(loaded, bindings)
    return loaded, bindings


def _decide(
    strategy: Any,
    resolved: dict[str, Any],
    config: dict[str, Any],
    position: dict[str, Any] | None = None,
) -> Any:
    """Evaluate the policy the engine's own way. ``position=None`` = the namespace ABSENT."""
    capsule: dict[str, Any] = {"resolved_values": resolved}
    if position is not None:
        capsule[POSITION_NAMESPACE] = position
    return evaluate_policy(strategy.policy, {"capsule": capsule, "config": config})


def test_experiment_a_is_setup_d_with_the_probe_binding_off(tmp_path: Path) -> None:
    """000660 runs R1-R3 only: the R4 rule is still there and can no longer fire."""
    loaded, bindings = _loaded_strategy_source(_EXPERIMENT_A, tmp_path)
    (entry,) = loaded.strategies
    assert entry.path.name == "setup_d_long.strategy.yaml"
    config = dict(bindings.strategies["setup_d_long.strategy"].bindings)
    assert config["m2_probe_entry_enabled"] is False
    assert config["z_entry_max_x1000"] == -1800

    strategy = entry.strategy
    # The probe's own input: entry window open, every Setup D gate false.
    probe_shaped = {
        "entry_window": True,
        "hi_vol": False,
        "stall_ok": False,
        "reversal_ok": False,
        "z_x1000": 0,
        "vwap_reverted": False,
        "eod": False,
    }
    assert _decide(strategy, probe_shaped, config, _FLAT).kind is DecisionKind.NO_ACTION
    # ...while the real Setup D entry still fires.
    gates = {
        "entry_window": True,
        "hi_vol": True,
        "stall_ok": True,
        "reversal_ok": True,
        "z_x1000": config["z_entry_max_x1000"] - 1,
    }
    r1 = _decide(strategy, gates, config, _FLAT)
    assert r1.kind is DecisionKind.ACTION
    assert r1.rationale.startswith("R1-ENTRY-LONG:")


# ---------------------------------------------------------------------------
# 실험 A's declared stop-loss / take-profit (P4 S4)
# ---------------------------------------------------------------------------


def _experiment_a(tmp_path: Path) -> tuple[Any, dict[str, Any]]:
    """The SHIPPED 000660 strategy + its SHIPPED bindings, through the production loader."""
    loaded, bindings = _loaded_strategy_source(_EXPERIMENT_A, tmp_path)
    (entry,) = loaded.strategies
    return entry.strategy, dict(bindings.strategies["setup_d_long.strategy"].bindings)


def _entry_gates(config: dict[str, Any]) -> dict[str, Any]:
    """Every Setup D entry gate satisfied — so a NO_ACTION can only be the position guard."""
    return {
        "entry_window": True,
        "hi_vol": True,
        "stall_ok": True,
        "reversal_ok": True,
        "z_x1000": config["z_entry_max_x1000"] - 1,
        "vwap_reverted": False,
        "eod": False,
    }


def test_experiment_a_declares_the_position_namespace_its_rules_read() -> None:
    """A `capsule.position.*` rule with the tree's namespace off is a boot refusal."""
    tree = _tree(_EXPERIMENT_A)
    declared = load_position_context_config(tree)
    assert declared is not None and declared.enabled is True
    # The bar period `bars_held` divides by is this tree's own 1-minute bar.
    marketfeed = yaml.safe_load((tree / "marketfeed.yaml").read_text(encoding="utf-8"))
    assert declared.bar_interval_ms == marketfeed["time_evaluate_closed_interval_ms"]

    # 005930 and 005380 stay off, which is what keeps THEIR payload path byte-identical.
    for symbol in (_PRIMARY_SYMBOL, _EXPERIMENT_B):
        assert load_position_context_config(_tree(symbol)) is None, symbol


def test_experiment_a_position_refs_resolve_only_with_the_namespace_on(
    tmp_path: Path,
) -> None:
    """The shipped tree through the boot-time check, both ways round."""
    loaded, _ = _loaded_strategy_source(_EXPERIMENT_A, tmp_path)
    _refuse_unresolvable_position_refs(loaded, position_context_enabled=True)
    with pytest.raises(StrategyLoadError, match="position_context.enabled"):
        _refuse_unresolvable_position_refs(loaded, position_context_enabled=False)

    read = {
        tuple(compare["left"]["ref"])
        for rule in yaml.safe_load(
            (
                _tree(_EXPERIMENT_A) / "strategies" / "setup_d_long.strategy.yaml"
            ).read_text(encoding="utf-8")
        )["policy"]["rules"]
        for compare in rule["all_of"]
        if compare["left"].get("ref", [None, None])[1] == POSITION_NAMESPACE
    }
    assert {ref[2] for ref in read} == {"side", "unrealized_bp"}
    assert {ref[2] for ref in read} <= set(POSITION_DSL_FIELDS)


def test_experiment_a_rule_order_is_entry_then_stop_then_target_then_the_old_exits(
    tmp_path: Path,
) -> None:
    """Order IS semantics — first match wins, so this list is the contract."""
    strategy, _ = _experiment_a(tmp_path)
    assert [
        rule.decision.rationale.split(":")[0] for rule in strategy.policy.rules
    ] == [
        "R1-ENTRY-LONG",
        _STOP_RULE_ID,
        _TARGET_RULE_ID,
        "R2-EXIT-VWAP-REVERTED",
        "R3-EXIT-EOD",
        "R4-M2-PROBE-ENTRY-LONG",
    ]
    budget = yaml.safe_load(
        (_tree(_EXPERIMENT_A) / "engine.yaml").read_text(encoding="utf-8")
    )["dsl_evaluation_budget_steps"]
    assert policy_work_steps(strategy.policy) == 51 <= budget
    assert strategy_admissible(strategy).verdict is AdmissionVerdict.ADMISSIBLE


def test_experiment_a_stop_fires_at_its_bound_and_not_one_bp_above(
    tmp_path: Path,
) -> None:
    """The boundary, read from the YAML — `LE` includes the bound itself."""
    strategy, config = _experiment_a(tmp_path)
    bound = config["stop_loss_bp"]
    assert isinstance(bound, int) and not isinstance(bound, bool) and bound < 0

    quiet = {"entry_window": False, "vwap_reverted": False, "eod": False}
    at = _decide(strategy, quiet, config, _held(bound))
    assert at.kind is DecisionKind.FLAT
    assert at.rationale.startswith(f"{_STOP_RULE_ID}:")
    assert at.target is not None
    assert (at.target.direction, at.target.position_effect) == ("SHORT", "CLOSE")

    assert (
        _decide(strategy, quiet, config, _held(bound + 1)).kind
        is DecisionKind.NO_ACTION
    )
    assert _decide(strategy, quiet, config, _held(bound - 1)).rationale.startswith(
        f"{_STOP_RULE_ID}:"
    )


def test_experiment_a_target_fires_at_its_bound_and_not_one_bp_below(
    tmp_path: Path,
) -> None:
    strategy, config = _experiment_a(tmp_path)
    bound = config["take_profit_bp"]
    assert isinstance(bound, int) and not isinstance(bound, bool) and bound > 0

    quiet = {"entry_window": False, "vwap_reverted": False, "eod": False}
    at = _decide(strategy, quiet, config, _held(bound))
    assert at.kind is DecisionKind.FLAT
    assert at.rationale.startswith(f"{_TARGET_RULE_ID}:")
    assert (
        _decide(strategy, quiet, config, _held(bound - 1)).kind
        is DecisionKind.NO_ACTION
    )
    assert _decide(strategy, quiet, config, _held(bound + 1)).rationale.startswith(
        f"{_TARGET_RULE_ID}:"
    )


def test_experiment_a_stop_wins_over_the_vwap_exit_when_both_hold(
    tmp_path: Path,
) -> None:
    """R5 sits ABOVE R2, so a reverted bar that is also at the stop is a stop."""
    strategy, config = _experiment_a(tmp_path)
    both = {"entry_window": False, "vwap_reverted": True, "eod": True}
    decision = _decide(strategy, both, config, _held(config["stop_loss_bp"]))
    assert decision.rationale.startswith(f"{_STOP_RULE_ID}:")
    # ...and the old exits still win when the position is nowhere near either bound.
    middle = _decide(strategy, both, config, _held(0))
    assert middle.rationale.startswith("R2-EXIT-VWAP-REVERTED:")


def test_experiment_a_neither_entry_rule_fires_while_a_position_is_held(
    tmp_path: Path,
) -> None:
    """The `side EQ "FLAT"` guard on R1 AND on R4 — the two must not diverge."""
    strategy, config = _experiment_a(tmp_path)
    gates = _entry_gates(config)
    assert _decide(strategy, gates, config, _FLAT).rationale.startswith(
        "R1-ENTRY-LONG:"
    )
    assert _decide(strategy, gates, config, _held(0)).kind is DecisionKind.NO_ACTION

    # R4 on its own input, with the probe binding forced ON: still guarded while held.
    probe_on = dict(config, m2_probe_entry_enabled=True)
    probe_shaped = {"entry_window": True, "vwap_reverted": False, "eod": False}
    assert _decide(strategy, probe_shaped, probe_on, _FLAT).rationale.startswith(
        "R4-M2-PROBE-ENTRY-LONG:"
    )
    assert (
        _decide(strategy, probe_shaped, probe_on, _held(0)).kind
        is DecisionKind.NO_ACTION
    )


def test_experiment_a_decides_nothing_when_the_position_namespace_is_absent(
    tmp_path: Path,
) -> None:
    """Plan §2 D3: no namespace -> every position compare is False, NE included."""
    strategy, config = _experiment_a(tmp_path)
    quiet = {"entry_window": False, "vwap_reverted": False, "eod": False}
    assert _decide(strategy, quiet, config, None).kind is DecisionKind.NO_ACTION
    assert (
        _decide(strategy, _entry_gates(config), config, None).kind
        is DecisionKind.NO_ACTION
    )
    probe_on = dict(config, m2_probe_entry_enabled=True)
    assert (
        _decide(strategy, {"entry_window": True}, probe_on, None).kind
        is DecisionKind.NO_ACTION
    )
    # The pre-S4 exits are unchanged: they read `resolved_values` only, so they still fire.
    reverted = _decide(strategy, {"vwap_reverted": True}, config, None)
    assert reverted.rationale.startswith("R2-EXIT-VWAP-REVERTED:")


def test_experiment_a_is_the_only_tree_declaring_a_bp_bound() -> None:
    """A bound with no namespace, or a namespace with no bound, is the drift to catch."""
    for symbol in (_PRIMARY_SYMBOL, _EXPERIMENT_B):
        document = yaml.safe_load(
            (_tree(symbol) / STRATEGY_BINDINGS_FILE_NAME).read_text(encoding="utf-8")
        )
        for stem, item in (document.get("strategies") or {}).items():
            stray = sorted(
                key
                for key in (item.get("bindings") or {})
                if key in ("stop_loss_bp", "take_profit_bp")
            )
            assert stray == [], f"{symbol}: stem {stem!r} binds {stray}"


def test_experiment_b_ships_one_rsi_wr_strategy_and_no_bindings(
    tmp_path: Path,
) -> None:
    """005380's strategy source loads, and its empty bindings entry is deliberate."""
    loaded, bindings = _loaded_strategy_source(_EXPERIMENT_B, tmp_path)
    (entry,) = loaded.strategies
    assert entry.path.name == "rsi_wr_reversion_long.strategy.yaml"
    # Empty, not absent: the strategy reads no `config`-sourced operand, and a leftover
    # key would be refused as configuration drift (resolve.py rule 4). The thresholds live
    # in fields.yaml because a momentum field has no value during warmup and so cannot be
    # published as a number for the DSL to compare against.
    assert bindings.present is True
    assert bindings.strategies == {}

    result = strategy_admissible(entry.strategy)
    assert result.verdict is AdmissionVerdict.ADMISSIBLE, result.reasons
    budget = yaml.safe_load(
        (_tree(_EXPERIMENT_B) / "engine.yaml").read_text(encoding="utf-8")
    )["dsl_evaluation_budget_steps"]
    assert policy_work_steps(entry.strategy.policy) == 18 <= budget


def test_experiment_b_rules_fire_as_declared(tmp_path: Path) -> None:
    """Entry needs BOTH oversold gates inside the window; either exit goes flat."""
    loaded, _ = _loaded_strategy_source(_EXPERIMENT_B, tmp_path)
    strategy = loaded.strategies[0].strategy
    oversold = {
        "entry_window": True,
        "rsi_oversold": True,
        "wr_oversold": True,
        "rsi_recovered": False,
        "eod": False,
    }

    entry = _decide(strategy, oversold, {})
    assert entry.kind is DecisionKind.ACTION
    assert entry.rationale.startswith("R1-ENTRY-LONG-RSI-WR:")
    assert entry.target is not None
    assert (entry.target.direction, entry.target.position_effect) == ("LONG", "OPEN")
    assert entry.target.quantity_basis == "RISK"
    assert (entry.target.account, entry.target.instrument) == (
        _VENUE_POLICY_ACCOUNT,
        _EXPERIMENT_B,
    )

    for missing in ("rsi_oversold", "wr_oversold", "entry_window"):
        assert (
            _decide(strategy, dict(oversold, **{missing: False}), {}).kind
            is DecisionKind.NO_ACTION
        ), missing
    # A warming-up or locked momentum window publishes `false`, never a missing key; an
    # empty capsule is the fail-closed floor and must still decide nothing.
    assert _decide(strategy, {}, {}).kind is DecisionKind.NO_ACTION

    exits = (
        ("rsi_recovered", "R2-EXIT-RSI-RECOVERED:"),
        ("eod", "R3-EXIT-EOD:"),
    )
    for gate, rule in exits:
        flat = _decide(
            strategy,
            {
                "entry_window": False,
                "rsi_oversold": False,
                "wr_oversold": False,
                "rsi_recovered": gate == "rsi_recovered",
                "eod": gate == "eod",
            },
            {},
        )
        assert flat.kind is DecisionKind.FLAT, gate
        assert flat.rationale.startswith(rule)
        assert flat.target is not None
        assert flat.target.position_effect == "CLOSE"


def test_the_experiment_b_declaration_publishes_exactly_what_its_dsl_reads() -> None:
    """A kernel poll is refused whole on a missing journal key, so pin the three sets."""
    tree = _tree(_EXPERIMENT_B)
    published = {
        entry["as"]
        for entry in yaml.safe_load((tree / "fields.yaml").read_text(encoding="utf-8"))[
            "publish"
        ]
    }
    strategy = yaml.safe_load(
        (tree / "strategies" / "rsi_wr_reversion_long.strategy.yaml").read_text(
            encoding="utf-8"
        )
    )
    read: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            ref = node.get("ref")
            if isinstance(ref, list) and ref[:2] == ["capsule", "resolved_values"]:
                read.add(str(ref[2]))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(strategy)
    assert read == {
        "entry_window",
        "rsi_oversold",
        "wr_oversold",
        "rsi_recovered",
        "eod",
    }
    assert read <= published
    declared = {
        entry["field_key"]
        for entry in yaml.safe_load(
            (tree / "critical_input_policy.yaml").read_text(encoding="utf-8")
        )["fields"]
    }
    assert declared == published, "the producer refuses a mismatch at startup"
    construction = yaml.safe_load(
        (tree / "construction.yaml").read_text(encoding="utf-8")
    )
    assert construction["price_field_key"] in published
    assert construction["shape_price_field_key"] in published
