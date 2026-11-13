"""Shared primitives — the canonicalization scheme, the lineage schema version, the typed refusal."""

from __future__ import annotations

from tos.canonical import EV_L1_PROVISIONAL_VERSION, ArtifactIntegrityError, get_scheme

__all__ = ["LINEAGE_SCHEMA_VERSION", "SCHEME", "Cp3RunnerRefusal"]

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

LINEAGE_SCHEMA_VERSION = 2


class Cp3RunnerRefusal(ArtifactIntegrityError):
    """A typed refusal — every one exits the CLI with status 2."""
