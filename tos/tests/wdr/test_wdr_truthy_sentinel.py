"""Truthy-sentinel seal — the five WDR-axis StrEnums raise on ``bool()`` (design #26 §2.2/§4.2).

``DecisionResult`` / ``NonWaivableClassification`` / ``RequestState`` / ``ActiveDeviationState`` /
``WaivedEvidenceStatus`` are ``_NonTruthyStrEnum`` (``__bool__`` raises ``TypeError``), so a bare ``if
result:`` cannot read a denial / non-permissive / terminal member (``DENY`` / ``HOLD`` / ``NON_WAIVABLE``
/ ``UNRESOLVED`` / ``REVOKED`` / ``EXPIRED`` / ``FAIL``) as a truthy "go" (#13/#14 M1). Consumers use the
explicit positive-identity gate; the source is grep-asserted free of ``if result:`` misuse. ``PASS`` is
a member but is likewise truthy-untestable — the deviation ⇒ PASS flip is forbidden by the predicate.

Regime tag: structural substrate; truthy-sentinel seal; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import pytest
import tos.wdr as w

_ENUMS = (
    w.DecisionResult,
    w.NonWaivableClassification,
    w.RequestState,
    w.ActiveDeviationState,
    w.WaivedEvidenceStatus,
)


def test_every_member_raises_on_bool() -> None:
    """(§4.2) bool(member) raises TypeError on every member of every WDR-axis truthy-sealed enum."""
    for enum in _ENUMS:
        for member in enum:
            with pytest.raises(TypeError):
                bool(member)
            with pytest.raises(TypeError):
                if member:  # noqa: SIM103 — deliberately exercising __bool__
                    pass


def test_pass_member_is_truthy_untestable() -> None:
    """(§4.2) WaivedEvidenceStatus.PASS is a member yet truthy-untestable (no `if status:` go)."""
    with pytest.raises(TypeError):
        bool(w.WaivedEvidenceStatus.PASS)


def test_identity_value_and_membership_unaffected() -> None:
    """(§4.2) `is` identity, `.value`, and set membership do NOT call __bool__ (still usable)."""
    assert (
        w.DecisionResult.ELIGIBLE_FOR_RESTRICTED_CONFIGURATION
        is w.DecisionResult.ELIGIBLE_FOR_RESTRICTED_CONFIGURATION
    )
    assert w.DecisionResult.DENY.value == "DENY"
    assert w.WaivedEvidenceStatus.FAIL in w.MEASURED_FAILURE_STATUSES


def test_source_uses_explicit_identity_gates_not_truthy() -> None:
    """(§4.2) No wdr predicate code reads a truthy-sealed enum with a bare `if result:` / `if x:`.

    Docstrings cite the bare-``if`` misuse as an anti-pattern, so the check strips string / comment
    tokens and asserts the forbidden idiom is absent from executable code — the consume gates are
    explicit ``x is ENUM.MEMBER`` comparisons.
    """
    import tokenize
    from pathlib import Path

    src = Path(w.__file__).resolve().parent / "predicates.py"
    with open(src, encoding="utf-8") as handle:
        code = " ".join(
            tok.string
            for tok in tokenize.generate_tokens(handle.readline)
            if tok.type not in (tokenize.STRING, tokenize.COMMENT)
        )
    for forbidden in (
        "if result :",
        "if classification :",
        "if state :",
        "if status :",
    ):
        assert (
            forbidden not in code
        ), f"forbidden truthy misuse `{forbidden}` in predicates.py"


def test_member_counts_verbatim() -> None:
    """(appendix D) The enum member counts match the ADR verbatim transcription (over/under both caught)."""
    assert len(list(w.DecisionResult)) == 3
    assert len(list(w.NonWaivableClassification)) == 3
    assert len(list(w.RequestState)) == 10
    assert len(list(w.ActiveDeviationState)) == 7
    assert len(list(w.WaivedEvidenceStatus)) == 7
