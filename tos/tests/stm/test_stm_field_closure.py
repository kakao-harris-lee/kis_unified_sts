"""§7.2 (a) field-closure property — the polarity table, the models and the predicates are closed over
each other, **in three directions** (design #30 §7.2 (a); the #28 MAJOR-1 lesson).

design #30 v1.1 upgrade condition (a): every field the §4.3 tables reference must **exist on a declared
model**, every ``bool | None`` field a declared model carries must **appear in one of the three
registries**, and — the #28 MAJOR-1 direction — every polarized field must actually be **read by a
predicate**. The #28 review found a field declared, polarized and never read: it contributed nothing to
any judgement while *looking* like it did. That direction is asserted here for the whole registry, with
the deliberate exceptions given as an **exact whitelist with a substantive documented reason** each.

The design #30 §4.3 judgement table and its separate marker list are re-transcribed here
**independently** (the drift anchor), and every row is resolved to exactly one of two dispositions:

* a **declared model field** with the declared polarity (the common case);
* a **marker** — a non-judgement observation record, either structurally consumed (the recovery-event
  disjunction, the independence claim, the two dashboard gate triggers) or explicitly deferred (the
  five silence markers, whose judgement is unconditional by design #30 MINOR-2).

Regime tag: predicate substrate only; closes **no** STM-EV; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path
from types import ModuleType
from typing import get_args

import pytest
import tos.stm as s
import tos.stm._base
import tos.stm.predicates
import tos.stm.records
import tos.stm.state
import tos.stm.vocabulary
from pydantic import BaseModel

_STM_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "stm"

_SUBMODULES: dict[str, ModuleType] = {
    "_base": tos.stm._base,
    "predicates": tos.stm.predicates,
    "records": tos.stm.records,
    "state": tos.stm.state,
    "vocabulary": tos.stm.vocabulary,
}

#: The design #30 §4.3 **judgement** table, independently transcribed — name -> "positive"/"negative".
#: The UNKNOWN row is expanded to its seven named axes, the suppression row to its six ``disables_*``
#: fields, the recovery row to its four non-revival fields and the signal row to its four prohibitions.
_SECTION_4_3_JUDGEMENT_TABLE: dict[str, str] = {
    # positive polarity
    "is_complete": "positive",
    "closure_1_to_12_complete": "positive",
    "restrictive_response_present": "positive",
    "alert_path_present": "positive",
    "evidence_path_present": "positive",
    "currentness_rule_present": "positive",
    "approved_exclusion_proof_present": "positive",
    "admitted_as_coverage_item": "positive",
    "runtime_falsity_invalidates_property": "positive",
    "units_exact": "positive",
    "window_inside_bound": "positive",
    "uncertainty_treated": "positive",
    "source_continuity_present": "positive",
    "closure_proof_present": "positive",
    "ordering_provable": "positive",
    "residual_common_mode_disclosed": "positive",
    # negative polarity
    "excluded": "negative",
    "coverage_score_present": "negative",
    "permits_individual_exceedance": "negative",
    "semantics_reinterpreted": "negative",
    "hash_equality_claims_equivalence": "negative",
    "cross_host_monotonic_subtracted": "negative",
    "identical_values_claim_continuity": "negative",
    "age_clamped_from_unbounded": "negative",
    "treated_as_healthy": "negative",
    "telemetry_missing": "negative",
    "state_stale": "negative",
    "state_conflicting": "negative",
    "state_ambiguous": "negative",
    "state_discontinuous": "negative",
    "generation_mixed": "negative",
    "state_unverifiable": "negative",
    "disables_collection": "negative",
    "disables_evaluation": "negative",
    "disables_restrictive_signaling": "negative",
    "disables_evidence": "negative",
    "disables_generation_advancement": "negative",
    "disables_final_egress_denial": "negative",
    "self_health_as_proof": "negative",
    "validates_own_continuity_by_own_output": "negative",
    "ack_implies_containment": "negative",
    "advance_of_one_implies_another": "negative",
    "adverse_record_dropped": "negative",
    "elapsed_time_reset": "negative",
    "missing_ack_treated_as_non_acceptance": "negative",
    "cancel_ack_treated_as_fqp": "negative",
    "unknown_effect_capacity_released": "negative",
    "defaulted_to_green": "negative",
    "revived_prior_authority": "negative",
    "resumed_trial": "negative",
    "restored_production_scope": "negative",
    "auto_re_armed": "negative",
    "downgrades_existing_fence": "negative",
    "selects_narrower_scope": "negative",
    "clears_local_latch": "negative",
    "publishes_no_incident": "negative",
    "unioned_or_substituted": "negative",
}

#: The design #30 §4.3 **marker** list, independently transcribed. A marker is a non-judgement
#: observation record: it carries no polarity because it is never itself cleared or denied.
_SECTION_4_3_MARKER_LIST: frozenset[str] = frozenset(
    {
        # SilenceObservation (5) — explicitly deferred
        "no_alert",
        "repeated_heartbeat",
        "quiet_time",
        "empty_query",
        "green_dashboard",
        # MonitoringRecoveryInputs (9, one name shared with the silence set) — structurally consumed
        "restart",
        "reconnect",
        "failover",
        "restore",
        "queue_drain",
        "alert_ack",
        "replay",
        "operator_return",
        # read only in combination
        "claimed_independent",
        # §23 line 499 gate triggers
        "rendering_failed",
        "state_unknown",
    }
)

#: The fields design #30 v1.1 newly required (M1 / M2 / M4 / M5 / M6) — asserted to exist by name so a
#: silent omission of any single revision item is impossible.
_V1_1_NEW_FIELDS = (
    "coverage_score_present",
    "permits_individual_exceedance",
    "treated_as_healthy",
    "disables_evidence",
    "disables_generation_advancement",
    "clears_local_latch",
    "ack_implies_containment",
    "defaulted_to_green",
    "admitted_as_coverage_item",
    "runtime_falsity_invalidates_property",
    "source_continuity_present",
    "closure_proof_present",
    "unioned_or_substituted",
)


def _declared_models() -> dict[str, type[BaseModel]]:
    """Every pydantic model ``tos.stm`` declares, by class name."""
    models: dict[str, type[BaseModel]] = {}
    for module in _SUBMODULES.values():
        for name, obj in vars(module).items():
            if (
                inspect.isclass(obj)
                and issubclass(obj, BaseModel)
                and obj.__module__.startswith("tos.stm")
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


def _registry_disposition(name: str) -> str | None:
    """The disposition the implementation registry declares for ``name`` (``None`` if unregistered)."""
    if name in s.POSITIVE_POLARITY_FIELDS:
        return "positive"
    if name in s.NEGATIVE_POLARITY_FIELDS:
        return "negative"
    if name in s.MARKER_FIELDS:
        return "marker"
    return None


# --- direction 1: every §4.3 row resolves, with the declared disposition ----


@pytest.mark.parametrize("field", sorted(_SECTION_4_3_JUDGEMENT_TABLE))
def test_every_judgement_row_resolves_with_its_declared_polarity(field: str) -> None:
    """(§7.2 (a) forward) Each §4.3 judgement row is a declared model field with its polarity."""
    expected = _SECTION_4_3_JUDGEMENT_TABLE[field]
    assert _registry_disposition(field) == expected, (
        f"{field} polarity drifted from the design #30 §4.3 table "
        f"(table={expected}, registry={_registry_disposition(field)})"
    )
    assert (
        field in _tribool_fields()
    ), f"{field} is in the §4.3 table but no declared model carries it — a phantom field"


@pytest.mark.parametrize("field", sorted(_SECTION_4_3_MARKER_LIST))
def test_every_marker_row_resolves_as_a_marker(field: str) -> None:
    """(§7.2 (a) forward) Each §4.3 marker is registered as a marker and declared on a model."""
    assert _registry_disposition(field) == "marker", (
        f"{field} is a §4.3 marker but the registry says {_registry_disposition(field)} — a marker "
        "carries no polarity because it is never itself cleared or denied"
    )
    assert (
        field in _tribool_fields()
    ), f"{field} is a §4.3 marker with no declared model field"


def test_the_v1_1_new_fields_all_exist() -> None:
    """(§7.2 (a) explicit list) Every field design #30 v1.1 newly required is really declared."""
    fields = _tribool_fields()
    missing = [name for name in _V1_1_NEW_FIELDS if name not in fields]
    assert (
        missing == []
    ), f"design #30 v1.1 fields that are not declared model fields: {missing}"


