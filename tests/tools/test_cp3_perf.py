"""``tools/tos_cp3/perf.py`` — `sts tos perf` (종목·날짜별 체결·손익)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from tools.tos_cp3 import inspect_session as insp
from tools.tos_cp3 import perf
from tools.tos_cp3 import session_inputs as si

EVIDENCE_COLUMNS_SQL = (
    "CREATE TABLE entries (seq INTEGER PRIMARY KEY, segment_id TEXT, kind TEXT NOT NULL,"
    " record_class TEXT NOT NULL, runtime_identity_json TEXT, payload_json TEXT NOT NULL,"
    " entry_digest TEXT NOT NULL, chain_digest TEXT NOT NULL,"
    " key_generation INTEGER NOT NULL, appended_at_monotonic_ns INTEGER NOT NULL)"
)

SYMBOL = "005930"
ACCOUNT = "5020591501"
PRICE_SCALE = 100


def _seal(attempt: str, side: str, price_krw: int, quantity: int = 1) -> dict[str, Any]:
    """하나의 ``SEND_SEALED`` — 실 잎이 적는 모양 그대로(지정가는 ×price_scale)."""
    return {
        "kind": "SEND_SEALED",
        "send_seal": {
            "attempt_id": attempt,
            "action": "NEW_ORDER",
            "outbound_side": side,
            "outbound_quantity": str(quantity),
            "outbound_price": str(price_krw * PRICE_SCALE),
            "instrument_key": {"account": ACCOUNT, "instrument": SYMBOL},
        },
    }


def _ack(attempt: str, odno: str, date: str | None) -> dict[str, Any]:
    return {
        "kind": "EGRESS_RESULT_CONSUMED",
        "attempt_id": attempt,
        "broker_execution_id": odno,
        "egress_result_kind": "ACK",
        "knowledge": "ACKNOWLEDGED",
        "trading_date": date,
    }


def _fill(
    attempt: str,
    odno: str,
    date: str,
    quantity: int = 1,
    *,
    executed_krw: int | None = None,
) -> dict[str, Any]:
    """하나의 ``FILL_OBSERVED``. ``executed_krw`` 를 빼면 그 필드가 생기기 전의 행 모양."""
    row = {
        "attempt_id": attempt,
        "broker_execution_id": odno,
        "trading_date": date,
        "kind": "FULL_FILL",
        "filled_quantity": str(quantity),
        "remaining_quantity": "0",
        "reason": "filled",
    }
    if executed_krw is not None:
        row["avg_execution_price"] = str(executed_krw)
        row["executed_amount"] = str(executed_krw * quantity)
    return row


def _write_leaf(leaf: Path, rows: list[tuple[str, dict[str, Any]]]) -> Path:
    """``rows`` 를 그 순서대로 담은 evidence 저장소 하나."""
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


def _policy() -> tuple[str, dict[str, Any]]:
    return ("VENUE_POLICY_BOUND", {"price_scale": PRICE_SCALE})


def _round_trip_rows(*, executed: bool = True) -> list[tuple[str, dict[str, Any]]]:
    """2026-11-17 왕복 한 번 — 지정가 193,400 에 내서 **193,300 에 체결**, 192,200 에 매도."""
    buy_fill = 193_300 if executed else None
    sell_fill = 192_200 if executed else None
    return [
        _policy(),
        ("SEND_SEALED", _seal("attempt-buy", "BUY", 193_400)),
        ("EGRESS_RESULT_CONSUMED", _ack("attempt-buy", "0000008082", "20261117")),
        (
            "FILL_OBSERVED",
            _fill("attempt-buy", "0000008082", "20261117", executed_krw=buy_fill),
        ),
        ("SEND_SEALED", _seal("attempt-sell", "SELL", 192_200)),
        ("EGRESS_RESULT_CONSUMED", _ack("attempt-sell", "0000010650", "20261117")),
        (
            "FILL_OBSERVED",
            _fill("attempt-sell", "0000010650", "20261117", executed_krw=sell_fill),
        ),
    ]


@pytest.fixture
def round_trip_leaf(tmp_path: Path) -> Path:
    return _write_leaf(tmp_path / "leaf" / SYMBOL, _round_trip_rows())


GOLDEN_ROUND_TRIP = """\
sts tos perf — 종목·날짜별 체결·손익 (읽기 전용)

가격 기준: EXECUTION_PRICE_WITH_SEALED_FALLBACK
  체결가는 FILL_OBSERVED 의 avg_execution_price — 브로커의 평균 체결가다
    (tos/runtime/src/tos_runtime/posttrade/fill_observer.py::_emit).
  그 값은 브로커가 찍은 원 단위 정수다 — price_scale 로 나누지 않는다.
  그 키가 없는 체결은 SEND_SEALED 의 send_seal.outbound_price —
    보낸 주문의 지정가(ORD_UNPR × price_scale) — 로 떨어진다.
  손익에 «*» 가 붙은 줄은 그 지정가가 섞여 있다는 뜻이다.

