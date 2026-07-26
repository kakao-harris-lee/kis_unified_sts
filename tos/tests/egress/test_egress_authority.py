"""All-false egress authority + constructive-absence canary (design #22 §4.3/§4.7/§7).

``AllFalseEgressAuthority`` forces every permissive flag ``False`` at construction (any ``True`` ⇒
``ArtifactIntegrityError``): a QCC / request / generation is verified data, not permission
(EGRESS-INV-005/010). The **constructive-absence** canary asserts the package has **no** send /
transmit / sign / re-arm / clear-latch / rotate / failover method — the structural absence of a
transmit method is this package's identity (design #22 §4.7 — "send/transmit 메서드 부재가 정체성").

Regime tag: structural / coordinate predicate substrate only; EGRESS-EV-004 substrate;
EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from tos.egress import (
    ActiveEgressPrincipalSet,
    AllFalseEgressAuthority,
    ArtifactIntegrityError,
    EgressGeneration,
    EgressRequestRecord,
    QuorumCommitCertificate,
    ReplayObservation,
)
from tos.egress._base import DigestBoundArtifact

from ._egress_strategies import (
    SCHEME,
    clean_active_set,
    clean_qcc,
    clean_replay_observation,
    clean_request,
)

_EGRESS_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "egress"

_AUTHORITY_FLAGS = (
    "permits_transmission",
    "creates_route",
    "grants_credential",
    "arms_generation",
    "re_arms",
)

#: Forbidden verb roots — a method whose name starts with any of these would be an egress capability.
_FORBIDDEN_VERB_PREFIXES = (
    "send",
    "transmit",
    "dispatch",
    "emit",
    "publish",
    "deliver",
    "issue",
    "activate",
    "sign",
    "re_arm",
    "rearm",
    "clear_latch",
    "rotate",
    "failover",
    "mutate",
)


def test_default_authority_is_all_false() -> None:
    """(§4.3) The default AllFalseEgressAuthority has every flag False."""
    effect = AllFalseEgressAuthority()
    for flag in _AUTHORITY_FLAGS:
        assert getattr(effect, flag) is False


@pytest.mark.parametrize("flag", _AUTHORITY_FLAGS)
def test_any_true_authority_flag_is_unconstructable(flag: str) -> None:
    """(§4.3) Any True authority flag makes AllFalseEgressAuthority unconstructable."""
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        AllFalseEgressAuthority(**{flag: True})


def test_every_authority_bearing_artifact_carries_all_false() -> None:
    """(§4.3) QCC / request / generation / active-set / replay carry all-false authority."""
    artifacts = (
        clean_qcc(),
        clean_request(),
        EgressGeneration.issue(
            scheme=SCHEME,
            generation_id="g-1",
            egress_generation=1,
        ),
        clean_active_set(),
        clean_replay_observation(observation_id="o-1"),
    )
    for artifact in artifacts:
        effect = artifact.authority_effect
        for flag in _AUTHORITY_FLAGS:
            assert getattr(effect, flag) is False


def test_artifacts_have_no_transmit_or_mutate_method() -> None:
    """(§4.7 constructive absence) No artifact exposes a send / transmit / sign / re-arm method."""
    artifacts = (
        QuorumCommitCertificate,
        EgressRequestRecord,
        EgressGeneration,
        ActiveEgressPrincipalSet,
        ReplayObservation,
    )
    # The inherited core digest machinery (``.issue()`` — issue an artifact's digest) is NOT an
    # egress capability; only egress-artifact-SPECIFIC additions are checked (skip base names).
    base_names = set(dir(DigestBoundArtifact))
    for artifact in artifacts:
        for name in dir(artifact):
            if name in base_names:
                continue
            lowered = name.lstrip("_").lower()
            for prefix in _FORBIDDEN_VERB_PREFIXES:
                assert not lowered.startswith(prefix), (
                    f"{artifact.__name__}.{name} looks like an egress capability method — "
                    "the structural absence of a transmit / sign / re-arm method is this "
                    "package's identity (§4.7)"
                )


def _defined_function_names(path: Path) -> list[str]:
    """Return every def / async def name in a source file (module + method level)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def test_no_egress_source_defines_a_transmit_verb_function() -> None:
    """(§4.7 constructive absence, source scan) No egress source defines a capability-verb function."""
    offenders: list[str] = []
    for path in sorted(_EGRESS_SRC.rglob("*.py")):
        for name in _defined_function_names(path):
            lowered = name.lstrip("_").lower()
            for prefix in _FORBIDDEN_VERB_PREFIXES:
                if lowered.startswith(prefix):
                    offenders.append(f"{path.name}: def {name}")
    assert offenders == [], f"forbidden capability-verb function defined: {offenders}"
