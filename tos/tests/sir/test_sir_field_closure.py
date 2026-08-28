"""§7.2 (a) field-closure property — the polarity table and the models are closed over each other.

design #28 v1.1 upgrade condition (a): every field the §4.3 polarity table and the §5/§6 predicates
reference must **exist on a declared model** with the declared polarity, and every ``bool | None`` field
a declared model carries must **appear in the polarity registry**. Both directions, mechanically — a
field in the table with no model is a phantom, and a model field outside the table is an unpolarized
coordinate that could be read with the wrong normalization.

The design #28 §4.3 table is re-transcribed here **independently** (the drift anchor), and every row is
resolved to exactly one of three dispositions:

* a **declared model field** (the common case);
* a **structurally derived** coordinate with a ``_derive_<name>`` function and *no* field of that name
  (design #28 §5.2 conjunct 3 — the C2-2 "structure over self-report" rule);
* a **foreign consumer coordinate** deliberately not authored here (design #28 §3.6 / §4.1 — sir owns
  only the incident component, so the consumers' combined coordinate must be absent).

Regime tag: predicate substrate only; closes **no** SIR-EV; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from types import ModuleType

import pytest
import tos.sir as s
import tos.sir._base
import tos.sir.predicates
import tos.sir.records
import tos.sir.state
import tos.sir.vocabulary
from pydantic import BaseModel

_SIR_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "sir"

_SUBMODULES: dict[str, ModuleType] = {
    "_base": tos.sir._base,
    "predicates": tos.sir.predicates,
    "records": tos.sir.records,
    "state": tos.sir.state,
    "vocabulary": tos.sir.vocabulary,
}

#: The design #28 §4.3 polarity table, **independently transcribed** — name -> "positive" / "negative".
#: The UNKNOWN row is expanded to its ten named axes and the derived row to its four derived names.
_SECTION_4_3_TABLE: dict[str, str] = {
    "is_material": "positive",
    "is_authenticated": "positive",
    "greatest_credible_scope_computed": "positive",
    "dependency_closure_complete": "positive",
    "is_complete": "positive",
    "is_current": "positive",
    "effective_principal_verdict": "positive",
    "recovery_barrier_closed": "positive",
    "accepted_by_recovery_session": "positive",
    "single_operator_variant_supplies_second": "positive",
    "final_quantity_proof_present": "positive",
    "dominating_halt_or_incident": "negative",  # foreign consumer coordinate — NOT authored here
    "single_use_consumed": "negative",
    "consumed_by_live_authority": "negative",
    "broker_state_unknown": "negative",
    "order_state_unknown": "negative",
    "fill_state_unknown": "negative",
    "exposure_unknown": "negative",
    "containment_outcome_unknown": "negative",
    "protection_state_unknown": "negative",
    "external_activity_unknown": "negative",
    "shutdown_result_unknown": "negative",
    "evidence_state_unknown": "negative",
    "currentness_unknown": "negative",
    "open_parent_present": "negative",  # derived
    "open_child_present": "negative",  # derived
    "shared_cause_unresolved": "negative",  # derived
    "common_mode_present": "negative",  # derived
    "restriction_workflow_gated": "negative",
    "severity_label_narrows_scope": "negative",
    "independence_resolved": "positive",  # naming inversion — see the §4.3 note
    "principals_collapsed": "negative",
    "treated_as_enforcement_ack": "negative",
    "is_message_ack": "positive",
    "substitutes_prevention": "negative",
    "authorizes_past_effect": "negative",
    "deny_before_stop": "positive",
    "re_armed": "negative",
    "self_reverted": "negative",
    "revived_prior_authority": "negative",
    "resumed_trial": "negative",
    "restored_production_scope": "negative",
    "scope_establishable": "negative",
}

#: The one §4.3 row that is a **foreign consumer coordinate**: the downstream consumers' *combined*
#: dominance slot. sir produces only the incident component, so this name must be absent from the
#: package entirely (design #28 §3.6 ambiguity prescription; the §4.1 canary enforces the absence).
_FOREIGN_CONSUMER_COORDINATES = frozenset({"dominating_halt_or_incident"})

#: Coordinates that are **predicate arguments** rather than model fields (design #28 §5.3 supporting /
#: §6b thin models). Each is documented at its predicate; they carry no model surface by design.
_ARGUMENT_ONLY_COORDINATES = frozenset(
    {
        "restriction_waits_for_ordinary_pipeline",
        "evidence_loss_blocks_closure",
        "halt_suppressed",
    }
)

#: The §2.4 / §6 field skeletons the §4.3 table does not enumerate, each with its declared polarity.
#: Kept as an explicit, closed supplement so the registry can never grow silently (this set is asserted
#: **exactly**, not as a subset).
_SUPPLEMENTARY_POLARITY: dict[str, str] = {
    # §2.4 field skeletons
    "resolved": "positive",
    "transferred_with_owner_and_evidence": "positive",
    "policy_class_match": "positive",
    "closure_unknown": "negative",
    "self_exempted": "negative",
    "wildcard_or_narrowed": "negative",
    "completed": "negative",
    "assumed_executable": "negative",
    "unestablished": "negative",
    # §6.4 protective carriers (§14 line 388 / §12 step 6 / §14 line 397)
    "protection_blindly_cancelled": "negative",
    "cancellation_arbiter_approved": "positive",
    "exposure_reported_safely_closed": "negative",
    # §6.6 broker-finality tokens (SIR-INV-010 line 194)
    "missing_ack_treated_as_non_acceptance": "negative",
    "cancel_ack_treated_as_final_quantity_proof": "negative",
    "query_omission_treated_as_absence_proof": "negative",
    "blind_retry_authorized": "negative",
    "premature_release_authorized": "negative",
    "optimistic_reconciliation_authorized": "negative",
    # §6b external activity (§15 line 407-412)
    "retroactively_compliant_transmission": "negative",
    "proves_execution_or_final_quantity": "negative",
    "releases_capacity_by_operator_statement": "negative",
    "clears_halt_or_closes_incident": "negative",
    "re_arms": "negative",
    "expands_reconciliation_and_closure": "positive",
}


def _declared_models() -> dict[str, type[BaseModel]]:
    """Every pydantic model ``tos.sir`` declares, by class name."""
    models: dict[str, type[BaseModel]] = {}
    for module in _SUBMODULES.values():
        for name, obj in vars(module).items():
            if (
                inspect.isclass(obj)
                and issubclass(obj, BaseModel)
                and obj.__module__.startswith("tos.sir")
            ):
                models[name] = obj
    return models


def _tribool_fields() -> dict[str, set[str]]:
    """Every ``bool | None`` field across the declared models, mapped to its owning class names."""
    owners: dict[str, set[str]] = {}
    for class_name, model in _declared_models().items():
        for field_name, field in model.model_fields.items():
            if field.annotation == (bool | None):
                owners.setdefault(field_name, set()).add(class_name)
    return owners


def _registry_polarity(name: str) -> str | None:
    """The polarity the implementation registry declares for ``name`` (``None`` if unregistered)."""
    if name in s.POSITIVE_POLARITY_FIELDS:
        return "positive"
    if name in s.NEGATIVE_POLARITY_FIELDS:
        return "negative"
    if name in s.DERIVED_NEGATIVE_POLARITY_NAMES:
        return "negative"
    return None


# --- direction 1: every §4.3 row resolves, with the declared polarity -------


@pytest.mark.parametrize("field", sorted(_SECTION_4_3_TABLE))
def test_every_section_4_3_row_resolves_with_its_declared_polarity(field: str) -> None:
    """(§7.2 (a) forward) Each §4.3 row is a model field, a derivation, or a foreign coordinate."""
    expected = _SECTION_4_3_TABLE[field]
    if field in _FOREIGN_CONSUMER_COORDINATES:
        # a foreign coordinate must be absent from the package (design #28 §3.6 / §4.1 canary)
        assert field not in _tribool_fields()
        assert _registry_polarity(field) is None
        return
    assert _registry_polarity(field) == expected, (
        f"{field} polarity drifted from the design #28 §4.3 table "
        f"(table={expected}, registry={_registry_polarity(field)})"
    )
    if field in s.DERIVED_NEGATIVE_POLARITY_NAMES:
        return
    assert (
        field in _tribool_fields()
    ), f"{field} is in the §4.3 table but no declared model carries it — a phantom field"


def test_derived_coordinates_have_a_derivation_and_no_field() -> None:
    """(§7.2 (a) / §5.2 C2-2) Each derived coordinate has a ``_derive_<name>`` and no field of that name.

    The four no-favorable-subset coordinates are **structurally derived** from the
    :class:`~tos.sir.state.ActiveSetMember` tuple. If one ever became a self-reported ``bool | None``
    field, the #21/#24 "structure over self-report" discipline would be silently reversed — so both the
    presence of the derivation and the *absence* of the field are asserted.
    """
    source = (_SIR_SRC / "predicates.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="predicates.py")
    defined = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    fields = _tribool_fields()
    assert (
        s.DERIVED_NEGATIVE_POLARITY_NAMES
    ), "the derived-coordinate set must not be empty"
    for name in s.DERIVED_NEGATIVE_POLARITY_NAMES:
        assert (
            f"_derive_{name}" in defined
        ), f"_derive_{name} is missing — {name} must be structurally derived (design #28 §5.2 C2-2)"
        assert name not in fields, (
            f"{name} became a declared model field — the no-favorable-subset coordinates are "
            "structurally derived, never self-reported (design #28 §5.2 conjunct 3)"
        )


def test_the_v1_1_new_fields_exist() -> None:
    """(§7.2 (a) explicit list) The seven fields design #28 v1.1 newly required all exist."""
    fields = _tribool_fields()
    for name in (
        "restriction_workflow_gated",
        "severity_label_narrows_scope",
        "substitutes_prevention",
        "authorizes_past_effect",
        "deny_before_stop",
        "is_message_ack",
        "principals_collapsed",
    ):
        assert (
            name in fields
        ), f"{name} (design #28 §7.2 (a)) is not a declared model field"


