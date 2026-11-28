"""S3 — 리플레이가 포지션을 시뮬레이션하고, 가상 손익이 **그 체결**을 센다(계획 P4 §4 S3)."""

from __future__ import annotations

import re
import shutil
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import yaml

from tools.tos_cp3 import hypothetical_pnl as hp
from tools.tos_cp3 import replay as rp

REPO_ROOT = Path(__file__).resolve().parents[2]

SHIPPED_TREE = REPO_ROOT / "config" / "tos_runtime" / "cp3-setup-d-stock-000660"
SYMBOL = "000660"

#: 포지션을 **켜지 않은** 출하 트리 — 꺼진 경로의 기준선. S4 가 000660 을 켰으므로
#: 카나리아가 그 자리를 받는다(`test_marketfeed_position_context_config.py` 가 어느 트리가
#: 켜졌는지 고정한다).
OFF_TREE = "cp3-setup-d-stock-005930"
OFF_SYMBOL = "005930"

STOP_RULE_ID = "R5-EXIT-STOP-LOSS"
TARGET_RULE_ID = "R6-EXIT-TAKE-PROFIT"

#: 기본 합성 봉은 한 봉에 ±50(≈5bp)씩 움직이고 11 봉마다 방향이 바뀐다 — 출하 폭(수십 bp)은
#: 이 프레임에서 닿지 않는다. 손절이 **실제로 발화하는** 구간을 만들려고 사본에서만 이
#: 폭으로 좁히고, 목표는 발화하지 않을 만큼 멀리 둔다(손절을 가리지 않게).
TIGHT_STOP_LOSS_BP = -1
UNREACHABLE_TAKE_PROFIT_BP = 100_000

#: 출하 폭(`stop_loss_bp` -100 · `take_profit_bp` +150)에 **둘 다** 닿는 비대칭 삼각파.
#: 오르는 다리보다 내리는 다리가 길어서 목표로 끝나는 왕복과 손절로 끝나는 왕복이 함께
#: 생긴다 — 대칭파에서는 진입이 늘 저점 근처라 `unrealized_bp` 가 출하 손절까지 내려가지
#: 않고, 출하 값을 그대로 쓰는 시험이 **한 봉도 검사하지 않는 빈 루프**가 된다.
REACHING_UP = 200.0
REACHING_DOWN = 300.0

#: 트리가 선언한 체결가 필드의 배수(``fields.yaml::publish`` 의 ``close_x100``).
PRICE_SCALE = 100

#: 트리의 ``broker_scopes.yaml`` 이 선언한 **상대** 경로. 트리를 저장소 밖으로 복사하면
#: 이 경로가 풀리지 않으므로 사본과 ``RENDER.yaml`` 의 앵커를 함께 절대 경로로 바꾼다.
BROKER_PROFILE_REL = (
    "../../../docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml"
)

SESSIONS = (date(2026, 9, 14), date(2026, 9, 15))
BARS_PER_SESSION = 380


def shipped_bindings() -> dict[str, Any]:
    """출하 트리가 선언한 바인딩 그대로 — 임계값을 이 파일에 다시 적지 않는다."""
    document = yaml.safe_load(
        (SHIPPED_TREE / "strategy_bindings.yaml").read_text(encoding="utf-8")
    )
    return dict(document["strategies"]["setup_d_long.strategy"]["bindings"])


