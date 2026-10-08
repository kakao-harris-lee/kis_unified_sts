"""Pure tick/field arithmetic shared by probe modules. STDLIB ONLY.

This module exists so a GET-only probe can reuse these two functions without
importing an order-capable module. There are TWO of those: ``probes_order.py``
POSTs 모의 orders for the seven ``emits_orders=True`` specs, and
``probes_real_order.py`` is the only module in the harness that can place a
**REAL-money** order. The second imports the first at module level, so a single
import of either one puts both order paths into the importer's graph — which is
exactly what the committed canaries
``tests/tools/test_broker_probes_real_order.py::test_get_only_real_module_does_not_import_the_real_order_module``
and ``tests/tools/test_broker_probes_ca.py::test_module_does_not_import_order_capable_modules``
forbid. Both functions were pure already; only their address changed.

The dependency rule for this file is therefore absolute: **standard library
only.** No ``tools.broker_probes`` sibling, no ``shared``, no third party. A
single import here would be inherited by every GET-only module that reuses it
and would silently reopen the hole the relocation closed.

``tick`` is typed as :class:`TickLike` rather than ``probes_order.Tick``, since
naming that class would mean importing it. The Protocol is structural, so the
existing ``Tick`` dataclass satisfies it with no change at either call site.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Protocol


class TickLike(Protocol):
    """Anything carrying an exact price increment.

    Satisfied structurally by ``probes_order.Tick``, whose ``size`` is the
    minimum price increment as an exact :class:`~decimal.Decimal`.

    Deliberately NOT ``@runtime_checkable``: a Protocol with only data members
    cannot be used with ``isinstance`` (it raises ``TypeError``), so the
    decorator would advertise a check nobody can perform. Static structural
    typing is the whole contract here.
    """

    size: Decimal


def decimal_field(container: Any, key: str) -> Decimal | None:
    """A numeric broker field as an exact Decimal, or ``None`` if unestablished.

    ``None`` means "the broker did not give us this number", which is a different
    fact from ``0``. Every caller here treats ``None`` as fail-closed: an
    unreadable order-available amount aborts exactly like a zero one, and an
    unreadable fill quantity aborts rather than reading as "did not fill".
    """
    if not isinstance(container, dict):
        return None
    raw = container.get(key)
    if raw is None:
        return None
    text = str(raw).strip().replace(",", "")
    if not text:
        return None
    try:
        value = Decimal(text)
    except ArithmeticError:
        return None
    # ``Decimal("NaN")`` and ``Decimal("Infinity")`` PARSE. They are not numbers
    # a venue quotes, and letting one through turns the next ``value % tick``
    # into an ``InvalidOperation`` traceback far from this field. "The broker did
    # not give us this number" is exactly the documented contract for them.
    if not value.is_finite():
        return None
    return value


def corroborate_tick(
    quote_output: dict[str, Any], tick: TickLike, fields: tuple[str, ...]
) -> dict[str, Any]:
    """Check the broker's own quoted prices are multiples of the configured tick.

    The honest substitute for a broker-reported 호가단위 on an asset class that
    does not report one. If the venue quotes a price that is not a multiple of
    the tick this repo has registered, the registered tick is CONTRADICTED and
    the caller must not snap to it.
    """
    observed: dict[str, Any] = {}
    offenders: list[str] = []
    for name in fields:
        value = decimal_field(quote_output, name)
        observed[name] = str(value) if value is not None else None
        if value is not None and value > 0 and value % tick.size != 0:
            offenders.append(f"{name}={value}")
    return {
        "tick_size_points": str(tick.size),
        "broker_quoted_values": observed,
        "non_multiples": offenders,
        "corroborated": not offenders,
        "meaning": (
            "Every positive broker-quoted price above is expected to be an exact "
            "multiple of the registered tick. A non-multiple contradicts the "
            "registry and the resting price must not be snapped to it."
        ),
    }
