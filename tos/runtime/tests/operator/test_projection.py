"""Hermetic tests for :class:`tos_runtime.operator.projection.OperatorProjection` (TOS Phase 5
W4 plan §2 decision 7; JSON schema plan §2.7).
"""

from __future__ import annotations

from typing import Any

import pytest
from tos_runtime.operator.projection import (
    MAX_UNRESOLVED_STM_ALERT_SEQS,
    SCHEMA_VERSION,
    OperatorProjection,
)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_GROUP_KEYS = (
    "runtime",
    "recovery",
    "driver",
    "time",
    "safety_mesh",
    "currentness",
    "rcl",
    "inbox",
    "evidence",
    "release",
    "protective",
    "operations",
)

_TOP_LEVEL_KEYS = frozenset(
    _GROUP_KEYS
    + (
        "schema_version",
        "projection_generation",
        "exported_at_monotonic_ns",
        "non_authorizing",
        "alerts",
        "export",
    )
)


def _all_none_projection(
    *,
    candidate_seqs=lambda: None,
    resolved_seqs=lambda: None,
    export_status=None,
) -> OperatorProjection:
    """A projection where every group reader legitimately returns ``None`` — the "nothing has a
    source yet" baseline (module docstring's OBS-INV-003 discipline)."""
    readers = {f"read_{name}": (lambda: None) for name in _GROUP_KEYS}
    return OperatorProjection(
        read_unresolved_stm_alert_candidate_seqs=candidate_seqs,
        read_resolved_stm_alert_seqs=resolved_seqs,
        read_export_status=export_status,
        **readers,
    )


def _populated_projection() -> OperatorProjection:
    values = {name: {"populated": name} for name in _GROUP_KEYS}
    readers = {f"read_{name}": (lambda v=values[name]: v) for name in _GROUP_KEYS}
    return OperatorProjection(
        read_unresolved_stm_alert_candidate_seqs=lambda: (3, 2, 1),
        read_resolved_stm_alert_seqs=lambda: (2,),
        **readers,
    )


# -- schema shape -------------------------------------------------------------


def test_schema_version_constant_is_1() -> None:
    assert SCHEMA_VERSION == 1


def test_build_emits_exactly_the_pinned_top_level_keys() -> None:
    document = _populated_projection().build()
    assert set(document) == _TOP_LEVEL_KEYS


def test_build_passes_through_each_group_reader_value() -> None:
    document = _populated_projection().build()
    for name in _GROUP_KEYS:
        assert document[name] == {"populated": name}


def test_alerts_group_shape() -> None:
    document = _populated_projection().build()
    assert set(document["alerts"]) == {"unresolved_stm_alert_seqs", "delivery_owner"}
    assert document["alerts"]["delivery_owner"] == (
        "legacy alert-manager (outside tos_runtime)"
    )


def test_export_group_shape() -> None:
    document = _populated_projection().build()
    assert set(document["export"]) == {"failures", "last_error"}


# -- projection_generation / exported_at_monotonic_ns -------------------------


def test_projection_generation_increments_monotonically_per_build() -> None:
    projection = _all_none_projection()
    first = projection.build()
    second = projection.build()
    third = projection.build()
    assert (
        first["projection_generation"]
        < second["projection_generation"]
        < third["projection_generation"]
    )
    assert first["projection_generation"] == 1


def test_exported_at_monotonic_ns_is_a_nonnegative_int() -> None:
    document = _all_none_projection().build()
    value = document["exported_at_monotonic_ns"]
    assert isinstance(value, int)
    assert value >= 0


# -- OBS-INV-002/006: no literal True except the marker (mutation M6) --------


def _assert_no_stray_true(value: Any, path: str, offenders: list[str]) -> None:
    if value is True:
        offenders.append(path)
        return
    if isinstance(value, dict):
        for key, sub in value.items():
            _assert_no_stray_true(sub, f"{path}.{key}", offenders)
        return
    if isinstance(value, (list, tuple)):
        for index, sub in enumerate(value):
            _assert_no_stray_true(sub, f"{path}[{index}]", offenders)


def test_all_none_readers_produce_no_true_literal_except_non_authorizing() -> None:
    """Mutation lens M6 (plan §5): if any group field were ever hardcoded to a literal ``True``
    instead of genuinely sourced, this test goes red."""
    document = _all_none_projection().build()
    assert document["non_authorizing"] is True

    offenders: list[str] = []
    for key, value in document.items():
        if key == "non_authorizing":
            continue
        _assert_no_stray_true(value, key, offenders)
    assert offenders == []


def test_all_none_readers_produce_null_groups() -> None:
    document = _all_none_projection().build()
    for name in _GROUP_KEYS:
        assert document[name] is None
    assert document["alerts"]["unresolved_stm_alert_seqs"] is None


# -- read-callable failure surfacing -----------------------------------------


def test_a_raising_group_reader_yields_none_for_its_own_field_only() -> None:
    def _boom() -> None:
        raise RuntimeError("no source wired yet")

    readers = {f"read_{name}": (lambda: None) for name in _GROUP_KEYS}
    readers["read_driver"] = _boom
    projection = OperatorProjection(
        read_unresolved_stm_alert_candidate_seqs=lambda: (),
        read_resolved_stm_alert_seqs=lambda: (),
        **readers,
    )
    document = projection.build()
    assert document["driver"] is None
    for name in _GROUP_KEYS:
        if name != "driver":
            assert document[name] is None


