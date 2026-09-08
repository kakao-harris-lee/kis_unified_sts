"""Retention-policy loader + judgement-only evaluation (design #40 D3, §2 item 5).

:func:`evaluate` judges — it never deletes. The kernel predicate
:func:`tos.evidence.retention_deletable` is the sole authority for "may this
record's tombstone be inserted"; this module only assembles that predicate's
five injected arguments per record and reports the verdicts. The ONLY write
action this package exposes is :func:`tombstone`, which appends one
append-only :class:`~tos.evidence.Tombstone` record — there is no deletion
job anywhere in this module, by construction (design #40 §2 item 5 "삭제
잡 없음 · 툼스톤 INSERT 만").

**Policy loading is fail-closed on a missing key, not a missing value.**
``minimum_days_by_class`` must be PRESENT in the YAML (its absence refuses to
load — "부재 시 기동 거부"); an individual class's value may be YAML ``null``
("named-TBD", pending operator approval), which the kernel predicate itself
already treats as "no configured minimum" (refuses that class, never
vacuously admits it).

**Age is process-monotonic only, honestly scoped.** ``entries.
appended_at_monotonic_ns`` is a ``time.monotonic_ns()``-family value — NOT
epoch-relative, and therefore not comparable across a process restart. This
module's ``now`` parameter is the same monotonic coordinate space, so
:func:`evaluate`'s ``age_days`` is only meaningful within one continuous
process lifetime. Wiring real wall-clock age (Trustworthy Time,
``tos_runtime.time``, a sibling lane) is out of this slice's scope; this
module does not claim more than that honest limit.

Firewall: stdlib (``pathlib``) + ``pydantic`` + ``pyyaml`` (``yaml``) +
``tos.canonical``/``tos.evidence`` + ``tos_runtime.evidence.store`` only.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict
from tos.canonical import ArtifactIntegrityError
from tos.evidence import EvidenceAppendReceipt, Tombstone, retention_deletable

from tos_runtime.evidence.store import SqliteEvidenceStore

__all__ = ["RetentionPolicy", "RetentionVerdict", "tombstone"]

#: Nanoseconds per day — used only to convert a monotonic-ns delta to
#: ``age_days`` for the kernel predicate (see the module docstring's honest
#: scope note on what this delta actually means across a restart).
_NS_PER_DAY = 24 * 60 * 60 * 1_000_000_000


class RetentionVerdict(BaseModel):
    """One record's retention judgement — never a deletion, only a report."""

    model_config = ConfigDict(frozen=True)

    seq: int
    record_class: str
    deletable: bool
    reason: str | None = None


