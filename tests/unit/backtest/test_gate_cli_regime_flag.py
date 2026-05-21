import importlib.util
import pathlib

_REPO = pathlib.Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "gfs", _REPO / "scripts" / "gate_futures_strategy.py")
gfs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gfs)


def test_gate_yaml_loader_minimal(tmp_path):
    y = tmp_path / "g.yaml"
    y.write_text(
        "regime_percentile_max: 75.0\n"
        "impact_score_max: 60\n"
        "event_window_minutes: 10\n"
        "require_overnight_us_direction: false\n"
        "permissive_on_missing: true\n")
    cfg = gfs.load_gate_config(str(y))
    assert cfg.regime_percentile_max == 75.0
    assert cfg.impact_score_max == 60
    assert cfg.event_window_minutes == 10
    assert cfg.require_overnight_us_direction is False
    assert cfg.permissive_on_missing is True


def test_head_to_head_delta_computation():
    # Δ = gated OOS Sharpe − baseline OOS Sharpe; pass iff Δ ≥ delta AND
    # gated MDD ≤ baseline MDD AND rescoped_gate(study_gated, oos_gated).pass
    baseline = {"sharpe_ratio": 5.0, "max_drawdown_pct": 4.5}
    gated = {"sharpe_ratio": 5.8, "max_drawdown_pct": 4.0}
    ok, delta = gfs.head_to_head_verdict(
        baseline_oos=baseline, gated_oos=gated, delta_min=0.5,
        gated_gate_pass=True)
    assert ok is True
    assert round(delta, 4) == 0.8

    # Δ below threshold → FAIL
    ok2, _ = gfs.head_to_head_verdict(
        baseline_oos=baseline, gated_oos={"sharpe_ratio": 5.2,
                                           "max_drawdown_pct": 4.0},
        delta_min=0.5, gated_gate_pass=True)
    assert ok2 is False

    # MDD worsens → FAIL
    ok3, _ = gfs.head_to_head_verdict(
        baseline_oos=baseline, gated_oos={"sharpe_ratio": 6.0,
                                           "max_drawdown_pct": 6.0},
        delta_min=0.5, gated_gate_pass=True)
    assert ok3 is False


def test_head_to_head_requires_gated_gate_pass():
    # Even with great Δ Sharpe + MDD, FAIL when gated rescoped-gate didn't pass.
    baseline = {"sharpe_ratio": 5.0, "max_drawdown_pct": 4.5}
    gated = {"sharpe_ratio": 10.0, "max_drawdown_pct": 3.0}
    ok, _ = gfs.head_to_head_verdict(
        baseline_oos=baseline, gated_oos=gated, delta_min=0.5,
        gated_gate_pass=False)
    assert ok is False


def test_load_gate_config_empty_yaml(tmp_path):
    # Empty YAML must fall back to all-defaults (no AttributeError on None.get).
    y = tmp_path / "empty.yaml"
    y.write_text("")
    cfg = gfs.load_gate_config(str(y))
    assert cfg.regime_percentile_max == 80.0
    assert cfg.impact_score_max == 70
    assert cfg.event_window_minutes == 15
    assert cfg.require_overnight_us_direction is False
    assert cfg.permissive_on_missing is True
