"""Orchestrator execution-config construction — review attempt-2 #5 / #8.

This path builds the ``ExecutionConfig`` for TODAY's live futures execution.
Two things had to change together:

* The old whitelist forwarded 8 hand-listed keys and silently dropped every
  knob added after it was written, so ``execution.yaml`` had stopped being the
  source of truth for this path.
* Construction sat inside a ``try`` whose handler degrades to
  ``_order_executor = None`` — and a ``None`` executor makes the exit path fall
  through to the mock branch, REPORTING every exit as filled at the requested
  price while nothing reaches the broker. Widening the forwarding without
  moving the construction out of that ``try`` would have turned one unknown
  YAML key into a silent fail-open.
"""

import pytest
from pydantic import ValidationError

from services.trading.orchestrator import build_execution_config


@pytest.fixture(autouse=True)
def _account_env(monkeypatch):
    """Pin the account env this builder reads.

    ``build_execution_config`` overrides ``account_no`` from the environment,
    so a developer shell holding a placeholder would otherwise decide these
    tests. Note the placeholder case is a real failure now: a malformed
    account number RAISES rather than degrading to a mocked executor.
    """
    monkeypatch.setenv("KIS_ACCOUNT_NO", "5011064801")
    monkeypatch.setenv("KIS_FUTURES_ACCOUNT_NO", "5011064801")


def _section() -> dict:
    from shared.config.loader import ConfigLoader

    return dict(ConfigLoader.load("execution.yaml").get("execution", {}))


def test_knobs_the_old_whitelist_dropped_now_reach_the_config():
    """Every knob added after the whitelist was written must be forwarded."""
    section = _section()
    for key in (
        "futures_cancel_max_attempts",
        "futures_cancel_retry_delay_seconds",
        "futures_inquire_page_size",
        "throttle_backoff_initial_seconds",
        "throttle_backoff_multiplier",
        "throttle_backoff_max_seconds",
        "throttle_storm_alert_threshold",
        "cancel_rate_limit_suffix",
        "futures_fill_check_rate_limit_timeout_seconds",
    ):
        assert key in section, f"execution.yaml no longer configures {key}"

    config = build_execution_config(
        raw_exec_cfg=section, mode="REAL", asset_class="futures"
    )

    assert config.futures_cancel_max_attempts == section["futures_cancel_max_attempts"]
    assert config.throttle_storm_alert_threshold == (
        section["throttle_storm_alert_threshold"]
    )
    assert config.futures_inquire_page_size == section["futures_inquire_page_size"]
    assert config.cancel_rate_limit_suffix == section["cancel_rate_limit_suffix"]


def test_a_non_default_yaml_value_actually_changes_the_config():
    """Guards against the forwarding being a no-op that happens to match defaults."""
    section = _section()
    section["futures_cancel_max_attempts"] = 7
    section["throttle_storm_alert_threshold"] = 42

    config = build_execution_config(
        raw_exec_cfg=section, mode="REAL", asset_class="futures"
    )

    assert config.futures_cancel_max_attempts == 7
    assert config.throttle_storm_alert_threshold == 42


def test_orchestrator_owned_keys_override_the_file():
    section = _section()
    section["trading_mode"] = "PAPER"

    config = build_execution_config(
        raw_exec_cfg=section, mode="REAL", asset_class="futures"
    )

    assert config.trading_mode == "REAL"
    assert config.rate_limit_key == "futures"


def test_legacy_orders_per_second_still_folds_on_this_path():
    config = build_execution_config(
        raw_exec_cfg=_section(), mode="MOCK", asset_class="stock"
    )

    assert config.requests_per_second == 5.0


def test_an_unknown_key_raises_rather_than_degrading():
    """The whole point of #5: this must NOT become a silently mocked executor."""
    section = _section()
    section["futures_cancel_max_attemtps"] = 3  # typo

    with pytest.raises(ValidationError):
        build_execution_config(raw_exec_cfg=section, mode="REAL", asset_class="futures")


@pytest.mark.parametrize("mode", ["PAPER", "LIVE"])
def test_the_deploy_vocabulary_does_not_raise(mode):
    """The config layer must NOT police the ``mode`` vocabulary.

    Two different knobs are both spelled TRADING_MODE: this orchestrator's
    deploy space is ``paper|live`` (docker-compose sets it, and
    ``trading_loop_entrypoint.sh`` exits 64 on anything else), while
    ``ExecutionConfig`` speaks ``PAPER|MOCK|REAL``. ``_init_execution_layer``
    therefore resolves ``mode`` to "PAPER" or "LIVE" on every production path.
    Raising here — outside the degrade handler — made the live orchestrator
    unstartable by ANY documented configuration, since no value satisfies both
    the entrypoint and the check.
    """
    config = build_execution_config(
        raw_exec_cfg=_section(), mode=mode, asset_class="futures"
    )

    assert config.trading_mode == mode


def test_the_mode_gate_still_lives_inside_the_degrade_handler():
    """Structural: the vocabulary check must sit INSIDE the try that degrades.

    Keeping it there preserves HEAD's behaviour exactly — a live-vocabulary
    mode leaves ``_order_executor = None`` with a warning instead of aborting
    startup. Only the CONFIG construction was hoisted out.
    """
    import inspect

    from services.trading.orchestrator import TradingOrchestrator

    source = inspect.getsource(TradingOrchestrator._init_execution_layer)
    build_at = source.index("build_execution_config(")
    try_at = source.index("from shared.execution.executor import OrderExecutor")
    gate_at = source.index('if mode not in ("MOCK", "REAL"):')

    assert build_at < try_at, "config construction must be outside the try"
    assert gate_at > try_at, (
        "the mode vocabulary gate must stay INSIDE the degrade-to-mock try; "
        "hoisting it out makes the live orchestrator unstartable"
    )


