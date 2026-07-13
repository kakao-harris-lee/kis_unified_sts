# ADR-002-004 — Broker Capability Requirements and Fallbacks

- **Status:** Proposed
- **Date:** 2026-07-13
- **Decision Type:** Safety-Critical Architecture Decision
- **Scope:** Broker capability contracts, order identity, idempotency, evidence semantics, cancellation, fills, reconciliation, rate limits, sessions, credentials, protective execution, capability degradation, and live-scope gating
- **Supersedes:** None
- **Amends:** RFC-002 Broker Adapter, reconciliation, execution, and live-scope semantics
- **Depends On:** RFC-000; RFC-001 SAFE-020, SAFE-021, SAFE-024, SAFE-025, SAFE-033, SAFE-040, SAFE-043; ADR-002-001 v0.2; ADR-002-002; ADR-002-003

---

## 1. Decision

Every live broker integration SHALL have a versioned, evidence-backed **Broker Capability Profile** that defines what the broker actually guarantees for a specific combination of:

- broker and API product;
- environment;
- account type;
- market;
- instrument class;
- order type;
- session or connection type;
- credential scope;
- API version;
- broker operational mode.

The Trading Operating System SHALL NOT infer broker safety properties from generic API success, documentation wording, sandbox behavior, or another market/account configuration.

The Broker Adapter SHALL enforce a capability-dependent execution policy. Missing, unknown, contradictory, expired, or unverified capability evidence SHALL reduce live scope or prohibit the affected action.

A broker capability deficiency SHALL NOT be hidden behind retries or optimistic reconciliation. Required fallback behavior SHALL be explicit, conservative, measurable, and tied to the affected authority and risk scope.

Where deterministic broker-side idempotency or attribution is unavailable:

1. blind retry is prohibited;
2. the uncertain transmission remains potentially live;
3. its full conservative economic effect remains capacity-consuming;
4. the affected scope enters containment;
5. account-wide or approved-scope reconciliation runs before any new conflicting action;
6. unresolved ambiguity remains `UNKNOWN` and cannot be released by timeout.

A broker integration may be approved for restricted live operation even when some capabilities are unavailable, but only when the fallback preserves RFC-000/RFC-001 safety properties and the restricted scope is explicitly approved.

---

## 2. Context

Broker APIs differ materially in their semantics. They may:

- assign an order identifier only in the response;
- not accept a client-generated identifier;
- acknowledge receipt without confirming acceptance;
- emit fills before acknowledgements;
- deliver duplicate or out-of-order events;
- omit an order from a query during eventual consistency;
- provide incomplete pagination or limited history windows;
- acknowledge cancellation while a crossing fill is still possible;
- implement replace as cancel-then-new;
- lack reduce-only semantics;
- expose only polling rather than account event push;
- apply one global request limit across normal and protective traffic;
- serialize requests through one session;
- provide sandbox behavior that differs from production;
- permit manual HTS activity without immediate API notification;
- change API semantics without preserving prior assumptions.

The architecture cannot guarantee exactly-once economic effect at the network boundary. It must instead understand the broker’s identity, evidence, and ordering properties and use conservative containment when the external effect is uncertain.

A capability profile converts external assumptions into explicit safety inputs. It also prevents one broker’s stronger features from silently becoming assumptions in another adapter.

---

## 3. Decision Drivers

1. no duplicate order from blind retry;
2. deterministic attribution where available and conservative containment where unavailable;
3. no capacity release based on weak cancellation or missing query evidence;
4. explicit external-activity detection bounds;
5. broker rate/session limitations must not be represented as guaranteed protective reserve when they are not;
6. live scope must shrink when capabilities are weaker;
7. capability changes must trigger revalidation;
8. evidence must be reproducible and broker-specific;
9. paper/test behavior must not automatically authorize live behavior;
10. implementation convenience is subordinate to safety.

---

## 4. Scope

This ADR decides:

- the Broker Capability Profile model;
- capability status and assurance levels;
- mandatory capability dimensions;
- minimum live-operation gates;
- fallback behavior for missing capabilities;
- order identity and uncertain-send policy;
- cancellation, fill, replace, and final-quantity evidence rules;
- polling and external-activity bounds;
- rate-limit and session treatment;
- credential and egress requirements;
- capability change and revalidation policy;
- verification and approval obligations.

This ADR does not decide:

- one broker’s final capability values;
- exact polling intervals;
- exact request quotas;
- exact supported instrument list;
- the broker’s commercial or contractual terms;
- the internal database technology;
- the complete order-state implementation.

Those values belong in broker-specific Capability Profiles and Verification Profiles.

---

## 5. Definitions

### 5.1 Broker Capability Profile

A signed or otherwise controlled configuration and evidence record describing broker semantics for a defined integration scope.

### 5.2 Capability Dimension

One independently assessed broker property, such as client-order identity, cancellation finality, fill replay, or rate-limit isolation.

