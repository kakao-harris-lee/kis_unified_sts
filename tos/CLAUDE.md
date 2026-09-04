# tos/ — Trading Operating System kernel (agent scope guide)

This directory is a **separate distribution** (`tos`, src-layout, own
`pyproject.toml`) living inside the `kis_unified_sts` monorepo. Read the root
`CLAUDE.md` first for repo-wide rules; this file narrows the working set for
tos work so agents do not scan the legacy runtime.

## Relationship to the legacy runtime (ratified 2026-07-20)

- Design contract: `docs/plans/2026-07-20-tos-boundary-and-import-firewall-design.md`
  (strategy B — isolated cohabitation → content migration → inversion).
- **Asymmetric import firewall (design §3).** Reverse direction is absolute:
  nothing outside `tos/` may import `tos`. Forward direction is default-deny
  with one carve-out: `tos/` may import only the six ratified pure-commons
  packages `shared.models`, `shared.indicators`, `shared.resilience`,
  `shared.utils`, `shared.exceptions`, `shared.determinism` (the
  `SHARED_ALLOWED` set in `tools/tos_firewall_check.py`). Two layers enforce
  it, with different reach: (1) the AST gate rejects any *direct* import in
  `tos/` that is not stdlib, an allowlisted third party, or one of the six
  (so `shared.config`, `services`, `tools`, `cli` are all direct-denied);
  (2) the `.importlinter` contract additionally forbids *transitive* reach
  from `tos` into the §2.3 operational set only: `shared.execution`,
  `shared.kis`, `shared.streaming`, `shared.llm`, `shared.storage`,
  `shared.backtest`, `shared.config.secrets`, `services`, `cli`. A commons
  package pulling in `tools` or non-secrets `shared.config` transitively is
  **not mechanically enforced by either layer**; it is covered only by the
  manual commons-closure review the design records as residual risk (§4,
  design #3 checklist). Both layers run in the `tos-firewall` CI job. As of 2026-09-04 the kernel
  uses none of the six (measured: 0 `shared` imports under `tos/src`); do not
  add an allowlist entry without a §6.1 revision-log line in the design doc.
- The legacy runtime is not a reference implementation for tos. Do not port
  `shared/execution`, `shared/kis`, or service code into `tos/`; the safety
  core is greenfield by spec (IMPLEMENTATION-PLAN-002 §2).
- Repo split (strategy C) is deferred to the live gate by design §6.2; the
  eventual separation removes the legacy runtime from this repo, it does not
  move `tos/` out. Do not propose moving `tos/` to a new repo as a side effect
  of other work — the Phase-0 governance is bound to this repo's git history
  (commit SHAs, `git rev-list --full-history` predicates, blob digests).

## Working set for tos tasks (search here, not the whole repo)

| Concern | Where |
| --- | --- |
| Kernel code | `tos/src/tos/` (one package per RFC component: `rcl`, `authority`, `egressgw`, `engine`, `marketfeed`, `capsule`, `evidence`, `staterestore`, …) |
| Hermetic tests | `tos/tests/` (no `.env`, no network, no Redis; pytest rootdir is `tos/`) |
| Spec (normative, broker-agnostic) | `tos-spec/src/` — RFC/ADR/verification registers |
| Evidence runs | `tos-evidence/` |
| Governance tools | `tools/tos_*.py`, `tools/tos_entry_harness.sh`, `tools/u17-verify.sh`, `tools/wfcanon-v222.py` |
| Governance tests | `tests/tools/test_tos_*.py`, `tests/tools/test_u17_verify.py`, `tests/tos_l3/` |
| Design docs / errata | `docs/plans/*tos*`, `docs/reviews/phase0-*` |
| Completion config | `config/tos_completion.yaml` |
| CI | `.github/workflows/tos-firewall.yml`, `.github/workflows/tos-gate.yml` |

Everything else in the repo (`shared/`, `services/`, `strategy-builder-ui/`,
`config/strategies/`, `tests/unit/`, Docker files) is the legacy runtime and
is out of scope for tos work unless the task says otherwise.

## Commands

```bash
# Hermetic package tests from the repo root venv
PYTHONPATH=tos/src .venv/bin/python -m pytest tos/tests -q

# Standalone environment (no legacy stack): pinned deps from tos/pyproject.toml.
# Subshell so the cwd returns to the repo root for the checkers below. The
# environment lands in tos/.venv (gitignored); the firewall forward scan prunes
# `.venv` by exact name, so it does not get scanned.
(cd tos && uv sync --extra test && uv run pytest tests -q)

# Firewall + governance checkers — run from the repo root with the root venv
# (they import the repo `tools` package and read repo-relative paths)
python tools/tos_firewall_check.py && lint-imports
python tools/tos_contract_check.py && python tools/tos_contract_check.py --self-test
python tools/tos_completion_status.py --check
python tools/tos_spec_status.py --check
```

## Hard constraints specific to tos

- Third-party deps are pinned in `tos/pyproject.toml` and limited to the
  design §3.2 allowlist (`pydantic`, `numpy`, `pandas`, `pyyaml`; test:
  `pytest`, `hypothesis`). Adding one is a design-doc PR, not a code change.
- No stdlib egress in kernel code (`socket`, `subprocess`, `os.environ`
  intake, dynamic import). The AST gate rejects it.
- The Phase-0 completion contract
  (`docs/plans/2026-08-12-tos-phase0-completion-contract-design.md`) is frozen
  and blob-bound. Never edit it as a side effect; locate sections with
  `python tools/tos_contract_index.py --locate <ID>` and read only that range.
- `tools/tos_entry_harness.sh` is sha256-pinned in `tos-gate.yml`, and
  `tos-gate.yml` itself is a contract literal read by `u17-verify.sh`. Changing
  either is a re-pin round, not a routine edit.
