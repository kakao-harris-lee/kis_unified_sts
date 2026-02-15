"""Tests for TFT model components.

Tests TFTConfig loading, GRN/VSN shapes, TFTModel forward pass,
variable importance, attention weights, save/load roundtrip,
and classification mode (predict_direction_probs).
"""

import json

import numpy as np
import pytest
import torch

from shared.ml.tft.model import (
    GatedResidualNetwork,
    TFTConfig,
    TFTModel,
    VariableSelectionNetwork,
)


@pytest.fixture
def tft_config():
    """Minimal TFTConfig for testing."""
    return TFTConfig(
        n_features=25,
        n_time_features=3,
        total_input_dim=28,
        hidden_size=16,  # small for fast tests
        lstm_layers=1,
        n_heads=2,
        dropout=0.0,
        grn_hidden=8,
        lookback=10,
        horizons=[1, 5, 15],
    )


@pytest.fixture
def model(tft_config):
    """TFTModel instance for testing."""
    return TFTModel(tft_config)


@pytest.fixture
def sample_input(tft_config):
    """Sample input tensor: (batch, lookback, total_input_dim)."""
    return torch.randn(4, tft_config.lookback, tft_config.total_input_dim)


class TestTFTConfig:
    def test_defaults(self):
        config = TFTConfig()
        assert config.n_features == 25
        assert config.total_input_dim == 28
        assert config.horizons == [1, 5, 15]
        assert config.mode == "regression"

    def test_classification_mode(self):
        config = TFTConfig(mode="classification", label_smoothing=0.1)
        assert config.mode == "classification"
        assert config.label_smoothing == 0.1
        assert config.classification_threshold == 0.0

    def test_to_dict_includes_mode(self):
        config = TFTConfig(mode="classification")
        d = config.to_dict()
        assert d["mode"] == "classification"
        assert "label_smoothing" in d
        assert "classification_threshold" in d

    def test_to_dict(self):
        config = TFTConfig()
        d = config.to_dict()
        assert "hidden_size" in d
        assert "horizons" in d
        assert d["n_features"] == 25

    def test_from_json_roundtrip(self, tft_config, tmp_path):
        json_path = tmp_path / "config.json"
        with open(json_path, "w") as f:
            json.dump(tft_config.to_dict(), f)

        loaded = TFTConfig.from_json(json_path)
        assert loaded.hidden_size == tft_config.hidden_size
        assert loaded.horizons == tft_config.horizons
        assert loaded.lookback == tft_config.lookback


class TestGRN:
    def test_output_shape(self):
        grn = GatedResidualNetwork(
            input_size=16, hidden_size=8, output_size=16, dropout=0.0
        )
        x = torch.randn(4, 10, 16)
        out = grn(x)
        assert out.shape == (4, 10, 16)

    def test_different_input_output_dims(self):
        grn = GatedResidualNetwork(
            input_size=32, hidden_size=16, output_size=16, dropout=0.0
        )
        x = torch.randn(2, 5, 32)
        out = grn(x)
        assert out.shape == (2, 5, 16)

    def test_with_context(self):
        grn = GatedResidualNetwork(
            input_size=16, hidden_size=8, output_size=16,
            dropout=0.0, context_size=32,
        )
        x = torch.randn(4, 10, 16)
        ctx = torch.randn(4, 10, 32)
        out = grn(x, context=ctx)
        assert out.shape == (4, 10, 16)


class TestVSN:
    def test_output_shape(self):
        vsn = VariableSelectionNetwork(
            n_vars=28, hidden_size=16, grn_hidden=8, dropout=0.0
        )
        x = torch.randn(4, 10, 28)
        selected, weights = vsn(x)
        assert selected.shape == (4, 10, 16)
        assert weights.shape == (4, 10, 28)

    def test_weights_sum_to_one(self):
        vsn = VariableSelectionNetwork(
            n_vars=28, hidden_size=16, grn_hidden=8, dropout=0.0
        )
        x = torch.randn(2, 5, 28)
        _, weights = vsn(x)
        weight_sums = weights.sum(dim=-1)
        assert torch.allclose(weight_sums, torch.ones_like(weight_sums), atol=1e-5)


