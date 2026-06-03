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
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

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
        load_stock_minute_from_clickhouse,
    )
    from shared.config.loader import ConfigLoader
    from shared.strategy.registry import StrategyFactory, register_builtin_components

    if is_daily:
        from shared.backtest.daily_adapter import (
            DailyBacktestAdapter,
            load_stock_daily_from_clickhouse,
        )

    register_builtin_components()

    if tier == "all":
        stocks = STOCK_UNIVERSE
    else:
        stocks = [s for s in STOCK_UNIVERSE if s["tier"] == tier]

    tf_label = "daily" if is_daily else "minute"
    click.echo(f"Tier backtest: {strategy} ({asset}, {tf_label}) — {len(stocks)} stocks ({tier})")
    click.echo("=" * 80)

    strategy_config = ConfigLoader.load_strategy(asset, strategy)
    bt_override = strategy_config.get("strategy", {}).get("backtest", {})
    bt_capital = bt_override.get("initial_capital", capital)
    position_params = (
        strategy_config.get("strategy", {})
        .get("position", {})
        .get("params", {})
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
            if is_daily:
                df = load_stock_daily_from_clickhouse(code, start_d, end_d)
            else:
                df = load_stock_minute_from_clickhouse(code, start_d, end_d)
        except ValueError:
            click.echo(f"  {code} {name}: No data — skipped")
            results.append({
                "code": code, "name": name, "tier": stock_tier,
                "trades": 0, "return_pct": 0, "win_rate": 0,
                "sharpe": 0, "mdd": 0, "status": "NO_DATA",
            })
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

        results.append({
            "code": code, "name": name, "tier": stock_tier,
            "trades": result.total_trades,
            "return_pct": result.total_return_pct,
            "win_rate": result.win_rate,
            "sharpe": result.sharpe_ratio,
            "mdd": result.max_drawdown_pct,
            "status": "OK",
        })

    # Summary table
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
    help="Run backtest across tier stocks from ClickHouse (top/mid/bottom/all)",
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
        click.echo("Error: Data source required. Use --data, --symbol, or --tier", err=True)
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
        strategy_config.get("strategy", {})
        .get("position", {})
        .get("params", {})
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
        sts data export-clickhouse --asset futures --database kospi --table kospi200f_1m --out data/market/futures/minute
        sts data validate-parquet --root data/market
    """
    pass


def _validate_clickhouse_identifier(value: str, label: str) -> str:
    import re

    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value or ""):
        raise click.BadParameter(f"invalid {label}: {value!r}")
    return value


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


@data_cmd.command("export-clickhouse")
@click.option(
    "--asset",
    type=click.Choice(["stock", "futures"]),
    required=True,
    help="Asset class to export",
)
@click.option("--database", required=True, help="ClickHouse database")
@click.option("--table", default="", help="ClickHouse table")
@click.option("--symbol", default=None, help="Optional code/symbol filter")
@click.option(
    "--timeframe",
    type=click.Choice(["minute", "daily"]),
    default="minute",
    show_default=True,
)
@click.option("--start", type=click.DateTime(formats=["%Y-%m-%d"]), help="Start date")
@click.option("--end", type=click.DateTime(formats=["%Y-%m-%d"]), help="End date")
@click.option(
    "--out",
    default="data/market",
    show_default=True,
    help="Parquet root or data/market/<asset>/<timeframe> directory",
)
@click.option("--limit", type=int, default=0, help="Optional max rows for smoke export")
def data_export_clickhouse(
    asset: str,
    database: str,
    table: str,
    symbol: str | None,
    timeframe: str,
    start,
    end,
    out: str,
    limit: int,
):
    """Export standard OHLCV rows from ClickHouse into Parquet partitions."""
    import pandas as pd
    from clickhouse_driver import Client as CHSyncClient

    from shared.storage import ParquetMarketDataStore

    database = _validate_clickhouse_identifier(database, "database")
    default_table = "kospi200f_1m" if asset == "futures" else "minute_candles"
    table = _validate_clickhouse_identifier(table or default_table, "table")

    time_column = "date" if timeframe == "daily" else "datetime"
    conditions = []
    params: dict[str, object] = {}
    if symbol:
        conditions.append("code = %(code)s")
        params["code"] = symbol
    if start:
        conditions.append(f"{time_column} >= %(start)s")
        params["start"] = start.date() if timeframe == "daily" else start
    if end:
        if timeframe == "daily":
            conditions.append(f"{time_column} <= %(end)s")
            params["end"] = end.date()
        else:
            # CLI dates are day-level. Use a half-open range so
            # --end 2026-06-03 includes the full 2026-06-03 minute session.
            conditions.append(f"{time_column} < %(end_exclusive)s")
            params["end_exclusive"] = end + timedelta(days=1)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    limit_sql = "LIMIT %(limit)s" if limit and limit > 0 else ""
    if limit_sql:
        params["limit"] = int(limit)

    query = f"""
        SELECT code, {time_column} AS datetime, open, high, low, close, volume
        FROM {database}.{table}
        {where}
        ORDER BY code, {time_column}
        {limit_sql}
    """

    client = CHSyncClient(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_NATIVE_PORT", "9000")),
        user=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
    )
    rows = client.execute(query, params)
    if not rows:
        click.echo("Error: ClickHouse query returned no rows", err=True)
        sys.exit(1)

    df = pd.DataFrame(
        rows,
        columns=["code", "datetime", "open", "high", "low", "close", "volume"],
    )
    parquet_root = _resolve_parquet_export_root(out, asset=asset, timeframe=timeframe)
    store = ParquetMarketDataStore(parquet_root, asset_class=asset)
    if timeframe == "daily":
        written = store.append_daily_bars(df)
    else:
        written = store.append_minute_bars(df)

    click.echo(
        f"Exported {written} rows from {database}.{table} "
        f"to {parquet_root}/{asset}/{timeframe}"
    )


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
@click.option(
    "--no-resume",
    is_flag=True,
    default=False,
    help="Force re-collect all selected products/days (ignore saved state)",
)
def backfill_run(
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

    from shared.collector.historical import (
        backfill as do_backfill,
        backfill_kospi200_index,
        backfill_kospi200f,
        backfill_all,
    )

    click.echo(f"Starting backfill for {days} days...")
    resume = not no_resume

    if all_products:
        asyncio.run(backfill_all(days=days, resume=resume))
    else:
        if mini:
            click.echo("Backfilling Mini KOSPI200 futures...")
            asyncio.run(do_backfill(days=days, resume=resume))
        if index:
            click.echo("Backfilling KOSPI200 index...")
            asyncio.run(backfill_kospi200_index(days=days, resume=resume))
        if futures:
            click.echo("Backfilling KOSPI200 futures...")
            asyncio.run(backfill_kospi200f(days=days, resume=resume))

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
def stock_backfill_run(days: int, codes: tuple, no_resume: bool):
    """주식 분봉 데이터 백필 실행

    \b
    Example:
        sts stock-backfill run --days 7
        sts stock-backfill run --days 30 -c 005930 -c 000660
        sts stock-backfill run --days 180 --no-resume
    """
    import asyncio

    from shared.collector.historical.stock import backfill_stock_minute

    click.echo(f"Starting stock minute backfill for {days} days...")

    codes_list = list(codes) if codes else None
    asyncio.run(backfill_stock_minute(days=days, codes=codes_list, resume=not no_resume))

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


@stock_backfill.command("daily")
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
def stock_backfill_daily(days: int, codes: tuple):
    """주식 일봉 데이터 백필 실행.

    \b
    Example:
        sts stock-backfill daily --days 100
        sts stock-backfill daily --days 30 -c 005930 -c 000660
    """
    import asyncio

    from shared.collector.historical.daily_stock import collect_daily_candles

    codes_list = list(codes) if codes else None
    click.echo(f"Starting stock daily backfill for {days} days...")
    rows = asyncio.run(collect_daily_candles(codes=codes_list, days=days, verbose=True))
    click.echo(f"Daily backfill complete! rows={rows:,}")


@stock_backfill.command("daily-status")
@click.option(
    "--days",
    "-d",
    default=100,
    type=int,
    help="Period to check (default: 100 days)",
)
def stock_backfill_daily_status(days: int):
    """주식 일봉 데이터 수집 현황 조회."""
    from shared.collector.historical.daily_stock import get_daily_collection_status
    from shared.collector.historical.stock_universe import STOCK_UNIVERSE

    click.echo(f"Stock Daily Data Collection Status (last {days} days)")
    click.echo("=" * 50)
    click.echo(f"Universe: {len(STOCK_UNIVERSE)} stocks")
    click.echo()

    status = get_daily_collection_status(days=days)
    if "error" in status:
        click.echo(f"Error: {status['error']}", err=True)
        return

    click.echo(f"Table: {status['table']}")
    click.echo(f"   Rows: {status.get('rows', 0):,}")
    click.echo(f"   Days Collected: {status.get('days_collected', 0)}")
    click.echo(f"   Unique Codes: {status.get('unique_codes', 0)}")
    if status.get("min_date"):
        click.echo(f"   Range: {status['min_date']} ~ {status['max_date']}")


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

    click.echo(f"Table: {status['table']}")
    click.echo(f"   Rows: {status.get('rows', 0):,}")
    click.echo(f"   Days Collected: {status.get('days_collected', 0)}")
    click.echo(f"   Unique Codes: {status.get('unique_codes', 0)}")
    if status.get("min_datetime"):
        click.echo(f"   Range: {status['min_datetime']} ~ {status['max_datetime']}")

    stocks = status.get("stocks", [])
    if stocks:
        click.echo(f"\n{'Code':<8} {'Bars':>8} {'Days':>5} {'Earliest':<20} {'Latest':<20}")
        click.echo("-" * 65)
        for s in stocks:
            click.echo(
                f"{s['code']:<8} {s['bars']:>8,} {s['trading_days']:>5} "
                f"{s.get('earliest', '-'):<20} {s.get('latest', '-'):<20}"
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
    from shared.collector.historical.stock import STOCK_UNIVERSE
    from services.daily_scanner import DailyScanner, DailyScannerConfig

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
        click.echo(f"  TTL: {config.redis_ttl_seconds}s ({config.redis_ttl_seconds // 3600}h)")
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

        try:
            asyncio.run(run())
        except KeyboardInterrupt:
            pass  # Signal handler already initiated shutdown

    except ImportError as e:
        click.echo(f"Error: Required module not installed: {e}", err=True)
        sys.exit(1)


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

    click.echo("Starting Paper Trading")
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
        sts rl pipeline
        sts rl slippage --model mppo_best
        sts rl tensorboard
    """
    pass


def _write_temp_rl_config(
    base_config_path: str,
    *,
    database: str,
    table: str,
    symbol: str,
) -> tuple[str, Path]:
    """Write a temporary RL config overriding data source fields."""
    import copy

    import yaml

    from shared.config.loader import ConfigLoader

    base_cfg = ConfigLoader.load(base_config_path, use_cache=False)
    cfg = copy.deepcopy(base_cfg)
    data_cfg = cfg.setdefault("data", {})
    data_cfg["source"] = "clickhouse"
    data_cfg["database"] = database
    data_cfg["table"] = table
    data_cfg["symbol"] = symbol
    # Do not silently fall back to synthetic samples in production pipeline.
    data_cfg["allow_sample_fallback"] = False

    rel_path = f"ml/.tmp_rl_pipeline_{uuid4().hex}.yaml"
    abs_path = ConfigLoader.get_config_dir() / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True)
    ConfigLoader.clear_cache()
    return rel_path, abs_path


