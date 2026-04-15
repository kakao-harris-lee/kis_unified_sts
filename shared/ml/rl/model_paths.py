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


def check_save_path(save_dir: Path, *, promote: bool = False) -> None:
    """Validate that save_dir is an approved RL model write target.

    Args:
        save_dir: Directory where the training run will write best_model.zip.
        promote: True only when operator explicitly passes --promote at CLI.
                 Required to write to the production champion directory.

    Raises:
        RLPathGuardError: when write is not allowed.
    """
    resolved = Path(save_dir).resolve()
    champion_resolved = PRODUCTION_CHAMPION_DIR.resolve()
    challenger_resolved = CHALLENGER_DIR.resolve()

    if resolved == champion_resolved:
        if not promote:
            raise RLPathGuardError(
                f"Refusing to write to production champion path {save_dir}. "
                f"Use --promote to explicitly promote, or pick "
                f"{CHALLENGER_DIR} / {EXPERIMENT_PREFIX}<tag>/ for experiments."
            )
        return

    if resolved == challenger_resolved:
        return

    if resolved.name.startswith(EXPERIMENT_PREFIX) and resolved.parent == champion_resolved.parent:
        return

    raise RLPathGuardError(
        f"Unknown RL model save path: {save_dir}. Approved targets: "
        f"{PRODUCTION_CHAMPION_DIR} (with --promote), {CHALLENGER_DIR}, "
        f"or sibling {EXPERIMENT_PREFIX}<tag>/."
    )
