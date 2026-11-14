"""The synthetic venue ledger's compose wiring — one config key, one transport kind (#1011 P2)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from tos.canonical import CanonicalizationScheme

from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.posttrade.config import (
    PostTradeWitnessKind,
    load_finality_config,
)
from tos_runtime.recon.witness_synthetic_venue import SyntheticVenueLedgerWitness
from tos_runtime.riskstate.policies import (
    ACTION_FLOW_POLICY_CONFIG_NAME,
    load_action_flow_policy,
)
from tos_runtime.venue_ledger.synthetic import (
    VENUE_LEDGER_FILE_NAME,
    SyntheticVenueLedger,
    VenueLedgerReader,
)

__all__ = [
    "FINALITY_CONFIG_NAME",
    "SyntheticVenueLedgerParts",
    "VenueLedgerWiringError",
    "build_synthetic_venue_ledger",
]

FINALITY_CONFIG_NAME = "finality.yaml"


class VenueLedgerWiringError(Exception):
    """A venue-ledger boot fact could not be established — fail-closed, never a silent default."""


@dataclass(frozen=True)
class SyntheticVenueLedgerParts:
    """This boot's venue-ledger parts; both ``None`` means "the key is absent" (today)."""

    ledger: SyntheticVenueLedger | None = None
    witness: SyntheticVenueLedgerWitness | None = None

    @property
    def enabled(self) -> bool:
        """Whether this boot uses the venue ledger at all."""
        return self.ledger is not None

    def close(self) -> None:
        """Close the writer's sqlite connection, if this boot opened one. Idempotent-safe to"""
        if self.ledger is not None:
            self.ledger.close()


def build_synthetic_venue_ledger(
    *,
    config_dir: Path,
    data_dir: Path,
    transport_kind: TransportKind,
    scheme: CanonicalizationScheme,
    trading_date_now: Callable[[], str | None],
) -> SyntheticVenueLedgerParts:
    """Resolve the one decision this module owns, and build both parts when it is ``on``."""
    finality_config = load_finality_config(config_dir / FINALITY_CONFIG_NAME)
    if finality_config.witness is not PostTradeWitnessKind.SYNTHETIC_VENUE_LEDGER:
        return SyntheticVenueLedgerParts()
    if transport_kind is not TransportKind.SYNTHETIC:
        raise VenueLedgerWiringError(
            f"{FINALITY_CONFIG_NAME}::witness is "
            f"{PostTradeWitnessKind.SYNTHETIC_VENUE_LEDGER.value!r} but this boot's transport "
            f"is {transport_kind.value!r} — the venue ledger is the SYNTHETIC venue's own "
            "record, and a transport that reaches a broker must be corroborated by that "
            "broker, never by a file this process wrote; refusing to boot"
        )
    buy_side_token, sell_side_token = load_action_flow_policy(
        config_dir / ACTION_FLOW_POLICY_CONFIG_NAME, scheme=scheme
    ).side_tokens
    path = data_dir / VENUE_LEDGER_FILE_NAME
    ledger = SyntheticVenueLedger(path)
    witness = SyntheticVenueLedgerWitness(
        VenueLedgerReader(path),
        buy_side_token=buy_side_token,
        sell_side_token=sell_side_token,
        trading_date_now=trading_date_now,
    )
    return SyntheticVenueLedgerParts(ledger=ledger, witness=witness)
