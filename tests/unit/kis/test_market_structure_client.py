"""KIS market-structure quotation TR wrappers (roadmap Phase 0, Wave 2b).

Response-fixture parsing tests for FHPTJ04030000 / FHPPG04600001 /
FHPUP02100000 / FHKUP03500100 plus the FHMIF10000000 open-interest snapshot
fields. No real network: aiohttp GET is patched (test_client_futures.py
conventions).
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.kis.client import KISAuthConfig, KISClient


@pytest.fixture
def mock_auth_manager():
    with patch("shared.kis.client.KISAuthManager") as MockManager:
        instance = MockManager.get_instance.return_value
        instance.get_auth_headers_async = AsyncMock(
            return_value={"Authorization": "Bearer token"}
        )
        yield instance


@pytest.fixture
def client(mock_auth_manager):
    config = KISAuthConfig(app_key="test", app_secret="test", is_real=True)
    return KISClient(config)


def _response(payload, *, status=200, tr_cont="", text=""):
    resp = AsyncMock()
    resp.status = status
    resp.json.return_value = payload
    resp.text.return_value = text
    resp.headers = {"tr_cont": tr_cont}
    return resp


def _context(resp):
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=resp)
    ctx.__aexit__ = AsyncMock(return_value=None)
    return ctx


def _install(client, responses):
    """Wire canned responses into the client session; returns the get mock."""
    mock_get = MagicMock(side_effect=[_context(resp) for resp in responses])
    session = MagicMock()
    session.closed = False
    session.get = mock_get
    client._session = session
    return mock_get


@pytest.mark.asyncio
async def test_fetch_market_investor_trend_parses_output_rows(client):
    payload = {
        "rt_cd": "0",
        "output": [
            {"frgn_ntby_qty": "-1,250", "frgn_ntby_tr_pbmn": "-31,500"},
            {"frgn_ntby_qty": "300"},
        ],
    }
    mock_get = _install(client, [_response(payload)])

    rows = await client.fetch_market_investor_trend("K2I", "F001")

    assert rows == payload["output"]
    call = mock_get.call_args
    assert "/uapi/domestic-stock/v1/quotations/inquire-investor-time-by-market" in (
        call[0][0]
    )
    assert call[1]["headers"]["tr_id"] == "FHPTJ04030000"
    assert call[1]["headers"]["custtype"] == "P"
    assert call[1]["params"] == {
        "FID_INPUT_ISCD": "K2I",
        "FID_INPUT_ISCD_2": "F001",
    }


@pytest.mark.asyncio
async def test_fetch_market_investor_trend_wraps_dict_output(client):
    payload = {"rt_cd": "0", "output": {"frgn_ntby_qty": "42"}}
    _install(client, [_response(payload)])

    rows = await client.fetch_market_investor_trend("K2I", "F001")

    assert rows == [{"frgn_ntby_qty": "42"}]


@pytest.mark.asyncio
async def test_fetch_program_trade_daily_single_page(client):
    payload = {
        "rt_cd": "0",
        "output": [
            {"stck_bsop_date": "20260702", "whol_ntby_tr_pbmn": "-1234"},
        ],
    }
    mock_get = _install(client, [_response(payload)])

    rows = await client.fetch_program_trade_daily(
        date(2026, 7, 1), date(2026, 7, 2), market_div="J"
    )

    assert rows == payload["output"]
    assert mock_get.call_count == 1
    call = mock_get.call_args
    assert "/uapi/domestic-stock/v1/quotations/comp-program-trade-daily" in call[0][0]
    assert call[1]["headers"]["tr_id"] == "FHPPG04600001"
    assert "tr_cont" not in call[1]["headers"]
    assert call[1]["params"] == {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_MRKT_CLS_CODE": "K",
        "FID_INPUT_DATE_1": "20260701",
        "FID_INPUT_DATE_2": "20260702",
    }


@pytest.mark.asyncio
async def test_fetch_program_trade_daily_follows_tr_cont(client):
    first = {"rt_cd": "0", "output": [{"stck_bsop_date": "20260701"}]}
    second = {"rt_cd": "0", "output": [{"stck_bsop_date": "20260702"}]}
    mock_get = _install(
        client,
        [_response(first, tr_cont="M"), _response(second, tr_cont="")],
    )

    rows = await client.fetch_program_trade_daily("2026-07-01", "2026-07-02")

    assert [row["stck_bsop_date"] for row in rows] == ["20260701", "20260702"]
    assert mock_get.call_count == 2
    # the continuation request must carry tr_cont=N
    second_call = mock_get.call_args_list[1]
    assert second_call[1]["headers"]["tr_cont"] == "N"


@pytest.mark.asyncio
async def test_fetch_program_trade_daily_respects_max_pages(client):
    page = {"rt_cd": "0", "output": [{"stck_bsop_date": "20260701"}]}
    mock_get = _install(client, [_response(page, tr_cont="M")] * 5)

    rows = await client.fetch_program_trade_daily(
        date(2026, 7, 1), date(2026, 7, 2), max_pages=2
    )

    assert len(rows) == 2
    assert mock_get.call_count == 2


@pytest.mark.asyncio
async def test_fetch_index_price_returns_output_dict(client):
    payload = {
        "rt_cd": "0",
        "output": {"bstp_nmix_prpr": "380.11", "bstp_nmix_prdy_ctrt": "-0.62"},
    }
    mock_get = _install(client, [_response(payload)])

    output = await client.fetch_index_price("2001", market_div="U")

    assert output == payload["output"]
    call = mock_get.call_args
    assert "/uapi/domestic-stock/v1/quotations/inquire-index-price" in call[0][0]
    assert call[1]["headers"]["tr_id"] == "FHPUP02100000"
    assert call[1]["params"] == {
        "FID_COND_MRKT_DIV_CODE": "U",
        "FID_INPUT_ISCD": "2001",
    }


@pytest.mark.asyncio
async def test_fetch_index_price_non_dict_output_degrades_to_empty(client):
    _install(client, [_response({"rt_cd": "0", "output": []})])

    assert await client.fetch_index_price("2001") == {}


@pytest.mark.asyncio
async def test_fetch_index_daily_candles_returns_output2_rows(client):
    payload = {
        "rt_cd": "0",
        "output1": {"bstp_nmix_prpr": "380.11"},
        "output2": [
            {"stck_bsop_date": "20260702", "bstp_nmix_prpr": "380.11"},
            {"stck_bsop_date": "20260701", "bstp_nmix_prpr": "381.02"},
            "garbage",
        ],
    }
    mock_get = _install(client, [_response(payload)])

    rows = await client.fetch_index_daily_candles(
        "2001", date(2026, 3, 25), date(2026, 7, 2)
    )

    assert [row["stck_bsop_date"] for row in rows] == ["20260702", "20260701"]
    call = mock_get.call_args
    assert (
        "/uapi/domestic-stock/v1/quotations/inquire-daily-indexchartprice" in call[0][0]
    )
    assert call[1]["headers"]["tr_id"] == "FHKUP03500100"
    assert call[1]["params"] == {
        "FID_COND_MRKT_DIV_CODE": "U",
        "FID_INPUT_ISCD": "2001",
        "FID_INPUT_DATE_1": "20260325",
        "FID_INPUT_DATE_2": "20260702",
        "FID_PERIOD_DIV_CODE": "D",
    }


@pytest.mark.asyncio
async def test_quotation_tr_raises_on_api_error(client):
    payload = {"rt_cd": "1", "msg1": "모의투자 미지원 TR입니다."}
    _install(client, [_response(payload)])

    with pytest.raises(RuntimeError, match="FHPTJ04030000"):
        await client.fetch_market_investor_trend("K2I", "F001")


@pytest.mark.asyncio
async def test_quotation_tr_raises_on_http_error(client):
    _install(client, [_response({}, status=500, text="server error")])

    with pytest.raises(RuntimeError, match="HTTP 500"):
        await client.fetch_index_price("2001")


@pytest.mark.asyncio
async def test_futures_quote_parses_open_interest_snapshot(client):
    payload = {
        "rt_cd": "0",
        "output1": {
            "futs_prpr": "381.40",
            "futs_prdy_clpr": "384.30",
            "futs_prdy_ctrt": "-0.75",
            "acml_vol": "152000",
            "hts_otst_stpl_qty": "248,100",
            "otst_stpl_qty_icdc": "1530",
        },
    }
    _install(client, [_response(payload)])

    quote = await client.get_current_price("101S6000")

    assert quote["close"] == 381.40
    assert quote["change"] == pytest.approx(-0.0075)
    assert quote["open_interest"] == 248_100.0
    assert quote["open_interest_change"] == 1_530.0


@pytest.mark.asyncio
async def test_futures_quote_missing_oi_fields_are_none_not_zero(client):
    payload = {
        "rt_cd": "0",
        "output1": {"futs_prpr": "381.40", "futs_prdy_clpr": "384.30"},
    }
    _install(client, [_response(payload)])

    quote = await client.get_current_price("101S6000")

    assert quote["open_interest"] is None
    assert quote["open_interest_change"] is None
