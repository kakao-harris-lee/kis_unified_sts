"""Runtime workload-instance identity record (design #40 D4-a).

Realizes the *kernel* (pure) half of design doc #40's D4 decision
(``docs/plans/2026-09-07-tos-phase2-runtime-shell-preliminary-decisions.md`` §D4.1
line 109): "정체성: ``RuntimeIdentity{cell_id, runtime_generation, process_nonce,
code_digest}`` — 기동 시 발급, 모든 evidence·RCL 항목에 결속. ``runtime_generation``
은 D2 epoch 와 **같은 트랜잭션**에서 증가(ADR-002-017 :15 Recovery Generation 의
전신 · Phase 5 가 소비)." §5-A's own line for this deliverable: "``RuntimeIdentity``
레코드(cell_id·runtime_generation·process_nonce·code_digest — 전부 주입 스칼라) ...
순수 · custody 는 여전히 런타임 소관(커널은 비밀을 모른다)". This module authors
only the record; **issuance** (allocating a fresh ``process_nonce``, reading
``code_digest``, incrementing ``runtime_generation`` alongside the RCL epoch) is
``tos_runtime`` territory (D1, not yet ratified) — every field here is injected.

**Package placement, decided by anti-phantom grep (task directive).** No existing
``tos`` kernel package models a running-instance identity of this shape.
``git grep -n "RuntimeIdentity\\|runtime_generation\\|process_nonce\\|code_digest"
tos/src/tos`` (before this module) -> empty across all four names. The two nearest
candidates, checked and rejected:

* ``tos.failuredomain`` — owns ``safety_cell_id`` / ``safety_cell_identity`` as a
  **referenced deployment/isolation coordinate** (``evidence/envelope.py:69``,
  ``replacement/records.py:381``), not an *issuing* record for a workload instance;
  its own module docstring states it "grants no authority... enforces no
  containment" and generalizes only the six sibling coordinates it already owns —
  runtime instance identity is not one of them (design #27 §3.5 ownership table).
* ``tos.sci`` — owns release-artifact-level supply-chain provenance
  (``RuntimeArtifactAttestation``, build/source/signing digests), a *build-time*
  identity axis. Its own module docstring lists "runtime measurement... effective-
  principal collapse" among the over-realization risks it explicitly does NOT take
  on (design #29 §0.1-5 item 1) — a *live* instance identity is exactly that
  excluded axis, not something ``tos.sci`` already models.
* ``tos.authority`` — owns the Safety Authority epoch (``safety_authority_epoch``),
  a *different* governed namespace from both RCL's Writer Epoch (already reported
  as distinct in ``tos/src/tos/rcl/commitlog.py`` lines 52-61, ADR-002-012 §5.5)
  and this module's ``runtime_generation`` (design #40 §7 v1.1 revision-log note ②
  makes the same "no unproven-equivalence force-merge" call for the RCL/authority
  epoch pair — the same discipline applies here a third time).
* ``tos.egress`` (ADR-002-013's own kernel package) — owns egress-boundary
  *credential/principal* identity (``EgressRequestRecord.active_principal``,
  ``credential_generation``), scoped to the broker send boundary. D4.1's
  ``RuntimeIdentity`` binds into "모든 evidence·RCL 항목" (every evidence/RCL
  entry), not only egress ones — a strictly broader binding scope than
  ``tos.egress`` claims for its own principal identity.

No sibling package's own scope covers a cross-cutting, boot-issued workload
identity that binds evidence AND RCL entries alike, so this module lands in a new,
small package named after design #40 D4's own section title ("워크로드 정체성" —
workload identity) — ``tos.workload`` — rather than a bespoke ADR-numbered name
(no single ADR owns this Phase-2 concept).

Pure module: ``pydantic`` + stdlib only; no ``shared.*``, no I/O, no clock, no RNG
(a real ``process_nonce``/``code_digest`` is issued by the runtime, never generated
here).
"""

from __future__ import annotations

from pydantic import model_validator

from tos.canonical import ArtifactIntegrityError, FrozenModel

__all__ = ["RuntimeIdentity"]


class RuntimeIdentity(FrozenModel):
    """The identity of one running kernel-hosting process instance (design #40 D4-a).

    "기동 시 발급, 모든 evidence·RCL 항목에 결속" — issued once at process start by
    the (not-yet-ratified) runtime shell, then carried as an injected scalar
    binding on every evidence record and RCL log entry this process produces. This
    kernel module never issues one itself; it only defines the shape a runtime
    issuer must produce and a kernel consumer may bind against.

    ``cell_id`` is left type-independent of ``tos.failuredomain``'s
    ``safety_cell_id`` / ``tos.replacement``'s ``safety_cell_identity`` (both plain
    ``str | None`` already) — a caller may inject the same string value into both,
    but this record does not import or structurally couple to either sibling
    (module docstring "package placement" note).

    ``runtime_generation`` "은 D2 epoch 와 같은 트랜잭션에서 증가" (design #40
    §D4.1 line 109) — a **precursor** of ADR-002-017's Recovery Generation
    (":15 ... SHALL create or advance a monotonic Recovery Generation"), which
    Phase 5 consumes; this module does not model Recovery Generation itself, only
    the runtime-instance counter design #40 names as its forerunner.
    """

    cell_id: str | None = None
    runtime_generation: int | None = None
    process_nonce: str | None = None
    code_digest: str | None = None

    @model_validator(mode="after")
    def _runtime_identity_invariants(self) -> RuntimeIdentity:
        """Reject a negative generation or a blank (but present) process nonce."""
        if self.runtime_generation is not None and self.runtime_generation < 0:
            raise ArtifactIntegrityError(
                "RuntimeIdentity.runtime_generation must be non-negative "
                f"(got {self.runtime_generation})"
            )
        if self.process_nonce is not None and not self.process_nonce.strip():
            raise ArtifactIntegrityError(
                "RuntimeIdentity.process_nonce must be non-blank when provided — "
                "a blank nonce cannot fence a stale-instance replay"
            )
        return self