def test_a_missing_section_still_builds_on_model_defaults():
    """An absent file is degradable; a malformed one is not."""
    config = build_execution_config(raw_exec_cfg={}, mode="MOCK", asset_class="stock")

    assert config.requests_per_second == 20.0
    assert config.trading_mode == "MOCK"


def test_config_construction_is_outside_the_degrade_to_mock_handler():
    """Structural: the constructor must not be inside the try that nulls it.

    A ``None`` executor makes the exit path report fills that never reached the
    broker, so a config error must stop the process instead.
    """
    import inspect

    from services.trading.orchestrator import TradingOrchestrator

    source = inspect.getsource(TradingOrchestrator._init_execution_layer)
    build_at = source.index("build_execution_config(")
    try_at = source.index("from shared.execution.executor import OrderExecutor")

    assert build_at < try_at, (
        "build_execution_config must run BEFORE the try block that degrades "
        "to _order_executor = None"
    )


def test_a_placeholder_account_number_raises_rather_than_degrading(monkeypatch):
    """Behaviour change worth naming: this used to degrade to a mock executor.

    An unfilled `KIS_ACCOUNT_NO` placeholder previously produced a ValidationError
    that the caller swallowed, leaving `_order_executor = None` — and every exit
    then reported filled without reaching the broker. Refusing to start is the
    correct direction for a live-execution path. An EMPTY account is still
    allowed (the validator permits it); only a malformed one raises.
    """
    monkeypatch.setenv("KIS_ACCOUNT_NO", "your_kis_account_no")
    monkeypatch.setenv("KIS_FUTURES_ACCOUNT_NO", "your_kis_account_no")

    with pytest.raises(ValidationError, match="10 digits"):
        build_execution_config(
            raw_exec_cfg=_section(), mode="REAL", asset_class="futures"
        )


def test_an_empty_account_number_is_still_permitted(monkeypatch):
    monkeypatch.setenv("KIS_ACCOUNT_NO", "")
    monkeypatch.setenv("KIS_FUTURES_ACCOUNT_NO", "")

    config = build_execution_config(
        raw_exec_cfg=_section(), mode="MOCK", asset_class="futures"
    )

    assert config.account_no == ""


# ---------------------------------------------------------------------------
# Review attempt-3 #10 — the documented live deploy shape must START
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_documented_live_deploy_shape_starts_without_raising(monkeypatch):
    """TRADING_MODE=live + paper_trading=False must not abort startup.

    That is the shape docker-compose and trading_loop_entrypoint.sh produce.
    No try sits between `_init_execution_layer` and `start()`, so a raise here
    escapes `start()` and — under `restart: unless-stopped` — becomes a
    crash-loop. HEAD continued with `_order_executor = None`; this must too.
    """
    from types import SimpleNamespace

    from services.trading.orchestrator import TradingOrchestrator

    monkeypatch.setenv("TRADING_MODE", "live")

    orch = TradingOrchestrator.__new__(TradingOrchestrator)
    orch.config = SimpleNamespace(
        paper_trading=False,
        execution_mode="",  # what every production path leaves it as
        asset_class="futures",
    )
    orch._kis_client = None
    orch._order_executor = "sentinel"

    await orch._init_execution_layer()

    # Degraded, exactly as at HEAD — not an abort.
    assert orch._order_executor is None


@pytest.mark.asyncio
async def test_a_malformed_execution_yaml_still_aborts_startup(monkeypatch):
    """The #5 protection must survive the #10 fix: config errors still raise."""
    from types import SimpleNamespace

    from services.trading import orchestrator as orch_mod
    from services.trading.orchestrator import TradingOrchestrator

    monkeypatch.setenv("TRADING_MODE", "live")
    monkeypatch.setattr(
        orch_mod,
        "_load_execution_section",
        lambda: {"futures_cancel_max_attemtps": 3},  # typo
    )

    orch = TradingOrchestrator.__new__(TradingOrchestrator)
    orch.config = SimpleNamespace(
        paper_trading=False, execution_mode="", asset_class="futures"
    )
    orch._kis_client = None
    orch._order_executor = None

    with pytest.raises(ValidationError):
        await orch._init_execution_layer()


@pytest.mark.asyncio
async def test_a_valid_executor_mode_still_builds_an_executor(monkeypatch):
    """Negative control: MOCK/REAL still produce a real executor."""
    from types import SimpleNamespace

    from services.trading.orchestrator import TradingOrchestrator

    monkeypatch.setenv("TRADING_MODE", "MOCK")

    orch = TradingOrchestrator.__new__(TradingOrchestrator)
    orch.config = SimpleNamespace(
        paper_trading=False, execution_mode="MOCK", asset_class="futures"
    )
    orch._kis_client = None
    orch._order_executor = None

    await orch._init_execution_layer()

    assert orch._order_executor is not None
    assert orch._order_executor.config.trading_mode == "MOCK"
    await orch._order_executor.cleanup()
