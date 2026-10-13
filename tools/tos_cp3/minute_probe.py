"""CP-3 PR-1: real quotation GET measurements; never writes tenant state.

Only quote transport is the method/TR/path allowlist in
:mod:`tools.tos_cp3.quote_client`, which this module re-exports — PR-2's live
field producer reuses that same client rather than growing a second one.
Authentication uses existing KISAuthManager with an app-key scoped PRIVATE
cache. No order imports. Raw quote pages, timing brackets, parser comparisons
and B1a timings are retained.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import yaml

from shared.collector.historical.ohlcv_parser import parse_ohlcv
from shared.config.dotenv_guard import read_explicit_dotenv
from shared.storage.market_data_store import ParquetMarketDataStore
from tools.broker_probes.common import (
    REAL_BASE_URL,
    resolve_credentials,
    secret_fingerprint,
)
from tools.tos_cp3.produce_fields import (
    DEFAULT_MIN_BARS_PER_DAY,
    ContractSpecRegistry,
    load_strategy_inputs,
    produce_bars,
    resolve_contract_spec,
    resolve_open_anchor,
)
from tools.tos_cp3.quote_client import (
    ALLOWLIST,
    KST,
    QUOTE_PATH,
    TR,
    Quotes,
    raw_stamp,
    select_day,
)

ROOT = Path(__file__).resolve().parents[2]
COLUMNS = ["code", "timestamp", "open", "high", "low", "close", "volume"]

__all__ = [
    "ALLOWLIST",
    "KST",
    "QUOTE_PATH",
    "REAL_BASE_URL",
    "TR",
    "Quotes",
    "main",
    "raw_stamp",
    "select_day",
]


def frame(rows: list[tuple]) -> pd.DataFrame:
    return (
        pd.DataFrame(rows, columns=COLUMNS)
        .sort_values("timestamp")
        .reset_index(drop=True)
    )


def parser_comparison(rows: list[dict], day: date, symbol: str) -> dict:
    """Test today's proposed singleton parsing against full-day parsing, by value."""
    rows = select_day(rows, day)
    full = parse_ohlcv(symbol, day.strftime("%Y%m%d"), {"output2": rows})
    groups: dict[datetime, list] = {}
    for row in rows:
        stamp = raw_stamp(row, day).replace(second=0, microsecond=0)
        groups.setdefault(stamp, []).append(row)
    incremental = []
    for group in groups.values():
        incremental.extend(
            parse_ohlcv(symbol, day.strftime("%Y%m%d"), {"output2": group})
        )
    a = {r[1].isoformat(): r[2:] for r in full}
    b = {r[1].isoformat(): r[2:] for r in incremental}
    differing = sorted(k for k in a.keys() | b.keys() if a.get(k) != b.get(k))
    return {
        "full_rows": len(a),
        "incremental_rows": len(b),
        "different_minutes": differing,
    }


def seed_capacity(df: pd.DataFrame, strategy, anchor) -> int:
    """First session cannot advance check's window without a previous close."""
    if df.empty:
        return 0
    dates = sorted(set(df.timestamp.dt.date))
    minutes = (
        df.timestamp.dt.hour * 60
        + df.timestamp.dt.minute
        - (anchor.hour * 60 + anchor.minute)
    )
    cfg = strategy.entry_config
    return int(
        (
            (df.timestamp.dt.date != dates[0])
            & (minutes >= cfg.valid_minutes_min)
            & (minutes <= cfg.no_entry_after_minutes_since_open)
        ).sum()
    )


class Recorder:
    def __init__(self, output: Path):
        output.mkdir(parents=True, mode=0o700, exist_ok=False)
        self.output = output

    def save(self, name: str, value) -> None:
        tmp = self.output / (name + ".tmp")
        tmp.write_text(
            json.dumps(value, ensure_ascii=False, default=str, indent=2) + "\n"
        )
        tmp.replace(self.output / name)

    def event(self, value) -> None:
        with (self.output / "requests.jsonl").open("a") as f:
            f.write(json.dumps(value, ensure_ascii=False, default=str) + "\n")

    def finish(self) -> None:
        self.save(
            "sha256.json",
            {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(self.output.iterdir())
                if p.is_file() and p.name != "sha256.json"
            },
        )


