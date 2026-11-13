"""``tos_runtime.compose`` Coordinator-precondition wiring — TOS Phase 3 Wave 2 Lane B-R."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml
from tos.egressgw import TransportNature
from tos.engine import TransportNatureLike

from tos_runtime.authority.epoch import SafetyAuthorityEpochService
from tos_runtime.brokercap.instance import InstanceDocument
from tos_runtime.brokercap.scopes import BrokerScope
from tos_runtime.compose._nonlive_admission import nonlive_broker_consuming_admitted

__all__ = [
    "COORDINATOR_PRECONDITIONS_CONFIG_NAME",
    "CoordinatorPreconditionsConfig",
    "CoordinatorPreconditionsConfigError",
    "RuntimeCoordinatorPreconditions",
    "load_coordinator_preconditions_config",
]

COORDINATOR_PRECONDITIONS_CONFIG_NAME = "coordinator_preconditions.yaml"

_NOT_AUTHORIZED = "NOT_AUTHORIZED"

_SUPPORTED_LIVE_AUTHORIZATION_STATES = frozenset({_NOT_AUTHORIZED})


class CoordinatorPreconditionsConfigError(Exception):
    """Raised when the Coordinator-preconditions config is missing, malformed,"""


@dataclass(frozen=True)
class CoordinatorPreconditionsConfig:
    """The operator-configured Coordinator-precondition governance facts."""

    live_authorization_state: str
    nonlive_broker_consuming_admitted: bool


def load_coordinator_preconditions_config(path: Path) -> CoordinatorPreconditionsConfig:
    """Load + fail-closed-validate ``coordinator_preconditions.example.yaml``-shaped config."""
    if not path.is_file():
        raise CoordinatorPreconditionsConfigError(
            f"coordinator-preconditions config file not found: {path}"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CoordinatorPreconditionsConfigError(
            f"coordinator-preconditions config file could not be read: {path}"
        ) from exc
    try:
        raw: Any = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CoordinatorPreconditionsConfigError(
            f"coordinator-preconditions config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise CoordinatorPreconditionsConfigError(
            f"coordinator-preconditions config file must be a top-level mapping: {path}"
        )
    value = raw.get("live_authorization_state")
    if value is None:
        raise CoordinatorPreconditionsConfigError(
            f"{path}: 'live_authorization_state' is missing or still null "
            "(named-TBD) — refusing to start until an operator supplies a "
            "concrete, spec-cited governance value"
        )
    if not isinstance(value, str) or value not in _SUPPORTED_LIVE_AUTHORIZATION_STATES:
        raise CoordinatorPreconditionsConfigError(
            f"{path}: 'live_authorization_state' {value!r} is not a supported "
            f"posture (supported: {sorted(_SUPPORTED_LIVE_AUTHORIZATION_STATES)}) "
            "— no runtime wiring exists yet for any other restricted-live "
            "governance posture (fail-closed, never silently trusted)"
        )
    nonlive_block = raw.get("nonlive_broker_consuming")
    if not isinstance(nonlive_block, dict):
        raise CoordinatorPreconditionsConfigError(
            f"{path}: 'nonlive_broker_consuming' is missing or not a mapping "
            "— refusing to start until an operator supplies "
            "{admitted: bool} (T2 lane B; plan §2 decision 7)"
        )
    nonlive_admitted = nonlive_block.get("admitted")
    if nonlive_admitted is None:
        raise CoordinatorPreconditionsConfigError(
            f"{path}: 'nonlive_broker_consuming.admitted' is missing or "
            "still null (named-TBD) — refusing to start until an operator "
            "supplies a concrete true/false posture (plan §2 decision 7 / "
            "§7 operator disposition row 1)"
        )
    if not isinstance(nonlive_admitted, bool):
        raise CoordinatorPreconditionsConfigError(
            f"{path}: 'nonlive_broker_consuming.admitted' must be a bool, "
            f"got {nonlive_admitted!r}"
        )
    return CoordinatorPreconditionsConfig(
        live_authorization_state=value,
        nonlive_broker_consuming_admitted=nonlive_admitted,
    )


class RuntimeCoordinatorPreconditions:
    """The runtime implementation of the kernel's ``CoordinatorPreconditions`` Protocol"""

    def __init__(
        self,
        *,
        epoch_service: SafetyAuthorityEpochService | None,
        live_authorization_state: str | None,
        nonlive_admitted: bool | None = None,
        active_scope: BrokerScope | None = None,
        instance_document: InstanceDocument | None = None,
    ) -> None:
        """Wire the preconditions object over its injected ports."""
        self._epoch_service = epoch_service
        self._live_authorization_state = live_authorization_state
        self._nonlive_admitted = nonlive_admitted
        self._active_scope = active_scope
        self._instance_document = instance_document
        self._bound_epoch: int | None = (
            epoch_service.current_epoch() if epoch_service is not None else None
        )

    def authority_epoch_current(self) -> bool | None:
        """Whether this runtime's bound Safety Authority epoch is still current (§5.1)."""
        if self._epoch_service is None:
            return None
        return self._epoch_service.epoch_current(self._bound_epoch)

    def live_scope_authorized(
        self, transport_nature: TransportNatureLike | None
    ) -> bool | None:
        """Whether ``transport_nature`` may proceed under the current live-scope"""
        if self._live_authorization_state is None:
            return None
        if self._live_authorization_state not in _SUPPORTED_LIVE_AUTHORIZATION_STATES:
            return None
        if transport_nature is None:
            return False
        if transport_nature.reaches_broker is False:
            return True
        if transport_nature.reaches_broker is True:
            verdict = nonlive_broker_consuming_admitted(
                posture_admitted=self._nonlive_admitted,
                transport_nature=cast(TransportNature, transport_nature),
                active_scope=self._active_scope,
                instance_document=self._instance_document,
            )
            return verdict.admitted
        return False


class _ReplayPreconditions:
    """A ``True``/``True`` stand-in ``CoordinatorPreconditions`` used ONLY by the"""

    def authority_epoch_current(self) -> bool | None:
        """Always ``True`` — see the class docstring for why this is safe."""
        return True

    def live_scope_authorized(
        self, _transport_nature: TransportNatureLike | None
    ) -> bool | None:
        """Always ``True`` — see the class docstring for why this is safe."""
        return True
