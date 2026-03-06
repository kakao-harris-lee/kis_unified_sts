"""Tests for CORS security configuration."""

import os
from unittest.mock import patch


class TestCORSSecurity:
    """Test CORS configuration security."""

    def test_development_cors_methods_explicit(self):
        """Development mode should use explicit allowed methods."""
        from services.api.app import _get_cors_config

        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            cors_config = _get_cors_config({})

        # Should not allow all methods
        assert cors_config["allow_methods"] != ["*"]

        # Should have explicit list
        assert "GET" in cors_config["allow_methods"]
        assert "POST" in cors_config["allow_methods"]
        assert "PUT" in cors_config["allow_methods"]
        assert "DELETE" in cors_config["allow_methods"]

    def test_development_cors_headers_explicit(self):
        """Development mode should use explicit allowed headers."""
        from services.api.app import _get_cors_config

        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            cors_config = _get_cors_config({})

        # Should not allow all headers
        assert cors_config["allow_headers"] != ["*"]

        # Should have explicit list
        assert "Content-Type" in cors_config["allow_headers"]
        assert "Authorization" in cors_config["allow_headers"]
        assert "X-API-Key" in cors_config["allow_headers"]

    def test_production_cors_strict(self):
        """Production mode should have strict CORS settings."""
        from services.api.app import _get_cors_config

        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            cors_config = _get_cors_config({})

        # Credentials with wildcard origins is insecure
        if cors_config.get("allow_credentials"):
            assert cors_config["allow_origins"] != ["*"]

        # Should have explicit methods and headers
        assert cors_config["allow_methods"] != ["*"]
        assert cors_config["allow_headers"] != ["*"]

    def test_cors_options_method_included(self):
        """OPTIONS method should be included for preflight requests."""
        from services.api.app import _get_cors_config

        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            cors_config = _get_cors_config({})

        assert "OPTIONS" in cors_config["allow_methods"]

    def test_development_cors_respects_config_override(self):
        """Development mode should respect custom config values."""
        from services.api.app import _get_cors_config

        custom_config = {
            "cors": {
                "allowed_methods": ["GET", "POST"],  # Custom subset
                "allowed_headers": ["Content-Type", "X-Custom-Header"],
            }
        }

        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            cors_config = _get_cors_config(custom_config)

        # Should use custom values, not defaults
        assert cors_config["allow_methods"] == ["GET", "POST"]
        assert "X-Custom-Header" in cors_config["allow_headers"]

    def test_production_cors_respects_config(self):
        """Production mode should respect config values."""
        from services.api.app import _get_cors_config

        custom_config = {
            "cors": {
                "allowed_origins": ["https://example.com"],
                "allowed_methods": ["GET", "POST"],
                "allowed_headers": ["Content-Type"],
            }
        }

        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            cors_config = _get_cors_config(custom_config)

        assert cors_config["allow_methods"] == ["GET", "POST"]
        assert cors_config["allow_headers"] == ["Content-Type"]

    def test_dashboard_cors_credentials_security(self):
        """Dashboard should never combine wildcard origins with credentials."""
        from services.dashboard.app import _get_cors_config

        # Test development mode
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            dev_cors_config = _get_cors_config({})

            # If credentials are enabled, origins must not be wildcard
            if dev_cors_config.get("allow_credentials"):
                assert dev_cors_config["allow_origins"] != ["*"], \
                    "Development mode combines allow_credentials=True with wildcard origins"
                # Should have explicit localhost origins
                assert isinstance(dev_cors_config["allow_origins"], list), \
                    "allow_origins should be a list"
                assert len(dev_cors_config["allow_origins"]) > 0, \
                    "allow_origins should not be empty when credentials enabled"
                # Verify they are localhost origins
                for origin in dev_cors_config["allow_origins"]:
                    assert "localhost" in origin or "127.0.0.1" in origin, \
                        f"Development origin should be localhost, got: {origin}"

        # Test production mode
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            prod_cors_config = _get_cors_config({})

            # If credentials are enabled, origins must not be wildcard
            if prod_cors_config.get("allow_credentials"):
                assert prod_cors_config["allow_origins"] != ["*"], \
                    "Production mode combines allow_credentials=True with wildcard origins"

        # Test with custom config that tries to use wildcard (should be overridden)
        custom_config_wildcard = {
            "cors": {
                "allowed_origins": ["*"],
                "allow_credentials": True,
            }
        }

        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            cors_config = _get_cors_config(custom_config_wildcard)

            # Even if config says wildcard, development should use explicit localhost
            if cors_config.get("allow_credentials"):
                assert cors_config["allow_origins"] != ["*"], \
                    "Should not use wildcard origins from config when credentials enabled"