def seed_and_compare(
    quotes: Quotes, cfg: dict, target: date, symbol: str, rec: Recorder
):
    strategy = load_strategy_inputs(ROOT / cfg["strategy_yaml"])
    calendar = yaml.safe_load((ROOT / cfg["calendar_yaml"]).read_text())
    holidays = {date.fromisoformat(str(d)) for d in calendar["holidays"]}
    years = {d.year for d in holidays}
    day, chunks, summaries = target, [], []
    anchor = resolve_open_anchor(
        cli_value="auto", first_session=target, last_session=target
    )
    for _ in range(cfg["max_seed_calendar_days"]):
        day -= timedelta(days=1)
        if day.year not in years:
            raise RuntimeError("seed exceeds calendar coverage")
        if day.weekday() >= 5 or day in holidays:
            continue
        before = quotes.calls
        rows = quotes.history(symbol, day)
        parsed = parse_ohlcv(symbol, day.strftime("%Y%m%d"), {"output2": rows})
        reference = ParquetMarketDataStore(
            root=Path(cfg["data_root"]), asset_class="futures"
        ).get_minute_bars(symbol, start=day, end=day)
        ref_values = {}
        if not reference.empty:
            for r in reference.to_dict("records"):
                ref_values[
                    pd.Timestamp(r["datetime"]).tz_localize(None).isoformat()
                ] = tuple(r[k] for k in COLUMNS[2:])
        actual = {r[1].isoformat(): r[2:] for r in parsed}
        diff = sorted(
            k
            for k in actual.keys() | ref_values.keys()
            if actual.get(k) != ref_values.get(k)
        )
        summaries.append(
            {
                "day": day,
                "calls": quotes.calls - before,
                "parsed_rows": len(parsed),
                "density_pass": len(parsed) >= DEFAULT_MIN_BARS_PER_DAY,
                "parser": parser_comparison(rows, day, symbol),
                "parquet_rows": len(ref_values),
                "parquet_comparable": bool(ref_values),
                "parquet_different_minutes": diff if ref_values else None,
            }
        )
        if len(parsed) >= DEFAULT_MIN_BARS_PER_DAY:
            chunks.append(frame(parsed))
        df = (
            pd.concat(chunks).sort_values("timestamp").reset_index(drop=True)
            if chunks
            else frame([])
        )
        capacity = seed_capacity(df, strategy, anchor)
        rec.save(
            "seed-summary.json",
            {
                "sessions": summaries,
                "capacity": capacity,
                "required": strategy.entry_config.vol_window_bars,
            },
        )
        if capacity >= strategy.entry_config.vol_window_bars:
            df.to_json(
                rec.output / "seed-bars.json", orient="records", date_format="iso"
            )
            return df, strategy, anchor
    raise RuntimeError("seed window not filled within configured horizon")


def benchmark(df, symbol, strategy, anchor, cfg) -> dict:
    registry = ContractSpecRegistry.from_yaml(str(ROOT / "config/execution.yaml"))
    contract = resolve_contract_spec(symbol, registry)
    elapsed, count = [], 0
    for _ in range(cfg["benchmark_rounds"]):
        begin = time.perf_counter()
        result = produce_bars(
            df, symbol=symbol, strategy=strategy, contract_spec=contract, anchor=anchor
        )
        elapsed.append(time.perf_counter() - begin)
        count = len(result.records)
    return {
        "rows": len(df),
        "records": count,
        "seconds": elapsed,
        "max_s": max(elapsed),
    }