# --- direction 2: every declared bool|None field is registered --------------


def test_every_declared_tribool_field_is_registered() -> None:
    """(§7.2 (a) reverse) No declared ``bool | None`` field escapes the three registries."""
    unregistered = sorted(
        name for name in _tribool_fields() if _registry_disposition(name) is None
    )
    assert unregistered == [], (
        "declared bool|None fields with no disposition — each could be read with the wrong "
        f"normalization: {unregistered}"
    )


def test_the_registries_are_exactly_the_transcribed_tables() -> None:
    """(§7.2 (a) closure) The three registries equal §4.3 exactly — no silent addition or drop."""
    expected = dict(_SECTION_4_3_JUDGEMENT_TABLE) | dict.fromkeys(
        _SECTION_4_3_MARKER_LIST, "marker"
    )
    registry = (
        dict.fromkeys(s.POSITIVE_POLARITY_FIELDS, "positive")
        | dict.fromkeys(s.NEGATIVE_POLARITY_FIELDS, "negative")
        | dict.fromkeys(s.MARKER_FIELDS, "marker")
    )
    assert registry == expected, (
        "the polarity / marker registry drifted from the design #30 §4.3 tables; "
        f"only-in-registry={sorted(set(registry) - set(expected))}, "
        f"only-in-expected={sorted(set(expected) - set(registry))}"
    )


