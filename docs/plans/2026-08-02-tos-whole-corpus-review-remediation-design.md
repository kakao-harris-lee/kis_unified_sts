# TOS whole-corpus review remediation design (2026-08-02)

> **Standing:** Phase 0 gap-closing audit and execution design. This document is
> non-normative. It performs no RFC ratification, ADR acceptance, evidence
> promotion, restricted-live gate, production authorization, or broker action.
> `tos-spec/src/` remains canonical; `tos-spec/book/` is generated output.

## 0. Scope, boundaries, and reverified baseline

This stream repairs the specification, governance record, evidence semantics,
and current-to-target account before any further ADR mechanism implementation.
It does not execute or review the separately owned KIS measurement handoff, call
broker endpoints, read secrets, change a trading runtime, or alter paper/live
authorization.

Repository state at the start of this audit:

| Item | Reverified state | Method / limitation |
|---|---|---|
| Worktree / branch | isolated `fix/tos-review-remediation`, clean | `git status --short --branch`; `git worktree list --porcelain` |
| Base | `a62d72a1`, zero ahead/behind the locally recorded `origin/mission-critical-trading-operating-system` | `git merge-base`; `git rev-list --left-right --count` |
| Remote freshness | not independently network-confirmed | `git ls-remote` failed because the sandbox could not resolve `github.com`; no remote ref was mutated |
| TOS Python sources | 241 files | `find tos/src -name '*.py' -type f \| wc -l` |
| TOS test sources | 536 files | `find tos/tests -name '*.py' -type f \| wc -l` |
| TOS tests | 8,560 passed | `PYTHONPATH=tos/src ... pytest tos/tests ... -q`; collection count independently summed from `--collect-only` |
| Import firewall | PASS | `python tools/tos_firewall_check.py` |
| mdBook | PASS | `mdbook build tos-spec -d /private/tmp/tos-review-mdbook-baseline` |
| Part-1 evidence | 372 total: 292 `NOT_IMPLEMENTED`, 79 `READY`, 1 `PASS` | authoritative CSV `tos-spec/src/part-1-foundation/verification/EVIDENCE-REGISTER-002.csv` |
| Development evidence | 98 total: 98 `NOT_IMPLEMENTED` | authoritative CSV `tos-spec/src/part-3-development/verification/EVIDENCE-REGISTER-DEV.csv` |
| Effective document state | 13 Ratified RFC-class baselines; all 30 ADR-002 and 15 ADR-DEV records remain Proposed | canonical headers plus `ARCHITECTURE-GATE-STATUS.md` §9.6/§9.7 |
| Live authority | restricted-live not authorized; production authorization `NO` | ADR-002-025 §§11, 18, 29; active register headers |

The 8,560 passing unit/property tests are implementation test results only. They
do not move an evidence row; evidence state additionally requires the governed
run artifacts, minimum level, profile binding, independent review, and signature
requirements in VER-002-001.

## 1. Classification and authority model

Every remediation item uses one of four action classes:

| Class | Meaning | Who may complete it |
|---|---|---|
| Mechanical | deterministic mirror/count/link/traceability repair with no new obligation or authority | implementation stream, followed by review |
| Normative | new or materially changed RFC/VER contract; prior Ratified version remains governing under GOV-001 G6 until the new version is re-ratified | author may draft; System Owner/Architecture Board must decide |
| Evidence-producing | an executed governed evidence run that may change a register row | evidence owner plus independent reviewer/signature workflow |
| Human-authority-only | profile bounds, ratification/de-ratification, ADR acceptance, investment mandate, restricted-live, or production decision | named accountable human authority only |

GOV-001 G1 separates ratification, ADR acceptance, and live authorization
(`tos-spec/src/part-1-foundation/GOV-001-Ratification-and-Change-Governance.md`
§3 G1). G3 P2 requires every finding and carried open question to be resolved or
explicitly deferred with rationale (§4 G3). Material edits to Ratified RFCs use
G6 amendment and re-ratification; G7 de-ratification is a System Owner act. This
stream may draft those artifacts but may not perform the acts.

## 2. Finding-by-finding gap design

### F1 — CONST-003 has no economic-expectancy evidence family

