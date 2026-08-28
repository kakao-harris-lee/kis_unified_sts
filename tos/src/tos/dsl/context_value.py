"""The env-value carrier shape — ``ContextValue`` / ``ContextValueView`` (design #32 §2.2 F1).

**Why the shape lives in ``tos.dsl`` and not in ``tos.marketfeed``** (design #32 §2.2 MAJOR-1).
The DSL owns the environment shape: :func:`~tos.dsl.vocabulary.resolve_operand` navigates it and
:data:`~tos.dsl.vocabulary.ADMISSIBLE_CONTEXT_SOURCES` names its sources. If the carrier type lived
in ``tos.marketfeed``, then ``DecisionTickPayload.value_view`` would force ``tos.engine.records`` to
import ``tos.marketfeed`` at runtime — breaching the committed engine import-closure allowlist
(fourteen packages, ``tos/tests/engine/test_engine_import_closure.py:59-76``, ``marketfeed`` absent)
and creating an ``engine -> marketfeed -> engine`` cycle. With the shape here, the existing
``engine -> dsl`` (``records.py:28-33``) and ``dsl -> capsule`` (``determinism.py:35``) edges carry
everything: **no** ``dsl -> marketfeed`` and **no** ``engine -> marketfeed`` edge exists, so the
cycle has no origin (design #32 §3.4).

**Ownership split.** ``tos.dsl`` owns the *shape*, the environment assembly, and the recorded
signature; ``tos.marketfeed`` owns *production and verification* — value ⟺ covered ``payload_digest``
binding, the VALID gate, and the canonical digest of the value set (design #32 §2.2/§3.2).

**A lean container, deliberately.** Every field here is a primitive (``str`` / ``int`` /
:data:`~tos.dsl.vocabulary.ScalarValue`); no ``tos.capsule`` type is imported. In particular a
``ContextValue`` carries **no** ``field_state``: the VALID gate (``worst`` of admission state,
observation state, and the matching field evaluations, with an explicit ``UNKNOWN`` floor for the
empty case) is applied by the ``tos.marketfeed`` producer, so ``ContextValueView.values`` is
**VALID by construction** (design #32 §2.2). A carrier that re-declared its own state would be a
self-report competing with the snapshot governance that already decided it (구조 파생 > 자기신고).

⚠ **Trust seam, stated plainly** (design #32 §2.3 MAJOR-2b / Gap-1). The value ⟺ digest binding is
verified **at production time** by ``tos.marketfeed``. The environment-injection point
(:func:`~tos.dsl.determinism.build_environment`) does **not** re-verify it — it consumes the
published view. A buggy or dishonest producer that publishes a value inconsistent with its
``payload_digest`` is therefore not caught here. What *is* structural is detection: a different value
set yields a different :attr:`ContextValueView.canonical_digest`, which
:func:`~tos.dsl.determinism.evaluate_resolved` appends to the recorded signature, so replay/audit
sees a different signature (design #32 §3.2 (3b)). Complete enforcement is the upstream Context
Integrity Service's (design #32 §0.2-4). No over-claim is made here.

⚠ **Provisional; closes no EV** (design #32 §1.1). The digest this carrier records rides
``ev-l1-provisional-0``, which is explicitly non-production.

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #1 §3.2). No clock, no RNG, no network.
"""

from __future__ import annotations

from pydantic import model_validator

from tos.dsl._base import ArtifactIntegrityError, FrozenModel
from tos.dsl.candidate import WILDCARD_TOKENS
from tos.dsl.vocabulary import ScalarValue

__all__ = [
    "VALUE_NAMESPACE",
    "ContextValue",
    "ContextValueView",
    "is_wildcard_field_key",
]

