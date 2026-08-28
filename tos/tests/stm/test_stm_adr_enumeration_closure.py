"""§7.2 (c) ADR-enumeration-closure property — every ADR enumeration is closed over a model, both ways.

design #30 v1.1 **M6**, the third and newest regression: (a) field-closure checks the package against
its own tables and (b) anchor-resolution checks the citations against the ADR — but neither checks
whether an **ADR prose enumeration** is represented in the model 1:1. That is the blind axis this file
closes, and it is the axis the contract's own v1.0 got wrong: it counted §1 line 25 as **thirteen**
verbs and omitted ``satisfy preventive control`` from the all-false authority block entirely.

For each enumeration the ADR is **re-parsed here** — never trusted from the transcription — and three
things are asserted:

* the **cardinality** matches (過 0 · 不 0);
* each ADR item, **in order**, carries the keyword of the model field / enum member at the same index —
  so a reordering or a substitution fails;
* the model carries **no extra** member the ADR does not name.

Regime tag: predicate substrate only; closes **no** STM-EV; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import tos.stm as s

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ADR = (
    _REPO_ROOT
    / "tos-spec"
    / "src"
    / "part-1-foundation"
    / "ADR-002-028-Safety-Telemetry-Integrity-Continuous-Conformance-Monitoring-and-Alert-Escalation-Governance.md"
)


def _lines() -> list[str]:
    """The ADR as 1-indexed lines (index 0 is a sentinel)."""
    return [""] + _ADR.read_text(encoding="utf-8").splitlines()


def _segment(line_number: int, start_after: str, stop_before: str) -> str:
    """The substring of an ADR line between two verbatim markers (both must be present)."""
    text = _lines()[line_number]
    assert start_after in text, f"ADR line {line_number} lacks {start_after!r}"
    assert stop_before in text, f"ADR line {line_number} lacks {stop_before!r}"
    head = text.split(start_after, 1)[1]
    return head.split(stop_before, 1)[0]


def _comma_items(segment: str) -> list[str]:
    """Split an ADR inline enumeration on commas, dropping a leading "or "/"and " on the last item."""
    items = [part.strip() for part in segment.split(",")]
    cleaned = []
    for item in items:
        for lead in ("or ", "and "):
            if item.startswith(lead):
                item = item[len(lead) :]
        cleaned.append(item.strip().strip("."))
    return [item for item in cleaned if item]


def _numbered_items(start: int, end: int) -> list[str]:
    """Every ``N. ...`` numbered list item in an inclusive ADR line range."""
    lines = _lines()
    return [
        lines[n].strip()
        for n in range(start, end + 1)
        if re.match(r"^\d+\.\s", lines[n].strip())
    ]


def _bullet_items(start: int, end: int) -> list[str]:
    """Every ``- ...`` bullet item in an inclusive ADR line range."""
    lines = _lines()
    return [
        lines[n].strip()[2:]
        for n in range(start, end + 1)
        if lines[n].strip().startswith("- ")
    ]


def _table_rows(start: int, end: int) -> list[str]:
    """Every markdown table data row in an inclusive ADR line range."""
    lines = _lines()
    return [
        lines[n].strip()
        for n in range(start, end + 1)
        if lines[n].strip().startswith("|") and not set(lines[n]) <= set("|- ")
    ]


def _assert_ordered_keywords(
    items: list[str], keywords: tuple[str, ...], anchor: str
) -> None:
    """Assert the ADR items and the model keywords line up 1:1, in order (過 0 · 不 0)."""
    assert len(items) == len(keywords), (
        f"{anchor}: ADR names {len(items)} items but the model carries {len(keywords)} "
        f"(過/不 mismatch)\n  ADR: {items}\n  model: {list(keywords)}"
    )
    for index, (item, keyword) in enumerate(zip(items, keywords)):
        assert keyword.lower() in item.lower(), (
            f"{anchor} item {index}: ADR says {item!r} but the model slot is {keyword!r} — "
            "a reordering or a substitution"
        )


# --- §1 line 25 + STM-INV-001 + §7 line 236 -> AllFalseMonitoringAuthority ---


def test_the_all_false_authority_block_closes_over_the_adr_verbs() -> None:
    """(appendix K, **M6**) §1 line 25's twelve verbs + capacity + protective = fourteen fields.

    The contract's own v1.0 counted thirteen and dropped ``satisfy preventive control``; this property
    re-parses the ADR sentence so that error class cannot recur.
    """
    segment = _segment(25, "It does not ", " or re-arm.")
    verbs = _comma_items(segment) + ["re-arm"]
    assert (
        len(verbs) == 12
    ), f"§1 line 25 names {len(verbs)} verbs, expected 12: {verbs}"
    _assert_ordered_keywords(
        verbs,
        (
            "approve an action",
            "create headroom",
            "mark an RFC requirement",
            "satisfy preventive control",
            "establish broker finality",
            "activate configuration",
            "issue authority",
            "permit transmission",
            "close an incident",
            "establish recovery readiness",
            "restore scope",
            "re-arm",
        ),
        "§1 line 25",
    )
    fields = tuple(s.AllFalseMonitoringAuthority.model_fields)
    assert (
        len(fields) == 12 + 2
    ), "the block must be the twelve verbs plus capacity and protective"
    assert fields[0] == "creates_capacity"  # STM-INV-001 line 159
    assert fields[-1] == "classifies_protective"  # §7 line 236
    assert fields[1:-1] == (
        "approves_action",
        "creates_headroom",
        "marks_requirement_pass",
        "satisfies_preventive_control",
        "establishes_broker_finality",
        "activates_configuration",
        "issues_authority",
        "permits_transmission",
        "closes_incident",
        "establishes_recovery_readiness",
        "restores_scope",
        "re_arms",
    )
    assert len(s.ALL_FALSE_AUTHORITY_VERBS) == len(fields)


def test_the_two_non_line_25_flags_have_their_own_anchors() -> None:
    """(appendix K) ``creates_capacity`` is STM-INV-001 line 159; ``classifies_protective`` is §7:236."""
    assert "capacity" in _lines()[159]
    assert "alert severity is not protective classification" in _lines()[236]


# --- §5.11 line 151 -> MonitoringSuppression.DISABLE_FIELDS ----------------


def test_the_suppression_prohibitions_close_over_the_adr() -> None:
    """(**M6**) §5.11 line 151's six prohibitions map 1:1 onto the six ``disables_*`` fields."""
    segment = _segment(151, "SHALL NOT disable ", " for a Critical condition")
    items = _comma_items(segment)
    _assert_ordered_keywords(
        items,
        (
            "source collection",
            "invariant evaluation",
            "restrictive signaling",
            "evidence",
            "generation advancement",
            "final-egress denial",
        ),
        "§5.11 line 151",
    )
    assert len(items) == 6
    assert s.MonitoringSuppression.DISABLE_FIELDS == (
        "disables_collection",
        "disables_evaluation",
        "disables_restrictive_signaling",
        "disables_evidence",
        "disables_generation_advancement",
        "disables_final_egress_denial",
    )
    assert len(s.MONITORING_SUPPRESSION_PROHIBITIONS) == 6


