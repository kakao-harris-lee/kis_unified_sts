"""Regression tests for the 2026-10-08 independent-review dispositions.

One test per finding, each written so the finding's own failure mode — not a
paraphrase of it — is what turns the test red.
"""

from __future__ import annotations

import json
import socket
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from .. import runner
from ..differences import declared_difference_ids, declared_differences
from ..lineage import entry_comparison
from ..replay import _attribute_rule
from ..strategy import load_strategy_content
from . import _cp3_fixtures as fx


def _content() -> runner.LoadedStrategyContent:
    return runner.load_strategy_content(
        strategy_path=fx.STRATEGY_PATH, bindings_path=fx.BINDINGS_PATH
    )


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "tos").is_dir() and (candidate / "config").is_dir():
            return candidate
    pytest.fail("cannot locate the repo root — this check cannot be skipped")


# ---------------------------------------------------------------------------
# item 5 — source_id constancy
# ---------------------------------------------------------------------------


def test_mixed_source_id_is_refused(tmp_path: Path) -> None:
    """Two producers in one artifact have no single lineage parent identity."""
    lines = fx.synthetic_stream(bar_count=4)
    lines[2]["source_id"] = "some-other-producer/9.9.9"
    path = fx.write_jsonl(tmp_path / "fields.jsonl", lines)
    with pytest.raises(runner.Cp3RunnerRefusal, match="differs from the file's first"):
        runner.read_field_records(path)


def test_source_id_is_carried_as_a_value_not_a_pointer(tmp_path: Path) -> None:
    """The run records the producer identity itself, for the lineage parent."""
    path = fx.write_jsonl(tmp_path / "fields.jsonl", fx.synthetic_stream(bar_count=4))
    artifacts = runner.run_replay(
        records=runner.read_field_records(path), content=_content()
    )
    assert artifacts.source_id == "tos-cp3-b1b-test/0.1.0"


# ---------------------------------------------------------------------------
# item 11 — extra `fields` keys
# ---------------------------------------------------------------------------


def test_extra_fields_key_is_refused(tmp_path: Path) -> None:
    """An ungoverned field would still enter the snapshot digest.

    The journal level already refused extra top-level keys; this closes the same
    hole one level down, where it matters more: every ``fields`` value is inside
    ``FieldRecord.snapshot_canonical_digest``, so admitting an unknown key lets
    content nobody governs change the Capsule identity the trace is bound to.
    """
    lines = fx.synthetic_stream(bar_count=3)
    lines[1]["fields"]["smuggled_x100"] = 1234
    path = fx.write_jsonl(tmp_path / "fields.jsonl", lines)
    with pytest.raises(runner.Cp3RunnerRefusal, match="unexpected key"):
        runner.read_field_records(path)


# ---------------------------------------------------------------------------
# item 12 — the bindings path is the boot's derivation, not a basename
# ---------------------------------------------------------------------------


