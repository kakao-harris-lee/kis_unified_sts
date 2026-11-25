"""The producer-side records D-E2 consumes and the resolution it reports (design #32 §2.3/§6)."""

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
    """One key/value entry of a raw payload preimage (design #32 §2.3)."""

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
            raise MarketFeedIntegrityError(
                "PreimageEntry.key must be a concrete, non-empty name"
            )
        return self


class RawPayloadPreimage(FrozenModel):
    """The canonical preimage one ``raw.payload_digest`` addresses (design #32 §2.3)."""

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
        """Project the preimage to the mapping the canonicalizer digests."""
        return {entry.key: entry.value for entry in self.entries}

    def lookup(self, key: str) -> ScalarValue | None:
        """Return the value under ``key``, or ``None`` when the payload carries no such field."""
        for entry in self.entries:
            if entry.key == key:
                return entry.value
        return None


class AdmittedValue(FrozenModel):
    """One producer-supplied candidate value + the provenance it claims (design #32 §2.3)."""

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
    """The terminal report of one value-view resolution (design #32 §3.3/§6)."""

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
        if (
            self.disposition is ValueViewDisposition.EXPLICIT_EMPTY
            and self.view is not None
        ):
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