### 5.3 Capability Status

Each dimension SHALL have one of:

```text
VERIFIED
VERIFIED_WITH_RESTRICTION
DOCUMENTED_NOT_VERIFIED
UNSUPPORTED
CONTRADICTORY
UNKNOWN
EXPIRED
```

Only `VERIFIED` and explicitly approved `VERIFIED_WITH_RESTRICTION` may authorize live behavior.

### 5.4 Assurance Source

The evidence used to classify a capability, including:

- official specification;
- broker contractual statement;
- controlled sandbox test;
- controlled production probe;
- fault-injection result;
- observed live evidence;
- broker support confirmation;
- independent operational review.

### 5.5 Deterministic Attribution

The ability to map a broker-visible order or fill to exactly one TOS Intent and transmission attempt without relying on ambiguous combinations of time, price, quantity, or side.

### 5.6 Deterministic Idempotency

A broker guarantee that repeated submission using the approved identity cannot create more than one broker-side order or economic effect.

### 5.7 Final Quantity Proof

Broker-specific evidence establishing both final cumulative filled quantity and zero remaining executable quantity.

### 5.8 External Activity Detection Bound

The maximum approved interval between an external account change and TOS containment or incorporation of that change into authoritative risk state.

### 5.9 Capability Degradation

A change from a stronger to a weaker or unknown capability status caused by API version change, broker incident, inconsistent observation, credential/session change, or evidence expiry.

### 5.10 Live Scope

The approved combination of account, instrument, order type, quantity/risk limits, session, action class, and operating mode that the capability profile permits.

---

## 6. Safety Invariants

### BC-INV-001 — No Assumed Capability

A broker property that is not present and current in the approved Capability Profile SHALL be treated as unavailable.

### BC-INV-002 — No Blind Retry

If deterministic idempotency or equivalent proof is unavailable, a transmission with unknown outcome SHALL NOT be retried as a new broker order.

### BC-INV-003 — Unknown Send Remains Potentially Live

Loss of acknowledgement does not prove rejection. The reservation and potentially-live quantity remain active until evidence resolves them.

### BC-INV-004 — Weak Negative Evidence Cannot Release

Absence from one query, one event stream, or one page is not Final Quantity Proof.

### BC-INV-005 — Broker-Specific Finality

Cancellation, rejection, expiration, and replacement semantics SHALL be interpreted only according to the approved profile for that broker/order type.

### BC-INV-006 — External Detection Is Bounded

Where external account activity is possible, the approved live scope SHALL be sized so that the worst credible undetected change during the detection bound cannot violate the Hard Safety Envelope when combined with new TOS activity.

### BC-INV-007 — Protective Guarantee Is Honest

A shared session, connection, rate limit, credential, or broker control plane SHALL NOT be described as physically reserved unless the broker or implementation enforces independent availability.

### BC-INV-008 — Capability Change Fails Closed

Capability degradation to `UNKNOWN`, `CONTRADICTORY`, `EXPIRED`, or `UNSUPPORTED` SHALL block the affected live action until re-approved.

### BC-INV-009 — Test and Live Are Separate

Sandbox or paper capability evidence SHALL NOT automatically establish live capability.

### BC-INV-010 — Egress Enforces Profile

The final Broker Adapter SHALL reject any request outside the current approved Capability Profile and Live Scope.

### BC-INV-011 — Query Limits Are Safety Inputs

Pagination, history windows, rate limits, session serialization, and query consistency are part of the safety model, not operational details.

### BC-INV-012 — Manual Activity Is Not Invisible by Assumption

When manual or third-party account activity is permitted, its detection and containment behavior SHALL be explicitly modeled and tested.

---

## 7. Capability Profile Identity and Governance

### 7.1 Profile Key

A profile SHALL be keyed by at least:

```text
broker_id
api_product
api_version
environment
account_type
market
instrument_class
order_type
session_type
credential_scope
```

Broader profiles are permitted only when evidence proves semantic equivalence across the broader scope.

### 7.2 Profile Version

Every profile SHALL have:

- immutable profile version;
- effective date;
- evidence package version;
- approver identity;
- expiration or revalidation date;
- superseded version link;
- change reason.

### 7.3 Activation

A profile becomes active only after:

- required dimensions are classified;
- mandatory tests pass;
- residual restrictions are encoded;
- Safety Profile references the profile version;
- Broker Adapter has the matching enforcement policy;
- independent safety review approves live scope.

### 7.4 Change Control

Any change in API version, endpoint, account type, market, credential model, session behavior, or broker operational notice SHALL trigger impact assessment and may invalidate the profile.

### 7.5 Contradictory Evidence

When documentation and observed behavior conflict, the capability status becomes `CONTRADICTORY`. The system applies the safer interpretation and blocks affected actions until resolved.

---

## 8. Capability Dimensions

### 8.1 Order Identity

The profile SHALL state:

