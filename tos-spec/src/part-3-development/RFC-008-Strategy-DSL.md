# RFC-008 — Strategy DSL

**Document ID:** RFC-008
**Title:** Strategy DSL
**Version:** 0.2
**Status:** Ratified (2026-07-18 — GOV-001 G5 record RR-0010, ARCHITECTURE-GATE-STATUS §9.7; ratification confers no live authorization, no ADR acceptance, and no capacity)
**Classification:** Implementation-Layer Specification
**Authority:** Governed by RFC-000 — Trading Constitution
**Safety Authority:** Constrained by RFC-001 — Safety Case and RFC-002 — Architecture
**Decision Authority:** Constrained by RFC-003 — Decision Framework
**Owner:** Trading Operating System Architecture Board
**Created:** 2026-07-15
**Last Updated:** 2026-07-17

---

## 1. Abstract

This document defines the **Strategy DSL**: the authoring surface through which a
strategy expresses a trading view and produces a **Proposal**. Per RFC-000 §9 the
Constitution defines WHY, the Safety Case defines WHAT SHALL NEVER HAPPEN, the
Architecture RFCs define WHAT EXISTS, the Decision Framework defines HOW DECISIONS
ARE MADE, and Implementation defines HOW SOFTWARE IS BUILT. RFC-008 occupies the
Implementation layer: it is the concrete authoring language for the **Decision
Policy** that RFC-003 §5 defines abstractly, and it exists to make the untrusted
proposer of RFC-002 §7.3 and philosophy §13 buildable in practice.

RFC-008 is subordinate to RFC-000, RFC-001, RFC-002, every accepted ADR-002-xxx,
and RFC-003, and it consumes the models specified in RFC-004 through RFC-007. Its
governing thesis is **containment by construction**: the language a strategy
author writes in SHALL make the sixteen decision↔safety prohibitions of RFC-003
§11 *unexpressible*, rather than expressible-but-forbidden. A strategy author
cannot approve, size beyond capacity, commit capacity, transmit, arm live, or
classify an action as protective — not because a rule says not to, but because the
DSL provides no term, handle, or escape through which any of those effects can be
named.

RFC-008 defines an authoring surface and its guarantees. It selects no signal,
model, indicator, or strategy; it grants no authority; and its acceptance does not
authorize live operation.

---

## 2. Normative Authority

RFC-008's authority is bounded as follows:

* **RFC-000 — Trading Constitution** governs this document. RFC-008 SHALL NOT
  redefine constitutional intent (RFC-000 §9) and SHALL use RFC-000 §6
  vocabulary verbatim.
* **RFC-001 — Safety Case** constrains this document. No language construct,
  runtime, or authoring convenience defined here may weaken, bypass, or
  reinterpret any SAFE-xxx requirement, and every DSL input remains Critical Input
  governed by ADR-002-018.
* **RFC-002 — Architecture** and the accepted **ADR-002-xxx** series define the
  components and contracts a Proposal flows into. RFC-008 targets the Decision
  Service contract (RFC-002 §10.2) and the strategy boundary (RFC-002 §7.3, §9.1);
  it defines none of the downstream owners.
* **RFC-003 — Decision Framework** is the layer RFC-008 implements. RFC-008 is a
  conforming realization of RFC-003's decision pipeline (§7), Proposal output
  (§9), determinism and reproducibility discipline (§10), and decision↔safety
  boundary (§11); it inherits every RFC-003 obligation and adds no authority.
* Where RFC-008 and any higher document appear to conflict, the higher document
  governs and the conflict SHALL be raised through governance, not resolved by
  local reinterpretation or by a language feature.

RFC-008 defines an implementation surface. It creates no capacity, authority,
configuration, transmission permission, or protective status, and its acceptance
does not authorize live operation.

---

## 3. Scope and Non-Scope

This document governs:

* the strategy authoring surface: what a Decision Policy may express and how;
* the containment-by-construction guarantee — which effects the language makes
  unexpressible, and why;
* the Proposal a strategy emits, as a conforming instance of the RFC-003 §9
  output contract;
* the determinism, reproducibility, versioning, and isolation properties an
  authored strategy SHALL exhibit;
* how a strategy consumes Decision Context and the RFC-004–007 models without
  self-certifying or relabeling them;
