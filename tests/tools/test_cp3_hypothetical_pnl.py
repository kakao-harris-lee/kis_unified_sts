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
) -> dict[str, Any]:
    fields: dict[str, Any] = {} if close_x100 is None else {"close_x100": close_x100}
    return {
        "time_kst": time_kst,
        "decision_kind": kind,
        "decision_rule_id": rule_id,
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
