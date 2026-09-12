"""``SafetyProfileService`` — the SAFETY_ENVELOPE_PROFILE runtime owner (spg · item 7 ·
plan ``docs/plans/2026-09-11-tos-phase5-w3-safety-mesh-plan.md`` §2 decision 2, first
bullet; lane W3-a1).

Loads three operator policy documents — a Hard Safety Envelope, a Runtime Safety Profile,
and an Activation Record (ADR-002-014 / ``tos.spg``) — into the kernel's own frozen
records via ``model_validate`` (never a raw ``dict`` downstream, project directive
``defensive-dto-tdd-directive``), and combines four kernel predicates' verdicts into one
:class:`~tos_runtime.safety.ports.MeshClearance`. **This module authors no verdict of its
own** — every boolean in :meth:`SafetyProfileService.clear` is either read verbatim off a
loaded document or produced by calling a ``tos.spg`` predicate (kernel round #1 §0 "판정은
커널 술어만 한다"; the M6 lesson from ``tos-phase4-scopes-round-2026-09-09``: a constant
fed where a real fact belongs silences the predicate it is fed to).

**Honest-source table (docstring per predicate, plan "Report back" requirement).**

* :func:`~tos.spg.profile_within_envelope` — both arguments are the loaded envelope /
  profile records; this predicate needs nothing this service cannot supply.
* :func:`~tos.spg.hard_and_runtime_versions_match` — envelope / profile / activation are
  the loaded records; ``mixed_versions_present`` is sourced from **cardinality**, not
  assumption: this service's config format loads exactly one candidate generation of each
  artifact (a single YAML document each, never a collection of concurrent candidates), so
  there is structurally no representation of a second, concurrently-active generation in
  this document set. ``mixed_versions_present=False`` states that structural fact, not a
  business guess (documented as a deviation for the operator — see the module docstring's
  final paragraph).
* :func:`~tos.spg.activation_atomic` — the four content seam-bools + two staging gates are
  each sourced from the **loaded documents only** (no external bundle / signature /
  aggregate-risk / software-release / time-validity service is in this lane's scope):

  - ``version_fully_active`` — the three loaded records' generations cross-reference
    consistently (``profile.target_envelope_generation == envelope.envelope_generation``
    and ``activation.profile_generation == profile.profile_generation``), all concrete.
  - ``mixed_versions_present`` — ``False`` (cardinality, above).
  - ``units_compatible`` — computed by :func:`~tos.spg.units_compatible` over a
    :class:`~tos.spg.SafetyConfigurationBundle` built from **only** the loaded envelope +
    profile (``members=()``) and a bare :class:`~tos.spg.SemanticValidationInputs` (every
    other fold-step flag left at its ``None`` default). This is honest because
    ``units_compatible`` reads exactly one reason
    (``ValidationReason.UNIT_OR_MULTIPLIER_MISMATCH``) out of
    :func:`~tos.spg.semantic_validation`'s result, and that one reason is produced purely
    from the envelope/profile dimension metadata comparison (unit / multiplier / sign /
    precision / rounding / boundary) — never from the other injected fold-step flags this
    service leaves at ``None``. No fabricated fact reaches this particular answer.
  - ``envelope_bounded`` — :func:`~tos.spg.envelope_bounded` is pure delegation to
    :func:`~tos.spg.profile_within_envelope`, i.e. it reuses the same loaded records.
  - ``staging_complete`` — ``activation.approval_ids`` is a non-empty tuple (a concrete
    field read directly off the loaded Activation Record — approvals were recorded).
  - ``attestation_complete`` — ``activation.compatibility_attestation_refs`` is a
    non-empty tuple (same discipline, the record's own attestation-refs field).
* :func:`~tos.spg.expiry_suspends_new_risk` — ``not_expired`` is an **explicit operator
  attestation** on the activation document (this lane owns no date-arithmetic / clock
  service, and spg itself "performs no time arithmetic" by design — design #12 §3.5), the
  same "named-TBD attestation until a real producer lands" discipline
  :mod:`tos_runtime.compose._egress_attestations` already applies to item 12/16.
  ``time_verifiable`` comes from an **injected time port** (constructor parameter
  ``time_source``): ``True`` only when ``time_source.health_state() is HealthState.TRUSTED``.
  When no ``time_source`` is supplied, or its health state is not ``TRUSTED``, the service
  cannot establish time-verifiability at all — this is the plan's own worked example of an
  **unevaluable** fact ("time not TRUSTED for expiry"), so it does not feed a fabricated
  ``False`` into the kernel predicate; instead :meth:`clear` reports the whole verdict as
  ``None`` (UNKNOWN) rather than a false-negative ``False`` (DENIED), unless another
  predicate has *already* positively failed (see the tri-state combination rule below).

**Tri-state combination (this service's own runtime-level policy, not a kernel
invention).** Each of the four checks above yields ``True`` / ``False`` / ``None``
(``None`` occurs only for the expiry check, exactly when ``time_verifiable`` cannot be
established). The overall verdict combines them with a fail-closed AND: any ``False``
dominates (a positively-established violation is the strongest, most informative
signal — never softened to "unknown" just because a sibling check is unevaluable);
absent any ``False``, any ``None`` makes the whole verdict ``None``; only when every
check is ``True`` does :meth:`clear` return ``True``.

**Deviation flagged for the operator (plan "report back" requirement).** The
``mixed_versions_present=False`` cardinality argument above is sound for THIS service's
config format (one document per artifact), but is a real gap if the platform ever needs to
track multiple concurrent candidate generations under review — at that point a genuine
multi-candidate producer must replace this structural inference, not just widen this
docstring.

Pure module beyond stdlib + third-party: ``pydantic`` (via ``tos.spg`` records) + ``yaml``
+ ``tos.spg`` + ``tos.time`` (``HealthState`` only, for the injected time port's return
type) + ``tos_runtime.safety.ports`` + ``tos_runtime.safety._policy_loader`` +
``tos_runtime.currentness.vector`` (``DimensionReport``). No ``shared.*``, no
``os.environ``, no network I/O beyond the local YAML file reads.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError
from tos.cur import DimensionKey
from tos.spg import (
    ActivationInputs,
    ActivationRecord,
    ActivationVerdict,
    HardSafetyEnvelope,
    RuntimeSafetyProfile,
    SafetyConfigurationBundle,
    SemanticValidationInputs,
    activation_atomic,
    active_envelope_generation,
    envelope_bounded,
    expiry_suspends_new_risk,
    hard_and_runtime_versions_match,
    profile_within_envelope,
    units_compatible,
)
from tos.time import HealthState

from tos_runtime.currentness.vector import DimensionReport
from tos_runtime.safety._policy_loader import (
    load_yaml_document,
    require_bool_field,
    require_mapping_field,
)
from tos_runtime.safety.ports import MeshClearance

__all__ = [
    "SafetyProfileConfigError",
    "TimeHealthSource",
    "SafetyProfileService",
]

#: The code-constant ``owner_identity`` this service stamps (plan §2 decision 1 — an
#: identity is a code constant, never configuration).
_IDENTITY = "safety-profile-service-spg-v1"

#: Deterministic, fixed-order reason tokens (ports.py "reasons" contract — one token per
#: predicate NOT positively satisfied, never a free-text message).
_REASON_PROFILE_WITHIN_ENVELOPE = "profile_within_envelope"
_REASON_VERSIONS_MATCH = "hard_and_runtime_versions_match"
_REASON_ACTIVATION_ATOMIC = "activation_atomic"
_REASON_EXPIRY = "expiry_suspends_new_risk"
_REASON_TIME_UNVERIFIABLE = "time_health_not_trusted"


class SafetyProfileConfigError(Exception):
    """Raised when the envelope / profile / activation policy documents are missing,
    malformed, still carry an unfilled (named-TBD) required field, or fail the kernel
    record's own schema validation (``extra="forbid"`` / type checks) — fail-closed at
    construction, never a lazily-discovered ``None`` inside :meth:`SafetyProfileService
    .clear`."""


class TimeHealthSource(Protocol):
    """The one-method injected time port this service needs (module docstring). Any
    object exposing ``health_state() -> HealthState`` satisfies it —
    ``tos_runtime.time.service.TrustworthyTimeService`` already does, via its
    ``health_state`` property read as a zero-arg callable is NOT what this Protocol
    demands; a caller wires ``lambda: time_service.health_state`` (a property access) or
    a thin adapter. This service performs no time arithmetic of its own (module
    docstring)."""

    def health_state(self) -> HealthState:
        """Return the current trustworthy-time health state."""
        ...


def _tri_and(*values: bool | None) -> bool | None:
    """Combine tri-state (``True``/``False``/``None``) values with a fail-closed AND.

    A positively-established ``False`` dominates (a real violation is never softened to
    "unknown" merely because a sibling check is unevaluable); absent any ``False``, any
    ``None`` makes the combination ``None``; only all-``True`` yields ``True``.
    """
    if any(v is False for v in values):
        return False
    if any(v is None for v in values):
        return None
    return True


@dataclass(frozen=True)
class _LoadedDocuments:
    """The three validated kernel records + their source paths + raw digests-in-waiting
    (this service holds no digest computation of its own — ``describe()`` reports the
    documents it loaded, not a recomputed artifact digest)."""

    envelope: HardSafetyEnvelope
    profile: RuntimeSafetyProfile
    activation: ActivationRecord
    not_expired: bool
    envelope_path: Path
    profile_path: Path
    activation_path: Path


def _validate_record(model: type[Any], raw: dict[str, Any], path: Path) -> Any:
    """``model.model_validate(raw)``, wrapping a pydantic ``ValidationError`` into
    :class:`SafetyProfileConfigError` (fail-closed, never a bare pydantic error leaking
    past this module's boundary)."""
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        raise SafetyProfileConfigError(
            f"{path}: does not satisfy {model.__name__} — {exc}"
        ) from exc


def _load_documents(
    envelope_path: Path, profile_path: Path, activation_path: Path
) -> _LoadedDocuments:
    envelope_raw = load_yaml_document(envelope_path, SafetyProfileConfigError)
    envelope_body = require_mapping_field(
        envelope_raw, "envelope", envelope_path, SafetyProfileConfigError
    )
    envelope = _validate_record(HardSafetyEnvelope, envelope_body, envelope_path)

    profile_raw = load_yaml_document(profile_path, SafetyProfileConfigError)
    profile_body = require_mapping_field(
        profile_raw, "profile", profile_path, SafetyProfileConfigError
    )
    profile = _validate_record(RuntimeSafetyProfile, profile_body, profile_path)

    activation_raw = load_yaml_document(activation_path, SafetyProfileConfigError)
    activation_body = require_mapping_field(
        activation_raw, "activation", activation_path, SafetyProfileConfigError
    )
    activation = _validate_record(ActivationRecord, activation_body, activation_path)
    not_expired = require_bool_field(
        activation_raw, "not_expired", activation_path, SafetyProfileConfigError
    )

    return _LoadedDocuments(
        envelope=envelope,
        profile=profile,
        activation=activation,
        not_expired=not_expired,
        envelope_path=envelope_path,
        profile_path=profile_path,
        activation_path=activation_path,
    )


class SafetyProfileService:
    """The SAFETY_ENVELOPE_PROFILE :class:`~tos_runtime.safety.ports.SafetyMeshService`
    (module docstring). Construction loads and validates all three policy documents —
    a missing / still-null / schema-invalid document refuses construction outright
    (never a ``None`` service instance)."""

    def __init__(
        self,
        *,
        envelope_path: Path,
        profile_path: Path,
        activation_path: Path,
        time_source: TimeHealthSource | None = None,
        software_deployment_ok: bool | None = None,
    ) -> None:
        """Load + validate the three policy documents, fail-closed.

        Args:
            envelope_path: Path to a Hard Safety Envelope YAML document (top-level key
                ``envelope``).
            profile_path: Path to a Runtime Safety Profile YAML document (top-level key
                ``profile``).
            activation_path: Path to an Activation Record YAML document (top-level keys
                ``activation`` + the ``not_expired`` operator attestation).
            time_source: The injected time-health port (module docstring
                :class:`TimeHealthSource`); ``None`` means this service can never
                establish time-verifiability, so :meth:`clear` reports ``None`` whenever
                no sibling check has already positively failed.
            software_deployment_ok: The injected Phase 5 W4
                ``tos_runtime.release.admission.release_admission`` verdict (ADR-002-029
                step 8; :class:`~tos.spg.SemanticValidationInputs.software_deployment_ok`)
                — ``None`` when this fact is not yet available at construction time
                (e.g. release admission has not run yet), never a fabricated ``True``.

        Raises:
            SafetyProfileConfigError: Any document is missing, unreadable, not valid
                YAML, not a mapping, missing a required field, still null (named-TBD),
                or fails the kernel record's own schema validation.
        """
        self._docs = _load_documents(envelope_path, profile_path, activation_path)
        self._time_source = time_source
        self._software_deployment_ok = software_deployment_ok

    @property
    def identity(self) -> str:
        return _IDENTITY

    @property
    def dimension_key(self) -> DimensionKey:
        return DimensionKey.SAFETY_ENVELOPE_PROFILE

    def _time_verifiable(self) -> bool | None:
        """``True`` only when the injected time port reports ``TRUSTED``; ``None``
        (unevaluable) otherwise — the plan's own worked example of a fact this service
        cannot establish (module docstring)."""
        if self._time_source is None:
            return None
        if self._time_source.health_state() is HealthState.TRUSTED:
            return True
        return None

    def _activation_inputs(self) -> ActivationInputs:
        envelope = self._docs.envelope
        profile = self._docs.profile
        activation = self._docs.activation

        version_fully_active = (
            envelope.envelope_generation is not None
            and profile.target_envelope_generation is not None
            and profile.target_envelope_generation == envelope.envelope_generation
            and profile.profile_generation is not None
            and activation.profile_generation is not None
            and activation.profile_generation == profile.profile_generation
        )
        bundle = SafetyConfigurationBundle(envelope=envelope, profile=profile)
        return ActivationInputs(
            version_fully_active=version_fully_active,
            mixed_versions_present=False,
            units_compatible=units_compatible(
                bundle,
                SemanticValidationInputs(
                    software_deployment_ok=self._software_deployment_ok
                ),
            ),
            envelope_bounded=envelope_bounded(envelope, profile),
            staging_complete=bool(activation.approval_ids),
            attestation_complete=bool(activation.compatibility_attestation_refs),
        )

    def clear(self) -> MeshClearance:
        """The deferred-item / Coordinator verdict (module docstring)."""
        envelope = self._docs.envelope
        profile = self._docs.profile
        activation = self._docs.activation

        reasons: list[str] = []

        validity = profile_within_envelope(envelope, profile).valid
        if validity is not True:
            reasons.append(_REASON_PROFILE_WITHIN_ENVELOPE)

        versions_match = hard_and_runtime_versions_match(
            envelope, profile, activation, mixed_versions_present=False
        )
        if versions_match is not True:
            reasons.append(_REASON_VERSIONS_MATCH)

        activation_verdict = activation_atomic(self._activation_inputs())
        activation_ok = activation_verdict is ActivationVerdict.COMMITTABLE
        if not activation_ok:
            reasons.append(_REASON_ACTIVATION_ATOMIC)

        time_verifiable = self._time_verifiable()
        if time_verifiable is None:
            expiry_ok: bool | None = None
            reasons.append(_REASON_TIME_UNVERIFIABLE)
        else:
            suspended = expiry_suspends_new_risk(
                not_expired=self._docs.not_expired, time_verifiable=time_verifiable
            )
            expiry_ok = not suspended
            if not expiry_ok:
                reasons.append(_REASON_EXPIRY)

        overall = _tri_and(validity, versions_match, activation_ok, expiry_ok)
        if overall is True:
            reasons = []
        return MeshClearance(
            identity=self.identity, clear=overall, reasons=tuple(reasons)
        )

    def dimension_report(self) -> DimensionReport | None:
        """This owner's currentness verdict for SAFETY_ENVELOPE_PROFILE (module
        docstring). ``restrictive_floor`` is ``0`` — a **deliberate** statement, not an
        invented default: Phase 2/5 has no floor-governance runtime for this dimension
        yet (the same "an owner reporting 0 is that owner's own choice" discipline
        :class:`~tos_runtime.currentness.vector.DimensionReport`'s own docstring
        states)."""
        return DimensionReport(
            bound_generation=active_envelope_generation(self._docs.envelope),
            positively_established=self.clear().clear is True,
            restrictive_floor=0,
        )

    def describe(self) -> dict[str, Any]:
        """Evidence-facing description of the loaded policy documents — names,
        generations, and version identifiers only; never a secret / bearer token
        (:class:`~tos_runtime.safety.ports.SafetyMeshService.describe` contract)."""
        envelope = self._docs.envelope
        profile = self._docs.profile
        activation = self._docs.activation
        return {
            "identity": self.identity,
            "envelope_path": str(self._docs.envelope_path),
            "envelope_id": envelope.envelope_id,
            "envelope_generation": envelope.envelope_generation,
            "envelope_version": (
                envelope.envelope_version.version
                if envelope.envelope_version is not None
                else None
            ),
            "profile_path": str(self._docs.profile_path),
            "profile_id": profile.profile_id,
            "profile_generation": profile.profile_generation,
            "profile_version": (
                profile.profile_version.version
                if profile.profile_version is not None
                else None
            ),
            "activation_path": str(self._docs.activation_path),
            "activation_id": activation.activation_id,
            "not_expired": self._docs.not_expired,
        }
