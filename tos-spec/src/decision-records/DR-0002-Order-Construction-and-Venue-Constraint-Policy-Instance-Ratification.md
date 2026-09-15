# DR-0002 — Order Construction Policy and Venue Constraint Policy Instance Ratification Path

- **Decision ID:** DR-0002
- **Date:** 2026-09-15
- **Status:** Accepted (System Owner, 2026-09-16 — PR #688 merged 2026-09-15;
  acceptance confirmed with the adoption of the first policy instances, see §6)
- **Decision Owner:** System Owner (final risk-acceptance authority, vision §12.1)
- **Category:** Governance Decision
- **Originating Finding:** RFC-002 §9.1 row "Construct canonical broker command"
  names "Order Construction Policy governance" as the rule supplier, and the
  Venue Constraint Gate as the producer of a non-authorizing decision. The
  implementation track's composition root (Phase 2 runtime shell) has, until
  this decision, carried both the Order Construction Policy coordinates and the
  three venue artifacts (Venue Constraint Policy, Venue Constraint Snapshot,
  Order Admissibility Decision) as caller-supplied test constants, and recorded
  the Order Construction Policy as "still-unratified". No document in the corpus
  said where an *instance* of either policy lives, what makes it active, or
  which of its declared content the current kernel realizes.
- **Normative Carriers:** ADR-002-019 §§5.1, 5.2, 5.4, 8, 9, 14; ADR-002-020
  §§5.2, 5.3, 9; ADR-002-014 §§7, 12, 13 (activation); RFC-002 §9.1;
  VER-002-001 §5 (authoring is not evidence); DR-0001 (governed
  single-operator variant)

---

## 1. Context

ADR-002-019 §5.1 defines the Venue Constraint Policy as "an immutable,
authenticated, separately governed artifact" and §8 closes with "Policy
activation follows ADR-002-014." ADR-002-020 §5.2 defines the Order
Construction Policy with the same three adjectives and §7 assigns its
governance to ADR-002-014 as well. Both ADRs remain `Proposed`: an ADR is
accepted only through executed evidence, so the object of ratification here is
not the ADR text but a **policy instance** — a concrete, digest-bound document
that a running system binds.

The verification track already carries non-authorizing shape canons for all
four artifacts involved (`verification/VENUE-CONSTRAINT-POLICY-template.yaml`,
`ORDER-CONSTRUCTION-POLICY-template.yaml`, `VENUE-CONSTRAINT-SNAPSHOT-template.yaml`,
`ORDER-ADMISSIBILITY-DECISION-template.yaml`). The templates carry shape, not
values, and each declares its rule content as free-form lists that are wider
than the Phase-1 kernel records (`tos.venue.VenueConstraintPolicy` realizes
admitting-phase rules, required constraint classes, order-shape constraints and
a dependency closure; `tos.ioc.OrderConstructionPolicy` realizes identity,
generation and version only).

The corpus has one prior instance-placement decision to follow: broker facts
"belong to a non-normative Broker Capability Profile instance produced on the
implementation track" (ADR-002-004 line 798), and that instance is loaded by the
runtime through a `_model_view` discipline — template-shaped keys carry data,
sibling `_model_view` blocks carry the kernel record's own field names, and the
loader constructs kernel values only from `_model_view` blocks.

Three questions were open and are resolved here:

1. **Placement.** Where does a filled Venue Constraint Policy / Order
   Construction Policy instance live, and is it normative?
2. **Activation.** What makes an instance *active* for a running system, given
   that ADR-002-014 §13 prescribes a ten-step atomic protocol whose full
   realization (staging to every consumer, commit-log ordering, attested
   compatibility) is later-phase work?
3. **Coverage.** Which declared content of each template does the current
   kernel realize, and what happens to the rest?

## 2. Decision

The System Owner adopts the following.

### 2.1 Placement — instances are non-normative, implementation-track files

A filled Venue Constraint Policy or Order Construction Policy instance is a
**non-normative implementation-track document**. It lives outside `tos-spec/`
(the ratified runtime location is a per-environment configuration directory of
the runtime shell, e.g. `config/tos_runtime/<environment>/`), it is never cited
as normative by any RFC, ADR or VER, and it follows the corresponding template's
shape exactly:

- every template key is present (schema fidelity); `artifact_type` and
  `schema_version` equal the template's;
- kernel-typed content is carried in a sibling `_model_view` block whose keys
  are the kernel record's own field names, spelled as the kernel spells them
  (`tos/src/tos/venue/records.py`, `tos/src/tos/ioc/records.py`);
