"""Stock historical backfill CLI commands."""

import click

from cli.commands.backfill import _require_parquet_sink


@click.group("stock-backfill")
def stock_backfill():
    """주식 분봉 데이터 백필 명령

    \b
    Examples:
        sts stock-backfill today          # 오늘 데이터 수집
        sts stock-backfill run --days 7   # 최근 7일 백필
        sts stock-backfill refresh        # DB 종목 기준 재수집
        sts stock-backfill status         # 수집 현황 조회
    """
    pass


@stock_backfill.command("today")
@click.option(
    "--sink",
    type=click.Choice(["parquet"]),
    default="parquet",
    show_default=True,
    help="Storage sink for collected bars",
)
def stock_backfill_today(sink: str):
    """오늘 주식 분봉 데이터 수집 (장 마감 후 실행)

    \b
    Example:
        sts stock-backfill today
    """
    import asyncio

    _require_parquet_sink(sink)
    from shared.collector.historical.parquet_backfill import (
        collect_today_stock_minute_parquet,
    )

    click.echo("Collecting stock minute data to Parquet for today...")
    result = asyncio.run(collect_today_stock_minute_parquet())
    click.echo(
        "Collection complete! "
        f"tasks={result.tasks}, skipped={result.skipped}, "
        f"rows={result.rows}, failed={result.failed}"
    )


@stock_backfill.command("run")
@click.option(
    "--sink",
    type=click.Choice(["parquet"]),
    default="parquet",
    show_default=True,
    help="Storage sink for collected bars",
)
@click.option(
    "--days",
    "-d",
    default=7,
    type=int,
    help="Number of days to backfill (max 180, default: 7)",
)
@click.option(
    "--codes",
    "-c",
    multiple=True,
    help="Specific stock codes to backfill (default: all universe)",
)
@click.option(
    "--no-resume",
    is_flag=True,
    default=False,
    help="Force re-collect all days (ignore saved state)",
)
def stock_backfill_run(sink: str, days: int, codes: tuple, no_resume: bool):
    """주식 분봉 데이터 백필 실행

    \b
    Example:
        sts stock-backfill run --days 7
        sts stock-backfill run --days 30 -c 005930 -c 000660
        sts stock-backfill run --days 180 --no-resume
    """
    import asyncio

    codes_list = list(codes) if codes else None

    _require_parquet_sink(sink)
    from shared.collector.historical.parquet_backfill import (
        backfill_stock_minute_parquet,
    )

    click.echo(f"Starting stock minute Parquet backfill for {days} days...")
    result = asyncio.run(
        backfill_stock_minute_parquet(
            days=days,
            codes=codes_list,
            resume=not no_resume,
        )
    )
    click.echo(
        "Backfill complete! "
        f"tasks={result.tasks}, skipped={result.skipped}, "
        f"rows={result.rows}, failed={result.failed}"
    )


@stock_backfill.command("refresh")
@click.option(
    "--days",
    "-d",
    default=30,
    type=int,
    help="Number of days to backfill (max 30, default: 30)",
)
@click.option(
    "--code-days",
    default=None,
    type=int,
    help="Limit codes to those seen in last N days (default: all codes in DB)",
)
def stock_backfill_refresh(days: int, code_days: int | None):
    """주식 유니버스 기준으로 분봉 재수집

    \b
    Example:
        sts stock-backfill refresh --days 30
        sts stock-backfill refresh --days 7
    """
    import asyncio

    from shared.collector.historical.parquet_backfill import (
        backfill_stock_minute_parquet,
    )
    from shared.collector.historical.stock_universe import STOCK_UNIVERSE

    if code_days:
        click.echo(
            "--code-days is ignored after ClickHouse removal; "
            "refresh uses the configured stock universe."
        )

    click.echo(
        f"Refreshing {len(STOCK_UNIVERSE)} universe codes into Parquet for {days} days..."
    )
    result = asyncio.run(
        backfill_stock_minute_parquet(days=days, codes=None, resume=False)
    )
    click.echo(
        "Backfill complete! "
        f"tasks={result.tasks}, skipped={result.skipped}, "
        f"rows={result.rows}, failed={result.failed}"
    )


@stock_backfill.command("daily")
@click.option(
    "--sink",
    type=click.Choice(["parquet"]),
    default="parquet",
    show_default=True,
    help="Storage sink for collected bars",
)
@click.option(
    "--days",
    "-d",
    default=100,
    type=int,
    help="Number of calendar days to fetch (capped by STOCK_DAILY_MAX_DAYS, default: 100)",
)
@click.option(
    "--codes",
    "-c",
    multiple=True,
    help="Specific stock codes to backfill (default: stock universe)",
)
def stock_backfill_daily(sink: str, days: int, codes: tuple):
    """주식 일봉 데이터 백필 실행.

    \b
    Example:
        sts stock-backfill daily --days 100
        sts stock-backfill daily --days 30 -c 005930 -c 000660
    """
    import asyncio

    codes_list = list(codes) if codes else None

    _require_parquet_sink(sink)
    from shared.collector.historical.parquet_backfill import (
        collect_stock_daily_parquet,
    )

    click.echo(f"Starting stock daily Parquet backfill for {days} days...")
    result = asyncio.run(
        collect_stock_daily_parquet(codes=codes_list, days=days, verbose=True)
    )
    click.echo(
        "Daily backfill complete! "
        f"tasks={result.tasks}, skipped={result.skipped}, "
        f"rows={result.rows}, failed={result.failed}"
    )


