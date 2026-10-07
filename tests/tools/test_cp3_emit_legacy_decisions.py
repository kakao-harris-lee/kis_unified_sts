"""Tests for the CP-3 B2 legacy decision emitter (``tools/tos_cp3``).

Hermetic: the **same synthetic minute series B1a's suite uses**, imported from
``tests/tools/test_cp3_produce_fields.py`` rather than copied, no Redis / KIS /
network. Sharing the series is not a convenience — the join invariant below is
only meaningful if both producers see literally the same bars.

What is pinned here:

* **Outcome parity** — every line's ``outcome`` equals what a fresh
  ``SetupDVWAPReversion`` decides on the same series, with the reason→outcome
  mapping restated here by an INDEPENDENT derivation (split the legacy reason
  at its delimiters) rather than by reusing the emitter's prefix table.
* **The closed sets are the legacy source's** — the reject-prefix table and the
  trace-key table are checked against the AST of
  ``shared/decision/setups/vwap_reversion.py``, so a new reject branch or a new
  ``ev[...]`` key fails here instead of becoming an unknown string at run time.
* **Join invariant** — B1a's and B2's ``raw_event_id`` sequences are identical
  on the same series, ``as_of_ms`` agrees, and the one quantity both publish
  (``z_x1000``) agrees value for value where B2 carries it.
* **The position-model flag is the walk-forward harness's** — compared against
  a direct call of ``collect_entries`` on the same frame under the same open
  anchor.
* **No floats**, with a red proof.
* **Determinism** — two full runs write byte-identical JSONL and lineage.
* **Refusals** — an unknown reject reason, an unknown trace key, a
  fired/rejected contradiction, and a bar that fires while being unpublishable
  each abort rather than ship something quietly wrong.

File name: deliberately NOT ``test_tos_cp3_*``, for the reason B1a's suite
states — ``tos-firewall.yml`` runs ``pytest tests/tools/test_tos_*.py`` in a
job with a minimal dependency set (no pyarrow), and ``test.yml``'s path filter
negates the same prefix. This suite needs the full runtime stack.
"""

from __future__ import annotations

import json
import logging
import sys
import warnings
from collections import Counter
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from shared.backtest.market_context_replay import MarketContextReplay
from shared.decision.setups.vwap_reversion import SetupDVWAPReversion
from tools.tos_cp3 import emit_legacy_decisions, produce_fields

#: B1a's suite lives in this directory and is imported by its top-level module
#: name. pytest's default ``prepend`` import mode puts this directory on
#: ``sys.path`` when it collects either file; the insert makes the import work
#: regardless of which file is collected first (or alone).
_TESTS_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TESTS_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_TOOLS_DIR))

import test_cp3_produce_fields as b1a  # noqa: E402

SYMBOL = b1a.SYMBOL
SESSIONS = b1a.SESSIONS
STRATEGY_YAML = b1a.STRATEGY_YAML

#: The anchor ``collect_entries`` takes by default, because it builds
#: ``MarketContextReplay`` without ``market_open_hour``/``market_open_minute``
#: (walkforward script lines 160-167; the dataclass default is 08:45). The
#: position-model test runs B2 on this anchor so the two sides are comparable;
#: a real run uses the era rule instead (declared difference L2).
WALKFORWARD_DEFAULT_OPEN = "08:45"


# ---------------------------------------------------------------------------
# Fixtures — the shared series
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def bars() -> pd.DataFrame:
    """B1a's synthetic series, verbatim."""
    return b1a._synthetic_bars().reset_index(drop=True)


@pytest.fixture(scope="module")
def strategy() -> produce_fields.StrategyInputs:
    return produce_fields.load_strategy_inputs(STRATEGY_YAML)


@pytest.fixture(scope="module")
def anchor() -> produce_fields.OpenAnchor:
    """The anchor a real run resolves for this window — B1a's era rule."""
    return produce_fields.resolve_open_anchor(
        cli_value="auto", first_session=SESSIONS[0], last_session=SESSIONS[-1]
    )


def _quiet():
    """Silence MarketContextReplay's large-1-min-return research warning."""
    return warnings.catch_warnings()


def _emit(
    df: pd.DataFrame,
    strategy: produce_fields.StrategyInputs,
    anchor: produce_fields.OpenAnchor,
) -> emit_legacy_decisions.EmittedDecisions:
    with _quiet():
        warnings.simplefilter("ignore")
        return emit_legacy_decisions.emit_decisions(
            df.reset_index(drop=True),
            symbol=SYMBOL,
            strategy=strategy,
            contract_spec=b1a._contract_spec(),
            anchor=anchor,
        )


@pytest.fixture(scope="module")
def emitted(
    bars: pd.DataFrame,
    strategy: produce_fields.StrategyInputs,
    anchor: produce_fields.OpenAnchor,
) -> emit_legacy_decisions.EmittedDecisions:
    return _emit(bars, strategy, anchor)


# ---------------------------------------------------------------------------
# The closed sets belong to the legacy source, not to this module
# ---------------------------------------------------------------------------


def test_reject_outcome_rules_cover_every_legacy_reject_branch() -> None:
    """Every ``_reject`` branch in the legacy setup classifies, and none is dead.

    The failing input this guards against is concrete: add a branch
    ``return self._reject(f"mystery_gate({x:.2f})")`` to
    ``SetupDVWAPReversion.check()`` and this test goes red, where without it
    the emitter would only fail on a dataset that happens to reach the new
    branch.
    """
    prefixes = emit_legacy_decisions.legacy_reject_prefixes()
    assert prefixes, "the AST walk found no _reject() calls — it is not working"

    matched_rules: set[str] = set()
    for prefix in prefixes:
        hits = [
            (match, literal, outcome)
            for match, literal, outcome in emit_legacy_decisions.REJECT_OUTCOME_RULES
            if (prefix == literal if match == "exact" else prefix.startswith(literal))
        ]
        assert len(hits) == 1, (prefix, hits)
        matched_rules.add(hits[0][1])
        # And a reason actually formatted from that prefix resolves the same way.
        reason = prefix if prefix.endswith(")") or "(" not in prefix else prefix + "X)"
        assert emit_legacy_decisions.outcome_for_reject_reason(reason) == hits[0][2]

    declared = {literal for _, literal, _ in emit_legacy_decisions.REJECT_OUTCOME_RULES}
    assert declared == matched_rules, (
        "REJECT_OUTCOME_RULES has entries no legacy branch can produce: "
        f"{sorted(declared - matched_rules)}"
    )
    assert len(emit_legacy_decisions.OUTCOMES) == len(declared) + 1  # + FIRED


