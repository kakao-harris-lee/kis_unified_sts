"""Owner tests for post-exit re-entry guard helper functions."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from services.trading.runtime_config import EntryReentryGuardConfig
from shared.models.signal import ExitReason, ExitSignal


def _guard(scope: str = "symbol_strategy") -> EntryReentryGuardConfig:
    return EntryReentryGuardConfig(
        enabled=True,
        scope=scope,
        default_cooldown_seconds=900,
        reason_cooldown_seconds={"stop_loss": 3600},
    )


def test_reentry_guard_key_respects_config_scope() -> None:
    from services.trading.reentry_guard import reentry_guard_key

    assert reentry_guard_key(_guard("symbol"), "064400", "momentum_breakout") == (
        "064400"
    )
    assert (
        reentry_guard_key(
            _guard("symbol_strategy"),
            "064400",
            "momentum_breakout",
        )
        == "064400:momentum_breakout"
    )


def test_record_recent_exit_writes_cooldown_record() -> None:
    from services.trading.reentry_guard import record_recent_exit_cooldown

    recent: dict[str, dict[str, object]] = {}
    closed = SimpleNamespace(code="064400", strategy="momentum_breakout")
    exit_signal = ExitSignal(
        code="064400",
        strategy="momentum_breakout",
        reason=ExitReason.STOP_LOSS,
    )
    now = datetime(2026, 7, 4, 9, 30, tzinfo=UTC)

    record_recent_exit_cooldown(
        recent,
        _guard(),
        closed=closed,
        signal=exit_signal,
        reason="stop_loss",
        now=now,
    )

    assert recent == {
        "064400:momentum_breakout": {
            "code": "064400",
            "strategy": "momentum_breakout",
            "reason": "stop_loss",
            "exit_time": now,
            "cooldown_seconds": 3600.0,
        }
    }


def test_reentry_guard_block_prunes_expired_record() -> None:
    from services.trading.reentry_guard import reentry_guard_block

    recent = {
        "064400:momentum_breakout": {
            "code": "064400",
            "strategy": "momentum_breakout",
            "reason": "stop_loss",
            "exit_time": datetime(2026, 7, 4, 9, 0, tzinfo=UTC),
            "cooldown_seconds": 600.0,
        }
    }

    block = reentry_guard_block(
        recent,
        _guard(),
        code="064400",
        strategy="momentum_breakout",
        now=datetime(2026, 7, 4, 9, 20, tzinfo=UTC),
    )

    assert block is None
    assert recent == {}


def test_reentry_guard_block_reports_remaining_seconds() -> None:
    from services.trading.reentry_guard import reentry_guard_block

    recent = {
        "064400:momentum_breakout": {
            "code": "064400",
            "strategy": "momentum_breakout",
            "reason": "stop_loss",
            "exit_time": datetime(2026, 7, 4, 9, 0, tzinfo=UTC),
            "cooldown_seconds": 600.0,
        }
    }

    block = reentry_guard_block(
        recent,
        _guard(),
        code="064400",
        strategy="momentum_breakout",
        now=datetime(2026, 7, 4, 9, 5, tzinfo=UTC),
    )

    assert block == {
        "code": "064400",
        "strategy": "momentum_breakout",
        "reason": "stop_loss",
        "exit_time": datetime(2026, 7, 4, 9, 0, tzinfo=UTC),
        "cooldown_seconds": 600.0,
        "remaining_seconds": 300.0,
        "elapsed_seconds": 300.0,
    }


def test_reentry_guard_helpers_do_not_import_orchestrator() -> None:
    import subprocess
    import sys
    import textwrap

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent("""
                import sys
                import services.trading.reentry_guard

                assert "services.trading.orchestrator" not in sys.modules
                """),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
