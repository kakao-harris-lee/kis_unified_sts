"""The simulated position replay carries, pinned to a hand-computed scenario (plan P4 S3)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from .._base import Cp3RunnerRefusal
from ..inspect_report import InspectReport, render_json, render_text
from ..inspect_session import inspect_session
from ..position_sim import (
    DECLARED_UNIT_SOURCE,
    DEFAULT_UNIT_SOURCE,
    GAP_EXIT_FIRST_VISIBLE_BAR,
    GAP_REENTRY_NEXT_BAR,
    POSITION_MODE_SIMULATED,
    load_simulation_config,
)
from . import _position_tree as tree

_BASE_AS_OF_MS = 1_794_268_800_000

_MINUTE_MS = 60_000

_ENTRY_PRICE = 100_000


def _journal(
    root: Path,
    prices: Sequence[int | None],
    windows: Sequence[bool],
    *,
    step_ms: int = _MINUTE_MS,
) -> Path:
    """One journal line per ``(price, entry_window)`` pair, one bar apart."""
    lines: list[str] = []
    for index, (price, window) in enumerate(zip(prices, windows, strict=True)):
        fields: dict[str, Any] = {"entry_window": window}
        if price is not None:
            fields[tree.PRICE_FIELD] = price
        lines.append(
            json.dumps(
                {
                    "raw_event_id": f"{tree.INSTRUMENT}:1m:synthetic-{index:05d}",
                    "source_id": "tos-cp3-s3-test/0.1.0",
                    "instrument": tree.INSTRUMENT,
                    "as_of_ms": _BASE_AS_OF_MS + index * step_ms,
                    "fields": fields,
                },
                sort_keys=True,
            )
        )
    path = root / "journal.jsonl"
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    return path


def _inspect(
    root: Path,
    prices: Sequence[int | None],
    windows: Sequence[bool],
    *,
    step_ms: int = _MINUTE_MS,
    **tree_kwargs: Any,
) -> InspectReport:
    """Replay one hand-written bar path against a freshly written tenant tree."""
    config_dir = tree.write_tree(root, **tree_kwargs)
    return inspect_session(
        journal_path=_journal(root, prices, windows, step_ms=step_ms),
        strategy_path=config_dir / "strategies" / tree.STRATEGY_FILE_NAME,
        bindings_path=config_dir / "strategy_bindings.yaml",
        session_name="s3-fixture",
    )


def _decisions(report: InspectReport) -> list[str | None]:
    """The first-match rule id per bar, in journal order."""
    return [row.decision_rule_id for row in report.bars]


def _sides(report: InspectReport) -> list[str | None]:
    """The ``side`` each bar's rules actually read, ``None`` where absent."""
    return [
        None if row.position is None else str(row.position.get("side"))
        for row in report.bars
    ]


_LONG_PRICES: tuple[int, ...] = (
    _ENTRY_PRICE,
    _ENTRY_PRICE,
    99_700,
    99_500,
    99_500,
    99_500,
    99_500,
)
_LONG_WINDOWS: tuple[bool, ...] = (True, False, False, False, False, True, True)


@pytest.fixture
def long_report(tmp_path: Path) -> InspectReport:
    """The seven-bar LONG scenario: entry, stop at the computed bar, re-entry."""
    return _inspect(tmp_path, _LONG_PRICES, _LONG_WINDOWS)


def test_the_entry_bar_itself_is_still_flat(long_report: InspectReport) -> None:
    """Live reads the position before the bar's own decision, so bar N sees FLAT."""
    first = long_report.bars[0]
    assert first.position == {"side": "FLAT", "held_qty": 0}
    assert first.decision_rule_id == tree.ENTRY_RULE_ID


def test_the_position_is_visible_from_the_bar_after_the_fill(
    long_report: InspectReport,
) -> None:
    """Bar N+1 carries the fill: the entry price, one unit, and one bar held."""
    assert long_report.bars[1].position == {
        "side": "LONG",
        "held_qty": 1,
        "entry_price": _ENTRY_PRICE,
        "entry_price_basis": "ORDER",
        "unrealized": 0,
        "unrealized_bp": 0,
        "bars_held": 1,
    }


