"""Tests for hybrid manifest trust warnings."""

from __future__ import annotations

from shared.ml.rl.hybrid_manifest_warnings import build_hybrid_manifest_warning


def test_returns_none_when_manifest_is_final_selection_eligible():
    warning = build_hybrid_manifest_warning(
        {
            "final_selection_allowed": True,
            "bootstrap_mode": False,
            "real_catalog_authentic": True,
            "test_is_real_only": True,
        },
        mode="train",
    )

    assert warning is None


def test_bootstrap_warning_is_explicit_for_training_runs():
    warning = build_hybrid_manifest_warning(
        {
            "final_selection_allowed": False,
            "bootstrap_mode": True,
            "real_catalog_authentic": False,
            "test_is_real_only": False,
        },
        mode="train",
    )

    assert warning is not None
    assert warning["warning_code"] == "bootstrap_no_real_holdout"
    assert "no authentic real KOSPI holdout" in warning["warning"]
    assert "pretraining" in warning["recommendation"]


def test_fallback_warning_is_explicit_for_evaluation_runs():
    warning = build_hybrid_manifest_warning(
        {
            "final_selection_allowed": False,
            "bootstrap_mode": False,
            "real_catalog_authentic": False,
            "real_catalog_source_mode": "sample_fallback",
            "test_is_real_only": True,
        },
        mode="evaluate",
    )

    assert warning is not None
    assert warning["warning_code"] == "fallback_real_catalog"
    assert "source_mode=sample_fallback" in warning["warning"]
    assert "final model selection" in warning["warning"]
