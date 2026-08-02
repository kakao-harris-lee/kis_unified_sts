# Futures LLM Determinism Migration Plan

Date: 2026-08-02
Status: non-authorizing implementation plan; runtime changes not started
Scope: futures Setup A/C/D, the monolithic trading orchestrator, and the
provisional TOS DSL / Independent Approval seams

## 1. Decision and honesty boundary

The target is deliberately narrow:

- an LLM may contribute recorded soft context, rationale, or a **restrictive
  entry veto**;
- deterministic, versioned, independently recomputable inputs and rules decide
  direction, quantity basis, price constraints, exposure, and thresholds;
- changing a field name from `llm_*` to `risk_*`, copying an LLM category into a
  numeric score, or storing the response does not make it independently
  recomputable;
- this plan changes no strategy, YAML, broker path, order quantity, threshold,
  or live gate. Any economic change requires the operator gate in §7.

This is a current-to-target migration plan, not ADR acceptance or evidence. The
TOS engine is still explicitly provisional and uses non-authoritative approval
and RCL stand-ins (`tos/src/tos/engine/__init__.py:24-41`).

## 2. Governing conflict

The project roadmap currently says that the LLM interprets `veto / risk-mode /
size / threshold` (`docs/ROADMAP.md:347-351`). RFC-003 instead classifies every
value that changes direction, instrument, quantity, price, exposure, risk,
margin, venue eligibility, authorization, or execution behavior as a Critical
Input (`tos-spec/src/part-2-decision/RFC-003-Decision-Framework.md:228-249`). A
stochastic or external value that determines direction, quantity, price, or
exposure is non-approvable when an independent service cannot rederive it; it
may be only non-determining soft evidence, and relabeling does not change that
classification (`RFC-003:365-381`).

The roadmap statement is therefore replaced by a current/target distinction,
not treated as authority to weaken RFC-003.

## 3. Reverified current path

### 3.1 Current runtime

The active project-side path remains the monolithic `trader-futures`
orchestrator; the decoupled chain is described as dormant in
`docs/ROADMAP.md:353-361`. This audit read code and configuration only. It did
not start a service, contact KIS, inspect secrets, or exercise a broker path.

The LLM publisher converts a stochastic `MarketAnalysis` into:

- `regime`, derived from `overall_signal`;
- `risk_score`, a fixed numeric mapping of the LLM-owned `risk_mode`;
- `confidence`, computed from LLM output presence, signal strength, and source
  presence.

These transformations are visible in
`services/trading/llm_context_publisher.py:220-350`. They are deterministic
*given the LLM response*, but the originating economic classification remains
external/stochastic. The transformation is therefore lineage, not independent
recomputation.

### 3.2 Entry direction and threshold seams

`shared/strategy/entry/setup_llm_gate.py:87-193` uses LLM `regime`,
`risk_mode`, and `risk_score` to:

- block Setup A/C long or short signals;
- scale Setup A confidence and potentially drop it below a threshold;
- boost Setup C confidence under an LLM-derived regime and risk mode.

The Setup A/C adapters apply those results before emitting a signal and then
apply the separate veto (`setup_a_adapter.py:221-274`,
`setup_c_adapter.py:252-304`). Direction blocking and confidence/threshold
tuning therefore determine whether an action exists and are Critical Input
uses, even when their outcome is restrictive.

The dedicated veto in `setup_llm_gate.py:196-269` is entry-only and can only
turn an otherwise emitted long/short entry into no action. This is the closest
current seam to the target, but its invariants are not yet structurally sealed
against later use for quantity, direction reversal, price changes, or exit/stop
suppression.

### 3.3 Quantity seam: configured capability versus active call

Setup A and C select `type: llm_adaptive` and configure risk-score tiers in
`config/strategies/futures/setup_a_gap_reversion.yaml` and
`setup_c_event_reaction.yaml`. The sizer can use LLM `risk_score`, confidence,
and risk mode to scale a base quantity or return zero
(`shared/strategy/position/llm_adaptive_sizer.py:280-364,415-470`). This is a
quantity/exposure-determining capability and is non-conformant as a target TOS
Critical Input path.

