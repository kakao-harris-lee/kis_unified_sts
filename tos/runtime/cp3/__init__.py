"""CP-3 B1b — the ``tos``-side runner that drives B1a's field JSONL through the kernel.

`docs/plans/2026-10-07-tos-cp3-first-tenant-kickoff.md` §3 구축물 B1b, §5 2/3.

**Why this directory and not another.** Two constraints bracket the placement and
only one directory satisfies both:

1. **Zero bytes under the two installed package roots.** The resident paper
   release pin ``config/tos_runtime/paper/release.yaml::expected_code_digest``
   is a sha256 fold over every ``*.py`` under ``tos/src/tos/`` **and**
   ``tos/runtime/src/tos_runtime/``
   (``tos_runtime.operations.dependency_admission.observe_source_tree_digest``
   + ``default_package_roots``), re-derived from ``origin/main`` every morning;
   a single new file under either root ABORTS the resident session. So B1b adds
   nothing there.
2. **May import ``tos_runtime``.** The import firewall's scope predicate
   (``tools/tos_firewall_check.py::scope_for_tos_path``) classifies a path as
   RUNTIME scope **only** when its first two components are ``tos`` then
   ``runtime``; everything else under ``tos/`` is KERNEL scope, and a
   kernel-scope file importing ``tos_runtime`` is rule **TOS-FW-G**
   (``kernel-scope file imports 'tos_runtime' — forbidden``, measured: a probe
   file at ``tos/cp3/_probe.py`` importing the strategy loader fails the gate).
   B1b must reach ``tos_runtime.strategy.loader`` / ``.bindings`` / ``.resolve``
   so the strategy file is admitted by the **production** loader rather than a
   second implementation of it.

``tos/runtime/cp3/`` is RUNTIME scope (so (2) holds) and is **outside**
``tos/runtime/src/tos_runtime/`` (so (1) holds). It is also where the kickoff's
own §3 B1b row puts it ("**`tos/runtime/` 안**"). It is not part of either
distribution's wheel — ``tos/runtime/pyproject.toml`` packages
``["src/tos_runtime"]`` only — so nothing installs or ships from here.

**CLI** (the ``tos.cp3.runner`` module path the task text names is unreachable
without adding files under ``tos/src/tos/``, which constraint (1) forbids)::

    PYTHONPATH=tos/src:tos/runtime/src:tos/runtime \\
      .venv/bin/python -m cp3.runner \\
        --fields <fields.jsonl> \\
        --strategy <strategy.yaml> \\
        --bindings <strategy_bindings.yaml> \\
        --out <dir>

Firewall: ``tos.*`` (kernel) + ``tos_runtime.*`` + stdlib + ``pyyaml`` only. No
``shared.*`` anywhere — the comparison's legacy side is a separate process that
meets this one through files (kickoff §3; design #33 §6.1 alternative B).
"""

from __future__ import annotations

__all__ = ["__version__"]

#: The B1b runner's own version token, stamped into every lineage block.
__version__ = "tos_cp3_b1b/0.1.0"
