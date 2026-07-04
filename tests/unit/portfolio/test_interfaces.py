"""Contract tests for the lightweight portfolio interface surface."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from shared.portfolio.hedge import (
    BetaEstimate,
    HedgeAdvisorConfig,
    compute_hedge_advice,
)
from shared.portfolio.interfaces import (
    HedgeAdviceView,
    HedgeAdvisorProtocol,
    HedgeBetaEstimateView,
    HedgeExposureView,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
ASOF = datetime(2026, 7, 6, 19, 0)
MULTIPLIERS = {"kospi200_mini": 50_000.0, "kospi200_full": 250_000.0}


@dataclass(frozen=True)
class _ExposureAdapter:
    stock_positions: list[dict[str, Any]]
    futures_positions: list[dict[str, Any]]
    betas: dict[str, BetaEstimate]
    multipliers: dict[str, float]
    futures_price: float | None
    futures_price_fresh: bool
    band: str | None
    score: float | None
    asof_ts: datetime
    extra_missing: tuple[str, ...] = field(default_factory=tuple)


class _ComputeHedgeAdvisorAdapter:
    def __init__(self, config: HedgeAdvisorConfig) -> None:
        self._config = config

    def advise(self, exposure: HedgeExposureView) -> HedgeAdviceView:
        return compute_hedge_advice(
            config=self._config,
            stock_positions=exposure.stock_positions,
            futures_positions=exposure.futures_positions,
            betas=exposure.betas,
            multipliers=exposure.multipliers,
            futures_price=exposure.futures_price,
            futures_price_fresh=exposure.futures_price_fresh,
            band=exposure.band,
            score=exposure.score,
            asof_ts=exposure.asof_ts,
            extra_missing=exposure.extra_missing,
        )


def test_importing_interfaces_does_not_load_hedge_or_execution_modules():
    snippet = textwrap.dedent("""
        import sys

        import shared.portfolio.interfaces  # noqa: F401

        forbidden = sorted(
            name
            for name in sys.modules
            if (
                name == "shared.portfolio.hedge"
                or name == "shared.execution"
                or name.startswith("shared.execution.")
                or name == "shared.order"
                or name.startswith("shared.order.")
                or name == "services.order_router"
                or name.startswith("services.order_router.")
                or name == "services.stock_order_router"
                or name.startswith("services.stock_order_router.")
            )
        )
        if forbidden:
            print("forbidden modules imported: " + ", ".join(forbidden))
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


def test_current_beta_and_advice_objects_satisfy_views():
    beta = BetaEstimate(beta=1.2, observations=120, fallback=False)
    advice = compute_hedge_advice(
        config=HedgeAdvisorConfig(),
        stock_positions=[
            {
                "code": "005930",
                "side": "long",
                "quantity": 1000,
                "current_price": 60_000,
            }
        ],
        futures_positions=[],
        betas={"005930": beta},
        multipliers=MULTIPLIERS,
        futures_price=400.0,
        futures_price_fresh=True,
        band="HIGH",
        score=80.0,
        asof_ts=ASOF,
    )

    assert isinstance(beta, HedgeBetaEstimateView)
    assert isinstance(advice, HedgeAdviceView)
    assert advice.recommended_short_contracts == 3
    assert advice.advisory_active is True


def test_small_compute_adapter_satisfies_hedge_advisor_protocol():
    exposure = _ExposureAdapter(
        stock_positions=[
            {
                "code": "005930",
                "side": "long",
                "quantity": 1000,
                "current_price": 60_000,
            }
        ],
        futures_positions=[],
        betas={"005930": BetaEstimate(beta=1.0, observations=120, fallback=False)},
        multipliers=MULTIPLIERS,
        futures_price=400.0,
        futures_price_fresh=True,
        band="HIGH",
        score=80.0,
        asof_ts=ASOF,
    )
    advisor = _ComputeHedgeAdvisorAdapter(HedgeAdvisorConfig())

    assert isinstance(exposure, HedgeExposureView)
    assert isinstance(advisor, HedgeAdvisorProtocol)

    advice = advisor.advise(exposure)
    assert isinstance(advice, HedgeAdviceView)
    assert advice.recommended_short_contracts == 3
    assert advice.net_beta_exposure == pytest.approx(60_000_000.0)