# --- direction 2: every declared bool|None field is registered --------------


def test_every_declared_tribool_field_is_registered() -> None:
    """(§7.2 (a) reverse) No declared ``bool | None`` field escapes the polarity registry."""
    unregistered = sorted(
        name for name in _tribool_fields() if _registry_polarity(name) is None
    )
    assert unregistered == [], (
        "declared bool|None fields with no polarity — each could be read with the wrong "
        f"normalization: {unregistered}"
    )


def test_registry_is_exactly_the_table_plus_the_declared_supplement() -> None:
    """(§7.2 (a) closure) The registry equals §4.3 (minus the foreign coordinate) plus the supplement.

    Asserted as an **equality**, not a subset: a name that is neither a §4.3 row nor an explicitly
    declared supplement cannot be quietly added to the registry, and a §4.3 row cannot be quietly
    dropped from it.
    """
    from_table = {
        name: polarity
        for name, polarity in _SECTION_4_3_TABLE.items()
        if name not in _FOREIGN_CONSUMER_COORDINATES
    }
    expected = {**from_table, **_SUPPLEMENTARY_POLARITY}
    registry = dict.fromkeys(s.POSITIVE_POLARITY_FIELDS, "positive") | dict.fromkeys(
        s.NEGATIVE_POLARITY_FIELDS, "negative"
    )
    registry |= dict.fromkeys(s.DERIVED_NEGATIVE_POLARITY_NAMES, "negative")
    assert registry == expected, (
        "the polarity registry drifted from §4.3 + the declared supplement; "
        f"only-in-registry={sorted(set(registry) - set(expected))}, "
        f"only-in-expected={sorted(set(expected) - set(registry))}"
    )