def sample(quotes, cfg, target, symbol, rec):
    start = datetime.fromisoformat(f"{target}T{cfg['sample_start']}").replace(
        tzinfo=KST
    )
    end = datetime.fromisoformat(f"{target}T{cfg['sample_end']}").replace(tzinfo=KST)
    closing = datetime.fromisoformat(f"{target}T{cfg['closing_start']}").replace(
        tzinfo=KST
    )
    minute = max(start, datetime.now(KST).replace(second=0, microsecond=0))
    observations, latest_rows = [], []
    while minute < end:
        previous_absent, found = None, False
        for offset in cfg["sample_offsets_s"]:
            scheduled = minute + timedelta(seconds=offset)
            if datetime.now(KST) > scheduled + timedelta(
                seconds=cfg["late_tolerance_s"]
            ):
                observations.append(
                    {
                        "boundary_kst": minute,
                        "scheduled_kst": scheduled,
                        "skipped_late": True,
                    }
                )
                continue
            time.sleep(max(0, (scheduled - datetime.now(KST)).total_seconds()))
            try:
                rows = quotes.page(symbol, target)
                now = quotes.last_received_kst
                request_start = quotes.last_started_kst
                stamps = [raw_stamp(r, target) for r in rows]
                present = any(
                    s is not None and s.replace(second=0, microsecond=0) == minute
                    for s in stamps
                )
                observations.append(
                    {
                        "boundary_kst": minute,
                        "received_kst": now,
                        "request_started_kst": request_start,
                        "successor_present": present,
                        "delay_upper_s": (
                            (now - minute).total_seconds() if present else None
                        ),
                        "last_absent_delay_s": previous_absent,
                    }
                )
                if present:
                    found = True
                else:
                    # An absent response may have been sampled by the server
                    # before receipt. Request START is the conservative lower edge.
                    previous_absent = max(0, (request_start - minute).total_seconds())
                latest_rows = select_day(rows, target)
                if found and minute < closing:
                    break
            except RuntimeError:
                observations.append({"boundary_kst": minute, "fetch_error": True})
        rec.save("boundary-samples.json", observations)
        minute += timedelta(minutes=1)
    return latest_rows, observations


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args(argv)
    cfg = yaml.safe_load(args.config.read_text())
    target = date.fromisoformat(str(cfg["date"]))
    if not args.confirm:
        print(
            json.dumps(
                {
                    "mode": "DRY_RUN",
                    "date": str(target),
                    "method": "GET",
                    "tr_id": TR,
                    "path": QUOTE_PATH,
                    "output": cfg["output"],
                    "orders": 0,
                }
            )
        )
        return 0
    os.umask(0o077)
    now = datetime.now(KST)
    if now.date() != target or now.strftime("%H:%M:%S") >= cfg["sample_end"]:
        raise RuntimeError("wrong date or measurement window ended")
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
    from shared.instruments.futures import get_front_month_code

    symbol = get_front_month_code(product="mini", target_date=target)
    rec = Recorder(Path(cfg["output"]))
    rec.save(
        "run.json",
        {
            "started_kst": now,
            "symbol": symbol,
            "config": cfg,
            "app_key_fingerprint": secret_fingerprint(creds.app_key),
            "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
    )
    quotes = Quotes(creds, rec, cfg)
    stage = "sample"
    try:
        rows, observations = sample(quotes, cfg, target, symbol, rec)
        rec.save(
            "capture-status.json", {"status": "CAPTURED", "samples": len(observations)}
        )
        # Preserve all market-dependent measurements before attempting a thin-roll seed.
        stage = "today_history"
        raw = quotes.history(symbol, target)
        parsed = parse_ohlcv(symbol, target.strftime("%Y%m%d"), {"output2": raw})
        today = frame(parsed)
        today.to_json(
            rec.output / "today-bars.json", orient="records", date_format="iso"
        )
        rec.save("m4-today-parser.json", parser_comparison(raw, target, symbol))
        first = {}
        sampled = set()
        for obs in observations:
            boundary = str(obs["boundary_kst"])
            sampled.add(boundary)
            if obs.get("successor_present") and boundary not in first:
                first[boundary] = obs["delay_upper_s"]
        delays = list(first.values())
        rec.save(
            "summary.json",
            {
                "status": "CAPTURED_PENDING_SEED_BENCHMARK",
                "requests": quotes.calls,
                "orders": 0,
                "boundaries": len(sampled),
                "seen_successors": len(first),
                "censored_or_errors": len(sampled - first.keys()),
                "max_first_seen_delay_s": max(delays) if delays else None,
                "delta_G": "derive after inspection of brackets, censored samples and closing rows; no automatic bound claim",
            },
        )
        stage = "seed"
        seed, strategy, anchor = seed_and_compare(quotes, cfg, target, symbol, rec)
        stage = "benchmark_seed"
        rec.save("m3-seed.json", benchmark(seed, symbol, strategy, anchor, cfg))
        stage = "benchmark_full_day"
        rec.save(
            "m3-full-day.json",
            benchmark(
                pd.concat([seed, today]).sort_values("timestamp"),
                symbol,
                strategy,
                anchor,
                cfg,
            ),
        )
        stage = "completion"
        rec.save(
            "completion.json",
            {
                "status": "MEASURED",
                "requests": quotes.calls,
                "requires_analysis": ["delta", "G", "parser_parity", "seed_lineage"],
            },
        )
    except BaseException as exc:
        # The message is kept so an abort names its own cause instead of sending
        # the reader to guess from the last artifact.
        #
        # Scope of the redaction below: exactly the two query secrets this process
        # holds. It does NOT cover the bearer token, which exists only as a local
        # in Quotes.page — and every transport/OAuth exception raised in there is
        # already reduced to one of two fixed tokens before it reaches this
        # handler, so no token text takes this path today. If a future caller
        # raises token-bearing text from outside page(), this scope must widen.
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
                "note": "capture summary is not complete M1-M4 acceptance",
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
