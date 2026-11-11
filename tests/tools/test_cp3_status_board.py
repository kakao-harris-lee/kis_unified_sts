"""`sts tos status` — TOS 한 장 상태판, 녹화 픽스처로만(실 상태 디렉터리 읽지 않음).

픽스처: ``tests/tools/fixtures/cp3_status_board`` (README 참조). 매 테스트가 ``tmp_path`` 에 상태
루트를 펼치고 SQL 덤프로 sqlite 저장소를 다시 만든다. 프로세스 생존은 가짜 ``/proc`` 로 준다.
"""

from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import re
import shutil
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest
from click.testing import CliRunner

from tools.tos_cp3 import session_day as sd
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
    _paper_leaf(state)
    return state


PAPER_LEAF = "paper-data/A05611"
EVIDENCE_COLUMNS_SQL = (
    "CREATE TABLE entries (seq INTEGER PRIMARY KEY, segment_id TEXT, kind TEXT NOT NULL,"
    " record_class TEXT NOT NULL, runtime_identity_json TEXT, payload_json TEXT NOT NULL,"
    " entry_digest TEXT NOT NULL, chain_digest TEXT NOT NULL,"
    " key_generation INTEGER NOT NULL, appended_at_monotonic_ns INTEGER NOT NULL)"
)


def _paper_leaf(state: Path) -> None:
    """상주 paper 잎의 빈 evidence 저장소(픽스처는 paper 잎을 담지 않는다 — 실 호스트엔 늘 있다)."""
    leaf = state / PAPER_LEAF
    leaf.mkdir(parents=True)
    conn = sqlite3.connect(leaf / "evidence.sqlite3")
    conn.execute(EVIDENCE_COLUMNS_SQL)
    conn.execute(f"PRAGMA user_version = {sb.si.PINNED_EVIDENCE_SCHEMA_VERSION}")
    conn.commit()
    conn.close()


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
    assert (cfg.paper_runtime_cmdline_needle, cfg.paper_driver_cmdline_needle) == (
        "tos_runtime",
        "tos_paper_session",
    )


def test_paper_liveness_needles_come_from_config(
    tmp_path: Path, state: Path, cfg: sb.BoardConfig
):
    proc = _fake_proc(tmp_path, state)
    other = replace(cfg, paper_runtime_cmdline_needle="not-in-any-cmdline")
    paper = _board(other, D1023, today=D1023, proc=proc)["paper"]
    assert paper["runtime_alive"] is False and paper["driver_alive"] is True


def test_config_missing_key_is_refused(tmp_path: Path):
    path = tmp_path / "c.yaml"
    path.write_text("state_dir: /x\n")
    with pytest.raises(ValueError, match="키가 없다"):
        sb.load_config(path)


@pytest.mark.parametrize(
    "key", ["paper_runtime_cmdline_needle", "paper_driver_cmdline_needle"]
)
@pytest.mark.parametrize("value", ['""', "'  '", "null"])
def test_config_blank_cmdline_needle_is_refused(tmp_path: Path, key: str, value: str):
    # 빈 needle 은 아무 프로세스나 «살아 있음» 으로 본다 — 로드에서 거부한다(#941).
    committed = sb.DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
    lines = [
        f"{key}: {value}" if line.startswith(f"{key}:") else line
        for line in committed.splitlines()
    ]
    path = tmp_path / "c.yaml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="빈 값은 허용하지 않는다"):
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
    assert (
        "long-20261022: B3 결과 없음(세션 디렉터리에 b3/report/summary.json 이 없다)"
        in warns
    )
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
        # v2 summary: it does not separate the declared families out of
        # `divergent`, and `None` says so rather than claiming zero.
        "declared": None,
        "excluded": None,
        "separates_declared": False,
        "window": "2026-10-08..2026-10-15",
    }
    assert any("ABORT: the producer stopped" in b for b in _issues(board, sb.BLOCK))
    assert board["paper"]["session"] is None
    assert "paper: 2026-10-15 상주 paper 세션 디렉터리 없음" in _issues(board, sb.WARN)


def test_b3_unresolved_is_a_check_not_a_block(state: Path, cfg: sb.BoardConfig):
    """2026-11-11 완화 §2 문장 1 — 수는 계속 올리지만 막지는 않는다."""
    path = state / "cp3-sessions/long-20261015/b3/report/summary.json"
    data = json.loads(path.read_text())
    data["unresolved"]["count"] = 3
    path.write_text(json.dumps(data))
    board = _board(cfg, D1015)
    assert "long-20261015: B3 unresolved=3" in _issues(board, sb.WARN)
    assert "long-20261015: B3 unresolved=3" not in _issues(board, sb.BLOCK)


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
        "런타임 저장소 상태 모름" in b and "user_version=99" in b
        for b in _issues(board, sb.BLOCK)
    )
    assert "저장소: 상태 모름" in sb.render_text(board)


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
        "B3 대조: 결과 없음",
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


# --- review-935 regressions ------------------------------------------------------


def _append_band_refused(state: Path, reason: str) -> int:
    """런타임 ``band_journal._refuse`` 의 행 모양 그대로 — trading_date 가 없다."""
    db = state / LEAVES["long-A05611"] / "evidence.sqlite3"
    conn = sqlite3.connect(db)
    seq = conn.execute("SELECT max(seq) FROM entries").fetchone()[0] + 1
    payload = {
        "outcome": "REFUSED",
        "instrument": "A05611",
        "reason": reason,
        "detail": "x",
    }
    conn.execute(
        "INSERT INTO entries (seq, segment_id, kind, record_class, runtime_identity_json,"
        " payload_json, entry_digest, chain_digest, key_generation, appended_at_monotonic_ns)"
        " VALUES (?, NULL, ?, ?, NULL, ?, 'x', 'x', 0, 0)",
        (
            seq,
            sb.BAND_OBSERVED_KIND,
            sb.BAND_OBSERVED_KIND,
            json.dumps({"masked_keys": [], "payload": payload}),
        ),
    )
    conn.commit()
    conn.close()
    return seq


def test_b1_band_refused_later_in_the_session_blocks(
    tmp_path: Path, state: Path, cfg: sb.BoardConfig
):
    seq = _append_band_refused(state, "journal_empty")
    proc = _fake_proc(tmp_path, state)
    board = _board(cfg, D1023, today=D1023, proc=proc)
    bands = _session(board, "long-20261023")["store"]["band_observed"]
    assert [(b["outcome"], b["reason"]) for b in bands] == [
        ("OBSERVED", None),
        ("REFUSED", "journal_empty"),
    ]
    assert (
        f"long-20261023: VENUE_BAND_OBSERVED REFUSED seq {seq} reason=journal_empty detail=x"
        in _issues(board, sb.BLOCK)
    )
    assert "VENUE_BAND_OBSERVED REFUSED reason=journal_empty" in sb.render_text(board)
    # 같은 잎의 지난 부팅 구간(10-22)에는 붙지 않는다
    assert _session(_board(cfg, D1022), "long-20261022")["store"]["band_observed"] == []


def test_b1_band_row_missing_from_the_boot_segment_warns(
    tmp_path: Path, state: Path, cfg: sb.BoardConfig
):
    conn = sqlite3.connect(state / LEAVES["long-A05611"] / "evidence.sqlite3")
    # 녹화 저장소는 런타임의 append-only 트리거를 그대로 갖고 있다 — tmp 사본에서만 걷어 낸다
    for (name,) in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'trigger'"
    ).fetchall():
        conn.execute(f'DROP TRIGGER "{name}"')
    conn.execute("DELETE FROM entries WHERE kind = ?", (sb.BAND_OBSERVED_KIND,))
    conn.commit()
    conn.close()
    board = _board(cfg, D1023, today=D1023, proc=_fake_proc(tmp_path, state))
    assert "long-20261023: band 를 선언한 트리인데 이 부팅 구간에 VENUE_BAND_OBSERVED 행 없음" in _issues(
        board, sb.WARN
    )


def test_b2_booted_session_without_a_data_leaf_line_is_unknown_not_pre_boot(
    state: Path, cfg: sb.BoardConfig
):
    log = state / "cp3-sessions/long-20261022/session.log"
    log.write_text(
        "\n".join(
            ln for ln in log.read_text().splitlines() if " · data leaf " not in ln
        )
        + "\n"
    )
    board = _board(cfg, D1022)
    blocks = _issues(board, sb.BLOCK)
    assert any(
        b.startswith("long-20261022: 런타임 저장소 상태 모름 — session.log 에")
        for b in blocks
    )
    text = sb.render_text(board)
    assert "부팅 전이라 읽지 않음" not in text
    assert "저장소: 상태 모름" in text


def test_n1_missing_boot_snapshot_is_raised(state: Path, cfg: sb.BoardConfig):
    (state / "cp3-sessions/long-20261022/producer/boot-journal-snapshot.json").unlink()
    warns = _issues(_board(cfg, D1022), sb.WARN)
    assert any(
        "부팅 스냅샷을 읽지 못해 pre-boot 봉을 빼지 않고 셌다" in w for w in warns
    )


def test_n2_an_unreadable_bar_id_is_refused_not_dropped(
    state: Path, cfg: sb.BoardConfig
):
    conn = sqlite3.connect(state / LEAVES["long-A05611"] / "marketfeed.sqlite3")
    snap = conn.execute(
        "SELECT snapshot_id FROM preimages WHERE raw_event_id LIKE '%20261022T1512%'"
    ).fetchone()[0]
    conn.execute(
        "UPDATE preimages SET raw_event_id = 'A05611:1m:garbage' WHERE snapshot_id = ?",
        (snap,),
    )
    conn.commit()
    conn.close()
    blocks = _issues(_board(cfg, D1022), sb.BLOCK)
    assert any("세션 범위 거부" in b and "A05611:1m:garbage" in b for b in blocks)


