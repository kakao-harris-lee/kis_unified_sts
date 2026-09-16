"""``JsonLinesObservationJournal`` — the file-backed :class:`~tos_runtime.marketfeed.ports
.ObservationIntake` (plan ``docs/plans/2026-09-16-tos-tick-source-plan.md`` §2 decision 4, lane C).

An upstream collector — out of scope here — appends one JSON object per line to a plain text
file. This module only *reads* that file; it never writes to it, opens no socket, and reads no
clock. One line looks like::

    {"raw_event_id": "...", "instrument": "...", "as_of_ms": 1700000060000,
     "fields": {"close": 4512500}, "source_id": "...", "received_ms": 1700000060120}

**Fail-closed on malformed input, deliberately not fail-soft.** A line that is not valid JSON, is
missing a required key, or carries a field value outside :data:`~tos.dsl.ScalarValue`
(``bool | int | float | str``) refuses the **whole** :meth:`~JsonLinesObservationJournal.poll` call
with a typed error naming the file and the 1-indexed line — it does not silently skip the bad line
and return the rest. A collector writing garbage is a fault this journal surfaces, never one it
routes around; skipping the line would make a corrupt collector look like a quiet one, which is
exactly the kind of vacuous validity design #32 §2.3 and this wave's own port contract
(``ports.py``'s "field state is derived, never declared") refuse elsewhere in this package.

**No trailing-partial-line special case.** A collector that appends non-atomically — so a reader
mid-poll can observe a half-written final line — is a real operational shape, but this
implementation does not treat the LAST line differently from any other: a malformed final line
refuses the poll exactly like a malformed line anywhere else in the file (see
``test_malformed_trailing_line_is_not_treated_specially`` in the paired test module, which pins
this choice so it is never silently revisited). The fix belongs upstream, in the collector: write
atomically (temp file + rename) or buffer whole lines before flushing, rather than have every
reader guess whether a half-written line is "not yet there" or "corrupt". A guess in either
direction is a phantom this module chooses not to make.

**Scalar honesty.** :data:`~tos.dsl.ScalarValue` is ``bool | int | float | str`` — a JSON ``null``,
object, or array field value is refused the same as a malformed line, and a JSON number simply
passes through as whatever Python type ``json.loads`` gave it (``int`` or ``float``); this module
does not attempt to detect a fractional magnitude masquerading as an exact minor unit — that is
:class:`~tos.marketfeed.records.PreimageEntry`'s job downstream (``records.py:64-71``), not the
journal's.

**Missing file vs. nothing new.** A journal path that does not exist is a typed refusal, never an
empty result — "the journal does not exist" and "the journal has nothing new since ``after_as_of_ms``"
are different facts, and collapsing them would let a collector that was never wired at all look
identical to one that is simply caught up.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos.*`` + ``tos_runtime.*``
only. No network, no clock — this module reads a file and nothing else.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tos_runtime.marketfeed.ports import ObservationIntake, RawObservation

__all__ = ["JournalError", "JsonLinesObservationJournal"]

#: A line-local refusal factory: ``reason -> JournalError`` already bound to the file path and
#: line number (see :meth:`JsonLinesObservationJournal._parse_line`).
_Refuse = Callable[[str], "JournalError"]

#: The keys every journal line MUST carry — mirrors :class:`RawObservation`'s own required
#: (non-defaulted) fields exactly (``ports.py``'s ``RawObservation``: ``received_ms`` alone is
#: optional there, via its ``= None`` default).
_REQUIRED_KEYS: frozenset[str] = frozenset(
    {"raw_event_id", "instrument", "as_of_ms", "fields", "source_id"}
)

#: JSON-native scalar types that map 1:1 onto :data:`~tos.dsl.ScalarValue`. ``bool`` is checked
#: before ``int`` at every call site below — ``bool`` is an ``int`` subclass in Python, and a
#: silent ``True -> 1`` narrowing would be exactly the kind of unannounced coercion this module's
#: fail-closed discipline refuses elsewhere.
_SCALAR_FIELD_TYPES: tuple[type, ...] = (bool, int, float, str)


class JournalError(Exception):
    """Raised when the observation journal is missing, unreadable, or carries a malformed line.

    One exception type covers every refusal (mirrors
    :class:`~tos_runtime.time.config.TimeConfigError`'s own single-class-many-messages
    convention) — the message names the concrete fact (missing file vs. which line, and why).
    """


@dataclass(frozen=True)
class JsonLinesObservationJournal:
    """A file-backed :class:`~tos_runtime.marketfeed.ports.ObservationIntake`.

    Attributes:
        path: The journal file an upstream collector appends to. Read-only from this class's own
            point of view — nothing here ever opens ``path`` in a write mode.
    """

    path: Path

    def poll(
        self, *, instrument: str, after_as_of_ms: int | None
    ) -> Sequence[RawObservation]:
        """Return ``instrument``'s observations strictly newer than ``after_as_of_ms``.

        The entire file is parsed and validated before any instrument/as-of filtering happens, so
        a malformed line for a DIFFERENT instrument still refuses the call — the journal is one
        shared fault domain, not one per instrument (module docstring).

        Args:
            instrument: The single instrument in scope (``ports.py``'s ``ObservationIntake``).
            after_as_of_ms: The newest as-of already issued, or ``None`` for "everything".

        Returns:
            The matching observations, strictly newer than ``after_as_of_ms``, oldest first.

        Raises:
            JournalError: The file does not exist, cannot be read, or contains a malformed line.
        """
        if not self.path.is_file():
            raise JournalError(f"observation journal does not exist: {self.path}")
        try:
            text = self.path.read_text(encoding="utf-8")
        except OSError as exc:
            raise JournalError(
                f"observation journal could not be read: {self.path} ({exc})"
            ) from exc

        parsed = [
            self._parse_line(raw_line, line_no)
            for line_no, raw_line in enumerate(text.splitlines(), start=1)
            if raw_line.strip()
        ]
        matching = [
            observation
            for observation in parsed
            if observation.instrument == instrument
            and (after_as_of_ms is None or observation.as_of_ms > after_as_of_ms)
        ]
        matching.sort(key=lambda observation: observation.as_of_ms)
        return tuple(matching)

    def _parse_line(self, raw_line: str, line_no: int) -> RawObservation:
        """Parse and validate one journal line, or raise :class:`JournalError` naming it."""

        def refuse(reason: str) -> JournalError:
            return JournalError(f"{self.path}:{line_no}: {reason}")

        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise refuse(f"not valid JSON ({exc})") from exc
        if not isinstance(payload, dict):
            raise refuse(f"not a JSON object (got {type(payload).__name__})")

        missing = _REQUIRED_KEYS - payload.keys()
        if missing:
            raise refuse(f"missing required key(s): {sorted(missing)}")

        raw_event_id = self._require_nonblank_str(payload, "raw_event_id", refuse)
        instrument = self._require_nonblank_str(payload, "instrument", refuse)
        source_id = self._require_nonblank_str(payload, "source_id", refuse)
        as_of_ms = self._require_int(payload, "as_of_ms", refuse)
        received_ms_raw = payload.get("received_ms")
        received_ms = (
            None
            if received_ms_raw is None
            else self._require_int(payload, "received_ms", refuse)
        )
        fields = self._require_fields(payload, refuse)

        return RawObservation(
            raw_event_id=raw_event_id,
            instrument=instrument,
            as_of_ms=as_of_ms,
            fields=fields,
            source_id=source_id,
            received_ms=received_ms,
        )

    @staticmethod
    def _require_nonblank_str(
        payload: dict[str, Any], key: str, refuse: _Refuse
    ) -> str:
        value = payload[key]
        if not isinstance(value, str) or not value.strip():
            raise refuse(f"{key!r} must be a non-blank string (got {value!r})")
        return value

    @staticmethod
    def _require_int(payload: dict[str, Any], key: str, refuse: _Refuse) -> int:
        value = payload[key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise refuse(f"{key!r} must be an int (got {value!r})")
        return value

    @staticmethod
    def _require_fields(
        payload: dict[str, Any], refuse: _Refuse
    ) -> tuple[tuple[str, Any], ...]:
        fields = payload["fields"]
        if not isinstance(fields, dict):
            raise refuse(
                f"'fields' must be a JSON object (got {type(fields).__name__})"
            )
        entries: list[tuple[str, Any]] = []
        for key, value in fields.items():
            if not isinstance(key, str) or not key.strip():
                raise refuse(f"'fields' key must be a non-blank string (got {key!r})")
            if isinstance(value, _SCALAR_FIELD_TYPES):
                entries.append((key, value))
                continue
            raise refuse(
                f"'fields' key {key!r} has unsupported value type "
                f"{type(value).__name__} (must be bool|int|float|str)"
            )
        return tuple(entries)


#: Static conformance check — mypy fails this file if this class's shape ever drifts from the
#: ``ObservationIntake`` port it implements (structurally; there is no explicit inheritance edge).
_conforms_to_observation_intake: type[ObservationIntake] = JsonLinesObservationJournal
