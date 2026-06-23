"""Test GDELTSourceConfig GKG field structure."""


from shared.news.config import GDELTSourceConfig


def test_gdelt_config_gkg_fields():
    """Verify GDELTSourceConfig has GKG fields and lacks DOC fields."""
    c = GDELTSourceConfig()

    # GKG fields should exist
    assert c.gkg_base_url.endswith("/gdeltv2")
    assert isinstance(c.match_keywords, list)
    assert len(c.match_keywords) > 0
    assert "federal reserve" in [k.lower() for k in c.match_keywords]
    assert c.max_records == 20
    assert c.timeout_seconds == 20.0

    # DOC fields should NOT exist
    assert not hasattr(c, "query"), "Should not have 'query' attribute"
    assert not hasattr(c, "timespan"), "Should not have 'timespan' attribute"
    assert not hasattr(c, "sort"), "Should not have 'sort' attribute"


def test_gdelt_config_defaults():
    """Verify GDELTSourceConfig default values."""
    c = GDELTSourceConfig()

    assert c.enabled is False
    assert c.poll_interval_seconds == 600
    assert c.gkg_base_url == "http://data.gdeltproject.org/gdeltv2"
    assert c.match_keywords == [
        "federal reserve",
        "bond yields",
        "equity market",
        "semiconductor",
    ]
    assert c.max_records == 20
    assert c.timeout_seconds == 20.0


def test_gdelt_config_custom_values():
    """Verify GDELTSourceConfig accepts custom values."""
    c = GDELTSourceConfig(
        enabled=True,
        poll_interval_seconds=300,
        gkg_base_url="http://custom.example.com",
        match_keywords=["inflation", "interest rates"],
        max_records=50,
        timeout_seconds=30.0,
    )

    assert c.enabled is True
    assert c.poll_interval_seconds == 300
    assert c.gkg_base_url == "http://custom.example.com"
    assert c.match_keywords == ["inflation", "interest rates"]
    assert c.max_records == 50
    assert c.timeout_seconds == 30.0
