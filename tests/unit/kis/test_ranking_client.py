"""Unit tests for KIS ranking client (request mapping and constants)."""

import asyncio

import pytest

from shared.kis.auth import KISAuthConfig
from shared.kis.ranking_client import (
    KISRankingClient,
    RankingEndpoints,
    _market_to_input_iscd,
)


def test_market_to_input_iscd_mapping():
    assert _market_to_input_iscd("ALL") == "0000"
    assert _market_to_input_iscd("KOSPI") == "0001"
    assert _market_to_input_iscd("KOSDAQ") == "1001"
    assert _market_to_input_iscd("KOSPI200") == "2001"
    assert _market_to_input_iscd("KRX100") == "4001"


def test_endpoints_match_kis_docs():
    e = RankingEndpoints()
    assert e.volume_path == "/uapi/domestic-stock/v1/quotations/volume-rank"
    assert e.volume_tr_id_real == "FHPST01710000"
    assert e.fluctuation_path == "/uapi/domestic-stock/v1/ranking/fluctuation"
    assert e.fluctuation_tr_id_real == "FHPST01700000"
    assert e.volume_power_path == "/uapi/domestic-stock/v1/ranking/volume-power"
    assert e.volume_power_tr_id_real == "FHPST01680000"
    assert e.near_new_highlow_path == (
        "/uapi/domestic-stock/v1/ranking/near-new-highlow"
    )
    assert e.near_new_highlow_tr_id_real == "FHPST01870000"


def test_rate_limit_error_detection():
    assert KISRankingClient._is_rate_limit_error("EGW00201: 초당 거래건수 초과")
    assert KISRankingClient._is_rate_limit_error("RATE limit exceeded")
    assert not KISRankingClient._is_rate_limit_error("normal business error")


@pytest.mark.asyncio
async def test_ranking_rejects_mock_investment():
    client = KISRankingClient(
        KISAuthConfig(app_key="dummy", app_secret="dummy", is_real=False)
    )
    with pytest.raises(RuntimeError):
        await client.get_ranking(type="volume", market="KOSPI")


def test_normalize_volume_power_row():
    row = {
        "stck_shrn_iscd": "005930",
        "hts_kor_isnm": "삼성전자",
        "stck_prpr": "75000",
        "prdy_ctrt": "3.21",
        "acml_vol": "1234567",
        "data_rank": "2",
        "tday_rltv": "185.5",
        "seln_cnqn_smtn": "1111",
        "shnu_cnqn_smtn": "2222",
    }

    normalized = KISRankingClient._normalize_volume_power_row(row)

    assert normalized["code"] == "005930"
    assert normalized["name"] == "삼성전자"
    assert normalized["price"] == 75000.0
    assert normalized["change_pct"] == 3.21
    assert normalized["volume"] == 1234567
    assert normalized["rank"] == 2
    assert normalized["volume_power"] == 185.5
    assert normalized["sell_volume"] == 1111
    assert normalized["buy_volume"] == 2222


def test_normalize_near_new_highlow_row():
    row = {
        "mksc_shrn_iscd": "000660",
        "hts_kor_isnm": "SK하이닉스",
        "stck_prpr": "210000",
        "prdy_ctrt": "4.5",
        "acml_vol": "555555",
        "new_hgpr": "215000",
        "hprc_near_rate": "1.23",
        "new_lwpr": "120000",
        "lwpr_near_rate": "75.0",
        "bidp": "209500",
        "askp": "210000",
        "bidp_rsqn1": "99",
        "askp_rsqn1": "88",
    }

    normalized = KISRankingClient._normalize_near_new_highlow_row(row)

    assert normalized["code"] == "000660"
    assert normalized["name"] == "SK하이닉스"
    assert normalized["near_high_rate"] == 1.23
    assert normalized["new_high"] == 215000.0
    assert normalized["near_low_rate"] == 75.0
    assert normalized["new_low"] == 120000.0
    assert normalized["bid_quantity"] == 99
    assert normalized["ask_quantity"] == 88


@pytest.mark.asyncio
async def test_get_all_aggressive_sources_can_disable_swing_sources(monkeypatch):
    client = KISRankingClient(
        KISAuthConfig(app_key="dummy", app_secret="dummy", is_real=True),
        inter_call_seconds=0.0,
    )
    calls: list[str] = []

    async def fake_get_ranking(*, type, market, limit=30, direction="up"):
        _ = market, limit, direction
        calls.append(type)
        return []

    monkeypatch.setattr(client, "get_ranking", fake_get_ranking)

    sources = await client.get_all_aggressive_sources(limit=5, include_swing=False)

    assert "volume_power" not in calls
    assert "near_new_high" not in calls
    assert sources["kospi_volume_power"] == []
    assert sources["kosdaq_volume_power"] == []
    assert sources["kospi_near_new_high"] == []
    assert sources["kosdaq_near_new_high"] == []


# ---------------------------------------------------------------------------
# Rate-limit pacing and EGW retry tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sources_fetched_sequentially_not_concurrent(monkeypatch):
    """get_all_aggressive_sources must not fire calls concurrently.

    We verify this by recording active-concurrency counts: if more than one
    call is in-flight at any point, the test fails.
    """
    client = KISRankingClient(
        KISAuthConfig(app_key="dummy", app_secret="dummy", is_real=True),
        inter_call_seconds=0.0,  # no sleep delay in the test
    )
    in_flight = 0
    max_in_flight = 0
    call_count = 0

    async def fake_get_ranking(*, type, market, limit=30, direction="up"):
        nonlocal in_flight, max_in_flight, call_count
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        call_count += 1
        await asyncio.sleep(0)  # yield to event loop
        in_flight -= 1
        return []

    monkeypatch.setattr(client, "get_ranking", fake_get_ranking)

    await client.get_all_aggressive_sources(limit=5, include_swing=True)

    assert call_count == 10, f"Expected 10 source calls, got {call_count}"
    assert max_in_flight == 1, (
        f"Calls were concurrent: max_in_flight={max_in_flight} "
        "(should be 1 — sequential)"
    )


