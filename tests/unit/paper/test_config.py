"""Test paper trading configuration."""


def test_paper_config_defaults():
    """Test PaperTradingConfig default values."""
    from shared.paper.config import PaperTradingConfig

    config = PaperTradingConfig()

    assert config.initial_balance == 10_000_000
    assert config.commission_rate == 0.00015
    assert config.slippage_rate == 0.0001


def test_paper_config_from_yaml(tmp_path):
    """Test loading config from YAML."""
    from shared.paper.config import PaperTradingConfig
    import yaml

    config_file = tmp_path / "paper.yaml"
    config_file.write_text(yaml.dump({
        "initial_balance": 5_000_000,
        "commission_rate": 0.0002,
    }))

    config = PaperTradingConfig.from_yaml(str(config_file))
    assert config.initial_balance == 5_000_000
