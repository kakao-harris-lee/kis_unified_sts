"""Helpers for presenting trust and selection warnings for hybrid RL datasets."""

from __future__ import annotations

from typing import Any


def build_hybrid_manifest_warning(rules: dict[str, Any] | None, *, mode: str) -> dict[str, str] | None:
    """Return a user-facing warning payload when the manifest is not final-selection safe."""

    normalized_rules = rules or {}
    if normalized_rules.get("final_selection_allowed", True):
        return None

    mode_label = "training" if mode == "train" else "evaluation"
    recommendation = "Use this run for pretraining, smoke validation, or pipeline checks only."

    if normalized_rules.get("bootstrap_mode", False):
        return {
            "warning_code": "bootstrap_no_real_holdout",
            "warning": (
                f"Bootstrap {mode_label} only: no authentic real KOSPI holdout is available. "
                f"Do not use this {mode_label} result for final model selection."
            ),
            "recommendation": recommendation,
        }

    if not normalized_rules.get("real_catalog_authentic", True):
        source_mode = normalized_rules.get("real_catalog_source_mode", "unknown")
        return {
            "warning_code": "fallback_real_catalog",
            "warning": (
                f"Non-final {mode_label}: the real regime catalog is not authentic KOSPI data "
                f"(source_mode={source_mode}). The holdout may be labeled 'real', but it originated "
                f"from fallback/sample data. Do not use this {mode_label} result for final model selection."
            ),
            "recommendation": recommendation,
        }

    if not normalized_rules.get("test_is_real_only", True):
        return {
            "warning_code": "non_real_holdout",
            "warning": (
                f"Non-final {mode_label}: the holdout split is not real-only KOSPI data. "
                f"Do not use this {mode_label} result for final model selection."
            ),
            "recommendation": recommendation,
        }

    return {
        "warning_code": "selection_guard_blocked",
        "warning": (
            f"Non-final {mode_label}: the manifest blocks final selection. "
            f"Review manifest rules before using this {mode_label} result for model ranking."
        ),
        "recommendation": recommendation,
    }
