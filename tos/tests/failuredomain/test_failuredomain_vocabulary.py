"""Coordinate-vocabulary per-member binding + closed-StrEnum properties (design #27 §6 / §2.1).

Every member of all four enums is bound **individually** to its ADR-002-009 / RFC-002 anchor —
the design #27 §6 "per-member 계수 property (누락 0 강제)" requirement, taken from the #21 MINOR-1
lesson that an "N members" assertion happily passes with one member missing and one invented. The
hand-transcribed anchor sets below are **regression anchors, not derivations**: they are typed
from the spec text, so a drift in either direction (a dropped member, an invented member, a
renamed value) fails.

Also sealed here: the **plain, closed StrEnum** property (an unregistered value is a construction
failure — design #27 §2.1A m5), the **falsy-forgery** axis (no member value is empty, so no member
can ever be mistaken for absence by a truthiness read), and the ``∅`` marker's deliberate
**non-``str``** identity.

Regime tag: EV-L1 predicate substrate only; closes no FD-EV; the L1-decidable content is
sibling-owned per design #27 §3.5.
"""

from __future__ import annotations

from enum import Enum, StrEnum

import pytest
from tos.failuredomain import (
    SIBLING_OWNER_TOKENS,
    ExplicitlyAnalyzedEmpty,
    FailureBehaviorKind,
    FailureDomainKind,
    IsolationClaimStatus,
    IsolationKind,
)

# --- manually-transcribed regression anchors (design #27 §6 / §0.5) ----------

#: ADR-002-009 §4.1 line 80, transcribed by hand: "process, runtime, node, zone, region,
#: datastore, event infrastructure, cache, network path, broker session, account, credential,
#: workload identity, deployment pipeline, clock, configuration distribution, parser, and shared
#: risk library."
_ADR_41_DOMAINS: frozenset[str] = frozenset(
    {
        "PROCESS",
        "RUNTIME",
        "NODE",
        "ZONE",
        "REGION",
        "DATASTORE",
        "EVENT_INFRASTRUCTURE",
        "CACHE",
        "NETWORK_PATH",
        "BROKER_SESSION",
        "ACCOUNT",
        "CREDENTIAL",
        "WORKLOAD_IDENTITY",
        "DEPLOYMENT_PIPELINE",
        "CLOCK",
        "CONFIGURATION_DISTRIBUTION",
        "PARSER",
        "SHARED_RISK_LIBRARY",
    }
)

#: RFC-002 §24.1 (line 1888) supply-chain categories ADR §4.1 does not spell out, mandated as a
#: floor by ADR §5 line 132 ("SHALL cover at minimum the failure-domain categories listed in
#: RFC-002 §24.1"): source repository + review workflow; isolated build runner + toolchain
#: resolver; artifact signer + key custody + transparency/admission; content-addressed artifact
#: registry + restore path.
_RFC_241_SUPPLY_CHAIN: frozenset[str] = frozenset(
    {
        "SOURCE_REPOSITORY",
        "BUILD_TOOLCHAIN",
        "ARTIFACT_SIGNING",
        "ARTIFACT_REGISTRY",
    }
)

#: ADR §5 line 122 "Failure behavior" field: "Crash, omission, delay, duplication, corruption,
#: partition, stale survival, Byzantine input, or exhaustion."
_ADR_5_BEHAVIORS: frozenset[str] = frozenset(
    {
        "CRASH",
        "OMISSION",
        "DELAY",
        "DUPLICATION",
        "CORRUPTION",
        "PARTITION",
        "STALE_SURVIVAL",
        "BYZANTINE_INPUT",
        "EXHAUSTION",
    }
)

#: ADR §1 line 32 / §4.4 claim-status axis.
_CLAIM_STATUSES: frozenset[str] = frozenset({"ESTABLISHED", "COMMON_MODE", "UNKNOWN"})

#: RFC-002 §24.1 line 1910 "physical/logical/common-mode classification"; ADR §7 line 192.
_ISOLATION_KINDS: frozenset[str] = frozenset({"PHYSICAL", "LOGICAL", "COMMON_MODE"})