def test_n3_missing_expected_code_digest_after_boot_warns(
    state: Path, cfg: sb.BoardConfig
):
    (state / "cp3-sessions/long-20261022/config/release.yaml").unlink()
    assert (
        "long-20261022: release.yaml 의 expected_code_digest 를 찾지 못해 code_digest 를"
        " 대조하지 않았다" in _issues(_board(cfg, D1022), sb.WARN)
    )


@pytest.mark.parametrize(
    "mutate, needle",
    [
        (lambda d: d.update(unresolved=3), "unresolved.count 가 정수가 아니다"),
        (lambda d: d.update(summary_schema_version=4), "summary_schema_version=4"),
        (lambda d: d["live_comparison"].pop("divergent"), "live_comparison"),
    ],
)
def test_n4_b3_summary_of_another_shape_blocks_without_crashing(
    state: Path, cfg: sb.BoardConfig, mutate, needle
):
    path = state / "cp3-sessions/long-20261015/b3/report/summary.json"
    data = json.loads(path.read_text())
    mutate(data)
    path.write_text(json.dumps(data))
    board = _board(cfg, D1015)
    assert any(
        "B3 summary 를 읽을 수 없다" in b and needle in b
        for b in _issues(board, sb.BLOCK)
    )
    assert "B3 대조: summary 를 읽을 수 없음" in sb.render_text(board)


def test_n4_a_v2_divergence_count_is_a_warning_because_it_mixes_declared_ones(
    cfg: sb.BoardConfig,
):
    """A v2 summary's ``divergent`` is NOT the unexplained count.

    Concrete input: the 10-15 genesis summary, 26 divergent of 303 — a count
    that mixes the B1b-D1 family in, because that shape had no bucket for it.
    Reading it as "설명 안 되는 divergence" would report declared bars as
    unexplained, so the line says so and the grade stays 확인.
    """
    board = _board(cfg, D1015)
    assert (
        "long-20261015: B3 live divergent 26/303 — 이 summary 모양은 선언된 차이를"
        " 가르지 않는다" in _issues(board, sb.WARN)
    )
    assert "선언된 차이: 모름" in sb.render_text(board)


def test_n4_a_v3_divergence_is_a_check_and_the_declared_buckets_show_separately(
    state: Path, cfg: sb.BoardConfig
):
    """From v3 on, ``divergent`` IS the unexplained count — shown, not blocking.

    Concrete input: the same session rewritten in the v3 shape — 25 of the 26
    bars attributed to B1b-D1, one bar held out as the boot journal's own, and
    one left unexplained. The declared and held-out counts appear on their own
    line: folded into the divergent line they would be unreadable, and folded
    into ``divergent`` they would be unfalsifiable. The grade is 확인 since the
    2026-11-11 relaxation (§2 sentence 1) took these numbers out of the verdict.
    """
    path = state / "cp3-sessions/long-20261015/b3/report/summary.json"
    data = json.loads(path.read_text())
    data["summary_schema_version"] = sb.B3_DECLARED_BUCKET_SCHEMA_VERSION
    data["live_comparison"].update(
        bars_in_scope=303,
        excluded_from_comparison=1,
        compared_bars=302,
        divergent=1,
        declared_difference_counts={"B1b-D1": 25},
        excluded_bar_counts={"pre_boot_at_boot": 1},
    )
    path.write_text(json.dumps(data))
    board = _board(cfg, D1015)
    assert "long-20261015: B3 live divergent 1/302 (선언 B1b-D1 25)" in _issues(
        board, sb.WARN
    )
    assert not any("divergent" in b for b in _issues(board, sb.BLOCK))
    assert "선언된 차이: B1b-D1 25 · 대조 제외: pre_boot_at_boot 1" in sb.render_text(
        board
    )


def _b3_status(state: Path, session: str, **fields) -> None:
    """``<session>/b3/status.json`` — what the automated step leaves behind
    (``tools/tos_cp3/post_session_b3.py``)."""
    record = {
        "status_schema_version": 1,
        "verdict": "ok",
        "reason": "",
        "stage": None,
        "started_at": dt.datetime.now(sb.KST).isoformat(timespec="seconds"),
        "total_timeout_s": 480,
    }
    record.update(fields)
    path = state / "cp3-sessions" / session / "b3" / "status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record), encoding="utf-8")


def test_b3_that_could_not_run_blocks_and_the_summary_is_not_read(
    state: Path, cfg: sb.BoardConfig
):
    """**The fail-closed direction, on the board.** ``unresolved`` has a good
    value (0), so a stale summary next to a failed run must not be reported as
    this session's result: the run record is read first and the numbers are
    not read at all."""
    _b3_status(
        state,
        "long-20261015",
        verdict="failed",
        stage="b1a-fields",
        reason="b1a-fields exited 2 — see /x/b1a-fields.log",
    )
    board = _board(cfg, D1015)
    blocks = _issues(board, sb.BLOCK)
    assert (
        "long-20261015: B3 대조가 돌지 않았다 — failed (b1a-fields):"
        " b1a-fields exited 2 — see /x/b1a-fields.log" in blocks
    )
    # the fixture's own summary says unresolved 0 and divergent 26; neither is
    # reported, because this session did not produce them
    assert not any("B3 unresolved" in b for b in blocks)
    assert not any("B3 live divergent" in w for w in _issues(board, sb.WARN))
    assert "B3 대조: failed (b1a-fields)" in sb.render_text(board)


def test_b3_skipped_is_a_warning_not_a_block(state: Path, cfg: sb.BoardConfig):
    """A skip is a decision (the config, or a market B3 does not cover), not a
    defect — but B3 still did not run, so it is not silent either."""
    _b3_status(
        state,
        "long-20261015",
        verdict="skipped",
        reason="market 'stock' is not in config markets ['futures']",
    )
    board = _board(cfg, D1015)
    assert (
        "long-20261015: B3 대조 건너뜀 — market 'stock' is not in config"
        " markets ['futures']" in _issues(board, sb.WARN)
    )
    assert not any("B3" in b for b in _issues(board, sb.BLOCK))


def test_b3_still_running_inside_its_budget_is_only_a_warning(
    state: Path, cfg: sb.BoardConfig
):
    """B3 runs for a minute or two after the stop. Blocking on ``running``
    alone would raise a false alarm once a day, so the record's own
    ``total_timeout_s`` decides."""
    _b3_status(state, "long-20261015", verdict="running", stage=None)
    board = _board(cfg, D1015)
    assert "long-20261015: B3 대조 진행 중" in _issues(board, sb.WARN)
    assert not any("B3" in b for b in _issues(board, sb.BLOCK))


@pytest.mark.parametrize(
    "started",
    [
        "overdue",
        "unreadable",
        "naive",
    ],
)
def test_b3_running_past_its_budget_blocks(
    state: Path, cfg: sb.BoardConfig, started: str
):
    """``running`` that outlived its own budget is the SIGKILL case — the outer
    ``timeout`` cut the tool off and nothing replaced the record. A start time
    that cannot be read is treated the same way: an unreadable record cannot be
    used to claim the run is still going."""
    stamps = {
        "overdue": (dt.datetime.now(sb.KST) - dt.timedelta(seconds=10_000)).isoformat(
            timespec="seconds"
        ),
        "unreadable": "어제",
        "naive": "2026-10-15T15:50:00",
    }
    _b3_status(state, "long-20261015", verdict="running", started_at=stamps[started])
    blocks = _issues(_board(cfg, D1015), sb.BLOCK)
    assert any("B3 대조가 돌지 않았다 — running" in b for b in blocks), blocks


def test_b3_ok_reads_the_summary_as_before(state: Path, cfg: sb.BoardConfig):
    """The record gates the numbers; it does not replace them."""
    _b3_status(state, "long-20261015", verdict="ok")
    board = _board(cfg, D1015)
    assert _session(board, "long-20261015")["b3"]["divergent"] == 26
    assert any("B3 live divergent 26/303" in w for w in _issues(board, sb.WARN))


@pytest.mark.parametrize(
    ("fields", "needle"),
    [
        ({"status_schema_version": 2}, "status_schema_version=2"),
        ({"verdict": None}, "verdict 가 문자열이 아니다"),
    ],
)
def test_a_b3_record_of_another_shape_blocks_without_crashing(
    state: Path, cfg: sb.BoardConfig, fields: dict, needle: str
):
    _b3_status(state, "long-20261015", **fields)
    board = _board(cfg, D1015)
    assert any(
        "B3 실행 기록을 읽을 수 없다" in b and needle in b
        for b in _issues(board, sb.BLOCK)
    )
    assert "B3 대조: 실행 기록을 읽을 수 없음" in sb.render_text(board)


def test_a_session_with_no_b3_record_keeps_the_old_reading(cfg: sb.BoardConfig):
    """Sessions from before step 14 existed have no record. They must still be
    read off the summary alone, or every historical session turns red."""
    board = _board(cfg, D1015)
    assert _session(board, "long-20261015")["b3_run"] is None
    assert _session(board, "long-20261015")["b3"]["unresolved"] == 0


def test_n5_history_days_one_is_only_the_day(cfg: sb.BoardConfig):
    board = _board(replace(cfg, history_days=1), D1023)
    assert [(h["day"], h["label"]) for h in board["history"]] == [
        ("20261023", "long"),
        ("20261023", "short"),
    ]
    two = _board(replace(cfg, history_days=2), D1023)
    assert [h["day"] for h in two["history"]] == ["20261022", "20261023", "20261023"]


# --- MARKETFEED_PASS_OVERRUN (#949) ---------------------------------------------
#
# 픽스처 long 잎의 부팅 행: seq 0(10-15) · 51085(10-22) · 113576(10-23). short 잎: seq 0(10-23).
# 이 행은 날짜도 벽시계도 싣지 않으므로 세션 날짜의 경계는 곧 부팅 구간의 경계다.