집계 규칙:
  손익은 수수료·세금·슬리피지 전이다 — 증거에 그 값이 없다.
  왕복·승은 FIFO 로 닫힌 lot 조각마다 센다 — 매수 둘을 한 번에 턴 매도는 왕복 2 다.

읽은 잎:
  005930   {leaf}  (price_scale=100, 체결 2건)

종목      날짜         매수   매도   매수량   매도량   보유   왕복    승            손익
005930    20261117        1      1        1        1      0      1     0          -1,100
005930    합계            1      1        1        1      0      1     0          -1,100
"""


def test_round_trip_renders_the_golden_table(round_trip_leaf: Path) -> None:
    """한 왕복의 표 전체 — 칸·정렬·가격 기준 문단까지 고정한다."""
    text, code = perf.run(leaf_paths=(str(round_trip_leaf),))

    assert text == GOLDEN_ROUND_TRIP.format(leaf=round_trip_leaf)
    assert code == 0


def test_round_trip_json_counts_the_loss_at_the_execution_price(
    round_trip_leaf: Path,
) -> None:
    """손익은 체결가 기준(−1,100)이고, JSON 이 그 기준을 이름으로 말한다."""
    text, _ = perf.run(leaf_paths=(str(round_trip_leaf),), as_json=True)
    document = json.loads(text)

    assert document["price_basis"]["basis"] == perf.PRICE_BASIS
    assert document["price_basis"]["execution_price_in_evidence"] is True
    (symbol,) = document["symbols"]
    assert symbol["days"] == [
        {
            "date": "20261117",
            "buy_fills": 1,
            "sell_fills": 1,
            "quantity_bought": "1",
            "quantity_sold": "1",
            "closed_round_trips": 1,
            "wins": 0,
            "pnl_krw": "-1100",
            "pnl_basis": perf.BASIS_EXECUTION,
            "open_quantity_end": "0",
        }
    ]
    assert symbol["totals"]["pnl_krw"] == "-1100"
    assert symbol["totals"]["pnl_basis"] == perf.BASIS_EXECUTION
    assert symbol["totals"]["open_quantity"] == "0"
    assert symbol["open_lots"] == []
    assert symbol["unresolved_attempts"] == []


def test_a_leaf_without_the_price_keys_falls_back_to_the_sealed_order_price(
    tmp_path: Path,
) -> None:
    """체결가가 생기기 전에 기록된 잎 — 같은 왕복이 지정가 기준 −1,200 이고, 그렇다고 말한다."""
    leaf = _write_leaf(tmp_path / "leaf" / SYMBOL, _round_trip_rows(executed=False))

    text, _ = perf.run(leaf_paths=(str(leaf),))
    document = json.loads(perf.run(leaf_paths=(str(leaf),), as_json=True)[0])

    assert document["price_basis"]["execution_price_in_evidence"] is False
    (symbol,) = document["symbols"]
    assert symbol["days"][0]["pnl_krw"] == "-1200"
    assert symbol["days"][0]["pnl_basis"] == perf.BASIS_ORDER_PRICE
    assert symbol["totals"]["pnl_basis"] == perf.BASIS_ORDER_PRICE
    assert f"-1,200{perf.FALLBACK_MARK}" in text


@pytest.mark.parametrize(
    "value",
    ["NaN", "sNaN", "Infinity", "-Infinity", "0", "-1"],
    ids=["nan", "snan", "infinity", "negative-infinity", "zero", "negative"],
)
def test_an_uncomparable_or_nonpositive_execution_price_falls_back(
    tmp_path: Path, value: str
) -> None:
    """``Decimal("NaN") > 0`` 은 ``False`` 가 아니라 ``InvalidOperation`` 을 던진다."""
    rows = _round_trip_rows()
    rows[3][1]["avg_execution_price"] = value

    leaf = _write_leaf(tmp_path / "leaf" / SYMBOL, rows)

    text, code = perf.run(leaf_paths=(str(leaf),))
    document = json.loads(perf.run(leaf_paths=(str(leaf),), as_json=True)[0])

    assert code == 0
    (symbol,) = document["symbols"]
    assert symbol["days"][0]["pnl_krw"] == "-1200"
    assert symbol["days"][0]["pnl_basis"] == perf.BASIS_MIXED
    assert f"-1,200{perf.FALLBACK_MARK}" in text


def test_a_round_trip_that_mixes_both_prices_says_mixed(tmp_path: Path) -> None:
    """한 다리만 체결가가 있으면 그 날의 기준은 «섞임» 이고 표에 표시가 붙는다."""
    rows = [
        _policy(),
        ("SEND_SEALED", _seal("attempt-buy", "BUY", 193_400)),
        (
            "FILL_OBSERVED",
            _fill("attempt-buy", "0000008082", "20261117", executed_krw=193_300),
        ),
        ("SEND_SEALED", _seal("attempt-sell", "SELL", 192_200)),
        ("FILL_OBSERVED", _fill("attempt-sell", "0000010650", "20261117")),
    ]
    leaf = _write_leaf(tmp_path / "leaf" / SYMBOL, rows)

    text, _ = perf.run(leaf_paths=(str(leaf),))
    document = json.loads(perf.run(leaf_paths=(str(leaf),), as_json=True)[0])

    (symbol,) = document["symbols"]
    assert symbol["days"][0]["pnl_krw"] == "-1100"
    assert symbol["days"][0]["pnl_basis"] == perf.BASIS_MIXED
    assert f"-1,100{perf.FALLBACK_MARK}" in text


def test_a_profitable_round_trip_counts_a_win(tmp_path: Path) -> None:
    """이긴 왕복은 승 1 — 지는 쪽만 세고 있지 않다는 것을 고정한다."""
    rows = [
        _policy(),
        ("SEND_SEALED", _seal("attempt-buy", "BUY", 100_000)),
        ("FILL_OBSERVED", _fill("attempt-buy", "0000000001", "20261118")),
        ("SEND_SEALED", _seal("attempt-sell", "SELL", 101_500)),
        ("FILL_OBSERVED", _fill("attempt-sell", "0000000002", "20261118")),
    ]
    leaf = _write_leaf(tmp_path / "leaf" / SYMBOL, rows)

    text, _ = perf.run(leaf_paths=(str(leaf),), as_json=True)

    (symbol,) = json.loads(text)["symbols"]
    assert symbol["totals"]["wins"] == 1
    assert symbol["totals"]["pnl_krw"] == "1500"
    assert symbol["totals"]["pnl_basis"] == perf.BASIS_ORDER_PRICE


def test_an_acked_order_with_no_fill_observation_is_reported_unresolved(
    tmp_path: Path,
) -> None:
    """ACK 만 받고 체결 관측이 없는 주문은 체결로도 0 으로도 세지 않는다."""
    rows = [
        _policy(),
        ("SEND_SEALED", _seal("attempt-orphan", "BUY", 215_500)),
        ("EGRESS_RESULT_CONSUMED", _ack("attempt-orphan", "0000007012", None)),
        (
            "FILL_OBSERVER_ACK_UNTRACKABLE",
            {
                "attempt_id": "attempt-orphan",
                "broker_execution_id": "0000007012",
                "reason": "no_trading_date",
            },
        ),
    ]
    leaf = _write_leaf(tmp_path / "leaf" / SYMBOL, rows)

    text, code = perf.run(leaf_paths=(str(leaf),))
    document = json.loads(perf.run(leaf_paths=(str(leaf),), as_json=True)[0])

    (symbol,) = document["symbols"]
    assert symbol["days"] == []
    assert symbol["totals"]["buy_fills"] == 0
    (unresolved,) = symbol["unresolved_attempts"]
    assert unresolved["status"] == perf.STATUS_UNRESOLVED
    assert unresolved["broker_execution_id"] == "0000007012"
    assert unresolved["ack_untrackable_reason"] == "no_trading_date"
    assert unresolved["order_price_krw"] == "215500"
    assert "미해결 BUY 1주" in text
    assert "odno=0000007012" in text
    assert code == 0


def test_a_cancelled_order_that_partially_filled_says_so(tmp_path: Path) -> None:
    """#1120 MEDIUM-1: BUY 2 · 부분 체결 1 · 취소 — 계좌에는 1주가 남는다."""
    rows = [
        _policy(),
        ("SEND_SEALED", _seal("attempt-partial", "BUY", 193_400, quantity=2)),
        ("EGRESS_RESULT_CONSUMED", _ack("attempt-partial", "0000008200", "20261118")),
        (
            "FILL_OBSERVED",
            {
                "attempt_id": "attempt-partial",
                "broker_execution_id": "0000008200",
                "trading_date": "20261118",
                "kind": "PARTIAL_FILL",
                "filled_quantity": "1",
                "remaining_quantity": "1",
                "reason": "partially_filled",
            },
        ),
        (
            "EGRESS_RESULT_CONSUMED",
            {
                "attempt_id": "attempt-partial",
                "broker_execution_id": "0000008200",
                "egress_result_kind": "CANCEL_ACK",
                "trading_date": "20261118",
            },
        ),
    ]
    leaf = _write_leaf(tmp_path / "leaf" / SYMBOL, rows)

    text, code = perf.run(leaf_paths=(str(leaf),))
    document = json.loads(perf.run(leaf_paths=(str(leaf),), as_json=True)[0])

    assert code == 0
    (symbol,) = document["symbols"]
    assert symbol["days"] == []
    (attempt,) = symbol["unresolved_attempts"]
    assert attempt["status"] == perf.STATUS_NO_FILL
    assert attempt["partial_filled_quantity"] == "1"
    assert "비체결 종료 BUY 2주" in text
    assert "부분 체결 1주 관측" in text
    assert "체결 관측 없음" not in text


