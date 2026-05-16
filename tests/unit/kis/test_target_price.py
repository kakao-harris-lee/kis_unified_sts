"""Unit tests for KIS invest-opinion target-price summaries."""

import pytest

from shared.kis.auth import KISAuthConfig
from shared.kis.client import KISClient


@pytest.mark.asyncio
async def test_summarize_target_price_builds_consensus(monkeypatch):
    client = KISClient(KISAuthConfig(app_key="dummy", app_secret="dummy", is_real=True))

    async def fake_fetch_invest_opinion(symbol, **kwargs):
        assert symbol == "005930"
        assert kwargs["lookback_days"] == 180
        return [
            {
                "stck_bsop_date": "20260515",
                "mbcr_name": "A증권",
                "invt_opnn": "BUY",
                "rgbf_invt_opnn": "BUY",
                "hts_goal_prc": "120000",
                "stck_prdy_clpr": "99000",
            },
            {
                "stck_bsop_date": "20260510",
                "mbcr_name": "B증권",
                "invt_opnn": "매수",
                "rgbf_invt_opnn": "중립",
                "hts_goal_prc": "110000",
                "stck_prdy_clpr": "99000",
            },
            {
                "stck_bsop_date": "20260301",
                "mbcr_name": "C증권",
                "invt_opnn": "HOLD",
                "rgbf_invt_opnn": "HOLD",
                "hts_goal_prc": "100000",
                "stck_prdy_clpr": "98000",
            },
        ]

    monkeypatch.setattr(client, "fetch_invest_opinion", fake_fetch_invest_opinion)

    summary = await client.summarize_target_price(
        "005930",
        current_price=100000,
        lookback_days=180,
        recent_days=30,
    )

    assert summary["available"] is True
    assert summary["target_price"] == 110000
    assert summary["latest_target_price"] == 120000
    assert summary["upside_pct"] == pytest.approx(10.0)
    assert summary["latest_target_upside_pct"] == pytest.approx(20.0)
    assert summary["date"] == "2026-05-15"
    assert summary["latest_broker"] == "A증권"
    assert summary["sample_count"] == 3
    assert summary["coverage_count"] == 3
    assert summary["revision_direction"] == "up"
    assert summary["revision_30d_pct"] == pytest.approx(15.0)
    assert summary["dispersion_pct"] == pytest.approx(18.1818, rel=1e-4)
    assert summary["opinion_distribution"] == {"BUY": 1, "매수": 1, "HOLD": 1}
    assert summary["recent_reports"][0]["broker"] == "A증권"


@pytest.mark.asyncio
async def test_summarize_target_price_returns_unavailable_without_targets(monkeypatch):
    client = KISClient(KISAuthConfig(app_key="dummy", app_secret="dummy", is_real=True))

    async def fake_fetch_invest_opinion(symbol, **kwargs):
        return [{"stck_bsop_date": "20260515", "hts_goal_prc": "0"}]

    monkeypatch.setattr(client, "fetch_invest_opinion", fake_fetch_invest_opinion)

    summary = await client.summarize_target_price("005930", current_price=100000)

    assert summary["available"] is False
    assert summary["target_price"] == 0.0
    assert summary["recent_reports"] == []


@pytest.mark.asyncio
async def test_fetch_invest_opinion_rejects_mock_investment():
    client = KISClient(
        KISAuthConfig(app_key="dummy", app_secret="dummy", is_real=False)
    )

    with pytest.raises(RuntimeError):
        await client.fetch_invest_opinion("005930")
