"""§13.15 composed-consequence partition-protective class (design #10 §6.5; BC-EV-013/016)."""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.brokercap import (
    ConformanceClass,
    partition_class_scope_ok,
    partition_protective_class,
)

from ._brokercap_strategies import issue_profile, live_scope

_ALL_WEAK = {
    "single_serialized_channel": True,
    "no_rapid_revocation": True,
    "shared_global_rate_limit": True,
}


def test_three_weaknesses_form_the_class() -> None:
    """(§13.15) All three weaknesses simultaneously => partition-protective class."""
    assert partition_protective_class(True, True, True) is True


@given(
    a=st.sampled_from([True, False, None]),
    b=st.sampled_from([True, False, None]),
    c=st.sampled_from([True, False, None]),
)
def test_partition_class_requires_all_three(
    a: bool | None, b: bool | None, c: bool | None
) -> None:
    """The class holds iff all three conditions are exactly True (None fails closed)."""
    assert partition_protective_class(a, b, c) == (
        a is True and b is True and c is True
    )


def test_class_a_unreduced_scope_prohibited() -> None:
    """(§13.15 canary a) Partition-protective class + CLASS_A + unreduced scope => False."""
    profile = issue_profile(
        conformance_class=ConformanceClass.CLASS_A_DETERMINISTIC_LIVE,
        live_scope=live_scope(reduced_off_unattended_partition_protection=None),
    )
    assert partition_class_scope_ok(profile, **_ALL_WEAK) is False


def test_class_c_is_ok() -> None:
    """(§13.15 canary b) The same class profile classified CLASS_C is admissible."""
    profile = issue_profile(
        conformance_class=ConformanceClass.CLASS_C_PROTECTIVE_SUPERVISED_ONLY
    )
    assert partition_class_scope_ok(profile, **_ALL_WEAK) is True


def test_class_d_is_ok() -> None:
    """(§13.15) A CLASS_D profile is admissible."""
    profile = issue_profile(conformance_class=ConformanceClass.CLASS_D_NON_LIVE)
    assert partition_class_scope_ok(profile, **_ALL_WEAK) is True


def test_reduced_scope_is_ok() -> None:
    """(§13.15) A reduced live scope (off unattended partition protection) is admissible."""
    profile = issue_profile(
        conformance_class=ConformanceClass.CLASS_A_DETERMINISTIC_LIVE,
        live_scope=live_scope(reduced_off_unattended_partition_protection=True),
    )
    assert partition_class_scope_ok(profile, **_ALL_WEAK) is True


def test_not_partition_class_imposes_no_reduction() -> None:
    """(§13.15) When not in the composed class, scope_ok is True (no reduction required)."""
    profile = issue_profile(
        conformance_class=ConformanceClass.CLASS_A_DETERMINISTIC_LIVE
    )
    assert (
        partition_class_scope_ok(
            profile,
            single_serialized_channel=False,
            no_rapid_revocation=True,
            shared_global_rate_limit=True,
        )
        is True
    )


def test_none_profile_fails_closed() -> None:
    """A None profile => False."""
    assert partition_class_scope_ok(None, **_ALL_WEAK) is False


def test_none_weakness_input_is_not_partition_class_so_scope_ok_true() -> None:
    """(§6.5, design-approved) A None weakness input => not the composed class => scope_ok True."""
    profile = issue_profile(
        conformance_class=ConformanceClass.CLASS_A_DETERMINISTIC_LIVE
    )
    assert (
        partition_class_scope_ok(
            profile,
            single_serialized_channel=None,
            no_rapid_revocation=None,
            shared_global_rate_limit=None,
        )
        is True
    )
    assert (
        partition_class_scope_ok(
            profile,
            single_serialized_channel=True,
            no_rapid_revocation=None,
            shared_global_rate_limit=True,
        )
        is True
    )
