"""§7.2-6 — the Execution Coordinator holds no authority (design #31 §4.3).

The design's target: *"시퀀서가 capacity mutation·command 구성·Transmission Capability 발행을 직접 하지
않음 (RFC-002 §9.1:557·§10.7:724 미러·주입 stage만 호출) — AST/호출 canary"*.

Three independent lines of evidence, because a single one is easy to satisfy vacuously:

1. **structural** — :class:`~tos.engine.AllFalseCoordinatorAuthority` carries the eleven RFC-005
   §12:346-377 ``SHALL NOT`` obligations, and any ``True`` makes the record unconstructable. Every
   engine-emitted record carries it;
2. **AST call canary** — no engine source calls a capacity-mutating, command-constructing,
   capability-issuing, or authority-producing sibling function. This is the "fail-open lives in the
   wiring" check applied to the wiring's own source;
3. **author-level absence** — no engine namespace so much as *binds* such a symbol
   (:mod:`test_engine_import_closure` sweeps ``vars()`` of every submodule, the #27 FD lesson that
   locking the export surface is not locking the package).

Regime tag: orchestration authoring evidence only; closes no EV.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError
from tos.engine import (
    COORDINATOR_SHALL_NOT_FLAGS,
    AllFalseCoordinatorAuthority,
    AttemptRequest,
    CommitmentStep,
    EngineEvidenceRecord,
    EvidenceKind,
    ProvisionalReservation,
    StageAuthorityClass,
    StageOutcome,
    StageVerdict,
)

from ._engine_fixtures import (
    PERMIT_IDENTITY,
    PROOF_DIGEST,
    RecordingTransmit,
    build_core,
    decision_tick,
)

_ENGINE_SRC = Path(__file__).resolve().parents[2] / "src" / "tos" / "engine"

#: Sibling functions whose invocation would mean the Coordinator performed someone else's act.
_FORBIDDEN_CALLS = frozenset(
    {
        # rcl — capacity mutation / capability consumption (RFC-002 §9.1:557)
        "apply_committed",
        "apply_benefit",
        "claim_capability",
        "fold_commands",
        "available_headroom",
        "credible_union_capacity",
        # ioc — broker-command construction (RFC-002 §10.7:724; RFC-005 §7:210-213)
        "compile_command",
        # are / afg / cur — another authority's own decision production
        "risk_decision",
        "action_flow_decision",
        "vector_complete",
        # afg — permit consumption
        "permit_single_use",
    }
)


def test_the_authority_block_carries_the_eleven_shall_nots() -> None:
    """(§4.3) The flag set is exactly the RFC-005 §12:346-377 list — a drift anchor."""
    assert len(COORDINATOR_SHALL_NOT_FLAGS) == 11
    assert len(set(COORDINATOR_SHALL_NOT_FLAGS)) == 11
    fields = set(AllFalseCoordinatorAuthority.model_fields)
    assert fields == set(COORDINATOR_SHALL_NOT_FLAGS), (
        "the model's fields and the named SHALL NOT list must not drift apart — they are one set"
    )


def test_every_flag_defaults_to_false() -> None:
    """(§4.3) The Coordinator's default posture is "no authority at all"."""
    authority = AllFalseCoordinatorAuthority()
    for name in COORDINATOR_SHALL_NOT_FLAGS:
        assert getattr(authority, name) is False


@pytest.mark.parametrize("flag", list(COORDINATOR_SHALL_NOT_FLAGS))
def test_any_true_flag_makes_the_block_unconstructable(flag) -> None:
    """(§4.3) Each of the eleven is enforced individually — none is decorative."""
    with pytest.raises(ValidationError, match="must be false"):
        AllFalseCoordinatorAuthority(**{flag: True})


