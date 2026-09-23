"""``_loader_probe`` — run every boot-blocking loader against one ``config_dir`` and report
PASS/REFUSE per file, with the refusal verbatim.

**Why this is committed (review-794 MEDIUM-4).** The W-A A-5 landing record
(``docs/plans/2026-09-18-tos-config-adoption-and-carryover-plan.md`` §7.8) quotes a
"N PASS / M REFUSE" partition as its diagnosis of what still blocks a ``run`` boot. The first
cut of that record quoted the number from a scratch script that was never committed, so the
number could not be re-derived by a reader — this repo's own rule is that evidence has to be
re-runnable. This module is that script, committed, and
``test_deploy_approved_values.py::test_loader_probe_partition_is_as_recorded`` pins the
partition BY NAME (not merely by count), so the landing record's number cannot drift away from
what the loaders actually do.

``run`` itself stops at its own FIRST refusal (``construction.yaml``, ``_run_dispatch.py:94-99``),
so a sequential boot can never enumerate what else is blocked. This probe calls each loader
independently and therefore does.

Run it directly to print the table::

    PYTHONPATH=tos/src:tos/runtime/src python tos/runtime/tests/compose/_loader_probe.py \\
        config/tos_runtime/paper

Leading underscore: this is a helper, not a pytest module (pytest collects ``test_*.py`` only).
Hermetic: every loader here only READS the files it is given; nothing is written.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "PROBES",
    "ProbeOutcome",
    "ProbeSpec",
    "format_table",
    "refusing_labels",
    "run_probes",
]


def _scheme() -> Any:
    from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme

    return get_scheme(EV_L1_PROVISIONAL_VERSION)


#: The environment label the two ``{environment_label}``-templating loaders need. Any non-live
#: label works for a load-only probe; this one matches the compose e2e suite's own fixture.
_ENVIRONMENT_LABEL = "non-live-test"


def _unreachable_observer() -> Any:
    raise AssertionError("observer must not be reached during a config load")


# --------------------------------------------------------------------------
# One callable per probed loader. Each takes the config DIRECTORY, because several
# loaders read more than one file (the safety mesh reads three).
# --------------------------------------------------------------------------


def _time(d: Path) -> object:
    from tos_runtime.time.config import load_time_config

    return load_time_config(d / "time.yaml")


def _authority(d: Path) -> object:
    from tos_runtime.authority.epoch import load_authority_config

    return load_authority_config(d / "authority.yaml")


def _release(d: Path) -> object:
    from tos_runtime.release.config import load_release_config

    return load_release_config(d / "release.yaml")


def _calendar(d: Path) -> object:
    from tos_runtime.calendar.config import load_calendar_config

    return load_calendar_config(d / "calendar.yaml")


def _risk(d: Path) -> object:
    from tos_runtime.risk.aggregate import (
        load_adverse_scenario_set,
        load_required_scenario_kinds,
    )

    load_adverse_scenario_set(d / "risk.yaml")
    return load_required_scenario_kinds(d / "risk.yaml")


def _currentness(d: Path) -> object:
    from tos_runtime.currentness.config import load_currentness_config

    return load_currentness_config(d / "currentness.yaml")


def _pending_dimensions(d: Path) -> object:
    from tos_runtime.compose._pending_dimensions import (
        load_pending_currentness_dimensions,
    )

    return load_pending_currentness_dimensions(d / "currentness_dimensions.yaml")


def _risk_attestations(d: Path) -> object:
    from tos_runtime.compose._risk_attestations import load_risk_attestations

    return load_risk_attestations(d / "risk_attestations.yaml")


def _egress_coordinates(d: Path) -> object:
    from tos_runtime.compose._egress_coordinates import load_egress_coordinates

    return load_egress_coordinates(
        d / "egress_coordinates.yaml", environment_label=_ENVIRONMENT_LABEL
    )


def _broker_scopes(d: Path) -> object:
    from tos_runtime.brokercap.scopes import load_broker_scopes

    return load_broker_scopes(
        d / "broker_scopes.yaml", environment_label=_ENVIRONMENT_LABEL
    )


def _engine(d: Path) -> object:
    from tos_runtime.compose._engine_config import load_engine_config

    return load_engine_config(d / "engine.yaml")


def _engine_driver(d: Path) -> object:
    from tos_runtime.compose._engine_wiring import load_engine_driver_config

    return load_engine_driver_config(d / "engine_driver.yaml")


def _preconditions(d: Path) -> object:
    from tos_runtime.compose._preconditions import (
        load_coordinator_preconditions_config,
    )

    return load_coordinator_preconditions_config(d / "coordinator_preconditions.yaml")


def _finality(d: Path) -> object:
    from tos_runtime.posttrade.config import load_finality_config

    return load_finality_config(d / "finality.yaml")


def _safety_mesh_documents(d: Path) -> object:
    from tos_runtime.safety.profile import SafetyProfileService

    return SafetyProfileService(
        envelope_path=d / "safety_envelope.yaml",
        profile_path=d / "safety_profile.yaml",
        activation_path=d / "safety_activation.yaml",
    )


def _deviations(d: Path) -> object:
    from tos_runtime.safety.deviation import DeviationService

    return DeviationService(deviations_path=d / "safety_deviations.yaml")


def _incidents(d: Path) -> object:
    from tos_runtime.safety.incident import IncidentService

    return IncidentService(config_path=d / "safety_incidents.yaml")


def _monitoring(d: Path) -> object:
    from tos_runtime.safety.monitoring import MonitoringService

    return MonitoringService(
        config_path=d / "monitor_coverage.yaml",
        evidence_tip_observer=lambda: _unreachable_observer(),
        time_health_observer=lambda: _unreachable_observer(),
        inbox_unconsumed_observer=lambda: _unreachable_observer(),
        monotonic_ns=lambda: _unreachable_observer(),
        evidence_recorder=lambda *_a, **_k: _unreachable_observer(),
    )


def _activation_members(d: Path) -> object:
    from tos_runtime.venue.activation import load_activation_members

    return load_activation_members(d / "safety_activation.yaml")


def _venue_policy(d: Path) -> object:
    from tos_runtime.venue import load_venue_constraint_policy

    return load_venue_constraint_policy(
        d / "venue_constraint_policy.yaml", scheme=_scheme()
    )


def _ocp(d: Path) -> object:
    from tos_runtime.venue import load_order_construction_policy

    return load_order_construction_policy(
        d / "order_construction_policy.yaml", scheme=_scheme()
    )


def _aggregate_risk(d: Path) -> object:
    from tos_runtime.riskstate.policies import load_aggregate_risk_policy

    return load_aggregate_risk_policy(
        d / "aggregate_risk_policy.yaml", scheme=_scheme()
    )


def _action_flow(d: Path) -> object:
    from tos_runtime.riskstate.policies import load_action_flow_policy

    return load_action_flow_policy(d / "action_flow_policy.yaml", scheme=_scheme())


def _construction(d: Path) -> object:
    from tos_runtime.compose._construction_config import load_construction_config

    return load_construction_config(d / "construction.yaml")


def _strategies(d: Path) -> object:
    from tos.dsl import AuthoredStrategy
    from tos.engine.admission import AdmissionResult
    from tos_runtime.strategy.loader import load_strategies

    def _never_parse(_mapping: Mapping[str, Any]) -> AuthoredStrategy:
        raise AssertionError(
            "parse must not be reached — the null-leaf check precedes it"
        )

    def _never_admit(_strategy: AuthoredStrategy) -> AdmissionResult:
        raise AssertionError("admit must not be reached")

    return load_strategies(d / "strategies", parse=_never_parse, admit=_never_admit)


@dataclass(frozen=True)
class ProbeSpec:
    """One probed loader."""

    #: Stable label — the partition test pins these, so they are part of the contract.
    label: str
    #: Called with the config DIRECTORY.
    load: Callable[[Path], object]


@dataclass(frozen=True)
class ProbeOutcome:
    """What one :class:`ProbeSpec` did against one config dir."""

    label: str
    passed: bool
    #: ``""`` when it passed; otherwise ``"<ExcType>: <message>"``.
    refusal: str


#: Every fixed config-dir name a ``run`` boot needs, in the order ``compose_paper_runtime``'s
#: own wiring reaches them (the 18 this wave adopted, the 6 adopted earlier, plus the two the
#: ``run`` CLI needs that have no adopted instance at all).
PROBES: tuple[ProbeSpec, ...] = (
    ProbeSpec("time.yaml", _time),
    ProbeSpec("authority.yaml", _authority),
    ProbeSpec("release.yaml", _release),
    ProbeSpec("calendar.yaml", _calendar),
    ProbeSpec("risk.yaml", _risk),
    ProbeSpec("currentness.yaml", _currentness),
    ProbeSpec("currentness_dimensions.yaml", _pending_dimensions),
    ProbeSpec("risk_attestations.yaml", _risk_attestations),
    ProbeSpec("egress_coordinates.yaml", _egress_coordinates),
    ProbeSpec("broker_scopes.yaml", _broker_scopes),
    ProbeSpec("engine.yaml", _engine),
    ProbeSpec("engine_driver.yaml", _engine_driver),
    ProbeSpec("coordinator_preconditions.yaml", _preconditions),
    ProbeSpec("finality.yaml", _finality),
    ProbeSpec("safety_envelope+profile+activation", _safety_mesh_documents),
    ProbeSpec("safety_deviations.yaml", _deviations),
    ProbeSpec("safety_incidents.yaml", _incidents),
    ProbeSpec("monitor_coverage.yaml", _monitoring),
    ProbeSpec("safety_activation.yaml::members", _activation_members),
    ProbeSpec("venue_constraint_policy.yaml", _venue_policy),
    ProbeSpec("order_construction_policy.yaml", _ocp),
    ProbeSpec("aggregate_risk_policy.yaml", _aggregate_risk),
    ProbeSpec("action_flow_policy.yaml", _action_flow),
    ProbeSpec("construction.yaml", _construction),
    ProbeSpec("strategies/", _strategies),
)


def run_probes(config_dir: Path) -> tuple[ProbeOutcome, ...]:
    """Run every :data:`PROBES` entry against ``config_dir``.

    A loader that raises ANYTHING is reported as a refusal with its exception type and
    message — the point is to surface whichever fail-closed check fired, never to guess which
    exception types to enumerate (the same broad-catch rationale ``_run_dispatch.dispatch_run``
    documents for itself).
    """
    outcomes: list[ProbeOutcome] = []
    for spec in PROBES:
        try:
            spec.load(config_dir)
        except Exception as exc:  # noqa: BLE001 - see docstring
            outcomes.append(
                ProbeOutcome(spec.label, False, f"{type(exc).__name__}: {exc}")
            )
        else:
            outcomes.append(ProbeOutcome(spec.label, True, ""))
    return tuple(outcomes)


def refusing_labels(outcomes: tuple[ProbeOutcome, ...]) -> frozenset[str]:
    """The labels that REFUSED — the partition test compares against this, by name."""
    return frozenset(outcome.label for outcome in outcomes if not outcome.passed)


def format_table(outcomes: tuple[ProbeOutcome, ...]) -> str:
    """A human-readable table, with each refusal's own message indented under it."""
    width = max(len(outcome.label) for outcome in outcomes)
    lines: list[str] = []
    for outcome in outcomes:
        lines.append(
            f"{outcome.label.ljust(width)}  {'PASS' if outcome.passed else 'REFUSED'}"
        )
        if outcome.refusal:
            for part in outcome.refusal.splitlines():
                lines.append(f"{' ' * width}    | {part}")
    passed = sum(1 for outcome in outcomes if outcome.passed)
    lines.append("")
    lines.append(f"PASS {passed} / {len(outcomes)}")
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover - operator/diagnostic entry point
    print(format_table(run_probes(Path(sys.argv[1]).resolve())))
