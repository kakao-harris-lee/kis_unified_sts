"""The P4 S1 position carrier: the pure projection, the merge, and the signature append (plan P4 §2)."""

from __future__ import annotations

import inspect
from collections.abc import Callable

import pytest
from pydantic import ValidationError
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.capsule._base import PolicyRef
from tos.capsule.capsule import (
    CapsuleScope,
    DecisionContextCapsule,
    SafetyCriticalFacts,
    SnapshotRef,
)
from tos.dsl import (
    ENTRY_PRICE_BASES,
    POSITION_NAMESPACE,
    UNKNOWN,
    VALUE_NAMESPACE,
    ArtifactIntegrityError,
    AuthoredStrategy,
    Compare,
    CompareOp,
    ContextValue,
    ContextValueView,
    Decision,
    DecisionKind,
    DecisionPolicy,
    EvaluationConfig,
    Operand,
    PositionContext,
    PositionSide,
    Proposal,
    Rule,
    TargetKind,
    TargetSpec,
    build_environment,
    evaluate,
    evaluate_resolved,
    flat_position_context,
    position_context_digest,
    project_position_context,
    resolve_operand,
)

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)
ENFORCEMENT_VERSION = "esc-0"

_ENTRY = 30_000
_ENTRY_AS_OF = 1_700_000_000_000
_BAR_MS = 60_000
_STOP_BP = -50

_INT_FIELD_NAMES: tuple[str, ...] = (
    "held_qty",
    "entry_price",
    "unrealized",
    "unrealized_bp",
    "bars_held",
    "as_of",
)


def _capsule() -> DecisionContextCapsule:
    """An issued Capsule bound to a snapshot reference."""
    return DecisionContextCapsule.issue(
        scheme=SCHEME,
        issuer_principal_id="iss-1",
        critical_input_policy=PolicyRef(policy_id="pol-1", canonical_digest="pd-1"),
        critical_input_snapshot=SnapshotRef(
            snapshot_id="cis-1", canonical_digest="sd-1"
        ),
        scope=CapsuleScope(
            environment="non-live-test",
            account="acct-1",
            instrument="ES",
            decision_class="exit",
        ),
        safety_critical_facts=SafetyCriticalFacts(
            account="acct-1",
            instrument="ES",
            direction="LONG",
            quantity_basis="RISK",
            unit="contract",
        ),
    )


def _view(*, digest: str = "view-0") -> ContextValueView:
    """A value view carrying one admitted ``close`` — the namespace the position sits beside."""
    return ContextValueView(
        snapshot_id="cis-1",
        snapshot_canonical_digest="sd-1",
        values=(
            ContextValue(
                field_key="close",
                value=_ENTRY,
                as_of=_ENTRY_AS_OF,
                payload_digest="pay-1",
                observation_ref="raw-1",
            ),
        ),
        canonical_digest=digest,
        canonicalization_version=EV_L1_PROVISIONAL_VERSION,
    )


def _projection(**overrides: object) -> dict[str, object]:
    """The keyword set :func:`project_position_context` takes, with one row's overrides applied."""
    arguments: dict[str, object] = {
        "side": PositionSide.LONG,
        "held_qty": 1,
        "entry_price": _ENTRY,
        "entry_price_basis": "EXECUTION",
        "entry_as_of": _ENTRY_AS_OF,
        "price": _ENTRY,
        "as_of": _ENTRY_AS_OF,
        "bar_interval_ms": _BAR_MS,
        "source_ref": "ev-send-1",
        "scheme": SCHEME,
    }
    arguments.update(overrides)
    return arguments


def _project(**overrides: object) -> PositionContext:
    """Project one position with the table's overrides."""
    return project_position_context(**_projection(**overrides))  # type: ignore[arg-type]


def _record(**overrides: object) -> dict[str, object]:
    """The keyword set :class:`PositionContext` takes directly, digest-bound to its own content."""
    content: dict[str, object] = {
        "side": PositionSide.FLAT,
        "held_qty": 0,
        "entry_price": None,
        "entry_price_basis": None,
        "unrealized": None,
        "unrealized_bp": None,
        "bars_held": None,
        "source_ref": "ev-send-1",
        "as_of": _ENTRY_AS_OF,
    }
    content.update(
        {name: value for name, value in overrides.items() if name in content}
    )
    arguments: dict[str, object] = dict(content)
    arguments["canonical_digest"] = position_context_digest(scheme=SCHEME, **content)  # type: ignore[arg-type]
    arguments["canonicalization_version"] = EV_L1_PROVISIONAL_VERSION
    arguments.update(overrides)
    return arguments


