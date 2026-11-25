"""``tools/tos_cp3/hypothetical_pnl.py`` — 판단 전용 tenant 의 «체결됐다면» 손익.

순수 함수라 손으로 쓴 봉 몇 개로 경계를 통째로 고정한다. 실 세션으로 한 번 더
보는 것은 ``test_cp3_export_bars.py`` 쪽이다.
"""

from __future__ import annotations

from typing import Any

import pytest

from tools.tos_cp3 import hypothetical_pnl as hp

#: 실 선물 tenant 의 계약 사실 그대로 — `A05612` 는 KOSPI200 **미니**(배수 50,000)
#: 이고 종가는 `close_x100` 에 100 배로 실린다.
MINI = hp.Contract(
    name="kospi200_mini",
    multiplier_krw_per_point=50_000,
    price_field="close_x100",
    price_scale=100,
)


def bar(
    time_kst: str,
    close_x100: int | None,
    *,
    kind: str | None = None,
    rule_id: str | None = None,
    counted: bool = True,
    disagrees: bool = False,
) -> dict[str, Any]:
    """실 바 문서의 봉 한 줄 — ``counted`` 까지 포함해서.

    기본이 ``counted=True`` 인 이유: 실제 내보낸 문서에서 결정을 가진 봉은 거의
    전부 엔진 view 로 평가된 봉이고, 그것이 유일하게 셀 수 있는 결정이다.
    """
    fields: dict[str, Any] = {} if close_x100 is None else {"close_x100": close_x100}
    return {
        "time_kst": time_kst,
        "decision_kind": kind,
        "decision_rule_id": rule_id,
        "counted": counted,
        "decision_disagrees": disagrees,
        "fields": fields,
    }


def test_a_long_round_trip_is_exit_minus_entry_times_the_multiplier() -> None:
    """진입 735.64 → 청산 738.58 = +2.94 포인트 × 50,000 = +147,000 원."""
    out = hp.build_hypothetical_pnl(
        [
            bar("09:13", 73_500),
            bar("09:14", 73_564, kind="ACTION", rule_id="R1-ENTRY-LONG"),
            bar("09:30", 73_700),
            bar("09:50", 73_858, kind="FLAT", rule_id="R2-EXIT-VWAP-REVERTED"),
        ],
        direction=hp.LONG,
        contract=MINI,
        instrument="A05612",
    )
    (trade,) = out["trades"]
    assert trade["entry_price_points"] == "735.64"
    assert trade["exit_price_points"] == "738.58"
    assert trade["points"] == "2.94"
    assert trade["hypothetical_pnl_krw"] == "147000"
    assert trade["forced_close"] is False
    assert out["totals"] == {
        "trades": 1,
        "wins": 1,
        "points": "2.94",
        "hypothetical_pnl_krw": "147000",
        "forced_closes": 0,
    }


def test_a_short_is_the_exact_mirror_of_the_same_prices() -> None:
    """비협상 규칙 «long/short symmetry» — 부호를 빠뜨리면 SHORT 성적이 뒤집힌다.

    같은 두 가격에 SHORT 로 들어갔다면 손익은 정확히 부호만 반대여야 한다.
    """
    bars = [
        bar("09:14", 73_564, kind="ACTION", rule_id="R1-ENTRY-SHORT"),
        bar("09:50", 73_858, kind="FLAT", rule_id="R2-EXIT-VWAP-REVERTED"),
    ]
    long_out = hp.build_hypothetical_pnl(bars, direction=hp.LONG, contract=MINI)
    short_out = hp.build_hypothetical_pnl(bars, direction=hp.SHORT, contract=MINI)

    assert short_out["trades"][0]["points"] == "-2.94"
    assert short_out["trades"][0]["hypothetical_pnl_krw"] == "-147000"
    assert short_out["totals"]["wins"] == 0
    assert long_out["totals"]["wins"] == 1
    assert float(short_out["totals"]["hypothetical_pnl_krw"]) == -float(
        long_out["totals"]["hypothetical_pnl_krw"]
    )


