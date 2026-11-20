"""CP-3 operator repair tools (``tools/tos_cp3/ops``).

The three files here are what an operator runs BY HAND on a stock MOCK tenant
that has to be repaired during the trading day (operator standing approval
2026-11-20, memory ``mock-tenant-intraday-iteration-20261120.md``). They are not
part of the unattended cron path — ``tools/tos_cp3/runners/`` owns that — and
they live in the repo rather than in a session scratchpad so the procedure is
reviewable, testable and the same one twice.

Runbook: ``docs/runbooks/tos-paper-boot.md`` §7.2-f «장중 모의 tenant 재시작».

Firewall: legacy side (``tools/``). No ``tos`` / ``tos_runtime`` import.
"""

from __future__ import annotations
