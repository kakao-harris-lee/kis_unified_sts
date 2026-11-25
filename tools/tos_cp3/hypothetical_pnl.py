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
    "SKIP_ENGINE_DISAGREES",
    "SKIP_NOT_ENGINE_COUNTED",
    "SKIP_PROBE_ENTRY",
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

#: 아직 도는 세션에서 열린 포지션을 마지막 봉 종가로 **평가**했다는 표시.
OPEN_MARK_BASIS = "OPEN_MARKED_TO_LAST_BAR"

#: 미청산으로 끝난 포지션을 마지막 봉 종가로 닫을 때 붙는 표시.
FORCED_CLOSE_REASON = "LAST_BAR_FORCED_CLOSE"

#: 결정이 적혀 있는데도 거래로 세지 **않은** 사유들.
#:
#: ``NOT_ENGINE_COUNTED`` — 그 봉의 ``decision_kind`` 는 엔진이 내린 것이 아니라
#: 점검이 저널에서 **다시 도출한** 값이다(``counted`` 가 참이 아닌 봉: 증거를 잇지
#: 못한 ``journal_unjoined``, 그리고 보류된 봉). 엔진이 낸 적 없는 진입으로 손익을
#: 세면 그 수는 전략이 한 일이 아니다.
#: ``ENGINE_DISAGREES`` — 엔진이 기록한 결과 모양과 다시 도출한 결정이 어긋난 봉
#: (``decision_disagrees``). 어느 쪽이 참인지 여기서 정할 수 없으므로 세지 않는다.
#: ``PROBE_ENTRY`` — 주문 경로 시험 규칙의 진입. 전략 신호가 아니다.
SKIP_NOT_ENGINE_COUNTED = "NOT_ENGINE_COUNTED"
SKIP_ENGINE_DISAGREES = "ENGINE_DISAGREES"
SKIP_PROBE_ENTRY = "PROBE_ENTRY"

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


def _note(bar: Mapping[str, Any], kind: Any, reason: str | None) -> dict[str, Any]:
    """합계에서 빠진 결정 봉 한 줄. ``reason`` 이 ``None`` 이면 사유 키를 달지 않는다.

    ``unpriced_decisions`` 는 사유가 하나뿐이라(종가를 못 읽었다) 키를 달지 않고,
    ``skipped_decisions`` 는 사유가 여럿이라 단다.
    """
    note: dict[str, Any] = {
        "time_kst": bar.get("time_kst"),
        "decision_kind": kind,
        "rule_id": bar.get("decision_rule_id"),
    }
    if reason is not None:
        note["reason"] = reason
    return note


def _not_an_engine_decision(bar: Mapping[str, Any]) -> str | None:
    """이 봉의 결정을 엔진이 낸 것으로 볼 수 없는 사유, 볼 수 있으면 ``None``.

    바 문서의 ``decision_kind`` 는 두 가지 중 하나다 — 엔진 자신의 value view 로
    평가한 것(``counted``), 아니면 점검이 저널에서 **다시 도출한** 것. 뒤쪽은
    엔진이 낸 적 없는 결정이므로, 그것으로 진입·청산을 세면 그 손익은 전략이 한
    일이 아니라 점검 도구가 한 일이다.
    """
    if bar.get("decision_disagrees") is True:
        return SKIP_ENGINE_DISAGREES
    if bar.get("counted") is not True:
        return SKIP_NOT_ENGINE_COUNTED
    return None


