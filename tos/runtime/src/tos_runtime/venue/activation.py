"""tos_runtime.venue.activation — activation-exact-match against ``safety_activation.yaml``.

TOS venue constraint service wave, plan §2 decision 7, §4.1
(``docs/plans/2026-09-15-tos-venue-constraint-service-plan.md``).

**Policy activation is spg-owned, not venue-owned** (ADR-002-019 §5.1 line
111 / ADR-002-014 §3.5, cited verbatim on ``tos.venue.records
.VenueConstraintPolicy``'s own docstring): venue is the CONTENT author, spg
is the activation authority. This module realizes the runtime half of that
split with a document-level check rather than a full
``SafetyConfigurationBundle``/``bundle_complete`` reuse (plan §3 rejected
alternatives — reusing ``bundle_complete`` would feed the two new policies
into ``SafetyProfileService``'s existing ``activation_atomic``/
``units_compatible`` judgement as a side effect, which this wave does not
intend): it reads the SAME ``safety_activation.yaml`` document the existing
:mod:`tos_runtime.safety.profile` machinery reads, but a SEPARATE top-level
key (``members:``) that document does not otherwise use, and never reads any
other key of that document — this module never imports
:mod:`tos_runtime.safety.profile` and never touches the
``SafetyProfileService``'s own bundle construction.

Every entry under ``members:`` is validated into the kernel's own
``tos.spg.records.BundleMemberRef`` model via ``model_validate`` — the exact
5-coordinate shape (``kind``/``member_id``/``generation``/``digest``/
``resolved``/``immutable``) plan §2 decision 7 names, reused rather than
re-authored. A member counts as activated for one exact
``(kind, member_id, generation, digest)`` coordinate only when EXACTLY ONE
matching ref exists AND that ref is positively ``resolved is True`` AND
positively ``immutable is True`` — an absent match, a coordinate mismatch, a
duplicate match, or a non-``True`` resolved/immutable flag all refuse
(fail-closed; ADR-014 §13 SPG-INV-002 "an unresolved / floating / mutable
member cannot create new-risk authority").

Firewall (R1, runtime scope): stdlib + ``pyyaml`` + ``tos.spg`` only — no
``shared.*``, no ``tos_runtime.safety.profile``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError
from tos.spg import BundleMemberKind, BundleMemberRef

__all__ = [
    "ActivationMembersConfigError",
    "PolicyNotActivated",
    "load_activation_members",
    "require_member_activated",
]


class ActivationMembersConfigError(RuntimeError):
    """The activation document is missing/unreadable/not valid YAML/not a
    mapping, its ``members`` key is absent or ``null`` (named-TBD), the key
    is not an explicit list, or one entry does not validate into the kernel's
    ``BundleMemberRef`` shape — fail-closed, never a silent empty list."""


class PolicyNotActivated(RuntimeError):
    """No exactly-one, positively resolved+immutable ``BundleMemberRef``
    matches the requested ``(kind, member_id, generation, digest)`` coordinate
    — see :func:`require_member_activated`."""


def load_activation_members(activation_path: Path) -> tuple[BundleMemberRef, ...]:
    """Load the ``members:`` list of ``activation_path`` (a
    ``safety_activation.yaml``-shaped document) into kernel ``BundleMemberRef``
    records.

    Raises:
        ActivationMembersConfigError: the file is missing/unreadable/not
            valid YAML/not a mapping; the ``members`` key is absent, ``null``,
            or not an explicit list; or an entry fails
            ``BundleMemberRef.model_validate``.
    """
    if not activation_path.is_file():
        raise ActivationMembersConfigError(
            f"activation config file not found: {activation_path}"
        )
    try:
        text = activation_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ActivationMembersConfigError(
            f"activation config file could not be read: {activation_path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ActivationMembersConfigError(
            f"activation config file is not valid YAML: {activation_path}"
        ) from exc
    if not isinstance(raw, dict):
        raise ActivationMembersConfigError(
            f"{activation_path}: activation config must be a top-level mapping"
        )
    if "members" not in raw or raw["members"] is None:
        raise ActivationMembersConfigError(
            f"{activation_path}: 'members' key is missing or still null "
            "(named-TBD) — an activation document must explicitly declare "
            "its member list, [] included, to admit 'nothing is activated'"
        )
    members_raw: Any = raw["members"]
    if not isinstance(members_raw, list):
        raise ActivationMembersConfigError(
            f"{activation_path}: 'members' must be an explicit list"
        )
    members: list[BundleMemberRef] = []
    for i, entry in enumerate(members_raw):
        try:
            member = BundleMemberRef.model_validate(entry)
        except ValidationError as exc:
            raise ActivationMembersConfigError(
                f"{activation_path}: members[{i}] does not validate as a "
                f"BundleMemberRef: {exc}"
            ) from exc
        members.append(member)
    return tuple(members)


def _match_reason(
    ref: BundleMemberRef,
    *,
    kind: BundleMemberKind,
    member_id: str,
    generation: int,
    digest: str,
) -> str | None:
    """The first coordinate at which ``ref`` fails to match, or ``None`` when
    it matches every coordinate (resolved/immutable included)."""
    if ref.kind is not kind:
        return f"kind {ref.kind!r} != {kind!r}"
    if ref.member_id != member_id:
        return f"member_id {ref.member_id!r} != {member_id!r}"
    if ref.generation != generation:
        return f"generation {ref.generation!r} != {generation!r}"
    if ref.digest != digest:
        return f"digest {ref.digest!r} != {digest!r}"
    if ref.resolved is not True:
        return f"resolved is not True (got {ref.resolved!r})"
    if ref.immutable is not True:
        return f"immutable is not True (got {ref.immutable!r})"
    return None


def require_member_activated(
    members: tuple[BundleMemberRef, ...],
    *,
    kind: BundleMemberKind,
    member_id: str,
    generation: int,
    digest: str,
) -> BundleMemberRef:
    """Return the activated ``BundleMemberRef`` for the exact
    ``(kind, member_id, generation, digest)`` coordinate, or raise
    :class:`PolicyNotActivated`.

    A member is activated iff EXACTLY ONE entry of ``members`` has
    ``kind is kind`` AND ``member_id == member_id`` AND
    ``generation == generation`` AND ``digest == digest`` AND
    ``resolved is True`` AND ``immutable is True``. Any other case — absent,
    any single-coordinate mismatch, two matches, or a non-``True``
    resolved/immutable flag — raises with a reason naming which coordinate
    failed (or, for the two-match case, that the match set is not exactly
    one).

    Raises:
        PolicyNotActivated: no exactly-one matching, positively
            resolved+immutable member exists.
    """
    exact_matches = [
        ref
        for ref in members
        if _match_reason(
            ref, kind=kind, member_id=member_id, generation=generation, digest=digest
        )
        is None
    ]
    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(exact_matches) > 1:
        raise PolicyNotActivated(
            f"activation refused for kind={kind!r} member_id={member_id!r} "
            f"generation={generation!r} digest={digest!r}: {len(exact_matches)} "
            "distinct members match the exact coordinate (expected exactly one)"
        )
    reasons = [
        f"members[{i}]: {_match_reason(ref, kind=kind, member_id=member_id, generation=generation, digest=digest)}"
        for i, ref in enumerate(members)
        if ref.kind is kind
    ]
    detail = "; ".join(reasons) if reasons else "no member declares this kind at all"
    raise PolicyNotActivated(
        f"activation refused for kind={kind!r} member_id={member_id!r} "
        f"generation={generation!r} digest={digest!r}: {detail}"
    )
