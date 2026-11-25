"""tos_runtime.venue.band_journal — the ``producer_journal`` band source (CP-3 band 원천 경로"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tos.venue import PriceBandTick

from tos_runtime.time.sources import MonotonicSource
from tos_runtime.transport.kis_mock.token import EvidenceRecorder
from tos_runtime.venue.band_source import (
    VENUE_BAND_OBSERVED_KIND,
    BandObservation,
    BandRefusal,
    BandSourceConfig,
    validate_band_values,
)

__all__ = [
    "BAND_JOURNAL_LINE_KEYS",
    "BAND_JOURNAL_LINE_KIND",
    "BAND_SOURCE_KIND_PRODUCER_JOURNAL",
    "ProducerJournalBandReader",
    "ProducerJournalBandSource",
]

BAND_SOURCE_KIND_PRODUCER_JOURNAL = "producer_journal"

BAND_JOURNAL_LINE_KIND = "cp3-band/1"

BAND_JOURNAL_LINE_KEYS: frozenset[str] = frozenset(
    {
        "kind",
        "source_id",
        "instrument",
        "trading_date",
        "tr_id",
        "upper",
        "lower",
        "basis",
        "raw_payload_digest",
        "producer_continuity_id",
        "as_of_ms",
    }
)

_SHA256_HEX = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class ProducerJournalBandSource(BandSourceConfig):
    """``kind: "producer_journal"`` — the band comes from the ③ producer's band journal."""

    band_journal_path: str
    approved_source_prefixes: tuple[str, ...]


def _matches_prefix(source_id: str, prefix: str) -> bool:
    """``source_id`` is ``prefix`` exactly, or ``prefix`` followed by ``/``."""
    return source_id == prefix or source_id.startswith(prefix + "/")


