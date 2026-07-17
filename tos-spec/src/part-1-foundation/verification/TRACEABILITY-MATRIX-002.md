# TRACEABILITY-MATRIX-002 — Bidirectional Safety Coverage Matrix

- **Date:** 2026-07-17
- **Scope:** RFC-001 SAFE-001..054 (defined requirements) and HAZ-001..025, resolved to VER-002-001 / EVIDENCE-REGISTER-002 evidence families for ADR-002-001 through ADR-002-030.
- **Method:** EVIDENCE-REGISTER-002 records carry no direct evidence→SAFE annotation (the VER-002-001 §10 Traceability Model is not yet instantiated in the register). SAFE→evidence coverage is therefore derived through an ADR bridge: `SAFE → (realizing ADR, each ADR's §22/§2x Requirements Traceability table) → EV-family (register primary_adr)`. HAZ→evidence coverage reuses the verified HAZ→SAFE control mapping (RFC-001 §9 Constitutional-basis and §10 Controlled-by) then the same SAFE→evidence bridge. Per-individual-evidence-item SAFE mapping is not asserted here because it is not present in the source records; inventing it is prohibited. Family-level derivation is the strongest mapping the current sources support.
- **Status:** DERIVED — traceability accounting only. Registration and derivation create no verification evidence, no ADR acceptance, and no live readiness. Register count remains 363; no evidence row was added.

---

## 1. Evidence-Family Legend

Each evidence family's dedicated acceptance rows are owned by one primary ADR (EVIDENCE-REGISTER-002 `primary_adr`). Families realized only by ADRs whose §2x traceability table is absent (see §5) cannot be reached through the ADR bridge.

| Family | Domain | Primary ADR |
|---|---|---|
| AFG-EV | Action Flow Governance | ADR-002-022 |
| ARE-EV | Aggregate Risk Evaluation | ADR-002-021 |
| BC-EV | Broker Capability | ADR-002-004 |
| CII-EV | Critical Input Integrity | ADR-002-018 |
| CUR-EV | Active Currentness | ADR-002-024 |
| EGRESS-EV | Egress Security | ADR-002-013 |
| ERI-EV | Evidence and Replay Integrity | ADR-002-016 |
| FD-EV | Failure Domain | ADR-002-009 |
| HAG-EV | Human Authority Governance | ADR-002-015 |
| IAP-EV | Independent Proposal Approval | ADR-002-023 |
| IOC-EV | Intent-to-Order Conformance | ADR-002-020 |
| NT-EV | Non-Trade Events | ADR-002-010 |
| PR-EV | Protective Replacement | ADR-002-011 |
| PTF-EV | Post-Trade Economic Obligations and Finality | ADR-002-030 |
| RC-EV | Risk Capacity | ADR-002-002 |
| RCLP-EV | RCL Persistence and Consensus | ADR-002-012 |
| REARM-EV | Live Authorization and Re-arm | ADR-002-007 |
| RECON-EV | Reconciliation Confidence | ADR-002-006 |
| RLP-EV | Restricted-Live and Promotion Governance | ADR-002-025 |
| SA-EV | Safety Authority | ADR-002-003 |
| SBR-EV | Safe Startup and Recovery Barrier | ADR-002-017 |
| SCI-EV | Software Supply-Chain and Runtime Artifact Admission | ADR-002-029 |
| SIR-EV | Safety Incident and Controlled Shutdown | ADR-002-027 |
| SPG-EV | Safety Profile Governance | ADR-002-014 |
| STATE-EV | Orthogonal State | ADR-002-005 |
| STM-EV | Safety Telemetry and Continuous Monitoring | ADR-002-028 |
| TIME-EV | Trustworthy Time | ADR-002-008 |
| VTG-EV | Venue and Tradability Gate | ADR-002-019 |
| WDR-EV | Safety Deviation and Residual Risk | ADR-002-026 |
| X-EV | Cross-System | ADR-002-002/003/004 |

---

## 2. SAFE → Evidence Coverage (forward)

ADR column shows the realizing ADR suffixes (ADR-002-0xx) whose Requirements Traceability table claims the SAFE. EV-family column is the union of those ADRs' register families.

