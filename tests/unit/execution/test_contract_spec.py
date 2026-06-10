# tests/unit/execution/test_contract_spec.py
import pytest

from shared.execution.contract_spec import (
    ContractSpec,
    ContractSpecRegistry,
    resolve_contract_spec,
)


def test_contract_spec_exposes_multiplier_tick_value():
    spec = ContractSpec(
        name="kospi200_mini",
        multiplier_krw_per_point=50000,
        tick_size_points=0.02,
        tick_value_krw=1000,
        commission_rate=0.00003,
        symbol_prefix="A05",
    )
    assert spec.multiplier_krw_per_point == 50000
    assert spec.tick_value_krw == 1000


def test_resolve_by_symbol_prefix():
    registry = ContractSpecRegistry(
        specs={
            "kospi200_mini": ContractSpec(
                name="kospi200_mini",
                multiplier_krw_per_point=50000,
                tick_size_points=0.02,
                tick_value_krw=1000,
                commission_rate=0.00003,
                symbol_prefix="A05",
            ),
            "kospi200_full": ContractSpec(
                name="kospi200_full",
                multiplier_krw_per_point=250000,
                tick_size_points=0.05,
                tick_value_krw=12500,
                commission_rate=0.00003,
                symbol_prefix="101",
            ),
        }
    )
    assert resolve_contract_spec("A05603", registry).name == "kospi200_mini"
    assert resolve_contract_spec("101S6000", registry).name == "kospi200_full"


def test_resolve_supports_comma_separated_prefixes():
    """kospi200_full lists both the continuous '101…' (backtest) and the live
    'A01…' front-month prefixes — resolve must match either (F200 paper)."""
    registry = ContractSpecRegistry(
        specs={
            "kospi200_mini": ContractSpec(
                name="kospi200_mini",
                multiplier_krw_per_point=50000,
                tick_size_points=0.02,
                tick_value_krw=1000,
                commission_rate=0.00003,
                symbol_prefix="A05",
            ),
            "kospi200_full": ContractSpec(
                name="kospi200_full",
                multiplier_krw_per_point=250000,
                tick_size_points=0.05,
                tick_value_krw=12500,
                commission_rate=0.00003,
                symbol_prefix="101,A01",
            ),
        }
    )
    # live F200 front-month (A01…) → full
    assert resolve_contract_spec("A01606", registry).name == "kospi200_full"
    # continuous backtest code (101…) → full (unchanged)
    assert resolve_contract_spec("101S6000", registry).name == "kospi200_full"
    # mini still resolves to mini, not full
    assert resolve_contract_spec("A05606", registry).name == "kospi200_mini"


def test_shipped_config_resolves_mini_and_f200():
    """The shipped config/execution.yaml resolves both live front-month products."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[3]
    registry = ContractSpecRegistry.from_yaml(
        str(repo_root / "config" / "execution.yaml")
    )
    assert resolve_contract_spec("A05606", registry).name == "kospi200_mini"
    assert resolve_contract_spec("A01606", registry).name == "kospi200_full"


def test_resolve_unknown_symbol_raises():
    registry = ContractSpecRegistry(specs={})
    with pytest.raises(ValueError, match="no contract spec"):
        resolve_contract_spec("XXX000", registry)


def test_registry_loads_from_yaml(tmp_path):
    y = tmp_path / "execution.yaml"
    y.write_text(
        "futures_contract_spec:\n"
        "  kospi200_mini:\n"
        "    multiplier_krw_per_point: 50000\n"
        "    tick_size_points: 0.02\n"
        "    tick_value_krw: 1000\n"
        "    commission_rate: 0.00003\n"
        "    symbol_prefix: A05\n"
    )
    registry = ContractSpecRegistry.from_yaml(str(y))
    assert registry.specs["kospi200_mini"].multiplier_krw_per_point == 50000