* the boundary between the authoring surface and every safety-enforcement and
  decision-authority owner.

This document does not decide:

* the decision process discipline itself — RFC-003 owns that; RFC-008 realizes it;
* whether a Proposal is approved — the Independent Approval Service owns that
  (RFC-002 §10.3, ADR-002-023);
* risk-capacity allocation or mutation — the Risk Capacity Ledger owns that
  (ADR-002-002);
* order construction, transmission, or currentness — ADR-002-020/024 and the
  Broker Egress Gateway own those;
* the market model (RFC-004), execution model (RFC-005), risk model (RFC-006), or
  hedge model (RFC-007) — RFC-008 consumes their outputs, it does not define them;
* any specific signal, indicator, statistical model, or strategy expressed *in*
  the DSL;
* numeric thresholds, limits, symbols, schedules, or feature gates, which are
  approved configuration and the Verification Profile.

An authoring surface that lets a strategy reach beyond this scope — or that offers
any escape from it — is non-conforming regardless of its expressive convenience.

---

## 4. Relationship to Vision and Philosophy

RFC-008 operationalizes principles already established upstream; it inherits, and
does not restate, them.

* **Strategies are replaceable; safety is durable** (philosophy §13, Vision §7.5).
  The DSL is the mechanism that makes this true in code: a strategy may express
  intent, expected edge, desired quantity, preferred timing, and execution
  constraints, and SHALL NOT be able to express live authority, final approval,
  aggregate risk capacity, safety limits, protective classification, broker
  transmission, or emergency containment (philosophy §13).
* **Prediction has limited authority** (philosophy §7). A signal, score, or model
  output authored in the DSL is uncertain evidence, never permission; the language
  SHALL NOT let signal strength become a bypass.
* **Uncertainty reduces authority** (philosophy §8, RFC-003 §6). Under Critical
  Uncertainty an authored strategy's only conforming outcomes are a more
  conservative action or no action; the DSL SHALL NOT provide a construct that
  widens the action set as confidence rises.
* **No trade is a valid decision** (philosophy §6, RFC-003 §6). Declining to act
  SHALL be a first-class, directly expressible outcome, as reproducible and
  auditable as an action.
* **Authority must be explicit** (philosophy §14). The DSL SHALL NOT let a strategy
  infer authority from deployment, credentials, a prior success, reachability of a
  broker endpoint, or a `live=true` flag; expressing an order request is not
  authority.

Where a language construct would contradict a Vision or Philosophy principle, that
construct is non-conforming.

---

## 5. Definitions

RFC-008 reuses canonical terms from RFC-000 §6, RFC-001 §5, RFC-002 §3.1, the
ADR series, and the framework-local terms of RFC-003 §5 (**Proposal**, **Decision
Policy**). It SHALL NOT introduce synonyms for any of them. The following terms
are scoped to the authoring surface and are non-authorizing.

* **Strategy DSL** — the constrained authoring surface (a language, embedded
  API, or equivalently restricted interface) in which a Decision Policy is
  written. The DSL is a means of expression, not a component of authority.
* **Strategy Author** — the human or tool that writes a Decision Policy in the
  DSL. A Strategy Author holds no runtime authority; authored artifacts are
  untrusted proposals (RFC-002 §7.3).
* **Authored Strategy** — a versioned Decision Policy expressed in the DSL,
  together with its declared configuration bindings. An Authored Strategy is a
  candidate proposer, never an authorization.
* **Proposal Builder** — the DSL-provided, effect-free means by which an Authored
  Strategy assembles a Proposal (RFC-003 §9). The Proposal Builder can construct
  only a candidate; it exposes no approval, capacity, transmission, or protective
  handle.
* **Expressible Effect** — an effect the DSL provides a term for. RFC-008's thesis
  is that the set of Expressible Effects excludes every prohibition in RFC-003
  §11.

These terms describe an authoring surface. None grants authority, allocates
capacity, or produces an Intent.

---

## 6. Strategy DSL Principles

A conforming Strategy DSL SHALL satisfy the following. They are properties of the
authoring surface and its runtime, not new enforcement mechanisms; the enforcement
points remain owned by RFC-002 and the ADR series.

