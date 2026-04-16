"""RL model path constants + write guards.

Incident 2026-04-14 (see docs/data/known_gaps.md): experimental hybrid training
overwrote the production champion at models/futures/rl/mppo_best/best_model.zip.
This module centralizes path constants and write-path validation so the mistake
is structurally prevented.

Policy:
- Champion (production): models/futures/rl/mppo_best/ — write only with explicit promote flag
- Challenger (pre-promotion): models/futures/rl/mppo_challenger/ — write anytime
- Experiment: models/futures/rl/mppo_experiment_<tag>/ — write anytime
- Any other path: rejected by guard
"""
from __future__ import annotations

from pathlib import Path


class RLPathGuardError(RuntimeError):
    """Raised when a training script attempts to write to a protected model path."""


PRODUCTION_CHAMPION_DIR = Path("models/futures/rl/mppo_best/")
CHALLENGER_DIR = Path("models/futures/rl/mppo_challenger/")
EXPERIMENT_PREFIX = "mppo_experiment_"


def _is_under(child: Path, parent: Path) -> bool:
    """Return True if child == parent or child is strictly inside parent."""
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def check_save_path(save_dir: Path, *, promote: bool = False) -> None:
    """Validate that save_dir is an approved RL model write target.

    Args:
        save_dir: Directory where the training run will write best_model.zip.
                 May be either the approved directory itself or any subdirectory
                 under it (e.g. ``mppo_challenger/mppo_best`` is allowed because
                 ``mppo_challenger`` is approved).
        promote: True only when operator explicitly passes --promote at CLI.
                 Required to write to the production champion directory.

    Raises:
        RLPathGuardError: when write is not allowed.
    """
    resolved = Path(save_dir).resolve()
    champion_resolved = PRODUCTION_CHAMPION_DIR.resolve()
    challenger_resolved = CHALLENGER_DIR.resolve()
    rl_root = champion_resolved.parent  # models/futures/rl/

    # Champion path: writes anywhere under mppo_best/ require --promote.
    if _is_under(resolved, champion_resolved):
        if not promote:
            raise RLPathGuardError(
                f"Refusing to write under production champion path {save_dir}. "
                f"Use --promote to explicitly promote, or pick "
                f"{CHALLENGER_DIR} / {EXPERIMENT_PREFIX}<tag>/ for experiments."
            )
        return

    # Challenger path: writes anywhere under mppo_challenger/ OK.
    if _is_under(resolved, challenger_resolved):
        return

    # Experiment path: direct sibling (mppo_experiment_<tag>) or anywhere under it.
    try:
        rel = resolved.relative_to(rl_root)
    except ValueError:
        rel = None
    if rel is not None and rel.parts and rel.parts[0].startswith(EXPERIMENT_PREFIX):
        return

    raise RLPathGuardError(
        f"Unknown RL model save path: {save_dir}. Approved targets: "
        f"{PRODUCTION_CHAMPION_DIR} (with --promote), {CHALLENGER_DIR}, "
        f"or sibling {EXPERIMENT_PREFIX}<tag>/."
    )
