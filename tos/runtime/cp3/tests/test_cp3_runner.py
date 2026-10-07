"""CP-3 B1b — loader / value-seam / driver / refusal / determinism evidence.

Hermetic: synthetic JSONL written under ``tmp_path``, the committed strategy
content read from the repo, no network, no ambient env, no clock.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from tos.dsl import DecisionKind
from tos.dsl.context_value import VALUE_NAMESPACE
from tos.engine import HaltReason
from tos.marketfeed.value import view_digest_matches

# Relative, not absolute: `import cp3.runner` from a file under tos/ is a
# TOS-FW-A violation (the firewall allowlist does not name `cp3`), while a
# relative import is skipped by the gate. See tests/__init__.py.
from .. import runner
from . import _cp3_fixtures as fx

# ---------------------------------------------------------------------------
# (a) a synthetic stream round-trips into Bars and the driver runs
# ---------------------------------------------------------------------------


def _content() -> runner.LoadedStrategyContent:
    """The committed strategy content, loaded through the production loader."""
    return runner.load_strategy_content(
        strategy_path=fx.STRATEGY_PATH, bindings_path=fx.BINDINGS_PATH
    )


def test_fifty_bar_stream_round_trips_into_bars_and_drives(tmp_path: Path) -> None:
    """~50 synthetic bars become a validated ``BarStream`` and the core runs them.

    The round trip is asserted on the *structure*, not on a count alone: every
    bar's ``timestamp_coordinate`` is its record's ``as_of_ms`` verbatim, the
    prices are the exact ×100 inverse, and the trace carries one line per bar.
    """
    path = fx.write_jsonl(tmp_path / "fields.jsonl", fx.synthetic_stream(bar_count=50))
    records = runner.read_field_records(path)
    assert len(records) == 50

    bars, by_index = runner.build_bars(records)
    assert len(bars) == 50
    assert [bar.bar_index for bar in bars] == list(range(50))
    assert [bar.timestamp_coordinate for bar in bars] == [
        record.as_of_ms for record in records
    ]
    # The declared Decimal/int mapping: close_x100 58000 -> Decimal("580.00") via
    # an exact scale shift. Compared NUMERICALLY, because CanonicalDecimal
    # normalizes at validation time (580.00 -> 5.8E+2): the normalization is the
    # point — numerically-equal magnitudes share one digest — so asserting the
    # repr would pin the wrong property.
    assert bars[0].close_price == Decimal("580")
    assert bars[1].close_price == Decimal("580.01")
    assert bars[0].high_price == Decimal("580.50")
    assert bars[0].volume == Decimal(100)
    assert by_index[0] is records[0]

    artifacts = runner.run_replay(records=records, content=_content())
    assert artifacts.bars_read == 50
    assert artifacts.bars_driven == 50
    assert len(artifacts.trace_lines) == 50
    # Neutral bars fire nothing: the default is reached every time.
    assert artifacts.outcome_counts == {DecisionKind.NO_ACTION.value: 50}
    assert artifacts.rule_fire_counts == {"R0-DEFAULT-NO-ACTION": 50}
    assert artifacts.capacity_denials == 0
    assert artifacts.run.closes_no_ev is True


def test_value_view_reaches_the_dsl_at_resolved_values() -> None:
    """The seam is asserted positively: the published view carries every field.

    Without this the suite could pass with a resolver that published nothing —
    every operand would silently degrade to ``UNKNOWN`` and every bar would
    read as a legitimate no-action.
    """
    records = (
        runner.FieldRecord(
            raw_event_id="x:1",
            source_id="s",
            instrument=fx.INSTRUMENT,
            as_of_ms=1,
            fields=fx.entry_fields(0),
        ),
    )
    source = runner.Cp3CapsuleSource(
        instrument_key=_content().instrument_key,
        direction="LONG",
        records_by_bar_index={0: records[0]},
    )
    bars, _ = runner.build_bars(records)
    capsule = source(bars[0])
    resolver = runner.Cp3FieldResolver(
        records_by_snapshot_id={records[0].snapshot_id: records[0]}
    )
    payload = resolver(capsule, instrument_key=_content().instrument_key)
    assert payload.value_view is not None
    mapping = payload.value_view.as_environment_mapping()
    assert set(mapping) == set(runner.REQUIRED_FIELD_KEYS)
    assert mapping["z_x1000"] == -1_800
    assert mapping["entry_window"] is True
    assert mapping["session_token"] == "2025-12-08"
    # The namespace the DSL ref walks.
    assert VALUE_NAMESPACE == "resolved_values"
    # THE regression guard for review item 1: the recorded digest must be the
    # digest of the view's own content under the KERNEL's preimage (which
    # includes the snapshot binding and sorts by field_key). Before the fix this
    # was False on every bar, and the mismatch rode into every outcome_digest.
    assert view_digest_matches(payload.value_view, runner.SCHEME) is True
    # ...and the values are published in field_key order, the ordering the
    # kernel's preimage uses.
    assert [value.field_key for value in payload.value_view.values] == sorted(
        runner.REQUIRED_FIELD_KEYS
    )


# ---------------------------------------------------------------------------
# (b) the entry rule fires on exactly its bar; the second is capacity-denied
# ---------------------------------------------------------------------------


def test_entry_fires_on_its_bar_and_the_second_is_capacity_denied(
    tmp_path: Path,
) -> None:
    """One realized entry + an exact capacity denial — the B4 cap FIRING.

    The second satisfying bar must be ``ACTION`` + ``capacity_denied``, never an
    error and never a silent no-action: a run that errored there would make the
    cap indistinguishable from a defect, and one that read ``NO_ACTION`` would
    make it indistinguishable from the rule not firing.
    """
    lines = fx.synthetic_stream(bar_count=50, entry_at=(10, 30))
    path = fx.write_jsonl(tmp_path / "fields.jsonl", lines)
    artifacts = runner.run_replay(
        records=runner.read_field_records(path), content=_content()
    )

    by_index = {line["bar_index"]: line for line in artifacts.trace_lines}
    first, second = by_index[10], by_index[30]

    assert first["outcome_kind"] == DecisionKind.ACTION.value
    assert first["rule_id"] == "R1-ENTRY-LONG"
    assert first["capacity_denied"] is False
    assert first["handed_off"] is True

    assert second["outcome_kind"] == DecisionKind.ACTION.value
    assert second["rule_id"] == "R1-ENTRY-LONG"
    assert second["capacity_denied"] is True
    assert second["handed_off"] is False
    assert second["flow_halt_reason"] == HaltReason.AT_MOST_ONE_EXPOSURE_HELD.value

    assert artifacts.capacity_denials == 1
    assert artifacts.outcome_counts[DecisionKind.ACTION.value] == 2
    assert artifacts.rule_fire_counts["R1-ENTRY-LONG"] == 2
    # Every other bar took the default.
    assert artifacts.rule_fire_counts["R0-DEFAULT-NO-ACTION"] == 48
    # WHICH bar spent the order is recorded, not inferred from handoffs=1.
    assert artifacts.realized_orders == (
        {
            "raw_event_id": lines[10]["raw_event_id"],
            "bar_index": 10,
            "rule_id": "R1-ENTRY-LONG",
            "outcome_kind": DecisionKind.ACTION.value,
        },
    )


def test_entry_threshold_is_the_authored_binding_not_an_always_true_gate(
    tmp_path: Path,
) -> None:
    """A bar one ×1000 unit short of ``-1800`` must NOT fire — the red half.

    Every other entry conjunct is true on this bar, so the only thing that can
    keep it from firing is the ``z_x1000 <= config.z_entry_max_x1000`` compare
    resolving against the authored ``-1800``. Deleting the binding, or widening
    it, flips this test.
    """
    lines = fx.synthetic_stream(
        bar_count=20, special={5: fx.near_miss_entry_fields, 9: fx.entry_fields}
    )
    path = fx.write_jsonl(tmp_path / "fields.jsonl", lines)
    artifacts = runner.run_replay(
        records=runner.read_field_records(path), content=_content()
    )
    by_index = {line["bar_index"]: line for line in artifacts.trace_lines}
    assert by_index[5]["outcome_kind"] == DecisionKind.NO_ACTION.value
    assert by_index[5]["rule_id"] == "R0-DEFAULT-NO-ACTION"
    assert by_index[9]["outcome_kind"] == DecisionKind.ACTION.value


# ---------------------------------------------------------------------------
# (c) vwap_reverted / eod produce FLAT
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("builder", "rule_id"),
    [
        (fx.reverted_fields, "R2-EXIT-VWAP-REVERTED"),
        (fx.eod_fields, "R3-EXIT-EOD"),
    ],
)
def test_exit_gates_produce_flat(tmp_path: Path, builder: object, rule_id: str) -> None:
    """``vwap_reverted`` and ``eod`` each select their FLAT rule, realized.

    One exit per run, so the single-order cap does not mask the realization —
    that interaction is covered separately below.
    """
    lines = fx.synthetic_stream(bar_count=20, special={7: builder})
    path = fx.write_jsonl(tmp_path / f"fields-{rule_id}.jsonl", lines)
    artifacts = runner.run_replay(
        records=runner.read_field_records(path), content=_content()
    )
    line = next(item for item in artifacts.trace_lines if item["bar_index"] == 7)
    assert line["outcome_kind"] == DecisionKind.FLAT.value
    assert line["rule_id"] == rule_id
    assert line["capacity_denied"] is False
    assert line["handed_off"] is True
    assert artifacts.outcome_counts[DecisionKind.FLAT.value] == 1


def test_entry_then_exit_exit_is_capacity_denied_not_reclassified(
    tmp_path: Path,
) -> None:
    """After the one order is spent, a FLAT still reads FLAT — and is denied.

    This is the honest shape of the B4 cap on the exit side, and it is why the
    trace records the decision kind and the denial as two independent facts.
    """
    lines = fx.synthetic_stream(
        bar_count=30, entry_at=(4,), special={12: fx.reverted_fields}
    )
    path = fx.write_jsonl(tmp_path / "fields.jsonl", lines)
    artifacts = runner.run_replay(
        records=runner.read_field_records(path), content=_content()
    )
    by_index = {line["bar_index"]: line for line in artifacts.trace_lines}
    assert by_index[4]["handed_off"] is True
    assert by_index[12]["outcome_kind"] == DecisionKind.FLAT.value
    assert by_index[12]["rule_id"] == "R2-EXIT-VWAP-REVERTED"
    assert by_index[12]["capacity_denied"] is True
    assert len(artifacts.realized_orders) == 1
    assert artifacts.realized_orders[0]["bar_index"] == 4


def test_an_early_exit_spends_the_single_order_before_any_entry(
    tmp_path: Path,
) -> None:
    """The cap is spent by the FIRST firing of ANY rule — not by the first entry.

    The real 35,612-bar run lands exactly here: B1a's first bar carries
    ``vwap_reverted: true`` (close sits on the session VWAP), so the one order
    goes to an exit FLAT on bar 0 and every one of the 392 entry firings is
    capacity-denied. Reading ``handoffs=1`` beside ``ACTION=392`` as "an entry
    was realized" is therefore wrong, and this test is what keeps
    ``realized_order`` honest about it.
    """
    lines = fx.synthetic_stream(
        bar_count=20, entry_at=(11,), special={1: fx.reverted_fields}
    )
    path = fx.write_jsonl(tmp_path / "fields.jsonl", lines)
    artifacts = runner.run_replay(
        records=runner.read_field_records(path), content=_content()
    )
    assert artifacts.realized_orders == (
        {
            "raw_event_id": lines[1]["raw_event_id"],
            "bar_index": 1,
            "rule_id": "R2-EXIT-VWAP-REVERTED",
            "outcome_kind": DecisionKind.FLAT.value,
        },
    )
    by_index = {line["bar_index"]: line for line in artifacts.trace_lines}
    # The entry still FIRES — it is denied at the ledger, not reclassified.
    assert by_index[11]["outcome_kind"] == DecisionKind.ACTION.value
    assert by_index[11]["rule_id"] == "R1-ENTRY-LONG"
    assert by_index[11]["capacity_denied"] is True
    assert artifacts.run.handoff_count == 1


# ---------------------------------------------------------------------------
# (d) refusals
# ---------------------------------------------------------------------------


def test_missing_source_id_is_refused(tmp_path: Path) -> None:
    """A line missing a journal key refuses the whole read, naming the key."""
    lines = fx.synthetic_stream(bar_count=3)
    del lines[1]["source_id"]
    path = fx.write_jsonl(tmp_path / "fields.jsonl", lines)
    with pytest.raises(runner.Cp3RunnerRefusal, match="missing journal key"):
        runner.read_field_records(path)


def test_float_field_is_refused(tmp_path: Path) -> None:
    """A float field refuses — the Critical Input value shape is bool/int/str."""
    lines = fx.synthetic_stream(bar_count=3)
    lines[2]["fields"]["z_x1000"] = -1800.5
    path = fx.write_jsonl(tmp_path / "fields.jsonl", lines)
    with pytest.raises(runner.Cp3RunnerRefusal, match="is a float"):
        runner.read_field_records(path)


def test_duplicate_raw_event_id_is_refused(tmp_path: Path) -> None:
    """A repeated ``raw_event_id`` refuses — one raw event is one bar."""
    lines = fx.synthetic_stream(bar_count=4)
    lines[3]["raw_event_id"] = lines[1]["raw_event_id"]
    path = fx.write_jsonl(tmp_path / "fields.jsonl", lines)
    with pytest.raises(runner.Cp3RunnerRefusal, match="duplicate raw_event_id"):
        runner.read_field_records(path)


def test_missing_required_field_key_is_refused(tmp_path: Path) -> None:
    """A ``fields`` mapping short one governed key refuses."""
    lines = fx.synthetic_stream(bar_count=3)
    del lines[0]["fields"]["reversal_ok"]
    path = fx.write_jsonl(tmp_path / "fields.jsonl", lines)
    with pytest.raises(runner.Cp3RunnerRefusal, match="missing \\['reversal_ok'\\]"):
        runner.read_field_records(path)


def test_non_increasing_as_of_ms_is_refused(tmp_path: Path) -> None:
    """A non-advancing time coordinate refuses before ``Bar`` ever sees it."""
    lines = fx.synthetic_stream(bar_count=3)
    lines[2]["as_of_ms"] = lines[1]["as_of_ms"]
    path = fx.write_jsonl(tmp_path / "fields.jsonl", lines)
    with pytest.raises(runner.Cp3RunnerRefusal, match="strictly increase"):
        runner.read_field_records(path)


def test_empty_file_is_refused(tmp_path: Path) -> None:
    """A zero-line artifact is a producer failure, not a defined empty run."""
    path = tmp_path / "fields.jsonl"
    path.write_text("", encoding="utf-8")
    with pytest.raises(runner.Cp3RunnerRefusal, match="zero lines"):
        runner.read_field_records(path)


def test_instrument_mismatch_against_the_strategy_scope_is_refused(
    tmp_path: Path,
) -> None:
    """A replay never retargets a strategy at another instrument."""
    lines = fx.synthetic_stream(bar_count=3)
    for line in lines:
        line["instrument"] = "A05610"
        line["raw_event_id"] = line["raw_event_id"].replace(fx.INSTRUMENT, "A05610")
    path = fx.write_jsonl(tmp_path / "fields.jsonl", lines)
    with pytest.raises(runner.Cp3RunnerRefusal, match="declares dispatch instrument"):
        runner.run_replay(records=runner.read_field_records(path), content=_content())


def test_unknown_snapshot_binding_is_refused() -> None:
    """The resolver publishes a view only on an exact binding match."""
    record = runner.FieldRecord(
        raw_event_id="x:1",
        source_id="s",
        instrument=fx.INSTRUMENT,
        as_of_ms=1,
        fields=fx.neutral_fields(0),
    )
    other = runner.FieldRecord(
        raw_event_id="x:2",
        source_id="s",
        instrument=fx.INSTRUMENT,
        as_of_ms=2,
        fields=fx.entry_fields(1),
    )
    bars, _ = runner.build_bars((record,))
    capsule = runner.Cp3CapsuleSource(
        instrument_key=_content().instrument_key,
        direction="LONG",
        records_by_bar_index={0: record},
    )(bars[0])
    # The store holds a DIFFERENT record under the same id -> digest mismatch.
    resolver = runner.Cp3FieldResolver(
        records_by_snapshot_id={record.snapshot_id: other}
    )
    with pytest.raises(runner.Cp3RunnerRefusal, match="exact binding match"):
        resolver(capsule, instrument_key=_content().instrument_key)


def test_cli_exits_two_on_a_typed_refusal(tmp_path: Path) -> None:
    """Exit status 2 is the CLI's contract for every typed refusal."""
    lines = fx.synthetic_stream(bar_count=3)
    lines[0]["fields"]["eod"] = 1.0
    path = fx.write_jsonl(tmp_path / "fields.jsonl", lines)
    status = runner.main(
        [
            "--fields",
            str(path),
            "--strategy",
            str(fx.STRATEGY_PATH),
            "--bindings",
            str(fx.BINDINGS_PATH),
            "--out",
            str(tmp_path / "out"),
        ]
    )
    assert status == 2


