"""Rate-limiter wiring and config-drop guards — wave-3b D-3.

``OrderExecutor`` builds a rate limiter only when ``redis_url`` is set. Two
runtime paths passed none and therefore ran completely unpaced:

* ``services/order_router/main.py`` — the LIVE futures order path, built from
  ``config/execution.yaml::execution`` which carries no ``redis_url``;
* ``shared/execution/mock_mirror.py`` — mirrors every stock paper entry/exit to
  the KIS mock account.

Compounding it, ``execution.yaml`` spells the pacing limit ``orders_per_second``
while the model field is ``requests_per_second``; Pydantic's default
``extra='ignore'`` discarded it silently, so the configured value never applied.
"""

import pytest
from pydantic import ValidationError

from shared.execution.config import ExecutionConfig
from shared.execution.executor import OrderExecutor

_REDIS_URL = "redis://localhost:6379/1"


def _execution_section() -> dict:
    """The real ``execution.yaml::execution`` section.

    ``account_no`` is normalized because it interpolates from the environment
    and a developer/CI shell may hold a placeholder; nothing here depends on it.
    """
    from shared.config.loader import ConfigLoader

    section = dict(ConfigLoader.load("execution.yaml").get("execution", {}))
    section["account_no"] = "5011064801"
    return section


# ---------------------------------------------------------------------------
# The live futures path constructs a limiter
# ---------------------------------------------------------------------------


def test_no_redis_url_still_means_no_limiter():
    """Negative control: the opt-out is unchanged."""
    executor = OrderExecutor(ExecutionConfig(trading_mode="PAPER"))

    assert executor._rate_limiter is None


@pytest.mark.asyncio
async def test_mock_mirror_paces_on_its_own_bucket(monkeypatch):
    """The mirror paces its orders, and NOT out of the real path's budget.

    The mirror authenticates against 모의투자 with a different key on a
    different host, so its traffic does not consume the real account's broker
    allowance. Sharing ``kis:ratelimit:stock`` would spend the REAL stock
    path's tokens on MOCK traffic.
    """
    from shared.execution.mock_mirror import MockAccountMirror

    monkeypatch.setenv("KIS_STOCK_APP_KEY", "test-key")
    monkeypatch.setenv("KIS_STOCK_APP_SECRET", "test-secret")
    monkeypatch.setenv("KIS_STOCK_ACCOUNT_NO", "5011064801")
    monkeypatch.setenv("REDIS_URL", _REDIS_URL)

    mirror = MockAccountMirror(asset_class="stock")
    try:
        assert await mirror.initialize() is True
        assert mirror._executor._rate_limiter is not None
        assert mirror._executor._rate_limiter.key != "kis:ratelimit:stock"
        assert mirror._executor._rate_limiter.key == "kis:ratelimit:stock-mock-mirror"
    finally:
        if mirror._executor is not None:
            await mirror._executor.cleanup()


# ---------------------------------------------------------------------------
# Unknown keys fail loudly instead of being silently dropped
# ---------------------------------------------------------------------------


def test_misspelled_config_key_fails_loudly():
    """A key the model does not know is a silent-drop hazard, not a no-op."""
    with pytest.raises(ValidationError) as excinfo:
        ExecutionConfig(trading_mode="PAPER", request_per_second=5.0)

    assert "request_per_second" in str(excinfo.value)


def test_unknown_key_from_yaml_section_fails_loudly():
    section = _execution_section()
    section["orders_per_secnod"] = 5.0  # typo

    with pytest.raises(ValidationError):
        ExecutionConfig(**section)


def test_legacy_orders_per_second_alias_is_accepted():
    config = ExecutionConfig(trading_mode="PAPER", orders_per_second=7.0)

    assert config.requests_per_second == 7.0


def test_canonical_requests_per_second_still_accepted():
    config = ExecutionConfig(trading_mode="PAPER", requests_per_second=9.0)

    assert config.requests_per_second == 9.0


# ---------------------------------------------------------------------------
# Review attempt-1 #7 / #8 — the live futures path must be able to trade
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wired_live_executor_can_build_auth_headers(monkeypatch):
    """End of the #7 chain: with an auth_manager, header building is reachable.

    Without one, ``_build_auth_headers`` short-circuits to None and every
    futures order fails with 'Failed to get auth headers'.
    """
    from shared.kis.auth import KISAuthConfig, KISAuthManager

    auth = KISAuthManager(
        KISAuthConfig(app_key="k", app_secret="s", is_real=True),
        use_singleton=False,
    )
    monkeypatch.setattr(auth, "get_auth_headers", lambda: {"authorization": "Bearer t"})

    executor = OrderExecutor(ExecutionConfig(trading_mode="REAL"), auth_manager=auth)
    try:
        headers = await executor._build_auth_headers(tr_id="TTTO1101U")
    finally:
        await executor.cleanup()

    assert headers is not None
    assert headers["tr_id"] == "TTTO1101U"


def test_unwired_live_executor_cannot_build_auth_headers():
    """The defect itself, pinned: no auth_manager -> no headers."""
    import asyncio

    executor = OrderExecutor(ExecutionConfig(trading_mode="REAL"))

    assert asyncio.run(executor._build_auth_headers(tr_id="TTTO1101U")) is None


# ---------------------------------------------------------------------------
# Review attempt-2 #6 — the auth assertion's CALL SITE, not just the helper
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Review attempt-2 #7 — the conflicting-alias branch
# ---------------------------------------------------------------------------


def test_conflicting_alias_spellings_are_rejected_by_name():
    """Both spellings with different values must name both, not pick one."""
    with pytest.raises(ValidationError, match="orders_per_second") as excinfo:
        ExecutionConfig(orders_per_second=5.0, requests_per_second=9.0)

    message = str(excinfo.value)
    assert "requests_per_second" in message
    assert "5.0" in message and "9.0" in message


def test_agreeing_alias_spellings_are_accepted():
    """Negative control: duplicates that agree are not an operator error."""
    config = ExecutionConfig(orders_per_second=5.0, requests_per_second=5.0)

    assert config.requests_per_second == 5.0