The reverified monolithic order-quantity call currently invokes
`strategy.calculate_position_size(...)` without the optional `market_context`
(`services/trading/orchestrator.py:6670-6705`). The base strategy consequently
passes `None` to the sizer on that call, and the tier mode returns its configured
base quantity (`llm_adaptive_sizer.py:310-317`). This means the configured LLM
sizing capability is not shown to be load-bearing on this exact current call
path. It does **not** make the seam acceptable: another caller or later wiring
can activate it, and the current comments/roadmap claim that behavior as a
supported operating mechanism.

### 3.4 TOS target seams

- A DSL `Proposal` carries direction and an abstract `quantity_basis`, explicitly
  as evidence rather than capacity (`tos/src/tos/dsl/proposal.py:45-110`).
- `evaluate_resolved` consumes values admitted through the Critical Input view
  and binds that view's digest to the recorded input signature
  (`tos/src/tos/dsl/determinism.py:371-405`).
- Order construction derives quantity and price from an admitted Critical Input
  observation and injected bounds; an author cannot supply the final quantity
  (`tos/src/tos/egressgw/construction.py:1-27,223-385`).
- `tos.iap` is an automated independent-approval decision kernel, not human
  approval, signing, egress, or an owning production service
  (`tos/src/tos/iap/__init__.py:1-29`).

These are suitable target contracts, but the provisional engine cannot yet
prove that the project-side LLM-free deterministic inputs were independently
recomputed or approved in a real authority service.

## 4. Current-to-target mapping

| Seam | Current effect | RFC-003 classification | Target | Migration evidence |
|---|---|---|---|---|
| LLM regime direction lists | suppresses selected long/short entries | action/direction determining | deterministic admitted market-state rule decides eligibility; LLM may veto the already deterministic proposal only | paired-context invariance and long/short symmetry |
| LLM risk score/mode threshold tuning | changes confidence and whether a signal crosses admission | threshold/action determining | versioned deterministic threshold profile over captured recomputable inputs | threshold provenance, replay digest, boundary tests |
| Setup C confidence boost | can loosen admission | authority/economic-effect increasing | remove LLM boost; only deterministic profile may loosen/tighten | prove LLM cannot increase admissibility |
| `llm_adaptive` sizing | implementation can alter or zero quantity | quantity/exposure determining | deterministic quantity-basis and construction bound; LLM never scales quantity | paired-context quantity invariance and construction replay |
| LLM entry veto | converts a deterministic entry to no action | restrictive, but still recorded external context | isolated `restrictive_veto` result that cannot mutate proposal fields, exits, stops, or approval | monotonicity/property tests and veto audit lineage |
| LLM context/rationale | observational metadata | soft evidence only if non-determining | digest-bound rationale/context, excluded from decision operands | dependency/taint and counterfactual tests |
| DSL resolved value view | captured Critical Input operand | target deterministic decision seam | only registered recomputable producers may populate determining operands | source/provenance admission and replay |
| IAP/engine stand-ins | provisional decision/wiring | not real authority | independent service rederives determining facts before exact approval | independent-service evidence; stand-in rejection canary |

Relabeling is tested by dependency, not by key name: if perturbing an LLM-origin
value changes direction, quantity basis, quantity, price constraint, exposure,
threshold result, venue, or execution behavior, it is a determining Critical
Input and cannot enter the approvable target path.

## 5. Scoped implementation sequence

Each phase is a separate change and stops before the next operator gate.

1. **Inventory and shadow record.** Add a typed decision-dependency record that
   labels source provenance and economic axes affected. Record current
   deterministic outcome, LLM tuning outcome, and veto outcome without changing
   the emitted signal. No broker or live evidence.
