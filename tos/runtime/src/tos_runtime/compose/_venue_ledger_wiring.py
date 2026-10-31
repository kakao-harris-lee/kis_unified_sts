"""The synthetic venue ledger's compose wiring — one config key, one transport kind (#1011 P2).

**What this module decides, and from what.** Exactly one thing: whether THIS boot records every
synthetic venue result into its own :mod:`tos_runtime.venue_ledger.synthetic` ledger and
reconciles against :class:`~tos_runtime.recon.witness_synthetic_venue.SyntheticVenueLedgerWitness`
instead of the store-derived :class:`~tos_runtime.recon.witness_synthetic.SyntheticLedgerWitness`.
It decides that from two facts and no others:

1. ``finality.yaml::witness`` (:class:`~tos_runtime.posttrade.config.PostTradeWitnessKind`) — the
   operator's own key, absent in every shipped tree, which is today's behaviour;
2. the boot's :class:`~tos_runtime.compose._transport_wiring.TransportKind`.

**No tree name reaches this decision** — the same discipline
:func:`~tos_runtime.compose.root._close_authority_for` already holds for the CLOSE bound. A tree
is a directory of config; what it IS, is its transport.

**The key ON with a ``kis-mock`` transport REFUSES the boot.** The ledger is the SYNTHETIC
venue's own record: a wrapper around a transport that actually reaches a broker would be writing
a record of someone else's venue and then reading it back as independent corroboration. That is
the exact fail-open shape plan §2 rejects option B for. The refusal is here, before any file is
created, rather than only inside
:func:`~tos_runtime.compose._transport_wiring.build_transport` — a refused boot must not leave a
``venue_ledger.sqlite3`` behind.

**Where the side tokens come from.** :class:`SyntheticVenueLedgerWitness` nets fills, so it needs
the two outbound side tokens, and it takes them as REQUIRED arguments precisely so no runtime
module spells one (``tos/runtime/tests/test_no_side_literals.py``). They come from the SAME
governed source :class:`~tos_runtime.riskstate.position.EvidencePositionReader` already takes
them from — ``action_flow_policy.yaml``'s own ``_runtime.side_tokens`` — re-loaded here rather
than threaded through, the accepted "a second read is a duplication of a read, never of
authority" pattern :mod:`tos_runtime.compose._release_wiring` documents for ``finality.yaml``.
A boot that turns the key on without that governed file is REFUSED: a witness that cannot sign a
fill cannot net a position, and guessing a token would be the long/short-symmetry break the
repo-wide pin forbids.

**Two parts, built at one moment, used at two.** The ledger WRITER is needed before
``_finalize`` (the transport wraps it); the WITNESS is needed after it (release + recovery
wiring). Both are built here, together, from one path — so "the thing that writes" and "the
thing that reads" can never be pointed at two different files.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``dataclasses``,
``pathlib``) + ``tos.canonical`` + ``tos_runtime.*`` only. No ``shared.*``, no network, no
``os.environ``.
"""

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

#: The file this module re-loads for its one key (module docstring) — the same literal
#: ``_wiring.py`` and :mod:`tos_runtime.compose._release_wiring` already each carry.
FINALITY_CONFIG_NAME = "finality.yaml"


class VenueLedgerWiringError(Exception):
    """A venue-ledger boot fact could not be established — fail-closed, never a silent default.

    Mirrors :class:`~tos_runtime.compose._transport_wiring.TransportWiringError`'s own role for
    the transport kind: raised during boot, before anything durable is created.
    """


@dataclass(frozen=True)
class SyntheticVenueLedgerParts:
    """This boot's venue-ledger parts; both ``None`` means "the key is absent" (today).

    Attributes:
        ledger: The WRITER, handed to
            :func:`~tos_runtime.compose._transport_wiring.build_transport` so the synthetic
            transport records before it answers. ``None`` keeps the bare kernel transport.
        witness: The READER, handed to the release and recovery reconciliation wiring. ``None``
            keeps :class:`~tos_runtime.recon.witness_synthetic.SyntheticLedgerWitness`.

    The two are always both set or both ``None``: a writer with no reader would record a venue
    nothing corroborates against, and a reader with no writer would observe an empty file and —
    because that witness reports ``positions_complete=True`` — read it as PROVEN FLAT.
    """

    ledger: SyntheticVenueLedger | None = None
    witness: SyntheticVenueLedgerWitness | None = None

    @property
    def enabled(self) -> bool:
        """Whether this boot uses the venue ledger at all."""
        return self.ledger is not None

    def close(self) -> None:
        """Close the writer's sqlite connection, if this boot opened one. Idempotent-safe to
        call on a boot that has none (the reader opens its own per read and closes it there).
        """
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
    """Resolve the one decision this module owns, and build both parts when it is ``on``.

    Args:
        config_dir: The boot's config directory — ``finality.yaml`` (the key) and, when the key
            is on, ``action_flow_policy.yaml`` (the side tokens) are read from it.
        data_dir: The data leaf the ledger file is created in, at
            :data:`~tos_runtime.venue_ledger.synthetic.VENUE_LEDGER_FILE_NAME`, mode ``0600``.
        transport_kind: This boot's transport. Only ``synthetic`` may carry a venue ledger.
        scheme: The SAME canonicalization scheme this runtime composes with, for the governed
            Action Flow Policy's own kernel issue.
        trading_date_now: The runtime's ONE trusted trading-date reader — the same reading the
            egress receipt is stamped with, passed to BOTH parts so the row and the receipt can
            never disagree about which day it is.

    Returns:
        Both parts, or an all-``None`` :class:`SyntheticVenueLedgerParts` when the key is absent.

    Raises:
        VenueLedgerWiringError: The key is on for a transport that reaches a broker.
        ~tos_runtime.posttrade.config.FinalityConfigError: ``finality.yaml`` is unreadable or
            its ``witness`` key names no known witness (propagated, not swallowed).
        ~tos_runtime.venue.VenuePolicyConfigError: The key is on and ``action_flow_policy.yaml``
            is missing or malformed (propagated — the witness cannot sign a fill without it).
        ~tos_runtime.venue_ledger.synthetic.VenueLedgerWriteFailed: The ledger file could not be
            created at mode ``0600`` (propagated).
    """
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
