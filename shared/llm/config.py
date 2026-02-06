"""
LLM 분석 설정
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

import yaml


@dataclass
class LLMConfig:
    """LLM Analyzer Configuration"""

    # OpenAI 설정
    api_key: str = ""
    model: str = "gpt-4o-mini"
    max_tokens: int = 1500
    temperature: float = 0.3
    enabled: bool = True

    # 출력 설정
    output_dir: str = "./trading_reports"

    # 주식 스크리닝 설정
    stock_markets: List[str] = field(default_factory=lambda: ["KOSPI"])
    stock_min_market_cap: int = 100_000_000_000  # 1000억
    stock_max_market_cap: int = 50_000_000_000_000  # 50조
    stock_min_price: int = 1000
    stock_max_price: int = 500000
    stock_top_n_volume: int = 30
    stock_final_selection: int = 5
    stock_backtest_days: int = 60
    stock_history_days: int = 252
    stock_min_history_days: int = 90
    stock_volume_lookback_days: int = 20
    stock_min_avg_volume: int = 100_000
    stock_min_trade_value: float = 500_000_000  # 최소 거래대금 (5억)
    stock_min_turnover: float = 0.003  # 거래대금/시가총액 최소 비율
    stock_momentum_lookback_days: int = 252
    stock_max_atr_pct: float = 0.08
    stock_max_drawdown_pct: float = 0.25
    stock_min_backtest_trades: int = 5
    stock_min_backtest_win_rate: float = 45.0
    stock_max_position: float = 0.20
    stock_stop_loss: float = 0.05
    stock_take_profit: float = 0.10
    stock_blacklist: List[str] = field(
        default_factory=lambda: ["관리종목", "투자주의", "환기종목", "거래정지"]
    )
    stock_keyword_filter: List[str] = field(
        default_factory=lambda: ["횡령", "배임", "감자", "상장폐지", "회생절차"]
    )
    stock_exclude_name_keywords: List[str] = field(
        default_factory=lambda: ["스팩", "SPAC", "리츠", "REIT"]
    )
    stock_exclude_preferred_shares: bool = True
    stock_risk_keywords: List[str] = field(
        default_factory=lambda: [
            "유상증자",
            "전환사채",
            "CB",
            "BW",
            "불성실공시",
            "감사의견",
            "실적부진",
        ]
    )
    stock_score_weight_momentum: float = 0.25
    stock_score_weight_technical: float = 0.20
    stock_score_weight_backtest: float = 0.25
    stock_score_weight_news: float = 0.10
    stock_score_weight_liquidity: float = 0.10
    stock_score_weight_risk: float = 0.10

    # 선물 분석 가중치
    futures_weight_global: float = 0.35
    futures_weight_flow: float = 0.30
    futures_weight_technical: float = 0.20
    futures_weight_event: float = 0.15
    futures_stop_loss_pt: float = 3.0
    futures_take_profit_pt: float = 6.0
    futures_tick_stream: str = "raw_data"
    futures_tick_lookback_seconds: int = 600
    futures_tick_max: int = 2000
    futures_tick_symbol: str = ""

    # KRX Open API 설정
    krx_api_key: str = ""
    krx_base_url: str = "http://data.krx.co.kr/svc/apis"
    krx_timeout: int = 30
    krx_analysis_days: int = 20

    # 섹터 ETF 매핑
    sector_etfs: Dict[str, List[str]] = field(default_factory=lambda: {
        "반도체": ["091160", "091170", "395160"],
        "2차전지": ["305720", "371460", "394670"],
        "바이오": ["244580", "261060"],
        "금융": ["091180", "140700"],
        "자동차": ["091170", "204450"],
        "철강": ["117680"],
        "조선": ["140710"],
        "건설": ["117700"],
        "에너지": ["117460", "261220"],
        "인터넷": ["261110"],
        "게임": ["251340"],
    })

    # 지수 코드 매핑
    indices: Dict[str, str] = field(default_factory=lambda: {
        "KOSPI": "KS11",
        "KOSDAQ": "KQ11",
        "KOSPI200": "KS200",
        "KOSPI_LARGE": "KS100",
        "KOSDAQ150": "KQ150",
    })

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """환경변수에서 설정 로드"""
        return cls(
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
            max_tokens=int(os.environ.get("LLM_MAX_TOKENS", "1500")),
            temperature=float(os.environ.get("LLM_TEMPERATURE", "0.3")),
            enabled=os.environ.get("LLM_ANALYSIS_ENABLED", "true").lower() == "true",
            output_dir=os.environ.get("LLM_OUTPUT_DIR", "./trading_reports"),
            krx_api_key=os.environ.get("KRX_API_KEY", ""),
            futures_tick_stream=os.environ.get("LLM_FUTURES_TICK_STREAM", "raw_data"),
            futures_tick_lookback_seconds=int(
                os.environ.get("LLM_FUTURES_TICK_LOOKBACK_SECONDS", "600")
            ),
            futures_tick_max=int(os.environ.get("LLM_FUTURES_TICK_MAX", "2000")),
            futures_tick_symbol=os.environ.get("LLM_FUTURES_TICK_SYMBOL", ""),
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "LLMConfig":
        """YAML 파일에서 설정 로드"""
        with open(path) as f:
            data = yaml.safe_load(f)

        # YAML 섹션 매핑 (새 포맷과 기존 포맷 모두 지원)
        openai_config = data.get("openai", data.get("llm", {}))
        stock_config = data.get("stock", data.get("stock_screening", {}))
        futures_config = data.get("futures", data.get("futures_analysis", {}))
        output_config = data.get("output", {})
        krx_config = data.get("krx_api", {})

        # 기본 섹터 ETF 매핑
        default_sector_etfs = {
            "반도체": ["091160", "091170", "395160"],
            "2차전지": ["305720", "371460", "394670"],
            "바이오": ["244580", "261060"],
            "금융": ["091180", "140700"],
            "자동차": ["091170", "204450"],
            "철강": ["117680"],
            "조선": ["140710"],
            "건설": ["117700"],
            "에너지": ["117460", "261220"],
            "인터넷": ["261110"],
            "게임": ["251340"],
        }

        # 기본 지수 매핑
        default_indices = {
            "KOSPI": "KS11",
            "KOSDAQ": "KQ11",
            "KOSPI200": "KS200",
            "KOSPI_LARGE": "KS100",
            "KOSDAQ150": "KQ150",
        }

        return cls(
            # OpenAI 설정
            api_key=os.environ.get("OPENAI_API_KEY", openai_config.get("api_key", "")),
            model=openai_config.get("model", "gpt-4o-mini"),
            max_tokens=openai_config.get("max_tokens", 1500),
            temperature=openai_config.get("temperature", 0.3),
            enabled=openai_config.get("enabled", True),
            output_dir=output_config.get("dir", "./trading_reports"),
            # 주식 설정
            stock_markets=stock_config.get("markets", ["KOSPI"]),
            stock_min_market_cap=stock_config.get("min_market_cap", 100_000_000_000),
            stock_max_market_cap=stock_config.get("max_market_cap", 50_000_000_000_000),
            stock_min_price=stock_config.get("min_price", 1000),
            stock_max_price=stock_config.get("max_price", 500000),
            stock_top_n_volume=stock_config.get("top_n_volume", 30),
            stock_final_selection=stock_config.get("final_selection", 5),
            stock_backtest_days=stock_config.get("backtest_days", 60),
            stock_history_days=stock_config.get("history_days", 252),
            stock_min_history_days=stock_config.get("min_history_days", 90),
            stock_volume_lookback_days=stock_config.get("volume_lookback_days", 20),
            stock_min_avg_volume=stock_config.get("min_avg_volume", 100_000),
            stock_min_trade_value=stock_config.get("min_trade_value", 500_000_000),
            stock_min_turnover=stock_config.get("min_turnover", 0.003),
            stock_momentum_lookback_days=stock_config.get("momentum_lookback_days", 252),
            stock_max_atr_pct=stock_config.get("max_atr_pct", 0.08),
            stock_max_drawdown_pct=stock_config.get("max_drawdown_pct", 0.25),
            stock_min_backtest_trades=stock_config.get("min_backtest_trades", 5),
            stock_min_backtest_win_rate=stock_config.get("min_backtest_win_rate", 45.0),
            stock_max_position=stock_config.get("max_position", 0.20),
            stock_stop_loss=stock_config.get("stop_loss", 0.05),
            stock_take_profit=stock_config.get("take_profit", 0.10),
            stock_blacklist=stock_config.get(
                "blacklist", ["관리종목", "투자주의", "환기종목", "거래정지"]
            ),
            stock_keyword_filter=stock_config.get(
                "keyword_filter", ["횡령", "배임", "감자", "상장폐지", "회생절차"]
            ),
            stock_exclude_name_keywords=stock_config.get(
                "exclude_name_keywords", ["스팩", "SPAC", "리츠", "REIT"]
            ),
            stock_exclude_preferred_shares=stock_config.get(
                "exclude_preferred_shares", True
            ),
            stock_risk_keywords=stock_config.get(
                "risk_keywords",
                ["유상증자", "전환사채", "CB", "BW", "불성실공시", "감사의견", "실적부진"],
            ),
            stock_score_weight_momentum=stock_config.get("score_weight_momentum", 0.25),
            stock_score_weight_technical=stock_config.get("score_weight_technical", 0.20),
            stock_score_weight_backtest=stock_config.get("score_weight_backtest", 0.25),
            stock_score_weight_news=stock_config.get("score_weight_news", 0.10),
            stock_score_weight_liquidity=stock_config.get("score_weight_liquidity", 0.10),
            stock_score_weight_risk=stock_config.get("score_weight_risk", 0.10),
            # 선물 설정
            futures_weight_global=futures_config.get("weight_global", 0.35),
            futures_weight_flow=futures_config.get("weight_flow", 0.30),
            futures_weight_technical=futures_config.get("weight_technical", 0.20),
            futures_weight_event=futures_config.get("weight_event", 0.15),
            futures_stop_loss_pt=futures_config.get("stop_loss_pt", 3.0),
            futures_take_profit_pt=futures_config.get("take_profit_pt", 6.0),
            futures_tick_stream=futures_config.get("tick_stream", "raw_data"),
            futures_tick_lookback_seconds=futures_config.get("tick_lookback_seconds", 600),
            futures_tick_max=futures_config.get("tick_max", 2000),
            futures_tick_symbol=futures_config.get("tick_symbol", ""),
            # KRX API 설정
            krx_api_key=os.environ.get("KRX_API_KEY", krx_config.get("api_key", "")),
            krx_base_url=krx_config.get("base_url", "http://data.krx.co.kr/svc/apis"),
            krx_timeout=krx_config.get("timeout_seconds", 30),
            krx_analysis_days=krx_config.get("analysis_days", 20),
            sector_etfs=krx_config.get("sector_etfs", default_sector_etfs),
            indices=krx_config.get("indices", default_indices),
        )

    @classmethod
    def load(cls, path: str | Path | None = None) -> "LLMConfig":
        """기본 경로/환경변수에서 설정 로드.

        우선순위:
        1) 인자로 받은 path
        2) 환경변수 LLM_CONFIG_PATH
        3) 레포 기본값 config/llm.yaml (CWD 또는 레포 루트)
        4) 환경변수 기반(from_env)
        """
        if path is not None:
            return cls.from_yaml(path)

        env_path = os.environ.get("LLM_CONFIG_PATH")
        if env_path:
            p = Path(env_path)
            if p.exists():
                return cls.from_yaml(p)

        candidates = [
            Path.cwd() / "config" / "llm.yaml",
            Path(__file__).resolve().parents[3] / "config" / "llm.yaml",
        ]
        for p in candidates:
            if p.exists():
                return cls.from_yaml(p)

        return cls.from_env()
