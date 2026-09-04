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
import os
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from tools.tos_profile_census import _profile_null_key_census

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
VERIFICATION_PROFILE_YAML = Path(
    "tos-spec/src/part-1-foundation/verification/VERIFICATION-PROFILE-002.yaml"
)
# Non-normative: the completion plan's §1 baseline table is a point-in-time
# snapshot, not a canonical input.  A drift here is reported as a WARNING (see
# ``_profile_baseline_plan_warning``), never a StatusError -- this file must not
# become the plan's hostage.
BASELINE_PLAN_MD = Path("docs/plans/2026-08-11-tos-completion-development-plan.md")
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
# The corpus is broker-agnostic, so the concrete class names that constitute this
# deployment's broker transport binding live in a governed registry instead of in
# this file.  See the reverse-census block below for why that separation is not
# cosmetic.
#
# The registry lives *outside* tos-spec/ because it names concrete broker
# symbols: ADR-002-004:798 puts facts about a specific broker in a non-normative
# instance produced on the implementation track, and
# BROKER-CAPABILITY-PROFILE-template.yaml:20-24 states the placement rule
# directly.  ``docs/broker-profiles/`` is the existing home for exactly that.
BROKER_SYMBOLS_CSV = Path("docs/broker-profiles/BROKER-TRANSPORT-SYMBOLS.csv")
BROKER_SYMBOLS_MD = Path("docs/broker-profiles/BROKER-TRANSPORT-SYMBOLS.md")

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
REQUIRED_BROKER_SYMBOL_FIELDS = (
    "symbol",
    "kind",
    # ``transport_role``, not ``capability_class``: the corpus already spends
    # "capability class" twice -- ADR-002-004 §10 Broker Conformance Classes
    # (CLASS-A..D) and ARCHITECTURE-GATE-STATUS.md:314's §13.15 composed class --
    # and this column is neither of them.
    "transport_role",
    "capability_reference",
    "binding_rationale",
    "authority_state",
)
_STATUS_HEADER = re.compile(
    r"^\s*(?:-\s*)?\*\*Status:?\*\*:?\s*(.+?)\s*$", re.MULTILINE
)
_PRODUCTION_AUTHORIZATION_HEADER = re.compile(
    r"^\s*(?:[-*]\s*)?\*\*Production Authorization:?\*\*:?\s*(.+?)\s*$", re.MULTILINE
)
_PRODUCTION_AUTHORIZATION_STATES = {"NO": "NOT_AUTHORIZED", "YES": "AUTHORIZED"}
# Documents that independently publish the corpus's production-authorization
# honesty marker.  ``load_authorities`` requires them to exist, to carry the
# marker, and to agree with each other and with ``AUTHORITY-STATUS.csv``.
_PRODUCTION_HONESTY_SOURCES = (
    "part-1-foundation/verification/EVIDENCE-REGISTER-002.md",
    "part-3-development/verification/EVIDENCE-REGISTER-DEV.md",
    "MIGRATION-CONFORMANCE-REGISTER.md",
)
_GOVERNING_SOURCE_PATH = re.compile(r"(?<![\w./-])([\w./-]+\.md)(?![\w./-])")
_SUMMARY_LINE = re.compile(r"^- ([A-Za-z][A-Za-z0-9_ ]*): \*\*(\d+)\*\*$", re.MULTILINE)
_TABLE_SEPARATOR_ROW = re.compile(r"\|(?:\s*:?-{3,}:?\s*\|)+")
_REGISTER_HEADER_PREFIX = "| ID "
_REGISTER_COLUMNS = (
    "evidence_id",
    "domain",
    "title",
    "primary_adr",
    "minimum_evidence_level",
    "status",
    "implementation_owner",
    "independent_reviewer",
)
_BLOCKQUOTE_PREFIX = re.compile(r"^[ \t]*>+[ \t]?", re.MULTILINE)
_DOCUMENT_NAME = re.compile(r"^(?:RFC-\d{3}|GOV-\d{3})-")
_ADR_NAME = re.compile(r"^ADR-(?:002|DEV)-\d{3}-")
_PART1_ADR_NAME = re.compile(r"^(ADR-002-\d{3})-")
_NON_CANONICAL_SOURCE_DIRS = frozenset({".omc", "patches", "reviews"})
_TRACEABILITY_HEADING = re.compile(
    r"^##\s+\d+(?:\.\d+)?\.?\s+(?:Requirements\s+)?Traceability\s*$",
    re.MULTILINE,
)
_SAFE_ID = re.compile(r"\bSAFE-\d{3}\b")
# The four ADRs whose direct Traceability tables transcribe their own existing
# ``Depends On`` SAFE set.  Each must survive the full forward/reverse matrix
# cross-check below.
_DIRECT_REPAIR_ADRS = frozenset(
    {"ADR-002-003", "ADR-002-004", "ADR-002-005", "ADR-002-006"}
)
# ADR-002-002 is deliberately absent from ``_DIRECT_REPAIR_ADRS``: no source
# document allocates any SAFE requirement to it, so a direct table there would
# be unsourced.  Its exemption is not a hole -- it is a recorded gap, and
# ``_validate_source_gap_traceability`` requires the record to stay published in
# both the ADR and the matrix.  Recognition is explicit: ``_TRACEABILITY_HEADING``
# does not match ``## 38.1 Requirements Traceability -- Source Gap`` (the heading
# carries trailing text), and the tool must never treat that near-miss as if it
# were a table.
_SOURCE_GAP_ADRS = frozenset({"ADR-002-002"})
_SOURCE_GAP_HEADING = re.compile(
    r"^##\s+\d+(?:\.\d+)?\.?\s+Requirements\s+Traceability\s+—\s+Source\s+Gap\s*$",
    re.MULTILINE,
)
_DEPENDS_ON_HEADER = re.compile(r"^\s*(?:[-*]\s*)?\*\*Depends On:?\*\*", re.MULTILINE)
_MATRIX_SOURCE_GAP_SECTION = re.compile(
    r"^###\s+5\.3\s+Direct-source gaps\b", re.MULTILINE
)
_DIRECT_TABLE_SUMMARY = (
    "- ADRs with a direct Traceability table: 29/30; source gaps: 1 "
    "(ADR-002-002 — see §5.3; unreachable family: RC-EV)."
)
# Reverse legacy-route census.  The forward check (a registered ``component``
# still resolves to a real file) can only confirm routes somebody already wrote
# down, so on its own it can never discover an unregistered one -- which is
# exactly how ``scripts/trading/flatten_all.py`` and
# ``scripts/trading/recover_positions.py`` stayed off the register.  A hardcoded
# ``LEGACY-001..005`` range had the same blindness.
#
# The same blindness applies to the *vocabulary* the census scans for.  A broker
# class name compiled into this file would mean a second broker adapter is missed
# silently -- a hardcoded census can never discover a new item, whether the item
# is a route or the symbol that identifies one.  The vocabulary is therefore a
# governed corpus input (``BROKER-TRANSPORT-SYMBOLS.csv``) that this file derives
# from and never restates.  Only the *kind* vocabulary below is the tool's own:
# it selects an enforcement tier, it is not a broker fact.
_BROKER_SYMBOL_ORDER_SENDER = "ORDER_SENDER"
_BROKER_SYMBOL_KINDS = frozenset({_BROKER_SYMBOL_ORDER_SENDER, "BROKER_CLIENT_READ"})
# Recording a transport symbol is an observation; no value of this column may
# turn it into an authorization.
_BROKER_SYMBOL_AUTHORITY_STATE = "NON_AUTHORIZING_OPEN"
# Registered symbols are rejected unless they are bare Python identifiers, so a
# regex metacharacter can never reach the compiled pattern.  ``re.escape`` below
# is the second, independent guard.
_BROKER_SYMBOL_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# Every registered symbol must cite the normative treatment it is bound to, and
# the cited decision must resolve to a real document.  Prose is not validated --
# only that the identifier exists -- because a checker that graded prose would be
# asserting a judgement it cannot make.
_BROKER_SYMBOL_DECISION = re.compile(r"\bADR-\d{3}-\d{3}\b")
_BROKER_SYMBOLS_MARKER = "## 4. Registered symbols"
# NIT-4: matching the header by an exact cell tuple rather than a ``| Symbol ``
# prefix, so a symbol literally named ``Symbol`` does not skip its own row.
_BROKER_SYMBOLS_HEADER_CELLS = (
    "Symbol",
    "Kind",
    "Transport role",
    "Capability reference",
    "Binding rationale",
    "Authority state",
)
# NIT-3: the table ends at the next Markdown section, so a later section's table
# cannot be absorbed into this one.
_BROKER_SYMBOLS_SECTION_END = re.compile(r"^##\s", re.MULTILINE)
_BROKER_SYMBOLS_MIRROR_COLUMNS = REQUIRED_BROKER_SYMBOL_FIELDS
# The registry must keep saying what it is.  A deployment binding record that
# quietly starts reading as specification text would reintroduce broker specifics
# into the normative layer by the back door.
_BROKER_SYMBOLS_STANDING_MARKERS = (
    "This registry is non-normative.",
    "It confers no ADR acceptance, evidence result, or authorization.",
    "It is a deployment binding record, not a specification.",
    "The normative treatment of brokers is the capability-class model in "
    "ADR-002-004",
    "Adding a broker requires editing this registry, which is a governed, "
    "reviewable act",
    # Why it is not in tos-spec/.  Losing this sentence is how a broker-naming
    # file drifts back into the published corpus.
    "This registry names concrete broker classes, so it may not live in the "
    "published corpus.",
    # The coverage claim must stay honest: the scan does not see dotted or
    # indirect construction, and must never be read as if it did.
    "The scan is **not** complete, and this register does not claim it is.",
)
_ENTRYPOINT_GUARD = re.compile(
    r"^if\s+__name__\s*==\s*[\"']__main__[\"']\s*:", re.MULTILINE
)
_REVERSE_SCAN_SKIPPED_DIRS = frozenset(
    {
        "tos",
        "tos-spec",
        "tests",
        "node_modules",
        "__pycache__",
        "build",
        "dist",
        "venv",
        "site-packages",
    }
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
    direct_traceability_total: int
    unregistered_broker_sites: tuple[str, ...]
    p2_carried_questions: int
    const003_result: str
    migration_rows: int
    broker_site_rows: int
    transcription_sites: int
    order_sender_symbols: tuple[str, ...]
    profile_total: int
    profile_null_keys: int
    profile_plan_warning: str | None


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
    head, _, body = text.partition(marker)
    marker_line_no = head.count("\n") + 1
    parsed: list[dict[str, str]] = []
    for offset, line in enumerate(body.splitlines()):
        stripped = line.strip()
        if not stripped.startswith("|"):
            # Not a table row at all: prose, blank lines, headings.
            continue
        if stripped.startswith(
            _REGISTER_HEADER_PREFIX
        ) or _TABLE_SEPARATOR_ROW.fullmatch(stripped):
            # The column header and the GFM alignment separator.
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) != len(_REGISTER_COLUMNS):
            # A malformed row is never dropped: GFM renders surplus cells
            # invisibly, so a silent skip would publish a fabricated row.
            raise StatusError(
                f"{path}: line {marker_line_no + offset}: register table row has "
                f"{len(cells)} cells, expected {len(_REGISTER_COLUMNS)}: {stripped}"
            )
        parsed.append(dict(zip(_REGISTER_COLUMNS, cells, strict=True)))
    if not parsed:
        raise StatusError(f"{path}: register table contains no rows")
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

    _validate_summary_parity(markdown_path, register)


