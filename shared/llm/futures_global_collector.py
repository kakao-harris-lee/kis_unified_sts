"""Global market data collector for futures analysis."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta

from .collector_base import DataCollector
from .config import LLMConfig
from .data_classes import GlobalMarketData
from .errors import DataUnavailableError

logger = logging.getLogger("shared.llm.collectors")

try:
    import FinanceDataReader as fdr

    FDR_AVAILABLE = True
except ImportError:
    FDR_AVAILABLE = False


class FuturesGlobalCollector(DataCollector):
    """글로벌 시장 데이터 수집"""

    def __init__(self, config: LLMConfig | None = None):
        super().__init__()
        self.config = config or LLMConfig.from_env()

    def collect(self) -> GlobalMarketData:
        """글로벌 시장 데이터 수집 (가능하면 실제 데이터 사용)"""
        snapshot = self._load_snapshot()
        if snapshot:
            return snapshot

        if FDR_AVAILABLE:
            try:
                data = self._collect_from_fdr()
                if data:
                    return data
            except Exception as e:
                logger.debug(f"FDR global market collection failed: {e}")
            raise DataUnavailableError("global_market_data", "fdr_empty")

        raise DataUnavailableError("global_market_data", "fdr_not_available")

    def _load_snapshot(self) -> GlobalMarketData | None:
        """외부 스냅샷(JSON)에서 글로벌 데이터 로드 (선택)"""
        snapshot_json = os.environ.get("LLM_GLOBAL_SNAPSHOT_JSON", "").strip()
        snapshot_path = os.environ.get("LLM_GLOBAL_SNAPSHOT_PATH", "").strip()

        payload = None
        if snapshot_json:
            try:
                payload = json.loads(snapshot_json)
            except Exception as e:
                logger.debug(f"Invalid LLM_GLOBAL_SNAPSHOT_JSON: {e}")
                payload = None
        elif snapshot_path:
            try:
                with open(snapshot_path, encoding="utf-8") as f:
                    payload = json.load(f)
            except Exception as e:
                logger.debug(f"Failed to load snapshot file: {e}")
                payload = None

        if not isinstance(payload, dict):
            return None

        allowed = set(GlobalMarketData.__dataclass_fields__.keys())
        data = {k: payload.get(k) for k in allowed if k in payload}
        if not data:
            return None

        result = GlobalMarketData(**data)
        if not result.global_score:
            result.global_score = self._compute_global_score(result)
        return result

    def _collect_from_fdr(self) -> GlobalMarketData | None:
        """FinanceDataReader 기반 글로벌 지표 수집 (Investing.com/TradingView 연계)"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        tickers = {
            "sp500": os.environ.get("LLM_TICKER_SP500", "US500"),
            "nasdaq": os.environ.get("LLM_TICKER_NASDAQ", "IXIC"),
            "nikkei": os.environ.get("LLM_TICKER_NIKKEI", "N225"),
            "shanghai": os.environ.get("LLM_TICKER_SHANGHAI", "000001.SS"),
            "vix": os.environ.get("LLM_TICKER_VIX", "VIX"),
            "wti": os.environ.get("LLM_TICKER_WTI", "CL=F"),
            "gold": os.environ.get("LLM_TICKER_GOLD", "GC=F"),
            "dxy": os.environ.get("LLM_TICKER_DXY", "DXY"),
            "usd_krw": os.environ.get("LLM_TICKER_USDKRW", "USDKRW"),
        }

        def _fetch_last(ticker: str) -> tuple[float, float] | None:
            if not ticker:
                return None
            df = fdr.DataReader(ticker, start_date, end_date)
            if df is None or len(df) < 2:
                return None
            col = "Close" if "Close" in df.columns else "close"
            last = float(df[col].iloc[-1])
            prev = float(df[col].iloc[-2])
            change_pct = (last / prev - 1) * 100 if prev else 0.0
            return last, change_pct

        values: dict[str, tuple[float, float]] = {}
        for key, ticker in tickers.items():
            try:
                res = _fetch_last(ticker)
                if res:
                    values[key] = res
            except Exception:
                continue

        if not values:
            return None

        result = GlobalMarketData(
            sp500=round(values.get("sp500", (0.0, 0.0))[0], 2),
            sp500_change_pct=round(values.get("sp500", (0.0, 0.0))[1], 2),
            nasdaq=round(values.get("nasdaq", (0.0, 0.0))[0], 2),
            nasdaq_change_pct=round(values.get("nasdaq", (0.0, 0.0))[1], 2),
            nikkei=round(values.get("nikkei", (0.0, 0.0))[0], 2),
            nikkei_change_pct=round(values.get("nikkei", (0.0, 0.0))[1], 2),
            shanghai=round(values.get("shanghai", (0.0, 0.0))[0], 2),
            shanghai_change_pct=round(values.get("shanghai", (0.0, 0.0))[1], 2),
            vix=round(values.get("vix", (0.0, 0.0))[0], 2),
            wti=round(values.get("wti", (0.0, 0.0))[0], 2),
            gold=round(values.get("gold", (0.0, 0.0))[0], 2),
            dxy=round(values.get("dxy", (0.0, 0.0))[0], 2),
            usd_krw=round(values.get("usd_krw", (0.0, 0.0))[0], 2),
        )
        result.global_score = self._compute_global_score(result)
        return result

    @staticmethod
    def _compute_global_score(data: GlobalMarketData) -> float:
        return round(
            data.sp500_change_pct * 15
            + data.nasdaq_change_pct * 10
            + data.nikkei_change_pct * 5
            - (data.vix - 15) * 2,
            1,
        )
