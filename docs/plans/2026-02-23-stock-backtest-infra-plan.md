# Stock Backtest Infrastructure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable 6-month stock minute data collection from KIS API and ClickHouse-direct backtesting to diagnose bb_reversion performance degradation.

**Architecture:** Extend the existing `backfill_stock_minute()` to support 180-day collection with resume capability, then add `--symbol`/`--tier` options to `sts backtest run` that query ClickHouse directly (bypassing CSV). The backtest engine itself is unchanged — only the data loading layer is extended.

**Tech Stack:** Python 3.11+, Click CLI, clickhouse-connect, httpx (async), pandas

---

### Task 1: Remove 30-Day Hardcap and Add Inter-Day Throttling

**Files:**
- Modify: `shared/collector/historical/stock.py:717-778` (the `backfill_stock_minute` function)

**Step 1: Update the hardcap**

In `shared/collector/historical/stock.py`, line 734:

```python
# BEFORE:
    # KIS API limits minute data to 30 days
    days = min(days, 30)

# AFTER:
    days = min(days, 180)
```

**Step 2: Add inter-day sleep to avoid rate limits during long backfills**

In the same function, around line 764-770 (the day loop), add a 1-second sleep between each day's batch:

```python
# BEFORE (inside the for loop, after collect_stock_batch):
            rows = await collect_stock_batch(client, db_client, batch)
            total_rows += rows

# AFTER:
            rows = await collect_stock_batch(client, db_client, batch)
            total_rows += rows

            # Throttle between days to avoid API rate limits on long backfills
            if len(trading_days) > 30:
                await asyncio.sleep(1.0)
```

**Step 3: Update the CLI help text**

In `cli/main.py`, line 742:

```python
# BEFORE:
    help="Number of days to backfill (max 30, default: 7)",

# AFTER:
    help="Number of days to backfill (max 180, default: 7)",
```

**Step 4: Test manually**

Run: `cd /home/deploy/project/kis_unified_sts && python -c "from shared.collector.historical.stock import backfill_stock_minute; print('import ok')"`
Expected: `import ok` (no syntax errors)

**Step 5: Commit**

```bash
git add shared/collector/historical/stock.py cli/main.py
git commit -m "feat: extend stock backfill to 180 days with inter-day throttling"
```

---

### Task 2: Add Resume Capability for Long Backfills

**Files:**
- Modify: `shared/collector/historical/stock.py:570-588` (state functions) and `shared/collector/historical/stock.py:717-778` (`backfill_stock_minute`)

**Step 1: Enhance state tracking to record per-day completion**

The existing `load_collection_state()`/`save_collection_state()` at lines 570-588 are unused. Enhance them to track completed (code, date) pairs:

```python
# Replace load_collection_state (line 570-578):
def load_collection_state() -> Dict:
    """Load collection state from file."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load state file: {e}")
    return {"completed_days": {}, "last_run": None}


# Replace save_collection_state (line 581-588):
def save_collection_state(state: Dict):
    """Save collection state to file."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Failed to save state file: {e}")
```

**Step 2: Wire state tracking into `backfill_stock_minute`**

Add resume logic: skip days already fully collected. Modify `backfill_stock_minute` (lines 717-778):

```python
async def backfill_stock_minute(
    days: int = 30,
    codes: List[str] = None,
    verbose: bool = True,
    resume: bool = True,
) -> int:
    """
    Backfill stock minute data for specified days.

    Args:
        days: Number of days to backfill (max 180)
        codes: Specific codes to backfill (None = all universe)
        verbose: Print progress
        resume: Skip already-collected days (for long backfills)

    Returns:
        Total rows collected
    """
    days = min(days, 180)

    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    trading_days = get_trading_days_range(start_date, end_date)
    if not trading_days:
        if verbose:
            print("No trading days in range")
        return 0

    # Select codes
    if codes:
        selected_codes = list(dict.fromkeys(codes))
    else:
        selected_codes = [s["code"] for s in STOCK_UNIVERSE]

    # Resume: load state and skip completed days
    state = load_collection_state() if resume else {"completed_days": {}}
    completed = state.get("completed_days", {})
    codes_key = ",".join(sorted(selected_codes))

    if resume:
        original_count = len(trading_days)
        trading_days = [
            d for d in trading_days
            if f"{d.isoformat()}:{codes_key}" not in completed
        ]
        skipped = original_count - len(trading_days)
        if skipped > 0 and verbose:
            print(f"Resuming: skipping {skipped} already-collected days")

    if not trading_days:
        if verbose:
            print("All days already collected (use --no-resume to force re-collect)")
        return 0

    if verbose:
        print(f"Stock Minute Backfill")
        print(f"Trading days: {len(trading_days)}")
        print(f"Date range: {trading_days[0]} ~ {trading_days[-1]}")
        print(f"Stocks: {len(selected_codes)}")

    ensure_stock_database()
    db_client = get_stock_db_client()

    total_rows = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        for day_idx, day in enumerate(reversed(trading_days), start=1):
            tasks = [(code, day) for code in selected_codes]

            if verbose:
                print(f"{day_idx}/{len(trading_days)} {day} stocks={len(tasks)}")

            rows = await collect_stock_batch(client, db_client, tasks)
            total_rows += rows

            # Mark day as completed and save state
            if resume and rows > 0:
                completed[f"{day.isoformat()}:{codes_key}"] = True
                state["completed_days"] = completed
                state["last_run"] = datetime.now().isoformat()
                save_collection_state(state)

            # Throttle between days for long backfills
            if len(trading_days) > 30:
                await asyncio.sleep(1.0)

    db_client.close()

    if verbose:
        print(f"Backfill complete. Total rows: {total_rows}")

    return total_rows
```

