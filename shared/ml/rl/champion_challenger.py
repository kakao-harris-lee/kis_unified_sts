"""Champion/Challenger Model Evaluation

Compares RL model performance to determine if a new challenger model should be
promoted to production champion. Implements threshold validation and generates
detailed comparison reports for audit trail.

Usage:
    evaluator = ChampionChallengerEvaluator()

    # Compare two models
    comparison = evaluator.compare_models(
        champion_model=champion,
        challenger_model=challenger,
        test_days=test_days,
        test_prices=test_prices
    )

    # Check if challenger should be promoted
    should_promote = evaluator.should_promote(
        challenger_metrics=comparison['challenger'],
        champion_metrics=comparison['champion']
    )

    # Generate detailed report
    report = evaluator.generate_comparison_report(
        comparison['challenger'],
        comparison['champion']
    )
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from shared.config import ConfigLoader
from shared.ml.rl.evaluator import RLEvaluator

logger = logging.getLogger(__name__)


class ChampionChallengerEvaluator:
    """Champion/Challenger model comparison and promotion logic

    Uses RLEvaluator to assess model performance and applies configurable
    thresholds to determine if a challenger model should replace the current
    production champion.

    Promotion criteria:
    1. Absolute thresholds: Challenger must meet minimum Sharpe, win rate, max drawdown
    2. Relative improvement: Challenger must improve primary metric by min_improvement_pct
    3. No critical regression: Challenger must not significantly worsen any key metric
    """

    def __init__(self, config_path: str = "ml/retraining_pipeline.yaml"):
        """Initialize champion/challenger evaluator

        Args:
            config_path: Path to retraining pipeline config file
        """
        self.config = ConfigLoader.load(config_path)
        self.thresholds = self.config.get("thresholds", {})
        self.evaluation_config = self.config.get("evaluation", {})

        # Initialize RL evaluator (uses base rl_mppo config)
        base_config = self.config.get("training", {}).get(
            "base_config",
            "ml/rl_mppo.yaml"
        )
        self.rl_evaluator = RLEvaluator(config_path=base_config)

        logger.info(
            f"ChampionChallengerEvaluator initialized with config: {config_path}"
        )

    def compare_models(
        self,
        champion_model: Any,
        challenger_model: Any,
        test_days: list[np.ndarray],
        test_prices: list[np.ndarray],
        slippage: float = 0.0,
        deterministic: bool = True,
        continuous: bool = False,
        is_dt: bool = False,
        test_aux: list[np.ndarray] | None = None,
    ) -> dict[str, dict[str, float]]:
        """Compare champion and challenger model performance

        Args:
            champion_model: Current production model
            challenger_model: New model to evaluate
            test_days: Test data (daily features)
            test_prices: Test data (daily OHLC prices)
            slippage: Slippage to apply during evaluation
            deterministic: Use deterministic actions
            continuous: True if models use continuous action space
            is_dt: True if using Decision Transformer
            test_aux: Auxiliary test features (e.g., TFT probs)

        Returns:
            Dict with 'champion' and 'challenger' keys containing evaluation metrics
        """
        logger.info("Evaluating champion model...")
        champion_metrics = self.rl_evaluator.evaluate_model(
            model=champion_model,
            test_days=test_days,
            test_prices=test_prices,
            slippage=slippage,
            deterministic=deterministic,
            continuous=continuous,
            is_dt=is_dt,
            test_aux=test_aux,
        )

        logger.info("Evaluating challenger model...")
        challenger_metrics = self.rl_evaluator.evaluate_model(
            model=challenger_model,
            test_days=test_days,
            test_prices=test_prices,
            slippage=slippage,
            deterministic=deterministic,
            continuous=continuous,
            is_dt=is_dt,
            test_aux=test_aux,
        )

        # Calculate improvement metrics
        improvement = self.calculate_improvement(
            challenger_metrics=challenger_metrics,
            champion_metrics=champion_metrics
        )

        logger.info(
            f"Champion: Sharpe={champion_metrics['sharpe_ratio']:.2f}, "
            f"Win Rate={champion_metrics['win_rate_pct']:.1f}%, "
            f"Max DD={champion_metrics['max_drawdown_pct']:.2f}%"
        )
        logger.info(
            f"Challenger: Sharpe={challenger_metrics['sharpe_ratio']:.2f}, "
            f"Win Rate={challenger_metrics['win_rate_pct']:.1f}%, "
            f"Max DD={challenger_metrics['max_drawdown_pct']:.2f}%"
        )
        logger.info(
            f"Improvement: Sharpe={improvement['sharpe_improvement_pct']:.1f}%, "
            f"Win Rate={improvement['win_rate_improvement_pct']:.1f}%"
        )

        return {
            "champion": champion_metrics,
            "challenger": challenger_metrics,
            "improvement": improvement,
        }

    def should_promote(
        self,
        challenger_metrics: dict[str, float],
        champion_metrics: dict[str, float] | None = None,
    ) -> tuple[bool, str]:
        """Determine if challenger should be promoted to production

        Applies three-level validation:
        1. Absolute thresholds: min_sharpe_ratio, min_win_rate, max_drawdown_threshold
        2. Relative improvement: min_improvement_pct vs champion
        3. Critical regression check: No catastrophic degradation in any metric

        Args:
            challenger_metrics: Challenger model evaluation metrics
                Can use either full format (sharpe_ratio, win_rate_pct, max_drawdown_pct)
                or simplified format (sharpe, win_rate, max_dd)
            champion_metrics: Champion model evaluation metrics (None if no champion exists)

        Returns:
            Tuple of (should_promote: bool, reason: str)
        """
        # Extract thresholds from config
        min_sharpe = self.thresholds.get("min_sharpe_ratio", 1.0)
        min_win_rate = self.thresholds.get("min_win_rate", 0.45)
        max_dd_threshold = self.thresholds.get("max_drawdown_threshold", -0.20)
        min_improvement_pct = self.thresholds.get("min_improvement_pct", 0.05)
        min_sharpe_improvement = self.thresholds.get("min_sharpe_improvement", 0.10)

        # Normalize metrics to standard format (handle both full and simplified keys)
        challenger_sharpe = self._get_metric(challenger_metrics, "sharpe_ratio", "sharpe")
        challenger_win_rate = self._get_metric(challenger_metrics, "win_rate_pct", "win_rate")
        challenger_max_dd = self._get_metric(challenger_metrics, "max_drawdown_pct", "max_dd")

        # Convert percentages to decimals if needed (RLEvaluator returns percentages)
        if "win_rate_pct" in challenger_metrics:
            challenger_win_rate = challenger_win_rate / 100.0
        if "max_drawdown_pct" in challenger_metrics:
            challenger_max_dd = challenger_max_dd / 100.0

        # Check 1: Absolute thresholds
        if challenger_sharpe < min_sharpe:
            reason = (
                f"Challenger Sharpe ({challenger_sharpe:.2f}) below minimum "
                f"threshold ({min_sharpe:.2f})"
            )
            logger.warning(f"Promotion rejected: {reason}")
            return False, reason

        if challenger_win_rate < min_win_rate:
            reason = (
                f"Challenger win rate ({challenger_win_rate:.2%}) below minimum "
                f"threshold ({min_win_rate:.2%})"
            )
            logger.warning(f"Promotion rejected: {reason}")
            return False, reason

        if challenger_max_dd < max_dd_threshold:
            reason = (
                f"Challenger max drawdown ({challenger_max_dd:.2%}) exceeds maximum "
                f"threshold ({max_dd_threshold:.2%})"
            )
            logger.warning(f"Promotion rejected: {reason}")
            return False, reason

        # Check 2: Relative improvement (if champion exists)
        if champion_metrics is not None:
            champion_sharpe = self._get_metric(champion_metrics, "sharpe_ratio", "sharpe")
            champion_win_rate = self._get_metric(champion_metrics, "win_rate_pct", "win_rate")

            # Convert percentages to decimals if needed
            if "win_rate_pct" in champion_metrics:
                champion_win_rate = champion_win_rate / 100.0

            # Calculate improvement
            sharpe_improvement = challenger_sharpe - champion_sharpe
            sharpe_improvement_pct = (
                (challenger_sharpe - champion_sharpe) / abs(champion_sharpe)
                if champion_sharpe != 0 else 0
            )

            # Require minimum improvement in primary metric (Sharpe)
            if sharpe_improvement < min_sharpe_improvement:
                reason = (
                    f"Challenger Sharpe improvement ({sharpe_improvement:.2f}) below "
                    f"minimum threshold ({min_sharpe_improvement:.2f})"
                )
                logger.warning(f"Promotion rejected: {reason}")
                return False, reason

            if sharpe_improvement_pct < min_improvement_pct:
                reason = (
                    f"Challenger Sharpe improvement ({sharpe_improvement_pct:.1%}) below "
                    f"minimum threshold ({min_improvement_pct:.1%})"
                )
                logger.warning(f"Promotion rejected: {reason}")
                return False, reason

            # Check 3: Critical regression check
            # Allow some degradation in secondary metrics, but not catastrophic
            max_allowed_regression = 0.10  # Allow up to 10% regression in secondary metrics

            win_rate_regression = (champion_win_rate - challenger_win_rate) / champion_win_rate
            if win_rate_regression > max_allowed_regression:
                reason = (
                    f"Critical regression in win rate: {win_rate_regression:.1%} degradation "
                    f"exceeds maximum allowed ({max_allowed_regression:.1%})"
                )
                logger.warning(f"Promotion rejected: {reason}")
                return False, reason

        # All checks passed
        if champion_metrics is not None:
            reason = (
                f"Challenger passes all thresholds with {sharpe_improvement:.2f} "
                f"Sharpe improvement ({sharpe_improvement_pct:.1%})"
            )
        else:
            reason = (
                f"First model deployment - challenger meets all absolute thresholds "
                f"(Sharpe={challenger_sharpe:.2f}, WinRate={challenger_win_rate:.1%})"
            )

        logger.info(f"Promotion approved: {reason}")
        return True, reason

    def calculate_improvement(
        self,
        challenger_metrics: dict[str, float],
        champion_metrics: dict[str, float],
    ) -> dict[str, float]:
        """Calculate improvement metrics comparing challenger to champion

        Args:
            challenger_metrics: Challenger evaluation metrics
            champion_metrics: Champion evaluation metrics

        Returns:
            Dict with improvement percentages and absolute differences
        """
        def safe_pct_change(new: float, old: float) -> float:
            """Calculate percentage change, handling zero/negative cases"""
            if old == 0:
                return 0.0
            return ((new - old) / abs(old)) * 100.0

        # Calculate improvements
        sharpe_improvement = (
            challenger_metrics["sharpe_ratio"] - champion_metrics["sharpe_ratio"]
        )
        sharpe_improvement_pct = safe_pct_change(
            challenger_metrics["sharpe_ratio"],
            champion_metrics["sharpe_ratio"]
        )

        win_rate_improvement = (
            challenger_metrics["win_rate_pct"] - champion_metrics["win_rate_pct"]
        )
        win_rate_improvement_pct = safe_pct_change(
            challenger_metrics["win_rate_pct"],
            champion_metrics["win_rate_pct"]
        )

        # For max drawdown, improvement means less negative (closer to 0)
        max_dd_improvement = (
            challenger_metrics["max_drawdown_pct"] - champion_metrics["max_drawdown_pct"]
        )
        max_dd_improvement_pct = safe_pct_change(
            challenger_metrics["max_drawdown_pct"],
            champion_metrics["max_drawdown_pct"]
        )

        return_improvement = (
            challenger_metrics["avg_return_pct"] - champion_metrics["avg_return_pct"]
        )
        return_improvement_pct = safe_pct_change(
            challenger_metrics["avg_return_pct"],
            champion_metrics["avg_return_pct"]
        )

        return {
            "sharpe_improvement": round(sharpe_improvement, 2),
            "sharpe_improvement_pct": round(sharpe_improvement_pct, 1),
            "win_rate_improvement": round(win_rate_improvement, 1),
            "win_rate_improvement_pct": round(win_rate_improvement_pct, 1),
            "max_dd_improvement": round(max_dd_improvement, 2),
            "max_dd_improvement_pct": round(max_dd_improvement_pct, 1),
            "return_improvement": round(return_improvement, 2),
            "return_improvement_pct": round(return_improvement_pct, 1),
        }

    def generate_comparison_report(
        self,
        challenger_metrics: dict[str, float],
        champion_metrics: dict[str, float] | None = None,
        improvement: dict[str, float] | None = None,
        promotion_decision: tuple[bool, str] | None = None,
    ) -> dict[str, Any]:
        """Generate detailed comparison report for audit trail

        Args:
            challenger_metrics: Challenger evaluation metrics
            champion_metrics: Champion evaluation metrics (None if no champion)
            improvement: Pre-calculated improvement metrics (optional)
            promotion_decision: Tuple of (should_promote, reason) (optional)

        Returns:
            Comprehensive comparison report dict suitable for MLflow logging
        """
        # Calculate improvement if not provided
        if improvement is None and champion_metrics is not None:
            improvement = self.calculate_improvement(
                challenger_metrics=challenger_metrics,
                champion_metrics=champion_metrics
            )

        # Make promotion decision if not provided
        if promotion_decision is None:
            should_promote, reason = self.should_promote(
                challenger_metrics=challenger_metrics,
                champion_metrics=champion_metrics
            )
        else:
            should_promote, reason = promotion_decision

        # Build report
        report: dict[str, Any] = {
            "challenger": {
                "sharpe_ratio": challenger_metrics["sharpe_ratio"],
                "win_rate_pct": challenger_metrics["win_rate_pct"],
                "max_drawdown_pct": challenger_metrics["max_drawdown_pct"],
                "avg_return_pct": challenger_metrics["avg_return_pct"],
                "total_trades": challenger_metrics["total_trades"],
                "rr_ratio": challenger_metrics.get("rr_ratio", 0.0),
            },
            "promotion_decision": {
                "approved": should_promote,
                "reason": reason,
                "timestamp": None,  # Will be set by caller
            },
            "thresholds": {
                "min_sharpe_ratio": self.thresholds.get("min_sharpe_ratio", 1.0),
                "min_win_rate": self.thresholds.get("min_win_rate", 0.45),
                "max_drawdown_threshold": self.thresholds.get("max_drawdown_threshold", -0.20),
                "min_improvement_pct": self.thresholds.get("min_improvement_pct", 0.05),
            },
        }

        # Add champion and improvement data if available
        if champion_metrics is not None:
            report["champion"] = {
                "sharpe_ratio": champion_metrics["sharpe_ratio"],
                "win_rate_pct": champion_metrics["win_rate_pct"],
                "max_drawdown_pct": champion_metrics["max_drawdown_pct"],
                "avg_return_pct": champion_metrics["avg_return_pct"],
                "total_trades": champion_metrics["total_trades"],
                "rr_ratio": champion_metrics.get("rr_ratio", 0.0),
            }
        else:
            report["champion"] = None

        if improvement is not None:
            report["improvement"] = improvement
        else:
            report["improvement"] = None

        # Add risk assessment
        report["risk_assessment"] = self._assess_risk(
            challenger_metrics=challenger_metrics,
            champion_metrics=champion_metrics,
            improvement=improvement,
        )

        return report

    def _get_metric(
        self,
        metrics: dict[str, float],
        primary_key: str,
        fallback_key: str
    ) -> float:
        """Get metric value with fallback to alternative key

        Supports both RLEvaluator format (sharpe_ratio, win_rate_pct, max_drawdown_pct)
        and simplified format (sharpe, win_rate, max_dd)

        Args:
            metrics: Metrics dictionary
            primary_key: Primary key to look for (e.g., "sharpe_ratio")
            fallback_key: Fallback key if primary not found (e.g., "sharpe")

        Returns:
            Metric value

        Raises:
            KeyError: If neither key exists in metrics
        """
        if primary_key in metrics:
            return metrics[primary_key]
        elif fallback_key in metrics:
            return metrics[fallback_key]
        else:
            raise KeyError(
                f"Metric not found. Expected either '{primary_key}' or '{fallback_key}' "
                f"in metrics dict. Available keys: {list(metrics.keys())}"
            )

    def _assess_risk(
        self,
        challenger_metrics: dict[str, float],
        champion_metrics: dict[str, float] | None,
        improvement: dict[str, float] | None,
    ) -> dict[str, Any]:
        """Assess deployment risk of challenger model

        Args:
            challenger_metrics: Challenger evaluation metrics
            champion_metrics: Champion evaluation metrics
            improvement: Improvement metrics

        Returns:
            Risk assessment dict with level and factors
        """
        risk_factors = []

        # Check for low sample size
        if challenger_metrics["total_trades"] < self.evaluation_config.get("min_sample_size", 30):
            risk_factors.append(
                f"Low sample size ({challenger_metrics['total_trades']} trades)"
            )

        # Check for volatile performance
        if challenger_metrics.get("daily_returns"):
            returns = challenger_metrics["daily_returns"]
            if len(returns) > 1:
                volatility = float(np.std(returns))
                if volatility > 0.05:  # 5% daily volatility
                    risk_factors.append(f"High daily volatility ({volatility:.1%})")

        # Check for marginal improvement
        if improvement and champion_metrics:
            if improvement["sharpe_improvement_pct"] < 10:  # Less than 10% improvement
                risk_factors.append(
                    f"Marginal Sharpe improvement ({improvement['sharpe_improvement_pct']:.1f}%)"
                )

        # Determine risk level
        if len(risk_factors) == 0:
            risk_level = "LOW"
        elif len(risk_factors) <= 2:
            risk_level = "MEDIUM"
        else:
            risk_level = "HIGH"

        return {
            "level": risk_level,
            "factors": risk_factors,
            "recommendation": (
                "Safe to deploy" if risk_level == "LOW"
                else "Monitor closely after deployment" if risk_level == "MEDIUM"
                else "Consider paper trading validation before production"
            ),
        }
