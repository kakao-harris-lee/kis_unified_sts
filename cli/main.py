"""CLI 메인 진입점

Usage:
    sts --help
    sts backtest run --strategy bb_reversion --asset stock
    sts optimize --strategy bb_reversion --trials 100
    sts mlflow ui
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import click
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


@click.group()
@click.version_option(version="0.1.0")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging")
def cli(verbose: bool):
    """KIS Unified Trading System CLI

    진입/청산 타이밍 최적화를 위한 통합 트레이딩 플랫폼.

    \b
    Commands:
        backtest    백테스트 실행 및 관리
        optimize    파라미터 최적화
        mlflow      MLflow 관련 명령
        collect     데이터 수집 명령
        trade       트레이딩 제어 명령
        health      시스템 헬스 체크
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


# =============================================================================
# Backtest Commands
# =============================================================================


@cli.group()
def backtest():
    """백테스트 실행 및 관리

    \b
    Examples:
        sts backtest run --strategy bb_reversion --asset stock
        sts backtest best --strategy bb_reversion
        sts backtest list --asset stock
    """
    pass


@backtest.command("run")
@click.option(
    "--strategy",
    "-s",
    required=True,
    help="Strategy name (e.g., bb_reversion, ofi_momentum)",
)
@click.option(
    "--asset",
    "-a",
    required=True,
    type=click.Choice(["stock", "futures"]),
    help="Asset class",
)
@click.option(
    "--start",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Start date (YYYY-MM-DD)",
)
@click.option(
    "--end",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="End date (YYYY-MM-DD)",
)
@click.option(
    "--capital",
    "-c",
    default=10_000_000,
    type=float,
    help="Initial capital (default: 10,000,000)",
)
@click.option(
    "--data",
    "-d",
    type=click.Path(exists=True),
    help="Path to data file (CSV)",
)
@click.option(
    "--track/--no-track",
    default=True,
    help="Track with MLflow (default: True)",
)
@click.option(
    "--experiment",
    "-e",
    default=None,
    help="MLflow experiment name",
)
def backtest_run(
    strategy: str,
    asset: str,
    start,
    end,
    capital: float,
    data: str | None,
    track: bool,
    experiment: str | None,
):
    """백테스트 실행

    \b
    Examples:
        sts backtest run -s bb_reversion -a stock
        sts backtest run -s bb_reversion -a stock --start 2024-01-01 --end 2024-12-31
        sts backtest run -s bb_reversion -a stock -d ./data/005930.csv --track
    """
    from shared.backtest import BacktestConfig, BacktestEngine, MLflowTracker
    from shared.backtest.adapter import BacktestStrategyAdapter
    from shared.config.loader import ConfigLoader
    from shared.strategy.registry import StrategyFactory, register_builtin_components
    from shared.validation.cli_validators import (
        validate_csv_file,
        validate_capital,
        ValidationError,
    )

    click.echo(f"Running backtest: {strategy} ({asset})")

    register_builtin_components()

    # 자본금 검증
    try:
        capital = validate_capital(capital)
    except ValidationError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # 전략 설정 로드
    try:
        strategy_config = ConfigLoader.load_strategy(asset, strategy)
    except FileNotFoundError:
        click.echo(f"Error: Strategy config not found: {asset}/{strategy}", err=True)
        sys.exit(1)

    click.echo(f"Loaded strategy config: {strategy_config['strategy']['name']}")

    # 데이터 로드 및 검증
    if data:
        try:
            df = validate_csv_file(data)
            click.echo(f"Loaded data: {len(df)} rows")
        except ValidationError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    else:
        click.echo("Error: Data file required (use --data option)", err=True)
        click.echo("Hint: Create sample data or download from data source")
        sys.exit(1)

    # 날짜 필터링
    if start:
        df = df[df["datetime"] >= start]
    if end:
        df = df[df["datetime"] <= end]

    click.echo(f"Data range: {df['datetime'].min()} ~ {df['datetime'].max()}")

    # 백테스트 설정
    if asset == "stock":
        config = BacktestConfig.stock(initial_capital=capital)
    else:
        config = BacktestConfig.futures(initial_capital=capital)

    # 전략 생성
    try:
        trading_strategy = StrategyFactory.create(strategy_config)
    except Exception as e:
        click.echo(f"Error creating strategy: {e}", err=True)
        sys.exit(1)

    # 어댑터로 감싸기 (TradingStrategy → StrategyProtocol)
    adapted = BacktestStrategyAdapter(trading_strategy, strategy_config)

    # 백테스트 실행
    engine = BacktestEngine(adapted, config)
    result = engine.run(df)

    # 결과 출력
    result.print_summary()

    # MLflow 추적
    if track:
        exp_name = experiment or f"{asset}_{strategy}"
        click.echo(f"\nTracking with MLflow (experiment: {exp_name})")

        try:
            tracker = MLflowTracker(exp_name)
            with tracker.start_run(run_name=f"{strategy}_run"):
                tracker.log_result(result, strategy_config)
            click.echo("Results logged to MLflow")
        except ImportError:
            click.echo("MLflow not installed, skipping tracking")

    click.echo("\nBacktest complete!")


@backtest.command("best")
@click.option(
    "--strategy",
    "-s",
    required=True,
    help="Strategy name",
)
@click.option(
    "--asset",
    "-a",
    required=True,
    type=click.Choice(["stock", "futures"]),
    help="Asset class",
)
@click.option(
    "--metric",
    "-m",
    default="sharpe_ratio",
    help="Metric to optimize (default: sharpe_ratio)",
)
def backtest_best(strategy: str, asset: str, metric: str):
    """최적 백테스트 결과 조회

    \b
    Example:
        sts backtest best -s bb_reversion -a stock --metric sharpe_ratio
    """
    from shared.backtest import MLflowTracker

    exp_name = f"{asset}_{strategy}"

    try:
        best = MLflowTracker.get_best_run(exp_name, metric=metric)
    except ImportError:
        click.echo("MLflow not installed", err=True)
        sys.exit(1)

    if best is None:
        click.echo(f"No runs found for experiment: {exp_name}")
        return

    click.echo(f"\nBest run for {exp_name} (by {metric}):")
    click.echo("-" * 40)
    for key, value in best.items():
        if value is not None:
            click.echo(f"  {key}: {value}")


