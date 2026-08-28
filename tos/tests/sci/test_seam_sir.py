"""MANDATED test-only seam cross-check: the ADR-002-027 incident coordinate SCI injects (§0.4f).

**Why this file exists (measured twice, reported).** The ratified contract §0.4f makes this seam
conditional on a disk measurement at implementation time: "착지 시 seam test … 미착지 시 명시 이연
docstring". ``git ls-files tos/src/tos/sir/`` was **empty** when this package was started (the
deferral branch), and ``tos.sir`` **landed mid-implementation** (commit ``5aa4ade8``,
``tos/src/tos/sir/records.py`` line 246 ``SafetyIncidentRecord.incident_generation``). Leaving a
"sibling not committed" claim in a shipped docstring once the sibling *is* committed would be a
stale phantom claim — exactly the FD #27 anti-phantom defect class — so the deferral was upgraded to
this seam, and both measurements are recorded rather than one of them quietly dropped.

sir (ADR-002-027) owns incident declaration, containment, communication honesty, recovery handoff,
and closure. §20 line 406 is emphatic that none of it revives a release: "Incident declaration,
stabilization, remediation, administrative closure, postmortem, signer recovery, registry recovery,
or quiet time does not readmit an artifact, **clear a release restriction**, restore production
scope, or re-arm." SCI therefore consumes the incident coordinate as an **injected opaque generation
/ digest** and re-authors no incident lifecycle. This file imports the real sir models as a **test**
to witness that the coordinate is a plain ``int`` ordering scalar; the import-closure test proves
``tos.sir`` is **absent** from the sci runtime closure (edge 0).

Regime tag: structural / injected-coordinate seam substrate only; closes no SCI-EV; an
EV-L1-complete claim is forbidden.
"""

from __future__ import annotations

import ast
from pathlib import Path

import tos.sci as sci
import tos.sir as sir


def test_sir_is_committed_now() -> None:
    """(anti-phantom) The sibling this seam cites really exists — the measurement is re-runnable."""
    sir_src = Path(__file__).resolve().parents[2] / "src" / "tos" / "sir"
    assert sir_src.is_dir()
    assert (sir_src / "records.py").is_file()


def test_incident_generation_is_a_plain_int_ordering_scalar() -> None:
    """(§0.4f) sir's incident generation is an ``int | None`` scalar SCI can inject opaquely."""
    annotation = sir.SafetyIncidentRecord.model_fields["incident_generation"].annotation
    assert annotation == (int | None)


def test_sci_carries_the_incident_coordinate_as_an_opaque_digest() -> None:
    """(§2.4) SCI's incident slots are plain scalars — never a sir type."""
    assert sci.AdmittedReleaseSet.model_fields[
        "incident_scope_binding_digest"
    ].annotation == (str | None)
    assert sci.ReleaseRestriction.model_fields["trigger_class"].annotation == (
        str | None
    )


def test_sci_reauthors_no_incident_type() -> None:
    """(§3.5) Incident lifecycle is ADR-002-027-owned — no sir symbol is re-expressed in sci."""
    for name in (
        "SafetyIncidentRecord",
        "SafetyIncidentPolicy",
        "ActiveSafetyIncidentSet",
        "IncidentContainmentPlan",
        "IncidentRecoveryHandoffPackage",
        "IncidentClosureDecision",
        "IncidentLifecycleState",
        "IncidentScope",
        "incident_generation_advances",
        "AllFalseIncidentAuthority",
    ):
        assert hasattr(
            sir, name
        ), f"the seam cites a sir symbol that does not exist: {name}"
        assert not hasattr(sci, name), f"tos.sci must not expose the sir-owned {name}"


def test_sci_does_not_import_sir_at_runtime() -> None:
    """(§3.4) The seam is a value, not an edge — static mirror of the closure assertion."""
    src = Path(__file__).resolve().parents[2] / "src" / "tos" / "sci"
    offenders: list[str] = []
    for path in sorted(src.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offenders += [
                    f"{path.name}:{node.lineno}"
                    for alias in node.names
                    if alias.name.startswith("tos.sir")
                ]
            elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "tos.sir"
            ):
                offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == [], f"sci imports tos.sir: {offenders}"


def test_incident_closure_does_not_revive_a_release_restriction() -> None:
    """(§20 line 406 / SCI-INV-016) The two packages' propositions stay disjoint.

    sir may close an incident; that closure is **not** an input to any SCI predicate and cannot
    clear a Release Restriction. ``restriction_is_monotonic_non_revival`` reads its own
    negative-polarity ``revival_claimed`` argument, so an incident-closure-shaped ``True`` denies —
    it never becomes a clear.
    """
    from ._sci_strategies import CREDIBLE_SCOPE_DIMENSIONS, clean_restriction

    assert (
        sci.restriction_is_monotonic_non_revival(
            clean_restriction(), CREDIBLE_SCOPE_DIMENSIONS, True, True
        )
        is False
    )
    assert (
        sci.restriction_is_monotonic_non_revival(
            clean_restriction(), CREDIBLE_SCOPE_DIMENSIONS, True, None
        )
        is False
    )


def test_sci_documents_the_incident_handoff_boundary() -> None:
    """(§0.4f) The ownership split is stated in prose, not implied."""
    doc = " ".join(((sci.records.__doc__ or "") + (sci.__doc__ or "")).split())
    assert "incident handoff is ADR-002-027" in doc
    assert "consumed as injected opaque generation" in doc
    assert "no ``tos.sir`` import" in doc