SCHEDULER_SRC = (
    Path(__file__).resolve().parents[2]
    / "tos/runtime/src/tos_runtime/marketfeed/scheduler.py"
)


def _overrun_payload(pass_ms: int, tick_ms: int) -> dict:
    """런타임 ``TickScheduler._record_pass_overrun`` 의 행 모양 그대로(#949)."""
    return {
        "instrument": "A05611",
        "budget_ms": 500,
        "pass_ms": pass_ms,
        "tick_ms": tick_ms,
        "after_pass_ms": pass_ms - tick_ms,
        "poll_interval_ms": 400,
        "pass_allowance_ms": 100,
    }


def _insert(db: Path, rows: list[tuple[int, str, dict]]) -> None:
    conn = sqlite3.connect(db)
    for seq, kind, payload in rows:
        conn.execute(
            "INSERT INTO entries (seq, segment_id, kind, record_class, runtime_identity_json,"
            " payload_json, entry_digest, chain_digest, key_generation, appended_at_monotonic_ns)"
            " VALUES (?, NULL, ?, ?, NULL, ?, 'x', 'x', 0, 0)",
            (seq, kind, kind, json.dumps({"masked_keys": [], "payload": payload})),
        )
    conn.commit()
    conn.close()


def _append_overrun(state: Path, leaf: str, seq: int, pass_ms: int, tick_ms: int = 50):
    _insert(
        state / LEAVES[leaf] / "evidence.sqlite3",
        [(seq, sb.PASS_OVERRUN_KIND, _overrun_payload(pass_ms, tick_ms))],
    )


def test_overrun_kind_mirrors_the_runtime_constant():
    # tools/ 는 tos_runtime 를 import 할 수 없다(방화벽) — 소스 줄로 거울을 대조한다.
    assert (
        f'_MARKETFEED_PASS_OVERRUN_KIND = "{sb.PASS_OVERRUN_KIND}"'
        in SCHEDULER_SRC.read_text(encoding="utf-8")
    )


def test_overrun_zero_rows_shows_zero_and_raises_nothing(cfg: sb.BoardConfig):
    board = _board(cfg, D1022)
    st = _session(board, "long-20261022")["store"]
    assert st["pass_overrun"] == {"rows": 0, "worst": None}
    assert not [i for i in _issues(board) if sb.PASS_OVERRUN_KIND in i]
    assert f"    {sb.PASS_OVERRUN_KIND} 0행" in sb.render_text(board)


def test_overrun_rows_are_counted_per_tree(state: Path, cfg: sb.BoardConfig):
    _append_overrun(state, "long-A05611", 120001, 640, tick_ms=120)
    _append_overrun(state, "long-A05611", 120002, 910, tick_ms=150)
    _append_overrun(state, "short-A05611", 17000, 700, tick_ms=90)
    board = _board(cfg, D1023)
    long_ = _session(board, "long-20261023")["store"]["pass_overrun"]
    short = _session(board, "short-20261023")["store"]["pass_overrun"]
    assert long_ == {
        "rows": 2,
        "worst": {
            "seq": 120002,
            "pass_ms": 910,
            "budget_ms": 500,
            "tick_ms": 150,
            "after_pass_ms": 760,
        },
    }
    assert (short["rows"], short["worst"]["pass_ms"]) == (1, 700)
    warns = [i for i in _issues(board, sb.WARN) if sb.PASS_OVERRUN_KIND in i]
    assert warns == [
        f"long-20261023: {sb.PASS_OVERRUN_KIND} 2행 — 최악 pass 910ms > 창 500ms"
        " (tick 150ms + post-pass 760ms, seq 120002)",
        f"short-20261023: {sb.PASS_OVERRUN_KIND} 1행 — 최악 pass 700ms > 창 500ms"
        " (tick 90ms + post-pass 610ms, seq 17000)",
    ]
    # 진단 행이다 — 막힘이 아니다.
    assert not [i for i in _issues(board, sb.BLOCK) if sb.PASS_OVERRUN_KIND in i]
    text = sb.render_text(board)
    assert f"    {sb.PASS_OVERRUN_KIND} 2행 · 최악 pass 910ms > 창 500ms" in text
    history = {(h["day"], h["label"]): h["overrun"] for h in board["history"]}
    assert (history[("20261023", "long")], history[("20261023", "short")]) == (2, 1)


def test_overrun_rows_of_another_day_are_excluded_at_the_boot_boundary(
    state: Path, cfg: sb.BoardConfig
):
    # 10-22 부팅 구간의 마지막 seq 와 10-23 부팅 바로 다음 seq — 경계 양쪽 한 행씩.
    _append_overrun(state, "long-A05611", 113575, 600)
    _append_overrun(state, "long-A05611", 113577, 800)
    on_1022 = _session(_board(cfg, D1022), "long-20261022")["store"]["pass_overrun"]
    on_1023 = _session(_board(cfg, D1023), "long-20261023")["store"]["pass_overrun"]
    assert (on_1022["rows"], on_1022["worst"]["seq"]) == (1, 113575)
    assert (on_1023["rows"], on_1023["worst"]["seq"]) == (1, 113577)
    # 다른 잎(short)에는 번지지 않는다.
    assert _session(_board(cfg, D1023), "short-20261023")["store"]["pass_overrun"] == {
        "rows": 0,
        "worst": None,
    }


def test_paper_overrun_is_scoped_to_its_session(state: Path, cfg: sb.BoardConfig):
    # 10-22: report.json(baseline 479138, data_dir) · 10-23: 진행 중, bootproof 만(baseline 540128).
    boot = {"x": 1}
    _insert(
        state / PAPER_LEAF / "evidence.sqlite3",
        [
            (
                479100,
                sb.PASS_OVERRUN_KIND,
                _overrun_payload(999, 10),
            ),  # 10-22 baseline 이전
            (479140, sb.BOOT_KIND, boot),
            (479150, sb.PASS_OVERRUN_KIND, _overrun_payload(620, 10)),
            (479160, sb.PASS_OVERRUN_KIND, _overrun_payload(880, 10)),
            (540130, sb.BOOT_KIND, boot),
            (540200, sb.PASS_OVERRUN_KIND, _overrun_payload(530, 10)),
            (600000, sb.BOOT_KIND, boot),  # 다음 날 부팅
            (600100, sb.PASS_OVERRUN_KIND, _overrun_payload(990, 10)),
        ],
    )
    p1022 = _board(cfg, D1022)["paper"]["pass_overrun"]
    p1023 = _board(cfg, D1023)["paper"]["pass_overrun"]
    assert (p1022["rows"], p1022["worst"]["pass_ms"]) == (2, 880)
    assert (p1023["rows"], p1023["worst"]["pass_ms"]) == (1, 530)
    board = _board(cfg, D1023)
    assert f"paper: {sb.PASS_OVERRUN_KIND} 1행 — 최악 pass 530ms" in "\n".join(
        _issues(board, sb.WARN)
    )
    assert f"    {sb.PASS_OVERRUN_KIND} 1행 · 최악 pass 530ms" in sb.render_text(board)


def test_paper_without_a_leaf_is_unknown_not_zero(state: Path, cfg: sb.BoardConfig):
    shutil.rmtree(state / PAPER_LEAF)
    board = _board(cfg, D1023)
    po = board["paper"]["pass_overrun"]
    assert "error" in po  # 잎(paper-data/A05611)이 없다 — 0 행으로 말하지 않는다
    assert f"    {sb.PASS_OVERRUN_KIND}: 읽지 못함" in sb.render_text(board)
    assert any(
        i.startswith(f"paper: {sb.PASS_OVERRUN_KIND}·권한 행을 읽지 못했다")
        for i in _issues(board, sb.WARN)
    )


def test_paper_empty_leaf_is_zero(cfg: sb.BoardConfig):
    assert _board(cfg, D1023)["paper"]["pass_overrun"] == {"rows": 0, "worst": None}


def test_paper_without_a_boot_proof_is_not_given_the_next_sessions_rows(
    state: Path, cfg: sb.BoardConfig
):
    # #951 리뷰 LOW-1 의 입력: 10-22 런타임이 자기 TIME_SERVICE_STARTUP 을 쓰지 못했고(boot proof
    # MISSING), 10-23 세션이 같은 잎에서 부팅했다. 고치기 전에는 «기준 뒤 두 번째 부팅»(600000)
    # 이 상한이 되어 10-23 의 행(540200)이 10-22 에 붙었다.
    proof = state / "paper-sessions" / "2026-10-22-084508-LONG" / "bootproof.txt"
    lines = proof.read_text(encoding="utf-8").splitlines()
    lines[0] = "boot proof: MISSING · genesis=False · rev 0cc899617f5b · A05611"
    proof.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _insert(
        state / PAPER_LEAF / "evidence.sqlite3",
        [
            (540130, sb.BOOT_KIND, {"x": 1}),
            (540200, sb.PASS_OVERRUN_KIND, _overrun_payload(530, 10)),
            (600000, sb.BOOT_KIND, {"x": 1}),
        ],
    )
    board = _board(cfg, D1022)
    assert board["paper"]["pass_overrun"] is None
    assert (
        f"    {sb.PASS_OVERRUN_KIND}: 잎·기준 seq 를 몰라 보지 못함"
        in sb.render_text(board)
    )
    assert _board(cfg, D1023)["paper"]["pass_overrun"]["rows"] == 1


