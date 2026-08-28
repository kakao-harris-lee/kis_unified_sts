"""Unit tests for the EV-L1 evidence run harness (``tools/tos_evidence_run.py``).

Regressions locked here:

  * the seven design #1 §5.1 run-manifest items are all present in the baseline;
  * all 22 VER-002-001 §3 baseline fields are present, and the ones whose
    artifacts do not exist are marked ``NOT_APPLICABLE_EV_L1`` **with a reason**
    rather than fabricated (the honesty property of the whole harness);
  * append-only: an existing run directory is refused and left byte-identical;
  * every sha256 in ``sha256sums.txt`` / the manifest is the real digest, and the
    sums file closes over the manifest;
  * the manifest carries the discipline tag and claims no PASS / no closure.

The module under test lives outside the package tree, so it is loaded from its
file path (same convention as ``test_tos_firewall_check.py``).
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "tools" / "tos_evidence_run.py"

#: A tracked, clean, fast tos test file used as the harness's own target.
_SMOKE_NODE = "tos/tests/test_package.py"


def _load_harness():
    spec = importlib.util.spec_from_file_location("tos_evidence_run", _MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ev = _load_harness()


# --------------------------------------------------------------------------
# hermetic Evidence Register
#
# The harness reads the row's ``status`` out of the Evidence Register and records
# it verbatim (``register_status_at_run_time``) — that reading is the honest part
# and is NOT under test here. What must not leak into a self-test is the *state*
# of the repo's register: a real row legitimately moves (NOT_IMPLEMENTED -> READY
# -> PASS) whenever evidence lands, which would break any expectation pinned to a
# literal. So the self-tests inject their own frozen two-row register via the
# harness's existing ``--register-csv`` argument and assert against that.
#
# The column list below is a drift anchor: ``test_hermetic_register_columns_match
# _the_repo_register`` fails if the real register's header changes shape.
# --------------------------------------------------------------------------

_REGISTER_COLUMNS = (
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

#: The frozen rows the self-tests run against. Only the ids the self-tests use are
#: present, so an id outside this set is "unregistered" exactly as in the real
#: register. ``status`` is pinned to READY: the harness must copy it through.
_REGISTER_ROWS = (
    {
        "evidence_id": "STATE-EV-001",
        "domain": "Orthogonal State",
        "title": "Orthogonal Composite Persistence",
        "primary_adr": "ADR-002-005",
        "criticality": "Critical",
        "minimum_evidence_level": "EV-L1/2",
        "status": "READY",
        "implementation_owner": "ai-impl(claude-orchestrated)",
        "evidence_owner": "operator",
        "independent_reviewer": "ai-review(decorrelated)+operator-countersign",
        "verification_profile_version": "2.1-PROPOSED",
        "broker_capability_profile_version": "N/A",
    },
    {
        "evidence_id": "STATE-EV-004",
        "domain": "Orthogonal State",
        "title": "Conservative Restart Reconstruction",
        "primary_adr": "ADR-002-005",
        "criticality": "Critical",
        "minimum_evidence_level": "EV-L3",
        "status": "READY",
        "implementation_owner": "ai-impl(claude-orchestrated)",
        "evidence_owner": "operator",
        "independent_reviewer": "ai-review(decorrelated)+operator-countersign",
        "verification_profile_version": "2.1-PROPOSED",
        "broker_capability_profile_version": "TBD",
    },
    {
        # present so the EV-L3 continuity gate can be exercised against a REAL package
        # filed under the wrong row (design §6.2 MINOR-2) — STATE-EV-003 is registered
        # at EV-L1/3 in the repo register too.
        "evidence_id": "STATE-EV-003",
        "domain": "Orthogonal State",
        "title": "Cross-Dimension Coupling",
        "primary_adr": "ADR-002-005",
        "criticality": "Critical",
        "minimum_evidence_level": "EV-L1/3",
        "status": "READY",
        "implementation_owner": "ai-impl(claude-orchestrated)",
        "evidence_owner": "operator",
        "independent_reviewer": "ai-review(decorrelated)+operator-countersign",
        "verification_profile_version": "2.1-PROPOSED",
        "broker_capability_profile_version": "N/A",
    },
    {
        "evidence_id": "SPG-EV-002",
        "domain": "Safety Profile Governance",
        "title": "Semantic Units, Numeric, and Cross-Field Validation",
        "primary_adr": "ADR-002-014",
        "criticality": "Critical",
        "minimum_evidence_level": "EV-L1/2",
        "status": "READY",
        "implementation_owner": "ai-impl(claude-orchestrated)",
        "evidence_owner": "operator",
        "independent_reviewer": "ai-review(decorrelated)+operator-countersign",
        "verification_profile_version": "2.1-PROPOSED",
        "broker_capability_profile_version": "N/A",
    },
)

#: What ``_REGISTER_ROWS`` pins the status column to.
_HERMETIC_REGISTER_STATUS = "READY"


def _hermetic_register(
    evidence_root: Path,
    *,
    overrides: dict[str, str] | None = None,
    filename: str = "EVIDENCE-REGISTER-002.csv",
) -> Path:
    """Write the frozen mini register beside ``evidence_root`` and return its path.

    Kept out of the evidence root itself so it never appears inside a run package.
    Writing is idempotent: repeated calls for the same tmp dir rewrite the same
    bytes. ``overrides`` (applied to every row, under its own ``filename``) lets a
    test pin a column to a value the real register cannot hold, which is how the
    injection itself is proved rather than assumed.
    """
    csv_path = evidence_root.parent / "register-fixture" / filename
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(_REGISTER_COLUMNS))
        writer.writeheader()
        for row in _REGISTER_ROWS:
            out = {col: row.get(col, "") for col in _REGISTER_COLUMNS}
            out.update(overrides or {})
            writer.writerow(out)
    return csv_path


def _argv(evidence_root: Path, *, evidence_id: str = "STATE-EV-001") -> list[str]:
    return [
        "--register-csv",
        str(_hermetic_register(evidence_root)),
        "--evidence-id",
        evidence_id,
        "--node",
        f"{_SMOKE_NODE} | harness self-test target (tracked, clean, hermetic)",
        "--primary-adr",
        "ADR-002-005",
        "--design-doc",
        "docs/plans/2026-07-25-tos-orthogonal-state-design.md",
        "--seed-policy",
        "fixed:1234",
        "--evidence-root",
        str(evidence_root),
    ]


@pytest.fixture(scope="module")
def run_dir(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("evidence")
    rc = ev.main(_argv(root))
    assert rc == 0, "the smoke node must be green"
    runs = list((root / "STATE-EV-001").iterdir())
    assert len(runs) == 1
    return runs[0]


@pytest.fixture(scope="module")
def manifest(run_dir: Path) -> dict:
    return yaml.safe_load((run_dir / "manifest.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def baseline(run_dir: Path) -> dict:
    return yaml.safe_load((run_dir / "baseline.yaml").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# package shape
# --------------------------------------------------------------------------


def test_run_package_contains_every_required_artifact(run_dir: Path) -> None:
    assert {p.name for p in run_dir.iterdir()} == {
        "manifest.yaml",
        "baseline.yaml",
        "traceability.csv",
        "junit.xml",
        "run.log",
        "sha256sums.txt",
    }


def test_run_id_is_timestamp_plus_short_sha(run_dir: Path) -> None:
    stamp, _, sha = run_dir.name.partition("-")
    datetime.strptime(stamp, "%Y%m%dT%H%M%SZ")  # raises if malformed
    assert sha and all(c in "0123456789abcdef" for c in sha)


# --------------------------------------------------------------------------
# design #1 §5.1 — the seven items
# --------------------------------------------------------------------------


def test_all_seven_design_5_1_items_are_present(baseline: dict) -> None:
    items = baseline["design1_5_1"]
    assert list(items) == [
        "item_1_repository_and_package",
        "item_2_interpreter_and_dependencies",
        "item_3_execution_environment",
        "item_4_harness_version",
        "item_5_seed_policy",
        "item_6_consumed_configuration_artifacts",
        "item_7_retained_artifact_digests",
    ]


def test_item_1_records_commit_worktree_and_per_file_digests(baseline: dict) -> None:
    item = baseline["design1_5_1"]["item_1_repository_and_package"]
    assert len(item["git_commit_sha"]) == 40
    assert item["tos_package_version"] != ev.NOT_APPLICABLE
    # worktree honesty: the enumeration keys exist even when clean
    for key in ("untracked", "modified_unstaged", "staged", "all_dirty_paths"):
        assert isinstance(item["worktree"][key], list)
    digests = {d["path"]: d for d in item["target_file_digests"]}
    assert _SMOKE_NODE in digests
    actual = hashlib.sha256((_REPO_ROOT / _SMOKE_NODE).read_bytes()).hexdigest()
    assert digests[_SMOKE_NODE]["sha256_before_run"] == actual
    assert digests[_SMOKE_NODE]["sha256_after_run"] == actual
    assert digests[_SMOKE_NODE]["status"] == "STABLE_DURING_RUN"
    assert digests[_SMOKE_NODE]["git_clean"] is True
    assert item["target_files_clean"] is True
    assert item["target_files_stable_during_run"] is True


def test_item_1_watches_the_harness_itself(baseline: dict) -> None:
    """The harness is inside the mutation-watch set (it can rewrite the run)."""
    item = baseline["design1_5_1"]["item_1_repository_and_package"]
    watched = {d["path"]: d for d in item["target_file_digests"]}
    harness = watched["tools/tos_evidence_run.py"]
    assert harness["status"] == "STABLE_DURING_RUN"
    # watched for mutation, but exempt from the cleanliness REFUSAL — otherwise an
    # uncommitted harness could never run; its provenance is recorded in item 4.
    assert harness["cleanliness_guarded"] is False
    assert watched[_SMOKE_NODE]["cleanliness_guarded"] is True


def test_item_1_records_the_worktree_before_and_after(baseline: dict) -> None:
    item = baseline["design1_5_1"]["item_1_repository_and_package"]
    assert "worktree" in item and "worktree_after_run" in item
    delta = item["worktree_delta"]
    assert set(delta) == {
        "became_dirty_during_run",
        "became_clean_during_run",
        "stable",
    }


def test_item_2_measures_installed_versions_not_only_pins(baseline: dict) -> None:
    item = baseline["design1_5_1"]["item_2_interpreter_and_dependencies"]
    for dist in ("pydantic", "hypothesis", "pytest", "numpy", "pandas"):
        assert item["installed_versions_measured"][dist] != "NOT_INSTALLED"
    assert item["pinned_in_tos_pyproject"]
    # drift is reported, never silently reconciled
    for entry in item["pin_vs_installed_drift"]:
        assert entry["pinned"] != entry["installed"]


def test_item_5_seed_policy_is_recorded_as_executed(baseline: dict, manifest) -> None:
    policy = baseline["design1_5_1"]["item_5_seed_policy"]
    assert policy["policy"] == "fixed"
    assert policy["hypothesis_seed"] == 1234
    assert "--hypothesis-seed=1234" in manifest["execution"]["command"]


def test_item_6_absent_config_is_marked_not_applicable(baseline: dict) -> None:
    item = baseline["design1_5_1"]["item_6_consumed_configuration_artifacts"]
    assert item["status"] == ev.NOT_APPLICABLE
    assert item["reason"]


# --------------------------------------------------------------------------
# VER §3 — 22 fields, no fabrication
# --------------------------------------------------------------------------

_VER3_FIELDS = [
    "repository_commit_sha",
    "build_artifact_digest",
    "rfc_adr_versions",
    "hard_safety_envelope_version",
    "runtime_safety_profile_version",
    "human_authority_policy_generation_and_digest",
    "effective_principal_graph_generation_and_digest",
    "evidence_integrity_policy_generation_and_digest",
    "recovery_barrier_policy_generation_and_digest",
    "critical_input_policy_generation_and_digest",
    "venue_constraint_policy_generation_and_digest",
    "trading_approval_policy_generation_and_digest",
    "currentness_policy_generation_and_digest",
    "restricted_live_trial_policy_generation_and_digest",
    "broker_capability_profile_version",
    "verification_profile_version",
    "database_schema_migration_version",
    "deployment_manifest_digest",
    "workload_identities_and_key_versions",
    "environment_identifier",
    "test_harness_version",
    "fault_injection_schedule_and_seed",
]

#: Fields whose artifact does not exist at this stage — they must be N/A, and a
#: future run that starts emitting a value for one of them must fail here first.
_MUST_BE_NOT_APPLICABLE = [
    "build_artifact_digest",
    "hard_safety_envelope_version",
    "runtime_safety_profile_version",
    "human_authority_policy_generation_and_digest",
    "effective_principal_graph_generation_and_digest",
    "evidence_integrity_policy_generation_and_digest",
    "recovery_barrier_policy_generation_and_digest",
    "critical_input_policy_generation_and_digest",
    "venue_constraint_policy_generation_and_digest",
    "trading_approval_policy_generation_and_digest",
    "currentness_policy_generation_and_digest",
    "restricted_live_trial_policy_generation_and_digest",
    "broker_capability_profile_version",
    "database_schema_migration_version",
    "deployment_manifest_digest",
    "workload_identities_and_key_versions",
]


def test_ver3_baseline_carries_all_22_fields_in_order(baseline: dict) -> None:
    ver3 = baseline["ver_002_001_section_3_baseline"]
    assert list(ver3) == _VER3_FIELDS
    assert len(_VER3_FIELDS) == 22


@pytest.mark.parametrize("field", _MUST_BE_NOT_APPLICABLE)
def test_nonexistent_artifacts_are_marked_not_applicable_with_reason(
    baseline: dict, field: str
) -> None:
    entry = baseline["ver_002_001_section_3_baseline"][field]
    assert entry["status"] == ev.NOT_APPLICABLE
    assert entry["reason"], "an N/A field without a reason is an unexplained gap"
    assert "value" not in entry, "an N/A field must carry no fabricated value"


def test_ver3_statuses_are_from_the_closed_vocabulary(baseline: dict) -> None:
    allowed = {ev.RECORDED, ev.NOT_APPLICABLE, ev.PARTIAL}
    for name, entry in baseline["ver_002_001_section_3_baseline"].items():
        assert entry["status"] in allowed, name


def test_seed_field_is_partial_with_fault_schedule_deferred(baseline: dict) -> None:
    entry = baseline["ver_002_001_section_3_baseline"][
        "fault_injection_schedule_and_seed"
    ]
    assert entry["status"] == ev.PARTIAL
    assert entry["value"]["fault_schedule"]["status"] == ev.NOT_APPLICABLE
    assert entry["value"]["seed"]["hypothesis_seed"] == 1234


def test_verification_profile_state_is_derived_from_the_artifact(
    baseline: dict,
) -> None:
    """The recorded approval state must be a re-derivation of the profile on disk.

    The pin is deliberately NOT a literal: a literal is exactly what went stale when
    P0-1 closed on 2026-07-29 and the harness kept writing "PROPOSED — P0-1 open".
    What is locked instead is that every recorded field equals what an independent
    parse of ``VERIFICATION-PROFILE-002.yaml`` yields, and that the digest recorded
    beside them covers those same bytes.
    """
    entry = baseline["ver_002_001_section_3_baseline"]["verification_profile_version"]
    assert entry["status"] == ev.RECORDED
    value = entry["value"]

    profile_path = _REPO_ROOT / ev.PROFILE_YAML_PATH
    doc = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    assert value["profile_status"] == doc["status"]
    assert value["profile_version"] == doc["version"]
    assert value["approved_by"] == doc["approved_by"]
    assert value["effective_from"] == doc["effective_from"]
    assert (
        value["artifact"]["sha256"]
        == hashlib.sha256(profile_path.read_bytes()).hexdigest()
    )

    # the null-key census is a count of the artifact, not a number the harness knows
    expected_nulls = sorted(
        [k for k, v in doc["bounds"].items() if v.get("value_ms") is None]
        + [k for k, v in doc["limits"].items() if v is None]
    )
    assert value["unapproved_null_key_names"] == expected_nulls
    assert value["unapproved_null_keys"] == len(expected_nulls)
    assert value["numeric_keys_total"] == len(doc["bounds"]) + len(doc["limits"])

    # the human-readable label must be built from those same parsed parts
    assert value["profile_version"] in value["version"]
    assert value["profile_status"] in value["approval_state"]
    assert str(value["unapproved_null_keys"]) in value["approval_state"]


def test_verification_profile_version_is_not_the_register_column(
    baseline: dict,
) -> None:
    """Two independent sources, not one copied twice.

    The injected hermetic register pins ``2.1-PROPOSED`` in its column while the repo
    profile derives ``2.1``; if the harness ever started echoing the register column
    as the profile's version, these would collapse into one value.
    """
    value = baseline["ver_002_001_section_3_baseline"]["verification_profile_version"][
        "value"
    ]
    assert value["register_column_value"] == "2.1-PROPOSED"
    # atom against atom: ``version`` is a built sentence and would differ from the
    # column even if the harness DID echo it, so the comparison that actually
    # discriminates is the parsed version field against the copied column.
    assert value["profile_version"] != value["register_column_value"]
    assert value["version"] != value["register_column_value"]


# --------------------------------------------------------------------------
# Verification Profile approval — fail-closed derivation
#
# Negative coverage for ``read_profile_approval``. The happy path above proves the
# harness re-derives the repo's real state; what matters at least as much is that a
# profile it CANNOT read never yields an approved-looking record. Every case below
# builds a throwaway repo root, so none of them touches the real corpus.
# --------------------------------------------------------------------------


def _profile_repo(tmp_path: Path, text: str | None) -> Path:
    """A repo root carrying only a profile at the harness's expected relative path.

    ``text is None`` leaves the file absent (the FILE_ABSENT branch).
    """
    target = tmp_path / ev.PROFILE_YAML_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    if text is not None:
        target.write_text(text, encoding="utf-8")
    return tmp_path


def _assert_fail_closed(approval: dict) -> None:
    """Every unknown record must be unknown in EVERY limb, and approved in none."""
    assert approval["status"] == ev.PROFILE_APPROVAL_UNKNOWN
    assert approval["version"] == ev.PROFILE_APPROVAL_UNKNOWN
    assert approval["version_label"] == ev.PROFILE_APPROVAL_UNKNOWN
    assert approval["approval_state"] == ev.PROFILE_APPROVAL_UNKNOWN
    assert approval["p0_1_bounds_approval"] == ev.PROFILE_APPROVAL_UNKNOWN
    assert approval["approved_by"] == []
    assert approval["effective_from"] == ""
    assert approval["unreadable_reason"], "an UNKNOWN without a reason is unexplained"
    # The load-bearing polarity: no CLAIM-bearing field may read as an approval. The
    # diagnostic ``unreadable_reason`` is excluded on purpose — it quotes what was
    # found (which may itself be the word APPROVED) and asserts nothing.
    claims = {k: v for k, v in approval.items() if k != "unreadable_reason"}
    assert "APPROVED" not in yaml.safe_dump(claims, allow_unicode=True)
    assert "CLOSED" not in yaml.safe_dump(claims, allow_unicode=True).replace(
        "fail-closed", ""
    )


_APPROVED_PROFILE = """
profile_id: VERIFICATION-PROFILE-002
version: "9.9"
status: APPROVED
approved_by: ["test-approver"]
effective_from: "2030-01-02"
review_due: "2031-01-02"
bounds:
  B_ok: {value_ms: 100}
  B_null: {value_ms: null}