@pytest.mark.parametrize(
    "model",
    [AttemptRequest, EngineEvidenceRecord, ProvisionalReservation, StageVerdict],
)
def test_every_engine_record_carries_the_all_false_authority_block(model) -> None:
    """(§4.3) The authority block is on the record type, not remembered by convention."""
    assert "authority" in model.model_fields
    assert model.model_fields["authority"].annotation is AllFalseCoordinatorAuthority


def test_an_engine_record_cannot_be_built_with_authority() -> None:
    """(§4.3) A record claiming authority is unconstructable, not merely discouraged."""
    with pytest.raises(ValidationError, match="must be false"):
        StageVerdict(
            step=CommitmentStep.ATOMIC_COMMIT,
            outcome=StageOutcome.ADMIT,
            authority_class=StageAuthorityClass.NON_AUTHORITATIVE_PROVISIONAL,
            authority={"mutates_risk_capacity_ledger": True},
        )


def _called_names(path: Path) -> set[str]:
    """Every simple / attribute call name in one source file."""
    names: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def test_no_engine_source_calls_a_mutation_construction_or_capability_function() -> None:
    """(§7.2-6 AST canary) The sequencer requests; it never performs another actor's act."""
    offenders: list[str] = []
    for path in sorted(_ENGINE_SRC.rglob("*.py")):
        for name in sorted(_called_names(path) & _FORBIDDEN_CALLS):
            offenders.append(f"{path.name}: {name}()")
    assert offenders == [], (
        "the Execution Coordinator SHALL NOT mutate capacity (RFC-002 §9.1:557), construct broker "
        "commands (§10.7:724), issue or reuse a Transmission Capability (RFC-005 §12:358), or "
        f"produce another authority's decision — found: {offenders}"
    )


def test_the_ast_call_canary_detects_a_planted_call(tmp_path: Path) -> None:
    """The canary really catches what it claims to — "green" is not an artefact of a broken scan."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "def go(ledger, rcl):\n"
        "    rcl.apply_committed(x)\n"
        "    compile_command(intent=None)\n"
        "    return claim_capability(y)\n",
        encoding="utf-8",
    )
    found = _called_names(planted) & _FORBIDDEN_CALLS
    assert {"apply_committed", "compile_command", "claim_capability"} <= found


def test_no_authoritative_stage_class_exists() -> None:
    """(§4.4 over-realization seal) A stand-in cannot be promoted — the member does not exist."""
    members = {member.name for member in StageAuthorityClass}
    assert members == {
        "AVAILABLE_PURE_PREDICATE",
        "NON_AUTHORITATIVE_PROVISIONAL",
        "DEFERRED_SEND_BOUNDARY",
    }
    assert "AUTHORITATIVE" not in members


def test_provisional_stand_ins_label_themselves_non_authoritative() -> None:
    """(§4.4) Every stand-in verdict is labelled NON_AUTHORITATIVE_PROVISIONAL in the run."""
    core, sink = build_core(transmit=RecordingTransmit())
    core.handle(decision_tick(sequence=1))
    admitted = [r for r in sink.records if r.kind is EvidenceKind.FLOW_STEP_ADMITTED]
    assert admitted
    assert all(
        r.authority_class is StageAuthorityClass.NON_AUTHORITATIVE_PROVISIONAL for r in admitted
    )
    assert all("NON-AUTHORITATIVE PROVISIONAL" in (r.detail or "") for r in admitted)


def test_the_attempt_request_binds_but_grants_nothing() -> None:
    """(§4.3) The Coordinator's one artifact is a binding, not a permission."""
    core, _ = build_core(transmit=RecordingTransmit())
    result = core.handle(decision_tick(sequence=1))
    assert result.flow is not None and result.flow.attempt is not None
    attempt = result.flow.attempt
    assert attempt.conformance_proof_digest == PROOF_DIGEST
    assert attempt.action_flow_permit_identity == PERMIT_IDENTITY
    for name in COORDINATOR_SHALL_NOT_FLAGS:
        assert getattr(attempt.authority, name) is False