1. **Containment by construction.** The DSL SHALL make every RFC-003 §11
   prohibition unexpressible: it SHALL provide no term, argument, handle, escape,
   or extension point through which a strategy could approve, transmit, commit or
   mutate capacity, size beyond capacity, arm live, alter safety configuration,
   classify its action as protective, or self-certify context.
2. **Proposer only.** The sole output an Authored Strategy can produce is a
   Proposal or an explicit no-action (RFC-003 §7). The DSL exposes no other exit.
3. **Context in, through the Capsule only.** A strategy SHALL read Decision
   Context only as delivered by the Decision Context Capsule (ADR-002-018,
   RFC-003 §8); the DSL SHALL provide no ambient fetch, cache, clock, network,
   filesystem, or side channel.
4. **Determinism of process.** Given identical Decision Context, Authored Strategy
   version, and configuration version, evaluation SHALL yield an identical outcome
   and rationale (RFC-003 §10). Nondeterminism is a declared, seeded exception
   (§9).
5. **No-action is first-class.** Declining to act SHALL be a direct, ordinary
   expression, not an error, a null, or an omission.
6. **Uncertainty is restrictive.** The DSL SHALL make conservative-or-no-action
   the natural expression under degraded context, and SHALL provide no construct
   whose effect is to widen the action set as a signal strengthens.
7. **Isolation of failure.** A strategy that errors, diverges, exhausts a
   resource, or is removed SHALL degrade to no-action for its own scope and SHALL
   NOT affect any other strategy's outcome or any safety control (RFC-003 §13).
8. **Everything is versioned.** An Authored Strategy, its DSL version, and its
   configuration bindings SHALL be versioned and recorded in decision evidence; a
   change is a versioned substitution, never an in-place unversioned mutation
   (RFC-003 §13).

---

## 7. The Authoring Surface

The Strategy DSL is deliberately *less* than a general-purpose language. Its
expressive power is bounded by what a proposer legitimately needs, and no more.

**What a strategy MAY express** (philosophy §13):

* a view derived from admitted Decision Context and the RFC-004–007 models;
* an intended trading action — account, instrument, direction, position effect;
* a desired quantity basis and an expected edge or confidence, as evidence;
* preferred timing and execution constraints, as *requests* to the execution
  layer (RFC-005), not as commands;
* an explicit no-action outcome;
* a rationale sufficient to reconstruct why the outcome followed from the context
  (RFC-003 §§6, 9).

**What the DSL SHALL NOT provide any means to express** — the containment set,
drawn from the RFC-003 §11 prohibitions (§11 below restates them in full):

* approval of its own or any proposal;
* transmission, a broker route, or reaching an egress path;
* reservation, commitment, mutation, or release of risk capacity, or any write to
  the Risk Capacity Ledger;
* alteration, relaxation, or reinterpretation of a safety limit or safety
  configuration;
* arming live mode, or issuing Live Authorization or a Transmission Capability;
* classification of its own action as protective — no `hedge`, `exit`, `stop`,
  `protective`, or `emergency` keyword confers protective status (RFC-002 §9.1:
  "Strategy SHALL NOT self-label an action as protective");
* disabling, bypassing, or degrading the Safety Authority or any containment
  mechanism;
* self-certification of context freshness, completeness, or validity, or evasion
  of Critical Input governance by renaming data;
* a wildcard or "latest policy" account, instrument, side, quantity, or unit
  reference (ADR-002-020 §8).

The surface is intentionally closed. If an author needs an effect that the DSL
cannot express, that need is raised through governance and the model/architecture
layer — never satisfied by a language escape, a foreign-function interface, or an
unconstrained embedded host.

---

## 8. The Proposal as the Only Output

An Authored Strategy's only output is a **Proposal**, exactly as defined by
RFC-003 §9 and populating the Approved Intent Contract field set of ADR-002-020
§8. RFC-008 adds no field and relaxes no requirement; it constrains only *how* the
Proposal is assembled.

* **Assembled through the Proposal Builder.** A Proposal SHALL be constructed only
  via the effect-free Proposal Builder (§5). Assembling a Proposal has no side
  effect: it does not reserve capacity, notify Approval, or reach any owner.
* **Complete and immutable.** A Proposal SHALL be complete and immutable at
  emission and SHALL bind the exact Decision Context Capsule identity and digest it
  consumed (RFC-003 §§7, 9).
