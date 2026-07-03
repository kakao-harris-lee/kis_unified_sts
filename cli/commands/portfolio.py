"""Track A core-portfolio manual-ledger CLI (Phase 5A).

``sts portfolio`` records and displays the MANUAL Track A core portfolio
(config/portfolio/core_holdings.yaml — design doc §2). Nothing here places
orders: ``record`` appends a pure bookkeeping row to the RuntimeLedger
(track_id="A"), ``value`` updates the manual-valuation sidecar, ``list``
renders holdings/candidates/sector weights. Holding registration and share
counts stay operator-edited YAML (the CLI never rewrites the main file, so
its comments — schema docs, theses — survive).
"""

from __future__ import annotations

import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

import click

KST = ZoneInfo("Asia/Seoul")


@click.group("portfolio")
def portfolio_cmd():
    """트랙 A 코어 포트폴리오 수동 원장 (기록·표시 전용 — 주문 없음).

    \b
    Examples:
        sts portfolio list
        sts portfolio value 012450 985000 --date 2026-07-02
        sts portfolio record buy 012450 10 985000
    """


def _load_core(config_path: str | None):
    from shared.portfolio.core_holdings import CoreHoldings

    return CoreHoldings.load_or_default(config_path)


def _today_kst() -> date:
    return datetime.now(KST).date()


def _won(value: float | None) -> str:
    return "-" if value is None else f"{value:,.0f}"


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@portfolio_cmd.command("list")
@click.option(
    "--config",
    "config_path",
    default=None,
    help="core_holdings.yaml 경로 오버라이드 (기본: config/portfolio/)",
)
def portfolio_list(config_path: str | None):
    """보유/후보 종목과 섹터 비중(실측 vs 목표)을 표시한다."""
    core = _load_core(config_path)

    click.echo("=== Track A 보유 종목 ===")
    if not core.holdings:
        click.echo("(없음 — config/portfolio/core_holdings.yaml에 등록)")
    else:
        header = (
            f"{'symbol':<10} {'name':<16} {'sector':<24} {'shares':>8}"
            f" {'avg_price':>12} {'val_date':>12} {'val_price':>12} {'value':>16}"
        )
        click.echo(header)
        for holding in core.holdings:
            valuation = holding.last_valuation
            click.echo(
                f"{holding.symbol:<10} {holding.name:<16} {holding.sector:<24}"
                f" {holding.shares:>8}"
                f" {_won(holding.avg_price):>12}"
                f" {valuation.date.isoformat() if valuation.date else '-':>12}"
                f" {_won(valuation.price):>12}"
                f" {_won(holding.value):>16}"
            )
    click.echo(f"현금 버퍼: {_won(core.cash_krw)} KRW")
    total = core.total_value()
    click.echo(f"총 평가액: {_won(total)} KRW")
    if core.holdings and total is None:
        click.echo(
            "(미평가 보유 종목 존재 — `sts portfolio value <symbol> <price>`로 갱신)"
        )

    click.echo("\n=== 섹터 비중 (실측 vs 목표) ===")
    weights = core.sector_weights()
    drift = core.rebalancing.drift_threshold_pct
    for key, spec in core.sectors.items():
        actual = weights.get(key)
        actual_text = "-" if actual is None else f"{actual:.1%}"
        flag = ""
        if actual is not None and abs(actual - spec.target_weight) > drift:
            flag = f"  ← ±{drift:.0%}p 이탈 (리밸런싱 검토)"
        click.echo(
            f"{spec.label:<12} ({key}): {actual_text:>7} / 목표"
            f" {spec.target_weight:.0%}{flag}"
        )

    click.echo("\n=== 후보 종목 ===")
    if not core.candidates:
        click.echo("(없음)")
    for candidate in core.candidates:
        click.echo(
            f"{candidate.symbol:<10} {candidate.name:<16} {candidate.sector:<24}"
            f" {candidate.thesis}"
        )


# ---------------------------------------------------------------------------
# value
# ---------------------------------------------------------------------------


