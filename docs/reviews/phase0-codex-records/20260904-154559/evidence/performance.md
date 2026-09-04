> [재심 스탬프 20260904-001114 안내] 이 증거는 1차 스탬프 .omc/review/20260903-165133/evidence/performance.md 의 사본이다 — HEAD b5d2448a(수정 커밋 067ecb2e·2e5edb4a 이전) 기준 관측. 수정된 파일군(tools/tos_completion_status.py · tools/tos_spec_status.py · 두 테스트 파일 · D0-5 7 docstring · 생성물)에 대한 관측은 낡았을 수 있다.

# Performance Lens — D0 Completion-Contract Block (Read-Only Evidence)

Repo: /Users/harris/Development/private/kis_unified_sts
HEAD at audit start: `b5d2448a`
Diff scope: `git diff 28475ca1^ HEAD -- . ':!docs/plans' ':!docs/reviews'` (34 files, +14530/-109)
Lens angle: this block is CI gate/checker/test code, not a real-time trading hot path.
Question: does it finish deterministically inside the CI time budget, does complexity
scale with input size (10k-line contract, ~488-row required-kinds CSV, ~2024-row
surface-map CSV, full git history), and do external calls (git subprocess, gh API)
stay bounded.

Status: COMPLETE — all six requested check items covered (§① summary, §②
findings, §③ checked-and-sound, §④ not-verified/out-of-scope below).

## ① Summary

The D0 block is CI-gate/checker/test code, not a real-time hot path, so the
question is CI time budget and complexity scaling, not per-tick latency. Under
that lens:

- **All standalone checker invocations are cheap** (`tos_completion_status.py
  --check` ≈ 9s, `tos_spec_status.py --check` ≈ 0.65s, `tos_contract_check.py`
  ≈ 0.58s, `--self-test` ≈ 70s). Both CI workflows that run them
  (`tos-firewall.yml`, `test.yml`) finish well inside their timeout budgets
  (see §③).
- **The dominant real cost is subprocess-spawn overhead from git**, not
  algorithmic complexity over the 10k-line contract or the CSV registers.
  `tos_completion_status.py --check` alone shells out to `git` **184 times**
  in a single run (measured via a PATH shim, see finding P-2). Every join
  over the register/MAP/required-kinds CSVs is dict-indexed, not nested-loop
  (finding P-6, sound).
- **The one clearly unbounded-growth pattern** is `_create_u16_snapshot()`
  (`tools/tos_completion_status.py:2296`), which does a real `git clone
  --no-local --no-hardlinks` of the **entire** repository (currently 81MB
  `.git`, ~1.9s locally) once per `--check` invocation, and the same
  clone-based isolation pattern is repeated inside `tools/u17-verify.sh`.
  Cost scales with total repo history size, not with the size of what
  changed (finding P-1).
- **The most significant, measured finding is local test-suite cost, not CI
  cost**: the 4 diff-touched test files alone (`test_tos_completion_status.py`,
  `test_tos_contract_index.py`, `test_tos_spec_status.py`,
  `test_u17_verify.py`, 334 tests total) take **5m20s wall-clock, single
  worker** locally, driven by ~23 tests that each spin up a real git repo
  fixture (multiple real commits/checkouts/merges) and then exercise the
  same clone-heavy production code path (finding P-3). In CI this is masked
  by `pytest -n auto` parallelism — the whole `tests/` suite (this file plus
  everything else in the repo) finished in 5m07s against a 25-minute budget
  in the most recent run — so CI budget is currently fine, but local
  edit-run-repeat iteration on this test file is materially slow.

## ② Findings

### P-1 (MEDIUM) — full-repo `git clone` per `--check`/`u17-verify` run, cost scales with total repo size

- **Location**: `tools/tos_completion_status.py:2296-2340`
  (`_create_u16_snapshot`, called once per `--check` from the U-16 derivation
  path), and the equivalent snapshot step at the top of
  `tools/u17-verify.sh` (see the `U17-SNAP … git clone --no-local
  --no-hardlinks` line in the live capture, evidence P-4 below).