def test_an_entry_while_a_position_is_open_is_ignored() -> None:
    """한 계약만 든다는 가정이다 — 쌓으면 가정도 수도 다른 것이 된다."""
    out = hp.build_hypothetical_pnl(
        [
            bar("09:14", 73_500, kind="ACTION", rule_id="R1-ENTRY-LONG"),
            bar("09:20", 73_000, kind="ACTION", rule_id="R1-ENTRY-LONG"),
            bar("09:50", 73_600, kind="FLAT", rule_id="R2-EXIT-VWAP-REVERTED"),
        ],
        direction=hp.LONG,
        contract=MINI,
    )
    (trade,) = out["trades"]
    # 첫 진입만 쓴다 — 두 번째(더 좋은) 가격을 쓰면 수가 조용히 좋아진다.
    assert trade["entry_price_points"] == "735"
    assert trade["points"] == "1"


def test_an_exit_with_no_open_position_is_not_a_trade() -> None:
    """진입 전의 FLAT 판단(장 초반 매 봉)이 거래가 되면 안 된다."""
    out = hp.build_hypothetical_pnl(
        [
            bar("08:48", 74_524, kind="FLAT", rule_id="R2-EXIT-VWAP-REVERTED"),
            bar("08:50", 74_510, kind="FLAT", rule_id="R2-EXIT-VWAP-REVERTED"),
        ],
        direction=hp.LONG,
        contract=MINI,
    )
    assert out["trades"] == []
    assert out["totals"]["trades"] == 0


def test_a_position_still_open_at_the_last_bar_is_closed_and_flagged() -> None:
    """안 닫으면 그날이 «진입만 있고 결과 없음» 으로 빠져 조용히 좋아 보인다."""
    out = hp.build_hypothetical_pnl(
        [
            bar("09:14", 73_500, kind="ACTION", rule_id="R1-ENTRY-LONG"),
            bar("15:19", 73_200),
            bar("15:20", 73_100, kind="ACTION", rule_id="R1-ENTRY-LONG"),
        ],
        direction=hp.LONG,
        contract=MINI,
    )
    (trade,) = out["trades"]
    assert trade["forced_close"] is True
    assert trade["forced_close_reason"] == hp.FORCED_CLOSE_REASON
    # 강제 청산에는 청산 규칙이 없다 — 규칙이 시킨 적 없으므로 비운다.
    assert trade["exit_rule_id"] is None
    assert trade["exit_time_kst"] == "15:20"
    assert trade["points"] == "-4"
    assert out["totals"]["forced_closes"] == 1


def test_the_forced_close_uses_the_last_bar_not_the_last_decision_bar() -> None:
    """마지막 **결정** 봉에서 닫으면 그 뒤의 장을 통째로 버린다.

    진입이 그날의 마지막 결정이면(그 뒤는 전부 NO_ACTION) 결정 봉만 보는 코드는
    진입가 = 청산가로 0 포인트를 내고 «본전» 이라고 적는다. 실제로는 그 뒤 59분
    동안 20 포인트가 움직였다. 종가는 생산자가 발행한 시장 사실이라, 결정이
    엔진의 것이 아니어도 마지막 표시로 쓸 수 있다.
    """
    out = hp.build_hypothetical_pnl(
        [
            bar("10:00", 70_000, kind="ACTION", rule_id="R1-ENTRY-LONG"),
            bar("10:01", 71_000),
            bar("10:59", 72_000),
        ],
        direction=hp.LONG,
        contract=MINI,
    )
    (trade,) = out["trades"]
    assert trade["entry_price_points"] == "700"
    assert trade["exit_time_kst"] == "10:59"
    assert trade["exit_price_points"] == "720"
    assert trade["points"] == "20"
    assert trade["hypothetical_pnl_krw"] == "1000000"
    assert trade["forced_close"] is True


