"""Focused tests for the deterministic TOS status consistency check."""

from __future__ import annotations

import csv
import importlib.util
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
    assert snapshot.direct_traceability_count == 30
    assert snapshot.p2_carried_questions == 28
    assert snapshot.const003_result == "INCONCLUSIVE"
    assert snapshot.migration_rows == 51
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
    assert (
        status.validate_migration_conformance(
            _REPO_ROOT,
            _REPO_ROOT / status.MIGRATION_CSV,
            _REPO_ROOT / status.MIGRATION_MD,
        )
        == 51
    )
