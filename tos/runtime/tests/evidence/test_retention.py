"""``tos_runtime.evidence.retention`` tests — judgement-only, never deletes."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from tos.canonical import ArtifactIntegrityError
from tos_runtime.evidence.retention import RetentionPolicy, tombstone
from tos_runtime.evidence.store import SqliteEvidenceStore

_ONE_DAY_NS = 24 * 60 * 60 * 1_000_000_000

_EXAMPLE_CONFIG = (
    Path(__file__).resolve().parents[2] / "config" / "evidence_retention.example.yaml"
)


def test_load_refuses_when_minimum_days_by_class_key_is_missing(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("some_other_key: 1\n")
    with pytest.raises(ArtifactIntegrityError):
        RetentionPolicy.load(bad)


def test_load_refuses_when_minimum_days_by_class_is_not_a_mapping(
    tmp_path: Path,
) -> None:
    bad = tmp_path / "bad2.yaml"
    bad.write_text("minimum_days_by_class: 5\n")
    with pytest.raises(ArtifactIntegrityError):
        RetentionPolicy.load(bad)


def test_load_accepts_null_values_as_named_tbd(tmp_path: Path) -> None:
    ok = tmp_path / "ok.yaml"
    ok.write_text("minimum_days_by_class:\n  SOME_CLASS: null\n")
    policy = RetentionPolicy.load(ok)
    assert policy.minimum_days_by_class == {"SOME_CLASS": None}


def test_example_config_loads_and_is_all_named_tbd() -> None:
    policy = RetentionPolicy.load(_EXAMPLE_CONFIG)
    assert all(value is None for value in policy.minimum_days_by_class.values())


def test_evaluate_never_deletes_rows(store: SqliteEvidenceStore) -> None:
    store.append({"a": 1}, kind="TEST", record_class="C", segment_id=None)
    policy = RetentionPolicy({"C": 1})
    row_count_before = store.connection.execute(
        "SELECT COUNT(*) FROM entries"
    ).fetchone()[0]
    policy.evaluate(
        store,
        now=_ONE_DAY_NS * 100,
        holds={0: False},
        open_or_live={0: False},
    )
    row_count_after = store.connection.execute(
        "SELECT COUNT(*) FROM entries"
    ).fetchone()[0]
    assert row_count_before == row_count_after


def test_evaluate_with_null_minimum_is_never_deletable(
    store: SqliteEvidenceStore,
) -> None:
    store.append({"a": 1}, kind="TEST", record_class="C")
    policy = RetentionPolicy({"C": None})
    verdicts = policy.evaluate(
        store, now=_ONE_DAY_NS * 1000, holds={0: False}, open_or_live={0: False}
    )
    assert verdicts[0].deletable is False


def test_evaluate_with_mixed_null_and_valued_minimums_only_valued_class_is_deletable(
    store: SqliteEvidenceStore,
) -> None:
    """A null-valued class stays refused even inside a policy that ALSO holds
    a real per-class minimum for another class — proving the null-filtering
    fix for the kernel's ``Mapping[str, int] | None`` signature does not
    corrupt or drop the valued entries it keeps."""
    store.append({"a": 1}, kind="TEST", record_class="NAMED_TBD_CLASS")
    store.append({"b": 2}, kind="TEST", record_class="VALUED_CLASS")
    policy = RetentionPolicy({"NAMED_TBD_CLASS": None, "VALUED_CLASS": 1})
    verdicts = policy.evaluate(
        store,
        now=_ONE_DAY_NS * 2,
        holds={0: False, 1: False},
        open_or_live={0: False, 1: False},
    )
    verdicts_by_seq = {verdict.seq: verdict for verdict in verdicts}
    assert verdicts_by_seq[0].deletable is False  # NAMED_TBD_CLASS, null minimum
    assert verdicts_by_seq[1].deletable is True  # VALUED_CLASS, aged past minimum


def test_evaluate_with_active_hold_is_never_deletable(
    store: SqliteEvidenceStore,
) -> None:
    store.append({"a": 1}, kind="TEST", record_class="C")
    policy = RetentionPolicy({"C": 1})
    verdicts = policy.evaluate(
        store, now=_ONE_DAY_NS * 10, holds={0: True}, open_or_live={0: False}
    )
    assert verdicts[0].deletable is False


def test_evaluate_with_unknown_hold_state_is_never_deletable(
    store: SqliteEvidenceStore,
) -> None:
    store.append({"a": 1}, kind="TEST", record_class="C")
    policy = RetentionPolicy({"C": 1})
    verdicts = policy.evaluate(
        store, now=_ONE_DAY_NS * 10, holds={}, open_or_live={0: False}
    )
    assert verdicts[0].deletable is False


def test_evaluate_with_sufficient_age_and_no_holds_is_deletable(
    store: SqliteEvidenceStore,
) -> None:
    store.append({"a": 1}, kind="TEST", record_class="C")
    policy = RetentionPolicy({"C": 1})
    verdicts = policy.evaluate(
        store, now=_ONE_DAY_NS * 2, holds={0: False}, open_or_live={0: False}
    )
    assert verdicts[0].deletable is True


def test_tombstone_appends_a_record_and_never_deletes(
    store: SqliteEvidenceStore,
) -> None:
    store.append({"a": 1}, kind="TEST", record_class="C")
    policy = RetentionPolicy({"C": 1})
    verdicts = policy.evaluate(
        store, now=_ONE_DAY_NS * 2, holds={0: False}, open_or_live={0: False}
    )
    row_count_before = store.connection.execute(
        "SELECT COUNT(*) FROM entries"
    ).fetchone()[0]
    receipt = tombstone(store, verdicts[0], dual_control_ref="ops-approved-123")
    row_count_after = store.connection.execute(
        "SELECT COUNT(*) FROM entries"
    ).fetchone()[0]
    assert row_count_after == row_count_before + 1
    assert receipt.seq == 1


def test_tombstone_refuses_a_non_deletable_verdict(store: SqliteEvidenceStore) -> None:
    store.append({"a": 1}, kind="TEST", record_class="C")
    policy = RetentionPolicy({"C": None})
    verdicts = policy.evaluate(
        store, now=_ONE_DAY_NS * 2, holds={0: False}, open_or_live={0: False}
    )
    with pytest.raises(ValueError):
        tombstone(store, verdicts[0], dual_control_ref="ops-approved-123")


def test_tombstone_requires_non_blank_dual_control_ref(
    store: SqliteEvidenceStore,
) -> None:
    store.append({"a": 1}, kind="TEST", record_class="C")
    policy = RetentionPolicy({"C": 1})
    verdicts = policy.evaluate(
        store, now=_ONE_DAY_NS * 2, holds={0: False}, open_or_live={0: False}
    )
    with pytest.raises(ValidationError, match="dual_control_ref"):
        tombstone(store, verdicts[0], dual_control_ref="   ")
