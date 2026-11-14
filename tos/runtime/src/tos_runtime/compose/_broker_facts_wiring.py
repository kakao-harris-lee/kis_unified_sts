"""Item 12's broker-side readers for the option (a) mock class (PR-3a, operator decision"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from tos.brokercap import mock_order_without_position_or_cash

from tos_runtime.brokercap import BrokerScopesConfig
from tos_runtime.compose._kis_credential_wiring import (
    KisCredentialSessionsCell,
    kis_mock_credential_session,
    kis_transport_pacing,
)
from tos_runtime.time.sources import MonotonicSource
from tos_runtime.transport.kis_mock.broker_facts import (
    BROKER_FACTS_CONFIG_NAME,
    KisMockBrokerFacts,
    load_broker_facts_config,
)
from tos_runtime.transport.kis_mock.client import build_client
from tos_runtime.transport.kis_mock.config import KisMockTransportConfig
from tos_runtime.transport.kis_mock.credential_session import KisCredentialSessions
from tos_runtime.transport.kis_mock.token import EvidenceRecorder

__all__ = ["BrokerFactsWiring", "build_broker_facts"]

FlagReader = Callable[[], bool | None]


class BrokerFactsWiring:
    """The (possibly absent) mock-account source plus the readers compose hands on."""

    def __init__(self) -> None:
        self.source: KisMockBrokerFacts | None = None
        self.enabled = False

    def _pick(
        self, own: FlagReader, mock: Callable[[KisMockBrokerFacts], bool | None]
    ) -> FlagReader:
        def _read() -> bool | None:
            if not self.enabled:
                return own()
            return None if self.source is None else mock(self.source)

        return _read

    def tradability(self, own: FlagReader) -> FlagReader:
        return self._pick(own, lambda facts: facts.tradability_facts_current())

    def account(self, own: FlagReader) -> FlagReader:
        return self._pick(own, lambda facts: facts.account_facts_current())

    def generation(self) -> bool | None:
        """``broker_constraint_generation_current``'s mock-class source; ``None`` otherwise"""
        if not self.enabled or self.source is None:
            return None
        return self.source.generation_current()


def build_broker_facts(
    *,
    config_dir: Path,
    broker_scopes: BrokerScopesConfig,
    transport_config: KisMockTransportConfig | None,
    credential_sessions_cell: KisCredentialSessionsCell,
    monotonic: MonotonicSource,
    evidence_sink: EvidenceRecorder,
    account: str,
    instrument: str,
) -> BrokerFactsWiring:
    """Build the wiring (module docstring)."""
    wiring = BrokerFactsWiring()
    if transport_config is None or not mock_order_without_position_or_cash(
        broker_scopes.active_scope.capability_tuples
    ):
        return wiring
    wiring.enabled = True
    config = load_broker_facts_config(config_dir / BROKER_FACTS_CONFIG_NAME)
    client = build_client(transport_config)

    def _build(sessions: KisCredentialSessions) -> None:
        wiring.source = KisMockBrokerFacts(
            config=config,
            client=client,
            credential_session=kis_mock_credential_session(
                sessions,
                client=client,
                token_endpoint_base=transport_config.endpoint_rest_base,
                token_path=transport_config.token_path,
                token_reissue_min_interval_s=transport_config.token_reissue_min_interval_s,
                pacing=kis_transport_pacing(transport_config),
            ),
            monotonic=monotonic,
            evidence_sink=evidence_sink,
            account=account,
            instrument=instrument,
        )

    credential_sessions_cell.on_ready(_build)
    return wiring
