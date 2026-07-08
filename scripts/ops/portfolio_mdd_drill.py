"""Offline portfolio-MDD circuit-breaker drill (Phase 3 gate requirement).

Walks a simulated month of Track-B losses through the REAL Phase 3B path —
RuntimeLedger trades → equity/stage evaluation → Redis contract publish →
``PortfolioMddFilter`` verdicts → FULL_STOP sentinel/flag trip — and verifies
every expected transition:

    NORMAL → REDUCE (−5%) → HALT_NEW (−8%) → FULL_STOP (−12%)

Modes:

* default (dry-run): fully sandboxed. Temp SQLite ledger, in-memory Redis
  stub, temp sentinel path, breaker mode forced to ``enforce`` INSIDE the
  sandbox only. Touches no real infrastructure. Exit 0 = all checks PASS.
* ``--execute``: additionally performs the REAL FULL_STOP trip — writes the
  production kill-switch sentinel file and sets ``futures:live:suspended``
  on the configured Redis — then prints the rollback (원복) procedure.
  Use only for scheduled ops drills.

Usage:
    python -m scripts.ops.portfolio_mdd_drill            # dry-run (safe)
    python -m scripts.ops.portfolio_mdd_drill --execute  # real trip + rollback guide
"""

from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from services.portfolio_monitor.main import (
    default_sentinel_path,
    default_suspend_key,
    run_snapshot,
    trip_full_stop,
)
from shared.portfolio.config import TRACK_FUTURES, TRACK_STOCK, PortfolioConfig
from shared.portfolio.equity import (
    STAGE_FULL_STOP,
    STAGE_HALT_NEW,
    STAGE_NORMAL,
    STAGE_REDUCE,
    PortfolioEquitySnapshot,
    TrackEquity,
    evaluate_snapshot,
)
from shared.risk.filters.portfolio_mdd import PortfolioMddFilter
from shared.storage.runtime_ledger import SQLiteRuntimeLedger

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sandbox infrastructure (dry-run) — no external deps, no real I/O
# ---------------------------------------------------------------------------


class MiniRedis:
    """Tiny in-memory stand-in for the handful of Redis calls the drill uses."""

    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = {}
        self.strings: dict[str, str] = {}
        self.streams: dict[str, list[dict[str, str]]] = {}
        self.ttls: dict[str, int] = {}

    def delete(self, key: str) -> int:
        existed = int(key in self.hashes or key in self.strings)
        self.hashes.pop(key, None)
        self.strings.pop(key, None)
        return existed

    def hset(self, key: str, mapping: dict[str, str]) -> int:
        self.hashes.setdefault(key, {}).update(
            {str(k): str(v) for k, v in mapping.items()}
        )
        return len(mapping)

    def hgetall(self, key: str) -> dict[str, str]:
        return dict(self.hashes.get(key, {}))

    def expire(self, key: str, seconds: int) -> bool:
        self.ttls[key] = int(seconds)
        return True

    def set(self, key: str, value: str) -> bool:
        self.strings[key] = str(value)
        return True

    def get(self, key: str) -> str | None:
        return self.strings.get(key)

    def xadd(
        self,
        key: str,
        fields: dict[str, str],
        maxlen: int = 0,
        approximate: bool = True,  # noqa: ARG002 — real-Redis signature parity
    ) -> str:
        entries = self.streams.setdefault(key, [])
        entries.append({str(k): str(v) for k, v in fields.items()})
        if maxlen and len(entries) > maxlen:
            del entries[: len(entries) - maxlen]
        return f"{len(entries)}-0"


class _AlwaysOpenCalendar:
    def is_market_day(self, _day: date) -> bool:
        return True


@dataclass
class _StepExpectation:
    """One drill day: an equity level and the stage/filter verdict it owes."""

    label: str
    equity_ratio: float  # target total equity as a fraction of capital
    stage: str
    filter_passes: bool
    filter_size: float


def _check(
    results: list[tuple[str, bool, str]], name: str, ok: bool, detail: str
) -> None:
    results.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")


# ---------------------------------------------------------------------------
# Dry-run drill
# ---------------------------------------------------------------------------


