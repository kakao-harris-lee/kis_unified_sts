"""The stock tenant trees added for the operator's 2026-11-19 directive."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.dsl.serialization import parse_strategy
from tos.dsl.vocabulary import DecisionKind, evaluate_policy
from tos.engine.admission import policy_work_steps, strategy_admissible
from tos.engine.vocabulary import AdmissionVerdict, CommitmentStep, StageOutcome
from tos_runtime.strategy.bindings import (
    STRATEGY_BINDINGS_FILE_NAME,
    load_strategy_bindings,
)
from tos_runtime.strategy.loader import load_strategies
from tos_runtime.strategy.resolve import _resolve_bindings_or_refuse
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
        # One line: the R4 probe rule stays in the (byte-identical) strategy file and can
        # no longer fire. See `test_experiment_a_is_setup_d_with_the_probe_binding_off`.
        "strategy_bindings.yaml": frozenset(
            {"strategies.setup_d_long.strategy.bindings.m2_probe_entry_enabled"}
        ),
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


def _decide(strategy: Any, resolved: dict[str, Any], config: dict[str, Any]) -> Any:
    return evaluate_policy(
        strategy.policy, {"capsule": {"resolved_values": resolved}, "config": config}
    )


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
    assert _decide(strategy, probe_shaped, config).kind is DecisionKind.NO_ACTION
    # ...while the real Setup D entry still fires.
    gates = {
        "entry_window": True,
        "hi_vol": True,
        "stall_ok": True,
        "reversal_ok": True,
        "z_x1000": config["z_entry_max_x1000"] - 1,
    }
    r1 = _decide(strategy, gates, config)
    assert r1.kind is DecisionKind.ACTION
    assert r1.rationale.startswith("R1-ENTRY-LONG:")


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
