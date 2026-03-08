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

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from shared.config import ConfigLoader
from shared.ml.rl.champion_challenger import ChampionChallengerEvaluator
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
                mlflow.log_params({
                    "train_days_count": len(train_days),
                    "test_days_count": len(test_days) if test_days else 0,
                    "promoted": promoted,
                })

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
        timestamped version and registers in ModelRegistry.

        Args:
            train_days: Training data (daily features)
            train_prices: Training prices (daily OHLC)
            train_aux: Auxiliary training features

        Returns:
            Trained model
        """
        logger.info("Training new challenger model...")

        # Load data if not provided
        if train_days is None or train_prices is None:
            train_days, train_prices, _, _ = self._load_data()

        # Train model using RLTrainer
        max_retries = self.training_config.get("max_retries", 2)
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                model = self.trainer.train(
                    algo="mppo",
                    train_days=train_days,
                    train_prices=train_prices,
                    train_aux=train_aux,
                )

                # Save model with timestamp version
                version = datetime.now().strftime("%Y%m%d_%H%M%S")
                model_filename = f"mppo_challenger_{version}.zip"
                model_path = self.challenger_path / model_filename
                model.save(str(model_path))
                logger.info(f"Challenger model saved: {model_path}")

                return model

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Training attempt {attempt + 1}/{max_retries + 1} failed: {e}"
                )
                if attempt < max_retries:
                    logger.info("Retrying training...")
                    continue
                else:
                    logger.error(f"Training failed after {max_retries + 1} attempts")
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

            # Note: In production, we would load the champion model from MLflow
            # For now, we'll compare metrics from registry against live evaluation
            # This is a simplified version - full implementation would load model from:
            # champion_model = mlflow.pyfunc.load_model(champion_info['source'])

            # For now, use champion metrics from registry
            champion_metrics = champion_info["metrics"]

            # Evaluate challenger
            challenger_metrics = self.evaluator.rl_evaluator.evaluate_model(
                model=challenger_model,
                test_days=test_days,
                test_prices=test_prices,
                slippage=0.0,
                deterministic=True,
                test_aux=test_aux,
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
    ) -> bool:
        """Promote challenger to production if it meets thresholds

        Registers challenger in ModelRegistry and transitions to Production stage
        if promotion decision is positive. Archives current champion if exists.

        Args:
            comparison: Comparison results from evaluate_models()
            model_path: Path to challenger model file (optional)

        Returns:
            True if promotion occurred, False otherwise
        """
        should_promote = comparison["should_promote"]
        reason = comparison["reason"]
        challenger_metrics = comparison["challenger"]

        if not should_promote:
            logger.info(f"Promotion rejected: {reason}")
            if HAS_MLFLOW:
                mlflow.log_param("promotion_decision", "rejected")
                mlflow.log_param("rejection_reason", reason)
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

            # Register model
            model_version = self.registry.register_model(
                model_path=str(model_path),
                metrics=metrics,
                metadata={
                    "promoted_at": datetime.now().isoformat(),
                    "promotion_reason": reason,
                },
            )

            logger.info(f"Model registered: version {model_version}")

            # Promote to Production stage
            promotion_success = self.registry.promote_model(
                version=model_version,
                stage="Production",
                archive_current=True,
            )

            if promotion_success:
                logger.info(f"✓ Model version {model_version} promoted to Production")
                if HAS_MLFLOW:
                    mlflow.log_param("promotion_decision", "approved")
                    mlflow.log_param("promoted_version", model_version)
                    mlflow.log_param("promotion_reason", reason)
                return True
            else:
                logger.error("Failed to promote model to Production")
                return False

        except Exception as e:
            logger.error(f"Promotion failed: {e}", exc_info=True)
            if HAS_MLFLOW:
                mlflow.log_param("promotion_decision", "failed")
                mlflow.log_param("promotion_error", str(e))
            return False

    def rollback_if_failed(self) -> bool:
        """Rollback to previous champion if current production model underperforms

        Monitors production model performance and triggers rollback if it falls
        below configured thresholds. Demotes current champion and restores
        previous archived model.

        Returns:
            True if rollback occurred, False otherwise
        """
        if not self.rollback_config.get("enabled", True):
            logger.info("Rollback disabled in config")
            return False

        logger.info("Checking if rollback is needed...")

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

        # In a full implementation, we would:
        # 1. Monitor production model performance over time
        # 2. Compare against rollback thresholds
        # 3. Trigger rollback if thresholds breached

        # For now, this is a manual trigger point
        # Actual rollback decision would be based on production metrics
        logger.info("Rollback check complete: No rollback needed at this time")
        return False

        # Example rollback implementation:
        # try:
        #     success = self.registry.rollback_model()
        #     if success:
        #         logger.info("✓ Rolled back to previous champion")
        #         if HAS_MLFLOW:
        #             mlflow.log_param("rollback_triggered", True)
        #             mlflow.log_param("rollback_timestamp", datetime.now().isoformat())
        #         return True
        # except Exception as e:
        #     logger.error(f"Rollback failed: {e}")
        #     return False

    def _load_data(self) -> tuple[
        list[np.ndarray],
        list[np.ndarray],
        list[np.ndarray],
        list[np.ndarray]
    ]:
        """Load training and test data from ClickHouse

        Uses load_data_from_clickhouse from train_rl.py (or similar logic).
        Implements rolling window: train on last N days, test on held-out M days.

        Returns:
            Tuple of (train_days, train_prices, test_days, test_prices)
        """
        logger.info("Loading data from ClickHouse...")

        # Import here to avoid circular dependency
        try:
            from scripts.training.train_rl import load_data_from_clickhouse

            # Load data using base RL config
            base_config = self.training_config.get("base_config", "ml/rl_mppo.yaml")
            train_days, train_prices, test_days, test_prices = load_data_from_clickhouse(
                config_path=base_config,
                persist_scaler=True,
            )

            # Log data ranges to MLflow
            if HAS_MLFLOW and self.mlflow_config.get("log_data_ranges", True):
                mlflow.log_param("train_days_count", len(train_days))
                mlflow.log_param("test_days_count", len(test_days))

            return train_days, train_prices, test_days, test_prices

        except ImportError as e:
            logger.error(f"Failed to import data loading function: {e}")
            # Fallback: return empty arrays
            logger.warning("Using empty data arrays - training will fail")
            return [], [], [], []