# ---------------------------------------------------------------------------
# (e) determinism
# ---------------------------------------------------------------------------


def test_two_runs_produce_byte_identical_trace_and_lineage(tmp_path: Path) -> None:
    """Replay identity: same inputs -> byte-identical ``trace.jsonl`` + lineage.

    The lineage block carries no timestamp and no clock read, which is what
    makes this assertable at all rather than only "equal modulo a time field".
    """
    path = fx.write_jsonl(
        tmp_path / "fields.jsonl",
        fx.synthetic_stream(
            bar_count=40, entry_at=(6, 22), special={30: fx.eod_fields}
        ),
    )
    outputs = []
    for name in ("run-a", "run-b"):
        status = runner.main(
            [
                "--fields",
                str(path),
                "--strategy",
                str(fx.STRATEGY_PATH),
                "--bindings",
                str(fx.BINDINGS_PATH),
                "--out",
                str(tmp_path / name),
            ]
        )
        assert status == 0
        outputs.append(
            (
                (tmp_path / name / "trace.jsonl").read_bytes(),
                (tmp_path / name / "lineage.json").read_bytes(),
            )
        )
    assert outputs[0][0] == outputs[1][0]
    assert outputs[0][1] == outputs[1][1]

    lineage = json.loads(outputs[0][1])
    assert lineage["lineage_schema_version"] == runner.LINEAGE_SCHEMA_VERSION
    assert lineage["determinism"]["no_clock_derived_timestamp"] is True
    # The two tautological reconciliation booleans are GONE (review item 4):
    # they could not be False, because run_replay refuses an unequal run.
    assert "bars_read_equals_bars_driven" not in lineage["reconciliation"]
    assert "trace_lines_equals_bars_driven" not in lineage["reconciliation"]
    assert lineage["reconciliation"]["enforced_by"]
    assert lineage["counts"]["bars_read"] == 40
    assert lineage["counts"]["bars_driven"] == 40
    assert lineage["counts"]["capacity_denials"] == 2
    assert [order["rule_id"] for order in lineage["counts"]["realized_orders"]] == [
        "R1-ENTRY-LONG"
    ]
    # Review item 5: the producer identity by VALUE, not a pointer string.
    assert lineage["parents"]["fields_jsonl"]["source_id"] == "tos-cp3-b1b-test/0.1.0"
    # Review item 9: repo + interpreter coordinates are present.
    assert set(lineage["tool"]["git"]) == {"repo_root", "commit", "branch", "dirty"}
    assert lineage["tool"]["runtime"]["python"]
    assert lineage["tool"]["runtime"]["sqlite"]
    assert lineage["claims"]["closes_no_ev"] is True
    # The two declared differences the task names explicitly.
    ids = {item["id"] for item in lineage["declared_differences"]}
    assert {"B1b-D1", "B1b-D2"} <= ids
    # Parents: B1a's artifact digests and the installed-code digest.
    assert len(lineage["parents"]["fields_jsonl"]["sha256"]) == 64
    assert len(lineage["parents"]["strategy_file"]["sha256"]) == 64
    assert lineage["parents"]["strategy_bindings_file"]["bindings"] == {
        "z_entry_max_x1000": -1800
    }
    assert len(lineage["parents"]["installed_code"]["source_tree_digest"]) == 64


