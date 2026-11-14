"""Package-level structure: exports, honest scope declarations, and the sibling-kernel seals."""

from __future__ import annotations

import tos.egressgw
import tos.egressgw._base
import tos.egressgw.construction
import tos.egressgw.gateway
import tos.egressgw.mesh
import tos.egressgw.records
import tos.egressgw.venuefacts
import tos.egressgw.vocabulary

_MODULES = {
    "tos.egressgw": tos.egressgw,
    "tos.egressgw._base": tos.egressgw._base,
    "tos.egressgw.construction": tos.egressgw.construction,
    "tos.egressgw.gateway": tos.egressgw.gateway,
    "tos.egressgw.mesh": tos.egressgw.mesh,
    "tos.egressgw.records": tos.egressgw.records,
    "tos.egressgw.venuefacts": tos.egressgw.venuefacts,
    "tos.egressgw.vocabulary": tos.egressgw.vocabulary,
}


def test_every_exported_name_resolves() -> None:
    """``__all__`` is not padded with phantom names (anti-phantom: existence is grepped too)."""
    for name in tos.egressgw.__all__:
        assert hasattr(
            tos.egressgw, name
        ), f"tos.egressgw.__all__ names a missing {name!r}"


def test_no_module_exposes_a_sibling_kernel_production_symbol() -> None:
    """(§0.3 / §11-3, author-level) The kernels are consumed; their productions are not re-hosted."""
    forbidden = (
        "apply_committed",
        "apply_benefit",
        "claim_capability",
        "fold_commands",
        "vector_complete",
        "quorum_commit_certificate_structurally_complete",
        "quorum_threshold_structurally_met",
        "quorum_coordinates_current",
        "risk_decision",
        "action_flow_decision",
    )
    for module_name, module in _MODULES.items():
        for name in forbidden:
            assert name not in vars(module), (
                f"{module_name} exposes {name!r} — egressgw consumes the sibling kernels and "
                "re-authors none of their productions (design #34 §0.2-2 / §11-3)"
            )


def test_no_module_defines_a_transmit_or_credential_holder() -> None:
    """(§4.5 / firewall) The gateway holds no credential and opens nothing itself."""
    forbidden_fragments = ("app_key", "app_secret", "access_token", "connect", "socket")
    for module_name, module in _MODULES.items():
        for name in vars(module):
            lowered = name.lower()
            for fragment in forbidden_fragments:
                assert fragment not in lowered, (
                    f"{module_name} defines {name!r} — credentials and connections live outside "
                    "tos/ entirely (ADR-002-013 §1; design #34 §4.5/§5.1)"
                )


def test_the_send_transport_port_has_exactly_one_method() -> None:
    """(§5.4) One single-shot method: a retry loop cannot be written against the port."""
    methods = [
        name
        for name in vars(tos.egressgw.gateway.SendTransport)
        if not name.startswith("_")
    ]
    assert methods == ["send_once"]


def test_the_gateway_delegates_to_the_transport_exactly_once_in_its_source() -> None:
    """(§5.4 structural) There is exactly one ``send_once`` call site and it is not in a loop."""
    import ast
    from pathlib import Path

    source = Path(tos.egressgw.gateway.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    call_sites = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "send_once"
    ]
    assert len(call_sites) == 1, "the transport is delegated to exactly once"
    loop_lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.While)):
            for child in ast.walk(node):
                if hasattr(child, "lineno"):
                    loop_lines.add(child.lineno)
    assert call_sites[0].lineno not in loop_lines, (
        "the transport call is inside a loop — a resend loop is exactly the Q-IDEMP-1 defect "
        "this contract exists to make unrepresentable (design #34 §5.4/§13)"
    )
