"""Broker Capability Profile INSTANCE loader (Phase 4 plan §2 decision 3).

Loads the non-normative KIS Broker Capability Profile INSTANCE draft
(``docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml``) into the
kernel's :class:`~tos.brokercap.records.BrokerCapabilityProfile` record, per
``docs/plans/2026-09-09-tos-phase4-scopes-and-verify-realization-plan.md`` §2
decision 3 ("INSTANCE 소비").

**Why this exists.** The kernel's ``tos.brokercap`` predicates
(:func:`~tos.brokercap.predicates.capability_admissible` and friends) have,
until now, only ever been exercised against synthetic test fixtures. This
loader lets them judge a *real* (draft, unapproved) broker instance, so the
dishonest-admissible-by-omission failure mode ("we never actually ran the
predicate against real data") cannot hide. The instance is ``status: DRAFT``
with ``approvers: []`` and zero ``VERIFIED`` declarations, so every
broker-reaching admissibility check comes back ``PROHIBITED`` — that is the
*correct*, honest verdict for an unapproved draft, not a bug in this loader.

**``_model_view`` discipline — the one rule this module never breaks.** The
draft YAML's schema spine is a *template* whose key names / vocabulary
sometimes diverge from the brokercap kernel model (recorded in
``docs/plans/2026-07-29-tos-broker-capability-profile-kis-draft.md`` §6).
Every genuinely model-shaped block in the draft carries a sibling
``_model_view`` mapping whose keys are the kernel record's own field names
and whose values are already the model's own vocabulary spelling. This
module reads **only** ``_model_view`` blocks (plus the four
``profile_identity`` scalars named below) — it never reads a template-shaped
key to construct a kernel value, and it never "fixes" a divergent spelling
(e.g. the template's ``CLASS-D`` / ``EV-L1`` style abbreviations). A block
that is supposed to carry a ``_model_view`` but does not is a refusal, not a
silent default — see :class:`BrokerInstanceConfigError`.

**Constructed as ``DRAFT``, not issued.** The draft names its own
canonicalization/digest fields ``TBD`` (§9.2 item 2 gate, unresolved) and its
``conformance_class`` has no ``_model_view`` counterpart anywhere in the file
(it is a ``BrokerCapabilityProfile``-level field, not a ``LiveScope`` field,
and the template only records it as an abbreviated, non-model-spelled
scalar — a genuine template/model gap, not one this loader may paper over).
Both facts are exactly what the kernel's ``ArtifactStatus.DRAFT`` lifecycle
state represents: pre-issuance, digest not yet computed, required-covered
completeness deferred. Every profile this loader builds is therefore
constructed with ``status=ArtifactStatus.DRAFT`` and
``conformance_class=None`` — never invented, never issued.

**Read-only.** This module opens the instance file for reading only; it
never writes to ``docs/broker-profiles/`` (non-normative, byte-immutable
input) and reads no environment variable.

Pure-ish module: ``pyyaml`` (an existing kernel/runtime dependency) + stdlib
+ ``tos.brokercap`` + ``tos.canonical`` only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from tos.brokercap.predicates import profile_version_current
from tos.brokercap.records import (
    BrokerCapabilityProfile,
    CapabilityDeclaration,
    FinalQuantityProofRule,
    LiveScope,
    ProfileKey,
    ProfileVersion,
)
from tos.brokercap.routing import CapabilityProvenance, ProvenanceClass
from tos.brokercap.vocabulary import (
    AssuranceLevel,
    AssuranceSource,
    CapabilityDimension,
    CapabilityStatus,
    ProhibitedProof,
)
from tos.canonical import ArtifactStatus

__all__ = [
    "BrokerInstanceConfigError",
    "InstanceDocument",
    "instance_version_current",
    "load_instance_document",
    "load_instance_documents",
    "select_document",
]


class BrokerInstanceConfigError(Exception):
    """The instance file is missing/unreadable/malformed, or a block that
    must carry a ``_model_view`` mapping does not, or a ``_model_view`` value
    is not an exact kernel-vocabulary enum member. Fail-closed at load: this
    module never invents a value to paper over a gap (module docstring)."""


@dataclass(frozen=True)
class InstanceDocument:
    """One parsed Broker Capability Profile INSTANCE document (plan §2 decision 3).

    Attributes:
        artifact_id: The document's own ``profile_identity.artifact_id`` scalar.
        environment: The document's own ``profile_identity.environment`` scalar.
        status: The document's own ``profile_identity.status`` scalar (e.g. ``"DRAFT"``).
        approvers: The document's own ``profile_identity.approvers`` list, as a tuple.
        profile: The constructed kernel :class:`BrokerCapabilityProfile` (``DRAFT``).
        declared_dimensions: Every :class:`CapabilityDimension` that has a declaration
            in this document (regardless of status — "declared" is not "verified").
        verified_dimensions: The subset of ``declared_dimensions`` whose declaration
            status is :attr:`~tos.brokercap.vocabulary.CapabilityStatus.VERIFIED`.
        provenance: The :class:`CapabilityProvenance` records this document's
            ``assurance_sources`` map to through the closed
            :data:`_ASSURANCE_SOURCE_TO_PROVENANCE_CLASS` table.
        unmapped_sources: The ``assurance_sources`` values this document declares
            that the closed table does not map to any :class:`ProvenanceClass`
            (e.g. a probe-derived source with no :class:`~tos.brokercap.routing.ProbeManifest`
            behind it) — reported rather than fabricated (module docstring).
    """

    artifact_id: str | None
    environment: str | None
    status: str | None
    approvers: tuple[str, ...]
    profile: BrokerCapabilityProfile
    declared_dimensions: frozenset[CapabilityDimension]
    verified_dimensions: frozenset[CapabilityDimension]
    provenance: tuple[CapabilityProvenance, ...]
    unmapped_sources: tuple[str, ...]


# ===========================================================================
# AssuranceSource -> ProvenanceClass — closed table (plan §2 decision 3 / 작업 3)
#
# Every row is a deliberate judgment over the ADR-002-004 §5.4 assurance-source
# meaning (vocabulary.py:160-176), never an invented correspondence. A source
# with no fitting closed-vocabulary class maps to `None` (unmapped) rather than
# being forced into the nearest class — see `_provenance_for_source` below.
# ===========================================================================

_ASSURANCE_SOURCE_TO_PROVENANCE_CLASS: dict[AssuranceSource, ProvenanceClass | None] = {
    # A published broker specification IS the broker's published documentation.
    AssuranceSource.OFFICIAL_SPECIFICATION: ProvenanceClass.OFFICIAL_DOCUMENT,
    # A formal broker statement is likewise a broker-issued document, not a
    # measurement of the broker's live behavior.
    AssuranceSource.BROKER_CONTRACTUAL_STATEMENT: ProvenanceClass.OFFICIAL_DOCUMENT,
    # A support confirmation is a broker-issued statement (email/ticket text),
    # not a measurement — the same document-class treatment as the two rows above.
    AssuranceSource.BROKER_SUPPORT_CONFIRMATION: ProvenanceClass.OFFICIAL_DOCUMENT,
    # A sandbox test is an active behavioral measurement — the nearest closed
    # class is CONTROLLED_GET_PROBE, but that class is validator-locked to a
    # non-order-emitting GET probe with a ProbeManifest (routing.py); the real
    # sandbox tests this draft cites explicitly SEND orders, so mapping here
    # would misrepresent the manifest's own `emits_orders: False` seal. Unmapped.
    AssuranceSource.CONTROLLED_SANDBOX_TEST: None,
    # A production probe is the literal CONTROLLED_GET_PROBE shape in spirit,
    # but that class requires a concrete ProbeManifest (validator-enforced);
    # this instance layer builds no manifest (P0-2 probe-gate work, out of
    # this slice). Unmapped rather than fabricate a manifest.
    AssuranceSource.CONTROLLED_PRODUCTION_PROBE: None,
    # An active behavioral measurement with no counterpart in the closed
    # 4-member ProvenanceClass vocabulary at all. Unmapped.
    AssuranceSource.FAULT_INJECTION_RESULT: None,
    # A passive live observation — not a document, not our internal client,
    # not a manifested probe. Unmapped.
    AssuranceSource.OBSERVED_LIVE_EVIDENCE: None,
    # A third-party independent review is neither the broker's own
    # document/SDK nor our internal client nor a manifested probe. Unmapped.
    AssuranceSource.INDEPENDENT_OPERATIONAL_REVIEW: None,
}

#: ProfileKey field names read from `profile_identity._model_view` (records.py:59-68).
_PROFILE_KEY_FIELDS = (
    "broker_id",
    "api_product",
    "api_version",
    "environment",
    "account_type",
    "market",
    "instrument_class",
    "order_type",
    "session_type",
    "credential_scope",
)

#: LiveScope field names read from `live_scope._model_view` (records.py:125-132).
_LIVE_SCOPE_FIELDS = (
    "account_scope",
    "instrument_scope",
    "order_type_scope",
    "quantity_risk_limit",
    "session_scope",
    "action_classes",
    "mode",
    "reduced_off_unattended_partition_protection",
)

#: The reserved template placeholder for an unfilled required field (never a value).
_TBD = "TBD"


def _tbd_to_none(value: Any) -> Any:
    """Map the template's ``"TBD"`` placeholder to ``None`` (never a value)."""
    return None if value == _TBD else value


