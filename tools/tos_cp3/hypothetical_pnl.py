#!/usr/bin/env python3
"""판단 전용 tenant 의 «체결됐다면» 손익 — 결정 봉 종가로만, 실현 손익과 절대 안 섞인다.

계획 ``docs/plans/2026-11-25-tos-operator-page-legibility-plan.md`` §6 P2 다섯째
항목. 선물 둘은 진입이 독립 승인 단계에서 멈추므로(운영자 결정 2026-11-05) 주문도
체결도 없다. 그래서 «이 전략이 오늘 뭘 했나» 를 볼 길이 하나도 없는데, 결정은
봉마다 남아 있다. 진입 판단 봉의 종가에 들어가 다음 청산 판단 봉의 종가에 나왔다고
보고 세는 것이 이 모듈이다.

**이것은 손익이 아니다.** 모든 수에 ``hypothetical: true`` 와 :data:`ASSUMPTIONS`
가 붙고, 실현 손익 필드(``symbols/today.json`` 의 ``pnl``)와 **합산되지 않는다**.
화면 표기도 «가상 손익(체결 가정)» 이다. 가정이 셋이나 되고(체결 보장 · 수수료
없음 · 슬리피지 없음) 그 셋은 전부 수를 좋은 쪽으로 민다 — 실제 성적이라고 읽히는
순간 이 수는 해롭다.

**방향 대칭.** LONG 은 ``청산 − 진입``, SHORT 는 ``진입 − 청산`` 이다. 비협상
규칙 «Futures must preserve long/short symmetry» 가 여기에도 그대로 적용된다 —
한쪽 부호를 빠뜨리면 SHORT tenant 의 성적이 정확히 뒤집혀 나온다.

**순수 함수다.** 디스크도 시계도 브로커도 보지 않는다. 입력은 바 목록과 계약
사실뿐이므로, 테스트가 손으로 쓴 봉 몇 개로 경계(미청산 강제 청산 · 포지션 중
진입 무시 · 가격 없는 봉)를 통째로 고정할 수 있다.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

__all__ = [
    "ASSUMPTIONS",
    "ENTRY_KIND",
    "EXIT_KINDS",
    "LONG",
    "SHORT",
    "Contract",
    "build_hypothetical_pnl",
]

#: 진입으로 보는 결정 종류. 커널의 어휘이고 이 모듈은 커널을 import 하지 못하므로
#: (방화벽 TOS-FW-R) 여기 다시 적는다 — 바 문서의 ``decision_kind`` 가 쓰는 값이다.
ENTRY_KIND = "ACTION"

#: 청산으로 보는 결정 종류. Setup D 의 R2(VWAP 복귀) · R3(EOD) 가 둘 다 ``FLAT``
#: 이므로 규칙 id 목록 대신 종류로 짝짓는다 — 규칙을 하나 더 붙인 날 목록을
#: 갱신하지 않아 청산이 조용히 사라지는 일이 없다.
EXIT_KINDS = frozenset({"FLAT"})

#: 이 수가 서 있는 가정. 문서에 **값과 함께** 실려서, 화면이 수만 떼어 그릴 수 없다.
ASSUMPTIONS = (
    "FILL_AT_DECISION_BAR_CLOSE",
    "FILL_ALWAYS_ASSUMED",
    "NO_FEES",
    "NO_SLIPPAGE",
    "ONE_CONTRACT",
    "ONE_POSITION_AT_A_TIME",
)

#: 미청산으로 끝난 포지션을 마지막 봉 종가로 닫을 때 붙는 표시.
FORCED_CLOSE_REASON = "LAST_BAR_FORCED_CLOSE"

LONG, SHORT = "LONG", "SHORT"


@dataclass(frozen=True)
class Contract:
    """가상 손익이 딛고 선 계약 사실 — 전부 설정에서 읽은 값이다.

    Attributes:
        name: 계약 규격의 이름(``kospi200_mini``).
        multiplier_krw_per_point: 지수 1포인트의 원화. 설정
            (``config/execution.yaml::futures_contract_spec``)에서 읽는다.
        price_field: 봉에서 종가를 담은 필드의 **발행 이름**. tenant 자신의
            ``construction.yaml::price_field_key`` 가 말한다.
        price_scale: 그 필드가 곱해져 실린 배수(``close_x100`` 은 100).
            tenant 의 ``fields.yaml::publish`` 가 말한다.
    """

    name: str | None
    multiplier_krw_per_point: int
    price_field: str
    price_scale: int


def _price(bar: Mapping[str, Any], contract: Contract) -> Decimal | None:
    """한 봉의 종가(지수 포인트). 읽히지 않으면 ``None`` — 지어내지 않는다."""
    for key in ("fields", "env_values"):
        values = bar.get(key)
        if not isinstance(values, Mapping) or contract.price_field not in values:
            continue
        raw = values[contract.price_field]
        if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
            continue
        try:
            return Decimal(str(raw)) / Decimal(contract.price_scale)
        except (InvalidOperation, ArithmeticError):
            continue
    return None


def _num(value: Decimal) -> str:
    """``perf`` 와 같은 수 표기 — 지수 표기 없이, 꼬리 0 없이."""
    normalized = value.normalize()
    text = format(normalized, "f")
    return "0" if text in ("-0", "0E+0") else text


def _points(entry: Decimal, exit_price: Decimal, direction: str) -> Decimal:
    """방향을 지킨 손익(포인트). SHORT 는 부호가 뒤집힌다."""
    return exit_price - entry if direction == LONG else entry - exit_price


def build_hypothetical_pnl(
    bars: Sequence[Mapping[str, Any]],
    *,
    direction: str,
    contract: Contract,
    instrument: str | None = None,
) -> dict[str, Any]:
    """진입 판단 봉과 다음 청산 판단 봉을 짝지어 «체결됐다면» 손익을 센다.

    포지션을 쥐고 있는 동안의 진입 판단은 **무시한다** — 한 계약만 든다는 가정
    (:data:`ASSUMPTIONS`)이고, 쌓으면 그 가정도 수도 다른 것이 된다. 마지막 봉까지
    열려 있으면 그 봉 종가로 닫고 ``forced_close`` 를 붙인다: 안 닫으면 그날 성적이
    «진입만 있고 결과 없음» 으로 빠져 조용히 좋아 보인다.

    Args:
        bars: 바 문서의 ``bars`` 그대로. 각 봉은 ``decision_kind`` ·
            ``decision_rule_id`` · ``time_kst`` · ``fields`` 를 가진다.
        direction: ``LONG`` 또는 ``SHORT`` — 그 tenant 가 설정에 고정한 방향.
        contract: 배수 · 가격 필드 · 스케일. 전부 설정에서 읽은 값이다.
        instrument: 월물 코드. 기록용이고 계산에 쓰지 않는다.

    Returns:
        ``trades`` · ``totals`` · ``assumptions`` 를 담은 블록. 실현 손익과 같은
        키 이름을 쓰지 않는다(``pnl_krw`` 가 아니라 ``hypothetical_pnl_krw``).
    """
    trades: list[dict[str, Any]] = []
    unpriced: list[dict[str, Any]] = []
    open_entry: dict[str, Any] | None = None
    last_priced: tuple[Mapping[str, Any], Decimal] | None = None

    for bar in bars:
        kind = bar.get("decision_kind")
        if kind not in (ENTRY_KIND, *EXIT_KINDS):
            continue
        price = _price(bar, contract)
        if price is None:
            unpriced.append(
                {
                    "time_kst": bar.get("time_kst"),
                    "decision_kind": kind,
                    "rule_id": bar.get("decision_rule_id"),
                }
            )
            continue
        last_priced = (bar, price)
        if kind == ENTRY_KIND:
            if open_entry is None:
                open_entry = {"bar": bar, "price": price}
            # 이미 열려 있으면 버린다 — ONE_POSITION_AT_A_TIME.
            continue
        if open_entry is not None:
            trades.append(_trade(open_entry, bar, price, direction, contract))
            open_entry = None

    if open_entry is not None and last_priced is not None:
        bar, price = last_priced
        trades.append(_trade(open_entry, bar, price, direction, contract, forced=True))

    total_points = sum((Decimal(t["points"]) for t in trades), Decimal(0))
    total_krw = sum((Decimal(t["hypothetical_pnl_krw"]) for t in trades), Decimal(0))
    return {
        "hypothetical": True,
        "direction": direction,
        "instrument": instrument,
        "contract": contract.name,
        "multiplier_krw_per_point": contract.multiplier_krw_per_point,
        "price_field": contract.price_field,
        "price_scale": contract.price_scale,
        "assumptions": list(ASSUMPTIONS),
        "trades": trades,
        "totals": {
            "trades": len(trades),
            "wins": sum(1 for t in trades if Decimal(t["points"]) > 0),
            "points": _num(total_points),
            "hypothetical_pnl_krw": _num(total_krw),
            "forced_closes": sum(1 for t in trades if t["forced_close"]),
        },
        # 결정은 있었는데 종가를 읽지 못한 봉. 비어 있는 것이 정상이고, 비어 있지
        # 않으면 위의 수는 그 봉들을 **빼고** 센 것이다.
        "unpriced_decisions": unpriced,
    }


def _trade(
    entry: Mapping[str, Any],
    exit_bar: Mapping[str, Any],
    exit_price: Decimal,
    direction: str,
    contract: Contract,
    *,
    forced: bool = False,
) -> dict[str, Any]:
    """가상 거래 한 건."""
    entry_bar = entry["bar"]
    entry_price: Decimal = entry["price"]
    points = _points(entry_price, exit_price, direction)
    return {
        "entry_time_kst": entry_bar.get("time_kst"),
        "entry_rule_id": entry_bar.get("decision_rule_id"),
        "entry_price_points": _num(entry_price),
        "exit_time_kst": exit_bar.get("time_kst"),
        "exit_rule_id": None if forced else exit_bar.get("decision_rule_id"),
        "exit_price_points": _num(exit_price),
        "points": _num(points),
        "hypothetical_pnl_krw": _num(
            points * Decimal(contract.multiplier_krw_per_point)
        ),
        "forced_close": forced,
        "forced_close_reason": FORCED_CLOSE_REASON if forced else None,
    }