def _select_default_mini_symbol(database: str, table: str) -> str:
    """Pick the densest A05* symbol from ClickHouse as mini validation symbol."""
    from clickhouse_driver import Client as CHSyncClient

    client = CHSyncClient(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_NATIVE_PORT", "9000")),
        user=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
    )
    rows = client.execute(
        f"""
        SELECT code, count() AS c
        FROM {database}.{table}
        WHERE code LIKE 'A05%'
        GROUP BY code
        ORDER BY c DESC
        LIMIT 1
        """
    )
    if not rows:
        raise ValueError(f"No mini symbols found in {database}.{table}")
    return str(rows[0][0])


def _resolve_trained_model_path(config_path: str, algo: str = "mppo") -> Path:
    """Resolve trained model path, preferring best model for inference."""
    import shutil

    from shared.config.loader import ConfigLoader

    cfg = ConfigLoader.load(config_path)
    save_dir = Path(cfg.get("training", {}).get("save_dir", "./models/futures/rl/"))
    best = save_dir / f"{algo}_best" / "best_model.zip"
    final_zip = Path(str(save_dir / f"{algo}_final") + ".zip")

    if best.exists():
        return best
    if final_zip.exists():
        best.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(final_zip, best)
        return best
    raise FileNotFoundError(
        f"Trained model not found. expected one of: {best} or {final_zip}"
    )


