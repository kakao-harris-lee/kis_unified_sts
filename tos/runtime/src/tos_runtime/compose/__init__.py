"""``tos_runtime.compose`` — the ONE composition root (design #40 D1.1;
slice plan §4).

"composition root 는 `tos_runtime.compose` 단 하나 — 커널 Protocol 심을
구현체와 한 자리에서 결선한다. 커널 어디에도 «기본 구현» 을 두지 않는다."
No other package in this distribution wires a kernel Protocol seam
(``SendTransport``/``Transmit``/``EvidenceSink``/``Stage``/
``DecisionContextResolver``/…) to a concrete implementation; that happens
exactly here.

Public surface:

* :func:`~tos_runtime.compose.root.compose_paper_runtime` — wires custody,
  the durable evidence store, the emergency log, Trustworthy Time, the RCL
  log, the Safety Authority epoch service + Intent Registry, the Aggregate
  Risk Authority + Action Flow Governor, the currentness assembler + Egress
  Currentness Proof issuer, release admission, the engine
  ``EngineCore`` (real ``Stage``s for steps 4, 6-10, 13, 14; the kernel's own
  existing Order Construction stages for steps 2, 3, 5, 11), and the
  ``BrokerEgressGateway`` + ``SyntheticPaperTransport`` — in that order.
* :class:`~tos_runtime.compose.root.ComposedRuntime` — the return value,
  holding every live composed service plus ``run_once(events)``.
* :class:`~tos_runtime.compose.root.ConstructionConfig` — the per-strategy
  Order Construction facts steps 2/3/5/11 need.
* :class:`~tos_runtime.compose.root.ReleaseAdmissionRefused` — raised when
  release admission denies at startup (fail-closed boot refusal).
* :mod:`tos_runtime.compose.context` — the ``SendBoundaryContext`` lazy
  resolver + the small, explicitly-reported compose-only recording shims
  (see that module's own docstring).
* :mod:`tos_runtime.compose.cli` — argument parsing only; no daemon loop
  (Phase 5).

Firewall (tools/tos_firewall_check.py R1, runtime scope): stdlib + ``tos.*``
+ ``tos_runtime.*`` only. No ``shared.*``.
"""

from __future__ import annotations

from tos_runtime.compose.root import (
    ComposedRuntime,
    ConstructionConfig,
    ReleaseAdmissionRefused,
    compose_paper_runtime,
)

__all__ = [
    "ComposedRuntime",
    "ConstructionConfig",
    "ReleaseAdmissionRefused",
    "compose_paper_runtime",
]