def _require_dict(raw: Any, key: str, *, context: str) -> dict[str, Any]:
    block = raw.get(key) if isinstance(raw, dict) else None
    if not isinstance(block, dict):
        raise BrokerInstanceConfigError(
            f"{context}: missing or non-mapping {key!r} block — refusing to "
            "invent one"
        )
    return block


def _require_model_view(block: dict[str, Any], *, context: str) -> dict[str, Any]:
    model_view = block.get("_model_view")
    if not isinstance(model_view, dict):
        raise BrokerInstanceConfigError(
            f"{context}: block carries no `_model_view` mapping — this "
            "module reads only `_model_view` blocks (never a template-shaped "
            "key) and refuses to invent one"
        )
    return model_view


def _to_enum(enum_cls: type, value: Any, *, context: str) -> Any:
    """Coerce ``value`` to an exact member of ``enum_cls``, or fail closed.

    ``None`` passes through as ``None`` (an unspecified field, not an error);
    any other value must be an exact enum-member spelling — this module never
    "fixes" a divergent template spelling (module docstring).
    """
    if value is None:
        return None
    try:
        return enum_cls(value)
    except ValueError as exc:
        raise BrokerInstanceConfigError(
            f"{context}: {value!r} is not a valid {enum_cls.__name__} member "
            "— the `_model_view` value must already be exact kernel "
            "vocabulary; this module does not translate template spellings"
        ) from exc


