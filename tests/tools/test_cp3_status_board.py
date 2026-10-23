"""`sts tos status` — TOS 한 장 상태판, 녹화 픽스처로만(실 상태 디렉터리 읽지 않음).

픽스처: ``tests/tools/fixtures/cp3_status_board`` (README 참조). 매 테스트가 ``tmp_path`` 에 상태
루트를 펼치고 SQL 덤프로 sqlite 저장소를 다시 만든다. 프로세스 생존은 가짜 ``/proc`` 로 준다.
"""

from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import shutil
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest
from click.testing import CliRunner

from tools.tos_cp3 import status_board as sb

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "cp3_status_board"
LEAVES = {
    "long-A05611": "cp3-setup-d-long-data/A05611",
    "short-A05611": "cp3-setup-d-short-data/A05611",
}
D1015, D1022, D1023 = (
    dt.date(2026, 10, 15),
    dt.date(2026, 10, 22),
    dt.date(2026, 10, 23),
)


def _materialize(tmp_path: Path) -> Path:
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
    return state


def _fake_proc(tmp_path: Path, state: Path, *, alive: bool = True) -> Path:
    proc = tmp_path / "proc"
    proc.mkdir()
    if not alive:
        return proc
    for name in ("long-20261023", "short-20261023"):
        runner = sb.parse_runner_log(
            (state / "cp3-sessions" / name / "session.log").read_text()
        )
        for pid in (runner.run_pid, runner.producer_pid):
            (proc / str(pid)).mkdir()
            (proc / str(pid) / "cmdline").write_bytes(
                b"timeout\x0026036s\x00python\x00--config-dir\x00"
                + str(state / "cp3-sessions" / name / "config").encode()
            )
    for pid, cmd in (
        (424201, b"python\x00-c\x00from tos_runtime.compose.cli import main"),
        (424202, b"python\x00/x/tos_paper_session.py"),
    ):
        (proc / str(pid)).mkdir()
        (proc / str(pid) / "cmdline").write_bytes(cmd)
    return proc


@pytest.fixture
def state(tmp_path: Path) -> Path:
    return _materialize(tmp_path)


@pytest.fixture
def cfg(state: Path) -> sb.BoardConfig:
    return replace(sb.load_config(), state_dir=state)


def _board(
    cfg: sb.BoardConfig,
    day: dt.date,
    *,
    today: dt.date | None = None,
    proc: Path | None = None,
):
    return sb.build_board(
        cfg,
        day=day,
        today=today or dt.date(2026, 12, 31),
        proc_root=proc or Path("/nonexistent"),
    )


def _session(board: dict, name: str) -> dict:
    return next(s for s in board["tenant_sessions"] if s["name"] == name)


def _issues(board: dict, level: str | None = None) -> list[str]:
    return [
        f"{i['where']}: {i['text']}"
        for i in board["issues"]
        if level is None or i["level"] == level
    ]


# --- config -----------------------------------------------------------------


def test_committed_config_loads_with_the_operator_threshold():
    cfg = sb.load_config()
    assert cfg.stale_refusal_ratio_max == 0.005  # #931 운영자 지시
    assert cfg.latency_percentiles == (50, 90)
    assert cfg.tenant_sessions_subdir == "cp3-sessions"


def test_config_missing_key_is_refused(tmp_path: Path):
    path = tmp_path / "c.yaml"
    path.write_text("state_dir: /x\n")
    with pytest.raises(ValueError, match="키가 없다"):
        sb.load_config(path)


# --- pure helpers -------------------------------------------------------------


def test_percentile_is_nearest_rank():
    assert sb.percentile([], 50) is None
    assert sb.percentile([5, 1, 3, 2, 4], 50) == 3
    assert sb.percentile(list(range(1, 11)), 90) == 9
    assert sb.percentile([7], 90) == 7


def test_bar_close_is_bar_start_plus_one_minute_in_kst():
    close = sb.bar_close_ms("A05611:1m:20261022T084500+0900")
    assert close == int(
        dt.datetime(2026, 10, 22, 8, 46, tzinfo=sb.KST).timestamp() * 1000
    )
    assert sb.bar_close_ms("garbage") is None


def test_pid_alive_requires_the_needle_in_cmdline(tmp_path: Path):
    (tmp_path / "7").mkdir()
    (tmp_path / "7" / "cmdline").write_bytes(b"python\x00/a/session-x")
    assert sb.pid_alive(7, "/a/session-x", proc_root=tmp_path)
    assert not sb.pid_alive(7, "/a/session-y", proc_root=tmp_path)  # pid 재사용
    assert not sb.pid_alive(8, "/a/session-x", proc_root=tmp_path)
    assert not sb.pid_alive(None, "x", proc_root=tmp_path)


