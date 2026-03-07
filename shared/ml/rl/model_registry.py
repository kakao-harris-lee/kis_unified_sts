"""RL Model Registry

Version tracking and metadata storage for RL models using MLflow Model Registry.
Manages champion/challenger model lifecycle with full audit trail.

Usage:
    registry = ModelRegistry()

    # Register new model
    registry.register_model(
        name="rl_mppo",
        model_path="./models/mppo_20260308.zip",
        metrics={"sharpe": 2.1, "win_rate": 0.58, "max_dd": -0.12},
        metadata={"data_range": "2025-01-01_2026-01-01"}
    )

    # Get production champion
    champion = registry.get_champion("rl_mppo")

    # Get latest challenger
    challenger = registry.get_challenger("rl_mppo")

    # Promote model to production
    registry.promote_model("rl_mppo", version=2)

    # Rollback to previous version
    registry.rollback_model("rl_mppo")
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Optional imports
try:
    import mlflow
    from mlflow.exceptions import MlflowException
    from mlflow.tracking import MlflowClient

    HAS_MLFLOW = True
except ImportError:
    HAS_MLFLOW = False
    mlflow = None
    MlflowClient = None
    MlflowException = Exception


class ModelRegistry:
    """MLflow-based model registry for RL models

    Tracks model versions, metadata, and promotion status using MLflow Model Registry.
    Supports champion/challenger workflow with stage transitions:
    - None → Staging → Production

    Attributes:
        model_name: Registered model name in MLflow
        tracking_uri: MLflow tracking URI
        client: MLflow client instance
    """

    def __init__(
        self,
        model_name: str = "rl_mppo",
        tracking_uri: str | None = None,
    ):
        """
        Args:
            model_name: Model name for registry (default: "rl_mppo")
            tracking_uri: MLflow tracking URI (default: sqlite:///mlflow.db)

        Raises:
            ImportError: If MLflow is not installed
        """
        if not HAS_MLFLOW:
            raise ImportError(
                "MLflow is required for ModelRegistry. "
                "Install with: pip install mlflow>=2.10.0"
            )

        self.model_name = model_name
        self.tracking_uri = tracking_uri or "sqlite:///mlflow.db"

        mlflow.set_tracking_uri(self.tracking_uri)
        self.client = MlflowClient()

        # Ensure registered model exists
        try:
            self.client.get_registered_model(model_name)
            logger.info(f"ModelRegistry initialized: {model_name}")
        except MlflowException:
            # Create registered model if it doesn't exist
            self.client.create_registered_model(
                model_name,
                description=f"RL model registry for {model_name}",
            )
            logger.info(f"Created new registered model: {model_name}")

    def register_model(
        self,
        model_path: str | Path,
        metrics: dict[str, float],
        metadata: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> str:
        """Register a new model version

        Args:
            model_path: Path to model artifact (e.g., .zip file)
            metrics: Model performance metrics (sharpe, win_rate, max_dd, etc.)
            metadata: Additional metadata (data_range, hyperparams, etc.)
            run_id: MLflow run ID (if from a training run)

        Returns:
            Model version number as string

        Raises:
            FileNotFoundError: If model_path doesn't exist
        """
        model_path = Path(model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        # Log model artifact to MLflow
        if run_id is None:
            # Create a new run if not provided
            with mlflow.start_run() as run:
                run_id = run.info.run_id
                mlflow.log_artifact(str(model_path), "model")
                mlflow.log_metrics(metrics)
                if metadata:
                    mlflow.log_params(metadata)
                artifact_uri = f"runs:/{run_id}/model"
        else:
            artifact_uri = f"runs:/{run_id}/model"

        # Register model version
        model_version = self.client.create_model_version(
            name=self.model_name,
            source=artifact_uri,
            run_id=run_id,
        )

        # Add metadata tags
        version_num = model_version.version
        self.client.set_model_version_tag(
            self.model_name,
            version_num,
            "registered_at",
            datetime.now().isoformat(),
        )
        self.client.set_model_version_tag(
            self.model_name,
            version_num,
            "sharpe",
            str(metrics.get("sharpe", "N/A")),
        )
        self.client.set_model_version_tag(
            self.model_name,
            version_num,
            "win_rate",
            str(metrics.get("win_rate", "N/A")),
        )
        self.client.set_model_version_tag(
            self.model_name,
            version_num,
            "max_dd",
            str(metrics.get("max_dd", "N/A")),
        )

        if metadata:
            for key, value in metadata.items():
                self.client.set_model_version_tag(
                    self.model_name,
                    version_num,
                    key,
                    str(value),
                )

        logger.info(
            f"Registered model version {version_num}: "
            f"sharpe={metrics.get('sharpe', 'N/A')}, "
            f"win_rate={metrics.get('win_rate', 'N/A')}"
        )

        return str(version_num)

    def get_champion(self) -> dict[str, Any] | None:
        """Get current production champion model

        Returns:
            Model info dict with version, metrics, stage, etc.
            None if no production model exists
        """
        try:
            versions = self.client.get_latest_versions(
                self.model_name,
                stages=["Production"],
            )
            if not versions:
                logger.warning(f"No production model found for {self.model_name}")
                return None

            version = versions[0]
            return self._version_to_dict(version)

        except MlflowException as e:
            logger.error(f"Failed to get champion: {e}")
            return None

    def get_challenger(self) -> dict[str, Any] | None:
        """Get latest staging challenger model

        Returns:
            Model info dict with version, metrics, stage, etc.
            None if no staging model exists
        """
        try:
            versions = self.client.get_latest_versions(
                self.model_name,
                stages=["Staging"],
            )
            if not versions:
                logger.debug(f"No staging model found for {self.model_name}")
                return None

            version = versions[0]
            return self._version_to_dict(version)

        except MlflowException as e:
            logger.error(f"Failed to get challenger: {e}")
            return None

    def get_model(self, version: int | str | None = None) -> dict[str, Any] | None:
        """Get model by version number

        Args:
            version: Model version number (default: latest)

        Returns:
            Model info dict, or None if not found
        """
        try:
            if version is None:
                versions = self.client.search_model_versions(
                    f"name='{self.model_name}'"
                )
                if not versions:
                    return None
                version = max(int(v.version) for v in versions)

            model_version = self.client.get_model_version(
                self.model_name,
                str(version),
            )
            return self._version_to_dict(model_version)

        except MlflowException as e:
            logger.error(f"Failed to get model version {version}: {e}")
            return None

    def promote_model(
        self,
        version: int | str,
        stage: str = "Production",
        archive_current: bool = True,
    ) -> bool:
        """Promote model to a stage (Staging or Production)

        Args:
            version: Model version to promote
            stage: Target stage ("Staging" or "Production")
            archive_current: Archive current production model if promoting to Production

        Returns:
            True if promotion successful, False otherwise
        """
        try:
            if stage not in ["Staging", "Production"]:
                logger.error(f"Invalid stage: {stage}. Must be Staging or Production")
                return False

            # Archive current production model if requested
            if archive_current and stage == "Production":
                current = self.get_champion()
                if current:
                    self.client.transition_model_version_stage(
                        self.model_name,
                        current["version"],
                        "Archived",
                    )
                    logger.info(
                        f"Archived previous champion version {current['version']}"
                    )

            # Promote new model
            self.client.transition_model_version_stage(
                self.model_name,
                str(version),
                stage,
            )

            # Add promotion timestamp
            self.client.set_model_version_tag(
                self.model_name,
                str(version),
                f"promoted_to_{stage.lower()}_at",
                datetime.now().isoformat(),
            )

            logger.info(f"Promoted model version {version} to {stage}")
            return True

        except MlflowException as e:
            logger.error(f"Failed to promote model version {version}: {e}")
            return False

    def rollback_model(self) -> bool:
        """Rollback to previous production model

        Demotes current production model and promotes previous archived model.

        Returns:
            True if rollback successful, False otherwise
        """
        try:
            # Get current production model
            current = self.get_champion()
            if not current:
                logger.error("No current production model to rollback from")
                return False

            # Find previous production model (most recent archived)
            versions = self.client.get_latest_versions(
                self.model_name,
                stages=["Archived"],
            )
            if not versions:
                logger.error("No archived model available for rollback")
                return False

            # Sort by version number to get most recent
            versions.sort(key=lambda v: int(v.version), reverse=True)
            previous = versions[0]

            # Demote current production
            self.client.transition_model_version_stage(
                self.model_name,
                current["version"],
                "Archived",
            )

            # Promote previous archived
            self.client.transition_model_version_stage(
                self.model_name,
                previous.version,
                "Production",
            )

            # Add rollback tags
            self.client.set_model_version_tag(
                self.model_name,
                previous.version,
                "rollback_at",
                datetime.now().isoformat(),
            )
            self.client.set_model_version_tag(
                self.model_name,
                current["version"],
                "demoted_at",
                datetime.now().isoformat(),
            )

            logger.info(
                f"Rolled back from version {current['version']} "
                f"to version {previous.version}"
            )
            return True

        except MlflowException as e:
            logger.error(f"Failed to rollback model: {e}")
            return False

    def list_versions(self, stage: str | None = None) -> list[dict[str, Any]]:
        """List all model versions

        Args:
            stage: Filter by stage (Production, Staging, Archived, None)

        Returns:
            List of model version dicts
        """
        try:
            if stage:
                versions = self.client.get_latest_versions(
                    self.model_name,
                    stages=[stage],
                )
            else:
                versions = self.client.search_model_versions(
                    f"name='{self.model_name}'"
                )

            return [self._version_to_dict(v) for v in versions]

        except MlflowException as e:
            logger.error(f"Failed to list model versions: {e}")
            return []

    def _version_to_dict(self, version: Any) -> dict[str, Any]:
        """Convert MLflow ModelVersion to dict

        Args:
            version: MLflow ModelVersion object

        Returns:
            Dict with version info and metadata
        """
        tags = {tag.key: tag.value for tag in version.tags}

        return {
            "version": version.version,
            "stage": version.current_stage,
            "source": version.source,
            "run_id": version.run_id,
            "created_at": version.creation_timestamp,
            "metrics": {
                "sharpe": float(tags.get("sharpe", 0.0))
                if tags.get("sharpe", "N/A") != "N/A"
                else None,
                "win_rate": float(tags.get("win_rate", 0.0))
                if tags.get("win_rate", "N/A") != "N/A"
                else None,
                "max_dd": float(tags.get("max_dd", 0.0))
                if tags.get("max_dd", "N/A") != "N/A"
                else None,
            },
            "metadata": {
                k: v
                for k, v in tags.items()
                if k not in ["sharpe", "win_rate", "max_dd", "registered_at"]
            },
            "registered_at": tags.get("registered_at"),
        }