def _evaluate_maskableppo_with_config(
    *,
    model_path: Path,
    config_path: str,
) -> dict:
    """Run evaluation with a specific data config."""
    from sb3_contrib import MaskablePPO

    from scripts.training.train_rl import load_data_from_clickhouse, precompute_tft_aux
    from shared.ml.rl.evaluator import RLEvaluator

    _, _, test_days, test_prices = load_data_from_clickhouse(config_path)
    _, test_aux = precompute_tft_aux(config_path)
    model = MaskablePPO.load(str(model_path))
    evaluator = RLEvaluator(config_path=config_path)
    return evaluator.evaluate_model(
        model,
        test_days,
        test_prices,
        test_aux=test_aux,
    )


def _run_futures_backtest_with_table(
    *,
    strategy: str,
    symbol: str,
    table: str,
    start,
    end,
    track: bool,
    experiment: str | None,
    capital: float = 100_000_000,
) -> None:
    """Run existing backtest command logic with temporary futures table override."""
    prev_table = os.getenv("FUTURES_CANDLE_TABLE")
    os.environ["FUTURES_CANDLE_TABLE"] = table
    runner = getattr(backtest_run, "callback", backtest_run)
    try:
        runner(
            strategy=strategy,
            asset="futures",
            start=start,
            end=end,
            capital=capital,
            data=None,
            symbol=symbol,
            tier=None,
            track=track,
            experiment=experiment,
        )
    except SystemExit as e:
        if e.code not in (0, None):
            raise RuntimeError(
                f"Backtest failed for {symbol} ({table}) with exit code {e.code}"
            ) from e
    finally:
        if prev_table is None:
            os.environ.pop("FUTURES_CANDLE_TABLE", None)
        else:
            os.environ["FUTURES_CANDLE_TABLE"] = prev_table