| SAFE | Title | Realizing ADR-002-0xx | EV families | Status |
|---|---|---|---|---|
| SAFE-001 | Default Safe State | 001, 023, 024, 027 | CUR, IAP, SIR | COVERED |
| SAFE-002 | No Unmanaged Exposure | 001, 010, 011, 027 | NT, PR, SIR | COVERED |
| SAFE-003 | Fail-Closed Safety Profile | 001, 007, 009, 014, 017, 018, 019, 020, 021, 022, 023, 024, 026, 028, 029 | AFG, ARE, CII, CUR, FD, IAP, IOC, REARM, SBR, SCI, SPG, STM, VTG, WDR | COVERED |
| SAFE-004 | Hard Safety Envelope | 001, 007, 009, 010, 011, 014, 017, 018, 019, 020, 021, 022, 025, 026, 028, 029, 030 | AFG, ARE, CII, FD, IOC, NT, PR, PTF, REARM, RLP, SBR, SCI, SPG, STM, VTG, WDR | COVERED |
| SAFE-010 | Pre-Trade Safety Authorization | 012, 013, 014, 015, 016, 017, 018, 019, 020, 021, 022, 023, 024, 025, 026, 027, 028, 029, 030 | AFG, ARE, CII, CUR, EGRESS, ERI, HAG, IAP, IOC, PTF, RCLP, RLP, SBR, SCI, SIR, SPG, STM, VTG, WDR | COVERED |
| SAFE-011 | Non-Bypassable Safety Limits | 001, 007, 009, 010, 011, 012, 013, 014, 015, 016, 017, 018, 019, 020, 022, 023, 024, 025, 026, 027, 028, 029, 030 | AFG, CII, CUR, EGRESS, ERI, FD, HAG, IAP, IOC, NT, PR, PTF, RCLP, REARM, RLP, SBR, SCI, SIR, SPG, STM, VTG, WDR | COVERED |
| SAFE-012 | Bounded Single-Action Risk | 021, 022, 025, 026, 030 | AFG, ARE, PTF, RLP, WDR | COVERED |
| SAFE-013 | Aggregate Risk Authority | 001, 007, 009, 010, 011, 012, 014, 017, 018, 019, 020, 021, 022, 023, 024, 025, 027, 028, 029, 030 | AFG, ARE, CII, CUR, FD, IAP, IOC, NT, PR, PTF, RCLP, REARM, RLP, SBR, SCI, SIR, SPG, STM, VTG | COVERED |
| SAFE-014 | Bounded Action Rate | 001, 013, 021, 022, 027, 029, 030 | AFG, ARE, EGRESS, PTF, SCI, SIR | COVERED |
| SAFE-015 | Exclusive Risk-Capacity Commitment | 001, 007, 009, 010, 011, 012, 013, 017, 018, 019, 020, 021, 022, 023, 024, 025, 026, 028, 030 | AFG, ARE, CII, CUR, EGRESS, FD, IAP, IOC, NT, PR, PTF, RCLP, REARM, RLP, SBR, STM, VTG, WDR | COVERED |
| SAFE-020 | Immutable Intent Identity | 010, 011, 016, 017, 018, 019, 020, 021, 022, 023, 024, 030 | AFG, ARE, CII, CUR, ERI, IAP, IOC, NT, PR, PTF, SBR, VTG | COVERED |
| SAFE-021 | At-Most-One Exposure Effect | 001, 007, 009, 011, 012, 013, 016, 017, 018, 020, 021, 022, 023, 024, 025, 026, 027, 030 | AFG, ARE, CII, CUR, EGRESS, ERI, FD, IAP, IOC, PR, PTF, RCLP, REARM, RLP, SBR, SIR, WDR | COVERED |
| SAFE-022 | Reconciliation Before Exposure | 007, 009, 010, 011, 016, 017, 018, 024, 028, 030 | CII, CUR, ERI, FD, NT, PR, PTF, REARM, SBR, STM | COVERED |
| SAFE-023 | Evidence-Based State Validation | 010, 011, 016, 017, 026 | ERI, NT, PR, SBR, WDR | COVERED |
| SAFE-024 | Continuous External-State Reconciliation | 001, 007, 009, 010, 012, 013, 016, 017, 020, 021, 022, 025 | AFG, ARE, EGRESS, ERI, FD, IOC, NT, RCLP, REARM, RLP, SBR | COVERED |
| SAFE-025 | Partial and Asynchronous Fill Integrity | 001, 007, 010, 011, 016, 017, 018, 019, 020, 021, 022, 024, 025, 026, 027, 028, 030 | AFG, ARE, CII, CUR, ERI, IOC, NT, PR, PTF, REARM, RLP, SBR, SIR, STM, VTG, WDR | COVERED |
| SAFE-030 | Trustworthy Context Precondition | 008, 009, 010, 016, 017, 018, 019, 020, 021, 022, 023, 024, 028, 029, 030 | AFG, ARE, CII, CUR, ERI, FD, IAP, IOC, NT, PTF, SBR, SCI, STM, TIME, VTG | COVERED |
| SAFE-031 | Critical Input Provenance | 008, 009, 016, 018, 019, 021, 022, 023, 028, 029, 030 | AFG, ARE, CII, ERI, FD, IAP, PTF, SCI, STM, TIME, VTG | COVERED |
| SAFE-032 | Venue and Tradability Gate | 010, 011, 018, 019, 020, 022, 023, 030 | AFG, CII, IAP, IOC, NT, PR, PTF, VTG | COVERED |
| SAFE-033 | Intent-to-Order Conformance | 013, 018, 019, 020, 022, 023, 029, 030 | AFG, CII, EGRESS, IAP, IOC, PTF, SCI, VTG | COVERED |
| SAFE-034 | Independent Approval Inputs | 015, 018, 019, 020, 021, 022, 023, 026, 029, 030 | AFG, ARE, CII, HAG, IAP, IOC, PTF, SCI, VTG, WDR | COVERED |
| SAFE-035 | Trustworthy Time Basis | 001, 007, 008, 009, 010, 014, 015, 016, 017, 018, 019, 020, 021, 022, 023, 024, 025, 026, 028, 029, 030 | AFG, ARE, CII, CUR, ERI, FD, HAG, IAP, IOC, NT, PTF, REARM, RLP, SBR, SCI, SPG, STM, TIME, VTG, WDR | COVERED |
| SAFE-040 | Protective Control in Degraded Operation | 001, 010, 011, 013, 017, 018, 019, 020, 021, 022, 023, 024, 027, 028, 030 | AFG, ARE, CII, CUR, EGRESS, IAP, IOC, NT, PR, PTF, SBR, SIR, STM, VTG | COVERED |
| SAFE-041 | Independent Safety Authority | 001, 007, 009, 010, 011, 012, 013, 014, 015, 016, 017, 018, 019, 020, 021, 022, 023, 025, 026, 029 | AFG, ARE, CII, EGRESS, ERI, FD, HAG, IAP, IOC, NT, PR, RCLP, REARM, RLP, SBR, SCI, SPG, VTG, WDR | COVERED |
| SAFE-042 | Human Emergency Authority | 007, 013, 015, 017, 022, 026 | AFG, EGRESS, HAG, REARM, SBR, WDR | COVERED |
| SAFE-043 | Exit-Unavailable Containment | 001, 011, 017, 019, 020, 021, 022, 023, 024, 027 | AFG, ARE, CUR, IAP, IOC, PR, SBR, SIR, VTG | COVERED |
| SAFE-044 | Safe Start and Resume | 001, 007, 008, 009, 010, 016, 017, 018, 019, 020, 021, 022, 023, 024, 025, 026, 027, 028, 029, 030 | AFG, ARE, CII, CUR, ERI, FD, IAP, IOC, NT, PTF, REARM, RLP, SBR, SCI, SIR, STM, TIME, VTG, WDR | COVERED |
| SAFE-045 | Live and Non-Live Segregation | 007, 009, 013, 014, 015, 016, 017, 025, 026, 027, 028, 029 | EGRESS, ERI, FD, HAG, REARM, RLP, SBR, SCI, SIR, SPG, STM, WDR | COVERED |
| SAFE-046 | Explicit Live Arming | 007, 013, 014, 015, 017, 018, 019, 020, 022, 025, 026, 029 | AFG, CII, EGRESS, HAG, IOC, REARM, RLP, SBR, SCI, SPG, VTG, WDR | COVERED |
| SAFE-047 | Production Scope Confinement | 007, 013, 014, 015, 017, 025, 026, 027, 029 | EGRESS, HAG, REARM, RLP, SBR, SCI, SIR, SPG, WDR | COVERED |
| SAFE-048 | Partition-Tolerant Safety Authority | 001, 007, 008, 009, 010, 011, 012, 013, 014, 015, 016, 017, 018, 019, 020, 021, 022, 023, 024, 025, 026, 027, 028, 029, 030 | AFG, ARE, CII, CUR, EGRESS, ERI, FD, HAG, IAP, IOC, NT, PR, PTF, RCLP, REARM, RLP, SBR, SCI, SIR, SPG, STM, TIME, VTG, WDR | COVERED |
| SAFE-050 | Safety Configuration Governance | 001, 007, 008, 009, 010, 014, 015, 016, 017, 018, 019, 020, 021, 022, 023, 024, 025, 026, 027, 028, 029, 030 | AFG, ARE, CII, CUR, ERI, FD, HAG, IAP, IOC, NT, PTF, REARM, RLP, SBR, SCI, SIR, SPG, STM, TIME, VTG, WDR | COVERED |
| SAFE-051 | Decision and Execution Evidence | 001, 007, 008, 009, 010, 011, 012, 013, 014, 015, 016, 017, 018, 019, 020, 021, 022, 023, 024, 025, 026, 027, 028, 029, 030 | AFG, ARE, CII, CUR, EGRESS, ERI, FD, HAG, IAP, IOC, NT, PR, PTF, RCLP, REARM, RLP, SBR, SCI, SIR, SPG, STM, TIME, VTG, WDR | COVERED |
| SAFE-052 | Replay and Incident Reconstruction | 007, 008, 009, 010, 011, 012, 013, 014, 015, 016, 017, 018, 019, 020, 021, 022, 023, 024, 025, 026, 027, 028, 029, 030 | AFG, ARE, CII, CUR, EGRESS, ERI, FD, HAG, IAP, IOC, NT, PR, PTF, RCLP, REARM, RLP, SBR, SCI, SIR, SPG, STM, TIME, VTG, WDR | COVERED |
| SAFE-053 | Independent Approval of Risk-Increasing Re-Arm and Scope Promotion | 015 | UNMAPPED | UNMAPPED — evidence debt (gate-status §4.2) |
| SAFE-054 | Out-of-Band Containment of Final Egress | — | UNMAPPED | UNMAPPED — evidence debt (gate-status §4.3) |

