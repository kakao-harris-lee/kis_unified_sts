"""S3 — 리플레이가 포지션을 시뮬레이션하고, 가상 손익이 **그 체결**을 센다(계획 P4 §4 S3)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from tools.tos_cp3 import hypothetical_pnl as hp
from tools.tos_cp3 import replay as rp

REPO_ROOT = Path(__file__).resolve().parents[2]

SHIPPED_TREE = REPO_ROOT / "config" / "tos_runtime" / "cp3-setup-d-stock-000660"
SYMBOL = "000660"
STOP_RULE_ID = "R5-STOP-LOSS"
#: 합성 봉은 한 봉에 ±50(≈5bp)씩 움직인다 — 진입 다음 봉의 역행에서 반드시 걸리는 폭을
#: 골라, 손절이 **실제로 발화하는** 구간을 만든다.
STOP_LOSS_BP = -1

#: 트리가 선언한 체결가 필드의 배수(``fields.yaml::publish`` 의 ``close_x100``).
PRICE_SCALE = 100

#: 트리의 ``broker_scopes.yaml`` 이 선언한 **상대** 경로. 트리를 저장소 밖으로 복사하면
#: 이 경로가 풀리지 않으므로 사본과 ``RENDER.yaml`` 의 앵커를 함께 절대 경로로 바꾼다.
BROKER_PROFILE_REL = (
    "../../../docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml"
)

_FLAT_GUARD = """        - left:
            ref: [capsule, position, side]
          op: EQ
          right:
            const: "FLAT"
"""

_STOP_RULE = f"""    - all_of:
        - left:
            ref: [capsule, position, side]
          op: NE
          right:
            const: "FLAT"
        - left:
            ref: [capsule, position, unrealized_bp]
          op: LE
          right:
            ref: [config, stop_loss_bp]
      decision:
        kind: FLAT
        rationale: >-
          {STOP_RULE_ID}: the declared stop is reached — go flat.
        target:
          kind: FLAT
          account: *account
          instrument: *instrument
          direction: SHORT
          position_effect: CLOSE
          rationale: >-
            {STOP_RULE_ID}: close the long at its declared stop.
"""

#: 출하 트리의 두 번째 규칙(VWAP 복귀 청산)이 시작하는 자리 — 손절 규칙을 그 앞에 끼운다.
_VWAP_RULE_HEAD = """    - all_of:
        - left:
            ref: [capsule, resolved_values, vwap_reverted]
