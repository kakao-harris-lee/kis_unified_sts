"""The #1011 §3.5 reason split — ``WITNESS_NOT_INDEPENDENT`` is not a conflict."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.release_consumer import (
    CAPACITY_RELEASE_HELD_KIND,
    CAPACITY_RELEASE_INTENT_KIND,
    ReleaseHoldReason,
    uncorroborated_hold_reason,
)
from tos_runtime.posttrade.release_currentness import latest_release_is_conflict_free
from tos_runtime.rcl.reservation_identity import scope_reservation_id
from tos_runtime.recon.service import (
    WITNESS_NOT_INDEPENDENT_REASON,
    ReconciliationReport,
    witness_independence_collapsed,
)

from ..engine.conftest import FixedKeyProvider

_ACCOUNT = "acct-wni"
_INSTRUMENT = "101W12"


@pytest.fixture
def evidence_store(tmp_path: Path) -> Iterator[SqliteEvidenceStore]:
    instance = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=FixedKeyProvider()
    )
    yield instance
    instance.close()


def _report(reason: str | None) -> ReconciliationReport:
    """A report carrying ``reason`` and nothing else that matters here."""
    return ReconciliationReport(
        field_confidences=(),
        classifications=(),
        permits_capacity_release=False,
        permits_rearm=False,
        reason=reason,
        observed_positions=(),
        observed_positions_complete=False,
    )


def _record_hold(store: SqliteEvidenceStore, *, reason: str) -> None:
    store.append(
        {
            "attempt_id": "attempt-wni",
            "reservation_id": scope_reservation_id(_ACCOUNT, _INSTRUMENT),
            "reason": reason,
            "detail": None,
        },
        kind=CAPACITY_RELEASE_HELD_KIND,
        record_class=CAPACITY_RELEASE_HELD_KIND,
    )


def test_the_predicate_fires_only_on_the_independence_reason() -> None:
    """``witness_independence_collapsed`` on the three reports gate 3 can produce."""
    assert witness_independence_collapsed(_report(WITNESS_NOT_INDEPENDENT_REASON)) is (
        True
    )
    assert witness_independence_collapsed(_report("no observations in scope")) is False
    assert witness_independence_collapsed(_report(None)) is False
    assert witness_independence_collapsed(None) is False


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        (WITNESS_NOT_INDEPENDENT_REASON, ReleaseHoldReason.WITNESS_NOT_INDEPENDENT),
        ("no observations in scope", ReleaseHoldReason.NOT_CORROBORATED),
        (None, ReleaseHoldReason.NOT_CORROBORATED),
    ],
)
def test_the_release_path_maps_each_report_onto_its_own_hold_reason(
    reason: str | None, expected: ReleaseHoldReason
) -> None:
    """The release consumer's own mapping — one reason per report shape."""
    assert uncorroborated_hold_reason(_report(reason)) is expected


def test_the_two_hold_reasons_are_distinct_strings() -> None:
    """The split is only worth anything if the two spell differently in the evidence row."""
    assert (
        ReleaseHoldReason.WITNESS_NOT_INDEPENDENT.value
        != ReleaseHoldReason.NOT_CORROBORATED.value
    )
    assert (
        ReleaseHoldReason.WITNESS_NOT_INDEPENDENT.value
        == WITNESS_NOT_INDEPENDENT_REASON
    )


def test_a_witness_not_independent_hold_is_not_a_post_trade_conflict(
    evidence_store: SqliteEvidenceStore,
) -> None:
    """#1011 F6, closed: the old synthetic leaf's hold no longer reads as a conflict."""
    _record_hold(evidence_store, reason=ReleaseHoldReason.WITNESS_NOT_INDEPENDENT.value)

    assert (
        latest_release_is_conflict_free(
            evidence_store, account=_ACCOUNT, instrument=_INSTRUMENT
        )
        is True
    )


def test_a_genuine_conflict_still_reads_as_one(
    evidence_store: SqliteEvidenceStore,
) -> None:
    """The other half: the split narrowed the conflict reason, it did not remove it."""
    _record_hold(evidence_store, reason=ReleaseHoldReason.NOT_CORROBORATED.value)

    assert (
        latest_release_is_conflict_free(
            evidence_store, account=_ACCOUNT, instrument=_INSTRUMENT
        )
        is False
    )


def test_the_dimension_reads_the_newest_row_whichever_reason_it_carries(
    evidence_store: SqliteEvidenceStore,
) -> None:
    """A real conflict followed by an independence hold reads as the independence hold."""
    _record_hold(evidence_store, reason=ReleaseHoldReason.NOT_CORROBORATED.value)
    _record_hold(evidence_store, reason=ReleaseHoldReason.WITNESS_NOT_INDEPENDENT.value)

    assert (
        latest_release_is_conflict_free(
            evidence_store, account=_ACCOUNT, instrument=_INSTRUMENT
        )
        is True
    )

    evidence_store.append(
        {
            "attempt_id": "attempt-wni",
            "reservation_id": scope_reservation_id(_ACCOUNT, _INSTRUMENT),
            "destination": "RELEASED",
        },
        kind=CAPACITY_RELEASE_INTENT_KIND,
        record_class=CAPACITY_RELEASE_INTENT_KIND,
    )
    assert (
        latest_release_is_conflict_free(
            evidence_store, account=_ACCOUNT, instrument=_INSTRUMENT
        )
        is True
    )
