"""Unit tests for KIS ranking client (request mapping and constants)."""

import pytest

from shared.kis.auth import KISAuthConfig
from shared.kis.ranking_client import RankingEndpoints, _market_to_input_iscd, KISRankingClient


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


@pytest.mark.asyncio
async def test_ranking_rejects_mock_investment():
    client = KISRankingClient(
        KISAuthConfig(app_key="dummy", app_secret="dummy", is_real=False)
    )
    with pytest.raises(RuntimeError):
        await client.get_ranking(type="volume", market="KOSPI")

