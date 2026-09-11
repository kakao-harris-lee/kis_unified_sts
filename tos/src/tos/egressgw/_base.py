"""egressgw-local base — reused canonical substrate + the two all-false authority blocks.

The digest-binding substrate (``FrozenModel``, ``ArtifactStatus``, ``ArtifactIntegrityError``,
``derive_id``, ``CanonicalizationScheme``, ``get_scheme``, ``CanonicalDecimal``) is reused
verbatim from :mod:`tos.canonical` — the series "재정의 금지" discipline (design #34 §8.1 REUSE).
This module adds only the two egressgw-local authority blocks:

* :class:`AllFalseConstructionCoordinatorAuthority` — carried by every **Order Construction**
  record. RFC-002 §9.1:553 verbatim: "Order Construction Service SHALL NOT approve, mutate
  capacity, classify protection, issue authority, transmit, or arm live scope" (design #34 §3.3).
  Note ``transmits`` is present and false here: construction never transmits.
* :class:`AllFalseGatewayAuthority` — carried by every **Broker Egress Gateway** record. The
  gateway is the *final enforcement point* (RFC-002 §10.8), so it deliberately carries **no**
  ``transmits`` flag — claiming "this record does not transmit" on the boundary that delegates
  step 18 would be a dishonest flag rather than a seal. What it does claim, and what any ``True``
  makes unconstructable, is that a gateway record approves nothing, mutates no capacity, issues
  no authority, classifies no protection, chooses no admissibility, arms no live scope, clears no
  halt, re-arms nothing, and widens no authority (ADR-002-013 §1; RFC-005 §12:352-373).

Both blocks are the ioc ``OrderConstructionAuthorityEffect`` / egress ``AllFalseEgressAuthority``
isomorph, authored locally rather than imported so a sibling's flag-set drift cannot silently
change what this package claims (the series' local-authorship discipline).

This module also holds the two shared verify-item helpers ``gateway.py`` and ``mesh.py`` both
need (kernel round #2 §2 decision 1 — a single definition, never duplicated):

* ``_verdict`` — assembles one :class:`~tos.egressgw.records.VerifyItemVerdict`, deriving its
  design-§4.1 disposition from :data:`~tos.egressgw.vocabulary.REALIZED_ITEMS` /
  :data:`~tos.egressgw.vocabulary.PROVISIONAL_ITEMS` / (else) ``DEFERRED_APPLICABILITY``.
* ``_positive`` — the shared positive-polarity read of an injected stand-in flag (``None`` /
  ``False`` ⇒ not admitted).

``records.py`` imports this module (for the two authority blocks above), so ``_verdict`` cannot
import :class:`~tos.egressgw.records.VerifyItemVerdict` at module scope without recreating that
cycle the other way — the import is deferred into the function body instead (a standard,
call-time-safe break: by the time ``_verdict`` actually runs, ``tos.egressgw.records`` is fully
loaded). ``vocabulary.py`` no longer imports this module (it now takes
``ArtifactIntegrityError`` straight from :mod:`tos.canonical`), so this module importing
``vocabulary`` at module scope for the item-disposition sets is safe.

Firewall (design #1 §3.2 / design #34 §0.3): ``pydantic`` + stdlib + ``tos.*`` only. No
``importlib`` / ``exec`` / ``eval`` / ``compile``, no ``os.environ`` / ``getenv``, no network
stdlib, no ``shared.*``, no ``numpy`` / ``pandas``, no wall clock (``time`` / ``datetime``) and
no ``random`` / ``secrets`` / ``uuid`` — every identity on this path is content-addressed or
injected (design #34 §0.3/§12.1-8).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import model_validator

from tos.canonical import (
    EV_L1_PROVISIONAL_VERSION,
    ArtifactIntegrityError,
    ArtifactStatus,
    CanonicalDecimal,
    CanonicalizationScheme,
    FrozenModel,
    IndependentIdArtifact,
    derive_id,
    get_scheme,
)
from tos.egressgw.vocabulary import (
    PROVISIONAL_ITEMS,
    REALIZED_ITEMS,
    SendVerifyItem,
    VerifyDisposition,
    VerifyOutcome,
)

if TYPE_CHECKING:
    from tos.egressgw.records import VerifyItemVerdict

__all__ = [
    "CONSTRUCTION_SHALL_NOT_FLAGS",
    "EV_L1_PROVISIONAL_VERSION",
    "GATEWAY_SHALL_NOT_FLAGS",
    "AllFalseConstructionCoordinatorAuthority",
    "AllFalseGatewayAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "CanonicalDecimal",
    "CanonicalizationScheme",
    "FrozenModel",
    "IndependentIdArtifact",
    "derive_id",
    "get_scheme",
]


def _verdict(
    item: SendVerifyItem,
    outcome: VerifyOutcome,
    *,
    reason: str | None = None,
    native: object | None = None,
    native_value: str | None = None,
    preserved_worst_credible_capacity: int | None = None,
    preserved_obligation_magnitude_unknown: bool = False,
) -> "VerifyItemVerdict":
    """Assemble one item verdict, deriving its disposition from the design §4.1 partition.

    Shared by ``gateway.py``'s eleven non-deferred item checks and ``mesh.py``'s deferred-item
    judgement (kernel round #2 §2 decision 1) — a single definition, never duplicated.
    """
    from tos.egressgw.records import VerifyItemVerdict  # noqa: PLC0415 - breaks the base<->records cycle

    if item in REALIZED_ITEMS:
        disposition = VerifyDisposition.REALIZED_STRUCTURAL
    elif item in PROVISIONAL_ITEMS:
        disposition = VerifyDisposition.PROVISIONAL_STAND_IN
    else:
        disposition = VerifyDisposition.DEFERRED_APPLICABILITY
    return VerifyItemVerdict(
        item=item,
        disposition=disposition,
        outcome=outcome,
        reason=reason,
        native_verdict_type=None if native is None else type(native).__name__,
        native_verdict_value=native_value,
        preserved_worst_credible_capacity=preserved_worst_credible_capacity,
        preserved_obligation_magnitude_unknown=preserved_obligation_magnitude_unknown,
    )


def _positive(flag: bool | None) -> bool:
    """Positive-polarity read of an injected stand-in flag (``None`` / ``False`` ⇒ not admitted)."""
    return flag is True


#: RFC-002 §9.1:553 verbatim — the six things an Order Construction Service SHALL NOT do.
CONSTRUCTION_SHALL_NOT_FLAGS: tuple[str, ...] = (
    "approves",
    "mutates_capacity",
    "classifies_protection",
    "issues_authority",
    "transmits",
    "arms_live_scope",
)

#: The gateway's SHALL NOT set (ADR-002-013 §1; RFC-005 §12:352-373). ``transmits`` is
#: deliberately **absent**: the gateway is the boundary that delegates step 18, and a false
#: "does not transmit" flag there would be a lie rather than a seal (design #34 §0.4 E5).
GATEWAY_SHALL_NOT_FLAGS: tuple[str, ...] = (
    "approves",
    "mutates_capacity",
    "issues_authority",
    "classifies_protection",
    "chooses_admissibility",
    "arms_live_scope",
    "clears_halt",
    "rearms",
    "widens_authority",
)


class AllFalseConstructionCoordinatorAuthority(FrozenModel):
    """Order Construction authority block — every flag forced ``false`` (design #34 §3.3).

    RFC-002 §9.1:553 verbatim: "Order Construction Service SHALL NOT approve, mutate capacity,
    classify protection, issue authority, transmit, or arm live scope." Approval is step 4's
    (iap), capacity is steps 8-10's (RCL), and transmission is step 18's (the Broker Adapter) —
    construction produces a *candidate*, an envelope, and a proof, and nothing else.

    Any ``True`` value raises :class:`~tos.canonical.ArtifactIntegrityError`, so an
    authority-claiming construction record is unconstructable.
    """

    approves: bool = False
    mutates_capacity: bool = False
    classifies_protection: bool = False
    issues_authority: bool = False
    transmits: bool = False
    arms_live_scope: bool = False

    @model_validator(mode="after")
    def _all_construction_authority_false(
        self,
    ) -> AllFalseConstructionCoordinatorAuthority:
        """Reject construction if any RFC-002 §9.1:553 flag is ``True``."""
        for name in CONSTRUCTION_SHALL_NOT_FLAGS:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false — the Order Construction "
                    "Service approves nothing, mutates no capacity, classifies no protection, "
                    "issues no authority, transmits nothing, and arms no live scope "
                    "(RFC-002 §9.1:553; design #34 §3.3)"
                )
        return self


class AllFalseGatewayAuthority(FrozenModel):
    """Broker Egress Gateway authority block — every flag forced ``false`` (design #34 §4).

    A gateway verdict is *verified data about a send*, never permission: the gateway enforces
    the RFC-002 §10.8:741-759 verify list and refuses, it does not originate, approve, or widen
    anything. Holding a satisfied verification is not authority — the capability, the permit, the
    approval, and the currentness proof are each produced elsewhere and only *consumed* here
    (ADR-002-013 §4.3 isomorph).

    Any ``True`` value raises :class:`~tos.canonical.ArtifactIntegrityError`.
    """

    approves: bool = False
    mutates_capacity: bool = False
    issues_authority: bool = False
    classifies_protection: bool = False
    chooses_admissibility: bool = False
    arms_live_scope: bool = False
    clears_halt: bool = False
    rearms: bool = False
    widens_authority: bool = False

    @model_validator(mode="after")
    def _all_gateway_authority_false(self) -> AllFalseGatewayAuthority:
        """Reject construction if any gateway ``SHALL NOT`` flag is ``True``."""
        for name in GATEWAY_SHALL_NOT_FLAGS:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false — the Broker Egress Gateway "
                    "is a final enforcement point, not an authority: it approves nothing, "
                    "mutates no capacity, issues no authority, and re-arms nothing "
                    "(ADR-002-013 §1; RFC-005 §12:352-373; design #34 §4)"
                )
        return self