* **No wildcard, no "latest."** The Proposal Builder SHALL reject wildcard or
  "latest policy" account, instrument, side, quantity, or unit references; such a
  construction is non-conforming for live use (ADR-002-020 §8, RFC-003 §9).
* **Rationale and versions attached.** A Proposal SHALL carry its decision
  rationale, the Authored Strategy version, the DSL version, and the configuration
  version (RFC-003 §§9, 10).
* **Emission is the end.** Emitting a Proposal hands it to the separately owned
  Approval stage; the DSL SHALL provide no means for the strategy to observe,
  await, assume, or act upon that stage's outcome as permission (RFC-003 §7).

A Proposal is a candidate. Its well-formedness is necessary for downstream
consideration and is never sufficient for authorization; the decision layer owns
none of the transitions that would make it an Intent (RFC-003 §9, ADR-002-023).

---

## 9. Determinism, Reproducibility, and Isolation

RFC-008 realizes RFC-003 §10 at the language level: the authoring surface and its
runtime SHALL make a conforming strategy reproducible by default and hard to make
nondeterministic by accident.

* **Pure evaluation.** Evaluating an Authored Strategy over a fixed Decision
  Context and fixed configuration SHALL be a pure function of those inputs. The
  DSL SHALL NOT expose an ambient clock, wall-time, randomness source, mutable
  global, network, or filesystem; the trustworthy-time evidence a strategy may
  read is the value delivered inside the Capsule (ADR-002-008, ADR-002-018), not a
  live clock.
* **Declared, seeded nondeterminism — captured before evaluation, never called
  during it.** Where a strategy legitimately uses a stochastic or
  externally-sourced component (for example a Monte Carlo estimate or an
  LLM-derived interpretation), that value SHALL be produced *outside and before*
  DSL evaluation and delivered into the Decision Context Capsule as Critical Input
  (§10; ADR-002-018), together with its seed and recorded response as decision
  evidence, so that re-execution reconstructs the same outcome (RFC-003 §10;
  ADR-002-018 §10). DSL evaluation itself performs no live call: it reads the
  captured value from the Capsule and never reaches a network, model endpoint, or
  other ambient source, preserving §6 principle 3 and the §11 item 12 ambient-state
  prohibition. An undeclared nondeterministic source, or one obtained by a live
  call during evaluation, is non-conforming.
* **Recorded provenance.** Evaluation SHALL record the exact Capsule
  identity/digest, the Authored Strategy version, the DSL version, and the
  configuration version it used, as inputs to the evidence and replay integrity
  owned by ADR-002-016 (RFC-003 §10). RFC-008 supplies conforming inputs to that
  integrity; it does not replace it.
* **Bounded evaluation.** A strategy evaluation SHALL be bounded in time and
  resources; exhausting a bound SHALL degrade to no-action for that strategy's
  scope, never to an unbounded stall or a partial, unrecorded action (RFC-003
  §13; philosophy §13).
* **Isolation between strategies.** Multiple Authored Strategies SHALL NOT share
  mutable state, aggregate their Proposals into a combined authority, or bypass
  per-Proposal approval and capacity evaluation; one strategy's failure SHALL NOT
  widen another's authority (RFC-003 §13).

Reproducibility and isolation are properties the DSL enforces structurally, not
conventions an author is asked to observe.

---

## 10. Consuming the Decision and Model Layers

An Authored Strategy reasons over Decision Context (RFC-003 §8) and the companion
models (RFC-004–007). RFC-008 fixes how it may consume them without acquiring
authority or evading governance.

* **Critical Input, always.** Any market datum, feature, signal, or reference the
  DSL exposes to a strategy is Critical Input governed by ADR-002-018 regardless of
  what the DSL calls it. The DSL SHALL NOT let a strategy relabel a value as a
  "feature," "signal," or "override" to escape that governance (ADR-002-018 §1,
  RFC-003 §8).
* **Market model (RFC-004).** A strategy consumes market state, microstructure,
  volatility, and regime as evidence; it SHALL NOT assert tradability, which
  remains owned by ADR-002-019, and SHALL NOT infer source continuity from its own
  health (ADR-002-018 §9).