# --- §17 line 402 -> RestrictiveMonitoringSignal.PROHIBITION_FIELDS --------


def test_the_restrictive_signal_prohibitions_close_over_the_adr() -> None:
    """(**M6**) §17 line 402's four prohibitions map 1:1 onto the four negative-polarity fields."""
    segment = _segment(402, "No monitor or alert may ", ". Conflicting")
    items = _comma_items(segment)
    _assert_ordered_keywords(
        items,
        (
            "downgrade an existing fence",
            "select a narrower scope",
            "clear a local latch",
            "publish",
        ),
        "§17 line 402",
    )
    assert len(items) == 4
    assert s.RestrictiveMonitoringSignal.PROHIBITION_FIELDS == (
        "downgrades_existing_fence",
        "selects_narrower_scope",
        "clears_local_latch",
        "publishes_no_incident",
    )
    assert len(s.RESTRICTIVE_SIGNAL_PROHIBITIONS) == 4


# --- §13 line 347 -> CoverageDimension -------------------------------------


def test_the_coverage_dimensions_close_over_the_adr() -> None:
    """(appendix L, **M2**) §13 line 347's eleven axes map 1:1 onto ``CoverageDimension``."""
    segment = _segment(347, "expands across shared ", " until isolation")
    items = _comma_items(segment)
    _assert_ordered_keywords(
        items,
        (
            "accounts",
            "Capacity Domains",
            "Safety Cells",
            "broker sessions",
            "credentials",
            "routes",
            "datastores",
            "clocks",
            "deployments",
            "policies",
            "failure domains",
        ),
        "§13 line 347",
    )
    assert len(items) == 11
    assert [member.value for member in s.CoverageDimension] == [
        "ACCOUNT",
        "CAPACITY_DOMAIN",
        "SAFETY_CELL",
        "BROKER_SESSION",
        "CREDENTIAL",
        "ROUTE",
        "DATASTORE",
        "CLOCK",
        "DEPLOYMENT",
        "POLICY",
        "FAILURE_DOMAIN",
    ]