"""

SESSIONS = (date(2026, 9, 14), date(2026, 9, 15))
BARS_PER_SESSION = 380


def _frame() -> pd.DataFrame:
    """합성 주식 분봉 두 세션 — 삼각파라 세션 VWAP 왕복이 생기고 값이 결정론적이다."""
    rows: list[dict[str, Any]] = []
    price = 100_000.0
    for day in SESSIONS:
        opening = datetime(day.year, day.month, day.day, 9, 0)
        for minute in range(BARS_PER_SESSION):
            price += 50 if (minute // 11) % 2 == 0 else -50
            rows.append(
                {
                    "timestamp": opening + timedelta(minutes=minute),
                    "open": price,
                    "high": price + 50,
                    "low": price - 50,
                    "close": price,
                    "volume": 100 + minute,
                }
            )
    return pd.DataFrame(rows)


def _position_tree(root: Path) -> Path:
    """출하 트리 사본에 포지션 이름공간과 손절 규칙 하나를 더한 tenant 트리."""
    import shutil

    tree = root / "cp3-setup-d-stock-000660"
    shutil.copytree(SHIPPED_TREE, tree)

    marketfeed = tree / "marketfeed.yaml"
    marketfeed.write_text(
        marketfeed.read_text(encoding="utf-8")
        + "\nposition_context:\n  enabled: true\n  bar_interval_ms: 60000\n",
        encoding="utf-8",
    )
    strategy = tree / "strategies" / "setup_d_long.strategy.yaml"
    text = strategy.read_text(encoding="utf-8")
    text = text.replace(
        "  rules:\n    - all_of:\n", f"  rules:\n    - all_of:\n{_FLAT_GUARD}", 1
    )
    # SAFETY: 손절 규칙은 진입 **뒤**, 나머지 청산 **앞**에 넣는다 — `*account` 별칭은
    # 첫 규칙의 target 에서 정의되므로 더 앞에 두면 YAML 이 정의 전 별칭을 만나고,
    # 더 뒤에 두면 기존 VWAP 청산이 먼저 맞아 손절이 한 번도 발화하지 않는다.
    text = text.replace(_VWAP_RULE_HEAD, f"{_STOP_RULE}{_VWAP_RULE_HEAD}", 1)
    strategy.write_text(text, encoding="utf-8")

    bindings = tree / "strategy_bindings.yaml"
    bindings.write_text(
        bindings.read_text(encoding="utf-8") + f"      stop_loss_bp: {STOP_LOSS_BP}\n",
        encoding="utf-8",
    )
    absolute = REPO_ROOT / BROKER_PROFILE_REL.removeprefix("../../../")
    for name in ("broker_scopes.yaml", "RENDER.yaml"):
        path = tree / name
        path.write_text(
            path.read_text(encoding="utf-8").replace(BROKER_PROFILE_REL, str(absolute)),
            encoding="utf-8",
        )
    return tree


@pytest.fixture(scope="module")
def enabled(tmp_path_factory: pytest.TempPathFactory) -> rp.ReplayResult:
    """포지션을 켠 트리를 합성 봉으로 한 번 리플레이한 결과(모듈 전체가 공유)."""
    tree = _position_tree(tmp_path_factory.mktemp("position-tree"))
    return rp.replay(tree, symbol=SYMBOL, bars=_frame(), min_bars_per_day=0)


@pytest.fixture(scope="module")
def disabled() -> rp.ReplayResult:
    """같은 봉으로 출하(꺼진) 트리를 리플레이한 결과 — 비교의 기준선."""
    return rp.replay(
        "cp3-setup-d-stock-000660", symbol=SYMBOL, bars=_frame(), min_bars_per_day=0
    )


# ---------------------------------------------------------------------------
# 켠 트리
# ---------------------------------------------------------------------------


def test_the_replay_simulates_a_position_and_says_so(
    enabled: rp.ReplayResult,
) -> None:
    """머리 한 줄이 체결 모델과 «세션을 넘어 유지된다» 를 같이 말한다."""
    assert enabled.position_mode == rp.SIMULATED_MODE
    text = rp.render_text(enabled)
    assert rp.SIMULATED_POSITION in text
    assert rp.NO_POSITION not in text
    assert "세션 경계에서 초기화되지 않는다" in text
    assert "전량 체결" in text


def test_the_declared_stop_rule_can_fire_only_because_the_position_is_visible(
    enabled: rp.ReplayResult,
) -> None:
    """꺼진 트리에서는 그 규칙의 비교가 전부 거짓이므로 한 봉도 발화하지 않는다."""
    fired = {
        bar["decision_rule_id"] for bar in enabled.bars if bar.get("decision_rule_id")
    }
    assert fired <= {
        "R0-DEFAULT-NO-ACTION",
        "R1-ENTRY-LONG",
        "R2-EXIT-VWAP-REVERTED",
        "R3-EXIT-EOD",
        STOP_RULE_ID,
    }
    held = [
        bar
        for bar in enabled.bars
        if (bar.get("position") or {}).get("side") not in (None, "FLAT")
    ]
    assert held, "진입이 한 번도 없으면 손절 규칙을 시험하지 못한다"
    stops = [bar for bar in enabled.bars if bar.get("decision_rule_id") == STOP_RULE_ID]
    assert stops, "포지션이 보이지 않으면 이 규칙은 영원히 거짓이다 — 발화가 증거다"
    for bar in stops:
        position = bar["position"]
        assert position["side"] == "LONG"
        assert position["unrealized_bp"] <= STOP_LOSS_BP
    assert all(bar.get("position_source") == rp.SIMULATED_MODE for bar in enabled.bars)


def test_the_hypothetical_pnl_counts_exactly_the_simulated_fills(
    enabled: rp.ReplayResult,
) -> None:
    """체결 모델은 하나다 — 왕복 표와 합계가 같은 진입·청산을 말한다(계획 §4 S3)."""
    trips = enabled.round_trips
    trades = enabled.pnl["trades"]
    assert trips, "시뮬레이션이 왕복을 하나도 내지 않으면 비교할 것이 없다"
    assert len(trades) == len(trips)
    for trip, trade in zip(trips, trades, strict=True):
        assert trade["entry_time_kst"] == trip["entry_time_kst"]
        assert trade["exit_time_kst"] == trip["exit_time_kst"]
        assert trade["entry_rule_id"] == trip["entry_rule_id"]
        assert trade["exit_rule_id"] == trip["exit_rule_id"]
        assert Decimal(trade["entry_price_points"]) * PRICE_SCALE == trip["entry_price"]
        assert Decimal(trade["exit_price_points"]) * PRICE_SCALE == trip["exit_price"]


def test_the_round_trip_times_carry_their_date(enabled: rp.ReplayResult) -> None:
    """여러 날을 한 번에 도는 리플레이에서 «09:41» 만으로는 어느 날인지 알 수 없다."""
    for trip in enabled.round_trips:
        assert str(trip["entry_time_kst"]).startswith("2026-09-")
        assert str(trip["exit_time_kst"]).startswith("2026-09-")


def test_the_golden_header_of_an_enabled_tree_names_the_position(
    enabled: rp.ReplayResult,
) -> None:
    """정답 머리가 포지션 설정을 적는다 — 설정이 바뀌면 diff 가 먼저 말한다."""
    header = dict(rp.golden_header(enabled))
    assert header["position"] == rp.SIMULATED_MODE
    assert header["position_price_field"] == "close_x100"
    assert header["position_bar_interval_ms"] == "60000"
    assert header["position_held_qty"] == "1"
    assert header["position_round_trips"] == str(len(enabled.round_trips))


def test_the_output_counts_the_decisions_live_may_not_reproduce(
    enabled: rp.ReplayResult,
) -> None:
    """공백의 크기를 말로만 적지 않는다 — 다음 단계가 이 표에서 임계를 고른다."""
    gap = enabled.live_gap
    assert set(gap) == {rp.GAP_REENTRY_NEXT_BAR, rp.GAP_EXIT_FIRST_VISIBLE_BAR}
    # 첫 보인 봉에서 닫힌 왕복은 왕복 전체의 부분집합이고, 재진입은 그 왕복 수를 넘지 않는다.
    assert 0 <= gap[rp.GAP_EXIT_FIRST_VISIBLE_BAR] <= len(enabled.round_trips)
    assert 0 <= gap[rp.GAP_REENTRY_NEXT_BAR] <= len(enabled.round_trips)
    # 이 합성 경로는 청산 바로 다음 봉에서 다시 진입 창이 열린다 — 0 이면 세지 않은 것이다.
    assert gap[rp.GAP_REENTRY_NEXT_BAR] > 0
    text = rp.render_text(enabled)
    assert f"{rp.LIVE_GAP_LABEL}: {rp.GAP_REENTRY_NEXT_BAR} " in text
    assert "전송이 미결인 봉에 포지션 이름공간이 없어" in text
    header = dict(rp.golden_header(enabled))
    assert header[f"position_{rp.GAP_REENTRY_NEXT_BAR}"] == str(
        gap[rp.GAP_REENTRY_NEXT_BAR]
    )
    assert header[f"position_{rp.GAP_EXIT_FIRST_VISIBLE_BAR}"] == str(
        gap[rp.GAP_EXIT_FIRST_VISIBLE_BAR]
    )


def test_the_published_fill_model_line_carries_lives_absence_gap(
    enabled: rp.ReplayResult,
) -> None:
    """머리 한 줄이 «라이브와 같다» 로 읽히면 다음 단계가 과대평가된 임계를 고른다."""
    line = enabled.position_line
    assert "전송이 미결인 동안" in line
    assert "side EQ FLAT" in line
    assert line in rp.render_text(enabled)


# ---------------------------------------------------------------------------
# 꺼진 트리 — 바이트 동일
# ---------------------------------------------------------------------------


def test_an_off_tree_keeps_the_no_position_sentence_and_no_position_header(
    disabled: rp.ReplayResult,
) -> None:
    """포지션을 켜지 않은 트리의 출력과 정답 머리는 S3 전과 같다."""
    assert disabled.position_mode is None
    assert disabled.round_trips == []
    text = rp.render_text(disabled)
    assert rp.NO_POSITION in text
    assert rp.SIMULATED_POSITION not in text
    assert "시뮬레이션 체결" not in text
    assert rp.LIVE_GAP_LABEL not in text
    assert not [key for key, _value in rp.golden_header(disabled) if "position" in key]


# ---------------------------------------------------------------------------
# 가상 손익 — 체결을 주지 않으면 코드 경로가 그대로다
# ---------------------------------------------------------------------------

_CONTRACT = hp.Contract(
    name="test", multiplier_krw_per_point=1, price_field="close_x100", price_scale=100
)


def _bar(time_kst: str, close: int, kind: str | None, rule_id: str | None) -> dict:
    """결정 짝짓기 경로가 읽는 모양의 봉 하나."""
    return {
        "time_kst": time_kst,
        "counted": True,
        "decision_kind": kind,
        "decision_rule_id": rule_id,
        "fields": {"close_x100": close},
    }


_PAIRED_BARS = (
    _bar("09:00", 100_000, "ACTION", "R1"),
    _bar("09:01", 100_500, None, None),
    _bar("09:02", 101_000, "FLAT", "R2"),
)


def test_omitting_fills_is_the_decision_pairing_path_unchanged() -> None:
    """꺼진 트리는 ``fills`` 를 주지 않는다 — 그 경로의 출력은 S3 전과 같다."""
    without = hp.build_hypothetical_pnl(
        _PAIRED_BARS, direction=hp.LONG, contract=_CONTRACT
    )
    explicit_none = hp.build_hypothetical_pnl(
        _PAIRED_BARS, direction=hp.LONG, contract=_CONTRACT, fills=None
    )
    assert without == explicit_none
    assert [(t["entry_time_kst"], t["exit_time_kst"]) for t in without["trades"]] == [
        ("09:00", "09:02")
    ]
    assert without["totals"] == {
        "trades": 1,
        "wins": 1,
        "points": "10",
        "hypothetical_pnl_krw": "10",
        "forced_closes": 0,
    }
    assert without["open_position"] is None
    assert (without["skipped_decisions"], without["unpriced_decisions"]) == ([], [])


def test_given_fills_the_decisions_are_not_paired_again() -> None:
    """체결을 주면 같은 봉들을 다시 짝짓지 않는다 — 두 체결 모델을 만들지 않는다."""
    document = hp.build_hypothetical_pnl(
        _PAIRED_BARS,
        direction=hp.LONG,
        contract=_CONTRACT,
        fills={
            "round_trips": [
                {
                    "entry_time_kst": "09:00",
                    "entry_rule_id": "R1",
                    "entry_price": 100_000,
                    "exit_time_kst": "09:01",
                    "exit_rule_id": STOP_RULE_ID,
                    "exit_price": 99_000,
                }
            ],
            "open_entry": None,
        },
    )
    assert [
        (t["entry_time_kst"], t["exit_time_kst"], t["exit_rule_id"], t["points"])
        for t in document["trades"]
    ] == [("09:00", "09:01", STOP_RULE_ID, "-10")]
    assert document["totals"]["trades"] == 1
    assert document["open_position"] is None


def test_an_open_simulated_fill_is_forced_closed_on_an_ended_session() -> None:
    """미청산 체결의 마지막 봉 처리는 결정 짝짓기와 **같은** 관례를 쓴다."""
    document = hp.build_hypothetical_pnl(
        _PAIRED_BARS,
        direction=hp.LONG,
        contract=_CONTRACT,
        session_ended=True,
        fills={
            "round_trips": [],
            "open_entry": {
                "entry_time_kst": "09:00",
                "entry_rule_id": "R1",
                "entry_price": 100_000,
            },
        },
    )
    assert len(document["trades"]) == 1
    trade = document["trades"][0]
    assert (trade["exit_time_kst"], trade["forced_close"]) == ("09:02", True)
    assert trade["forced_close_reason"] == hp.FORCED_CLOSE_REASON
    assert document["open_position"] is None


def test_an_open_simulated_fill_is_marked_not_closed_while_the_session_runs() -> None:
    """장중 내보내기는 열린 포지션을 거래로 세지 않는다 — 시뮬레이션 체결도 같다."""
    document = hp.build_hypothetical_pnl(
        _PAIRED_BARS,
        direction=hp.LONG,
        contract=_CONTRACT,
        session_ended=False,
        fills={
            "round_trips": [],
            "open_entry": {
                "entry_time_kst": "09:00",
                "entry_rule_id": "R1",
                "entry_price": 100_000,
            },
        },
    )
    assert document["trades"] == []
    assert document["open_position"] is not None
    assert document["open_position"]["basis"] == hp.OPEN_MARK_BASIS
