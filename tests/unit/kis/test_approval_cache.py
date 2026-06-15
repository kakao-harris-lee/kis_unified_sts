"""Tests for the process-wide KIS WS approval-key cache."""

from __future__ import annotations

from shared.kis.approval_cache import ApprovalKeyCache


def test_miss_then_hit():
    c = ApprovalKeyCache()
    assert c.get("appA", True) is None
    c.set("appA", True, "key-1")
    assert c.get("appA", True) == "key-1"


def test_keys_are_isolated_per_app_key():
    c = ApprovalKeyCache()
    c.set("appA", True, "key-A")
    c.set("appB", True, "key-B")
    assert c.get("appA", True) == "key-A"
    assert c.get("appB", True) == "key-B"


def test_real_and_mock_are_separate_entries():
    c = ApprovalKeyCache()
    c.set("appA", True, "real-key")
    c.set("appA", False, "mock-key")
    # same app key, different env → distinct cached keys (real/mock endpoints
    # issue different approval keys)
    assert c.get("appA", True) == "real-key"
    assert c.get("appA", False) == "mock-key"


def test_expiry_by_ttl():
    c = ApprovalKeyCache()
    c.set("appA", True, "key-1")
    # ttl=0 → any positive age is expired → miss
    assert c.get("appA", True, ttl=0) is None
    # large ttl → still valid
    assert c.get("appA", True, ttl=10_000) == "key-1"


def test_invalidate_drops_key():
    c = ApprovalKeyCache()
    c.set("appA", True, "key-1")
    c.invalidate("appA", True)
    assert c.get("appA", True) is None
    c.invalidate("missing", True)  # no error on unknown key
