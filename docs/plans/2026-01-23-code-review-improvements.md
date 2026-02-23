# Code Review Improvements Implementation Plan

**Status**: Implemented (2026-01-23)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 코드 리뷰에서 발견된 CRITICAL/HIGH 이슈 20개를 수정하여 Production-ready 상태로 만든다.

**Architecture:** Thread-safety 패턴 적용, 보안 강화, 리소스 관리 개선, 테스트 커버리지 확대

**Tech Stack:** Python 3.11+, asyncio, threading, pytest, pydantic

---

## Phase 1: Security Critical Fixes (즉시)

### Task 1: API 인증 우회 취약점 수정

**Files:**
- Modify: `services/api/auth.py:69-72`
- Test: `tests/unit/api/test_auth.py`

**Step 1: Write the failing test**

```python
# tests/unit/api/test_auth.py
import pytest
import os
from unittest.mock import patch

def test_auth_required_in_production_when_no_api_key():
    """Production 환경에서 API_KEY 미설정 시 예외 발생"""
    with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=False):
        with patch.dict(os.environ, {"API_KEY": ""}, clear=False):
            from services.api.auth import validate_api_key
            with pytest.raises(RuntimeError, match="API_KEY must be set"):
                validate_api_key(None)

def test_auth_bypassed_in_development_when_no_api_key():
    """Development 환경에서는 API_KEY 없이 허용"""
    with patch.dict(os.environ, {"ENVIRONMENT": "development", "API_KEY": ""}, clear=False):
        from services.api.auth import validate_api_key
        # Should not raise, return True
        result = validate_api_key(None)
        assert result is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/api/test_auth.py::test_auth_required_in_production_when_no_api_key -v`
Expected: FAIL (현재 코드는 production에서도 인증 우회)

**Step 3: Write minimal implementation**

```python
# services/api/auth.py - 수정할 부분
import os

def validate_api_key(api_key: str | None) -> bool:
    expected_key = os.getenv("API_KEY")

    if expected_key is None or expected_key == "":
        env = os.getenv("ENVIRONMENT", "production")
        if env == "production":
            raise RuntimeError(
                "API_KEY must be set in production environment. "
                "Set ENVIRONMENT=development to disable authentication."
            )
        logger.warning("API authentication is disabled (API_KEY not set)")
        return True

    if api_key is None:
        return False

    return secrets.compare_digest(api_key, expected_key)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/api/test_auth.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/api/auth.py tests/unit/api/test_auth.py
git commit -m "fix(security): enforce API_KEY in production environment

BREAKING CHANGE: API_KEY environment variable is now required in production.
Set ENVIRONMENT=development to disable authentication for local development."
```

---

### Task 2: 토큰 캐시 파일 권한 Race Condition 수정

**Files:**
- Modify: `shared/kis/auth.py:271-277`
- Test: `tests/unit/kis/test_auth_security.py`

**Step 1: Write the failing test**

```python
# tests/unit/kis/test_auth_security.py
import os
import stat
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

def test_token_cache_file_created_with_secure_permissions():
    """토큰 캐시 파일이 0o600 권한으로 atomic하게 생성되어야 함"""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_path = Path(tmpdir) / "token_cache.json"

        # Mock the cache object
        mock_cache = MagicMock()
        mock_cache.to_dict.return_value = {"token": "secret", "expires": 12345}

        from shared.kis.auth import _save_token_cache_secure
        _save_token_cache_secure(mock_cache, cache_path)

        # Verify file exists and has correct permissions
        assert cache_path.exists()
        file_stat = os.stat(cache_path)
        file_mode = stat.S_IMODE(file_stat.st_mode)
        assert file_mode == 0o600, f"Expected 0o600, got {oct(file_mode)}"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/kis/test_auth_security.py -v`
Expected: FAIL (함수가 존재하지 않음)

**Step 3: Write minimal implementation**

```python
# shared/kis/auth.py - 새 함수 추가 및 기존 코드 수정
import os
import json
from pathlib import Path

def _save_token_cache_secure(cache: "TokenCache", cache_path: Path) -> None:
    """토큰 캐시를 안전한 권한으로 atomic하게 저장"""
    cache_path = Path(cache_path)

    # Create file with secure permissions atomically
    fd = os.open(
        str(cache_path),
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        0o600
    )
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(cache.to_dict(), f, indent=2)
    except Exception:
        # fd is closed by fdopen, but if fdopen fails we need to close
        try:
            os.close(fd)
        except OSError:
            pass
        raise

# 기존 save_token_cache 함수에서 호출
def save_token_cache(cache: "TokenCache", cache_path: str | Path) -> None:
    """토큰 캐시 저장 (public interface)"""
    _save_token_cache_secure(cache, Path(cache_path))
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/kis/test_auth_security.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/kis/auth.py tests/unit/kis/test_auth_security.py
git commit -m "fix(security): atomic file permission for token cache

Use os.open() with explicit mode to prevent race condition where
token file could be world-readable before chmod."
```

---

### Task 3: Path Traversal 취약점 수정

**Files:**
- Modify: `shared/config/loader.py:171-174`
- Test: `tests/unit/config/test_loader_security.py`

**Step 1: Write the failing test**

```python
# tests/unit/config/test_loader_security.py
import pytest
from shared.config.loader import ConfigLoader
from shared.config.exceptions import ConfigError

def test_path_traversal_attack_blocked():
    """Path traversal 공격 차단"""
    with pytest.raises(ConfigError, match="Path traversal"):
        ConfigLoader.load("../../../etc/passwd")

def test_path_traversal_with_encoded_dots_blocked():
    """인코딩된 path traversal 차단"""
    with pytest.raises(ConfigError, match="Path traversal"):
        ConfigLoader.load("..%2F..%2Fetc/passwd")

def test_valid_nested_path_allowed():
    """정상적인 중첩 경로는 허용"""
    # This should not raise PathTraversal error
    # (may raise FileNotFound if file doesn't exist)
    try:
        ConfigLoader.load("strategies/stock/bb_reversion.yaml")
    except Exception as e:
        assert "Path traversal" not in str(e)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/config/test_loader_security.py::test_path_traversal_attack_blocked -v`
Expected: FAIL (현재 path traversal 검사 없음)

**Step 3: Write minimal implementation**