# --- §11 line 316 -> NumericInputState -------------------------------------


def test_the_numeric_input_states_close_over_the_adr() -> None:
    """(appendix B) §11 line 316's eleven malformed states + ``WELL_FORMED`` = twelve."""
    segment = _segment(316, "Unknown ", " yields `UNKNOWN`")
    segment = "Unknown " + segment
    items = _comma_items(segment)
    _assert_ordered_keywords(
        items,
        (
            "Unknown numeric input",
            "NaN",
            "infinity",
            "overflow",
            "underflow",
            "non-convergence",
            "unit mismatch",
            "parser differential",
            "missing sample",
            "insufficient history",
            "evaluator disagreement",
        ),
        "§11 line 316",
    )
    assert len(items) == 11
    assert len(s.MALFORMED_NUMERIC_STATES) == 11
    assert len(s.NumericInputState) == 12
    assert s.NumericInputState.WELL_FORMED not in s.MALFORMED_NUMERIC_STATES


# --- §11 line 314 + STM-INV-007 line 183 -> BoundSemanticKind WEAK ---------


def test_the_weak_bound_forms_close_over_both_adr_anchors() -> None:
    """(appendix C, **M3**) §11 line 314's three weak forms ∪ INV-007 line 183's five = six."""
    from_314 = _comma_items(
        _segment(314, "cannot be implemented as a ", ", or window that permits")
    )
    assert from_314 == ["percentile", "average", "best-effort target"], from_314
    from_183 = _comma_items(_segment(183, "cannot be replaced by a ", "."))
    assert from_183 == [
        "percentile",
        "average",
        "local threshold",
        "hidden grace period",
        "favorable sampling rule",
    ], from_183
    union = {
        item.replace(" ", "_").replace("-", "_").upper() for item in from_314 + from_183
    }
    assert union == {member.value for member in s.WEAK_BOUND_KINDS}
    assert len(s.WEAK_BOUND_KINDS) == 6


def test_the_hard_and_neutral_partitions_are_stm_authored_and_disjoint() -> None:
    """(appendix C) The four hard and two neutral kinds complete the twelve-member partition."""
    assert len(s.HARD_BOUND_KINDS) == 4
    assert len(s.NEUTRAL_BOUND_KINDS) == 2
    assert (
        frozenset(s.BoundSemanticKind)
        == s.HARD_BOUND_KINDS | s.NEUTRAL_BOUND_KINDS | s.WEAK_BOUND_KINDS
    )
    assert len(s.BoundSemanticKind) == 12


# --- §12 line 335 -> AggregateConformanceResult ---------------------------


def test_the_aggregate_results_close_over_the_adr() -> None:
    """(appendix A) §12 line 335 names exactly four allowed aggregate results."""
    segment = _segment(335, "Allowed aggregate results are ", ".")
    tokens = re.findall(r"`([A-Z_]+)`", segment)
    assert tokens == ["CONFORMING", "RESTRICTED", "NON_CONFORMING", "UNKNOWN"]
    assert [member.value for member in s.AggregateConformanceResult] == tokens


# --- §23 line 499 -> DashboardStatusToken ---------------------------------


def test_the_dashboard_status_tokens_close_over_the_adr() -> None:
    """(appendix D) §23 line 499 names exactly seven dashboard statuses."""
    segment = _segment(499, "SHALL distinguish at minimum ", ". Rendering failures")
    tokens = re.findall(r"`([A-Z_]+)`", segment)
    assert tokens == [
        "CURRENT_CONFORMING",
        "RESTRICTED",
        "NON_CONFORMING",
        "UNKNOWN",
        "STALE",
        "GAP",
        "UNVERIFIED",
    ]
    assert [member.value for member in s.DashboardStatusToken] == tokens


