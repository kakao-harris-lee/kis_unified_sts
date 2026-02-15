"""Temporal Fusion Transformer for futures return prediction

Multi-horizon return forecasting (1/5/15 min).
Custom PyTorch implementation: VSN + GRN + LSTM + MultiHeadAttention.

Usage:
    trainer = TFTTrainer()
    model = trainer.train(train_features, train_prices, eval_features, eval_prices)

    model = TFTModel.load("models/futures/tft/tft_best")
    preds = model.predict(features)  # (3,) → [ret_1m, ret_5m, ret_15m]
"""

from shared.ml.tft.model import TFTConfig, TFTModel
from shared.ml.tft.dataset import TFTDataset
from shared.ml.tft.trainer import TFTTrainer

__all__ = ["TFTConfig", "TFTModel", "TFTDataset", "TFTTrainer"]
