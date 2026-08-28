"""MANDATED test-only seam cross-check: SCI produces ``software_deployment_ok``, spg consumes it
(design #29 §3.5-1 / §6.2; the brokercap #10 / venue #18 decoupled-seam precedent).

spg (ADR-002-014) owns configuration activation and the Hard Safety Envelope. Its semantic-validation
fold carries **step 8** as an injected ``bool | None`` slot that ADR-002-029 fills. This file imports
the real spg model as a **test** to witness that the slot exists, is a plain ``bool | None``, and is
gated with the ``is not True`` fail-closed normalization spg already ships — while the import-closure
test proves ``tos.spg`` is **absent** from the sci runtime closure (edge 0) and sci re-authors no spg
type.

**Landed-name correction (reported to the ratifying orchestrator).** The design contract §6.2 names
the consuming class ``SafetyChangeInputs``; the class that actually landed is
``SemanticValidationInputs`` (``tos/src/tos/spg/records.py`` line 177), carrying
``software_deployment_ok`` at line 206 and gated at ``tos/src/tos/spg/predicates.py`` line 467 — the
two line anchors the contract gives are exact, only the class name in the contract is a phantom. The
seam is bound to the **landed** name, since binding to a non-existent class would make this test
vacuous.

The ADR-002-027 (``tos.sir``) incident seam lives in ``test_seam_sir.py`` — the contract makes it
conditional on a disk measurement (§0.4f) and that measurement flipped mid-implementation; both
readings are recorded there.

Regime tag: structural / produced-value seam substrate only; closes no SCI-EV; an EV-L1-complete
claim is forbidden.
"""

from __future__ import annotations

import ast
from pathlib import Path

import tos.sci as sci
import tos.spg.predicates
import tos.spg.vocabulary
from tos.spg import SemanticValidationInputs


def test_spg_carries_the_software_deployment_ok_slot() -> None:
    """(§3.5-1) The landed spg consumption slot exists and is a plain ``bool | None``."""
    assert "software_deployment_ok" in SemanticValidationInputs.model_fields
    annotation = SemanticValidationInputs.model_fields[
        "software_deployment_ok"
    ].annotation
    assert annotation == (bool | None)


def test_the_sci_verdict_is_the_plain_bool_spg_consumes() -> None:
    """(§5.6e) The producer emits exactly the ``bool`` the consumer's slot accepts — no sci type."""
    verdict = sci.software_deployment_ok_verdict(
        sci.AdmissionResult.ADMIT, True, True, False, True
    )
    assert isinstance(verdict, bool)
    inputs = SemanticValidationInputs(software_deployment_ok=verdict)
    assert inputs.software_deployment_ok is True


def test_a_denied_sci_verdict_flows_into_the_spg_slot_as_false() -> None:
    """(§5.6e) A denial is carried as an explicit ``False``, never as an absent slot."""
    verdict = sci.software_deployment_ok_verdict(
        sci.AdmissionResult.UNKNOWN, True, True, False, True
    )
    assert verdict is False
    assert (
        SemanticValidationInputs(software_deployment_ok=verdict).software_deployment_ok
        is False
    )


def test_spg_gates_the_slot_fail_closed() -> None:
    """(§3.5-1) The spg default is ``None`` and its gate is ``is not True`` — an absent verdict denies.

    This is why the sci producer returns a plain ``bool`` and never ``None``: the consumer's
    fail-closed default already denies, and a produced ``None`` would be indistinguishable from
    "never produced".
    """
    assert SemanticValidationInputs().software_deployment_ok is None
    spg_predicates = Path(tos.spg.predicates.__file__ or "")
    assert spg_predicates.is_file()
    text = spg_predicates.read_text(encoding="utf-8")
    assert "inputs.software_deployment_ok is not True" in text


def test_sci_reauthors_no_spg_type() -> None:
    """(§3.4 / §3.5-1) sci re-authors no spg envelope, profile, or validation type — edge 0."""
    for name in (
        "SemanticValidationInputs",
        "SemanticValidationResult",
        "HardSafetyEnvelope",
        "RuntimeSafetyProfile",
        "profile_within_envelope",
        "activation_atomic",
    ):
        assert not hasattr(sci, name), f"tos.sci must not expose the spg-owned {name}"


def test_sci_does_not_import_spg_at_runtime() -> None:
    """(§3.4) The seam is a value, not an edge — the runtime closure test proves the absence.

    Here the static mirror: no sci source names ``tos.spg`` in an import statement.
    """
    src = Path(__file__).resolve().parents[2] / "src" / "tos" / "sci"
    offenders: list[str] = []
    for path in sorted(src.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offenders += [
                    f"{path.name}:{node.lineno}"
                    for alias in node.names
                    if alias.name.startswith("tos.spg")
                ]
            elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "tos.spg"
            ):
                offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == [], f"sci imports tos.spg: {offenders}"


def test_spg_bundle_member_deferral_names_this_adr() -> None:
    """(§3.5-2 / M5) spg defers four of the seven BundleMember items to ADR-002-029/030 by name.

    ``tos/src/tos/spg/vocabulary.py`` lines 185-187 enumerate the seven deferred items and name
    ADR-002-029/030 as their joint owner. SCI produces four of them (Release Generation,
    compatibility graph, runtime-attestation requirements, software compatibility manifests);
    posttrade (ADR-002-030) owns the two Post-Trade items; the referenced policy objects are shared.
    Neither package imports the other, and neither imports spg (design #29 §3.5).
    """
    spg_vocabulary = Path(tos.spg.vocabulary.__file__ or "")
    assert spg_vocabulary.is_file()
    text = spg_vocabulary.read_text(encoding="utf-8")
    assert "ADR-002-029/030" in text
    assert "Release Generation" in text
    assert "runtime-attestation requirements" in text