**Step 3: Add `--no-resume` CLI flag**

In `cli/main.py`, add a flag to the `stock_backfill_run` command (after line 748):

```python
@click.option(
    "--no-resume",
    is_flag=True,
    default=False,
    help="Force re-collect all days (ignore saved state)",
)
def stock_backfill_run(days: int, codes: tuple, no_resume: bool):
```

And update the handler body (around line 765):

```python
    asyncio.run(backfill_stock_minute(days=days, codes=codes_list, resume=not no_resume))
```

**Step 4: Test import**

Run: `cd /home/deploy/project/kis_unified_sts && python -c "from shared.collector.historical.stock import backfill_stock_minute; import inspect; sig = inspect.signature(backfill_stock_minute); print(sig)"`
Expected: Shows `resume` parameter in signature

**Step 5: Commit**

```bash
git add shared/collector/historical/stock.py cli/main.py
git commit -m "feat: add resume capability for long stock backfills"
```

---

### Task 3: Add ClickHouse Data Loader Function

**Files:**
- Modify: `shared/collector/historical/stock.py` (add new function after `get_stock_collection_status`)

**Step 1: Add `load_stock_minute_from_clickhouse()` function**

Add this function at the end of the "Main Collection Functions" section in `shared/collector/historical/stock.py`:

```python
def load_stock_minute_from_clickhouse(
    code: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> "pd.DataFrame":
    """
    Load stock minute data from ClickHouse as a DataFrame suitable for BacktestEngine.

    Args:
        code: Stock code (e.g., '005930')
        start_date: Start date filter (inclusive). None = no lower bound.
        end_date: End date filter (inclusive). None = no upper bound.

    Returns:
        DataFrame with columns: code, datetime, open, high, low, close, volume
        Sorted by datetime ascending.

    Raises:
        ValueError: If no data found for the given code/date range.
    """
    import pandas as pd

    db_client = get_stock_db_client()

    conditions = [f"code = '{code}'"]
    if start_date:
        conditions.append(f"datetime >= '{start_date.isoformat()}'")
    if end_date:
        conditions.append(f"datetime <= '{end_date.isoformat()} 23:59:59'")

    where = " AND ".join(conditions)
    query = f"""
        SELECT code, datetime, open, high, low, close, volume
        FROM minute_candles
        WHERE {where}
        ORDER BY datetime ASC
    """

    result = db_client.query(query)
    db_client.close()

    if not result.result_rows:
        raise ValueError(f"No data found for {code} in ClickHouse (range: {start_date} ~ {end_date})")

    df = pd.DataFrame(
        result.result_rows,
        columns=["code", "datetime", "open", "high", "low", "close", "volume"],
    )

    # Ensure datetime is pandas Timestamp (ClickHouse returns Python datetime)
    df["datetime"] = pd.to_datetime(df["datetime"])

    return df
```

**Step 2: Test the function**

Run:
```bash
cd /home/deploy/project/kis_unified_sts && python -c "
from shared.collector.historical.stock import load_stock_minute_from_clickhouse
df = load_stock_minute_from_clickhouse('005930')
print(f'Rows: {len(df)}, Columns: {list(df.columns)}')
print(f'Range: {df[\"datetime\"].min()} ~ {df[\"datetime\"].max()}')
print(df.head(3))
"
```
Expected: DataFrame with 10K+ rows for Samsung, correct columns, datetime sorted ascending.

