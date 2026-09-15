# DR-0003 — Aggregate Risk Policy and Action Flow Policy Instances: Ratification Path and the Single-Source Position Observation

- **Decision ID:** DR-0003
- **Date:** 2026-09-16
- **Status:** Proposed (becomes Accepted on System Owner merge; see §6)
- **Decision Owner:** System Owner (final risk-acceptance authority, vision §12.1)
- **Category:** Governance Decision
- **Originating Finding:** The implementation track's composition root takes
  its Aggregate Risk (ADR-002-021) and Action Flow (ADR-002-022) decision
  inputs as caller-supplied callables with no production source; every
  existing caller is a test fixture hand-building `ProjectedCell` magnitudes,
  an `ActionCause`, an `ActionFlowStateSnapshot` and an
  `ObservedAmplification`. No Aggregate Risk Policy or Action Flow Policy
  instance has ever been issued (the approved Adverse Scenario Set pilots
  record `aggregate_risk_policy_id: null` for that reason), and no document
  says where such instances live, what activates them, or which of their
  declared content the current kernel realizes.
- **Normative Carriers:** ADR-002-021 §§5.1, 5.3, 9, 12, 15, ARE-INV-006;
  ADR-002-022 §§5.1, 5.3, 5.8, 10, 12; ADR-002-014 §§7, 13; ADR-002-018
  (Critical Inputs); ADR-002-006 (conservative knowledge state); DR-0001;
  DR-0002

---

## 1. Context

DR-0002 fixed, for the Venue Constraint Policy and the Order Construction
Policy, the three answers this corpus had left open for every governed policy
instance: placement (a non-normative implementation-track file shaped by the
verification template, kernel content under `_model_view`, runtime-only
facts under `_runtime`), activation (an exact `BundleMemberRef` match in the
ADR-002-014 Activation Record, refused on any mismatch), and coverage (what
the Phase-1 kernel realizes; everything else preserved as data or left null so
the kernel returns `UNKNOWN`). ADR-002-021 §5.1 and ADR-002-022 §5.1 define the
Aggregate Risk Policy and the Action Flow Policy with the same words —
"immutable, authenticated, content-addressed" / "part of the ADR-002-014
Safety Configuration Bundle" — and the spg vocabulary already carries their
bundle-member kinds. The same three answers therefore apply, and this record
extends DR-0002 to them rather than restating it.

Two further questions are specific to these policies and are decided here:

1. **Which state the runtime may observe for the Aggregate Risk State
   Snapshot.** ADR-002-021 §9 lists positions, orders, fills, commitments and
   UNKNOWN outcomes among the snapshot's consistency cut; ARE-INV-006 says
   UNKNOWN state "consumes conservative capacity and blocks new risk". The
   runtime has no broker position query and no position ledger. It does have
   an append-only evidence store carrying every sealed send and every
   consumed egress result.
2. **Which Action Flow facts are observations and which are declarations.**
   ADR-002-022 §5.8 bounds amplification per root cause and §12 distinguishes
   six operational states; some of the facts the kernel's
   `amplification_bounded` / `scope_graph_complete` predicates consume are
   observable from the durable inbox and commit log, and some describe the
   deployment's structure (whether concurrent consumers share one envelope,
   whether the scope's allocation is separated from another's) and cannot be
   observed by the runtime about itself.

## 2. Decision

### 2.1 Placement, activation and coverage — DR-0002 applies

An Aggregate Risk Policy instance and an Action Flow Policy instance follow
DR-0002 §2.1 and §2.2 verbatim: template shape
(`verification/AGGREGATE-RISK-POLICY-template.yaml`,
`ACTION-FLOW-POLICY-template.yaml`), `_model_view` for the kernel record's
covered fields, `_runtime` for runtime-only facts, `status: ISSUED` only,
digest derived by the kernel's own issuance, activation by an exact member
reference of kind `AGGREGATE_RISK_POLICY` / `ACTION_FLOW_POLICY` in the
Activation Record. The bounded realization of ADR-002-014 §13 recorded in
DR-0002 §2.2 is unchanged and is not widened here.

### 2.2 The position observation is a single-source, conservative fill sum

The runtime MAY derive the aggregate state snapshot's directional usage, in
contract units, from its own durable evidence: confirmed fills from consumed
egress results, signed by the sealed outbound side; every attempt that was
sealed but has no terminal result counted in full, in the direction that makes
usage largest (ARE-INV-006 — an UNKNOWN outcome consumes conservative
capacity). This is an observation aggregate, not a risk judgment: it produces
a magnitude the kernel's own `adverse_increment` and `risk_decision` then
evaluate.

Its limits are recorded, not hidden:

