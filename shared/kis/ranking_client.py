"""KIS domestic stock ranking API client.

Ranking references are sourced from `kis_docs/[국내주식] 순위분석.xlsx`.

Key endpoints used for screening:
  - 거래량순위: /uapi/domestic-stock/v1/quotations/volume-rank (TR: FHPST01710000)
  - 국내주식 등락률 순위: /uapi/domestic-stock/v1/ranking/fluctuation (TR: FHPST01700000)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Literal

import aiohttp

from shared.http import AsyncSessionMixin
from shared.kis.auth import KISAuthConfig, KISAuthManager

logger = logging.getLogger(__name__)


RankingType = Literal["volume", "gainer"]
MarketType = Literal["KOSPI", "KOSDAQ", "ALL", "KOSPI200", "KRX100"]


_MAX_KIS_RANKING_ROWS = 30


def _parse_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    s = str(value).strip().replace(",", "")
    if not s:
        return 0
    try:
        return int(float(s))
    except ValueError:
        return 0


def _parse_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", "")
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _market_to_input_iscd(market: str) -> str:
    m = (market or "").strip().upper()
    mapping = {
        "ALL": "0000",
        "KOSPI": "0001",
        "KOSDAQ": "1001",
        "KOSPI200": "2001",
        "KRX100": "4001",
    }
    if m not in mapping:
        raise ValueError(f"Unsupported market: {market}")
    return mapping[m]


@dataclass(frozen=True)
class RankingEndpoints:
    """Domestic stock ranking endpoint definitions."""

    # 거래량순위 (HTS 0171)
    volume_path: str = "/uapi/domestic-stock/v1/quotations/volume-rank"
    volume_tr_id_real: str = "FHPST01710000"

    # 등락률 순위 (HTS 0170)
    fluctuation_path: str = "/uapi/domestic-stock/v1/ranking/fluctuation"
    fluctuation_tr_id_real: str = "FHPST01700000"


class KISRankingClient(AsyncSessionMixin):
    """Async client for KIS domestic stock ranking APIs."""

    def __init__(self, config: KISAuthConfig, endpoints: RankingEndpoints | None = None):
        self.config = config
        self.endpoints = endpoints or RankingEndpoints()
        self.auth_manager = KISAuthManager.get_instance(config)

    async def close(self) -> None:
        await self._close_session()

    async def get_ranking(
        self,
        type: RankingType,
        market: MarketType,
        limit: int = _MAX_KIS_RANKING_ROWS,
        *,
        direction: Literal["up", "down"] = "up",
    ) -> list[dict[str, Any]]:
        """Fetch a ranking list.

        Args:
            type: "volume" or "gainer"
            market: "KOSPI" | "KOSDAQ" | "ALL" | "KOSPI200" | "KRX100"
            limit: Max number of rows (KIS returns at most 30)
            direction: For gainer ranking, "up" or "down"
        """
        if limit <= 0:
            return []
        if limit > _MAX_KIS_RANKING_ROWS:
            limit = _MAX_KIS_RANKING_ROWS

        if not self.config.is_real:
            raise RuntimeError("KIS ranking APIs are not supported in mock investment.")

        if type == "volume":
            raw = await self._get_volume_rank(market=market)
            items = self._extract_output_list(raw)
            normalized = [self._normalize_volume_row(x) for x in items]
            return normalized[:limit]

        if type == "gainer":
            raw = await self._get_fluctuation_rank(market=market, direction=direction)
            items = self._extract_output_list(raw)
            normalized = [self._normalize_fluctuation_row(x) for x in items]
            return normalized[:limit]

        raise ValueError(f"Unsupported ranking type: {type}")

    async def get_all_aggressive_sources(self, limit: int = _MAX_KIS_RANKING_ROWS) -> dict[str, Any]:
        """Fetch multiple ranking sources concurrently.

        This is meant for screeners: high volume + strong gainers across KOSPI/KOSDAQ.
        """
        tasks = [
            self.get_ranking(type="volume", market="KOSPI", limit=limit),
            self.get_ranking(type="volume", market="KOSDAQ", limit=limit),
            self.get_ranking(type="gainer", market="KOSPI", limit=limit),
            self.get_ranking(type="gainer", market="KOSDAQ", limit=limit),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            "kospi_volume": results[0] if not isinstance(results[0], Exception) else [],
            "kosdaq_volume": results[1] if not isinstance(results[1], Exception) else [],
            "kospi_gainer": results[2] if not isinstance(results[2], Exception) else [],
            "kosdaq_gainer": results[3] if not isinstance(results[3], Exception) else [],
        }

    async def _get_volume_rank(self, market: MarketType) -> dict[str, Any]:
        headers = await self._get_headers(self.endpoints.volume_tr_id_real)
        params = {
            # Docs show uppercase params for this endpoint.
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_COND_SCR_DIV_CODE": "20171",
            "FID_INPUT_ISCD": _market_to_input_iscd(market),
            "FID_DIV_CLS_CODE": "0",
            "FID_BLNG_CLS_CODE": "0",
            "FID_TRGT_CLS_CODE": "111111111",
            "FID_TRGT_EXLS_CLS_CODE": "000000",
            "FID_INPUT_PRICE_1": "0",
            "FID_INPUT_PRICE_2": "0",
            "FID_VOL_CNT": "",
            "FID_INPUT_DATE_1": "",
        }
        return await self._get(self.endpoints.volume_path, headers=headers, params=params)

    async def _get_fluctuation_rank(
        self, market: MarketType, direction: Literal["up", "down"]
    ) -> dict[str, Any]:
        headers = await self._get_headers(self.endpoints.fluctuation_tr_id_real)
        params = {
            # Docs show lowercase params for this endpoint.
            "fid_cond_mrkt_div_code": "J",
            "fid_cond_scr_div_code": "20170",
            "fid_input_iscd": _market_to_input_iscd(market),
            "fid_rank_sort_cls_code": "0" if direction == "up" else "1",
            "fid_input_cnt_1": "0",
            "fid_prc_cls_code": "0",
            "fid_input_price_1": "",
            "fid_input_price_2": "",
            "fid_vol_cnt": "",
            "fid_trgt_cls_code": "0",
            "fid_trgt_exls_cls_code": "0",
            "fid_div_cls_code": "0",
            "fid_rsfl_rate1": "",
            "fid_rsfl_rate2": "",
        }
        return await self._get(
            self.endpoints.fluctuation_path, headers=headers, params=params
        )

    async def _get_headers(self, tr_id: str) -> dict[str, str]:
        headers = await self.auth_manager.get_auth_headers_async()
        headers["tr_id"] = tr_id
        headers["custtype"] = "P"
        return headers

    async def _get(self, path: str, headers: dict[str, str], params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.config.base_url}{path}"
        session = await self._get_session()
        timeout_seconds = getattr(self.config, "request_timeout_seconds", 30)
        request_timeout = aiohttp.ClientTimeout(total=float(timeout_seconds))

        async with session.get(
            url, headers=headers, params=params, timeout=request_timeout
        ) as response:
            text = await response.text()
            if response.status != 200:
                raise RuntimeError(f"KIS ranking HTTP {response.status}: {text[:2000]}")
            try:
                data = await response.json()
            except Exception as e:
                raise RuntimeError(f"KIS ranking JSON decode failed: {e}: {text[:2000]}") from e

        if data.get("rt_cd") != "0":
            msg = data.get("msg1", "Unknown error")
            raise RuntimeError(f"KIS ranking API error: {msg}")
        return data

    @staticmethod
    def _extract_output_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
        # Most ranking APIs use 'output' as list. Some might use output1/output2.
        for key in ("output", "output1", "output2"):
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
        return []

    @staticmethod
    def _normalize_volume_row(row: dict[str, Any]) -> dict[str, Any]:
        code = row.get("mksc_shrn_iscd") or row.get("stck_shrn_iscd") or ""
        name = row.get("hts_kor_isnm") or row.get("stck_prpr_name") or ""
        return {
            "code": str(code).strip(),
            "name": str(name).strip(),
            "price": _parse_float(row.get("stck_prpr")),
            "change_pct": _parse_float(row.get("prdy_ctrt")),
            "volume": _parse_int(row.get("acml_vol")),
            "trade_value": _parse_int(row.get("acml_tr_pbmn")),
            "rank": _parse_int(row.get("data_rank")),
            "raw": row,
        }

    @staticmethod
    def _normalize_fluctuation_row(row: dict[str, Any]) -> dict[str, Any]:
        code = row.get("stck_shrn_iscd") or row.get("mksc_shrn_iscd") or ""
        name = row.get("hts_kor_isnm") or ""
        return {
            "code": str(code).strip(),
            "name": str(name).strip(),
            "price": _parse_float(row.get("stck_prpr")),
            "change_pct": _parse_float(row.get("prdy_ctrt") or row.get("prd_rsfl_rate")),
            "volume": _parse_int(row.get("acml_vol") or row.get("cntg_vol")),
            "trade_value": _parse_int(row.get("acml_tr_pbmn") or row.get("tr_pbmn")),
            "rank": _parse_int(row.get("data_rank")),
            "raw": row,
        }