- whether client-generated order identity is accepted;
- whether it is echoed in responses and queries;
- uniqueness scope;
- duplicate-submission behavior;
- retention duration;
- query-by-client-identity support;
- broker-assigned order identity semantics;
- identity behavior across session reconnect and day boundary.

### 8.2 Submission Idempotency

The profile SHALL state:

- whether identical retries are deduplicated;
- required idempotency key;
- deduplication window;
- whether retries can create multiple accepted orders;
- behavior after timeout, disconnect, and session reauthentication.

### 8.3 Acknowledgement Semantics

The profile SHALL distinguish:

```text
TRANSPORT_RECEIVED
BROKER_RECEIVED
VALIDATED
ACCEPTED
WORKING
REJECTED
```

If one response code combines these states, the weakest safe interpretation applies.

### 8.4 Fill Events

The profile SHALL state:

- whether fills may precede acknowledgement;
- event ordering guarantees;
- sequence identifiers;
- duplicate delivery behavior;
- replay support;
- cumulative versus incremental quantity semantics;
- correction/bust behavior;
- event retention and recovery window.

### 8.5 Open-Order Query

The profile SHALL state:

- completeness;
- pagination behavior;
- eventual-consistency window;
- filter semantics;
- status coverage;
- day/session scope;
- whether missing orders can still be live;
- maximum result size and truncation behavior.

### 8.6 Order-History Query

The profile SHALL state:

- retained period;
- final state fields;
- cumulative fill accuracy;
- correction visibility;
- query latency;
- pagination and omission behavior.

### 8.7 Cancellation

The profile SHALL state:

- what cancel acknowledgement means;
- whether crossing fills remain possible;
- how final cumulative quantity is obtained;
- whether cancel is idempotent;
- whether cancellation can be rejected because the order already filled;
- late-event window;
- broker sequence semantics.

### 8.8 Replace or Amend

The profile SHALL classify replace as:

```text
ATOMIC_REPLACE
CANCEL_THEN_NEW
NEW_THEN_CANCEL
BROKER_UNSPECIFIED
UNSUPPORTED
```

The profile SHALL define overlap and protection-gap behavior.

### 8.9 Reduce-Only or Close-Only

The profile SHALL state:

- availability;
- exact enforcement semantics;
- race behavior when position changes;
- whether the broker can reverse a position despite the flag;
- instrument and order-type restrictions.

### 8.10 Positions, Balances, and Margin

The profile SHALL state:

- consistency and freshness;
- intraday versus settled quantities;
- pending settlement treatment;
- margin calculation timing;
- currency conversion timing;
- correction behavior;
- account aggregation semantics;
- manual and third-party activity visibility.

### 8.11 Account Event Push

The profile SHALL state:

- whether real-time account events exist;
- delivery guarantees;
- reconnect replay;
- sequence handling;
- event gaps;
- rate and session interactions.

### 8.12 Corporate and Administrative Events

The profile SHALL state support for:

- splits and consolidations;
- symbol changes;
- mergers;
- delisting and suspension;
- option assignment/exercise;
- futures expiry and rollover;
- broker adjustments;
- account transfer;
- dividend or distribution quantity effects.

### 8.13 Rate Limits

The profile SHALL state:

- hard and soft limits;
- scope: credential, account, session, IP, endpoint, or global;
- burst behavior;
- reset behavior;
- throttling response;
- cancellation and query treatment;
- whether ordinary traffic can consume protective capacity;
- broker incident behavior.

### 8.14 Session and Connection Model

The profile SHALL state:

- concurrent session support;
- single-session restrictions;
- request serialization;
- head-of-line blocking;
- reconnect behavior;
- session ownership;
- independent protective session feasibility;
- push/poll coexistence.

### 8.15 Credentials and Authorization

The profile SHALL state:

- credential scope by account/action;
- read versus trade separation;
- environment isolation;
- session revocation behavior;
- credential rotation latency;
- IP/network restrictions;
- sub-account isolation;
- emergency disable capability.

### 8.16 Broker Time

The profile SHALL state:

- timestamp source;
- timezone;
- precision;
- ordering reliability;
- drift or synchronization guarantees;
- day-boundary behavior;
- whether timestamps can be used for attribution or only audit.

### 8.17 Market and Instrument Constraints

The profile SHALL state:

- quantity units;
- price units and tick sizes;
- multipliers;
- order limits;
- price collars;
- session phases;
- auction behavior;
- market halts;
- short-sale or derivative restrictions;
- settlement and expiration rules relevant to safety.

---

## 9. Capability Assurance Levels

Each dimension SHALL record both status and assurance level.

### Level 0 — Unknown

No usable evidence. Live use prohibited.

### Level 1 — Documented

Official documentation describes the behavior, but it has not been operationally verified. Live use is prohibited for safety-critical reliance unless an explicit temporary exception is approved with a stricter fallback.

### Level 2 — Controlled Test Verified