def _build_profile_key(profile_identity: dict[str, Any], *, context: str) -> ProfileKey:
    model_view = _require_model_view(
        profile_identity, context=f"{context}.profile_identity"
    )
    kwargs = {name: model_view.get(name) for name in _PROFILE_KEY_FIELDS}
    try:
        return ProfileKey(**kwargs)
    except Exception as exc:  # pydantic ValidationError, wrapped for callers
        raise BrokerInstanceConfigError(
            f"{context}: profile_identity._model_view did not build a valid "
            f"ProfileKey: {exc}"
        ) from exc


def _build_profile_version(profile_identity: dict[str, Any]) -> ProfileVersion:
    """Build ``ProfileVersion`` from the ``profile_identity`` scalars (not `_model_view`).

    Per plan §2 decision 3, ``profile_version`` / ``status`` / ``approvers`` /
    ``artifact_id`` / ``environment`` are read as plain scalars off
    ``profile_identity`` itself (they are not part of the 10-coordinate
    ``ProfileKey`` `_model_view`). ``approvers`` is a list, not the singular
    ``approver_identity`` string `ProfileVersion` carries — the first named
    approver is used when present (a genuine value, never invented); with no
    approvers (this draft's case) it stays ``None``.
    """
    approvers = profile_identity.get("approvers") or []
    approver_identity = approvers[0] if approvers else None
    return ProfileVersion(
        profile_version=_tbd_to_none(profile_identity.get("profile_version")),
        effective_date=_tbd_to_none(profile_identity.get("effective_from")),
        evidence_package_version=_tbd_to_none(
            profile_identity.get("evidence_package_version")
        ),
        approver_identity=approver_identity,
        expiration_or_revalidation_date=_tbd_to_none(
            profile_identity.get("expires_at")
        ),
        superseded_version_link=_tbd_to_none(
            profile_identity.get("superseded_version_link")
        ),
        change_reason=_tbd_to_none(profile_identity.get("change_reason")),
    )


def _build_live_scope(raw: dict[str, Any], *, context: str) -> LiveScope:
    live_scope_block = _require_dict(raw, "live_scope", context=context)
    model_view = _require_model_view(live_scope_block, context=f"{context}.live_scope")
    kwargs: dict[str, Any] = {}
    for name in _LIVE_SCOPE_FIELDS:
        value = model_view.get(name)
        if name == "action_classes":
            value = tuple(value) if value is not None else ()
        kwargs[name] = value
    try:
        return LiveScope(**kwargs)
    except Exception as exc:
        raise BrokerInstanceConfigError(
            f"{context}.live_scope: `_model_view` did not build a valid "
            f"LiveScope: {exc}"
        ) from exc