@stock_backfill.command("ensure-coverage")
@click.option(
    "--codes",
    "-c",
    multiple=True,
    help="Specific codes to ensure (default: drain the Redis pending queue)",
)
@click.option(
    "--universe",
    is_flag=True,
    default=False,
    help="Seed the coverage queue from system:universe:latest before draining "
    "(off-hours whole-universe top-up; ignored when --codes is given)",
)
def stock_backfill_ensure_coverage(codes: tuple, universe: bool):
    """Deepen daily history (and minute-prewarm) shallow dynamic-universe symbols.

    Drains the on-entry coverage queue (Redis ``stock:coverage:pending``, filled
    by the market-ingest universe-change handler) and paginating-backfills any
    symbol below the configured ``min_daily_bars`` so SMA(200)/pattern_pullback
    becomes available. Also fetches recent 1m bars into parquet so a newly-added
    symbol is minute-warm the same cycle (config ``prewarm_minutes``). Idempotent,
    throttled, and batched (config/env driven).

    ``--universe`` first seeds the queue from ``system:universe:latest`` so an
    off-hours pass tops up the whole current live universe (follow-up (b)).

    \b
    Example:
        sts stock-backfill ensure-coverage
        sts stock-backfill ensure-coverage --universe
        sts stock-backfill ensure-coverage -c 005930 -c 000660
    """
    import asyncio

    from shared.collector.historical.coverage import (
        ensure_daily_coverage,
        seed_universe_queue,
    )

    codes_list = list(codes) if codes else None
    if universe and not codes_list:
        seeded = seed_universe_queue()
        click.echo(f"Seeded {seeded} universe codes into the coverage queue.")
    summary = asyncio.run(ensure_daily_coverage(codes=codes_list))
    click.echo(
        "Coverage ensure complete! "
        f"checked={summary['checked']}, already_deep={summary['already_deep']}, "
        f"deepened={summary['deepened']}, failed={summary['failed']}, "
        f"requeued={summary['requeued']}, "
        f"prewarmed={summary.get('prewarmed', 0)}, rows={summary['rows']}"
    )


@stock_backfill.command("daily-status")
@click.option(
    "--sink",
    type=click.Choice(["parquet"]),
    default="parquet",
    show_default=True,
    help="Storage sink to inspect",
)
@click.option(
    "--days",
    "-d",
    default=100,
    type=int,
    help="Period to check (default: 100 days)",
)
def stock_backfill_daily_status(sink: str, days: int):
    """주식 일봉 데이터 수집 현황 조회."""
    _require_parquet_sink(sink)
    from shared.collector.historical.parquet_backfill import (
        get_parquet_backfill_status,
    )
    from shared.collector.historical.stock_universe import STOCK_UNIVERSE

    status = get_parquet_backfill_status(days=days, asset_class="stock")
    click.echo(f"Stock Parquet Status (last {days} days)")
    click.echo("=" * 50)
    click.echo(f"Universe: {len(STOCK_UNIVERSE)} stocks")
    click.echo(f"Root: {status['root']}")
    click.echo(f"Files: {status['parquet_files']}")
    click.echo(f"Rows: {status['row_count']}")
    if status.get("min_datetime") or status.get("max_datetime"):
        click.echo(
            f"Range: {status.get('min_datetime')} ~ {status.get('max_datetime')}"
        )


@stock_backfill.command("status")
@click.option(
    "--sink",
    type=click.Choice(["parquet"]),
    default="parquet",
    show_default=True,
    help="Storage sink to inspect",
)
@click.option(
    "--days",
    "-d",
    default=30,
    type=int,
    help="Period to check (default: 30 days)",
)
def stock_backfill_status(sink: str, days: int):
    """주식 분봉 데이터 수집 현황 조회

    \b
    Example:
        sts stock-backfill status
        sts stock-backfill status --days 90
    """
    _require_parquet_sink(sink)
    from shared.collector.historical.parquet_backfill import (
        get_parquet_backfill_status,
    )
    from shared.collector.historical.stock_universe import STOCK_UNIVERSE

    status = get_parquet_backfill_status(days=days, asset_class="stock")
    click.echo(f"Stock Parquet Status (last {days} days)")
    click.echo("=" * 50)
    click.echo(f"Universe: {len(STOCK_UNIVERSE)} stocks")
    click.echo(f"Root: {status['root']}")
    click.echo(f"Files: {status['parquet_files']}")
    click.echo(f"Rows: {status['row_count']}")
    if status.get("min_datetime") or status.get("max_datetime"):
        click.echo(
            f"Range: {status.get('min_datetime')} ~ {status.get('max_datetime')}"
        )
    click.echo()
    for row in status.get("tasks", []):
        click.echo(
            f"{row['asset_class']}/{row['timeframe']}/{row['dataset']} "
            f"{row['status']}: tasks={row['tasks']} rows={row['rows'] or 0}"
        )


@stock_backfill.command("universe")
def stock_backfill_universe():
    """주식 유니버스 조회

    \b
    Example:
        sts stock-backfill universe
    """
    from shared.collector.historical.stock_universe import STOCK_UNIVERSE

    click.echo("Stock Universe (30 stocks by market cap tier)")
    click.echo("=" * 50)

    for tier, label in [
        ("top", "📈 Top (대형주)"),
        ("mid", "📊 Mid (중형주)"),
        ("bottom", "📉 Bottom (소형주)"),
    ]:
        stocks = [s for s in STOCK_UNIVERSE if s["tier"] == tier]
        click.echo(f"\n{label}:")
        for s in stocks:
            click.echo(f"  {s['code']} {s['name']}")