Behavior is verified in sandbox or a controlled environment. Live use remains restricted until production equivalence is established.

### Level 3 — Restricted Production Verified

Behavior is verified in controlled production scope with bounded risk and reproducible evidence.

### Level 4 — Continuously Monitored

Production behavior is verified and continuously checked for drift or contradiction.

Safety-critical live scope normally requires Level 3 or Level 4 for the dimensions it relies upon.

---

## 10. Broker Conformance Classes

Conformance classes summarize but do not replace dimension-level decisions.

### CLASS-A — Deterministic Live

Required characteristics include:

- deterministic order attribution;
- proven idempotency or safe same-order retry;
- reliable fill replay or sequence recovery;
- broker-specific Final Quantity Proof;
- bounded external-activity detection;
- enforced egress identity and revocation;
- approved rate/session behavior.

CLASS-A may support broader live concurrency within the Hard Safety Envelope.

### CLASS-B — Restricted Serialized Live

Used when some identity or event capability is weaker but conservative fallback is possible.

Typical restrictions:

- one unresolved transmission per approved containment scope;
- no blind network retry;
- smaller action and aggregate limits;
- account or instrument serialization;
- mandatory query-before-decision after uncertainty;
- stricter operator and reconciliation controls;
- no claimed guaranteed protective session unless proven.

### CLASS-C — Protective or Supervised Only

Used when normal autonomous risk increase is not supportable but a narrow supervised or broker-native protective action is safe.

### CLASS-D — Non-Live

Used for research, simulation, paper, shadow, or unsupported broker scope. Live transmission prohibited.

A class cannot override a failed mandatory dimension.

---

## 11. Minimum Live Gates

No live scope may be approved unless all of the following are defined:

1. deterministic or conservatively bounded order attribution;
2. explicit uncertain-send behavior;
3. broker-specific Final Quantity Proof;
4. partial-fill and duplicate-event handling;
5. cancellation crossing-fill behavior;
6. replace semantics;
7. open-order and history query completeness limits;
8. external-activity detection bound;
9. rate-limit and session model;
10. credential and egress fencing model;
11. position, balance, and margin evidence semantics;
12. capability version and revalidation process;
13. approved fallback for every unavailable capability;
14. verification evidence at required assurance level.

A missing gate results in CLASS-D for the affected scope.

---

## 12. Order Submission Policy

### 12.1 Pre-Submission

Before transmission, Broker Adapter SHALL verify:

- active Capability Profile version;
- order type and instrument are within Live Scope;
- required identity/idempotency semantics;
- current authority and capacity capability;
- request conforms to broker units, multiplier, price, quantity, and session rules;
- rate/session budget permits the request;
- no unresolved transmission exists in a mutually exclusive containment scope.

### 12.2 Durable Send Boundary

The adapter SHALL durably record `SEND_STARTED` or equivalent before the first external side effect can occur.

### 12.3 Response Interpretation

A broker response SHALL be mapped to the weakest state supported by the profile. Unknown fields or undocumented codes do not imply rejection.

### 12.4 Uncertain Send

When the outcome is uncertain:

```text
NO blind retry
NO capacity release
NO assumption of rejection
NO new conflicting order in containment scope
START reconciliation
ENTER UNKNOWN/CONTAINED as required
```

### 12.5 Same-Order Retry

A network retry is allowed only when the profile proves deterministic idempotency for the exact request identity and retry window.

The adapter SHALL verify that retry cannot create a second broker order.

---

## 13. Fallback Matrix

### 13.1 No Client-Generated Order ID

Required fallback:

- assign an internal attempt identity;
- prohibit blind retry after uncertain send;
- serialize unresolved sends within the approved containment scope;
- query all available order, fill, and account evidence;
- attempt attribution using broker-assigned identity only when obtained;
- treat ambiguous candidates as external/unattributed;
- keep full reservation until resolved;
- contain the affected account or narrower proven scope.

Time, price, quantity, and side matching alone SHALL NOT be treated as deterministic when multiple candidates can exist.

### 13.2 No Query by Client Identity

Required fallback:

- query complete approved order-history windows;
- use broader account evidence;
- prevent concurrency that would create ambiguous matches;
- contain on ambiguity;
- require dedicated-account or manual-trading restrictions if necessary.

### 13.3 No Proven Idempotency

Required fallback:

- no network resend after uncertainty;
- new attempt only after non-acceptance is authoritatively proven;
- preserve reservation during query and reconciliation.

### 13.4 No Real-Time Fill Push

Required fallback:

- bounded polling using reserved reconciliation budget;
- smaller live limits sized to polling delay;
- no capacity release until polled final evidence is complete;
- degraded or contained state if polling bound is missed.

### 13.5 Incomplete or Eventually Consistent Open-Order Query

Required fallback:

- absence is weak negative evidence;
- combine history, fills, position, and later queries;
- maintain UNKNOWN until Final Quantity Proof;
- record the maximum observed omission window.

