"""RL Model Retraining Pipeline

Automated pipeline that periodically retrains RL models on fresh data, validates
performance against baseline thresholds, and promotes winning models to production.
Implements champion/challenger pattern with automatic rollback capability.

Usage:
    pipeline = RetrainingPipeline()

    # Full retraining workflow
    result = pipeline.run()  # Train, evaluate, promote if better

    # Individual steps
    model = pipeline.train_challenger()
    comparison = pipeline.evaluate_models(challenger_model=model)
    pipeline.promote_if_better(comparison)

    # Rollback if needed
    pipeline.rollback_if_failed()
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from shared.config import ConfigLoader
from shared.ml.rl.champion_challenger import ChampionChallengerEvaluator
from shared.ml.rl.features import RLFeatureCalculator, RL_FEATURE_COLUMNS
from shared.ml.rl.model_registry import ModelRegistry
from shared.ml.rl.trainer import RLTrainer

logger = logging.getLogger(__name__)

# Optional imports
try:
    import mlflow
    from mlflow.exceptions import MlflowException

    HAS_MLFLOW = True
except ImportError:
    HAS_MLFLOW = False
    mlflow = None
    MlflowException = Exception


def _validate_ohlcv_quality(
    df: pd.DataFrame,
    *,
    symbol: str,
    table: str,
    max_zero_volume_ratio: float = 0.95,
    max_zero_volume_price_move_ratio: float = 0.20,
    reject_duplicate_datetime: bool = True,
    require_monotonic_datetime: bool = True,
) -> None:
    """Validate OHLCV integrity for RL training/evaluation inputs"""
    if df.empty:
        raise ValueError(f"Empty dataset: {table} ({symbol})")

    if "datetime" not in df.columns:
        raise ValueError("Missing required column: datetime")

    if reject_duplicate_datetime:
        duplicate_count = int(df["datetime"].duplicated().sum())
        if duplicate_count > 0:
            raise ValueError(
                f"Data quality check failed ({table}/{symbol}): "
                f"duplicated datetime rows={duplicate_count}"
            )

    if require_monotonic_datetime and not df["datetime"].is_monotonic_increasing:
        raise ValueError(
            f"Data quality check failed ({table}/{symbol}): "
            "datetime is not monotonic increasing"
        )

    if "volume" in df.columns:
        zero_volume_ratio = float((df["volume"] == 0).mean())
        if zero_volume_ratio > max_zero_volume_ratio:
            raise ValueError(
                f"Data quality check failed ({table}/{symbol}): "
                f"zero-volume ratio={zero_volume_ratio:.4f} > {max_zero_volume_ratio:.4f}"
            )

        if "close" in df.columns:
            close_diff = df["close"].diff().abs().fillna(0)
            phantom_ratio = float(((df["volume"] == 0) & (close_diff > 0)).mean())
            if phantom_ratio > max_zero_volume_price_move_ratio:
                raise ValueError(
                    f"Data quality check failed ({table}/{symbol}): "
                    "zero-volume moving-price ratio="
                    f"{phantom_ratio:.4f} > {max_zero_volume_price_move_ratio:.4f}"
                )


def _generate_sample_data(n_days: int = 60, bars_per_day: int = 405) -> pd.DataFrame:
    """Generate sample data (when ClickHouse is not available)"""
    np.random.seed(42)
    rows = []
    base_price = 350.0

    for day in range(n_days):
        price = base_price
        for bar in range(bars_per_day):
            dt = pd.Timestamp(
                f"2025-{1 + day // 22:02d}-{1 + day % 22:02d} "
                f"{9 + bar // 60:02d}:{bar % 60:02d}:00"
            )
            change = np.random.normal(0, 0.1)
            price += change
            high = price + abs(np.random.normal(0, 0.05))
            low = price - abs(np.random.normal(0, 0.05))
            volume = int(np.random.exponential(100))
            rows.append({
                "datetime": dt,
                "open": price - change * 0.5,
                "high": high,
                "low": low,
                "close": price,
                "volume": volume,
            })

    return pd.DataFrame(rows)


class RetrainingPipeline:
    """Automated RL model retraining and promotion pipeline

    Orchestrates the complete retraining workflow:
    1. Load fresh data from ClickHouse
    2. Train challenger model using RLTrainer
    3. Evaluate champion vs challenger using ChampionChallengerEvaluator
    4. Promote challenger if it meets thresholds
    5. Automatic rollback if promoted model underperforms

    All steps are logged to MLflow for full audit trail.
    """

    def __init__(self, config_path: str = "ml/retraining_pipeline.yaml"):
        """Initialize retraining pipeline

        Args:
            config_path: Path to retraining pipeline config file
        """
        self.config = ConfigLoader.load(config_path)

        # Extract config sections
        self.data_config = self.config.get("data", {})
        self.training_config = self.config.get("training", {})
        self.evaluation_config = self.config.get("evaluation", {})
        self.mlflow_config = self.config.get("mlflow", {})
        self.thresholds = self.config.get("thresholds", {})
        self.rollback_config = self.config.get("rollback", {})

        # Initialize components
        base_config = self.training_config.get("base_config", "ml/rl_mppo.yaml")
        self.trainer = RLTrainer(config_path=base_config)
        self.evaluator = ChampionChallengerEvaluator(config_path=config_path)

        model_name = self.mlflow_config.get("registered_model_name", "rl_mppo")
        self.registry = ModelRegistry(model_name=model_name)

        # Setup paths
        self.challenger_path = Path(
            self.training_config.get(
                "save_challenger_path",
                "./models/futures/rl/challenger/"
            )
        )
        self.challenger_path.mkdir(parents=True, exist_ok=True)

        # Initialize Telegram notifier
        self._notifier = None
        notification_config = self.config.get("notifications", {})
        telegram_config = notification_config.get("telegram", {})
        if telegram_config.get("enabled", False):
            try:
                from shared.notification.telegram import TelegramNotifier
                self._notifier = TelegramNotifier()
                logger.info("Telegram notifications enabled for retraining pipeline")
            except ImportError:
                logger.warning("python-telegram-bot not installed. Notifications disabled.")
            except Exception as e:
                logger.warning(f"Failed to initialize Telegram notifier: {e}")

        logger.info(f"RetrainingPipeline initialized with config: {config_path}")

    def run(
        self,
        train_days: list[np.ndarray] | None = None,
        train_prices: list[np.ndarray] | None = None,
        test_days: list[np.ndarray] | None = None,
        test_prices: list[np.ndarray] | None = None,
        train_aux: list[np.ndarray] | None = None,
        test_aux: list[np.ndarray] | None = None,
    ) -> dict[str, Any]:
        """Run complete retraining pipeline

        Executes full workflow: train challenger → evaluate → promote if better.
        Logs all steps to MLflow for audit trail.

        Args:
            train_days: Training data (daily features). If None, loads from ClickHouse
            train_prices: Training prices (daily OHLC)
            test_days: Test data for evaluation
            test_prices: Test prices
            train_aux: Auxiliary training features (e.g., TFT probs)
            test_aux: Auxiliary test features

        Returns:
            Dict with keys:
                - challenger_model: Trained model
                - comparison: Evaluation results
                - promoted: Whether challenger was promoted
                - run_id: MLflow run ID
        """
        logger.info("=" * 80)
        logger.info("Starting RL Model Retraining Pipeline")
        logger.info("=" * 80)

        # Start MLflow run for entire pipeline
        if HAS_MLFLOW:
            experiment_name = self.mlflow_config.get(
                "experiment_name",
                "rl_retraining_pipeline"
            )
            mlflow.set_experiment(experiment_name)
            run = mlflow.start_run(run_name=f"retraining_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            run_id = run.info.run_id
            logger.info(f"MLflow run started: {run_id}")
        else:
            run_id = None

        try:
            # Step 1: Load data if not provided
            if train_days is None or train_prices is None:
                logger.info("Loading data from ClickHouse...")
                train_days, train_prices, test_days, test_prices = self._load_data()
                logger.info(
                    f"Loaded {len(train_days)} training days, "
                    f"{len(test_days) if test_days else 0} test days"
                )

            # Extract date ranges for audit trail
            train_start, train_end = self._extract_date_range(train_days, train_prices)
            test_start, test_end = self._extract_date_range(
                test_days if test_days else [],
                test_prices if test_prices else []
            )

            logger.info(f"Training data: {train_start} to {train_end} ({len(train_days)} days)")
            logger.info(f"Test data: {test_start} to {test_end} ({len(test_days) if test_days else 0} days)")

            # Step 2: Train challenger model
            logger.info("Step 1/3: Training challenger model...")
            challenger_model = self.train_challenger(
                train_days=train_days,
                train_prices=train_prices,
                train_aux=train_aux,
            )

            # Step 3: Evaluate models
            logger.info("Step 2/3: Evaluating champion vs challenger...")
            comparison = self.evaluate_models(
                challenger_model=challenger_model,
                test_days=test_days,
                test_prices=test_prices,
                test_aux=test_aux,
            )

            # Step 4: Promote if better
            logger.info("Step 3/3: Making promotion decision...")
            promoted = self.promote_if_better(comparison)

            # Log final results
            result = {
                "challenger_model": challenger_model,
                "comparison": comparison,
                "promoted": promoted,
                "run_id": run_id,
            }

            if HAS_MLFLOW:
                # Log comprehensive parameters for audit trail
                git_sha = self._get_git_sha()
                mlflow.log_params({
                    "git_sha": git_sha,
                    "pipeline_timestamp": datetime.now().isoformat(),
                    "train_days_count": len(train_days),
                    "test_days_count": len(test_days) if test_days else 0,
                    "train_data_start": train_start,
                    "train_data_end": train_end,
                    "test_data_start": test_start,
                    "test_data_end": test_end,
                    "promoted": promoted,
                    "promotion_reason": comparison.get("reason", "unknown"),
                })

                # Log challenger metrics
                challenger_metrics = comparison.get("challenger", {})
                if challenger_metrics:
                    mlflow.log_metrics({
                        "challenger_sharpe": challenger_metrics.get("sharpe_ratio", 0.0),
                        "challenger_win_rate": challenger_metrics.get("win_rate_pct", 0.0),
                        "challenger_max_dd": challenger_metrics.get("max_drawdown_pct", 0.0),
                        "challenger_total_trades": challenger_metrics.get("total_trades", 0),
                        "challenger_profit_factor": challenger_metrics.get("profit_factor", 0.0),
                    })

                # Log champion metrics if available
                champion_metrics = comparison.get("champion")
                if champion_metrics:
                    mlflow.log_metrics({
                        "champion_sharpe": champion_metrics.get("sharpe_ratio", 0.0),
                        "champion_win_rate": champion_metrics.get("win_rate_pct", 0.0),
                        "champion_max_dd": champion_metrics.get("max_drawdown_pct", 0.0),
                    })

                    # Log improvement metrics
                    improvement = comparison.get("improvement", {})
                    if improvement:
                        mlflow.log_metrics({
                            "sharpe_improvement": improvement.get("sharpe_improvement", 0.0),
                            "win_rate_improvement": improvement.get("win_rate_improvement", 0.0),
                            "max_dd_improvement": improvement.get("max_dd_improvement", 0.0),
                        })

                # Log comparison as artifact for full audit trail
                self._log_comparison_artifact(comparison, "pipeline_comparison.json")

            logger.info("=" * 80)
            if promoted:
                logger.info("✓ Retraining pipeline completed: Challenger PROMOTED")
            else:
                logger.info("✓ Retraining pipeline completed: Promotion REJECTED")
            logger.info("=" * 80)

            return result

        except Exception as e:
            logger.error(f"Retraining pipeline failed: {e}", exc_info=True)
            if HAS_MLFLOW:
                mlflow.log_param("pipeline_status", "failed")
                mlflow.log_param("failure_reason", str(e))

            # Send training failure notification
            self._send_training_failure_notification(
                error=e,
                stage="retraining_pipeline",
            )
            raise
        finally:
            if HAS_MLFLOW:
                mlflow.end_run()

    def train_challenger(
        self,
        train_days: list[np.ndarray] | None = None,
        train_prices: list[np.ndarray] | None = None,
        train_aux: list[np.ndarray] | None = None,
    ) -> Any:
        """Train new challenger model

        Uses RLTrainer to train a new model on fresh data. Saves model with
        timestamped version and registers in ModelRegistry. Full MLflow tracking
        of training process, hyperparameters, and metadata.

        Args:
            train_days: Training data (daily features)
            train_prices: Training prices (daily OHLC)
            train_aux: Auxiliary training features

        Returns:
            Trained model

        Raises:
            Exception: If training fails after all retry attempts
        """
        logger.info("Training new challenger model...")

        # Load data if not provided
        if train_days is None or train_prices is None:
            train_days, train_prices, _, _ = self._load_data()

        # Generate version identifier
        version = datetime.now().strftime(
            self.training_config.get("version_format", "%Y%m%d_%H%M%S")
        )

        # Prepare MLflow experiment
        experiment_name = self.mlflow_config.get(
            "experiment_name",
            "rl_retraining_pipeline"
        )

        # Start MLflow run for retraining pipeline (wraps RLTrainer's internal run)
        if HAS_MLFLOW:
            try:
                mlflow.set_experiment(experiment_name)
            except MlflowException as e:
                logger.warning(f"Failed to set MLflow experiment: {e}")

        # Extract training data date range for audit trail
        train_start, train_end = self._extract_date_range(train_days, train_prices)
        git_sha = self._get_git_sha()

        logger.info(f"Training data: {train_start} to {train_end} ({len(train_days)} days)")
        logger.info(f"Git SHA: {git_sha}")

        # Collect training metadata
        training_params = {
            "git_sha": git_sha,
            "training_timestamp": datetime.now().isoformat(),
            "pipeline_version": version,
            "algo": "mppo",
            "model_type": "challenger",
            "n_train_days": len(train_days) if train_days else 0,
            "train_data_start": train_start,
            "train_data_end": train_end,
            "has_aux_features": train_aux is not None,
            **{
                k: v
                for k, v in self.training_config.items()
                if isinstance(v, (int, float, str, bool))
            },
        }

        # Train model with retry logic and MLflow tracking
        max_retries = self.training_config.get("max_retries", 2)
        last_error = None
        model = None

        for attempt in range(max_retries + 1):
            # Start MLflow run for this training attempt
            run_name = f"challenger_{version}_attempt_{attempt + 1}"

            if HAS_MLFLOW:
                try:
                    mlflow.start_run(run_name=run_name, nested=True)
                    mlflow.log_params(training_params)
                    mlflow.log_param("attempt_number", attempt + 1)
                    mlflow.log_param("max_retries", max_retries)
                except MlflowException as e:
                    logger.warning(f"MLflow run start failed: {e}")

            try:
                logger.info(
                    f"Training attempt {attempt + 1}/{max_retries + 1} "
                    f"(version: {version})..."
                )

                # Train model using RLTrainer (it has its own MLflow tracking)
                model = self.trainer.train(
                    algo="mppo",
                    train_days=train_days,
                    train_prices=train_prices,
                    train_aux=train_aux,
                )

                # Save model with versioned filename
                model_filename = f"mppo_challenger_{version}.zip"
                model_path = self.challenger_path / model_filename
                model.save(str(model_path))
                logger.info(f"Challenger model saved: {model_path}")

                # Log model metadata to MLflow
                if HAS_MLFLOW:
                    try:
                        mlflow.log_param("model_path", str(model_path))
                        mlflow.log_param("model_filename", model_filename)
                        mlflow.log_param("training_status", "success")
                        mlflow.log_metric("training_attempts_used", attempt + 1)

                        # Log model as artifact
                        mlflow.log_artifact(str(model_path), artifact_path="models")

                        logger.info(f"Model metadata logged to MLflow: {run_name}")
                    except MlflowException as e:
                        logger.warning(f"MLflow artifact logging failed: {e}")
                    finally:
                        try:
                            mlflow.end_run()
                        except MlflowException:
                            pass

                # Training successful, return model
                logger.info(
                    f"Training successful on attempt {attempt + 1}/{max_retries + 1}"
                )
                return model

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Training attempt {attempt + 1}/{max_retries + 1} failed: {e}",
                    exc_info=True,
                )

                # Log failure to MLflow
                if HAS_MLFLOW:
                    try:
                        mlflow.log_param("training_status", "failed")
                        mlflow.log_param("error_message", str(e)[:500])
                        mlflow.log_param("error_type", type(e).__name__)
                        mlflow.log_metric("training_attempts_used", attempt + 1)
                    except MlflowException as mlflow_err:
                        logger.warning(f"MLflow error logging failed: {mlflow_err}")
                    finally:
                        try:
                            mlflow.end_run()
                        except MlflowException:
                            pass

                # Retry or raise
                if attempt < max_retries:
                    logger.info(f"Retrying training... ({max_retries - attempt} retries left)")
                    continue
                else:
                    logger.error(
                        f"Training failed after {max_retries + 1} attempts. "
                        f"Last error: {last_error}"
                    )
                    raise last_error

    def evaluate_models(
        self,
        challenger_model: Any,
        test_days: list[np.ndarray] | None = None,
        test_prices: list[np.ndarray] | None = None,
        test_aux: list[np.ndarray] | None = None,
    ) -> dict[str, Any]:
        """Evaluate champion vs challenger models

        Loads current champion from registry and compares against new challenger
        using ChampionChallengerEvaluator on held-out test data.

        Args:
            challenger_model: Newly trained challenger model
            test_days: Test data (daily features)
            test_prices: Test prices (daily OHLC)
            test_aux: Auxiliary test features

        Returns:
            Comparison results dict with keys:
                - champion: Champion metrics
                - challenger: Challenger metrics
                - improvement: Improvement metrics
                - should_promote: Promotion decision
                - reason: Decision reason
        """
        logger.info("Evaluating champion vs challenger...")

        # Load test data if not provided
        if test_days is None or test_prices is None:
            _, _, test_days, test_prices = self._load_data()

        # Get current champion model
        champion_info = self.registry.get_champion()

        if champion_info is None:
            logger.warning("No champion model found - this is first deployment")
            # Evaluate challenger only
            challenger_metrics = self.evaluator.rl_evaluator.evaluate_model(
                model=challenger_model,
                test_days=test_days,
                test_prices=test_prices,
                slippage=0.0,
                deterministic=True,
                test_aux=test_aux,
            )

            # Check if challenger meets absolute thresholds
            should_promote, reason = self.evaluator.should_promote(
                challenger_metrics=challenger_metrics,
                champion_metrics=None,
            )

            comparison = {
                "champion": None,
                "challenger": challenger_metrics,
                "improvement": None,
                "should_promote": should_promote,
                "reason": reason,
            }
        else:
            # Load champion model for comparison
            logger.info(
                f"Loading champion model version {champion_info['version']} "
                f"(Sharpe: {champion_info['metrics'].get('sharpe', 'N/A')})"
            )

            # Load champion model from MLflow artifact
            champion_model = None
            champion_source = champion_info.get("source")

            if champion_source:
                try:
                    # Download champion model from MLflow to temp directory
                    import tempfile
                    from sb3_contrib import MaskablePPO

                    logger.info(f"Downloading champion model from: {champion_source}")

                    # MLflow source is like "runs:/<run_id>/models/mppo_challenger_*.zip"
                    # We need to extract the artifact path and download it
                    if HAS_MLFLOW:
                        # Download artifact from MLflow
                        temp_dir = tempfile.mkdtemp()
                        artifact_path = champion_source.split("/", 3)[-1]  # Extract path after run_id
                        run_id = champion_info.get("run_id")

                        if run_id:
                            # Download artifact from run
                            local_path = mlflow.artifacts.download_artifacts(
                                run_id=run_id,
                                artifact_path=artifact_path,
                                dst_path=temp_dir,
                            )
                            logger.info(f"Champion model downloaded to: {local_path}")

                            # Load SB3 model (remove .zip extension if present)
                            model_path = str(local_path).replace(".zip", "")
                            champion_model = MaskablePPO.load(model_path)
                            logger.info("Champion model loaded successfully")
                        else:
                            logger.warning("No run_id found in champion info, using cached metrics")
                    else:
                        logger.warning("MLflow not available, using cached champion metrics")

                except Exception as e:
                    logger.warning(
                        f"Failed to load champion model from MLflow: {e}. "
                        "Using cached metrics instead."
                    )
                    champion_model = None
            else:
                logger.warning("No source path found for champion model, using cached metrics")

            # Evaluate champion if loaded, otherwise use cached metrics
            if champion_model is not None:
                logger.info("Evaluating champion model on test data...")
                champion_metrics = self.evaluator.rl_evaluator.evaluate_model(
                    model=champion_model,
                    test_days=test_days,
                    test_prices=test_prices,
                    slippage=0.0,
                    deterministic=True,
                    test_aux=test_aux,
                )
                logger.info(
                    f"Champion fresh evaluation: Sharpe={champion_metrics['sharpe_ratio']:.2f}, "
                    f"Win Rate={champion_metrics['win_rate_pct']:.1f}%, "
                    f"Max DD={champion_metrics['max_drawdown_pct']:.2f}%"
                )
            else:
                # Fall back to cached metrics from registry
                logger.info("Using cached champion metrics from registry")
                champion_metrics = champion_info["metrics"]

                # Normalize metric format to match RLEvaluator output
                if "sharpe" in champion_metrics and "sharpe_ratio" not in champion_metrics:
                    champion_metrics["sharpe_ratio"] = champion_metrics.get("sharpe", 0.0)
                if "win_rate" in champion_metrics and "win_rate_pct" not in champion_metrics:
                    # win_rate is stored as decimal (0.55), convert to percentage (55.0)
                    champion_metrics["win_rate_pct"] = champion_metrics.get("win_rate", 0.0) * 100
                if "max_dd" in champion_metrics and "max_drawdown_pct" not in champion_metrics:
                    # max_dd is stored as decimal (-0.15), convert to percentage (-15.0)
                    champion_metrics["max_drawdown_pct"] = champion_metrics.get("max_dd", 0.0) * 100

            # Evaluate challenger
            logger.info("Evaluating challenger model on test data...")
            challenger_metrics = self.evaluator.rl_evaluator.evaluate_model(
                model=challenger_model,
                test_days=test_days,
                test_prices=test_prices,
                slippage=0.0,
                deterministic=True,
                test_aux=test_aux,
            )
            logger.info(
                f"Challenger evaluation: Sharpe={challenger_metrics['sharpe_ratio']:.2f}, "
                f"Win Rate={challenger_metrics['win_rate_pct']:.1f}%, "
                f"Max DD={challenger_metrics['max_drawdown_pct']:.2f}%"
            )

            # Make promotion decision
            should_promote, reason = self.evaluator.should_promote(
                challenger_metrics=challenger_metrics,
                champion_metrics=champion_metrics,
            )

            # Calculate improvement
            improvement = self.evaluator.calculate_improvement(
                challenger_metrics=challenger_metrics,
                champion_metrics=champion_metrics,
            )

            comparison = {
                "champion": champion_metrics,
                "challenger": challenger_metrics,
                "improvement": improvement,
                "should_promote": should_promote,
                "reason": reason,
            }

        # Generate detailed report
        report = self.evaluator.generate_comparison_report(
            challenger_metrics=comparison["challenger"],
            champion_metrics=comparison.get("champion"),
            improvement=comparison.get("improvement"),
            promotion_decision=(comparison["should_promote"], comparison["reason"]),
        )

        # Log to MLflow
        if HAS_MLFLOW and self.mlflow_config.get("log_comparison_report", True):
            mlflow.log_dict(report, "comparison_report.json")

        logger.info(f"Evaluation complete: {comparison['reason']}")

        return comparison

    def promote_if_better(
        self,
        comparison: dict[str, Any],
        model_path: Path | None = None,
        skip_paper_trading: bool = False,
    ) -> bool:
        """Promote challenger to Staging if it meets backtest thresholds

        First stage of promotion: registers model and moves to Staging stage.
        Paper trading validation is required before final Production promotion
        (unless skip_paper_trading=True for testing/emergency deployments).

        Args:
            comparison: Comparison results from evaluate_models()
            model_path: Path to challenger model file (optional)
            skip_paper_trading: If True, promote directly to Production (default: False)

        Returns:
            True if promotion occurred, False otherwise
        """
        should_promote = comparison["should_promote"]
        reason = comparison["reason"]
        challenger_metrics = comparison["challenger"]
        champion_metrics = comparison.get("champion")

        if not should_promote:
            logger.info(f"Promotion rejected: {reason}")
            if HAS_MLFLOW:
                git_sha = self._get_git_sha()
                mlflow.log_params({
                    "promotion_decision": "rejected",
                    "rejection_reason": reason,
                    "rejection_timestamp": datetime.now().isoformat(),
                    "git_sha": git_sha,
                })

                # Log rejection metrics for audit trail
                mlflow.log_metrics({
                    "rejected_sharpe": challenger_metrics.get("sharpe_ratio", 0.0),
                    "rejected_win_rate": challenger_metrics.get("win_rate_pct", 0.0),
                    "rejected_max_dd": challenger_metrics.get("max_drawdown_pct", 0.0),
                })

                # Log rejection decision as artifact
                rejection_report = {
                    "decision": "rejected",
                    "reason": reason,
                    "timestamp": datetime.now().isoformat(),
                    "git_sha": git_sha,
                    "challenger_metrics": challenger_metrics,
                    "champion_metrics": champion_metrics,
                }
                self._log_comparison_artifact(rejection_report, "rejection_decision.json")

            # Send rejection notification
            self._send_rejection_notification(
                reason=reason,
                challenger_metrics=challenger_metrics,
                champion_metrics=champion_metrics,
            )
            return False

        logger.info(f"Promotion approved: {reason}")

        try:
            # Find latest challenger model if not provided
            if model_path is None:
                challenger_files = sorted(
                    self.challenger_path.glob("mppo_challenger_*.zip"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if not challenger_files:
                    logger.error("No challenger model file found")
                    return False
                model_path = challenger_files[0]

            # Register model in MLflow Model Registry
            version = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Extract metrics for registration
            metrics = {
                "sharpe": challenger_metrics.get("sharpe_ratio", 0.0),
                "win_rate": challenger_metrics.get("win_rate_pct", 0.0) / 100.0,  # Convert to decimal
                "max_dd": challenger_metrics.get("max_drawdown_pct", 0.0) / 100.0,
            }

            # Determine target stage and validation requirements
            target_stage = "Production" if skip_paper_trading else "Staging"
            paper_days = self.thresholds.get("paper_trading_days", 5)

            # Register model
            model_version = self.registry.register_model(
                model_path=str(model_path),
                metrics=metrics,
                metadata={
                    "promoted_at": datetime.now().isoformat(),
                    "promotion_reason": reason,
                    "requires_paper_validation": not skip_paper_trading,
                    "paper_trading_days_required": paper_days if not skip_paper_trading else 0,
                },
            )

            logger.info(f"Model registered: version {model_version}")

            # Promote to target stage
            promotion_success = self.registry.promote_model(
                version=model_version,
                stage=target_stage,
                archive_current=(target_stage == "Production"),
            )

            if promotion_success:
                logger.info(f"✓ Model version {model_version} promoted to {target_stage}")
                if HAS_MLFLOW:
                    git_sha = self._get_git_sha()
                    mlflow.log_params({
                        "promotion_decision": "approved",
                        "promoted_version": model_version,
                        "promoted_stage": target_stage,
                        "promotion_reason": reason,
                        "skip_paper_trading": skip_paper_trading,
                        "promotion_timestamp": datetime.now().isoformat(),
                        "git_sha": git_sha,
                    })

                    # Log detailed metrics for audit trail
                    mlflow.log_metrics({
                        "promoted_sharpe": challenger_metrics.get("sharpe_ratio", 0.0),
                        "promoted_win_rate": challenger_metrics.get("win_rate_pct", 0.0),
                        "promoted_max_dd": challenger_metrics.get("max_drawdown_pct", 0.0),
                        "promoted_total_trades": challenger_metrics.get("total_trades", 0),
                        "promoted_profit_factor": challenger_metrics.get("profit_factor", 0.0),
                    })

                    # Log promotion decision as artifact
                    promotion_report = {
                        "decision": "approved",
                        "version": model_version,
                        "stage": target_stage,
                        "reason": reason,
                        "timestamp": datetime.now().isoformat(),
                        "git_sha": git_sha,
                        "challenger_metrics": challenger_metrics,
                        "champion_metrics": champion_metrics,
                        "skip_paper_trading": skip_paper_trading,
                        "requires_paper_validation": not skip_paper_trading,
                        "paper_trading_days_required": paper_days if not skip_paper_trading else 0,
                    }
                    self._log_comparison_artifact(promotion_report, "promotion_decision.json")

                # Send appropriate notification
                if target_stage == "Staging":
                    self._send_staging_notification(
                        version=model_version,
                        reason=reason,
                        metrics=challenger_metrics,
                        paper_days=paper_days,
                    )
                else:
                    self._send_promotion_notification(
                        version=model_version,
                        reason=reason,
                        metrics=challenger_metrics,
                    )
                return True
            else:
                logger.error(f"Failed to promote model to {target_stage}")
                return False

        except Exception as e:
            logger.error(f"Promotion failed: {e}", exc_info=True)
            if HAS_MLFLOW:
                mlflow.log_param("promotion_decision", "failed")
                mlflow.log_param("promotion_error", str(e))
            return False

    def check_paper_trading_performance(
        self,
        model_version: str | None = None,
        min_days: int | None = None,
    ) -> dict[str, Any]:
        """Check paper trading performance for a Staging model

        Analyzes recent paper trading logs to determine if model meets production
        readiness criteria. Checks performance over required validation period.

        Args:
            model_version: Model version to check. If None, uses current Staging model
            min_days: Minimum days of paper trading required. If None, uses config

        Returns:
            dict with keys:
                - ready_for_production: bool
                - reason: str
                - metrics: dict (sharpe, win_rate, trades, etc.)
                - days_validated: int
        """
        if min_days is None:
            min_days = self.thresholds.get("paper_trading_days", 5)

        min_trades = self.thresholds.get("paper_trading_min_trades", 10)

        # Get Staging model if not specified
        if model_version is None:
            staging_versions = self.registry.list_versions(stage="Staging")
            if not staging_versions:
                return {
                    "ready_for_production": False,
                    "reason": "No Staging model found",
                    "metrics": {},
                    "days_validated": 0,
                }
            model_version = staging_versions[0]["version"]

        logger.info(f"Checking paper trading performance for model version {model_version}")

        # Load paper trading logs
        try:
            paper_logs = self._load_paper_trading_logs(model_version, days=min_days)
        except Exception as e:
            logger.error(f"Failed to load paper trading logs: {e}")
            return {
                "ready_for_production": False,
                "reason": f"Failed to load paper trading logs: {e}",
                "metrics": {},
                "days_validated": 0,
            }

        if not paper_logs:
            return {
                "ready_for_production": False,
                "reason": f"No paper trading data found (need {min_days} days)",
                "metrics": {},
                "days_validated": 0,
            }

        # Calculate performance metrics from logs
        metrics = self._calculate_paper_metrics(paper_logs)
        days_validated = len(paper_logs)

        # Check validation requirements
        if days_validated < min_days:
            return {
                "ready_for_production": False,
                "reason": f"Insufficient validation period ({days_validated}/{min_days} days)",
                "metrics": metrics,
                "days_validated": days_validated,
            }

        if metrics.get("total_trades", 0) < min_trades:
            return {
                "ready_for_production": False,
                "reason": f"Insufficient trades ({metrics['total_trades']}/{min_trades} trades)",
                "metrics": metrics,
                "days_validated": days_validated,
            }

        # Check performance thresholds
        sharpe = metrics.get("sharpe", 0.0)
        win_rate = metrics.get("win_rate", 0.0)
        max_dd = metrics.get("max_dd", 0.0)

        min_sharpe = self.thresholds.get("min_sharpe_ratio", 1.0)
        min_wr = self.thresholds.get("min_win_rate", 0.45)
        max_dd_threshold = self.thresholds.get("max_drawdown_threshold", -0.20)

        failures = []
        if sharpe < min_sharpe:
            failures.append(f"Sharpe {sharpe:.2f} < {min_sharpe:.2f}")
        if win_rate < min_wr:
            failures.append(f"Win rate {win_rate:.1%} < {min_wr:.1%}")
        if max_dd < max_dd_threshold:
            failures.append(f"Max DD {max_dd:.1%} < {max_dd_threshold:.1%}")

        if failures:
            return {
                "ready_for_production": False,
                "reason": "Performance below thresholds: " + "; ".join(failures),
                "metrics": metrics,
                "days_validated": days_validated,
            }

        # All checks passed
        return {
            "ready_for_production": True,
            "reason": f"Validated over {days_validated} days with {metrics['total_trades']} trades",
            "metrics": metrics,
            "days_validated": days_validated,
        }

    def promote_staging_to_production(
        self,
        model_version: str | None = None,
        force: bool = False,
    ) -> bool:
        """Promote Staging model to Production after paper trading validation

        Final promotion step: moves validated model from Staging to Production.
        Requires paper trading validation to pass unless force=True.

        Args:
            model_version: Model version to promote. If None, uses current Staging model
            force: If True, skip validation and promote anyway

        Returns:
            True if promotion successful, False otherwise
        """
        # Get Staging model
        if model_version is None:
            staging_versions = self.registry.list_versions(stage="Staging")
            if not staging_versions:
                logger.error("No Staging model to promote")
                return False
            model_version = staging_versions[0]["version"]

        logger.info(f"=" * 80)
        logger.info(f"Attempting to promote Staging model {model_version} to Production")
        logger.info(f"=" * 80)

        # Check paper trading validation (unless forced)
        if not force:
            validation = self.check_paper_trading_performance(model_version)

            if not validation["ready_for_production"]:
                logger.warning(f"Paper trading validation failed: {validation['reason']}")
                logger.warning(f"Metrics: {validation['metrics']}")

                # Send rejection notification
                self._send_paper_validation_failed_notification(
                    version=model_version,
                    reason=validation["reason"],
                    metrics=validation["metrics"],
                    days_validated=validation["days_validated"],
                )
                return False

            logger.info(f"✓ Paper trading validation passed: {validation['reason']}")
            logger.info(f"Metrics: {validation['metrics']}")

        # Promote to Production
        try:
            promotion_success = self.registry.promote_model(
                version=model_version,
                stage="Production",
                archive_current=True,
            )

            if promotion_success:
                logger.info(f"✓ Model version {model_version} promoted to Production")

                # Log to MLflow
                if HAS_MLFLOW:
                    with mlflow.start_run(run_name=f"paper_validation_{model_version}"):
                        mlflow.log_param("model_version", model_version)
                        mlflow.log_param("promotion_type", "staging_to_production")
                        mlflow.log_param("forced", force)

                        if not force:
                            validation = self.check_paper_trading_performance(model_version)
                            for key, value in validation["metrics"].items():
                                mlflow.log_metric(f"paper_{key}", value)
                            mlflow.log_metric("paper_days_validated", validation["days_validated"])

                # Send production promotion notification
                metrics = validation["metrics"] if not force else {}
                self._send_paper_validation_success_notification(
                    version=model_version,
                    metrics=metrics,
                    days_validated=validation.get("days_validated", 0) if not force else 0,
                )

                return True
            else:
                logger.error("Failed to promote model to Production")
                return False

        except Exception as e:
            logger.error(f"Production promotion failed: {e}", exc_info=True)
            return False

    def reject_staging_model(
        self,
        model_version: str | None = None,
        reason: str = "Manual rejection",
    ) -> bool:
        """Reject and archive a Staging model that failed paper trading validation

        Args:
            model_version: Model version to reject. If None, uses current Staging model
            reason: Reason for rejection

        Returns:
            True if rejection successful, False otherwise
        """
        # Get Staging model
        if model_version is None:
            staging_versions = self.registry.list_versions(stage="Staging")
            if not staging_versions:
                logger.error("No Staging model to reject")
                return False
            model_version = staging_versions[0]["version"]

        logger.info(f"Rejecting Staging model {model_version}: {reason}")

        try:
            # Move to Archived
            rejection_success = self.registry.promote_model(
                version=model_version,
                stage="Archived",
                archive_current=False,
            )

            if rejection_success:
                logger.info(f"✓ Model version {model_version} rejected and archived")

                # Log to MLflow
                if HAS_MLFLOW:
                    with mlflow.start_run(run_name=f"staging_rejection_{model_version}"):
                        mlflow.log_param("model_version", model_version)
                        mlflow.log_param("rejection_reason", reason)
                        mlflow.log_param("rejected_at", datetime.now().isoformat())

                # Send rejection notification
                self._send_staging_rejection_notification(
                    version=model_version,
                    reason=reason,
                )

                return True
            else:
                logger.error("Failed to reject Staging model")
                return False

        except Exception as e:
            logger.error(f"Staging rejection failed: {e}", exc_info=True)
            return False

    def _load_paper_trading_logs(
        self,
        model_version: str,
        days: int,
    ) -> list[dict[str, Any]]:
        """Load paper trading logs for model validation

        Looks for paper trading log files in results/rl/paper/ directory.
        Each log file should contain daily trading session results.

        Args:
            model_version: Model version identifier
            days: Number of days to load

        Returns:
            List of daily log dictionaries
        """
        import json
        from datetime import timedelta

        log_dir = Path(self.config.get("paper", {}).get("log_dir", "./results/rl/paper/"))

        if not log_dir.exists():
            logger.warning(f"Paper trading log directory not found: {log_dir}")
            return []

        # Look for log files matching the model version
        # Format: paper_YYYYMMDD_{model_version}.json
        logs = []
        today = datetime.now().date()

        for i in range(days):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y%m%d")

            # Try multiple naming patterns
            patterns = [
                f"paper_{date_str}_{model_version}.json",
                f"paper_{date_str}.json",  # Fallback: any paper trading log from that day
            ]

            for pattern in patterns:
                log_path = log_dir / pattern
                if log_path.exists():
                    try:
                        with open(log_path) as f:
                            log_data = json.load(f)
                            logs.append(log_data)
                        break  # Found log for this day
                    except Exception as e:
                        logger.warning(f"Failed to load {log_path}: {e}")

        logger.info(f"Loaded {len(logs)} days of paper trading logs")
        return logs

    def _calculate_paper_metrics(self, paper_logs: list[dict[str, Any]]) -> dict[str, float]:
        """Calculate aggregate metrics from paper trading logs

        Args:
            paper_logs: List of daily paper trading logs

        Returns:
            Dictionary of performance metrics
        """
        if not paper_logs:
            return {}

        # Aggregate trades across all days
        all_trades = []
        total_pnl = 0.0
        initial_balance = self.config.get("env", {}).get("initial_balance", 10_000_000)

        for log in paper_logs:
            trades = log.get("trades", [])
            all_trades.extend(trades)
            total_pnl += log.get("total_pnl", 0.0)

        if not all_trades:
            return {
                "total_trades": 0,
                "sharpe": 0.0,
                "win_rate": 0.0,
                "max_dd": 0.0,
                "total_return": 0.0,
            }

        # Calculate metrics
        wins = sum(1 for t in all_trades if t.get("pnl", 0) > 0)
        losses = sum(1 for t in all_trades if t.get("pnl", 0) < 0)
        win_rate = wins / len(all_trades) if all_trades else 0.0

        # Calculate returns for Sharpe
        returns = [t.get("pnl", 0) / initial_balance for t in all_trades]
        mean_return = np.mean(returns) if returns else 0.0
        std_return = np.std(returns) if len(returns) > 1 else 1e-6
        sharpe = (mean_return / std_return) * np.sqrt(252) if std_return > 0 else 0.0

        # Calculate max drawdown
        balances = [initial_balance]
        for t in all_trades:
            balances.append(balances[-1] + t.get("pnl", 0))

        peak = balances[0]
        max_dd = 0.0
        for balance in balances:
            if balance > peak:
                peak = balance
            dd = (balance - peak) / peak if peak > 0 else 0.0
            max_dd = min(max_dd, dd)

        return {
            "total_trades": len(all_trades),
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "sharpe": sharpe,
            "total_return": total_pnl / initial_balance,
            "max_dd": max_dd,
            "avg_pnl_per_trade": total_pnl / len(all_trades) if all_trades else 0.0,
        }

    def rollback_if_failed(
        self,
        test_days: list[np.ndarray] | None = None,
        test_prices: list[np.ndarray] | None = None,
        test_aux: list[np.ndarray] | None = None,
    ) -> bool:
        """Rollback to previous champion if current production model underperforms

        Monitors production model performance and triggers rollback if it falls
        below configured thresholds. Demotes current champion and restores
        previous archived model.

        Args:
            test_days: Test data (daily features). If None, loads from ClickHouse
            test_prices: Test prices (daily OHLC)
            test_aux: Auxiliary test features

        Returns:
            True if rollback occurred, False otherwise
        """
        if not self.rollback_config.get("enabled", True):
            logger.info("Rollback disabled in config")
            return False

        logger.info("=" * 80)
        logger.info("Checking if rollback is needed...")
        logger.info("=" * 80)

        # Get current production champion
        current_champion = self.registry.get_champion()
        if not current_champion:
            logger.warning("No production model to rollback from")
            return False

        # Get previous archived versions
        archived_versions = self.registry.list_versions(stage="Archived")
        if not archived_versions:
            logger.warning("No archived model available for rollback")
            return False

        # Get most recent archived model (previous champion)
        previous_champion = sorted(
            archived_versions,
            key=lambda v: int(v["version"]),
            reverse=True
        )[0]

        logger.info(
            f"Current champion: version {current_champion['version']} "
            f"(Sharpe: {current_champion['metrics'].get('sharpe', 'N/A')})"
        )
        logger.info(
            f"Previous champion: version {previous_champion['version']} "
            f"(Sharpe: {previous_champion['metrics'].get('sharpe', 'N/A')})"
        )

        # Load test data if not provided
        if test_days is None or test_prices is None:
            try:
                _, _, test_days, test_prices = self._load_data()
                logger.info(f"Loaded {len(test_days)} days of test data for evaluation")
            except Exception as e:
                logger.error(f"Failed to load test data for rollback evaluation: {e}")
                return False

        # Load and evaluate current production model
        try:
            from sb3_contrib import MaskablePPO

            # Download current champion model
            champion_source = current_champion.get("source")
            if not champion_source:
                logger.error("No source path for current champion model")
                return False

            if HAS_MLFLOW:
                import tempfile

                logger.info(f"Downloading current champion model from MLflow...")
                temp_dir = tempfile.mkdtemp()
                artifact_path = champion_source.split("/", 3)[-1]
                run_id = current_champion.get("run_id")

                if not run_id:
                    logger.error("No run_id found for current champion")
                    return False

                # Download artifact
                local_path = mlflow.artifacts.download_artifacts(
                    run_id=run_id,
                    artifact_path=artifact_path,
                    dst_path=temp_dir,
                )

                # Load model
                model_path = str(local_path).replace(".zip", "")
                current_model = MaskablePPO.load(model_path)
                logger.info("Current champion model loaded successfully")
            else:
                logger.error("MLflow not available, cannot load model for rollback check")
                return False

        except Exception as e:
            logger.error(f"Failed to load current champion model: {e}", exc_info=True)
            return False

        # Evaluate current model on test data
        try:
            logger.info("Evaluating current production model performance...")
            current_metrics = self.evaluator.rl_evaluator.evaluate_model(
                model=current_model,
                test_days=test_days,
                test_prices=test_prices,
                slippage=0.0,
                deterministic=True,
                test_aux=test_aux,
            )

            logger.info(
                f"Current model performance: "
                f"Sharpe={current_metrics['sharpe_ratio']:.2f}, "
                f"Win Rate={current_metrics['win_rate_pct']:.1f}%, "
                f"Max DD={current_metrics['max_drawdown_pct']:.2f}%"
            )

        except Exception as e:
            logger.error(f"Failed to evaluate current model: {e}", exc_info=True)
            return False

        # Get previous champion metrics (baseline for comparison)
        previous_metrics = previous_champion["metrics"]

        # Normalize metric format
        if "sharpe" in previous_metrics and "sharpe_ratio" not in previous_metrics:
            previous_sharpe = previous_metrics.get("sharpe", 0.0)
        else:
            previous_sharpe = previous_metrics.get("sharpe_ratio", 0.0)

        if "win_rate" in previous_metrics and "win_rate_pct" not in previous_metrics:
            previous_win_rate = previous_metrics.get("win_rate", 0.0) * 100
        else:
            previous_win_rate = previous_metrics.get("win_rate_pct", 0.0)

        if "max_dd" in previous_metrics and "max_drawdown_pct" not in previous_metrics:
            previous_max_dd = previous_metrics.get("max_dd", 0.0) * 100
        else:
            previous_max_dd = previous_metrics.get("max_drawdown_pct", 0.0)

        # Extract rollback thresholds
        sharpe_threshold = float(self.thresholds.get("rollback_sharpe_threshold", 0.8))
        win_rate_threshold = float(self.thresholds.get("rollback_win_rate_threshold", 0.9))
        max_dd_threshold = float(self.thresholds.get("rollback_max_dd_threshold", 1.2))

        # Check rollback conditions
        rollback_reasons = []

        # Sharpe ratio check (current should be >= 80% of previous)
        if previous_sharpe > 0:
            sharpe_ratio = current_metrics["sharpe_ratio"] / previous_sharpe
            if sharpe_ratio < sharpe_threshold:
                rollback_reasons.append(
                    f"Sharpe ratio degraded: {sharpe_ratio:.2%} of previous "
                    f"(threshold: {sharpe_threshold:.0%})"
                )

        # Win rate check (current should be >= 90% of previous)
        if previous_win_rate > 0:
            win_rate_ratio = current_metrics["win_rate_pct"] / previous_win_rate
            if win_rate_ratio < win_rate_threshold:
                rollback_reasons.append(
                    f"Win rate degraded: {win_rate_ratio:.2%} of previous "
                    f"(threshold: {win_rate_threshold:.0%})"
                )

        # Max drawdown check (current should be <= 120% of previous)
        # Note: max_dd is negative, so more negative = worse
        if previous_max_dd < 0:
            max_dd_ratio = abs(current_metrics["max_drawdown_pct"]) / abs(previous_max_dd)
            if max_dd_ratio > max_dd_threshold:
                rollback_reasons.append(
                    f"Max drawdown exceeded: {max_dd_ratio:.2%} of previous "
                    f"(threshold: {max_dd_threshold:.0%})"
                )

        # Decide rollback
        should_rollback = len(rollback_reasons) > 0

        if not should_rollback:
            logger.info("✓ Rollback check passed: Production model performing within thresholds")
            logger.info("=" * 80)
            return False

        # Log rollback decision
        logger.warning("❌ Rollback triggered: Production model underperforming")
        for reason in rollback_reasons:
            logger.warning(f"  - {reason}")

        # Start MLflow run for rollback tracking
        if HAS_MLFLOW:
            try:
                experiment_name = self.mlflow_config.get(
                    "experiment_name",
                    "rl_retraining_pipeline"
                )
                mlflow.set_experiment(experiment_name)
                mlflow.start_run(run_name=f"rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

                git_sha = self._get_git_sha()

                # Log rollback metadata
                mlflow.log_params({
                    "git_sha": git_sha,
                    "rollback_triggered": True,
                    "rollback_timestamp": datetime.now().isoformat(),
                    "demoted_version": current_champion["version"],
                    "restored_version": previous_champion["version"],
                    "rollback_reason_count": len(rollback_reasons),
                    "rollback_sharpe_threshold": sharpe_threshold,
                    "rollback_win_rate_threshold": win_rate_threshold,
                    "rollback_max_dd_threshold": max_dd_threshold,
                })

                # Log performance comparison
                mlflow.log_metrics({
                    "current_sharpe": current_metrics["sharpe_ratio"],
                    "current_win_rate": current_metrics["win_rate_pct"],
                    "current_max_dd": current_metrics["max_drawdown_pct"],
                    "current_total_trades": current_metrics.get("total_trades", 0),
                    "current_profit_factor": current_metrics.get("profit_factor", 0.0),
                    "previous_sharpe": previous_sharpe,
                    "previous_win_rate": previous_win_rate,
                    "previous_max_dd": previous_max_dd,
                    "sharpe_degradation_pct": (
                        (current_metrics["sharpe_ratio"] / previous_sharpe - 1.0) * 100
                        if previous_sharpe > 0 else 0.0
                    ),
                    "win_rate_degradation_pct": (
                        (current_metrics["win_rate_pct"] / previous_win_rate - 1.0) * 100
                        if previous_win_rate > 0 else 0.0
                    ),
                })

                # Log rollback reasons
                for i, reason in enumerate(rollback_reasons):
                    mlflow.log_param(f"rollback_reason_{i+1}", reason)

                # Log comprehensive rollback report as artifact
                rollback_report = {
                    "event": "rollback",
                    "timestamp": datetime.now().isoformat(),
                    "git_sha": git_sha,
                    "demoted_version": current_champion["version"],
                    "restored_version": previous_champion["version"],
                    "reasons": rollback_reasons,
                    "thresholds": {
                        "sharpe_threshold": sharpe_threshold,
                        "win_rate_threshold": win_rate_threshold,
                        "max_dd_threshold": max_dd_threshold,
                    },
                    "current_model": {
                        "version": current_champion["version"],
                        "metrics": current_metrics,
                    },
                    "previous_model": {
                        "version": previous_champion["version"],
                        "metrics": {
                            "sharpe_ratio": previous_sharpe,
                            "win_rate_pct": previous_win_rate,
                            "max_drawdown_pct": previous_max_dd,
                        },
                    },
                }
                self._log_comparison_artifact(rollback_report, "rollback_report.json")

            except MlflowException as e:
                logger.warning(f"MLflow logging failed: {e}")

        # Execute rollback
        try:
            success = self.registry.rollback_model()

            if success:
                logger.info(
                    f"✓ Rolled back from version {current_champion['version']} "
                    f"to version {previous_champion['version']}"
                )

                # Send Telegram notification
                self._send_rollback_notification(
                    current_version=current_champion["version"],
                    previous_version=previous_champion["version"],
                    reasons=rollback_reasons,
                    current_metrics=current_metrics,
                    previous_metrics={
                        "sharpe_ratio": previous_sharpe,
                        "win_rate_pct": previous_win_rate,
                        "max_drawdown_pct": previous_max_dd,
                    },
                )

                if HAS_MLFLOW:
                    mlflow.log_param("rollback_success", True)

                logger.info("=" * 80)
                return True

            else:
                logger.error("Failed to execute rollback")
                if HAS_MLFLOW:
                    mlflow.log_param("rollback_success", False)
                    mlflow.log_param("rollback_error", "Registry rollback failed")
                logger.info("=" * 80)
                return False

        except Exception as e:
            logger.error(f"Rollback failed: {e}", exc_info=True)
            if HAS_MLFLOW:
                mlflow.log_param("rollback_success", False)
                mlflow.log_param("rollback_error", str(e))
            logger.info("=" * 80)
            return False

        finally:
            if HAS_MLFLOW:
                try:
                    mlflow.end_run()
                except MlflowException:
                    pass

    def _send_rollback_notification(
        self,
        current_version: str,
        previous_version: str,
        reasons: list[str],
        current_metrics: dict[str, float],
        previous_metrics: dict[str, float],
    ) -> None:
        """Send Telegram notification for rollback event

        Args:
            current_version: Demoted model version
            previous_version: Restored model version
            reasons: List of rollback reasons
            current_metrics: Current model performance metrics
            previous_metrics: Previous model performance metrics
        """
        if not self._notifier:
            return

        # Check if rollback notifications are enabled
        notify_on = self.config.get("notifications", {}).get("notify_on", {})
        if not notify_on.get("rollback_triggered", True):
            return

        try:
            # Build notification message
            message = (
                "🔴 <b>RL Model Rollback Triggered</b>\n\n"
                f"<b>Demoted Version:</b> {current_version}\n"
                f"<b>Restored Version:</b> {previous_version}\n\n"
                "<b>Rollback Reasons:</b>\n"
            )

            for i, reason in enumerate(reasons, 1):
                message += f"{i}. {reason}\n"

            message += (
                "\n<b>Performance Comparison:</b>\n"
                f"Sharpe: {current_metrics['sharpe_ratio']:.2f} → {previous_metrics['sharpe_ratio']:.2f}\n"
                f"Win Rate: {current_metrics['win_rate_pct']:.1f}% → {previous_metrics['win_rate_pct']:.1f}%\n"
                f"Max DD: {current_metrics['max_drawdown_pct']:.2f}% → {previous_metrics['max_drawdown_pct']:.2f}%\n"
            )

            # Use asyncio.run to properly handle async call
            asyncio.run(self._notifier.send_message(message, is_critical=True))
            logger.info("Rollback notification sent via Telegram")

        except Exception as e:
            logger.warning(f"Failed to send rollback notification: {e}")

    def _send_promotion_notification(
        self,
        version: str,
        reason: str,
        metrics: dict[str, float],
    ) -> None:
        """Send Telegram notification for model promotion

        Args:
            version: Promoted model version
            reason: Promotion reason
            metrics: Model performance metrics
        """
        if not self._notifier:
            return

        # Check if promotion notifications are enabled
        notify_on = self.config.get("notifications", {}).get("notify_on", {})
        if not notify_on.get("promotion_approved", True):
            return

        try:
            # Build notification message
            message = (
                "🟢 <b>RL Model Promoted to Production</b>\n\n"
                f"<b>Version:</b> {version}\n"
                f"<b>Reason:</b> {reason}\n\n"
                "<b>Performance Metrics:</b>\n"
                f"Sharpe Ratio: {metrics.get('sharpe_ratio', 0.0):.2f}\n"
                f"Win Rate: {metrics.get('win_rate_pct', 0.0):.1f}%\n"
                f"Max Drawdown: {metrics.get('max_drawdown_pct', 0.0):.2f}%\n"
                f"Total Trades: {metrics.get('total_trades', 0)}\n"
                f"Total Return: {metrics.get('total_return_pct', 0.0):.2f}%\n"
            )

            # Use asyncio.run to properly handle async call
            asyncio.run(self._notifier.send_message(message, is_critical=True))
            logger.info("Promotion notification sent via Telegram")

        except Exception as e:
            logger.warning(f"Failed to send promotion notification: {e}")

    def _send_rejection_notification(
        self,
        reason: str,
        challenger_metrics: dict[str, float],
        champion_metrics: dict[str, float] | None = None,
    ) -> None:
        """Send Telegram notification for promotion rejection

        Args:
            reason: Rejection reason
            challenger_metrics: Challenger model performance metrics
            champion_metrics: Optional champion model metrics for comparison
        """
        if not self._notifier:
            return

        # Check if rejection notifications are enabled
        notify_on = self.config.get("notifications", {}).get("notify_on", {})
        if not notify_on.get("promotion_rejected", True):
            return

        try:
            # Build notification message
            message = (
                "🟡 <b>RL Model Promotion Rejected</b>\n\n"
                f"<b>Reason:</b> {reason}\n\n"
                "<b>Challenger Performance:</b>\n"
                f"Sharpe Ratio: {challenger_metrics.get('sharpe_ratio', 0.0):.2f}\n"
                f"Win Rate: {challenger_metrics.get('win_rate_pct', 0.0):.1f}%\n"
                f"Max Drawdown: {challenger_metrics.get('max_drawdown_pct', 0.0):.2f}%\n"
            )

            if champion_metrics:
                message += (
                    "\n<b>Current Champion Performance:</b>\n"
                    f"Sharpe Ratio: {champion_metrics.get('sharpe_ratio', 0.0):.2f}\n"
                    f"Win Rate: {champion_metrics.get('win_rate_pct', 0.0):.1f}%\n"
                    f"Max Drawdown: {champion_metrics.get('max_drawdown_pct', 0.0):.2f}%\n"
                )

            # Use asyncio.run to properly handle async call
            asyncio.run(self._notifier.send_message(message, is_critical=False))
            logger.info("Rejection notification sent via Telegram")

        except Exception as e:
            logger.warning(f"Failed to send rejection notification: {e}")

    def _send_training_failure_notification(
        self,
        error: Exception,
        stage: str = "training",
    ) -> None:
        """Send Telegram notification for training failure

        Args:
            error: The exception that caused the failure
            stage: The stage where the failure occurred (training, evaluation, promotion)
        """
        if not self._notifier:
            return

        # Check if failure notifications are enabled
        notify_on = self.config.get("notifications", {}).get("notify_on", {})
        if not notify_on.get("training_failed", True):
            return

        try:
            # Build notification message
            message = (
                "🔴 <b>RL Model Retraining Failed</b>\n\n"
                f"<b>Stage:</b> {stage}\n"
                f"<b>Error:</b> {type(error).__name__}\n"
                f"<b>Details:</b> {str(error)}\n"
                f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            )

            # Use asyncio.run to properly handle async call
            asyncio.run(self._notifier.send_error(message))
            logger.info("Training failure notification sent via Telegram")

        except Exception as e:
            logger.warning(f"Failed to send training failure notification: {e}")

    def _send_staging_notification(
        self,
        version: str,
        reason: str,
        metrics: dict[str, float],
        paper_days: int,
    ) -> None:
        """Send Telegram notification for model promotion to Staging

        Args:
            version: Model version promoted to Staging
            reason: Promotion reason
            metrics: Model performance metrics
            paper_days: Number of paper trading days required
        """
        if not self._notifier:
            return

        # Check if notifications are enabled
        notify_on = self.config.get("notifications", {}).get("notify_on", {})
        if not notify_on.get("paper_trading_start", False):
            return

        try:
            # Build notification message
            message = (
                "🟡 <b>RL Model Promoted to Staging</b>\n\n"
                f"<b>Version:</b> {version}\n"
                f"<b>Reason:</b> {reason}\n\n"
                "<b>Backtest Performance:</b>\n"
                f"Sharpe Ratio: {metrics.get('sharpe_ratio', 0.0):.2f}\n"
                f"Win Rate: {metrics.get('win_rate_pct', 0.0):.1f}%\n"
                f"Max Drawdown: {metrics.get('max_drawdown_pct', 0.0):.2f}%\n\n"
                f"⏳ <b>Paper Trading Validation Required:</b> {paper_days} days\n"
                "Model will be promoted to Production after successful paper trading validation."
            )

            # Use asyncio.run to properly handle async call
            asyncio.run(self._notifier.send_message(message, is_critical=False))
            logger.info("Staging promotion notification sent via Telegram")

        except Exception as e:
            logger.warning(f"Failed to send staging notification: {e}")

    def _send_paper_validation_success_notification(
        self,
        version: str,
        metrics: dict[str, float],
        days_validated: int,
    ) -> None:
        """Send Telegram notification for successful paper trading validation

        Args:
            version: Model version that passed validation
            metrics: Paper trading performance metrics
            days_validated: Number of days validated
        """
        if not self._notifier:
            return

        # Check if notifications are enabled
        notify_on = self.config.get("notifications", {}).get("notify_on", {})
        if not notify_on.get("paper_trading_complete", True):
            return

        try:
            # Build notification message
            message = (
                "✅ <b>Paper Trading Validation Passed</b>\n\n"
                f"<b>Version:</b> {version}\n"
                f"<b>Validation Period:</b> {days_validated} days\n\n"
                "<b>Paper Trading Performance:</b>\n"
                f"Sharpe Ratio: {metrics.get('sharpe', 0.0):.2f}\n"
                f"Win Rate: {metrics.get('win_rate', 0.0):.1%}\n"
                f"Max Drawdown: {metrics.get('max_dd', 0.0):.1%}\n"
                f"Total Trades: {metrics.get('total_trades', 0)}\n"
                f"Total Return: {metrics.get('total_return', 0.0):.2%}\n\n"
                "🟢 <b>Model promoted to Production</b>"
            )

            # Use asyncio.run to properly handle async call
            asyncio.run(self._notifier.send_message(message, is_critical=True))
            logger.info("Paper validation success notification sent via Telegram")

        except Exception as e:
            logger.warning(f"Failed to send paper validation success notification: {e}")

    def _send_paper_validation_failed_notification(
        self,
        version: str,
        reason: str,
        metrics: dict[str, float],
        days_validated: int,
    ) -> None:
        """Send Telegram notification for failed paper trading validation

        Args:
            version: Model version that failed validation
            reason: Failure reason
            metrics: Paper trading performance metrics
            days_validated: Number of days validated
        """
        if not self._notifier:
            return

        # Check if notifications are enabled
        notify_on = self.config.get("notifications", {}).get("notify_on", {})
        if not notify_on.get("paper_trading_complete", True):
            return

        try:
            # Build notification message
            message = (
                "❌ <b>Paper Trading Validation Failed</b>\n\n"
                f"<b>Version:</b> {version}\n"
                f"<b>Validation Period:</b> {days_validated} days\n"
                f"<b>Reason:</b> {reason}\n\n"
                "<b>Paper Trading Performance:</b>\n"
                f"Sharpe Ratio: {metrics.get('sharpe', 0.0):.2f}\n"
                f"Win Rate: {metrics.get('win_rate', 0.0):.1%}\n"
                f"Max Drawdown: {metrics.get('max_dd', 0.0):.1%}\n"
                f"Total Trades: {metrics.get('total_trades', 0)}\n\n"
                "🔴 <b>Model will NOT be promoted to Production</b>"
            )

            # Use asyncio.run to properly handle async call
            asyncio.run(self._notifier.send_message(message, is_critical=True))
            logger.info("Paper validation failure notification sent via Telegram")

        except Exception as e:
            logger.warning(f"Failed to send paper validation failure notification: {e}")

    def _send_staging_rejection_notification(
        self,
        version: str,
        reason: str,
    ) -> None:
        """Send Telegram notification for Staging model rejection

        Args:
            version: Model version rejected
            reason: Rejection reason
        """
        if not self._notifier:
            return

        # Check if notifications are enabled
        notify_on = self.config.get("notifications", {}).get("notify_on", {})
        if not notify_on.get("promotion_rejected", True):
            return

        try:
            # Build notification message
            message = (
                "🔴 <b>Staging Model Rejected</b>\n\n"
                f"<b>Version:</b> {version}\n"
                f"<b>Reason:</b> {reason}\n\n"
                "Model has been archived and will not proceed to Production."
            )

            # Use asyncio.run to properly handle async call
            asyncio.run(self._notifier.send_message(message, is_critical=False))
            logger.info("Staging rejection notification sent via Telegram")

        except Exception as e:
            logger.warning(f"Failed to send staging rejection notification: {e}")

    def _get_git_sha(self) -> str:
        """Get current git commit SHA for versioning

        Returns:
            Git SHA (short form) or 'unknown' if not in a git repo
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return "unknown"

    def _extract_date_range(
        self,
        days: list[np.ndarray],
        prices: list[np.ndarray],
    ) -> tuple[str, str]:
        """Extract start and end dates from daily episode data

        Args:
            days: List of daily feature arrays
            prices: List of daily price arrays

        Returns:
            Tuple of (start_date, end_date) in YYYY-MM-DD format
        """
        if not days or len(days) == 0:
            return ("unknown", "unknown")

        try:
            # Prices array has datetime info - reconstruct dates from indices
            # Use config dates if available
            start_date = self.data_config.get("start_date", "unknown")
            end_date = self.data_config.get("end_date", "unknown")

            # If dates are timestamps, convert them
            if start_date != "unknown" and hasattr(pd, "to_datetime"):
                start_date = pd.to_datetime(start_date).strftime("%Y-%m-%d")
            if end_date != "unknown" and hasattr(pd, "to_datetime"):
                end_date = pd.to_datetime(end_date).strftime("%Y-%m-%d")

            return (str(start_date), str(end_date))
        except Exception as e:
            logger.warning(f"Failed to extract date range: {e}")
            return ("unknown", "unknown")

    def _log_comparison_artifact(
        self,
        comparison: dict[str, Any],
        artifact_name: str = "model_comparison.json",
    ) -> None:
        """Log comparison report as MLflow artifact

        Args:
            comparison: Comparison results dict
            artifact_name: Name for the artifact file
        """
        if not HAS_MLFLOW:
            return

        try:
            # Create temporary file with comparison data
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.json',
                delete=False,
                prefix='comparison_'
            ) as f:
                json.dump(comparison, f, indent=2, default=str)
                temp_path = f.name

            # Log as artifact
            mlflow.log_artifact(temp_path, artifact_path="comparisons")
            logger.debug(f"Logged comparison artifact: {artifact_name}")

            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)

        except Exception as e:
            logger.warning(f"Failed to log comparison artifact: {e}")

    def _load_data(self) -> tuple[
        list[np.ndarray],
        list[np.ndarray],
        list[np.ndarray],
        list[np.ndarray]
    ]:
        """Load training and test data from ClickHouse

        Implements data loading with date range filtering and train/test split.
        Steps:
        1. Load OHLCV data from ClickHouse with date filters
        2. Validate data quality
        3. Calculate RL features
        4. Split by dates with train_ratio
        5. Normalize using MinMaxScaler
        6. Return daily episodes as lists

        Returns:
            Tuple of (train_days, train_prices, test_days, test_prices)
        """
        logger.info("Loading data from ClickHouse...")

        # Extract data config
        symbol = self.data_config.get("symbol", "101S6000")
        database = self.data_config.get("database", "kospi")
        table = self.data_config.get("table", "kospi200f_1m")
        start_date = self.data_config.get("start_date")
        end_date = self.data_config.get("end_date")
        allow_sample_fallback = bool(self.data_config.get("allow_sample_fallback", True))
        train_ratio = float(self.data_config.get("train_ratio", 0.8))
        min_bars = self.data_config.get("min_bars_per_day", 300)

        # Quality validation config
        quality_cfg = self.data_config.get("quality", {}) or {}
        quality_enabled = bool(quality_cfg.get("enabled", True))
        max_zero_volume_ratio = float(quality_cfg.get("max_zero_volume_ratio", 0.95))
        max_zero_volume_price_move_ratio = float(
            quality_cfg.get("max_zero_volume_price_move_ratio", 0.20)
        )
        reject_duplicate_datetime = bool(quality_cfg.get("reject_duplicate_datetime", True))
        require_monotonic_datetime = bool(quality_cfg.get("require_monotonic_datetime", True))

        logger.info(
            f"Loading data: {database}.{table}, symbol={symbol}, "
            f"train_ratio={train_ratio}, start={start_date}, end={end_date}"
        )

        # Load data from ClickHouse
        try:
            import os
            from clickhouse_driver import Client as CHSyncClient

            client = CHSyncClient(
                host=os.getenv("CLICKHOUSE_HOST", "localhost"),
                port=int(os.getenv("CLICKHOUSE_NATIVE_PORT", "9000")),
                user=os.getenv("CLICKHOUSE_USER", "default"),
                password=os.getenv("CLICKHOUSE_PASSWORD", ""),
            )

            # Build query with date range filters
            where = ["code = %(symbol)s"]
            params: dict[str, object] = {"symbol": symbol}
            if start_date:
                where.append("datetime >= %(start_dt)s")
                params["start_dt"] = pd.to_datetime(start_date).to_pydatetime()
            if end_date:
                where.append("datetime <= %(end_dt)s")
                params["end_dt"] = pd.to_datetime(end_date).to_pydatetime()

            query = f"""
                SELECT datetime, open, high, low, close, volume
                FROM {database}.{table}
                WHERE {' AND '.join(where)}
                ORDER BY datetime
            """
            rows = client.execute(query, params)
            df = pd.DataFrame(
                rows,
                columns=["datetime", "open", "high", "low", "close", "volume"]
            )

        except Exception as e:
            if not allow_sample_fallback:
                raise RuntimeError(
                    f"ClickHouse load failed for {database}.{table} ({symbol}): {e}"
                ) from e
            logger.warning(f"ClickHouse not available: {e}. Using sample data.")
            df = _generate_sample_data()

        # Handle empty data
        if df.empty:
            if not allow_sample_fallback:
                raise ValueError(
                    f"No data loaded from {database}.{table} ({symbol}) "
                    f"for range {start_date} ~ {end_date}"
                )
            logger.warning("No data loaded. Using sample data.")
            df = _generate_sample_data()
        elif quality_enabled:
            _validate_ohlcv_quality(
                df,
                symbol=symbol,
                table=f"{database}.{table}",
                max_zero_volume_ratio=max_zero_volume_ratio,
                max_zero_volume_price_move_ratio=max_zero_volume_price_move_ratio,
                reject_duplicate_datetime=reject_duplicate_datetime,
                require_monotonic_datetime=require_monotonic_datetime,
            )

        # Calculate RL features
        calc = RLFeatureCalculator()
        df = calc.calculate(df)

        # Remove NaN rows
        df = df.dropna(subset=RL_FEATURE_COLUMNS)

        # Split by dates
        df["date"] = pd.to_datetime(df["datetime"]).dt.date
        dates = sorted(df["date"].unique())

        # Filter dates with minimum bar count
        valid_dates = []
        for d in dates:
            day_df = df[df["date"] == d]
            if len(day_df) >= min_bars:
                valid_dates.append(d)

        logger.info(f"Valid dates: {len(valid_dates)} / {len(dates)}")

        # Train/test split by dates
        split_idx = int(len(valid_dates) * train_ratio)
        train_dates = valid_dates[:split_idx]
        test_dates = valid_dates[split_idx:]

        # Normalize using MinMaxScaler
        from sklearn.preprocessing import MinMaxScaler

        scaler = MinMaxScaler()

        # Fit scaler on training data
        train_all = pd.concat([df[df["date"] == d][RL_FEATURE_COLUMNS] for d in train_dates])
        scaler.fit(train_all.values)

        # Save scaler for inference
        save_dir = Path(
            self.training_config.get("save_dir", "./models/futures/rl/")
        )
        save_dir.mkdir(parents=True, exist_ok=True)
        scaler_path = save_dir / "scaler.joblib"
        joblib.dump(scaler, scaler_path)
        logger.info(f"Scaler saved to {scaler_path}")

        # Helper to split days into episodes
        def split_days(date_list):
            days = []
            prices = []
            for d in date_list:
                day_df = df[df["date"] == d]
                if len(day_df) == 0:
                    continue
                features = scaler.transform(day_df[RL_FEATURE_COLUMNS].values)
                ohlc = day_df[["open", "high", "low", "close"]].values
                days.append(features.astype(np.float32))
                prices.append(ohlc.astype(np.float32))
            return days, prices

        train_days, train_prices = split_days(train_dates)
        test_days, test_prices = split_days(test_dates)

        logger.info(
            f"Data split: train={len(train_days)} days, test={len(test_days)} days"
        )

        # Log to MLflow
        if HAS_MLFLOW and self.mlflow_config.get("log_data_ranges", True):
            mlflow.log_param("train_days_count", len(train_days))
            mlflow.log_param("test_days_count", len(test_days))
            mlflow.log_param("symbol", symbol)
            mlflow.log_param("database", database)
            mlflow.log_param("table", table)
            if start_date:
                mlflow.log_param("start_date", start_date)
            if end_date:
                mlflow.log_param("end_date", end_date)

        return train_days, train_prices, test_days, test_prices
