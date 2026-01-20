"""CLI 메인 진입점

Usage:
    sts --help
    sts backtest run --strategy bb_reversion --asset stock
    sts optimize --strategy bb_reversion --trials 100
    sts mlflow ui
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

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
    import pandas as pd

    from shared.backtest import BacktestConfig, BacktestEngine, MLflowTracker
    from shared.config.loader import ConfigLoader
    from shared.strategy.registry import StrategyFactory

    click.echo(f"Running backtest: {strategy} ({asset})")

    # 전략 설정 로드
    try:
        strategy_config = ConfigLoader.load_strategy(asset, strategy)
    except FileNotFoundError:
        click.echo(f"Error: Strategy config not found: {asset}/{strategy}", err=True)
        sys.exit(1)

    click.echo(f"Loaded strategy config: {strategy_config['strategy']['name']}")

    # 데이터 로드
    if data:
        df = pd.read_csv(data, parse_dates=["datetime"])
        click.echo(f"Loaded data: {len(df)} rows")
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

    # 백테스트 실행
    engine = BacktestEngine(trading_strategy, config)
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
    timeout: int | None,
    output: str | None,
):
    """파라미터 최적화 실행

    \b
    Example:
        sts optimize -s bb_reversion -a stock -d ./data/005930.csv -n 100
        sts optimize -s bb_reversion -a stock -d data.csv --metric profit_factor
    """
    import pandas as pd

    click.echo(f"Optimizing: {strategy} ({asset})")
    click.echo(f"Trials: {trials}, Metric: {metric}")

    # 데이터 로드
    df = pd.read_csv(data, parse_dates=["datetime"])
    click.echo(f"Loaded data: {len(df)} rows")

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
def collect_start(symbol: tuple, interval: float, output: str | None):
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
    click.echo(f"  Strategy: {strategy}")
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
@click.option("--capital", "-c", default=10_000_000, type=float)
def paper_start(strategy: str, asset: str, capital: float):
    """모의 거래 시작

    \b
    Example:
        sts paper start -s bb_reversion -a stock
    """
    click.echo(f"Starting paper trading: {strategy} ({asset})")
    click.echo(f"  Capital: {capital:,.0f}")
    click.echo("  Status: Started (simulation)")


@paper.command("status")
def paper_status():
    """모의 거래 상태 조회"""
    click.echo("Paper Trading Status:")
    click.echo("-" * 40)
    click.echo("  Status: Not running")
    click.echo("  Note: Use 'sts paper start' to begin")


@paper.command("stop")
def paper_stop():
    """모의 거래 종료"""
    click.echo("Paper trading stopped")


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
        response = httpx.get(f"{url}/api/v1/health", timeout=5.0)
        if response.status_code == 200:
            data = response.json()
            click.echo("Health Check: ✓")
            click.echo(f"  Status: {data.get('status', 'unknown')}")
            click.echo(f"  Version: {data.get('version', 'unknown')}")
        else:
            click.echo(f"Health Check: ✗ ({response.status_code})")

        # Readiness
        response = httpx.get(f"{url}/api/v1/health/ready", timeout=5.0)
        if response.status_code == 200:
            data = response.json()
            click.echo("Readiness: ✓")
            components = data.get("components", {})
            for name, status in components.items():
                icon = "✓" if status else "✗"
                click.echo(f"  {name}: {icon}")
        else:
            click.echo(f"Readiness: ✗ ({response.status_code})")

    except httpx.ConnectError:
        click.echo("Health Check: ✗ (Connection refused)")
        click.echo("Note: Start API server with 'uvicorn services.api.app:app'")
    except ImportError:
        click.echo("Error: httpx not installed (pip install httpx)", err=True)
        sys.exit(1)


# =============================================================================
# Entry Point
# =============================================================================


def main():
    """CLI 진입점"""
    cli()


if __name__ == "__main__":
    main()