2. **Seal a restrictive veto interface.** Its input is an already complete
   deterministic entry proposal; output is exactly `ALLOW_UNCHANGED` or
   `VETO_TO_NO_ACTION`. It cannot carry replacement direction, quantity, price,
   confidence, threshold, exit, or stop fields. Unknown/stale/unavailable input
   must follow an owner-approved restrictive policy and cannot expand authority.
3. **Replace quantity dependence.** Introduce a deterministic, versioned sizing
   profile whose inputs are present in the captured snapshot and independently
   recomputable. Run shadow comparison first. Do not change active economics
   until §7 accepts the quantity/capacity delta.
4. **Replace direction and threshold dependence.** Move regime eligibility and
   threshold decisions to deterministic admitted inputs and rules. Remove LLM
   confidence boosts and LLM-derived threshold operands. Retain only the sealed
   veto and non-determining rationale.
5. **Bind TOS provenance.** Map every determining value to the DSL resolved
   Critical Input view, exact recorded signature, order-construction bound, and
   independent recomputation request. Values with an unregistered producer or
   failed recomputation produce no approvable action.
6. **Fence and deprecate old seams.** Reject `llm_adaptive` for an approvable TOS
   strategy, reject LLM-origin fields in determining operands, remove dormant
   wiring only after rollback evidence, and update the migration/conformance
   register. Project paper behavior remains distinct from TOS authority.

No phase may silently replace a current entry rule, base quantity, threshold, or
strategy economics under the label of documentation cleanup.

## 6. Test and evidence contract

Focused implementation tests must include:

- paired runs with identical deterministic inputs and adversarially different
  LLM contexts yield byte-identical direction, quantity basis, quantity, price
  constraints, exposure, threshold result, and execution constraints;
- the only permitted difference is `ALLOW_UNCHANGED` versus
  `VETO_TO_NO_ACTION` after a deterministic proposal exists;
- an LLM cannot flip direction, increase or scalar-reduce quantity, loosen a
  threshold, change a price/venue, suppress exits/stops, or revive a denied
  proposal;
- key relabeling and derived-score mapping do not evade source classification;
- missing, stale, malformed, conflicting, or replayed LLM context never widens
  authority;
- long/short futures behavior remains symmetric;
- the deterministic result and its captured input digest replay exactly;
- configuration migration tests preserve the pre-approved deterministic base
  behavior before any economics gate;
- shadow/counterfactual reports include signal count, veto count, direction,
  quantity, turnover, cost, drawdown, and capacity deltas, but are not evidence
  `PASS` by themselves.

The future independent approval service must recompute every determining fact.
A test double, stored LLM response, cache hit, dashboard state, or healthy
process is not that proof.

## 7. Operator and human decision gates

Before an active runtime change, the System Owner and strategy/economic owner
must receive a versioned delta package containing:

- old/new signal and quantity counterfactuals by setup, side, and regime;
- total-cost, turnover, capacity, drawdown, and restricted-live implications;
- missing-data and stale-data behavior;
- an exact configuration diff, activation scope, observation window, stop rule,
  rollback trigger, and rollback command;
- confirmation that exits/stops and live/paper authorization did not change.

The Architecture Board must accept the source-classification and independent
recomputation design. Risk Authority must accept safety-bound interactions.
Investment Authority must accept any economic delta. An independent reviewer
must review governed evidence. Until those acts occur, the current path remains
a documented conformance gap and no RFC amendment, evidence `PASS`, restricted
live readiness, or production authority is claimed.

## 8. Rollback and completion

Each runtime phase must be independently reversible to the last accepted
deterministic configuration, with queued proposal invalidation and proof that
rollback cannot double trade. Rollback must not re-enable a non-conformant LLM
determining seam as an approved TOS path; if the deterministic replacement is
unsafe, the safe rollback is no new entry for that scope while existing
protective exits remain available.

This finding is documentation-closed only when the roadmap, this map, and the
migration register agree. Runtime conformance remains open until all phases,
human gates, and governed evidence are complete.
