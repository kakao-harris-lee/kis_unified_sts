"""``tos_runtime.operations`` — operational-continuity surfaces (TOS Phase 5 W4, plan §2
decisions 1-3).

Three concerns, each its own module:

* :mod:`tos_runtime.operations.schema_ledger` — the generic, per-store append-only
  ``schema_ledger`` table + the "boot refuses on a behind/ahead ``user_version``" check every
  durable store's constructor consults.
* :mod:`tos_runtime.operations.schema_migrations` — the per-store baseline ``SchemaMigration``
  definitions and the CLI-facing :func:`~tos_runtime.operations.schema_migrations.apply_migrations`
  that brings a pre-existing, not-yet-ledgered file up to the current baseline.
* :mod:`tos_runtime.operations.backup_set` — the durable-set (evidence + RCL + inbox +
  composite-state) backup/restore/restore-drill machinery.
* :mod:`tos_runtime.operations.key_rotation` — the evidence-signing key-generation continuity
  gate (consulted by :class:`tos_runtime.evidence.store.SqliteEvidenceStore`'s own constructor)
  and the explicit, operator-invoked ``rotate_evidence_key`` workflow (TOS Phase 5 W4 plan §2
  decision 4). Imports nothing from ``tos_runtime`` at all — every cross-package argument is a
  structural :class:`~typing.Protocol`; see that module's own docstring for the real circular
  import this avoids (``evidence.store`` is itself on this package's import path).

Deliberately does not import :mod:`tos_runtime.compose` (that package will import THIS one,
``compose/_operations_wiring.py`` — the reverse edge would be a cycle) or any kernel
``tos.staterestore`` type (the composite-state store is kernel-owned; this package only ever
touches its file by path, never its class — see :mod:`tos_runtime.operations.backup_set`'s own
module docstring).

Firewall: stdlib + ``pydantic`` + ``tos.*`` + ``tos_runtime.evidence``/``tos_runtime.engine`` only
(R1 allowlist) — no ``shared.*``, no ``tos_runtime.compose``, no ``tos_runtime.custody``.
"""

from __future__ import annotations

__all__: list[str] = []
