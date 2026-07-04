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
from datetime import timedelta

import click

from cli.commands import backfill as backfill_commands
from cli.commands import common as common_commands
from cli.commands import health as health_commands
from cli.commands import paper as paper_commands
from cli.commands import stock_backfill as stock_backfill_commands
from cli.commands import trading_control as trading_control_commands
from cli.commands.data import data_cmd
from cli.commands.portfolio import portfolio_cmd

_require_parquet_sink = backfill_commands._require_parquet_sink
backfill = backfill_commands.backfill
backfill_run = backfill_commands.backfill_run
backfill_status = backfill_commands.backfill_status
backfill_today = backfill_commands.backfill_today

DEFAULT_DASHBOARD_HOST_PORT = common_commands.DEFAULT_DASHBOARD_HOST_PORT
DEFAULT_DASHBOARD_URL = common_commands.DEFAULT_DASHBOARD_URL

health = health_commands.health

paper = paper_commands.paper
paper_history = paper_commands.paper_history
paper_start = paper_commands.paper_start
paper_status = paper_commands.paper_status
paper_stop = paper_commands.paper_stop

stock_backfill = stock_backfill_commands.stock_backfill
stock_backfill_daily = stock_backfill_commands.stock_backfill_daily
stock_backfill_daily_status = stock_backfill_commands.stock_backfill_daily_status
stock_backfill_ensure_coverage = stock_backfill_commands.stock_backfill_ensure_coverage
stock_backfill_refresh = stock_backfill_commands.stock_backfill_refresh
stock_backfill_run = stock_backfill_commands.stock_backfill_run
stock_backfill_status = stock_backfill_commands.stock_backfill_status
stock_backfill_today = stock_backfill_commands.stock_backfill_today
stock_backfill_universe = stock_backfill_commands.stock_backfill_universe

_futures_orchestrator_blocked = trading_control_commands._futures_orchestrator_blocked
_futures_orchestrator_enabled = trading_control_commands._futures_orchestrator_enabled
_stock_orchestrator_blocked = trading_control_commands._stock_orchestrator_blocked
_stock_orchestrator_enabled = trading_control_commands._stock_orchestrator_enabled
trade = trading_control_commands.trade
trade_start = trading_control_commands.trade_start
trade_status = trading_control_commands.trade_status
trade_stop = trading_control_commands.trade_stop

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


@cli.group()
def experiment():
    """전략 실험(백테스트) — 현재 운용 전략을 수집 데이터로 비교 실행

    \b
    Examples:
        sts experiment run --spec config/experiments/stock_default.yaml
    """
    pass


@experiment.command("run")
@click.option("--spec", "-s", required=True, help="Experiment spec YAML 경로")
@click.option("--start", default=None, help="시작일 오버라이드 (YYYY-MM-DD)")
@click.option("--end", default=None, help="종료일 오버라이드 (YYYY-MM-DD)")
@click.option(
    "--output-dir", default="reports/stock_experiment", help="리포트 출력 디렉토리"
)
def experiment_run(spec: str, start: str | None, end: str | None, output_dir: str):
    """전략 실험을 실행하고 통합 리포트 JSON을 기록한다."""
    import yaml

    from shared.backtest.experiment_runner import (
        ExperimentSpec,
        run_stock_experiment,
        write_experiment_report,
    )

    with open(spec, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if start:
        data["start"] = start
    if end:
        data["end"] = end

    exp_spec = ExperimentSpec.from_dict(data)
    click.echo(
        f"Running experiment '{exp_spec.id}' — "
        f"{len(exp_spec.strategies)} strategies × {len(exp_spec.symbols)} symbols"
    )
    report = run_stock_experiment(exp_spec)

    for s in report["summaries"]:
        click.echo(
            f"  {s['strategy_id']:<22} "
            f"ret {s['total_return_pct']:+7.2f}%  "
            f"Sharpe {s['sharpe_ratio']:+5.2f}  "
            f"MDD {s['max_drawdown_pct']:5.2f}%  "
            f"trades {s['closed_trades']:>3}  win {s['win_rate_pct']:.0f}%"
        )
    for st in report["status_by_strategy"]:
        if st["status"] != "ok":
            click.echo(f"  [{st['status']}] {st['strategy_id']}: {st['error']}")

    path = write_experiment_report(report, output_dir)
    click.echo(f"\nReport written: {path}")


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


cli.add_command(data_cmd)


# =============================================================================
# Track A Core Portfolio (manual ledger — record/display only, no orders)
# =============================================================================


cli.add_command(portfolio_cmd)


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


cli.add_command(backfill)
cli.add_command(stock_backfill)


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


cli.add_command(trade)
cli.add_command(paper)
cli.add_command(health)


# =============================================================================
# Entry Point
# =============================================================================


def main():
    """CLI 진입점"""
    cli()


if __name__ == "__main__":
    main()
