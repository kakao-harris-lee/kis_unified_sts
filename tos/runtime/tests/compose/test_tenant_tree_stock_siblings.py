"""The stock tenant trees added for the operator's 2026-11-19 directive.

「유동성이 큰 대형주들로 최종 모의투자에서 매수/매도가 잘 동작하게 완료해」 — one open
position per symbol (the kernel's no-pyramiding is unchanged), so three concurrent slots
come from three symbols. ``cp3-setup-d-stock-000660`` and ``cp3-setup-d-stock-005380`` are
derivations of ``cp3-setup-d-stock-005930``, whose own differences from the LONG tree
``test_tenant_tree_stock.py`` already pins — this module pins the step from 005930 to a
sibling, which is exactly «the symbol, and nothing else»:

* the file set is identical;
* every file is a BYTE copy of 005930's except the ones listed in ``_DIFFERS``, and in
  those the only differing leaves are the ones declared there;
* each sibling tree BOOTS under ``compose_paper_runtime`` with the kis-mock transport and
  a crossing event still sends nothing (the band is absent in a hermetic boot);
* the trees are discovered, not listed, so a fourth symbol cannot land uncovered.

What the symbol does NOT change is worth stating because it is why the siblings are copies:
the KRX 호가가격단위 ladder is chosen by PRICE, not by symbol, and the day's price band is
read per session by the band source. So the venue policy's tick table is byte-identical and
only its ``policy_id`` and provenance move.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine.vocabulary import CommitmentStep, StageOutcome
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

#: Per file, the leaf paths that may differ from the 005930 tree. ``None`` means the file
#: is prose (its whole content may differ). An EMPTY set means the bytes differ but NO
#: parsed leaf does — the file's only difference is a comment naming the symbol, so the
#: runtime reads exactly the 005930 values from it. Everything absent from this map must
#: be a BYTE copy — including ``strategies/``, ``strategy_bindings.yaml`` and
#: ``engine.yaml``, which is what makes all three stock tenants measure one decision
#: digest (``config/tos_runtime/decision_generations.yaml``).
_DIFFERS: dict[str, frozenset[str] | None] = {
    "README.md": None,
    "RENDER.yaml": frozenset({"tree_id", "instrument.pattern"}),
    "fields.yaml": frozenset(),
    "fill_observer.yaml": frozenset(),
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


def _sibling_symbols() -> tuple[str, ...]:
    """Every shipped stock tenant tree except the one the siblings derive from.

    Discovered from the config root rather than listed, so a tree added later is covered
    by this module instead of being silently skipped.
    """
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


def test_three_stock_tenants_ship() -> None:
    """The directive's own shape: three slots need three symbols."""
    assert len(_SIBLINGS) >= 2, _SIBLINGS
    assert all(symbol.isdigit() and len(symbol) == 6 for symbol in _SIBLINGS), _SIBLINGS


@pytest.mark.parametrize("symbol", _SIBLINGS)
def test_a_sibling_tree_has_exactly_the_primary_trees_files(symbol: str) -> None:
    assert _files(_tree(symbol)) == _files(_STOCK)


@pytest.mark.parametrize("symbol", _SIBLINGS)
@pytest.mark.parametrize("name", sorted(_files(_STOCK)))
def test_every_file_is_a_byte_copy_or_differs_only_where_declared(
    name: str, symbol: str
) -> None:
    primary_bytes = (_STOCK / name).read_bytes()
    sibling_bytes = (_tree(symbol) / name).read_bytes()
    if name not in _DIFFERS:
        assert (
            sibling_bytes == primary_bytes
        ), f"{name} must stay a byte copy of the {_PRIMARY_SYMBOL} tree"
        return
    assert (
        sibling_bytes != primary_bytes
    ), f"{name} is declared different but is identical"
    allowed = _DIFFERS[name]
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
    # Single-symbol by construction: the renderer FULL-matches `--instrument` against this.
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
    assert raw["front_month_product"] is None  # a stock does not roll
    assert raw["open_anchor"] == "09:00"


@pytest.mark.parametrize("symbol", _SIBLINGS)
def test_a_sibling_has_a_contract_spec_the_producer_can_resolve(symbol: str) -> None:
    """``resolve_contract_spec`` matches by ``symbol_prefix``; without a block the

    producer refuses to start. The values are 005930's, because a KRX share is
    price x 1 and the tick ladder is the tenant tree's business, not this spec's.
    """
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
    # The policy's identity moves with its content (the LONG tree's header rule).
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
    """``_install_stock_tree`` for a sibling: its calendar + its two filled policies.

    The instrument filled in is the compose fixture's (``_VENUE_POLICY_INSTRUMENT``), not
    the tenant's symbol, because the boot cross-checks the policy scope against the
    fixture's ``construction.instrument``. This test is about the tree's own files
    composing; which symbol a deployment renders in is
    ``tests/unit/scripts/test_render_tenant_trees.py``'s subject.
    """
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
    """The same end as 005930's own boot test, per sibling tree.

    A hermetic boot has no band line, so a fully constructed candidate still ends at
    VENUE_ADMISSIBILITY_DECISION = UNKNOWN and nothing is sealed. That is the fail-closed
    direction the tree is supposed to have, and it proves the tree's own files compose.
    """
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
