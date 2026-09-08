"""Retention deletability predicate + Tombstone record (design #40 D3.1, D3-c).

Realizes the *kernel* (pure) half of design doc #40's D3 retention decision
(``docs/plans/2026-09-07-tos-phase2-runtime-shell-preliminary-decisions.md`` §D3.1
line 92): "«열린/live 레코드는 재구성 가능성 아래로 삭제 불가»(ADR-002-016
:432-441)는 술어 ``deletable(record, holds, now)`` 로만 존재하고 **삭제 잡은
Phase 2 범위 밖**(툼스톤 스키마만)". This module authors that predicate — named
:func:`retention_deletable` (the design doc's own shorthand is generic prose,
"``deletable(record, holds, now)``"; no existing symbol of that literal name was
found — ``git grep -n "def deletable"`` and ``git grep -n "class Deletable"`` under
``tos/src`` (before this module) both -> empty, so this is a fresh name, not a
collision) — and the append-only :class:`Tombstone` deletion record shape.

**Deliberately separate from the Phase-1 retention substrate, reported not merged**
(playbook §2.C/§2.D). :mod:`tos.evidence.predicates` already has
:class:`~tos.evidence.predicates.RetentionSubject` (a flag bundle: open order /
potentially-live attempt / UNKNOWN / open position / unreleased capacity / ... /
live scope) and :func:`~tos.evidence.predicates.tombstone_admissible` (``True`` iff
no flag is set), plus :func:`~tos.evidence.predicates.effective_retention_horizon`
(a *dominance-ordered* ``RetentionHorizon`` enum with "no duration hard-coded ...
concrete durations are Phase-0" — ``predicates.py`` lines 291-292). That Phase-1
substrate deliberately left concrete per-class retention *durations* unbound
(unapproved profile key). Design #40 D3.1 is the first decision to inject a concrete
axis — ``minimum_days_by_class`` — so :func:`retention_deletable` is a **new,
additive** predicate over that axis, not a replacement for
:func:`~tos.evidence.predicates.tombstone_admissible`'s dominance semantics. A
caller composing the two derives this predicate's ``open_or_live`` argument as
``not tombstone_admissible(subject)`` when a full :class:`RetentionSubject` is
available; :func:`retention_deletable` itself takes the already-collapsed boolean so
it stays a pure function of exactly five injected scalars (per the task's own
signature) with no dependency on that Phase-1 model.

Pure module: ``pydantic`` + stdlib only; no ``shared.*``, no I/O.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import model_validator

from tos.canonical import ArtifactIntegrityError, FrozenModel

__all__ = ["Tombstone", "retention_deletable"]


def retention_deletable(
    record_class: str | None,
    age_days: int | None,
    minimum_days_by_class: Mapping[str, int] | None,
    holds_active: bool | None,
    open_or_live: bool | None,
) -> bool:
    """Whether a record may be deleted under retention policy (design #40 D3.1).

    Fail-closed on every axis (playbook §2.A — a ``None`` coordinate is never
    treated as a pass): admits **only** when every input is concretely present,
    the record's class has a configured minimum retention, its age has reached
    that minimum, no legal/incident hold is active, and the record is not
    open/live. ``holds_active``/``open_or_live`` are checked with ``is False``
    (not ``is not True`` — playbook §2.A's "negative-polarity clear flag" rule):
    an unknown hold/open state is conservatively treated as "still holding" /
    "still live", never as "known clear".

    Args:
        record_class: The record's retention class label, or ``None`` if unknown
            (refuses).
        age_days: The record's age in days since it became eligible for
            retention counting, or ``None`` if unknown (refuses).
        minimum_days_by_class: The injected per-class minimum retention period
            (design #40 §D3.1 "``config/tos_runtime/evidence_retention.yaml``" —
            this module invents no values; the mapping is supplied by the caller).
            ``None`` refuses (no policy loaded is not "no minimum").
        holds_active: Whether a legal/incident hold is currently active on this
            record. Only an explicit ``False`` admits; ``None`` (unknown) and
            ``True`` both refuse.
        open_or_live: Whether the record still supports an open/unresolved live
            or economic effect (ADR-002-016 :432-441). Only an explicit ``False``
            admits; ``None`` and ``True`` both refuse.

    Returns:
        ``True`` iff every condition above is positively satisfied.
    """
    if record_class is None or age_days is None or minimum_days_by_class is None:
        return False
    if holds_active is not False:
        return False
    if open_or_live is not False:
        return False
    minimum = minimum_days_by_class.get(record_class)
    if minimum is None:
        return False
    if age_days < 0 or minimum < 0:
        return False
    return age_days >= minimum


class Tombstone(FrozenModel):
    """An append-only deletion record over one prior evidence record (design #40 D3.1).

    "삭제 잡은 Phase 2 범위 밖(툼스톤 스키마만)" — this module authors only the
    record shape, never a deletion executor. ``deleted_at`` is an **injected
    scalar** coordinate, never a clock read (this package is clock-free, matching
    every other ``tos`` kernel package's convention — e.g. ``tos.time``'s "opaque
    injected time coordinate", never ``time``/``datetime``); it is typed as an
    opaque id string, the same shape as
    ``tos.evidence.receipt.EvidenceCommitReceipt.committed_at_time_snapshot_id``,
    rather than a raw numeric timestamp, so a Tombstone binds to a Trustworthy Time
    snapshot the same way every other timed evidence artifact does.

    ``dual_control_ref`` is the only field this record validates as required +
    non-blank (per the task directive): ADR-002-016 §17 line 443 verbatim —
    "Destructive deletion requires approved policy, effective-human dual control,
    scope proof, expired holds, integrity-preserving tombstone, and evidence that
    economic lifetime and acceptance obligations ended" — so a Tombstone with no
    dual-control witness reference could not be checked against that requirement
    and is therefore not a valid deletion record. ``record_id``/``record_class``
    (the reference to what was tombstoned) are left optional at the type level,
    matching this codebase's convention of validating only the field the design
    doc calls out explicitly, with fuller required-ness enforced at the point of
    use.
    """

    record_id: str | None = None
    record_class: str | None = None
    deleted_at: str | None = None
    dual_control_ref: str | None = None

    @model_validator(mode="after")
    def _dual_control_ref_non_blank(self) -> Tombstone:
        """Reject a Tombstone with a missing or blank dual-control reference."""
        if self.dual_control_ref is None or not self.dual_control_ref.strip():
            raise ArtifactIntegrityError(
                "Tombstone.dual_control_ref must be non-blank — a tombstone with "
                "no dual-control witness is not a valid deletion record "
                "(ADR-002-016 :432-441)"
            )
        return self