def run_dry_drill() -> int:
    config = PortfolioConfig.load_or_default().model_copy(deep=True)
    config.circuit_breaker.mode = "enforce"  # sandbox-only override
    stages = config.circuit_breaker.monthly_mdd_stages
    reduce_factor = stages.reduce.new_entry_size_factor

    capital_total = config.capital_base.track_b_stock_krw + (
        config.capital_base.track_c_futures_krw
    )
    if config.capital_base.track_a_core_krw:
        capital_total += config.capital_base.track_a_core_krw

    # Scenario: sit just past each threshold (thresholds are inclusive, so
    # aim slightly deeper to stay robust to float formatting round-trips).
    steps = [
        _StepExpectation("baseline", 1.00, STAGE_NORMAL, True, 1.0),
        _StepExpectation(
            "reduce",
            1.0 + stages.reduce.threshold - 0.005,
            STAGE_REDUCE,
            True,
            reduce_factor,
        ),
        _StepExpectation(
            "halt_new",
            1.0 + stages.halt_new.threshold - 0.005,
            STAGE_HALT_NEW,
            False,
            1.0,
        ),
        _StepExpectation(
            "full_stop",
            1.0 + stages.full_stop.threshold - 0.005,
            STAGE_FULL_STOP,
            False,
            1.0,
        ),
    ]

    results: list[tuple[str, bool, str]] = []
    start_day = date(2026, 7, 6)  # Monday; sandbox calendar is always open

    with tempfile.TemporaryDirectory(prefix="portfolio_mdd_drill_") as tmp:
        tmp_path = Path(tmp)
        ledger = SQLiteRuntimeLedger(tmp_path / "drill_ledger.db")
        redis = MiniRedis()
        sentinel = tmp_path / "kis_kill_switch.tripped"
        suspend_key = "futures:live:suspended"
        latest_key = config.monitor.redis.latest_key

        # The drill replays fixed calendar days, so the filter's staleness
        # clock must follow the simulated day (not wall time) or snapshots
        # older than stale_max_age_seconds fail open once real time moves
        # past start_day + the allowance.
        sim_clock = {"now": datetime.combine(start_day, datetime.min.time())}
        mdd_filter = PortfolioMddFilter(
            reduce_size_factor=reduce_factor,
            latest_key=latest_key,
            stale_max_age_seconds=93600,
            snapshot_provider=lambda: redis.hgetall(latest_key) or None,
            now_provider=lambda: sim_clock["now"],
        )

        cumulative_pnl = 0.0
        for index, step in enumerate(steps):
            day = start_day + timedelta(days=index)
            sim_clock["now"] = datetime.combine(day, datetime.min.time()).replace(
                hour=19
            )
            target_equity = capital_total * step.equity_ratio
            delta = target_equity - capital_total - cumulative_pnl
            cumulative_pnl += delta
            ledger.record_trade(
                {
                    "trade_id": f"drill-{index}",
                    "asset_class": "stock",
                    "symbol": "DRILL",
                    "side": "sell",
                    "pnl": delta,
                    "exit_time": f"{day.isoformat()}T15:30:00",
                },
                track_id=TRACK_STOCK,
            )

            run_snapshot(
                config=config,
                ledger=ledger,
                redis=redis,
                positions_providers={
                    TRACK_STOCK: lambda: [],
                    TRACK_FUTURES: lambda: [],
                },
                calendar=_AlwaysOpenCalendar(),
                notifier=None,
                trade_date=day,
                now=sim_clock["now"],
                sentinel_path=str(sentinel),
                suspend_key=suspend_key,
            )

            print(f"\nday {index + 1} ({step.label}): equity → {target_equity:,.0f}")
            published = redis.hgetall(latest_key)
            _check(
                results,
                f"{step.label}: published stage",
                published.get("stage") == step.stage,
                f"stage={published.get('stage')!r} expected={step.stage!r}",
            )

            verdict = mdd_filter.check(signal=None, state_snapshot=None)  # type: ignore[arg-type]
            _check(
                results,
                f"{step.label}: filter verdict",
                verdict.passed == step.filter_passes
                and (
                    not verdict.passed
                    or abs(verdict.size_multiplier - step.filter_size) < 1e-9
                ),
                f"passed={verdict.passed} size={verdict.size_multiplier}"
                f" skip={verdict.skip_reason}",
            )

        _check(
            results,
            "full_stop: sentinel tripped (tmp path)",
            sentinel.exists(),
            str(sentinel),
        )
        _check(
            results,
            "full_stop: suspend flag set (sandbox redis)",
            redis.get(suspend_key) == "1",
            f"{suspend_key}={redis.get(suspend_key)!r}",
        )

        # Latch check: recover equity fully back to the capital base — the
        # raw stage returns to NORMAL but the latched stage must stay
        # FULL_STOP for the remainder of the month (stage_latch=true).
        recovery_day = start_day + timedelta(days=len(steps))
        recovered = TrackEquity(
            track_id=TRACK_STOCK,
            equity=capital_total,
            capital_base=capital_total,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            missing_components=(),
            degraded=False,
        )
        rows = ledger.query_portfolio_equity_daily({"limit": 0})
        snapshot_after: PortfolioEquitySnapshot = evaluate_snapshot(
            trade_date=recovery_day,
            tracks={TRACK_STOCK: recovered},
            month_history=rows,
            stages=stages,
            stage_latch=config.circuit_breaker.stage_latch,
            mode=config.circuit_breaker.mode,
            asof_ts=datetime.combine(recovery_day, datetime.min.time()),
        )
        _check(
            results,
            "latch: stage holds after recovery",
            snapshot_after.stage == STAGE_FULL_STOP
            and snapshot_after.raw_stage == STAGE_NORMAL,
            f"stage={snapshot_after.stage} raw={snapshot_after.raw_stage}"
            f" (latch={config.circuit_breaker.stage_latch})",
        )

        ledger.close()

    failed = [name for name, ok, _ in results if not ok]
    print(f"\ndrill summary: {len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("FAILED checks:", ", ".join(failed))
        return 1
    print("dry-run drill PASS — no real infrastructure was touched.")
    return 0


# ---------------------------------------------------------------------------
# --execute: real trip + rollback guide
# ---------------------------------------------------------------------------


def run_execute_trip() -> int:
    import redis as redis_lib

    from shared.config.runtime_defaults import redis_url_from_env
    from shared.storage import SQLiteRuntimeLedger as _Ledger
    from shared.storage.config import StorageConfig

    sentinel_path = default_sentinel_path()
    suspend_key = default_suspend_key()
    redis_client = redis_lib.Redis.from_url(redis_url_from_env(), decode_responses=True)
    storage = StorageConfig.load_or_default()
    ledger = _Ledger(storage.runtime_storage.sqlite)

    now = datetime.now()
    snapshot = PortfolioEquitySnapshot(
        trade_date=now.date(),
        track_a_equity=None,
        track_b_equity=None,
        track_c_equity=None,
        total_equity=0.0,
        month_start_equity=0.0,
        month_peak_equity=0.0,
        monthly_mdd_pct=0.0,
        raw_stage=STAGE_FULL_STOP,
        stage=STAGE_FULL_STOP,
        prev_stage=None,
        stage_changed=True,
        latched=False,
        mode="enforce",
        degraded=False,
        missing_components=("drill_execute",),
        asof_ts=now,
    )

    print("EXECUTE drill: tripping REAL kill-switch sentinel + suspend flag ...")
    try:
        actions = trip_full_stop(
            redis=redis_client,
            ledger=ledger,
            snapshot=snapshot,
            sentinel_path=sentinel_path,
            suspend_key=suspend_key,
        )
    finally:
        redis_client.close()
        ledger.close()

    print(f"actions performed: {actions or ['none (already tripped?)']}")
    print(
        "\n=== 원복 절차 (rollback) ===\n"
        f"1. sentinel 파일 삭제:        rm '{sentinel_path}'\n"
        f"2. suspend 플래그 해제:       redis-cli -n 1 DEL {suspend_key}\n"
        "3. 대시보드 상태 복원:        python -m services.portfolio_monitor.main\n"
        "   (실제 equity 기준 stage를 재발행해 portfolio:equity:latest를 복원)\n"
        "4. kill_switch / order_router 컨테이너 재기동 후 정상 기동 로그 확인\n"
        "5. RuntimeLedger risk_events에 drill 트립 감사 레코드가 남았는지 확인"
    )
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(
        description="Portfolio-MDD circuit-breaker drill (dry-run by default)"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="REAL trip: write the production sentinel + suspend flag, then "
        "print the rollback procedure",
    )
    args = parser.parse_args()
    if args.execute:
        return run_execute_trip()
    return run_dry_drill()


if __name__ == "__main__":
    sys.exit(main())
