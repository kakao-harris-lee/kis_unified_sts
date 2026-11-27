"""The projected-position carrier the DSL reads under ``capsule.position`` (plan P4 §2 D2/D4)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import model_validator

from tos.canonical import CanonicalizationScheme
from tos.dsl._base import ArtifactIntegrityError, FrozenModel
from tos.dsl.context_value import is_wildcard_field_key
from tos.dsl.vocabulary import ScalarValue

__all__ = [
    "ENTRY_PRICE_BASES",
    "POSITION_NAMESPACE",
    "PositionContext",
    "PositionSide",
    "flat_position_context",
    "position_context_digest",
    "project_position_context",
]

POSITION_NAMESPACE = "position"

BASIS_EXECUTION = "EXECUTION"
BASIS_ORDER = "ORDER"
ENTRY_PRICE_BASES: frozenset[str] = frozenset({BASIS_EXECUTION, BASIS_ORDER})

_BP_PER_UNIT = 10_000

_PROVENANCE_FIELDS: tuple[str, ...] = (
    "source_ref",
    "canonical_digest",
    "canonicalization_version",
)
_ENTRY_FIELDS: tuple[str, ...] = (
    "entry_price",
    "entry_price_basis",
    "unrealized",
    "unrealized_bp",
    "bars_held",
)
_INT_FIELDS: tuple[str, ...] = (
    "held_qty",
    "entry_price",
    "unrealized",
    "unrealized_bp",
    "bars_held",
    "as_of",
)


class PositionSide(StrEnum):
    """The proven holding direction a position context may carry (plan P4 §2 D2)."""

    FLAT = "FLAT"
    LONG = "LONG"
    SHORT = "SHORT"


_HELD_SIDES: tuple[PositionSide, ...] = (PositionSide.LONG, PositionSide.SHORT)


class PositionContext(FrozenModel):
    """One bar's proven position as the DSL environment sees it (plan P4 §2 D2)."""

    side: PositionSide
    held_qty: int
    entry_price: int | None = None
    entry_price_basis: str | None = None
    unrealized: int | None = None
    unrealized_bp: int | None = None
    bars_held: int | None = None
    source_ref: str
    as_of: int
    canonical_digest: str
    canonicalization_version: str

    @model_validator(mode="before")
    @classmethod
    def _no_bool_where_an_int_is_expected(cls, data: Any) -> Any:
        """Refuse a bool in an int slot (fail-closed)."""
        if not isinstance(data, dict):
            return data
        for name in _INT_FIELDS:
            # SAFETY: a bool is refused before validation, not after — pydantic coerces True
            # to 1 first, so held_qty=True would read back as a proven one-lot holding.
            if type(data.get(name)) is bool:
                raise ArtifactIntegrityError(
                    f"PositionContext.{name} must be an int, not a bool — a flag read as a "
                    "magnitude is a silently wrong holding (plan P4 §2 D3)"
                )
        return data

    @model_validator(mode="after")
    def _provenance_concrete_and_shape_consistent(self) -> PositionContext:
        """Refuse a blank/wildcard pointer or a side/quantity/entry combination that disagrees."""
        for name in _PROVENANCE_FIELDS:
            token: str = getattr(self, name)
            if not token.strip():
                raise ArtifactIntegrityError(
                    f"PositionContext.{name} must be concrete — a position with no attributed "
                    "evidence is a side channel, not a proven holding (plan P4 §2 D1/D3)"
                )
        if is_wildcard_field_key(self.source_ref):
            raise ArtifactIntegrityError(
                f"PositionContext.source_ref={self.source_ref!r} must not be a wildcard / "
                "'latest' form — a position points at one evidence record (plan P4 §2 D3)"
            )
        if self.side is PositionSide.FLAT:
            return self._flat_shape()
        return self._held_shape()

    def _flat_shape(self) -> PositionContext:
        """FLAT carries no quantity and no entry field at all."""
        if self.held_qty != 0:
            raise ArtifactIntegrityError(
                f"PositionContext side=FLAT requires held_qty=0, got {self.held_qty} — a flat "
                "position with a quantity is two disagreeing claims (plan P4 §2 D3)"
            )
        present = [name for name in _ENTRY_FIELDS if getattr(self, name) is not None]
        if present:
            raise ArtifactIntegrityError(
                f"PositionContext side=FLAT must carry no entry field, got {present} — an "
                "unrealized figure on a flat position would gate a stop-loss rule that has "
                "nothing to close (plan P4 §2 D3)"
            )
        return self

    def _held_shape(self) -> PositionContext:
        """A non-flat side requires a positive quantity and every entry field, sane."""
        if self.held_qty <= 0:
            raise ArtifactIntegrityError(
                f"PositionContext side={self.side.value} requires a positive held_qty, got "
                f"{self.held_qty} — a direction with no proven quantity is not a holding"
            )
        if self.entry_price is None or self.entry_price <= 0:
            raise ArtifactIntegrityError(
                f"PositionContext side={self.side.value} requires a positive entry_price, got "
                f"{self.entry_price!r} — every unrealized figure divides by it"
            )
        if self.entry_price_basis not in ENTRY_PRICE_BASES:
            raise ArtifactIntegrityError(
                f"PositionContext.entry_price_basis={self.entry_price_basis!r} is not one of "
                f"{sorted(ENTRY_PRICE_BASES)} — an unnamed basis cannot be gated on by a tenant"
            )
        if self.unrealized is None or self.unrealized_bp is None:
            raise ArtifactIntegrityError(
                f"PositionContext side={self.side.value} requires both unrealized and "
                "unrealized_bp — a partially filled position context is never published "
                "(plan P4 §2 D3)"
            )
        if self.bars_held is None or self.bars_held < 0:
            raise ArtifactIntegrityError(
                f"PositionContext side={self.side.value} requires a non-negative bars_held, got "
                f"{self.bars_held!r}"
            )
        return self

    def as_environment_mapping(self) -> dict[str, ScalarValue]:
        """Project the DSL-visible fields onto the flat mapping the DSL walks."""
        # SAFETY: the plain ``.value``, never the enum member — eval_compare's EQ/NE demand
        # type(left) is type(right), so a PositionSide member would make every authored
        # ``side EQ FLAT`` comparison false and let an entry rule fire while holding.
        mapping: dict[str, ScalarValue] = {
            "side": self.side.value,
            "held_qty": self.held_qty,
        }
        for name in _ENTRY_FIELDS:
            value: ScalarValue | None = getattr(self, name)
            # SAFETY: an absent field is left out, never defaulted — a 0 here would make
            # ``unrealized_bp LE config.stop_loss_bp`` fire on a position whose entry price
            # was never proven; an absent key stays UNKNOWN and narrows to False instead.
            if value is not None:
                mapping[name] = value
        return mapping