def _held_dump(**altered: object) -> dict[str, object]:
    """A valid held record's JSON dump, with the named fields altered and the digest left as it was."""
    dumped: dict[str, object] = _project(price=_ENTRY - 300).model_dump(mode="json")
    dumped.update(altered)
    return dumped


def _stop_loss_strategy() -> AuthoredStrategy:
    """A declared stop-loss: a held position whose bp loss reached the configured bound goes FLAT."""
    flat = Decision(
        kind=DecisionKind.FLAT,
        rationale="the declared stop-loss bound was reached — explicit flat",
        target=TargetSpec(
            kind=TargetKind.FLAT,
            account="acct-1",
            instrument="ES",
            direction="SHORT",
            position_effect="CLOSE",
            rationale="the declared stop-loss bound was reached — explicit flat",
        ),
    )
    policy = DecisionPolicy(
        rules=(
            Rule(
                all_of=(
                    Compare(
                        left=Operand(ref=("capsule", POSITION_NAMESPACE, "side")),
                        op=CompareOp.NE,
                        right=Operand(const=PositionSide.FLAT.value),
                    ),
                    Compare(
                        left=Operand(
                            ref=("capsule", POSITION_NAMESPACE, "unrealized_bp")
                        ),
                        op=CompareOp.LE,
                        right=Operand(ref=("config", "stop_loss_bp")),
                    ),
                ),
                decision=flat,
            ),
        ),
        default=Decision(
            kind=DecisionKind.NO_ACTION,
            rationale="no declared bound was reached — hold",
        ),
    )
    return AuthoredStrategy.issue(
        scheme=SCHEME,
        dsl_version="dsl-0",
        config_binding_version="cfg-bind-0",
        policy=policy,
    )


_CONFIG = EvaluationConfig(config_version="cfg-1", bindings={"stop_loss_bp": _STOP_BP})


# --------------------------------------------------------------------------------------
# the pure projection — a hand-computed table
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("side", "price", "unrealized", "unrealized_bp"),
    [
        (PositionSide.LONG, 30_300, 300, 100),
        (PositionSide.LONG, 29_700, -300, -100),
        (PositionSide.SHORT, 29_700, 300, 100),
        (PositionSide.SHORT, 30_300, -300, -100),
        (PositionSide.LONG, 30_001, 1, 0),
        (PositionSide.LONG, 29_999, -1, 0),
        (PositionSide.LONG, 30_299, 299, 99),
        (PositionSide.LONG, 29_701, -299, -99),
        (PositionSide.SHORT, 29_701, 299, 99),
        (PositionSide.SHORT, 30_299, -299, -99),
    ],
)
def test_the_projection_matches_the_hand_computed_table(
    side: PositionSide, price: int, unrealized: int, unrealized_bp: int
) -> None:
    """(plan P4 §2 D4) Favourable is positive on both sides, and the bp figure truncates to zero."""
    position = _project(side=side, price=price)
    assert position.unrealized == unrealized
    assert position.unrealized_bp == unrealized_bp
    assert position.entry_price == _ENTRY


@pytest.mark.parametrize("offset", [1, 299, 300, 3_000])
def test_long_and_short_are_exact_mirrors(offset: int) -> None:
    """(비협상 선물 대칭) The same adverse move reads identically whichever way the tree is held."""
    long_loss = _project(side=PositionSide.LONG, price=_ENTRY - offset)
    short_loss = _project(side=PositionSide.SHORT, price=_ENTRY + offset)
    assert (long_loss.unrealized, long_loss.unrealized_bp) == (
        short_loss.unrealized,
        short_loss.unrealized_bp,
    )
    long_gain = _project(side=PositionSide.LONG, price=_ENTRY + offset)
    short_gain = _project(side=PositionSide.SHORT, price=_ENTRY - offset)
    assert (long_gain.unrealized, long_gain.unrealized_bp) == (
        short_gain.unrealized,
        short_gain.unrealized_bp,
    )
    loss, loss_bp = long_loss.unrealized, long_loss.unrealized_bp
    assert loss is not None and loss_bp is not None
    assert long_gain.unrealized == -loss
    assert long_gain.unrealized_bp == -loss_bp


