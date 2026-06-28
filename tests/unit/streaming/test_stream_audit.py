"""Unit tests for shared.streaming.audit helpers."""

from __future__ import annotations

import logging

import pytest

from shared.streaming.audit import (
    RateLimitedLog,
    decode_stream_id,
    extract_audit_fields,
    format_audit_kv,
)


def test_decode_stream_id_normalizes_bytes_and_strings():
    assert decode_stream_id(b"1740000000000-1") == "1740000000000-1"
    assert decode_stream_id("1740000000000-2") == "1740000000000-2"


def test_extract_audit_fields_keeps_only_safe_identifiers():
    fields = {
        b"signal_id": b"sig-1",
        b"symbol": b"005930",
        "code": "069500",
        b"strategy": b"setup_c_event_reaction",
        b"setup_type": b"setup_c",
        b"direction": b"long",
        b"price": b"123.45",
        b"account": b"secret",
        b"empty": b"",
    }

    assert extract_audit_fields(fields) == {
        "signal_id": "sig-1",
        "symbol": "005930",
        "code": "069500",
        "strategy": "setup_c_event_reaction",
        "setup_type": "setup_c",
        "direction": "long",
    }


def test_format_audit_kv_renders_stable_tokens_and_omits_empty_values():
    assert (
        format_audit_kv(
            event="stream_message_processed",
            ack=True,
            claimed=False,
            signal_id="sig-1",
            empty="",
            none=None,
        )
        == "event=stream_message_processed ack=true claimed=false signal_id=sig-1"
    )


def test_rate_limited_log_emits_first_exception_then_cooldown_summary(caplog):
    times = iter([0.0, 1.0, 2.0, 11.0])
    rate_limit = RateLimitedLog(cooldown_seconds=10.0, clock=lambda: next(times))
    logger = logging.getLogger("tests.stream_audit.rate_limited")
    caplog.set_level(logging.ERROR, logger=logger.name)

    for index in range(4):
        try:
            raise RuntimeError(f"redis down {index}")
        except RuntimeError:
            rate_limit.exception(logger, "xreadgroup error")

    messages = [record.getMessage() for record in caplog.records]
    assert messages == [
        "xreadgroup error",
        "xreadgroup error suppressed_count=2",
    ]
    assert caplog.records[0].exc_info is not None
    assert caplog.records[1].exc_info is None


def test_rate_limited_log_logs_sparse_exceptions_with_traceback(caplog):
    times = iter([0.0, 11.0])
    rate_limit = RateLimitedLog(cooldown_seconds=10.0, clock=lambda: next(times))
    logger = logging.getLogger("tests.stream_audit.sparse")
    caplog.set_level(logging.ERROR, logger=logger.name)

    for _index in range(2):
        try:
            raise RuntimeError("redis down")
        except RuntimeError:
            rate_limit.exception(logger, "xautoclaim error")

    assert [record.getMessage() for record in caplog.records] == [
        "xautoclaim error",
        "xautoclaim error",
    ]
    assert all(record.exc_info is not None for record in caplog.records)


def test_rate_limited_log_rejects_invalid_cooldown():
    with pytest.raises(ValueError):
        RateLimitedLog(cooldown_seconds=-1.0)
