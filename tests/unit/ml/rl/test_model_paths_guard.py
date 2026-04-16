"""프로덕션 챔피언 경로 쓰기 가드 회귀 테스트.

CLAUDE.md / known_gaps.md: mppo_best/ 경로는 의도적 promote 시에만 쓰기 가능.
Hybrid 등 실험은 mppo_challenger/, mppo_experiment_*/로 한정.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from shared.ml.rl.model_paths import (
    PRODUCTION_CHAMPION_DIR,
    RLPathGuardError,
    check_save_path,
)


class TestCheckSavePath:
    def test_champion_path_rejected_without_promote(self):
        with pytest.raises(RLPathGuardError, match="production champion"):
            check_save_path(
                Path("models/futures/rl/mppo_best/"),
                promote=False,
            )

    def test_champion_path_allowed_with_promote(self):
        check_save_path(
            Path("models/futures/rl/mppo_best/"),
            promote=True,
        )

    def test_challenger_path_allowed(self):
        check_save_path(
            Path("models/futures/rl/mppo_challenger/"),
            promote=False,
        )

    def test_experiment_path_allowed(self):
        check_save_path(
            Path("models/futures/rl/mppo_experiment_hybrid_2026_04/"),
            promote=False,
        )

    def test_unknown_path_rejected(self):
        with pytest.raises(RLPathGuardError, match="Unknown"):
            check_save_path(
                Path("/tmp/random/path/"),
                promote=False,
            )

    def test_production_champion_dir_constant(self):
        assert PRODUCTION_CHAMPION_DIR == Path("models/futures/rl/mppo_best/")

    def test_nested_under_challenger_allowed(self):
        """트레이너가 save_dir에 `{algo}_best` 서브디렉토리를 덧붙여도 OK.

        이 케이스가 없으면 `save_dir=mppo_challenger/`로 설정해도
        `effective_path = mppo_challenger/mppo_best`가 되어 Unknown으로 거부됨.
        """
        check_save_path(
            Path("models/futures/rl/mppo_challenger/mppo_best"),
            promote=False,
        )

    def test_nested_under_experiment_allowed(self):
        check_save_path(
            Path("models/futures/rl/mppo_experiment_retrain_2026_04/mppo_best"),
            promote=False,
        )

    def test_nested_under_champion_rejected_without_promote(self):
        """mppo_best/ 하위 경로 쓰기도 --promote 필수."""
        with pytest.raises(RLPathGuardError, match="production champion"):
            check_save_path(
                Path("models/futures/rl/mppo_best/sub_run"),
                promote=False,
            )

    def test_nested_under_champion_allowed_with_promote(self):
        check_save_path(
            Path("models/futures/rl/mppo_best/sub_run"),
            promote=True,
        )