@backtest.command("list")
@click.option(
    "--asset",
    "-a",
    type=click.Choice(["stock", "futures"]),
    help="Filter by asset class",
)
def backtest_list(asset: str | None):
    """사용 가능한 전략 목록

    \b
    Example:
        sts backtest list
        sts backtest list -a stock
    """
    from shared.config.loader import ConfigLoader

    click.echo("Available strategies:")
    click.echo("-" * 40)

    try:
        strategies = ConfigLoader.load_all_strategies(asset)
        for config in strategies:
            name = config["strategy"]["name"]
            asset_class = config["strategy"].get("asset_class", "unknown")
            enabled = "✓" if config["strategy"].get("enabled", True) else "✗"
            click.echo(f"  [{enabled}] {name} ({asset_class})")
    except Exception as e:
        click.echo(f"Error loading strategies: {e}", err=True)


# =============================================================================
# Optimize Commands
# =============================================================================


@cli.command("optimize")
@click.option(
    "--strategy",
    "-s",
    required=True,
    help="Strategy name",
)
@click.option(
    "--asset",
    "-a",
    required=True,
    type=click.Choice(["stock", "futures"]),
    help="Asset class",
)
@click.option(
    "--data",
    "-d",
    required=True,
    type=click.Path(exists=True),
    help="Path to data file (CSV)",
)
@click.option(
    "--trials",
    "-n",
    default=100,
    type=int,
    help="Number of trials (default: 100)",
)
@click.option(
    "--metric",
    "-m",
    default="sharpe_ratio",
    help="Metric to optimize (default: sharpe_ratio)",
)
@click.option(
    "--timeout",
    "-t",
    default=None,
    type=int,
    help="Timeout in seconds",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file for best parameters (YAML)",
)
def optimize(
    strategy: str,
    asset: str,
    data: str,
    trials: int,
    metric: str,
    _timeout: int | None,
    _output: str | None,
):
    """파라미터 최적화 실행

    \b
    Example:
        sts optimize -s bb_reversion -a stock -d ./data/005930.csv -n 100
        sts optimize -s bb_reversion -a stock -d data.csv --metric profit_factor
    """
    from shared.validation.cli_validators import validate_csv_file, ValidationError

    click.echo(f"Optimizing: {strategy} ({asset})")
    click.echo(f"Trials: {trials}, Metric: {metric}")

    # 데이터 로드 및 검증
    try:
        df = validate_csv_file(data)
        click.echo(f"Loaded data: {len(df)} rows")
    except ValidationError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    click.echo("\nNote: Strategy-specific optimization coming soon.")
    click.echo("For now, use the Python API directly:")
    click.echo("""
    from shared.backtest import StrategyOptimizer, ParamSpec

    optimizer = StrategyOptimizer(strategy_factory, data)
    optimizer.add_param(ParamSpec.int("period", 10, 30))
    best = optimizer.optimize(n_trials=100)
    """)


# =============================================================================
# MLflow Commands
# =============================================================================


@cli.group()
def mlflow():
    """MLflow 관련 명령

    \b
    Examples:
        sts mlflow ui
        sts mlflow list
    """
    pass