```python
# shared/config/loader.py - load 메서드 수정
from urllib.parse import unquote

@classmethod
def load(cls, path: str, schema: type[T] | None = None) -> T | dict:
    """YAML 설정 파일 로드 (path traversal 방어 포함)"""
    # Decode any URL-encoded characters
    decoded_path = unquote(path)

    # Resolve the full path
    config_dir = cls.get_config_dir().resolve()
    full_path = (config_dir / decoded_path).resolve()

    # Security check: ensure resolved path is within config directory
    try:
        full_path.relative_to(config_dir)
    except ValueError:
        raise ConfigError(
            f"Path traversal detected: '{path}' resolves outside config directory"
        )

    # ... rest of the existing implementation
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/config/test_loader_security.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/config/loader.py tests/unit/config/test_loader_security.py
git commit -m "fix(security): prevent path traversal in config loader

Add validation to ensure resolved paths stay within config directory.
Handles URL-encoded path components."
```

---

## Phase 2: Thread-Safety & Concurrency Fixes

### Task 4: Singleton Thread-Safety 수정 (ClickHouseClient)

**Files:**
- Modify: `shared/db/client.py:85-89`
- Test: `tests/unit/db/test_client_thread_safety.py`

**Step 1: Write the failing test**

```python
# tests/unit/db/test_client_thread_safety.py
import threading
import time
from unittest.mock import patch, MagicMock
from concurrent.futures import ThreadPoolExecutor

def test_singleton_thread_safety():
    """동시 접근 시 단일 인스턴스만 생성되어야 함"""
    # Reset singleton for test
    from shared.db.client import ClickHouseClient
    ClickHouseClient._instance = None

    instances = []
    creation_count = 0
    original_new = ClickHouseClient.__new__

    def counting_new(cls, *args, **kwargs):
        nonlocal creation_count
        creation_count += 1
        time.sleep(0.01)  # Simulate slow initialization
        return original_new(cls)

    mock_config = MagicMock()

    def create_instance():
        with patch.object(ClickHouseClient, '__new__', counting_new):
            instance = ClickHouseClient(mock_config)
            instances.append(id(instance))

    # Create multiple threads trying to get singleton
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(create_instance) for _ in range(10)]
        for f in futures:
            f.result()

    # All instances should be the same object
    assert len(set(instances)) == 1, f"Multiple instances created: {len(set(instances))}"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/db/test_client_thread_safety.py -v`
Expected: FAIL (race condition으로 여러 인스턴스 생성)

**Step 3: Write minimal implementation**

```python
# shared/db/client.py - 클래스 수정
import threading
from typing import ClassVar

class ClickHouseClient:
    """Thread-safe singleton ClickHouse client"""

    _instance: ClassVar["ClickHouseClient | None"] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()
    _initialized: bool = False

    def __new__(cls, config: ClickHouseConfig | None = None) -> "ClickHouseClient":
        if cls._instance is None:
            with cls._lock:
                # Double-checked locking pattern
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: ClickHouseConfig | None = None) -> None:
        # Prevent re-initialization
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            if config is None:
                raise ValueError("Config required for first initialization")

            self.config = config
            self._client: Client | None = None
            self._initialized = True

    @classmethod
    def reset_singleton(cls) -> None:
        """테스트용 싱글톤 리셋"""
        with cls._lock:
            cls._instance = None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/db/test_client_thread_safety.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/db/client.py tests/unit/db/test_client_thread_safety.py
git commit -m "fix(concurrency): thread-safe singleton for ClickHouseClient

Implement double-checked locking pattern to prevent race conditions
during singleton initialization in multi-threaded environments."
```

---

### Task 5: ConfigLoader Thread-Safety 수정

**Files:**
- Modify: `shared/config/loader.py:75-78`
- Test: `tests/unit/config/test_loader_thread_safety.py`

**Step 1: Write the failing test**

```python
# tests/unit/config/test_loader_thread_safety.py
import threading
from concurrent.futures import ThreadPoolExecutor
from shared.config.loader import ConfigLoader

def test_config_loader_thread_safety():
    """동시 로드 시 캐시 corruption 없어야 함"""
    ConfigLoader._cache.clear()

    results = []
    errors = []

    def load_config():
        try:
            result = ConfigLoader.load("strategies/stock/bb_reversion.yaml")
            results.append(result)
        except Exception as e:
            errors.append(e)

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(load_config) for _ in range(20)]
        for f in futures:
            f.result()

    assert len(errors) == 0, f"Errors occurred: {errors}"
    # All results should be identical
    first = results[0]
    for r in results[1:]:
        assert r == first, "Cache corruption detected"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/config/test_loader_thread_safety.py -v`
Expected: May FAIL under heavy load due to race conditions

**Step 3: Write minimal implementation**

```python
# shared/config/loader.py - 클래스 수정
import threading
from typing import ClassVar

class ConfigLoader:
    """Thread-safe configuration loader"""

    _cache: ClassVar[dict[str, Any]] = {}
    _cache_lock: ClassVar[threading.Lock] = threading.Lock()
    _config_dir: ClassVar[Path | None] = None
    _dir_lock: ClassVar[threading.Lock] = threading.Lock()

    @classmethod
    def load(cls, path: str, schema: type[T] | None = None) -> T | dict:
        cache_key = str(path)

        # Fast path: check cache without lock
        if cache_key in cls._cache:
            data = cls._cache[cache_key]
        else:
            # Slow path: acquire lock and load
            with cls._cache_lock:
                # Double-check after acquiring lock
                if cache_key not in cls._cache:
                    # ... path validation code ...
                    with open(full_path, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                    cls._cache[cache_key] = data
                else:
                    data = cls._cache[cache_key]

        if schema:
            return schema(**data)
        return data

    @classmethod
    def clear_cache(cls) -> None:
        """캐시 초기화 (thread-safe)"""
        with cls._cache_lock:
            cls._cache.clear()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/config/test_loader_thread_safety.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/config/loader.py tests/unit/config/test_loader_thread_safety.py
git commit -m "fix(concurrency): thread-safe config loader cache

Add locking to prevent cache corruption during concurrent config loading."
```

---

### Task 6: ThreeStageExit State Machine Race Condition 수정

**Files:**
- Modify: `shared/strategy/exit/three_stage.py:648-687`
- Test: `tests/unit/strategy/test_three_stage_concurrency.py`

**Step 1: Write the failing test**