#: The reserved key under which a resolved value set is merged into ``env["capsule"]``
#: (design #32 §3.2 (1)). It SHALL stay structurally disjoint from the
#: :class:`~tos.capsule.DecisionContextCapsule` ``model_dump(mode="json")`` top-level key set;
#: :func:`~tos.dsl.determinism.build_environment` refuses to merge on a collision rather than
#: overwriting a covered Capsule field, and ``tos.marketfeed`` re-checks the disjointness
#: **structurally at publication time** (never as a declared constant list).
#:
#: A DSL reference therefore reads ``("capsule", "resolved_values", "<field_key>")`` — the
#: ``"capsule"`` source, so the D-E1 contract holds and no third context source is invented
#: (``vocabulary.py:88``; design #32 §3.2 alternative C rejected).
VALUE_NAMESPACE = "resolved_values"


def is_wildcard_field_key(field_key: str) -> bool:
    """Whether a ``field_key`` is a wildcard / "latest" form (design #32 §2.4).

    Reuses the shipped :data:`~tos.dsl.candidate.WILDCARD_TOKENS` set rather than re-authoring one
    (the ``tos.engine.records._is_wildcard_scope`` precedent, ``records.py:76-90``). RFC-008
    §7:239-240 prohibits a wildcard field reference on the authoring surface; a wildcard *value key*
    would reintroduce it from the environment side.

    Args:
        field_key: The candidate DSL-visible field name.

    Returns:
        ``True`` iff the key is a wildcard / "latest" form.
    """
    if field_key in WILDCARD_TOKENS:
        return True
    return "*" in field_key or field_key.lower() == "latest"


class ContextValue(FrozenModel):
    """One admitted Critical Input value as the DSL environment sees it (design #32 §2.2).

    Five primitives, each load-bearing:

    * ``field_key`` — the DSL-visible stable leaf name (the last component of an ``Operand.ref``).
      Concrete and wildcard-free (RFC-008 §7:239-240).
    * ``value`` — the admitted scalar. Ordering comparisons in the DSL are ``int`` / ``float`` only
      and exclude ``bool`` (``vocabulary.py:366-368``), which is why the producer exposes numerics
      as **integer tick/minor units** wherever an ordering comparison is intended (design #32 §2.5).
    * ``as_of`` — the value's recorded as-of / production time, taken from the attributed
      observation's ``time.source_event_time`` (``observation.py:85``). It anchors the Validity
      Window (design #2 §6.2 — never the capsule wrap time) **and** carries the per-bar distinctness
      load (design #32 §4.1): distinct bars carry distinct as-of times, and observations are a
      covered snapshot field (``snapshot.py:131``), so distinct bars yield distinct snapshot digests.
    * ``payload_digest`` — the value's *provenance* pointer, the attributed observation's
      ``raw.payload_digest`` (``observation.py:74``). The value is a scalar drawn from the payload
      that digest addresses, which is what makes it an attributed Critical Input rather than a side
      channel (RFC-004 §9:244; design #32 §2.3).
    * ``observation_ref`` — the attributed observation's raw-event identity, so the value's
      governance chain (admission, field evaluation, lineage) is structurally re-derivable.

    ``as_of`` is typed ``int`` and ``payload_digest`` / ``observation_ref`` are typed ``str``
    deliberately: an absent as-of or an absent provenance pointer makes the value
    **unconstructable**, which is the design §4.2 publication gate expressed as a type rather than
    as a check a producer could forget.
    """

    field_key: str
    value: ScalarValue
    as_of: int
    payload_digest: str
    observation_ref: str

    @model_validator(mode="after")
    def _bindings_concrete_and_governed(self) -> ContextValue:
        """Reject a blank / wildcard key or a blank provenance pointer (fail-closed)."""
        for name in ("field_key", "payload_digest", "observation_ref"):
            token: str = getattr(self, name)
            if not token.strip():
                raise ArtifactIntegrityError(
                    f"ContextValue.{name} must be concrete — a value with no attributed "
                    "provenance is a side channel, not a Critical Input "
                    "(RFC-004 §9:242-244; design #32 §2.3/§4.2)"
                )
        if is_wildcard_field_key(self.field_key):
            raise ArtifactIntegrityError(
                f"ContextValue.field_key={self.field_key!r} must not be a wildcard / 'latest' "
                "form — a wildcard field reference is prohibited on the authoring surface "
                "(RFC-008 §7:239-240; design #32 §2.4)"
            )
        return self