def _validate_rl_config(config_path: str):
    """Validate RL config and return validated config object.

    Args:
        config_path: Path to config YAML file

    Returns:
        Validated RLMPPOConfig object

    Raises:
        SystemExit: If validation fails
    """
    from pydantic import ValidationError
    from shared.ml.rl.config import RLMPPOConfig

    try:
        validated_config = RLMPPOConfig.from_yaml(config_path)
        click.echo("✓ Config validation passed")
        click.echo(
            f"  Learning rate: {validated_config.mppo.learning_rate}, "
            f"Initial balance: {validated_config.env.initial_balance:,.0f}"
        )
        return validated_config
    except ValidationError as e:
        click.echo("✗ Config validation failed:", err=True)
        click.echo("", err=True)
        for error in e.errors():
            field = ".".join(str(x) for x in error["loc"])
            msg = error["msg"]
            value = error.get("input")
            click.echo(f"  Field: {field}", err=True)
            click.echo(f"  Error: {msg}", err=True)
            if value is not None:
                click.echo(f"  Value: {value}", err=True)
            click.echo("", err=True)
        click.echo(
            f"Fix the validation errors in {config_path} and try again.", err=True
        )
        sys.exit(1)


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

        # Validate config early to fail fast before expensive data loading
        # RLMPPOConfig validation only applies to MPPO configs
        if algo in ("mppo", "all"):
            _validate_rl_config(config)

        train_days, train_prices, test_days, test_prices = load_data_from_clickhouse(
            config,
            persist_scaler=True,
        )

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

    # Validate config early (only for MPPO configs)
    if not is_dt and not is_sac:
        _validate_rl_config(config)

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


