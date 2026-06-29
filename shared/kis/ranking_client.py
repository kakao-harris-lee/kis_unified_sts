"""KIS domestic stock ranking API client.

Ranking references are sourced from `kis_docs/[국내주식] 순위분석.xlsx`.

Key endpoints used for screening:
  - 거래량순위: /uapi/domestic-stock/v1/quotations/volume-rank (TR: FHPST01710000)
  - 국내주식 등락률 순위: /uapi/domestic-stock/v1/ranking/fluctuation (TR: FHPST01700000)
  - 체결강도상위: /uapi/domestic-stock/v1/ranking/volume-power (TR: FHPST01680000)
  - 신고/신저 근접종목 상위: /uapi/domestic-stock/v1/ranking/near-new-highlow (TR: FHPST01870000)

Rate-limiting note
------------------
``get_all_aggressive_sources`` iterates the ranking sources **sequentially** with a
configurable inter-call delay (``KIS_RANKING_INTER_CALL_SECONDS``, default 0.25 s)
rather than firing them all concurrently via ``asyncio.gather``.  Concurrent fan-out
caused the screener to burst up to 10 calls within a single second against an API key
that also services the trend-confirmation ``KISClient``, overwhelming KIS's per-second
transaction limit (EGW "초당 거래건수를 초과하였습니다.").

When KIS returns an EGW throttle response the source is retried once after
``KIS_RANKING_RETRY_BACKOFF_SECONDS`` (default 1.0 s) before being dropped for
that cycle so a transient burst recovers within the same sweep.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any, Literal

import aiohttp

from shared.http import AsyncSessionMixin
from shared.kis.auth import KISAuthConfig, KISAuthManager
from shared.kis.client import _DEFAULT_RATE_LIMIT, _RateLimiter
from shared.utils.parsing import parse_float, parse_int

logger = logging.getLogger(__name__)


RankingType = Literal["volume", "gainer", "volume_power", "near_new_high"]
MarketType = Literal["KOSPI", "KOSDAQ", "ALL", "KOSPI200", "KRX100"]


_MAX_KIS_RANKING_ROWS = 30

# Default inter-call delay between sequential ranking source fetches (seconds).
# Matches the ``stagger_delay`` convention in streaming.yaml / DataProvider.
_DEFAULT_INTER_CALL_SECONDS = float(
    os.environ.get("KIS_RANKING_INTER_CALL_SECONDS", "0.25")
)

# Backoff (seconds) before retrying a source that returned an EGW throttle error.
_DEFAULT_RETRY_BACKOFF_SECONDS = float(
    os.environ.get("KIS_RANKING_RETRY_BACKOFF_SECONDS", "1.0")
)


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

    # 체결강도상위 (HTS 0168)
    volume_power_path: str = "/uapi/domestic-stock/v1/ranking/volume-power"
    volume_power_tr_id_real: str = "FHPST01680000"

    # 신고/신저 근접종목 상위 (HTS 0187)
    near_new_highlow_path: str = "/uapi/domestic-stock/v1/ranking/near-new-highlow"
    near_new_highlow_tr_id_real: str = "FHPST01870000"


class KISRankingClient(AsyncSessionMixin):
    """Async client for KIS domestic stock ranking APIs."""

    def __init__(
        self,
        config: KISAuthConfig,
        endpoints: RankingEndpoints | None = None,
        *,
        inter_call_seconds: float | None = None,
        retry_backoff_seconds: float | None = None,
    ):
        self.config = config
        self.endpoints = endpoints or RankingEndpoints()
        self.auth_manager = KISAuthManager.get_instance(config)
        rate_limit = int(
            os.environ.get(
                "KIS_RANKING_API_RATE_LIMIT",
                os.environ.get("KIS_API_RATE_LIMIT", str(_DEFAULT_RATE_LIMIT)),
            )
        )
        self._rate_limiter = _RateLimiter(max_requests=max(1, rate_limit))
        # Inter-call pacing: minimum sleep between sequential source fetches.
        self._inter_call_seconds = (
            inter_call_seconds
            if inter_call_seconds is not None
            else _DEFAULT_INTER_CALL_SECONDS
        )
        # Backoff before retrying an EGW-throttled source.
        self._retry_backoff_seconds = (
            retry_backoff_seconds
            if retry_backoff_seconds is not None
            else _DEFAULT_RETRY_BACKOFF_SECONDS
        )

    async def close(self) -> None:
        await self._close_session()

    @property
    def is_rate_limited(self) -> bool:
        """True while ranking requests are backing off from KIS rate limiting."""
        return self._rate_limiter.is_penalized

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
            type: "volume", "gainer", "volume_power", or "near_new_high"
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

        if type == "volume_power":
            raw = await self._get_volume_power_rank(market=market)
            items = self._extract_output_list(raw)
            normalized = [self._normalize_volume_power_row(x) for x in items]
            return normalized[:limit]

        if type == "near_new_high":
            raw = await self._get_near_new_highlow_rank(market=market)
            items = self._extract_output_list(raw)
            normalized = [self._normalize_near_new_highlow_row(x) for x in items]
            return normalized[:limit]

        raise ValueError(f"Unsupported ranking type: {type}")

    async def get_all_aggressive_sources(
        self, limit: int = _MAX_KIS_RANKING_ROWS, *, include_swing: bool = True
    ) -> dict[str, Any]:
        """Fetch multiple ranking sources sequentially with inter-call pacing.

        Sources are fetched one at a time (not concurrently) to avoid bursting
        multiple calls per second against the shared KIS API key.  A short
        ``inter_call_seconds`` gap is inserted between consecutive fetches.

        When KIS returns an EGW per-second throttle response (rt_cd != "0",
        "초당 거래건수") the source is retried once after ``retry_backoff_seconds``
        before being recorded as failed for this cycle.  This lets a transient
        burst recover within the same sweep rather than silently dropping sources.

        This is meant for screeners: high volume + strong gainers + losers
        across KOSPI/KOSDAQ. When include_swing is true, also fetches
        short-term momentum discovery inputs for volume power and near-new-high.
        """
        source_specs: list[tuple[str, str, str, str]] = [
            # (key, type, market, direction)
            ("kospi_volume", "volume", "KOSPI", "up"),
            ("kosdaq_volume", "volume", "KOSDAQ", "up"),
            ("kospi_gainer", "gainer", "KOSPI", "up"),
            ("kosdaq_gainer", "gainer", "KOSDAQ", "up"),
            ("kospi_loser", "gainer", "KOSPI", "down"),
            ("kosdaq_loser", "gainer", "KOSDAQ", "down"),
        ]
        if include_swing:
            source_specs += [
                ("kospi_volume_power", "volume_power", "KOSPI", "up"),
                ("kosdaq_volume_power", "volume_power", "KOSDAQ", "up"),
                ("kospi_near_new_high", "near_new_high", "KOSPI", "up"),
                ("kosdaq_near_new_high", "near_new_high", "KOSDAQ", "up"),
            ]

        results: dict[str, Any] = {}
        for idx, (key, rtype, market, direction) in enumerate(source_specs):
            if idx > 0 and self._inter_call_seconds > 0:
                await asyncio.sleep(self._inter_call_seconds)
            result = await self._fetch_source_with_retry(
                key=key,
                rtype=rtype,  # type: ignore[arg-type]
                market=market,  # type: ignore[arg-type]
                direction=direction,  # type: ignore[arg-type]
                limit=limit,
            )
            results[key] = result

        # Ensure all swing keys are present even when include_swing=False.
        for key in (
            "kospi_volume_power",
            "kosdaq_volume_power",
            "kospi_near_new_high",
            "kosdaq_near_new_high",
        ):
            results.setdefault(key, [])

        return {
            "kospi_volume": results["kospi_volume"],
            "kosdaq_volume": results["kosdaq_volume"],
            "kospi_gainer": results["kospi_gainer"],
            "kosdaq_gainer": results["kosdaq_gainer"],
            "kospi_loser": results["kospi_loser"],
            "kosdaq_loser": results["kosdaq_loser"],
            "kospi_volume_power": results["kospi_volume_power"],
            "kosdaq_volume_power": results["kosdaq_volume_power"],
            "kospi_near_new_high": results["kospi_near_new_high"],
            "kosdaq_near_new_high": results["kosdaq_near_new_high"],
        }

    async def _fetch_source_with_retry(
        self,
        *,
        key: str,
        rtype: RankingType,
        market: MarketType,
        direction: Literal["up", "down"],
        limit: int,
    ) -> list[dict[str, Any]]:
        """Fetch one ranking source; retry once on EGW throttle response.

        Returns an empty list and logs a warning when both attempts fail.
        """
        for attempt in range(2):
            try:
                return await self.get_ranking(
                    type=rtype, market=market, limit=limit, direction=direction
                )
            except RuntimeError as exc:
                err_text = str(exc)
                if self._is_rate_limit_error(err_text) and attempt == 0:
                    logger.warning(
                        "KIS ranking EGW throttle on %s (attempt 1); "
                        "retrying after %.1fs",
                        key,
                        self._retry_backoff_seconds,
                    )
                    await asyncio.sleep(self._retry_backoff_seconds)
                    continue
                logger.warning("KIS ranking source failed (%s): %s", key, exc)
                return []
            except Exception as exc:
                logger.warning("KIS ranking source failed (%s): %s", key, exc)
                return []
        # Should not reach here, but satisfy the type checker.
        return []  # pragma: no cover

    @staticmethod
    def _is_rate_limit_error(text: str) -> bool:
        markers = (
            "EGW00201",
            "초당 거래건수",
            "거래건수",
            "rate limit",
            "RATE",
        )
        return any(marker in text for marker in markers)

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
        return await self._get(
            self.endpoints.volume_path, headers=headers, params=params
        )

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

    async def _get_volume_power_rank(self, market: MarketType) -> dict[str, Any]:
        headers = await self._get_headers(self.endpoints.volume_power_tr_id_real)
        params = {
            "fid_trgt_exls_cls_code": "0",
            "fid_cond_mrkt_div_code": "J",
            "fid_cond_scr_div_code": "20168",
            "fid_input_iscd": _market_to_input_iscd(market),
            "fid_div_cls_code": "0",
            "fid_input_price_1": "0",
            "fid_input_price_2": "1000000",
            "fid_vol_cnt": "0",
            "fid_trgt_cls_code": "0",
        }
        return await self._get(
            self.endpoints.volume_power_path, headers=headers, params=params
        )

    async def _get_near_new_highlow_rank(self, market: MarketType) -> dict[str, Any]:
        headers = await self._get_headers(self.endpoints.near_new_highlow_tr_id_real)
        params = {
            "fid_aply_rang_vol": "100",
            "fid_cond_mrkt_div_code": "J",
            "fid_cond_scr_div_code": "20187",
            "fid_div_cls_code": "0",
            "fid_input_cnt_1": "0",
            "fid_input_cnt_2": "10",
            "fid_prc_cls_code": "0",
            "fid_input_iscd": _market_to_input_iscd(market),
            "fid_trgt_cls_code": "0",
            "fid_trgt_exls_cls_code": "0",
            "fid_aply_rang_prc_1": "0",
            "fid_aply_rang_prc_2": "1000000",
        }
        return await self._get(
            self.endpoints.near_new_highlow_path, headers=headers, params=params
        )

    async def _get_headers(self, tr_id: str) -> dict[str, str]:
        headers = await self.auth_manager.get_auth_headers_async()
        headers["tr_id"] = tr_id
        headers["custtype"] = "P"
        return headers

    async def _get(
        self, path: str, headers: dict[str, str], params: dict[str, Any]
    ) -> dict[str, Any]:
        await self._rate_limiter.acquire()
        url = f"{self.config.base_url}{path}"
        session = await self._get_session()
        timeout_seconds = getattr(self.config, "request_timeout_seconds", 30)
        request_timeout = aiohttp.ClientTimeout(total=float(timeout_seconds))

        async with session.get(
            url, headers=headers, params=params, timeout=request_timeout
        ) as response:
            text = await response.text()
            if response.status != 200:
                if self._is_rate_limit_error(text):
                    self._rate_limiter.penalty()
                raise RuntimeError(f"KIS ranking HTTP {response.status}: {text[:2000]}")
            try:
                data = await response.json()
            except Exception as e:
                raise RuntimeError(
                    f"KIS ranking JSON decode failed: {e}: {text[:2000]}"
                ) from e

        if data.get("rt_cd") != "0":
            msg = data.get("msg1", "Unknown error")
            if self._is_rate_limit_error(str(msg)):
                self._rate_limiter.penalty()
            raise RuntimeError(f"KIS ranking API error: {msg}")
        self._rate_limiter.reset_backoff()
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
            "price": parse_float(row.get("stck_prpr")),
            "change_pct": parse_float(row.get("prdy_ctrt")),
            "volume": parse_int(row.get("acml_vol")),
            "trade_value": parse_int(row.get("acml_tr_pbmn")),
            "rank": parse_int(row.get("data_rank")),
            "raw": row,
        }

    @staticmethod
    def _normalize_fluctuation_row(row: dict[str, Any]) -> dict[str, Any]:
        code = row.get("stck_shrn_iscd") or row.get("mksc_shrn_iscd") or ""
        name = row.get("hts_kor_isnm") or ""
        return {
            "code": str(code).strip(),
            "name": str(name).strip(),
            "price": parse_float(row.get("stck_prpr")),
            "change_pct": parse_float(row.get("prdy_ctrt") or row.get("prd_rsfl_rate")),
            "volume": parse_int(row.get("acml_vol") or row.get("cntg_vol")),
            "trade_value": parse_int(row.get("acml_tr_pbmn") or row.get("tr_pbmn")),
            "rank": parse_int(row.get("data_rank")),
            "raw": row,
        }

    @staticmethod
    def _normalize_volume_power_row(row: dict[str, Any]) -> dict[str, Any]:
        code = row.get("stck_shrn_iscd") or row.get("mksc_shrn_iscd") or ""
        name = row.get("hts_kor_isnm") or ""
        return {
            "code": str(code).strip(),
            "name": str(name).strip(),
            "price": parse_float(row.get("stck_prpr")),
            "change_pct": parse_float(row.get("prdy_ctrt")),
            "volume": parse_int(row.get("acml_vol")),
            "trade_value": parse_int(row.get("acml_tr_pbmn") or row.get("tr_pbmn")),
            "rank": parse_int(row.get("data_rank")),
            "volume_power": parse_float(row.get("tday_rltv")),
            "sell_volume": parse_int(row.get("seln_cnqn_smtn")),
            "buy_volume": parse_int(row.get("shnu_cnqn_smtn")),
            "raw": row,
        }

    @staticmethod
    def _normalize_near_new_highlow_row(row: dict[str, Any]) -> dict[str, Any]:
        code = row.get("mksc_shrn_iscd") or row.get("stck_shrn_iscd") or ""
        name = row.get("hts_kor_isnm") or ""
        return {
            "code": str(code).strip(),
            "name": str(name).strip(),
            "price": parse_float(row.get("stck_prpr")),
            "change_pct": parse_float(row.get("prdy_ctrt")),
            "volume": parse_int(row.get("acml_vol")),
            "trade_value": parse_int(row.get("acml_tr_pbmn") or row.get("tr_pbmn")),
            "rank": parse_int(row.get("data_rank")),
            "near_high_rate": parse_float(row.get("hprc_near_rate")),
            "new_high": parse_float(row.get("new_hgpr")),
            "near_low_rate": parse_float(row.get("lwpr_near_rate")),
            "new_low": parse_float(row.get("new_lwpr")),
            "bid_price": parse_float(row.get("bidp")),
            "ask_price": parse_float(row.get("askp")),
            "bid_quantity": parse_int(row.get("bidp_rsqn1")),
            "ask_quantity": parse_int(row.get("askp_rsqn1")),
            "raw": row,
        }