```python
# tests/unit/strategy/test_three_stage_concurrency.py
import asyncio
import pytest
from unittest.mock import MagicMock
from shared.strategy.exit.three_stage import ThreeStageExit, ThreeStageExitConfig
from shared.models.position import Position, PositionState

@pytest.fixture
def exit_strategy():
    config = ThreeStageExitConfig(
        hard_stop_pct=2.0,
        breakeven_threshold_pct=2.0,
        breakeven_buffer_pct=0.1,
        maximize_threshold_pct=5.0,
        trailing_stop_pct=3.0,
        tight_trailing_pct=1.5,
        tight_trailing_trigger_pct=10.0,
    )
    return ThreeStageExit(config)

@pytest.mark.asyncio
async def test_concurrent_state_updates_no_corruption(exit_strategy):
    """동시 상태 업데이트 시 corruption 없어야 함"""
    position = Position(
        id="test-001",
        symbol="005930",
        side="BUY",
        quantity=10,
        entry_price=70000.0,
        state=PositionState.SURVIVAL,
    )

    async def update_state(price: float):
        await exit_strategy.update_position_state(position, price)
        return position.state

    # Concurrent updates with different prices
    tasks = [
        update_state(71500.0),  # Should trigger BREAKEVEN
        update_state(73500.0),  # Should trigger MAXIMIZE
        update_state(70500.0),  # Should stay in current state
    ]

    results = await asyncio.gather(*tasks)

    # Final state should be consistent (no corruption)
    assert position.state in [PositionState.BREAKEVEN, PositionState.MAXIMIZE]
```

**Step 2: Run test to verify behavior**

Run: `pytest tests/unit/strategy/test_three_stage_concurrency.py -v`
Expected: May show inconsistent behavior

**Step 3: Write minimal implementation**

```python
# shared/strategy/exit/three_stage.py - 수정
import asyncio
from typing import Dict

class ThreeStageExit(ExitSignalGenerator[ThreeStageExitConfig]):
    """Thread-safe 3-Stage Exit Strategy"""

    def __init__(self, config: ThreeStageExitConfig):
        super().__init__(config)
        self._position_locks: Dict[str, asyncio.Lock] = {}
        self._locks_lock = asyncio.Lock()

    async def _get_position_lock(self, position_id: str) -> asyncio.Lock:
        """Position별 Lock 획득 (lazy initialization)"""
        if position_id not in self._position_locks:
            async with self._locks_lock:
                if position_id not in self._position_locks:
                    self._position_locks[position_id] = asyncio.Lock()
        return self._position_locks[position_id]

    async def update_position_state(
        self,
        position: Position,
        current_price: float
    ) -> None:
        """Thread-safe 포지션 상태 업데이트"""
        lock = await self._get_position_lock(position.id)
        async with lock:
            await self._update_position_state_internal(position, current_price)

    async def _update_position_state_internal(
        self,
        position: Position,
        current_price: float
    ) -> None:
        """실제 상태 업데이트 로직 (lock 내에서 호출)"""
        # ... existing state transition logic ...

    def cleanup_position(self, position_id: str) -> None:
        """포지션 종료 시 lock 정리"""
        self._position_locks.pop(position_id, None)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/strategy/test_three_stage_concurrency.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/strategy/exit/three_stage.py tests/unit/strategy/test_three_stage_concurrency.py
git commit -m "fix(concurrency): thread-safe state transitions in ThreeStageExit

Add per-position locks to prevent race conditions during
concurrent state updates in the exit strategy state machine."
```

---

## Phase 3: Resource Management Fixes

### Task 7: AsyncClickHouseClient 리소스 누수 수정

**Files:**
- Modify: `shared/db/client.py:261-265`
- Test: `tests/unit/db/test_async_client_cleanup.py`

**Step 1: Write the failing test**

```python
# tests/unit/db/test_async_client_cleanup.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_async_client_closes_all_resources():
    """close() 호출 시 모든 리소스 정리"""
    mock_session = AsyncMock()
    mock_client = MagicMock()
    mock_client.close = AsyncMock()  # ChClient may have close method

    from shared.db.client import AsyncClickHouseClient

    client = AsyncClickHouseClient.__new__(AsyncClickHouseClient)
    client._session = mock_session
    client._client = mock_client
    client._initialized = True

    await client.close()

    mock_session.close.assert_awaited_once()
    # If ChClient has close method, it should be called
    if hasattr(mock_client, 'close'):
        mock_client.close.assert_awaited_once()

    assert client._session is None
    assert client._client is None

@pytest.mark.asyncio
async def test_async_client_context_manager():
    """Context manager 사용 시 자동 cleanup"""
    from shared.db.client import AsyncClickHouseClient

    with patch.object(AsyncClickHouseClient, 'connect', new_callable=AsyncMock):
        with patch.object(AsyncClickHouseClient, 'close', new_callable=AsyncMock) as mock_close:
            async with AsyncClickHouseClient(MagicMock()) as client:
                pass

            mock_close.assert_awaited_once()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/db/test_async_client_cleanup.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# shared/db/client.py - AsyncClickHouseClient 수정
class AsyncClickHouseClient:
    """Async ClickHouse client with proper resource management"""

    async def close(self) -> None:
        """Close all resources properly"""
        errors = []

        # Close ChClient if it has a close method
        if self._client is not None:
            try:
                if hasattr(self._client, 'close'):
                    close_method = self._client.close
                    if asyncio.iscoroutinefunction(close_method):
                        await close_method()
                    else:
                        close_method()
            except Exception as e:
                errors.append(f"ChClient close error: {e}")
            finally:
                self._client = None

        # Close aiohttp session
        if self._session is not None:
            try:
                await self._session.close()
            except Exception as e:
                errors.append(f"Session close error: {e}")
            finally:
                self._session = None

        self._initialized = False

        if errors:
            logger.warning(f"Errors during close: {errors}")

    async def __aenter__(self) -> "AsyncClickHouseClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/db/test_async_client_cleanup.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/db/client.py tests/unit/db/test_async_client_cleanup.py
git commit -m "fix(resources): proper cleanup in AsyncClickHouseClient

Ensure all resources (ChClient, aiohttp session) are properly closed.
Add context manager support for automatic cleanup."
```

---

### Task 8: Background Task 예외 처리 수정

**Files:**
- Modify: `services/api/routes.py:371-377`
- Test: `tests/unit/api/test_background_task_error_handling.py`