def position_context_digest(
    *,
    side: PositionSide,
    held_qty: int,
    entry_price: int | None,
    entry_price_basis: str | None,
    unrealized: int | None,
    unrealized_bp: int | None,
    bars_held: int | None,
    source_ref: str,
    as_of: int,
    scheme: CanonicalizationScheme,
) -> str:
    """The canonical digest of one projected position's content (plan P4 §2 D5)."""
    return scheme.compute_digest(
        {
            "side": side.value,
            "held_qty": held_qty,
            "entry_price": entry_price,
            "entry_price_basis": entry_price_basis,
            "unrealized": unrealized,
            "unrealized_bp": unrealized_bp,
            "bars_held": bars_held,
            "source_ref": source_ref,
            "as_of": as_of,
        }
    )


def _issue(
    *,
    side: PositionSide,
    held_qty: int,
    entry_price: int | None,
    entry_price_basis: str | None,
    unrealized: int | None,
    unrealized_bp: int | None,
    bars_held: int | None,
    source_ref: str,
    as_of: int,
    scheme: CanonicalizationScheme,
) -> PositionContext:
    """The one construction site — a context is always digest-bound to its own content."""
    return PositionContext(
        side=side,
        held_qty=held_qty,
        entry_price=entry_price,
        entry_price_basis=entry_price_basis,
        unrealized=unrealized,
        unrealized_bp=unrealized_bp,
        bars_held=bars_held,
        source_ref=source_ref,
        as_of=as_of,
        canonical_digest=position_context_digest(
            side=side,
            held_qty=held_qty,
            entry_price=entry_price,
            entry_price_basis=entry_price_basis,
            unrealized=unrealized,
            unrealized_bp=unrealized_bp,
            bars_held=bars_held,
            source_ref=source_ref,
            as_of=as_of,
            scheme=scheme,
        ),
        canonicalization_version=scheme.version,
    )