def test_tenant_overrun_without_a_boot_segment_is_unseen_not_zero(
    state: Path, cfg: sb.BoardConfig
):
    # short 잎의 유일한 부팅 행(seq 0)을 없애면 이 세션의 부팅 구간을 정할 수 없다.
    conn = sqlite3.connect(state / LEAVES["short-A05611"] / "evidence.sqlite3")
    conn.execute("DROP TRIGGER entries_no_delete")
    conn.execute("DELETE FROM entries WHERE kind = ?", (sb.BOOT_KIND,))
    conn.commit()
    conn.close()
    _append_overrun(state, "short-A05611", 17000, 700)
    board = _board(cfg, D1023)
    assert _session(board, "short-20261023")["store"]["pass_overrun"] is None
    assert (
        f"    {sb.PASS_OVERRUN_KIND}: 부팅 구간을 정할 수 없어 보지 못함"
        in sb.render_text(board)
    )
    history = {(h["day"], h["label"]): h["overrun"] for h in board["history"]}
    assert history[("20261023", "short")] is None


# --- 권한 행: AUTHORITY_WITNESS_LOST (#957) · APPROVAL_STANDING_* (#955) -----------

HEARTBEAT_SRC = (
    Path(__file__).resolve().parents[2]
    / "tos/runtime/src/tos_runtime/compose/_authority_heartbeat.py"
)
STANDING_SRC = (
    Path(__file__).resolve().parents[2]
    / "tos/runtime/src/tos_runtime/authority/standing.py"
)
ZERO_AUTHORITY = {
    "witness_lost": 0,
    "witness_lost_mid_session": 0,
    "witness_lost_mid_session_seqs": [],
    "witness_lost_before_first_tick": 0,
    "witness_lost_before_first_tick_seqs": [],
    "standing": {"bound": 0, "consumed": 0, "refused": 0, "not_covered": 0},
    "standing_consumed_by_action": {},
    "standing_refused_by_reason": {},
    "standing_not_covered_by_reason": {},
}


def _lost():
    return (
        sb.AUTHORITY_WITNESS_LOST_KIND,
        {"witness_source": "rcl", "within_containment_bound": False},
    )


def _standing(key: str, **payload):
    return (sb.STANDING_APPROVAL_KINDS[key], payload)


def _append_rows(state: Path, leaf: str, rows: list[tuple[int, tuple[str, dict]]]):
    _insert(
        state / LEAVES[leaf] / "evidence.sqlite3",
        [(seq, kind, payload) for seq, (kind, payload) in rows],
    )


def test_authority_kinds_mirror_the_runtime_constants():
    # tools/ 는 tos_runtime 를 import 할 수 없다(방화벽) — 소스 줄로 거울을 대조한다.
    heartbeat = HEARTBEAT_SRC.read_text(encoding="utf-8")
    assert (
        f'AUTHORITY_WITNESS_LOST_KIND = "{sb.AUTHORITY_WITNESS_LOST_KIND}"' in heartbeat
    )
    standing = STANDING_SRC.read_text(encoding="utf-8")
    for key, kind in sb.STANDING_APPROVAL_KINDS.items():
        assert f'_EVIDENCE_{key.upper()} = "{kind}"' in standing


def test_authority_zero_rows_shows_zero_and_raises_nothing(cfg: sb.BoardConfig):
    board = _board(cfg, D1022)
    assert _session(board, "long-20261022")["store"]["authority"] == ZERO_AUTHORITY
    assert board["paper"]["authority"] == ZERO_AUTHORITY
    assert not [i for i in _issues(board) if "AUTHORITY" in i or "APPROVAL" in i]
    assert (
        f"    {sb.AUTHORITY_WITNESS_LOST_KIND} 0행 (장중 0) · standing 승인 BOUND 0 · CONSUMED 0"
        " · REFUSED 0 · NOT_COVERED 0"
    ) in sb.render_text(board)


def test_authority_rows_are_counted_per_tree_and_mid_session_loss_blocks(
    state: Path, cfg: sb.BoardConfig
):
    _append_rows(
        state,
        "long-A05611",
        [
            (120010, _standing("bound", artifact_digest="d")),
            (120011, _standing("consumed", action="ENTER", slot="s1")),
            (120012, _standing("consumed", action="ENTER", slot="s2")),
            (120013, _standing("consumed", action="EXIT", slot="s1")),
            (
                120014,
                _standing("refused", reason="digest_changed_since_bound", detail="x"),
            ),
            (120015, _standing("not_covered", reason="uses_exhausted:ENTER")),
            (120016, _lost()),
        ],
    )
    _append_rows(state, "short-A05611", [(17010, _lost()), (17011, _lost())])
    board = _board(cfg, D1023)
    long_ = _session(board, "long-20261023")["store"]["authority"]
    short = _session(board, "short-20261023")["store"]["authority"]
    assert long_ == {
        "witness_lost": 1,
        "witness_lost_mid_session": 1,  # 120016 > 첫 틱 113595
        "witness_lost_mid_session_seqs": [120016],
        "witness_lost_before_first_tick": 0,
        "witness_lost_before_first_tick_seqs": [],
        "standing": {"bound": 1, "consumed": 3, "refused": 1, "not_covered": 1},
        "standing_consumed_by_action": {"ENTER": 2, "EXIT": 1},
        "standing_refused_by_reason": {"digest_changed_since_bound": 1},
        "standing_not_covered_by_reason": {"uses_exhausted:ENTER": 1},
    }
    assert short == ZERO_AUTHORITY | {
        "witness_lost": 2,
        "witness_lost_mid_session": 2,
        "witness_lost_mid_session_seqs": [17010, 17011],
    }
    warns = [i for i in _issues(board, sb.WARN) if "AUTHORITY" in i or "APPROVAL" in i]
    assert warns == [
        "long-20261023: APPROVAL_STANDING_REFUSED 1행 (digest_changed_since_bound 1)",
        "long-20261023: APPROVAL_STANDING_NOT_COVERED 1행 (uses_exhausted:ENTER 1)",
    ]
    tail = (
        "; 첫 틱 뒤 또는 송신 봉인 뒤)"
        " — 이후 송신은 재부팅 전까지 거절된다(fail-closed)"
    )
    assert [i for i in _issues(board, sb.BLOCK) if "AUTHORITY" in i] == [
        f"long-20261023: {sb.AUTHORITY_WITNESS_LOST_KIND} 장중 1행 (seq 120016{tail}",
        f"short-20261023: {sb.AUTHORITY_WITNESS_LOST_KIND} 장중 2행 (seq 17010,17011{tail}",
    ]
    text = sb.render_text(board)
    assert (
        f"    {sb.AUTHORITY_WITNESS_LOST_KIND} 1행 (장중 1) · standing 승인 BOUND 1"
        " · CONSUMED 3 (ENTER 2 · EXIT 1) · REFUSED 1 (digest_changed_since_bound 1)"
        " · NOT_COVERED 1 (uses_exhausted:ENTER 1)"
    ) in text
    history = {(h["day"], h["label"]): h["witness_lost"] for h in board["history"]}
    assert (history[("20261023", "long")], history[("20261023", "short")]) == (1, 2)


def test_authority_rows_of_another_day_are_excluded_at_the_boot_boundary(
    state: Path, cfg: sb.BoardConfig
):
    _append_rows(
        state,
        "long-A05611",
        [(113575, _lost()), (113577, _standing("consumed", action="ENTER"))],
    )
    on_1022 = _session(_board(cfg, D1022), "long-20261022")["store"]["authority"]
    on_1023 = _session(_board(cfg, D1023), "long-20261023")["store"]["authority"]
    assert (on_1022["witness_lost"], on_1022["standing"]["consumed"]) == (1, 0)
    assert (on_1023["witness_lost"], on_1023["standing"]["consumed"]) == (0, 1)


def test_tenant_authority_without_a_boot_segment_is_unseen_not_zero(
    state: Path, cfg: sb.BoardConfig
):
    conn = sqlite3.connect(state / LEAVES["short-A05611"] / "evidence.sqlite3")
    conn.execute("DROP TRIGGER entries_no_delete")
    conn.execute("DELETE FROM entries WHERE kind = ?", (sb.BOOT_KIND,))
    conn.commit()
    conn.close()
    _append_rows(state, "short-A05611", [(17010, _lost())])
    board = _board(cfg, D1023)
    assert _session(board, "short-20261023")["store"]["authority"] is None
    assert "    권한 행: 부팅 구간을 정할 수 없어 보지 못함" in sb.render_text(board)
    history = {(h["day"], h["label"]): h["witness_lost"] for h in board["history"]}
    assert history[("20261023", "short")] is None


def test_paper_authority_is_scoped_to_its_session(state: Path, cfg: sb.BoardConfig):
    boot = {"x": 1}
    kind_lost, p_lost = _lost()
    _insert(
        state / PAPER_LEAF / "evidence.sqlite3",
        [
            (479100, kind_lost, p_lost),  # 10-22 baseline 이전
            (479140, sb.BOOT_KIND, boot),
            (479150, kind_lost, p_lost),
            (540130, sb.BOOT_KIND, boot),
            (540140, *_standing("not_covered", reason="unbounded")),
            (600000, sb.BOOT_KIND, boot),  # 다음 날 부팅
            (600100, kind_lost, p_lost),
        ],
    )
    p1022 = _board(cfg, D1022)["paper"]["authority"]
    board = _board(cfg, D1023)
    p1023 = board["paper"]["authority"]
    assert (p1022["witness_lost"], p1022["standing"]["not_covered"]) == (1, 0)
    assert (p1023["witness_lost"], p1023["standing"]["not_covered"]) == (0, 1)
    assert "paper: APPROVAL_STANDING_NOT_COVERED 1행 (unbounded 1)" in _issues(
        board, sb.WARN
    )


