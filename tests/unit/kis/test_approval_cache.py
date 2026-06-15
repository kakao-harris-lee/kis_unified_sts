"""Tests for the process-wide KIS WS approval-key cache."""

from __future__ import annotations

from shared.kis.approval_cache import ApprovalKeyCache


def test_miss_then_hit():
    c = ApprovalKeyCache()
    assert c.get("appA") is None
    c.set("appA", "key-1")
    assert c.get("appA") == "key-1"


def test_keys_are_isolated_per_app_key():
    c = ApprovalKeyCache()
    c.set("appA", "key-A")
    c.set("appB", "key-B")
    assert c.get("appA") == "key-A"
    assert c.get("appB") == "key-B"


def test_expiry_by_ttl():
    c = ApprovalKeyCache()
    c.set("appA", "key-1")
    # ttl=0 → any positive age is expired → miss
    assert c.get("appA", ttl=0) is None
    # large ttl → still valid
    assert c.get("appA", ttl=10_000) == "key-1"


def test_invalidate_drops_key():
    c = ApprovalKeyCache()
    c.set("appA", "key-1")
    c.invalidate("appA")
    assert c.get("appA") is None
    c.invalidate("missing")  # no error on unknown key