**Current coverage and exact sources**

- RFC-000 CONST-003 defines Positive Expectancy and currently names the composite
  `RFC-003 §12 -> RFC-006 §11 -> ADR-002-025 RLP-EV-001..012`
  (`RFC-000-Trading-Constitution.md` §7 CONST-003, especially Traceability).
- RFC-003 §12 requires population-level evaluation, backtest-as-evidence-only,
  cost/slippage/impact realism, and non-authority; its traceability note still
  names RLP-EV-001..012 as completion (`RFC-003-Decision-Framework.md` §12 and
  §15 CONST-003 composite-discharge note).
- RFC-006 §11 covers population, costs, uncertainty, regime dependence,
  restricted-live, and non-authority at methodology level; its completion note
  also points to RLP-EV-001..012 (`RFC-006-Risk-Model.md` §§11, 16).
- ADR-002-025 §26 and VER-002-001 cases RLP-EV-001..012 cover exact trial scope,
  capacity separation, no bypass, abort, evidence retention, non-extrapolation,
  promotion, role separation, expiry, recovery, demotion, and gate honesty
  (`ADR-002-025...md` §§26, 29; `VER-002-001...md` Part XXV).
- DEC-EV-001..005 inspect only whether Part-2 authority boundaries reduce to
  RFC-002 §9.1 (`VER-DEV-001...md` §5 DEC-EV). BTE-EV-001..007 govern backtest
  admissibility but do not demonstrate out-of-sample or restricted-live economic
  viability (`VER-DEV-001...md` §5 BTE).

**Missing contract/evidence**

Create a dedicated `ECO-EV` economic-viability family in the development track,
owned at the smallest layer that already owns the methodology: a **Proposed
RFC-006 amendment**, coordinated with RFC-003/004/005/007. It must cover:

1. pre-registered hypothesis, population, benchmark, horizon, and stop rules;
2. fees, taxes, spread, slippage, impact, missed trades, rejections, partial fills,
   latency, and safety-induced opportunity loss;
3. uncertainty interval, sample discipline, estimation error, multiple-testing
   and selection-bias correction, and regime dependence;
4. out-of-sample and restricted-live evidence, with backtest explicitly not proof;
5. turnover, deployable capacity, capital efficiency, drawdown magnitude and
   duration, correlation to the existing book, and edge/alpha decay;
6. `PASS` / `FAIL` / `INCONCLUSIVE` semantics and explicit non-authority.

The amendment requires a versioned, approved Economic Viability Profile. Its
schema may be drafted now, but every numeric/ordinal acceptance bound remains a
human-owned field with no default. New `ECO-EV` rows start `NOT_IMPLEMENTED` with
TBD accountable owners and independent reviewer; no row is marked `READY` merely
because a template or test exists.

A deterministic gate will require both the economic family and applicable RLP
governance evidence. Its focused test sets hypothetical RLP-EV-001..012 to
`PASS` while leaving ECO incomplete and must still return CONST-003
`INCOMPLETE`. This is the machine proof that trial-safety governance alone cannot
complete positive expectancy.

**Failure modes**

- Operational: safe trial mechanics are mistaken for a profitable strategy;
  optional stopping and selected runs are allowed to masquerade as evidence.
- Investment: gross backtest edge disappears after total costs, correlation,
  capacity, or decay; capital is allocated to negative or non-deployable edge.
- Governance: a safety-governance `PASS` is promoted into investment mandate or
  production authority.

**Affected files**

RFC-000, RFC-003, RFC-006, ADR-002-025 traceability statements (drafted through
the G6 package); VER-DEV-001; EVIDENCE-REGISTER-DEV CSV/Markdown; the Economic
Viability Profile template; generated status/count surfaces; the P2 package.

**Class / decision gate**

Normative + evidence-producing + human-authority-only. Codex may add Proposed
cases and `NOT_IMPLEMENTED` registrations. The System Owner must authorize the
RFC amendment track; Investment Authority owns profile bounds; an independent
reviewer owns evidence review. No completion claim precedes those acts.

**Verification / rollback**

