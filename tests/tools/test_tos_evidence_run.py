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
from datetime import UTC, datetime
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


def _argv(evidence_root: Path, *, evidence_id: str = "STATE-EV-001") -> list[str]:
    return [
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


def test_verification_profile_is_recorded_as_proposed(baseline: dict) -> None:
    entry = baseline["ver_002_001_section_3_baseline"]["verification_profile_version"]
    assert entry["status"] == ev.RECORDED
    assert entry["value"]["version"] == "2.1 (PROPOSED — P0-1 open)"
    assert "P0-1" in entry["value"]["approval_state"]


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
