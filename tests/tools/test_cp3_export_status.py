"""``tools/tos_cp3/export_status.py`` — 상태 띠의 호스트 측 내보내기.

계획 ``docs/plans/2026-11-25-tos-operator-page-legibility-plan.md`` §4 ① «상태 띠».

입력은 ``test_cp3_status_board`` 와 **같은 녹화 픽스처**다. 상태판이 실제로 내는
문서에서 무엇이 실리고 무엇이 떨어지는지를 고정하는 것이 이 파일의 일이므로,
판정 자체를 흉내 낸 손 문서로 보면 아무 것도 증명하지 못한다. 실 상태 디렉터리
(``~/.local/state/tos``)는 읽지 않는다.
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
import shutil
import sqlite3
import stat
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from tools.tos_cp3 import export_bars
from tools.tos_cp3 import export_status as ex
from tools.tos_cp3 import status_board as sb

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "cp3_status_board"
LEAVES = {
    "long-A05611": "cp3-setup-d-long-data/A05611",
    "short-A05611": "cp3-setup-d-short-data/A05611",
}
PAPER_LEAF = "paper-data/A05611"
D1022, D1023 = dt.date(2026, 10, 22), dt.date(2026, 10, 23)

EVIDENCE_COLUMNS_SQL = (
    "CREATE TABLE entries (seq INTEGER PRIMARY KEY, segment_id TEXT, kind TEXT NOT NULL,"
    " record_class TEXT NOT NULL, runtime_identity_json TEXT, payload_json TEXT NOT NULL,"
    " entry_digest TEXT NOT NULL, chain_digest TEXT NOT NULL,"
    " key_generation INTEGER NOT NULL, appended_at_monotonic_ns INTEGER NOT NULL)"
)


def _materialize(tmp_path: Path) -> Path:
    """``test_cp3_status_board`` 와 같은 전개 — 같은 녹화를 두 번 만들지 않는다."""
    state = tmp_path / "state"
    shutil.copytree(FIXTURE / "state", state)
    for path in state.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            if "{STATE_DIR}" in text:
                path.write_text(
                    text.replace("{STATE_DIR}", str(state)), encoding="utf-8"
                )
    for name, leaf in LEAVES.items():
        dest = state / leaf
        dest.mkdir(parents=True)
        for store in ("evidence", "inbox", "marketfeed"):
            sql = gzip.decompress(
                (FIXTURE / "stores" / name / f"{store}.sql.gz").read_bytes()
            )
            conn = sqlite3.connect(dest / f"{store}.sqlite3")
            conn.executescript(sql.decode("utf-8"))
            conn.commit()
            conn.close()
    paper = state / PAPER_LEAF
    paper.mkdir(parents=True)
    conn = sqlite3.connect(paper / "evidence.sqlite3")
    conn.execute(EVIDENCE_COLUMNS_SQL)
    conn.execute(f"PRAGMA user_version = {sb.si.PINNED_EVIDENCE_SCHEMA_VERSION}")
    conn.commit()
    conn.close()
    return state


@pytest.fixture
def state(tmp_path: Path) -> Path:
    return _materialize(tmp_path)


@pytest.fixture
def cfg(state: Path) -> sb.BoardConfig:
    return replace(sb.load_config(), state_dir=state)


@pytest.fixture
def board(cfg: sb.BoardConfig) -> dict[str, Any]:
    return sb.build_board(
        cfg, day=D1022, today=dt.date(2026, 12, 31), proc_root=Path("/nonexistent")
    )


def test_the_document_says_what_ran_and_how_it_ended(board: dict[str, Any]) -> None:
    """tenant 줄은 상태판이 판정한 상태·rc·틱 그대로다 — 여기서 다시 세지 않는다."""
    document = ex.build_document(board)
    assert document["schema_version"] == ex.STATUS_SCHEMA_VERSION
    assert document["date"] == "2026-10-22"

    names = [tenant["name"] for tenant in document["tenants"]]
    assert names == [session["name"] for session in board["tenant_sessions"]]
    long_row = next(t for t in document["tenants"] if t["name"] == "long-20261022")
    recorded = next(s for s in board["tenant_sessions"] if s["name"] == "long-20261022")
    assert long_row["status"] == recorded["status"]
    assert long_row["run_rc"] == recorded["run_rc"]
    assert long_row["market"] == recorded["market"]
    assert long_row["direction"] == recorded["direction"]
    assert long_row["instrument"] == recorded["instrument"]
    assert long_row["ticks"] == (recorded["store"] or {}).get("ticks")
    assert long_row["boot_at"] == "08:46:18"


def test_a_session_that_never_booted_reports_null_not_the_clis_dash() -> None:
    """뜨지 못한 세션의 시각은 ``null`` 이다 — «—» 는 화면이 그릴 글자다.

    ``status_board._hhmmss`` 는 표 렌더러라 없는 값을 «—» 로 적는다. 그 글자가
    문서에 실리면 페이지가 그것을 시각 **문자열**로 받고, `boot_at == null` 을
    보는 분기는 영영 서지 않는다. 세션이 뜨지 못한 날 — 운영자가 가장 봐야 하는
    날 — 이 정확히 이 경우다(계획 §7: 「없음을 '이상 없음'으로 그리지 않는다」).
    """
    row = ex._tenant_row(
        {
            "name": "stock-r1-20261125",
            "status": "NOT-BOOTED",
            "boot_at": None,
            "end_at": None,
            "store": None,
            "issues": None,
        }
    )
    assert row["boot_at"] is None
    assert row["end_at"] is None
    assert row["ticks"] is None
    assert row["issues"] == []
    assert row["status"] == "NOT-BOOTED"
    # …and a stamp that IS there still becomes the clock the board renders.
    assert ex._clock("2026-11-25 08:46:08") == "08:46:08"


def test_the_issue_list_is_the_boards_own_with_its_levels(
    board: dict[str, Any],
) -> None:
    """판정은 상태판의 것이다 — 레벨·문장·순서를 글자 그대로 옮긴다."""
    document = ex.build_document(board)
    assert document["issues"] == board["issues"]
    assert document["levels"] == {"blocked": sb.BLOCK, "check": sb.WARN}
    assert document["blocked"] == sum(
        1 for issue in board["issues"] if issue["level"] == sb.BLOCK
    )
    assert document["checks"] == sum(
        1 for issue in board["issues"] if issue["level"] == sb.WARN
    )
    # 두 수의 합이 목록 길이다 — 레벨이 셋이 되는 날 조용히 어긋나지 않게.
    assert document["blocked"] + document["checks"] == len(document["issues"])


def test_the_clean_day_count_keeps_its_target_and_loses_its_calendar_path(
    board: dict[str, Any],
) -> None:
    """누적은 목표와 함께 간다. 달력 **경로**는 호스트 경로이므로 판 이름만 남긴다."""
    streak = ex.build_document(board)["clean_streak"][0]
    recorded = board["clean_streak"][0]
    assert streak["days"] == recorded["days"]
    assert streak["target_days"] == recorded["target_days"]
    assert streak["met"] == recorded["met"]
    assert streak["calendar_version"] == recorded["calendar_version"]
    assert "calendar" not in streak


def test_the_boot_proof_becomes_a_verdict_not_a_line(board: dict[str, Any]) -> None:
    """boot proof 한 줄에는 커밋 revision 이 들어 있다 — 판정만 싣는다."""
    paper = ex.build_document(board)["paper"]
    assert paper["boot_ok"] is (sb.BOOTPROOF_OK in (board["paper"]["bootproof"] or ""))
    assert "bootproof" not in paper
    assert paper["session"] == board["paper"]["session"]
    assert paper["live_check"] == board["paper"]["live_check"]


def test_a_paper_session_with_no_boot_proof_is_unknown_not_false() -> None:
    """줄이 없는 것과 «OK 가 아니었다» 는 다른 사실이다."""
    assert ex._boot_ok(None) is None
    assert ex._boot_ok("") is None
    assert ex._boot_ok("boot proof: FAILED") is False
    assert ex._boot_ok("boot proof: OK · rev abcdef") is True


def test_the_paper_report_drops_the_worktree_commit(board: dict[str, Any]) -> None:
    """``worktree_commit`` 은 화면이 그리지 않는다 — 고르는 키 목록에 없다."""
    report = ex.build_document(board)["paper"]["report"]
    if report is not None:
        assert "worktree_commit" not in report
        assert set(report) == set(ex._PAPER_REPORT_KEYS)


def test_no_host_path_or_digest_reaches_the_document(
    board: dict[str, Any], state: Path
) -> None:
    """문서 전체에 상태 디렉터리 경로도, 릴리스 digest 도 한 번 나오지 않는다.

    ``/tos`` 는 Cloudflare Access 뒤에서 인터넷에 열려 있고 앱 자체 인증이 없다.
    상태판 JSON 은 둘 다 들고 있으므로, 고르기가 아니라 **지우기**로 짰다면 키
    하나가 늘어난 날 조용히 샌다.
    """
    rendered = json.dumps(ex.build_document(board), ensure_ascii=False)
    assert str(state) not in rendered
    assert "state_dir" not in rendered
    for session in board["tenant_sessions"]:
        for key in ("expected_code_digest", "band_digest", "repo_commit"):
            value = session.get(key)
            if isinstance(value, str) and value:
                assert value not in rendered, key


def test_the_document_lands_where_the_dashboard_reads_with_narrow_modes(
    cfg: sb.BoardConfig, tmp_path: Path
) -> None:
    """``export-bars`` 와 같은 목적지 규약 · 같은 권한으로 원자적으로 쓴다."""
    out = tmp_path / "projection"
    path = ex.export_status(
        out_dir=out,
        state_dir=str(cfg.state_dir),
        date="2026-10-22",
        proc_root=Path("/nonexistent-proc"),
    )
    assert path == out / ex.STATUS_SUBDIR / ex.DOCUMENT_NAME
    assert stat.S_IMODE(path.stat().st_mode) == export_bars.DOCUMENT_MODE
    assert stat.S_IMODE(path.parent.stat().st_mode) == export_bars.DIR_MODE
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["schema_version"] == ex.STATUS_SCHEMA_VERSION
    assert document["date"] == "2026-10-22"
    assert document["tenants"]


def test_what_the_exporter_writes_is_what_the_route_accepts(
    board: dict[str, Any],
) -> None:
    """두 쪽은 파일로만 만난다 — 그래서 그 파일이 저쪽 DTO 를 통과하는지 여기서 본다.

    이것이 없으면 내보내기 쪽 키 하나를 고쳐도 아무것도 빨개지지 않고, 화면만
    조용히 빈다.
    """
    from services.dashboard.routes.tos_status import TosStatusDocument

    document = TosStatusDocument.model_validate(ex.build_document(board))
    assert document.schema_version == ex.STATUS_SCHEMA_VERSION
    assert document.tenants is not None and document.tenants
    assert document.issues is not None
    assert document.clean_streak is not None
    assert document.paper is not None
    assert document.levels is not None and document.levels.blocked == sb.BLOCK


def test_the_exporters_exit_code_is_not_the_boards_verdict(
    cfg: sb.BoardConfig, tmp_path: Path
) -> None:
    """막힘이 있어도 rc 는 0 이다 — 세션 훅의 rc 와 판정이 섞이면 안 된다.

    ``sts tos status`` 는 막힘 하나에 1 로 끝난다. 그 규칙을 이리로 옮기면 러너
    로그의 «END STATUS EXPORT rc=1» 이 «쓰기 실패» 로 읽힌다.
    """
    rc = ex.main(
        [
            "--out-dir",
            str(tmp_path / "projection"),
            "--state-dir",
            str(cfg.state_dir),
            "--date",
            "2026-10-22",
        ]
    )
    assert rc == 0
    document = json.loads(
        (tmp_path / "projection" / ex.STATUS_SUBDIR / ex.DOCUMENT_NAME).read_text(
            encoding="utf-8"
        )
    )
    # 판정은 문서 안에 있다.
    assert isinstance(document["blocked"], int)


def test_an_unwritable_destination_is_a_refusal_with_rc_2(
    cfg: sb.BoardConfig, tmp_path: Path
) -> None:
    """목적지가 막히면 조용히 성공하지 않는다 — 화면이 어제 문서를 오늘로 읽는다."""
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    blocked.chmod(0o500)
    try:
        rc = ex.main(
            [
                "--out-dir",
                str(blocked / "projection"),
                "--state-dir",
                str(cfg.state_dir),
                "--date",
                "2026-10-22",
            ]
        )
    finally:
        blocked.chmod(0o700)
    assert rc == 2