* **Execution model (RFC-005).** A strategy may express execution *constraints*
  and *preferences*; it SHALL NOT construct a canonical broker command, choose a
  route, or assume an execution trajectory is achievable (ADR-002-020, RFC-005).
* **Risk model (RFC-006).** A strategy may compute and express a risk estimate and
  a desired size as evidence; the estimate SHALL NOT be treated as authoritative
  capacity, and the DSL SHALL NOT let a strategy size beyond, or in place of, the
  Aggregate Risk Decision or the RCL commitment (RFC-006 §§9, 13; ADR-002-002).
* **Hedge model (RFC-007).** A strategy may propose a hedge action; the DSL SHALL
  NOT let it label that action protective. Protective classification is owned
  exclusively by the Protective Action Controller under ADR-002-001 §6 (RFC-007
  §§3, 10, 12).
* **UNKNOWN is restrictive.** Missing, stale, conflicting, ambiguous, or
  unverifiable context or model output SHALL be expressible only restrictively;
  the DSL SHALL NOT provide a permissive default that treats absence as
  permission (ADR-002-018 CII-INV-005; RFC-006 §6).

The strategy is a consumer of context and models, never a definer of, or authority
over, them.

---

## 11. The DSL↔Safety Boundary

This section is the load-bearing safety content of RFC-008. It restates, at the
authoring-surface layer, the separation that RFC-002 §9.1 and §7.3, the ADR
series, and RFC-003 §11 enforce, and expresses it as the containment guarantee: an
effect that is prohibited is also **unexpressible**.

The Strategy DSL, its runtime, and any Authored Strategy within it SHALL NOT
provide or possess any means to:

1. approve its own Proposal or any proposal (RFC-000 CONST-005; RFC-002 §9.1,
   §10.2; RFC-003 §11.1);
2. transmit orders or reach a broker route (RFC-002 §7.3, §10.2; RFC-003 §11.2);
3. reserve, commit, mutate, or release risk capacity, or write to the Risk
   Capacity Ledger (RFC-002 §9.1, §10.2; ADR-002-002; RFC-003 §11.3);
4. alter, relax, or reinterpret safety limits or safety configuration (RFC-002
   §7.4; RFC-001 §7.5; RFC-003 §11.4);
5. arm live mode or issue Live Authorization or a Transmission Capability
   (RFC-002 §7.3, §7.6; ADR-002-007; RFC-003 §11.5);
6. classify its own action as protective — no keyword, field, or label confers
   protective status (RFC-002 §9.1 "Strategy SHALL NOT self-label an action as
   protective"; ADR-002-001 §6; RFC-003 §11.6);
7. disable, bypass, or degrade the Safety Authority or any containment mechanism
   (RFC-000 CONST-011; RFC-001 §7.6; RFC-003 §11.7);
8. treat a strong signal or favorable prediction as grounds to bypass any risk,
   execution, account, venue, live-authorization, or aggregate control
   (philosophy §7; RFC-003 §11.8);
9. size an action beyond capacity on the assumption that its own risk computation
   is authoritative (ADR-002-021, ADR-002-002; RFC-003 §11.9);
10. self-certify context freshness or validity, or evade Critical Input governance
    by renaming data (ADR-002-018 §1; RFC-003 §§8, 11.10);
11. observe, await, or act upon an Approval, capacity, venue, or currentness
    result as permission, or substitute its own derived facts for the Approval
    Service's independent recomputation (RFC-001 SAFE-034; ADR-002-018 §13,
    ADR-002-023; RFC-003 §11.11, §11.12);
12. read ambient state — clock, randomness, network, filesystem, or mutable global
    — outside the Decision Context Capsule (ADR-002-018; RFC-003 §§8, 10);
13. use a wildcard or "latest policy" scope in any construction it produces
    (ADR-002-020 §8; RFC-003 §11.13);
14. infer context, market-state validity, or source continuity from its own
    component health, uptime, or last-known-good state (ADR-002-018 §9; philosophy
    §16; RFC-003 §11.14);
15. bypass, remove, or reorder any stage of the RFC-000 §10 pipeline (RFC-003
    §11.15);
16. express a locally-compliant decision in a way that presumes to excuse an
    unsafe aggregate portfolio state; local compliance is never aggregate
    permission (RFC-000 §5; RFC-001 §7.4; philosophy §18; RFC-003 §11.16);
