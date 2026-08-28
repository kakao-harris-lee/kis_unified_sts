"""Pure-evaluation property tests — determinism slice (design §6.2 / §4).

* **Referential transparency**: ``evaluate(s, c, cfg) == evaluate(s, c, cfg)`` — the
  same three inputs always yield the same Outcome + recorded signature (RFC-008 §9).
* **Ambient-independence (structural)**: ``evaluate``'s signature exposes no
  clock/RNG/env/network/fs parameter and no fetch callable, so it *cannot* reach an
  ambient source (DCE-INV-003) — verified at the type/signature level, backed by the
  import-closure test (``test_dsl_import_closure.py``).
* **EXV-INV-001 (captured, not called)**: ``evaluate`` has no fetch capability; a
  captured external value enters only through the Capsule (its snapshot digest is
  recorded as the reproduction pointer, never live-fetched).

Reproducibility granularity (bit-for-bit) is **not asserted** — deferred to
ADR-DEV-002 (design §4.3). Only outcome + recorded-signature equivalence is claimed.
"""

from __future__ import annotations

import inspect

import hypothesis.strategies as st
from hypothesis import given, settings
from tos.dsl import (
    EvaluationConfig,
    EvaluationResult,
    NoActionOutcome,
    Proposal,
    TargetKind,
    build_environment,
    evaluate,
)

from ._dsl_strategies import ENFORCEMENT_VERSION, SCHEME, issue_capsule, issue_strategy

_STRATEGY = issue_strategy()  # simple_policy: propose ACTION iff config.enabled
_CAPSULE = issue_capsule()

# Ambient names that MUST NOT appear as evaluation parameters (DCE-INV-003).
_AMBIENT_PARAM_NAMES = frozenset(
    {
        "clock",
        "now",
        "time",
        "wall_time",
        "random",
        "rand",
        "rng",
        "seed",
        "env",
        "environ",
        "getenv",
        "network",
        "socket",
        "http",
        "url",
        "fs",
        "file",
        "open",
        "fetch",
        "fetcher",
        "loader",
        "io",
        "callback",
    }
)


def _config(enabled: bool, **bindings: object) -> EvaluationConfig:
    return EvaluationConfig(
        config_version="cfg-v1", bindings={**bindings, "enabled": enabled}
    )


# ---------------------------------------------------------------------------
# Referential transparency
# ---------------------------------------------------------------------------


@given(
    enabled=st.booleans(),
    extra=st.dictionaries(st.text(max_size=4), st.integers(), max_size=3),
)
@settings(deadline=None, max_examples=50)
def test_evaluate_is_referentially_transparent(
    enabled: bool, extra: dict[str, int]
) -> None:
    """The same (strategy, capsule, config) always yields the same result (RFC-008 §9)."""
    cfg = _config(enabled, **extra)
    r1 = evaluate(
        _STRATEGY,
        _CAPSULE,
        cfg,
        scheme=SCHEME,
        enforcement_mechanism_version=ENFORCEMENT_VERSION,
    )
    r2 = evaluate(
        _STRATEGY,
        _CAPSULE,
        cfg,
        scheme=SCHEME,
        enforcement_mechanism_version=ENFORCEMENT_VERSION,
    )
    assert isinstance(r1, EvaluationResult)
    assert r1 == r2
    assert r1.outcome == r2.outcome
    assert r1.recorded_input_signature == r2.recorded_input_signature


def test_config_drives_decision_deterministically() -> None:
    """enabled ⇒ ACTION Proposal; disabled ⇒ No-Action (pure config-driven decision)."""
    on = evaluate(
        _STRATEGY,
        _CAPSULE,
        _config(True),
        scheme=SCHEME,
        enforcement_mechanism_version=ENFORCEMENT_VERSION,
    )
    assert isinstance(on.outcome, Proposal)
    assert on.outcome.target_kind is TargetKind.ACTION

    off = evaluate(
        _STRATEGY,
        _CAPSULE,
        _config(False),
        scheme=SCHEME,
        enforcement_mechanism_version=ENFORCEMENT_VERSION,
    )
    assert isinstance(off.outcome, NoActionOutcome)


# ---------------------------------------------------------------------------
# Ambient-independence (structural) + EXV-INV-001 (captured, not called)
# ---------------------------------------------------------------------------


def test_evaluate_signature_exposes_no_ambient_source() -> None:
    """evaluate takes only (strategy, capsule, config, scheme, mechanism-version) — no ambient (DCE-INV-003)."""
    params = set(inspect.signature(evaluate).parameters)
    assert params == {
        "strategy",
        "capsule",
        "config",
        "scheme",
        "enforcement_mechanism_version",
    }
    assert not (params & _AMBIENT_PARAM_NAMES)


def test_evaluate_has_no_fetch_capability_and_captures_from_capsule() -> None:
    """No fetch parameter exists; captured values come from the Capsule snapshot (EXV-INV-001)."""
    params = set(inspect.signature(evaluate).parameters)
    assert {"fetch", "fetcher", "loader", "callback"}.isdisjoint(params)
    result = evaluate(
        _STRATEGY,
        _CAPSULE,
        _config(True),
        scheme=SCHEME,
        enforcement_mechanism_version=ENFORCEMENT_VERSION,
    )
    assert result.recorded_input_signature.captured_external_value_refs == (
        _CAPSULE.critical_input_snapshot.canonical_digest,
    )


def test_build_environment_is_pure_and_ambient_free() -> None:
    """The environment namespaces only capsule + config — no clock/random/network (DCE-INV-003)."""
    cfg = _config(True)
    e1 = build_environment(_CAPSULE, cfg)
    e2 = build_environment(_CAPSULE, cfg)
    assert e1 == e2
    assert set(e1.keys()) == {"capsule", "config"}
