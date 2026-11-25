"""Instrument-keyed strategy registry — the G4 dispatch decision (design #31 §3.3 / D2)."""

from __future__ import annotations

from dataclasses import dataclass

from tos.dsl import AuthoredStrategy, EvaluationConfig
from tos.engine._base import ArtifactIntegrityError
from tos.engine.admission import strategy_admissible
from tos.engine.records import InstrumentKey, RegisteredStrategy
from tos.engine.vocabulary import AdmissionVerdict, DispatchResolution

__all__ = ["Dispatch", "RegistrationRefused", "StrategyRegistry"]


class RegistrationRefused(ArtifactIntegrityError):
    """A strategy registration was refused (fail-closed; design #31 §3.3/§3.5)."""


@dataclass(frozen=True)
class Dispatch:
    """The ∅-both-ways result of a registry lookup (design #31 §6)."""

    resolution: DispatchResolution
    entries: tuple[RegisteredStrategy, ...] = ()


class StrategyRegistry:
    """An instrument-keyed registry of admitted Authored Strategies (design #31 §3.3)."""

    def __init__(self) -> None:
        """Create an empty registry (no key is registered; every lookup is ``MISSING``)."""
        self._entries: dict[tuple[str, str], list[RegisteredStrategy]] = {}

    @staticmethod
    def _key_tuple(key: InstrumentKey) -> tuple[str, str]:
        """The hashable form of an :class:`InstrumentKey`."""
        return (key.account, key.instrument)

    def declare_key(self, key: InstrumentKey) -> None:
        """Declare a key with **zero** strategies — an explicit, defined no-action scope."""
        self._entries.setdefault(self._key_tuple(key), [])

    def register(
        self,
        strategy: AuthoredStrategy,
        config: EvaluationConfig,
        *,
        key: InstrumentKey | None = None,
    ) -> RegisteredStrategy:
        """Admit and register one Authored Strategy under its **structurally derived** key."""
        admission = strategy_admissible(strategy)
        if admission.verdict is not AdmissionVerdict.ADMISSIBLE:
            raise RegistrationRefused(
                "strategy registration refused — typed admission is INADMISSIBLE: "
                + "; ".join(admission.reasons)
            )
        derived = admission.instrument_key
        if derived is None:  # pragma: no cover - ADMISSIBLE always carries a key
            raise RegistrationRefused(
                "strategy registration refused — admission reported ADMISSIBLE without a derived "
                "dispatch key (fail-closed)"
            )
        if key is not None and key != derived:
            raise RegistrationRefused(
                f"asserted registry key {self._key_tuple(key)} does not match the scope the "
                f"strategy itself declares {self._key_tuple(derived)} — the key is derived from "
                "the artifact, never self-reported (design #31 §3.3)"
            )
        entry = RegisteredStrategy(
            strategy=strategy, config=config, instrument_key=derived
        )
        self._entries.setdefault(self._key_tuple(derived), []).append(entry)
        return entry

    def resolve(self, key: InstrumentKey) -> Dispatch:
        """Resolve an instrument key, distinguishing *missing* from *explicitly empty*."""
        entries = self._entries.get(self._key_tuple(key))
        if entries is None:
            return Dispatch(resolution=DispatchResolution.MISSING)
        if not entries:
            return Dispatch(resolution=DispatchResolution.EXPLICIT_EMPTY)
        return Dispatch(
            resolution=DispatchResolution.DISPATCHED, entries=tuple(entries)
        )

    def declared_keys(self) -> tuple[InstrumentKey, ...]:
        """The keys currently declared, in insertion order (declared-empty keys included)."""
        return tuple(
            InstrumentKey(account=account, instrument=instrument)
            for account, instrument in self._entries
        )
