# Migration and Conformance Register

- **Status:** Non-authorizing current-to-target register
- **Date:** 2026-08-02
- **Machine source:** `MIGRATION-CONFORMANCE-REGISTER.csv`
- **Reverse-census vocabulary:** `docs/broker-profiles/BROKER-TRANSPORT-SYMBOLS.csv` — non-normative deployment binding record, held outside this corpus because it names concrete broker symbols (ADR-002-004:798), listing the transport symbols the §2 census scans for
- **Production Authorization:** NO

## 1. Standing and scope

This is the compact current-to-target view missing from the corpus. It records
legacy order routes, all top-level TOS packages, real versus stand-in authority,
cutover/rollback/double-trade requirements, queued-work invalidation, direct
egress removal, consolidated operator-state ownership, and Proposed safe-removal
criteria for the eight mechanisms whose Complexity Register Q6 is OPEN.

The CSV is canonical. This Markdown explains it; neither file accepts an ADR,
changes evidence, authorizes restricted-live/production, or changes a runtime.
Code/configuration were inspected without starting services or contacting a
broker. “Current” below means repository-designated/configured state; actual
deployment/process state was not observed.

## 2. Current broker-order paths

| ID | Repository path | Reverified state | TOS conformance gap |
|---|---|---|---|
| LEGACY-001 | `services/trading/orchestrator.py` stock | configured project route; deployment not observed | constructs `OrderExecutor` sends outside TOS engine/IAP/RCL/egressgw |
| LEGACY-002 | `services/trading/orchestrator.py` futures | roadmap-designated current monolith; deployment not observed | same direct project sender; not independently approved or RCL-committed |
| LEGACY-003 | `services/order_router/main.py` futures | dormant profile-gated path; live-capable | `PassiveMaker`/KIS adapter/`OrderExecutor` are project controls, not TOS authority |
| LEGACY-004 | `services/stock_order_router/main.py` stock | paper/shadow `VirtualBroker` only | simulation/read-model route; no live authority |
| LEGACY-005 | `shared/execution/executor.py` | common KIS stock/futures sender used by project callers | multiple construction callers remain until a single accepted gateway and route removal proof exist |
| LEGACY-006 | `scripts/trading/flatten_all.py` | operator-invocable CLI; builds a real `KISClient` + `OrderExecutor` and issues per-position market-close orders; `KIS_FUTURES_MARKET` defaults to **real** when unset | direct project send outside TOS engine/IAP/RCL/egressgw; `--confirm` gates only the CLI, while the in-process `flatten_all_async()` seam has no confirm gate (and no wired producer today) |
| LEGACY-007 | `scripts/trading/recover_positions.py` | operator-invocable CLI; builds a real `KISClient` and reads futures balance; **sends no order**; writes a divergence sentinel | reconciliation/resume verdict is a project control, not a TOS Recovery Coordinator or Reconciliation Service; **the sentinel has no consumer** — `services/order_router/main.py` honours only the separate kill-switch sentinel, and the documented `scripts/recover_positions_clear.sh` does not exist |

**LEGACY-006 and LEGACY-007 were previously unregistered** — the F6 failure mode
this register exists to prevent: operator-invocable paths that reach a real
broker with no fence, cutover, rollback, or removal criterion on record.
Registering them changes nothing about their safety. Neither row fences a route,
authorizes an invocation, or claims a cutover or removal is done. Two facts are
recorded because they were verified in code, not to imply they are acceptable:
LEGACY-006 defaults to the **real** market when `KIS_FUTURES_MARKET` is unset,
and LEGACY-007's startup barrier is **unconsumed**, so a divergent broker view
does not in fact block resume and must not be relied on as a fence.

`docker-compose.yml` explicitly requires the futures monolith to be disabled at
F-9 cutover, but an environment switch alone is not sufficient proof. A cutover
must also fence credentials and network routes, bind a new generation, reconcile
all old attempts, and prove no old queued consumer can send.

## 3. TOS package conformance inventory

There are 37 top-level packages under `tos/src/tos` (excluding `__pycache__`).
No package row below is production authority. `READY` and `PASS` are exact
register states at their recorded scope—not package acceptance or live readiness.

