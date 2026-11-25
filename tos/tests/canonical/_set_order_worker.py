"""Print every canonical set-ordering digest as JSON, for one process."""

from __future__ import annotations

import json
import sys

from ._set_order_builders import digest_map


def main() -> int:
    """Print the digest map as one JSON object on stdout."""
    json.dump(digest_map(), sys.stdout, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
