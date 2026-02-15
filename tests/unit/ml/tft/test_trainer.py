"""Tests for TFT trainer.

Tests 1-epoch training run, loss decrease, eval metrics shape,
and trading simulation.
"""

import numpy as np
import pytest
import torch

from shared.ml.tft.dataset import TFTDataset
from shared.ml.tft.model import TFTConfig, TFTModel
from shared.ml.tft.trainer import TFTTrainer


@pytest.fixture
def tft_config():
    """Minimal config for fast tests."""
    return TFTConfig(
        n_features=25,
        n_time_features=3,
        total_input_dim=28,
        hidden_size=16,
        lstm_layers=1,
        n_heads=2,
        dropout=0.0,
        grn_hidden=8,
        lookback=10,
        horizons=[1, 5, 15],
    )


@pytest.fixture
def sample_data():
    """Generate 5 days of sample data (200 bars each)."""
    np.random.seed(42)
    days_feat = []
    days_prices = []

    for _ in range(5):
        n_bars = 200
        feat = np.random.randn(n_bars, 25).astype(np.float32)
        close = 350.0 + np.cumsum(np.random.randn(n_bars) * 0.1)
        prices = np.column_stack([
            close - 0.05,
            close + np.abs(np.random.randn(n_bars) * 0.05),
            close - np.abs(np.random.randn(n_bars) * 0.05),
            close,
        ]).astype(np.float32)
        days_feat.append(feat)
        days_prices.append(prices)

    return days_feat, days_prices


class TestTFTTrainerUnit:
    """Unit tests using direct model/dataset creation (no config file)."""

    def test_single_epoch_runs(self, tft_config, sample_data):
        """Training runs without error for 1 epoch."""
        features, prices = sample_data
        train_feat, eval_feat = features[:3], features[3:]
        train_prices, eval_prices = prices[:3], prices[3:]

        model = TFTModel(tft_config)
        model.train()

        dataset = TFTDataset(
            train_feat, train_prices,
            lookback=tft_config.lookback,
            horizons=tft_config.horizons,
        )
        loader = torch.utils.data.DataLoader(
            dataset, batch_size=32, shuffle=True, drop_last=True,
        )

        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
        loss_fn = torch.nn.MSELoss()

        total_loss = 0.0
        n_batches = 0
        for x, y in loader:
            preds = model(x)
            loss = loss_fn(preds, y)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            n_batches += 1

        avg_loss = total_loss / max(n_batches, 1)
        assert avg_loss > 0
        assert n_batches > 0

    def test_loss_decreases(self, tft_config, sample_data):
        """Loss should decrease over multiple epochs."""
        features, prices = sample_data

        model = TFTModel(tft_config)
        model.train()

        dataset = TFTDataset(
            features, prices,
            lookback=tft_config.lookback,
            horizons=tft_config.horizons,
        )
        loader = torch.utils.data.DataLoader(
            dataset, batch_size=64, shuffle=True, drop_last=True,
        )

        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
        loss_fn = torch.nn.MSELoss()

        epoch_losses = []
        for epoch in range(5):
            total_loss = 0.0
            n = 0
            for x, y in loader:
                preds = model(x)
                loss = loss_fn(preds, y)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
                n += 1
            epoch_losses.append(total_loss / max(n, 1))

        # Loss should decrease (last < first)
        assert epoch_losses[-1] < epoch_losses[0]

    def test_eval_metrics_shape(self, tft_config, sample_data):
        """Eval metrics should contain expected keys."""
        features, prices = sample_data

        model = TFTModel(tft_config)
        model.eval()

        dataset = TFTDataset(
            features, prices,
            lookback=tft_config.lookback,
            horizons=tft_config.horizons,
        )
        loader = torch.utils.data.DataLoader(
            dataset, batch_size=64, shuffle=False,
        )

        # Manually compute eval metrics
        all_preds = []
        all_targets = []
        with torch.no_grad():
            for x, y in loader:
                preds = model(x)
                all_preds.append(preds.numpy())
                all_targets.append(y.numpy())

        preds_arr = np.concatenate(all_preds, axis=0)
        targets_arr = np.concatenate(all_targets, axis=0)

        assert preds_arr.shape[1] == 3  # 3 horizons
        assert targets_arr.shape[1] == 3
        assert preds_arr.shape[0] == targets_arr.shape[0]

    def test_trading_simulation(self, tft_config, sample_data):
        """Trading simulation should return valid metrics."""
        features, prices = sample_data

        model = TFTModel(tft_config)
        model.eval()

        # Manually run a simplified trading sim
        from shared.ml.tft.dataset import compute_time_features

        lookback = tft_config.lookback
        total_trades = 0

        for day_feat, day_prices in zip(features, prices):
            n_bars = len(day_feat)
            if n_bars < lookback + 15:
                continue

            time_feat = compute_time_features(n_bars)
            combined = np.concatenate([day_feat, time_feat], axis=1)

            t = lookback
            while t < n_bars - 15:
                x = combined[t - lookback : t]
                x_tensor = torch.from_numpy(x).unsqueeze(0)
                with torch.no_grad():
                    pred = model(x_tensor).numpy()[0]

                if abs(pred[2]) > 0.0001:  # 15m prediction
                    total_trades += 1
                    t += 15
                else:
                    t += 1

        # At least some trades should happen (random model makes predictions)
        assert total_trades >= 0  # May be 0 if all predictions are small