Verify ID uniqueness, all required administrative fields, count/mirror parity,
profile fail-closed validation, ECO semantic coverage, and RLP-only negative
gate. Roll back the isolated normative commit as a unit if the owner rejects the
governing home; retain this finding and the old chain as unresolved rather than
silently reverting to a false completion claim.

### F2 — Part-2 Ratification records do not visibly discharge G3 P2

**Current coverage and exact sources**

- GOV-001 G3 P2 requires every finding and carried open question to be resolved
  or explicitly deferred with rationale before Ratification-Ready
  (`GOV-001...md` §4 G3).
- RFC-003 §16 retains three unresolved/residual questions (Q2, Q5, Q6); RFC-004
  §15 retains six; RFC-005 §16 retains six; RFC-006 §17 retains seven; RFC-007
  §16 retains six: **28 total**.
- RR-0005..RR-0009 record P2 as satisfied but principally carry implementation or
  evidence deferrals, not one disposition per open question
  (`ARCHITECTURE-GATE-STATUS.md` §9.7 RR-0005..RR-0009).
- RR-0010 is the sound pattern: it names open questions, Proposed ADR-DEVs, and
  states that resolution occurs only when the ADR is accepted
  (`ARCHITECTURE-GATE-STATUS.md` §9.7 RR-0010).

**Missing contract/evidence**

Produce one line-by-line P2 disposition package with exactly one of:

- resolved in exact canonical text;
- deferred to a named Proposed ADR/profile/evidence owner, with rationale and a
  trigger that keeps the affected scope restricted;
- retained scope-restricting open debt, explicitly making P2 unmet.

The package drafts, but does not enact, the G6 amendment/re-ratification entries
for RFC-003..007 and the G7 option if the System Owner chooses de-ratification.
No old RR record is rewritten as if the later audit had occurred in 2026-07-18.

**Failure modes**

- Operational: contradictory model choices become ambient implementation
  convention, bypassing the canonical decision record.
- Investment: benchmark, cost, hedge, and risk-method choices drift by strategy,
  invalidating comparisons and portfolio aggregation.
- Governance: `Ratified` is interpreted as proof that P2 was established when the
  record cannot demonstrate it.

**Affected files**

RFC-003..007 Open Questions; ARCHITECTURE-GATE-STATUS RR-0005..0009 plus a new
dated audit/amendment record; GOV-001 citation-integrity record; generated status.

**Class / decision gate**

Normative + human-authority-only. The audit and draft package are implementable;
P2 remains `NOT ESTABLISHED BY THIS AUDIT` until the System Owner chooses the
amendment/de-ratification path and the required independent reviews pass.

**Verification / rollback**

Check exactly 28 source question IDs and exactly 28 dispositions; reject duplicate,
missing, unnamed, rationale-free, or trigger-free dispositions. Reverting the
draft package restores no claim of P2 satisfaction; the discrepancy remains open.

### F3 — Active current-state surfaces contradict authoritative registers

**Current coverage and exact sources**

- The Part-1 CSV contains 372 rows: 292 `NOT_IMPLEMENTED`, 79 `READY`, 1 `PASS`.
  Its Markdown mirror correctly reports those values
  (`EVIDENCE-REGISTER-002.md` Status / Status Summary).
- The DEV CSV contains 98 `NOT_IMPLEMENTED` rows and its mirror correctly reports
  98 (`EVIDENCE-REGISTER-DEV.md` Status Summary).
- `tos-spec/README.md` Status still calls RFC-003..011 `0.1 Review Draft`.
- `preface.md` §§"What this corpus is" and "Reading the current effective state"
  say every evidence item is `NOT_IMPLEMENTED`, and its table says 97 DEV items.
- `ARCHITECTURE-GATE-STATUS.md` header says verification not started and its §4.5
  says all 372/98 are `NOT_IMPLEMENTED` and Part-2/3 ratification is pending,
  while §9.6/§9.7 later records 13 Ratified RFC-class documents.
- RFC-002 §26 and IMPLEMENTATION-PLAN-002 still contain point-in-time counts and
  statuses that are presented as current rather than historical.

**Missing contract/evidence**