def _validate_summary_parity(markdown_path: Path, register: EvidenceRegister) -> None:
    """Reconcile the Markdown summary block against the CSV in both directions.

    ``register.counts`` is a ``Counter``, so it has no key for a state that no
    CSV row carries.  Iterating it alone therefore never inspects the Markdown
    line for an absent state, which lets a fabricated ``- PASS: **7**`` (or a
    wholly invented state) pass unread.  Every summary line in the Markdown is
    parsed first, then reconciled.
    """
    text = markdown_path.read_text(encoding="utf-8-sig")
    total_label = "Total evidence items"
    known_labels = {total_label, *EVIDENCE_STATES}
    errors: list[str] = []

    declared: dict[str, int] = {}
    for label, value in _SUMMARY_LINE.findall(text):
        if label in declared:
            errors.append(f"duplicate summary line for {label}")
        declared[label] = int(value)

    for label, value in declared.items():
        if label not in known_labels:
            errors.append(f"unknown summary state {label!r} (declared {value})")
            continue
        expected = (
            len(register.rows)
            if label == total_label
            else register.counts.get(label, 0)
        )
        if value != expected:
            errors.append(f"summary {label}={value}, CSV={expected}")

    required = [
        total_label,
        *(state for state in EVIDENCE_STATES if register.counts.get(state, 0)),
    ]
    for label in required:
        if label not in declared:
            errors.append(f"missing summary count for {label}")

    if errors:
        raise StatusError(f"{markdown_path}: " + "; ".join(errors))


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
        if _NON_CANONICAL_SOURCE_DIRS.intersection(path.relative_to(source_root).parts):
            continue
        if _DOCUMENT_NAME.match(path.name):
            documents[_header_state(path, DOCUMENT_STATES)] += 1
        elif _ADR_NAME.match(path.name):
            adrs[_header_state(path, ADR_STATES)] += 1
    if not documents:
        raise StatusError(f"{source_root}: no RFC/GOV documents discovered")
    if not adrs:
        raise StatusError(f"{source_root}: no ADR documents discovered")
    return documents, adrs


def _resolve_governing_source(source_root: Path, axis: str, declared: str) -> Path:
    """Dereference an axis's declared ``governing_source`` to a real document."""
    match = _GOVERNING_SOURCE_PATH.search(declared)
    if match is None:
        raise StatusError(
            f"{AUTHORITY_CSV}: {axis}: governing_source names no resolvable corpus "
            f"document: {declared!r}"
        )
    relative = match.group(1)
    candidate = source_root / relative
    try:
        candidate.resolve().relative_to(source_root.resolve())
    except ValueError as exc:
        raise StatusError(
            f"{AUTHORITY_CSV}: {axis}: governing_source {relative!r} points "
            f"outside the corpus source root {source_root}"
        ) from exc
    if not candidate.is_file():
        raise StatusError(
            f"{AUTHORITY_CSV}: {axis}: governing_source does not resolve to an "
            f"existing corpus document: {relative} (searched under {source_root})"
        )
    return candidate


def _governing_status_gate(path: Path) -> tuple[bool, str]:
    """Return whether a governing document's own status can support AUTHORIZED."""
    if _ADR_NAME.match(path.name):
        state = _header_state(path, ADR_STATES)
        return state == "ACCEPTED", f"ADR Status={state}"
    if _DOCUMENT_NAME.match(path.name):
        state = _header_state(path, DOCUMENT_STATES)
        return state == "RATIFIED", f"Status={state}"
    return True, "no document-status gate"


def _production_authorization_header(path: Path) -> str | None:
    match = _PRODUCTION_AUTHORIZATION_HEADER.search(
        path.read_text(encoding="utf-8-sig")
    )
    if match is None:
        return None
    return match.group(1).strip().rstrip(".").upper()


def _production_authority_errors(
    source_root: Path, declared: str, governing: Path
) -> list[str]:
    """Derive the production axis from the corpus instead of trusting the CSV."""
    observed: dict[Path, str] = {}
    candidates = [
        governing,
        *(source_root / rel for rel in _PRODUCTION_HONESTY_SOURCES),
    ]
    for candidate in candidates:
        if candidate in observed:
            continue
        if not candidate.is_file():
            return [
                f"production: required honesty source is missing: {candidate}",
            ]
        header = _production_authorization_header(candidate)
        if header is None:
            return [
                f"production authority is declared against {candidate}, but that "
                "document carries no '**Production Authorization:**' header",
            ]
        observed[candidate] = header

    values = set(observed.values())
    if len(values) > 1:
        detail = "; ".join(
            f"{path}='{value}'"
            for path, value in sorted(observed.items(), key=lambda item: str(item[0]))
        )
        return [f"corpus production-authorization headers disagree: {detail}"]
    header_value = values.pop()
    derived = _PRODUCTION_AUTHORIZATION_STATES.get(header_value)
    if derived is None:
        return [
            f"{governing}: unsupported '**Production Authorization:**' value "
            f"{header_value!r}; expected one of "
            f"{sorted(_PRODUCTION_AUTHORIZATION_STATES)!r}"
        ]
    if derived != declared:
        return [
            f"production={declared} contradicts its own declared governing source "
            f"{governing}, which reads '**Production Authorization:** "
            f"{header_value}' (derived {derived}); the authority register may not "
            "self-attest"
        ]
    return []


