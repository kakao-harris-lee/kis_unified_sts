#!/usr/bin/env python3
"""
CNN-LSTM 선물 가격 예측 모델 학습 스크립트

Usage:
    # 단일 모델 학습
    python scripts/training/train_futures_lstm.py --days 30 --epochs 100

    # 앙상블 모델 학습
    python scripts/training/train_futures_lstm.py --ensemble --horizons 1,3,5,10

    # CSV 파일로 학습
    python scripts/training/train_futures_lstm.py --csv data/ohlcv.csv --epochs 50
"""

import argparse
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# PyTorch imports (optional)
try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

# ClickHouse imports (optional)
try:
    import clickhouse_connect

    CLICKHOUSE_AVAILABLE = True
except ImportError:
    CLICKHOUSE_AVAILABLE = False

# Add project root to path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.ml.models import TradingCNNLSTM
from shared.ml.base import get_device, ModelMetadata, ScalerParams
from domains.futures.prediction.features import FeatureCalculator, FEATURE_COLUMNS

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Constants
MODELS_DIR = Path(__file__).resolve().parents[2] / "models" / "futures"


class ClickHouseDataLoader:
    """ClickHouse에서 OHLCV 데이터 로드"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8123,
        database: str = "default",
        table: str = "kospi_mini_1m",
    ):
        if not CLICKHOUSE_AVAILABLE:
            raise ImportError("clickhouse-connect package required")

        self.client = clickhouse_connect.get_client(
            host=host, port=port, database=database
        )
        self.table = table

    def load(self, days: int = 30) -> pd.DataFrame:
        """최근 N일 데이터 로드"""
        query = f"""
        SELECT
            datetime,
            open,
            high,
            low,
            close,
            volume
        FROM {self.table}
        WHERE datetime >= now() - INTERVAL {days} DAY
        ORDER BY datetime
        """
        result = self.client.query(query)
        df = pd.DataFrame(result.result_rows, columns=result.column_names)
        df["datetime"] = pd.to_datetime(df["datetime"])
        df.set_index("datetime", inplace=True)
        logger.info(f"Loaded {len(df)} rows from ClickHouse")
        return df


def load_data_from_csv(csv_path: str) -> pd.DataFrame:
    """CSV 파일에서 OHLCV 데이터 로드"""
    df = pd.read_csv(csv_path)

    # datetime 컬럼 처리
    if "datetime" in df.columns:
        df["datetime"] = pd.to_datetime(df["datetime"])
        df.set_index("datetime", inplace=True)
    elif "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)

    logger.info(f"Loaded {len(df)} rows from {csv_path}")
    return df


def create_labels(df: pd.DataFrame, horizon: int = 5, threshold: float = 0.001) -> np.ndarray:
    """
    가격 변동 방향 라벨 생성

    Args:
        df: OHLCV DataFrame
        horizon: 예측 기간 (봉 개수)
        threshold: 변동폭 기준 (0.1% = 0.001)

    Returns:
        labels: 0=Hold, 1=Up, 2=Down
    """
    future_returns = df["close"].shift(-horizon) / df["close"] - 1

    labels = np.zeros(len(df), dtype=np.int64)
    labels[future_returns > threshold] = 1  # Up
    labels[future_returns < -threshold] = 2  # Down
    # else: 0 = Hold

    return labels


def prepare_sequences(
    features: np.ndarray, labels: np.ndarray, seq_len: int = 60
) -> tuple[np.ndarray, np.ndarray]:
    """
    시퀀스 데이터 생성

    Args:
        features: (N, num_features) 특성 배열
        labels: (N,) 라벨 배열
        seq_len: 시퀀스 길이

    Returns:
        X: (N-seq_len, seq_len, num_features)
        y: (N-seq_len,)
    """
    X, y = [], []
    for i in range(len(features) - seq_len):
        X.append(features[i : i + seq_len])
        y.append(labels[i + seq_len])

    return np.array(X), np.array(y)


def train_model(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    config: dict,
    device: torch.device,
) -> tuple[TradingCNNLSTM, float]:
    """
    모델 학습

    Args:
        X_train, y_train: 학습 데이터
        X_val, y_val: 검증 데이터
        config: 모델 하이퍼파라미터
        device: torch device

    Returns:
        model: 학습된 모델
        best_accuracy: 최고 검증 정확도
    """
    # TensorDataset 생성
    train_dataset = TensorDataset(
        torch.FloatTensor(X_train), torch.LongTensor(y_train)
    )
    val_dataset = TensorDataset(torch.FloatTensor(X_val), torch.LongTensor(y_val))

    train_loader = DataLoader(
        train_dataset, batch_size=config.get("batch_size", 64), shuffle=True
    )
    val_loader = DataLoader(val_dataset, batch_size=config.get("batch_size", 64))

    # 모델 생성
    model = TradingCNNLSTM(
        input_dim=config["input_dim"],
        hidden_dim=config.get("hidden_dim", 64),
        num_layers=config.get("num_layers", 2),
        num_classes=config.get("num_classes", 3),
        dropout=config.get("dropout", 0.2),
        cnn_channels=config.get("cnn_channels", [32, 64]),
        kernel_size=config.get("kernel_size", 3),
    ).to(device)

    # 클래스 불균형 처리를 위한 가중치 계산
    class_counts = np.bincount(y_train, minlength=3)
    class_weights = 1.0 / (class_counts + 1e-6)
    class_weights = class_weights / class_weights.sum() * len(class_weights)
    class_weights = torch.FloatTensor(class_weights).to(device)

    criterion = nn.CrossEntropyLoss(weight=class_weights)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.get("learning_rate", 0.001),
        weight_decay=config.get("weight_decay", 0.01),
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="max", factor=0.5, patience=5
    )

    # 학습 루프
    best_accuracy = 0.0
    patience_counter = 0
    early_stopping_patience = config.get("early_stopping_patience", 15)

    epochs = config.get("epochs", 100)
    for epoch in range(epochs):
        # Training
        model.train()
        train_loss = 0.0
        for X_batch, y_batch in train_loader:
            X_batch, y_batch = X_batch.to(device), y_batch.to(device)

            optimizer.zero_grad()
            outputs = model(X_batch)
            loss = criterion(outputs, y_batch)
            loss.backward()

            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

            optimizer.step()
            train_loss += loss.item()

        train_loss /= len(train_loader)

        # Validation
        model.eval()
        correct = 0
        total = 0
        with torch.no_grad():
            for X_batch, y_batch in val_loader:
                X_batch, y_batch = X_batch.to(device), y_batch.to(device)
                outputs = model(X_batch)
                _, predicted = torch.max(outputs, 1)
                total += y_batch.size(0)
                correct += (predicted == y_batch).sum().item()

        val_accuracy = correct / total
        scheduler.step(val_accuracy)

        if (epoch + 1) % 10 == 0 or epoch == 0:
            logger.info(
                f"Epoch {epoch + 1}/{epochs} - "
                f"Loss: {train_loss:.4f}, Val Acc: {val_accuracy:.4f}"
            )

        # Early stopping
        if val_accuracy > best_accuracy:
            best_accuracy = val_accuracy
            patience_counter = 0
            # Save best model state
            best_state = model.state_dict().copy()
        else:
            patience_counter += 1
            if patience_counter >= early_stopping_patience:
                logger.info(f"Early stopping at epoch {epoch + 1}")
                break

    # Restore best model
    if "best_state" in locals():
        model.load_state_dict(best_state)

    return model, best_accuracy


def save_model(
    model: TradingCNNLSTM,
    scaler_mean: np.ndarray,
    scaler_scale: np.ndarray,
    config: dict,
    accuracy: float,
    training_samples: int,
    output_path: Path,
    horizon: Optional[int] = None,
):
    """모델 및 메타데이터 저장"""
    output_path.mkdir(parents=True, exist_ok=True)

    # 파일명 결정
    if horizon is not None:
        model_name = f"model_h{horizon}"
    else:
        model_name = "trading_lstm"

    # 모델 가중치 저장
    model_path = output_path / f"{model_name}.pth"
    torch.save(model.state_dict(), model_path)
    logger.info(f"Model saved to {model_path}")

    # 메타데이터 저장
    metadata = {
        "model_type": "cnn-lstm",
        "input_dim": config["input_dim"],
        "hidden_dim": config.get("hidden_dim", 64),
        "num_layers": config.get("num_layers", 2),
        "num_classes": config.get("num_classes", 3),
        "dropout": config.get("dropout", 0.2),
        "cnn_channels": config.get("cnn_channels", [32, 64]),
        "kernel_size": config.get("kernel_size", 3),
        "seq_len": config.get("seq_len", 60),
        "version": "1.0.0",
        "feature_columns": FEATURE_COLUMNS,
        "trained_at": datetime.now().isoformat(),
        "training_samples": training_samples,
        "validation_accuracy": accuracy,
    }
    if horizon is not None:
        metadata["horizon"] = horizon

    metadata_path = output_path / f"{model_name}.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"Metadata saved to {metadata_path}")

    # Scaler 저장 (단일 모델일 때만)
    if horizon is None:
        scaler_data = {
            "mean": scaler_mean.tolist(),
            "scale": scaler_scale.tolist(),
        }
        scaler_path = output_path / "scaler.json"
        with open(scaler_path, "w") as f:
            json.dump(scaler_data, f, indent=2)
        logger.info(f"Scaler saved to {scaler_path}")


def main():
    parser = argparse.ArgumentParser(description="Train CNN-LSTM futures prediction model")
    parser.add_argument("--days", type=int, default=30, help="Days of data to use")
    parser.add_argument("--epochs", type=int, default=100, help="Training epochs")
    parser.add_argument("--csv", type=str, help="CSV file path (alternative to ClickHouse)")
    parser.add_argument("--ensemble", action="store_true", help="Train ensemble models")
    parser.add_argument(
        "--horizons",
        type=str,
        default="1,3,5,10",
        help="Comma-separated horizons for ensemble",
    )
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--seq-len", type=int, default=60)
    parser.add_argument("--threshold", type=float, default=0.001, help="Label threshold")

    args = parser.parse_args()

    if not TORCH_AVAILABLE:
        logger.error("PyTorch is required. Install with: pip install torch")
        sys.exit(1)

    # 데이터 로드
    if args.csv:
        df = load_data_from_csv(args.csv)
    elif CLICKHOUSE_AVAILABLE:
        loader = ClickHouseDataLoader()
        df = loader.load(days=args.days)
    else:
        logger.error("Either --csv or ClickHouse connection required")
        sys.exit(1)

    # 특성 계산
    calculator = FeatureCalculator()
    features_df = calculator.calculate_features(df)
    features_df = features_df.dropna()

    features = features_df[FEATURE_COLUMNS].values.astype(np.float32)

    # 정규화
    scaler_mean = features.mean(axis=0)
    scaler_scale = features.std(axis=0) + 1e-8
    features_normalized = (features - scaler_mean) / scaler_scale

    # 디바이스 설정
    device = get_device()
    logger.info(f"Using device: {device}")

    # 기본 설정
    config = {
        "input_dim": len(FEATURE_COLUMNS),
        "hidden_dim": args.hidden_dim,
        "num_layers": 2,
        "num_classes": 3,
        "dropout": 0.2,
        "cnn_channels": [32, 64],
        "kernel_size": 3,
        "seq_len": args.seq_len,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "epochs": args.epochs,
        "early_stopping_patience": 15,
    }

    if args.ensemble:
        # 앙상블 모델 학습
        horizons = [int(h) for h in args.horizons.split(",")]
        logger.info(f"Training ensemble models for horizons: {horizons}")

        for horizon in horizons:
            logger.info(f"\n{'='*50}")
            logger.info(f"Training model for horizon={horizon}")
            logger.info("=" * 50)

            # 라벨 생성
            labels = create_labels(features_df, horizon=horizon, threshold=args.threshold)

            # 시퀀스 생성
            X, y = prepare_sequences(features_normalized, labels, seq_len=args.seq_len)

            # 학습/검증 분할 (시계열이므로 순서 유지)
            split_idx = int(len(X) * 0.8)
            X_train, X_val = X[:split_idx], X[split_idx:]
            y_train, y_val = y[:split_idx], y[split_idx:]

            logger.info(f"Training samples: {len(X_train)}, Validation samples: {len(X_val)}")

            # 학습
            model, accuracy = train_model(X_train, y_train, X_val, y_val, config, device)
            logger.info(f"Horizon {horizon} - Best validation accuracy: {accuracy:.4f}")

            # 저장
            save_model(
                model,
                scaler_mean,
                scaler_scale,
                config,
                accuracy,
                len(X_train),
                MODELS_DIR / "ensemble",
                horizon=horizon,
            )

        # Scaler는 한 번만 저장
        scaler_data = {"mean": scaler_mean.tolist(), "scale": scaler_scale.tolist()}
        scaler_path = MODELS_DIR / "scaler.json"
        with open(scaler_path, "w") as f:
            json.dump(scaler_data, f, indent=2)
        logger.info(f"Scaler saved to {scaler_path}")

    else:
        # 단일 모델 학습
        horizon = 5  # 기본 예측 기간
        labels = create_labels(features_df, horizon=horizon, threshold=args.threshold)

        # 시퀀스 생성
        X, y = prepare_sequences(features_normalized, labels, seq_len=args.seq_len)

        # 학습/검증 분할
        split_idx = int(len(X) * 0.8)
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]

        logger.info(f"Training samples: {len(X_train)}, Validation samples: {len(X_val)}")

        # 클래스 분포 확인
        class_dist = np.bincount(y_train, minlength=3)
        logger.info(f"Class distribution - Hold: {class_dist[0]}, Up: {class_dist[1]}, Down: {class_dist[2]}")

        # 학습
        model, accuracy = train_model(X_train, y_train, X_val, y_val, config, device)
        logger.info(f"Best validation accuracy: {accuracy:.4f}")

        # 저장
        save_model(
            model,
            scaler_mean,
            scaler_scale,
            config,
            accuracy,
            len(X_train),
            MODELS_DIR,
        )

    logger.info("\nTraining completed!")


if __name__ == "__main__":
    main()
