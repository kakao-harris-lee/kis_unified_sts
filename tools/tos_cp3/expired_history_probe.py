"""CP-3 PR-2b prerequisite: does `FHKIF03020200` serve an EXPIRED contract's history?

Plan `docs/plans/2026-10-10-tos-cp3-live-field-producer-plan.md` §3.2a asks one
question that has no observation in this repo: the junction seed walks back into
the month that already expired, so the producer can only be built if the
quotation TR still answers for that code.

GET-only. Transport, the method/TR/path allowlist, the app-key scoped token
cache and the private recorder are PR-1's (`minute_probe`): nothing here opens a
second HTTP client, and no order TR exists in that allowlist. Only finished
sessions are read, so this probe never observes a growing day.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import date, datetime, time, timedelta
from pathlib import Path

import yaml

from shared.collector.historical.ohlcv_parser import parse_ohlcv
from shared.config.dotenv_guard import read_explicit_dotenv
from shared.instruments.futures import get_front_month_code
from tools.broker_probes.common import resolve_credentials, secret_fingerprint
from tools.tos_cp3.minute_probe import (
    KST,
    QUOTE_PATH,
    ROOT,
    TR,
    Quotes,
    Recorder,
    raw_stamp,
    select_day,
)
from tools.tos_cp3.produce_fields import DEFAULT_MIN_BARS_PER_DAY

#: §3.2a applies B1a's gate with the same constant through the same name.
DENSITY_GATE = DEFAULT_MIN_BARS_PER_DAY

#: parse_ohlcv's own tuple layout: (code, minute, open, high, low, close, volume).
CLOSE, VOLUME, MINUTE = 5, 6, 1


def load_calendar(path: Path) -> tuple[set[date], set[int]]:
    """Holidays and the years the tenant calendar actually covers."""
    calendar = yaml.safe_load(path.read_text())
    holidays = {date.fromisoformat(str(d)) for d in calendar["holidays"]}
    return holidays, {d.year for d in holidays}


def is_trading_day(day: date, holidays: set[date]) -> bool:
    return day.weekday() < 5 and day not in holidays


def next_trading_day(day: date, holidays: set[date]) -> date:
    for step in range(1, 15):
        candidate = day + timedelta(days=step)
        if is_trading_day(candidate, holidays):
            return candidate
    raise RuntimeError("no trading day within two weeks of the junction")


def resolve_plan(cfg: dict, *, today: date) -> dict:
    """What will be requested, with the §3.2a walk and the refusals it implies.

    The contract per session comes from the same front-month resolver the
    producer uses; a second roll rule is not written here. Refusals exist so a
    response that is empty for the wrong reason (holiday, unfinished session,
    a window spanning two junctions) cannot be read as the answer.
    """
    holidays, years = load_calendar(ROOT / cfg["calendar_yaml"])
    junction = date.fromisoformat(str(cfg["junction_day"]))
    seed_days = [date.fromisoformat(str(d)) for d in cfg["seed_days"]]
    for day in [junction, *seed_days]:
        if day.year not in years:
            raise RuntimeError("session outside tenant calendar coverage")
        if not is_trading_day(day, holidays):
            raise RuntimeError("requested session is not a trading day")
        if day >= today:
            raise RuntimeError("history probe refuses an unfinished session")
    if any(day >= junction for day in seed_days):
        raise RuntimeError("seed session is not before the junction day")
    expired = get_front_month_code(product="mini", target_date=junction)
    for day in seed_days:
        if get_front_month_code(product="mini", target_date=day) != expired:
            raise RuntimeError("seed window spans more than one contract junction")
    successor_day = next_trading_day(junction, holidays)
    successor = get_front_month_code(product="mini", target_date=successor_day)
    if successor == expired:
        raise RuntimeError("requested junction day has no contract junction")
    sessions = sorted([junction, *seed_days], reverse=True)
    return {
        "junction_day": junction,
        "expired_symbol": expired,
        "successor_symbol": successor,
        "successor_first_session": successor_day,
        "requests": [(expired, day) for day in sessions] + [(successor, junction)],
    }


def broker_statuses(output: Path, symbol: str, day: date) -> dict:
    """Response classes this (symbol, day) produced, from the private request log.

    Only codes: `rt_cd`, `msg_cd`, HTTP status and the probe's own two fixed
    error tokens. `msg1` text is never recorded by the transport, so it cannot
    reach the evidence through here either.
    """
    stamp = day.strftime("%Y%m%d")
    path = output / "requests.jsonl"
    rt_cd: set[str] = set()
    msg_cd: set[str] = set()
    http: set[int] = set()
    errors: set[str] = set()
    pages = 0
    if path.is_file():
        for line in path.read_text().splitlines():
            event = json.loads(line)
            params = event.get("params") or {}
            if (
                params.get("FID_INPUT_ISCD") != symbol
                or params.get("FID_INPUT_DATE_1") != stamp
            ):
                continue
            if event.get("error"):
                errors.add(str(event["error"]))
                continue
            if "rt_cd" not in event:
                continue
            pages += 1
            rt_cd.add(str(event.get("rt_cd")))
            if event.get("msg_cd"):
                msg_cd.add(str(event["msg_cd"]))
            http.add(int(event.get("http_status", 0)))
    return {
        "pages": pages,
        "rt_cd": sorted(rt_cd),
        "msg_cd": sorted(msg_cd),
        "http_status": sorted(http),
        "transport_errors": sorted(errors),
    }


def session_report(quotes: Quotes, rec: Recorder, symbol: str, day: date) -> tuple:
    """One (symbol, day): raw shape, raw edges, parsed count against the gate.

    A broker refusal is this probe's result, not its failure, so it is recorded
    and the walk continues.
    """
    raw: list[dict] = []
    fetch_error = None
    try:
        raw = quotes.history(symbol, day)
    except RuntimeError as exc:
        fetch_error = str(exc)
    raw = select_day(raw, day)
    stamps = sorted(s for s in (raw_stamp(r, day) for r in raw) if s is not None)
    keys: set[str] = set()
    for row in raw:
        keys.update(row.keys())
    parsed = parse_ohlcv(symbol, day.strftime("%Y%m%d"), {"output2": raw})
    minutes = [row[MINUTE] for row in parsed]
    report = {
        "symbol": symbol,
        "day": day.isoformat(),
        "fetch_error": fetch_error,
        "broker": broker_statuses(rec.output, symbol, day),
        "raw_rows": len(raw),
        "raw_row_keys": sorted(keys),
        "raw_first_kst": stamps[0].strftime("%H:%M:%S") if stamps else None,
        "raw_last_kst": stamps[-1].strftime("%H:%M:%S") if stamps else None,
        "parsed_bars": len(parsed),
        "density_gate": DENSITY_GATE,
        "density_pass": len(parsed) >= DENSITY_GATE,
        "parsed_first_kst": minutes[0].strftime("%H:%M") if minutes else None,
        "parsed_last_kst": minutes[-1].strftime("%H:%M") if minutes else None,
        # Both causes at once: parse_ohlcv's volume floor and its phantom
        # resolution. The artifact does not claim which one dropped a minute.
        "raw_minutes_not_stored": len({m.replace(second=0) for m in stamps})
        - len(minutes),
    }
    return report, parsed


def closes_by_minute(parsed: list[tuple]) -> dict:
    return {row[MINUTE]: row for row in parsed}


def junction_alignment(expired: list[tuple], successor: list[tuple]) -> dict:
    """§3.2a `c_x100` from the LAST minute both contracts have a PARSED bar for.

    Not each contract's own last close: the expiring leg may stop earlier, and
    the stored-bar (volume floor applied) minute is what the producer and the
    offline pair both have.
    """
    old, new = closes_by_minute(expired), closes_by_minute(successor)
    common = sorted(set(old) & set(new))
    if not common:
        return {
            "common_parsed_minutes": 0,
            "last_common_minute_kst": None,
            "c_x100": None,
            "note": "no common parsed minute: §3.2a would refuse startup here",
        }
    last = common[-1]
    old_close = round(old[last][CLOSE] * 100)
    new_close = round(new[last][CLOSE] * 100)
    return {
        "common_parsed_minutes": len(common),
        "first_common_minute_kst": common[0].strftime("%H:%M"),
        "last_common_minute_kst": last.strftime("%H:%M"),
        "expired_close_x100": old_close,
        "successor_close_x100": new_close,
        "c_x100": new_close - old_close,
        "c_x100_is_even": (new_close - old_close) % 2 == 0,
        "expired_last_parsed_kst": max(old).strftime("%H:%M"),
        "successor_last_parsed_kst": max(new).strftime("%H:%M"),
        "last_common_is_expired_last": last == max(old),
        "last_common_is_successor_last": last == max(new),
    }


def spread_window(
    expired: list[tuple], successor: list[tuple], start: str, end: str | None
) -> dict:
    """S1a input: the spread range over [start, end] on the junction day.

    Both legs are PARSED bars, so `parse_ohlcv`'s `KIS_MINUTE_BAR_MIN_VOLUME`
    floor (pinned to the §3.3 value of 10) has already removed every minute
    below the floor on either side; the volume extremes below prove it held.
    """
    if end is None:
        return {"minutes_used": 0, "note": "no common parsed minute in the window"}
    old, new = closes_by_minute(expired), closes_by_minute(successor)
    begin = time.fromisoformat(start if len(start) > 5 else start + ":00")
    finish = time.fromisoformat(end if len(end) > 5 else end + ":00")
    used = [
        minute
        for minute in sorted(set(old) & set(new))
        if begin <= minute.time() <= finish
    ]
    spreads = [round(new[m][CLOSE] * 100) - round(old[m][CLOSE] * 100) for m in used]
    volumes = [row[VOLUME] for m in used for row in (old[m], new[m])]
    return {
        "window_start_kst": begin.strftime("%H:%M"),
        "window_end_kst": finish.strftime("%H:%M"),
        "minutes_used": len(used),
        "volume_floor": int(os.getenv("KIS_MINUTE_BAR_MIN_VOLUME", "10")),
        "min_volume_observed": min(volumes) if volumes else None,
        "spread_x100_min": min(spreads) if spreads else None,
        "spread_x100_max": max(spreads) if spreads else None,
        "spread_x100_range": (max(spreads) - min(spreads)) if spreads else None,
        "spread_x100_first": spreads[0] if spreads else None,
        "spread_x100_last": spreads[-1] if spreads else None,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args(argv)
    cfg = yaml.safe_load(args.config.read_text())
    # Resolved before --confirm so a dry run exercises every refusal above.
    plan = resolve_plan(cfg, today=datetime.now(KST).date())
    if not args.confirm:
        print(
            json.dumps(
                {
                    "mode": "DRY_RUN",
                    "method": "GET",
                    "tr_id": TR,
                    "path": QUOTE_PATH,
                    "expired_symbol": plan["expired_symbol"],
                    "successor_symbol": plan["successor_symbol"],
                    "requests": [f"{s} {d}" for s, d in plan["requests"]],
                    "output": cfg["output"],
                    "orders": 0,
                },
                default=str,
            )
        )
        return 0
    os.umask(0o077)
    # Only the two futures query secrets cross into this measurement process.
    credential_keys = ("KIS_FUTURES_APP_KEY", "KIS_FUTURES_APP_SECRET")
    values = read_explicit_dotenv(Path(cfg["env_file"]), keys=credential_keys)
    for key in credential_keys:
        value = values.get(key)
        if not value:
            raise RuntimeError("missing futures credential")
        os.environ[key] = value
    for key, expected in cfg["parser_env"].items():
        if os.getenv(key, str(expected)) != str(expected):
            raise RuntimeError("parser env pin mismatch")
        os.environ[key] = str(expected)
    creds = resolve_credentials("futures", is_real=True)
    rec = Recorder(Path(cfg["output"]))
    rec.save(
        "run.json",
        {
            "started_kst": datetime.now(KST),
            "plan": plan,
            "config": cfg,
            "app_key_fingerprint": secret_fingerprint(creds.app_key),
            "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
    )
    quotes = Quotes(creds, rec, cfg)
    stage = "sessions"
    try:
        sessions, bars = [], {}
        for symbol, day in plan["requests"]:
            stage = f"session {symbol} {day}"
            report, parsed = session_report(quotes, rec, symbol, day)
            sessions.append(report)
            bars[(symbol, day)] = parsed
            rec.save("sessions.json", sessions)
        stage = "junction"
        expired_bars = bars[(plan["expired_symbol"], plan["junction_day"])]
        successor_bars = bars[(plan["successor_symbol"], plan["junction_day"])]
        align = junction_alignment(expired_bars, successor_bars)
        rec.save("junction.json", align)
        stage = "spread"
        rec.save(
            "s1a-spread.json",
            spread_window(
                expired_bars,
                successor_bars,
                str(cfg["spread_window_start"]),
                align["last_common_minute_kst"],
            ),
        )
        stage = "summary"
        expired_days = [s for s in sessions if s["symbol"] == plan["expired_symbol"]]
        served = [s for s in expired_days if s["parsed_bars"] > 0]
        rec.save(
            "summary.json",
            {
                "expired_symbol": plan["expired_symbol"],
                "expired_history_served": bool(served),
                "expired_sessions_requested": len(expired_days),
                "expired_sessions_with_bars": len(served),
                "expired_sessions_passing_density": sum(
                    1 for s in expired_days if s["density_pass"]
                ),
                "requests": quotes.calls,
                "orders": 0,
                "method": "GET",
                "tr_id": TR,
                "verdict_scope": (
                    "prerequisite only; neither the producer nor the §6.2 "
                    "fallback is designed or approved here"
                ),
            },
        )
    except BaseException as exc:
        # Scope of the redaction: exactly the two query secrets this process
        # holds. The bearer token never leaves Quotes.page, which reduces every
        # transport/OAuth exception to one of two fixed tokens first.
        message = str(exc)
        for secret in (creds.app_key, creds.app_secret):
            if secret:
                message = message.replace(secret, "<redacted>")
        rec.save(
            "abort.json",
            {
                "status": "ABORT",
                "error_type": type(exc).__name__,
                "error_message": message,
                "stage": stage,
                "requests": quotes.calls,
            },
        )
        raise RuntimeError(
            "probe aborted; inspect private artifact directory"
        ) from None
    finally:
        quotes.http.close()
        rec.finish()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
