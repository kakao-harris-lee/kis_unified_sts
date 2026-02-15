"""TFT 학습 파이프라인

MSE/Huber loss로 다중 지평 수익률 예측.
AdamW + CosineAnnealing + Warmup + Gradient Clipping.
평가: MSE, MAE, 방향 정확도, IC, 단순 트레이딩 Sharpe.

Usage:
    trainer = TFTTrainer()
    model = trainer.train(train_features, train_prices, eval_features, eval_prices)
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from shared.config import ConfigLoader
from shared.ml.base import get_device
from shared.ml.tft.dataset import TFTDataset
from shared.ml.tft.model import TFTConfig, TFTModel

logger = logging.getLogger(__name__)


class TFTTrainer:
    """TFT 학습기

    모든 하이퍼파라미터는 YAML 설정에서 로드.
    """

    def __init__(
        self,
        config_path: str = "ml/tft.yaml",
        mode_override: str | None = None,
    ):
        self.config_path = config_path
        self.config = ConfigLoader.load(config_path)
        self.tft_config = TFTConfig.from_yaml(config_path)

        # mode override (CLI --mode)
        if mode_override is not None:
            self.tft_config.mode = mode_override

        self.mode = self.tft_config.mode

        tft_training = self.config.get("tft_training", {})
        self.lr = tft_training.get("learning_rate", 0.001)
        self.weight_decay = tft_training.get("weight_decay", 0.0001)
        self.warmup_steps = tft_training.get("warmup_steps", 500)
        self.max_epochs = tft_training.get("max_epochs", 50)
        self.batch_size = tft_training.get("batch_size", 256)
        self.grad_clip = tft_training.get("grad_clip", 1.0)
        self.eval_interval = tft_training.get("eval_interval", 5)
        self.patience = tft_training.get("patience", 10)

        training_cfg = self.config.get("training", {})
        self.save_dir = Path(training_cfg.get("save_dir", "./models/futures/tft/"))
        self.save_dir.mkdir(parents=True, exist_ok=True)

        self.device = get_device("auto")

    def train(
        self,
        train_features: list[np.ndarray],
        train_prices: list[np.ndarray],
        eval_features: list[np.ndarray] | None = None,
        eval_prices: list[np.ndarray] | None = None,
    ) -> TFTModel:
        """TFT 학습

        Args:
            train_features: 학습 피처 (일별), 각 (n_bars, 25)
            train_prices: 학습 가격 (일별), 각 (n_bars, 4) OHLC
            eval_features: 평가 피처
            eval_prices: 평가 가격

        Returns:
            학습된 TFTModel
        """
        logger.info(
            f"Starting TFT training ({self.mode}): "
            f"epochs={self.max_epochs}, lr={self.lr}, batch={self.batch_size}"
        )

        # Dataset + DataLoader
        ds_kwargs = dict(
            lookback=self.tft_config.lookback,
            horizons=self.tft_config.horizons,
            mode=self.mode,
            classification_threshold=self.tft_config.classification_threshold,
        )
        train_dataset = TFTDataset(train_features, train_prices, **ds_kwargs)
        train_loader = DataLoader(
            train_dataset,
            batch_size=self.batch_size,
            shuffle=True,
            drop_last=True,
            num_workers=0,
        )

        eval_loader = None
        if eval_features is not None and eval_prices is not None:
            eval_dataset = TFTDataset(eval_features, eval_prices, **ds_kwargs)
            if len(eval_dataset) > 0:
                eval_loader = DataLoader(
                    eval_dataset,
                    batch_size=self.batch_size,
                    shuffle=False,
                    num_workers=0,
                )

        # 모델 생성
        model = TFTModel(self.tft_config).to(self.device)
        model.train()

        # Optimizer + Scheduler
        optimizer = torch.optim.AdamW(
            model.parameters(), lr=self.lr, weight_decay=self.weight_decay,
        )
        total_steps = self.max_epochs * len(train_loader)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=max(total_steps, 1),
        )

        warmup_scheduler = None
        if self.warmup_steps > 0:
            warmup_scheduler = torch.optim.lr_scheduler.LinearLR(
                optimizer, start_factor=0.01, total_iters=self.warmup_steps,
            )

        if self.mode == "classification":
            loss_fn = nn.BCEWithLogitsLoss()
        else:
            loss_fn = nn.HuberLoss(delta=0.01)  # Robust to return outliers

        # Training loop
        best_eval_loss = float("inf")
        best_state_dict = None
        patience_counter = 0
        global_step = 0

        for epoch in range(1, self.max_epochs + 1):
            train_loss = self._train_epoch(
                model, train_loader, optimizer, scheduler, warmup_scheduler,
                loss_fn, global_step,
            )
            global_step += len(train_loader)

            log_msg = f"Epoch {epoch}/{self.max_epochs} | Train loss: {train_loss:.6f}"

            # Eval (offline)
            eval_loss = None
            eval_metrics = None
            if eval_loader is not None:
                eval_loss, eval_metrics = self._eval_metrics(model, eval_loader)
                log_msg += f" | Eval loss: {eval_loss:.6f}"
                if self.mode == "classification":
                    log_msg += (
                        f" | Acc: {eval_metrics['accuracy_avg']:.1f}%"
                        f" | AUC: {eval_metrics.get('auc_avg', 0):.3f}"
                    )
                else:
                    log_msg += (
                        f" | DirAcc: {eval_metrics['dir_acc_avg']:.1f}%"
                        f" | IC: {eval_metrics['ic_avg']:.3f}"
                    )

            # Trading evaluation
            if (
                epoch % self.eval_interval == 0
                and eval_features is not None
                and eval_prices is not None
            ):
                trading_metrics = self._eval_trading(
                    model, eval_features, eval_prices,
                )
                log_msg += (
                    f" | Sharpe: {trading_metrics['sharpe']:.2f}"
                    f" | WR: {trading_metrics['win_rate']:.1f}%"
                    f" | Trades: {trading_metrics['total_trades']}"
                )

            logger.info(log_msg)

            # Early stopping
            check_loss = eval_loss if eval_loss is not None else train_loss
            if check_loss < best_eval_loss:
                best_eval_loss = check_loss
                best_state_dict = copy.deepcopy(model.state_dict())
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= self.patience:
                    logger.info(f"Early stopping at epoch {epoch}")
                    break

        # Best model 복원
        if best_state_dict is not None:
            model.load_state_dict(best_state_dict)

        model.eval()

        # 저장 — best
        if self.mode == "classification":
            best_path = self.save_dir / "tft_cls_best"
        else:
            best_path = self.save_dir / "tft_best"
        model.save(best_path)
        logger.info(f"TFT training complete ({self.mode}). Best model saved: {best_path}")

        # Final evaluation
        if eval_features is not None and eval_prices is not None:
            final_metrics = self._eval_trading(model, eval_features, eval_prices)
            logger.info(
                f"Final trading eval: Sharpe={final_metrics['sharpe']:.2f}, "
                f"WR={final_metrics['win_rate']:.1f}%, "
                f"Trades={final_metrics['total_trades']}, "
                f"Return={final_metrics['total_return_pct']:.2f}%"
            )

        # MLflow 로깅
        self._log_mlflow(best_eval_loss)

        return model

    def _train_epoch(
        self,
        model: TFTModel,
        loader: DataLoader,
        optimizer: torch.optim.Optimizer,
        scheduler: Any,
        warmup_scheduler: Any,
        loss_fn: nn.Module,
        global_step: int,
    ) -> float:
        """1 에폭 학습"""
        model.train()
        total_loss = 0.0
        n_batches = 0

        label_smoothing = self.tft_config.label_smoothing
        is_cls = self.tft_config.mode == "classification"

        for x, y in loader:
            x = x.to(self.device)  # (B, lookback, 28)
            y = y.to(self.device)  # (B, n_horizons)

            # Label smoothing for classification
            if is_cls and label_smoothing > 0:
                y = y * (1 - label_smoothing) + 0.5 * label_smoothing

            preds = model(x)  # (B, n_horizons)
            loss = loss_fn(preds, y)

            optimizer.zero_grad()
            loss.backward()

            if self.grad_clip > 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), self.grad_clip)

            optimizer.step()

            # Scheduler step
            current_step = global_step + n_batches
            if warmup_scheduler is not None and current_step < self.warmup_steps:
                warmup_scheduler.step()
            else:
                scheduler.step()

            total_loss += loss.item()
            n_batches += 1

        return total_loss / max(n_batches, 1)

    @torch.no_grad()
    def _eval_metrics(
        self, model: TFTModel, loader: DataLoader,
    ) -> tuple[float, dict[str, float]]:
        """평가 지표 계산

        Returns:
            (eval_loss, metrics_dict)

        regression metrics_dict:
            mse_{h}m, mae_{h}m, dir_acc_{h}m, ic_{h}m, dir_acc_avg, ic_avg
        classification metrics_dict:
            accuracy_{h}m, auc_{h}m, f1_{h}m, calibration_{h}m,
            accuracy_avg, auc_avg
        """
        model.eval()
        all_preds = []
        all_targets = []
        total_loss = 0.0
        n_batches = 0

        if self.mode == "classification":
            loss_fn = nn.BCEWithLogitsLoss()
        else:
            loss_fn = nn.MSELoss()

        for x, y in loader:
            x = x.to(self.device)
            y = y.to(self.device)

            preds = model(x)
            loss = loss_fn(preds, y)

            total_loss += loss.item()
            n_batches += 1

            all_preds.append(preds.cpu().numpy())
            all_targets.append(y.cpu().numpy())

        eval_loss = total_loss / max(n_batches, 1)

        preds_arr = np.concatenate(all_preds, axis=0)
        targets_arr = np.concatenate(all_targets, axis=0)

        metrics: dict[str, float] = {}
        horizons = self.tft_config.horizons

        if self.mode == "classification":
            metrics = self._classification_metrics(preds_arr, targets_arr, horizons)
        else:
            metrics = self._regression_metrics(preds_arr, targets_arr, horizons)

        model.train()
        return eval_loss, metrics

    def _regression_metrics(
        self,
        preds_arr: np.ndarray,
        targets_arr: np.ndarray,
        horizons: list[int],
    ) -> dict[str, float]:
        """Regression-specific metrics."""
        metrics: dict[str, float] = {}
        dir_accs = []
        ics = []

        for h_idx, h in enumerate(horizons):
            p = preds_arr[:, h_idx]
            t = targets_arr[:, h_idx]

            mse = float(np.mean((p - t) ** 2))
            mae = float(np.mean(np.abs(p - t)))

            # 방향 정확도
            nonzero = np.abs(t) > 1e-10
            if nonzero.sum() > 0:
                dir_correct = np.mean(
                    (np.sign(p[nonzero]) == np.sign(t[nonzero])).astype(float)
                )
            else:
                dir_correct = 0.5
            dir_acc = float(dir_correct) * 100

            # IC (Pearson correlation)
            if np.std(p) > 1e-10 and np.std(t) > 1e-10:
                ic = float(np.corrcoef(p, t)[0, 1])
            else:
                ic = 0.0

            metrics[f"mse_{h}m"] = mse
            metrics[f"mae_{h}m"] = mae
            metrics[f"dir_acc_{h}m"] = dir_acc
            metrics[f"ic_{h}m"] = ic
            dir_accs.append(dir_acc)
            ics.append(ic)

        metrics["dir_acc_avg"] = float(np.mean(dir_accs))
        metrics["ic_avg"] = float(np.mean(ics))
        return metrics

    def _classification_metrics(
        self,
        logits_arr: np.ndarray,
        targets_arr: np.ndarray,
        horizons: list[int],
    ) -> dict[str, float]:
        """Classification-specific metrics: accuracy, AUC-ROC, F1, calibration."""
        from sklearn.metrics import f1_score, roc_auc_score

        metrics: dict[str, float] = {}
        accuracies = []
        aucs = []

        for h_idx, h in enumerate(horizons):
            logits = logits_arr[:, h_idx]
            targets = targets_arr[:, h_idx]  # 0/1 labels
            probs = 1.0 / (1.0 + np.exp(-logits))  # sigmoid

            predicted = (probs >= 0.5).astype(float)
            actual = (targets >= 0.5).astype(float)

            # Accuracy
            accuracy = float(np.mean(predicted == actual)) * 100
            accuracies.append(accuracy)

            # AUC-ROC
            n_pos = actual.sum()
            n_neg = len(actual) - n_pos
            if n_pos > 0 and n_neg > 0:
                auc = float(roc_auc_score(actual, probs))
            else:
                auc = 0.5
            aucs.append(auc)

            # F1
            f1 = float(f1_score(actual, predicted, zero_division=0.0))

            # Calibration: |mean(probs) - actual_up_ratio|
            actual_up_ratio = float(actual.mean())
            calibration = float(abs(probs.mean() - actual_up_ratio))

            # IC (prob vs actual direction)
            if np.std(probs) > 1e-10 and np.std(actual) > 1e-10:
                ic = float(np.corrcoef(probs, actual)[0, 1])
            else:
                ic = 0.0

            metrics[f"accuracy_{h}m"] = accuracy
            metrics[f"auc_{h}m"] = auc
            metrics[f"f1_{h}m"] = f1
            metrics[f"calibration_{h}m"] = calibration
            metrics[f"ic_{h}m"] = ic

        metrics["accuracy_avg"] = float(np.mean(accuracies))
        metrics["auc_avg"] = float(np.mean(aucs))
        return metrics

    @torch.no_grad()
    def _eval_trading(
        self,
        model: TFTModel,
        eval_features: list[np.ndarray],
        eval_prices: list[np.ndarray],
        threshold: float = 0.0001,
        commission: float = 0.00015,
    ) -> dict[str, float]:
        """단순 롱/숏 트레이딩 시뮬레이션

        regression: 15분 수익률 예측 기반. threshold 초과 시 진입.
        classification: prob > 0.55 → LONG, prob < 0.45 → SHORT.

        Args:
            model: TFT 모델
            eval_features: 평가 피처 (일별)
            eval_prices: 평가 가격 (일별)
            threshold: 진입 임계값 (regression 전용)
            commission: 편도 수수료율

        Returns:
            sharpe, win_rate, total_trades, total_return_pct
        """
        model.eval()
        from shared.ml.tft.dataset import compute_time_features

        lookback = self.tft_config.lookback
        horizons = self.tft_config.horizons
        h15_idx = horizons.index(15) if 15 in horizons else len(horizons) - 1
        is_cls = self.mode == "classification"

        daily_returns: list[float] = []
        total_trades = 0
        total_wins = 0

        for day_feat, day_prices in zip(eval_features, eval_prices):
            n_bars = len(day_feat)
            if n_bars < lookback + 15:
                continue

            time_feat = compute_time_features(n_bars)
            combined = np.concatenate([day_feat, time_feat], axis=1)
            close = day_prices[:, 3].astype(np.float64)

            day_pnl = 0.0

            t = lookback
            while t < n_bars - 15:
                x = combined[t - lookback : t]
                x_tensor = (
                    torch.from_numpy(x.astype(np.float32))
                    .unsqueeze(0)
                    .to(self.device)
                )
                pred = model(x_tensor).cpu().numpy()[0]
                pred_15m = pred[h15_idx]

                if is_cls:
                    prob = 1.0 / (1.0 + np.exp(-pred_15m))  # sigmoid
                    if prob > 0.55:
                        direction = 1.0
                    elif prob < 0.45:
                        direction = -1.0
                    else:
                        t += 1
                        continue
                else:
                    if abs(pred_15m) <= threshold:
                        t += 1
                        continue
                    direction = 1.0 if pred_15m > 0 else -1.0

                entry_price = close[t]
                exit_price = close[min(t + 15, n_bars - 1)]

                ret = direction * (exit_price - entry_price) / entry_price
                ret -= 2 * commission  # 왕복 수수료

                day_pnl += ret
                total_trades += 1
                if ret > 0:
                    total_wins += 1

                t += 15  # 포지션 유지 후 다음

            daily_returns.append(day_pnl)

        # Sharpe
        if len(daily_returns) >= 2 and np.std(daily_returns) > 0:
            sharpe = float(
                np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(252)
            )
        else:
            sharpe = 0.0

        win_rate = (total_wins / max(total_trades, 1)) * 100
        total_return_pct = float(np.sum(daily_returns)) * 100

        return {
            "sharpe": sharpe,
            "win_rate": win_rate,
            "total_trades": total_trades,
            "total_return_pct": total_return_pct,
        }

    def evaluate(
        self,
        model: TFTModel,
        eval_features: list[np.ndarray],
        eval_prices: list[np.ndarray],
    ) -> dict[str, Any]:
        """전체 평가 (예측 + 트레이딩)

        Returns:
            prediction_metrics + trading_metrics + baseline
        """
        # 예측 지표
        eval_dataset = TFTDataset(
            eval_features, eval_prices,
            lookback=self.tft_config.lookback,
            horizons=self.tft_config.horizons,
            mode=self.mode,
            classification_threshold=self.tft_config.classification_threshold,
        )
        eval_loader = DataLoader(
            eval_dataset,
            batch_size=self.batch_size,
            shuffle=False,
            num_workers=0,
        )
        _, pred_metrics = self._eval_metrics(model, eval_loader)

        # 트레이딩 지표
        trading_metrics = self._eval_trading(model, eval_features, eval_prices)

        # Naive baseline (last return → future return 예측)
        baseline = self._eval_naive_baseline(eval_features, eval_prices)

        return {
            "prediction": pred_metrics,
            "trading": trading_metrics,
            "baseline_naive": baseline,
        }

    def _eval_naive_baseline(
        self,
        eval_features: list[np.ndarray],
        eval_prices: list[np.ndarray],
    ) -> dict[str, float]:
        """Naive baseline: 직전 수익률로 미래 수익률 예측"""
        horizons = self.tft_config.horizons
        max_h = max(horizons)

        all_naive = {h: [] for h in horizons}
        all_actual = {h: [] for h in horizons}

        for day_feat, day_prices in zip(eval_features, eval_prices):
            n_bars = len(day_feat)
            close = day_prices[:, 3].astype(np.float64)

            for t in range(1, n_bars - max_h):
                last_ret = (close[t] - close[t - 1]) / close[t - 1]
                for h in horizons:
                    actual = (close[t + h] - close[t]) / close[t]
                    all_naive[h].append(last_ret)
                    all_actual[h].append(actual)

        metrics: dict[str, float] = {}
        for h in horizons:
            naive = np.array(all_naive[h])
            actual = np.array(all_actual[h])
            if len(naive) == 0:
                continue

            mse = float(np.mean((naive - actual) ** 2))
            nonzero = np.abs(actual) > 1e-10
            if nonzero.sum() > 0:
                dir_acc = float(
                    np.mean(
                        (np.sign(naive[nonzero]) == np.sign(actual[nonzero]))
                        .astype(float)
                    )
                ) * 100
            else:
                dir_acc = 50.0

            metrics[f"naive_mse_{h}m"] = mse
            metrics[f"naive_dir_acc_{h}m"] = dir_acc

        return metrics

    def _log_mlflow(self, best_loss: float) -> None:
        """MLflow 로깅"""
        try:
            import mlflow

            mlflow.set_experiment("tft")
            run_name = f"tft_{self.mode}"
            with mlflow.start_run(run_name=run_name):
                mlflow.log_params({
                    "algo": "tft",
                    "mode": self.mode,
                    "hidden_size": self.tft_config.hidden_size,
                    "lstm_layers": self.tft_config.lstm_layers,
                    "n_heads": self.tft_config.n_heads,
                    "lookback": self.tft_config.lookback,
                    "horizons": str(self.tft_config.horizons),
                    "learning_rate": self.lr,
                    "batch_size": self.batch_size,
                    "max_epochs": self.max_epochs,
                })
                mlflow.log_metric("best_loss", best_loss)
        except (ImportError, Exception) as e:
            logger.debug(f"MLflow logging skipped: {e}")
