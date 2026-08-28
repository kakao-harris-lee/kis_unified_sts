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


def test_live_futures_path_config_yields_a_constructed_limiter():
    """The real order_router wiring, fed the real execution.yaml section."""
    from services.order_router.main import build_live_execution_config

    config = build_live_execution_config(_execution_section(), redis_url=_REDIS_URL)
    executor = OrderExecutor(config)

    assert executor._rate_limiter is not None
    assert executor._rate_limiter.key == "kis:ratelimit:futures"


def test_live_futures_path_honours_the_configured_pacing():
    """``orders_per_second: 5.0`` must reach the limiter, not be discarded.

    The expected value is hardcoded on purpose. Comparing the config back to
    the section it came from passes for ANY consistent wiring, including one
    reading the wrong key — it only proves the object is self-consistent.
    """
    from services.order_router.main import build_live_execution_config

    section = _execution_section()
    assert "orders_per_second" in section, "execution.yaml uses the legacy spelling"
    assert section["orders_per_second"] == 5.0, (
        "execution.yaml changed its configured pacing; update this pin "
        "deliberately rather than re-deriving it from the file"
    )

    config = build_live_execution_config(section, redis_url=_REDIS_URL)
    executor = OrderExecutor(config)

    assert config.requests_per_second == 5.0
    assert executor._rate_limiter.max_requests == 5


def test_pacing_falls_back_to_the_model_default_without_the_legacy_key():
    """Negative: with the key REMOVED the default must apply, not 5.0.

    Without this, a wiring that hardcoded 5.0 anywhere in the path would pass
    the positive test above.
    """
    from services.order_router.main import build_live_execution_config

    section = _execution_section()
    section.pop("orders_per_second")

    config = build_live_execution_config(section, redis_url=_REDIS_URL)

    assert config.requests_per_second == 20.0
    assert OrderExecutor(config)._rate_limiter.max_requests == 20


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


def test_live_config_forces_real_trading_mode():
    """The live branch owns this decision, not the TRADING_MODE env var.

    The live/paper selector is FUTURES_ORDER_ROUTER. With TRADING_MODE unset,
    execution.yaml resolves trading_mode to PAPER; KISFuturesAdapter derives
    ``is_mock = trading_mode != "REAL"``, so the LIVE router would have aimed
    at the KIS mock host — which does not serve futures at all.
    """
    from services.order_router.main import build_live_execution_config

    section = _execution_section()
    section["trading_mode"] = "PAPER"  # what ${TRADING_MODE:PAPER} yields unset

    config = build_live_execution_config(section, redis_url=_REDIS_URL)

    assert config.trading_mode == "REAL"


def test_live_config_forces_real_even_when_yaml_says_mock():
    from services.order_router.main import build_live_execution_config

    section = _execution_section()
    section["trading_mode"] = "MOCK"

    assert (
        build_live_execution_config(section, redis_url=_REDIS_URL).trading_mode
        == "REAL"
    )


def test_live_startup_refuses_an_executor_without_an_auth_manager():
    """A live router that silently places zero orders is worse than one that
    refuses to start."""
    from services.order_router.main import _assert_live_executor_can_authenticate

    executor = OrderExecutor(ExecutionConfig(trading_mode="REAL"))
    assert executor.auth_manager is None

    with pytest.raises(RuntimeError, match="no auth_manager"):
        _assert_live_executor_can_authenticate(executor)


def test_live_startup_refuses_empty_credentials():
    from types import SimpleNamespace

    from services.order_router.main import _assert_live_executor_can_authenticate

    executor = OrderExecutor(
        ExecutionConfig(trading_mode="REAL"),
        auth_manager=SimpleNamespace(config=SimpleNamespace(app_key="", app_secret="")),
    )

    with pytest.raises(RuntimeError, match="credentials are empty"):
        _assert_live_executor_can_authenticate(executor)


def test_live_startup_accepts_a_real_auth_manager():
    """Negative control: a properly wired executor starts."""
    from types import SimpleNamespace

    from services.order_router.main import _assert_live_executor_can_authenticate

    executor = OrderExecutor(
        ExecutionConfig(trading_mode="REAL"),
        auth_manager=SimpleNamespace(
            config=SimpleNamespace(app_key="k", app_secret="s")
        ),
    )

    _assert_live_executor_can_authenticate(executor)  # must not raise


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


def test_live_executor_builder_refuses_empty_credentials(monkeypatch):
    """Deleting the assertion CALL must break something.

    The helper was pinned by three tests while its call site was inlined in
    `_build_and_run`, so replacing the call with `pass` killed nothing.
    """
    from services.order_router.main import build_live_order_executor
    from shared.kis.auth import KISAuthConfig

    # KISAuthConfig.__post_init__ falls back to these; a developer shell that
    # has them set would otherwise mask the empty-credential case.
    monkeypatch.delenv("KIS_APP_KEY", raising=False)
    monkeypatch.delenv("KIS_APP_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="credentials are empty"):
        build_live_order_executor(
            _execution_section(),
            redis_url=_REDIS_URL,
            kis_auth=KISAuthConfig(app_key="", app_secret="", is_real=True),
        )


def test_live_executor_builder_returns_a_wired_executor(monkeypatch):
    """Negative control: with credentials it builds and carries the manager."""
    from services.order_router.main import build_live_order_executor
    from shared.kis.auth import KISAuthConfig

    monkeypatch.delenv("KIS_APP_KEY", raising=False)
    monkeypatch.delenv("KIS_APP_SECRET", raising=False)

    executor = build_live_order_executor(
        _execution_section(),
        redis_url=_REDIS_URL,
        kis_auth=KISAuthConfig(app_key="k", app_secret="s", is_real=True),
    )

    assert executor.auth_manager is not None
    assert executor.config.trading_mode == "REAL"
    assert executor._rate_limiter is not None


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