# --- FailureDomainKind: 22 = 18 + 4, per member ------------------------------


def test_failure_domain_kind_is_exactly_the_adr_plus_rfc_anchor() -> None:
    """(§2.1A) The taxonomy == ADR §4.1's 18 ∪ RFC-002 §24.1's supply-chain 4 — drift caught."""
    assert {member.name for member in FailureDomainKind} == (
        _ADR_41_DOMAINS | _RFC_241_SUPPLY_CHAIN
    )
    assert len(FailureDomainKind) == 22
    assert len(_ADR_41_DOMAINS) == 18
    assert len(_RFC_241_SUPPLY_CHAIN) == 4
    # the two anchor sets are disjoint — no member is double-counted into 22.
    assert len(_ADR_41_DOMAINS & _RFC_241_SUPPLY_CHAIN) == 0


@pytest.mark.parametrize("name", sorted(_ADR_41_DOMAINS | _RFC_241_SUPPLY_CHAIN))
def test_each_failure_domain_member_binds_name_to_value(name: str) -> None:
    """(§6 per-member binding) Each of the 22 members exists and its value == its name."""
    member = FailureDomainKind[name]
    assert member.value == name
    assert FailureDomainKind(name) is member


@pytest.mark.parametrize("name", sorted(_RFC_241_SUPPLY_CHAIN))
def test_supply_chain_members_are_present_because_of_the_rfc_floor(name: str) -> None:
    """(M1) The four supply-chain domains are members — ADR §5 line 132 makes RFC §24.1 a floor."""
    assert FailureDomainKind[name] in set(FailureDomainKind)
    # and they are NOT part of the ADR §4.1 sentence — they come from the RFC floor.
    assert name not in _ADR_41_DOMAINS


# --- FailureBehaviorKind: 9, per member --------------------------------------


def test_failure_behavior_kind_is_exactly_the_adr_anchor() -> None:
    """(§2.1B) The behavior catalogue == ADR §5 line 122's nine, no more and no fewer."""
    assert {member.name for member in FailureBehaviorKind} == _ADR_5_BEHAVIORS
    assert len(FailureBehaviorKind) == 9


@pytest.mark.parametrize("name", sorted(_ADR_5_BEHAVIORS))
def test_each_failure_behavior_member_binds_name_to_value(name: str) -> None:
    """(§6 per-member binding) Each of the 9 behaviors exists and its value == its name."""
    member = FailureBehaviorKind[name]
    assert member.value == name
    assert FailureBehaviorKind(name) is member


# --- IsolationClaimStatus: 3, per member -------------------------------------


def test_isolation_claim_status_is_exactly_three() -> None:
    """(§2.1C) The claim-status axis == {ESTABLISHED, COMMON_MODE, UNKNOWN}."""
    assert {member.name for member in IsolationClaimStatus} == _CLAIM_STATUSES
    assert len(IsolationClaimStatus) == 3


@pytest.mark.parametrize("name", sorted(_CLAIM_STATUSES))
def test_each_claim_status_member_binds_name_to_value(name: str) -> None:
    """(§6 per-member binding) Each status member exists and its value == its name."""
    member = IsolationClaimStatus[name]
    assert member.value == name
    assert IsolationClaimStatus(name) is member


# --- IsolationKind: 3, per member (M2 — the genuine FD original) -------------


def test_isolation_kind_is_exactly_three() -> None:
    """(§2.1E / M2) The classification == RFC §24.1 line 1910's physical/logical/common-mode."""
    assert {member.name for member in IsolationKind} == _ISOLATION_KINDS
    assert len(IsolationKind) == 3


@pytest.mark.parametrize("name", sorted(_ISOLATION_KINDS))
def test_each_isolation_kind_member_binds_name_to_value(name: str) -> None:
    """(§6 per-member binding) Each isolation-kind member exists and its value == its name."""
    member = IsolationKind[name]
    assert member.value == name
    assert IsolationKind(name) is member