@pytest.mark.parametrize(
    ("elapsed_ms", "bars_held"),
    [(0, 0), (1, 0), (59_999, 0), (60_000, 1), (119_999, 1), (300_000, 5)],
)
def test_bars_held_counts_whole_elapsed_bars(elapsed_ms: int, bars_held: int) -> None:
    """(plan P4 §2 D2) Whole bars only — a part-bar never counts as one for a time exit."""
    position = _project(as_of=_ENTRY_AS_OF + elapsed_ms)
    assert position.bars_held == bars_held
    assert position.as_of == _ENTRY_AS_OF + elapsed_ms


def test_the_flat_projection_carries_a_quantity_of_zero_and_no_entry() -> None:
    """(plan P4 §2 D2) Proven flat is a published fact, not an absent namespace."""
    flat = flat_position_context(
        source_ref="ev-close-1", as_of=_ENTRY_AS_OF, scheme=SCHEME
    )
    assert flat.side is PositionSide.FLAT
    assert flat.held_qty == 0
    for name in ("entry_price", "entry_price_basis", "unrealized", "bars_held"):
        assert getattr(flat, name) is None
    assert flat.unrealized_bp is None


@pytest.mark.parametrize("basis", sorted(ENTRY_PRICE_BASES))
def test_both_named_entry_price_bases_project(basis: str) -> None:
    """(plan P4 §6) A tenant may gate on the basis, so both must survive the projection."""
    assert _project(entry_price_basis=basis).entry_price_basis == basis


# --------------------------------------------------------------------------------------
# the projection refuses rather than repairs
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"side": PositionSide.FLAT},
        {"held_qty": 0},
        {"held_qty": -1},
        {"held_qty": True},
        {"entry_price": 0},
        {"entry_price": -1},
        {"entry_price": True},
        {"price": 0},
        {"price": -30_000},
        {"bar_interval_ms": 0},
        {"bar_interval_ms": -60_000},
        {"as_of": _ENTRY_AS_OF - 1},
        {"as_of": True},
        {"entry_as_of": 1.0},
        {"entry_price_basis": "MARK"},
        {"entry_price_basis": ""},
    ],
)
def test_the_projection_refuses_every_bad_input(overrides: dict[str, object]) -> None:
    """(plan P4 §2 D3) No partially-filled context is ever returned — the call raises instead."""
    with pytest.raises(ArtifactIntegrityError):
        _project(**overrides)


@pytest.mark.parametrize("source_ref", ["", "   ", "*", "latest", "close.*"])
def test_the_projection_refuses_an_unattributable_source(source_ref: str) -> None:
    """(plan P4 §2 D3) A position with no single evidence pointer is a side channel."""
    with pytest.raises(ValidationError):
        _project(source_ref=source_ref)


# --------------------------------------------------------------------------------------
# the record refuses every inconsistent combination
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"held_qty": 1}, "held_qty=0"),
        ({"held_qty": -1}, "held_qty=0"),
        ({"entry_price": _ENTRY}, "no entry field"),
        ({"unrealized": -1}, "no entry field"),
        ({"unrealized_bp": 0}, "no entry field"),
        ({"bars_held": 0}, "no entry field"),
        ({"entry_price_basis": "EXECUTION"}, "no entry field"),
    ],
)
def test_a_flat_record_refuses_any_quantity_or_entry_field(
    overrides: dict[str, object], match: str
) -> None:
    """(plan P4 §2 D3) FLAT plus an unrealized figure would gate an exit with nothing to close."""
    with pytest.raises(ValidationError, match=match):
        PositionContext(**_record(**overrides))  # type: ignore[arg-type]


