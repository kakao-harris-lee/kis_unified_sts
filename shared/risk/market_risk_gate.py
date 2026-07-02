"""Market Risk Gate — shared ENTRY-gate evaluator over ``market:risk:latest``.

Unified investment roadmap Phase 2A (§4.2 reaction matrix, §5.1 track B,
§5.2 track C). Reads the Phase 1 market-risk hash published by
``services/market_risk_engine`` on Redis DB 1 (fields: ``score``,
``score_ema3``, ``band``, ``regime``, ``degraded``, ``coverage_ratio``,
``missing_components``, ``asof_ts`` KST-naive ISO, ``kind``, ``components``)
and turns the confirmed band into an entry directive shared by the stock
M4-P pipeline, the futures decision_engine, and the dashboard lanes.

Scope and invariants:

- ENTRY ONLY. This gate applies exclusively to NEW entries and must never be
  wired into exit paths — stock swing exits stay signal-driven (no blanket
  EOD liquidation) and futures exits are untouched (roadmap §4.2).
- Direction symmetry: the caller's ``signal_direction`` decides long/short;
  the gate receives ``side`` and only answers allow/size for that side. The
  reaction matrix carries no short-block rule except the CRITICAL full stop
  (roadmap §5.2 long/short symmetry).
- Fail-open (RegimeGate P2-③ precedent): missing hash, parse failure,
  ``degraded=true``, stale ``asof_ts``, unknown asset/side/band, or
  ``mode: off`` all yield ``allow=True, would_block=False, size_factor=1.0``
  with a machine-readable ``fail_open:*`` reason.
  :func:`evaluate_market_risk_gate` never raises into the caller.
- Mode semantics: in ``shadow`` the rule verdict is reported via
  ``would_block``/``reason`` but ``allow`` stays True; only ``enforce`` may
  return ``allow=False``. ``size_factor``/``min_confidence`` always carry
  the matrix cell values whenever the matrix was evaluated
  (mode-independent, for shadow observability) — callers must apply them
  only when ``mode == "enforce"``.

Every band rule, size factor, staleness bound, and mode lives in
``config/market_risk_gate.yaml`` (:class:`MarketRiskGateConfig`). The code
defaults below are a mirror of that shipped file (fallback when the YAML is
absent), not an alternative source of truth.

Naming: this consumes the composite ``market_risk_score`` band — distinct
from the LLM ``MarketContext.risk_score`` static RiskMode mapping (roadmap
O8).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field, model_validator

from shared.config.base import ServiceConfigBase
from shared.config.loader import ConfigNotFoundError
from shared.risk.market_risk_score import KST

logger = logging.getLogger(__name__)

__all__ = [
    "MarketRiskGateBandRule",
    "MarketRiskGateConfig",
    "MarketRiskGateDecision",
    "MarketRiskGateRedisSettings",
    "evaluate_market_risk_gate",
    "gate_trace_payload",
]

# Redis hash field names — fixed Phase 1 §4.3 publication contract
# (services/market_risk_engine.publish_result), not tunables.
_FIELD_SCORE = "score"
_FIELD_BAND = "band"
_FIELD_REGIME = "regime"
_FIELD_DEGRADED = "degraded"
_FIELD_ASOF = "asof_ts"

# Side literals — fixed contract with signal_direction, not tunables.
_SIDE_LONG = "long"
_SIDE_SHORT = "short"


# ---------------------------------------------------------------------------
# Configuration (config/market_risk_gate.yaml)
# ---------------------------------------------------------------------------


class MarketRiskGateBandRule(BaseModel):
    """One reaction-matrix cell (asset x band) — NEW-entry rule for a side."""

    allow_long: bool = Field(default=True)
    allow_short: bool = Field(default=True)
    size_factor: float = Field(default=1.0, gt=0.0, le=1.0)
    min_confidence: str | None = Field(default=None)


def _default_assets() -> dict[str, dict[str, MarketRiskGateBandRule]]:
    """Mirror of the shipped config/market_risk_gate.yaml assets section."""
    rule = MarketRiskGateBandRule
    return {
        # Track B (stock): long-only in practice; no short-block rules by
        # design — the CRITICAL full stop is the only both-side block.
        "stock": {
            "LOW": rule(),
            "NEUTRAL": rule(),
            "ELEVATED": rule(min_confidence="HIGH"),
            "HIGH": rule(allow_long=False),
            "CRITICAL": rule(allow_long=False, allow_short=False),
        },
        # Track C (futures): direction stays with signal_direction; the gate
        # only adjusts allow/size per side.
        "futures": {
            "LOW": rule(size_factor=1.0),
            "NEUTRAL": rule(size_factor=1.0),
            "ELEVATED": rule(size_factor=0.7),
            "HIGH": rule(allow_long=False, allow_short=True, size_factor=0.5),
            "CRITICAL": rule(allow_long=False, allow_short=False),
        },
    }


class MarketRiskGateRedisSettings(BaseModel):
    """Where the Phase 1 engine publishes the latest hash (Redis DB 1)."""

    latest_key: str = Field(default="market:risk:latest")


class MarketRiskGateConfig(ServiceConfigBase):
    """Top-level config loaded from ``config/market_risk_gate.yaml``."""

    _default_config_file: ClassVar[str] = "market_risk_gate.yaml"

    mode: Literal["off", "shadow", "enforce"] = Field(default="shadow")
    staleness_max_age_seconds: int = Field(default=21600, gt=0)
    redis: MarketRiskGateRedisSettings = Field(
        default_factory=MarketRiskGateRedisSettings
    )
    assets: dict[str, dict[str, MarketRiskGateBandRule]] = Field(
        default_factory=_default_assets
    )

    @model_validator(mode="after")
    def _validate_assets(self) -> MarketRiskGateConfig:
        if not self.assets:
            raise ValueError("assets must not be empty")
        for asset, bands in self.assets.items():
            if not bands:
                raise ValueError(f"assets[{asset!r}] must define at least one band")
        return self

    @classmethod
    def load_or_default(cls, path: str | None = None) -> MarketRiskGateConfig:
        """Load from YAML when available, otherwise return validated defaults."""
        try:
            return cls.from_yaml(path)
        except ConfigNotFoundError:
            return cls()


# ---------------------------------------------------------------------------
# Decision (fixed contract with the M4-P / decision_engine / dashboard lanes)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MarketRiskGateDecision:
    """Entry-gate verdict for one (asset, side) evaluation.

    ``allow`` is False only when ``mode == "enforce"`` and the matrix rule
    blocks the requested side. ``would_block`` is the mode-independent rule
    verdict (shadow observation). ``size_factor``/``min_confidence`` report
    the matrix cell whenever it was evaluated (1.0/None on every fail-open
    path); callers apply them only in enforce mode. ``reason`` is
    machine-readable: ``market_risk band=... score=... rule=...`` for matrix
    verdicts, ``fail_open:*`` otherwise.
    """

    allow: bool  # enforce mode + blocking rule → False; True otherwise
    would_block: bool  # rule verdict regardless of mode (shadow observation)
    size_factor: float  # matrix size factor (1.0 default / on fail-open)
    min_confidence: str | None  # e.g. "HIGH" at ELEVATED (stock)
    reason: str  # e.g. "market_risk band=HIGH score=74.2 rule=block_new_long"
    band: str | None
    score: float | None
    regime: str | None
    degraded: bool
    stale: bool
    mode: str  # "off" | "shadow" | "enforce"


def gate_trace_payload(decision: MarketRiskGateDecision) -> dict[str, Any]:
    """Serialize a decision for trace/signal metadata (fixed key contract)."""
    return {
        "mode": decision.mode,
        "band": decision.band,
        "score": decision.score,
        "regime": decision.regime,
        "would_block": decision.would_block,
        "allow": decision.allow,
        "size_factor": decision.size_factor,
        "min_confidence": decision.min_confidence,
        "reason": decision.reason,
        "degraded": decision.degraded,
        "stale": decision.stale,
    }


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def evaluate_market_risk_gate(
    redis: Any,
    config: MarketRiskGateConfig,
    *,
    asset: str,  # "stock" | "futures"
    side: str,  # "long" | "short"
    now: datetime | None = None,
) -> MarketRiskGateDecision:
    """Evaluate the market-risk ENTRY gate for one (asset, side).

    Never raises: any unexpected failure degrades to a fail-open decision
    (``allow=True``) so the gate can never break an entry path outright.
    ``now`` defaults to the current KST-naive wall clock; aware datetimes
    are converted to KST and stripped before the staleness comparison.
    """
    try:
        return _evaluate(redis, config, asset=asset, side=side, now=now)
    except Exception as exc:  # the gate must never propagate into callers
        logger.warning("market_risk_gate: unexpected failure, failing open: %s", exc)
        mode = getattr(config, "mode", "shadow")
        return _fail_open(mode, f"fail_open:error:{type(exc).__name__}")


def _evaluate(
    redis: Any,
    config: MarketRiskGateConfig,
    *,
    asset: str,
    side: str,
    now: datetime | None,
) -> MarketRiskGateDecision:
    mode = config.mode
    if mode == "off":
        return _fail_open(mode, "fail_open:mode_off")

    asset_key = str(asset).strip().lower()
    band_rules = config.assets.get(asset_key)
    if band_rules is None:
        return _fail_open(mode, f"fail_open:unknown_asset:{asset_key}")

    side_key = str(side).strip().lower()
    if side_key not in (_SIDE_LONG, _SIDE_SHORT):
        return _fail_open(mode, f"fail_open:invalid_side:{side_key}")

    try:
        raw = redis.hgetall(config.redis.latest_key)
    except Exception as exc:
        logger.warning("market_risk_gate: redis read failed, failing open: %s", exc)
        return _fail_open(mode, f"fail_open:redis_error:{type(exc).__name__}")

    fields = _decode_hash(raw)
    if not fields:
        return _fail_open(mode, "fail_open:missing")

    band = fields.get(_FIELD_BAND, "").strip() or None
    score = _parse_float(fields.get(_FIELD_SCORE))
    regime = fields.get(_FIELD_REGIME, "").strip() or None
    degraded = fields.get(_FIELD_DEGRADED, "").strip().lower() == "true"

    asof = _parse_asof(fields.get(_FIELD_ASOF))
    if asof is None:
        return _fail_open(
            mode,
            "fail_open:invalid_asof",
            band=band,
            score=score,
            regime=regime,
            degraded=degraded,
        )

    reference = _kst_naive(now) if now is not None else _now_kst()
    age_seconds = (reference - asof).total_seconds()
    stale = age_seconds > config.staleness_max_age_seconds

    if band is None:
        return _fail_open(
            mode,
            "fail_open:invalid_band",
            score=score,
            regime=regime,
            degraded=degraded,
            stale=stale,
        )
    if degraded:
        return _fail_open(
            mode,
            "fail_open:degraded",
            band=band,
            score=score,
            regime=regime,
            degraded=True,
            stale=stale,
        )
    if stale:
        return _fail_open(
            mode,
            (
                f"fail_open:stale age_seconds={age_seconds:.0f}"
                f">max_age={config.staleness_max_age_seconds}"
            ),
            band=band,
            score=score,
            regime=regime,
            stale=True,
        )

    rule = band_rules.get(band)
    if rule is None:
        return _fail_open(
            mode,
            f"fail_open:unknown_band:{band}",
            band=band,
            score=score,
            regime=regime,
        )

    blocked = not (rule.allow_long if side_key == _SIDE_LONG else rule.allow_short)
    score_text = "na" if score is None else f"{score:.1f}"
    reason = (
        f"market_risk band={band} score={score_text}"
        f" rule={_rule_label(rule, side_key, blocked)}"
    )
    return MarketRiskGateDecision(
        allow=not (blocked and mode == "enforce"),
        would_block=blocked,
        size_factor=rule.size_factor,
        min_confidence=rule.min_confidence,
        reason=reason,
        band=band,
        score=score,
        regime=regime,
        degraded=False,
        stale=False,
        mode=mode,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fail_open(
    mode: str,
    reason: str,
    *,
    band: str | None = None,
    score: float | None = None,
    regime: str | None = None,
    degraded: bool = False,
    stale: bool = False,
) -> MarketRiskGateDecision:
    """Pass-through decision: size_factor 1.0 is the neutral multiplier."""
    return MarketRiskGateDecision(
        allow=True,
        would_block=False,
        size_factor=1.0,
        min_confidence=None,
        reason=reason,
        band=band,
        score=score,
        regime=regime,
        degraded=degraded,
        stale=stale,
        mode=mode,
    )


def _rule_label(rule: MarketRiskGateBandRule, side: str, blocked: bool) -> str:
    """Machine-readable label of the matrix cell verdict for ``reason``."""
    if blocked:
        if not rule.allow_long and not rule.allow_short:
            return "block_all_entries"
        return "block_new_long" if side == _SIDE_LONG else "block_new_short"
    parts: list[str] = []
    if rule.min_confidence:
        parts.append(f"min_confidence:{rule.min_confidence}")
    if rule.size_factor != 1.0:
        parts.append(f"size_factor:{rule.size_factor:g}")
    return ",".join(parts) if parts else "allow"


def _decode_hash(raw: Any) -> dict[str, str]:
    """Normalize hgetall output to str→str (bytes clients included)."""
    if not raw:
        return {}
    fields: dict[str, str] = {}
    for key, value in dict(raw).items():
        name = (
            key.decode("utf-8", "replace")
            if isinstance(key, bytes | bytearray)
            else str(key)
        )
        fields[name] = (
            value.decode("utf-8", "replace")
            if isinstance(value, bytes | bytearray)
            else str(value)
        )
    return fields


def _parse_float(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _parse_asof(value: str | None) -> datetime | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    return _kst_naive(parsed)


def _kst_naive(ts: datetime) -> datetime:
    """KST-native comparison basis (CLAUDE.md timezone rule)."""
    if ts.tzinfo is not None:
        return ts.astimezone(KST).replace(tzinfo=None)
    return ts


def _now_kst() -> datetime:
    return datetime.now(KST).replace(tzinfo=None)
