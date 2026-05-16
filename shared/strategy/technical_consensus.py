"""Rule-based technical signal consensus for stock timing.

The module intentionally keeps the signal logic pure: callers provide a
snapshot of indicators and market data, and the function returns the entry/exit
votes that can be passed to an LLM, a screener, or an exit component.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TechnicalConsensusConfig:
    """Configuration for RSI/Williams %R/MACD timing consensus."""

    min_entry_votes: int = 2
    min_exit_votes: int = 2
    min_entry_core_votes: int = 2
    min_exit_core_votes: int = 2

    rsi_oversold: float = 35.0
    rsi_recovery: float = 40.0
    rsi_overbought: float = 70.0
    rsi_rollover: float = 60.0

    williams_oversold: float = -80.0
    williams_reversal: float = -65.0
    williams_overbought: float = -20.0
    williams_exit: float = -35.0

    macd_hist_threshold: float = 0.0
    include_trend_vote: bool = True
    trend_buffer_pct: float = 0.0
    include_volume_vote: bool = True
    min_volume_ratio: float = 1.2

    exit_retrace_from_high_pct: float = 0.03

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> TechnicalConsensusConfig:
        if not data:
            return cls()
        if isinstance(data.get("params"), Mapping):
            data = data["params"]  # type: ignore[assignment]
        valid_fields = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        config = cls(**filtered)
        config.validate()
        return config

    def validate(self) -> None:
        if self.min_entry_votes < 1:
            raise ValueError("min_entry_votes must be positive")
        if self.min_exit_votes < 1:
            raise ValueError("min_exit_votes must be positive")
        if self.min_entry_core_votes < 1:
            raise ValueError("min_entry_core_votes must be positive")
        if self.min_exit_core_votes < 1:
            raise ValueError("min_exit_core_votes must be positive")
        if not self.rsi_oversold < self.rsi_recovery < self.rsi_overbought:
            raise ValueError("RSI thresholds must satisfy oversold < recovery < overbought")
        if not self.rsi_rollover < self.rsi_overbought:
            raise ValueError("rsi_rollover must be lower than rsi_overbought")
        if not (
            self.williams_oversold
            < self.williams_reversal
            < self.williams_overbought
        ):
            raise ValueError(
                "Williams thresholds must satisfy oversold < reversal < overbought"
            )
        if not self.williams_oversold < self.williams_exit < self.williams_overbought:
            raise ValueError(
                "williams_exit must be between oversold and overbought thresholds"
            )
        if self.trend_buffer_pct < 0:
            raise ValueError("trend_buffer_pct must be non-negative")
        if self.min_volume_ratio <= 0:
            raise ValueError("min_volume_ratio must be positive")
        if self.exit_retrace_from_high_pct < 0:
            raise ValueError("exit_retrace_from_high_pct must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class ConsensusVote:
    """Single indicator vote in the consensus model."""

    name: str
    side: str
    score: float
    value: float | None = None
    reason: str = ""
    category: str = "indicator"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "side": self.side,
            "score": round(self.score, 4),
            "value": None if self.value is None else round(self.value, 4),
            "reason": self.reason,
            "category": self.category,
        }


@dataclass(frozen=True)
class TechnicalConsensus:
    """Entry/exit vote result for a single stock snapshot."""

    entry_votes: list[ConsensusVote] = field(default_factory=list)
    exit_votes: list[ConsensusVote] = field(default_factory=list)
    entry_signal: bool = False
    exit_signal: bool = False
    entry_score: float = 0.0
    exit_score: float = 0.0
    recommendation: str = "hold"
    summary: str = ""

    @property
    def entry_vote_count(self) -> int:
        return len(self.entry_votes)

    @property
    def exit_vote_count(self) -> int:
        return len(self.exit_votes)

    @property
    def entry_core_vote_count(self) -> int:
        return _core_vote_count(self.entry_votes)

    @property
    def exit_core_vote_count(self) -> int:
        return _core_vote_count(self.exit_votes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_signal": self.entry_signal,
            "exit_signal": self.exit_signal,
            "entry_vote_count": self.entry_vote_count,
            "exit_vote_count": self.exit_vote_count,
            "entry_core_vote_count": self.entry_core_vote_count,
            "exit_core_vote_count": self.exit_core_vote_count,
            "entry_score": round(self.entry_score, 4),
            "exit_score": round(self.exit_score, 4),
            "recommendation": self.recommendation,
            "summary": self.summary,
            "entry_votes": [v.to_dict() for v in self.entry_votes],
            "exit_votes": [v.to_dict() for v in self.exit_votes],
        }


def build_technical_consensus(
    indicators: Mapping[str, Any],
    market_data: Mapping[str, Any] | None = None,
    *,
    position: Any | None = None,
    config: TechnicalConsensusConfig | Mapping[str, Any] | None = None,
) -> TechnicalConsensus:
    """Build entry/exit consensus from current and previous indicators."""

    cfg = (
        config
        if isinstance(config, TechnicalConsensusConfig)
        else TechnicalConsensusConfig.from_dict(config)
    )
    current = _Snapshot(indicators=indicators, market_data=market_data or {})

    entry_votes = _entry_votes(current, cfg)
    exit_votes = _exit_votes(current, cfg, position)
    entry_core_votes = _core_vote_count(entry_votes)
    exit_core_votes = _core_vote_count(exit_votes)

    entry_score = _score_votes(entry_votes, cfg.min_entry_votes)
    exit_score = _score_votes(exit_votes, cfg.min_exit_votes)
    exit_signal = (
        len(exit_votes) >= cfg.min_exit_votes
        and exit_core_votes >= cfg.min_exit_core_votes
    )
    entry_signal = (
        len(entry_votes) >= cfg.min_entry_votes
        and entry_core_votes >= cfg.min_entry_core_votes
        and not exit_signal
    )

    if exit_signal:
        recommendation = "exit_candidate"
    elif entry_signal:
        recommendation = "entry_candidate"
    else:
        recommendation = "hold"

    summary = (
        f"entry_votes={len(entry_votes)}/{cfg.min_entry_votes} "
        f"entry_core={entry_core_votes}/{cfg.min_entry_core_votes} "
        f"exit_votes={len(exit_votes)}/{cfg.min_exit_votes} "
        f"exit_core={exit_core_votes}/{cfg.min_exit_core_votes} "
        f"recommendation={recommendation}"
    )
    return TechnicalConsensus(
        entry_votes=entry_votes,
        exit_votes=exit_votes,
        entry_signal=entry_signal,
        exit_signal=exit_signal,
        entry_score=entry_score,
        exit_score=exit_score,
        recommendation=recommendation,
        summary=summary,
    )


def build_technical_consensus_from_ohlcv(
    df: Any,
    *,
    config: TechnicalConsensusConfig | Mapping[str, Any] | None = None,
    volume_lookback: int = 20,
) -> TechnicalConsensus:
    """Calculate indicators from an OHLCV DataFrame and return consensus.

    Supports both English OHLCV columns and KRX/KIS Korean columns used by the
    stock analyzer.
    """

    if df is None or len(df) < 2:
        return build_technical_consensus({}, {}, config=config)

    from shared.indicators.momentum import calculate_all_momentum

    work = _normalize_ohlcv_frame(df)
    work = calculate_all_momentum(work, include_obv=False)
    work["ma20"] = work["close"].rolling(window=20, min_periods=1).mean()
    work["volume_avg"] = (
        work["volume"]
        .shift(1)
        .rolling(window=max(1, int(volume_lookback)), min_periods=1)
        .mean()
    )

    last = work.iloc[-1]
    prev = work.iloc[-2]
    avg_volume = _as_float(last.get("volume_avg"), 0.0) or 0.0
    volume = _as_float(last.get("volume"), 0.0) or 0.0
    volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0

    snapshot = {
        "close": _as_float(last.get("close")),
        "ma20": _as_float(last.get("ma20")),
        "rsi": _as_float(last.get("rsi")),
        "prev_rsi": _as_float(prev.get("rsi")),
        "macd_hist": _as_float(last.get("macd_oscillator")),
        "prev_macd_hist": _as_float(prev.get("macd_oscillator")),
        "williams_r": _as_float(last.get("williams_r")),
        "prev_williams_r": _as_float(prev.get("williams_r")),
        "volume_ratio": volume_ratio,
    }
    return build_technical_consensus(snapshot, config=config)


@dataclass
class _Snapshot:
    indicators: Mapping[str, Any]
    market_data: Mapping[str, Any]

    def value(self, *keys: str) -> float | None:
        for source in (self.indicators, self.market_data):
            value = _lookup(source, *keys)
            if value is not None:
                return _as_float(value)
        return None


def _entry_votes(
    snapshot: _Snapshot,
    config: TechnicalConsensusConfig,
) -> list[ConsensusVote]:
    votes: list[ConsensusVote] = []
    wr = snapshot.value("williams_r", "wr")
    prev_wr = snapshot.value("prev_williams_r", "williams_r_prev", "prev_wr")
    rsi = snapshot.value("rsi")
    prev_rsi = snapshot.value("prev_rsi", "rsi_prev")
    macd_hist = snapshot.value("macd_hist", "macd_oscillator")
    prev_macd_hist = snapshot.value(
        "prev_macd_hist",
        "macd_hist_prev",
        "prev_macd_oscillator",
        "macd_oscillator_prev",
    )

    if (
        wr is not None
        and prev_wr is not None
        and prev_wr <= config.williams_oversold
        and wr >= config.williams_reversal
    ):
        votes.append(
            ConsensusVote(
                name="williams_r_reversal",
                side="entry",
                score=1.0,
                value=wr,
                reason="Williams %R recovered from oversold",
            )
        )

    if (
        rsi is not None
        and prev_rsi is not None
        and prev_rsi <= config.rsi_oversold
        and rsi >= config.rsi_recovery
    ):
        votes.append(
            ConsensusVote(
                name="rsi_recovery",
                side="entry",
                score=1.0,
                value=rsi,
                reason="RSI recovered from oversold",
            )
        )

    if (
        macd_hist is not None
        and prev_macd_hist is not None
        and prev_macd_hist <= config.macd_hist_threshold
        and macd_hist > config.macd_hist_threshold
    ):
        votes.append(
            ConsensusVote(
                name="macd_hist_cross_up",
                side="entry",
                score=1.0,
                value=macd_hist,
                reason="MACD histogram crossed above threshold",
            )
        )

    if config.include_trend_vote:
        close = snapshot.value("close", "price", "current_price", "last_price", "종가")
        anchor = snapshot.value("ma20", "bb_middle", "vwap")
        if close is not None and anchor is not None and close > anchor * (
            1 + config.trend_buffer_pct
        ):
            votes.append(
                ConsensusVote(
                    name="trend_anchor_reclaim",
                    side="entry",
                    score=0.75,
                    value=close,
                    reason="Price is above trend anchor",
                    category="context",
                )
            )

    if config.include_volume_vote:
        volume_ratio = snapshot.value("volume_ratio", "rvol", "relative_volume")
        if volume_ratio is not None and volume_ratio >= config.min_volume_ratio:
            votes.append(
                ConsensusVote(
                    name="relative_volume_confirm",
                    side="entry",
                    score=0.5,
                    value=volume_ratio,
                    reason="Relative volume confirms move",
                    category="context",
                )
            )

    return votes


def _exit_votes(
    snapshot: _Snapshot,
    config: TechnicalConsensusConfig,
    position: Any | None,
) -> list[ConsensusVote]:
    votes: list[ConsensusVote] = []
    wr = snapshot.value("williams_r", "wr")
    prev_wr = snapshot.value("prev_williams_r", "williams_r_prev", "prev_wr")
    rsi = snapshot.value("rsi")
    prev_rsi = snapshot.value("prev_rsi", "rsi_prev")
    macd_hist = snapshot.value("macd_hist", "macd_oscillator")
    prev_macd_hist = snapshot.value(
        "prev_macd_hist",
        "macd_hist_prev",
        "prev_macd_oscillator",
        "macd_oscillator_prev",
    )

    if (
        wr is not None
        and prev_wr is not None
        and prev_wr >= config.williams_overbought
        and wr <= config.williams_exit
    ):
        votes.append(
            ConsensusVote(
                name="williams_r_rollover",
                side="exit",
                score=1.0,
                value=wr,
                reason="Williams %R rolled over from overbought",
            )
        )

    if (
        rsi is not None
        and prev_rsi is not None
        and prev_rsi >= config.rsi_overbought
        and rsi <= config.rsi_rollover
    ):
        votes.append(
            ConsensusVote(
                name="rsi_rollover",
                side="exit",
                score=1.0,
                value=rsi,
                reason="RSI rolled over from overbought",
            )
        )

    if (
        macd_hist is not None
        and prev_macd_hist is not None
        and prev_macd_hist >= config.macd_hist_threshold
        and macd_hist < config.macd_hist_threshold
    ):
        votes.append(
            ConsensusVote(
                name="macd_hist_cross_down",
                side="exit",
                score=1.0,
                value=macd_hist,
                reason="MACD histogram crossed below threshold",
            )
        )

    if config.include_trend_vote:
        close = snapshot.value("close", "price", "current_price", "last_price", "종가")
        anchor = snapshot.value("ma20", "bb_middle", "vwap")
        if close is not None and anchor is not None and close < anchor * (
            1 - config.trend_buffer_pct
        ):
            votes.append(
                ConsensusVote(
                    name="trend_anchor_break",
                    side="exit",
                    score=0.75,
                    value=close,
                    reason="Price broke below trend anchor",
                    category="context",
                )
            )

    close = snapshot.value("close", "price", "current_price", "last_price", "종가")
    high_since_entry = _position_high(position)
    high_since_entry = snapshot.value(
        "high_since_entry", "highest_price", "day_high"
    ) or high_since_entry
    if (
        close is not None
        and high_since_entry is not None
        and high_since_entry > 0
        and (high_since_entry - close) / high_since_entry
        >= config.exit_retrace_from_high_pct
    ):
        votes.append(
            ConsensusVote(
                name="high_retrace",
                side="exit",
                score=0.5,
                value=(high_since_entry - close) / high_since_entry,
                reason="Price retraced from favorable high",
                category="context",
            )
        )

    return votes


def _score_votes(votes: list[ConsensusVote], minimum_votes: int) -> float:
    if not votes:
        return 0.0
    return min(1.0, sum(v.score for v in votes) / max(1, minimum_votes))


def _core_vote_count(votes: list[ConsensusVote]) -> int:
    return sum(1 for vote in votes if vote.category == "indicator")


def _lookup(data: Mapping[str, Any], *keys: str) -> Any | None:
    for key in keys:
        if key in data:
            return data[key]

    for nested_key in ("momentum_5m", "momentum", "technical", "indicators"):
        nested = data.get(nested_key)
        if isinstance(nested, Mapping):
            value = _lookup(nested, *keys)
            if value is not None:
                return value
    return None


def _as_float(value: Any, default: float | None = None) -> float | None:
    if value is None or isinstance(value, bool):
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(result):
        return default
    return result


def _position_high(position: Any | None) -> float | None:
    if position is None:
        return None
    return _as_float(getattr(position, "highest_price", None))


def _normalize_ohlcv_frame(df: Any) -> Any:
    import pandas as pd

    close = _column(df, "close", "종가")
    high = _column(df, "high", "고가", default=close)
    low = _column(df, "low", "저가", default=close)
    open_ = _column(df, "open", "시가", default=close)
    volume = _column(df, "volume", "거래량", default=0.0)

    return pd.DataFrame(
        {
            "open": pd.to_numeric(open_, errors="coerce").ffill().bfill(),
            "high": pd.to_numeric(high, errors="coerce").ffill().bfill(),
            "low": pd.to_numeric(low, errors="coerce").ffill().bfill(),
            "close": pd.to_numeric(close, errors="coerce").ffill().bfill(),
            "volume": pd.to_numeric(volume, errors="coerce").fillna(0.0),
        },
        index=df.index,
    )


def _column(df: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if name in df.columns:
            return df[name]
    if default is not None:
        return default
    raise KeyError(f"Missing OHLCV column: {names}")
