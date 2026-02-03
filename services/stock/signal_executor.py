"""Deprecated: use `services.stock.signal_orchestrator` instead."""

from __future__ import annotations

import logging

from services.stock.signal_orchestrator import main

logger = logging.getLogger(__name__)


def _warn() -> None:
    logger.warning(
        "services.stock.signal_executor is deprecated; "
        "use services.stock.signal_orchestrator instead."
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    _warn()
    main()

