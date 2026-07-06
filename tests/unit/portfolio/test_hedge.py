"""Unit tests for shared/portfolio/hedge.py (Phase 4A engine — advisory ONLY).

Hermetic: pure inputs only — no Redis, no filesystem writes, no network. Pins:

* the HARD safety constraint that neither ``shared.portfolio.hedge`` nor
  ``services.portfolio_monitor.hedge_advisor`` imports ``shared.execution``
  (static AST scan of every import statement + a fresh-interpreter check of
  the transitive module-level import graph);
* β OLS accuracy on synthetic series, clipping bounds, and the
  ``default_beta`` fallback with coverage recording;
* signed futures notional with product-aware (full vs mini) multipliers;
* floor recommendation boundaries, ``net <= 0`` → 0, stale-price skip;
* the FIXED 18-field ``portfolio:hedge:latest`` contract mapping.
"""

from __future__ import annotations

import ast
import json
import math
import subprocess
import sys
import textwrap
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

import services.portfolio_monitor.hedge_advisor as hedge_advisor_module
import shared.portfolio.hedge as hedge_module
from shared.portfolio.hedge import (
    BetaEstimate,
    BetaEstimationConfig,
    HedgeAdvice,
    HedgeAdvisorConfig,
    advice_to_latest_fields,
    advice_v2_to_latest_fields,
    compute_hedge_advice,
    compute_hedge_advice_v2,
    compute_returns,
    current_hedge_ratio,
    estimate_beta,
    is_price_fresh,
    multiplier_for_symbol,
    product_multipliers,
    side_sign,
    target_hedge_ratio_for_band,
    verify_product_spec,
)

REPO_ROOT = Path(__file__).resolve().parents[3]

ASOF = datetime(2026, 7, 6, 19, 0)

#: Product-key → KRW/point, mirroring config/execution.yaml constants.
MULTIPLIERS = {"kospi200_mini": 50_000.0, "kospi200_full": 250_000.0}

EXEC_SPECS = {
    "kospi200_mini": {"multiplier_krw_per_point": 50_000, "tick_size_points": 0.02},
    "kospi200_full": {"multiplier_krw_per_point": 250_000, "tick_size_points": 0.05},
}


# ---------------------------------------------------------------------------
# Execution-import guard (advisory-only safety pin)
# ---------------------------------------------------------------------------


def _import_statement_targets(module) -> set[str]:
    """Every module named by an import statement anywhere in the source.

    AST-based so lazy (function-body) imports are covered too, and the
    docstrings that merely *mention* shared.execution do not false-positive.
    """
    source = Path(module.__file__).read_text(encoding="utf-8")
    targets: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            targets.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            targets.add(node.module)
            targets.update(f"{node.module}.{alias.name}" for alias in node.names)
    return targets