# --- §5.7 line 135 -> MonitoringGapKind -----------------------------------


def test_the_monitoring_gap_kinds_close_over_the_adr() -> None:
    """(appendix E) §5.7 line 135 names exactly ten gap kinds."""
    segment = _segment(135, "An immutable record of ", " monitoring coverage")
    items = _comma_items(segment)
    _assert_ordered_keywords(
        items,
        (
            "missing",
            "stale",
            "conflicting",
            "ambiguous",
            "discontinuous",
            "incomplete",
            "unverified",
            "common-mode",
            "failed",
            "suppressed",
        ),
        "§5.7 line 135",
    )
    assert len(items) == 10
    assert [member.value for member in s.MonitoringGapKind] == [
        "MISSING",
        "STALE",
        "CONFLICTING",
        "AMBIGUOUS",
        "DISCONTINUOUS",
        "INCOMPLETE",
        "UNVERIFIED",
        "COMMON_MODE",
        "FAILED",
        "SUPPRESSED",
    ]


# --- §9 line 275-286 -> COVERAGE_CLOSURE_ITEMS ----------------------------


def test_the_coverage_closure_items_close_over_the_adr() -> None:
    """(appendix F) §9 line 275-286 is a twelve-item numbered closure."""
    items = _numbered_items(275, 286)
    _assert_ordered_keywords(
        items,
        (
            "exact requirement",
            "scope and dependency closure",
            "preventive or restrictive owner",
            "telemetry and source continuity",
            "deterministic evaluator",
            "detection trigger",
            "restrictive action",
            "alert delivery",
            "evidence and independent-review",
            "failure-domain",
            "currentness dependency",
            "approved exclusions with proof",
        ),
        "§9 line 275-286",
    )
    assert len(items) == 12 == s.COVERAGE_CLOSURE_ITEM_COUNT
    assert len(s.COVERAGE_CLOSURE_ITEMS) == 12


# --- §15 line 369-376 -> SUPPRESSION_PRESERVED_FUNCTIONS ------------------


def test_the_preserved_suppression_functions_close_over_the_adr() -> None:
    """(appendix H) §15 line 369-376 is an eight-item preserved-active bullet list."""
    items = _bullet_items(369, 376)
    _assert_ordered_keywords(
        items,
        (
            "telemetry collection and continuity",
            "monitor evaluation and violation state",
            "Monitoring Gap creation",
            "restrictive signaling and local deny latching",
            "incident-signal handoff",
            "evidence capture and audit",
            "escalation on suppression failure",
            "final-egress currentness and denial",
        ),
        "§15 line 369-376",
    )
    assert len(items) == 8 == len(s.SUPPRESSION_PRESERVED_FUNCTIONS)


# --- §18 line 410-417 -> FINAL_EGRESS_CURRENTNESS_FACTS -------------------


def test_the_final_egress_currentness_facts_close_over_the_adr() -> None:
    """(appendix G) §18 line 410-417 is an eight-item numbered currentness vector."""
    items = _numbered_items(410, 417)
    _assert_ordered_keywords(
        items,
        (
            "Safety Monitoring Policy identity",
            "Critical Telemetry and Monitor Coverage Manifest digests",
            "Monitor Generation and fenced owner epoch",
            "action-scope coverage completeness",
            "conformance result",
            "suppression state",
            "restrictive signal",
            "Snapshot age",
        ),
        "§18 line 410-417",
    )
    assert len(items) == 8 == len(s.FINAL_EGRESS_CURRENTNESS_FACTS)


# --- §21 line 451-462 -> PARTITION_FAILURE_MODES --------------------------


def test_the_partition_failure_matrix_closes_over_the_adr() -> None:
    """(appendix I) §21 line 451-462 is a twelve-row partition / failure matrix."""
    rows = _table_rows(451, 462)
    _assert_ordered_keywords(
        rows,
        (
            "telemetry source or continuity lost",
            "collector, parser, evaluator, or registry unavailable",
            "monitor owner or generation conflict",
            "monitoring plane partitioned",
            "queue overflow or backpressure",
            "alert delivery or escalation unproven",
            "common-mode independence claim fails",
            "suppression state missing, stale, or expired",
            "time confidence or receipt-age proof lost",
            "evidence path unavailable",
            "dashboard or paging system compromised",
            "recovery or backlog drain completes",
        ),
        "§21 line 451-462",
    )
    assert len(rows) == 12 == len(s.PARTITION_FAILURE_MODES)


