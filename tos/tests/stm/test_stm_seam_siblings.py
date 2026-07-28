"""Forward-seam consistency — stm produces, four committed siblings consume (design #30 §3.6).

STM is a **greenfield content owner with no inbound deferee** but the richest committed forward seam in
the series: four landed siblings already consume coordinates stm produces, and every one of those
consumptions is **anonymous** — a dimension name, a string token, an all-false authority block, an
opaque generation. This file re-resolves each of the four clades against the real sibling source, so a
rename or removal fails here rather than leaving a citation quietly wrong, and asserts the seam stays
**forward**: polarity and naming consistency only, **never a value wiring**.

The single most dangerous claim in this contract is the one the #28 review caught in SIR: asserting that
a sibling does **not** own a dimension it actually owns. cur really does own the ``MONITORING``
currentness dimension key, and it really is inside cur's mandated floor. That is asserted **positively**
here, together with the absence of cur's judgement names from every stm source (the §4.1 canary).

Regime tag: predicate substrate only; closes **no** STM-EV; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from pathlib import Path

import tos.stm as s

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TOS_SRC = _REPO_ROOT / "tos" / "src" / "tos"
_STM_SRC = _TOS_SRC / "stm"


def _stm_sources() -> list[Path]:
    """Every ``tos.stm`` source, asserted **non-empty** so a path typo cannot make a sweep vacuous."""
    sources = sorted(_STM_SRC.rglob("*.py"))
    assert (
        sources
    ), f"no tos.stm source found under {_STM_SRC} — this sweep would be vacuous"
    return sources


# --- clade 1: cur MONITORING currentness dimension -------------------------


def test_cur_owns_the_monitoring_currentness_dimension() -> None:
    """(**#28 C1 head-on**, §0.4b-2/§3.5) cur really holds the MONITORING key, in its mandated floor.

    The #28 review's CRITICAL was a contract asserting a sibling did *not* own a dimension it did own.
    Here the claim runs the other way and is verified positively: cur's currentness dimension-key enum
    has a ``MONITORING`` member and that member is inside cur's mandated dimension floor. stm produces
    that dimension's **value**; cur keeps the completeness judgement.
    """
    from tos.cur import MANDATED_DIMENSION_FLOOR, DimensionKey, vector_complete

    assert DimensionKey.MONITORING in MANDATED_DIMENSION_FLOOR
    assert callable(vector_complete)
    source = (_TOS_SRC / "cur" / "vocabulary.py").read_text(encoding="utf-8")
    assert 'MONITORING = "MONITORING"' in source


def test_stm_does_not_reauthor_curs_dimension_judgement() -> None:
    """(§3.6 direct-wiring ban / §4.1 canary) cur's judgement names are absent from stm authorship."""
    for name in ("DimensionKey", "vector_complete", "MANDATED_DIMENSION_FLOOR"):
        assert not hasattr(
            s, name
        ), f"tos.stm exposes {name} — that judgement is cur-owned"
        for path in _stm_sources():
            assert name not in path.read_text(encoding="utf-8"), (
                f"{path.name} references the cur-owned name {name} — stm produces the MONITORING "
                "dimension's value only (design #30 §3.6)"
            )


def test_the_stm_coverage_dimension_is_a_different_axis_from_curs() -> None:
    """(§0.5 seal 1) Same word, different proposition: a coverage closure axis vs a currentness key."""
    from tos.cur import DimensionKey

    assert s.CoverageDimension is not DimensionKey
    assert "MONITORING" not in {member.value for member in s.CoverageDimension}
    # stm's catalogue is the §13 line 347 eleven-dimension dependency closure
    assert len(s.CoverageDimension) == 11


# --- clade 2: spg governed-artifact-kind tokens ---------------------------


def test_spg_owns_the_governed_artifact_kind_tokens() -> None:
    """(§0.5 seal 2 / §3.5) The three spg kind tokens exist and are not these artifact models."""
    source = (_TOS_SRC / "spg" / "vocabulary.py").read_text(encoding="utf-8")
    for token in (
        "SAFETY_MONITORING_POLICY",
        "CRITICAL_TELEMETRY_MANIFEST",
        "MONITOR_COVERAGE_MANIFEST",
    ):
        assert f'{token} = "{token}"' in source, f"spg no longer enumerates {token}"
    # spg names the *kind of artifact ADR-002-014 governs*; stm authors the artifact *model*.
    for model in (
        s.SafetyMonitoringPolicy,
        s.CriticalTelemetryManifest,
        s.MonitorCoverageManifest,
    ):
        assert model.__module__.startswith("tos.stm")


# --- clade 3: rlp EV-L6 monitor-result concept seam ------------------------


def test_rlp_consumes_the_non_authorizing_monitor_result_concept() -> None:
    """(§0.4b-4 / §3.6) rlp's own docstring names the injected -028 coordinate — verbatim, still there."""
    from tos.rlp import monitoring_not_preventive

    assert callable(monitoring_not_preventive)
    source = (_TOS_SRC / "rlp" / "predicates.py").read_text(encoding="utf-8")
    assert "def monitoring_not_preventive(" in source
    assert "injected -028 (STM) coordinate, not landed" in source
    # the consumption is an anonymous all-false authority block, never a tos.stm type
    assert "tos.stm" not in source


def test_the_rlp_polarity_matches_what_stm_produces() -> None:
    """(§3.6 polarity consistency) Both sides clear only on a genuinely all-false authority block.

    rlp clears ``monitoring_not_preventive`` only when the injected authority block is all-false; stm's
    :func:`~tos.stm.predicates.handoff_is_non_authorizing` produces exactly that shape. The two are
    checked for **polarity agreement** — no value is wired between them (sibling edge 0).
    """
    from tos.rlp import AllFalseTrialAuthority, monitoring_not_preventive

    assert monitoring_not_preventive(AllFalseTrialAuthority()) is True
    assert monitoring_not_preventive(None) is False
    assert s.all_false_monitoring_authority(s.AllFalseMonitoringAuthority()) is True
    assert s.all_false_monitoring_authority(None) is False


# --- clade 4: sir -028 handoff anticipation --------------------------------


def test_sir_anticipates_the_028_handoff_as_an_injected_coordinate() -> None:
    """(§0.4b-5 / §3.6) sir's own sources still name the not-landed -028 handoff, anonymously."""
    for relative in ("sir/predicates.py", "sir/state.py"):
        raw = (_TOS_SRC / relative).read_text(encoding="utf-8")
        text = " ".join(
            raw.split()
        )  # normalize wrapping so a line break cannot hide the phrase
        assert (
            "-028 / -029 handoff" in text
        ), f"{relative} no longer anticipates the -028 handoff"
        # the consumption is anonymous: no import of, and no attribute access into, tos.stm
        assert "import tos.stm" not in raw
        assert "tos.stm." not in raw
    predicates = " ".join(
        (_TOS_SRC / "sir" / "predicates.py").read_text(encoding="utf-8").split()
    )
    assert "injected opaque coordinates" in predicates


def test_sir_retains_the_incident_authority_stm_never_takes() -> None:
    """(§17 line 400 / §3.5) Incident materiality, generation and closure stay ADR-002-027-owned."""
    import tos.sir

    for sir_owned in (
        "IncidentLifecycleState",
        "ActiveSafetyIncidentSet",
        "IncidentClosureDecision",
    ):
        assert hasattr(tos.sir, sir_owned)
        assert not hasattr(
            s, sir_owned
        ), f"tos.stm re-authors the sir-owned {sir_owned}"
    # stm's §17 production is a *prohibition-bearing signal*, not an incident verdict
    assert "publishes_no_incident" in s.NEGATIVE_POLARITY_FIELDS


# --- naming: the firewall exclusion lists ----------------------------------


def test_firewall_exclusion_lists_still_name_this_package() -> None:
    """(§0.4a weak soft load-bearing) The four firewall exclusion comments still enumerate ``tos.stm``.

    The package name is fixed only by four *comment* references. They are weak load-bearing — a
    different name would orphan no functional reference — but the citation is an existence claim, so it
    is locked like every other.
    """
    for relative in (
        "wdr/__init__.py",
        "rlp/__init__.py",
        "cur/__init__.py",
        "sir/__init__.py",
    ):
        text = (_TOS_SRC / relative).read_text(encoding="utf-8")
        assert "tos.stm" in text, (
            f"{relative} no longer enumerates ``tos.stm`` — the design #30 §0.4a naming citation "
            "has drifted"
        )


# --- sci: named, never cited ----------------------------------------------


#: Symbols both stm and sci simply **re-export from** ``tos.canonical`` — one shared definition, one
#: proposition, no collision at all.
_SHARED_CANONICAL_REEXPORTS = frozenset(
    {
        "ArtifactIntegrityError",
        "ArtifactStatus",
        "CanonicalDecimal",
        "IndependentIdArtifact",
        "RecordPairKind",
        "classify_record_pair",
    }
)

#: The one genuine same-name / different-proposition collision **discovered during implementation**
#: (design #30 §0.5 — the seal list is representative, not exhaustive, which is exactly why this
#: property re-checks mechanically). Each entry documents the two propositions.
_SCI_NAME_COLLISION_SEAL: dict[str, str] = {
    "PARTITION_FAILURE_MODES": (
        "stm: the ADR-002-028 §21 line 451-462 twelve-row monitoring partition / backpressure matrix "
        "(telemetry loss, collector unavailability, queue overflow, delivery unproven, ...). "
        "sci: ADR-002-029's own partition / failure enumeration for software-release admission. "
        "Same transcription-anchor name, different ADR, different rows, different proposition; "
        "neither package imports the other (sibling edge 0)."
    ),
}


def test_sci_is_an_injected_coordinate_with_zero_code_citation() -> None:
    """(§0.4f) ADR-002-029 landed after authoring; the contract keeps it injected — 0 code citation.

    The ADR §8 line 253 release-lineage group is an opaque injected coordinate. stm neither imports
    ``tos.sci`` nor re-judges its content.
    """
    assert not any(
        path.read_text(encoding="utf-8").count("tos.sci") for path in _stm_sources()
    )


def test_the_stm_sci_name_collisions_are_exactly_the_sealed_ones() -> None:
    """(§0.5, discovered during implementation) Every stm/sci name overlap is classified, both ways.

    ``tos.sci`` landed after the contract was authored, so the contract's §0.5 collision sweep could not
    include it. This property performs that sweep mechanically: the only permitted overlaps are the
    shared ``tos.canonical`` re-exports (one definition, one proposition) and the explicitly sealed
    same-name / different-proposition entries below. Anything else fails, so a future collision cannot
    slip in unrecorded.
    """
    import tos.sci

    from .test_stm_anchor_resolution import _authored_names

    #: Submodule attributes and the ``from __future__`` binding are package *plumbing*, identical in
    #: every tos package; they are not a proposition and are excluded from both sides.
    plumbing = frozenset(
        {"annotations", "predicates", "records", "state", "vocabulary", "_base"}
    )
    sci_names = {
        name
        for name in vars(tos.sci)
        if not name.startswith("_") and name not in plumbing
    }
    # the stm side is the **authorship** sweep, not ``__all__``: a collision re-authored internally and
    # never exported would otherwise pass unrecorded (the #27 FD MAJOR-1 lesson).
    overlaps = sci_names & (_authored_names() - plumbing)
    unclassified = sorted(
        overlaps - _SHARED_CANONICAL_REEXPORTS - set(_SCI_NAME_COLLISION_SEAL)
    )
    assert unclassified == [], (
        f"unclassified stm/sci public-name overlap: {unclassified} — each must be either a shared "
        "tos.canonical re-export or an explicitly sealed same-name / different-proposition entry"
    )
    for name, reason in _SCI_NAME_COLLISION_SEAL.items():
        assert name in overlaps, f"{name} is sealed but is no longer a real collision"
        assert len(reason) > 120, f"{name} needs a substantive documented reason"


def test_the_sealed_collision_really_carries_two_different_propositions() -> None:
    """(§0.5) ``PARTITION_FAILURE_MODES`` names two different matrices in two different ADRs."""
    import tos.sci

    assert s.PARTITION_FAILURE_MODES != tos.sci.PARTITION_FAILURE_MODES
    assert len(s.PARTITION_FAILURE_MODES) == 12  # ADR-002-028 §21 line 451-462
    assert "TELEMETRY_SOURCE_OR_CONTINUITY_LOST" in s.PARTITION_FAILURE_MODES
    assert "TELEMETRY_SOURCE_OR_CONTINUITY_LOST" not in tos.sci.PARTITION_FAILURE_MODES


# --- forward, not backward -------------------------------------------------


def test_the_seam_is_forward_only_no_value_is_wired() -> None:
    """(§3.6) stm imports none of the four consumers, and none of them references a ``tos.stm`` type."""
    for sibling in ("cur", "spg", "rlp", "sir"):
        assert not hasattr(s, sibling)
    stm_sources = " ".join(path.read_text(encoding="utf-8") for path in _stm_sources())
    for forbidden in (
        "import tos.cur",
        "import tos.spg",
        "import tos.rlp",
        "import tos.sir",
    ):
        assert forbidden not in stm_sources
