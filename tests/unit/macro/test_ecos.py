import re

import aiohttp
import pytest
from aioresponses import aioresponses

from shared.macro.sources.ecos import ECOSSource


@pytest.mark.asyncio
async def test_ecos_parses_usdkrw():
    # Minimal ECOS response shape — real API is verbose; we only need row with DATA_VALUE
    payload = {
        "StatisticSearch": {
            "row": [
                {"TIME": "20260419", "DATA_VALUE": "1350.20"},
                {"TIME": "20260420", "DATA_VALUE": "1355.80"},
            ]
        }
    }
    with aioresponses() as m:
        # Use regex to match any date in the URL
        m.get(
            url=re.compile(
                r"https://ecos\.bok\.or\.kr/api/StatisticSearch/TEST_KEY/json/kr/1/2/731Y001/D/\d{8}/\d{8}/0000001"
            ),
            payload=payload,
        )
        async with aiohttp.ClientSession() as session:
            src = ECOSSource(api_key="TEST_KEY", session=session)
            snap = await src.fetch_fx_snapshot()
    assert snap.session == "overnight_fx"
    assert snap.usdkrw == 1355.80
    assert abs(snap.usdkrw_change_pct - (1355.80 - 1350.20) / 1350.20 * 100) < 1e-6
    assert "ecos" in snap.collected_from