def test_a_raising_reader_increments_export_failures_and_sets_last_error() -> None:
    def _boom() -> None:
        raise ValueError("boom")

    readers = {f"read_{name}": (lambda: None) for name in _GROUP_KEYS}
    readers["read_evidence"] = _boom
    projection = OperatorProjection(
        read_unresolved_stm_alert_candidate_seqs=lambda: (),
        read_resolved_stm_alert_seqs=lambda: (),
        **readers,
    )
    document = projection.build()
    assert document["export"]["failures"] == 1
    assert "evidence" in document["export"]["last_error"]
    assert "boom" in document["export"]["last_error"]


def test_multiple_raising_readers_are_all_counted() -> None:
    def _boom() -> None:
        raise ValueError("boom")

    readers = {f"read_{name}": (lambda: None) for name in _GROUP_KEYS}
    readers["read_evidence"] = _boom
    readers["read_rcl"] = _boom
    projection = OperatorProjection(
        read_unresolved_stm_alert_candidate_seqs=_boom,
        read_resolved_stm_alert_seqs=lambda: (),
        **readers,
    )
    document = projection.build()
    assert document["export"]["failures"] == 3
    assert document["rcl"] is None
    assert document["evidence"] is None
    assert document["alerts"]["unresolved_stm_alert_seqs"] is None


# -- alert unresolved-seq derivation -----------------------------------------


def test_unresolved_excludes_resolved_seqs() -> None:
    document = _populated_projection().build()
    assert document["alerts"]["unresolved_stm_alert_seqs"] == [3, 1]


def test_unresolved_is_none_when_candidate_reader_fails() -> None:
    def _boom() -> None:
        raise RuntimeError("no candidates source")

    document = _all_none_projection(candidate_seqs=_boom).build()
    assert document["alerts"]["unresolved_stm_alert_seqs"] is None


def test_unresolved_does_not_assume_resolution_when_resolved_reader_fails() -> None:
    """Plan §2 decision 7: "the projection must not assume resolution" — a failing
    resolved-seq reader must not cause any candidate seq to be silently treated as resolved.
    """

    def _boom() -> None:
        raise RuntimeError("no resolved source")

    document = _all_none_projection(
        candidate_seqs=lambda: (5, 6, 7), resolved_seqs=_boom
    ).build()
    assert document["alerts"]["unresolved_stm_alert_seqs"] == [5, 6, 7]


def test_unresolved_when_nothing_has_ever_been_resolved() -> None:
    """The honest "no STM_ALERT_RESOLVED producer exists yet" wiring (plan §6 ⑧): a resolved
    reader returning an explicit empty tuple, not a failure — everything stays unresolved.
    """
    document = _all_none_projection(
        candidate_seqs=lambda: (1, 2), resolved_seqs=lambda: ()
    ).build()
    assert document["alerts"]["unresolved_stm_alert_seqs"] == [1, 2]


def test_unresolved_seqs_are_truncated_to_the_export_cap() -> None:
    many = tuple(range(MAX_UNRESOLVED_STM_ALERT_SEQS + 25))
    document = _all_none_projection(
        candidate_seqs=lambda: many, resolved_seqs=lambda: ()
    ).build()
    unresolved = document["alerts"]["unresolved_stm_alert_seqs"]
    assert len(unresolved) == MAX_UNRESOLVED_STM_ALERT_SEQS
    assert unresolved == list(many[:MAX_UNRESOLVED_STM_ALERT_SEQS])


# -- read_export_status: folding an exporter's write-side failures into export.* -------------


def test_no_read_export_status_supplied_behaves_exactly_as_before() -> None:
    """The default (``None``) — every existing standalone construction's behaviour — must be
    unchanged: ``export.failures``/``export.last_error`` reflect only this build's own reads.
    """
    document = _all_none_projection().build()
    assert document["export"] == {"failures": 0, "last_error": None}


def test_read_export_status_failures_are_summed_with_read_failures() -> None:
    def _boom() -> None:
        raise ValueError("boom")

    document = _all_none_projection(
        candidate_seqs=_boom, export_status=lambda: (2, None)
    ).build()
    # 1 own read failure (the candidate reader) + 2 supplied exporter failures = 3.
    assert document["export"]["failures"] == 3


def test_read_export_status_last_error_wins_when_both_sides_have_one() -> None:
    def _boom() -> None:
        raise ValueError("own read failed")

    document = _all_none_projection(
        candidate_seqs=_boom,
        export_status=lambda: (1, "exporter write failed"),
    ).build()
    assert document["export"]["last_error"] == "exporter write failed"
    assert document["export"]["failures"] == 2


def test_read_export_status_last_error_falls_back_to_own_when_exporter_has_none() -> (
    None
):
    def _boom() -> None:
        raise ValueError("own read failed")

    document = _all_none_projection(
        candidate_seqs=_boom, export_status=lambda: (0, None)
    ).build()
    assert "own read failed" in document["export"]["last_error"]
    assert document["export"]["failures"] == 1


def test_read_export_status_with_no_failures_on_either_side() -> None:
    document = _all_none_projection(export_status=lambda: (0, None)).build()
    assert document["export"] == {"failures": 0, "last_error": None}


def test_a_raising_read_export_status_is_counted_and_never_crashes_the_build() -> None:
    def _boom() -> None:
        raise RuntimeError("exporter status read broke")

    document = _all_none_projection(export_status=_boom).build()
    assert document["export"]["failures"] == 1
    assert "exporter status read broke" in document["export"]["last_error"]
