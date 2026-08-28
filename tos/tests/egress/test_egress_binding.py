"""Core §5.7 — exact binding, no substitution (design #22; EGRESS-EV-005).

Regime tag: structural / coordinate predicate substrate only; EGRESS-EV-005 substrate;
EV-L1-complete claim forbidden. Over-realization boundary: byte-level reconstruction / route /
env enforcement is +Security; L1 is injected coordinate equality + the ioc verdict only.
"""

from __future__ import annotations

import pytest
from tos.egress import exact_binding_holds

from ._egress_strategies import clean_authorized_coordinates, clean_qcc, clean_request

_CONFORMANT = "CONFORMANT"


def test_exact_binding_holds_on_matching_coordinates() -> None:
    """(§5.7) All coordinates equal + capsule digest equal + CONFORMANT ⇒ True."""
    assert (
        exact_binding_holds(
            clean_request(),
            clean_qcc(),
            clean_authorized_coordinates(),
            _CONFORMANT,
            "bytes-digest",
        )
        is True
    )


@pytest.mark.parametrize(
    ("coordinate", "substitute"),
    [
        ("endpoint", "SUBSTITUTED"),
        ("account", "SUBSTITUTED"),
        ("environment", "SUBSTITUTED"),
        ("action", "SUBSTITUTED"),
        ("method", "SUBSTITUTED"),
        ("route_identity", "SUBSTITUTED"),
        ("credential_generation", 999999),
        ("broker_session_generation", 999999),
        ("egress_generation", 999999),
        ("active_principal", "SUBSTITUTED"),
    ],
)
def test_any_substituted_coordinate_fails_binding(
    coordinate: str, substitute: object
) -> None:
    """(§5.7 (i) / EGRESS-INV-004) A substitution on ANY egress coordinate fails binding."""
    tampered = clean_authorized_coordinates(**{coordinate: substitute})
    assert (
        exact_binding_holds(
            clean_request(), clean_qcc(), tampered, _CONFORMANT, "bytes-digest"
        )
        is False
    )


def test_request_bytes_digest_must_equal_capsule_terminus() -> None:
    """(§5.7 (ii) / §0.4e) The request bytes digest must equal the capsule egress_request_digest."""
    assert (
        exact_binding_holds(
            clean_request(),
            clean_qcc(),
            clean_authorized_coordinates(),
            _CONFORMANT,
            "DIFFERENT-terminus",
        )
        is False
    )


def test_command_digest_mismatch_fails_binding() -> None:
    """(§5.7 (iii)) A QCC command digest that mismatches the request command digest fails."""
    qcc = clean_qcc(canonical_command_digest="cmd-A")
    request = clean_request(canonical_command_digest="cmd-B")
    assert (
        exact_binding_holds(
            request,
            qcc,
            clean_authorized_coordinates(),
            _CONFORMANT,
            "bytes-digest",
        )
        is False
    )


def test_non_conformant_ioc_verdict_fails_binding() -> None:
    """(§5.7 (iv) / §0.4c) A non-CONFORMANT injected ioc verdict fails binding."""
    for verdict in ("NON_CONFORMANT", "UNKNOWN", "", None):
        assert (
            exact_binding_holds(
                clean_request(),
                clean_qcc(),
                clean_authorized_coordinates(),
                verdict,
                "bytes-digest",
            )
            is False
        )


def test_none_inputs_fail_binding() -> None:
    """(§5.7 fail-closed) A None request / qcc / authorized set fails binding."""
    assert (
        exact_binding_holds(
            None,
            clean_qcc(),
            clean_authorized_coordinates(),
            _CONFORMANT,
            "bytes-digest",
        )
        is False
    )
    assert (
        exact_binding_holds(
            clean_request(),
            None,
            clean_authorized_coordinates(),
            _CONFORMANT,
            "bytes-digest",
        )
        is False
    )
    assert (
        exact_binding_holds(
            clean_request(), clean_qcc(), None, _CONFORMANT, "bytes-digest"
        )
        is False
    )