Add a deterministic status tool that reads canonical document/register headers
and both authoritative CSVs, validates allowed states and administrative fields,
derives counts, and renders one generated current-status surface. The output must
keep five independent axes: document ratification, ADR acceptance, evidence
state, restricted-live authorization, and production authorization. Active prose
will link to or embed the generated view; historical merge-map statements will be
labelled as historical and not rewritten into false present-tense claims.

**Failure modes**

- Operator: stale "not started" hides READY/PASS work or a future failure.
- Investment/governance: Ratified RFCs, Proposed ADRs, evidence PASS, and live
  authority collapse into one misleading status.
- Engineering: manual mirror edits drift from the CSV and counts change
  non-atomically.

**Affected files**

New status tool and focused tests; README; preface; ARCHITECTURE-GATE-STATUS;
IMPLEMENTATION-PLAN-002; RFC-002 current-state note; both register mirrors;
SUMMARY/index surfaces.

**Class / decision gate**

Mechanical. It changes no row status and no normative obligation. Generated
status explicitly reports Proposed/Not Authorized states.

**Verification / rollback**

Run `--check`, focused mutation tests, CSV/Markdown parity, header/status checks,
and mdBook. Revert this commit independently if rendering breaks; CSVs remain
authoritative and no evidence state is lost.

### F4 — Project LLM role conflicts with RFC-003

**Current coverage and exact sources**

- `docs/ROADMAP.md` Futures North Star says LLM context controls
  `veto / risk-mode / size / threshold` (§Futures, lines 347–350 at baseline).
- Setup A/C YAML enables LLM threshold tuning, directional regime blocks, veto,
  and `llm_adaptive` sizing (`config/strategies/futures/setup_a_gap_reversion.yaml`
  entry lines 63–86 and position lines 123–141; corresponding Setup C sections).
- `shared/strategy/entry/setup_llm_gate.py` uses LLM regime/risk mode/risk score to
  drop a direction or scale confidence; `setup_a_adapter.py` and
  `setup_c_adapter.py` apply it before signal emission.
- `shared/strategy/position/llm_adaptive_sizer.py` applies LLM risk score,
  confidence, and risk mode to quantity; monolithic futures remains the current
  operating path (`docs/ROADMAP.md` Current operating state).
- RFC-003 §8 classifies any value determining direction, quantity, price, exposure,
  or thresholds as Critical Input. §10 says an LLM/external value may be replayable
  but not independently recomputable and therefore may only be soft,
  non-determining evidence; relabeling cannot change classification.
- The TOS DSL carries deterministic config constants and admitted Capsule values,
  emits a non-authorizing Proposal, and binds direction/quantity basis
  (`tos/src/tos/dsl/determinism.py`, `proposal.py`). `tos.iap` requires a complete
  exact request and an injected independent-validation fact, but its Phase-1
  engine uses explicit non-authoritative stand-ins and closes no IAP evidence
  (`tos/src/tos/engine/__init__.py`, `standins.py`; `tos/src/tos/iap/__init__.py`).

**Missing contract/evidence**

Add a non-authorizing current-to-target conformance register:

| Current seam | Target | Migration proof |
|---|---|---|
| LLM directional regime block | deterministic rule owns direction; LLM may only provide restrictive veto | counterfactual parity and source-dependency test |
| LLM confidence/threshold scaling | approved deterministic config/Capsule inputs own thresholds | dependency-closure test proving no LLM-derived scalar is determining |
| LLM adaptive quantity | deterministic position/risk rule owns quantity; LLM may withhold but never enlarge or select quantity | side-by-side paper replay; quantity identical for equal deterministic inputs |
| LLM rationale/context | retained as attributed soft evidence | exact lineage/replay and non-authority test |

No runtime change occurs in this stream. A separate scoped implementation plan
must enumerate affected Setup A/C adapter/sizer/config paths, compatibility tests,
strategy-economic impact, paper counterfactuals, rollback, and an operator decision
gate before any config or trading behavior changes.

**Failure modes**

- Operational: a non-recomputable LLM value silently becomes a Critical Input and
  a proposal is approved despite failed independent recomputation.
- Investment: removing or changing the dependence without counterfactual evidence
  changes strategy economics, direction frequency, or exposure.