**Step 3: Commit**

```bash
git add shared/collector/historical/stock.py
git commit -m "feat: add ClickHouse data loader for backtest"
```

---

### Task 4: Add `--symbol` and `--tier` Options to Backtest CLI

**Files:**
- Modify: `cli/main.py:69-234` (the `backtest_run` command)

**Step 1: Add Click options**

Add these options after the existing `--data` option (after line 105):

```python
@click.option(
    "--symbol",
    default=None,
    help="Stock code to load from ClickHouse (e.g., 005930)",
)
@click.option(
    "--tier",
    default=None,
    type=click.Choice(["top", "mid", "bottom", "all"]),
    help="Run backtest across tier stocks from ClickHouse (top/mid/bottom/all)",
)
```

Update the function signature (line 117):

```python
def backtest_run(
    strategy: str,
    asset: str,
    start,
    end,
    capital: float,
    data: str | None,
    symbol: str | None,
    tier: str | None,
    track: bool,
    experiment: str | None,
):
```

**Step 2: Add ClickHouse data loading logic**

Replace the data loading block (lines 165-176) with:

```python
    # 데이터 로드 및 검증
    if data:
        # CSV 파일 로드 (기존 방식)
        try:
            df = validate_csv_file(data)
            click.echo(f"Loaded data from CSV: {len(df)} rows")
        except ValidationError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    elif symbol:
        # ClickHouse에서 단일 종목 로드
        from shared.collector.historical.stock import load_stock_minute_from_clickhouse

        try:
            start_d = start.date() if start else None
            end_d = end.date() if end else None
            df = load_stock_minute_from_clickhouse(symbol, start_d, end_d)
            click.echo(f"Loaded {symbol} from ClickHouse: {len(df)} rows")
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    elif tier:
        # 티어별 순회 백테스트 → 별도 함수로 위임
        _run_tier_backtest(
            strategy=strategy,
            asset=asset,
            tier=tier,
            start=start,
            end=end,
            capital=capital,
            track=track,
            experiment=experiment,
        )
        return
    else:
        click.echo("Error: Data source required. Use --data, --symbol, or --tier", err=True)
        click.echo("  --data <path>     Load from CSV file")
        click.echo("  --symbol <code>   Load from ClickHouse (e.g., --symbol 005930)")
        click.echo("  --tier <tier>     Run across tier stocks (top/mid/bottom/all)")
        sys.exit(1)
```

**Step 3: Implement `_run_tier_backtest` helper**

Add this function BEFORE the `backtest_run` command (around line 65):

