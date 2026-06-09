"""Accumulation-pattern scan one-shot for the compose scheduler.

Replaces the host wrapper ``scripts/cron/accumulation_scan.sh`` (which ran the
scan via an inline ``python -c``). Runs :class:`AccumulationScanner`, which
publishes its candidates to Redis; ``min_score`` comes from the
``ACCUMULATION_MIN_SCORE`` env var (default 60, matching the host cron).
"""

from __future__ import annotations

import asyncio
import logging
import os

from shared.scanner.accumulation import AccumulationScanner

logger = logging.getLogger("run_accumulation_scan")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    min_score = int(os.environ.get("ACCUMULATION_MIN_SCORE", "60"))
    scanner = AccumulationScanner(min_score=min_score)
    candidates = asyncio.run(scanner.run())
    logger.info(
        "accumulation scan: %d candidates (min_score=%d)", len(candidates), min_score
    )


if __name__ == "__main__":
    main()