class RetentionPolicy:
    """The loaded ``minimum_days_by_class`` policy (design #40 §2 item 5)."""

    def __init__(self, minimum_days_by_class: Mapping[str, int | None]) -> None:
        """Wrap an already-validated policy mapping.

        Prefer :meth:`load` over calling this directly — it enforces the
        fail-closed "key must be present" rule the YAML file itself is
        subject to.
        """
        self._minimum_days_by_class = dict(minimum_days_by_class)

    @classmethod
    def load(cls, path: Path) -> RetentionPolicy:
        """Load a retention policy YAML file (fail-closed on a missing key).

        Args:
            path: The YAML file (see
                ``tos/runtime/config/evidence_retention.example.yaml``).

        Returns:
            The loaded policy.

        Raises:
            ArtifactIntegrityError: If the file is unreadable, not a mapping,
                or missing the ``minimum_days_by_class`` top-level key
                entirely (a ``null`` VALUE for one class is allowed —
                named-TBD; the KEY itself missing is refused).
        """
        raw = yaml.safe_load(path.read_text())
        if not isinstance(raw, Mapping) or "minimum_days_by_class" not in raw:
            raise ArtifactIntegrityError(
                "RetentionPolicy.load: 'minimum_days_by_class' key is missing from "
                f"{path} — refuse to load (fail-closed; a class's own value may be "
                "null/named-TBD, but the key itself must be present)"
            )
        minimum_days_by_class = raw["minimum_days_by_class"]
        if not isinstance(minimum_days_by_class, Mapping):
            raise ArtifactIntegrityError(
                "RetentionPolicy.load: 'minimum_days_by_class' must be a mapping "
                f"(got {type(minimum_days_by_class).__name__}) in {path}"
            )
        return cls(minimum_days_by_class)

    @property
    def minimum_days_by_class(self) -> Mapping[str, int | None]:
        """The loaded per-class minimum retention, ``None`` meaning named-TBD."""
        return dict(self._minimum_days_by_class)

    def evaluate(
        self,
        store: SqliteEvidenceStore,
        now: int,
        holds: Mapping[int, bool],
        open_or_live: Mapping[int, bool],
    ) -> tuple[RetentionVerdict, ...]:
        """Judge every entry's deletability; never deletes anything.

        Args:
            store: The evidence store to read entry metadata from.
            now: The current moment, in the SAME monotonic-ns coordinate
                space as ``appended_at_monotonic_ns`` (see module docstring's
                honest scope note).
            holds: ``seq -> holds_active``. A ``seq`` absent from this
                mapping is treated as ``None`` (unknown), which the kernel
                predicate refuses (fail-closed), never as "no hold".
            open_or_live: ``seq -> open_or_live``. Same fail-closed-on-absence
                rule as ``holds``.

        Returns:
            One :class:`RetentionVerdict` per entry, in ``seq`` order.
        """
        # The kernel predicate's own signature is `Mapping[str, int] | None` —
        # a null/named-TBD class must not reach it as a `None` VALUE inside
        # the mapping. Dropping null-valued classes here is behaviourally
        # identical to keeping them: `retention_deletable` does
        # `minimum_days_by_class.get(record_class)` and treats a `None`
        # result (whether from an absent key or a `None` value) the same way
        # — refuse (fail-closed) — so this filter changes only the type, not
        # the verdict.
        valued_minimums: Mapping[str, int] = {
            record_class: minimum
            for record_class, minimum in self._minimum_days_by_class.items()
            if minimum is not None
        }
        verdicts: list[RetentionVerdict] = []
        for meta in store.iter_entry_meta():
            age_days = (now - meta.appended_at_monotonic_ns) // _NS_PER_DAY
            deletable = retention_deletable(
                meta.record_class,
                age_days,
                valued_minimums,
                holds.get(meta.seq),
                open_or_live.get(meta.seq),
            )
            verdicts.append(
                RetentionVerdict(
                    seq=meta.seq,
                    record_class=meta.record_class,
                    deletable=deletable,
                    reason=None if deletable else "kernel retention_deletable refused",
                )
            )
        return tuple(verdicts)


def tombstone(
    store: SqliteEvidenceStore,
    verdict: RetentionVerdict,
    *,
    dual_control_ref: str,
    deleted_at: str | None = None,
) -> EvidenceAppendReceipt:
    """Append one :class:`~tos.evidence.Tombstone` for a ``deletable`` verdict.

    The only write action this module performs — never a ``DELETE``.

    Args:
        store: The evidence store to append the tombstone into.
        verdict: A verdict from :meth:`RetentionPolicy.evaluate` with
            ``deletable=True`` — refused otherwise.
        dual_control_ref: The required, non-blank dual-control witness
            reference (:class:`~tos.evidence.Tombstone`'s own invariant,
            ADR-002-016 §17 line 443).
        deleted_at: An opaque time-snapshot id (this package is clock-free —
            see :class:`~tos.evidence.Tombstone`'s own docstring); ``None``
            when not yet bound to a Trustworthy Time snapshot.

    Returns:
        The tombstone entry's commit receipt.

    Raises:
        ValueError: If ``verdict.deletable`` is not ``True`` — a tombstone
            for a non-deletable record would misrepresent the retention
            judgement.
    """
    if not verdict.deletable:
        raise ValueError(
            f"tombstone refused: verdict for seq={verdict.seq} is not deletable "
            f"({verdict.reason!r}) — no deletion job exists in this module, and a "
            "tombstone must not be fabricated for a record retention still protects"
        )
    record = Tombstone(
        record_id=str(verdict.seq),
        record_class=verdict.record_class,
        deleted_at=deleted_at,
        dual_control_ref=dual_control_ref,
    )
    return store.append(
        record.model_dump(mode="json"),
        kind="TOMBSTONE",
        record_class=verdict.record_class,
    )
