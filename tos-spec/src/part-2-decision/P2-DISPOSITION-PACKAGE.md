# P2 Disposition and Owner Decision Package — RFC-003..007

- **Status:** Draft owner decision package — not a ratification record
- **Date:** 2026-08-02
- **Governed by:** GOV-001 G3 P2, G6, and G7
- **Machine source:** `P2-DISPOSITION-REGISTER.csv`
- **Authority:** none; this audit does not amend, de-ratify, or re-ratify an RFC

## 1. Audit verdict

The five canonical Open Questions sections contain 31 numbered questions. RFC-003
marks Q1, Q3, and Q4 resolved in canonical text. The remaining **28 questions**
are carried open: RFC-003 has 3, RFC-004 has 6, RFC-005 has 6, RFC-006 has 7,
and RFC-007 has 6.

RR-0005..RR-0009 do not record one rationale-and-trigger disposition for each of
those 28 questions. Therefore this audit cannot establish GOV-001 G3 P2 for the
existing ratification records. The RFC headers remain Ratified unless and until
the System Owner performs a G6 or G7 act; this package neither silently rewrites
history nor self-ratifies an amendment.

## 2. Line-by-line disposition census

The CSV is authoritative for rationale, trigger, scope restriction, owner, and
decision state. Every source question has exactly one draft disposition.

| Source | Topic | Draft disposition | Named home / owner |
|---|---|---|---|
| RFC-003 Q1 | portfolio vs per-target proposal | resolved in canonical text | RFC-003 §9.1 / System Owner |
| RFC-003 Q2 | evidence granularity | explicitly deferred | ADR-002-016 + ADR-DEV-002 / Evidence Authority |
| RFC-003 Q3 | stochastic/external values | resolved in canonical text; residual classified separately | RFC-003 §10 / System Owner |
| RFC-003 Q4 | no-action vs flat | resolved in canonical text | RFC-003 §9.1 / System Owner |
| RFC-003 Q5 | concrete companion/economic models | explicitly deferred | named model profiles + Economic Viability Profile / Investment Authority |
| RFC-003 Q6 | degraded companion | explicitly deferred | ADR-DEV-008 / Development Architecture Owner |
| RFC-004 Q1 | regime definition | explicitly deferred | Market Regime Profile / Market Model Owner |
| RFC-004 Q2 | shared estimators | explicitly deferred | Estimator Coordination Profile / Market + Risk owners |
| RFC-004 Q3 | VI/price-limit state | explicitly deferred | Market Context Continuity Profile + ADR-002-018/019 / Market Data Owner |
| RFC-004 Q4 | mini/full product model | explicitly deferred | Instrument Model Profile / Market Model Owner |
| RFC-004 Q5 | KRX rule currency | explicitly deferred | Market Rules Source Profile / Market Data Owner |
| RFC-004 Q6 | impact ownership | explicitly deferred | Execution Cost and Impact Profile / Execution + Market owners |
| RFC-005 Q1 | optimizer/slicing method | explicitly deferred | Execution Policy Profile / Execution Model Owner |
| RFC-005 Q2 | execution benchmark | explicitly deferred | Execution Benchmark Profile / Investment + Execution owners |
| RFC-005 Q3 | limited-depth impact | explicitly deferred | Execution Cost and Impact Profile / Execution Model Owner |
| RFC-005 Q4 | call-auction planning | explicitly deferred | Venue-Phase Execution Profile / Execution Model Owner |
| RFC-005 Q5 | retry after UNKNOWN | explicitly deferred | ADR-002-002/022 + Broker Capability Profile / Execution Safety Owner |
| RFC-005 Q6 | shared expectancy costs | explicitly deferred | Cost/Impact + Economic Viability Profiles / Execution + Investment owners |
| RFC-006 Q1 | VaR/ES method | explicitly deferred | Risk Methodology Profile / Risk Authority |
| RFC-006 Q2 | primary tail measure | explicitly deferred | Risk Methodology Profile / Risk Authority |
| RFC-006 Q3 | shared market/risk estimates | explicitly deferred | Estimator Coordination Profile / Market + Risk owners |
| RFC-006 Q4 | portfolio vs sub-limits | explicitly deferred | Investment Mandate and Allocation Profile / Investment + Risk authorities |
| RFC-006 Q5 | drawdown control | explicitly deferred | Drawdown Control Profile / Investment + Risk authorities |
| RFC-006 Q6 | positive-expectancy evidence | explicitly deferred | Economic Viability Profile + ECO-EV / Investment Authority + independent reviewer |
| RFC-006 Q7 | benefit-recognition proofs | explicitly deferred | Benefit Recognition Profile + ADR-002-021 / Risk Authority |
| RFC-007 Q1 | hedge-ratio method | explicitly deferred | Hedge Model Profile / Investment + Hedge owners |
| RFC-007 Q2 | product/rounding/basis | explicitly deferred | Hedge Instrument and Rounding Profile / Hedge + Risk owners |
| RFC-007 Q3 | roll policy | explicitly deferred | Hedge Roll Profile / Hedge + Execution owners |
| RFC-007 Q4 | portfolio proxy | explicitly deferred | Investment Mandate + Hedge Model Profiles / Investment Authority |
| RFC-007 Q5 | overnight residual gap | explicitly deferred | Overnight Residual Risk Decision / Risk + Investment authorities |
| RFC-007 Q6 | hedge benefit proof | explicitly deferred | Benefit Recognition Profile + ADR-002-021 / Risk Authority |