- Governance: calling a value "veto" or "context" disguises determining influence.

**Affected files**

ROADMAP current statement; conformance/migration register; proposed RFC-003/006
alignment package; future implementation plan only (runtime files are read-only
in this remediation).

**Class / decision gate**

Current-to-target audit is mechanical/non-normative; target contract is normative;
runtime migration is a later operator-approved implementation change.

**Verification / rollback**

Verify every current LLM use has a mapped target and test, and negative-grep the
TOS dependency closure for `shared.llm`. Rollback is removal of the planning
record only; current runtime remains unchanged throughout this stream.

### F5 — Safety architecture is ahead of the investment operating model (G-02..G-05)

**Current coverage and exact sources**

- `ARCHITECTURE-GATE-STATUS.md` §4.6 explicitly registers G-02 capital/portfolio
  allocation, G-03 market-data ingestion, G-04 multi-account/multi-broker
  concurrency, and G-05 safety latency/performance as future gaps.
- RFC-006 covers risk methodology and positive expectancy but does not assign an
  investment mandate, benchmark authority, capital-allocation decision, strategy
  budget, attribution, degradation, or retirement owner.
- ADR-002-002/RCL is the sole risk-capacity serialization authority; it is not an
  investment capital allocator. ADR-002-021 aggregates risk but does not choose
  which strategy deserves capital.
- ADR-002-018 governs Critical Inputs after admission, including continuity and
  gaps, but §4.6 correctly observes that source acquisition/backfill ownership is
  not defined.
- ADR-002-002 §37 leaves writer-epoch scope open for multi-account/multi-broker;
  the initial declared scope is single-account.
- Latency bounds exist as proposed/null or owner-approved individual values in
  VERIFICATION-PROFILE-002, but no end-to-end budget demonstrates that safety and
  economic viability survive real execution conditions.

**Missing contract/evidence**

Draft a consolidated Proposed Part-2 amendment set, preferring RFC-006 plus its
verification track and making cross-RFC allocations only where ownership demands:

- Investment Authority owns mandate, benchmark, allocation policy, strategy risk
  budgets, correlation/crowding, attribution, capital efficiency, capacity,
  degradation, and retirement; Risk Authority retains safety/risk limits.
- RFC-004 owns acquisition/context source classes and hands off admitted,
  continuity-proven, gap/backfill-complete inputs to ADR-002-018.
- RFC-005 owns measured execution/service-level decomposition; RFC-006 owns the
  economic survival test; no budget may be met by weakening a safety gate.
- Architecture Board owns account/broker partitioning, shared capacity domains,
  writer epochs, concurrency, and failure-domain rules before a second concurrent
  account or broker.

No numeric thresholds are invented. Profile schemas require named authorities,
version/digest, exact scope, approval, expiry/review, and fail-closed behavior for
unset values.

**Failure modes**

- Risk capacity is mistaken for a positive capital-allocation decision.
- Several locally viable strategies create correlated/crowded book risk or poor
  capital efficiency.
- Feed gaps or stale backfills become valid-looking Critical Inputs.
- Account/broker concurrency double-uses headroom or creates unowned state.
- Safety latency consumes the entire edge, or performance is "fixed" by weakening
  an admission/currentness gate.

**Affected files**

Proposed Part-2 amendment/P2 package; RFC-004/005/006/007 draft deltas;
VER-DEV-001 and Economic Viability Profile; G-02..G-05 status entries; migration
register; no trading runtime.

**Class / decision gate**

Normative + human-authority-only. Architecture Board, Risk Authority, Investment
Authority, data owner, and independent reviewer decisions remain explicit gates.

**Verification / rollback**

Verify owner separation, profile fail-closed fields, second-account/broker trigger,
source continuity/backfill precondition, and latency-budget safety invariance.
Reject/revert individual proposed amendments without changing the currently
effective Ratified baselines.

### F6 — Current-to-target migration and operator complexity debt

**Current coverage and exact sources**

- The project-side three-stage design is explicit: isolated coexistence, content
  migration, then inversion/cutover (`docs/plans/2026-07-20-tos-boundary-and-import-firewall-design.md`
  §1.1–§1.3). It requires direct live broker-order paths to be removed at final
  cutover, but does not inventory current paths and proof obligations in one view.
