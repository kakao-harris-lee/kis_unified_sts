"""`sts tos` — TOS 운영 조회 명령(읽기 전용).

본체는 ``tools/tos_cp3/`` 다. 여기는 click 래퍼뿐이다 — 상태판 로직은 CP-3 도구
(``session_inputs``)를 재사용하므로 그 옆에 둔다.

* ``status`` → ``tools/tos_cp3/status_board.py``
* ``inspect`` → ``tools/tos_cp3/inspect_session.py`` (로드맵
  ``docs/plans/2026-11-11-tos-platform-roadmap.md`` §P1). 그 모듈은 방화벽
  (TOS-FW-R)상 ``tos`` 를 import 할 수 없으므로 평가 본체
  ``tos/runtime/cp3/inspect_session.py`` 를 별 프로세스로 돌린다.
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
        sts tos inspect stock-r1-20261110 --from 09:00 --to 10:00
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


@tos_cmd.command("inspect")
@click.argument("session")
@click.option("--from", "window_from", default=None, help="KST HH:MM (포함)")
@click.option("--to", "window_to", default=None, help="KST HH:MM (포함)")
@click.option(
    "--data-dir",
    default=None,
    help="tenant durable-set 잎 (기본: 렌더 매니페스트에서 도출)",
)
@click.option(
    "--evidence/--no-evidence",
    "with_evidence",
    default=True,
    help="--no-evidence 는 규칙만 본다 — durable set 을 열지 않는다",
)
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
def tos_inspect(
    session: str,
    window_from: str | None,
    window_to: str | None,
    data_dir: str | None,
    with_evidence: bool,
    state_dir: str | None,
    config_path: Path | None,
    as_json: bool,
) -> None:
    """바마다 «왜 이 결정이었나» — 기록된 CP-3 세션의 읽기 전용 점검.

    세션의 producer journal 과 그날 쓴 렌더 트리를 읽어, 바마다 필드값 · 규칙별
    비교식별 통과/실패 · 첫 일치 결정을 내고, tenant durable set 의 증거
    (결정 결과 · 정지 단계와 사유)를 옆에 붙인다. 끝에 규칙별·비교식별로 그
    비교가 거짓이었던 바의 비율을 적는다 — «어느 비교식이 R1 을 몇 % 막았나».

    \b
    Examples:
        sts tos inspect stock-r1-20261110
        sts tos inspect stock-r1-20261110 --from 09:00 --to 10:00
        sts tos inspect stock-r1-20261110 --json
    """
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    from tools.tos_cp3 import inspect_session, status_board

    text, code = inspect_session.run(
        session=session,
        config_path=config_path or status_board.DEFAULT_CONFIG_PATH,
        state_dir=state_dir,
        data_dir=data_dir,
        window_from=window_from,
        window_to=window_to,
        as_json=as_json,
        with_evidence=with_evidence,
    )
    click.echo(text, nl=False)
    sys.exit(code)