**Step 1: Write the failing test**

```python
# tests/unit/api/test_background_task_error_handling.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_background_task_updates_state_on_error():
    """Background task 실패 시 상태가 ERROR로 업데이트되어야 함"""
    from services.trading.orchestrator import TradingOrchestrator, OrchestratorState

    mock_orchestrator = MagicMock(spec=TradingOrchestrator)
    mock_orchestrator.run_session = AsyncMock(side_effect=RuntimeError("Connection lost"))
    mock_orchestrator.state = OrchestratorState.RUNNING

    # Import the error handling wrapper
    from services.api.routes import _create_session_runner

    runner = _create_session_runner(mock_orchestrator)
    await runner()

    # State should be updated to ERROR
    assert mock_orchestrator.state == OrchestratorState.ERROR
    # Error should be stored
    assert mock_orchestrator.last_error is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/api/test_background_task_error_handling.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# services/api/routes.py - 수정
from services.trading.orchestrator import OrchestratorState

def _create_session_runner(orchestrator: TradingOrchestrator) -> Callable:
    """Create background task runner with proper error handling"""

    async def run_with_error_handling():
        try:
            await orchestrator.run_session()
        except Exception as e:
            logger.error(f"Trading session failed: {e}", exc_info=True)

            # Update orchestrator state to reflect failure
            orchestrator.state = OrchestratorState.ERROR
            orchestrator.last_error = str(e)
            orchestrator.last_error_time = datetime.now()

            # Send notification if configured
            if orchestrator._notifier:
                try:
                    await orchestrator._notifier.send_error(
                        title="Trading Session Failed",
                        message=str(e),
                        severity="critical"
                    )
                except Exception as notify_error:
                    logger.error(f"Failed to send error notification: {notify_error}")

    return run_with_error_handling

# 기존 엔드포인트 수정
@router.post("/api/v1/trading/start")
async def start_trading(...):
    # ...
    runner = _create_session_runner(orchestrator)
    background_tasks.add_task(runner)
    # ...
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/api/test_background_task_error_handling.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/api/routes.py tests/unit/api/test_background_task_error_handling.py
git commit -m "fix(reliability): proper error handling in background trading task

Update orchestrator state and send notifications when background
trading session fails unexpectedly."
```

---

### Task 9: Holiday Cache Blocking I/O 수정

**Files:**
- Modify: `services/trading/orchestrator.py:67-110`
- Create: `services/trading/holiday_cache.py`
- Test: `tests/unit/trading/test_holiday_cache.py`

**Step 1: Write the failing test**

```python
# tests/unit/trading/test_holiday_cache.py
import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_holiday_loader_is_async():
    """Holiday loader가 async여야 함 (event loop 블로킹 방지)"""
    from services.trading.holiday_cache import async_holiday_loader

    # Should be a coroutine function
    assert asyncio.iscoroutinefunction(async_holiday_loader)

    with patch('aiofiles.open', new_callable=AsyncMock) as mock_open:
        mock_file = AsyncMock()
        mock_file.read = AsyncMock(return_value="holidays: []")
        mock_open.return_value.__aenter__.return_value = mock_file

        result = await async_holiday_loader("config/market_schedule.yaml")
        assert isinstance(result, set)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/trading/test_holiday_cache.py -v`
Expected: FAIL (모듈이 없음)

**Step 3: Write minimal implementation**

```python
# services/trading/holiday_cache.py - 새 파일
import asyncio
from datetime import date
from pathlib import Path
from typing import Set, Callable, Awaitable
import yaml

try:
    import aiofiles
    HAS_AIOFILES = True
except ImportError:
    HAS_AIOFILES = False

import logging
logger = logging.getLogger(__name__)

async def async_holiday_loader(config_path: str = "config/market_schedule.yaml") -> Set[date]:
    """Async holiday loader (non-blocking)"""
    path = Path(config_path)

    if not path.exists():
        logger.warning(f"Holiday config not found: {path}")
        return set()

    if HAS_AIOFILES:
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            content = await f.read()
    else:
        # Fallback: run sync I/O in thread pool
        loop = asyncio.get_event_loop()
        content = await loop.run_in_executor(
            None,
            lambda: path.read_text(encoding="utf-8")
        )

    data = yaml.safe_load(content)
    holidays_raw = data.get("holidays", [])

    return {
        date.fromisoformat(h) if isinstance(h, str) else h
        for h in holidays_raw
    }


class AsyncHolidayCache:
    """Async-friendly holiday cache"""

    def __init__(
        self,
        loader: Callable[[str], Awaitable[Set[date]]] = async_holiday_loader
    ):
        self._loader = loader
        self._cache: Set[date] | None = None
        self._lock = asyncio.Lock()

    async def get(self, config_path: str = "config/market_schedule.yaml") -> Set[date]:
        """Get holidays (async, cached)"""
        if self._cache is None:
            async with self._lock:
                if self._cache is None:
                    self._cache = await self._loader(config_path)
        return self._cache

    async def reload(self, config_path: str = "config/market_schedule.yaml") -> None:
        """Force reload (async)"""
        async with self._lock:
            self._cache = await self._loader(config_path)

    def is_holiday(self, d: date, holidays: Set[date]) -> bool:
        """Check if date is holiday (sync, uses pre-loaded data)"""
        return d in holidays
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/trading/test_holiday_cache.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/trading/holiday_cache.py tests/unit/trading/test_holiday_cache.py
git commit -m "feat(performance): async holiday cache to prevent event loop blocking

Replace sync file I/O with async version using aiofiles.
Fallback to thread pool executor if aiofiles not installed."
```

---

## Phase 4: Domain Strategy Fixes

### Task 10: Probability 계산 오류 수정 (Triple Barrier)

**Files:**
- Modify: `domains/futures/strategies/dl_trend.py:321`
- Test: `tests/unit/domains/futures/test_dl_trend.py`

**Step 1: Write the failing test**

