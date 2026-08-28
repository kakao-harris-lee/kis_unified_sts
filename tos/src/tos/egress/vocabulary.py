"""Egress-boundary vocabulary — the EGRESS-axis StrEnums (design #22 §2.2).

Spec terms = code terms (design #22 §2; boundary design #1 §2.4). The enums are authored
**verbatim** from ADR-002-013 (§1/§11.2 final admission verdict, §11.2 commit-proof validity,
§13/§11.2 step 14 restrictive latch, §11.1 quorum signer role).

**Truthy-sentinel structural seal (design #22 §2.2/§4.7 — #13/#14 M1 adopted from the start).**
``EgressAdmission`` (ADMIT / DENY), ``CommitProofValidity`` (VALID / INVALID / UNKNOWN), and
``RestrictiveLatchState`` (CLEAR / DENY_LATCHED) are non-empty ``StrEnum`` strings, so
``if admission:`` / ``bool(validity)`` / ``if state:`` would read a **denial** member (``DENY`` /
``INVALID`` / ``UNKNOWN`` / ``DENY_LATCHED``) as **truthy** — a catastrophic silent fail-open that
reads a *rejection* as an *admission* (ADR §6 EGRESS-INV-011 line 183 "Unknown ... is denial";
§11.2 line 351 "insufficient" ⇒ deny). Each subclasses :class:`_NonTruthyStrEnum`, whose
:meth:`~_NonTruthyStrEnum.__bool__` **raises** ``TypeError``, making them *truthy-untestable*: the
misuse surfaces as an immediate runtime error, never a silent pass. The mandated consume gates are
the explicit positive-identity comparison (``admission is EgressAdmission.ADMIT`` /
``validity is CommitProofValidity.VALID`` / ``state is RestrictiveLatchState.CLEAR``) — everything
else is denial. Isomorphic to the iap ``_NonTruthyStrEnum`` seal (``iap/vocabulary.py:50``) and the
ioc ``ConformanceResult`` seal (``ioc/vocabulary.py:63``); authored locally-fresh here (sibling
edge 0 — no iap / ioc import).

``SignerRole`` is a **plain, closed** ``StrEnum`` (ADR §11.1 quorum signer identity taxonomy): it
is an input taxonomy token consumed by identity / count membership
(:func:`~tos.egress.predicates.quorum_threshold_structurally_met`), never a gate result read with
``if role:``, so it does not need the truthy seal. §11.2 line 351 "One leader signature ... is
insufficient" fixes the leader-vs-quorum axis — a quorum SHALL NOT reduce to one ``LEADER``.

This module names **no** concrete broker (broker-agnostic — project memory
``tos-spec-broker-agnostic``; design #22 §0.2/§18) and hardcodes **no** numeric quorum / age /
latency bound (ADR §4 non-scope / §8): every bound is an injected policy-content value (design #22
§8). An enum member is a structural label, never a limit or a permission.

Pure module: stdlib only; no ``shared.*``, no sibling ``tos.*`` (design #22 §0.3).
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "EgressAdmission",
    "CommitProofValidity",
    "RestrictiveLatchState",
    "SignerRole",
]


class _NonTruthyStrEnum(StrEnum):
    """A ``StrEnum`` that is deliberately **not truthy-testable** (design #22 §2.2/§4.7/M1).

    Every member is a non-empty string, so a bare ``if admission:`` / ``bool(validity)`` /
    ``if state:`` would read a denial member (``DENY`` / ``INVALID`` / ``UNKNOWN`` /
    ``DENY_LATCHED``) as truthy — a catastrophic silent fail-open that reads a rejection as an
    admission. :meth:`__bool__` therefore raises ``TypeError`` on every member, so the misuse
    surfaces as a loud runtime error rather than a silent pass. Consumers MUST use the explicit
    positive-identity gate (``x is ENUM.SAFE_VALUE``). Isomorphic to the iap ``_NonTruthyStrEnum``
    seal (``iap/vocabulary.py:50``) and the ioc ``ConformanceResult`` seal (``ioc/vocabulary.py:63``);
    authored locally-fresh here (sibling edge 0, no iap / ioc import — design #22 §0.4). ``is``
    identity, ``.value``, hashing, set membership, and ``model_dump`` are all unaffected (none
    calls ``__bool__``).
    """

    def __bool__(self) -> bool:
        """Reject truthiness testing outright (truthy-sentinel seal, design #22 §2.2/§4.7/M1).

        Raises:
            TypeError: always — the enum is not truthy-testable. Use the explicit positive
                identity gate (e.g. ``admission is EgressAdmission.ADMIT``;
                ``validity is CommitProofValidity.VALID``; ``state is RestrictiveLatchState.CLEAR``);
                a bare ``if admission:`` / ``bool(admission)`` would fail open on the truthy denial
                strings.
        """
        raise TypeError(
            f"{type(self).__name__} is not truthy-testable — use an explicit positive "
            "identity gate (e.g. `admission is EgressAdmission.ADMIT`; "
            "`validity is CommitProofValidity.VALID`; `state is RestrictiveLatchState.CLEAR`) "
            "per the truthy-sentinel seal (design #22 §2.2/§4.7/M1). The denial members are "
            "non-empty strings and a bare `if admission:` would fail open — reading DENY / "
            "INVALID / UNKNOWN / DENY_LATCHED as an admission."
        )


class EgressAdmission(_NonTruthyStrEnum):
    """The final egress admission verdict (ADR-002-013 §1/§11.2, non-truthy — critical seal).

    §11.2 resolves to admit or deny a broker-order transmission at the final egress boundary.
    **Truthy-untestable** (``__bool__`` raises): ``DENY`` is a non-empty string, so ``if admission:``
    would read a *denial* as an *admission* — the catastrophic fail-open this seal blocks (ADR §6
    EGRESS-INV-011 line 183 "Unknown proof, credential, route, send, session, broker acceptance, or
    old-principal state ... is denial"; §11.2 line 351 "insufficient"). Egress is fundamentally
    DENY-biased: the mandated consume gate is ``admission is EgressAdmission.ADMIT`` — every other
    value is denial. The final admission is a runtime aggregation of the §5 structural / coordinate
    predicates plus the +Security quorum-consensus / cryptographic / bypass-resistance checks
    (design #22 §1/§9.3); this L1 model owns the **vocabulary** of that verdict, not its runtime
    production.
    """

    ADMIT = "ADMIT"
    DENY = "DENY"


class CommitProofValidity(_NonTruthyStrEnum):
    """The Quorum Commit Certificate validity verdict (ADR-002-013 §11.2, non-truthy).

    §11.2 step 2 line 332 "reject unknown security-relevant fields or ambiguous encodings" — a
    ``UNKNOWN`` validity is denial (ADR §6 EGRESS-INV-011). Isomorphic to the ioc
    ``ConformanceResult`` (``ioc/vocabulary.py:40-72``, VALID / INVALID / **UNKNOWN read as truthy
    is a catastrophic fail-open**). **Truthy-untestable** (``__bool__`` raises). The mandated
    consume gate is ``validity is CommitProofValidity.VALID`` — ``INVALID`` and ``UNKNOWN`` are both
    denial. This L1 model owns the **vocabulary** of the verdict; the actual quorum-consensus /
    cryptographic-signature validity is +Security (design #22 §5.3 over-realization boundary).
    """

    VALID = "VALID"
    INVALID = "INVALID"
    UNKNOWN = "UNKNOWN"


class RestrictiveLatchState(_NonTruthyStrEnum):
    """The local restrictive deny-latch state (ADR-002-013 §13/§11.2 step 14, non-truthy).

    §11.2 step 14 line 344 verbatim: "the local restrictive latch is **positively established as
    ``CLEAR``**" — so ``CLEAR`` must be a *positive* proof, never a default. §13 line 393 verbatim:
    "The deny state is monotonic ... Cache recovery, reconnect, secret refresh, route restoration,
    deployment success, or deletion of an alert cannot clear it." The state-machine arrow is judged
    by :func:`~tos.egress.predicates.monotonic_denial_no_revival` (the record does not
    self-transition). **Truthy-untestable** (``__bool__`` raises): ``DENY_LATCHED`` is a non-empty
    string, so ``if state:`` would read a latched denial as clear — a fail-open. The mandated gate
    is ``state is RestrictiveLatchState.CLEAR`` (a ``None`` / ``DENY_LATCHED`` is deny).
    """

    CLEAR = "CLEAR"
    DENY_LATCHED = "DENY_LATCHED"


class SignerRole(StrEnum):
    """The quorum signer role taxonomy (ADR-002-013 §11.1, closed — leader-vs-quorum axis).

    §11.1 line 325 quorum signer identities: a signer is a ``QUORUM_MEMBER`` or the ``LEADER``. A
    **plain, closed** ``StrEnum`` input token compared by identity / count membership
    (:func:`~tos.egress.predicates.quorum_threshold_structurally_met`), never a gate result read
    with ``if role:``. §11.2 line 351 "One leader signature ... is insufficient" — a quorum SHALL
    NOT reduce to one ``LEADER`` (§21.4 fixes leader belief vs quorum commitment); the count
    predicate rejects a lone ``LEADER``.
    """

    QUORUM_MEMBER = "QUORUM_MEMBER"
    LEADER = "LEADER"
