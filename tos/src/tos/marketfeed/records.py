"""The producer-side records D-E2 consumes and the resolution it reports (design #32 §2.3/§6).

Three shapes, each carrying a structural decision:

* :class:`RawPayloadPreimage` — the canonical preimage the attributed observation's
  ``raw.payload_digest`` addresses. This is where the values actually live: ``tos.capsule``'s
  ``Observation`` is a *provenance* record with **no** numeric leaf at all (``observation.py``;
  ADR-002-018 §9:249-261 lists raw event identity, payload digest, and unit/scale/multiplier/sign
  metadata — never the observed magnitude), so a value is exposed by naming the payload behind the
  digest, not by inventing a field on the Capsule (design #32 §2.1/§2.3, capsule 무변경).

* :class:`AdmittedValue` — one producer-supplied *candidate*: "the value under ``field_key`` in the
  payload behind observation ``observation_ref``". Note what it does **not** carry: the value
  itself, the as-of, the payload digest, or a field state. Every one of those is derived — the
  value from the preimage, the as-of and digest from the attributed observation, the state from the
  snapshot's own governance (구조 파생 > 자기신고). A producer therefore cannot declare a value that
  disagrees with its provenance: changing the value changes the preimage, which changes its digest,
  which no longer matches the observation the snapshot covers (design #32 §2.3).

* :class:`ValueResolution` — the terminal report. It carries the published view *or* the named
  reason there is none, plus a per-candidate rejection list. The ∅ distinction (explicit-empty vs
  no view) is a recorded member, not an inference from ``view is None`` (design #32 §6).

⚠ **Preimage form is provisional** (design #32 §2.3, 미결-3). A flat, scalar-keyed preimage is the
EV-L1 shape; the production preimage (whole native event vs extracted fields) is fixed only once the
G2 production canonicalization is approved. What this contract fixes is the **binding property**
(value ⟺ covered digest), not the preimage bytes.

Firewall: ``pydantic`` + stdlib + ``tos.*`` only. No ``tos.engine`` edge — this module is part of
the pure layer (design #32 §3.4).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import field_validator, model_validator

from tos.dsl import ContextValue, ContextValueView, ScalarValue, is_wildcard_field_key
from tos.marketfeed._base import (
    FrozenModel,
    MarketFeedIntegrityError,
    seal_fetch_surface,
)
from tos.marketfeed.vocabulary import (
    ADMITTING_DISPOSITIONS,
    ValueRejectionReason,
    ValueViewDisposition,
)

__all__ = [
    "AdmittedValue",
    "PreimageEntry",
    "RawPayloadPreimage",
    "RejectedValue",
    "ValueResolution",
]


class PreimageEntry(FrozenModel):
    """One key/value entry of a raw payload preimage (design #32 §2.3).

    ``value`` is the payload field **as the digest preimage carries it**. It is typed
    :data:`~tos.dsl.ScalarValue` (``bool | int | float | str``) and a :class:`~decimal.Decimal` is
    **rejected outright** rather than coerced: pydantic's lax union would happily turn a
    ``Decimal("1.5")`` into a float, and that silent Decimal → float coercion is exactly what
    design #32 §2.5 forbids ("Decimal 직접 노출 금지·silent 강제변환 금지"). A producer holding a
    Decimal magnitude must decide explicitly — integer minor units (exposed) or a fractional
    magnitude (fail-closed until the deterministic-float rule is fixed) — and record that decision
    in the observation's ``mapping`` unit/scale/multiplier provenance.
    """

    key: str
    value: ScalarValue

    @field_validator("value", mode="before")
    @classmethod
    def _no_silent_decimal(cls, value: Any) -> Any:
        """Reject a ``Decimal`` before pydantic's union can coerce it to a float (§2.5)."""
        if isinstance(value, Decimal):
            raise MarketFeedIntegrityError(
                "PreimageEntry.value must not be a Decimal — coercing one to a float here would "
                "be the silent conversion design #32 §2.5 prohibits. Expose an exact integer in "
                "minor/tick units, or leave the value unexposed (structurally UNKNOWN) until the "
                "deterministic-float projection rule is fixed"
            )
        return value

    @model_validator(mode="after")
    def _key_concrete(self) -> PreimageEntry:
        """Reject a blank preimage key (a nameless payload field addresses nothing)."""
        if not self.key.strip():
            raise MarketFeedIntegrityError("PreimageEntry.key must be a concrete, non-empty name")
        return self


class RawPayloadPreimage(FrozenModel):
    """The canonical preimage one ``raw.payload_digest`` addresses (design #32 §2.3).

    Entries are carried as a tuple (frozen, order-preserving) and projected to a mapping only when
    the digest is computed; the shipped canonicalizer key-sorts mappings, so entry order does not
    affect the digest (``canonicalization.py`` ``_encode``: mappings are key-sorted).

    A duplicated key is rejected: a preimage with two entries under one name has no single value to
    attribute, and picking one would be an arbitrary fold.
    """

    entries: tuple[PreimageEntry, ...] = ()

    @model_validator(mode="after")
    def _keys_distinct(self) -> RawPayloadPreimage:
        """Reject a preimage with a duplicated key (no arbitrary fold)."""
        seen: set[str] = set()
        for entry in self.entries:
            if entry.key in seen:
                raise MarketFeedIntegrityError(
                    f"RawPayloadPreimage carries duplicate key {entry.key!r} — a payload with two "
                    "values under one name has no attributable value (design #32 §6)"
                )
            seen.add(entry.key)
        return self

    def as_mapping(self) -> dict[str, ScalarValue]:
        """Project the preimage to the mapping the canonicalizer digests.

        Returns:
            The ``{key: value}`` mapping.
        """
        return {entry.key: entry.value for entry in self.entries}

    def lookup(self, key: str) -> ScalarValue | None:
        """Return the value under ``key``, or ``None`` when the payload carries no such field.

        Args:
            key: The payload field name.

        Returns:
            The value, or ``None`` if absent. ``None`` is unambiguous here because
            :class:`PreimageEntry` cannot carry a ``None`` value.
        """
        for entry in self.entries:
            if entry.key == key:
                return entry.value
        return None


class AdmittedValue(FrozenModel):
    """One producer-supplied candidate value + the provenance it claims (design #32 §2.3).

    ``field_key`` is the DSL-visible leaf name; ``observation_ref`` is the attributed observation's
    ``raw.raw_event_id``; ``preimage`` is the payload that observation's ``payload_digest`` claims
    to address. Publication verifies all three against the snapshot before anything is exposed —
    this record is a *claim*, never an admission (the name refers to the admitted **observation**
    the value is attributed to, which the gate then confirms).
    """

    field_key: str
    observation_ref: str
    preimage: RawPayloadPreimage = RawPayloadPreimage()

    @model_validator(mode="after")
    def _claim_is_well_formed(self) -> AdmittedValue:
        """Reject a blank/wildcard key or a blank observation reference (fail-closed)."""
        seal_fetch_surface(type(self).__name__, type(self).model_fields)
        for name in ("field_key", "observation_ref"):
            token: str = getattr(self, name)
            if not token.strip():
                raise MarketFeedIntegrityError(
                    f"AdmittedValue.{name} must be concrete — an unattributed value is a side "
                    "channel (RFC-004 §9:242-244; design #32 §2.3)"
                )
        if is_wildcard_field_key(self.field_key):
            raise MarketFeedIntegrityError(
                f"AdmittedValue.field_key={self.field_key!r} must not be a wildcard / 'latest' "
                "form (RFC-008 §7:239-240; design #32 §2.4)"
            )
        return self


class RejectedValue(FrozenModel):
    """One candidate that did not reach the environment, with its named cause (design #32 §6)."""

    field_key: str
    observation_ref: str
    reason: ValueRejectionReason
    detail: str | None = None


class ValueResolution(FrozenModel):
    """The terminal report of one value-view resolution (design #32 §3.3/§6).

    ``disposition`` is the authority on what happened; ``view`` is present **iff** the disposition
    is an admitting one. The two are cross-checked at construction so a caller can never observe a
    view under ``BINDING_MISMATCH``, nor a missing view under ``RESOLVED`` — the ∅ distinction stays
    a recorded fact rather than something inferred from a nullable field.

    ``rejected`` lists every candidate that was refused and why, so a decision that starved of
    values can say which ones and for what reason (design #32 §6).
    """

    disposition: ValueViewDisposition
    view: ContextValueView | None = None
    rejected: tuple[RejectedValue, ...] = ()
    detail: str | None = None

    @model_validator(mode="after")
    def _view_matches_disposition(self) -> ValueResolution:
        """Reject a report whose view presence contradicts its disposition (fail-closed)."""
        admitting = self.disposition in ADMITTING_DISPOSITIONS
        if admitting and self.view is None:
            raise MarketFeedIntegrityError(
                f"ValueResolution disposition={self.disposition} requires a published view — an "
                "admitting disposition with no view would make the ∅ distinction unreadable "
                "(design #32 §6)"
            )
        if not admitting and self.view is not None:
            raise MarketFeedIntegrityError(
                f"ValueResolution disposition={self.disposition} must carry no view — a refused "
                "binding never yields consumable values (ADR-002-018 §15:386; design #32 §3.3)"
            )
        if self.disposition is ValueViewDisposition.RESOLVED and self.view is not None:
            if not self.view.values:
                raise MarketFeedIntegrityError(
                    "ValueResolution disposition=RESOLVED with an empty value set must be recorded "
                    "as EXPLICIT_EMPTY — a defined no-value context is materially different from a "
                    "resolved one (design #32 §6 ∅ 양방향)"
                )
        if self.disposition is ValueViewDisposition.EXPLICIT_EMPTY and self.view is not None:
            if self.view.values:
                raise MarketFeedIntegrityError(
                    "ValueResolution disposition=EXPLICIT_EMPTY must carry a value-free view "
                    "(design #32 §6 ∅ 양방향)"
                )
        return self

    @property
    def values(self) -> tuple[ContextValue, ...]:
        """The admitted values, or an empty tuple when no view was published."""
        return () if self.view is None else self.view.values