_HELD_RECORD: dict[str, object] = {
    "side": PositionSide.LONG,
    "held_qty": 1,
    "entry_price": _ENTRY,
    "entry_price_basis": "EXECUTION",
    "unrealized": -300,
    "unrealized_bp": -100,
    "bars_held": 5,
}


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"held_qty": 0}, "positive held_qty"),
        ({"held_qty": -1}, "positive held_qty"),
        ({"held_qty": True}, "not a bool"),
        ({"entry_price": 0}, "positive entry_price"),
        ({"entry_price": None}, "positive entry_price"),
        ({"entry_price": True}, "not a bool"),
        ({"entry_price_basis": None}, "entry_price_basis"),
        ({"entry_price_basis": "MARK"}, "entry_price_basis"),
        ({"unrealized": None}, "unrealized"),
        ({"unrealized_bp": None}, "unrealized"),
        ({"unrealized_bp": True}, "not a bool"),
        ({"bars_held": None}, "bars_held"),
        ({"bars_held": -1}, "bars_held"),
        ({"bars_held": True}, "not a bool"),
        ({"as_of": True}, "not a bool"),
        ({"source_ref": " "}, "concrete"),
        ({"canonical_digest": ""}, "concrete"),
        ({"canonicalization_version": ""}, "concrete"),
        ({"source_ref": "latest"}, "wildcard"),
    ],
)
def test_a_held_record_refuses_every_inconsistent_combination(
    overrides: dict[str, object], match: str
) -> None:
    """(plan P4 §2 D3) Every field a rule can read is either proven or the record does not exist."""
    arguments = _record(**_HELD_RECORD)
    arguments.update(overrides)
    with pytest.raises(ValidationError, match=match):
        PositionContext(**arguments)  # type: ignore[arg-type]


def test_the_held_record_this_table_mutates_is_itself_valid() -> None:
    """(anti-phantom) The refusals above are the overrides' doing, not a broken baseline."""
    assert PositionContext(**_record(**_HELD_RECORD)).held_qty == 1  # type: ignore[arg-type]


# --------------------------------------------------------------------------------------
# the record verifies itself — it refuses what no constructor would ever produce
# --------------------------------------------------------------------------------------


def test_the_reviewed_record_that_was_accepted_is_refused() -> None:
    """(S1 리뷰 MEDIUM) The reviewer's reproduced input: coerced ints, a bp that disagrees, a free digest."""
    with pytest.raises(ValidationError):
        PositionContext(
            side="LONG",  # type: ignore[arg-type]
            held_qty=1.0,  # type: ignore[arg-type]
            entry_price="30000",  # type: ignore[arg-type]
            entry_price_basis="ORDER",
            unrealized=5,
            unrealized_bp=999999,
            bars_held=0,
            source_ref="x",
            as_of=1,
            canonical_digest="bogus",
            canonicalization_version="nope",
        )


def test_a_bogus_digest_alone_is_refused() -> None:
    """(plan P4 §2 D5) Everything else is the kernel's own output — only the digest was replaced."""
    with pytest.raises(ValidationError, match="is not the digest of its own content"):
        PositionContext(**_held_dump(canonical_digest="bogus"))  # type: ignore[arg-type]


def test_an_unknown_canonicalization_version_is_refused() -> None:
    """(plan P4 §2 D5) An unresolvable scheme cannot recompute the digest, so nothing is proven."""
    with pytest.raises(ValidationError, match="no canonicalization scheme registered"):
        PositionContext(**_held_dump(canonicalization_version="nope"))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("name", "tampered"),
    [
        ("side", "SHORT"),
        ("held_qty", 2),
        ("entry_price", 30_001),
        ("entry_price_basis", "ORDER"),
        ("unrealized", -299),
        ("unrealized_bp", -99),
        ("bars_held", 1),
        ("source_ref", "ev-send-2"),
        ("as_of", _ENTRY_AS_OF + _BAR_MS),
    ],
)
def test_altering_any_covered_field_under_the_original_digest_is_refused(
    name: str, tampered: object
) -> None:
    """(plan P4 §2 D5) Every field the digest covers is tamper-evident when the record is rebuilt."""
    with pytest.raises(ValidationError, match="is not the digest of its own content"):
        PositionContext(**_held_dump(**{name: tampered}))  # type: ignore[arg-type]


def test_an_inconsistent_bp_is_refused_even_with_a_recomputed_digest() -> None:
    """(S1 리뷰 MEDIUM) −300 over 30,000 is −100bp; a digest taken over −99 does not make it true."""
    arguments = _record(**dict(_HELD_RECORD, unrealized_bp=-99))
    with pytest.raises(ValidationError, match="disagrees with unrealized"):
        PositionContext(**arguments)  # type: ignore[arg-type]


