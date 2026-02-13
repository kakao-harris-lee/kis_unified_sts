"""Tests for Decision Transformer trainer.

Tests single epoch execution, loss decrease, gradient clipping,
and online evaluation metrics.
"""

import numpy as np
import pytest
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

transformers = pytest.importorskip("transformers", reason="transformers not available")

from shared.ml.rl.decision_transformer.dataset import TrajectoryDataset
from shared.ml.rl.decision_transformer.model import DTAgent, DTConfig


def _make_trajectory(T: int = 50, state_dim: int = 31) -> dict[str, np.ndarray]:
    """Generate a synthetic trajectory."""
    states = np.random.randn(T, state_dim).astype(np.float32)
    actions = np.random.randint(0, 5, size=T).astype(np.int64)
    rewards = np.random.randn(T).astype(np.float32)

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
def dt_config():
    return DTConfig(
        state_dim=31,
        act_dim=5,
        hidden_size=32,
        n_layer=1,
        n_head=2,
        max_ep_len=100,
        action_tanh=False,
        context_length=10,
        resid_pdrop=0.0,
    )


@pytest.fixture
def train_trajectories():
    return [_make_trajectory(T=50) for _ in range(5)]


@pytest.fixture
def train_loader(train_trajectories, dt_config):
    dataset = TrajectoryDataset(
        train_trajectories,
        context_length=dt_config.context_length,
        act_dim=dt_config.act_dim,
    )
    return DataLoader(dataset, batch_size=8, shuffle=True, drop_last=True)


class TestSingleEpoch:
    def test_one_epoch_runs(self, dt_config, train_loader):
        agent = DTAgent(config=dt_config, device="cpu")
        model = agent.model
        model.train()

        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
        loss_fn = nn.CrossEntropyLoss()

        total_loss = 0.0
        n_batches = 0

        for batch in train_loader:
            output = model(
                states=batch["states"],
                actions=batch["actions"],
                rewards=batch["rewards"],
                returns_to_go=batch["returns_to_go"],
                timesteps=batch["timesteps"],
                attention_mask=batch["attention_mask"],
            )

            preds = output.action_preds
            B, K, A = preds.shape
            mask_flat = batch["attention_mask"].reshape(-1).bool()
            preds_flat = preds.reshape(-1, A)[mask_flat]
            targets_flat = batch["target_actions"].reshape(-1)[mask_flat]

            loss = loss_fn(preds_flat, targets_flat)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            total_loss += loss.item()
            n_batches += 1

        avg_loss = total_loss / max(n_batches, 1)
        assert avg_loss > 0  # loss should be positive
        assert n_batches > 0

    def test_loss_decreases_over_epochs(self, dt_config, train_loader):
        agent = DTAgent(config=dt_config, device="cpu")
        model = agent.model
        model.train()

        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
        loss_fn = nn.CrossEntropyLoss()

        epoch_losses = []
        for _epoch in range(5):
            total_loss = 0.0
            n = 0
            for batch in train_loader:
                output = model(
                    states=batch["states"],
                    actions=batch["actions"],
                    rewards=batch["rewards"],
                    returns_to_go=batch["returns_to_go"],
                    timesteps=batch["timesteps"],
                    attention_mask=batch["attention_mask"],
                )
                preds = output.action_preds
                B, K, A = preds.shape
                mask_flat = batch["attention_mask"].reshape(-1).bool()
                preds_flat = preds.reshape(-1, A)[mask_flat]
                targets_flat = batch["target_actions"].reshape(-1)[mask_flat]

                loss = loss_fn(preds_flat, targets_flat)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
                n += 1

            epoch_losses.append(total_loss / max(n, 1))

        # Loss should generally decrease (last < first)
        assert epoch_losses[-1] < epoch_losses[0], (
            f"Loss did not decrease: {epoch_losses}"
        )


class TestGradientClipping:
    def test_grad_clip_limits_norms(self, dt_config, train_loader):
        agent = DTAgent(config=dt_config, device="cpu")
        model = agent.model
        model.train()

        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
        loss_fn = nn.CrossEntropyLoss()
        max_norm = 0.25

        batch = next(iter(train_loader))
        output = model(
            states=batch["states"],
            actions=batch["actions"],
            rewards=batch["rewards"],
            returns_to_go=batch["returns_to_go"],
            timesteps=batch["timesteps"],
            attention_mask=batch["attention_mask"],
        )
        preds = output.action_preds
        B, K, A = preds.shape
        mask_flat = batch["attention_mask"].reshape(-1).bool()
        preds_flat = preds.reshape(-1, A)[mask_flat]
        targets_flat = batch["target_actions"].reshape(-1)[mask_flat]

        loss = loss_fn(preds_flat, targets_flat)
        optimizer.zero_grad()
        loss.backward()

        # Clip gradients
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm)

        # Verify total norm is bounded
        total_norm = 0.0
        for p in model.parameters():
            if p.grad is not None:
                total_norm += p.grad.data.norm(2).item() ** 2
        total_norm = total_norm ** 0.5

        assert total_norm <= max_norm + 0.01  # small tolerance


class TestOnlineEvaluation:
    def test_agent_runs_on_env(self, dt_config):
        """Test DTAgent can run on FuturesTradingEnv for one episode."""
        from shared.ml.rl.env import FuturesTradingEnv, RLEnvConfig

        env_config = RLEnvConfig(
            initial_balance=100_000_000,
            commission_rate=0.00003,
            tick_size=0.05,
            tick_value=250_000,
            contract_multiplier=250_000,
            max_contracts=1,
            slippage=0.0,
            margin_rate=0.15,
            n_market_features=25,
            n_position_features=6,
        )

        n_steps = 50
        day_data = np.random.randn(n_steps, 25).astype(np.float32)
        prices = np.zeros((n_steps, 4), dtype=np.float32)
        base_price = 350.0
        for i in range(n_steps):
            c = base_price + np.random.randn() * 0.5
            prices[i] = [c + 0.1, c + 0.3, c - 0.3, c]

        env = FuturesTradingEnv(day_data=day_data, config=env_config, prices=prices)
        agent = DTAgent(config=dt_config, device="cpu")
        agent.reset(target_return=5_000_000.0)

        obs, _ = env.reset()
        terminated = False
        prev_reward = 0.0
        steps = 0

        while not terminated:
            masks = env.action_masks()
            action, probs = agent.predict(
                obs, action_masks=masks, reward=prev_reward, deterministic=True,
            )
            obs, reward, terminated, _, info = env.step(int(action))
            prev_reward = float(reward)
            steps += 1

        assert steps > 0
        assert "balance" in info
        assert "n_trades" in info