def test_a_broker_fill_the_engine_did_not_hold_is_named_as_such(tmp_path: Path) -> None:
    """#1120 MEDIUM-2: ENGINE_RESERVATION_ABSENT{FULL_FILL} 은 «체결 관측 없음» 이 아니다."""
    rows = [
        _policy(),
        ("SEND_SEALED", _seal("attempt-absent", "BUY", 193_400)),
        ("EGRESS_RESULT_CONSUMED", _ack("attempt-absent", "0000008300", "20261118")),
        (
            "FILL_OBSERVER_ENGINE_RESERVATION_ABSENT",
            {
                "attempt_id": "attempt-absent",
                "broker_execution_id": "0000008300",
                "trading_date": "20261118",
                "kind": "FULL_FILL",
                "filled_quantity": "1",
                "remaining_quantity": "0",
                "reason": "filled",
            },
        ),
    ]
    leaf = _write_leaf(tmp_path / "leaf" / SYMBOL, rows)

    text, _ = perf.run(leaf_paths=(str(leaf),))
    document = json.loads(perf.run(leaf_paths=(str(leaf),), as_json=True)[0])

    (symbol,) = document["symbols"]
    (attempt,) = symbol["unresolved_attempts"]
    assert attempt["engine_reservation_absent"]["kind"] == "FULL_FILL"
    assert "브로커 체결 관측 · 엔진 미보유(FULL_FILL 1주)" in text
    assert "체결 관측 없음" not in text


