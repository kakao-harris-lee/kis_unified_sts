"""``tools/tos_cp3/perf.py`` — `sts tos perf` (종목·날짜별 체결·손익).

계획 ``docs/plans/2026-11-19-tos-usage-plan.md`` §5 «`sts tos perf` 최소판».

이 묶음이 쥐어야 하는 것은 산술보다 «정직함» 쪽이다.

* 증거에 **체결가가 없다**. 런타임의 ``FILL_OBSERVED`` 는 체결 수량만 적고
  (``posttrade/fill_observer.py``), 브로커 주문 행 파서도 가격 필드를 읽지 않는다
  (``recon/witness_kis.py::KisOrderRow``). 유일한 가격은 ``SEND_SEALED`` 의
  주문 지정가다. 그래서 손익 칸은 «지정가 기준» 으로 이름이 붙고, 출력이 그
  사실을 먼저 말한다 — 이 테스트가 그 문장을 고정한다.
* ACK 만 받고 체결 관측이 없는 attempt(2026-11-13 의 미추적 주문)는 **집계에
  들어가지 않고** 사유·odno 와 함께 따로 나온다. 조용히 0 으로 세거나 체결로
  세면 숫자가 거짓이 된다.
* 짝 없는 매도(계좌를 손으로 평탄화한 날)와 남은 보유 수량도 따로 나온다.
* 잎은 ``mode=ro`` 로만 열린다 — 보고서를 보는 것이 증거를 바꾸면 안 된다.

픽스처는 이 파일이 직접 만드는 evidence 저장소다(호스트 경로를 읽지 않는다).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

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


def _fill(attempt: str, odno: str, date: str, quantity: int = 1) -> dict[str, Any]:
    return {
        "attempt_id": attempt,
        "broker_execution_id": odno,
        "trading_date": date,
        "kind": "FULL_FILL",
        "filled_quantity": str(quantity),
        "remaining_quantity": "0",
        "reason": "filled",
    }


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


def _round_trip_rows() -> list[tuple[str, dict[str, Any]]]:
    """2026-11-17 왕복 한 번 — 193,400 에 사서 192,200 에 팔았다(지정가)."""
    return [
        _policy(),
        ("SEND_SEALED", _seal("attempt-buy", "BUY", 193_400)),
        ("EGRESS_RESULT_CONSUMED", _ack("attempt-buy", "0000008082", "20261117")),
        ("FILL_OBSERVED", _fill("attempt-buy", "0000008082", "20261117")),
        ("SEND_SEALED", _seal("attempt-sell", "SELL", 192_200)),
        ("EGRESS_RESULT_CONSUMED", _ack("attempt-sell", "0000010650", "20261117")),
        ("FILL_OBSERVED", _fill("attempt-sell", "0000010650", "20261117")),
    ]


@pytest.fixture
def round_trip_leaf(tmp_path: Path) -> Path:
    return _write_leaf(tmp_path / "leaf" / SYMBOL, _round_trip_rows())


GOLDEN_ROUND_TRIP = """\
sts tos perf — 종목·날짜별 체결·손익 (읽기 전용)

가격 기준: SEALED_ORDER_PRICE_ORD_UNPR
  증거에 체결가가 없다 — FILL_OBSERVED 는 체결 «수량» 만 적는다
    (tos/runtime/src/tos_runtime/posttrade/fill_observer.py::_emit).
  브로커 주문 행 파서도 가격 필드를 읽지 않는다
    (tos/runtime/src/tos_runtime/recon/witness_kis.py::KisOrderRow).
  증거 안의 유일한 가격은 SEND_SEALED 의 send_seal.outbound_price —
    보낸 주문의 지정가(ORD_UNPR × price_scale)다.
  따라서 아래 손익은 «지정가 기준» 이며 체결가 기준 실현 손익이 아니다.

읽은 잎:
  005930   {leaf}  (price_scale=100, 체결 2건)

종목      날짜         매수   매도   매수량   매도량   보유   왕복    승     손익@지정가
005930    20261117        1      1        1        1      0      1     0          -1,200
005930    합계            1      1        1        1      0      1     0          -1,200
"""


def test_round_trip_renders_the_golden_table(round_trip_leaf: Path) -> None:
    """한 왕복의 표 전체 — 칸·정렬·가격 기준 문단까지 고정한다."""
    text, code = perf.run(leaf_paths=(str(round_trip_leaf),))

    assert text == GOLDEN_ROUND_TRIP.format(leaf=round_trip_leaf)
    assert code == 0


def test_round_trip_json_counts_the_loss_at_the_sealed_order_price(
    round_trip_leaf: Path,
) -> None:
    """손익은 지정가 기준이고, JSON 이 그 기준을 이름으로 말한다."""
    text, _ = perf.run(leaf_paths=(str(round_trip_leaf),), as_json=True)
    document = json.loads(text)

    assert document["price_basis"]["basis"] == perf.PRICE_BASIS
    assert document["price_basis"]["execution_price_in_evidence"] is False
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
            "pnl_at_order_price_krw": "-1200",
            "open_quantity_end": "0",
        }
    ]
    assert symbol["totals"]["open_quantity"] == "0"
    assert symbol["open_lots"] == []
    assert symbol["unresolved_attempts"] == []


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
    assert symbol["totals"]["pnl_at_order_price_krw"] == "1500"


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
    # 보유 수량은 음수가 되지 않는다 — 짝 없는 매도는 수량이 아니라 아래 줄로 센다.
    assert symbol["days"][0]["open_quantity_end"] == "0"
    assert symbol["totals"]["open_quantity"] == "0"
    assert symbol["unmatched_sell_fills"] == [
        {
            "trading_date": "20261118",
            "side": "SELL",
            "quantity": "1",
            "order_price_krw": "192200",
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
    assert symbol["days"][1]["pnl_at_order_price_krw"] == "-1200"
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
