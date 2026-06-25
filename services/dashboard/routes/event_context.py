"""Event-context diagnostics for Setup C observability."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from services.dashboard.routes.trading import _normalize_asset_class
from shared.decision.context import ScheduledEvent, load_scheduled_events
from shared.decision.setups.event_reaction import SetupCConfig

router = APIRouter(prefix="/api/event-context", tags=["event-context"])

KST = ZoneInfo("Asia/Seoul")
_REPO_ROOT = Path(__file__).resolve().parents[3]
_FORECAST_EVENT_LATEST_KEY = os.environ.get(
    "FORECAST_EVENT_LATEST_KEY", "forecast:event:latest"
)
_NEWS_RAW_STREAM = os.environ.get("NEWS_RAW_STREAM", "stream:news.raw")
_NEWS_SCORED_STREAM = os.environ.get("NEWS_SCORED_STREAM", "stream:news.scored")
_MACRO_OVERNIGHT_STREAM = os.environ.get(
    "MACRO_OVERNIGHT_STREAM", "stream:macro.overnight"
)
_SCHEDULED_EVENTS_PATH = os.environ.get(
    "SCHEDULED_EVENTS_PATH", "config/scheduled_events.yaml"
)
_SETUP_C_STRATEGY_CONFIG_PATH = os.environ.get(
    "SETUP_C_STRATEGY_CONFIG_PATH",
    "config/strategies/futures/setup_c_event_reaction.yaml",
)
_SETUP_EVAL_KEY = os.environ.get("SETUP_EVAL_KEY", "trading:futures:setup_eval")
_SETUP_C_FIELD = "setup_c_event_reaction"
_STALE_STREAM_SECONDS = int(os.environ.get("EVENT_CONTEXT_STALE_STREAM_SECONDS", "3600"))
_SETUP_EVAL_STALE_SECONDS = int(
    os.environ.get("EVENT_CONTEXT_SETUP_EVAL_STALE_SECONDS", "900")
)
_SOURCE_SAMPLE_LIMIT = int(os.environ.get("EVENT_CONTEXT_SOURCE_SAMPLE_LIMIT", "3"))


class EventScoreSummary(BaseModel):
    """Freshness and sparsity summary for the latest event score."""

    available: bool
    status: str
    latest_at: datetime | None = None
    age_seconds: int | None = None
    ttl_minutes: int | None = None
    impact_score: float | None = None
    impact_tier: int | None = None
    event_type: str | None = None
    source: str | None = None
    sparse: bool
    recent_count: int
    # Tier → count histogram for the latest event (single-entry off the
    # `:latest` key). Surfaces "T2: 1" on the dashboard instead of
    # "impact tiers unavailable".
    by_impact_tier: dict[str, int] = Field(default_factory=dict)
    missing_evidence: list[str] = Field(default_factory=list)


class EventSourceStatus(BaseModel):
    """One diagnostic row for an event/news/macro source."""

    name: str
    kind: str
    key: str | None = None
    available: bool
    status: str
    count: int | None = None
    latest_at: datetime | None = None
    age_seconds: int | None = None
    detail: str | None = None
    sample: list[dict[str, Any]] = Field(default_factory=list)


class SetupEvalSummary(BaseModel):
    """Latest runtime Setup C evaluation from the adapter hash."""

    available: bool
    status: str
    outcome: str | None = None
    reason: str | None = None
    latest_at: datetime | None = None
    age_seconds: int | None = None
    missing_evidence: list[str] = Field(default_factory=list)


class SetupCEventRow(BaseModel):
    """Scheduled-event row relevant to Setup C."""

    event_id: str
    event_type: str
    scheduled_at: datetime
    impact_tier: int
    elapsed_minutes: float | None = None
    qualifies_window: bool


class SetupCDiagnostics(BaseModel):
    """Root-cause summary for Setup C no-signal investigation."""

    enabled: bool
    window_minutes: int
    min_impact_tier: int
    candidate_count: int
    scheduled_events_total: int
    scheduled_events_in_window: int
    blocked_reasons: dict[str, int] = Field(default_factory=dict)
    missing_event_sources: list[str] = Field(default_factory=list)
    root_cause: str
    recent_events: list[SetupCEventRow] = Field(default_factory=list)


class EventContextDiagnosticsResponse(BaseModel):
    """Response body for event-context diagnostics."""

    status: str
    asset_class: str
    generated_at: datetime
    event_score: EventScoreSummary
    setup_eval: SetupEvalSummary
    source_timeline: list[EventSourceStatus]
    setup_c: SetupCDiagnostics
    config_warnings: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def _get_redis_client():
    try:
        from shared.streaming.client import RedisClient

        return RedisClient.get_client()
    except Exception:  # noqa: BLE001 - dashboard must stay resilient
        return None


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else _REPO_ROOT / p


def _decode(raw: Any) -> Any:
    if isinstance(raw, bytes):
        return raw.decode(errors="ignore")
    return raw


def _decode_fields(fields: dict[Any, Any]) -> dict[str, Any]:
    return {str(_decode(k)): _decode(v) for k, v in fields.items()}


def _parse_epoch_ms(raw: Any) -> datetime | None:
    try:
        value = int(float(str(raw)))
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return datetime.fromtimestamp(value / 1000, tz=UTC)


def _coerce_int(raw: Any, *, default: int = 0) -> int:
    try:
        return int(float(str(raw)))
    except (TypeError, ValueError):
        return default


def _coerce_float(raw: Any) -> float | None:
    try:
        return float(str(raw))
    except (TypeError, ValueError):
        return None


def _parse_datetime(raw: Any) -> datetime | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        dt = raw
    else:
        text = str(_decode(raw)).strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return _parse_epoch_ms(text)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _stream_id_timestamp(entry_id: Any) -> datetime | None:
    text = str(_decode(entry_id))
    head = text.split("-", maxsplit=1)[0]
    return _parse_epoch_ms(head)


def _entry_timestamp(entry_id: Any, fields: dict[str, Any]) -> datetime | None:
    for key in (
        "ts_ms",
        "published_at_ms",
        "created_at_ms",
        "timestamp_ms",
        "asof_ms",
    ):
        ts = _parse_epoch_ms(fields.get(key))
        if ts is not None:
            return ts
    for key in (
        "asof",
        "timestamp",
        "created_at",
        "published_at",
        "collected_at",
        "scored_at",
    ):
        ts = _parse_datetime(fields.get(key))
        if ts is not None:
            return ts
    return _stream_id_timestamp(entry_id)


def _age_seconds(now: datetime, ts: datetime | None) -> int | None:
    if ts is None:
        return None
    return max(0, int((now - ts.astimezone(UTC)).total_seconds()))


def _latest_stream_entries(redis: Any, key: str, count: int) -> list[tuple[Any, dict[str, Any]]]:
    if redis is None:
        return []
    try:
        entries = redis.xrevrange(key, count=count)
    except Exception:  # noqa: BLE001
        return []
    decoded: list[tuple[Any, dict[str, Any]]] = []
    for entry_id, fields in entries or []:
        if isinstance(fields, dict):
            decoded.append((_decode(entry_id), _decode_fields(fields)))
    return decoded


def _stream_count(redis: Any, key: str, fallback: int) -> int:
    try:
        return int(redis.xlen(key))
    except Exception:  # noqa: BLE001
        return fallback


def _source_from_stream(
    redis: Any,
    *,
    name: str,
    key: str,
    now: datetime,
) -> EventSourceStatus:
    if redis is None:
        return EventSourceStatus(
            name=name,
            kind="redis_stream",
            key=key,
            available=False,
            status="unavailable",
            detail="redis_unavailable",
        )

    entries = _latest_stream_entries(redis, key, max(1, _SOURCE_SAMPLE_LIMIT))
    if not entries:
        return EventSourceStatus(
            name=name,
            kind="redis_stream",
            key=key,
            available=False,
            status="empty",
            count=0,
        )

    latest_id, latest_fields = entries[0]
    latest_at = _entry_timestamp(latest_id, latest_fields)
    age = _age_seconds(now, latest_at)
    status = "ok" if age is None or age <= _STALE_STREAM_SECONDS else "stale"
    count = _stream_count(redis, key, fallback=len(entries))
    sample = [
        {
            "id": str(entry_id),
            "timestamp": _entry_timestamp(entry_id, fields),
            "fields": sorted(fields.keys())[:12],
        }
        for entry_id, fields in entries
    ]
    return EventSourceStatus(
        name=name,
        kind="redis_stream",
        key=key,
        available=True,
        status=status,
        count=count,
        latest_at=latest_at,
        age_seconds=age,
        sample=sample,
    )


def _source_from_event_score(
    score: EventScoreSummary,
) -> EventSourceStatus:
    return EventSourceStatus(
        name="forecast_event_latest",
        kind="redis_key",
        key=_FORECAST_EVENT_LATEST_KEY,
        available=score.available,
        status=score.status,
        count=score.recent_count,
        latest_at=score.latest_at,
        age_seconds=score.age_seconds,
        detail=score.event_type,
        sample=[
            {
                "event_type": score.event_type,
                "impact_score": score.impact_score,
                "impact_tier": score.impact_tier,
                "source": score.source,
                "ttl_minutes": score.ttl_minutes,
            }
        ]
        if score.available
        else [],
    )


def _source_from_setup_eval(setup_eval: SetupEvalSummary) -> EventSourceStatus:
    return EventSourceStatus(
        name="setup_c_latest_eval",
        kind="redis_hash",
        key=_SETUP_EVAL_KEY,
        available=setup_eval.available,
        status=setup_eval.status,
        count=1 if setup_eval.available else 0,
        latest_at=setup_eval.latest_at,
        age_seconds=setup_eval.age_seconds,
        detail=setup_eval.reason,
        sample=[
            {
                "field": _SETUP_C_FIELD,
                "outcome": setup_eval.outcome,
                "reason": setup_eval.reason,
            }
        ]
        if setup_eval.available
        else [],
    )


def _event_score_summary(redis: Any, now: datetime) -> EventScoreSummary:
    raw = None
    if redis is not None:
        try:
            raw = redis.get(_FORECAST_EVENT_LATEST_KEY)
        except Exception:  # noqa: BLE001
            raw = None

    if raw is None:
        return EventScoreSummary(
            available=False,
            status="missing",
            sparse=True,
            recent_count=0,
            missing_evidence=["forecast_event_latest"],
        )

    payload = _decode_json_object(raw)
    if payload is None:
        return EventScoreSummary(
            available=False,
            status="invalid",
            sparse=True,
            recent_count=0,
            missing_evidence=["forecast_event_latest_invalid"],
        )

    asof = _parse_datetime(payload.get("asof"))
    age = _age_seconds(now, asof)
    ttl_minutes = _coerce_int(payload.get("ttl_minutes"), default=0)
    if asof is None or ttl_minutes <= 0:
        return EventScoreSummary(
            available=False,
            status="invalid",
            sparse=True,
            recent_count=0,
            missing_evidence=["forecast_event_latest_invalid"],
        )
    ttl_seconds = ttl_minutes * 60
    status = "fresh" if age is not None and age <= ttl_seconds else "stale"
    # Surface the latest event's tier as a single-entry histogram. Pre-tier
    # payloads (impact_tier absent → 0) yield an empty histogram, leaving the
    # dashboard's "impact tiers unavailable" fallback intact.
    impact_tier = _coerce_int(payload.get("impact_tier"), default=0)
    tier = impact_tier if impact_tier in (1, 2, 3) else None
    by_impact_tier = {str(tier): 1} if tier is not None else {}
    return EventScoreSummary(
        available=True,
        status=status,
        latest_at=asof,
        age_seconds=age,
        ttl_minutes=ttl_minutes or None,
        impact_score=_coerce_float(payload.get("impact_score")),
        impact_tier=tier,
        event_type=str(payload.get("event_type")) if payload.get("event_type") else None,
        source=str(payload.get("source")) if payload.get("source") else None,
        sparse=True,
        recent_count=1,
        by_impact_tier=by_impact_tier,
        missing_evidence=[] if status == "fresh" else ["forecast_event_latest_stale"],
    )


def _decode_json_object(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode(errors="ignore")
    if isinstance(raw, dict):
        return raw
    try:
        payload = json.loads(str(raw))
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _setup_eval_summary(redis: Any, now: datetime) -> SetupEvalSummary:
    if redis is None:
        return SetupEvalSummary(
            available=False,
            status="unavailable",
            missing_evidence=["setup_c_latest_eval"],
        )
    raw = None
    try:
        raw = redis.hget(_SETUP_EVAL_KEY, _SETUP_C_FIELD)
    except Exception:  # noqa: BLE001
        raw = None
    if raw is None:
        return SetupEvalSummary(
            available=False,
            status="not_published_yet",
            missing_evidence=["setup_c_latest_eval"],
        )

    payload = _decode_json_object(raw)
    if payload is None:
        return SetupEvalSummary(
            available=False,
            status="malformed",
            missing_evidence=["setup_c_latest_eval_malformed"],
        )

    latest_at = _parse_datetime(payload.get("ts_kst"))
    age = _age_seconds(now, latest_at)
    if latest_at is None:
        return SetupEvalSummary(
            available=False,
            status="malformed",
            missing_evidence=["setup_c_latest_eval_malformed"],
        )
    status = "ok" if age is None or age <= _SETUP_EVAL_STALE_SECONDS else "stale"
    return SetupEvalSummary(
        available=True,
        status=status,
        outcome=str(payload.get("outcome")) if payload.get("outcome") else None,
        reason=str(payload.get("reason")) if payload.get("reason") else None,
        latest_at=latest_at,
        age_seconds=age,
        missing_evidence=[] if status == "ok" else ["setup_c_latest_eval_stale"],
    )


def _load_setup_c_config() -> SetupCConfig:
    try:
        return SetupCConfig.from_yaml()
    except Exception:  # noqa: BLE001
        return SetupCConfig()


def _load_events() -> list[ScheduledEvent]:
    path = _resolve(_SCHEDULED_EVENTS_PATH)
    try:
        return load_scheduled_events(str(path))
    except Exception:  # noqa: BLE001
        return []


def _load_strategy_setup_c_params() -> dict[str, Any]:
    path = _resolve(_SETUP_C_STRATEGY_CONFIG_PATH)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(data, dict):
        return {}
    strategy = data.get("strategy")
    if not isinstance(strategy, dict):
        return {}
    entry = strategy.get("entry")
    if not isinstance(entry, dict):
        return {}
    params = entry.get("params")
    return params if isinstance(params, dict) else {}


def _config_warnings(cfg: SetupCConfig, strategy_params: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    comparisons = {
        "window_minutes": cfg.window_minutes,
        "min_impact_tier": cfg.min_impact_tier,
        "breakout_buffer_atr_mult": cfg.breakout_buffer_atr_mult,
        "target_atr_mult": cfg.target_atr_mult,
        "signal_ttl_minutes": cfg.signal_ttl_minutes,
    }
    for key, decision_value in comparisons.items():
        strategy_value = strategy_params.get(key)
        if strategy_value is not None and strategy_value != decision_value:
            warnings.append(
                "setup_c_config_mismatch:"
                f"{key}=decision_engine:{decision_value},strategy_yaml:{strategy_value}"
            )
    return warnings


def _event_row(
    event: ScheduledEvent,
    *,
    now_kst: datetime,
    cfg: SetupCConfig,
) -> SetupCEventRow:
    scheduled_at = event.scheduled_at
    if scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=UTC)
    scheduled_kst = scheduled_at.astimezone(KST)
    elapsed_minutes: float | None = None
    qualifies = False
    if scheduled_kst <= now_kst:
        elapsed_minutes = (now_kst - scheduled_kst).total_seconds() / 60
        qualifies = (
            elapsed_minutes <= cfg.window_minutes
            and event.impact_tier <= cfg.min_impact_tier
        )
    return SetupCEventRow(
        event_id=event.event_id,
        event_type=event.event_type,
        scheduled_at=scheduled_kst,
        impact_tier=event.impact_tier,
        elapsed_minutes=round(elapsed_minutes, 1)
        if elapsed_minutes is not None
        else None,
        qualifies_window=qualifies,
    )


def _event_at_utc(event: ScheduledEvent) -> datetime:
    scheduled_at = event.scheduled_at
    if scheduled_at.tzinfo is None:
        return scheduled_at.replace(tzinfo=UTC)
    return scheduled_at.astimezone(UTC)


def _scheduled_source(
    events: list[ScheduledEvent],
    *,
    now: datetime,
) -> EventSourceStatus:
    if not events:
        return EventSourceStatus(
            name="scheduled_events",
            kind="config",
            key=str(_resolve(_SCHEDULED_EVENTS_PATH)),
            available=False,
            status="empty",
            count=0,
        )

    past_events = [
        scheduled_at
        for event in events
        if (scheduled_at := _event_at_utc(event)) <= now
    ]
    latest = max(past_events) if past_events else None
    return EventSourceStatus(
        name="scheduled_events",
        kind="config",
        key=str(_resolve(_SCHEDULED_EVENTS_PATH)),
        available=True,
        status="ok",
        count=len(events),
        latest_at=latest,
        age_seconds=_age_seconds(now, latest),
        sample=[
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "scheduled_at": event.scheduled_at,
                "impact_tier": event.impact_tier,
            }
            for event in sorted(events, key=_event_at_utc, reverse=True)[
                :_SOURCE_SAMPLE_LIMIT
            ]
        ],
    )


def _missing_from_sources(sources: list[EventSourceStatus]) -> list[str]:
    missing: list[str] = []
    for source in sources:
        if not source.available or source.status in {"missing", "invalid", "empty", "unavailable"}:
            missing.append(source.name)
        elif source.status == "stale":
            missing.append(f"{source.name}_stale")
    return missing


def _root_from_setup_eval_reason(reason: str | None) -> str:
    if not reason:
        return "setup_eval_reject"
    if reason.startswith("no_event_in_window"):
        return "selective_no_qualifying_event"
    if reason.startswith("no_breakout_within_buffer"):
        return "setup_c_selective_breakout_or_risk"
    if reason.startswith("llm_veto") or reason in {
        "daily_bias_flat",
        "daily_bias_misaligned",
        "regime_gate_blocked",
    }:
        return "setup_c_blocked_by_context_gate"
    if reason == "no_market_context":
        return "market_context_missing"
    if reason.startswith("event_already_traded"):
        return "setup_c_event_already_traded"
    if reason.startswith("after_cutoff"):
        return "setup_c_after_cutoff"
    return "setup_eval_reject"


def _setup_c_diagnostics(
    *,
    asset_class: str,
    cfg: SetupCConfig,
    events: list[ScheduledEvent],
    event_score: EventScoreSummary,
    setup_eval: SetupEvalSummary,
    sources: list[EventSourceStatus],
    now: datetime,
) -> SetupCDiagnostics:
    now_kst = now.astimezone(KST)
    rows = [_event_row(event, now_kst=now_kst, cfg=cfg) for event in events]
    recent_rows = sorted(
        rows,
        key=lambda row: abs(row.elapsed_minutes)
        if row.elapsed_minutes is not None
        else float("inf"),
    )[:10]
    in_window = [row for row in rows if row.qualifies_window]
    missing_sources = _missing_from_sources(sources)
    blocked: dict[str, int] = {}

    def add_block(reason: str) -> None:
        blocked[reason] = blocked.get(reason, 0) + 1

    if asset_class == "stock":
        add_block("setup_c_not_applicable_to_stock")
        root_cause = "not_applicable"
    elif not cfg.enabled:
        add_block("setup_c_disabled")
        root_cause = "setup_c_disabled"
    elif setup_eval.available and setup_eval.status == "ok":
        if setup_eval.outcome == "fired":
            root_cause = "setup_c_signal_active_or_recent"
        elif setup_eval.outcome == "reject":
            add_block(setup_eval.reason or "setup_rejected")
            root_cause = _root_from_setup_eval_reason(setup_eval.reason)
        else:
            root_cause = "setup_eval_unknown_outcome"
    else:
        if setup_eval.status == "stale":
            add_block("setup_eval_stale")
        elif setup_eval.status in {"not_published_yet", "malformed", "unavailable"}:
            add_block(f"setup_eval_{setup_eval.status}")
        if not in_window:
            add_block(f"no_event_in_window({cfg.window_minutes}m,tier<={cfg.min_impact_tier})")
        if event_score.status == "missing":
            add_block("event_score_missing")
        elif event_score.status == "stale":
            add_block("event_score_stale")
        elif event_score.status == "invalid":
            add_block("event_score_invalid")
        for source in sources:
            if source.name in {"news_raw", "news_scored"} and not source.available:
                add_block(f"{source.name}_{source.status}")

        has_news = any(
            source.name in {"news_raw", "news_scored"} and source.available
            for source in sources
        )
        if event_score.status in {"missing", "invalid"} and not has_news and not events:
            root_cause = "event_sourcing_empty"
        elif event_score.status in {"missing", "invalid"} and has_news:
            root_cause = "event_scorer_not_publishing"
        elif event_score.status == "stale" and has_news:
            root_cause = "event_scorer_stale"
        elif not events:
            root_cause = "event_calendar_empty"
        elif not in_window:
            root_cause = "selective_no_qualifying_event"
        elif event_score.status == "fresh":
            root_cause = "setup_c_selective_breakout_or_risk"
        else:
            root_cause = "insufficient_event_context"

    return SetupCDiagnostics(
        enabled=bool(cfg.enabled) and asset_class != "stock",
        window_minutes=int(cfg.window_minutes),
        min_impact_tier=int(cfg.min_impact_tier),
        candidate_count=len(in_window),
        scheduled_events_total=len(events),
        scheduled_events_in_window=len(in_window),
        blocked_reasons=blocked,
        missing_event_sources=missing_sources,
        root_cause=root_cause,
        recent_events=recent_rows,
    )


@router.get("/diagnostics", response_model=EventContextDiagnosticsResponse)
async def get_event_context_diagnostics(
    asset_class: str = Query(default="futures"),
) -> EventContextDiagnosticsResponse:
    """Return event-score/source diagnostics for Setup C no-signal triage."""

    asset = _normalize_asset_class(asset_class)
    now = datetime.now(UTC)
    redis = _get_redis_client()
    cfg = _load_setup_c_config()
    strategy_params = _load_strategy_setup_c_params()
    config_warnings = _config_warnings(cfg, strategy_params)
    event_score = _event_score_summary(redis, now)
    setup_eval = _setup_eval_summary(redis, now)
    events = _load_events()

    sources = [
        _source_from_setup_eval(setup_eval),
        _source_from_event_score(event_score),
        _source_from_stream(redis, name="news_raw", key=_NEWS_RAW_STREAM, now=now),
        _source_from_stream(
            redis, name="news_scored", key=_NEWS_SCORED_STREAM, now=now
        ),
        _source_from_stream(
            redis, name="macro_overnight", key=_MACRO_OVERNIGHT_STREAM, now=now
        ),
        _scheduled_source(events, now=now),
    ]
    setup_c = _setup_c_diagnostics(
        asset_class=asset,
        cfg=cfg,
        events=events,
        event_score=event_score,
        setup_eval=setup_eval,
        sources=sources,
        now=now,
    )
    missing = sorted(
        set(
            event_score.missing_evidence
            + setup_eval.missing_evidence
            + setup_c.missing_event_sources
        )
    )
    notes = [
        "setup_c_latest_eval is the direct runtime reject/fired source when the adapter has published it.",
        "event_score is latest-only because forecasting:events is pubsub, not durable history.",
        "candidate_count counts scheduled events qualifying for the Setup C event window; breakout and risk gates are runtime-only unless setup_c_latest_eval is available.",
    ]
    if config_warnings:
        notes.append("setup_c config mismatch detected between decision_engine.yaml and strategy YAML.")
    if redis is None:
        notes.append("redis_unavailable: stream/key diagnostics are degraded.")
    status = "degraded" if missing or config_warnings else "ok"

    return EventContextDiagnosticsResponse(
        status=status,
        asset_class=asset,
        generated_at=now,
        event_score=event_score,
        setup_eval=setup_eval,
        source_timeline=sources,
        setup_c=setup_c,
        config_warnings=config_warnings,
        missing_evidence=missing,
        notes=notes,
    )
