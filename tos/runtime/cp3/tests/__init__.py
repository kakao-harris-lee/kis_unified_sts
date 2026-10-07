"""CP-3 B1b test package.

``__init__.py`` is present so these modules import as ``cp3.tests.*`` and can
reach the package under test with a **relative** import. That is not a style
choice: the import firewall's allowlist does not name ``cp3``, so
``import cp3.runner`` from a file under ``tos/`` is a TOS-FW-A violation, while
a relative import is skipped by the gate (``tools/tos_firewall_check.py``
``node.level > 0``). The firewall scans ``tos/`` tests as well as sources
(design §2.4), so the rule applies here identically.

Hermetic: no network, no ambient env, no writes outside ``tmp_path`` — the
``tos/runtime/tests`` D1.4 definition, honoured here by construction (this
suite's only writes go to ``tmp_path``; it opens no socket and reads no env).
Collected with its own rootdir::

    PYTHONPATH=tos/src:tos/runtime/src \\
      .venv/bin/python -m pytest tos/runtime/cp3/tests -q
"""

from __future__ import annotations
