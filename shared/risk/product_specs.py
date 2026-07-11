"""Shared futures product-spec builder (P5-3 F3 — moved out of a service).

``build_product_specs`` merges the contract constants from
``config/execution.yaml::futures_contract_spec`` (multiplier + tick — the single
source of contract constants) with the per-product margin rates + stress gap
from ``config/futures_margin.yaml`` into a
``{product_key -> MarginProductSpec}`` map.

It used to live in ``services/futures_margin_risk/main.py`` and was reached into
by ``services/risk_filter`` (the decoupled futures risk-filter leverage wiring)
through a service→service import of that module's ``main`` — a reverse-layering
smell, with the ``execution.yaml`` load block duplicated at both call sites. It
now lives here in ``shared/`` so BOTH consumers import identical logic from the
shared seam and no service depends on another service's ``main``:

* ``services/futures_margin_risk`` (the margin read-model publisher);
* ``services/risk_filter`` (the LeverageFilter product-spec map, P5-3).

Layering: this module imports only ``shared.*`` — never ``services.*`` — so it
introduces no import cycle. The config argument is typed structurally
(:class:`MarginConfigLike`) precisely so ``shared`` need not import the
service-side ``FuturesMarginConfig`` model.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from shared.risk.futures_margin import MarginProductSpec

logger = logging.getLogger(__name__)


class ProductDefaultLike(Protocol):
    """Structural type for one product's margin defaults (duck-typed).

    Matches ``services.futures_margin_risk.config.MarginProductDefault`` without
    importing it, keeping ``shared`` free of any ``services`` dependency. Members
    are read-only ``@property`` so matching is covariant — a concrete class with
    a mutable ``list[str] symbol_prefixes`` attribute still satisfies the
    ``Sequence[str]`` member (a mutable protocol attribute would be invariant and
    reject it).
    """

    @property
    def initial_margin_rate(self) -> float: ...
    @property
    def maintenance_margin_rate(self) -> float: ...
    @property
    def stress_gap_points(self) -> float: ...
    @property
    def symbol_prefixes(self) -> Sequence[str]: ...


class MarginConfigLike(Protocol):
    """Structural type for the margin config's ``product_defaults`` map."""

    @property
    def product_defaults(self) -> Mapping[str, ProductDefaultLike]: ...


def build_product_specs(
    config: MarginConfigLike, execution_specs: Mapping[str, Any]
) -> dict[str, MarginProductSpec]:
    """Merge execution-spec constants with margin-config rates per product.

    ``execution_specs`` is ``config/execution.yaml::futures_contract_spec``.
    A product configured in the margin YAML but absent from the execution spec
    is skipped (logged) — its symbol simply won't resolve a spec at compute.
    """
    specs: dict[str, MarginProductSpec] = {}
    for key, defaults in config.product_defaults.items():
        exec_spec = execution_specs.get(key)
        if not isinstance(exec_spec, Mapping):
            logger.warning(
                "futures_contract_spec.%s missing — margin product %s skipped",
                key,
                key,
            )
            continue
        multiplier = exec_spec.get("multiplier_krw_per_point")
        tick = exec_spec.get("tick_size_points")
        if multiplier is None or tick is None:
            logger.warning("futures_contract_spec.%s missing multiplier/tick", key)
            continue
        specs[key] = MarginProductSpec(
            multiplier_krw_per_point=float(multiplier),
            tick_size_points=float(tick),
            initial_margin_rate=defaults.initial_margin_rate,
            maintenance_margin_rate=defaults.maintenance_margin_rate,
            stress_gap_points=defaults.stress_gap_points,
            symbol_prefixes=tuple(defaults.symbol_prefixes),
        )
    return specs


def load_execution_contract_specs() -> Mapping[str, Any]:
    """Load ``config/execution.yaml::futures_contract_spec`` (``{}`` if absent).

    Deduplicates the identical load block previously copied into both
    ``services/futures_margin_risk`` and ``services/risk_filter``.
    """
    from shared.config.loader import ConfigLoader

    execution_yaml = ConfigLoader.load("execution.yaml")
    if not isinstance(execution_yaml, dict):
        return {}
    specs = execution_yaml.get("futures_contract_spec", {})
    return specs if isinstance(specs, Mapping) else {}