def test_the_declared_stop_fires_at_the_hand_computed_bar(
    long_report: InspectReport,
) -> None:
    """-30bp holds, -50bp closes: the bound is reached at bar 3, not bar 2."""
    assert long_report.bars[2].position == {
        "side": "LONG",
        "held_qty": 1,
        "entry_price": _ENTRY_PRICE,
        "entry_price_basis": "ORDER",
        "unrealized": -300,
        "unrealized_bp": -30,
        "bars_held": 2,
    }
    assert long_report.bars[2].decision_rule_id == tree.DEFAULT_RULE_ID
    assert long_report.bars[3].position == {
        "side": "LONG",
        "held_qty": 1,
        "entry_price": _ENTRY_PRICE,
        "entry_price_basis": "ORDER",
        "unrealized": -500,
        "unrealized_bp": tree.STOP_LOSS_BP,
        "bars_held": 3,
    }
    assert long_report.bars[3].decision_rule_id == tree.STOP_RULE_ID


def test_the_exit_is_flat_from_the_next_bar_and_re_entry_is_possible(
    long_report: InspectReport,
) -> None:
    """The FLAT fill lands at bar 3's price, so bar 4 is flat and bar 5 re-enters."""
    assert _sides(long_report) == [
        "FLAT",
        "LONG",
        "LONG",
        "LONG",
        "FLAT",
        "FLAT",
        "LONG",
    ]
    assert _decisions(long_report) == [
        tree.ENTRY_RULE_ID,
        tree.DEFAULT_RULE_ID,
        tree.DEFAULT_RULE_ID,
        tree.STOP_RULE_ID,
        tree.DEFAULT_RULE_ID,
        tree.ENTRY_RULE_ID,
        tree.DEFAULT_RULE_ID,
    ]
    assert long_report.bars[6].position == {
        "side": "LONG",
        "held_qty": 1,
        "entry_price": 99_500,
        "entry_price_basis": "ORDER",
        "unrealized": 0,
        "unrealized_bp": 0,
        "bars_held": 1,
    }


def test_the_round_trips_are_the_simulations_own_fills(
    long_report: InspectReport,
) -> None:
    """One closed round trip at the stop, plus the re-entry still open at the end."""
    assert long_report.position_mode == POSITION_MODE_SIMULATED
    assert [
        (
            trip["entry_rule_id"],
            trip["entry_price"],
            trip["exit_rule_id"],
            trip["exit_price"],
            trip["bars_held"],
            trip["unrealized"],
            trip["unrealized_bp"],
        )
        for trip in long_report.round_trips
    ] == [(tree.ENTRY_RULE_ID, _ENTRY_PRICE, tree.STOP_RULE_ID, 99_500, 3, -500, -50)]
    assert long_report.position_open_fill is not None
    assert long_report.position_open_fill["entry_price"] == 99_500


def test_every_row_marks_its_position_as_simulated(long_report: InspectReport) -> None:
    """A reader must never take a replayed position for one the engine recorded."""
    assert {row.position_source for row in long_report.bars} == {
        POSITION_MODE_SIMULATED
    }
    assert long_report.position_simulation is not None
    assert long_report.position_simulation["price_field_key"] == tree.PRICE_FIELD
    assert long_report.position_simulation["bar_interval_ms"] == tree.BAR_INTERVAL_MS
    assert long_report.position_simulation["held_qty_source"] == DEFAULT_UNIT_SOURCE


def test_the_rendered_report_says_the_position_carries_across_sessions(
    long_report: InspectReport,
) -> None:
    """Plan §11 #3: a stock swing is held overnight, so the replay never resets."""
    text = render_text(long_report)
    assert "세션 경계에서 초기화되지 않는다" in text
    document = json.loads(render_json(long_report))
    simulation = document["position"]["simulation"]
    assert "세션 경계에서 초기화되지 않는다" in str(
        simulation["carries_across_sessions"]
    )


