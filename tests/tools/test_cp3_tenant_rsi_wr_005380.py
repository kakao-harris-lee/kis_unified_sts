"""The 005380 tenant's RSI / Williams %R declaration (실험 B) — hermetic."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import yaml

from shared.indicators.fields import load_fields_file
from tools.tos_cp3 import produce_fields as pf
from tools.tos_cp3.produce_fields import OpenAnchor, load_strategy_inputs

REPO_ROOT = Path(__file__).resolve().parents[2]
TREE = REPO_ROOT / "config" / "tos_runtime" / "cp3-setup-d-stock-005380"
LEGACY_STRATEGY_YAML = (
    REPO_ROOT / "config" / "strategies" / "futures" / "setup_d_vwap_reversion.yaml"
)

#: What the declaration publishes, in order. The kernel refuses a poll whole on a missing
#: journal key, so this set is a contract with three other files at once: the tree's
#: ``critical_input_policy.yaml``, its strategy DSL, and ``construction.yaml``'s price key.
PUBLISHED = (
    "open_x100",
    "high_x100",
    "low_x100",
    "close_x100",
    "volume",
    "session_token",
    "vwap_x100",
    "atr14_x100",
    "entry_window",
    "rsi_oversold",
    "wr_oversold",
    "rsi_recovered",
    "eod",
)


@pytest.fixture(scope="module")
def document() -> Any:
    return load_fields_file(TREE / "fields.yaml")


def _by_name(doc: Any) -> dict[str, Any]:
    return {spec.name: spec for spec in doc.fields}


class TestTheDeclaredParameters:
    """The numbers an operator reads in the PR, read back from the file."""

    def test_the_momentum_periods_are_the_reference_defaults(
        self, document: Any
    ) -> None:
        by_name = _by_name(document)
        assert by_name["rsi14"].op_name == "rsi"
        assert by_name["rsi14"].params["period"] == 14
        assert by_name["wr14"].op_name == "williams_r"
        assert by_name["wr14"].params["period"] == 14

    def test_the_thresholds_and_their_operators(self, document: Any) -> None:
        by_name = _by_name(document)
        assert (
            by_name["rsi_oversold_raw"].op_name,
            by_name["rsi_oversold_raw"].params["const"],
        ) == ("le", 30.0)
        assert (
            by_name["wr_oversold_raw"].op_name,
            by_name["wr_oversold_raw"].params["const"],
        ) == ("le", -80.0)
        assert (
            by_name["rsi_recovered_raw"].op_name,
            by_name["rsi_recovered_raw"].params["const"],
        ) == ("ge", 50.0)

    def test_every_momentum_gate_is_made_definite_fail_closed(
        self, document: Any
    ) -> None:
        """A warming-up or locked window must publish ``false``, never act."""
        by_name = _by_name(document)
        for gate in ("rsi_oversold", "wr_oversold", "rsi_recovered"):
            spec = by_name[gate]
            assert spec.op_name == "permissive", gate
            assert spec.params["when_missing"] is False, gate

    def test_the_session_bounds_match_the_other_stock_tenants(
        self, document: Any
    ) -> None:
        by_name = _by_name(document)
        assert by_name["mso"].params == {"open_hour": 9, "open_minute": 0}
        assert by_name["entry_window"].params == {"lo": 15, "hi": 345}
        assert str(by_name["eod"].params["at"]) == "15:15:00"

    def test_it_publishes_exactly_the_thirteen_fields(self, document: Any) -> None:
        assert tuple(entry.name for entry in document.publish) == PUBLISHED


class TestTheProducerStartupBinds:
    """The three refusals the live producer applies to a tenant declaration."""

    def test_publish_matches_the_critical_input_policy(self, document: Any) -> None:
        pf.assert_publish_matches_critical_inputs(
            document, policy_path=TREE / "critical_input_policy.yaml"
        )

    def test_every_dsl_resolved_value_is_published(self, document: Any) -> None:
        pf.assert_dsl_refs_are_published(document, strategies_dir=TREE / "strategies")

    def test_it_binds_to_a_09_00_session_and_the_seed_window(
        self, document: Any
    ) -> None:
        """``vol_ref`` stays declared because the seed length is sized from it."""
        pf.assert_declaration_binds_to_the_run(
            document,
            strategy=load_strategy_inputs(LEGACY_STRATEGY_YAML),
            anchor=OpenAnchor(9, 0, "test"),
        )

    def test_a_shifted_open_anchor_is_refused(self, document: Any) -> None:
        with pytest.raises(pf.ProduceFieldsError, match="open anchor"):
            pf.assert_declaration_binds_to_the_run(
                document,
                strategy=load_strategy_inputs(LEGACY_STRATEGY_YAML),
                anchor=OpenAnchor(8, 45, "test"),
            )


def _frame(closes: list[float], *, start: datetime) -> Any:
    """A minute frame whose high/low straddle the close by one tick."""
    rows = []
    for index, close in enumerate(closes):
        rows.append(
            {
                "timestamp": start + timedelta(minutes=index),
                "open": close,
                "high": close + 10.0,
                "low": close - 10.0,
                "close": close,
                "volume": 100.0,
            }
        )
    return pd.DataFrame(rows)


def _flat_frame(price: float, count: int, *, start: datetime) -> Any:
    """A locked window — every bar identical, as a 상한가/하한가 day reads."""
    rows = [
        {
            "timestamp": start + timedelta(minutes=index),
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": 100.0,
        }
        for index in range(count)
    ]
    return pd.DataFrame(rows)


class TestTheDeclarationOverABarStream:
    """The producer function the live line calls, on synthetic bars."""

    def test_a_falling_stream_opens_both_oversold_gates(self, document: Any) -> None:
        # Day 1 is dropped wholesale (warmup + first session), so the emitted bars are
        # day 2's. A monotonically falling day 2 drives RSI down and %R to -100.
        start = datetime(2026, 11, 2, 9, 0)
        day_one = _frame(
            [70_000.0 + (index % 3) * 10 for index in range(70)], start=start
        )
        day_two = _frame(
            [70_000.0 - index * 10 for index in range(60)],
            start=datetime(2026, 11, 3, 9, 0),
        )
        produced = pf.produce_bars_declarative(
            pd.concat([day_one, day_two], ignore_index=True),
            symbol="005380",
            document=document,
        )
        assert produced.records, "no bar survived the omission gate"
        assert tuple(produced.records[0].fields) == PUBLISHED
        last = produced.records[-1].fields
        assert last["rsi_oversold"] is True
        assert last["wr_oversold"] is True
        assert last["rsi_recovered"] is False

    def test_a_rising_stream_opens_the_exit_gate_and_no_entry(
        self, document: Any
    ) -> None:
        start = datetime(2026, 11, 2, 9, 0)
        day_one = _frame(
            [70_000.0 + (index % 3) * 10 for index in range(70)], start=start
        )
        day_two = _frame(
            [70_000.0 + index * 10 for index in range(60)],
            start=datetime(2026, 11, 3, 9, 0),
        )
        produced = pf.produce_bars_declarative(
            pd.concat([day_one, day_two], ignore_index=True),
            symbol="005380",
            document=document,
        )
        last = produced.records[-1].fields
        assert last["rsi_recovered"] is True
        assert last["rsi_oversold"] is False
        assert last["wr_oversold"] is False

    def test_a_locked_window_publishes_false_rather_than_an_entry(
        self, document: Any
    ) -> None:
        """TA-Lib's %R would read 0.0 ("close at the window high") on a flat window."""
        start = datetime(2026, 11, 2, 9, 0)
        day_one = _frame([70_000.0 - index * 10 for index in range(70)], start=start)
        day_two = _flat_frame(69_300.0, 60, start=datetime(2026, 11, 3, 9, 0))
        produced = pf.produce_bars_declarative(
            pd.concat([day_one, day_two], ignore_index=True),
            symbol="005380",
            document=document,
        )
        assert produced.records
        last = produced.records[-1].fields
        assert last["wr_oversold"] is False
        assert isinstance(last["wr_oversold"], bool)

    def test_every_published_value_is_a_journal_scalar(self, document: Any) -> None:
        start = datetime(2026, 11, 2, 9, 0)
        frame = pd.concat(
            [
                _frame(
                    [70_000.0 + (index % 5) * 10 for index in range(70)], start=start
                ),
                _frame(
                    [70_000.0 - index * 5 for index in range(60)],
                    start=datetime(2026, 11, 3, 9, 0),
                ),
            ],
            ignore_index=True,
        )
        produced = pf.produce_bars_declarative(
            frame, symbol="005380", document=document
        )
        for record in produced.records:
            for key, value in record.fields.items():
                assert isinstance(value, (bool, int, str)), (key, value)


def test_the_tree_declares_no_strategy_binding() -> None:
    """Thresholds live in fields.yaml, so an unused knob would refuse the boot."""
    bindings = yaml.safe_load(
        (TREE / "strategy_bindings.yaml").read_text(encoding="utf-8")
    )
    assert bindings == {"strategies": {}}