```python
def _run_tier_backtest(
    strategy: str,
    asset: str,
    tier: str,
    start,
    end,
    capital: float,
    track: bool,
    experiment: str | None,
):
    """Run backtest across multiple stocks by tier, print summary table."""
    from shared.backtest import BacktestConfig, BacktestEngine
    from shared.backtest.adapter import BacktestStrategyAdapter
    from shared.backtest.config import RiskConfig
    from shared.collector.historical.stock import (
        STOCK_UNIVERSE,
        load_stock_minute_from_clickhouse,
    )
    from shared.config.loader import ConfigLoader
    from shared.strategy.registry import StrategyFactory, register_builtin_components

    register_builtin_components()

    # Filter stocks by tier
    if tier == "all":
        stocks = STOCK_UNIVERSE
    else:
        stocks = [s for s in STOCK_UNIVERSE if s["tier"] == tier]

    click.echo(f"Tier backtest: {strategy} ({asset}) — {len(stocks)} stocks ({tier})")
    click.echo("=" * 80)

    # Load strategy config once
    strategy_config = ConfigLoader.load_strategy(asset, strategy)
    bt_override = strategy_config.get("strategy", {}).get("backtest", {})
    bt_capital = bt_override.get("initial_capital", capital)

    start_d = start.date() if start else None
    end_d = end.date() if end else None

    results = []

    for stock in stocks:
        code = stock["code"]
        name = stock["name"]
        stock_tier = stock["tier"]

        try:
            df = load_stock_minute_from_clickhouse(code, start_d, end_d)
        except ValueError:
            click.echo(f"  {code} {name}: No data — skipped")
            results.append({
                "code": code, "name": name, "tier": stock_tier,
                "trades": 0, "return_pct": 0, "win_rate": 0,
                "sharpe": 0, "mdd": 0, "status": "NO_DATA",
            })
            continue

        # Create fresh strategy + config for each stock
        config = BacktestConfig.stock(initial_capital=bt_capital)
        if "risk" in bt_override:
            config.risk = RiskConfig.from_dict(bt_override["risk"])

        trading_strategy = StrategyFactory.create(strategy_config)
        adapted = BacktestStrategyAdapter(trading_strategy, strategy_config)
        engine = BacktestEngine(adapted, config)

        result = engine.run(df)

        click.echo(
            f"  {code} {name}: "
            f"trades={result.total_trades} "
            f"return={result.total_return_pct:+.2f}% "
            f"WR={result.win_rate:.0f}% "
            f"Sharpe={result.sharpe_ratio:.2f}"
        )

        results.append({
            "code": code, "name": name, "tier": stock_tier,
            "trades": result.total_trades,
            "return_pct": result.total_return_pct,
            "win_rate": result.win_rate,
            "sharpe": result.sharpe_ratio,
            "mdd": result.max_drawdown_pct,
            "status": "OK",
        })

    # Print summary table
    click.echo("\n" + "=" * 80)
    click.echo("Summary Table")
    click.echo("=" * 80)
    click.echo(f"{'Code':<8} {'Name':<12} {'Tier':<7} {'Trades':>6} {'Return%':>9} {'WR%':>5} {'Sharpe':>7} {'MDD%':>7}")
    click.echo("-" * 80)

    for r in results:
        if r["status"] == "NO_DATA":
            click.echo(f"{r['code']:<8} {r['name']:<12} {r['tier']:<7} {'—':>6} {'—':>9} {'—':>5} {'—':>7} {'—':>7}")
        else:
            click.echo(
                f"{r['code']:<8} {r['name']:<12} {r['tier']:<7} "
                f"{r['trades']:>6} {r['return_pct']:>+8.2f}% "
                f"{r['win_rate']:>4.0f}% {r['sharpe']:>7.2f} "
                f"{r['mdd']:>6.2f}%"
            )

    # Tier aggregates
    click.echo("\n" + "-" * 80)
    click.echo("Tier Aggregates")
    click.echo("-" * 80)

    for t_label, t_key in [("Top (대형주)", "top"), ("Mid (중형주)", "mid"), ("Bottom (소형주)", "bottom")]:
        tier_results = [r for r in results if r["tier"] == t_key and r["status"] == "OK"]
        if not tier_results:
            continue
        avg_ret = sum(r["return_pct"] for r in tier_results) / len(tier_results)
        avg_wr = sum(r["win_rate"] for r in tier_results) / len(tier_results)
        avg_sharpe = sum(r["sharpe"] for r in tier_results) / len(tier_results)
        total_trades = sum(r["trades"] for r in tier_results)
        click.echo(
            f"  {t_label:<18} stocks={len(tier_results)} "
            f"trades={total_trades} "
            f"avg_return={avg_ret:+.2f}% "
            f"avg_WR={avg_wr:.0f}% "
            f"avg_Sharpe={avg_sharpe:.2f}"
        )

    # Overall
    ok_results = [r for r in results if r["status"] == "OK"]
    if ok_results:
        avg_ret = sum(r["return_pct"] for r in ok_results) / len(ok_results)
        avg_sharpe = sum(r["sharpe"] for r in ok_results) / len(ok_results)
        total_trades = sum(r["trades"] for r in ok_results)
        click.echo(
            f"\n  Overall: stocks={len(ok_results)} "
            f"trades={total_trades} "
            f"avg_return={avg_ret:+.2f}% "
            f"avg_Sharpe={avg_sharpe:.2f}"
        )
```

**Step 4: Verify CLI help**

Run: `cd /home/deploy/project/kis_unified_sts && python -m cli.main backtest run --help`
Expected: Shows `--symbol`, `--tier` options alongside `--data`

**Step 5: Commit**

```bash
git add cli/main.py
git commit -m "feat: add --symbol and --tier options for ClickHouse-direct backtest"
```

---

### Task 5: Enhance `stock-backfill status` with Per-Stock Detail

**Files:**
- Modify: `shared/collector/historical/stock.py` (the `get_stock_collection_status` function)
- Modify: `cli/main.py:815-852` (the `stock_backfill_status` handler)

**Step 1: Find and enhance `get_stock_collection_status`**

Locate the function in `shared/collector/historical/stock.py` and add per-stock detail to its return value. Add a new query that returns per-code stats:

