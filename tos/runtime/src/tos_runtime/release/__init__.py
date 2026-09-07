"""Release admission — design #40 §5 order 6, lane R item 4
(`docs/plans/2026-09-08-tos-phase2-runtime-slice3-authority-risk-currentness-
compose-plan.md` §3 item 4).

Realizes the kernel's ``tos.sci`` (ADR-002-029) release-admission negative
gate over an operator-approved static Phase 2 config snapshot: no live
source/build/dependency/signer/registry-scanning runtime exists yet, so every
fact this package needs beyond the running process's own
:class:`~tos.workload.RuntimeIdentity` is config, not computation. A ``null``
config value refuses service construction (fail-closed) — see
:mod:`tos_runtime.release.config`.

Public surface groups by module:

* :mod:`tos_runtime.release.config` — :func:`~tos_runtime.release.config.
  load_release_config`.
* :mod:`tos_runtime.release.admission` — :func:`~tos_runtime.release.
  admission.release_admission`, :class:`~tos_runtime.release.admission.
  ReleaseAdmissionService`, :class:`~tos_runtime.release.admission.
  ReleaseRestrictionLookup`.
"""

from __future__ import annotations

from tos_runtime.release.admission import (
    ReleaseAdmissionService,
    ReleaseRestrictionLookup,
    release_admission,
)
from tos_runtime.release.config import (
    ReleaseAdmissionConfig,
    ReleaseAdmissionConfigError,
    load_release_config,
)

__all__ = [
    "ReleaseAdmissionConfig",
    "ReleaseAdmissionConfigError",
    "ReleaseAdmissionService",
    "ReleaseRestrictionLookup",
    "load_release_config",
    "release_admission",
]