| Package | Owning contract | Current implementation level | Registered evidence state | Principal trust seam |
|---|---|---|---|---|
| `afg` | ADR-002-022 | L1 pure predicate substrate | AFG: 4 READY / 8 NOT_IMPLEMENTED | no owning AFG/RCL runtime |
| `are` | ADR-002-021 | L1 pure predicate substrate | ARE: 3 READY / 9 NOT_IMPLEMENTED | injected models; no Aggregate Risk Authority |
| `authority` | ADR-002-003 | L1 pure predicate substrate | SA: 15 NOT_IMPLEMENTED | no leader/epoch/fencing runtime |
| `backtest` | RFC-003/005 D-E3 design | provisional vertical slice | no direct family; closes no EV | synthetic fills and provisional engine |
| `brokeradapter` | ADR-002-013 / RFC-002 §10.8 | provisional synthetic transport | no direct family; closes no EV | no real broker adapter/profile/credential boundary |
| `brokercap` | ADR-002-004 | L1 pure predicate substrate | BC: 22 NOT_IMPLEMENTED | injected/unapproved measured broker profile |
| `canonical` | shared 002/016/018 substrate | shared digest substrate | no direct family | production canonical scheme unresolved |
| `capsule` | ADR-002-018 | L1 pure predicate substrate | CII: 8 READY / 4 NOT_IMPLEMENTED | acquisition continuity and production assembly absent |
| `cur` | ADR-002-024 | L1 pure predicate substrate | CUR: 1 READY / 11 NOT_IMPLEMENTED | no atomic per-send currentness service |
| `dsl` | ADR-DEV-001/003/007 | L1 pure evaluator substrate | DCE: 7 NOT_IMPLEMENTED | typed in-process admission; no real approval/capacity |
| `egress` | ADR-002-013 | L1 pure predicate substrate | EGRESS: 2 READY / 11 NOT_IMPLEMENTED | QCC/security/credential/route enforcement injected |
| `egressgw` | ADR-002-002/013 / RFC-002 §10.8 | provisional vertical slice | no direct family; closes no EV | provisional bounds/stand-ins and synthetic transport |
| `engine` | RFC-003/005 / ADR-002-002 | provisional owning runtime | unit tests only; closes no EV | IAP/ARE/AFG/RCL are non-authoritative stand-ins |
| `evidence` | ADR-002-016 | L1 ledger substrate | ERI: 5 READY / 7 NOT_IMPLEMENTED | provisional storage/commitment and unverified receipt |
| `failuredomain` | ADR-002-009 | L1 coordinate substrate | FD: 12 NOT_IMPLEMENTED | deployment topology/isolation enforcement external |
| `hag` | ADR-002-015 | L1 pure predicate substrate | HAG: 8 READY / 10 NOT_IMPLEMENTED | no Human Authority Service/identity custody |
| `iap` | ADR-002-023 | L1 approval-decision kernel | IAP: 4 READY / 8 NOT_IMPLEMENTED | no independent owning service/recomputation/signer |
| `ioc` | ADR-002-020 | L1 pure predicate substrate | IOC: 3 READY / 9 NOT_IMPLEMENTED | final construction and enforcement runtime external |
| `liveauth` | ADR-002-007 | L1 pure predicate substrate | REARM: 12 NOT_IMPLEMENTED | no Live Armer/registry/epoch/revocation runtime |
| `marketfeed` | ADR-002-018 D-E2 design | provisional value resolver | no direct family; closes no EV | acquisition/continuity/source service absent |
| `nontrade` | ADR-002-028 | L1 pure predicate substrate | NT: 2 READY / 10 NOT_IMPLEMENTED | corporate-action/cash source and owning runtime absent |
| `ordering` | shared 016/008 substrate | shared ordering substrate | no direct family | no global sequencer/trusted coordinate owner |
| `orthostate` | ADR-002-006 | L1 pure state substrate | STATE: 2 READY / 3 NOT_IMPLEMENTED | no authoritative state owner/persistence runtime |
| `posttrade` | ADR-002-030 | L1 pure predicate substrate | PTF: 12 NOT_IMPLEMENTED | no PTOL/settlement/finality authority |
| `protective` | ADR-002-001 | L1 pure predicate substrate | PRD: 1 READY / 1 NOT_IMPLEMENTED | no Protective Controller/classifier/broker runtime |
| `rcl` | ADR-002-002/012 | L1 in-memory predicate substrate | RCLP: 3 READY / 9 NOT_IMPLEMENTED | not durable/linearizable/distributed; no quorum log |
| `recon` | ADR-002-005 | L1 pure predicate substrate | RECON: 5 NOT_IMPLEMENTED | no independent broker-state reconciliation service |
| `replacement` | ADR-002-011 | L1 pure predicate substrate | PR: 2 READY / 10 NOT_IMPLEMENTED | no Cancellation Arbiter/Protective/RCL runtime |
| `rlp` | ADR-002-025 | L1 pure predicate substrate | RLP: 4 READY / 8 NOT_IMPLEMENTED | no human trial authorization/live/evidence runtime |
| `sbr` | ADR-002-017 | L1 pure predicate substrate | SBR: 5 READY / 7 NOT_IMPLEMENTED | no Recovery Coordinator/reconciliation/re-arm runtime |
| `sci` | ADR-002-029 | L1 pure predicate substrate | SCI: 4 READY / 8 NOT_IMPLEMENTED | no build signer/registry/deployment admission runtime |
| `sir` | ADR-002-027 | L1 pure predicate substrate | SIR: 3 READY / 9 NOT_IMPLEMENTED | no incident classifier/containment/finality runtime |
| `spg` | ADR-002-014 | L1 pure predicate substrate | SPG: 7 READY / 1 PASS / 4 NOT_IMPLEMENTED | scoped PASS is not activation; profile service absent |
| `stm` | ADR-002-028 | L1 pure predicate substrate | STM: 2 READY / 10 NOT_IMPLEMENTED | no collector/evaluator/complete source ownership |
| `time` | ADR-002-008 | L1 pure predicate substrate | TIME: 10 NOT_IMPLEMENTED | no trusted clock/synchronization/uncertainty service |
| `venue` | ADR-002-019 | L1 pure predicate substrate | VTG: 2 READY / 10 NOT_IMPLEMENTED | no Venue Authority/calendar/halt/capability runtime |
| `wdr` | ADR-002-026 | L1 pure predicate substrate | WDR: 4 READY / 8 NOT_IMPLEMENTED | no deviation authority/conflict/activation/custody runtime |