def load_authorities(path: Path, source_root: Path) -> dict[str, str]:
    rows = _read_csv(path, REQUIRED_AUTHORITY_FIELDS)
    required_axes = {"restricted_live", "production"}
    seen: dict[str, str] = {}
    sources: dict[str, Path] = {}
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
        sources[axis] = _resolve_governing_source(
            source_root, axis, row["governing_source"]
        )
        seen[axis] = row["status"]
    if set(seen) != required_axes:
        raise StatusError(
            f"{path}: authority axes must be exactly {sorted(required_axes)!r}"
        )

    errors: list[str] = []
    for axis, state in seen.items():
        permits, reason = _governing_status_gate(sources[axis])
        if state == "AUTHORIZED" and not permits:
            errors.append(
                f"{axis}=AUTHORIZED is not supported by its declared governing "
                f"source {sources[axis]} ({reason}); a governing document that is "
                "not itself accepted confers no authority"
            )
    errors.extend(
        _production_authority_errors(
            source_root, seen["production"], sources["production"]
        )
    )
    if errors:
        raise StatusError(f"{path}: " + "; ".join(errors))
    return seen


@dataclass(frozen=True)
class _CountTranscription:
    """One prose location that hand-transcribes a derived register count.

    ``pattern`` is matched against whitespace-normalised, blockquote-stripped
    text so a wrapped sentence still matches.  Each capture group is an integer
    that must equal the derived value named by the matching ``derived_keys``
    entry.  Anchors carry enough literal context to exclude the corpus's
    wave-scoped historical snapshots, which quote counts that were correct at
    their review point and must not be rewritten.
    """

    relative_path: str
    label: str
    pattern: re.Pattern[str]
    derived_keys: tuple[str, ...]


_GATE_STATUS_MD = "part-1-foundation/ARCHITECTURE-GATE-STATUS.md"
_COMPLEXITY_REGISTER_MD = "part-1-foundation/COMPLEXITY-REGISTER-002.md"
_IMPLEMENTATION_PLAN_MD = "part-1-foundation/verification/IMPLEMENTATION-PLAN-002.md"
_PREFACE_MD = "preface.md"
_PROFILE_YAML = "part-1-foundation/verification/VERIFICATION-PROFILE-002.yaml"

_PART1_STATE_KEYS = ("part1.NOT_IMPLEMENTED", "part1.READY", "part1.PASS")

_COUNT_TRANSCRIPTIONS: tuple[_CountTranscription, ...] = (
    _CountTranscription(
        _GATE_STATUS_MD,
        "header Verification Execution",
        re.compile(
            r"\*\*Verification Execution:\*\* Part 1: (\d+) `NOT_IMPLEMENTED`, "
            r"(\d+) `READY`, (\d+) `PASS`; development: (\d+) `NOT_IMPLEMENTED`"
        ),
        (*_PART1_STATE_KEYS, "development.NOT_IMPLEMENTED"),
    ),
    _CountTranscription(
        _GATE_STATUS_MD,
        "current evidence state",
        re.compile(
            r"The Part-1 register contains (\d+) rows: (\d+) `NOT_IMPLEMENTED`, "
            r"(\d+) `READY`, and (\d+) `PASS`; the development register contains "
            r"(\d+) `NOT_IMPLEMENTED` rows"
        ),
        ("part1.TOTAL", *_PART1_STATE_KEYS, "development.NOT_IMPLEMENTED"),
    ),
    _CountTranscription(
        _GATE_STATUS_MD,
        "development-track evidence row",
        re.compile(
            r"\| Development-track verification evidence \| (\d+) items registered "
            r"\(EVIDENCE-REGISTER-DEV\), all `NOT_IMPLEMENTED`"
        ),
        ("development.TOTAL",),
    ),
    _CountTranscription(
        _GATE_STATUS_MD,
        "ratification ladder preamble",
        re.compile(
            r"The current Part-1 register is (\d+) `NOT_IMPLEMENTED`, (\d+) `READY`, "
            r"and (\d+) `PASS`; all (\d+) development-track rows remain "
            r"`NOT_IMPLEMENTED`"
        ),
        (*_PART1_STATE_KEYS, "development.TOTAL"),
    ),
    _CountTranscription(
        _GATE_STATUS_MD,
        "evidence-incomplete disposition row",
        re.compile(
            r"Evidence incomplete \(Part 1: (\d+) `NOT_IMPLEMENTED` / (\d+) `READY` "
            r"/ (\d+) `PASS`; development: (\d+) `NOT_IMPLEMENTED`\)"
        ),
        (*_PART1_STATE_KEYS, "development.NOT_IMPLEMENTED"),
    ),
    _CountTranscription(
        _COMPLEXITY_REGISTER_MD,
        "non-normative standing preamble",
        re.compile(
            r"\(Part-1 remains (\d+); the development track now has (\d+) after "
            r"separate ECO/IOM registrations\)"
        ),
        ("part1.TOTAL", "development.TOTAL"),
    ),
    _CountTranscription(
        _COMPLEXITY_REGISTER_MD,
        "standing restated",
        re.compile(
            r"It adds nothing to either evidence count \(Part-1 (\d+); development "
            r"track (\d+)\)\."
        ),
        ("part1.TOTAL", "development.TOTAL"),
    ),
    _CountTranscription(
        _IMPLEMENTATION_PLAN_MD,
        "register-count note (Part 1)",
        re.compile(
            r"The Part-1 Evidence Register holds (\d+) items: (\d+) "
            r"`NOT_IMPLEMENTED`, (\d+) `READY`, and (\d+) `PASS`\."
        ),
        ("part1.TOTAL", *_PART1_STATE_KEYS),
    ),
    _CountTranscription(
        _IMPLEMENTATION_PLAN_MD,
        "register-count note (development)",
        re.compile(r"EVIDENCE-REGISTER-DEV \((\d+) items, all `NOT_IMPLEMENTED`"),
        ("development.TOTAL",),
    ),
    _CountTranscription(
        _PREFACE_MD,
        "part map (Part 1)",
        re.compile(r"EVIDENCE-REGISTER-002 \((\d+) items\)"),
        ("part1.TOTAL",),
    ),
    _CountTranscription(
        _PREFACE_MD,
        "part map (development)",
        re.compile(r"EVIDENCE-REGISTER-DEV \((\d+) items at this revision"),
        ("development.TOTAL",),
    ),
    # S-1/S-2 (design §3.3.2): the two prose/table transcriptions of the direct
    # Traceability table count. Anchors require the "source gap"/"gap" literal
    # context alongside the digits -- like S-3 (``_DIRECT_TABLE_SUMMARY``) -- so a
    # rewrite that keeps only the numbers still fails.
    _CountTranscription(
        _GATE_STATUS_MD,
        "direct-table count (prose, S-1)",
        re.compile(r"Direct tables now stand at \*\*(\d+)/(\d+) with 1 source gap\*\*"),
        ("direct_traceability.count", "direct_traceability.total"),
    ),
    _CountTranscription(
        _GATE_STATUS_MD,
        "direct-table count (table cell, S-2)",
        re.compile(r"leaving (\d+)/(\d+) direct tables and 1 gap"),
        ("direct_traceability.count", "direct_traceability.total"),
    ),
    # Profile null-key census (design §6.3.2). Only ``164`` (total numeric keys)
    # and ``16`` (null keys) are derived-and-checked here; the ``148`` (non-null)
    # figure that appears alongside them is UNCHK-001 (design §6.3.3) -- the
    # profile's per-key ``approved`` predicate is not machine-derivable yet (the
    # ``limits`` provenance markers live in YAML comments, not values), so ``148``
    # stays required literal context for anchor specificity but is never compared
    # against a derived value.
    _CountTranscription(
        _GATE_STATUS_MD,
        "profile null-key census (gate status)",
        re.compile(
            r"148/(\d+) numeric keys carry approved values "
            r"\(`MIN_evidence_retention_ms` approved 2026-08-07, §3\.26; "
            r"`MAX_time_conservative_freshness_age_ms` approved 2026-09-04, "
            r"§3\.28\); "
            r"(\d+) keys \(10 broker bounds pending P0-2 measurement, 6 "
            r"instance/architecture limits under ratified trigger-bound "
            r"deferrals\) remain "
            r"key-level unapproved and fail-closed"
        ),
        ("profile.total", "profile.null"),
    ),
    _CountTranscription(
        _PROFILE_YAML,
        "profile null-key census (profile header)",
        re.compile(
            r"148 of the (\d+) numeric keys now carry approved values; "
            r"(\d+) keys stay null —"
        ),
        ("profile.total", "profile.null"),
    ),
)


