"""Safety Cell scope — the ADR §4.3 structural coordinate (design #27 §2.1D).

A single frozen coordinate record: the structural expansion of the **scalar** ``safety_cell``
coordinate the siblings already carry (capsule ``safety_cell: str | None``; afg / are
``SAFETY_CELL``; rlp ``ScopeDimension.SAFETY_CELL``). ``tos.failuredomain`` **aligns** with that
scalar and does **not** import it — sibling edge 0, the design #4 §3.1 scalar-reference pattern
(design #27 §3.1/§3.2).

Regime tag: **EV-L1 predicate substrate only; closes no FD-EV; the L1-decidable content is
sibling-owned per design #27 §3.5.**

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` (via :mod:`tos.failuredomain._base`)
only; no ``shared.*``, no sibling ``tos.*`` (design #27 §0.3).
"""

from __future__ import annotations

from tos.failuredomain._base import FrozenModel

__all__ = ["SafetyCellScope"]


class SafetyCellScope(FrozenModel):
    """The seven explicit scopes a Safety Cell SHALL have (ADR §4.3 line 92, verbatim).

    ADR-002-009 §4.3 line 90 defines a Safety Cell as "The smallest governed scope within which
    authority, capacity, egress, reconciliation, and containment consequences are intentionally
    coupled", and line 92: "A Safety Cell SHALL have an explicit **account, portfolio, broker,
    environment, authority-epoch, writer-epoch, and egress scope**. A cell boundary is not
    proven merely by labels or namespaces."

    Every field is an **opaque injected** ``str | None`` — an identifier the deployment profile
    supplies, never a value this package interprets, derives, compares numerically, or
    validates against a broker (broker-agnostic; design #27 §0.2 no hardcoded numbers).

    **A present field is not an isolation proof.** ADR §4.3 line 92 is explicit that labels and
    namespaces do not prove a cell boundary, so filling all seven scopes establishes exactly
    nothing on its own: the positive proof of recovery-scope isolation is sbr
    ``restricted_isolation_proven`` / ``IsolationFacts.all_proven`` (ADR-002-017 §17 eight
    axes, "Logical strategy separation, different UI labels, separate recovery tickets,
    distinct process instances, or unused nominal capacity do not prove isolation"), which this
    package references by token and **never re-authors** (design #27 §3.5-1).

    The **seven** fields are pinned to ADR §4.3 line 92 by the design #27 §6.4 anchor-drift
    property (the rlp §7.2 ``ScopeDimension`` ↔ ``TrialScope`` precedent): adding, dropping, or
    renaming a field fails the property until ADR §4.3 is re-read, so a spec coordinate and a
    code coordinate cannot silently diverge ("spec terms = code terms", boundary design #1
    §2.4).

    **Q3 (design #27 §2.1D)**: a ``FrozenModel`` rather than an enum, because §4.3 is a
    *structure* that carries seven scope values, not a catalogue of dimensions to enumerate —
    the rlp split (``ScopeDimension`` the closed member catalogue, ``TrialScope`` the record
    holding them) resolved the same question the same way.
    """

    account: str | None = None
    portfolio: str | None = None
    broker: str | None = None
    environment: str | None = None
    authority_epoch: str | None = None
    writer_epoch: str | None = None
    egress_scope: str | None = None
