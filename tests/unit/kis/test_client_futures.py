
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from shared.kis.client import KISClient, KISAuthConfig

@pytest.fixture
def mock_auth_manager():
    with patch("shared.kis.client.KISAuthManager") as MockManager:
        instance = MockManager.get_instance.return_value
        instance.get_auth_headers_async = AsyncMock(return_value={"Authorization": "Bearer token"})
        yield instance

@pytest.fixture
def client(mock_auth_manager):
    config = KISAuthConfig(app_key="test", app_secret="test", is_real=False)
    return KISClient(config)

@pytest.mark.asyncio
async def test_is_futures_detection(client):
    assert client._is_futures("101S6000") is True  # KOSPI 200
    assert client._is_futures("105S6000") is True  # KOSPI 200 Mini
    assert client._is_futures("005930") is False   # Samsung Electronics
    assert client._is_futures("000660") is False   # SK Hynix

@pytest.mark.asyncio
async def test_get_futures_current_price(client):
    symbol = "101S6000"
    mock_response = {
        "rt_cd": "0",
        "msg_cd": "MCA00000",
        "msg1": "정상처리 되었습니다.",
        "output1": {
            "hts_kor_isnm": "F 202603",
            "futs_prpr": "350.50",
            "futs_oprc": "350.00",
            "futs_hgpr": "351.00",
            "futs_lwpr": "349.50",
            "acml_vol": "1000",
            "futs_prdy_ctrt": "0.50"
        }
    }

    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_resp_obj = AsyncMock()
        mock_resp_obj.status = 200
        mock_resp_obj.json.return_value = mock_response
        mock_get.return_value.__aenter__.return_value = mock_resp_obj

        # Inject mock session
        client._session = MagicMock()
        client._session.get = mock_get

        price = await client.get_current_price(symbol)

        assert price["code"] == symbol
        assert price["close"] == 350.50
        assert price["volume"] == 1000

        # Verify TR ID and URL
        call_args = mock_get.call_args
        assert "/uapi/domestic-futureoption/v1/quotations/inquire-price" in call_args[0][0]
        assert call_args[1]["headers"]["tr_id"] == "FHMIF10000000"
        assert call_args[1]["params"]["FID_COND_MRKT_DIV_CODE"] == "F"

@pytest.mark.asyncio
async def test_get_futures_minute_bars(client):
    symbol = "105S6000"
    mock_response = {
        "rt_cd": "0",
        "output2": [
            {
                "stck_prpr": "350.50",
                "stck_oprc": "350.00",
                "stck_hgpr": "351.00",
                "stck_lwpr": "349.50",
                "cntg_vol": "10"
            },
            {
                "stck_prpr": "350.00",
                "stck_oprc": "349.50",
                "stck_hgpr": "350.00",
                "stck_lwpr": "349.00",
                "cntg_vol": "20"
            }
        ]
    }

    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_resp_obj = AsyncMock()
        mock_resp_obj.status = 200
        mock_resp_obj.json.return_value = mock_response
        mock_get.return_value.__aenter__.return_value = mock_resp_obj

        # Inject mock session
        client._session = MagicMock()
        client._session.get = mock_get

        bars = await client.get_minute_bars(symbol, count=2)

        assert len(bars) == 2
        # Verify oldest first
        assert bars[0]["close"] == 350.00
        assert bars[1]["close"] == 350.50

        # Verify TR ID and URL
        call_args = mock_get.call_args
        assert "/uapi/domestic-futureoption/v1/quotations/inquire-time-fuopchartprice" in call_args[0][0]
        assert call_args[1]["headers"]["tr_id"] == "FHKIF03020200"