def test_the_last_bar_mark_may_come_from_a_bar_the_engine_did_not_decide() -> None:
    """표시는 **가격**이고 가격은 참이다 — 결정만 엔진의 것을 요구한다."""
    out = hp.build_hypothetical_pnl(
        [
            bar("10:00", 70_000, kind="ACTION", rule_id="R1-ENTRY-LONG"),
            bar("10:30", 72_000, kind="FLAT", rule_id="R2", counted=False),
        ],
        direction=hp.LONG,
        contract=MINI,
    )
    # 그 FLAT 은 청산으로 세지 않았지만(엔진 결정이 아니다), 그 봉의 종가는
    # 마지막 표시로 쓰였다.
    (trade,) = out["trades"]
    assert trade["forced_close"] is True
    assert trade["exit_price_points"] == "720"
    assert [s["reason"] for s in out["skipped_decisions"]] == [
        hp.SKIP_NOT_ENGINE_COUNTED
    ]


def test_a_decision_bar_without_a_readable_close_is_named_not_guessed() -> None:
    """가격을 모르는 봉은 세지 않고, 세지 않았다는 사실을 문서가 말한다."""
    out = hp.build_hypothetical_pnl(
        [
            bar("09:14", None, kind="ACTION", rule_id="R1-ENTRY-LONG"),
            bar("09:20", 73_500, kind="ACTION", rule_id="R1-ENTRY-LONG"),
            bar("09:50", 73_600, kind="FLAT", rule_id="R2-EXIT-VWAP-REVERTED"),
        ],
        direction=hp.LONG,
        contract=MINI,
    )
    assert out["unpriced_decisions"] == [
        {"time_kst": "09:14", "decision_kind": "ACTION", "rule_id": "R1-ENTRY-LONG"}
    ]
    (trade,) = out["trades"]
    assert trade["entry_time_kst"] == "09:20"


def test_a_withheld_bar_carries_no_decision_and_so_no_trade() -> None:
    """보류 봉은 ``decision_kind`` 가 없다 — 짝짓기에 들어오지 않는다."""
    out = hp.build_hypothetical_pnl(
        [bar("09:14", 73_500), bar("09:20", 73_600)],
        direction=hp.LONG,
        contract=MINI,
    )
    assert out["trades"] == []
    assert out["unpriced_decisions"] == []


def test_a_bar_the_engine_never_decided_is_not_a_trade() -> None:
    """증거를 잇지 못한 봉의 ``decision_kind`` 는 **점검이 다시 도출한** 값이다.

    그 진입으로 손익을 세면 1,000,000 원이 전략의 성적인 것처럼 나오는데, 엔진은
    그 주문을 낸 적도 내려 한 적도 없다. 버리고, 버렸다는 사실을 남긴다.
    """
    out = hp.build_hypothetical_pnl(
        [
            bar("09:14", 70_000, kind="ACTION", rule_id="R1-ENTRY-LONG", counted=False),
            bar("09:50", 72_000, kind="FLAT", rule_id="R2-EXIT-VWAP-REVERTED"),
        ],
        direction=hp.LONG,
        contract=MINI,
    )
    assert out["trades"] == []
    assert out["totals"]["trades"] == 0
    assert out["skipped_decisions"] == [
        {
            "time_kst": "09:14",
            "decision_kind": "ACTION",
            "rule_id": "R1-ENTRY-LONG",
            "reason": hp.SKIP_NOT_ENGINE_COUNTED,
        }
    ]


def test_a_bar_whose_decision_disagrees_with_the_engine_is_not_a_trade() -> None:
    """어느 쪽이 참인지 여기서 정할 수 없다 — 그러면 세지 않는 것이 맞다."""
    out = hp.build_hypothetical_pnl(
        [
            bar("09:14", 70_000, kind="ACTION", rule_id="R1", disagrees=True),
            bar("09:50", 72_000, kind="FLAT", rule_id="R2"),
        ],
        direction=hp.LONG,
        contract=MINI,
    )
    assert out["trades"] == []
    assert [s["reason"] for s in out["skipped_decisions"]] == [hp.SKIP_ENGINE_DISAGREES]


