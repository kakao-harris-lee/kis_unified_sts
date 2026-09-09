"""Operator-configured egress coordinates + capsule-terminus stand-in
inputs (TOS Phase 4 작업 6 §2.1, plan doc
``docs/plans/2026-09-08-tos-phase4-send-seal-plan.md``).

``tos_runtime.compose._wiring._build_context_resolver`` used to construct its
``EgressCoordinateSet`` (the ADR-002-013 §11.2/§12 authorized-egress-
coordinate literal ``BrokerEgressGateway`` verifies every attempt's request
against) from **eight bare Python literals** — ``endpoint="synthetic://paper/order"``,
``action="NEW_ORDER"``, ``method="SUBMIT"``, ``route_identity="synthetic-route"``,
``credential_generation=0``, ``broker_session_generation=0``,
``egress_generation=1``, ``active_principal=f"egressgw-{environment_label}"``
— plus a ninth value, ``capsule_egress_request_digest``, computed from a
literal two-field dict (``{"account": ..., "instrument": ...}``). CLAUDE.md's
non-negotiable configuration-driven rule ("thresholds, symbols, ... belong in
YAML/env/config files, not hardcoded branches") applies to every one of
these: they are per-deployment authorization facts, not compose-root
identity. (``endpoint`` was originally left out of this module's scope —
review finding #2, 2026-09-09 — because the seal now makes it load-bearing
via ``SendSeal.endpoint``/``outbound_coordinates``/``seal_digest``, so a
bare literal here is no longer merely a missing-config gap; it is now
included alongside the other seven.)

This module moves all nine out to composition config, mirroring
:mod:`tos_runtime.compose._egress_attestations`'s own mechanism exactly:
every field is a named-TBD ``null`` in the example config, and a still-null
field refuses composition at startup (fail-closed, never a silent default).

**``active_principal`` templating.** The configured value MAY contain the
literal token ``{environment_label}``, substituted by :func:`load_egress_coordinates`
with the runtime's own environment label — the ONLY templating this loader
performs (never a general format-string evaluation of operator-authored
config).

**``capsule_terminus_fields`` — a STAND-IN, not the real thing.** ``tos.egress.
EgressRequestRecord.request_bytes_digest`` is verified (item 17,
``exact_binding_holds``) against ``capsule_egress_request_digest`` here, and
design #34's own gateway survey (2026-09-08, this plan's §survey) is explicit
that this compose root has **no capsule chain** yet — ``capsule_egress_
request_digest`` is a STAND-IN for that eventual capsule-chain terminus
(design #34 / EGRESS-EV-003 "+Security", not landed in this Phase). Rather
than hardcode which fields feed that stand-in digest, ``capsule_terminus_
fields`` names them as config: a list of :class:`~tos_runtime.compose._types.
ConstructionConfig` field names (currently ``["account", "instrument"]``,
matching this compose root's prior literal dict exactly) whose *values* are
digested — the value set is still a genuine per-attempt derivation, never a
literal, only the field-name SELECTION moved to config. :func:`load_egress_coordinates`
validates every named field actually exists on ``ConstructionConfig`` at
boot, so a typo'd or renamed field fails closed at startup rather than
raising deep inside a digest computation on the first attempt.

Phase 5+ (a real capsule chain, EGRESS-EV-003 "+Security" byte-level
reconstruction / route confinement) replaces this stand-in with a genuine
capsule-terminus digest; this module's docstring and the example config's own
comments both say so, so a future reader does not mistake the stand-in for
the finished mechanism.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

import yaml

from tos_runtime.compose._types import ConstructionConfig

__all__ = [
    "EgressCoordinateConfigError",
    "EgressCoordinatesConfig",
    "load_egress_coordinates",
]

#: The ONLY templating this loader performs on ``active_principal``.
_ENVIRONMENT_LABEL_TOKEN = "{environment_label}"


class EgressCoordinateConfigError(Exception):
    """Raised when the egress-coordinates config is missing, malformed,
    carries an unfilled (named-TBD) field, or names an unknown
    ``capsule_terminus_fields`` entry — fail-closed at load, never a silent
    default."""


@dataclass(frozen=True)
class EgressCoordinatesConfig:
    """The 8 ``EgressCoordinateSet`` authorized-coordinate literals plus
    ``capsule_terminus_fields`` (module docstring), moved out of
    ``tos_runtime.compose._wiring._build_context_resolver``.

    ``account`` is deliberately NOT here: it is a genuine live per-attempt
    value (``ConstructionConfig.account``), never an authorized-coordinate
    literal.
    """

    endpoint: str
    action: str
    method: str
    route_identity: str
    credential_generation: int
    broker_session_generation: int
    egress_generation: int
    #: Already ``{environment_label}``-substituted by the loader.
    active_principal: str
    #: :class:`~tos_runtime.compose._types.ConstructionConfig` field names
    #: whose values feed the capsule-terminus stand-in digest (module
    #: docstring) — currently ``("account", "instrument")``.
    capsule_terminus_fields: tuple[str, ...]


def _require_block(raw: Any, field: str, path: Path) -> dict:
    block = raw.get(field) if isinstance(raw, dict) else None
    if not isinstance(block, dict):
        raise EgressCoordinateConfigError(
            f"{path}: egress-coordinates config missing a mapping entry "
            f"for {field!r} — refusing to start"
        )
    return block


def _require_str(raw: Any, field: str, path: Path) -> str:
    block = _require_block(raw, field, path)
    value = block.get("value")
    if not isinstance(value, str) or not value:
        raise EgressCoordinateConfigError(
            f"{path}: {field!r}.value is still null (named-TBD), empty, or "
            "not a string — refusing to start until an operator attests a "
            "concrete value"
        )
    return value


def _require_int(raw: Any, field: str, path: Path) -> int:
    block = _require_block(raw, field, path)
    value = block.get("value")
    if isinstance(value, bool) or not isinstance(value, int):
        raise EgressCoordinateConfigError(
            f"{path}: {field!r}.value is still null (named-TBD) or not an "
            "int — refusing to start until an operator attests a concrete "
            "value"
        )
    return value


def load_egress_coordinates(
    path: Path, *, environment_label: str
) -> EgressCoordinatesConfig:
    """Load + fail-closed-validate the egress-coordinates config from
    ``path`` (shaped like
    ``tos/runtime/config/egress_coordinates.example.yaml``).

    Args:
        path: The config file (per-deployment, every named-TBD filled).
        environment_label: Substituted for the ``{environment_label}``
            token in ``active_principal``, if present.

    Raises:
        EgressCoordinateConfigError: The file is missing/unreadable/not
            valid YAML/not a mapping, an entry is absent, a field is still
            ``null`` (named-TBD), or ``capsule_terminus_fields`` is empty,
            not a list of strings, or names a field that does not exist on
            :class:`~tos_runtime.compose._types.ConstructionConfig`.
    """
    if not path.is_file():
        raise EgressCoordinateConfigError(
            f"egress-coordinates config file not found: {path}"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EgressCoordinateConfigError(
            f"egress-coordinates config file could not be read: {path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise EgressCoordinateConfigError(
            f"egress-coordinates config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise EgressCoordinateConfigError(
            f"egress-coordinates config file must be a top-level mapping: {path}"
        )

    endpoint = _require_str(raw, "endpoint", path)
    action = _require_str(raw, "action", path)
    method = _require_str(raw, "method", path)
    route_identity = _require_str(raw, "route_identity", path)
    credential_generation = _require_int(raw, "credential_generation", path)
    broker_session_generation = _require_int(raw, "broker_session_generation", path)
    egress_generation = _require_int(raw, "egress_generation", path)
    active_principal = _require_str(raw, "active_principal", path).replace(
        _ENVIRONMENT_LABEL_TOKEN, environment_label
    )

    terminus_block = _require_block(raw, "capsule_terminus_fields", path)
    terminus_value = terminus_block.get("value")
    if (
        not isinstance(terminus_value, list)
        or not terminus_value
        or not all(isinstance(name, str) and name for name in terminus_value)
    ):
        raise EgressCoordinateConfigError(
            f"{path}: 'capsule_terminus_fields.value' is still null "
            "(named-TBD), empty, or not a non-empty list of strings — "
            "refusing to start"
        )
    known_fields = {f.name for f in fields(ConstructionConfig)}
    unknown = [name for name in terminus_value if name not in known_fields]
    if unknown:
        raise EgressCoordinateConfigError(
            f"{path}: 'capsule_terminus_fields.value' names field(s) not "
            f"present on ConstructionConfig: {unknown!r} — refusing to start"
        )

    return EgressCoordinatesConfig(
        endpoint=endpoint,
        action=action,
        method=method,
        route_identity=route_identity,
        credential_generation=credential_generation,
        broker_session_generation=broker_session_generation,
        egress_generation=egress_generation,
        active_principal=active_principal,
        capsule_terminus_fields=tuple(terminus_value),
    )