def build_hypothetical_pnl(
    bars: Sequence[Mapping[str, Any]],
    *,
    direction: str,
    contract: Contract,
    instrument: str | None = None,
    probe_rule_ids: frozenset[str] = frozenset(),
    session_ended: bool = True,
) -> dict[str, Any]:
    """진입 판단 봉과 다음 청산 판단 봉을 짝지어 «체결됐다면» 손익을 센다.

    **엔진이 낸 결정만 센다.** 증거를 잇지 못한 봉(``counted`` 거짓)과 엔진 기록과
    어긋난 봉(``decision_disagrees``)의 ``decision_kind`` 는 점검이 다시 도출한
    값이지 엔진의 것이 아니다(:func:`_not_an_engine_decision`). 프로브 규칙의
    진입도 세지 않는다 — 주문 경로 시험이지 전략 신호가 아니다. 버린 봉은 전부
    ``skipped_decisions`` 에 사유와 함께 남으므로, 합계가 무엇을 빼고 센 것인지
    문서만 보고 말할 수 있다.

    포지션을 쥐고 있는 동안의 진입 판단은 **무시한다** — 한 계약만 든다는 가정
    (:data:`ASSUMPTIONS`)이고, 쌓으면 그 가정도 수도 다른 것이 된다.

    마지막 봉까지 열려 있는 포지션의 처리는 **세션이 끝났는지**에 달렸다.

    * 끝난 세션이면 그 봉 종가로 닫고 ``forced_close`` 를 붙인다: 안 닫으면 그날
      성적이 «진입만 있고 결과 없음» 으로 빠져 조용히 좋아 보인다.
    * 아직 도는 세션이면 **닫지 않는다**. 장중 내보내기(P3)는 5분마다 같은 날을
      다시 쓰는데, 그때마다 열린 포지션을 마지막 봉에 닫아 ``trades`` 에 넣으면
      «끝난 왕복» 이 아닌 것을 끝났다고 말하고 승·왕복·합계가 전부 그 가짜 청산
      위에서 계산된다. 대신 ``open_position`` 으로 따로 내고 합계에서는 뺀다.

    Args:
        bars: 바 문서의 ``bars`` 그대로. 각 봉은 ``decision_kind`` ·
            ``decision_rule_id`` · ``time_kst`` · ``fields`` · ``counted`` 를 가진다.
        direction: ``LONG`` 또는 ``SHORT`` — 그 tenant 가 설정에 고정한 방향.
        contract: 배수 · 가격 필드 · 스케일. 전부 설정에서 읽은 값이다.
        instrument: 월물 코드. 기록용이고 계산에 쓰지 않는다.
        probe_rule_ids: 주문 경로 시험 규칙의 id — 그 진입은 세지 않는다.
        session_ended: 그 세션이 끝났는지. 거짓이면 마지막까지 열린 포지션을
            닫지 않고 ``open_position`` 으로 낸다. 모르면 호출자가 거짓을
            준다 — 끝났다고 가정하면 장중에 가짜 청산이 기록된다.

    Returns:
        ``trades`` · ``totals`` · ``assumptions`` 를 담은 블록. 실현 손익과 같은
        키 이름을 쓰지 않는다(``pnl_krw`` 가 아니라 ``hypothetical_pnl_krw``).
    """
    trades: list[dict[str, Any]] = []
    unpriced: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    open_entry: dict[str, Any] | None = None
    last_priced: tuple[Mapping[str, Any], Decimal] | None = None

    for bar in bars:
        price = _price(bar, contract)
        # SAFETY: 마지막 봉 표시는 **모든** 봉의 종가를 후보로 본다 — 종가는 생산자가 발행한 시장 사실이라 결정이 엔진 것이 아니어도 참이고, 결정 봉만 보면 미청산 포지션이 마지막 «결정» 에서 닫혀 그날 결과가 조용히 틀린다
        if price is not None:
            last_priced = (bar, price)

        kind = bar.get("decision_kind")
        if kind not in (ENTRY_KIND, *EXIT_KINDS):
            continue

        not_engine = _not_an_engine_decision(bar)
        if not_engine is not None:
            skipped.append(_note(bar, kind, not_engine))
            continue
        if kind == ENTRY_KIND and bar.get("decision_rule_id") in probe_rule_ids:
            skipped.append(_note(bar, kind, SKIP_PROBE_ENTRY))
            continue
        if price is None:
            unpriced.append(_note(bar, kind, None))
            continue

        if kind == ENTRY_KIND:
            if open_entry is None:
                open_entry = {"bar": bar, "price": price}
            # 이미 열려 있으면 버린다 — ONE_POSITION_AT_A_TIME.
            continue
        if open_entry is not None:
            trades.append(_trade(open_entry, bar, price, direction, contract))
            open_entry = None

    open_position: dict[str, Any] | None = None
    if open_entry is not None and last_priced is not None:
        bar, price = last_priced
        if session_ended:
            trades.append(
                _trade(open_entry, bar, price, direction, contract, forced=True)
            )
        else:
            open_position = _open_position(open_entry, bar, price, direction, contract)

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
        # 세션이 끝났는지 — 화면이 «확정» 과 «평가» 를 가르는 근거다.
        "session_ended": session_ended,
        "trades": trades,
        "totals": {
            "trades": len(trades),
            "wins": sum(1 for t in trades if Decimal(t["points"]) > 0),
            # 거래가 없는 날의 합계는 **0 원이 아니라 «없음»** 이다. 0 을 적으면
            # 화면이 «오늘 ±0 원» 으로 그리고, 그것은 «아무 신호도 없었다» 와
            # 전혀 다른 말이다.
            "points": _num(total_points) if trades else None,
            "hypothetical_pnl_krw": _num(total_krw) if trades else None,
            "forced_closes": sum(1 for t in trades if t["forced_close"]),
        },
        # 아직 닫히지 않은 포지션의 평가 — 위 합계에 **들어 있지 않다**. 끝난
        # 세션에서는 언제나 ``None`` 이다(그때는 마지막 봉에서 닫는다).
        "open_position": open_position,
        # 결정은 엔진의 것인데 세지 않은 봉 — 사유와 함께. 비어 있지 않으면 위의
        # 수는 그 봉들을 **빼고** 센 것이다.
        "skipped_decisions": skipped,
        # 결정은 있었는데 종가를 읽지 못한 봉. 비어 있는 것이 정상이고, 비어 있지
        # 않으면 위의 수는 그 봉들을 **빼고** 센 것이다.
        "unpriced_decisions": unpriced,
    }


def _open_position(
    entry: Mapping[str, Any],
    as_of_bar: Mapping[str, Any],
    as_of_price: Decimal,
    direction: str,
    contract: Contract,
) -> dict[str, Any]:
    """아직 닫히지 않은 포지션을 마지막 봉 종가로 **평가**한 것.

    거래가 아니다. 키 이름이 전부 다르고(``unrealized_pnl_krw``), ``basis`` 가
    무엇에 맞춰 평가했는지를 말한다 — 이 수를 왕복·승·합계에 더하면 끝나지 않은
    일을 끝났다고 세는 것이 된다.
    """
    entry_bar = entry["bar"]
    entry_price: Decimal = entry["price"]
    points = _points(entry_price, as_of_price, direction)
    return {
        "entry_time_kst": entry_bar.get("time_kst"),
        "entry_rule_id": entry_bar.get("decision_rule_id"),
        "entry_price_points": _num(entry_price),
        "as_of_time_kst": as_of_bar.get("time_kst"),
        "as_of_price_points": _num(as_of_price),
        "points": _num(points),
        "unrealized_pnl_krw": _num(points * Decimal(contract.multiplier_krw_per_point)),
        "basis": OPEN_MARK_BASIS,
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
