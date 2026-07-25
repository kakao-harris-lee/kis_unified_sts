"""request_is_complete — complete exact request (design #15 §5.1; IAP-EV-001 substrate, core L1 slice).

both-ways canary (§4.1/§4.7): a complete request earns APPROVE (positive side — a lawful request
is not blocked); an omitted / empty / wildcard / UNKNOWN / not-single-use / no-independent-facts
field cannot yield APPROVE (guard fires). ∅ both-ways: absent field => DENY; missing scope =>
DENY (never zero / wildcard / unconstrained). Forbidden-verb canary: default / wildcard /
substitute-by-omission cannot preserve APPROVE.

Regime tag: predicate / model substrate only; IAP-EV-001 NOT_IMPLEMENTED (`/3` residue);
EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import pytest
from tos.iap import ApprovalResult, request_is_complete

from ._iap_strategies import complete_request, issue_policy, minimal_request


def test_complete_request_earns_approve() -> None:
    """(positive side, §5.1) A fully complete request earns APPROVE — a lawful request is not blocked."""
    assert (
        request_is_complete(complete_request(), issue_policy())
        is ApprovalResult.APPROVE
    )


def test_absent_request_denies() -> None:
    """(∅ / §9 line 253) A None request is absent — cannot yield APPROVE (DENY)."""
    assert request_is_complete(None, issue_policy()) is ApprovalResult.DENY


def test_absent_policy_is_unknown() -> None:
    """(§8 line 230) A None policy cannot determine the policy-owned required set => UNKNOWN (not APPROVE)."""
    assert request_is_complete(complete_request(), None) is ApprovalResult.UNKNOWN


def test_minimal_request_denies() -> None:
    """(§9 line 253) A defaults-only request is structurally incomplete => DENY."""
    assert request_is_complete(minimal_request(), issue_policy()) is ApprovalResult.DENY


@pytest.mark.parametrize(
    "field",
    [
        "account",
        "instrument",
        "proposal_id",
        "proposal_digest",
        "trading_approval_policy_id",
        "canonical_broker_command_digest",
    ],
)
def test_dropped_scalar_field_denies(field: str) -> None:
    """(drop-one, §9 line 253) Dropping any one required scalar to None => DENY (guard fires)."""
    request = complete_request(**{field: None})
    assert request_is_complete(request, issue_policy()) is ApprovalResult.DENY


@pytest.mark.parametrize("field", ["account", "instrument", "environment"])
def test_empty_string_field_denies(field: str) -> None:
    """(∅ / §9 line 253) An empty-string scope field is absent, never zero — DENY."""
    request = complete_request(**{field: "  "})
    assert request_is_complete(request, issue_policy()) is ApprovalResult.DENY


@pytest.mark.parametrize("wildcard", ["*", "ACCT-*", "latest", "LATEST"])
def test_wildcard_field_denies(wildcard: str) -> None:
    """(forbidden-verb: wildcard, §9 line 253) A wildcard / 'latest' scope cannot yield APPROVE — DENY."""
    request = complete_request(account=wildcard)
    assert request_is_complete(request, issue_policy()) is ApprovalResult.DENY


@pytest.mark.parametrize("field", ["action_class", "operating_mode", "direction"])
def test_unknown_token_field_is_unknown(field: str) -> None:
    """(§9 / template L29-30) A present-but-UNKNOWN token => UNKNOWN (never a permissive default)."""
    request = complete_request(**{field: "UNKNOWN"})
    assert request_is_complete(request, issue_policy()) is ApprovalResult.UNKNOWN


def test_required_scope_complete_false_denies() -> None:
    """(§4.1 template L17) required_scope_complete not True is a fail-closed incompleteness => DENY."""
    assert (
        request_is_complete(
            complete_request(required_scope_complete=False), issue_policy()
        )
        is ApprovalResult.DENY
    )
    assert (
        request_is_complete(
            complete_request(required_scope_complete=None), issue_policy()
        )
        is ApprovalResult.DENY
    )


def test_not_single_use_denies() -> None:
    """(template L70-71) single_use / exact_intent_only must be True => otherwise DENY."""
    assert (
        request_is_complete(complete_request(single_use=False), issue_policy())
        is ApprovalResult.DENY
    )
    assert (
        request_is_complete(complete_request(exact_intent_only=None), issue_policy())
        is ApprovalResult.DENY
    )


def test_empty_independent_facts_denies() -> None:
    """(§9 line 249) Empty required-independent-facts / common-mode declarations => DENY."""
    assert (
        request_is_complete(
            complete_request(required_independent_facts=()), issue_policy()
        )
        is ApprovalResult.DENY
    )
    assert (
        request_is_complete(
            complete_request(common_mode_declarations=()), issue_policy()
        )
        is ApprovalResult.DENY
    )


def test_deny_dominates_unknown() -> None:
    """(§5.1) A definite absent field (DENY) dominates a present-UNKNOWN field (a hard reject wins)."""
    request = complete_request(account=None, action_class="UNKNOWN")
    assert request_is_complete(request, issue_policy()) is ApprovalResult.DENY
