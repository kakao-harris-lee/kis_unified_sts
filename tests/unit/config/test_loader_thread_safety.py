"""Thread-safety tests for ConfigLoader

Tests concurrent access to the cache dictionary to ensure no race conditions or corruption.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

from shared.config.loader import ConfigLoader


class TestConfigLoaderThreadSafety:
    """Thread-safety tests for ConfigLoader cache operations"""

    @pytest.fixture(autouse=True)
    def setup_teardown(self, tmp_path):
        """Setup and teardown for each test"""
        # Create test config directory
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Create test config files
        (config_dir / "test1.yaml").write_text("key: value1\n")
        (config_dir / "test2.yaml").write_text("key: value2\n")
        (config_dir / "test3.yaml").write_text("key: value3\n")

        # Set config directory
        ConfigLoader.set_config_dir(config_dir)

        yield

        # Cleanup
        ConfigLoader.clear_cache()

    def test_concurrent_load_same_file_no_corruption(self):
        """동시 로드 시 캐시 corruption 없어야 함

        20개 스레드가 동시에 같은 파일을 로드해도
        모든 결과가 동일해야 함
        """
        num_threads = 20
        results = []
        errors = []

        # Force cache miss by clearing it first
        ConfigLoader.clear_cache()

        def load_config():
            try:
                result = ConfigLoader.load("test1.yaml")
                return result
            except Exception as e:
                errors.append(e)
                raise

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(load_config) for _ in range(num_threads)]
            for future in as_completed(futures):
                results.append(future.result())

        # No errors
        assert len(errors) == 0, f"Errors occurred: {errors}"

        # All results should be identical
        assert len(results) == num_threads
        first_result = results[0]
        for result in results[1:]:
            assert result == first_result, "Results differ across threads"

        # Cache should have exactly one entry for this file
        cache_keys = [k for k in ConfigLoader._cache if k.startswith("test1.yaml:")]
        assert len(cache_keys) == 1, f"Expected 1 cache entry, got {len(cache_keys)}"

    def test_concurrent_load_different_files(self):
        """다른 파일 동시 로드 시 간섭 없어야 함

        스레드별로 다른 파일을 로드해도 각각 정상 동작해야 함
        """
        num_threads = 30
        results = {}
        errors = []
        lock = threading.Lock()

        def load_config(file_num):
            try:
                filename = f"test{file_num % 3 + 1}.yaml"
                result = ConfigLoader.load(filename)
                with lock:
                    if filename not in results:
                        results[filename] = []
                    results[filename].append(result)
            except Exception as e:
                errors.append(e)
                raise

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(load_config, i) for i in range(num_threads)]
            for future in as_completed(futures):
                future.result()

        # No errors
        assert len(errors) == 0, f"Errors occurred: {errors}"

        # Each file should have correct results
        assert "test1.yaml" in results
        assert "test2.yaml" in results
        assert "test3.yaml" in results

        # All results for same file should be identical
        for filename, file_results in results.items():
            first = file_results[0]
            for result in file_results[1:]:
                assert result == first, f"Results differ for {filename}"

        # Verify actual values
        assert results["test1.yaml"][0] == {"key": "value1"}
        assert results["test2.yaml"][0] == {"key": "value2"}
        assert results["test3.yaml"][0] == {"key": "value3"}

    def test_concurrent_clear_cache_during_load(self):
        """로드 중 캐시 클리어해도 corruption 없어야 함

        일부 스레드가 로드하는 동안 다른 스레드가 캐시를 클리어해도
        데드락이나 corruption이 발생하지 않아야 함
        """
        num_loaders = 20
        num_clearers = 5
        errors = []
        successes = []

        def load_config():
            try:
                for _ in range(10):  # 여러 번 로드
                    result = ConfigLoader.load("test1.yaml")
                    successes.append(result)
                    time.sleep(0.001)  # 약간의 지연
            except Exception as e:
                errors.append(e)
                raise

        def clear_cache():
            try:
                for _ in range(5):  # 여러 번 클리어
                    ConfigLoader.clear_cache()
                    time.sleep(0.002)  # 약간의 지연
            except Exception as e:
                errors.append(e)
                raise

        with ThreadPoolExecutor(max_workers=num_loaders + num_clearers) as executor:
            futures = []
            futures.extend([executor.submit(load_config) for _ in range(num_loaders)])
            futures.extend([executor.submit(clear_cache) for _ in range(num_clearers)])

            for future in as_completed(futures):
                future.result()

        # No errors
        assert len(errors) == 0, f"Errors occurred: {errors}"

        # All successful loads should have correct value
        assert len(successes) > 0
        for result in successes:
            assert result == {"key": "value1"}

    def test_concurrent_set_config_dir(self):
        """set_config_dir 동시 호출 시 안전해야 함

        여러 스레드가 동시에 set_config_dir를 호출해도
        데드락이나 corruption이 발생하지 않아야 함
        """
        num_threads = 10
        errors = []

        # Create multiple test directories
        test_dirs = []
        for i in range(3):
            dir_path = Path(ConfigLoader.get_config_dir()).parent / f"test_config_{i}"
            dir_path.mkdir(exist_ok=True)
            (dir_path / "test.yaml").write_text(f"key: value{i}\n")
            test_dirs.append(dir_path)

        def set_dir(dir_index):
            try:
                for _ in range(5):
                    ConfigLoader.set_config_dir(test_dirs[dir_index])
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
                raise

        try:
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = [
                    executor.submit(set_dir, i % len(test_dirs))
                    for i in range(num_threads)
                ]
                for future in as_completed(futures):
                    future.result()

            # No errors
            assert len(errors) == 0, f"Errors occurred: {errors}"

            # Final state should be consistent
            final_dir = ConfigLoader.get_config_dir()
            assert final_dir.exists()

        finally:
            # Cleanup test directories
            for dir_path in test_dirs:
                if dir_path.exists():
                    for f in dir_path.iterdir():
                        f.unlink()
                    dir_path.rmdir()

    def test_concurrent_reload_during_load(self):
        """reload 동시 호출 시 안전해야 함

        일부 스레드가 load를 하는 동안 다른 스레드가 reload를 해도
        데드락이나 corruption이 발생하지 않아야 함
        """
        num_loaders = 15
        num_reloaders = 5
        errors = []
        results = []

        def load_config():
            try:
                for _ in range(10):
                    result = ConfigLoader.load("test1.yaml")
                    results.append(result)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
                raise

        def reload_config():
            try:
                for _ in range(5):
                    result = ConfigLoader.reload("test1.yaml")
                    results.append(result)
                    time.sleep(0.002)
            except Exception as e:
                errors.append(e)
                raise

        with ThreadPoolExecutor(max_workers=num_loaders + num_reloaders) as executor:
            futures = []
            futures.extend([executor.submit(load_config) for _ in range(num_loaders)])
            futures.extend([executor.submit(reload_config) for _ in range(num_reloaders)])

            for future in as_completed(futures):
                future.result()

        # No errors
        assert len(errors) == 0, f"Errors occurred: {errors}"

        # All results should have correct value
        assert len(results) > 0
        for result in results:
            assert result == {"key": "value1"}

    def test_cache_consistency_under_stress(self):
        """스트레스 테스트: 다양한 작업 동시 수행

        load, clear_cache, reload를 동시에 수행해도
        캐시 상태가 일관성 있게 유지되어야 함
        """
        num_operations = 50
        errors = []

        operations = {
            "load": lambda: ConfigLoader.load("test1.yaml"),
            "clear": lambda: ConfigLoader.clear_cache(),
            "reload": lambda: ConfigLoader.reload("test1.yaml"),
            "load2": lambda: ConfigLoader.load("test2.yaml"),
            "load3": lambda: ConfigLoader.load("test3.yaml"),
        }

        def perform_operation(op_name):
            try:
                for _ in range(10):
                    operations[op_name]()
                    time.sleep(0.001)
            except Exception as e:
                errors.append((op_name, e))
                raise

        with ThreadPoolExecutor(max_workers=num_operations) as executor:
            futures = []
            for i in range(num_operations):
                op_name = list(operations.keys())[i % len(operations)]
                futures.append(executor.submit(perform_operation, op_name))

            for future in as_completed(futures):
                future.result()

        # No errors
        assert len(errors) == 0, f"Errors occurred: {errors}"

        # Final cache should be in valid state
        # Try to load each file - should not raise
        result1 = ConfigLoader.load("test1.yaml")
        result2 = ConfigLoader.load("test2.yaml")
        result3 = ConfigLoader.load("test3.yaml")

        assert result1 == {"key": "value1"}
        assert result2 == {"key": "value2"}
        assert result3 == {"key": "value3"}

    def test_double_checked_locking_fast_path(self):
        """Double-checked locking의 fast path 검증

        캐시된 항목은 lock 없이 빠르게 반환되어야 함
        """
        # First load to populate cache
        ConfigLoader.load("test1.yaml")

        # Measure time for cached loads (should be very fast)
        num_iterations = 1000
        start = time.time()
        for _ in range(num_iterations):
            ConfigLoader.load("test1.yaml")
        elapsed = time.time() - start

        # Should complete very quickly (< 0.1 seconds)
        # This is a smoke test - if locking is wrong, it will be much slower
        assert elapsed < 0.1, f"Cached loads too slow: {elapsed:.3f}s"

    def test_no_deadlock_with_nested_operations(self):
        """중첩된 작업에서 데드락 없어야 함

        load_all_strategies 같은 중첩된 작업이 동시에 실행되어도
        데드락이 발생하지 않아야 함
        """
        # Create strategy files
        config_dir = ConfigLoader.get_config_dir()
        strategies_dir = config_dir / "strategies" / "stock"
        strategies_dir.mkdir(parents=True, exist_ok=True)

        for i in range(5):
            strategy_file = strategies_dir / f"strategy{i}.yaml"
            strategy_file.write_text(
                f"""
