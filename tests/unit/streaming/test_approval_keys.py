"""Tests for shared/streaming/approval_keys.py — pending-approval key conventions."""

from __future__ import annotations

from shared.streaming.approval_keys import (
    APPROVAL_EVENTS_CHANNEL,
    approval_field_id,
    pending_approval_key,
)


def test_pending_approval_key_default_format(monkeypatch):
    monkeypatch.delenv("PENDING_APPROVAL_KEY", raising=False)
    assert pending_approval_key("stock") == "signal:pending_approval:stock"
    assert pending_approval_key("futures") == "signal:pending_approval:futures"


def test_pending_approval_key_env_override(monkeypatch):
    monkeypatch.setenv("PENDING_APPROVAL_KEY", "custom:pending_approval")
    assert pending_approval_key("stock") == "custom:pending_approval"
    assert pending_approval_key("futures") == "custom:pending_approval"


def test_approval_field_id_format():
    assert approval_field_id("stock", "abc123") == "stock:abc123"
    assert approval_field_id("futures", "def456") == "futures:def456"


def test_approval_events_channel_is_fixed_and_asset_neutral():
    assert APPROVAL_EVENTS_CHANNEL == "trading:events:approval"
