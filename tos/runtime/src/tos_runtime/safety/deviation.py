"""``DeviationService`` — the DEVIATION runtime owner (wdr · item 8 · plan
``docs/plans/2026-09-11-tos-phase5-w3-safety-mesh-plan.md`` §2 decision 2, second bullet;
lane W3-a1).

Loads one operator policy document — the currently Active Deviation Set plus its member
decisions (ADR-002-026 / ``tos.wdr``) — into the kernel's own frozen records via
``model_validate``, and combines three kernel predicates' verdicts into one
:class:`~tos_runtime.safety.ports.MeshClearance`. Like :mod:`tos_runtime.safety.profile`,
this module authors no verdict of its own: every boolean in :meth:`DeviationService.clear`
either comes straight off the loaded document or from a ``tos.wdr`` predicate call.

**Honest-source table.**

* :func:`~tos.wdr.combined_set_no_permissive_union` — ``active_set`` and
  ``applicable_decision_ids`` are the loaded document; ``member_within_envelope`` maps to
  the kernel record's own ``combined_within_envelope`` field
  (``tos.wdr.ActiveDeviationSet.combined_within_envelope``), which the kernel's own
  ``records.py`` docstring calls an **injected** spg verdict (§13 item 3) — i.e. the
  kernel itself does not expect wdr to derive this fact; it expects a producer elsewhere
  to supply it. This lane owns no live wiring into :class:`~tos_runtime.safety.profile
  .SafetyProfileService` (that composition, if wanted, is a ``compose``-layer decision
  for W3-b, outside this lane's file ownership — plan §4), so ``combined_within_envelope``
  is carried here as an **explicit named operator attestation** on the policy document,
  the same "no real producer yet" discipline :mod:`tos_runtime.compose
  ._egress_attestations` already applies to items 12/16. **Flagged for the operator**
  (plan "report back" requirement): a future wiring that feeds this from
  ``SafetyProfileService.clear()`` directly would be a strictly more honest source than a
  static attestation, and should replace this field when W3-b or a later wave composes
  the four services together.
* per-member :func:`~tos.wdr.classification_admissible` /
  :func:`~tos.wdr.unresolved_is_non_waivable` — both read only the member's own loaded
  :class:`~tos.wdr.DeviationClassification` (``classification`` /
  ``applicability_resolved`` / ``boundary_hits``), all concrete fields on the policy
  document. No fabricated fact.
* :func:`~tos.wdr.revocation_dominates_send` — ``revoke_generation`` / ``send_generation``
  are per-member optional ints on the policy document (``null`` by default: "no
  revocation in progress" / "no outstanding send to race against"). This predicate is
  only evaluated for a member that **declares** a ``revoke_generation`` (an active
  revocation) — a member with no revocation in progress has nothing to dominate, so it is
  vacuously fine and not evaluated (never a fabricated ``True``).

**Tri-state note.** Every fact this service reads is either a concrete field on the
loaded document or a definite kernel-predicate return; nothing here is genuinely
unevaluable at construction time (there is no injected external port, unlike
``SafetyProfileService``'s time source). So :meth:`clear` only ever returns ``True`` /
``False`` for this service, never ``None`` — an honest consequence of the document-only
design, not a shortcut (fabricating a ``None`` case where every input is already
concretely known would itself be a form of over-claiming uncertainty).

Pure module beyond stdlib + third-party: ``pydantic`` (via ``tos.wdr`` records) + ``yaml``
+ ``tos.wdr`` + ``tos_runtime.safety.ports`` + ``tos_runtime.safety._policy_loader`` +
``tos_runtime.currentness.vector`` (``DimensionReport``). No ``shared.*``, no
``os.environ``, no network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from tos.cur import DimensionKey
from tos.wdr import (
    ActiveDeviationSet,
    DeviationClassification,
    classification_admissible,
    combined_set_no_permissive_union,
    revocation_dominates_send,
    unresolved_is_non_waivable,
)

from tos_runtime.currentness.vector import DimensionReport
from tos_runtime.safety._policy_loader import (
    load_yaml_document,
    require_bool_field,
    require_int_field,
    require_list_field,
    require_mapping_field,
    require_str_field,
)
from tos_runtime.safety.ports import MeshClearance

__all__ = [
    "DeviationConfigError",
    "DeviationService",
]

#: The code-constant ``owner_identity`` this service stamps (plan §2 decision 1).
_IDENTITY = "deviation-service-wdr-v1"

#: Deterministic, fixed-order reason tokens (ports.py "reasons" contract).
_REASON_COMBINED_SET = "combined_set_no_permissive_union"
_REASON_CLASSIFICATION = "unresolved_is_non_waivable_or_not_admissible"
_REASON_REVOCATION = "revocation_dominates_send"


class DeviationConfigError(Exception):
    """Raised when the deviation policy document is missing, malformed, still carries an
    unfilled (named-TBD) required field, or fails the kernel record's own schema
    validation — fail-closed at construction."""


@dataclass(frozen=True)
class _DeviationMember:
    decision_id: str
    classification: DeviationClassification
    revoke_generation: int | None
    send_generation: int | None


@dataclass(frozen=True)
class _LoadedDeviations:
    active_set: ActiveDeviationSet
    applicable_decision_ids: frozenset[str]
    members: tuple[_DeviationMember, ...]
    source_path: Path


def _validate_member(raw: Any, index: int, path: Path) -> _DeviationMember:
    if not isinstance(raw, dict):
        raise DeviationConfigError(
            f"{path}: members[{index}] must be a mapping (got {type(raw)!r})"
        )
    decision_id = require_str_field(raw, "decision_id", path, DeviationConfigError)
    classification_raw = {
        "classification": raw.get("classification"),
        "applicability_resolved": raw.get("applicability_resolved"),
        "boundary_hits": raw.get("boundary_hits", []),
    }
    try:
        classification = DeviationClassification.model_validate(classification_raw)
    except ValidationError as exc:
        raise DeviationConfigError(
            f"{path}: members[{index}] ({decision_id!r}) does not satisfy "
            f"DeviationClassification — {exc}"
        ) from exc
    revoke_generation = raw.get("revoke_generation")
    if revoke_generation is not None and (
        isinstance(revoke_generation, bool) or not isinstance(revoke_generation, int)
    ):
        raise DeviationConfigError(
            f"{path}: members[{index}] ({decision_id!r}) revoke_generation must be an "
            f"int or null (got {revoke_generation!r})"
        )
    send_generation = raw.get("send_generation")
    if send_generation is not None and (
        isinstance(send_generation, bool) or not isinstance(send_generation, int)
    ):
        raise DeviationConfigError(
            f"{path}: members[{index}] ({decision_id!r}) send_generation must be an "
            f"int or null (got {send_generation!r})"
        )
    return _DeviationMember(
        decision_id=decision_id,
        classification=classification,
        revoke_generation=revoke_generation,
        send_generation=send_generation,
    )


def _load_deviations(path: Path) -> _LoadedDeviations:
    raw = load_yaml_document(path, DeviationConfigError)
    body = require_mapping_field(raw, "deviations", path, DeviationConfigError)

    active_set_raw = require_mapping_field(
        body, "active_set", path, DeviationConfigError
    )
    active_set_generation = require_int_field(
        active_set_raw, "active_set_generation", path, DeviationConfigError
    )
    deviation_generation = require_int_field(
        active_set_raw, "deviation_generation", path, DeviationConfigError
    )
    is_complete = require_bool_field(
        active_set_raw, "is_complete", path, DeviationConfigError
    )
    combined_within_envelope = require_bool_field(
        active_set_raw, "combined_within_envelope", path, DeviationConfigError
    )
    active_set_id = require_str_field(
        active_set_raw, "active_set_id", path, DeviationConfigError
    )

    applicable_decision_ids = frozenset(
        require_list_field(body, "applicable_decision_ids", path, DeviationConfigError)
    )

    members_raw = require_list_field(body, "members", path, DeviationConfigError)
    members = tuple(
        _validate_member(member_raw, index, path)
        for index, member_raw in enumerate(members_raw)
    )

    active_set = ActiveDeviationSet.model_validate(
        {
            "active_set_id": active_set_id,
            "active_set_generation": active_set_generation,
            "deviation_generation": deviation_generation,
            "is_complete": is_complete,
            "combined_within_envelope": combined_within_envelope,
            "member_decisions": tuple(member.decision_id for member in members),
        }
    )

    return _LoadedDeviations(
        active_set=active_set,
        applicable_decision_ids=applicable_decision_ids,
        members=members,
        source_path=path,
    )


class DeviationService:
    """The DEVIATION :class:`~tos_runtime.safety.ports.SafetyMeshService` (module
    docstring). Construction loads and validates the deviation policy document — a
    missing / still-null / schema-invalid document refuses construction outright."""

    def __init__(self, *, deviations_path: Path) -> None:
        """Load + validate the deviation policy document, fail-closed.

        Args:
            deviations_path: Path to a deviations YAML document (top-level key
                ``deviations``; see module docstring for the schema — an explicit empty
                ``members: []`` / ``applicable_decision_ids: []`` is the valid nominal
                "no deviations" state).

        Raises:
            DeviationConfigError: The document is missing, unreadable, not valid YAML,
                not a mapping, missing a required field, still null (named-TBD), or a
                member fails the kernel record's own schema validation.
        """
        self._docs = _load_deviations(deviations_path)

    @property
    def identity(self) -> str:
        return _IDENTITY

    @property
    def dimension_key(self) -> DimensionKey:
        return DimensionKey.DEVIATION

    def _member_violations(self) -> tuple[str, ...]:
        violated: list[str] = []
        for member in self._docs.members:
            admissible = classification_admissible(member.classification)
            non_waivable = unresolved_is_non_waivable(
                member.classification.classification
            )
            if admissible is not True or non_waivable is not False:
                violated.append(member.decision_id)
        return tuple(violated)

    def _revocation_violations(self) -> tuple[str, ...]:
        violated: list[str] = []
        for member in self._docs.members:
            if member.revoke_generation is None:
                # No revocation in progress for this member — nothing to dominate.
                continue
            dominates = revocation_dominates_send(
                member.revoke_generation, member.send_generation
            )
            if dominates is not True:
                violated.append(member.decision_id)
        return tuple(violated)

    def clear(self) -> MeshClearance:
        """The deferred-item / Coordinator verdict (module docstring)."""
        reasons: list[str] = []

        combined_ok = combined_set_no_permissive_union(
            self._docs.active_set,
            self._docs.applicable_decision_ids,
            self._docs.active_set.combined_within_envelope,
        )
        if combined_ok is not True:
            reasons.append(_REASON_COMBINED_SET)

        member_violations = self._member_violations()
        if member_violations:
            reasons.append(_REASON_CLASSIFICATION)

        revocation_violations = self._revocation_violations()
        if revocation_violations:
            reasons.append(_REASON_REVOCATION)

        overall = (
            combined_ok is True and not member_violations and not revocation_violations
        )
        return MeshClearance(
            identity=self.identity,
            clear=overall,
            reasons=() if overall else tuple(reasons),
        )

    def dimension_report(self) -> DimensionReport | None:
        """This owner's currentness verdict for DEVIATION (module docstring).
        ``restrictive_floor`` is ``0`` — a deliberate statement (no floor-governance
        runtime for this dimension yet), never an invented default."""
        return DimensionReport(
            bound_generation=self._docs.active_set.deviation_generation,
            positively_established=self.clear().clear is True,
            restrictive_floor=0,
        )

    def describe(self) -> dict[str, Any]:
        """Evidence-facing description of the loaded policy document."""
        return {
            "identity": self.identity,
            "source_path": str(self._docs.source_path),
            "active_set_id": self._docs.active_set.active_set_id,
            "active_set_generation": self._docs.active_set.active_set_generation,
            "deviation_generation": self._docs.active_set.deviation_generation,
            "member_decision_ids": list(self._docs.active_set.member_decisions),
        }