17. escape the authoring surface through a foreign-function interface, unconstrained
    embedded host, dynamic code loading, or extension point that would reintroduce
    any effect prohibited by items 1–16.

This list restates every one of the sixteen RFC-003 §11 prohibitions at the
authoring surface — with §11.11 and §11.12 combined in item 11 and one
DSL-specific prohibition (item 12, ambient state) added — and closes with item 17,
the DSL-specific escape property. No RFC-003 §11 prohibition is dropped. The single
generalizing rule (RFC-002 §9.1; RFC-003 §11): the identity that proposes an action
SHALL NOT also approve it, commit capacity for it, or transmit it. RFC-008 realizes
that rule by ensuring the proposer's *language* can name only the proposing role. A
containment surface with an escape hatch is not a containment surface.

---

## 12. Relationship to RFC-003 through RFC-007 and to RFC-009–011

RFC-008 is the authoring surface that realizes the decision layer and consumes its
models. The pointers below are non-normative scope markers; RFC-008 SHALL NOT
define their content.

* **RFC-003 — Decision Framework.** RFC-008 is a conforming realization of
  RFC-003's pipeline, Proposal output, determinism discipline, and §11 boundary;
  it adds no authority and relaxes no obligation.
* **RFC-004 — Market Model.** The market state, microstructure, volatility, and
  regime a strategy reads as evidence; tradability remains owned by ADR-002-019
  (§10).
* **RFC-005 — Execution Model.** How an approved Intent executes; a strategy
  expresses execution constraints as requests, never commands, and constructs no
  canonical command (§10).
* **RFC-006 — Risk Model.** The risk methodology a strategy uses to estimate risk
  and desired size; the estimate is evidence, never capacity (§10).
* **RFC-007 — Portfolio Hedge Model.** How equity exposure is hedged with index
  futures; a strategy may propose a hedge but SHALL NOT classify it protective
  (§10).
* **RFC-009 — Agent Guide, RFC-010 — Testing Strategy, RFC-011 — Operational
  Guidelines.** Companion Implementation-layer documents. RFC-009 governs how
  agents author within this DSL; RFC-010 governs how an Authored Strategy is
  tested (including that its determinism, isolation, and containment properties are
  verified); RFC-011 governs its operation. RFC-008 defines the surface; those
  documents define working within it and SHALL NOT be pre-empted here.

Until each companion RFC is authored and accepted, its concerns remain open and
SHALL NOT be resolved by authoring-surface convention.

---

## 13. Requirements Traceability

RFC-008 discharges implementation-layer obligations that RFC-000, RFC-002, and
RFC-003 assign to the strategy authoring surface. This table is an initial
allocation and SHALL be refined as RFC-009 through RFC-011 are accepted.

| Requirement | Discharge in RFC-008 |
|---|---|
| RFC-000 §9 layering (Implementation defines HOW SOFTWARE IS BUILT) | RFC-008 confined to the authoring surface for a Decision Policy; defines no WHY/WHAT/HOW-DECISIONS content (§§1, 2) |
| RFC-000 CONST-005 (no self-authorization) | approval is unexpressible in the DSL (§§7, 11.1) |
| RFC-000 CONST-011 (safety independence) | safety-control disablement/bypass unexpressible (§11.7) |
| RFC-002 §7.3 Strategy Boundary; §9.1 authority ownership | the language can name only the proposing role; every strategy prohibition is unexpressible (§§7, 11) |
| RFC-002 §10.2 Decision Service contract | RFC-008 emits exactly the Proposal that contract requires, via an effect-free builder (§8) |
| RFC-003 §7 decision pipeline | strategy produces a single Proposal or no-action and ends at emission (§§7, 8) |
| RFC-003 §9 Proposal output | Proposal Builder populates the ADR-002-020 §8 field set with no wildcard/"latest" (§8) |
| RFC-003 §10 determinism/reproducibility | pure evaluation, declared seeds, recorded provenance, bounded evaluation (§9) |
| RFC-003 §11 decision↔safety boundary | all sixteen prohibitions restated as unexpressible effects, plus a DSL-specific ambient-state item and the escape-closure property (§11) |
| RFC-003 §13 strategy replaceability | uniform proposer contract, failure isolation, versioned substitution (§§6, 9) |
| RFC-001 SAFE-030, SAFE-031, SAFE-034 | DSL inputs remain Critical Input; no self-certification; no substitute for independent recomputation (§§10, 11.10, 11.11) |
| ADR-002-018 (Critical Input, §1 relabeling, §9 health, §10 lineage) | no relabeling escape, no ambient fetch, declared lineage for derived inputs (§§9, 10, 11.10, 11.12, 11.14) |
| ADR-002-020 §8 (canonical construction, no wildcard) | Proposal Builder rejects wildcard/"latest"; no command construction in the DSL (§§8, 10) |
| ADR-002-001 §6 (protective classification) | protective status is unexpressible; owned by the Protective Action Controller (§§7, 10, 11.6) |
| philosophy §§6, 7, 8, 13, 14, 16, 18 | operationalized as authoring-surface principles and the containment set (§§4, 6, 7, 11) |

