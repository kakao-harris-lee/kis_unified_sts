# GOV-001 — Ratification and Change Governance

**Document ID:** GOV-001
**Title:** Ratification and Change Governance
**Version:** 0.1 Review Draft
**Status:** Review Draft — Not Ratified
**Classification:** Governance Process Specification
**Authority:** Derived from RFC-000 §13 (Engineering Governance); process-normative, content-inert
**Owner:** Trading Operating System Architecture Board
**Governed By:** RFC-000

---

## 1. Purpose and Authority

This document is the approved governance process delegated by RFC-000 §13. It derives its authority from RFC-000 and specifies the process by which corpus documents attain, retain, and lose status, and the procedure for amending RFC-000 under §18. GOV-001 does not sit in the RFC-000 §12 content-governance hierarchy and SHALL NOT govern, widen, relax, or reinterpret the safety content, authority, limit, gate, or Hard Safety Envelope constraint of any document. Where GOV-001 conflicts with RFC-000, RFC-000 governs.

---

## 2. The Three Governance Acts

G1. Ratification, ADR acceptance, and live authorization are distinct acts. **Document ratification** establishes an exact document version as the governing baseline; it is the terminal state of the authoring track, is independent of verification-evidence execution, and SHALL confer no live authorization, no ADR acceptance, no capacity, and no transmission authority. **ADR acceptance** — the acceptance decision itself — is governed by the EVIDENCE-REGISTER-002 Gate Rule and VER-002-001 §380; GOV-001 adds only the status-ordering precondition of G2 (the Architecture RFC the ADR refines is Ratified) and alters no acceptance evidence criterion. **Live authorization** is governed by ADR-002-007, ADR-002-025, RFC-001 SAFE-053, and every other live-authorization control identified by RFC-001 and the ADR-002 tier. Ratification is a precondition for acceptance and for live authorization; it SHALL NOT substitute for either.

---

## 3. Status Ladder

G2. A normative RFC-class document SHALL occupy exactly one of: Working Draft, Review Draft, Ratification-Ready, or Ratified. An Architecture Decision Record SHALL NOT enter this ladder; it occupies Proposed or Accepted only, and SHALL NOT move to Accepted unless the Architecture RFC it refines is Ratified. A Verification Evidence specification SHALL NOT be ratified; it moves from Proposed to Approved for Execution under its own approval gate (VER-002-001 §383; VER-DEV-001 §8). vision and philosophy SHALL NOT be ratified; the System Owner MAY record their accepted directional baseline by Baseline Adoption (§7), which modifies neither document. A process-normative governance specification — GOV-001 itself — follows the RFC-class status ladder for its own status while remaining outside the RFC-000 §12 content hierarchy; its own ratification follows the process defined here, a controlled self-reference recorded in its ratification record.

---

## 4. Ratification-Ready Preconditions

G3. A document is Ratification-Ready only when all hold: (P1) an independent review meeting the ADR-DEV-005 §7 independence standard has passed at EV-L0 with reviewer provenance recorded per VER-002-001 §5, so its independence is falsifiable; (P2) every finding and carried open question against the document is resolved or explicitly deferred with recorded rationale; (P3) every document it is governed by is Ratified; (P4) it carries no dangling citation and no unresolved cross-document conflict; (P5) its version is stable and not under active revision. A precondition that cannot be positively established SHALL be treated as unmet. For RFC-000, which is governed by no higher document, P3 is vacuously satisfied; RFC-000 is therefore the only document that can become Ratification-Ready first.

---

## 5. Ratifying Authority

G4. Ratification is decided by the System Owner (vision §12.1) upon the Architecture Board's attestation of constitutional conformance (vision §12.2). A single person MAY perform both roles (vision §12 closing note). Because ratification confers no live authorization, it is not a risk-increasing re-arm, Live Authorization issuance, or production-scope promotion, and RFC-001 SAFE-053 does not apply to it; ratification SHALL NOT be construed to require any specific number of natural persons (RFC-000 CONST-015). The independence that SAFE-053 secures for live acts is, for ratification, secured instead by the mandatory independent EV-L0 review of §4 (P1): only independently reviewed text is eligible, and the reviewer SHALL NOT be the ratifying authority acting as author.

---

## 6. Ratification Record

G5. Each ratification SHALL be recorded in ARCHITECTURE-GATE-STATUS and SHALL identify: the target document and its exact version and commit; the decision and date; the ratifying authority and the conformance attestor; the reference to the passing independent EV-L0 review and its recorded provenance; the P1–P5 evidence; accepted requirements; deferred requirements with rationale; residual risks accepted by the System Owner; the pinned versions of every document this version cites (cited-version pins); the Ratified upstream documents relied upon; the effective date; and the re-review or expiry trigger. The record SHALL state that the ratification confers no live authority, no ADR acceptance, and no capacity.

Where RFC-001 §17 identifies accepted operational scope and applicable Safety Profile, those items are discharged at the live-authorization tier (ADR-002-007, ADR-002-014, ADR-002-025), not by document ratification; the document-ratification record for RFC-001 identifies its accepted/deferred requirements, residual risks, authority, and dates.

---

## 7. Baseline Adoption

vision and philosophy are directional, non-normative documents; they carry no Status field and are not ratification targets (G2). The System Owner MAY record a Baseline Adoption in ARCHITECTURE-GATE-STATUS that identifies the exact committed version — by commit reference and date, as these documents carry no version field — of vision and philosophy from which the normative corpus derives as its accepted directional baseline. Baseline Adoption modifies neither document, adds no requirement, confers no authority, and is not ratification.

---

## 8. Amendment and Re-ratification

G6. After ratification, any material change to a Ratified document SHALL proceed only through the RFC-000 §18 amendment process and SHALL require re-ratification of the new version; the prior Ratified version continues to govern until the new version is Ratified. A change to a clause named in another Ratified document's cited-version pins SHALL trigger a citation-integrity re-check of that citing document.

---

## 9. De-ratification

G7. The System Owner MAY de-ratify a document through the §18 process. De-ratification fails safe: governance reverts to the most recent prior Ratified version if one exists; otherwise the affected requirement SHALL NOT be relied upon and the safer (more restrictive) interpretation governs (RFC-000 §12, §15). De-ratification SHALL NOT of itself create, restore, or widen any authority.

---

## 10. Non-Authority Safety Belt

G8. Nothing in GOV-001 grants, widens, or relaxes any authority, capacity, limit, or gate defined by RFC-000, RFC-001, or any ADR. Where any clause of this document could be read to confer authority, the narrower reading governs (RFC-000 §12).

---

## 11. Review History

### v0.1 — Created

* Established the ratification and change-governance process delegated by RFC-000 §13: the three governance acts (G1), the RFC-class status ladder and the ADR/VER/Part-0 exclusions (G2), the Ratification-Ready preconditions P1 through P5 (G3), the single-operator ratifying-authority reconciliation (G4), the ratification-record schema (G5), Baseline Adoption (§7), amendment/re-ratification and citation-integrity re-check (G6), fail-safe de-ratification (G7), and the non-authority safety belt (G8).
* Process-normative and content-inert: introduces no CONST, SAFE, or AX requirement, no ADR, no numeric bound, and no verification evidence; adds nothing to either Evidence Register count; vision.md, philosophy.md, and RFC-000 are unchanged.
* Independent EV-L0 review is owed, with reviewer provenance recorded per ADR-DEV-005 §7 / VER-002-001 §5 (M-18).