def test_isolation_kind_and_claim_status_share_a_token_but_not_a_type() -> None:
    """(§3.3 proposition identity) COMMON_MODE appears on both axes and the two never collapse."""
    assert IsolationKind.COMMON_MODE.value == IsolationClaimStatus.COMMON_MODE.value
    assert IsolationKind.COMMON_MODE is not IsolationClaimStatus.COMMON_MODE
    assert type(IsolationKind.COMMON_MODE) is not type(IsolationClaimStatus.COMMON_MODE)


# --- plain, closed StrEnum + falsy-forgery axis ------------------------------


@pytest.mark.parametrize(
    "enum_type",
    [FailureDomainKind, FailureBehaviorKind, IsolationClaimStatus, IsolationKind],
)
def test_vocabularies_are_plain_closed_str_enums(enum_type: type[StrEnum]) -> None:
    """(§2.1A m5) Plain StrEnum, closed: an unregistered value cannot be constructed."""
    assert issubclass(enum_type, StrEnum)
    for member in enum_type:
        assert isinstance(member, str)
    with pytest.raises(ValueError):
        enum_type("NOT_A_REGISTERED_MEMBER")
    with pytest.raises(ValueError):
        enum_type("")


@pytest.mark.parametrize(
    "enum_type",
    [FailureDomainKind, FailureBehaviorKind, IsolationClaimStatus, IsolationKind],
)
def test_no_member_value_is_falsy(enum_type: type[StrEnum]) -> None:
    """(falsy forgery) No member is an empty / blank string, so none can read as 'absent'."""
    for member in enum_type:
        assert member.value != ""
        assert member.value.strip() != ""
        assert bool(member) is True


@pytest.mark.parametrize(
    "enum_type",
    [FailureDomainKind, FailureBehaviorKind, IsolationClaimStatus, IsolationKind],
)
def test_member_values_are_unique(enum_type: type[StrEnum]) -> None:
    """(no aliasing) No member is an alias of another — a duplicate value hides a whole member.

    Iterating an ``Enum`` **skips aliases**, so ``len({m.value for m in E}) == len(list(E))``
    passes happily on an aliased enum and the count assertions above would too. ``__members__`` is
    the only mapping that contains aliases, so the drift is detected by comparing it against the
    iteration order — an alias appears in the first set and not the second.
    """
    assert set(enum_type.__members__) == {member.name for member in enum_type}
    values = [member.value for member in enum_type]
    assert len(values) == len(set(values))
    assert len(values) == len(list(enum_type))


# --- the ∅ marker ------------------------------------------------------------


def test_explicitly_analyzed_empty_is_a_single_closed_non_str_member() -> None:
    """(§4.1) The ∅ marker is one plain-Enum member — deliberately NOT a str subclass."""
    assert issubclass(ExplicitlyAnalyzedEmpty, Enum)
    assert not issubclass(ExplicitlyAnalyzedEmpty, str)
    assert len(ExplicitlyAnalyzedEmpty) == 1
    member = ExplicitlyAnalyzedEmpty.EXPLICITLY_ANALYZED_EMPTY
    assert not isinstance(member, str)
    assert bool(member) is True
    # `is` identity over the single closed member is total — the predicate helper relies on it.
    assert all(item is member for item in ExplicitlyAnalyzedEmpty)


# --- the §6.2 sibling owner token anchor -------------------------------------


def test_sibling_owner_tokens_are_a_closed_non_blank_set() -> None:
    """(§6.2) The drift-lock anchor is a frozenset of non-blank dotted tokens."""
    assert isinstance(SIBLING_OWNER_TOKENS, frozenset)
    assert len(SIBLING_OWNER_TOKENS) > 0
    for token in SIBLING_OWNER_TOKENS:
        assert isinstance(token, str)
        assert token.strip() != ""
        assert "." in token, f"{token!r} is not a dotted owner token"
        assert not token.startswith("tos."), (
            f"{token!r} must be a bare injected token, never an import path — "
            "tos.failuredomain holds sibling edge 0 (design #27 §3.2)"
        )
