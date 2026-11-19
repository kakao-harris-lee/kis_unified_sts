#!/usr/bin/env python3
"""`sts tos perf` — 종목·날짜별 체결과 손익(읽기 전용).

계획 ``docs/plans/2026-11-19-tos-usage-plan.md`` §5 «`sts tos perf` 최소판».
tenant 잎의 durable evidence 만 읽는다 — sqlite 는 ``file:...?mode=ro`` 로 열고
아무것도 쓰지 않는다. 방화벽(TOS-FW-R)상 이 모듈은 ``tos``/``tos_runtime`` 를
import 하지 않는다. 읽는 종류 이름은 런타임이 적는 상수와 같고, 그 출처를 아래
상수 옆에 적어 둔다.

**가격 기준 — 체결가가 있으면 체결가로.** 런타임이 적는 ``FILL_OBSERVED`` 는
브로커의 평균 체결가를 ``avg_execution_price`` 로 적는다
(``tos/runtime/src/tos_runtime/posttrade/fill_observer.py`` ``_emit``; 파서는
``tos/runtime/src/tos_runtime/recon/witness_kis.py`` ``KisOrderRow.avg_prvs``).
그 값은 브로커가 찍은 **원 단위 정수**다 — 트리의 ``price_scale`` 로 나누지
않는다. 그 키가 없거나 비어 있는 체결(그 필드가 생기기 전에 기록된 잎, 또는
브로커 행이 모호했던 체결)은 ``SEND_SEALED`` 의 ``send_seal.outbound_price``
— **보낸 주문의 지정가**(ORD_UNPR × price_scale) — 로 떨어진다. 도구는 어느
기준이 쓰였는지를 표와 JSON 양쪽에 적고, 가격을 지어내지 않는다.
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.tos_cp3 import session_inputs as si  # noqa: E402
from tools.tos_cp3 import status_board  # noqa: E402

__all__ = [
    "Fill",
    "LeafReport",
    "PRICE_BASIS",
    "SymbolReport",
    "TENANT_TREE_GLOB",
    "build_report",
    "discover_leaves",
    "main",
    "read_leaf",
    "render_text",
    "run",
]

# 런타임이 적는 종류 이름. 출처는 각 줄 옆에 — 이 모듈은 그 패키지를 import 할 수 없다.
SEND_SEALED_KIND = "SEND_SEALED"  # tos/src/tos/egressgw/seal.py (send_seal 블록)
FILL_OBSERVED_KIND = "FILL_OBSERVED"  # posttrade/fill_observer.py::FILL_OBSERVED_KIND
ACK_UNTRACKABLE_KIND = "FILL_OBSERVER_ACK_UNTRACKABLE"  # 같은 파일
EGRESS_RESULT_CONSUMED_KIND = "EGRESS_RESULT_CONSUMED"  # engine 투영 전진
VENUE_POLICY_BOUND_KIND = "VENUE_POLICY_BOUND"  # price_scale 의 출처

FULL_FILL = "FULL_FILL"
NON_FILL_TERMINAL_KINDS = frozenset({"CANCEL_ACK", "EXPIRED", "REJECT"})

BUY, SELL = "BUY", "SELL"

TENANT_TREE_GLOB = "cp3-setup-d-stock-*"
TENANT_DATA_PARENT_SUFFIX = "-data"  # tools/tos_cp3/inspect_session.py 와 같은 규약
ARCHIVE_DIRNAME = "archive"

PRICE_BASIS = "EXECUTION_PRICE_WITH_SEALED_FALLBACK"

#: 한 체결(또는 한 날)의 가격이 어디서 왔는지.
BASIS_EXECUTION = "EXECUTION"
BASIS_ORDER_PRICE = "ORDER_PRICE"
BASIS_MIXED = "MIXED"

#: 지정가로 떨어진 체결이 섞인 줄에 붙는 표시.
FALLBACK_MARK = "*"

PRICE_BASIS_NOTE_LINES: tuple[str, ...] = (
    "체결가는 FILL_OBSERVED 의 avg_execution_price — 브로커의 평균 체결가다",
    "  (tos/runtime/src/tos_runtime/posttrade/fill_observer.py::_emit).",
    "그 값은 브로커가 찍은 원 단위 정수다 — price_scale 로 나누지 않는다.",
    "그 키가 없는 체결은 SEND_SEALED 의 send_seal.outbound_price —",
    "  보낸 주문의 지정가(ORD_UNPR × price_scale) — 로 떨어진다.",
    f"손익에 «{FALLBACK_MARK}» 가 붙은 줄은 그 지정가가 섞여 있다는 뜻이다.",
)

PRICE_BASIS_NOTE = " ".join(line.strip() for line in PRICE_BASIS_NOTE_LINES)

STATUS_FILLED = "FILLED"
STATUS_NO_FILL = "NO_FILL"
STATUS_UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class _Order:
    """한 ``SEND_SEALED`` — 보낸 주문의 방향·수량·지정가."""

    seq: int
    attempt_id: str
    side: str | None
    quantity: Decimal | None
    order_price: Decimal | None
    instrument: str | None
    account: str | None


@dataclass(frozen=True)
class Fill:
    """관측된 전량 체결 하나. 브로커의 체결가가 있으면 그것, 없으면 주문의 지정가."""

    leaf_order: int
    seq: int
    attempt_id: str
    broker_execution_id: str | None
    trading_date: str
    side: str
    quantity: Decimal
    order_price: Decimal | None
    execution_price: Decimal | None = None

    @property
    def price(self) -> Decimal | None:
        """손익에 쓰이는 가격 — 체결가가 있으면 체결가, 없으면 지정가."""
        return (
            self.order_price if self.execution_price is None else self.execution_price
        )

    @property
    def basis(self) -> str:
        """:attr:`price` 가 어디서 왔는지."""
        return BASIS_ORDER_PRICE if self.execution_price is None else BASIS_EXECUTION


@dataclass
class LeafReport:
    """한 잎을 한 번 읽은 결과. 거부는 문자열로 남긴다 — 보고서는 죽지 않는다."""

    path: Path
    symbol: str | None = None
    account: str | None = None
    price_scale: int | None = None
    fills: list[Fill] = field(default_factory=list)
    attempts: list[dict[str, Any]] = field(default_factory=list)
    unattributed_fills: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


@dataclass
class _DayRow:
    buy_fills: int = 0
    sell_fills: int = 0
    qty_bought: Decimal = Decimal(0)
    qty_sold: Decimal = Decimal(0)
    closed_round_trips: int = 0
    wins: int = 0
    pnl: Decimal = Decimal(0)
    open_quantity_end: Decimal = Decimal(0)
    pnl_known: bool = True
    #: 그 날 손익에 실제로 쓰인 가격의 출처들 — 둘 다 있으면 «섞임».
    bases: set[str] = field(default_factory=set)

    @property
    def pnl_basis(self) -> str | None:
        if not self.pnl_known or not self.bases:
            return None
        return BASIS_MIXED if len(self.bases) > 1 else next(iter(self.bases))


@dataclass
class SymbolReport:
    """한 종목(= 한 tenant)의 날짜별 집계와, 집계에 넣지 못한 것들."""

    symbol: str
    days: dict[str, _DayRow] = field(default_factory=dict)
    open_lots: list[dict[str, Any]] = field(default_factory=list)
    unmatched_sell_fills: list[dict[str, Any]] = field(default_factory=list)
    unresolved_attempts: list[dict[str, Any]] = field(default_factory=list)
    unattributed_fills: list[dict[str, Any]] = field(default_factory=list)


def _num(value: Decimal) -> str:
    """지수 표기 없이 — JSON 과 표에 같은 문자열이 가도록."""
    return format(value.normalize(), "f")


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _positive(value: Decimal | None) -> Decimal | None:
    """0 이나 음수인 «가격» 은 가격이 아니다 — 브로커가 아직 못 찍은 것으로 본다."""
    return value if value is not None and value > 0 else None


def _dig(record: Any, *path: str) -> Any:
    for key in path:
        if not isinstance(record, dict):
            return None
        record = record.get(key)
    return record


def discover_leaves(
    *, state_dir: Path, config_dir: Path, tree_glob: str = TENANT_TREE_GLOB
) -> list[Path]:
    """tenant 트리마다 **살아 있는** 잎 하나씩. 보관된 잎은 ``--leaf`` 로만 읽는다.

    트리 이름(``config/tos_runtime/<tree_id>``)에서 데이터 부모
    ``<state_dir>/<tree_id>-data`` 를 만들고, 그 아래 ``evidence.sqlite3`` 를 쥔
    바로 아래 디렉터리를 잎으로 본다. ``archive/`` 는 건너뛴다 — 보관된 잎은
    운영자가 이름으로 부를 때만 읽는다.
    """
    leaves: list[Path] = []
    for tree in sorted(config_dir.glob(tree_glob)):
        if not tree.is_dir():
            continue
        parent = state_dir / f"{tree.name}{TENANT_DATA_PARENT_SUFFIX}"
        if not parent.is_dir():
            continue
        for child in sorted(parent.iterdir()):
            if child.name == ARCHIVE_DIRNAME or not child.is_dir():
                continue
            if (child / si.EVIDENCE_FILE_NAME).is_file():
                leaves.append(child)
    return leaves


def _price_scale_at(scales: list[tuple[int, int]], seq: int) -> int | None:
    """``seq`` 직전에 마지막으로 바인딩된 ``price_scale``."""
    current: int | None = None
    for bound_seq, scale in scales:
        if bound_seq > seq:
            break
        current = scale
    return current


def _rows(conn: Any, kinds: tuple[str, ...]) -> list[tuple[int, str, dict[str, Any]]]:
    marks = ",".join("?" * len(kinds))
    return [
        (
            int(seq),
            str(kind),
            si._evidence_record(payload, seq=int(seq), kind=str(kind)),
        )
        for seq, kind, payload in conn.execute(
            f"SELECT seq, kind, payload_json FROM entries WHERE kind IN ({marks})"
            " ORDER BY seq",
            kinds,
        )
    ]


def read_leaf(path: Path, *, leaf_order: int = 0) -> LeafReport:
    """한 잎의 체결·주문·미해결 attempt. 읽기만 한다."""
    report = LeafReport(path=path)
    try:
        conn = si._connect_ro(
            path / si.EVIDENCE_FILE_NAME,
            label="evidence",
            pinned_version=si.PINNED_EVIDENCE_SCHEMA_VERSION,
        )
    except (si.SessionInputsError, OSError) as exc:
        report.error = f"{type(exc).__name__}: {exc}"
        return report
    try:
        rows = _rows(
            conn,
            (
                SEND_SEALED_KIND,
                FILL_OBSERVED_KIND,
                ACK_UNTRACKABLE_KIND,
                EGRESS_RESULT_CONSUMED_KIND,
                VENUE_POLICY_BOUND_KIND,
            ),
        )
    except Exception as exc:  # noqa: BLE001 — sqlite3.Error 등. 사유를 보여 준다
        report.error = f"{type(exc).__name__}: {exc}"
        return report
    finally:
        conn.close()
    _fold_leaf(report, rows, leaf_order=leaf_order)
    return report


def _fold_leaf(
    report: LeafReport,
    rows: list[tuple[int, str, dict[str, Any]]],
    *,
    leaf_order: int,
) -> None:
    """읽은 행을 잎 보고서로 접는다(순수 함수 — 테스트가 행만 주고 부를 수 있다)."""
    scales: list[tuple[int, int]] = [
        (seq, int(record["price_scale"]))
        for seq, kind, record in rows
        if kind == VENUE_POLICY_BOUND_KIND
        and isinstance(record.get("price_scale"), int)
        and not isinstance(record.get("price_scale"), bool)
    ]
    report.price_scale = scales[-1][1] if scales else None

    orders: dict[str, _Order] = {}
    last_result_kind: dict[str, str] = {}
    untrackable: dict[str, str] = {}
    fills: dict[str, Fill] = {}
    # 체결이 관측되지 않은 attempt 도 브로커 번호·거래일은 알 수 있다 — ACK 가 적는다.
    broker_id: dict[str, str] = {}
    acked_date: dict[str, str] = {}

    for seq, kind, record in rows:
        if kind == SEND_SEALED_KIND:
            seal = record.get("send_seal")
            if not isinstance(seal, dict):
                continue
            attempt = seal.get("attempt_id")
            if not isinstance(attempt, str):
                continue
            raw_price = _decimal(seal.get("outbound_price"))
            scale = _price_scale_at(scales, seq)
            orders[attempt] = _Order(
                seq=seq,
                attempt_id=attempt,
                side=seal.get("outbound_side"),
                quantity=_decimal(seal.get("outbound_quantity")),
                order_price=(
                    None
                    if raw_price is None or not scale
                    else raw_price / Decimal(scale)
                ),
                instrument=_dig(seal, "instrument_key", "instrument"),
                account=_dig(seal, "instrument_key", "account"),
            )
        elif kind == EGRESS_RESULT_CONSUMED_KIND:
            attempt = record.get("attempt_id")
            result_kind = record.get("egress_result_kind")
            if isinstance(attempt, str) and isinstance(result_kind, str):
                last_result_kind[attempt] = result_kind
            _remember(broker_id, record, "broker_execution_id")
            _remember(acked_date, record, "trading_date")
        elif kind == ACK_UNTRACKABLE_KIND:
            attempt = record.get("attempt_id")
            if isinstance(attempt, str):
                untrackable[attempt] = str(record.get("reason"))
            _remember(broker_id, record, "broker_execution_id")
        elif kind == FILL_OBSERVED_KIND:
            if record.get("kind") != FULL_FILL:
                continue
            attempt = record.get("attempt_id")
            quantity = _decimal(record.get("filled_quantity"))
            date = record.get("trading_date")
            if not isinstance(attempt, str) or quantity is None or quantity <= 0:
                continue
            order = orders.get(attempt)
            side = order.side if order is not None else None
            if side not in (BUY, SELL) or not isinstance(date, str) or not date:
                # 방향이나 거래일을 모르는 체결은 FIFO 에 넣을 수 없다. 조용히
                # 버리면 숫자가 거짓이 되므로 따로 적는다.
                report.unattributed_fills.append(
                    {
                        "attempt_id": attempt,
                        "broker_execution_id": record.get("broker_execution_id"),
                        "trading_date": date if isinstance(date, str) else None,
                        "quantity": _num(quantity),
                        "side": side,
                        "reason": (
                            "주문 방향 모름(SEND_SEALED 없음)"
                            if side not in (BUY, SELL)
                            else "거래일 없음"
                        ),
                    }
                )
                continue
            fills[attempt] = Fill(
                leaf_order=leaf_order,
                seq=seq,
                attempt_id=attempt,
                broker_execution_id=record.get("broker_execution_id"),
                trading_date=date,
                side=str(side),
                quantity=quantity,
                order_price=order.order_price if order is not None else None,
                # 이미 원 단위다 — price_scale 로 나누지 않는다(지정가와 다른 점).
                execution_price=_positive(_decimal(record.get("avg_execution_price"))),
            )

    report.fills = sorted(fills.values(), key=lambda f: f.seq)
    report.symbol = _sole(order.instrument for order in orders.values())
    report.account = _sole(order.account for order in orders.values())
    for attempt, order in sorted(orders.items(), key=lambda kv: kv[1].seq):
        status = STATUS_FILLED
        if attempt not in fills:
            terminal = last_result_kind.get(attempt)
            status = (
                STATUS_NO_FILL
                if terminal in NON_FILL_TERMINAL_KINDS
                else STATUS_UNRESOLVED
            )
        report.attempts.append(
            {
                "attempt_id": attempt,
                "status": status,
                "side": order.side,
                "quantity": None if order.quantity is None else _num(order.quantity),
                "order_price_krw": (
                    None if order.order_price is None else _num(order.order_price)
                ),
                "broker_execution_id": (
                    fills[attempt].broker_execution_id
                    if attempt in fills
                    else broker_id.get(attempt)
                ),
                "trading_date": (
                    fills[attempt].trading_date
                    if attempt in fills
                    else acked_date.get(attempt)
                ),
                "last_egress_result_kind": last_result_kind.get(attempt),
                "ack_untrackable_reason": untrackable.get(attempt),
                "leaf": str(report.path),
            }
        )


def _remember(store: dict[str, str], record: dict[str, Any], field_name: str) -> None:
    """``record`` 의 ``field_name`` 이 문자열이면 그 attempt 의 마지막 값으로 기억한다."""
    attempt = record.get("attempt_id")
    value = record.get(field_name)
    if isinstance(attempt, str) and isinstance(value, str) and value:
        store[attempt] = value


def _sole(values: Any) -> str | None:
    """값이 하나로 모이면 그 값, 비었거나 갈리면 ``None`` — 추측하지 않는다."""
    distinct = {value for value in values if isinstance(value, str) and value}
    return distinct.pop() if len(distinct) == 1 else None


def build_report(leaves: list[LeafReport]) -> dict[str, Any]:
    """잎 보고서들을 종목별 집계로.

    FIFO 는 한 tenant 안에서만 돈다 — 커널이 tenant 당 한 번에 한 포지션을
    보장한다(계획 ``2026-11-19-tos-usage-plan.md`` §7 U1). 체결은 거래일 ·
    잎 순서 · seq 로 줄 세운다.
    """
    by_symbol: dict[str, SymbolReport] = {}
    fills_by_symbol: dict[str, list[Fill]] = {}
    for leaf in leaves:
        if not (leaf.fills or leaf.attempts or leaf.unattributed_fills):
            # 주문도 체결도 없는 잎(부팅만 한 날)은 종목 칸을 만들지 않는다 —
            # 종목 이름을 디렉터리에서 추측하느니 «읽은 잎» 줄로만 남긴다.
            continue
        symbol = leaf.symbol or leaf.path.name
        report = by_symbol.setdefault(symbol, SymbolReport(symbol=symbol))
        report.unresolved_attempts.extend(
            attempt
            for attempt in leaf.attempts
            if attempt["status"] == STATUS_UNRESOLVED
        )
        report.unattributed_fills.extend(leaf.unattributed_fills)
        fills_by_symbol.setdefault(symbol, []).extend(leaf.fills)
    for symbol, fills in fills_by_symbol.items():
        _fifo(
            by_symbol[symbol],
            sorted(fills, key=lambda f: (f.trading_date, f.leaf_order, f.seq)),
        )
    return {
        "price_basis": {
            "basis": PRICE_BASIS,
            "execution_price_in_evidence": any(
                fill.execution_price is not None
                for leaf in leaves
                for fill in leaf.fills
            ),
            "note": PRICE_BASIS_NOTE,
        },
        "leaves": [
            {
                "path": str(leaf.path),
                "symbol": leaf.symbol,
                "account": leaf.account,
                "price_scale": leaf.price_scale,
                "fills": len(leaf.fills),
                "error": leaf.error,
            }
            for leaf in leaves
        ],
        "symbols": [
            _symbol_document(by_symbol[symbol]) for symbol in sorted(by_symbol)
        ],
    }


def _fifo(report: SymbolReport, fills: list[Fill]) -> None:
    """FIFO 매칭. 가격을 모르는 체결은 손익에서 빼고 그 날을 «손익 모름» 으로 표시한다."""
    lots: deque[list[Any]] = deque()
    for fill in fills:
        row = report.days.setdefault(fill.trading_date, _DayRow())
        if fill.side == BUY:
            row.buy_fills += 1
            row.qty_bought += fill.quantity
            lots.append([fill.quantity, fill.price, fill])
            if fill.price is None:
                row.pnl_known = False
        else:
            row.sell_fills += 1
            row.qty_sold += fill.quantity
            remaining = fill.quantity
            while remaining > 0 and lots:
                lot = lots[0]
                take = min(remaining, lot[0])
                lot[0] -= take
                remaining -= take
                row.closed_round_trips += 1
                if fill.price is None or lot[1] is None:
                    row.pnl_known = False
                else:
                    pnl = (fill.price - lot[1]) * take
                    row.pnl += pnl
                    row.bases |= {fill.basis, lot[2].basis}
                    if pnl > 0:
                        row.wins += 1
                if lot[0] == 0:
                    lots.popleft()
            if remaining > 0:
                report.unmatched_sell_fills.append(_fill_document(fill, remaining))
        # 열린 수량은 «아직 짝이 없는 매수» 의 합이다. 짝 없는 매도를 여기서 빼면
        # 수량이 음수가 되고 합계(열린 lot 의 합)와 어긋난다 — 그 매도는 따로 적는다.
        row.open_quantity_end = sum((lot[0] for lot in lots), Decimal(0))
    report.open_lots = [_fill_document(lot[2], lot[0]) for lot in lots if lot[0] > 0]


def _fill_document(fill: Fill, quantity: Decimal) -> dict[str, Any]:
    return {
        "trading_date": fill.trading_date,
        "side": fill.side,
        "quantity": _num(quantity),
        "order_price_krw": (
            None if fill.order_price is None else _num(fill.order_price)
        ),
        "execution_price_krw": (
            None if fill.execution_price is None else _num(fill.execution_price)
        ),
        "price_basis": fill.basis,
        "broker_execution_id": fill.broker_execution_id,
        "attempt_id": fill.attempt_id,
    }


def _symbol_document(report: SymbolReport) -> dict[str, Any]:
    days = [
        {
            "date": date,
            "buy_fills": row.buy_fills,
            "sell_fills": row.sell_fills,
            "quantity_bought": _num(row.qty_bought),
            "quantity_sold": _num(row.qty_sold),
            "closed_round_trips": row.closed_round_trips,
            "wins": row.wins,
            "pnl_krw": None if not row.pnl_known else _num(row.pnl),
            "pnl_basis": row.pnl_basis,
            "open_quantity_end": _num(row.open_quantity_end),
        }
        for date, row in sorted(report.days.items())
    ]
    rows = list(report.days.values())
    total_known = all(row.pnl_known for row in rows)
    total_bases = {basis for row in rows for basis in row.bases}
    return {
        "symbol": report.symbol,
        "days": days,
        "totals": {
            "buy_fills": sum(row.buy_fills for row in rows),
            "sell_fills": sum(row.sell_fills for row in rows),
            "quantity_bought": _num(sum((row.qty_bought for row in rows), Decimal(0))),
            "quantity_sold": _num(sum((row.qty_sold for row in rows), Decimal(0))),
            "closed_round_trips": sum(row.closed_round_trips for row in rows),
            "wins": sum(row.wins for row in rows),
            "pnl_krw": (
                _num(sum((row.pnl for row in rows), Decimal(0)))
                if total_known
                else None
            ),
            "pnl_basis": (
                None
                if not total_known or not total_bases
                else (BASIS_MIXED if len(total_bases) > 1 else next(iter(total_bases)))
            ),
            "open_quantity": _num(
                sum((Decimal(lot["quantity"]) for lot in report.open_lots), Decimal(0))
            ),
        },
        "open_lots": report.open_lots,
        "unmatched_sell_fills": report.unmatched_sell_fills,
        "unresolved_attempts": report.unresolved_attempts,
        "unattributed_fills": report.unattributed_fills,
    }


_HEADERS: tuple[tuple[str, int], ...] = (
    ("종목", 8),
    ("날짜", 10),
    ("매수", 5),
    ("매도", 5),
    ("매수량", 7),
    ("매도량", 7),
    ("보유", 5),
    ("왕복", 5),
    ("승", 4),
    ("손익", 14),
)


def _money(value: str | None) -> str:
    if value is None:
        return "모름"
    whole = Decimal(value)
    return f"{whole:,.0f}" if whole == whole.to_integral_value() else f"{whole:,}"


def _pnl_cell(value: str | None, basis: str | None) -> str:
    """지정가가 섞인 손익에는 표시를 붙인다 — 어느 기준인지 표에서 보이게."""
    mark = FALLBACK_MARK if basis in (BASIS_ORDER_PRICE, BASIS_MIXED) else ""
    return _money(value) + mark


def _width(text: str) -> int:
    """터미널에서 차지하는 칸 수 — 한글은 두 칸이다(표가 틀어지지 않게)."""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def _row(cells: list[str]) -> str:
    out = []
    for index, (cell, (_, width)) in enumerate(zip(cells, _HEADERS, strict=True)):
        pad = " " * max(0, width - _width(cell))
        out.append(cell + pad if index < 2 else pad + cell)
    return "  ".join(out)


def render_text(document: dict[str, Any]) -> str:
    lines = ["sts tos perf — 종목·날짜별 체결·손익 (읽기 전용)", ""]
    lines.append(f"가격 기준: {document['price_basis']['basis']}")
    lines.extend(f"  {line}" for line in PRICE_BASIS_NOTE_LINES)
    lines.append("")
    lines.append("읽은 잎:")
    for leaf in document["leaves"]:
        if leaf["error"]:
            lines.append(f"  ✗ {leaf['path']} — {leaf['error']}")
            continue
        lines.append(
            f"  {leaf['symbol'] or '종목 모름':<8} {leaf['path']}"
            f"  (price_scale={leaf['price_scale']}, 체결 {leaf['fills']}건)"
        )
    if not document["leaves"]:
        lines.append("  (없음)")
    lines.append("")
    lines.append(_row([name for name, _ in _HEADERS]))
    for symbol in document["symbols"]:
        for day in symbol["days"]:
            lines.append(
                _row(
                    [
                        symbol["symbol"],
                        day["date"],
                        str(day["buy_fills"]),
                        str(day["sell_fills"]),
                        day["quantity_bought"],
                        day["quantity_sold"],
                        day["open_quantity_end"],
                        str(day["closed_round_trips"]),
                        str(day["wins"]),
                        _pnl_cell(day["pnl_krw"], day["pnl_basis"]),
                    ]
                )
            )
        total = symbol["totals"]
        lines.append(
            _row(
                [
                    symbol["symbol"],
                    "합계",
                    str(total["buy_fills"]),
                    str(total["sell_fills"]),
                    total["quantity_bought"],
                    total["quantity_sold"],
                    total["open_quantity"],
                    str(total["closed_round_trips"]),
                    str(total["wins"]),
                    _pnl_cell(total["pnl_krw"], total["pnl_basis"]),
                ]
            )
        )
    if not any(symbol["days"] for symbol in document["symbols"]):
        lines.append("  (관측된 체결 없음)")
    lines.extend(_render_leftovers(document))
    return "\n".join(lines) + "\n"


def _price_label(fill_document: dict[str, Any]) -> str:
    """체결 한 건의 가격을 쓰인 기준과 함께 — «@체결가 193,300» / «@지정가 193,400»."""
    if fill_document.get("execution_price_krw") is not None:
        return f"@체결가 {_money(fill_document['execution_price_krw'])}"
    return f"@지정가 {_money(fill_document['order_price_krw'])}"


def _render_leftovers(document: dict[str, Any]) -> list[str]:
    """집계에 넣지 못한 것들 — 열린 수량 · 짝 없는 매도 · 미해결 attempt."""
    lines: list[str] = []
    for symbol in document["symbols"]:
        name = symbol["symbol"]
        for lot in symbol["open_lots"]:
            lines.append(
                f"  {name} 보유 {lot['quantity']}주 — {lot['trading_date']} 매수 "
                f"odno={lot['broker_execution_id']} {_price_label(lot)} "
                "(아직 TOS 가 닫지 않았다)"
            )
        for sell in symbol["unmatched_sell_fills"]:
            lines.append(
                f"  {name} 짝 없는 매도 {sell['quantity']}주 — "
                f"{sell['trading_date']} odno={sell['broker_execution_id']} "
                "(이 잎에 대응하는 매수 체결이 없다)"
            )
        for stray in symbol["unattributed_fills"]:
            lines.append(
                f"  {name} 집계 못 한 체결 {stray['quantity']}주 — "
                f"odno={stray['broker_execution_id']} · 사유 {stray['reason']}"
            )
        for attempt in symbol["unresolved_attempts"]:
            reason = (
                attempt["ack_untrackable_reason"]
                or f"마지막 결과 {attempt['last_egress_result_kind']}"
            )
            lines.append(
                f"  {name} 미해결 {attempt['side']} {attempt['quantity']}주 "
                f"@지정가 {_money(attempt['order_price_krw'])} — "
                f"odno={attempt['broker_execution_id']} · 사유 {reason} · "
                "체결 관측 없음(채워졌는지 모른다)"
            )
    return ["", "집계 밖:", *lines] if lines else []


def run(
    *,
    config_path: Path = status_board.DEFAULT_CONFIG_PATH,
    state_dir: str | None = None,
    leaf_paths: tuple[str, ...] = (),
    tree_glob: str = TENANT_TREE_GLOB,
    config_dir: Path | None = None,
    as_json: bool = False,
) -> tuple[str, int]:
    """(출력, 종료코드). 읽을 잎이 없거나 읽히지 않는 잎이 있으면 1.

    ``leaf_paths`` 를 주면 탐색하지 않는다 — 상태판 설정도 그때는 읽지 않는다.
    """
    if leaf_paths:
        paths = [Path(p).expanduser() for p in leaf_paths]
    else:
        root = (
            status_board.expand_path(state_dir)
            if state_dir is not None
            else status_board.load_config(config_path).state_dir
        )
        paths = discover_leaves(
            state_dir=root,
            config_dir=config_dir or (REPO_ROOT / "config" / "tos_runtime"),
            tree_glob=tree_glob,
        )
    leaves = [read_leaf(path, leaf_order=index) for index, path in enumerate(paths)]
    document = build_report(leaves)
    text = (
        json.dumps(document, ensure_ascii=False, indent=2) + "\n"
        if as_json
        else render_text(document)
    )
    failed = not leaves or any(leaf.error for leaf in leaves)
    return text, (1 if failed else 0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--config", type=Path, default=status_board.DEFAULT_CONFIG_PATH)
    parser.add_argument("--state-dir", default=None)
    parser.add_argument(
        "--leaf",
        action="append",
        default=[],
        help="읽을 잎을 직접 지정(반복 가능) — 보관된 잎은 이 방법으로만 읽는다",
    )
    parser.add_argument("--tree-glob", default=TENANT_TREE_GLOB)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    text, code = run(
        config_path=args.config,
        state_dir=args.state_dir,
        leaf_paths=tuple(args.leaf),
        tree_glob=args.tree_glob,
        as_json=args.json,
    )
    sys.stdout.write(text)
    return code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
