"""Live-mode guard for the order_router daemon — Phase 5 Task 5.

Two-layer suspend:
  1. Config-level: ``futures_live.enabled`` (default ``false``). Until the
     Gate-2 checklist is complete and the operator flips this to ``true``,
     every live order is rejected.
  2. Runtime flag in Redis at ``suspend_key`` (default
     ``futures:live:suspended``). Set/cleared without a process restart.

Spec reference: ``docs/plans/2026-04-20-futures-paradigm-phase5-implementation-plan.md``
Task 5; ``docs/plans/2026-04-20-futures-paradigm-phase5-rollout.md`` §2.3
(Gate 3 ladder).

Caller: ``services/order_router/main.py`` consults
:meth:`LiveModeGuard.is_live_suspended` BEFORE each
``passive_maker.place_passive_limit_futures`` call.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import Field

from shared.config.base import ServiceConfigBase


class LiveModeGuard(ServiceConfigBase):
    """Live-mode YAML config + runtime suspend helper.

    Loaded from ``config/futures_live.yaml`` under the ``futures_live``
    section. Combines the static (YAML) and dynamic (Redis flag) suspend
    triggers into a single :meth:`is_live_suspended` query the
    order_router calls per signal.
    """

    _default_config_file: ClassVar[str] = "futures_live.yaml"
    _default_section: ClassVar[str] = "futures_live"

    enabled: bool = Field(default=False)
    max_position_size_contracts: int = Field(default=1, gt=0)
    max_daily_trades: int = Field(default=2, gt=0)
    symbol_lock_enabled: bool = Field(default=True)
    account_suffix: str = Field(default="_live")
    suspend_key: str = Field(default="futures:live:suspended")

    async def is_live_suspended(self, redis: Any) -> bool:
        """Return True if live orders should be refused right now.

        Suspended when ANY of:
        - ``enabled`` is False (Gate 2 not yet completed)
        - ``redis.get(suspend_key)`` returns a truthy value

        Redis I/O failures are treated as "suspended" — fail-closed (we'd
        rather skip an order than place one with unknown guard state).
        """
        if not self.enabled:
            return True
        try:
            value = await redis.get(self.suspend_key)
        except Exception:
            # Fail-closed: any Redis read error suspends the live path.
            return True
        if value is None:
            return False
        if isinstance(value, bytes):
            value = value.decode(errors="replace")
        return str(value).strip().lower() not in ("", "0", "false", "no", "off")
