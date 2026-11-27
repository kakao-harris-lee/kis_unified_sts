"""The projected-position carrier the DSL reads under ``capsule.position`` (plan P4 §2 D2/D4)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import model_validator

from tos.canonical import CanonicalizationScheme, get_scheme
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
_STR_FIELDS: tuple[str, ...] = (
    "side",
    "entry_price_basis",
    "source_ref",
    "canonical_digest",
    "canonicalization_version",
)
_OPTIONAL_FIELDS: frozenset[str] = frozenset(_ENTRY_FIELDS)

_ABSENT = object()


def _slot_is_concrete(name: str, value: Any) -> bool:
    """Whether a slot carries a value the declared-type check applies to."""
    if value is _ABSENT:
        return False
    return not (value is None and name in _OPTIONAL_FIELDS)


def _coerced_slot_error(name: str, value: Any, declared: str) -> ArtifactIntegrityError:
    """The refusal of a value pydantic would coerce into ``name``."""
    return ArtifactIntegrityError(
        f"PositionContext.{name} must already be of type {declared}, not a "
        f"{type(value).__name__} ({value!r}) — a coerced near-miss is a holding whose "
        "digest was taken over different content (plan P4 §2 D3)"
    )


def _unrealized_bp(unrealized: int, entry_price: int) -> int:
    """The bp figure of one unrealized move over its entry price (plan P4 §2 D4)."""
    # SAFETY: the bp figure truncates toward zero on both signs — Python's // floors toward
    # -inf, so a direct unrealized * 10_000 // entry_price would overstate every loss by up
    # to one bp and trip a declared stop-loss a bar early.
    magnitude = abs(unrealized) * _BP_PER_UNIT // entry_price
    return -magnitude if unrealized < 0 else magnitude


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
    def _every_slot_already_holds_its_declared_type(cls, data: Any) -> Any:
        """Refuse a value pydantic would coerce into an int or str slot (fail-closed)."""
        if not isinstance(data, dict):
            return data
        for name in _INT_FIELDS:
            value = data.get(name, _ABSENT)
            # SAFETY: an int slot is checked before validation, not after — pydantic coerces
            # True to 1 and "30000" to 30000, so held_qty=True or an inbox row's quoted
            # entry_price would read back as a proven magnitude nobody projected.
            if _slot_is_concrete(name, value) and type(value) is not int:
                raise _coerced_slot_error(name, value, "int")
        for name in _STR_FIELDS:
            value = data.get(name, _ABSENT)
            # SAFETY: a str slot too — pydantic decodes b"ORDER" to "ORDER", so an entry
            # basis a tenant gates on could arrive as bytes and pass as a named basis.
            if _slot_is_concrete(name, value) and not isinstance(value, str):
                raise _coerced_slot_error(name, value, "str")
        return data

    @model_validator(mode="after")
    def _provenance_concrete_and_shape_consistent(self) -> PositionContext:
        """Refuse a blank/wildcard pointer, a disagreeing shape, or an unbound digest."""
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
        held = self.side is not PositionSide.FLAT
        if held:
            self._held_shape()
        else:
            self._flat_shape()
        self._digest_binds_its_own_content()
        if held:
            self._bp_agrees_with_its_own_unrealized()
        return self

    def _flat_shape(self) -> None:
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

    def _held_shape(self) -> None:
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

    def _digest_binds_its_own_content(self) -> None:
        """Refuse a digest that is not the digest of this record's own covered content."""
        # SAFETY: the record recomputes its own digest instead of trusting the stored field —
        # the next stage rebuilds this record from an inbox row, where an unverified digest
        # would let a tampered holding gate a real exit as if the kernel had projected it.
        expected = position_context_digest(
            side=self.side,
            held_qty=self.held_qty,
            entry_price=self.entry_price,
            entry_price_basis=self.entry_price_basis,
            unrealized=self.unrealized,
            unrealized_bp=self.unrealized_bp,
            bars_held=self.bars_held,
            source_ref=self.source_ref,
            as_of=self.as_of,
            scheme=get_scheme(self.canonicalization_version),
        )
        if self.canonical_digest != expected:
            raise ArtifactIntegrityError(
                f"PositionContext.canonical_digest={self.canonical_digest!r} is not the "
                f"digest of its own content (expected {expected!r}) — a position not bound "
                "to what it claims is not evidence (plan P4 §2 D5)"
            )

    def _bp_agrees_with_its_own_unrealized(self) -> None:
        """Refuse a bp figure this record's own unrealized and entry price do not yield."""
        entry_price, unrealized = self.entry_price, self.unrealized
        if entry_price is None or unrealized is None:
            return
        # SAFETY: the bp figure is recomputed, not trusted — it is the one field a declared
        # stop-loss compares against, so an inbox row claiming -5 bp on a -50 bp move would
        # hold a losing position through its own bound.
        expected = _unrealized_bp(unrealized, entry_price)
        if self.unrealized_bp != expected:
            raise ArtifactIntegrityError(
                f"PositionContext.unrealized_bp={self.unrealized_bp!r} disagrees with "
                f"unrealized={unrealized} over entry_price={entry_price} (expected "
                f"{expected}) — the figure a declared bound is compared against must be the "
                "one this record's own entry price yields (plan P4 §2 D3)"
            )

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


def _refuse_non_int_instant(name: str, instant: object) -> None:
    """Refuse anything but an int for a position context's instant (fail-closed)."""
    if type(instant) is not int:
        raise ArtifactIntegrityError(
            f"position context {name}={instant!r} must be an int instant — the digest is "
            "taken over the value as given, so a coerced instant would bind the record to "
            "content it does not carry (plan P4 §2 D3)"
        )


def flat_position_context(
    *, source_ref: str, as_of: int, scheme: CanonicalizationScheme
) -> PositionContext:
    """The proven-flat context: zero quantity and no entry field (pure; plan P4 §2 D2)."""
    _refuse_non_int_instant("as_of", as_of)
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
        _refuse_non_int_instant(name, instant)
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
    return _issue(
        side=PositionSide(side),
        held_qty=held_qty,
        entry_price=entry_price,
        entry_price_basis=entry_price_basis,
        unrealized=unrealized,
        unrealized_bp=_unrealized_bp(unrealized, entry_price),
        bars_held=(as_of - entry_as_of) // bar_interval_ms,
        source_ref=source_ref,
        as_of=as_of,
        scheme=scheme,
    )
