"""The band line's shape, and the two readers of it. Stdlib + ``yaml`` only."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from tools.tos_cp3.session_day import SessionDayError, load_producer_session

KST = ZoneInfo("Asia/Seoul")

BAND_LINE_KIND = "cp3-band/1"

BAND_JOURNAL_NAME = "band.jsonl"

BAND_KEY_ORDER: tuple[str, ...] = (
    "kind",
    "source_id",
    "instrument",
    "trading_date",
    "tr_id",
    "upper",
    "lower",
    "basis",
    "raw_payload_digest",
    "producer_continuity_id",
    "as_of_ms",
)

BAND_PAYLOAD_FIELDS: tuple[tuple[str, str], ...] = (
    ("futs_mxpr", "upper"),
    ("futs_llam", "lower"),
    ("futs_sdpr", "basis"),
)

BAND_PAYLOAD_MEMBER = "output1"

BAND_PAYLOADS: dict[str, tuple[str, tuple[tuple[str, str], ...]]] = {
    "futures": (BAND_PAYLOAD_MEMBER, BAND_PAYLOAD_FIELDS),
    "stock": (
        "output",
        (("stck_mxpr", "upper"), ("stck_llam", "lower"), ("stck_sdpr", "basis")),
    ),
}


class BandLineError(RuntimeError):
    """A band payload or band line that cannot be used. Never routed around."""


class TickLadderMismatch(BandLineError):
    """The broker's ``aspr_unit`` disagrees with the tree's tick ladder (#929 review)."""


@dataclass(frozen=True)
class TickLadder:
    """The tree's ``price_band_ticks`` rows at its own ``_runtime.price_scale``."""

    price_scale: int
    rows: tuple[tuple[int, int, int], ...]

    def tick_for(self, scaled_price: int) -> int | None:
        """The tick of the row covering ``scaled_price``, or ``None``."""
        for band_min, band_max, tick in self.rows:
            if band_min <= scaled_price <= band_max:
                return tick
        return None


def _ladder_cell(row: object, key: str) -> int | None:
    """One ladder cell as a non-bool ``int``, or ``None`` when it is not one."""
    if not isinstance(row, dict):
        return None
    value = row.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def load_tick_ladder(venue_policy_yaml: Path) -> TickLadder:
    """Read the ladder the runtime enforces, or raise :class:`BandLineError`."""
    try:
        raw = yaml.safe_load(venue_policy_yaml.read_text(encoding="utf-8"))
        scale = raw["_runtime"]["price_scale"]
        table = raw["_model_view"]["shape_constraints"]["price_band_ticks"]
    except (OSError, yaml.YAMLError, KeyError, TypeError) as exc:
        raise BandLineError(
            f"{venue_policy_yaml}: no _runtime.price_scale / price_band_ticks ({exc!r})"
        ) from exc
    rows: list[tuple[int, int, int]] = []
    for row in table if isinstance(table, list) else []:
        band_min = _ladder_cell(row, "band_min")
        band_max = _ladder_cell(row, "band_max")
        tick = _ladder_cell(row, "tick")
        if band_min is None or band_max is None or tick is None:
            raise BandLineError(f"{venue_policy_yaml}: malformed ladder row {row!r}")
        rows.append((band_min, band_max, tick))
    if not rows or not isinstance(scale, int) or isinstance(scale, bool) or scale < 1:
        raise BandLineError(
            f"{venue_policy_yaml}: price_scale={scale!r} / {len(rows)} ladder rows"
        )
    return TickLadder(price_scale=scale, rows=tuple(rows))


STOCK_TICK_FIELDS = ("stck_prpr", "aspr_unit")


def check_broker_tick(payload: Mapping[str, Any], ladder: TickLadder) -> dict[str, int]:
    """The broker's ``aspr_unit`` for the quoted price against the ladder's tick."""
    member = payload.get("output")
    if not isinstance(member, Mapping):
        raise BandLineError("stock band response has no output mapping")
    parsed: dict[str, int] = {}
    for name in STOCK_TICK_FIELDS:
        text = str(member.get(name) or "").strip()
        if not (text.isascii() and text.isdigit()) or int(text) <= 0:
            raise BandLineError(f"stock band response {name}={member.get(name)!r}")
        parsed[name] = int(text)
    scaled_price = parsed["stck_prpr"] * ladder.price_scale
    broker_tick = parsed["aspr_unit"] * ladder.price_scale
    ladder_tick = ladder.tick_for(scaled_price)
    if ladder_tick != broker_tick:
        raise TickLadderMismatch(
            f"aspr_unit {parsed['aspr_unit']} at stck_prpr {parsed['stck_prpr']} "
            f"(= tick {broker_tick} at scale {ladder.price_scale}) != ladder tick "
            f"{ladder_tick} — the venue gate's grid disagrees with the broker"
        )
    return {**parsed, "ladder_tick": ladder_tick}


def trading_date_text(day: date) -> str:
    """The producer's local KST calendar stamp for *day* (band plan §3.2)."""
    return day.strftime("%Y%m%d")


def band_values_from_payload(
    payload: Mapping[str, Any], market: str = "futures"
) -> dict[str, str]:
    """The three band fields, as strings, or raise."""
    member_name, fields = BAND_PAYLOADS[market]
    member = payload.get(member_name)
    if not isinstance(member, Mapping):
        raise BandLineError(
            f"band response has no {member_name} mapping "
            f"(got {type(member).__name__})"
        )
    values: dict[str, str] = {}
    missing: list[str] = []
    for source, key in fields:
        raw = member.get(source)
        text = "" if raw is None else str(raw).strip()
        if not text:
            missing.append(f"{source}={raw!r}")
        else:
            values[key] = text
    if missing:
        raise BandLineError(f"band response is missing {', '.join(missing)}")
    return values


def read_last_band_line(path: Path) -> dict[str, Any] | None:
    """The LAST line of *path*, parsed, or ``None``."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    try:
        parsed = json.loads(lines[-1])
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def reject_reason(
    line: Any, *, instrument: str, trading_date: str, open_ms: int
) -> str | None:
    """Why *line* is not a usable band for this session, or ``None``."""
    if not isinstance(line, Mapping):
        return "not_a_mapping"
    if line.get("kind") != BAND_LINE_KIND:
        return f"kind={line.get('kind')!r} is not {BAND_LINE_KIND!r}"
    if line.get("instrument") != instrument:
        return f"instrument={line.get('instrument')!r} is not {instrument!r}"
    if line.get("trading_date") != trading_date:
        return f"trading_date={line.get('trading_date')!r} is not {trading_date!r}"
    as_of_ms = line.get("as_of_ms")
    if not isinstance(as_of_ms, int) or isinstance(as_of_ms, bool):
        return f"as_of_ms={as_of_ms!r} is not an integer"
    if as_of_ms < open_ms:
        return f"as_of_ms={as_of_ms} is before the open ({open_ms})"
    return None


def session_open_ms(
    producer_config: Path, *, repo_root: Path, day: date
) -> tuple[int, str]:
    """``(epoch ms of *day*'s session open, that day's trading-date stamp)``."""
    try:
        window = load_producer_session(producer_config, repo_root=repo_root).window(day)
    except SessionDayError as exc:
        raise BandLineError(str(exc)) from exc
    opened = datetime.combine(day, window.start, tzinfo=KST)
    return int(opened.timestamp() * 1000), trading_date_text(day)