class ProducerJournalBandReader:
    """Reads the band journal's last line once per call, validates it completely, and records"""

    def __init__(
        self,
        *,
        band_source: ProducerJournalBandSource,
        monotonic: MonotonicSource,
        evidence_sink: EvidenceRecorder,
        trading_date_reader: Callable[[], str | None],
        tick_size: int | None,
        price_band_ticks: tuple[PriceBandTick, ...] | None = None,
    ) -> None:
        """Wire this reader's dependencies (all injected — no ambient state)."""
        self._band_source = band_source
        self._monotonic = monotonic
        self._evidence = evidence_sink
        self._trading_date_reader = trading_date_reader
        self._tick_size = tick_size
        self._price_band_ticks = price_band_ticks
        self._last_observation: BandObservation | None = None

    def read(self) -> BandObservation | None:
        """One last-line read + full validation. ``None`` on ANY failure, always with one"""
        as_of_ms = self._monotonic.now_ms()
        trading_date = self._trading_date_reader()
        if trading_date is None:
            self._refuse("trading_date_unavailable")
            return None
        line = self._last_line()
        if line is None:
            return None
        return self._validate(line, trading_date=trading_date, as_of_ms=as_of_ms)

    def _last_line(self) -> dict[str, Any] | None:
        """The last non-blank line of the journal, parsed, or ``None`` + a named refusal."""
        path = Path(self._band_source.band_journal_path)
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            self._refuse("journal_absent", detail=str(path))
            return None
        except UnicodeDecodeError as exc:
            self._refuse("journal_not_utf8", detail=f"{path}: {exc}")
            return None
        except OSError as exc:
            self._refuse("journal_io_error", detail=f"{path}: {exc}")
            return None
        lines = [line for line in text.splitlines() if line.strip()]
        if not lines:
            self._refuse("journal_empty", detail=str(path))
            return None
        try:
            parsed = json.loads(lines[-1])
        except ValueError as exc:
            self._refuse("line_unparseable", detail=str(exc))
            return None
        except RecursionError:
            self._refuse("line_too_deeply_nested", detail=f"{path}: json nesting")
            return None
        if not isinstance(parsed, dict):
            self._refuse("line_not_a_mapping", detail=type(parsed).__name__)
            return None
        return parsed

    def _line_refusal(
        self, line: dict[str, Any], *, trading_date: str
    ) -> BandRefusal | None:
        """The READ-SIDE clauses: why this line is not a usable band here, or ``None``."""
        kind = line.get("kind")
        if kind != BAND_JOURNAL_LINE_KIND:
            return BandRefusal("line_kind_unknown", f"kind={kind!r}")
        if set(line) != BAND_JOURNAL_LINE_KEYS:
            missing = sorted(BAND_JOURNAL_LINE_KEYS - set(line))
            extra = sorted(set(line) - BAND_JOURNAL_LINE_KEYS)
            return BandRefusal("line_key_set", f"missing={missing} unexpected={extra}")
        if line["instrument"] != self._band_source.instrument:
            return BandRefusal(
                "instrument_mismatch",
                f"line={line['instrument']!r} "
                f"policy={self._band_source.instrument!r}",
            )
        if line["trading_date"] != trading_date:
            return BandRefusal(
                "trading_date_mismatch",
                f"line={line['trading_date']!r} now={trading_date!r}",
            )
        source_id = line["source_id"]
        if not isinstance(source_id, str) or not any(
            _matches_prefix(source_id, prefix)
            for prefix in self._band_source.approved_source_prefixes
        ):
            return BandRefusal(
                "source_id_unapproved",
                f"source_id={source_id!r} approved="
                f"{list(self._band_source.approved_source_prefixes)!r}",
            )
        producer_as_of_ms = line["as_of_ms"]
        if isinstance(producer_as_of_ms, bool) or not isinstance(
            producer_as_of_ms, int
        ):
            return BandRefusal("producer_as_of_ms_not_an_int", f"{producer_as_of_ms!r}")
        digest = line["raw_payload_digest"]
        if not isinstance(digest, str) or _SHA256_HEX.fullmatch(digest) is None:
            return BandRefusal("raw_payload_digest_not_a_sha256_hex", f"{digest!r}")
        continuity = line["producer_continuity_id"]
        if not isinstance(continuity, str) or not continuity:
            return BandRefusal(
                "producer_continuity_id_not_a_nonempty_string", f"{continuity!r}"
            )
        return None

    def _validate(
        self, line: dict[str, Any], *, trading_date: str, as_of_ms: int
    ) -> BandObservation | None:
        """:meth:`_line_refusal`'s clauses, then band plan §4.2's shared validation set."""
        refusal = self._line_refusal(line, trading_date=trading_date)
        if refusal is not None:
            self._refuse(refusal.reason, detail=refusal.detail)
            return None
        source_id = line["source_id"]
        producer_as_of_ms = line["as_of_ms"]
        outcome = validate_band_values(
            lower_raw=line["lower"],
            upper_raw=line["upper"],
            basis_raw=line["basis"],
            price_scale=self._band_source.price_scale,
            tick_size=self._tick_size,
            price_band_ticks=self._price_band_ticks,
            lower_label="lower",
            upper_label="upper",
        )
        if isinstance(outcome, BandRefusal):
            self._refuse(outcome.reason, detail=outcome.detail)
            return None
        observation = BandObservation(
            instrument=self._band_source.instrument,
            price_min=outcome.price_min,
            price_max=outcome.price_max,
            trading_date=line["trading_date"],
            raw_payload_digest=line["raw_payload_digest"],
            source_continuity_id=line["producer_continuity_id"],
            as_of_ms=as_of_ms,
            basis=outcome.basis,
            symmetric_about_basis=outcome.symmetric_about_basis,
        )
        self._record_observed(
            observation, source_id=source_id, producer_as_of_ms=producer_as_of_ms
        )
        self._last_observation = observation
        return observation

    def _narrowed_intraday(self, observation: BandObservation) -> bool:
        """A band that NARROWS within one trading date contradicts the monotonicity the"""
        previous = self._last_observation
        if previous is None or previous.trading_date != observation.trading_date:
            return False
        return (
            observation.price_min > previous.price_min
            or observation.price_max < previous.price_max
        )

    def _record_observed(
        self,
        observation: BandObservation,
        *,
        source_id: str,
        producer_as_of_ms: int,
    ) -> None:
        self._evidence(
            VENUE_BAND_OBSERVED_KIND,
            {
                "outcome": "OBSERVED",
                "instrument": observation.instrument,
                "price_min": observation.price_min,
                "price_max": observation.price_max,
                "basis": observation.basis,
                "trading_date": observation.trading_date,
                "raw_payload_digest": observation.raw_payload_digest,
                "raw_payload_digest_source": "producer",
                "producer_source_id": source_id,
                "producer_as_of_ms": producer_as_of_ms,
                "continuity": observation.source_continuity_id,
                "band_digest": observation.record_digest,
                "symmetric_about_basis": observation.symmetric_about_basis,
                "narrowed_intraday": self._narrowed_intraday(observation),
                "critical_input_snapshot_digest_role": "stand-in",
            },
        )

    def _refuse(self, reason: str, *, detail: str | None = None) -> None:
        self._evidence(
            VENUE_BAND_OBSERVED_KIND,
            {
                "outcome": "REFUSED",
                "instrument": self._band_source.instrument,
                "reason": reason,
                "detail": detail,
            },
        )
        return None
