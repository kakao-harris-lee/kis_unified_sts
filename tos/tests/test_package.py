"""Hermetic smoke test for the tos package skeleton (§2.4).

Hermetic by construction: no .env, no filesystem I/O beyond import, no network,
no external services. Its only import is the package under test (`import tos`),
which the firewall permits as a self-import.
"""

from __future__ import annotations

import tos


def test_version_is_nonempty_string():
    assert isinstance(tos.__version__, str)
    assert tos.__version__


def test_package_identity():
    assert tos.__name__ == "tos"