def test_a_cancel_hold_is_named_as_the_cause(tmp_path: Path) -> None:
    """#1120 MEDIUM-2: FILL_OBSERVER_CANCEL_UNSUPPORTED 도 사유로 읽힌다."""
    rows = [
        _policy(),
        ("SEND_SEALED", _seal("attempt-cancel", "BUY", 193_400)),
        ("EGRESS_RESULT_CONSUMED", _ack("attempt-cancel", "0000008400", "20261118")),
        (
            "FILL_OBSERVER_CANCEL_UNSUPPORTED",
            {
                "attempt_id": "attempt-cancel",
                "broker_execution_id": "0000008400",
                "trading_date": "20261118",
                "reason": "cancelled_at_broker",
                "observed_rows": [],
            },
        ),
    ]
    leaf = _write_leaf(tmp_path / "leaf" / SYMBOL, rows)

    text, _ = perf.run(leaf_paths=(str(leaf),))
    document = json.loads(perf.run(leaf_paths=(str(leaf),), as_json=True)[0])

    (symbol,) = document["symbols"]
    (attempt,) = symbol["unresolved_attempts"]
    assert attempt["cancel_unsupported_reason"] == "cancelled_at_broker"
    assert attempt["trading_date"] == "20261118"
    assert "사유 취소 보류(cancelled_at_broker)" in text


def test_the_same_leaf_twice_is_counted_once(round_trip_leaf: Path) -> None:
    """#1120 LOW: 같은 잎을 두 번 주면 체결이 두 번 집계됐다 — resolve 한 경로로 지운다."""
    once = json.loads(perf.run(leaf_paths=(str(round_trip_leaf),), as_json=True)[0])
    twice = json.loads(
        perf.run(
            leaf_paths=(str(round_trip_leaf), str(round_trip_leaf) + "/."),
            as_json=True,
        )[0]
    )

    assert len(twice["leaves"]) == 1
    assert twice["symbols"] == once["symbols"]
    assert twice["symbols"][0]["totals"]["pnl_krw"] == "-1100"


