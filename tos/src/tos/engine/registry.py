"""Instrument-keyed strategy registry — the G4 dispatch decision (design #31 §3.3 / D2).

``TargetSpec``'s scope fields are literal strings (``tos.dsl.vocabulary`` lines 193-205, not
operands), so one Authored Strategy targets exactly one hard-coded (account, instrument) pair. The
dispatch decision follows that structural fact: an **instrument-keyed registry** whose key is
*derived from the strategy's own declared scope*, never asserted by the registrant.

Three fail-closed refusals (design #31 §3.3):

1. **key ↔ declaration mismatch** — registering under a key the strategy does not declare is
   refused, so "the registry says X but the strategy targets Y" is unconstructable;
2. **``None`` (wildcard) scope** — refused; the dispatch-layer mirror of RFC-003 §9:279-283;
3. **inadmissible strategy** — the typed D1↔D4 admission gate must pass positively first
   (:mod:`tos.engine.admission`).

Lookup is ∅-both-ways (design #31 §6/§11): a **missing** key is fail-closed (nothing is
evaluated), a key registered with **zero** strategies is a *defined* no-action. Collapsing the two
in either direction is the #17/#26 vacuity defect class.

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #31 §0.3).
"""

from __future__ import annotations

from dataclasses import dataclass

from tos.dsl import AuthoredStrategy, EvaluationConfig
from tos.engine._base import ArtifactIntegrityError
from tos.engine.admission import strategy_admissible
from tos.engine.records import InstrumentKey, RegisteredStrategy
from tos.engine.vocabulary import AdmissionVerdict, DispatchResolution

__all__ = ["Dispatch", "RegistrationRefused", "StrategyRegistry"]


class RegistrationRefused(ArtifactIntegrityError):
    """A strategy registration was refused (fail-closed; design #31 §3.3/§3.5).

    Subclasses :class:`~tos.canonical.ArtifactIntegrityError` (itself a ``ValueError``) so a
    refusal is an error the caller must handle, never a silently-dropped registration.
    """


@dataclass(frozen=True)
class Dispatch:
    """The ∅-both-ways result of a registry lookup (design #31 §6).

    ``resolution is DispatchResolution.DISPATCHED`` is the only value that yields strategies;
    ``MISSING`` and ``EXPLICIT_EMPTY`` both yield none but for **different, recorded** reasons.
    """

    resolution: DispatchResolution
    entries: tuple[RegisteredStrategy, ...] = ()


class StrategyRegistry:
    """An instrument-keyed registry of admitted Authored Strategies (design #31 §3.3).

    Slice #1 holds one entry; a multi-symbol universe is N entries with **no interface change**
    (design #31 §3.3). The registry is a mutable container by design — registration is a setup-time
    act, not a decision-time one — but every value it stores is a frozen artifact.
    """

    def __init__(self) -> None:
        """Create an empty registry (no key is registered; every lookup is ``MISSING``)."""
        self._entries: dict[tuple[str, str], list[RegisteredStrategy]] = {}

    @staticmethod
    def _key_tuple(key: InstrumentKey) -> tuple[str, str]:
        """The hashable form of an :class:`InstrumentKey`."""
        return (key.account, key.instrument)

    def declare_key(self, key: InstrumentKey) -> None:
        """Declare a key with **zero** strategies — an explicit, defined no-action scope.

        The ∅-both-ways positive side (design #31 §6): a declared-but-empty key resolves to
        ``EXPLICIT_EMPTY`` (a defined no-action), which is materially different from a key that was
        never declared at all (``MISSING`` — fail-closed).

        Args:
            key: The instrument key to declare.
        """
        self._entries.setdefault(self._key_tuple(key), [])

    def register(
        self,
        strategy: AuthoredStrategy,
        config: EvaluationConfig,
        *,
        key: InstrumentKey | None = None,
    ) -> RegisteredStrategy:
        """Admit and register one Authored Strategy under its **structurally derived** key.

        Args:
            strategy: The in-process typed Authored Strategy.
            config: Its authored configuration (authored constants only — design #31 §3.2 (2)).
            key: An optional *asserted* key. When given it is **checked against** the derived key
                and a mismatch is refused; it never overrides the derivation (구조 파생 > 자기신고).

        Returns:
            The stored :class:`~tos.engine.records.RegisteredStrategy`.

        Raises:
            RegistrationRefused: If typed admission fails, if the key cannot be derived (no
                declared scope / multiple scopes / a ``None`` wildcard scope), or if an asserted
                key disagrees with the derived one.
        """
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
        entry = RegisteredStrategy(strategy=strategy, config=config, instrument_key=derived)
        self._entries.setdefault(self._key_tuple(derived), []).append(entry)
        return entry

    def resolve(self, key: InstrumentKey) -> Dispatch:
        """Resolve an instrument key, distinguishing *missing* from *explicitly empty*.

        Args:
            key: The event's instrument key.

        Returns:
            A :class:`Dispatch` whose ``resolution`` is ``MISSING`` (key never declared —
            fail-closed, nothing is evaluated), ``EXPLICIT_EMPTY`` (declared with zero strategies —
            a defined no-action), or ``DISPATCHED`` with the registered entries.
        """
        entries = self._entries.get(self._key_tuple(key))
        if entries is None:
            return Dispatch(resolution=DispatchResolution.MISSING)
        if not entries:
            return Dispatch(resolution=DispatchResolution.EXPLICIT_EMPTY)
        return Dispatch(resolution=DispatchResolution.DISPATCHED, entries=tuple(entries))

    def declared_keys(self) -> tuple[InstrumentKey, ...]:
        """The keys currently declared, in insertion order (declared-empty keys included)."""
        return tuple(
            InstrumentKey(account=account, instrument=instrument)
            for account, instrument in self._entries
        )
