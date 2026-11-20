"""Unit tests for the N-19 / P-CA non_trade probe registrations."""

from __future__ import annotations

from pathlib import Path

from tools.broker_probes.registry import (
    ADJACENT_BOUND_KEYS,
    PROBES,
    coverage_report,
    get,
)

_NON_TRADE_KEYS = ("B_non_trade_event_detect", "B_non_trade_reconcile")


class TestAdjacentBoundKeys:
    """§8.1 — the adjacent bound-key entries stay on file with their notes."""

    def test_other_adjacent_bound_keys_untouched(self) -> None:
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

    def test_total_is_24(self) -> None:
        """A deliberate literal: the register grows only by an explicit edit."""
        report = coverage_report()
        assert report["total"] == 24
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
            "P-SC",
            "P-VL",
        ]

    def test_n19_still_unsupported_pca_no_longer_is(self) -> None:
        unsupported = coverage_report()["unsupported"]
        assert "N-19" in unsupported and unsupported["N-19"].strip() != ""
        assert "P-CA" not in unsupported

    def test_non_trade_bound_keys_touched(self) -> None:
        touched = {
            key
            for spec in PROBES.values()
            for key in spec.bounds_keys
            if key in _NON_TRADE_KEYS
        }
        assert touched == set(_NON_TRADE_KEYS)


_RUNBOOK = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "runbooks"
    / "kis-capability-probes.md"
)

_ORDER_CELL_TRUTH = {"예": True, "아니오": False}


def _runbook_order_column() -> dict[str, bool]:
    """``{probe_id: emits_orders}`` as the runbook §3 table states it."""
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
