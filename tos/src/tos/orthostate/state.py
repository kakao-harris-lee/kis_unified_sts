"""Orthostate injected predicate-input models (design #8 §2.1, §5.2).

Plain frozen models that carry the **injected** side-conditions the pure coupling
predicate folds over (design #8 §0.2/§5.2: everything is a pure function over injected
state — no clock reads, no egress, no persistence). Every flag is ``bool | None`` and
**fail-closed**: ``None`` (UNKNOWN) is treated conservatively as *not proven*, so a
missing proof / epoch / trapped flag can never turn an invariant violation into a pass
(design #8 §4.4). Numeric freshness bounds are out of scope for Phase 1 — freshness is
carried as an injected opaque flag, never a hardcoded threshold (design #8 §3.5/§8).

Pure module: ``pydantic`` + stdlib + ``tos.orthostate`` only; no ``shared.*`` (§0.3).
"""

from __future__ import annotations

from tos.orthostate._base import FrozenModel


class CouplingSideConditions(FrozenModel):
    """Injected side-conditions for the cross-dimension coupling predicate (§5.2).

    Each flag is ``bool | None``; ``None`` is UNKNOWN and fails closed (the coupling
    predicate never treats an unproven side-condition as satisfied — design #8 §5.2
    "side-flag None ⇒ 보수적으로 위반-처리"). These carry only the proof / epoch /
    trapped signals the CPL invariants require; the actual evidence, Final Quantity
    Proof, and authority-epoch mechanisms are owned by other ADRs and are referenced
    here only as opaque flags (design #8 §2.0/§3.5).

    Attributes:
        final_quantity_proof: Final Quantity Proof is present where required (CPL-2
            release; also distinguishes a bare cancel-ACK from a proven cancel in
            CPL-4). ``None`` / ``False`` => not proven.
        consistent_release_proof_rule: The applicable proof rule holds for a
            ``CONSISTENT`` (rather than ``RECONCILED``) release (CPL-2 alternative).
            ``None`` / ``False`` => not proven.
        authority_epoch_current: The current authority epoch + live scope are
            verifiable at final egress for an attempt that reached ``SEND_STARTED``
            (CPL-6). ``None`` / ``False`` (stale) => fail closed.
        non_reducible_exposure: Confirmed non-reducible exposure is present (CPL-7).
            Only ``True`` triggers the ``TRAPPED_CONSUMED`` obligation; ``None`` /
            ``False`` do not assert exposure.
    """

    final_quantity_proof: bool | None = None
    consistent_release_proof_rule: bool | None = None
    authority_epoch_current: bool | None = None
    non_reducible_exposure: bool | None = None
