"""
LLM 분석 설정
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, ClassVar

from pydantic import Field

from shared.config.base import ServiceConfigBase


def default_stock_technical_consensus() -> dict[str, Any]:
    """Default stock timing-consensus settings."""
    return {
        "min_entry_votes": 2,
        "min_exit_votes": 2,
        "min_entry_core_votes": 2,
        "min_exit_core_votes": 2,
        "rsi_oversold": 35.0,
        "rsi_recovery": 40.0,
        "rsi_overbought": 70.0,
        "rsi_rollover": 60.0,
        "williams_oversold": -80.0,
        "williams_reversal": -65.0,
        "williams_overbought": -20.0,
        "williams_exit": -35.0,
        "macd_hist_threshold": 0.0,
        "include_trend_vote": True,
        "trend_buffer_pct": 0.0,
        "include_volume_vote": True,
        "min_volume_ratio": 1.2,
        "exit_retrace_from_high_pct": 0.03,
    }


class LLMConfig(ServiceConfigBase):
    """LLM Analyzer Configuration"""

    # Class-level configuration
    _default_config_file: ClassVar[str] = "llm.yaml"
    _env_prefix: ClassVar[str] = "LLM_"

    # LLM 공통 설정
    llm_provider: str = Field(
        default="openai", description="LLM provider: 'openai' or 'claude'"
    )
    api_key: str = Field(default="", description="API key for LLM provider")
    model: str = Field(default="gpt-4o-mini", description="LLM model name")
    max_tokens: int = Field(default=1500, description="Maximum tokens per request")
    temperature: float = Field(default=0.3, description="LLM temperature")
    enabled: bool = Field(default=True, description="Enable LLM analysis")
    llm_strict_json_schema: bool = Field(
        default=True, description="Strict JSON schema validation"
    )
    llm_prompt_cache_enabled: bool = Field(
        default=True, description="Enable prompt caching"
    )
    llm_prompt_cache_ttl_seconds: int = Field(
        default=21_600, description="Prompt cache TTL in seconds"
    )
    llm_prompt_cache_prefix: str = Field(
        default="llm:prompt_cache", description="Redis key prefix for prompt cache"
    )
    llm_batch_size: int = Field(default=10, description="Batch size for bulk analysis")

    # 출력 설정
    output_dir: str = Field(
        default="./trading_reports", description="Output directory for reports"
    )

    # 주식 스크리닝 설정
    stock_markets: list[str] = Field(
        default_factory=lambda: ["KOSPI"], description="Markets to screen"
    )
    stock_min_market_cap: int = Field(
        default=100_000_000_000, description="Minimum market cap (1000억)"
    )
    stock_max_market_cap: int = Field(
        default=50_000_000_000_000, description="Maximum market cap (50조)"
    )
    stock_min_price: int = Field(default=1000, description="Minimum stock price")
    stock_top_n_volume: int = Field(
        default=30, description="Top N stocks by volume to analyze"
    )
    stock_final_selection: int = Field(
        default=5, description="Final number of stocks to recommend"
    )
    stock_backtest_days: int = Field(default=60, description="Backtest period in days")
    stock_history_days: int = Field(
        default=252, description="Historical data period in days"
    )
    stock_min_history_days: int = Field(
        default=90, description="Minimum history days required"
    )
    stock_new_listing_min_days: int = Field(
        default=20, description="Minimum days since listing"
    )
    stock_new_listing_penalty: float = Field(
        default=0.7, description="Score penalty for new listings"
    )
    stock_volume_lookback_days: int = Field(
        default=20, description="Volume average calculation period"
    )
    stock_min_trade_value: float = Field(
        default=500_000_000, description="Minimum trade value (5억)"
    )
    stock_min_turnover: float = Field(
        default=0.003, description="Minimum turnover ratio"
    )
    stock_momentum_lookback_days: int = Field(
        default=252, description="Momentum lookback period"
    )
    stock_max_atr_pct: float = Field(
        default=0.08, description="Maximum ATR/price ratio"
    )
    stock_max_drawdown_pct: float = Field(
        default=0.25, description="Maximum drawdown threshold"
    )
    stock_min_backtest_trades: int = Field(
        default=10, description="Minimum backtest trades"
    )
    stock_min_backtest_win_rate: float = Field(
        default=45.0, description="Minimum backtest win rate"
    )
    stock_min_recommendation_score: float = Field(
        default=5.0, description="Minimum recommendation score"
    )
    stock_max_position: float = Field(
        default=0.20, description="Maximum position size (20%)"
    )
    stock_stop_loss: float = Field(default=0.05, description="Stop loss threshold")
    stock_take_profit: float = Field(default=0.10, description="Take profit threshold")
    stock_blacklist: list[str] = Field(
        default_factory=lambda: ["관리종목", "투자주의", "환기종목", "거래정지"],
        description="Blacklisted stock types",
    )
    stock_keyword_filter: list[str] = Field(
        default_factory=lambda: ["횡령", "배임", "감자", "상장폐지", "회생절차"],
        description="Negative keywords to filter",
    )
    stock_exclude_name_keywords: list[str] = Field(
        default_factory=lambda: ["스팩", "SPAC", "리츠", "REIT"],
        description="Stock name keywords to exclude",
    )
    stock_exclude_preferred_shares: bool = Field(
        default=True, description="Exclude preferred shares"
    )
    stock_risk_keywords: list[str] = Field(
        default_factory=lambda: [
            "유상증자",
            "전환사채",
            "CB",
            "BW",
            "불성실공시",
            "감사의견",
            "실적부진",
        ],
        description="Risk keywords",
    )
    stock_enable_kis_target_price: bool = Field(
        default=True, description="Enable KIS target price analysis"
    )
    stock_target_lookback_days: int = Field(
        default=180, description="Target price lookback period"
    )
    stock_score_weight_momentum: float = Field(
        default=0.35, description="Momentum score weight"
    )
    stock_score_weight_technical: float = Field(
        default=0.15, description="Technical score weight"
    )
    stock_score_weight_backtest: float = Field(
        default=0.20, description="Backtest score weight"
    )
    stock_score_weight_news: float = Field(default=0.10, description="News score weight")
    stock_score_weight_liquidity: float = Field(
        default=0.10, description="Liquidity score weight"
    )
    stock_score_weight_target_price: float = Field(
        default=0.10, description="Target price score weight"
    )
    stock_score_weight_risk: float = Field(default=0.10, description="Risk score weight")
    stock_score_weight_theme: float = Field(
        default=0.15, description="Theme/sector score weight"
    )
    stock_llm_scoring_enabled: bool = Field(
        default=True, description="Enable LLM-based scoring"
    )
    stock_llm_scoring_model: str = Field(
        default="", description="LLM model for scoring (empty = use default)"
    )
    stock_llm_scoring_max_tokens: int = Field(
        default=500, description="Max tokens for LLM scoring"
    )
    stock_llm_scoring_temperature: float = Field(
        default=0.2, description="Temperature for LLM scoring"
    )
    stock_technical_consensus: dict[str, Any] = Field(
        default_factory=default_stock_technical_consensus,
        description="RSI/Williams %R/MACD consensus settings for stock timing",
    )

    # 선물 분석 가중치
    futures_prompt_addendum: str = Field(
        default="",
        description=(
            "Futures-specific LLM prompt addendum injected when asset_class='futures'. "
            "Loaded from config/llm.yaml::futures.prompt_addendum. "
            "Empty string disables the addendum."
        ),
    )
    futures_weight_global: float = Field(
        default=0.35, description="Global market weight"
    )
    futures_weight_flow: float = Field(default=0.30, description="Flow weight")
    futures_weight_technical: float = Field(
        default=0.20, description="Technical analysis weight"
    )
    futures_weight_event: float = Field(default=0.15, description="Event weight")
    futures_stop_loss_pt: float = Field(default=3.0, description="Stop loss points")
    futures_take_profit_pt: float = Field(
        default=6.0, description="Take profit points"
    )
    futures_tick_stream: str = Field(
        default="raw_data", description="Tick stream name"
    )
    futures_tick_lookback_seconds: int = Field(
        default=600, description="Tick lookback period in seconds"
    )
    futures_tick_max: int = Field(default=2000, description="Maximum ticks to fetch")
    futures_tick_symbol: str = Field(default="", description="Futures symbol")

    # KRX Open API 설정
    krx_api_key: str = Field(default="", description="KRX API key")
    krx_base_url: str = Field(
        default="https://data-dbg.krx.co.kr/svc/apis", description="KRX API base URL"
    )
    krx_timeout: int = Field(default=30, description="KRX API timeout in seconds")
    krx_analysis_days: int = Field(
        default=20, description="KRX analysis period in days"
    )

    # 섹터 ETF 매핑
    sector_etfs: dict[str, list[str]] = Field(
        default_factory=lambda: {
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
        },
        description="Sector ETF code mappings",
    )

    # 지수 코드 매핑
    indices: dict[str, str] = Field(
        default_factory=lambda: {
            "KOSPI": "KS11",
            "KOSDAQ": "KQ11",
            "KOSPI200": "KS200",
            "KOSPI_LARGE": "KS100",
            "KOSDAQ150": "KQ150",
        },
        description="Index code mappings",
    )

    @classmethod
    def from_env(cls, env_prefix: str | None = None, **overrides: Any) -> LLMConfig:
        """환경변수에서 설정 로드.

        Provider-specific API key resolution:
        - For provider='openai': uses OPENAI_API_KEY
        - For provider='claude': uses ANTHROPIC_API_KEY
        """
        # Get provider first to determine which API key to use
        provider = os.environ.get("LLM_PROVIDER", "openai").strip().lower()
        if provider not in ("openai", "claude"):
            provider = "openai"

        # Resolve API key based on provider
        if provider == "claude":
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            default_model = "claude-3-5-haiku-latest"
        else:
            api_key = os.environ.get("OPENAI_API_KEY", "")
            default_model = "gpt-4o-mini"

        # Extract all LLM_* environment variables using base class method
        env_vars = cls._extract_env_vars(env_prefix or cls._env_prefix or "LLM_")

        # Override with provider-specific values
        env_vars["llm_provider"] = provider
        env_vars["api_key"] = api_key

        # Set default model if not provided
        if "model" not in env_vars:
            env_vars["model"] = os.environ.get("LLM_MODEL", default_model)

        # Handle fields with "llm_" prefix in field name but env var uses plain "LLM_".
        # _extract_env_vars("LLM_") strips prefix → "prompt_cache_enabled" which
        # doesn't match field "llm_prompt_cache_enabled". Map explicitly.
        _llm_field_map = {
            "LLM_STRICT_JSON_SCHEMA": "llm_strict_json_schema",
            "LLM_PROMPT_CACHE_ENABLED": "llm_prompt_cache_enabled",
            "LLM_PROMPT_CACHE_TTL_SECONDS": "llm_prompt_cache_ttl_seconds",
            "LLM_PROMPT_CACHE_PREFIX": "llm_prompt_cache_prefix",
            "LLM_BATCH_SIZE": "llm_batch_size",
        }
        for env_key, field_name in _llm_field_map.items():
            if field_name not in env_vars:
                env_val = os.environ.get(env_key)
                if env_val is not None:
                    field_info = cls.model_fields.get(field_name)
                    if field_info is not None:
                        env_vars[field_name] = cls._parse_env_value(
                            env_val, field_info.annotation
                        )

        # Handle KRX API key (uses different prefix)
        if "krx_api_key" not in env_vars:
            env_vars["krx_api_key"] = os.environ.get("KRX_API_KEY", "")

        # Handle futures tick settings with LLM_FUTURES_* prefix
        if "futures_tick_stream" not in env_vars:
            env_vars["futures_tick_stream"] = os.environ.get(
                "LLM_FUTURES_TICK_STREAM", "raw_data"
            )
        if "futures_tick_lookback_seconds" not in env_vars:
            env_vars["futures_tick_lookback_seconds"] = int(
                os.environ.get("LLM_FUTURES_TICK_LOOKBACK_SECONDS", "600")
            )
        if "futures_tick_max" not in env_vars:
            env_vars["futures_tick_max"] = int(
                os.environ.get("LLM_FUTURES_TICK_MAX", "2000")
            )
        if "futures_tick_symbol" not in env_vars:
            env_vars["futures_tick_symbol"] = os.environ.get(
                "LLM_FUTURES_TICK_SYMBOL", ""
            )

        # Apply user overrides
        env_vars.update(overrides)

        return cls(**env_vars)

    @classmethod
    def from_yaml(
        cls,
        path: str | Path | None = None,
        section: str | None = None,
        *,
        apply_env_overrides: bool = False,
        env_prefix: str | None = None,
    ) -> LLMConfig:
        """YAML 파일에서 설정 로드.

        Handles complex nested YAML structure with provider-specific settings.
        Supports both new format (llm/openai/claude sections) and legacy formats.
        """
        # Use ConfigLoader to load YAML with env var substitution
        from shared.config.loader import ConfigLoader

        if path is None:
            path = cls._default_config_file
            if path is None:
                raise ValueError(
                    f"{cls.__name__} requires 'path' argument or "
                    "_default_config_file class attribute"
                )

        # ConfigLoader.load() expects a str (calls unquote internally).
        # Convert Path objects and handle absolute paths directly.
        path_str = str(path)
        import os as _os

        if _os.path.isabs(path_str):
            import yaml as _yaml

            with open(path_str, "r", encoding="utf-8") as _f:
                data = _yaml.safe_load(_f) or {}
        else:
            data = ConfigLoader.load(path_str)

        # Extract sections (supports both new and legacy formats)
        llm_common = data.get("llm", {}) if isinstance(data, dict) else {}
        openai_config = data.get("openai", {}) if isinstance(data, dict) else {}
        claude_config = data.get("claude", {}) if isinstance(data, dict) else {}
        stock_config = (
            data.get("stock", data.get("stock_screening", {}))
            if isinstance(data, dict)
            else {}
        )
        futures_config = (
            data.get("futures", data.get("futures_analysis", {}))
            if isinstance(data, dict)
            else {}
        )
        output_config = data.get("output", {}) if isinstance(data, dict) else {}
        krx_config = data.get("krx_api", {}) if isinstance(data, dict) else {}

        # Ensure sections are dicts
        if not isinstance(llm_common, dict):
            llm_common = {}
        if not isinstance(openai_config, dict):
            openai_config = {}
        if not isinstance(claude_config, dict):
            claude_config = {}
        if not isinstance(stock_config, dict):
            stock_config = {}
        if not isinstance(futures_config, dict):
            futures_config = {}
        if not isinstance(output_config, dict):
            output_config = {}
        if not isinstance(krx_config, dict):
            krx_config = {}

        # Determine provider (env var takes precedence)
        provider = str(
            os.environ.get("LLM_PROVIDER", llm_common.get("provider", "openai"))
        ).strip().lower()
        if provider not in ("openai", "claude"):
            provider = "openai"

        # Select provider-specific config
        provider_config = claude_config if provider == "claude" else openai_config
        default_model = (
            "claude-3-5-haiku-latest" if provider == "claude" else "gpt-4o-mini"
        )
        env_key_name = "ANTHROPIC_API_KEY" if provider == "claude" else "OPENAI_API_KEY"

        # Helper function to get value with env var override
        def get_value(env_key: str, yaml_keys: list[Any], default: Any) -> Any:
            """Get value from env var or YAML (provider-specific → common → default)."""
            env_val = os.environ.get(env_key)
            if env_val is not None:
                # Convert env var to appropriate type
                if isinstance(default, bool):
                    return env_val.strip().lower() == "true"
                elif isinstance(default, int):
                    return int(env_val)
                elif isinstance(default, float):
                    return float(env_val)
                return env_val
            # Try YAML values in order
            for val in yaml_keys:
                if val is not None:
                    return val
            return default

        # Build flattened config dict with all fields
        config_dict = {
            # LLM common settings
            "llm_provider": provider,
            "api_key": os.environ.get(
                env_key_name,
                provider_config.get("api_key", llm_common.get("api_key", "")),
            ),
            "model": get_value(
                "LLM_MODEL",
                [
                    provider_config.get("model"),
                    llm_common.get("model"),
                ],
                default_model,
            ),
            "max_tokens": get_value(
                "LLM_MAX_TOKENS",
                [
                    provider_config.get("max_tokens"),
                    llm_common.get("max_tokens"),
                ],
                1500,
            ),
            "temperature": get_value(
                "LLM_TEMPERATURE",
                [
                    provider_config.get("temperature"),
                    llm_common.get("temperature"),
                ],
                0.3,
            ),
            "enabled": get_value(
                "LLM_ANALYSIS_ENABLED",
                [
                    provider_config.get("enabled"),
                    llm_common.get("enabled"),
                ],
                True,
            ),
            "llm_strict_json_schema": get_value(
                "LLM_STRICT_JSON_SCHEMA",
                [
                    llm_common.get("strict_json_schema"),
                    provider_config.get("strict_json_schema"),
                ],
                True,
            ),
            "llm_prompt_cache_enabled": get_value(
                "LLM_PROMPT_CACHE_ENABLED",
                [
                    llm_common.get("prompt_cache_enabled"),
                    provider_config.get("prompt_cache_enabled"),
                ],
                True,
            ),
            "llm_prompt_cache_ttl_seconds": get_value(
                "LLM_PROMPT_CACHE_TTL_SECONDS",
                [
                    llm_common.get("prompt_cache_ttl_seconds"),
                    provider_config.get("prompt_cache_ttl_seconds"),
                ],
                21600,
            ),
            "llm_prompt_cache_prefix": get_value(
                "LLM_PROMPT_CACHE_PREFIX",
                [
                    llm_common.get("prompt_cache_prefix"),
                    provider_config.get("prompt_cache_prefix"),
                ],
                "llm:prompt_cache",
            ),
            "llm_batch_size": max(
                1,
                get_value(
                    "LLM_BATCH_SIZE",
                    [
                        llm_common.get("batch_size"),
                        provider_config.get("batch_size"),
                    ],
                    10,
                ),
            ),
            # Output settings
            "output_dir": output_config.get("dir", "./trading_reports"),
            # Stock settings (all stock_* prefixed fields)
            "stock_markets": stock_config.get("markets", ["KOSPI"]),
            "stock_min_market_cap": stock_config.get("min_market_cap", 100_000_000_000),
            "stock_max_market_cap": stock_config.get(
                "max_market_cap", 50_000_000_000_000
            ),
            "stock_min_price": stock_config.get("min_price", 1000),
            "stock_top_n_volume": stock_config.get("top_n_volume", 30),
            "stock_final_selection": stock_config.get("final_selection", 5),
            "stock_backtest_days": stock_config.get("backtest_days", 60),
            "stock_history_days": stock_config.get("history_days", 252),
            "stock_min_history_days": stock_config.get("min_history_days", 90),
            "stock_new_listing_min_days": stock_config.get("new_listing_min_days", 20),
            "stock_new_listing_penalty": stock_config.get("new_listing_penalty", 0.7),
            "stock_volume_lookback_days": stock_config.get("volume_lookback_days", 20),
            "stock_min_trade_value": stock_config.get("min_trade_value", 500_000_000),
            "stock_min_turnover": stock_config.get("min_turnover", 0.003),
            "stock_momentum_lookback_days": stock_config.get(
                "momentum_lookback_days", 252
            ),
            "stock_max_atr_pct": stock_config.get("max_atr_pct", 0.08),
            "stock_max_drawdown_pct": stock_config.get("max_drawdown_pct", 0.25),
            "stock_min_backtest_trades": stock_config.get("min_backtest_trades", 10),
            "stock_min_backtest_win_rate": stock_config.get("min_backtest_win_rate", 45.0),
            "stock_min_recommendation_score": stock_config.get(
                "min_recommendation_score", 5.0
            ),
            "stock_max_position": stock_config.get("max_position", 0.20),
            "stock_stop_loss": stock_config.get("stop_loss", 0.05),
            "stock_take_profit": stock_config.get("take_profit", 0.10),
            "stock_blacklist": stock_config.get(
                "blacklist", ["관리종목", "투자주의", "환기종목", "거래정지"]
            ),
            "stock_keyword_filter": stock_config.get(
                "keyword_filter", ["횡령", "배임", "감자", "상장폐지", "회생절차"]
            ),
            "stock_exclude_name_keywords": stock_config.get(
                "exclude_name_keywords", ["스팩", "SPAC", "리츠", "REIT"]
            ),
            "stock_exclude_preferred_shares": stock_config.get(
                "exclude_preferred_shares", True
            ),
            "stock_risk_keywords": stock_config.get(
                "risk_keywords",
                [
                    "유상증자",
                    "전환사채",
                    "CB",
                    "BW",
                    "불성실공시",
                    "감사의견",
                    "실적부진",
                ],
            ),
            "stock_enable_kis_target_price": stock_config.get(
                "enable_kis_target_price", True
            ),
            "stock_target_lookback_days": stock_config.get("target_lookback_days", 180),
            "stock_score_weight_momentum": stock_config.get(
                "score_weight_momentum", 0.35
            ),
            "stock_score_weight_technical": stock_config.get(
                "score_weight_technical", 0.15
            ),
            "stock_score_weight_backtest": stock_config.get(
                "score_weight_backtest", 0.20
            ),
            "stock_score_weight_news": stock_config.get("score_weight_news", 0.10),
            "stock_score_weight_liquidity": stock_config.get(
                "score_weight_liquidity", 0.10
            ),
            "stock_score_weight_target_price": stock_config.get(
                "score_weight_target_price", 0.10
            ),
            "stock_score_weight_risk": stock_config.get("score_weight_risk", 0.10),
            "stock_score_weight_theme": stock_config.get("score_weight_theme", 0.15),
            "stock_llm_scoring_enabled": stock_config.get("llm_scoring_enabled", True),
            "stock_llm_scoring_model": stock_config.get("llm_scoring_model", ""),
            "stock_llm_scoring_max_tokens": stock_config.get(
                "llm_scoring_max_tokens", 500
            ),
            "stock_llm_scoring_temperature": stock_config.get(
                "llm_scoring_temperature", 0.2
            ),
            "stock_technical_consensus": stock_config.get(
                "technical_consensus", default_stock_technical_consensus()
            ),
            # Futures settings
            "futures_prompt_addendum": futures_config.get("prompt_addendum", ""),
            "futures_weight_global": futures_config.get("weight_global", 0.35),
            "futures_weight_flow": futures_config.get("weight_flow", 0.30),
            "futures_weight_technical": futures_config.get("weight_technical", 0.20),
            "futures_weight_event": futures_config.get("weight_event", 0.15),
            "futures_stop_loss_pt": futures_config.get("stop_loss_pt", 3.0),
            "futures_take_profit_pt": futures_config.get("take_profit_pt", 6.0),
            "futures_tick_stream": futures_config.get("tick_stream", "raw_data"),
            "futures_tick_lookback_seconds": futures_config.get(
                "tick_lookback_seconds", 600
            ),
            "futures_tick_max": futures_config.get("tick_max", 2000),
            "futures_tick_symbol": futures_config.get("tick_symbol", ""),
            # KRX API settings
            "krx_api_key": os.environ.get("KRX_API_KEY", krx_config.get("api_key", "")),
            "krx_base_url": krx_config.get(
                "base_url", "https://data-dbg.krx.co.kr/svc/apis"
            ),
            "krx_timeout": krx_config.get("timeout_seconds", 30),
            "krx_analysis_days": krx_config.get("analysis_days", 20),
            "sector_etfs": krx_config.get(
                "sector_etfs",
                {
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
                },
            ),
            "indices": krx_config.get(
                "indices",
                {
                    "KOSPI": "KS11",
                    "KOSDAQ": "KQ11",
                    "KOSPI200": "KS200",
                    "KOSPI_LARGE": "KS100",
                    "KOSDAQ150": "KQ150",
                },
            ),
        }

        # Apply env var overrides if requested
        if apply_env_overrides:
            prefix = env_prefix if env_prefix is not None else cls._env_prefix
            if prefix:
                env_overrides = cls._extract_env_vars(prefix)
                config_dict.update(env_overrides)

        return cls(**config_dict)

    @classmethod
    def load(cls, path: str | Path | None = None) -> LLMConfig:
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
