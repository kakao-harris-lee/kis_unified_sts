"""Long/short compose end-to-end symmetry (TOS Phase 5 W5 plan §2 decision 8, compose half;
lane f4). Hermetic — two independent, fully-composed runtimes (real sqlite, real custody files),
one per mirrored side, each driven through the SAME two-pass approval-file pattern
``test_send_seal.py``/``test_compose_root.py`` already establish.

Drives the identical ``close < lower_band`` crossing event through two separately-composed
runtimes — one with :func:`~._fixtures.construction_config` (``NEW_LONG``/``BUY``), one with
:func:`~._symmetry_fixtures.mirrored_construction_config` (``NEW_SHORT``/``SELL``) — and asserts
the 19-step commitment-flow verdict sequence and the durable evidence-kind sequence are IDENTICAL
between the two runs, while the ``SendSeal``'s ``outbound_side`` and ``seal_digest`` are the one
place they legitimately differ.

Each side needs its OWN ``config_dir``/``data_dir``/``custody_root`` (a second
``compose_paper_runtime`` call into an already-composed data/custody directory would collide with
the first run's sqlite/ledger state) — the shared ``conftest.py`` fixtures are parametrized only
by ``tmp_path``, so :func:`_fresh_compose_dirs` calls their underlying (undecorated) functions
directly against two independent subdirectories of the test's own ``tmp_path``, rather than
re-deriving conftest's config-writing logic a second time.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest
from tos_runtime.calendar.ports import FixedWallClockReference
from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.compose.root import compose_paper_runtime

from . import _fixtures as fx
from . import _symmetry_fixtures as sfx
from .conftest import config_dir as _config_dir_fixture
from .conftest import custody_root as _custody_root_fixture
from .conftest import data_dir as _data_dir_fixture
from .conftest import write_approval_file
from .test_compose_root import _action_flow_inputs, _aggregate_inputs, _reach_trusted

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


def _fresh_compose_dirs(root: Path) -> tuple[Path, Path, Path]:
    """Build one independent ``(config_dir, data_dir, custody_root)`` triple under ``root``.

    ``conftest.py``'s ``config_dir``/``data_dir``/``custody_root`` fixtures are each
    parametrized only by ``tmp_path`` (verified by reading their signatures) — pytest refuses a
    fixture function called directly, but the plain function each decorator wraps is reachable
    via ``__wrapped__``, so this calls exactly the same config-writing logic every other compose
    e2e test uses, just twice, against two independent roots.
    """
    root.mkdir(parents=True, exist_ok=True)
    config_dir = _config_dir_fixture.__wrapped__(root)
    data_dir = _data_dir_fixture.__wrapped__(root)
    custody_root = _custody_root_fixture.__wrapped__(root)
    return config_dir, data_dir, custody_root


def _compose_long(root: Path):
    config_dir, data_dir, custody_root = _fresh_compose_dirs(root)
    fx.write_band_strategy_file(config_dir)
    runtime = compose_paper_runtime(
        config_dir,
        data_dir,
        custody_root,
        "non-live-test",
        construction=fx.construction_config(),
        aggregate_risk_inputs_provider=_aggregate_inputs,
        action_flow_inputs_provider=_action_flow_inputs,
        transport_kind=TransportKind.SYNTHETIC,
        wall_clock=FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS),
    )
    return runtime, custody_root


def _compose_short(root: Path):
    config_dir, data_dir, custody_root = _fresh_compose_dirs(root)
    sfx.write_mirrored_strategy_file(config_dir)
    runtime = compose_paper_runtime(
        config_dir,
        data_dir,
        custody_root,
        "non-live-test",
        construction=sfx.mirrored_construction_config(),
        aggregate_risk_inputs_provider=_aggregate_inputs,
        action_flow_inputs_provider=_action_flow_inputs,
        transport_kind=TransportKind.SYNTHETIC,
        wall_clock=FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS),
    )
    return runtime, custody_root


def _durable_rows_in_order(runtime) -> list[tuple[str, dict]]:
    """Every durable evidence row in append order — mirrors
    ``test_send_seal.py``'s own ``_durable_rows_in_order`` exactly (kept as a second, tiny
    definition rather than an import: importing a sibling test module's private helper into a
    THIRD file starts a chain this suite does not otherwise have)."""
    rows = runtime.evidence_store.connection.execute(
        "SELECT kind, payload_json FROM entries ORDER BY seq ASC"
    ).fetchall()
    return [(kind, json.loads(payload_json)["payload"]) for kind, payload_json in rows]


@dataclass(frozen=True)
class SymmetryObservation:
    """What one mirrored side's run produced, reduced to exactly what decision 8 compares."""

    verdict_sequence: tuple[tuple[str, str], ...]
    evidence_kind_sequence: tuple[str, ...]
    outbound_side: str
    seal_digest: str