### 13.6 Weak Cancel Acknowledgement

Required fallback:

- keep remaining quantity potentially live;
- establish final cumulative fill and zero remaining quantity;
- include broker-specific late-event window;
- process late fills without state rejection.

### 13.7 Non-Atomic Replace

Required fallback:

- reserve overlap capacity when both old and new may be live;
- represent any protection gap as unprotected risk;
- fail closed if neither overlap nor gap risk fits the envelope;
- record replacement sequence and final evidence.

### 13.8 No Reduce-Only

Required fallback:

- use target-position semantics rather than repeated order quantity;
- include all pending exits and potentially-live attempts;
- cap quantity to conservative confirmed position;
- prohibit autonomous exit when position and pending-exit state are too uncertain to prevent reversal;
- use supervised or narrower scope where required.

### 13.9 No Account Event Push

Required fallback:

- define and test polling detection bound;
- reserve rate capacity for reconciliation;
- limit new action size for undetected external changes;
- contain when the bound is missed.

### 13.10 Shared Global Rate Limit

Required fallback:

- classify protective request capacity as `PRIORITIZED_ONLY` or `BEST_EFFORT`, not physical reserve;
- enforce ordinary traffic admission below the broker limit;
- reserve local worker and queue capacity;
- trigger degraded mode before broker headroom is exhausted;
- record common-mode residual risk.

### 13.11 Single Session or Head-of-Line Blocking

Required fallback:

- enforce bounded request duration;
- isolate local queues and workers where possible;
- prevent ordinary long-running operations from occupying the only channel;
- classify external guarantee honestly;
- reduce live scope if protective latency cannot be bounded.

### 13.12 No Rapid Credential or Session Revocation

Required fallback:

- force traffic through an internally fenced egress gateway;
- prevent direct broker credentials in execution workers;
- treat direct credential leakage as Critical incident;
- prohibit offline protective ownership where stale direct access cannot be bounded.

### 13.13 No Corporate-Action Feed

Required fallback:

- use approved independent reference source;
- run pre-session identity and quantity checks;
- enter containment on unexplained remap or quantity change;
- prohibit live authority until revaluation and mapping complete.

### 13.14 Sandbox/Production Divergence

Required fallback:

- use sandbox only for protocol development;
- require restricted production verification for safety-critical semantics;
- do not inherit capability status across environments.

---

## 14. Attribution and Containment Scope

### 14.1 Preferred Scope

Containment SHOULD be as narrow as can be proven safe, for example one attempt or one instrument.

### 14.2 Ambiguity Expansion

When broker evidence cannot distinguish among multiple actions, containment SHALL expand to include every scope that could own the economic effect.

This may expand to:

- instrument;
- strategy;
- account;
- portfolio;
- broker integration.

### 14.3 Dedicated Accounts

A dedicated account may reduce attribution ambiguity. It does not remove the need for broker evidence, reconciliation, or manual-activity controls.

### 14.4 Manual Activity

If manual HTS or another system may trade the account:

- its activity is considered a first-class external input;
- the detection bound must be approved;
- ambiguous activity triggers containment;
- operator identity or declared maintenance windows may improve attribution but do not replace broker evidence.

---

## 15. Final Quantity Proof

### 15.1 Per-Profile Definition

Every supported order type SHALL define an approved Final Quantity Proof recipe.

### 15.2 Required Result

The recipe SHALL establish:

- broker order identity or bounded unattributed effect;
- final cumulative filled quantity;
- zero remaining executable quantity;
- treatment of corrections, busts, and late events;
- evidence source provenance;
- valid history/query window;
- ordering or waiting rule where required.

### 15.3 Prohibited Proofs

The following alone are insufficient:

- cancel acknowledgement;
- one open-order query omission;
- local timeout;
- strategy cancellation intent;
- process restart;
- account position matching an expected value;
- operator assertion without broker evidence.

### 15.4 Stronger Broker Proof

A broker-specific terminal event may be accepted when its semantics are verified and the profile states that no crossing fill or correction can later change final quantity, or defines the bounded correction handling required.

---

## 16. External Activity Detection

### 16.1 Detection Sources

Detection may use:

- account event push;
- order and fill polling;
- position polling;
- balance and margin polling;
- broker statements or drop-copy;
- approved independent records.

### 16.2 Detection Bound

The profile SHALL define:

```text
B_external_detect
B_external_contain
```

The bound SHALL include:

- broker update latency;
- poll schedule;
- pagination;
- request throttling;
- processing delay;
- evidence consistency delay;
- failure retry budget.

### 16.3 Missed Bound

If the bound is exceeded:

- new risk authority for the affected scope is denied;
- the system enters at least `LIVE_RESTRICTED` or `CONTAINED` as defined by Safety Profile;
- reconciliation receives reserved priority;
- an alert and evidence record are generated.

### 16.4 Sizing Against the Window

Maximum order and aggregate limits SHALL account for the largest credible external change that can remain undetected during the bound.