class ContextValueView(FrozenModel):
    """The value set one evaluation may read, bound to its snapshot (design #32 §2.2).

    ``snapshot_id`` / ``snapshot_canonical_digest`` record which Critical Input Snapshot the values
    were resolved from; the ``tos.marketfeed`` resolver publishes a view **only** when those match
    the Capsule's ``SnapshotRef`` exactly, so a more-permissive silent substitution is refused
    (ADR-002-018 §15:386; design #32 §3.3).

    ``values`` is the complete exposed set. A duplicate ``field_key`` is **rejected**, never folded:
    conflicting observations of the same field are not averaged, majority-voted, or arbitrarily
    collapsed (ADR-002-018 §11:311, §14:365; design #32 §6).

    An **explicit-empty** view (``values == ()``) is a defined outcome — "the binding resolved and
    nothing was admissible" — and is materially different from *no view at all* (binding mismatch /
    snapshot missing). Both are restrictive, and ``tos.marketfeed`` records which one occurred
    (design #32 §6 ∅ 양방향).

    ``canonical_digest`` is the digest of the value set; it is appended to the recorded input
    signature by :func:`~tos.dsl.determinism.evaluate_resolved`, so a different value set produces a
    different signature (design #32 §3.2 (3b), MAJOR-2a). ``canonicalization_version`` records which
    scheme produced it — ``ev-l1-provisional-0`` today, explicitly non-production (design #32 §1.1).
    """

    snapshot_id: str
    snapshot_canonical_digest: str
    values: tuple[ContextValue, ...] = ()
    canonical_digest: str
    canonicalization_version: str

    @model_validator(mode="after")
    def _binding_concrete_and_keys_distinct(self) -> ContextValueView:
        """Reject a blank binding/digest or a duplicated ``field_key`` (fail-closed)."""
        for name in (
            "snapshot_id",
            "snapshot_canonical_digest",
            "canonical_digest",
            "canonicalization_version",
        ):
            token: str = getattr(self, name)
            if not token.strip():
                raise ArtifactIntegrityError(
                    f"ContextValueView.{name} must be concrete — an unbound or undigested value "
                    "view cannot evidence which snapshot it came from (ADR-002-018 §15:373-386; "
                    "design #32 §2.2/§3.3)"
                )
        seen: set[str] = set()
        duplicates: list[str] = []
        for value in self.values:
            if value.field_key in seen:
                duplicates.append(value.field_key)
            seen.add(value.field_key)
        if duplicates:
            raise ArtifactIntegrityError(
                f"ContextValueView carries duplicate field_key(s) {sorted(set(duplicates))} — "
                "disagreeing observations of one field are never averaged, majority-voted, or "
                "collapsed onto an arbitrary one (ADR-002-018 §11:311, §14:365; design #32 §6)"
            )
        return self

    def as_environment_mapping(self) -> dict[str, ScalarValue]:
        """Project the view onto the flat ``{field_key: scalar}`` mapping the DSL walks.

        :func:`~tos.dsl.vocabulary.resolve_operand` navigates ``env`` by dict keys only and demands
        a scalar leaf (``vocabulary.py:334, 338``) — it cannot index a list. A flat, field-key-keyed
        mapping of scalars is therefore the only shape a value can reach a policy through, which is
        the mechanical reason ``field_key`` is governed at all (design #32 §3.2 (2)).

        Returns:
            The ``{field_key: value}`` mapping (empty for an explicit-empty view).
        """
        return {value.field_key: value.value for value in self.values}
