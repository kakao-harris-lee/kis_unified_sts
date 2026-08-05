# Broker Transport Symbol Registry

- **Status:** Non-normative deployment binding record
- **Date:** 2026-08-05
- **Machine source:** `BROKER-TRANSPORT-SYMBOLS.csv`

## 1. Standing

This registry is non-normative. It confers no ADR acceptance, evidence result, or
authorization. It is a deployment binding record, not a specification. The
normative treatment of brokers is the capability-class model in ADR-002-004,
whose concrete per-broker facts belong in a Broker Capability Profile instance —
never in RFC/ADR/GOV/VER text.

Nothing here fences a route, approves a construction site, or claims that any
listed symbol is safe, migrated, or authorized to reach a real broker. The
migration and cutover obligations for the code these symbols appear in stay in
`MIGRATION-CONFORMANCE-REGISTER.csv`.

Both decisions cited in §4 are **Proposed**, not Accepted (`ADR-002-004:3`,
`ADR-002-020:3`). A citation records which normative treatment a symbol is bound
to; it does not import that document's status, and no row here becomes more
authoritative because a cited ADR is later accepted.

## 2. Why this file lives outside `tos-spec/`

This registry names concrete broker classes, so it may not live in the published
corpus. `BROKER-CAPABILITY-PROFILE-template.yaml:20-24` states the rule flatly —
"a filled INSTANCE therefore lives outside tos-spec/ and is never cited as
normative by any RFC/ADR/VER" — backed by `ADR-002-004:798`: facts about a
specific broker "belong to a non-normative Broker Capability Profile instance
produced on the implementation track (§21), not to this normative decision."

`docs/broker-profiles/` is the existing home for exactly that, alongside
`KIS-BROKER-CAPABILITY-PROFILE-draft.yaml`. Placing the registry here also ends
an inconsistency it had while inside `tos-spec/src/`: it was absent from
`SUMMARY.md` and never rendered, so it was an orphan in a published tree whose
placement rule it contradicted.

## 3. What it is for

The corpus is deliberately broker-agnostic, so the concrete class names that
constitute *this* deployment's broker transport binding have no home in a
specification document. They still have to be written down somewhere the reverse
legacy-route census can read, because a census whose vocabulary is compiled into
the checker is exactly the defect the census exists to prevent: a second broker
adapter would be silently invisible to it, the same way a hardcoded
`LEGACY-001..005` range could never discover `LEGACY-006`.

`tools/tos_spec_status.py` therefore derives its scan vocabulary from this file
and hardcodes no symbol of its own. Adding a broker requires editing this
registry, which is a governed, reviewable act — it does not require an edit to
the checker. The checker's tests pin that property in both directions: no
registered broker symbol may appear anywhere in the checker's source, and
registering a further symbol is permitted without a tool edit, while removing or
substituting a registered one is not.

Field discipline follows `MIGRATION-CONFORMANCE-REGISTER.csv`: stable column
order, no empty cells, and semicolons rather than commas inside a cell.

## 4. Registered symbols

| Symbol | Kind | Transport role | Capability reference | Binding rationale | Authority state |
|---|---|---|---|---|---|
| OrderExecutor | ORDER_SENDER | order-submission-and-cancellation | ADR-002-004 (Proposed) §8.1 Order Identity; §8.2 Submission Idempotency; §8.7 Cancellation; ADR-002-020 (Proposed) canonical command construction | Project-native direct broker order sender defined in shared/execution/executor.py; constructing it inside an operator- or service-invocable entrypoint is the F6 blocking condition the reverse census exists to catch | NON_AUTHORIZING_OPEN |
| KISClient | BROKER_CLIENT_READ | broker-session-and-account-read | ADR-002-004 (Proposed) §8.5 Open-Order Query; §8.14 Session and Connection Model; §8.15 Credentials and Authorization | This deployment's concrete broker session/read client defined in shared/kis/client.py; it also backs pure market-data reads so it cannot gate the fail-closed tier without false positives and is reported by the warning tier only | NON_AUTHORIZING_OPEN |