- runtime-only facts that neither the template nor the kernel model names are
  carried in a `_runtime` block and are never read as kernel values;
- template rule lists that the kernel does not realize are preserved as data
  and interpreted by nothing (a runtime that interprets a free-form rule list
  would be authoring a judgment the kernel does not own).

The instance's `canonical_digest` is computed by the kernel's own issuance path
(`IndependentIdArtifact.issue`) over the kernel record's covered content. An
instance file may carry `TBD` in that slot (the digest is derived), or the exact
derived value (any other value is a refusal, not a warning).

### 2.2 Activation — an exact member reference in the Activation Record

An instance is active for a running system **only** when the system's
ADR-002-014 Activation Record names it as a bundle member with an exact match on
kind, identity, generation and canonical digest, and the member is marked
resolved and immutable (`tos.spg.BundleMemberRef`, kinds
`VENUE_CONSTRAINT_POLICY` / `ORDER_CONSTRUCTION_POLICY`). Absence, any
mismatch, a duplicate match, an unresolved or mutable member, or an instance
whose own `status` is not `ISSUED` is a boot refusal of the composition root —
never a permissive default, never a warning.

This is a **bounded realization** of ADR-002-014 §13: it establishes steps 2
(immutable artifact set and generation), 3 (approval — through DR-0001's
governed single-operator variant, the same path the runtime's existing
Runtime Safety Profile activation uses) and 8's *content* (one record naming
exact digests). It does **not** realize staging to every permission-creating
consumer, authenticated compatibility attestations per consumer, or Safety
Commit Log ordering of the activation. Those remain later-phase obligations and
are recorded as such; nothing in this decision claims them.

The Runtime Safety Profile's own activation semantics are unchanged by this
decision: the two policy members are checked by a separate exact-match read of
the same Activation Record and do not enter the safety-profile bundle's
completeness or atomicity judgment.

### 2.3 Coverage — what v1 realizes, and what the rest becomes

| Template content | Kernel realization (Phase 1) | v1 instance treatment |
|---|---|---|
| Venue policy: admitting session phases per action | `admitting_phase_rules` → `session_phase_admits` | filled; an action not enumerated is `INADMISSIBLE`; a phase token the deployment's calendar can never produce is a boot refusal (a vacuous admit is not an admit) |
| Venue policy: price band, tick, lot, quantity, allowed order types / TIF / sides / position effects | `shape_constraints` → `order_shape_admissible` | filled where a source exists; a numeric bound with **no source is `null`** and the kernel returns `UNKNOWN` for the shape — the instance lists its null bounds, the runtime evidences them at boot, and no value is invented |
| Venue policy: required constraint classes, dependency closure | covered digest content; no Phase-1 predicate consumes them | filled as declared; grants nothing |
| Venue policy: approved sources, continuity, halt/suspension, account/margin/borrow/settlement, broker-capability requirements, corroboration | not realized by a Phase-1 predicate the composition root folds | preserved as data; not interpreted |
| Venue snapshot / admissibility decision | issued by the runtime's venue-constraint service, per tick generation and per exact attempt respectively, with `result` produced **only** by the kernel fold (`fold_venue_admissibility`) | never file-supplied; fields with no source (`critical_input_snapshot_digest`, `source_continuity_id`, per-action tradability map, `max_age`, broker profile digest while the profile is `DRAFT`) are `None` and evidenced as absent |
| Order Construction Policy: identity, generation, version | `policy_id` / `policy_generation` / `policy_version` (`_REQUIRED_COVERED`) | filled; the candidate command binds these coordinates |
| Order Construction Policy: signer, approval, evidence package | fields exist on the kernel record but the kernel's construction path (`construct_candidate_command`) issues the bound policy from the three coordinates above only | left `None` in v1 so the instance digest equals the digest the construction path issues (a same-identity, different-bytes pair is the kernel's own `CRITICAL_CONFLICT` shape); binding them is a kernel-round candidate, recorded, not silently approximated |
| Order Construction Policy: canonicalization version, serializer / actual-outbound rules | not a kernel-record field | `_runtime.canonicalization_version` must equal the composition root's scheme version; `_runtime.wire_codec` must name the exact wire field set the transport's codec realizes when a broker-wire transport is composed, and must be `null` for the synthetic transport — cross-checked at boot, refused on mismatch |
| Order Construction Policy: every other §9 declaration | not realized | preserved as data; `TBD` where owed |