# --- runner log ------------------------------------------------------------------


def test_runner_log_of_a_clean_full_day(state: Path):
    r = sb.parse_runner_log(
        (state / "cp3-sessions/long-20261022/session.log").read_text()
    )
    assert (r.boot_at, r.stop_at, r.end_at) == (
        "2026-10-22 08:46:18",
        "2026-10-22 15:50:00",
        "2026-10-22 15:50:01",
    )
    assert (r.run_rc, r.producer_rc, r.aborts) == (0, 0, [])
    assert r.tree_id == "cp3-setup-d-long" and r.direction == "LONG"
    assert r.activation == "ACTIVATED 5 (re-derived in a fresh process)"
    assert (
        r.repo_commit == r.source_revision == "b15069fd1737962d92766e73648b0c2128957d32"
    )
    assert r.band_declared is True and r.band_line_ok
    assert r.data_leaf == str(state / LEAVES["long-A05611"])


def test_runner_log_abort_and_band_off(state: Path):
    abort = sb.parse_runner_log(
        (state / "cp3-sessions/long-20261015/session.log").read_text()
    )
    assert (
        len(abort.aborts) == 1
        and "producer stopped before the session did" in abort.aborts[0]
    )
    short = sb.parse_runner_log(
        (state / "cp3-sessions/short-20261023/session.log").read_text()
    )
    assert short.band_declared is False  # SHORT 트리는 band 를 끈다
    assert short.end_at is None and short.run_pid is not None


# --- the board ----------------------------------------------------------------------


def test_ended_day_reads_the_scoped_store(cfg: sb.BoardConfig):
    board = _board(cfg, D1022)
    s = _session(board, "long-20261022")
    assert s["status"] == "ENDED"
    st = s["store"]
    # 잎에는 10-15·10-22·10-23 이 누적돼 있다 — 10-22 만 센다.
    assert st["ticks"] == 6
    assert st["outcomes"] == {"NO_ACTION": 1, "NO_OUTCOME": 2, "PROPOSAL": 3}
    assert st["withheld_by_reason"] == {"DECISION_WITHHELD/TIME_NOT_ADMITTED": 2}
    assert st["flow_halts"] == {"STAGE_DENIED": 3}
    # 08:45 봉은 pre-boot(부팅 스냅샷) — post-boot stale 은 15:12 한 건뿐
    assert st["post_boot_consumed_ids"] == 5
    assert st["m5_present_value_refused_as_unknown"] == 1
    assert st["stale_withheld_post_boot"] == 1
    assert st["other_withheld_post_boot"] == []
    assert st["code_digests"] == [s["expected_code_digest"]]
    assert st["band_observed"] == []
    p = s["producer"]
    assert p["journal_rows"] == 20
    assert p["latency_ms"]["n"] == 20
    assert p["counters"]["published"] == 410


def test_stale_ratio_over_the_limit_blocks_an_ended_session(cfg: sb.BoardConfig):
    board = _board(cfg, D1022)
    blocks = _issues(board, sb.BLOCK)
    assert blocks == ["long-20261022: stale 거절(M5 ①) 1/5 = 20.000% > 0.5%"]
    warns = _issues(board, sb.WARN)
    assert "long-20261022: B3 대조 미실행(b3/report/summary.json 없음)" in warns
    assert any("VENUE_BAND_OBSERVED 행 없음" in w for w in warns)


def test_stale_ratio_within_the_limit_is_quiet(cfg: sb.BoardConfig):
    board = _board(replace(cfg, stale_refusal_ratio_max=0.5), D1022)
    assert _issues(board, sb.BLOCK) == []