```python
def get_stock_collection_status(days: int = 30) -> Dict:
    """Get collection status with per-stock detail."""
    try:
        db_client = get_stock_db_client()

        # Overall stats
        start_date = (date.today() - timedelta(days=days)).isoformat()
        result = db_client.query(f"""
            SELECT
                count(*) as rows,
                count(DISTINCT toDate(datetime)) as days_collected,
                count(DISTINCT code) as unique_codes,
                min(datetime) as min_datetime,
                max(datetime) as max_datetime
            FROM minute_candles
            WHERE datetime >= '{start_date}'
        """)

        row = result.result_rows[0] if result.result_rows else (0, 0, 0, None, None)

        # Per-stock stats
        per_stock = db_client.query(f"""
            SELECT
                code,
                count(*) as bars,
                count(DISTINCT toDate(datetime)) as trading_days,
                min(datetime) as earliest,
                max(datetime) as latest
            FROM minute_candles
            WHERE datetime >= '{start_date}'
            GROUP BY code
            ORDER BY bars DESC
        """)

        stocks_detail = []
        for sr in per_stock.result_rows:
            stocks_detail.append({
                "code": sr[0],
                "bars": sr[1],
                "trading_days": sr[2],
                "earliest": str(sr[3]) if sr[3] else None,
                "latest": str(sr[4]) if sr[4] else None,
            })

        db_client.close()

        return {
            "table": "minute_candles",
            "rows": row[0],
            "days_collected": row[1],
            "unique_codes": row[2],
            "min_datetime": str(row[3]) if row[3] else None,
            "max_datetime": str(row[4]) if row[4] else None,
            "stocks": stocks_detail,
        }
    except Exception as e:
        return {"error": str(e)}
```

**Step 2: Update CLI status handler to print per-stock table**

In `cli/main.py`, update `stock_backfill_status` (lines 823-852) to print per-stock detail:

```python
    # After the existing summary output, add:
    stocks = status.get("stocks", [])
    if stocks:
        click.echo(f"\n{'Code':<8} {'Bars':>8} {'Days':>5} {'Earliest':<20} {'Latest':<20}")
        click.echo("-" * 65)
        for s in stocks:
            click.echo(
                f"{s['code']:<8} {s['bars']:>8,} {s['trading_days']:>5} "
                f"{s.get('earliest', '—'):<20} {s.get('latest', '—'):<20}"
            )
```

**Step 3: Test**

Run: `cd /home/deploy/project/kis_unified_sts && sts stock-backfill status --days 90`
Expected: Summary stats + per-stock table

**Step 4: Commit**

```bash
git add shared/collector/historical/stock.py cli/main.py
git commit -m "feat: enhance stock-backfill status with per-stock detail"
```

---

### Task 6: Run 6-Month Backfill

**This is a manual execution step, not a code change.**

**Step 1: Run the 180-day backfill**

```bash
cd /home/deploy/project/kis_unified_sts
sts stock-backfill run --days 180
```

Expected: ~90 minutes. Progress printed per day. If interrupted, re-run same command (resume will skip completed days).

**Step 2: Verify data coverage**

```bash
sts stock-backfill status --days 180
```

Expected: 30 stocks, ~120+ trading days, 500K+ rows.

---

### Task 7: Run bb_reversion Performance Analysis

**This is a manual analysis step using the new infrastructure.**

**Step 1: Run tier-all backtest**

```bash
cd /home/deploy/project/kis_unified_sts
sts backtest run -s bb_reversion -a stock --tier all
```

Expected: Per-stock results + tier aggregates + overall summary.

**Step 2: Analyze results**

Look for:
- Which tier performs best/worst?
- How many trades per stock? (Low trade count = insufficient signals)
- Which stocks have negative Sharpe?
- Is the overall Sharpe significantly lower than the config's V35 Sharpe 2.62?

**Step 3: Run single-stock deep analysis for top performers/losers**

```bash
# Example: Samsung (top)
sts backtest run -s bb_reversion -a stock --symbol 005930

# Example: worst performer
sts backtest run -s bb_reversion -a stock --symbol <worst_code>
```

Review trade-level detail, exit reasons, drawdown.

---

## File Change Summary

| File | Tasks | Changes |
|------|-------|---------|
| `shared/collector/historical/stock.py` | 1,2,3,5 | Hardcap 180d, resume state, ClickHouse loader, status detail |
| `cli/main.py` | 1,2,4,5 | --symbol, --tier, --no-resume, status per-stock table |
| `shared/backtest/engine.py` | — | No changes |

## Execution Order

Tasks 1-5 are code changes (sequential).
Task 6 is a long-running data collection (can run in background).
Task 7 is analysis that requires Task 6 data (but can start with existing 2-month data).