### 2.4 What this decision does not do

It does not accept ADR-002-019, ADR-002-020 or ADR-002-014. It creates no
authority: an active policy instance approves nothing, commits no capacity,
issues no Live Authorization, classifies nothing as protective, and transmits
nothing (the templates' `authority` blocks stay all-false and are not read by
the runtime as permission). It does not fill any value: the concrete numbers a
deployment's instance carries are a separate System Owner approval, table by
table, with provenance recorded per value.

## 3. Options Considered

### 3.1 Option (a) — Load the snapshot and decision from configuration too

Rejected. A file-supplied Order Admissibility Decision makes the final-egress
check "the bound decision itself admits" vacuous by construction — the same
constant-into-a-predicate failure the implementation track has already
catalogued — and contradicts ADR-002-019 §14 (a decision is issued for one exact
broker-request shape, before approval and again for any changed shape).

### 3.2 Option (b) — Author kernel-narrow instance files without the template shape

Rejected. The templates exist precisely so that an instance is recognizably an
instance of the ratified artifact; a kernel-shaped file would drift from the
spec artifact the moment the kernel model grows, and the Broker Capability
Profile instance already established the template-plus-`_model_view` path.

### 3.3 Option (c) — Wait for the full ADR-002-014 §13 activation protocol

Rejected for now. The runtime already activates its Runtime Safety Profile
through an Activation Record file plus DR-0001's single-operator variant; adding
two exact member references to that record is the same level of realization, no
more and no less, and it is honestly bounded in §2.2. Waiting would leave the
composition root binding test constants indefinitely.

### 3.4 Option (d) — Template shape plus `_model_view`, exact activation member match, bounded coverage (ADOPTED)

Adopted as §2.

## 4. Rationale

- The spec's own division of roles (RFC-002 §9.1:553-554) is *policy supplies
  rules, service produces a non-authorizing decision, gateway enforces the
  exact current result*. Placing the policy in a governed file and the decision
  in a service is that division realized; anything else collapses two roles
  into one.
- Honesty about coverage is cheaper than a wide claim: ADR-002-019 §8 already
  says missing policy coverage yields `UNKNOWN` or `INADMISSIBLE`, never a
  permissive default. Leaving unsourced bounds `null` makes the kernel say
  exactly that.
- Reusing the existing Activation Record and the kernel's `BundleMemberRef`
  model adds no new activation mechanism and keeps the safety-profile
  judgment untouched.

## 5. Consequences

- A composition root that binds a `DRAFT` policy instance, an instance not named
  in its Activation Record, or an instance whose digest differs from the named
  member digest, does not boot.
- A deployment whose venue policy carries `null` price bounds produces
  `UNKNOWN` venue admissibility for every attempt and therefore transmits
  nothing until a governed price-band source exists. This is the intended
  fail-closed state, and it is visible in evidence at boot.
- The Order Construction Policy's signer / approval / evidence-package binding
  is deferred to a kernel change; until then the instance carries them as
  `None` and the activation member digest is the digest of the three-coordinate
  record. This is recorded here so no later reader mistakes it for a bound
  approval.
- The templates are unchanged by this decision.

## 6. Normative Status and Future Constitutional Work

This record is a governance decision, not a normative specification. It becomes
`Accepted` when the System Owner merges the change that introduces it; a later
change that realizes the remaining ADR-002-014 §13 steps, or a kernel round that
binds the Order Construction Policy's approval fields, supersedes the
corresponding rows of §2.3 by a new decision record, never by editing this one.

## 7. Related Documents

- ADR-002-019 — Venue, Session, Tradability, and Broker Constraint Gate
- ADR-002-020 — Intent-to-Order Conformance, Canonical Command Construction, and Economic-Effect Fencing
- ADR-002-014 — Hard Safety Envelope and Runtime Safety Profile Governance
- ADR-002-004 line 798 — instance placement precedent (Broker Capability Profile)
- DR-0001 — Single-Operator Live Governance
- `verification/VENUE-CONSTRAINT-POLICY-template.yaml`,
  `verification/ORDER-CONSTRUCTION-POLICY-template.yaml`,
  `verification/VENUE-CONSTRAINT-SNAPSHOT-template.yaml`,
  `verification/ORDER-ADMISSIBILITY-DECISION-template.yaml`
- Implementation-track plan: `docs/plans/2026-09-15-tos-venue-constraint-service-plan.md`
