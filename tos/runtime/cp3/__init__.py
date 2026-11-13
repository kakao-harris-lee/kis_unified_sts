"""CP-3 ``sts tos inspect`` — the ``tos``-side per-bar session reader.

`docs/plans/2026-11-11-tos-platform-roadmap.md` §7 결정 3.

**What this package was and what is left.** It was B1b, the runner that drove
B1a's field JSONL through the kernel so the post-session B3 comparison had a
``tos``-side trace to diff against the legacy Setup D witness
(`docs/plans/2026-10-07-tos-cp3-first-tenant-kickoff.md` §3 구축물 B1b). That
comparison retired on 2026-11-13 — P2-b measured the declarative producer
equivalent to the legacy one (626,745 cells, 0 mismatches: #1065 / #1066),
which is the condition 결정 3 set — so the runner, the replay, the seam, the
bar builder, the field contract, the declared-difference register, the lineage
builder and both committed harness strategy copies were deleted. They are in
git history.

What remains is the **operator-facing** half, which never belonged to the
comparison: :mod:`cp3.inspect_session` (per bar: fields, per-compare pass/fail,
decision, halt), its evidence projection :mod:`cp3.inspect_evidence`, its two
renderings :mod:`cp3.inspect_report`, and the production strategy loading
:mod:`cp3.strategy` that all three need. ``sts tos inspect`` runs it as a
separate process through ``tools/tos_cp3/inspect_session.py``.

**Why this directory and not another.** Two constraints bracket the placement
and only one directory satisfies both:

1. **Zero bytes under the two installed package roots.** The resident paper
   release pin ``config/tos_runtime/paper/release.yaml::expected_code_digest``
   is a sha256 fold over every ``*.py`` under ``tos/src/tos/`` **and**
   ``tos/runtime/src/tos_runtime/``
   (``tos_runtime.operations.dependency_admission.observe_source_tree_digest``
   + ``default_package_roots``), re-derived from ``origin/main`` every morning;
   a single new file under either root ABORTS the resident session. So this
   package adds nothing there.
2. **May import ``tos_runtime``.** The import firewall's scope predicate
   (``tools/tos_firewall_check.py::scope_for_tos_path``) classifies a path as
   RUNTIME scope **only** when its first two components are ``tos`` then
   ``runtime``; everything else under ``tos/`` is KERNEL scope, and a
   kernel-scope file importing ``tos_runtime`` is rule **TOS-FW-G**
   (``kernel-scope file imports 'tos_runtime' — forbidden``, measured: a probe
   file at ``tos/cp3/_probe.py`` importing the strategy loader fails the gate).
   :mod:`cp3.strategy` must reach ``tos_runtime.strategy.loader`` /
   ``.bindings`` / ``.resolve`` so the strategy file is admitted by the
   **production** loader rather than a second implementation of it.

``tos/runtime/cp3/`` is RUNTIME scope (so (2) holds) and is **outside**
``tos/runtime/src/tos_runtime/`` (so (1) holds). It is not part of either
distribution's wheel — ``tos/runtime/pyproject.toml`` packages
``["src/tos_runtime"]`` only — so nothing installs or ships from here.

**CLI**::

    PYTHONPATH=tos/src:tos/runtime/src:tos/runtime \\
      .venv/bin/python -m cp3.inspect_session \\
        --session-dir <session> \\
        --strategy <strategy.yaml> \\
        --bindings <strategy_bindings.yaml>

Firewall: ``tos.*`` (kernel) + ``tos_runtime.*`` + stdlib + ``pyyaml`` only. No
``shared.*`` anywhere — the legacy side is a separate process that meets this
one through files (kickoff §3; design #33 §6.1 alternative B).
"""

from __future__ import annotations
