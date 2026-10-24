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
        (lambda d: d.update(summary_schema_version=3), "summary_schema_version=3"),
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


def test_n4_b3_live_divergence_is_raised_as_a_warning(cfg: sb.BoardConfig):
    assert (
        "long-20261015: B3 live divergent 26/303 — 귀속은 B3 리포트에서 확인"
        in _issues(_board(cfg, D1015), sb.WARN)
    )


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