class TestExecutionImportGuard:
    @pytest.mark.parametrize(
        "module",
        [hedge_module, hedge_advisor_module],
        ids=["shared.portfolio.hedge", "services.portfolio_monitor.hedge_advisor"],
    )
    def test_no_execution_import_statements(self, module):
        offenders = {
            name
            for name in _import_statement_targets(module)
            if name == "shared.execution" or name.startswith("shared.execution.")
        }
        assert (
            offenders == set()
        ), f"{module.__name__} must never import the order path: {offenders}"

    def test_transitive_import_graph_excludes_execution(self):
        """Fresh interpreter: importing the hedge lane pulls no execution module."""
        snippet = textwrap.dedent("""
            import sys

            import shared.portfolio.hedge  # noqa: F401
            import services.portfolio_monitor.hedge_advisor  # noqa: F401

            bad = sorted(
                name
                for name in sys.modules
                if name == "shared.execution" or name.startswith("shared.execution.")
            )
            if bad:
                print("execution modules imported: " + ", ".join(bad))
                sys.exit(1)
            """)
        result = subprocess.run(
            [sys.executable, "-c", snippet],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------------------
# β estimation
# ---------------------------------------------------------------------------

#: Deterministic non-degenerate daily-return pattern (no RNG — hermetic).
_RETURN_PATTERN = [0.01, -0.005, 0.007, -0.012, 0.004]


def _series(
    n_returns: int,
    *,
    slope: float = 1.0,
    base: float = 100.0,
    start: date = date(2026, 1, 5),
) -> list[tuple[date, float]]:
    """(date, close) series whose daily return on day t is slope × pattern[t]."""
    closes = [(start, base)]
    day, value = start, base
    for i in range(n_returns):
        day += timedelta(days=1)
        value *= 1.0 + slope * _RETURN_PATTERN[i % len(_RETURN_PATTERN)]
        closes.append((day, value))
    return closes


class TestComputeReturns:
    def test_unsorted_and_invalid_closes_are_cleaned(self):
        d = [date(2026, 1, i) for i in range(1, 6)]
        closes = [
            (d[2], 110.0),  # unsorted on purpose
            (d[0], 100.0),
            (d[1], "bad"),  # non-numeric → dropped
            (d[3], -5.0),  # non-positive → dropped
            (d[4], 121.0),
        ]
        returns = compute_returns(closes)
        assert [day for day, _ in returns] == [d[2], d[4]]
        assert [r for _, r in returns] == [
            pytest.approx(0.10),
            pytest.approx(0.10),
        ]

    def test_empty_input(self):
        assert compute_returns([]) == []


class TestEstimateBeta:
    def test_known_slope_recovers_exactly(self):
        config = BetaEstimationConfig()
        market = _series(130)
        symbol = _series(130, slope=1.5, base=50.0)
        estimate = estimate_beta(symbol, market, config)
        assert estimate.beta == pytest.approx(1.5, abs=1e-9)
        assert estimate.fallback is False
        assert estimate.observations == config.window_trading_days

    def test_window_trims_and_alignment_uses_common_dates_only(self):
        config = BetaEstimationConfig()
        market = _series(200)  # longer than the symbol series
        symbol = _series(130, slope=1.5, base=50.0)
        estimate = estimate_beta(symbol, market, config)
        # Only the 130 common return days align; the window keeps the last 120.
        assert estimate.observations == 120
        assert estimate.beta == pytest.approx(1.5, abs=1e-9)
        assert estimate.fallback is False

    def test_clip_max_bounds_high_beta(self):
        config = BetaEstimationConfig()
        estimate = estimate_beta(_series(130, slope=5.0), _series(130), config)
        assert estimate.beta == pytest.approx(config.clip_max)
        assert estimate.fallback is False

    def test_clip_min_bounds_negative_beta(self):
        config = BetaEstimationConfig()
        estimate = estimate_beta(_series(130, slope=-0.5), _series(130), config)
        assert estimate.beta == pytest.approx(config.clip_min)
        assert estimate.fallback is False

    def test_insufficient_observations_falls_back_with_coverage(self):
        config = BetaEstimationConfig()
        estimate = estimate_beta(_series(10, slope=1.5), _series(10), config)
        assert estimate.fallback is True
        assert estimate.beta == pytest.approx(config.default_beta)
        assert estimate.observations == 10  # aligned sample size is recorded

    def test_empty_series_falls_back(self):
        config = BetaEstimationConfig()
        estimate = estimate_beta([], _series(130), config)
        assert estimate == BetaEstimate(
            beta=config.default_beta, observations=0, fallback=True
        )

    def test_degenerate_market_variance_falls_back(self):
        config = BetaEstimationConfig()
        flat = [(date(2026, 1, 5) + timedelta(days=i), 100.0) for i in range(130)]
        estimate = estimate_beta(_series(129, slope=1.5), flat, config)
        assert estimate.fallback is True
        assert estimate.beta == pytest.approx(config.default_beta)


# ---------------------------------------------------------------------------
# Sign / freshness / multiplier helpers
# ---------------------------------------------------------------------------


class TestSideSign:
    @pytest.mark.parametrize("side", ["short", "SELL", " Short ", "sell"])
    def test_short_sides_negative(self, side):
        assert side_sign(side) == -1.0

    @pytest.mark.parametrize("side", ["long", "buy", "LONG", "", None, "hold"])
    def test_everything_else_positive(self, side):
        assert side_sign(side) == 1.0


class TestIsPriceFresh:
    NOW = datetime(2026, 7, 6, 19, 0)

    def test_missing_asof_is_stale(self):
        assert is_price_fresh(None, self.NOW, 24.0) is False

    def test_within_bound_is_fresh(self):
        assert is_price_fresh(self.NOW - timedelta(hours=1), self.NOW, 24.0) is True

    def test_exactly_at_bound_is_fresh(self):
        assert is_price_fresh(self.NOW - timedelta(hours=24), self.NOW, 24.0) is True

    def test_beyond_bound_is_stale(self):
        assert (
            is_price_fresh(self.NOW - timedelta(hours=24, seconds=1), self.NOW, 24.0)
            is False
        )

    def test_future_dated_is_stale(self):
        assert is_price_fresh(self.NOW + timedelta(minutes=1), self.NOW, 24.0) is False


class TestProductSpec:
    def test_verify_passes_on_matching_spec(self):
        verify_product_spec(HedgeAdvisorConfig(), EXEC_SPECS)  # no raise

    def test_verify_rejects_multiplier_mismatch(self):
        specs = {
            "kospi200_mini": {
                "multiplier_krw_per_point": 250_000,
                "tick_size_points": 0.02,
            }
        }
        with pytest.raises(ValueError, match="multiplier"):
            verify_product_spec(HedgeAdvisorConfig(), specs)

    def test_verify_rejects_missing_spec(self):
        with pytest.raises(ValueError, match="missing"):
            verify_product_spec(HedgeAdvisorConfig(), {})

    def test_verify_skipped_when_cross_check_disabled(self):
        config = HedgeAdvisorConfig(product={"cross_check_execution_spec": False})
        verify_product_spec(config, {})  # no raise

    def test_product_multipliers_from_execution_spec(self):
        assert product_multipliers(HedgeAdvisorConfig(), EXEC_SPECS) == MULTIPLIERS

    def test_product_multipliers_skips_missing_spec(self):
        specs = {"kospi200_mini": EXEC_SPECS["kospi200_mini"]}
        assert product_multipliers(HedgeAdvisorConfig(), specs) == {
            "kospi200_mini": 50_000.0
        }

    @pytest.mark.parametrize(
        ("symbol", "expected"),
        [
            ("A05M6000", 50_000.0),  # KIS live mini
            ("105W09", 50_000.0),  # continuous mini
            ("A01M6000", 250_000.0),  # KIS live full
            ("101W09", 250_000.0),  # continuous full
            ("005930", None),  # not a configured futures product
            ("", None),
            (None, None),
        ],
    )
    def test_multiplier_for_symbol_prefix_resolution(self, symbol, expected):
        config = HedgeAdvisorConfig()
        assert multiplier_for_symbol(symbol, config, MULTIPLIERS) == expected


# ---------------------------------------------------------------------------
# compute_hedge_advice
# ---------------------------------------------------------------------------


def _stock(quantity: float, price: float, code="005930", side="long"):
    return {"code": code, "side": side, "quantity": quantity, "current_price": price}


def _future(quantity: float, price: float, code="A05M6000", side="short"):
    return {"code": code, "side": side, "quantity": quantity, "current_price": price}


def _beta(value: float) -> BetaEstimate:
    return BetaEstimate(beta=value, observations=120, fallback=False)


def _advice(
    *,
    stock=(),
    futures=(),
    betas=None,
    price=400.0,
    fresh=True,
    band="HIGH",
    score=80.0,
    config=None,
    extra_missing=(),
):
    return compute_hedge_advice(
        config=config or HedgeAdvisorConfig(),
        stock_positions=list(stock),
        futures_positions=list(futures),
        betas=betas or {},
        multipliers=MULTIPLIERS,
        futures_price=price,
        futures_price_fresh=fresh,
        band=band,
        score=score,
        asof_ts=ASOF,
        extra_missing=list(extra_missing),
    )


class TestBetaNotional:
    def test_weighted_beta_notional(self):
        advice = _advice(stock=[_stock(1000, 60_000.0)], betas={"005930": _beta(1.5)})
        assert advice.stock_long_notional == pytest.approx(60_000_000.0)
        assert advice.beta_notional == pytest.approx(90_000_000.0)
        assert advice.portfolio_beta == pytest.approx(1.5)
        assert advice.degraded is False
        assert advice.missing_components == ()

    def test_anomalous_stock_short_is_ignored(self):
        advice = _advice(
            stock=[_stock(1000, 60_000.0, side="short")],
            betas={"005930": _beta(1.5)},
        )
        assert advice.stock_long_notional == pytest.approx(0.0)
        assert advice.beta_notional == pytest.approx(0.0)
        assert advice.portfolio_beta is None

    def test_missing_beta_uses_default_and_records_coverage(self):
        advice = _advice(stock=[_stock(1000, 60_000.0)])
        assert advice.beta_notional == pytest.approx(60_000_000.0)  # default β=1.0
        assert "beta:005930" in advice.missing_components
        assert advice.degraded is True

    def test_fallback_beta_estimate_records_coverage(self):
        betas = {"005930": BetaEstimate(beta=1.0, observations=5, fallback=True)}
        advice = _advice(stock=[_stock(1000, 60_000.0)], betas=betas)
        assert "beta:005930" in advice.missing_components


class TestFuturesExposure:
    def test_short_mini_position_is_negative_notional(self):
        advice = _advice(futures=[_future(2, 400.0)])
        assert advice.futures_net_contracts == -2
        assert advice.futures_net_notional == pytest.approx(-40_000_000.0)

    def test_long_full_position_uses_full_multiplier(self):
        advice = _advice(futures=[_future(1, 400.0, code="101W09", side="long")])
        assert advice.futures_net_contracts == 1
        assert advice.futures_net_notional == pytest.approx(100_000_000.0)

    def test_mixed_products_net_with_own_multipliers(self):
        advice = _advice(
            futures=[
                _future(2, 400.0, code="A05M6000", side="short"),  # -40M mini
                _future(1, 400.0, code="A01M6000", side="long"),  # +100M full
            ]
        )
        assert advice.futures_net_contracts == -1
        assert advice.futures_net_notional == pytest.approx(60_000_000.0)

    def test_unknown_product_prefix_skipped_and_recorded(self):
        advice = _advice(futures=[_future(1, 400.0, code="ZZZ999")])
        assert advice.futures_net_notional == pytest.approx(0.0)
        assert "futures_product:ZZZ999" in advice.missing_components
        assert advice.degraded is True

    def test_net_beta_exposure_sums_both_legs(self):
        advice = _advice(
            stock=[_stock(1000, 60_000.0)],
            betas={"005930": _beta(1.0)},
            futures=[_future(1, 400.0)],  # -20M mini short
        )
        assert advice.net_beta_exposure == pytest.approx(40_000_000.0)


class TestRecommendation:
    # contract_value = 400.0pt × ₩50,000/pt = ₩20,000,000
    def test_floor_exact_multiple_hedges_fully(self):
        advice = _advice(
            stock=[_stock(1000, 60_000.0)], betas={"005930": _beta(1.0)}
        )  # net 60M → raw 3.0
        assert advice.recommended_short_contracts == 3
        assert advice.residual_exposure_after == pytest.approx(0.0)

    def test_floor_never_over_hedges_at_dot_nine(self):
        advice = _advice(
            stock=[_stock(1300, 60_000.0)], betas={"005930": _beta(1.0)}
        )  # net 78M → raw 3.9
        assert advice.recommended_short_contracts == 3
        assert advice.residual_exposure_after == pytest.approx(18_000_000.0)
        assert "floor" in advice.reason

    def test_nearest_policy_rounds_up_at_dot_nine(self):
        config = HedgeAdvisorConfig(advisory={"rounding": "nearest"})
        advice = _advice(
            stock=[_stock(1300, 60_000.0)],
            betas={"005930": _beta(1.0)},
            config=config,
        )
        assert advice.recommended_short_contracts == 4

    def test_ceil_policy_rounds_up_any_fraction(self):
        config = HedgeAdvisorConfig(advisory={"rounding": "ceil"})
        advice = _advice(
            stock=[_stock(1050, 60_000.0)],  # net 63M → raw 3.15
            betas={"005930": _beta(1.0)},
            config=config,
        )
        assert advice.recommended_short_contracts == 4

    def test_sub_one_contract_floors_to_zero(self):
        advice = _advice(
            stock=[_stock(100, 60_000.0)], betas={"005930": _beta(1.0)}
        )  # net 6M → raw 0.3
        assert advice.recommended_short_contracts == 0
        assert advice.residual_exposure_after == pytest.approx(6_000_000.0)
        assert advice.advisory_active is False  # rec 0 never activates

    def test_net_negative_recommends_zero_never_longs(self):
        advice = _advice(futures=[_future(2, 400.0)])  # net -40M
        assert advice.net_beta_exposure == pytest.approx(-40_000_000.0)
        assert advice.recommended_short_contracts == 0
        assert advice.residual_exposure_after == pytest.approx(-40_000_000.0)
        assert "no hedge needed" in advice.reason

    def test_net_zero_recommends_zero(self):
        advice = _advice()
        assert advice.recommended_short_contracts == 0
        assert "no hedge needed" in advice.reason

    def test_stale_price_skips_recommendation_and_degrades(self):
        advice = _advice(
            stock=[_stock(1000, 60_000.0)],
            betas={"005930": _beta(1.0)},
            fresh=False,
        )
        assert advice.recommended_short_contracts == 0
        assert advice.residual_exposure_after == pytest.approx(60_000_000.0)
        assert advice.degraded is True
        assert "futures_price" in advice.missing_components
        assert "recommendation skipped" in advice.reason
        assert advice.advisory_active is False

    def test_missing_price_skips_recommendation(self):
        advice = _advice(
            stock=[_stock(1000, 60_000.0)],
            betas={"005930": _beta(1.0)},
            price=None,
        )
        assert advice.recommended_short_contracts == 0
        assert advice.futures_price is None
        assert "futures_price" in advice.missing_components

    def test_residual_matches_recommended_times_contract_value(self):
        advice = _advice(stock=[_stock(1300, 60_000.0)], betas={"005930": _beta(1.0)})
        contract_value = advice.futures_price * advice.multiplier
        expected = advice.net_beta_exposure - (
            advice.recommended_short_contracts * contract_value
        )
        assert advice.residual_exposure_after == pytest.approx(expected)


class TestAdvisoryActivation:
    @pytest.mark.parametrize(
        ("band", "active"),
        [
            ("HIGH", True),
            ("CRITICAL", True),
            ("ELEVATED", False),
            ("NEUTRAL", False),
            ("LOW", False),
        ],
    )
    def test_band_threshold(self, band, active):
        advice = _advice(
            stock=[_stock(1000, 60_000.0)],
            betas={"005930": _beta(1.0)},
            band=band,
        )
        assert advice.recommended_short_contracts == 3
        assert advice.advisory_active is active

    def test_unknown_band_nullified_and_recorded(self):
        advice = _advice(band="WEIRD")
        assert advice.band is None
        assert "risk_band" in advice.missing_components
        assert advice.advisory_active is False

    def test_missing_band_and_score_recorded(self):
        advice = _advice(band=None, score=None)
        assert "risk_band" in advice.missing_components
        assert "risk_score" in advice.missing_components
        assert advice.degraded is True

    def test_extra_missing_propagates(self):
        advice = _advice(extra_missing=["stock_positions"])
        assert "stock_positions" in advice.missing_components
        assert advice.degraded is True


# ---------------------------------------------------------------------------
# advice_to_latest_fields — FIXED 4B UI contract (18 fields)
# ---------------------------------------------------------------------------

_CONTRACT_FIELDS = {
    "product",
    "multiplier",
    "futures_price",
    "stock_long_notional",
    "portfolio_beta",
    "beta_notional",
    "futures_net_contracts",
    "futures_net_notional",
    "net_beta_exposure",
    "recommended_short_contracts",
    "residual_exposure_after",
    "band",
    "score",
    "advisory_active",
    "reason",
    "degraded",
    "missing_components",
    "asof_ts",
}


class TestLatestFieldsContract:
    def test_exact_field_set_has_18_keys(self):
        fields = advice_to_latest_fields(_advice())
        assert set(fields) == _CONTRACT_FIELDS
        assert len(fields) == 18

    def test_active_advice_values_and_formats(self):
        advice = _advice(
            stock=[_stock(1000, 60_000.0)],
            betas={"005930": _beta(1.5)},
            futures=[_future(1, 400.0)],
        )
        fields = advice_to_latest_fields(advice)

        assert all(isinstance(value, str) for value in fields.values())
        assert fields["product"] == "mini_kospi200"
        assert fields["multiplier"] == "50000"
        assert fields["futures_price"] == "400.0000"
        assert fields["stock_long_notional"] == "60000000.0000"
        assert fields["portfolio_beta"] == "1.5000"
        assert fields["beta_notional"] == "90000000.0000"
        assert fields["futures_net_contracts"] == "-1"
        assert fields["futures_net_notional"] == "-20000000.0000"
        assert fields["net_beta_exposure"] == "70000000.0000"
        assert fields["recommended_short_contracts"] == "3"  # floor(70M / 20M)
        assert fields["residual_exposure_after"] == "10000000.0000"
        assert fields["band"] == "HIGH"
        assert fields["score"] == "80.0000"
        assert fields["advisory_active"] == "true"
        assert fields["reason"] == advice.reason
        assert fields["degraded"] == "false"
        assert json.loads(fields["missing_components"]) == []
        assert datetime.fromisoformat(fields["asof_ts"]) == ASOF

    def test_absent_values_publish_as_empty_string(self):
        advice = _advice(price=None, band=None, score=None)  # no positions either
        fields = advice_to_latest_fields(advice)

        assert fields["futures_price"] == ""
        assert fields["portfolio_beta"] == ""  # no stock longs
        assert fields["band"] == ""
        assert fields["score"] == ""
        assert fields["advisory_active"] == "false"
        assert fields["degraded"] == "true"
        missing = json.loads(fields["missing_components"])
        assert "futures_price" in missing
        assert "risk_band" in missing
        assert "risk_score" in missing

    def test_float_fields_parse_back_losslessly(self):
        advice = _advice(stock=[_stock(1300, 60_000.0)], betas={"005930": _beta(1.0)})
        fields = advice_to_latest_fields(advice)
        assert float(fields["net_beta_exposure"]) == pytest.approx(
            advice.net_beta_exposure
        )
        assert float(fields["residual_exposure_after"]) == pytest.approx(
            advice.residual_exposure_after
        )
        assert int(fields["recommended_short_contracts"]) == (
            advice.recommended_short_contracts
        )
        assert math.isfinite(float(fields["score"]))


# ---------------------------------------------------------------------------
# HedgeAdvisorV2 — feasibility layer (append-only; advisory ONLY)
# ---------------------------------------------------------------------------

_V2_FIELDS = {
    "target_hedge_ratio",
    "current_hedge_ratio",
    "delta_short_contracts",
    "max_contracts_by_margin",
    "margin_after_hedge_pct",
    "estimated_slippage_ticks",
    "roll_adjustment",
    "execution_feasibility",
    "operator_action",
}


def _base_advice(
    *, band="HIGH", beta_notional=100_000_000.0, fut_net=0.0, price=400.0
) -> HedgeAdvice:
    """A minimal base HedgeAdvice for v2 folding (mini KOSPI200, mult 50k)."""
    return HedgeAdvice(
        product="mini_kospi200",
        multiplier=50_000,
        futures_price=price,
        stock_long_notional=beta_notional,
        portfolio_beta=1.0,
        beta_notional=beta_notional,
        futures_net_contracts=int(fut_net / (price * 50_000)) if price else 0,
        futures_net_notional=fut_net,
        net_beta_exposure=beta_notional + fut_net,
        recommended_short_contracts=0,
        residual_exposure_after=0.0,
        band=band,
        score=70.0,
        advisory_active=True,
        reason="base",
        degraded=False,
        missing_components=(),
        asof_ts=ASOF,
    )


def _v2(
    base=None,
    *,
    roll_state="normal",
    hedge_front_allowed=True,
    margin_risk_level="ok",
    margin_usage_pct=0.10,
    max_additional_contracts=10,
    per_contract_initial_margin_krw=1_600_000.0,
    account_equity_krw=50_000_000.0,
    initial_margin_required_krw=5_000_000.0,
    estimated_slippage_ticks=None,
    contract_state_present=True,
    margin_state_present=True,
):
    return compute_hedge_advice_v2(
        base=base if base is not None else _base_advice(),
        config=HedgeAdvisorConfig(),
        roll_state=roll_state,
        hedge_front_allowed=hedge_front_allowed,
        margin_risk_level=margin_risk_level,
        margin_usage_pct=margin_usage_pct,
        max_additional_contracts=max_additional_contracts,
        per_contract_initial_margin_krw=per_contract_initial_margin_krw,
        account_equity_krw=account_equity_krw,
        initial_margin_required_krw=initial_margin_required_krw,
        estimated_slippage_ticks=estimated_slippage_ticks,
        contract_state_present=contract_state_present,
        margin_state_present=margin_state_present,
    )


class TestHedgeAdviceV2:
    def test_target_ratio_by_band(self):
        cfg = HedgeAdvisorConfig()
        assert target_hedge_ratio_for_band("HIGH", cfg.risk_adjustment) == 0.50
        assert target_hedge_ratio_for_band("CRITICAL", cfg.risk_adjustment) == 0.75
        assert target_hedge_ratio_for_band("LOW", cfg.risk_adjustment) == 0.0
        assert target_hedge_ratio_for_band(None, cfg.risk_adjustment) is None

    def test_current_hedge_ratio_from_signed_notional(self):
        # short futures offset -60M against 100M β-notional → 0.6 covered.
        assert current_hedge_ratio(100_000_000.0, -60_000_000.0) == pytest.approx(0.6)
        # net-long futures add exposure → clamp to 0.0 (not negative).
        assert current_hedge_ratio(100_000_000.0, 20_000_000.0) == 0.0
        assert current_hedge_ratio(0.0, -10.0) is None

    def test_feasible_recommends_place_manual_hedge(self):
        # HIGH target 0.5 × 100M = 50M short; contract value 400×50k=20M →
        # 50M/20M = 2.5 → trunc 2 contracts.
        v = _v2()
        assert v.target_hedge_ratio == 0.50
        assert v.delta_short_contracts == 2
        assert v.execution_feasibility == "feasible"
        assert v.operator_action == "place_manual_hedge"

    def test_margin_cap_limits_delta(self):
        v = _v2(max_additional_contracts=1)
        assert v.delta_short_contracts == 1
        assert v.execution_feasibility == "limited_by_margin"
        assert v.operator_action == "review"

    def test_margin_stress_level_suppresses_add(self):
        v = _v2(margin_risk_level="reduce_only")
        assert v.delta_short_contracts == 0
        assert v.execution_feasibility == "limited_by_margin"
        assert v.operator_action == "review"

    def test_roll_required_blocks_front_add(self):
        v = _v2(roll_state="roll_required", hedge_front_allowed=False)
        assert v.delta_short_contracts == 0
        assert v.execution_feasibility == "blocked_by_roll"
        assert v.roll_adjustment == "use_next"
        assert v.operator_action == "roll_position"

    def test_expired_roll_recommends_close_front_first(self):
        v = _v2(roll_state="expired", hedge_front_allowed=False)
        assert v.execution_feasibility == "blocked_by_roll"
        assert v.roll_adjustment == "close_front_first"

    def test_slippage_limit_blocks_when_estimate_supplied(self):
        v = _v2(estimated_slippage_ticks=5.0)  # > default 2.0
        assert v.delta_short_contracts == 0
        assert v.execution_feasibility == "limited_by_liquidity"

    def test_missing_margin_state_degrades_to_noop(self):
        v = _v2(
            margin_state_present=False,
            margin_risk_level=None,
            margin_usage_pct=None,
            max_additional_contracts=None,
            per_contract_initial_margin_krw=None,
            account_equity_krw=None,
            initial_margin_required_krw=None,
        )
        assert v.delta_short_contracts == 0
        assert v.execution_feasibility == "degraded"
        assert v.operator_action == "review"

    def test_over_hedged_recommends_reduce(self):
        # LOW band → target 0.0, but 60M short already on → reduce.
        v = _v2(base=_base_advice(band="LOW", fut_net=-60_000_000.0))
        assert v.current_hedge_ratio == pytest.approx(0.6)
        assert v.delta_short_contracts < 0
        assert v.operator_action == "reduce_existing_hedge"

    def test_zero_target_no_existing_is_none_action(self):
        v = _v2(base=_base_advice(band="NEUTRAL"))
        assert v.target_hedge_ratio == 0.0
        assert v.delta_short_contracts == 0
        assert v.operator_action == "none"

    def test_margin_after_hedge_reflects_added_contracts(self):
        v = _v2()  # 2 contracts × 1.6M added on 5M base / 50M equity.
        assert v.margin_after_hedge_pct == pytest.approx(
            (5_000_000 + 2 * 1_600_000) / 50_000_000
        )

    def test_v2_fields_preserve_base_18_and_append_9(self):
        fields = advice_v2_to_latest_fields(_v2())
        assert set(advice_to_latest_fields(_v2().base)) <= set(fields)
        assert set(fields) >= _V2_FIELDS
        assert len(fields) == 27
        assert all(isinstance(value, str) for value in fields.values())

    def test_v2_fields_null_markers_when_degraded(self):
        v = _v2(
            margin_state_present=False,
            margin_usage_pct=None,
            per_contract_initial_margin_krw=None,
            account_equity_krw=None,
        )
        fields = advice_v2_to_latest_fields(v)
        assert fields["margin_after_hedge_pct"] == ""
        assert fields["execution_feasibility"] == "degraded"


# ---------------------------------------------------------------------------
# Enum-drift guard (audit M2): hedge.py hardcodes risk_level / roll_state
# string sets (advisory-only import ban forbids importing the source modules
# at runtime). This TEST-ONLY import pins those sets against the canonical
# enums so a value rename in the source can't silently break the hedge gate.
# ---------------------------------------------------------------------------


class TestEnumDriftGuard:
    def test_margin_suppress_set_subset_of_risk_levels(self):
        from shared.risk.futures_margin import RISK_LEVELS

        assert set(RISK_LEVELS) >= hedge_module._MARGIN_SUPPRESSES_ADD

    def test_roll_block_set_subset_of_roll_states(self):
        import typing

        from shared.instruments.futures import RollState

        roll_states = set(typing.get_args(RollState))
        assert roll_states >= hedge_module._ROLL_BLOCKS_FRONT_ADD
