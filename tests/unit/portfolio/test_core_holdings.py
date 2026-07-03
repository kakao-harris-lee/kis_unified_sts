"""Unit tests for shared.portfolio.core_holdings (Phase 5A Track A ledger).

Hermetic: tmp_path YAML files loaded via absolute paths (no ConfigLoader
global state). Pins the loader/validation contract consumed by the 5B
stock-filter lane and the 5E UI lane, the valuations-sidecar merge, and the
Track A equity computation used by services/portfolio_monitor.
"""

from __future__ import annotations

import logging
from datetime import date

import pytest
import yaml

from shared.portfolio.core_holdings import (
    TRACK_A_STALE_COMPONENT,
    CoreHoldings,
    Valuation,
    compute_track_a_equity,
    load_valuations,
    save_valuation,
    valuations_sidecar_path,
)

AS_OF = date(2026, 7, 6)


def _write_yaml(path, data) -> str:
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return str(path)


def _core_data(**overrides) -> dict:
    data = {
        "sectors": {
            "defense": {"label": "방산", "target_weight": 0.35},
            "semiconductor_equipment": {"label": "반도체 장비", "target_weight": 0.35},
            "robotics": {"label": "로보틱스", "target_weight": 0.15},
            "cash": {"label": "현금 버퍼", "target_weight": 0.15},
        },
        "rebalancing": {"drift_threshold_pct": 0.10, "single_holding_max": 0.25},
        "cash_krw": 0,
        "holdings": [],
        "candidates": [],
    }
    data.update(overrides)
    return data


def _holding(**overrides) -> dict:
    holding = {
        "symbol": "012450",
        "name": "한화에어로스페이스",
        "sector": "defense",
        "thesis": "수주잔고 확정형",
        "kill_criteria": ["수주잔고 분기 연속 2회 감소"],
        "shares": 10,
        "avg_price": 900_000,
        "last_valuation": {"date": "2026-07-01", "price": 1_000_000},
    }
    holding.update(overrides)
    return holding


# ---------------------------------------------------------------------------
# Loading + validation
# ---------------------------------------------------------------------------


class TestLoading:
    def test_missing_file_returns_validated_defaults(self, tmp_path):
        core = CoreHoldings.load_or_default(str(tmp_path / "absent.yaml"))
        assert core.holdings == []
        assert core.candidates == []
        assert core.symbols() == frozenset()
        assert not core.provisioned
        assert core.total_value() is None
        assert core.sector_weights() == {}
        assert sum(s.target_weight for s in core.sectors.values()) == pytest.approx(1.0)

    def test_repo_scaffold_loads_empty(self):
        # The checked-in config/portfolio/core_holdings.yaml is the empty
        # scaffold — it must load, validate, and read as not provisioned.
        from pathlib import Path

        root = Path(__file__).resolve().parents[3]
        core = CoreHoldings.load_or_default(
            str(root / "config" / "portfolio" / "core_holdings.yaml")
        )
        assert core.holdings == []
        assert not core.provisioned

    def test_holdings_and_candidates_load(self, tmp_path):
        path = _write_yaml(
            tmp_path / "core.yaml",
            _core_data(
                holdings=[_holding()],
                candidates=[
                    {
                        "symbol": "042700",
                        "name": "한미반도체",
                        "sector": "semiconductor_equipment",
                        "thesis": "TC 본더 독점",
                        "kill_criteria": ["경쟁사 양산 진입"],
                    }
                ],
            ),
        )
        core = CoreHoldings.load_or_default(path)
        assert core.symbols() == frozenset({"012450"})  # candidates not owned
        assert core.sector_of("012450") == "defense"
        assert core.sector_of("042700") == "semiconductor_equipment"
        assert core.sector_of("999999") is None
        assert core.holdings[0].value == pytest.approx(10_000_000.0)

    def test_unknown_sector_rejected(self, tmp_path):
        path = _write_yaml(
            tmp_path / "core.yaml",
            _core_data(holdings=[_holding(sector="crypto")]),
        )
        with pytest.raises(ValueError, match="unknown sector"):
            CoreHoldings.load_or_default(path)

    def test_target_weight_sum_must_be_one(self, tmp_path):
        data = _core_data()
        data["sectors"]["defense"]["target_weight"] = 0.5
        path = _write_yaml(tmp_path / "core.yaml", data)
        with pytest.raises(ValueError, match="sum to 1.0"):
            CoreHoldings.load_or_default(path)

    def test_duplicate_holding_symbol_rejected(self, tmp_path):
        path = _write_yaml(
            tmp_path / "core.yaml",
            _core_data(holdings=[_holding(), _holding(name="dup")]),
        )
        with pytest.raises(ValueError, match="duplicate"):
            CoreHoldings.load_or_default(path)

    def test_empty_kill_criteria_warns(self, tmp_path, caplog):
        path = _write_yaml(
            tmp_path / "core.yaml",
            _core_data(holdings=[_holding(kill_criteria=[])]),
        )
        with caplog.at_level(logging.WARNING, "shared.portfolio.core_holdings"):
            CoreHoldings.load_or_default(path)
        assert any("kill_criteria" in record.message for record in caplog.records)

    def test_symbol_keeps_leading_zero_and_coerces(self, tmp_path):
        path = _write_yaml(
            tmp_path / "core.yaml",
            _core_data(holdings=[_holding(symbol=42700)]),
        )
        core = CoreHoldings.load_or_default(path)
        assert core.holdings[0].symbol == "42700"


