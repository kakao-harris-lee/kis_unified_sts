"""Historical backfill CLI commands."""

import click

# =============================================================================
# Backfill Commands
# =============================================================================


def _require_parquet_sink(sink: str) -> None:
    if sink != "parquet":
        raise click.ClickException(
            "ClickHouse sink has been removed. Collect and inspect Parquet data."
        )


@click.group()
def backfill():
    """과거 데이터 백필 명령

    \b
    Examples:
        sts backfill today          # 오늘 데이터 수집
        sts backfill --days 30      # 최근 30일 백필
        sts backfill status         # 데이터 현황 조회
        sts backfill --all          # 모든 상품 백필
    """
    pass


@backfill.command("today")
@click.option(
    "--sink",
    type=click.Choice(["parquet"]),
    default="parquet",
    show_default=True,
    help="Storage sink for collected bars",
)
@click.option(
    "--all",
    "-a",
    "all_products",
    is_flag=True,
    help="Collect all products (Mini, Index, Futures)",
)
@click.option(
    "--mini/--no-mini",
    default=True,
    help="Collect Mini KOSPI200 futures (default: True)",
)
@click.option(
    "--index/--no-index",
    default=False,
    help="Collect KOSPI200 index (default: False)",
)
@click.option(
    "--futures/--no-futures",
    default=False,
    help="Collect KOSPI200 full-size futures (default: False)",
)
def backfill_today(
    sink: str,
    all_products: bool,
    mini: bool,
    index: bool,
    futures: bool,
):
    """오늘 데이터 수집 (장 마감 후 실행)

    \b
    Example:
        sts backfill today
        sts backfill today --all
        sts backfill today --index --futures
    """
    import asyncio

    _require_parquet_sink(sink)
    from shared.collector.historical.parquet_backfill import (
        collect_today_futures_parquet,
    )

    click.echo("Collecting today's data to Parquet...")
    result = asyncio.run(
        collect_today_futures_parquet(
            all_products=all_products,
            mini=mini,
            index=index,
            futures=futures,
        )
    )
    click.echo(
        "Done! "
        f"tasks={result.tasks}, skipped={result.skipped}, "
        f"rows={result.rows}, failed={result.failed}"
    )


@backfill.command("run")
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
    default=30,
    type=int,
    help="Number of days to backfill (default: 30)",
)
@click.option(
    "--all",
    "-a",
    "all_products",
    is_flag=True,
    help="Backfill all products (Mini, Index, Futures)",
)
@click.option(
    "--mini/--no-mini",
    default=True,
    help="Backfill Mini KOSPI200 futures (default: True)",
)
@click.option(
    "--index/--no-index",
    default=False,
    help="Backfill KOSPI200 index (default: False)",
)
@click.option(
    "--futures/--no-futures",
    default=False,
    help="Backfill KOSPI200 full-size futures (default: False)",
)
@click.option(
    "--no-resume",
    is_flag=True,
    default=False,
    help="Force re-collect all selected products/days (ignore saved state)",
)
def backfill_run(
    sink: str,
    days: int,
    all_products: bool,
    mini: bool,
    index: bool,
    futures: bool,
    no_resume: bool,
):
    """과거 데이터 백필 실행

    \b
    Example:
        sts backfill run --days 30
        sts backfill run --days 180 --all
        sts backfill run --days 90 --index --futures
        sts backfill run --days 30 --futures --no-resume
    """
    import asyncio

    _require_parquet_sink(sink)
    from shared.collector.historical.parquet_backfill import (
        backfill_futures_parquet,
    )

    click.echo(f"Starting Parquet backfill for {days} days...")
    result = asyncio.run(
        backfill_futures_parquet(
            days=days,
            all_products=all_products,
            mini=mini,
            index=index,
            futures=futures,
            resume=not no_resume,
        )
    )
    click.echo(
        "Backfill complete! "
        f"tasks={result.tasks}, skipped={result.skipped}, "
        f"rows={result.rows}, failed={result.failed}"
    )


@backfill.command("status")
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
def backfill_status(sink: str, days: int):
    """데이터 수집 현황 조회

    \b
    Example:
        sts backfill status
        sts backfill status --days 90
    """
    _require_parquet_sink(sink)
    from shared.collector.historical.parquet_backfill import (
        get_parquet_backfill_status,
    )

    status = get_parquet_backfill_status(days=days, asset_class="futures")
    click.echo(f"Parquet Backfill Status (last {days} days)")
    click.echo("=" * 50)
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
            f"{row['status']}: tasks={row['tasks']} rows={row['rows'] or 0} "
            f"range={row['min_date']}~{row['max_date']}"
        )
