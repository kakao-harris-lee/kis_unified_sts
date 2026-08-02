#!/usr/bin/env python3
"""Validate and render the TOS corpus's independent current-status axes.

Canonical inputs live under ``tos-spec/src``:

* RFC/GOV and ADR ``Status`` headers own document disposition;
* the two CSV evidence registers own evidence execution state;
* ``AUTHORITY-STATUS.csv`` owns restricted-live and production authorization.

The generated Markdown is a convenience view.  It deliberately does not infer
authority from document ratification, ADR disposition, tests, or evidence.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

EVIDENCE_STATES = (
    "NOT_IMPLEMENTED",
    "READY",
    "RUNNING",
    "PASS",
    "FAIL",
    "INCONCLUSIVE",
    "BLOCKED",
    "EXPIRED",
    "SUPERSEDED",
    "WAIVED_WITH_RESIDUAL_RISK",
)
DOCUMENT_STATES = frozenset({"RATIFIED", "PROPOSED", "DE-RATIFIED", "SUPERSEDED"})
ADR_STATES = frozenset({"PROPOSED", "ACCEPTED", "REJECTED", "SUPERSEDED"})
AUTHORITY_STATES = frozenset({"NOT_AUTHORIZED", "AUTHORIZED"})

PART1_CSV = Path(
    "tos-spec/src/part-1-foundation/verification/EVIDENCE-REGISTER-002.csv"
)
PART1_MD = Path("tos-spec/src/part-1-foundation/verification/EVIDENCE-REGISTER-002.md")
DEV_CSV = Path("tos-spec/src/part-3-development/verification/EVIDENCE-REGISTER-DEV.csv")
DEV_MD = Path("tos-spec/src/part-3-development/verification/EVIDENCE-REGISTER-DEV.md")
AUTHORITY_CSV = Path("tos-spec/src/AUTHORITY-STATUS.csv")
GENERATED_MD = Path("tos-spec/src/CURRENT-STATUS.md")
TRACEABILITY_MD = Path(
    "tos-spec/src/part-1-foundation/verification/TRACEABILITY-MATRIX-002.md"
)
P2_DISPOSITION_CSV = Path("tos-spec/src/part-2-decision/P2-DISPOSITION-REGISTER.csv")
P2_DISPOSITION_MD = Path("tos-spec/src/part-2-decision/P2-DISPOSITION-PACKAGE.md")
ECO_PROFILE_SCHEMA = Path(
    "tos-spec/src/part-2-decision/profiles/ECONOMIC-VIABILITY-PROFILE.schema.yaml"
)
IOM_PROFILE_SCHEMA = Path(
    "tos-spec/src/part-2-decision/profiles/INVESTMENT-OPERATING-PROFILE.schema.yaml"
)
MIGRATION_CSV = Path("tos-spec/src/MIGRATION-CONFORMANCE-REGISTER.csv")
MIGRATION_MD = Path("tos-spec/src/MIGRATION-CONFORMANCE-REGISTER.md")

REQUIRED_EVIDENCE_FIELDS = (
    "evidence_id",
    "domain",
    "title",
    "primary_adr",
    "criticality",
    "minimum_evidence_level",
    "status",
    "implementation_owner",
    "evidence_owner",
    "independent_reviewer",
    "verification_profile_version",
    "broker_capability_profile_version",
    "latest_run_id",
    "latest_result_date",
    "evidence_location",
    "notes",
)
REQUIRED_AUTHORITY_FIELDS = (
    "axis",
    "status",
    "governing_source",
    "change_authority",
    "notes",
)
REQUIRED_P2_FIELDS = (
    "question_id",
    "rfc",
    "source_section",
    "question_summary",
    "source_marking",
    "disposition",
    "canonical_resolution",
    "deferred_artifact",
    "accountable_owner",
    "rationale",
    "trigger",
    "scope_restriction",
    "decision_state",
)
REQUIRED_MIGRATION_FIELDS = (
    "record_id",
    "category",
    "component",
    "owning_contract",
    "current_level",
    "evidence_state",
    "trust_seam",
    "target_cutover",
    "rollback_double_trade",
    "queued_work_direct_egress",
    "operator_state_owner",
    "decommission_criteria",
    "authority_state",
)
_STATUS_HEADER = re.compile(
    r"^\s*(?:-\s*)?\*\*Status:?\*\*:?\s*(.+?)\s*$", re.MULTILINE
)
_DOCUMENT_NAME = re.compile(r"^(?:RFC-\d{3}|GOV-\d{3})-")
_ADR_NAME = re.compile(r"^ADR-(?:002|DEV)-\d{3}-")
_PART1_ADR_NAME = re.compile(r"^(ADR-002-\d{3})-")
_TRACEABILITY_HEADING = re.compile(
    r"^##\s+\d+(?:\.\d+)?\.?\s+(?:Requirements\s+)?Traceability\s*$",
    re.MULTILINE,
)
_SAFE_ID = re.compile(r"\bSAFE-\d{3}\b")
_DIRECT_REPAIR_ADRS = frozenset(
    {"ADR-002-002", "ADR-002-003", "ADR-002-004", "ADR-002-005", "ADR-002-006"}
)
_EXPECTED_ECO_IDS = frozenset(f"ECO-EV-{number:03}" for number in range(1, 13))
_EXPECTED_IOM_IDS = frozenset(f"IOM-EV-{number:03}" for number in range(1, 9))
_EXPECTED_RLP_IDS = frozenset(f"RLP-EV-{number:03}" for number in range(1, 13))
_EXPECTED_HUMAN_BOUNDS = frozenset(
    {
        "minimum_net_expectancy",
        "minimum_benchmark_relative_performance",
        "confidence_level",
        "minimum_effective_sample",
        "maximum_adjusted_error",
        "minimum_deployable_capacity",
        "maximum_turnover",
        "minimum_capital_efficiency",
        "maximum_drawdown_magnitude",
        "maximum_drawdown_duration",
        "maximum_existing_book_correlation",
        "minimum_decay_horizon",
        "maximum_estimation_error",
    }
)


class StatusError(ValueError):
    """The canonical corpus status inputs are inconsistent."""


@dataclass(frozen=True)
class EvidenceRegister:
    label: str
    rows: tuple[Mapping[str, str], ...]
    counts: Counter[str]


@dataclass(frozen=True)
class StatusSnapshot:
    documents: Counter[str]
    adrs: Counter[str]
    part1: EvidenceRegister
    development: EvidenceRegister
    authorities: Mapping[str, str]
    direct_traceability_count: int
    p2_carried_questions: int
    const003_result: str
    migration_rows: int


def _read_csv(path: Path, required_fields: Sequence[str]) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = tuple(reader.fieldnames or ())
            if fields != tuple(required_fields):
                raise StatusError(
                    f"{path}: header mismatch; expected {list(required_fields)!r}, "
                    f"got {list(fields)!r}"
                )
            return [
                {key: (value or "").strip() for key, value in row.items()}
                for row in reader
            ]
    except FileNotFoundError as exc:
        raise StatusError(f"missing canonical input: {path}") from exc


def load_evidence_register(path: Path, label: str) -> EvidenceRegister:
    rows = _read_csv(path, REQUIRED_EVIDENCE_FIELDS)
    seen: set[str] = set()
    errors: list[str] = []
    for line_no, row in enumerate(rows, start=2):
        evidence_id = row["evidence_id"]
        if not evidence_id:
            errors.append(f"line {line_no}: empty evidence_id")
        elif evidence_id in seen:
            errors.append(f"line {line_no}: duplicate evidence_id {evidence_id}")
        seen.add(evidence_id)

        status = row["status"]
        if status not in EVIDENCE_STATES:
            errors.append(f"line {line_no} {evidence_id}: invalid status {status!r}")

        always_required = (
            "domain",
            "title",
            "primary_adr",
            "criticality",
            "minimum_evidence_level",
            "implementation_owner",
            "evidence_owner",
            "independent_reviewer",
            "verification_profile_version",
            "broker_capability_profile_version",
        )
        for field in always_required:
            if not row[field]:
                errors.append(f"line {line_no} {evidence_id}: empty {field}")

        if status != "NOT_IMPLEMENTED":
            for field in (
                "implementation_owner",
                "evidence_owner",
                "independent_reviewer",
                "verification_profile_version",
                "evidence_location",
            ):
                if row[field].upper() in {"", "TBD", "UNKNOWN", "UNASSIGNED"}:
                    errors.append(
                        f"line {line_no} {evidence_id}: {status} requires assigned {field}"
                    )
        if status == "PASS":
            for field in ("latest_run_id", "latest_result_date", "evidence_location"):
                if not row[field]:
                    errors.append(
                        f"line {line_no} {evidence_id}: PASS requires {field}"
                    )

    if errors:
        raise StatusError(f"{path}:\n  " + "\n  ".join(errors))
    return EvidenceRegister(
        label=label, rows=tuple(rows), counts=Counter(r["status"] for r in rows)
    )


def _markdown_register_rows(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8-sig")
    marker = "## Register"
    if marker not in text:
        raise StatusError(f"{path}: missing {marker!r}")
    body = text.split(marker, 1)[1]
    parsed: list[dict[str, str]] = []
    for line in body.splitlines():
        if (
            not line.startswith("|")
            or line.startswith("|---")
            or line.startswith("| ID ")
        ):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 8:
            continue
        parsed.append(
            dict(
                zip(
                    (
                        "evidence_id",
                        "domain",
                        "title",
                        "primary_adr",
                        "minimum_evidence_level",
                        "status",
                        "implementation_owner",
                        "independent_reviewer",
                    ),
                    cells,
                    strict=True,
                )
            )
        )
    return parsed


def validate_markdown_mirror(markdown_path: Path, register: EvidenceRegister) -> None:
    parsed = _markdown_register_rows(markdown_path)
    fields = (
        "evidence_id",
        "domain",
        "title",
        "primary_adr",
        "minimum_evidence_level",
        "status",
        "implementation_owner",
        "independent_reviewer",
    )
    expected = {
        row["evidence_id"]: {field: row[field] for field in fields}
        for row in register.rows
    }
    actual = {row["evidence_id"]: row for row in parsed}
    if len(actual) != len(parsed):
        raise StatusError(
            f"{markdown_path}: duplicate evidence ID in Markdown register"
        )
    if actual != expected:
        mismatched_ids = sorted(
            evidence_id
            for evidence_id in set(actual) | set(expected)
            if actual.get(evidence_id) != expected.get(evidence_id)
        )
        raise StatusError(
            f"{markdown_path}: CSV/Markdown register mismatch for "
            f"{', '.join(mismatched_ids[:5])}; CSV rows={len(expected)}, "
            f"Markdown rows={len(parsed)}"
        )

    text = markdown_path.read_text(encoding="utf-8-sig")
    summary = {"TOTAL": len(register.rows), **register.counts}
    for state, count in summary.items():
        label = "Total evidence items" if state == "TOTAL" else state
        match = re.search(rf"^- {re.escape(label)}: \*\*(\d+)\*\*$", text, re.MULTILINE)
        if match is None:
            if count == 0 and state != "TOTAL":
                continue
            raise StatusError(f"{markdown_path}: missing summary count for {label}")
        if int(match.group(1)) != count:
            raise StatusError(
                f"{markdown_path}: summary {label}={match.group(1)}, CSV={count}"
            )


def _header_state(path: Path, allowed: frozenset[str]) -> str:
    text = path.read_text(encoding="utf-8-sig")
    match = _STATUS_HEADER.search(text)
    if not match:
        raise StatusError(f"{path}: missing canonical Status header")
    state = match.group(1).split(maxsplit=1)[0].upper().rstrip(".,;")
    if state not in allowed:
        raise StatusError(f"{path}: unsupported Status header state {state!r}")
    return state


def load_document_states(source_root: Path) -> tuple[Counter[str], Counter[str]]:
    documents: Counter[str] = Counter()
    adrs: Counter[str] = Counter()
    for path in sorted(source_root.rglob("*.md")):
        if _DOCUMENT_NAME.match(path.name):
            documents[_header_state(path, DOCUMENT_STATES)] += 1
        elif _ADR_NAME.match(path.name):
            adrs[_header_state(path, ADR_STATES)] += 1
    if not documents:
        raise StatusError(f"{source_root}: no RFC/GOV documents discovered")
    if not adrs:
        raise StatusError(f"{source_root}: no ADR documents discovered")
    return documents, adrs


def load_authorities(path: Path) -> dict[str, str]:
    rows = _read_csv(path, REQUIRED_AUTHORITY_FIELDS)
    required_axes = {"restricted_live", "production"}
    seen: dict[str, str] = {}
    for line_no, row in enumerate(rows, start=2):
        axis = row["axis"]
        if axis in seen:
            raise StatusError(f"{path}: line {line_no}: duplicate axis {axis}")
        if row["status"] not in AUTHORITY_STATES:
            raise StatusError(
                f"{path}: line {line_no}: invalid authority state {row['status']!r}"
            )
        for field in ("governing_source", "change_authority", "notes"):
            if not row[field]:
                raise StatusError(f"{path}: line {line_no}: empty {field}")
        seen[axis] = row["status"]
    if set(seen) != required_axes:
        raise StatusError(
            f"{path}: authority axes must be exactly {sorted(required_axes)!r}"
        )
    return seen


def _traceability_safe_ids(path: Path, defined_safes: set[str]) -> set[str]:
    text = path.read_text(encoding="utf-8-sig")
    match = _TRACEABILITY_HEADING.search(text)
    if match is None:
        raise StatusError(f"{path}: missing direct Traceability table")
    next_heading = re.search(r"^##\s+", text[match.end() :], re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(text)
    section = text[match.end() : end]
    safe_ids = set(_SAFE_ID.findall(section))
    if not safe_ids:
        raise StatusError(f"{path}: Traceability table contains no SAFE ID")
    unknown = safe_ids - defined_safes
    if unknown:
        raise StatusError(
            f"{path}: undefined SAFE IDs in Traceability table: {sorted(unknown)!r}"
        )
    return safe_ids


def validate_direct_traceability(
    source_root: Path, register: EvidenceRegister, matrix_path: Path
) -> int:
    safety_case = source_root / "part-1-foundation/RFC-001-Safety-Case.md"
    safety_text = safety_case.read_text(encoding="utf-8-sig")
    defined_safes = set(
        re.findall(r"^###\s+(SAFE-\d{3})\s+", safety_text, re.MULTILINE)
    )
    if not defined_safes:
        raise StatusError(f"{safety_case}: no defined SAFE requirements discovered")

    adr_paths: dict[str, Path] = {}
    for path in sorted((source_root / "part-1-foundation").glob("ADR-002-*.md")):
        match = _PART1_ADR_NAME.match(path.name)
        if match:
            adr_paths[match.group(1)] = path
    if len(adr_paths) != 30:
        raise StatusError(
            f"{source_root}: expected 30 ADR-002 source documents, found {len(adr_paths)}"
        )

    safe_sets = {
        adr: _traceability_safe_ids(path, defined_safes)
        for adr, path in adr_paths.items()
    }
    primary_families: dict[str, set[str]] = {}
    for row in register.rows:
        primary_adrs = set(row["primary_adr"].split("/"))
        family = row["evidence_id"].rsplit("-", 1)[0]
        for adr in primary_adrs:
            primary_families.setdefault(adr, set()).add(family)
    missing_evidence = sorted(set(adr_paths) - set(primary_families))
    if missing_evidence:
        raise StatusError(
            f"{register.label}: ADRs lack registered primary evidence: {missing_evidence!r}"
        )

    matrix = matrix_path.read_text(encoding="utf-8-sig")
    if "ADRs with a direct Traceability table: 30/30; source gaps: 0." not in matrix:
        raise StatusError(f"{matrix_path}: direct-table coverage summary is stale")
    for adr in sorted(_DIRECT_REPAIR_ADRS):
        exact_families = {
            row["evidence_id"].rsplit("-", 1)[0]
            for row in register.rows
            if row["primary_adr"] == adr
        }
        if len(exact_families) != 1:
            raise StatusError(
                f"{adr}: expected one exact primary evidence family, got {sorted(exact_families)!r}"
            )
        family = next(iter(exact_families))
        reverse_match = re.search(
            rf"^\| {re.escape(family)} \| ([^|]+) \|$", matrix, re.MULTILINE
        )
        if reverse_match is None:
            raise StatusError(f"{matrix_path}: missing reverse row for {family}")
        matrix_safes = set(_SAFE_ID.findall(reverse_match.group(1)))
        if matrix_safes != safe_sets[adr]:
            raise StatusError(
                f"{matrix_path}: {family} reverse SAFE set {sorted(matrix_safes)!r} "
                f"does not match {adr} direct set {sorted(safe_sets[adr])!r}"
            )
        suffix = adr.removeprefix("ADR-002-")
        for safe_id in safe_sets[adr]:
            forward_match = re.search(
                rf"^\| {re.escape(safe_id)} \|[^\n]+\| ([^|]+) \| ([^|]+) \| COVERED \|$",
                matrix,
                re.MULTILINE,
            )
            if forward_match is None:
                raise StatusError(f"{matrix_path}: missing forward row for {safe_id}")
            realizing_adrs = {
                item.strip() for item in forward_match.group(1).split(",")
            }
            families = {item.strip() for item in forward_match.group(2).split(",")}
            if (
                suffix not in realizing_adrs
                or family.removesuffix("-EV") not in families
            ):
                raise StatusError(
                    f"{matrix_path}: {safe_id} does not directly reach {adr}/{family}"
                )
    return len(adr_paths)


def validate_p2_dispositions(csv_path: Path, package_path: Path) -> int:
    rows = _read_csv(csv_path, REQUIRED_P2_FIELDS)
    expected_ids = {
        *(f"RFC-003-Q{number}" for number in range(1, 7)),
        *(f"RFC-004-Q{number}" for number in range(1, 7)),
        *(f"RFC-005-Q{number}" for number in range(1, 7)),
        *(f"RFC-006-Q{number}" for number in range(1, 8)),
        *(f"RFC-007-Q{number}" for number in range(1, 7)),
    }
    actual_ids = [row["question_id"] for row in rows]
    if len(set(actual_ids)) != len(actual_ids):
        raise StatusError(f"{csv_path}: duplicate question_id")
    if set(actual_ids) != expected_ids:
        raise StatusError(
            f"{csv_path}: question census mismatch; "
            f"missing={sorted(expected_ids - set(actual_ids))!r}, "
            f"extra={sorted(set(actual_ids) - expected_ids)!r}"
        )

    allowed = {
        "RESOLVED_IN_CANONICAL_TEXT",
        "EXPLICITLY_DEFERRED",
        "RETAINED_SCOPE_RESTRICTING_OPEN_DEBT",
    }
    errors: list[str] = []
    for line_no, row in enumerate(rows, start=2):
        question_id = row["question_id"]
        disposition = row["disposition"]
        if disposition not in allowed:
            errors.append(
                f"line {line_no} {question_id}: invalid disposition {disposition!r}"
            )
            continue
        for field in (
            "rfc",
            "source_section",
            "question_summary",
            "source_marking",
            "accountable_owner",
            "rationale",
            "trigger",
            "scope_restriction",
            "decision_state",
        ):
            if not row[field]:
                errors.append(f"line {line_no} {question_id}: empty {field}")
        if disposition == "RESOLVED_IN_CANONICAL_TEXT":
            if not row["canonical_resolution"]:
                errors.append(
                    f"line {line_no} {question_id}: missing canonical_resolution"
                )
            if row["deferred_artifact"]:
                errors.append(
                    f"line {line_no} {question_id}: resolved row has deferred_artifact"
                )
        else:
            if row["canonical_resolution"]:
                errors.append(
                    f"line {line_no} {question_id}: open row claims canonical_resolution"
                )
            if not row["deferred_artifact"] and disposition == "EXPLICITLY_DEFERRED":
                errors.append(
                    f"line {line_no} {question_id}: missing named deferred_artifact"
                )
            if row["decision_state"] != "DRAFT_PENDING_SYSTEM_OWNER":
                errors.append(
                    f"line {line_no} {question_id}: open disposition must remain "
                    "DRAFT_PENDING_SYSTEM_OWNER"
                )
    if errors:
        raise StatusError(f"{csv_path}:\n  " + "\n  ".join(errors))

    resolved = sum(row["disposition"] == "RESOLVED_IN_CANONICAL_TEXT" for row in rows)
    carried = len(rows) - resolved
    if resolved != 3 or carried != 28:
        raise StatusError(
            f"{csv_path}: expected 3 resolved and 28 carried, got {resolved}/{carried}"
        )
    package = package_path.read_text(encoding="utf-8-sig")
    if "P2 NOT ESTABLISHED BY THIS AUDIT" not in package:
        raise StatusError(
            f"{package_path}: missing explicit non-completion decision gate"
        )
    return carried


def evaluate_const003(
    rlp_states: Mapping[str, str],
    eco_states: Mapping[str, str],
    *,
    profile_approved: bool,
    independent_review_complete: bool,
) -> str:
    """Return the Proposed CONST-003 verdict without creating authority."""
    if set(rlp_states) != _EXPECTED_RLP_IDS or set(eco_states) != _EXPECTED_ECO_IDS:
        return "INCONCLUSIVE"
    all_states = [*rlp_states.values(), *eco_states.values()]
    if "FAIL" in all_states:
        return "FAIL"
    if (
        profile_approved
        and independent_review_complete
        and all(state == "PASS" for state in all_states)
    ):
        return "PASS"
    return "INCONCLUSIVE"


def _contains_key(value: object, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False


def validate_economic_viability(
    schema_path: Path,
    part1: EvidenceRegister,
    development: EvidenceRegister,
) -> str:
    try:
        schema = yaml.safe_load(schema_path.read_text(encoding="utf-8-sig"))
    except yaml.YAMLError as exc:
        raise StatusError(f"{schema_path}: invalid YAML: {exc}") from exc
    if not isinstance(schema, dict):
        raise StatusError(f"{schema_path}: schema root must be an object")
    if _contains_key(schema, "default"):
        raise StatusError(f"{schema_path}: numeric and policy defaults are prohibited")
    required = set(schema.get("required", []))
    for field in ("human_bounds", "approvals", "non_authority"):
        if field not in required:
            raise StatusError(f"{schema_path}: top-level {field} must be required")
    bounds = schema.get("properties", {}).get("human_bounds", {})
    if set(bounds.get("required", [])) != _EXPECTED_HUMAN_BOUNDS:
        raise StatusError(
            f"{schema_path}: human-owned bound set is incomplete or expanded"
        )
    status_values = schema.get("properties", {}).get("status", {}).get("enum", [])
    if "APPROVED" not in status_values or "PROPOSED" not in status_values:
        raise StatusError(f"{schema_path}: profile status must distinguish approval")

    eco_rows = {
        row["evidence_id"]: row
        for row in development.rows
        if row["evidence_id"].startswith("ECO-EV-")
    }
    if set(eco_rows) != _EXPECTED_ECO_IDS:
        raise StatusError(
            f"{development.label}: ECO family mismatch; "
            f"expected={sorted(_EXPECTED_ECO_IDS)!r}, got={sorted(eco_rows)!r}"
        )
    for evidence_id, row in eco_rows.items():
        if row["status"] != "NOT_IMPLEMENTED":
            raise StatusError(
                f"{development.label}: new {evidence_id} must start NOT_IMPLEMENTED"
            )
        for field in ("implementation_owner", "evidence_owner", "independent_reviewer"):
            if not row[field].startswith("TBD-"):
                raise StatusError(
                    f"{development.label}: {evidence_id} must expose pending {field}"
                )

    rlp_states = {
        row["evidence_id"]: row["status"]
        for row in part1.rows
        if row["evidence_id"].startswith("RLP-EV-")
    }
    if set(rlp_states) != _EXPECTED_RLP_IDS:
        raise StatusError(f"{part1.label}: RLP family must contain exactly 12 cases")
    hypothetical_rlp_pass = dict.fromkeys(_EXPECTED_RLP_IDS, "PASS")
    actual_eco_states = {
        evidence_id: row["status"] for evidence_id, row in eco_rows.items()
    }
    if (
        evaluate_const003(
            hypothetical_rlp_pass,
            actual_eco_states,
            profile_approved=False,
            independent_review_complete=False,
        )
        != "INCONCLUSIVE"
    ):
        raise StatusError("RLP-only CONST-003 negative proof failed")
    return evaluate_const003(
        rlp_states,
        actual_eco_states,
        profile_approved=False,
        independent_review_complete=False,
    )


def validate_investment_operating_model(
    schema_path: Path, development: EvidenceRegister
) -> None:
    """Validate the Proposed G-02..G-05 profile and honest initial family."""
    try:
        schema = yaml.safe_load(schema_path.read_text(encoding="utf-8-sig"))
    except yaml.YAMLError as exc:
        raise StatusError(f"{schema_path}: invalid YAML: {exc}") from exc
    if not isinstance(schema, dict):
        raise StatusError(f"{schema_path}: schema root must be an object")
    if _contains_key(schema, "default"):
        raise StatusError(f"{schema_path}: numeric and policy defaults are prohibited")
    required = set(schema.get("required", []))
    expected_sections = {
        "mandate",
        "allocation",
        "market_data_continuity",
        "concurrency",
        "latency",
        "approvals",
        "non_authority",
    }
    if not expected_sections <= required:
        raise StatusError(
            f"{schema_path}: missing required operating sections "
            f"{sorted(expected_sections - required)!r}"
        )
    status_values = schema.get("properties", {}).get("status", {}).get("enum", [])
    if "APPROVED" not in status_values or "PROPOSED" not in status_values:
        raise StatusError(f"{schema_path}: profile status must distinguish approval")
    allocation_required = set(
        schema.get("properties", {}).get("allocation", {}).get("required", [])
    )
    if not {"allocation_authority", "risk_capacity_authority"} <= allocation_required:
        raise StatusError(
            f"{schema_path}: allocation and risk-capacity authorities must be separate"
        )
    latency_required = set(
        schema.get("properties", {}).get("latency", {}).get("required", [])
    )
    if not {"stages", "end_to_end_bound", "no_gate_weakening"} <= latency_required:
        raise StatusError(
            f"{schema_path}: latency survivability contract is incomplete"
        )

    iom_rows = {
        row["evidence_id"]: row
        for row in development.rows
        if row["evidence_id"].startswith("IOM-EV-")
    }
    if set(iom_rows) != _EXPECTED_IOM_IDS:
        raise StatusError(
            f"{development.label}: IOM family mismatch; "
            f"expected={sorted(_EXPECTED_IOM_IDS)!r}, got={sorted(iom_rows)!r}"
        )
    for evidence_id, row in iom_rows.items():
        if row["status"] != "NOT_IMPLEMENTED":
            raise StatusError(
                f"{development.label}: new {evidence_id} must start NOT_IMPLEMENTED"
            )
        if row["verification_profile_version"] != "IOM-0.1-PROPOSED":
            raise StatusError(
                f"{development.label}: {evidence_id} must bind Proposed IOM profile"
            )
        for field in ("implementation_owner", "evidence_owner", "independent_reviewer"):
            if not row[field].startswith("TBD-"):
                raise StatusError(
                    f"{development.label}: {evidence_id} must expose pending {field}"
                )


def validate_migration_conformance(
    repo_root: Path, csv_path: Path, markdown_path: Path
) -> int:
    """Validate package coverage and non-authorizing migration/Q6 honesty."""
    rows = _read_csv(csv_path, REQUIRED_MIGRATION_FIELDS)
    ids = [row["record_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise StatusError(f"{csv_path}: duplicate record_id")
    errors: list[str] = []
    for line_no, row in enumerate(rows, start=2):
        for field in REQUIRED_MIGRATION_FIELDS:
            if not row[field]:
                errors.append(f"line {line_no} {row['record_id']}: empty {field}")
        expected_authority = (
            "PROPOSED_Q6_NOT_GOVERNING"
            if row["category"] == "COMPLEXITY_DECOMMISSION"
            else "NON_AUTHORIZING_OPEN"
        )
        if row["authority_state"] != expected_authority:
            errors.append(
                f"line {line_no} {row['record_id']}: authority_state must be "
                f"{expected_authority}"
            )
        if row["operator_state_owner"] != (
            "TBD-consolidated-operator-safety-state-owner"
        ):
            errors.append(
                f"line {line_no} {row['record_id']}: operator state owner must "
                "remain explicit and pending"
            )
    if errors:
        raise StatusError(f"{csv_path}:\n  " + "\n  ".join(errors))

    by_category: dict[str, set[str]] = {}
    for row in rows:
        by_category.setdefault(row["category"], set()).add(row["record_id"])
    expected_categories = {
        "LEGACY_ROUTE",
        "OPERATOR_VIEW",
        "TOS_PACKAGE",
        "COMPLEXITY_DECOMMISSION",
    }
    if set(by_category) != expected_categories:
        raise StatusError(f"{csv_path}: migration category set is incomplete")
    if by_category["LEGACY_ROUTE"] != {f"LEGACY-{number:03}" for number in range(1, 6)}:
        raise StatusError(f"{csv_path}: legacy route census must be LEGACY-001..005")
    if by_category["OPERATOR_VIEW"] != {"OPERATOR-001"}:
        raise StatusError(
            f"{csv_path}: exactly one consolidated operator view is required"
        )
    expected_complexity = {f"COMPLEXITY-{number:03}" for number in range(1, 9)}
    if by_category["COMPLEXITY_DECOMMISSION"] != expected_complexity:
        raise StatusError(
            f"{csv_path}: complexity Q6 census must contain all eight rows"
        )

    package_root = repo_root / "tos/src/tos"
    actual_packages = {
        path.name
        for path in package_root.iterdir()
        if path.is_dir() and path.name != "__pycache__"
    }
    registered_packages = {
        record_id.removeprefix("TOS-") for record_id in by_category["TOS_PACKAGE"]
    }
    if registered_packages != actual_packages:
        raise StatusError(
            f"{csv_path}: TOS package census mismatch; "
            f"missing={sorted(actual_packages - registered_packages)!r}, "
            f"extra={sorted(registered_packages - actual_packages)!r}"
        )

    legacy_rows = [row for row in rows if row["category"] == "LEGACY_ROUTE"]
    for row in legacy_rows:
        source_path = repo_root / row["component"].split(maxsplit=1)[0]
        if not source_path.is_file():
            raise StatusError(
                f"{csv_path}: {row['record_id']} source path is missing: {source_path}"
            )

    markdown = markdown_path.read_text(encoding="utf-8-sig")
    required_markers = (
        "Production Authorization:** NO",
        "deployment/process state was not observed",
        "all eight Complexity Register Q6 answers remain OPEN",
        "Deleting a queue without broker reconciliation is not invalidation proof",
    )
    for marker in required_markers:
        if marker not in markdown:
            raise StatusError(f"{markdown_path}: missing honesty marker {marker!r}")
    for package in actual_packages:
        if f"| `{package}` |" not in markdown:
            raise StatusError(f"{markdown_path}: missing TOS package row {package}")
    for record_id in {
        *by_category["LEGACY_ROUTE"],
        *by_category["COMPLEXITY_DECOMMISSION"],
    }:
        if record_id not in markdown:
            raise StatusError(f"{markdown_path}: missing register row {record_id}")
    return len(rows)


def collect_status(repo_root: Path) -> StatusSnapshot:
    source_root = repo_root / "tos-spec/src"
    documents, adrs = load_document_states(source_root)
    part1 = load_evidence_register(repo_root / PART1_CSV, "Part 1")
    development = load_evidence_register(repo_root / DEV_CSV, "Parts 2/3 development")
    validate_markdown_mirror(repo_root / PART1_MD, part1)
    validate_markdown_mirror(repo_root / DEV_MD, development)
    authorities = load_authorities(repo_root / AUTHORITY_CSV)
    direct_traceability_count = validate_direct_traceability(
        source_root, part1, repo_root / TRACEABILITY_MD
    )
    p2_carried_questions = validate_p2_dispositions(
        repo_root / P2_DISPOSITION_CSV, repo_root / P2_DISPOSITION_MD
    )
    validate_investment_operating_model(repo_root / IOM_PROFILE_SCHEMA, development)
    migration_rows = validate_migration_conformance(
        repo_root, repo_root / MIGRATION_CSV, repo_root / MIGRATION_MD
    )
    const003_result = validate_economic_viability(
        repo_root / ECO_PROFILE_SCHEMA, part1, development
    )
    return StatusSnapshot(
        documents,
        adrs,
        part1,
        development,
        authorities,
        direct_traceability_count,
        p2_carried_questions,
        const003_result,
        migration_rows,
    )


def _counts_text(counts: Counter[str], order: Iterable[str]) -> str:
    return ", ".join(
        f"{counts.get(state, 0)} `{state}`" for state in order if counts.get(state, 0)
    )


def render_status(snapshot: StatusSnapshot) -> str:
    evidence_total = snapshot.part1.counts + snapshot.development.counts
    return f"""# Current TOS Status (generated)\n\n> Generated by `python tools/tos_spec_status.py --write` from canonical headers\n> and CSV registers under `tos-spec/src/`. Do not edit this file by hand. This\n> view confers no ADR acceptance, evidence result, restricted-live readiness, or\n> production authority.\n\n## Independent status axes\n\n| Axis | Current state | Meaning |\n|---|---|---|\n| Document ratification | {_counts_text(snapshot.documents, ("RATIFIED", "PROPOSED", "DE-RATIFIED", "SUPERSEDED"))} | Ratification governs specification text only; it is not ADR acceptance or runtime authority. |\n| ADR acceptance | {_counts_text(snapshot.adrs, ("ACCEPTED", "PROPOSED", "REJECTED", "SUPERSEDED"))} | A Proposed or even future Accepted ADR is not evidence or live authorization. |\n| Evidence | {sum(evidence_total.values())} total: {_counts_text(evidence_total, EVIDENCE_STATES)} | Unit tests and document reviews do not move these rows; governed execution and review do. |\n| Restricted-live | `{snapshot.authorities["restricted_live"]}` | Only the authority named in `AUTHORITY-STATUS.csv` may change this axis. |\n| Production authorization | `{snapshot.authorities["production"]}` | Evidence `PASS` does not imply production authorization. |\n\n## Evidence registers\n\n| Register | Total | NOT_IMPLEMENTED | READY | PASS | FAIL | INCONCLUSIVE | Other |\n|---|---:|---:|---:|---:|---:|---:|---:|\n| Part 1 | {len(snapshot.part1.rows)} | {snapshot.part1.counts.get("NOT_IMPLEMENTED", 0)} | {snapshot.part1.counts.get("READY", 0)} | {snapshot.part1.counts.get("PASS", 0)} | {snapshot.part1.counts.get("FAIL", 0)} | {snapshot.part1.counts.get("INCONCLUSIVE", 0)} | {sum(count for state, count in snapshot.part1.counts.items() if state not in {"NOT_IMPLEMENTED", "READY", "PASS", "FAIL", "INCONCLUSIVE"})} |\n| Parts 2/3 development | {len(snapshot.development.rows)} | {snapshot.development.counts.get("NOT_IMPLEMENTED", 0)} | {snapshot.development.counts.get("READY", 0)} | {snapshot.development.counts.get("PASS", 0)} | {snapshot.development.counts.get("FAIL", 0)} | {snapshot.development.counts.get("INCONCLUSIVE", 0)} | {sum(count for state, count in snapshot.development.counts.items() if state not in {"NOT_IMPLEMENTED", "READY", "PASS", "FAIL", "INCONCLUSIVE"})} |\n\n## Interpretation guardrails\n\n- Ratified document: governing specification baseline only.\n- Accepted ADR: accepted design decision only.\n- Evidence `PASS`: a governed evidence fact at the registered scope only.\n- Restricted-live and production: separate human-authority decisions; both remain\n  fail-closed unless the authority register records the governed act.\n- A dashboard, cache, healthy process, unit test, review result, implementation,\n  or registration is never an authority source.\n"""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--write", action="store_true", help="write the generated Markdown"
    )
    mode.add_argument(
        "--check", action="store_true", help="check inputs and generated Markdown"
    )
    parser.add_argument(
        "--root", type=Path, default=_repo_root(), help="repository root"
    )
    args = parser.parse_args(argv)

    try:
        snapshot = collect_status(args.root)
        rendered = render_status(snapshot)
        output = args.root / GENERATED_MD
        if args.write:
            output.write_text(rendered, encoding="utf-8")
            print(f"wrote {output}")
        else:
            actual = output.read_text(encoding="utf-8") if output.exists() else ""
            if actual != rendered:
                raise StatusError(
                    f"{output}: generated status is missing or stale; "
                    "run python tools/tos_spec_status.py --write"
                )
            print(
                "TOS spec status PASS: "
                f"documents={sum(snapshot.documents.values())}, "
                f"ADRs={sum(snapshot.adrs.values())}, "
                f"Part1={len(snapshot.part1.rows)}, "
                f"DEV={len(snapshot.development.rows)}, "
                f"direct_traceability={snapshot.direct_traceability_count}/30, "
                f"p2_carried={snapshot.p2_carried_questions}, "
                f"CONST-003={snapshot.const003_result}, "
                f"migration_rows={snapshot.migration_rows}, "
                f"restricted_live={snapshot.authorities['restricted_live']}, "
                f"production={snapshot.authorities['production']}"
            )
    except (OSError, StatusError) as exc:
        print(f"TOS spec status FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
