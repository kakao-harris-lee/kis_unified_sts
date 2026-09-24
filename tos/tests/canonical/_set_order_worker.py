"""Print every canonical set-ordering digest as JSON, for one process.

Driven by ``tests/tools/test_tos_canonical_set_order.py``, which runs this
module once per ``PYTHONHASHSEED`` value and compares the outputs. It lives
inside ``tos/`` because only files under ``tos/`` may ``import tos``
(``tools/tos_firewall_check.py`` rule (e)/TOS-FW-R), and it lives under
``tos/tests`` rather than ``tos/src`` because it is test scaffolding and must
not enter ``expected_code_digest``'s source-tree fold.

Run as a module from ``tos/`` so the package-relative import resolves::

    PYTHONPATH=tos/src PYTHONHASHSEED=7 python -m tests.canonical._set_order_worker
"""

from __future__ import annotations

import json
import sys

from ._set_order_builders import digest_map


def main() -> int:
    """Print the digest map as one JSON object on stdout.

    Returns:
        Process exit status (always 0; an exception is the failure channel).
    """
    json.dump(digest_map(), sys.stdout, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