def test_running_day_with_live_processes(
    tmp_path: Path, state: Path, cfg: sb.BoardConfig
):
    proc = _fake_proc(tmp_path, state)
    board = _board(cfg, D1023, today=D1023, proc=proc)
    long, short = _session(board, "long-20261023"), _session(board, "short-20261023")
    assert long["status"] == short["status"] == "RUNNING"
    assert long["run_alive"] and long["producer_alive"]
    # band: LONG 은 행이 있고, SHORT 는 band 를 끈 트리라 경고하지 않는다
    assert [b["outcome"] for b in long["store"]["band_observed"]] == ["OBSERVED"]
    assert long["store"]["band_observed"][0]["trading_date"] == "20261023"
    assert short["store"]["band_observed"] == []
    issues = _issues(board)
    assert not any("VENUE_BAND_OBSERVED" in i for i in issues)
    # 진행 중 stale 초과는 확인으로만
    assert all(i["level"] == sb.WARN for i in board["issues"])
    assert any("진행 중 — 판정은 종료 뒤" in i for i in issues)
    paper = board["paper"]
    assert paper["session"] == "2026-10-23-084506-LONG"
    assert paper["runtime_alive"] and paper["driver_alive"] and paper["report"] is None
    assert paper["issues"] == []
    # 10 일 이력에 네 세션이 다 있다
    assert [(h["day"], h["label"]) for h in board["history"]] == [
        ("20261015", "long"),
        ("20261022", "long"),
        ("20261023", "long"),
        ("20261023", "short"),
    ]


def test_running_day_whose_processes_are_gone_is_blocked(
    tmp_path: Path, state: Path, cfg: sb.BoardConfig
):
    proc = _fake_proc(tmp_path, state, alive=False)
    board = _board(cfg, D1023, today=D1023, proc=proc)
    assert _session(board, "long-20261023")["status"] == "LOST"
    blocks = _issues(board, sb.BLOCK)
    assert any("END 기록 없이 사라졌다" in b for b in blocks)
    assert "paper: report.json 없이 상주 런타임/드라이버가 멈춰 있다" in blocks


def test_past_day_does_not_look_at_pids(
    tmp_path: Path, state: Path, cfg: sb.BoardConfig
):
    proc = _fake_proc(tmp_path, state)
    board = _board(cfg, D1023, today=dt.date(2026, 10, 24), proc=proc)
    assert _session(board, "long-20261023")["status"] == "LOST"
    assert board["paper"]["live_check"] is False
    assert (
        "paper: 지난 날짜인데 report.json 이 없다(세션이 정상 종료되지 않음)"
        in _issues(board, sb.BLOCK)
    )


def test_abort_day_with_b3(cfg: sb.BoardConfig):
    board = _board(cfg, D1015)
    s = _session(board, "long-20261015")
    assert s["status"] == "ABORT"
    assert s["b3"] == {
        "unresolved": 0,
        "compared_bars": 303,
        "identical": 277,
        "divergent": 26,
        "window": "2026-10-08..2026-10-15",
    }
    assert any("ABORT: the producer stopped" in b for b in _issues(board, sb.BLOCK))
    assert board["paper"]["session"] is None
    assert "paper: 2026-10-15 상주 paper 세션 디렉터리 없음" in _issues(board, sb.WARN)


def test_b3_unresolved_blocks(state: Path, cfg: sb.BoardConfig):
    path = state / "cp3-sessions/long-20261015/b3/report/summary.json"
    data = json.loads(path.read_text())
    data["unresolved"]["count"] = 3
    path.write_text(json.dumps(data))
    assert "long-20261015: B3 unresolved=3" in _issues(_board(cfg, D1015), sb.BLOCK)


def test_code_digest_mismatch_blocks(state: Path, cfg: sb.BoardConfig):
    (state / "cp3-sessions/long-20261022/config/release.yaml").write_text(
        'expected_code_digest: "' + "ab" * 32 + '"\n'
    )
    blocks = _issues(_board(cfg, D1022), sb.BLOCK)
    assert any("≠ release.yaml abababababab" in b for b in blocks)


def _append_field_refused(
    state: Path, reasons: dict[str, list[str]], age_ms: int
) -> None:
    """런타임 ``scheduler._record_field_refusals`` 의 행 모양 그대로(#931)."""
    db = state / LEAVES["long-A05611"] / "evidence.sqlite3"
    conn = sqlite3.connect(db)
    seq = conn.execute("SELECT max(seq) FROM entries").fetchone()[0] + 1
    payload = {
        "instrument": "A05611",
        "raw_event_id": "A05611:1m:20261022T151200+0900",
        "as_of_ms": 1,
        "evaluated_at_ms": 1 + age_ms,
        "age_ms": age_ms,
        "stale_max_age_ms": [800],
        "fields_declared": 15,
        "fields_refused": 15,
        "refused_by_reason": reasons,
    }
    conn.execute(
        "INSERT INTO entries (seq, segment_id, kind, record_class, runtime_identity_json, payload_json,"
        " entry_digest, chain_digest, key_generation, appended_at_monotonic_ns)"
        " VALUES (?, NULL, ?, ?, NULL, ?, 'x', 'x', 0, 0)",
        (
            seq,
            sb.FIELD_REFUSED_KIND,
            sb.FIELD_REFUSED_KIND,
            json.dumps({"masked_keys": [], "payload": payload}),
        ),
    )
    conn.commit()
    conn.close()


