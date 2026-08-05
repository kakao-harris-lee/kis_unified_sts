"""Focused tests for the deterministic TOS status consistency check."""

from __future__ import annotations

import csv
import importlib.util
import re
import shutil
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "tools" / "tos_spec_status.py"


def _load_status_module():
    spec = importlib.util.spec_from_file_location("tos_spec_status", _MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


status = _load_status_module()


def _row(**overrides: str) -> dict[str, str]:
    row = dict.fromkeys(status.REQUIRED_EVIDENCE_FIELDS, "value")
    row.update(
        evidence_id="TEST-EV-001",
        status="NOT_IMPLEMENTED",
        implementation_owner="TBD",
        evidence_owner="TBD",
        independent_reviewer="TBD",
        verification_profile_version="TBD",
        broker_capability_profile_version="N/A",
        latest_run_id="",
        latest_result_date="",
        evidence_location="",
        notes="",
    )
    row.update(overrides)
    return row


def _write_register(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=status.REQUIRED_EVIDENCE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


_MIRROR_COLUMNS = (
    "evidence_id",
    "domain",
    "title",
    "primary_adr",
    "minimum_evidence_level",
    "status",
    "implementation_owner",
    "independent_reviewer",
)


def _mirror_row(row: dict[str, str]) -> str:
    return "| " + " | ".join(row[field] for field in _MIRROR_COLUMNS) + " |"


def _write_mirror(
    path: Path,
    rows: list[dict[str, str]],
    summary: list[str],
    *,
    extra_rows: list[str] | None = None,
) -> None:
    lines = [
        "# Register mirror",
        "",
        "## Status Summary",
        "",
        *summary,
        "",
        "## Register",
        "",
        "| ID | Domain | Test | ADR | Minimum level | Status | Owner | Reviewer |",
        "|---|---|---|---|---|---|---|---|",
        *(_mirror_row(row) for row in rows),
        *(extra_rows or []),
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _mirror_pair(
    tmp_path: Path,
    rows: list[dict[str, str]],
    summary: list[str],
    *,
    extra_rows: list[str] | None = None,
) -> tuple[Path, object]:
    csv_path = tmp_path / "register.csv"
    _write_register(csv_path, rows)
    register = status.load_evidence_register(csv_path, "test")
    markdown_path = tmp_path / "register.md"
    _write_mirror(markdown_path, rows, summary, extra_rows=extra_rows)
    return markdown_path, register


_ADR_025_REL = "part-1-foundation/ADR-002-025-Restricted-Live-Governance.md"
_PART1_MD_REL = "part-1-foundation/verification/EVIDENCE-REGISTER-002.md"
_DEV_MD_REL = "part-3-development/verification/EVIDENCE-REGISTER-DEV.md"
_MIGRATION_MD_REL = "MIGRATION-CONFORMANCE-REGISTER.md"


def _authority_corpus(
    tmp_path: Path,
    *,
    restricted_live: str = "NOT_AUTHORIZED",
    production: str = "NOT_AUTHORIZED",
    production_headers: dict[str, str] | None = None,
    adr_status: str = "Proposed",
    restricted_source: str | None = None,
    production_source: str | None = None,
) -> tuple[Path, Path]:
    """Lay down the minimal corpus shape ``load_authorities`` dereferences."""
    source_root = tmp_path / "tos-spec/src"
    headers = production_headers or {}
    for rel in (_PART1_MD_REL, _DEV_MD_REL, _MIGRATION_MD_REL):
        path = source_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "# register\n\n"
            f"- **Production Authorization:** {headers.get(rel, 'NO')}\n",
            encoding="utf-8",
        )
    adr = source_root / _ADR_025_REL
    adr.parent.mkdir(parents=True, exist_ok=True)
    adr.write_text(f"# ADR-002-025\n\n- **Status:** {adr_status}\n", encoding="utf-8")

    csv_path = source_root / "AUTHORITY-STATUS.csv"
    rows = [
        {
            "axis": "restricted_live",
            "status": restricted_live,
            "governing_source": restricted_source or f"{_ADR_025_REL} §29",
            "change_authority": "System Owner",
            "notes": "no grant recorded",
        },
        {
            "axis": "production",
            "status": production,
            "governing_source": (
                production_source or f"{_PART1_MD_REL} Production Authorization header"
            ),
            "change_authority": "System Owner",
            "notes": "production remains fail-closed",
        },
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=status.REQUIRED_AUTHORITY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return csv_path, source_root


def _transcription_corpus(tmp_path: Path) -> Path:
    """Copy only the registered transcription sources into a scratch corpus."""
    source_root = tmp_path / "tos-spec/src"
    for relative in sorted(
        {entry.relative_path for entry in status._COUNT_TRANSCRIPTIONS}
    ):
        destination = source_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(_REPO_ROOT / "tos-spec/src" / relative, destination)
    return source_root


def _real_registers() -> tuple[object, object]:
    part1 = status.load_evidence_register(_REPO_ROOT / status.PART1_CSV, "Part 1")
    development = status.load_evidence_register(
        _REPO_ROOT / status.DEV_CSV, "Parts 2/3 development"
    )
    return part1, development


# --------------------------------------------------------------------------
# Broker transport vocabulary: a governed corpus input, never a tool literal.
# --------------------------------------------------------------------------

_BROKER_MIRROR_HEADER = "| " + " | ".join(status._BROKER_SYMBOLS_HEADER_CELLS) + " |"

# The real registry's symbols, named here as an explicit floor.  A test may name
# a broker class; the tool may not.  See the reverse canary below.
_REAL_BROKER_SYMBOLS = frozenset({"OrderExecutor", "KISClient"})


def _symbol_row(symbol: str, kind: str, **overrides: str) -> dict[str, str]:
    row = {
        "symbol": symbol,
        "kind": kind,
        "transport_role": "fixture-transport-role",
        "capability_reference": "ADR-002-004 §8",
        "binding_rationale": "fixture deployment binding row",
        "authority_state": "NON_AUTHORIZING_OPEN",
    }
    row.update(overrides)
    return row


def _write_broker_registry(
    corpus: Path,
    rows: list[dict[str, str]],
    *,
    markdown_rows: list[str] | None = None,
    standing: list[str] | None = None,
    write_markdown: bool = True,
) -> tuple[Path, Path]:
    corpus.mkdir(parents=True, exist_ok=True)
    csv_path = corpus / "BROKER-TRANSPORT-SYMBOLS.csv"
    markdown_path = corpus / "BROKER-TRANSPORT-SYMBOLS.md"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=status.REQUIRED_BROKER_SYMBOL_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    if write_markdown:
        table = (
            markdown_rows
            if markdown_rows is not None
            else [
                "| "
                + " | ".join(
                    row[field] for field in status.REQUIRED_BROKER_SYMBOL_FIELDS
                )
                + " |"
                for row in rows
            ]
        )
        lines = [
            "# Fixture broker transport registry",
            "",
            *(
                standing
                if standing is not None
                else list(status._BROKER_SYMBOLS_STANDING_MARKERS)
            ),
            "",
            status._BROKER_SYMBOLS_MARKER,
            "",
            _BROKER_MIRROR_HEADER,
            "|---|---|---|---|---|---|",
            *table,
            "",
        ]
        markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return csv_path, markdown_path


def _vocabulary(corpus: Path, rows: list[dict[str, str]], **kwargs):
    csv_path, markdown_path = _write_broker_registry(corpus, rows, **kwargs)
    return status.load_broker_transport_symbols(csv_path, markdown_path)


def _real_vocabulary():
    return status.load_broker_transport_symbols(
        _REPO_ROOT / status.BROKER_SYMBOLS_CSV,
        _REPO_ROOT / status.BROKER_SYMBOLS_MD,
    )


def test_current_corpus_is_consistent_and_axes_are_separate():
    snapshot = status.collect_status(_REPO_ROOT)
    rendered = status.render_status(snapshot)

    assert snapshot.documents == {"RATIFIED": 13}
    assert snapshot.adrs == {"PROPOSED": 45}
    assert snapshot.part1.counts == {
        "NOT_IMPLEMENTED": 292,
        "READY": 79,
        "PASS": 1,
    }
    assert snapshot.development.counts == {"NOT_IMPLEMENTED": 118}
    assert snapshot.authorities == {
        "restricted_live": "NOT_AUTHORIZED",
        "production": "NOT_AUTHORIZED",
    }
    # 29/30, not 30/30: ADR-002-002 has no direct Traceability table because no
    # source document allocates a SAFE requirement to it.  The gap is recorded,
    # not papered over -- see the source-gap tests below.
    assert snapshot.direct_traceability_count == 29
    assert snapshot.direct_traceability_total == 30
    assert snapshot.p2_carried_questions == 28
    assert snapshot.const003_result == "INCONCLUSIVE"
    assert snapshot.migration_rows == 53
    # The warning tier is advisory; the fail-closed tier already proved no
    # unregistered site is an invocable order-sending entrypoint.
    assert "shared/execution/executor.py" not in snapshot.unregistered_broker_sites
    # Monotone, not exact: registering a legitimate second broker's order sender
    # must not red CI, while dropping or substituting this one must.
    assert "OrderExecutor" in snapshot.order_sender_symbols
    assert "| Document ratification |" in rendered
    assert "| ADR acceptance |" in rendered
    assert "| Evidence |" in rendered
    assert "| Restricted-live | `NOT_AUTHORIZED` |" in rendered
    assert "| Production authorization | `NOT_AUTHORIZED` |" in rendered


def test_duplicate_evidence_id_is_rejected(tmp_path):
    path = tmp_path / "register.csv"
    _write_register(path, [_row(), _row(title="duplicate")])

    with pytest.raises(status.StatusError, match="duplicate evidence_id TEST-EV-001"):
        status.load_evidence_register(path, "test")


def test_ready_row_requires_assigned_owner_and_reviewer(tmp_path):
    path = tmp_path / "register.csv"
    _write_register(path, [_row(status="READY", evidence_location="evidence/")])

    with pytest.raises(
        status.StatusError, match="READY requires assigned implementation_owner"
    ):
        status.load_evidence_register(path, "test")


def test_pass_row_requires_governed_run_binding(tmp_path):
    path = tmp_path / "register.csv"
    _write_register(
        path,
        [
            _row(
                status="PASS",
                implementation_owner="implementation-team",
                evidence_owner="evidence-owner",
                independent_reviewer="independent-reviewer",
                verification_profile_version="approved-v1",
                evidence_location="evidence/",
            )
        ],
    )

    with pytest.raises(status.StatusError, match="PASS requires latest_run_id"):
        status.load_evidence_register(path, "test")


def test_generated_output_drift_fails_check(tmp_path, monkeypatch):
    output = tmp_path / status.GENERATED_MD
    output.parent.mkdir(parents=True)
    output.write_text("stale\n", encoding="utf-8")
    monkeypatch.setattr(status, "collect_status", lambda _root: object())
    monkeypatch.setattr(status, "render_status", lambda _snapshot: "current\n")

    assert status.main(["--check", "--root", str(tmp_path)]) == 1


def test_document_census_ignores_noncanonical_working_artifacts(tmp_path):
    source_root = tmp_path / "tos-spec/src"
    source_root.mkdir(parents=True)
    (source_root / "RFC-001-example.md").write_text(
        "# RFC\n\n**Status:** Ratified\n", encoding="utf-8"
    )
    (source_root / "ADR-002-001-example.md").write_text(
        "# ADR\n\n**Status:** Proposed\n", encoding="utf-8"
    )
    patch_dir = source_root / "part-1-foundation/patches"
    patch_dir.mkdir(parents=True)
    (patch_dir / "ADR-002-001-Patch-0043.md").write_text(
        "# Non-canonical patch artifact without a status header\n", encoding="utf-8"
    )
    review_dir = source_root / "part-1-foundation/reviews"
    review_dir.mkdir(parents=True)
    (review_dir / "RFC-000-Review-0001.md").write_text(
        "# Non-canonical review artifact without a status header\n", encoding="utf-8"
    )

    documents, adrs = status.load_document_states(source_root)

    assert documents == {"RATIFIED": 1}
    assert adrs == {"PROPOSED": 1}


def test_traceability_table_rejects_undefined_safe_id(tmp_path):
    adr = tmp_path / "ADR-002-999-example.md"
    adr.write_text(
        "# Example\n\n## 1. Requirements Traceability\n\n"
        "| Requirement | Allocation |\n|---|---|\n| SAFE-999 | invented |\n",
        encoding="utf-8",
    )

    with pytest.raises(status.StatusError, match="undefined SAFE IDs"):
        status._traceability_safe_ids(adr, {"SAFE-001"})


def test_p2_register_has_exact_question_census_and_pending_gate():
    carried = status.validate_p2_dispositions(
        _REPO_ROOT / status.P2_DISPOSITION_CSV,
        _REPO_ROOT / status.P2_DISPOSITION_MD,
    )

    assert carried == 28


def test_const003_cannot_complete_from_twelve_rlp_passes_alone():
    rlp = dict.fromkeys(status._EXPECTED_RLP_IDS, "PASS")
    eco = dict.fromkeys(status._EXPECTED_ECO_IDS, "NOT_IMPLEMENTED")

    assert (
        status.evaluate_const003(
            rlp,
            eco,
            profile_approved=True,
            independent_review_complete=True,
        )
        == "INCONCLUSIVE"
    )


def test_const003_pass_requires_both_families_profile_and_review():
    rlp = dict.fromkeys(status._EXPECTED_RLP_IDS, "PASS")
    eco = dict.fromkeys(status._EXPECTED_ECO_IDS, "PASS")

    assert (
        status.evaluate_const003(
            rlp,
            eco,
            profile_approved=True,
            independent_review_complete=True,
        )
        == "PASS"
    )
    assert (
        status.evaluate_const003(
            rlp,
            eco,
            profile_approved=False,
            independent_review_complete=True,
        )
        == "INCONCLUSIVE"
    )


def test_investment_operating_family_is_proposed_and_unexecuted():
    development = status.load_evidence_register(
        _REPO_ROOT / status.DEV_CSV, "Parts 2/3 development"
    )

    status.validate_investment_operating_model(
        _REPO_ROOT / status.IOM_PROFILE_SCHEMA, development
    )
    iom = [row for row in development.rows if row["evidence_id"].startswith("IOM-EV-")]
    assert len(iom) == 8
    assert {row["status"] for row in iom} == {"NOT_IMPLEMENTED"}
    assert {row["verification_profile_version"] for row in iom} == {"IOM-0.1-PROPOSED"}


def test_migration_register_covers_code_packages_and_open_q6():
    rows, broker_sites, unregistered = status.validate_migration_conformance(
        _REPO_ROOT,
        _REPO_ROOT / status.MIGRATION_CSV,
        _REPO_ROOT / status.MIGRATION_MD,
        _real_vocabulary(),
    )

    assert rows == 53
    assert broker_sites == 9
    # The live corpus registers every construction site the scan can see, so the
    # warning tier is empty.  This is an assertion about the register, not about
    # the scan: a new unregistered site must make it fail.
    assert unregistered == ()


# --------------------------------------------------------------------------
# Direct traceability: ADR-002-002's source gap must stay visible.
# --------------------------------------------------------------------------

_GAP_ADR = "ADR-002-002"
_GAP_FAMILY = "RC-EV"
_GAP_MATRIX = (
    "### 5.3 Direct-source gaps (four resolved; one open)\n\n"
    f"| {_GAP_ADR} | {_GAP_FAMILY} | — (none sourced) | **OPEN source gap** — "
    "no source document allocates a SAFE to this ADR. |\n"
    f"| {_GAP_FAMILY} | — (none via bridge; see §5.3 source gap) |\n"
)
_GAP_ADR_TEXT = (
    "# ADR-002-002\n\n**Status:** Proposed\n\n"
    "## 38.1 Requirements Traceability — Source Gap\n\n"
    "This ADR has no direct Requirements Traceability table.\n"
)


class _FakeRegister:
    def __init__(self) -> None:
        self.rows = ({"evidence_id": "RC-EV-001", "primary_adr": _GAP_ADR},)


def _gap_adr(tmp_path: Path, text: str = _GAP_ADR_TEXT) -> Path:
    path = tmp_path / f"{_GAP_ADR}-Example.md"
    path.write_text(text, encoding="utf-8")
    return path


def _assert_source_gap(tmp_path: Path, adr_text: str, matrix: str, expected: str):
    with pytest.raises(status.StatusError, match=expected):
        status._validate_source_gap_traceability(
            _GAP_ADR,
            _gap_adr(tmp_path, adr_text),
            tmp_path / "TRACEABILITY-MATRIX-002.md",
            matrix,
            _FakeRegister(),
        )


def test_recorded_source_gap_passes_when_both_documents_still_record_it(tmp_path):
    status._validate_source_gap_traceability(
        _GAP_ADR,
        _gap_adr(tmp_path),
        tmp_path / "TRACEABILITY-MATRIX-002.md",
        _GAP_MATRIX,
        _FakeRegister(),
    )


def test_source_gap_adr_may_not_silently_regrow_a_direct_table(tmp_path):
    _assert_source_gap(
        tmp_path,
        _GAP_ADR_TEXT + "\n## 39. Requirements Traceability\n\n| SAFE-013 | x |\n",
        _GAP_MATRIX,
        "carries a direct Traceability table again",
    )


def test_source_gap_section_may_not_be_dropped_from_the_adr(tmp_path):
    _assert_source_gap(
        tmp_path,
        "# ADR-002-002\n\n**Status:** Proposed\n\n## 38. Adoption Plan\n",
        _GAP_MATRIX,
        "no longer publishes its",
    )


def test_source_gap_heading_is_recognised_explicitly_not_by_regex_accident():
    # The direct-table regex anchors at end of line, so the gap heading is not a
    # near-miss that could ever be mistaken for a table.
    heading = "## 38.1 Requirements Traceability — Source Gap"
    assert status._TRACEABILITY_HEADING.search(heading) is None
    assert status._SOURCE_GAP_HEADING.search(heading) is not None
    assert status._TRACEABILITY_HEADING.search("## 27.1 Requirements Traceability")


def test_source_gap_adr_declaring_a_depends_on_header_fails(tmp_path):
    _assert_source_gap(
        tmp_path,
        "# ADR-002-002\n\n- **Depends On:** RFC-001 SAFE-013\n\n"
        "## 38.1 Requirements Traceability — Source Gap\n\ntext\n",
        _GAP_MATRIX,
        "now declares a Depends On header",
    )


def test_matrix_dropping_the_open_gap_row_fails(tmp_path):
    _assert_source_gap(
        tmp_path,
        _GAP_ADR_TEXT,
        "### 5.3 Direct-source gaps\n\n"
        f"| {_GAP_FAMILY} | — (none via bridge; see §5.3 source gap) |\n",
        "no longer records an open source gap",
    )


def test_matrix_filling_the_gap_row_with_a_safe_set_fails(tmp_path):
    _assert_source_gap(
        tmp_path,
        _GAP_ADR_TEXT,
        "### 5.3 Direct-source gaps\n\n"
        f"| {_GAP_ADR} | {_GAP_FAMILY} | SAFE-013, SAFE-015 | **OPEN source gap** |\n"
        f"| {_GAP_FAMILY} | — (none via bridge; see §5.3 source gap) |\n",
        "now lists a direct SAFE set",
    )


def test_matrix_reverse_row_may_not_quietly_reach_the_gap_family(tmp_path):
    _assert_source_gap(
        tmp_path,
        _GAP_ADR_TEXT,
        "### 5.3 Direct-source gaps\n\n"
        f"| {_GAP_ADR} | {_GAP_FAMILY} | — (none sourced) | **OPEN source gap** |\n"
        f"| {_GAP_FAMILY} | SAFE-013, SAFE-015 |\n",
        "must stay unreachable through the SAFE→ADR bridge",
    )


def test_direct_table_coverage_summary_is_pinned_to_the_current_census():
    matrix = (_REPO_ROOT / status.TRACEABILITY_MD).read_text(encoding="utf-8-sig")

    assert status._DIRECT_TABLE_SUMMARY in matrix
    assert "29/30" in status._DIRECT_TABLE_SUMMARY
    assert "source gaps: 1" in status._DIRECT_TABLE_SUMMARY


def test_stale_direct_table_summary_fails(tmp_path, monkeypatch):
    matrix = tmp_path / "TRACEABILITY-MATRIX-002.md"
    matrix.write_text(
        "- ADRs with a direct Traceability table: 30/30; source gaps: 0.\n",
        encoding="utf-8",
    )
    part1, _ = _real_registers()

    with pytest.raises(status.StatusError, match="coverage summary is stale"):
        status.validate_direct_traceability(_REPO_ROOT / "tos-spec/src", part1, matrix)


# --------------------------------------------------------------------------
# FAIL-OPEN F6: a hardcoded route range can never discover a new route.
# --------------------------------------------------------------------------


def _migration_copy(tmp_path: Path, replace: tuple[str, str] | None = None):
    csv_path = tmp_path / "MIGRATION-CONFORMANCE-REGISTER.csv"
    markdown_path = tmp_path / "MIGRATION-CONFORMANCE-REGISTER.md"
    csv_text = (_REPO_ROOT / status.MIGRATION_CSV).read_text(encoding="utf-8")
    markdown_text = (_REPO_ROOT / status.MIGRATION_MD).read_text(encoding="utf-8")
    if replace is not None:
        old, new = replace
        csv_text = csv_text.replace(old, new)
        markdown_text = markdown_text.replace(old, new)
    csv_path.write_text(csv_text, encoding="utf-8")
    markdown_path.write_text(markdown_text, encoding="utf-8")
    return csv_path, markdown_path


def test_legacy_census_is_derived_from_the_csv_not_a_hardcoded_range(tmp_path):
    # The corpus grew from LEGACY-001..005 to LEGACY-001..007 with no tool edit.
    csv_path, markdown_path = _migration_copy(tmp_path)

    rows, _, _ = status.validate_migration_conformance(
        _REPO_ROOT, csv_path, markdown_path, _real_vocabulary()
    )

    assert rows == 53


def test_legacy_census_rejects_a_gap_in_the_route_numbering(tmp_path):
    csv_path, markdown_path = _migration_copy(tmp_path, ("LEGACY-007", "LEGACY-009"))

    with pytest.raises(status.StatusError, match="contiguous LEGACY-001..LEGACY-007"):
        status.validate_migration_conformance(
            _REPO_ROOT, csv_path, markdown_path, _real_vocabulary()
        )


def _fake_repo(tmp_path: Path, relative: str, body: str) -> Path:
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return tmp_path


_SENDER_ENTRYPOINT = (
    "from shared.execution.executor import OrderExecutor\n\n\n"
    "def main():\n    return OrderExecutor(config)\n\n\n"
    'if __name__ == "__main__":\n    main()\n'
)


def test_unregistered_order_sending_entrypoint_fails_and_names_the_file(tmp_path):
    repo = _fake_repo(
        tmp_path, "scripts/trading/flatten_everything.py", _SENDER_ENTRYPOINT
    )

    with pytest.raises(status.StatusError) as excinfo:
        status.validate_legacy_route_reverse_census(
            repo, repo / "register.csv", frozenset(), _real_vocabulary()
        )

    assert "scripts/trading/flatten_everything.py" in str(excinfo.value)


def test_registered_order_sending_entrypoint_passes(tmp_path):
    repo = _fake_repo(
        tmp_path, "scripts/trading/flatten_everything.py", _SENDER_ENTRYPOINT
    )

    assert (
        status.validate_legacy_route_reverse_census(
            repo,
            repo / "register.csv",
            frozenset({"scripts/trading/flatten_everything.py"}),
            _real_vocabulary(),
        )
        == ()
    )


def test_reverse_scan_ignores_tos_and_test_sources(tmp_path):
    repo = _fake_repo(tmp_path, "tos/src/tos/egressgw/send.py", _SENDER_ENTRYPOINT)
    _fake_repo(tmp_path, "tests/unit/test_sender.py", _SENDER_ENTRYPOINT)

    assert status.scan_broker_construction_sites(repo, _real_vocabulary()) == ()


def test_reverse_scan_does_not_mistake_a_class_definition_for_a_construction(tmp_path):
    repo = _fake_repo(
        tmp_path,
        "shared/kis/client.py",
        "class KISClient(AsyncSessionMixin):\n    pass\n",
    )

    assert status.scan_broker_construction_sites(repo, _real_vocabulary()) == ()


def test_reverse_scan_reports_non_entrypoint_constructions_without_failing(tmp_path):
    repo = _fake_repo(
        tmp_path,
        "shared/execution/mirror.py",
        "def build():\n    return OrderExecutor(config)\n",
    )

    assert status.validate_legacy_route_reverse_census(
        repo, repo / "register.csv", frozenset(), _real_vocabulary()
    ) == ("shared/execution/mirror.py",)


# --------------------------------------------------------------------------
# Warning-only categories (BROKER_READ_SITE / MOCK_CONFINED_ORDER_SITE) must
# silence the warning tier WITHOUT buying immunity from the fail-closed tier.
#
# The defect these guard against is concrete: an earlier shape of the census
# tested the blocking tier *after* a ``continue`` on the exemption set, so
# registering a read site to quiet its warning also disarmed the blocking check
# for that path forever.  ``shared/execution/mock_mirror.py`` is the live case
# that makes this more than theory -- it constructs a real OrderExecutor and is
# kept out of the blocking tier only by having no ``__main__`` guard.
# --------------------------------------------------------------------------


def test_warning_only_registration_silences_the_warning_tier(tmp_path):
    repo = _fake_repo(
        tmp_path,
        "services/market_ingest/main.py",
        "def build():\n    return KISClient(auth)\n",
    )

    assert (
        status.validate_legacy_route_reverse_census(
            repo,
            repo / "register.csv",
            frozenset(),
            _real_vocabulary(),
            warning_exempt_components=frozenset({"services/market_ingest/main.py"}),
        )
        == ()
    )


def test_warning_only_registration_does_not_exempt_the_fail_closed_tier(tmp_path):
    # HEADLINE.  A registered BROKER_READ_SITE that later grows an invocable
    # entrypoint around an order sender must still fail closed.  If this test
    # ever passes silently, registration has become a way to disarm the census.
    repo = _fake_repo(tmp_path, "services/market_ingest/main.py", _SENDER_ENTRYPOINT)

    with pytest.raises(status.StatusError) as excinfo:
        status.validate_legacy_route_reverse_census(
            repo,
            repo / "register.csv",
            frozenset(),
            _real_vocabulary(),
            warning_exempt_components=frozenset({"services/market_ingest/main.py"}),
        )

    assert "services/market_ingest/main.py" in str(excinfo.value)


def test_mock_confined_site_still_fails_closed_once_it_gains_an_entrypoint(tmp_path):
    # MOCK-001's real shape: an OrderExecutor construction that is currently
    # non-invocable.  Registration records it; adding a ``__main__`` guard must
    # still trip the blocking tier.
    repo = _fake_repo(tmp_path, "shared/execution/mock_mirror.py", _SENDER_ENTRYPOINT)

    with pytest.raises(status.StatusError) as excinfo:
        status.validate_legacy_route_reverse_census(
            repo,
            repo / "register.csv",
            frozenset(),
            _real_vocabulary(),
            warning_exempt_components=frozenset({"shared/execution/mock_mirror.py"}),
        )

    assert "shared/execution/mock_mirror.py" in str(excinfo.value)


def test_legacy_route_registration_still_exempts_both_tiers(tmp_path):
    # Invariant regression for the pre-existing behaviour: a LEGACY_ROUTE row is
    # the one registration that does exempt the blocking tier.  LEGACY-001/002
    # and LEGACY-006 depend on this, so the new asymmetry must not disturb it.
    repo = _fake_repo(tmp_path, "scripts/trading/flatten_all.py", _SENDER_ENTRYPOINT)

    assert (
        status.validate_legacy_route_reverse_census(
            repo,
            repo / "register.csv",
            frozenset({"scripts/trading/flatten_all.py"}),
            _real_vocabulary(),
        )
        == ()
    )


def test_a_new_unregistered_read_site_is_still_reported(tmp_path):
    # The exemption is per-path, not a blanket amnesty for the category.
    repo = _fake_repo(
        tmp_path,
        "services/brand_new_collector/main.py",
        "def build():\n    return KISClient(auth)\n",
    )

    assert status.validate_legacy_route_reverse_census(
        repo,
        repo / "register.csv",
        frozenset(),
        _real_vocabulary(),
        warning_exempt_components=frozenset({"services/market_ingest/main.py"}),
    ) == ("services/brand_new_collector/main.py",)


def test_a_component_may_not_sit_in_both_the_blocking_and_warning_censuses(tmp_path):
    csv_path, markdown_path = _migration_copy(
        tmp_path,
        (
            "READ-007,BROKER_READ_SITE,services/trading/market_data_bootstrap.py",
            "READ-007,BROKER_READ_SITE,scripts/trading/flatten_all.py",
        ),
    )

    with pytest.raises(status.StatusError, match="registered in both"):
        status.validate_migration_conformance(
            _REPO_ROOT, csv_path, markdown_path, _real_vocabulary()
        )


def test_a_component_may_not_hold_both_warning_only_categories(tmp_path):
    # MOCK-001 records an order-sender construction that is merely non-invocable;
    # READ-xxx records that no order sender exists at all.  A path holding both
    # would let the weaker description stand in for the stricter one.
    csv_path, markdown_path = _migration_copy(
        tmp_path,
        (
            "READ-007,BROKER_READ_SITE,services/trading/market_data_bootstrap.py",
            "READ-007,BROKER_READ_SITE,shared/execution/mock_mirror.py",
        ),
    )

    with pytest.raises(
        status.StatusError,
        match="both BROKER_READ_SITE and MOCK_CONFINED_ORDER_SITE",
    ):
        status.validate_migration_conformance(
            _REPO_ROOT, csv_path, markdown_path, _real_vocabulary()
        )


# --------------------------------------------------------------------------
# FAIL-OPEN F6b: a hardcoded *vocabulary* can never discover a second broker.
# --------------------------------------------------------------------------

_ACME = "AcmeBrokerClient"
_ACME_SENDER = "AcmeOrderGateway"


def test_a_second_brokers_client_is_scanned_after_a_registry_edit_alone(tmp_path):
    # The deliverable: registering a fabricated second broker's client is a
    # corpus edit.  If this test ever needs an edit to tools/tos_spec_status.py
    # to pass, the broker-specific coupling has come back.
    vocabulary = _vocabulary(
        tmp_path / "corpus",
        [
            _symbol_row("OrderExecutor", "ORDER_SENDER"),
            _symbol_row("KISClient", "BROKER_CLIENT_READ"),
            _symbol_row(_ACME, "BROKER_CLIENT_READ"),
        ],
    )
    repo = _fake_repo(
        tmp_path / "repo",
        "services/acme_gateway/main.py",
        f"def build():\n    return {_ACME}(config)\n",
    )

    sites = status.scan_broker_construction_sites(repo, vocabulary)

    assert [site.relative_path for site in sites] == ["services/acme_gateway/main.py"]
    assert sites[0].classes == frozenset({_ACME})
    # NOT the decoupling canary.  ``_ACME`` is fabricated, so the tool never
    # contained it and this line cannot regress; it only records that the
    # *fixture* name was not smuggled into the tool to make this test pass.  The
    # canary that can actually fail is the reverse one below, over the symbols the
    # tool really did hardcode.
    assert _ACME not in _MODULE_PATH.read_text(encoding="utf-8")


def test_a_second_brokers_order_sender_reaches_the_blocking_tier(tmp_path):
    # The blocking tier is selected by the ``kind`` column, not by a class name.
    vocabulary = _vocabulary(
        tmp_path / "corpus",
        [_symbol_row(_ACME_SENDER, "ORDER_SENDER")],
    )
    repo = _fake_repo(
        tmp_path / "repo",
        "scripts/trading/acme_flatten.py",
        f"def main():\n    return {_ACME_SENDER}(config)\n\n\n"
        'if __name__ == "__main__":\n    main()\n',
    )

    with pytest.raises(status.StatusError) as excinfo:
        status.validate_legacy_route_reverse_census(
            repo, repo / "register.csv", frozenset(), vocabulary
        )

    assert "scripts/trading/acme_flatten.py" in str(excinfo.value)
    assert _ACME_SENDER in str(excinfo.value)


def test_deregistering_a_symbol_blinds_the_scan_to_it(tmp_path):
    # The mirror image, and the actual proof of decoupling: the checker retains
    # no private knowledge of any broker symbol, so a symbol absent from the
    # registry is not scanned for -- even one it used to hardcode.
    vocabulary = _vocabulary(
        tmp_path / "corpus", [_symbol_row("OrderExecutor", "ORDER_SENDER")]
    )
    repo = _fake_repo(
        tmp_path / "repo",
        "services/reader/main.py",
        "def build():\n    return KISClient(config)\n",
    )

    assert status.scan_broker_construction_sites(repo, vocabulary) == ()


def test_registry_still_seeds_the_vocabulary_the_tool_used_to_hardcode():
    # Monotone, deliberately.  The register claims adding a broker "does not
    # require an edit to the checker"; an exact-equality pin here would have made
    # that claim false end-to-end, because a legitimate second broker would red
    # CI on this assertion.  Additions are free; removal or substitution of a
    # registered symbol still fails, which is the property worth keeping -- and
    # the structural anchor below is what now catches a decoy, so this pin no
    # longer has to do that job.
    vocabulary = _real_vocabulary()

    assert set(vocabulary.symbols) >= _REAL_BROKER_SYMBOLS
    assert "OrderExecutor" in vocabulary.order_senders


def test_no_broker_symbol_appears_anywhere_in_the_checker_source():
    # THE reverse canary.  The forward canary above uses a fabricated name and so
    # can never regress; this one names the symbols the tool actually did
    # hardcode, so re-introducing any of them fails here.
    #
    # The forbidden set is derived from the registry, so it *follows* the registry
    # rather than restating a literal -- register a third broker and the tool is
    # forbidden that name too, with no edit here.  Derivation alone would be
    # weakenable by deleting a registry row, so the explicit floor is asserted
    # first: a test may name a broker class, the tool may not.
    forbidden = set(_real_vocabulary().symbols)
    assert forbidden >= _REAL_BROKER_SYMBOLS

    source = _MODULE_PATH.read_text(encoding="utf-8")
    present = sorted(symbol for symbol in forbidden if symbol in source)

    assert present == [], (
        f"tools/tos_spec_status.py names broker symbol(s) {present!r}; the scan "
        "vocabulary must come only from the registry"
    )


def test_a_registered_symbol_that_defines_nothing_is_rejected(tmp_path):
    # MAJOR-1: the decoy.  Every other guard on the registry validates syntax --
    # non-empty, mirrored, known ``kind``, bare identifier, pinned
    # ``authority_state`` -- and a name that exists nowhere satisfies all of them.
    # Counting rows is not the same as resolving referents.
    vocabulary = _vocabulary(
        tmp_path / "corpus", [_symbol_row("NoSuchSender", "ORDER_SENDER")]
    )
    repo = _fake_repo(
        tmp_path / "repo",
        "services/real/main.py",
        "class OrderExecutor:\n    pass\n",
    )

    with pytest.raises(status.StatusError) as excinfo:
        status.validate_broker_symbols_are_grounded(
            repo, repo / "register.csv", vocabulary
        )

    assert "NoSuchSender" in str(excinfo.value)
    assert "no class definition" in str(excinfo.value)


def test_the_real_registry_symbols_resolve_to_real_class_definitions():
    definitions = status.validate_broker_symbols_are_grounded(
        _REPO_ROOT, _REPO_ROOT / status.BROKER_SYMBOLS_CSV, _real_vocabulary()
    )

    assert definitions["OrderExecutor"] == ("shared/execution/executor.py",)
    assert definitions["KISClient"] == ("shared/kis/client.py",)


def test_a_symbol_defined_only_in_a_test_is_not_grounded(tmp_path):
    # The anchor tree is deliberately the tree the census scans.  A test file
    # would otherwise be a trivial place to plant an anchor for a decoy.
    vocabulary = _vocabulary(
        tmp_path / "corpus", [_symbol_row("TestOnlySender", "ORDER_SENDER")]
    )
    repo = _fake_repo(
        tmp_path / "repo",
        "tests/unit/test_planted.py",
        "class TestOnlySender:\n    pass\n",
    )
    _fake_repo(
        tmp_path / "repo",
        "tos/src/tos/egressgw/planted.py",
        "class TestOnlySender:\n    pass\n",
    )

    with pytest.raises(status.StatusError, match="TestOnlySender"):
        status.validate_broker_symbols_are_grounded(
            repo, repo / "register.csv", vocabulary
        )


def test_a_symbol_defined_in_two_places_is_accepted(tmp_path):
    # Chosen behaviour: multiplicity is not evidence of absence, and rejecting it
    # would assert a uniqueness claim the registry never makes.  Both sites are
    # returned so a caller can say what was found.
    vocabulary = _vocabulary(
        tmp_path / "corpus", [_symbol_row("TwiceDefined", "ORDER_SENDER")]
    )
    repo = _fake_repo(
        tmp_path / "repo", "shared/a/one.py", "class TwiceDefined:\n    pass\n"
    )
    _fake_repo(
        tmp_path / "repo", "shared/b/two.py", "class TwiceDefined(Base):\n    x=1\n"
    )

    definitions = status.validate_broker_symbols_are_grounded(
        repo, repo / "register.csv", vocabulary
    )

    assert definitions["TwiceDefined"] == ("shared/a/one.py", "shared/b/two.py")


def test_a_nested_class_is_not_a_grounding_definition(tmp_path):
    vocabulary = _vocabulary(
        tmp_path / "corpus", [_symbol_row("NestedOnly", "ORDER_SENDER")]
    )
    repo = _fake_repo(
        tmp_path / "repo",
        "shared/a/one.py",
        "class Outer:\n    class NestedOnly:\n        pass\n",
    )

    with pytest.raises(status.StatusError, match="NestedOnly"):
        status.validate_broker_symbols_are_grounded(
            repo, repo / "register.csv", vocabulary
        )


def test_capability_reference_must_cite_a_decision_that_exists(tmp_path):
    vocabulary = _vocabulary(
        tmp_path / "corpus",
        [
            _symbol_row(
                "OrderExecutor", "ORDER_SENDER", capability_reference="ADR-999-999 §1"
            )
        ],
    )

    with pytest.raises(status.StatusError, match="ADR-999-999"):
        status.validate_broker_symbol_citations(
            _REPO_ROOT / "tos-spec/src", tmp_path / "register.csv", vocabulary
        )


def test_capability_reference_without_any_decision_identifier_is_rejected(tmp_path):
    csv_path, markdown_path = _write_broker_registry(
        tmp_path / "corpus",
        [
            _symbol_row(
                "OrderExecutor", "ORDER_SENDER", capability_reference="see the ADR"
            )
        ],
    )

    with pytest.raises(status.StatusError, match="cites no ADR-nnn-nnn"):
        status.load_broker_transport_symbols(csv_path, markdown_path)


def test_vocabulary_type_rejects_an_inert_construction_pattern():
    # MINOR-4: validation lived only in the loader, so the type could be built
    # empty -- and an empty vocabulary makes every scan return green.
    with pytest.raises(status.StatusError, match="has no symbols"):
        status.BrokerTransportVocabulary(
            symbols=(),
            order_senders=frozenset(),
            construction=re.compile(r"(?!)"),
        )


def test_vocabulary_type_rejects_a_pattern_not_derived_from_its_symbols():
    with pytest.raises(status.StatusError, match="not derived from symbols"):
        status.BrokerTransportVocabulary(
            symbols=("OrderExecutor",),
            order_senders=frozenset({"OrderExecutor"}),
            construction=re.compile(r"(?<![\w.])(?P<name>SomethingElse)\s*\("),
        )


def test_vocabulary_type_rejects_an_order_sender_that_is_not_a_symbol():
    with pytest.raises(status.StatusError, match="not registered symbols"):
        status.BrokerTransportVocabulary(
            symbols=("KISClient",),
            order_senders=frozenset({"OrderExecutor"}),
            construction=status._compile_broker_construction(("KISClient",)),
        )


def test_a_later_markdown_section_table_is_not_absorbed(tmp_path):
    # NIT-3: the table scan stops at the next ``##`` instead of running to EOF.
    rows = [_symbol_row("OrderExecutor", "ORDER_SENDER")]
    csv_path, markdown_path = _write_broker_registry(tmp_path / "corpus", rows)
    markdown_path.write_text(
        markdown_path.read_text(encoding="utf-8")
        + "\n## 5. Something else\n\n| A | B |\n|---|---|\n| one | two |\n",
        encoding="utf-8",
    )

    vocabulary = status.load_broker_transport_symbols(csv_path, markdown_path)

    assert vocabulary.symbols == ("OrderExecutor",)


def test_a_symbol_named_symbol_does_not_skip_its_own_row(tmp_path):
    # NIT-4: the header was matched by a ``| Symbol `` prefix, so a symbol
    # literally named ``Symbol`` skipped its own mirror row.
    rows = [_symbol_row("Symbol", "ORDER_SENDER")]
    csv_path, markdown_path = _write_broker_registry(tmp_path / "corpus", rows)

    vocabulary = status.load_broker_transport_symbols(csv_path, markdown_path)

    assert vocabulary.symbols == ("Symbol",)


def test_missing_broker_registry_fails_closed(tmp_path):
    with pytest.raises(status.StatusError, match="missing canonical input"):
        status.load_broker_transport_symbols(
            tmp_path / "absent.csv", tmp_path / "absent.md"
        )


def test_missing_broker_registry_mirror_fails_closed(tmp_path):
    csv_path, markdown_path = _write_broker_registry(
        tmp_path / "corpus",
        [_symbol_row("OrderExecutor", "ORDER_SENDER")],
        write_markdown=False,
    )

    with pytest.raises(status.StatusError, match="missing canonical input"):
        status.load_broker_transport_symbols(csv_path, markdown_path)


def test_empty_broker_registry_fails_closed(tmp_path):
    csv_path, markdown_path = _write_broker_registry(tmp_path / "corpus", [])

    with pytest.raises(status.StatusError, match="registry is empty"):
        status.load_broker_transport_symbols(csv_path, markdown_path)


def test_unknown_broker_symbol_kind_fails_closed(tmp_path):
    csv_path, markdown_path = _write_broker_registry(
        tmp_path / "corpus", [_symbol_row("OrderExecutor", "PROBABLY_FINE")]
    )

    with pytest.raises(status.StatusError, match="unknown kind 'PROBABLY_FINE'"):
        status.load_broker_transport_symbols(csv_path, markdown_path)


def test_registry_without_an_order_sender_fails_closed(tmp_path):
    csv_path, markdown_path = _write_broker_registry(
        tmp_path / "corpus", [_symbol_row("KISClient", "BROKER_CLIENT_READ")]
    )

    with pytest.raises(status.StatusError, match="no ORDER_SENDER symbol"):
        status.load_broker_transport_symbols(csv_path, markdown_path)


def test_empty_broker_registry_cell_fails_closed(tmp_path):
    csv_path, markdown_path = _write_broker_registry(
        tmp_path / "corpus",
        [_symbol_row("OrderExecutor", "ORDER_SENDER", binding_rationale="")],
    )

    with pytest.raises(status.StatusError, match="empty binding_rationale"):
        status.load_broker_transport_symbols(csv_path, markdown_path)


def test_authorizing_broker_registry_row_is_rejected(tmp_path):
    csv_path, markdown_path = _write_broker_registry(
        tmp_path / "corpus",
        [_symbol_row("OrderExecutor", "ORDER_SENDER", authority_state="AUTHORIZED")],
    )

    with pytest.raises(status.StatusError, match="authority_state must be"):
        status.load_broker_transport_symbols(csv_path, markdown_path)


def test_regex_metacharacter_symbol_is_rejected_not_compiled(tmp_path):
    # Rejected explicitly rather than merely escaped: a symbol that is not a bare
    # Python identifier can never be a construction the scan should look for.
    csv_path, markdown_path = _write_broker_registry(
        tmp_path / "corpus", [_symbol_row("Order.*Executor", "ORDER_SENDER")]
    )

    with pytest.raises(status.StatusError, match="not a bare Python identifier"):
        status.load_broker_transport_symbols(csv_path, markdown_path)


def test_broker_registry_csv_markdown_drift_fails_closed(tmp_path):
    rows = [_symbol_row("OrderExecutor", "ORDER_SENDER")]
    csv_path, markdown_path = _write_broker_registry(
        tmp_path / "corpus",
        rows,
        markdown_rows=[
            "| "
            + " | ".join(
                _symbol_row("OrderExecutor", "BROKER_CLIENT_READ")[field]
                for field in status.REQUIRED_BROKER_SYMBOL_FIELDS
            )
            + " |"
        ],
    )

    with pytest.raises(status.StatusError, match="CSV/Markdown broker symbol mismatch"):
        status.load_broker_transport_symbols(csv_path, markdown_path)


def test_broker_registry_markdown_row_with_surplus_cells_is_rejected(tmp_path):
    rows = [_symbol_row("OrderExecutor", "ORDER_SENDER")]
    csv_path, markdown_path = _write_broker_registry(
        tmp_path / "corpus",
        rows,
        markdown_rows=[
            "| "
            + " | ".join(row[field] for field in status.REQUIRED_BROKER_SYMBOL_FIELDS)
            + " | surplus |"
            for row in rows
        ],
    )

    with pytest.raises(status.StatusError, match="has 7 cells, expected 6"):
        status.load_broker_transport_symbols(csv_path, markdown_path)


def test_broker_registry_dropping_its_standing_statement_fails_closed(tmp_path):
    csv_path, markdown_path = _write_broker_registry(
        tmp_path / "corpus",
        [_symbol_row("OrderExecutor", "ORDER_SENDER")],
        standing=["A registry that no longer says what it is."],
    )

    with pytest.raises(status.StatusError, match="missing standing marker"):
        status.load_broker_transport_symbols(csv_path, markdown_path)


# --------------------------------------------------------------------------
# FAIL-OPEN A: AUTHORITY-STATUS.csv must not be able to self-attest authority.
# --------------------------------------------------------------------------


def test_authority_csv_cannot_self_declare_production_authorization(tmp_path):
    csv_path, source_root = _authority_corpus(
        tmp_path, restricted_live="AUTHORIZED", production="AUTHORIZED"
    )

    with pytest.raises(status.StatusError) as excinfo:
        status.load_authorities(csv_path, source_root)

    message = str(excinfo.value)
    assert "AUTHORITY-STATUS.csv" in message
    assert "EVIDENCE-REGISTER-002.md" in message


def test_production_authorized_contradicting_evidence_register_fails(tmp_path):
    csv_path, source_root = _authority_corpus(tmp_path, production="AUTHORIZED")

    with pytest.raises(status.StatusError, match=r"Production Authorization:\*\* NO"):
        status.load_authorities(csv_path, source_root)


def test_restricted_live_authorized_under_proposed_adr_fails(tmp_path):
    csv_path, source_root = _authority_corpus(
        tmp_path, restricted_live="AUTHORIZED", adr_status="Proposed"
    )

    with pytest.raises(status.StatusError, match=r"restricted_live=AUTHORIZED"):
        status.load_authorities(csv_path, source_root)


def test_unresolvable_governing_source_fails_closed(tmp_path):
    csv_path, source_root = _authority_corpus(
        tmp_path,
        production_source="part-1-foundation/verification/DOES-NOT-EXIST.md header",
    )

    with pytest.raises(status.StatusError, match="does not resolve"):
        status.load_authorities(csv_path, source_root)


def test_governing_source_without_document_path_fails_closed(tmp_path):
    csv_path, source_root = _authority_corpus(
        tmp_path, restricted_source="the System Owner said so"
    )

    with pytest.raises(status.StatusError, match="names no resolvable"):
        status.load_authorities(csv_path, source_root)


def test_governing_source_may_not_escape_the_corpus_root(tmp_path):
    csv_path, source_root = _authority_corpus(
        tmp_path, production_source="../../outside.md header"
    )

    with pytest.raises(status.StatusError, match="outside the corpus source root"):
        status.load_authorities(csv_path, source_root)


def test_disagreeing_production_honesty_markers_fail(tmp_path):
    csv_path, source_root = _authority_corpus(
        tmp_path, production_headers={_DEV_MD_REL: "YES"}
    )

    with pytest.raises(status.StatusError, match="disagree"):
        status.load_authorities(csv_path, source_root)


def test_valid_fail_closed_authority_csv_still_passes(tmp_path):
    csv_path, source_root = _authority_corpus(tmp_path)

    assert status.load_authorities(csv_path, source_root) == {
        "restricted_live": "NOT_AUTHORIZED",
        "production": "NOT_AUTHORIZED",
    }


def test_production_authorized_is_accepted_when_the_corpus_says_yes(tmp_path):
    csv_path, source_root = _authority_corpus(
        tmp_path,
        production="AUTHORIZED",
        production_headers={
            _PART1_MD_REL: "YES",
            _DEV_MD_REL: "YES",
            _MIGRATION_MD_REL: "YES",
        },
    )

    assert status.load_authorities(csv_path, source_root)["production"] == "AUTHORIZED"


# --------------------------------------------------------------------------
# FAIL-OPEN B: Markdown summary parity must be bidirectional.
# --------------------------------------------------------------------------


def test_summary_state_absent_from_csv_must_read_zero(tmp_path):
    markdown_path, register = _mirror_pair(
        tmp_path,
        [_row()],
        [
            "- Total evidence items: **1**",
            "- NOT_IMPLEMENTED: **1**",
            "- PASS: **7**",
        ],
    )

    with pytest.raises(status.StatusError, match=r"summary PASS=7, CSV=0"):
        status.validate_markdown_mirror(markdown_path, register)


def test_summary_states_invented_wholesale_are_rejected(tmp_path):
    markdown_path, register = _mirror_pair(
        tmp_path,
        [_row()],
        [
            "- Total evidence items: **1**",
            "- NOT_IMPLEMENTED: **1**",
            "- WAIVED_WITH_RESIDUAL_RISK: **42**",
            "- BLOCKED: **9**",
        ],
    )

    with pytest.raises(status.StatusError) as excinfo:
        status.validate_markdown_mirror(markdown_path, register)

    message = str(excinfo.value)
    assert "WAIVED_WITH_RESIDUAL_RISK=42" in message
    assert "BLOCKED=9" in message


def test_summary_line_with_unknown_state_name_is_rejected(tmp_path):
    markdown_path, register = _mirror_pair(
        tmp_path,
        [_row()],
        [
            "- Total evidence items: **1**",
            "- NOT_IMPLEMENTED: **1**",
            "- FABRICATED: **5**",
        ],
    )

    with pytest.raises(status.StatusError, match="unknown summary state 'FABRICATED'"):
        status.validate_markdown_mirror(markdown_path, register)


def test_summary_omitting_a_populated_state_is_rejected(tmp_path):
    markdown_path, register = _mirror_pair(
        tmp_path, [_row()], ["- Total evidence items: **1**"]
    )

    with pytest.raises(
        status.StatusError, match="missing summary count for NOT_IMPLEMENTED"
    ):
        status.validate_markdown_mirror(markdown_path, register)


def test_summary_count_mismatch_still_fails(tmp_path):
    markdown_path, register = _mirror_pair(
        tmp_path,
        [_row()],
        ["- Total evidence items: **1**", "- NOT_IMPLEMENTED: **0**"],
    )

    with pytest.raises(status.StatusError, match=r"summary NOT_IMPLEMENTED=0, CSV=1"):
        status.validate_markdown_mirror(markdown_path, register)


def test_summary_with_honest_zero_states_passes(tmp_path):
    markdown_path, register = _mirror_pair(
        tmp_path,
        [_row()],
        [
            "- Total evidence items: **1**",
            "- NOT_IMPLEMENTED: **1**",
            "- PASS: **0**",
            "- FAIL: **0**",
            "- INCONCLUSIVE: **0**",
        ],
    )

    status.validate_markdown_mirror(markdown_path, register)


# --------------------------------------------------------------------------
# FAIL-OPEN C: a malformed register row must fail, never be silently dropped.
# --------------------------------------------------------------------------


_FABRICATED_NINE_CELL_ROW = (
    "| FAKE-EV-999 | Fabricated | Looks Governed | ADR-DEV-001 | EV-L3 | PASS "
    "| real-owner | real-reviewer | extra |"
)


def test_nine_cell_register_row_is_rejected(tmp_path):
    markdown_path, register = _mirror_pair(
        tmp_path,
        [_row()],
        ["- Total evidence items: **1**", "- NOT_IMPLEMENTED: **1**"],
        extra_rows=[_FABRICATED_NINE_CELL_ROW],
    )

    with pytest.raises(status.StatusError) as excinfo:
        status._markdown_register_rows(markdown_path)

    message = str(excinfo.value)
    assert "9 cells" in message
    assert "FAKE-EV-999" in message
    assert "line 13" in message


def test_nine_cell_register_row_is_rejected_through_the_mirror_check(tmp_path):
    markdown_path, register = _mirror_pair(
        tmp_path,
        [_row()],
        ["- Total evidence items: **1**", "- NOT_IMPLEMENTED: **1**"],
        extra_rows=[_FABRICATED_NINE_CELL_ROW],
    )

    with pytest.raises(status.StatusError, match="9 cells"):
        status.validate_markdown_mirror(markdown_path, register)


def test_seven_cell_register_row_is_rejected(tmp_path):
    markdown_path, _register = _mirror_pair(
        tmp_path,
        [_row()],
        ["- Total evidence items: **1**", "- NOT_IMPLEMENTED: **1**"],
        extra_rows=["| SHORT-EV-001 | a | b | c | d | PASS | e |"],
    )

    with pytest.raises(status.StatusError, match="7 cells"):
        status._markdown_register_rows(markdown_path)


def test_non_row_lines_are_still_excluded_from_the_register_table(tmp_path):
    markdown_path, register = _mirror_pair(
        tmp_path,
        [_row()],
        ["- Total evidence items: **1**", "- NOT_IMPLEMENTED: **1**"],
        extra_rows=[
            "",
            "Prose after the table that mentions | a pipe | inline.",
            "",
            "## Notes",
            "",
            "- A bullet.",
        ],
    )

    parsed = status._markdown_register_rows(markdown_path)

    assert [row["evidence_id"] for row in parsed] == ["TEST-EV-001"]
    status.validate_markdown_mirror(markdown_path, register)


# --------------------------------------------------------------------------
# FAIL-OPEN D: hand-transcribed register counts must be checked.
# --------------------------------------------------------------------------


_GATE_STATUS_REL = "part-1-foundation/ARCHITECTURE-GATE-STATUS.md"


def test_registered_transcriptions_agree_with_the_real_corpus():
    part1, development = _real_registers()

    checked = status.validate_count_transcriptions(
        _REPO_ROOT / "tos-spec/src", part1, development
    )

    assert checked == len(status._COUNT_TRANSCRIPTIONS)
    assert any(
        entry.relative_path == _GATE_STATUS_REL
        for entry in status._COUNT_TRANSCRIPTIONS
    )


def test_hand_edited_gate_status_counts_are_detected(tmp_path):
    part1, development = _real_registers()
    source_root = _transcription_corpus(tmp_path)
    gate = source_root / _GATE_STATUS_REL
    gate.write_text(
        gate.read_text(encoding="utf-8").replace("118", "999").replace("372", "111"),
        encoding="utf-8",
    )

    with pytest.raises(status.StatusError) as excinfo:
        status.validate_count_transcriptions(source_root, part1, development)

    message = str(excinfo.value)
    assert "ARCHITECTURE-GATE-STATUS.md" in message
    assert "999" in message


def test_missing_architecture_gate_status_file_fails(tmp_path):
    part1, development = _real_registers()
    source_root = _transcription_corpus(tmp_path)
    (source_root / _GATE_STATUS_REL).unlink()

    with pytest.raises(status.StatusError, match="required transcription source"):
        status.validate_count_transcriptions(source_root, part1, development)


def test_deleted_transcription_sentence_fails(tmp_path):
    part1, development = _real_registers()
    source_root = _transcription_corpus(tmp_path)
    gate = source_root / _GATE_STATUS_REL
    kept = [
        line
        for line in gate.read_text(encoding="utf-8").splitlines()
        if not line.startswith("- **Verification Execution:**")
    ]
    gate.write_text("\n".join(kept) + "\n", encoding="utf-8")

    with pytest.raises(status.StatusError, match="transcription anchor not found"):
        status.validate_count_transcriptions(source_root, part1, development)


def test_unedited_transcription_corpus_copy_still_passes(tmp_path):
    part1, development = _real_registers()
    source_root = _transcription_corpus(tmp_path)

    assert status.validate_count_transcriptions(source_root, part1, development) == len(
        status._COUNT_TRANSCRIPTIONS
    )
