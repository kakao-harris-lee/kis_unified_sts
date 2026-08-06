# EVL3 Ladder Review Packet v1 — baseline 12dd4077 (2026-08-06)
Five evidence packages produced consecutively at one baseline commit
(no intervening commits): STATE-EV-001 EV-L1 -> SPG-EV-002 EV-L1 ->
STATE-EV-001 EV-L2 -> SPG-EV-002 EV-L2 -> STATE-EV-004 EV-L3 (the
first EV-L3 execution in register history). All files below are
verbatim from disk. Source files carry line numbers for anchor
verification. Nothing outside this packet was available to the
reviewer.


============================================================================
# PACKAGE tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077
============================================================================

---- FILE tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/baseline.yaml ----
```
schema: tos-evidence/baseline/v1
run_id: 20260806T015629Z-12dd4077
evidence_id: STATE-EV-001
evidence_level_stage: EV-L1
generated_utc: '2026-08-06T01:56:29.830478+00:00'
contract:
  run_manifest_contract: docs/plans/2026-07-20-tos-boundary-and-import-firewall-design.md §5.1 (seven
    items)
  ver_specification: tos-spec/src/part-1-foundation/VER-002-001-Safety-Critical-Architecture-Verification-Evidence-Specification.md
    §2.3/§3/§8/§9.1/§9.2/§9.5
  completeness: 'EV-L1 subset. VER §3 requires 22 baseline fields and states that ''A run without a complete
    baseline is invalid''; design #1 §5.1 ratifies the seven items below as the EV-L1 subset. Fields whose
    artifacts do not exist at this stage are marked NOT_APPLICABLE_EV_L1 with a reason. Under VER §3''s
    full standard this baseline is complete for EV-L1 only and is NOT a complete baseline for EV-L2 and
    above.'
evidence_register_row:
  source: tos-spec/src/part-1-foundation/verification/EVIDENCE-REGISTER-002.csv
  evidence_id: STATE-EV-001
  domain: Orthogonal State
  title: Orthogonal Composite Persistence
  primary_adr: ADR-002-005
  criticality: Critical
  minimum_evidence_level: EV-L1/2
  status_at_run_time: READY
  implementation_owner: ai-impl(claude-orchestrated)
  evidence_owner: operator
  independent_reviewer: ai-review(decorrelated)+operator-countersign
design1_5_1:
  item_1_repository_and_package:
    git_commit_sha: 12dd40778b0237ea6992a3b0a9ecadb10f865f0f
    git_short_sha: 12dd4077
    tos_package_version: 0.0.1
    worktree:
      clean: true
      untracked: []
      modified_unstaged: []
      staged: []
      all_dirty_paths: []
      note: 'A non-empty list does not by itself invalidate the run: the executed files are pinned individually
        by target_file_digests below. Paths outside the executed set belong to other work in the same
        worktree.'
    worktree_after_run:
      clean: false
      untracked:
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/junit.xml
      modified_unstaged: []
      staged: []
      all_dirty_paths:
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/junit.xml
      note: 'A non-empty list does not by itself invalidate the run: the executed files are pinned individually
        by target_file_digests below. Paths outside the executed set belong to other work in the same
        worktree.'
    worktree_delta:
      became_dirty_during_run:
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/junit.xml
      became_clean_during_run: []
      stable: false
    target_files_clean: true
    target_files_stable_during_run: true
    target_file_digests:
    - path: tools/tos_evidence_run.py
      sha256_before_run: 562c52eebc1758ccf804b55c2eb03a1887a07014433d649ec0e01a7a143fb0aa
      sha256_after_run: 562c52eebc1758ccf804b55c2eb03a1887a07014433d649ec0e01a7a143fb0aa
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: false
    - path: tos/src/tos/orthostate/__init__.py
      sha256_before_run: c866fc0fd8dc7bb0961f7550e2d9e73d1dfc4819afbc341c1f23fe4e0b11f632
      sha256_after_run: c866fc0fd8dc7bb0961f7550e2d9e73d1dfc4819afbc341c1f23fe4e0b11f632
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/orthostate/_base.py
      sha256_before_run: 2c1b8bb6c73ee8f73697ecc5e33d149a80efd7fdf27550b2f148248a2b34a40e
      sha256_after_run: 2c1b8bb6c73ee8f73697ecc5e33d149a80efd7fdf27550b2f148248a2b34a40e
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/orthostate/predicates.py
      sha256_before_run: 7265e75af582048fba54d757e5344a9d467348738a37dec7898df4c30db897c0
      sha256_after_run: 7265e75af582048fba54d757e5344a9d467348738a37dec7898df4c30db897c0
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/orthostate/records.py
      sha256_before_run: 8dabc903e03d039fb5292d5094a7d87cb46f073965a163c12eb1c3f167285cd2
      sha256_after_run: 8dabc903e03d039fb5292d5094a7d87cb46f073965a163c12eb1c3f167285cd2
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/orthostate/state.py
      sha256_before_run: aa68710f84ab21ba93d68d132a607ecb8f139f1acabde6e515712dc9599de0b3
      sha256_after_run: aa68710f84ab21ba93d68d132a607ecb8f139f1acabde6e515712dc9599de0b3
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/orthostate/vocabulary.py
      sha256_before_run: 67dda3c7eed990f3150273fcf6f00e7ad8bca5bcf5fb101d37573f289fcc37d4
      sha256_after_run: 67dda3c7eed990f3150273fcf6f00e7ad8bca5bcf5fb101d37573f289fcc37d4
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/tests/orthostate/test_orthostate_composite.py
      sha256_before_run: b764693802b2494b1fe86f2c737f7756d8857f13a3a32b8e472b8fe3398b3003
      sha256_after_run: b764693802b2494b1fe86f2c737f7756d8857f13a3a32b8e472b8fe3398b3003
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/tests/orthostate/test_orthostate_coupling.py
      sha256_before_run: 0465aba77727992042312a199959d8f71c161b04940eec81c44a169de6eace65
      sha256_after_run: 0465aba77727992042312a199959d8f71c161b04940eec81c44a169de6eace65
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/tests/orthostate/test_orthostate_vocabulary.py
      sha256_before_run: eabf04b0f1a030b3066f00ba0065bab652f8286c60f7a08336736398f3f291f8
      sha256_after_run: eabf04b0f1a030b3066f00ba0065bab652f8286c60f7a08336736398f3f291f8
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
  item_2_interpreter_and_dependencies:
    python:
      version: 3.12.2
      version_full: 3.12.2 (main, Dec 11 2025, 16:36:08) [Clang 17.0.0 (clang-1700.4.4.1)]
      implementation: CPython
      executable: /Users/harris/Development/private/kis_unified_sts/.venv/bin/python
    installed_versions_measured:
      pydantic: 2.12.5
      hypothesis: 6.151.5
      pytest: 9.0.2
      numpy: 1.26.4
      pandas: 2.3.3
      pyyaml: 6.0.3
      tos: NOT_INSTALLED
    pinned_in_tos_pyproject:
      pydantic: 2.12.5
      numpy: 2.4.0
      pandas: 2.3.3
      pyyaml: 6.0.3
      pytest: 9.0.2
      hypothesis: 6.150.2
    pins_satisfied: false
    pin_vs_installed_drift:
    - distribution: hypothesis
      pinned: 6.150.2
      installed: 6.151.5
    - distribution: numpy
      pinned: 2.4.0
      installed: 1.26.4
    drift_note: 'pins_satisfied is the machine-readable claim; an empty drift list = the executed interpreter
      matches every pin. A non-empty list is recorded, not resolved: the installed version is what executed.'
  item_3_execution_environment: &id001
    os: Darwin
    os_release: 25.5.0
    machine: arm64
    platform: macOS-26.5.2-arm64-arm-64bit
    python_implementation: CPython
  item_4_harness_version: &id002
    harness_path: tools/tos_evidence_run.py
    harness_sha256: 562c52eebc1758ccf804b55c2eb03a1887a07014433d649ec0e01a7a143fb0aa
    harness_tracked: true
    harness_at_commit: aac2827bb5941603705da735ea079129ce3d942a
    harness_dirty: false
    pytest_version: 9.0.2
    note: 'design #1 §5.1 item 4 — Phase 1 harness version = git digest, which exists only once the harness
      is committed. Until then harness_at_commit is NOT_IN_COMMIT and harness_sha256 is the only identity
      of the code that ran.'
  item_5_seed_policy: &id003
    policy: fixed
    pytest_flags:
    - --hypothesis-seed=0
    hypothesis_seed: 0
    note: 'VER §9.1 append-only: seed pinned before the run began.'
  item_6_consumed_configuration_artifacts:
    status: NOT_APPLICABLE_EV_L1
    reason: 'No configuration artifact is consumed: bounds are hypothesis-injected generated values, not
      read from a profile, and the run is hermetic (no .env, no YAML).'
  item_7_retained_artifact_digests: Enumerated in manifest.yaml (artifacts) and closed over by sha256sums.txt,
    which is written last and covers every retained file including the manifest.
ver_002_001_section_3_baseline:
  repository_commit_sha:
    status: RECORDED
    value: 12dd40778b0237ea6992a3b0a9ecadb10f865f0f
  build_artifact_digest:
    status: NOT_APPLICABLE_EV_L1
    reason: 'Phase 1 executes from the source tree; no built distribution artifact is produced or consumed
      (design #1 §5.1 items 1/4 — the git digest stands in). The executed bytes are pinned individually
      by design1_5_1.item_1_repository_and_package.target_file_digests.'
  rfc_adr_versions:
    status: RECORDED
    value:
    - role: primary_adr
      path: tos-spec/src/part-1-foundation/ADR-002-005-Intent-Transmission-Attempt-Broker-Order-and-Knowledge-State-Model.md
      sha256: 025c02cf8638f6aed84faf22f724c47bbc0af390d3d189fa25ef065a8cd73d51
    - role: design_document
      path: docs/plans/2026-07-25-tos-orthogonal-state-design.md
      sha256: e2d9612bf26a48dfad6581d49d549229cdb247a59d20e616d87d43a4c2ddac49
    - role: ver_specification
      path: tos-spec/src/part-1-foundation/VER-002-001-Safety-Critical-Architecture-Verification-Evidence-Specification.md
      sha256: 217a43ab1b32e04fe6515316a7383c3e9e75bb177ed18c7c7e7267ca0a3c2a38
    - role: boundary_design_1
      path: docs/plans/2026-07-20-tos-boundary-and-import-firewall-design.md
      sha256: 2449f18d6088e21f601da623d27e6eff74066661f5d92116db2eda1a59b5a988
    reason: The corpus documents carry no separate version field; their content sha256 is the version
      identity.
  hard_safety_envelope_version:
    status: NOT_APPLICABLE_EV_L1
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L1 model/property run consumes none. Recorded N/A per design #1 §5.1 (EV-L1 subset of VER
      §3).'
  runtime_safety_profile_version:
    status: NOT_APPLICABLE_EV_L1
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L1 model/property run consumes none. Recorded N/A per design #1 §5.1 (EV-L1 subset of VER
      §3).'
  human_authority_policy_generation_and_digest:
    status: NOT_APPLICABLE_EV_L1
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L1 model/property run consumes none. Recorded N/A per design #1 §5.1 (EV-L1 subset of VER
      §3).'
  effective_principal_graph_generation_and_digest:
    status: NOT_APPLICABLE_EV_L1
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L1 model/property run consumes none. Recorded N/A per design #1 §5.1 (EV-L1 subset of VER
      §3).'
  evidence_integrity_policy_generation_and_digest:
    status: NOT_APPLICABLE_EV_L1
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L1 model/property run consumes none. Recorded N/A per design #1 §5.1 (EV-L1 subset of VER
      §3).'
  recovery_barrier_policy_generation_and_digest:
    status: NOT_APPLICABLE_EV_L1
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L1 model/property run consumes none. Recorded N/A per design #1 §5.1 (EV-L1 subset of VER
      §3).'
  critical_input_policy_generation_and_digest:
    status: NOT_APPLICABLE_EV_L1
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L1 model/property run consumes none. Recorded N/A per design #1 §5.1 (EV-L1 subset of VER
      §3).'
  venue_constraint_policy_generation_and_digest:
    status: NOT_APPLICABLE_EV_L1
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L1 model/property run consumes none. Recorded N/A per design #1 §5.1 (EV-L1 subset of VER
      §3).'
  trading_approval_policy_generation_and_digest:
    status: NOT_APPLICABLE_EV_L1
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L1 model/property run consumes none. Recorded N/A per design #1 §5.1 (EV-L1 subset of VER
      §3).'
  currentness_policy_generation_and_digest:
    status: NOT_APPLICABLE_EV_L1
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L1 model/property run consumes none. Recorded N/A per design #1 §5.1 (EV-L1 subset of VER
      §3).'
  restricted_live_trial_policy_generation_and_digest:
    status: NOT_APPLICABLE_EV_L1
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L1 model/property run consumes none. Recorded N/A per design #1 §5.1 (EV-L1 subset of VER
      §3).'
  broker_capability_profile_version:
    status: NOT_APPLICABLE_EV_L1
    reason: Evidence Register broker_capability_profile_version for this row = 'N/A'; the row's minimum
      evidence level (EV-L1/2) carries no +Broker suffix and no Broker Capability Profile instance exists
      (template only). P0-2 is not in this run's scope.
  verification_profile_version:
    status: RECORDED
    value:
      version: 2.1 (PROPOSED — P0-1 open)
      register_column_value: 2.1-PROPOSED
      artifact:
        path: tos-spec/src/part-1-foundation/verification/VERIFICATION-PROFILE-002.yaml
        sha256: d837c7e74b0fbe70d7cf2dfb30e412a29042577a0a38dcba22c649dd457d5064
      approval_state: PROPOSED — P0-1 (bounds approval) OPEN
    reason: Recorded, not approved. VER §6 numeric bounds remain unapproved; no bound value is consumed
      by this run (bounds are hypothesis-injected, not hardcoded).
  database_schema_migration_version:
    status: NOT_APPLICABLE_EV_L1
    reason: EV-L1 model/property verification exercises no persistence substrate; durable persistence
      is the deferred /2 stage.
  deployment_manifest_digest:
    status: NOT_APPLICABLE_EV_L1
    reason: 'Nothing is deployed: the kernel is non-transmitting and is executed in-process by pytest.'
  workload_identities_and_key_versions:
    status: NOT_APPLICABLE_EV_L1
    reason: No workload identity, credential, or key material is used — the run is hermetic (no network,
      no .env, no clock authority).
  environment_identifier:
    status: RECORDED
    value: *id001
  test_harness_version:
    status: RECORDED
    value: *id002
  fault_injection_schedule_and_seed:
    status: PARTIAL_EV_L1
    value:
      fault_schedule:
        status: NOT_APPLICABLE_EV_L1
        reason: 'Fault injection begins at EV-L2 (VER §5); design #1 §5.1 adds the §9.1 fault schedule
          on EV-L2 entry.'
      seed: *id003
ver_002_001_section_3_unmet_fields:
- broker_capability_profile_version
- build_artifact_digest
- critical_input_policy_generation_and_digest
- currentness_policy_generation_and_digest
- database_schema_migration_version
- deployment_manifest_digest
- effective_principal_graph_generation_and_digest
- evidence_integrity_policy_generation_and_digest
- fault_injection_schedule_and_seed
- hard_safety_envelope_version
- human_authority_policy_generation_and_digest
- recovery_barrier_policy_generation_and_digest
- restricted_live_trial_policy_generation_and_digest
- runtime_safety_profile_version
- trading_approval_policy_generation_and_digest
- venue_constraint_policy_generation_and_digest
- workload_identities_and_key_versions
ver_002_001_section_3_unmet_note: 'VER §3 line 109 (''A run without a complete baseline is invalid'')
  has no ''as applicable'' clause. This list names every field that is not RECORDED, so the gap is machine-checkable:
  an empty list would be the claim that the baseline is complete, and this run does not make that claim.'
test_nodes:
- tos/tests/orthostate/test_orthostate_composite.py
- tos/tests/orthostate/test_orthostate_vocabulary.py
- tos/tests/orthostate/test_orthostate_coupling.py::test_coupling_negative_fixtures_are_representable_and_flagged

```

---- FILE tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/junit.xml ----
```
<?xml version="1.0" encoding="utf-8"?><testsuites name="pytest tests"><testsuite name="pytest" errors="0" failures="0" skipped="0" tests="51" time="0.163" timestamp="2026-08-06T10:56:29.521142+09:00" hostname="ichihun-ui-MacBookPro.local"><testcase classname="tests.orthostate.test_orthostate_composite" name="test_all_14_fixtures_are_representable[cs-14-1]" time="0.001" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_all_14_fixtures_are_representable[cs-14-2]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_all_14_fixtures_are_representable[cs-14-3]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_all_14_fixtures_are_representable[cs-14-4]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_all_14_fixtures_are_representable[cs-14-5]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_disagreement_composite_is_representable" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_composite_digest_is_deterministic" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_distinct_dimensions_change_the_digest" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_missing_dimension_field_is_unconstructable[intent_state]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_missing_dimension_field_is_unconstructable[transmission_attempt_state]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_missing_dimension_field_is_unconstructable[broker_order_state]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_missing_dimension_field_is_unconstructable[knowledge_state]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_missing_dimension_field_is_unconstructable[capacity_state]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_attempt_none_value_constructs_but_missing_field_does_not" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_issued_composite_requires_all_five_concrete" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_dimension_swap_is_rejected[broker_order_state-PROPOSED]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_dimension_swap_is_rejected[knowledge_state-UNKNOWN]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_dimension_swap_is_rejected[intent_state-RECONCILED]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_dimension_swap_is_rejected[capacity_state-SEND_STARTED]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_dimension_swap_is_rejected[transmission_attempt_state-POTENTIALLY_LIVE]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_dimension_swap_is_rejected[broker_order_state-QUARANTINED]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_missing_required_covered_rejects_issuance[CompositeState:intent_identity]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_missing_required_covered_rejects_issuance[CompositeState:intent_state]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_missing_required_covered_rejects_issuance[CompositeState:transmission_attempt_state]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_missing_required_covered_rejects_issuance[CompositeState:broker_order_state]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_missing_required_covered_rejects_issuance[CompositeState:knowledge_state]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_missing_required_covered_rejects_issuance[CompositeState:capacity_state]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_missing_required_covered_rejects_issuance[DimensionTransitionRecord:intent_identity]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_missing_required_covered_rejects_issuance[DimensionTransitionRecord:dimension]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_missing_required_covered_rejects_issuance[DimensionTransitionRecord:from_state]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_missing_required_covered_rejects_issuance[DimensionTransitionRecord:to_state]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_missing_required_covered_rejects_issuance[DimensionTransitionRecord:owning_authority]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_every_record_has_non_vacuous_required_covered" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_issued_record_requires_independent_id[None]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_issued_record_requires_independent_id[TBD]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_same_id_diff_bytes_is_critical_conflict" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_same_id_same_bytes_is_idempotent_dup" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_fresh_id_per_observation_is_distinct" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_transition_record_same_id_diff_bytes_conflicts" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_composite_is_frozen" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_no_dimension_mutation_method_on_records" time="0.001" /><testcase classname="tests.orthostate.test_orthostate_composite" name="test_package_exposes_no_normalize_operation" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_vocabulary" name="test_dimension_cardinalities_match_adr" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_vocabulary" name="test_reconciled_is_knowledge_only" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_vocabulary" name="test_unknown_is_broker_not_knowledge" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_vocabulary" name="test_attempt_none_is_a_real_value" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_vocabulary" name="test_global_string_value_pairwise_disjoint_across_five_dimensions" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_vocabulary" name="test_state_dimension_and_authority_enums_complete" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_vocabulary" name="test_weak_bases_are_wider_than_rcl_weak_causes" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_coupling" name="test_coupling_negative_fixtures_are_representable_and_flagged[cs-14-2]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_coupling" name="test_coupling_negative_fixtures_are_representable_and_flagged[cs-14-4]" time="0.000" /></testsuite></testsuites>
```

---- FILE tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/manifest.yaml ----
```
schema: tos-evidence/manifest/v1
run_id: 20260806T015629Z-12dd4077
evidence_id: STATE-EV-001
primary_adr: ADR-002-005
design_document: docs/plans/2026-07-25-tos-orthogonal-state-design.md
evidence_level_stage: EV-L1
discipline_tag: EV-L1 stage execution record only; not a row PASS; incomplete until independent review
  signs (VER §9.5) and P0-1 (bounds approval) closes; staged rows require higher stages before acceptance
  (VER:171).
claim:
  closes_evidence_item: false
  register_status_moved_by_this_run: false
  register_status_at_run_time: READY
  minimum_evidence_level: EV-L1/2
  independent_review: NOT_SIGNED (VER §9.5)
  p0_1_bounds_approval: OPEN
  verification_profile_version: 2.1 (PROPOSED — P0-1 open)
  target_integrity: STABLE_DURING_RUN
  mutated_during_run: []
  note: This document records that named tests executed at the recorded baseline. It asserts no acceptance,
    no PASS, and no coverage of the higher stages the row's minimum level names.
execution:
  command:
  - /Users/harris/Development/private/kis_unified_sts/.venv/bin/python
  - -m
  - pytest
  - tos/tests/orthostate/test_orthostate_composite.py
  - tos/tests/orthostate/test_orthostate_vocabulary.py
  - tos/tests/orthostate/test_orthostate_coupling.py::test_coupling_negative_fixtures_are_representable_and_flagged
  - -q
  - --junitxml=/Users/harris/Development/private/kis_unified_sts/tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/junit.xml
  - --hypothesis-seed=0
  cwd: /Users/harris/Development/private/kis_unified_sts
  env_overrides:
    PYTHONPATH: tos/src
    PYTHONHASHSEED: '0'
  started_utc: '2026-08-06T01:56:29.247760+00:00'
  finished_utc: '2026-08-06T01:56:29.755900+00:00'
  monotonic_duration_s: 0.508124
  return_code: 0
  outcome: ALL_SELECTED_TESTS_GREEN
  junit_summary:
    tests: 51
    failures: 0
    errors: 0
    skipped: 0
    time_s: '0.163'
test_nodes:
- tos/tests/orthostate/test_orthostate_composite.py
- tos/tests/orthostate/test_orthostate_vocabulary.py
- tos/tests/orthostate/test_orthostate_coupling.py::test_coupling_negative_fixtures_are_representable_and_flagged
baseline:
  file: baseline.yaml
  sha256: 2497d7f76f968b18cfc68091a102d70ea224cc2afd0c45929f4a0853a7d3d1bb
  completeness: 'EV-L1 subset (design #1 §5.1); VER §3 fields without an existing artifact are NOT_APPLICABLE_EV_L1.'
  ver3_unmet_field_count: 17
artifacts:
- name: baseline.yaml
  sha256: 2497d7f76f968b18cfc68091a102d70ea224cc2afd0c45929f4a0853a7d3d1bb
  bytes: 16367
- name: junit.xml
  sha256: b70c092c56aa86cbdb578d79f6a5c95b5da150ca8da3d78ea791d012e677cf37
  bytes: 7705
- name: run.log
  sha256: 621f658bfead9a3f256c5f6416426de51eca414be093684dcf81e00379ba5b4c
  bytes: 610
- name: traceability.csv
  sha256: 6807fc1a92be75c30e9c7ccf22456cbe8b3c53ac562ea0a32ccfe89ee343cecc
  bytes: 2082
artifact_closure_note: manifest.yaml cannot contain its own digest; sha256sums.txt is written last and
  closes over every retained file including this manifest (VER §9.2).

```

---- FILE tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/run.log ----
```
$ PYTHONPATH=tos/src PYTHONHASHSEED=0 /Users/harris/Development/private/kis_unified_sts/.venv/bin/python -m pytest tos/tests/orthostate/test_orthostate_composite.py tos/tests/orthostate/test_orthostate_vocabulary.py tos/tests/orthostate/test_orthostate_coupling.py::test_coupling_negative_fixtures_are_representable_and_flagged -q --junitxml=/Users/harris/Development/private/kis_unified_sts/tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/junit.xml --hypothesis-seed=0

--- stdout ---
...................................................                      [100%]

--- stderr ---

--- return code: 0 ---

```

---- FILE tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/sha256sums.txt ----
```
2497d7f76f968b18cfc68091a102d70ea224cc2afd0c45929f4a0853a7d3d1bb  baseline.yaml
b70c092c56aa86cbdb578d79f6a5c95b5da150ca8da3d78ea791d012e677cf37  junit.xml
896617350170139ae4a43ba724621c46b66d5c793a038a7828007ae95196b572  manifest.yaml
621f658bfead9a3f256c5f6416426de51eca414be093684dcf81e00379ba5b4c  run.log
6807fc1a92be75c30e9c7ccf22456cbe8b3c53ac562ea0a32ccfe89ee343cecc  traceability.csv

```

---- FILE tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/traceability.csv ----
```
evidence_id,primary_adr,design_document,test_node,mapping_basis,evidence_claim
STATE-EV-001,ADR-002-005,docs/plans/2026-07-25-tos-orthogonal-state-design.md,tos/tests/orthostate/test_orthostate_composite.py,"design #8 §1:320 STATE-EV-001 core row (representability + digest determinism) and §7 family row ""§14 다섯 composite 표현 + digest 결정성 ONLY""; file header test_orthostate_composite.py:3,9 declares ""[STATE-EV-001 slice — /2 durable persistence deferred]"". Node anchors measured against the executed baseline: required-dimension drop test_orthostate_composite.py:104, NONE != None test_orthostate_composite.py:112, dimension swap test_orthostate_composite.py:145. The design-doc anchor is the -001 table row, re-measured — the row this basis previously cited was the table header (the design v1.2 N5 citation-drift class).",STAGE_RECORD_ONLY (does not close the evidence item)
STATE-EV-001,ADR-002-005,docs/plans/2026-07-25-tos-orthogonal-state-design.md,tos/tests/orthostate/test_orthostate_vocabulary.py,"design #8 §7 family rows ""no-mixed-enum + dimension-swap"" / ""composite completeness"" (§4.1/§4.2 structural invariants that make representability meaningful); file header test_orthostate_vocabulary.py:7 declares ""[STATE-EV-001 slice]"". Anchor re-measured against the executed baseline (unchanged).",STAGE_RECORD_ONLY (does not close the evidence item)
STATE-EV-001,ADR-002-005,docs/plans/2026-07-25-tos-orthogonal-state-design.md,tos/tests/orthostate/test_orthostate_coupling.py::test_coupling_negative_fixtures_are_representable_and_flagged,"design #8 §7 family row ""representable-but-coupling-flagged (C1 test class) = core(001∧003 교차)""; the node is defined at test_orthostate_coupling.py:69 and asserts Claim 1 = STATE-EV-001 representability at test_orthostate_coupling.py:80 — included for the 001 claim only, not for the 003 coupling claim. Anchors re-measured against the executed baseline; the prior citation pointed at a docstring sentence rather than the assertion.",STAGE_RECORD_ONLY (does not close the evidence item)

```


============================================================================
# PACKAGE tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077
============================================================================

---- FILE tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/baseline.yaml ----
```
schema: tos-evidence/baseline/v1
run_id: 20260806T015630Z-12dd4077
evidence_id: SPG-EV-002
evidence_level_stage: EV-L1
generated_utc: '2026-08-06T01:56:30.503785+00:00'
contract:
  run_manifest_contract: docs/plans/2026-07-20-tos-boundary-and-import-firewall-design.md §5.1 (seven
    items)
  ver_specification: tos-spec/src/part-1-foundation/VER-002-001-Safety-Critical-Architecture-Verification-Evidence-Specification.md
    §2.3/§3/§8/§9.1/§9.2/§9.5
  completeness: 'EV-L1 subset. VER §3 requires 22 baseline fields and states that ''A run without a complete
    baseline is invalid''; design #1 §5.1 ratifies the seven items below as the EV-L1 subset. Fields whose
    artifacts do not exist at this stage are marked NOT_APPLICABLE_EV_L1 with a reason. Under VER §3''s
    full standard this baseline is complete for EV-L1 only and is NOT a complete baseline for EV-L2 and
    above.'
evidence_register_row:
  source: tos-spec/src/part-1-foundation/verification/EVIDENCE-REGISTER-002.csv
  evidence_id: SPG-EV-002
  domain: Safety Profile Governance
  title: Semantic Units, Numeric, and Cross-Field Validation
  primary_adr: ADR-002-014
  criticality: Critical
  minimum_evidence_level: EV-L1/2
  status_at_run_time: PASS
  implementation_owner: ai-impl(claude-orchestrated)
  evidence_owner: operator
  independent_reviewer: ai-review(decorrelated)+operator-countersign
design1_5_1:
  item_1_repository_and_package:
    git_commit_sha: 12dd40778b0237ea6992a3b0a9ecadb10f865f0f
    git_short_sha: 12dd4077
    tos_package_version: 0.0.1
    worktree:
      clean: false
      untracked:
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/baseline.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/junit.xml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/manifest.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/sha256sums.txt
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/traceability.csv
      modified_unstaged: []
      staged: []
      all_dirty_paths:
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/baseline.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/junit.xml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/manifest.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/sha256sums.txt
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/traceability.csv
      note: 'A non-empty list does not by itself invalidate the run: the executed files are pinned individually
        by target_file_digests below. Paths outside the executed set belong to other work in the same
        worktree.'
    worktree_after_run:
      clean: false
      untracked:
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/junit.xml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/baseline.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/junit.xml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/manifest.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/sha256sums.txt
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/traceability.csv
      modified_unstaged: []
      staged: []
      all_dirty_paths:
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/junit.xml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/baseline.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/junit.xml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/manifest.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/sha256sums.txt
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/traceability.csv
      note: 'A non-empty list does not by itself invalidate the run: the executed files are pinned individually
        by target_file_digests below. Paths outside the executed set belong to other work in the same
        worktree.'
    worktree_delta:
      became_dirty_during_run:
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/junit.xml
      became_clean_during_run: []
      stable: false
    target_files_clean: true
    target_files_stable_during_run: true
    target_file_digests:
    - path: tools/tos_evidence_run.py
      sha256_before_run: 562c52eebc1758ccf804b55c2eb03a1887a07014433d649ec0e01a7a143fb0aa
      sha256_after_run: 562c52eebc1758ccf804b55c2eb03a1887a07014433d649ec0e01a7a143fb0aa
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: false
    - path: tos/src/tos/spg/__init__.py
      sha256_before_run: 216b0249c63e6f11cb1e21c3c2668764aef96cc2b88664fe01f06e9d3c04d256
      sha256_after_run: 216b0249c63e6f11cb1e21c3c2668764aef96cc2b88664fe01f06e9d3c04d256
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/spg/_base.py
      sha256_before_run: 72d6ef47c9289896eb036d7931f285d3b31e310f8ebbc0a5281b0f677889076a
      sha256_after_run: 72d6ef47c9289896eb036d7931f285d3b31e310f8ebbc0a5281b0f677889076a
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/spg/predicates.py
      sha256_before_run: 0e135bee214bdbe55654e40586d0693d5b44d9dffbc56f7abaad8531e041327e
      sha256_after_run: 0e135bee214bdbe55654e40586d0693d5b44d9dffbc56f7abaad8531e041327e
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/spg/records.py
      sha256_before_run: dd8f5492bf4795d80c26f344b92fb85c5c4d615954afe3ab199c190c27745dc0
      sha256_after_run: dd8f5492bf4795d80c26f344b92fb85c5c4d615954afe3ab199c190c27745dc0
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/spg/vocabulary.py
      sha256_before_run: 878b429c2d2f53df430a9ba88680240e28ed38d2bfcd322f64b1ff7ed3aa96cc
      sha256_after_run: 878b429c2d2f53df430a9ba88680240e28ed38d2bfcd322f64b1ff7ed3aa96cc
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/tests/spg/test_spg_records.py
      sha256_before_run: 91289d3d615b738f294cba1b7fb47f7ad0ab77a77929084b105b2eb25ee15f07
      sha256_after_run: 91289d3d615b738f294cba1b7fb47f7ad0ab77a77929084b105b2eb25ee15f07
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/tests/spg/test_spg_semantic.py
      sha256_before_run: 51bc8d7d6168d68306d622ebd14bf930ee21fe1c078953338a0f473e508c2b2c
      sha256_after_run: 51bc8d7d6168d68306d622ebd14bf930ee21fe1c078953338a0f473e508c2b2c
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
  item_2_interpreter_and_dependencies:
    python:
      version: 3.12.2
      version_full: 3.12.2 (main, Dec 11 2025, 16:36:08) [Clang 17.0.0 (clang-1700.4.4.1)]
      implementation: CPython
      executable: /Users/harris/Development/private/kis_unified_sts/.venv/bin/python
    installed_versions_measured:
      pydantic: 2.12.5
      hypothesis: 6.151.5
      pytest: 9.0.2
      numpy: 1.26.4
      pandas: 2.3.3
      pyyaml: 6.0.3
      tos: NOT_INSTALLED
    pinned_in_tos_pyproject:
      pydantic: 2.12.5
      numpy: 2.4.0
      pandas: 2.3.3
      pyyaml: 6.0.3
      pytest: 9.0.2
      hypothesis: 6.150.2
    pins_satisfied: false
    pin_vs_installed_drift:
    - distribution: hypothesis
      pinned: 6.150.2
      installed: 6.151.5
    - distribution: numpy
      pinned: 2.4.0
      installed: 1.26.4
    drift_note: 'pins_satisfied is the machine-readable claim; an empty drift list = the executed interpreter
      matches every pin. A non-empty list is recorded, not resolved: the installed version is what executed.'
  item_3_execution_environment: &id001
    os: Darwin
    os_release: 25.5.0
    machine: arm64
    platform: macOS-26.5.2-arm64-arm-64bit
    python_implementation: CPython
  item_4_harness_version: &id002
    harness_path: tools/tos_evidence_run.py
    harness_sha256: 562c52eebc1758ccf804b55c2eb03a1887a07014433d649ec0e01a7a143fb0aa
    harness_tracked: true
    harness_at_commit: aac2827bb5941603705da735ea079129ce3d942a
    harness_dirty: false
    pytest_version: 9.0.2
    note: 'design #1 §5.1 item 4 — Phase 1 harness version = git digest, which exists only once the harness
      is committed. Until then harness_at_commit is NOT_IN_COMMIT and harness_sha256 is the only identity
      of the code that ran.'
  item_5_seed_policy: &id003
    policy: fixed
    pytest_flags:
    - --hypothesis-seed=0
    hypothesis_seed: 0
    note: 'VER §9.1 append-only: seed pinned before the run began.'
  item_6_consumed_configuration_artifacts:
    status: NOT_APPLICABLE_EV_L1
    reason: 'No configuration artifact is consumed: bounds are hypothesis-injected generated values, not
      read from a profile, and the run is hermetic (no .env, no YAML).'
  item_7_retained_artifact_digests: Enumerated in manifest.yaml (artifacts) and closed over by sha256sums.txt,
    which is written last and covers every retained file including the manifest.
ver_002_001_section_3_baseline:
  repository_commit_sha:
    status: RECORDED
    value: 12dd40778b0237ea6992a3b0a9ecadb10f865f0f
  build_artifact_digest:
    status: NOT_APPLICABLE_EV_L1
    reason: 'Phase 1 executes from the source tree; no built distribution artifact is produced or consumed
      (design #1 §5.1 items 1/4 — the git digest stands in). The executed bytes are pinned individually
      by design1_5_1.item_1_repository_and_package.target_file_digests.'
  rfc_adr_versions:
    status: RECORDED
    value:
    - role: primary_adr
      path: tos-spec/src/part-1-foundation/ADR-002-014-Hard-Safety-Envelope-and-Runtime-Safety-Profile-Governance.md
      sha256: ba84bb15e30658323d9be6f9cf11fe16a90569789a22f96a2db9203b649f6709
    - role: design_document
      path: docs/plans/2026-07-25-tos-safety-profile-governance-design.md
      sha256: cae316b02bed99e11bfad1e6b868ee8782e2c8173e1ecaf5404659ce047f1531
    - role: ver_specification
      path: tos-spec/src/part-1-foundation/VER-002-001-Safety-Critical-Architecture-Verification-Evidence-Specification.md
      sha256: 217a43ab1b32e04fe6515316a7383c3e9e75bb177ed18c7c7e7267ca0a3c2a38
    - role: boundary_design_1
      path: docs/plans/2026-07-20-tos-boundary-and-import-firewall-design.md
      sha256: 2449f18d6088e21f601da623d27e6eff74066661f5d92116db2eda1a59b5a988
    reason: The corpus documents carry no separate version field; their content sha256 is the version
      identity.
  hard_safety_envelope_version:
    status: NOT_APPLICABLE_EV_L1
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L1 model/property run consumes none. Recorded N/A per design #1 §5.1 (EV-L1 subset of VER
      §3).'
  runtime_safety_profile_version:
    status: NOT_APPLICABLE_EV_L1
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L1 model/property run consumes none. Recorded N/A per design #1 §5.1 (EV-L1 subset of VER
      §3).'
  human_authority_policy_generation_and_digest:
    status: NOT_APPLICABLE_EV_L1
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L1 model/property run consumes none. Recorded N/A per design #1 §5.1 (EV-L1 subset of VER
      §3).'
  effective_principal_graph_generation_and_digest:
    status: NOT_APPLICABLE_EV_L1
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L1 model/property run consumes none. Recorded N/A per design #1 §5.1 (EV-L1 subset of VER
      §3).'
  evidence_integrity_policy_generation_and_digest:
    status: NOT_APPLICABLE_EV_L1
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L1 model/property run consumes none. Recorded N/A per design #1 §5.1 (EV-L1 subset of VER
      §3).'
  recovery_barrier_policy_generation_and_digest:
    status: NOT_APPLICABLE_EV_L1
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L1 model/property run consumes none. Recorded N/A per design #1 §5.1 (EV-L1 subset of VER
      §3).'
  critical_input_policy_generation_and_digest:
    status: NOT_APPLICABLE_EV_L1
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L1 model/property run consumes none. Recorded N/A per design #1 §5.1 (EV-L1 subset of VER
      §3).'
  venue_constraint_policy_generation_and_digest:
    status: NOT_APPLICABLE_EV_L1
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L1 model/property run consumes none. Recorded N/A per design #1 §5.1 (EV-L1 subset of VER
      §3).'
  trading_approval_policy_generation_and_digest:
    status: NOT_APPLICABLE_EV_L1
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L1 model/property run consumes none. Recorded N/A per design #1 §5.1 (EV-L1 subset of VER
      §3).'
  currentness_policy_generation_and_digest:
    status: NOT_APPLICABLE_EV_L1
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L1 model/property run consumes none. Recorded N/A per design #1 §5.1 (EV-L1 subset of VER
      §3).'
  restricted_live_trial_policy_generation_and_digest:
    status: NOT_APPLICABLE_EV_L1
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L1 model/property run consumes none. Recorded N/A per design #1 §5.1 (EV-L1 subset of VER
      §3).'
  broker_capability_profile_version:
    status: NOT_APPLICABLE_EV_L1
    reason: Evidence Register broker_capability_profile_version for this row = 'N/A'; the row's minimum
      evidence level (EV-L1/2) carries no +Broker suffix and no Broker Capability Profile instance exists
      (template only). P0-2 is not in this run's scope.
  verification_profile_version:
    status: RECORDED
    value:
      version: 2.1 (PROPOSED — P0-1 open)
      register_column_value: 2.1-PROPOSED
      artifact:
        path: tos-spec/src/part-1-foundation/verification/VERIFICATION-PROFILE-002.yaml
        sha256: d837c7e74b0fbe70d7cf2dfb30e412a29042577a0a38dcba22c649dd457d5064
      approval_state: PROPOSED — P0-1 (bounds approval) OPEN
    reason: Recorded, not approved. VER §6 numeric bounds remain unapproved; no bound value is consumed
      by this run (bounds are hypothesis-injected, not hardcoded).
  database_schema_migration_version:
    status: NOT_APPLICABLE_EV_L1
    reason: EV-L1 model/property verification exercises no persistence substrate; durable persistence
      is the deferred /2 stage.
  deployment_manifest_digest:
    status: NOT_APPLICABLE_EV_L1
    reason: 'Nothing is deployed: the kernel is non-transmitting and is executed in-process by pytest.'
  workload_identities_and_key_versions:
    status: NOT_APPLICABLE_EV_L1
    reason: No workload identity, credential, or key material is used — the run is hermetic (no network,
      no .env, no clock authority).
  environment_identifier:
    status: RECORDED
    value: *id001
  test_harness_version:
    status: RECORDED
    value: *id002
  fault_injection_schedule_and_seed:
    status: PARTIAL_EV_L1
    value:
      fault_schedule:
        status: NOT_APPLICABLE_EV_L1
        reason: 'Fault injection begins at EV-L2 (VER §5); design #1 §5.1 adds the §9.1 fault schedule
          on EV-L2 entry.'
      seed: *id003
ver_002_001_section_3_unmet_fields:
- broker_capability_profile_version
- build_artifact_digest
- critical_input_policy_generation_and_digest
- currentness_policy_generation_and_digest
- database_schema_migration_version
- deployment_manifest_digest
- effective_principal_graph_generation_and_digest
- evidence_integrity_policy_generation_and_digest
- fault_injection_schedule_and_seed
- hard_safety_envelope_version
- human_authority_policy_generation_and_digest
- recovery_barrier_policy_generation_and_digest
- restricted_live_trial_policy_generation_and_digest
- runtime_safety_profile_version
- trading_approval_policy_generation_and_digest
- venue_constraint_policy_generation_and_digest
- workload_identities_and_key_versions
ver_002_001_section_3_unmet_note: 'VER §3 line 109 (''A run without a complete baseline is invalid'')
  has no ''as applicable'' clause. This list names every field that is not RECORDED, so the gap is machine-checkable:
  an empty list would be the claim that the baseline is complete, and this run does not make that claim.'
test_nodes:
- tos/tests/spg/test_spg_semantic.py
- tos/tests/spg/test_spg_records.py::test_valid_result_must_have_empty_reason_set
- tos/tests/spg/test_spg_records.py::test_invalid_result_must_have_nonempty_reason_set
- tos/tests/spg/test_spg_records.py::test_extra_field_forbidden

```

---- FILE tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/junit.xml ----
```
<?xml version="1.0" encoding="utf-8"?><testsuites name="pytest tests"><testsuite name="pytest" errors="0" failures="0" skipped="0" tests="19" time="0.100" timestamp="2026-08-06T10:56:30.278706+09:00" hostname="ichihun-ui-MacBookPro.local"><testcase classname="tests.spg.test_spg_semantic" name="test_valid_bundle_has_empty_reason_set" time="0.001" /><testcase classname="tests.spg.test_spg_semantic" name="test_absent_bundle_is_invalid" time="0.000" /><testcase classname="tests.spg.test_spg_semantic" name="test_bundle_missing_profile_is_invalid" time="0.000" /><testcase classname="tests.spg.test_spg_semantic" name="test_exceeds_envelope_reason" time="0.000" /><testcase classname="tests.spg.test_spg_semantic" name="test_empty_profile_omit_propagates_to_semantic_validation" time="0.000" /><testcase classname="tests.spg.test_spg_semantic" name="test_unit_mismatch_reason" time="0.000" /><testcase classname="tests.spg.test_spg_semantic" name="test_cross_field_contradiction_reason" time="0.000" /><testcase classname="tests.spg.test_spg_semantic" name="test_cross_field_none_fails_closed" time="0.000" /><testcase classname="tests.spg.test_spg_semantic" name="test_unorderable_direction_reason" time="0.001" /><testcase classname="tests.spg.test_spg_semantic" name="test_nan_limit_rejected_at_construction" time="0.000" /><testcase classname="tests.spg.test_spg_semantic" name="test_duplicate_dimension_reason" time="0.000" /><testcase classname="tests.spg.test_spg_semantic" name="test_canonical_irreproducible_reason" time="0.000" /><testcase classname="tests.spg.test_spg_semantic" name="test_floating_member_reason" time="0.000" /><testcase classname="tests.spg.test_spg_semantic" name="test_schema_downgrade_reason" time="0.000" /><testcase classname="tests.spg.test_spg_semantic" name="test_default_semantic_inputs_fail_every_fold_step" time="0.000" /><testcase classname="tests.spg.test_spg_semantic" name="test_units_compatible_seam_bool" time="0.001" /><testcase classname="tests.spg.test_spg_records" name="test_valid_result_must_have_empty_reason_set" time="0.000" /><testcase classname="tests.spg.test_spg_records" name="test_invalid_result_must_have_nonempty_reason_set" time="0.000" /><testcase classname="tests.spg.test_spg_records" name="test_extra_field_forbidden" time="0.000" /></testsuite></testsuites>
```

---- FILE tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/manifest.yaml ----
```
schema: tos-evidence/manifest/v1
run_id: 20260806T015630Z-12dd4077
evidence_id: SPG-EV-002
primary_adr: ADR-002-014
design_document: docs/plans/2026-07-25-tos-safety-profile-governance-design.md
evidence_level_stage: EV-L1
discipline_tag: EV-L1 stage execution record only; not a row PASS; incomplete until independent review
  signs (VER §9.5) and P0-1 (bounds approval) closes; staged rows require higher stages before acceptance
  (VER:171).
claim:
  closes_evidence_item: false
  register_status_moved_by_this_run: false
  register_status_at_run_time: PASS
  minimum_evidence_level: EV-L1/2
  independent_review: NOT_SIGNED (VER §9.5)
  p0_1_bounds_approval: OPEN
  verification_profile_version: 2.1 (PROPOSED — P0-1 open)
  target_integrity: STABLE_DURING_RUN
  mutated_during_run: []
  note: This document records that named tests executed at the recorded baseline. It asserts no acceptance,
    no PASS, and no coverage of the higher stages the row's minimum level names.
execution:
  command:
  - /Users/harris/Development/private/kis_unified_sts/.venv/bin/python
  - -m
  - pytest
  - tos/tests/spg/test_spg_semantic.py
  - tos/tests/spg/test_spg_records.py::test_valid_result_must_have_empty_reason_set
  - tos/tests/spg/test_spg_records.py::test_invalid_result_must_have_nonempty_reason_set
  - tos/tests/spg/test_spg_records.py::test_extra_field_forbidden
  - -q
  - --junitxml=/Users/harris/Development/private/kis_unified_sts/tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/junit.xml
  - --hypothesis-seed=0
  cwd: /Users/harris/Development/private/kis_unified_sts
  env_overrides:
    PYTHONPATH: tos/src
    PYTHONHASHSEED: '0'
  started_utc: '2026-08-06T01:56:30.074569+00:00'
  finished_utc: '2026-08-06T01:56:30.428603+00:00'
  monotonic_duration_s: 0.354021
  return_code: 0
  outcome: ALL_SELECTED_TESTS_GREEN
  junit_summary:
    tests: 19
    failures: 0
    errors: 0
    skipped: 0
    time_s: '0.100'
test_nodes:
- tos/tests/spg/test_spg_semantic.py
- tos/tests/spg/test_spg_records.py::test_valid_result_must_have_empty_reason_set
- tos/tests/spg/test_spg_records.py::test_invalid_result_must_have_nonempty_reason_set
- tos/tests/spg/test_spg_records.py::test_extra_field_forbidden
baseline:
  file: baseline.yaml
  sha256: d63b86a51603506bf90c682ede9f72bbda5e14533f3925dcc5f3b5f1353887f9
  completeness: 'EV-L1 subset (design #1 §5.1); VER §3 fields without an existing artifact are NOT_APPLICABLE_EV_L1.'
  ver3_unmet_field_count: 17
artifacts:
- name: baseline.yaml
  sha256: d63b86a51603506bf90c682ede9f72bbda5e14533f3925dcc5f3b5f1353887f9
  bytes: 17209
- name: junit.xml
  sha256: cfd9b39267881b7d55abf1e18bcc20c7e2a5d07b0f40bf8ff3a3fa3c80ab0f3c
  bytes: 2327
- name: run.log
  sha256: 4a0e5689d39db2c156f83d5b9eda16b1f20d8199062db299cb3218dae95bb871
  bytes: 657
- name: traceability.csv
  sha256: e08cf4ff8afd5203ce34d1904f007e0ecbddf34bc8a93369f8beb9439116cb42
  bytes: 2372
artifact_closure_note: manifest.yaml cannot contain its own digest; sha256sums.txt is written last and
  closes over every retained file including this manifest (VER §9.2).

```

---- FILE tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/run.log ----
```
$ PYTHONPATH=tos/src PYTHONHASHSEED=0 /Users/harris/Development/private/kis_unified_sts/.venv/bin/python -m pytest tos/tests/spg/test_spg_semantic.py tos/tests/spg/test_spg_records.py::test_valid_result_must_have_empty_reason_set tos/tests/spg/test_spg_records.py::test_invalid_result_must_have_nonempty_reason_set tos/tests/spg/test_spg_records.py::test_extra_field_forbidden -q --junitxml=/Users/harris/Development/private/kis_unified_sts/tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/junit.xml --hypothesis-seed=0

--- stdout ---
...................                                                      [100%]

--- stderr ---

--- return code: 0 ---

```

---- FILE tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/sha256sums.txt ----
```
d63b86a51603506bf90c682ede9f72bbda5e14533f3925dcc5f3b5f1353887f9  baseline.yaml
cfd9b39267881b7d55abf1e18bcc20c7e2a5d07b0f40bf8ff3a3fa3c80ab0f3c  junit.xml
ee89d2a29759a1a91c21324e0ef1bae172d856b681e57c08f2928626947bb931  manifest.yaml
4a0e5689d39db2c156f83d5b9eda16b1f20d8199062db299cb3218dae95bb871  run.log
e08cf4ff8afd5203ce34d1904f007e0ecbddf34bc8a93369f8beb9439116cb42  traceability.csv

```

---- FILE tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/traceability.csv ----
```
evidence_id,primary_adr,design_document,test_node,mapping_basis,evidence_claim
SPG-EV-002,ADR-002-014,docs/plans/2026-07-25-tos-safety-profile-governance-design.md,tos/tests/spg/test_spg_semantic.py,"design #12 §1:475 maps ADR §11 (Semantic Validation — units/numeric/cross-field/direction, the register title of SPG-EV-002) to the core L1 substrate ""semantic_validation -> SemanticValidationResult (§5.2)""; file header test_spg_semantic.py:1 declares ""design #12 §5.2; SPG-EV-002/003""; the producer carries the same SPG-EV-002/003 anchor at tos/src/tos/spg/predicates.py:429 (§5.2 section header) and tos/src/tos/spg/predicates.py:461 (semantic_validation docstring). Every file:line in this basis was re-measured against the executed baseline; the pre-hardening anchors this row previously carried had drifted onto unrelated docstring lines and are not reproduced here.",STAGE_RECORD_ONLY (does not close the evidence item)
SPG-EV-002,ADR-002-014,docs/plans/2026-07-25-tos-safety-profile-governance-design.md,tos/tests/spg/test_spg_records.py::test_valid_result_must_have_empty_reason_set,"design #12 §1:475 SPG-EV-002 substrate is the rich verdict itself; this node seals the VALID <-> empty-reason-set coupling of SemanticValidationResult (test_spg_records.py:267, §4.2 ∅-seal). Anchor re-measured against the executed baseline (the §7 citizen tests shifted this file).",STAGE_RECORD_ONLY (does not close the evidence item)
SPG-EV-002,ADR-002-014,docs/plans/2026-07-25-tos-safety-profile-governance-design.md,tos/tests/spg/test_spg_records.py::test_invalid_result_must_have_nonempty_reason_set,"design #12 §1:475 SPG-EV-002 substrate; seals the vacuous-INVALID (no reason) verdict as unconstructable (test_spg_records.py:276, §4.2 ∅-seal). Anchor re-measured against the executed baseline.",STAGE_RECORD_ONLY (does not close the evidence item)
SPG-EV-002,ADR-002-014,docs/plans/2026-07-25-tos-safety-profile-governance-design.md,tos/tests/spg/test_spg_records.py::test_extra_field_forbidden,"design #12 §1:474 maps ADR §10 (Runtime Safety Profile Content — explicit, no wildcard) to ""wildcard/미선언 Critical field 거부(§2.3/§5.2)"" for SPG-EV-002/003; this node is the §2.3 extra=""forbid"" realization (test_spg_records.py:155). Anchor re-measured against the executed baseline.",STAGE_RECORD_ONLY (does not close the evidence item)

```


============================================================================
# PACKAGE tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077
============================================================================

---- FILE tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/baseline.yaml ----
```
schema: tos-evidence/baseline/v2
run_id: 20260806T015630Z-12dd4077
evidence_id: STATE-EV-001
evidence_level_stage: EV-L2
generated_utc: '2026-08-06T01:56:31.178573+00:00'
contract:
  run_manifest_contract: docs/plans/2026-07-20-tos-boundary-and-import-firewall-design.md §5.1 (seven
    items)
  ver_specification: tos-spec/src/part-1-foundation/VER-002-001-Safety-Critical-Architecture-Verification-Evidence-Specification.md
    §2.3/§3/§8/§9.1/§9.2/§9.5
  completeness: EV-L2 component-fault. VER §3 requires 22 baseline fields and states that 'A run without
    a complete baseline is invalid' (line 109) — a clause carrying no 'as applicable' qualifier, unlike
    §7 line 258, so it stands beside P0-1 and the independent signature as a gate, not a waivable formality.
    The unmet-field list and every reason are retained from EV-L1 with the stage attribution updated (NOT_APPLICABLE_EV_L1
    -> NOT_APPLICABLE_PURE_MODEL_L2); the enumerated list is ver_002_001_section_3_unmet_fields below.
    The absent artifacts are the broker, authority/human, reconciliation, network and recovery instances
    — none of which a pure-model, single-component, non-transmitting fault run brings into existence.
    Under VER §3's full standard this baseline is NOT complete.
evidence_register_row:
  source: tos-spec/src/part-1-foundation/verification/EVIDENCE-REGISTER-002.csv
  evidence_id: STATE-EV-001
  domain: Orthogonal State
  title: Orthogonal Composite Persistence
  primary_adr: ADR-002-005
  criticality: Critical
  minimum_evidence_level: EV-L1/2
  status_at_run_time: READY
  implementation_owner: ai-impl(claude-orchestrated)
  evidence_owner: operator
  independent_reviewer: ai-review(decorrelated)+operator-countersign
design1_5_1:
  item_1_repository_and_package:
    git_commit_sha: 12dd40778b0237ea6992a3b0a9ecadb10f865f0f
    git_short_sha: 12dd4077
    tos_package_version: 0.0.1
    worktree:
      clean: false
      untracked:
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/baseline.yaml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/junit.xml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/manifest.yaml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/sha256sums.txt
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/traceability.csv
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/baseline.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/junit.xml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/manifest.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/sha256sums.txt
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/traceability.csv
      modified_unstaged: []
      staged: []
      all_dirty_paths:
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/baseline.yaml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/junit.xml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/manifest.yaml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/sha256sums.txt
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/traceability.csv
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/baseline.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/junit.xml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/manifest.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/sha256sums.txt
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/traceability.csv
      note: 'A non-empty list does not by itself invalidate the run: the executed files are pinned individually
        by target_file_digests below. Paths outside the executed set belong to other work in the same
        worktree.'
    worktree_after_run:
      clean: false
      untracked:
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/baseline.yaml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/junit.xml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/manifest.yaml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/sha256sums.txt
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/traceability.csv
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/baseline.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/junit.xml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/manifest.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/sha256sums.txt
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/traceability.csv
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/fault-timeline.jsonl
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/junit.xml
      modified_unstaged: []
      staged: []
      all_dirty_paths:
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/baseline.yaml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/junit.xml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/manifest.yaml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/sha256sums.txt
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/traceability.csv
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/baseline.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/junit.xml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/manifest.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/sha256sums.txt
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/traceability.csv
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/fault-timeline.jsonl
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/junit.xml
      note: 'A non-empty list does not by itself invalidate the run: the executed files are pinned individually
        by target_file_digests below. Paths outside the executed set belong to other work in the same
        worktree.'
    worktree_delta:
      became_dirty_during_run:
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/fault-timeline.jsonl
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/junit.xml
      became_clean_during_run: []
      stable: false
    target_files_clean: true
    target_files_stable_during_run: true
    target_file_digests:
    - path: tools/tos_evidence_run.py
      sha256_before_run: 562c52eebc1758ccf804b55c2eb03a1887a07014433d649ec0e01a7a143fb0aa
      sha256_after_run: 562c52eebc1758ccf804b55c2eb03a1887a07014433d649ec0e01a7a143fb0aa
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: false
    - path: tos/src/tos/canonical/__init__.py
      sha256_before_run: 46fd765566c6c6b567b1f87c4a70f64014bb1678def66c44d798d9f85a9d75bb
      sha256_after_run: 46fd765566c6c6b567b1f87c4a70f64014bb1678def66c44d798d9f85a9d75bb
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/canonical/_base.py
      sha256_before_run: ca560b2987e078f9afc867c335f35915dfcb5c1065f00073c27bfef613f45dfb
      sha256_after_run: ca560b2987e078f9afc867c335f35915dfcb5c1065f00073c27bfef613f45dfb
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/canonical/canonicalization.py
      sha256_before_run: 18d855970b3ae0eebc6b7b6db6b5e7d93cf52179360d7986883792ab2057bfe3
      sha256_after_run: 18d855970b3ae0eebc6b7b6db6b5e7d93cf52179360d7986883792ab2057bfe3
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/canonical/record_pair.py
      sha256_before_run: 764c96796038dcab512071aa31075b79160e8cda247b50fcf5b2dfbd4c81f551
      sha256_after_run: 764c96796038dcab512071aa31075b79160e8cda247b50fcf5b2dfbd4c81f551
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/orthostate/__init__.py
      sha256_before_run: c866fc0fd8dc7bb0961f7550e2d9e73d1dfc4819afbc341c1f23fe4e0b11f632
      sha256_after_run: c866fc0fd8dc7bb0961f7550e2d9e73d1dfc4819afbc341c1f23fe4e0b11f632
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/orthostate/_base.py
      sha256_before_run: 2c1b8bb6c73ee8f73697ecc5e33d149a80efd7fdf27550b2f148248a2b34a40e
      sha256_after_run: 2c1b8bb6c73ee8f73697ecc5e33d149a80efd7fdf27550b2f148248a2b34a40e
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/orthostate/predicates.py
      sha256_before_run: 7265e75af582048fba54d757e5344a9d467348738a37dec7898df4c30db897c0
      sha256_after_run: 7265e75af582048fba54d757e5344a9d467348738a37dec7898df4c30db897c0
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/orthostate/records.py
      sha256_before_run: 8dabc903e03d039fb5292d5094a7d87cb46f073965a163c12eb1c3f167285cd2
      sha256_after_run: 8dabc903e03d039fb5292d5094a7d87cb46f073965a163c12eb1c3f167285cd2
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/orthostate/state.py
      sha256_before_run: aa68710f84ab21ba93d68d132a607ecb8f139f1acabde6e515712dc9599de0b3
      sha256_after_run: aa68710f84ab21ba93d68d132a607ecb8f139f1acabde6e515712dc9599de0b3
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/orthostate/vocabulary.py
      sha256_before_run: 67dda3c7eed990f3150273fcf6f00e7ad8bca5bcf5fb101d37573f289fcc37d4
      sha256_after_run: 67dda3c7eed990f3150273fcf6f00e7ad8bca5bcf5fb101d37573f289fcc37d4
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/tests/orthostate/test_orthostate_l2_fault.py
      sha256_before_run: 4cea0d91f144cae6519a58779a05656f6f0a38ffd9eeffcdb2197215fdc1639e
      sha256_after_run: 4cea0d91f144cae6519a58779a05656f6f0a38ffd9eeffcdb2197215fdc1639e
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
  item_2_interpreter_and_dependencies:
    python:
      version: 3.12.2
      version_full: 3.12.2 (main, Dec 11 2025, 16:36:08) [Clang 17.0.0 (clang-1700.4.4.1)]
      implementation: CPython
      executable: /Users/harris/Development/private/kis_unified_sts/.venv/bin/python
    installed_versions_measured:
      pydantic: 2.12.5
      hypothesis: 6.151.5
      pytest: 9.0.2
      numpy: 1.26.4
      pandas: 2.3.3
      pyyaml: 6.0.3
      tos: NOT_INSTALLED
    pinned_in_tos_pyproject:
      pydantic: 2.12.5
      numpy: 2.4.0
      pandas: 2.3.3
      pyyaml: 6.0.3
      pytest: 9.0.2
      hypothesis: 6.150.2
    pins_satisfied: false
    pin_vs_installed_drift:
    - distribution: hypothesis
      pinned: 6.150.2
      installed: 6.151.5
    - distribution: numpy
      pinned: 2.4.0
      installed: 1.26.4
    drift_note: 'pins_satisfied is the machine-readable claim; an empty drift list = the executed interpreter
      matches every pin. A non-empty list is recorded, not resolved: the installed version is what executed.'
  item_3_execution_environment: &id001
    os: Darwin
    os_release: 25.5.0
    machine: arm64
    platform: macOS-26.5.2-arm64-arm-64bit
    python_implementation: CPython
  item_4_harness_version: &id002
    harness_path: tools/tos_evidence_run.py
    harness_sha256: 562c52eebc1758ccf804b55c2eb03a1887a07014433d649ec0e01a7a143fb0aa
    harness_tracked: true
    harness_at_commit: aac2827bb5941603705da735ea079129ce3d942a
    harness_dirty: false
    pytest_version: 9.0.2
    note: 'design #1 §5.1 item 4 — Phase 1 harness version = git digest, which exists only once the harness
      is committed. Until then harness_at_commit is NOT_IN_COMMIT and harness_sha256 is the only identity
      of the code that ran.'
  item_5_seed_policy: &id003
    policy: fixed
    pytest_flags:
    - --hypothesis-seed=0
    hypothesis_seed: 0
    note: 'VER §9.1 append-only: seed pinned before the run began.'
  item_6_consumed_configuration_artifacts:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: 'No configuration artifact is consumed: bounds are hypothesis-injected generated values, not
      read from a profile, and the run is hermetic (no .env, no YAML).'
  item_7_retained_artifact_digests: Enumerated in manifest.yaml (artifacts) and closed over by sha256sums.txt,
    which is written last and covers every retained file including the manifest.
ver_002_001_section_3_baseline:
  repository_commit_sha:
    status: RECORDED
    value: 12dd40778b0237ea6992a3b0a9ecadb10f865f0f
  build_artifact_digest:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: 'Phase 1 executes from the source tree; no built distribution artifact is produced or consumed
      (design #1 §5.1 items 1/4 — the git digest stands in). The executed bytes are pinned individually
      by design1_5_1.item_1_repository_and_package.target_file_digests.'
  rfc_adr_versions:
    status: RECORDED
    value:
    - role: primary_adr
      path: tos-spec/src/part-1-foundation/ADR-002-005-Intent-Transmission-Attempt-Broker-Order-and-Knowledge-State-Model.md
      sha256: 025c02cf8638f6aed84faf22f724c47bbc0af390d3d189fa25ef065a8cd73d51
    - role: design_document
      path: docs/plans/2026-07-29-tos-ev-l2-pilot-design.md
      sha256: 43dff50a6567f23d5aec58f8c061282e8b8e42944f0d66ea190e9d26c7b0d5a9
    - role: ver_specification
      path: tos-spec/src/part-1-foundation/VER-002-001-Safety-Critical-Architecture-Verification-Evidence-Specification.md
      sha256: 217a43ab1b32e04fe6515316a7383c3e9e75bb177ed18c7c7e7267ca0a3c2a38
    - role: boundary_design_1
      path: docs/plans/2026-07-20-tos-boundary-and-import-firewall-design.md
      sha256: 2449f18d6088e21f601da623d27e6eff74066661f5d92116db2eda1a59b5a988
    reason: The corpus documents carry no separate version field; their content sha256 is the version
      identity.
  hard_safety_envelope_version:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      a pure-model EV-L2 component-fault run consumes none — it injects faults into a single in-process
      component and inspects that component''s own authoritative verdict. Recorded N/A per design #1 §5.1
      read forward to EV-L2 (EV-L2 pilot design §6.2 M2 / §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  runtime_safety_profile_version:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      a pure-model EV-L2 component-fault run consumes none — it injects faults into a single in-process
      component and inspects that component''s own authoritative verdict. Recorded N/A per design #1 §5.1
      read forward to EV-L2 (EV-L2 pilot design §6.2 M2 / §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  human_authority_policy_generation_and_digest:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      a pure-model EV-L2 component-fault run consumes none — it injects faults into a single in-process
      component and inspects that component''s own authoritative verdict. Recorded N/A per design #1 §5.1
      read forward to EV-L2 (EV-L2 pilot design §6.2 M2 / §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  effective_principal_graph_generation_and_digest:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      a pure-model EV-L2 component-fault run consumes none — it injects faults into a single in-process
      component and inspects that component''s own authoritative verdict. Recorded N/A per design #1 §5.1
      read forward to EV-L2 (EV-L2 pilot design §6.2 M2 / §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  evidence_integrity_policy_generation_and_digest:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      a pure-model EV-L2 component-fault run consumes none — it injects faults into a single in-process
      component and inspects that component''s own authoritative verdict. Recorded N/A per design #1 §5.1
      read forward to EV-L2 (EV-L2 pilot design §6.2 M2 / §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  recovery_barrier_policy_generation_and_digest:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      a pure-model EV-L2 component-fault run consumes none — it injects faults into a single in-process
      component and inspects that component''s own authoritative verdict. Recorded N/A per design #1 §5.1
      read forward to EV-L2 (EV-L2 pilot design §6.2 M2 / §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  critical_input_policy_generation_and_digest:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      a pure-model EV-L2 component-fault run consumes none — it injects faults into a single in-process
      component and inspects that component''s own authoritative verdict. Recorded N/A per design #1 §5.1
      read forward to EV-L2 (EV-L2 pilot design §6.2 M2 / §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  venue_constraint_policy_generation_and_digest:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      a pure-model EV-L2 component-fault run consumes none — it injects faults into a single in-process
      component and inspects that component''s own authoritative verdict. Recorded N/A per design #1 §5.1
      read forward to EV-L2 (EV-L2 pilot design §6.2 M2 / §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  trading_approval_policy_generation_and_digest:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      a pure-model EV-L2 component-fault run consumes none — it injects faults into a single in-process
      component and inspects that component''s own authoritative verdict. Recorded N/A per design #1 §5.1
      read forward to EV-L2 (EV-L2 pilot design §6.2 M2 / §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  currentness_policy_generation_and_digest:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      a pure-model EV-L2 component-fault run consumes none — it injects faults into a single in-process
      component and inspects that component''s own authoritative verdict. Recorded N/A per design #1 §5.1
      read forward to EV-L2 (EV-L2 pilot design §6.2 M2 / §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  restricted_live_trial_policy_generation_and_digest:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      a pure-model EV-L2 component-fault run consumes none — it injects faults into a single in-process
      component and inspects that component''s own authoritative verdict. Recorded N/A per design #1 §5.1
      read forward to EV-L2 (EV-L2 pilot design §6.2 M2 / §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  broker_capability_profile_version:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: Evidence Register broker_capability_profile_version for this row = 'N/A'; the row's minimum
      evidence level (EV-L1/2) carries no +Broker suffix and no Broker Capability Profile instance exists
      (template only). P0-2 is not in this run's scope.
  verification_profile_version:
    status: RECORDED
    value:
      version: 2.1 (PROPOSED — P0-1 open)
      register_column_value: 2.1-PROPOSED
      artifact:
        path: tos-spec/src/part-1-foundation/verification/VERIFICATION-PROFILE-002.yaml
        sha256: d837c7e74b0fbe70d7cf2dfb30e412a29042577a0a38dcba22c649dd457d5064
      approval_state: PROPOSED — P0-1 (bounds approval) OPEN
    reason: Recorded, not approved. VER §6 numeric bounds remain unapproved; no bound value is consumed
      by this run (bounds are hypothesis-injected, not hardcoded).
  database_schema_migration_version:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: EV-L1 model/property verification exercises no persistence substrate; durable persistence
      is the deferred /2 stage.
  deployment_manifest_digest:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: 'Nothing is deployed: the kernel is non-transmitting and is executed in-process by pytest.'
  workload_identities_and_key_versions:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: No workload identity, credential, or key material is used — the run is hermetic (no network,
      no .env, no clock authority).
  environment_identifier:
    status: RECORDED
    value: *id001
  test_harness_version:
    status: RECORDED
    value: *id002
  fault_injection_schedule_and_seed:
    status: RECORDED
    value:
      fault_schedule:
        catalog_ref: docs/plans/2026-07-29-tos-ev-l2-pilot-design.md#3
        seed: 0
        seed_pinned: true
        schedule_artifact: fault-timeline.jsonl
        fault_count: 11
        expected_fault_count: 11
        fault_count_matches_catalog: true
        fault_ids:
        - ST-01
        - ST-02
        - ST-03
        - ST-04
        - ST-11
        - ST-05
        - ST-06
        - ST-07
        - ST-09
        - ST-12
        - ST-08
        duplicate_fault_ids: []
        foreign_evidence_id_rows: []
        deviation_faults: []
        misreported_outcome_faults: []
        expected_undefined_faults: []
        unobserved_disposition_faults: []
        all_faults_met: true
        all_faults_met_basis: every row's outcome RE-DERIVED from observed vs expected (the row's own
          outcome field is cross-checked, never trusted); withheld on an empty schedule (0 injected !=
          0 violations), any deviation or misreport, any undefined Expected or unobserved disposition,
          a duplicated fault id, a row from another evidence id, or a recount that disagrees with the
          catalog size
        l1_hardening_prereq_met: true
        l1_hardening_prereq:
          met: true
          measured_from: structural analysis of the executed source's syntax tree; comments and docstrings
            cannot satisfy any check (the harness never imports tos)
          items:
          - hardening: H-1 allow_inf_nan=False pinned on FrozenModel.model_config
            path: tos/src/tos/canonical/_base.py
            sha256: ca560b2987e078f9afc867c335f35915dfcb5c1065f00073c27bfef613f45dfb
            met: true
            measured:
              bound_keywords:
              - allow_inf_nan
              - extra
              - frozen
              allow_inf_nan: 'False'
          - hardening: H-2 precision/rounding/boundary comparability + boundary-aware comparison
            path: tos/src/tos/spg/predicates.py
            sha256: 0e135bee214bdbe55654e40586d0693d5b44d9dffbc56f7abaad8531e041327e
            met: true
            measured:
              unit_metadata_keys:
              - unit
              - multiplier
              - sign
              - precision
              - rounding
              - boundary
              missing_metadata_keys: []
              boundary_comparison_defined: true
          - hardening: H-4 canonicalization scheme lookup wrapped as ArtifactIntegrityError
            path: tos/src/tos/canonical/canonicalization.py
            sha256: 18d855970b3ae0eebc6b7b6db6b5e7d93cf52179360d7986883792ab2057bfe3
            met: true
            measured:
              get_scheme_raises:
              - ArtifactIntegrityError
              module_raises:
              - ArtifactIntegrityError
              - TypeError
      seed: *id003
    reason: 'EV-L2: the VER §9.1 append-only fault schedule and the seed are both recorded. This field
      is no longer PARTIAL — it is the one VER §3 field the EV-L2 stage completes relative to EV-L1.'
ver_002_001_section_3_unmet_fields:
- broker_capability_profile_version
- build_artifact_digest
- critical_input_policy_generation_and_digest
- currentness_policy_generation_and_digest
- database_schema_migration_version
- deployment_manifest_digest
- effective_principal_graph_generation_and_digest
- evidence_integrity_policy_generation_and_digest
- hard_safety_envelope_version
- human_authority_policy_generation_and_digest
- recovery_barrier_policy_generation_and_digest
- restricted_live_trial_policy_generation_and_digest
- runtime_safety_profile_version
- trading_approval_policy_generation_and_digest
- venue_constraint_policy_generation_and_digest
- workload_identities_and_key_versions
ver_002_001_section_3_unmet_note: 'VER §3 line 109 (''A run without a complete baseline is invalid'')
  has no ''as applicable'' clause. This list names every field that is not RECORDED, so the gap is machine-checkable:
  an empty list would be the claim that the baseline is complete, and this run does not make that claim.'
test_nodes:
- tos/tests/orthostate/test_orthostate_l2_fault.py

```

---- FILE tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/fault-timeline.jsonl ----
```
{"fault_id": "ST-01", "evidence_id": "STATE-EV-001", "target_component": "tos.orthostate.records.CompositeState (serialization / reconstruction)", "guard_code_line": "tos/src/tos/orthostate/records.py:94", "fault_kind": "mandatory_dimension_dropped+silent_derivation_probe", "seed": 0, "input_witness_ref": "cs-1@5664ed5db3341b162da886e2fdd2841e43d4f0da4be220b8eb008a30c6ebdcaf", "expected_disposition": "ValidationError[missing@broker_order_state]", "observed_disposition": "ValidationError[missing@broker_order_state]", "outcome": "MET"}
{"fault_id": "ST-02", "evidence_id": "STATE-EV-001", "target_component": "tos.orthostate.records.CompositeState (serialization / reconstruction)", "guard_code_line": "tos/src/tos/orthostate/records.py:95; tos/src/tos/orthostate/vocabulary.py:82", "fault_kind": "none_substituted_for_NONE_state", "seed": 0, "input_witness_ref": "cs-1@588b3ac3a9817dd3ca70a4fc2795d16c756959e354d3a09aa712186327b4998f", "expected_disposition": "ValidationError[enum@transmission_attempt_state]", "observed_disposition": "ValidationError[enum@transmission_attempt_state]", "outcome": "MET"}
{"fault_id": "ST-03", "evidence_id": "STATE-EV-001", "target_component": "tos.orthostate.records.CompositeState (serialization / reconstruction)", "guard_code_line": "tos/src/tos/orthostate/records.py:96", "fault_kind": "dimension_swap_value_contamination", "seed": 0, "input_witness_ref": "cs-1@5664ed5db3341b162da886e2fdd2841e43d4f0da4be220b8eb008a30c6ebdcaf", "expected_disposition": "ValidationError[enum@broker_order_state]", "observed_disposition": "ValidationError[enum@broker_order_state]", "outcome": "MET"}
{"fault_id": "ST-04", "evidence_id": "STATE-EV-001", "target_component": "tos.orthostate.records.CompositeState (serialization / reconstruction)", "guard_code_line": "tos/src/tos/orthostate/records.py:97", "fault_kind": "out_of_enum_token", "seed": 0, "input_witness_ref": "cs-1@5664ed5db3341b162da886e2fdd2841e43d4f0da4be220b8eb008a30c6ebdcaf", "expected_disposition": "ValidationError[enum@knowledge_state]", "observed_disposition": "ValidationError[enum@knowledge_state]", "outcome": "MET"}
{"fault_id": "ST-11", "evidence_id": "STATE-EV-001", "target_component": "tos.orthostate.records.CompositeState (serialization / reconstruction)", "guard_code_line": "tos/src/tos/orthostate/records.py:102", "fault_kind": "scalar_meta_type_contamination", "seed": 0, "input_witness_ref": "cs-1@5664ed5db3341b162da886e2fdd2841e43d4f0da4be220b8eb008a30c6ebdcaf", "expected_disposition": "ValidationError[int_parsing@observation_revision]", "observed_disposition": "ValidationError[int_parsing@observation_revision]", "outcome": "MET"}
{"fault_id": "ST-05", "evidence_id": "STATE-EV-001", "target_component": "tos.orthostate.records.CompositeState (serialization / reconstruction)", "guard_code_line": "tos/src/tos/canonical/_base.py:211", "fault_kind": "covered_content_tampered_digest_retained", "seed": 0, "input_witness_ref": "cs-1@5664ed5db3341b162da886e2fdd2841e43d4f0da4be220b8eb008a30c6ebdcaf", "expected_disposition": "ValidationError(cause=ArtifactIntegrityError)", "observed_disposition": "ValidationError(cause=ArtifactIntegrityError)", "outcome": "MET"}
{"fault_id": "ST-06", "evidence_id": "STATE-EV-001", "target_component": "tos.orthostate.records.CompositeState (serialization / reconstruction)", "guard_code_line": "tos/src/tos/canonical/_base.py:211", "fault_kind": "digest_substituted_covered_retained", "seed": 0, "input_witness_ref": "cs-1@5664ed5db3341b162da886e2fdd2841e43d4f0da4be220b8eb008a30c6ebdcaf", "expected_disposition": "ValidationError(cause=ArtifactIntegrityError)", "observed_disposition": "ValidationError(cause=ArtifactIntegrityError)", "outcome": "MET"}
{"fault_id": "ST-07", "evidence_id": "STATE-EV-001", "target_component": "tos.orthostate.records.CompositeState (serialization / reconstruction)", "guard_code_line": "tos/src/tos/canonical/canonicalization.py:255; tos/src/tos/canonical/_base.py:209", "fault_kind": "unregistered_canonicalization_version", "seed": 0, "input_witness_ref": "cs-1@5664ed5db3341b162da886e2fdd2841e43d4f0da4be220b8eb008a30c6ebdcaf", "expected_disposition": "ValidationError(cause=ArtifactIntegrityError)", "observed_disposition": "ValidationError(cause=ArtifactIntegrityError)", "outcome": "MET"}
{"fault_id": "ST-09", "evidence_id": "STATE-EV-001", "target_component": "tos.orthostate.records.CompositeState (serialization / reconstruction)", "guard_code_line": "tos/src/tos/canonical/_base.py:205", "fault_kind": "lifecycle_contradiction_issued_null_digest", "seed": 0, "input_witness_ref": "cs-1@5664ed5db3341b162da886e2fdd2841e43d4f0da4be220b8eb008a30c6ebdcaf", "expected_disposition": "ValidationError(cause=ArtifactIntegrityError)", "observed_disposition": "ValidationError(cause=ArtifactIntegrityError)", "outcome": "MET"}
{"fault_id": "ST-12", "evidence_id": "STATE-EV-001", "target_component": "tos.orthostate.records.CompositeState (serialization / reconstruction)", "guard_code_line": "tos/src/tos/canonical/_base.py:187; tos/src/tos/orthostate/records.py:102", "fault_kind": "self_excluded_field_changed_positive_canary", "seed": 0, "input_witness_ref": "cs-1@5664ed5db3341b162da886e2fdd2841e43d4f0da4be220b8eb008a30c6ebdcaf", "expected_disposition": "DIGEST_STABLE_RECONSTRUCTION_IDENTICAL", "observed_disposition": "DIGEST_STABLE_RECONSTRUCTION_IDENTICAL", "outcome": "MET"}
{"fault_id": "ST-08", "evidence_id": "STATE-EV-001", "target_component": "tos.orthostate.records.CompositeState (serialization / reconstruction)", "guard_code_line": "tos/src/tos/canonical/record_pair.py:96", "fault_kind": "same_identity_different_bytes", "seed": 0, "input_witness_ref": "cs-1@5664ed5db3341b162da886e2fdd2841e43d4f0da4be220b8eb008a30c6ebdcaf", "expected_disposition": "CRITICAL_CONFLICT", "observed_disposition": "CRITICAL_CONFLICT", "outcome": "MET"}

```

---- FILE tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/junit.xml ----
```
<?xml version="1.0" encoding="utf-8"?><testsuites name="pytest tests"><testsuite name="pytest" errors="0" failures="0" skipped="0" tests="23" time="0.082" timestamp="2026-08-06T10:56:30.965789+09:00" hostname="ichihun-ui-MacBookPro.local"><testcase classname="tests.orthostate.test_orthostate_l2_fault" name="test_guard_code_lines_are_measured_not_phantom[ST-01]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_l2_fault" name="test_guard_code_lines_are_measured_not_phantom[ST-02]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_l2_fault" name="test_guard_code_lines_are_measured_not_phantom[ST-03]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_l2_fault" name="test_guard_code_lines_are_measured_not_phantom[ST-04]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_l2_fault" name="test_guard_code_lines_are_measured_not_phantom[ST-05]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_l2_fault" name="test_guard_code_lines_are_measured_not_phantom[ST-06]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_l2_fault" name="test_guard_code_lines_are_measured_not_phantom[ST-07]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_l2_fault" name="test_guard_code_lines_are_measured_not_phantom[ST-08]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_l2_fault" name="test_guard_code_lines_are_measured_not_phantom[ST-09]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_l2_fault" name="test_guard_code_lines_are_measured_not_phantom[ST-11]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_l2_fault" name="test_guard_code_lines_are_measured_not_phantom[ST-12]" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_l2_fault" name="test_catalog_is_the_design_section_3_table" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_l2_fault" name="test_st_01_dropped_dimension_is_not_derived_from_its_neighbours" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_l2_fault" name="test_st_02_none_is_not_the_none_state" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_l2_fault" name="test_st_03_dimension_swap_is_unconstructable" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_l2_fault" name="test_st_04_out_of_vocabulary_token_is_rejected" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_l2_fault" name="test_st_11_scalar_meta_type_contamination" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_l2_fault" name="test_st_05_covered_content_tampered_with_a_retained_digest" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_l2_fault" name="test_st_06_digest_substituted_with_covered_content_retained" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_l2_fault" name="test_st_07_unregistered_canonicalization_version" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_l2_fault" name="test_st_09_issued_status_with_a_null_digest" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_l2_fault" name="test_st_12_self_excluded_field_round_trip_is_stable" time="0.000" /><testcase classname="tests.orthostate.test_orthostate_l2_fault" name="test_st_08_same_id_different_bytes_is_a_critical_conflict" time="0.000" /></testsuite></testsuites>
```

---- FILE tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/manifest.yaml ----
```
schema: tos-evidence/manifest/v2
run_id: 20260806T015630Z-12dd4077
evidence_id: STATE-EV-001
primary_adr: ADR-002-005
design_document: docs/plans/2026-07-29-tos-ev-l2-pilot-design.md
evidence_level_stage: EV-L2
discipline_tag: EV-L2 stage execution record only; not a row PASS; L1 hardening prereq + coverage argument
  + P0-1 + independent review remain as stated in claim/coverage_argument blocks.
claim:
  closes_evidence_item: false
  register_status_moved_by_this_run: false
  register_status_at_run_time: READY
  minimum_evidence_level: EV-L1/2
  independent_review: NOT_SIGNED (VER §9.5)
  p0_1_bounds_approval: OPEN
  verification_profile_version: 2.1 (PROPOSED — P0-1 open)
  target_integrity: STABLE_DURING_RUN
  mutated_during_run: []
  note: This document records that named tests executed at the recorded baseline. It asserts no acceptance,
    no PASS, and no coverage of the higher stages the row's minimum level names.
  ev_l2_stage_gates_unmet: []
  stages_executed:
  - EV-L1
  - EV-L2
  stages_executed_note: EV-L1 is executed as its own run package and bound here by prior_stage_runs; this
    package is the EV-L2 stage.
  covered_axis: 'STATE: representability + non-derivation ONLY (NOT durable). The /2 durable/persisted
    limb of the VER:1024 Expected is not evidenced by this run and is registered as a §378 residual; this
    row is therefore NOT PASS-eligible on the evidence axis from this EV-L2 stage alone (design §2.3 alternative
    C, §9). A companion STATE-EV-004 EV-L3 run at this same baseline executes the durable axis (design
    #39); the R-1 discharge disposition is recorded there as a conditional dual-record (evidence limb,
    substrate-class; ADR-002-005 §4 project decision OPEN — pending OQ-1), not by this run.'
prior_stage_runs:
- evidence_id: STATE-EV-001
  run_id: 20260806T015629Z-12dd4077
  stage: EV-L1
  sha256sums_digest: e03f10df1cebc4403333d44e9f5665582e68f85ab171e2e07364c0be26f53c53
  artifacts_reverified:
  - baseline.yaml
  - junit.xml
  - manifest.yaml
  - run.log
  - traceability.csv
  baseline_commit_sha: 12dd40778b0237ea6992a3b0a9ecadb10f865f0f
  baseline_matches_this_run: true
  outcome: ALL_SELECTED_TESTS_GREEN
  reconcile_note: L1 stage executed at THIS baseline (design §6.2 M9), with every traceability file:line
    citation re-measured against the executed source (cited surfaces unchanged since d4160fd0; spot-verified).
    Its traceability declares "[STATE-EV-001 slice — /2 durable persistence deferred]"; this L2 covers
    the storage-independent axis only (design §2.2/§2.3).
supersedes_run_id: []
supersedes_note: Superseded packages are retained unmodified (VER §2.2); this field is the forward pointer,
  not a deletion record.
fault_injection:
  catalog_ref: docs/plans/2026-07-29-tos-ev-l2-pilot-design.md#3
  seed: 0
  seed_pinned: true
  schedule_artifact: fault-timeline.jsonl
  fault_count: 11
  expected_fault_count: 11
  fault_count_matches_catalog: true
  fault_ids:
  - ST-01
  - ST-02
  - ST-03
  - ST-04
  - ST-11
  - ST-05
  - ST-06
  - ST-07
  - ST-09
  - ST-12
  - ST-08
  duplicate_fault_ids: []
  foreign_evidence_id_rows: []
  deviation_faults: []
  misreported_outcome_faults: []
  expected_undefined_faults: []
  unobserved_disposition_faults: []
  all_faults_met: true
  all_faults_met_basis: every row's outcome RE-DERIVED from observed vs expected (the row's own outcome
    field is cross-checked, never trusted); withheld on an empty schedule (0 injected != 0 violations),
    any deviation or misreport, any undefined Expected or unobserved disposition, a duplicated fault id,
    a row from another evidence id, or a recount that disagrees with the catalog size
  l1_hardening_prereq_met: true
  l1_hardening_prereq:
    met: true
    measured_from: structural analysis of the executed source's syntax tree; comments and docstrings cannot
      satisfy any check (the harness never imports tos)
    items:
    - hardening: H-1 allow_inf_nan=False pinned on FrozenModel.model_config
      path: tos/src/tos/canonical/_base.py
      sha256: ca560b2987e078f9afc867c335f35915dfcb5c1065f00073c27bfef613f45dfb
      met: true
      measured:
        bound_keywords:
        - allow_inf_nan
        - extra
        - frozen
        allow_inf_nan: 'False'
    - hardening: H-2 precision/rounding/boundary comparability + boundary-aware comparison
      path: tos/src/tos/spg/predicates.py
      sha256: 0e135bee214bdbe55654e40586d0693d5b44d9dffbc56f7abaad8531e041327e
      met: true
      measured:
        unit_metadata_keys:
        - unit
        - multiplier
        - sign
        - precision
        - rounding
        - boundary
        missing_metadata_keys: []
        boundary_comparison_defined: true
    - hardening: H-4 canonicalization scheme lookup wrapped as ArtifactIntegrityError
      path: tos/src/tos/canonical/canonicalization.py
      sha256: 18d855970b3ae0eebc6b7b6db6b5e7d93cf52179360d7986883792ab2057bfe3
      met: true
      measured:
        get_scheme_raises:
        - ArtifactIntegrityError
        module_raises:
        - ArtifactIntegrityError
        - TypeError
coverage_argument:
  specification: tos-spec/src/part-1-foundation/VER-002-001-Safety-Critical-Architecture-Verification-Evidence-Specification.md
    §2.7 (line 76-78) — a finite set of executed evidence cases does not by itself discharge a universally-quantified
    safety claim. Both this row's Expected clauses are universally quantified, so the coverage argument
    is mandatory.
  boundary_values: per-dimension boundary combinations exercised (seed-fixed)
  adverse_scenario_set: ADR-002-021 PROPOSED (unapproved) — adversarial-combination leg UNMET; applicability
    to non-risk row = OQ; residual per §378
  unexercised_residual_ref:
  - 'STATE-EV-001 durable/persisted axis — VER:1024 "durable"; ADR-002-005 §13:197 "SHALL be durable and
    reconstructable after crash"; AC-005-1:237 "representable and persisted". Referent is a real persisted
    authoritative record surviving a real fault: absent from an in-memory model, EV-L3 (VER:151-153; STATE-EV-004
    EV-L3 VER:1043). Persistence technology: pilot-scope decision recorded (design #39 §3, stdlib sqlite3
    WAL synchronous=FULL); the ADR-002-005 §4:61 project decision remains OPEN (OQ-1). Critical, so WAIVED_WITH_RESIDUAL_RISK
    is unavailable (VER:131) — a real gap at this stage; the companion STATE-EV-004 EV-L3 run at this
    baseline executes this axis.'
  unexercised_residual_note: 'The §378 Residual Risk Register INSTANCE is absent (measured: verification/
    holds only RESIDUAL-RISK-ACCEPTANCE-RECORD-template.yaml; tos-evidence/ holds zero residual artifacts)
    — creating it is prerequisite work. Each entry SHALL carry all twelve VER:3293-3306 fields (risk identity;
    affected requirement/ADR; scope; credible failure sequence; maximum economic effect; existing controls;
    detection/containment bound; owner; approver; expiration/review date; required scope reduction; evidence
    references), and owner/approver come through the P0-3 role system (D1). The refs above are pointers,
    not a union: separate residual risks SHALL NOT be unioned at a consumer (VER:3308) — each is registered
    independently.'
  discharged: false
  discharged_note: The adversarial-combination leg cannot be discharged while ADR-002-021 is PROPOSED,
    and an unresolved applicability question defaults to APPLICABLE (VER §2.4 line 64-66; VER:173 'Missing
    resolution is a blocker and SHALL NOT default to the lowest level'). This run therefore records the
    argument's state; it does not claim to have made it.
execution:
  command:
  - /Users/harris/Development/private/kis_unified_sts/.venv/bin/python
  - -m
  - pytest
  - tos/tests/orthostate/test_orthostate_l2_fault.py
  - -q
  - --junitxml=/Users/harris/Development/private/kis_unified_sts/tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/junit.xml
  - --hypothesis-seed=0
  - --l2-fault-timeline=/Users/harris/Development/private/kis_unified_sts/tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/fault-timeline.jsonl
  cwd: /Users/harris/Development/private/kis_unified_sts
  env_overrides:
    PYTHONPATH: tos/src
    PYTHONHASHSEED: '0'
  started_utc: '2026-08-06T01:56:30.762052+00:00'
  finished_utc: '2026-08-06T01:56:31.102799+00:00'
  monotonic_duration_s: 0.340735
  return_code: 0
  outcome: ALL_SELECTED_TESTS_GREEN
  junit_summary:
    tests: 23
    failures: 0
    errors: 0
    skipped: 0
    time_s: '0.082'
  stage_gate_outcome: EV_L2_STAGE_GATES_MET
test_nodes:
- tos/tests/orthostate/test_orthostate_l2_fault.py
baseline:
  file: baseline.yaml
  sha256: deb216da3f37d96e33456e647cb94514386fe529bb23ddd54d25cdee57e6db3d
  completeness: NOT complete (VER §3 line 109 has no 'as applicable' clause). VER §3 fields without an
    existing artifact are NOT_APPLICABLE_PURE_MODEL_L2; the unmet set is enumerated in baseline.yaml::ver_002_001_section_3_unmet_fields.
  ver3_unmet_field_count: 16
artifacts:
- name: baseline.yaml
  sha256: deb216da3f37d96e33456e647cb94514386fe529bb23ddd54d25cdee57e6db3d
  bytes: 26152
- name: fault-timeline.jsonl
  sha256: 77ae73ef8ce54735e6d32a8501c4c2804bce6fc1e139cb2433c7bf9d76eafd8f
  bytes: 5847
- name: junit.xml
  sha256: 9fe688d87ffb21517bad96c0195299790363e9ed8694f6655be9c428b9603c39
  bytes: 3437
- name: run.log
  sha256: c75ad4c132b4b21001eee47f771b0bdc4977ef2eac4bce153d60a2fa15240392
  bytes: 589
- name: traceability.csv
  sha256: 14b9e64db6de7c3645cd6faed654bc8de3aebd33d5116ae33399eb87546ec673
  bytes: 928
artifact_closure_note: manifest.yaml cannot contain its own digest; sha256sums.txt is written last and
  closes over every retained file including this manifest (VER §9.2).

```

---- FILE tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/run.log ----
```
$ PYTHONPATH=tos/src PYTHONHASHSEED=0 /Users/harris/Development/private/kis_unified_sts/.venv/bin/python -m pytest tos/tests/orthostate/test_orthostate_l2_fault.py -q --junitxml=/Users/harris/Development/private/kis_unified_sts/tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/junit.xml --hypothesis-seed=0 --l2-fault-timeline=/Users/harris/Development/private/kis_unified_sts/tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/fault-timeline.jsonl

--- stdout ---
.......................                                                  [100%]

--- stderr ---

--- return code: 0 ---

```

---- FILE tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/sha256sums.txt ----
```
deb216da3f37d96e33456e647cb94514386fe529bb23ddd54d25cdee57e6db3d  baseline.yaml
77ae73ef8ce54735e6d32a8501c4c2804bce6fc1e139cb2433c7bf9d76eafd8f  fault-timeline.jsonl
9fe688d87ffb21517bad96c0195299790363e9ed8694f6655be9c428b9603c39  junit.xml
4419d6e6bb62c92143eba39821bb46df9c32a40e2bc332be9feeed728d5491e9  manifest.yaml
c75ad4c132b4b21001eee47f771b0bdc4977ef2eac4bce153d60a2fa15240392  run.log
14b9e64db6de7c3645cd6faed654bc8de3aebd33d5116ae33399eb87546ec673  traceability.csv

```

---- FILE tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/traceability.csv ----
```
evidence_id,primary_adr,design_document,test_node,mapping_basis,evidence_claim
STATE-EV-001,ADR-002-005,docs/plans/2026-07-29-tos-ev-l2-pilot-design.md,tos/tests/orthostate/test_orthostate_l2_fault.py,"EV-L2 pilot design §3 (2026-07-29-tos-ev-l2-pilot-design.md:159) fault catalog — 11 faults ST-01..ST-09/11/12, enumerated at test_orthostate_l2_fault.py:106 and guard-anchored at :81; module-wide @pytest.mark.l2_fault at :60. Each test injects a single controlled failure into tos.orthostate.records.CompositeState and inspects that component's own authoritative construction verdict (VER-002-001 §5 lines 146-148). Storage-independent axis ONLY — the /2 durable limb (VER:1024; ADR-002-005 §13:197; AC-005-1:237) is NOT evidenced and is carried as a §378 residual (design §2.2/§2.3 alternative C, §9). All file:line citations re-measured at baseline eb92ea46.",STAGE_RECORD_ONLY (does not close the evidence item)

```


============================================================================
# PACKAGE tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077
============================================================================

---- FILE tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/baseline.yaml ----
```
schema: tos-evidence/baseline/v2
run_id: 20260806T015631Z-12dd4077
evidence_id: SPG-EV-002
evidence_level_stage: EV-L2
generated_utc: '2026-08-06T01:56:31.865054+00:00'
contract:
  run_manifest_contract: docs/plans/2026-07-20-tos-boundary-and-import-firewall-design.md §5.1 (seven
    items)
  ver_specification: tos-spec/src/part-1-foundation/VER-002-001-Safety-Critical-Architecture-Verification-Evidence-Specification.md
    §2.3/§3/§8/§9.1/§9.2/§9.5
  completeness: EV-L2 component-fault. VER §3 requires 22 baseline fields and states that 'A run without
    a complete baseline is invalid' (line 109) — a clause carrying no 'as applicable' qualifier, unlike
    §7 line 258, so it stands beside P0-1 and the independent signature as a gate, not a waivable formality.
    The unmet-field list and every reason are retained from EV-L1 with the stage attribution updated (NOT_APPLICABLE_EV_L1
    -> NOT_APPLICABLE_PURE_MODEL_L2); the enumerated list is ver_002_001_section_3_unmet_fields below.
    The absent artifacts are the broker, authority/human, reconciliation, network and recovery instances
    — none of which a pure-model, single-component, non-transmitting fault run brings into existence.
    Under VER §3's full standard this baseline is NOT complete.
evidence_register_row:
  source: tos-spec/src/part-1-foundation/verification/EVIDENCE-REGISTER-002.csv
  evidence_id: SPG-EV-002
  domain: Safety Profile Governance
  title: Semantic Units, Numeric, and Cross-Field Validation
  primary_adr: ADR-002-014
  criticality: Critical
  minimum_evidence_level: EV-L1/2
  status_at_run_time: PASS
  implementation_owner: ai-impl(claude-orchestrated)
  evidence_owner: operator
  independent_reviewer: ai-review(decorrelated)+operator-countersign
design1_5_1:
  item_1_repository_and_package:
    git_commit_sha: 12dd40778b0237ea6992a3b0a9ecadb10f865f0f
    git_short_sha: 12dd4077
    tos_package_version: 0.0.1
    worktree:
      clean: false
      untracked:
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/baseline.yaml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/junit.xml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/manifest.yaml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/sha256sums.txt
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/traceability.csv
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/baseline.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/junit.xml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/manifest.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/sha256sums.txt
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/traceability.csv
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/baseline.yaml
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/fault-timeline.jsonl
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/junit.xml
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/manifest.yaml
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/sha256sums.txt
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/traceability.csv
      modified_unstaged: []
      staged: []
      all_dirty_paths:
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/baseline.yaml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/junit.xml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/manifest.yaml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/sha256sums.txt
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/traceability.csv
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/baseline.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/junit.xml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/manifest.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/sha256sums.txt
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/traceability.csv
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/baseline.yaml
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/fault-timeline.jsonl
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/junit.xml
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/manifest.yaml
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/sha256sums.txt
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/traceability.csv
      note: 'A non-empty list does not by itself invalidate the run: the executed files are pinned individually
        by target_file_digests below. Paths outside the executed set belong to other work in the same
        worktree.'
    worktree_after_run:
      clean: false
      untracked:
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/baseline.yaml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/junit.xml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/manifest.yaml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/sha256sums.txt
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/traceability.csv
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/fault-timeline.jsonl
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/junit.xml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/baseline.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/junit.xml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/manifest.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/sha256sums.txt
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/traceability.csv
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/baseline.yaml
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/fault-timeline.jsonl
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/junit.xml
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/manifest.yaml
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/sha256sums.txt
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/traceability.csv
      modified_unstaged: []
      staged: []
      all_dirty_paths:
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/baseline.yaml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/junit.xml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/manifest.yaml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/sha256sums.txt
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/traceability.csv
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/fault-timeline.jsonl
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/junit.xml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/baseline.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/junit.xml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/manifest.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/sha256sums.txt
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/traceability.csv
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/baseline.yaml
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/fault-timeline.jsonl
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/junit.xml
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/manifest.yaml
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/sha256sums.txt
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/traceability.csv
      note: 'A non-empty list does not by itself invalidate the run: the executed files are pinned individually
        by target_file_digests below. Paths outside the executed set belong to other work in the same
        worktree.'
    worktree_delta:
      became_dirty_during_run:
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/fault-timeline.jsonl
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/junit.xml
      became_clean_during_run: []
      stable: false
    target_files_clean: true
    target_files_stable_during_run: true
    target_file_digests:
    - path: tools/tos_evidence_run.py
      sha256_before_run: 562c52eebc1758ccf804b55c2eb03a1887a07014433d649ec0e01a7a143fb0aa
      sha256_after_run: 562c52eebc1758ccf804b55c2eb03a1887a07014433d649ec0e01a7a143fb0aa
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: false
    - path: tos/src/tos/canonical/__init__.py
      sha256_before_run: 46fd765566c6c6b567b1f87c4a70f64014bb1678def66c44d798d9f85a9d75bb
      sha256_after_run: 46fd765566c6c6b567b1f87c4a70f64014bb1678def66c44d798d9f85a9d75bb
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/canonical/_base.py
      sha256_before_run: ca560b2987e078f9afc867c335f35915dfcb5c1065f00073c27bfef613f45dfb
      sha256_after_run: ca560b2987e078f9afc867c335f35915dfcb5c1065f00073c27bfef613f45dfb
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/canonical/canonicalization.py
      sha256_before_run: 18d855970b3ae0eebc6b7b6db6b5e7d93cf52179360d7986883792ab2057bfe3
      sha256_after_run: 18d855970b3ae0eebc6b7b6db6b5e7d93cf52179360d7986883792ab2057bfe3
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/canonical/record_pair.py
      sha256_before_run: 764c96796038dcab512071aa31075b79160e8cda247b50fcf5b2dfbd4c81f551
      sha256_after_run: 764c96796038dcab512071aa31075b79160e8cda247b50fcf5b2dfbd4c81f551
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/spg/__init__.py
      sha256_before_run: 216b0249c63e6f11cb1e21c3c2668764aef96cc2b88664fe01f06e9d3c04d256
      sha256_after_run: 216b0249c63e6f11cb1e21c3c2668764aef96cc2b88664fe01f06e9d3c04d256
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/spg/_base.py
      sha256_before_run: 72d6ef47c9289896eb036d7931f285d3b31e310f8ebbc0a5281b0f677889076a
      sha256_after_run: 72d6ef47c9289896eb036d7931f285d3b31e310f8ebbc0a5281b0f677889076a
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/spg/predicates.py
      sha256_before_run: 0e135bee214bdbe55654e40586d0693d5b44d9dffbc56f7abaad8531e041327e
      sha256_after_run: 0e135bee214bdbe55654e40586d0693d5b44d9dffbc56f7abaad8531e041327e
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/spg/records.py
      sha256_before_run: dd8f5492bf4795d80c26f344b92fb85c5c4d615954afe3ab199c190c27745dc0
      sha256_after_run: dd8f5492bf4795d80c26f344b92fb85c5c4d615954afe3ab199c190c27745dc0
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/spg/vocabulary.py
      sha256_before_run: 878b429c2d2f53df430a9ba88680240e28ed38d2bfcd322f64b1ff7ed3aa96cc
      sha256_after_run: 878b429c2d2f53df430a9ba88680240e28ed38d2bfcd322f64b1ff7ed3aa96cc
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/tests/spg/test_spg_l2_fault.py
      sha256_before_run: 8656675731a2939884f3a6cfbae750cbae85ff2dc38da181e879c7319a86dd55
      sha256_after_run: 8656675731a2939884f3a6cfbae750cbae85ff2dc38da181e879c7319a86dd55
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/tests/test_digest_binding.py
      sha256_before_run: 295aafb7a44cabc740a1b1973cd599652bb6a5bc9d70a09727477204850264be
      sha256_after_run: 295aafb7a44cabc740a1b1973cd599652bb6a5bc9d70a09727477204850264be
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
  item_2_interpreter_and_dependencies:
    python:
      version: 3.12.2
      version_full: 3.12.2 (main, Dec 11 2025, 16:36:08) [Clang 17.0.0 (clang-1700.4.4.1)]
      implementation: CPython
      executable: /Users/harris/Development/private/kis_unified_sts/.venv/bin/python
    installed_versions_measured:
      pydantic: 2.12.5
      hypothesis: 6.151.5
      pytest: 9.0.2
      numpy: 1.26.4
      pandas: 2.3.3
      pyyaml: 6.0.3
      tos: NOT_INSTALLED
    pinned_in_tos_pyproject:
      pydantic: 2.12.5
      numpy: 2.4.0
      pandas: 2.3.3
      pyyaml: 6.0.3
      pytest: 9.0.2
      hypothesis: 6.150.2
    pins_satisfied: false
    pin_vs_installed_drift:
    - distribution: hypothesis
      pinned: 6.150.2
      installed: 6.151.5
    - distribution: numpy
      pinned: 2.4.0
      installed: 1.26.4
    drift_note: 'pins_satisfied is the machine-readable claim; an empty drift list = the executed interpreter
      matches every pin. A non-empty list is recorded, not resolved: the installed version is what executed.'
  item_3_execution_environment: &id001
    os: Darwin
    os_release: 25.5.0
    machine: arm64
    platform: macOS-26.5.2-arm64-arm-64bit
    python_implementation: CPython
  item_4_harness_version: &id002
    harness_path: tools/tos_evidence_run.py
    harness_sha256: 562c52eebc1758ccf804b55c2eb03a1887a07014433d649ec0e01a7a143fb0aa
    harness_tracked: true
    harness_at_commit: aac2827bb5941603705da735ea079129ce3d942a
    harness_dirty: false
    pytest_version: 9.0.2
    note: 'design #1 §5.1 item 4 — Phase 1 harness version = git digest, which exists only once the harness
      is committed. Until then harness_at_commit is NOT_IN_COMMIT and harness_sha256 is the only identity
      of the code that ran.'
  item_5_seed_policy: &id003
    policy: fixed
    pytest_flags:
    - --hypothesis-seed=0
    hypothesis_seed: 0
    note: 'VER §9.1 append-only: seed pinned before the run began.'
  item_6_consumed_configuration_artifacts:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: 'No configuration artifact is consumed: bounds are hypothesis-injected generated values, not
      read from a profile, and the run is hermetic (no .env, no YAML).'
  item_7_retained_artifact_digests: Enumerated in manifest.yaml (artifacts) and closed over by sha256sums.txt,
    which is written last and covers every retained file including the manifest.
ver_002_001_section_3_baseline:
  repository_commit_sha:
    status: RECORDED
    value: 12dd40778b0237ea6992a3b0a9ecadb10f865f0f
  build_artifact_digest:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: 'Phase 1 executes from the source tree; no built distribution artifact is produced or consumed
      (design #1 §5.1 items 1/4 — the git digest stands in). The executed bytes are pinned individually
      by design1_5_1.item_1_repository_and_package.target_file_digests.'
  rfc_adr_versions:
    status: RECORDED
    value:
    - role: primary_adr
      path: tos-spec/src/part-1-foundation/ADR-002-014-Hard-Safety-Envelope-and-Runtime-Safety-Profile-Governance.md
      sha256: ba84bb15e30658323d9be6f9cf11fe16a90569789a22f96a2db9203b649f6709
    - role: design_document
      path: docs/plans/2026-07-29-tos-ev-l2-pilot-design.md
      sha256: 43dff50a6567f23d5aec58f8c061282e8b8e42944f0d66ea190e9d26c7b0d5a9
    - role: ver_specification
      path: tos-spec/src/part-1-foundation/VER-002-001-Safety-Critical-Architecture-Verification-Evidence-Specification.md
      sha256: 217a43ab1b32e04fe6515316a7383c3e9e75bb177ed18c7c7e7267ca0a3c2a38
    - role: boundary_design_1
      path: docs/plans/2026-07-20-tos-boundary-and-import-firewall-design.md
      sha256: 2449f18d6088e21f601da623d27e6eff74066661f5d92116db2eda1a59b5a988
    reason: The corpus documents carry no separate version field; their content sha256 is the version
      identity.
  hard_safety_envelope_version:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      a pure-model EV-L2 component-fault run consumes none — it injects faults into a single in-process
      component and inspects that component''s own authoritative verdict. Recorded N/A per design #1 §5.1
      read forward to EV-L2 (EV-L2 pilot design §6.2 M2 / §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  runtime_safety_profile_version:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      a pure-model EV-L2 component-fault run consumes none — it injects faults into a single in-process
      component and inspects that component''s own authoritative verdict. Recorded N/A per design #1 §5.1
      read forward to EV-L2 (EV-L2 pilot design §6.2 M2 / §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  human_authority_policy_generation_and_digest:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      a pure-model EV-L2 component-fault run consumes none — it injects faults into a single in-process
      component and inspects that component''s own authoritative verdict. Recorded N/A per design #1 §5.1
      read forward to EV-L2 (EV-L2 pilot design §6.2 M2 / §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  effective_principal_graph_generation_and_digest:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      a pure-model EV-L2 component-fault run consumes none — it injects faults into a single in-process
      component and inspects that component''s own authoritative verdict. Recorded N/A per design #1 §5.1
      read forward to EV-L2 (EV-L2 pilot design §6.2 M2 / §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  evidence_integrity_policy_generation_and_digest:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      a pure-model EV-L2 component-fault run consumes none — it injects faults into a single in-process
      component and inspects that component''s own authoritative verdict. Recorded N/A per design #1 §5.1
      read forward to EV-L2 (EV-L2 pilot design §6.2 M2 / §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  recovery_barrier_policy_generation_and_digest:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      a pure-model EV-L2 component-fault run consumes none — it injects faults into a single in-process
      component and inspects that component''s own authoritative verdict. Recorded N/A per design #1 §5.1
      read forward to EV-L2 (EV-L2 pilot design §6.2 M2 / §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  critical_input_policy_generation_and_digest:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      a pure-model EV-L2 component-fault run consumes none — it injects faults into a single in-process
      component and inspects that component''s own authoritative verdict. Recorded N/A per design #1 §5.1
      read forward to EV-L2 (EV-L2 pilot design §6.2 M2 / §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  venue_constraint_policy_generation_and_digest:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      a pure-model EV-L2 component-fault run consumes none — it injects faults into a single in-process
      component and inspects that component''s own authoritative verdict. Recorded N/A per design #1 §5.1
      read forward to EV-L2 (EV-L2 pilot design §6.2 M2 / §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  trading_approval_policy_generation_and_digest:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      a pure-model EV-L2 component-fault run consumes none — it injects faults into a single in-process
      component and inspects that component''s own authoritative verdict. Recorded N/A per design #1 §5.1
      read forward to EV-L2 (EV-L2 pilot design §6.2 M2 / §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  currentness_policy_generation_and_digest:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      a pure-model EV-L2 component-fault run consumes none — it injects faults into a single in-process
      component and inspects that component''s own authoritative verdict. Recorded N/A per design #1 §5.1
      read forward to EV-L2 (EV-L2 pilot design §6.2 M2 / §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  restricted_live_trial_policy_generation_and_digest:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      a pure-model EV-L2 component-fault run consumes none — it injects faults into a single in-process
      component and inspects that component''s own authoritative verdict. Recorded N/A per design #1 §5.1
      read forward to EV-L2 (EV-L2 pilot design §6.2 M2 / §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  broker_capability_profile_version:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: Evidence Register broker_capability_profile_version for this row = 'N/A'; the row's minimum
      evidence level (EV-L1/2) carries no +Broker suffix and no Broker Capability Profile instance exists
      (template only). P0-2 is not in this run's scope.
  verification_profile_version:
    status: RECORDED
    value:
      version: 2.1 (PROPOSED — P0-1 open)
      register_column_value: 2.1-PROPOSED
      artifact:
        path: tos-spec/src/part-1-foundation/verification/VERIFICATION-PROFILE-002.yaml
        sha256: d837c7e74b0fbe70d7cf2dfb30e412a29042577a0a38dcba22c649dd457d5064
      approval_state: PROPOSED — P0-1 (bounds approval) OPEN
    reason: Recorded, not approved. VER §6 numeric bounds remain unapproved; no bound value is consumed
      by this run (bounds are hypothesis-injected, not hardcoded).
  database_schema_migration_version:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: EV-L1 model/property verification exercises no persistence substrate; durable persistence
      is the deferred /2 stage.
  deployment_manifest_digest:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: 'Nothing is deployed: the kernel is non-transmitting and is executed in-process by pytest.'
  workload_identities_and_key_versions:
    status: NOT_APPLICABLE_PURE_MODEL_L2
    reason: No workload identity, credential, or key material is used — the run is hermetic (no network,
      no .env, no clock authority).
  environment_identifier:
    status: RECORDED
    value: *id001
  test_harness_version:
    status: RECORDED
    value: *id002
  fault_injection_schedule_and_seed:
    status: RECORDED
    value:
      fault_schedule:
        catalog_ref: docs/plans/2026-07-29-tos-ev-l2-pilot-design.md#4
        seed: 0
        seed_pinned: true
        schedule_artifact: fault-timeline.jsonl
        fault_count: 12
        expected_fault_count: 12
        fault_count_matches_catalog: true
        fault_ids:
        - SPG-01
        - SPG-02
        - SPG-03
        - SPG-05
        - SPG-06
        - SPG-08
        - SPG-09
        - SPG-10
        - SPG-11
        - SPG-14
        - SPG-15
        - SPG-13
        duplicate_fault_ids: []
        foreign_evidence_id_rows: []
        deviation_faults: []
        misreported_outcome_faults: []
        expected_undefined_faults: []
        unobserved_disposition_faults: []
        all_faults_met: true
        all_faults_met_basis: every row's outcome RE-DERIVED from observed vs expected (the row's own
          outcome field is cross-checked, never trusted); withheld on an empty schedule (0 injected !=
          0 violations), any deviation or misreport, any undefined Expected or unobserved disposition,
          a duplicated fault id, a row from another evidence id, or a recount that disagrees with the
          catalog size
        l1_hardening_prereq_met: true
        l1_hardening_prereq:
          met: true
          measured_from: structural analysis of the executed source's syntax tree; comments and docstrings
            cannot satisfy any check (the harness never imports tos)
          items:
          - hardening: H-1 allow_inf_nan=False pinned on FrozenModel.model_config
            path: tos/src/tos/canonical/_base.py
            sha256: ca560b2987e078f9afc867c335f35915dfcb5c1065f00073c27bfef613f45dfb
            met: true
            measured:
              bound_keywords:
              - allow_inf_nan
              - extra
              - frozen
              allow_inf_nan: 'False'
          - hardening: H-2 precision/rounding/boundary comparability + boundary-aware comparison
            path: tos/src/tos/spg/predicates.py
            sha256: 0e135bee214bdbe55654e40586d0693d5b44d9dffbc56f7abaad8531e041327e
            met: true
            measured:
              unit_metadata_keys:
              - unit
              - multiplier
              - sign
              - precision
              - rounding
              - boundary
              missing_metadata_keys: []
              boundary_comparison_defined: true
          - hardening: H-4 canonicalization scheme lookup wrapped as ArtifactIntegrityError
            path: tos/src/tos/canonical/canonicalization.py
            sha256: 18d855970b3ae0eebc6b7b6db6b5e7d93cf52179360d7986883792ab2057bfe3
            met: true
            measured:
              get_scheme_raises:
              - ArtifactIntegrityError
              module_raises:
              - ArtifactIntegrityError
              - TypeError
      seed: *id003
    reason: 'EV-L2: the VER §9.1 append-only fault schedule and the seed are both recorded. This field
      is no longer PARTIAL — it is the one VER §3 field the EV-L2 stage completes relative to EV-L1.'
ver_002_001_section_3_unmet_fields:
- broker_capability_profile_version
- build_artifact_digest
- critical_input_policy_generation_and_digest
- currentness_policy_generation_and_digest
- database_schema_migration_version
- deployment_manifest_digest
- effective_principal_graph_generation_and_digest
- evidence_integrity_policy_generation_and_digest
- hard_safety_envelope_version
- human_authority_policy_generation_and_digest
- recovery_barrier_policy_generation_and_digest
- restricted_live_trial_policy_generation_and_digest
- runtime_safety_profile_version
- trading_approval_policy_generation_and_digest
- venue_constraint_policy_generation_and_digest
- workload_identities_and_key_versions
ver_002_001_section_3_unmet_note: 'VER §3 line 109 (''A run without a complete baseline is invalid'')
  has no ''as applicable'' clause. This list names every field that is not RECORDED, so the gap is machine-checkable:
  an empty list would be the claim that the baseline is complete, and this run does not make that claim.'
test_nodes:
- tos/tests/spg/test_spg_l2_fault.py
- tos/tests/test_digest_binding.py::test_frozen_model_pins_allow_inf_nan_explicitly

```

---- FILE tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/fault-timeline.jsonl ----
```
{"fault_id": "SPG-01", "evidence_id": "SPG-EV-002", "target_component": "tos.spg.predicates.semantic_validation / profile_within_envelope (Safety Profile Validator)", "guard_code_line": "tos/src/tos/spg/predicates.py:536; tos/src/tos/spg/predicates.py:537", "fault_kind": "unit_mismatch", "seed": 0, "input_witness_ref": "b-1@72c6e6cdd3317601e4f87f4d8d3d5f7e0f3e19bb5b2ac68a4446b7841c450b11", "expected_disposition": "REJECTED[UNIT_OR_MULTIPLIER_MISMATCH]{qty}", "observed_disposition": "REJECTED[UNIT_OR_MULTIPLIER_MISMATCH]{qty}", "outcome": "MET"}
{"fault_id": "SPG-02", "evidence_id": "SPG-EV-002", "target_component": "tos.spg.predicates.semantic_validation / profile_within_envelope (Safety Profile Validator)", "guard_code_line": "tos/src/tos/spg/predicates.py:536; tos/src/tos/spg/predicates.py:537", "fault_kind": "multiplier_mismatch", "seed": 0, "input_witness_ref": "b-1@72c6e6cdd3317601e4f87f4d8d3d5f7e0f3e19bb5b2ac68a4446b7841c450b11", "expected_disposition": "REJECTED[UNIT_OR_MULTIPLIER_MISMATCH]{qty}", "observed_disposition": "REJECTED[UNIT_OR_MULTIPLIER_MISMATCH]{qty}", "outcome": "MET"}
{"fault_id": "SPG-03", "evidence_id": "SPG-EV-002", "target_component": "tos.spg.predicates.semantic_validation / profile_within_envelope (Safety Profile Validator)", "guard_code_line": "tos/src/tos/spg/predicates.py:536; tos/src/tos/spg/predicates.py:537", "fault_kind": "sign_mismatch", "seed": 0, "input_witness_ref": "b-1@72c6e6cdd3317601e4f87f4d8d3d5f7e0f3e19bb5b2ac68a4446b7841c450b11", "expected_disposition": "REJECTED[UNIT_OR_MULTIPLIER_MISMATCH]{qty}", "observed_disposition": "REJECTED[UNIT_OR_MULTIPLIER_MISMATCH]{qty}", "outcome": "MET"}
{"fault_id": "SPG-05", "evidence_id": "SPG-EV-002", "target_component": "tos.spg.predicates.semantic_validation / profile_within_envelope (Safety Profile Validator)", "guard_code_line": "tos/src/tos/canonical/_base.py:87", "fault_kind": "nan_magnitude", "seed": 0, "input_witness_ref": "b-1@72c6e6cdd3317601e4f87f4d8d3d5f7e0f3e19bb5b2ac68a4446b7841c450b11", "expected_disposition": "ValidationError[finite_number@envelope_max]", "observed_disposition": "ValidationError[finite_number@envelope_max]", "outcome": "MET"}
{"fault_id": "SPG-06", "evidence_id": "SPG-EV-002", "target_component": "tos.spg.predicates.semantic_validation / profile_within_envelope (Safety Profile Validator)", "guard_code_line": "tos/src/tos/canonical/_base.py:87", "fault_kind": "infinity_magnitude", "seed": 0, "input_witness_ref": "b-1@72c6e6cdd3317601e4f87f4d8d3d5f7e0f3e19bb5b2ac68a4446b7841c450b11", "expected_disposition": "ValidationError[finite_number@envelope_max]", "observed_disposition": "ValidationError[finite_number@envelope_max]", "outcome": "MET"}
{"fault_id": "SPG-08", "evidence_id": "SPG-EV-002", "target_component": "tos.spg.predicates.semantic_validation / profile_within_envelope (Safety Profile Validator)", "guard_code_line": "tos/src/tos/spg/predicates.py:536; tos/src/tos/spg/predicates.py:200", "fault_kind": "precision_rounding_boundary_mismatch+exclusive_boundary_equality", "seed": 0, "input_witness_ref": "b-1@72c6e6cdd3317601e4f87f4d8d3d5f7e0f3e19bb5b2ac68a4446b7841c450b11", "expected_disposition": "A=boundary=REJECTED[UNIT_OR_MULTIPLIER_MISMATCH]{qty}+precision=REJECTED[UNIT_OR_MULTIPLIER_MISMATCH]{qty}+rounding=REJECTED[UNIT_OR_MULTIPLIER_MISMATCH]{qty}|B=REJECTED[EXCEEDS_ENVELOPE]{qty}", "observed_disposition": "A=boundary=REJECTED[UNIT_OR_MULTIPLIER_MISMATCH]{qty}+precision=REJECTED[UNIT_OR_MULTIPLIER_MISMATCH]{qty}+rounding=REJECTED[UNIT_OR_MULTIPLIER_MISMATCH]{qty}|B=REJECTED[EXCEEDS_ENVELOPE]{qty}", "outcome": "MET"}
{"fault_id": "SPG-09", "evidence_id": "SPG-EV-002", "target_component": "tos.spg.predicates.semantic_validation / profile_within_envelope (Safety Profile Validator)", "guard_code_line": "tos/src/tos/spg/predicates.py:301", "fault_kind": "over_envelope_value", "seed": 0, "input_witness_ref": "b-1@72c6e6cdd3317601e4f87f4d8d3d5f7e0f3e19bb5b2ac68a4446b7841c450b11", "expected_disposition": "REJECTED[EXCEEDS_ENVELOPE]{qty}", "observed_disposition": "REJECTED[EXCEEDS_ENVELOPE]{qty}", "outcome": "MET"}
{"fault_id": "SPG-10", "evidence_id": "SPG-EV-002", "target_component": "tos.spg.predicates.semantic_validation / profile_within_envelope (Safety Profile Validator)", "guard_code_line": "tos/src/tos/spg/predicates.py:293", "fault_kind": "undeclared_dimension", "seed": 0, "input_witness_ref": "b-1@72c6e6cdd3317601e4f87f4d8d3d5f7e0f3e19bb5b2ac68a4446b7841c450b11", "expected_disposition": "REJECTED[EXCEEDS_ENVELOPE]{notional}", "observed_disposition": "REJECTED[EXCEEDS_ENVELOPE]{notional}", "outcome": "MET"}
{"fault_id": "SPG-11", "evidence_id": "SPG-EV-002", "target_component": "tos.spg.predicates.semantic_validation / profile_within_envelope (Safety Profile Validator)", "guard_code_line": "tos/src/tos/spg/predicates.py:282", "fault_kind": "omitted_mandatory_dimension", "seed": 0, "input_witness_ref": "b-1@72c6e6cdd3317601e4f87f4d8d3d5f7e0f3e19bb5b2ac68a4446b7841c450b11", "expected_disposition": "REJECTED[EXCEEDS_ENVELOPE]{notional}", "observed_disposition": "REJECTED[EXCEEDS_ENVELOPE]{notional}", "outcome": "MET"}
{"fault_id": "SPG-14", "evidence_id": "SPG-EV-002", "target_component": "tos.spg.predicates.semantic_validation / profile_within_envelope (Safety Profile Validator)", "guard_code_line": "tos/src/tos/spg/predicates.py:282; tos/src/tos/spg/predicates.py:293", "fault_kind": "vector_dimension_identity_mismatch_equal_cardinality", "seed": 0, "input_witness_ref": "b-1@72c6e6cdd3317601e4f87f4d8d3d5f7e0f3e19bb5b2ac68a4446b7841c450b11", "expected_disposition": "REJECTED[EXCEEDS_ENVELOPE]{latency,notional}", "observed_disposition": "REJECTED[EXCEEDS_ENVELOPE]{latency,notional}", "outcome": "MET"}
{"fault_id": "SPG-15", "evidence_id": "SPG-EV-002", "target_component": "tos.spg.predicates.semantic_validation / profile_within_envelope (Safety Profile Validator)", "guard_code_line": "tos/src/tos/spg/predicates.py:300", "fault_kind": "none_magnitude", "seed": 0, "input_witness_ref": "b-1@72c6e6cdd3317601e4f87f4d8d3d5f7e0f3e19bb5b2ac68a4446b7841c450b11", "expected_disposition": "REJECTED[EXCEEDS_ENVELOPE]{qty}", "observed_disposition": "REJECTED[EXCEEDS_ENVELOPE]{qty}", "outcome": "MET"}
{"fault_id": "SPG-13", "evidence_id": "SPG-EV-002", "target_component": "tos.spg.predicates.semantic_validation / profile_within_envelope (Safety Profile Validator)", "guard_code_line": "tos/src/tos/spg/predicates.py:559; tos/src/tos/spg/predicates.py:560", "fault_kind": "cross_field_constraint_violated_and_unproven", "seed": 0, "input_witness_ref": "b-1@72c6e6cdd3317601e4f87f4d8d3d5f7e0f3e19bb5b2ac68a4446b7841c450b11", "expected_disposition": "REJECTED[CROSS_FIELD_CONSTRAINT_VIOLATION]{}|REJECTED[CROSS_FIELD_CONSTRAINT_VIOLATION]{}", "observed_disposition": "REJECTED[CROSS_FIELD_CONSTRAINT_VIOLATION]{}|REJECTED[CROSS_FIELD_CONSTRAINT_VIOLATION]{}", "outcome": "MET"}

```

---- FILE tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/junit.xml ----
```
<?xml version="1.0" encoding="utf-8"?><testsuites name="pytest tests"><testsuite name="pytest" errors="0" failures="0" skipped="0" tests="35" time="0.114" timestamp="2026-08-06T10:56:31.626551+09:00" hostname="ichihun-ui-MacBookPro.local"><testcase classname="tests.spg.test_spg_l2_fault" name="test_guard_code_lines_are_measured_not_phantom[SPG-01]" time="0.001" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_guard_code_lines_are_measured_not_phantom[SPG-02]" time="0.000" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_guard_code_lines_are_measured_not_phantom[SPG-03]" time="0.000" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_guard_code_lines_are_measured_not_phantom[SPG-05]" time="0.000" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_guard_code_lines_are_measured_not_phantom[SPG-06]" time="0.000" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_guard_code_lines_are_measured_not_phantom[SPG-08]" time="0.000" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_guard_code_lines_are_measured_not_phantom[SPG-09]" time="0.000" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_guard_code_lines_are_measured_not_phantom[SPG-10]" time="0.000" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_guard_code_lines_are_measured_not_phantom[SPG-11]" time="0.000" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_guard_code_lines_are_measured_not_phantom[SPG-13]" time="0.000" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_guard_code_lines_are_measured_not_phantom[SPG-14]" time="0.000" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_guard_code_lines_are_measured_not_phantom[SPG-15]" time="0.000" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_catalog_is_the_design_section_4_table" time="0.000" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_spg_01_02_03_incomparable_unit_metadata_is_rejected[SPG-01-unit_mismatch-env_meta0-profile_meta0]" time="0.001" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_spg_01_02_03_incomparable_unit_metadata_is_rejected[SPG-02-multiplier_mismatch-env_meta1-profile_meta1]" time="0.001" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_spg_01_02_03_incomparable_unit_metadata_is_rejected[SPG-03-sign_mismatch-env_meta2-profile_meta2]" time="0.001" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_spg_05_06_non_finite_magnitude_is_unconstructable[SPG-05-nan_magnitude-NaN]" time="0.001" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_spg_05_06_non_finite_magnitude_is_unconstructable[SPG-06-infinity_magnitude-Infinity]" time="0.000" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_spg_08_precision_rounding_boundary_and_boundary_equality" time="0.002" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_spg_09_over_envelope_value_is_rejected" time="0.001" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_spg_10_undeclared_dimension_is_zero_authority" time="0.001" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_spg_11_omitted_mandatory_dimension_cannot_pass_vacuously" time="0.001" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_spg_14_vector_dimension_set_identity_mismatch" time="0.001" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_spg_15_none_magnitude_is_not_unbounded" time="0.001" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_spg_13_cross_field_violation_fails_closed" time="0.000" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_an_unreadable_boundary_token_is_never_a_permission[inclusive]" time="0.000" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_an_unreadable_boundary_token_is_never_a_permission[Inclusive]" time="0.000" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_an_unreadable_boundary_token_is_never_a_permission[INCLUSIVE ]" time="0.000" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_an_unreadable_boundary_token_is_never_a_permission[ INCLUSIVE]" time="0.000" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_an_unreadable_boundary_token_is_never_a_permission[]" time="0.000" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_an_unreadable_boundary_token_is_never_a_permission[OPEN]" time="0.000" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_an_unreadable_boundary_token_is_never_a_permission[EXCLUSIV]" time="0.000" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_recognized_boundary_tokens_are_exactly_two" time="0.000" /><testcase classname="tests.spg.test_spg_l2_fault" name="test_envelope_expansion_seam_is_boundary_aware" time="0.000" /><testcase classname="tests.test_digest_binding" name="test_frozen_model_pins_allow_inf_nan_explicitly" time="0.000" /></testsuite></testsuites>
```

---- FILE tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/manifest.yaml ----
```
schema: tos-evidence/manifest/v2
run_id: 20260806T015631Z-12dd4077
evidence_id: SPG-EV-002
primary_adr: ADR-002-014
design_document: docs/plans/2026-07-29-tos-ev-l2-pilot-design.md
evidence_level_stage: EV-L2
discipline_tag: EV-L2 stage execution record only; not a row PASS; L1 hardening prereq + coverage argument
  + P0-1 + independent review remain as stated in claim/coverage_argument blocks.
claim:
  closes_evidence_item: false
  register_status_moved_by_this_run: false
  register_status_at_run_time: PASS
  minimum_evidence_level: EV-L1/2
  independent_review: NOT_SIGNED (VER §9.5)
  p0_1_bounds_approval: OPEN
  verification_profile_version: 2.1 (PROPOSED — P0-1 open)
  target_integrity: STABLE_DURING_RUN
  mutated_during_run: []
  note: This document records that named tests executed at the recorded baseline. It asserts no acceptance,
    no PASS, and no coverage of the higher stages the row's minimum level names.
  ev_l2_stage_gates_unmet: []
  stages_executed:
  - EV-L1
  - EV-L2
  stages_executed_note: EV-L1 is executed as its own run package and bound here by prior_stage_runs; this
    package is the EV-L2 stage.
  covered_axis: 'SPG: semantic-validation component (post-hardening). The Expected referent (VER:1549
    "rejected deterministically before activation") is the validator verdict itself, which exists in full
    at the model layer, so there is no durable entanglement. The d4160fd0 generation of these stages completed
    coverage argument and the VER §9.5 signature chain (row PASS 2026-07-30); this re-run refreshes both
    stages at the current baseline for staged-claim continuity (design §6.2 M9). Independent review of
    THIS run''s package remains open.'
prior_stage_runs:
- evidence_id: SPG-EV-002
  run_id: 20260806T015630Z-12dd4077
  stage: EV-L1
  sha256sums_digest: db730541d4430e6b04307d81fbc1c6863ebe47b1c3e0519ffeace0bc35941c18
  artifacts_reverified:
  - baseline.yaml
  - junit.xml
  - manifest.yaml
  - run.log
  - traceability.csv
  baseline_commit_sha: 12dd40778b0237ea6992a3b0a9ecadb10f865f0f
  baseline_matches_this_run: true
  outcome: ALL_SELECTED_TESTS_GREEN
  reconcile_note: L1 stage executed at THIS baseline (design §6.2 M9), with every traceability file:line
    citation re-measured against the executed source (cited surfaces unchanged since d4160fd0; spot-verified).
supersedes_run_id: []
supersedes_note: Superseded packages are retained unmodified (VER §2.2); this field is the forward pointer,
  not a deletion record.
fault_injection:
  catalog_ref: docs/plans/2026-07-29-tos-ev-l2-pilot-design.md#4
  seed: 0
  seed_pinned: true
  schedule_artifact: fault-timeline.jsonl
  fault_count: 12
  expected_fault_count: 12
  fault_count_matches_catalog: true
  fault_ids:
  - SPG-01
  - SPG-02
  - SPG-03
  - SPG-05
  - SPG-06
  - SPG-08
  - SPG-09
  - SPG-10
  - SPG-11
  - SPG-14
  - SPG-15
  - SPG-13
  duplicate_fault_ids: []
  foreign_evidence_id_rows: []
  deviation_faults: []
  misreported_outcome_faults: []
  expected_undefined_faults: []
  unobserved_disposition_faults: []
  all_faults_met: true
  all_faults_met_basis: every row's outcome RE-DERIVED from observed vs expected (the row's own outcome
    field is cross-checked, never trusted); withheld on an empty schedule (0 injected != 0 violations),
    any deviation or misreport, any undefined Expected or unobserved disposition, a duplicated fault id,
    a row from another evidence id, or a recount that disagrees with the catalog size
  l1_hardening_prereq_met: true
  l1_hardening_prereq:
    met: true
    measured_from: structural analysis of the executed source's syntax tree; comments and docstrings cannot
      satisfy any check (the harness never imports tos)
    items:
    - hardening: H-1 allow_inf_nan=False pinned on FrozenModel.model_config
      path: tos/src/tos/canonical/_base.py
      sha256: ca560b2987e078f9afc867c335f35915dfcb5c1065f00073c27bfef613f45dfb
      met: true
      measured:
        bound_keywords:
        - allow_inf_nan
        - extra
        - frozen
        allow_inf_nan: 'False'
    - hardening: H-2 precision/rounding/boundary comparability + boundary-aware comparison
      path: tos/src/tos/spg/predicates.py
      sha256: 0e135bee214bdbe55654e40586d0693d5b44d9dffbc56f7abaad8531e041327e
      met: true
      measured:
        unit_metadata_keys:
        - unit
        - multiplier
        - sign
        - precision
        - rounding
        - boundary
        missing_metadata_keys: []
        boundary_comparison_defined: true
    - hardening: H-4 canonicalization scheme lookup wrapped as ArtifactIntegrityError
      path: tos/src/tos/canonical/canonicalization.py
      sha256: 18d855970b3ae0eebc6b7b6db6b5e7d93cf52179360d7986883792ab2057bfe3
      met: true
      measured:
        get_scheme_raises:
        - ArtifactIntegrityError
        module_raises:
        - ArtifactIntegrityError
        - TypeError
coverage_argument:
  specification: tos-spec/src/part-1-foundation/VER-002-001-Safety-Critical-Architecture-Verification-Evidence-Specification.md
    §2.7 (line 76-78) — a finite set of executed evidence cases does not by itself discharge a universally-quantified
    safety claim. Both this row's Expected clauses are universally quantified, so the coverage argument
    is mandatory.
  boundary_values: per-dimension boundary combinations exercised (seed-fixed)
  adverse_scenario_set: ADR-002-021 PROPOSED (unapproved) — adversarial-combination leg UNMET; applicability
    to non-risk row = OQ; residual per §378
  unexercised_residual_ref:
  - SPG-07 overflow / underflow — bound-dependent Expected. Decimal is arbitrary-precision so no float
    overflow exists; "exceeds the safe range" depends on Verification Profile bounds (profile-level APPROVED
    scope-limited 2026-07-29; the overflow bound keys are not consumed by this run), so the Expected remains
    un-instantiated here (design §0.5-4 / §4).
  - SPG-04 currency — GovernedDimensionLimit carries no independent currency field (only unit), so currency
    cannot be mutated independently of unit at this model layer (design §4).
  - SPG-12 duplicate / unknown / extension FIELD bypass — ADR-002-014 §11 step 12 (line 313); this is
    the SPG-EV-003 axis (EV-L1/2+Security, VER:1553/1555), not SPG-EV-002. Not claimed here.
  unexercised_residual_note: 'The §378 Residual Risk Register INSTANCE is absent (measured: verification/
    holds only RESIDUAL-RISK-ACCEPTANCE-RECORD-template.yaml; tos-evidence/ holds zero residual artifacts)
    — creating it is prerequisite work. Each entry SHALL carry all twelve VER:3293-3306 fields (risk identity;
    affected requirement/ADR; scope; credible failure sequence; maximum economic effect; existing controls;
    detection/containment bound; owner; approver; expiration/review date; required scope reduction; evidence
    references), and owner/approver come through the P0-3 role system (D1). The refs above are pointers,
    not a union: separate residual risks SHALL NOT be unioned at a consumer (VER:3308) — each is registered
    independently.'
  discharged: false
  discharged_note: The adversarial-combination leg cannot be discharged while ADR-002-021 is PROPOSED,
    and an unresolved applicability question defaults to APPLICABLE (VER §2.4 line 64-66; VER:173 'Missing
    resolution is a blocker and SHALL NOT default to the lowest level'). This run therefore records the
    argument's state; it does not claim to have made it.
execution:
  command:
  - /Users/harris/Development/private/kis_unified_sts/.venv/bin/python
  - -m
  - pytest
  - tos/tests/spg/test_spg_l2_fault.py
  - tos/tests/test_digest_binding.py::test_frozen_model_pins_allow_inf_nan_explicitly
  - -q
  - --junitxml=/Users/harris/Development/private/kis_unified_sts/tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/junit.xml
  - --hypothesis-seed=0
  - --l2-fault-timeline=/Users/harris/Development/private/kis_unified_sts/tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/fault-timeline.jsonl
  cwd: /Users/harris/Development/private/kis_unified_sts
  env_overrides:
    PYTHONPATH: tos/src
    PYTHONHASHSEED: '0'
  started_utc: '2026-08-06T01:56:31.433630+00:00'
  finished_utc: '2026-08-06T01:56:31.793061+00:00'
  monotonic_duration_s: 0.359419
  return_code: 0
  outcome: ALL_SELECTED_TESTS_GREEN
  junit_summary:
    tests: 35
    failures: 0
    errors: 0
    skipped: 0
    time_s: '0.114'
  stage_gate_outcome: EV_L2_STAGE_GATES_MET
test_nodes:
- tos/tests/spg/test_spg_l2_fault.py
- tos/tests/test_digest_binding.py::test_frozen_model_pins_allow_inf_nan_explicitly
baseline:
  file: baseline.yaml
  sha256: 532700a22921c349169c5d86c61e659c8b34e32b8efd1f7a31fa8bf79e84e4d9
  completeness: NOT complete (VER §3 line 109 has no 'as applicable' clause). VER §3 fields without an
    existing artifact are NOT_APPLICABLE_PURE_MODEL_L2; the unmet set is enumerated in baseline.yaml::ver_002_001_section_3_unmet_fields.
  ver3_unmet_field_count: 16
artifacts:
- name: baseline.yaml
  sha256: 532700a22921c349169c5d86c61e659c8b34e32b8efd1f7a31fa8bf79e84e4d9
  bytes: 28009
- name: fault-timeline.jsonl
  sha256: 7a568574e2ec4f4fc2d1b56f8f1ac6684a7905df0f719a0a97151cc27b50dc37
  bytes: 6896
- name: junit.xml
  sha256: e0c2b9ed3452e23807a31c3d0de682e0bd8d1832bbdf93c64fdf07722f765c6d
  bytes: 4932
- name: run.log
  sha256: 6ac7228b64013f7f47c9f39e1c004ab5d545a74dc127762e964d359ad29b83e9
  bytes: 653
- name: traceability.csv
  sha256: 9d0b40a32ed937a29ce268ba90b823b465241fd93faabd010111cf373726d373
  bytes: 1652
artifact_closure_note: manifest.yaml cannot contain its own digest; sha256sums.txt is written last and
  closes over every retained file including this manifest (VER §9.2).

```

---- FILE tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/run.log ----
```
$ PYTHONPATH=tos/src PYTHONHASHSEED=0 /Users/harris/Development/private/kis_unified_sts/.venv/bin/python -m pytest tos/tests/spg/test_spg_l2_fault.py tos/tests/test_digest_binding.py::test_frozen_model_pins_allow_inf_nan_explicitly -q --junitxml=/Users/harris/Development/private/kis_unified_sts/tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/junit.xml --hypothesis-seed=0 --l2-fault-timeline=/Users/harris/Development/private/kis_unified_sts/tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/fault-timeline.jsonl

--- stdout ---
...................................                                      [100%]

--- stderr ---

--- return code: 0 ---

```

---- FILE tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/sha256sums.txt ----
```
532700a22921c349169c5d86c61e659c8b34e32b8efd1f7a31fa8bf79e84e4d9  baseline.yaml
7a568574e2ec4f4fc2d1b56f8f1ac6684a7905df0f719a0a97151cc27b50dc37  fault-timeline.jsonl
e0c2b9ed3452e23807a31c3d0de682e0bd8d1832bbdf93c64fdf07722f765c6d  junit.xml
ce386e9c1ca47626a4b51cd3fd403f052187cdca69d6bb7d53cf4c8b69889be2  manifest.yaml
6ac7228b64013f7f47c9f39e1c004ab5d545a74dc127762e964d359ad29b83e9  run.log
9d0b40a32ed937a29ce268ba90b823b465241fd93faabd010111cf373726d373  traceability.csv

```

---- FILE tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/traceability.csv ----
```
evidence_id,primary_adr,design_document,test_node,mapping_basis,evidence_claim
SPG-EV-002,ADR-002-014,docs/plans/2026-07-29-tos-ev-l2-pilot-design.md,tos/tests/spg/test_spg_l2_fault.py,"EV-L2 pilot design §4 (2026-07-29-tos-ev-l2-pilot-design.md:188) fault catalog — 12 faults SPG-01/02/03/05/06/08/09/10/11/13/14/15, enumerated at test_spg_l2_fault.py:128 and guard-anchored at :93; module-wide @pytest.mark.l2_fault at :73. Each test injects a single semantic mutation into an otherwise-valid Safety Configuration Bundle and inspects the Safety Profile Validator's own SemanticValidationResult verdict (VER-002-001 §5 lines 146-148; Injection VER:1548, Expected VER:1549). SPG-05/06 depend on design §5 H-1 and SPG-08 on §5 H-2 (the measured fail-open seal), §5 at 2026-07-29-tos-ev-l2-pilot-design.md:233. All file:line citations re-measured at baseline eb92ea46.",STAGE_RECORD_ONLY (does not close the evidence item)
SPG-EV-002,ADR-002-014,docs/plans/2026-07-29-tos-ev-l2-pilot-design.md,tos/tests/test_digest_binding.py::test_frozen_model_pins_allow_inf_nan_explicitly,"EV-L2 pilot design §5 H-1 ownership seal (2026-07-29-tos-ev-l2-pilot-design.md:233), executed IN-BAND with the SPG-EV-002 fault schedule because SPG-05/06 depend on it: their Expected (""a non-finite magnitude is unconstructable"") holds today under pydantic's own default, so a run that did not also execute this node could not distinguish ""tos pins allow_inf_nan=False"" from ""the third-party default happens to agree"". Records no fault-timeline row (it is not @pytest.mark.l2_fault), so fault_count stays 12.",STAGE_RECORD_ONLY (does not close the evidence item)

```


============================================================================
# PACKAGE tos-evidence/STATE-EV-004/20260806T015632Z-12dd4077
============================================================================

---- FILE tos-evidence/STATE-EV-004/20260806T015632Z-12dd4077/baseline.yaml ----
```
schema: tos-evidence/baseline/v3
run_id: 20260806T015632Z-12dd4077
evidence_id: STATE-EV-004
evidence_level_stage: EV-L3
generated_utc: '2026-08-06T01:56:35.230648+00:00'
contract:
  run_manifest_contract: docs/plans/2026-07-20-tos-boundary-and-import-firewall-design.md §5.1 (seven
    items)
  ver_specification: tos-spec/src/part-1-foundation/VER-002-001-Safety-Critical-Architecture-Verification-Evidence-Specification.md
    §2.3/§3/§8/§9.1/§9.2/§9.5
  completeness: EV-L3 integrated crash/restart. VER §3 requires 22 baseline fields and states that 'A
    run without a complete baseline is invalid' (line 109) — a clause carrying no 'as applicable' qualifier,
    unlike §7 line 258, so it stands beside P0-1 and the independent signature as a gate, not a waivable
    formality. The unmet-field list and every reason are retained with the stage attribution updated (NOT_APPLICABLE_EV_L1
    -> NOT_APPLICABLE_MODELED_TRANSPORT_L3); the enumerated list is ver_002_001_section_3_unmet_fields
    below. This stage DOES bring a real local persistence substrate and a real OS process boundary into
    existence; what remains absent is the transport and everything hanging off it — the broker, authority/human,
    network and recovery instances — because the send boundary is a MODELLED marker emitting zero real
    bytes and zero real orders (residuals R-N / R-I). Under VER §3's full standard this baseline is NOT
    complete.
evidence_register_row:
  source: tos-spec/src/part-1-foundation/verification/EVIDENCE-REGISTER-002.csv
  evidence_id: STATE-EV-004
  domain: Orthogonal State
  title: Conservative Restart Reconstruction
  primary_adr: ADR-002-005
  criticality: Critical
  minimum_evidence_level: EV-L3
  status_at_run_time: NOT_IMPLEMENTED
  implementation_owner: ai-impl(claude-orchestrated)
  evidence_owner: operator
  independent_reviewer: ai-review(decorrelated)+operator-countersign
design1_5_1:
  item_1_repository_and_package:
    git_commit_sha: 12dd40778b0237ea6992a3b0a9ecadb10f865f0f
    git_short_sha: 12dd4077
    tos_package_version: 0.0.1
    worktree:
      clean: false
      untracked:
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/baseline.yaml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/junit.xml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/manifest.yaml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/sha256sums.txt
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/traceability.csv
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/baseline.yaml
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/fault-timeline.jsonl
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/junit.xml
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/manifest.yaml
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/sha256sums.txt
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/traceability.csv
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/baseline.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/junit.xml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/manifest.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/sha256sums.txt
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/traceability.csv
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/baseline.yaml
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/fault-timeline.jsonl
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/junit.xml
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/manifest.yaml
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/sha256sums.txt
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/traceability.csv
      modified_unstaged: []
      staged: []
      all_dirty_paths:
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/baseline.yaml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/junit.xml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/manifest.yaml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/sha256sums.txt
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/traceability.csv
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/baseline.yaml
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/fault-timeline.jsonl
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/junit.xml
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/manifest.yaml
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/sha256sums.txt
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/traceability.csv
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/baseline.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/junit.xml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/manifest.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/sha256sums.txt
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/traceability.csv
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/baseline.yaml
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/fault-timeline.jsonl
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/junit.xml
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/manifest.yaml
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/sha256sums.txt
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/traceability.csv
      note: 'A non-empty list does not by itself invalidate the run: the executed files are pinned individually
        by target_file_digests below. Paths outside the executed set belong to other work in the same
        worktree.'
    worktree_after_run:
      clean: false
      untracked:
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/baseline.yaml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/junit.xml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/manifest.yaml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/sha256sums.txt
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/traceability.csv
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/baseline.yaml
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/fault-timeline.jsonl
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/junit.xml
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/manifest.yaml
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/sha256sums.txt
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/traceability.csv
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/baseline.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/junit.xml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/manifest.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/sha256sums.txt
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/traceability.csv
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/baseline.yaml
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/fault-timeline.jsonl
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/junit.xml
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/manifest.yaml
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/sha256sums.txt
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/traceability.csv
      - tos-evidence/STATE-EV-004/20260806T015632Z-12dd4077/crash-timeline.jsonl
      - tos-evidence/STATE-EV-004/20260806T015632Z-12dd4077/junit.xml
      modified_unstaged: []
      staged: []
      all_dirty_paths:
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/baseline.yaml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/junit.xml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/manifest.yaml
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/sha256sums.txt
      - tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/traceability.csv
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/baseline.yaml
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/fault-timeline.jsonl
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/junit.xml
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/manifest.yaml
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/sha256sums.txt
      - tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/traceability.csv
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/baseline.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/junit.xml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/manifest.yaml
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/sha256sums.txt
      - tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/traceability.csv
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/baseline.yaml
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/fault-timeline.jsonl
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/junit.xml
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/manifest.yaml
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/sha256sums.txt
      - tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/traceability.csv
      - tos-evidence/STATE-EV-004/20260806T015632Z-12dd4077/crash-timeline.jsonl
      - tos-evidence/STATE-EV-004/20260806T015632Z-12dd4077/junit.xml
      note: 'A non-empty list does not by itself invalidate the run: the executed files are pinned individually
        by target_file_digests below. Paths outside the executed set belong to other work in the same
        worktree.'
    worktree_delta:
      became_dirty_during_run:
      - tos-evidence/STATE-EV-004/20260806T015632Z-12dd4077/crash-timeline.jsonl
      - tos-evidence/STATE-EV-004/20260806T015632Z-12dd4077/junit.xml
      became_clean_during_run: []
      stable: false
    target_files_clean: true
    target_files_stable_during_run: true
    target_file_digests:
    - path: tests/tos_l3/conftest.py
      sha256_before_run: dd7202231254c1f2eb5ac34d3bfb7307a5741d20972fd0e23cd1a100069963ad
      sha256_after_run: dd7202231254c1f2eb5ac34d3bfb7307a5741d20972fd0e23cd1a100069963ad
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tests/tos_l3/test_state_ev_004_crash_restart.py
      sha256_before_run: 84c940ea7770fed86b4341ccc2d629f107d495a858145db859547c91ca113c59
      sha256_after_run: 84c940ea7770fed86b4341ccc2d629f107d495a858145db859547c91ca113c59
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tools/tos_evidence_run.py
      sha256_before_run: 562c52eebc1758ccf804b55c2eb03a1887a07014433d649ec0e01a7a143fb0aa
      sha256_after_run: 562c52eebc1758ccf804b55c2eb03a1887a07014433d649ec0e01a7a143fb0aa
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: false
    - path: tos/src/tos/orthostate/__init__.py
      sha256_before_run: c866fc0fd8dc7bb0961f7550e2d9e73d1dfc4819afbc341c1f23fe4e0b11f632
      sha256_after_run: c866fc0fd8dc7bb0961f7550e2d9e73d1dfc4819afbc341c1f23fe4e0b11f632
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/orthostate/_base.py
      sha256_before_run: 2c1b8bb6c73ee8f73697ecc5e33d149a80efd7fdf27550b2f148248a2b34a40e
      sha256_after_run: 2c1b8bb6c73ee8f73697ecc5e33d149a80efd7fdf27550b2f148248a2b34a40e
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/orthostate/predicates.py
      sha256_before_run: 7265e75af582048fba54d757e5344a9d467348738a37dec7898df4c30db897c0
      sha256_after_run: 7265e75af582048fba54d757e5344a9d467348738a37dec7898df4c30db897c0
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/orthostate/records.py
      sha256_before_run: 8dabc903e03d039fb5292d5094a7d87cb46f073965a163c12eb1c3f167285cd2
      sha256_after_run: 8dabc903e03d039fb5292d5094a7d87cb46f073965a163c12eb1c3f167285cd2
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/orthostate/state.py
      sha256_before_run: aa68710f84ab21ba93d68d132a607ecb8f139f1acabde6e515712dc9599de0b3
      sha256_after_run: aa68710f84ab21ba93d68d132a607ecb8f139f1acabde6e515712dc9599de0b3
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/orthostate/vocabulary.py
      sha256_before_run: 67dda3c7eed990f3150273fcf6f00e7ad8bca5bcf5fb101d37573f289fcc37d4
      sha256_after_run: 67dda3c7eed990f3150273fcf6f00e7ad8bca5bcf5fb101d37573f289fcc37d4
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/staterestore/__init__.py
      sha256_before_run: 138fd3eeff890ee44822925d76e81a9a270dc00a72b6a04af4b39d05b3990b8e
      sha256_after_run: 138fd3eeff890ee44822925d76e81a9a270dc00a72b6a04af4b39d05b3990b8e
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/staterestore/_l3_worker.py
      sha256_before_run: 3adeaa2c7e4ebc3a988e453201fc283d18f4b65cfb881ddb515ed91d470870b3
      sha256_after_run: 3adeaa2c7e4ebc3a988e453201fc283d18f4b65cfb881ddb515ed91d470870b3
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/staterestore/reload.py
      sha256_before_run: e9f65fcf3ae781ebab13958f47a7337f5c30cba5bfd4891161fc61eadcd5f75b
      sha256_after_run: e9f65fcf3ae781ebab13958f47a7337f5c30cba5bfd4891161fc61eadcd5f75b
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
    - path: tos/src/tos/staterestore/store.py
      sha256_before_run: c4e70f4692d9a4e7b418c1af61ae03827122cc6ee76a1f89de00d84cf3ef4e3f
      sha256_after_run: c4e70f4692d9a4e7b418c1af61ae03827122cc6ee76a1f89de00d84cf3ef4e3f
      status: STABLE_DURING_RUN
      git_clean: true
      cleanliness_guarded: true
  item_2_interpreter_and_dependencies:
    python:
      version: 3.12.2
      version_full: 3.12.2 (main, Dec 11 2025, 16:36:08) [Clang 17.0.0 (clang-1700.4.4.1)]
      implementation: CPython
      executable: /Users/harris/Development/private/kis_unified_sts/.venv/bin/python
    installed_versions_measured:
      pydantic: 2.12.5
      hypothesis: 6.151.5
      pytest: 9.0.2
      numpy: 1.26.4
      pandas: 2.3.3
      pyyaml: 6.0.3
      tos: NOT_INSTALLED
    pinned_in_tos_pyproject:
      pydantic: 2.12.5
      numpy: 2.4.0
      pandas: 2.3.3
      pyyaml: 6.0.3
      pytest: 9.0.2
      hypothesis: 6.150.2
    pins_satisfied: false
    pin_vs_installed_drift:
    - distribution: hypothesis
      pinned: 6.150.2
      installed: 6.151.5
    - distribution: numpy
      pinned: 2.4.0
      installed: 1.26.4
    drift_note: 'pins_satisfied is the machine-readable claim; an empty drift list = the executed interpreter
      matches every pin. A non-empty list is recorded, not resolved: the installed version is what executed.'
  item_3_execution_environment: &id001
    os: Darwin
    os_release: 25.5.0
    machine: arm64
    platform: macOS-26.5.2-arm64-arm-64bit
    python_implementation: CPython
  item_4_harness_version: &id002
    harness_path: tools/tos_evidence_run.py
    harness_sha256: 562c52eebc1758ccf804b55c2eb03a1887a07014433d649ec0e01a7a143fb0aa
    harness_tracked: true
    harness_at_commit: aac2827bb5941603705da735ea079129ce3d942a
    harness_dirty: false
    pytest_version: 9.0.2
    note: 'design #1 §5.1 item 4 — Phase 1 harness version = git digest, which exists only once the harness
      is committed. Until then harness_at_commit is NOT_IN_COMMIT and harness_sha256 is the only identity
      of the code that ran.'
  item_5_seed_policy: &id003
    policy: fixed
    pytest_flags:
    - --hypothesis-seed=0
    hypothesis_seed: 0
    note: 'VER §9.1 append-only: seed pinned before the run began.'
  item_6_consumed_configuration_artifacts:
    status: NOT_APPLICABLE_MODELED_TRANSPORT_L3
    reason: 'No configuration artifact is consumed: bounds are hypothesis-injected generated values, not
      read from a profile, and the run is hermetic (no .env, no YAML).'
  item_7_retained_artifact_digests: Enumerated in manifest.yaml (artifacts) and closed over by sha256sums.txt,
    which is written last and covers every retained file including the manifest.
ver_002_001_section_3_baseline:
  repository_commit_sha:
    status: RECORDED
    value: 12dd40778b0237ea6992a3b0a9ecadb10f865f0f
  build_artifact_digest:
    status: NOT_APPLICABLE_MODELED_TRANSPORT_L3
    reason: 'Phase 1 executes from the source tree; no built distribution artifact is produced or consumed
      (design #1 §5.1 items 1/4 — the git digest stands in). The executed bytes are pinned individually
      by design1_5_1.item_1_repository_and_package.target_file_digests.'
  rfc_adr_versions:
    status: RECORDED
    value:
    - role: primary_adr
      path: tos-spec/src/part-1-foundation/ADR-002-005-Intent-Transmission-Attempt-Broker-Order-and-Knowledge-State-Model.md
      sha256: 025c02cf8638f6aed84faf22f724c47bbc0af390d3d189fa25ef065a8cd73d51
    - role: design_document
      path: docs/plans/2026-08-06-tos-ev-l3-pilot-design.md
      sha256: 64ec27c15f94fa7ea16252c2f383ce3725e11523a5a45bb6f08fe88a2e11b4c8
    - role: ver_specification
      path: tos-spec/src/part-1-foundation/VER-002-001-Safety-Critical-Architecture-Verification-Evidence-Specification.md
      sha256: 217a43ab1b32e04fe6515316a7383c3e9e75bb177ed18c7c7e7267ca0a3c2a38
    - role: boundary_design_1
      path: docs/plans/2026-07-20-tos-boundary-and-import-firewall-design.md
      sha256: 2449f18d6088e21f601da623d27e6eff74066661f5d92116db2eda1a59b5a988
    reason: The corpus documents carry no separate version field; their content sha256 is the version
      identity.
  hard_safety_envelope_version:
    status: NOT_APPLICABLE_MODELED_TRANSPORT_L3
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L3 crash/restart run on a real local persistence substrate and a real process boundary consumes
      none — its send boundary is a MODELLED marker (zero real bytes, zero real orders), so no broker,
      authority/human, network or recovery instance is brought into existence. Recorded N/A per design
      #1 §5.1 read forward to EV-L3 (EV-L3 pilot design §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  runtime_safety_profile_version:
    status: NOT_APPLICABLE_MODELED_TRANSPORT_L3
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L3 crash/restart run on a real local persistence substrate and a real process boundary consumes
      none — its send boundary is a MODELLED marker (zero real bytes, zero real orders), so no broker,
      authority/human, network or recovery instance is brought into existence. Recorded N/A per design
      #1 §5.1 read forward to EV-L3 (EV-L3 pilot design §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  human_authority_policy_generation_and_digest:
    status: NOT_APPLICABLE_MODELED_TRANSPORT_L3
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L3 crash/restart run on a real local persistence substrate and a real process boundary consumes
      none — its send boundary is a MODELLED marker (zero real bytes, zero real orders), so no broker,
      authority/human, network or recovery instance is brought into existence. Recorded N/A per design
      #1 §5.1 read forward to EV-L3 (EV-L3 pilot design §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  effective_principal_graph_generation_and_digest:
    status: NOT_APPLICABLE_MODELED_TRANSPORT_L3
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L3 crash/restart run on a real local persistence substrate and a real process boundary consumes
      none — its send boundary is a MODELLED marker (zero real bytes, zero real orders), so no broker,
      authority/human, network or recovery instance is brought into existence. Recorded N/A per design
      #1 §5.1 read forward to EV-L3 (EV-L3 pilot design §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  evidence_integrity_policy_generation_and_digest:
    status: NOT_APPLICABLE_MODELED_TRANSPORT_L3
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L3 crash/restart run on a real local persistence substrate and a real process boundary consumes
      none — its send boundary is a MODELLED marker (zero real bytes, zero real orders), so no broker,
      authority/human, network or recovery instance is brought into existence. Recorded N/A per design
      #1 §5.1 read forward to EV-L3 (EV-L3 pilot design §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  recovery_barrier_policy_generation_and_digest:
    status: NOT_APPLICABLE_MODELED_TRANSPORT_L3
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L3 crash/restart run on a real local persistence substrate and a real process boundary consumes
      none — its send boundary is a MODELLED marker (zero real bytes, zero real orders), so no broker,
      authority/human, network or recovery instance is brought into existence. Recorded N/A per design
      #1 §5.1 read forward to EV-L3 (EV-L3 pilot design §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  critical_input_policy_generation_and_digest:
    status: NOT_APPLICABLE_MODELED_TRANSPORT_L3
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L3 crash/restart run on a real local persistence substrate and a real process boundary consumes
      none — its send boundary is a MODELLED marker (zero real bytes, zero real orders), so no broker,
      authority/human, network or recovery instance is brought into existence. Recorded N/A per design
      #1 §5.1 read forward to EV-L3 (EV-L3 pilot design §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  venue_constraint_policy_generation_and_digest:
    status: NOT_APPLICABLE_MODELED_TRANSPORT_L3
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L3 crash/restart run on a real local persistence substrate and a real process boundary consumes
      none — its send boundary is a MODELLED marker (zero real bytes, zero real orders), so no broker,
      authority/human, network or recovery instance is brought into existence. Recorded N/A per design
      #1 §5.1 read forward to EV-L3 (EV-L3 pilot design §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  trading_approval_policy_generation_and_digest:
    status: NOT_APPLICABLE_MODELED_TRANSPORT_L3
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L3 crash/restart run on a real local persistence substrate and a real process boundary consumes
      none — its send boundary is a MODELLED marker (zero real bytes, zero real orders), so no broker,
      authority/human, network or recovery instance is brought into existence. Recorded N/A per design
      #1 §5.1 read forward to EV-L3 (EV-L3 pilot design §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  currentness_policy_generation_and_digest:
    status: NOT_APPLICABLE_MODELED_TRANSPORT_L3
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L3 crash/restart run on a real local persistence substrate and a real process boundary consumes
      none — its send boundary is a MODELLED marker (zero real bytes, zero real orders), so no broker,
      authority/human, network or recovery instance is brought into existence. Recorded N/A per design
      #1 §5.1 read forward to EV-L3 (EV-L3 pilot design §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  restricted_live_trial_policy_generation_and_digest:
    status: NOT_APPLICABLE_MODELED_TRANSPORT_L3
    reason: 'No instance artifact exists in the corpus (template only under tos-spec/src/part-1-foundation/verification/);
      an EV-L3 crash/restart run on a real local persistence substrate and a real process boundary consumes
      none — its send boundary is a MODELLED marker (zero real bytes, zero real orders), so no broker,
      authority/human, network or recovery instance is brought into existence. Recorded N/A per design
      #1 §5.1 read forward to EV-L3 (EV-L3 pilot design §6.3): the field, its N/A status and its reason
      are retained, only the stage attribution changes.'
  broker_capability_profile_version:
    status: NOT_APPLICABLE_MODELED_TRANSPORT_L3
    reason: Evidence Register broker_capability_profile_version for this row = 'TBD'; the row's minimum
      evidence level (EV-L3) carries no +Broker suffix and no Broker Capability Profile instance exists
      (template only). P0-2 is not in this run's scope.
  verification_profile_version:
    status: RECORDED
    value:
      version: 2.1 (PROPOSED — P0-1 open)
      register_column_value: 2.1-PROPOSED
      artifact:
        path: tos-spec/src/part-1-foundation/verification/VERIFICATION-PROFILE-002.yaml
        sha256: d837c7e74b0fbe70d7cf2dfb30e412a29042577a0a38dcba22c649dd457d5064
      approval_state: PROPOSED — P0-1 (bounds approval) OPEN
    reason: Recorded, not approved. VER §6 numeric bounds remain unapproved; no bound value is consumed
      by this run (bounds are hypothesis-injected, not hardcoded).
  database_schema_migration_version:
    status: NOT_APPLICABLE_MODELED_TRANSPORT_L3
    reason: 'The EV-L3 pilot exercises a real local persistence substrate (stdlib sqlite3, WAL, synchronous=FULL)
      whose schema is a single fixed table created on open: there is no migration history and no versioned
      schema artifact to record. This substrate is a PILOT-SCOPE choice, NOT the ADR-002-005 §4 line 61
      project persistence-technology decision, which remains open.'
  deployment_manifest_digest:
    status: NOT_APPLICABLE_MODELED_TRANSPORT_L3
    reason: 'Nothing is deployed: the kernel is non-transmitting and is executed in-process by pytest.'
  workload_identities_and_key_versions:
    status: NOT_APPLICABLE_MODELED_TRANSPORT_L3
    reason: No workload identity, credential, or key material is used — the run is hermetic (no network,
      no .env, no clock authority).
  environment_identifier:
    status: RECORDED
    value: *id001
  test_harness_version:
    status: RECORDED
    value: *id002
  fault_injection_schedule_and_seed:
    status: RECORDED
    value:
      fault_schedule:
        catalog_ref: docs/plans/2026-08-06-tos-ev-l3-pilot-design.md#4
        seed: 0
        seed_pinned: true
        schedule_artifact: crash-timeline.jsonl
        crash_scenario_count: 8
        expected_crash_scenario_count: 8
        crash_scenario_count_matches_catalog: true
        scenario_ids:
        - L3-01
        - L3-02
        - L3-03
        - L3-04
        - L3-05
        - L3-06
        - L3-07
        - L3-08
        duplicate_scenario_ids: []
        foreign_evidence_id_rows: []
        deviation_scenarios: []
        misreported_outcome_scenarios: []
        expected_undefined_scenarios: []
        unobserved_reconstruction_scenarios: []
        shared_process_scenarios: []
        non_durable_store_scenarios: []
        crash_points:
        - AFTER_COMPLETE_DURABLE_COMMIT
        - AFTER_DURABLE_SEND_STARTED_BEFORE_BROKER
        - AFTER_MODELLED_NETWORK_TRANSMISSION
        - AFTER_STALE_OPTIMISTIC_CACHE
        - AFTER_TERMINAL_FILL_WITH_POSITIVE_KNOWLEDGE
        - AT_NON_TERMINAL_BROKER_ORDER_BOUNDARY
        - BEFORE_EVIDENCE_PERSISTENCE
        - BETWEEN_DIMENSION_TRANSACTIONS_INCOMPLETE_STORE
        process_boundary_real: true
        persistence_real_measured: true
        all_crash_scenarios_met: true
        all_crash_scenarios_met_basis: every row's outcome RE-DERIVED from observed vs expected reconstruction
          plus the row's own structural boundary measurements (the row's outcome field is cross-checked,
          never trusted); withheld on an empty schedule (0 injected != 0 violations), any deviation or
          misreport, any undefined Expected or unobserved reconstruction, a writer/reader pid that is
          not a real distinct pair, a store that was not a non-empty on-disk file, a duplicated scenario
          id, a row from another evidence id, or a recount that disagrees with the catalog size
        persistence_real: true
        persistence_substrate_check:
          met: true
          path: tos/src/tos/staterestore/store.py
          sha256: c4e70f4692d9a4e7b418c1af61ae03827122cc6ee76a1f89de00d84cf3ef4e3f
          measured_from: structural analysis of the executed source's syntax tree; pragmas are read out
            of real execute(...) arguments, so a docstring or comment mentioning one cannot satisfy the
            check; the harness never imports tos (TOS-FW-R)
          measured:
            connect_call_sites: 1
            literal_connection_targets: []
            in_memory_tokens_present: []
            executed_pragmas:
              journal_mode: WAL
              synchronous: FULL
            pragmas_present:
            - journal_mode=WAL
            - synchronous=FULL
            pragmas_missing: []
            pragmas_required:
            - journal_mode=WAL
            - synchronous=FULL
      seed: *id003
    reason: 'EV-L3: the VER §9.1 append-only crash schedule and the seed are both recorded. This field
      is no longer PARTIAL — it is the one VER §3 field the EV-L3 stage completes relative to EV-L1.'
ver_002_001_section_3_unmet_fields:
- broker_capability_profile_version
- build_artifact_digest
- critical_input_policy_generation_and_digest
- currentness_policy_generation_and_digest
- database_schema_migration_version
- deployment_manifest_digest
- effective_principal_graph_generation_and_digest
- evidence_integrity_policy_generation_and_digest
- hard_safety_envelope_version
- human_authority_policy_generation_and_digest
- recovery_barrier_policy_generation_and_digest
- restricted_live_trial_policy_generation_and_digest
- runtime_safety_profile_version
- trading_approval_policy_generation_and_digest
- venue_constraint_policy_generation_and_digest
- workload_identities_and_key_versions
ver_002_001_section_3_unmet_note: 'VER §3 line 109 (''A run without a complete baseline is invalid'')
  has no ''as applicable'' clause. This list names every field that is not RECORDED, so the gap is machine-checkable:
  an empty list would be the claim that the baseline is complete, and this run does not make that claim.'
test_nodes:
- tests/tos_l3/test_state_ev_004_crash_restart.py

```

---- FILE tos-evidence/STATE-EV-004/20260806T015632Z-12dd4077/crash-timeline.jsonl ----
```
{"scenario_id": "L3-01", "evidence_id": "STATE-EV-004", "target_component": "CompositeState + durable staterestore store + restart reload + reconstruct_conservative, across a real process boundary", "crash_point": "AFTER_DURABLE_SEND_STARTED_BEFORE_BROKER", "crash_exit_status": 137, "seed": 0, "writer_pid": 16911, "reader_pid": 16912, "store_real_on_disk": true, "store_bytes": 12288, "expected_reconstruction": "INTENT=ACTIVE|ATTEMPT=SEND_STARTED|BROKER=UNKNOWN|KNOWLEDGE=UNOBSERVED|CAPACITY=POTENTIALLY_LIVE", "observed_reconstruction": "INTENT=ACTIVE|ATTEMPT=SEND_STARTED|BROKER=UNKNOWN|KNOWLEDGE=UNOBSERVED|CAPACITY=POTENTIALLY_LIVE", "outcome": "MET"}
{"scenario_id": "L3-02", "evidence_id": "STATE-EV-004", "target_component": "CompositeState + durable staterestore store + restart reload + reconstruct_conservative, across a real process boundary", "crash_point": "AFTER_MODELLED_NETWORK_TRANSMISSION", "crash_exit_status": 137, "seed": 0, "writer_pid": 16913, "reader_pid": 16914, "store_real_on_disk": true, "store_bytes": 12288, "expected_reconstruction": "INTENT=ACTIVE|ATTEMPT=SENT_UNCONFIRMED|BROKER=UNKNOWN|KNOWLEDGE=UNOBSERVED|CAPACITY=POTENTIALLY_LIVE", "observed_reconstruction": "INTENT=ACTIVE|ATTEMPT=SENT_UNCONFIRMED|BROKER=UNKNOWN|KNOWLEDGE=UNOBSERVED|CAPACITY=POTENTIALLY_LIVE", "outcome": "MET"}
{"scenario_id": "L3-03", "evidence_id": "STATE-EV-004", "target_component": "CompositeState + durable staterestore store + restart reload + reconstruct_conservative, across a real process boundary", "crash_point": "BEFORE_EVIDENCE_PERSISTENCE", "crash_exit_status": 137, "seed": 0, "writer_pid": 16915, "reader_pid": 16916, "store_real_on_disk": true, "store_bytes": 12288, "expected_reconstruction": "INTENT=ACTIVE|ATTEMPT=SEND_STARTED|BROKER=UNKNOWN|KNOWLEDGE=UNOBSERVED|CAPACITY=POTENTIALLY_LIVE", "observed_reconstruction": "INTENT=ACTIVE|ATTEMPT=SEND_STARTED|BROKER=UNKNOWN|KNOWLEDGE=UNOBSERVED|CAPACITY=POTENTIALLY_LIVE", "outcome": "MET"}
{"scenario_id": "L3-04", "evidence_id": "STATE-EV-004", "target_component": "CompositeState + durable staterestore store + restart reload + reconstruct_conservative, across a real process boundary", "crash_point": "AT_NON_TERMINAL_BROKER_ORDER_BOUNDARY", "crash_exit_status": 137, "seed": 0, "writer_pid": 16918, "reader_pid": 16919, "store_real_on_disk": true, "store_bytes": 12288, "expected_reconstruction": "INTENT=ACTIVE|ATTEMPT=SENT_UNCONFIRMED|BROKER=UNKNOWN|KNOWLEDGE=UNOBSERVED|CAPACITY=POTENTIALLY_LIVE", "observed_reconstruction": "INTENT=ACTIVE|ATTEMPT=SENT_UNCONFIRMED|BROKER=UNKNOWN|KNOWLEDGE=UNOBSERVED|CAPACITY=POTENTIALLY_LIVE", "outcome": "MET"}
{"scenario_id": "L3-05", "evidence_id": "STATE-EV-004", "target_component": "CompositeState + durable staterestore store + restart reload + reconstruct_conservative, across a real process boundary", "crash_point": "BETWEEN_DIMENSION_TRANSACTIONS_INCOMPLETE_STORE", "crash_exit_status": 137, "seed": 0, "writer_pid": 16920, "reader_pid": 16921, "store_real_on_disk": true, "store_bytes": 12288, "expected_reconstruction": "INTENT=ACTIVE|ATTEMPT=SEND_STARTED|BROKER=UNKNOWN|KNOWLEDGE=UNOBSERVED|CAPACITY=POTENTIALLY_LIVE", "observed_reconstruction": "INTENT=ACTIVE|ATTEMPT=SEND_STARTED|BROKER=UNKNOWN|KNOWLEDGE=UNOBSERVED|CAPACITY=POTENTIALLY_LIVE", "outcome": "MET"}
{"scenario_id": "L3-06", "evidence_id": "STATE-EV-004", "target_component": "CompositeState + durable staterestore store + restart reload + reconstruct_conservative, across a real process boundary", "crash_point": "AFTER_STALE_OPTIMISTIC_CACHE", "crash_exit_status": 137, "seed": 0, "writer_pid": 16922, "reader_pid": 16923, "store_real_on_disk": true, "store_bytes": 12288, "expected_reconstruction": "INTENT=ACTIVE|ATTEMPT=SENT_UNCONFIRMED|BROKER=UNKNOWN|KNOWLEDGE=UNOBSERVED|CAPACITY=POTENTIALLY_LIVE", "observed_reconstruction": "INTENT=ACTIVE|ATTEMPT=SENT_UNCONFIRMED|BROKER=UNKNOWN|KNOWLEDGE=UNOBSERVED|CAPACITY=POTENTIALLY_LIVE", "outcome": "MET"}
{"scenario_id": "L3-07", "evidence_id": "STATE-EV-004", "target_component": "CompositeState + durable staterestore store + restart reload + reconstruct_conservative, across a real process boundary", "crash_point": "AFTER_TERMINAL_FILL_WITH_POSITIVE_KNOWLEDGE", "crash_exit_status": 137, "seed": 0, "writer_pid": 16924, "reader_pid": 16925, "store_real_on_disk": true, "store_bytes": 12288, "expected_reconstruction": "INTENT=ACTIVE|ATTEMPT=ACK_OBSERVED|BROKER=FILLED|KNOWLEDGE=CONFLICTED|CAPACITY=POSITION_CONSUMED", "observed_reconstruction": "INTENT=ACTIVE|ATTEMPT=ACK_OBSERVED|BROKER=FILLED|KNOWLEDGE=CONFLICTED|CAPACITY=POSITION_CONSUMED", "outcome": "MET"}
{"scenario_id": "L3-08", "evidence_id": "STATE-EV-004", "target_component": "CompositeState + durable staterestore store + restart reload + reconstruct_conservative, across a real process boundary", "crash_point": "AFTER_COMPLETE_DURABLE_COMMIT", "crash_exit_status": 137, "seed": 0, "writer_pid": 16926, "reader_pid": 16928, "store_real_on_disk": true, "store_bytes": 12288, "expected_reconstruction": "INTENT=ACTIVE|ATTEMPT=SENT_UNCONFIRMED|BROKER=UNKNOWN|KNOWLEDGE=CONFLICTED|CAPACITY=POTENTIALLY_LIVE", "observed_reconstruction": "INTENT=ACTIVE|ATTEMPT=SENT_UNCONFIRMED|BROKER=UNKNOWN|KNOWLEDGE=CONFLICTED|CAPACITY=POTENTIALLY_LIVE", "outcome": "MET"}

```

---- FILE tos-evidence/STATE-EV-004/20260806T015632Z-12dd4077/junit.xml ----
```
<?xml version="1.0" encoding="utf-8"?><testsuites name="pytest tests"><testsuite name="pytest" errors="0" failures="0" skipped="0" tests="13" time="2.282" timestamp="2026-08-06T10:56:32.348297+09:00" hostname="ichihun-ui-MacBookPro.local"><testcase classname="tests.tos_l3.test_state_ev_004_crash_restart" name="test_crash_restart_reconstructs_the_hand_derived_anchor[L3-01]" time="2.001" /><testcase classname="tests.tos_l3.test_state_ev_004_crash_restart" name="test_crash_restart_reconstructs_the_hand_derived_anchor[L3-02]" time="0.000" /><testcase classname="tests.tos_l3.test_state_ev_004_crash_restart" name="test_crash_restart_reconstructs_the_hand_derived_anchor[L3-03]" time="0.000" /><testcase classname="tests.tos_l3.test_state_ev_004_crash_restart" name="test_crash_restart_reconstructs_the_hand_derived_anchor[L3-04]" time="0.000" /><testcase classname="tests.tos_l3.test_state_ev_004_crash_restart" name="test_crash_restart_reconstructs_the_hand_derived_anchor[L3-05]" time="0.000" /><testcase classname="tests.tos_l3.test_state_ev_004_crash_restart" name="test_crash_restart_reconstructs_the_hand_derived_anchor[L3-06]" time="0.000" /><testcase classname="tests.tos_l3.test_state_ev_004_crash_restart" name="test_crash_restart_reconstructs_the_hand_derived_anchor[L3-07]" time="0.000" /><testcase classname="tests.tos_l3.test_state_ev_004_crash_restart" name="test_crash_restart_reconstructs_the_hand_derived_anchor[L3-08]" time="0.000" /><testcase classname="tests.tos_l3.test_state_ev_004_crash_restart" name="test_the_catalog_is_the_eight_design_cells_and_no_row_is_silently_dropped" time="0.000" /><testcase classname="tests.tos_l3.test_state_ev_004_crash_restart" name="test_every_anchor_is_falsifiable_and_no_two_cells_are_the_same_observation" time="0.000" /><testcase classname="tests.tos_l3.test_state_ev_004_crash_restart" name="test_a_store_no_writer_ever_touched_is_refused_not_fabricated" time="0.127" /><testcase classname="tests.tos_l3.test_state_ev_004_crash_restart" name="test_the_verdict_follows_the_store_not_the_scenario_argument" time="0.124" /><testcase classname="tests.tos_l3.test_state_ev_004_crash_restart" name="test_this_suite_never_imports_the_kernel_it_measures" time="0.003" /></testsuite></testsuites>
```

---- FILE tos-evidence/STATE-EV-004/20260806T015632Z-12dd4077/manifest.yaml ----
```
schema: tos-evidence/manifest/v3
run_id: 20260806T015632Z-12dd4077
evidence_id: STATE-EV-004
primary_adr: ADR-002-005
design_document: docs/plans/2026-08-06-tos-ev-l3-pilot-design.md
evidence_level_stage: EV-L3
discipline_tag: EV-L3 stage execution record only; not a row PASS; restart coverage argument + network/identity
  residuals + independent review remain as stated in claim/coverage_argument blocks.
claim:
  closes_evidence_item: false
  register_status_moved_by_this_run: false
  register_status_at_run_time: NOT_IMPLEMENTED
  minimum_evidence_level: EV-L3
  independent_review: NOT_SIGNED (VER §9.5)
  p0_1_bounds_approval: OPEN
  verification_profile_version: 2.1 (PROPOSED — P0-1 open)
  target_integrity: STABLE_DURING_RUN
  mutated_during_run: []
  note: This document records that named tests executed at the recorded baseline. It asserts no acceptance,
    no PASS, and no coverage of the higher stages the row's minimum level names.
  ev_l3_stage_gates_unmet: []
  stages_executed:
  - EV-L1
  - EV-L2
  - EV-L3
  stages_executed_note: EV-L1 and EV-L2 are executed as their own run packages and bound here by prior_stage_runs;
    this package is the EV-L3 stage.
  covered_axis: 'STATE-EV-004: persistence + process + reconstruction ONLY (NOT real network, NOT credential
    identity — both modeled/deferred with residual refs in integration_boundary.modeled_axes). Serves
    the STATE-EV-001 R-1 durable axis as its evidence limb (substrate-class: ACID-durability class exercised
    via stdlib sqlite3 WAL; the ADR-002-005 §4 project persistence decision remains OPEN — OQ-1 operator
    adjudication; the R-1 register transition is a conditional dual-record made outside this run). NOT
    PASS-eligible for STATE-EV-004 from this pilot (design #39 §9).'
prior_stage_runs:
- evidence_id: STATE-EV-001
  run_id: 20260806T015629Z-12dd4077
  stage: EV-L1
  sha256sums_digest: e03f10df1cebc4403333d44e9f5665582e68f85ab171e2e07364c0be26f53c53
  artifacts_reverified:
  - baseline.yaml
  - junit.xml
  - manifest.yaml
  - run.log
  - traceability.csv
  baseline_commit_sha: 12dd40778b0237ea6992a3b0a9ecadb10f865f0f
  baseline_matches_this_run: true
  outcome: ALL_SELECTED_TESTS_GREEN
  reconcile_note: 'STATE-EV-001 EV-L1 stage at THIS baseline — prior binding for the STATE-EV-001 durable-limb
    staged continuity (design #39 §6.2 gate 4: the L1∧L2 prior requirement is STATE-EV-001 continuity,
    not a STATE-EV-004 minimum-level claim; STATE-EV-004 is EV-L3-only).'
- evidence_id: STATE-EV-001
  run_id: 20260806T015630Z-12dd4077
  stage: EV-L2
  sha256sums_digest: 73b2a08753d7709bd9fb1043a00caad31c6ddf0486e1131cc917aba7aeecd59f
  artifacts_reverified:
  - baseline.yaml
  - fault-timeline.jsonl
  - junit.xml
  - manifest.yaml
  - run.log
  - traceability.csv
  baseline_commit_sha: 12dd40778b0237ea6992a3b0a9ecadb10f865f0f
  baseline_matches_this_run: true
  outcome: ALL_SELECTED_TESTS_GREEN
  reconcile_note: 'STATE-EV-001 EV-L2 stage at THIS baseline — same continuity basis as the L1 prior (design
    #39 §6.2 gate 4).'
supersedes_run_id: []
supersedes_note: Superseded packages are retained unmodified (VER §2.2); this field is the forward pointer,
  not a deletion record.
integration_boundary:
  persistence:
    technology: stdlib sqlite3 WAL, synchronous=FULL (PILOT-SCOPE; NOT the ADR-002-005 §4 line 61 project
      persistence-technology decision, which remains an open gate)
    real_on_disk: true
    substrate_source: tos/src/tos/staterestore/store.py
    substrate_check: &id002
      met: true
      path: tos/src/tos/staterestore/store.py
      sha256: c4e70f4692d9a4e7b418c1af61ae03827122cc6ee76a1f89de00d84cf3ef4e3f
      measured_from: structural analysis of the executed source's syntax tree; pragmas are read out of
        real execute(...) arguments, so a docstring or comment mentioning one cannot satisfy the check;
        the harness never imports tos (TOS-FW-R)
      measured:
        connect_call_sites: 1
        literal_connection_targets: []
        in_memory_tokens_present: []
        executed_pragmas:
          journal_mode: WAL
          synchronous: FULL
        pragmas_present:
        - journal_mode=WAL
        - synchronous=FULL
        pragmas_missing: []
        pragmas_required:
        - journal_mode=WAL
        - synchronous=FULL
    measured_store_bytes:
    - 12288
  process_boundary:
    writer_pids:
    - 16911
    - 16913
    - 16915
    - 16918
    - 16920
    - 16922
    - 16924
    - 16926
    reader_pids:
    - 16912
    - 16914
    - 16916
    - 16919
    - 16921
    - 16923
    - 16925
    - 16928
    distinct_per_scenario: true
    crash_mechanism: deterministic os._exit at a parametrized crash point (not a racy externally delivered
      SIGKILL)
    observed_crash_exit_statuses:
    - 137
    crash_points: &id001
    - AFTER_COMPLETE_DURABLE_COMMIT
    - AFTER_DURABLE_SEND_STARTED_BEFORE_BROKER
    - AFTER_MODELLED_NETWORK_TRANSMISSION
    - AFTER_STALE_OPTIMISTIC_CACHE
    - AFTER_TERMINAL_FILL_WITH_POSITIVE_KNOWLEDGE
    - AT_NON_TERMINAL_BROKER_ORDER_BOUNDARY
    - BEFORE_EVIDENCE_PERSISTENCE
    - BETWEEN_DIMENSION_TRANSACTIONS_INCOMPLETE_STORE
  modeled_axes:
  - axis: network
    disposition: MODELED
    residual_ref: 'design #39 §2.4 R-N (PROPOSED_NOT_YET_REGISTERED; carrier ADVERSE-SCENARIO-SET-002-EVL3-PILOT.yaml)'
    note: VirtualBroker capability-class marker; real broker network deferred to EV-L4/+Broker; real-futures
      real-order path policy-blocked (zero real order bytes)
  - axis: credential_identity
    disposition: DEFERRED
    residual_ref: 'design #39 §2.4 R-I (PROPOSED_NOT_YET_REGISTERED; carrier ADVERSE-SCENARIO-SET-002-EVL3-PILOT.yaml)'
    note: logical identity re-derivation executed; real credential/cross-host auth deferred to STATE-EV-005
      (+Security)
  modeled_axis_residual_declared: true
  modeled_axes_note: An axis listed here was NOT exercised as a real boundary by this stage; each carries
    the §378 residual that holds it. VER §5 line 151-153 defines EV-L3 by real persistence, identity and
    network boundaries — this run realizes persistence, the process boundary and logical identity re-derivation
    only.
crash_injection:
  catalog_ref: docs/plans/2026-08-06-tos-ev-l3-pilot-design.md#4
  seed: 0
  seed_pinned: true
  schedule_artifact: crash-timeline.jsonl
  crash_scenario_count: 8
  expected_crash_scenario_count: 8
  crash_scenario_count_matches_catalog: true
  scenario_ids:
  - L3-01
  - L3-02
  - L3-03
  - L3-04
  - L3-05
  - L3-06
  - L3-07
  - L3-08
  duplicate_scenario_ids: []
  foreign_evidence_id_rows: []
  deviation_scenarios: []
  misreported_outcome_scenarios: []
  expected_undefined_scenarios: []
  unobserved_reconstruction_scenarios: []
  shared_process_scenarios: []
  non_durable_store_scenarios: []
  crash_points: *id001
  process_boundary_real: true
  persistence_real_measured: true
  all_crash_scenarios_met: true
  all_crash_scenarios_met_basis: every row's outcome RE-DERIVED from observed vs expected reconstruction
    plus the row's own structural boundary measurements (the row's outcome field is cross-checked, never
    trusted); withheld on an empty schedule (0 injected != 0 violations), any deviation or misreport,
    any undefined Expected or unobserved reconstruction, a writer/reader pid that is not a real distinct
    pair, a store that was not a non-empty on-disk file, a duplicated scenario id, a row from another
    evidence id, or a recount that disagrees with the catalog size
  persistence_real: true
  persistence_substrate_check: *id002
coverage_argument:
  specification: tos-spec/src/part-1-foundation/VER-002-001-Safety-Critical-Architecture-Verification-Evidence-Specification.md
    §2.7 (line 76-78) — a finite set of executed evidence cases does not by itself discharge a universally-quantified
    safety claim. Both this row's Expected clauses are universally quantified, so the coverage argument
    is mandatory.
  boundary_values: per crash-point x composite boundary combinations, deterministically enumerated (seed-fixed);
    the restart axis only
  adverse_scenario_set: ADR-002-021 PROPOSED (unapproved) — adversarial-combination leg UNMET; applicability
    to non-risk row = OQ; residual per §378
  unexercised_residual_ref:
  - 'R-N — STATE-EV-004 real-network-boundary axis unexercised: transmission is a modeled (capability-class
    VirtualBroker) marker, zero real order bytes; real broker network is EV-L4/+Broker and the real-futures
    real-order path is policy-blocked (design #39 §2.4). PROPOSED_NOT_YET_REGISTERED — carried by ADVERSE-SCENARIO-SET-002-EVL3-PILOT.yaml;
    registration follows per design #39 §11 step 3 (operator gate).'
  - 'R-I — STATE-EV-004 credential/service-identity axis unexercised: logical identity re-derivation executed;
    real credential/cross-host auth deferred to STATE-EV-005 (+Security) (design #39 §2.4). PROPOSED_NOT_YET_REGISTERED
    — carried by ADVERSE-SCENARIO-SET-002-EVL3-PILOT.yaml.'
  - 'R-D — power-loss/torn-sector durability unexercised: os._exit models application crash, not kernel
    page-cache loss; synchronous=FULL is unfalsifiable under the process-crash model (equivalent-mutant
    E, design #39 §2.4 errata v1.2 addendum) and is pinned structurally instead. PROPOSED (candidate)
    — carried by ADVERSE-SCENARIO-SET-002-EVL3-PILOT.yaml.'
  unexercised_residual_note: 'The §378 Residual Risk Register INSTANCE is absent (measured: verification/
    holds only RESIDUAL-RISK-ACCEPTANCE-RECORD-template.yaml; tos-evidence/ holds zero residual artifacts)
    — creating it is prerequisite work. Each entry SHALL carry all twelve VER:3293-3306 fields (risk identity;
    affected requirement/ADR; scope; credible failure sequence; maximum economic effect; existing controls;
    detection/containment bound; owner; approver; expiration/review date; required scope reduction; evidence
    references), and owner/approver come through the P0-3 role system (D1). The refs above are pointers,
    not a union: separate residual risks SHALL NOT be unioned at a consumer (VER:3308) — each is registered
    independently.'
  discharged: false
  discharged_note: The adversarial-combination leg cannot be discharged while ADR-002-021 is PROPOSED,
    and an unresolved applicability question defaults to APPLICABLE (VER §2.4 line 64-66; VER:173 'Missing
    resolution is a blocker and SHALL NOT default to the lowest level'). This run therefore records the
    argument's state; it does not claim to have made it.
execution:
  command:
  - /Users/harris/Development/private/kis_unified_sts/.venv/bin/python
  - -m
  - pytest
  - tests/tos_l3/test_state_ev_004_crash_restart.py
  - -q
  - --junitxml=/Users/harris/Development/private/kis_unified_sts/tos-evidence/STATE-EV-004/20260806T015632Z-12dd4077/junit.xml
  - --hypothesis-seed=0
  - --l3-crash-timeline=/Users/harris/Development/private/kis_unified_sts/tos-evidence/STATE-EV-004/20260806T015632Z-12dd4077/crash-timeline.jsonl
  cwd: /Users/harris/Development/private/kis_unified_sts
  env_overrides:
    PYTHONPATH: tos/src
    PYTHONHASHSEED: '0'
  started_utc: '2026-08-06T01:56:32.140349+00:00'
  finished_utc: '2026-08-06T01:56:35.152801+00:00'
  monotonic_duration_s: 3.01241
  return_code: 0
  outcome: ALL_SELECTED_TESTS_GREEN
  junit_summary:
    tests: 13
    failures: 0
    errors: 0
    skipped: 0
    time_s: '2.282'
  stage_gate_outcome: EV_L3_STAGE_GATES_MET
test_nodes:
- tests/tos_l3/test_state_ev_004_crash_restart.py
baseline:
  file: baseline.yaml
  sha256: eced9b729b62ee51cb4b5feb470efd42431cfb3937d4f61f11630ca02d5f41f7
  completeness: NOT complete (VER §3 line 109 has no 'as applicable' clause). VER §3 fields without an
    existing artifact are NOT_APPLICABLE_MODELED_TRANSPORT_L3; the unmet set is enumerated in baseline.yaml::ver_002_001_section_3_unmet_fields.
  ver3_unmet_field_count: 16
artifacts:
- name: baseline.yaml
  sha256: eced9b729b62ee51cb4b5feb470efd42431cfb3937d4f61f11630ca02d5f41f7
  bytes: 31690
- name: crash-timeline.jsonl
  sha256: bda362559afc9f3d1e21dec93d50acc8cb32ab6684e04ca4be12444211c0472a
  bytes: 5270
- name: junit.xml
  sha256: cf4f8f309de963f5f36982d86d311488e350181c84fb03fe2136949e83cd69b5
  bytes: 2250
- name: run.log
  sha256: 8b04062ddad3daa45eca1efccaf65047f88990ba557144c9c3cdcff71f7febac
  bytes: 588
- name: traceability.csv
  sha256: 2fb60c7fe999f5dfca04aba86cd62ee10088eb401db3d8b1743b93d648071d01
  bytes: 736
artifact_closure_note: manifest.yaml cannot contain its own digest; sha256sums.txt is written last and
  closes over every retained file including this manifest (VER §9.2).

```

---- FILE tos-evidence/STATE-EV-004/20260806T015632Z-12dd4077/run.log ----
```
$ PYTHONPATH=tos/src PYTHONHASHSEED=0 /Users/harris/Development/private/kis_unified_sts/.venv/bin/python -m pytest tests/tos_l3/test_state_ev_004_crash_restart.py -q --junitxml=/Users/harris/Development/private/kis_unified_sts/tos-evidence/STATE-EV-004/20260806T015632Z-12dd4077/junit.xml --hypothesis-seed=0 --l3-crash-timeline=/Users/harris/Development/private/kis_unified_sts/tos-evidence/STATE-EV-004/20260806T015632Z-12dd4077/crash-timeline.jsonl

--- stdout ---
.............                                                            [100%]

--- stderr ---

--- return code: 0 ---

```

---- FILE tos-evidence/STATE-EV-004/20260806T015632Z-12dd4077/sha256sums.txt ----
```
eced9b729b62ee51cb4b5feb470efd42431cfb3937d4f61f11630ca02d5f41f7  baseline.yaml
bda362559afc9f3d1e21dec93d50acc8cb32ab6684e04ca4be12444211c0472a  crash-timeline.jsonl
cf4f8f309de963f5f36982d86d311488e350181c84fb03fe2136949e83cd69b5  junit.xml
21231169e6c1835839e475b83a16cff945e3c26d705946abbf91802d05664200  manifest.yaml
8b04062ddad3daa45eca1efccaf65047f88990ba557144c9c3cdcff71f7febac  run.log
2fb60c7fe999f5dfca04aba86cd62ee10088eb401db3d8b1743b93d648071d01  traceability.csv

```

---- FILE tos-evidence/STATE-EV-004/20260806T015632Z-12dd4077/traceability.csv ----
```
evidence_id,primary_adr,design_document,test_node,mapping_basis,evidence_claim
STATE-EV-004,ADR-002-005,docs/plans/2026-08-06-tos-ev-l3-pilot-design.md,tests/tos_l3/test_state_ev_004_crash_restart.py,"design #39 §4 catalog (errata v1.2) — 8 crash cells parametrized outside the firewall; Expected = hand-derived anchors (§5.3 oracle independence: the file contains zero `import tos`, AST-asserted from both sides); two-layer assertion per cell: deterministic five-dimension post-restart values from the §13 downgrade/preserve maps + the independent invariant K∉{RECONCILED,CONSISTENT} (§13:199 direct derivation); per-cell expected CPL set pinned with loud abort (exit 70).",STAGE_RECORD_ONLY (does not close the evidence item)

```


============================================================================
# CONTRACT AND SOURCE FILES (line-numbered)
============================================================================

---- SOURCE docs/plans/2026-08-06-tos-ev-l3-pilot-design.md (full) ----
```
    1	# 작업 메모 — tos-spec EV-L3 (Integrated System Fault Test) 파일럿 설계 (2026-08-06)
    2	
    3	> **상태: 비준(RATIFIED) 2026-08-06 · 에라타 v1.2 적용** — 독립 비평 REVISE(CRITICAL 0·MAJOR 2·MINOR 4·
    4	> NIT 3) → v1.1 전건 반영(반론 0) → 동일 리뷰어 델타 재검증 **RATIFY-READY**(전건 해소·신규 phantom 0·
    5	> 부작용 0·비차단 관찰 1건은 §4 CPL 확인 의무로 반영). 비준 주체: 오케스트레이터, ADR-002 시리즈 자동비준
    6	> 위임(2026-07-25, Part-2/3 연장 2026-07-29) — 독립 비평 통과 검증 후 기록. ADR acceptance/live
    7	> authorization은 별개 게이트. **에라타 v1.2**(구현 사이클): §4 CPL 절 사실오류 정정(expected CPL set pin)·
    8	> CPL-6 조건 sanction·§2.4 R-D 부기 — 적대적 코드 리뷰 ACCEPT-WITH-MINOR·이탈 전건 JUSTIFIED(§12).
    9	>
   10	> **v1.1** (독립 비평 REVISE 반영 — CRITICAL 0·MAJOR 2·MINOR 4·NIT 3; 개정 로그 §12). 전 finding을
   11	> **1차 소스 재실측 후 반영**(리뷰어 실측 그대로 신뢰 금지 — 재측정 결과 리뷰어와 불일치 0). 핵심 방향
   12	> 전환: **MAJOR-1** — outside 배치는 subprocess 금지에 의한 **강제가 아니라**, `multiprocessing` spawn
   13	> 우회(inside)가 firewall 허용·기실사용(`tos/tests/test_import_closure.py:6`)이므로 **선택**이다; 채택
   14	> 근거를 "subprocess 금지라서"에서 "**구조적 oracle 독립 우선(구조>convention)**"으로 재서술(§5.2/§5.3).
   15	> **MAJOR-2** — crash 셀의 5차원 커밋 상태 전부 pin + Knowledge 다운그레이드 맵 결정론 파생 + 2층 독립
   16	> 불변식(§4/§5.1). 개정은 문서 직접 편집(오케스트레이터 지시)·커밋 없음.
   17	>
   18	> **문서 성격 (v1.0 저작 초안 상속)**: 이 문서는 `STATE-EV-004`(ADR-002-005 AC-005-4 "Conservative Restart
   19	> Reconstruction", EV-L3, NOT_IMPLEMENTED) 행에 **EV-L3 통합-크래시 층**을 얹는 **설계·실행 계획**이며,
   20	> 그 실행의 부수 효과로 `STATE-EV-001`(EV-L1/2, READY)의 **R-1 durable-axis residual을 닫는** 경로를
   21	> 확정한다. 코드는 작성하지 않는다(설계 계약 단계). **어떤 acceptance/PASS도 선언하지 않는다** — L3 실행이
   22	> 완료돼도 독립 서명·VER §2.7 coverage argument(restart 축)·STATE-EV-004 자체의 network/identity 잔여
   23	> 축·VER §3 complete-baseline가 남는다(§9).
   24	>
   25	> **성격**: EV-L2 파일럿(`docs/plans/2026-07-29-tos-ev-l2-pilot-design.md`)이 STATE-EV-001의 durable 축을
   26	> 정직 이연한 그 residual(R-1)을, 본 파일럿이 **실 durable 저장 + 실 프로세스 경계**로 처음 방전한다. 이는
   27	> 시리즈 최초의 **닫힌-세계 → 열린-세계 전이**(방법론 플레이북 §5:428) — tos/ 최초의 실 I/O·실 크래시.
   28	>
   29	> **브리핑 규율 상속**: 방법론 플레이북 §0(저작자 절, :27)·부록 B(§0.5 체크리스트 13항, :531)·부록 D(극성,
   30	> :600)·**§5 열린-세계 경계(:423)**. anti-phantom: 모든 인용 grep/Read 실측·file:line 부록 A 병기·존재/부재
   31	> 대칭(부재=negative-grep). EV-L2 파일럿 §2(C1 durable 판정)·§9(R-1 residual)을 1차 소스로 상속했다.
   32	
   33	---
   34	
   35	## 0. 이 문서가 확정하는 것 / 하지 않는 것
   36	
   37	**확정한다**: (1) EV-L3 의미 실측 + "Integrated System Fault Test"가 STATE-EV-004에 요구하는 것의 명시 논증
   38	(§1); (2) 열린-세계 전이의 원리 논증 + EV-L3 3축(persistence/identity/network) 분할·정직 이연(§2); (3)
   39	**persistence 기술 결정**(파일럿-범위 vs ADR §4 프로젝트 결정의 지위 명시, falsifiable 근거)(§3); (4)
   40	crash-restart fault 카탈로그(§4, falsifiable Expected만); (5) **durable-reload 컴포넌트 명세 + oracle
   41	독립성**(§5, EV-L2 파일럿의 "L1 하드닝" 위치의 대응물); (6) 하네스 EV-L3 stage 확장 계약(manifest v3·게이트·
   42	prior L1∧L2 결속·self-test)(§6); (7) STATE-EV-001 R-1 closure 경로 + STATE-EV-002/003 처분 + firewall/gap
   43	canary(§7); (8) 테스트 스위트(§8); (9) 수용 주장의 **축소된** 정확한 형태 + 잔여 게이트(§9).
   44	
   45	**하지 않는다**:
   46	
   47	- **PASS/acceptance 선언.** 하네스는 원리적으로 row status를 이동시키지 않는다(`tools/tos_evidence_run.py:26`).
   48	- **실 broker 주문 전송.** 파일럿은 **실 주문 0바이트**를 방출한다. STATE-EV-004:1045의 "after network
   49	  transmission" 크래시 지점은 **모델된(capability-class VirtualBroker) 전송 마커**로 실현하며, 실 broker
   50	  네트워크는 별도 residual(§2.4 R-N)이다 — 실 선물 계좌 무입금·실주문 경로 영구 차단 정책(CLAUDE.md 비협상
   51	  규칙) 준수. tos-spec broker-agnostic(KIS 사실 금지) 준수.
   52	- **STATE-EV-004의 PASS.** 그 자체 EV-L3의 network·credential-identity 축이 모델/이연이라 STATE-EV-004는
   53	  본 파일럿만으로 PASS-부적격(§9). 파일럿은 STATE-EV-004의 **persistence+process+reconstruction 축**을
   54	  실행하고, 그 산출이 STATE-EV-001의 **R-1(durable) 축**을 방전한다.
   55	- **ADR-002-017 Recovery Barrier / 재-arm 체인.** ADR-002-005 §13:200이 요구하는 "no new risk … until
   56	  Recovery Barrier … re-arm chain"은 **별개 EV-L3 통합**(recovery orchestration)이다. 파일럿은 §13:197-199
   57	  (durable + 보수 재구성)만 방전하고 §13:200은 정직 이연(§7, §10).
   58	- **durable-reload 컴포넌트의 구현.** §5는 코드 명세만 확정 — 구현은 별도 단계(executor)다.
   59	
   60	---
   61	
   62	## 0.5. 선제-봉합 체크리스트 (플레이북 부록 B:531 상속 + 본 문서 앵커 + 열린-세계 신설)
   63	
   64	| # | 규율 | 본 문서 적용 |
   65	|---|------|-------------|
   66	| 1 | **anti-phantom (부재·존재 대칭)** | 전 인용 file:line 부록 A. 부재 5건 negative-grep(§6 STAGE_L3 부재·§3 sqlite3 tos/ 부재·§2 tos/ 실 I/O 부재·§7 STATE-EV-004 evidence dir 부재·§5 network token 부재). |
   67	| 2 | **∅-seal 양방향** | "crash scenario 0건 실행"≠"위반 없음". `all_crash_scenarios_met`에 "빈 스케줄 ⇒ GREEN 불가" 구조 게이트(§6). |
   68	| 3 | **구조 파생 > 자기신고** | reconstruction verdict는 self-report 아닌 **durable store 실독 + 구조 비교**에서 관측. 프로세스 경계는 writer_pid ≠ reader_pid 구조 검사(§6). |
   69	| 4 | **falsifiable Expected만** | Expected가 결정적·반증가능하지 않은 crash 지점은 카탈로그 제외·residual 이연(§4). |
   70	| 5 | **음극성 `is False`만 (부록 D:600)** | 신설 극성 코드 최소화. reconstruct 결과의 극성은 Enum identity(`is UNKNOWN`/`is CONFLICTED`)로 관측 — truthy 금지. |
   71	| 6 | **register CSV 전수 파싱** | STATE-EV-00x 행은 csv 모듈/awk 컬럼 고정 파싱(§부록 A). naive grep head 금지. |
   72	| 7 | **over-scope 금지 (정직 이연)** | network·credential-identity·Recovery Barrier·STATE-EV-002/003 L3·power-loss durability 전부 명시 이연(§7·§10). |
   73	| 8 | **뮤테이션 canary 실효성** | 각 crash fault: both-ways + reload-path mutant(RECONCILED 기본·stale-cache 신뢰·낙관 채움·sync 하향)가 **outside 하드코딩 앵커 테스트를 FAIL**시킴을 실측 의무(§5·§8). |
   74	| **O-1** | **열린-세계 배선 fail-open (플레이북 §5:436)** | fail-open이 술어 내부가 아니라 **배선(store↔process↔reload)**에 산다. §5가 durable-reload seam을 명시·gap canary로 잠금(§7). |
   75	| **O-2** | **결정론 canary 공백 (플레이북 §5:437)** | crash 지점은 **파라미터화된 결정론 os._exit**(racy SIGKILL 아님)·scenario 열거 순서 고정·seed=0(pure projection property). 비결정 크래시는 acceptance 집합 제외(§4·§6). |
   76	| **O-3** | **oracle 독립성 (ASS-CM-04:590 상속)** | "guard가 곧 oracle"을 **firewall R-reverse로 구조 차단**: outside 크래시 테스트는 `import tos` 불가(reverse 규칙 e:192)라 `reconstruct_conservative`를 호출 못 함 ⇒ Expected는 **손으로 유도한 독립 하드코딩 앵커**(§5.3). inside(mp-spawn)도 가능하나(MAJOR-1) **구조적 oracle 독립을 위해 outside 선택 구매**(구조>convention, §5.2 대안 B). |
   77	| **O-4** | **committed canary 전수-grep (누적 교훈)** | 터치 표면(tos.staterestore·outside 테스트·harness L3)의 **모든 committed canary 전수-grep**·closure allowlist만으론 불충분. stale-.pyc 퍼지 필수(§8). |
   78	| **O-5** | **저작-레벨 firewall 잠금** | 신규 `tos.staterestore`는 firewall AST 게이트(`tools/tos_firewall_check.py`:203) 통과 의무 — subprocess/socket 등 금지 stdlib 직접 import 0·os.environ 0(§5·§8). |
   79	
   80	---
   81	
   82	## 1. EV-L3의 의미 실측 (VER-002-001 verbatim)
   83	
   84	### 1.1 강도 레벨 정의 (VER §5:143-161)
   85	
   86	```text
   87	EV-L1 (VER:143-145) Model and Property Verification — state-machine exploration, model
   88	                    checking, property-based testing, deterministic simulation.
   89	EV-L2 (VER:147-149) Component Fault Test — "A component is tested with controlled failure
   90	                    injection and authoritative state inspection."
   91	EV-L3 (VER:151-153) Integrated System Fault Test — "Multiple live-path components are tested
   92	                    together with real persistence, identity, and network boundaries."
   93	EV-L4 (VER:155-157) Broker Sandbox or Certified Test Environment.
   94	EV-L5 (VER:159-161) Restricted Production Verification.
   95	```
   96	
   97	**세 문장의 델타가 본 설계의 전 경계를 규정**: L1=valid 공간 속성; L2=단일 컴포넌트+통제 실패주입+권위 상태
   98	검사(EV-L2 파일럿이 방전); **L3=다중 live-path 컴포넌트 통합 + 실 persistence·identity·network 경계**.
   99	따라서 L3가 L2에 **추가로 요구하는 것**은 정확히 세 축이다: (a) **실 persistence**(in-memory 직렬화가
  100	아닌 실 durable 저장), (b) **실 identity**(실 프로세스/자격/식별 경계), (c) **실 network**(실 전송 경계).
  101	
  102	### 1.2 STATE-EV-004가 EV-L3로 요구하는 것 (VER:1041-1046 verbatim)
  103	
  104	**STATE-EV-004 — Conservative Restart Reconstruction** (VER:1041-1046):
  105	- Minimum: `EV-L3`(1043). Supports: **AC-005-4**(1044) — STATE-EV-001의 AC-005-1과 **다른 AC**.
  106	- **Injection**(1045): "Crash at each attempt and broker-order boundary, including after durable
  107	  `SEND_STARTED`, after network transmission, and before evidence persistence; then restart with
  108	  incomplete stores and stale caches."
  109	- **Expected**(1046): "Potentially live attempts and non-terminal orders reconstruct as `POTENTIALLY_LIVE`
  110	  or `UNKNOWN`; Knowledge is re-derived and never defaults to `RECONCILED`."
  111	
  112	**규범 근거 (ADR-002-005 §13:195-200)**:
  113	- §13:197 "All five dimensions SHALL be **durable and reconstructable after crash, restart, or failover**."
  114	- §13:198 "On restart, any Attempt that reached `SEND_STARTED` and any Broker Order that is not provably
  115	  terminal SHALL be treated as `POTENTIALLY_LIVE`/`UNKNOWN` until reconciled."
  116	- §13:199 "Knowledge SHALL be re-derived from evidence, defaulting to `UNOBSERVED`/`CONFLICTED`, never to
  117	  `RECONCILED`."
  118	- §13:200 "No new risk SHALL be authorized until the **ADR-002-017 Recovery Barrier** … re-arm chain
  119	  completes." ⇒ **별개 통합**(§7 이연).
  120	- §19:271 "restart reconstructs a conservative composite state **in tests**."
  121	
  122	### 1.3 세 축의 파일럿 처분 (요약 — §2에서 논증)
  123	
  124	| EV-L3 축 | STATE-EV-004에서의 지시체 | 파일럿 처분 |
  125	|---|---|---|
  126	| **real persistence** | 실 fault(크래시)를 견딘 실 persisted 권위 record(§13:197) | **실행** — 실 on-disk store·프로세스 사후 재적재 |
  127	| **real identity (논리)** | 재구성이 intent/attempt/order **식별자를 store에서 재파생**(reconstruct는 intent_identity 보존, `predicates.py:735`) | **실행** — 논리 식별자 재파생 |
  128	| **real identity (자격/호스트)** | 실 자격·cross-host auth 경계 | **이연** — STATE-EV-005(+Security):1050; residual R-I(§2.4) |
  129	| **real network** | 실 broker 전송(§1045 "after network transmission") | **이연** — 모델 전송; residual R-N; 실주문 정책 영구 차단(§0) |
  130	
  131	**핵심 이중-AC 서비스**: 단일 crash-restart run이 (i) STATE-EV-004/AC-005-4의 **재구성**("post-restart
  132	POTENTIALLY_LIVE/UNKNOWN")과 (ii) STATE-EV-001/AC-005-1의 **durable/persisted**("persisted", :237; R-1)
  133	**양쪽 증거를 동시에 산출**한다. R-1은 persistence 축에만 걸리므로 network/identity 축 이연과 무관하게 닫힌다
  134	(§7).
  135	
  136	### 1.4 §2.7 coverage argument 의무 (VER:79)
  137	
  138	STATE-EV-004 Expected는 **전칭**("**every** … boundary", "**never** defaults to `RECONCILED`")이라 VER:79
  139	coverage argument 의무. 최소 요건 = per-dimension boundary values + "adversarial combinations of the
  140	approved Adverse Scenario Set (ADR-002-021)". ADR-002-021은 여전히 **Proposed**(§9-2). ⇒ EV-L2 파일럿과
  141	동형으로, restart 축 전용 **ADVERSE-SCENARIO-SET-002-EVL3 인스턴스**(운영자 승인)로 adversarial leg를 리뷰
  142	층에서 방전하되 하네스는 `discharged:false`를 기계적으로 유지(§6·§9). VER:3171도 "bounded model still requires
  143	the §2.7 coverage argument"라 못 박음.
  144	
  145	---
  146	
  147	## 2. 원리 논증 — 열린-세계 전이 + EV-L3 축 분할
  148	
  149	### 2.1 닫힌-세계 → 열린-세계 (시리즈 최초 실 I/O)
  150	
  151	Part 1(ADR-002)은 **닫힌 세계**였다 — 순수 술어, I/O 없음, 시간조차 `tos.time` 데이터(플레이북 §5:428).
  152	**실측**: tos/src 전체에 sqlite3/fsync/실 파일쓰기 **부재**(negative-grep — `sqlite3`·`fsync`·`open(` 매칭은
  153	sir의 `_member_is_open` 오탐뿐, §부록 A). `orthostate/__init__.py:11` verbatim "**no** persistence / durable
  154	restart"; `:38-39` "STATE-EV-### remains NOT_IMPLEMENTED pending EV-L2/L3 … durable persistence … real
  155	restart." `reconstruct_conservative` docstring(`predicates.py:692`) verbatim "actual durable reload / crash
  156	recovery / Recovery Barrier are **EV-L3**." ⇒ **본 파일럿이 tos/ 최초의 실 durable 저장·실 프로세스 경계를
  157	도입**한다. 이는 firewall 배제가 아니라 **의도된 진화**(플레이북 §5:442 "새 레인 필요 … 정의는 수직 슬라이스
  158	설계 사이클 소관") — firewall은 import 경계만 규정하며 파일 I/O를 금하지 않는다(§3.1).
  159	
  160	### 2.2 "durable" 지시체는 열린-세계에서만 존재한다 (EV-L2 파일럿 C1 상속)
  161	
  162	EV-L2 파일럿 §2.2가 확정한 축 분할을 1차 소스로 상속한다: STATE-EV-001 durable 축("durable" VER:1025;
  163	crash 복원 ADR §13:197; "persisted" AC-005-1:237)의 **지시체 = 실 fault를 견딘 실 persisted 권위 record —
  164	in-memory에 부재**. EV-L2(순수 모델)로는 **도달 불가**라 R-1 residual로 이연됐다(`STATE-EV-001` 레지스터
  165	notes:91; RESIDUAL-RISK-REGISTER-002 R-1). **본 파일럿이 그 지시체를 처음 실현**한다: 실 store에 commit →
  166	**실 프로세스 크래시(os._exit)** → **fresh 프로세스**가 store 재적재 → 재구성. 두 프로세스 사이 유일 채널이
  167	on-disk store라는 점이 곧 "real persistence … boundaries"(VER:153)의 방전이다.
  168	
  169	### 2.3 EV-L3 축 분할 — 대안 명시 검토
  170	
  171	| 대안 | 논증 | 판정 |
  172	|---|---|---|
  173	| **A. STATE-EV-004 EV-L3를 3축 모두 실행** | 실 network=실 broker 전송=실 선물 주문 ⇒ 정책 영구 차단(CLAUDE.md); broker-agnostic 위반; 불가 | **기각** |
  174	| **B. 실 network 불가 ⇒ STATE-EV-004 미실행·R-1 영구 미방전** | reconstruction Expected(1046)·durable 축(R-1)은 network 축과 무관하게 실 persistence+process로 완전 검증 가능 ⇒ 미실행은 정보 손실이고 운영자 지시("최종 완료")에 반함 | **기각** |
  175	| **C. 축 분할: persistence+process+reconstruction 실행, network/credential-identity residual**(채택) | reconstruction·durable은 실 persistence+process로 방전; network(모델)·credential-identity(STATE-EV-005)는 정직 residual. R-1은 방전 축에만 걸려 닫힘. STATE-EV-004 자체는 PASS-부적격(잔여 축) | **채택** |
  176	
  177	**귀결**: 파일럿은 STATE-EV-004의 **persistence+process+reconstruction 축을 실 EV-L3로 실행**하고, network·
  178	credential-identity 축은 residual로 이연한다. 이 실행이 STATE-EV-001의 **R-1(durable) 축을 방전**한다(그 축은
  179	network/identity와 무관). **STATE-EV-004 자체는 본 파일럿만으로 PASS-부적격**(자체 network/identity 축 미방전
  180	+ 독립 서명 미완). 이 비대칭을 §4 태그·§9 수용주장·§10 경계표가 관철한다.
  181	
  182	### 2.4 이연 축의 residual 등재 (비-union·독립 — VER:3308)
  183	
  184	파일럿은 §378 레지스터(RESIDUAL-RISK-REGISTER-002.yaml)에 **독립 신규 항** 2건을 등재한다(12필드 SHALL 전수,
  185	owner/approver=D1 operator, 비-union). **R-1과 별개** — R-1은 닫히고 R-N/R-I는 STATE-EV-004 자체를 막는다:
  186	
  187	- **R-N — STATE-EV-004 real-network-boundary 축 미방전**: 전송이 모델(VirtualBroker 마커)이라 실 broker
  188	  네트워크 경계 미증거. 지시체 = EV-L4 broker sandbox(VER:155)/+Broker; 실 선물은 정책 영구 차단(무입금). 실
  189	  economic effect 0(전송 0바이트). Critical이라 WAIVED 불가(VER:131).
  190	- **R-I — STATE-EV-004 credential/service-identity 축 미방전**: 논리 식별자 재파생은 실행하나 실 자격·cross-
  191	  host auth 경계 미증거. 지시체 = STATE-EV-005(EV-L2/3+Security):1050. Critical이라 WAIVED 불가.
  192	
  193	**추가 이연 (candidate residual, 운영자 결정)**: **R-D — power-loss/torn-sector durability**: os._exit는
  194	애플리케이션 크래시(프로세스 사망)를 충실히 모델하나 커널 page-cache·전원상실·torn-sector는 모델하지 못한다
  195	(FS fault injection 필요). 파일럿은 **프로세스-크래시 durability**(§13 "crash, restart")를 방전하고 전원상실
  196	durability는 이연(§4에서 inter-transaction incomplete-store로 대체 커버되는 범위 명시). **(에라타 v1.2 부기)**:
  197	`synchronous=FULL` pragma 자체는 프로세스-크래시 모델에서 **반증 불가**다 — os._exit는 OS page-cache를 죽이지
  198	않으므로 synchronous=OFF는 등가 뮤턴트(구현 시 실측·mutant E)이며, 실행 증거가 주장하는 것은 **프로세스-크래시
  199	durability뿐**이다(전원상실 durability = R-D). pragma의 실재는 별도 구조 검사(AST 기반 `execute()` 인자 검사 +
  200	`PRAGMA synchronous` 반환값 단언)로 고정한다 — 도크스트링 토큰이 검사를 충족시킬 수 없게(리뷰 MINOR-1 하드닝).
  201	
  202	---
  203	
  204	## 3. persistence 기술 결정 (파일럿-범위 — ADR §4 프로젝트 결정 아님)
  205	
  206	### 3.1 firewall 제약 실측
  207	
  208	firewall 허용목록(`2026-07-20-tos-boundary-and-import-firewall-design.md:186-187`): **표준 라이브러리 전체**,
  209	단 직접 import 금지 = `socket, ssl, http, urllib.request, ftplib, smtplib, poplib, imaplib, telnetlib,
  210	subprocess, ctypes`. 서드파티 = `pydantic, numpy, pandas, pytest, hypothesis, pyyaml`(DB 라이브러리 없음).
  211	⇒ **`sqlite3`는 stdlib이며 금지 목록에 없다 ⇒ 허용**(negative-grep: 금지 11개에 sqlite3 부재). `os`(단
  212	`os.environ`/`os.getenv`는 AST 게이트가 검출·금지, :205)·`pathlib`·`hashlib` 허용. **`subprocess` 금지가
  213	본 설계의 핵심 제약**(§5.2·§6).
  214	
  215	### 3.2 후보 평가
  216	
  217	| 후보 | durable 근거 | incomplete-store 주입 | firewall | 판정 |
  218	|---|---|---|---|---|
  219	| **A. stdlib `sqlite3` WAL, `synchronous=FULL`**(채택) | 트랜잭션 원자 commit·재개 시 WAL recovery가 미commit 롤백; 잘 정의된 크래시 의미 | 두 트랜잭션(SEND_STARTED / ACK) 사이 크래시 = 합법 incomplete store | stdlib·clean | **채택** |
  220	| B. append-only 파일 + `os.fsync` 저널 | 투명하나 원자성·torn-record 수제(오류 위험↑) | torn-record 직접 주입 가능하나 A가 inter-tx로 충분 | clean | 보조(§4 torn 주입 옵션) |
  221	| C. atomic rename 스냅샷(temp+fsync+`os.rename`+dir fsync) | POSIX-atomic rename; whole-composite 스냅샷 durable | 증분 attempt/order 마커에 부자연 | clean | 기각(증분성 부족) |
  222	
  223	**결정**: 파일럿 store = **stdlib sqlite3 WAL, synchronous=FULL**. dimension별 마커(intent/attempt/broker/
  224	knowledge/capacity)를 **별도 트랜잭션**으로 commit해 "after SEND_STARTED"·"before evidence persistence"
  225	크래시 지점을 두 트랜잭션 사이에서 실현한다.
  226	
  227	### 3.3 지위 — 파일럿-범위 vs ADR §4
  228	
  229	ADR-002-005 §4:61 verbatim "This ADR does not decide **the persistence technology**." 이는 **프로덕션
  230	persistence 아키텍처 결정**(RCL·ADR-002-016 evidence·failover 통합)으로 **ADR acceptance 인접 거버넌스 행위**
  231	다. 파일럿은 이를 **하지 않는다**. 파일럿 결정은 **"STATE-EV-004 EV-L3 크래시-테스트할 실 substrate"의
  232	파일럿-범위 선택**이며, 비-live-test scope(PROFILE scope.environment `non-live-test`:59)에 한정된다.
  233	
  234	> **⚠ 미해결 쟁점 OQ-1 (§11 최상위)**: R-1의 required_scope_reduction(RESIDUAL-RISK-REGISTER-002 R-1:177)은
  235	> "the persistence technology decision deferred by ADR-002-005 §4 … must be made **first**; an EV-L3 crash/
  236	> restart fault run then discharges the limb"라 적는다. **엄격 독해**로는 §4 프로젝트 결정이 선행이고 파일럿-
  237	> 범위 결정은 그것이 아니다. **파일럿-범위 독해**로는 STATE-EV-004를 돌리는 데 필요한 결정("어떤 실
  238	> substrate를 크래시-테스트하나")은 파일럿 층에서 답 가능하다. 이는 **SPG-EV-002의 coverage-discharge와
  239	> 동형의 운영자/리뷰어 판정**(하네스가 자기-인증 못 하는 leg를 승인 인스턴스가 방전)이다. 본 설계는 (b)를
  240	> 권고하되 — 파일럿-범위 결정 기록 + EV-L3 run 실행 = R-1 방전 — **R-1 closure의 충분성 자체를 운영자 결정
  241	> 항목으로 명시**하고, 축소 수용주장(§9)에 "§4 프로젝트 persistence 결정은 별개 open gate"를 병기한다.
  242	
  243	### 3.4 falsifiable 근거
  244	
  245	- **durable commit**: "sqlite3 WAL·synchronous=FULL은 commit된 record가 os._exit 크래시 후 fresh 프로세스
  246	  재적재에서 존재함을 보장. **반증**: post-commit 크래시가 commit된 record를 소실." (§8 mutant E)
  247	- **incomplete-store rollback**: "미commit(트랜잭션 중 크래시) 쓰기는 재개 시 롤백되어 reader는 마지막 commit
  248	  상태만 관측(torn 아님). **반증**: 재개된 store가 half-written record 노출."
  249	- **process boundary real**: "writer_pid ≠ reader_pid ∧ 유일 채널 = on-disk store 파일. **반증**: 동일 pid
  250	  또는 in-memory 잔존 채널."
  251	
  252	---
  253	
  254	## 4. Crash-Restart Fault 카탈로그 (STATE-EV-004; falsifiable Expected만)
  255	
  256	**컴포넌트 통합**: `CompositeState`(orthostate) + durable store(staterestore, §5) + durable-reload+
  257	`reconstruct_conservative`(§5) + 실 프로세스 경계 + 모델 전송 마커. **크래시 모델**: 파라미터화된 결정론
  258	`os._exit(137)`(racy SIGKILL 아님 — O-2). **seed**: pure projection property는 `--hypothesis-seed=0`+
  259	`PYTHONHASHSEED=0`; 통합 매트릭스는 파라미터화 결정 열거(seed는 스케줄 append-only에 기록, VER §9.1). **주입-
  260	지점**: 실 crash 호출 라인 + durable-reload seam(구현 시 실측 기록 의무). Expected는 **§5.3 outside 하드코딩
  261	앵커**(reconstruct_conservative 재호출 아님 — oracle 독립).
  262	
  263	**MAJOR-2 정정 — 앵커 결정론화**: v1.0은 셀의 커밋 상태를 부분만 지정해 Knowledge 앵커가 셀 서술로부터
  264	파생 불가했다(리뷰어 실측: §13:199는 "defaulting to `UNOBSERVED`/`CONFLICTED`" **둘 다** 허용; `reconstruct_
  265	conservative`는 pre∈`_KNOWLEDGE_DOWNGRADE_ON_RESTART={RECONCILED,CONSISTENT}`(`predicates.py:683-685`)일
  266	때만 CONFLICTED로 강등하고 pre=UNOBSERVED면 UNOBSERVED **보존**(`predicates.py:729-732`) — 재측정 확인).
  267	⇒ v1.1은 **각 셀의 5차원 커밋 상태(I·A·B·K·C)를 전부 pin**해 앵커를 다운그레이드/보존 맵에서 결정론
  268	파생하고, 별도로 **2층 독립 불변식**(reconstruct 재호출 없이 §13:199에서 직파생: `K ∉ {RECONCILED,
  269	CONSISTENT}`)을 병기한다. 부재 차원의 보수-채움 규약은 §5.1 S-2가 논증한다.
  270	
  271	카탈로그 = {Attempt 경계} × {Broker 경계} × {evidence 시점} × {store 완전성} × {cache 신선도}의 결정론 부분
  272	집합. `I=Intent·A=Attempt·B=Broker·K=Knowledge·C=Capacity`. 대표 falsifiable 셀(구현 시 enum 경계 전수 열거):
  273	
  274	| id | crash 지점 | 커밋 5차원 (I·A·B·K·C) — 전부 pin | Expected 재구성 (결정론 값) | 2층 독립 불변식 | 근거 | 태그 |
  275	|---|---|---|---|---|---|---|
  276	| L3-01 | after durable `SEND_STARTED`, broker 수신 전 | ACTIVE·SEND_STARTED·UNKNOWN·**UNOBSERVED**·POTENTIALLY_LIVE | A=SEND_STARTED; B=UNKNOWN(보존); **K=UNOBSERVED(보존·not-in-downgrade)**; C=POTENTIALLY_LIVE | `K∉{REC,CONS}` ∧ `C⪰PL` ∧ `B=UNKNOWN` | §13:198; `predicates.py:659-668,715-719,731-732` | 핵심 |
  277	| L3-02 | after (모델) network transmission | ACTIVE·SENT_UNCONFIRMED·UNKNOWN·**UNOBSERVED**·POTENTIALLY_LIVE | A=SENT_UNCONFIRMED; B=UNKNOWN; K=UNOBSERVED(보존); C=POTENTIALLY_LIVE | `K∉{REC,CONS}` ∧ `C⪰PL` ∧ `B=UNKNOWN` | §13:198; 1045 "after network transmission" | 핵심·모델전송 |
  278	| L3-03 | **before evidence persistence** (in-mem ACK, durable 전 크래시 — durable=pre-ACK) | ACTIVE·SEND_STARTED·UNKNOWN·**UNOBSERVED**·POTENTIALLY_LIVE (in-mem 낙관 지식 **미persist**) | 소실 ACK가 RECONCILED로 부활 안 함 → K=UNOBSERVED(보존); B=UNKNOWN | **`K∉{REC,CONS}`**(load-bearing, 1046 "never … RECONCILED") | §13:199; 1046 | 핵심 |
  279	| L3-04 | broker-order 경계(비-terminal) 크래시 | ACTIVE·SENT_UNCONFIRMED·**⟨비-terminal member, 구현 enum pin⟩**·UNOBSERVED·POTENTIALLY_LIVE | B→UNKNOWN(비-terminal 재구성); K=UNOBSERVED(보존) | `B=UNKNOWN`(비-terminal) ∧ `C⪰PL` | §13:198; `predicates.py:672-679` | 핵심 |
  280	| L3-05 | **incomplete store**(inter-tx 크래시·차원 부분 commit) | A=SEND_STARTED commit; **B·K 미commit(부재)** | S-2 보수-채움: 부재 K→**UNOBSERVED**·부재 B→UNKNOWN; 낙관 채움 금지 | 부재 차원 ∉ 낙관값 ∧ `K∉{REC,CONS}` | 1045 "incomplete stores"; §5.1 S-2 | L3-신규 |
  281	| L3-06 | **stale cache**(낙관 캐시 파일) + 크래시 | store: K=**UNOBSERVED**(보수); 별도 cache: K=RECONCILED(낙관) | reader가 cache **무시**·store 재파생 → K=UNOBSERVED | **`K∉{REC,CONS}`**(cache의 RECONCILED 미유입) | 1045 "stale caches"; §13:199 re-derive | L3-신규 |
  282	| L3-07 | terminal Broker + 양성 Knowledge 크래시(양성 canary·다운그레이드 발화) | ACTIVE·ACK_OBSERVED·**FILLED**·**RECONCILED**·⟨POSITION_CONSUMED, §14:211⟩ (sub-case: K=CONSISTENT) | B=FILLED(terminal **보존**); **K=RECONCILED→CONFLICTED**(강등·in-downgrade); C=rcl 비교자(⪰PL 보존·아니면 상향, 구현 실측) | `B=FILLED(보존)` ∧ `K=CONFLICTED` ∧ `K∉{REC,CONS}` | §13:199; `predicates.py:729-732,683-685`; §14:211 | L3-신규·both-ways |
  283	| L3-08 | **durability 메커니즘**(정상 완전 commit → 크래시 → 재적재; reconstruct=항등) | ACTIVE·SENT_UNCONFIRMED·UNKNOWN·CONFLICTED·POTENTIALLY_LIVE (§14:208·이미 보수적 ⇒ reconstruct 항등) | 재적재 5차원 **== 커밋 5차원**(무손실 durable round-trip·AC-005-1 "representable and persisted") | `reload(store) == committed` (필드 동일) | §13:197; AC-005-1:237; §14:208 | durability |
  284	
  285	**규모**: 대표 8셀(구현은 Attempt·Broker enum 경계 전수로 확장·결정론 열거). `reconstruct_conservative`
  286	코도메인은 **구조적으로 RECONCILED 배제**(`predicates.py:700-702` "codomain **structurally excludes**
  287	RECONCILED") — L3-03/06/07의 `K∉{REC,CONS}` 불변식이 이를 outside에서 독립 재확인(구현 회귀 아닌 §13:199
  288	직파생 앵커).
  289	
  290	**④ L3-08 ↔ R-1 방전의 정밀화 (MAJOR-2)**: L3-08은 **durability 메커니즘 셀 1건**이지 R-1 방전 자체가
  291	아니다. R-1(STATE-EV-001 "**every** valid composite remains representable **and durable**", 1025)은 **전칭**
  292	이므로, 그 방전은 **§14 valid composite + 경계조합(1024) 위의 durability 속성**을 요구하고 **VER §2.7 coverage
  293	argument(§9 게이트 2)에 종속**한다. 즉 "L3-08이 R-1을 직접 방전"이 아니라 "L3-08이 durability 메커니즘을
  294	실증하고, R-1 방전 = 열거된 composite 경계집합 위 durability 속성 + coverage argument"다(§7.1 반영).
  295	
  296	**뮤테이션 canary 실효성 의무** (§8): 각 reload-path mutant가 outside 앵커 테스트를 **FAIL(KILLED)**시킴을
  297	실측 — (A) 부재 Knowledge를 RECONCILED 기본, (B) 비-terminal Broker 보존(UNKNOWN 미강등), (C) stale cache
  298	신뢰, (D) incomplete store 낙관 채움, (E) sqlite `synchronous=OFF`로 durable 소실. 5종 KILLED가 OQ-2/O-2의
  299	경험적 답.
  300	
  301	**카탈로그 제외/이연**: power-loss/torn-sector(R-D, FS fault injection 필요)·Recovery Barrier/재-arm(§13:200,
  302	ADR-002-017 별개 통합)·실 network(R-N)·실 credential(R-I).
  303	
  304	**커밋 composite CPL 정합성 (에라타 v1.2 — "구현이 더 충실하면 에라타가 정답")**: v1.1의
  305	`coupling_violations() == ∅` 요구는 **사실오류**였다 — Broker=UNKNOWN을 pin한 셀(L3-01/02/03/05/08)은
  306	CPL-5를 구조적으로 발화하며(`predicates.py:184-186` — CPL-5는 Broker=UNKNOWN에 Capacity=QUARANTINED_UNKNOWN
  307	정확 요구), 이는 §14 "Composite Examples (all valid)"의 **representable ≠ CPL-clean** 구분과 정합한다(기존
  308	선례 `tos/tests/orthostate/_orthostate_strategies.py:147,167` "representable BUT coupling-negative
  309	(Broker=UNKNOWN fires CPL-5)"). v1.1의 "§14 예시에 미열거된 조합" 표현도 정정한다 — L3-07(§14:211)·
  310	L3-08(§14:208)은 §14에 **열거된** 조합이다. **정정된 의무**: 각 셀은 **expected CPL set을 pin**
  311	(L3-01/02/03/05/08 = {CPL-5}, L3-04/06/07 = ∅)하고, worker가 커밋 composite 구성 시점에 실측
  312	`coupling_violations()`와 대조해 **불일치 시 시끄럽게 abort**(exit 70)한다 — "silent 결함 불가" 의도는
  313	보존된다. 아울러 v1.1이 미명세한 **CPL-6 부작동 조건**을 명시 sanction한다: 전 셀의 Attempt가
  314	≥SEND_STARTED이므로 `authority_epoch_current`가 None이면 CPL-6이 전 셀 발화한다 — 구현의 모델링 결정
  315	(**`authority_epoch_current=True`(authorized-send 모델)·나머지 side-condition flag 전부 None(fail-closed)**)
  316	을 채택한다. CPL 체크는 pre-commit sanity 게이트이며 `reconstruct_conservative`에는 투입되지 않는다
  317	(앵커 결정론성과 무관). 적대적 코드 리뷰 판정: 이탈 (1)·(2) JUSTIFIED(§12 로그).
  318	
  319	---
  320	
  321	## 5. durable-reload 컴포넌트 명세 + oracle 독립성 (구현은 별도 단계)
  322	
  323	EV-L2 파일럿에서 "§5 L1 하드닝"이 L2 실행의 코드 선행이었듯, 본 파일럿의 코드 선행은 **신규 `tos.staterestore`
  324	패키지(durable store + reload 경로)**와 **outside 크래시 orchestration**이다. 각 항은 ADR §13 SHALL의 실현.
  325	
  326	### 5.1 `tos.staterestore` (firewall 내부·subprocess 없음)
  327	
  328	| 항 | 명세 | 근거(SHALL) | firewall |
  329	|---|---|---|---|
  330	| **S-1 store** | sqlite3 WAL·synchronous=FULL로 CompositeState 5-dimension 마커를 dimension별 트랜잭션 commit·재적재 | §13:197 durable | stdlib sqlite3(허용)·subprocess 0 |
  331	| **S-2 reload** | 재개 시 store 실독 → 완전이면 CompositeState 복원 → 불완전/torn이면 **부재 dimension을 보수(UNKNOWN/POTENTIALLY_LIVE) 채움** → `reconstruct_conservative` 적용 | §13:198-199; `predicates.py:688` | orthostate import edge |
  332	| **S-3 no-stale** | in-memory/파일 cache는 재개 시 **폐기**·store에서만 재파생 | §13:199 re-derive; 1046 | — |
  333	| **S-4 worker** | `python -m tos.staterestore._l3_worker <mode> <args>` — writer(commit→`os._exit`)·reader(reload→verdict stdout). 파라미터는 **argv**(os.environ 금지·:205) | 결정론 크래시(O-2) | os._exit·subprocess 0·os.environ 0 |
  334	
  335	**S-2 per-dimension 보수-채움 규약 (MAJOR-2 명세)**: 부재/torn 차원의 채움값은 §13:199에서 논증한다. §13:199
  336	"Knowledge SHALL be re-derived … **defaulting to `UNOBSERVED`/`CONFLICTED`, never to `RECONCILED`**" — 부재
  337	Knowledge의 자연 독해는 **UNOBSERVED**("durable 증거가 없음"은 관측 부재이지 조작된 conflict가 아님)이며,
  338	CONFLICTED는 존재하지 않는 conflict를 단언한다. ⇒ **부재 K→UNOBSERVED**를 채택하되, **load-bearing 불변식은
  339	음성**(`K∉{RECONCILED,CONSISTENT}`)이다(양성 값은 결정론 앵커, 음성 불변식은 oracle-독립 검증축). 타 차원:
  340	부재 B→UNKNOWN; 부재 A→**SEND_STARTED 미존재 시 send 미개시**(§6:96 "durable **before** the external call"의
  341	순서 보장 — durable SEND_STARTED 부재 = 외부호출 미발생, 구조 안전 독해); 부재 C→CPL-1 최소 보수값
  342	(POTENTIALLY_LIVE); 부재 I→식별 불가 record는 재구성 거부(torn-unidentifiable). 완전 차원은 §4대로
  343	`reconstruct_conservative` 적용(다운그레이드/보존 맵).
  344	
  345	**비-transmitting 불변식 보존 (MINOR-3)**: staterestore는 **로컬 durable 저장(disk)만** 추가하고 **egress
  346	0**을 유지한다. tos-wide 불변식 `tos/__init__.py:6` verbatim "This package is **non-transmitting by
  347	construction** (§4): no broker credentials, routes, order-construction, or env-flag capability paths"와,
  348	orthostate-scoped `orthostate/__init__.py:11` "**no** persistence / durable restart / egress"를 함께 보존한다
  349	— persistence(로컬 disk I/O) ≠ transmission(network egress)이며, staterestore는 전자만 도입·후자 0. **canary
  350	열거에 tos-wide non-transmitting 불변식 포함**(§7.4).
  351	
  352	**내부 edge**: staterestore → orthostate(CompositeState·reconstruct_conservative) + canonical(직렬화). 정확한
  353	allowlist 배선은 구현 의무이며 게이트 = `tools/tos_firewall_check.py`(§8). staterestore는 orthostate 순수성
  354	(`orthostate/__init__.py:11` "no persistence")을 침해하지 않도록 **별도 패키지**(orthostate 내부 아님).
  355	**`os._exit` gate-clean 실측**: firewall AST 게이트는 `os.environ`/`os.getenv`만 검출(`tos_firewall_check.py:
  356	214-216,237-240`)이라 worker의 `os._exit`(충실한 abrupt 종료)는 gate 통과 — `tos/tests`의 os 회피 관행
  357	(`test_import_closure.py:6`)은 import-closure 격리용이지 게이트 규칙이 아니다(구현 시 명시).
  358	
  359	### 5.2 프로세스-경계 spawn 배치 — 대안 명시 검토 (MAJOR-1 정정)
  360	
  361	**실측 정정 (v1.0 전제 오류)**: v1.0은 "outside 배치는 `subprocess` 금지(:186)에 의한 **강제**"라 주장했으나
  362	1차 소스 재실측이 이를 반증한다. `multiprocessing`은 stdlib이며 firewall 금지 목록(:186의 11개)에 **없어
  363	허용**(negative-grep: 금지 목록에 multiprocessing 부재)이고, **이미 tos/tests에서 fresh isolated interpreter
  364	목적으로 사용 중**이다 — `tos/tests/test_import_closure.py:6` verbatim "a **fresh, isolated interpreter** (via
  365	`multiprocessing` spawn — `subprocess` and `os` are firewall-forbidden even in tests)"; `:30` `import
  366	multiprocessing as mp`; `tos/tests/test_evidence_import_closure.py:106` `ctx = mp.get_context("spawn")`. 즉
  367	**inside(tos/tests)에서 mp-spawn으로도** writer_pid≠reader_pid·유일채널=on-disk store가 완전 충족된다. 따라서
  368	배치는 **강제가 아니라 선택**이다.
  369	
  370	| 대안 | 프로세스 경계 | oracle 독립 | 대가 | 판정 |
  371	|---|---|---|---|---|
  372	| **A. inside `tos/tests/staterestore/`, `mp.get_context("spawn")`** | 충족(spawn=별 pid·별 인터프리터) — 전 orchestration이 firewall AST 게이트 **인증** 범위 안 | **관행적(conventional)** — parent(tos/tests)는 `import tos` 가능(forward 허용)해 `reconstruct_conservative` 직접 호출 가능; 저자가 "호출 안 함"을 **선택**해야만 독립(구조 강제 아님) | orchestration이 firewall 인증 안(장점) | 후보 |
  373	| **B. outside `tests/tos_l3/`, subprocess spawn**(채택) | 충족 — worker=`python -m tos.staterestore._l3_worker`(tos/ 내부, tos import 합법); outside는 arg-string만 넘김(`import tos` 안 함) | **구조적(structural)** — R-reverse(:192)가 outside의 `import tos`를 **강제 금지**(§5.3) ⇒ `reconstruct_conservative` 호출이 구조 불가 | orchestration(spawn·argv·stdout 파싱·앵커 비교)이 firewall 구조 보증 **밖**(§5.2 firewall 정밀) | **채택** |
  374	
  375	**채택 근거 (구조 > convention)**: 시리즈 메타 교훈 ②("구조 > 자기신고", 플레이북 §6.1:476)를 oracle 층에
  376	적용한다. A는 oracle 독립이 저자 규율(convention)에 의존하고 B는 firewall R-reverse에 의해 **구조적으로
  377	강제**된다. 본 파일럿은 **outside orchestration 복잡도를 지불하고 구조적 oracle 독립을 구매**한다 — EV-L3의
  378	핵심 위험이 ASS-CM-04(:590 "guards … are also the oracles")이므로 그 방어를 관행이 아닌 구조에 둔다.
  379	
  380	**firewall 적용의 정밀 서술 (MINOR-1 정정)**: repo-root `tests/tos_l3/`는 "firewall 밖"이 아니라 **규칙별로
  381	갈린다**. 실측: `tools/tos_firewall_check.py:114-116` `_REVERSE_SCAN_PRUNE = {"tos", ".git", ".venv",
  382	"node_modules", "__pycache__", ".omc", ".history"}` — **`tests` 부재**. ⇒ (i) **forward 규칙(a-d: 허용목록·
  383	금지 stdlib·os.environ)은 tos/(src+tests)에만 적용**(:166-167)이라 repo-root `tests/tos_l3/`는 subprocess
  384	허용; (ii) **reverse 규칙(e: `import tos` 금지)은 repo 전수 스캔**(`check_reverse_imports`:306·prune에 tests
  385	없음)이라 `tests/tos_l3/`에 **적용** — 이것이 O-3 구조 독립의 근거다. worker spawn은 `tos_evidence_run.py`가
  386	`python -m pytest`를 subprocess spawn하는 것과 동형(합법 선례).
  387	
  388	### 5.3 oracle 독립성 (O-3 — firewall R-reverse를 구조 자산으로 전용)
  389	
  390	outside 크래시 테스트는 reverse 규칙(e)상 `import tos` 불가(§5.2 실측) ⇒ **`reconstruct_conservative`를 호출할
  391	수 없다.** ⇒ Expected 재구성은 **§4 표의 손-유도 하드코딩 앵커**(결정론 값 + 2층 불변식 `never ∈ {RECONCILED,
  392	CONSISTENT}`, §4)로 표현하고 worker가 방출한 **실제** 재구성과 비교한다. 이는 ASS-CM-04(:590)를 **구조적으로
  393	차단** — 구현(reconstruct_conservative)에 버그가 있어도 독립 앵커가 잡는다. 방법론의 "자기참조 순서 단언 →
  394	독립 하드코딩 앵커"(누적 교훈)의 oracle-층 적용. **트레이드오프 명시(MAJOR-1)**: 이 구조 독립은 공짜가 아니라
  395	§5.2-B의 outside orchestration 복잡도(firewall 인증 밖의 spawn·파싱·비교)를 대가로 산 것이다 — 대안 A는 그
  396	복잡도를 firewall 인증 안에 두는 대신 oracle 독립을 관행으로 격하한다. **"firewall 제약을 oracle 독립 보증으로
  397	전용"이 본 파일럿의 방법론적 관찰**이며, 이는 강제가 아닌 **의도적 설계 선택**이다.
  398	
  399	---
  400	
  401	## 6. 하네스 EV-L3 stage 확장 계약 (`tools/tos_evidence_run.py`)
  402	
  403	현 하네스 = EV-L1(manifest v1)·EV-L2(manifest v2 superset) 지원. `STAGE_L3`·`is_l3`·manifest v3 **부재**
  404	(negative-grep: `tools/tos_evidence_run.py`에 STAGE_L3/EV-L3/manifest v3 0건, §부록 A). L3는 **additive
  405	확장**(v2 전 필드 유지).
  406	
  407	### 6.1 manifest v2 → v3 (superset·이름 명시)
  408	
  409	> **NIT-1 네임스페이스 주의**: 본 문서의 "manifest v3"는 항상 **`tos-evidence/manifest/v3`**(하네스 manifest
  410	> 스키마)를 뜻하며, self-test의 `_VER3_FIELDS`(=VER-002-001 **§3** baseline 22필드, `test_tos_evidence_run.
  411	> py:293`)와 **무관**하다 — 명명 충돌 방지.
  412	
  413	```yaml
  414	schema: tos-evidence/manifest/v3
  415	evidence_level_stage: EV-L3
  416	prior_stage_runs:                    # [신규 게이트] L1 AND L2 둘 다 THIS baseline에서 결속
  417	  - {evidence_id: STATE-EV-001, stage: EV-L1, baseline_commit_sha: <B>, baseline_matches_this_run: true, ...}
  418	  - {evidence_id: STATE-EV-001, stage: EV-L2, baseline_commit_sha: <B>, baseline_matches_this_run: true, ...}
  419	integration_boundary:                # [v3 신규 필드그룹]
  420	  persistence:
  421	    technology: "stdlib sqlite3 WAL, synchronous=FULL (pilot-scope; NOT the ADR-002-005 §4 project decision)"
  422	    real_on_disk: true               # 구조 검사: store 파일이 실재·프로세스 사후 존재
  423	  process_boundary:
  424	    writer_pid: <int>; reader_pid: <int>   # writer_pid != reader_pid 구조 검사 (real boundary)
  425	    crash_mechanism: "deterministic os._exit at parametrized crash point"
  426	  modeled_axes:                      # [O-1·over-claim 방지] 모델/이연 축은 residual_ref 필수
  427	    - {axis: network, disposition: MODELED, residual_ref: "RESIDUAL-RISK-REGISTER-002 R-N", note: "VirtualBroker marker; real broker network deferred (EV-L4/+Broker); real-futures policy-blocked"}
  428	    - {axis: credential_identity, disposition: DEFERRED, residual_ref: "R-I", note: "logical identity re-derivation executed; real auth deferred (STATE-EV-005 +Security)"}
  429	crash_injection:                     # [신규 — L2 fault_injection의 L3 대응]
  430	  catalog_ref: docs/plans/2026-08-06-tos-ev-l3-pilot-design.md#4
  431	  schedule_artifact: crash-timeline.jsonl      # append-only (VER §9.1)
  432	  seed: 0
  433	  crash_scenario_count: <per-row>
  434	  all_crash_scenarios_met: true      # [게이트] false·미정의 Expected>0 ⇒ GREEN 불가 (관측 vs 하드코딩 앵커 재파생)
  435	  process_boundary_real: true        # [게이트] writer_pid != reader_pid
  436	  persistence_real: true             # [게이트] on-disk store 실재
  437	coverage_argument:                   # VER §2.7 (restart 축) — L2와 동형
  438	  boundary_values: "per crash-point × composite boundary combinations (deterministic enumeration)"
  439	  adverse_scenario_set: "ADVERSE-SCENARIO-SET-002-EVL3 (operator-approved instance) — restart adversarial leg"
  440	  unexercised_residual_ref: ["R-N network", "R-I credential-identity", "R-D power-loss durability"]
  441	  discharged: false                  # 하네스는 자기-인증 안 함 (리뷰층 방전 — §9)
  442	claim:
  443	  closes_evidence_item: false
  444	  register_status_moved_by_this_run: false
  445	  covered_axis: "STATE-EV-004: persistence + process + reconstruction ONLY (NOT real network, NOT credential
  446	    identity). Serves STATE-EV-001 R-1 durable axis. NOT PASS-eligible for STATE-EV-004 from this pilot."
  447	  independent_review: NOT_SIGNED (VER §9.5)
  448	```
  449	
  450	### 6.2 EV-L3 전용 게이트 (각 측정·자기신고 불신 — L2:2130-2149 확장)
  451	
  452	1. **`all_crash_scenarios_met`**: 각 (crash × composite) verdict을 **관측(reader stdout) vs §4 하드코딩 앵커**
  453	   재파생. 빈 스케줄·DEVIATION·미정의 Expected ⇒ 미충족(∅ 양방향, O-2·2번).
  454	2. **`process_boundary_real`**: writer_pid ≠ reader_pid 구조 검사(§0.5-3). 동일 pid ⇒ 미충족(in-process
  455	   fallback이 EV-L3를 위조하는 것 차단).
  456	3. **`persistence_real`**: store가 실 on-disk 파일·프로세스 사후 존재. in-memory ⇒ 미충족(EV-L2 파일럿 C1
  457	   "in-memory 재정의" 재발 차단).
  458	4. **`PRIOR_EV_L1_AND_L2_NOT_BOTH_BOUND_AT_THIS_BASELINE`**(NIT-2 개명 — "OR"의 오독 제거·요건은 AND):
  459	   prior_stage_runs가 **`evidence_id == STATE-EV-001`인 L1 AND L2 둘 다**를 `baseline_matches_this_run:true`로
  460	   결속(L2 게이트 M9의 확장·bind_prior_stage_run:903 재사용). **evidence_id 결속 추가(MINOR-2)**: STATE-EV-003도
  461	   `EV-L1/3` READY(register:93)라 엉뚱한 행의 L1/L2로 충족될 수 있으므로 `evidence_id` 구조 검증 필수. **왜
  462	   L1∧L2인가(오독 방지)**: STATE-EV-004 최소레벨은 `EV-L3`-only(1043)라 이 결속은 STATE-EV-004 **자체 staging
  463	   요건이 아니다** — **STATE-EV-001(EV-L1/2)의 durable-limb 연속성 근거**다(L3 durable 증거가 비-stale L1/L2
  464	   모델 기반에 부착돼 R-1을 방전, §7.1). 하나라도 stale/타-evidence_id ⇒ 미충족.
  465	5. **`modeled_axis_residual_declared`**: `integration_boundary.modeled_axes` 각 항에 `residual_ref` 존재
  466	   (over-claim 방지 — 실 network/identity를 residual 없이 주장하면 미충족).
  467	6. **seed 고정** + **DEVIATION run 보존**(supersedes_run_id, VER §2.2 — L2 게이트 상속).
  468	
  469	미충족 시 `stages_executed`/`covered_axis`는 **WITHHELD**·`invoked_covered_axis`만 기록(L2:2194-2216 패턴
  470	상속). DISCIPLINE_TAG_L3 신문구: "EV-L3 stage execution record only; not a row PASS; restart coverage argument
  471	+ network/identity residuals + independent review remain as stated in claim/coverage_argument blocks."
  472	
  473	### 6.3 §7 applicable 부분집합 (VER:256 "as applicable")
  474	
  475	item 1·2·3(crash-timeline)·4·5·30-34 = ✓. **item(network/broker/authority/human/recovery)** = 부분: 전송은
  476	모델·recovery barrier 미포함 ⇒ N/A + residual 명기(§13:200 이연). baseline 노트는 L2 패턴(NOT_APPLICABLE_
  477	PURE_MODEL_L2 → **NOT_APPLICABLE_MODELED_TRANSPORT_L3**) 갱신·§3 미충족 필드 목록 유지(M2 상속).
  478	
  479	### 6.4 self-test 갱신 (`tests/tools/test_tos_evidence_run.py`, 현 1744행)
  480	
  481	v3 manifest 구조·integration_boundary·crash_injection·6대 게이트(all_crash_scenarios_met withheld-on-empty/
  482	deviation·process_boundary_real pid≠pid·persistence_real·prior L1∧L2 결속·modeled_axis residual 필수·seed)·
  483	DISCIPLINE_TAG_L3·no-PASS(:395) 검증 추가. 게이트 both-ways(충족/미충족 픽스처 각각).
  484	
  485	---
  486	
  487	## 7. R-1 closure 경로 + 인접 행 처분 + firewall/gap canary
  488	
  489	### 7.1 R-1 closure (STATE-EV-001 durable 축)
  490	
  491	R-1 register 요건(RESIDUAL-RISK-REGISTER-002 R-1:173-177): "persistence 기술 결정 + EV-L3 crash/restart run이
  492	limb 방전"·"consumer는 STATE-EV-004를 EV-L3·real persistence substrate로 인용". **파일럿 실행이 이를
  493	**조건부**로 충족**한다:
  494	- persistence 결정 = §3(파일럿-범위 sqlite3 WAL) — **:177 문자적 요건("§4 decision first")은 미충족이므로
  495	  OQ-1 운영자 판정 종속**(MINOR-4).
  496	- EV-L3 crash/restart run = §4 카탈로그. **L3-08은 durability 메커니즘 셀**이고 R-1 방전 = **§14 composite +
  497	  경계조합(1024) 위 durability 속성 + VER §2.7 coverage argument(§9 게이트 2)**다(④ 정밀화 — "L3-08 직접
  498	  방전" 아님).
  499	- **R-1 register 항 전이(MINOR-4 — 무조건 아님)**: "open blocking gap" → "**evidence limb discharged by
  500	  STATE-EV-004 run `<L3 run_id>` (substrate-class); §4 project-persistence gate + substrate-class caveat
  501	  OPEN — pending OQ-1**". OQ-1 미해소 시 **이중 기록**("evidence limb 방전 · §4-decision gate 잔존"). evidence_
  502	  references에 L3 run 추가. **비-union**: R-1은 R-N/R-I와 별개(R-1은 조건부 닫히고 R-N/R-I는 STATE-EV-004
  503	  자체를 막음).
  504	- **substrate-class caveat(MINOR-4·OQ-1)**: evidence-limb 방전은 **substrate-class 수준** — ACID durability를
  505	  제공하는 substrate에서 **모델의 durable-restart 속성**을 검증한 것이다. 상이한 §4 production 기술 선택(역시
  506	  ACID)은 별도 production-acceptance EV-L3 소관이지 **R-1 소급 무효화가 아니다**(모델 속성은 substrate-class로
  507	  검증됨). 이 caveat가 파일럿-범위 결정을 방어 가능하게 한다.
  508	
  509	**R-1 방전 후 STATE-EV-001 PASS의 축소형(여전히 열림)**: (a) L1∧L2 THIS baseline 재실행(§9 절차); (b) restart
  510	축 coverage argument(ADVERSE-SCENARIO-SET-002-EVL3); (c) P0-1(STATE 축 — reconstruction Expected는 **bound-
  511	independent**라 승인 numeric bound 미소비·negative-grep VER:1046에 ms/duration/retention 토큰 0; 단 null
  512	`MIN_evidence_retention_ms`(:923)를 소비하면 fail-closed·§7.3); (d) 독립 서명(VER §9.5)+운영자 countersign;
  513	(e) VER §3 complete-baseline(구조적 미충족 잔존). **파일럿은 R-1 closure까지만 담당·PASS 미선언**.
  514	
  515	### 7.2 인접 행 정직 처분 (over-scope 금지)
  516	
  517	| 행 | 최소 레벨 | 파일럿 처분 |
  518	|---|---|---|
  519	| **STATE-EV-002** Conservative Direction(1029) | EV-L2/3 | **미커버**. Injection(1031)은 timeout/ACK loss/query omission/cache miss/**process restart**/authority expiry/operator assertion — restart는 부분 접점이나 나머지 6주입 미실행. process-restart limb만 접하고 **행 미종결**(정직 부분-접점). |
  520	| **STATE-EV-003** Cross-Dimension Coupling(1036) | EV-L1/3 | **L3 limb 미커버**. Expected(1039)=CPL-1..7 under partial-fill/cancel-crossing + RCL capacity transition. **별개 통합**(coupling/RCL 동시성)이라 restart 파일럿 미접촉(negative: 본 카탈로그에 CPL-2..7 fill/cancel·RCL transition 0). 정직 이연. |
  521	| **STATE-EV-005** Dimension Transition Ownership(1050) | EV-L2/3+Security | **미커버**. credential-identity 축(R-I)의 상위 행. 이연. |
  522	| ADR-002-017 Recovery Barrier / 재-arm(§13:200) | 별개 | **미커버**. reconstruction은 보수 상태 산출; "no new risk until Recovery Barrier … re-arm" recovery orchestration은 별개 EV-L3. 이연(§10). |
  523	
  524	### 7.3 null-key 노출 분석 (fail-closed)
  525	
  526	PROFILE 17 null 키는 key-level 미승인·fail-closed(:6-8). STATE-EV-004 reconstruction Expected(1046)는 **정성적
  527	·bound-independent**(negative-grep: ms/duration/retention/threshold 토큰 0). ⇒ 승인 numeric bound 미소비 —
  528	P0-1 대부분 vacuous 충족. **단** `MIN_evidence_retention_ms`(:923, null)를 소비하는 retention-duration 주장은
  529	파일럿이 **하지 않는다**(재구성은 "얼마나 오래"가 아니라 "무슨 값"이라 retention 무관). 만약 확장이 retention-
  530	duration을 주장하면 null 키에 걸려 **fail-closed·residual**. `B_stale_epoch_reject`=0(승인, :228-232)와 S-3
  531	no-stale re-derive는 **보수 방향만 정합**(NIT-3) — 전자는 **stale ledger/authority epoch fencing**(compare-
  532	and-set), 후자는 **재개 시 cache 폐기·store 재파생**으로 **별개 메커니즘**이다. "0 = no stale window"의 극성이
  533	S-3의 "stale cache 불신"과 같은 보수 방향일 뿐, 동일 메커니즘 주장 아님.
  534	
  535	### 7.4 firewall/gap canary 규율 (O-4·O-5)
  536	
  537	- **firewall 게이트**: 신규 `tos.staterestore` 전 파일이 `tools/tos_firewall_check.py`(:203) 통과 — subprocess/
  538	  socket 등 금지 stdlib 직접 import 0·os.environ 0·R-reverse(outside `import tos` 0) 실측.
  539	- **gap canary**(`tos/tests/slice/test_slice_gaps.py` 규율 상속): 신규 seam을 실행 가능한 관측으로 잠금 —
  540	  (i) reconstruct_conservative 코도메인이 RECONCILED **구조 배제** 유지(`predicates.py:700-702` 회귀), (ii)
  541	  staterestore가 실 on-disk store(in-memory 아님) 구조 검사, (iii) outside 테스트가 `import tos` **미포함**
  542	  negative-grep(R-reverse 보증 = oracle 독립 O-3), (iv) 금지 stdlib 부재 grep, (v) **tos-wide non-transmitting
  543	  불변식 보존(MINOR-3)** — staterestore가 `tos/__init__.py:6` "non-transmitting by construction"을 유지함을
  544	  잠금: 로컬 durable 저장(disk)만 있고 egress(socket/broker route) 0인지 grep(persistence ≠ transmission).
  545	- **committed canary 전수-grep**(누적 교훈): sanction 전 터치 표면(staterestore·outside·harness L3)의 **모든
  546	  committed canary 전수-grep**·closure allowlist만으론 불충분. stale-.pyc 퍼지 필수(§8).
  547	
  548	---
  549	
  550	## 8. 테스트 스위트 계획
  551	
  552	### 8.1 배치 (firewall 경계 준수)
  553	
  554	- **inside tos/** (`tos/tests/staterestore/`, firewall 적용·subprocess 없음): store round-trip·reload
  555	  보수 채움·no-stale re-derive의 **단일-프로세스 단위 테스트** + reconstruct_conservative property(seed=0).
  556	- **outside tos/** (`tests/tos_l3/test_state_ev_004_crash_restart.py`, **forward 규칙(a-d) 미적용 ⇒ subprocess
  557	  허용·reverse 규칙(e) 적용 ⇒ `import tos` 금지**, MINOR-1 정밀): **실 크래시-재개 통합 테스트** — worker
  558	  spawn(§5.2)·§4 하드코딩 앵커 비교(§5.3, R-reverse가 oracle 독립 보증). 이것이 하네스 EV-L3 stage의 target
  559	  노드. (대안 A 채택 시 inside `tos/tests/staterestore/`로 `mp.get_context("spawn")` 이동 — §5.2·OQ-4.)
  560	
  561	### 8.2 비중복 매핑 (재-검증 금지)
  562	
  563	| L3 fault | 인접 L1/L2 노드 | L3 추가분 |
  564	|---|---|---|
  565	| reconstruct 순수 투영 | orthostate L1 property(reconstruct_conservative) | 재-검증 아님(기존) |
  566	| L3-01..04 재구성 | (없음/EV-L1은 in-memory) | **실 durable + 실 프로세스 경계 신규** |
  567	| L3-05/06 incomplete/stale | (없음) | **실 크래시 산물 신규** |
  568	| L3-08 durability | (없음) | **R-1 직접 방전 신규** |
  569	
  570	### 8.3 뮤테이션 canary 실효성 (플레이북 §3.8)
  571	
  572	each fault both-ways(가드 발화 ∧ 정당 통과) + §4 mutant A~E가 **outside 앵커 테스트를 FAIL(KILLED)** 실측 +
  573	등가 뮤턴트 열거. mutant는 tos.staterestore reload 경로에 주입, oracle은 outside 하드코딩 앵커(O-3)라 구현 버그
  574	독립 검출. **KILLED 실측이 OQ-2의 경험적 답**.
  575	
  576	### 8.4 게이트 실행 환경
  577	
  578	pytest = `PYTHONPATH=tos/src .venv/bin/python -m pytest`(pyenv=mypy 전용). worker도 동일 env(PYTHONPATH=
  579	tos/src). **stale-.pyc 퍼지 필수**(pycache 오염이 위양성 유발 — 누적 교훈). firewall check·full suite green
  580	재확인. rc + FAILED grep 판정.
  581	
  582	---
  583	
  584	## 9. 수용 기준 (축소된 정확한 형태 + 잔여 게이트)
  585	
  586	**L3 실행 성립 주장(PASS 아님)**: "STATE-EV-004의 EV-L3 integrated crash-restart stage가 baseline B에서
  587	결정론적으로 실행됐고, §4 카탈로그 전 crash scenario가 §5.3 독립 앵커 대비 재구성 Expected를 MET(또는
  588	DEVIATION 기록·보존)했으며, 실 on-disk sqlite3 WAL store·실 프로세스 경계(writer_pid≠reader_pid)·L1∧L2
  589	prior-stage 결속·modeled-axis residual 등재가 확인됐다. 이 run은 register row를 PASS로 이동시키지 않는다."
  590	
  591	**축별 covered 주장**:
  592	- **STATE-EV-001 R-1(durable)**: **조건부 방전(MINOR-4)** — 실 persistence+process가 durable 축 지시체를
  593	  substrate-class로 실현. R-1 register 항 "**evidence limb discharged (substrate-class); §4-decision gate +
  594	  substrate-class caveat OPEN — pending OQ-1**" 전이(무조건 "discharged" 아님). ⇒ durable 잔여는 evidence-limb
  595	  수준 해소·§4 프로젝트 결정 gate 잔존(PASS는 §9 잔여 게이트 후).
  596	- **STATE-EV-004(persistence+process+reconstruction)**: **실행**. network·credential-identity 축 **미방전**
  597	  (R-N/R-I residual) ⇒ STATE-EV-004 자체는 **PASS-부적격**(자체 EV-L3 축 미완).
  598	
  599	**PASS 전 잔여 게이트**:
  600	1. **L1∧L2 THIS baseline 재실행**: HEAD 전진으로 기존 d4160fd0 패키지 M9-stale. 최종 baseline B에서 STATE-
  601	   EV-001 **L1 → L2 → (STATE-EV-004) L3 연속 실행·중간 커밋 금지**(§11 절차).
  602	2. **restart 축 coverage argument**(VER:79): boundary leg 충족 가능; adversarial leg = **ADVERSE-SCENARIO-
  603	   SET-002-EVL3 운영자 승인 인스턴스**(EV-L2 파일럿의 EVL2-PILOT 동형·SoD reviewer≠approver:51). ADR-002-021
  604	   PROPOSED이라 하네스는 `discharged:false` 기계 유지·**리뷰층 방전**.
  605	3. **R-N/R-I residual**(§378): STATE-EV-004 자체 PASS는 network·credential 축 방전(EV-L4/+Security) 전까지
  606	   불가. Critical이라 WAIVED 불가(VER:131).
  607	4. **P0-1**: reconstruction bound-independent(§7.3)라 대부분 vacuous; null retention 키 미소비 확인.
  608	5. **독립 서명**(VER §9.5, NOT_SIGNED)+운영자 countersign. **D1 혼합 scheme**(role-scheme §1): reviewer는
  609	   저작 세션과 다른 모델 계열 우선(SPG-EV-002는 "Gemini"). 저작⊥리뷰 — 본 저작자·L3 구현자 서명 불가.
  610	6. **VER §3 complete-baseline**(:110 "as applicable" 없음): ENGINE/live 트랙 아티팩트 실체화 전까지 구조 미충족.
  611	7. **OQ-1(§4 프로젝트 persistence 결정)**: R-1 closure 충분성의 운영자 판정(파일럿-범위 vs §4 프로젝트).
  612	8. **DEVIATION run 보존**(VER §2.2): 실패 run 삭제 금지·supersedes_run_id.
  613	
  614	⇒ **acceptance = (L1∧L2∧L3 실행) ∧ R-1 방전 ∧ restart coverage(ADR-002-021 의존) ∧ P0-1 ∧ 독립 서명 ∧
  615	complete-baseline; STATE-EV-004 자체는 추가로 R-N/R-I 해소.** 파일럿은 **L3 실행 1건 + persistence 결정 + R-1
  616	방전 + residual/coverage 정직 등재**를 담당. **STATE-EV-001의 "durable 축 최초 방전"은 성립하나 그 PASS는 본
  617	파일럿 범위 밖**(잔여 6+게이트).
  618	
  619	---
  620	
  621	## 10. L3 / L4+ / residual 경계 판정 요약 (정직 이연표)
  622	
  623	| 축 | **L3 (본 파일럿)** | **이연 (residual/상위)** | 앵커 |
  624	|---|---|---|---|
  625	| real persistence | **포함** — sqlite3 WAL on-disk·크래시 생존 | (power-loss/torn-sector = R-D) | VER:153; §13:197; AC-005-1:237 |
  626	| real process boundary | **포함** — 2 OS 프로세스·os._exit·pid≠pid | — | VER:153 |
  627	| reconstruction(보수) | **포함** — POTENTIALLY_LIVE/UNKNOWN·Knowledge≠RECONCILED | — | VER:1046; §13:198-199 |
  628	| logical identity 재파생 | **포함** — intent/attempt/order 식별자 store 재파생 | — | `predicates.py:735` |
  629	| **real network** | **모델(이연)** — VirtualBroker 마커·실주문 0 | 실 broker 전송 = EV-L4/+Broker; 실선물 정책차단 | VER:153; 1045; CLAUDE.md; R-N |
  630	| **credential/service identity** | **이연** | STATE-EV-005(+Security) | VER:1050; R-I |
  631	| Recovery Barrier / 재-arm | **미포함** | ADR-002-017 별개 EV-L3 | §13:200 |
  632	| STATE-EV-002 전 conservative-direction | restart limb만 접점·미종결 | timeout/ACK/query/cache/authority 주입 | 1031 |
  633	| STATE-EV-003 coupling L3 | **미포함** | CPL/RCL 동시성 통합 | 1039 |
  634	
  635	**한 줄**: L3 = 다중 컴포넌트(CompositeState+durable store+reload+reconstruct)를 **실 sqlite 저장·실 프로세스
  636	크래시**로 통합해 보수 재구성 검증. **실 network·credential identity·Recovery Barrier·power-loss durability·
  637	STATE-EV-002/003 L3 전부 이연.** R-1(durable)은 방전, STATE-EV-004 자체 PASS는 R-N/R-I로 미완.
  638	
  639	---
  640	
  641	## 11. 판단 지점 · Open Questions · 실행 절차
  642	
  643	- **OQ-1 (최상위·§3.3)**: R-1의 "§4 persistence 결정 first" 요건 — 파일럿-범위 결정이 R-1 closure에 충분한가,
  644	  아니면 §4 프로젝트 결정(ADR acceptance 인접)이 선행인가. **권고**: (b) 파일럿-범위 sqlite로 EV-L3 evidence
  645	  limb 방전, §4 프로젝트 결정은 별개 open gate로 병기 — 단 **충분성 자체는 운영자/리뷰어 판정**(SPG coverage-
  646	  discharge 동형). **리뷰어 판정 반영(SOUND)**: (b) 권고는 :177 문자적 요건("§4 first")을 만족하지 않으므로
  647	  R-1 기록은 "**evidence limb discharged; §4 project-persistence gate + substrate-class caveat OPEN**" 형태의
  648	  이중 기록이다(무조건 "discharged" 아님). **substrate-class caveat**: evidence-limb 방전은 ACID-durability
  649	  substrate 위에서 **모델의 durable-restart 속성**을 검증한 것(substrate-class)이고, 상이한 §4 production 기술
  650	  선택(역시 ACID)은 별도 production-acceptance EV-L3 소관이지 R-1을 **소급 무효화하지 않는다** — 이 caveat가
  651	  파일럿-범위 결정을 방어 가능하게 하며 §4 gate와 R-1 evidence-limb을 분리한다.
  652	- **OQ-2 (뮤테이션 실증)**: reload-path mutant A~E가 outside 앵커 테스트를 KILLED시키는지 — 구현·실행 시 실측.
  653	  현재 미실증(설계 단계). §8.3이 의무화.
  654	- **OQ-3 (crash 모델 충실도)**: os._exit(결정론·프로세스 크래시) vs 외부 SIGKILL(racy·harder). **권고**:
  655	  결정론 os._exit를 acceptance 집합·외부 SIGKILL fuzz는 optional 하드닝(비-acceptance). power-loss는 R-D.
  656	- **OQ-4 (staterestore 배치 + spawn 메커니즘 — MAJOR-1 병합)**: (i) 신규 `tos.staterestore` 패키지 vs
  657	  orthostate 내부 모듈 — **권고**: 별도 패키지(orthostate `__init__.py:11` "no persistence" 순수성 보존). (ii)
  658	  **프로세스-경계 spawn 메커니즘**(§5.2 대안 A/B): inside `mp.get_context("spawn")`(firewall 인증·oracle 독립
  659	  관행적) vs outside subprocess(orchestration 인증 밖·oracle 독립 **구조적**) — **권고**: B(구조>convention),
  660	  단 최종 채택은 하네스 소유자(OQ-5)와 구현 확정. 최종 명명/edge allowlist는 구현 확정.
  661	- **OQ-5 (하네스 소유자)**: manifest v3 superset·STAGES 확장·outside 노드 target — 하네스 소유자 확인(L2 OQ-5
  662	  상속).
  663	- **OQ-6 (ADVERSE-SCENARIO-SET-002-EVL3 §11 그룹)**: EVL2-PILOT은 9 trading-scenario 그룹 전부 empty(순수
  664	  모델)였다. EV-L3 restart는 execution_path/venue-broker-recovery 그룹에 **모델 전송 접점**이 생긴다 — 그러나
  665	  실 broker 아니므로 여전히 "declared scope limitation"(NOT_APPLICABLE_AT_THIS_SCOPE·모델 전송 명기)로 처분할
  666	  지, 부분 populate할지 = coverage-argument 소유자 판정. **권고**: 모델 축은 empty-with-declared-reason 유지·
  667	  실 network는 R-N 명기(over-claim 금지).
  668	
  669	**실행 절차 (최종 baseline B·중간 커밋 금지)**:
  670	1. 구현: `tos.staterestore`(S-1..S-4) + outside 크래시 테스트 + 하네스 v3 확장 + self-test. firewall check green.
  671	2. baseline B(최종 HEAD)에서 **연속 실행**: STATE-EV-001 L1 → STATE-EV-001 L2 → STATE-EV-004 L3 (전부 동일
  672	   `baseline_commit_sha=B` — M9 게이트). full suite + firewall green·stale-.pyc 퍼지.
  673	3. R-1 register 항 "discharged by `<L3 run_id>`" 전이 + R-N/R-I 신규 등재(12필드·비-union) + ADVERSE-
  674	   SCENARIO-SET-002-EVL3 인스턴스(운영자 승인).
  675	4. 독립 리뷰(attempt 1-3 패턴·decorrelated 모델 계열) + 운영자 countersign(SPG-EV-002 review 체인 상속).
  676	5. push는 운영자 수동(`! git push` — 하네스 staleness 게이트는 HEAD `ee5e280d` 기준 살아있음, 메모리 기록).
  677	
  678	**잔여 판단(오케스트레이터 보고)**: (a) OQ-1 = R-1 closure 충분성(파일럿-범위 sqlite) 운영자 판정 필요 —
  679	**본 저작자 최대 미해결 쟁점**(substrate-class caveat로 방어). (b) crash 모델 = 결정론 os._exit 권고(§4·
  680	gate-clean 실측). (c) spawn 배치 = **선택**(MAJOR-1 정정) — inside mp-spawn 가능하나 **구조적 oracle 독립**을
  681	위해 outside subprocess 채택(구조>convention, §5.2). (d) 3 residual 신규(R-N/R-I/R-D)·R-1 조건부 전이·비-union.
  682	
  683	---
  684	
  685	## 12. 개정 로그
  686	
  687	- **에라타 v1.2 (2026-08-06, 구현 사이클 — 적대적 코드 리뷰 ACCEPT-WITH-MINOR 반영)** — 구현이 계약의
  688	  사실오류 2건을 적발("구현이 더 충실하면 에라타가 정답"·#36 v1.3 선례):
  689	  - **§4 CPL 절 정정**: `coupling_violations()==∅`는 Broker=UNKNOWN 셀(L3-01/02/03/05/08)에서 구조적 달성
  690	    불가(CPL-5 발화·`predicates.py:184-186`·선례 `_orthostate_strategies.py:147,167`) → **expected CPL set
  691	    pin(5셀={CPL-5}·3셀=∅) + 불일치 시 exit 70 abort**로 대체(의도 보존). "§14 미열거" 표현 정정(L3-07=
  692	    §14:211·L3-08=§14:208은 열거됨 — "all valid"=representable≠CPL-clean).
  693	  - **CPL-6 부작동 조건 sanction**: v1.1 미명세 — `authority_epoch_current=True`(authorized-send 모델)·
  694	    나머지 flag None(fail-closed) 채택.
  695	  - **§2.4 R-D 부기**: synchronous=OFF는 프로세스-크래시 모델에서 등가 뮤턴트(mutant E 실측) — 실행 증거
  696	    주장은 프로세스-크래시 durability뿐·pragma 실재는 구조 검사로 고정(리뷰 MINOR-1 하드닝 지시).
  697	  - 리뷰 판정 기록: 이탈 후보 5건 **전건 JUSTIFIED**(VIOLATION 0)·출하 fail-open 0·뮤턴트 A/D 독립 재현
  698	    KILLED·D는 "하류 보수 투영이 상류 fail-open을 가림" 결함 클래스 실증(`expect_fill_values`가 load-bearing).
  699	    이탈 (3)(4)(5)는 에라타 불요 판정(계약 위임 범위 내 완결).
  700	- **v1.1 (2026-08-06)** — 독립 비평 **REVISE**(CRITICAL 0·MAJOR 2·MINOR 4·NIT 3; phantom 0·핵심 아키텍처
  701	  건전 판정) 반영. **전 finding 1차 소스 재실측 후 반영 — 재측정 결과 리뷰어 실측과 불일치 0**(반론 없음).
  702	  - **MAJOR-1 (§5.2/§5.3)**: v1.0 전제 오류 정정 — outside 배치는 subprocess 금지 **강제가 아님**. `multiprocessing`
  703	    spawn이 firewall 허용·기실사용(`test_import_closure.py:6`·`test_evidence_import_closure.py:106`
  704	    `mp.get_context("spawn")` 실측)이라 **inside도 가능**. 대안 A(inside mp-spawn·oracle 독립 관행적)/B(outside
  705	    subprocess·oracle 독립 **구조적** R-reverse)의 명시 검토표 신설. 채택 근거를 "subprocess 금지라서" →
  706	    "**구조>convention**(플레이북 §6.1 메타②)·outside 복잡도를 지불하고 구조 독립 구매"로 재서술. §5.3 "방법론적
  707	    발견"을 트레이드오프 명시로 조정.
  708	  - **MAJOR-2 (§4/§5.1)**: crash 셀의 5차원 커밋 상태 전부 pin — v1.0의 CONFLICTED 앵커는 미결정이었음(§13:199
  709	    "UNOBSERVED/CONFLICTED 둘 다 허용"·reconstruct는 pre∈{RECONCILED,CONSISTENT}만 강등, `predicates.py:729-732,
  710	    683-685` 재측정). 앵커 = 다운그레이드/보존 맵 결정론 값 + 2층 독립 불변식 `K∉{RECONCILED,CONSISTENT}`. §5.1
  711	    S-2에 부재 Knowledge→UNOBSERVED 채움 규약을 §13:199에서 논증. ④ "L3-08 직접 R-1 방전" → "durability 메커니즘
  712	    셀; R-1 방전 = composite 경계집합 durability 속성 + coverage argument(§9 게이트 2)"로 정밀화.
  713	  - **MINOR-1 (§5.2/§8.1)**: "firewall 밖 ⇒ 미적용" 정밀화 — `_REVERSE_SCAN_PRUNE`(`tos_firewall_check.py:114-116`)에
  714	    `tests` 부재 실측 ⇒ forward(a-d) 미적용(subprocess 허용)·**reverse(e) 적용**(O-3 구조 독립의 근거).
  715	  - **MINOR-2 (§6.2 게이트 #4)**: `evidence_id==STATE-EV-001` 결속 추가(STATE-EV-003도 EV-L1/3 READY·오충족 차단)
  716	    + "prior L1∧L2는 STATE-EV-004 자체 요건 아니라 STATE-EV-001 durable-limb 연속성" 명시.
  717	  - **MINOR-3 (§5.1/§7.4)**: tos-wide 비-transmitting 불변식(`tos/__init__.py:6`) canary 추가·staterestore가
  718	    로컬 persistence(disk)만·egress 0 보존 못 박음(persistence≠transmission).
  719	  - **MINOR-4 (§7.1/§9/OQ-1)**: 무조건 "discharged" → **OQ-1 조건부 이중 기록** + substrate-class caveat(ACID
  720	    substrate class 검증·§4 production 기술 변경은 R-1 소급 무효화 아님).
  721	  - **NIT-1** manifest v3 네임스페이스 주의(vs `_VER3_FIELDS`=VER §3)·**NIT-2** 게이트 개명 `PRIOR_EV_L1_AND_L2_
  722	    NOT_BOTH_BOUND_AT_THIS_BASELINE`·**NIT-3** B_stale_epoch_reject "보수 방향만 정합"(epoch fencing≠cache 폐기).
  723	  - **OQ-4**에 MAJOR-1 spawn 메커니즘 질문 병합. 리뷰어 OQ 판정(OQ-1 fail-closed 이중기록 SOUND·substrate-class
  724	    caveat) 반영.
  725	- **비준 (2026-08-06)** — 델타 재검증(동일 독립 리뷰어·연속 컨텍스트) **RATIFY-READY**: MAJOR 2건 FULLY
  726	  RESOLVED(대안표 역-비용 명시·8셀 전수 결정론 재파생 확인, L3-07 §14:211/L3-08 §14:208 verbatim 합법·L3-08
  727	  fixpoint 분리검증)·MINOR/NIT 전건 문구 정합·신규 앵커 phantom 0·부작용 0(§2.3 byte-동일·정책 온존). 비차단
  728	  관찰 1건(pin 커밋 composite의 §14 미열거 조합 CPL 합법성) → §4 "커밋 composite CPL 합법성" 절로 반영
  729	  (오케스트레이터 직접·기계적 정정 선례 #20/#23). 자동비준 위임에 따라 비준 기록. 실행 잔여 인간 게이트:
  730	  OQ-1 R-1 closure 충분성·ADVERSE-SCENARIO-SET-002-EVL3 인스턴스 승인·countersign(§9·§11).
  731	- **v1.0 (2026-08-06)** — 저작 초안. EV-L2 파일럿(v1.2)·방법론 플레이북(§0/부록 B/D/§5)·VER §5·STATE-EV-004
  732	  (1041-1046)·ADR-002-005 §13(195-200)·§4(61)·AC-005-4(240)·reconstruct_conservative(688-742)·firewall
  733	  (186-192)·PROFILE(null 17·MIN_evidence_retention_ms:923)·countersign(R-1:39-40)·RESIDUAL-RISK-REGISTER-002
  734	  (R-1)·ADVERSE-SCENARIO-SET-002-EVL2-PILOT·role-scheme §1 전부 1차 소스 실측 후 작성. 핵심 판정: 열린-세계
  735	  전이(시리즈 최초 실 I/O)·EV-L3 축 분할(persistence+process 실행·network/identity 이연)·firewall
  736	  subprocess 금지 → outside spawn + oracle 독립(R-reverse)·pilot-scope persistence(OQ-1)·R-1 방전 vs
  737	  STATE-EV-004 자체 PASS-부적격 비대칭. 독립 비평 리뷰 대기.
  738	
  739	---
  740	
  741	## 부록 A. 실측 인용 대장 (anti-phantom — file:line)
  742	
  743	**VER-002-001**: EV-L1 143-145·EV-L2 147-149·**EV-L3 151-153**·EV-L4 155-157·EV-L5 159-161·composite notation
  744	167-176(staged 172-173)·**§2.7 coverage 79**·complete-baseline 110·WAIVED 금지 **131**(enum 값 128)·bounded-
  745	model 3171·**§378 register 3292-3310**(non-union 3308·broker-limitation 3310)·§379 checklist 3315-3345(restart
  746	limbs 3327-3328)·**STATE-EV-001 1020-1025**(min 1022·sup AC-005-1 1023·inj 1024·exp 1025)·STATE-EV-002 1027-
  747	1032(min EV-L2/3 1029·inj restart 1031)·STATE-EV-003 1034-1039(min EV-L1/3 1036·exp CPL 1039)·**STATE-EV-004
  748	1041-1046**(min EV-L3 1043·sup AC-005-4 1044·inj 1045·exp 1046)·STATE-EV-005 1048-1053(min EV-L2/3+Security
  749	1050)·1 PASS(SPG-EV-002) 6·292/79/1.
  750	
  751	**ADR-002-005**: §4 "does not decide the persistence technology" **61**·§6 SEND_STARTED durable before external
  752	call 96·**§13 Persistence and Restart 195-200**(durable+reconstructable **197**·restart POTENTIALLY_LIVE/
  753	UNKNOWN 198·Knowledge never RECONCILED **199**·Recovery Barrier/re-arm **200**)·§14 composite 204-212·AC-005-1
  754	"representable and persisted" **237**·**AC-005-4 restart 240**·§19 "restart reconstructs … in tests" 271.
  755	
  756	**reconstruct_conservative** (`tos/src/tos/orthostate/predicates.py`): def **688-742**·docstring "durable
  757	reload / crash recovery … EV-L3" **692**·codomain "structurally excludes RECONCILED" **700-702**·intent_identity
  758	보존 735·_ATTEMPT_POTENTIALLY_LIVE_AFTER_RESTART 659-668·_BROKER_STRUCTURALLY_TERMINAL 672-679·**_KNOWLEDGE_
  759	DOWNGRADE_ON_RESTART={RECONCILED,CONSISTENT} 683-685**·**Knowledge 강등/보존 분기 729-732**(pre∈set→CONFLICTED·
  760	else 보존, MAJOR-2)·capacity 상향 714-719·may_transition send-boundary 594-650. **orthostate __init__**: "no persistence /
  761	durable restart" 11·"pending EV-L2/L3 … durable persistence … real restart" 38-39·reconstruct export 68/114.
  762	
  763	**register CSV** (`EVIDENCE-REGISTER-002.csv`): header 1·STATE-EV-001 **91**(EV-L1/2 READY)·STATE-EV-002 92
  764	(EV-L2/3 NOT_IMPL)·STATE-EV-003 93(EV-L1/3 READY)·**STATE-EV-004 94**(EV-L3 NOT_IMPL·broker TBD)·STATE-EV-005
  765	95(EV-L2/3+Security NOT_IMPL).
  766	
  767	**firewall** (`2026-07-20-tos-boundary-and-import-firewall-design.md`): 허용목록 **186**(stdlib 전체·금지 11:
  768	socket/ssl/http/urllib.request/ftplib/smtplib/poplib/imaplib/telnetlib/**subprocess**/ctypes·**multiprocessing
  769	부재=허용**)·서드파티 187(pydantic/numpy/pandas/pytest/hypothesis/pyyaml·DB 없음)·**R-reverse 192**·scope
  770	src+tests 166-167·AST 게이트 `tools/tos_firewall_check.py` 203-207. **firewall check 내부(v1.1 신규)**: os
  771	검출 = environ/getenv만(**214-216 from-import·237-240 attr**; os._exit 미검출)·**_REVERSE_SCAN_PRUNE 114-116**
  772	(`{tos,.git,.venv,node_modules,__pycache__,.omc,.history}` — **tests 부재**)·check_reverse_imports 306·reverse
  773	line RE 120. **multiprocessing 기실사용(MAJOR-1)**: `tos/tests/test_import_closure.py:6`("fresh, isolated
  774	interpreter (via `multiprocessing` spawn — `subprocess` and `os` are firewall-forbidden even in tests)")·:30
  775	`import multiprocessing as mp`·`tos/tests/test_evidence_import_closure.py:106` `mp.get_context("spawn")`.
  776	**tos-wide 불변식**: `tos/src/tos/__init__.py:6` "non-transmitting by construction (§4)".
  777	
  778	**harness** (`tools/tos_evidence_run.py`): EV-L1/L2 header 2·never PASS 26·STAGE_L1/L2 129-130·STAGES 131·
  779	is_l2 1902·build_baseline stage/schema 1231/1299/1327·**L2 게이트 2130-2149**(NO_PRIOR_EV_L1 2147)·manifest
  780	v2/v1 2164·coverage_argument 2236-2258(discharged false 2248)·DISCIPLINE_TAG_L2 124·bind_prior_stage_run 903
  781	(baseline_matches M9 920)·summarise_fault_schedule 786-889·check_l1_hardening 689·build_parser 1773(--evidence-
  782	level-stage choices=STAGES 1820-1822·--covered-axis 1858·--residual-ref 1876·--prior-stage-run 1838). self-test
  783	`tests/tools/test_tos_evidence_run.py`(1744행·discipline tag 389-391·no-PASS 395-401·ver3 baseline 340·
  784	**`_VER3_FIELDS`=VER §3 22필드 293**[NIT-1 명명 충돌원]).
  785	
  786	**PROFILE** (`VERIFICATION-PROFILE-002.yaml`): status APPROVED scope-limited 1-8·17 null fail-closed 6-8/30-31·
  787	scope.environment non-live-test "EV-L1..L3 harness" 35/59·**MIN_evidence_retention_ms null 923**·B_stale_epoch_
  788	reject 0 approved 228-232.
  789	
  790	**residual/coverage/role**: RESIDUAL-RISK-REGISTER-002.yaml R-1(required_scope_reduction "§4 first … EV-L3 run
  791	discharges" **177**·"cite STATE-EV-004 … real persistence substrate" 176·VER:131 unwaivable 149·detection
  792	NOT_ESTABLISHED 153·owner/approver operator 161-165). SPG-EV-002 countersign(R-1 blocks STATE-EV-001 PASS 39-40·
  793	SPG PASS first 31-33·coverage via ASS-EVL2-PILOT 25·P0-1 within 146 26). ADVERSE-SCENARIO-SET-002-EVL2-PILOT
  794	(consumer 2 rows·§11 9 groups empty 90-147·ASS-CM-04 guards-are-oracles 590-597·SoD reviewer≠approver 51·
  795	self_referentiality_caveat 158). role-scheme §1(D1 mixed·operator=owner/approver·reviewer diff model family·
  796	Live-Armer unassigned·reviewer≠approver). gate-status(292/79/1 7·EV-L2/L3 ceilings 822).
  797	
  798	**부재 (negative-grep)**: (1) `STAGE_L3`/`EV_L3`/`is_l3`/`manifest/v3` in `tos_evidence_run.py` = 0. (2) sqlite3/
  799	fsync/실 파일쓰기 in `tos/src` = 0(sir `_member_is_open` 오탐뿐). (3) `tos-evidence/STATE-EV-004/` 디렉토리 =
  800	0(EV-L3 run 미실행). (4) STATE-EV-004 Expected(1046) ms/duration/retention/threshold 토큰 = 0(bound-
  801	independent). (5) `subprocess` in firewall 허용목록 = 0(금지 11에 포함). (6) **`multiprocessing` in firewall
  802	금지목록 = 0 ⇒ 허용**(MAJOR-1·기실사용 `test_import_closure.py:6`). (7) `_REVERSE_SCAN_PRUNE`에 `tests` = 0
  803	(reverse 규칙이 repo-root `tests/`에 적용 — O-3 근거, MINOR-1).
  804	
  805	**플레이북**: 저작자 절 27·부록 B §0.5 13항 531·부록 D 극성 600·**§5 열린-세계 전이 423-447**(닫힌→열린 428·
  806	새 레인 442·배선 fail-open 436·결정론 canary 437)·§3.8 뮤테이션 KILLED 388. **EV-L2 파일럿**: C1 durable 판정
  807	§2.2·R-1 residual §9·축 분할 대안 A/B/C §2.3·L1 하드닝 위치 §5.
  808	
```

---- SOURCE tos-spec/src/part-1-foundation/verification/ADVERSE-SCENARIO-SET-002-EVL3-PILOT.yaml (full) ----
```
    1	# ADVERSE-SCENARIO-SET-002-EVL3-PILOT — PROPOSED (pre-execution; operator approval pending)
    2	#
    3	# WHAT THIS IS
    4	#   An Adverse Scenario Set INSTANCE created for exactly one purpose: the
    5	#   VER-002-001 §2.7 (line 79) coverage argument's ADVERSARIAL-COMBINATION leg
    6	#   for the RESTART axis of the EV-L3 pilot (STATE-EV-004 "Conservative Restart
    7	#   Reconstruction"). §2.7 requires, at minimum, "the boundary values of each
    8	#   governed dimension and the adversarial combinations of the approved Adverse
    9	#   Scenario Set (ADR-002-021)". This file supplies that second leg for the
   10	#   restart axis and nothing else. It is the sibling of
   11	#   ADVERSE-SCENARIO-SET-002-EVL2-PILOT.yaml and inherits its structure
   12	#   homomorphically (§11 groups, SoD, self_referentiality_caveat, consumer rows,
   13	#   empty-with-declared-reason pattern).
   14	#
   15	# WHAT IS DIFFERENT FROM THE EV-L2 SIBLING (two structural differences)
   16	#   1. PRE-EXECUTION. The EV-L2 instance was authored AFTER its faults executed,
   17	#      so its scenarios carried `outcome: MET` and pointed to landed run
   18	#      packages. This EV-L3 instance is authored from the RATIFIED DESIGN CATALOG
   19	#      (docs/plans/2026-08-06-tos-ev-l3-pilot-design.md §4, design #39, ratified
   20	#      commit 2b455dd9) BEFORE the STATE-EV-004 EV-L3 run executes. Every
   21	#      scenario therefore carries `outcome: PENDING_EXECUTION` and
   22	#      `observed: <runtime-observed — run not yet executed>`. It SPECIFIES the
   23	#      adverse set the run must cover; it records no observation it does not have
   24	#      (VER §2.2 negative-results discipline; no fabricated observation).
   25	#   2. TWO §11 GROUPS ARE POPULATED (restart-reconstruction contact only). The
   26	#      EV-L2 instance kept all nine ADR-002-021 §11 trading-scenario groups empty
   27	#      (pure model, no execution path). At EV-L3 the restart pilot genuinely
   28	#      reaches two of them — `execution_path_scenarios` (§11 lines 293-294:
   29	#      missing acknowledgement, receipt ambiguity, position-effect) and
   30	#      `venue_broker_partition_and_recovery_scenarios` (§11 line 299: recovery
   31	#      uncertainty). Those two are POPULATED with pointer entries bound 1:1 to the
   32	#      §4 catalogue's eight crash cells. The other seven groups stay empty with a
   33	#      declared reason. See OQ-6 disposition below.
   34	#
   35	# OQ-6 DISPOSITION (ratified SOUND; design §11 OQ-6; over-claim forbidden)
   36	#   The two populated groups carry ONLY the restart-reconstruction sub-axis, not
   37	#   full trading-scenario coverage. Each populated entry declares
   38	#   `full_trading_scenario_coverage: NOT_CLAIMED`, `modeled_transmission: true`
   39	#   (the crash-point transmission is a capability-class VirtualBroker marker, not
   40	#   a real broker send — design §0, §2.4), and `real_network_sub_axis:
   41	#   DEFERRED_R_N`. The real broker-network / real partition sub-axis is a
   42	#   declared residual (R-N), never silently covered.
   43	#     `adr_002_021_section_11_full_coverage: NOT_MET` (seven empty + two
   44	#     restart-reconstruction-only).
   45	#
   46	# WHAT THIS IS NOT
   47	#   - It is NOT an ADR-002-021 §5.4 (line 127) Adverse Scenario Set in the full
   48	#     sense. §5.4 defines a "policy-bound set ... used to establish maximum
   49	#     credible effects"; no Aggregate Risk Policy exists (ADR-002-021 §28
   50	#     question 1, line 698, is open), so `aggregate_risk_policy_id` is null and
   51	#     this set is NOT policy-bound. It establishes no maximum credible economic
   52	#     effect and SHALL NOT be consumed by any aggregate-risk evaluation.
   53	#   - It does NOT satisfy ADR-002-021 §11 (lines 289-299) full coverage: seven of
   54	#     the nine mandated groups are empty and the two populated ones carry the
   55	#     restart-reconstruction sub-axis only.
   56	#   - Approving this instance does NOT accept ADR-002-021. That ADR stays
   57	#     `Proposed` (ADR-002-021 §29 line 719) and its §29 Approval Gate
   58	#     (lines 717-735) is untouched. An instance approval is not an ADR acceptance.
   59	#   - It moves no EVIDENCE-REGISTER-002 row to PASS. STATE-EV-004 stays
   60	#     NOT_IMPLEMENTED and STATE-EV-001 stays READY; the other §9 gates of the
   61	#     EV-L3 pilot design (independent review signature, VER §3 complete baseline,
   62	#     R-N/R-I residuals, OQ-1 §4-persistence adjudication) remain open
   63	#     independently of this file.
   64	#
   65	# SHAPE DEVIATIONS FROM ADVERSE-SCENARIO-SET-template.yaml (declared, additive)
   66	#   1. `result` carries `PROPOSED_PENDING_EXECUTION_AND_APPROVAL`. The template
   67	#      ships `result: INVALID` beside `status: DRAFT`. Plain `INVALID` would not
   68	#      convey that the set is ratified-design-derived and awaiting a run; the
   69	#      extended value states both facts (proposed, and pending execution +
   70	#      operator approval).
   71	#   2. Additive fields mirroring the EV-L2 sibling plus EV-L3-specific ones:
   72	#      `adr_002_021_section_11_full_coverage`, `unpopulated_trading_scenario_groups`,
   73	#      `ev_l3_pilot_coverage_scenarios`, `authorization_notice`, and the per-entry
   74	#      `restart_reconstruction_sub_axis` / `modeled_transmission` /
   75	#      `real_network_sub_axis` / `full_trading_scenario_coverage` /
   76	#      `outcome: PENDING_EXECUTION` fields.
   77	#   3. `canonical_digest`, `aggregate_risk_policy_id`, `aggregate_risk_generation`
   78	#      are null rather than `TBD`: the referents do not exist. A null digest is
   79	#      not a digest — see `authorization_notice`.
   80	#   4. `approved_by: []` and `effective_from`/`review_due: null`: this instance is
   81	#      PROPOSED, not APPROVED. Operator approval is a human gate (see APPROVAL
   82	#      RECORD).
   83	#
   84	# APPROVAL RECORD (PENDING — human gate)
   85	#   Status PROPOSED. approved_by is empty. The ADR-002 series delegated
   86	#   auto-ratification (operator 2026-07-25, extended 2026-07-29) applies to the
   87	#   DESIGN CONTRACT ratification only (design #39, commit 2b455dd9). Approval of
   88	#   THIS scenario-set instance is a SEPARATE operator human gate, deliberately
   89	#   left unsigned. When approved, the approver identity `operator` = the D1 role
   90	#   scheme System owner / Bounds-Approver (docs/plans/2026-07-29-tos-phase0-role-
   91	#   scheme-and-disposition.md §1). Separation of duties (VER-002-001 §2.6 line 75:
   92	#   Critical evidence "SHALL be reviewed by a principal who did not implement the
   93	#   tested mechanism and did not approve the relevant residual-risk exception"):
   94	#   the approving identity SHALL NOT be the independent reviewer of the pilot
   95	#   evidence, and SHALL NOT also arm live trading (Live-Armer unassigned).
   96	
   97	artifact_type: ADVERSE_SCENARIO_SET
   98	schema_version: "1.0-DRAFT"
   99	scenario_set_id: ADVERSE-SCENARIO-SET-002-EVL3-PILOT
  100	scenario_set_version: "1.0"
  101	aggregate_risk_generation: null      # no Aggregate Risk Generation exists
  102	canonical_digest: null               # no approved canonicalization scheme for spec-layer YAML
  103	status: PROPOSED
  104	result: PROPOSED_PENDING_EXECUTION_AND_APPROVAL
  105	aggregate_risk_policy_id: null       # no Aggregate Risk Policy exists (ADR-002-021 §28 Q1, line 698, open)
  106	
  107	scope:
  108	  - kind: consumer
  109	    value: "VER-002-001 §2.7 (line 79) coverage argument, adversarial-combination leg, RESTART axis"
  110	    detail: >-
  111	      Consumable by exactly two evidence rows. PRIMARY consumer: STATE-EV-004
  112	      (Conservative Restart Reconstruction, minimum level EV-L3, VER:1043;
  113	      Supports ADR-002-005 AC-005-4, VER:1044). SECONDARY consumer: STATE-EV-001
  114	      (Orthogonal Composite Persistence, minimum level EV-L1/EV-L2, VER:1022) for
  115	      the R-1 durable-limb discharge only — the crash-restart run's durability
  116	      property (design §7.1, §9). Any other consumer is out of scope.
  117	  - kind: environment
  118	    value: non-live-test
  119	    detail: >-
  120	      No real broker session, no account, no instrument, no live authorization,
  121	      and ZERO real broker orders. The "after network transmission" crash point
  122	      (STATE-EV-004 Injection, VER:1045) is realized by a modeled capability-class
  123	      VirtualBroker marker (design §0, §2.4). Real persistence (on-disk sqlite3
  124	      WAL) and a real OS process boundary ARE used (design §2, §3). Consistent
  125	      with VERIFICATION-PROFILE-002.yaml scope.environment (line 59), which
  126	      declares these EV-L1..L3 harness ceilings non-live-test.
  127	  - kind: evidence_baseline
  128	    value: "PENDING — STATE-EV-004 EV-L3 run not yet executed"
  129	    detail: >-
  130	      This instance is authored from the ratified design catalogue (docs/plans/
  131	      2026-08-06-tos-ev-l3-pilot-design.md §4, design #39, ratified commit
  132	      2b455dd9) BEFORE the run. Each scenario's evidence baseline is the future
  133	      STATE-EV-004 EV-L3 run's baseline; it does not exist yet. `outcome` is
  134	      PENDING_EXECUTION for every scenario and no observation is recorded that was
  135	      not made (VER §2.2).
  136	  - kind: exclusion
  137	    value: aggregate-risk evaluation
  138	    detail: >-
  139	      SHALL NOT be used as the Adverse Scenario Set of an Aggregate Risk Decision,
  140	      a Projected Aggregate State, or an Adverse Increment Vector (ADR-002-021 §1
  141	      line 15, §12 lines 309-330). It proves no maximum credible effect for any
  142	      trading action.
  143	
  144	# --- ADR-002-021 §11 (lines 289-299) mandated trading-scenario groups ----------
  145	# Template shape preserved (each stays a list). TWO groups are populated with
  146	# restart-reconstruction pointer entries (bound 1:1 to the design §4 catalogue's
  147	# eight crash cells); the other seven stay empty. Full scenario detail lives in
  148	# `ev_l3_pilot_coverage_scenarios`; these pointers carry the ADR-group binding and
  149	# the over-claim guards (sub-axis, modeled transmission, R-N deferral).
  150	
  151	execution_path_scenarios:
  152	  # ADR-002-021 §11 lines 293-294 (missing acknowledgement, broker receipt
  153	  # ambiguity, zero crossing, reversal, reduce-only failure, position-effect
  154	  # mismatch). Restart-reconstruction contact only.
  155	  - coverage_scenario_ref: ASS-EVL3-B-01
  156	    design_cell: "L3-01"
  157	    ad_002_021_facet: "broker receipt ambiguity (§11 line 293)"
  158	    restart_reconstruction_sub_axis: "crash after durable SEND_STARTED, before broker receipt"
  159	    modeled_transmission: true
  160	    real_network_sub_axis: DEFERRED_R_N
  161	    full_trading_scenario_coverage: NOT_CLAIMED
  162	  - coverage_scenario_ref: ASS-EVL3-B-02
  163	    design_cell: "L3-02"
  164	    ad_002_021_facet: "broker receipt ambiguity (§11 line 293)"
  165	    restart_reconstruction_sub_axis: "crash after modeled network transmission (SENT_UNCONFIRMED)"
  166	    modeled_transmission: true
  167	    real_network_sub_axis: DEFERRED_R_N
  168	    full_trading_scenario_coverage: NOT_CLAIMED
  169	  - coverage_scenario_ref: ASS-EVL3-C-01
  170	    design_cell: "L3-03"
  171	    ad_002_021_facet: "missing acknowledgement (§11 line 293)"
  172	    restart_reconstruction_sub_axis: "crash before evidence persistence; in-memory positive knowledge lost"
  173	    modeled_transmission: true
  174	    real_network_sub_axis: DEFERRED_R_N
  175	    full_trading_scenario_coverage: NOT_CLAIMED
  176	  - coverage_scenario_ref: ASS-EVL3-B-03
  177	    design_cell: "L3-04"
  178	    ad_002_021_facet: "position-effect mismatch / order-state ambiguity (§11 line 294)"
  179	    restart_reconstruction_sub_axis: "crash at non-terminal broker-order boundary (reconstruct broker as UNKNOWN)"
  180	    modeled_transmission: true
  181	    real_network_sub_axis: DEFERRED_R_N
  182	    full_trading_scenario_coverage: NOT_CLAIMED
  183	  - coverage_scenario_ref: ASS-EVL3-C-04
  184	    design_cell: "L3-07"
  185	    ad_002_021_facet: "position-effect known, knowledge must re-derive (§11 line 294)"
  186	    restart_reconstruction_sub_axis: "terminal broker FILLED preserved; positive Knowledge downgraded on restart"
  187	    modeled_transmission: true
  188	    real_network_sub_axis: DEFERRED_R_N
  189	    full_trading_scenario_coverage: NOT_CLAIMED
  190	
  191	partial_fill_and_ordering_scenarios: []
  192	cancel_amend_replace_retry_and_overlap_scenarios: []
  193	price_slippage_gap_volatility_and_liquidity_scenarios: []
  194	correlation_basis_and_hedge_failure_scenarios: []
  195	margin_collateral_borrow_and_currency_scenarios: []
  196	exercise_assignment_delivery_and_settlement_scenarios: []
  197	external_trapped_non_trade_and_concurrent_scenarios: []
  198	
  199	venue_broker_partition_and_recovery_scenarios:
  200	  # ADR-002-021 §11 line 299 (unavailable exit/protection, rate-limit saturation,
  201	  # broker/session restriction, partition, and RECOVERY uncertainty). Only the
  202	  # recovery (restart-reconstruction) sub-axis; real partition is DEFERRED_R_N.
  203	  - coverage_scenario_ref: ASS-EVL3-C-02
  204	    design_cell: "L3-05"
  205	    ad_002_021_facet: "recovery uncertainty (§11 line 299)"
  206	    restart_reconstruction_sub_axis: "recovery from an incomplete store (inter-transaction crash; partial dimensions)"
  207	    modeled_transmission: true
  208	    real_network_sub_axis: DEFERRED_R_N
  209	    full_trading_scenario_coverage: NOT_CLAIMED
  210	  - coverage_scenario_ref: ASS-EVL3-C-03
  211	    design_cell: "L3-06"
  212	    ad_002_021_facet: "recovery uncertainty (§11 line 299)"
  213	    restart_reconstruction_sub_axis: "recovery discarding a stale optimistic cache; re-derive from store"
  214	    modeled_transmission: true
  215	    real_network_sub_axis: DEFERRED_R_N
  216	    full_trading_scenario_coverage: NOT_CLAIMED
  217	  - coverage_scenario_ref: ASS-EVL3-B-04
  218	    design_cell: "L3-08"
  219	    ad_002_021_facet: "recovery reload fidelity / durability (§11 line 299)"
  220	    restart_reconstruction_sub_axis: "durability positive canary: commit -> crash -> lossless reload"
  221	    modeled_transmission: false
  222	    real_network_sub_axis: NOT_APPLICABLE
  223	    full_trading_scenario_coverage: NOT_CLAIMED
  224	
  225	adr_002_021_section_11_full_coverage: NOT_MET
  226	
  227	unpopulated_trading_scenario_groups:
  228	  common_reason: >-
  229	    The declared scope has no fill, no cancel/amend, no price/slippage, no
  230	    correlation/hedge, no margin/settlement, and no external trade activity: the
  231	    restart pilot crashes a persisted state and reconstructs it conservatively;
  232	    it executes no trade. Populating these groups would require inventing
  233	    scenarios with no executed referent, which the pilot design forbids (design
  234	    §0.5-4). Emptiness here is a declared scope limitation, NOT a dominance proof
  235	    and NOT a claim the omitted paths are harmless (ADR-002-021 §11 line 301:
  236	    "Scenario reduction or pruning SHALL be policy-governed and prove dominance").
  237	  populated_groups_caveat: >-
  238	    execution_path_scenarios and venue_broker_partition_and_recovery_scenarios are
  239	    populated with the restart-reconstruction sub-axis ONLY. They do NOT establish
  240	    full ADR-002-021 §11 coverage of those groups: the real broker-network / real
  241	    partition sub-axis is deferred (R-N), and no fill/price/margin facet is
  242	    exercised. `full_trading_scenario_coverage: NOT_CLAIMED` on every populated
  243	    entry.
  244	  groups:
  245	    - group: partial_fill_and_ordering_scenarios
  246	      adr_anchor: "ADR-002-021 §11 line 291 (fill prefixes, out-of-order fill sequence)"
  247	      disposition: NOT_APPLICABLE_AT_THIS_SCOPE
  248	    - group: cancel_amend_replace_retry_and_overlap_scenarios
  249	      adr_anchor: "ADR-002-021 §11 line 292 (original, cancel, amend, replace, split-child, retry overlap)"
  250	      disposition: NOT_APPLICABLE_AT_THIS_SCOPE
  251	    - group: price_slippage_gap_volatility_and_liquidity_scenarios
  252	      adr_anchor: "ADR-002-021 §11 line 295"
  253	      disposition: NOT_APPLICABLE_AT_THIS_SCOPE
  254	    - group: correlation_basis_and_hedge_failure_scenarios
  255	      adr_anchor: "ADR-002-021 §11 line 296"
  256	      disposition: NOT_APPLICABLE_AT_THIS_SCOPE
  257	    - group: margin_collateral_borrow_and_currency_scenarios
  258	      adr_anchor: "ADR-002-021 §11 line 297"
  259	      disposition: NOT_APPLICABLE_AT_THIS_SCOPE
  260	    - group: exercise_assignment_delivery_and_settlement_scenarios
  261	      adr_anchor: "ADR-002-021 §11 line 297"
  262	      disposition: NOT_APPLICABLE_AT_THIS_SCOPE
  263	    - group: external_trapped_non_trade_and_concurrent_scenarios
  264	      adr_anchor: "ADR-002-021 §11 line 298"
  265	      disposition: NOT_APPLICABLE_AT_THIS_SCOPE
  266	  partially_populated_groups:
  267	    - group: execution_path_scenarios
  268	      adr_anchor: "ADR-002-021 §11 lines 293-294"
  269	      disposition: PARTIALLY_POPULATED_RESTART_RECONSTRUCTION_ONLY
  270	      deferred_sub_axis: "real broker-network receipt (R-N)"
  271	    - group: venue_broker_partition_and_recovery_scenarios
  272	      adr_anchor: "ADR-002-021 §11 line 299"
  273	      disposition: PARTIALLY_POPULATED_RECOVERY_SUB_AXIS_ONLY
  274	      deferred_sub_axis: "real broker/session partition (R-N)"
  275	
  276	# --- The scenarios this set actually carries -----------------------------------
  277	# Derivation rule: every entry below corresponds 1:1 to a crash cell in the
  278	# ratified design §4 catalogue (docs/plans/2026-08-06-tos-ev-l3-pilot-design.md).
  279	# No entry is hypothetical, and no entry is observed: the run has not executed.
  280	# Classification rule: an entry is an ADVERSARIAL COMBINATION when the crash holds
  281	# two or more factors simultaneously; otherwise it is a single-factor BOUNDARY
  282	# VALUE of one governed dimension's crash boundary.
  283	ev_l3_pilot_coverage_scenarios:
  284	  self_referentiality_caveat: >-
  285	    This set is derived from the ratified design catalogue, so by construction it
  286	    cannot reveal a crash scenario the catalogue missed. It argues coverage of the
  287	    declared restart axis only. It is authored PRE-EXECUTION: it specifies the
  288	    adverse set the STATE-EV-004 EV-L3 run must cover and records no observed
  289	    disposition (all `outcome: PENDING_EXECUTION`). Axes outside it are recorded
  290	    under `dominance_and_pruning_proofs`, `unbounded_credible_effects`, or the
  291	    residual references — never as silently covered.
  292	
  293	  oracle_independence_note: >-
  294	    The design places the Expected reconstruction as a hand-derived hardcoded
  295	    anchor in an outside test that structurally cannot `import tos` (firewall
  296	    reverse rule; design §5.3, O-3). So unlike the EV-L2 sibling's ASS-CM-04
  297	    ("guards under test are also the oracles"), each Expected here is NOT the
  298	    implementation's own `reconstruct_conservative` output. This structurally
  299	    offsets — it does not fully remove — the guard-is-oracle common mode (see
  300	    common_mode_dependencies ASS-CM-04).
  301	
  302	  committed_composite_cpl_legality: >-
  303	    The pinned committed composites for L3-01..L3-06 are not all in ADR-002-005
  304	    §14's enumerated examples. Per the ratified design §4 "committed composite CPL
  305	    legality" clause (delta-review observation), the run SHALL confirm
  306	    coupling_violations() == empty on each pinned committed composite before the
  307	    crash, so a CPL-illegal committed state fails loudly at construction rather
  308	    than silently seeding a defect.
  309	
  310	  governed_dimensions:
  311	    referent: "tos.orthostate.records.CompositeState (tos/src/tos/orthostate/records.py:39-102); projection tos.orthostate.predicates.reconstruct_conservative (predicates.py:688-742)"
  312	    dimensions:
  313	      - name: intent_state
  314	        directly_exercised: false
  315	        disposition: "preserved across restart (intent_identity carried, predicates.py:735); structural-identity argument, not a mutated dimension (see ASS-DOM-05)"
  316	      - name: transmission_attempt_state
  317	        directly_exercised: true
  318	        cells: ["L3-01 (SEND_STARTED)", "L3-02 (SENT_UNCONFIRMED)", "L3-07 (ACK_OBSERVED)"]
  319	      - name: broker_order_state
  320	        directly_exercised: true
  321	        cells: ["L3-04 (non-terminal -> UNKNOWN)", "L3-07 (FILLED preserved)"]
  322	      - name: knowledge_state
  323	        directly_exercised: true
  324	        cells: ["L3-03 (UNOBSERVED preserved)", "L3-06 (stale RECONCILED ignored)", "L3-07 (RECONCILED/CONSISTENT -> CONFLICTED)"]
  325	      - name: capacity_state
  326	        directly_exercised: true
  327	        cells: ["L3-01 / L3-02 (raised to at least POTENTIALLY_LIVE via CPL-1, predicates.py:714-719)"]
  328	    directly_exercised_ratio: "4 of the 5 ADR-002-005 §14 dimensions (intent_state via preservation argument)"
  329	
  330	  boundary_value_scenarios:
  331	    - scenario_id: ASS-EVL3-B-01
  332	      row: STATE-EV-004
  333	      design_cell: L3-01
  334	      governed_dimension: transmission_attempt_state
  335	      committed_5tuple: "Intent=ACTIVE Attempt=SEND_STARTED Broker=UNKNOWN Knowledge=UNOBSERVED Capacity=POTENTIALLY_LIVE"
  336	      crash_boundary: "after durable SEND_STARTED, before broker receipt"
  337	      expected: "Attempt=SEND_STARTED; Broker=UNKNOWN; Knowledge=UNOBSERVED (preserved, not in downgrade set); Capacity>=POTENTIALLY_LIVE"
  338	      two_layer_invariant: "Knowledge NOT IN {RECONCILED, CONSISTENT} AND Capacity at-least-as-conservative-as POTENTIALLY_LIVE AND Broker=UNKNOWN"
  339	      observed: "<runtime-observed — STATE-EV-004 EV-L3 run not yet executed>"
  340	      outcome: PENDING_EXECUTION
  341	      normative_anchor: "ADR-002-005 §13 line 198; predicates.py:659-668, 715-719, 731-732"
  342	      evidence_ref: "docs/plans/2026-08-06-tos-ev-l3-pilot-design.md §4 row L3-01; run package <pending>"
  343	    - scenario_id: ASS-EVL3-B-02
  344	      row: STATE-EV-004
  345	      design_cell: L3-02
  346	      governed_dimension: transmission_attempt_state
  347	      committed_5tuple: "Intent=ACTIVE Attempt=SENT_UNCONFIRMED Broker=UNKNOWN Knowledge=UNOBSERVED Capacity=POTENTIALLY_LIVE"
  348	      crash_boundary: "after modeled network transmission (VirtualBroker marker)"
  349	      expected: "Attempt=SENT_UNCONFIRMED; Broker=UNKNOWN; Knowledge=UNOBSERVED (preserved); Capacity>=POTENTIALLY_LIVE"
  350	      two_layer_invariant: "Knowledge NOT IN {RECONCILED, CONSISTENT} AND Capacity>=POTENTIALLY_LIVE AND Broker=UNKNOWN"
  351	      observed: "<runtime-observed — run not yet executed>"
  352	      outcome: PENDING_EXECUTION
  353	      normative_anchor: "ADR-002-005 §13 line 198; STATE-EV-004 Injection VER:1045 'after network transmission'"
  354	      evidence_ref: "design §4 row L3-02; run package <pending>"
  355	    - scenario_id: ASS-EVL3-B-03
  356	      row: STATE-EV-004
  357	      design_cell: L3-04
  358	      governed_dimension: broker_order_state
  359	      committed_5tuple: "Intent=ACTIVE Attempt=SENT_UNCONFIRMED Broker=<non-terminal member, implementation enum pin> Knowledge=UNOBSERVED Capacity=POTENTIALLY_LIVE"
  360	      crash_boundary: "crash at a non-terminal broker-order boundary"
  361	      expected: "Broker -> UNKNOWN (non-terminal reconstructed); Knowledge=UNOBSERVED (preserved)"
  362	      two_layer_invariant: "Broker=UNKNOWN (for the non-terminal committed state) AND Capacity>=POTENTIALLY_LIVE"
  363	      observed: "<runtime-observed — run not yet executed>"
  364	      outcome: PENDING_EXECUTION
  365	      normative_anchor: "ADR-002-005 §13 line 198; predicates.py:672-679 (_BROKER_STRUCTURALLY_TERMINAL)"
  366	      evidence_ref: "design §4 row L3-04; run package <pending>"
  367	    - scenario_id: ASS-EVL3-B-04
  368	      row: STATE-EV-001
  369	      design_cell: L3-08
  370	      governed_dimension: "durability round-trip (all five dimensions)"
  371	      committed_5tuple: "Intent=ACTIVE Attempt=SENT_UNCONFIRMED Broker=UNKNOWN Knowledge=CONFLICTED Capacity=POTENTIALLY_LIVE (ADR-002-005 §14 line 208; already conservative => reconstruct is identity)"
  372	      crash_boundary: "normal complete commit -> crash -> reload"
  373	      expected: "reloaded 5-tuple == committed 5-tuple (lossless durable round-trip)"
  374	      two_layer_invariant: "reload(store) == committed (field-identical)"
  375	      observed: "<runtime-observed — run not yet executed>"
  376	      outcome: PENDING_EXECUTION
  377	      normative_anchor: "ADR-002-005 §13 line 197 'durable and reconstructable'; AC-005-1 line 237 'representable and persisted'; §14 line 208"
  378	      evidence_ref: "design §4 row L3-08; run package <pending>"
  379	      note: >-
  380	        This is the R-1 durable-limb boundary cell (consumer STATE-EV-001). Per
  381	        design §4 point (4) and §7.1, L3-08 is a durability MECHANISM cell; the
  382	        R-1 discharge is the durability property over the enumerated §14 composite
  383	        + boundary set (VER §2.7 coverage), not this single cell.
  384	
  385	  adversarial_combination_scenarios:
  386	    - scenario_id: ASS-EVL3-C-01
  387	      row: STATE-EV-004
  388	      design_cell: L3-03
  389	      sub_case_count: 1
  390	      factors:
  391	        - "the attempt reached SEND_STARTED and an ACK was observed in memory"
  392	        - "the crash occurred before that evidence was durably persisted, so the durable store holds only the pre-ACK state"
  393	      governed_dimension: knowledge_state
  394	      committed_5tuple: "Intent=ACTIVE Attempt=SEND_STARTED Broker=UNKNOWN Knowledge=UNOBSERVED Capacity=POTENTIALLY_LIVE (durable = pre-ACK)"
  395	      expected: "the lost ACK does NOT resurrect as RECONCILED; Knowledge=UNOBSERVED (preserved); Broker=UNKNOWN"
  396	      two_layer_invariant: "Knowledge NOT IN {RECONCILED, CONSISTENT}  (load-bearing; VER:1046 'never ... RECONCILED')"
  397	      observed: "<runtime-observed — run not yet executed>"
  398	      outcome: PENDING_EXECUTION
  399	      normative_anchor: "ADR-002-005 §13 line 199; STATE-EV-004 Expected VER:1046"
  400	      evidence_ref: "design §4 row L3-03; run package <pending>"
  401	    - scenario_id: ASS-EVL3-C-02
  402	      row: STATE-EV-004
  403	      design_cell: L3-05
  404	      sub_case_count: 1
  405	      factors:
  406	        - "one dimension (Attempt=SEND_STARTED) is durably committed"
  407	        - "a neighbouring dimension is uncommitted/absent (inter-transaction crash) — an incomplete store"
  408	      governed_dimension: "reconstruction from incomplete store"
  409	      committed_5tuple: "Attempt=SEND_STARTED committed; Broker and Knowledge absent (not committed)"
  410	      expected: "S-2 conservative fill: absent Knowledge -> UNOBSERVED, absent Broker -> UNKNOWN; no optimistic fill"
  411	      two_layer_invariant: "absent dimensions NOT filled with an optimistic value AND Knowledge NOT IN {RECONCILED, CONSISTENT}"
  412	      observed: "<runtime-observed — run not yet executed>"
  413	      outcome: PENDING_EXECUTION
  414	      normative_anchor: "STATE-EV-004 Injection VER:1045 'incomplete stores'; design §5.1 S-2"
  415	      evidence_ref: "design §4 row L3-05; run package <pending>"
  416	    - scenario_id: ASS-EVL3-C-03
  417	      row: STATE-EV-004
  418	      design_cell: L3-06
  419	      sub_case_count: 1
  420	      factors:
  421	        - "the authoritative store holds a conservative Knowledge=UNOBSERVED"
  422	        - "a separate stale cache file holds an optimistic Knowledge=RECONCILED, present simultaneously at restart"
  423	      governed_dimension: knowledge_state
  424	      committed_5tuple: "store: Knowledge=UNOBSERVED (authoritative); cache: Knowledge=RECONCILED (stale, optimistic)"
  425	      expected: "reader ignores the stale cache and re-derives from the store -> Knowledge=UNOBSERVED"
  426	      two_layer_invariant: "Knowledge NOT IN {RECONCILED, CONSISTENT}  (the cache's RECONCILED does not leak in)"
  427	      observed: "<runtime-observed — run not yet executed>"
  428	      outcome: PENDING_EXECUTION
  429	      normative_anchor: "STATE-EV-004 Injection VER:1045 'stale caches'; ADR-002-005 §13 line 199 're-derived'"
  430	      evidence_ref: "design §4 row L3-06; run package <pending>"
  431	    - scenario_id: ASS-EVL3-C-04
  432	      row: STATE-EV-004
  433	      design_cell: L3-07
  434	      sub_case_count: 2
  435	      polarity: positive_canary_both_ways
  436	      factors:
  437	        - "the broker order is structurally terminal (FILLED) and MUST be preserved across restart"
  438	        - "positive Knowledge (RECONCILED; sub-case CONSISTENT) MUST be downgraded on restart"
  439	      governed_dimension: "broker_order_state (preserve) and knowledge_state (downgrade)"
  440	      committed_5tuple: "Intent=ACTIVE Attempt=ACK_OBSERVED Broker=FILLED Knowledge=RECONCILED Capacity=POSITION_CONSUMED (ADR-002-005 §14 line 211)"
  441	      sub_cases:
  442	        - "Knowledge=RECONCILED -> CONFLICTED (in _KNOWLEDGE_DOWNGRADE_ON_RESTART)"
  443	        - "Knowledge=CONSISTENT -> CONFLICTED (the other downgrade member)"
  444	      expected: "Broker=FILLED preserved (terminal); Knowledge -> CONFLICTED (downgraded); Capacity via rcl comparator (preserve if >= POTENTIALLY_LIVE, else raise — implementation-measured)"
  445	      two_layer_invariant: "Broker=FILLED (preserved) AND Knowledge=CONFLICTED AND Knowledge NOT IN {RECONCILED, CONSISTENT}"
  446	      observed: "<runtime-observed — run not yet executed>"
  447	      outcome: PENDING_EXECUTION
  448	      normative_anchor: "ADR-002-005 §13 line 199; predicates.py:729-732, 683-685; §14 line 211"
  449	      evidence_ref: "design §4 row L3-07; run package <pending>"
  450	
  451	  counts:
  452	    catalogue_cells_total: 8
  453	    boundary_value_scenarios: 4        # L3-01, L3-02, L3-04, L3-08
  454	    adversarial_combination_scenarios: 4   # L3-03, L3-05, L3-06, L3-07
  455	    adversarial_combination_sub_cases: 5   # C-04 expands to 2 (RECONCILED, CONSISTENT)
  456	    planned_disposition_observations: 9
  457	    reconciliation: "4 boundary + 4 combination = 8 catalogue cells; sub-case expansion (C-04 -> 2) yields 9 planned dispositions"
  458	    all_outcomes_met: PENDING_EXECUTION
  459	    all_outcomes_met_basis: >-
  460	      NOT ASSERTED. The run has not executed. When it does, each outcome SHALL be
  461	      re-derived by comparing the reader worker's emitted reconstruction against
  462	      the hand-derived hardcoded anchor above (design §5.3), never trusting a
  463	      self-reported flag (design §6.2 all_crash_scenarios_met gate).
  464	
  465	dominance_and_pruning_proofs:
  466	  - id: ASS-DOM-01
  467	    subject: "the seven empty ADR-002-021 §11 trading-scenario groups"
  468	    pruning_basis: SCOPE_DECLARATION_NOT_DOMINANCE
  469	    argument: >-
  470	      See unpopulated_trading_scenario_groups. No dominance is claimed; the groups
  471	      (fill, cancel/amend, price/slippage, correlation, margin, settlement,
  472	      external) have no referent at a restart-reconstruction, non-live-test scope.
  473	  - id: ASS-DOM-02
  474	    subject: "real broker-network / real partition sub-axis of the two populated groups"
  475	    pruning_basis: DEFERRED_TO_RESIDUAL_NOT_DOMINANCE
  476	    argument: >-
  477	      The crash-point transmission is a modeled VirtualBroker marker and the
  478	      pilot emits zero real broker orders (design §0). Real receipt ambiguity and
  479	      real partition are not pruned by dominance; they are a declared residual
  480	      (R-N). ADR-002-021 §11 line 301 forbids pruning without a dominance proof,
  481	      and none is offered here.
  482	  - id: ASS-DOM-03
  483	    subject: "power-loss / torn-sector durability"
  484	    pruning_basis: NOT_PRUNED_UNRESOLVED
  485	    argument: >-
  486	      os._exit models an application process crash faithfully (design §2.4,
  487	      §4), but not kernel page-cache loss, power loss, or torn-sector writes,
  488	      which need filesystem fault injection. Carried as residual R-D. The
  489	      "incomplete stores" facet (VER:1045) IS exercised via an inter-transaction
  490	      crash (L3-05); intra-transaction torn sectors are the R-D residual.
  491	  - id: ASS-DOM-04
  492	    subject: "intent_state and capacity_state as directly mutated inputs"
  493	    pruning_basis: STRUCTURAL_IDENTITY_ARGUED_NOT_EXECUTED
  494	    argument: >-
  495	      intent_state is carried unchanged across restart (intent_identity,
  496	      predicates.py:735) and capacity_state is exercised only through the CPL-1
  497	      raise, not as an independently mutated crash input. The argument that these
  498	      behave correctly across the full input space is structural, NOT a separately
  499	      executed crash mutation. A future run that varies them directly would
  500	      discharge it.
  501	    honesty_flag: >-
  502	      ADR-002-021 §11 line 301 requires pruning to be policy-governed and prove
  503	      dominance. No Aggregate Risk Policy exists to govern this, so this entry is
  504	      an argument on the record, not a discharged proof.
  505	
  506	unbounded_credible_effects:
  507	  - id: ASS-UNB-01
  508	    subject: "real broker-network receipt and partition (the R-N deferred sub-axis)"
  509	    statement: >-
  510	      The economic effect of a real broker transmission cannot be bounded at this
  511	      scope because no real transmission occurs (zero real orders) and no approved
  512	      Broker Capability Profile bound exists (STATE-EV-004 broker_capability_
  513	      profile_version = TBD in EVIDENCE-REGISTER-002.csv line 94). Per ADR-002-021
  514	      §11 line 303, an unbounded credible effect is DENY or UNKNOWN, never a
  515	      convenient finite value.
  516	    present_effect: "None. The pilot emits zero real broker orders; no economic effect can be produced today."
  517	    registered_as: "RESIDUAL-RISK-REGISTER-002.yaml entry R-N (see residual_risk_references — NOT YET registered)"
  518	
  519	common_mode_dependencies:
  520	  - id: ASS-CM-01
  521	    dependency: "single evaluator"
  522	    detail: >-
  523	      The planned run will execute under one harness (tools/tos_evidence_run.py
  524	      EV-L3 stage), one interpreter, and one baseline commit. ADR-002-021 §22
  525	      requires independent reproduction and parser/model/library differential
  526	      results; none is planned in this pilot.
  527	  - id: ASS-CM-02
  528	    dependency: "single seed / deterministic crash schedule"
  529	    detail: >-
  530	      seed=0 with PYTHONHASHSEED=0 for the pure reconstruction property, and
  531	      parametrized deterministic os._exit crash points for the integration matrix
  532	      (design §4, O-2). Determinism is established by construction; input-space
  533	      diversity is not.
  534	  - id: ASS-CM-03
  535	    dependency: "single authoring lane"
  536	    detail: >-
  537	      The design catalogue, the implementation (in progress), this scenario set,
  538	      and the forthcoming evidence were/are produced in the same AI-orchestrated
  539	      authoring lane. VER-002-001 §2.6 (line 75) independent review is NOT_SIGNED,
  540	      so no independent principal has yet reviewed these scenarios or their
  541	      sufficiency.
  542	  - id: ASS-CM-04
  543	    dependency: "the guards under test are also the oracles — STRUCTURALLY OFFSET at EV-L3"
  544	    detail: >-
  545	      In the EV-L2 sibling each Expected was the validator's own verdict, an
  546	      unmitigated common mode. At EV-L3 the design places each Expected as a
  547	      hand-derived hardcoded anchor in an outside test that cannot import tos
  548	      (firewall reverse rule; design §5.3, O-3), so a defect shared between the
  549	      reconstruction guard and the expectation would be caught. This structurally
  550	      OFFSETS the common mode; it does not fully remove it (the hand-derived
  551	      anchors and the §13 norm share a human author). The mutation-canary
  552	      discipline (design §8.3, mutants A-E KILLED) further offsets it.
  553	  - id: ASS-CM-05
  554	    dependency: "pre-execution authoring (temporal)"
  555	    detail: >-
  556	      This instance is authored BEFORE the run. Every outcome is
  557	      PENDING_EXECUTION. A scenario whose Expected proves unreachable or wrong at
  558	      run time SHALL be corrected and the correction traced (VER §2.2); this
  559	      instance is not evidence that the scenarios passed, only that they are the
  560	      specified adverse set.
  561	
  562	residual_risk_references:
  563	  # VER-002-001 §378 line 3309 non-union rule: separate residual risks SHALL NOT
  564	  # be unioned at a consumer. Each is cited individually below.
  565	  non_union_statement: >-
  566	    R-1, R-N, R-I, and R-D are four independent residuals. A consumer SHALL cite
  567	    them individually and SHALL NOT summarise them as one aggregate residual
  568	    (VER-002-001 §378 line 3309).
  569	  entries:
  570	    - id: R-1
  571	      subject: "STATE-EV-001 durable/persisted limb"
  572	      status: REGISTERED
  573	      location: "RESIDUAL-RISK-REGISTER-002.yaml (entry R-1, risk_identity line 89-90)"
  574	      relation_to_this_set: >-
  575	        This set's boundary cell ASS-EVL3-B-04 (design L3-08) and the durability
  576	        property over the §14 composite set are the coverage argument the R-1
  577	        discharge depends on (design §7.1). The discharge is CONDITIONAL on the
  578	        OQ-1 operator adjudication (§4-persistence decision) and is recorded
  579	        substrate-class (design §7.1, §9, MINOR-4).
  580	    - id: R-N
  581	      subject: "STATE-EV-004 real-network-boundary axis (modeled transmission)"
  582	      status: PROPOSED_NOT_YET_REGISTERED
  583	      location: >-
  584	        Proposed by the EV-L3 pilot design §2.4. MEASURED ABSENT from
  585	        RESIDUAL-RISK-REGISTER-002.yaml (the register holds R-1, R-2, R-3 only;
  586	        negative-grep). Registration is prerequisite work on the STATE-EV-004 PASS
  587	        track and is an open operator gate.
  588	    - id: R-I
  589	      subject: "STATE-EV-004 credential/service-identity axis (logical identity re-derivation executed; real auth deferred)"
  590	      status: PROPOSED_NOT_YET_REGISTERED
  591	      location: "Proposed by the EV-L3 pilot design §2.4; absent from the register (negative-grep). Referent: STATE-EV-005 (EV-L2/3 plus security, VER:1050)."
  592	    - id: R-D
  593	      subject: "power-loss / torn-sector durability (os._exit models process crash, not power loss)"
  594	      status: CANDIDATE_NOT_YET_REGISTERED
  595	      location: "Candidate in the EV-L3 pilot design §2.4; absent from the register (negative-grep). Needs filesystem fault injection."
  596	
  597	approved_by: []                        # PROPOSED — operator approval is a pending human gate
  598	effective_from: null                   # set on approval
  599	review_due: null                       # set on approval; MAX_residual_risk_review_interval_ms bound then applies
  600	
  601	authority:
  602	  grants_risk_allocation: false
  603	  creates_capacity: false
  604	  releases_capacity: false
  605	  creates_live_authorization: false
  606	  creates_protective_classification: false
  607	  creates_transmission_capability: false
  608	  permits_broker_transmission: false
  609	  clears_halt: false
  610	  permits_rearm: false
  611	  permits_automatic_rearm: false
  612	
  613	authorization_notice: >-
  614	  This PROPOSED instance grants nothing and is not yet approved. It specifies the
  615	  adversarial-combination leg of the VER-002-001 §2.7 coverage argument for the
  616	  RESTART axis of exactly two evidence rows (STATE-EV-004 primary; STATE-EV-001
  617	  R-1 durable limb) at a non-live-test scope that emits zero real broker orders.
  618	  Seven of the nine ADR-002-021 §11 trading-scenario groups are empty and the two
  619	  populated groups carry the restart-reconstruction sub-axis only, with the real
  620	  broker-network / partition sub-axis deferred to residual R-N. It is not
  621	  policy-bound (`aggregate_risk_policy_id` is null), so it establishes no maximum
  622	  credible effect and SHALL NOT be consumed by any aggregate-risk evaluation. Its
  623	  `canonical_digest` is null because no approved canonicalization scheme exists for
  624	  spec-layer YAML instances (ADR-002-021 §28 question 1, line 698, is open); a null
  625	  digest is not a digest, and a consumer that requires digest binding SHALL treat
  626	  this set as unbound. It is authored PRE-EXECUTION: every scenario outcome is
  627	  PENDING_EXECUTION and this file is not evidence that any scenario passed.
  628	  Approving this instance does not accept ADR-002-021, which remains `Proposed`
  629	  (§29 line 719), and does not move any evidence row to PASS: STATE-EV-004 stays
  630	  NOT_IMPLEMENTED, STATE-EV-001 stays READY, and the pilot's remaining gates
  631	  (independent review signature per VER §9.5 and §2.6, VER §3 complete baseline,
  632	  residuals R-N/R-I/R-D registration, and the OQ-1 §4-persistence adjudication for
  633	  R-1) are untouched by this file.
  634	
```

---- SOURCE tests/tos_l3/conftest.py (full) ----
```
    1	"""EV-L3 crash-schedule capture — the outside orchestration's only wiring.
    2	
    3	Isomorphic to ``tos/tests/conftest.py`` (the EV-L2 fault-schedule sink), extended to the
    4	EV-L3 integrated crash/restart stage per the ratified design contract
    5	``docs/plans/2026-08-06-tos-ev-l3-pilot-design.md`` §6.1: the append-only schedule
    6	artifact VER-002-001 §9.1 requires ("test identity, baseline, seed, and fault schedule
    7	SHALL be append-only").
    8	
    9	Why a pytest option and not an environment variable: the option is how the evidence
   10	harness (``tools/tos_evidence_run.py``) hands the run-scoped sink path to the suite,
   11	exactly as ``--l2-fault-timeline`` already does. When the option is absent (a plain
   12	developer ``pytest tests/tos_l3``) **no file is written and nothing is skipped** — the
   13	crash assertions still execute. The timeline is an evidence artifact, never a
   14	precondition of the tests.
   15	
   16	⚠ This directory is **outside** ``tos/``. The firewall's forward rules (allowlist /
   17	forbidden stdlib / ``os.environ``) do not apply here — ``subprocess`` is legitimate —
   18	but the **reverse** rule TOS-FW-R does: ``tools/tos_firewall_check.py`` prunes only a
   19	directory literally named ``tos`` (``_REVERSE_SCAN_PRUNE``, line 114-116), so nothing
   20	here may ``import tos``. That prohibition is not an inconvenience, it is the design's
   21	structural oracle-independence guarantee (§5.3 / O-3).
   22	"""
   23	
   24	from __future__ import annotations
   25	
   26	import json
   27	from pathlib import Path
   28	from typing import Any
   29	
   30	import pytest
   31	
   32	#: The fixed seed the EV-L3 crash schedule is executed under (design §4 "seed=0"). The
   33	#: catalog is a deterministic enumeration rather than a sampled one, so the seed is
   34	#: recorded for reproducibility of the surrounding property assertions and of the run
   35	#: record itself (VER §9.1), not because the crash points are randomised.
   36	L3_CRASH_SEED = 0
   37	
   38	#: Outcome vocabulary (design §6.1, inherited from the EV-L2 schedule). A single
   39	#: ``DEVIATION`` forbids a GREEN run.
   40	OUTCOME_MET = "MET"
   41	OUTCOME_DEVIATION = "DEVIATION"
   42	
   43	#: The exact ordered field set of one crash-timeline row (design §6.2 — the harness's
   44	#: six gates must each be re-derivable from these fields alone).
   45	L3_TIMELINE_FIELDS: tuple[str, ...] = (
   46	    "scenario_id",
   47	    "evidence_id",
   48	    "target_component",
   49	    "crash_point",
   50	    "crash_exit_status",
   51	    "seed",
   52	    "writer_pid",
   53	    "reader_pid",
   54	    "store_real_on_disk",
   55	    "store_bytes",
   56	    "expected_reconstruction",
   57	    "observed_reconstruction",
   58	    "outcome",
   59	)
   60	
   61	
   62	def pytest_addoption(parser: pytest.Parser) -> None:
   63	    """Register ``--l3-crash-timeline`` (the EV-L3 crash-schedule sink)."""
   64	    parser.addoption(
   65	        "--l3-crash-timeline",
   66	        action="store",
   67	        default=None,
   68	        metavar="PATH",
   69	        help=(
   70	            "append the EV-L3 crash schedule (one JSON object per crash scenario, "
   71	            "VER-002-001 §9.1 append-only) to PATH; omit to run the crash "
   72	            "assertions without producing an evidence artifact"
   73	        ),
   74	    )
   75	
   76	
   77	class L3CrashTimeline:
   78	    """Append-only sink for EV-L3 crash rows (design §6.1).
   79	
   80	    Each :meth:`record` call appends exactly one JSON object — the file is opened in
   81	    append mode per row, so a row that has been written is never rewritten and an
   82	    aborted session still leaves every scenario it reached (VER §9.1 / §2.2: a failed
   83	    run is preserved, not replaced).
   84	
   85	    ``outcome`` is **derived**, never passed in: a row is ``MET`` only when the expected
   86	    reconstruction is a concrete non-empty string, the observed reconstruction equals
   87	    it, **and** the two structural boundary facts hold (a real process boundary —
   88	    distinct positive pids — and a real on-disk store). A missing expectation is
   89	    therefore structurally a ``DEVIATION`` and can never be silently counted as met
   90	    (design §0.5-2 / §0.5-4: only falsifiable Expecteds are admissible, and "0 crashes
   91	    injected" is not "no violations").
   92	    """
   93	
   94	    def __init__(self, path: Path | None) -> None:
   95	        """Bind the sink to ``path`` (``None`` => in-memory only)."""
   96	        self._path = path
   97	        self.rows: list[dict[str, Any]] = []
   98	
   99	    @property
  100	    def path(self) -> Path | None:
  101	        """The artifact path, or ``None`` when no artifact is being produced."""
  102	        return self._path
  103	
  104	    def record(
  105	        self,
  106	        *,
  107	        scenario_id: str,
  108	        evidence_id: str,
  109	        target_component: str,
  110	        crash_point: str,
  111	        crash_exit_status: int,
  112	        writer_pid: int,
  113	        reader_pid: int,
  114	        store_real_on_disk: bool,
  115	        store_bytes: int,
  116	        expected_reconstruction: str,
  117	        observed_reconstruction: str,
  118	    ) -> dict[str, Any]:
  119	        """Append one crash row and return it.
  120	
  121	        Args:
  122	            scenario_id: The design §4 catalog id (``L3-01`` … ``L3-08``).
  123	            evidence_id: The Evidence Register row this crash scenario belongs to.
  124	            target_component: The integrated components under crash injection.
  125	            crash_point: Where the deterministic crash landed, named structurally.
  126	            crash_exit_status: The writer process's **observed** exit status.
  127	            writer_pid: The crashed writer's OS pid, observed by this orchestrator.
  128	            reader_pid: The fresh reader's OS pid, observed by this orchestrator.
  129	            store_real_on_disk: Whether the store file existed on the filesystem after
  130	                the writer died — measured with :meth:`pathlib.Path.is_file`, never
  131	                self-reported by the worker.
  132	            store_bytes: The store file's size after the crash.
  133	            expected_reconstruction: The hand-derived §4 anchor, as the canonical
  134	                five-dimension string. Derived independently of the implementation:
  135	                nothing outside ``tos/`` can call ``reconstruct_conservative``.
  136	            observed_reconstruction: The same string built from the fresh reader's
  137	                stdout verdict.
  138	
  139	        Returns:
  140	            The appended row.
  141	        """
  142	        boundary_real = writer_pid > 0 and reader_pid > 0 and writer_pid != reader_pid
  143	        met = (
  144	            bool(expected_reconstruction)
  145	            and observed_reconstruction == expected_reconstruction
  146	            and boundary_real
  147	            and store_real_on_disk
  148	            and store_bytes > 0
  149	        )
  150	        row: dict[str, Any] = {
  151	            "scenario_id": scenario_id,
  152	            "evidence_id": evidence_id,
  153	            "target_component": target_component,
  154	            "crash_point": crash_point,
  155	            "crash_exit_status": crash_exit_status,
  156	            "seed": L3_CRASH_SEED,
  157	            "writer_pid": writer_pid,
  158	            "reader_pid": reader_pid,
  159	            "store_real_on_disk": store_real_on_disk,
  160	            "store_bytes": store_bytes,
  161	            "expected_reconstruction": expected_reconstruction,
  162	            "observed_reconstruction": observed_reconstruction,
  163	            "outcome": OUTCOME_MET if met else OUTCOME_DEVIATION,
  164	        }
  165	        assert tuple(row) == L3_TIMELINE_FIELDS
  166	        self.rows.append(row)
  167	        if self._path is not None:
  168	            with open(self._path, "a", encoding="utf-8") as fh:
  169	                fh.write(json.dumps(row, sort_keys=False, ensure_ascii=False) + "\n")
  170	        return row
  171	
  172	
  173	@pytest.fixture(scope="session")
  174	def l3_crash_timeline(request: pytest.FixtureRequest) -> L3CrashTimeline:
  175	    """The session-wide EV-L3 crash-schedule sink (design §6.1)."""
  176	    raw = request.config.getoption("--l3-crash-timeline")
  177	    return L3CrashTimeline(Path(raw) if raw else None)
  178	
```

---- SOURCE tests/tos_l3/test_state_ev_004_crash_restart.py (full) ----
```
    1	"""STATE-EV-004 EV-L3 integrated crash/restart suite — the outside orchestration.
    2	
    3	**Stage**: EV-L3 (VER-002-001 §5 line 151-153 verbatim — "Multiple live-path components
    4	are tested together with real persistence, identity, and network boundaries"). Catalog:
    5	EV-L3 pilot design ``docs/plans/2026-08-06-tos-ev-l3-pilot-design.md`` §4, **eight crash
    6	scenarios** (``L3-01`` … ``L3-08``).
    7	
    8	Why this file lives outside ``tos/``
    9	------------------------------------
   10	Not because it must — a ``multiprocessing`` spawn inside ``tos/tests`` would also give a
   11	distinct pid and a distinct interpreter, and the kernel's own closure tests already use
   12	one (design §5.2 MAJOR-1, measured). It lives here because of what the placement
   13	**structurally forbids**: the firewall's reverse rule TOS-FW-R
   14	(``tools/tos_firewall_check.py``; ``_REVERSE_SCAN_PRUNE`` at line 114-116 prunes only a
   15	directory literally named ``tos``, so this path is scanned) makes ``import tos``
   16	impossible here. This suite therefore **cannot** call
   17	``tos.orthostate.reconstruct_conservative``, and its Expecteds are necessarily
   18	hand-derived anchors rather than a second invocation of the implementation under test.
   19	
   20	That is the whole point. ADVERSE-SCENARIO-SET-002 ASS-CM-04 names the failure mode —
   21	"guards … are also the oracles" — and design §5.3 buys structural immunity to it at the
   22	cost of orchestration complexity (subprocess spawn, argv, stdout parsing, anchor
   23	comparison) sitting outside the firewall's certified surface. A bug in
   24	``reconstruct_conservative`` cannot make these anchors agree with it.
   25	
   26	What is real here, and what is modelled
   27	---------------------------------------
   28	* **Real persistence** — a sqlite3 file on the filesystem, written by a process that
   29	  then died. Asserted structurally (the file exists and is non-empty *after* the writer
   30	  is gone), never self-reported.
   31	* **Real process boundary** — two OS processes, ``writer_pid != reader_pid``, whose only
   32	  channel is that file. Both pids are the ones this orchestrator observed from
   33	  :class:`subprocess.Popen`, cross-checked against what each worker reported about
   34	  itself; a disagreement fails.
   35	* **Real crash** — the writer dies by a deterministic ``os._exit(137)`` at a
   36	  parametrized point. Nothing is flushed or unwound.
   37	* **Modelled network** — the "after network transmission" injection point (VER line
   38	  1045) is a VirtualBroker-class marker. **Zero real bytes are transmitted and zero real
   39	  orders exist**; the real broker network boundary is residual R-N and the real futures
   40	  order path is permanently policy-blocked.
   41	* **Deferred credential identity** — logical identifiers are re-derived from the store;
   42	  real credential / cross-host authentication is residual R-I (STATE-EV-005).
   43	
   44	⚠ Executing this suite records an EV-L3 stage. It moves no Evidence Register row to
   45	PASS: STATE-EV-004 keeps its unexercised network and credential-identity axes, the
   46	restart coverage argument is a review-layer obligation, and independent sign-off
   47	(VER §9.5) is outstanding.
   48	"""
   49	
   50	from __future__ import annotations
   51	
   52	import json
   53	import subprocess
   54	import sys
   55	from pathlib import Path
   56	from typing import NamedTuple
   57	
   58	import pytest
   59	
   60	_REPO_ROOT = Path(__file__).resolve().parents[2]
   61	_KERNEL_SRC = _REPO_ROOT / "tos" / "src"
   62	
   63	_EVIDENCE_ID = "STATE-EV-004"
   64	_WORKER_MODULE = "tos.staterestore._l3_worker"
   65	_COMPONENT = (
   66	    "CompositeState + durable staterestore store + restart reload + "
   67	    "reconstruct_conservative, across a real process boundary"
   68	)
   69	
   70	#: The writer's deterministic crash status (design §4 / O-2). Hardcoded here rather than
   71	#: read from the kernel: an implementation that stopped crashing and merely returned
   72	#: would otherwise redefine the expectation to match itself.
   73	_CRASH_EXIT = 137
   74	
   75	#: The five-dimension coordinate order the anchors are written in.
   76	_DIMENSION_KEYS = (
   77	    "intent_state",
   78	    "transmission_attempt_state",
   79	    "broker_order_state",
   80	    "knowledge_state",
   81	    "capacity_state",
   82	)
   83	
   84	#: Layer 2 of the design §4 anchors — derived directly from ADR-002-005 §13 line 199
   85	#: ("Knowledge SHALL be re-derived …, **never** to ``RECONCILED``") plus the §11 rule
   86	#: that a restart is a weak basis and so may not produce positive knowledge. This set is
   87	#: independent of the reconstruction's *value* anchors: even if every value anchor below
   88	#: were wrong, a post-restart Knowledge inside this set is a spec violation.
   89	_FORBIDDEN_POST_RESTART_KNOWLEDGE = frozenset({"RECONCILED", "CONSISTENT"})
   90	
   91	#: Capacity conservatism order, transcribed by hand from ADR-002-002 §10.1 (least → most
   92	#: conservative / capacity-consuming). Transcribed rather than imported **on purpose**:
   93	#: the reverse firewall rule forbids importing ``tos.rcl``'s comparator, so ``Capacity is
   94	#: at least as conservative as POTENTIALLY_LIVE`` is decided here against an independent
   95	#: statement of the order.
   96	_CAPACITY_ORDER = (
   97	    "RELEASED",
   98	    "COMMITTED_UNBOUND",
   99	    "ATTEMPT_BOUND",
  100	    "POTENTIALLY_LIVE",
  101	    "PARTIALLY_CONSUMED",
  102	    "POSITION_CONSUMED",
  103	    "RELEASE_PENDING_PROOF",
  104	    "TRAPPED_CONSUMED",
  105	    "QUARANTINED_UNKNOWN",
  106	)
  107	
  108	
  109	def _canonical(values: tuple[str, str, str, str, str]) -> str:
  110	    """The five dimensions as one comparable string (the schedule's Expected/Observed)."""
  111	    labels = ("INTENT", "ATTEMPT", "BROKER", "KNOWLEDGE", "CAPACITY")
  112	    return "|".join(f"{label}={value}" for label, value in zip(labels, values))
  113	
  114	
  115	class _Cell:
  116	    """One design §4 catalog cell, as the **oracle** half.
  117	
  118	    Holds only what the design table states as *Expected*: the crash point's structural
  119	    name, the hand-derived post-restart anchor, and the cell's own layer-2 invariants.
  120	    The committed composite (the input) belongs to the worker; nothing here is read back
  121	    from it.
  122	    """
  123	
  124	    def __init__(
  125	        self,
  126	        scenario_id: str,
  127	        crash_point: str,
  128	        anchor: tuple[str, str, str, str, str],
  129	        *,
  130	        min_capacity: str | None = None,
  131	        required_broker: str | None = None,
  132	        required_knowledge: str | None = None,
  133	        expect_store_complete: bool = True,
  134	        expect_filled: tuple[str, ...] = (),
  135	        expect_fill_values: tuple[tuple[str, str], ...] = (),
  136	        expect_cache_discarded: bool = False,
  137	        expect_lossless_roundtrip: bool = False,
  138	        basis: str = "",
  139	    ) -> None:
  140	        self.scenario_id = scenario_id
  141	        self.crash_point = crash_point
  142	        self.anchor = anchor
  143	        self.min_capacity = min_capacity
  144	        self.required_broker = required_broker
  145	        self.required_knowledge = required_knowledge
  146	        self.expect_store_complete = expect_store_complete
  147	        self.expect_filled = expect_filled
  148	        self.expect_fill_values = expect_fill_values
  149	        self.expect_cache_discarded = expect_cache_discarded
  150	        self.expect_lossless_roundtrip = expect_lossless_roundtrip
  151	        self.basis = basis
  152	
  153	    @property
  154	    def expected(self) -> str:
  155	        """The canonical Expected string for the schedule row."""
  156	        return _canonical(self.anchor)
  157	
  158	
  159	#: The design §4 catalog. Every anchor below was derived by hand from ADR-002-005 §13:
  160	#:
  161	#:   * line 198 — an Attempt that reached ``SEND_STARTED`` and is not proven-terminal
  162	#:     raises Capacity to at least ``POTENTIALLY_LIVE``; a Broker Order that is not
  163	#:     *provably terminal* reconstructs as ``UNKNOWN`` (terminal ones are preserved);
  164	#:   * line 199 — positive Knowledge (``RECONCILED`` / ``CONSISTENT``) is re-derived
  165	#:     downward and never re-arrived at, while a Knowledge that was already conservative
  166	#:     is preserved;
  167	#:   * Intent and Attempt are carried across the restart unchanged.
  168	_CELLS: tuple[_Cell, ...] = (
  169	    _Cell(
  170	        "L3-01",
  171	        "AFTER_DURABLE_SEND_STARTED_BEFORE_BROKER",
  172	        ("ACTIVE", "SEND_STARTED", "UNKNOWN", "UNOBSERVED", "POTENTIALLY_LIVE"),
  173	        min_capacity="POTENTIALLY_LIVE",
  174	        required_broker="UNKNOWN",
  175	        basis="§13:198 — durable SEND_STARTED implies a possibly-live send",
  176	    ),
  177	    _Cell(
  178	        "L3-02",
  179	        "AFTER_MODELLED_NETWORK_TRANSMISSION",
  180	        ("ACTIVE", "SENT_UNCONFIRMED", "UNKNOWN", "UNOBSERVED", "POTENTIALLY_LIVE"),
  181	        min_capacity="POTENTIALLY_LIVE",
  182	        required_broker="UNKNOWN",
  183	        basis="VER:1045 'after network transmission' (MODELLED marker; residual R-N)",
  184	    ),
  185	    _Cell(
  186	        "L3-03",
  187	        "BEFORE_EVIDENCE_PERSISTENCE",
  188	        ("ACTIVE", "SEND_STARTED", "UNKNOWN", "UNOBSERVED", "POTENTIALLY_LIVE"),
  189	        required_knowledge="UNOBSERVED",
  190	        basis=(
  191	            "VER:1046 'never defaults to RECONCILED' — the in-memory ACK that was "
  192	            "never persisted must not be resurrected"
  193	        ),
  194	    ),
  195	    _Cell(
  196	        "L3-04",
  197	        "AT_NON_TERMINAL_BROKER_ORDER_BOUNDARY",
  198	        ("ACTIVE", "SENT_UNCONFIRMED", "UNKNOWN", "UNOBSERVED", "POTENTIALLY_LIVE"),
  199	        min_capacity="POTENTIALLY_LIVE",
  200	        required_broker="UNKNOWN",
  201	        basis="§13:198 — a broker order that is not provably terminal is UNKNOWN",
  202	    ),
  203	    _Cell(
  204	        "L3-05",
  205	        "BETWEEN_DIMENSION_TRANSACTIONS_INCOMPLETE_STORE",
  206	        ("ACTIVE", "SEND_STARTED", "UNKNOWN", "UNOBSERVED", "POTENTIALLY_LIVE"),
  207	        min_capacity="POTENTIALLY_LIVE",
  208	        required_broker="UNKNOWN",
  209	        expect_store_complete=False,
  210	        expect_filled=("BROKER_ORDER", "KNOWLEDGE"),
  211	        # The §4 invariant's FIRST conjunct — "an absent dimension is never an
  212	        # optimistic value" — is a claim about the FILL, not about the projection's
  213	        # output. Asserting only the output would leave an optimistic fill invisible,
  214	        # because the §13 projection repairs a non-terminal Broker to UNKNOWN on its
  215	        # way past (measured: an absent-Broker => NONE_OBSERVED mutant survives an
  216	        # output-only anchor). These pin the re-derived pre-restart values themselves.
  217	        expect_fill_values=(("BROKER_ORDER", "UNKNOWN"), ("KNOWLEDGE", "UNOBSERVED")),
  218	        basis="VER:1045 'incomplete stores' — absent dimensions fill conservatively",
  219	    ),
  220	    _Cell(
  221	        "L3-06",
  222	        "AFTER_STALE_OPTIMISTIC_CACHE",
  223	        ("ACTIVE", "SENT_UNCONFIRMED", "UNKNOWN", "UNOBSERVED", "POTENTIALLY_LIVE"),
  224	        required_knowledge="UNOBSERVED",
  225	        expect_cache_discarded=True,
  226	        basis="VER:1045 'stale caches' + §13:199 re-derive — the cache never flows in",
  227	    ),
  228	    _Cell(
  229	        "L3-07",
  230	        "AFTER_TERMINAL_FILL_WITH_POSITIVE_KNOWLEDGE",
  231	        ("ACTIVE", "ACK_OBSERVED", "FILLED", "CONFLICTED", "POSITION_CONSUMED"),
  232	        min_capacity="POTENTIALLY_LIVE",
  233	        required_broker="FILLED",
  234	        required_knowledge="CONFLICTED",
  235	        basis=(
  236	            "§13:198 terminal broker preserved + §13:199 positive knowledge downgraded "
  237	            "(the both-ways positive canary: this cell FIRES the downgrade)"
  238	        ),
  239	    ),
  240	    _Cell(
  241	        "L3-08",
  242	        "AFTER_COMPLETE_DURABLE_COMMIT",
  243	        ("ACTIVE", "SENT_UNCONFIRMED", "UNKNOWN", "CONFLICTED", "POTENTIALLY_LIVE"),
  244	        min_capacity="POTENTIALLY_LIVE",
  245	        required_broker="UNKNOWN",
  246	        expect_lossless_roundtrip=True,
  247	        basis=(
  248	            "§13:197 durable + AC-005-1:237 'representable and persisted' — an already "
  249	            "conservative composite round-trips losslessly and the projection is the "
  250	            "identity"
  251	        ),
  252	    ),
  253	)
  254	
  255	_CELLS_BY_ID = {cell.scenario_id: cell for cell in _CELLS}
  256	
  257	
  258	class _Worker(NamedTuple):
  259	    """One finished worker process, as observed from outside it."""
  260	
  261	    pid: int
  262	    returncode: int
  263	    stdout: str
  264	    stderr: str
  265	
  266	
  267	def _spawn(mode: str, scenario_id: str, store: Path, cache: Path) -> _Worker:
  268	    """Run one worker process to completion and report what was observed.
  269	
  270	    The pid recorded is the one **this orchestrator** received from the OS, not one the
  271	    worker printed about itself — the process-boundary claim must not rest on a
  272	    self-report. ``PYTHONPATH`` is set explicitly rather than inherited so a plain
  273	    developer run behaves identically to a harness run, and ``PYTHONHASHSEED`` is pinned
  274	    so the subprocess is as deterministic as the parent (VER §9.1).
  275	    """
  276	    env = {
  277	        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
  278	        "PYTHONPATH": str(_KERNEL_SRC),
  279	        "PYTHONHASHSEED": "0",
  280	        "LC_ALL": "C",
  281	    }
  282	    proc = subprocess.Popen(
  283	        [
  284	            sys.executable,
  285	            "-m",
  286	            _WORKER_MODULE,
  287	            mode,
  288	            scenario_id,
  289	            str(store),
  290	            str(cache),
  291	        ],
  292	        cwd=str(_REPO_ROOT),
  293	        stdout=subprocess.PIPE,
  294	        stderr=subprocess.PIPE,
  295	        text=True,
  296	        env=env,
  297	    )
  298	    stdout, stderr = proc.communicate()
  299	    return _Worker(proc.pid, proc.returncode, stdout, stderr)
  300	
  301	
  302	def _run_scenario(scenario_id: str, workdir: Path) -> dict:
  303	    """Crash a writer, then reload in a fresh process. Returns the measured facts."""
  304	    store = workdir / f"{scenario_id}.sqlite3"
  305	    cache = workdir / f"{scenario_id}.cache.json"
  306	
  307	    writer = _spawn("writer", scenario_id, store, cache)
  308	
  309	    # Measured AFTER the writer is gone: this is the persistence claim, and it is a
  310	    # filesystem observation rather than anything the worker said about itself.
  311	    store_exists = store.is_file()
  312	    store_bytes = store.stat().st_size if store_exists else 0
  313	
  314	    reader = _spawn("reader", scenario_id, store, cache)
  315	
  316	    return {
  317	        "store": store,
  318	        "cache": cache,
  319	        "writer": writer,
  320	        "reader": reader,
  321	        "store_real_on_disk": store_exists,
  322	        "store_bytes": store_bytes,
  323	    }
  324	
  325	
  326	@pytest.fixture(scope="module")
  327	def crash_runs(tmp_path_factory) -> dict[str, dict]:
  328	    """Execute all eight §4 crash scenarios once, in catalog order (deterministic)."""
  329	    workdir = tmp_path_factory.mktemp("tos-l3-crash")
  330	    return {
  331	        cell.scenario_id: _run_scenario(cell.scenario_id, workdir) for cell in _CELLS
  332	    }
  333	
  334	
  335	@pytest.mark.parametrize("cell", _CELLS, ids=lambda c: c.scenario_id)
  336	def test_crash_restart_reconstructs_the_hand_derived_anchor(
  337	    cell: _Cell, crash_runs: dict[str, dict], l3_crash_timeline
  338	) -> None:
  339	    """The §4 catalog, both anchor layers, plus the two structural boundary facts.
  340	
  341	    Layer 1 is the exact five-dimension anchor; layer 2 is the independent
  342	    ``Knowledge ∉ {RECONCILED, CONSISTENT}`` invariant read straight off ADR-002-005
  343	    §13 line 199. Both are asserted for every cell, so a wrong-but-self-consistent
  344	    implementation would have to defeat two independently derived statements.
  345	    """
  346	    run = crash_runs[cell.scenario_id]
  347	    writer: _Worker = run["writer"]
  348	    reader: _Worker = run["reader"]
  349	
  350	    # -- the crash really happened, at the parametrized point -------------------
  351	    assert writer.returncode == _CRASH_EXIT, (
  352	        f"{cell.scenario_id}: writer exited {writer.returncode} "
  353	        f"(expected the deterministic crash {_CRASH_EXIT}); stderr={writer.stderr}"
  354	    )
  355	    assert reader.returncode == 0, f"reader failed: {reader.stderr}"
  356	
  357	    # -- real persistence: the store outlived the process that wrote it ---------
  358	    assert run["store_real_on_disk"] is True, "the store is not a real on-disk file"
  359	    assert run["store_bytes"] > 0, "an empty store file evidences nothing"
  360	
  361	    # -- real process boundary: two distinct OS processes -----------------------
  362	    verdict = json.loads(reader.stdout.strip().splitlines()[-1])
  363	    assert writer.pid != reader.pid, "writer and reader share a pid"
  364	    assert verdict["pid"] == reader.pid, (
  365	        "the reader's self-reported pid disagrees with the pid this orchestrator "
  366	        "spawned — the verdict may not come from the process that was measured"
  367	    )
  368	    writer_verdict = json.loads(writer.stdout.strip().splitlines()[-1])
  369	    assert writer_verdict["pid"] == writer.pid
  370	
  371	    observed = _canonical(tuple(verdict[key] for key in _DIMENSION_KEYS))
  372	
  373	    # -- layer 2 first: it holds regardless of whether layer 1 is right ---------
  374	    assert verdict["knowledge_state"] not in _FORBIDDEN_POST_RESTART_KNOWLEDGE, (
  375	        f"{cell.scenario_id}: post-restart Knowledge is "
  376	        f"{verdict['knowledge_state']} — ADR-002-005 §13 line 199 forbids re-arriving "
  377	        "at positive knowledge across a restart"
  378	    )
  379	    # -- layer 1: the exact hand-derived anchor --------------------------------
  380	    assert observed == cell.expected, f"{cell.scenario_id} ({cell.basis})"
  381	
  382	    # -- the cell's own extra invariants ---------------------------------------
  383	    if cell.min_capacity is not None:
  384	        assert _CAPACITY_ORDER.index(
  385	            verdict["capacity_state"]
  386	        ) >= _CAPACITY_ORDER.index(
  387	            cell.min_capacity
  388	        ), f"{cell.scenario_id}: capacity is less conservative than {cell.min_capacity}"
  389	    if cell.required_broker is not None:
  390	        assert verdict["broker_order_state"] == cell.required_broker
  391	    if cell.required_knowledge is not None:
  392	        assert verdict["knowledge_state"] == cell.required_knowledge
  393	    assert verdict["store_complete"] is cell.expect_store_complete
  394	    assert tuple(verdict["filled_dimensions"]) == cell.expect_filled
  395	    for dimension, expected_fill in cell.expect_fill_values:
  396	        assert verdict["committed_dimensions_readback"][dimension] == expected_fill, (
  397	            f"{cell.scenario_id}: the absent {dimension} was filled with "
  398	            f"{verdict['committed_dimensions_readback'][dimension]} — VER:1045 "
  399	            "requires an incomplete store to fill conservatively, and an optimistic "
  400	            "fill is a fail-open even when a later projection happens to mask it"
  401	        )
  402	    if cell.expect_cache_discarded:
  403	        assert verdict["discarded_caches"], "the stale cache was never written"
  404	        assert (
  405	            verdict["cache_present_after_reload"] is False
  406	        ), "the optimistic cache survived the reload — it must be discarded, not kept"
  407	    if cell.expect_lossless_roundtrip:
  408	        # AC-005-1 line 237 "representable and persisted": what came back off the disk
  409	        # is byte-for-byte the five dimensions that were committed, and the §13
  410	        # projection over an already-conservative composite is the identity — so the
  411	        # anchor doubles as the committed pin here.
  412	        readback = tuple(
  413	            verdict["committed_dimensions_readback"][dimension]
  414	            for dimension in (
  415	                "INTENT",
  416	                "TRANSMISSION_ATTEMPT",
  417	                "BROKER_ORDER",
  418	                "KNOWLEDGE",
  419	                "CAPACITY",
  420	            )
  421	        )
  422	        assert (
  423	            readback == cell.anchor
  424	        ), "the durable round-trip lost or altered a committed dimension"
  425	
  426	    l3_crash_timeline.record(
  427	        scenario_id=cell.scenario_id,
  428	        evidence_id=_EVIDENCE_ID,
  429	        target_component=_COMPONENT,
  430	        crash_point=cell.crash_point,
  431	        crash_exit_status=writer.returncode,
  432	        writer_pid=writer.pid,
  433	        reader_pid=reader.pid,
  434	        store_real_on_disk=run["store_real_on_disk"],
  435	        store_bytes=run["store_bytes"],
  436	        expected_reconstruction=cell.expected,
  437	        observed_reconstruction=observed,
  438	    )
  439	
  440	
  441	def test_the_catalog_is_the_eight_design_cells_and_no_row_is_silently_dropped(
  442	    crash_runs: dict[str, dict],
  443	) -> None:
  444	    """∅-seal, both directions (design §0.5-2): the catalog size is itself pinned."""
  445	    assert [cell.scenario_id for cell in _CELLS] == [
  446	        "L3-01",
  447	        "L3-02",
  448	        "L3-03",
  449	        "L3-04",
  450	        "L3-05",
  451	        "L3-06",
  452	        "L3-07",
  453	        "L3-08",
  454	    ]
  455	    assert set(crash_runs) == set(_CELLS_BY_ID)
  456	
  457	
  458	def test_every_anchor_is_falsifiable_and_no_two_cells_are_the_same_observation(
  459	    crash_runs: dict[str, dict],
  460	) -> None:
  461	    """A catalog whose cells all expect the same thing evidences almost nothing.
  462	
  463	    Eight rows that happened to share one anchor would look like eight measurements
  464	    while being one. The distinct-anchor count is therefore asserted, and every anchor
  465	    is required to be a concrete non-empty string (an unstated Expected cannot be
  466	    falsified — design §0.5-4).
  467	    """
  468	    for cell in _CELLS:
  469	        assert cell.expected and "=" in cell.expected
  470	    assert len({cell.expected for cell in _CELLS}) >= 3
  471	
  472	
  473	def test_a_store_no_writer_ever_touched_is_refused_not_fabricated(tmp_path) -> None:
  474	    """The reader derives from the store — it does not emit a constant.
  475	
  476	    Without this, a reader that ignored the store and printed the conservative anchor
  477	    unconditionally would pass every cell above. Here there is nothing to reload, so the
  478	    only correct behaviour is a refusal (fail-closed), never a plausible-looking
  479	    composite.
  480	    """
  481	    store = tmp_path / "never-written.sqlite3"
  482	    cache = tmp_path / "never-written.cache.json"
  483	    reader = _spawn("reader", "L3-01", store, cache)
  484	    assert reader.returncode != 0, f"an empty store produced a verdict: {reader.stdout}"
  485	    assert (
  486	        "IncompleteStoreError" in reader.stderr
  487	        or "cannot be identified" in reader.stderr
  488	    )
  489	
  490	
  491	def test_the_verdict_follows_the_store_not_the_scenario_argument(
  492	    crash_runs: dict[str, dict],
  493	) -> None:
  494	    """Reading L3-07's store while claiming to be L3-01 must report L3-07's state.
  495	
  496	    This separates "the reader re-derived state from durable bytes" from "the reader
  497	    looked up an answer by scenario id". Only the former is evidence of reconstruction.
  498	    """
  499	    seven = crash_runs["L3-07"]
  500	    reader = _spawn("reader", "L3-01", seven["store"], seven["cache"])
  501	    assert reader.returncode == 0, reader.stderr
  502	    verdict = json.loads(reader.stdout.strip().splitlines()[-1])
  503	    observed = _canonical(tuple(verdict[key] for key in _DIMENSION_KEYS))
  504	    assert observed == _CELLS_BY_ID["L3-07"].expected
  505	    assert observed != _CELLS_BY_ID["L3-01"].expected
  506	
  507	
  508	def test_this_suite_never_imports_the_kernel_it_measures() -> None:
  509	    """TOS-FW-R as a *local* canary — the oracle-independence guarantee (§5.3 / O-3).
  510	
  511	    The repo-wide firewall gate already enforces this, but a gate that lives elsewhere
  512	    can be skipped; asserting it here means the independence claim fails **in the same
  513	    suite that depends on it**. Checked over the parsed syntax tree, because a string
  514	    such as the worker's module path legitimately contains ``tos`` and a substring scan
  515	    would either miss a real import or reject that string.
  516	    """
  517	    import ast
  518	
  519	    for path in sorted(Path(__file__).parent.glob("*.py")):
  520	        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
  521	        for node in ast.walk(tree):
  522	            if isinstance(node, ast.Import):
  523	                for alias in node.names:
  524	                    assert not (
  525	                        alias.name == "tos" or alias.name.startswith("tos.")
  526	                    ), f"{path.name}:{node.lineno} imports {alias.name}"
  527	            elif isinstance(node, ast.ImportFrom):
  528	                module = node.module or ""
  529	                assert not (
  530	                    not node.level and (module == "tos" or module.startswith("tos."))
  531	                ), f"{path.name}:{node.lineno} imports from {module}"
  532	
```

---- SOURCE tos/src/tos/staterestore/__init__.py (full) ----
```
    1	"""Durable composite-state store + conservative restart reload (EV-L3 pilot).
    2	
    3	Realizes the ADR-002-005 §13 line 195-199 persistence-and-restart SHALLs on a **real
    4	on-disk substrate**, per the ratified design contract
    5	``docs/plans/2026-08-06-tos-ev-l3-pilot-design.md`` (v1.1) §5.1 S-1..S-4. This is the
    6	first ``tos`` package that performs real I/O: the series' closed-world → open-world
    7	transition (design #39 §2.1).
    8	
    9	What this package adds, and what it deliberately does not
   10	--------------------------------------------------------
   11	It adds **local durable persistence only** — a sqlite3 file on the local filesystem.
   12	It adds **no egress**: the tos-wide invariant ``tos/__init__.py`` line 6 verbatim
   13	"This package is non-transmitting by construction (§4): no broker credentials, routes,
   14	order-construction, or env-flag capability paths" is preserved unchanged (design #39
   15	§5.1 MINOR-3 — *persistence (local disk) ≠ transmission (network egress)*). There is no
   16	socket, no broker route, no credential, and no env-flag capability path here; the
   17	firewall gate (``tools/tos_firewall_check.py``) mechanizes that as
   18	``TOS-FW-B``/``TOS-FW-C``, and ``tos/tests/staterestore/test_staterestore_gaps.py``
   19	locks it as an executable canary.
   20	
   21	It is a **separate package, not a module inside** :mod:`tos.orthostate`: that package's
   22	own docstring (line 11) states verbatim that it implements "**no** persistence / durable
   23	restart", and adding a store there would falsify it. staterestore depends on orthostate
   24	(one direction only); orthostate never references staterestore (design #39 OQ-4(i)).
   25	
   26	Substrate decision and its status
   27	---------------------------------
   28	The store is stdlib ``sqlite3`` in WAL journal mode with ``synchronous=FULL`` (design
   29	#39 §3.2 candidate A). This is a **pilot-scope** choice — the substrate an EV-L3
   30	crash/restart run is executed against — and is explicitly **NOT** the ADR-002-005 §4
   31	line 61 project persistence-technology decision ("This ADR does not decide the
   32	persistence technology"), which remains an open governance gate (design #39 §3.3 /
   33	OQ-1).
   34	
   35	Crash model
   36	-----------
   37	:mod:`tos.staterestore._l3_worker` crashes with a deterministic ``os._exit`` at a
   38	parametrized point (design #39 §4 / O-2 — *not* a racy external ``SIGKILL``). That
   39	models an **application/process** crash faithfully; kernel page-cache loss, power loss,
   40	and torn sectors are **not** modelled and are carried as residual R-D (§2.4).
   41	
   42	Public surface
   43	--------------
   44	* :mod:`tos.staterestore.store` — :class:`CompositeStateStore`, the per-dimension
   45	  durable marker store (S-1).
   46	* :mod:`tos.staterestore.reload` — :func:`reload_conservative`, the restart read path
   47	  (S-2 conservative fill + S-3 no-stale re-derivation).
   48	* :mod:`tos.staterestore._l3_worker` — the ``python -m`` writer/reader entry point
   49	  (S-4), parametrized by **argv only** (``os.environ`` / ``os.getenv`` are forbidden
   50	  anywhere under ``tos/`` by TOS-FW-C).
   51	
   52	⚠ Authoring is not evidence: this package closes no Evidence Register row. STATE-EV-004
   53	remains NOT_IMPLEMENTED, and an executed EV-L3 stage covers its persistence + process +
   54	reconstruction axes only — real network and real credential identity stay deferred
   55	(design #39 §9; residuals R-N / R-I).
   56	"""
   57	
   58	from __future__ import annotations
   59	
   60	from tos.staterestore.reload import (
   61	    ABSENT_DIMENSION_FILL,
   62	    IncompleteStoreError,
   63	    RestartReconstruction,
   64	    discard_caches,
   65	    reload_conservative,
   66	)
   67	from tos.staterestore.store import (
   68	    DIMENSION_COMMIT_ORDER,
   69	    CompositeStateStore,
   70	    StoreIntegrityError,
   71	)
   72	
   73	__all__ = [
   74	    "ABSENT_DIMENSION_FILL",
   75	    "CompositeStateStore",
   76	    "DIMENSION_COMMIT_ORDER",
   77	    "IncompleteStoreError",
   78	    "RestartReconstruction",
   79	    "StoreIntegrityError",
   80	    "discard_caches",
   81	    "reload_conservative",
   82	]
   83	
```

---- SOURCE tos/src/tos/staterestore/store.py (full) ----
```
    1	"""S-1 — the durable per-dimension composite marker store (design #39 §5.1).
    2	
    3	ADR-002-005 §13 line 197 verbatim: "All five dimensions SHALL be durable and
    4	reconstructable after crash, restart, or failover." This module realizes the *durable*
    5	half on a real on-disk substrate; :mod:`tos.staterestore.reload` realizes the
    6	*reconstructable* half.
    7	
    8	Substrate
    9	---------
   10	stdlib ``sqlite3``, ``journal_mode=WAL``, ``synchronous=FULL`` (design #39 §3.2 A). Two
   11	properties are load-bearing and both are falsifiable (§3.4):
   12	
   13	* **durable commit** — a committed row survives an ``os._exit`` crash and is read back
   14	  by a *fresh process*. Falsified by: a post-commit crash losing a committed row.
   15	* **incomplete-store rollback** — writes that were still inside a transaction when the
   16	  process died roll back on reopen, so a reader observes the last committed state and
   17	  never a half-written row. Falsified by: a reopened store exposing a torn record.
   18	
   19	Per-dimension transactions
   20	--------------------------
   21	The five dimensions are committed in :data:`DIMENSION_COMMIT_ORDER`, **one transaction
   22	per dimension**. That is what makes the STATE-EV-004 line 1045 injection points
   23	realizable: a crash *between* two of those transactions is a legitimate "incomplete
   24	store", not a corruption. The order follows the ADR's own write-ahead ordering —
   25	identity and capacity are durable before the send boundary, the attempt marker
   26	(``SEND_STARTED``) is durable **before** the external call (§6 line 96), broker evidence
   27	can only follow the call (§7 line 104), and knowledge/evidence is persisted last (line
   28	1045 "before evidence persistence").
   29	
   30	This module is non-transmitting: it opens a local file and nothing else. No socket, no
   31	route, no credential, no ambient env (``tos/__init__.py`` line 6; TOS-FW-B / TOS-FW-C).
   32	"""
   33	
   34	from __future__ import annotations
   35	
   36	import sqlite3
   37	from pathlib import Path
   38	from types import TracebackType
   39	
   40	from tos.orthostate import (
   41	    BrokerOrderState,
   42	    CompositeState,
   43	    IntentState,
   44	    KnowledgeState,
   45	    StateDimension,
   46	    TransmissionAttemptState,
   47	)
   48	from tos.rcl import CapacityState
   49	
   50	#: The fixed per-dimension commit order (see the module docstring). A crash after the
   51	#: *k*-th entry leaves exactly the first *k* dimensions durable — that is the whole
   52	#: mechanism behind the design #39 §4 "incomplete store" cell.
   53	DIMENSION_COMMIT_ORDER: tuple[StateDimension, ...] = (
   54	    StateDimension.INTENT,
   55	    StateDimension.CAPACITY,
   56	    StateDimension.TRANSMISSION_ATTEMPT,
   57	    StateDimension.BROKER_ORDER,
   58	    StateDimension.KNOWLEDGE,
   59	)
   60	
   61	#: The composite attribute each dimension marker carries.
   62	_DIMENSION_FIELD: dict[StateDimension, str] = {
   63	    StateDimension.INTENT: "intent_state",
   64	    StateDimension.TRANSMISSION_ATTEMPT: "transmission_attempt_state",
   65	    StateDimension.BROKER_ORDER: "broker_order_state",
   66	    StateDimension.KNOWLEDGE: "knowledge_state",
   67	    StateDimension.CAPACITY: "capacity_state",
   68	}
   69	
   70	#: The enum each dimension's stored string is coerced back through on reload. A value
   71	#: that is not a member of its own dimension's enum is a :class:`StoreIntegrityError`,
   72	#: never a silently-accepted string: global string-value distinctness across the five
   73	#: dimension enums (design #8 §2.2) is what makes a dimension swap detectable, and
   74	#: skipping the coercion would discard exactly that canary.
   75	_DIMENSION_ENUM: dict[StateDimension, type] = {
   76	    StateDimension.INTENT: IntentState,
   77	    StateDimension.TRANSMISSION_ATTEMPT: TransmissionAttemptState,
   78	    StateDimension.BROKER_ORDER: BrokerOrderState,
   79	    StateDimension.KNOWLEDGE: KnowledgeState,
   80	    StateDimension.CAPACITY: CapacityState,
   81	}
   82	
   83	_SCHEMA = """
   84	CREATE TABLE IF NOT EXISTS dimension_marker (
   85	    intent_identity TEXT NOT NULL,
   86	    dimension       TEXT NOT NULL,
   87	    state_value     TEXT NOT NULL,
   88	    PRIMARY KEY (intent_identity, dimension)
   89	)
   90	"""
   91	
   92	
   93	class StoreIntegrityError(RuntimeError):
   94	    """A stored marker cannot be read back as a member of its own dimension.
   95	
   96	    Fail-closed: an unreadable store is never summarised as an empty one. "The store
   97	    holds nothing" and "the store holds something this code cannot interpret" are
   98	    different findings, and collapsing them would let a corrupted marker be re-derived
   99	    as an *absent* one — which the conservative fill would then quietly repair
  100	    (design #39 §0.5 O-1: the fail-open lives in the wiring, not in the predicate).
  101	    """
  102	
  103	
  104	class CompositeStateStore:
  105	    """A durable, per-dimension marker store for :class:`CompositeState` (S-1).
  106	
  107	    Usage is deliberately explicit rather than magical: the caller commits dimensions
  108	    one at a time (or all five through :meth:`commit_composite`), and each call is its
  109	    own transaction that has returned only after sqlite reports the commit. There is no
  110	    write buffer, no autocommit-deferred queue, and no in-process cache of what was
  111	    written — :meth:`read_markers` always re-reads the file.
  112	
  113	    Attributes:
  114	        path: The on-disk store file. It is a real filesystem path: an in-memory sqlite
  115	            database would make ``persistence_real`` unfalsifiable, which is the exact
  116	            EV-L2-pilot C1 defect ("in-memory redefinition") this stage exists to avoid.
  117	    """
  118	
  119	    def __init__(self, path: Path) -> None:
  120	        """Open (creating if needed) the store at ``path`` in WAL / synchronous=FULL."""
  121	        self.path = Path(path)
  122	        self.path.parent.mkdir(parents=True, exist_ok=True)
  123	        self._conn = sqlite3.connect(str(self.path), isolation_level=None)
  124	        self._conn.execute("PRAGMA journal_mode=WAL")
  125	        self._conn.execute("PRAGMA synchronous=FULL")
  126	        self._conn.execute(_SCHEMA)
  127	
  128	    # -- context manager ----------------------------------------------------
  129	
  130	    def __enter__(self) -> CompositeStateStore:
  131	        """Return self (the store is already open)."""
  132	        return self
  133	
  134	    def __exit__(
  135	        self,
  136	        exc_type: type[BaseException] | None,
  137	        exc: BaseException | None,
  138	        tb: TracebackType | None,
  139	    ) -> None:
  140	        """Close the connection."""
  141	        self.close()
  142	
  143	    def close(self) -> None:
  144	        """Close the sqlite connection. Committed rows are already durable."""
  145	        self._conn.close()
  146	
  147	    # -- write path ---------------------------------------------------------
  148	
  149	    def commit_dimension(
  150	        self,
  151	        intent_identity: str,
  152	        dimension: StateDimension,
  153	        state_value: str,
  154	    ) -> None:
  155	        """Commit one dimension marker in its own transaction.
  156	
  157	        The explicit ``BEGIN`` / ``COMMIT`` pair (``isolation_level=None`` disables
  158	        pysqlite's implicit transaction management) is what makes the transaction
  159	        boundary the *observable* crash boundary: a crash before ``COMMIT`` returns
  160	        leaves the marker absent, and a crash after it leaves the marker durable. There
  161	        is no third outcome for a reader to see.
  162	
  163	        Args:
  164	            intent_identity: The immutable intent identity the marker belongs to
  165	                (ADR-002-005 §5 line 76 SAFE-020).
  166	            dimension: Which of the five orthogonal dimensions this marker carries.
  167	            state_value: The dimension's state as its spec string.
  168	        """
  169	        self._conn.execute("BEGIN")
  170	        self._conn.execute(
  171	            "INSERT INTO dimension_marker (intent_identity, dimension, state_value) "
  172	            "VALUES (?, ?, ?) "
  173	            "ON CONFLICT(intent_identity, dimension) DO UPDATE SET state_value=excluded.state_value",
  174	            (intent_identity, str(dimension), str(state_value)),
  175	        )
  176	        self._conn.execute("COMMIT")
  177	
  178	    def commit_composite(
  179	        self,
  180	        composite: CompositeState,
  181	        *,
  182	        stop_after: int | None = None,
  183	    ) -> tuple[StateDimension, ...]:
  184	        """Commit the composite's five dimensions, one transaction each.
  185	
  186	        Args:
  187	            composite: The observation whose dimensions become durable. Its
  188	                ``intent_identity`` is required — an unidentified record cannot be
  189	                re-associated after a restart, and storing it under a synthesised key
  190	                would fabricate the identity the reload path is supposed to re-derive.
  191	            stop_after: Commit only the first ``stop_after`` dimensions of
  192	                :data:`DIMENSION_COMMIT_ORDER` (``None`` = all five). This is how an
  193	                *incomplete store* is produced deliberately; it is not a crash by
  194	                itself.
  195	
  196	        Returns:
  197	            The dimensions actually committed, in commit order.
  198	
  199	        Raises:
  200	            StoreIntegrityError: If the composite carries no ``intent_identity``.
  201	        """
  202	        identity = composite.intent_identity
  203	        if not identity:
  204	            raise StoreIntegrityError(
  205	                "CompositeState.intent_identity is required to persist a composite: "
  206	                "an unidentified durable record cannot be reconstructed after restart"
  207	            )
  208	        limit = len(DIMENSION_COMMIT_ORDER) if stop_after is None else stop_after
  209	        committed: list[StateDimension] = []
  210	        for dimension in DIMENSION_COMMIT_ORDER[:limit]:
  211	            value = getattr(composite, _DIMENSION_FIELD[dimension])
  212	            self.commit_dimension(identity, dimension, str(value))
  213	            committed.append(dimension)
  214	        return tuple(committed)
  215	
  216	    # -- read path ----------------------------------------------------------
  217	
  218	    def read_markers(self, intent_identity: str) -> dict[StateDimension, object]:
  219	        """Re-read the durable markers for ``intent_identity`` from the file.
  220	
  221	        Returns:
  222	            A mapping of the dimensions actually present to their coerced enum values.
  223	            An absent dimension is simply **not a key** — the caller decides what an
  224	            absence means (:mod:`tos.staterestore.reload` fills it conservatively), and
  225	            this method never invents a default of its own.
  226	
  227	        Raises:
  228	            StoreIntegrityError: If a stored string is not a member of its dimension's
  229	                enum, or the row names a dimension outside the five.
  230	        """
  231	        rows = self._conn.execute(
  232	            "SELECT dimension, state_value FROM dimension_marker "
  233	            "WHERE intent_identity = ?",
  234	            (intent_identity,),
  235	        ).fetchall()
  236	        markers: dict[StateDimension, object] = {}
  237	        for raw_dimension, raw_value in rows:
  238	            try:
  239	                dimension = StateDimension(raw_dimension)
  240	            except ValueError as exc:
  241	                raise StoreIntegrityError(
  242	                    f"stored row names an unknown dimension {raw_dimension!r}"
  243	                ) from exc
  244	            enum_type = _DIMENSION_ENUM[dimension]
  245	            try:
  246	                markers[dimension] = enum_type(raw_value)
  247	            except ValueError as exc:
  248	                raise StoreIntegrityError(
  249	                    f"stored {dimension} marker {raw_value!r} is not a member of "
  250	                    f"{enum_type.__name__} — a marker that cannot be read back is a "
  251	                    "corrupt record, not an absent one"
  252	                ) from exc
  253	        return markers
  254	
```

---- SOURCE tos/src/tos/staterestore/reload.py (full) ----
```
    1	"""S-2 / S-3 — the restart read path: conservative fill, then re-derivation.
    2	
    3	ADR-002-005 §13, the three SHALLs this module realizes (design #39 §5.1):
    4	
    5	* line 197 "All five dimensions SHALL be durable and **reconstructable** after crash,
    6	  restart, or failover" — the store is re-read from disk by a *fresh process* and a
    7	  composite is rebuilt from it.
    8	* line 198 "On restart, any Attempt that reached ``SEND_STARTED`` and any Broker Order
    9	  that is not provably terminal SHALL be treated as ``POTENTIALLY_LIVE``/``UNKNOWN``
   10	  until reconciled" — delegated verbatim to
   11	  :func:`tos.orthostate.reconstruct_conservative`; this module does **not** re-author it.
   12	* line 199 "Knowledge SHALL be re-derived from evidence, defaulting to
   13	  ``UNOBSERVED``/``CONFLICTED``, never to ``RECONCILED``".
   14	
   15	S-2 — the per-dimension conservative fill
   16	-----------------------------------------
   17	An incomplete store (STATE-EV-004 line 1045 "restart with incomplete stores") leaves
   18	some dimension absent. Absence is **not** an excuse to guess favourably, so each
   19	dimension's fill value is argued from the spec rather than picked for convenience
   20	(design #39 §5.1 S-2, table :data:`ABSENT_DIMENSION_FILL`):
   21	
   22	* **Knowledge → ``UNOBSERVED``.** §13 line 199 permits ``UNOBSERVED``/``CONFLICTED``
   23	  and forbids ``RECONCILED``. Of the two permitted values the natural reading of "no
   24	  durable evidence" is ``UNOBSERVED`` — an *absence of observation* — whereas
   25	  ``CONFLICTED`` would assert a conflict that was never observed. The load-bearing
   26	  guarantee is nevertheless the **negative** one, ``knowledge ∉ {RECONCILED,
   27	  CONSISTENT}``: the positive value is a deterministic anchor, the negative invariant is
   28	  what the outside oracle checks independently.
   29	* **Broker Order → ``UNKNOWN``.** §13 line 198 — a broker order that is not *provably*
   30	  terminal is ``UNKNOWN``; no durable evidence is the weakest possible proof. ``UNKNOWN``
   31	  is capacity-consuming and never means rejected / cancelled / safe-to-retry (§1 line
   32	  27).
   33	* **Transmission Attempt → ``NONE``.** §6 line 96 makes the transition into
   34	  ``SEND_STARTED`` durable **before** the external call, so a store with no attempt
   35	  marker structurally implies the external call had not been made. This is a *structural*
   36	  safe reading derived from the write-ahead ordering, not an optimistic default.
   37	* **Capacity → ``POTENTIALLY_LIVE``.** The CPL-1 minimum for a possibly-live effect
   38	  (§10 line 156). ``reconstruct_conservative`` may raise it further but never lowers it.
   39	* **Intent → refused.** An absent intent marker means the record cannot be identified,
   40	  and a reconstruction that invented an identity would be a fabrication rather than a
   41	  re-derivation. :class:`IncompleteStoreError` is raised (fail-closed).
   42	
   43	S-3 — no stale cache
   44	--------------------
   45	Caches are **discarded** on resume and the composite is re-derived from the store alone
   46	(§13 line 199 "re-derived from evidence"; line 1045 "stale caches"). :func:`discard_caches`
   47	unlinks them, so "the reader ignored the cache" is observable as *the cache is gone*
   48	rather than as an absence of a code path. :func:`reload_conservative` has no parameter,
   49	branch, or fallback that could consume a cache's contents.
   50	
   51	Non-transmitting: this module reads a local file. No socket, no route, no credential
   52	(``tos/__init__.py`` line 6).
   53	"""
   54	
   55	from __future__ import annotations
   56	
   57	from dataclasses import dataclass
   58	from pathlib import Path
   59	
   60	from tos.orthostate import (
   61	    BrokerOrderState,
   62	    CompositeState,
   63	    KnowledgeState,
   64	    StateDimension,
   65	    TransmissionAttemptState,
   66	    reconstruct_conservative,
   67	)
   68	from tos.rcl import CapacityState
   69	from tos.staterestore.store import DIMENSION_COMMIT_ORDER, CompositeStateStore
   70	
   71	#: The S-2 conservative fill for an absent dimension (argued in the module docstring).
   72	#: ``StateDimension.INTENT`` is deliberately **absent from this table**: there is no
   73	#: conservative value for "which intent is this", so an absent intent marker is refused
   74	#: rather than filled. A future edit that adds an INTENT entry here would be adding a
   75	#: fabricated identity, and :mod:`tos.tests.staterestore` fails if the key appears.
   76	ABSENT_DIMENSION_FILL: dict[StateDimension, object] = {
   77	    StateDimension.TRANSMISSION_ATTEMPT: TransmissionAttemptState.NONE,
   78	    StateDimension.BROKER_ORDER: BrokerOrderState.UNKNOWN,
   79	    StateDimension.KNOWLEDGE: KnowledgeState.UNOBSERVED,
   80	    StateDimension.CAPACITY: CapacityState.POTENTIALLY_LIVE,
   81	}
   82	
   83	
   84	class IncompleteStoreError(RuntimeError):
   85	    """The store cannot identify the record it holds (fail-closed).
   86	
   87	    Raised when the Intent dimension is absent. Every other dimension has a defensible
   88	    conservative fill; identity does not, and a reconstruction under a synthesised
   89	    identity would attach conservative state to the wrong trading action.
   90	    """
   91	
   92	
   93	@dataclass(frozen=True)
   94	class RestartReconstruction:
   95	    """The outcome of one restart reload (design #39 §5.1 S-2).
   96	
   97	    Attributes:
   98	        pre_restart: The composite as re-derived from the store, with absent dimensions
   99	            conservatively filled — the *input* to the §13 projection.
  100	        composite: The post-restart composite, i.e.
  101	            ``reconstruct_conservative(pre_restart)``. This is the authoritative result.
  102	        store_complete: Whether all five dimensions were durable (no fill applied).
  103	        filled_dimensions: The dimensions that were absent and conservatively filled, in
  104	            :data:`tos.staterestore.store.DIMENSION_COMMIT_ORDER`. Reported so a caller
  105	            can tell "the store said ``UNKNOWN``" from "the store said nothing and the
  106	            reload chose ``UNKNOWN``" — collapsing those two would hide an incomplete
  107	            store behind a value that happens to look the same.
  108	        discarded_caches: The cache files unlinked before re-derivation (S-3).
  109	    """
  110	
  111	    pre_restart: CompositeState
  112	    composite: CompositeState
  113	    store_complete: bool
  114	    filled_dimensions: tuple[StateDimension, ...]
  115	    discarded_caches: tuple[str, ...]
  116	
  117	
  118	def discard_caches(cache_paths: tuple[Path, ...] | list[Path]) -> tuple[str, ...]:
  119	    """Discard resume-time caches (S-3) and report which ones existed.
  120	
  121	    Unlinking rather than merely not-reading is the point: after this call the optimistic
  122	    cache is *gone*, so a later regression that tried to consult one would have nothing
  123	    to consult. The return value is the executable observation that a cache was present
  124	    and was dropped, which is what distinguishes "the stale-cache scenario ran" from
  125	    "no cache was ever written".
  126	
  127	    Args:
  128	        cache_paths: Candidate cache files. A path that does not exist is simply not
  129	            reported; discarding is idempotent.
  130	
  131	    Returns:
  132	        The string paths of the caches that existed and were removed.
  133	    """
  134	    discarded: list[str] = []
  135	    for path in cache_paths:
  136	        candidate = Path(path)
  137	        if candidate.is_file():
  138	            candidate.unlink()
  139	            discarded.append(str(candidate))
  140	    return tuple(discarded)
  141	
  142	
  143	def reload_conservative(
  144	    store_path: Path,
  145	    intent_identity: str,
  146	    *,
  147	    cache_paths: tuple[Path, ...] | list[Path] = (),
  148	    state_model_version: str | None = None,
  149	) -> RestartReconstruction:
  150	    """Re-derive a conservative post-restart composite from the durable store alone.
  151	
  152	    The sequence is fixed and has no alternative branch: discard caches (S-3), read the
  153	    store from disk (S-1), fill absent dimensions conservatively (S-2), then apply the
  154	    §13 projection :func:`tos.orthostate.reconstruct_conservative`. The projection is
  155	    **not** re-implemented here — re-authoring it would make this module both the guard
  156	    and the oracle, which is the failure mode design #39 §5.3 exists to structurally
  157	    prevent.
  158	
  159	    Args:
  160	        store_path: The on-disk store written before the crash.
  161	        intent_identity: The identity whose markers are re-derived.
  162	        cache_paths: Optimistic caches to discard before re-deriving (S-3).
  163	        state_model_version: Carried onto the rebuilt composite when known.
  164	
  165	    Returns:
  166	        The :class:`RestartReconstruction`.
  167	
  168	    Raises:
  169	        IncompleteStoreError: If the Intent dimension is absent (unidentifiable record).
  170	        tos.staterestore.store.StoreIntegrityError: If a stored marker is unreadable.
  171	    """
  172	    discarded = discard_caches(cache_paths)
  173	    with CompositeStateStore(Path(store_path)) as store:
  174	        markers = store.read_markers(intent_identity)
  175	
  176	    if StateDimension.INTENT not in markers:
  177	        raise IncompleteStoreError(
  178	            f"no durable Intent marker for {intent_identity!r}: the record cannot be "
  179	            "identified, so it is refused rather than reconstructed under a "
  180	            "synthesised identity"
  181	        )
  182	
  183	    filled: list[StateDimension] = []
  184	    resolved: dict[StateDimension, object] = {}
  185	    for dimension in DIMENSION_COMMIT_ORDER:
  186	        if dimension not in ABSENT_DIMENSION_FILL:
  187	            continue  # Intent: refused above, never filled
  188	        if dimension in markers:
  189	            resolved[dimension] = markers[dimension]
  190	        else:
  191	            resolved[dimension] = ABSENT_DIMENSION_FILL[dimension]
  192	            filled.append(dimension)
  193	
  194	    pre = CompositeState(
  195	        intent_identity=intent_identity,
  196	        intent_state=markers[StateDimension.INTENT],
  197	        transmission_attempt_state=resolved[StateDimension.TRANSMISSION_ATTEMPT],
  198	        broker_order_state=resolved[StateDimension.BROKER_ORDER],
  199	        knowledge_state=resolved[StateDimension.KNOWLEDGE],
  200	        capacity_state=resolved[StateDimension.CAPACITY],
  201	        state_model_version=state_model_version,
  202	    )
  203	    return RestartReconstruction(
  204	        pre_restart=pre,
  205	        composite=reconstruct_conservative(pre),
  206	        store_complete=not filled,
  207	        filled_dimensions=tuple(filled),
  208	        discarded_caches=discarded,
  209	    )
  210	
```

---- SOURCE tos/src/tos/staterestore/_l3_worker.py (full) ----
```
    1	"""S-4 — the ``python -m`` crash/restart worker (design #39 §5.1 / §5.2).
    2	
    3	Two modes, one process each::
    4	
    5	    python -m tos.staterestore._l3_worker writer <scenario-id> <store-path> <cache-path>
    6	    python -m tos.staterestore._l3_worker reader <scenario-id> <store-path> <cache-path>
    7	
    8	The **writer** commits the scenario's durable markers and then dies at the scenario's
    9	parametrized crash point via ``os._exit(137)`` — a *deterministic* application crash,
   10	not a racy externally-delivered ``SIGKILL`` (design #39 O-2 / OQ-3). Nothing is flushed,
   11	unwound, or finalized: whatever sqlite had already committed is all that survives.
   12	
   13	The **reader** is a *fresh* process. Its only channel to the writer is the on-disk store,
   14	which is precisely what VER-002-001 §5 line 151-153 means by "real persistence …
   15	boundaries". It reloads through :func:`tos.staterestore.reload_conservative` and prints
   16	one JSON verdict object on stdout.
   17	
   18	Parametrization is **argv only.** ``os.environ`` / ``os.getenv`` is forbidden anywhere
   19	under ``tos/`` by the firewall's TOS-FW-C rule (``tools/tos_firewall_check.py`` lines
   20	214-216 / 237-240), because capability must not be reachable through ambient env. The
   21	same AST gate detects **only** ``environ``/``getenv`` on ``os``, so the ``os._exit``
   22	below is gate-clean; the ``tos/tests`` convention of avoiding ``os`` entirely
   23	(``tos/tests/test_import_closure.py`` line 6) is an *import-closure isolation* practice
   24	for those tests, not a firewall rule (design #39 §5.1, measured).
   25	
   26	Oracle independence
   27	-------------------
   28	This module owns the crash scenarios' **inputs** (which composite is committed, and
   29	where the crash lands). It does **not** own their expected outputs. The Expected
   30	reconstructions live in the outside orchestration
   31	(``tests/tos_l3/test_state_ev_004_crash_restart.py``) as hand-derived hardcoded anchors,
   32	which the firewall's reverse rule (TOS-FW-R) structurally prevents from calling
   33	``reconstruct_conservative`` at all (design #39 §5.3 / O-3). A bug in the implementation
   34	therefore cannot make the oracle agree with it.
   35	
   36	Commit-composite legality
   37	-------------------------
   38	Several §4 cells pin composites that ADR-002-005 §14 lists as valid *observations* while
   39	the static CPL predicate flags them (``Broker=UNKNOWN`` forces CPL-5's exact
   40	``QUARANTINED_UNKNOWN``). Design #39 §4 makes checking that legality an implementation
   41	obligation, so every scenario carries its **expected CPL violation set** and the writer
   42	compares :func:`tos.orthostate.coupling_violations` against it before committing
   43	anything. A disagreement aborts loudly with exit code
   44	:data:`CPL_MISMATCH_EXIT` — never a silent commit (see
   45	:data:`SCENARIOS` for the per-cell justification).
   46	"""
   47	
   48	from __future__ import annotations
   49	
   50	import json
   51	import os
   52	import sys
   53	from dataclasses import dataclass
   54	from pathlib import Path
   55	from typing import NoReturn
   56	
   57	from tos.orthostate import (
   58	    BrokerOrderState,
   59	    CompositeState,
   60	    CouplingSideConditions,
   61	    IntentState,
   62	    KnowledgeState,
   63	    StateDimension,
   64	    TransmissionAttemptState,
   65	    coupling_violations,
   66	)
   67	from tos.rcl import CapacityState
   68	from tos.staterestore.reload import reload_conservative
   69	from tos.staterestore.store import CompositeStateStore
   70	
   71	#: The deterministic crash status. 137 is the conventional "killed" code; the value is a
   72	#: constant so the outside orchestration can assert the crash was *the parametrized one*
   73	#: and not an ordinary interpreter failure (which exits 1) or a refusal (see below).
   74	CRASH_EXIT = 137
   75	
   76	#: The writer aborts with this code when a scenario's committed composite does not carry
   77	#: the CPL violation set the scenario pins. A wrong-but-committed composite would make
   78	#: every downstream anchor meaningless, so this is loud and terminal.
   79	CPL_MISMATCH_EXIT = 70
   80	
   81	#: Usage / unknown-scenario refusal.
   82	USAGE_EXIT = 64
   83	
   84	#: The intent identity every scenario uses. Fixed, so a run is reproducible from argv
   85	#: alone (VER §9.1 seed/schedule reproducibility).
   86	INTENT_IDENTITY = "STATE-EV-004-L3-PILOT-INTENT"
   87	
   88	#: The side-conditions the committed composites are evaluated under. ``authority_epoch_
   89	#: current=True`` is the *only* positive flag: every §4 cell has an attempt at or beyond
   90	#: ``SEND_STARTED``, and CPL-6 requires a current authority epoch for exactly those. The
   91	#: remaining flags stay ``None`` (fail-closed), so no proof is asserted that the scenario
   92	#: does not actually establish.
   93	COMMIT_SIDE_CONDITIONS = CouplingSideConditions(authority_epoch_current=True)
   94	
   95	
   96	@dataclass(frozen=True)
   97	class CrashScenario:
   98	    """One design #39 §4 catalog cell, as the worker's *input* half.
   99	
  100	    Attributes:
  101	        scenario_id: The catalog id (``L3-01`` … ``L3-08``).
  102	        intent_state: Pinned Intent dimension.
  103	        transmission_attempt_state: Pinned Transmission Attempt dimension.
  104	        broker_order_state: Pinned Broker Order dimension.
  105	        knowledge_state: Pinned Knowledge dimension — the value that is made **durable**.
  106	        capacity_state: Pinned Capacity dimension.
  107	        commit_dimension_count: How many of :data:`DIMENSION_COMMIT_ORDER`'s five
  108	            dimensions are committed before the crash. ``5`` = complete store; anything
  109	            less produces the line 1045 "incomplete store" by crashing between two
  110	            per-dimension transactions.
  111	        write_stale_cache: Whether an *optimistic* cache file is written after the
  112	            markers (line 1045 "stale caches"). Its content is deliberately the most
  113	            favourable knowledge value there is.
  114	        uncommitted_knowledge: An in-memory knowledge value the process held but never
  115	            persisted — the "crash **before evidence persistence**" limb of line 1045.
  116	            It dies with the process, which is the whole point: the reader must not
  117	            resurrect it.
  118	        expected_cpl: The CPL invariant ids the committed composite is expected to
  119	            raise. See :data:`SCENARIOS` for why several cells are non-empty.
  120	        note: Why this cell exists, in one line.
  121	    """
  122	
  123	    scenario_id: str
  124	    intent_state: IntentState
  125	    transmission_attempt_state: TransmissionAttemptState
  126	    broker_order_state: BrokerOrderState
  127	    knowledge_state: KnowledgeState
  128	    capacity_state: CapacityState
  129	    commit_dimension_count: int
  130	    expected_cpl: frozenset[str]
  131	    note: str
  132	    write_stale_cache: bool = False
  133	    uncommitted_knowledge: KnowledgeState | None = None
  134	
  135	    def composite(self) -> CompositeState:
  136	        """The pinned five-dimension composite this scenario makes durable."""
  137	        return CompositeState(
  138	            intent_identity=INTENT_IDENTITY,
  139	            intent_state=self.intent_state,
  140	            transmission_attempt_state=self.transmission_attempt_state,
  141	            broker_order_state=self.broker_order_state,
  142	            knowledge_state=self.knowledge_state,
  143	            capacity_state=self.capacity_state,
  144	        )
  145	
  146	
  147	#: ``{CPL-5}`` — ADR-002-005 §10 line 160 makes ``Broker=UNKNOWN`` (or Knowledge in
  148	#: ``{CONFLICTED, QUARANTINED}``) demand ``Capacity=QUARANTINED_UNKNOWN`` *exactly*,
  149	#: while §14 lists ``Broker=UNKNOWN`` with ``Capacity=POTENTIALLY_LIVE`` among its "all
  150	#: valid" composites (line 208, verbatim). The repository already resolves that tension
  151	#: the same way — ``tos/tests/orthostate/_orthostate_strategies.py`` lines 147 and 167
  152	#: label the two affected §14 rows "representable BUT coupling-negative (… fires CPL-5)"
  153	#: — so these composites are *representable observations that carry a flagged coupling*,
  154	#: which is exactly the state a crash can leave behind. Pinning the expected set (rather
  155	#: than demanding ``∅``) keeps the check loud: a composite whose CPL status differs from
  156	#: this pin aborts the writer.
  157	_CPL5 = frozenset({"CPL-5"})
  158	_CPL_CLEAN: frozenset[str] = frozenset()
  159	
  160	#: The design #39 §4 catalog, eight cells. Every dimension is pinned (§4 MAJOR-2): the
  161	#: outside anchors are derived from these by hand, so an unpinned dimension would make
  162	#: an anchor underdetermined.
  163	SCENARIOS: dict[str, CrashScenario] = {
  164	    "L3-01": CrashScenario(
  165	        scenario_id="L3-01",
  166	        intent_state=IntentState.ACTIVE,
  167	        transmission_attempt_state=TransmissionAttemptState.SEND_STARTED,
  168	        broker_order_state=BrokerOrderState.UNKNOWN,
  169	        knowledge_state=KnowledgeState.UNOBSERVED,
  170	        capacity_state=CapacityState.POTENTIALLY_LIVE,
  171	        commit_dimension_count=5,
  172	        expected_cpl=_CPL5,
  173	        note="crash after durable SEND_STARTED, before the broker received anything",
  174	    ),
  175	    "L3-02": CrashScenario(
  176	        scenario_id="L3-02",
  177	        intent_state=IntentState.ACTIVE,
  178	        transmission_attempt_state=TransmissionAttemptState.SENT_UNCONFIRMED,
  179	        broker_order_state=BrokerOrderState.UNKNOWN,
  180	        knowledge_state=KnowledgeState.UNOBSERVED,
  181	        capacity_state=CapacityState.POTENTIALLY_LIVE,
  182	        commit_dimension_count=5,
  183	        expected_cpl=_CPL5,
  184	        note=(
  185	            "crash after the (modelled) network transmission — the transmission is a "
  186	            "VirtualBroker-class marker, zero real bytes; real broker network is "
  187	            "residual R-N"
  188	        ),
  189	    ),
  190	    "L3-03": CrashScenario(
  191	        scenario_id="L3-03",
  192	        intent_state=IntentState.ACTIVE,
  193	        transmission_attempt_state=TransmissionAttemptState.SEND_STARTED,
  194	        broker_order_state=BrokerOrderState.UNKNOWN,
  195	        knowledge_state=KnowledgeState.UNOBSERVED,
  196	        capacity_state=CapacityState.POTENTIALLY_LIVE,
  197	        commit_dimension_count=5,
  198	        uncommitted_knowledge=KnowledgeState.RECONCILED,
  199	        expected_cpl=_CPL5,
  200	        note=(
  201	            "crash BEFORE evidence persistence: an in-memory ACK had already produced "
  202	            "an optimistic RECONCILED that was never made durable"
  203	        ),
  204	    ),
  205	    "L3-04": CrashScenario(
  206	        scenario_id="L3-04",
  207	        intent_state=IntentState.ACTIVE,
  208	        transmission_attempt_state=TransmissionAttemptState.SENT_UNCONFIRMED,
  209	        broker_order_state=BrokerOrderState.WORKING,
  210	        knowledge_state=KnowledgeState.UNOBSERVED,
  211	        capacity_state=CapacityState.POTENTIALLY_LIVE,
  212	        commit_dimension_count=5,
  213	        expected_cpl=_CPL_CLEAN,
  214	        note="crash at a NON-terminal broker-order boundary (WORKING)",
  215	    ),
  216	    "L3-05": CrashScenario(
  217	        scenario_id="L3-05",
  218	        intent_state=IntentState.ACTIVE,
  219	        transmission_attempt_state=TransmissionAttemptState.SEND_STARTED,
  220	        broker_order_state=BrokerOrderState.UNKNOWN,
  221	        knowledge_state=KnowledgeState.UNOBSERVED,
  222	        capacity_state=CapacityState.POTENTIALLY_LIVE,
  223	        commit_dimension_count=3,
  224	        expected_cpl=_CPL5,
  225	        note=(
  226	            "INCOMPLETE STORE: crash between per-dimension transactions, so Broker and "
  227	            "Knowledge never became durable at all"
  228	        ),
  229	    ),
  230	    "L3-06": CrashScenario(
  231	        scenario_id="L3-06",
  232	        intent_state=IntentState.ACTIVE,
  233	        transmission_attempt_state=TransmissionAttemptState.SENT_UNCONFIRMED,
  234	        broker_order_state=BrokerOrderState.WORKING,
  235	        knowledge_state=KnowledgeState.UNOBSERVED,
  236	        capacity_state=CapacityState.POTENTIALLY_LIVE,
  237	        commit_dimension_count=5,
  238	        write_stale_cache=True,
  239	        expected_cpl=_CPL_CLEAN,
  240	        note=(
  241	            "STALE CACHE: an optimistic RECONCILED cache file survives the crash beside "
  242	            "the conservative store"
  243	        ),
  244	    ),
  245	    "L3-07": CrashScenario(
  246	        scenario_id="L3-07",
  247	        intent_state=IntentState.ACTIVE,
  248	        transmission_attempt_state=TransmissionAttemptState.ACK_OBSERVED,
  249	        broker_order_state=BrokerOrderState.FILLED,
  250	        knowledge_state=KnowledgeState.RECONCILED,
  251	        capacity_state=CapacityState.POSITION_CONSUMED,
  252	        commit_dimension_count=5,
  253	        expected_cpl=_CPL_CLEAN,
  254	        note=(
  255	            "positive canary: ADR-002-005 §14 line 211 verbatim — a terminal broker "
  256	            "order with positive knowledge, so the §13 line 199 downgrade must FIRE"
  257	        ),
  258	    ),
  259	    "L3-08": CrashScenario(
  260	        scenario_id="L3-08",
  261	        intent_state=IntentState.ACTIVE,
  262	        transmission_attempt_state=TransmissionAttemptState.SENT_UNCONFIRMED,
  263	        broker_order_state=BrokerOrderState.UNKNOWN,
  264	        knowledge_state=KnowledgeState.CONFLICTED,
  265	        capacity_state=CapacityState.POTENTIALLY_LIVE,
  266	        commit_dimension_count=5,
  267	        expected_cpl=_CPL5,
  268	        note=(
  269	            "durability mechanism: ADR-002-005 §14 line 208 verbatim, already "
  270	            "conservative, so the projection is the identity and the reload must be a "
  271	            "lossless round-trip of the committed five dimensions"
  272	        ),
  273	    ),
  274	}
  275	
  276	#: What the optimistic cache file claims. The most favourable knowledge value there is,
  277	#: so a reader that trusted it would be caught by the ``never RECONCILED`` invariant.
  278	STALE_CACHE_KNOWLEDGE = KnowledgeState.RECONCILED
  279	
  280	
  281	def cache_payload(scenario: CrashScenario) -> str:
  282	    """The optimistic cache bytes for ``scenario`` (S-3 target)."""
  283	    return json.dumps(
  284	        {
  285	            "intent_identity": INTENT_IDENTITY,
  286	            "scenario_id": scenario.scenario_id,
  287	            "knowledge_state": str(STALE_CACHE_KNOWLEDGE),
  288	            "note": "optimistic resume cache — must be discarded, never consumed",
  289	        },
  290	        sort_keys=True,
  291	    )
  292	
  293	
  294	def _fail(message: str, code: int) -> NoReturn:
  295	    """Print ``message`` on stderr and exit ``code`` without unwinding.
  296	
  297	    Typed ``NoReturn`` so callers do not need a narrowing assertion after it: the
  298	    refusal really is terminal, and saying so in the signature is what makes the code
  299	    after a refusal unreachable rather than merely unreached.
  300	    """
  301	    sys.stderr.write(f"tos-l3-worker: {message}\n")
  302	    sys.stderr.flush()
  303	    os._exit(code)
  304	
  305	
  306	def run_writer(scenario: CrashScenario, store_path: Path, cache_path: Path) -> None:
  307	    """Commit the scenario's durable markers, then crash deterministically.
  308	
  309	    Never returns: the last statement is ``os._exit``.
  310	    """
  311	    composite = scenario.composite()
  312	
  313	    # Commit-composite legality (design #39 §4). Measured, then compared against the
  314	    # scenario's own pin — a mismatch is a defect in the catalog or in the predicate,
  315	    # and either way must not be committed silently.
  316	    observed_cpl = coupling_violations(composite, COMMIT_SIDE_CONDITIONS)
  317	    if observed_cpl != scenario.expected_cpl:
  318	        _fail(
  319	            f"{scenario.scenario_id}: committed composite raises CPL "
  320	            f"{sorted(observed_cpl)} but the catalog pins "
  321	            f"{sorted(scenario.expected_cpl)} — refusing to commit",
  322	            CPL_MISMATCH_EXIT,
  323	        )
  324	
  325	    with CompositeStateStore(store_path) as store:
  326	        committed = store.commit_composite(
  327	            composite, stop_after=scenario.commit_dimension_count
  328	        )
  329	
  330	    if scenario.write_stale_cache:
  331	        cache_path.write_text(cache_payload(scenario), encoding="utf-8")
  332	
  333	    # The in-memory optimistic knowledge (L3-03) exists only here and is about to be
  334	    # destroyed by the crash. Naming it on stderr makes the "lost ACK" observable in the
  335	    # run log without ever making it durable.
  336	    if scenario.uncommitted_knowledge is not None:
  337	        sys.stderr.write(
  338	            f"tos-l3-worker: {scenario.scenario_id}: holding UNPERSISTED knowledge "
  339	            f"{scenario.uncommitted_knowledge} in memory at crash time\n"
  340	        )
  341	
  342	    sys.stdout.write(
  343	        json.dumps(
  344	            {
  345	                "role": "writer",
  346	                "scenario_id": scenario.scenario_id,
  347	                "pid": os.getpid(),
  348	                "committed_dimensions": [str(d) for d in committed],
  349	                "store_path": str(store_path),
  350	                "crash_exit": CRASH_EXIT,
  351	            },
  352	            sort_keys=True,
  353	        )
  354	        + "\n"
  355	    )
  356	    sys.stdout.flush()
  357	    sys.stderr.flush()
  358	    os._exit(CRASH_EXIT)
  359	
  360	
  361	def run_reader(scenario: CrashScenario, store_path: Path, cache_path: Path) -> int:
  362	    """Reload from the store in this fresh process and print the verdict.
  363	
  364	    Returns:
  365	        The process exit code (``0``).
  366	    """
  367	    outcome = reload_conservative(
  368	        store_path,
  369	        INTENT_IDENTITY,
  370	        cache_paths=(cache_path,),
  371	    )
  372	    post = outcome.composite
  373	    verdict = {
  374	        "role": "reader",
  375	        "scenario_id": scenario.scenario_id,
  376	        "pid": os.getpid(),
  377	        "store_path": str(store_path),
  378	        "store_exists": Path(store_path).is_file(),
  379	        "store_complete": outcome.store_complete,
  380	        "filled_dimensions": [str(d) for d in outcome.filled_dimensions],
  381	        "discarded_caches": list(outcome.discarded_caches),
  382	        "cache_present_after_reload": cache_path.is_file(),
  383	        "intent_identity": post.intent_identity,
  384	        "intent_state": str(post.intent_state),
  385	        "transmission_attempt_state": str(post.transmission_attempt_state),
  386	        "broker_order_state": str(post.broker_order_state),
  387	        "knowledge_state": str(post.knowledge_state),
  388	        "capacity_state": str(post.capacity_state),
  389	        "committed_dimensions_readback": {
  390	            str(dimension): str(getattr(outcome.pre_restart, attribute))
  391	            for dimension, attribute in (
  392	                (StateDimension.INTENT, "intent_state"),
  393	                (StateDimension.CAPACITY, "capacity_state"),
  394	                (StateDimension.TRANSMISSION_ATTEMPT, "transmission_attempt_state"),
  395	                (StateDimension.BROKER_ORDER, "broker_order_state"),
  396	                (StateDimension.KNOWLEDGE, "knowledge_state"),
  397	            )
  398	        },
  399	    }
  400	    sys.stdout.write(json.dumps(verdict, sort_keys=True) + "\n")
  401	    sys.stdout.flush()
  402	    return 0
  403	
  404	
  405	_USAGE = (
  406	    "usage: python -m tos.staterestore._l3_worker "
  407	    "{writer|reader} <scenario-id> <store-path> <cache-path>"
  408	)
  409	
  410	
  411	def main(argv: list[str]) -> int:
  412	    """Dispatch on argv (design #39 S-4 — argv only, never ``os.environ``).
  413	
  414	    Args:
  415	        argv: ``[mode, scenario_id, store_path, cache_path]``.
  416	
  417	    Returns:
  418	        The reader's exit code. The writer never returns.
  419	    """
  420	    if len(argv) != 4:
  421	        _fail(f"expected 4 arguments, got {len(argv)}. {_USAGE}", USAGE_EXIT)
  422	    mode, scenario_id, store_raw, cache_raw = argv
  423	    scenario = SCENARIOS.get(scenario_id)
  424	    if scenario is None:
  425	        _fail(
  426	            f"unknown scenario {scenario_id!r}; known: {sorted(SCENARIOS)}", USAGE_EXIT
  427	        )
  428	    store_path, cache_path = Path(store_raw), Path(cache_raw)
  429	    if mode == "writer":
  430	        run_writer(scenario, store_path, cache_path)
  431	    if mode == "reader":
  432	        return run_reader(scenario, store_path, cache_path)
  433	    _fail(f"unknown mode {mode!r}. {_USAGE}", USAGE_EXIT)
  434	    return USAGE_EXIT  # unreachable
  435	
  436	
  437	if __name__ == "__main__":
  438	    sys.exit(main(sys.argv[1:]))
  439	
```

---- SOURCE tos/src/tos/orthostate/predicates.py (lines 640-742) ----
```
  640	        if from_state is None or to_state is None:
  641	            return False  # an Attempt transition needs both endpoints (fail-closed)
  642	        if to_state in _ATTEMPT_PREP_REGION:
  643	            return actor is TransitionAuthority.EXECUTION_COORDINATOR
  644	        if to_state in _ATTEMPT_SEND_BOUNDARY_REGION:
  645	            return actor is TransitionAuthority.BROKER_ADAPTER_EGRESS
  646	        return False  # off-region to_state (e.g. genesis NONE) => fail-closed
  647	    owners = _DIMENSION_OWNERS.get(dimension)
  648	    if owners is None:
  649	        return False
  650	    return actor in owners
  651	
  652	
  653	# ===========================================================================
  654	# §6.3 — conservative restart reconstruction (Knowledge never RECONCILED)
  655	# ===========================================================================
  656	
  657	#: Attempt states that, on restart, imply the send may be live (§13 line 198): reached
  658	#: SEND_STARTED and not proven-terminal (SEND_FAILED_PROVEN is the only proven-not-live).
  659	_ATTEMPT_POTENTIALLY_LIVE_AFTER_RESTART: frozenset[TransmissionAttemptState] = (
  660	    frozenset(
  661	        {
  662	            TransmissionAttemptState.SEND_STARTED,
  663	            TransmissionAttemptState.SENT_UNCONFIRMED,
  664	            TransmissionAttemptState.ACK_OBSERVED,
  665	            TransmissionAttemptState.SUPERSEDED,
  666	        }
  667	    )
  668	)
  669	
  670	#: Broker states that are structurally terminal and so preserved across restart (§13
  671	#: line 198); every other non-UNKNOWN broker state is reconstructed as UNKNOWN.
  672	_BROKER_STRUCTURALLY_TERMINAL: frozenset[BrokerOrderState] = frozenset(
  673	    {
  674	        BrokerOrderState.FILLED,
  675	        BrokerOrderState.CANCELLED,
  676	        BrokerOrderState.REJECTED,
  677	        BrokerOrderState.EXPIRED,
  678	    }
  679	)
  680	
  681	#: Positive-knowledge states that must NOT survive a restart (§13 line 199 — re-derive,
  682	#: never carry positive knowledge across a restart; §11 line 175 recovery != knowledge).
  683	_KNOWLEDGE_DOWNGRADE_ON_RESTART: frozenset[KnowledgeState] = frozenset(
  684	    {KnowledgeState.RECONCILED, KnowledgeState.CONSISTENT}
  685	)
  686	
  687	
  688	def reconstruct_conservative(pre: CompositeState) -> CompositeState:
  689	    """Project a pre-restart composite to a conservative post-restart one (§6.3; §13).
  690	
  691	    A pure projection realizing ADR-002-005 §13 line 195-200 (the substrate only —
  692	    actual durable reload / crash recovery / Recovery Barrier are EV-L3, design #8 §6.3):
  693	
  694	    * If the Attempt reached ``SEND_STARTED`` and is not proven-terminal, Capacity is
  695	      raised to at least ``POTENTIALLY_LIVE`` (preserved if already more conservative —
  696	      via the rcl comparator, no rank re-derivation) (line 198).
  697	    * A Broker Order that is not structurally terminal is reconstructed as ``UNKNOWN``;
  698	      terminal / already-``UNKNOWN`` states are preserved (line 198).
  699	    * Knowledge is re-derived: the positive-knowledge states (``RECONCILED`` /
  700	      ``CONSISTENT``) are downgraded to ``CONFLICTED`` — the codomain **structurally
  701	      excludes** ``RECONCILED`` (never re-arrived at), so "restart as knowledge of a
  702	      specific state" is unrepresentable (line 199; §11 line 175). Intent and Attempt
  703	      are preserved.
  704	
  705	    The result is a fresh DRAFT observation (no digest / id yet) whose dimensions are
  706	    never less conservative than ``pre``'s.
  707	
  708	    Args:
  709	        pre: The pre-restart composite observation.
  710	
  711	    Returns:
  712	        A new conservative :class:`CompositeState` (DRAFT).
  713	    """
  714	    post_capacity = pre.capacity_state
  715	    if pre.transmission_attempt_state in _ATTEMPT_POTENTIALLY_LIVE_AFTER_RESTART:
  716	        if not capacity_at_least_as_conservative(
  717	            pre.capacity_state, CapacityState.POTENTIALLY_LIVE
  718	        ):
  719	            post_capacity = CapacityState.POTENTIALLY_LIVE
  720	
  721	    if (
  722	        pre.broker_order_state in _BROKER_STRUCTURALLY_TERMINAL
  723	        or pre.broker_order_state is BrokerOrderState.UNKNOWN
  724	    ):
  725	        post_broker = pre.broker_order_state
  726	    else:
  727	        post_broker = BrokerOrderState.UNKNOWN
  728	
  729	    if pre.knowledge_state in _KNOWLEDGE_DOWNGRADE_ON_RESTART:
  730	        post_knowledge = KnowledgeState.CONFLICTED
  731	    else:
  732	        post_knowledge = pre.knowledge_state
  733	
  734	    return CompositeState(
  735	        intent_identity=pre.intent_identity,
  736	        intent_state=pre.intent_state,
  737	        transmission_attempt_state=pre.transmission_attempt_state,
  738	        broker_order_state=post_broker,
  739	        knowledge_state=post_knowledge,
  740	        capacity_state=post_capacity,
  741	        state_model_version=pre.state_model_version,
  742	    )
```

---- SOURCE tools/tos_evidence_run.py (lines 260-460) ----
```
  260	#: a stage run that exercised SPG-05/06/08 or ST-07 against an un-hardened component would
  261	#: be recording DEVIATIONs as if they were MET (design §5 gating).
  262	#:
  263	#: Each entry is checked **structurally** (:func:`check_l1_hardening`), never by scanning
  264	#: the file for a substring. A file-wide substring test is satisfied by the token appearing
  265	#: *anywhere*, including in a comment or a docstring — so H-1 could be rolled back while a
  266	#: sentence merely mentioning ``allow_inf_nan=False`` kept the gate green (measured). H-1
  267	#: is therefore read out of the parsed AST: the keyword must be bound in the actual
  268	#: ``ConfigDict(...)`` call assigned to ``FrozenModel.model_config``, with the literal
  269	#: value ``False``. H-2/H-4 are matched against **code tokens only**, with comments and
  270	#: string contents removed by :mod:`tokenize` first.
  271	#:
  272	#: This harness must never ``import tos`` (TOS-FW-R), so every check is static analysis of
  273	#: the source, not introspection of loaded objects.
  274	#: The §11 step 3 metadata axes ``_UNIT_METADATA_KEYS`` must compare for H-2.
  275	H2_REQUIRED_METADATA_KEYS = frozenset(
  276	    {"unit", "multiplier", "sign", "precision", "rounding", "boundary"}
  277	)
  278	
  279	
  280	def _assigned_value(tree: ast.AST, name: str) -> ast.expr | None:
  281	    """The value expression assigned to a module-level ``name``, or ``None``."""
  282	    for node in ast.walk(tree):
  283	        targets: list[ast.expr] = []
  284	        if isinstance(node, ast.Assign):
  285	            targets = list(node.targets)
  286	        elif isinstance(node, ast.AnnAssign):
  287	            targets = [node.target]
  288	        if any(isinstance(t, ast.Name) and t.id == name for t in targets):
  289	            return node.value
  290	    return None
  291	
  292	
  293	def _class_attr_value(tree: ast.AST, class_name: str, attr: str) -> ast.expr | None:
  294	    """The value expression assigned to ``<class_name>.<attr>``, or ``None``."""
  295	    for node in ast.walk(tree):
  296	        if isinstance(node, ast.ClassDef) and node.name == class_name:
  297	            for stmt in node.body:
  298	                targets: list[ast.expr] = []
  299	                if isinstance(stmt, ast.Assign):
  300	                    targets = list(stmt.targets)
  301	                elif isinstance(stmt, ast.AnnAssign):
  302	                    targets = [stmt.target]
  303	                if any(isinstance(t, ast.Name) and t.id == attr for t in targets):
  304	                    return stmt.value
  305	    return None
  306	
  307	
  308	def _function_def(tree: ast.AST, name: str) -> ast.FunctionDef | None:
  309	    """The (first) function definition called ``name``, or ``None``."""
  310	    for node in ast.walk(tree):
  311	        if isinstance(node, ast.FunctionDef) and node.name == name:
  312	            return node
  313	    return None
  314	
  315	
  316	def _raised_names(scope: ast.AST) -> list[str]:
  317	    """The exception class names raised anywhere inside ``scope``."""
  318	    names: list[str] = []
  319	    for node in ast.walk(scope):
  320	        if not isinstance(node, ast.Raise) or node.exc is None:
  321	            continue
  322	        exc = node.exc
  323	        func = exc.func if isinstance(exc, ast.Call) else exc
  324	        if isinstance(func, ast.Name):
  325	            names.append(func.id)
  326	        elif isinstance(func, ast.Attribute):
  327	            names.append(func.attr)
  328	    return names
  329	
  330	
  331	def check_h1(tree: ast.AST) -> tuple[bool, dict]:
  332	    """H-1: ``FrozenModel.model_config = ConfigDict(..., allow_inf_nan=False)``.
  333	
  334	    Read out of the AST, so the pin must be a real keyword bound in the real call with
  335	    the literal ``False``. A substring scan would also accept the token sitting in a
  336	    comment or docstring while the pin itself was deleted (measured).
  337	    """
  338	    value = _class_attr_value(tree, "FrozenModel", "model_config")
  339	    if not (
  340	        isinstance(value, ast.Call)
  341	        and isinstance(value.func, ast.Name)
  342	        and value.func.id == "ConfigDict"
  343	    ):
  344	        return False, {
  345	            "reason": "FrozenModel.model_config is not a ConfigDict(...) call"
  346	        }
  347	    bound = {kw.arg: kw.value for kw in value.keywords if kw.arg is not None}
  348	    pin = bound.get("allow_inf_nan")
  349	    met = isinstance(pin, ast.Constant) and pin.value is False
  350	    return met, {
  351	        "bound_keywords": sorted(bound),
  352	        "allow_inf_nan": None if pin is None else ast.unparse(pin),
  353	    }
  354	
  355	
  356	def check_h2(tree: ast.AST) -> tuple[bool, dict]:
  357	    """H-2: the six §11 step 3 metadata axes are compared, and the boundary test exists."""
  358	    value = _assigned_value(tree, "_UNIT_METADATA_KEYS")
  359	    keys = (
  360	        [e.value for e in value.elts if isinstance(e, ast.Constant)]
  361	        if isinstance(value, ast.Tuple)
  362	        else []
  363	    )
  364	    missing = sorted(H2_REQUIRED_METADATA_KEYS - set(keys))
  365	    has_comparison = _function_def(tree, "_exceeds_envelope_maximum") is not None
  366	    return (not missing and has_comparison), {
  367	        "unit_metadata_keys": keys,
  368	        "missing_metadata_keys": missing,
  369	        "boundary_comparison_defined": has_comparison,
  370	    }
  371	
  372	
  373	def check_h4(tree: ast.AST) -> tuple[bool, dict]:
  374	    """H-4: ``get_scheme`` raises ``ArtifactIntegrityError`` and no raw ``KeyError`` survives."""
  375	    scheme_fn = _function_def(tree, "get_scheme")
  376	    inner = _raised_names(scheme_fn) if scheme_fn is not None else []
  377	    module_wide = _raised_names(tree)
  378	    met = "ArtifactIntegrityError" in inner and "KeyError" not in module_wide
  379	    return met, {
  380	        "get_scheme_raises": sorted(set(inner)),
  381	        "module_raises": sorted(set(module_wide)),
  382	    }
  383	
  384	
  385	_H1_LABEL = "H-1 allow_inf_nan=False pinned on FrozenModel.model_config"
  386	
  387	#: ``(label, repo-relative path, structural checker)``. Every checker takes the parsed
  388	#: module AST and returns ``(met, detail)``; the detail is recorded either way so an unmet
  389	#: run says exactly *what* was measured, not merely that something failed.
  390	L1_HARDENING_PREREQUISITES: tuple[
  391	    tuple[str, str, Callable[[ast.AST], tuple[bool, dict]]], ...
  392	] = (
  393	    (_H1_LABEL, "tos/src/tos/canonical/_base.py", check_h1),
  394	    (
  395	        "H-2 precision/rounding/boundary comparability + boundary-aware comparison",
  396	        "tos/src/tos/spg/predicates.py",
  397	        check_h2,
  398	    ),
  399	    (
  400	        "H-4 canonicalization scheme lookup wrapped as ArtifactIntegrityError",
  401	        "tos/src/tos/canonical/canonicalization.py",
  402	        check_h4,
  403	    ),
  404	)
  405	
  406	#: VER-002-001 §2.7 (line 76-78) coverage-argument legs. ``boundary_values`` and
  407	#: ``adverse_scenario_set`` are corpus-level facts, so they are stated here once;
  408	#: ``unexercised_residual_ref`` is row-specific and comes from ``--residual-ref``.
  409	COVERAGE_BOUNDARY_VALUES = "per-dimension boundary combinations exercised (seed-fixed)"
  410	#: The EV-L3 restart axis (EV-L3 pilot design §6.1). Same leg, different quantifier: the
  411	#: boundary values are crash points crossed with composite boundary combinations, and
  412	#: the enumeration is deterministic rather than sampled.
  413	COVERAGE_BOUNDARY_VALUES_L3 = (
  414	    "per crash-point x composite boundary combinations, deterministically enumerated "
  415	    "(seed-fixed); the restart axis only"
  416	)
  417	COVERAGE_ADVERSE_SCENARIO_SET = (
  418	    "ADR-002-021 PROPOSED (unapproved) — adversarial-combination leg UNMET; "
  419	    "applicability to non-risk row = OQ; residual per §378"
  420	)
  421	#: design §6.2 N4 — the §378 register instance is **absent** (measured: only
  422	#: RESIDUAL-RISK-ACCEPTANCE-RECORD-template.yaml under verification/, zero residual
  423	#: artifacts under tos-evidence/), so creating it is prerequisite work. Each entry must
  424	#: carry all twelve VER:3293-3306 SHALL fields, and separate residuals SHALL NOT be
  425	#: unioned at a consumer (VER:3308) — the refs below are pointers, not a union.
  426	COVERAGE_RESIDUAL_NOTE = (
  427	    "The §378 Residual Risk Register INSTANCE is absent (measured: "
  428	    "verification/ holds only RESIDUAL-RISK-ACCEPTANCE-RECORD-template.yaml; "
  429	    "tos-evidence/ holds zero residual artifacts) — creating it is prerequisite "
  430	    "work. Each entry SHALL carry all twelve VER:3293-3306 fields (risk identity; "
  431	    "affected requirement/ADR; scope; credible failure sequence; maximum economic "
  432	    "effect; existing controls; detection/containment bound; owner; approver; "
  433	    "expiration/review date; required scope reduction; evidence references), and "
  434	    "owner/approver come through the P0-3 role system (D1). The refs above are "
  435	    "pointers, not a union: separate residual risks SHALL NOT be unioned at a "
  436	    "consumer (VER:3308) — each is registered independently."
  437	)
  438	
  439	
  440	class HarnessError(RuntimeError):
  441	    """A precondition or append-only violation. Never a test failure."""
  442	
  443	
  444	# ============================================================================
  445	# primitives
  446	# ============================================================================
  447	
  448	
  449	def _utc_now() -> datetime:
  450	    """UTC wall clock (seam: monkeypatched by the harness self-tests)."""
  451	    return datetime.now(UTC)
  452	
  453	
  454	def sha256_file(path: Path) -> str:
  455	    digest = hashlib.sha256()
  456	    with open(path, "rb") as fh:
  457	        for chunk in iter(lambda: fh.read(1 << 16), b""):
  458	            digest.update(chunk)
  459	    return digest.hexdigest()
  460	
```

---- SOURCE tools/tos_evidence_run.py (lines 660-860) ----
```
  660	    return sorted(
  661	        p for p in path.rglob("*.py") if "__pycache__" not in p.parts and p.is_file()
  662	    )
  663	
  664	
  665	def node_file(node: str) -> str:
  666	    """``pkg/test_x.py::TestC::test_y`` -> ``pkg/test_x.py``."""
  667	    return node.split("::", 1)[0]
  668	
  669	
  670	def parse_node_spec(spec: str) -> tuple[str, str]:
  671	    """``"<node> | <mapping basis>"`` -> ``(node, basis)``.
  672	
  673	    The basis is the measured reason this node belongs to the evidence row (a
  674	    file:line citation). An absent basis is recorded as ``UNSPECIFIED`` rather
  675	    than invented.
  676	    """
  677	    if "|" in spec:
  678	        node, basis = spec.split("|", 1)
  679	        return node.strip(), basis.strip()
  680	    return spec.strip(), "UNSPECIFIED"
  681	
  682	
  683	def read_nodes_file(path: Path) -> list[tuple[str, str]]:
  684	    out: list[tuple[str, str]] = []
  685	    for line in path.read_text(encoding="utf-8").splitlines():
  686	        line = line.strip()
  687	        if not line or line.startswith("#"):
  688	            continue
  689	        out.append(parse_node_spec(line))
  690	    return out
  691	
  692	
  693	# ============================================================================
  694	# environment / dependency measurement
  695	# ============================================================================
  696	
  697	_PROBE_SOURCE = r"""
  698	import json, platform, sys
  699	import importlib.metadata as md
  700	
  701	dists = json.loads(sys.argv[1])
  702	installed = {}
  703	for name in dists:
  704	    try:
  705	        installed[name] = md.version(name)
  706	    except Exception:
  707	        installed[name] = "NOT_INSTALLED"
  708	print(json.dumps({
  709	    "python": {
  710	        "version": platform.python_version(),
  711	        "version_full": sys.version.replace("\n", " "),
  712	        "implementation": platform.python_implementation(),
  713	        "executable": sys.executable,
  714	    },
  715	    "installed": installed,
  716	}))
  717	"""
  718	
  719	
  720	def probe_interpreter(
  721	    python: Path, distributions: tuple[str, ...] = PROBED_DISTRIBUTIONS
  722	) -> dict:
  723	    """Measure the *target* interpreter (the one that will run pytest)."""
  724	    proc = subprocess.run(
  725	        [str(python), "-c", _PROBE_SOURCE, json.dumps(list(distributions))],
  726	        capture_output=True,
  727	        text=True,
  728	        check=False,
  729	    )
  730	    if proc.returncode != 0:
  731	        raise HarnessError(
  732	            f"interpreter probe failed for {python}: {proc.stderr.strip()}"
  733	        )
  734	    probed: dict = json.loads(proc.stdout)
  735	    return probed
  736	
  737	
  738	def read_pinned_dependencies(repo_root: Path) -> dict[str, str]:
  739	    """Pins declared in ``tos/pyproject.toml`` (§3.2 / §5.1)."""
  740	    pyproject = repo_root / "tos" / "pyproject.toml"
  741	    if not pyproject.is_file():
  742	        return {}
  743	    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
  744	    project = data.get("project", {})
  745	    pins: dict[str, str] = {}
  746	    specs = list(project.get("dependencies", []))
  747	    for extra in project.get("optional-dependencies", {}).values():
  748	        specs.extend(extra)
  749	    for spec in specs:
  750	        if "==" in spec:
  751	            name, version = spec.split("==", 1)
  752	            pins[name.strip()] = version.strip()
  753	    return pins
  754	
  755	
  756	def read_tos_package_version(repo_root: Path) -> str:
  757	    pyproject = repo_root / "tos" / "pyproject.toml"
  758	    if not pyproject.is_file():
  759	        return NOT_APPLICABLE
  760	    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
  761	    return str(data.get("project", {}).get("version", NOT_APPLICABLE))
  762	
  763	
  764	# ============================================================================
  765	# EV-L2: hardening prerequisite, fault schedule, prior-stage binding
  766	# ============================================================================
  767	
  768	
  769	def check_l1_hardening(repo_root: Path) -> dict:
  770	    """Confirm the design §5 L1 hardening **structurally** (never from a flag).
  771	
  772	    Each prerequisite is decided by parsing the file that realizes it and inspecting the
  773	    syntax tree — the pin must be a real keyword in a real call, the metadata tuple must
  774	    really contain the six axes, ``get_scheme`` must really raise the integrity error and
  775	    no raw ``KeyError`` may survive anywhere in that module. This is deliberately not a
  776	    substring scan: a substring is satisfied by the token appearing in a comment or a
  777	    docstring, so the gate would stay green with the hardening rolled back.
  778	
  779	    A file that is absent, or that does not parse, is unmet — an unparseable file cannot
  780	    be certified, and treating a parse failure as "no violations found" would be the same
  781	    ∅-fail-open the fault schedule refuses.
  782	
  783	    Returns:
  784	        ``{"met": bool, "items": [...]}`` — every item is reported, met or not, with the
  785	        structural detail measured, so an unmet run says *which* hardening is absent.
  786	    """
  787	    items: list[dict] = []
  788	    for label, rel, checker in L1_HARDENING_PREREQUISITES:
  789	        path = repo_root / rel
  790	        if not path.is_file():
  791	            items.append(
  792	                {"hardening": label, "path": rel, "met": False, "reason": "FILE_ABSENT"}
  793	            )
  794	            continue
  795	        try:
  796	            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
  797	        except SyntaxError as exc:
  798	            items.append(
  799	                {
  800	                    "hardening": label,
  801	                    "path": rel,
  802	                    "met": False,
  803	                    "reason": f"SOURCE_DOES_NOT_PARSE: {exc}",
  804	                }
  805	            )
  806	            continue
  807	        met, detail = checker(tree)
  808	        items.append(
  809	            {
  810	                "hardening": label,
  811	                "path": rel,
  812	                "sha256": sha256_file(path),
  813	                "met": met,
  814	                "measured": detail,
  815	            }
  816	        )
  817	    return {
  818	        "met": all(item["met"] for item in items),
  819	        "measured_from": (
  820	            "structural analysis of the executed source's syntax tree; comments and "
  821	            "docstrings cannot satisfy any check (the harness never imports tos)"
  822	        ),
  823	        "items": items,
  824	    }
  825	
  826	
  827	def read_fault_timeline(path: Path) -> list[dict]:
  828	    """Parse the append-only fault schedule (one JSON object per line).
  829	
  830	    A malformed line is surfaced as a ``HarnessError`` rather than skipped: a schedule
  831	    the harness cannot fully read must not be summarised as if it had been.
  832	    """
  833	    if not path.is_file():
  834	        return []
  835	    rows: list[dict] = []
  836	    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
  837	        line = line.strip()
  838	        if not line:
  839	            continue
  840	        try:
  841	            row = json.loads(line)
  842	        except json.JSONDecodeError as exc:
  843	            raise HarnessError(
  844	                f"{FAULT_TIMELINE_NAME} line {number} is not valid JSON: {exc}"
  845	            ) from exc
  846	        if not isinstance(row, dict):
  847	            raise HarnessError(
  848	                f"{FAULT_TIMELINE_NAME} line {number} is not a JSON object"
  849	            )
  850	        rows.append(row)
  851	    return rows
  852	
  853	
  854	#: The design §6.1 placeholder for a disposition the run has not actually observed. A row
  855	#: carrying it verbatim was never filled in at runtime, so it proves nothing.
  856	RUNTIME_OBSERVED_PLACEHOLDER = "<runtime-observed>"
  857	
  858	#: The design §6.1 outcome vocabulary. Duplicated from ``tos/tests/conftest.py`` by
  859	#: necessity, not oversight: this tool must never ``import tos`` (TOS-FW-R), and the two
  860	#: sides agreeing is exactly what the re-derivation below checks — a shared import would
```

---- SOURCE tools/tos_evidence_run.py (lines 1260-1310) ----
```
 1260	            "in_memory_tokens_present": in_memory_tokens,
 1261	            "executed_pragmas": dict(sorted(executed_pragmas.items())),
 1262	            "pragmas_present": sorted(pragmas_present),
 1263	            "pragmas_missing": sorted(pragmas_missing),
 1264	            "pragmas_required": list(PERSISTENCE_REQUIRED_PRAGMAS),
 1265	        },
 1266	    }
 1267	
 1268	
 1269	def parse_modeled_axis_spec(spec: str) -> dict:
 1270	    """``"<axis> | <disposition> | <residual-ref> | <note>"`` -> the manifest entry.
 1271	
 1272	    An axis this stage did not really exercise must name the residual that carries it
 1273	    (design §6.2 gate 5). Parsing it as a required positional field — rather than as an
 1274	    optional key — is what makes an over-claim impossible to express: there is no way to
 1275	    declare a modelled axis and leave its residual blank.
 1276	    """
 1277	    parts = [part.strip() for part in spec.split("|")]
 1278	    if len(parts) < 3:
 1279	        raise HarnessError(
 1280	            "--modeled-axis expects '<axis> | <disposition> | <residual-ref> "
 1281	            f"[| <note>]', got {spec!r}"
 1282	        )
 1283	    axis, disposition, residual_ref = parts[0], parts[1], parts[2]
 1284	    note = " | ".join(parts[3:]).strip()
 1285	    if not axis or not disposition or not residual_ref:
 1286	        raise HarnessError(
 1287	            f"--modeled-axis has an empty axis / disposition / residual_ref in {spec!r}"
 1288	        )
 1289	    return {
 1290	        "axis": axis,
 1291	        "disposition": disposition,
 1292	        "residual_ref": residual_ref,
 1293	        "note": note or "UNSPECIFIED",
 1294	    }
 1295	
 1296	
 1297	def parse_prior_stage_spec(spec: str) -> tuple[str, str, str]:
 1298	    """``"<EVIDENCE-ID>/<run-id> | <reconcile note>"`` -> ``(evidence_id, run_id, note)``."""
 1299	    ref, _, note = spec.partition("|")
 1300	    ref = ref.strip()
 1301	    if "/" not in ref:
 1302	        raise HarnessError(
 1303	            f"--prior-stage-run expects '<EVIDENCE-ID>/<run-id> | <note>', got {spec!r}"
 1304	        )
 1305	    evidence_id, _, run_id = ref.partition("/")
 1306	    if not evidence_id.strip() or not run_id.strip():
 1307	        raise HarnessError(f"--prior-stage-run has an empty id in {spec!r}")
 1308	    return evidence_id.strip(), run_id.strip(), note.strip()
 1309	
 1310	
```

---- EVIDENCE-REGISTER-002.csv (header + STATE/SPG rows) ----
```
﻿evidence_id,domain,title,primary_adr,criticality,minimum_evidence_level,status,implementation_owner,evidence_owner,independent_reviewer,verification_profile_version,broker_capability_profile_version,latest_run_id,latest_result_date,evidence_location,notes
STATE-EV-001,Orthogonal State,Orthogonal Composite Persistence,ADR-002-005,Critical,EV-L1/2,READY,ai-impl(claude-orchestrated),operator,ai-review(decorrelated)+operator-countersign,2.1-PROPOSED,N/A,20260729T135150Z-d4160fd0,2026-07-29,tos-evidence/STATE-EV-001/20260729T135150Z-d4160fd0/,"EV-L2 component-fault stage executed 2026-07-29 at baseline d4160fd0 (EV-L2 pilot design §3; 11/11 faults MET; seed=0 pinned; L1 hardening H-1/H-2/H-4 verified structurally) over the EV-L1 stage 20260729T135130Z-d4160fd0 at the same baseline. Every traceability file:line citation re-measured against the executed source. NOT a PASS and NOT PASS-eligible from this pilot: storage-independent axis only — the /2 durable/persisted limb (VER:1024; ADR-002-005 §13:197; AC-005-1:237) is unevidenced and is a §378 residual. VER §2.7 coverage argument, P0-1 and independent signature also remain open. Superseded earlier stage runs are retained unmodified (VER §2.2)."
STATE-EV-002,Orthogonal State,Conservative Direction,ADR-002-005,Critical,EV-L2/3,NOT_IMPLEMENTED,ai-impl(claude-orchestrated),operator,ai-review(decorrelated)+operator-countersign,2.1-PROPOSED,TBD,,,tos-evidence/,
STATE-EV-003,Orthogonal State,Cross-Dimension Coupling,ADR-002-005,Critical,EV-L1/3,READY,ai-impl(claude-orchestrated),operator,ai-review(decorrelated)+operator-countersign,2.1-PROPOSED,N/A,,,tos-evidence/,
STATE-EV-004,Orthogonal State,Conservative Restart Reconstruction,ADR-002-005,Critical,EV-L3,NOT_IMPLEMENTED,ai-impl(claude-orchestrated),operator,ai-review(decorrelated)+operator-countersign,2.1-PROPOSED,TBD,,,tos-evidence/,
STATE-EV-005,Orthogonal State,Dimension Transition Ownership,ADR-002-005,Critical,EV-L2/3+Security,NOT_IMPLEMENTED,ai-impl(claude-orchestrated),operator,ai-review(decorrelated)+operator-countersign,2.1-PROPOSED,TBD,,,tos-evidence/,
SPG-EV-001,Safety Profile Governance,Envelope Governance and Non-Silent Expansion,ADR-002-014,Critical,EV-L1/3+Security,READY,ai-impl(claude-orchestrated),operator,ai-review(decorrelated)+operator-countersign,2.1-PROPOSED,N/A,,,tos-evidence/,
SPG-EV-002,Safety Profile Governance,"Semantic Units, Numeric, and Cross-Field Validation",ADR-002-014,Critical,EV-L1/2,PASS,ai-impl(claude-orchestrated),operator,ai-review(decorrelated)+operator-countersign,2.1-PROPOSED,N/A,20260729T135209Z-d4160fd0,2026-07-30,tos-evidence/SPG-EV-002/20260729T135209Z-d4160fd0/,"EV-L1/2 stages executed at baseline d4160fd0 (EV-L1 run 20260729T135131Z-d4160fd0; EV-L2 component-fault run 20260729T135209Z-d4160fd0 per EV-L2 pilot design §4; 12/12 faults MET; seed=0 pinned; L1 hardening H-1/H-2/H-4 verified structurally). Every traceability file:line citation re-measured against the executed source. Signature chain complete (VER §9.5): ai-review attempt 3 + operator countersign 2026-07-30 (tos-evidence/SPG-EV-002/review/). PASS covers the EV-L1/EV-L2 minimum level only — no authority/live/broker/ADR-acceptance effect. SPG-04/07 are §378 residuals and SPG-12 is SPG-EV-003; residuals R-2/R-3 registered. Superseded earlier stage runs are retained unmodified (VER §2.2)."
SPG-EV-003,Safety Profile Governance,"Schema, Omission, and Canonicalization Safety",ADR-002-014,Critical,EV-L1/2+Security,READY,ai-impl(claude-orchestrated),operator,ai-review(decorrelated)+operator-countersign,2.1-PROPOSED,N/A,,,tos-evidence/,
SPG-EV-004,Safety Profile Governance,Atomic Mixed-Generation Activation,ADR-002-014,Critical,EV-L1/3,READY,ai-impl(claude-orchestrated),operator,ai-review(decorrelated)+operator-countersign,2.1-PROPOSED,N/A,,,tos-evidence/,
SPG-EV-005,Safety Profile Governance,Concurrent and Stale-Base Activation,ADR-002-014,Critical,EV-L1/3,READY,ai-impl(claude-orchestrated),operator,ai-review(decorrelated)+operator-countersign,2.1-PROPOSED,N/A,,,tos-evidence/,
SPG-EV-006,Safety Profile Governance,Restrictive Precedence and Economic Continuity,ADR-002-014,Critical,EV-L1/3,READY,ai-impl(claude-orchestrated),operator,ai-review(decorrelated)+operator-countersign,2.1-PROPOSED,N/A,,,tos-evidence/,
SPG-EV-007,Safety Profile Governance,"Rollback, Restore, and Historical Replay Fencing",ADR-002-014,Critical,EV-L2/3+Security,NOT_IMPLEMENTED,ai-impl(claude-orchestrated),operator,ai-review(decorrelated)+operator-countersign,2.1-PROPOSED,TBD,,,tos-evidence/,
SPG-EV-008,Safety Profile Governance,Expiry and Recovery Non-Revival,ADR-002-014,Critical,EV-L1/3,READY,ai-impl(claude-orchestrated),operator,ai-review(decorrelated)+operator-countersign,2.1-PROPOSED,N/A,,,tos-evidence/,
SPG-EV-009,Safety Profile Governance,Separation of Duties and Break-Glass Confinement,ADR-002-014,Critical,EV-L2/3+Security,NOT_IMPLEMENTED,ai-impl(claude-orchestrated),operator,ai-review(decorrelated)+operator-countersign,2.1-PROPOSED,TBD,,,tos-evidence/,
```

---- RESIDUAL-RISK-REGISTER-002.yaml (lines 1-200, incl. R-1) ----
```
    1	# RESIDUAL-RISK-REGISTER-002 — the VER-002-001 §378 (line 3291-3310) register
    2	#
    3	# WHAT THIS IS
    4	#   The §378 Residual Risk Register instance for the ADR-002 evidence track.
    5	#   §378 line 3293: "Every unresolved limitation SHALL record:" followed by
    6	#   twelve items. Each entry below carries all twelve under those names.
    7	#
    8	# SHAPE
    9	#   No template exists for this artifact (measured: verification/ ships
   10	#   RESIDUAL-RISK-ACCEPTANCE-RECORD-template.yaml, which is the ADR-002-026
   11	#   deviation-acceptance record — a different artifact with a different
   12	#   authority). The shape here is derived directly from VER §378's twelve SHALL
   13	#   items, in the specification's own order and wording.
   14	#
   15	# THIS IS NOT A DEVIATION ACCEPTANCE
   16	#   §378 line 3308 adds binding requirements "Where RFC-001 permits a deviation".
   17	#   None of the three entries claims a deviation: no ADR-002-026 request, no
   18	#   decision, no Active Deviation Set, no compensating-control acceptance, no
   19	#   Deviation Generation. Entry R-1 in particular CANNOT be accepted that way —
   20	#   VER:130 forbids WAIVED_WITH_RESIDUAL_RISK for a Critical requirement. These
   21	#   are recorded gaps that block, not accepted risks that release.
   22	#
   23	# NON-UNION RULE
   24	#   §378 line 3308: "Separate residual risks SHALL NOT be unioned at a consumer;
   25	#   combined risk requires one canonical reviewed set." R-1, R-2, and R-3 are
   26	#   three independent entries. A consumer SHALL cite them individually and SHALL
   27	#   NOT summarise them as one aggregate residual.
   28	#
   29	# "BROKER LIMITATION" PROHIBITION
   30	#   §378 line 3310: "Broker limitation" is not a sufficient residual-risk
   31	#   description. No entry below invokes one; the scope is broker-free.
   32	#
   33	# APPROVAL RECORD
   34	#   Operator directive 2026-07-29 ("§378 Residual Risk Register 생성: 승인");
   35	#   session C record. Approver identity `operator` = D1 role scheme System owner /
   36	#   Bounds-Approver (docs/plans/2026-07-29-tos-phase0-role-scheme-and-disposition.md
   37	#   lines 15-16). Separation of duties preserved: this identity is not the
   38	#   Live-Armer (unassigned), and per VER §2.6 the independent reviewer of the
   39	#   affected evidence SHALL NOT be the identity that approved these residuals.
   40	
   41	artifact_type: RESIDUAL_RISK_REGISTER
   42	schema_version: "1.0-DRAFT"
   43	register_id: RESIDUAL-RISK-REGISTER-002
   44	register_version: "1.0"
   45	canonical_digest: null   # no approved canonicalization scheme for spec-layer YAML; the git object is the integrity reference
   46	status: APPROVED
   47	approved_by: ["operator"]
   48	effective_from: "2026-07-29"
   49	review_due: "2027-01-25"
   50	# review_due rationale: the approved MAX_residual_risk_review_interval_ms
   51	# (VERIFICATION-PROFILE-002.yaml line 949) is 15552000000 ms = 180 days. From
   52	# effective_from 2026-07-29 that bound lands on 2027-01-25, four days before the
   53	# profile's own review_due 2027-01-29 (line 56). The earlier, bound-conforming
   54	# date governs every entry; a later date would breach an approved bound.
   55	
   56	scope:
   57	  environment: non-live-test
   58	  detail: >-
   59	    Pure model layer at commit eb92ea467cb55d923b5c9eb4307b65491b14fe26. No
   60	    broker session, no account, no instrument, no order path, no live
   61	    authorization. Matches VERIFICATION-PROFILE-002.yaml scope.environment
   62	    (line 60).
   63	  covered_rows: [STATE-EV-001, SPG-EV-002]
   64	
   65	union_prohibition: >-
   66	  Per VER-002-001 §378 line 3308 these entries SHALL NOT be unioned at a
   67	  consumer. Each is registered independently with its own scope, controls,
   68	  bound, owner, approver, review date, and required scope reduction.
   69	
   70	deviation_binding_applicability: >-
   71	  NOT_APPLICABLE — no entry claims an RFC-001 permitted deviation, so the §378
   72	  line 3308 ADR-002-026 binding requirements (request, decision, Active Deviation
   73	  Set, reduced configuration scope, independently verified compensating controls,
   74	  Deviation Generation, hard expiry, review interval, non-PASS evidence status)
   75	  do not attach. R-1 is additionally ineligible for that route (VER:130).
   76	
   77	entries_scope_note: >-
   78	  This register holds exactly the three entries the operator approved on
   79	  2026-07-29. One further candidate limitation was identified while authoring the
   80	  companion scenario set and is recorded there rather than invented into this
   81	  register: ADVERSE-SCENARIO-SET-002-EVL2-PILOT.yaml
   82	  `dominance_and_pruning_proofs` id ASS-DOM-05 (STATE-EV-001 dimensions
   83	  intent_state and capacity_state were never directly mutated; their coverage
   84	  rests on a structural-identity argument, not an executed one). Registering it
   85	  as R-4 is an open operator decision.
   86	
   87	entries:
   88	
   89	  - risk_identity: >-
   90	      R-1 — STATE-EV-001 durable/persisted limb is unevidenced. The EV-L2 pilot
   91	      covers the representability and no-silent-derivation axes of the row's
   92	      Expected; the "durable" half of that same Expected has no evidence at all,
   93	      because no persisted authoritative record exists to fault.
   94	    affected_requirement_and_adr:
   95	      requirement: >-
   96	        VER-002-001 STATE-EV-001 Expected (line 1024): "Every valid composite
   97	        remains representable and durable; no dimension is silently derived from
   98	        another except through an explicit CPL invariant and owned transition."
   99	        Minimum level EV-L1/EV-L2 (line 1021).
  100	      adr: >-
  101	        ADR-002-005 §13 (line 197): "All five dimensions SHALL be durable and
  102	        reconstructable after crash, restart, or failover." AC-005-1 (line 237):
  103	        the composite states "are all representable and persisted". The durable
  104	        referent's own row, STATE-EV-004, is minimum level EV-L3 (line 1042).
  105	      criticality_note: >-
  106	        The requirement is Critical, so VER:130 makes
  107	        WAIVED_WITH_RESIDUAL_RISK unavailable. This is a blocking gap, not an
  108	        acceptable one.
  109	    broker_account_instrument_scope:
  110	      brokers: []
  111	      accounts: []
  112	      instruments: []
  113	      statement: >-
  114	        Non-live-test only; the affected artifact is the in-memory
  115	        tos.orthostate.records.CompositeState at commit eb92ea46. No broker,
  116	        account, or instrument is in scope, and no broker limitation is invoked
  117	        or implied (VER:3310).
  118	    credible_failure_sequence: >-
  119	      (1) A durability or reconstruction defect exists in whatever persistence is
  120	      later chosen — a write that is not durable at the claimed point, or a
  121	      reconstruction that resolves a dimension differently after crash. (2) The
  122	      defect is invisible at the model layer, so the EV-L2 pilot cannot fail on
  123	      it. (3) A reader of the pilot evidence treats STATE-EV-001 as covering the
  124	      row's whole Expected and builds restart, recovery-barrier, or reconciliation
  125	      logic on "durable and reconstructable" as an established premise. (4) The
  126	      defect first surfaces at a real crash-restart, when a composite state is
  127	      reconstructed with a different capacity_state or knowledge_state than the
  128	      one that was committed. (5) The conservative-resume barrier is then armed
  129	      from a false premise, which is exactly the condition ADR-002-005 §13 exists
  130	      to prevent.
  131	    maximum_economic_effect:
  132	      present: >-
  133	        None. The declared scope has no broker route, no account, and no order
  134	        path, so no economic effect can be produced by this residual today.
  135	      path_to_economic_effect: >-
  136	        The credible economic path is evidence-chain contamination, not direct
  137	        loss: a coverage or PASS claim resting on this row could later be cited
  138	        as a satisfied precondition in a live-authorization or scope-promotion
  139	        decision. The effect would then be bounded by whatever live scope that
  140	        later decision opens — which is presently unbounded on the record,
  141	        because MAX_trial_authorized_economic_effect and
  142	        MAX_trial_concurrent_potential_effect are null and key-level unapproved
  143	        in VERIFICATION-PROFILE-002.yaml (lines 942-943).
  144	      statement: "No present economic effect; future effect unbounded-by-record until those keys are approved."
  145	    existing_controls:
  146	      - "The run manifest's claim.covered_axis names the exclusion in-band: 'representability + non-derivation ONLY (NOT durable)'."
  147	      - "coverage_argument.discharged is false in the same manifest; unexercised_residual_ref carries the durable limb with its anchors."
  148	      - "claim.closes_evidence_item and claim.register_status_moved_by_this_run are both false, so no register row moved."
  149	      - "VER:130 structurally forbids waiving a Critical requirement, so no acceptance route can quietly close this."
  150	      - "The durable referent has its own higher-level row (STATE-EV-004, EV-L3), so the gap has a named destination."
  151	    detection_and_containment_bound:
  152	      detection: >-
  153	        NOT_ESTABLISHED. There is no runtime detector because there is no durable
  154	        substrate to monitor — ADR-002-005 §4 (line 61) leaves the persistence
  155	        technology undecided. Detection today is document-gate only: review of the
  156	        evidence package's covered_axis and coverage_argument fields.
  157	      containment: >-
  158	        Gate-level only. The row cannot reach PASS while the coverage argument is
  159	        undischarged, and no automated fence exists (none can, absent a substrate).
  160	      time_bound: "None claimed. A gate reviewed at most every 180 days is not a time-to-detect bound."
  161	    owner: operator
  162	    approver:
  163	      identity: operator
  164	      basis: "Operator directive 2026-07-29 (§378 register creation approved); session C record. D1 role scheme System owner."
  165	      separation_of_duties: "Not the Live-Armer (unassigned). Per VER §2.6 this identity SHALL NOT also be the independent reviewer of the affected evidence."
  166	    expiration_or_review_date:
  167	      review_date: "2027-01-25"
  168	      basis: "MAX_residual_risk_review_interval_ms = 15552000000 ms = 180 days from 2026-07-29 (VERIFICATION-PROFILE-002.yaml line 949)."
  169	      expiry_semantics: >-
  170	        This entry does not expire into acceptance. A missed or unproven review
  171	        restricts scope and never auto-renews; the underlying requirement stays
  172	        Critical and unwaivable regardless of the date.
  173	    required_scope_reduction:
  174	      - "STATE-EV-001 SHALL NOT be marked PASS on the strength of the EV-L2 pilot."
  175	      - "No live scope, restricted-live trial, or production authorization may cite STATE-EV-001 as evidence of durability."
  176	      - "Any consumer needing the durable limb SHALL cite STATE-EV-004 at EV-L3 with a real persistence substrate, not this row."
  177	      - "Resolution prerequisite: the persistence technology decision deferred by ADR-002-005 §4 (line 61) must be made first; an EV-L3 crash/restart fault run then discharges the limb."
  178	    evidence_references:
  179	      - "tos-evidence/STATE-EV-001/20260729T120613Z-eb92ea46/manifest.yaml (run_id 20260729T120613Z-eb92ea46; coverage_argument.unexercised_residual_ref[0]; claim.covered_axis)"
  180	      - "tos-evidence/STATE-EV-001/20260729T120613Z-eb92ea46/fault-timeline.jsonl (11 faults, all MET, none durable)"
  181	      - "tos-evidence/STATE-EV-001/20260729T120613Z-eb92ea46/baseline.yaml (sha256 77c0234e9c83d5a662a39faf0a7ee9631e577c1a8b0f62cc72016aecbd7658f2; 16 VER §3 fields unmet)"
  182	      - "baseline commit eb92ea467cb55d923b5c9eb4307b65491b14fe26; evidence commit 9611142d"
  183	      - "docs/plans/2026-07-29-tos-ev-l2-pilot-design.md §2.3, §9 gate 3, §10 (ratified at commit fdb74324)"
  184	      - "VER-002-001 lines 1021, 1024, 1042, 130; ADR-002-005 lines 61, 197, 237"
  185	
  186	  - risk_identity: >-
  187	      R-2 — the overflow/underflow limb of Safety-Profile semantic validation is
  188	      unexercised, because no approved bound defines a safe magnitude range for a
  189	      governed dimension. The fault was written, then excluded from the catalogue
  190	      for lack of a falsifiable Expected.
  191	    affected_requirement_and_adr:
  192	      requirement: >-
  193	        VER-002-001 SPG-EV-002 Expected (line 1549): "Every unsafe or incomparable
  194	        semantic mutation is rejected deterministically before activation; no
  195	        parser or consumer interpretation grants a more permissive result."
  196	        Minimum level EV-L1/EV-L2 (line 1546).
  197	      adr: >-
  198	        ADR-002-014 §11 step 3 (line 304) SHALL-validates "types, units,
  199	        currencies, multipliers, signs, precision, rounding, overflow, underflow,
  200	        NaN, infinity, and boundary inclusion"; SPG-AC-002 (line 621) requires
```


============================================================================
# AUTHOR-SIDE COMMAND OUTPUTS (disclosed; executed 2026-08-06)
============================================================================

$ .venv/bin/python tools/tos_firewall_check.py  (rc=0)
```
tos-firewall: PASS — no import-firewall violations
```

$ .venv/bin/python tools/tos_spec_status.py  (rc=0)
```
TOS spec status PASS: documents=13, ADRs=45, Part1=372, DEV=118, direct_traceability=29/30, source_gap_adrs=1, p2_carried=28, CONST-003=INCONCLUSIVE, migration_rows=54, broker_sites=9, count_transcriptions=11, restricted_live=NOT_AUTHORIZED, production=NOT_AUTHORIZED
```

$ git log --oneline -6  (rc=0)
```
12dd4077 feat(tos): implement the EV-L3 pilot — staterestore, crash orchestration, harness v3 (design #39)
d99fd291 feat(tos-spec): author the EV-L3 pilot Adverse Scenario Set instance (PROPOSED)
2b455dd9 docs(plans): ratify the EV-L3 pilot design contract (design #39)
0673ccef fix(tests): repin EMA golden parity to last-ulp band (pandas FMA contraction)
818edf4a docs(plans): apply #38 errata v1.4 and register the (b) judgment closure
e4db5a5f docs(plans): record the (b) env-reverification judgment — path absent
```

$ git status --porcelain  (rc=0)
```
?? tos-evidence/SPG-EV-002/20260806T015630Z-12dd4077/
?? tos-evidence/SPG-EV-002/20260806T015631Z-12dd4077/
?? tos-evidence/STATE-EV-001/20260806T015629Z-12dd4077/
?? tos-evidence/STATE-EV-001/20260806T015630Z-12dd4077/
?? tos-evidence/STATE-EV-004/
```
