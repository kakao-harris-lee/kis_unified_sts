"""Decision Transformer 학습 파이프라인

CrossEntropyLoss로 모든 timestep에서 action 예측.
AdamW + cosine scheduler + gradient clipping.
Online evaluation: FuturesTradingEnv에서 DTAgent 실행.

Usage:
    trainer = DTTrainer()
    trainer.train(train_trajs, eval_trajs, eval_days, eval_prices)
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
from shared.ml.rl.decision_transformer.dataset import TrajectoryDataset
from shared.ml.rl.decision_transformer.model import DTAgent, DTConfig
from shared.ml.rl.env import Action, FuturesTradingEnv, RLEnvConfig

logger = logging.getLogger(__name__)


class DTTrainer:
    """Decision Transformer 학습기

    모든 하이퍼파라미터는 YAML 설정에서 로드.
    """

    def __init__(self, config_path: str = "ml/rl_dt.yaml"):
        self.config_path = config_path
        self.config = ConfigLoader.load(config_path)
        self.dt_config = DTConfig.from_yaml(config_path)
        self.env_config = RLEnvConfig.from_yaml(config_path)

        dt_training = self.config.get("dt_training", {})
        self.lr = dt_training.get("learning_rate", 0.0001)
        self.weight_decay = dt_training.get("weight_decay", 0.0001)
        self.warmup_steps = dt_training.get("warmup_steps", 1000)
        self.max_epochs = dt_training.get("max_epochs", 50)
        self.batch_size = dt_training.get("batch_size", 64)
        self.grad_clip = dt_training.get("grad_clip", 0.25)
        self.eval_interval = dt_training.get("eval_interval", 5)
        self.patience = dt_training.get("patience", 10)

        training_cfg = self.config.get("training", {})
        self.save_dir = Path(training_cfg.get("save_dir", "./models/futures/rl/"))
        self.save_dir.mkdir(parents=True, exist_ok=True)

        self.device = get_device("auto")
        self.target_return = float(
            self.config.get("paper", {}).get("target_return", 5_000_000)
        )

    def train(
        self,
        train_trajs: list[dict[str, np.ndarray]],
        eval_trajs: list[dict[str, np.ndarray]] | None = None,
        eval_days: list[np.ndarray] | None = None,
        eval_prices: list[np.ndarray] | None = None,
    ) -> DTAgent:
        """DT 학습

        Args:
            train_trajs: 학습 궤적
            eval_trajs: 평가 궤적 (offline loss 평가용)
            eval_days: 온라인 평가 피처 데이터
            eval_prices: 온라인 평가 가격 데이터

        Returns:
            학습된 DTAgent
        """
        logger.info(
            f"Starting DT training: "
            f"epochs={self.max_epochs}, lr={self.lr}, batch={self.batch_size}"
        )

        # Dataset + DataLoader
        train_dataset = TrajectoryDataset(
            train_trajs,
            context_length=self.dt_config.context_length,
            act_dim=self.dt_config.act_dim,
        )
        train_loader = DataLoader(
            train_dataset,
            batch_size=self.batch_size,
            shuffle=True,
            drop_last=True,
            num_workers=0,
        )

        eval_loader = None
        if eval_trajs is not None and len(eval_trajs) > 0:
            eval_dataset = TrajectoryDataset(
                eval_trajs,
                context_length=self.dt_config.context_length,
                act_dim=self.dt_config.act_dim,
            )
            eval_loader = DataLoader(
                eval_dataset,
                batch_size=self.batch_size,
                shuffle=False,
                num_workers=0,
            )

        # 모델 생성
        agent = DTAgent(config=self.dt_config, device=self.device)
        model = agent.model
        model.train()

        # Optimizer + Scheduler
        optimizer = torch.optim.AdamW(
            model.parameters(), lr=self.lr, weight_decay=self.weight_decay,
        )
        total_steps = self.max_epochs * len(train_loader)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=max(total_steps, 1),
        )

        # Warmup (linear)
        warmup_scheduler = None
        if self.warmup_steps > 0:
            warmup_scheduler = torch.optim.lr_scheduler.LinearLR(
                optimizer, start_factor=0.01, total_iters=self.warmup_steps,
            )

        loss_fn = nn.CrossEntropyLoss()

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

            log_msg = f"Epoch {epoch}/{self.max_epochs} | Train loss: {train_loss:.4f}"

            # Eval (offline)
            eval_loss = None
            if eval_loader is not None:
                eval_loss = self._eval_loss(model, eval_loader, loss_fn)
                log_msg += f" | Eval loss: {eval_loss:.4f}"

            # Online evaluation
            if (
                epoch % self.eval_interval == 0
                and eval_days is not None
                and eval_prices is not None
            ):
                online_metrics = self._eval_online(agent, eval_days, eval_prices)
                log_msg += (
                    f" | Sharpe: {online_metrics['sharpe']:.2f}"
                    f" | WR: {online_metrics['win_rate']:.1f}%"
                    f" | Trades: {online_metrics['total_trades']}"
                )

            logger.info(log_msg)

            # Early stopping on eval loss (or train loss if no eval)
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

        agent.model.eval()

        # 저장
        save_path = self.save_dir / "dt_final"
        agent.save(save_path)
        logger.info(f"DT training complete. Model saved: {save_path}")

        # MLflow 로깅
        self._log_mlflow(best_eval_loss)

        return agent

    def _train_epoch(
        self,
        model: Any,
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

        for batch in loader:
            states = batch["states"].to(self.device)
            actions = batch["actions"].to(self.device)
            rewards = batch["rewards"].to(self.device)
            rtg = batch["returns_to_go"].to(self.device)
            timesteps = batch["timesteps"].to(self.device)
            attn_mask = batch["attention_mask"].to(self.device)
            targets = batch["target_actions"].to(self.device)

            output = model(
                states=states,
                actions=actions,
                rewards=rewards,
                returns_to_go=rtg,
                timesteps=timesteps,
                attention_mask=attn_mask,
            )

            # action_preds: (B, K, act_dim) → CE loss on all timesteps
            preds = output.action_preds  # (B, K, act_dim)
            B, K, A = preds.shape

            # Mask out padded positions
            mask_flat = attn_mask.reshape(-1).bool()  # (B*K,)
            preds_flat = preds.reshape(-1, A)[mask_flat]  # (N, act_dim)
            targets_flat = targets.reshape(-1)[mask_flat]  # (N,)

            loss = loss_fn(preds_flat, targets_flat)

            optimizer.zero_grad()
            loss.backward()

            # Gradient clipping
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
    def _eval_loss(
        self,
        model: Any,
        loader: DataLoader,
        loss_fn: nn.Module,
    ) -> float:
        """오프라인 평가 loss"""
        model.eval()
        total_loss = 0.0
        n_batches = 0

        for batch in loader:
            states = batch["states"].to(self.device)
            actions = batch["actions"].to(self.device)
            rewards = batch["rewards"].to(self.device)
            rtg = batch["returns_to_go"].to(self.device)
            timesteps = batch["timesteps"].to(self.device)
            attn_mask = batch["attention_mask"].to(self.device)
            targets = batch["target_actions"].to(self.device)

            output = model(
                states=states,
                actions=actions,
                rewards=rewards,
                returns_to_go=rtg,
                timesteps=timesteps,
                attention_mask=attn_mask,
            )

            preds = output.action_preds
            B, K, A = preds.shape
            mask_flat = attn_mask.reshape(-1).bool()
            preds_flat = preds.reshape(-1, A)[mask_flat]
            targets_flat = targets.reshape(-1)[mask_flat]

            loss = loss_fn(preds_flat, targets_flat)
            total_loss += loss.item()
            n_batches += 1

        model.train()
        return total_loss / max(n_batches, 1)

    def _eval_online(
        self,
        agent: DTAgent,
        eval_days: list[np.ndarray],
        eval_prices: list[np.ndarray],
    ) -> dict[str, float]:
        """온라인 평가: FuturesTradingEnv에서 DTAgent 실행"""
        agent.model.eval()

        daily_returns = []
        total_trades = 0
        total_wins = 0

        for day_data, day_prices in zip(eval_days, eval_prices):
            env = FuturesTradingEnv(
                day_data=day_data, config=self.env_config, prices=day_prices,
            )
            obs, _ = env.reset()
            agent.reset(target_return=self.target_return)

            terminated = False
            prev_reward = 0.0

            while not terminated:
                masks = env.action_masks()
                action_int, _ = agent.predict(
                    obs, action_masks=masks, reward=prev_reward, deterministic=True,
                )
                obs, reward, terminated, _, info = env.step(action_int)
                prev_reward = float(reward)

            daily_return = (
                (info["balance"] - self.env_config.initial_balance)
                / self.env_config.initial_balance
            )
            daily_returns.append(daily_return)
            total_trades += info["n_trades"]
            total_wins += env.wins

        # Sharpe
        if len(daily_returns) >= 2 and np.std(daily_returns) > 0:
            sharpe = float(np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(252))
        else:
            sharpe = 0.0

        win_rate = (total_wins / max(total_trades, 1)) * 100

        agent.model.train()
        return {
            "sharpe": sharpe,
            "win_rate": win_rate,
            "total_trades": total_trades,
            "avg_return": float(np.mean(daily_returns)) * 100 if daily_returns else 0.0,
        }

    def _log_mlflow(self, best_loss: float) -> None:
        """MLflow 로깅"""
        try:
            import mlflow

            mlflow.set_experiment("rl_dt")
            with mlflow.start_run(run_name="dt_training"):
                mlflow.log_params({
                    "algo": "dt",
                    "hidden_size": self.dt_config.hidden_size,
                    "n_layer": self.dt_config.n_layer,
                    "n_head": self.dt_config.n_head,
                    "context_length": self.dt_config.context_length,
                    "learning_rate": self.lr,
                    "batch_size": self.batch_size,
                    "max_epochs": self.max_epochs,
                })
                mlflow.log_metric("best_loss", best_loss)
        except (ImportError, Exception) as e:
            logger.debug(f"MLflow logging skipped: {e}")
