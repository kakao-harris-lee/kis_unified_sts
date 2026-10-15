"""
KIS Auth Security Tests

Tests for security-critical aspects of KIS authentication,
particularly file permission handling to prevent credential leaks.
"""

import inspect
import json
import os
import stat
import tempfile
from pathlib import Path

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
            issued_at="2024-01-01T00:00:00",
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
        with open(cache_path) as f:
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
        issued_at="2024-01-01T00:00:00",
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

    # Check that implementation uses os.open (atomic permission setting)
    source = inspect.getsource(_save_token_cache_secure)

    # Must use os.open with explicit mode
    assert "os.open" in source, "Must use os.open for atomic permission setting"
    assert "0o600" in source, "Must explicitly set 0o600 permission"


def test_is_token_expired_error_detects_kis_code_and_message():
    from shared.kis.auth import is_token_expired_error

    assert is_token_expired_error({"msg_cd": "EGW00123", "msg1": "ignored"})
    assert is_token_expired_error({"rt_cd": "1", "msg1": "기간이 만료된 token 입니다."})
    assert not is_token_expired_error(
        {"msg_cd": "EGW00201", "msg1": "초당 거래건수 초과"}
    )


def test_auth_config_uses_env_token_cache_dir(monkeypatch):
    from shared.kis.auth import KISAuthConfig

    monkeypatch.setenv("KIS_TOKEN_CACHE_DIR", "/app/.cache")

    assert KISAuthConfig(is_real=False).token_cache_path == Path(
        "/app/.cache/.kis_token_mock"
    )
    assert KISAuthConfig(is_real=True).token_cache_path == Path(
        "/app/.cache/.kis_token_real"
    )


@pytest.mark.asyncio
async def test_retry_once_skips_retry_when_not_expired():
    """A healthy first response returns immediately without invalidating."""
    from unittest.mock import MagicMock

    from shared.kis.auth import retry_once_on_token_expiry

    auth_manager = MagicMock()
    attempts: list[int] = []

    async def request_fn(attempt: int) -> str:
        attempts.append(attempt)
        return "ok"

    result = await retry_once_on_token_expiry(
        request_fn, auth_manager, is_expired=lambda r: r == "expired"
    )

    assert result == "ok"
    assert attempts == [0]
    auth_manager.invalidate.assert_not_called()


@pytest.mark.asyncio
async def test_retry_once_invalidates_and_retries_on_expiry():
    """An expired first response triggers exactly one invalidate + one retry."""
    from unittest.mock import MagicMock

    from shared.kis.auth import retry_once_on_token_expiry

    auth_manager = MagicMock()
    attempts: list[int] = []

    async def request_fn(attempt: int) -> str:
        attempts.append(attempt)
        return "expired" if attempt == 0 else "ok"

    result = await retry_once_on_token_expiry(
        request_fn, auth_manager, is_expired=lambda r: r == "expired"
    )

    assert result == "ok"
    assert attempts == [0, 1]
    auth_manager.invalidate.assert_called_once()


@pytest.mark.asyncio
async def test_retry_once_no_retry_when_auth_manager_cannot_invalidate():
    """Without a callable invalidate, resending a stale token is futile and skipped."""
    from shared.kis.auth import retry_once_on_token_expiry

    attempts: list[int] = []

    async def request_fn(attempt: int) -> str:
        attempts.append(attempt)
        return "expired"

    # auth_manager is None: getattr(None, "invalidate", None) is not callable.
    result = await retry_once_on_token_expiry(
        request_fn, None, is_expired=lambda r: r == "expired"
    )

    assert result == "expired"
    assert attempts == [0]


def test_red_a_cache_write_in_progress_never_exposes_a_partial_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A reader mid-write sees the OLD cache, never a prefix of the new one.

    CP-3 (band plan v3, 2026-10-16) runs two processes against ONE fingerprinted
    token cache file: the minute producer and the short-lived band probe. Before
    this, ``_save_token_cache_secure`` opened the destination with ``O_TRUNC``
    and wrote in place — "atomic" was true of create+permission only, not of the
    contents — so a concurrent reader could ``json.load`` a truncated file. The
    damage is not a crash: ``_load_from_cache`` swallows ``JSONDecodeError`` and
    returns False, so the process quietly re-issues a token, and KIS rate-limits
    token issuance.

    The observation is taken deterministically rather than by racing threads:
    the write is split in half, and in between we read the destination exactly
    the way ``_load_from_cache`` does. Under the temp-file + ``os.replace``
    implementation the destination is still the previous file in full. Put the
    ``O_TRUNC`` write back and this read returns half a JSON document, which is
    the mutation.
    """
    from shared.kis import auth as auth_module
    from shared.kis.auth import TokenCache, _save_token_cache_secure

    cache_path = tmp_path / "token_cache.json"
    previous = TokenCache(
        app_key="old_key",
        token="OLD_TOKEN_" + "x" * 400,
        expires_at=1.0,
        issued_at="2026-10-15T08:45:00",
    )
    _save_token_cache_secure(previous, cache_path)
    bytes_before = cache_path.read_bytes()

    real_dumps = json.dumps
    seen: list[bytes | None] = []

    def halved_dump(obj: object, fp: object, **kwargs: object) -> None:
        text = real_dumps(obj, **kwargs)  # type: ignore[arg-type]
        middle = len(text) // 2
        assert middle > 0
        fp.write(text[:middle])  # type: ignore[attr-defined]
        fp.flush()  # type: ignore[attr-defined]
        seen.append(cache_path.read_bytes() if cache_path.exists() else None)
        fp.write(text[middle:])  # type: ignore[attr-defined]

    monkeypatch.setattr(auth_module.json, "dump", halved_dump)
    updated = TokenCache(
        app_key="new_key",
        token="NEW_TOKEN_" + "y" * 400,
        expires_at=2.0,
        issued_at="2026-10-16T08:45:00",
    )
    _save_token_cache_secure(updated, cache_path)
    monkeypatch.undo()

    assert len(seen) == 1, "the write was not intercepted"
    assert seen[0] == bytes_before, "a reader saw neither the old nor the new file"
    # ...and that is the read `_load_from_cache` performs, so spell it out.
    mid_write = TokenCache.from_dict(json.loads(seen[0].decode("utf-8")))
    assert mid_write.app_key == "old_key"
    assert mid_write.token == previous.token

    # The replacement landed, kept 0o600, and left no temp file behind.
    after = TokenCache.from_dict(json.loads(cache_path.read_text(encoding="utf-8")))
    assert after.app_key == "new_key"
    assert after.token == updated.token
    assert stat.S_IMODE(os.stat(cache_path).st_mode) == 0o600
    assert sorted(p.name for p in tmp_path.iterdir()) == [cache_path.name]