class TestTFTModel:
    def test_forward_shape(self, model, sample_input):
        out = model(sample_input)
        assert out.shape == (4, 3)  # (batch, n_horizons)

    def test_output_is_continuous(self, model, sample_input):
        """Output should be continuous return predictions, not bounded."""
        out = model(sample_input)
        # Returns can be any real number
        assert out.dtype == torch.float32

    def test_variable_importance_shape(self, model, sample_input):
        importance = model.get_variable_importance(sample_input)
        assert importance.shape == (28,)  # one weight per variable

    def test_attention_weights_shape(self, model, sample_input):
        attn = model.get_attention_weights(sample_input)
        # (batch, lookback, lookback) for single-head avg, or may vary
        assert attn.shape[0] == 4
        assert attn.shape[1] == 10  # lookback

    def test_save_load_roundtrip(self, model, tft_config, sample_input, tmp_path):
        save_dir = tmp_path / "tft_test"
        model.save(save_dir)

        assert (save_dir / "model.pt").exists()
        assert (save_dir / "config.json").exists()

        loaded = TFTModel.load(save_dir)
        assert loaded.config.hidden_size == tft_config.hidden_size
        assert loaded.config.horizons == tft_config.horizons

        # Verify inference works and produces same output
        model.eval()
        loaded.eval()
        with torch.no_grad():
            orig_out = model(sample_input)
            loaded_out = loaded(sample_input)
        assert torch.allclose(orig_out, loaded_out, atol=1e-5)

    def test_gradient_flow(self, model, sample_input):
        """Verify gradients flow through all components."""
        model.train()
        out = model(sample_input)
        loss = out.sum()
        loss.backward()

        # Check that all parameters got gradients
        for name, param in model.named_parameters():
            if param.requires_grad:
                assert param.grad is not None, f"No gradient for {name}"


class TestTFTModelClassification:
    """Classification mode tests."""

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
        )

    @pytest.fixture
    def cls_model(self, cls_config):
        return TFTModel(cls_config)

    @pytest.fixture
    def cls_input(self, cls_config):
        return torch.randn(4, cls_config.lookback, cls_config.total_input_dim)

    def test_classification_forward_shape(self, cls_model, cls_input):
        """Classification mode outputs logits with same shape as regression."""
        out = cls_model(cls_input)
        assert out.shape == (4, 3)  # (batch, n_horizons)

    def test_predict_direction_probs_batch(self, cls_model, cls_input):
        """predict_direction_probs returns probabilities in [0, 1]."""
        probs = cls_model.predict_direction_probs(cls_input)
        assert probs.shape == (4, 3)
        assert np.all(probs >= 0.0)
        assert np.all(probs <= 1.0)

    def test_predict_direction_probs_single(self, cls_model, cls_config):
        """predict_direction_probs works with single (unbatched) input."""
        x = torch.randn(cls_config.lookback, cls_config.total_input_dim)
        probs = cls_model.predict_direction_probs(x)
        assert probs.shape == (3,)
        assert np.all(probs >= 0.0)
        assert np.all(probs <= 1.0)

    def test_predict_direction_probs_numpy_input(self, cls_model, cls_config):
        """predict_direction_probs accepts numpy array input."""
        x = np.random.randn(cls_config.lookback, cls_config.total_input_dim).astype(
            np.float32
        )
        probs = cls_model.predict_direction_probs(x)
        assert probs.shape == (3,)
        assert np.all(probs >= 0.0)
        assert np.all(probs <= 1.0)

    def test_classification_bce_loss_backward(self, cls_model, cls_input):
        """BCEWithLogitsLoss should work with classification model output."""
        cls_model.train()
        logits = cls_model(cls_input)
        targets = torch.randint(0, 2, (4, 3)).float()
        loss = torch.nn.BCEWithLogitsLoss()(logits, targets)
        loss.backward()

        for name, param in cls_model.named_parameters():
            if param.requires_grad:
                assert param.grad is not None, f"No gradient for {name}"

    def test_save_load_preserves_mode(self, cls_model, cls_config, tmp_path):
        """Save/load roundtrip should preserve mode in config."""
        save_dir = tmp_path / "tft_cls_test"
        cls_model.save(save_dir)

        loaded = TFTModel.load(save_dir)
        assert loaded.config.mode == "classification"