@pytest.mark.asyncio
async def test_egw_throttle_retried_and_source_recovered(monkeypatch):
    """A single EGW throttle response is retried once; source must succeed on retry."""
    client = KISRankingClient(
        KISAuthConfig(app_key="dummy", app_secret="dummy", is_real=True),
        inter_call_seconds=0.0,
        retry_backoff_seconds=0.0,  # no sleep in tests
    )
    attempts: dict[str, int] = {}

    async def fake_get_ranking(*, type, market, limit=30, direction="up"):
        key = f"{type}_{market}"
        attempts[key] = attempts.get(key, 0) + 1
        # Fail the first attempt for kospi_volume with an EGW throttle error.
        if type == "volume" and market == "KOSPI" and attempts[key] == 1:
            raise RuntimeError(
                'KIS ranking API error: {"rt_cd":"1","msg1":"초당 거래건수를 초과하였습니다.",'
                '"msg_cd":"EGW00201"}'
            )
        return [{"code": f"00000{attempts[key]}", "name": "test"}]

    monkeypatch.setattr(client, "get_ranking", fake_get_ranking)

    sources = await client.get_all_aggressive_sources(limit=5, include_swing=False)

    # kospi_volume should have recovered on the second attempt.
    assert len(sources["kospi_volume"]) > 0, "kospi_volume should recover after retry"
    assert attempts.get("volume_KOSPI", 0) == 2, "kospi_volume must be attempted twice"


@pytest.mark.asyncio
async def test_egw_throttle_second_attempt_also_fails_logs_and_drops(
    monkeypatch, caplog
):
    """If both attempts fail with EGW throttle, source is dropped with a warning."""
    import logging

    client = KISRankingClient(
        KISAuthConfig(app_key="dummy", app_secret="dummy", is_real=True),
        inter_call_seconds=0.0,
        retry_backoff_seconds=0.0,
    )

    async def fake_get_ranking(*, type, market, limit=30, direction="up"):
        if type == "volume" and market == "KOSPI":
            raise RuntimeError(
                'KIS ranking API error: {"rt_cd":"1","msg1":"초당 거래건수를 초과하였습니다.",'
                '"msg_cd":"EGW00201"}'
            )
        return []

    monkeypatch.setattr(client, "get_ranking", fake_get_ranking)

    with caplog.at_level(logging.WARNING, logger="shared.kis.ranking_client"):
        sources = await client.get_all_aggressive_sources(limit=5, include_swing=False)

    assert sources["kospi_volume"] == [], "Failed source must degrade to empty list"
    # Should log the EGW retry attempt and then the final failure.
    egw_logs = [
        r
        for r in caplog.records
        if "EGW" in r.message or "throttle" in r.message.lower()
    ]
    final_fail_logs = [
        r for r in caplog.records if "ranking source failed" in r.message
    ]
    assert egw_logs, "Should log EGW throttle on first attempt"
    assert final_fail_logs, "Should log final failure after both attempts exhausted"


@pytest.mark.asyncio
async def test_non_throttle_error_not_retried(monkeypatch):
    """Non-EGW errors should not trigger the retry path."""
    client = KISRankingClient(
        KISAuthConfig(app_key="dummy", app_secret="dummy", is_real=True),
        inter_call_seconds=0.0,
        retry_backoff_seconds=0.0,
    )
    attempts: dict[str, int] = {}

    async def fake_get_ranking(*, type, market, limit=30, direction="up"):
        key = f"{type}_{market}"
        attempts[key] = attempts.get(key, 0) + 1
        if type == "volume" and market == "KOSPI":
            raise RuntimeError("KIS ranking API error: some unrelated business error")
        return []

    monkeypatch.setattr(client, "get_ranking", fake_get_ranking)

    sources = await client.get_all_aggressive_sources(limit=5, include_swing=False)

    assert sources["kospi_volume"] == []
    # Non-throttle error must NOT trigger a retry — only one attempt.
    assert (
        attempts.get("volume_KOSPI", 0) == 1
    ), "Non-throttle errors must not be retried (attempt count should be 1)"


@pytest.mark.asyncio
async def test_inter_call_delay_applied_between_sources(monkeypatch):
    """The inter_call_seconds delay is applied between consecutive source calls."""
    sleep_calls: list[float] = []

    async def recording_sleep(delay: float) -> None:
        sleep_calls.append(delay)
        # Don't actually sleep in tests — just record.

    monkeypatch.setattr(asyncio, "sleep", recording_sleep)

    client = KISRankingClient(
        KISAuthConfig(app_key="dummy", app_secret="dummy", is_real=True),
        inter_call_seconds=0.25,
    )

    async def fake_get_ranking(*, type, market, limit=30, direction="up"):
        return []

    monkeypatch.setattr(client, "get_ranking", fake_get_ranking)

    await client.get_all_aggressive_sources(limit=5, include_swing=True)

    # 10 sources: 9 inter-call gaps (first source has no preceding gap).
    inter_call_delays = [d for d in sleep_calls if d == 0.25]
    assert (
        len(inter_call_delays) == 9
    ), f"Expected 9 inter-call delays of 0.25s, got {len(inter_call_delays)}: {sleep_calls}"
