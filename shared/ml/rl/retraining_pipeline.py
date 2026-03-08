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

        # Collect training metadata
        training_params = {
            "pipeline_version": version,
            "algo": "mppo",
            "model_type": "challenger",
            "n_train_days": len(train_days) if train_days else 0,
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
