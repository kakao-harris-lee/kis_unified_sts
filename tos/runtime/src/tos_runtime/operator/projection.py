"""``OperatorProjection`` — an authority-neutral, read-only JSON snapshot of runtime state
(TOS Phase 5 W4 plan §2 decision 7; JSON schema pinned at plan §2.7; ADR-DEV-014
``OBS-INV-001..006``).

**What this is not.** This projection never authorizes, gates, halts, or clears anything — it is
a pure *observation* of facts other parts of the runtime already computed, assembled for a human
operator (or a downstream read-only dashboard route, plan §2 decision 9) to look at. Every field
this module can populate comes from a zero-argument READ callable supplied at construction; this
class holds no reference to a store, a driver, a gateway, or any other write-capable object (plan
§2 decision 8a — see ``tests/operator/test_no_write_port.py`` for the structural + negative-grep
proof this package holds no write port at all).

**"One callable per field group."** The constructor accepts exactly one read callable per
top-level JSON field group (``runtime``, ``recovery``, ``driver``, ``time``, ``safety_mesh``,
``currentness``, ``rcl``, ``inbox``, ``evidence``, ``release``, ``protective``, ``operations``),
plus two callables for the ``alerts`` group (the raw STM_ALERT candidate seqs and the resolved
seqs — kept separate because "unresolved" is a DERIVED fact, computed here, never supplied
pre-computed by a caller). Each group callable returns either an already-shaped dict for that
group, or ``None`` when the fact has no source yet — "원천 없음 = null" (OBS-INV-003): a missing
fact is represented as ``null``, never guessed, never defaulted to a constant that looks like an
answer.

**No literal ``True`` except the ``non_authorizing`` marker (OBS-INV-002/006).** ``build()``
never writes a hardcoded ``True`` into any field this module computes from callable input — the
single literal ``True`` in the whole document is the ``non_authorizing`` marker itself, which is
a documentary constant about the DOCUMENT (it is not a fact about the runtime), not a value this
module infers. ``tests/operator/test_projection.py`` pins this with an all-callables-return-None
mutation check (plan §5 mutation M6).

**Self-diagnostic failure surfacing.** If a read callable raises, ``build()`` never lets the
exception propagate (a broken read for one field group must not break the whole projection or,
transitively, the driver turn that triggers an export — see
:meth:`tos_runtime.engine.driver.EngineDriver.bind_after_turn`). The failing group's own field is
recorded as ``None`` and an internal counter/last-error pair is surfaced under this SAME
document's own ``export.failures``/``export.last_error`` fields — a self-observation of this
build cycle's own read health. A caller may ALSO supply ``read_export_status`` (optional,
``None`` by default) to fold a :class:`~tos_runtime.operator.export.ProjectionExporter`'s own
write-side failure count/last error into these SAME two fields (compose wiring's own directive —
see :func:`tos_runtime.compose._operations_wiring.apply_operations_wiring`'s module docstring for
why this needs a two-step, late-bound construction): counts SUM; ``last_error`` prefers the
exporter's own message when both sides have one (a write failure is necessarily the NEWER of the
two — discovered only on the build AFTER it happened).

**Alert ownership (plan §2 decision 12; runtime operations wiring plan (2026-09-13) §2 decision
4/8).** ``alerts.unresolved_stm_alert_seqs`` is DERIVED here: "unresolved" = "in the candidate set
and NOT in the resolved set". There is still no ``STM_ALERT_RESOLVED`` evidence producer wired
anywhere, and there never will be — ADR-002-028 :159/:187/:191/:388/:511 is explicit that no
acknowledgement, mute, dedup, or operator action ever creates "resolved"/"incident closed"/
"recovery readiness". What exists now is ``tos_runtime.safety.ack.acknowledge_alert``'s own
single-operator ``STM_ALERT_ACKNOWLEDGED`` producer — a confirmation of receipt, nothing more
(that module's own docstring: "acknowledgement is not containment, remediation, incident closure,
recovery readiness, or re-arm"). The caller-supplied "resolved"-seq reader
(``tos_runtime.compose._operations_wiring._read_resolved``) now sources from THOSE acknowledged
seqs — so this field's exported name, ``unresolved_stm_alert_seqs`` (schema v1, UNCHANGED), means
precisely **"not yet acknowledged"**, never "not yet fixed" or "not yet closed"; an acknowledged
alert leaving this list grants no authority and clears no state anywhere else in the runtime (the
safety mesh's own ``clear()`` verdict, the new-risk-halt latch, and the re-arm workflow are all
structurally unreachable from ``tos_runtime.safety.ack`` — see that module's own "structural pin"
docstring section). If the RESOLVED (acknowledged-seq) reader itself fails, this module
deliberately does **not** propagate that failure into "assume everything is acknowledged" (which
would silently hide real alerts) — a failed read is treated the same as "nothing acknowledged
yet" so nothing is ever wrongly excluded from ``unresolved_stm_alert_seqs``. If the CANDIDATE
reader fails, the derived list becomes genuinely unknown (``None``) — there is nothing safe to
report at all. Alert **delivery** is out of this module's scope entirely: the legacy
Telegram-based alert-manager reads this file and delivers it; this runtime does not know a
delivery channel exists (see :attr:`_ALERT_DELIVERY_OWNER`).

Firewall: stdlib only — no ``tos``/``tos_runtime`` import at all (this module is a pure dict
assembler over caller-supplied callables; it has nothing kernel-facing to reach for).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from typing import Any

__all__ = ["OperatorProjection", "SCHEMA_VERSION", "MAX_UNRESOLVED_STM_ALERT_SEQS"]

#: The JSON document's own ``schema_version`` field (plan §2.7). Bumping this is a schema
#: change — both this module and any consumer (e.g. the dashboard DTO, plan §2 decision 9) move
#: together, per the plan's own "필드 추가는 양쪽 동시 커밋" discipline.
SCHEMA_VERSION = 1

#: Export size cap for ``alerts.unresolved_stm_alert_seqs`` — plan §2 decision 13: "export 목록
#: 상한 50 ... 코드 상수로 공시" (an export-size bound, not a policy value, hence a code constant
#: rather than a YAML setting). The candidate-seq reader is expected to already return at most
#: this many (the newest ones); this module re-truncates defensively so a misbehaving reader
#: cannot blow the export past its documented bound.
MAX_UNRESOLVED_STM_ALERT_SEQS = 50

#: plan §2 decision 12 — the runtime never learns a delivery channel or recipient exists
#: (firewall: egress 0 from this package). This string is the documentary answer to "who
#: delivers this", not a configuration value.
_ALERT_DELIVERY_OWNER = "legacy alert-manager (outside tos_runtime)"

#: A zero-argument callable returning either an already-shaped value for its field group, or
#: ``None`` when the fact has no source yet.
ReadCallable = Callable[[], Any]

#: The ordered ``(schema_key, ...)`` field-group names this class accepts one reader for each of
#: (excluding the two ``alerts`` readers, handled separately below).
_GROUP_FIELDS: tuple[str, ...] = (
    "runtime",
    "recovery",
    "driver",
    "time",
    "safety_mesh",
    "currentness",
    "rcl",
    "inbox",
    "evidence",
    "release",
    "protective",
    "operations",
)


class OperatorProjection:
    """Builds the plan §2.7 operator-projection JSON document from read callables only.

    Every constructor argument is a zero-argument callable (``Callable[[], X | None]``) — never
    a store, driver, gateway, or any other object this class could call a write method on (plan
    §2 decision 8a).
    """

    def __init__(
        self,
        *,
        read_runtime: ReadCallable,
        read_recovery: ReadCallable,
        read_driver: ReadCallable,
        read_time: ReadCallable,
        read_safety_mesh: ReadCallable,
        read_currentness: ReadCallable,
        read_rcl: ReadCallable,
        read_inbox: ReadCallable,
        read_evidence: ReadCallable,
        read_release: ReadCallable,
        read_protective: ReadCallable,
        read_operations: ReadCallable,
        read_unresolved_stm_alert_candidate_seqs: ReadCallable,
        read_resolved_stm_alert_seqs: ReadCallable,
        read_export_status: Callable[[], tuple[int, str | None]] | None = None,
    ) -> None:
        self._readers: dict[str, ReadCallable] = {
            "runtime": read_runtime,
            "recovery": read_recovery,
            "driver": read_driver,
            "time": read_time,
            "safety_mesh": read_safety_mesh,
            "currentness": read_currentness,
            "rcl": read_rcl,
            "inbox": read_inbox,
            "evidence": read_evidence,
            "release": read_release,
            "protective": read_protective,
            "operations": read_operations,
        }
        self._read_candidate_seqs = read_unresolved_stm_alert_candidate_seqs
        self._read_resolved_seqs = read_resolved_stm_alert_seqs
        #: Optional — a caller (compose wiring) that ALSO owns a
        #: :class:`~tos_runtime.operator.export.ProjectionExporter` may supply this to fold that
        #: exporter's own write-side ``failures``/``last_error`` into THIS document's
        #: ``export.failures``/``export.last_error`` (module docstring — a write failure from a
        #: PRIOR export cycle becomes visible on the NEXT build, since the exporter itself never
        #: raises and this projection has no other way to learn about it). ``None`` (the default,
        #: and every existing standalone construction's behaviour) means this document's
        #: ``export.failures``/``export.last_error`` reflect ONLY this build's own read-callable
        #: failures, exactly as before this field existed.
        self._read_export_status = read_export_status
        #: ``projection_generation`` — a monotonic export sequence number (plan §2.7), one of the
        #: two fields (with ``exported_at_monotonic_ns``) this class computes itself rather than
        #: reading from a callable: both are facts ABOUT this projection's own build history, not
        #: facts about the runtime it observes.
        self._generation = 0

    def build(self) -> dict[str, Any]:
        """Assemble one operator-projection document.

        Increments :attr:`_generation` first (a build that later fails partway through some
        group's own read still counts as one export attempt — "generation" tracks build calls,
        not successful reads). Never raises: every group read is individually guarded, and a
        failure there is recorded under this SAME document's ``export.failures``/
        ``export.last_error`` rather than aborting the whole build.
        """
        self._generation += 1
        read_failures = 0
        last_error: str | None = None

        def _read(name: str, callback: ReadCallable) -> Any:
            nonlocal read_failures, last_error
            try:
                return callback()
            except (
                Exception
            ) as exc:  # noqa: BLE001 - a broken reader yields None, never a crash
                read_failures += 1
                last_error = f"{name}: {exc!r}"
                return None

        groups: dict[str, Any] = {
            name: _read(name, reader) for name, reader in self._readers.items()
        }

        candidates = _read(
            "alerts.unresolved_stm_alert_candidate_seqs", self._read_candidate_seqs
        )
        resolved = _read("alerts.resolved_stm_alert_seqs", self._read_resolved_seqs)
        unresolved = _unresolved_seqs(candidates, resolved)

        # Fold a supplied exporter's own write-side failure count into this SAME document's
        # export field (module docstring / __init__'s own docstring on read_export_status) — the
        # exporter's last_error wins when both sides have one, since it is the NEWER of the two
        # (a write failure can only be observed on the NEXT build, after this build's own reads
        # already ran); read_failures always SUMS (never overwritten).
        if self._read_export_status is not None:
            try:
                exporter_failures, exporter_last_error = self._read_export_status()
            except (
                Exception
            ) as exc:  # noqa: BLE001 - a broken status read never crashes a build
                read_failures += 1
                if last_error is None:
                    last_error = f"export_status: {exc!r}"
            else:
                read_failures += exporter_failures
                if exporter_last_error is not None:
                    last_error = exporter_last_error

        document: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "projection_generation": self._generation,
            "exported_at_monotonic_ns": time.monotonic_ns(),
            "non_authorizing": True,
        }
        for name in _GROUP_FIELDS:
            document[name] = groups[name]
        document["alerts"] = {
            "unresolved_stm_alert_seqs": unresolved,
            "delivery_owner": _ALERT_DELIVERY_OWNER,
        }
        document["export"] = {"failures": read_failures, "last_error": last_error}
        return document


def _unresolved_seqs(
    candidates: Iterable[int] | None, resolved: Iterable[int] | None
) -> list[int] | None:
    """Derive ``alerts.unresolved_stm_alert_seqs`` (module docstring's "alert ownership"
    section).

    ``candidates is None`` (the candidate reader failed or has no source) means the unresolved
    set is genuinely unknown — returns ``None``, never ``[]`` (an empty list would falsely claim
    "known: zero alerts"). ``resolved is None`` (no resolved-seq source, or that reader failed) is
    treated as "resolved is the empty set" — the fail-SAFE direction (nothing gets wrongly
    excluded from the unresolved list because the resolved-reader hiccuped), never the fail-DANGEROUS
    direction of assuming unread candidates are resolved.
    """
    if candidates is None:
        return None
    resolved_set = set(resolved) if resolved is not None else set()
    unresolved = [seq for seq in candidates if seq not in resolved_set]
    return unresolved[:MAX_UNRESOLVED_STM_ALERT_SEQS]