- Current futures remains the monolithic orchestrator; the decoupled F-9 chain is
  dormant and separately operator-gated (`docs/ROADMAP.md` Futures current state).
- `tos.engine` declares provisional bounds, stand-in Independent Approval and
  RCL authority, no broker authority, and no evidence closure
  (`tos/src/tos/engine/__init__.py`; `standins.py`).
- COMPLEXITY-REGISTER-002 §4 records the combined operator view (Q5) open and the
  safe-removal/decommission path (Q6) open for all eight mechanisms.

**Missing contract/evidence**

Add one non-authorizing migration/conformance register covering:

- every current legacy broker-order path and its fence/removal criterion;
- each TOS package, owning ADR, implementation level, evidence state, and trust seam;
- real authority versus stand-in/provisional mechanism;
- cutover, rollback, double-trade prevention, queued-work invalidation, and
  direct-egress removal proof;
- one consolidated operator-facing safety-state owner that displays upstream
  authority facts without becoming authority;
- decommission/removal criteria for all eight Q6 mechanisms.

A dashboard, cache, test, healthy process, or stand-in cannot be labelled authority.

**Failure modes**

- Legacy and TOS egress coexist and double-trade.
- Queued work from a predecessor generation drains after cutover or rollback.
- A provisional stand-in is treated as a linearizable RCL or independent approver.
- Operators assemble conflicting safety state from several dashboards/caches.
- A complex mechanism is removed without replacement proof, residual obligations,
  or rollback evidence.

**Affected files**

New migration/conformance register and SUMMARY entry; COMPLEXITY-REGISTER-002 Q5/Q6
links; ARCHITECTURE-GATE-STATUS G-02..G-05/current state; project ROADMAP link.

**Class / decision gate**

Mechanical/non-authorizing register now; normative ownership amendments and
operator-approved cutover/removal decisions later.

**Verification / rollback**

Verify every discovered broker send/import route and every `tos` package is
represented exactly once; fail if a row lacks authority class, evidence state,
cutover proof, or rollback. Revert the register commit without touching any
runtime path or worktree.

### F7 — ADR-002-002..006 lack direct Requirements Traceability

**Current coverage and exact sources**

- TRACEABILITY-MATRIX-002 §5.3 names exactly five source gaps and says RC, SA, BC,
  STATE, and RECON are not reachable through the SAFE→ADR bridge.
- Existing claimed requirement sets are available without invention:
  ADR-002-003..006 `Depends On` headers name their SAFE sets; ADR-002-002 is
  allocated SAFE-013/SAFE-015 in RFC-002 §9.1 and the RFC-002 Requirements
  Traceability Matrix.
- Existing EV allocation is explicit in each ADR's Verification/Approval Gate,
  VER-002-001, and the CSV `primary_adr` fields. HAZ relationships remain derived
  only through RFC-001's existing `Controlled by` mapping; no direct HAZ claim is
  added to an ADR.

**Missing contract/evidence**

Add a standard Requirements Traceability table to each of ADR-002-002..006 using
only those existing SAFE claims and existing RC/SA/BC/STATE/RECON/X evidence
families. Update the matrix to show 30/30 source tables, direct family
reachability, and zero source gaps. Add a check that discovers all 30 ADRs and
requires a direct table with at least one valid SAFE ID whose RFC-001 definition
exists and a matching registered primary evidence family.

**Failure modes**

- Direct source review cannot prove why a mechanism exists or which requirement
  its evidence family supports.
- Matrix coverage survives only because later ADRs co-claim a SAFE, masking loss
  of a foundational ADR or evidence family.
- A future tool invents per-case SAFE/HAZ relationships not present in source.

**Affected files**

ADR-002-002..006; TRACEABILITY-MATRIX-002; deterministic status/traceability tool;
focused tests; ARCHITECTURE-GATE-STATUS current debt line.

**Class / decision gate**

Mechanical traceability repair: no new SAFE, HAZ, ADR, invariant, evidence ID,
status, or authority. Review must confirm every mapping is transcribed.

