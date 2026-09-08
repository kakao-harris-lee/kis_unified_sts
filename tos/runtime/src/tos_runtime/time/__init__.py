"""tos_runtime.time — Trustworthy Time runtime composition (design #40 §5 order 1).

Realizes the runtime (composition-root) half of the Trustworthy Time slice
(slice plan §1, ``docs/plans/2026-09-08-tos-phase2-runtime-slice1-time-
evidence-plan.md``): this package **collects inputs and calls the ``tos.time``
kernel predicate substrate** — it never re-judges what the kernel already
decides (slice plan §0 "커널 Protocol 심을 구현한다. 커널을 편집하지 않는다").

Public surface groups by module:

* :mod:`tos_runtime.time.sources` — injectable monotonic + reference-clock
  source ports (``MonotonicSource``/``ReferenceSourceReader`` Protocols) and
  their Phase-2 concrete implementations (``time.monotonic_ns`` /
  ``time.time_ns`` — the first place in this codebase a real clock is read;
  the kernel is clock-free by design, time design §0.3).
* :mod:`tos_runtime.time.generation` — ``GenerationCounter``, the in-process
  monotonic TTS-generation counter (durable binding to the RCL log is design
  #40 §5 order 3, out of this slice's scope).
* :mod:`tos_runtime.time.config` — the VER-002-keyed YAML loader
  (``tos/runtime/config/time.example.yaml``); any missing or null
  (named-TBD) bound is a fail-closed startup rejection (``TimeConfigError``).
* :mod:`tos_runtime.time.service` — ``TrustworthyTimeService``, the
  composition that turns injected readings + config into kernel-predicate
  calls, a ``tos.time.TimeHealthSnapshot`` (evidenced durably before it is
  ever exposed), and a conservative ``HealthState`` transition.

Phase-2 scope note (ADR-002-008 :184 residual, named explicitly, not hidden):
only ONE reference source kind is implemented — the local system clock
(``LocalSystemClockReader``). NTP / broker-time / any second independent
reference source is NOT implemented in this slice; a profile that requires
more than one independent reference (``MIN_time_independent_reference_count``
> 1) will therefore never observe ``TRUSTED`` from this package alone, which
is the conservative, honest outcome — not a bug to work around here.
"""

from __future__ import annotations
