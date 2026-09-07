"""tos_runtime — the runtime shell (composition root + adapters) for the tos
kernel.

Design #40 (`docs/plans/2026-09-07-tos-phase2-runtime-shell-preliminary-
decisions.md`) D1 — **ratified by the operator 2026-09-08** — decided the
composition boundary this package occupies: `tos/runtime/` is a SEPARATE
distribution (`tos-runtime` / `tos_runtime`) from the `tos` kernel. Allowed
import directions (D1.1):

    tos_runtime -> tos (kernel)                          allowed
    tos_runtime -> an approved adapter (D1.3 allowlist R1)  allowed
    tos -> tos_runtime                                   FORBIDDEN (rule g)
    <anything outside tos/> -> tos OR tos_runtime         FORBIDDEN (rule R)

**D1 ratified 2026-09-08; runtime I/O lives in this distribution and
nowhere in the kernel.** Upper plan §4.2's discipline (no network code
lands inside the `tos/` kernel) extends permanently to this package as its
own composition-root boundary, not merely as a pre-ratification hold; this
module is still a package placeholder only, proving the distribution
boundary, the allowlist split (rule (g)/(e) extension in
`tools/tos_firewall_check.py`), and the hermetic test fixture (D1.4) exist
and are enforced, before any sqlite3/socket-touching code is written. The
composition root this package will eventually hold —
`tos_runtime.compose`, wiring the kernel's Protocol seams
(`SendTransport`, `GatewayEvidenceSink`, `EvidenceSink`, `Transport`,
`SnapshotStore`, `Stage`, `Transmit`, `DecisionContextResolver`) to concrete
adapters in ONE place (D1.1 "composition root" row) — is Phase 2 work that
starts now that D1 has landed (design #40 §5, sequence item 0).
"""

from __future__ import annotations

__version__ = "0.0.1"
