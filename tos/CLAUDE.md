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
| Application Runtime + Infrastructure Adapters (ratified by the operator 2026-09-08, design #40 D1) | `tos/runtime/` — SEPARATE distribution `tos-runtime` / `tos_runtime` (own `pyproject.toml`, src-layout `tos/runtime/src/tos_runtime/`), the composition root + I/O adapters for the kernel. `tos_runtime -> tos` allowed; `tos -> tos_runtime` FORBIDDEN (firewall rule (g) + `.importlinter` contract `tos-kernel-must-not-import-runtime`). Application Runtime + Infrastructure Adapters: composition, durable event processing, SQLite evidence/state, custody, market intake, synthetic/KIS mock transport, recovery, and operations CLI are implemented. `compose/cli.py` dispatches `run` through `_run_dispatch.py`; this is no longer a skeleton. Implementation is not live authorization. See `docs/architecture/tos-system-context.md` and `docs/architecture/tos-public-interfaces.md` for layer names, integration surfaces, and remaining gaps. Hermetic tests: `tos/runtime/tests/` (D1.4 — zero external network/ambient env/writes outside `tmp_path`; `127.0.0.1`/`::1` and `tmp_path` sqlite files are the one exception, guarded by an autouse fixture in `tos/runtime/tests/conftest.py`) |
| Governance tools | `tools/tos_*.py` |
| Governance tests | `tests/tools/test_tos_*.py`, `tests/tos_l3/` |
| Architecture / integration docs | `docs/architecture/tos-*.md`, `docs/migration/legacy-disposition.md`, `docs/PROJECT_STATUS.md` (TOS snapshot) |
| Design docs / errata | `docs/plans/*tos*` |
| CI | `.github/workflows/tos-firewall.yml`, `.github/workflows/tos-gate.yml` |

The runtime must not import any `shared.*` package (including the six kernel
commons exceptions); code outside `tos/` must not import either `tos` or
`tos_runtime`. Product integration uses serialized process boundaries.

Everything else in the repo (`shared/`, `services/`, `strategy-builder-ui/`,
`config/strategies/`, `tests/unit/`, Docker files) is the legacy runtime and
is out of scope for tos work unless the task says otherwise.

## Commands

```bash
# Hermetic package tests from the repo root venv
PYTHONPATH=tos/src .venv/bin/python -m pytest tos/tests -q

# Runtime shell hermetic tests (ratified by the operator 2026-09-08, design #40 D1 — see the table above).
# Isolated rootdir (tos/runtime/pyproject.toml's own [tool.pytest.ini_options]),
# same pattern as the kernel command above.
PYTHONPATH=tos/runtime/src:tos/src .venv/bin/python -m pytest tos/runtime/tests -q

# Standalone environment (no legacy stack): pinned deps from tos/pyproject.toml.
# Subshell so the cwd returns to the repo root for the checkers below. The
# environment lands in tos/.venv (gitignored); the firewall forward scan prunes
# `.venv` by exact name, so it does not get scanned.
(cd tos && uv sync --extra test && uv run pytest tests -q)

# Firewall + governance checkers — run from the repo root with the root venv
# (they import the repo `tools` package and read repo-relative paths)
python tools/tos_firewall_check.py && lint-imports
python tools/tos_redigest.py --check   # the `tos-gate` required check
python tools/tos_size_budget.py --check
```

## Hard constraints specific to tos

- Third-party deps are pinned in `tos/pyproject.toml` and limited to the
  design §3.2 allowlist (`pydantic`, `numpy`, `pandas`, `pyyaml`; test:
  `pytest`, `hypothesis`). Adding one is a design-doc PR, not a code change.
- No stdlib egress in kernel code (`socket`, `subprocess`, `os.environ`
  intake, dynamic import). The AST gate rejects it.
- The Phase-0 완료 계약과 그 판정 장치(계약서 · `tos_contract_index.py` ·
  `tos_contract_check.py` · `tos_completion_status.py` · `tos_entry_harness.sh` ·
  `u17-verify.sh`)는 2026-11-12 에 퇴역했다
  (`docs/plans/2026-11-12-phase0-retirement-plan.md`). 내용은 git 이력에 있다.
- 명세 코퍼스 `tos-spec/`(66k 줄) 와 증거 `tos-evidence/`(25k) 는 2026-11-13 에
  은퇴했다 (`docs/plans/2026-11-13-tos-code-halving-plan.md` §S3). 그들만 읽던
  `tos_spec_status.py` · `tos_evidence_run.py` · `tos_profile_census.py` 와 그
  테스트, mdBook CI 단계, 명세 앵커 커널 테스트(`sci/test_sci_anchor_drift.py` ·
  `sci/test_sci_authority.py` · `stm/test_stm_adr_enumeration_closure.py` ·
  `stm/test_stm_anchor_resolution.py`)도 함께 지웠다. 커널·런타임의
  `tos-spec/src/...` 인용은 S4 산문 걷어내기(docstring 첫 줄만)에서 함께 사라졌다.
- `.github/workflows/tos-gate.yml` 은 삭제하거나 잡 이름을 바꾸지 않는다 —
  룰셋이 `tos-gate` 체크를 필수로 요구하므로, 사라지면 모든 PR 이 오지 않는
  체크를 기다린다. 내용은 `tools/tos_redigest.py --check` 다.
