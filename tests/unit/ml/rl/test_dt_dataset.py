"""Tests for Decision Transformer dataset and trajectory collection.

Tests RTG computation, Dataset length/shape, one-hot encoding,
attention mask, and save/load.
"""

import numpy as np
import pytest
import torch

from shared.ml.rl.decision_transformer.dataset import TrajectoryDataset


def _make_trajectory(T: int = 50, state_dim: int = 31) -> dict[str, np.ndarray]:
    """Generate a synthetic trajectory."""
    states = np.random.randn(T, state_dim).astype(np.float32)
    actions = np.random.randint(0, 5, size=T).astype(np.int64)
    rewards = np.random.randn(T).astype(np.float32)

    # Compute returns-to-go (reverse cumsum)
    rtg = np.zeros_like(rewards)
    rtg[-1] = rewards[-1]
    for t in range(T - 2, -1, -1):
        rtg[t] = rewards[t] + rtg[t + 1]

    timesteps = np.arange(T, dtype=np.int64)

    return {
        "states": states,
        "actions": actions,
        "rewards": rewards,
        "returns_to_go": rtg,
        "timesteps": timesteps,
    }


@pytest.fixture
def trajectories():
    """Multiple synthetic trajectories."""
    return [_make_trajectory(T=50), _make_trajectory(T=30), _make_trajectory(T=100)]


@pytest.fixture
def dataset(trajectories):
    """TrajectoryDataset with K=10."""
    return TrajectoryDataset(trajectories, context_length=10, act_dim=5)


class TestRTGComputation:
    def test_rtg_is_reverse_cumsum(self):
        traj = _make_trajectory(T=5)
        rewards = traj["rewards"]
        rtg = traj["returns_to_go"]

        # rtg[t] = sum(rewards[t:])
        for t in range(5):
            expected = rewards[t:].sum()
            assert abs(rtg[t] - expected) < 1e-5, f"RTG mismatch at t={t}"

    def test_rtg_last_equals_last_reward(self):
        traj = _make_trajectory(T=10)
        assert abs(traj["returns_to_go"][-1] - traj["rewards"][-1]) < 1e-5


class TestTrajectoryDataset:
    def test_length(self, dataset, trajectories):
        # Each traj contributes max(1, T - K + 1) indices
        K = 10
        expected = sum(max(1, len(t["states"]) - K + 1) for t in trajectories)
        assert len(dataset) == expected

    def test_item_shapes(self, dataset):
        item = dataset[0]

        assert item["states"].shape == (10, 31)
        assert item["actions"].shape == (10, 5)
        assert item["rewards"].shape == (10, 1)
        assert item["returns_to_go"].shape == (10, 1)
        assert item["timesteps"].shape == (10,)
        assert item["attention_mask"].shape == (10,)
        assert item["target_actions"].shape == (10,)

    def test_item_dtypes(self, dataset):
        item = dataset[0]

        assert item["states"].dtype == torch.float32
        assert item["actions"].dtype == torch.float32
        assert item["rewards"].dtype == torch.float32
        assert item["returns_to_go"].dtype == torch.float32
        assert item["timesteps"].dtype == torch.long
        assert item["attention_mask"].dtype == torch.float32
        assert item["target_actions"].dtype == torch.long

    def test_onehot_encoding(self, dataset):
        item = dataset[0]

        # Each row of actions should be one-hot (exactly one 1.0)
        for t in range(10):
            if item["attention_mask"][t] > 0:  # skip padded
                row = item["actions"][t]
                assert row.sum().item() == pytest.approx(1.0, abs=1e-5)
                assert row.max().item() == 1.0

    def test_attention_mask(self, dataset):
        item = dataset[0]
        mask = item["attention_mask"]

        # All non-padded positions should be 1.0
        # Padded positions (if any) should be 0.0
        assert (mask >= 0).all()
        assert (mask <= 1).all()

        # At least some positions should be real (mask=1)
        assert mask.sum() > 0

    def test_target_actions_match_onehot(self, dataset):
        item = dataset[0]

        for t in range(10):
            if item["attention_mask"][t] > 0:
                target = item["target_actions"][t].item()
                onehot = item["actions"][t]
                assert onehot[target].item() == 1.0

    def test_short_trajectory_padding(self):
        # Trajectory shorter than context length
        short_traj = _make_trajectory(T=5, state_dim=31)
        dataset = TrajectoryDataset([short_traj], context_length=10, act_dim=5)

        assert len(dataset) >= 1
        item = dataset[0]

        assert item["states"].shape == (10, 31)
        # First 5 positions should be padded (mask=0)
        pad_count = (item["attention_mask"] == 0).sum().item()
        assert pad_count >= 5  # at least 5 padded

    def test_empty_trajectories(self):
        dataset = TrajectoryDataset([], context_length=10, act_dim=5)
        assert len(dataset) == 0


class TestTrajectorySaveLoad:
    def test_save_load_roundtrip(self, trajectories, tmp_path):
        from shared.ml.rl.decision_transformer.dataset import TrajectoryCollector

        save_path = tmp_path / "test_trajs.pt"
        TrajectoryCollector.save(trajectories, save_path)

        assert save_path.exists()

        loaded = TrajectoryCollector.load(save_path)
        assert len(loaded) == len(trajectories)

        for orig, load in zip(trajectories, loaded):
            np.testing.assert_allclose(orig["states"], load["states"], atol=1e-5)
            np.testing.assert_array_equal(orig["actions"], load["actions"])
            np.testing.assert_allclose(orig["rewards"], load["rewards"], atol=1e-5)

    def test_load_nonexistent(self, tmp_path):
        from shared.ml.rl.decision_transformer.dataset import TrajectoryCollector

        with pytest.raises(FileNotFoundError):
            TrajectoryCollector.load(tmp_path / "nonexistent.pt")
