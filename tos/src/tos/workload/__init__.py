"""Runtime workload identity — pure kernel records + predicates (design #40 D4, kernel side).

Realizes the *kernel*-scope half of design doc #40's D4 decision ("워크로드
정체성 · 키 회전 · 자격증명 보관" — workload identity, key rotation, credential
custody; ``docs/plans/2026-09-07-tos-phase2-runtime-shell-preliminary-decisions.md``
§D4, §5-A). Key rotation and credential custody are ``tos_runtime.custody``
territory (D1 not yet ratified — see :mod:`tos.evidence.chain` for the kernel-side
HMAC chain scheme that custody's rotated keys feed). This package authors only the
two pieces §5-A calls out as landable pre-ratification: the workload-instance
identity shape a runtime issuer must produce (:class:`RuntimeIdentity`), and the
environment-label consistency check a boot sequence consults before arming
(:func:`environment_label_consistent`).

**New package, not an existing ADR-numbered one** — see
:mod:`tos.workload.records`'s module docstring "package placement" section for the
anti-phantom grep record of why no sibling package (``tos.failuredomain``,
``tos.sci``, ``tos.authority``, ``tos.egress``) already owns this concept.

This package is **pure, non-transmitting, clock-free, and RNG-free**: frozen
pydantic models over injected scalars plus a conservative fail-closed predicate. It
never issues a nonce, reads a code digest, or refuses to boot itself — those are
runtime actions (D1). It imports only ``pydantic`` + stdlib + ``tos.canonical``
(the digest-binding substrate's ``FrozenModel``/``ArtifactIntegrityError``) — no
``numpy``/``pandas``/``yaml``, no ``shared.*``, no other ``tos`` sibling package
(no ``tos.rcl`` / ``tos.evidence`` / ``tos.authority`` / ``tos.egress`` — the
"reported not merged" identity axes stay reported, not silently coupled by an
import edge) — actively verified by this package's own import-closure test.

Public surface groups by module:

* :mod:`tos.workload.records` — :class:`RuntimeIdentity` (design #40 D4-a).
* :mod:`tos.workload.predicates` — :func:`environment_label_consistent`
  (design #40 D4-b).
"""

from __future__ import annotations

from tos.workload.predicates import environment_label_consistent
from tos.workload.records import RuntimeIdentity

__all__ = [
    "RuntimeIdentity",
    "environment_label_consistent",
]