limits:
  MAX_ok: 5
  MIN_null: null
"""


def test_profile_approval_derives_an_approved_profile(tmp_path: Path) -> None:
    approval = ev.read_profile_approval(_profile_repo(tmp_path, _APPROVED_PROFILE))
    assert approval["status"] == "APPROVED"
    assert approval["version"] == "9.9"
    assert approval["approved_by"] == ["test-approver"]
    assert approval["effective_from"] == "2030-01-02"
    assert approval["numeric_keys_total"] == 4
    assert approval["unapproved_null_keys"] == 2
    assert approval["unapproved_null_key_names"] == ["B_null", "MIN_null"]
    assert approval["p0_1_bounds_approval"].startswith("CLOSED 2030-01-02")
    # scope-limitation is never dropped: the residual null keys are stated in the
    # same sentence that reports the approval
    assert "2 of 4" in approval["version_label"]
    assert "2 of 4" in approval["approval_state"]


def test_profile_approval_keeps_the_open_wording_while_status_is_proposed(
    tmp_path: Path,
) -> None:
    """The pre-P0-1 wording is a *derived* branch, not a deleted one — a profile that
    reverts to PROPOSED re-produces the historical claim byte for byte."""
    text = _APPROVED_PROFILE.replace("status: APPROVED", "status: PROPOSED")
    approval = ev.read_profile_approval(_profile_repo(tmp_path, text))
    assert approval["status"] == "PROPOSED"
    assert approval["version_label"] == "9.9 (PROPOSED — P0-1 open)"
    assert approval["approval_state"] == "PROPOSED — P0-1 (bounds approval) OPEN"
    assert approval["p0_1_bounds_approval"] == "OPEN"


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param(None, id="file-absent"),
        pytest.param("bounds: [unclosed\n  - :\n\t bad", id="yaml-parse-error"),
        pytest.param("- just\n- a\n- list\n", id="not-a-mapping"),
        pytest.param(
            _APPROVED_PROFILE.replace("status: APPROVED", "status: RATIFIED"),
            id="status-outside-vocabulary",
        ),
        pytest.param(
            _APPROVED_PROFILE.replace("status: APPROVED", "status: null"),
            id="status-absent",
        ),
        pytest.param(
            _APPROVED_PROFILE.replace('version: "9.9"', "version: null"),
            id="version-unusable",
        ),
        pytest.param(
            _APPROVED_PROFILE.replace('approved_by: ["test-approver"]', "approved_by:"),
            id="approved-without-approver",
        ),
        pytest.param(
            _APPROVED_PROFILE.replace(
                'effective_from: "2030-01-02"', "effective_from:"
            ),
            id="approved-without-effective-from",
        ),
        pytest.param(
            _APPROVED_PROFILE.replace("  B_ok: {value_ms: 100}", "  B_ok: 100"),
            id="bounds-entry-not-a-mapping",
        ),
        pytest.param(
            _APPROVED_PROFILE.replace(
                "  B_ok: {value_ms: 100}", "  B_ok: {semantics: hard_maximum}"
            ),
            id="bounds-entry-without-value-ms",
        ),
        pytest.param(
            _APPROVED_PROFILE.replace("  MAX_ok: 5", "  MAX_ok: {nested: 1}"),
            id="limits-entry-is-a-mapping",
        ),
        pytest.param(
            _APPROVED_PROFILE.replace("  MAX_ok: 5", "  MAX_ok: true"),
            id="limits-entry-is-a-bool",
        ),
        pytest.param(
            _APPROVED_PROFILE.replace(
                "bounds:\n  B_ok: {value_ms: 100}\n  B_null: {value_ms: null}\n",
                "bounds: {}\n",
            ),
            id="empty-bounds-census",
        ),
        pytest.param(
            _APPROVED_PROFILE.replace(
                "limits:\n  MAX_ok: 5\n  MIN_null: null\n", "limits: {}\n"
            ),
            id="empty-limits-census",
        ),
        pytest.param(
            _APPROVED_PROFILE + "status: PROPOSED\n",
            id="duplicate-status-key",
        ),
        pytest.param(
            _APPROVED_PROFILE.replace("bounds:", "bounds: []").replace(
                "  B_ok: {value_ms: 100}\n  B_null: {value_ms: null}\n", ""
            ),
            id="bounds-section-not-a-mapping",
        ),
    ],
)
def test_profile_approval_fails_closed_to_unknown(
    tmp_path: Path, mutation: str | None
) -> None:
    _assert_fail_closed(ev.read_profile_approval(_profile_repo(tmp_path, mutation)))


def test_unreadable_profile_still_records_the_digest_it_could_compute(
    tmp_path: Path,
) -> None:
    """UNKNOWN suppresses the CLAIM, never the evidence: an unparseable file is still
    digested, so a reviewer can identify the exact bytes that defeated the parse."""
    bad = "bounds: [unclosed\n  - :\n\t bad"
    approval = ev.read_profile_approval(_profile_repo(tmp_path, bad))
    assert (
        approval["digest"]["sha256"] == hashlib.sha256(bad.encode("utf-8")).hexdigest()
    )
    absent = ev.read_profile_approval(_profile_repo(tmp_path / "empty", None))
    assert absent["digest"]["sha256"] == "FILE_ABSENT"


def test_unreadable_profile_reason_reaches_the_recorded_baseline_reason() -> None:
    """The UNKNOWN branch must explain itself in the field a reader actually reads."""
    unknown = ev._profile_unknown({"path": "p", "sha256": "x"}, "synthetic failure")
    reason = ev.profile_version_reason(unknown)
    assert "UNKNOWN" in reason and "synthetic failure" in reason
    assert "approved" not in reason.replace("No approval is implied", "")


def test_profile_bytes_are_read_exactly_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The digest and the parse MUST come from one buffer (concurrent-writer sim).

    A two-read implementation (digest the file, then reopen it to parse) can record a
    sha256 of bytes it never parsed. Here the byte source mutates on every access, so
    a second read would be observable: the recorded digest would cover the APPROVED
    payload while the recorded status came from the PROPOSED one — a package whose own
    digest does not cover its own approval claim.
    """
    repo = _profile_repo(tmp_path, _APPROVED_PROFILE)
    second = _APPROVED_PROFILE.replace("status: APPROVED", "status: PROPOSED").replace(
        'version: "9.9"', 'version: "0.0"'
    )
    payloads = [_APPROVED_PROFILE.encode("utf-8"), second.encode("utf-8")]
    reads: list[int] = []
    real_read_bytes = Path.read_bytes

    def mutating_read_bytes(self: Path) -> bytes:
        if self == repo / ev.PROFILE_YAML_PATH:
            reads.append(1)
            # every access hands back the NEXT payload; a single-read impl sees only
            # payloads[0], a two-read impl sees payloads[1] on its second access
            return payloads[min(len(reads) - 1, len(payloads) - 1)]
        return real_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", mutating_read_bytes)
    # a reintroduced ``sha256_file(path)`` would reopen the file behind our back, so
    # the helper is made explosive for the duration of the call
    monkeypatch.setattr(
        ev,
        "sha256_file",
        lambda *a, **k: pytest.fail("read_profile_approval must not re-open the file"),
    )
    approval = ev.read_profile_approval(repo)

    assert len(reads) == 1, f"profile bytes were read {len(reads)} times, must be 1"
    assert approval["digest"]["sha256"] == hashlib.sha256(payloads[0]).hexdigest()
    # the decisive cross-check: digest and parse describe the SAME payload
    assert approval["status"] == "APPROVED"
    assert approval["version"] == "9.9"


def test_discipline_tags_cannot_contradict_the_derived_state(manifest: dict) -> None:
    """MAJOR-1: one artifact may not refute itself.

    The tag used to hardcode "P0-1 (bounds approval) closes" while the claim block
    carries a profile-derived ``p0_1_bounds_approval``. Once P0-1 closed those two
    stated opposite things inside a single manifest.
    """
    for name in ("DISCIPLINE_TAG", "DISCIPLINE_TAG_L2", "DISCIPLINE_TAG_L3"):
        tag = getattr(ev, name)
        assert "P0-1" not in tag, f"{name} re-asserts a gate the claim block derives"
    tag = manifest["discipline_tag"]
    claim = manifest["claim"]
    assert "P0-1" not in tag
    # the tag must POINT at the derived fields rather than restate them
    assert "p0_1_bounds_approval" in tag
    assert claim["p0_1_bounds_approval"]
    assert (
        claim["verification_profile_status"]
        == ev.read_profile_approval(_REPO_ROOT)["status"]
    )


def test_l2_discipline_tag_matches_the_design_errata_verbatim() -> None:
    """The EV-L2 tag is design-owned text; the harness copy must equal the errata.

    The errata (EV-L2 pilot design §12, v1.3) quotes the replacement string. If either
    side is edited alone they drift, which is how design-owned strings rot.
    """
    design = (
        _REPO_ROOT / "docs" / "plans" / "2026-07-29-tos-ev-l2-pilot-design.md"
    ).read_text(encoding="utf-8")
    flat = " ".join(design.replace(">", " ").split())
    assert (
        " ".join(ev.DISCIPLINE_TAG_L2.split()) in flat
    ), "DISCIPLINE_TAG_L2 is not quoted verbatim by its design errata"
    # the errata is ADDITIVE: the superseded wording stays in the document as record
    assert "coverage argument + P0-1 + independent review" in flat


def test_harness_hardcodes_no_verification_profile_version() -> None:
    """Anti-phantom, both directions: the self-reported constant is gone (not merely
    unused), and no profile version literal survives anywhere in the harness."""
    assert not hasattr(ev, "VERIFICATION_PROFILE_VERSION")
    source = _MODULE_PATH.read_text(encoding="utf-8")
    assert "VERIFICATION_PROFILE_VERSION" not in source
    profile_version = yaml.safe_load(
        (_REPO_ROOT / ev.PROFILE_YAML_PATH).read_text(encoding="utf-8")
    )["version"]
    assert profile_version not in source, (
        f"the harness hardcodes the profile version {profile_version!r}; "
        "it must be derived at run time"
    )


def test_baseline_declares_its_own_ev_l1_only_completeness(baseline: dict) -> None:
    text = baseline["contract"]["completeness"]
    assert ev.NOT_APPLICABLE in text
    assert "EV-L2" in text  # states it is NOT a complete baseline above EV-L1


# --------------------------------------------------------------------------
# discipline: no PASS, no closure
# --------------------------------------------------------------------------


def test_manifest_carries_the_discipline_tag(manifest: dict) -> None:
    assert manifest["discipline_tag"] == ev.DISCIPLINE_TAG
    assert "not a row PASS" in manifest["discipline_tag"]
    assert "VER §9.5" in manifest["discipline_tag"]