def test_eval_projection_covers_every_legacy_trace_key() -> None:
    """``EVAL_PROJECTION`` is exactly the ``ev[...]`` key set of ``check()``.

    Guards the same shape of silent drift: add ``ev["new_score"] = 1.5`` to
    ``check()`` and this goes red. Without it, the emitter would refuse only on
    a dataset that reaches the branch recording it.
    """
    from_source = set(emit_legacy_decisions.legacy_trace_keys())
    assert from_source, "the AST walk found no ev[...] assignments"
    declared = {key for key, _, _ in emit_legacy_decisions.EVAL_PROJECTION}
    assert declared == from_source
    published = [name for _, name, _ in emit_legacy_decisions.EVAL_PROJECTION]
    assert len(set(published)) == len(published), "duplicate published trace key"


# ---------------------------------------------------------------------------
# (a) Outcome parity with a fresh setup on the same series
# ---------------------------------------------------------------------------


def _expected_outcome(fired: bool, reason: str | None) -> str:
    """Restate reason → outcome INDEPENDENTLY of the emitter's prefix table.

    Derived by splitting the legacy reason at its own delimiters instead of by
    matching a declared prefix list, so this test cannot pass merely because
    the emitter and the test share a table.
    """
    if fired:
        assert reason is None
        return "FIRED"
    assert reason is not None
    head, _, tail = reason.partition("(")
    if head == "awaiting_reversal_confirm":
        inner = tail[:-1] if tail.endswith(")") else tail
        sub = inner.split("=", 1)[0]
        return f"AWAITING_REVERSAL_CONFIRM_{sub.upper()}"
    return head.upper()


def test_outcome_per_bar_equals_a_fresh_setup_on_the_same_series(
    bars: pd.DataFrame,
    strategy: produce_fields.StrategyInputs,
    anchor: produce_fields.OpenAnchor,
    emitted: emit_legacy_decisions.EmittedDecisions,
) -> None:
    """Replay the series again with a fresh setup and compare, bar by bar."""
    setup = SetupDVWAPReversion(config=strategy.entry_config)
    with _quiet():
        warnings.simplefilter("ignore")
        replay = MarketContextReplay(
            df=bars,
            symbol=SYMBOL,
            macro_snapshot=None,
            scheduled_events=[],
            contract_spec=b1a._contract_spec(),
            market_open_hour=anchor.hour,
            market_open_minute=anchor.minute,
            min_volume=0,
        )
        expected: dict[str, str] = {}
        for ctx in replay.iter_contexts():
            signal = setup.check(ctx)
            raw_event_id = produce_fields.derive_raw_event_id(SYMBOL, ctx.now)
            expected[raw_event_id] = _expected_outcome(
                signal is not None, setup.last_reject_reason
            )

    assert expected, "the independent replay produced nothing"
    for record in emitted.records:
        assert record.outcome == expected[record.raw_event_id], record.raw_event_id

    # Non-vacuous: the series must actually reach several distinct outcomes,
    # including a fire, or "every outcome matches" would mean nothing.
    seen = Counter(record.outcome for record in emitted.records)
    assert emit_legacy_decisions.OUTCOME_FIRED in seen, seen
    assert len(seen) >= 6, seen
    assert set(seen) <= set(emit_legacy_decisions.OUTCOMES)
    for required in (
        "BEFORE_WINDOW",
        "AFTER_CUTOFF",
        "NOT_EXTREME",
        "AWAITING_REVERSAL_CONFIRM_PRICE_TURN",
    ):
        assert seen[required] > 0, (required, seen)


def test_fired_bars_carry_the_bracket_and_others_carry_null(
    emitted: emit_legacy_decisions.EmittedDecisions,
) -> None:
    """``entry``/``stop``/``target``/``confidence`` exist exactly on FIRED bars."""
    fired = [
        record
        for record in emitted.records
        if record.outcome == emit_legacy_decisions.OUTCOME_FIRED
    ]
    assert fired
    for record in fired:
        assert record.direction in {"LONG", "SHORT"}
        assert isinstance(record.confidence_x1000, int)
        assert isinstance(record.entry_x100, int)
        assert isinstance(record.stop_x100, int)
        assert isinstance(record.target_x100, int)
        # The bracket is symmetric about the entry in the fade direction.
        if record.direction == "LONG":
            assert record.stop_x100 < record.entry_x100 < record.target_x100
        else:
            assert record.target_x100 < record.entry_x100 < record.stop_x100
        assert record.eval_trace["fired"] is True

    for record in emitted.records:
        if record.outcome == emit_legacy_decisions.OUTCOME_FIRED:
            continue
        assert record.confidence_x1000 is None
        assert record.entry_x100 is None
        assert record.stop_x100 is None
        assert record.target_x100 is None
        assert "fired" not in record.eval_trace


