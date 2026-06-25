"""Observe Setup C event-score readiness from Redis or offline JSON."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_LATEST_KEY = "forecast:event:latest"
DEFAULT_HISTORY_KEY = "forecast:event:history"
_PLACEHOLDER_MARKERS = (
    "todo",
    "tbd",
    "placeholder",
    "replace me",
    "lorem ipsum",
)


@dataclass(frozen=True)
class ObservationThresholds:
    min_history: int
    max_age_minutes: float
    min_impact_score: float


def _decode(raw: Any) -> Any:
    if isinstance(raw, bytes):
        return raw.decode(errors="ignore")
    return raw


def _decode_json_object(raw: Any) -> dict[str, Any] | None:
    raw = _decode(raw)
    if isinstance(raw, dict):
        return raw
    try:
        payload = json.loads(str(raw))
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


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
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _coerce_float(raw: Any) -> float | None:
    try:
        return float(str(raw))
    except (TypeError, ValueError):
        return None


def _coerce_int(raw: Any) -> int | None:
    try:
        return int(float(str(raw)))
    except (TypeError, ValueError):
        return None


def _round(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def _has_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        lowered = value.strip().lower()
        return any(marker in lowered for marker in _PLACEHOLDER_MARKERS)
    if isinstance(value, dict):
        return any(_has_placeholder(child) for child in value.values())
    if isinstance(value, list):
        return any(_has_placeholder(child) for child in value)
    return False


def _fresh_age_limit_minutes(
    payload: dict[str, Any],
    thresholds: ObservationThresholds,
) -> float:
    ttl_minutes = _coerce_float(payload.get("ttl_minutes"))
    if ttl_minutes is None or ttl_minutes <= 0:
        return thresholds.max_age_minutes
    return min(thresholds.max_age_minutes, ttl_minutes)


def _load_history_json(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("--history-json must contain a JSON list")
    rows: list[dict[str, Any]] = []
    for item in payload:
        if isinstance(item, dict):
            rows.append(item)
        elif (decoded := _decode_json_object(item)) is not None:
            rows.append(decoded)
    return rows


def _load_redis_history(
    *,
    redis_url: str,
    latest_key: str,
    history_key: str,
    history_limit: int,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    try:
        import redis
    except ImportError as exc:  # pragma: no cover - depends on operator env
        raise RuntimeError("redis package is required for --redis-url") from exc

    client = redis.Redis.from_url(redis_url)
    latest = _decode_json_object(client.get(latest_key))
    raw_history = client.lrange(history_key, 0, max(0, history_limit - 1)) or []
    history = [
        payload
        for raw in raw_history
        if (payload := _decode_json_object(raw)) is not None
    ]
    if latest is not None and not history:
        history = [latest]
    return latest, history


def build_report(
    *,
    history: Sequence[dict[str, Any]],
    asof: datetime,
    thresholds: ObservationThresholds,
    latest: dict[str, Any] | None = None,
    source: str,
) -> dict[str, Any]:
    rows = [
        {
            **payload,
            "_asof": parsed_asof,
            "_impact_score": _coerce_float(payload.get("impact_score")),
            "_impact_tier": _coerce_int(payload.get("impact_tier")),
        }
        for payload in history
        if (parsed_asof := _parse_datetime(payload.get("asof"))) is not None
    ]
    rows.sort(key=lambda row: row["_asof"], reverse=True)

    ages = [max(0.0, (asof - row["_asof"]).total_seconds() / 60.0) for row in rows]
    fresh_rows = [
        row
        for row, age in zip(rows, ages)
        if age <= _fresh_age_limit_minutes(row, thresholds)
    ]
    impacts = [row["_impact_score"] for row in rows if row["_impact_score"] is not None]
    tier_distribution = Counter(
        str(tier)
        for row in rows
        if (tier := row["_impact_tier"]) is not None and tier > 0
    )
    latest_payload = latest or (rows[0] if rows else None)

    missing_evidence: list[str] = []
    if len(rows) < thresholds.min_history:
        missing_evidence.append("event_score_history_empty")
    if not fresh_rows:
        missing_evidence.append("event_score_stale")
    if not impacts or min(impacts) < thresholds.min_impact_score:
        missing_evidence.append("impact_score_below_minimum")
    if any(_has_placeholder(row) for row in rows):
        missing_evidence.append("placeholder_event_score_evidence")

    return {
        "ready": not missing_evidence,
        "source": source,
        "generated_at": asof.isoformat(),
        "thresholds": {
            "min_history": thresholds.min_history,
            "max_age_minutes": thresholds.max_age_minutes,
            "min_impact_score": thresholds.min_impact_score,
        },
        "count": len(rows),
        "fresh_count": len(fresh_rows),
        "max_age_minutes": _round(max(ages) if ages else None),
        "impact_score": {
            "min": _round(min(impacts) if impacts else None),
            "avg": _round((sum(impacts) / len(impacts)) if impacts else None),
        },
        "tier_distribution": dict(sorted(tier_distribution.items())),
        "latest": _summarize_latest(latest_payload),
        "missing_evidence": missing_evidence,
    }


def _summarize_latest(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if payload is None:
        return None
    asof = _parse_datetime(payload.get("asof"))
    return {
        "asof": asof.isoformat() if asof else None,
        "event_type": payload.get("event_type"),
        "impact_score": _coerce_float(payload.get("impact_score")),
        "impact_tier": _coerce_int(payload.get("impact_tier")),
        "source": payload.get("source"),
        "ttl_minutes": _coerce_int(payload.get("ttl_minutes")),
    }


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Observe Setup C event-score history readiness."
    )
    parser.add_argument(
        "--history-json",
        type=Path,
        help="Offline JSON file containing a list of EventScore JSON objects.",
    )
    parser.add_argument(
        "--redis-url",
        default=os.environ.get("REDIS_URL"),
        help="Redis URL for read-only observation. Defaults to REDIS_URL.",
    )
    parser.add_argument("--latest-key", default=DEFAULT_LATEST_KEY)
    parser.add_argument("--history-key", default=DEFAULT_HISTORY_KEY)
    parser.add_argument("--history-limit", type=int, default=500)
    parser.add_argument("--min-history", type=int, default=20)
    parser.add_argument("--max-age-minutes", type=float, default=60.0)
    parser.add_argument("--min-impact-score", type=float, default=60.0)
    parser.add_argument(
        "--asof",
        help="Evaluation timestamp. Defaults to current UTC time.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Optional path to write the JSON report.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    asof = _parse_datetime(args.asof) if args.asof else datetime.now(UTC)
    if asof is None:
        raise ValueError("--asof must be an ISO-8601 datetime")

    thresholds = ObservationThresholds(
        min_history=max(1, args.min_history),
        max_age_minutes=max(0.0, args.max_age_minutes),
        min_impact_score=args.min_impact_score,
    )

    latest: dict[str, Any] | None = None
    if args.history_json:
        history = _load_history_json(args.history_json)
        source = "history_json"
    elif args.redis_url:
        latest, history = _load_redis_history(
            redis_url=args.redis_url,
            latest_key=args.latest_key,
            history_key=args.history_key,
            history_limit=args.history_limit,
        )
        source = "redis"
    else:
        raise ValueError("provide --history-json or --redis-url/REDIS_URL")

    report = build_report(
        history=history,
        latest=latest,
        asof=asof,
        thresholds=thresholds,
        source=source,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