def test_a_leaf_whose_symbol_is_unknown_is_not_named_after_its_directory(
    tmp_path: Path,
) -> None:
    """#1120 LOW: 보관된 잎의 디렉터리 이름은 운영자 라벨이지 종목이 아니다."""
    rows = [
        _policy(),
        ("FILL_OBSERVED", _fill("attempt-orphan-fill", "0000011111", "20261118")),
    ]
    leaf = _write_leaf(tmp_path / "005930.stuck-20261105" / "005930.pre-r4", rows)

    text, _ = perf.run(leaf_paths=(str(leaf),))
    document = json.loads(perf.run(leaf_paths=(str(leaf),), as_json=True)[0])

    (symbol,) = document["symbols"]
    assert symbol["symbol"] == perf.UNKNOWN_SYMBOL
    assert "005930.pre-r4 집계 못 한 체결" not in text
    assert f"{perf.UNKNOWN_SYMBOL} 집계 못 한 체결 1주" in text


def test_the_data_parent_suffix_is_the_inspect_sessions_own(tmp_path: Path) -> None:
    """#1120 LOW: 규약은 한 곳에만 있다 — 두 도구가 다른 디렉터리를 보면 둘 다 조용히 빈다."""
    assert perf.TENANT_DATA_PARENT_SUFFIX is insp.TENANT_DATA_PARENT_SUFFIX


def test_a_rejected_order_is_not_unresolved(tmp_path: Path) -> None:
    """거부로 끝난 주문은 «모름» 이 아니다 — 안 채워진 것을 안다."""
    rows = [
        _policy(),
        ("SEND_SEALED", _seal("attempt-reject", "BUY", 193_400)),
        (
            "EGRESS_RESULT_CONSUMED",
            {
                "attempt_id": "attempt-reject",
                "broker_execution_id": "0000009999",
                "egress_result_kind": "REJECT",
                "trading_date": "20261117",
            },
        ),
    ]
    leaf = _write_leaf(tmp_path / "leaf" / SYMBOL, rows)

    document = json.loads(perf.run(leaf_paths=(str(leaf),), as_json=True)[0])

    (symbol,) = document["symbols"]
    assert symbol["unresolved_attempts"] == []
    assert symbol["days"] == []


def _uncertain(attempt: str, side: str) -> tuple[str, dict[str, Any]]:
    """HTTP 500 으로 주문번호 없이 돌아온 전송의 ``EGRESS_RESULT_CONSUMED``."""
    return (
        "EGRESS_RESULT_CONSUMED",
        {
            "attempt_id": attempt,
            "egress_result_kind": "UNKNOWN",
            "knowledge": "UNKNOWN",
            "trading_date": "20261123",
            "sealed_side": side,
        },
    )


def _reconciled(
    attempt: str,
    outcome: str,
    *,
    odno: str | None = None,
    candidates: tuple[str, ...] = (),
) -> tuple[str, dict[str, Any]]:
    """하나의 ``UNCERTAIN_SEND_RECONCILED`` — 런타임이 적는 모양 그대로."""
    return (
        "UNCERTAIN_SEND_RECONCILED",
        {
            "attempt_id": attempt,
            "outcome": outcome,
            "broker_execution_id": odno,
            "trading_date": "20261123",
            "sealed_side": "BUY",
            "sealed_quantity": "1",
            "candidate_order_ids": list(candidates),
            "candidate_order_times": [],
            "discarded_order_ids": [],
            "discarded_order_times": [],
            "settle_ms": 30000,
            "send_started_time": "102007",
            "ord_tmd_tolerance_s": 5,
            "foreign_min_age_s": 120,
        },
    )


def _discarded_unsent(attempt: str, reason: str) -> tuple[str, dict[str, Any]]:
    return (
        "RESERVATION_DISCARDED_UNSENT",
        {"attempt_id": attempt, "proposal_id": "prop-1", "reason": reason},
    )


def test_a_send_the_broker_never_accepted_is_not_unresolved(tmp_path: Path) -> None:
    """2026-11-23 세 잎 그대로 — KIS 500 → 재조회가 «미접수» 로 닫은 전송은 «미해결» 이 아니다."""
    rows = [
        _policy(),
        ("SEND_SEALED", _seal("attempt-500", "BUY", 175_800)),
        _uncertain("attempt-500", "BUY"),
        _reconciled("attempt-500", "never_accepted"),
        _discarded_unsent("attempt-500", "UNCERTAIN_SEND_NEVER_ACCEPTED"),
    ]
    leaf = _write_leaf(tmp_path / "leaf" / SYMBOL, rows)

    text, code = perf.run(leaf_paths=(str(leaf),))
    document = json.loads(perf.run(leaf_paths=(str(leaf),), as_json=True)[0])

    assert code == 0
    (symbol,) = document["symbols"]
    assert symbol["days"] == []
    (attempt,) = symbol["unresolved_attempts"]
    assert attempt["status"] == perf.STATUS_NO_FILL
    assert attempt["uncertain_send_outcome"] == perf.RECONCILED_NEVER_ACCEPTED
    assert attempt["discarded_unsent_reason"] == "UNCERTAIN_SEND_NEVER_ACCEPTED"
    assert "비체결 종료 BUY 1주" in text
    assert "미접수(마지막 결과 UNKNOWN → 재조회로 확인)" in text
    assert "전송되지 않음(체결 없음)" in text
    assert "미해결" not in text
    assert "체결 관측 없음" not in text


