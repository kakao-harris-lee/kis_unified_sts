"""Polarity exhaustive regression — None ⇒ deny convergence (design #26 §4.3 / #18/#22 MAJOR-2 seal).

The #18/#22 MAJOR-2 lesson: a ``bool | None`` field read with ``if field:`` / ``if not field:`` fails
open on ``None`` depending on polarity. Every wdr field declares its polarity and is normalized with
``is True`` / ``is False`` — **never** ``is not True`` on a negative-polarity field. This suite
property-checks that **every negative-polarity field's ``None`` converges to deny** (never fail-opens to
"not unknown" / "not consumed" / "not drifted") and **every positive-polarity field's ``None`` /
``False`` converges to deny. The polarity expectations here are read off the §4.3 table, not
back-derived from the implementation.

Regime tag: predicate substrate only; polarity seal; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import pytest
import tos.wdr as w
from hypothesis import given

from ._wdr_strategies import (
    TRIBOOL,
    clean_decision,
    clean_request,
    clean_unknown_request,
)

_NEGATIVE_UNKNOWN_FIELDS = (
    "broker_state_unknown",
    "order_state_unknown",
    "exposure_unknown",
    "residual_risk_unknown",
    "control_state_unknown",
    "evidence_unknown",
    "scope_unknown",
    "currentness_unknown",
    "materiality_unknown",
)

_NEGATIVE_SCOPE_DRIFT_FIELDS = (
    "scope_wildcard",
    "scope_patched",
    "scope_widened",
    "scope_stale",
    "scope_conflicting",
)


# --- negative polarity: only explicit False admits; None / True deny ---------


@pytest.mark.parametrize("field", _NEGATIVE_UNKNOWN_FIELDS)
@given(flag=TRIBOOL)
def test_unknown_flag_negative_polarity_none_denies(
    field: str, flag: bool | None
) -> None:
    """(§4.3 negative) Each §16 UNKNOWN flag admits only on explicit False; None / True ⇒ deny."""
    req = clean_unknown_request(**{field: flag})
    result = w.unknown_denies_and_confines(req, w.AllFalseDeviationAuthority())
    assert result is (flag is False)


@pytest.mark.parametrize("field", _NEGATIVE_SCOPE_DRIFT_FIELDS)
@given(flag=TRIBOOL)
def test_scope_drift_negative_polarity_none_denies(
    field: str, flag: bool | None
) -> None:
    """(§4.3 negative) Each scope-drift flag admits only on explicit False; None / True ⇒ deny."""
    req = clean_request(**{field: flag}, non_waivable_classification=None)
    result = w.scope_exact_and_complete(req, w.MANDATED_SCOPE_FLOOR)
    assert result is (flag is False)


@given(consumed=TRIBOOL)
def test_single_use_consumed_negative_polarity(consumed: bool | None) -> None:
    """(§4.3 negative / §13 line 368) single_use_consumed: only explicit False admits; None / True deny."""
    decision = clean_decision(single_use_consumed=consumed)
    assert w.deviation_single_use_non_authorizing(decision) is (consumed is False)


@given(
    re_armed=TRIBOOL,
    self_reverted=TRIBOOL,
    recovered=TRIBOOL,
)
def test_expiry_recovery_revives_nothing_negative_polarity(
    re_armed: bool | None, self_reverted: bool | None, recovered: bool | None
) -> None:
    """(§4.3 negative / §6.5) revives-nothing admits only when all three are explicit False."""
    result = w.expiry_recovery_revives_nothing(re_armed, self_reverted, recovered)
    expected = re_armed is False and self_reverted is False and recovered is False
    assert result is expected


@given(broker=TRIBOOL, order=TRIBOOL)
def test_broker_finality_negative_polarity(
    broker: bool | None, order: bool | None
) -> None:
    """(§4.3 negative / §6.4) broker_finality_unchanged admits only when both are explicit False."""
    result = w.broker_finality_unchanged(broker, order)
    assert result is (broker is False and order is False)


# --- positive polarity: only explicit True admits; None / False deny --------


@given(resolved=TRIBOOL)
def test_applicability_resolved_positive_polarity(resolved: bool | None) -> None:
    """(§4.3 positive / §9 line 273) applicability_resolved admits only on True; None / False deny."""
    req = clean_request(applicability_resolved=resolved)
    # the boundary yolk requires applicability_resolved is True.
    from ._wdr_strategies import clean_boundary

    assert w.boundary_denies_non_waivable(req, clean_boundary()) is (resolved is True)


@given(resolved=TRIBOOL)
def test_applicability_resolved_positive_polarity_in_unknown_yolk(
    resolved: bool | None,
) -> None:
    """(§4.3 positive / INV-010 line 184 / MINOR-1) The UNKNOWN yolk admits only on applicability True."""
    req = clean_unknown_request(applicability_resolved=resolved)
    result = w.unknown_denies_and_confines(req, w.AllFalseDeviationAuthority())
    assert result is (resolved is True)


@given(verdict=TRIBOOL, common_mode=TRIBOOL)
def test_effective_principal_verdict_positive_polarity(
    verdict: bool | None, common_mode: bool | None
) -> None:
    """(§4.3 positive) effective_principal_verdict admits only on True; common_mode admits only False."""
    result = w.independent_effective_person_approval(
        w.AllFalseDeviationAuthority(), verdict, common_mode
    )
    assert result is (verdict is True and common_mode is False)


@given(within=TRIBOOL)
def test_combined_envelope_positive_polarity(within: bool | None) -> None:
    """(§4.3 positive / §13 item 3) member_within_envelope admits only on True; None / False deny."""
    from ._wdr_strategies import clean_active_set

    aset = clean_active_set(member_decisions=("d1",))
    assert w.combined_set_no_permissive_union(aset, frozenset({"d1"}), within) is (
        within is True
    )


@given(complete=TRIBOOL)
def test_is_complete_positive_polarity(complete: bool | None) -> None:
    """(§4.3 positive / §13 line 364) is_complete admits only on True; None / False ⇒ invalid config."""
    from ._wdr_strategies import clean_active_set

    aset = clean_active_set(member_decisions=("d1",), is_complete=complete)
    assert w.combined_set_no_permissive_union(aset, frozenset({"d1"}), True) is (
        complete is True
    )


def _code_only(path: str) -> str:
    """Return the source with string literals and comments stripped (tokenize-based).

    Docstrings deliberately *cite* the forbidden idioms as anti-patterns, so a raw grep would
    false-match; stripping ``STRING`` / ``COMMENT`` tokens leaves only executable code.
    """
    import tokenize

    with open(path, encoding="utf-8") as handle:
        tokens = tokenize.generate_tokens(handle.readline)
        return " ".join(
            tok.string
            for tok in tokens
            if tok.type not in (tokenize.STRING, tokenize.COMMENT)
        )


#: Every negative-polarity ``bool | None`` field consumed by the predicates (§4.3 table). A negative
#: field admits only on ``is False`` (deny normalization ``is not False``); ``is not True`` on any of
#: these would admit a ``None`` — the #18/#22 fail-open the task forbids. (Positive-polarity fields
#: legitimately use ``is not True`` as their deny form, so the ban is field-specific, not blanket.)
_NEGATIVE_POLARITY_FIELDS = (
    "single_use_consumed",
    "scope_wildcard",
    "scope_patched",
    "scope_widened",
    "scope_stale",
    "scope_conflicting",
    "materiality_unknown",
    "common_mode_present",
    "protective_label_bypass",
    "broker_state_unknown",
    "order_state_unknown",
    "exposure_unknown",
    "residual_risk_unknown",
    "control_state_unknown",
    "evidence_unknown",
    "scope_unknown",
    "currentness_unknown",
    "observation_only",
    "deviation_exists",
    "re_armed",
    "self_reverted",
    "recovered_without_fresh_chain",
)


def test_no_is_not_true_on_negative_polarity_field_in_source() -> None:
    """(§4.3 task discipline) No negative-polarity field is consumed via the fail-open ``is not True``.

    ``is not True`` on a negative-polarity field admits a ``None`` (the #18/#22 fail-open). Every
    negative-polarity field must be read with ``is False`` (deny ``is not False``). The check strips
    docstrings / comments (which cite the idiom as an anti-pattern) and asserts no ``<field> is not
    True`` occurs in executable code. Positive-polarity fields legitimately use ``is not True`` as their
    deny form, so the ban is field-specific.
    """
    from pathlib import Path

    src = Path(w.__file__).resolve().parent
    offenders: list[str] = []
    for name in ("predicates.py", "state.py", "records.py"):
        code = _code_only(str(src / name))
        for field in _NEGATIVE_POLARITY_FIELDS:
            if f"{field} is not True" in code:
                offenders.append(f"{name}: {field} is not True")
    assert offenders == [], f"negative-polarity fail-open `is not True`: {offenders}"