@rl.command("pipeline")
@click.option("--config", "-c", default="ml/rl_mppo.yaml", help="Base RL config path")
@click.option(
    "--strategy",
    default="rl_mppo",
    show_default=True,
    help="Backtest strategy profile",
)
@click.option("--database", default="kospi", show_default=True, help="ClickHouse database")
@click.option(
    "--kospi-table",
    default="kospi200f_1m",
    show_default=True,
    help="KOSPI200 table for train/validate/backtest",
)
@click.option(
    "--kospi-symbol",
    default="101S6000",
    show_default=True,
    help="KOSPI200 symbol for train/validate/backtest",
)
@click.option(
    "--mini-table",
    default="kospi_mini_1m",
    show_default=True,
    help="KOSPI mini table for validation/backtest",
)
@click.option(
    "--mini-symbol",
    default="",
    help="KOSPI mini symbol for validation/backtest (default: densest A05* auto-pick)",
)
@click.option("--start", type=click.DateTime(formats=["%Y-%m-%d"]), help="Backtest start date")
@click.option("--end", type=click.DateTime(formats=["%Y-%m-%d"]), help="Backtest end date")
@click.option("--track/--no-track", default=False, show_default=True, help="Track backtest with MLflow")
@click.option("--experiment", default=None, help="MLflow experiment name for backtests")
@click.option("--skip-train", is_flag=True, help="Skip training stage")
@click.option("--skip-eval", is_flag=True, help="Skip validation stage")
@click.option("--skip-backtest", is_flag=True, help="Skip backtest stage")
def rl_pipeline(
    config: str,
    strategy: str,
    database: str,
    kospi_table: str,
    kospi_symbol: str,
    mini_table: str,
    mini_symbol: str,
    start,
    end,
    track: bool,
    experiment: str | None,
    skip_train: bool,
    skip_eval: bool,
    skip_backtest: bool,
):
    """KOSPI200 RL 파이프라인: train -> validate(KOSPI200+mini) -> backtest."""
    from scripts.training.train_rl import load_data_from_clickhouse, precompute_tft_aux
    from shared.ml.rl.trainer import RLTrainer

    temp_config_paths: list[Path] = []
    mini_symbol_selected = mini_symbol.strip()
    if not mini_symbol_selected:
        mini_symbol_selected = _select_default_mini_symbol(database, mini_table)

    click.echo("RL KOSPI Pipeline")
    click.echo(f"  Base config: {config}")
    click.echo(f"  Train data: {database}.{kospi_table} ({kospi_symbol})")
    click.echo(
        f"  Validate data: {database}.{kospi_table} ({kospi_symbol}) + "
        f"{database}.{mini_table} ({mini_symbol_selected})"
    )
    click.echo(f"  Backtest strategy: {strategy}")
    click.echo("-" * 50)

    # Validate config early
    _validate_rl_config(config)

    try:
        train_cfg_rel, train_cfg_abs = _write_temp_rl_config(
            config,
            database=database,
            table=kospi_table,
            symbol=kospi_symbol,
        )
        temp_config_paths.append(train_cfg_abs)

        if not skip_train:
            click.echo("[1/3] Training on KOSPI200 data...")
            train_days, train_prices, test_days, test_prices = load_data_from_clickhouse(
                train_cfg_rel,
                persist_scaler=True,
            )
            train_aux, test_aux = precompute_tft_aux(train_cfg_rel)

            trainer = RLTrainer(config_path=train_cfg_rel)
            trainer.train(
                algo="mppo",
                train_days=train_days,
                train_prices=train_prices,
                eval_days=test_days,
                eval_prices=test_prices,
                train_aux=train_aux,
                eval_aux=test_aux,
            )
            click.echo("  Training complete.")
        else:
            click.echo("[1/3] Training skipped (--skip-train)")

        model_path = _resolve_trained_model_path(train_cfg_rel, algo="mppo")
        click.echo(f"  Model for inference: {model_path}")

        if not skip_eval:
            click.echo("[2/3] Validation on KOSPI200 + KOSPI mini...")
            eval_targets = [
                ("KOSPI200", kospi_table, kospi_symbol),
                ("KOSPI Mini", mini_table, mini_symbol_selected),
            ]
            for label, table, symbol in eval_targets:
                eval_cfg_rel, eval_cfg_abs = _write_temp_rl_config(
                    config,
                    database=database,
                    table=table,
                    symbol=symbol,
                )
                temp_config_paths.append(eval_cfg_abs)
                results = _evaluate_maskableppo_with_config(
                    model_path=model_path,
                    config_path=eval_cfg_rel,
                )
                click.echo(f"  [{label}]")
                for key, value in results.items():
                    if key == "daily_returns":
                        continue
                    click.echo(f"    {key}: {value}")
        else:
            click.echo("[2/3] Validation skipped (--skip-eval)")

        if not skip_backtest:
            click.echo("[3/3] Backtest on KOSPI200 + KOSPI mini...")
            _run_futures_backtest_with_table(
                strategy=strategy,
                symbol=kospi_symbol,
                table=kospi_table,
                start=start,
                end=end,
                track=track,
                experiment=experiment,
            )
            _run_futures_backtest_with_table(
                strategy=strategy,
                symbol=mini_symbol_selected,
                table=mini_table,
                start=start,
                end=end,
                track=track,
                experiment=experiment,
            )
            click.echo("  Backtest complete.")
        else:
            click.echo("[3/3] Backtest skipped (--skip-backtest)")

        click.echo("Pipeline complete.")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    finally:
        for path in temp_config_paths:
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass


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

    # Validate config early
    _validate_rl_config(config)

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
@click.option(
    "--strategy",
    default=None,
    show_default=True,
    help=(
        "Futures strategy profile name.  Default (None) loads ALL "
        "strategies whose `strategy.enabled: true` in "
        "`config/strategies/futures/*.yaml` (Phase 2 cutover: rl_mppo "
        "shadow + Setup A/C primary).  Pass an explicit name to load "
        "only that single strategy (legacy single-profile mode)."
    ),
)
@click.option(
    "--symbol",
    "-s",
    default=None,
    help="Futures symbol override (default: auto-detected KOSPI200 mini front-month)",
)
@click.option("--no-daemon", is_flag=True, help="Run single session (foreground, no loop)")
def rl_paper(
    model: str,
    config: str,
    strategy: str,
    symbol: str,
    no_daemon: bool,
):
    """RL Paper Trading 실행

    \b
    학습된 MaskablePPO 모델로 실시간 paper trading.
    Orchestrator 경로(전략/리스크/주문 공통 경로)로 실행.

    \b
    Example:
        sts rl paper                          # 기본 (asym_long_strict profile)
        sts rl paper --model mppo_best        # 특정 모델
        sts rl paper --strategy rl_mppo       # 기존 기본 프로필로 실행
        sts rl paper --no-daemon              # 단일 세션
        sts rl paper --symbol A05603          # 종목 지정 (mini 월물 코드)
    """
    import asyncio

    click.echo("RL Paper Trading")
    click.echo(f"  Model: {model}")
    click.echo(f"  Config: {config}")
    click.echo(f"  Strategy: {strategy}")
    if symbol:
        click.echo(f"  Symbol: {symbol}")
    click.echo(f"  Mode: {'single session' if no_daemon else 'daemon'}")

    try:
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator

        # Allow model override for rl_mppo strategy when running via orchestrator.
        if model.endswith(".zip") or "/" in model:
            model_path = model
        else:
            model_path = f"models/futures/rl/{model}/best_model.zip"
        os.environ["RL_MPPO_MODEL_PATH"] = model_path

        # Orchestrator path: do NOT read paper.symbol from YAML.
        # Default symbol must be auto-detected mini front-month.
        symbols = [symbol] if symbol else None

        trading_config = TradingConfig.futures(
            strategy_name=strategy,
            symbols=symbols,
        )
        trading_config.paper_trading = True
        orchestrator = TradingOrchestrator(trading_config)

        async def _run():
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
                if no_daemon:
                    await orchestrator.run_session()
                else:
                    await orchestrator.run()
            finally:
                if not shutdown_requested:
                    await orchestrator.stop()

        try:
            asyncio.run(_run())
        except KeyboardInterrupt:
            pass  # Signal handler already initiated shutdown
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
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