RFC-008 introduces no SAFE-xxx requirement and no numeric bound. It relies
entirely on the enforcement points already defined upstream; its own contribution
is to make the prohibited effects unexpressible at the authoring surface.

---

## 14. Open Questions

These questions are open while RFC-008 is a Review Draft. Each is addressed by a proposed
ADR-DEV as noted; because every such ADR-DEV is `Proposed` (unaccepted), a proposed ADR-DEV
does not resolve its question — resolution follows acceptance. None SHALL be resolved by
informal authoring-surface convention.

1. Is the DSL a standalone constrained language, a sandboxed embedding in a host
   language, or a restricted API surface — and which realization most credibly
   guarantees §11 item 17 (no escape) for the agents authoring under RFC-009?
   *(Addressed by proposed ADR-DEV-001; pending acceptance: a default-deny, capability-restricted authoring
   surface; any family is permitted only if escape-closure holds.)*
2. What is the exact mechanism by which the runtime *enforces* purity and the
   absence of ambient state (§9) — a capability-restricted interpreter, static
   rejection of prohibited references, a sandbox, or a combination — and how is
   that mechanism itself verified (RFC-010)? *(Addressed by proposed ADR-DEV-001; pending acceptance: three-layer
   non-self-trusting enforcement — static admissibility analysis, capability-
   restricted evaluation, isolation boundary — with the mechanism itself
   adversarially verified per RFC-010 §8.)*
3. Beyond the pre-evaluation capture §9 now requires, what evidence and staleness
   discipline governs an externally-sourced or LLM-derived interpretation so that
   it remains reproducible (§9) and cannot become a live side channel (§11 items
   12, 17)? *(Reproducibility aspect addressed by proposed ADR-DEV-002; capture, staleness, and
   re-authoring addressed by proposed ADR-DEV-003; pending acceptance.)*
4. How does the DSL represent "no-action / hold" versus "explicit flat
   (target = 0)" as distinct, first-class, reproducible outcomes (RFC-003 §16 Q4)?
   *(Addressed by proposed ADR-DEV-007; pending acceptance: distinct, first-class, reproducible outcomes — hold
   leaves exposure, flat proposes a zero-position action — never conflated or null.)*
5. Is the atomic authored unit a per-instrument target or a portfolio-wide target
   vector, and does the Proposal Builder support both without letting a strategy
   aggregate a combined authority (RFC-003 §§13, 16 Q1)? *(Addressed by proposed ADR-DEV-007; pending acceptance:
   both are supported and the unit is explicit; a portfolio vector is a set of
   per-instrument targets each independently approved and capacity-evaluated, never one
   aggregated authority.)*
