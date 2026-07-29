"""Engine-local base — reused canonical substrate + the Coordinator all-false authority block.

The digest-binding substrate (``FrozenModel``, ``ArtifactStatus``, ``ArtifactIntegrityError``,
``derive_id``, ``CanonicalizationScheme``, ``get_scheme``, ``CanonicalDecimal``) is reused verbatim
from :mod:`tos.canonical` — the series "재정의 금지" discipline (design #31 §5.1 REUSE). This module
adds only the engine-local piece the Execution Coordinator needs:

* :class:`AllFalseCoordinatorAuthority` — the authority block every engine-emitted record carries.
  Its eleven flags are the RFC-005 §12 ``SHALL NOT`` list the design mirrors verbatim (design #31
  §4.3 — RFC-005 §12:346-377 items at lines 352 / 354 / 356 / 358 / 360 / 362 / 364 / 366 / 368 /
  371 / 373), plus RFC-002 §9.1:557 ("Execution Coordinator SHALL NOT mutate capacity") and
  §10.7:722/:724. Any ``True`` flag makes the record **unconstructable**: the Coordinator is a pure
  requester/sequencer and holds no authority at all (design #31 §4.3; RFC-002 §9.1:551 records
  ``None`` state authority for the proposing side).

The absence of an ``AUTHORITATIVE`` stage class, of any capacity-mutation method, and of any
capability-issuing method is itself part of this package's identity (design #31 §4.3/§11
"provisional over-realization" seal).

Firewall (design #1 §3.2 / design #31 §0.3): ``pydantic`` + stdlib + ``tos.*`` only. No
``importlib`` / ``exec`` / ``eval`` / ``compile``, no ``os.environ`` / ``getenv``, no network
stdlib, no ``shared.*`` operational package, no ``numpy`` / ``pandas``, and — the engine-specific
addition — no wall clock (``time`` / ``datetime``) and no ``random`` / ``secrets`` / ``uuid``
(design #31 §2.3/§7.1).
"""

from __future__ import annotations

from pydantic import model_validator

from tos.canonical import (
    ArtifactIntegrityError,
    ArtifactStatus,
    CanonicalDecimal,
    CanonicalizationScheme,
    FrozenModel,
    derive_id,
    get_scheme,
)

__all__ = [
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "CanonicalDecimal",
    "CanonicalizationScheme",
    "COORDINATOR_SHALL_NOT_FLAGS",
    "AllFalseCoordinatorAuthority",
    "FrozenModel",
    "derive_id",
    "get_scheme",
]


#: The eleven RFC-005 §12:346-377 ``SHALL NOT`` obligations the Execution Coordinator mirrors
#: (design #31 §4.3). Named as a module constant so the model validator and the §7.2-6
#: "Coordinator holds no authority" canary consume **one** set and cannot drift apart.
COORDINATOR_SHALL_NOT_FLAGS: tuple[str, ...] = (
    "originates_approves_or_widens_authority",  # RFC-005 §12:352
    "mutates_risk_capacity_ledger",  # RFC-005 §12:354; RFC-002 §9.1:557
    "constructs_broker_command",  # RFC-005 §12:356; RFC-002 §10.7:724
    "issues_or_reuses_transmission_capability",  # RFC-005 §12:358
    "bypasses_currentness",  # RFC-005 §12:360
    "treats_timeout_as_rejection",  # RFC-005 §12:362; RFC-002 §10.7:722
    "creates_aggregate_exposure_via_retry",  # RFC-005 §12:364
    "exceeds_action_flow_budget",  # RFC-005 §12:366
    "asserts_venue_or_session_state",  # RFC-005 §12:368
    "self_classifies_protective",  # RFC-005 §12:371
    "treats_tca_as_authority",  # RFC-005 §12:373
)


class AllFalseCoordinatorAuthority(FrozenModel):
    """Coordinator authority block — every flag forced ``false`` (design #31 §4.3).

    The Execution Coordinator is a **pure requester and sequencer**: it originates, approves, or
    widens no authority; it mutates no capacity (the Risk Capacity Ledger is the sole
    serialization and mutation authority, RFC-002 §9.1:557); it constructs no broker command
    (ADR-002-020 owns construction, RFC-002 §10.7:724); it issues and reuses no Transmission
    Capability; it bypasses no currentness check; it never reads a missing acknowledgement as a
    rejection (RFC-002 §10.7:722); it creates no aggregate exposure through retry; it exceeds no
    Action Flow budget; it asserts no venue/session state; it self-classifies nothing as
    protective; and it treats no transaction-cost analysis as authority.

    Any ``True`` value raises :class:`~tos.canonical.ArtifactIntegrityError`, so an
    authority-claiming engine record is unconstructable.
    """

    originates_approves_or_widens_authority: bool = False
    mutates_risk_capacity_ledger: bool = False
    constructs_broker_command: bool = False
    issues_or_reuses_transmission_capability: bool = False
    bypasses_currentness: bool = False
    treats_timeout_as_rejection: bool = False
    creates_aggregate_exposure_via_retry: bool = False
    exceeds_action_flow_budget: bool = False
    asserts_venue_or_session_state: bool = False
    self_classifies_protective: bool = False
    treats_tca_as_authority: bool = False

    @model_validator(mode="after")
    def _all_coordinator_authority_false(self) -> AllFalseCoordinatorAuthority:
        """Reject construction if any ``SHALL NOT`` flag is ``True`` (design #31 §4.3)."""
        for name in COORDINATOR_SHALL_NOT_FLAGS:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false — the Execution Coordinator is "
                    "a pure requester/sequencer and holds no authority (RFC-002 §9.1:557, "
                    "§10.7:722/:724; RFC-005 §12:346-377)"
                )
        return self