def test_supplementary_fields_are_all_declared_somewhere() -> None:
    """(§7.2 (a)) Every supplementary polarity entry is a real declared model field."""
    fields = _tribool_fields()
    missing = sorted(name for name in _SUPPLEMENTARY_POLARITY if name not in fields)
    assert (
        missing == []
    ), f"supplementary polarity entries with no model field: {missing}"


def test_argument_only_coordinates_are_not_model_fields() -> None:
    """(§5.3 supporting) The three §18 line 470 coordinates stay predicate arguments, not fields."""
    fields = _tribool_fields()
    for name in _ARGUMENT_ONLY_COORDINATES:
        assert name not in fields
        assert _registry_polarity(name) is None
    signature = inspect.signature(s.emergency_evidence_no_suppress)
    assert set(signature.parameters) == _ARGUMENT_ONLY_COORDINATES


def test_no_field_carries_a_bare_bool_annotation_outside_the_authority_block() -> None:
    """(§4.3) Only the all-false authority block uses bare ``bool``; every judgement coordinate is tri-state.

    A bare ``bool`` cannot express UNKNOWN, and UNKNOWN is exactly what SIR-INV-009 line 190 requires to
    be conservative. The all-false authority block is the one deliberate exception: each of its flags is
    a *constant* ``False`` the validator enforces, never an injected judgement.
    """
    offenders: list[str] = []
    for class_name, model in _declared_models().items():
        if class_name == "AllFalseIncidentAuthority":
            continue
        for field_name, field in model.model_fields.items():
            if field.annotation is bool:
                offenders.append(f"{class_name}.{field_name}")
    assert (
        offenders == []
    ), f"bare bool judgement coordinate (cannot express UNKNOWN): {offenders}"


