"""Guards on the Setup A/C Optuna driver (`scripts/optimize_decision_engine.py`).

Two things are pinned here.

**The degenerate-study abort.** ``_run_and_score`` returns a large negative
penalty for any parameter set that produced fewer than 10 trades. With Setup C's
deployed 15-minute event window the replay can hit that floor for EVERY sampled
point, and Optuna still reports a ``best_trial`` — an arbitrary first sample.
Writing that out as ``best_params`` would hand a later walk-forward a set of
"tuned" values that were never measured, so the driver refuses instead.

**The single YAML read.** ``window_minutes`` is not tuned; it comes from the
deployed strategy file so this in-sample search and the out-of-sample
walk-forward evaluate the same event window. It must be read once per process,
not once per trial.

Hermetic: no study is run and no market data is touched. Optuna's in-memory
study (already a project dependency) is used only as a container for
hand-built trial values.
"""

from __future__ import annotations

import importlib
from typing import Any

import optuna
import pytest

from shared.decision.setups.event_reaction import SetupCConfig

optuna.logging.set_verbosity(optuna.logging.WARNING)


@pytest.fixture(scope="module")
def optimizer() -> Any:
    """The script module under test (imported once — it is import-heavy)."""
    return importlib.import_module("scripts.optimize_decision_engine")


def _study_with_values(values: list[float]) -> optuna.Study:
    """An in-memory study holding one COMPLETE trial per supplied value."""
    study = optuna.create_study(direction="maximize")
    for value in values:
        trial = study.ask()
        study.tell(trial, value)
    return study


# ---------------------------------------------------------------------------
# _assert_study_is_not_degenerate
# ---------------------------------------------------------------------------


def test_all_penalty_trials_abort_the_study(optimizer: Any) -> None:
    """Every trial at the floor = nothing was measured; refuse to emit params."""
    study = _study_with_values([optimizer._DEGENERATE_TRIAL_SCORE] * 5)

    with pytest.raises(SystemExit) as excinfo:
        optimizer._assert_study_is_not_degenerate(study, "c")

    message = str(excinfo.value)
    assert "min-trades penalty" in message
    # The operator has to be told WHICH window produced it and where it lives.
    assert "setup_c_event_reaction.yaml" in message
    assert f"window_minutes={SetupCConfig.from_yaml().window_minutes}" in message


def test_abort_message_for_setup_a_omits_the_setup_c_window(optimizer: Any) -> None:
    """The window note is Setup C's; Setup A must not be told about it."""
    study = _study_with_values([optimizer._DEGENERATE_TRIAL_SCORE] * 3)

    with pytest.raises(SystemExit) as excinfo:
        optimizer._assert_study_is_not_degenerate(study, "a")

    message = str(excinfo.value)
    assert "min-trades penalty" in message
    assert "window_minutes" not in message


def test_one_real_trial_is_enough_to_proceed(optimizer: Any) -> None:
    """A single scoring trial means the search space is not degenerate."""
    study = _study_with_values(
        [optimizer._DEGENERATE_TRIAL_SCORE, 1.75, optimizer._DEGENERATE_TRIAL_SCORE]
    )

    optimizer._assert_study_is_not_degenerate(study, "c")  # must not raise


def test_empty_study_aborts(optimizer: Any) -> None:
    """No completed trial at all is a different failure, reported as such."""
    study = optuna.create_study(direction="maximize")

    with pytest.raises(SystemExit) as excinfo:
        optimizer._assert_study_is_not_degenerate(study, "c")

    assert "no trial completed" in str(excinfo.value)


def test_failed_trials_do_not_count_as_measurements(optimizer: Any) -> None:
    """A study whose only non-penalty trials FAILED is still degenerate."""
    study = optuna.create_study(direction="maximize")
    study.tell(study.ask(), optimizer._DEGENERATE_TRIAL_SCORE)
    study.tell(study.ask(), state=optuna.trial.TrialState.FAIL)

    with pytest.raises(SystemExit):
        optimizer._assert_study_is_not_degenerate(study, "c")


# ---------------------------------------------------------------------------
# _deployed_setup_c_window_minutes
# ---------------------------------------------------------------------------


def test_window_minutes_matches_the_deployed_strategy_file(optimizer: Any) -> None:
    """The optimiser and the walk-forward must read the same value."""
    optimizer._deployed_setup_c_window_minutes.cache_clear()
    assert (
        optimizer._deployed_setup_c_window_minutes()
        == SetupCConfig.from_yaml().window_minutes
    )


def test_window_minutes_is_read_once_per_process(
    optimizer: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cached: the objective runs per trial and must not re-read YAML each time.

    It also stops a mid-study edit from silently splitting one study across two
    event windows.
    """
    optimizer._deployed_setup_c_window_minutes.cache_clear()
    calls = {"n": 0}
    real = SetupCConfig.from_yaml

    @classmethod  # type: ignore[misc]
    def _counting_from_yaml(cls: type[SetupCConfig], *args: Any, **kwargs: Any):
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(SetupCConfig, "from_yaml", _counting_from_yaml)

    first = optimizer._deployed_setup_c_window_minutes()
    for _ in range(20):
        assert optimizer._deployed_setup_c_window_minutes() == first

    assert calls["n"] == 1, f"YAML read {calls['n']} times, expected once"
    optimizer._deployed_setup_c_window_minutes.cache_clear()