def test_a_probe_entry_is_not_a_strategy_entry() -> None:
    """``R4-M2-PROBE-ENTRY-LONG`` 은 주문 경로 시험이다 — 성적에 섞이면 거짓이 된다."""
    bars = [
        bar("09:14", 70_000, kind="ACTION", rule_id="R4-M2-PROBE-ENTRY-LONG"),
        bar("09:50", 72_000, kind="FLAT", rule_id="R2-EXIT-VWAP-REVERTED"),
    ]
    out = hp.build_hypothetical_pnl(
        bars,
        direction=hp.LONG,
        contract=MINI,
        probe_rule_ids=frozenset({"R4-M2-PROBE-ENTRY-LONG"}),
    )
    assert out["trades"] == []
    assert [s["reason"] for s in out["skipped_decisions"]] == [hp.SKIP_PROBE_ENTRY]

    # 같은 봉을 프로브로 선언하지 않으면 그대로 거래가 된다 — 분기가 실제로
    # probe 목록을 보는지 확인한다(공허한 검사 방지).
    assert hp.build_hypothetical_pnl(bars, direction=hp.LONG, contract=MINI)["trades"]


def test_a_session_with_no_trade_reports_no_total_rather_than_zero_won() -> None:
    """«0원» 은 «오늘 ±0» 으로 읽힌다. «신호가 없었다» 와 전혀 다른 말이다."""
    out = hp.build_hypothetical_pnl([], direction=hp.SHORT, contract=MINI)
    assert out["totals"]["trades"] == 0
    assert out["totals"]["wins"] == 0
    assert out["totals"]["points"] is None
    assert out["totals"]["hypothetical_pnl_krw"] is None
    assert out["totals"]["forced_closes"] == 0


def test_every_number_travels_with_its_assumptions() -> None:
    """수만 떼어 그릴 수 없게, 가정은 문서 안에 값과 **함께** 있다."""
    out = hp.build_hypothetical_pnl([], direction=hp.LONG, contract=MINI)
    assert out["hypothetical"] is True
    assert out["assumptions"] == list(hp.ASSUMPTIONS)
    assert "FILL_ALWAYS_ASSUMED" in out["assumptions"]
    assert "NO_FEES" in out["assumptions"]
    assert "NO_SLIPPAGE" in out["assumptions"]


def test_no_key_here_is_named_like_a_realized_pnl_field() -> None:
    """실현 손익과 같은 키 이름이면 언젠가 합산된다.

    ``symbols/today.json`` 의 실현 손익은 ``pnl_krw`` 다. 이 블록의 수는 전부
    ``hypothetical_`` 를 달고 있어서, 두 문서를 한 화면에서 합치는 코드가
    **이름만 보고** 섞을 수 없다.
    """
    out = hp.build_hypothetical_pnl(
        [
            bar("09:14", 73_500, kind="ACTION", rule_id="R1"),
            bar("09:50", 73_600, kind="FLAT", rule_id="R2"),
        ],
        direction=hp.LONG,
        contract=MINI,
    )
    assert "pnl_krw" not in out["totals"]
    assert "pnl_krw" not in out["trades"][0]
    assert out["totals"]["hypothetical_pnl_krw"]


@pytest.mark.parametrize("scale,expected", [(100, "735"), (1, "73500")])
def test_the_scale_comes_from_config_not_from_a_literal(
    scale: int, expected: str
) -> None:
    """배수를 100 틀리게 읽으면 틀려 보이지 않는다 — 아주 좋은 날처럼 보인다."""
    contract = hp.Contract(
        name="x",
        multiplier_krw_per_point=50_000,
        price_field="close_x100",
        price_scale=scale,
    )
    out = hp.build_hypothetical_pnl(
        [
            bar("09:14", 73_500, kind="ACTION", rule_id="R1"),
            bar("09:50", 73_500, kind="FLAT", rule_id="R2"),
        ],
        direction=hp.LONG,
        contract=contract,
    )
    assert out["trades"][0]["entry_price_points"] == expected