def test_the_long_path_counts_no_decision_live_could_not_reproduce(
    long_report: InspectReport,
) -> None:
    """Bar 3's exit is three bars after the entry and bar 5's entry two after the exit."""
    assert long_report.position_live_gap == {
        GAP_REENTRY_NEXT_BAR: 0,
        GAP_EXIT_FIRST_VISIBLE_BAR: 0,
    }
    assert f"{GAP_REENTRY_NEXT_BAR} 0" in render_text(long_report)


def test_a_next_bar_exit_and_the_re_entry_behind_it_are_both_counted(
    tmp_path: Path,
) -> None:
    """Live carries no namespace while a send is unresolved, so these two it may not make."""
    report = _inspect(
        tmp_path,
        (_ENTRY_PRICE, 99_500, 99_500, 99_500),
        (True, False, True, False),
    )
    assert _decisions(report) == [
        tree.ENTRY_RULE_ID,
        tree.STOP_RULE_ID,
        tree.ENTRY_RULE_ID,
        tree.DEFAULT_RULE_ID,
    ]
    assert report.position_live_gap == {
        GAP_REENTRY_NEXT_BAR: 1,
        GAP_EXIT_FIRST_VISIBLE_BAR: 1,
    }
    text = render_text(report)
    assert f"{GAP_EXIT_FIRST_VISIBLE_BAR} 1" in text
    assert "전송이 미결인 봉에 포지션 이름공간이 없어" in text
    document = json.loads(render_json(report))
    assert document["position"]["live_gap"] == {
        GAP_REENTRY_NEXT_BAR: 1,
        GAP_EXIT_FIRST_VISIBLE_BAR: 1,
    }


def test_the_published_fill_model_does_not_claim_parity_with_live(
    long_report: InspectReport,
) -> None:
    """The one sentence a consumer may print alone must carry live's absence gap."""
    simulation = long_report.position_simulation
    assert simulation is not None
    fill_model = str(simulation["fill_model"])
    assert "전송이 미결인 동안" in fill_model
    assert "side EQ FLAT" in fill_model
    assert GAP_EXIT_FIRST_VISIBLE_BAR in fill_model
    note = str(simulation["entry_price_basis_note"])
    assert "EXECUTION" in note and "ORDER" in note
    header = render_text(long_report)
    assert fill_model in header
    assert note in header


def test_an_action_while_already_held_changes_nothing(tmp_path: Path) -> None:
    """Live halts the second entry at the capacity stage, so replay stacks nothing."""
    report = _inspect(
        tmp_path,
        (_ENTRY_PRICE, 99_900, 99_900, 99_500),
        (True, True, True, False),
        flat_guard=False,
    )
    assert _decisions(report)[:3] == [tree.ENTRY_RULE_ID] * 3
    assert [
        None if row.position is None else row.position.get("entry_price")
        for row in report.bars
    ] == [None, _ENTRY_PRICE, _ENTRY_PRICE, _ENTRY_PRICE]
    assert len(report.round_trips) == 1
    assert report.round_trips[0]["entry_price"] == _ENTRY_PRICE


def test_the_declared_target_fires_at_the_hand_computed_bar(tmp_path: Path) -> None:
    """+80bp is exactly 100_800; +79bp (100_790) is not yet the declared target."""
    report = _inspect(
        tmp_path,
        (_ENTRY_PRICE, 100_790, 100_800),
        (True, False, False),
    )
    assert _decisions(report) == [
        tree.ENTRY_RULE_ID,
        tree.DEFAULT_RULE_ID,
        tree.TARGET_RULE_ID,
    ]
    assert report.bars[1].position is not None
    assert report.bars[1].position["unrealized_bp"] == 79
    assert report.bars[2].position is not None
    assert report.bars[2].position["unrealized_bp"] == tree.TAKE_PROFIT_BP