def _provenance_for_sources(
    sources: tuple[AssuranceSource, ...],
    *,
    source_ref: str,
    captured_at: str,
) -> tuple[tuple[CapabilityProvenance, ...], tuple[str, ...]]:
    """Map ``sources`` through the closed table, splitting mapped / unmapped."""
    produced: list[CapabilityProvenance] = []
    unmapped: list[str] = []
    for source in sources:
        provenance_class = _ASSURANCE_SOURCE_TO_PROVENANCE_CLASS.get(source)
        if provenance_class is None:
            unmapped.append(source.value)
            continue
        produced.append(
            CapabilityProvenance(
                provenance_class=provenance_class,
                source_ref=source_ref,
                captured_at=captured_at,
            )
        )
    return tuple(produced), tuple(unmapped)


def _build_declarations(
    raw: dict[str, Any], *, captured_at: str, context: str
) -> tuple[
    tuple[CapabilityDeclaration, ...],
    frozenset[CapabilityDimension],
    frozenset[CapabilityDimension],
    tuple[CapabilityProvenance, ...],
    tuple[str, ...],
]:
    capabilities = _require_dict(raw, "capabilities", context=context)
    declarations: list[CapabilityDeclaration] = []
    declared: set[CapabilityDimension] = set()
    verified: set[CapabilityDimension] = set()
    provenance: list[CapabilityProvenance] = []
    unmapped: list[str] = []

    for name, block in capabilities.items():
        block_context = f"{context}.capabilities.{name}"
        if not isinstance(block, dict):
            raise BrokerInstanceConfigError(
                f"{block_context}: capability block is not a mapping"
            )
        model_view = _require_model_view(block, context=block_context)

        # A `_model_view` with `dimension: null` is the memo §6-2 divergence:
        # a template-only key with no CapabilityDimension counterpart at all
        # (e.g. `account_margin_borrow_and_settlement_constraints`). Skip it —
        # this is a documented absence, not a missing `_model_view`.
        if model_view.get("dimension") is None:
            continue

        dimension = _to_enum(
            CapabilityDimension, model_view.get("dimension"), context=block_context
        )
        status = _to_enum(
            CapabilityStatus, model_view.get("status"), context=block_context
        )
        assurance_level = _to_enum(
            AssuranceLevel, model_view.get("assurance_level"), context=block_context
        )
        raw_sources = model_view.get("assurance_sources") or []
        sources = tuple(
            _to_enum(AssuranceSource, source, context=block_context)
            for source in raw_sources
        )

        declaration = CapabilityDeclaration(
            dimension=dimension,
            status=status,
            assurance_level=assurance_level,
            evidence_reference=model_view.get("evidence_reference"),
            restriction=model_view.get("restriction"),
            restriction_approved=model_view.get("restriction_approved"),
            fallback_reference=model_view.get("fallback_reference"),
            assurance_sources=sources,
        )
        declarations.append(declaration)
        declared.add(dimension)
        if status is CapabilityStatus.VERIFIED:
            verified.add(dimension)

        block_provenance, block_unmapped = _provenance_for_sources(
            sources, source_ref=name, captured_at=captured_at
        )
        provenance.extend(block_provenance)
        unmapped.extend(block_unmapped)

    return (
        tuple(declarations),
        frozenset(declared),
        frozenset(verified),
        tuple(provenance),
        tuple(unmapped),
    )


def _build_fqp_rules(
    raw: dict[str, Any], *, context: str
) -> tuple[FinalQuantityProofRule, ...]:
    """Build the Final Quantity Proof recipes from `final_quantity_proof.recipes[]`.

    The block is optional (plan §2 decision 3: "if present, else empty
    tuple"); when present, every recipe element must carry its own
    `_model_view` (the same discipline as every other block).
    """
    fqp_block = raw.get("final_quantity_proof")
    if not isinstance(fqp_block, dict):
        return ()
    recipes = fqp_block.get("recipes") or []
    rules: list[FinalQuantityProofRule] = []
    for index, recipe in enumerate(recipes):
        recipe_context = f"{context}.final_quantity_proof.recipes[{index}]"
        if not isinstance(recipe, dict):
            raise BrokerInstanceConfigError(
                f"{recipe_context}: recipe is not a mapping"
            )
        model_view = _require_model_view(recipe, context=recipe_context)
        prohibited = tuple(
            _to_enum(ProhibitedProof, proof, context=recipe_context)
            for proof in (model_view.get("prohibited_proofs") or [])
        )
        rules.append(
            FinalQuantityProofRule(
                order_type=model_view.get("order_type"),
                prohibited_proofs=frozenset(prohibited),
                no_later_change_asserted=model_view.get("no_later_change_asserted"),
                late_event_window_defined=model_view.get("late_event_window_defined"),
            )
        )
    return tuple(rules)