---

## 3. HAZ → SAFE → Evidence Coverage (forward)

SAFE control set from RFC-001 §9 Constitutional-basis / §10 Controlled-by. EV families are the union of the controlling SAFEs' families (§2); UNMAPPED controlling SAFEs are carried as debt.

| HAZ | Title | Controlling SAFE | EV families | Status |
|---|---|---|---|---|
| HAZ-001 | Permanent Capital Impairment | SAFE-010, SAFE-012, SAFE-013, SAFE-042 | AFG, ARE, CII, CUR, EGRESS, ERI, FD, HAG, IAP, IOC, NT, PR, PTF, RCLP, REARM, RLP, SBR, SCI, SIR, SPG, STM, VTG, WDR | COVERED |
| HAZ-002 | Unbounded Loss or Exposure | SAFE-010, SAFE-011, SAFE-012, SAFE-013, SAFE-014 | AFG, ARE, CII, CUR, EGRESS, ERI, FD, HAG, IAP, IOC, NT, PR, PTF, RCLP, REARM, RLP, SBR, SCI, SIR, SPG, STM, VTG, WDR | COVERED |
| HAZ-003 | Limit-Breaching Action | SAFE-010, SAFE-011, SAFE-012 | AFG, ARE, CII, CUR, EGRESS, ERI, FD, HAG, IAP, IOC, NT, PR, PTF, RCLP, REARM, RLP, SBR, SCI, SIR, SPG, STM, VTG, WDR | COVERED |
| HAZ-004 | Duplicate Exposure | SAFE-020, SAFE-021, SAFE-022 | AFG, ARE, CII, CUR, EGRESS, ERI, FD, IAP, IOC, NT, PR, PTF, RCLP, REARM, RLP, SBR, SIR, STM, VTG, WDR | COVERED |
| HAZ-005 | Runaway Action Rate | SAFE-014, SAFE-042 | AFG, ARE, EGRESS, HAG, PTF, REARM, SBR, SCI, SIR, WDR | COVERED |
| HAZ-006 | Trading on Untrustworthy Context | SAFE-030, SAFE-031, SAFE-033 | AFG, ARE, CII, CUR, EGRESS, ERI, FD, IAP, IOC, NT, PTF, SBR, SCI, STM, TIME, VTG | COVERED |
| HAZ-007 | Trading Into an Unavailable or Restricted Venue | SAFE-032, SAFE-043 | AFG, ARE, CII, CUR, IAP, IOC, NT, PR, PTF, SBR, SIR, VTG | COVERED |
| HAZ-008 | Unmanaged Exposure in a Degraded State | SAFE-002, SAFE-040, SAFE-043 | AFG, ARE, CII, CUR, EGRESS, IAP, IOC, NT, PR, PTF, SBR, SIR, STM, VTG | COVERED |
| HAZ-009 | Trading Before Reconciliation | SAFE-022, SAFE-044 | AFG, ARE, CII, CUR, ERI, FD, IAP, IOC, NT, PR, PTF, REARM, RLP, SBR, SCI, SIR, STM, TIME, VTG, WDR | COVERED |
| HAZ-010 | Loss of Containment Authority | SAFE-041, SAFE-042, SAFE-050 | AFG, ARE, CII, CUR, EGRESS, ERI, FD, HAG, IAP, IOC, NT, PR, PTF, RCLP, REARM, RLP, SBR, SCI, SIR, SPG, STM, TIME, VTG, WDR | COVERED |
| HAZ-011 | Fail-Open Safety Configuration | SAFE-003, SAFE-011, SAFE-050 | AFG, ARE, CII, CUR, EGRESS, ERI, FD, HAG, IAP, IOC, NT, PR, PTF, RCLP, REARM, RLP, SBR, SCI, SIR, SPG, STM, TIME, VTG, WDR | COVERED |
| HAZ-012 | Live and Non-Live Crossover | SAFE-045, SAFE-046, SAFE-047 | AFG, CII, EGRESS, ERI, FD, HAG, IOC, REARM, RLP, SBR, SCI, SIR, SPG, STM, VTG, WDR | COVERED |
| HAZ-013 | Aggregate Risk Accumulation | SAFE-013 | AFG, ARE, CII, CUR, FD, IAP, IOC, NT, PR, PTF, RCLP, REARM, RLP, SBR, SCI, SIR, SPG, STM, VTG | COVERED |
| HAZ-014 | Intent-to-Order Corruption | SAFE-033, SAFE-034 | AFG, ARE, CII, EGRESS, HAG, IAP, IOC, PTF, SCI, VTG, WDR | COVERED |
| HAZ-015 | Audit Mistaken for Prevention | SAFE-010, SAFE-051, SAFE-052 | AFG, ARE, CII, CUR, EGRESS, ERI, FD, HAG, IAP, IOC, NT, PR, PTF, RCLP, REARM, RLP, SBR, SCI, SIR, SPG, STM, TIME, VTG, WDR | COVERED |
| HAZ-016 | Time-Source Corruption | SAFE-035, SAFE-030, SAFE-044, SAFE-046, SAFE-050 | AFG, ARE, CII, CUR, EGRESS, ERI, FD, HAG, IAP, IOC, NT, PTF, REARM, RLP, SBR, SCI, SIR, SPG, STM, TIME, VTG, WDR | COVERED |
| HAZ-017 | Authoritative-State Corruption | SAFE-023, SAFE-022, SAFE-024, SAFE-025 | AFG, ARE, CII, CUR, EGRESS, ERI, FD, IOC, NT, PR, PTF, RCLP, REARM, RLP, SBR, SIR, STM, VTG, WDR | COVERED |
| HAZ-018 | Containment Isolation | SAFE-041, SAFE-048 | AFG, ARE, CII, CUR, EGRESS, ERI, FD, HAG, IAP, IOC, NT, PR, PTF, RCLP, REARM, RLP, SBR, SCI, SIR, SPG, STM, TIME, VTG, WDR | COVERED |
| HAZ-019 | Semantically Invalid Safety Profile | SAFE-003, SAFE-004, SAFE-012, SAFE-013, SAFE-050 | AFG, ARE, CII, CUR, ERI, FD, HAG, IAP, IOC, NT, PR, PTF, RCLP, REARM, RLP, SBR, SCI, SIR, SPG, STM, TIME, VTG, WDR | COVERED |
| HAZ-020 | Concurrent Risk-Capacity Oversubscription | SAFE-013, SAFE-015, SAFE-021 | AFG, ARE, CII, CUR, EGRESS, ERI, FD, IAP, IOC, NT, PR, PTF, RCLP, REARM, RLP, SBR, SCI, SIR, SPG, STM, VTG, WDR | COVERED |
| HAZ-021 | Unattributed External Exposure | SAFE-023, SAFE-024, SAFE-044 | AFG, ARE, CII, CUR, EGRESS, ERI, FD, IAP, IOC, NT, PR, PTF, RCLP, REARM, RLP, SBR, SCI, SIR, STM, TIME, VTG, WDR | COVERED |
| HAZ-022 | Partial-Fill State Corruption | SAFE-021, SAFE-022, SAFE-025, SAFE-043, SAFE-051 | AFG, ARE, CII, CUR, EGRESS, ERI, FD, HAG, IAP, IOC, NT, PR, PTF, RCLP, REARM, RLP, SBR, SCI, SIR, SPG, STM, TIME, VTG, WDR | COVERED |
| HAZ-023 | Trapped-Exposure Compounding | SAFE-013, SAFE-032, SAFE-043 | AFG, ARE, CII, CUR, FD, IAP, IOC, NT, PR, PTF, RCLP, REARM, RLP, SBR, SCI, SIR, SPG, STM, VTG | COVERED |
| HAZ-024 | Operator/Human Configuration or Authorization Error | SAFE-042, SAFE-046, SAFE-050, SAFE-053 | AFG, ARE, CII, CUR, EGRESS, ERI, FD, HAG, IAP, IOC, NT, PTF, REARM, RLP, SBR, SCI, SIR, SPG, STM, TIME, VTG, WDR | COVERED (partial); SAFE-053 UNMAPPED debt |
| HAZ-025 | Defect or Compromise of the Final Egress Enforcement Point | SAFE-041, SAFE-048, SAFE-054 | AFG, ARE, CII, CUR, EGRESS, ERI, FD, HAG, IAP, IOC, NT, PR, PTF, RCLP, REARM, RLP, SBR, SCI, SIR, SPG, STM, TIME, VTG, WDR | COVERED (partial); SAFE-054 UNMAPPED debt |