```python
# tests/unit/domains/futures/test_dl_trend.py
import pytest
from unittest.mock import MagicMock
from domains.futures.strategies.dl_trend import DLTrendEntry

def test_triple_barrier_probability_handling():
    """Triple barrier 확률이 올바르게 처리되어야 함"""
    entry = DLTrendEntry(MagicMock())

    # Prediction with explicit probabilities
    prediction = {
        "up_prob": 0.6,
        "down_prob": 0.3,
        "hold_prob": 0.1,  # Should not be ignored
    }

    up, down, hold = entry._extract_probabilities(prediction)

    assert up == 0.6
    assert down == 0.3
    assert hold == 0.1
    assert abs(up + down + hold - 1.0) < 0.001

def test_binary_prediction_fallback():
    """Binary prediction에서는 hold_prob=0으로 처리"""
    entry = DLTrendEntry(MagicMock())

    prediction = {"up_prob": 0.7}  # Only up_prob provided

    up, down, hold = entry._extract_probabilities(prediction)

    assert up == 0.7
    assert down == 0.3  # 1 - up_prob
    assert hold == 0.0  # Default for binary

def test_weak_prediction_detected():
    """HOLD 확률이 높으면 약한 예측으로 감지"""
    entry = DLTrendEntry(MagicMock())

    prediction = {
        "up_prob": 0.35,
        "down_prob": 0.25,
        "hold_prob": 0.4,  # Dominant hold probability
    }

    is_weak = entry._is_weak_prediction(prediction)
    assert is_weak is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/domains/futures/test_dl_trend.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# domains/futures/strategies/dl_trend.py - 수정
from typing import Tuple

class DLTrendEntry(EntrySignalGenerator):
    """DL Trend Entry with proper triple-barrier handling"""

    def _extract_probabilities(
        self,
        prediction: dict
    ) -> Tuple[float, float, float]:
        """
        Triple barrier 확률 추출

        Returns:
            (up_prob, down_prob, hold_prob)
        """
        up_prob = prediction.get("up_prob", 0.5)

        # Check if model provides explicit triple-barrier probabilities
        if "down_prob" in prediction and "hold_prob" in prediction:
            down_prob = prediction["down_prob"]
            hold_prob = prediction["hold_prob"]
        elif "down_prob" in prediction:
            # Binary with explicit down_prob
            down_prob = prediction["down_prob"]
            hold_prob = max(0.0, 1.0 - up_prob - down_prob)
        else:
            # Fallback: binary assumption (legacy models)
            down_prob = 1.0 - up_prob
            hold_prob = 0.0

        return up_prob, down_prob, hold_prob

    def _is_weak_prediction(self, prediction: dict) -> bool:
        """HOLD 확률이 지배적인지 확인"""
        up, down, hold = self._extract_probabilities(prediction)

        # Weak if hold is the dominant probability
        if hold > up and hold > down:
            return True

        # Weak if no clear direction (close to uniform)
        if abs(up - down) < 0.1 and hold > 0.2:
            return True

        return False
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/domains/futures/test_dl_trend.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add domains/futures/strategies/dl_trend.py tests/unit/domains/futures/test_dl_trend.py
git commit -m "fix(strategy): proper triple-barrier probability handling

Extract all three probabilities (up/down/hold) instead of assuming
binary classification. Detect weak predictions when hold is dominant."
```

---

### Task 11: Division by Zero 보호 강화

**Files:**
- Modify: `domains/futures/strategies/dl_trend.py:228-234`
- Test: `tests/unit/domains/futures/test_probability_calibrator.py`

**Step 1: Write the failing test**

```python
# tests/unit/domains/futures/test_probability_calibrator.py
import pytest
import numpy as np
from domains.futures.strategies.dl_trend import ProbabilityCalibrator

def test_zscore_handles_zero_std():
    """std=0일 때 None 반환"""
    calibrator = ProbabilityCalibrator(window_size=10, min_samples=5)

    # Add identical values to create std=0
    for _ in range(10):
        calibrator.update(horizon=1, prob=0.5)

    result = calibrator.get_zscore(horizon=1, prob=0.6)
    assert result is None  # Should not raise division by zero

def test_zscore_handles_near_zero_std():
    """std가 매우 작을 때 None 반환"""
    calibrator = ProbabilityCalibrator(window_size=10, min_samples=5)

    # Add nearly identical values
    for i in range(10):
        calibrator.update(horizon=1, prob=0.5 + i * 1e-12)

    result = calibrator.get_zscore(horizon=1, prob=0.6)
    assert result is None  # std too small for meaningful z-score

def test_zscore_valid_calculation():
    """정상적인 z-score 계산"""
    calibrator = ProbabilityCalibrator(window_size=10, min_samples=5)

    # Add varied values
    probs = [0.3, 0.4, 0.5, 0.6, 0.7, 0.35, 0.45, 0.55, 0.65, 0.75]
    for p in probs:
        calibrator.update(horizon=1, prob=p)

    result = calibrator.get_zscore(horizon=1, prob=0.8)
    assert result is not None
    assert isinstance(result, float)
    assert not np.isnan(result)
    assert not np.isinf(result)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/domains/futures/test_probability_calibrator.py -v`
Expected: May FAIL on edge cases

**Step 3: Write minimal implementation**

```python
# domains/futures/strategies/dl_trend.py - ProbabilityCalibrator 수정
import numpy as np

class ProbabilityCalibrator:
    """Probability calibrator with robust numerical handling"""

    # Minimum std threshold for meaningful z-score calculation
    MIN_STD_THRESHOLD = 1e-8

    def get_zscore(self, horizon: int, prob: float) -> float | None:
        """
        Calculate z-score with numerical safety

        Returns None if:
        - Not enough samples
        - Standard deviation is too small for meaningful calculation
        """
        history = self._history.get(horizon)

        if history is None or len(history) < self.min_samples:
            return None

        values = np.array(list(history))
        mean = np.mean(values)
        std = np.std(values)

        # Check for numerical stability
        if std < self.MIN_STD_THRESHOLD or not np.isfinite(std):
            logger.debug(
                f"Std too small for z-score: {std:.2e} "
                f"(threshold: {self.MIN_STD_THRESHOLD:.2e})"
            )
            return None

        zscore = (prob - mean) / std

        # Sanity check on result
        if not np.isfinite(zscore):
            logger.warning(f"Non-finite z-score: {zscore}")
            return None

        return float(zscore)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/domains/futures/test_probability_calibrator.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add domains/futures/strategies/dl_trend.py tests/unit/domains/futures/test_probability_calibrator.py
git commit -m "fix(numerical): robust division-by-zero protection in calibrator

Use explicit epsilon threshold instead of arbitrary 0.001.
Add sanity checks for non-finite results."
```

