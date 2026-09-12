"""``tos/runtime/tests/brokercap`` — shared fixtures.

Reuses the compose end-to-end suite's own config/custody/data fixtures
(:mod:`tos.runtime.tests.compose`) rather than re-typing them — the same reuse
:mod:`tos.runtime.tests.recovery`'s own ``conftest.py`` already established for a different
consumer suite.

These names are re-exported here, in a ``conftest.py``, specifically so that
``test_exit_conditions.py`` (and any future module in this package) never has to import them
into its OWN module namespace: a test file that both imports a fixture by name and requests it as
a same-named test-function parameter trips ruff's ``F811`` (pyflakes reads the parameter as
"redefining" the import — it does not know pytest resolves fixtures by name, not by import
visibility). Fixtures a ``conftest.py`` re-exports are available to every test in this package
automatically, with no import needed in the test module at all, so the collision never arises
here (kernel round #3 K-6).
"""

from __future__ import annotations

from ..compose.conftest import config_dir, custody_root, data_dir  # noqa: F401
