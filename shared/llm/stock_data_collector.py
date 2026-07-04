"""Stock price and history collector."""

from __future__ import annotations

import contextlib
import logging
import os
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd

from shared.calendar import MarketCalendar
from shared.config.secrets import SecretsManager
from shared.kis.auth import KISAuthConfig, KISAuthManager

from .collector_base import DataCollector
from .config import LLMConfig
from .krx_api_client import KRXOpenAPIClient

logger = logging.getLogger("shared.llm.collectors")


class StockDataCollector(DataCollector):
    """주식 시세 데이터 수집 (KRX Open API 기반)"""

    SUPPORTED_MARKETS = ("KOSPI", "KOSDAQ")

    def __init__(self, config: LLMConfig | None = None):
        super().__init__()
        self._config = config or LLMConfig.from_env()
        self._krx_client = KRXOpenAPIClient(self._config)
        self._calendar = MarketCalendar()
        self._kis_auth_manager: KISAuthManager | None = None
        self._kis_auth_initialized: bool = False
        # 종목명 캐시 (daily 데이터에서 수집)
        self._name_cache: dict[str, str] = {}
        self._name_cache_warmed: bool = False
        self._code_market_cache: dict[str, str] = {}

    def _get_last_trading_date(self) -> str:
        """가장 최근 거래일 반환 (KRX API 데이터 게시 시간 고려)."""
        return self._krx_client._get_last_trading_date()

    def collect(self, market: str = "KOSPI") -> pd.DataFrame | None:
        """전체 시장 데이터 수집 (단일 시장)

        KRX Open API 오류에 대비해 최대 3영업일까지 fallback 시도.
        """
        try:
            self._validate_market(market)

            target_date = self._get_last_trading_date()
            logger.info(
                f"Collecting market data for {target_date} ({market}) via KRX Open API"
            )

            # 최대 3일 전까지 fallback 시도
            df = pd.DataFrame()
            attempt_date = target_date
            for attempt in range(3):
                try:
                    df = self._krx_client.get_stock_daily_as_dataframe(
                        market, attempt_date
                    )
                except Exception as e:
                    logger.warning(
                        f"KRX API fetch failed for {attempt_date} ({market}): {e}"
                    )
                    df = pd.DataFrame()
                if len(df) > 0:
                    break
                prev = self._previous_date(attempt_date)
                logger.info(
                    f"No data for {attempt_date}, trying {prev} (attempt {attempt + 2}/3)"
                )
                attempt_date = prev

            if len(df) > 0:
                # 종목명 캐시 업데이트
                if "종목명" in df.columns:
                    for code, row in df.iterrows():
                        self._name_cache[str(code)] = str(row["종목명"])
                self._attach_market_column(df, market)
                logger.info(
                    f"Collected {len(df)} stocks for {market} (date={attempt_date})"
                )
            else:
                logger.error(
                    f"Market data collection exhausted for {market} (tried 3 dates)"
                )

            return df
        except Exception as e:
            logger.error(f"Failed to collect market data: {e}")
            return None

    def _validate_market(self, market: str) -> None:
        if market not in self.SUPPORTED_MARKETS:
            raise ValueError(
                f"Unsupported market: {market} (supported={self.SUPPORTED_MARKETS})"
            )

    def _previous_date(self, target_date: str) -> str:
        parsed = datetime.strptime(target_date, "%Y%m%d").date()
        return self._calendar.get_previous_market_day(parsed).strftime("%Y%m%d")

    @staticmethod
    def _attach_market_column(df: pd.DataFrame, market: str) -> None:
        df["시장"] = market

    def get_stock_history(self, code: str, days: int = 60) -> pd.DataFrame | None:
        """개별 종목 과거 일봉 수집 (KIS 우선, KRX Open API 폴백)."""
        code = str(code).strip()
        if not code:
            return None
        days = max(1, int(days))

        kis_df = self._fetch_stock_history_via_kis(code, days)
        if kis_df is not None and not kis_df.empty:
            return kis_df.tail(days)

        krx_df = self._fetch_stock_history_via_krx(code, days)
        if krx_df is not None and not krx_df.empty:
            return krx_df.tail(days)

        logger.debug("Failed to get history for %s (days=%s)", code, days)
        return None

    def _get_kis_auth_manager(self) -> KISAuthManager | None:
        if self._kis_auth_initialized:
            return self._kis_auth_manager
        self._kis_auth_initialized = True

        app_key = SecretsManager.kis_app_key("stock") or ""
        app_secret = SecretsManager.kis_app_secret("stock") or ""
        if not app_key or not app_secret:
            logger.debug(
                "KIS stock credentials not configured; history uses KRX fallback only"
            )
            return None

        is_real = str(SecretsManager.kis_market("stock")).lower() != "mock"
        config = KISAuthConfig(
            app_key=app_key,
            app_secret=app_secret,
            is_real=is_real,
        )
        self._kis_auth_manager = KISAuthManager.get_instance(config)
        return self._kis_auth_manager

    def _fetch_stock_history_via_kis(self, code: str, days: int) -> pd.DataFrame | None:
        auth = self._get_kis_auth_manager()
        if auth is None:
            return None

        start_date = date.today() - timedelta(days=max(days * 3, 90))
        end_date = date.today()
        url = (
            f"{auth.config.base_url}"
            "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
        )
        headers = auth.get_auth_headers()
        headers["tr_id"] = "FHKST03010100"
        headers["custtype"] = "P"
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": code,
            "FID_INPUT_DATE_1": start_date.strftime("%Y%m%d"),
            "FID_INPUT_DATE_2": end_date.strftime("%Y%m%d"),
            "FID_PERIOD_DIV_CODE": "D",
            "FID_ORG_ADJ_PRC": os.getenv("KIS_DAILY_ORG_ADJ_PRC", "0"),
        }

        try:
            response = self.session.get(url, headers=headers, params=params, timeout=10)
            if response.status_code != 200:
                logger.debug(
                    "KIS history failed for %s: http %s",
                    code,
                    response.status_code,
                )
                return None

            payload = response.json()
            if payload.get("rt_cd") not in ("0", None, ""):
                logger.debug(
                    "KIS history rt_cd failure for %s: %s (%s)",
                    code,
                    payload.get("rt_cd"),
                    payload.get("msg1", ""),
                )
                return None

            output = payload.get("output2", []) or payload.get("output1", []) or []
            rows: list[dict[str, Any]] = []

            def _to_float(value: Any) -> float:
                try:
                    return float(str(value).replace(",", "").strip() or 0)
                except Exception:
                    return 0.0

            def _to_int(value: Any) -> int:
                return int(_to_float(value))

            for item in output:
                if not isinstance(item, dict):
                    continue
                date_str = str(item.get("stck_bsop_date", "")).strip()
                if not date_str:
                    continue
                try:
                    dt = datetime.strptime(date_str, "%Y%m%d")
                except ValueError:
                    continue

                close_price = _to_float(item.get("stck_clpr", item.get("stck_prpr", 0)))
                if close_price <= 0:
                    continue

                rows.append(
                    {
                        "date": dt,
                        "시가": _to_float(item.get("stck_oprc", 0)),
                        "고가": _to_float(item.get("stck_hgpr", 0)),
                        "저가": _to_float(item.get("stck_lwpr", 0)),
                        "종가": close_price,
                        "거래량": _to_int(item.get("acml_vol", 0)),
                        "거래대금": _to_int(item.get("acml_tr_pbmn", 0)),
                        "등락률": _to_float(item.get("prdy_ctrt", 0)),
                    }
                )

            if not rows:
                return None

            history = (
                pd.DataFrame(rows).drop_duplicates(subset=["date"]).sort_values("date")
            )
            history = history.set_index("date")
            return history
        except Exception as e:
            logger.debug("KIS history fetch failed for %s: %s", code, e)
            return None

    def _resolve_market_for_code(self, code: str) -> str | None:
        cached = self._code_market_cache.get(code)
        if cached:
            return cached

        base_date = self._krx_client._get_last_trading_date()
        attempt_date = base_date
        for _ in range(3):
            for market in self.SUPPORTED_MARKETS:
                try:
                    df = self._krx_client.get_stock_daily_as_dataframe(
                        market, attempt_date
                    )
                except Exception:
                    df = pd.DataFrame()
                if df.empty:
                    continue
                if str(code) in {str(idx) for idx in df.index}:
                    self._code_market_cache[code] = market
                    return market
            attempt_date = self._previous_date(attempt_date)
        return None

    def _fetch_stock_history_via_krx(self, code: str, days: int) -> pd.DataFrame | None:
        market = self._resolve_market_for_code(code)
        if market is None:
            return None

        try:
            cursor = datetime.strptime(
                self._krx_client._get_last_trading_date(), "%Y%m%d"
            ).date()
        except Exception:
            cursor = date.today()

        rows: list[dict[str, Any]] = []
        max_attempts = max(days * 2, days + 10)
        attempts = 0
        while len(rows) < days and attempts < max_attempts:
            date_str = cursor.strftime("%Y%m%d")
            attempts += 1
            try:
                df = self._krx_client.get_stock_daily_as_dataframe(market, date_str)
            except Exception:
                df = pd.DataFrame()

            if not df.empty and "거래량" in df.columns:
                market_rows = {str(idx): row for idx, row in df.iterrows()}
                row = market_rows.get(code)
                if row is not None:
                    with contextlib.suppress(Exception):
                        rows.append(
                            {
                                "date": pd.to_datetime(date_str, format="%Y%m%d"),
                                "시가": float(row.get("시가", 0)),
                                "고가": float(row.get("고가", 0)),
                                "저가": float(row.get("저가", 0)),
                                "종가": float(row.get("종가", 0)),
                                "거래량": int(float(row.get("거래량", 0))),
                                "거래대금": int(float(row.get("거래대금", 0))),
                                "등락률": float(row.get("등락률", 0)),
                            }
                        )

            cursor = self._calendar.get_previous_market_day(cursor)

        if not rows:
            return None

        history = (
            pd.DataFrame(rows).drop_duplicates(subset=["date"]).sort_values("date")
        )
        history = history.set_index("date")
        return history

    def get_stock_name(self, code: str) -> str:
        """종목명 조회 (daily 데이터 캐시 우선, KRX Open API fallback)."""
        if code in self._name_cache:
            return self._name_cache[code]
        self._warm_name_cache_from_krx()
        if code in self._name_cache:
            return self._name_cache[code]
        return code

    def _warm_name_cache_from_krx(self) -> None:
        if self._name_cache_warmed:
            return
        self._name_cache_warmed = True

        try:
            base_date = self._krx_client._get_last_trading_date()
            for market in self.SUPPORTED_MARKETS:
                df = self._krx_client.get_stock_daily_as_dataframe(market, base_date)
                if df.empty or "종목명" not in df.columns:
                    continue
                for stock_code, row in df.iterrows():
                    name = str(row.get("종목명", "")).strip()
                    if name:
                        self._name_cache[str(stock_code)] = name
        except Exception as e:
            logger.debug(f"KRX name cache warmup failed: {e}")
