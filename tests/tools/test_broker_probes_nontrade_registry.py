"""Unit tests for the N-19 / P-CA non_trade probe registrations.

``docs/plans/2026-08-07-tos-p02-nontrade-probe-definition.md`` §5/§8 defines two
probes for the two adjacent ``VERIFICATION-PROFILE-002`` bound keys
``B_non_trade_event_detect`` / ``B_non_trade_reconcile``:

* **N-19** — a documentary spec cross-check (no broker contact, ``ENV_NONE``).
* **P-CA** — an opportunistic GET-only observation, gated on N-19 landing
  first, that can never place an order.

Neither probe is executable yet (``supported=False`` — see each ``skip_reason``),
so this test guards the *registration*, not behavior: the right kind/environment/
flags are on file, both bound keys are cited, both probes show up in
``coverage_report()['unsupported']`` with a real reason, and the ratified
canonical-12 / census-4 counts are untouched by adding follow-ups. It also pins
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
        assert spec.supported is False

    def test_skip_reason_present(self) -> None:
        spec = get("P-CA")
        assert spec.skip_reason.strip() != ""

    def test_prerequisites_present(self) -> None:
        spec = get("P-CA")
        assert len(spec.prerequisites) > 0

    def test_no_entrypoint_yet(self) -> None:
        spec = get("P-CA")
        assert spec.entrypoint == ""

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

    def test_total_is_22(self) -> None:
        report = coverage_report()
        assert report["total"] == 22

    def test_both_new_probes_in_unsupported_with_reason(self) -> None:
        unsupported = coverage_report()["unsupported"]
        assert "N-19" in unsupported and unsupported["N-19"].strip() != ""
        assert "P-CA" in unsupported and unsupported["P-CA"].strip() != ""

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