@rl.command("retrain")
@click.option(
    "--config",
    "-c",
    default="ml/retraining_pipeline.yaml",
    show_default=True,
    help="Pipeline config file path",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Evaluate only without promotion (testing mode)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Skip threshold validation and force promotion",
)
def rl_retrain(config: str, dry_run: bool, force: bool):
    """RL 모델 자동 재학습 및 champion/challenger 평가

    \b
    Workflow:
        1. Load champion model from MLflow Production stage
        2. Train challenger model on latest ClickHouse data
        3. Evaluate both models on held-out test set
        4. Promote challenger if it meets performance thresholds
        5. Log full audit trail to MLflow

    \b
    Examples:
        sts rl retrain
        sts rl retrain --dry-run
        sts rl retrain --force --config ml/retraining_pipeline.yaml
    """
    click.echo("Starting RL Retraining Pipeline")
    click.echo(f"  Config: {config}")
    click.echo(f"  Dry Run: {dry_run}")
    click.echo(f"  Force Promotion: {force}")
    click.echo("-" * 60)

    try:
        from shared.ml.rl.retraining_pipeline import RetrainingPipeline

        # Initialize pipeline
        pipeline = RetrainingPipeline(config_path=config)

        # Run full retraining workflow
        click.echo("\n[1/5] Loading champion model...")
        click.echo("[2/5] Training challenger model...")
        click.echo("[3/5] Evaluating models on test data...")
        click.echo("[4/5] Comparing performance and checking thresholds...")

        # Run pipeline with dry-run and force options
        result = pipeline.run(dry_run=dry_run, force_promotion=force)

        # Display results
        click.echo("\n" + "=" * 60)
        click.echo("Retraining Pipeline Results")
        click.echo("=" * 60)

        if result.get("status") == "success":
            click.echo("✅ Status: SUCCESS")

            # Champion metrics
            if "champion_metrics" in result:
                champ = result["champion_metrics"]
                click.echo(
                    f"\n📊 Champion Model (v{result.get('champion_version', 'N/A')})"
                )
                click.echo(f"   Sharpe Ratio: {champ.get('sharpe', 0):.3f}")
                click.echo(f"   Win Rate: {champ.get('win_rate', 0) * 100:.1f}%")
                click.echo(f"   Max Drawdown: {champ.get('max_dd', 0) * 100:.1f}%")

            # Challenger metrics
            if "challenger_metrics" in result:
                chal = result["challenger_metrics"]
                click.echo(
                    f"\n🆕 Challenger Model (v{result.get('challenger_version', 'N/A')})"
                )
                click.echo(f"   Sharpe Ratio: {chal.get('sharpe', 0):.3f}")
                click.echo(f"   Win Rate: {chal.get('win_rate', 0) * 100:.1f}%")
                click.echo(f"   Max Drawdown: {chal.get('max_dd', 0) * 100:.1f}%")

            # Promotion decision
            promoted = result.get("promoted", False)
            if dry_run:
                click.echo("\n🔍 Dry Run Mode: No promotion performed")
                if result.get("should_promote", False):
                    click.echo("   ✓ Would promote: Thresholds met")
                else:
                    click.echo(
                        f"   ✗ Would NOT promote: {result.get('promotion_reason', 'Unknown')}"
                    )
            elif promoted:
                click.echo("\n🎉 Model Promoted to Production!")
                click.echo(f"   Version: {result.get('challenger_version', 'N/A')}")
                click.echo(f"   Reason: {result.get('promotion_reason', 'Thresholds met')}")
            else:
                click.echo("\n⚠️  Model NOT Promoted")
                click.echo(f"   Reason: {result.get('promotion_reason', 'Thresholds not met')}")

            # MLflow info
            if "mlflow_run_id" in result:
                click.echo(f"\n📝 MLflow Run ID: {result['mlflow_run_id']}")

        else:
            click.echo("❌ Status: FAILED")
            click.echo(f"   Error: {result.get('error', 'Unknown error')}")
            sys.exit(1)

        click.echo("=" * 60)

    except KeyboardInterrupt:
        click.echo("\n\nRetraining interrupted by user")
        sys.exit(130)
    except Exception as e:
        click.echo(f"\n❌ Error: {e}", err=True)
        import traceback

        traceback.print_exc()
        sys.exit(1)