def test_an_unevaluated_trace_key_is_absent_not_false(
    emitted: emit_legacy_decisions.EmittedDecisions,
) -> None:
    """Declared difference L6, pinned on a bar that really stops at step 1."""
    before = next(
        record for record in emitted.records if record.outcome == "BEFORE_WINDOW"
    )
    assert set(before.eval_trace) == {"minutes_since_open_x1000", "entry_window"}
    assert before.eval_trace["entry_window"] is False
    assert "hi_vol" not in before.eval_trace

    # ... and on a bar that stops at the extension trigger, where the gates it
    # DID evaluate are present and the ones after it are not.
    not_extreme = next(
        record for record in emitted.records if record.outcome == "NOT_EXTREME"
    )
    assert not_extreme.eval_trace["hi_vol"] is True
    assert not_extreme.eval_trace["extreme"] is False
    assert "stall_ok" not in not_extreme.eval_trace
    assert "reversal_ok" not in not_extreme.eval_trace
    assert not_extreme.direction is None


# ---------------------------------------------------------------------------
# (b) Join invariant against B1a
# ---------------------------------------------------------------------------


def test_join_invariant_b1a_and_b2_key_sequences_are_identical(
    bars: pd.DataFrame,
    strategy: produce_fields.StrategyInputs,
    anchor: produce_fields.OpenAnchor,
    emitted: emit_legacy_decisions.EmittedDecisions,
) -> None:
    """Same bars, same keys, same ``z_x1000`` — the three things B3 relies on."""
    with _quiet():
        warnings.simplefilter("ignore")
        b1a_records = produce_fields.produce_records(
            bars.reset_index(drop=True),
            symbol=SYMBOL,
            strategy=strategy,
            contract_spec=b1a._contract_spec(),
            anchor=anchor,
        )

    assert [record.raw_event_id for record in b1a_records] == [
        record.raw_event_id for record in emitted.records
    ]
    assert [record.as_of_ms for record in b1a_records] == [
        record.as_of_ms for record in emitted.records
    ]

    # The one quantity both artifacts publish must agree exactly where B2
    # carries it — same scale, same quantization, same bar. If it did not, the
    # join would be key-aligned but semantically meaningless.
    compared = 0
    for b1a_record, b2_record in zip(b1a_records, emitted.records):
        if "z_x1000" not in b2_record.eval_trace:
            continue
        assert (
            b2_record.eval_trace["z_x1000"] == b1a_record.fields["z_x1000"]
        ), b2_record.raw_event_id
        compared += 1
    assert compared > 0, "no bar reached step 4, so the z agreement is vacuous"


# ---------------------------------------------------------------------------
# (c) No floats, with a red proof
# ---------------------------------------------------------------------------


def test_no_floats_anywhere_in_the_payload(
    emitted: emit_legacy_decisions.EmittedDecisions,
) -> None:
    def walk(value: object, path: str) -> int:
        if isinstance(value, dict):
            return sum(walk(item, f"{path}.{key}") for key, item in value.items())
        if isinstance(value, list):
            return sum(walk(item, f"{path}[{i}]") for i, item in enumerate(value))
        assert not isinstance(value, float), (path, value)
        assert value is None or isinstance(value, (bool, int, str)), (path, value)
        return 1

    total = 0
    for record in emitted.records:
        # Through JSON, so a float that only survives serialization is caught.
        total += walk(json.loads(record.to_json_line()), "line")
    assert total > 0


def test_a_float_in_the_payload_is_refused() -> None:
    """Red proof for :func:`_assert_no_floats` — the nested case included."""
    emit_legacy_decisions._assert_no_floats(
        {
            "decision": {
                "eval": {"z_x1000": -1799, "hi_vol": True, "vol_ref_x100": None}
            }
        },
        "id",
    )
    with pytest.raises(emit_legacy_decisions.EmitLegacyDecisionsError, match="z_x1000"):
        emit_legacy_decisions._assert_no_floats(
            {"decision": {"eval": {"z_x1000": -1.799}}}, "id"
        )


def test_a_float_valued_trace_entry_is_scaled_not_passed_through() -> None:
    """Every projection returns an ``int`` for a float input, or refuses."""
    projected = emit_legacy_decisions.project_eval(
        {
            "close": 400.005,
            "z": -1.7995,
            "stall_distance": -0.125,
            "minutes_since_open": -15.0,
            "vol_ratio": 1.2349,
            "confidence": 0.6667,
            "direction": "short",
            "hi_vol": True,
            "vol_ref": None,
        }
    )
    assert projected == {
        "minutes_since_open_x1000": -15000,
        "close_x100": 40001,  # half-up on a magnitude
        "vol_ref_x100": None,
        "vol_ratio_x1000": 1234,  # toward zero
        "hi_vol": True,
        "z_x1000": -1799,  # toward zero: symmetric and conservative
        "direction": "SHORT",
        "stall_distance_x100": -12,  # toward zero on a signed price distance
        "confidence_x1000": 666,
    }
    # Order follows EVAL_PROJECTION, not the input dict's insertion order.
    assert list(projected) == [
        name
        for _, name, _ in emit_legacy_decisions.EVAL_PROJECTION
        if name in projected
    ]


# ---------------------------------------------------------------------------
# (d) Determinism, through the real CLI path
# ---------------------------------------------------------------------------


