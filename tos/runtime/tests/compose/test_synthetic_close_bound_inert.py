"""What a SYNTHETIC boot actually does after a filled entry — today's outcome, pinned (#1011).

**This file exists because the fix for #1011 does not fix #1011** (review-1015 H1, measured).
The durable CLOSE bound (`tos_runtime.riskstate.close_bound`) assumes a filled entry reaches
``POSITION_CONSUMED``. On a synthetic boot it never does: the only broker witness this compose
root has is :class:`~tos_runtime.recon.witness_synthetic.SyntheticLedgerWitness`, which is
derived from the evidence store it would be corroborating, so
:mod:`tos_runtime.posttrade.release_consumer` holds the release with
``WITNESS_NOT_INDEPENDENT`` (#1011 §3.5) and the reservation stays
``COMMITTED_UNBOUND`` forever. That is the W2-R "정직 상태" design, asserted by
``test_compose_root.py::test_full_fill_hand_off_never_releases_rcl_capacity_end_to_end``.

So the scope seals one step EARLIER than review-1007 M2 assumed: step 8 denies a CLOSE (it
admits only over exactly one ``POSITION_CONSUMED`` row) and denies every later OPEN (the
``COMMITTED_UNBOUND`` row is outstanding). The new bound is correct and fail-closed, and
simply never runs.

The test below pins that outcome rather than the wish. **If synthetic fills ever become
corroborated — the real fix for #1011 — this test fails loudly**, at the exact assertions that
name the current behaviour, which is the point: the claim cannot drift again without someone
editing it on purpose.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest
from tos.rcl import CapacityState
from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.compose.root import _close_authority_for
from tos_runtime.rcl.projection import (
    SqliteReservationProjectionReader,
    outstanding_reservations,
)
from tos_runtime.risk.ledger_stages import verdict_for_scope
from tos_runtime.riskstate.close_bound import (
    CloseAuthoritySource,
    CloseBoundRefusal,
    DurableEntryCloseBoundReader,
)

from . import _fixtures as fx
from .conftest import write_approval_file
from .test_compose_root import _compose, _reach_trusted

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


def _hand_off_a_filled_entry(runtime, custody_root: Path):
    """Discover, approve and hand off ONE OPEN, then let the idle passes consume its fill."""
    event = fx.crossing_event()
    discovery = runtime.run_once((event,))[0]
    assert discovery.pipeline is not None and discovery.pipeline.proposal is not None
    construction = runtime.construction_stage.construction
    assert construction is not None and construction.intent is not None
    write_approval_file(
        custody_root,
        proposal_digest=discovery.pipeline.proposal.canonical_digest,
        environment_label="non-live-test",
        approved_intent_envelope_digest=construction.intent.canonical_digest,
    )
    result = runtime.run_once((event,))[0]
    assert result.flow is not None and result.flow.handed_off is True
    # Idle passes: the release consumer runs on each, and keeps holding.
    for _ in range(3):
        runtime.run_once(())
    return result


def test_an_uncorroborated_synthetic_fill_leaves_the_close_bound_inert_and_the_scope_sealed(
    config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
) -> None:
    """Approved OPEN -> hand-off -> idle: entry stays COMMITTED_UNBOUND, every CLOSE refuses.

    Concrete input: a real ``compose_paper_runtime`` on ``TransportKind.SYNTHETIC``, one
    approved OPEN handed off, three idle passes. Concrete result today:

    * the scope's ONE reservation is ``COMMITTED_UNBOUND`` (not ``POSITION_CONSUMED``);
    * the release is held with ``WITNESS_NOT_INDEPENDENT``;
    * :meth:`DurableEntryCloseBoundReader.read` refuses with
      ``ENTRY_NOT_SOLE_CONSUMED_POSITION``, so step 6 can only be UNKNOWN;
    * step 8 DENIES both a CLOSE and a further OPEN over that row — the seal #1011 describes.

    Every assertion here is a statement about the CURRENT corroboration rule, not about what
    the close bound should eventually do. Making synthetic fills corroborated flips all four.
    """
    runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
    try:
        _reach_trusted(runtime)
        _hand_off_a_filled_entry(runtime, custody_root)

        rows = [
            (reservation_id, state)
            for reservation_id, state, _seq, _scope in runtime.rcl_log.reservation_rows()
        ]
        assert len(rows) == 1, rows
        assert rows[0][1] is CapacityState.COMMITTED_UNBOUND, rows

        held = runtime.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = 'CAPACITY_RELEASE_HELD'"
        ).fetchall()
        assert len(held) == 1, held
        payload = json.loads(held[0][0])["payload"]
        assert (payload["reason"], payload["detail"]) == (
            "WITNESS_NOT_INDEPENDENT",
            "WITNESS_NOT_INDEPENDENT",
        )

        # The bound the composition root wires on this transport, read against the very
        # stores that boot owns. It cannot find an entry, so it grants nothing.
        instrument_key = runtime.context_resolver.instrument_key
        bound = DurableEntryCloseBoundReader(
            rcl_log=runtime.rcl_log,
            evidence_store=runtime.evidence_store,
            projection=SqliteReservationProjectionReader(runtime.rcl_log),
            account=instrument_key.account,
            instrument=instrument_key.instrument,
        ).read()
        assert bound.proven is False
        assert bound.refusal == CloseBoundRefusal.ENTRY_NOT_SOLE_CONSUMED_POSITION.value
        assert bound.entry_quantity is None and bound.prior_closed is None

        # Step 8's own table on the real rows: the scope admits neither side.
        scope_rows = SqliteReservationProjectionReader(
            runtime.rcl_log
        ).scope_reservations(instrument_key)
        assert len(outstanding_reservations(scope_rows)) == 1
        assert verdict_for_scope("CLOSE", scope_rows).outcome.value == "DENY"
        assert verdict_for_scope("OPEN", scope_rows).outcome.value == "DENY"
    finally:
        runtime.rcl_log.close()
        runtime.evidence_store.close()


@pytest.mark.parametrize(
    ("transport_kind", "expected"),
    [
        (TransportKind.SYNTHETIC, CloseAuthoritySource.DURABLE_EVIDENCE),
        (TransportKind.KIS_MOCK, CloseAuthoritySource.BROKER_HELD_PROOF),
    ],
)
def test_close_authority_is_selected_by_transport_kind(
    transport_kind: TransportKind, expected: CloseAuthoritySource
) -> None:
    """The ONE dispatch #1011 adds, pinned per member — no tree name reaches this decision."""
    assert _close_authority_for(transport_kind) == expected


def test_close_authority_defaults_to_the_broker_path_for_anything_unrecognized() -> (
    None
):
    """An unrecognized transport takes the broker path, which is the fail-closed side.

    The broker path needs a held-position proof reader, and only a ``kis-mock`` posttrade boot
    ever builds one (``compose/root.py``'s ``held_position_bridge``), so a transport that is
    neither member gets ``PROVIDER_NOT_CONFIGURED`` and UNKNOWN — never the durable-evidence
    authority, which would grant on evidence that transport's broker never produced.

    The second assertion is the ratchet: ``TransportKind`` has exactly two members today, so a
    third one added without revisiting :func:`_close_authority_for` fails here and has to be
    classified deliberately.
    """
    unrecognized: TransportKind = cast(TransportKind, "not-a-transport")
    assert _close_authority_for(unrecognized) is CloseAuthoritySource.BROKER_HELD_PROOF
    assert sorted(member.value for member in TransportKind) == ["kis-mock", "synthetic"]