@mlflow.command("ui")
@click.option(
    "--port",
    "-p",
    default=5000,
    type=int,
    help="Port number (default: 5000)",
)
@click.option(
    "--host",
    "-h",
    default="127.0.0.1",
    help="Host (default: 127.0.0.1)",
)
def mlflow_ui(port: int, host: str):
    """MLflow UI 실행

    \b
    Example:
        sts mlflow ui
        sts mlflow ui --port 5001
    """
    import subprocess

    click.echo(f"Starting MLflow UI at http://{host}:{port}")
    click.echo("Press Ctrl+C to stop")

    try:
        subprocess.run(
            [
                "mlflow",
                "ui",
                "--backend-store-uri",
                "sqlite:///mlflow.db",
                "--host",
                host,
                "--port",
                str(port),
            ],
            check=True,
        )
    except FileNotFoundError:
        click.echo("Error: mlflow not found. Install with: pip install mlflow", err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\nMLflow UI stopped")


@mlflow.command("list")
def mlflow_list():
    """MLflow 실험 목록

    \b
    Example:
        sts mlflow list
    """
    try:
        import mlflow as mlf

        mlf.set_tracking_uri("sqlite:///mlflow.db")
        experiments = mlf.search_experiments()

        click.echo("MLflow Experiments:")
        click.echo("-" * 40)
        for exp in experiments:
            click.echo(f"  [{exp.experiment_id}] {exp.name}")
    except ImportError:
        click.echo("MLflow not installed", err=True)
        sys.exit(1)


# =============================================================================
# Data Collection Commands
# =============================================================================


@cli.group()
def collect():
    """데이터 수집 명령

    \b
    Examples:
        sts collect start --symbol 005930
        sts collect stop
        sts collect status
    """
    pass


# =============================================================================
# Backfill Commands
# =============================================================================


@cli.group()
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
def backfill_today(all_products: bool, mini: bool, index: bool, futures: bool):
    """오늘 데이터 수집 (장 마감 후 실행)

    \b
    Example:
        sts backfill today
        sts backfill today --all
        sts backfill today --index --futures
    """
    import asyncio

    from shared.collector.historical import (
        collect_today,
        collect_today_kospi200_index,
        collect_today_kospi200f,
        collect_today_all,
    )

    if all_products:
        click.echo("Collecting today's data for all products...")
        asyncio.run(collect_today_all())
    else:
        if mini:
            click.echo("Collecting Mini KOSPI200 futures...")
            asyncio.run(collect_today())
        if index:
            click.echo("Collecting KOSPI200 index...")
            asyncio.run(collect_today_kospi200_index())
        if futures:
            click.echo("Collecting KOSPI200 futures...")
            asyncio.run(collect_today_kospi200f())

    click.echo("Done!")


@backfill.command("run")
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
def backfill_run(days: int, all_products: bool, mini: bool, index: bool, futures: bool):
    """과거 데이터 백필 실행

    \b
    Example:
        sts backfill run --days 30
        sts backfill run --days 180 --all
        sts backfill run --days 90 --index --futures
    """
    import asyncio

    from shared.collector.historical import (
        backfill as do_backfill,
        backfill_kospi200_index,
        backfill_kospi200f,
        backfill_all,
    )

    click.echo(f"Starting backfill for {days} days...")

    if all_products:
        asyncio.run(backfill_all(days=days))
    else:
        if mini:
            click.echo("Backfilling Mini KOSPI200 futures...")
            asyncio.run(do_backfill(days=days))
        if index:
            click.echo("Backfilling KOSPI200 index...")
            asyncio.run(backfill_kospi200_index(days=days))
        if futures:
            click.echo("Backfilling KOSPI200 futures...")
            asyncio.run(backfill_kospi200f(days=days))

    click.echo("Backfill complete!")


@backfill.command("status")
@click.option(
    "--days",
    "-d",
    default=30,
    type=int,
    help="Period to check (default: 30 days)",
)
def backfill_status(days: int):
    """데이터 수집 현황 조회

    \b
    Example:
        sts backfill status
        sts backfill status --days 90
    """
    from shared.collector.historical.backfill import get_data_status

    click.echo(f"Data Collection Status (last {days} days)")
    click.echo("=" * 50)

    status = get_data_status(days=days)

    if "error" in status:
        click.echo(f"Error: {status['error']}", err=True)
        return

    click.echo(f"Period: {status['period']}")
    click.echo(f"Trading Days: {status['trading_days']}")
    click.echo()

    for table_name, info in status.get("tables", {}).items():
        click.echo(f"📊 {table_name}:")
        if "error" in info:
            click.echo(f"   Error: {info['error']}")
        else:
            click.echo(f"   Rows: {info['rows']:,}")
            click.echo(f"   Days Collected: {info['days_collected']}")
            if info.get("min_datetime"):
                click.echo(f"   Range: {info['min_datetime']} ~ {info['max_datetime']}")
        click.echo()


# =============================================================================
# Stock Backfill Commands
# =============================================================================


@cli.group("stock-backfill")
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
def stock_backfill_today():
    """오늘 주식 분봉 데이터 수집 (장 마감 후 실행)

    \b
    Example:
        sts stock-backfill today
    """
    import asyncio

    from shared.collector.historical.stock import collect_stock_minute_today

    click.echo("Collecting stock minute data for today...")
    asyncio.run(collect_stock_minute_today())
    click.echo("Collection complete!")


@stock_backfill.command("run")
@click.option(
    "--days",
    "-d",
    default=7,
    type=int,
    help="Number of days to backfill (max 30, default: 7)",
)
@click.option(
    "--codes",
    "-c",
    multiple=True,
    help="Specific stock codes to backfill (default: all universe)",
)
def stock_backfill_run(days: int, codes: tuple):
    """주식 분봉 데이터 백필 실행

    \b
    Example:
        sts stock-backfill run --days 7
        sts stock-backfill run --days 30 -c 005930 -c 000660
    """
    import asyncio

    from shared.collector.historical.stock import backfill_stock_minute

    click.echo(f"Starting stock minute backfill for {days} days...")

    codes_list = list(codes) if codes else None
    asyncio.run(backfill_stock_minute(days=days, codes=codes_list))

    click.echo("Backfill complete!")


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
    """DB에 이미 존재하는 종목 기준으로 분봉 재수집

    \b
    Example:
        sts stock-backfill refresh --days 30
        sts stock-backfill refresh --days 7 --code-days 90
    """
    import asyncio

    from shared.collector.historical.stock import (
        backfill_stock_minute,
        get_stock_codes_from_db,
    )

    if code_days:
        click.echo(f"Loading codes from last {code_days} days in DB...")
        codes = get_stock_codes_from_db(days=code_days)
    else:
        click.echo("Loading codes from DB...")
        codes = get_stock_codes_from_db()

    if not codes:
        click.echo("No codes found in DB.")
        return

    click.echo(f"Found {len(codes)} codes. Starting backfill for {days} days...")
    asyncio.run(backfill_stock_minute(days=days, codes=codes))
    click.echo("Backfill complete!")


@stock_backfill.command("status")
@click.option(
    "--days",
    "-d",
    default=30,
    type=int,
    help="Period to check (default: 30 days)",
)
def stock_backfill_status(days: int):
    """주식 분봉 데이터 수집 현황 조회

    \b
    Example:
        sts stock-backfill status
        sts stock-backfill status --days 90
    """
    from shared.collector.historical.stock import (
        get_stock_collection_status,
        STOCK_UNIVERSE,
    )

    click.echo(f"Stock Minute Data Collection Status (last {days} days)")
    click.echo("=" * 50)
    click.echo(f"Universe: {len(STOCK_UNIVERSE)} stocks")
    click.echo()

    status = get_stock_collection_status(days=days)

    if "error" in status:
        click.echo(f"Error: {status['error']}", err=True)
        return

    click.echo(f"📊 {status['table']}:")
    click.echo(f"   Rows: {status.get('rows', 0):,}")
    click.echo(f"   Days Collected: {status.get('days_collected', 0)}")
    click.echo(f"   Unique Codes: {status.get('unique_codes', 0)}")
    if status.get("min_datetime"):
        click.echo(f"   Range: {status['min_datetime']} ~ {status['max_datetime']}")


@stock_backfill.command("universe")
def stock_backfill_universe():
    """주식 유니버스 조회

    \b
    Example:
        sts stock-backfill universe
    """
    from shared.collector.historical.stock import STOCK_UNIVERSE

    click.echo("Stock Universe (30 stocks by market cap tier)")
    click.echo("=" * 50)

    for tier, label in [("top", "📈 Top (대형주)"), ("mid", "📊 Mid (중형주)"), ("bottom", "📉 Bottom (소형주)")]:
        stocks = [s for s in STOCK_UNIVERSE if s["tier"] == tier]
        click.echo(f"\n{label}:")
        for s in stocks:
            click.echo(f"  {s['code']} {s['name']}")


@collect.command("start")
@click.option(
    "--symbol",
    "-s",
    required=True,
    multiple=True,
    help="Symbol to collect (can specify multiple)",
)
@click.option(
    "--interval",
    "-i",
    default=1.0,
    type=float,
    help="Collection interval in seconds (default: 1.0)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output directory for collected data",
)
def collect_start(symbol: tuple, interval: float, _output: str | None):
    """데이터 수집 시작

    \b
    Example:
        sts collect start -s 005930 -s 000660
        sts collect start -s 101S06 --interval 0.5
    """
    import asyncio

    click.echo(f"Starting data collection for: {list(symbol)}")
    click.echo(f"Interval: {interval}s")

    try:
        from shared.collector import DataCollector, CollectorConfig

        config = CollectorConfig(
            symbols=list(symbol),
            tick_interval=interval,
        )
        collector = DataCollector(config)

        click.echo("Press Ctrl+C to stop collection")

        async def run():
            await collector.start()
            try:
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                pass
            finally:
                await collector.stop()

        asyncio.run(run())

    except ImportError as e:
        click.echo(f"Error: Required module not installed: {e}", err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\nData collection stopped")


# =============================================================================
# WebSocket Realtime Collection Commands
# =============================================================================


@cli.group("websocket")
def websocket():
    """WebSocket 실시간 데이터 수집

    \b
    Examples:
        sts websocket start             # 기본 선물 코드로 수집 시작
        sts websocket start -c 101V01   # 특정 코드 지정
        sts websocket status            # 수집 상태 확인
    """
    pass


@websocket.command("start")
@click.option(
    "--code",
    "-c",
    multiple=True,
    help="Futures code to subscribe (can specify multiple, default: front month mini)",
)
@click.option(
    "--real/--mock",
    default=True,
    help="Real or mock trading environment (default: real)",
)
@click.option(
    "--stream",
    "-s",
    default="raw_data",
    help="Redis stream name for output (default: raw_data)",
)
@click.option(
    "--daemon/--foreground",
    default=False,
    help="Run as daemon (default: foreground)",
)
def websocket_start(code: tuple, real: bool, stream: str, daemon: bool):
    """WebSocket 실시간 데이터 수집 시작

    선물 호가/체결 데이터를 WebSocket으로 수신하여 Redis Stream에 발행합니다.

    \b
    Example:
        sts websocket start
        sts websocket start -c 101V01 -c 101W01
        sts websocket start --mock
    """
    from shared.kis.websocket import create_websocket_adapter
    from shared.collector import DataCollector

    # Determine symbols
    if code:
        symbols = list(code)
    else:
        # Default: front month mini futures
        from shared.collector.historical.futures import get_front_month_code
        symbols = [get_front_month_code()]
        click.echo(f"Using default symbol: {symbols[0]} (front month mini)")

    mode_str = "Real" if real else "Mock"
    click.echo(f"Starting WebSocket Collector ({mode_str})")
    click.echo(f"  Symbols: {symbols}")
    click.echo(f"  Stream: {stream}")
    click.echo("-" * 40)

    try:
        # Create WebSocket adapter
        adapter = create_websocket_adapter(is_real=real)

        # Create collector
        collector = DataCollector(
            api_adapter=adapter,
            stream_name=stream,
        )

        click.echo("Connecting to KIS WebSocket...")

        if daemon:
            # Daemon mode: write PID file and detach
            import os

            pid_dir = Path("/home/deploy/project/kis_unified_sts/pids")
            pid_dir.mkdir(exist_ok=True)
            pid_file = pid_dir / "websocket.pid"

            with open(pid_file, "w") as f:
                f.write(str(os.getpid()))

            click.echo(f"PID file: {pid_file}")

        click.echo("Press Ctrl+C to stop")

        # Start collection (blocking)
        collector.start(symbols)

    except KeyboardInterrupt:
        click.echo("\nWebSocket collection stopped")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@websocket.command("stop")
def websocket_stop():
    """WebSocket 실시간 데이터 수집 중지

    \b
    Example:
        sts websocket stop
    """
    import os
    import signal

    pid_file = Path("/home/deploy/project/kis_unified_sts/pids/websocket.pid")

    if not pid_file.exists():
        click.echo("WebSocket collector not running (no PID file found)")
        return

    try:
        with open(pid_file, "r") as f:
            pid = int(f.read().strip())

        os.kill(pid, signal.SIGTERM)
        click.echo(f"Sent SIGTERM to PID {pid}")

        # Remove PID file
        pid_file.unlink()
        click.echo("WebSocket collector stopped")

    except ProcessLookupError:
        click.echo(f"Process {pid} not found (already stopped?)")
        pid_file.unlink()
    except Exception as e:
        click.echo(f"Error stopping collector: {e}", err=True)


@websocket.command("status")
def websocket_status():
    """WebSocket 실시간 데이터 수집 상태 확인

    \b
    Example:
        sts websocket status
    """
    import os

    pid_file = Path("/home/deploy/project/kis_unified_sts/pids/websocket.pid")

    click.echo("WebSocket Collector Status")
    click.echo("-" * 40)

    if not pid_file.exists():
        click.echo("  Status: Not running")
        click.echo("  Note: Use 'sts websocket start' to begin")
        return

    try:
        with open(pid_file, "r") as f:
            pid = int(f.read().strip())

        # Check if process is running
        os.kill(pid, 0)  # Signal 0 just checks existence
        click.echo(f"  Status: Running (PID {pid})")

        # Try to get Redis stream info
        try:
            from shared.streaming.client import RedisClient
            client = RedisClient.get_client()
            info = client.xinfo_stream("raw_data")
            click.echo(f"  Stream Length: {info.get('length', 'N/A')}")
            click.echo(f"  Last Entry: {info.get('last-entry', 'N/A')}")
        except Exception:
            click.echo("  Stream: Unable to query")

    except ProcessLookupError:
        click.echo("  Status: Stale (process not found)")
        click.echo("  Note: PID file exists but process is not running")
        pid_file.unlink()
    except Exception as e:
        click.echo(f"  Error: {e}")


@collect.command("status")
def collect_status():
    """데이터 수집 상태 조회

    \b
    Example:
        sts collect status
    """
    click.echo("Collector Status:")
    click.echo("-" * 40)
    click.echo("  Status: Not running (use 'sts collect start' to begin)")
    click.echo("  Note: For persistent collection, use the API or daemon mode")


# =============================================================================
# Trading Commands
# =============================================================================


@cli.group()
def trade():
    """트레이딩 제어 명령

    \b
    Examples:
        sts trade start --strategy bb_reversion --asset stock
        sts trade stop
        sts trade status
    """
    pass


@trade.command("start")
@click.option(
    "--strategy",
    "-s",
    default=None,
    help="Strategy name (omit to load all enabled strategies)",
)
@click.option(
    "--asset",
    "-a",
    required=True,
    type=click.Choice(["stock", "futures"]),
    help="Asset class",
)
@click.option(
    "--capital",
    "-c",
    default=10_000_000,
    type=float,
    help="Initial capital (default: 10,000,000)",
)
@click.option(
    "--paper/--live",
    default=True,
    help="Paper trading mode (default: paper)",
)
@click.option(
    "--daemon/--single",
    default=False,
    help="Daemon mode (run daily) or single session",
)
def trade_start(
    strategy: str,
    asset: str,
    capital: float,
    paper: bool,
    daemon: bool,
):
    """트레이딩 시작

    \b
    Example:
        sts trade start -s bb_reversion -a stock
        sts trade start -s pure_micro -a futures --capital 5000000
        sts trade start -s bb_reversion -a stock --daemon
    """
    import asyncio

    mode_str = "Paper" if paper else "LIVE"
    click.echo(f"Starting {mode_str} Trading")
    click.echo(f"  Strategy: {strategy or 'all enabled'}")
    click.echo(f"  Asset: {asset}")
    click.echo(f"  Capital: {capital:,.0f}")
    click.echo(f"  Mode: {'Daemon' if daemon else 'Single Session'}")

    if not paper:
        if not click.confirm("⚠️  LIVE TRADING - Are you sure?"):
            click.echo("Aborted.")
            return

    try:
        from services.trading.orchestrator import (
            TradingOrchestrator,
            TradingConfig,
        )

        if asset == "stock":
            config = TradingConfig.stock(
                strategy_name=strategy,
                initial_capital=capital,
            )
        else:
            config = TradingConfig.futures(
                strategy_name=strategy,
                initial_capital=capital,
            )

        config.paper_trading = paper

        orchestrator = TradingOrchestrator(config)

        click.echo("\nPress Ctrl+C to stop trading")

        async def run():
            if daemon:
                await orchestrator.run()
            else:
                await orchestrator.run_session()

        asyncio.run(run())

    except ImportError as e:
        click.echo(f"Error: Required module not installed: {e}", err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\nTrading stopped")


@trade.command("status")
@click.option(
    "--url",
    "-u",
    default="http://localhost:8000",
    help="API server URL",
)
def trade_status(url: str):
    """트레이딩 상태 조회

    \b
    Example:
        sts trade status
        sts trade status --url http://localhost:8000
    """
    try:
        import httpx

        response = httpx.get(f"{url}/api/v1/trading/status", timeout=5.0)
        if response.status_code == 200:
            data = response.json()
            click.echo("Trading Status:")
            click.echo("-" * 40)
            for key, value in data.items():
                click.echo(f"  {key}: {value}")
        else:
            click.echo(f"Error: {response.status_code}")
    except Exception:
        click.echo("Trading Status:")
        click.echo("-" * 40)
        click.echo("  Status: Not running")
        click.echo("  Note: Start API server with 'uvicorn services.api.app:app'")


@trade.command("stop")
@click.option(
    "--url",
    "-u",
    default="http://localhost:8000",
    help="API server URL",
)
def trade_stop(url: str):
    """트레이딩 종료

    \b
    Example:
        sts trade stop
        sts trade stop --url http://localhost:8000
    """
    try:
        import httpx

        response = httpx.post(
            f"{url}/api/v1/trading/stop",
            timeout=10.0,
        )
        if response.status_code == 200:
            click.echo("Trading stopped successfully")
        else:
            click.echo(f"Error: {response.status_code} - {response.text}")
    except Exception as e:
        click.echo(f"Error stopping trading: {e}", err=True)
        click.echo("Note: Ensure API server is running")


# =============================================================================
# Paper Trading Commands
# =============================================================================


@cli.group()
def paper():
    """모의 거래 명령

    \b
    Examples:
        sts paper start -s bb_reversion -a stock
        sts paper status
        sts paper stop
    """
    pass


@paper.command("start")
@click.option("--strategy", "-s", required=True, help="Strategy name")
@click.option("--asset", "-a", required=True, type=click.Choice(["stock", "futures"]))
@click.option("--capital", "-c", default=10_000_000, type=float, help="Initial capital (KRW)")
@click.option("--max-positions", "-m", default=5, type=int, help="Maximum concurrent positions")
def paper_start(strategy: str, asset: str, capital: float, max_positions: int):
    """모의 거래 시작

    \b
    Example:
        sts paper start -s bb_reversion -a stock
        sts paper start -s ofi_momentum -a futures --capital 50000000
    """
    import asyncio

    click.echo(f"Starting Paper Trading")
    click.echo(f"  Strategy: {strategy}")
    click.echo(f"  Asset: {asset}")
    click.echo(f"  Capital: {capital:,.0f} KRW")
    click.echo(f"  Max Positions: {max_positions}")
    click.echo("-" * 40)

    try:
        from shared.paper.engine import PaperTradingEngine
        from shared.paper.config import PaperTradingConfig
        from shared.config.loader import ConfigLoader

        # Load strategy config
        try:
            strategy_config = ConfigLoader.load_strategy(asset, strategy)
            click.echo(f"Loaded strategy: {strategy_config['strategy']['name']}")
        except FileNotFoundError:
            click.echo(f"Error: Strategy not found: {asset}/{strategy}", err=True)
            sys.exit(1)

        # Create paper trading config
        config = PaperTradingConfig(
            initial_balance=capital,
            max_positions=max_positions,
            commission_rate=0.00015,  # 0.015%
        )

        # Create and start engine
        engine = PaperTradingEngine(config)

        click.echo("\nPaper trading started. Press Ctrl+C to stop.")
        click.echo("Waiting for market signals...\n")

        async def run():
            await engine.start()
            try:
                # Keep running until interrupted
                while engine.is_running:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                pass
            finally:
                await engine.stop()
                # Print summary
                perf = engine.get_performance()
                click.echo("\n" + "=" * 40)
                click.echo("Paper Trading Summary")
                click.echo("=" * 40)
                click.echo(f"  Total Trades: {perf.get('total_trades', 0)}")
                click.echo(f"  Winning Trades: {perf.get('winning_trades', 0)}")
                click.echo(f"  Win Rate: {perf.get('win_rate', 0) * 100:.1f}%")
                click.echo(f"  Total P&L: {perf.get('total_pnl', 0):,.0f} KRW")
                click.echo(f"  Final Equity: {perf.get('equity', capital):,.0f} KRW")

        asyncio.run(run())

    except ImportError as e:
        click.echo(f"Error: Required module not installed: {e}", err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\nPaper trading stopped")


@paper.command("status")
@click.option("--url", "-u", default="http://localhost:8001", help="Dashboard API URL")
def paper_status(url: str):
    """모의 거래 상태 조회

    \b
    Example:
        sts paper status
    """
    try:
        import httpx

        response = httpx.get(f"{url}/api/trading/status", timeout=5.0)
        if response.status_code == 200:
            data = response.json()
            click.echo("Paper Trading Status:")
            click.echo("-" * 40)
            click.echo(f"  Running: {data.get('is_running', False)}")
            click.echo(f"  Positions: {data.get('total_positions', 0)}")
            click.echo(f"  Total P&L: {data.get('total_pnl', 0):,.0f} KRW")
        else:
            click.echo("Paper Trading Status:")
            click.echo("-" * 40)
            click.echo("  Status: Not running")
    except Exception:
        click.echo("Paper Trading Status:")
        click.echo("-" * 40)
        click.echo("  Status: Not running")
        click.echo("  Note: Use 'sts paper start' to begin")


@paper.command("stop")
@click.option("--url", "-u", default="http://localhost:8001", help="Dashboard API URL")
def paper_stop(url: str):
    """모의 거래 종료

    \b
    Example:
        sts paper stop
    """
    try:
        import httpx

        response = httpx.post(f"{url}/api/trading/stop", timeout=5.0)
        if response.status_code == 200:
            click.echo("Paper trading stopped successfully")
        else:
            click.echo(f"Error: {response.status_code}")
    except Exception:
        click.echo("Paper trading stopped (local mode)")


@paper.command("history")
@click.option("--limit", "-n", default=10, type=int, help="Number of trades to show")
@click.option("--format", "fmt", default="table", type=click.Choice(["table", "json"]))
def paper_history(_limit: int, _fmt: str):
    """모의 거래 히스토리 조회

    \b
    Example:
        sts paper history
        sts paper history -n 20 --format json
    """
    click.echo("Trade History:")
    click.echo("-" * 60)
    click.echo("  No trades recorded in current session.")
    click.echo("  Note: Start paper trading with 'sts paper start' first")


# =============================================================================
# Health Commands
# =============================================================================


@cli.command("health")
@click.option(
    "--url",
    "-u",
    default="http://localhost:8000",
    help="API server URL",
)
def health(url: str):
    """시스템 헬스 체크

    \b
    Example:
        sts health
        sts health --url http://localhost:8000
    """
    try:
        import httpx

        click.echo(f"Checking health: {url}")

        # Basic health
        response = httpx.get(f"{url}/health", timeout=5.0)
        if response.status_code == 200:
            data = response.json()
            click.echo("Health Check: ✓")
            click.echo(f"  Status: {data.get('status', 'unknown')}")
            click.echo(f"  Version: {data.get('version', 'unknown')}")
        else:
            click.echo(f"Health Check: ✗ ({response.status_code})")

        # Readiness (optional - not all servers have this endpoint)
        try:
            response = httpx.get(f"{url}/health/ready", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                click.echo("Readiness: ✓")
                components = data.get("components", {})
                for name, status in components.items():
                    icon = "✓" if status else "✗"
                    click.echo(f"  {name}: {icon}")
            elif response.status_code == 404:
                click.echo("Readiness: N/A (endpoint not available)")
            else:
                click.echo(f"Readiness: ✗ ({response.status_code})")
        except httpx.HTTPError:
            click.echo("Readiness: N/A")

    except httpx.ConnectError:
        click.echo("Health Check: ✗ (Connection refused)")
        click.echo("Note: Start API server with 'uvicorn services.api.app:app'")
    except ImportError:
        click.echo("Error: httpx not installed (pip install httpx)", err=True)
        sys.exit(1)




# =============================================================================
# RL (Reinforcement Learning) Commands
# =============================================================================


@cli.group()
def rl():
    """강화학습 모델 관련 명령

    \b
    Examples:
        sts rl train --algo mppo
        sts rl train --algo all
        sts rl evaluate --model mppo_best
        sts rl slippage --model mppo_best
        sts rl tensorboard
    """
    pass


@rl.command("train")
@click.option("--algo", "-a", default="mppo", type=click.Choice(["mppo", "sac", "dqn", "a2c", "ppo", "dt", "all"]), help="Algorithm to train (default: mppo)")
@click.option("--config", "-c", default=None, help="Config file path (auto-detected for dt)")
def rl_train(algo: str, config: str | None):
    """RL 모델 학습

    \b
    Example:
        sts rl train --algo mppo
        sts rl train --algo dt
        sts rl train --algo all
    """
    # DT일 때 자동으로 rl_dt.yaml 선택
    if config is None:
        config = "ml/rl_dt.yaml" if algo == "dt" else "ml/rl_mppo.yaml"

    click.echo("Starting RL Training")
    click.echo(f"  Algorithm: {algo}")
    click.echo(f"  Config: {config}")
    click.echo("-" * 40)

    try:
        from scripts.training.train_rl import (
            load_data_from_clickhouse,
            precompute_tft_aux,
        )
        from shared.ml.rl.trainer import RLTrainer

        train_days, train_prices, test_days, test_prices = load_data_from_clickhouse(config)

        # TFT 보조 피처 사전 계산 (tft_aux.enabled=true인 경우)
        train_aux, test_aux = precompute_tft_aux(config)

        trainer = RLTrainer(config_path=config)

        if algo == "all":
            models = trainer.train_all(
                train_days=train_days,
                train_prices=train_prices,
                eval_days=test_days,
                eval_prices=test_prices,
            )
            click.echo(f"Trained {len(models)} models: {list(models.keys())}")
        else:
            trainer.train(
                algo=algo,
                train_days=train_days,
                train_prices=train_prices,
                eval_days=test_days,
                eval_prices=test_prices,
                train_aux=train_aux,
                eval_aux=test_aux,
            )
            click.echo(f"Training complete: {algo}")

    except ImportError as e:
        click.echo(f"Error: Required package not installed: {e}", err=True)
        click.echo("Install with: pip install -e .[ml]", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@rl.command("evaluate")
@click.option("--model", "-m", default="mppo_best", help="Model name to evaluate")
@click.option("--config", "-c", default=None, help="Config file path (auto-detected for dt)")
def rl_evaluate(model: str, config: str | None):
    """RL 모델 평가 (표1 재현)

    \b
    Example:
        sts rl evaluate --model mppo_best
        sts rl evaluate --model dt_final
    """
    from pathlib import Path

    model_dir = Path(f"models/futures/rl/{model}")
    is_dt = (model_dir / "model.pt").exists()

    is_sac = "sac" in model.lower()
    if config is None:
        if is_dt:
            config = "ml/rl_dt.yaml"
        elif is_sac:
            config = "ml/rl_sac.yaml"
        else:
            config = "ml/rl_mppo.yaml"

    algo_label = "DT" if is_dt else ("SAC" if is_sac else "MPPO")
    click.echo(f"Evaluating RL Model: {model} ({algo_label})")

    try:
        from scripts.training.train_rl import (
            load_data_from_clickhouse,
            precompute_tft_aux,
        )
        from shared.ml.rl.evaluator import RLEvaluator

        _, _, test_days, test_prices = load_data_from_clickhouse(config)

        # TFT 보조 피처 (tft_aux.enabled=true인 경우)
        _, test_aux = precompute_tft_aux(config)

        if is_dt:
            from shared.config.loader import ConfigLoader
            from shared.ml.rl.decision_transformer.model import DTAgent

            loaded_model = DTAgent.load(model_dir)
            evaluator = RLEvaluator(config_path=config)
            dt_cfg = ConfigLoader.load(config)
            target_return = float(dt_cfg.get("paper", {}).get("target_return", 5_000_000))
            results = evaluator.evaluate_model(
                loaded_model, test_days, test_prices, is_dt=True,
                target_return=target_return,
            )
        else:
            is_sac = "sac" in model.lower()
            if is_sac:
                from stable_baselines3 import SAC

                model_path = f"models/futures/rl/{model}/best_model.zip"
                if not Path(model_path).exists():
                    # sac_final.zip 등 직접 파일인 경우
                    model_path = f"models/futures/rl/{model}.zip"
                loaded_model = SAC.load(model_path)
                evaluator = RLEvaluator(config_path=config)
                results = evaluator.evaluate_model(
                    loaded_model, test_days, test_prices, continuous=True,
                )
            else:
                from sb3_contrib import MaskablePPO

                model_path = f"models/futures/rl/{model}/best_model.zip"
                if not Path(model_path).exists():
                    model_path = f"models/futures/rl/{model}.zip"
                loaded_model = MaskablePPO.load(model_path)
                evaluator = RLEvaluator(config_path=config)
                results = evaluator.evaluate_model(
                    loaded_model, test_days, test_prices,
                    test_aux=test_aux,
                )

        click.echo("\nEvaluation Results:")
        click.echo("-" * 40)
        for k, v in results.items():
            if k != "daily_returns":
                click.echo(f"  {k}: {v}")

    except FileNotFoundError:
        click.echo(f"Error: Model not found at models/futures/rl/{model}/", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@rl.command("slippage")
@click.option("--model", "-m", default="mppo_best", help="Model name")
@click.option("--retrain", is_flag=True, help="Retrain with each slippage (Table 3)")
@click.option("--config", "-c", default="ml/rl_mppo.yaml", help="Config file path")
def rl_slippage(model: str, retrain: bool, config: str):
    """슬리피지 분석 (표2/표3)

    \b
    Example:
        sts rl slippage --model mppo_best
        sts rl slippage --model mppo_best --retrain
    """
    table = "Table 3 (retrain)" if retrain else "Table 2 (test-only)"
    click.echo(f"Slippage Analysis: {table}")

    try:
        from scripts.training.train_rl import load_data_from_clickhouse
        from shared.ml.rl.evaluator import RLEvaluator
        from shared.ml.rl.trainer import RLTrainer
        from sb3_contrib import MaskablePPO

        train_days, train_prices, test_days, test_prices = load_data_from_clickhouse(config)

        model_path = f"models/futures/rl/{model}/best_model.zip"
        loaded_model = MaskablePPO.load(model_path)

        evaluator = RLEvaluator(config_path=config)
        trainer = RLTrainer(config_path=config) if retrain else None

        df = evaluator.slippage_analysis(
            loaded_model,
            test_days,
            test_prices,
            retrain=retrain,
            trainer=trainer,
            train_days=train_days if retrain else None,
            train_prices=train_prices if retrain else None,
        )

        click.echo(f"\n{df.to_string(index=False)}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@rl.command("paper")
@click.option("--model", "-m", default="mppo_best", help="Model name (default: mppo_best)")
@click.option("--config", "-c", default="ml/rl_mppo.yaml", help="Config file path")
@click.option("--symbol", "-s", default=None, help="Futures symbol (default: from config)")
@click.option(
    "--engine",
    type=click.Choice(["orchestrator", "legacy"], case_sensitive=False),
    default="orchestrator",
    show_default=True,
    help="Execution engine path",
)
@click.option("--no-daemon", is_flag=True, help="Run single session (foreground, no loop)")
def rl_paper(model: str, config: str, symbol: str, engine: str, no_daemon: bool):
    """RL Paper Trading 실행

    \b
    학습된 MaskablePPO 모델로 실시간 paper trading.
    기본 엔진은 orchestrator 경로(전략/리스크/주문 공통 경로).
    legacy는 기존 paper_trader 단독 엔진.

    \b
    Example:
        sts rl paper                          # 기본 (mppo_final)
        sts rl paper --model mppo_best        # 특정 모델
        sts rl paper --no-daemon              # 단일 세션
        sts rl paper --symbol 101S6000        # 종목 지정
    """
    import asyncio

    click.echo("RL Paper Trading")
    click.echo(f"  Model: {model}")
    click.echo(f"  Config: {config}")
    if symbol:
        click.echo(f"  Symbol: {symbol}")
    click.echo(f"  Engine: {engine}")
    click.echo(f"  Mode: {'single session' if no_daemon else 'daemon'}")

    try:
        from shared.config.loader import ConfigLoader

        if engine == "legacy":
            from shared.ml.rl.paper_trader import run_paper_trader

            asyncio.run(run_paper_trader(
                config_path=config,
                model_name=model,
                symbol=symbol,
            ))
            return

        from services.trading.orchestrator import TradingConfig, TradingOrchestrator

        # Allow model override for rl_mppo strategy when running via orchestrator.
        if model.endswith(".zip") or "/" in model:
            model_path = model
        else:
            model_path = f"models/futures/rl/{model}/best_model.zip"
        os.environ["RL_MPPO_MODEL_PATH"] = model_path

        symbols = [symbol] if symbol else None
        if not symbols:
            try:
                cfg_data = ConfigLoader.load(config)
                paper_cfg = cfg_data.get("paper", {})
                cfg_symbol = paper_cfg.get("symbol")
                if isinstance(cfg_symbol, str) and cfg_symbol:
                    symbols = [cfg_symbol]
            except Exception:
                pass

        trading_config = TradingConfig.futures(
            strategy_name="rl_mppo",
            symbols=symbols,
        )
        trading_config.paper_trading = True
        orchestrator = TradingOrchestrator(trading_config)

        async def _run():
            if no_daemon:
                await orchestrator.run_session()
            else:
                await orchestrator.run()

        asyncio.run(_run())
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\nPaper trading stopped")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


@rl.command("generate-trajectories")
@click.option("--config", "-c", default="ml/rl_dt.yaml", help="Config file path")
@click.option("--output", "-o", default=None, help="Output path (default: from config)")
def rl_generate_trajectories(config: str, output: str | None):
    """MPPO expert rollout으로 DT 학습용 궤적 생성

    \b
    Example:
        sts rl generate-trajectories
        sts rl generate-trajectories --output models/futures/rl/dt_trajs.pt
    """
    click.echo("Generating expert trajectories for Decision Transformer")
    click.echo(f"  Config: {config}")

    try:
        from scripts.training.train_rl import load_data_from_clickhouse
        from shared.config.loader import ConfigLoader
        from shared.ml.rl.decision_transformer.dataset import TrajectoryCollector

        train_days, train_prices, _, _ = load_data_from_clickhouse(config)

        collector = TrajectoryCollector(config_path=config)
        trajs = collector.collect(train_days, train_prices)

        if output is None:
            cfg = ConfigLoader.load(config)
            output = cfg.get("trajectory", {}).get(
                "save_path", "models/futures/rl/dt_trajectories.pt"
            )

        collector.save(trajs, output)
        click.echo(f"Saved {len(trajs)} trajectories to {output}")

    except ImportError as e:
        click.echo(f"Error: Required package not installed: {e}", err=True)
        click.echo("Install with: pip install -e .[ml]", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@rl.command("tensorboard")
@click.option("--logdir", default="./results/rl/tensorboard/", help="TensorBoard log directory")
@click.option("--port", default=6006, type=int, help="TensorBoard port")
def rl_tensorboard(logdir: str, port: int):
    """TensorBoard 실행 (학습 커브 확인)

    \b
    Example:
        sts rl tensorboard
        sts rl tensorboard --port 6007
    """
    import subprocess

    click.echo("Starting TensorBoard")
    click.echo(f"  Log dir: {logdir}")
    click.echo(f"  URL: http://localhost:{port}")

    try:
        subprocess.run(
            ["tensorboard", "--logdir", logdir, "--port", str(port)],
            check=True,
        )
    except FileNotFoundError:
        click.echo("Error: TensorBoard not installed", err=True)
        click.echo("Install with: pip install tensorboard", err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\nTensorBoard stopped")


# =============================================================================
# TFT Commands
# =============================================================================


@cli.group()
def tft():
    """TFT (Temporal Fusion Transformer) 예측 모델 명령

    \b
    다중 시간 지평 수익률 예측/방향 분류 모델 학습/평가.
    모드: regression (수익률 회귀) | classification (방향 분류).
    """
    pass


@tft.command("train")
@click.option("--config", "-c", default="ml/tft.yaml", help="Config file path")
@click.option(
    "--mode", "-m", default=None,
    type=click.Choice(["regression", "classification"]),
    help="Override mode from config (regression|classification)",
)
def tft_train(config: str, mode: str | None):
    """TFT 모델 학습

    \b
    Example:
        sts tft train
        sts tft train --mode classification
        sts tft train --config ml/tft.yaml
    """
    from shared.ml.tft.trainer import TFTTrainer

    trainer = TFTTrainer(config_path=config, mode_override=mode)
    effective_mode = trainer.mode

    click.echo(f"Starting TFT Training ({effective_mode})")
    click.echo(f"  Config: {config}")
    click.echo("-" * 40)

    try:
        from scripts.training.train_rl import load_data_from_clickhouse

        train_days, train_prices, test_days, test_prices = load_data_from_clickhouse(config)

        model = trainer.train(
            train_features=train_days,
            train_prices=train_prices,
            eval_features=test_days,
            eval_prices=test_prices,
        )
        if effective_mode == "classification":
            save_name = "tft_cls_best"
        else:
            save_name = "tft_best"
        click.echo(f"Training complete. Model saved to {trainer.save_dir / save_name}")

    except ImportError as e:
        click.echo(f"Error: Required package not installed: {e}", err=True)
        click.echo("Install with: pip install torch", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@tft.command("evaluate")
@click.option("--model", "-m", default=None, help="Model name (directory under save_dir)")
@click.option("--config", "-c", default="ml/tft.yaml", help="Config file path")
@click.option(
    "--mode", default=None,
    type=click.Choice(["regression", "classification"]),
    help="Override mode from config",
)
def tft_evaluate(model: str | None, config: str, mode: str | None):
    """TFT 모델 평가

    \b
    예측 성능 + 트레이딩 시뮬레이션.
    regression: MSE, MAE, 방향 정확도, IC, Sharpe.
    classification: Accuracy, AUC-ROC, F1, Calibration, Sharpe.

    Example:
        sts tft evaluate
        sts tft evaluate --model tft_cls_best --mode classification
    """
    from shared.config import ConfigLoader
    from shared.ml.tft.trainer import TFTTrainer

    trainer = TFTTrainer(config_path=config, mode_override=mode)
    effective_mode = trainer.mode

    # Default model name based on mode
    if model is None:
        model = "tft_cls_best" if effective_mode == "classification" else "tft_best"

    cfg = ConfigLoader.load(config)
    save_dir = Path(cfg.get("training", {}).get("save_dir", "./models/futures/tft/"))
    model_dir = save_dir / model

    if not (model_dir / "model.pt").exists():
        click.echo(f"Error: Model not found at {model_dir}/", err=True)
        sys.exit(1)

    click.echo(f"Evaluating TFT Model ({effective_mode}): {model}")
    click.echo(f"  Model dir: {model_dir}")
    click.echo(f"  Config: {config}")
    click.echo("-" * 40)

    try:
        from scripts.training.train_rl import load_data_from_clickhouse
        from shared.ml.tft.model import TFTModel

        _, _, test_days, test_prices = load_data_from_clickhouse(config)

        loaded_model = TFTModel.load(model_dir)
        results = trainer.evaluate(loaded_model, test_days, test_prices)

        click.echo("\n=== Prediction Metrics ===")
        for k, v in results["prediction"].items():
            click.echo(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

        click.echo("\n=== Trading Simulation ===")
        for k, v in results["trading"].items():
            click.echo(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

        click.echo("\n=== Naive Baseline ===")
        for k, v in results["baseline_naive"].items():
            click.echo(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# =============================================================================
# Entry Point
# =============================================================================


def main():
    """CLI 진입점"""
    cli()


if __name__ == "__main__":
    main()