---

## 17. Rate Limits and Protective Capacity

### 17.1 Measured Limit

The adapter SHALL maintain a conservative broker request budget using both documented limits and observed behavior.

### 17.2 Admission Control

Ordinary trading SHALL be throttled before consuming request headroom needed for:

- cancellation;
- order-state query;
- fill query;
- position/margin query;
- protective action;
- emergency containment.

### 17.3 Honest Guarantee Level

Where the broker has one global rate limit, external capacity is not physically reserved. Local admission control may provide a logical reserve but cannot guarantee availability against broker-side or third-party traffic.

### 17.4 Rate-Limit Incident

Unexpected throttling, undocumented limit changes, or persistent head-of-line blocking SHALL degrade the capability profile and may force containment.

### 17.5 Multi-Account Contention

When accounts share a broker/global quota, protective and reconciliation budgets SHALL have an approved arbitration policy. First failure must not consume all capacity without considering other exposed accounts.

---

## 18. Session and Credential Architecture

### 18.1 Final Egress

Every live order SHALL pass through the approved Broker Adapter or egress gateway.

### 18.2 Credential Isolation

Live trade credentials SHALL NOT be available to:

- strategy code;
- research code;
- backtest or simulation;
- general operator UI;
- untrusted automation;
- stale worker instances outside the fenced egress identity.

### 18.3 Read and Trade Separation

Where supported, reconciliation read credentials SHOULD be separated from trade credentials, provided this does not create inconsistent account visibility.

### 18.4 Environment Separation

Test and live credentials, endpoints, network routes, and account identities SHALL be distinct and non-interchangeable.

### 18.5 Emergency Disable

The profile SHALL state how broker access can be disabled and the maximum enforcement latency. Absence of rapid broker-side revocation increases reliance on internal egress fencing and reduces permissible offline authority.

---

## 19. Broker Adapter Enforcement

Before transmitting, the adapter SHALL verify:

- active Broker Capability Profile and version;
- permitted conformance class;
- Live Scope;
- current Safety Authority capability;
- valid risk-capacity reservation or protective consumption;
- supported order identity and retry policy;
- no unresolved mutually exclusive attempt;
- session and request budget;
- units, multiplier, quantity, price, and order semantics;
- required evidence capture path available;
- capability has not degraded since authorization.

The adapter SHALL reject requests that depend on a capability status other than `VERIFIED` or approved `VERIFIED_WITH_RESTRICTION`.

---

## 20. Capability Monitoring and Drift

### 20.1 Runtime Contradiction Detection

The system SHALL detect behavior inconsistent with the active profile, including:

- duplicate order despite declared idempotency;
- event before states declared impossible;
- missing sequence;
- late fill beyond approved window;
- query omission beyond measured bound;
- unexpected rate limit;
- session behavior change;
- unknown status code;
- unit or multiplier mismatch.

### 20.2 Degradation Response

On contradiction:

1. mark affected dimension `CONTRADICTORY`;
2. deny affected live actions;
3. preserve potentially-live capacity;
4. contain or halt the affected scope;
5. capture evidence;
6. require profile review and revalidation.

### 20.3 Evidence Expiry

Evidence SHALL have a freshness policy. A capability whose evidence expires becomes `EXPIRED` until revalidated.

### 20.4 Broker Notice

Material broker API or operational notices trigger profile impact review before continued reliance.

---

## 21. Broker-Specific Capability Profile Template

Every broker profile SHALL contain at least:

```text
Profile Identity
- broker/API/environment/account/market/order scope
- profile version
- effective and expiry dates

Live Scope
- allowed accounts
- instruments and order types
- maximum concurrency
- maximum quantity/risk
- permitted modes

Capability Matrix
- dimension
- status
- assurance level
- evidence reference
- restriction
- fallback

Final Quantity Proof
- recipe by order type
- late-event/correction rule

Uncertain Send Policy
- containment scope
- query sequence
- retry prohibition or proven idempotent retry

External Activity
- source
- detection and containment bounds

Rate and Session
- measured limits
- ordinary admission ceiling
- protective/reconciliation classification

Credential and Fencing
- egress path
- revocation behavior
- direct-access prohibition

Residual Risks
- description
- owner
- acceptance
- expiry

Verification
- test IDs
- last pass
- evidence digest
```

A broker-specific profile SHALL not copy unverified assumptions from this ADR.

---

## 22. Failure Modes and Required Responses