def _normalized_prose(text: str) -> str:
    """Flatten wrapping and blockquote markers so anchors match across lines."""
    return re.sub(r"\s+", " ", _BLOCKQUOTE_PREFIX.sub("", text))


def _derived_register_counts(
    part1: EvidenceRegister, development: EvidenceRegister
) -> dict[str, int]:
    derived = {
        "part1.TOTAL": len(part1.rows),
        "development.TOTAL": len(development.rows),
    }
    for state in EVIDENCE_STATES:
        derived[f"part1.{state}"] = part1.counts.get(state, 0)
        derived[f"development.{state}"] = development.counts.get(state, 0)
    return derived


def validate_count_transcriptions(
    source_root: Path,
    part1: EvidenceRegister,
    development: EvidenceRegister,
    extra_derived: Mapping[str, int] | None = None,
) -> int:
    """Check every registered hand-transcribed register count against the CSVs.

    The registered documents are required to exist: deleting one, deleting an
    anchored sentence, or editing a transcribed number all fail.

    ``extra_derived`` folds in derived counts that do not come from the two
    evidence registers -- the direct-traceability (S-1/S-2) and profile
    null-key-census (§6.3.2) axes are computed by the caller and merged in here
    so every count anchor is checked through this one loop.
    """
    derived = _derived_register_counts(part1, development)
    if extra_derived:
        derived.update(extra_derived)
    errors: list[str] = []
    checked = 0
    texts: dict[str, str] = {}
    for entry in _COUNT_TRANSCRIPTIONS:
        if entry.relative_path not in texts:
            path = source_root / entry.relative_path
            if not path.is_file():
                errors.append(
                    f"{entry.relative_path}: required transcription source is missing"
                )
                texts[entry.relative_path] = ""
                continue
            texts[entry.relative_path] = _normalized_prose(
                path.read_text(encoding="utf-8-sig")
            )
        text = texts[entry.relative_path]
        if not text:
            continue
        matches = entry.pattern.findall(text)
        if not matches:
            errors.append(
                f"{entry.relative_path} [{entry.label}]: transcription anchor not "
                "found; the sentence was edited, moved, or deleted"
            )
            continue
        for match in matches:
            values = match if isinstance(match, tuple) else (match,)
            for key, value in zip(entry.derived_keys, values, strict=True):
                if int(value) != derived[key]:
                    errors.append(
                        f"{entry.relative_path} [{entry.label}]: transcribed "
                        f"{key}={value} but the registers derive {derived[key]}"
                    )
        checked += 1
    if errors:
        raise StatusError(
            "register count transcription check failed:\n  " + "\n  ".join(errors)
        )
    return checked


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


def _exact_primary_family(register: EvidenceRegister, adr: str) -> str:
    exact_families = {
        row["evidence_id"].rsplit("-", 1)[0]
        for row in register.rows
        if row["primary_adr"] == adr
    }
    if len(exact_families) != 1:
        raise StatusError(
            f"{adr}: expected one exact primary evidence family, got {sorted(exact_families)!r}"
        )
    return next(iter(exact_families))


def _validate_source_gap_traceability(
    adr: str,
    adr_path: Path,
    matrix_path: Path,
    matrix: str,
    register: EvidenceRegister,
) -> None:
    """Require a recorded direct-source gap to stay recorded, in both documents.

    Exempting ``adr`` from the direct-table requirement is only honest while the
    gap itself stays visible.  Re-adding an unsourced direct table, dropping the
    ADR's gap section, dropping the matrix's open-gap row, or quietly filling in
    a SAFE set must each fail loudly rather than register as coverage.
    """
    text = adr_path.read_text(encoding="utf-8-sig")
    if _TRACEABILITY_HEADING.search(text) is not None:
        raise StatusError(
            f"{adr_path}: {adr} carries a direct Traceability table again, but no "
            "source document allocates a SAFE requirement to it; closing this gap "
            "is a GOV-001 G6 amendment, not a transcription"
        )
    if _SOURCE_GAP_HEADING.search(text) is None:
        raise StatusError(
            f"{adr_path}: {adr} no longer publishes its "
            "'Requirements Traceability — Source Gap' section"
        )
    if _DEPENDS_ON_HEADER.search(text) is not None:
        raise StatusError(
            f"{adr_path}: {adr} now declares a Depends On header; the recorded gap "
            "asserts it declares none, so the gap record is stale"
        )

    if _MATRIX_SOURCE_GAP_SECTION.search(matrix) is None:
        raise StatusError(f"{matrix_path}: the §5.3 direct-source gap section is gone")
    family = _exact_primary_family(register, adr)
    gap_row = re.search(
        rf"^\| {re.escape(adr)} \| {re.escape(family)} \| ([^|]*) \| ([^|]*) \|$",
        matrix,
        re.MULTILINE,
    )
    if gap_row is None:
        raise StatusError(
            f"{matrix_path}: §5.3 no longer records an open source gap for "
            f"{adr}/{family}"
        )
    if _SAFE_ID.search(gap_row.group(1)):
        raise StatusError(
            f"{matrix_path}: {adr} gap row now lists a direct SAFE set "
            f"({gap_row.group(1).strip()!r}); an allocation may not be introduced here"
        )
    if "OPEN source gap" not in gap_row.group(2):
        raise StatusError(f"{matrix_path}: {adr} gap row no longer reads OPEN")
    reverse_row = re.search(
        rf"^\| {re.escape(family)} \| ([^|]+) \|$", matrix, re.MULTILINE
    )
    if reverse_row is None:
        raise StatusError(f"{matrix_path}: missing reverse row for {family}")
    reverse_cell = reverse_row.group(1)
    if _SAFE_ID.search(reverse_cell) or "source gap" not in reverse_cell:
        raise StatusError(
            f"{matrix_path}: {family} must stay unreachable through the SAFE→ADR "
            f"bridge and cite the source gap; got {reverse_cell.strip()!r}"
        )