def _build_instance_document(
    raw: dict[str, Any], *, path: Path, index: int
) -> InstanceDocument:
    context = f"{path}[doc {index}]"
    profile_identity = _require_dict(raw, "profile_identity", context=context)
    profile_key = _build_profile_key(profile_identity, context=context)
    profile_version = _build_profile_version(profile_identity)
    live_scope = _build_live_scope(raw, context=context)

    artifact_id = profile_identity.get("artifact_id")
    captured_at = _tbd_to_none(profile_identity.get("effective_from")) or "UNKNOWN"

    (
        declarations,
        declared_dimensions,
        verified_dimensions,
        provenance,
        unmapped_sources,
    ) = _build_declarations(raw, captured_at=captured_at, context=context)
    fqp_rules = _build_fqp_rules(raw, context=context)

    profile = BrokerCapabilityProfile(
        status=ArtifactStatus.DRAFT,
        canonical_digest=None,
        canonicalization_version=None,
        profile_id=artifact_id,
        profile_key=profile_key,
        profile_version=profile_version,
        declarations=declarations,
        conformance_class=None,
        live_scope=live_scope,
        final_quantity_proof_rules=fqp_rules,
    )

    approvers_raw = profile_identity.get("approvers") or []
    return InstanceDocument(
        artifact_id=artifact_id,
        environment=profile_identity.get("environment"),
        status=profile_identity.get("status"),
        approvers=tuple(approvers_raw),
        profile=profile,
        declared_dimensions=declared_dimensions,
        verified_dimensions=verified_dimensions,
        provenance=provenance,
        unmapped_sources=unmapped_sources,
    )


