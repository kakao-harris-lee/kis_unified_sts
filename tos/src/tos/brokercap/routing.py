"""Broker environment/operation capability axes + closed routing whitelist (plan §5).

Realizes the upstream completion plan's §5 "Broker 환경·작업 capability 모델"
(``docs/plans/2026-08-11-tos-completion-development-plan.md`` §5.1-§5.3) per the ratified
Phase 4 slice #1 plan
(``docs/plans/2026-09-07-tos-phase4-capability-axes-slice-plan.md`` §3, whose decisions are
authoritative and are not re-litigated here):

* **§5.1 — the 5 required axes.** Not ``is_mock: bool``, but 5 independent StrEnums
  (:class:`BrokerEnvironment`, :class:`OperationClass`, :class:`EconomicEffect`,
  :class:`AssetScope`, :class:`AuthorizationClass`) composed into one
  :class:`CapabilityTuple`. ``BrokerEnvironment`` is named **broker-agnostically**
  (``SYNTHETIC`` / ``BROKER_SIMULATION`` / ``BROKER_PRODUCTION``) rather than the upstream
  plan's illustrative concrete-broker mock/real example tokens — no concrete broker is named
  in ``tos/``
  (project memory ``tos-spec-broker-agnostic``); a concrete broker identity is
  :class:`~tos.brokercap.records.ProfileKey`'s ``broker_id`` coordinate (ADR-002-004 §21
  instance concern), consumed here only through the injected ``environment_binding`` /
  ``asset_binding`` maps of :func:`endpoint_binding_from_profile_ok` — never a kernel
  constant.
* **§5.2 — the allowed matrix is a closed whitelist.** :func:`routing_admissibility` maps a
  :class:`CapabilityTuple` to the reused 3-token
  :class:`~tos.brokercap.vocabulary.Admissibility` (no new vocabulary — slice plan §3
  decision 4): a tuple is ``ADMISSIBLE``/``REDUCED`` only when it is one of the finitely many
  sanctioned rows derived from the upstream plan's §5.2 table; **everything else is
  ``PROHIBITED``** (denylist is forbidden — playbook §3.1/§2.E). The "선물 REAL 주문" row is
  not merely absent from the whitelist: :class:`CapabilityTuple` makes the
  ``BROKER_PRODUCTION`` x ``ORDER_SEND``/``CANCEL_REPLACE`` x ``FUTURES`` combination
  *unconstructable* — the root ``CLAUDE.md`` non-negotiable "real futures account is never
  funded with margin" / "real-money futures order paths are permanently blocked by policy"
  is therefore a **type-level seal**, not a predicate a caller could route around. The
  "선물 실체결 필요 bound" row has **no** whitelist tuple at all (§5.2: "없음" endpoint, "실체결
  하지 않고 mock-derived bound 사용") — it is a compute-time policy outside the routing axes,
  not a routing case.
* **§5.3 — kernel-representable routing invariants only.** This slice realizes exactly the
  three invariants the kernel can express without Phase-2 runtime actors (slice plan §3
  decision 5): (i) :func:`endpoint_binding_from_profile_ok` — exact-string environment/asset
  binding against an injected :class:`~tos.brokercap.records.ProfileKey`; (ii)
  :func:`credential_principal_separation_ok` — read/order principal separation; (iii) the
  "MOCK 미지원은 REAL로 재작성되지 않는다" invariant is represented by **absence**: this module
  authors no function that takes a :class:`CapabilityTuple` and returns a (possibly
  different-environment) one — the absence itself is the seal, locked by a negative-grep
  regression test (``tests/brokercap/test_brokercap_routing.py``), not a runtime check.
  :class:`ProbeManifest` is **record shape only** (§5.3 item 5 / decision 5.iv) — provenance
  data-filling is a later Phase-4 task (P0-2 probe gate), out of this slice's scope.

**What this slice explicitly does NOT do** (slice plan §1 exclusions): fill
:class:`ProbeManifest` provenance from a real P0-2 probe run, consume the injected
``profile_evidence_ok`` from a real evidence pipeline, wire a pre-SEND_STARTED sealed-tuple
consumer into ``egressgw``, or bind one outbound call to one adapter result. Those are
separate, later Phase-4 work items with their own gates. This module opens **no** routing
path by itself — it is a closed, non-transmitting representation (design #10 §4.5, inherited
brokercap-wide discipline).

Pure module: ``pydantic`` + stdlib + ``tos.brokercap`` (self) only — no ``shared.*``, no
``numpy``/``pandas``/``yaml``, and the same sibling-edge-0 discipline as the rest of
``tos.brokercap`` (design #10 §0.3/§3.4; verified by the extended
``tests/brokercap/test_brokercap_import_closure.py``).
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Literal

from pydantic import model_validator

from tos.brokercap._base import ArtifactIntegrityError, FrozenModel
from tos.brokercap.records import BrokerEvidenceRef, ProfileKey
from tos.brokercap.vocabulary import Admissibility

__all__ = [
    "AssetScope",
    "AuthorizationClass",
    "BrokerEnvironment",
    "CapabilityProvenance",
    "CapabilityTuple",
    "ClaimKind",
    "EconomicEffect",
    "OperationClass",
    "ProbeManifest",
    "ProvenanceClass",
    "credential_principal_separation_ok",
    "endpoint_binding_from_profile_ok",
    "provenance_admits_claim",
    "routing_admissibility",
]


# ===========================================================================
# §5.1 — the 5 required capability axes (plan §5.1; slice plan §3 decision 2)
# ===========================================================================


class BrokerEnvironment(StrEnum):
    """The broker-environment axis (plan §5.1; broker-agnostic — slice plan §3 decision 2).

    ``SYNTHETIC`` (non-authoritative simulated/backtest data or fills — no broker involved
    at all), ``BROKER_SIMULATION`` (a broker's own mock/paper endpoint), ``BROKER_PRODUCTION``
    (a broker's real endpoint — reachable for reads; permanently unreachable for a
    FUTURES order-mutating operation, see :class:`CapabilityTuple`). Naming deliberately
    avoids any concrete broker token (project memory ``tos-spec-broker-agnostic``); a
    concrete broker's endpoint identity is carried by
    :class:`~tos.brokercap.records.ProfileKey.broker_id` / ``.environment``, consumed only
    through the injected bindings of :func:`endpoint_binding_from_profile_ok`.
    """

    SYNTHETIC = "SYNTHETIC"
    BROKER_SIMULATION = "BROKER_SIMULATION"
    BROKER_PRODUCTION = "BROKER_PRODUCTION"


class OperationClass(StrEnum):
    """The broker-operation-class axis (plan §5.1 verbatim)."""

    MARKET_DATA_READ = "MARKET_DATA_READ"
    ACCOUNT_READ = "ACCOUNT_READ"
    CAPABILITY_PROBE = "CAPABILITY_PROBE"
    ORDER_SEND = "ORDER_SEND"
    CANCEL_REPLACE = "CANCEL_REPLACE"


class EconomicEffect(StrEnum):
    """The economic-effect axis (plan §5.1 verbatim)."""

    NONE = "NONE"
    BROKER_RESOURCE_ONLY = "BROKER_RESOURCE_ONLY"
    POSITION_OR_CASH = "POSITION_OR_CASH"


class AssetScope(StrEnum):
    """The asset-scope axis (plan §5.1 verbatim)."""

    STOCK = "STOCK"
    FUTURES = "FUTURES"


class AuthorizationClass(StrEnum):
    """The authorization-class axis (plan §5.1's 3 members + the v1.1 correction's 4th).

    **v1.1 정정 (2026-09-07):** ``SYNTHETIC_ORDER`` was added because, without it, the
    upstream plan's §5.2 row 1 ("synthetic backtest/fill") was unrepresentable: rule 1 (see
    :class:`CapabilityTuple`) forbids ``ORDER_SEND``/``CANCEL_REPLACE`` from coexisting with
    ``EconomicEffect.NONE``, yet a synthetic (non-authoritative) fill has no economic effect
    by definition. ``SYNTHETIC_ORDER`` names that non-authoritative synthetic fill —
    "authorizes" nothing at a real or mock broker, consumes zero broker resource — and is the
    single exemption to rule 1, scoped by rule 3′ to the ``SYNTHETIC`` environment only.
    """

    NON_AUTHORIZING_READ = "NON_AUTHORIZING_READ"
    MOCK_ORDER = "MOCK_ORDER"
    REAL_ORDER = "REAL_ORDER"
    SYNTHETIC_ORDER = "SYNTHETIC_ORDER"


#: Operation classes that mutate broker order state (used by the CapabilityTuple validator).
_ORDER_MUTATING_OPERATIONS: frozenset[OperationClass] = frozenset(
    {OperationClass.ORDER_SEND, OperationClass.CANCEL_REPLACE}
)
#: Authorization classes that represent an actual (mock or real) broker order — deliberately
#: excludes SYNTHETIC_ORDER, which is a non-authoritative synthetic fill, not a broker order.
_ORDER_AUTHORIZATIONS: frozenset[AuthorizationClass] = frozenset(
    {AuthorizationClass.MOCK_ORDER, AuthorizationClass.REAL_ORDER}
)


class CapabilityTuple(FrozenModel):
    """The closed 5-axis capability tuple (plan §5.1; slice plan §3 decision 3).

    All 5 axes are **required** (no ``| None``, no default) — a partially-specified tuple is
    not a value this type can hold at all, so "unspecified axis" cannot silently mean
    "any axis" (design #10 §4.1 fail-open seal, applied at the type level). A combined
    ``model_validator`` rejects, at construction time, every axis combination the upstream
    plan and root ``CLAUDE.md`` make structurally impossible (slice plan §3 decision 3, v1.1):

    * **(rule 1)** ``ORDER_SEND``/``CANCEL_REPLACE`` cannot coexist with
      ``EconomicEffect.NONE`` — an order-mutating operation always has *some* economic
      effect — **except** ``SYNTHETIC`` environment x ``SYNTHETIC_ORDER`` authorization: a
      non-authoritative synthetic fill has no economic effect by definition (§5.2 row 1b;
      v1.1 정정).
    * **(rule 2)** ``NON_AUTHORIZING_READ`` cannot coexist with ``ORDER_SEND``/
      ``CANCEL_REPLACE`` — a non-authorizing read never sends or amends an order.
    * **(rule 3)** ``SYNTHETIC`` environment cannot coexist with ``REAL_ORDER``/``MOCK_ORDER``
      — synthetic data never authorizes an actual broker order (there is no broker on the
      other end). ``SYNTHETIC_ORDER`` is unaffected by this rule (see rule 3′).
    * **(rule 3′)** ``SYNTHETIC_ORDER`` cannot coexist with any non-``SYNTHETIC`` environment
      — a synthetic fill is only meaningful inside the ``SYNTHETIC`` environment.
    * **(rule 4)** ``BROKER_PRODUCTION`` x (``ORDER_SEND`` or ``CANCEL_REPLACE``) x
      ``FUTURES`` is **permanently unrepresentable** — the root ``CLAUDE.md`` non-negotiable
      rule ("the real futures account is never funded with margin"; "real-money futures
      order paths ... are permanently blocked by policy") is realized as a type-level
      construction seal, not a predicate a caller could route around after the fact.

    Every rejection raises :class:`~tos.brokercap._base.ArtifactIntegrityError` (a
    ``ValueError`` subclass), which pydantic surfaces as a ``pydantic.ValidationError`` —
    the same discipline as every other brokercap record (design #10 §4.1/§4.2).
    """

    environment: BrokerEnvironment
    operation_class: OperationClass
    economic_effect: EconomicEffect
    asset_scope: AssetScope
    authorization_class: AuthorizationClass

    @model_validator(mode="after")
    def _no_axis_contradiction(self) -> CapabilityTuple:
        """Reject the axis combinations §3 decision 3 (v1.1) makes structurally impossible."""
        synthetic_order_exempt = (
            self.environment is BrokerEnvironment.SYNTHETIC
            and self.authorization_class is AuthorizationClass.SYNTHETIC_ORDER
        )
        if (
            self.operation_class in _ORDER_MUTATING_OPERATIONS
            and self.economic_effect is EconomicEffect.NONE
            and not synthetic_order_exempt
        ):
            raise ArtifactIntegrityError(
                "CapabilityTuple: ORDER_SEND/CANCEL_REPLACE cannot coexist with "
                "EconomicEffect.NONE — an order-mutating operation always has an economic "
                "effect, except the SYNTHETIC x SYNTHETIC_ORDER exemption (slice plan §3 "
                "decision 3, v1.1)"
            )
        if (
            self.authorization_class is AuthorizationClass.NON_AUTHORIZING_READ
            and self.operation_class in _ORDER_MUTATING_OPERATIONS
        ):
            raise ArtifactIntegrityError(
                "CapabilityTuple: NON_AUTHORIZING_READ cannot coexist with "
                "ORDER_SEND/CANCEL_REPLACE — a non-authorizing read never sends or amends "
                "an order (slice plan §3 decision 3)"
            )
        if (
            self.environment is BrokerEnvironment.SYNTHETIC
            and self.authorization_class in _ORDER_AUTHORIZATIONS
        ):
            raise ArtifactIntegrityError(
                "CapabilityTuple: SYNTHETIC environment cannot coexist with "
                "REAL_ORDER/MOCK_ORDER — synthetic data never authorizes an actual broker "
                "order (slice plan §3 decision 3)"
            )
        if (
            self.authorization_class is AuthorizationClass.SYNTHETIC_ORDER
            and self.environment is not BrokerEnvironment.SYNTHETIC
        ):
            raise ArtifactIntegrityError(
                "CapabilityTuple: SYNTHETIC_ORDER cannot coexist with a non-SYNTHETIC "
                "environment — a synthetic fill is only meaningful inside the SYNTHETIC "
                "environment (slice plan §3 decision 3, v1.1 rule 3′)"
            )
        if (
            self.environment is BrokerEnvironment.BROKER_PRODUCTION
            and self.operation_class in _ORDER_MUTATING_OPERATIONS
            and self.asset_scope is AssetScope.FUTURES
        ):
            raise ArtifactIntegrityError(
                "CapabilityTuple: BROKER_PRODUCTION x ORDER_SEND/CANCEL_REPLACE x FUTURES "
                "is permanently unrepresentable — the real futures account is never funded "
                "with margin and real-money futures order paths are policy-blocked (root "
                "CLAUDE.md non-negotiable rules; slice plan §3 decision 3)"
            )
        return self


# ===========================================================================
# §5.2 — closed routing whitelist (plan §5.2 six rows; slice plan §3 decision 4)
# ===========================================================================

#: Row 1 — synthetic backtest/fill: non-authoritative, no economic effect, either asset.
_ROW_1_SYNTHETIC_BACKTEST: frozenset[CapabilityTuple] = frozenset(
    CapabilityTuple(
        environment=BrokerEnvironment.SYNTHETIC,
        operation_class=OperationClass.MARKET_DATA_READ,
        economic_effect=EconomicEffect.NONE,
        asset_scope=asset,
        authorization_class=AuthorizationClass.NON_AUTHORIZING_READ,
    )
    for asset in AssetScope
)

#: Row 1b (v1.1) — synthetic order/cancel-replace: a non-authoritative synthetic fill has no
#: economic effect by definition (the exemption to rule 1), either asset.
_ROW_1B_SYNTHETIC_ORDER: frozenset[CapabilityTuple] = frozenset(
    CapabilityTuple(
        environment=BrokerEnvironment.SYNTHETIC,
        operation_class=operation,
        economic_effect=EconomicEffect.NONE,
        asset_scope=asset,
        authorization_class=AuthorizationClass.SYNTHETIC_ORDER,
    )
    for operation in (OperationClass.ORDER_SEND, OperationClass.CANCEL_REPLACE)
    for asset in AssetScope
)

#: Row 2 — futures paper + real quotes: read-only credential, zero real orders (futures only).
_ROW_2_FUTURES_PAPER_REAL_QUOTES: frozenset[CapabilityTuple] = frozenset(
    CapabilityTuple(
        environment=BrokerEnvironment.BROKER_PRODUCTION,
        operation_class=operation,
        economic_effect=EconomicEffect.NONE,
        asset_scope=AssetScope.FUTURES,
        authorization_class=AuthorizationClass.NON_AUTHORIZING_READ,
    )
    for operation in (OperationClass.MARKET_DATA_READ, OperationClass.ACCOUNT_READ)
)

#: Row 4 — measuring conditions absent from MOCK: official spec (SYNTHETIC, non-authoritative)
#: or a REAL GET probe, zero real orders, either asset. Runtime enforcement of the
#: accompanying "probe manifest required" clause is a later task (§3 decision 5.iv) — this
#: slice only shapes :class:`ProbeManifest`, it does not consume one here.
_ROW_4_PROBE_BEYOND_MOCK: frozenset[CapabilityTuple] = frozenset(
    CapabilityTuple(
        environment=environment,
        operation_class=OperationClass.CAPABILITY_PROBE,
        economic_effect=EconomicEffect.NONE,
        asset_scope=asset,
        authorization_class=AuthorizationClass.NON_AUTHORIZING_READ,
    )
    for environment in (
        BrokerEnvironment.SYNTHETIC,
        BrokerEnvironment.BROKER_PRODUCTION,
    )
    for asset in AssetScope
)

#: The unconditionally-``ADMISSIBLE`` whitelist — plan §5.2 rows 1, 1b (v1.1), 2, 4. Row 5
#: ("선물 실체결 필요 bound") contributes no tuple (no endpoint — a compute-time policy, not a
#: routing case); row 6 ("선물 REAL 주문") is excluded by construction (see
#: :class:`CapabilityTuple`).
_ADMISSIBLE_WHITELIST: frozenset[CapabilityTuple] = (
    _ROW_1_SYNTHETIC_BACKTEST
    | _ROW_1B_SYNTHETIC_ORDER
    | _ROW_2_FUTURES_PAPER_REAL_QUOTES
    | _ROW_4_PROBE_BEYOND_MOCK
)

#: Row 3 — MOCK stock order verification: admitted only at the ``REDUCED`` ceiling, and only
#: when the injected profile/evidence flag is positively ``True`` (plan §5.2 row 3; decision 4).
_REDUCED_WHITELIST: frozenset[CapabilityTuple] = frozenset(
    {
        CapabilityTuple(
            environment=BrokerEnvironment.BROKER_SIMULATION,
            operation_class=OperationClass.ORDER_SEND,
            economic_effect=EconomicEffect.BROKER_RESOURCE_ONLY,
            asset_scope=AssetScope.STOCK,
            authorization_class=AuthorizationClass.MOCK_ORDER,
        )
    }
)


def routing_admissibility(
    capability_tuple: CapabilityTuple,
    *,
    profile_evidence_ok: bool | None = None,
) -> Admissibility:
    """The closed §5.2 whitelist verdict for one capability tuple (slice plan §3 decision 4).

    Reuses the existing 3-token :class:`~tos.brokercap.vocabulary.Admissibility` (no new
    vocabulary): ``ADMISSIBLE`` for the unconditional rows (plan §5.2 rows 1/1b/2/4),
    ``REDUCED`` for the MOCK-stock-order row (row 3) **only** when ``profile_evidence_ok is
    True``, and ``PROHIBITED`` for every other tuple — including row 3 when the evidence flag
    is not positively ``True`` (``None``/``False`` both fail closed) and any tuple this
    module never enumerates at all. There is deliberately no "assume-admissible" fallthrough
    (design #10 §4.1): membership in a whitelist is the only path to anything but
    ``PROHIBITED``.

    Args:
        capability_tuple: The tuple under test.
        profile_evidence_ok: Whether the injected profile/evidence check for the row-3
            (MOCK stock order) case is satisfied. ``True`` only is positive; ``None``/``False``
            fail closed. Irrelevant to every other row.

    Returns:
        The admissibility verdict.
    """
    if capability_tuple in _ADMISSIBLE_WHITELIST:
        return Admissibility.ADMISSIBLE
    if capability_tuple in _REDUCED_WHITELIST:
        if profile_evidence_ok is True:
            return Admissibility.REDUCED
        return Admissibility.PROHIBITED
    return Admissibility.PROHIBITED


# ===========================================================================
# §5.3 — kernel-representable routing invariants (slice plan §3 decision 5)
# ===========================================================================


def endpoint_binding_from_profile_ok(
    capability_tuple: CapabilityTuple,
    profile_key: ProfileKey | None,
    *,
    environment_binding: Mapping[BrokerEnvironment, str],
    asset_binding: Mapping[AssetScope, str],
) -> bool:
    """Whether the tuple's environment/asset axes exactly bind to a Profile Key (§5.3 (i)).

    "endpoint 선택은 ... 승인된 Capability Profile의 exact tuple로 결정한다" (plan §5.3) — this
    predicate is that exact-match check for the two axes the kernel can compare without a
    Phase-2 runtime actor: ``capability_tuple.environment`` must map, through the injected
    ``environment_binding``, to exactly ``profile_key.environment``; and
    ``capability_tuple.asset_scope`` must map, through ``asset_binding``, to exactly
    ``profile_key.instrument_class``. The string correspondence tables are **injected
    arguments**, never kernel constants (no concrete broker string is hardcoded here —
    broker-agnostic, plan §0.1). ``True`` only when both bindings resolve and both match
    exactly; a missing binding-map entry, a ``None`` profile-key coordinate, or a ``None``
    ``profile_key`` itself all fail closed to ``False``.

    Args:
        capability_tuple: The tuple whose environment/asset axes are being bound.
        profile_key: The candidate Profile Key (``None`` => ``False``).
        environment_binding: Injected map from :class:`BrokerEnvironment` to the profile-key
            environment string it must equal.
        asset_binding: Injected map from :class:`AssetScope` to the profile-key
            ``instrument_class`` string it must equal.

    Returns:
        ``True`` iff both axes exactly bind to the profile key's coordinates.
    """
    if profile_key is None:
        return False
    expected_environment = environment_binding.get(capability_tuple.environment)
    expected_instrument_class = asset_binding.get(capability_tuple.asset_scope)
    if expected_environment is None or expected_instrument_class is None:
        return False
    if profile_key.environment is None or profile_key.instrument_class is None:
        return False
    return (
        profile_key.environment == expected_environment
        and profile_key.instrument_class == expected_instrument_class
    )


def credential_principal_separation_ok(
    read_principal: str | None,
    order_principal: str | None,
) -> bool:
    """Whether the read and order credentials are separate principals (§5.3 (ii)).

    "read credential과 order credential은 다른 principal·secret·network policy를 쓴다" (plan
    §5.3) — the principal-identity half of that invariant. ``True`` only when both principals
    are concrete (non-``None``, non-empty) **and** different; a missing principal or an
    identical read/order principal fails closed to ``False``.

    Args:
        read_principal: The read-credential principal identifier.
        order_principal: The order-credential principal identifier.

    Returns:
        ``True`` iff both principals are concrete and distinct.
    """
    if not read_principal or not order_principal:
        return False
    return read_principal != order_principal


# ===========================================================================
# §5.3 (iv) — probe manifest: record shape only (slice plan §3 decision 5.iv)
# ===========================================================================


class ProbeManifest(FrozenModel):
    """The probe-manifest record shape (plan §5.3 last bullet; slice plan §3 decision 5.iv).

    "probe는 emits_orders=false, 허용 HTTP method/TR ID, 데이터 보존 범위, TTL, provenance를
    manifest에 기록한다" (plan §5.3) — this slice carries **only the shape**; filling
    provenance from a real P0-2 probe run and wiring a consumer are separate, later Phase-4
    work (slice plan §1 exclusions). ``emits_orders: Literal[False]`` structurally seals a
    probe manifest from ever claiming to emit an order — mirroring the
    :class:`~tos.brokercap.records.UncertainSendVerdict` all-restrictive-ladder pattern
    (design #10 §4.6): a permissive value is not a value this field can hold.
    """

    emits_orders: Literal[False] = False
    allowed_methods: tuple[str, ...]
    retention: str
    ttl: str
    provenance: str


# ===========================================================================
# Phase 4 작업 3 schema half — provenance classes (slice plan §5-A)
# ===========================================================================


class ProvenanceClass(StrEnum):
    """Where one capability fact came from (upstream plan Phase 4 작업 3; slice plan §5-A).

    The kernel carries only the **class name** — never a concrete source identity. A
    concrete source (the official ``open-trading-api`` SDK, a specific document URL, the
    internal ``shared/kis`` client module, or a specific probe endpoint) is an **instance**
    concern injected through :attr:`CapabilityProvenance.source_ref`, never a kernel
    constant (the same broker-agnostic discipline :class:`BrokerEnvironment` already
    applies — project memory ``tos-spec-broker-agnostic``).

    ``OFFICIAL_SDK`` — the broker's own published SDK/API surface. ``OFFICIAL_DOCUMENT`` —
    the broker's published documentation (not a measurement — see
    :func:`provenance_admits_claim`). ``INTERNAL_CLIENT`` — this repo's own internal broker
    client (also not a measurement of the *broker's* behavior). ``CONTROLLED_GET_PROBE`` — a
    controlled, non-order-emitting GET probe against a live endpoint; the only class that
    requires a :class:`ProbeManifest` (:class:`CapabilityProvenance`'s combined validator).
    """

    OFFICIAL_SDK = "OFFICIAL_SDK"
    OFFICIAL_DOCUMENT = "OFFICIAL_DOCUMENT"
    INTERNAL_CLIENT = "INTERNAL_CLIENT"
    CONTROLLED_GET_PROBE = "CONTROLLED_GET_PROBE"


class ClaimKind(StrEnum):
    """The kind of claim a :class:`CapabilityProvenance` is asked to admit (slice plan §5-A).

    A small closed vocabulary local to :func:`provenance_admits_claim` — not a general
    claims taxonomy. ``MEASURED_BOUND`` — a numeric bound established by an actual
    measurement (a probe or an SDK observation). ``DOCUMENTED_LIMIT`` — a limit merely
    stated by a source, not measured. ``REAL_ORDER_CAPABILITY`` — a claim that a source
    establishes the capability to place a *real* broker order; :func:`provenance_admits_claim`
    never admits this claim from any provenance class (structural — root ``CLAUDE.md``
    "real-money futures order paths ... are permanently blocked by policy" extends to the
    provenance layer: no *evidence artifact* can stand in for that authorization either).
    """

    MEASURED_BOUND = "MEASURED_BOUND"
    DOCUMENTED_LIMIT = "DOCUMENTED_LIMIT"
    REAL_ORDER_CAPABILITY = "REAL_ORDER_CAPABILITY"


#: Provenance classes that are never a measurement — a document / internal client describes
#: or wraps broker behavior, it does not observe it directly (slice plan §5-A).
_NON_MEASURING_CLASSES: frozenset[ProvenanceClass] = frozenset(
    {ProvenanceClass.OFFICIAL_DOCUMENT, ProvenanceClass.INTERNAL_CLIENT}
)


class CapabilityProvenance(FrozenModel):
    """Where one capability fact came from, plus its evidence anchor (slice plan §5-A).

    ``provenance_class`` / ``source_ref`` / ``captured_at`` are all **required** (no
    default) — a provenance with an unspecified class or an unspecified opaque source is not
    a value this type can hold. ``source_ref`` is an opaque instance-level string (no
    concrete source name in the kernel — see :class:`ProvenanceClass`). ``captured_at`` is an
    **injected scalar** (an opaque string), never read from a clock — brokercap accesses no
    clock (design #10 §3.5, the same discipline :class:`~tos.brokercap.records.ProfileVersion`
    already applies to its dates). ``evidence_ref`` reuses
    :class:`~tos.brokercap.records.BrokerEvidenceRef` (evidence is referenced, never
    reimported — design #10 §3.5); it stays ``None`` until a real evidence pipeline supplies
    one (data-filling is out of this slice — slice plan §5-A).

    A combined validator enforces the ``CONTROLLED_GET_PROBE`` <=> ``probe_manifest``
    biconditional in both directions (slice plan §5-A): a ``CONTROLLED_GET_PROBE``
    provenance *must* carry a :class:`ProbeManifest` (a controlled probe without its manifest
    is an unaccountable probe); every other class *must not* (a manifest on a non-probe
    provenance would misrepresent where the fact came from).
    """

    provenance_class: ProvenanceClass
    source_ref: str
    captured_at: str
    evidence_ref: BrokerEvidenceRef | None = None
    probe_manifest: ProbeManifest | None = None

    @model_validator(mode="after")
    def _probe_manifest_iff_controlled_probe(self) -> CapabilityProvenance:
        """Reject a CONTROLLED_GET_PROBE without a manifest, or any other class with one."""
        is_probe = self.provenance_class is ProvenanceClass.CONTROLLED_GET_PROBE
        has_manifest = self.probe_manifest is not None
        if is_probe and not has_manifest:
            raise ArtifactIntegrityError(
                "CapabilityProvenance: CONTROLLED_GET_PROBE requires a probe_manifest — a "
                "controlled probe without its manifest is an unaccountable probe (slice "
                "plan §5-A)"
            )
        if not is_probe and has_manifest:
            raise ArtifactIntegrityError(
                "CapabilityProvenance: only CONTROLLED_GET_PROBE may carry a probe_manifest "
                f"— {self.provenance_class} is not a probe (slice plan §5-A)"
            )
        return self


def provenance_admits_claim(
    provenance: CapabilityProvenance | None,
    claim_kind: ClaimKind | None,
) -> bool:
    """Whether ``provenance`` admits a claim of ``claim_kind`` (slice plan §5-A).

    Three rules, checked in order, all fail-closed:

    1. **Structural denial.** ``REAL_ORDER_CAPABILITY`` is never admitted by any provenance
       — no evidence artifact stands in for the root ``CLAUDE.md`` real-order-authorization
       block (see :class:`ClaimKind`).
    2. **Non-measuring classes.** ``OFFICIAL_DOCUMENT`` / ``INTERNAL_CLIENT`` never admit
       ``MEASURED_BOUND`` — a document is not a measurement, regardless of any attached
       ``evidence_ref``.
    3. **Evidence-gated.** Every other (provenance class, claim kind) combination admits
       **only** when ``evidence_ref is not None`` — an unevidenced provenance never admits a
       claim (design #10 §4.1 fail-open seal, applied here).

    ``None`` for either argument fails closed to ``False`` (§5-A: "None 은 어디든 False").

    Args:
        provenance: The candidate provenance (``None`` => ``False``).
        claim_kind: The claim kind being asked about (``None`` => ``False``).

    Returns:
        ``True`` iff the provenance positively admits the claim.
    """
    if provenance is None or claim_kind is None:
        return False
    if claim_kind is ClaimKind.REAL_ORDER_CAPABILITY:
        return False
    if (
        claim_kind is ClaimKind.MEASURED_BOUND
        and provenance.provenance_class in _NON_MEASURING_CLASSES
    ):
        return False
    return provenance.evidence_ref is not None
