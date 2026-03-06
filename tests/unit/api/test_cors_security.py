"""Tests for CORS security configuration."""

import os
from unittest.mock import patch


class TestCORSSecurity:
    """Test CORS configuration security."""

    def test_development_cors_methods_explicit(self):
        """Development mode should use explicit allowed methods."""
        from shared.api.cors import get_cors_config

        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            cors_config = get_cors_config({})

        # Should not allow all methods
        assert cors_config["allow_methods"] != ["*"]

        # Should have explicit list
        assert "GET" in cors_config["allow_methods"]
        assert "POST" in cors_config["allow_methods"]
        assert "PUT" in cors_config["allow_methods"]
        assert "DELETE" in cors_config["allow_methods"]

    def test_development_cors_headers_explicit(self):
        """Development mode should use explicit allowed headers."""
        from shared.api.cors import get_cors_config

        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            cors_config = get_cors_config({})

        # Should not allow all headers
        assert cors_config["allow_headers"] != ["*"]

        # Should have explicit list
        assert "Content-Type" in cors_config["allow_headers"]
        assert "Authorization" in cors_config["allow_headers"]
        assert "X-API-Key" in cors_config["allow_headers"]

    def test_production_cors_strict(self):
        """Production mode should have strict CORS settings."""
        from shared.api.cors import get_cors_config

        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            cors_config = get_cors_config({})

        # Production defaults to no credentials when no origins configured
        assert cors_config["allow_credentials"] is False

        # Should have explicit methods and headers
        assert cors_config["allow_methods"] != ["*"]
        assert cors_config["allow_headers"] != ["*"]

    def test_cors_options_method_included(self):
        """OPTIONS method should be included for preflight requests."""
        from shared.api.cors import get_cors_config

        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            cors_config = get_cors_config({})

        assert "OPTIONS" in cors_config["allow_methods"]

    def test_development_cors_respects_config_override(self):
        """Development mode should respect custom config values."""
        from shared.api.cors import get_cors_config

        custom_config = {
            "cors": {
                "allowed_methods": ["GET", "POST"],  # Custom subset
                "allowed_headers": ["Content-Type", "X-Custom-Header"],
            }
        }

        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            cors_config = get_cors_config(custom_config)

        # Should use custom values, not defaults
        assert cors_config["allow_methods"] == ["GET", "POST"]
        assert "X-Custom-Header" in cors_config["allow_headers"]

    def test_production_cors_respects_config(self):
        """Production mode should respect config values."""
        from shared.api.cors import get_cors_config

        custom_config = {
            "cors": {
                "allowed_origins": ["https://example.com"],
                "allowed_methods": ["GET", "POST"],
                "allowed_headers": ["Content-Type"],
            }
        }

        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            cors_config = get_cors_config(custom_config)

        assert cors_config["allow_methods"] == ["GET", "POST"]
        assert cors_config["allow_headers"] == ["Content-Type"]

    def test_wildcard_origins_blocked_with_credentials(self):
        """Wildcard origins with credentials should be blocked."""
        from shared.api.cors import get_cors_config

        wildcard_config = {
            "cors": {
                "allowed_origins": ["*"],
                "allow_credentials": True,
            }
        }

        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            cors_config = get_cors_config(wildcard_config)

            # Wildcard should be filtered out
            assert "*" not in cors_config["allow_origins"]
            # Should fall back to dev origins
            assert len(cors_config["allow_origins"]) > 0
            for origin in cors_config["allow_origins"]:
                assert "localhost" in origin or "127.0.0.1" in origin

    def test_dashboard_cors_credentials_security(self):
        """Shared CORS module should never combine wildcard origins with credentials."""
        from shared.api.cors import get_cors_config

        # Test development mode
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            dev_cors_config = get_cors_config({})

            # If credentials are enabled, origins must not be wildcard
            if dev_cors_config.get("allow_credentials"):
                assert dev_cors_config["allow_origins"] != ["*"], \
                    "Development mode combines allow_credentials=True with wildcard origins"
                # Should have explicit localhost origins
                assert isinstance(dev_cors_config["allow_origins"], list)
                assert len(dev_cors_config["allow_origins"]) > 0
                for origin in dev_cors_config["allow_origins"]:
                    assert "localhost" in origin or "127.0.0.1" in origin, \
                        f"Development origin should be localhost, got: {origin}"

        # Test production mode
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            prod_cors_config = get_cors_config({})

            # Production defaults to no credentials
            assert prod_cors_config["allow_credentials"] is False