---

### Task 12: Exit Strategy Registry 등록

**Files:**
- Create: `shared/strategy/exit/atr_trailing.py`
- Modify: `shared/strategy/registry.py`
- Test: `tests/unit/strategy/test_exit_registry.py`

**Step 1: Write the failing test**

```python
# tests/unit/strategy/test_exit_registry.py
import pytest
from shared.strategy.registry import ExitRegistry

def test_atr_trailing_exit_registered():
    """atr_trailing exit strategy가 registry에 등록되어 있어야 함"""
    assert "atr_trailing" in ExitRegistry.list_all()

def test_atr_trailing_exit_creation():
    """atr_trailing exit strategy 생성 가능해야 함"""
    config = {
        "atr_multiplier": 2.0,
        "initial_stop_atr": 1.5,
        "max_hold_minutes": 30,
        "stop_loss_ticks": 10,
        "take_profit_ticks": 20,
    }

    exit_strategy = ExitRegistry.create("atr_trailing", config)
    assert exit_strategy is not None
    assert exit_strategy.config.atr_multiplier == 2.0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/strategy/test_exit_registry.py -v`
Expected: FAIL (atr_trailing 미등록)

**Step 3: Write minimal implementation**

```python
# shared/strategy/exit/atr_trailing.py - 새 파일
from dataclasses import dataclass
from shared.strategy.base import ExitSignalGenerator, ExitContext
from shared.strategy.registry import ExitRegistry

@dataclass
class ATRTrailingConfig:
    """ATR Trailing Stop 설정"""
    atr_multiplier: float = 2.0
    initial_stop_atr: float = 1.5
    max_hold_minutes: int = 30
    stop_loss_ticks: int = 10
    take_profit_ticks: int = 20
    tick_size: float = 0.05


@ExitRegistry.register("atr_trailing")
class ATRTrailingExit(ExitSignalGenerator[ATRTrailingConfig]):
    """ATR 기반 트레일링 스탑 청산 전략"""

    CONFIG_CLASS = ATRTrailingConfig

    def __init__(self, config: ATRTrailingConfig | dict):
        if isinstance(config, dict):
            config = ATRTrailingConfig(**config)
        super().__init__(config)
        self._entry_times: dict[str, float] = {}
        self._trailing_stops: dict[str, float] = {}

    def _validate_config(self) -> None:
        c = self.config
        assert c.atr_multiplier > 0, "atr_multiplier must be positive"
        assert c.initial_stop_atr > 0, "initial_stop_atr must be positive"
        assert c.max_hold_minutes > 0, "max_hold_minutes must be positive"

    @property
    def required_indicators(self) -> list[str]:
        return ["atr"]

    async def should_exit(self, context: ExitContext) -> tuple[bool, str]:
        """청산 여부 판단"""
        position = context.position
        current_price = context.market_data.get("close", 0)
        atr = context.indicators.get("atr", 0)

        # Time-based exit
        if position.id in self._entry_times:
            hold_minutes = (context.timestamp - self._entry_times[position.id]).total_seconds() / 60
            if hold_minutes >= self.config.max_hold_minutes:
                return True, f"TIME_EXIT (held {hold_minutes:.1f} min)"

        # Fixed stop loss (ticks)
        tick_pnl = self._calc_tick_pnl(position, current_price)
        if tick_pnl <= -self.config.stop_loss_ticks:
            return True, f"STOP_LOSS ({tick_pnl} ticks)"

        # Fixed take profit (ticks)
        if tick_pnl >= self.config.take_profit_ticks:
            return True, f"TAKE_PROFIT ({tick_pnl} ticks)"

        # ATR trailing stop
        if position.id not in self._trailing_stops:
            # Initialize trailing stop
            if position.side == "BUY":
                self._trailing_stops[position.id] = position.entry_price - atr * self.config.initial_stop_atr
            else:
                self._trailing_stops[position.id] = position.entry_price + atr * self.config.initial_stop_atr

        # Update trailing stop
        trailing_stop = self._trailing_stops[position.id]
        if position.side == "BUY":
            new_stop = current_price - atr * self.config.atr_multiplier
            if new_stop > trailing_stop:
                self._trailing_stops[position.id] = new_stop
                trailing_stop = new_stop

            if current_price <= trailing_stop:
                return True, f"ATR_TRAILING_STOP (stop: {trailing_stop:.2f})"
        else:
            new_stop = current_price + atr * self.config.atr_multiplier
            if new_stop < trailing_stop:
                self._trailing_stops[position.id] = new_stop
                trailing_stop = new_stop

            if current_price >= trailing_stop:
                return True, f"ATR_TRAILING_STOP (stop: {trailing_stop:.2f})"

        return False, ""

    def _calc_tick_pnl(self, position, current_price: float) -> float:
        """틱 단위 손익 계산"""
        if position.side == "BUY":
            return (current_price - position.entry_price) / self.config.tick_size
        return (position.entry_price - current_price) / self.config.tick_size

    def update_state(self, context: ExitContext) -> None:
        """상태 업데이트"""
        if context.position.id not in self._entry_times:
            self._entry_times[context.position.id] = context.timestamp

    def cleanup(self, position_id: str) -> None:
        """포지션 종료 시 상태 정리"""
        self._entry_times.pop(position_id, None)
        self._trailing_stops.pop(position_id, None)


# shared/strategy/exit/__init__.py 에 추가
from .atr_trailing import ATRTrailingExit, ATRTrailingConfig
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/strategy/test_exit_registry.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/strategy/exit/atr_trailing.py shared/strategy/exit/__init__.py tests/unit/strategy/test_exit_registry.py
git commit -m "feat(strategy): implement ATR trailing stop exit strategy

Add atr_trailing exit strategy to registry for futures trading.
Includes time-based exit, fixed stop/target, and ATR-based trailing."
```

---

## Phase 5: Memory Leak Fixes

### Task 13: PositionManager 메모리 누수 수정

**Files:**
- Modify: `shared/position/manager.py:52-54`
- Test: `tests/unit/position/test_manager_memory.py`

**Step 1: Write the failing test**