def test_manifest_claims_no_closure_and_no_pass(manifest: dict) -> None:
    claim = manifest["claim"]
    assert claim["closes_evidence_item"] is False
    assert claim["register_status_moved_by_this_run"] is False
    assert claim["independent_review"].startswith("NOT_SIGNED")
    assert manifest["execution"]["outcome"] == "ALL_SELECTED_TESTS_GREEN"
    assert "PASS" not in manifest["execution"]["outcome"]


def test_manifest_records_the_junit_summary_and_rc(manifest: dict) -> None:
    assert manifest["execution"]["return_code"] == 0
    junit = manifest["execution"]["junit_summary"]
    assert junit["tests"] >= 1
    assert junit["failures"] == 0 and junit["errors"] == 0
    # VER §9.3 — wall clock AND monotonic sequencing
    assert manifest["execution"]["started_utc"].endswith("+00:00")
    assert isinstance(manifest["execution"]["monotonic_duration_s"], float)


def test_traceability_maps_every_node_with_its_basis(run_dir: Path) -> None:
    with open(run_dir / "traceability.csv", newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    row = rows[0]
    assert row["evidence_id"] == "STATE-EV-001"
    assert row["primary_adr"] == "ADR-002-005"
    assert row["test_node"] == _SMOKE_NODE
    assert row["mapping_basis"] and row["mapping_basis"] != "UNSPECIFIED"
    assert "does not close" in row["evidence_claim"]


# --------------------------------------------------------------------------
# VER §9.2 — artifact hashing accuracy
# --------------------------------------------------------------------------


def test_sha256sums_covers_every_file_and_is_accurate(run_dir: Path) -> None:
    sums = {}
    for line in (run_dir / "sha256sums.txt").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        sums[name] = digest
    on_disk = {p.name for p in run_dir.iterdir() if p.name != "sha256sums.txt"}
    assert set(sums) == on_disk
    assert "manifest.yaml" in sums, "the sums file must close over the manifest"
    for name, digest in sums.items():
        assert digest == hashlib.sha256((run_dir / name).read_bytes()).hexdigest()


def test_manifest_artifact_digests_are_accurate(manifest: dict, run_dir: Path) -> None:
    for entry in manifest["artifacts"]:
        path = run_dir / entry["name"]
        assert entry["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert entry["bytes"] == path.stat().st_size
    assert (
        manifest["baseline"]["sha256"]
        == hashlib.sha256((run_dir / "baseline.yaml").read_bytes()).hexdigest()
    )


# --------------------------------------------------------------------------
# VER §9.1 — append-only
# --------------------------------------------------------------------------


def test_existing_run_directory_is_refused_and_left_untouched(
    tmp_path, monkeypatch
) -> None:
    frozen = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(ev, "_utc_now", lambda: frozen)

    root = tmp_path / "evidence"
    assert ev.main(_argv(root)) == 0
    created = next((root / "STATE-EV-001").iterdir())
    before = {p.name: p.read_bytes() for p in created.iterdir()}

    assert ev.main(_argv(root)) == 2, "a second run at the same run-id must refuse"

    after = {p.name: p.read_bytes() for p in created.iterdir()}
    assert after == before, "an existing run package must be byte-identical"


def test_create_run_directory_refuses_an_existing_directory(tmp_path) -> None:
    target = tmp_path / "EV" / "run"
    ev.create_run_directory(target)
    with pytest.raises(ev.HarnessError, match="append-only"):
        ev.create_run_directory(target)


# --------------------------------------------------------------------------
# fail-closed preconditions
# --------------------------------------------------------------------------


def test_unregistered_evidence_id_is_refused(tmp_path) -> None:
    rc = ev.main(_argv(tmp_path / "e", evidence_id="NOPE-EV-999"))
    assert rc == 2
    assert not (tmp_path / "e").exists(), "no package for an unregistered item"


# --------------------------------------------------------------------------
# the injected register (hermeticity of the self-tests themselves)
# --------------------------------------------------------------------------


def test_the_injected_register_is_the_one_read_and_recorded(tmp_path: Path) -> None:
    """``--register-csv`` is honoured, and the baseline names the file it read.

    This is what makes the register-derived expectations in this module hermetic:
    the status the harness copies through comes from the injected file, and the
    recorded provenance is that file — not the default constant.
    """
    # a title the repo register cannot hold: if the harness silently read its
    # default path instead, the recorded row would carry the real title
    marker = "harness self-test fixture row (never the repo register's title)"
    injected = _hermetic_register(
        tmp_path / "e",
        overrides={"title": marker},
        filename="EVIDENCE-REGISTER-002-injection-probe.csv",
    )
    root = tmp_path / "e"
    assert ev.main([*_argv(root), "--register-csv", str(injected)]) == 0
    run = next((root / "STATE-EV-001").iterdir())
    baseline = yaml.safe_load((run / "baseline.yaml").read_text(encoding="utf-8"))
    manifest = yaml.safe_load((run / "manifest.yaml").read_text(encoding="utf-8"))

    row = baseline["evidence_register_row"]
    assert row["source"] == str(injected)
    assert row["title"] == marker, "the harness read a register it was not given"
    assert row["status_at_run_time"] == _HERMETIC_REGISTER_STATUS
    assert manifest["claim"]["register_status_at_run_time"] == (
        _HERMETIC_REGISTER_STATUS
    )
    # the default is unchanged: no injection means the repo register
    defaults = ev.build_parser().parse_args(
        ["--evidence-id", "STATE-EV-001", "--node", _SMOKE_NODE]
    )
    assert defaults.register_csv == ev.REGISTER_CSV_PATH


def test_hermetic_register_columns_match_the_repo_register() -> None:
    """Drift anchor: the fixture must keep the real register's column shape."""
    register = _REPO_ROOT / ev.REGISTER_CSV_PATH
    if not register.is_file():
        pytest.skip("evidence register not present")
    with open(register, newline="", encoding="utf-8-sig") as fh:
        header = next(csv.reader(fh))
    assert tuple(header) == _REGISTER_COLUMNS


def test_missing_test_node_is_refused(tmp_path) -> None:
    rc = ev.main(
        [
            "--evidence-id",
            "STATE-EV-001",
            "--node",
            "tos/tests/does_not_exist.py",
            "--evidence-root",
            str(tmp_path / "e"),
        ]
    )
    assert rc == 2


def test_dirty_target_file_is_refused_by_default(tmp_path, monkeypatch) -> None:
    """A dirty executed file would make the recorded commit describe other bytes."""
    real = ev.worktree_status

    def _dirty(repo_root):
        status = real(repo_root)
        status["clean"] = False
        status["modified_unstaged"] = sorted(
            {*status["modified_unstaged"], _SMOKE_NODE}
        )
        status["all_dirty_paths"] = sorted({*status["all_dirty_paths"], _SMOKE_NODE})
        return status

    monkeypatch.setattr(ev, "worktree_status", _dirty)
    assert ev.main(_argv(tmp_path / "e")) == 2

    # ...and is recorded in-band, not hidden, when explicitly allowed
    rc = ev.main([*_argv(tmp_path / "e2"), "--allow-dirty-targets"])
    assert rc == 0
    run = next((tmp_path / "e2" / "STATE-EV-001").iterdir())
    data = yaml.safe_load((run / "baseline.yaml").read_text(encoding="utf-8"))
    item = data["design1_5_1"]["item_1_repository_and_package"]
    assert item["target_files_clean"] is False


def test_bad_seed_policy_is_refused(tmp_path) -> None:
    rc = ev.main([*_argv(tmp_path / "e"), "--seed-policy", "fixed:abc"])
    assert rc == 2


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def test_porcelain_first_line_keeps_its_leading_status_column() -> None:
    """Regression: the leading blank of an unstaged entry is column-significant.

    Stripping ``git status --porcelain`` output shifts the *first* line one
    column left, which both mis-classifies it as staged and truncates its path's
    first character — and a truncated path never matches an executed file, so
    the dirty-target guard would fail OPEN for exactly that file.
    """
    raw = "\0".join(
        [
            " M tos-spec/register.csv",
            "M  staged.py",
            "MM both.py",
            "?? new/file with space.py",
            "R  renamed.py",
            "old.py",  # the rename source field — must not be read as an entry
            "",
        ]
    )
    status = ev.parse_porcelain(raw)
    assert status["modified_unstaged"] == ["both.py", "tos-spec/register.csv"]
    assert status["staged"] == ["both.py", "renamed.py", "staged.py"]
    assert status["untracked"] == ["new/file with space.py"]
    assert "old.py" not in status["all_dirty_paths"]
    assert "tos-spec/register.csv" in status["all_dirty_paths"]
    assert status["clean"] is False


def _init_repo(root: Path) -> None:
    import subprocess

    def _run(*args: str) -> None:
        subprocess.run(args, cwd=root, check=True, capture_output=True)

    _run("git", "init", "-q")
    _run("git", "config", "user.email", "t@example.invalid")
    _run("git", "config", "user.name", "t")
    (root / "a.txt").write_text("one\n", encoding="utf-8")
    _run("git", "add", "a.txt")
    _run("git", "commit", "-qm", "init")


def test_worktree_status_classifies_an_unstaged_change_end_to_end(tmp_path) -> None:
    """The same regression across the real ``git status`` seam (not just parsing)."""
    _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("two\n", encoding="utf-8")

    status = ev.worktree_status(tmp_path)
    assert status["modified_unstaged"] == ["a.txt"]
    assert status["staged"] == []
    assert status["all_dirty_paths"] == ["a.txt"]


def test_files_inside_a_new_untracked_directory_are_enumerated(tmp_path) -> None:
    """``-uall``: an untracked *package* must not hide its files from the guard.

    Without it git reports a single ``?? pkg/`` entry, and an executed file
    inside a brand-new package matches nothing in the dirty set — the guard
    passes it as clean while the recorded commit contains none of its bytes.
    """
    _init_repo(tmp_path)
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").write_text("x = 1\n", encoding="utf-8")

    status = ev.worktree_status(tmp_path)
    assert status["untracked"] == ["pkg/mod.py"], "the FILE, not the directory"
    assert ev.is_dirty_target("pkg/mod.py", status["all_dirty_paths"]) is True


def test_is_dirty_target_also_matches_a_directory_entry() -> None:
    """Belt-and-braces for any git that still collapses a directory."""
    assert ev.is_dirty_target("pkg/mod.py", ["pkg/"]) is True
    assert ev.is_dirty_target("pkg/mod.py", ["pkg/mod.py"]) is True
    assert ev.is_dirty_target("other/mod.py", ["pkg/"]) is False


def test_a_target_in_an_untracked_directory_is_refused(tmp_path, monkeypatch) -> None:
    """End-to-end: the run is refused, not silently recorded as clean."""
    real = ev.worktree_status

    def _dir_form(repo_root):
        status = real(repo_root)
        collapsed = "tos/tests/"  # the directory holding the smoke node
        status["untracked"] = sorted({*status["untracked"], collapsed})
        status["all_dirty_paths"] = sorted({*status["all_dirty_paths"], collapsed})
        status["clean"] = False
        return status

    monkeypatch.setattr(ev, "worktree_status", _dir_form)
    assert ev.main(_argv(tmp_path / "e")) == 2


def test_a_file_mutated_during_the_run_is_named_not_averaged(
    tmp_path, monkeypatch
) -> None:
    """TOCTOU: digests are taken before AND after; a change is recorded and fails."""
    seen: list[int] = []

    def _shifting(repo_root, rels):
        seen.append(1)
        marker = "a" * 64 if len(seen) == 1 else "b" * 64
        return dict.fromkeys(rels, marker)

    monkeypatch.setattr(ev, "collect_digests", _shifting)
    rc = ev.main(_argv(tmp_path / "e"))
    assert len(seen) == 2, "digests must be collected before AND after the run"
    assert rc == 2, "an integrity violation is not a green run"

    run = next((tmp_path / "e" / "STATE-EV-001").iterdir())
    data = yaml.safe_load((run / "baseline.yaml").read_text(encoding="utf-8"))
    item = data["design1_5_1"]["item_1_repository_and_package"]
    assert item["target_files_stable_during_run"] is False
    assert all(d["status"] == "MUTATED_DURING_RUN" for d in item["target_file_digests"])
    man = yaml.safe_load((run / "manifest.yaml").read_text(encoding="utf-8"))
    assert man["claim"]["target_integrity"] == "MUTATED_DURING_RUN"
    assert man["claim"]["mutated_during_run"]


def test_digest_report_names_a_disagreement() -> None:
    report = ev.digest_report(
        {"a.py": "x", "b.py": "y"}, {"a.py": "x", "b.py": "z"}, []
    )
    by_path = {r["path"]: r for r in report}
    assert by_path["a.py"]["status"] == "STABLE_DURING_RUN"
    assert by_path["b.py"]["status"] == "MUTATED_DURING_RUN"
    assert by_path["b.py"]["sha256_before_run"] == "y"
    assert by_path["b.py"]["sha256_after_run"] == "z"


@pytest.mark.parametrize(
    ("rc", "junit", "expected"),
    [
        (
            0,
            {"tests": 3, "skipped": 0, "failures": 0, "errors": 0},
            "ALL_SELECTED_TESTS_GREEN",
        ),
        (
            0,
            {"tests": 3, "skipped": 1, "failures": 0, "errors": 0},
            "ALL_SELECTED_TESTS_GREEN",
        ),
        (0, {"tests": 3, "skipped": 3, "failures": 0, "errors": 0}, "NO_TEST_EXECUTED"),
        (0, {"tests": 0, "skipped": 0, "failures": 0, "errors": 0}, "NO_TEST_EXECUTED"),
        (5, {"tests": 0, "skipped": 0, "failures": 0, "errors": 0}, "NO_TEST_EXECUTED"),
        (
            1,
            {"tests": 3, "skipped": 0, "failures": 1, "errors": 0},
            "SELECTED_TESTS_NOT_GREEN",
        ),
        (
            0,
            {"tests": 3, "skipped": 0, "failures": 0, "errors": 1},
            "SELECTED_TESTS_NOT_GREEN",
        ),
    ],
)
def test_green_requires_executed_assertions_not_just_rc_zero(
    rc, junit, expected
) -> None:
    """A wholly-skipped selection exits 0; that is a vacuous green, not evidence."""
    assert ev.classify_outcome(rc, junit) == expected


def test_a_fully_skipped_run_is_recorded_as_no_test_executed(
    tmp_path, monkeypatch
) -> None:
    real = ev.parse_junit

    def _all_skipped(path):
        summary = real(path)
        summary["skipped"] = summary["tests"]
        return summary

    monkeypatch.setattr(ev, "parse_junit", _all_skipped)
    rc = ev.main(_argv(tmp_path / "e"))
    assert rc == 1, "nothing executed is not success"
    run = next((tmp_path / "e" / "STATE-EV-001").iterdir())
    man = yaml.safe_load((run / "manifest.yaml").read_text(encoding="utf-8"))
    assert man["execution"]["outcome"] == "NO_TEST_EXECUTED"


def test_harness_provenance_is_derived_never_assumed(tmp_path) -> None:
    """MAJOR-4: an untracked harness must not borrow the repository HEAD."""
    _init_repo(tmp_path)
    tracked = tmp_path / "a.txt"
    untracked = tmp_path / "harness.py"
    untracked.write_text("print(1)\n", encoding="utf-8")

    status = ev.worktree_status(tmp_path)
    prov = ev.harness_provenance(tmp_path, untracked, status, "9.0.2")
    assert prov["harness_tracked"] is False
    assert prov["harness_at_commit"] == "NOT_IN_COMMIT"
    assert prov["harness_sha256"] == hashlib.sha256(untracked.read_bytes()).hexdigest()

    prov_tracked = ev.harness_provenance(tmp_path, tracked, status, "9.0.2")
    assert prov_tracked["harness_tracked"] is True
    assert len(prov_tracked["harness_at_commit"]) == 40
    assert prov_tracked["harness_dirty"] is False


def test_baseline_harness_provenance_is_self_consistent(baseline: dict) -> None:
    item = baseline["design1_5_1"]["item_4_harness_version"]
    assert item["harness_path"] == "tools/tos_evidence_run.py"
    assert "harness_git_commit" not in item, "the repo HEAD is not the harness version"
    if item["harness_tracked"] is False:
        assert item["harness_at_commit"] == "NOT_IN_COMMIT"
    else:
        assert len(item["harness_at_commit"]) == 40


def test_pins_satisfied_is_a_boolean_claim(baseline: dict) -> None:
    item = baseline["design1_5_1"]["item_2_interpreter_and_dependencies"]
    assert isinstance(item["pins_satisfied"], bool)
    assert item["pins_satisfied"] == (not item["pin_vs_installed_drift"])


def test_an_evidence_id_cannot_escape_the_evidence_root(tmp_path) -> None:
    root = tmp_path / "store"
    with pytest.raises(ev.HarnessError, match="escapes the evidence root"):
        ev.create_run_directory(root / ".." / "elsewhere" / "run", root)


def test_a_subdirectory_would_escape_the_sums_file(tmp_path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    (run / "manifest.yaml").write_text("x\n", encoding="utf-8")
    (run / "state-dimensions").mkdir()
    with pytest.raises(ev.HarnessError, match="subdirectories"):
        ev.write_sha256sums(run)


def test_an_unexpected_failure_marks_the_package_incomplete(
    tmp_path, monkeypatch
) -> None:
    def _boom(**kwargs):
        raise MemoryError("pytest could not start")

    monkeypatch.setattr(ev, "run_pytest", _boom)
    with pytest.raises(MemoryError):
        ev.main(_argv(tmp_path / "e"))
    run = next((tmp_path / "e" / "STATE-EV-001").iterdir())
    marker = run / "INCOMPLETE_RUN.txt"
    assert marker.is_file()
    assert "NOT an evidence package" in marker.read_text(encoding="utf-8")
    assert not (run / "manifest.yaml").exists()


def test_clean_worktree_reports_clean() -> None:
    status = ev.parse_porcelain("")
    assert status["clean"] is True
    assert status["all_dirty_paths"] == []


def test_parse_node_spec_splits_basis_and_defaults_to_unspecified() -> None:
    assert ev.parse_node_spec("a.py::t | because §7:12") == ("a.py::t", "because §7:12")
    assert ev.parse_node_spec("  a.py  ") == ("a.py", "UNSPECIFIED")


def test_node_file_strips_the_selector() -> None:
    assert ev.node_file("pkg/test_x.py::TestC::test_y") == "pkg/test_x.py"


# ==========================================================================
# EV-L2 stage (manifest v2) — EV-L2 pilot design §6.2 / §8.5
# ==========================================================================

#: A real EV-L2 fault node: it records one append-only fault-timeline row per catalog
#: fault, which is what makes the schedule summary a measurement and not a stub.
_L2_NODE = "tos/tests/spg/test_spg_l2_fault.py"
_L2_CATALOG_REF = "docs/plans/2026-07-29-tos-ev-l2-pilot-design.md#4"
#: The design §4 table size — the harness recounts the schedule against it.
_L2_CATALOG_SIZE = 12


def _l2_argv(evidence_root: Path, *, prior: str, **overrides) -> list[str]:
    argv = [
        "--register-csv",
        str(_hermetic_register(evidence_root)),
        "--evidence-id",
        "SPG-EV-002",
        "--node",
        f"{_L2_NODE} | EV-L2 §4 fault catalog (harness self-test)",
        "--primary-adr",
        "ADR-002-014",
        "--seed-policy",
        "fixed:0",
        "--evidence-level-stage",
        "EV-L2",
        "--fault-catalog-ref",
        overrides.get("catalog_ref", _L2_CATALOG_REF),
        "--expected-fault-count",
        str(overrides.get("expected_fault_count", _L2_CATALOG_SIZE)),
        "--covered-axis",
        "semantic-validation component (post-hardening)",
        "--residual-ref",
        "SPG overflow (bound-dependent); currency (no independent field)",
        "--prior-stage-run",
        prior,
        "--evidence-root",
        str(evidence_root),
        # the L2 suite is new work in this branch, so its bytes may be uncommitted;
        # the dirt is then recorded in-band rather than hiding the run.
        "--allow-dirty-targets",
    ]
    return argv


@pytest.fixture(scope="module")
def l2_package(tmp_path_factory, module_monkeypatch):
    """An EV-L1 run followed by an EV-L2 run that binds it (the real staged shape)."""
    root = tmp_path_factory.mktemp("evidence-l2")
    # A frozen, explicitly advanced clock: run ids are second-resolution, so two runs
    # for the same evidence id in the same second would collide with the append-only
    # refusal. ``advance`` is handed to the tests that need a further run.
    clock = {"now": datetime(2026, 7, 29, 6, 0, 0, tzinfo=UTC)}

    def _now():
        return clock["now"]

    def advance(seconds: int = 1):
        clock["now"] = clock["now"] + timedelta(seconds=seconds)
        return clock["now"]

    module_monkeypatch.setattr(ev, "_utc_now", _now)

    rc_l1 = ev.main(
        [
            "--register-csv",
            str(_hermetic_register(root)),
            "--evidence-id",
            "SPG-EV-002",
            "--node",
            f"{_SMOKE_NODE} | EV-L1 stage (harness self-test)",
            "--primary-adr",
            "ADR-002-014",
            "--seed-policy",
            "fixed:0",
            "--evidence-root",
            str(root),
        ]
    )
    assert rc_l1 == 0
    l1_run = next((root / "SPG-EV-002").iterdir())

    advance()
    rc_l2 = ev.main(_l2_argv(root, prior=f"SPG-EV-002/{l1_run.name} | L1 traceability"))
    l2_run = next(p for p in (root / "SPG-EV-002").iterdir() if p != l1_run)
    manifest = yaml.safe_load((l2_run / "manifest.yaml").read_text(encoding="utf-8"))
    baseline = yaml.safe_load((l2_run / "baseline.yaml").read_text(encoding="utf-8"))
    return {
        "root": root,
        "l1_run": l1_run,
        "run": l2_run,
        "rc": rc_l2,
        "manifest": manifest,
        "baseline": baseline,
        "advance": advance,
    }


@pytest.fixture(scope="module")
def module_monkeypatch():
    """A module-scoped monkeypatch (the built-in fixture is function-scoped)."""
    patcher = pytest.MonkeyPatch()
    yield patcher
    patcher.undo()


def test_l2_manifest_is_v2_and_a_strict_superset_of_v1(
    l2_package: dict, manifest: dict
) -> None:
    """design §6.2 N8 — v2 ADDS field groups; it drops no v1 field."""
    l2 = l2_package["manifest"]
    assert l2["schema"] == "tos-evidence/manifest/v2"
    assert l2["evidence_level_stage"] == "EV-L2"
    assert set(manifest) <= set(l2), "a v1 top-level field was dropped by v2"
    assert set(manifest["claim"]) <= set(l2["claim"]), "a v1 claim field was dropped"
    # the v1 fields the design names explicitly (N8) are present with real values
    assert (
        l2["claim"]["verification_profile_version"]
        == ev.read_profile_approval(_REPO_ROOT)["version_label"]
    )
    # copied through from the INJECTED register (see ``_hermetic_register``), so a
    # real row moving READY -> PASS cannot break this expectation
    assert l2["claim"]["register_status_at_run_time"] == _HERMETIC_REGISTER_STATUS
    assert l2["claim"]["note"]
    assert l2["claim"]["closes_evidence_item"] is False
    assert l2["claim"]["register_status_moved_by_this_run"] is False


def test_l2_discipline_tag_is_the_l2_wording(l2_package: dict) -> None:
    tag = l2_package["manifest"]["discipline_tag"]
    assert tag == ev.DISCIPLINE_TAG_L2
    assert "not a row PASS" in tag
    assert "L1 hardening prereq" in tag and "coverage argument" in tag


def test_l2_fault_injection_group_recounts_the_schedule(l2_package: dict) -> None:
    """fault_count is recounted from the artifact, never taken from the catalog."""
    run = l2_package["run"]
    fault = l2_package["manifest"]["fault_injection"]
    lines = [
        line
        for line in (run / "fault-timeline.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert fault["fault_count"] == len(lines) == 12  # design §4 table: SPG = 12
    assert fault["schedule_artifact"] == "fault-timeline.jsonl"
    assert fault["seed"] == 0
    assert fault["catalog_ref"] == _L2_CATALOG_REF
    assert fault["all_faults_met"] is True
    assert fault["deviation_faults"] == []
    assert fault["expected_undefined_faults"] == []
    assert fault["l1_hardening_prereq_met"] is True


def test_l2_fault_timeline_rows_carry_every_section_6_1_field(l2_package: dict) -> None:
    """design §6.1 — the exact row shape, incl. a MEASURED guard_code_line."""
    run = l2_package["run"]
    rows = [
        json.loads(line)
        for line in (run / "fault-timeline.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    for row in rows:
        assert list(row) == [
            "fault_id",
            "evidence_id",
            "target_component",
            "guard_code_line",
            "fault_kind",
            "seed",
            "input_witness_ref",
            "expected_disposition",
            "observed_disposition",
            "outcome",
        ]
        assert row["seed"] == 0
        assert row["outcome"] == "MET"
        # a real file:line, not a docstring anchor (design §3 line 163 v1.2)
        for citation in row["guard_code_line"].split(";"):
            path, _, line_no = citation.strip().rpartition(":")
            assert path.endswith(".py") and line_no.isdigit()


def test_l2_fault_timeline_is_covered_by_the_sums_file(l2_package: dict) -> None:
    """The schedule is part of the artifact closure (VER §9.1 + §9.2)."""
    run = l2_package["run"]
    sums = (run / "sha256sums.txt").read_text(encoding="utf-8")
    assert "fault-timeline.jsonl" in sums
    names = {entry["name"] for entry in l2_package["manifest"]["artifacts"]}
    assert "fault-timeline.jsonl" in names


def test_l2_coverage_argument_states_the_ver_2_7_legs(l2_package: dict) -> None:
    """VER §2.7 — both legs are stated, and the argument is NOT claimed discharged."""
    coverage = l2_package["manifest"]["coverage_argument"]
    assert coverage["boundary_values"] == ev.COVERAGE_BOUNDARY_VALUES
    assert "ADR-002-021" in coverage["adverse_scenario_set"]
    assert "PROPOSED" in coverage["adverse_scenario_set"]
    assert coverage["unexercised_residual_ref"], "residual pointers must be recorded"
    assert coverage["discharged"] is False
    # design §6.2 N4 — the §378 register instance is absent; entries need 12 fields;
    # separate residuals are never unioned at a consumer.
    assert "template" in coverage["unexercised_residual_note"]
    assert "twelve" in coverage["unexercised_residual_note"]
    assert "VER:3308" in coverage["unexercised_residual_note"]


def test_l2_prior_stage_run_is_bound_by_digest_and_baseline(l2_package: dict) -> None:
    """design §6.2 M9 — the prior EV-L1 package is pinned, not merely named."""
    prior = l2_package["manifest"]["prior_stage_runs"]
    assert len(prior) == 1
    entry = prior[0]
    assert entry["stage"] == "EV-L1"
    assert entry["run_id"] == l2_package["l1_run"].name
    expected_digest = hashlib.sha256(
        (l2_package["l1_run"] / "sha256sums.txt").read_bytes()
    ).hexdigest()
    assert entry["sha256sums_digest"] == expected_digest
    assert len(entry["baseline_commit_sha"]) == 40
    assert entry["baseline_matches_this_run"] is True
    assert entry["reconcile_note"] == "L1 traceability"


def test_l2_run_is_green_when_every_stage_gate_is_met(l2_package: dict) -> None:
    assert l2_package["manifest"]["claim"]["ev_l2_stage_gates_unmet"] == []
    assert l2_package["manifest"]["execution"]["outcome"] == "ALL_SELECTED_TESTS_GREEN"
    assert l2_package["rc"] == 0
    assert l2_package["manifest"]["claim"]["stages_executed"] == ["EV-L1", "EV-L2"]
    assert l2_package["manifest"]["claim"]["covered_axis"]


# ---- M2: the VER §3 baseline note is UPDATED, never deleted ---------------


def test_l2_baseline_keeps_the_ver3_gap_with_the_l2_attribution(
    l2_package: dict,
) -> None:
    baseline = l2_package["baseline"]
    ver3 = baseline["ver_002_001_section_3_baseline"]
    assert list(ver3) == _VER3_FIELDS, "all 22 fields survive the stage change"
    for field in _MUST_BE_NOT_APPLICABLE:
        entry = ver3[field]
        assert entry["status"] == ev.NOT_APPLICABLE_L2
        assert entry["reason"], "the reason is retained, not dropped"
        assert "value" not in entry
    assert ev.NOT_APPLICABLE_L2 in baseline["contract"]["completeness"]
    assert "NOT complete" in baseline["contract"]["completeness"]


def test_l2_baseline_completes_the_fault_schedule_field(l2_package: dict) -> None:
    """The one VER §3 field EV-L2 completes relative to EV-L1."""
    entry = l2_package["baseline"]["ver_002_001_section_3_baseline"][
        "fault_injection_schedule_and_seed"
    ]
    assert entry["status"] == ev.RECORDED
    assert entry["value"]["fault_schedule"]["fault_count"] == 12
    assert entry["value"]["seed"]["hypothesis_seed"] == 0


def test_ver3_unmet_field_list_is_a_structural_canary(l2_package: dict) -> None:
    """design §6.2 M2 — the §3 gap is an enumerable LIST, not a sentence to grep.

    A substring canary would keep passing if the note survived while the underlying
    fields quietly became RECORDED. This checks the list against the field statuses.
    """
    baseline = l2_package["baseline"]
    unmet = baseline["ver_002_001_section_3_unmet_fields"]
    ver3 = baseline["ver_002_001_section_3_baseline"]
    assert unmet, "an empty unmet list would claim a complete VER §3 baseline"
    assert unmet == sorted(
        name for name, entry in ver3.items() if entry["status"] != ev.RECORDED
    )
    assert set(_MUST_BE_NOT_APPLICABLE) <= set(unmet)
    assert l2_package["manifest"]["baseline"]["ver3_unmet_field_count"] == len(unmet)


def test_ver3_unmet_field_list_is_present_at_ev_l1_too(baseline: dict) -> None:
    """The canary is not an EV-L2 novelty — the EV-L1 baseline carries it as well."""
    unmet = baseline["ver_002_001_section_3_unmet_fields"]
    assert unmet
    assert "fault_injection_schedule_and_seed" in unmet


# ---- all_faults_met gate (design §6.2 C2-c) -------------------------------


def _row(fault_id: str, **overrides) -> dict:
    """A well-formed schedule row (observed == expected, so it re-derives to MET)."""
    row = {
        "fault_id": fault_id,
        "evidence_id": "SPG-EV-002",
        "expected_disposition": "REJECTED",
        "observed_disposition": "REJECTED",
        "outcome": "MET",
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize(
    ("rows", "expected", "why"),
    [
        ([_row("A"), _row("B")], True, "every row met"),
        ([], False, "an empty schedule is not 'no violations' (∅-seal)"),
        (
            [
                _row("A"),
                _row("B", observed_disposition="ACCEPTED", outcome="DEVIATION"),
            ],
            False,
            "a single DEVIATION forbids GREEN",
        ),
        (
            [_row("A"), _row("B", expected_disposition="")],
            False,
            "an unstated Expected cannot be falsified, so it cannot be met",
        ),
        (
            [_row("A"), _row("B", expected_disposition=None)],
            False,
            "a null Expected is equally unfalsifiable",
        ),
        (
            [_row("A"), _row("A")],
            False,
            "a duplicated fault id would inflate the recount",
        ),
        (
            [_row("A"), _row("B", observed_disposition="ACCEPTED")],
            False,
            "observed != expected is a deviation even when the row SAYS it is MET",
        ),
        (
            [_row("A"), _row("B", observed_disposition="<runtime-observed>")],
            False,
            "the design §6.1 placeholder means no runtime ever filled the row in",
        ),
        (
            [_row("A"), _row("B", observed_disposition="")],
            False,
            "an empty observation proves nothing",
        ),
        (
            [_row("A"), _row("B", evidence_id="STATE-EV-001")],
            False,
            "a row from another evidence row does not evidence this one",
        ),
    ],
)
def test_all_faults_met_is_withheld_on_every_defective_schedule(
    rows, expected, why
) -> None:
    summary = ev.summarise_fault_schedule(rows, evidence_id="SPG-EV-002")
    assert summary["all_faults_met"] is expected, why


def test_a_row_that_misreports_its_own_outcome_is_caught() -> None:
    """The row's ``outcome`` field is cross-checked, never believed.

    A schedule whose emitter labels a mismatch ``MET`` would otherwise certify itself:
    the summary must re-derive the verdict from observed vs expected and name the
    disagreement rather than adopt the claim.
    """
    summary = ev.summarise_fault_schedule(
        [_row("A"), _row("B", observed_disposition="ACCEPTED", outcome="MET")]
    )
    assert summary["all_faults_met"] is False
    assert summary["deviation_faults"] == ["B"]
    assert summary["misreported_outcome_faults"] == ["B"]


def test_fault_count_is_recounted_from_the_rows() -> None:
    summary = ev.summarise_fault_schedule([_row("A"), _row("B"), _row("C")])
    assert summary["fault_count"] == 3
    assert summary["fault_ids"] == ["A", "B", "C"]


def test_a_recount_that_disagrees_with_the_catalog_withholds_green() -> None:
    """A deselected fault shrinks the schedule; the catalog size is what notices.

    Without this the remaining rows are all still ``MET``, so the run reads green while
    silently evidencing less than the ratified catalog defines.
    """
    rows = [_row("A"), _row("B")]
    assert ev.summarise_fault_schedule(rows, expected_fault_count=2)["all_faults_met"]
    short = ev.summarise_fault_schedule(rows, expected_fault_count=3)
    assert short["all_faults_met"] is False
    assert short["fault_count_matches_catalog"] is False
    assert short["deviation_faults"] == [], "the rows themselves were fine"


def test_a_malformed_schedule_line_is_refused_not_skipped(tmp_path) -> None:
    """A schedule the harness cannot fully read must not be summarised as if it could."""
    path = tmp_path / "fault-timeline.jsonl"
    path.write_text('{"fault_id": "A"}\nnot-json\n', encoding="utf-8")
    with pytest.raises(ev.HarnessError, match="not valid JSON"):
        ev.read_fault_timeline(path)


def test_an_absent_schedule_reads_as_empty_and_withholds_green(tmp_path) -> None:
    rows = ev.read_fault_timeline(tmp_path / "nothing.jsonl")
    assert rows == []
    assert ev.summarise_fault_schedule(rows)["all_faults_met"] is False


# ---- L1 hardening prerequisite (design §5) --------------------------------


def test_l1_hardening_is_measured_from_the_executed_source() -> None:
    """The §5 H-1/H-2/H-4 prerequisite is read out of the code, not passed as a flag."""
    result = ev.check_l1_hardening(_REPO_ROOT)
    assert result["met"] is True
    labels = [item["hardening"] for item in result["items"]]
    assert any(label.startswith("H-1") for label in labels)
    assert any(label.startswith("H-2") for label in labels)
    assert any(label.startswith("H-4") for label in labels)
    for item in result["items"]:
        assert item["met"] is True, item


def test_l1_hardening_is_unmet_when_the_files_are_absent(tmp_path) -> None:
    result = ev.check_l1_hardening(tmp_path)
    assert result["met"] is False
    assert all(item["met"] is False for item in result["items"])
    assert all(item["reason"] == "FILE_ABSENT" for item in result["items"])


def _write(tmp_path: Path, rel: str, source: str) -> None:
    target = tmp_path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")


_H1_SOURCE_PINNED = (
    "from pydantic import BaseModel, ConfigDict\n"
    "class FrozenModel(BaseModel):\n"
    '    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)\n'
)
_H2_SOURCE_HARDENED = (
    '_UNIT_METADATA_KEYS = ("unit", "multiplier", "sign", "precision", '
    '"rounding", "boundary")\n'
    "def _exceeds_envelope_maximum(a, b, c):\n    return a > b\n"
)
_H4_SOURCE_WRAPPED = (
    "def get_scheme(version):\n"
    "    if version is None:\n"
    "        raise ArtifactIntegrityError('no scheme')\n"
    "    return version\n"
)


def _hardening_paths() -> dict[str, str]:
    return {label.split()[0]: rel for label, rel, _ in ev.L1_HARDENING_PREREQUISITES}


def _hardened_tree(tmp_path: Path) -> None:
    paths = _hardening_paths()
    _write(tmp_path, paths["H-1"], _H1_SOURCE_PINNED)
    _write(tmp_path, paths["H-2"], _H2_SOURCE_HARDENED)
    _write(tmp_path, paths["H-4"], _H4_SOURCE_WRAPPED)


def _item(result: dict, prefix: str) -> dict:
    return next(i for i in result["items"] if i["hardening"].startswith(prefix))


def test_a_minimal_hardened_tree_is_met(tmp_path) -> None:
    """The structural checks pass on a tree that really carries the hardening."""
    _hardened_tree(tmp_path)
    assert ev.check_l1_hardening(tmp_path)["met"] is True


def test_h1_is_not_satisfied_by_a_comment_or_docstring(tmp_path) -> None:
    """CRITICAL regression: the pin must be a real keyword, not a mention of one.

    A file-wide substring gate was green for exactly this file — H-1 rolled back, with
    the token surviving in a comment and a docstring. The AST check reads the keyword out
    of the actual ``ConfigDict(...)`` call, so prose cannot satisfy it.
    """
    _hardened_tree(tmp_path)
    _write(
        tmp_path,
        _hardening_paths()["H-1"],
        "from pydantic import BaseModel, ConfigDict\n"
        "class FrozenModel(BaseModel):\n"
        '    """Historically this pinned allow_inf_nan=False."""\n'
        "    # allow_inf_nan=False\n"
        '    model_config = ConfigDict(frozen=True, extra="forbid")\n',
    )
    result = ev.check_l1_hardening(tmp_path)
    assert result["met"] is False
    h1 = _item(result, "H-1")
    assert h1["met"] is False
    assert h1["measured"]["allow_inf_nan"] is None
    assert "allow_inf_nan" not in h1["measured"]["bound_keywords"]


def test_h1_rejects_a_non_false_pin(tmp_path) -> None:
    """``allow_inf_nan=True`` is a bound keyword — but the wrong one."""
    _hardened_tree(tmp_path)
    _write(
        tmp_path,
        _hardening_paths()["H-1"],
        "from pydantic import BaseModel, ConfigDict\n"
        "class FrozenModel(BaseModel):\n"
        "    model_config = ConfigDict(frozen=True, allow_inf_nan=True)\n",
    )
    result = ev.check_l1_hardening(tmp_path)
    assert result["met"] is False
    assert _item(result, "H-1")["measured"]["allow_inf_nan"] == "True"


def test_h2_is_unmet_when_an_axis_is_dropped(tmp_path) -> None:
    _hardened_tree(tmp_path)
    _write(
        tmp_path,
        _hardening_paths()["H-2"],
        '_UNIT_METADATA_KEYS = ("unit", "multiplier", "sign")\n'
        "def _exceeds_envelope_maximum(a, b, c):\n    return a > b\n",
    )
    result = ev.check_l1_hardening(tmp_path)
    assert result["met"] is False
    assert _item(result, "H-2")["measured"]["missing_metadata_keys"] == [
        "boundary",
        "precision",
        "rounding",
    ]


def test_h4_regression_is_caught_if_the_raw_keyerror_returns(tmp_path) -> None:
    """H-4: a surviving raw ``raise KeyError`` disqualifies the module."""
    _hardened_tree(tmp_path)
    _write(
        tmp_path,
        _hardening_paths()["H-4"],
        "def get_scheme(version):\n"
        "    if version is None:\n"
        "        raise KeyError('no scheme')\n"
        "    return version\n",
    )
    result = ev.check_l1_hardening(tmp_path)
    assert result["met"] is False
    h4 = _item(result, "H-4")
    assert "KeyError" in h4["measured"]["module_raises"]
    assert "ArtifactIntegrityError" not in h4["measured"]["get_scheme_raises"]


def test_unparseable_source_is_unmet_not_ignored(tmp_path) -> None:
    """A file that does not parse cannot be certified — silence is not compliance."""
    _hardened_tree(tmp_path)
    _write(tmp_path, _hardening_paths()["H-1"], "class FrozenModel(:\n")
    result = ev.check_l1_hardening(tmp_path)
    assert result["met"] is False
    assert _item(result, "H-1")["reason"].startswith("SOURCE_DOES_NOT_PARSE")


# ---- stage-option hygiene --------------------------------------------------


def test_ev_l2_options_are_refused_on_an_ev_l1_run(tmp_path) -> None:
    rc = ev.main([*_argv(tmp_path / "e"), "--covered-axis", "something"])
    assert rc == 2


@pytest.mark.parametrize(
    "dropped", ["--fault-catalog-ref", "--covered-axis", "--prior-stage-run"]
)
def test_ev_l2_requires_its_unmeasurable_claims_to_be_stated(tmp_path, dropped) -> None:
    """A claim the harness cannot measure must be given, never defaulted."""
    argv = _l2_argv(tmp_path / "e", prior="SPG-EV-002/whatever")
    index = argv.index(dropped)
    del argv[index : index + 2]
    assert ev.main(argv) == 2


def test_a_prior_stage_run_that_is_not_a_closed_package_is_refused(tmp_path) -> None:
    rc = ev.main(_l2_argv(tmp_path / "e", prior="SPG-EV-002/20260101T000000Z-deadbeef"))
    assert rc == 2


def test_l2_gate_fires_end_to_end_when_no_fault_was_injected(
    l2_package: dict, tmp_path
) -> None:
    """∅-seal, end to end: a node that injects nothing cannot produce a GREEN EV-L2 run.

    This is the failure mode the design calls out first (§0.5-2): a stage that ran, passed
    every assertion, and injected **zero** faults would otherwise be indistinguishable
    from one that injected the whole catalog and met it.
    """
    prior = f"SPG-EV-002/{l2_package['l1_run'].name}"
    argv = _l2_argv(l2_package["root"], prior=f"{prior} | L1 traceability")
    argv[argv.index("--node") + 1] = f"{_SMOKE_NODE} | injects no fault"
    l2_package["advance"]()
    rc = ev.main(argv)
    assert rc != 0, "an empty fault schedule is not a green EV-L2 stage"

    run = max((l2_package["root"] / "SPG-EV-002").iterdir(), key=lambda p: p.name)
    man = yaml.safe_load((run / "manifest.yaml").read_text(encoding="utf-8"))
    assert man["fault_injection"]["fault_count"] == 0
    assert man["fault_injection"]["all_faults_met"] is False
    assert "FAULT_SCHEDULE_NOT_ALL_MET" in man["claim"]["ev_l2_stage_gates_unmet"]
    assert man["execution"]["stage_gate_outcome"].startswith("EV_L2_STAGE_GATE_UNMET")
    # m5: the TEST result stays visible — a gated run and a run whose tests actually
    # failed must not collapse into one indistinguishable outcome string.
    assert man["execution"]["outcome"] == "ALL_SELECTED_TESTS_GREEN"
    # m7: a gated run makes no stage or coverage claim
    assert man["claim"]["stages_executed"] == "WITHHELD (EV-L2 stage gate unmet)"
    assert man["claim"]["covered_axis"].startswith("WITHHELD")
    assert man["claim"]["invoked_covered_axis"]


def test_a_prior_package_edited_after_the_fact_is_refused(l2_package: dict) -> None:
    """MAJOR-5: the prior package's recorded digests are RE-VERIFIED, not just quoted.

    Citing a ``sha256sums.txt`` digest proves nothing about the files beside it unless
    someone re-hashes them. Here the prior run's manifest is edited after the fact — the
    sums file still lists its old digest, so the binding must refuse rather than carry a
    reference that no longer describes the package.
    """
    prior = l2_package["l1_run"]
    manifest_path = prior / "manifest.yaml"
    original = manifest_path.read_bytes()
    manifest_path.write_bytes(original + b"\ntampered: true\n")
    try:
        with pytest.raises(ev.HarnessError, match="no longer describe"):
            ev.bind_prior_stage_run(
                l2_package["root"], "SPG-EV-002", prior.name, "note", "sha"
            )
    finally:
        manifest_path.write_bytes(original)


def test_a_prior_package_with_an_uncovered_file_is_refused(l2_package: dict) -> None:
    """MAJOR-5: a file the sums do not list would ride along unverified."""
    prior = l2_package["l1_run"]
    smuggled = prior / "extra.yaml"
    smuggled.write_text("added later\n", encoding="utf-8")
    try:
        with pytest.raises(ev.HarnessError, match="does not cover"):
            ev.bind_prior_stage_run(
                l2_package["root"], "SPG-EV-002", prior.name, "note", "sha"
            )
    finally:
        smuggled.unlink()


def test_a_prior_stage_that_was_not_green_is_refused(
    l2_package: dict, tmp_path
) -> None:
    """MAJOR-5: a stage that did not pass cannot support a staged L1 ∧ L2 claim."""
    root = tmp_path / "evidence"
    src = l2_package["l1_run"]
    dest = root / "SPG-EV-002" / src.name
    dest.mkdir(parents=True)
    for item in src.iterdir():
        dest.joinpath(item.name).write_bytes(item.read_bytes())

    man = yaml.safe_load((dest / "manifest.yaml").read_text(encoding="utf-8"))
    man["execution"]["outcome"] = "SELECTED_TESTS_NOT_GREEN"
    (dest / "manifest.yaml").write_text(ev.dump_yaml(man), encoding="utf-8")
    # re-close the package so the failure is attributable to the OUTCOME, not the digests
    (dest / "sha256sums.txt").unlink()
    ev.write_sha256sums(dest)

    with pytest.raises(ev.HarnessError, match="did not pass"):
        ev.bind_prior_stage_run(root, "SPG-EV-002", src.name, "note", "sha")


def test_a_prior_reference_cannot_escape_the_evidence_root(tmp_path) -> None:
    """m11: symmetric with create_run_directory — no reading outside the store."""
    with pytest.raises(ev.HarnessError, match="escapes the evidence root"):
        ev.bind_prior_stage_run(tmp_path / "store", "..", "elsewhere", "note", "sha")


def test_an_unpinned_seed_withholds_green_on_an_ev_l2_run(
    l2_package: dict,
) -> None:
    """m6: VER §9.1 makes the seed part of the run record — unpinned is unreproducible."""
    argv = _l2_argv(
        l2_package["root"],
        prior=f"SPG-EV-002/{l2_package['l1_run'].name} | L1 traceability",
    )
    argv[argv.index("--seed-policy") + 1] = "default"
    l2_package["advance"]()
    rc = ev.main(argv)
    assert rc != 0

    run = max((l2_package["root"] / "SPG-EV-002").iterdir(), key=lambda p: p.name)
    man = yaml.safe_load((run / "manifest.yaml").read_text(encoding="utf-8"))
    assert man["fault_injection"]["seed_pinned"] is False
    assert "SEED_NOT_PINNED" in man["claim"]["ev_l2_stage_gates_unmet"]


def test_bind_prior_stage_run_flags_a_stale_baseline(l2_package: dict) -> None:
    """design §6.2 M9 — an EV-L1 run at another baseline is stale, and says so."""
    bound = ev.bind_prior_stage_run(
        l2_package["root"],
        "SPG-EV-002",
        l2_package["l1_run"].name,
        "note",
        "0" * 40,
    )
    assert bound["baseline_matches_this_run"] is False
    assert bound["stage"] == "EV-L1"
    assert bound["sha256sums_digest"]


def test_l2_gate_fires_end_to_end_when_every_prior_l1_is_stale(
    l2_package: dict, monkeypatch
) -> None:
    """design §6.2 M9, end to end — a stale EV-L1 binding withholds GREEN.

    Recording ``baseline_matches_this_run: false`` is not enough on its own: if the run
    still reported GREEN, the staged ``L1 ∧ L2`` claim would rest on an EV-L1 package
    describing *different* bytes, which is exactly what M9 forbids. The stale flag is
    injected at the binding seam so the rest of the run is real.
    """
    real_bind = ev.bind_prior_stage_run

    def _stale(*args, **kwargs):
        bound = real_bind(*args, **kwargs)
        bound["baseline_matches_this_run"] = False
        return bound

    monkeypatch.setattr(ev, "bind_prior_stage_run", _stale)
    l2_package["advance"]()
    rc = ev.main(
        _l2_argv(
            l2_package["root"],
            prior=f"SPG-EV-002/{l2_package['l1_run'].name} | stale baseline",
        )
    )
    assert rc != 0, "an EV-L2 stage founded on a stale EV-L1 run is not green"

    run = max((l2_package["root"] / "SPG-EV-002").iterdir(), key=lambda p: p.name)
    man = yaml.safe_load((run / "manifest.yaml").read_text(encoding="utf-8"))
    # the faults themselves all passed — only the staged-binding gate withholds GREEN
    assert man["fault_injection"]["all_faults_met"] is True
    assert man["claim"]["ev_l2_stage_gates_unmet"] == [
        "NO_PRIOR_EV_L1_RUN_AT_THIS_BASELINE"
    ]
    assert man["execution"]["stage_gate_outcome"].startswith("EV_L2_STAGE_GATE_UNMET")
    assert man["execution"]["outcome"] == "ALL_SELECTED_TESTS_GREEN"
    assert man["claim"]["covered_axis"].startswith("WITHHELD")


def test_parse_prior_stage_spec_splits_ref_and_note() -> None:
    assert ev.parse_prior_stage_spec("EV-1/run-9 | because") == (
        "EV-1",
        "run-9",
        "because",
    )
    assert ev.parse_prior_stage_spec(" EV-1/run-9 ") == ("EV-1", "run-9", "")
    with pytest.raises(ev.HarnessError, match="expects"):
        ev.parse_prior_stage_spec("EV-1")


# ==========================================================================
# mapping-basis citations are re-measured, never trusted
# ==========================================================================

_BASIS_NODE = (
    "tos/tests/spg/test_spg_records.py::test_valid_result_must_have_empty_reason_set"
)


def _basis_defects(node: str, basis: str) -> list[dict]:
    return ev.verify_basis_citations(_REPO_ROOT, [(node, basis)])


def test_a_stale_citation_that_still_resolves_is_refused() -> None:
    """The defect an independent review actually found, mechanically caught.

    A re-executed stage copied its mapping basis forward from an earlier run. The cited
    lines had drifted, but they still existed and still held real code — just somebody
    else's — so every existence check passed and the run recorded them as its mapping
    evidence. When the node selects one exact test, a citation into that same file must
    land inside that test's own span.
    """
    span = ev._selector_line_span(
        _REPO_ROOT / "tos/tests/spg/test_spg_records.py",
        "test_valid_result_must_have_empty_reason_set",
    )
    assert span is not None
    outside = span[0] - 5
    defects = _basis_defects(
        _BASIS_NODE, f"seals the coupling (test_spg_records.py:{outside})"
    )
    assert [d["defect"] for d in defects] == ["OUTSIDE_THE_SELECTED_TEST"]
    assert defects[0]["selected_test_span"] == f"{span[0]}-{span[1]}"

    # ...and the correct anchor is accepted
    assert _basis_defects(_BASIS_NODE, f"(test_spg_records.py:{span[0]})") == []


def test_an_ambiguous_basename_citation_is_refused() -> None:
    """``predicates.py`` names many files; an uncheckable citation is not evidence."""
    defects = _basis_defects("a.py", "producer predicates.py:429 carries the anchor")
    assert [d["defect"] for d in defects] == ["AMBIGUOUS_BASENAME"]
    assert len(defects[0]["candidates"]) > 1
    # the same claim, written so it CAN be checked
    assert _basis_defects("a.py", "tos/src/tos/spg/predicates.py:429") == []


def test_a_citation_past_eof_or_on_a_blank_line_is_refused() -> None:
    assert [
        d["defect"] for d in _basis_defects("a.py", "test_spg_records.py:999999")
    ] == ["PAST_EOF"]
    blank = next(
        i + 1
        for i, line in enumerate(
            (_REPO_ROOT / "tos/tests/spg/test_spg_records.py")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        if not line.strip()
    )
    assert [
        d["defect"] for d in _basis_defects("a.py", f"test_spg_records.py:{blank}")
    ] == ["CITES_A_BLANK_LINE"]


def test_a_basis_without_citations_is_accepted() -> None:
    """The guard constrains citations; it does not require them."""
    assert _basis_defects("a.py", "prose only, no file:line claim") == []


def test_a_run_with_a_defective_basis_is_refused_before_it_starts(tmp_path) -> None:
    """End to end: no package is produced for an unverifiable mapping claim."""
    rc = ev.main(
        [
            "--evidence-id",
            "STATE-EV-001",
            "--node",
            f"{_SMOKE_NODE} | basis citing {_SMOKE_NODE.split('/')[-1]}:999999",
            "--evidence-root",
            str(tmp_path / "e"),
        ]
    )
    assert rc == 2
    assert not (tmp_path / "e").exists(), "no package for an unverifiable basis"


def test_the_evidence_the_register_points_at_has_resolving_bases() -> None:
    """Regression lock on the evidence actually in force.

    Scoped to the packages ``EVIDENCE-REGISTER-002.csv`` names in ``latest_run_id``, plus
    the prior stages those packages bind. Superseded packages are deliberately excluded:
    one legitimately cites the source of the commit it ran at, and its citations having
    drifted since is why it was superseded — not a defect in it. What must hold is that
    the evidence a reader is directed to still cites lines that exist where it says.
    """
    register = _REPO_ROOT / ev.REGISTER_CSV_PATH
    if not register.is_file():
        pytest.skip("evidence register not present")
    with open(register, newline="", encoding="utf-8-sig") as fh:
        latest = {
            (row["evidence_id"], row["latest_run_id"])
            for row in csv.DictReader(fh)
            if row.get("latest_run_id")
        }
    in_force: set[tuple[str, str]] = set()
    for evidence_id, run_id in latest:
        run = _REPO_ROOT / "tos-evidence" / evidence_id / run_id
        if not run.is_dir():
            continue
        in_force.add((evidence_id, run_id))
        manifest_path = run / "manifest.yaml"
        if not manifest_path.is_file():
            continue
        man = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        for prior in man.get("prior_stage_runs") or []:
            in_force.add((prior["evidence_id"], prior["run_id"]))

    checked = 0
    for evidence_id, run_id in sorted(in_force):
        trace = _REPO_ROOT / "tos-evidence" / evidence_id / run_id / "traceability.csv"
        if not trace.is_file():
            continue
        with open(trace, newline="", encoding="utf-8") as fh:
            nodes = [(r["test_node"], r["mapping_basis"]) for r in csv.DictReader(fh)]
        assert (
            ev.verify_basis_citations(_REPO_ROOT, nodes) == []
        ), f"{evidence_id}/{run_id}"
        checked += 1
    print(f"in-force evidence packages checked: {checked}")


# ==========================================================================
# EV-L3 stage (manifest v3) — EV-L3 pilot design §6.1 / §6.2 / §6.4
# ==========================================================================

#: The real outside crash-orchestration node. It records one append-only crash-timeline
#: row per catalog scenario, which is what makes the schedule summary a measurement.
_L3_NODE = "tests/tos_l3/test_state_ev_004_crash_restart.py"
_L3_CATALOG_REF = "docs/plans/2026-08-06-tos-ev-l3-pilot-design.md#4"
#: The design §4 table size — the harness recounts the schedule against it.
_L3_CATALOG_SIZE = 8
#: A real EV-L2 fault node for STATE-EV-001 (design §3 catalog: ST-01..09, 11, 12).
_L2_STATE_NODE = "tos/tests/orthostate/test_orthostate_l2_fault.py"
_L2_STATE_CATALOG_SIZE = 11

_L3_MODELED_AXES = (
    "network | MODELED | RESIDUAL-RISK-REGISTER-002 R-N | VirtualBroker-class marker; "
    "zero real bytes; real broker network deferred to EV-L4/+Broker",
    "credential_identity | DEFERRED | RESIDUAL-RISK-REGISTER-002 R-I | logical identity "
    "re-derivation executed; real auth deferred to STATE-EV-005 (+Security)",
)


def _l3_argv(evidence_root: Path, *, priors: list[str], **overrides) -> list[str]:
    argv = [
        "--register-csv",
        str(_hermetic_register(evidence_root)),
        "--evidence-id",
        "STATE-EV-004",
        "--node",
        f"{_L3_NODE} | EV-L3 §4 crash catalog (harness self-test)",
        "--primary-adr",
        "ADR-002-005",
        "--seed-policy",
        overrides.get("seed_policy", "fixed:0"),
        "--evidence-level-stage",
        "EV-L3",
        "--fault-catalog-ref",
        overrides.get("catalog_ref", _L3_CATALOG_REF),
        "--expected-fault-count",
        str(overrides.get("expected_scenario_count", _L3_CATALOG_SIZE)),
        "--covered-axis",
        "STATE-EV-004: persistence + process + reconstruction ONLY",
        "--residual-ref",
        "R-N network; R-I credential-identity; R-D power-loss durability",
        "--evidence-root",
        str(evidence_root),
        # the L3 suite is new work in this branch, so its bytes may be uncommitted;
        # the dirt is then recorded in-band rather than hiding the run.
        "--allow-dirty-targets",
    ]
    for prior in priors:
        argv += ["--prior-stage-run", prior]
    for axis in overrides.get("modeled_axes", _L3_MODELED_AXES):
        argv += ["--modeled-axis", axis]
    return argv


@pytest.fixture(scope="module")
def l3_package(tmp_path_factory, module_monkeypatch):
    """STATE-EV-001 EV-L1 -> EV-L2, then STATE-EV-004 EV-L3 binding both.

    The real staged shape design §6.2 gate 4 requires: the crash run's durable evidence
    attaches to a **non-stale** STATE-EV-001 model base, so both of that row's earlier
    stages are executed at this same baseline and bound here.
    """
    root = tmp_path_factory.mktemp("evidence-l3")
    clock = {"now": datetime(2026, 8, 6, 6, 0, 0, tzinfo=UTC)}

    def _now():
        return clock["now"]

    def advance(seconds: int = 1):
        clock["now"] = clock["now"] + timedelta(seconds=seconds)
        return clock["now"]

    module_monkeypatch.setattr(ev, "_utc_now", _now)

    rc_l1 = ev.main(
        [
            "--register-csv",
            str(_hermetic_register(root)),
            "--evidence-id",
            "STATE-EV-001",
            "--node",
            f"{_SMOKE_NODE} | EV-L1 stage (harness self-test)",
            "--primary-adr",
            "ADR-002-005",
            "--seed-policy",
            "fixed:0",
            "--evidence-root",
            str(root),
        ]
    )
    assert rc_l1 == 0
    l1_run = next((root / "STATE-EV-001").iterdir())

    advance()
    rc_l2 = ev.main(
        [
            "--register-csv",
            str(_hermetic_register(root)),
            "--evidence-id",
            "STATE-EV-001",
            "--node",
            f"{_L2_STATE_NODE} | EV-L2 §3 fault catalog (harness self-test)",
            "--primary-adr",
            "ADR-002-005",
            "--seed-policy",
            "fixed:0",
            "--evidence-level-stage",
            "EV-L2",
            "--fault-catalog-ref",
            "docs/plans/2026-07-29-tos-ev-l2-pilot-design.md#3",
            "--expected-fault-count",
            str(_L2_STATE_CATALOG_SIZE),
            "--covered-axis",
            "storage-independent representability (durable limb NOT covered)",
            "--residual-ref",
            "R-1 durable limb",
            "--prior-stage-run",
            f"STATE-EV-001/{l1_run.name} | L1 traceability",
            "--evidence-root",
            str(root),
            "--allow-dirty-targets",
        ]
    )
    assert rc_l2 == 0, "the EV-L2 prior stage must be green for the L3 binding"
    l2_run = next(p for p in (root / "STATE-EV-001").iterdir() if p != l1_run)

    advance()
    priors = [
        f"STATE-EV-001/{l1_run.name} | L1 model base",
        f"STATE-EV-001/{l2_run.name} | L2 component-fault base",
    ]
    rc_l3 = ev.main(_l3_argv(root, priors=priors))
    l3_run = next(iter((root / "STATE-EV-004").iterdir()))
    manifest = yaml.safe_load((l3_run / "manifest.yaml").read_text(encoding="utf-8"))
    baseline = yaml.safe_load((l3_run / "baseline.yaml").read_text(encoding="utf-8"))
    return {
        "root": root,
        "l1_run": l1_run,
        "l2_run": l2_run,
        "priors": priors,
        "run": l3_run,
        "rc": rc_l3,
        "manifest": manifest,
        "baseline": baseline,
        "advance": advance,
    }


def test_l3_manifest_is_v3_and_a_strict_superset_of_v2(
    l3_package: dict, l2_package: dict, manifest: dict
) -> None:
    """design §6.1 — v3 ADDS field groups; it drops no v1 or v2 field."""
    l3 = l3_package["manifest"]
    assert l3["schema"] == "tos-evidence/manifest/v3"
    assert l3["evidence_level_stage"] == "EV-L3"
    assert set(manifest) <= set(l3), "a v1 top-level field was dropped by v3"
    v2_carried = set(l2_package["manifest"]) - {"fault_injection"}
    assert v2_carried <= set(l3), "a v2 top-level field was dropped by v3"
    assert set(manifest["claim"]) <= set(l3["claim"])
    assert l3["claim"]["closes_evidence_item"] is False
    assert l3["claim"]["register_status_moved_by_this_run"] is False
    assert l3["claim"]["independent_review"] == "NOT_SIGNED (VER §9.5)"
    # fault_injection is an EV-L2 block: the two schedules have different row shapes
    # and different gates, so v3 carries crash_injection instead of renaming it.
    assert "fault_injection" not in l3
    assert l3["baseline"]["file"] == "baseline.yaml"
    assert l3_package["baseline"]["schema"] == "tos-evidence/baseline/v3"


def test_l3_discipline_tag_is_the_l3_wording(l3_package: dict) -> None:
    tag = l3_package["manifest"]["discipline_tag"]
    assert tag == ev.DISCIPLINE_TAG_L3
    assert "not a row PASS" in tag
    assert "restart coverage argument" in tag
    assert "network/identity residuals" in tag
    assert "independent review" in tag


def test_l3_crash_injection_group_recounts_the_schedule(l3_package: dict) -> None:
    """crash_scenario_count is recounted from the artifact, never taken from the catalog."""
    run = l3_package["run"]
    crash = l3_package["manifest"]["crash_injection"]
    lines = [
        line
        for line in (run / "crash-timeline.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert crash["crash_scenario_count"] == len(lines) == _L3_CATALOG_SIZE
    assert crash["schedule_artifact"] == "crash-timeline.jsonl"
    assert crash["seed"] == 0
    assert crash["catalog_ref"] == _L3_CATALOG_REF
    assert crash["all_crash_scenarios_met"] is True
    assert crash["deviation_scenarios"] == []
    assert crash["expected_undefined_scenarios"] == []
    assert crash["duplicate_scenario_ids"] == []
    assert crash["crash_scenario_count_matches_catalog"] is True


def test_l3_crash_timeline_rows_carry_every_section_6_1_field(l3_package: dict) -> None:
    """design §6.1 — the exact row shape, incl. MEASURED pids and store bytes."""
    run = l3_package["run"]
    rows = [
        json.loads(line)
        for line in (run / "crash-timeline.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert len(rows) == _L3_CATALOG_SIZE
    for row in rows:
        assert list(row) == [
            "scenario_id",
            "evidence_id",
            "target_component",
            "crash_point",
            "crash_exit_status",
            "seed",
            "writer_pid",
            "reader_pid",
            "store_real_on_disk",
            "store_bytes",
            "expected_reconstruction",
            "observed_reconstruction",
            "outcome",
        ]
        assert row["seed"] == 0
        assert row["outcome"] == "MET"
        assert row["evidence_id"] == "STATE-EV-004"
        assert row["writer_pid"] != row["reader_pid"]
        assert row["store_real_on_disk"] is True and row["store_bytes"] > 0
        assert row["expected_reconstruction"] == row["observed_reconstruction"]
    assert len({row["scenario_id"] for row in rows}) == _L3_CATALOG_SIZE


def test_l3_crash_timeline_is_covered_by_the_sums_file(l3_package: dict) -> None:
    """The schedule is part of the artifact closure (VER §9.1 + §9.2)."""
    run = l3_package["run"]
    sums = (run / "sha256sums.txt").read_text(encoding="utf-8")
    assert "crash-timeline.jsonl" in sums
    names = {entry["name"] for entry in l3_package["manifest"]["artifacts"]}
    assert "crash-timeline.jsonl" in names
    assert "fault-timeline.jsonl" not in names


def test_l3_integration_boundary_records_persistence_and_the_process_boundary(
    l3_package: dict,
) -> None:
    """design §6.1 — the v3 field group, with both boundary facts measured."""
    boundary = l3_package["manifest"]["integration_boundary"]
    persistence = boundary["persistence"]
    assert "sqlite3" in persistence["technology"]
    assert "PILOT-SCOPE" in persistence["technology"]
    # the over-claim guard: the pilot-scope substrate is NOT the ADR §4 decision
    assert "NOT the ADR-002-005 §4" in persistence["technology"]
    assert persistence["real_on_disk"] is True
    assert persistence["substrate_check"]["met"] is True
    assert all(size > 0 for size in persistence["measured_store_bytes"])

    process = boundary["process_boundary"]
    assert len(process["writer_pids"]) == _L3_CATALOG_SIZE
    assert set(process["writer_pids"]).isdisjoint(set(process["reader_pids"]))
    assert process["distinct_per_scenario"] is True
    assert "os._exit" in process["crash_mechanism"]
    assert process["observed_crash_exit_statuses"] == [137]
    assert len(process["crash_points"]) == _L3_CATALOG_SIZE


def test_l3_modeled_axes_each_name_the_residual_that_carries_them(
    l3_package: dict,
) -> None:
    """design §6.2 gate 5 — an axis cannot be declared modelled without a residual."""
    boundary = l3_package["manifest"]["integration_boundary"]
    assert boundary["modeled_axis_residual_declared"] is True
    axes = boundary["modeled_axes"]
    assert {axis["axis"] for axis in axes} == {"network", "credential_identity"}
    for axis in axes:
        assert axis[
            "residual_ref"
        ], "a modelled axis without a residual is an over-claim"
        assert axis["disposition"] in {"MODELED", "DEFERRED"}
        assert axis["note"] != "UNSPECIFIED"
    network = next(axis for axis in axes if axis["axis"] == "network")
    assert "R-N" in network["residual_ref"]
    assert "zero real bytes" in network["note"]


def test_l3_prior_stage_runs_bind_both_earlier_stages_of_state_ev_001(
    l3_package: dict,
) -> None:
    """design §6.2 gate 4 — L1 AND L2, same evidence id, same baseline."""
    priors = l3_package["manifest"]["prior_stage_runs"]
    assert len(priors) == 2
    assert {p["stage"] for p in priors} == {"EV-L1", "EV-L2"}
    for prior in priors:
        assert prior["evidence_id"] == ev.L3_PRIOR_STAGE_EVIDENCE_ID == "STATE-EV-001"
        assert prior["baseline_matches_this_run"] is True
        assert len(prior["baseline_commit_sha"]) == 40
        assert prior["outcome"] == "ALL_SELECTED_TESTS_GREEN"
    l1 = next(p for p in priors if p["stage"] == "EV-L1")
    expected_digest = hashlib.sha256(
        (l3_package["l1_run"] / "sha256sums.txt").read_bytes()
    ).hexdigest()
    assert l1["sha256sums_digest"] == expected_digest


def test_l3_run_is_green_when_every_stage_gate_is_met(l3_package: dict) -> None:
    assert l3_package["manifest"]["claim"]["ev_l3_stage_gates_unmet"] == []
    assert l3_package["manifest"]["execution"]["outcome"] == "ALL_SELECTED_TESTS_GREEN"
    assert l3_package["manifest"]["execution"]["stage_gate_outcome"] == (
        "EV_L3_STAGE_GATES_MET"
    )
    assert l3_package["rc"] == 0
    assert l3_package["manifest"]["claim"]["stages_executed"] == [
        "EV-L1",
        "EV-L2",
        "EV-L3",
    ]
    assert l3_package["manifest"]["claim"]["covered_axis"]


def test_l3_claims_no_pass_and_no_closure(l3_package: dict) -> None:
    """The invariant the whole harness exists for, re-asserted at the new stage."""
    claim = l3_package["manifest"]["claim"]
    assert claim["closes_evidence_item"] is False
    assert claim["register_status_moved_by_this_run"] is False
    assert claim["register_status_at_run_time"] == _HERMETIC_REGISTER_STATUS
    assert "PASS" not in claim["covered_axis"]
    assert (
        claim["p0_1_bounds_approval"]
        == ev.read_profile_approval(_REPO_ROOT)["p0_1_bounds_approval"]
    )
    dumped = yaml.safe_dump(l3_package["manifest"], allow_unicode=True)
    assert "register_status_moved_by_this_run: false" in dumped


def test_l3_coverage_argument_states_the_restart_axis_and_is_not_discharged(
    l3_package: dict,
) -> None:
    """VER §2.7 — the restart-axis legs are stated, and NOT claimed discharged."""
    coverage = l3_package["manifest"]["coverage_argument"]
    assert coverage["boundary_values"] == ev.COVERAGE_BOUNDARY_VALUES_L3
    assert "crash-point" in coverage["boundary_values"]
    assert "ADR-002-021" in coverage["adverse_scenario_set"]
    assert coverage["unexercised_residual_ref"], "residual pointers must be recorded"
    assert coverage["discharged"] is False


def test_l3_baseline_keeps_the_ver3_gap_with_the_l3_attribution(
    l3_package: dict,
) -> None:
    """design §6.3 — M2 inherited: the note is updated, the gap is retained."""
    baseline = l3_package["baseline"]
    ver3 = baseline["ver_002_001_section_3_baseline"]
    assert list(ver3) == _VER3_FIELDS, "all 22 fields survive the stage change"
    for field in _MUST_BE_NOT_APPLICABLE:
        entry = ver3[field]
        assert entry["status"] == ev.NOT_APPLICABLE_L3
        assert entry["reason"], "the reason is retained, not dropped"
        assert "value" not in entry
    assert ev.NOT_APPLICABLE_L3 == "NOT_APPLICABLE_MODELED_TRANSPORT_L3"
    assert ev.NOT_APPLICABLE_L3 in baseline["contract"]["completeness"]
    assert "NOT complete" in baseline["contract"]["completeness"]
    unmet = baseline["ver_002_001_section_3_unmet_fields"]
    assert unmet == sorted(
        name for name, entry in ver3.items() if entry["status"] != ev.RECORDED
    )
    assert set(_MUST_BE_NOT_APPLICABLE) <= set(unmet)


def test_l3_baseline_restates_the_schema_field_honestly(l3_package: dict) -> None:
    """The one reason EV-L1's wording would have made false at EV-L3.

    "exercises no persistence substrate" is not true of a stage whose whole subject is a
    durable store. The field stays N/A — there is no migration history to record — but
    for the reason that actually applies, and it repeats that the substrate is
    pilot-scope rather than the ADR §4 project decision.
    """
    entry = l3_package["baseline"]["ver_002_001_section_3_baseline"][
        "database_schema_migration_version"
    ]
    assert entry["status"] == ev.NOT_APPLICABLE_L3
    assert "exercises no persistence substrate" not in entry["reason"]
    assert "PILOT-SCOPE" in entry["reason"]
    assert "§4 line 61" in entry["reason"]


def test_l3_baseline_completes_the_fault_schedule_field(l3_package: dict) -> None:
    """VER §3 ``fault_injection_schedule_and_seed`` carries the crash schedule at L3."""
    entry = l3_package["baseline"]["ver_002_001_section_3_baseline"][
        "fault_injection_schedule_and_seed"
    ]
    assert entry["status"] == ev.RECORDED
    assert entry["value"]["fault_schedule"]["crash_scenario_count"] == _L3_CATALOG_SIZE
    assert entry["value"]["seed"]["hypothesis_seed"] == 0
    assert "crash schedule" in entry["reason"]


# ---- the six EV-L3 gates, both ways ---------------------------------------


def _crash_row(scenario_id: str, **overrides) -> dict:
    """A well-formed crash row (observed == expected, real boundary, real store)."""
    row = {
        "scenario_id": scenario_id,
        "evidence_id": "STATE-EV-004",
        "crash_point": "AFTER_COMPLETE_DURABLE_COMMIT",
        "crash_exit_status": 137,
        "writer_pid": 1001,
        "reader_pid": 1002,
        "store_real_on_disk": True,
        "store_bytes": 4096,
        "expected_reconstruction": "INTENT=ACTIVE|KNOWLEDGE=UNOBSERVED",
        "observed_reconstruction": "INTENT=ACTIVE|KNOWLEDGE=UNOBSERVED",
        "outcome": "MET",
    }
    row.update(overrides)
    return row


def test_a_well_formed_crash_schedule_is_met() -> None:
    summary = ev.summarise_crash_schedule(
        [_crash_row("L3-01"), _crash_row("L3-02")],
        expected_scenario_count=2,
        evidence_id="STATE-EV-004",
    )
    assert summary["all_crash_scenarios_met"] is True
    assert summary["process_boundary_real"] is True
    assert summary["persistence_real_measured"] is True


@pytest.mark.parametrize(
    "rows,reason",
    [
        ([], "an empty schedule is not 'no violations found'"),
        (
            [_crash_row("L3-01", observed_reconstruction="INTENT=CLOSED")],
            "observed != expected",
        ),
        (
            [_crash_row("L3-01", expected_reconstruction="")],
            "an unstated Expected cannot be falsified",
        ),
        (
            [_crash_row("L3-01", observed_reconstruction="")],
            "an unobserved reconstruction proves nothing",
        ),
        (
            [_crash_row("L3-01", writer_pid=1001, reader_pid=1001)],
            "a shared pid is an in-process fallback wearing EV-L3's name",
        ),
        (
            [_crash_row("L3-01", writer_pid=0)],
            "a non-positive pid is not a real process",
        ),
        (
            [_crash_row("L3-01", store_real_on_disk=False)],
            "an in-memory store is the EV-L2 C1 defect recurring",
        ),
        (
            [_crash_row("L3-01", store_bytes=0)],
            "an empty store file evidences nothing",
        ),
        (
            [_crash_row("L3-01"), _crash_row("L3-01")],
            "a duplicated scenario id inflates the recount",
        ),
        (
            [_crash_row("L3-01", evidence_id="STATE-EV-003")],
            "a row from another evidence id",
        ),
    ],
)
def test_all_crash_scenarios_met_is_withheld_on_every_defective_schedule(
    rows: list[dict], reason: str
) -> None:
    summary = ev.summarise_crash_schedule(rows, evidence_id="STATE-EV-004")
    assert summary["all_crash_scenarios_met"] is False, reason


def test_a_crash_row_that_misreports_its_own_outcome_is_caught() -> None:
    """The row's ``outcome`` is cross-checked against the re-derivation, never believed."""
    lying = _crash_row("L3-01", observed_reconstruction="INTENT=CLOSED", outcome="MET")
    summary = ev.summarise_crash_schedule([lying], evidence_id="STATE-EV-004")
    assert summary["misreported_outcome_scenarios"] == ["L3-01"]
    assert summary["deviation_scenarios"] == ["L3-01"]
    assert summary["all_crash_scenarios_met"] is False


def test_a_recount_that_disagrees_with_the_crash_catalog_withholds_green() -> None:
    """Deselecting one scenario must not shrink the evidence silently."""
    summary = ev.summarise_crash_schedule(
        [_crash_row("L3-01")],
        expected_scenario_count=8,
        evidence_id="STATE-EV-004",
    )
    assert summary["crash_scenario_count"] == 1
    assert summary["crash_scenario_count_matches_catalog"] is False
    assert summary["all_crash_scenarios_met"] is False


def test_a_malformed_crash_schedule_line_is_refused_not_skipped(tmp_path) -> None:
    path = tmp_path / "crash-timeline.jsonl"
    path.write_text('{"scenario_id": "L3-01"}\nnot json\n', encoding="utf-8")
    with pytest.raises(ev.HarnessError, match="not valid JSON"):
        ev.read_crash_timeline(path)


def test_an_absent_crash_schedule_reads_as_empty_and_withholds_green(tmp_path) -> None:
    rows = ev.read_crash_timeline(tmp_path / "nothing.jsonl")
    assert rows == []
    assert (
        ev.summarise_crash_schedule(rows, evidence_id="STATE-EV-004")[
            "all_crash_scenarios_met"
        ]
        is False
    )


def test_the_persistence_substrate_is_measured_from_the_executed_source() -> None:
    """gate 3's source half — measured against the real repository."""
    result = ev.check_persistence_substrate(_REPO_ROOT)
    assert result["met"] is True, result
    assert result["measured"]["connect_call_sites"] == 1
    assert result["measured"]["literal_connection_targets"] == []
    assert result["measured"]["in_memory_tokens_present"] == []
    assert result["measured"]["pragmas_present"] == sorted(
        ev.PERSISTENCE_REQUIRED_PRAGMAS
    )


def test_the_persistence_substrate_check_catches_an_in_memory_store(tmp_path) -> None:
    """The other way: a store that opened ``:memory:`` is unmet, not ignored."""
    rel = ev.PERSISTENCE_SUBSTRATE_PATH
    (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / rel).write_text(
        "import sqlite3\n"
        "def open_store():\n"
        '    return sqlite3.connect(":memory:")\n',
        encoding="utf-8",
    )
    result = ev.check_persistence_substrate(tmp_path)
    assert result["met"] is False
    assert result["measured"]["literal_connection_targets"] == [":memory:"]
    assert result["measured"]["in_memory_tokens_present"] == [":memory:"]


def test_the_persistence_substrate_check_requires_both_pragmas(tmp_path) -> None:
    rel = ev.PERSISTENCE_SUBSTRATE_PATH
    (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / rel).write_text(
        "import sqlite3\n"
        "def open_store(path):\n"
        "    conn = sqlite3.connect(str(path))\n"
        '    conn.execute("PRAGMA journal_mode=WAL")\n'
        "    return conn\n",
        encoding="utf-8",
    )
    result = ev.check_persistence_substrate(tmp_path)
    assert result["met"] is False
    assert result["measured"]["pragmas_present"] == ["journal_mode=WAL"]
    assert result["measured"]["pragmas_missing"] == ["synchronous=FULL"]


def test_a_docstring_that_names_the_pragma_cannot_satisfy_the_check(tmp_path) -> None:
    """The deceptive fixture: documented ``FULL``, executed ``OFF``.

    This is not hypothetical. The real store module documents its substrate decision in
    its module docstring and in ``__init__``'s docstring, and while this check scanned
    the file for the token, lowering the actual ``PRAGMA synchronous=FULL`` to ``OFF``
    left the gate green — the docstrings satisfied it (measured). The earlier fixture
    could not expose that, because it carried no docstring for the token to hide in.

    A substrate whose durability setting is a sentence rather than a statement is the
    exact ``persistence_real`` over-claim gate 3 exists to prevent.
    """
    rel = ev.PERSISTENCE_SUBSTRATE_PATH
    (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / rel).write_text(
        '"""Durable store using journal_mode=WAL and synchronous=FULL (design §3.2)."""\n'
        "import sqlite3\n"
        "def open_store(path):\n"
        '    """Open at journal_mode=WAL / synchronous=FULL."""\n'
        "    conn = sqlite3.connect(str(path))\n"
        "    # synchronous=FULL is the ratified pilot substrate decision\n"
        '    conn.execute("PRAGMA journal_mode=WAL")\n'
        '    conn.execute("PRAGMA synchronous=OFF")\n'
        "    return conn\n",
        encoding="utf-8",
    )
    result = ev.check_persistence_substrate(tmp_path)
    assert (
        result["met"] is False
    ), "a documented-but-not-executed pragma satisfied gate 3"
    assert result["measured"]["pragmas_missing"] == ["synchronous=FULL"]
    # what is really executed is reported, so the manifest names the actual setting
    assert result["measured"]["executed_pragmas"] == {
        "journal_mode": "WAL",
        "synchronous": "OFF",
    }


def test_the_substrate_check_reads_pragmas_only_from_execute_arguments(
    tmp_path,
) -> None:
    """Both ways: the same tokens in real ``execute`` arguments DO satisfy it.

    Paired with the deceptive fixture above, this pins the discrimination itself — the
    check distinguishes *executed* from *mentioned*, rather than rejecting everything.
    """
    rel = ev.PERSISTENCE_SUBSTRATE_PATH
    (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / rel).write_text(
        '"""A store module with no pragma tokens in its prose at all."""\n'
        "import sqlite3\n"
        "def open_store(path):\n"
        "    conn = sqlite3.connect(str(path))\n"
        '    conn.execute("PRAGMA journal_mode=WAL")\n'
        '    conn.execute("PRAGMA synchronous=FULL")\n'
        "    return conn\n",
        encoding="utf-8",
    )
    result = ev.check_persistence_substrate(tmp_path)
    assert result["met"] is True, result
    assert result["measured"]["pragmas_missing"] == []
    assert result["measured"]["executed_pragmas"] == {
        "journal_mode": "WAL",
        "synchronous": "FULL",
    }


def test_an_absent_or_unparseable_substrate_is_unmet_not_ignored(tmp_path) -> None:
    assert ev.check_persistence_substrate(tmp_path)["met"] is False
    rel = ev.PERSISTENCE_SUBSTRATE_PATH
    (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / rel).write_text("def broken(:\n", encoding="utf-8")
    result = ev.check_persistence_substrate(tmp_path)
    assert result["met"] is False
    assert "SOURCE_DOES_NOT_PARSE" in result["reason"]


def test_a_modeled_axis_without_a_residual_is_refused() -> None:
    with pytest.raises(ev.HarnessError, match="empty axis / disposition / residual"):
        ev.parse_modeled_axis_spec("network | MODELED |  | note")
    with pytest.raises(ev.HarnessError, match="expects"):
        ev.parse_modeled_axis_spec("network | MODELED")


def test_parse_modeled_axis_spec_keeps_a_note_containing_separators() -> None:
    axis = ev.parse_modeled_axis_spec("network | MODELED | R-N | zero bytes | policy")
    assert axis == {
        "axis": "network",
        "disposition": "MODELED",
        "residual_ref": "R-N",
        "note": "zero bytes | policy",
    }


def test_ev_l3_requires_its_unmeasurable_claims_to_be_stated(tmp_path) -> None:
    """Each EV-L3 claim the harness cannot measure must be supplied, not defaulted."""
    root = tmp_path / "evidence"
    base = _l3_argv(root, priors=["STATE-EV-001/whatever | note"])
    for flag in ("--covered-axis", "--fault-catalog-ref"):
        argv = list(base)
        argv[argv.index(flag) + 1] = ""
        assert ev.main(argv) == 2
    # and the EV-L3-only one: a stage with no declared modelled axis would read as if
    # all three VER §5 boundaries had been real
    no_axes = _l3_argv(root, priors=["STATE-EV-001/whatever | note"], modeled_axes=())
    assert ev.main(no_axes) == 2


def test_modeled_axis_is_refused_on_a_non_l3_run(tmp_path) -> None:
    root = tmp_path / "evidence"
    argv = _argv(root) + ["--modeled-axis", "network | MODELED | R-N | note"]
    assert ev.main(argv) == 2


def test_l3_gate_fires_end_to_end_when_a_prior_stage_is_missing(
    l3_package: dict,
) -> None:
    """gate 4 both ways: binding only EV-L1 withholds GREEN and the claims with it."""
    root = l3_package["root"]
    l3_package["advance"](60)
    rc = ev.main(
        _l3_argv(
            root,
            priors=[f"STATE-EV-001/{l3_package['l1_run'].name} | L1 only"],
        )
    )
    assert rc == 1, "a run missing the EV-L2 prior stage must not be green"
    run = max((root / "STATE-EV-004").iterdir(), key=lambda p: p.name)
    manifest = yaml.safe_load((run / "manifest.yaml").read_text(encoding="utf-8"))
    gates = manifest["claim"]["ev_l3_stage_gates_unmet"]
    assert "PRIOR_EV_L1_AND_L2_NOT_BOTH_BOUND_AT_THIS_BASELINE" in gates
    # the withheld claim is NAMED, not silently emitted
    assert manifest["claim"]["stages_executed"] == "WITHHELD (EV-L3 stage gate unmet)"
    assert "WITHHELD" in manifest["claim"]["covered_axis"]
    assert manifest["claim"]["invoked_covered_axis"]
    assert "EV_L3_STAGE_GATE_UNMET" in manifest["execution"]["stage_gate_outcome"]
    # the tests themselves still passed — that fact is preserved verbatim
    assert manifest["execution"]["outcome"] == "ALL_SELECTED_TESTS_GREEN"


def test_l3_gate_fires_when_the_bound_priors_belong_to_another_evidence_row(
    l3_package: dict,
) -> None:
    """design §6.2 MINOR-2 — the prior stages must be STATE-EV-001's, not any row's.

    STATE-EV-003 is also registered at ``EV-L1/3``, so without the evidence-id check two
    perfectly valid stages of a completely unrelated row would satisfy the durable-limb
    continuity gate. Run end to end against real packages rather than by re-stating the
    predicate: a test that recomputes the condition it is checking proves only that the
    test can compute it.
    """
    root = l3_package["root"]
    advance = l3_package["advance"]

    advance(300)
    assert (
        ev.main(
            [
                "--register-csv",
                str(_hermetic_register(root)),
                "--evidence-id",
                "STATE-EV-003",
                "--node",
                f"{_SMOKE_NODE} | EV-L1 stage of the WRONG row",
                "--primary-adr",
                "ADR-002-005",
                "--seed-policy",
                "fixed:0",
                "--evidence-root",
                str(root),
            ]
        )
        == 0
    )
    wrong_l1 = next(iter((root / "STATE-EV-003").iterdir()))

    advance()
    assert (
        ev.main(
            [
                "--register-csv",
                str(_hermetic_register(root)),
                "--evidence-id",
                "STATE-EV-003",
                "--node",
                f"{_L2_STATE_NODE} | EV-L2 stage of the WRONG row",
                "--primary-adr",
                "ADR-002-005",
                "--seed-policy",
                "fixed:0",
                "--evidence-level-stage",
                "EV-L2",
                "--fault-catalog-ref",
                "docs/plans/2026-07-29-tos-ev-l2-pilot-design.md#3",
                "--expected-fault-count",
                str(_L2_STATE_CATALOG_SIZE),
                "--covered-axis",
                "the wrong row's axis",
                "--prior-stage-run",
                f"STATE-EV-003/{wrong_l1.name} | wrong row L1",
                "--evidence-root",
                str(root),
                "--allow-dirty-targets",
            ]
        )
        # this run's own fault rows carry evidence_id STATE-EV-001, so its schedule
        # gate is unmet — irrelevant here: what matters is that a CLOSED, tests-green
        # package exists to be bound.
        in (0, 1)
    )
    wrong_l2 = next(p for p in (root / "STATE-EV-003").iterdir() if p != wrong_l1)

    advance()
    rc = ev.main(
        _l3_argv(
            root,
            priors=[
                f"STATE-EV-003/{wrong_l1.name} | wrong row L1",
                f"STATE-EV-003/{wrong_l2.name} | wrong row L2",
            ],
        )
    )
    assert rc == 1, "another row's L1 ∧ L2 must not satisfy the continuity gate"
    run = max((root / "STATE-EV-004").iterdir(), key=lambda p: p.name)
    manifest = yaml.safe_load((run / "manifest.yaml").read_text(encoding="utf-8"))
    assert "PRIOR_EV_L1_AND_L2_NOT_BOTH_BOUND_AT_THIS_BASELINE" in (
        manifest["claim"]["ev_l3_stage_gates_unmet"]
    )
    # both stages WERE bound and both ARE at this baseline — only the row differs
    priors = manifest["prior_stage_runs"]
    assert {p["stage"] for p in priors} == {"EV-L1", "EV-L2"}
    assert all(p["baseline_matches_this_run"] is True for p in priors)
    assert {p["evidence_id"] for p in priors} == {"STATE-EV-003"}


def test_an_unpinned_seed_withholds_green_on_an_ev_l3_run(l3_package: dict) -> None:
    """VER §9.1 — an unreproducible crash schedule is not evidence."""
    root = l3_package["root"]
    l3_package["advance"](120)
    rc = ev.main(_l3_argv(root, priors=l3_package["priors"], seed_policy="default"))
    assert rc == 1
    run = max((root / "STATE-EV-004").iterdir(), key=lambda p: p.name)
    manifest = yaml.safe_load((run / "manifest.yaml").read_text(encoding="utf-8"))
    assert "SEED_NOT_PINNED" in manifest["claim"]["ev_l3_stage_gates_unmet"]
