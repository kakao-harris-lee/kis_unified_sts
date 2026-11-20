"""``KisCredentialSessionsCell`` — the two-step publish/dispatch contract."""

from __future__ import annotations

from typing import Any, cast

import pytest
from tos_runtime.compose._kis_credential_wiring import (
    KisCredentialSessionsCell,
    KisCredentialSessionsCellMisuse,
    build_kis_credential_sessions,
    kis_shared_app_key_gate,
    kis_shared_token_cache,
)
from tos_runtime.transport.kis_mock.config import KisMockTransportConfig
from tos_runtime.transport.kis_mock.credential_session import KisCredentialSessions


def _sentinel() -> KisCredentialSessions:
    """An opaque stand-in — the cell only ever hands it on, never reads it."""
    return cast(KisCredentialSessions, object())


class TestRegistrationPrecedesPublication:
    def test_registering_after_fill_refuses(self) -> None:
        cell = KisCredentialSessionsCell()
        cell.fill(_sentinel())

        with pytest.raises(KisCredentialSessionsCellMisuse) as excinfo:
            cell.on_ready(lambda _sessions: None)

        assert "registered too late" in str(excinfo.value)

    def test_registering_before_fill_is_dispatched_exactly_once(self) -> None:
        """The baseline: without it the refusal above would also pass against a cell that"""
        cell = KisCredentialSessionsCell()
        seen: list[Any] = []
        cell.on_ready(seen.append)
        sessions = _sentinel()

        cell.fill(sessions)
        assert seen == []

        cell.start_consumers()
        assert seen == [sessions]

        cell.start_consumers()
        assert seen == [sessions]


class TestDispatchNeedsAPublishedRegistry:
    def test_start_consumers_before_fill_refuses(self) -> None:
        cell = KisCredentialSessionsCell()
        cell.on_ready(lambda _sessions: None)

        with pytest.raises(KisCredentialSessionsCellMisuse) as excinfo:
            cell.start_consumers()

        assert "before fill()" in str(excinfo.value)


class TestACallbackFailureIsTheCallersProblem:
    def test_an_exception_propagates_out_of_start_consumers(self) -> None:
        """This is how a ``KisCredentialSessionConflict`` raised by the band reader becomes a"""
        cell = KisCredentialSessionsCell()

        def _explode(_sessions: KisCredentialSessions) -> None:
            raise RuntimeError("conflict")

        cell.on_ready(_explode)
        cell.fill(_sentinel())

        with pytest.raises(RuntimeError, match="conflict"):
            cell.start_consumers()


class TestTheSharedTokenCacheComesFromTheTransportConfig:
    """#1125: ``kis_mock_transport.yaml`` is where a boot learns it shares a token."""

    @staticmethod
    def _config(**overrides: Any) -> KisMockTransportConfig:
        base: dict[str, Any] = {
            "mode": "live",
            "endpoint_rest_base": "https://openapivts.koreainvestment.com:29443",
            "order_path": "/uapi/domestic-stock/v1/trading/order-cash",
            "token_path": "/oauth2/tokenP",
            "tr_id_buy": "VTTC0012U",
            "tr_id_sell": "VTTC0011U",
            "field_map": {},
            "static_body_fields": {},
            "price_scale": 100,
            "min_send_interval_ms": 2000,
            "app_key_request_wait_budget_ms": 4000,
            "token_reissue_min_interval_s": 65,
            "request_timeout_s": 10.0,
            "allow_plaintext_for_tests": False,
        }
        base.update(overrides)
        return KisMockTransportConfig(**base)

    def _cache_config(self) -> KisMockTransportConfig:
        return self._config(
            token_cache_path="/var/lib/tos/kis-mock-token/stock-mock.json",
            token_cache_refresh_margin_s=600,
            shared_pacer_path="/var/lib/tos/kis-mock-token/stock-mock.pace",
            shared_max_rps=2.0,
        )

    def test_a_config_without_a_cache_path_wires_none(self) -> None:
        assert kis_shared_token_cache(None) is None
        assert kis_shared_token_cache(self._config()) is None

    def test_the_cache_takes_its_path_and_margin_from_the_config(self) -> None:
        cache = kis_shared_token_cache(self._cache_config())
        assert cache is not None
        assert str(cache.path) == "/var/lib/tos/kis-mock-token/stock-mock.json"
        assert cache.refresh_margin_s == 600

    def test_a_config_without_a_pacer_path_wires_no_gate(self) -> None:
        assert kis_shared_app_key_gate(None) is None
        assert kis_shared_app_key_gate(self._config()) is None

    def test_the_gate_takes_its_path_and_rate_from_the_config(self) -> None:
        gate = kis_shared_app_key_gate(self._cache_config())
        assert gate is not None
        assert str(gate.path) == "/var/lib/tos/kis-mock-token/stock-mock.pace"
        assert gate.min_interval_s == pytest.approx(0.5)

    def test_every_session_of_this_boot_gets_that_one_cache_and_gate(self) -> None:
        """One registry, one cache, one gate: the order transport, the broker-facts reader,

        the fill witness and the loop witness all take their session from here, so none of
        them can open a second token lifecycle or a second queue on this app key.
        """
        config = self._cache_config()
        cache = kis_shared_token_cache(config)
        gate = kis_shared_app_key_gate(config)
        sessions = build_kis_credential_sessions(
            custody=cast(Any, object()),
            monotonic=cast(Any, object()),
            evidence_sink=cast(Any, object()),
            token_cache=cache,
            shared_gate=gate,
        )
        assert sessions._token_cache is cache
        assert sessions._shared_gate is gate