# ---------------------------------------------------------------------------
# Valuation math
# ---------------------------------------------------------------------------


class TestValuationMath:
    def test_total_value_sums_holdings_and_cash(self, tmp_path):
        path = _write_yaml(
            tmp_path / "core.yaml",
            _core_data(cash_krw=1_500_000, holdings=[_holding()]),
        )
        core = CoreHoldings.load_or_default(path)
        assert core.provisioned
        assert core.total_value() == pytest.approx(11_500_000.0)

    def test_cash_only_ledger_is_provisioned(self, tmp_path):
        path = _write_yaml(tmp_path / "core.yaml", _core_data(cash_krw=2_000_000))
        core = CoreHoldings.load_or_default(path)
        assert core.provisioned
        assert core.total_value() == pytest.approx(2_000_000.0)

    def test_unvalued_held_position_blocks_total(self, tmp_path):
        path = _write_yaml(
            tmp_path / "core.yaml",
            _core_data(
                cash_krw=1_000_000,
                holdings=[
                    _holding(),
                    _holding(
                        symbol="042700",
                        sector="semiconductor_equipment",
                        last_valuation={"date": None, "price": None},
                    ),
                ],
            ),
        )
        core = CoreHoldings.load_or_default(path)
        assert core.provisioned
        assert core.total_value() is None  # partial sum would skew MDD math
        assert core.sector_weights() == {}

    def test_sector_weights_cover_all_sectors(self, tmp_path):
        path = _write_yaml(
            tmp_path / "core.yaml",
            _core_data(cash_krw=2_500_000, holdings=[_holding()]),
        )
        core = CoreHoldings.load_or_default(path)
        weights = core.sector_weights()
        assert set(weights) == set(core.sectors)
        assert weights["defense"] == pytest.approx(10.0 / 12.5)
        assert weights["cash"] == pytest.approx(2.5 / 12.5)
        assert weights["robotics"] == 0.0
        assert sum(weights.values()) == pytest.approx(1.0)

    def test_zero_share_holding_contributes_zero(self, tmp_path):
        path = _write_yaml(
            tmp_path / "core.yaml",
            _core_data(
                cash_krw=1_000_000,
                holdings=[_holding(shares=0, last_valuation={})],
            ),
        )
        core = CoreHoldings.load_or_default(path)
        # shares=0 without a valuation must not block the total.
        assert core.total_value() == pytest.approx(1_000_000.0)


# ---------------------------------------------------------------------------
# Valuations sidecar
# ---------------------------------------------------------------------------


class TestValuationsSidecar:
    def test_sidecar_overrides_inline_valuation(self, tmp_path):
        path = _write_yaml(tmp_path / "core.yaml", _core_data(holdings=[_holding()]))
        sidecar = valuations_sidecar_path(path)
        save_valuation(sidecar, "012450", 1_100_000, date(2026, 7, 3))

        core = CoreHoldings.load_or_default(path)
        assert core.holdings[0].last_valuation.price == pytest.approx(1_100_000.0)
        assert core.holdings[0].last_valuation.date == date(2026, 7, 3)
        assert core.total_value() == pytest.approx(11_000_000.0)

    def test_sidecar_path_is_sibling_of_config(self, tmp_path):
        path = tmp_path / "core.yaml"
        assert valuations_sidecar_path(str(path)) == (
            tmp_path / "core_holdings_valuations.yaml"
        )

    def test_save_valuation_upserts_and_preserves_others(self, tmp_path):
        sidecar = tmp_path / "vals.yaml"
        save_valuation(sidecar, "012450", 1_000_000, date(2026, 7, 1))
        save_valuation(sidecar, "042700", 90_000, date(2026, 7, 2))
        save_valuation(sidecar, "012450", 1_050_000, date(2026, 7, 3))

        valuations = load_valuations(sidecar)
        assert valuations["012450"].price == pytest.approx(1_050_000.0)
        assert valuations["012450"].date == date(2026, 7, 3)
        assert valuations["042700"].price == pytest.approx(90_000.0)

    def test_missing_or_broken_sidecar_reads_empty(self, tmp_path):
        assert load_valuations(tmp_path / "absent.yaml") == {}
        broken = tmp_path / "broken.yaml"
        broken.write_text("- just\n- a list\n", encoding="utf-8")
        assert load_valuations(broken) == {}

    def test_unknown_sidecar_symbol_is_ignored(self, tmp_path):
        path = _write_yaml(tmp_path / "core.yaml", _core_data(holdings=[_holding()]))
        sidecar = valuations_sidecar_path(path)
        save_valuation(sidecar, "999999", 1, date(2026, 7, 3))
        core = CoreHoldings.load_or_default(path)
        assert core.holdings[0].last_valuation.price == pytest.approx(1_000_000.0)