def test_paper_authority_without_a_boot_proof_is_unseen(
    state: Path, cfg: sb.BoardConfig
):
    proof = state / "paper-sessions" / "2026-10-22-084508-LONG" / "bootproof.txt"
    lines = proof.read_text(encoding="utf-8").splitlines()
    lines[0] = "boot proof: MISSING · genesis=False · rev 0cc899617f5b · A05611"
    proof.write_text("\n".join(lines) + "\n", encoding="utf-8")
    board = _board(cfg, D1022)
    assert board["paper"]["authority"] is None
    assert "    권한 행: 잎·기준 seq 를 몰라 보지 못함" in sb.render_text(board)


# --- 증인 상실: 장 전(설계상) vs 장중 — 위치로 가른다(#962 리뷰 MEDIUM) ----------
# long 10-23: 부팅 seq 113576, 첫 틱 evidence seq 113595.


def test_a_pre_open_loss_before_the_first_tick_does_not_block(
    state: Path, cfg: sb.BoardConfig
):
    _append_rows(state, "long-A05611", [(113580, _lost())])
    board = _board(cfg, D1023)
    auth = _session(board, "long-20261023")["store"]["authority"]
    assert (auth["witness_lost"], auth["witness_lost_mid_session"]) == (1, 0)
    # 장 전 설계상 상실은 본문 수로만 보인다 — 막힘도 확인 줄도 없다.
    assert not [i for i in _issues(board) if sb.AUTHORITY_WITNESS_LOST_KIND in i]
    assert f"    {sb.AUTHORITY_WITNESS_LOST_KIND} 1행 (장중 0)" in sb.render_text(board)
    history = {(h["day"], h["label"]): h for h in board["history"]}
    assert (
        history[("20261023", "long")]["witness_lost"],
        history[("20261023", "long")]["witness_lost_mid_session"],
    ) == (1, 0)


def test_stock_mock_loss_at_1030_after_ticks_is_mid_session():
    # stock-r1-20261026 모양: 09:01 봉의 첫 틱 seq 1000, 10:30 상실 seq 50000(틱 뒤), 송신 없음.
    auth = sb.authority_summary(
        [(50000, sb.AUTHORITY_WITNESS_LOST_KIND, {})],
        first_tick_seq=1000,
        first_send_seq=None,
    )
    assert (
        auth["witness_lost_mid_session"],
        auth["witness_lost_mid_session_seqs"],
    ) == (
        1,
        [50000],
    )
    assert [lv for lv, _ in sb._authority_issues(auth)] == [sb.BLOCK]


def test_a_loss_after_a_send_sealed_blocks_even_before_the_first_tick(
    state: Path, cfg: sb.BoardConfig
):
    _append_rows(
        state,
        "long-A05611",
        [(113578, (sb.SEND_SEALED_KIND, {"x": 1})), (113580, _lost())],
    )
    board = _board(cfg, D1023)
    auth = _session(board, "long-20261023")["store"]["authority"]
    assert auth["witness_lost_mid_session_seqs"] == [113580]
    assert any(
        i.startswith(f"long-20261023: {sb.AUTHORITY_WITNESS_LOST_KIND} 장중 1행")
        for i in _issues(board, sb.BLOCK)
    )


def test_a_loss_before_any_tick_warns_but_does_not_block(state: Path):
    # (d) #962 r2 LOW: paper 10-23, 부팅 뒤 상실, 아직 틱(EVENT_HANDLING_STARTED) 없음,
    # 송신 봉인 없음 → 확인(막힘 아님, exit 1 아님).
    _insert(
        state / PAPER_LEAF / "evidence.sqlite3",
        [(540130, sb.BOOT_KIND, {"x": 1}), (540140, *_lost())],
    )
    cfg = replace(sb.load_config(), state_dir=state)
    board = _board(cfg, D1023)
    auth = board["paper"]["authority"]
    assert (
        auth["witness_lost_mid_session"],
        auth["witness_lost_before_first_tick_seqs"],
    ) == (0, [540140])
    assert not [
        i for i in _issues(board, sb.BLOCK) if sb.AUTHORITY_WITNESS_LOST_KIND in i
    ]
    assert (
        f"paper: {sb.AUTHORITY_WITNESS_LOST_KIND} 첫 틱 전 상실 1행 (seq 540140)"
        in "\n".join(_issues(board, sb.WARN))
    )
    assert (
        f"    {sb.AUTHORITY_WITNESS_LOST_KIND} 1행 (장중 0 · 첫 틱 전 1)"
        in sb.render_text(board)
    )
    no_tick = sb.authority_summary(
        [(5, sb.AUTHORITY_WITNESS_LOST_KIND, {})],
        first_tick_seq=None,
        first_send_seq=None,
    )
    assert (
        no_tick["witness_lost_mid_session"],
        no_tick["witness_lost_before_first_tick"],
    ) == (0, 1)
    assert [lv for lv, _ in sb._authority_issues(no_tick)] == [sb.WARN]


def test_a_loss_after_a_send_sealed_blocks_even_with_no_tick_yet():
    auth = sb.authority_summary(
        [(10, sb.AUTHORITY_WITNESS_LOST_KIND, {})],
        first_tick_seq=None,
        first_send_seq=7,
    )
    assert (
        auth["witness_lost_mid_session"],
        auth["witness_lost_before_first_tick"],
    ) == (1, 0)
    assert [lv for lv, _ in sb._authority_issues(auth)] == [sb.BLOCK]


def test_paper_pre_open_loss_before_its_first_handled_tick_is_quiet(
    state: Path, cfg: sb.BoardConfig
):
    _insert(
        state / PAPER_LEAF / "evidence.sqlite3",
        [
            (540130, sb.BOOT_KIND, {"x": 1}),
            (540140, *_lost()),
            (540150, sb.HANDLING_STARTED_KIND, {"x": 1}),
        ],
    )
    board = _board(cfg, D1023)
    auth = board["paper"]["authority"]
    assert (auth["witness_lost"], auth["witness_lost_mid_session"]) == (1, 0)
    assert not [i for i in _issues(board) if sb.AUTHORITY_WITNESS_LOST_KIND in i]


def test_send_and_handling_kinds_mirror_the_runtime_constants():
    src = (
        Path(__file__).resolve().parents[2]
        / "tos/runtime/src/tos_runtime/riskstate/flow_observation.py"
    ).read_text(encoding="utf-8")
    assert f'_SEND_SEALED_KIND = "{sb.SEND_SEALED_KIND}"' in src
    assert f'_HANDLING_STARTED_KIND = "{sb.HANDLING_STARTED_KIND}"' in src


def test_history_label_column_fits_a_two_digit_stock_run():
    row = {
        "day": "20261026",
        "label": "stock-r10",
        "status": "ENDED",
        "run_rc": 0,
        "ticks": 1,
        "stale": 0,
        "other_withheld": 0,
        "band": 0,
        "overrun": 0,
        "witness_lost": 0,
        "witness_lost_mid_session": 0,
        "b3_unresolved": None,
        "store_error": None,
        "blocks": 0,
    }
    short = row | {"label": "long"}
    board = {
        "date": "2026-10-26",
        "state_dir": "/x",
        "generated_kst": "t",
        "issues": [],
        "tenant_sessions": [],
        "cron": {},
        "paper": {"live_check": False, "session": None},
        "history": [row, short],
    }
    lines = [
        ln for ln in sb.render_text(board).splitlines() if ln.startswith("  20261026")
    ]
    # 라벨 뒤 상태 칸이 두 줄에서 같은 열에서 시작한다.
    assert lines[0].index("ENDED") == lines[1].index("ENDED")


def test_a_mid_session_loss_turns_the_exit_code_to_1(tmp_path: Path, state: Path):
    # 픽스처 10-22 는 stale 비율로 이미 막힘이다 — 그 판정만 풀어 상실 하나의 효과를 본다.
    config = tmp_path / "board.yaml"
    config.write_text(
        sb.DEFAULT_CONFIG_PATH.read_text(encoding="utf-8").replace(
            "stale_refusal_ratio_max: 0.005", "stale_refusal_ratio_max: 0.5"
        ),
        encoding="utf-8",
    )

    def rc() -> int:
        return sb.run(config_path=config, state_dir=str(state), date="2026-10-22")[1]

    assert rc() == 0
    _append_rows(state, "long-A05611", [(60000, _lost())])  # 10-22 첫 틱 51104 뒤
    assert rc() == 1


# --- 4단계(독립 승인) UNKNOWN 정지 — 선물 결정 전용(운영자 판정 2026-11-05) ---------

#: 10-15 세션의 첫 제안 블록(evidence seq 46, 09:04 봉) 과 그 다음 결정(936) 사이의
#: 빈 seq — 여기 넣은 흐름 정지 행은 그 제안의 것으로 읽힌다. 같은 날에는 녹화된
#: ``VENUE_ADMISSIBILITY_DECISION`` UNKNOWN 두 건(940 · 1688)과 ``STAGE_DENIED``
#: 한 건(49475)이 이미 있어, 한 줄에서 세 경우를 모두 본다.
STEP4_HALT_SEQ = 500


def _append_step4_unknown(state: Path, seq: int = STEP4_HALT_SEQ) -> None:
    """런타임 ``engine.sequencer._halt`` 가 4단계에서 쓰는 행 모양 그대로.

    ``step`` · ``halt_reason`` · ``detail`` 은 실 잎
    (``~/.local/state/tos/cp3-setup-d-long-data/A05611/evidence.sqlite3``, 2026-11-05
    읽기 전용 확인: 이 모양 67행)에서 그대로 옮겼다.
    """
    _append_rows(
        state,
        "long-A05611",
        [
            (
                seq,
                (
                    "FLOW_HALTED",
                    {
                        "kind": "FLOW_HALTED",
                        "step": sb.INDEPENDENT_APPROVAL_STEP,
                        "halt_reason": sb.STAGE_UNKNOWN_HALT_REASON,
                        "detail": (
                            "no independent approval decision is available for this "
                            "proposal — UNKNOWN is restrictive, never an assumed grant"
                        ),
                        "instrument_key": {
                            "account": "6004929703",
                            "instrument": "A05611",
                        },
                    },
                ),
            )
        ],
    )


