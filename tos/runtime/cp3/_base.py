"""Shared primitives — the canonicalization scheme, the lineage schema version, the typed refusal.

Part of the CP-3 B1b runner (``cp3`` package). The runner was one module until the
2026-10-08 review: at 1,820 lines it broke ``config/tos_size_budget.yaml``'s
1,000-line module cap and its 100-line function cap three times over, and
registering four day-one exceptions against a budget whose own header calls
registration "가시성, 면허가 아니라" would have been the wrong answer for NEW code.
So the module was decomposed along the seams it already had, and
``tos/runtime/cp3`` was added to that budget's ``scope`` so the caps are actually
enforced here (the review's fourth gate).

Firewall: ``tos.*`` + ``tos_runtime.*`` + stdlib + ``pyyaml`` only. No
``shared.*``, no clock, no RNG, no ``subprocess``, no network. Intra-package
imports are RELATIVE — the allowlist does not name ``cp3``, so an absolute
``import cp3.…`` from a file under ``tos/`` is a TOS-FW-A violation while a
relative import carries no absolute name for the gate to classify.
"""

from __future__ import annotations

from tos.canonical import EV_L1_PROVISIONAL_VERSION, ArtifactIntegrityError, get_scheme

__all__ = ["LINEAGE_SCHEMA_VERSION", "SCHEME", "Cp3RunnerRefusal"]

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: ADR-002-018 §10 lineage block schema version — the SAME version B1a's
#: ``lineage.json`` carries, because this is the same block shape with a
#: different tool and different parents (B1a ``produce_fields.py``).
LINEAGE_SCHEMA_VERSION = 2


class Cp3RunnerRefusal(ArtifactIntegrityError):
    """A typed refusal — every one exits the CLI with status 2.

    Subclasses :class:`~tos.canonical.ArtifactIntegrityError` (itself a
    ``ValueError``) so a refusal raised here and a refusal raised inside the
    kernel's own validators are the same kind of failure to a caller, as every
    other fail-closed loader in this tree does
    (``tos_runtime.strategy.loader.StrategyLoadError`` precedent).
    """
