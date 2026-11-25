"""Spawn-child targets for the cycle-0 measurement (design #32 §3.4/§7.2-13)."""

from __future__ import annotations


def dsl_only_child(queue) -> None:
    """Import ``tos.dsl`` alone; report any ``tos.marketfeed`` module that came along."""
    import sys

    import tos.dsl  # noqa: F401

    queue.put(sorted(name for name in sys.modules if name.startswith("tos.marketfeed")))


def engine_only_child(queue) -> None:
    """Import ``tos.engine`` alone; report any ``tos.marketfeed`` module that came along."""
    import sys

    import tos.engine  # noqa: F401

    queue.put(sorted(name for name in sys.modules if name.startswith("tos.marketfeed")))


def capsule_only_child(queue) -> None:
    """Import ``tos.capsule`` alone; report any ``tos.marketfeed`` module that came along."""
    import sys

    import tos.capsule  # noqa: F401

    queue.put(sorted(name for name in sys.modules if name.startswith("tos.marketfeed")))