## 5. Column vocabulary

All six columns are defined here. Three are interpreted by the checker, one has
its identifiers resolved by it, and two are prose the checker requires to be
present but does not grade — a checker that graded prose would be manufacturing a
judgement it cannot make.

### 5.1 `symbol` — interpreted

The bare Python class name the census scans for. It must be a bare Python
identifier, and it must resolve to at least one module-level `class` definition
in the same tree the census scans (everything outside `tos/`, `tos-spec/`,
`tests/`, and `test_*.py`/`conftest.py` files). A symbol that denotes nothing
fails the check: without that anchor the registry would be self-attesting, and a
name that exists nowhere in the repository would satisfy every other guard while
the blocking tier enforced a rule about a class that does not exist.

A symbol defined in more than one file is accepted — multiplicity is not evidence
of absence, and rejecting it would assert a uniqueness claim this registry does
not make. A symbol defined *only* in a test or *only* under `tos/` is rejected,
because a symbol the census cannot observe in deployed code is not a transport
binding of this deployment.

### 5.2 `kind` — interpreted

Selects the enforcement tier. The vocabulary is closed and is the checker's own,
not a broker fact:

- `ORDER_SENDER` — the symbol transmits orders. Constructing it in a file that
  also carries a `__main__` entrypoint guard is a blocking failure unless that
  file is a registered `LEGACY_ROUTE` component.
- `BROKER_CLIENT_READ` — the symbol opens a broker session or reads broker state.
  Constructing it outside the register is reported as a non-blocking warning,
  because the same client also serves pure market-data reads and failing on those
  would assert a completeness claim no register makes.

### 5.3 `transport_role` — prose, required

What the symbol does at the transport surface. This column is deliberately *not*
called `capability_class`: the corpus already spends "capability class" twice —
ADR-002-004 §10 *Broker Conformance Classes* (CLASS-A..D), and
`ARCHITECTURE-GATE-STATUS.md:314`'s "Capability class:" for the §13.15 composed
partition-time protective class — and this column is neither of them. It carries
no conformance meaning and gates nothing.

### 5.4 `capability_reference` — identifiers resolved, prose not

The normative treatment the symbol is bound to. Every ADR identifier it names
(`ADR-nnn-nnn`) must resolve to a real document in the corpus, and at least one
must be present. The section numbers and the surrounding prose are **not**
validated: whether a cited section says what the row claims is a review
judgement, not a machine check.

The dimensions these rows cite are ADR-002-004 §8 *Capability Dimensions*. Note
that §13 is the *Fallback Matrix* — what to do when a dimension is absent — and
"Capability Dimension" is defined at §5.2. A row should cite the dimension it is
bound to, not the fallback for its absence.

### 5.5 `binding_rationale` — prose, required

Why this deployment binds this symbol, and what the census does with it. Free
text; required to be non-empty so a row cannot be added without a stated reason.

### 5.6 `authority_state` — interpreted

Uses the register vocabulary and is fixed at `NON_AUTHORIZING_OPEN`: recording a
transport symbol is an observation, and no value of this column can ever make it
an authorization.

## 6. What the census does and does not cover

An unrecognised `kind`, an empty cell, a symbol that is not a bare Python
identifier, a symbol that resolves to no class definition, a cited ADR that does
not exist, a registry with no `ORDER_SENDER` row, an empty registry, a missing
file, or any drift between this table and the CSV all fail the check. The
checker never degrades into scanning for nothing.

The scan is **not** complete, and this register does not claim it is. It matches
a bare `Symbol(` construction only. Dotted or otherwise indirect construction —
`module.OrderExecutor(cfg)`, an aliased import, or a factory that returns an
instance — is not detected, by the same guard that keeps attribute access from
producing false positives. The census is a discovery aid for the F6 defect class,
not a proof that every construction site has been enumerated;
`MIGRATION-CONFORMANCE-REGISTER.csv` records the same limitation in its own terms
at LEGACY-005, by noting that multiple construction callers remain without
enumerating them.