def _drive_to_send_boundary(runtime, custody_root: Path) -> SymmetryObservation:
    """Run once, write the matching approval file, run again — the same two-pass pattern
    ``test_compose_root.py::test_engine_steps_admit_for_real_and_reach_the_transport`` and
    ``test_send_seal.py::_run_to_send_boundary`` both use — then reduce the result to a
    :class:`SymmetryObservation`."""
    event = fx.crossing_event()
    results = runtime.run_once((event,))
    proposal_digest = results[0].pipeline.proposal.canonical_digest
    construction = runtime.construction_stage.construction
    assert construction is not None and construction.intent is not None
    write_approval_file(
        custody_root,
        proposal_digest=proposal_digest,
        environment_label="non-live-test",
        approved_intent_envelope_digest=construction.intent.canonical_digest,
    )

    results2 = runtime.run_once((event,))
    flow = results2[0].flow
    assert flow is not None

    rows = _durable_rows_in_order(runtime)
    sealed_payload = next(payload for kind, payload in rows if kind == "SEND_SEALED")
    seal = sealed_payload["send_seal"]

    return SymmetryObservation(
        verdict_sequence=tuple((v.step.value, v.outcome.value) for v in flow.verdicts),
        evidence_kind_sequence=tuple(kind for kind, _payload in rows),
        outbound_side=seal["outbound_side"],
        seal_digest=seal["seal_digest"],
    )


def assert_side_symmetric(
    long_obs: SymmetryObservation,
    short_obs: SymmetryObservation,
    *,
    long_side: str = "BUY",
    short_side: str = "SELL",
) -> None:
    """The decision-8 mutation pin, as a standalone, independently-testable assertion.

    Every structural field must match exactly; the seal is the one place a real, legitimate
    difference is REQUIRED (a design that produced the same seal digest on both sides would mean
    side was never actually bound into what gets signed)."""
    assert long_obs.verdict_sequence == short_obs.verdict_sequence, (
        "the 19-step commitment-flow verdict sequence diverged between mirrored sides:\n"
        f"long:  {long_obs.verdict_sequence}\nshort: {short_obs.verdict_sequence}"
    )
    assert long_obs.evidence_kind_sequence == short_obs.evidence_kind_sequence, (
        "the durable evidence-kind sequence diverged between mirrored sides:\n"
        f"long:  {long_obs.evidence_kind_sequence}\nshort: {short_obs.evidence_kind_sequence}"
    )
    assert long_obs.outbound_side == long_side, (
        f"expected the long run's SendSeal.outbound_side to be {long_side!r}, "
        f"got {long_obs.outbound_side!r}"
    )
    assert short_obs.outbound_side == short_side, (
        f"expected the short run's SendSeal.outbound_side to be {short_side!r}, "
        f"got {short_obs.outbound_side!r}"
    )
    assert long_obs.seal_digest != short_obs.seal_digest, (
        "the two mirrored sides produced the SAME seal digest — side is supposed to be bound "
        "into what the gateway seals; an equal digest here means it silently isn't"
    )


