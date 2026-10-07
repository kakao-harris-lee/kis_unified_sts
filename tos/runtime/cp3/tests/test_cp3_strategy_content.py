"""CP-3 B1b — the committed Setup D LONG strategy content.

Three claims, each asserted against the real artifacts rather than restated:

* the file loads through the **production** loader + admission gate;
* its work-step count fits the injected ``dsl_evaluation_budget_steps`` 64;
* the ``z_entry_max_x1000`` binding equals ``trunc(extreme_atr_mult × 1000)``
  for the ``extreme_atr_mult`` the legacy Setup D YAML declares.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from tos.dsl import DecisionKind
from tos.engine.admission import policy_work_steps, strategy_admissible
from tos.engine.vocabulary import AdmissionVerdict

from .. import runner
from . import _cp3_fixtures as fx

#: ``config/strategies/futures/setup_d_vwap_reversion.yaml`` 74행
#: ``extreme_atr_mult: 1.8`` — the citation, as a ``Decimal`` so the ×1000 is
#: exact (``1.8 * 1000`` in binary float is ``1800.0000000000002``).
CITED_EXTREME_ATR_MULT = Decimal("1.8")

#: The expected binding: ``-trunc(1.8 × 1000)``.
EXPECTED_Z_ENTRY_MAX_X1000 = -1800


def _repo_root() -> Path | None:
    """The repo root, found by walking up for the two directories that mark it.

    ``None`` when this package was extracted away from the repo (the strategy
    content then still loads — only the legacy-YAML cross-check below needs the
    repo, and it says so rather than passing vacuously).
    """
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "tos").is_dir() and (candidate / "config").is_dir():
            return candidate
    return None


def test_strategy_loads_through_the_real_loader_and_admission_gate() -> None:
    """The committed file is admitted by the shipped loader, not a test double.

    ``load_strategy_content`` wires ``tos_runtime.strategy.loader.load_strategies``
    to the production ``parse_strategy`` / ``strategy_admissible`` pair and runs
    ``tos_runtime.strategy.resolve``'s own five bindings rules — so passing here
    means a boot would accept this file, including its null-leaf / ``"TBD"`` /
    stray-file / unknown-key / orphan-binding discipline.
    """
    content = runner.load_strategy_content(
        strategy_path=fx.STRATEGY_PATH, bindings_path=fx.BINDINGS_PATH
    )
    assert strategy_admissible(content.strategy).verdict is AdmissionVerdict.ADMISSIBLE
    assert content.instrument_key.instrument == fx.INSTRUMENT
    assert content.instrument_key.account == "cp3-b1b-long"
    assert content.direction == "LONG"
    assert content.strategy.dsl_version == "cp3-b1b-dsl-1"
    assert content.strategy.config_binding_version == "cp3-b1b-bind-1"
    assert content.bindings == {"z_entry_max_x1000": EXPECTED_Z_ENTRY_MAX_X1000}


def test_policy_shape_is_the_three_ordered_rules_plus_a_default() -> None:
    """Entry first, then the two FLAT exits, then the mandatory default."""
    policy = runner.load_strategy_content(
        strategy_path=fx.STRATEGY_PATH, bindings_path=fx.BINDINGS_PATH
    ).strategy.policy
    assert policy is not None
    kinds = [rule.decision.kind for rule in policy.rules]
    assert kinds == [DecisionKind.ACTION, DecisionKind.FLAT, DecisionKind.FLAT]
    assert policy.default.kind is DecisionKind.NO_ACTION
    # The entry guard is the five-way conjunction; each exit guard is one compare.
    assert [len(rule.all_of) for rule in policy.rules] == [5, 1, 1]
    # The ACTION target carries the RISK quantity basis (evidence, not capacity).
    assert policy.rules[0].decision.target is not None
    assert policy.rules[0].decision.target.quantity_basis == "RISK"
    assert policy.rules[0].decision.target.direction == "LONG"
    assert policy.rules[0].decision.target.position_effect == "OPEN"


def test_work_steps_fit_the_injected_budget() -> None:
    """``policy_work_steps`` = rules + compares + operands ≤ 64, with headroom.

    The budget is a **pre-evaluation** gate (``tos.engine.pipeline``): over it,
    every tick folds to ``DEGRADED_BOUND_EXHAUSTED`` instead of evaluating, so
    this is not a cosmetic bound.
    """
    content = runner.load_strategy_content(
        strategy_path=fx.STRATEGY_PATH, bindings_path=fx.BINDINGS_PATH
    )
    policy = content.strategy.policy
    assert policy is not None
    steps = policy_work_steps(policy)
    assert steps == content.work_steps == 3 + 7 + 14 == 24
    assert steps <= runner.DEFAULT_BUDGET_STEPS == 64
    # kickoff §2: "규칙 3개(진입 + FLAT 둘)면 ≤ 20" compares.
    compares = sum(len(rule.all_of) for rule in policy.rules)
    assert compares == 7 <= 20


def test_z_entry_binding_is_trunc_extreme_atr_mult_times_1000() -> None:
    """The authored binding equals ``-trunc(extreme_atr_mult × 1000)``.

    The derivation, with its citation, is in ``strategy_bindings.yaml``: the
    legacy entry condition is ``abs(z) >= extreme_atr_mult`` and B1a publishes
    ``z`` as a ×1000 signed integer truncated toward zero, so the LONG-side
    comparison threshold is ``-trunc(extreme_atr_mult × 1000)``.
    """
    content = runner.load_strategy_content(
        strategy_path=fx.STRATEGY_PATH, bindings_path=fx.BINDINGS_PATH
    )
    derived = -int(CITED_EXTREME_ATR_MULT * 1000)
    assert derived == EXPECTED_Z_ENTRY_MAX_X1000
    assert content.bindings["z_entry_max_x1000"] == derived


def test_cited_extreme_atr_mult_still_matches_the_legacy_setup_d_yaml() -> None:
    """The citation is checked against the file it cites — not trusted.

    Read with ``yaml`` and a plain path, inside ``tos/``: no ``shared.*`` import
    (the firewall forbids it for runtime scope outright). If an operator retunes
    ``extreme_atr_mult``, this fails and names the new value, which is the
    signal that the binding above is stale.
    """
    repo_root = _repo_root()
    if repo_root is None:  # pragma: no cover - only outside the repo checkout
        pytest.fail(
            "cannot locate the repo root from this test file — the legacy "
            "Setup D YAML cross-check cannot be skipped silently"
        )
    path = (
        repo_root / "config" / "strategies" / "futures" / "setup_d_vwap_reversion.yaml"
    )
    assert path.is_file(), f"{path} is missing — the cited source must exist"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    params = document["strategy"]["entry"]["params"]
    actual = Decimal(str(params["extreme_atr_mult"]))
    assert actual == CITED_EXTREME_ATR_MULT, (
        f"{path} now declares extreme_atr_mult={actual}; "
        f"strategy_bindings.yaml's z_entry_max_x1000 "
        f"({EXPECTED_Z_ENTRY_MAX_X1000}) is derived from "
        f"{CITED_EXTREME_ATR_MULT} and is stale"
    )