| Failure | Required response |
|---|---|
| ACK lost, idempotency unsupported | no retry; preserve capacity; reconcile; contain scope |
| Fill arrives before ACK | process fill idempotently; do not reject by state order |
| Duplicate fill event | deduplicate by verified identity/sequence; preserve cumulative correctness |
| Order missing from open-order query | treat as weak negative evidence; continue reconciliation |
| Cancel ACK followed by fill | accept fill; transfer capacity; investigate profile if beyond approved semantics |
| Replace is non-atomic | reserve overlap or represent protection gap |
| Manual HTS trade detected | quarantine external exposure; contain and reconcile |
| Polling bound missed | deny new risk in affected scope |
| Broker throttles protective call | enter degraded/contained mode; record reserve guarantee failure |
| Session reconnect changes identity semantics | invalidate affected profile; no retry until revalidated |
| API version changes | suspend reliance pending profile review |
| Unknown broker status code | map to UNKNOWN; no release |
| Position query conflicts with fills | per-field evidence conflict; conservative bound |
| Credential cannot be revoked | rely on fenced egress; reduce offline authority |
| Sandbox and live differ | live profile controls; sandbox evidence does not override |

---

## 23. Alternatives Rejected

### 23.1 One Generic Broker Interface Contract

Rejected because identical method names hide materially different external semantics.

### 23.2 Retry on Timeout

Rejected because timeout does not prove non-acceptance.

### 23.3 Match by Time, Price, Quantity, and Side

Rejected as deterministic attribution when concurrent or manual orders can collide.

### 23.4 Broker Position as Absolute Truth

Rejected because position may lag, omit pending order effects, or reflect non-trade changes without attribution.

### 23.5 Cancel ACK as Terminal Proof

Rejected because crossing or late fills may remain possible.

### 23.6 Documentation-Only Approval

Rejected because documented behavior may be incomplete, environment-specific, or operationally contradicted.

### 23.7 Sandbox Equivalence

Rejected because sandbox implementation and production controls may differ.

### 23.8 Priority as Guaranteed Protective Reserve

Rejected because shared broker resources can still be exhausted or blocked.

### 23.9 Unsupported Capability with No Scope Reduction

Rejected because implementation difficulty cannot weaken safety properties.

---

## 24. Consequences

### 24.1 Positive

- broker assumptions become explicit and testable;
- unknown-send behavior is deterministic and conservative;
- weaker brokers can be supported only within justified restrictions;
- capability drift causes fail-closed degradation;
- protective reserve claims become honest;
- broker-specific final quantity and reconciliation rules are defined;
- live scope can be approved incrementally.

### 24.2 Negative

- every broker, market, and order type requires separate evidence;
- some integrations may support only restricted serialized live operation;
- throughput and availability may be reduced;
- production verification is operationally costly;
- capability profiles require continuous maintenance;
- broker changes may force immediate suspension.

These costs are accepted because external ambiguity cannot be removed by internal software alone.

---

## 25. Verification and Acceptance Criteria

ADR-002-004 SHALL remain Proposed until the following are demonstrated for each live broker profile.

### BC-AC-001 — Identity and Attribution

Demonstrate deterministic attribution or the approved containment fallback under concurrent, manual, and ambiguous order scenarios.

### BC-AC-002 — Lost Acknowledgement

Drop the submission response after broker acceptance. Verify no blind retry, full reservation retention, and correct reconciliation.

### BC-AC-003 — Duplicate Submission

Where idempotency is claimed, repeat the exact request and prove no second broker order. Where unsupported, prove the adapter refuses retry.

### BC-AC-004 — Fill Before ACK

Deliver fill evidence before acknowledgement. State and capacity must remain correct.

### BC-AC-005 — Duplicate and Out-of-Order Fill

Replay and reorder fills. Confirm idempotent cumulative quantity and no double position transfer.

### BC-AC-006 — Query Omission

Temporarily omit a live order from query results. No capacity may be released.

### BC-AC-007 — Cancel Crossing Fill

Generate a fill concurrent with cancellation. Final quantity and capacity transfer must be correct.

### BC-AC-008 — Late Fill

Deliver a late fill within and beyond the approved observation window. Within-window behavior must be correct; beyond-window behavior must degrade the profile and contain scope.

### BC-AC-009 — Replace

Test atomic and non-atomic replace paths. Verify overlap reservation or protection-gap treatment.

### BC-AC-010 — Reduce-Only or Exit Reversal

Test position changes during exit. The system must not reverse the position under the approved fallback.

### BC-AC-011 — External Activity Detection

Place manual or third-party orders and fills. Detect and contain within the approved bound.

### BC-AC-012 — Polling Under Rate Pressure

Saturate ordinary request budget. Reconciliation must meet its bound or new risk must be denied.

### BC-AC-013 — Protective Request Under Rate Pressure

Demonstrate the stated protective guarantee level. The system must not claim physical reservation when only priority exists.

### BC-AC-014 — Session Failure and Reconnect

Reconnect or replace broker sessions during live-order uncertainty. Identity and retry policy must remain safe.

### BC-AC-015 — Credential Fencing

Prove stale or unauthorized execution identities cannot bypass the final egress path.

### BC-AC-016 — Capability Drift

Inject behavior contradicting the active profile. The dimension must become `CONTRADICTORY` and affected live action must stop.

### BC-AC-017 — Pagination and History Window

