"""CLI 메인 진입점

Usage:
    sts --help
    sts tos status

레거시 명령(`backtest` · `optimize` · `mlflow` · `collect` · `scan` · `data` ·
`health` · `paper` · `portfolio` · `backfill` · `stock-backfill`)은 레거시 제거
계획 L3(`docs/plans/2026-11-07-legacy-removal-plan.md`)에서 그 구현과 함께
지워졌다. 남은 것은 TOS 한 장 상태판뿐이다.
"""

from __future__ import annotations

import logging

import click

from cli.commands.tos_status import tos_cmd

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

    \b
    Commands:
        tos         TOS 한 장 상태판 (읽기 전용)
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


cli.add_command(tos_cmd)


def main():
    """CLI 엔트리포인트"""
    cli()


if __name__ == "__main__":
    main()
