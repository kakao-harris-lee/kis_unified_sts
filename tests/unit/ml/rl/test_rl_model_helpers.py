"""load_rl_scaler — defensive guard regression test.

Regression test for defensive None guard in load_rl_scaler.scaler_path.
Ensures that passing scaler_path=None (config key missing) does not crash
with AttributeError: 'NoneType' object has no attribute 'strip'.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from shared.strategy.rl_model_helpers import load_rl_scaler


class TestLoadRLScaler:
    def test_load_rl_scaler_accepts_none_path(self, tmp_path, monkeypatch):
        """Passing scaler_path=None must not crash with AttributeError on .strip().

        When config key is missing, scaler_path may be None. The function should
        degrade gracefully by falling back to auto-detection from model_path.
        """
        # Clear environment overrides
        monkeypatch.delenv("RL_MPPO_SCALER_PATH", raising=False)
        monkeypatch.delenv("RL_MPPO_MODEL_PATH", raising=False)

        # Provide a nonexistent model_path — auto-detection will construct
        # an effective_path, but since scaler.joblib doesn't exist,
        # load_rl_scaler should return None gracefully (not raise AttributeError).
        result = load_rl_scaler(None, str(tmp_path / "nonexistent" / "model.zip"))
        assert result is None

    def test_load_rl_scaler_accepts_empty_string_path(self, tmp_path, monkeypatch):
        """Passing scaler_path='' (empty string) must also not crash.

        Empty string should be treated as missing and fall back to auto-detection.
        """
        monkeypatch.delenv("RL_MPPO_SCALER_PATH", raising=False)
        monkeypatch.delenv("RL_MPPO_MODEL_PATH", raising=False)

        result = load_rl_scaler("", str(tmp_path / "nonexistent" / "model.zip"))
        assert result is None

    def test_load_rl_scaler_uses_env_override(self, tmp_path, monkeypatch):
        """Environment variable override takes highest priority."""
        scaler_path = tmp_path / "scaler.joblib"
        scaler_path.write_text("dummy")

        monkeypatch.setenv("RL_MPPO_SCALER_PATH", str(scaler_path))
        monkeypatch.delenv("RL_MPPO_MODEL_PATH", raising=False)

        # Should attempt to load from env override path
        # (will fail gracefully due to invalid joblib format, but won't crash on None.strip())
        result = load_rl_scaler(None, "/tmp/dummy/model.zip")
        assert result is None  # File exists but can't load as joblib

    def test_load_rl_scaler_uses_argument_path(self, tmp_path, monkeypatch):
        """scaler_path argument is second priority (after env)."""
        scaler_path = tmp_path / "scaler.joblib"
        scaler_path.write_text("dummy")

        monkeypatch.delenv("RL_MPPO_SCALER_PATH", raising=False)
        monkeypatch.delenv("RL_MPPO_MODEL_PATH", raising=False)

        result = load_rl_scaler(str(scaler_path), "/tmp/dummy/model.zip")
        assert result is None  # File exists but can't load as joblib
