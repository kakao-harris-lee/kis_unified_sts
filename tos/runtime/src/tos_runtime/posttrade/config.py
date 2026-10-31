"""SYNTHETIC post-trade finality runtime config loader (TOS Phase 3 Wave 2 Lane C-R; plan §2.2).

Loads ``tos/runtime/config/finality.example.yaml`` (or an operator-approved copy). The four
scope-tuple values are what :class:`~tos.posttrade.records.ObligationLegScope` needs that this
runtime cannot honestly derive from an ``EgressResultPayload`` alone
(``currency``/``value_date``/``source_revision``) plus the approved proof-recipe identity
(``proof_recipe_id``, ADR-002-030 §29 Q3) — every one of them is an OPERATOR-APPROVED STATIC
value, never computed here (mirrors :mod:`tos_runtime.release.config`'s own "null=named-TBD ⇒
refuse to start" discipline). What IS derived from the result at hand — the account, the
instrument, the exact filled quantity — is never duplicated into this config; see
:mod:`tos_runtime.posttrade.finality`.

**``release_proof_wait_ms`` (TOS Phase 5 W2-R; plan §10 row ④).** The obligation-expiry bound
:mod:`tos_runtime.posttrade.release_consumer`'s :class:`~tos_runtime.posttrade.release_consumer
.FinalityReleaseConsumer` uses to record (never act on) a ``RELEASE_PROOF_OVERDUE`` evidence row
once a reservation has sat in ``RELEASE_PENDING_PROOF``/``QUARANTINED_UNKNOWN`` longer than this
many milliseconds — an OPERATOR-APPROVED STATIC value, same discipline as the other four.

**``witness`` (#1011 P2; plan 2026-10-31 §3.2).** The ONE post-trade key that selects which
:class:`~tos_runtime.recon.ports.BrokerWitness` a SYNTHETIC-transport boot reconciles against.
Unlike the five above it is **OPTIONAL and defaults to absent**, which is today's behaviour
(:class:`~tos_runtime.recon.witness_synthetic.SyntheticLedgerWitness`, store-derived,
fail-closed). The one recognized value, ``synthetic_venue_ledger``, selects the venue ledger
(:mod:`tos_runtime.venue_ledger.synthetic`) and its independent witness. An unrecognized value
refuses the boot rather than silently falling back: "the operator typed a witness name" and
"the operator typed nothing" are different facts and must not collapse. The key names the
witness FAMILY only — whether a given boot may use it is decided from the boot's transport kind
(:mod:`tos_runtime.compose._venue_ledger_wiring`), never from a tree name.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from tos_runtime._named_tbd import reject_named_tbd

__all__ = [
    "FinalityConfig",
    "FinalityConfigError",
    "PostTradeWitnessKind",
    "WITNESS_CONFIG_KEY",
    "load_finality_config",
]

#: The optional key's own name — the ONE spelling, shared by this loader and every error
#: message, so a config key and the string an operator reads never drift apart.
WITNESS_CONFIG_KEY = "witness"


class PostTradeWitnessKind(StrEnum):
    """The closed vocabulary ``finality.yaml::witness`` accepts (module docstring).

    Deliberately NOT carrying a member for the store-derived witness: that one is what an
    ABSENT key already means, and a second spelling for the default would let a tree claim a
    witness it already had.
    """

    SYNTHETIC_VENUE_LEDGER = "synthetic_venue_ledger"


class FinalityConfigError(Exception):
    """Raised when the finality config is missing, malformed, or carries an unfilled
    (missing/null) required key — fail-closed at load."""


@dataclass(frozen=True)
class FinalityConfig:
    """Fully-valued SYNTHETIC post-trade finality runtime configuration.

    Attributes:
        currency: The exact settlement currency this SYNTHETIC transport's obligations are
            denominated in (``ObligationLegScope.currency``, ADR §11 line 328).
        value_date: The exact value-date token this transport's obligations bind
            (``ObligationLegScope.value_date`` — an opaque injected token; this package is
            clock-free and reads no time source).
        source_revision: The exact source revision the finality proof is taken against
            (``ObligationLegScope.source_revision`` / :attr:`~tos.posttrade.records
            .PostTradeFinalityProof.source_revision`).
        proof_recipe_id: The Phase-0-approved proof recipe identity (ADR §29 Q3) this SYNTHETIC
            producer issues every proof under.
        release_proof_wait_ms: The obligation-expiry bound (module docstring's "release_proof_
            wait_ms" section) — a positive int, never derived.
        witness: The selected post-trade witness family (module docstring's "witness" section),
            or ``None`` when the key is absent — which is today's behaviour, not a missing
            value. Defaulted so every existing caller and every shipped tree stays valid
            unchanged.
    """

    currency: str
    value_date: str
    source_revision: str
    proof_recipe_id: str
    release_proof_wait_ms: int
    witness: PostTradeWitnessKind | None = None


def _require_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FinalityConfigError(f"finality config file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FinalityConfigError(
            f"finality config file could not be read: {path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise FinalityConfigError(
            f"finality config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise FinalityConfigError(
            f"finality config file must be a top-level mapping: {path} (got {type(raw)!r})"
        )
    return raw


def _require_str(raw: dict[str, Any], key: str) -> str:
    if key not in raw:
        raise FinalityConfigError(f"finality config missing required key: {key!r}")
    value = raw[key]
    if value is None:
        raise FinalityConfigError(
            "finality config has an unfilled (named-TBD) key — fail-closed at startup "
            f"until an operator fills it: {key!r}"
        )
    if not isinstance(value, str) or not value.strip():
        raise FinalityConfigError(
            f"finality config key {key!r} must be a non-blank string (got {value!r})"
        )
    reject_named_tbd(
        value, field=key, context="finality config", error_cls=FinalityConfigError
    )
    return value


def _require_positive_int(raw: dict[str, Any], key: str) -> int:
    if key not in raw:
        raise FinalityConfigError(f"finality config missing required key: {key!r}")
    value = raw[key]
    if value is None:
        raise FinalityConfigError(
            "finality config has an unfilled (named-TBD) key — fail-closed at startup "
            f"until an operator fills it: {key!r}"
        )
    if isinstance(value, bool) or not isinstance(value, int):
        raise FinalityConfigError(
            f"finality config key {key!r} must be an int (got {value!r})"
        )
    if value <= 0:
        raise FinalityConfigError(
            f"finality config key {key!r} must be a positive int (got {value!r}) — a "
            "zero/negative wait bound is not a smaller bound, it is a silently-disabled one"
        )
    return value


def _optional_witness(raw: dict[str, Any]) -> PostTradeWitnessKind | None:
    """``witness``, or ``None`` when the key is absent (module docstring's "witness" section).

    Three outcomes, and the middle one is the point: an ABSENT key is today's behaviour; a
    PRESENT key must name a member of :class:`PostTradeWitnessKind`; anything else — including
    an explicit ``null``, which in this file's own convention means "an operator has not filled
    this in yet" — refuses the load. A silently-ignored misspelling would leave a tree booting
    on the store-derived witness while its config says otherwise.

    Raises:
        FinalityConfigError: The key is present and is not one of the recognized tokens.
    """
    if WITNESS_CONFIG_KEY not in raw:
        return None
    value = raw[WITNESS_CONFIG_KEY]
    try:
        return PostTradeWitnessKind(value)
    except ValueError as exc:
        known = ", ".join(repr(kind.value) for kind in PostTradeWitnessKind)
        raise FinalityConfigError(
            f"finality config key {WITNESS_CONFIG_KEY!r} is {value!r}, which names no known "
            f"witness (known: {known}) — remove the key to keep the default store-derived "
            "witness, never leave it misspelled"
        ) from exc


def load_finality_config(path: Path) -> FinalityConfig:
    """Load + validate the SYNTHETIC finality config file, fail-closed.

    Args:
        path: Path to a YAML file shaped like ``tos/runtime/config/finality.example.yaml``.

    Returns:
        A fully-valued :class:`FinalityConfig`.

    Raises:
        FinalityConfigError: The file is missing/unreadable/not valid YAML/not a mapping, a
            required key is missing, still ``null`` (named-TBD), or the wrong shape, or the
            optional ``witness`` key names no known witness (:func:`_optional_witness`).
    """
    raw = _require_mapping(path)
    return FinalityConfig(
        currency=_require_str(raw, "currency"),
        value_date=_require_str(raw, "value_date"),
        source_revision=_require_str(raw, "source_revision"),
        proof_recipe_id=_require_str(raw, "proof_recipe_id"),
        release_proof_wait_ms=_require_positive_int(raw, "release_proof_wait_ms"),
        witness=_optional_witness(raw),
    )
