"""MANDATED test-only seam cross-check: ioc command-conformance -> egress (design #22 §3.4/§3.5/§7)."""

from __future__ import annotations

import tos.egress as egress
from tos.egress import exact_binding_holds
from tos.egress.predicates import _CONFORMANT_TOKEN
from tos.ioc.predicates import mutation_fence_holds
from tos.ioc.records import CanonicalBrokerCommand
from tos.ioc.vocabulary import ConformanceResult

from ._egress_strategies import (
    SCHEME,
    clean_authorized_coordinates,
    clean_qcc,
    clean_request,
)


def test_ioc_owns_mutation_fence_holds_command_proof_coupling() -> None:
    """(§3.4 ioc predicates.py:492) ioc owns mutation_fence_holds — the command↔proof coupling."""
    assert mutation_fence_holds(None, None) is False


def test_egress_reauthors_no_ioc_conformance_decision() -> None:
    """(§3.5) egress re-authors NO ioc derived_command_conformance / mutation_fence_holds."""
    assert not hasattr(egress, "mutation_fence_holds")
    assert not hasattr(egress, "derived_command_conformance")
    assert not hasattr(egress, "ConformanceResult")


def test_conformant_token_matches_ioc_verdict_value() -> None:
    """(§0.4c) The injected ioc verdict token egress accepts equals ConformanceResult.CONFORMANT."""
    assert ConformanceResult.CONFORMANT.value == _CONFORMANT_TOKEN


def test_exact_binding_consumes_the_injected_ioc_verdict() -> None:
    """(§5.7 (iv)) exact_binding_holds admits only when the injected ioc verdict is CONFORMANT."""
    request, qcc, authorized = (
        clean_request(),
        clean_qcc(),
        clean_authorized_coordinates(),
    )
    assert (
        exact_binding_holds(
            request, qcc, authorized, ConformanceResult.CONFORMANT.value, "bytes-digest"
        )
        is True
    )
    assert (
        exact_binding_holds(
            request,
            qcc,
            authorized,
            ConformanceResult.NON_CONFORMANT.value,
            "bytes-digest",
        )
        is False
    )


def test_qcc_accepts_canonical_broker_command_digest() -> None:
    """(§2.4) The QCC canonical_broker_command_digest slot accepts an ioc CanonicalBrokerCommand digest."""
    command = CanonicalBrokerCommand.issue(
        scheme=SCHEME,
        command_id="cmd-1",
        command_generation=1,
    )
    assert command.canonical_digest is not None
    qcc = clean_qcc(canonical_broker_command_digest=command.canonical_digest)
    assert qcc.canonical_broker_command_digest == command.canonical_digest


def test_egress_does_not_import_ioc_at_runtime() -> None:
    """(§3.5) The ioc conformance kernel is consumed as a verdict — egress imports no ioc."""
    assert not hasattr(egress, "CanonicalBrokerCommand")
    assert not hasattr(egress, "OrderConformanceProof")
