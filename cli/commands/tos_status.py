"""`sts tos` — TOS 운영 조회 명령(읽기 전용).

본체는 ``tools/tos_cp3/status_board.py`` 다. 여기는 click 래퍼뿐이다 — 상태판 로직은
CP-3 도구(``session_inputs``)를 재사용하므로 그 옆에 둔다.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

_REPO_ROOT = Path(__file__).resolve().parents[2]


@click.group("tos")
def tos_cmd() -> None:
    """TOS 운영 조회(읽기 전용).

    \b
    Examples:
        sts tos status
        sts tos status --date 2026-10-22
        sts tos status --json
    """


@tos_cmd.command("status")
@click.option("--date", "date", default=None, help="YYYY-MM-DD (기본: 오늘 KST)")
@click.option(
    "--state-dir",
    default=None,
    help="상태 루트 (기본: config/tos_status_board.yaml 의 state_dir)",
)
@click.option(
    "--config",
    "config_path",
    default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="상태판 설정 YAML (기본: config/tos_status_board.yaml)",
)
@click.option("--json", "as_json", is_flag=True, help="JSON 으로 출력")
def tos_status(
    date: str | None, state_dir: str | None, config_path: Path | None, as_json: bool
) -> None:
    """한 장 상태판 — 오늘 무엇이 돌았고 무엇이 막혔나.

    CP-3 tenant 세션(부팅·종료·digest, 틱·보류 사유, VENUE_BAND_OBSERVED, B3 대조,
    생산자 지연)과 상주 paper 세션을 상태 디렉터리에서 읽기만 해서 보여 준다.
    막힘이 하나라도 있으면 종료코드 1.
    """
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    from tools.tos_cp3 import status_board

    text, code = status_board.run(
        config_path=config_path or status_board.DEFAULT_CONFIG_PATH,
        state_dir=state_dir,
        date=date,
        as_json=as_json,
    )
    click.echo(text, nl=False)
    sys.exit(code)
