"""Broker transport implementations for the runtime shell (design #34 §5.1 / plan
``docs/plans/2026-09-10-tos-kis-mock-transport-plan.md``).

The kernel's ``tos.brokeradapter.Transport`` Protocol is deliberately network-free: the firewall
forbids network stdlib inside ``tos/`` (design #1 §2.3), so any transport that actually reaches a
broker necessarily lives here, in ``tos_runtime``, one layer below the kernel. This package is a
plain namespace for one or more such implementations — see :mod:`tos_runtime.transport.kis_mock`
for the first ("KIS 모의투자 stock order-verification MOCK" — 주식 MOCK 만, 선물 MOCK 은 KIS 가
제공하지 않음, plan §0 결정 3).

Nothing in this package is wired into the compose root yet (plan §4 슬라이스 T1 vs T2) — that is
a separate slice's job (``tos_runtime.compose``).
"""

from __future__ import annotations

__all__: list[str] = []
