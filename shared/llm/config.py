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
    stock_min_market_cap: int = 100_000_000_000  # 1000억
    stock_max_market_cap: int = 50_000_000_000_000  # 50조
    stock_min_price: int = 1000
    stock_max_price: int = 500000
    stock_top_n_volume: int = 30
    stock_final_selection: int = 5
    stock_backtest_days: int = 60
    stock_max_position: float = 0.20
    stock_stop_loss: float = 0.05
    stock_take_profit: float = 0.10

    # 선물 분석 가중치
    futures_weight_global: float = 0.35
    futures_weight_flow: float = 0.30
    futures_weight_technical: float = 0.20
    futures_weight_event: float = 0.15
    futures_stop_loss_pt: float = 3.0
    futures_take_profit_pt: float = 6.0

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
            stock_min_market_cap=stock_config.get("min_market_cap", 100_000_000_000),
            stock_max_market_cap=stock_config.get("max_market_cap", 50_000_000_000_000),
            stock_min_price=stock_config.get("min_price", 1000),
            stock_max_price=stock_config.get("max_price", 500000),
            stock_top_n_volume=stock_config.get("top_n_volume", 30),
            stock_final_selection=stock_config.get("final_selection", 5),
            stock_backtest_days=stock_config.get("backtest_days", 60),
            stock_max_position=stock_config.get("max_position", 0.20),
            stock_stop_loss=stock_config.get("stop_loss", 0.05),
            stock_take_profit=stock_config.get("take_profit", 0.10),
            # 선물 설정
            futures_weight_global=futures_config.get("weight_global", 0.35),
            futures_weight_flow=futures_config.get("weight_flow", 0.30),
            futures_weight_technical=futures_config.get("weight_technical", 0.20),
            futures_weight_event=futures_config.get("weight_event", 0.15),
            futures_stop_loss_pt=futures_config.get("stop_loss_pt", 3.0),
            futures_take_profit_pt=futures_config.get("take_profit_pt", 6.0),
            # KRX API 설정
            krx_api_key=os.environ.get("KRX_API_KEY", krx_config.get("api_key", "")),
            krx_base_url=krx_config.get("base_url", "http://data.krx.co.kr/svc/apis"),
            krx_timeout=krx_config.get("timeout_seconds", 30),
            krx_analysis_days=krx_config.get("analysis_days", 20),
            sector_etfs=krx_config.get("sector_etfs", default_sector_etfs),
            indices=krx_config.get("indices", default_indices),
        )