@pytest.mark.parametrize("name", _INT_FIELD_NAMES)
@pytest.mark.parametrize("coerce_to", [float, str])
def test_an_int_slot_refuses_a_float_or_a_numeric_string(
    name: str, coerce_to: type
) -> None:
    """(S1 리뷰 MEDIUM) pydantic would coerce 1.0 and "1" silently, and the digest would not cover them."""
    original = _held_dump()[name]
    with pytest.raises(ValidationError, match="must already be of type int"):
        PositionContext(**_held_dump(**{name: coerce_to(original)}))  # type: ignore[arg-type]


@pytest.mark.parametrize("name", ["side", "entry_price_basis", "source_ref"])
def test_a_str_slot_refuses_bytes(name: str) -> None:
    """(S1 리뷰 MEDIUM) pydantic decodes b"ORDER" to "ORDER" — a basis a tenant gates on must arrive as a str."""
    original = _held_dump()[name]
    with pytest.raises(ValidationError, match="must already be of type str"):
        PositionContext(**_held_dump(**{name: str(original).encode()}))  # type: ignore[arg-type]


@pytest.mark.parametrize("as_of", ["5", 5.0, True, None])
def test_the_flat_constructor_refuses_a_non_int_as_of(as_of: object) -> None:
    """(S1 리뷰 LOW) ``as_of="5"`` used to be coerced to 5 while the digest was taken over "5"."""
    with pytest.raises(ArtifactIntegrityError, match="must be an int instant"):
        flat_position_context(source_ref="ev-close-1", as_of=as_of, scheme=SCHEME)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "builder",
    [
        lambda: flat_position_context(
            source_ref="ev-close-1", as_of=_ENTRY_AS_OF, scheme=SCHEME
        ),
        lambda: _project(price=_ENTRY - 300),
    ],
)
def test_a_record_survives_the_json_round_trip_the_next_stage_does(
    builder: Callable[[], PositionContext],
) -> None:
    """(plan P4 §2 D1) The next stage rebuilds this record from an inbox row — equal object, both ways."""
    context = builder()
    assert PositionContext.model_validate(context.model_dump(mode="json")) == context
    assert PositionContext.model_validate_json(context.model_dump_json()) == context


# --------------------------------------------------------------------------------------
# the environment mapping
# --------------------------------------------------------------------------------------


def test_the_mapping_exposes_the_seven_declared_fields_and_no_provenance() -> None:
    """(plan P4 §2 D2) Seven values a rule may read; the evidence pointer is not one of them."""
    mapping = _project(price=_ENTRY - 300).as_environment_mapping()
    assert mapping == {
        "side": "LONG",
        "held_qty": 1,
        "entry_price": _ENTRY,
        "entry_price_basis": "EXECUTION",
        "unrealized": -300,
        "unrealized_bp": -100,
        "bars_held": 0,
    }
    for name in ("source_ref", "as_of", "canonical_digest", "canonicalization_version"):
        assert name not in mapping


def test_the_mapping_omits_what_is_unknown_rather_than_defaulting_it() -> None:
    """(plan P4 §2 D3) An absent key stays UNKNOWN; a 0 would fire a stop-loss on a flat tree."""
    flat = flat_position_context(
        source_ref="ev-close-1", as_of=_ENTRY_AS_OF, scheme=SCHEME
    )
    assert flat.as_environment_mapping() == {"side": "FLAT", "held_qty": 0}
    env = build_environment(_capsule(), _CONFIG, position_context=flat)
    assert (
        resolve_operand(
            Operand(ref=("capsule", POSITION_NAMESPACE, "unrealized_bp")), env
        )
        is UNKNOWN
    )


def test_the_side_is_a_plain_string_so_an_authored_comparison_can_match_it() -> None:
    """(dsl/vocabulary eval_compare) EQ demands ``type(left) is type(right)`` — an enum would never."""
    mapping = flat_position_context(
        source_ref="ev-close-1", as_of=_ENTRY_AS_OF, scheme=SCHEME
    ).as_environment_mapping()
    assert type(mapping["side"]) is str
    env = build_environment(
        _capsule(),
        _CONFIG,
        position_context=flat_position_context(
            source_ref="ev-close-1", as_of=_ENTRY_AS_OF, scheme=SCHEME
        ),
    )
    assert (
        resolve_operand(Operand(ref=("capsule", POSITION_NAMESPACE, "side")), env)
        == PositionSide.FLAT.value
    )