def test_a_discard_without_a_verdict_is_still_terminal(tmp_path: Path) -> None:
    """재조회 행 없이 ``RESERVATION_DISCARDED_UNSENT`` 만 있어도 보내지 못한 주문이다."""
    rows = [
        _policy(),
        ("SEND_SEALED", _seal("attempt-refused", "SELL", 245_500)),
        _uncertain("attempt-refused", "SELL"),
        _discarded_unsent("attempt-refused", "SEND_REFUSED_BEFORE_TRANSPORT"),
    ]
    leaf = _write_leaf(tmp_path / "leaf" / SYMBOL, rows)

    text, _ = perf.run(leaf_paths=(str(leaf),))
    document = json.loads(perf.run(leaf_paths=(str(leaf),), as_json=True)[0])

    (symbol,) = document["symbols"]
    (attempt,) = symbol["unresolved_attempts"]
    assert attempt["status"] == perf.STATUS_NO_FILL
    assert attempt["uncertain_send_outcome"] is None
    assert "미전송 종료(SEND_REFUSED_BEFORE_TRANSPORT)" in text
    assert "미해결" not in text


def test_a_bound_uncertain_send_resolves_to_the_matched_order_id(
    tmp_path: Path,
) -> None:
    """``bound`` 는 주문이 브로커에 **있다**는 판정이다 — 미해결로 두되 그 주문번호를 적는다."""
    rows = [
        _policy(),
        ("SEND_SEALED", _seal("attempt-bound", "BUY", 175_800)),
        _uncertain("attempt-bound", "BUY"),
        _reconciled("attempt-bound", "bound", odno="0000008082"),
    ]
    leaf = _write_leaf(tmp_path / "leaf" / SYMBOL, rows)

    text, _ = perf.run(leaf_paths=(str(leaf),))
    document = json.loads(perf.run(leaf_paths=(str(leaf),), as_json=True)[0])

    (symbol,) = document["symbols"]
    (attempt,) = symbol["unresolved_attempts"]
    assert attempt["status"] == perf.STATUS_UNRESOLVED
    assert attempt["uncertain_send_outcome"] == perf.RECONCILED_BOUND
    assert attempt["broker_execution_id"] == "0000008082"
    assert attempt["trading_date"] == "20261123"
    assert "미해결 BUY 1주" in text
    assert "odno=0000008082" in text


@pytest.mark.parametrize("outcome", ["ambiguous", "unprovable_time"])
def test_an_undecided_reconciliation_stays_unresolved(
    tmp_path: Path, outcome: str
) -> None:
    """주문을 짚지 못한 판정은 아무것도 닫지 않는다 — 브로커에 살아 있을 수 있다."""
    rows = [
        _policy(),
        ("SEND_SEALED", _seal("attempt-open", "BUY", 175_800)),
        _uncertain("attempt-open", "BUY"),
        _reconciled("attempt-open", outcome, candidates=("0000008082", "0000008083")),
    ]
    leaf = _write_leaf(tmp_path / "leaf" / SYMBOL, rows)

    text, _ = perf.run(leaf_paths=(str(leaf),))
    document = json.loads(perf.run(leaf_paths=(str(leaf),), as_json=True)[0])

    (symbol,) = document["symbols"]
    (attempt,) = symbol["unresolved_attempts"]
    assert attempt["status"] == perf.STATUS_UNRESOLVED
    assert attempt["broker_execution_id"] is None
    assert "미해결 BUY 1주" in text
    assert "사유 마지막 결과 UNKNOWN" in text
    assert "체결 관측 없음(채워졌는지 모른다)" in text


def test_a_later_verdict_supersedes_the_earlier_one(tmp_path: Path) -> None:
    """런타임은 attempt 마다 **마지막** 판정을 본다 — 보류 뒤에 온 미접수가 이긴다."""
    rows = [
        _policy(),
        ("SEND_SEALED", _seal("attempt-late", "BUY", 175_800)),
        _uncertain("attempt-late", "BUY"),
        _reconciled("attempt-late", "unprovable_time"),
        _reconciled("attempt-late", "never_accepted"),
        _discarded_unsent("attempt-late", "UNCERTAIN_SEND_NEVER_ACCEPTED"),
    ]
    leaf = _write_leaf(tmp_path / "leaf" / SYMBOL, rows)

    text, _ = perf.run(leaf_paths=(str(leaf),))
    document = json.loads(perf.run(leaf_paths=(str(leaf),), as_json=True)[0])

    (symbol,) = document["symbols"]
    (attempt,) = symbol["unresolved_attempts"]
    assert attempt["uncertain_send_outcome"] == perf.RECONCILED_NEVER_ACCEPTED
    assert attempt["status"] == perf.STATUS_NO_FILL
    assert "미해결" not in text