# --- direction 3: every registered field is actually CONSUMED by a predicate ---------

#: Registered coordinates that ``predicates.py`` reaches **dynamically**, through a transcribed
#: field-name tuple rather than a literal attribute access. Each entry is ``(class, ClassVar)``; the
#: check expands the tuple and treats its members as consumed only when ``predicates.py`` really
#: references that ClassVar.
_DYNAMIC_FIELD_GROUPS = (
    (s.IncidentUnknownState, "UNKNOWN_FIELDS"),
    (s.RecoveryRevivalInputs, "REVIVAL_FIELDS"),
)

#: The **only** registered coordinates deliberately left unconsumed, each with its reason. Asserted as
#: an exact set so a genuinely forgotten field can never be absorbed into it silently.
_DELIBERATELY_UNCONSUMED: dict[str, str] = {
    "is_authenticated": (
        "ADR §5.2 line 110 defines a Safety Signal as 'an authenticated observation **or** conservative "
        "inference'. design #28 v1.1 M6 withdrew the v1.0 AND gate precisely because gating on it would "
        "dismiss an unauthenticated conservative inference — the field records the evidence axis and the "
        "declaration predicate must NOT read it. Consuming it would be the defect, not the fix."
    ),
}


def _attribute_reads(tree: ast.AST) -> set[str]:
    """Every attribute name read (``Load`` context) anywhere in a source tree."""
    return {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load)
    }


def _classvar_references(tree: ast.AST) -> set[str]:
    """Every ``<Something>.<CLASSVAR>`` name referenced in a source tree."""
    return {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr.isupper()
    }


def _consumed_field_names() -> set[str]:
    """Every registered coordinate ``predicates.py`` actually consumes, directly or dynamically."""
    tree = ast.parse(
        (_SIR_SRC / "predicates.py").read_text(encoding="utf-8"),
        filename="predicates.py",
    )
    consumed = _attribute_reads(tree)
    referenced_classvars = _classvar_references(tree)
    for model, classvar in _DYNAMIC_FIELD_GROUPS:
        if classvar in referenced_classvars:
            consumed |= set(getattr(model, classvar))
    return consumed


def test_every_registered_field_is_consumed_by_a_predicate() -> None:
    """(§7.2 (a) consumption direction) A declared, polarized field that nothing reads is a fail-open.

    The #28 review found ``effective_principal_verdict`` declared, polarized and **never read** — so a
    closure could self-certify §20 item 10 and pass over a hag denial. A field that is declared and
    given a polarity but never consumed contributes nothing to any judgement while *looking* like it
    does; this direction closes that gap for the whole registry.
    """
    consumed = _consumed_field_names()
    registered = (
        s.POSITIVE_POLARITY_FIELDS | s.NEGATIVE_POLARITY_FIELDS
    ) - s.DERIVED_NEGATIVE_POLARITY_NAMES
    unconsumed = sorted(
        name
        for name in registered
        if name not in consumed and name not in _DELIBERATELY_UNCONSUMED
    )
    assert unconsumed == [], (
        "polarized model fields that no predicate reads — each is a silent fail-open, since the "
        f"judgement it looks like it constrains is made without it: {unconsumed}"
    )


def test_the_unconsumed_whitelist_is_exact_and_reasoned() -> None:
    """(§7.2 (a)) The deliberate-non-consumption whitelist cannot grow silently or without a reason."""
    consumed = _consumed_field_names()
    for name, reason in _DELIBERATELY_UNCONSUMED.items():
        assert name in s.POSITIVE_POLARITY_FIELDS | s.NEGATIVE_POLARITY_FIELDS
        assert name not in consumed, (
            f"{name} is now consumed — remove it from the deliberate-non-consumption whitelist "
            "rather than leaving a stale exemption"
        )
        assert len(reason) > 80, f"{name} needs a substantive documented reason"


def test_the_consumption_scan_detects_an_unread_field(tmp_path: Path) -> None:
    """(canary) The scan really distinguishes a read field from an unread one — not vacuous."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "def f(closure):\n    return closure.single_use_consumed is False\n",
        encoding="utf-8",
    )
    tree = ast.parse(planted.read_text(encoding="utf-8"), filename="planted")
    reads = _attribute_reads(tree)
    assert "single_use_consumed" in reads
    assert "effective_principal_verdict" not in reads


def test_the_hag_verdict_is_read_not_merely_declared() -> None:
    """(MAJOR-1 regression) ``effective_principal_verdict`` is consumed by the closure predicate."""
    assert "effective_principal_verdict" in _consumed_field_names()