## 4. Authority map

| Surface | What is real now | What it is not |
|---|---|---|
| Project monolith/routers | project-side guards, paper models, and live-capable KIS send implementations | Independent Approval, linearizable RCL, accepted TOS gateway, or production authorization |
| `tos.engine` | deterministic provisional wiring and fail-closed sequencing | real independent approver, Aggregate Risk Authority, AFG authority, or RCL |
| `tos.egressgw` + `brokeradapter` | synthetic vertical-slice send boundary | real credential-confined broker egress or KIS evidence |
| CSV evidence registers | current governed row states | ADR acceptance, restricted-live, capital allocation, or production authority |
| dashboards/caches/process health | read models and operational observations | authority, finality, continuity proof, or safety-state ownership |

Real target services remain absent until they are implemented, separately
deployed/owned where required, evidenced, independently reviewed, and activated
by the named human authorities. Relabeling a stand-in does not promote it.

## 5. Cutover, rollback, and direct-egress rules

Every legacy-to-TOS cutover must satisfy all of these before the old route is
removed:

1. **One wallet route:** code/config, credential custody, network policy, and
   startup fencing positively establish one final egress for the exact scope.
2. **No double trade:** monolith, decoupled project path, TOS path, retry worker,
   interactive close, replacement, and recovery paths cannot concurrently send
   the same economic intent.
3. **Queued-work invalidation:** bind a new generation; deny old Redis stream
   entries, consumer pending entries, proposals, approvals, capabilities,
   reservations, scheduled work, retry/cancel/replace work, and recovery tokens.
   Deleting a queue without broker reconciliation is not invalidation proof.
4. **Finality before removal:** reconcile every old attempt, fill, partial fill,
   cancel, bracket/protection, cash/margin effect, and post-trade obligation using
   governed Final Quantity/finality evidence.
5. **Rollback:** pre-register stop rules and return to exactly one fenced route or
   no-new-entry. Rollback does not revive an old authorization/generation and
   preserves protective exits for already-held exposure.
6. **Direct-egress removal:** prove no old sender import/call, credential, endpoint,
   deployment command, scheduled job, interactive path, network route, or
   outstanding work can reach the broker. A disabled flag or quiet process alone
   is insufficient.
7. **Operator state:** the named consolidated owner must show the source-owned
   currentness/generation/degraded state. Conflicts and missing sources are
   explicit and restrictive. The view itself has no command or authorization
   capability.

The exact criteria for each row are in the CSV. No cutover is authorized by this
register.

## 6. Complexity Q5/Q6 remediation

Q5 remains open until `TBD-consolidated-operator-safety-state-owner` is assigned
and an evidenced view covers all eight source mechanisms. The source authority
continues to own each fact; the consolidated view is a freshness- and
generation-bound projection, not a new authority.

Q6 now has **Proposed, non-governing decommission criteria**, not completion:

| ID | Mechanism | Minimum safe-removal condition |
|---|---|---|
| COMPLEXITY-001 | per-send currentness | replacement verifies every final send; all capabilities/sends drained; old proofs fenced; stale/partition evidence passes |
| COMPLEXITY-002 | RCL quorum log | freeze commits; zero unresolved effects; balances/epochs migrated; one replacement writer; quorum/recovery evidence |
| COMPLEXITY-003 | PTOL finality | every obligation settled/transferred/legally expired with proof and retained under a replacement finality authority |
| COMPLEXITY-004 | supply-chain admission | every running/deployable digest admitted by replacement; old keys/admission paths revoked; compromise evidence |
| COMPLEXITY-005 | single egress gateway | all attempts have Final Quantity; accepted replacement and independent containment; old credentials/routes/network paths removed |
| COMPLEXITY-006 | human authority/re-arm | no outstanding approval/delegation/break-glass scope; accepted replacement preserves distinctness/revocation; owner decision |
| COMPLEXITY-007 | recovery barrier | no recovery in progress; all effects reconciled; replacement monotone generation; old recovery tokens denied |
| COMPLEXITY-008 | incident/deviation/monitor fencing | all states/effects closed or transferred; replacements preserve generation floors and reject every stale replay |

These criteria require System Owner/Architecture/Risk and applicable independent
review decisions. They do not authorize removal. Until accepted and evidenced,
all eight Complexity Register Q6 answers remain OPEN.
