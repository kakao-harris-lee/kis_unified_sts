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


# --- override_env: a service-specific knob that outranks LOG_LEVEL ------------


def test_override_env_wins_over_log_level(
    monkeypatch: pytest.MonkeyPatch, restore_root_log_level: logging.Logger
) -> None:
    """The narrower knob decides: naming one service means that service."""
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("SERVICE_LOG_LEVEL", "DEBUG")

    assert configure_logging(override_env="SERVICE_LOG_LEVEL") == logging.DEBUG


def test_log_level_applies_when_override_is_unset(
    monkeypatch: pytest.MonkeyPatch, restore_root_log_level: logging.Logger
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "ERROR")
    monkeypatch.delenv("SERVICE_LOG_LEVEL", raising=False)

    assert configure_logging(override_env="SERVICE_LOG_LEVEL") == logging.ERROR


def test_blank_override_defers_to_log_level_without_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    restore_root_log_level: logging.Logger,
) -> None:
    """Compose renders an unset override as ``""`` (``"${VAR:-}"``).

    Blank therefore means "not configured", not "misconfigured" — warning on
    it would put a spurious line in every container's startup output.
    """
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("SERVICE_LOG_LEVEL", "")

    with caplog.at_level(logging.WARNING, logger="shared.observability.logging_setup"):
        assert configure_logging(override_env="SERVICE_LOG_LEVEL") == logging.DEBUG

    assert caplog.text == ""


def test_typo_in_override_falls_through_to_log_level_with_a_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    restore_root_log_level: logging.Logger,
) -> None:
    """A misspelled override must not also swallow a good ``LOG_LEVEL``."""
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("SERVICE_LOG_LEVEL", "DEBGU")

    with caplog.at_level(logging.WARNING, logger="shared.observability.logging_setup"):
        assert configure_logging(override_env="SERVICE_LOG_LEVEL") == logging.DEBUG

    assert "SERVICE_LOG_LEVEL" in caplog.text
    assert "DEBGU" in caplog.text


def test_both_unparseable_falls_back_to_info(
    monkeypatch: pytest.MonkeyPatch, restore_root_log_level: logging.Logger
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "loud")
    monkeypatch.setenv("SERVICE_LOG_LEVEL", "BASIC_FORMAT")

    assert configure_logging(override_env="SERVICE_LOG_LEVEL") == logging.INFO
