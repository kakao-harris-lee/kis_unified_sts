"""``tos_runtime.custody`` — file-backed credential custody + key provider"""

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