---

## 4. Reverse Index — Evidence family → SAFE(s)

Derived reverse of §2 (family appears for a SAFE when the family's primary ADR claims that SAFE in its traceability table).

| Family | SAFE requirements reached |
|---|---|
| AFG-EV | SAFE-003, SAFE-004, SAFE-010, SAFE-011, SAFE-012, SAFE-013, SAFE-014, SAFE-015, SAFE-020, SAFE-021, SAFE-024, SAFE-025, SAFE-030, SAFE-031, SAFE-032, SAFE-033, SAFE-034, SAFE-035, SAFE-040, SAFE-041, SAFE-042, SAFE-043, SAFE-044, SAFE-046, SAFE-048, SAFE-050, SAFE-051, SAFE-052 |
| ARE-EV | SAFE-003, SAFE-004, SAFE-010, SAFE-012, SAFE-013, SAFE-014, SAFE-015, SAFE-020, SAFE-021, SAFE-024, SAFE-025, SAFE-030, SAFE-031, SAFE-034, SAFE-035, SAFE-040, SAFE-041, SAFE-043, SAFE-044, SAFE-048, SAFE-050, SAFE-051, SAFE-052 |
| BC-EV | — (none via bridge) |
| CII-EV | SAFE-003, SAFE-004, SAFE-010, SAFE-011, SAFE-013, SAFE-015, SAFE-020, SAFE-021, SAFE-022, SAFE-025, SAFE-030, SAFE-031, SAFE-032, SAFE-033, SAFE-034, SAFE-035, SAFE-040, SAFE-041, SAFE-044, SAFE-046, SAFE-048, SAFE-050, SAFE-051, SAFE-052 |
| CUR-EV | SAFE-001, SAFE-003, SAFE-010, SAFE-011, SAFE-013, SAFE-015, SAFE-020, SAFE-021, SAFE-022, SAFE-025, SAFE-030, SAFE-035, SAFE-040, SAFE-043, SAFE-044, SAFE-048, SAFE-050, SAFE-051, SAFE-052 |
| EGRESS-EV | SAFE-010, SAFE-011, SAFE-014, SAFE-015, SAFE-021, SAFE-024, SAFE-033, SAFE-040, SAFE-041, SAFE-042, SAFE-045, SAFE-046, SAFE-047, SAFE-048, SAFE-051, SAFE-052 |
| ERI-EV | SAFE-010, SAFE-011, SAFE-020, SAFE-021, SAFE-022, SAFE-023, SAFE-024, SAFE-025, SAFE-030, SAFE-031, SAFE-035, SAFE-041, SAFE-044, SAFE-045, SAFE-048, SAFE-050, SAFE-051, SAFE-052 |
| FD-EV | SAFE-003, SAFE-004, SAFE-011, SAFE-013, SAFE-015, SAFE-021, SAFE-022, SAFE-024, SAFE-030, SAFE-031, SAFE-035, SAFE-041, SAFE-044, SAFE-045, SAFE-048, SAFE-050, SAFE-051, SAFE-052 |
| HAG-EV | SAFE-010, SAFE-011, SAFE-034, SAFE-035, SAFE-041, SAFE-042, SAFE-045, SAFE-046, SAFE-047, SAFE-048, SAFE-050, SAFE-051, SAFE-052 |
| IAP-EV | SAFE-001, SAFE-003, SAFE-010, SAFE-011, SAFE-013, SAFE-015, SAFE-020, SAFE-021, SAFE-030, SAFE-031, SAFE-032, SAFE-033, SAFE-034, SAFE-035, SAFE-040, SAFE-041, SAFE-043, SAFE-044, SAFE-048, SAFE-050, SAFE-051, SAFE-052 |
| IOC-EV | SAFE-003, SAFE-004, SAFE-010, SAFE-011, SAFE-013, SAFE-015, SAFE-020, SAFE-021, SAFE-024, SAFE-025, SAFE-030, SAFE-032, SAFE-033, SAFE-034, SAFE-035, SAFE-040, SAFE-041, SAFE-043, SAFE-044, SAFE-046, SAFE-048, SAFE-050, SAFE-051, SAFE-052 |
| NT-EV | SAFE-002, SAFE-004, SAFE-011, SAFE-013, SAFE-015, SAFE-020, SAFE-022, SAFE-023, SAFE-024, SAFE-025, SAFE-030, SAFE-032, SAFE-035, SAFE-040, SAFE-041, SAFE-044, SAFE-048, SAFE-050, SAFE-051, SAFE-052 |
| PR-EV | SAFE-002, SAFE-004, SAFE-011, SAFE-013, SAFE-015, SAFE-020, SAFE-021, SAFE-022, SAFE-023, SAFE-025, SAFE-032, SAFE-040, SAFE-041, SAFE-043, SAFE-048, SAFE-051, SAFE-052 |
| PTF-EV | SAFE-004, SAFE-010, SAFE-011, SAFE-012, SAFE-013, SAFE-014, SAFE-015, SAFE-020, SAFE-021, SAFE-022, SAFE-025, SAFE-030, SAFE-031, SAFE-032, SAFE-033, SAFE-034, SAFE-035, SAFE-040, SAFE-044, SAFE-048, SAFE-050, SAFE-051, SAFE-052 |
| RC-EV | — (none via bridge) |
| RCLP-EV | SAFE-010, SAFE-011, SAFE-013, SAFE-015, SAFE-021, SAFE-024, SAFE-041, SAFE-048, SAFE-051, SAFE-052 |
| REARM-EV | SAFE-003, SAFE-004, SAFE-011, SAFE-013, SAFE-015, SAFE-021, SAFE-022, SAFE-024, SAFE-025, SAFE-035, SAFE-041, SAFE-042, SAFE-044, SAFE-045, SAFE-046, SAFE-047, SAFE-048, SAFE-050, SAFE-051, SAFE-052 |
| RECON-EV | — (none via bridge) |
| RLP-EV | SAFE-004, SAFE-010, SAFE-011, SAFE-012, SAFE-013, SAFE-015, SAFE-021, SAFE-024, SAFE-025, SAFE-035, SAFE-041, SAFE-044, SAFE-045, SAFE-046, SAFE-047, SAFE-048, SAFE-050, SAFE-051, SAFE-052 |
| SA-EV | — (none via bridge) |
| SBR-EV | SAFE-003, SAFE-004, SAFE-010, SAFE-011, SAFE-013, SAFE-015, SAFE-020, SAFE-021, SAFE-022, SAFE-023, SAFE-024, SAFE-025, SAFE-030, SAFE-035, SAFE-040, SAFE-041, SAFE-042, SAFE-043, SAFE-044, SAFE-045, SAFE-046, SAFE-047, SAFE-048, SAFE-050, SAFE-051, SAFE-052 |
| SCI-EV | SAFE-003, SAFE-004, SAFE-010, SAFE-011, SAFE-013, SAFE-014, SAFE-030, SAFE-031, SAFE-033, SAFE-034, SAFE-035, SAFE-041, SAFE-044, SAFE-045, SAFE-046, SAFE-047, SAFE-048, SAFE-050, SAFE-051, SAFE-052 |
| SIR-EV | SAFE-001, SAFE-002, SAFE-010, SAFE-011, SAFE-013, SAFE-014, SAFE-021, SAFE-025, SAFE-040, SAFE-043, SAFE-044, SAFE-045, SAFE-047, SAFE-048, SAFE-050, SAFE-051, SAFE-052 |
| SPG-EV | SAFE-003, SAFE-004, SAFE-010, SAFE-011, SAFE-013, SAFE-035, SAFE-041, SAFE-045, SAFE-046, SAFE-047, SAFE-048, SAFE-050, SAFE-051, SAFE-052 |
| STATE-EV | — (none via bridge) |
| STM-EV | SAFE-003, SAFE-004, SAFE-010, SAFE-011, SAFE-013, SAFE-015, SAFE-022, SAFE-025, SAFE-030, SAFE-031, SAFE-035, SAFE-040, SAFE-044, SAFE-045, SAFE-048, SAFE-050, SAFE-051, SAFE-052 |
| TIME-EV | SAFE-030, SAFE-031, SAFE-035, SAFE-044, SAFE-048, SAFE-050, SAFE-051, SAFE-052 |
| VTG-EV | SAFE-003, SAFE-004, SAFE-010, SAFE-011, SAFE-013, SAFE-015, SAFE-020, SAFE-025, SAFE-030, SAFE-031, SAFE-032, SAFE-033, SAFE-034, SAFE-035, SAFE-040, SAFE-041, SAFE-043, SAFE-044, SAFE-046, SAFE-048, SAFE-050, SAFE-051, SAFE-052 |
| WDR-EV | SAFE-003, SAFE-004, SAFE-010, SAFE-011, SAFE-012, SAFE-015, SAFE-021, SAFE-023, SAFE-025, SAFE-034, SAFE-035, SAFE-041, SAFE-042, SAFE-044, SAFE-045, SAFE-046, SAFE-047, SAFE-048, SAFE-050, SAFE-051, SAFE-052 |
| X-EV | — (none via bridge) |

---

## 5. UNMAPPED Entries and Source Gaps

### 5.1 UNMAPPED SAFE requirements (accepted evidence debt)

| SAFE | Reason | Debt record |
|---|---|---|
| SAFE-053 | Independent-approval re-arm/promotion evidence (HAG-INV-015..019, prospective HAG-EV-013) not yet registered; the generic HAG-EV family does not carry a dedicated SAFE-053 acceptance row. | ARCHITECTURE-GATE-STATUS §4.2 |
| SAFE-054 | Out-of-band final-egress containment evidence not yet registered; capability-neutral, established in Broker Capability Profile terms. | ARCHITECTURE-GATE-STATUS §4.3 |

### 5.2 UNMAPPED HAZ (accepted evidence debt)

HAZ-024 and HAZ-025 obtain partial coverage from their non-debt controlling SAFEs (§3), but their dedicated coverage rides on SAFE-053 and SAFE-054 respectively, which are UNMAPPED evidence debt (§5.1). No dedicated register row was added; the count remains 363. See ARCHITECTURE-GATE-STATUS §4.3 (HAZ-024/HAZ-025) and §4.2 (SAFE-053).

### 5.3 Source gaps — ADRs without a Requirements Traceability table

The following ADRs declare no §2x Requirements Traceability table, so their evidence families (RC, SA, BC, STATE, RECON) are not reachable through the SAFE→ADR bridge even though the families exist in the register. This is a source-document gap, not an absence of evidence; the affected SAFE→family links are recovered elsewhere in this matrix through other realizing ADRs where a SAFE is co-claimed.

| ADR | Evidence family | Note |
|---|---|---|
| ADR-002-002 | RC-EV | No §2x Requirements Traceability table in source; add one in the Part-2/3 consolidation wave. |
| ADR-002-003 | SA-EV | No §2x Requirements Traceability table in source; add one in the Part-2/3 consolidation wave. |
| ADR-002-004 | BC-EV | No §2x Requirements Traceability table in source; add one in the Part-2/3 consolidation wave. |
| ADR-002-005 | STATE-EV | No §2x Requirements Traceability table in source; add one in the Part-2/3 consolidation wave. |
| ADR-002-006 | RECON-EV | No §2x Requirements Traceability table in source; add one in the Part-2/3 consolidation wave. |

---

## 6. Coverage Summary

- Defined SAFE requirements: 36; COVERED via ADR bridge: 34; UNMAPPED (evidence debt): 2 (SAFE-053, SAFE-054).
- Defined hazards: 25; every hazard resolves to ≥1 evidence family or is recorded as accepted evidence debt.
- ADRs with a Requirements Traceability table: 25/30; source gaps: 5 (ADR-002-002, ADR-002-003, ADR-002-004, ADR-002-005, ADR-002-006).
- This matrix is the instantiated bidirectional coverage matrix referenced by VER-002-001 §383. It changes no ADR status and adds no evidence row (register count 363).