All named profiles above are **Proposed candidate governing artifacts**. Their
names and owners are disposition targets, not approved content. Unknown or
unapproved fields fail closed according to the CSV's scope restriction; no
numeric threshold is supplied here.

## 3. Minimal GOV-001 G6/G7 decision package

The System Owner must choose one path; the default is no act and an open P2
discrepancy.

### Option A — G6 amendment and re-ratification

1. Accept or revise the 31-row census and the 28 proposed deferrals.
2. Amend RFC-003..007 Open Questions so every carried question points to its
   accepted disposition, rationale, trigger, owner, and scope restriction.
3. Increment each material RFC version; run an independent EV-L0 delta review and
   cited-version integrity check.
4. Record five new G5-complete re-ratification records. The records must name the
   old and new versions and may not claim ADR acceptance, evidence PASS, or live
   authority.

Draft record identifiers, reserved only for owner review:

| Draft ID | Target | Decision | Required completion |
|---|---|---|---|
| DRAFT-RR-P2-003 | RFC-003 amendment | PENDING | owner decision + independent review + G5 fields |
| DRAFT-RR-P2-004 | RFC-004 amendment | PENDING | owner decision + independent review + G5 fields |
| DRAFT-RR-P2-005 | RFC-005 amendment | PENDING | owner decision + independent review + G5 fields |
| DRAFT-RR-P2-006 | RFC-006 amendment | PENDING | owner decision + independent review + G5 fields |
| DRAFT-RR-P2-007 | RFC-007 amendment | PENDING | owner decision + independent review + G5 fields |

`DRAFT-*` entries are placeholders, not ratification records, and must not be
copied into the Ratification Records section until the human act occurs.

### Option B — G7 fail-safe de-ratification

The System Owner may de-ratify one or more affected RFCs, record the reason and
scope, and restore a non-authorizing pre-ratification rung until the P2 package is
accepted and re-reviewed. Codex cannot perform this act. De-ratification would
not delete RR-0005..RR-0009; it would add a later dated G7 record.

### Option C — no act yet

Keep the current Ratified headers and historical records unchanged, while the
2026-08-02 audit explicitly reports **P2 NOT ESTABLISHED BY THIS AUDIT**. No
implementation may use the unresolved choice to widen scope. This is the current
default.

## 4. Owner decision gate

Required human inputs:

1. System Owner: choose G6, G7, or no act; accept/revise each draft disposition.
2. Architecture Board: confirm governing homes and citation integrity.
3. Investment/Risk/Evidence authorities: accept ownership of the named profiles
   and evidence gates; provide bounds only through separately approved profiles.
4. Independent reviewer: review the eventual amendment delta before any
   re-ratification record is effective.

Until those acts occur, the register remains a draft audit, the 28 carried
questions remain scope-restricting debt, and no P2-completion claim is permitted.
