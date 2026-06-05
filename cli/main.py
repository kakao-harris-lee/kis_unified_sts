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
from contextlib import suppress
from datetime import timedelta
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
        data        Research market-data export/validation
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


def _run_tier_backtest(
    strategy: str,
    asset: str,
    tier: str,
    start,
    end,
    capital: float,
    track: bool,
    experiment: str | None,
    is_daily: bool = False,
):
    """Run backtest across multiple stocks by tier, print summary table."""
    from shared.backtest import BacktestConfig, BacktestEngine
    from shared.backtest.adapter import BacktestStrategyAdapter
    from shared.backtest.config import RiskConfig
    from shared.collector.historical.stock import (
        STOCK_UNIVERSE,
    )
    from shared.config.loader import ConfigLoader
    from shared.storage import (
        MarketDataStoreError,
        StorageConfig,
        load_market_bars_for_backtest,
    )
    from shared.strategy.registry import StrategyFactory, register_builtin_components

    if is_daily:
        from shared.backtest.daily_adapter import (
            DailyBacktestAdapter,
        )

    register_builtin_components()
    storage_config = StorageConfig.load_or_default()

    if tier == "all":
        stocks = STOCK_UNIVERSE
    else:
        stocks = [s for s in STOCK_UNIVERSE if s["tier"] == tier]

    tf_label = "daily" if is_daily else "minute"
    click.echo(
        f"Tier backtest: {strategy} ({asset}, {tf_label}) — "
        f"{len(stocks)} stocks ({tier})"
    )
    click.echo(f"Market data source: {storage_config.market_data.source}")
    click.echo("=" * 80)

    strategy_config = ConfigLoader.load_strategy(asset, strategy)
    bt_override = strategy_config.get("strategy", {}).get("backtest", {})
    bt_capital = bt_override.get("initial_capital", capital)
    position_params = (
        strategy_config.get("strategy", {}).get("position", {}).get("params", {})
    )
    bt_position_size_pct = float(bt_override.get("position_size_pct", 10.0) or 10.0)
    max_positions = int(position_params.get("max_positions", 5) or 5)
    order_amount_per_stock = float(
        position_params.get("order_amount_per_stock", 0) or 0
    )
    if order_amount_per_stock <= 0:
        order_amount_per_stock = None

    start_d = start.date() if start else None
    end_d = end.date() if end else None

    results = []

    for stock in stocks:
        code = stock["code"]
        name = stock["name"]
        stock_tier = stock["tier"]

        try:
            df = load_market_bars_for_backtest(
                symbol=code,
                asset_class=asset,
                timeframe="daily" if is_daily else "minute",
                start=start_d,
                end=end_d,
                config=storage_config,
            )
            if df.empty:
                raise ValueError(
                    f"No {tf_label} data found for {code} in "
                    f"{storage_config.market_data.source} source"
                )
        except (MarketDataStoreError, ValueError):
            click.echo(f"  {code} {name}: No data — skipped")
            results.append(
                {
                    "code": code,
                    "name": name,
                    "tier": stock_tier,
                    "trades": 0,
                    "return_pct": 0,
                    "win_rate": 0,
                    "sharpe": 0,
                    "mdd": 0,
                    "status": "NO_DATA",
                }
            )
            continue

        config = BacktestConfig.stock(
            initial_capital=bt_capital,
            position_size_pct=bt_position_size_pct,
            order_amount_per_stock=order_amount_per_stock,
            max_positions=max_positions,
        )
        if "risk" in bt_override:
            config.risk = RiskConfig.from_dict(bt_override["risk"])

        trading_strategy = StrategyFactory.create(strategy_config)
        if is_daily:
            adapted = DailyBacktestAdapter(trading_strategy, strategy_config)
        else:
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

        results.append(
            {
                "code": code,
                "name": name,
                "tier": stock_tier,
                "trades": result.total_trades,
                "return_pct": result.total_return_pct,
                "win_rate": result.win_rate,
                "sharpe": result.sharpe_ratio,
                "mdd": result.max_drawdown_pct,
                "status": "OK",
            }
        )

    # Summary table
    click.echo("\n" + "=" * 80)
    click.echo("Summary Table")
    click.echo("=" * 80)
    click.echo(
        f"{'Code':<8} {'Name':<12} {'Tier':<7} {'Trades':>6} {'Return%':>9} {'WR%':>5} {'Sharpe':>7} {'MDD%':>7}"
    )
    click.echo("-" * 80)

    for r in results:
        if r["status"] == "NO_DATA":
            click.echo(
                f"{r['code']:<8} {r['name']:<12} {r['tier']:<7} {'—':>6} {'—':>9} {'—':>5} {'—':>7} {'—':>7}"
            )
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

    for t_label, t_key in [
        ("Top (대형주)", "top"),
        ("Mid (중형주)", "mid"),
        ("Bottom (소형주)", "bottom"),
    ]:
        tier_results = [
            r for r in results if r["tier"] == t_key and r["status"] == "OK"
        ]
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
    "--symbol",
    default=None,
    help="Symbol/code to load from configured market-data source (e.g., 005930)",
)
@click.option(
    "--tier",
    default=None,
    type=click.Choice(["top", "mid", "bottom", "all"]),
    help="Run backtest across tier stocks from configured market-data source",
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
    symbol: str | None,
    tier: str | None,
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
        ValidationError,
        validate_capital,
        validate_csv_file,
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

    # Detect timeframe from strategy config
    timeframe = strategy_config.get("strategy", {}).get("timeframe", "minute")
    is_daily = timeframe == "daily"

    if is_daily:
        click.echo("Timeframe: daily (swing strategy)")

    # 데이터 로드 및 검증
    if data:
        try:
            csv_validation_kwargs = {}
            if asset == "futures":
                # Futures RL backtest guardrails: reject malformed timeline and
                # heavily synthetic zero-volume datasets.
                csv_validation_kwargs = {
                    "reject_duplicate_datetime": True,
                    "require_monotonic_datetime": True,
                    "max_zero_volume_ratio": 0.95,
                    "max_zero_volume_price_move_ratio": 0.20,
                }
            df = validate_csv_file(data, **csv_validation_kwargs)
            click.echo(f"Loaded data from CSV: {len(df)} rows")
        except ValidationError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    elif symbol:
        try:
            start_d = start.date() if start else None
            end_d = end.date() if end else None
            from shared.storage import (
                MarketDataStoreError,
                StorageConfig,
                load_market_bars_for_backtest,
            )

            storage_config = StorageConfig.load_or_default()
            df = load_market_bars_for_backtest(
                symbol=symbol,
                asset_class=asset,
                timeframe="daily" if is_daily else "minute",
                start=start_d,
                end=end_d,
                config=storage_config,
            )
            if df.empty:
                source = storage_config.market_data.source
                raise ValueError(
                    f"No {timeframe} data found for {symbol} in {source} source"
                )
            source = storage_config.market_data.source
            click.echo(f"Loaded {symbol} from {source}: {len(df)} rows ({timeframe})")
        except (MarketDataStoreError, ValueError) as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    elif tier:
        _run_tier_backtest(
            strategy=strategy,
            asset=asset,
            tier=tier,
            start=start,
            end=end,
            capital=capital,
            track=track,
            experiment=experiment,
            is_daily=is_daily,
        )
        return
    else:
        click.echo(
            "Error: Data source required. Use --data, --symbol, or --tier", err=True
        )
        click.echo("  --data <path>     Load from CSV file")
        click.echo("  --symbol <code>   Load from configured market-data source")
        click.echo("  --tier <tier>     Run across tier stocks (top/mid/bottom/all)")
        sys.exit(1)

    # 날짜 필터링
    def _normalize_filter_datetime(value):
        """Align filter timestamp tz-awareness to df['datetime'] before comparison."""
        try:
            import pandas as pd

            series_tz = df["datetime"].dt.tz
            ts = pd.Timestamp(value)
            if series_tz is not None and ts.tzinfo is None:
                return ts.tz_localize(series_tz)
            if series_tz is None and ts.tzinfo is not None:
                return ts.tz_localize(None)
            return ts
        except Exception:
            return value

    if start:
        start_filter = _normalize_filter_datetime(start)
        df = df[df["datetime"] >= start_filter]
    if end:
        # Click option is parsed as 00:00:00 for YYYY-MM-DD inputs.
        # Treat plain-date end as inclusive for the whole day.
        end_filter = end
        if (
            end.hour == 0
            and end.minute == 0
            and end.second == 0
            and end.microsecond == 0
        ):
            end_filter = end + timedelta(days=1) - timedelta(microseconds=1)
        end_filter = _normalize_filter_datetime(end_filter)
        df = df[df["datetime"] <= end_filter]

    click.echo(f"Data range: {df['datetime'].min()} ~ {df['datetime'].max()}")

    # 백테스트 설정
    bt_override = strategy_config.get("strategy", {}).get("backtest", {})
    bt_capital = bt_override.get("initial_capital", capital)
    position_params = (
        strategy_config.get("strategy", {}).get("position", {}).get("params", {})
    )
    bt_position_size_pct = float(bt_override.get("position_size_pct", 10.0) or 10.0)
    max_positions = int(position_params.get("max_positions", 5) or 5)
    order_amount_per_stock = float(
        position_params.get("order_amount_per_stock", 0) or 0
    )
    if order_amount_per_stock <= 0:
        order_amount_per_stock = None

    if asset == "stock":
        config = BacktestConfig.stock(
            initial_capital=bt_capital,
            position_size_pct=bt_position_size_pct,
            order_amount_per_stock=order_amount_per_stock,
            max_positions=max_positions,
        )
    else:
        config = BacktestConfig.futures(
            initial_capital=bt_capital,
            point_value=bt_override.get("point_value", 50_000),
        )

    # 전략 YAML의 backtest.risk로 리스크 설정 오버라이드
    if "risk" in bt_override:
        from shared.backtest.config import RiskConfig

        config.risk = RiskConfig.from_dict(bt_override["risk"])

    # 전략 생성
    try:
        trading_strategy = StrategyFactory.create(strategy_config)
    except Exception as e:
        click.echo(f"Error creating strategy: {e}", err=True)
        sys.exit(1)

    # 어댑터로 감싸기 (TradingStrategy → StrategyProtocol)
    if is_daily:
        from shared.backtest.daily_adapter import DailyBacktestAdapter

        adapted = DailyBacktestAdapter(trading_strategy, strategy_config)
    else:
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
    from shared.validation.cli_validators import ValidationError, validate_csv_file

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
        click.echo(
            "Error: mlflow not found. Install with: pip install mlflow", err=True
        )
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

        from shared.backtest.mlflow_uri import resolve_tracking_uri

        mlf.set_tracking_uri(resolve_tracking_uri())
        experiments = mlf.search_experiments()

        click.echo("MLflow Experiments:")
        click.echo("-" * 40)
        for exp in experiments:
            click.echo(f"  [{exp.experiment_id}] {exp.name}")
    except ImportError:
        click.echo("MLflow not installed", err=True)
        sys.exit(1)


# =============================================================================
# Research Market Data Commands
# =============================================================================


@cli.group("data")
def data_cmd():
    """Research market-data export and validation commands.

    \b
    Examples:
        sts data validate-parquet --root data/market
    """
    pass


def _resolve_parquet_export_root(out: str, *, asset: str, timeframe: str) -> Path:
    """Accept either data/market or data/market/<asset>/<timeframe>."""
    path = Path(out)
    if path.name == timeframe and path.parent.name == asset:
        return path.parent.parent
    return path


@data_cmd.command("validate-parquet")
@click.option(
    "--root", default=None, help="Parquet dataset root (default: storage config)"
)
@click.option(
    "--allow-empty",
    is_flag=True,
    help="Return success even when the dataset has no parquet files",
)
def data_validate_parquet(root: str | None, allow_empty: bool):
    """Validate the configured Parquet/DuckDB market-data dataset."""
    from shared.storage import ParquetMarketDataStore, StorageConfig

    if root is None:
        root = StorageConfig.load_or_default().market_data.parquet.root

    store = ParquetMarketDataStore(root)
    manifest = store.dataset_manifest()
    files = int(manifest.get("parquet_files", 0) or 0)
    rows = int(manifest.get("row_count", 0) or 0)

    click.echo(f"Parquet root: {manifest.get('root', root)}")
    click.echo(f"Files: {files}")
    click.echo(f"Rows: {rows}")
    if manifest.get("min_datetime") or manifest.get("max_datetime"):
        click.echo(
            f"Range: {manifest.get('min_datetime')} -> {manifest.get('max_datetime')}"
        )

    if files == 0 and not allow_empty:
        click.echo("Error: no parquet files found", err=True)
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


def _require_parquet_sink(sink: str) -> None:
    if sink != "parquet":
        raise click.ClickException(
            "ClickHouse sink has been removed. Collect and inspect Parquet data."
        )


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
        from shared.collector import CollectorConfig, DataCollector

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
# Scan Commands
# =============================================================================


@cli.group()
def scan():
    """스캔/스크리닝 명령

    \b
    Examples:
        sts scan daily              # Run daily scanner with default universe
        sts scan daily --symbols 005930,000660
    """
    pass


@scan.command("daily")
@click.option(
    "--symbols",
    "-s",
    type=str,
    default=None,
    help="Comma-separated stock codes (default: STOCK_UNIVERSE)",
)
def scan_daily(symbols: str | None):
    """Run daily scanner for pre-market universe selection

    Scans stock universe using daily candle data and publishes filtered
    watchlists to Redis for consumption by intraday trading strategies.

    Applies Layer 1 filters:
    - Minimum edge (ATR vs trading costs)
    - Trend pullback (uptrend + RSI pullback)
    - Momentum breakout (near N-day high + rising volume)

    Results are published to Redis key ``system:daily_watchlist:latest``.

    \b
    Examples:
        sts scan daily
        sts scan daily --symbols 005930,000660,035720
    """
    from services.daily_scanner import DailyScanner, DailyScannerConfig
    from shared.collector.historical.stock import STOCK_UNIVERSE

    # Parse symbols
    if symbols:
        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    else:
        symbol_list = [item["code"] for item in STOCK_UNIVERSE]

    if not symbol_list:
        click.echo("Error: No symbols provided", err=True)
        sys.exit(1)

    click.echo("=" * 80)
    click.echo("Daily Scanner Starting")
    click.echo(f"Universe size: {len(symbol_list)} stocks")
    click.echo("=" * 80)

    try:
        # Load configuration
        config = DailyScannerConfig.from_yaml()
        click.echo(f"Loaded DailyScannerConfig from {config._default_config_file}")

        # Initialize scanner
        scanner = DailyScanner(config)

        # Run scan and publish to Redis
        result = scanner.scan_and_publish(symbol_list)

        # Print results table
        click.echo("\n" + "=" * 80)
        click.echo("Daily Scanner Results")
        click.echo("=" * 80)

        tp_stocks = result.get("trend_pullback", [])
        mb_stocks = result.get("momentum_breakout", [])

        click.echo(f"\nTrend Pullback Watchlist ({len(tp_stocks)} stocks):")
        click.echo("-" * 80)
        if tp_stocks:
            for i, code in enumerate(tp_stocks, 1):
                click.echo(f"  {i:2}. {code}")
        else:
            click.echo("  (none)")

        click.echo(f"\nMomentum Breakout Watchlist ({len(mb_stocks)} stocks):")
        click.echo("-" * 80)
        if mb_stocks:
            for i, code in enumerate(mb_stocks, 1):
                click.echo(f"  {i:2}. {code}")
        else:
            click.echo("  (none)")

        click.echo("\n" + "=" * 80)
        click.echo("Summary")
        click.echo("=" * 80)
        click.echo(f"  Trend pullback watchlist:    {len(tp_stocks):>5} stocks")
        click.echo(f"  Momentum breakout watchlist: {len(mb_stocks):>5} stocks")
        click.echo(f"  Published to Redis: {config.redis_key}")
        click.echo(
            f"  TTL: {config.redis_ttl_seconds}s ({config.redis_ttl_seconds // 3600}h)"
        )
        click.echo("=" * 80)

    except Exception as exc:
        click.echo(f"Error: Daily scanner failed: {exc}", err=True)
        import traceback

        if logging.getLogger().level <= logging.DEBUG:
            traceback.print_exc()
        sys.exit(1)


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
@click.option(
    "--yes-live",
    is_flag=True,
    help="Confirm live trading non-interactively. Requires KIS_REAL_TRADING=true.",
)
def trade_start(
    strategy: str,
    asset: str,
    capital: float,
    paper: bool,
    daemon: bool,
    yes_live: bool,
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
        live_env = os.getenv("KIS_REAL_TRADING", "").lower() in {
            "1",
            "true",
            "yes",
        }
        if yes_live:
            if not live_env:
                click.echo(
                    "Error: --yes-live requires KIS_REAL_TRADING=true",
                    err=True,
                )
                sys.exit(1)
        elif not click.confirm("⚠️  LIVE TRADING - Are you sure?"):
            click.echo("Aborted.")
            return

    try:
        from services.trading.orchestrator import (
            TradingConfig,
            TradingOrchestrator,
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
            import signal

            loop = asyncio.get_running_loop()
            shutdown_requested = False

            def _request_shutdown():
                """Handle SIGTERM/SIGINT with guard against concurrent signals.

                No lock needed: asyncio signal handlers are executed sequentially
                on the event loop (single-threaded), preventing race conditions.
                """
                nonlocal shutdown_requested
                if shutdown_requested:
                    logging.getLogger("cli.main").debug(
                        "Duplicate shutdown signal ignored (shutdown already in progress)"
                    )
                    return
                shutdown_requested = True
                logging.getLogger("cli.main").info(
                    "Shutdown signal received, stopping gracefully..."
                )
                asyncio.ensure_future(orchestrator.stop())

            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, _request_shutdown)

            try:
                if daemon:
                    await orchestrator.run()
                else:
                    await orchestrator.run_session()
            finally:
                if not shutdown_requested:
                    await orchestrator.stop()

        with suppress(KeyboardInterrupt):
            asyncio.run(run())

    except ImportError as e:
        click.echo(f"Error: Required module not installed: {e}", err=True)
        sys.exit(1)


@trade.command("status")
@click.option(
    "--url",
    "-u",
    default="http://localhost:8001",
    help="Dashboard API URL",
)
def trade_status(url: str):
    """트레이딩 상태 조회

    \b
    Example:
        sts trade status
        sts trade status --url http://localhost:8001
    """
    try:
        import httpx

        response = httpx.get(f"{url}/api/trading/status", timeout=5.0)
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
        click.echo(
            "  Note: Start API server with 'uvicorn services.dashboard.app:create_app --factory'"
        )


@trade.command("stop")
@click.option(
    "--url",
    "-u",
    default="http://localhost:8001",
    help="Dashboard API URL",
)
def trade_stop(url: str):
    """트레이딩 종료

    \b
    Example:
        sts trade stop
        sts trade stop --url http://localhost:8001
    """
    try:
        import httpx

        response = httpx.post(
            f"{url}/api/trading/stop",
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
@click.option(
    "--capital", "-c", default=10_000_000, type=float, help="Initial capital (KRW)"
)
@click.option(
    "--max-positions", "-m", default=5, type=int, help="Maximum concurrent positions"
)
def paper_start(strategy: str, asset: str, capital: float, max_positions: int):
    """모의 거래 시작

    \b
    Example:
        sts paper start -s bb_reversion -a stock
        sts paper start -s ofi_momentum -a futures --capital 50000000
    """
    import asyncio

    click.echo("Starting Paper Trading")
    click.echo(f"  Strategy: {strategy}")
    click.echo(f"  Asset: {asset}")
    click.echo(f"  Capital: {capital:,.0f} KRW")
    click.echo(f"  Max Positions: {max_positions}")
    click.echo("-" * 40)

    try:
        from shared.config.loader import ConfigLoader
        from shared.paper.config import PaperTradingConfig
        from shared.paper.engine import PaperTradingEngine

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
            account = data.get("account")
            if isinstance(account, dict):
                click.echo("")
                click.echo("Account:")
                click.echo(
                    f"  Initial Balance:  {account.get('initial_balance', 0):>16,.0f} KRW"
                )
                click.echo(
                    f"  Cash Balance:     {account.get('balance', 0):>16,.0f} KRW"
                )
                click.echo(
                    f"  Equity (M2M):     {account.get('equity', 0):>16,.0f} KRW"
                )
                click.echo(
                    f"  Realized P&L:     {account.get('realized_pnl', 0):>16,+.0f} KRW"
                )
                click.echo(
                    f"  Unrealized P&L:   {account.get('unrealized_pnl', 0):>16,+.0f} KRW"
                )
                click.echo(
                    f"  Open Positions:   {account.get('open_positions', 0):>16d}"
                )
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
    default="http://localhost:8001",
    help="Dashboard API URL",
)
def health(url: str):
    """시스템 헬스 체크

    \b
    Example:
        sts health
        sts health --url http://localhost:8001
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

        # Readiness: the dashboard exposes a single /health (no separate
        # /health/ready); reuse it as the readiness signal.
        try:
            response = httpx.get(f"{url}/health", timeout=5.0)
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
        click.echo(
            "Note: Start API server with 'uvicorn services.dashboard.app:create_app --factory'"
        )
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