- **Finding**: to defend U-16/U-17 provenance derivation against `git
  replace`/grafts spoofing, both tools clone the **entire** repository
  (`git clone --no-local --no-hardlinks <repo_root> <tmp>/snapshot`) into a
  temp dir, once per invocation, then run their git-history derivation
  inside that clone. Measured standalone: `.git` is 81MB, the clone itself
  takes **1.86s wall** locally (`3.35s user 0.96s system 231% cpu 1.862s
  total`), producing a 92MB copy. This is real disk I/O and process cost
  proportional to **total repository history size**, not to the size of the
  path/commit range actually being checked (contrast with the scoped
  `git rev-list --full-history -- <path>` calls elsewhere, which stay cheap
  because they're filtered by path — see "checked and sound" below).
- **In-range vs pre-existing**: in-range. `_create_u16_snapshot` and the
  U-16 derivation path are part of this diff block (`tools/
  tos_completion_status.py` is a new file in the diff). `u17-verify.sh`'s
  snapshot step is a pre-existing pattern this block's `tos_completion_status.py`
  reuses/mirrors, not something it introduces from scratch, but both are
  in the reviewed file set.
- **Hot/cold path**: cold path (one clone per CI job step / per local
  `--check` invocation), not per-tick. Severity is about **unbounded
  growth**, not present-day latency: at 81MB this costs ~2s locally; CI
  measured this whole checker step (which includes the clone plus ~180
  other git subprocess calls) at 7s wall (see §③). The repo is at 2403
  commits and growing (10k-line contract doc, 2024-row CSV, etc.), and nothing
  bounds `.git` size before this clone is paid again on every run.
- **Recommendation**: measurement-worthy over time (track `.git` size /
  clone duration in CI, e.g. via the `duration_ms` telemetry
  `tos_evidence_run.py` already collects), not an immediate blocker. If it
  becomes a problem, a `git clone --no-local --no-hardlinks --shallow-since=<N
  commits back>` bound to slightly more than `DEFAULT_COMMITS`/the
  R-7-relevant window would keep the anti-replace/grafts guarantee (a
  shallow clone still can't have `git replace`/grafts state injected by the
  untrusted commit range under test) while decoupling clone cost from full
  history size — but that is a design change to a security-motivated
  mechanism and should go through the same review that approved the
  isolation design, not be applied as a drive-by perf patch. Confidence:
  70 (the growth trend is measured fact; whether it ever becomes CI-budget-
  relevant is a projection).
- **Confidence**: 70.

### P-2 (LOW/informational) — `--check` run spends ~9s wall making 184 separate `git` subprocess calls

- **Location**: `tools/tos_completion_status.py` — call sites at lines 337,
  680, 1343, 1358, 1431, 1770, 1788, 1806, 1820, 1845, 1989, 2006, 2023,
  2041, 2307, 2322, 2339, 2368 (`subprocess.run(["git", ...])`).
- **Finding**: instrumented one `tos_completion_status.py --check` run with
  a `git` PATH shim that logs every invocation. Result: **184** git
  subprocess spawns in one run: `cat-file`=75, `show`=38, `log`=20,
  `rev-parse`=19, `--no-replace-objects cat-file commit`=15, `merge-base`=7,
  `rev-list`=6, plus 1 each of `status`, `replace`, `ls-tree`, `clone`. Wall
  time for the same run (measured separately, without the shim) was 8.997s
  (`6.73s user 3.06s system 108% cpu`). At ~184 process spawns, that's
  roughly 30-50ms average per git invocation, consistent with process-spawn
  overhead (fork/exec + git's own startup), not with git actually walking
  meaningful amounts of history per call — each individual call is cheap in
  isolation (see P-1's clone aside, and the scoped `--full-history` call
  measured at 58ms for 2 candidates in "checked and sound" below).
- **In-range**: in-range (`tools/tos_completion_status.py` is new in this
  diff).
- **Hot/cold path**: cold (once per `--check` invocation; `--check` itself
  runs once per CI job step, not per commit-under-test or per row).
- **Recommendation**: not urgent at current scale (9s total, well inside
  budget — see §③). If this checker's runtime becomes a CI-budget concern
  as more U-1x-class derivations are added, the highest-leverage fix is
  batching repeated `cat-file -e`/`show` lookups through a single long-lived
  `git cat-file --batch`/`--batch-check` subprocess instead of one spawn per
  lookup (75 + 38 = 113 of the 184 calls are `cat-file`/`show`) — this is a
  standard git-plumbing pattern for exactly this access shape and would cut
  spawn count by roughly half without changing the derivation logic. Flagged
  as informational/measurement-recommended, not a current bottleneck.
- **Confidence**: 80 (call count and wall time are measured; the batching
  recommendation's payoff is not measured, just a standard technique for
  this access pattern).

### P-3 (HIGH for local dev velocity, informational for CI) — 23 "real corpus" / real-harness tests dominate a 5m20s single-worker run of the 4 diff-touched test files

- **Location**: `tests/tools/test_tos_completion_status.py` (8
  `test_real_corpus_*` functions, e.g. `test_real_corpus_generator_write_check_cycle`,
  `test_real_corpus_u15_entry_state_matches_harness`,
  `test_real_corpus_gate_verdicts_match_expectations`,
  `test_real_corpus_generated_doc_byte_identical_when_no_declaration`,
  `test_real_corpus_reports_oq11_not_required_and_reproduces_digest`,
  `test_real_corpus_u16_state_is_no_rows_clear`,
  `test_real_corpus_check_passes`); `tests/tools/test_u17_verify.py` (15 of
  its 21 tests call `_run_script(...)`, which drives the real
  `tools/u17-verify.sh`, e.g. `test_negative_alpha_ii_other_workflow_confirmed_passes`,
  `test_positive_full_stack_reaches_active`,
  `test_positive_delta_axis_observes_all_three_2b2_endpoints`).
- **Finding**: ran `pytest tests/tools/test_tos_completion_status.py
  tests/tools/test_tos_contract_index.py tests/tools/test_tos_spec_status.py
  tests/tools/test_u17_verify.py -q -p no:cacheprovider --durations=15`
  (334 tests total: 189+21+103+21 per `--collect-only`). Result: **5m19.76s
  wall** (`143.00s user 109.15s system 78% cpu`). `--durations=15` top
  entries are all 6.4-14.0s **individual tests**: `test_real_corpus_generator_write_check_cycle`
  13.96s, `test_real_corpus_u15_entry_state_matches_harness` 8.27s,
  `test_negative_alpha_ii_other_workflow_confirmed_passes` 8.04s,
  `test_positive_full_stack_reaches_active` 7.66s, down to 6.43s for the
  15th-slowest. The `test_real_corpus_*` family (8 tests) effectively
  re-runs the full `--check` derivation (same ~184-git-subprocess-call cost
  as P-2) against the real repo per test; the `test_u17_verify.py`
  `_run_script`-based tests (15 of 21) each spawn the full
  `tools/u17-verify.sh` harness, which itself does its own
  `git clone --no-local --no-hardlinks` snapshot (P-1's pattern) plus
  mocked-HTTP-call machinery per test. Combined, these ~23 heavy tests are a
  plausible majority of the 320s wall time (their measured durations alone
  sum to well over 150s; the other ~311 tests are comparatively cheap unit
  tests).
- **In-range**: in-range — `test_tos_completion_status.py` (4542 new
  lines) and `test_u17_verify.py` (modified, +10/-few lines but exercises
  the same pre-existing `_run_script` pattern) are both in the diff's file
  list.
- **Hot/cold path**: this is dev-loop/CI-test cost, not runtime hot path.
  Distinguish two audiences: (a) **CI budget** — currently fine, see §③,
  because `test.yml` runs the whole `tests/` tree with `pytest -n auto`
  (parallel across ubuntu-latest's available cores), and the most recent
  full "Run tests" step (parallel pass + serial pass, entire `tests/` tree)
  completed in 5m07s against a 25-minute timeout. None of these tests carry
  a `serial` marker (confirmed: `grep -c "pytest.mark.serial"
  tests/tools/test_tos_completion_status.py` = 0), so they participate in
  the parallel pool and get divided across workers rather than serialized.
  (b) **Local single-worker iteration** — a developer running just this one
  file (or `pytest tests/tools` without `-n auto`) pays the full 5m20s
  serially, which is slow for an edit-test-repeat loop on what is
  nominally "checker unit tests."
  Also note: I could not complete the full `tests/tools` directory (827
  tests collected, includes non-diff files like `test_broker_probes_*`)
  within a 5-minute foreground timeout on the first attempt — it was
  running fine (94%+ complete, not hung) but this itself is a concrete
  signal that these tests are not the fast, cheap unit tests their
  `tests/tools` location suggests.
- **Recommendation**: measurement is what's needed here (this finding *is*
  the measurement), plus a design call for the maintainers: either (1)
  accept this as intentional integration-test cost living in a unit-test
  directory (the `test_real_corpus_*`/`_run_script` naming does self-
  identify as "real" vs mocked, so it may be a deliberate choice already),
  or (2) mark the 23 heaviest tests with a custom marker (e.g. `@pytest.mark.slow`)
  so `-k "not slow"` gives a fast local loop, without touching CI behavior
  (CI's `-n auto` handling is unaffected either way). Not recommending a
  behavior change myself — this is a design/DX tradeoff for the test-
  reliability owner, not a bug.
- **Confidence**: 90 (durations, test counts, and CI parallel-vs-serial
  status are all directly measured; the "plausible majority of wall time"
  claim is an arithmetic estimate from the 15 shown durations, not a full
  per-test accounting of all 334).

### P-4 (informational) — `u17-verify.sh` single live run: 23 HTTP calls in 23s, no retry/backoff

- **Location**: `tools/u17-verify.sh` (`gh api` call sites at lines 105 and
  124; no retry/sleep logic found — `grep -n "retry\|--max-attempts\|sleep"
  tools/u17-verify.sh` matched nothing beyond the comment header).
- **Finding**: analyzed the pre-existing live-run capture at
  `/private/tmp/.../scratchpad/u17-verify-live.txt` (left by a prior attempt
  at this same audit task, per the task instructions — not re-run here).
  23 `http=`/`status=` lines, first `utc=2026-09-03T07:39:04Z`, last
  `utc=2026-09-03T07:39:27Z` → **23 seconds wall for one full run**, ~1
  HTTP call/second. Uses `gh api --paginate` (unbounded pages) and
  `gh api --paginate --slurp` for two endpoints, but the actual run's own
  log shows small result sets ("partial last page(4<100)", "partial last
  page(2<100)", "partial last page(1<100)") so pagination terminated after
  1 page each — not evidence of a pagination blowup risk at current data
  volumes (workflow runs / rulesets / PRs for this repo are all small
  counts). The script also does its own full-repo `git clone --no-local
  --no-hardlinks` snapshot at the start (same P-1 pattern), separate from
  the checkout inherited by the caller.
- **In-range**: in-range (`tools/u17-verify.sh` has diff changes: +2/-… per
  the diff stat).
- **Hot/cold path**: cold — this is invoked from CI/manually, not a
  runtime path.
- **Recommendation**: no retry/backoff means a single transient GitHub API
  hiccup fails the whole 23s run and forces a full re-run from scratch
  (including re-paying the git-clone snapshot cost) — a reliability
  observation with a mild performance corollary (wasted re-run cost on
  flake), not a correctness bug. Not blocking; worth a one-line note to the
  script owner if retries aren't already handled by a caller-level wrapper
  I didn't check.
- **Confidence**: 60 (the 23s/23-call figure is measured from an existing
  capture I did not regenerate myself this run, and I did not check whether
  a caller wraps `u17-verify.sh` in its own retry logic).

## ③ Checked and sound

- **`tos_completion_status.py --check`**: 8.997s wall (`6.73s user 3.06s
  system 108% cpu`), rc=0, RESULT: GREEN. Not a bottleneck at current CI
  budget (see workflow timing below).
- **`tos_spec_status.py --check`**: 0.647s wall, PASS.
- **`tos_contract_check.py` (default)**: 0.578s wall, PASS.
- **`tos_contract_check.py --self-test`** (145-mutation battery): 70.39s
  wall (`63.31s user 4.23s system 95% cpu`) ≈ 0.49s/mutation, in line with
  the ~0.58s base-check cost — confirms the battery is linear in mutation
  count × base-check-cost, not superlinear/blown-up. All 145 mutations +
  2 classifier controls PASS.
- **`tos_contract_index.py --locate S-26`**: 0.182s wall. `DEFAULT_COMMITS
  = 30` (line 57) bounds its survival-check history scan to a fixed 30
  commits, not the full 2403-commit repo history — correctly bounded, not
  a source of growth.
- **`_git_rev_list_full_history`/`_find_config_introduction_commits`**
  (`tools/tos_completion_status.py:1985-2091`, U-15-g config-provenance
  derivation): standalone-measured `git rev-list --full-history HEAD --
  config/tos_completion.yaml` = 58ms, 2 candidates, against a 2403-commit
  repo (`git rev-list HEAD | wc -l` = 2403, 29ms). Called once per
  `--check` run for one fixed path (`CONFIG_REL`), not per-row/per-item —
  correctly scoped by path rather than scanning full history unfiltered.
- **CSV-join complexity** (register × EVIDENCE-SURFACE-MAP × EVIDENCE-
  REQUIRED-KINDS): the relevant structures are explicitly typed as
  `dict[str, ...]` (`register_by_id: dict[str, dict[str, str]]`,
  `required_kinds_by_id: dict[str, frozenset[str]]`,
  `tools/tos_completion_status.py:171,174,478`) and built via dict
  comprehension, not nested loops — this is dict-indexed O(n+m) joining,
  not O(n·m). At current sizes (register ~490 rows via
  `PHASE0-UNCHECKABLE-REGISTER.csv`=25 lines /
  `EVIDENCE-REQUIRED-KINDS.csv`=488 lines /
  `EVIDENCE-SURFACE-MAP.csv`=2024 lines) this would be cheap even if it
  weren't dict-indexed, but the pattern is also correctly future-proofed.
- **Contract-document memory pattern**: `tools/tos_contract_check.py`
  `main()` reads the 10k-line/1.3MB contract document exactly **once**
  (`contract.read_text()` at line 7414) and passes the resulting `text`
  string by reference into `check_document`/`run_self_test` — no
  re-reading per rule (C1-C4) or per mutation in the self-test battery.
  Confirmed no repeated-`read_text`-on-the-contract-doc pattern anywhere
  else in that file (only 5 `read_text(` call sites total, none of them a
  second read of the contract path).
- **`git ls-files`-based census vs `os.walk` fallback**
  (`tools/tos_spec_status.py:1697` `_reverse_scan_git_universe`, commit
  `faea9720`): timed both paths directly. `git ls-files -z --cached
  --others --exclude-standard`: 33-38ms (3 warm runs), 3866 paths. Exact
  `os.walk` fallback logic (using the real `_REVERSE_SCAN_SKIPPED_DIRS` set
  — `tos, tos-spec, tests, node_modules, __pycache__, build, dist, venv,
  site-packages` — plus its dot-prefix directory pruning, which also
  correctly excludes `.venv`, `.git`, `.pytest_cache`, etc. without needing
  them in the named set): 24ms, 3294 files pre-eligibility-filter. Verdict:
  **os.walk is marginally faster than the git-subprocess path at this repo
  size** (git's process-spawn overhead outweighs its smaller walk surface);
  the migration to git-based census was a correctness fix (respects
  `.gitignore`, no drift with `os.walk`'s duplicated skip-list), not a
  performance regression. Both are sub-40ms, negligible against the
  multi-second `--check` runtime.
- **`tos-firewall.yml` CI budget** (`timeout-minutes: 10`): most recent
  successful run (`databaseId=33636732053`, 2026-09-02) — step timings via
  `gh run view --json jobs`: Checkout 3s, Setup Python 4s, Install deps 15s,
  Layer 1 (AST firewall) 2s, Layer 2 (import-linter) <1s, **`pytest
  tos/tests`** 100s, `tos_spec_status --check` <1s, `tos_completion_status
  --check` 7s, Layer 4 contract gate 1s, **Layer 4 self-test (mutation
  battery)** 129s. **Total job: 4m22s (262s) against a 600s budget — 44%
  utilized.** The two heavy steps (`pytest tos/tests` + self-test battery)
  are 229s of that 262s (87%), so there is headroom but the two dominant
  costs are concentrated and worth watching as `tos/tests` count or
  mutation-battery size grows, not urgent today.
- **`test.yml` CI budget** (`timeout-minutes: 25`): most recent successful
  run (`databaseId=33636731968`, same push) — the "Run tests" step (both
  the `-n auto` parallel pass and the `serial` pass, over the **entire**
  `tests/` tree, not just `tests/tools`) took 13:37:43→13:42:50 = **5m07s
  (307s) against a 1500s budget — 20% utilized.** This confirms that,
  despite the single-worker 5m20s finding in P-3, CI's xdist parallelism
  (`-n auto`) absorbs the heavy git-fixture tests fine at current scale;
  none of the P-3 tests carry the `serial` marker, so they run in the
  parallel pool.

## ④ Not verified / out of scope for this pass

- **Full `tests/tools` directory** (827 tests, includes non-diff files
  like `test_broker_probes_*` [257 tests] and `test_tos_firewall_check.py`
  [46 tests]): not run to completion. The 5-minute foreground attempt got
  to 94%+ without failing/hanging before I switched to running just the
  diff-touched subset in the background instead. Given the diff-touched
  subset (334 tests) alone took 5m20s single-worker, the full directory
  would plausibly take somewhat longer, but I have no direct measurement
  of the non-diff files' contribution and did not attribute it.
- **`tos/tests` full-suite timing**: re-verified directly this run
  (`PYTHONPATH=tos/src .venv/bin/python -m pytest tos/tests -q
  -p no:cacheprovider`): **39.49s wall** (`33.27s user 4.45s system 95% cpu`),
  100% dots with no `F`/`E` in the output — consistent with the prior
  attempt's cited figure (8,756 tests, 43.79s; this run didn't re-capture
  the exact collected-test count but timing is in the same range). Moved
  from "not verified" to confirmed — this suite is fast and not a concern.
- **GitHub Actions runner-vs-local slowdown factor for the self-test
  battery**: measured 70.39s locally vs 129s in the one CI run inspected
  (≈1.84x). I did not sample multiple CI runs to check variance, so this
  ratio should be treated as a single data point, not a stable multiplier.
- **`tos_evidence_run.py` subprocess call sites** (lines 490, 743, 2173):
  inspected each call site's immediate context (`_git` helper,
  `probe_interpreter`, main pytest-invocation runner) and found no
  loop-wrapped subprocess spawning at those three sites, but did not trace
  every caller of `_git()` across the 3233-line file to confirm none of
  them are invoked in a per-row loop elsewhere in the file. Time-boxed out.
- **`tos_profile_census.py`** (101 lines): read for size/shape only (no
  `read_text` calls found via grep, suggesting it likely consumes
  structures already loaded by a caller rather than doing its own I/O), not
  independently timed or profiled — it's small enough that a targeted look
  seemed low-yield relative to the rest of the scope, but I did not
  actually run it standalone to confirm.


File sizes at HEAD (line counts):
- tools/tos_completion_status.py: 4162
- tools/tos_spec_status.py: 2306
- tools/tos_contract_index.py: 1299
- tools/tos_evidence_run.py: 3233
- tools/tos_profile_census.py: 101
- tools/wfcanon-v222.py: 542
- tools/tos_entry_harness.sh: 115
- tools/u17-verify.sh: 917
- tos-spec/src/verification/EVIDENCE-REQUIRED-KINDS.csv: 488 lines
- tos-spec/src/verification/EVIDENCE-SURFACE-MAP.csv: 2024 lines (task description said "959 pairs" — line count is roughly 2x that, needs reconciliation, see below)
- tos-spec/src/verification/PHASE0-UNCHECKABLE-REGISTER.csv: 25 lines

---