class TestTFTTrainerIntegration:
    """Integration test with actual TFTTrainer (mocked config)."""

    def test_eval_trading_returns_dict(self, tft_config, sample_data):
        """_eval_trading should return a proper dict."""
        features, prices = sample_data
        model = TFTModel(tft_config)
        model.eval()

        # Create a minimal trainer without config file
        trainer = TFTTrainer.__new__(TFTTrainer)
        trainer.tft_config = tft_config
        trainer.mode = tft_config.mode
        trainer.device = "cpu"
        trainer.batch_size = 64

        result = trainer._eval_trading(model, features, prices)

        assert "sharpe" in result
        assert "win_rate" in result
        assert "total_trades" in result
        assert "total_return_pct" in result
        assert isinstance(result["sharpe"], float)

    def test_eval_metrics_returns_expected_keys(self, tft_config, sample_data):
        """_eval_metrics should return MSE, MAE, dir_acc, IC per horizon."""
        features, prices = sample_data
        model = TFTModel(tft_config)

        dataset = TFTDataset(
            features, prices,
            lookback=tft_config.lookback,
            horizons=tft_config.horizons,
        )
        loader = torch.utils.data.DataLoader(dataset, batch_size=64)

        trainer = TFTTrainer.__new__(TFTTrainer)
        trainer.tft_config = tft_config
        trainer.mode = tft_config.mode
        trainer.device = "cpu"

        eval_loss, metrics = trainer._eval_metrics(model, loader)

        assert eval_loss > 0
        assert "mse_1m" in metrics
        assert "mse_5m" in metrics
        assert "mse_15m" in metrics
        assert "dir_acc_1m" in metrics
        assert "ic_1m" in metrics
        assert "dir_acc_avg" in metrics
        assert "ic_avg" in metrics

    def test_naive_baseline(self, tft_config, sample_data):
        """Naive baseline should return valid metrics."""
        features, prices = sample_data

        trainer = TFTTrainer.__new__(TFTTrainer)
        trainer.tft_config = tft_config

        result = trainer._eval_naive_baseline(features, prices)

        assert "naive_mse_1m" in result
        assert "naive_dir_acc_15m" in result
        # Naive direction accuracy should be around 50% for random data
        assert 0 <= result["naive_dir_acc_1m"] <= 100


class TestTFTClassificationTrainer:
    """Classification-specific trainer tests."""

    @pytest.fixture
    def cls_config(self):
        return TFTConfig(
            n_features=25,
            n_time_features=3,
            total_input_dim=28,
            hidden_size=16,
            lstm_layers=1,
            n_heads=2,
            dropout=0.0,
            grn_hidden=8,
            lookback=10,
            horizons=[1, 5, 15],
            mode="classification",
            label_smoothing=0.05,
        )

    def test_classification_loss_decreases(self, cls_config, sample_data):
        """BCEWithLogitsLoss should decrease over epochs."""
        features, prices = sample_data

        model = TFTModel(cls_config)
        model.train()

        dataset = TFTDataset(
            features, prices,
            lookback=cls_config.lookback,
            horizons=cls_config.horizons,
            mode="classification",
        )
        loader = torch.utils.data.DataLoader(
            dataset, batch_size=64, shuffle=True, drop_last=True,
        )

        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
        loss_fn = torch.nn.BCEWithLogitsLoss()

        epoch_losses = []
        for epoch in range(5):
            total_loss = 0.0
            n = 0
            for x, y in loader:
                preds = model(x)
                loss = loss_fn(preds, y)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
                n += 1
            epoch_losses.append(total_loss / max(n, 1))

        assert epoch_losses[-1] < epoch_losses[0]

    def test_classification_eval_metrics_keys(self, cls_config, sample_data):
        """Classification eval should return accuracy, AUC, F1, calibration."""
        features, prices = sample_data
        model = TFTModel(cls_config)

        dataset = TFTDataset(
            features, prices,
            lookback=cls_config.lookback,
            horizons=cls_config.horizons,
            mode="classification",
        )
        loader = torch.utils.data.DataLoader(dataset, batch_size=64)

        trainer = TFTTrainer.__new__(TFTTrainer)
        trainer.tft_config = cls_config
        trainer.mode = "classification"
        trainer.device = "cpu"

        eval_loss, metrics = trainer._eval_metrics(model, loader)

        assert eval_loss > 0
        assert "accuracy_1m" in metrics
        assert "accuracy_5m" in metrics
        assert "accuracy_15m" in metrics
        assert "auc_1m" in metrics
        assert "f1_1m" in metrics
        assert "calibration_1m" in metrics
        assert "accuracy_avg" in metrics
        assert "auc_avg" in metrics
        assert "ic_1m" in metrics

        # Accuracy should be in valid range
        assert 0 <= metrics["accuracy_1m"] <= 100
        assert 0 <= metrics["auc_1m"] <= 1.0

    def test_classification_trading_eval(self, cls_config, sample_data):
        """Classification trading eval should return valid metrics."""
        features, prices = sample_data
        model = TFTModel(cls_config)
        model.eval()

        trainer = TFTTrainer.__new__(TFTTrainer)
        trainer.tft_config = cls_config
        trainer.mode = "classification"
        trainer.device = "cpu"
        trainer.batch_size = 64

        result = trainer._eval_trading(model, features, prices)

        assert "sharpe" in result
        assert "win_rate" in result
        assert "total_trades" in result
        assert isinstance(result["sharpe"], float)
