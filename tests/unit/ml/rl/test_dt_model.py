"""Tests for Decision Transformer model and agent.

Tests DTConfig loading, DTAgent predict shape, action masking,
context window management, RTG decrease, and save/load roundtrip.
"""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest
import torch

transformers = pytest.importorskip("transformers", reason="transformers not available")

from shared.ml.rl.decision_transformer.model import DTAgent, DTConfig, _ContextBuffer


@pytest.fixture
def dt_config():
    """Minimal DTConfig for testing."""
    return DTConfig(
        state_dim=31,
        act_dim=5,
        hidden_size=32,  # small for fast tests
        n_layer=1,
        n_head=2,
        max_ep_len=100,
        action_tanh=False,
        context_length=10,
        resid_pdrop=0.0,
    )


@pytest.fixture
def agent(dt_config):
    """DTAgent instance for testing."""
    return DTAgent(config=dt_config, device="cpu")


class TestDTConfig:
    def test_from_dict(self):
        config = DTConfig(state_dim=31, act_dim=5, hidden_size=128)
        assert config.state_dim == 31
        assert config.act_dim == 5

    def test_to_dict(self):
        config = DTConfig()
        d = config.to_dict()
        assert "state_dim" in d
        assert "act_dim" in d
        assert "context_length" in d

    def test_from_json_roundtrip(self, dt_config, tmp_path):
        json_path = tmp_path / "config.json"
        with open(json_path, "w") as f:
            json.dump(dt_config.to_dict(), f)

        loaded = DTConfig.from_json(json_path)
        assert loaded.state_dim == dt_config.state_dim
        assert loaded.hidden_size == dt_config.hidden_size
        assert loaded.context_length == dt_config.context_length


class TestContextBuffer:
    def test_reset_clears(self):
        buf = _ContextBuffer(K=10, state_dim=31, act_dim=5)
        buf.reset(target_return=1000.0)
        buf.append(np.zeros(31), 0, 1.0, 0)
        assert buf.length == 1

        buf.reset(target_return=1000.0)
        assert buf.length == 0

    def test_append_increments(self):
        buf = _ContextBuffer(K=10, state_dim=31, act_dim=5)
        buf.reset(target_return=1000.0)

        for i in range(5):
            buf.append(np.zeros(31), 0, 0.0, i)

        assert buf.length == 5

    def test_rtg_decreases_with_reward(self):
        buf = _ContextBuffer(K=10, state_dim=31, act_dim=5)
        buf.reset(target_return=1000.0)

        buf.append(np.zeros(31), 0, 0.0, 0)
        assert buf.returns_to_go[0] == 1000.0

        buf.append(np.zeros(31), 0, 100.0, 1)
        assert buf.returns_to_go[1] == 900.0

        buf.append(np.zeros(31), 0, 200.0, 2)
        assert buf.returns_to_go[2] == 700.0


class TestDTAgent:
    def test_predict_returns_valid_action(self, agent):
        agent.reset(target_return=5000.0)
        state = np.random.randn(31).astype(np.float32)
        masks = np.ones(5, dtype=bool)

        action, probs = agent.predict(state, action_masks=masks)

        assert 0 <= action < 5
        assert probs.shape == (5,)
        assert abs(probs.sum() - 1.0) < 1e-5

    def test_predict_respects_action_mask(self, agent):
        agent.reset(target_return=5000.0)
        state = np.random.randn(31).astype(np.float32)

        # Only HOLD (4) allowed
        masks = np.array([False, False, False, False, True], dtype=bool)

        action, probs = agent.predict(state, action_masks=masks, deterministic=True)
        assert action == 4  # HOLD is last True
        assert probs[4] > 0.99  # all probability on HOLD

    def test_predict_shape_consistency(self, agent):
        agent.reset(target_return=5000.0)

        for _ in range(15):  # more than context_length=10
            state = np.random.randn(31).astype(np.float32)
            masks = np.ones(5, dtype=bool)
            action, probs = agent.predict(state, action_masks=masks, reward=0.1)

            assert 0 <= action < 5
            assert probs.shape == (5,)

    def test_rtg_decreases_during_predict(self, agent):
        agent.reset(target_return=1000.0)
        state = np.random.randn(31).astype(np.float32)
        masks = np.ones(5, dtype=bool)

        # First predict
        agent.predict(state, action_masks=masks, reward=0.0)
        first_rtg = agent._buf.returns_to_go[0]

        # Second predict with positive reward
        agent.predict(state, action_masks=masks, reward=100.0)
        second_rtg = agent._buf.returns_to_go[-1]

        assert second_rtg < first_rtg

    def test_save_load_roundtrip(self, agent, tmp_path):
        save_dir = tmp_path / "dt_test_model"
        agent.save(save_dir)

        # Verify files exist
        assert (save_dir / "model.pt").exists()
        assert (save_dir / "config.json").exists()

        # Load and verify
        loaded = DTAgent.load(save_dir)
        assert loaded.config.state_dim == agent.config.state_dim
        assert loaded.config.hidden_size == agent.config.hidden_size

        # Verify inference works
        loaded.reset(target_return=5000.0)
        state = np.random.randn(31).astype(np.float32)
        masks = np.ones(5, dtype=bool)
        action, probs = loaded.predict(state, action_masks=masks)
        assert 0 <= action < 5

    def test_deterministic_vs_stochastic(self, agent):
        agent.reset(target_return=5000.0)
        state = np.random.randn(31).astype(np.float32)
        masks = np.ones(5, dtype=bool)

        # Deterministic should give consistent results
        agent.reset(target_return=5000.0)
        action1, _ = agent.predict(state, action_masks=masks, deterministic=True)
        agent.reset(target_return=5000.0)
        action2, _ = agent.predict(state, action_masks=masks, deterministic=True)
        assert action1 == action2

    def test_no_mask_uses_all_actions(self, agent):
        agent.reset(target_return=5000.0)
        state = np.random.randn(31).astype(np.float32)

        # No mask → all actions available
        action, probs = agent.predict(state, action_masks=None)
        assert 0 <= action < 5
        assert probs.shape == (5,)
