"""Unit tests for the N-19 / P-CA non_trade probe registrations.

``docs/plans/2026-08-07-tos-p02-nontrade-probe-definition.md`` §5/§8 defines two
probes for the two adjacent ``VERIFICATION-PROFILE-002`` bound keys
``B_non_trade_event_detect`` / ``B_non_trade_reconcile``:

* **N-19** — a documentary spec cross-check (no broker contact, ``ENV_NONE``).
* **P-CA** — an opportunistic GET-only observation, gated on N-19 landing
  first, that can never place an order.

N-19 is a documentary cross-check, not a script (``supported=False`` — see its
``skip_reason``). P-CA landed as a runnable probe
(``tools/broker_probes/probes_ca.py::probe_pca``, tested in
``tests/tools/test_broker_probes_ca.py``) once N-19
(``docs/plans/2026-09-10-tos-p02-n19-ca-spec-collation.md``) established the
CA-API exists (VERIFIED/E1); this test guards the *registration* for both —
the right kind/environment/flags are on file, both bound keys are cited, N-19
shows up in ``coverage_report()['unsupported']`` with a real reason, P-CA does
not, and the ratified canonical-12 / census-4 counts are untouched by adding
follow-ups. It also pins
the corrected ``ADJACENT_BOUND_KEYS`` ``vp_line`` values against a live re-read
of the VERIFICATION-PROFILE-002 source file, so future drift in that file fails
this test loudly instead of silently going stale (see the drift table in the
design doc §0.1).
"""

from __future__ import annotations

from pathlib import Path

from tools.broker_probes.registry import (
    _VP,
    ADJACENT_BOUND_KEYS,
    PROBES,
    coverage_report,
    get,
)

_NON_TRADE_KEYS = ("B_non_trade_event_detect", "B_non_trade_reconcile")


def _vp_key_line(key: str) -> int:
    """Return the 1-based line where ``key:`` starts in the live VP-002 source.

    Mirrors the convention the other :class:`BoundKey` entries use (verified by
    reading a couple of existing entries against the file): ``vp_line`` is the
    line of the ``<key>:`` mapping header itself, not a rationale/value line
    inside the block.
    """
    repo_root = Path(__file__).resolve().parents[2]
    vp_path = repo_root / _VP
    needle = f"{key}:"
    for lineno, line in enumerate(
        vp_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if line.strip() == needle:
            return lineno
    raise AssertionError(f"{key!r} not found in {vp_path}")


class TestAdjacentBoundKeysDriftCorrection:
    """§8.1 — the two non_trade ``vp_line`` values must track the live VP-002 file."""

    def test_non_trade_event_detect_vp_line_matches_live_source(self) -> None:
        assert ADJACENT_BOUND_KEYS["B_non_trade_event_detect"].vp_line == _vp_key_line(
            "B_non_trade_event_detect"
        )

    def test_non_trade_reconcile_vp_line_matches_live_source(self) -> None:
        assert ADJACENT_BOUND_KEYS["B_non_trade_reconcile"].vp_line == _vp_key_line(
            "B_non_trade_reconcile"
        )

    def test_other_adjacent_bound_keys_untouched(self) -> None:
        # Scope discipline: this registration touches only the two non_trade
        # keys' note/vp_line. The other two ADJACENT_BOUND_KEYS entries are a
        # separate, already-known drift class (design doc §9 M-1) out of scope
        # here — just confirm they still exist and still carry a note.
        assert ADJACENT_BOUND_KEYS["B_protection_gap"].note
        assert ADJACENT_BOUND_KEYS["B_post_trade_effect_to_obligation_commit"].note


class TestN19Registration:
    def test_present(self) -> None:
        spec = get("N-19")
        assert spec.probe_id == "N-19"

    def test_kind_and_environment(self) -> None:
        spec = get("N-19")
        assert spec.kind == "SPEC_CROSSCHECK"
        assert spec.environment == "NONE"

    def test_bounds_keys(self) -> None:
        spec = get("N-19")
        assert spec.bounds_keys == _NON_TRADE_KEYS

    def test_flags(self) -> None:
        spec = get("N-19")
        assert spec.emits_orders is False
        assert spec.requires_confirm is False
        assert spec.supported is False

    def test_skip_reason_present(self) -> None:
        spec = get("N-19")
        assert spec.skip_reason.strip() != ""

    def test_no_entrypoint_yet(self) -> None:
        spec = get("N-19")
        assert spec.entrypoint == ""

    def test_source_does_not_start_with_draft_or_plan(self) -> None:
        spec = get("N-19")
        assert not spec.source.startswith("draft")
        assert not spec.source.startswith("plan")


class TestPCARegistration:
    def test_present(self) -> None:
        spec = get("P-CA")
        assert spec.probe_id == "P-CA"

    def test_kind_and_environment(self) -> None:
        spec = get("P-CA")
        assert spec.kind == "MANUAL"
        assert spec.environment == "MOCK_VTS"

    def test_bounds_keys(self) -> None:
        spec = get("P-CA")
        assert spec.bounds_keys == _NON_TRADE_KEYS

    def test_flags(self) -> None:
        spec = get("P-CA")
        assert spec.emits_orders is False
        assert spec.requires_confirm is True
        assert spec.supported is True

    def test_skip_reason_is_now_empty(self) -> None:
        # P-CA landed as a runnable probe — skip_reason is cleared, not stale.
        spec = get("P-CA")
        assert spec.skip_reason == ""

    def test_prerequisites_present(self) -> None:
        spec = get("P-CA")
        assert len(spec.prerequisites) > 0

    def test_entrypoint_is_the_landed_probe(self) -> None:
        spec = get("P-CA")
        assert spec.entrypoint == "tools.broker_probes.probes_ca:probe_pca"

    def test_source_does_not_start_with_draft_or_plan(self) -> None:
        spec = get("P-CA")
        assert not spec.source.startswith("draft")
        assert not spec.source.startswith("plan")


class TestCoverageInvariantsUnchanged:
    """§5/§8 pin: adding N-19/P-CA must not move the ratified counts."""

    def test_canonical_count_still_12(self) -> None:
        report = coverage_report()
        assert report["canonical_count"] == 12

    def test_census_count_still_4(self) -> None:
        report = coverage_report()
        assert report["census_count"] == 4

    def test_total_is_23(self) -> None:
        """A deliberate literal: the register grows only by an explicit edit.

        The number is NOT derived (``canonical + census + followups`` is
        tautological — every probe lands in exactly one bucket, so such an
        assertion would block nothing). It is a hand-maintained count, so adding
        a probe has to come here and say which one. What the 23 is made of:

        * 12 canonical (draft §5) + 4 census (P0-2 plan §1 T2) — pinned above,
          and those two MUST NOT move;
        * 7 follow-ups, outside the ratified sets: P-NMPR, P-BAL, P-R5-PRE,
          P-R5, N-19, P-CA, and P-VL (2026-10-08, CP-3 decision 9 corroboration
          probe — ``docs/plans/2026-10-08-tos-cp3-venue-limit-source-and-probe-design.md``
          §4).
        """
        report = coverage_report()
        assert report["total"] == 23
        followups = sorted(
            spec.probe_id
            for spec in PROBES.values()
            if not spec.source.startswith(("draft", "plan"))
        )
        assert followups == [
            "N-19",
            "P-BAL",
            "P-CA",
            "P-NMPR",
            "P-R5",
            "P-R5-PRE",
            "P-VL",
        ]

    def test_n19_still_unsupported_pca_no_longer_is(self) -> None:
        # N-19 is a documentary cross-check, not a script — it stays unsupported.
        # P-CA landed as a runnable probe and must not appear here any more.
        unsupported = coverage_report()["unsupported"]
        assert "N-19" in unsupported and unsupported["N-19"].strip() != ""
        assert "P-CA" not in unsupported

    def test_non_trade_bound_keys_touched(self) -> None:
        # B_non_trade_event_detect / _reconcile live in ADJACENT_BOUND_KEYS, not
        # BOUND_KEYS, so they were never part of bound_keys_not_touched — but
        # they should now be reachable via PROBES for anyone iterating bounds_keys.
        touched = {
            key
            for spec in PROBES.values()
            for key in spec.bounds_keys
            if key in _NON_TRADE_KEYS
        }
        assert touched == set(_NON_TRADE_KEYS)


# ---------------------------------------------------------------------------
# runbook §3 table <-> registry agreement
#
# The runbook calls itself a view of this register ("the single source for the
# runbook table", registry.py:1), but nothing checked that. P-VL shipped with
# 주문 발생 = 예 against emits_orders=False, contradicting its own
# "QUERY (GET 전용)" cell and the note two lines below that reads the 예 set as
# "모의투자 전용 order probes" — four reviewers found it independently, which is
# what an unparsed table costs. The failing input for the test below is exactly
# that row.
# ---------------------------------------------------------------------------

_RUNBOOK = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "runbooks"
    / "kis-capability-probes.md"
)

