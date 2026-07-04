"""Unified stock/futures trading analyzer facade."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from shared.kis.auth import KISAuthConfig
from shared.kis.client import KISClient

from . import llm_scoring as _llm_scoring
from . import reporting as _reporting
from . import stock_analysis as _stock_analysis
from . import stock_screening as _stock_screening
from .analyzers import (
    FuturesTechnicalAnalyzer,
    StockBacktester,
    StockNewsAnalyzer,
    StockTechnicalAnalyzer,
)
from .collectors import (
    DARTDataCollector,
    FuturesEventCollector,
    FuturesFlowCollector,
    FuturesGlobalCollector,
    KOFIADataCollector,
    KRXDataCollector,
    KSDDataCollector,
    MKStockNewsCollector,
    SEIBRODataCollector,
    StockDataCollector,
)
from .config import LLMConfig
from .data_classes import (
    BacktestResult,
    FuturesTradingPlan,
    StockDetailedBriefing,
    StockInfo,
    StockTradingPlan,
    TechnicalAnalysis,
)
from .identifiers import DARTCorpCodeMapper
from .prompt_cache import LLMPromptCache, PromptCacheConfig
from .unified_trading_futures import FuturesAnalysisMixin

logger = logging.getLogger("shared.llm.llm_analyzer")


class UnifiedTradingAnalyzer(FuturesAnalysisMixin):
    """통합 트레이딩 분석기 (주식 + 선물)

    데이터 소스:
    - KRX Open API + KIS API: 주식 시세/히스토리
    - KRX (data.krx.co.kr): 거래소 공식 데이터, 투자자별 동향
    - SEIBRO (seibro.or.kr): 증권정보, 배당, 주주현황
    - DART (dart.fss.or.kr): 공시정보, 재무제표
    - KSD (ksd.or.kr): 공매도, 대차잔고, 대량보유
    - KOFIA (freesis.kofia.or.kr): 펀드, 채권, 투자자동향
    - MK Stock (stock.mk.co.kr): 증권뉴스, 테마, 분석
    """

    def __init__(
        self,
        notifier=None,
        dart_api_key: str | None = None,
        config: LLMConfig | None = None,
        config_path: str | Path | None = None,
    ):
        """
        Args:
            notifier: TelegramNotifier 인스턴스
            dart_api_key: DART API 키 (없으면 환경변수 DART_API_KEY 사용)
            config: LLMConfig (None이면 기본 설정 로드)
            config_path: LLM 설정 YAML 경로 (config가 None일 때만 사용)
        """
        self.notifier = notifier
        self.config = config or LLMConfig.load(config_path)

        # Stock analyzers
        self.stock_collector = StockDataCollector(self.config)
        self.stock_tech_analyzer = StockTechnicalAnalyzer()
        self.stock_backtester = StockBacktester()
        self.stock_news_analyzer = StockNewsAnalyzer()

        # Korean Financial Data Source Collectors
        self.krx_collector = KRXDataCollector(self.config)
        self.seibro_collector = SEIBRODataCollector()
        self.dart_collector = DARTDataCollector(api_key=dart_api_key)
        self.ksd_collector = KSDDataCollector()
        self.kofia_collector = KOFIADataCollector()
        self.mk_news_collector = MKStockNewsCollector()
        self.kis_client: KISClient | None = None
        self._target_price_cache: dict[str, dict[str, Any]] = {}
        if self.config.stock_enable_kis_target_price:
            kis_is_real = os.environ.get("KIS_IS_REAL", "true").lower() == "true"
            app_key = os.environ.get("KIS_STOCK_APP_KEY") or os.environ.get(
                "KIS_APP_KEY", ""
            )
            app_secret = os.environ.get("KIS_STOCK_APP_SECRET") or os.environ.get(
                "KIS_APP_SECRET", ""
            )
            kis_cfg = KISAuthConfig(
                app_key=app_key,
                app_secret=app_secret,
                is_real=kis_is_real,
            )
            if kis_cfg.is_real and kis_cfg.app_key and kis_cfg.app_secret:
                self.kis_client = KISClient(kis_cfg)
            else:
                logger.info(
                    "KIS target-price enrichment disabled (missing credentials or mock mode)"
                )
        self._dart_corp_mapper = DARTCorpCodeMapper(
            api_key=getattr(self.dart_collector, "api_key", "") or "",
            cache_path=Path(self.config.output_dir) / "dart_corp_codes.json",
            auto_refresh=bool(getattr(self.dart_collector, "api_key", "")),
        )

        # LLM scoring
        self._scoring_prompt_cache = LLMPromptCache(
            PromptCacheConfig(
                enabled=self.config.llm_prompt_cache_enabled,
                ttl_seconds=self.config.llm_prompt_cache_ttl_seconds,
                key_prefix=f"{self.config.llm_prompt_cache_prefix}:scoring",
            )
        )
        self._scoring_client = None

        # Futures analyzers
        self.futures_global_collector = FuturesGlobalCollector(self.config)
        self.futures_flow_collector = FuturesFlowCollector(self.config)
        self.futures_event_collector = FuturesEventCollector()
        self.futures_tech_analyzer = FuturesTechnicalAnalyzer(self.config)

        # Output
        self.date = datetime.now().strftime("%Y%m%d")
        self.datetime_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        os.makedirs(self.config.output_dir, exist_ok=True)

    def _is_preferred_share(self, name: str) -> bool:
        return _stock_screening.is_preferred_share(name)

    def _name_exclusion_reasons(self, name: str) -> list[str]:
        return _stock_screening.name_exclusion_reasons(name, self.config)

    @staticmethod
    def _find_keyword_hits(texts: list[str], keywords: list[str]) -> list[str]:
        return _stock_screening.find_keyword_hits(texts, keywords)

    @staticmethod
    def _calc_max_drawdown(close: pd.Series) -> float:
        return _stock_screening.calc_max_drawdown(close)

    @staticmethod
    def _calc_atr_pct(df: pd.DataFrame, period: int = 14) -> float:
        return _stock_screening.calc_atr_pct(df, period)

    @staticmethod
    def _calc_consecutive_up(returns: pd.Series) -> int:
        return _stock_screening.calc_consecutive_up(returns)

    @staticmethod
    def _calc_momentum_metrics(close: pd.Series, lookback: int) -> dict[str, float]:
        return _stock_screening.calc_momentum_metrics(close, lookback)

    @staticmethod
    def _score_target_price_signal(screening: dict[str, Any]) -> float:
        """Score analyst target-price signal from KIS invest-opinion."""
        return _stock_screening.score_target_price_signal(screening)

    async def _collect_target_price_signal(
        self,
        code: str,
        current_price: float,
    ) -> dict[str, Any]:
        return await _llm_scoring.collect_target_price_signal(self, code, current_price)

    def _collect_market_frames(self) -> tuple[list[pd.DataFrame], list[str]]:
        market_kospi = self.stock_collector.collect("KOSPI")
        market_kosdaq = self.stock_collector.collect("KOSDAQ")
        frames: list[pd.DataFrame] = []
        markets: list[str] = []
        if market_kospi is not None and len(market_kospi) > 0:
            frames.append(market_kospi)
            markets.append("KOSPI")
        if market_kosdaq is not None and len(market_kosdaq) > 0:
            frames.append(market_kosdaq)
            markets.append("KOSDAQ")
        return frames, markets

    def _merge_market_frames(self, frames: list[pd.DataFrame]) -> pd.DataFrame | None:
        if not frames:
            return None
        if len(frames) == 1:
            return frames[0]
        import pandas as pd

        return pd.concat(frames, axis=0)

    def _prepare_market_df(
        self,
        market_df: pd.DataFrame,
    ) -> tuple[pd.DataFrame | None, bool, dict[str, Any] | None]:
        if market_df is None or len(market_df) == 0:
            logger.error("Failed to collect market data")
            return None, False, None

        required_cols = ["종가", "시가", "거래량", "시가총액"]
        missing_cols = [c for c in required_cols if c not in market_df.columns]
        if missing_cols:
            logger.error(f"Market data missing columns: {missing_cols}")
            error_meta = {
                "_excluded": {"_error": [f"missing_columns:{','.join(missing_cols)}"]}
            }
            return None, False, error_meta

        trade_value_fallback = False
        if "거래대금" not in market_df.columns:
            trade_value_fallback = True
            market_df = market_df.copy()
            market_df["거래대금"] = market_df["종가"] * market_df["거래량"]

        market_df["거래대금"] = pd.to_numeric(market_df["거래대금"], errors="coerce")
        market_df["시가총액"] = pd.to_numeric(market_df["시가총액"], errors="coerce")
        market_df["거래량"] = pd.to_numeric(market_df["거래량"], errors="coerce")
        market_df = market_df.dropna(
            subset=["거래대금", "시가총액", "거래량", "종가", "시가"]
        )
        return market_df, trade_value_fallback, None

    def _filter_market_df(self, market_df: pd.DataFrame) -> pd.DataFrame:
        filtered = market_df[
            (market_df["종가"] >= self.config.stock_min_price)
            & (market_df["종가"] <= self.config.stock_max_price)
            & (market_df["시가총액"] >= self.config.stock_min_market_cap)
            & (market_df["시가총액"] <= self.config.stock_max_market_cap)
            & (market_df["거래대금"] >= self.config.stock_min_trade_value)
        ].copy()

        filtered["거래대금비율"] = filtered["거래대금"] / filtered["시가총액"].replace(
            0, np.nan
        )
        filtered = filtered[filtered["거래대금비율"] >= self.config.stock_min_turnover]
        filtered["등락률"] = (
            (filtered["종가"] - filtered["시가"]) / filtered["시가"] * 100
        )
        return filtered

    def _build_screened_stocks(
        self,
        top_volume: pd.DataFrame,
    ) -> tuple[list[StockInfo], dict[str, list[str]]]:
        stocks: list[StockInfo] = []
        excluded: dict[str, list[str]] = {}
        for code in top_volume.index:
            row = top_volume.loc[code]
            name = self.stock_collector.get_stock_name(code)
            name_exclusions = self._name_exclusion_reasons(name)
            if name_exclusions:
                excluded[code] = name_exclusions
                continue
            stocks.append(
                StockInfo(
                    code=code,
                    name=name,
                    price=row["종가"],
                    change_pct=round(row["등락률"], 2),
                    volume=int(row["거래량"]),
                    volume_ratio=1.0,
                    market_cap=row["시가총액"],
                    trade_value=float(row.get("거래대금", 0.0)),
                    turnover=float(row.get("거래대금비율", 0.0)),
                )
            )
        return stocks, excluded

    def _collect_stock_history(
        self,
        stock: StockInfo,
        history_days: int,
    ) -> tuple[pd.DataFrame | None, list[str] | None]:
        df = self.stock_collector.get_stock_history(stock.code, history_days)
        if df is None or len(df) < int(self.config.stock_min_history_days):
            reason = [f"history_insufficient:{0 if df is None else len(df)}"]
            return None, reason

        required_hist_cols = ["종가", "고가", "저가", "거래량"]
        missing_hist_cols = [c for c in required_hist_cols if c not in df.columns]
        if missing_hist_cols:
            return None, [f"history_missing:{','.join(missing_hist_cols)}"]

        if "거래대금" not in df.columns:
            df = df.copy()
            df["거래대금"] = df["종가"] * df["거래량"]
        return df, None

    def _compute_liquidity_metrics(
        self,
        df: pd.DataFrame,
        stock: StockInfo,
    ) -> tuple[dict[str, Any] | None, list[str] | None]:
        lookback = max(1, int(self.config.stock_volume_lookback_days))
        vol_window = df["거래량"].tail(lookback + 1)
        avg_volume = (
            float(vol_window.iloc[:-1].mean())
            if len(vol_window) > 1
            else float(vol_window.mean())
        )
        stock.volume_ratio = round(
            (stock.volume / avg_volume) if avg_volume > 0 else 1.0, 2
        )
        if avg_volume < float(self.config.stock_min_avg_volume):
            return None, [f"min_avg_volume:{int(avg_volume)}"]

        trade_window = df["거래대금"].tail(lookback + 1)
        avg_trade_value = (
            float(trade_window.iloc[:-1].mean())
            if len(trade_window) > 1
            else float(trade_window.mean())
        )
        if avg_trade_value < float(self.config.stock_min_trade_value):
            return None, [f"min_avg_trade_value:{int(avg_trade_value)}"]

        return {
            "avg_volume": avg_volume,
            "avg_trade_value": avg_trade_value,
        }, None

    def _compute_risk_metrics(self, df: pd.DataFrame) -> dict[str, Any]:
        close = df["종가"].astype(float)
        returns = close.pct_change()
        momentum = self._calc_momentum_metrics(
            close, int(self.config.stock_momentum_lookback_days)
        )
        consecutive_up = self._calc_consecutive_up(returns)
        atr_pct = self._calc_atr_pct(df)
        max_dd = self._calc_max_drawdown(close)
        volatility = float(returns.std() * np.sqrt(252)) if returns is not None else 0.0
        return {
            "momentum": momentum,
            "consecutive_up": consecutive_up,
            "atr_pct": atr_pct,
            "max_drawdown_pct": max_dd,
            "volatility": volatility,
        }

    def _collect_external_sources(
        self,
        stock: StockInfo,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
        mk_news: dict[str, Any] = {}
        try:
            mk_news = self.mk_news_collector.collect(stock.code)
            all_news = mk_news.get("market_news", []) + mk_news.get("stock_news", [])
            mk_news["sentiment"] = self.mk_news_collector.analyze_sentiment(
                all_news
            ).value
        except Exception as e:
            logger.debug(f"MK news failed for {stock.code}: {e}")

        dart_data: dict[str, Any] = {}
        try:
            corp_code = self._dart_corp_mapper.get_corp_code(stock.code)
            dart_data = (
                self.dart_collector.collect(corp_code)
                if corp_code
                else {"error": "corp_code_not_found"}
            )
        except Exception as e:
            logger.debug(f"DART data failed for {stock.code}: {e}")

        ksd_data: dict[str, Any] = {}
        try:
            ksd_data = self.ksd_collector.collect(stock.code)
        except Exception as e:
            logger.debug(f"KSD data failed for {stock.code}: {e}")

        krx_stock_info: dict[str, Any] = {}
        try:
            krx_stock_info = self.krx_collector.get_stock_info(stock.code) or {}
        except Exception as e:
            logger.debug(f"KRX stock info failed for {stock.code}: {e}")

        return mk_news, dart_data, ksd_data, krx_stock_info

    def _build_screening_metrics(
        self,
        stock: StockInfo,
        liquidity: dict[str, Any],
        risk: dict[str, Any],
        risk_hits: list[str],
    ) -> dict[str, Any]:
        return {
            "avg_volume": round(float(liquidity.get("avg_volume", 0.0)), 2),
            "avg_trade_value": round(float(liquidity.get("avg_trade_value", 0.0)), 2),
            "volume_ratio": stock.volume_ratio,
            "trade_value": round(stock.trade_value, 2),
            "turnover": round(stock.turnover, 6),
            "momentum": risk.get("momentum", {}),
            "consecutive_up": int(risk.get("consecutive_up", 0)),
            "atr_pct": round(float(risk.get("atr_pct", 0.0)), 4),
            "max_drawdown_pct": round(float(risk.get("max_drawdown_pct", 0.0)), 4),
            "volatility": round(float(risk.get("volatility", 0.0)), 4),
            "risk_keywords": risk_hits,
        }

    def _score_stock_candidate(
        self,
        stock: StockInfo,
        tech: TechnicalAnalysis,
        best: BacktestResult | None,
        news: dict[str, Any],
        screening: dict[str, Any],
    ) -> tuple[float, dict[str, float]]:
        return _stock_screening.score_stock_candidate(
            stock, tech, best, news, screening, self.config
        )

    async def _llm_score_candidate(
        self,
        stock: StockInfo,
        tech: TechnicalAnalysis,
        best: BacktestResult | None,
        news: dict[str, Any],
        screening: dict[str, Any],
    ) -> dict[str, Any]:
        """LLM 기반 종목 확신도 스코어링."""
        return await _llm_scoring.llm_score_candidate(
            self, stock, tech, best, news, screening
        )

    def collect_all_data_sources(self, code: str = None) -> dict:
        """모든 데이터 소스에서 데이터 수집"""
        logger.info(f"Collecting data from all sources{f' for {code}' if code else ''}")

        data = {"collected_at": datetime.now().isoformat(), "code": code, "sources": {}}

        # KRX 데이터
        try:
            krx_data = self.krx_collector.collect()
            if code:
                krx_data["stock_info"] = self.krx_collector.get_stock_info(code)
            data["sources"]["krx"] = krx_data
            logger.debug("KRX data collected")
        except Exception as e:
            logger.warning(f"KRX data collection failed: {e}")
            data["sources"]["krx"] = {"error": str(e)}

        # SEIBRO 데이터
        try:
            data["sources"]["seibro"] = self.seibro_collector.collect(code)
            logger.debug("SEIBRO data collected")
        except Exception as e:
            logger.warning(f"SEIBRO data collection failed: {e}")
            data["sources"]["seibro"] = {"error": str(e)}

        # DART 공시 데이터
        try:
            corp_code = self._dart_corp_mapper.get_corp_code(code) if code else None
            data["sources"]["dart"] = (
                self.dart_collector.collect(corp_code)
                if corp_code
                else {"error": "corp_code_not_found"}
            )
            logger.debug("DART data collected")
        except Exception as e:
            logger.warning(f"DART data collection failed: {e}")
            data["sources"]["dart"] = {"error": str(e)}

        # KSD 데이터
        try:
            data["sources"]["ksd"] = self.ksd_collector.collect(code)
            logger.debug("KSD data collected")
        except Exception as e:
            logger.warning(f"KSD data collection failed: {e}")
            data["sources"]["ksd"] = {"error": str(e)}

        # KOFIA 데이터
        try:
            data["sources"]["kofia"] = self.kofia_collector.collect()
            logger.debug("KOFIA data collected")
        except Exception as e:
            logger.warning(f"KOFIA data collection failed: {e}")
            data["sources"]["kofia"] = {"error": str(e)}

        # MK Stock 뉴스
        try:
            mk_data = self.mk_news_collector.collect(code)
            all_news = mk_data.get("market_news", []) + mk_data.get("stock_news", [])
            mk_data["sentiment"] = self.mk_news_collector.analyze_sentiment(
                all_news
            ).value
            data["sources"]["mk_news"] = mk_data
            logger.debug("MK News data collected")
        except Exception as e:
            logger.warning(f"MK News data collection failed: {e}")
            data["sources"]["mk_news"] = {"error": str(e)}

        return data

    async def run_full_analysis(
        self,
        mode: str = "all",
        send_telegram: bool = True,
        *,
        intraday: bool = False,
    ) -> tuple[list[StockTradingPlan], FuturesTradingPlan | None, dict]:
        """전체 분석 실행

        Args:
            mode: "all", "stock" (선물 분석 비활성화)
            send_telegram: 텔레그램 알림 전송 여부
            intraday: 장중 경량 갱신 모드 (backtest, DART, KSD, LLM scoring 생략)

        Returns:
            (stock_plans, futures_plan, analysis_data)
        """
        mode_label = f"{mode}/intraday" if intraday else mode
        logger.info(f"Starting unified analysis - mode: {mode_label}")
        snapshot_id = datetime.now().strftime("%Y%m%dT%H%M%S")

        stock_plans = []
        stock_analysis = {}
        futures_plan = None
        futures_analysis = {}

        # 주식 분석
        if mode in ["all", "stock"]:
            stock_plans, stock_analysis = await self._analyze_stocks(intraday=intraday)

        # 선물 분석 (비활성화)
        if mode in ["all", "futures"]:
            logger.info(
                "Futures analysis disabled: skipping futures data in LLM output"
            )

        # 통합 데이터
        analysis_data = {
            "snapshot_id": snapshot_id,
            "date": self.date,
            "generated_at": self.datetime_str,
            "stock": stock_analysis,
        }

        # 리포트 저장
        if stock_plans or futures_plan or stock_analysis:
            self._save_reports(stock_plans, futures_plan, analysis_data, snapshot_id)
            if stock_plans:
                self._save_training_rows(snapshot_id, stock_plans, stock_analysis)

        # 실시간-배치 융합용 LLM 품질 스냅샷 게시(best-effort)
        if _reporting.should_publish_llm_quality_snapshot(stock_analysis):
            self._publish_llm_quality_snapshot(snapshot_id, stock_plans, stock_analysis)

        # 텔레그램 알림
        if send_telegram and self.notifier:
            await self._send_telegram_alerts(
                stock_plans, futures_plan, futures_analysis, stock_analysis
            )

        return stock_plans, futures_plan, analysis_data

    async def _analyze_stocks(
        self, *, intraday: bool = False
    ) -> tuple[list[StockTradingPlan], dict]:
        """주식 분석 (다중 데이터 소스 활용)"""
        return await _stock_analysis.analyze_stocks(self, intraday=intraday)

    @staticmethod
    @staticmethod
    @staticmethod
    @staticmethod
    @staticmethod
    @staticmethod
    @staticmethod
    async def _send_telegram_alerts(
        self,
        stock_plans: list[StockTradingPlan],
        futures_plan: FuturesTradingPlan | None,
        futures_analysis: dict,
        stock_analysis: dict | None = None,
    ):
        """텔레그램 알림 전송"""
        await _reporting.send_telegram_alerts(
            self, stock_plans, futures_plan, futures_analysis, stock_analysis
        )

    def _save_reports(
        self,
        stock_plans: list[StockTradingPlan],
        futures_plan: FuturesTradingPlan | None,
        analysis_data: dict,
        snapshot_id: str,
    ):
        """리포트 저장"""
        _reporting.save_reports(
            self, stock_plans, futures_plan, analysis_data, snapshot_id
        )

    def _build_llm_quality_snapshot(
        self,
        snapshot_id: str,
        stock_plans: list[StockTradingPlan],
        stock_analysis: dict[str, Any],
    ) -> dict[str, Any]:
        return _reporting.build_llm_quality_snapshot(
            self, snapshot_id, stock_plans, stock_analysis
        )

    def _publish_llm_quality_snapshot(
        self,
        snapshot_id: str,
        stock_plans: list[StockTradingPlan],
        stock_analysis: dict[str, Any],
    ) -> None:
        _reporting.publish_llm_quality_snapshot(
            self, snapshot_id, stock_plans, stock_analysis
        )

    def _save_training_rows(
        self,
        snapshot_id: str,
        stock_plans: list[StockTradingPlan],
        stock_analysis: dict[str, Any],
    ) -> None:
        _reporting.save_training_rows(self, snapshot_id, stock_plans, stock_analysis)

    def generate_detailed_briefing(self, code: str) -> StockDetailedBriefing | None:
        """종목 코드에 대한 상세 브리핑 생성"""
        return _stock_analysis.generate_detailed_briefing(self, code)
