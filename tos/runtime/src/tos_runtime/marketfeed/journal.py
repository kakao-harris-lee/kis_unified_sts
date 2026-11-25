"""``JsonLinesObservationJournal`` — the file-backed :class:`~tos_runtime.marketfeed.ports"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tos_runtime.marketfeed.ports import ObservationIntake, RawObservation

__all__ = ["JournalError", "JsonLinesObservationJournal"]

_Refuse = Callable[[str], "JournalError"]

_REQUIRED_KEYS: frozenset[str] = frozenset(
    {"raw_event_id", "instrument", "as_of_ms", "fields", "source_id"}
)

_SCALAR_FIELD_TYPES: tuple[type, ...] = (bool, int, float, str)


class JournalError(Exception):
    """Raised when the observation journal is missing, unreadable, or carries a malformed line."""


@dataclass(frozen=True)
class JsonLinesObservationJournal:
    """A file-backed :class:`~tos_runtime.marketfeed.ports.ObservationIntake`."""

    path: Path

    def poll(
        self, *, instrument: str, after_as_of_ms: int | None
    ) -> Sequence[RawObservation]:
        """Return ``instrument``'s observations strictly newer than ``after_as_of_ms``."""
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


_conforms_to_observation_intake: type[ObservationIntake] = JsonLinesObservationJournal