def test_a_filled_attempt_that_was_also_discarded_still_counts(tmp_path: Path) -> None:
    """체결이 관측된 주문은 판정 행이 뒤에 붙어도 집계에 남는다 — 돈이 움직인 쪽이 이긴다."""
    rows = [
        _policy(),
        ("SEND_SEALED", _seal("attempt-filled", "BUY", 175_800)),
        ("FILL_OBSERVED", _fill("attempt-filled", "0000008082", "20261123")),
        _discarded_unsent("attempt-filled", "UNCERTAIN_SEND_NEVER_ACCEPTED"),
    ]
    leaf = _write_leaf(tmp_path / "leaf" / SYMBOL, rows)

    document = json.loads(perf.run(leaf_paths=(str(leaf),), as_json=True)[0])

    (symbol,) = document["symbols"]
    assert symbol["days"][0]["buy_fills"] == 1
    assert symbol["unresolved_attempts"] == []


def test_an_unclosed_buy_is_left_as_open_quantity(tmp_path: Path) -> None:
    """TOS 가 닫지 않은 매수는 보유 수량으로 남고, 그 사실이 표에 나온다."""
    rows = [
        _policy(),
        ("SEND_SEALED", _seal("attempt-buy", "BUY", 193_400)),
        ("FILL_OBSERVED", _fill("attempt-buy", "0000008082", "20261113")),
    ]
    leaf = _write_leaf(tmp_path / "leaf" / SYMBOL, rows)

    text, _ = perf.run(leaf_paths=(str(leaf),))
    document = json.loads(perf.run(leaf_paths=(str(leaf),), as_json=True)[0])

    (symbol,) = document["symbols"]
    assert symbol["days"][0]["open_quantity_end"] == "1"
    assert symbol["totals"]["open_quantity"] == "1"
    assert symbol["open_lots"] == [
        {
            "trading_date": "20261113",
            "side": "BUY",
            "quantity": "1",
            "order_price_krw": "193400",
            "execution_price_krw": None,
            "price_basis": perf.BASIS_ORDER_PRICE,
            "broker_execution_id": "0000008082",
            "attempt_id": "attempt-buy",
        }
    ]
    assert "보유 1주" in text


def test_a_sell_with_no_open_lot_is_reported_unmatched(tmp_path: Path) -> None:
    """대응 매수 체결이 없는 매도는 승패로 세지 않고 따로 적는다."""
    rows = [
        _policy(),
        ("SEND_SEALED", _seal("attempt-sell", "SELL", 192_200)),
        ("FILL_OBSERVED", _fill("attempt-sell", "0000010650", "20261118")),
    ]
    leaf = _write_leaf(tmp_path / "leaf" / SYMBOL, rows)

    text, _ = perf.run(leaf_paths=(str(leaf),))
    document = json.loads(perf.run(leaf_paths=(str(leaf),), as_json=True)[0])

    (symbol,) = document["symbols"]
    assert symbol["totals"]["closed_round_trips"] == 0
    assert symbol["totals"]["wins"] == 0
    assert symbol["days"][0]["open_quantity_end"] == "0"
    assert symbol["totals"]["open_quantity"] == "0"
    assert symbol["unmatched_sell_fills"] == [
        {
            "trading_date": "20261118",
            "side": "SELL",
            "quantity": "1",
            "order_price_krw": "192200",
            "execution_price_krw": None,
            "price_basis": perf.BASIS_ORDER_PRICE,
            "broker_execution_id": "0000010650",
            "attempt_id": "attempt-sell",
        }
    ]
    assert "짝 없는 매도 1주" in text


def test_a_fill_with_no_sealed_order_is_not_counted_silently(tmp_path: Path) -> None:
    """방향을 모르는 체결은 0 으로 사라지지 않고 사유와 함께 따로 나온다."""
    rows = [
        _policy(),
        ("FILL_OBSERVED", _fill("attempt-orphan-fill", "0000011111", "20261118")),
    ]
    leaf = _write_leaf(tmp_path / "leaf" / SYMBOL, rows)

    text, _ = perf.run(leaf_paths=(str(leaf),))
    document = json.loads(perf.run(leaf_paths=(str(leaf),), as_json=True)[0])

    (symbol,) = document["symbols"]
    assert symbol["days"] == []
    (stray,) = symbol["unattributed_fills"]
    assert stray["broker_execution_id"] == "0000011111"
    assert stray["reason"] == "주문 방향 모름(SEND_SEALED 없음)"
    assert "집계 못 한 체결 1주" in text