```python
# tests/unit/position/test_manager_memory.py
import pytest
from shared.position.manager import PositionManager

def test_closed_positions_bounded():
    """closed_positions가 무한히 증가하지 않아야 함"""
    manager = PositionManager(max_closed_history=100)

    # Add 200 positions and close them
    for i in range(200):
        pos_id = f"pos-{i}"
        manager.add_position(pos_id, "TEST", "BUY", 10, 100.0)
        manager.close_position(pos_id, 105.0)

    # Should be bounded to max_closed_history
    assert len(manager.closed_positions) <= 100

def test_default_max_closed_history():
    """기본 max_closed_history 설정"""
    manager = PositionManager()
    assert manager.max_closed_history == 10000  # Sensible default
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/position/test_manager_memory.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# shared/position/manager.py - 수정
from collections import deque
from typing import Deque

class PositionManager:
    """Position manager with bounded history"""

    DEFAULT_MAX_CLOSED_HISTORY = 10000

    def __init__(
        self,
        max_closed_history: int = DEFAULT_MAX_CLOSED_HISTORY
    ):
        self.active_positions: Dict[str, Position] = {}
        self.max_closed_history = max_closed_history
        self._closed_positions: Deque[Position] = deque(maxlen=max_closed_history)

    @property
    def closed_positions(self) -> list[Position]:
        """Get closed positions (most recent first)"""
        return list(self._closed_positions)

    def close_position(self, position_id: str, exit_price: float) -> Position | None:
        """Close a position and move to history"""
        if position_id not in self.active_positions:
            return None

        position = self.active_positions.pop(position_id)
        position.exit_price = exit_price
        position.exit_time = datetime.now()
        position.state = PositionState.CLOSED

        # deque with maxlen automatically removes oldest
        self._closed_positions.append(position)

        return position
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/position/test_manager_memory.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add shared/position/manager.py tests/unit/position/test_manager_memory.py
git commit -m "fix(memory): bound closed_positions with deque maxlen

Prevent unbounded growth of closed position history in long-running
trading sessions. Default limit: 10000 positions."
```

---

## Phase 6: CORS & Rate Limiting Fixes

### Task 14: CORS 설정 강화

**Files:**
- Modify: `services/api/app.py:105-106`
- Test: `tests/unit/api/test_cors_security.py`

**Step 1: Write the failing test**

```python
# tests/unit/api/test_cors_security.py
import pytest
from services.api.app import get_cors_settings

def test_development_cors_restricted():
    """Development에서도 CORS가 제한적이어야 함"""
    settings = get_cors_settings("development")

    # Should not allow all methods
    assert settings["allow_methods"] != ["*"]

    # Should have explicit list
    assert "GET" in settings["allow_methods"]
    assert "POST" in settings["allow_methods"]

    # Should not allow all headers
    assert settings["allow_headers"] != ["*"]

def test_production_cors_strict():
    """Production에서 CORS가 엄격해야 함"""
    settings = get_cors_settings("production")

    # Credentials should be carefully considered
    # allow_credentials=True with allow_origins=["*"] is insecure
    if settings.get("allow_credentials"):
        assert settings["allow_origins"] != ["*"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/api/test_cors_security.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# services/api/app.py - get_cors_settings 수정
ALLOWED_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
ALLOWED_HEADERS = [
    "Content-Type",
    "Authorization",
    "X-API-Key",
    "X-Request-ID",
    "Accept",
    "Accept-Language",
]

def get_cors_settings(env: str) -> dict:
    """Get CORS settings based on environment"""
    cors = config.get("cors", {})

    if env == "development":
        return {
            "allow_origins": cors.get("allowed_origins", ["http://localhost:3000"]),
            "allow_credentials": True,
            "allow_methods": ALLOWED_METHODS,  # Explicit list, not "*"
            "allow_headers": ALLOWED_HEADERS,   # Explicit list, not "*"
        }

    # Production: strict settings
    allowed_origins = cors.get("allowed_origins", [])
    if not allowed_origins:
        logger.warning("No CORS origins configured for production")

    return {
        "allow_origins": allowed_origins,
        "allow_credentials": cors.get("allow_credentials", False),
        "allow_methods": ALLOWED_METHODS,
        "allow_headers": ALLOWED_HEADERS,
    }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/api/test_cors_security.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/api/app.py tests/unit/api/test_cors_security.py
git commit -m "fix(security): restrict CORS to explicit methods and headers

Replace allow_methods='*' and allow_headers='*' with explicit lists
to reduce attack surface in both development and production."
```

---

### Task 15: Rate Limiting 전체 적용

**Files:**
- Modify: `services/api/routes.py`
- Test: `tests/unit/api/test_rate_limiting.py`

**Step 1: Write the failing test**

```python
# tests/unit/api/test_rate_limiting.py
import pytest
from services.api.routes import router
from fastapi import FastAPI
from fastapi.testclient import TestClient

def test_all_endpoints_have_rate_limit():
    """모든 엔드포인트에 rate limit이 적용되어야 함"""
    app = FastAPI()
    app.include_router(router)

    # Get all routes
    routes = [route for route in app.routes if hasattr(route, 'endpoint')]

    # Check that each route has rate limit dependency
    for route in routes:
        if route.path.startswith("/api/"):
            dependencies = getattr(route, 'dependencies', [])
            dep_names = [str(d.dependency) for d in dependencies]

            # Should have rate limit or be explicitly exempted
            has_rate_limit = any('rate_limit' in name.lower() for name in dep_names)
            is_exempted = route.path in ["/api/v1/health"]  # Health check exempted

            assert has_rate_limit or is_exempted, \
                f"Endpoint {route.path} missing rate limit"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/api/test_rate_limiting.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# services/api/routes.py - 수정
# 모든 엔드포인트에 rate limit 추가

# 기존 엔드포인트들에 Depends 추가
@router.get(
    "/api/v1/status",
    tags=["Status"],
    dependencies=[Depends(get_rate_limit_status())],  # 추가
)
async def get_status(state: Annotated[AppState, Depends(get_app_state)]):
    ...

@router.get(
    "/api/v1/trading/status",
    tags=["Trading"],
    dependencies=[Depends(get_rate_limit_trading())],  # 추가
)
async def get_trading_status(...):
    ...

@router.get(
    "/api/v1/trading/metrics",
    tags=["Trading"],
    dependencies=[Depends(get_rate_limit_trading())],  # 추가
)
async def get_trading_metrics(...):
    ...

# Rate limit helper functions
def get_rate_limit_status():
    """Status 엔드포인트용 rate limit (높음)"""
    return _create_rate_limit_dependency("300/minute")

def get_rate_limit_trading():
    """Trading 엔드포인트용 rate limit (중간)"""
    return _create_rate_limit_dependency("60/minute")

def get_rate_limit_strategies():
    """Strategy 엔드포인트용 rate limit (낮음)"""
    return _create_rate_limit_dependency("30/minute")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/api/test_rate_limiting.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add services/api/routes.py tests/unit/api/test_rate_limiting.py
git commit -m "fix(security): apply rate limiting to all API endpoints

Add rate limit dependencies to previously unprotected endpoints:
- /api/v1/status: 300/minute
- /api/v1/trading/status: 60/minute
- /api/v1/trading/metrics: 60/minute"
```

