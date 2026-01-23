"""
KIS Auth Security Tests

Tests for security-critical aspects of KIS authentication,
particularly file permission handling to prevent credential leaks.
"""

import json
import os
import stat
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def test_token_cache_file_created_with_secure_permissions():
    """토큰 캐시 파일이 0o600 권한으로 atomic하게 생성되어야 함

    SECURITY: 토큰 파일이 default 권한으로 생성된 후 chmod하면
    그 사이 world-readable 상태로 노출되는 race condition 발생.
    os.open()으로 파일 생성과 동시에 권한 설정 필요.
    """
    from shared.kis.auth import TokenCache, _save_token_cache_secure

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "token_cache.json"

        # Create test token cache
        cache = TokenCache(
            app_key="test_key",
            token="secret_token_data",
            expires_at=12345.0,
            issued_at="2024-01-01T00:00:00"
        )

        # Save using secure method
        _save_token_cache_secure(cache, cache_path)

        # Verify file exists
        assert cache_path.exists()

        # Verify permissions are exactly 0o600 (owner read/write only)
        file_stat = os.stat(cache_path)
        file_mode = stat.S_IMODE(file_stat.st_mode)
        assert file_mode == 0o600, f"Expected 0o600, got {oct(file_mode)}"

        # Verify content is correct
        with open(cache_path, 'r') as f:
            data = json.load(f)

        assert data["app_key"] == "test_key"
        assert data["token"] == "secret_token_data"


def test_token_cache_secure_save_handles_errors():
    """토큰 저장 실패 시 file descriptor leak 방지"""
    from shared.kis.auth import TokenCache, _save_token_cache_secure

    cache = TokenCache(
        app_key="test",
        token="token",
        expires_at=12345.0,
        issued_at="2024-01-01T00:00:00"
    )

    # Try to save to invalid path (no permission)
    invalid_path = Path("/root/impossible_path/token.json")

    with pytest.raises((OSError, PermissionError)):
        _save_token_cache_secure(cache, invalid_path)


def test_token_cache_no_world_readable_window():
    """토큰 파일이 생성 과정에서 world-readable 상태로 노출되지 않는지 확인

    이 테스트는 개념적 검증용. 실제 race condition은 테스트하기 어려우므로
    구현 자체가 os.open()을 사용하는지 확인하는 것으로 대체.
    """
    from shared.kis.auth import _save_token_cache_secure
    import inspect

    # Check that implementation uses os.open (atomic permission setting)
    source = inspect.getsource(_save_token_cache_secure)

    # Must use os.open with explicit mode
    assert "os.open" in source, "Must use os.open for atomic permission setting"
    assert "0o600" in source, "Must explicitly set 0o600 permission"
