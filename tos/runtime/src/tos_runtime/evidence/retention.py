"""Retention-policy loader + judgement-only evaluation (design #40 D3, §2 item 5)."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict
from tos.canonical import ArtifactIntegrityError
from tos.evidence import EvidenceAppendReceipt, Tombstone, retention_deletable

from tos_runtime.evidence.store import SqliteEvidenceStore

__all__ = ["RetentionPolicy", "RetentionVerdict", "tombstone"]

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
        """Wrap an already-validated policy mapping."""
        self._minimum_days_by_class = dict(minimum_days_by_class)

    @classmethod
    def load(cls, path: Path) -> RetentionPolicy:
        """Load a retention policy YAML file (fail-closed on a missing key)."""
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
        """Judge every entry's deletability; never deletes anything."""
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
    """Append one :class:`~tos.evidence.Tombstone` for a ``deletable`` verdict."""
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