def test_field_refused_stale_rows_are_counted_not_blocked(
    state: Path, cfg: sb.BoardConfig
):
    _append_field_refused(state, {"stale": ["close_x100", "vwap_x100"]}, 922)
    board = _board(replace(cfg, stale_refusal_ratio_max=0.5), D1022)
    st = _session(board, "long-20261022")["store"]
    assert (
        st["field_refused_rows"],
        st["field_refused_by_reason"],
        st["field_refused_max_age_ms"],
    ) == (
        1,
        {"stale": 1},
        922,
    )
    assert _issues(board, sb.BLOCK) == []


def test_field_refused_for_a_non_stale_reason_blocks(state: Path, cfg: sb.BoardConfig):
    _append_field_refused(state, {"absent_from_payload": ["close_x100"]}, 100)
    blocks = _issues(_board(replace(cfg, stale_refusal_ratio_max=0.5), D1022), sb.BLOCK)
    assert blocks == [
        "long-20261022: stale 이 아닌 필드 거절: A05611:1m:20261022T151200+0900 absent_from_payload"
    ]


def test_a_store_of_another_shape_is_reported_not_crashed(
    state: Path, cfg: sb.BoardConfig
):
    conn = sqlite3.connect(state / LEAVES["long-A05611"] / "evidence.sqlite3")
    conn.execute("PRAGMA user_version=99")
    conn.close()
    board = _board(cfg, D1022)
    assert "error" in _session(board, "long-20261022")["store"]
    assert any(
        "런타임 저장소 읽기 거부" in b and "user_version=99" in b
        for b in _issues(board, sb.BLOCK)
    )
    assert "저장소: 읽기 거부" in sb.render_text(board)


def test_no_tenant_session_on_the_day_is_flagged(cfg: sb.BoardConfig):
    board = _board(cfg, dt.date(2026, 10, 21))
    assert board["tenant_sessions"] == []
    assert "tenant: 2026-10-21 CP-3 tenant 세션 디렉터리 없음" in _issues(
        board, sb.WARN
    )


def _tree_digest(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_the_board_writes_nothing(tmp_path: Path, state: Path, cfg: sb.BoardConfig):
    proc = _fake_proc(tmp_path, state)
    before = _tree_digest(state)
    for day in (D1015, D1022, D1023):
        sb.render_text(_board(cfg, day, today=D1023, proc=proc))
    assert _tree_digest(state) == before


def test_text_rendering_carries_every_section(
    tmp_path: Path, state: Path, cfg: sb.BoardConfig
):
    proc = _fake_proc(tmp_path, state)
    text = sb.render_text(_board(cfg, D1023, today=D1023, proc=proc))
    for needle in (
        "■ CP-3 tenant 세션",
        "long-20261023  LONG A05611  [RUNNING]",
        "code_digest 1552b215f1ed = release.yaml",
        "VENUE_BAND_OBSERVED OBSERVED 20261023",
        "VENUE_BAND_OBSERVED 0행 (이 트리는 band 를 끔)",
        "지연(as_of−분마감) p50",
        "B3 대조: 미실행",
        "■ 상주 paper",
        "■ 최근 세션(날짜별)",
        "■ 막힌 것 / 확인할 것",
    ):
        assert needle in text, needle
    assert "0000000000" not in text  # 계좌 좌표는 출력하지 않는다


# --- the sts command ---------------------------------------------------------------


def test_sts_tos_status_exit_code_and_json(state: Path):
    from cli.main import cli

    runner = CliRunner()
    blocked = runner.invoke(
        cli, ["tos", "status", "--state-dir", str(state), "--date", "2026-10-15"]
    )
    assert blocked.exit_code == 1, blocked.output
    assert "판정: 막힘 있음" in blocked.output
    as_json = runner.invoke(
        cli,
        ["tos", "status", "--state-dir", str(state), "--date", "2026-10-15", "--json"],
    )
    doc = json.loads(as_json.output)
    assert doc["date"] == "2026-10-15"
    assert doc["tenant_sessions"][0]["b3"]["divergent"] == 26
