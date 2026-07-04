"""Trading control CLI commands."""

from __future__ import annotations

import logging
import os
import sys
from contextlib import suppress

import click

from cli.commands.common import DEFAULT_DASHBOARD_URL

# =============================================================================
# Trading Commands
# =============================================================================


@click.group()
def trade():
    """트레이딩 제어 명령

    \b
    Examples:
        sts trade start --strategy bb_reversion --asset stock
        sts trade stop
        sts trade status
    """
    pass


def _stock_orchestrator_enabled() -> bool:
    """The monolithic orchestrator runs stock only when explicitly enabled.

    Default ``True`` (pre-cutover behaviour). The operator sets
    ``STOCK_ORCHESTRATOR_ENABLED=false`` as the final M5d cutover step so the
    orchestrator permanently refuses stock — the decoupled M4 pipeline owns it.
    Rollback: set it back to ``true`` (``1``/``yes`` also accepted). Any other
    value (e.g. ``false``/``0``/``no``) keeps stock blocked.
    """
    return os.getenv("STOCK_ORCHESTRATOR_ENABLED", "true").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _stock_orchestrator_blocked(asset: str) -> bool:
    """True when the orchestrator must refuse this asset (stock + flag disabled)."""
    return asset == "stock" and not _stock_orchestrator_enabled()


def _futures_orchestrator_enabled() -> bool:
    """The monolithic orchestrator runs futures only when explicitly enabled.

    Default ``True`` (the orchestrator IS today's futures path). The operator
    sets ``FUTURES_ORCHESTRATOR_ENABLED=false`` at the futures cutover so the
    orchestrator refuses futures — the decoupled chain (decision_engine →
    risk_filter → order_router) owns it, preventing double-trading on the same
    account. Rollback: set it back to ``true`` (``1``/``yes`` also accepted).
    """
    return os.getenv("FUTURES_ORCHESTRATOR_ENABLED", "true").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _futures_orchestrator_blocked(asset: str) -> bool:
    """True when the orchestrator must refuse this asset (futures + flag disabled)."""
    return asset == "futures" and not _futures_orchestrator_enabled()


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
    if _stock_orchestrator_blocked(asset):
        click.echo(
            "Error: the monolithic orchestrator no longer runs stock — stock trades "
            "via the compose stock-pipeline/stock-ingest services.",
            err=True,
        )
        click.echo(
            "  Rollback to the orchestrator stock path: set "
            "STOCK_ORCHESTRATOR_ENABLED=true.",
            err=True,
        )
        sys.exit(1)

    if _futures_orchestrator_blocked(asset):
        click.echo(
            "Error: the monolithic orchestrator no longer runs futures — futures "
            "trades via the decoupled chain (decision_engine → risk_filter → "
            "order_router).",
            err=True,
        )
        click.echo(
            "  Rollback to the orchestrator futures path: set "
            "FUTURES_ORCHESTRATOR_ENABLED=true.",
            err=True,
        )
        sys.exit(1)

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
    default=DEFAULT_DASHBOARD_URL,
    help="Dashboard API URL",
)
def trade_status(url: str):
    """트레이딩 상태 조회

    \b
    Example:
        sts trade status
        sts trade status --url http://localhost:5081
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
    default=DEFAULT_DASHBOARD_URL,
    help="Dashboard API URL",
)
def trade_stop(url: str):
    """트레이딩 종료

    \b
    Example:
        sts trade stop
        sts trade stop --url http://localhost:5081
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
