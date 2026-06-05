#!/usr/bin/env python3
"""Coverage audit placeholder for forecast artifacts.

Forecast coverage must be rebuilt on top of Redis snapshots, RuntimeLedger, or
Parquet artifacts. The old external DB audit path has been removed.
"""

from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--min-coverage", type=float, default=0.95)
    parser.parse_args()
    raise SystemExit(
        "Forecast coverage audit needs a Parquet/RuntimeLedger implementation"
    )


if __name__ == "__main__":
    main()