def test_two_runs_write_byte_identical_artifacts(
    bars: pd.DataFrame, tmp_path: Path
) -> None:
    data_root = b1a._write_parquet_tree(bars, tmp_path / "market")
    outputs = []
    for name in ("run-a", "run-b"):
        with _quiet():
            warnings.simplefilter("ignore")
            outputs.append(
                emit_legacy_decisions.run(
                    data_root=data_root,
                    symbol=SYMBOL,
                    start=SESSIONS[0],
                    end=SESSIONS[-1],
                    strategy_yaml=STRATEGY_YAML,
                    out_dir=tmp_path / name,
                )
            )
    first, second = outputs
    assert first.jsonl_bytes == second.jsonl_bytes
    assert first.lineage_bytes == second.lineage_bytes
    assert first.jsonl_path.read_bytes() == first.jsonl_bytes
    assert first.lineage_path.read_bytes() == first.lineage_bytes

    lineage = first.lineage
    assert lineage["output"]["jsonl_lines"] == len(first.records)
    assert lineage["tool"]["source_id"] == emit_legacy_decisions.SOURCE_ID
    assert lineage["tool"]["source_id"].startswith("tos-cp3-b2/")
    assert lineage["join"]["key"] == "raw_event_id"
    # The join key encodes no anchor and no density gate, so the pair's window
    # identity has to travel in the sidecar or B3 cannot tell a comparable pair
    # from an incomparable one.
    identity = lineage["join"]["window_identity"]
    assert identity == {
        "symbol": SYMBOL,
        "market_open_kst": "09:00",
        "market_open_source": "era-rule",
        "min_bars_per_day": produce_fields.DEFAULT_MIN_BARS_PER_DAY,
        "window_start": SESSIONS[0].isoformat(),
        "window_end": SESSIONS[-1].isoformat(),
    }
    assert "MUST REFUSE" in lineage["join"]["b3_contract"]
    # Reconciliation is asserted by build_lineage; check the chain it reports.
    dataset = lineage["dataset"]
    assert (
        dataset["bars_after_density_gate"]
        - dataset["reconciliation"]["bars_dropped_before_replay"]
        == dataset["bars_replayed"]
    )
    assert (
        dataset["bars_replayed"] - dataset["omitted_bars"]["count"]
        == dataset["bars_emitted"]
    )
    assert sum(lineage["outcomes"]["counts"].values()) == dataset["bars_emitted"]
    # Nothing time-dependent leaked into the sidecar.
    rendered = first.lineage_bytes.decode("utf-8")
    for forbidden in ("run_at", "generated_at", "duration_seconds", "elapsed"):
        assert forbidden not in rendered
    assert {difference["id"] for difference in lineage["declared_differences"]} == {
        f"L{index}" for index in range(1, 13)
    }


# ---------------------------------------------------------------------------
# (e) The position-model flag is the walk-forward harness's
# ---------------------------------------------------------------------------


def test_position_model_flag_matches_the_walkforward_script(
    bars: pd.DataFrame, strategy: produce_fields.StrategyInputs
) -> None:
    """Compare against ``collect_entries`` itself, under its own open anchor.

    ``collect_entries`` builds its replay without an open override, so the
    comparison has to run B2 on 08:45 (declared difference L2 records that a
    real run uses the era rule instead). Its hardcoded ``ContractSpec`` is
    irrelevant: ``MarketContextReplay`` does not read one
    (``market_context_replay.py``: "currently unused").
    """
    harness = emit_legacy_decisions.load_walkforward_module()
    frame = bars.reset_index(drop=True)
    anchor = produce_fields.resolve_open_anchor(
        cli_value=WALKFORWARD_DEFAULT_OPEN,
        first_session=SESSIONS[0],
        last_session=SESSIONS[-1],
    )
    assert (anchor.hour, anchor.minute) == (8, 45)

    with _quiet():
        warnings.simplefilter("ignore")
        trades = harness.collect_entries(frame, strategy.entry_config)
    emitted = _emit(frame, strategy, anchor)

    expected = [pd.Timestamp(trade.ts) for trade in trades]
    actual = [
        pd.Timestamp(record.bar_kst).tz_localize(None)
        for record in emitted.records
        if record.would_be_admitted_by_legacy_position_model
    ]
    assert actual == expected
    assert expected, "the harness admitted nothing — the comparison is vacuous"

    # The flag is a STRICTER statement than "the rule fired": the series must
    # contain at least one fire discarded inside an open position, or the test
    # would pass with the flag wired straight to `outcome == FIRED`.
    fired = sum(
        1
        for record in emitted.records
        if record.outcome == emit_legacy_decisions.OUTCOME_FIRED
    )
    assert fired > len(expected), (fired, len(expected))
    # Only a FIRED bar can be admitted (also asserted inside the emitter).
    for record in emitted.records:
        if record.would_be_admitted_by_legacy_position_model:
            assert record.outcome == emit_legacy_decisions.OUTCOME_FIRED


def test_the_harness_names_the_flag_depends_on_still_exist() -> None:
    """A refactor of the walk-forward script must fail here, not silently."""
    harness = emit_legacy_decisions.load_walkforward_module()
    for name in emit_legacy_decisions.WALKFORWARD_REQUIRED_NAMES:
        assert hasattr(harness, name), name
    assert (harness.EOD_HOUR, harness.EOD_MINUTE) == (15, 15)


# ---------------------------------------------------------------------------
# (f) Refusals
# ---------------------------------------------------------------------------


def test_an_unknown_reject_reason_is_refused() -> None:
    """Red proof for the closed outcome set."""
    for known, expected in (
        ("no_atr", "NO_ATR"),
        ("before_window(3m<5)", "BEFORE_WINDOW"),
        (
            "awaiting_reversal_confirm(no_prev_close)",
            ("AWAITING_REVERSAL_CONFIRM_NO_PREV_CLOSE"),
        ),
        (
            "awaiting_reversal_confirm(z_improve=0.01<0.05)",
            ("AWAITING_REVERSAL_CONFIRM_Z_IMPROVE"),
        ),
    ):
        assert emit_legacy_decisions.outcome_for_reject_reason(known) == expected

    for unknown in (
        "mystery_gate(1.00<2.00)",
        "awaiting_reversal_confirm(volume_turn=long)",
        "",
        "NO_ATR",
    ):
        with pytest.raises(
            emit_legacy_decisions.EmitLegacyDecisionsError, match="unknown legacy"
        ):
            emit_legacy_decisions.outcome_for_reject_reason(unknown)