def test_the_three_registries_are_disjoint() -> None:
    """(§7.2 (a)) A field has exactly one disposition — never two."""
    assert not s.POSITIVE_POLARITY_FIELDS & s.NEGATIVE_POLARITY_FIELDS
    assert not s.POSITIVE_POLARITY_FIELDS & s.MARKER_FIELDS
    assert not s.NEGATIVE_POLARITY_FIELDS & s.MARKER_FIELDS


def test_no_field_carries_a_bare_bool_annotation_outside_the_authority_block() -> None:
    """(§4.3) Only the all-false authority block uses bare ``bool``; every judgement is tri-state.

    A bare ``bool`` cannot express UNKNOWN, and UNKNOWN is exactly what STM-INV-005 line 175 requires to
    be restrictive. The all-false authority block is the one deliberate exception: each of its flags is
    a *constant* ``False`` the validator enforces, never an injected judgement.
    """
    offenders: list[str] = []
    for class_name, model in _declared_models().items():
        if class_name == "AllFalseMonitoringAuthority":
            continue
        for field_name, field in model.model_fields.items():
            if field.annotation is bool:
                offenders.append(f"{class_name}.{field_name}")
    assert (
        offenders == []
    ), f"bare bool judgement coordinate (cannot express UNKNOWN): {offenders}"


# --- direction 3: every registered field is actually CONSUMED --------------

#: Registered coordinates that ``predicates.py`` reaches **dynamically**, through a transcribed
#: ClassVar field-name tuple rather than a literal attribute access. Each entry is ``(class, ClassVar)``;
#: the check expands the tuple and treats its members as consumed only when ``predicates.py`` really
#: references that ClassVar.
_DYNAMIC_FIELD_GROUPS = (
    (s.MonitoringUnknownState, "UNKNOWN_FIELDS"),
    (s.MonitoringSuppression, "DISABLE_FIELDS"),
    (s.MonitoringRecoveryInputs, "RECOVERY_MARKER_FIELDS"),
    (s.MonitoringRecoveryInputs, "NON_REVIVAL_FIELDS"),
    (s.RestrictiveMonitoringSignal, "PROHIBITION_FIELDS"),
)

