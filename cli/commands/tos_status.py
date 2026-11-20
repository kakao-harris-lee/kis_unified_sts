"""`sts tos` — TOS 운영 조회 명령(읽기 전용).

본체는 ``tools/tos_cp3/`` 다. 여기는 click 래퍼뿐이다 — 상태판 로직은 CP-3 도구
(``session_inputs``)를 재사용하므로 그 옆에 둔다.

* ``status`` → ``tools/tos_cp3/status_board.py``
* ``inspect`` → ``tools/tos_cp3/inspect_session.py`` (로드맵
  ``docs/plans/2026-11-11-tos-platform-roadmap.md`` §P1). 그 모듈은 방화벽
  (TOS-FW-R)상 ``tos`` 를 import 할 수 없으므로 평가 본체
  ``tos/runtime/cp3/inspect_session.py`` 를 별 프로세스로 돌린다.
* ``export-bars`` → ``tools/tos_cp3/export_bars.py``. 같은 점검을 ``--json`` 으로
  받아 대시보드가 이미 읽기 전용으로 bind-mount 한 디렉터리에 원자적으로 쓴다
  (§P1 둘째 항목의 호스트 측). 컨테이너는 그 파일을 **경로로만** 연다.
* ``perf`` → ``tools/tos_cp3/perf.py`` (활용 계획
  ``docs/plans/2026-11-19-tos-usage-plan.md`` §5 «`sts tos perf` 최소판»).
  tenant 잎 evidence 만 읽어 종목·날짜별 체결 수 · 손익 · 승 · 보유 수량을 센다.
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
        sts tos perf
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

    CP-3 tenant 세션(부팅·종료·digest, 틱·보류 사유, VENUE_BAND_OBSERVED,
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

    outcome = inspect_session.run(
        session=session,
        config_path=config_path or status_board.DEFAULT_CONFIG_PATH,
        state_dir=state_dir,
        data_dir=data_dir,
        window_from=window_from,
        window_to=window_to,
        as_json=as_json,
        with_evidence=with_evidence,
    )
    # The two streams stay apart so `--json | jq` gets a document or nothing,
    # never a document with a diagnostic appended (review of #1057, LOW-2).
    click.echo(outcome.stdout, nl=False)
    click.echo(outcome.stderr, nl=False, err=True)
    sys.exit(outcome.exit_code)


@tos_cmd.command("perf")
@click.option(
    "--leaf",
    "leaves",
    multiple=True,
    help="읽을 tenant durable-set 잎(반복 가능) — 보관된 잎은 이 방법으로만 읽는다",
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
def tos_perf(
    leaves: tuple[str, ...],
    state_dir: str | None,
    config_path: Path | None,
    as_json: bool,
) -> None:
    """종목·날짜별 체결과 손익 — tenant 잎 evidence 만 읽는다.

    종목(= tenant)마다, 거래일마다 체결된 진입·청산 수 · 왕복 수 · 승 수 · 남은
    보유 수량 · 손익을 센다. 손익은 FILL_OBSERVED 의 avg_execution_price —
    브로커의 평균 체결가(원 단위) — 기준이고, 그 키가 없는 체결은 SEND_SEALED 가
    봉인한 주문 지정가로 떨어진다. 어느 기준이 쓰였는지는 출력이 먼저 말한다
    (표의 «*» · JSON 의 pnl_basis). 가격은 지어내지 않는다. 손익은 수수료·세금 전이고,
    왕복·승은 FIFO 로 닫힌 lot 조각마다 센다 — 출력의 «집계 규칙» 문단이 같은 말을 한다.
    집계에 들어가지 않은 체결(부분 체결 · 엔진이 쥐지 않은 브로커 체결 · 취소 보류)은
    «집계 밖» 에 관측된 그대로 나온다.

    \b
    Examples:
        sts tos perf
        sts tos perf --json
        sts tos perf --leaf ~/.local/state/tos/cp3-setup-d-stock-005930-data/archive/005930.stuck-close-20261119
    """
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    from tools.tos_cp3 import perf, status_board

    text, code = perf.run(
        config_path=config_path or status_board.DEFAULT_CONFIG_PATH,
        state_dir=state_dir,
        leaf_paths=tuple(leaves),
        as_json=as_json,
    )
    click.echo(text, nl=False)
    sys.exit(code)


@tos_cmd.command("export-bars")
@click.argument("session")
@click.option(
    "--out-dir",
    default=None,
    help="대상 루트 (기본: $TOS_OPERATOR_PROJECTION_DIR — 컨테이너가 읽는 그 디렉터리)",
)
@click.option("--data-dir", default=None, help="tenant durable-set 잎")
@click.option(
    "--state-dir",
    default=None,
    help="상태 루트 (기본: config/tos_status_board.yaml 의 state_dir)",
)
def tos_export_bars(
    session: str, out_dir: str | None, data_dir: str | None, state_dir: str | None
) -> None:
    """기록된 세션의 바별 점검을 대시보드가 읽는 JSON 으로 내보낸다.

    `sts tos inspect --json` 과 같은 문서를 `<dir>/bars/<session>.json` 에
    원자적으로(tmp + rename) 쓴다. 대시보드 컨테이너는 그 파일을 경로로만 열고
    `tos`/`tos_runtime` 를 import 하지 않는다 — 컨테이너가 커널 코드도, 0700 상태
    디렉터리도 볼 수 없기 때문이다(export_bars 모듈 docstring 의 네 가지 벽).

    \b
    Examples:
        sts tos export-bars stock-r1-20261110
        sts tos export-bars stock-r1-20261110 --out-dir /tmp/dry-run
    """
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    from tools.tos_cp3 import export_bars

    sys.exit(
        export_bars.main(
            [
                session,
                *(["--out-dir", out_dir] if out_dir else []),
                *(["--data-dir", data_dir] if data_dir else []),
                *(["--state-dir", state_dir] if state_dir else []),
            ]
        )
    )
