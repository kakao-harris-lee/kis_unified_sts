"""tos_runtime.venue.band_journal — the ``producer_journal`` band source (CP-3 band 원천 경로
변경, ``docs/plans/2026-10-15-tos-cp3-band-via-producer-plan.md`` §3.2/§3.3/§3.4).

**What this module is.** The LAST line of the band journal the ③ live-field producer's band
probe writes (``tools/tos_cp3/live_producer/band_probe.py`` → ``<session dir>/band.jsonl``),
validated into the same :class:`~tos_runtime.venue.band_source.BandObservation` the
``kis_quote_get`` reader produces, so the venue service, the snapshot bond, the evidence kind
``VENUE_BAND_OBSERVED`` and the re-issue rules are all UNCHANGED (plan §3.3).

**Why the band arrives through a file at all.** Plan §1 measured that the runtime cannot do the
GET itself on any shipped tree: the band reader factory reads the host seal off the ACTIVE
order scope's INSTANCE binding, and all three trees' active scope is
``SYNTHETIC_FUTURES_ORDER``, which has none (B1); and the token would have to come from custody
scopes the tenant session does not provision, which would put KIS credentials back into the
process the ③ plan §3.4 separation keeps credential-free (B2). The producer already holds the
REAL quotation key and already reaches the broker, so the band comes from the same REAL domain
as the prices the runtime judges — and this process still opens no socket and loads no secret.

**Trust is not widened by reading the producer's line** (plan §2). All fifteen price fields this
runtime judges are already the producer's assertion; the band is one more assertion from the
same party. What WOULD widen it is putting a key in the runtime (rejected alternative (b)) or
changing the order scope (rejected alternative (a)).

**THE LAST LINE ONLY, and never a fallback** (plan §3.3, review LOW-1). An unusable last line is
band ``None`` plus a reason — never "try the line before it". Falling back believes "a band that
was once valid" instead of "the band that is valid now", and on a reused session directory the
line before it is yesterday's. Absence, an unparseable tail, a non-UTF-8 byte, a tail too deeply
nested for ``json.loads``, a bound that will not scale and an I/O error are all ``None`` plus a
reason too (band plan 2026-10-08 §4.6: every failure is band ``None`` ⇒ kernel ``UNKNOWN`` ⇒
송신 0). ⚠ "Failure" means EVERY failure: ``VenueConstraintService._read_band`` calls this
reader with no ``try``, so anything that merely RAISES here is not band ``None`` — it is no
snapshot and no decision at all (PR #907 review MEDIUM-1).

**The line's own schema is defined HERE, deliberately duplicated** (plan §3.3). The runtime may
not import ``tools`` — firewall R1 (``tools/tos_firewall_check.py``: stdlib + ``tos_runtime.*``
only) — so the key set and the ``kind`` token cannot be imported from the writer's
``tools.tos_cp3.live_producer.band_line``. The duplication is bounded by a test that pins
key-set equality against a fixture copied byte-for-byte out of the writer's own output
(``tos/runtime/tests/venue/test_band_journal.py``), which is what makes "the same shape" a
measured claim rather than two files that happen to agree today.

**Three read-side clauses, each with its own concrete failing input** (plan §3.4):

* **G2 (trading date)** — a D-dated line read by a D+1 runtime. Structural half: the probe
  refuses to boot into a session directory that already holds a ``band.jsonl``. This is the
  read-side layer. ⚠ Its red proof is a READER unit test plus the FIRST snapshot after the read:
  the service's own trading-date bond runs at the head of ``snapshot()``, so a two-snapshot test
  cannot discriminate this clause from that one (plan §3.4's 가려진 절 note).
* **G3 (contract)** — a roll-day session directory reused across contracts, so an ``A05610``
  line sits under an ``A05611`` policy. Measured values make it SILENT rather than loud: both
  bands pass every §4.2 clause (``A05610`` 987.46/1159.18, ``A05611`` 990.48/1162.72, P-VL
  2026-10-08). ⚠ The line's ``instrument`` is the PRODUCER's request argument, not a broker
  echo — the response body carries no contract identifier (plan §3.4 review LOW-3) — so this
  binds "the producer's request" to "the runtime's policy", not "the broker said so".
* **C1 (source prefix)** — a CONFIG-CONSISTENCY rule, deliberately NOT counted as a guard (plan
  §3.4's C1 paragraph): today only one tool writes this file, and a hand-written line can copy
  the prefix, so no concrete fail-open input can be written for it. It stays because a line from
  an unapproved writer is an operations error on its face. The approved list has ONE home —
  ``tools.tos_cp3.bootproof_guard.APPROVED_REAL_PRODUCER_PREFIXES`` — which this package cannot
  import, so the RENDERER writes it into the policy as a value and a test pins
  "render output == that constant".

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos_runtime.*`` only —
no ``shared.*``, no ``tools.*``, no ``os.environ``.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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

#: The ``band_source.kind`` this module reads.
BAND_SOURCE_KIND_PRODUCER_JOURNAL = "producer_journal"

#: The band line's ``kind`` token. Versioned like every other CP-3 wire shape: a second shape
#: is ``cp3-band/2`` and this reader refuses the one it does not know rather than guessing
#: which keys it has.
BAND_JOURNAL_LINE_KIND = "cp3-band/1"

#: The EXACT key set of one ``cp3-band/1`` line — the writer's own
#: ``tools.tos_cp3.live_producer.band_line.BAND_KEY_ORDER``, as a set (this reader does not
#: care about wire ORDER; the writer pins that so the file is byte-stable).
#:
#: ⚠ **Equality, not containment.** A line that claims ``cp3-band/1`` while missing
#: ``raw_payload_digest`` would otherwise bind ``None`` into the snapshot's
#: ``critical_input_snapshot_digest`` stand-in — a band in force whose provenance field reads
#: exactly like "no band at all". Requiring the whole set is what makes every field below a
#: present value rather than a ``.get()`` that might be ``None``.
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


@dataclass(frozen=True)
class ProducerJournalBandSource(BandSourceConfig):
    """``kind: "producer_journal"`` — the band comes from the ③ producer's band journal.

    Only two leaves beyond the common ones, and the runtime READS both (module docstring's note
    on why a per-kind record exists at all).

    Attributes:
        band_journal_path: The ``band.jsonl`` this reader opens. A DEPLOYMENT value, not a
            policy decision (plan §3.2): it comes from the runner's
            ``TENANT_PRODUCER_SESSION_DIR`` and the renderer fills this slot from it. Named
            ``band_journal_path`` rather than ``journal_path`` so it cannot be confused with
            ``marketfeed.yaml::journal_path``, the PRICE journal (plan §3.2, review LOW-4).
        approved_source_prefixes: The producer names allowed to have written this line (C1).
            Written into the rendered policy from
            ``tools.tos_cp3.bootproof_guard.APPROVED_REAL_PRODUCER_PREFIXES``, because the
            firewall forbids this package from importing it.
    """

    band_journal_path: str
    approved_source_prefixes: tuple[str, ...]


def _matches_prefix(source_id: str, prefix: str) -> bool:
    """``source_id`` is ``prefix`` exactly, or ``prefix`` followed by ``/``.

    The same rule, spelled the same way, as
    ``tools.tos_cp3.bootproof_guard._matches_prefix`` — which this package may not import
    (module docstring). The delimiter is the whole point: a bare ``startswith`` approves
    ``tos-cp3-live-EVIL`` on an entry of ``tos-cp3-live``, because a producer name is a
    namespace and the separator is what makes the boundary real.
    """
    return source_id == prefix or source_id.startswith(prefix + "/")


class ProducerJournalBandReader:
    """Reads the band journal's last line once per call, validates it completely, and records
    one ``VENUE_BAND_OBSERVED`` row either way (module docstring; plan §3.3/§3.4)."""

    def __init__(
        self,
        *,
        band_source: ProducerJournalBandSource,
        monotonic: MonotonicSource,
        evidence_sink: EvidenceRecorder,
        trading_date_reader: Callable[[], str | None],
        tick_size: int | None,
    ) -> None:
        """Wire this reader's dependencies (all injected — no ambient state).

        Args:
            band_source: The policy's own declared source block.
            monotonic: The process's monotonic source — :attr:`BandObservation.as_of_ms` is
                the RUNTIME's reading taken immediately before the file is opened, the same
                rule the ``kis_quote_get`` reader applies to its own request instant. The
                LINE's ``as_of_ms`` is the producer's wall clock and goes to evidence as
                ``producer_as_of_ms``; the two are not comparable and are never mixed.
            evidence_sink: Records ``VENUE_BAND_OBSERVED``.
            trading_date_reader: The calendar owner's own KST trading-date reading — compared
                against the LINE's stamp (G2), never written onto the observation.
            tick_size: The ACTIVE policy's ``shape_constraints.tick_size`` — the grid both
                bounds must sit on. ``None`` refuses every read.
        """
        self._band_source = band_source
        self._monotonic = monotonic
        self._evidence = evidence_sink
        self._trading_date_reader = trading_date_reader
        self._tick_size = tick_size
        #: The previous SUCCESSFUL observation, for the same-trading-date narrowing flag
        #: (band plan 2026-10-08 §4.5 / §8 8).
        self._last_observation: BandObservation | None = None

    def read(self) -> BandObservation | None:
        """One last-line read + full validation. ``None`` on ANY failure, always with one
        ``VENUE_BAND_OBSERVED`` row naming the reason."""
        as_of_ms = self._monotonic.now_ms()
        trading_date = self._trading_date_reader()
        if trading_date is None:
            self._refuse("trading_date_unavailable")
            return None
        line = self._last_line()
        if line is None:
            return None  # _last_line already recorded its own refusal
        return self._validate(line, trading_date=trading_date, as_of_ms=as_of_ms)

    # -- the file ------------------------------------------------------------

    def _last_line(self) -> dict[str, Any] | None:
        """The last non-blank line of the journal, parsed, or ``None`` + a named refusal."""
        path = Path(self._band_source.band_journal_path)
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            self._refuse("journal_absent", detail=str(path))
            return None
        except UnicodeDecodeError as exc:
            # ⚠ A `ValueError`, NOT an `OSError` (PR #907 review MEDIUM-1): a byte like
            # `0xff` anywhere in the file makes `read_text` raise, and without this clause the
            # error leaves `read()` and surfaces inside `snapshot()`/`decide()` — which is
            # not band `None`, it is no answer at all.
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
            # ⚠ NOT a `ValueError` (PR #907 review MEDIUM-1): `json.loads` recurses once per
            # nesting level, so a tail of 100k open brackets exhausts the stack and the clause
            # above never sees it. Its own reason rather than `line_unparseable`, because the
            # operator's next move differs: a truncated line means the writer was interrupted,
            # this one means the file holds something the writer never wrote.
            self._refuse("line_too_deeply_nested", detail=f"{path}: json nesting")
            return None
        if not isinstance(parsed, dict):
            self._refuse("line_not_a_mapping", detail=type(parsed).__name__)
            return None
        return parsed

    # -- validation ----------------------------------------------------------

    def _line_refusal(
        self, line: dict[str, Any], *, trading_date: str
    ) -> BandRefusal | None:
        """The READ-SIDE clauses: why this line is not a usable band here, or ``None``.

        Order is deliberate: SHAPE first (``kind``, key set), then the three bonds that are
        about THIS session (contract, trading date, writer), then the one type check the
        evidence row depends on. A refusal past the shape clauses names a line that is
        well-formed and merely unusable here.

        Split from :meth:`_validate` at that seam — read-side clauses here, the shared numeric
        set and the record there — rather than registered as a size-budget exception:
        ``config/tos_size_budget.yaml``'s own header calls registration "면허가 아니라
        가시성", which is the right stance for inherited code and the wrong one for code
        written this week.
        """
        kind = line.get("kind")
        if kind != BAND_JOURNAL_LINE_KIND:
            return BandRefusal("line_kind_unknown", f"kind={kind!r}")
        if set(line) != BAND_JOURNAL_LINE_KEYS:
            missing = sorted(BAND_JOURNAL_LINE_KEYS - set(line))
            extra = sorted(set(line) - BAND_JOURNAL_LINE_KEYS)
            return BandRefusal("line_key_set", f"missing={missing} unexpected={extra}")
        # G3 (plan §3.4) — the line's contract against the policy's. The loader already bound
        # `band_source.instrument` to `scope.instruments`' sole element, so this is the LINE
        # against the whole configuration, not one config key against another.
        if line["instrument"] != self._band_source.instrument:
            return BandRefusal(
                "instrument_mismatch",
                f"line={line['instrument']!r} "
                f"policy={self._band_source.instrument!r}",
            )
        # G2 read side (plan §3.4) — the line's own stamp against this runtime's trading date.
        if line["trading_date"] != trading_date:
            return BandRefusal(
                "trading_date_mismatch",
                f"line={line['trading_date']!r} now={trading_date!r}",
            )
        # C1 (plan §3.4) — a config-consistency rule, not a guard.
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
            # The LINE's stamp, carried through unchanged (plan §3.3, review MEDIUM-1).
            #
            # ⚠ **Past the G2 clause above these two values are EQUAL**, so no test can tell
            # this expression from `trading_date=trading_date` while that clause stands —
            # measured 2026-10-16, the single mutation is GREEN. It is kept because it is the
            # INPUT to a second layer, and the layering is measured as a compound:
            #
            #   read-side clause + line's stamp  -> refused at the first snapshot
            #   read-side clause GONE, line's stamp -> accepted, then DROPPED by
            #       `service.py::_enforce_trading_date_bond` on the next snapshot
            #   read-side clause GONE and re-stamped -> accepted and NEVER dropped; the
            #       D-1 band stays in force all session (effective price_max 115918)
            #
            # The bond's own red proof is `tests/venue/test_service_band.py::
            # TestTradingDateBond`. Saying only "re-stamping would make the bond unable to
            # fire" — as plan §3.3 does — overstates it: the bond still catches a band held
            # ACROSS a trading date either way. What re-stamping destroys is the bond's
            # ability to catch a stale LINE read within one session.
            trading_date=line["trading_date"],
            # The PRODUCER's digest, of the bytes IT received. The evidence row says so.
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

    # -- evidence ------------------------------------------------------------

    def _narrowed_intraday(self, observation: BandObservation) -> bool:
        """A band that NARROWS within one trading date contradicts the monotonicity the
        "read once at boot is safe all day" argument rests on (band plan 2026-10-08 §4.5 /
        §2's 단서). Recorded, never acted on — a narrower band is the conservative direction;
        what matters is that the counter-observation leaves a row."""
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
                # Plan §3.3: the digest is the PRODUCER's claim about bytes this process never
                # saw, and the row says whose it is rather than letting a reader assume the
                # runtime hashed a response itself.
                "raw_payload_digest_source": "producer",
                "producer_source_id": source_id,
                "producer_as_of_ms": producer_as_of_ms,
                "continuity": observation.source_continuity_id,
                "band_digest": observation.record_digest,
                "symmetric_about_basis": observation.symmetric_about_basis,
                "narrowed_intraday": self._narrowed_intraday(observation),
                # Band plan 2026-10-08 §4.3 M3 / §4.5: the stand-in label travels with the row.
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