def _frame(*, up: float = 50.0, down: float = 50.0) -> pd.DataFrame:
    """합성 주식 분봉 두 세션 — 삼각파라 세션 VWAP 왕복이 생기고 값이 결정론적이다.

    ``up`` 과 ``down`` 이 다르면 비대칭 삼각파다(:data:`REACHING_DOWN` 참조).
    """
    rows: list[dict[str, Any]] = []
    price = 100_000.0
    for day in SESSIONS:
        opening = datetime(day.year, day.month, day.day, 9, 0)
        for minute in range(BARS_PER_SESSION):
            price += up if (minute // 11) % 2 == 0 else -down
            rows.append(
                {
                    "timestamp": opening + timedelta(minutes=minute),
                    "open": price,
                    "high": price + up,
                    "low": price - down,
                    "close": price,
                    "volume": 100 + minute,
                }
            )
    return pd.DataFrame(rows)


def _rebind(path: Path, key: str, value: int) -> None:
    """바인딩 한 줄의 값만 바꾼다 — 덧붙이면 같은 키가 두 번 나와 하나가 조용히 이긴다."""
    text = path.read_text(encoding="utf-8")
    pattern = rf"^(\s*{re.escape(key)}:) *-?\d+$"
    replaced, count = re.subn(
        pattern, rf"\1 {value}", text, count=1, flags=re.MULTILINE
    )
    assert count == 1, f"{path}: {key} 를 한 줄로 찾지 못했다 (출하 트리가 바뀌었다)"
    path.write_text(replaced, encoding="utf-8")


def _narrowed_tree(root: Path, *, stop_bp: int, target_bp: int) -> Path:
    """출하 트리 사본 — 바뀌는 것은 두 임계값**뿐**이다(규칙도 이름공간도 출하 그대로)."""
    tree = root / SHIPPED_TREE.name
    shutil.copytree(SHIPPED_TREE, tree)
    bindings = tree / "strategy_bindings.yaml"
    _rebind(bindings, "stop_loss_bp", stop_bp)
    _rebind(bindings, "take_profit_bp", target_bp)
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
    """출하 트리 — 두 임계값만 이 프레임에서 손절이 걸리는 폭으로 좁힌 사본."""
    tree = _narrowed_tree(
        tmp_path_factory.mktemp("position-tree"),
        stop_bp=TIGHT_STOP_LOSS_BP,
        target_bp=UNREACHABLE_TAKE_PROFIT_BP,
    )
    return rp.replay(tree, symbol=SYMBOL, bars=_frame(), min_bars_per_day=0)


@pytest.fixture(scope="module")
def shipped() -> rp.ReplayResult:
    """임계값까지 **출하 그대로** 돌린 결과 — 두 폭에 닿는 비대칭 프레임으로 돈다."""
    return rp.replay(
        SHIPPED_TREE.name,
        symbol=SYMBOL,
        bars=_frame(up=REACHING_UP, down=REACHING_DOWN),
        min_bars_per_day=0,
    )


@pytest.fixture(scope="module")
def disabled() -> rp.ReplayResult:
    """포지션을 켜지 않은 출하 트리를 같은 봉으로 — 꺼진 경로의 기준선."""
    return rp.replay(OFF_TREE, symbol=OFF_SYMBOL, bars=_frame(), min_bars_per_day=0)


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
        TARGET_RULE_ID,
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
        assert position["unrealized_bp"] <= TIGHT_STOP_LOSS_BP
    assert all(bar.get("position_source") == rp.SIMULATED_MODE for bar in enabled.bars)


def test_the_guarded_entry_never_fires_on_a_bar_that_already_holds(
    enabled: rp.ReplayResult,
) -> None:
    """출하 R1 의 `side EQ "FLAT"` 가드 — 리플레이의 봉별 포지션으로 읽은 그대로."""
    entries = [
        bar for bar in enabled.bars if bar.get("decision_rule_id") == "R1-ENTRY-LONG"
    ]
    assert entries, "진입이 없으면 가드를 시험하지 못한다"
    for bar in entries:
        assert (bar.get("position") or {}).get("side") == "FLAT", bar["time_kst"]


def test_the_shipped_bounds_are_what_the_shipped_tree_replays_with(
    shipped: rp.ReplayResult,
) -> None:
    """임계값을 좁히지 않은 출하 트리에서 두 청산이 **발화하고**, 그 봉이 출하 폭을 지킨다."""
    bounds = shipped_bindings()
    assert shipped.position_mode == rp.SIMULATED_MODE

    def _fired(rule_id: str) -> list[dict[str, Any]]:
        return [b for b in shipped.bars if b.get("decision_rule_id") == rule_id]

    stops, targets = _fired(STOP_RULE_ID), _fired(TARGET_RULE_ID)
    # 두 폭에 닿지 않는 프레임이면 아래 두 루프가 비어 아무것도 시험하지 않는다.
    assert stops and targets, (len(stops), len(targets))
    for bar in stops:
        position = bar["position"]
        assert position["side"] == "LONG", bar["time_kst"]
        assert position["unrealized_bp"] <= bounds["stop_loss_bp"], bar["time_kst"]
    for bar in targets:
        position = bar["position"]
        assert position["side"] == "LONG", bar["time_kst"]
        assert position["unrealized_bp"] >= bounds["take_profit_bp"], bar["time_kst"]


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


def test_the_output_counts_the_entries_the_risk_unit_field_refused(
    enabled: rp.ReplayResult,
) -> None:
    """P4 S5: a field-sized tree opens no entry on a bar live's derivation refuses."""
    refusals = enabled.entry_refusals
    # 이 트리는 고정 N(1/1)이라 두 경로에 닿지 않는다 — 0 이 참이고, 0 도 적힌다.
    assert refusals == {rp.ENTRY_UNIT_UNAVAILABLE: 0, rp.ENTRY_SIZE_DENIED: 0}
    text = rp.render_text(enabled)
    assert (
        f"{rp.ENTRY_REFUSED_LABEL}: {rp.ENTRY_UNIT_UNAVAILABLE} 0 · "
        f"{rp.ENTRY_SIZE_DENIED} 0" in text
    )