def test_a_short_tree_fires_the_same_rule_text_on_the_mirrored_path(
    tmp_path: Path,
) -> None:
    """Futures symmetry: unrealized already carries the direction (plan P4 §2 D2)."""
    report = _inspect(
        tmp_path,
        (_ENTRY_PRICE, 100_300, 100_500),
        (True, False, False),
        direction="SHORT",
    )
    assert _sides(report) == ["FLAT", "SHORT", "SHORT"]
    assert report.bars[1].position is not None
    assert report.bars[1].position["unrealized_bp"] == -30
    assert report.bars[2].position is not None
    assert report.bars[2].position["unrealized_bp"] == tree.STOP_LOSS_BP
    assert _decisions(report) == [
        tree.ENTRY_RULE_ID,
        tree.DEFAULT_RULE_ID,
        tree.STOP_RULE_ID,
    ]


def test_an_unusable_price_field_leaves_the_namespace_absent(tmp_path: Path) -> None:
    """Live's PRICE_FIELD_UNUSABLE: no context for that bar, and no state change."""
    report = _inspect(
        tmp_path,
        (_ENTRY_PRICE, None, 99_500),
        (True, False, False),
    )
    assert report.bars[1].position is None
    assert report.bars[1].position_absent_reason == "PRICE_FIELD_UNUSABLE"
    assert report.bars[1].decision_rule_id == tree.DEFAULT_RULE_ID
    assert report.bars[2].position is not None
    assert report.bars[2].position["entry_price"] == _ENTRY_PRICE
    assert report.bars[2].decision_rule_id == tree.STOP_RULE_ID
    assert report.position_absence_counts == {"PRICE_FIELD_UNUSABLE": 1}


def test_the_position_is_held_across_a_session_boundary(tmp_path: Path) -> None:
    """``bars_held`` is wall-clock, so an overnight hold counts the whole gap."""
    gap_ms = 24 * 60 * 60 * 1000
    report = _inspect(
        tmp_path,
        (_ENTRY_PRICE, _ENTRY_PRICE),
        (True, False),
        step_ms=gap_ms,
    )
    assert report.bars[1].position is not None
    assert report.bars[1].position["side"] == "LONG"
    assert report.bars[1].position["bars_held"] == gap_ms // tree.BAR_INTERVAL_MS


def test_a_tree_without_the_block_simulates_no_position(tmp_path: Path) -> None:
    """An absent ``position_context`` block is OFF: no namespace, no column, no block."""
    report = _inspect(
        tmp_path,
        (_ENTRY_PRICE, _ENTRY_PRICE),
        (True, False),
        marketfeed=False,
        position_refs=False,
    )
    assert report.position_mode is None
    assert [row.position for row in report.bars] == [None, None]
    assert report.round_trips == ()
    assert "position  " not in render_text(report)


def test_a_position_ref_with_the_namespace_off_is_refused(tmp_path: Path) -> None:
    """Boot-refusal parity: live refuses this tree, so the inspector refuses it too."""
    with pytest.raises(Cp3RunnerRefusal, match="position_context.enabled"):
        _inspect(
            tmp_path,
            (_ENTRY_PRICE,),
            (True,),
            enabled=False,
        )


def test_an_unnamed_action_direction_is_refused_not_assumed_long(
    tmp_path: Path,
) -> None:
    """The DSL types direction as a free string; a guessed side flips every bp figure."""
    with pytest.raises(Cp3RunnerRefusal, match="direction"):
        _inspect(
            tmp_path,
            (_ENTRY_PRICE,),
            (True,),
            direction="BUY",
        )


def test_the_declared_sizing_bound_is_where_held_qty_comes_from(
    tmp_path: Path,
) -> None:
    """A tree whose OCP is unreadable falls back to one unit, and says which it used."""
    config_dir = tree.write_tree(tmp_path)
    declared = load_simulation_config(config_dir)
    assert declared is not None
    assert (declared.held_qty, declared.held_qty_source) == (1, DEFAULT_UNIT_SOURCE)
    assert declared.held_qty_source != DECLARED_UNIT_SOURCE