def flat_position_context(
    *, source_ref: str, as_of: int, scheme: CanonicalizationScheme
) -> PositionContext:
    """The proven-flat context: zero quantity and no entry field (pure; plan P4 §2 D2)."""
    return _issue(
        side=PositionSide.FLAT,
        held_qty=0,
        entry_price=None,
        entry_price_basis=None,
        unrealized=None,
        unrealized_bp=None,
        bars_held=None,
        source_ref=source_ref,
        as_of=as_of,
        scheme=scheme,
    )


def _refuse_non_positive(name: str, magnitude: object) -> None:
    """Refuse anything but a positive int for a projection magnitude (fail-closed)."""
    if type(magnitude) is not int or magnitude <= 0:
        raise ArtifactIntegrityError(
            f"project_position_context {name}={magnitude!r} must be a positive int — a "
            "projection refuses a bad input rather than repairing it (plan P4 §2 D3)"
        )


def project_position_context(
    *,
    side: PositionSide,
    held_qty: int,
    entry_price: int,
    entry_price_basis: str,
    entry_as_of: int,
    price: int,
    as_of: int,
    bar_interval_ms: int,
    source_ref: str,
    scheme: CanonicalizationScheme,
) -> PositionContext:
    """Project a proven holding onto this bar's position context (pure; plan P4 §2 D4)."""
    if side not in _HELD_SIDES:
        raise ArtifactIntegrityError(
            f"project_position_context side={side!r} must be one of "
            f"{[held.value for held in _HELD_SIDES]} — a flat position is "
            "flat_position_context, not a projection with an entry (plan P4 §2 D2)"
        )
    for name, magnitude in (
        ("held_qty", held_qty),
        ("entry_price", entry_price),
        ("price", price),
        ("bar_interval_ms", bar_interval_ms),
    ):
        _refuse_non_positive(name, magnitude)
    for name, instant in (("entry_as_of", entry_as_of), ("as_of", as_of)):
        if type(instant) is not int:
            raise ArtifactIntegrityError(
                f"project_position_context {name}={instant!r} must be an int instant "
                "(plan P4 §2 D3)"
            )
    if as_of < entry_as_of:
        raise ArtifactIntegrityError(
            f"project_position_context as_of={as_of} precedes entry_as_of={entry_as_of} — a "
            "position cannot be held before it was entered (plan P4 §2 D4)"
        )
    if entry_price_basis not in ENTRY_PRICE_BASES:
        raise ArtifactIntegrityError(
            f"project_position_context entry_price_basis={entry_price_basis!r} is not one of "
            f"{sorted(ENTRY_PRICE_BASES)} (plan P4 §2 D2)"
        )
    unrealized = (
        price - entry_price if side == PositionSide.LONG else entry_price - price
    )
    # SAFETY: the bp figure truncates toward zero on both signs — Python's // floors toward
    # -inf, so a direct unrealized * 10_000 // entry_price would overstate every loss by up
    # to one bp and trip a declared stop-loss a bar early.
    magnitude = abs(unrealized) * _BP_PER_UNIT // entry_price
    return _issue(
        side=PositionSide(side),
        held_qty=held_qty,
        entry_price=entry_price,
        entry_price_basis=entry_price_basis,
        unrealized=unrealized,
        unrealized_bp=-magnitude if unrealized < 0 else magnitude,
        bars_held=(as_of - entry_as_of) // bar_interval_ms,
        source_ref=source_ref,
        as_of=as_of,
        scheme=scheme,
    )
