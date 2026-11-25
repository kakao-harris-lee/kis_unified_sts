"""``tools/tos_cp3/export_symbols.py`` — 종목별 운영 화면의 호스트 측 내보내기.

계획 ``docs/plans/2026-11-19-tos-usage-plan.md`` §5 «종목별 운영 화면».

두 가지 입력으로 본다. 하나는 ``cp3_status_board`` 녹화 픽스처(실 세션 로그 · 실
marketfeed/inbox/evidence) — 세션 상태와 차단 사유가 **실제로 기록된 모양**에서
나오는지. 다른 하나는 ``test_cp3_perf`` 와 같은 손으로 쓴 잎 — 체결 줄이 ``perf`` 의
가격 기준을 그대로 쓰는지. 실 상태 디렉터리(``~/.local/state/tos``)는 읽지 않는다.
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
import shutil
import sqlite3
import stat
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from tools.tos_cp3 import export_bars, perf
from tools.tos_cp3 import export_symbols as ex
from tools.tos_cp3 import session_inputs as si
from tools.tos_cp3 import status_board as sb

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "cp3_status_board"
LEAVES = {
    "long-A05611": "cp3-setup-d-long-data/A05611",
    "short-A05611": "cp3-setup-d-short-data/A05611",
}
D1022, D1023 = dt.date(2026, 10, 22), dt.date(2026, 10, 23)

EVIDENCE_COLUMNS_SQL = (
    "CREATE TABLE entries (seq INTEGER PRIMARY KEY, segment_id TEXT, kind TEXT NOT NULL,"
    " record_class TEXT NOT NULL, runtime_identity_json TEXT, payload_json TEXT NOT NULL,"
    " entry_digest TEXT NOT NULL, chain_digest TEXT NOT NULL,"
    " key_generation INTEGER NOT NULL, appended_at_monotonic_ns INTEGER NOT NULL)"
)

SYMBOL = "005930"
ACCOUNT = "5020591501"
PRICE_SCALE = 100
DAY = "20261117"


# --------------------------------------------------------------------------- #
# 녹화 픽스처 — 실제로 돈 세션 하나
# --------------------------------------------------------------------------- #


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
    return state


def _trees(
    root: Path,
    *declared: tuple[str, str | None],
    market: str = ex.KIND_STOCK,
    direction: str = "LONG",
) -> Path:
    """``RENDER.yaml`` 만 있는 설정 디렉터리 — tenant 목록의 유일한 출처.

    ``symbol`` 이 ``None`` 이면 ``instrument.pattern`` 을 적지 않는다 — 선물 트리의
    실제 매니페스트가 그렇다(월물은 렌더 때 정해진다).
    """
    root.mkdir(parents=True, exist_ok=True)
    for tree_id, symbol in declared:
        tree = root / tree_id
        tree.mkdir()
        instrument = "" if symbol is None else f'instrument:\n  pattern: "{symbol}"\n'
        (tree / ex.RENDER_MANIFEST_NAME).write_text(
            f'tree_id: "{tree_id}"\nmarket: "{market}"\n'
            f'direction:\n  value: "{direction}"\n{instrument}',
            encoding="utf-8",
        )
    return root


def _board(state: Path) -> sb.BoardConfig:
    config = sb.load_config()
    return sb.BoardConfig(**{**config.__dict__, "state_dir": state})


@pytest.fixture
def recorded(tmp_path: Path) -> tuple[sb.BoardConfig, Path]:
    """녹화된 두 선물 tenant — 트리 선언도 실제 매니페스트대로 ``market: futures``.

    종목을 선언하지 않는 것까지 진짜와 같다: 선물 월물은 렌더 때 정해지므로
    ``instrument.pattern`` 이 없고, 줄의 종목은 그날 돈 세션이 말한다.
    """
    state = _materialize(tmp_path)
    trees = _trees(
        tmp_path / "trees",
        ("cp3-setup-d-long", None),
        ("cp3-setup-d-short", None),
        market=ex.KIND_FUTURES,
    )
    return _board(state), trees


def _document(
    recorded: tuple[sb.BoardConfig, Path], *, day: dt.date = D1022
) -> dict[str, Any]:
    config, trees = recorded
    return ex.build_document(
        cfg=config,
        day=day,
        today=D1023,
        config_dir=trees,
        proc_root=Path("/nonexistent-proc"),
        tree_glob="cp3-setup-d-*",
    )


def test_every_declared_tenant_gets_a_row(
    recorded: tuple[sb.BoardConfig, Path],
) -> None:
    """완료 판정은 «다섯 tenant 가 한 화면» 이다 — 안 돈 트리도 줄이 나야 한다."""
    document = _document(recorded)
    assert document["schema_version"] == ex.SYMBOLS_SCHEMA_VERSION
    assert document["date"] == "2026-10-22"
    assert [row["tree_id"] for row in document["symbols"]] == [
        "cp3-setup-d-long",
        "cp3-setup-d-short",
    ]
    # 선물 트리는 종목을 선언하지 않는다 — 그날 돈 세션이 말한 월물이 줄의 종목이고,
    # 세션이 없으면 비운다. 지어낸 월물은 지난 월물일 수 있다.
    assert [row["symbol"] for row in document["symbols"]] == ["A05611", None]
    assert all(row["kind"] == ex.KIND_FUTURES for row in document["symbols"])
    assert all(row["decision_only"] is True for row in document["symbols"])
    assert all(row["direction"] == "LONG" for row in document["symbols"])


def test_a_session_that_ran_reports_its_status_and_ticks(
    recorded: tuple[sb.BoardConfig, Path],
) -> None:
    """세션 상태는 러너 로그가 말한 그대로 — 상태판의 판정 함수를 그대로 부른다."""
    row = _document(recorded)["symbols"][0]
    assert row["session"] == {
        "name": "long-20261022",
        "status": "ENDED",
        "boot_at": "08:46:18",
        "end_at": "15:50:01",
        "run_rc": 0,
    }
    assert row["ticks"] == 6


def test_a_tenant_with_no_session_today_says_so_instead_of_vanishing(
    recorded: tuple[sb.BoardConfig, Path],
) -> None:
    """«오늘 시작 안 함» 은 ``status=None`` 이다. 줄을 빼면 조용한 실패가 된다."""
    row = _document(recorded)["symbols"][1]
    assert row["tree_id"] == "cp3-setup-d-short"
    assert row["session"]["status"] is None
    assert row["session"]["name"] is None
    # 선물 트리라 잎 자리를 도출할 수 없다(종목을 선언하지 않는다). «읽었는데 0 틱»
    # 이 아니라 «읽을 잎을 모른다» 이므로 None 이고, 사유는 error 가 아니라
    # status=None 이 말한다 — 안 돈 것은 고장이 아니다.
    assert row["ticks"] is None
    assert row["error"] is None


def test_the_last_halt_is_the_recorded_one_with_its_bar_time(
    recorded: tuple[sb.BoardConfig, Path],
) -> None:
    """마지막 차단 사유와 그 봉의 KST 시각 — 녹화된 값 그대로."""
    halt = _document(recorded)["symbols"][0]["halt"]
    assert halt["error"] is None
    assert halt["last_flow"] == {
        "reason": "STAGE_DENIED",
        "step": "CANDIDATE_COMMAND_CONSTRUCTION",
        "time_kst": "15:33",
    }
    assert halt["flow_counts"] == {"STAGE_DENIED": 3}


def test_a_withholding_never_hides_the_flow_halt(
    recorded: tuple[sb.BoardConfig, Path],
) -> None:
    """보류는 장 끝 무렵 매 봉 날 수 있다. 둘을 합치면 흐름 정지가 묻힌다.

    이 녹화에서 마지막 보류(15:12)는 마지막 흐름 정지(15:33)보다 **앞**이지만, 반대인
    날이 정상이다 — 그때 하나로 합쳤다면 운영자가 봐야 할 STAGE_DENIED 가 사라진다.
    """
    halt = _document(recorded)["symbols"][0]["halt"]
    assert halt["last_withheld"] == {
        "reason": "TIME_NOT_ADMITTED",
        "step": "DECISION_WITHHELD",
        "time_kst": "15:12",
    }
    assert halt["last_flow"]["reason"] == "STAGE_DENIED"


def test_a_day_with_no_session_counts_nothing_from_other_days(
    recorded: tuple[sb.BoardConfig, Path],
) -> None:
    """잎은 날짜를 누적한다. 날짜로 자르지 않으면 어제 일이 오늘 줄에 샌다."""
    document = _document(recorded, day=dt.date(2026, 10, 21))
    for row in document["symbols"]:
        assert row["ticks"] is None
        assert row["halt"]["last_flow"] is None
        assert row["halt"]["flow_counts"] == {}
        # 판단 전용 tenant 의 체결 자리는 0 이 아니라 None 이다 — «오늘 아무 것도
        # 안 샀다» 가 아니라 «살 수 있는 자리가 아니다».
        assert row["buy"]["fills"] is None
        assert row["pnl"] is None


def test_a_stock_tenant_with_no_session_still_reads_its_declared_leaf(
    tmp_path: Path,
) -> None:
    """주식 트리는 종목을 선언하므로, 세션이 없어도 잎 자리가 도출된다.

    그 잎을 실제로 읽었다는 증거가 ``ticks == 0`` 이다 — «읽을 잎을 모른다»(None)
    와 다르다. 선물 줄이 None 을 내는 것은 트리가 월물을 선언하지 않기 때문이지,
    세션이 없어서가 아니다.
    """
    state = _materialize(tmp_path)
    trees = _trees(tmp_path / "stock-trees", ("cp3-setup-d-long", "A05611"))
    document = ex.build_document(
        cfg=_board(state),
        day=dt.date(2026, 10, 21),
        today=D1023,
        config_dir=trees,
        proc_root=Path("/nonexistent-proc"),
    )
    row = document["symbols"][0]
    assert row["kind"] == ex.KIND_STOCK
    assert row["decision_only"] is False
    assert row["session"]["status"] is None
    assert row["ticks"] == 0
    assert row["buy"]["fills"] == 0
    assert row["pnl"]["today"]["pnl_krw"] == "0"


# --------------------------------------------------------------------------- #
# 손으로 쓴 주식 잎 — 체결 줄
# --------------------------------------------------------------------------- #


def _seal(attempt: str, side: str, price_krw: int) -> dict[str, Any]:
    return {
        "kind": "SEND_SEALED",
        "send_seal": {
            "attempt_id": attempt,
            "action": "NEW_ORDER",
            "outbound_side": side,
            "outbound_quantity": "1",
            "outbound_price": str(price_krw * PRICE_SCALE),
            "instrument_key": {"account": ACCOUNT, "instrument": SYMBOL},
        },
    }


def _fill(attempt: str, odno: str, executed_krw: int) -> dict[str, Any]:
    return {
        "attempt_id": attempt,
        "broker_execution_id": odno,
        "trading_date": DAY,
        "kind": "FULL_FILL",
        "filled_quantity": "1",
        "remaining_quantity": "0",
        "reason": "filled",
        "avg_execution_price": str(executed_krw),
    }


def _write_leaf(leaf: Path, rows: list[tuple[str, dict[str, Any]]]) -> Path:
    """``test_cp3_perf`` 와 같은 모양의 evidence 저장소 하나."""
    leaf.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(leaf / si.EVIDENCE_FILE_NAME)
    conn.execute(EVIDENCE_COLUMNS_SQL)
    conn.execute(f"PRAGMA user_version = {si.PINNED_EVIDENCE_SCHEMA_VERSION}")
    for seq, (kind, payload) in enumerate(rows, start=1):
        conn.execute(
            "INSERT INTO entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                seq,
                "segment-1",
                kind,
                "ENGINE",
                None,
                json.dumps({"masked_keys": [], "payload": payload}),
                f"entry-{seq}",
                f"chain-{seq}",
                0,
                seq * 1000,
            ),
        )
    conn.commit()
    conn.close()
    return leaf


def _round_trip_leaf(leaf: Path) -> Path:
    return _write_leaf(
        leaf,
        [
            ("VENUE_POLICY_BOUND", {"price_scale": PRICE_SCALE}),
            ("SEND_SEALED", _seal("attempt-buy", "BUY", 193_400)),
            ("FILL_OBSERVED", _fill("attempt-buy", "0000008082", 193_300)),
            ("SEND_SEALED", _seal("attempt-sell", "SELL", 192_200)),
            ("FILL_OBSERVED", _fill("attempt-sell", "0000010650", 192_200)),
        ],
    )


def _row_for(leaf: Path, *, day_key: str = DAY) -> dict[str, Any]:
    return ex.symbol_row(
        ex.Tenant(
            tree_id="cp3-setup-d-stock-005930",
            symbol=SYMBOL,
            market=ex.KIND_STOCK,
            direction="LONG",
        ),
        leaf_path=leaf,
        session=None,
        day_key=day_key,
    )


def test_todays_fills_are_counted_per_side_with_perfs_price_basis(
    tmp_path: Path,
) -> None:
    """건수·수량·마지막 한 건의 가격과 기준은 ``perf`` 가 정한 것을 그대로 쓴다."""
    row = _row_for(_round_trip_leaf(tmp_path / "005930"))
    assert row["buy"]["fills"] == 1
    assert row["buy"]["quantity"] == "1"
    assert row["buy"]["last"]["execution_price_krw"] == "193300"
    assert row["buy"]["last"]["order_price_krw"] == "193400"
    assert row["buy"]["last"]["price_basis"] == perf.BASIS_EXECUTION
    assert row["buy"]["last"]["broker_execution_id"] == "0000008082"
    assert row["sell"]["fills"] == 1
    assert row["sell"]["last"]["execution_price_krw"] == "192200"


def test_a_closed_round_trip_leaves_no_holding(tmp_path: Path) -> None:
    """보유는 ``perf`` 의 FIFO 미청산 lot 이고, 기준 이름을 같이 낸다(«TOS 기준»)."""
    row = _row_for(_round_trip_leaf(tmp_path / "005930"))
    assert row["holding"] == {
        "quantity": "0",
        "lots": 0,
        "basis": ex.HOLDING_BASIS,
    }


def test_the_pnl_block_is_perfs_own_figure_not_a_second_count(
    tmp_path: Path,
) -> None:
    """손익은 ``perf.build_report`` 의 FIFO 결과 그대로다 — 여기서 다시 더하지 않는다.

    193,300 에 사서 192,200 에 판 왕복 하나 = −1,100 원, 승 0. 같은 잎에 대고
    ``perf.build_report`` 를 직접 돌린 값과 **글자 그대로** 같아야 한다: 그래야
    ``sts tos perf`` 와 화면이 같은 날에 다른 손익을 말하는 일이 없다.
    """
    leaf = _round_trip_leaf(tmp_path / "005930")
    row = _row_for(leaf)
    expected = perf.build_report([perf.read_leaf(leaf)])["symbols"][0]
    day = expected["days"][0]

    assert row["pnl"]["today"] == {
        "pnl_krw": "-1100",
        "pnl_basis": perf.BASIS_EXECUTION,
        "closed_round_trips": 1,
        "wins": 0,
        "buy_fills": 1,
        "sell_fills": 1,
        "quantity_bought": "1",
        "quantity_sold": "1",
    }
    assert row["pnl"]["today"]["pnl_krw"] == day["pnl_krw"]
    assert row["pnl"]["cumulative"]["pnl_krw"] == expected["totals"]["pnl_krw"]
    assert row["pnl"]["cumulative"]["open_lots"] == 0
    assert row["pnl"]["cumulative"]["open_quantity"] == "0"
    assert row["pnl"]["unresolved"] == {"count": 0, "attempts": []}


def test_fills_on_another_day_stay_out_of_todays_pnl_but_not_the_total(
    tmp_path: Path,
) -> None:
    """오늘 칸은 그날 닫힌 것만, 누적 칸은 전부 — 둘을 섞으면 오늘이 과장된다."""
    row = _row_for(_round_trip_leaf(tmp_path / "005930"), day_key="20261118")
    assert row["pnl"]["today"] == {
        "pnl_krw": "0",
        "pnl_basis": None,
        "closed_round_trips": 0,
        "wins": 0,
        "buy_fills": 0,
        "sell_fills": 0,
        "quantity_bought": "0",
        "quantity_sold": "0",
    }
    assert row["pnl"]["cumulative"]["pnl_krw"] == "-1100"
    assert row["pnl"]["cumulative"]["closed_round_trips"] == 1


def test_an_unresolved_attempt_carries_perfs_sentences_and_no_leaf_path(
    tmp_path: Path,
) -> None:
    """집계 밖 주문은 ``sts tos perf`` 가 쓰는 말 그대로, 잎 경로는 떼고 싣는다.

    ``perf`` 는 그 attempt 에 ``leaf`` 로 **잎의 절대 경로**를 적는다. 이 문서는
    대시보드가 그대로 브라우저에 보내므로 그 키가 새면 호스트 경로가 공개된다.
    """
    leaf = _write_leaf(
        tmp_path / "005930",
        [
            ("VENUE_POLICY_BOUND", {"price_scale": PRICE_SCALE}),
            ("SEND_SEALED", _seal("attempt-buy", "BUY", 175_800)),
            (
                "UNCERTAIN_SEND_RECONCILED",
                {
                    "attempt_id": "attempt-buy",
                    "outcome": perf.RECONCILED_NEVER_ACCEPTED,
                },
            ),
        ],
    )
    row = _row_for(leaf)
    unresolved = row["pnl"]["unresolved"]
    assert unresolved["count"] == 1
    (attempt,) = unresolved["attempts"]
    assert attempt["side"] == "BUY"
    assert attempt["quantity"] == "1"
    assert attempt["order_price_krw"] == "175800"
    assert attempt["status"] == perf.STATUS_NO_FILL
    assert attempt["status_label"] == "비체결 종료"
    assert attempt["reason"].startswith("미접수")
    assert attempt["observation"] == "전송되지 않음(체결 없음)"
    assert "leaf" not in attempt
    assert str(tmp_path) not in json.dumps(row, ensure_ascii=False)


def test_an_open_buy_is_held_until_tos_closes_it(tmp_path: Path) -> None:
    """팔지 않은 매수는 보유로 남는다 — 브로커 잔고가 아니라 TOS 원장 기준."""
    leaf = _write_leaf(
        tmp_path / "005930",
        [
            ("VENUE_POLICY_BOUND", {"price_scale": PRICE_SCALE}),
            ("SEND_SEALED", _seal("attempt-buy", "BUY", 193_400)),
            ("FILL_OBSERVED", _fill("attempt-buy", "0000008082", 193_300)),
        ],
    )
    row = _row_for(leaf)
    assert row["holding"]["quantity"] == "1"
    assert row["holding"]["lots"] == 1
    assert row["sell"]["fills"] == 0
    assert row["sell"]["last"] is None


def test_fills_from_another_day_do_not_reach_todays_row(tmp_path: Path) -> None:
    """체결은 거래일로 자른다 — 보유는 누적, 오늘 줄은 오늘 것만."""
    row = _row_for(_round_trip_leaf(tmp_path / "005930"), day_key="20261118")
    assert row["buy"]["fills"] == 0
    assert row["sell"]["fills"] == 0
    # 그래도 보유는 누적이다(이 잎은 닫힌 왕복이라 0).
    assert row["holding"]["quantity"] == "0"


def test_a_leaf_without_a_marketfeed_still_reports_its_fills(tmp_path: Path) -> None:
    """차단 사유를 못 읽어도 체결 줄은 낸다 — 하나가 없다고 나머지를 버리지 않는다."""
    row = _row_for(_round_trip_leaf(tmp_path / "005930"))
    assert row["buy"]["fills"] == 1
    assert row["halt"]["error"] is not None
    assert row["halt"]["last_flow"] is None
    assert row["ticks"] is None
    assert row["error"] is None


def test_an_unreadable_leaf_reports_unknown_pnl_not_zero(tmp_path: Path) -> None:
    """잎을 열지 못한 줄의 손익은 ``None`` 이다 — 0 원은 «오늘 본전» 으로 읽힌다."""
    leaf = tmp_path / "005930"
    leaf.mkdir()
    (leaf / "evidence.sqlite3").write_bytes(b"not a database")
    row = _row_for(leaf)
    assert row["error"] is not None
    assert row["pnl"] is None
    assert row["holding"]["quantity"] is None


def test_an_unreadable_leaf_is_a_row_with_a_reason(tmp_path: Path) -> None:
    """잎이 없으면 줄은 나고 사유만 남는다."""
    row = _row_for(tmp_path / "absent")
    assert row["error"] is not None
    assert row["buy"]["fills"] == 0
    assert row["holding"]["quantity"] is None


# --------------------------------------------------------------------------- #
# 시각의 출처 · 경로 비노출 · 목적지
# --------------------------------------------------------------------------- #


def _record(seq: int, hhmm: str) -> dict[str, Any]:
    return {
        "evidence_seq": seq,
        "raw_event_id": f"{SYMBOL}:1m:20261117T{hhmm}00+0900",
        "outcome_kind": si.PROPOSAL_KIND,
        "pipeline_halt_reason": None,
        "flow_halt_reason": None,
        "flow_halt_step": None,
        "evidence_kind": "DECISION_OUTCOME_EMITTED",
    }


def test_the_fill_time_is_the_order_bar_not_the_bar_the_fill_landed_on() -> None:
    """체결이 몇 봉 뒤에 관측돼도 시각은 **주문을 낸 봉**이다.

    구체적 입력: 14:36 봉에서 낸 주문(seal seq 79)이 14:50 봉 뒤(seq 450)에야
    관측된 체결. 체결 자신의 seq 로 봉을 찾으면 14:50 이 나오는데, 그 봉은 이 주문을
    내지 않았다. ``Fill.order_seq`` 가 있는 이유가 이것이다.
    """
    records = [_record(79, "1436"), _record(144, "1437"), _record(449, "1450")]
    fill = perf.Fill(
        leaf_order=0,
        seq=450,
        attempt_id="attempt-buy",
        broker_execution_id="0000008082",
        trading_date=DAY,
        side=perf.BUY,
        quantity=Decimal(1),
        order_price=Decimal(193_400),
        execution_price=Decimal(193_300),
        order_seq=112,
    )
    block = ex._last_fill_block(fill, records)
    assert block["time_kst"] == "14:36"
    assert block["time_basis"] == ex.ORDER_BAR_TIME_BASIS
    # 같은 체결을 체결 seq 로 찾았다면 14:50 이었을 것이다 — 그 차이가 이 테스트다.
    assert ex._bar_at_or_before(records, fill.seq) != ex._bar_at_or_before(
        records, fill.order_seq
    )


def test_a_fill_with_no_order_row_has_neither_a_time_nor_a_basis() -> None:
    """시각이 없으면 기준도 없다 — «없음» 과 «출처 불명» 이 같아 보이면 안 된다."""
    fill = perf.Fill(
        leaf_order=0,
        seq=450,
        attempt_id="attempt-buy",
        broker_execution_id="0000008082",
        trading_date=DAY,
        side=perf.BUY,
        quantity=Decimal(1),
        order_price=None,
        execution_price=Decimal(193_300),
        order_seq=None,
    )
    block = ex._last_fill_block(fill, [_record(79, "1436")])
    assert block["time_kst"] is None
    assert block["time_basis"] is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "OSError: [Errno 13] Permission denied: '/home/deploy/.local/state/x'",
            "OSError",
        ),
        ("DatabaseError: file is not a database", "DatabaseError"),
        ("/home/deploy/.local/state/tos/leaf", "UNKNOWN"),
        ("", "UNKNOWN"),
    ],
)
def test_a_read_failure_is_reduced_to_its_exception_type(
    raw: str, expected: str
) -> None:
    """사유의 뒷부분엔 잎의 절대 경로가 들어 있다. 그 문서는 브라우저로 간다."""
    assert ex._reduce_error(raw) == expected


def test_no_host_path_reaches_the_document(
    recorded: tuple[sb.BoardConfig, Path], tmp_path: Path
) -> None:
    """문서 전체에 상태 디렉터리 경로가 한 번도 나오지 않는다."""
    config, _ = recorded
    rendered = json.dumps(_document(recorded), ensure_ascii=False)
    assert str(config.state_dir) not in rendered
    assert str(tmp_path) not in rendered


def test_the_document_lands_where_the_dashboard_reads_with_narrow_modes(
    recorded: tuple[sb.BoardConfig, Path], tmp_path: Path
) -> None:
    """``export-bars`` 와 같은 목적지 규약 · 같은 권한으로 원자적으로 쓴다."""
    config, trees = recorded
    out = tmp_path / "projection"
    path = ex.export_symbols(
        out_dir=out,
        state_dir=str(config.state_dir),
        date="2026-10-22",
        config_dir=trees,
        tree_glob="cp3-setup-d-*",
        proc_root=Path("/nonexistent-proc"),
    )
    assert path == out / ex.SYMBOLS_SUBDIR / ex.DOCUMENT_NAME
    assert stat.S_IMODE(path.stat().st_mode) == export_bars.DOCUMENT_MODE
    assert stat.S_IMODE(path.parent.stat().st_mode) == export_bars.DIR_MODE
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["schema_version"] == ex.SYMBOLS_SCHEMA_VERSION
    assert [row["tree_id"] for row in document["symbols"]] == [
        "cp3-setup-d-long",
        "cp3-setup-d-short",
    ]


def test_what_the_exporter_writes_is_what_the_route_accepts(
    recorded: tuple[sb.BoardConfig, Path],
) -> None:
    """두 쪽은 파일로만 만난다 — 그래서 그 파일이 저쪽 DTO 를 통과하는지 여기서 본다.

    이것이 없으면 내보내기 쪽 키 하나를 고쳐도 아무것도 빨개지지 않고, 화면만
    조용히 빈다.
    """
    from services.dashboard.routes.tos_symbols import TosSymbolsDocument

    document = TosSymbolsDocument.model_validate(_document(recorded))
    assert document.schema_version == ex.SYMBOLS_SCHEMA_VERSION
    assert document.holding_basis == ex.HOLDING_BASIS
    assert document.symbols is not None and len(document.symbols) == 2
    first = document.symbols[0]
    assert first.session is not None and first.session.status == "ENDED"
    assert first.halt is not None and first.halt.last_flow is not None
    assert first.halt.last_flow.reason == "STAGE_DENIED"
    assert first.holding is not None and first.holding.basis == ex.HOLDING_BASIS


def _manifest(trees: Path, tree_id: str, body: str) -> Path:
    tree = trees / tree_id
    tree.mkdir(parents=True)
    (tree / ex.RENDER_MANIFEST_NAME).write_text(body, encoding="utf-8")
    return trees


def test_a_stock_tree_that_names_no_instrument_is_refused(tmp_path: Path) -> None:
    """이름 없는 종목은 줄을 만들 수 없다 — 추측한 이름으로 만든 줄은 틀린 줄이다."""
    trees = _manifest(
        tmp_path / "trees",
        "cp3-setup-d-stock-005930",
        'tree_id: "x"\nmarket: "stock"\n',
    )
    with pytest.raises(ex.ExportRefusal, match="instrument.pattern"):
        ex.discover_tenants(config_dir=trees, tree_glob="cp3-setup-d-*")


def test_a_tree_that_names_no_market_is_refused(tmp_path: Path) -> None:
    """줄의 종류를 모르면 체결 자리를 0 으로 그릴지 None 으로 그릴지 알 수 없다."""
    trees = _manifest(tmp_path / "trees", "cp3-setup-d-long", 'tree_id: "x"\n')
    with pytest.raises(ex.ExportRefusal, match="market"):
        ex.discover_tenants(config_dir=trees, tree_glob="cp3-setup-d-*")


def test_a_futures_tree_without_an_instrument_is_accepted(tmp_path: Path) -> None:
    """선물 매니페스트에는 월물이 없는 것이 정상이다 — 거부가 아니다."""
    trees = _trees(
        tmp_path / "trees",
        ("cp3-setup-d-short", None),
        market=ex.KIND_FUTURES,
        direction="SHORT",
    )
    (tenant,) = ex.discover_tenants(config_dir=trees, tree_glob="cp3-setup-d-*")
    assert tenant.symbol is None
    assert tenant.market == ex.KIND_FUTURES
    assert tenant.direction == "SHORT"


def test_the_tenant_list_comes_from_config_not_from_code(tmp_path: Path) -> None:
    """트리를 하나 더 붙인 날, 코드를 고치지 않아도 줄이 하나 더 난다."""
    trees = _trees(
        tmp_path / "trees",
        ("cp3-setup-d-stock-005930", "005930"),
        ("cp3-setup-d-stock-000660", "000660"),
        ("cp3-setup-d-stock-005380", "005380"),
    )
    tenants = ex.discover_tenants(config_dir=trees, tree_glob=perf.TENANT_TREE_GLOB)
    assert [tenant.symbol for tenant in tenants] == ["000660", "005380", "005930"]
    assert tenants[0].tree_id == "cp3-setup-d-stock-000660"


def test_the_default_glob_takes_the_futures_trees_too(tmp_path: Path) -> None:
    """기본 glob 이 주식만 훑으면 선물 둘이 조용히 화면에서 사라진다(#1178 이전)."""
    trees = _trees(tmp_path / "trees", ("cp3-setup-d-stock-005930", "005930"))
    _trees(
        trees,
        ("cp3-setup-d-long", None),
        ("cp3-setup-d-short", None),
        market=ex.KIND_FUTURES,
    )
    tenants = ex.discover_tenants(config_dir=trees)
    assert [tenant.tree_id for tenant in tenants] == [
        "cp3-setup-d-long",
        "cp3-setup-d-short",
        "cp3-setup-d-stock-005930",
    ]
    assert [tenant.market for tenant in tenants] == [
        ex.KIND_FUTURES,
        ex.KIND_FUTURES,
        ex.KIND_STOCK,
    ]