def _set_market(state: Path, name: str, market: str) -> None:
    """러너 step 5b 의 market 줄을 세션 로그에 넣는다.

    픽스처(10-15~10-23)는 그 줄이 생기기 전 녹화다. 줄 모양은 실 로그 그대로다 —
    ``cp3-sessions/long-20261104/session.log`` 5번째 줄
    ``market=futures (tree and producer agree) · transport=synthetic``.
    """
    path = state / "cp3-sessions" / name / "session.log"
    lines = path.read_text(encoding="utf-8").splitlines()
    ts = lines[0][:19]
    transport = "synthetic" if market == "futures" else "kis-mock"
    at = next(i for i, line in enumerate(lines) if " instrument=" in line)
    lines.insert(
        at, f"{ts} market={market} (tree and producer agree) · transport={transport}"
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_the_market_line_of_a_tenant_session_is_read(state: Path):
    """러너 step 5b 의 ``market=`` 줄 — 트리의 범위를 말하는 유일한 로그 줄이다."""
    _set_market(state, "long-20261015", "futures")
    runner = sb.parse_runner_log(
        (state / "cp3-sessions/long-20261015/session.log").read_text(encoding="utf-8")
    )
    assert runner.market == "futures"
    # 뒤에 오는 B3 줄(`=== B3 … market=… ceiling …`)은 이 값을 덮지 않는다.
    b3_only = sb.parse_runner_log(
        "2026-10-15 15:50:03 === B3 session-dir=/x instrument=A05611 "
        "market=stock ceiling 600s"
    )
    assert b3_only.market is None


def test_futures_tree_step4_unknown_is_labelled_expected(
    state: Path, cfg: sb.BoardConfig
):
    """선물 트리의 4단계 UNKNOWN 은 떼어 이름을 붙이고, 다른 단계는 그대로 둔다.

    상주 session 승인은 설계상 MOCK 주식 전용이라(``tos_runtime.authority.standing``)
    선물 진입 제안은 4단계에서 멈춘다. 운영자 판정 2026-11-05: 선물 트리는 결정
    전용이고 이 정지가 예상 종착이다(LONG 실측 11 부팅 67 건 · 11-04 40 건, 4단계
    admit 은 한 번도 없다). 같은 날의 ``VENUE_ADMISSIBILITY_DECISION`` UNKNOWN 두
    건은 4단계가 아니므로 기존 이름 아래 그대로 남는다.
    """
    _append_step4_unknown(state)
    _set_market(state, "long-20261015", "futures")
    board = _board(cfg, D1015)
    s = _session(board, "long-20261015")
    assert s["market"] == "futures"
    st = s["store"]
    # 기존 필드는 그대로 전체 분포를 싣고, 새 필드가 그 부분집합을 센다.
    assert st["flow_halts"] == {"STAGE_DENIED": 1, "STAGE_UNKNOWN": 3}
    assert st["flow_halts_independent_approval_unknown"] == 1
    assert (
        "흐름 정지: STAGE_DENIED 1 · STAGE_UNKNOWN 2"
        f" · {sb.STEP4_UNKNOWN_EXPECTED_LABEL} 1" in sb.render_text(board)
    )
    # 예상 종착이므로 소견(막힘·확인)은 새로 올리지 않는다.
    assert not any(sb.STEP4_UNKNOWN_EXPECTED_LABEL in i for i in _issues(board))


def test_stock_tree_step4_unknown_is_not_labelled_expected(
    state: Path, cfg: sb.BoardConfig
):
    """주식 트리에서는 떼지 않는다 — standing 승인이 덮어야 하는 것이라 예상이 아니다."""
    _append_step4_unknown(state)
    _set_market(state, "long-20261015", "stock")
    board = _board(cfg, D1015)
    s = _session(board, "long-20261015")
    assert s["market"] == "stock"
    # 기계용 필드는 시장과 무관하게 같은 수를 싣는다(이름을 붙이는 쪽만 가른다).
    assert s["store"]["flow_halts_independent_approval_unknown"] == 1
    text = sb.render_text(board)
    assert "흐름 정지: STAGE_DENIED 1 · STAGE_UNKNOWN 3" in text
    assert sb.STEP4_UNKNOWN_EXPECTED_LABEL not in text


def test_a_session_log_without_a_market_line_is_not_labelled_expected(
    state: Path, cfg: sb.BoardConfig
):
    """market 줄이 없는 옛 세션(~10-23) — 시장을 모르면 「예상」이라 말하지 않는다."""
    _append_step4_unknown(state)
    board = _board(cfg, D1015)
    assert _session(board, "long-20261015")["market"] is None
    text = sb.render_text(board)
    assert "흐름 정지: STAGE_DENIED 1 · STAGE_UNKNOWN 3" in text
    assert sb.STEP4_UNKNOWN_EXPECTED_LABEL not in text


def test_without_a_step4_halt_a_futures_line_is_unchanged(
    state: Path, cfg: sb.BoardConfig
):
    """4단계 정지가 0 이면 선물 트리에서도 이름을 붙이지 않는다(빈 꼬리 금지)."""
    _set_market(state, "long-20261015", "futures")
    board = _board(cfg, D1015)
    st = _session(board, "long-20261015")["store"]
    assert st["flow_halts_independent_approval_unknown"] == 0
    text = sb.render_text(board)
    assert "흐름 정지: STAGE_DENIED 1 · STAGE_UNKNOWN 2" in text
    assert sb.STEP4_UNKNOWN_EXPECTED_LABEL not in text


# --- 깨끗한 거래일 누적 (2026-11-11 완화 §2 문장 1) --------------------------------

#: 2026-10-12(월) 앞의 두 주. 10-09(한글날·금) · 10-05(대체휴일·월) 가 휴장이고 그 양쪽에
#: 주말이 붙어, 「비거래일은 세지도 깨지도 않는다」를 실제 KRX 캘린더로 시험한다.
D1012 = dt.date(2026, 10, 12)
STREAK_CLEAN_DAYS = (
    dt.date(2026, 10, 12),
    dt.date(2026, 10, 8),
    dt.date(2026, 10, 7),
    dt.date(2026, 10, 6),
    dt.date(2026, 10, 2),
)


def _mk_session(
    state: Path,
    label: str,
    day: dt.date,
    *,
    run_rc: int | None = 0,
    booted: bool = False,
    status_fields: dict | None = None,
    summary_fields: dict | None = None,
    write_status: bool = True,
    write_summary: bool = True,
) -> Path:
    """세션 디렉터리 하나 — 누적 판정이 읽는 것만 담는다(러너 로그의 END 줄 + B3 두 파일).

    저장소는 담지 않는다. 깨끗함의 조건에 저장소는 없고, 담으면 이 테스트가 판정이 아니라
    sqlite 모양을 시험하게 된다. ``booted=True`` 에 ``run_rc=None`` 은 11-10 호스트
    크래시의 모양이다 — 부팅했고 END 줄이 없으니 지난 날짜에서는 ``LOST`` 다.
    """
    path = state / "cp3-sessions" / f"{label}-{day:%Y%m%d}"
    path.mkdir(parents=True)
    lines = [f"{day} 08:38:01 checkout ok: … repo_commit=deadbeef"]
    if booted:
        lines.append(f"{day} 08:45:00 === BOOT runtime")
    if run_rc is not None:
        lines += [
            f"{day} 15:50:01 === END run rc={run_rc}",
            f"{day} 15:50:01 === END producer rc=0",
        ]
    (path / "session.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if write_status:
        record = {
            "status_schema_version": 1,
            "verdict": "ok",
            "reason": "",
            "stage": None,
            "started_at": dt.datetime.now(sb.KST).isoformat(timespec="seconds"),
            "total_timeout_s": 480,
        }
        record.update(status_fields or {})
        (path / "b3").mkdir(exist_ok=True)
        (path / "b3" / "status.json").write_text(json.dumps(record), encoding="utf-8")
    if write_summary:
        live = {
            "bars_in_scope": 409,
            "excluded_from_comparison": 1,
            "compared_bars": 408,
            "identical": 408,
            "divergent": 0,
            "declared_difference_counts": {},
            "excluded_bar_counts": {"pre_boot_at_boot": 1},
        }
        summary = {
            "summary_schema_version": sb.B3_DECLARED_BUCKET_SCHEMA_VERSION,
            "unresolved": {"count": 0},
            "live_comparison": live,
            "window_identity": {
                "window_start": "2026-10-06",
                "window_end": f"{day}",
            },
        }
        for key, value in (summary_fields or {}).items():
            if key == "live_comparison":
                live.update(value)
            else:
                summary[key] = value
        report = path / "b3" / "report"
        report.mkdir(parents=True, exist_ok=True)
        (report / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    return path


@pytest.fixture
def streak_state(tmp_path: Path) -> Path:
    """깨끗한 다섯 거래일(휴장·주말을 두 번 건너뛴다)만 있는 상태 루트."""
    state = tmp_path / "streak"
    (state / "cp3-sessions").mkdir(parents=True)
    for day in STREAK_CLEAN_DAYS:
        _mk_session(state, "long", day)
    return state


@pytest.fixture
def streak_cfg(streak_state: Path) -> sb.BoardConfig:
    return replace(sb.load_config(), state_dir=streak_state)


def _streak(board: dict, label: str) -> dict:
    return next(t for t in board["clean_streak"] if t["label"] == label)


def test_committed_clean_day_config_is_the_relaxed_target():
    """2026-11-11 완화: 목표 5 · 창 40 · LONG 만 센다(SHORT 는 운영자가 켠 추가 트리)."""
    scfg = sb.load_config().clean_streak
    assert scfg.target_days == 5  # «깨끗한 거래일 누적 5일»
    assert scfg.window_days == 40  # «최근 40일 창»
    assert scfg.clean_run_rcs == frozenset({0})
    assert [t.label for t in scfg.trees] == ["long"]
    for tree in scfg.trees:
        assert tree.calendar_yaml.exists(), tree.calendar_yaml
        holidays = sb.load_tree_calendar(tree.calendar_yaml).holidays
        # 창이 지나는 휴장일. 거래일이 아니므로 세지도 깨지도 않는다.
        for closed in (dt.date(2026, 12, 25), dt.date(2026, 12, 31)):
            assert closed in holidays
            assert sd.is_trading_day(closed, holidays) is False


@pytest.mark.parametrize(
    "mutate, needle",
    [
        ({"window_days": 3}, "window_days=3"),
        ({"trees": []}, "trees 가 비었다"),
        ({"clean_run_rcs": []}, "clean_run_rcs 가 비었다"),
        ({"calendar_covered_years": []}, "calendar_covered_years 가 비었다"),
        ({"target_days": 0}, "target_days=0"),
        (
            {"trees": [{"label": "long"}]},
            "trees[0] 에 calendar_yaml 이 없다",
        ),
        (
            {
                "trees": [
                    {"label": "long", "calendar_yaml": "a.yaml"},
                    {"label": "long", "calendar_yaml": "b.yaml"},
                ]
            },
            "label 이 겹친다",
        ),
    ],
)
def test_streak_config_bad_shapes_are_refused(
    mutate: dict, needle: str, tmp_path: Path
):
    raw = {
        "target_days": 5,
        "window_days": 40,
        "clean_run_rcs": [0],
        "calendar_covered_years": [2026],
        "trees": [{"label": "long", "calendar_yaml": "a.yaml"}],
    }
    raw.update(mutate)
    with pytest.raises(ValueError, match=re.escape(needle)):
        sb.load_streak_config(raw, path=tmp_path / "c.yaml")


def test_clean_days_cross_a_weekend_and_a_holiday(streak_cfg: sb.BoardConfig):
    """비거래일은 세지도 깨지도 않는다 — 실제 KRX 캘린더로.

    구체 입력: 10-12 · 10-08 · 10-07 · 10-06 · 10-02 다섯 세션. 그 사이에 10-09(한글날)와
    주말, 10-05(대체휴일)와 주말이 있고 세션이 하나도 없다. 그 날들이 거래일로 읽히면
    「세션 없음」으로 깨진 날에 적히므로, ``broke_on`` 이 비어 있는 것이 그 판정이다.
    """
    board = _board(streak_cfg, D1012)
    long = _streak(board, "long")
    assert (long["days"], long["start"], long["met"]) == (5, "2026-10-02", True)
    assert (long["broke_on"], long["broke_reason"]) == (None, None)
    assert long["pending"] is None and long["error"] is None
    assert long["window_start"] == "2026-10-02"
    # SHORT 는 세지 않는다(완화 §2 문장 1) — 설정에 없으므로 이 절에 나오지 않는다.
    assert [t["label"] for t in board["clean_streak"]] == ["long"]
    assert "✔ 목표 충족" in sb.render_text(board)


def test_the_clean_days_span_christmas(tmp_path: Path):
    """12-25 휴장도 세지 않고 깨뜨리지도 않는다.

    구체 입력: 12-30 · 12-29 · 12-28 · 12-24 · 12-23 다섯 세션. 12-25(금·크리스마스)와
    12-26·27 주말에는 세션이 없다. 누적은 5 이고 깨진 날은 없다.
    """
    state = tmp_path / "december"
    (state / "cp3-sessions").mkdir(parents=True)
    december = (
        dt.date(2026, 12, 30),
        dt.date(2026, 12, 29),
        dt.date(2026, 12, 28),
        dt.date(2026, 12, 24),
        dt.date(2026, 12, 23),
    )
    for day in december:
        _mk_session(state, "long", day)
    cfg = replace(sb.load_config(), state_dir=state)
    long = _streak(_board(cfg, dt.date(2026, 12, 30)), "long")
    assert (long["days"], long["start"], long["met"]) == (5, "2026-12-23", True)
    assert (long["broke_on"], long["broke_reason"]) == (None, None)


def test_a_clean_day_a_lost_day_and_a_clean_day_count_two(tmp_path: Path):
    """**완화의 핵심.** 깨진 하루가 앞의 기록을 지우지 않는다.

    구체 입력: 10-12 깨끗 · 10-08 LOST(11-10 호스트 크래시의 모양 — 부팅했고 END 줄이
    없다) · 10-07 깨끗. 연속 판정이었다면 10-08 에서 멈춰 1 이었다. 누적은 2 이고,
    10-08 은 「마지막 깨진 거래일」로 계속 보고된다.
    """
    state = tmp_path / "cumulative"
    (state / "cp3-sessions").mkdir(parents=True)
    _mk_session(state, "long", dt.date(2026, 10, 12))
    _mk_session(state, "long", dt.date(2026, 10, 8), run_rc=None, booted=True)
    _mk_session(state, "long", dt.date(2026, 10, 7))
    cfg = replace(sb.load_config(), state_dir=state)
    long = _streak(_board(cfg, D1012), "long")
    assert (long["days"], long["met"], long["start"]) == (2, False, "2026-10-07")
    assert (long["broke_on"], long["broke_reason"]) == ("2026-10-08", "세션 상태 LOST")


def test_a_trading_day_without_a_session_is_skipped_not_a_reset(
    streak_state: Path, streak_cfg: sb.BoardConfig
):
    """중간의 거래일 하나가 비면 그 하루만 빠진다 — 5 가 4 가 되고 0 이 되지 않는다."""
    shutil.rmtree(streak_state / "cp3-sessions" / "long-20261007")
    board = _board(streak_cfg, D1012)
    long = _streak(board, "long")
    assert (long["days"], long["met"], long["start"]) == (4, False, "2026-10-02")
    assert (long["broke_on"], long["broke_reason"]) == (
        "2026-10-07",
        "세션 디렉터리 없음",
    )
    assert (
        "마지막 깨진 거래일 2026-10-07 — 세션 디렉터리 없음 (누적을 지우지 않는다)"
        in sb.render_text(board)
    )


def test_the_most_recent_broken_day_is_the_one_reported(
    streak_state: Path, streak_cfg: sb.BoardConfig
):
    """깨진 날이 둘이면 **가장 최근** 것을 보고한다(거꾸로 걸어 처음 만나는 날)."""
    for day in ("long-20261008", "long-20261006"):
        shutil.rmtree(streak_state / "cp3-sessions" / day)
    long = _streak(_board(streak_cfg, D1012), "long")
    assert (long["days"], long["broke_on"]) == (3, "2026-10-08")


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param({"summary_schema_version": 2}, id="v2-shape"),
        pytest.param({"live_comparison": {"divergent": 3, "identical": 405}}, id="div"),
        pytest.param({"unresolved": {"count": 2}}, id="unresolved"),
        pytest.param(
            {"live_comparison": {"compared_bars": 0, "identical": 0}}, id="zero-bars"
        ),
    ],
)
def test_what_b3_saw_no_longer_decides_whether_a_day_counts(
    streak_state: Path, streak_cfg: sb.BoardConfig, mutate: dict
):
    """2026-11-11 완화 §2 문장 1 — B3 는 **돌았는지만** 본다.

    구체 입력: 10-08 의 summary 를 옛 모양 · divergent 3 · unresolved 2 · 대조한 봉 0
    으로 바꾼다. 전에는 각각이 그 하루를 깨뜨렸다. 이제는 B3 가 돌았으므로(실행 기록의
    verdict 가 ok) 그 하루가 그대로 세어지고, 그 수들은 상태판의 «확인» 줄로만 나온다
    (``test_b3_unresolved_is_a_check_not_a_block``).
    """
    path = streak_state / "cp3-sessions/long-20261008/b3/report/summary.json"
    data = json.loads(path.read_text())
    for key, value in mutate.items():
        if key == "live_comparison":
            data["live_comparison"].update(value)
        else:
            data[key] = value
    path.write_text(json.dumps(data))
    long = _streak(_board(streak_cfg, D1012), "long")
    assert (long["days"], long["met"], long["broke_on"]) == (5, True, None)


def test_a_day_whose_summary_is_missing_still_counts_if_b3_ran(
    streak_state: Path, streak_cfg: sb.BoardConfig
):
    """summary 가 없어도 실행 기록이 ok 면 센다 — 깨끗함의 조건에서 빠졌다."""
    shutil.rmtree(streak_state / "cp3-sessions" / "long-20261008")
    _mk_session(streak_state, "long", dt.date(2026, 10, 8), write_summary=False)
    long = _streak(_board(streak_cfg, D1012), "long")
    assert (long["days"], long["met"], long["broke_on"]) == (5, True, None)


@pytest.mark.parametrize(
    "run_rc, reason",
    [
        (1, "세션 상태 FAILED"),
        # 143 은 러너가 «정상 정지» 로 보는 코드지만(NORMAL_END_RCS) 누적 판정은 0 만
        # 깨끗으로 본다 — 숨지 않고 그 rc 가 사유로 찍힌다.
        (143, "런타임 종료 rc=143 (깨끗은 [0])"),
        (None, "세션 상태 NOT-BOOTED"),
    ],
)
def test_a_session_that_did_not_end_with_a_clean_rc_is_not_counted(
    streak_state: Path, streak_cfg: sb.BoardConfig, run_rc: int | None, reason: str
):
    shutil.rmtree(streak_state / "cp3-sessions" / "long-20261008")
    _mk_session(streak_state, "long", dt.date(2026, 10, 8), run_rc=run_rc)
    long = _streak(_board(streak_cfg, D1012), "long")
    assert (long["days"], long["broke_on"], long["broke_reason"]) == (
        4,
        "2026-10-08",
        reason,
    )


def test_a_missing_b3_status_is_not_counted_and_the_summary_is_not_read(
    streak_state: Path, streak_cfg: sb.BoardConfig
):
    """**fail-closed 방향.** 실행 기록이 없으면 B3 가 돌았다는 근거가 없다.

    구체 입력: 10-08 에 ``b3/status.json`` 이 없고 깨끗한 v3 summary 만 있다. 그 summary
    가 이 세션의 것이라는 근거는 없으므로(#1000) 그 하루는 세지 않는다.
    """
    shutil.rmtree(streak_state / "cp3-sessions" / "long-20261008")
    _mk_session(streak_state, "long", dt.date(2026, 10, 8), write_status=False)
    long = _streak(_board(streak_cfg, D1012), "long")
    assert (long["days"], long["broke_on"]) == (4, "2026-10-08")
    assert long["broke_reason"] == "B3 실행 기록 없음 (b3/status.json)"


@pytest.mark.parametrize(
    "fields, needle",
    [
        ({"verdict": "failed", "stage": "b1a-fields", "reason": "exited 2"}, "failed"),
        ({"verdict": "skipped", "reason": "markets 에 없다"}, "skipped"),
        ({"status_schema_version": 9}, "B3 실행 기록을 읽을 수 없다"),
    ],
)
def test_a_b3_run_that_is_not_ok_is_not_counted(
    streak_state: Path, streak_cfg: sb.BoardConfig, fields: dict, needle: str
):
    shutil.rmtree(streak_state / "cp3-sessions" / "long-20261008")
    _mk_session(streak_state, "long", dt.date(2026, 10, 8), status_fields=fields)
    long = _streak(_board(streak_cfg, D1012), "long")
    assert (long["days"], long["broke_on"]) == (4, "2026-10-08")
    assert needle in long["broke_reason"]


def test_reaching_the_target_stops_the_walk(
    streak_state: Path, streak_cfg: sb.BoardConfig
):
    """목표에 닿으면 더 걷지 않는다 — 그 앞의 깨진 날은 판정하지 않는다.

    구체 입력: 깨끗한 다섯 거래일 앞(10-01)에 LOST 세션. 목표가 10-02 에서 채워지므로
    10-01 은 읽지 않고, 「마지막 깨진 거래일」도 비어 있다.
    """
    _mk_session(streak_state, "long", dt.date(2026, 10, 1), run_rc=None, booted=True)
    long = _streak(_board(streak_cfg, D1012), "long")
    assert (long["days"], long["met"], long["broke_on"]) == (5, True, None)
    assert long["window_start"] == "2026-10-02"


def test_the_board_date_is_pending_until_it_settles(
    streak_state: Path, streak_cfg: sb.BoardConfig
):
    """진행 중인 오늘은 깨끗도 아니고 깨짐도 아니다 — 아니면 장중에는 늘 오늘이 깨진 날이 된다.

    구체 입력: 오늘(10-12) 세션이 END 줄 없이 돌고 있고 그 앞 네 거래일이 깨끗하다.
    오늘은 보류로 두고 10-08 부터 센다 → 4. 보류는 **상태판 날짜에만** 쓰므로 같은 모양이
    어제의 것이면 그대로 깨진 날로 적힌다(위 rc=None 케이스).
    """
    shutil.rmtree(streak_state / "cp3-sessions" / "long-20261012")
    _mk_session(streak_state, "long", D1012, run_rc=None, write_status=False)
    long = _streak(_board(streak_cfg, D1012, today=D1012), "long")
    assert (long["days"], long["start"]) == (4, "2026-10-02")
    assert long["pending"] == "세션 NOT-BOOTED"
    assert long["broke_on"] == "2026-10-01"


def test_a_b3_still_running_on_the_board_date_is_pending_not_a_break(
    streak_state: Path, streak_cfg: sb.BoardConfig
):
    shutil.rmtree(streak_state / "cp3-sessions" / "long-20261012")
    _mk_session(
        streak_state,
        "long",
        D1012,
        status_fields={"verdict": "running"},
        write_summary=False,
    )
    long = _streak(_board(streak_cfg, D1012, today=D1012), "long")
    assert long["pending"] == "B3 대조 진행 중"
    assert long["days"] == 4


def test_only_the_days_inside_the_window_are_counted(
    streak_state: Path, tmp_path: Path
):
    """창 밖의 깨끗한 날은 세지 않는다 — 누적은 «최근 N 달력일» 안의 수다.

    구체 입력: 창을 11 달력일(10-02 까지)로, 목표를 6 으로 좁히고 10-01 에 깨끗한 세션을
    하나 더 둔다. 그 하루는 창 밖이므로 6 번째로 세지 않는다.
    """
    _mk_session(streak_state, "long", dt.date(2026, 10, 1))
    config = tmp_path / "board.yaml"
    config.write_text(
        sb.DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
        .replace("window_days: 40", "window_days: 11")
        .replace("target_days: 5", "target_days: 6"),
        encoding="utf-8",
    )
    cfg = replace(sb.load_config(config), state_dir=streak_state)
    board = _board(cfg, D1012)
    long = _streak(board, "long")
    assert (long["days"], long["met"], long["window_start"]) == (5, False, "2026-10-02")
    assert (long["broke_on"], long["error"]) == (None, None)
    assert "센 창 2026-10-02 ~ 2026-10-12" in sb.render_text(board)


def test_a_calendar_that_cannot_be_read_is_a_warning_not_a_guess(
    streak_state: Path, tmp_path: Path
):
    """거래일을 모르면 세지 않고 그 사실을 올린다 — 「주말 빼고 다 거래일」로 추측하지 않는다."""
    config = tmp_path / "board.yaml"
    config.write_text(
        sb.DEFAULT_CONFIG_PATH.read_text(encoding="utf-8").replace(
            "config/tos_runtime/cp3-setup-d-long/calendar.yaml",
            str(tmp_path / "gone.yaml"),
        ),
        encoding="utf-8",
    )
    cfg = replace(sb.load_config(config), state_dir=streak_state)
    board = _board(cfg, D1012)
    long = _streak(board, "long")
    assert (long["days"], long["broke_on"]) == (0, None)
    assert "FileNotFoundError" in long["error"]
    assert any(
        "streak/long: 깨끗한 거래일을 셀 수 없다" in i for i in _issues(board, sb.WARN)
    )


def test_a_date_outside_the_declared_years_stops_the_walk_without_guessing(
    streak_state: Path, tmp_path: Path
):
    """선언된 해를 벗어나면 그 날이 거래일인지 모른다 — 센 수는 하한으로 남긴다."""
    config = tmp_path / "board.yaml"
    config.write_text(
        sb.DEFAULT_CONFIG_PATH.read_text(encoding="utf-8").replace(
            "calendar_covered_years: [2026]", "calendar_covered_years: [2027]"
        ),
        encoding="utf-8",
    )
    cfg = replace(sb.load_config(config), state_dir=streak_state)
    long = _streak(_board(cfg, D1012), "long")
    assert (long["days"], long["broke_on"]) == (0, None)
    assert "covers [2027]; 2026-10-12 is outside it" in long["error"]


def test_the_clean_day_section_is_rendered_with_its_window(streak_cfg: sb.BoardConfig):
    text = sb.render_text(_board(streak_cfg, D1012))
    for needle in (
        "■ 깨끗한 거래일 누적 (창 40일 · 목표 5 거래일 · 끝난 거래일만 · 연속 아님",
        "long       5/5 ✔ 목표 충족 · 가장 오래된 깨끗한 날 2026-10-02",
        "센 창 2026-10-02 ~ 2026-10-12",
        "cp3-setup-d-long/calendar.yaml (krx-2026.11)",
    ):
        assert needle in text, needle


def test_the_clean_day_count_does_not_change_the_board_verdict(
    streak_state: Path, streak_cfg: sb.BoardConfig
):
    """목표를 채우는 동안 수가 작은 것은 소견이 아니다 — 종료 코드를 건드리지 않는다."""
    shutil.rmtree(streak_state / "cp3-sessions" / "long-20261007")
    board = _board(streak_cfg, D1012)
    assert _streak(board, "long")["met"] is False
    assert not any(i["where"].startswith("streak/") for i in board["issues"]), board[
        "issues"
    ]


def test_a_datetime_holiday_in_the_tenant_calendar_is_not_counted_as_a_trading_day(
    streak_state: Path, tmp_path: Path
):
    """review-1003 MEDIUM, 상태판 쪽. 거래일을 모르면 세지 않고 «확인» 을 올린다."""
    calendar = tmp_path / "calendar.yaml"
    calendar.write_text(
        (sb.REPO_ROOT / "config/tos_runtime/cp3-setup-d-long/calendar.yaml")
        .read_text(encoding="utf-8")
        .replace('  - "2026-10-09"', "  - 2026-10-09 00:00:00"),
        encoding="utf-8",
    )
    config = tmp_path / "board.yaml"
    config.write_text(
        sb.DEFAULT_CONFIG_PATH.read_text(encoding="utf-8").replace(
            "config/tos_runtime/cp3-setup-d-long/calendar.yaml", str(calendar)
        ),
        encoding="utf-8",
    )
    cfg = replace(sb.load_config(config), state_dir=streak_state)
    board = _board(cfg, D1012)
    long = _streak(board, "long")
    assert (long["days"], long["broke_on"]) == (0, None)
    assert "2026-10-09 00:00:00" in long["error"]
    assert any(
        "streak/long: 깨끗한 거래일을 셀 수 없다" in i for i in _issues(board, sb.WARN)
    )