strategy:
  name: strategy{i}
  enabled: true
"""
            )

        errors = []

        def load_all():
            try:
                for _ in range(10):
                    ConfigLoader.load_all_strategies("stock")
                    time.sleep(0.002)
            except Exception as e:
                errors.append(e)
                raise

        num_threads = 10
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(load_all) for _ in range(num_threads)]
            for future in as_completed(futures):
                future.result()

        # No errors
        assert len(errors) == 0, f"Errors occurred: {errors}"

    def test_concurrent_singleton_creation(self):
        """동시 singleton 생성 시 단일 인스턴스만 생성되어야 함

        여러 스레드가 동시에 ConfigLoader()를 호출해도
        단 하나의 인스턴스만 생성되어야 함 (race condition 방지)
        """
        num_threads = 50
        instances = []
        errors = []
        lock = threading.Lock()

        def create_instance():
            try:
                # Force a slight delay to maximize race condition chance
                time.sleep(0.001)
                instance = ConfigLoader()
                with lock:
                    instances.append(id(instance))
            except Exception as e:
                errors.append(e)
                raise

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(create_instance) for _ in range(num_threads)]
            for future in as_completed(futures):
                future.result()

        # No errors
        assert len(errors) == 0, f"Errors occurred: {errors}"

        # All instances should have the same id
        assert len(instances) == num_threads
        unique_instances = set(instances)
        assert len(unique_instances) == 1, (
            f"Expected 1 unique instance, got {len(unique_instances)}: {unique_instances}"
        )

    def test_concurrent_get_config_dir(self):
        """get_config_dir 동시 호출 시 안전해야 함

        여러 스레드가 동시에 get_config_dir를 호출해도
        일관된 결과를 반환해야 함 (초기화 race condition 방지)
        """
        # Reset config_dir to None to test initialization
        ConfigLoader._config_dir = None

        num_threads = 30
        results = []
        errors = []
        lock = threading.Lock()

        def get_dir():
            try:
                # Force a slight delay to maximize race condition chance
                time.sleep(0.001)
                result = ConfigLoader.get_config_dir()
                with lock:
                    results.append(result)
            except Exception as e:
                errors.append(e)
                raise

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(get_dir) for _ in range(num_threads)]
            for future in as_completed(futures):
                future.result()

        # No errors
        assert len(errors) == 0, f"Errors occurred: {errors}"

        # All results should be identical
        assert len(results) == num_threads
        first_result = results[0]
        for result in results[1:]:
            assert result == first_result, "get_config_dir results differ across threads"

        # Result should be a valid Path
        assert isinstance(first_result, Path)
        assert first_result.exists()
