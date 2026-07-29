"""Spawn-child targets for the cycle-0 measurement (design #32 §3.4/§7.2-13).

**Why this is a separate module.** ``multiprocessing`` "spawn" pickles a target by qualified name,
so the child imports the module the target lives in. If these children lived in the test module,
that module's own ``import tos.marketfeed`` would already have populated ``sys.modules`` in the
child and the measurement would be vacuously false — it would measure the test harness rather than
the package graph.

This module therefore imports **nothing** at module scope. Each child imports exactly the one
package under measurement and reports whether ``tos.marketfeed`` came along with it.
"""

from __future__ import annotations


def dsl_only_child(queue) -> None:  # type: ignore[no-untyped-def]
    """Import ``tos.dsl`` alone; report any ``tos.marketfeed`` module that came along."""
    import sys

    import tos.dsl  # noqa: F401

    queue.put(sorted(name for name in sys.modules if name.startswith("tos.marketfeed")))


def engine_only_child(queue) -> None:  # type: ignore[no-untyped-def]
    """Import ``tos.engine`` alone; report any ``tos.marketfeed`` module that came along."""
    import sys

    import tos.engine  # noqa: F401

    queue.put(sorted(name for name in sys.modules if name.startswith("tos.marketfeed")))


def capsule_only_child(queue) -> None:  # type: ignore[no-untyped-def]
    """Import ``tos.capsule`` alone; report any ``tos.marketfeed`` module that came along."""
    import sys

    import tos.capsule  # noqa: F401

    queue.put(sorted(name for name in sys.modules if name.startswith("tos.marketfeed")))
