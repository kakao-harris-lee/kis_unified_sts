"""``tos_runtime.custody`` — file-backed credential custody + key provider
(design #40 D4, slice plan §2 "레인 N").

Realizes design #40 D4.1 ("워크로드 정체성 · 키 회전 · 자격증명 보관") for
Phase 2's scope: ``FileCustody`` loads scoped credential files (``0600``,
owner-checked, environment-label-checked, evidence-recorded — never the raw
secret) and ``FileKeyProvider`` supplies
:class:`tos_runtime.evidence.store.SqliteEvidenceStore`'s initial signing key
from generation-numbered files. **Phase 2 provisions exactly three scopes**
(``read.principal``, ``evidence.key``, ``replay.params``) — ``order.*`` is
never provisioned here: stock order-scope custody is Phase 4, and futures
REAL is permanently absent (root ``CLAUDE.md`` non-negotiable rule).

No real broker transport, no ``order`` credential load path, and no evidence
row's state changes anywhere in this package — consistent with design #40's
own §0 "하지 않는 것" scope boundary and the slice plan's "권한 부여 없음"
line.

Public surface groups by module:

* :mod:`tos_runtime.custody.ports` — the seams (``CredentialCustody``,
  ``KeyProvider`` Protocols; ``CredentialHandle``; the ``CustodyError``
  exception hierarchy).
* :mod:`tos_runtime.custody.file_custody` — ``FileCustody``,
  ``CustodyManifest``, the shared ``verify_file_mode_and_owner`` gate.
* :mod:`tos_runtime.custody.key_provider` — ``FileKeyProvider``.
"""

from __future__ import annotations

from tos_runtime.custody.file_custody import (
    MANIFEST_FILENAME,
    PROVISIONED_SCOPES,
    CustodyManifest,
    FileCustody,
    verify_file_mode_and_owner,
)
from tos_runtime.custody.key_provider import FileKeyProvider
from tos_runtime.custody.ports import (
    CredentialCustody,
    CredentialHandle,
    CustodyError,
    CustodyLoadRefused,
    CustodyManifestError,
    CustodyScopeNotProvisioned,
    KeyProvider,
)

__all__ = [
    "CredentialCustody",
    "CredentialHandle",
    "CustodyError",
    "CustodyLoadRefused",
    "CustodyManifest",
    "CustodyManifestError",
    "CustodyScopeNotProvisioned",
    "FileCustody",
    "FileKeyProvider",
    "KeyProvider",
    "MANIFEST_FILENAME",
    "PROVISIONED_SCOPES",
    "verify_file_mode_and_owner",
]
