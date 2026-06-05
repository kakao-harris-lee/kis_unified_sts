#!/usr/bin/env python3
"""Reports archival / rotation.

Compresses and prunes the per-day / per-week JSON reports that accumulate
under ``reports/``:

  - ``reports/daily_verification/YYYY-MM-DD.json``  (Phase 2 daily check)
  - ``reports/counterfactual/YYYY-WNN.json``        (Phase 4 counterfactual)
  - ``reports/drills/*``                            (operator-run rollback drills)

Per-directory policy:

| dir                  | gzip after | delete after  | rationale                       |
| -------------------- | ---------- | ------------- | ------------------------------- |
| daily_verification   |   30 days  |     730 days  | high volume (252/yr), 2-yr keep |
| counterfactual       |  365 days  |    1825 days  | low volume (52/yr), 5-yr keep   |
| drills               |   90 days  | (keep forever)| infrequent, audit-relevant      |

5-year retention for counterfactual keeps enough history for long-window
strategy review.

Idempotent.  Safe defaults — dry-run unless ``--apply`` is passed.

Usage::

    # dry-run (recommended first):
    python -m scripts.maintenance.rotate_reports

    # apply (operator/cron):
    python -m scripts.maintenance.rotate_reports --apply

    # custom retention:
    python -m scripts.maintenance.rotate_reports \\
        --apply \\
        --daily-verification-gzip-days 60 \\
        --counterfactual-delete-days 3650
"""

from __future__ import annotations

import argparse
import gzip
import logging
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPORTS_ROOT = _REPO_ROOT / "reports"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RotationPolicy:
    """How to age a single report directory."""

    name: str
    directory: Path
    gzip_after_days: int
    delete_after_days: int | None  # None = keep forever
    file_pattern: str = "*.json"


@dataclass
class RotationStats:
    """Tally of work performed (or planned, in dry-run)."""

    gzipped: int = 0
    deleted: int = 0
    bytes_freed: int = 0
    skipped_existing_gz: int = 0
    errors: int = 0


def _file_age_days(path: Path, now: float) -> float:
    return (now - path.stat().st_mtime) / 86_400.0


def _gzip_in_place(path: Path) -> int:
    """Compress ``path`` to ``path.with_suffix('.json.gz')`` and unlink original.

    Returns:
        Bytes freed (original size minus gzipped size).
    """
    original_size = path.stat().st_size
    target = path.with_suffix(path.suffix + ".gz")
    if target.exists():
        # Already gzipped on a previous run — keep the original out of the way.
        path.unlink()
        return 0
    with path.open("rb") as src, gzip.open(target, "wb", compresslevel=6) as dst:
        shutil.copyfileobj(src, dst)
    compressed_size = target.stat().st_size
    path.unlink()
    return max(0, original_size - compressed_size)