# --------------------------------------------------------------------------------------
# the digest
# --------------------------------------------------------------------------------------


def test_the_record_is_digest_bound_to_its_own_content() -> None:
    """(plan P4 §2 D5) The recorded digest is the digest of the content, recomputed here."""
    position = _project(price=_ENTRY - 300)
    assert position.canonical_digest == position_context_digest(
        side=position.side,
        held_qty=position.held_qty,
        entry_price=position.entry_price,
        entry_price_basis=position.entry_price_basis,
        unrealized=position.unrealized,
        unrealized_bp=position.unrealized_bp,
        bars_held=position.bars_held,
        source_ref=position.source_ref,
        as_of=position.as_of,
        scheme=SCHEME,
    )
    assert position.canonicalization_version == SCHEME.version


@pytest.mark.parametrize(
    "overrides",
    [
        {"price": _ENTRY - 299},
        {"side": PositionSide.SHORT},
        {"held_qty": 2},
        {"entry_price_basis": "ORDER"},
        {"source_ref": "ev-send-2"},
        {"as_of": _ENTRY_AS_OF + _BAR_MS},
    ],
)
def test_every_covered_field_moves_the_digest(overrides: dict[str, object]) -> None:
    """(plan P4 §2 D5) Nothing a rule or the evidence chain reads is outside the digest."""
    moved = dict({"price": _ENTRY - 300}, **overrides)
    assert (
        _project(**moved).canonical_digest
        != _project(price=_ENTRY - 300).canonical_digest
    )


# --------------------------------------------------------------------------------------
# the off path is byte-identical
# --------------------------------------------------------------------------------------


def test_build_environment_without_a_position_is_unchanged() -> None:
    """(plan P4 완료 3) The pre-P4 return value, byte for byte, with and without the argument."""
    capsule = _capsule()
    legacy = {
        "capsule": capsule.model_dump(mode="json"),
        "config": dict(_CONFIG.bindings),
    }
    assert build_environment(capsule, _CONFIG) == legacy
    assert build_environment(capsule, _CONFIG, position_context=None) == legacy
    assert (
        build_environment(
            capsule, _CONFIG, resolved_context=None, position_context=None
        )
        == legacy
    )


def test_the_position_parameter_is_keyword_only_and_defaults_to_absent() -> None:
    """(plan P4 §2 D5) Additive and keyword-only, so no positional call site shifts meaning."""
    for function in (build_environment, evaluate_resolved):
        parameter = inspect.signature(function).parameters["position_context"]
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
        assert parameter.default is None


def test_the_merge_adds_exactly_one_key_beside_the_value_namespace() -> None:
    """(plan P4 §2 D2) A reserved namespace of its own — the value view is untouched."""
    capsule = _capsule()
    baseline = capsule.model_dump(mode="json")
    merged = dict(
        build_environment(
            capsule,
            _CONFIG,
            resolved_context=_view(),
            position_context=_project(price=_ENTRY - 300),
        )["capsule"]
    )
    assert set(merged) - set(baseline) == {VALUE_NAMESPACE, POSITION_NAMESPACE}
    assert merged[VALUE_NAMESPACE] == {"close": _ENTRY}
    merged.pop(VALUE_NAMESPACE)
    merged.pop(POSITION_NAMESPACE)
    assert merged == baseline


def test_a_position_namespace_collision_raises_rather_than_shadowing() -> None:
    """(plan P4 §2 D2) The merge refuses to overwrite covered Capsule content with order state."""

    class _CollidingCapsule(DecisionContextCapsule):
        def model_dump(self, **kwargs: object) -> dict[str, object]:
            dumped = super().model_dump(**kwargs)  # type: ignore[arg-type]
            dumped[POSITION_NAMESPACE] = {"smuggled": 1}
            return dumped

    colliding = _CollidingCapsule.model_construct(**dict(_capsule()))
    with pytest.raises(ArtifactIntegrityError, match="collides"):
        build_environment(colliding, _CONFIG, position_context=_project())
    assert POSITION_NAMESPACE in build_environment(colliding, _CONFIG)["capsule"]