def validate_direct_traceability(
    source_root: Path, register: EvidenceRegister, matrix_path: Path
) -> tuple[int, int]:
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

    unknown_gaps = sorted(_SOURCE_GAP_ADRS - set(adr_paths))
    if unknown_gaps:
        raise StatusError(
            f"{source_root}: recorded source-gap ADRs do not exist: {unknown_gaps!r}"
        )
    safe_sets = {
        adr: _traceability_safe_ids(path, defined_safes)
        for adr, path in adr_paths.items()
        if adr not in _SOURCE_GAP_ADRS
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
    if _DIRECT_TABLE_SUMMARY not in matrix:
        raise StatusError(f"{matrix_path}: direct-table coverage summary is stale")
    for adr in sorted(_SOURCE_GAP_ADRS):
        _validate_source_gap_traceability(
            adr, adr_paths[adr], matrix_path, matrix, register
        )
    for adr in sorted(_DIRECT_REPAIR_ADRS):
        family = _exact_primary_family(register, adr)
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
    return len(safe_sets), len(adr_paths)


_PROFILE_BASELINE_PLAN_CELL = re.compile(
    r"Verification Profile \| (\d+)/(\d+) 값 승인, (\d+)개 null/fail-closed"
)


def _load_profile_key_census(repo_root: Path) -> tuple[int, int]:
    """``(total numeric keys, null keys)`` for VERIFICATION-PROFILE-002.

    Delegates to the shared :func:`tools.tos_profile_census._profile_null_key_census`
    so this file and ``tools/tos_evidence_run.py`` derive the same numbers from one
    authored implementation (CLAUDE.md DRY; design §6.3.2). Unlike the evidence-run
    approval reader -- which folds an uncountable census into UNKNOWN, because
    UNKNOWN is a legitimate approval state -- this corpus-integrity check has no
    fail-closed placeholder to fall back to, so an uncountable census aborts here.
    """
    path = repo_root / VERIFICATION_PROFILE_YAML
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise StatusError(f"{path}: could not be read: {exc}") from exc
    except yaml.YAMLError as exc:
        raise StatusError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(doc, dict):
        raise StatusError(f"{path}: profile document root must be a mapping")
    census = _profile_null_key_census(doc)
    if census is None:
        raise StatusError(
            f"{path}: null-key census could not be derived (unrecognised bounds/"
            "limits shape)"
        )
    total, null_names = census
    return total, len(null_names)


def profile_baseline_plan_warning(
    repo_root: Path, profile_total: int, profile_null: int
) -> str | None:
    """Non-blocking drift check for the completion plan's §1 baseline table.

    ``docs/plans/2026-08-11-tos-completion-development-plan.md`` is a non-normative,
    bound planning document (design §6.3.3: "상위 계획 §1은 비규범 문서이므로 차단
    대상이 아니라 경고 대상으로 한다"). This never raises ``StatusError`` -- a stale
    or missing baseline cell is reported as a warning string for the caller to print,
    never a check failure, so the plan can never hold the corpus-integrity gate
    hostage.
    """
    path = repo_root / BASELINE_PLAN_MD
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return f"{BASELINE_PLAN_MD}: baseline plan document is unreadable"
    match = _PROFILE_BASELINE_PLAN_CELL.search(text)
    if match is None:
        return (
            f"{BASELINE_PLAN_MD}: §1 baseline table no longer states the "
            "Verification Profile row in the expected form"
        )
    _approved, total, null_keys = (int(value) for value in match.groups())
    if total != profile_total or null_keys != profile_null:
        return (
            f"{BASELINE_PLAN_MD}: §1 baseline table reads "
            f"{total}/{null_keys} null but the profile now derives "
            f"{profile_total}/{profile_null} null (non-normative; not blocking)"
        )
    return None


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


def _broker_symbol_alternation(symbols: Sequence[str]) -> str:
    # Longest first so a registered prefix cannot shadow a longer registered name.
    return "|".join(
        re.escape(symbol) for symbol in sorted(symbols, key=len, reverse=True)
    )


def _compile_broker_construction(symbols: Sequence[str]) -> re.Pattern[str]:
    return re.compile(
        rf"(?<![\w.])(?P<name>{_broker_symbol_alternation(symbols)})\s*\("
    )


def _compile_broker_definition(symbols: Sequence[str]) -> re.Pattern[str]:
    """Match a module-level ``class <RegisteredSymbol>`` -- the structural anchor.

    Anchored at column zero: a nested or locally defined class is not a
    module-level transport binding, and accepting one would widen the anchor to
    places a decoy is cheap to hide.
    """
    return re.compile(
        rf"^class\s+(?P<name>{_broker_symbol_alternation(symbols)})\s*[(:]",
        re.MULTILINE,
    )


@dataclass(frozen=True)
class BrokerTransportVocabulary:
    """The registered broker transport symbols, derived from the corpus.

    Nothing here is a literal in this file.  ``construction`` is compiled from
    ``symbols`` and ``order_senders`` is selected by the registry's ``kind``
    column, so registering a second broker's client is a corpus edit and never a
    tool edit.

    The invariants live here rather than only in the loader: a vocabulary that
    scans for nothing, or whose pattern has drifted from its own symbol list,
    makes every downstream scan return a confident green.  A type that can be
    constructed into that state is a fail-open waiting for a second caller.
    """

    symbols: tuple[str, ...]
    order_senders: frozenset[str]
    construction: re.Pattern[str]
    cited_decisions: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.symbols:
            raise StatusError(
                "broker transport vocabulary has no symbols; the reverse census "
                "would scan for nothing"
            )
        unknown = self.order_senders - set(self.symbols)
        if unknown:
            raise StatusError(
                "broker transport vocabulary order_senders are not registered "
                f"symbols: {sorted(unknown)!r}"
            )
        if not self.order_senders:
            raise StatusError(
                "broker transport vocabulary registers no "
                f"{_BROKER_SYMBOL_ORDER_SENDER}; the fail-closed census tier "
                "would have nothing to enforce"
            )
        expected = _compile_broker_construction(self.symbols)
        if self.construction.pattern != expected.pattern:
            raise StatusError(
                "broker transport construction pattern is not derived from "
                f"symbols {list(self.symbols)!r}"
            )


def _broker_symbols_markdown_rows(path: Path, text: str) -> list[dict[str, str]]:
    if _BROKER_SYMBOLS_MARKER not in text:
        raise StatusError(f"{path}: missing {_BROKER_SYMBOLS_MARKER!r}")
    head, _, body = text.partition(_BROKER_SYMBOLS_MARKER)
    marker_line_no = head.count("\n") + 1
    # NIT-3: stop at the next section rather than running to EOF, so a table added
    # under a later heading is not silently absorbed into this registry.
    section_end = _BROKER_SYMBOLS_SECTION_END.search(body)
    if section_end is not None:
        body = body[: section_end.start()]
    parsed: list[dict[str, str]] = []
    for offset, line in enumerate(body.splitlines()):
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if (
            tuple(cells) == _BROKER_SYMBOLS_HEADER_CELLS
            or _TABLE_SEPARATOR_ROW.fullmatch(stripped) is not None
        ):
            continue
        if len(cells) != len(_BROKER_SYMBOLS_MIRROR_COLUMNS):
            # Same discipline as the evidence mirrors: a malformed row is never
            # dropped, because GFM renders surplus cells invisibly.
            raise StatusError(
                f"{path}: line {marker_line_no + offset}: broker symbol table row "
                f"has {len(cells)} cells, expected "
                f"{len(_BROKER_SYMBOLS_MIRROR_COLUMNS)}: {stripped}"
            )
        parsed.append(dict(zip(_BROKER_SYMBOLS_MIRROR_COLUMNS, cells, strict=True)))
    if not parsed:
        raise StatusError(f"{path}: broker symbol table contains no rows")
    return parsed


def _validate_broker_symbols_mirror(
    markdown_path: Path, rows: Sequence[Mapping[str, str]]
) -> None:
    """Check CSV/Markdown parity rather than assuming it, as the other registers do."""
    try:
        text = markdown_path.read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise StatusError(f"missing canonical input: {markdown_path}") from exc
    prose = _normalized_prose(text)
    for marker in _BROKER_SYMBOLS_STANDING_MARKERS:
        if _normalized_prose(marker) not in prose:
            raise StatusError(f"{markdown_path}: missing standing marker {marker!r}")
    parsed = _broker_symbols_markdown_rows(markdown_path, text)
    expected = [
        {field: row[field] for field in _BROKER_SYMBOLS_MIRROR_COLUMNS} for row in rows
    ]
    if parsed != expected:
        raise StatusError(
            f"{markdown_path}: CSV/Markdown broker symbol mismatch; "
            f"markdown={parsed!r}, csv={expected!r}"
        )


def load_broker_transport_symbols(
    csv_path: Path, markdown_path: Path
) -> BrokerTransportVocabulary:
    """Derive the reverse-census vocabulary from its governed corpus registry.

    Fail-closed throughout: a missing file, an empty registry, a malformed row,
    an unknown ``kind``, a non-identifier symbol, a Markdown mirror that has
    drifted, or a registry that registers no order sender all raise.  The scan
    must never quietly degrade into looking for nothing.
    """
    rows = _read_csv(csv_path, REQUIRED_BROKER_SYMBOL_FIELDS)
    if not rows:
        raise StatusError(
            f"{csv_path}: broker transport registry is empty; the reverse census "
            "would scan for nothing"
        )
    errors: list[str] = []
    seen: set[str] = set()
    for line_no, row in enumerate(rows, start=2):
        symbol = row["symbol"]
        label = symbol or "<unnamed>"
        for field in REQUIRED_BROKER_SYMBOL_FIELDS:
            if not row[field]:
                errors.append(f"line {line_no} {label}: empty {field}")
        if symbol and not _BROKER_SYMBOL_NAME.fullmatch(symbol):
            errors.append(
                f"line {line_no}: symbol {symbol!r} is not a bare Python identifier"
            )
        if symbol in seen:
            errors.append(f"line {line_no}: duplicate symbol {symbol!r}")
        seen.add(symbol)
        if row["kind"] not in _BROKER_SYMBOL_KINDS:
            errors.append(
                f"line {line_no} {label}: unknown kind {row['kind']!r}; expected one "
                f"of {sorted(_BROKER_SYMBOL_KINDS)!r}"
            )
        if row["authority_state"] != _BROKER_SYMBOL_AUTHORITY_STATE:
            errors.append(
                f"line {line_no} {label}: authority_state must be "
                f"{_BROKER_SYMBOL_AUTHORITY_STATE}"
            )
        if row["capability_reference"] and not _BROKER_SYMBOL_DECISION.search(
            row["capability_reference"]
        ):
            errors.append(
                f"line {line_no} {label}: capability_reference cites no ADR-nnn-nnn "
                f"identifier: {row['capability_reference']!r}"
            )
    if errors:
        raise StatusError(f"{csv_path}:\n  " + "\n  ".join(errors))

    order_senders = frozenset(
        row["symbol"] for row in rows if row["kind"] == _BROKER_SYMBOL_ORDER_SENDER
    )
    if not order_senders:
        raise StatusError(
            f"{csv_path}: no {_BROKER_SYMBOL_ORDER_SENDER} symbol is registered; the "
            "fail-closed census tier would have nothing to enforce"
        )
    _validate_broker_symbols_mirror(markdown_path, rows)
    symbols = tuple(row["symbol"] for row in rows)
    return BrokerTransportVocabulary(
        symbols=symbols,
        order_senders=order_senders,
        construction=_compile_broker_construction(symbols),
        cited_decisions=frozenset(
            identifier
            for row in rows
            for identifier in _BROKER_SYMBOL_DECISION.findall(
                row["capability_reference"]
            )
        ),
    )


@dataclass(frozen=True)
class BrokerConstructionSite:
    relative_path: str
    classes: frozenset[str]
    is_entrypoint: bool


def _reverse_scan_source_is_eligible(relative_path: str) -> bool:
    """True if ``relative_path`` is within the reverse census's filters.

    Shared by the git-aware universe and the ``os.walk`` fallback below so the
    two paths cannot drift: every path component -- directories and the file
    name alike -- must avoid ``_REVERSE_SCAN_SKIPPED_DIRS`` and a leading
    ``.``, and the file itself must be a ``*.py`` file that is neither
    ``test_*.py`` nor ``conftest.py``.
    """
    parts = relative_path.split("/")
    if any(
        part in _REVERSE_SCAN_SKIPPED_DIRS or part.startswith(".") for part in parts
    ):
        return False
    file_name = parts[-1]
    if not file_name.endswith(".py"):
        return False
    return not (file_name.startswith("test_") or file_name == "conftest.py")


def _reverse_scan_git_universe(repo_root: Path) -> tuple[str, ...]:
    """Return the git-aware census universe: every file git does not ignore.

    The universe is every file git does *not* consider ignored: tracked files
    plus untracked-but-not-ignored files, via
    ``git ls-files --cached --others --exclude-standard``.  This keeps a
    gitignored local checkout -- a vendored SDK, say -- out of census input
    while still scanning a brand-new untracked top-level package, so the scan
    still cannot go blind the way a hardcoded route range would.

    Raises ``StatusError`` -- never silently substitutes another universe --
    when ``git`` is not on ``PATH``, the invocation otherwise fails (a
    nonzero exit, most commonly because ``repo_root`` is not a git work
    tree), or a path in the output cannot be decoded.  The census this feeds
    is what ``validate_broker_symbols_are_grounded`` uses to decide whether a
    registered broker symbol is real; silently substituting a
    ``.gitignore``-blind ``os.walk`` universe on git failure would let a
    gitignored decoy definition satisfy that check.  A caller that
    deliberately wants the non-authoritative walk universe asks for it
    explicitly via ``_iter_reverse_scan_sources(..., universe="walk")``
    instead of going through this function.
    """
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            capture_output=True,
            check=False,
            cwd=repo_root,
        )
    except FileNotFoundError as exc:
        raise StatusError("reverse census universe: git executable not found") from exc
    except OSError as exc:
        raise StatusError(
            f"reverse census universe: git invocation failed: {exc}"
        ) from exc
    if result.returncode != 0:
        stderr_lines = result.stderr.decode("utf-8", errors="replace").splitlines()
        detail = stderr_lines[0] if stderr_lines else "<no stderr output>"
        raise StatusError(
            "reverse census universe: git ls-files failed "
            f"(rc={result.returncode}): {detail}"
        )
    paths: list[str] = []
    for chunk in result.stdout.split(b"\x00"):
        if not chunk:
            continue
        try:
            paths.append(chunk.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise StatusError(
                f"reverse census universe: undecodable path in git output: {chunk!r}"
            ) from exc
    return tuple(paths)


def _iter_reverse_scan_sources(
    repo_root: Path, *, universe: Literal["git", "walk"] = "git"
) -> Iterator[tuple[str, str]]:
    """Yield ``(relative_path, text)`` for every file the reverse census covers.

    ``universe="git"`` (the default, and the only mode the authoritative
    ``--check`` path uses) requires every file git does not consider ignored
    (tracked plus untracked-but-not-ignored), via ``git ls-files --cached
    --others --exclude-standard``.  This is not an allowlist -- a brand-new
    untracked top-level package is still scanned automatically, so the scan
    cannot go blind the way a hardcoded route range does -- but it does mean
    a gitignored local checkout (a vendored SDK, say) is never census input.
    When git fails (not a work tree, ``git`` missing, or the call otherwise
    fails) this mode raises ``StatusError`` rather than silently substituting
    a ``.gitignore``-blind universe.

    ``universe="walk"`` is an explicit, non-authoritative opt-in for a
    synthetic corpus or fixture tree with no git repository at all: a
    directory-pruned ``os.walk`` that knows nothing about ``.gitignore``.
    Any other value raises ``ValueError``.

    Both modes apply the identical filters, via
    ``_reverse_scan_source_is_eligible``, so they cannot drift: skip a
    skipped or dot-prefixed directory (or file), keep only ``*.py``, and skip
    ``test_*.py`` and ``conftest.py``.  Both the construction scan and the
    definition anchor below walk exactly this set, which is what makes the
    anchor meaningful -- a symbol is grounded in the same tree the census is
    able to observe.
    """
    if universe == "git":
        for relative_path in sorted(
            path
            for path in _reverse_scan_git_universe(repo_root)
            if _reverse_scan_source_is_eligible(path)
        ):
            path = repo_root / relative_path
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                # A file may be in the git index (or newly untracked) but
                # absent or unreadable in the worktree; skip it rather than
                # fail the whole scan closed over one path.
                continue
            yield relative_path, text
        return
    if universe != "walk":
        raise ValueError(f"unknown reverse scan universe: {universe!r}")

    for dir_path, dir_names, file_names in os.walk(repo_root):
        dir_names[:] = sorted(
            name
            for name in dir_names
            if name not in _REVERSE_SCAN_SKIPPED_DIRS and not name.startswith(".")
        )
        for file_name in sorted(file_names):
            path = Path(dir_path) / file_name
            relative_path = path.relative_to(repo_root).as_posix()
            if not _reverse_scan_source_is_eligible(relative_path):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            yield relative_path, text


def scan_broker_construction_sites(
    repo_root: Path,
    vocabulary: BrokerTransportVocabulary,
    *,
    universe: Literal["git", "walk"] = "git",
) -> tuple[BrokerConstructionSite, ...]:
    """Find every non-TOS, non-test source file that constructs a broker client.

    ``vocabulary`` comes from the corpus registry, so a brand-new broker symbol
    is scanned for without touching this file.

    ``universe`` is forwarded to ``_iter_reverse_scan_sources`` verbatim; see
    that function for what ``"git"`` (the default, authoritative mode) and
    ``"walk"`` (an explicit, non-authoritative opt-in) mean.

    Known blind spot: only a bare ``Symbol(`` construction is matched.  Dotted or
    indirect construction (``module.Symbol(cfg)``, an aliased import, a factory
    that returns one) is not seen, by the same ``(?<![\\w.])`` guard that keeps
    attribute access from producing false positives.  The register documents this
    rather than implying the scan is complete.
    """
    sites: list[BrokerConstructionSite] = []
    for relative_path, text in _iter_reverse_scan_sources(repo_root, universe=universe):
        found: set[str] = set()
        for line in text.splitlines():
            stripped = line.lstrip()
            # A ``class <RegisteredSymbol>(...)`` definition is not a
            # construction.
            if stripped.startswith(("#", "class ")):
                continue
            found.update(
                match.group("name") for match in vocabulary.construction.finditer(line)
            )
        if found:
            sites.append(
                BrokerConstructionSite(
                    relative_path,
                    frozenset(found),
                    _ENTRYPOINT_GUARD.search(text) is not None,
                )
            )
    return tuple(sites)


def scan_broker_symbol_definitions(
    repo_root: Path,
    vocabulary: BrokerTransportVocabulary,
    *,
    universe: Literal["git", "walk"] = "git",
) -> dict[str, tuple[str, ...]]:
    """Map each registered symbol to the files that actually define it as a class.

    ``universe`` is forwarded to ``_iter_reverse_scan_sources`` verbatim; see
    that function for what ``"git"`` (the default, authoritative mode) and
    ``"walk"`` (an explicit, non-authoritative opt-in) mean.
    """
    definition = _compile_broker_definition(vocabulary.symbols)
    found: dict[str, list[str]] = {symbol: [] for symbol in vocabulary.symbols}
    for relative_path, text in _iter_reverse_scan_sources(repo_root, universe=universe):
        for match in definition.finditer(text):
            sites = found[match.group("name")]
            if relative_path not in sites:
                sites.append(relative_path)
    return {symbol: tuple(sites) for symbol, sites in found.items()}


def validate_broker_symbols_are_grounded(
    repo_root: Path,
    csv_path: Path,
    vocabulary: BrokerTransportVocabulary,
    *,
    universe: Literal["git", "walk"] = "git",
) -> dict[str, tuple[str, ...]]:
    """Require every registered symbol to resolve to a real class definition.

    Without this the registry is self-attesting -- the same defect class as an
    ``AUTHORITY-STATUS.csv`` row that declares its own authority.  Every other
    guard on the registry validates its *syntax*: non-empty, mirrored, well-known
    ``kind``, bare identifier, pinned ``authority_state``.  None of them looks at
    whether the name denotes anything, so a decoy symbol that exists nowhere in
    the repo satisfies all of them and the blocking tier then enforces a rule
    about a class that does not exist -- reporting a confident green.  The
    standing rule is structure-derived over self-reported.

    Two deliberate choices:

    * A symbol defined in **more than one** file passes.  Multiplicity is not
      evidence of absence, and failing on it would assert a uniqueness claim the
      registry never makes; the defining files are returned so a caller can say
      what was found.
    * A symbol defined **only under a test or under** ``tos/`` **fails**, because
      the anchor tree is deliberately the same tree the census scans.  A symbol
      the census could never observe in deployed code is not a transport binding
      of this deployment, and a test file would otherwise be a trivial place to
      plant an anchor for a decoy.

    ``universe`` is forwarded to ``scan_broker_symbol_definitions`` verbatim;
    see ``_iter_reverse_scan_sources`` for what ``"git"`` (the default,
    authoritative mode) and ``"walk"`` (an explicit, non-authoritative
    opt-in) mean.
    """
    definitions = scan_broker_symbol_definitions(
        repo_root, vocabulary, universe=universe
    )
    undefined = sorted(symbol for symbol, sites in definitions.items() if not sites)
    if undefined:
        raise StatusError(
            f"{csv_path}: registered broker transport symbol(s) resolve to no class "
            f"definition outside tos/ and tests: {undefined!r}; a registry entry "
            "that denotes nothing would make the census enforce a rule about a "
            "class that does not exist"
        )
    return definitions


def validate_broker_symbol_citations(
    source_root: Path, csv_path: Path, vocabulary: BrokerTransportVocabulary
) -> None:
    """Require each cited decision identifier to resolve to a real document.

    Only the identifier is checked.  ``capability_reference`` prose -- which
    section, and whether the section says what the row claims -- is not
    machine-checkable, and a checker that pretended otherwise would be
    manufacturing an assurance it cannot supply.
    """
    missing = sorted(
        identifier
        for identifier in vocabulary.cited_decisions
        if not any(source_root.rglob(f"{identifier}-*.md"))
    )
    if missing:
        raise StatusError(
            f"{csv_path}: capability_reference cites decision document(s) that do "
            f"not exist: {missing!r}"
        )


def validate_legacy_route_reverse_census(
    repo_root: Path,
    csv_path: Path,
    registered_components: frozenset[str],
    vocabulary: BrokerTransportVocabulary,
    *,
    warning_exempt_components: frozenset[str] = frozenset(),
    universe: Literal["git", "walk"] = "git",
) -> tuple[str, ...]:
    """Look for broker-order routes that nobody registered.

    ``universe`` is forwarded to ``scan_broker_construction_sites`` verbatim;
    see ``_iter_reverse_scan_sources`` for what ``"git"`` (the default,
    authoritative mode) and ``"walk"`` (an explicit, non-authoritative
    opt-in) mean.

    Fail-closed tier: an *operator- or service-invocable* entrypoint that
    constructs a registered ``ORDER_SENDER`` symbol must be a registered
    ``LEGACY_ROUTE`` component.  That is the F6 defect class verbatim --
    MIGRATION-CONFORMANCE-REGISTER §2 scopes it to "operator-invocable paths
    that reach a real broker" -- and it is exactly what ``flatten_all.py``
    tripped.

    Warning tier: every other unregistered construction of a registered symbol is
    returned, not raised.  A ``BROKER_CLIENT_READ`` symbol is equally the
    market-data read client, and LEGACY-005 explicitly records that "multiple
    construction callers remain" for the shared sender without enumerating them,
    so failing on those would assert a completeness claim the register does not
    make.  See the report accompanying this check for what that does not catch.

    The two tiers take **different** exemption sets, and that asymmetry is the
    point.  ``registered_components`` (LEGACY_ROUTE) exempts both tiers, because
    a legacy order route is a known, registered way to reach a real broker.
    ``warning_exempt_components`` (BROKER_READ_SITE and MOCK_CONFINED_ORDER_SITE)
    exempts the warning tier only: those rows say "this site constructs no
    invocable order sender today", and the fail-closed tier is precisely what
    keeps that statement honest tomorrow.  Registering a read site therefore
    documents it without disarming anything -- silencing a warning must never be
    a way to buy immunity from the blocking check.
    """
    unregistered_senders: list[str] = []
    unregistered: list[str] = []
    warning_exempt = registered_components | warning_exempt_components
    for site in scan_broker_construction_sites(
        repo_root, vocabulary, universe=universe
    ):
        # The fail-closed tier is evaluated *before* and independently of the
        # warning exemption, and consults ``registered_components`` only.  An
        # earlier shape tested it after a ``continue`` on the exemption set,
        # which meant that registering a read site to silence its warning also
        # bought it permanent immunity from the blocking tier -- the warning
        # would go quiet and the guard would go with it.  A BROKER_READ_SITE or
        # MOCK_CONFINED_ORDER_SITE row therefore silences the warning and
        # nothing else: let one of those files grow an invocable entrypoint
        # around an order sender and this still raises.
        if (
            site.is_entrypoint
            and site.classes & vocabulary.order_senders
            and site.relative_path not in registered_components
        ):
            unregistered_senders.append(site.relative_path)
        if site.relative_path not in warning_exempt:
            unregistered.append(site.relative_path)
    if unregistered_senders:
        raise StatusError(
            f"{csv_path}: unregistered broker-order route(s); every invocable "
            f"{'/'.join(sorted(vocabulary.order_senders))} construction site must "
            f"be a registered LEGACY_ROUTE component: {unregistered_senders!r}"
        )
    return tuple(unregistered)


def validate_migration_conformance(
    repo_root: Path,
    csv_path: Path,
    markdown_path: Path,
    vocabulary: BrokerTransportVocabulary,
) -> tuple[int, int, tuple[str, ...]]:
    """Validate package coverage and non-authorizing migration/Q6 honesty.

    Returns ``(migration_census, broker_site_census, unregistered_broker_sites)``.
    """
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
        "BROKER_READ_SITE",
        "MOCK_CONFINED_ORDER_SITE",
        "OPERATOR_VIEW",
        "TOS_PACKAGE",
        "COMPLEXITY_DECOMMISSION",
    }
    if set(by_category) != expected_categories:
        raise StatusError(f"{csv_path}: migration category set is incomplete")
    for category, prefix in (
        ("LEGACY_ROUTE", "LEGACY"),
        ("BROKER_READ_SITE", "READ"),
        ("MOCK_CONFINED_ORDER_SITE", "MOCK"),
    ):
        observed = by_category[category]
        expected_block = {
            f"{prefix}-{number:03}" for number in range(1, len(observed) + 1)
        }
        if observed != expected_block:
            raise StatusError(
                f"{csv_path}: {category} census must be a contiguous "
                f"{prefix}-001..{prefix}-{len(observed):03} block, "
                f"got {sorted(observed)!r}"
            )
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

    def _components(category: str) -> set[str]:
        """Resolve one category's component paths, requiring each to exist."""
        components: set[str] = set()
        for row in (row for row in rows if row["category"] == category):
            component = row["component"].split(maxsplit=1)[0]
            if not (repo_root / component).is_file():
                raise StatusError(
                    f"{csv_path}: {row['record_id']} source path is missing: "
                    f"{repo_root / component}"
                )
            components.add(component)
        return components

    registered_components = _components("LEGACY_ROUTE")
    # Warning-tier only.  See validate_legacy_route_reverse_census for why these
    # deliberately do not join the fail-closed exemption set.
    read_site_components = _components("BROKER_READ_SITE")
    mock_site_components = _components("MOCK_CONFINED_ORDER_SITE")
    # The two warning-only categories are not interchangeable: a read site
    # asserts it constructs no order sender at all, while a mock-confined site
    # asserts it constructs one that is merely non-invocable.  Letting a path
    # hold both rows would let the weaker READ description stand in for the
    # MOCK one and quietly dilute the stricter record.
    category_overlap = read_site_components & mock_site_components
    if category_overlap:
        raise StatusError(
            f"{csv_path}: component(s) registered as both BROKER_READ_SITE and "
            f"MOCK_CONFINED_ORDER_SITE: {sorted(category_overlap)!r}; a site "
            "constructs an order sender or it does not"
        )
    warning_exempt_components = read_site_components | mock_site_components
    overlap = registered_components & warning_exempt_components
    if overlap:
        raise StatusError(
            f"{csv_path}: component(s) registered in both the fail-closed-exempt "
            f"LEGACY_ROUTE census and a warning-only census: {sorted(overlap)!r}"
        )
    unregistered_broker_sites = validate_legacy_route_reverse_census(
        repo_root,
        csv_path,
        frozenset(registered_components),
        vocabulary,
        warning_exempt_components=frozenset(warning_exempt_components),
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
        *by_category["BROKER_READ_SITE"],
        *by_category["MOCK_CONFINED_ORDER_SITE"],
        *by_category["COMPLEXITY_DECOMMISSION"],
    }:
        if record_id not in markdown:
            raise StatusError(f"{markdown_path}: missing register row {record_id}")
    # ``migration_rows`` counts the migration census proper -- the current-to-target
    # records the register was created to hold.  BROKER_READ_SITE and
    # MOCK_CONFINED_ORDER_SITE rows are a construction-site census sharing the same
    # machine source: they migrate nothing and are reported separately, so this
    # number stays comparable across the addition instead of silently jumping.
    migration_census = sum(
        len(by_category[category])
        for category in (
            "LEGACY_ROUTE",
            "OPERATOR_VIEW",
            "TOS_PACKAGE",
            "COMPLEXITY_DECOMMISSION",
        )
    )
    broker_site_census = len(by_category["BROKER_READ_SITE"]) + len(
        by_category["MOCK_CONFINED_ORDER_SITE"]
    )
    if migration_census + broker_site_census != len(rows):
        raise StatusError(
            f"{csv_path}: census split does not account for every row "
            f"({migration_census} + {broker_site_census} != {len(rows)})"
        )
    return migration_census, broker_site_census, unregistered_broker_sites