def _apply_policy(
    policy: RotationPolicy,
    *,
    apply: bool,
    now: float,
) -> RotationStats:
    """Apply gzip + delete to one report directory.

    Args:
        policy: Per-dir retention policy.
        apply: If False, log intent but don't modify files.
        now: Reference time (epoch seconds) — overridable for tests.

    Returns:
        Stats covering files affected (real or dry-run).
    """
    stats = RotationStats()
    if not policy.directory.exists():
        logger.info(
            "[%s] directory does not exist (%s) — skipping",
            policy.name,
            policy.directory,
        )
        return stats

    # Files matching the pattern but already gzipped are deletion
    # candidates only.  When pattern is "*" (drills), exclude *.gz from
    # the gzip-candidate list so we don't try to gzip already-gzipped
    # files (would create .gz.gz and clobber the audit trail).
    all_matched = sorted(policy.directory.glob(policy.file_pattern))
    json_files = [f for f in all_matched if f.suffix != ".gz"]
    gz_files = sorted(policy.directory.glob(policy.file_pattern + ".gz"))

    # Step 1: gzip old uncompressed files
    for f in json_files:
        age = _file_age_days(f, now)
        if age >= policy.gzip_after_days:
            try:
                if apply:
                    bytes_freed = _gzip_in_place(f)
                    stats.bytes_freed += bytes_freed
                    logger.info(
                        "[%s] gzipped %s (age=%.1fd, freed=%d B)",
                        policy.name,
                        f.name,
                        age,
                        bytes_freed,
                    )
                else:
                    logger.info(
                        "[%s] DRY-RUN would gzip %s (age=%.1fd)",
                        policy.name,
                        f.name,
                        age,
                    )
                stats.gzipped += 1
            except OSError as e:
                logger.warning("[%s] gzip failed for %s: %s", policy.name, f.name, e)
                stats.errors += 1

    # Step 2: delete already-gzipped files past retention
    if policy.delete_after_days is not None:
        for f in gz_files:
            age = _file_age_days(f, now)
            if age >= policy.delete_after_days:
                try:
                    if apply:
                        f.unlink()
                        logger.info(
                            "[%s] deleted %s (age=%.1fd)",
                            policy.name,
                            f.name,
                            age,
                        )
                    else:
                        logger.info(
                            "[%s] DRY-RUN would delete %s (age=%.1fd)",
                            policy.name,
                            f.name,
                            age,
                        )
                    stats.deleted += 1
                except OSError as e:
                    logger.warning(
                        "[%s] delete failed for %s: %s", policy.name, f.name, e
                    )
                    stats.errors += 1

    return stats


def _build_policies(args: argparse.Namespace) -> list[RotationPolicy]:
    return [
        RotationPolicy(
            name="daily_verification",
            directory=_REPORTS_ROOT / "daily_verification",
            gzip_after_days=args.daily_verification_gzip_days,
            delete_after_days=args.daily_verification_delete_days,
        ),
        RotationPolicy(
            name="counterfactual",
            directory=_REPORTS_ROOT / "counterfactual",
            gzip_after_days=args.counterfactual_gzip_days,
            delete_after_days=args.counterfactual_delete_days,
        ),
        RotationPolicy(
            name="drills",
            directory=_REPORTS_ROOT / "drills",
            gzip_after_days=args.drills_gzip_days,
            delete_after_days=None,  # never delete — audit-relevant
            file_pattern="*",
        ),
    ]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compress and prune accumulated reports under reports/. "
            "Dry-run by default; pass --apply to mutate the filesystem."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually rotate (default: dry-run).",
    )
    parser.add_argument(
        "--daily-verification-gzip-days",
        type=int,
        default=30,
        help="Gzip daily-verification reports older than N days (default: 30).",
    )
    parser.add_argument(
        "--daily-verification-delete-days",
        type=int,
        default=730,
        help="Delete already-gzipped daily-verification reports older than N days (default: 730 = 2y).",
    )
    parser.add_argument(
        "--counterfactual-gzip-days",
        type=int,
        default=365,
        help="Gzip counterfactual reports older than N days (default: 365 = 1y).",
    )
    parser.add_argument(
        "--counterfactual-delete-days",
        type=int,
        default=1825,
        help="Delete already-gzipped counterfactual reports older than N days (default: 1825 = 5y, matches rl_trades TTL).",
    )
    parser.add_argument(
        "--drills-gzip-days",
        type=int,
        default=90,
        help="Gzip drill outputs older than N days (default: 90; never deleted).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if not args.apply:
        logger.info("DRY-RUN mode (pass --apply to actually rotate)")

    policies = _build_policies(args)
    now = time.time()

    grand_total = RotationStats()
    for policy in policies:
        stats = _apply_policy(policy, apply=args.apply, now=now)
        grand_total.gzipped += stats.gzipped
        grand_total.deleted += stats.deleted
        grand_total.bytes_freed += stats.bytes_freed
        grand_total.errors += stats.errors

    verb = "would" if not args.apply else ""
    logger.info(
        "Summary: gzipped=%d %s deleted=%d %s bytes_freed=%d errors=%d",
        grand_total.gzipped,
        verb,
        grand_total.deleted,
        verb,
        grand_total.bytes_freed,
        grand_total.errors,
    )
    return 1 if grand_total.errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
