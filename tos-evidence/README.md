# `tos-evidence/` — EV-L1 run package store

Machine-produced evidence packages for the Evidence Register
(`tos-spec/src/part-1-foundation/verification/EVIDENCE-REGISTER-002.csv`, the
machine-editable source of truth). Every package here is written by
`tools/tos_evidence_run.py`; nothing in this tree is hand-edited.

## Path structure

```text
tos-evidence/
  README.md
  <EVIDENCE-ID>/                 e.g. STATE-EV-001
    <run-id>/                    <UTC timestamp>-<git short sha>
      manifest.yaml              run metadata, result, discipline tag, artifact digests
      baseline.yaml              design #1 §5.1 seven items + all 22 VER-002-001 §3 fields
      traceability.csv           EV-ID -> ADR -> design document -> test node -> mapping basis
      junit.xml                  pytest --junitxml output
      run.log                    captured stdout + stderr + return code
      sha256sums.txt             sha256 of every retained file (written last)
```

This is the run-scoped equivalent of the VER-002-001 §8 (:299-340) recommended
package; §8 permits equivalent structures that preserve the required properties.
The `evidence_location` column of the register points at `tos-evidence/`.

## Append-only (VER-002-001 §9.1)

A run directory is created exclusively and every file inside it is opened with
mode `"x"`. Re-running against an existing run directory **fails** with exit
code 2; existing packages are never rewritten, and the test identity, baseline,
and seed of a started run are immutable. Corrections are made by adding a new
run, never by editing an old one.

`sha256sums.txt` is written last, so it closes over `manifest.yaml` as well — a
manifest cannot contain its own digest.

## What a run package does *not* claim

Every manifest carries this tag verbatim:

> EV-L1 stage execution record only; not a row PASS; incomplete until
> independent review signs (VER §9.5) and P0-1 (bounds approval) closes; staged
> rows require higher stages before acceptance (VER:171).

Concretely: a green run does not move a register row to `PASS`, does not close
an evidence item, and does not cover the `/2`, `/3`, `+Security`, or `+Broker`
stages named in a row's `minimum_evidence_level`. The Verification Profile is
recorded as `2.1 (PROPOSED — P0-1 open)` — recorded, not approved.

The baseline is deliberately a **subset**: VER §3 requires 22 fields and states
that "A run without a complete baseline is invalid", while design #1 §5.1
(`docs/plans/2026-07-20-tos-boundary-and-import-firewall-design.md`) ratifies
seven of them as the EV-L1 subset. Fields whose artifacts do not exist yet
(Hard Safety Envelope, Runtime Safety Profile, the policy generations, Broker
Capability Profile, deployment manifest, key versions, …) are emitted as
`NOT_APPLICABLE_EV_L1` **with a reason** and never with a fabricated value. Each
`baseline.yaml` states in-band that it is complete for EV-L1 only.

## Role fields (D1 convention)

The register's administrative columns follow the operator's D1 decision
(`docs/plans/2026-07-29-tos-phase0-role-scheme-and-disposition.md` §1):

| Role | Recorded string |
|---|---|
| System owner / Bounds-Approver / Evidence owner | `operator` |
| Implementation owner | `ai-impl(claude-orchestrated)` |
| Independent reviewer | `ai-review(decorrelated)+operator-countersign` |
| Live-Armer | intentionally unassigned (fail-closed; column left blank) |
| `verification_profile_version` | `2.1-PROPOSED` |
| `evidence_location` | `tos-evidence/` |

The independent reviewer signs the *evidence manifest* (VER §9.5:364-366) with
recorded provenance — model/substrate and determining inputs — per the
ADR-DEV-005 §7 independence standard. No sign-off record exists in this tree
until that review happens; its absence is why every manifest says
`independent_review: NOT_SIGNED`.

## Producing a run

```bash
.venv/bin/python tools/tos_evidence_run.py \
  --evidence-id STATE-EV-001 \
  --primary-adr ADR-002-005 \
  --design-doc docs/plans/2026-07-25-tos-orthogonal-state-design.md \
  --source-path tos/src/tos/orthostate \
  --seed-policy fixed:0 \
  --node 'tos/tests/orthostate/test_orthostate_composite.py | <measured mapping basis>'
```

The harness refuses to run when: the evidence id is not in the register, a named
test node file does not exist, an executed file is dirty at `HEAD` — including a
file inside a brand-new untracked package, which `-uall` enumerates individually
(pass `--allow-dirty-targets` to record the dirt in-band instead) — the run
directory already exists, or the run directory would fall outside the evidence
root.

Exit codes: `0` all selected tests green; `1` tests not green **or nothing
executed** (a wholly-skipped or empty selection exits 0 under pytest and is
recorded as `NO_TEST_EXECUTED`, never as green); `2` precondition failure,
append-only violation, or integrity violation. The package is written in the `1`
and integrity cases — the record of what happened is itself evidence.

Integrity checks carried in every package:

- executed files are digested **before and after** the run; a file changed while
  the tests ran is recorded per-file as `MUTATED_DURING_RUN` and the run exits
  `2` (a post-hoc digest alone would record the mutated file as the file that
  ran);
- the worktree is captured before and after, with the delta;
- the harness watches **itself** — it is in the digest set, and its own
  provenance is derived, not assumed: `harness_tracked` / `harness_at_commit`
  (`NOT_IN_COMMIT` while the harness is uncommitted, so the repository HEAD is
  never passed off as the harness version). It is exempt from the cleanliness
  *refusal* only, and that exemption is visible per-file as
  `cleanliness_guarded: false`;
- a run that raises before its package is closed leaves an `INCOMPLETE_RUN.txt`
  marker, so a partial directory can never be read as a completed run;
- `sha256sums.txt` is flat, so a subdirectory inside a run package is refused
  rather than retained without a digest.

Verify a package:

```bash
cd tos-evidence/<EVIDENCE-ID>/<run-id> && shasum -a 256 -c sha256sums.txt
```