def collect_status(repo_root: Path) -> StatusSnapshot:
    source_root = repo_root / "tos-spec/src"
    documents, adrs = load_document_states(source_root)
    part1 = load_evidence_register(repo_root / PART1_CSV, "Part 1")
    development = load_evidence_register(repo_root / DEV_CSV, "Parts 2/3 development")
    validate_markdown_mirror(repo_root / PART1_MD, part1)
    validate_markdown_mirror(repo_root / DEV_MD, development)
    authorities = load_authorities(repo_root / AUTHORITY_CSV, source_root)
    direct_traceability_count, direct_traceability_total = validate_direct_traceability(
        source_root, part1, repo_root / TRACEABILITY_MD
    )
    profile_total, profile_null_keys = _load_profile_key_census(repo_root)
    transcription_sites = validate_count_transcriptions(
        source_root,
        part1,
        development,
        extra_derived={
            "direct_traceability.count": direct_traceability_count,
            "direct_traceability.total": direct_traceability_total,
            "profile.total": profile_total,
            "profile.null": profile_null_keys,
        },
    )
    profile_plan_warning = profile_baseline_plan_warning(
        repo_root, profile_total, profile_null_keys
    )
    p2_carried_questions = validate_p2_dispositions(
        repo_root / P2_DISPOSITION_CSV, repo_root / P2_DISPOSITION_MD
    )
    validate_investment_operating_model(repo_root / IOM_PROFILE_SCHEMA, development)
    broker_vocabulary = load_broker_transport_symbols(
        repo_root / BROKER_SYMBOLS_CSV, repo_root / BROKER_SYMBOLS_MD
    )
    # The registry's syntax is validated above; these two validate its referents.
    # Without them the registry is self-attesting and a decoy symbol passes green.
    validate_broker_symbols_are_grounded(
        repo_root, repo_root / BROKER_SYMBOLS_CSV, broker_vocabulary
    )
    validate_broker_symbol_citations(
        source_root, repo_root / BROKER_SYMBOLS_CSV, broker_vocabulary
    )
    (
        migration_rows,
        broker_site_rows,
        unregistered_broker_sites,
    ) = validate_migration_conformance(
        repo_root,
        repo_root / MIGRATION_CSV,
        repo_root / MIGRATION_MD,
        broker_vocabulary,
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
        direct_traceability_total,
        unregistered_broker_sites,
        p2_carried_questions,
        const003_result,
        migration_rows,
        broker_site_rows,
        transcription_sites,
        tuple(sorted(broker_vocabulary.order_senders)),
        profile_total,
        profile_null_keys,
        profile_plan_warning,
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
                f"direct_traceability={snapshot.direct_traceability_count}"
                f"/{snapshot.direct_traceability_total}, "
                f"source_gap_adrs={len(_SOURCE_GAP_ADRS)}, "
                f"p2_carried={snapshot.p2_carried_questions}, "
                f"CONST-003={snapshot.const003_result}, "
                f"migration_rows={snapshot.migration_rows}, "
                f"broker_sites={snapshot.broker_site_rows}, "
                f"count_transcriptions={snapshot.transcription_sites}, "
                f"profile_keys={snapshot.profile_total}, "
                f"profile_null_keys={snapshot.profile_null_keys}, "
                f"restricted_live={snapshot.authorities['restricted_live']}, "
                f"production={snapshot.authorities['production']}"
            )
            if snapshot.unregistered_broker_sites:
                print(
                    "  reverse-scan WARNING (non-blocking): "
                    f"{len(snapshot.unregistered_broker_sites)} broker-client "
                    "construction site(s) outside tos/ and tests are in no "
                    "migration-register census (LEGACY_ROUTE, BROKER_READ_SITE, "
                    "MOCK_CONFINED_ORDER_SITE); none is an invocable "
                    f"{'/'.join(snapshot.order_sender_symbols)} entrypoint: "
                    + ", ".join(snapshot.unregistered_broker_sites)
                )
            if snapshot.profile_plan_warning:
                print(
                    f"  baseline-plan WARNING (non-blocking): {snapshot.profile_plan_warning}"
                )
    except (OSError, StatusError) as exc:
        print(f"TOS spec status FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
