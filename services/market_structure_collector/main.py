"""Market-structure daily collector — run via cron (KST-native).

Two one-shot modes (deploy/scheduler.crontab):

* ``close`` (18:40 KST): captures the day's finalized structure row — foreign
  futures net-buy (KIS FHPTJ04030000 snapshot after 15:45 = daily confirmed),
  program trading (FHPPG04600001), futures price/OI (FHMIF10000000), K200 spot
  index (FHPUP02100000), basis vs theoretical fair value, KRX stock investor
  net-buy, and FX/overseas read from the macro overnight stream.
* ``premarket`` (08:00 KST): composes the pre-open knowledge row from the
  previous close row plus overnight signals (macro premarket snapshot and the
  optional night-futures capture) — never any same-day intraday data, so
  backtests reading the ``premarket`` snapshot stay look-ahead free.

Rows are persisted via ``ParquetMarketStructureStore.replace_day`` (idempotent)
and published to Redis DB 1 (``market:structure:latest`` hash + event stream).
Every component may be missing; coverage_ratio/missing_components record gaps
and values are never synthesized.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from services.market_structure_collector import derived
from services.market_structure_collector.config import MarketStructureCollectorConfig
from shared.config.runtime_defaults import redis_url_from_env
from shared.macro.base import read_latest_macro_snapshot

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")

_SNAPSHOT_CLOSE = "close"
_SNAPSHOT_PREMARKET = "premarket"

# Row meta / derived-meta columns never carried forward between snapshots.
_NON_CARRY_COLUMNS = frozenset(
    {
        "trade_date",
        "snapshot",
        "asof_ts",
        "finalized",
        "schema_version",
        "coverage_ratio",
        "missing_components",
        "source_trade_date",
    }
)

# Coverage component -> columns that must be present for the component to
# count as collected (any-of semantics for multi-column components).
COMPONENT_COLUMNS: dict[str, tuple[str, ...]] = {
    "foreign_futures": ("fut_foreign_net_qty",),
    "program": ("prog_net_val",),
    "oi": ("fut_oi_qty",),
    "k200": ("k200_close",),
    "basis": ("basis_dev",),
    "stock_investor": ("stock_foreign_net_val",),
    "fx": ("usdkrw",),
    "overseas": (
        "es_futures_change_pct",
        "nq_futures_change_pct",
        "sox_change_pct",
    ),
}

# Defensive KIS field-name candidates. The exact program-TR row shape awaits
# the residual real-token probe (roadmap O1); parsing tries candidates in
# order and records the component as missing when none match.
_FOREIGN_QTY_KEYS = ("frgn_ntby_qty", "frgn_ntby_cntg_qty")
_FOREIGN_VAL_KEYS = ("frgn_ntby_tr_pbmn",)
_PROGRAM_DATE_KEYS = ("stck_bsop_date", "bsop_date")
_PROGRAM_WHOLE_KEYS = (
    "whol_ntby_tr_pbmn",
    "whol_smtn_ntby_tr_pbmn",
    "tot_ntby_tr_pbmn",
)
_PROGRAM_ARB_KEYS = ("arbt_ntby_tr_pbmn", "arbt_smtn_ntby_tr_pbmn")
_PROGRAM_NONARB_KEYS = ("nabt_ntby_tr_pbmn", "nabt_smtn_ntby_tr_pbmn")
_INDEX_PRICE_KEYS = ("bstp_nmix_prpr",)
_INDEX_CHANGE_PCT_KEYS = ("bstp_nmix_prdy_ctrt",)

# Night-capture fields kept as strings when merged into the premarket row
# ("code" keeps product_code — e.g. "101W9000" — from being number-parsed away).
_NIGHT_TEXT_MARKERS = ("asof", "time", "date", "session", "symbol", "source", "code")


# ---------------------------------------------------------------------------
# Parsing / small helpers
# ---------------------------------------------------------------------------


def _parse_number(value: Any) -> float | None:
    """Parse a KIS/KRX numeric string ("1,234" / "-" / "" → None-safe)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text or text in {"-", "."}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _first_number(row: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        parsed = _parse_number(row.get(key))
        if parsed is not None:
            return parsed
    return None


def _is_present(value: Any) -> bool:
    if value is None:
        return False
    # NaN check (value != value) marks pandas-null floats as missing.
    return not (isinstance(value, float) and value != value)


def _coverage(row: dict[str, Any], components: list[str]) -> tuple[float, list[str]]:
    """Coverage ratio + missing component names for a composed row."""
    missing: list[str] = []
    for component in components:
        columns = COMPONENT_COLUMNS.get(component, (component,))
        if not any(_is_present(row.get(column)) for column in columns):
            missing.append(component)
    total = max(len(components), 1)
    return (total - len(missing)) / total, missing


def _now_kst() -> datetime:
    return datetime.now(KST).replace(tzinfo=None)


def _resolve_trade_date(trade_date: date | None) -> date:
    return trade_date or _now_kst().date()


# ---------------------------------------------------------------------------
# History / derived inputs
# ---------------------------------------------------------------------------


def _load_close_history(store: Any, end_exclusive: date, lookback_days: int) -> Any:
    """Prior close rows (oldest→newest DataFrame; may be empty)."""
    start = end_exclusive - timedelta(days=max(int(lookback_days), 1))
    return store.read_range(
        start, end_exclusive - timedelta(days=1), snapshot=_SNAPSHOT_CLOSE
    )


def _history_series(history: Any, column: str) -> list[Any]:
    if history is None or getattr(history, "empty", True):
        return []
    if column not in history.columns:
        return []
    frame = history.sort_values("trade_date")
    return list(frame[column])


def _history_pairs(history: Any, column: str) -> list[list[Any]]:
    """(iso_date, value) pairs for non-null history values (oldest→newest)."""
    if history is None or getattr(history, "empty", True):
        return []
    if column not in history.columns:
        return []
    frame = history.sort_values("trade_date")
    pairs: list[list[Any]] = []
    for day, value in zip(frame["trade_date"], frame[column]):
        if _is_present(value):
            pairs.append([day.isoformat(), float(value)])
    return pairs


def _load_cum_window(
    redis: Any, config: MarketStructureCollectorConfig, history: Any
) -> list[list[Any]]:
    """Rolling foreign-futures window: Redis first, Parquet history fallback.

    The Redis key has a 48h TTL, so after weekends/holidays it may be gone;
    the store is the durable source and the window is rebuilt from it.
    """
    try:
        raw = redis.get(config.redis.cum20_key)
    except Exception:  # noqa: BLE001 — degraded Redis must not kill the run
        raw = None
    if raw:
        try:
            payload = json.loads(raw)
            window = payload.get("window", [])
            if isinstance(window, list) and window:
                return [list(entry) for entry in window if len(entry) == 2]
        except (TypeError, ValueError):
            logger.warning("cum20 window key is corrupt; rebuilding from store")
    return _history_pairs(history, "fut_foreign_net_qty")


# ---------------------------------------------------------------------------
# Component collection (close mode)
# ---------------------------------------------------------------------------


async def _collect_foreign_futures(
    kis_client: Any, config: MarketStructureCollectorConfig
) -> dict[str, Any]:
    rows = await kis_client.fetch_market_investor_trend(
        config.kis.foreign_futures_market_code,
        config.kis.foreign_futures_product_code,
    )
    if not rows:
        raise RuntimeError("FHPTJ04030000 returned no rows")
    row = rows[0]
    qty = _first_number(row, _FOREIGN_QTY_KEYS)
    if qty is None:
        raise RuntimeError(
            f"FHPTJ04030000 row lacks foreign net-qty keys: {sorted(row)[:20]}"
        )
    return {
        "fut_foreign_net_qty": qty,
        "fut_foreign_net_val": _first_number(row, _FOREIGN_VAL_KEYS),
    }


async def _collect_program(
    kis_client: Any, config: MarketStructureCollectorConfig, trade_date: date
) -> dict[str, Any]:
    rows = await kis_client.fetch_program_trade_daily(
        trade_date,
        trade_date,
        market_div=config.kis.program_market_div,
        market_cls=config.kis.program_market_cls,
    )
    if not rows:
        raise RuntimeError("FHPPG04600001 returned no rows")
    target = trade_date.strftime("%Y%m%d")
    row = next(
        (
            candidate
            for candidate in rows
            if any(
                str(candidate.get(key, "")).replace("-", "").replace("/", "") == target
                for key in _PROGRAM_DATE_KEYS
            )
        ),
        rows[0],
    )
    whole = _first_number(row, _PROGRAM_WHOLE_KEYS)
    arb = _first_number(row, _PROGRAM_ARB_KEYS)
    nonarb = _first_number(row, _PROGRAM_NONARB_KEYS)
    if whole is None and arb is not None and nonarb is not None:
        whole = arb + nonarb
    if whole is None:
        raise RuntimeError(
            f"FHPPG04600001 row lacks known net-value keys: {sorted(row)[:20]}"
        )
    return {
        "prog_net_val": whole,
        "prog_arb_net_val": arb,
        "prog_nonarb_net_val": nonarb,
    }


async def _collect_futures_quote(
    kis_client: Any, config: MarketStructureCollectorConfig
) -> dict[str, Any]:
    quote = await kis_client.get_current_price(config.kis.futures_symbol)
    close = _parse_number(quote.get("close"))
    if close is None or close <= 0:
        raise RuntimeError(f"futures quote has no price: {quote!r:.200}")
    change = _parse_number(quote.get("change"))
    return {
        "fut_close": close,
        "fut_change_pct": change * 100.0 if change is not None else None,
        "fut_oi_qty": _parse_number(quote.get("open_interest")),
        "fut_oi_change": _parse_number(quote.get("open_interest_change")),
    }


async def _collect_k200(
    kis_client: Any, config: MarketStructureCollectorConfig
) -> dict[str, Any]:
    output = await kis_client.fetch_index_price(
        config.kis.index_code, market_div=config.kis.index_market_div
    )
    close = _first_number(output, _INDEX_PRICE_KEYS)
    if close is None or close <= 0:
        raise RuntimeError(
            f"FHPUP02100000 output lacks index price: {sorted(output)[:20]}"
        )
    return {
        "k200_close": close,
        "k200_change_pct": _first_number(output, _INDEX_CHANGE_PCT_KEYS),
    }


def _collect_stock_investor(krx_collector: Any) -> dict[str, Any]:
    # Wave 2c corrected anonymous MDCSTAT02203_OUT path (KRW net trade value).
    data = krx_collector.get_investor_trading()
    if not data:
        raise RuntimeError("KRX investor trading returned empty payload")
    return {
        "stock_foreign_net_val": _parse_number(data.get("foreign_net")),
        "stock_institution_net_val": _parse_number(data.get("institution_net")),
        "stock_retail_net_val": _parse_number(data.get("retail_net")),
    }


def _collect_macro(
    redis: Any, config: MarketStructureCollectorConfig
) -> dict[str, Any]:
    """FX/overseas from the macro overnight stream (never re-collected)."""
    snap = read_latest_macro_snapshot(redis, config.redis.macro_stream_key)
    if snap is None:
        return {}
    usdkrw = snap.usdkrw if snap.usdkrw is not None else snap.usdkrw_realtime
    return {
        "usdkrw": usdkrw,
        "usdkrw_realtime": snap.usdkrw_realtime,
        "es_futures": snap.es_futures,
        "es_futures_change_pct": snap.es_futures_change_pct,
        "nq_futures": snap.nq_futures,
        "nq_futures_change_pct": snap.nq_futures_change_pct,
        "sox": snap.sox,
        "sox_change_pct": snap.sox_change_pct,
    }


def compute_basis_columns(
    *,
    fut_close: float | None,
    k200_close: float | None,
    trade_date: date,
    risk_free_rate: float,
) -> dict[str, Any]:
    """Market basis + deviation from theoretical fair value.

    Reuses ``shared/arbitrage/basis_calculator.py`` for the fair-value formula;
    days-to-expiry comes from the KOSPI200 quarterly front-month calendar.
    """
    if fut_close is None or k200_close is None or k200_close <= 0:
        return {}
    from shared.arbitrage.basis_calculator import BasisCalculator
    from shared.arbitrage.config import ArbitrageConfig
    from shared.instruments.futures import (
        get_expiry_date,
        get_front_month_code,
        parse_code,
    )

    front = get_front_month_code("kospi200", trade_date, legacy=False)
    year, month = parse_code(front)
    days_to_expiry = max((get_expiry_date(year, month) - trade_date).days, 0)
    calculator = BasisCalculator(ArbitrageConfig(risk_free_rate=risk_free_rate))
    fair_value = calculator.calculate_fair_value(k200_close, days_to_expiry)
    return {
        "basis": fut_close - k200_close,
        "basis_dev": fut_close - fair_value,
        "days_to_expiry": days_to_expiry,
    }


# ---------------------------------------------------------------------------
# Redis publication
# ---------------------------------------------------------------------------


def _flatten(row: dict[str, Any]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for key, value in row.items():
        if value is None or (isinstance(value, float) and value != value):
            fields[key] = ""
        elif isinstance(value, (list, tuple, dict)):
            fields[key] = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, (date, datetime)):
            fields[key] = value.isoformat()
        else:
            fields[key] = str(value)
    return fields


def publish_row(
    redis: Any, config: MarketStructureCollectorConfig, row: dict[str, Any]
) -> None:
    """Publish the composed row to Redis DB 1 (hash + stream, both with TTL)."""
    fields = _flatten(row)
    latest_key = config.redis.latest_key
    # delete-then-hset so fields from a previous snapshot never linger.
    redis.delete(latest_key)
    redis.hset(latest_key, mapping=fields)
    redis.expire(latest_key, config.redis.latest_ttl_seconds)

    stream_key = config.redis.stream_key
    redis.xadd(stream_key, fields, maxlen=config.redis.stream_maxlen, approximate=True)
    redis.expire(stream_key, config.redis.stream_ttl_seconds)


def _publish_cum_window(
    redis: Any,
    config: MarketStructureCollectorConfig,
    window: list[list[Any]],
    cum: float | None,
) -> None:
    payload = json.dumps(
        {"window": window, "cum": cum, "updated_at": _now_kst().isoformat()},
        ensure_ascii=False,
    )
    redis.set(config.redis.cum20_key, payload, ex=config.redis.cum20_ttl_seconds)


# ---------------------------------------------------------------------------
# close mode
# ---------------------------------------------------------------------------


async def collect_close(
    *,
    kis_client: Any,
    krx_collector: Any,
    store: Any,
    redis: Any,
    config: MarketStructureCollectorConfig,
    trade_date: date | None = None,
    calendar: Any = None,
) -> int:
    """Collect and persist the finalized ``close`` snapshot for ``trade_date``."""
    day = _resolve_trade_date(trade_date)
    if calendar is None:
        from shared.calendar import MarketCalendar

        calendar = MarketCalendar()
    if not calendar.is_market_day(day):
        logger.info("%s is not a market day; skipping close collection", day)
        return 0

    row: dict[str, Any] = {}

    async def _component(name: str, coro: Any) -> None:
        try:
            row.update(await coro)
        except Exception as exc:  # noqa: BLE001 — per-component degradation
            logger.warning("market-structure %s collection failed: %s", name, exc)

    await _component("foreign_futures", _collect_foreign_futures(kis_client, config))
    await _component("program", _collect_program(kis_client, config, day))
    await _component("futures_quote", _collect_futures_quote(kis_client, config))
    await _component("k200", _collect_k200(kis_client, config))
    try:
        row.update(_collect_stock_investor(krx_collector))
    except Exception as exc:  # noqa: BLE001
        logger.warning("market-structure stock_investor collection failed: %s", exc)
    try:
        row.update(_collect_macro(redis, config))
    except Exception as exc:  # noqa: BLE001
        logger.warning("market-structure macro read failed: %s", exc)

    row.update(
        compute_basis_columns(
            fut_close=row.get("fut_close"),
            k200_close=row.get("k200_close"),
            trade_date=day,
            risk_free_rate=config.basis.risk_free_rate,
        )
    )

    # -- derived values against prior close history --------------------------
    history = _load_close_history(store, day, config.derived.history_lookback_days)

    if _is_present(row.get("fut_foreign_net_qty")):
        window = derived.update_cum_window(
            _load_cum_window(redis, config, history),
            day,
            float(row["fut_foreign_net_qty"]),
            config.derived.foreign_cum_window_days,
        )
        row["fut_foreign_net_qty_cum20"] = derived.cum_window_sum(window)
        try:
            _publish_cum_window(redis, config, window, row["fut_foreign_net_qty_cum20"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("cum20 window publish failed: %s", exc)

    row["oi_price_signal"] = derived.oi_price_signal(
        row.get("fut_change_pct"), row.get("fut_oi_change")
    )

    if _is_present(row.get("basis_dev")):
        basis_series = derived.clean_series(_history_series(history, "basis_dev")) + [
            float(row["basis_dev"])
        ]
        row["basis_dev_ma5"] = derived.moving_average(
            basis_series, config.derived.basis_dev_ma_days
        )

    if _is_present(row.get("usdkrw")):
        fx_series = derived.clean_series(_history_series(history, "usdkrw")) + [
            float(row["usdkrw"])
        ]
        row["usdkrw_ret_5d"] = derived.pct_return(
            fx_series, config.derived.usdkrw_ret_days
        )

    if _is_present(row.get("k200_close")):
        k200_series = derived.clean_series(_history_series(history, "k200_close")) + [
            float(row["k200_close"])
        ]
        mas: list[float | None] = []
        for window_days in config.derived.k200_ma_windows:
            ma = derived.moving_average(k200_series, window_days)
            row[f"k200_ma{window_days}"] = ma
            mas.append(ma)
        row["k200_ma_alignment"] = derived.ma_alignment(mas)
        row["k200_ret_20d"] = derived.pct_return(
            k200_series, config.derived.k200_ret_days
        )

    coverage, missing = _coverage(row, config.components)
    row["coverage_ratio"] = coverage
    row["missing_components"] = missing
    row["asof_ts"] = _now_kst()

    store.replace_day(day, _SNAPSHOT_CLOSE, row)
    publish_row(
        redis,
        config,
        {"trade_date": day, "snapshot": _SNAPSHOT_CLOSE, "asof": row["asof_ts"], **row},
    )
    logger.info(
        "market-structure close row stored for %s (coverage=%.3f missing=%s)",
        day,
        coverage,
        missing,
    )
    return 0


# ---------------------------------------------------------------------------
# premarket mode
# ---------------------------------------------------------------------------


def _read_night_close(
    redis: Any, config: MarketStructureCollectorConfig
) -> dict[str, Any]:
    """Optional Wave 2e night-futures capture, ``night_``-prefixed columns."""
    key = config.redis.night_close_key
    payload: dict[str, Any] = {}
    try:
        raw_hash = redis.hgetall(key)
    except Exception:  # noqa: BLE001
        raw_hash = {}
    if raw_hash:
        payload = dict(raw_hash)
    else:
        try:
            raw = redis.get(key)
        except Exception:  # noqa: BLE001
            raw = None
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    payload = parsed
            except (TypeError, ValueError):
                payload = {}
    if not payload:
        return {}

    columns: dict[str, Any] = {}
    for key_name, value in payload.items():
        name = str(key_name)
        column = name if name.startswith("night_") else f"night_{name}"
        if any(marker in name.lower() for marker in _NIGHT_TEXT_MARKERS):
            columns[column] = str(value)
            continue
        parsed_value = _parse_number(value)
        if parsed_value is not None:
            columns[column] = parsed_value
    return columns


async def collect_premarket(
    *,
    store: Any,
    redis: Any,
    config: MarketStructureCollectorConfig,
    trade_date: date | None = None,
    calendar: Any = None,
) -> int:
    """Compose the pre-open ``premarket`` snapshot (prev close + overnight)."""
    day = _resolve_trade_date(trade_date)
    if calendar is None:
        from shared.calendar import MarketCalendar

        calendar = MarketCalendar()
    if not calendar.is_market_day(day):
        logger.info("%s is not a market day; skipping premarket collection", day)
        return 0

    row: dict[str, Any] = {}

    prev_close = store.read_latest(snapshot=_SNAPSHOT_CLOSE)
    if prev_close:
        prev_day = prev_close.get("trade_date")
        if isinstance(prev_day, date) and prev_day >= day:
            logger.warning(
                "latest close row (%s) is not before %s; skipping carry-forward",
                prev_day,
                day,
            )
        else:
            for column, value in prev_close.items():
                if column in _NON_CARRY_COLUMNS or not _is_present(value):
                    continue
                row[column] = value
            if isinstance(prev_day, date):
                row["source_trade_date"] = prev_day.isoformat()
    else:
        logger.warning("no prior close row found; premarket row is overnight-only")

    # Overnight signals overwrite carried values (fresher pre-open knowledge).
    try:
        row.update(
            {
                key: value
                for key, value in _collect_macro(redis, config).items()
                if _is_present(value)
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("market-structure macro read failed: %s", exc)
    row.update(_read_night_close(redis, config))

    coverage, missing = _coverage(row, config.components)
    row["coverage_ratio"] = coverage
    row["missing_components"] = missing
    row["asof_ts"] = _now_kst()

    store.replace_day(day, _SNAPSHOT_PREMARKET, row)
    publish_row(
        redis,
        config,
        {
            "trade_date": day,
            "snapshot": _SNAPSHOT_PREMARKET,
            "asof": row["asof_ts"],
            **row,
        },
    )
    logger.info(
        "market-structure premarket row stored for %s (coverage=%.3f missing=%s)",
        day,
        coverage,
        missing,
    )
    return 0


# ---------------------------------------------------------------------------
# CLI glue
# ---------------------------------------------------------------------------


def _futures_kis_auth_config() -> Any:
    """Futures-domain KIS auth (token cache reused via KISAuthManager)."""
    from shared.config.secrets import SecretsManager
    from shared.kis.auth import KISAuthConfig

    is_real = str(SecretsManager.kis_market("futures")).lower() == "real"
    if not is_real:
        logger.warning(
            "market-structure KIS TRs are REAL-investment only; mock credentials"
            " will leave KIS components missing"
        )
    return KISAuthConfig(
        app_key=SecretsManager.kis_app_key("futures") or "",
        app_secret=SecretsManager.kis_app_secret("futures") or "",
        is_real=is_real,
    )


async def _cli(mode: str) -> int:
    import redis as redis_lib

    from shared.storage.market_structure_store import create_market_structure_store

    config = MarketStructureCollectorConfig.from_yaml()
    redis_client = redis_lib.Redis.from_url(redis_url_from_env(), decode_responses=True)
    store = create_market_structure_store()

    try:
        if mode == "close":
            from shared.kis.client import KISClient
            from shared.llm.collectors import KRXDataCollector

            kis_client = KISClient(_futures_kis_auth_config())
            try:
                return await collect_close(
                    kis_client=kis_client,
                    krx_collector=KRXDataCollector(),
                    store=store,
                    redis=redis_client,
                    config=config,
                )
            finally:
                await kis_client.close()
        elif mode == "premarket":
            return await collect_premarket(
                store=store, redis=redis_client, config=config
            )
        print(f"unknown mode: {mode}", file=sys.stderr)
        return 2
    finally:
        redis_client.close()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    parser = argparse.ArgumentParser(description="Market-structure daily collector")
    parser.add_argument("mode", choices=["close", "premarket"])
    args = parser.parse_args()
    return asyncio.run(_cli(args.mode))


if __name__ == "__main__":
    sys.exit(main())