# ---------------------------------------------------------------------------
# Track A equity (portfolio_monitor input)
# ---------------------------------------------------------------------------


class TestTrackAEquity:
    def _core(self, tmp_path, **overrides) -> CoreHoldings:
        path = _write_yaml(tmp_path / "core.yaml", _core_data(**overrides))
        return CoreHoldings.load_or_default(path)

    def test_empty_ledger_reads_missing(self, tmp_path):
        equity = compute_track_a_equity(
            self._core(tmp_path), as_of=AS_OF, stale_after_days=45
        )
        assert equity.equity is None
        assert equity.missing_components == ("track_a",)
        assert not equity.degraded

    def test_valued_ledger_publishes_total(self, tmp_path):
        core = self._core(tmp_path, cash_krw=1_500_000, holdings=[_holding()])
        equity = compute_track_a_equity(core, as_of=AS_OF, stale_after_days=45)
        assert equity.equity == pytest.approx(11_500_000.0)
        assert equity.missing_components == ()
        assert equity.track_id == "A"

    def test_stale_valuation_flags_but_still_publishes(self, tmp_path):
        core = self._core(
            tmp_path,
            holdings=[
                _holding(last_valuation={"date": "2026-04-01", "price": 1_000_000})
            ],
        )
        equity = compute_track_a_equity(core, as_of=AS_OF, stale_after_days=45)
        assert equity.equity == pytest.approx(10_000_000.0)
        assert equity.missing_components == (TRACK_A_STALE_COMPONENT,)

    def test_stale_boundary_is_exclusive(self, tmp_path):
        # exactly stale_after_days old → still fresh (strictly older flags).
        core = self._core(
            tmp_path,
            holdings=[
                _holding(last_valuation={"date": "2026-05-22", "price": 1_000_000})
            ],
        )
        equity = compute_track_a_equity(core, as_of=AS_OF, stale_after_days=45)
        assert (AS_OF - date(2026, 5, 22)).days == 45
        assert equity.missing_components == ()

    def test_valuation_without_date_reads_stale(self, tmp_path):
        core = self._core(
            tmp_path,
            holdings=[_holding(last_valuation={"date": None, "price": 1_000_000})],
        )
        equity = compute_track_a_equity(core, as_of=AS_OF, stale_after_days=45)
        assert equity.equity == pytest.approx(10_000_000.0)
        assert equity.missing_components == (TRACK_A_STALE_COMPONENT,)

    def test_unvalued_holding_reads_missing(self, tmp_path):
        core = self._core(
            tmp_path,
            holdings=[_holding(last_valuation={"date": None, "price": None})],
        )
        equity = compute_track_a_equity(core, as_of=AS_OF, stale_after_days=45)
        assert equity.equity is None
        assert equity.missing_components == ("track_a",)

    def test_oldest_valuation_across_holdings_anchors_staleness(self, tmp_path):
        core = self._core(
            tmp_path,
            holdings=[
                _holding(),  # fresh (2026-07-01)
                _holding(
                    symbol="042700",
                    sector="semiconductor_equipment",
                    last_valuation={"date": "2026-01-05", "price": 90_000},
                ),
            ],
        )
        equity = compute_track_a_equity(core, as_of=AS_OF, stale_after_days=45)
        assert equity.equity == pytest.approx(10_000_000.0 + 900_000.0)
        assert equity.missing_components == (TRACK_A_STALE_COMPONENT,)


class TestValuationModel:
    def test_string_date_coerced(self):
        assert Valuation(date="2026-07-01", price=10.0).date == date(2026, 7, 1)

    def test_non_positive_price_rejected(self):
        with pytest.raises(ValueError):
            Valuation(date="2026-07-01", price=0.0)


# ---------------------------------------------------------------------------
# Manual-track guard: Track A surfaces never import the order path
# ---------------------------------------------------------------------------


def _import_statement_targets(module) -> set[str]:
    """Every module named by an import statement anywhere in the source.

    AST-based (hedge-lane guard pattern) so lazy function-body imports are
    covered and docstring mentions never false-positive.
    """
    import ast
    from pathlib import Path

    source = Path(module.__file__).read_text(encoding="utf-8")
    targets: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            targets.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            targets.add(node.module)
            targets.update(f"{node.module}.{alias.name}" for alias in node.names)
    return targets


class TestManualTrackGuard:
    def test_track_a_surfaces_never_import_execution(self):
        import cli.commands.portfolio as cli_module
        import services.portfolio_monitor.tier3_watch as tier3_module
        import shared.portfolio.core_holdings as loader_module

        for module in (loader_module, tier3_module, cli_module):
            offenders = {
                name
                for name in _import_statement_targets(module)
                if name == "shared.execution" or name.startswith("shared.execution.")
            }
            assert offenders == set(), (
                f"{module.__name__} is a MANUAL Track A surface and must never"
                f" import the order path: {offenders}"
            )