class TestComposeE2ELongShortSymmetry:
    def test_mirrored_sides_admit_through_the_identical_verdict_and_evidence_sequence(
        self, tmp_path: Path
    ) -> None:
        long_runtime, long_custody = _compose_long(tmp_path / "long")
        _reach_trusted(long_runtime)
        long_obs = _drive_to_send_boundary(long_runtime, long_custody)
        long_runtime.rcl_log.close()
        long_runtime.evidence_store.close()

        short_runtime, short_custody = _compose_short(tmp_path / "short")
        _reach_trusted(short_runtime)
        short_obs = _drive_to_send_boundary(short_runtime, short_custody)
        short_runtime.rcl_log.close()
        short_runtime.evidence_store.close()

        # Sanity: both sides genuinely reached the transport — a run that halted early with an
        # empty verdict/evidence sequence on BOTH sides would make the equality assertions below
        # pass vacuously. The flow records a verdict only for each step it actually reaches
        # (REGISTRY_DISPATCH through the Transmission Capability that hands off to the
        # transport) — not all 19 of :data:`~tos.engine.vocabulary.COMMITMENT_FLOW_ORDER`, since
        # later steps (e.g. egress result consumption) are driven by a SUBSEQUENT tick, not this
        # one — so this pins "genuinely reached the send boundary", not a fixed step count.
        assert len(long_obs.verdict_sequence) >= 10
        assert all(outcome == "ADMIT" for _step, outcome in long_obs.verdict_sequence)
        assert "SEND_SEALED" in long_obs.evidence_kind_sequence
        assert "SEND_SEALED" in short_obs.evidence_kind_sequence

        assert_side_symmetric(long_obs, short_obs)


def test_assert_side_symmetric_fires_on_a_fabricated_asymmetric_pair() -> None:
    """Mutation-detector self-test (anti-vacuity — the same idiom
    ``tests/engine/test_no_direct_latch_clear.py``/``tests/operator/test_no_write_port.py`` use
    for their own regexes, applied here to a structural assertion instead): prove
    :func:`assert_side_symmetric` actually fires when handed a genuinely asymmetric pair, rather
    than trusting the real long/short pair above passing as proof the check does anything.
    """
    base_sequence = (("REGISTRY_DISPATCH", "ADMIT"), ("VENUE_CONSTRUCTION", "ADMIT"))
    base_evidence = ("SEND_SEALED", "SEND_STARTED")

    symmetric_long = SymmetryObservation(
        verdict_sequence=base_sequence,
        evidence_kind_sequence=base_evidence,
        outbound_side="BUY",
        seal_digest="digest-long",
    )
    symmetric_short = SymmetryObservation(
        verdict_sequence=base_sequence,
        evidence_kind_sequence=base_evidence,
        outbound_side="SELL",
        seal_digest="digest-short",
    )
    # the genuinely symmetric pair must NOT raise.
    assert_side_symmetric(symmetric_long, symmetric_short)

    # (a) a verdict sequence that silently diverged between sides.
    asymmetric_verdicts = SymmetryObservation(
        verdict_sequence=(
            ("REGISTRY_DISPATCH", "ADMIT"),
            ("VENUE_CONSTRUCTION", "DENY"),
        ),
        evidence_kind_sequence=base_evidence,
        outbound_side="SELL",
        seal_digest="digest-short",
    )
    with pytest.raises(AssertionError, match="verdict sequence diverged"):
        assert_side_symmetric(symmetric_long, asymmetric_verdicts)

    # (b) an evidence-kind sequence that silently diverged between sides.
    asymmetric_evidence = SymmetryObservation(
        verdict_sequence=base_sequence,
        evidence_kind_sequence=("SEND_SEALED",),
        outbound_side="SELL",
        seal_digest="digest-short",
    )
    with pytest.raises(AssertionError, match="evidence-kind sequence diverged"):
        assert_side_symmetric(symmetric_long, asymmetric_evidence)

    # (c) the M6-shaped mutation: a "short" observation whose outbound_side is still "BUY" (the
    # side literal never actually flipped, as an `if side == "BUY"` branch that always takes the
    # BUY arm would produce).
    still_buy = SymmetryObservation(
        verdict_sequence=base_sequence,
        evidence_kind_sequence=base_evidence,
        outbound_side="BUY",
        seal_digest="digest-short",
    )
    with pytest.raises(AssertionError, match="outbound_side"):
        assert_side_symmetric(symmetric_long, still_buy)

    # (d) the digest-blindness mutation: both sides producing the identical seal digest.
    same_digest = SymmetryObservation(
        verdict_sequence=base_sequence,
        evidence_kind_sequence=base_evidence,
        outbound_side="SELL",
        seal_digest="digest-long",  # identical to symmetric_long's
    )
    with pytest.raises(AssertionError, match="SAME seal digest"):
        assert_side_symmetric(symmetric_long, same_digest)