Exercise maximum result sets, page boundaries, and day/session transitions. No order may disappear from required reconciliation evidence.

### BC-AC-018 — Position and Margin Conflict

Return conflicting order, fill, position, and margin evidence. Conservative bounds and containment must apply.

### BC-AC-019 — Corporate or Administrative Change

Inject non-trade quantity or identity change. Authority must remain blocked until remap and revaluation complete.

### BC-AC-020 — Environment Isolation

Prove paper/test credentials and endpoints cannot submit to live.

### BC-AC-021 — Profile Version Enforcement

Attempt execution with stale or expired profile version. Broker Adapter must reject it.

### BC-AC-022 — Evidence Replay

Reconstruct each broker decision, fallback, and final quantity conclusion from durable evidence.

---

## 26. Required Metrics and Alerts

At minimum:

- active Broker Capability Profile version;
- capability status and assurance level by dimension;
- profile expiry and next revalidation;
- uncertain transmissions;
- retry attempts allowed and denied;
- attribution ambiguity count;
- open-order query omission duration;
- late-fill latency distribution;
- external-activity detection latency;
- polling and reconciliation bound misses;
- rate-limit utilization by traffic class;
- broker throttling and unknown status codes;
- session reconnect count;
- profile contradiction events;
- egress requests rejected by capability policy;
- Final Quantity Proof pending duration;
- protection-gap duration;
- credential revocation/fencing status.

Critical alerts SHALL fire for:

- duplicate broker order despite claimed idempotency;
- blind retry after uncertain send;
- live transmission using expired or unknown profile;
- capacity release without profile-approved Final Quantity Proof;
- external detection bound miss while new risk remains enabled;
- unexpected broker behavior contradicting a safety-critical dimension;
- test identity reaching live broker path;
- stale credential bypassing egress.

---

## 27. Implementation Constraints

A conforming Broker Adapter SHALL:

- load an immutable approved profile version;
- reject unsupported or stale profile use;
- enforce broker-specific retry and containment policy;
- preserve unknown economic effects;
- record raw and normalized broker evidence;
- handle duplicate and out-of-order events idempotently;
- expose capability status to Safety Authority and Recovery Coordinator;
- prevent generic strategy code from invoking unprofiled broker behavior;
- retain enough evidence to reproduce Final Quantity Proof.

A generic adapter that maps broker status codes into optimistic common states without capability evidence is non-conforming.

---

## 28. Dependencies and Follow-Up Work

This ADR interfaces with:

1. ADR-002-001 — Degraded-Mode Protective Capacity;
2. ADR-002-002 — Aggregate Risk-Capacity Commitment Model;
3. ADR-002-003 — Safety Authority Validity, Epoch Fencing, and Partition Behavior;
4. ADR-002-005 — Intent, Transmission Attempt, Broker Order, and Knowledge State Model;
5. ADR-002-006 — Evidence and Reconciliation Confidence Model;
6. Corporate Actions and Non-Trade State Changes ADR;
7. ADR-002-008 — Trustworthy Time Architecture;
8. VER-002-001 — Safety Authority and Broker Capability Verification Evidence Specification.

Broker-specific profiles are implementation-controlled safety artifacts, not substitutes for this ADR.

---

## 29. Open Implementation Questions

The following must be answered per broker profile before live approval:

1. Does the broker accept and persist a client-generated identity?
2. Can a repeated request create multiple broker orders?
3. What exactly does submission acknowledgement prove?
4. Can fills precede acknowledgement?
5. How are duplicate, out-of-order, corrected, or busted fills represented?
6. What constitutes Final Quantity Proof?
7. How complete are open-order and history queries?
8. What pagination and retention limits exist?
9. What is the external-activity detection bound?
10. Are request limits global, per account, per session, or per endpoint?
11. Can protective and reconciliation traffic have independent broker capacity?
12. Can sessions or credentials be revoked quickly enough for hard fencing?
13. Is reduce-only actually enforced under races?
14. How are corporate actions and symbol remaps exposed?
15. Which production behaviors differ from sandbox?
16. What profile restrictions are necessary for accounts that allow manual HTS activity?

Unanswered questions result in `UNKNOWN` capability status.

---

## 30. Approval Gate

ADR-002-004 may move from **Proposed** to **Accepted** only when:

- the profile schema and governance are implemented;
- at least one broker-specific profile is completed for the intended restricted live scope;
- all minimum live gates are defined;
- uncertain-send fallback is demonstrated;
- broker-specific Final Quantity Proof is demonstrated;
- external-activity and polling bounds are measured;
- rate/session guarantee levels are honestly classified;
- credential and egress fencing are verified;
- all Critical acceptance criteria pass;
- capability drift causes fail-closed behavior;
- VER-002-001 evidence entries are complete and independently reviewed;
- residual risks and scope restrictions are approved.

Until then, broker integrations remain paper, shadow, or explicitly non-production.