def test_a_fired_and_rejected_bar_is_refused() -> None:
    with pytest.raises(
        emit_legacy_decisions.EmitLegacyDecisionsError, match="exactly one"
    ):
        emit_legacy_decisions.classify_outcome(fired=True, reject_reason="no_atr")
    with pytest.raises(
        emit_legacy_decisions.EmitLegacyDecisionsError, match="exactly one"
    ):
        emit_legacy_decisions.classify_outcome(fired=False, reject_reason=None)


def test_an_unknown_trace_key_is_refused() -> None:
    with pytest.raises(
        emit_legacy_decisions.EmitLegacyDecisionsError, match="some_new_gate_score"
    ):
        emit_legacy_decisions.project_eval({"z": -2.0, "some_new_gate_score": 1.5})


def test_a_non_bool_in_a_bool_slot_is_refused() -> None:
    with pytest.raises(emit_legacy_decisions.EmitLegacyDecisionsError, match="not a"):
        emit_legacy_decisions.project_eval({"hi_vol": 1})
    with pytest.raises(
        emit_legacy_decisions.EmitLegacyDecisionsError, match="fade direction"
    ):
        emit_legacy_decisions.project_eval({"direction": "sideways"})


def test_a_bar_that_fires_while_unpublishable_aborts(
    bars: pd.DataFrame,
    strategy: produce_fields.StrategyInputs,
    anchor: produce_fields.OpenAnchor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The one case the emitter refuses instead of declaring.

    A bar with ``vwap <= 0`` and a usable ``atr``/``close`` can FIRE on the
    fabricated extreme (``SetupDVWAPReversion.REQUIRES_VWAP``) while B1a omits
    its line. The guard is driven here by making the omission predicate claim
    every bar is unpublishable, which is the same input the real condition
    presents: "check() fired, and B1a will publish no line for this bar".
    """
    monkeypatch.setattr(
        emit_legacy_decisions,
        "_inputs_unusable",
        lambda close, vwap, atr: "vwap <= 0 (z would be a fabricated extreme)",
    )
    with pytest.raises(
        emit_legacy_decisions.EmitLegacyDecisionsError, match="FIRED on a bar"
    ):
        _emit(bars, strategy, anchor)


def test_trend_filter_on_is_refused_by_the_inherited_loader(
    tmp_path: Path, bars: pd.DataFrame
) -> None:
    """Declared difference L7 — the refusal is B1a's, and B2 inherits it."""
    raw = STRATEGY_YAML.read_text(encoding="utf-8")
    assert "trend_filter_enabled: false" in raw
    patched = tmp_path / "setup_d_trend_on.yaml"
    patched.write_text(
        raw.replace("trend_filter_enabled: false", "trend_filter_enabled: true"),
        encoding="utf-8",
    )
    data_root = b1a._write_parquet_tree(bars, tmp_path / "market")
    with pytest.raises(produce_fields.ProduceFieldsError, match="trend_filter_enabled"):
        emit_legacy_decisions.run(
            data_root=data_root,
            symbol=SYMBOL,
            start=SESSIONS[0],
            end=SESSIONS[-1],
            strategy_yaml=patched,
            out_dir=tmp_path / "out",
        )


# ---------------------------------------------------------------------------
# Window parity with B1a: the same loader, the same gate, the same anchor rule
# ---------------------------------------------------------------------------


def test_cli_window_options_mirror_b1a(tmp_path: Path, bars: pd.DataFrame) -> None:
    """The two CLIs expose the same window surface with the same defaults."""
    b2_options = {
        action.dest: action
        for action in emit_legacy_decisions.build_parser()._actions
        if action.dest != "help"
    }
    b1a_options = {
        action.dest: action
        for action in produce_fields.build_parser()._actions
        if action.dest != "help"
    }
    shared = (
        "data_root",
        "symbol",
        "start",
        "end",
        "strategy_yaml",
        "out",
        "market_open",
        "min_bars_per_day",
    )
    assert set(b2_options) == set(shared)
    assert set(shared) <= set(b1a_options)
    for name in shared:
        assert b2_options[name].default == b1a_options[name].default, name
    assert (
        b2_options["min_bars_per_day"].default
        == produce_fields.DEFAULT_MIN_BARS_PER_DAY
        == 330
    )
    assert b2_options["market_open"].default == "auto"


def test_the_density_gate_drops_the_same_sessions_b1a_drops(
    bars: pd.DataFrame, tmp_path: Path
) -> None:
    """A short session is gated out of BOTH artifacts, so the join survives it."""
    short_day = b1a.SHORT_SESSION
    base = datetime.combine(short_day, datetime.min.time()).replace(hour=8, minute=45)
    last_close = float(bars["close"].iloc[-1])
    extra = pd.DataFrame(
        [
            {
                "code": SYMBOL,
                "timestamp": base + timedelta(minutes=minute),
                "open": last_close,
                "high": last_close + 0.1,
                "low": last_close - 0.1,
                "close": last_close,
                "volume": 60,
            }
            for minute in range(b1a.SHORT_SESSION_BARS)
        ]
    )
    frame = pd.concat([bars, extra], ignore_index=True)
    data_root = b1a._write_parquet_tree(frame, tmp_path / "market")

    with _quiet():
        warnings.simplefilter("ignore")
        b2_result = emit_legacy_decisions.run(
            data_root=data_root,
            symbol=SYMBOL,
            start=SESSIONS[0],
            end=short_day,
            strategy_yaml=STRATEGY_YAML,
            out_dir=tmp_path / "b2",
        )
        b1a_result = produce_fields.run(
            data_root=data_root,
            symbol=SYMBOL,
            start=SESSIONS[0],
            end=short_day,
            strategy_yaml=STRATEGY_YAML,
            out_dir=tmp_path / "b1a",
        )

    assert b2_result.lineage["dataset"]["bars_loaded"] == (
        b1a_result.lineage["dataset"]["bars_loaded"]
    )
    assert b2_result.lineage["dataset"]["bars_after_density_gate"] == (
        b1a_result.lineage["dataset"]["bars_after_density_gate"]
    )
    assert b2_result.lineage["dataset"]["bars_loaded"] > (
        b2_result.lineage["dataset"]["bars_after_density_gate"]
    ), "the short session was not dropped — the gate is not being exercised"
    assert [record.raw_event_id for record in b2_result.records] == [
        record.raw_event_id for record in b1a_result.records
    ]
    assert all(record.bar_kst.date() != short_day for record in b2_result.records)


def test_a_window_straddling_the_open_anchor_cutover_is_refused() -> None:
    """Inherited from B1a: one anchor cannot be right for both eras."""
    cutover = produce_fields.OPEN_ANCHOR_CUTOVER
    with pytest.raises(produce_fields.ProduceFieldsError, match="straddles"):
        produce_fields.resolve_open_anchor(
            cli_value="auto",
            first_session=cutover - timedelta(days=5),
            last_session=cutover + timedelta(days=5),
        )
    assert produce_fields.resolve_open_anchor(
        cli_value="auto",
        first_session=date(2025, 12, 1),
        last_session=date(2026, 4, 30),
    ) == produce_fields.OpenAnchor(9, 0, "era-rule")


def test_the_emitter_imports_nothing_from_tos() -> None:
    """The reverse firewall, restated where a reader of this suite sees it.

    ``tools/tos_firewall_check.py`` is the gate; this is a fast local echo of
    it over the one module this PR adds, so a ``from tos...`` line added here
    fails in the unit suite too.
    """
    source = (
        produce_fields.REPO_ROOT / "tools" / "tos_cp3" / "emit_legacy_decisions.py"
    ).read_text(encoding="utf-8")
    for line in source.splitlines():
        stripped = line.strip()
        assert not stripped.startswith(("import tos", "from tos ")), line
        assert not stripped.startswith(("import tos_runtime", "from tos_runtime")), line
        assert not stripped.startswith("from tos."), line


def test_strategy_inputs_are_shared_with_b1a(
    strategy: produce_fields.StrategyInputs,
) -> None:
    """B2 reads the strategy through B1a's loader, not a second parser."""
    assert strategy.entry_config.trend_filter_enabled is False
    # The same object a second load produces — one parser, one set of values.
    again = produce_fields.load_strategy_inputs(STRATEGY_YAML)
    assert replace(again, path=strategy.path) == replace(strategy, path=strategy.path)
    assert again.sha256 == strategy.sha256


# ---------------------------------------------------------------------------
# Review #876: the config-source difference behind "admitted != published"
# ---------------------------------------------------------------------------


def test_config_source_diff_names_the_fields_the_harness_never_read(
    strategy: produce_fields.StrategyInputs,
) -> None:
    """The published walk-forward ran a different operating point, machine-proved.

    ``collect_entries``' caller builds ``SetupDConfig(trend_* only)`` and never
    reads the strategy YAML, so every field the YAML moves off its default is a
    value the published numbers did not use. An earlier revision blamed the
    whole gap on the 15-minute open anchor; this diff is why that was wrong.
    """
    diff = emit_legacy_decisions.config_source_diff(strategy)
    assert diff, "the YAML and the harness defaults cannot be identical"
    # The four that are in force today. Named explicitly so a YAML edit that
    # silently returns one of them to its default is visible here.
    assert set(diff) == {
        "no_entry_after_minutes_since_open",
        "stall_buffer_atr_mult",
        "min_confidence",
        "reversal_confirm_enabled",
    }, diff
    assert diff["no_entry_after_minutes_since_open"] == {
        "yaml": 345,
        "harness_default": 360,
    }
    assert diff["stall_buffer_atr_mult"] == {"yaml": 1.5, "harness_default": 1.0}
    assert diff["min_confidence"] == {"yaml": 0.6, "harness_default": 0.0}
    assert diff["reversal_confirm_enabled"] == {
        "yaml": True,
        "harness_default": False,
    }

    # Every entry is computed, not written down: it must agree with a fresh
    # SetupDConfig() rather than with a literal in the tool.
    defaults = emit_legacy_decisions.SetupDConfig()
    for name, pair in diff.items():
        assert pair["harness_default"] == getattr(defaults, name), name
        assert pair["yaml"] == getattr(strategy.entry_config, name), name
        assert pair["yaml"] != pair["harness_default"], name


def test_four_outcomes_were_unreachable_in_the_published_run() -> None:
    """Config-gated branches are DEAD at the defaults, not merely rare."""
    unreachable = emit_legacy_decisions.outcomes_unreachable_under_harness_defaults()
    assert set(unreachable) == {
        "LOW_CONFIDENCE",
        "AWAITING_REVERSAL_CONFIRM_NO_PREV_CLOSE",
        "AWAITING_REVERSAL_CONFIRM_PRICE_TURN",
        "AWAITING_REVERSAL_CONFIRM_Z_IMPROVE",
        "AGAINST_TREND",
    }, unreachable
    assert set(unreachable) <= set(emit_legacy_decisions.OUTCOMES)
    # Derived from the dataclass, so it tracks a default that moves.
    defaults = emit_legacy_decisions.SetupDConfig()
    assert defaults.min_confidence == 0.0
    assert defaults.reversal_confirm_enabled is False


def test_the_lineage_carries_the_config_source_diff(
    bars: pd.DataFrame, tmp_path: Path
) -> None:
    data_root = b1a._write_parquet_tree(bars, tmp_path / "market")
    with _quiet():
        warnings.simplefilter("ignore")
        result = emit_legacy_decisions.run(
            data_root=data_root,
            symbol=SYMBOL,
            start=SESSIONS[0],
            end=SESSIONS[-1],
            strategy_yaml=STRATEGY_YAML,
            out_dir=tmp_path / "out",
        )
    block = result.lineage["config_source_diff"]
    assert set(block["differs"]) == {
        "no_entry_after_minutes_since_open",
        "stall_buffer_atr_mult",
        "min_confidence",
        "reversal_confirm_enabled",
    }
    assert "LOW_CONFIDENCE" in block["outcomes_unreachable_under_harness_defaults"]

    # L2 must no longer assert the published run's anchor, and must name the
    # fold concatenation and this diff as independent reasons.
    l2 = next(
        item for item in result.lineage["declared_differences"] if item["id"] == "L2"
    )
    assert l2["value"]["anchor_of_published_numbers"].startswith("unresolved")
    assert l2["value"]["published_oos_trades"] == 135
    assert "config_source_diff" in l2["note"]
    assert "concatenation of OOS fold blocks" in l2["note"]
    assert "UNRESOLVED" in l2["note"]
    # The anchor collect_entries takes today is read off the dataclass, not
    # written as a literal.
    default_hour = MarketContextReplay.__dataclass_fields__["market_open_hour"].default
    default_minute = MarketContextReplay.__dataclass_fields__[
        "market_open_minute"
    ].default
    assert l2["value"]["collect_entries_anchor_today"] == (
        f"{default_hour:02d}:{default_minute:02d}"
    )


# ---------------------------------------------------------------------------
# Review #876: duplicate bar timestamps
# ---------------------------------------------------------------------------


def test_a_duplicated_bar_timestamp_is_refused(
    bars: pd.DataFrame,
    strategy: produce_fields.StrategyInputs,
    anchor: produce_fields.OpenAnchor,
) -> None:
    """Red proof: B1a refuses a duplicated stamp, so B2 must refuse it too.

    Without the shared refusal, ``ts_to_idx`` keeps only the LAST index for the
    repeated stamp — so ``last_exit_idx`` is compared against the wrong bar —
    and the duplicated ``raw_event_id`` would be emitted twice, which B3 joins
    one-to-many without noticing.
    """
    frame = bars.reset_index(drop=True)
    duplicated = pd.concat(
        [frame, frame.iloc[[len(frame) // 2]]], ignore_index=True
    ).sort_values("timestamp")

    with pytest.raises(produce_fields.ProduceFieldsError, match="duplicate bar"):
        _emit(duplicated, strategy, anchor)
    # ... and B1a refuses the same frame, which is what makes it the same rule.
    with pytest.raises(produce_fields.ProduceFieldsError, match="duplicate bar"):
        with _quiet():
            warnings.simplefilter("ignore")
            produce_fields.produce_records(
                duplicated.reset_index(drop=True),
                symbol=SYMBOL,
                strategy=strategy,
                contract_spec=b1a._contract_spec(),
                anchor=anchor,
            )


# ---------------------------------------------------------------------------
# Review #876: the omission leg of the join contract
# ---------------------------------------------------------------------------


def test_the_omission_leg_of_the_join_is_exercised(
    strategy: produce_fields.StrategyInputs,
    anchor: produce_fields.OpenAnchor,
) -> None:
    """Both producers must DROP the same bars, not merely keep the same ones.

    The earlier suite would stay green with ``_inputs_unusable`` replaced by
    ``lambda *_: None``, because its synthetic series has no unusable bar. B1a's
    flat-run fixture does: a 41-bar perfectly flat stretch drives
    ``atr_partial`` to exactly 0.
    """
    flat = b1a._bars_with_flat_run().reset_index(drop=True)

    with _quiet():
        warnings.simplefilter("ignore")
        b1a_produced = produce_fields.produce_bars(
            flat,
            symbol=SYMBOL,
            strategy=strategy,
            contract_spec=b1a._contract_spec(),
            anchor=anchor,
        )
    b2_emitted = _emit(flat, strategy, anchor)

    b1a_omitted = {raw_event_id for raw_event_id, _ in b1a_produced.omitted}
    b2_omitted = {raw_event_id for raw_event_id, _, _ in b2_emitted.omitted}
    assert b1a_omitted, "the flat run must make some bars unpublishable"
    assert b1a_omitted == b2_omitted
    assert [record.raw_event_id for record in b1a_produced.records] == [
        record.raw_event_id for record in b2_emitted.records
    ]
    assert b2_emitted.bars_replayed == len(b2_emitted.records) + len(b2_emitted.omitted)
    # The omitted bars' decisions are not lost: each carries its legacy outcome.
    assert all(
        outcome in emit_legacy_decisions.OUTCOMES
        for _, _, outcome in b2_emitted.omitted
    )


# ---------------------------------------------------------------------------
# Review #876: the EOD agreement is asserted, not printed
# ---------------------------------------------------------------------------


def test_an_eod_disagreement_with_the_strategy_yaml_is_refused(
    strategy: produce_fields.StrategyInputs,
    bars: pd.DataFrame,
    anchor: produce_fields.OpenAnchor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Red proof: move the harness constant and the run must stop."""
    harness = emit_legacy_decisions.load_walkforward_module()
    cutoff = strategy.exit_config.eod_close_time
    # Agreement today — the precondition the refusal protects.
    emit_legacy_decisions.assert_eod_agreement(harness, strategy)
    assert (cutoff.hour, cutoff.minute) == (harness.EOD_HOUR, harness.EOD_MINUTE)

    monkeypatch.setattr(harness, "EOD_MINUTE", 10)
    with pytest.raises(
        emit_legacy_decisions.EmitLegacyDecisionsError,
        match="EOD cutoff disagreement",
    ):
        emit_legacy_decisions.assert_eod_agreement(harness, strategy)
    # And the refusal is wired into the emit path, not only callable.
    with pytest.raises(
        emit_legacy_decisions.EmitLegacyDecisionsError,
        match="EOD cutoff disagreement",
    ):
        _emit(bars, strategy, anchor)


# ---------------------------------------------------------------------------
# Review #876: loading the harness must not reconfigure the process
# ---------------------------------------------------------------------------


def test_loading_the_harness_leaves_logging_and_sys_path_alone() -> None:
    """The script calls logging.basicConfig and sys.path.insert at module level."""
    # Force a fresh load so the side effects would actually run.
    monkey = emit_legacy_decisions
    monkey._WALKFORWARD_MODULE = None
    sys.modules.pop(emit_legacy_decisions.WALKFORWARD_MODULE_NAME, None)

    handlers_before = list(logging.root.handlers)
    level_before = logging.root.level
    path_before = list(sys.path)

    module = emit_legacy_decisions.load_walkforward_module()

    assert logging.root.handlers == handlers_before
    assert logging.root.level == level_before
    assert sys.path == path_before
    # The module itself stays registered — its dataclasses resolve annotations
    # through sys.modules for the life of the process.
    assert sys.modules[emit_legacy_decisions.WALKFORWARD_MODULE_NAME] is module
    assert hasattr(module, "_simulate_exit")


# ---------------------------------------------------------------------------
# Review #876: per-field provenance
# ---------------------------------------------------------------------------


def test_every_published_number_has_a_provenance_entry(
    bars: pd.DataFrame, tmp_path: Path
) -> None:
    """ADR-002-018 §10 shape, same as B1a's fields block, for every key."""
    data_root = b1a._write_parquet_tree(bars, tmp_path / "market")
    with _quiet():
        warnings.simplefilter("ignore")
        result = emit_legacy_decisions.run(
            data_root=data_root,
            symbol=SYMBOL,
            start=SESSIONS[0],
            end=SESSIONS[-1],
            strategy_yaml=STRATEGY_YAML,
            out_dir=tmp_path / "out",
        )
    fields = result.lineage["fields"]

    expected = {name for _, name, _ in emit_legacy_decisions.EVAL_PROJECTION} | {
        name for name, _, _, _ in emit_legacy_decisions.BRACKET_PROJECTION
    }
    assert set(fields) == expected
    for name, entry in fields.items():
        assert set(entry) >= {
            "unit",
            "scale",
            "multiplier",
            "sign",
            "type",
            "quantization",
            "parents",
            "range_observed",
        }, name
        assert isinstance(entry["multiplier"], str), name
        assert entry["scale"] in {"none", "hundredths", "thousandths"}, name
        assert entry["sign"] in {"signed", "unsigned"}, name
        assert entry["type"] in {"int", "bool", "str"}, name
        assert entry["parents"], name
        assert entry["range_observed"]["present"] >= 0, name

    # A trace key absent on some bars must say so, so "never observed" is
    # distinguishable from "observed false".
    assert (
        fields["fired"]["range_observed"]["present"]
        < result.lineage["dataset"]["bars_emitted"]
    )
    assert fields["entry_window"]["range_observed"]["present"] == (
        result.lineage["dataset"]["bars_emitted"]
    )
    # The bracket integers are null off a FIRED bar.
    assert fields["entry_x100"]["range_observed"]["null"] > 0

    # The scale tokens replaced the bare numbers in L5.
    l5 = next(
        item for item in result.lineage["declared_differences"] if item["id"] == "L5"
    )
    assert l5["value"]["price_magnitudes"] == {
        "scale": "hundredths",
        "multiplier": "100",
        "quantization": "half_up",
    }
    assert "price_scale" not in l5["value"]

    # And the "the bool is authoritative" statement is present and specific.
    sentence = result.lineage["encoding"]["published_bools_are_authoritative"]
    assert "stall_distance_x100" in sentence and "stall_buffer_x100" in sentence
    assert "BOOL is the decision" in sentence


def test_the_units_table_cannot_rot_behind_the_projection_table() -> None:
    assert set(emit_legacy_decisions.EVAL_UNITS) == {
        key for key, _, _ in emit_legacy_decisions.EVAL_PROJECTION
    }
    assert set(emit_legacy_decisions.PROJECTION_ENCODING) == {
        projection for _, _, projection in emit_legacy_decisions.EVAL_PROJECTION
    } | {projection for _, projection, _, _ in emit_legacy_decisions.BRACKET_PROJECTION}


# ---------------------------------------------------------------------------
# Review #876: the new declared differences point at real code
# ---------------------------------------------------------------------------


def test_the_new_declared_differences_cite_code_that_exists(
    strategy: produce_fields.StrategyInputs,
    anchor: produce_fields.OpenAnchor,
) -> None:
    """L10/L11/L12 must name real symbols, not plausible ones."""
    declared = {
        item["id"]: item
        for item in emit_legacy_decisions._declared_differences(strategy, anchor)
    }
    assert set(declared) == {f"L{index}" for index in range(1, 13)}

    orchestrator = (
        produce_fields.REPO_ROOT / "services" / "trading" / "orchestrator.py"
    ).read_text(encoding="utf-8")
    assert "def _filter_reentry_guarded_signals" in orchestrator
    execution_yaml = (produce_fields.REPO_ROOT / "config" / "execution.yaml").read_text(
        encoding="utf-8"
    )
    assert "entry_reentry_guard:" in execution_yaml
    assert (
        "L10" in declared
        and "entry_reentry_guard" in declared["L10"]["value"]["config"]
    )
    assert "UPPER BOUND" in declared["L10"]["note"]

    adapter = (
        produce_fields.REPO_ROOT
        / "shared"
        / "strategy"
        / "entry"
        / "setup_d_adapter.py"
    ).read_text(encoding="utf-8")
    assert '"no_market_context"' in adapter
    assert '"regime_gate_blocked"' in adapter
    assert "_apply_regime_gate" in adapter
    assert declared["L11"]["value"]["regime_gate_enabled_in_yaml"] is False

    assert "atr_90th_percentile" in declared["L12"]["note"]
    walkforward = emit_legacy_decisions.WALKFORWARD_SCRIPT.read_text(encoding="utf-8")
    assert "Look-ahead safety + live parity" in walkforward