def test_lineage_block_contains_no_timestamp_shaped_value(tmp_path: Path) -> None:
    """The determinism claim is checked structurally, not just self-reported.

    A ``no_timestamps: true`` flag beside an actual timestamp is exactly the
    kind of guard that admits what it names, so the block is walked and every
    string is tested for an ISO-8601-ish shape.
    """
    path = fx.write_jsonl(tmp_path / "fields.jsonl", fx.synthetic_stream(bar_count=5))
    assert (
        runner.main(
            [
                "--fields",
                str(path),
                "--strategy",
                str(fx.STRATEGY_PATH),
                "--bindings",
                str(fx.BINDINGS_PATH),
                "--out",
                str(tmp_path / "out"),
            ]
        )
        == 0
    )
    lineage = json.loads((tmp_path / "out" / "lineage.json").read_text())

    offenders: list[str] = []

    def walk(node: object, where: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{where}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{where}[{index}]")
        elif isinstance(node, str):
            # "2026-10-08", "2026-10-08T01:02:03", "01:02:03" shapes. The
            # synthetic session_token is not in the lineage block, and B1a's
            # dataset dates are in ITS lineage, not this one.
            stripped = node.strip()
            if len(stripped) >= 8 and stripped[:4].isdigit() and stripped[4:5] == "-":
                offenders.append(f"{where}={node!r}")

    walk(lineage, "lineage")
    assert offenders == []


# ---------------------------------------------------------------------------
# (g) the placement proof
# ---------------------------------------------------------------------------


def test_cp3_adds_no_bytes_under_either_installed_package_root() -> None:
    """``tos/runtime/cp3`` is under NEITHER digest-covered package root.

    ``observe_source_tree_digest`` folds every ``*.py`` under
    ``default_package_roots()`` = (``tos`` package dir, ``tos_runtime`` package
    dir). Re-deriving the digest "before" the package existed is not possible
    inside the test, so the structural property is asserted instead: not one
    file of this package lies under either root, therefore the fold cannot see
    them and ``expected_code_digest`` cannot move.
    """
    from tos_runtime.operations.dependency_admission import default_package_roots

    roots = [root.resolve() for root in default_package_roots()]
    assert len(roots) == 2
    package_root = Path(runner.__file__).resolve().parent
    files = sorted(package_root.rglob("*.py"))
    assert files, "the package has sources to check"
    for path in files:
        for root in roots:
            assert not path.is_relative_to(root), (
                f"{path} lies under the digest-covered package root {root} — "
                "adding it would change expected_code_digest and ABORT the "
                "resident paper session"
            )
    # And the converse, so this test fails if the roots stop being the two the
    # release pin covers.
    assert {root.name for root in roots} == {"tos", "tos_runtime"}
