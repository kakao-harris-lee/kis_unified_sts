"""``IncidentService`` — the INCIDENT runtime owner (sir · item 9 · plan
``docs/plans/2026-09-11-tos-phase5-w3-safety-mesh-plan.md`` §2 decision 2, third
bullet; lane W3-a2).

Loads one operator policy document — the Active Safety Incident Set (ADR-002-027 §5.5;
``tos.sir``) — into the kernel's own frozen record via the ordinary pydantic constructor
(never a raw ``dict`` downstream, project directive ``defensive-dto-tdd-directive``), and
combines two kernel predicates' verdicts into one
:class:`~tos_runtime.safety.ports.MeshClearance`. **This module authors no verdict of its
own** — every boolean in :meth:`IncidentService.clear` is either read verbatim off the
loaded document or produced by calling a ``tos.sir`` predicate (kernel round #1 §0 "판정은
커널 술어만 한다"; the M6 lesson from ``tos-phase4-scopes-round-2026-09-09``: a constant fed
where a real fact belongs silences the predicate it is fed to).

**Honest-source table (docstring per predicate, plan "Report back" requirement).**

* :func:`~tos.sir.active_set_is_canonical_union` — ``active_set`` is the loaded record;
  ``applicable_incidents`` is this service's own ``applicable_incident_ids`` config list,
  declared **separately** from ``members`` on the same document (two independent sources,
  not one field copied into two places) so a real drift between "what the operator says
  applies" and "what the members tuple actually holds" is a genuine, catchable
  inconsistency — the both-ways check design #28 §4.4 requires, not a vacuous
  self-comparison.
* :func:`~tos.sir.dominating_open_incident_present` — the loaded ``active_set`` only; the
  predicate derives openness structurally from each member's ``lifecycle_state``
  (module docstring "구조 파생 > 자기신고"), never a self-reported flag this service invents.

**Deviation flagged for the operator (plan "report back" requirement) —
``restriction_dominates_send`` is deliberately NOT called.** Plan §2 decision 2's INCIDENT
bullet lists it alongside the other two conjuncts, but the predicate's own docstring
(``tos/src/tos/sir/predicates.py:1550``) answers exactly one question — "does an incident
restriction provably precede *this specific send*" — and needs a live ``send_generation``
that does not exist at this evaluation point: :meth:`SafetyMeshService.clear` (ports.py) is
a zero-argument, per-tick call, not a per-send one. Fabricating a ``send_generation``
(``0``, ``None``, or any other constant) would be exactly the M6 anti-pattern this module's
own docstring warns against — a constant standing in for a fact that does not yet exist.
This reading is corroborated structurally: a repo-wide search
(``grep -rn restriction_dominates_send tos/``) shows **zero** kernel or runtime callers
today outside its own predicate-only test suite — the predicate's docstring is explicit
that "the cache-free currentness protocol ... and the deny-first latch are +Security
runtime and egress-owned" (i.e. still-future ``EV-L3+Security`` work), not something this
Phase 5 W3 lane can honestly wire without a live per-send caller. A future wave that adds a
live send boundary to this service's construction (or that calls it from inside the actual
egress path with a real ``send_generation``) should re-open this predicate — not invent one
here.

**Tri-state note.** Every fact this service reads is either a concrete field on the loaded
document or a definite (non-``None``-returning) kernel-predicate call — both
:func:`~tos.sir.active_set_is_canonical_union` and
:func:`~tos.sir.dominating_open_incident_present` are typed ``-> bool``, never
``bool | None``. So :meth:`clear` only ever returns ``True`` / ``False`` for this service,
never ``None`` — an honest consequence of the document-only design (mirrors
:mod:`tos_runtime.safety.deviation`'s own identical note), not a shortcut.

Pure module beyond stdlib + third-party: ``pydantic`` (via ``tos.sir`` records) + ``yaml``
+ ``tos.sir`` + ``tos_runtime.safety.ports`` + ``tos_runtime.safety._policy_loader`` +
``tos_runtime.currentness.vector`` (``DimensionReport``). No ``shared.*``, no
``os.environ``, no network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from tos.cur import DimensionKey
from tos.sir import (
    ActiveSafetyIncidentSet,
    ActiveSetMember,
    ArtifactIntegrityError,
    IncidentLifecycleState,
    active_set_is_canonical_union,
    dominating_open_incident_present,
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

__all__ = ["IncidentConfigError", "IncidentService"]

#: The code-constant ``owner_identity`` this service stamps (plan §2 decision 1 — an
#: identity is a code constant, never configuration).
_IDENTITY = "incident-service-sir-v1"

#: Deterministic, fixed-order reason tokens (ports.py "reasons" contract — one token per
#: predicate NOT positively satisfied, never a free-text message).
_REASON_CANONICAL_UNION = "active_set_is_canonical_union"
_REASON_DOMINATING_INCIDENT = "dominating_open_incident_present"


class IncidentConfigError(Exception):
    """Raised when the Active Safety Incident Set policy document is missing, malformed,
    still carries an unfilled (named-TBD) required field, or fails the kernel record's own
    schema / integrity validation — fail-closed at construction, never a lazily-discovered
    ``None`` inside :meth:`IncidentService.clear`."""


@dataclass(frozen=True)
class _LoadedIncidents:
    """The validated Active Safety Incident Set + the operator's separately-declared
    applicable-incident-id set + its source path (this service holds no digest
    computation of its own — :meth:`IncidentService.describe` reports what it loaded, not
    a recomputed artifact digest)."""

    active_set: ActiveSafetyIncidentSet
    applicable_incident_ids: frozenset[str]
    config_path: Path


def _require_lifecycle_state(
    raw: dict[str, Any], key: str, path: Path, index: int
) -> IncidentLifecycleState:
    value = require_str_field(raw, key, path, IncidentConfigError)
    try:
        return IncidentLifecycleState(value)
    except ValueError as exc:
        raise IncidentConfigError(
            f"{path}: incidents.members[{index}].{key} {value!r} is not a valid "
            f"IncidentLifecycleState ({[m.value for m in IncidentLifecycleState]!r})"
        ) from exc


def _require_str_list(raw: dict[str, Any], key: str, path: Path) -> tuple[str, ...]:
    values = require_list_field(raw, key, path, IncidentConfigError)
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise IncidentConfigError(
                f"{path}: {key!r} must be a list of non-blank strings (got {value!r})"
            )
    return tuple(values)


def _load_member(raw: Any, index: int, path: Path) -> ActiveSetMember:
    if not isinstance(raw, dict):
        raise IncidentConfigError(
            f"{path}: incidents.members[{index}] must be a mapping (got {type(raw)!r})"
        )
    incident_id = require_str_field(raw, "incident_id", path, IncidentConfigError)
    lifecycle_state = _require_lifecycle_state(raw, "lifecycle_state", path, index)
    shared_cause_ids = raw.get("shared_cause_ids") or []
    if not isinstance(shared_cause_ids, list) or not all(
        isinstance(v, str) for v in shared_cause_ids
    ):
        raise IncidentConfigError(
            f"{path}: incidents.members[{index}].shared_cause_ids must be a list of "
            f"strings (got {shared_cause_ids!r})"
        )
    resolved = raw.get("resolved")
    if resolved is not None and not isinstance(resolved, bool):
        raise IncidentConfigError(
            f"{path}: incidents.members[{index}].resolved must be a bool or null "
            f"(got {resolved!r})"
        )
    try:
        return ActiveSetMember(
            incident_id=incident_id,
            incident_digest=raw.get("incident_digest"),
            lifecycle_state=lifecycle_state,
            parent_id=raw.get("parent_id"),
            shared_cause_ids=frozenset(shared_cause_ids),
            resolved=resolved,
        )
    except ValidationError as exc:
        raise IncidentConfigError(
            f"{path}: incidents.members[{index}] does not satisfy ActiveSetMember — {exc}"
        ) from exc


def _load_active_set(body: dict[str, Any], path: Path) -> ActiveSafetyIncidentSet:
    active_set_body = require_mapping_field(
        body, "active_set", path, IncidentConfigError
    )
    members_raw = require_list_field(body, "members", path, IncidentConfigError)
    members = tuple(
        _load_member(member_raw, index, path)
        for index, member_raw in enumerate(members_raw)
    )
    shared_dependencies = _require_str_list(
        active_set_body, "shared_dependencies", path
    )

    kwargs: dict[str, Any] = {
        "active_set_id": require_str_field(
            active_set_body, "active_set_id", path, IncidentConfigError
        ),
        "active_set_generation": require_int_field(
            active_set_body, "active_set_generation", path, IncidentConfigError
        ),
        "incident_generation": require_int_field(
            active_set_body, "incident_generation", path, IncidentConfigError
        ),
        "safety_cell": require_str_field(
            active_set_body, "safety_cell", path, IncidentConfigError
        ),
        "members": members,
        "shared_dependencies": shared_dependencies,
        "is_complete": require_bool_field(
            active_set_body, "is_complete", path, IncidentConfigError
        ),
        "is_current": require_bool_field(
            active_set_body, "is_current", path, IncidentConfigError
        ),
    }
    try:
        return ActiveSafetyIncidentSet(**kwargs)
    except ValidationError as exc:
        raise IncidentConfigError(
            f"{path}: incidents.active_set does not satisfy ActiveSafetyIncidentSet — {exc}"
        ) from exc
    except ArtifactIntegrityError as exc:
        raise IncidentConfigError(
            f"{path}: incidents.active_set violates a kernel integrity seal — {exc}"
        ) from exc


def _load_incidents(path: Path) -> _LoadedIncidents:
    raw = load_yaml_document(path, IncidentConfigError)
    body = require_mapping_field(raw, "incidents", path, IncidentConfigError)
    active_set = _load_active_set(body, path)
    applicable_incident_ids = frozenset(
        _require_str_list(body, "applicable_incident_ids", path)
    )
    return _LoadedIncidents(
        active_set=active_set,
        applicable_incident_ids=applicable_incident_ids,
        config_path=path,
    )


class IncidentService:
    """The INCIDENT :class:`~tos_runtime.safety.ports.SafetyMeshService` (module
    docstring). Construction loads and validates the Active Safety Incident Set policy
    document — a missing / still-null / schema-invalid document refuses construction
    outright (never a ``None`` service instance)."""

    def __init__(self, *, config_path: Path) -> None:
        """Load + validate the Active Safety Incident Set policy document, fail-closed.

        Args:
            config_path: Path to a policy YAML document (top-level key ``incidents``,
                carrying ``active_set`` + ``members`` + ``applicable_incident_ids`` — see
                ``tos/runtime/config/safety_incidents.example.yaml``).

        Raises:
            IncidentConfigError: The file is missing, unreadable, not valid YAML, not a
                mapping, missing a required field, still null (named-TBD), or fails the
                kernel record's own schema / integrity validation.
        """
        self._docs = _load_incidents(config_path)

    @property
    def identity(self) -> str:
        return _IDENTITY

    @property
    def dimension_key(self) -> DimensionKey:
        return DimensionKey.INCIDENT

    def clear(self) -> MeshClearance:
        """The deferred-item / Coordinator verdict (module docstring)."""
        active_set = self._docs.active_set
        reasons: list[str] = []

        canonical = active_set_is_canonical_union(
            active_set, self._docs.applicable_incident_ids
        )
        if canonical is not True:
            reasons.append(_REASON_CANONICAL_UNION)

        dominating = dominating_open_incident_present(active_set)
        if dominating is not False:
            reasons.append(_REASON_DOMINATING_INCIDENT)

        overall = not reasons
        if overall:
            reasons = []
        return MeshClearance(
            identity=self.identity, clear=overall, reasons=tuple(reasons)
        )

    def dimension_report(self) -> DimensionReport | None:
        """This owner's currentness verdict for INCIDENT (module docstring).
        ``restrictive_floor`` is ``0`` — a **deliberate** statement, not an invented
        default: :class:`~tos.sir.records.ActiveSafetyIncidentSet` carries no
        floor-governance field of its own, and Phase 5 has no floor-governance runtime yet
        (the same "an owner reporting 0 is that owner's own choice" discipline
        :class:`~tos_runtime.currentness.vector.DimensionReport`'s own docstring states).
        """
        return DimensionReport(
            bound_generation=self._docs.active_set.incident_generation,
            positively_established=self.clear().clear is True,
            restrictive_floor=0,
        )

    def describe(self) -> dict[str, Any]:
        """Evidence-facing description of the loaded policy document — names,
        generations, and identity only; never a secret / bearer token
        (:class:`~tos_runtime.safety.ports.SafetyMeshService.describe` contract)."""
        active_set = self._docs.active_set
        return {
            "identity": self.identity,
            "config_path": str(self._docs.config_path),
            "active_set_id": active_set.active_set_id,
            "active_set_generation": active_set.active_set_generation,
            "incident_generation": active_set.incident_generation,
            "safety_cell": active_set.safety_cell,
            "member_count": len(active_set.members),
            "applicable_incident_count": len(self._docs.applicable_incident_ids),
        }