#: The **only** registered coordinates deliberately left unconsumed, each with its reason. Asserted as
#: an exact set so a genuinely forgotten field can never be absorbed into it silently.
_DELIBERATELY_UNCONSUMED: dict[tuple[str, str], str] = {
    ("SilenceObservation", "no_alert"): (
        "design #30 §2.4 / MINOR-2, OQ1: the five SilenceObservation markers record *which* silence a "
        "runtime observed and take no part in the L1 judgement, because absence_is_not_health consumes "
        "treated_as_healthy UNCONDITIONALLY. Gating on a marker would create a branch in which no "
        "silence is recorded and the health claim goes unchecked — consuming it would be the defect, "
        "not the fix. They exist for the §22 forgery / runtime-audit axis."
    ),
    ("SilenceObservation", "repeated_heartbeat"): (
        "design #30 §2.4 / MINOR-2, OQ1: a deferred SilenceObservation marker — see `no_alert`. The §4 "
        "judgement is unconditional on the kind of silence observed (STM-INV-004 line 171 lists the "
        "kinds, but the invariant is about the *inference*, not the kind), so this records the "
        "observation for the +Security forgery axis and is never a gate."
    ),
    ("SilenceObservation", "quiet_time"): (
        "design #30 §2.4 / MINOR-2, OQ1: a deferred SilenceObservation marker — see `no_alert`. The "
        "same *name* is a genuinely consumed recovery marker on MonitoringRecoveryInputs (§24 line "
        "507), which is exactly why the consumption scan is keyed by (class, field): the silence-side "
        "deferral must stay visible instead of being absorbed by the recovery-side consumption."
    ),
    ("SilenceObservation", "empty_query"): (
        "design #30 §2.4 / MINOR-2, OQ1: a deferred SilenceObservation marker — see `no_alert`. "
        "STM-INV-004 line 171 names 'empty query' explicitly, and the corresponding *judgement* is made "
        "unconditionally through treated_as_healthy; the presence/absence gate for an empty evaluation "
        "corpus is the separate yolk-2 (0) presence gate, not this marker."
    ),
    ("SilenceObservation", "green_dashboard"): (
        "design #30 §2.4 / MINOR-2, OQ1: a deferred SilenceObservation marker — see `no_alert`. The "
        "dashboard *honesty* judgement lives on its own carrier (DashboardStatusView, §6.9) with its "
        "own consumed gate triggers; this field only records that a green dashboard was among the "
        "silences observed."
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


def _model_classes_reachable_from(annotation: object) -> set[type[BaseModel]]:
    """Every declared stm model reachable from a type annotation (through ``tuple`` / ``| None``)."""
    found: set[type[BaseModel]] = set()
    if (
        inspect.isclass(annotation)
        and issubclass(annotation, BaseModel)
        and annotation.__module__.startswith("tos.stm")
    ):
        found.add(annotation)
    for argument in get_args(annotation):
        found |= _model_classes_reachable_from(argument)
    return found


def _candidate_classes(function: ast.FunctionDef) -> set[type[BaseModel]]:
    """The stm models a predicate can legitimately read, from its own parameter annotations.

    A predicate reads fields of the models it is *given*, plus the models those reach through their own
    declared fields (a coverage manifest hands out :class:`~tos.stm.state.CoverageItem` values, so a
    ``manifest``-typed predicate may read ``CoverageItem`` fields). Expanded to a fixpoint so a nested
    carrier two levels down is still attributable.
    """
    declared = _declared_models()
    seeds: set[type[BaseModel]] = set()
    for argument in function.args.args + function.args.kwonlyargs:
        if argument.annotation is None:
            continue
        name = ast.unparse(argument.annotation)
        for class_name, model in declared.items():
            if re.search(rf"\b{re.escape(class_name)}\b", name):
                seeds.add(model)
    frontier = set(seeds)
    while frontier:
        model = frontier.pop()
        for field in model.model_fields.values():
            for reachable in _model_classes_reachable_from(field.annotation):
                if reachable not in seeds:
                    seeds.add(reachable)
                    frontier.add(reachable)
    return seeds


def _consumed_field_pairs() -> set[tuple[str, str]]:
    """Every ``(owning class, field)`` pair ``predicates.py`` really consumes.

    **Attribution is per predicate, not per file (design #30 §7.2 (a), review MINOR-6).** A bare field
    *name* cannot distinguish two models that happen to share it — ``quiet_time`` is declared on both
    :class:`~tos.stm.state.SilenceObservation` (deliberately deferred) and
    :class:`~tos.stm.state.MonitoringRecoveryInputs` (structurally consumed), so a name-keyed scan
    would report the deferred one as consumed and quietly lose the exemption's meaning. Each attribute
    read is therefore attributed to the models its enclosing predicate is actually given, and each
    dynamic ``ClassVar`` group to the class that declares it.
    """
    tree = ast.parse(
        (_STM_SRC / "predicates.py").read_text(encoding="utf-8"),
        filename="predicates.py",
    )
    pairs: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        candidates = _candidate_classes(node)
        reads = _attribute_reads(node)
        classvars = _classvar_references(node)
        for model in candidates:
            for field_name in reads & set(model.model_fields):
                pairs.add((model.__name__, field_name))
        for model, classvar in _DYNAMIC_FIELD_GROUPS:
            if classvar in classvars:
                pairs |= {(model.__name__, name) for name in getattr(model, classvar)}
    return pairs


def _registered_pairs() -> set[tuple[str, str]]:
    """Every ``(owning class, field)`` pair the three registries cover."""
    registered = (
        s.POSITIVE_POLARITY_FIELDS | s.NEGATIVE_POLARITY_FIELDS | s.MARKER_FIELDS
    )
    return {
        (owner, name)
        for name, owners in _tribool_fields().items()
        if name in registered
        for owner in owners
    }


def test_every_registered_field_is_consumed_by_a_predicate() -> None:
    """(§7.2 (a) consumption direction, the #28 MAJOR-1 lesson) A polarized field nothing reads is a
    fail-open.

    The #28 review found a field declared, polarized and **never read** — so a decision could
    self-certify past a sibling's denial. A field that is declared and given a disposition but never
    consumed contributes nothing to any judgement while *looking* like it does; this direction closes
    that gap across the whole registry, per ``(class, field)`` pair.
    """
    consumed = _consumed_field_pairs()
    unconsumed = sorted(
        pair
        for pair in _registered_pairs()
        if pair not in consumed and pair not in _DELIBERATELY_UNCONSUMED
    )
    assert unconsumed == [], (
        "registered coordinates that no predicate reads — each is a silent fail-open, since the "
        f"judgement it looks like it constrains is made without it: {unconsumed}"
    )


def test_the_unconsumed_whitelist_is_exact_and_reasoned() -> None:
    """(§7.2 (a)) The deliberate-non-consumption whitelist cannot grow silently or without a reason."""
    consumed = _consumed_field_pairs()
    registered = _registered_pairs()
    for pair, reason in _DELIBERATELY_UNCONSUMED.items():
        assert (
            pair in registered
        ), f"{pair} is whitelisted but is not a registered coordinate"
        assert pair not in consumed, (
            f"{pair} is now consumed — remove it from the deliberate-non-consumption whitelist "
            "rather than leaving a stale exemption"
        )
        assert len(reason) > 120, f"{pair} needs a substantive documented reason"
    # every whitelisted pair is a SilenceObservation marker and nothing else
    assert {pair[0] for pair in _DELIBERATELY_UNCONSUMED} == {"SilenceObservation"}
    assert {pair[1] for pair in _DELIBERATELY_UNCONSUMED} == set(
        s.SilenceObservation.SILENCE_MARKER_FIELDS
    )


def test_quiet_time_is_attributed_per_class_not_per_name() -> None:
    """(**review MINOR-6**) The shared ``quiet_time`` name resolves to two *different* dispositions.

    Declared on both :class:`~tos.stm.state.SilenceObservation` (a deferred silence marker) and
    :class:`~tos.stm.state.MonitoringRecoveryInputs` (a consumed recovery marker). A name-keyed scan
    reported it globally "consumed" and silently voided the silence-side exemption; the pair-keyed scan
    keeps the two apart, so the deferred one stays in the reasoned whitelist and the consumed one stays
    genuinely locked.
    """
    owners = _tribool_fields()["quiet_time"]
    assert owners == {"SilenceObservation", "MonitoringRecoveryInputs"}
    consumed = _consumed_field_pairs()
    assert ("MonitoringRecoveryInputs", "quiet_time") in consumed
    assert ("SilenceObservation", "quiet_time") not in consumed
    assert ("SilenceObservation", "quiet_time") in _DELIBERATELY_UNCONSUMED
    assert "quiet_time" in s.MonitoringRecoveryInputs.RECOVERY_MARKER_FIELDS
    assert "quiet_time" in s.SilenceObservation.SILENCE_MARKER_FIELDS


def test_the_consumption_scan_detects_an_unread_field(tmp_path: Path) -> None:
    """(canary) The scan really distinguishes a read field from an unread one — not vacuous."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "def f(item):\n    return item.excluded is False\n",
        encoding="utf-8",
    )
    tree = ast.parse(planted.read_text(encoding="utf-8"), filename="planted")
    reads = _attribute_reads(tree)
    assert "excluded" in reads
    assert "coverage_score_present" not in reads


def test_the_attribution_really_narrows_and_is_not_vacuous() -> None:
    """(canary) Pair attribution is strictly finer than name attribution, and still covers everything."""
    consumed_pairs = _consumed_field_pairs()
    assert consumed_pairs, "the pair scan found nothing — it would be vacuously green"
    consumed_names = {name for _, name in consumed_pairs}
    # a name can be consumed while one of its owners is not — that is the whole point
    assert "quiet_time" in consumed_names
    assert ("SilenceObservation", "quiet_time") not in consumed_pairs
    # the seeds really come from annotations: a predicate given no model reads no model field
    assert ("CoverageItem", "excluded") in consumed_pairs
    assert ("MonitorCoverageManifest", "is_complete") in consumed_pairs


def test_the_dynamic_field_groups_are_really_referenced() -> None:
    """(§7.2 (a)) Each ClassVar group is a real transcribed tuple that ``predicates.py`` references."""
    tree = ast.parse(
        (_STM_SRC / "predicates.py").read_text(encoding="utf-8"),
        filename="predicates.py",
    )
    referenced = _classvar_references(tree)
    for model, classvar in _DYNAMIC_FIELD_GROUPS:
        assert (
            classvar in referenced
        ), f"{model.__name__}.{classvar} is never referenced"
        members = getattr(model, classvar)
        assert members, f"{model.__name__}.{classvar} is empty"
        for member in members:
            assert (
                member in model.model_fields
            ), f"{model.__name__}.{classvar} names {member}, which is not a declared field"


def test_the_recovery_markers_arm_the_gate_structurally() -> None:
    """(OQ1 / §2.4) The nine markers are consumed as a disjunction, not as a self-reported flag."""
    source = (_STM_SRC / "predicates.py").read_text(encoding="utf-8")
    assert "RECOVERY_MARKER_FIELDS" in source
    assert "NON_REVIVAL_FIELDS" in source
    assert len(s.MonitoringRecoveryInputs.RECOVERY_MARKER_FIELDS) == 9
    assert len(s.MonitoringRecoveryInputs.NON_REVIVAL_FIELDS) == 4