6. How does an Authored Strategy express a decision made when a companion model
   (RFC-004/006/007) is itself degraded or unavailable, such that degradation
   narrows rather than widens the action set (RFC-003 §16 Q6; §6, §10)? *(Addressed by proposed ADR-DEV-008; pending acceptance: a degraded/UNKNOWN/STALE output is expressible only restrictively, the
   degraded decision is first-class and reproducible, and no self-computed substitute
   acquires the degraded model's authority.)*
7. What is the versioning and substitution protocol for an Authored Strategy and
   its DSL version such that a change is always a recorded, versioned substitution
   (§§6, 9; RFC-003 §13), and how does it interact with software-artifact
   admission (ADR-002-029)? *(Addressed by proposed ADR-DEV-004; pending acceptance: a change to the artifact, DSL
   version, enforcement version, or configuration is a recorded Versioned
   Substitution producing a new Artifact Identity and a new ADR-002-029 Release
   Generation that inherits no admission.)*

Unresolved questions reduce, and do not expand, the conforming action set.

---

## 15. Review History

### v0.1 — Initial Draft

* Established RFC-008 as the Implementation-layer Strategy DSL: the concrete
  authoring surface that realizes the RFC-003 Decision Policy and makes the
  untrusted proposer of RFC-002 §7.3 and philosophy §13 buildable.
* Set the governing thesis as **containment by construction**: all sixteen
  RFC-003 §11 prohibitions are made *unexpressible* at the authoring surface,
  not merely forbidden, and added two DSL-specific boundary items — an
  ambient-state prohibition (item 12) and the escape-closure property (item 17:
  no FFI, embedded host, dynamic loading, or extension point that reintroduces a
  prohibited effect).
* Defined the authoring surface (§7), the Proposal as the only output assembled
  through an effect-free Proposal Builder (§8), pure/seeded/bounded/isolated
  evaluation (§9), and the rules for consuming the RFC-004–007 models without
  acquiring authority or evading Critical Input governance (§10).
* Restated the boundary as seventeen unexpressible effects (§11) — all sixteen
  RFC-003 §11 prohibitions plus the DSL-specific ambient-state and escape-closure
  items — each traced to RFC-002 §9.1/§7.3, the ADR series, and RFC-003 §11.
* Marked scope relationships to RFC-003–007 and forward to RFC-009–011 without
  pre-empting them (§12).
* Introduced no SAFE-xxx requirement, numeric bound, or authority.
* Independent adversarial EV-L0 document review returned PASS-WITH-FIXES with no
  Critical finding. Twelve authority-leak sequences were attempted — self-approval
  via a confidence field, aggregate-state laundering via rationale text, wildcard
  "latest config" smuggling, arm-live via a `live=true` timing constraint,
  self-certified freshness, a transmit-race skipping Approval, a dynamic-plugin
  escape, and a protective self-label via a rationale keyword among them — and all
  were found blocked by §7 and the §11 boundary; every citation was verified
  against source, including the two verbatim load-bearing quotes (RFC-002 §9.1
  "Strategy SHALL NOT self-label an action as protective" and RFC-003 §10's
  "an LLM-derived interpretation"), and all sixteen RFC-003 §11 prohibitions were
  confirmed present (items 11 and 12 honestly merged into item 11). Two Major
  findings were resolved: (M1) §14 Open Questions 1 and 3 mislabeled the
  escape-closure clause as "item 16"/"§11.16" when it is item 17 (ambient-state is
  item 12) — corrected; (M2) §9's stochastic/externally-sourced carve-out (for
  example an LLM-derived interpretation) was in tension with the §6 principle 3 and
  §11 item 12 ambient-state/network prohibition — resolved by requiring such a
  value to be produced outside and before evaluation and delivered into the
  Decision Context Capsule as Critical Input, so DSL evaluation itself performs no
  live call. The review is EV-L0 only and confers no acceptance or live-readiness.
* Governance note (inherited citation imprecision — RESOLVED). §2's "SHALL NOT
  redefine constitutional intent" now cites RFC-000 §9 (Constitutional Boundaries),
  where that literal phrase appears; §12 (Constitutional Governance) states the
  cognate "SHALL NOT reinterpret higher-level intent." The identical imprecision in
  RFC-003 through RFC-011 was corrected consistently across the series in a single
  companion change rather than by a lone divergent edit.

### v0.2 — Wave 6 (CORPUS-REVIEW-0001 seam-sealing: M-22)

* **M-22 (§14 status hygiene).** Reframed the §14 Open Questions preamble and each item so
  that a `Proposed` (unaccepted) ADR-DEV *addresses* a question but does not *resolve* it —
  resolution follows acceptance; deleted the stale "while RFC-009 through RFC-011 are
  unwritten" clause.
* The change is narrow-only and additive; RFC-008 introduces no SAFE-xxx requirement,
  numeric bound, or authority, and no new EV (register counts unchanged). Independent
  adversarial EV-L0 review of this Wave-6 change is owed; this patch confers no acceptance
  or live-readiness.
