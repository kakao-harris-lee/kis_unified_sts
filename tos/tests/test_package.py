"""Hermetic smoke test for the tos package skeleton (§2.4)."""

from __future__ import annotations

import tos


def test_version_is_nonempty_string():
    assert isinstance(tos.__version__, str)
    assert tos.__version__


def test_package_identity():
    assert tos.__name__ == "tos"