def load_instance_documents(path: Path) -> tuple[InstanceDocument, ...]:
    """Load every YAML document in the Broker Capability Profile INSTANCE file at ``path``.

    Reads ``path`` for content only (never writes to it — the file is a
    non-normative, byte-immutable instance authored by the P0-2 track). Every
    document must independently satisfy the ``_model_view`` discipline
    (module docstring); the first document that does not raises
    :class:`BrokerInstanceConfigError` naming the offending block — there is
    no partial-success return (fail-closed: a whole file with one bad
    document is not silently reported as "loaded").

    Args:
        path: The instance YAML file (e.g.
            ``docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml``).

    Returns:
        One :class:`InstanceDocument` per YAML document, in file order.

    Raises:
        BrokerInstanceConfigError: The file is missing/unreadable/not valid
            YAML/not a sequence of mappings, or any document is missing a
            required ``_model_view`` block or carries a non-enum vocabulary
            value.
    """
    if not path.is_file():
        raise BrokerInstanceConfigError(
            f"broker profile instance file not found: {path}"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BrokerInstanceConfigError(
            f"broker profile instance file could not be read: {path}"
        ) from exc
    try:
        raw_docs = list(yaml.safe_load_all(text))
    except yaml.YAMLError as exc:
        raise BrokerInstanceConfigError(
            f"broker profile instance file is not valid YAML: {path}"
        ) from exc

    documents: list[InstanceDocument] = []
    for index, raw in enumerate(raw_docs):
        if not isinstance(raw, dict):
            raise BrokerInstanceConfigError(
                f"{path}[doc {index}]: top-level YAML document must be a mapping"
            )
        documents.append(_build_instance_document(raw, path=path, index=index))
    return tuple(documents)


def load_instance_document(path: Path, *, environment: str) -> InstanceDocument:
    """Load and build ONLY the single document in ``path`` whose own
    ``profile_identity.environment`` scalar equals ``environment`` (plan §2
    decision 4, item 6/12 realization).

    Selection reads each raw YAML document's ``profile_identity.environment``
    scalar directly (before any ``_model_view``/kernel construction) so a
    NON-matching document's own defects (e.g. a missing ``_model_view``
    block) never block loading the one document actually being asked for —
    :func:`load_instance_documents` stays the strict, "every document must be
    valid" loader; this is the single-document, environment-scoped sibling
    plan §2 decision 4 needs to bind one active scope to one INSTANCE
    document without paying for every other document's validity.

    Args:
        path: The instance YAML file (e.g.
            ``docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml``).
        environment: The exact ``profile_identity.environment`` value to select.

    Returns:
        The single matching document, fully built (module docstring discipline).

    Raises:
        BrokerInstanceConfigError: The file is missing/unreadable/not valid
            YAML, zero or more than one raw document names ``environment``,
            or the ONE matching document fails the ``_model_view`` discipline.
    """
    if not path.is_file():
        raise BrokerInstanceConfigError(
            f"broker profile instance file not found: {path}"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BrokerInstanceConfigError(
            f"broker profile instance file could not be read: {path}"
        ) from exc
    try:
        raw_docs = list(yaml.safe_load_all(text))
    except yaml.YAMLError as exc:
        raise BrokerInstanceConfigError(
            f"broker profile instance file is not valid YAML: {path}"
        ) from exc

    matches = [
        (index, raw)
        for index, raw in enumerate(raw_docs)
        if isinstance(raw, dict)
        and isinstance(raw.get("profile_identity"), dict)
        and raw["profile_identity"].get("environment") == environment
    ]
    if len(matches) != 1:
        raise BrokerInstanceConfigError(
            f"{path}: expected exactly one raw document with "
            f"profile_identity.environment={environment!r}, found {len(matches)}"
        )
    index, raw = matches[0]
    return _build_instance_document(raw, path=path, index=index)


def select_document(
    documents: tuple[InstanceDocument, ...], *, environment: str
) -> InstanceDocument:
    """Select the single ``documents`` entry whose ``environment`` matches exactly.

    Args:
        documents: The loaded instance documents (e.g. from
            :func:`load_instance_documents`).
        environment: The exact ``profile_identity.environment`` value to match.

    Returns:
        The single matching document.

    Raises:
        BrokerInstanceConfigError: Zero or more than one document matches.
    """
    matches = [
        document for document in documents if document.environment == environment
    ]
    if len(matches) != 1:
        raise BrokerInstanceConfigError(
            f"expected exactly one instance document for environment={environment!r}, "
            f"found {len(matches)}"
        )
    return matches[0]


def instance_version_current(
    document: InstanceDocument, *, degraded_since_authorization: bool | None
) -> bool:
    """Whether ``document``'s profile version is current (plan §2 decision 3).

    The loader supplies genuine document data as the kernel
    :func:`~tos.brokercap.predicates.profile_version_current` predicate's
    inputs; the predicate is what judges "current" — this function makes no
    independent approval judgment of its own. The predicate's four kernel
    inputs, and which value/field feeds each (independent-review finding
    F5 — ``degraded_since_authorization`` used to be hardcoded ``None``,
    making the predicate's degradation gate unconditionally deny regardless
    of caller input; it is now a genuine, caller-supplied fact so the gate
    is load-bearing):

    * ``active_version`` — the *approved* active version. An approval act is
      what makes a version "active" (ADR-002-004 §7.2), so with an empty
      ``approvers`` tuple there is no approved active version to name at
      all: ``active_version`` is the document's own presented version only
      when ``approvers`` is non-empty, else ``None`` (the predicate's own
      ``active_version is None`` branch then denies — no separate "is
      approved" check is invented here).
    * ``presented_version`` — the document's own ``profile.profile_version.
      profile_version`` string.
    * ``not_expired`` — ``document.status != "EXPIRED"``, the only expiry
      signal this instance layer carries.
    * ``degraded_since_authorization`` — the CALLER-SUPPLIED
      ``degraded_since_authorization`` argument, passed straight through.
      The caller (:func:`~tos_runtime.brokercap.derive.derive_item6_item12`)
      feeds this from the active scope's own
      :attr:`~tos_runtime.brokercap.scopes.ScopeInstanceBinding.
      degraded_since_authorization` config field — an operator attestation,
      not a value this function invents. ``None`` (unknown) fails closed at
      the predicate, exactly like every other unknown here.

    Args:
        document: The instance document under test.
        degraded_since_authorization: Whether the capability has degraded
            since its authorization act (``None`` => unknown => the
            predicate denies).

    Returns:
        ``True`` iff the kernel predicate judges the version current.
    """
    presented = (
        document.profile.profile_version.profile_version
        if document.profile.profile_version is not None
        else None
    )
    active = presented if document.approvers else None
    not_expired = document.status != "EXPIRED"
    return profile_version_current(
        active_version=active,
        presented_version=presented,
        not_expired=not_expired,
        degraded_since_authorization=degraded_since_authorization,
    )
