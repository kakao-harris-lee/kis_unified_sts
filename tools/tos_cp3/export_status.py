#!/usr/bin/env python3
"""상태판 한 장을 ``/tos`` 가 읽는 JSON 으로 — 지금 괜찮은가, 무엇이 막혔나.

계획 ``docs/plans/2026-11-25-tos-operator-page-legibility-plan.md`` §4 ① «상태 띠»:
페이지 맨 위가 한 줄로 답해야 하는 질문 — 다섯 tenant 가 돌았나, 확인·막힘이 몇 건
있나, 깨끗한 날이 목표의 몇 날인가, 상주 paper 세션이 살아 있나.

**한 줄도 새로 세지 않는다.** 판정은 ``tools/tos_cp3/status_board.py::build_board``
(`sts tos status --json` 이 그대로 찍는 것)가 이미 내린다. 이 모듈이 더하는 것은 그
문서에서 **화면이 읽을 것만 고르고**, 호스트 경로와 digest 를 떼고, 대시보드가 읽는
디렉터리에 원자적으로 쓰는 것뿐이다. 세는 규칙을 여기서 다시 쓰면 `sts tos status`
와 화면이 다른 수를 말하게 된다.

**호스트 측이다.** ``export_bars`` · ``export_symbols`` 와 같은 네 가지 벽 —
대시보드 컨테이너는 ``tools/`` 를 담지 않고, 0700 상태 디렉터리를 mount 하지 않으며,
방화벽(TOS-FW-R)상 커널을 import 할 수 없고, 그 virtualenv 에 ``tos_runtime`` 이
없다. 경계는 **파일**이다.

**무엇을 떼는가.** 이 문서는 대시보드가 그대로 브라우저에 보내고, 그 페이지는
Cloudflare Access 뒤에서 인터넷에 열려 있다. 그래서 상태판 JSON 이 가진 것 중

* ``state_dir`` · ``clean_streak[].calendar`` — **호스트 경로**,
* ``expected_code_digest`` · ``band_digest`` · ``repo_commit`` · ``bootproof``
  한 줄 — 릴리스 digest 와 커밋,
* ``producer``/``store`` 의 내부 계수 블록과 ``cron`` 줄 — 화면이 그리지 않는 것,

은 **싣지 않는다**. boot proof 는 통째로 빼는 대신 «OK 였나» 한 불값으로 줄인다
(:func:`_boot_ok`) — 운영자가 봐야 하는 것은 그 문장이 아니라 그 판정이다.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.tos_cp3 import export_bars, status_board  # noqa: E402

__all__ = [
    "DOCUMENT_NAME",
    "ExportRefusal",
    "STATUS_SCHEMA_VERSION",
    "STATUS_SUBDIR",
    "build_document",
    "default_out_dir",
    "document_path",
    "export_status",
    "main",
]

#: ``export_bars`` 가 정한 목적지 규약을 그대로 쓴다 — 같은 ``$TOS_OPERATOR_DIR``
#: 아래 자기 하위 디렉터리 하나. 세 내보내기가 서로의 문서를 건드리지 않는다.
STATUS_SUBDIR = "status"

#: 파일 이름은 고정이다. 호출자가 고르는 경로 조각이 없으므로 route 에 traversal
#: 표면이 아예 생기지 않는다. 어느 날짜의 판정인지는 문서 안의 ``date`` 가 말한다.
DOCUMENT_NAME = "board.json"

STATUS_SCHEMA_VERSION = 1

ExportRefusal = export_bars.ExportRefusal

#: boot proof 한 줄이 «OK» 였음을 나타내는 토큰 — 상태판이 쓰는 그 상수를 그대로.
BOOTPROOF_OK = status_board.BOOTPROOF_OK

#: 상주 paper 세션 보고서에서 화면이 읽는 것. 나머지(커밋 · 세부 분해)는 뺀다.
_PAPER_REPORT_KEYS = (
    "verdict",
    "exit_code",
    "stop_reason",
    "started_kst",
    "ended_kst",
    "events_consumed",
    "stale_withheld",
    "stale_ratio",
)


def default_out_dir() -> Path:
    """``export_bars`` 와 **같은** 목적지 규약 — 세 문서가 다른 mount 로 갈라지지 않게."""
    return export_bars.default_out_dir()


def document_path(out_dir: Path) -> Path:
    """문서가 놓일 자리."""
    return out_dir / STATUS_SUBDIR / DOCUMENT_NAME


def _boot_ok(bootproof: Any) -> bool | None:
    """boot proof 한 줄의 판정만 — 문장은 커밋 revision 을 담으므로 싣지 않는다.

    줄이 없으면 ``None`` 이다. ``False`` 는 «줄은 있는데 OK 가 아니다» 이고, 그
    둘을 같게 그리면 «아직 안 떴다» 와 «뜨다 실패했다» 가 한 칸이 된다.
    """
    if not isinstance(bootproof, str) or not bootproof:
        return None
    return BOOTPROOF_OK in bootproof


def _tenant_row(session: Any) -> dict[str, Any]:
    """한 tenant 세션 — 화면이 그리는 것만. digest · 커밋 · 계수 블록은 뺀다."""
    store = session.get("store") or {}
    return {
        "name": session.get("name"),
        "label": session.get("label"),
        "tree_id": session.get("tree_id"),
        "market": session.get("market"),
        "direction": session.get("direction"),
        "instrument": session.get("instrument"),
        "status": session.get("status"),
        "run_alive": session.get("run_alive"),
        "producer_alive": session.get("producer_alive"),
        "boot_at": status_board._hhmmss(session.get("boot_at")),
        "end_at": status_board._hhmmss(session.get("end_at")),
        "run_rc": session.get("run_rc"),
        "producer_rc": session.get("producer_rc"),
        "ticks": store.get("ticks") if isinstance(store, dict) else None,
        "issues": list(session.get("issues") or []),
    }


def _streak_row(streak: Any) -> dict[str, Any]:
    """깨끗한 날 누적 한 트리 — ``calendar`` 는 호스트 경로라 빼고 판 이름만 남긴다."""
    return {
        "label": streak.get("label"),
        "days": streak.get("days"),
        "target_days": streak.get("target_days"),
        "window_days": streak.get("window_days"),
        "met": streak.get("met"),
        "start": streak.get("start"),
        "window_start": streak.get("window_start"),
        "pending": streak.get("pending"),
        "broke_on": streak.get("broke_on"),
        "broke_reason": streak.get("broke_reason"),
        "calendar_version": streak.get("calendar_version"),
        "error": streak.get("error"),
    }


def _paper_block(paper: Any) -> dict[str, Any]:
    """상주 paper 세션 — 살아 있나, 어떻게 끝났나, 그리고 그 자신의 이슈."""
    report = paper.get("report")
    return {
        "session": paper.get("session"),
        "live_check": paper.get("live_check"),
        "runtime_alive": paper.get("runtime_alive"),
        "driver_alive": paper.get("driver_alive"),
        "boot_ok": _boot_ok(paper.get("bootproof")),
        "report": (
            None
            if not isinstance(report, dict)
            else {key: report.get(key) for key in _PAPER_REPORT_KEYS}
        ),
        "issues": [
            {"level": level, "text": text} for level, text in paper.get("issues") or []
        ],
    }


def build_document(board: dict[str, Any]) -> dict[str, Any]:
    """상태판 JSON 에서 화면이 읽을 것만. ``board`` 는 ``build_board`` 의 반환값이다.

    순수 함수다 — 디스크도 시계도 보지 않는다. 그래서 테스트가 녹화된 상태판
    하나로 «무엇이 실리고 무엇이 떨어지는가» 를 통째로 고정할 수 있다.
    """
    issues = [dict(issue) for issue in board.get("issues") or []]
    return {
        "schema_version": STATUS_SCHEMA_VERSION,
        "date": board.get("date"),
        "generated_kst": board.get("generated_kst"),
        "tenants": [_tenant_row(s) for s in board.get("tenant_sessions") or []],
        "clean_streak": [_streak_row(t) for t in board.get("clean_streak") or []],
        "paper": _paper_block(board.get("paper") or {}),
        "issues": issues,
        # 상태판의 판정과 같은 수. 화면의 띠가 이 둘만 보고 색을 고를 수 있게 미리
        # 센다 — 페이지가 레벨 문자열을 다시 세다가 상태판과 어긋나지 않도록.
        "blocked": sum(1 for i in issues if i.get("level") == status_board.BLOCK),
        "checks": sum(1 for i in issues if i.get("level") == status_board.WARN),
        "levels": {"blocked": status_board.BLOCK, "check": status_board.WARN},
    }


def export_status(
    *,
    config_path: Path = status_board.DEFAULT_CONFIG_PATH,
    out_dir: Path | None = None,
    state_dir: str | None = None,
    date: str | None = None,
    proc_root: Path = Path("/proc"),
) -> Path:
    """상태판을 읽어 문서를 쓰고, 어디에 놓였는지 돌려준다."""
    destination_root = default_out_dir() if out_dir is None else out_dir
    cfg = status_board.load_config(config_path)
    if state_dir is not None:
        cfg = status_board.BoardConfig(
            **{**cfg.__dict__, "state_dir": status_board.expand_path(state_dir)}
        )
    today = status_board.today_kst()
    day = _dt.date.fromisoformat(date) if date else today
    board = status_board.build_board(cfg, day=day, today=today, proc_root=proc_root)
    document = build_document(board)
    path = document_path(destination_root)
    try:
        export_bars._write_atomically(
            path, json.dumps(document, ensure_ascii=False, sort_keys=True) + "\n"
        )
    except OSError as exc:
        raise ExportRefusal(f"{path}: 상태판 문서를 쓰지 못했다: {exc}") from exc
    return path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tools.tos_cp3.export_status",
        description=(
            "한 장 상태판(tenant 세션 상태 · 이슈 · 깨끗한 날 누적 · 상주 paper)을, "
            "대시보드가 읽기 전용으로 bind-mount 한 디렉터리에 JSON 으로 내보낸다."
        ),
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help=f"대상 루트 (기본: ${export_bars.PROJECTION_DIR_ENV})",
    )
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (기본: 오늘 KST)")
    parser.add_argument("--state-dir", default=None)
    parser.add_argument("--config", type=Path, default=status_board.DEFAULT_CONFIG_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """상태판 문서를 내보낸다. 성공 ``0``, 거부 ``2``.

    상태판 자신의 «막힘이 있으면 1» 종료 코드는 **옮기지 않는다** — 이 명령의 일은
    내보내기이고, 막힘 여부는 문서 안의 ``blocked`` 가 말한다. 러너의 훅이 이 rc 를
    세션 rc 와 섞지 않게 하는 것도 같은 이유다.
    """
    args = _parser().parse_args(argv)
    try:
        path = export_status(
            config_path=args.config,
            out_dir=None if args.out_dir is None else Path(args.out_dir),
            state_dir=args.state_dir,
            date=args.date,
        )
    except (ExportRefusal, ValueError, OSError) as exc:
        print(f"export-status refused: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
