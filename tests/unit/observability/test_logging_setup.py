"""``LOG_LEVEL``-driven logging setup (shared/observability/logging_setup.py)."""

from __future__ import annotations

import logging

import pytest

from shared.observability.logging_setup import configure_logging


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("DEBUG", logging.DEBUG),
        ("debug", logging.DEBUG),
        ("  WARNING  ", logging.WARNING),
        ("ERROR", logging.ERROR),
        ("CRITICAL", logging.CRITICAL),
    ],
)
def test_env_value_sets_root_level(
    raw: str,
    expected: int,
    monkeypatch: pytest.MonkeyPatch,
    restore_root_log_level: logging.Logger,
) -> None:
    monkeypatch.setenv("LOG_LEVEL", raw)

    assert configure_logging() == expected
    assert restore_root_log_level.level == expected


def test_unset_defaults_to_info(
    monkeypatch: pytest.MonkeyPatch, restore_root_log_level: logging.Logger
) -> None:
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    assert configure_logging() == logging.INFO
    assert restore_root_log_level.level == logging.INFO


def test_invalid_value_falls_back_to_info_without_raising(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    restore_root_log_level: logging.Logger,
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "bogus")

    with caplog.at_level(logging.WARNING, logger="shared.observability.logging_setup"):
        assert configure_logging() == logging.INFO

    assert restore_root_log_level.level == logging.INFO
    assert "bogus" in caplog.text


def test_empty_value_falls_back_to_info(
    monkeypatch: pytest.MonkeyPatch, restore_root_log_level: logging.Logger
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "")

    assert configure_logging() == logging.INFO


def test_non_level_module_attribute_is_not_a_level(
    monkeypatch: pytest.MonkeyPatch, restore_root_log_level: logging.Logger
) -> None:
    """``getattr(logging, name)`` would return a function here; we must not."""
    monkeypatch.setenv("LOG_LEVEL", "basicConfig")

    assert configure_logging() == logging.INFO


def test_valid_value_logs_no_fallback_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    restore_root_log_level: logging.Logger,
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    with caplog.at_level(logging.WARNING, logger="shared.observability.logging_setup"):
        configure_logging()

    assert caplog.text == ""