# --- §8 line 253-265 -> CRITICAL_TELEMETRY_BINDING_GROUPS -----------------


def test_the_critical_telemetry_binding_groups_close_over_the_adr() -> None:
    """(appendix J) §8 line 253-265 is a twelve-bullet binding list (line 255 is blank)."""
    items = _bullet_items(253, 265)
    _assert_ordered_keywords(
        items,
        (
            "ADR-002-029",
            "ADR-002-030",
            "canonical telemetry and semantic identity",
            "owner and publisher identity and epoch",
            "exact environments",
            "value type, units, scale",
            "source identities, continuity",
            "trustworthy-time basis",
            "expected cadence",
            "approved derivation",
            "dependency closure, consumers",
            "failure domains, common modes",
        ),
        "§8 line 253-265",
    )
    assert len(items) == 12 == len(s.CRITICAL_TELEMETRY_BINDING_GROUPS)


# --- §14 line 355 -> SHARED_DEPENDENCY_ANCHOR -----------------------------


def test_the_shared_dependency_anchor_closes_over_the_adr() -> None:
    """(appendix M, OQ2) §14 line 355 names exactly seventeen shared dependencies."""
    segment = _segment(355, "Shared ", " is a disclosed common mode")
    items = _comma_items(segment)
    _assert_ordered_keywords(
        items,
        (
            "source",
            "collector",
            "exporter",
            "parser",
            "schema registry",
            "library",
            "time source",
            "message bus",
            "datastore",
            "network",
            "region",
            "credential",
            "administrator",
            "CI pipeline",
            "deployment",
            "notification provider",
            "policy owner",
        ),
        "§14 line 355",
    )
    assert len(items) == 17 == len(s.SHARED_DEPENDENCY_ANCHOR)


def test_the_shared_dependency_field_stays_open_on_purpose() -> None:
    """(OQ2) §14 line 357 keeps residual common mode open-ended, so the field is not a closed enum."""
    assert "remaining common mode is recorded as residual risk" in _lines()[357]
    field = s.CommonModeDisclosure.model_fields["shared_dependencies"]
    assert field.annotation == frozenset[str]


# --- the enumerations with no ADR list ------------------------------------


def test_telemetry_criticality_is_anchored_on_a_sentence_not_a_list() -> None:
    """(§8 line 249) The three-token criticality axis has a sentence anchor, honestly recorded."""
    assert "Unknown materiality is Critical" in _lines()[249]
    assert len(s.TelemetryCriticality) == 3
    assert s.TelemetryCriticality.UNKNOWN_MATERIALITY.value == "UNKNOWN_MATERIALITY"


def test_suppression_lifecycle_is_anchored_on_two_sentences() -> None:
    """(§15 line 365 + §21 line 458) The four-state lifecycle has sentence anchors, honestly recorded."""
    assert "automatically restrictive on expiry or uncertainty" in _lines()[365]
    assert "treat monitoring state as restricted and unsuppressed" in _lines()[458]
    assert len(s.SuppressionLifecycleState) == 4
    assert (
        frozenset(
            {s.SuppressionLifecycleState.EXPIRED, s.SuppressionLifecycleState.UNKNOWN}
        )
        == s.RESTRICTIVE_SUPPRESSION_STATES
    )


# --- the parsers themselves ------------------------------------------------


@pytest.mark.parametrize(
    "segment,expected",
    [
        ("a, b, or c", ["a", "b", "c"]),
        ("a, b, and c", ["a", "b", "c"]),
        ("single", ["single"]),
    ],
)
def test_the_inline_parser_behaves(segment: str, expected: list[str]) -> None:
    """(canary) The comma parser drops the trailing conjunction and nothing else."""
    assert _comma_items(segment) == expected


def test_the_ordered_keyword_check_really_fires() -> None:
    """(canary) A substitution and a count mismatch both fail — green is evidence, not a no-op."""
    with pytest.raises(AssertionError):
        _assert_ordered_keywords(["alpha", "beta"], ("alpha",), "canary")
    with pytest.raises(AssertionError):
        _assert_ordered_keywords(["alpha", "beta"], ("alpha", "gamma"), "canary")
    _assert_ordered_keywords(["alpha one", "beta two"], ("alpha", "beta"), "canary")
