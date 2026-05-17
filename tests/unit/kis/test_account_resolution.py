"""Tests for `KISClient._resolve_account_no` — fail-fast account resolution.

Verifies the C5 hardening: the legacy single-account env var
``KIS_ACCOUNT_NO`` is no longer silently used as a fallback for either
stock or futures order paths. This prevents the cross-routing footgun
where a futures order would be placed against a stock account (or
vice-versa) just because the legacy env var was set during migration.

Backward compatibility is preserved behind an explicit opt-in:
``KIS_LEGACY_ACCOUNT_FALLBACK=1``.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from shared.kis.client import KISClient


@pytest.fixture(autouse=True)
def _clean_env():
    """Strip account env vars so each test starts from a known state."""
    keys = (
        "KIS_STOCK_ACCOUNT_NO",
        "KIS_FUTURES_ACCOUNT_NO",
        "KIS_ACCOUNT_NO",
        "KIS_LEGACY_ACCOUNT_FALLBACK",
    )
    saved = {k: os.environ.pop(k, None) for k in keys}
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_stock_prefers_explicit_env():
    with patch.dict(os.environ, {"KIS_STOCK_ACCOUNT_NO": "12345678-01"}, clear=False):
        assert KISClient._resolve_account_no("stock") == "12345678-01"


def test_futures_prefers_explicit_env():
    with patch.dict(os.environ, {"KIS_FUTURES_ACCOUNT_NO": "87654321-02"}, clear=False):
        assert KISClient._resolve_account_no("futures") == "87654321-02"


def test_returns_empty_when_unset_and_no_legacy_optin():
    """No KIS_*_ACCOUNT_NO, legacy var set but opt-in flag OFF -> empty.

    This is the primary fail-fast guarantee: legacy KIS_ACCOUNT_NO must
    NOT cross-route silently. Caller's downstream length check raises.
    """
    with patch.dict(os.environ, {"KIS_ACCOUNT_NO": "99999999-01"}, clear=False):
        assert KISClient._resolve_account_no("stock") == ""
        assert KISClient._resolve_account_no("futures") == ""


def test_legacy_fallback_only_when_opt_in_flag_true():
    with patch.dict(
        os.environ,
        {"KIS_ACCOUNT_NO": "99999999-01", "KIS_LEGACY_ACCOUNT_FALLBACK": "1"},
        clear=False,
    ):
        assert KISClient._resolve_account_no("stock") == "99999999-01"
        assert KISClient._resolve_account_no("futures") == "99999999-01"


@pytest.mark.parametrize("flag", ["true", "TRUE", "yes"])
def test_legacy_fallback_accepts_common_truthy_values(flag):
    with patch.dict(
        os.environ,
        {"KIS_ACCOUNT_NO": "11112222-33", "KIS_LEGACY_ACCOUNT_FALLBACK": flag},
        clear=False,
    ):
        assert KISClient._resolve_account_no("stock") == "11112222-33"


def test_explicit_env_always_wins_over_legacy_even_with_optin():
    """Asset-specific env wins even when legacy fallback is enabled."""
    with patch.dict(
        os.environ,
        {
            "KIS_STOCK_ACCOUNT_NO": "10000000-01",
            "KIS_ACCOUNT_NO": "99999999-99",
            "KIS_LEGACY_ACCOUNT_FALLBACK": "1",
        },
        clear=False,
    ):
        assert KISClient._resolve_account_no("stock") == "10000000-01"


def test_unknown_asset_raises():
    with pytest.raises(ValueError, match="unknown asset"):
        KISClient._resolve_account_no("crypto")


def test_empty_env_string_treated_as_unset():
    """Empty string should be treated as not configured."""
    with patch.dict(
        os.environ,
        {"KIS_STOCK_ACCOUNT_NO": "   ", "KIS_ACCOUNT_NO": "12345678-01"},
        clear=False,
    ):
        # Whitespace-only -> falls through to legacy, but legacy opt-in off
        assert KISClient._resolve_account_no("stock") == ""