def test_fills_from_two_leaves_fold_into_one_symbol(tmp_path: Path) -> None:
    """보관된 잎과 살아 있는 잎을 함께 주면 한 종목의 한 FIFO 로 접힌다."""
    first = _write_leaf(
        tmp_path / "a" / SYMBOL,
        [
            _policy(),
            ("SEND_SEALED", _seal("attempt-buy", "BUY", 193_400)),
            ("FILL_OBSERVED", _fill("attempt-buy", "0000008082", "20261117")),
        ],
    )
    second = _write_leaf(
        tmp_path / "b" / SYMBOL,
        [
            _policy(),
            ("SEND_SEALED", _seal("attempt-sell", "SELL", 192_200)),
            ("FILL_OBSERVED", _fill("attempt-sell", "0000010650", "20261118")),
        ],
    )

    document = json.loads(
        perf.run(leaf_paths=(str(first), str(second)), as_json=True)[0]
    )

    (symbol,) = document["symbols"]
    assert [day["date"] for day in symbol["days"]] == ["20261117", "20261118"]
    assert symbol["days"][1]["pnl_krw"] == "-1200"
    assert symbol["totals"]["open_quantity"] == "0"


def test_a_leaf_with_no_order_makes_no_symbol_row(tmp_path: Path) -> None:
    """주문이 없는 잎은 종목 이름을 디렉터리에서 추측하지 않는다 — 잎 줄로만 남는다."""
    leaf = _write_leaf(tmp_path / "005930.pre-r4-poisoned" / SYMBOL, [_policy()])

    text, code = perf.run(leaf_paths=(str(leaf),))
    document = json.loads(perf.run(leaf_paths=(str(leaf),), as_json=True)[0])

    assert document["symbols"] == []
    assert document["leaves"][0]["symbol"] is None
    assert "(관측된 체결 없음)" in text
    assert code == 0


def test_discovery_finds_the_live_leaf_and_skips_the_archive(tmp_path: Path) -> None:
    """기본 탐색은 tenant 트리 → 데이터 부모의 살아 있는 잎만 본다."""
    config_dir = tmp_path / "config" / "tos_runtime"
    (config_dir / f"cp3-setup-d-stock-{SYMBOL}").mkdir(parents=True)
    (config_dir / "cp3-setup-d-long").mkdir()
    state = tmp_path / "state"
    parent = state / f"cp3-setup-d-stock-{SYMBOL}-data"
    live = _write_leaf(parent / SYMBOL, _round_trip_rows())
    _write_leaf(parent / "archive" / f"{SYMBOL}.stuck", _round_trip_rows())

    found = perf.discover_leaves(state_dir=state, config_dir=config_dir)

    assert found == [live]


def test_reading_a_leaf_writes_nothing(round_trip_leaf: Path) -> None:
    """읽기 전용 — 보고서를 내도 잎의 파일 목록과 내용이 그대로다."""
    store = round_trip_leaf / si.EVIDENCE_FILE_NAME
    before = (sorted(p.name for p in round_trip_leaf.iterdir()), store.read_bytes())

    perf.run(leaf_paths=(str(round_trip_leaf),))

    assert (
        sorted(p.name for p in round_trip_leaf.iterdir()),
        store.read_bytes(),
    ) == before


def test_an_unreadable_leaf_is_named_and_exits_one(tmp_path: Path) -> None:
    """읽히지 않는 잎은 조용히 0 건이 되지 않는다 — 사유와 함께 종료코드 1."""
    leaf = _write_leaf(tmp_path / "leaf" / SYMBOL, _round_trip_rows())
    conn = sqlite3.connect(leaf / si.EVIDENCE_FILE_NAME)
    conn.execute("PRAGMA user_version = 99")
    conn.commit()
    conn.close()

    text, code = perf.run(leaf_paths=(str(leaf),))

    assert code == 1
    assert "user_version=99" in text


def test_no_leaf_at_all_exits_one(tmp_path: Path) -> None:
    """읽을 잎이 없으면 «체결 0건» 이 아니라 거부다."""
    config_dir = tmp_path / "config" / "tos_runtime"
    config_dir.mkdir(parents=True)

    text, code = perf.run(
        state_dir=str(tmp_path / "state"), config_dir=config_dir, as_json=False
    )

    assert code == 1
    assert "(없음)" in text