def test_the_signature_without_a_position_reproduces_evaluate_exactly() -> None:
    """(plan P4 완료 3) The position-free path is the old path — outcome and signature both."""
    capsule = _capsule()
    strategy = _stop_loss_strategy()
    plain = evaluate(
        strategy,
        capsule,
        _CONFIG,
        scheme=SCHEME,
        enforcement_mechanism_version=ENFORCEMENT_VERSION,
    )
    threaded = evaluate_resolved(
        strategy,
        capsule,
        _CONFIG,
        scheme=SCHEME,
        enforcement_mechanism_version=ENFORCEMENT_VERSION,
        position_context=None,
    )
    assert threaded.recorded_input_signature == plain.recorded_input_signature
    assert threaded.outcome.model_dump(mode="json") == plain.outcome.model_dump(
        mode="json"
    )


def test_the_signature_appends_the_position_digest_after_the_value_digest() -> None:
    """(plan P4 §2 D5) What a decision read must be in the evidence, in a fixed order."""
    capsule = _capsule()
    position = _project(price=_ENTRY - 300)
    result = evaluate_resolved(
        _stop_loss_strategy(),
        capsule,
        _CONFIG,
        scheme=SCHEME,
        enforcement_mechanism_version=ENFORCEMENT_VERSION,
        resolved_context=_view(digest="view-7"),
        position_context=position,
    )
    assert result.recorded_input_signature.captured_external_value_refs == (
        capsule.critical_input_snapshot.canonical_digest,
        "view-7",
        position.canonical_digest,
    )


# --------------------------------------------------------------------------------------
# end to end: a declared stop-loss
# --------------------------------------------------------------------------------------


def _evaluate_stop_loss(position: PositionContext | None):
    """Evaluate the declared stop-loss policy over one position context."""
    return evaluate_resolved(
        _stop_loss_strategy(),
        _capsule(),
        _CONFIG,
        scheme=SCHEME,
        enforcement_mechanism_version=ENFORCEMENT_VERSION,
        position_context=position,
    )


def test_a_declared_stop_loss_fires_on_a_held_position_past_the_bound() -> None:
    """(plan P4 완료 1) The whole point: a YAML-declared stop-loss decides FLAT from the DSL."""
    outcome = _evaluate_stop_loss(_project(price=_ENTRY - 300)).outcome
    assert isinstance(outcome, Proposal)
    assert outcome.target_kind is TargetKind.FLAT


@pytest.mark.parametrize("price", [_ENTRY - 149, _ENTRY, _ENTRY + 300])
def test_the_same_rule_holds_while_the_bound_is_not_reached(price: int) -> None:
    """(dsl/vocabulary evaluate_policy) −49bp is not −50bp — the default decision stands."""
    outcome = _evaluate_stop_loss(_project(price=price)).outcome
    assert outcome.model_dump(mode="json")["artifact_type"].startswith("NO_ACTION")


def test_the_bound_is_reached_exactly_at_the_declared_bp() -> None:
    """(plan P4 §3) LE, so the declared bound itself fires — a hand-computed boundary row."""
    at_bound = _project(price=_ENTRY - 150)
    assert at_bound.unrealized_bp == _STOP_BP
    assert isinstance(_evaluate_stop_loss(at_bound).outcome, Proposal)


def test_without_a_position_the_stop_loss_cannot_fire() -> None:
    """(plan P4 §2 D3, 완료 3) Absence narrows: no namespace ⇒ UNKNOWN ⇒ comparison False."""
    result = _evaluate_stop_loss(None)
    assert not isinstance(result.outcome, Proposal)
    assert result.recorded_input_signature.captured_external_value_refs == (
        _capsule().critical_input_snapshot.canonical_digest,
    )


def test_a_proven_flat_position_cannot_fire_the_stop_loss_either() -> None:
    """(plan P4 §3) ``side NE FLAT`` is what stops an exit rule from acting on nothing held."""
    flat = flat_position_context(
        source_ref="ev-close-1", as_of=_ENTRY_AS_OF, scheme=SCHEME
    )
    assert not isinstance(_evaluate_stop_loss(flat).outcome, Proposal)
