"""The #1011 §3.5 reason split — ``WITNESS_NOT_INDEPENDENT`` is not a conflict.

**What was wrong (#1011 F6, measured).** A store-derived witness cannot corroborate anything,
so :class:`~tos_runtime.recon.service.ReconciliationService` reports
:data:`~tos_runtime.recon.service.WITNESS_NOT_INDEPENDENT_REASON` and the release holds. That
hold used to be recorded with the hold reason ``NOT_CORROBORATED`` — the ONE reason the
POST_TRADE currentness dimension reads as "gate 3's reconciliation found a genuine conflict"
(:func:`~tos_runtime.posttrade.release_currentness.latest_release_is_conflict_free`). So every
synthetic leaf, from its first filled entry onwards, reported a reconciliation conflict it had
never had, and the dimension stayed ``False`` for the rest of that scope's life.

**What this file pins.** The split itself, and the thing it is for: the same scope, the same
held release, reported as NOT a conflict. The release DECISION is unchanged — both reasons are
holds, and the tests below assert that where it is observable.

Hermetic: ``tmp_path`` sqlite only, no network, no ambient env (D1.4).
"""

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
    """A report carrying ``reason`` and nothing else that matters here.

    Every other field is the "nothing corroborated" shape the real service produces alongside
    these reasons: no field confidences, no classifications, neither permit granted.
    """
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


# ===========================================================================
# the predicate and the two mappings onto it
# ===========================================================================


def test_the_predicate_fires_only_on_the_independence_reason() -> None:
    """``witness_independence_collapsed`` on the three reports gate 3 can produce."""
    assert witness_independence_collapsed(_report(WITNESS_NOT_INDEPENDENT_REASON)) is (
        True
    )
    assert witness_independence_collapsed(_report("no observations in scope")) is False
    assert witness_independence_collapsed(_report(None)) is False
    # `reconcile` itself raised — that is RECONCILIATION_UNAVAILABLE, a different state.
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
    """The release consumer's own mapping — one reason per report shape.

    Concrete input/result: a report reading ``WITNESS_NOT_INDEPENDENT`` now yields the hold
    reason of the same name; a report that genuinely found nothing to corroborate still
    yields ``NOT_CORROBORATED``.
    """
    assert uncorroborated_hold_reason(_report(reason)) is expected


def test_the_two_hold_reasons_are_distinct_strings() -> None:
    """The split is only worth anything if the two spell differently in the evidence row."""
    assert (
        ReleaseHoldReason.WITNESS_NOT_INDEPENDENT.value
        != ReleaseHoldReason.NOT_CORROBORATED.value
    )
    # And the new one is spelled EXACTLY as the report's own reason, so the evidence row's
    # `reason` and `detail` agree rather than translating between two vocabularies.
    assert (
        ReleaseHoldReason.WITNESS_NOT_INDEPENDENT.value
        == WITNESS_NOT_INDEPENDENT_REASON
    )


# ===========================================================================
# the POST_TRADE currentness dimension — what the split is FOR
# ===========================================================================


def test_a_witness_not_independent_hold_is_not_a_post_trade_conflict(
    evidence_store: SqliteEvidenceStore,
) -> None:
    """#1011 F6, closed: the old synthetic leaf's hold no longer reads as a conflict.

    Concrete input: this scope's latest post-trade row is a ``CAPACITY_RELEASE_HELD`` whose
    reason is ``WITNESS_NOT_INDEPENDENT``. Before the split that row said
    ``NOT_CORROBORATED`` and this read ``False`` — permanently, for every synthetic tree after
    its first filled entry.
    """
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
    """The other half: the split narrowed the conflict reason, it did not remove it.

    Concrete input: the same scope, the same evidence kind, reason ``NOT_CORROBORATED`` — an
    orphan broker order or a non-``MATCHED`` classification. Still ``False``.
    """
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
    """A real conflict followed by an independence hold reads as the independence hold.

    This is the ordering the scan already had; it is pinned here because the split adds a
    second reason that can sit on either side of a conflict, and "newest wins" is what makes
    the dimension recover rather than latch.
    """
    _record_hold(evidence_store, reason=ReleaseHoldReason.NOT_CORROBORATED.value)
    _record_hold(evidence_store, reason=ReleaseHoldReason.WITNESS_NOT_INDEPENDENT.value)

    assert (
        latest_release_is_conflict_free(
            evidence_store, account=_ACCOUNT, instrument=_INSTRUMENT
        )
        is True
    )

    # ...and an actual release after it is conflict-free too (the pre-existing INTENT branch).
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