@portfolio_cmd.command("value")
@click.argument("symbol")
@click.argument("price", type=float)
@click.option(
    "--date",
    "valuation_date",
    default=None,
    help="평가 기준일 (YYYY-MM-DD, 기본: 오늘 KST)",
)
@click.option(
    "--config",
    "config_path",
    default=None,
    help="core_holdings.yaml 경로 오버라이드 (기본: config/portfolio/)",
)
def portfolio_value(
    symbol: str, price: float, valuation_date: str | None, config_path: str | None
):
    """보유 종목의 수동 평가(last_valuation)를 갱신한다.

    core_holdings.yaml 본문은 재기록하지 않고 (주석 보존) 사이드카
    core_holdings_valuations.yaml에 기록한다 — 로더가 병합한다.
    """
    from shared.portfolio.core_holdings import (
        save_valuation,
        valuations_sidecar_path,
    )

    if price <= 0:
        click.echo("Error: price는 양수여야 합니다", err=True)
        sys.exit(1)
    day = date.fromisoformat(valuation_date) if valuation_date else _today_kst()

    core = _load_core(config_path)
    if symbol not in core.symbols():
        click.echo(
            f"Error: {symbol!r}은(는) 보유 종목이 아닙니다."
            " 먼저 config/portfolio/core_holdings.yaml holdings에 등록하세요.",
            err=True,
        )
        sys.exit(1)

    sidecar = valuations_sidecar_path(config_path)
    save_valuation(sidecar, symbol, price, day)
    click.echo(
        f"평가 갱신: {symbol} → {price:,.0f} KRW ({day.isoformat()})" f" [{sidecar}]"
    )


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------


@portfolio_cmd.command("record")
@click.argument("side", type=click.Choice(["buy", "sell"]))
@click.argument("symbol")
@click.argument("shares", type=int)
@click.argument("price", type=float)
@click.option(
    "--ledger-path",
    default=None,
    help="RuntimeLedger SQLite 경로 오버라이드 (기본: config/storage.yaml)",
)
@click.option(
    "--config",
    "config_path",
    default=None,
    help="core_holdings.yaml 경로 오버라이드 (기본: config/portfolio/)",
)
def portfolio_record(
    side: str,
    symbol: str,
    shares: int,
    price: float,
    ledger_path: str | None,
    config_path: str | None,
):
    """수동 체결을 RuntimeLedger에 기록한다 (track_id="A", 순수 기록).

    주문을 발행하지 않는다 — 이미 수동으로 체결한 매매의 장부 기록이다.
    보유 수량(shares)/평단(avg_price)은 operator가 core_holdings.yaml에서
    직접 갱신한다.
    """
    from shared.portfolio.config import TRACK_CORE
    from shared.storage import SQLiteRuntimeLedger
    from shared.storage.config import StorageConfig

    if shares <= 0 or price <= 0:
        click.echo("Error: shares/price는 양수여야 합니다", err=True)
        sys.exit(1)

    core = _load_core(config_path)
    known = core.sector_of(symbol)
    if known is None:
        click.echo(
            f"경고: {symbol!r}은(는) core_holdings.yaml에 없는 종목입니다"
            " (기록은 진행)",
            err=True,
        )

    now = datetime.now(KST).replace(tzinfo=None)
    trade: dict[str, object] = {
        "asset_class": "stock",
        "symbol": symbol,
        "side": side,
        "quantity": shares,
        "strategy": "track_a_manual",
        "exit_reason": "manual_core_portfolio",
    }
    if side == "buy":
        trade["entry_time"] = now.isoformat()
        trade["entry_price"] = price
    else:
        trade["exit_time"] = now.isoformat()
        trade["exit_price"] = price

    if ledger_path is None:
        ledger = SQLiteRuntimeLedger(
            StorageConfig.load_or_default().runtime_storage.sqlite
        )
    else:
        ledger = SQLiteRuntimeLedger(ledger_path)
    try:
        record_id = ledger.record_trade(trade, track_id=TRACK_CORE)
    finally:
        ledger.close()

    click.echo(
        f"원장 기록 완료: [{record_id}] track A {side} {symbol}"
        f" {shares}주 @ {price:,.0f} KRW"
    )
    click.echo("※ 순수 기록입니다 — 주문은 발행되지 않았습니다.")
    click.echo(
        "다음 단계: core_holdings.yaml의 shares/avg_price를 갱신하고"
        " `sts portfolio value`로 평가를 갱신하세요."
    )
