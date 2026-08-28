"""Package-level structure: exports, honest scope declarations, and the sibling-kernel seals.

Two things this file locks that nothing else does:

* **``tos.egress`` is consumed, never encroached upon** (design #34 §0.3/§11-3). Not merely
  "egressgw does not modify the kernel", but "egressgw's own namespaces expose no kernel
  production symbol" — the #27 FD lesson that locking the export surface alone leaves the
  submodules open, so every module's ``vars()`` is swept.
* **The honest scope is stated where a reader will hit it.** The package docstring must carry the
  "closes no EV / admits no live send" declaration; a slice whose over-realization warning lives
  only in a design document is one refactor away from losing it.

Regime tag: authoring evidence only; closes no EV (design #34 §1.1).
"""

from __future__ import annotations

import tos.egressgw
import tos.egressgw._base
import tos.egressgw.construction
import tos.egressgw.gateway
import tos.egressgw.records
import tos.egressgw.vocabulary

_MODULES = {
    "tos.egressgw": tos.egressgw,
    "tos.egressgw._base": tos.egressgw._base,
    "tos.egressgw.construction": tos.egressgw.construction,
    "tos.egressgw.gateway": tos.egressgw.gateway,
    "tos.egressgw.records": tos.egressgw.records,
    "tos.egressgw.vocabulary": tos.egressgw.vocabulary,
}


def test_every_exported_name_resolves() -> None:
    """``__all__`` is not padded with phantom names (anti-phantom: existence is grepped too)."""
    for name in tos.egressgw.__all__:
        assert hasattr(tos.egressgw, name), f"tos.egressgw.__all__ names a missing {name!r}"


def test_the_package_declares_its_honest_scope_in_its_own_docstring() -> None:
    """(§1.1) The provisional / no-EV / no-live declaration lives in the code, not only the doc."""
    doc = " ".join((tos.egressgw.__doc__ or "").split())
    for phrase in (
        "closes no EV",
        "synthetic transport",
        "P0-2",
        "admits no live send",
        "no ADR acceptance, restricted-live, or production is authorized",
    ):
        assert phrase in doc, f"the package docstring lost its honest-scope phrase: {phrase!r}"


def test_the_package_states_the_six_five_six_split() -> None:
    """(§4.1) The 6 / 5 / 6 honesty table is stated where a reader of the code will see it."""
    doc = " ".join((tos.egressgw.__doc__ or "").split())
    assert "six are verified by shipped predicates" in doc
    assert "five are non-authoritative provisional stand-ins" in doc
    assert "six" in doc and "deferred" in doc


def test_no_module_exposes_a_sibling_kernel_production_symbol() -> None:
    """(§0.3 / §11-3, author-level) The kernels are consumed; their productions are not re-hosted.

    ``compile_command`` is deliberately **absent** from this list: Order Construction is exactly
    the runtime that is *supposed* to call it (design #34 §3.2). What must not appear is a
    re-hosted kernel *production* — a locally defined quorum certificate builder, a capability
    issuer, a capacity mutation, or a currentness vector producer.
    """
    forbidden = (
        "apply_committed",  # rcl — capacity mutation
        "apply_benefit",  # rcl
        "claim_capability",  # rcl — the capability nonce ledger is rcl's
        "fold_commands",  # rcl
        "vector_complete",  # cur — the per-send currentness production
        "quorum_commit_certificate_structurally_complete",  # egress — QCC production
        "quorum_threshold_structurally_met",  # egress
        "quorum_coordinates_current",  # egress
        "risk_decision",  # are
        "action_flow_decision",  # afg
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