---

## Phase 7: Integration Tests

### Task 16: Domain Strategy 통합 테스트

**Files:**
- Create: `tests/integration/test_dl_trend_integration.py`

**Step 1: Write comprehensive integration test**

```python
# tests/integration/test_dl_trend_integration.py
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from domains.futures.strategies.dl_trend import DLTrendEntry, DLTrendConfig
from shared.strategy.base import EntryContext
from shared.models.position import Position

@pytest.fixture
def dl_trend_config():
    return DLTrendConfig(
        dl_threshold=0.6,
        max_atr_threshold=2.0,
        zscore_trigger_threshold=1.5,
        ma_fast_period=10,
        ma_slow_period=20,
        use_multi_horizon=True,
        horizons=[1, 5, 15],
    )

@pytest.fixture
def entry_strategy(dl_trend_config):
    return DLTrendEntry(dl_trend_config)

@pytest.mark.asyncio
async def test_full_entry_signal_flow(entry_strategy):
    """전체 진입 시그널 플로우 테스트"""
    # Setup market data
    market_data = {
        "close": 350.0,
        "volume": 10000,
        "atr": 2.5,
    }

    indicators = {
        "ma_fast": 348.0,
        "ma_slow": 345.0,  # Bullish crossover
        "rsi": 55.0,
    }

    # Mock prediction with high confidence
    prediction = {
        "up_prob": 0.75,
        "down_prob": 0.15,
        "hold_prob": 0.10,
        "horizon_probs": {1: 0.70, 5: 0.72, 15: 0.78},
    }

    context = EntryContext(
        market_data=market_data,
        indicators=indicators,
        current_positions=[],
        timestamp=datetime.now(),
        prediction=prediction,
    )

    # Generate signal
    signal = await entry_strategy.generate(context)

    # Should generate entry signal
    assert signal is not None
    assert signal.direction == "BUY"
    assert signal.confidence >= 0.6

@pytest.mark.asyncio
async def test_weak_prediction_no_signal(entry_strategy):
    """약한 예측에서는 시그널 없어야 함"""
    market_data = {"close": 350.0, "atr": 2.5}
    indicators = {"ma_fast": 348.0, "ma_slow": 345.0}

    # Weak prediction (high hold probability)
    prediction = {
        "up_prob": 0.35,
        "down_prob": 0.30,
        "hold_prob": 0.35,
    }

    context = EntryContext(
        market_data=market_data,
        indicators=indicators,
        current_positions=[],
        timestamp=datetime.now(),
        prediction=prediction,
    )

    signal = await entry_strategy.generate(context)

    # Should NOT generate signal for weak prediction
    assert signal is None

@pytest.mark.asyncio
async def test_calibrator_warmup_period(entry_strategy):
    """캘리브레이터 워밍업 기간 동안 z-score 없이 동작"""
    # First few predictions should work without z-score
    for i in range(5):
        prediction = {"up_prob": 0.6 + i * 0.02}
        context = EntryContext(
            market_data={"close": 350.0, "atr": 2.5},
            indicators={"ma_fast": 348.0, "ma_slow": 345.0},
            current_positions=[],
            timestamp=datetime.now(),
            prediction=prediction,
        )

        # Should not crash during warmup
        signal = await entry_strategy.generate(context)

        # Update calibrator
        entry_strategy.update_calibrator({1: prediction["up_prob"]})

@pytest.mark.asyncio
async def test_multi_horizon_confirmation():
    """멀티 호라이즌 확인 로직 테스트"""
    config = DLTrendConfig(
        dl_threshold=0.6,
        use_multi_horizon=True,
        horizons=[1, 5, 15],
        require_all_horizons_agree=True,
    )
    strategy = DLTrendEntry(config)

    # Horizons disagree
    prediction = {
        "up_prob": 0.7,
        "horizon_probs": {
            1: 0.65,   # Bullish
            5: 0.70,   # Bullish
            15: 0.45,  # Bearish - disagreement!
        },
    }

    context = EntryContext(
        market_data={"close": 350.0, "atr": 2.5},
        indicators={"ma_fast": 348.0, "ma_slow": 345.0},
        current_positions=[],
        timestamp=datetime.now(),
        prediction=prediction,
    )

    signal = await strategy.generate(context)

    # Should not generate signal when horizons disagree
    assert signal is None
```

**Step 2: Run integration tests**

Run: `pytest tests/integration/test_dl_trend_integration.py -v`
Expected: All tests should pass after previous fixes

**Step 3: Commit**

```bash
git add tests/integration/test_dl_trend_integration.py
git commit -m "test(integration): add DL trend strategy integration tests

Cover full entry signal flow, weak prediction handling,
calibrator warmup, and multi-horizon confirmation logic."
```

---

## Summary Checklist

- [ ] Phase 1: Security Critical Fixes (Tasks 1-3)
- [ ] Phase 2: Thread-Safety & Concurrency (Tasks 4-6)
- [ ] Phase 3: Resource Management (Tasks 7-9)
- [ ] Phase 4: Domain Strategy Fixes (Tasks 10-12)
- [ ] Phase 5: Memory Leak Fixes (Task 13)
- [ ] Phase 6: CORS & Rate Limiting (Tasks 14-15)
- [ ] Phase 7: Integration Tests (Task 16)

**Total Tasks: 16**
**Estimated Commits: 16**
**Test Files Created: 14**

---

## Post-Implementation Verification

After all tasks complete:

```bash
# Run full test suite
pytest tests/ -v --cov=shared --cov=services --cov=domains

# Type check
mypy shared/ services/ domains/

# Lint
ruff check .
black --check .

# Security scan (if available)
bandit -r shared/ services/
```