def test_bindings_file_outside_the_strategy_config_dir_is_refused(
    tmp_path: Path,
) -> None:
    """A correctly-NAMED bindings file in the wrong directory is still refused.

    This is the half a basename check misses: ``strategy_bindings.yaml`` under
    some unrelated directory passes a name test and would make the run resolve
    operands against content the deployment does not have.
    """
    stray = tmp_path / "strategy_bindings.yaml"
    stray.write_text(fx.BINDINGS_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(runner.Cp3RunnerRefusal, match="SAME config_dir"):
        runner.load_strategy_content(
            strategy_path=fx.STRATEGY_PATH, bindings_path=stray
        )


def test_the_committed_pair_is_the_boot_derivation() -> None:
    """The committed layout IS ``config_dir/strategies/x.yaml`` + sibling file."""
    assert fx.STRATEGY_PATH.parent.name == "strategies"
    assert fx.BINDINGS_PATH.parent == fx.STRATEGY_PATH.parent.parent
    assert fx.BINDINGS_PATH.name == "strategy_bindings.yaml"


# ---------------------------------------------------------------------------
# item 6 — the hand-off guard tracks the INJECTED bound
# ---------------------------------------------------------------------------


def test_a_larger_injected_bound_is_not_false_accused_and_does_not_raise_the_cap(
    tmp_path: Path,
) -> None:
    """Bound 2 and 3 run WITHOUT refusal — and still realize exactly one order.

    Two facts, and the second is a finding rather than a disposition.

    **The disposition (review item 6).** The guard is gated on the injected
    ``max_unresolved_send_per_scope``, so a run configured with a larger budget
    is no longer accused of a seal breach. The previous revision hardcoded
    at-most-one and would have raised here.

    **The finding.** Raising the bound does not raise the realized-order count.
    Measured at bounds 1 / 2 / 3: ``realized=[5]``, ``denials=2``, ``handoffs=1``
    every time. The binding constraint is NOT the send bound — it is the
    provisional reservation projection's absent release path, which
    ``tos.backtest`` declares in its own package docstring ("at most one order
    per scope, for the whole run … ``RELEASED`` is absent … even a ``REJECT``
    leaves the scope occupied"). What the bound DOES change is where the flow
    halts — ``LEDGER_VERIFICATION`` at 1, ``ATOMIC_COMMIT`` at 2+ — which is the
    evidence that the engine really consumes the injected value and that the cap
    is downstream of it. So ``--max-unresolved-send-per-scope`` cannot be used to
    get a second fill out of this harness, and the lineage's B1b-D1 says so.
    """
    lines = fx.synthetic_stream(bar_count=30, entry_at=(5, 15, 25))
    path = fx.write_jsonl(tmp_path / "fields.jsonl", lines)
    records = runner.read_field_records(path)
    seen_steps: dict[int, str | None] = {}
    for bound in (1, 2, 3):
        artifacts = runner.run_replay(
            records=records, content=_content(), max_unresolved_send_per_scope=bound
        )
        assert [order["bar_index"] for order in artifacts.realized_orders] == [5], (
            f"bound={bound}: the realized count is capped by the absent release "
            "path, not by this bound"
        )
        assert artifacts.capacity_denials == 2
        assert artifacts.run.handoff_count == 1
        by_index = {line["bar_index"]: line for line in artifacts.trace_lines}
        assert by_index[15]["capacity_denied"] is True
        seen_steps[bound] = by_index[15]["flow_halt_step"]
    # The bound IS consumed — it moves the halt step — it just is not the cap.
    assert seen_steps[1] == "LEDGER_VERIFICATION"
    assert seen_steps[2] == seen_steps[3] == "ATOMIC_COMMIT"


def test_one_hand_off_is_still_the_default_bound(tmp_path: Path) -> None:
    """With the default bound, the second firing is denied — the B4 cap."""
    path = fx.write_jsonl(
        tmp_path / "fields.jsonl", fx.synthetic_stream(bar_count=30, entry_at=(5, 15))
    )
    artifacts = runner.run_replay(
        records=runner.read_field_records(path), content=_content()
    )
    assert runner.DEFAULT_MAX_UNRESOLVED_SEND_PER_SCOPE == 1
    assert len(artifacts.realized_orders) == 1
    assert artifacts.capacity_denials == 1


# ---------------------------------------------------------------------------
# item 15 — NO_OUTCOME is refused, not a silent floor
# ---------------------------------------------------------------------------


class _NoOutcomeResult:
    """An ``EventResult`` double whose pipeline emitted nothing."""

    pipeline = None
    flow = None
    halt_reason = None


def test_a_bar_with_no_emitted_outcome_is_refused() -> None:
    """A tick that produced no Decision is not a comparable decision.

    Exercised at the attribution seam, which is where the fact is first
    observable. An all-halt run would otherwise have exited 0 with every count
    reconciling — the "silent floor" the review named.
    """
    record = runner.FieldRecord(
        raw_event_id="x:1",
        source_id="s",
        instrument=fx.INSTRUMENT,
        as_of_ms=1,
        fields=fx.neutral_fields(0),
    )
    collected: list[str] = []
    rule_id, kind_label = _attribute_rule(
        result=_NoOutcomeResult(),
        record=record,
        content=_content(),
        no_outcome_bars=collected,
    )
    assert (rule_id, kind_label) == ("none", "NO_OUTCOME")
    assert collected == ["x:1"], "the bar must be recorded for the run-level refusal"


def test_run_replay_refuses_when_any_bar_emitted_no_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The run-level refusal fires, naming the count and the first bar."""
    from .. import replay as replay_module

    path = fx.write_jsonl(tmp_path / "fields.jsonl", fx.synthetic_stream(bar_count=6))
    monkeypatch.setattr(replay_module, "_outcome_rationale", lambda _result: None)
    with pytest.raises(runner.Cp3RunnerRefusal, match="produced no"):
        runner.run_replay(records=runner.read_field_records(path), content=_content())


# ---------------------------------------------------------------------------
# item 13 — the declared differences, including the operator-approved two
# ---------------------------------------------------------------------------


def _declared(direction: str = "LONG") -> list[dict[str, str]]:
    """The declared-difference block as a run of *direction* would write it.

    Rendered from the committed strategy content rather than from literals, so
    the ``entry_comparison`` phrase these assertions read is the one a real run
    would emit. ``LONG`` is the default because these tests predate the SHORT
    render; the SHORT half is covered by
    ``test_cp3_short_strategy_content.py``.
    """
    paths = {
        "LONG": (fx.STRATEGY_PATH, fx.BINDINGS_PATH),
        "SHORT": (fx.SHORT_STRATEGY_PATH, fx.SHORT_BINDINGS_PATH),
    }[direction]
    content = load_strategy_content(strategy_path=paths[0], bindings_path=paths[1])
    return [
        dict(item)
        for item in declared_differences(
            direction=content.direction,
            entry_comparison=entry_comparison(content),
        )
    ]


def test_every_declared_difference_is_present_and_well_formed() -> None:
    """Nine entries, unique ids, each with a non-trivial note."""
    ids = declared_difference_ids()
    assert ids == (
        "B1b-D1",
        "B1b-D2",
        "B1b-D3",
        "B1b-D4",
        "B1b-D5",
        "B1b-D6",
        "B1b-D7",
        "B1b-D8",
        "B1b-D9",
    )
    assert len(set(ids)) == len(ids)
    for item in _declared():
        assert item["item"].strip()
        assert len(str(item["note"]).strip()) > 80, item["id"]


def test_the_two_operator_approved_differences_cite_their_decisions() -> None:
    """결정 5 and 결정 6 are registered with their kickoff citation.

    They were approved as *intended differences* on 2026-10-07; an artifact the
    parity report is built from must carry them, or the report attributes an
    approved difference to a policy disagreement.
    """
    by_id = {item["id"]: item for item in _declared()}
    assert "결정 5" in by_id["B1b-D8"]["item"]
    assert "short_blocked_regimes" in by_id["B1b-D8"]["note"]
    assert "결정 6" in by_id["B1b-D9"]["item"]
    assert "PAC" in by_id["B1b-D9"]["note"]


def test_the_band_form_difference_cites_b1a_d3_not_d7() -> None:
    """B1b-D2 names the right B1a entry.

    D7 is the measured-D7-generator entry and its own note says its counts must
    not be read as the band's error bar; the band form is D3.
    """
    by_id = {item["id"]: item for item in _declared()}
    assert "B1a D3" in by_id["B1b-D2"]["item"]
    assert "D3" in by_id["B1b-D2"]["note"]
    # Asserted on the SENTENCE that attributes the band form, not on a Korean
    # particle (verification D-3: `"B1a D7 의" not in strategy` pinned "의" and
    # would have passed any other inflection). The file legitimately MENTIONS
    # D7 — to say the band form is not D7 — so a bare `"B1a D7" not in` is wrong
    # too; what must hold is that the attributing line cites D3.
    strategy = fx.STRATEGY_PATH.read_text(encoding="utf-8")
    attributing = [line for line in strategy.splitlines() if "밴드 꼴" in line]
    assert attributing, "the band-form attribution comment is gone"
    for line in attributing:
        assert "D3" in line, f"band form attributed without D3: {line.strip()}"
        assert "D7" not in line, f"band form attributed to D7: {line.strip()}"


def test_the_exposure_precondition_difference_is_declared() -> None:
    """B1b-D7: FLAT carries no exposure precondition, and that is recorded."""
    by_id = {item["id"]: item for item in _declared()}
    note = by_id["B1b-D7"]["note"]
    assert "exposure" in note
    assert "position-scoped" in note


def test_flat_fires_with_no_position_ever_opened(tmp_path: Path) -> None:
    """The behaviour B1b-D7 declares, measured rather than asserted in prose.

    Nothing is ever opened in this stream — the entry gate never fires — yet
    every reverted bar still proposes FLAT. That is the difference from the
    legacy position-scoped exit, and it is why B3 must compare FLAT intent
    rather than FLAT count.
    """
    lines = fx.synthetic_stream(
        bar_count=12,
        special={3: fx.reverted_fields, 7: fx.reverted_fields, 9: fx.reverted_fields},
    )
    path = fx.write_jsonl(tmp_path / "fields.jsonl", lines)
    artifacts = runner.run_replay(
        records=runner.read_field_records(path), content=_content()
    )
    assert artifacts.rule_fire_counts.get("R1-ENTRY-LONG") is None
    assert artifacts.outcome_counts["FLAT"] == 3
    assert [order["bar_index"] for order in artifacts.realized_orders] == [3]


# ---------------------------------------------------------------------------
# item 14 — the R1-before-R3 non-overlap premise
# ---------------------------------------------------------------------------


def test_entry_cutoff_and_eod_cannot_overlap() -> None:
    """R1 can never contend with R3, pinned against the legacy YAML.

    The rule order (entry first) is only safe because the entry window closes
    before the EOD time, so a bar can never satisfy both. That rested on two
    numbers in the legacy config with nothing checking them; if an operator
    moves the cutoff to 400 minutes, the premise breaks and this fails.
    """
    path = (
        _repo_root()
        / "config"
        / "strategies"
        / "futures"
        / "setup_d_vwap_reversion.yaml"
    )
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    entry = document["strategy"]["entry"]["params"]
    exit_params = document["strategy"]["exit"]["params"]
    cutoff_minutes = int(entry["no_entry_after_minutes_since_open"])
    # The open anchor B1a uses for `entry_window` (era rule, 09:00 KST).
    anchor_minutes = 9 * 60
    eod_minutes = int(exit_params["eod_close_hour"]) * 60 + int(
        exit_params["eod_close_minute"]
    )
    assert cutoff_minutes == 345, f"{path}: cutoff moved to {cutoff_minutes}"
    assert eod_minutes == 15 * 60 + 15, f"{path}: EOD moved to {eod_minutes} minutes"
    assert anchor_minutes + cutoff_minutes < eod_minutes, (
        f"entry window closes at {anchor_minutes + cutoff_minutes} min but EOD is "
        f"{eod_minutes} min — R1 and R3 can now contend on one bar, and R1 being "
        "first would swallow an EOD exit"
    )


# ---------------------------------------------------------------------------
# item 9 — lineage carries repo + interpreter coordinates
# ---------------------------------------------------------------------------


def test_lineage_tool_block_carries_repo_and_runtime_coordinates(
    tmp_path: Path,
) -> None:
    """A 3.12 run and a 3.11 run no longer produce identical lineage."""
    path = fx.write_jsonl(tmp_path / "fields.jsonl", fx.synthetic_stream(bar_count=4))
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
    tool = json.loads((tmp_path / "out" / "lineage.json").read_text())["tool"]
    git = tool["git"]
    assert git["repo_root"]
    assert git["commit"] is None or (
        len(git["commit"]) == 40 and all(c in "0123456789abcdef" for c in git["commit"])
    )
    assert git["dirty"] in (True, False, "UNKNOWN")
    runtime = tool["runtime"]
    assert runtime["python"].count(".") == 2
    assert runtime["python_implementation"]
    assert runtime["sqlite"]
    # The code digest covers the WHOLE package, not a hardcoded file list: the
    # decomposition into sibling modules would have silently fallen out of a
    # two-file list.
    assert len(tool["code_digest"]) == 64


def _recompute_cp3_digest(root: Path) -> str:
    """The package digest, recomputed INDEPENDENTLY of the function under test.

    Spells out the shape rather than calling the implementation: a test that
    re-uses the code it checks cannot tell a correct digest from a consistent
    one. The shape is the one ``observe_source_tree_digest`` uses — sorted
    ``[relative posix path, sha256(bytes)]`` pairs under ``{"files": …}``,
    folded through the same canonical scheme.
    """
    import hashlib

    from .._base import SCHEME

    entries = [
        [
            path.relative_to(root).as_posix(),
            hashlib.sha256(path.read_bytes()).hexdigest(),
        ]
        for path in sorted(root.rglob("*.py"))
        if "__pycache__" not in path.parts
    ]
    digest = SCHEME.compute_digest({"files": entries})
    assert isinstance(digest, str)
    return digest


def test_cp3_code_digest_is_the_digest_of_every_tracked_source_file() -> None:
    """The digest EQUALS an independent fold over every tracked ``*.py``.

    The 2026-10-08 verification (D-1) found the previous version of this test
    computed the file list and then never used it, so restoring the old
    hardcoded two-file body still passed — a guard that admitted exactly what it
    named. The equality below is what bites: a digest over any other file set
    (two files, or a set that misses a module) cannot match it.
    """
    from .. import lineage as lineage_module

    package_root = Path(lineage_module.__file__).resolve().parent
    tracked = sorted(
        path for path in package_root.rglob("*.py") if "__pycache__" not in path.parts
    )
    assert len(tracked) >= 10, "the package has more than a couple of modules now"

    digest = lineage_module._cp3_code_digest()
    assert digest == lineage_module._cp3_code_digest(), "digest must be stable"
    assert len(digest) == 64
    assert digest == _recompute_cp3_digest(package_root), (
        "the recorded digest is not the fold over the package's tracked sources "
        f"({len(tracked)} files) — it is covering some other file set"
    )


def test_cp3_code_digest_moves_when_a_tracked_file_changes(tmp_path: Path) -> None:
    """Appending one byte to a NON-runner module changes the digest.

    The other half of D-1's disposition, and the half a hardcoded two-file list
    fails outright: ``differences.py`` is not ``runner.py`` or ``__init__.py``,
    so a digest over only those two is blind to it. Run over a copy so nothing
    in the real package is touched (and so the write stays inside ``tmp_path``,
    which this suite's own guard requires).
    """
    import shutil

    from .. import lineage as lineage_module

    package_root = Path(lineage_module.__file__).resolve().parent
    copy_root = tmp_path / "cp3"
    shutil.copytree(
        package_root, copy_root, ignore=shutil.ignore_patterns("__pycache__")
    )

    baseline = lineage_module._cp3_code_digest(copy_root)
    assert baseline == lineage_module._cp3_code_digest(), (
        "an untouched copy must digest to the same value as the original — "
        "otherwise this test's baseline is measuring the copy, not the content"
    )

    victim = copy_root / "differences.py"
    assert victim.is_file(), "the non-runner module this test perturbs is gone"
    with victim.open("ab") as handle:
        handle.write(b"\n")

    after = lineage_module._cp3_code_digest(copy_root)
    assert after != baseline, (
        "appending a byte to differences.py did not move the digest — the fold "
        "is not covering every tracked module (this is the exact defect a "
        "hardcoded ('__init__.py', 'runner.py') list reintroduces)"
    )
    assert after == _recompute_cp3_digest(copy_root)


def test_malformed_git_index_yields_unknown_never_a_traceback(
    tmp_path: Path,
) -> None:
    """Every unreadable index shape returns ``"UNKNOWN"`` (verification D-2).

    Four shapes, each of which reached a different failure before: a body with
    no NUL terminator (``bytes.index`` -> ``ValueError``), a truncated entry, a
    v3 entry with ``CE_EXTENDED`` set (whose name does NOT start at
    ``offset + 62``, so the old parser mis-set every subsequent offset while
    reporting a confident answer), and a missing file. A guessed ``False`` on
    any of them would stamp ``dirty: false`` onto an artifact built from an
    unknown tree.
    """
    import struct

    from .. import lineage as lineage_module

    git_dir = tmp_path / "gitdir"
    git_dir.mkdir()
    index = git_dir / "index"

    # 1. header claims 5 entries; body has no NUL at all
    index.write_bytes(b"DIRC" + struct.pack(">II", 2, 5) + b"\xff" * 80)
    assert lineage_module._worktree_dirty(tmp_path, git_dir) == "UNKNOWN", (
        "an index body with no NUL terminator must read UNKNOWN (bytes.index "
        "raises ValueError there)"
    )

    # 2. truncated inside the first entry's 62-byte prefix
    index.write_bytes(b"DIRC" + struct.pack(">II", 2, 1) + b"\x00" * 10)
    assert (
        lineage_module._worktree_dirty(tmp_path, git_dir) == "UNKNOWN"
    ), "an index truncated inside the first 62-byte prefix must read UNKNOWN"

    # 3. v3 entry with CE_EXTENDED — the shape the false comment claimed was
    #    "already handled"
    entry = bytearray(62 + 8)
    struct.pack_into(">H", entry, 60, lineage_module._CE_EXTENDED)
    entry[62:66] = b"a.py"
    index.write_bytes(b"DIRC" + struct.pack(">II", 3, 1) + bytes(entry))
    assert lineage_module._worktree_dirty(tmp_path, git_dir) == "UNKNOWN", (
        "a v3 entry with CE_EXTENDED must read UNKNOWN: an extra 2-byte field "
        "follows the prefix, so the name does not start at offset+62 and every "
        "later entry offset would be wrong — the shape the deleted comment "
        "claimed was already handled"
    )

    # 3b. the SAME entry without the extended bit is parsed, not refused —
    #     otherwise the check above would pass by refusing all of v3.
    struct.pack_into(">H", entry, 60, 0)
    index.write_bytes(b"DIRC" + struct.pack(">II", 3, 1) + bytes(entry))
    assert lineage_module._worktree_dirty(tmp_path, git_dir) is True, (
        "the same v3 entry WITHOUT the extended bit must be parsed (a.py is "
        "absent, so dirty) — otherwise the check above passes by refusing all "
        "of index v3, which would make it decorative"
    )

    # 4. no index file
    assert (
        lineage_module._worktree_dirty(tmp_path, git_dir / "absent") == "UNKNOWN"
    ), "a missing index file must read UNKNOWN, never a guessed False"


# ---------------------------------------------------------------------------
# item 10 — the D1.4 guards are actually installed for this suite
# ---------------------------------------------------------------------------


def test_the_network_guard_is_installed() -> None:
    """A non-loopback connect is refused — the autouse conftest guard is live.

    Before this suite had a ``conftest.py``, pytest loaded none (the
    ``tos/runtime/tests`` one is a sibling, never an ancestor) and both D1.4
    guards were absent while the suite called itself hermetic.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        with pytest.raises(AssertionError, match="network call to"):
            sock.connect(("198.51.100.1", 80))


def test_the_write_guard_is_installed(tmp_path: Path) -> None:
    """A write outside ``tmp_path`` is refused; inside it is allowed."""
    (tmp_path / "allowed.txt").write_text("fine", encoding="utf-8")
    with pytest.raises(PermissionError, match="refused"):
        (tmp_path.parent / "escaped.txt").write_text("no", encoding="utf-8")


# ---------------------------------------------------------------------------
# item 16 — the determinism claim is narrowed AND the predicate widened
# ---------------------------------------------------------------------------


def test_lineage_carries_no_clock_derived_timestamp(tmp_path: Path) -> None:
    """No clock-derived datetime anywhere, with the datetime-bearing inputs named.

    The predicate catches ``YYYY-MM-DD``, ``YYYYMMDDTHHMMSS`` and ``HH:MM:SS``
    shapes — the previous one matched only the first, which is why it sat happily
    beside ``…20251208T084500+0900``. The input-derived values that legitimately
    carry a datetime are whitelisted BY PATH, so the whitelist is auditable
    rather than a blanket exemption.
    """
    import re

    path = fx.write_jsonl(tmp_path / "fields.jsonl", fx.synthetic_stream(bar_count=4))
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
    assert lineage["determinism"]["no_clock_derived_timestamp"] is True
    assert lineage["determinism"]["datetime_bearing_inputs_reproduced_verbatim"]

    shapes = (
        re.compile(r"\d{4}-\d{2}-\d{2}"),
        re.compile(r"\d{8}T\d{6}"),
        re.compile(r"\d{2}:\d{2}:\d{2}"),
    )
    #: Values that legitimately carry a datetime because the INPUT does: B1a's
    #: event ids, the paths naming them, and this slice's own expiry-free prose
    #: citations of dated decisions.
    whitelist_prefixes = (
        "lineage.parents.fields_jsonl.path",
        "lineage.parents.fields_lineage_json.path",
        "lineage.parents.strategy_file.path",
        "lineage.parents.strategy_bindings_file.path",
        "lineage.tool.git.repo_root",
        "lineage.counts.realized_orders",
        "lineage.declared_differences",
        "lineage.reconciliation.enforced_by",
        "lineage.determinism.datetime_bearing_inputs_reproduced_verbatim",
    )
    offenders: list[str] = []

    def walk(node: object, where: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{where}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{where}[{index}]")
        elif isinstance(node, str):
            if where.startswith(whitelist_prefixes):
                return
            if any(shape.search(node) for shape in shapes):
                offenders.append(f"{where}={node!r}")

    walk(lineage, "lineage")
    assert offenders == [], offenders


def test_the_widened_predicate_would_have_caught_the_old_shape() -> None:
    """The red proof for the widening: the shape the old predicate missed.

    ``…20251208T084500+0900`` is exactly the value that sat in the lineage beside
    ``no_timestamps: true``. The old predicate (first four chars digits, fifth a
    dash) cannot match it; the new one must.
    """
    import re

    sample = "101S6000:1m:20251208T084500+0900"
    old_predicate = len(sample) >= 8 and sample[:4].isdigit() and sample[4:5] == "-"
    assert old_predicate is False, "the old predicate is being misrepresented"
    assert re.compile(r"\d{8}T\d{6}").search(sample) is not None


# ---------------------------------------------------------------------------
# item 17 — the dead constant is gone, and the price mapping still holds
# ---------------------------------------------------------------------------


def test_no_dead_price_field_constant() -> None:
    """``_PRICE_FIELD_KEYS`` was unused; it is gone rather than wired up."""
    from .. import contract

    assert not hasattr(contract, "_PRICE_FIELD_KEYS")


def test_price_mapping_is_an_exact_decimal_shift() -> None:
    """The documented ×100 inverse: a scale shift, never a float divide."""
    record = runner.FieldRecord(
        raw_event_id="x:1",
        source_id="s",
        instrument=fx.INSTRUMENT,
        as_of_ms=1,
        fields={
            **fx.neutral_fields(0),
            "close_x100": 58_333,
            "open_x100": 58_333,
            "high_x100": 58_333,
            "low_x100": 58_333,
        },
    )
    bars, _ = runner.build_bars((record,))
    assert bars[0].close_price == Decimal("583.33")