- it is **single-source** (the runtime's own evidence; no broker witness
  corroborates it). The snapshot-completeness witness
  (`all_fields_attributed`) therefore remains an operator attestation under
  the existing restrictive-merge mechanism, and the runtime does not set it;
- it is **contract-count only**. No valuation, margin or notional dimension
  can be governed until a mark source exists; a policy that governs such a
  dimension makes every evaluation `UNKNOWN`, which is the correct result;
- a kernel-side position predicate package is the intended home for the fold
  once the runtime realization has run; until then the runtime's pure fold is
  property-tested and its inputs are evidenced per attempt.

### 2.3 Action-flow facts: observed versus declared

The following are **observations** the runtime derives from durable state and
MUST NOT be literals: queue depth (durable inbox), in-flight and per-cause
attempt counts (sealed attempts without terminal results), lineage
(the event → proposal → attempt chain read from the inbox), duplicate
redelivery rejections, recovery replays, elapsed monotonic time since the
root event, the requested flow vector (one broker mutation per command), the
committed flow vectors (unconsumed permits in the commit log), and the number
of broker queries — which is zero because the runtime's transports expose no
query path, a structural fact pinned by a test so that adding a query path
forces this observation to be rebuilt.

The following are **declarations** the deployment makes about itself in the
Action Flow Policy instance, are evidenced at boot as declarations, and are
never observed or defaulted by code: scope-independence evidence (allocation,
refill, broker enforcement, credential/session state, failure domain, final
route, and the two "basis is only a local counter / scheduler priority"
negatives), whether concurrent consumers share one envelope, whether a
duplicate event may create a new allowance, and whether the envelope resets
on a duplicate.

### 2.4 What this decision does not do

It accepts no ADR. It creates no capacity, permit, authority or live scope. It
does not fill any value — the concrete limits, scenario coverage and
deployment declarations are a separate System Owner approval, table by table.
It does not introduce a broker position query; when one exists, the
single-source limit in §2.2 is lifted by a new decision record, not by editing
this one.

## 3. Options Considered

### 3.1 Option (a) — Keep the inputs caller-supplied until a broker position feed exists
Rejected. Every production boot would stay impossible, and the parts that are
observable today (fills, in-flight attempts, queue depth, lineage) would stay
unobserved for no safety gain — a conservative fill sum from durable evidence
is strictly more restrictive than nothing.

### 3.2 Option (b) — Treat the fill sum as corroborated and set the attribution witness from it
Rejected. One source cannot corroborate itself; ADR-002-018 requires source
provenance and independence for a Critical Input, and the existing operator
attestation is the honest interim.

### 3.3 Option (c) — Observe the deployment-structure facts by inspecting the process
Rejected. A process cannot prove there is no second consumer of its envelope;
a declaration in the governed instance, evidenced as such, is honest and
reviewable, while an in-process "observation" would be a literal wearing a
costume.

### 3.4 Option (d) — DR-0002 path + single-source fill sum + observed/declared split (ADOPTED)
Adopted as §2.

## 4. Rationale

The spec's division of roles is unchanged: policy supplies limits and scope,
the runtime supplies conservatively attributed state, the kernel decides.
Making the observable parts observed and the declared parts declared, with
the single-source limit written down, is the smallest change that lets the
kernel's existing `GRANT`/`DENY`/`UNKNOWN` logic act on real state.

## 5. Consequences

- A deployment without the two policy instances named in its Activation
  Record does not boot.
- Any dimension a policy governs that the runtime cannot source evaluates to
  `UNKNOWN`; the evidence row emitted per attempt lists the absent fields.
- Until a broker position witness exists, the snapshot-completeness witness
  remains an operator attestation and is reported as such.

## 6. Normative Status and Future Constitutional Work

A governance decision, not a normative specification. Becomes `Accepted` when
the System Owner merges the change that introduces it. A broker position
witness, a kernel position predicate package, or a valuation source each
supersede the corresponding limit of §2.2 by a new decision record.

## 7. Related Documents

- DR-0002 — Order Construction and Venue Constraint Policy Instance Ratification Path
- ADR-002-021 — Aggregate Risk Projection, Adverse-Scenario Evaluation, and Risk-Decision Integrity
- ADR-002-022 — Action-Flow Budgeting, Retry-Storm Containment, and Protective-Traffic Preservation
- ADR-002-014 — Hard Safety Envelope and Runtime Safety Profile Governance
- ADR-002-018 — Critical Input Integrity, Provenance, and Decision-Context Fencing
- `verification/AGGREGATE-RISK-POLICY-template.yaml`, `verification/ACTION-FLOW-POLICY-template.yaml`
- Implementation-track plan: `docs/plans/2026-09-16-tos-risk-state-service-plan.md`