#: The 주문 발생 column's vocabulary. ``n/a`` is not in use today; a cell that is
#: none of these fails loudly rather than being read as "no".
_ORDER_CELL_TRUTH = {"예": True, "아니오": False}


def _runbook_order_column() -> dict[str, bool]:
    """``{probe_id: emits_orders}`` as the runbook §3 table states it.

    Deliberately strict: a row whose ID is bold-wrapped, or whose 주문 발생 cell
    carries emphasis or a parenthetical ("**예 (실전)**" for P-R5), is normalised
    rather than skipped. Skipping is how a table drifts — the row stops being
    checked and nobody notices.
    """
    rows: dict[str, bool] = {}
    for line in _RUNBOOK.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 8:
            continue
        probe_id = cells[0].replace("*", "").strip()
        if probe_id not in PROBES:
            continue
        raw = cells[7].replace("*", "").strip()
        token = raw.split("(")[0].strip()
        assert token in _ORDER_CELL_TRUTH, (
            f"runbook §3 row {probe_id!r} has an unreadable 주문 발생 cell "
            f"{raw!r}; expected one of {sorted(_ORDER_CELL_TRUTH)}"
        )
        rows[probe_id] = _ORDER_CELL_TRUTH[token]
    return rows


def test_runbook_order_column_matches_the_register_for_every_row() -> None:
    """Every §3 row's 주문 발생 cell equals ``PROBES[id].emits_orders``."""
    stated = _runbook_order_column()

    assert stated, "parsed no §3 rows — the table shape changed, fix the parser"
    mismatched = {
        probe_id: (cell, PROBES[probe_id].emits_orders)
        for probe_id, cell in stated.items()
        if cell is not PROBES[probe_id].emits_orders
    }
    assert not mismatched, (
        "runbook §3 disagrees with registry.py (runbook, registry): " f"{mismatched}"
    )


def test_the_runbook_table_lists_every_registered_probe() -> None:
    """A probe missing from the table would pass the check above vacuously."""
    stated = _runbook_order_column()

    assert set(stated) == set(PROBES), (
        f"in the register but not in runbook §3: {sorted(set(PROBES) - set(stated))}; "
        f"in the table but not registered: {sorted(set(stated) - set(PROBES))}"
    )


def test_pvl_is_the_row_this_check_was_written_for() -> None:
    """P-VL specifically: GET-only, so the cell must read 아니오."""
    assert _runbook_order_column()["P-VL"] is False
    assert PROBES["P-VL"].emits_orders is False