@rl.command("train-hierarchical")
@click.option(
    "--mode",
    "-m",
    default="directional",
    type=click.Choice(["directional", "risk_budget"]),
    help="High-level agent mode (default: directional)",
)
@click.option(
    "--training",
    "-t",
    default="sequential",
    type=click.Choice(["sequential", "joint"]),
    help="Training mode (default: sequential)",
)
@click.option(
    "--config",
    "-c",
    default="ml/rl_mppo.yaml",
    help="Config file path (default: ml/rl_mppo.yaml)",
)
def rl_train_hierarchical(mode: str, training: str, config: str):
    """계층적 RL 모델 학습 (Multi-timeframe)

    고수준 에이전트(15분봉)가 전략적 방향을 설정하고,
    저수준 에이전트(1분봉)가 정밀한 진입/청산을 실행.

    \b
    Modes:
        directional:  High-level outputs LONG_BIAS/SHORT_BIAS/FLAT
        risk_budget:  High-level outputs AGGRESSIVE/NEUTRAL/DEFENSIVE

    \b
    Training:
        sequential:   Low-level 완전 학습 후 High-level 학습
        joint:        High/Low-level 동시 학습, 교대 업데이트

    \b
    Examples:
        sts rl train-hierarchical
        sts rl train-hierarchical --mode directional --training sequential
        sts rl train-hierarchical --mode risk_budget --training joint
        sts rl train-hierarchical --config ml/rl_mppo.yaml
    """
    click.echo("Starting Hierarchical RL Training")
    click.echo(f"  Mode: {mode}")
    click.echo(f"  Training: {training}")
    click.echo(f"  Config: {config}")
    click.echo("-" * 40)

    try:
        from scripts.training.train_rl import load_data_from_clickhouse
        from shared.ml.rl.hierarchical.trainer import HierarchicalTrainer

        # Load data from ClickHouse
        click.echo("Loading data from ClickHouse...")
        train_days, train_prices, test_days, test_prices = load_data_from_clickhouse(
            config,
            persist_scaler=True,
        )
        click.echo(f"  Train days: {len(train_days)}")
        click.echo(f"  Test days: {len(test_days)}")

        # Create hierarchical trainer
        trainer = HierarchicalTrainer(config_path=config, mode=mode)

        # Train based on selected mode
        if training == "sequential":
            click.echo("\n=== Sequential Training ===")
            _ = trainer.train(
                train_days=train_days,
                train_prices=train_prices,
                eval_days=test_days,
                eval_prices=test_prices,
            )
            click.echo("\nSequential training complete!")
            click.echo(f"  Low-level model: {trainer.save_dir}/low_level_final")
            click.echo(f"  High-level model: {trainer.save_dir}/high_level_final")
        else:  # joint
            click.echo("\n=== Joint Training ===")
            _ = trainer.train_joint(
                train_days=train_days,
                train_prices=train_prices,
                eval_days=test_days,
                eval_prices=test_prices,
            )
            click.echo("\nJoint training complete!")
            click.echo(f"  Low-level model: {trainer.save_dir}/low_level_joint")
            click.echo(f"  High-level model: {trainer.save_dir}/high_level_joint")

        click.echo("\n✓ Hierarchical training finished successfully")

    except ImportError as e:
        click.echo(f"Error: Required package not installed: {e}", err=True)
        click.echo("Install with: pip install -e .[ml]", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


@rl.command("evaluate-hierarchical")
@click.option(
    "--high-model",
    "-H",
    default="hierarchical/high_level_final",
    help="High-level model path (default: hierarchical/high_level_final)",
)
@click.option(
    "--low-model",
    "-l",
    default="hierarchical/low_level_final",
    help="Low-level model path (default: hierarchical/low_level_final)",
)
@click.option(
    "--baseline",
    "-b",
    default="mppo_best",
    help="Baseline flat rl_mppo model path (default: mppo_best)",
)
@click.option(
    "--mode",
    "-m",
    default="directional",
    type=click.Choice(["directional", "risk_budget"]),
    help="High-level agent mode (default: directional)",
)
@click.option(
    "--config",
    "-c",
    default="ml/rl_mppo.yaml",
    help="Config file path (default: ml/rl_mppo.yaml)",
)
def rl_evaluate_hierarchical(
    high_model: str, low_model: str, baseline: str, mode: str, config: str
):
    """계층적 RL 모델 평가 및 비교

    계층적 모델(High-level + Low-level)을 flat rl_mppo 베이스라인과 비교.
    Sharpe ratio, 수익률, 승률, MDD 등 주요 지표 비교표 출력.

    \b
    Examples:
        sts rl evaluate-hierarchical
        sts rl evaluate-hierarchical --mode directional
        sts rl evaluate-hierarchical --high-model hierarchical/high_level_joint --low-model hierarchical/low_level_joint
        sts rl evaluate-hierarchical --baseline mppo_best --mode risk_budget
    """
    from pathlib import Path

    click.echo("Starting Hierarchical RL Evaluation")
    click.echo(f"  High-level model: {high_model}")
    click.echo(f"  Low-level model: {low_model}")
    click.echo(f"  Baseline model: {baseline}")
    click.echo(f"  Mode: {mode}")
    click.echo(f"  Config: {config}")
    click.echo("-" * 40)

    try:
        from scripts.training.train_rl import load_data_from_clickhouse
        from shared.ml.rl.hierarchical.evaluator import HierarchicalEvaluator
        from stable_baselines3 import PPO
        from sb3_contrib import MaskablePPO

        # Load test data from ClickHouse
        click.echo("\nLoading test data from ClickHouse...")
        _, _, test_days, test_prices = load_data_from_clickhouse(config)
        click.echo(f"  Test days: {len(test_days)}")

        # Load models
        click.echo("\nLoading models...")

        # High-level model (PPO)
        high_model_path = Path(f"models/futures/rl/{high_model}")
        if not high_model_path.exists():
            click.echo(f"Error: High-level model not found at {high_model_path}", err=True)
            sys.exit(1)
        high_model_zip = high_model_path / "best_model.zip"
        if not high_model_zip.exists():
            high_model_zip = high_model_path.with_suffix(".zip")
        click.echo(f"  Loading high-level model from {high_model_zip}")
        high_model_obj = PPO.load(str(high_model_zip))

        # Low-level model (MaskablePPO)
        low_model_path = Path(f"models/futures/rl/{low_model}")
        if not low_model_path.exists():
            click.echo(f"Error: Low-level model not found at {low_model_path}", err=True)
            sys.exit(1)
        low_model_zip = low_model_path / "best_model.zip"
        if not low_model_zip.exists():
            low_model_zip = low_model_path.with_suffix(".zip")
        click.echo(f"  Loading low-level model from {low_model_zip}")
        low_model_obj = MaskablePPO.load(str(low_model_zip))

        # Baseline model (MaskablePPO)
        baseline_path = Path(f"models/futures/rl/{baseline}")
        if not baseline_path.exists():
            click.echo(f"Error: Baseline model not found at {baseline_path}", err=True)
            sys.exit(1)
        baseline_zip = baseline_path / "best_model.zip"
        if not baseline_zip.exists():
            baseline_zip = baseline_path.with_suffix(".zip")
        click.echo(f"  Loading baseline model from {baseline_zip}")
        baseline_model_obj = MaskablePPO.load(str(baseline_zip))

        # Create evaluator and run comparison
        click.echo("\nRunning evaluation and comparison...")
        evaluator = HierarchicalEvaluator(config_path=config)

        comparison_df = evaluator.compare_with_baseline(
            high_model=high_model_obj,
            low_model=low_model_obj,
            baseline_model=baseline_model_obj,
            test_days_1m=test_days,
            test_prices_1m=test_prices,
            test_days_15m=None,  # Auto-generated from 1m data
            mode=mode,
        )

        # Print comparison table
        click.echo("\n" + "=" * 80)
        click.echo("HIERARCHICAL RL vs BASELINE COMPARISON")
        click.echo("=" * 80)
        click.echo(comparison_df.to_string(index=False))
        click.echo("=" * 80)

        # Highlight key improvements
        improvement_row = comparison_df[comparison_df["model"] == "Improvement (%)"]
        if not improvement_row.empty:
            sharpe_improvement = improvement_row["sharpe_ratio"].iloc[0]
            total_return_improvement = improvement_row["total_return_pct"].iloc[0]

            click.echo("\nKey Findings:")
            click.echo(f"  Sharpe Ratio Improvement: {sharpe_improvement:+.2f}%")
            click.echo(f"  Total Return Improvement: {total_return_improvement:+.2f}%")

            if sharpe_improvement > 0:
                click.echo("\n✓ Hierarchical RL shows improved risk-adjusted returns!")
            else:
                click.echo("\n⚠ Hierarchical RL did not outperform baseline on Sharpe ratio")

        click.echo("\n✓ Evaluation complete!")

    except ImportError as e:
        click.echo(f"Error: Required package not installed: {e}", err=True)
        click.echo("Install with: pip install -e .[ml]", err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        import traceback

        traceback.print_exc()
        sys.exit(1)


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

        _ = trainer.train(
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