**Verification / rollback**

Run direct-table discovery, SAFE existence, evidence-family/primary-owner checks,
matrix parity, links, mdBook, and `git diff --check`. Revert independently if any
mapping cannot be sourced; keep that ADR listed as a source gap.

## 3. Non-overlapping implementation sequence and commits

| Step | Scope | Class | Commit boundary | Completion criterion |
|---|---|---|---|---|
| 0 | This audit/design + plan index | non-normative | design only | all seven findings, sources, gaps, failures, files, gates, verification, rollback recorded |
| 1 | Status source-of-truth tool, generated surface, stale active prose | mechanical | no normative/evidence-row edits | generator/tests/checks pass; five status axes remain distinct |
| 2 | ADR-002-002..006 direct tables + matrix/check | mechanical | traceability only | 30/30 direct tables; no invented IDs |
| 3 | 28-row Part-2 P2 audit + G6/G7 owner package | normative draft | no evidence rows | exactly one disposition per question; explicit System Owner gate |
| 4 | ECO contract/profile schema + VER/CSV/Markdown registrations | normative draft + registration | separate from status mechanics | all new rows `NOT_IMPLEMENTED`; RLP-only negative proof passes |
| 5 | LLM current-to-target section + separate runtime migration plan | non-authorizing plan | no runtime/config edit | all determining uses mapped; operator gate stated |
| 6 | G-02..G-05 Proposed contracts + migration/conformance/Q5/Q6 register | normative draft + non-authorizing register | no evidence execution | owner separation and removal/cutover criteria complete |
| 7 | Full verification + discrepancy re-audit | verification only | final docs-only correction if needed | commands/totals recorded; no unreviewed discrepancy remains |

No step may claim a later step's result. In particular: source registration is not
execution; unit tests are not governed evidence; a Proposed amendment is not a
Ratified version; and an operator-facing view is not authority.

## 4. Verification matrix

The final pass will run and report exact totals for:

1. `git diff --check`;
2. `mdbook build tos-spec -d <temporary-output>`;
3. status generator/check and focused tests;
4. CSV/Markdown count, allowed state, ID uniqueness, administrative-field, profile,
   evidence-owner/reviewer, and mirror consistency;
5. citation/link and direct traceability reachability checks;
6. `PYTHONPATH=tos/src` full TOS suite with temp/cache/Hypothesis state outside the repo;
7. `python tools/tos_firewall_check.py`;
8. discrepancy searches for the stale active claims identified in F3;
9. Git status and commit review.

Anything skipped or blocked is reported. No KIS capability probe, broker call,
order path, secret read, live arming, production mutation, merge, push, branch
removal, or worktree removal belongs to this verification.

## 5. Human decision register

| Decision | Accountable authority | Earliest trigger | Default before decision |
|---|---|---|---|
| RFC-003..007 G6 amendment versus G7 de-ratification path | System Owner | after 28-row P2 package review | prior Ratified baselines remain governing; P2 discrepancy open |
| CONST-003 governing-home and composite-chain amendment | System Owner + Architecture Board | after Proposed ECO contract review | RLP alone insufficient; CONST-003 completion prohibited |
| Economic Viability Profile values | Investment Authority, with Risk Authority on safety/risk bounds | before any ECO row can become READY | unset/unknown; fail closed |
| Investment mandate/allocation/benchmark owners | System Owner / Investment Authority | before cross-strategy or cross-account capital allocation | no allocation authority inferred from RCL headroom |
| Market-data acquisition/backfill ownership | Architecture Board / data owner | before first affected feed admission | no affected context admitted for new risk |
| Multi-account/multi-broker operating model | Architecture Board + Risk Authority | before second concurrent account/broker | single-account/scope restriction |
| End-to-end latency/economic-survival budget | Architecture Board + Investment/Risk Authorities | before latency-sensitive restricted live | scope prohibited; no gate weakened |
| LLM runtime migration | operator/System Owner after counterfactual review | separate implementation plan | current runtime unchanged; non-conforming dependence remains visible debt |
| Any ADR acceptance, restricted-live, or production action | authorities named by GOV/ADR/VER | only after their complete independent gates | NO |
