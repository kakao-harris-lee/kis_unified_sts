"""Thread-safety tests for ClickHouseClient singleton."""
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest


def test_singleton_thread_safety():
    """동시 접근 시 단일 인스턴스만 생성되어야 함"""
    from shared.db.client import ClickHouseClient
    from shared.db.config import ClickHouseConfig
    
    # Reset singleton for test
    ClickHouseClient.reset_singleton()
    
    instances = []
    mock_config = ClickHouseConfig(
        host="localhost",
        port=9000,
        database="test",
        user="default",
        password=""
    )
    
    def create_instance():
        instance = ClickHouseClient(mock_config)
        instances.append(id(instance))
    
    # Create multiple threads trying to get singleton
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(create_instance) for _ in range(10)]
        for f in futures:
            f.result()
    
    # All instances should be the same object
    unique_instances = set(instances)
    assert len(unique_instances) == 1, (
        f"Multiple instances created: {len(unique_instances)} unique IDs found. "
        f"Expected 1 singleton instance."
    )


def test_singleton_reset():
    """reset_singleton()으로 싱글톤 초기화 가능"""
    from shared.db.client import ClickHouseClient
    from shared.db.config import ClickHouseConfig
    
    mock_config = ClickHouseConfig(
        host="localhost",
        port=9000,
        database="test",
        user="default",
        password=""
    )
    
    instance1 = ClickHouseClient(mock_config)
    instance1_id = id(instance1)
    
    ClickHouseClient.reset_singleton()
    
    instance2 = ClickHouseClient(mock_config)
    instance2_id = id(instance2)
    
    assert instance1_id != instance2_id, (
        "After reset_singleton(), new instance should be created"
    )


def test_singleton_initialization_race():
    """초기화 중 race condition 테스트 - 모든 스레드가 동일 인스턴스를 받아야 함"""
    from shared.db.client import ClickHouseClient
    from shared.db.config import ClickHouseConfig

    ClickHouseClient.reset_singleton()

    instances_created = []
    lock = threading.Lock()

    mock_config = ClickHouseConfig(
        host="localhost",
        port=9000,
        database="test",
        user="default",
        password=""
    )

    def create_and_track():
        instance = ClickHouseClient(mock_config)
        with lock:
            instances_created.append(id(instance))

    # Spawn many threads simultaneously
    threads = [threading.Thread(target=create_and_track) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All threads should receive the exact same instance
    unique_instances = set(instances_created)
    assert len(unique_instances) == 1, (
        f"Multiple instances created: {len(unique_instances)} unique instances. "
        f"Expected exactly 1 singleton instance across all threads."
    )
