"""The band line's shape, and the two readers of it. Stdlib + ``yaml`` only.

Band plan ``docs/plans/2026-10-15-tos-cp3-band-via-producer-plan.md`` §3.2: the
venue band is a DAILY fact, so it goes in its own file beside the price journal
rather than into a price line. The price journal's contract is "one line a
minute, fifteen fields, consumed once per line" (③ plan §2 4) and
``critical_input_policy.yaml`` gives all fifteen ``max_age_ms: 800``; a daily
fact carried in that line would mix a field with different freshness meaning
into one CII policy (band plan §6).

**Why this module is separate from :mod:`~tools.tos_cp3.live_producer.band`.**
Two processes read a band line and only one of them writes: the producer
(through ``band``, which needs ``sinks`` and therefore ``produce_fields``,
pandas and the whole offline stack) and the RUNNER, which must decide whether a
band line for today exists before it boots the runtime. The runner's check runs
in a one-off interpreter inside a bash heredoc, and the test harness for that
runner stands up a throwaway checkout holding only the modules it copies in
(``tests/tools/test_cp3_bootproof.py::_runner_repo``). So the predicate lives
here, where its imports are the standard library plus ``yaml``, and both sides
call the same function instead of each spelling the rule out.

Firewall: legacy side (``tools/``). No ``tos`` / ``tos_runtime`` import.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date, datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

KST = ZoneInfo("Asia/Seoul")

#: The line's ``kind``. Versioned, like every other wire shape in CP-3: a
#: second shape gets ``cp3-band/2`` and the reader refuses the one it does not
#: know rather than guessing which keys it has.
BAND_LINE_KIND = "cp3-band/1"

#: The band journal's basename inside the producer session directory. The path
#: itself is a DEPLOYMENT value (band plan §3.2 — it comes from the runner's
#: ``TENANT_PRODUCER_SESSION_DIR`` and the renderer fills the runtime's slot
#: from it); only the basename is fixed, and it is fixed HERE so the producer,
#: the runner and the renderer cannot each pick their own.
BAND_JOURNAL_NAME = "band.jsonl"

#: Wire key order of one band line (band plan §3.2). Fixed so the file is
#: byte-stable, and passed to ``ObservationJournal`` rather than hardcoded
#: there: that class enforced the PRICE order, which is why PR-A generalises
#: it (review LOW-1).
BAND_KEY_ORDER: tuple[str, ...] = (
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
)

#: ``FHMIF10000000`` response field -> band line key. The three are copied as
#: STRINGS, exactly as they arrive (band plan §3.1): scale conversion, the tick
#: grid and the ordering checks are the runtime's existing validation set, in
#: one place (band plan §4.2).
BAND_PAYLOAD_FIELDS: tuple[tuple[str, str], ...] = (
    ("futs_mxpr", "upper"),
    ("futs_llam", "lower"),
    ("futs_sdpr", "basis"),
)

#: The response member the three fields live in. ⚠ The plan's §3.1 prose says
#: "``output``"; the MEASURED shape is ``output1`` — the official wrapper
#: returns ``output1``/``output2``/``output3`` for this TR
#: (``examples_llm/domestic_futureoption/inquire_price/inquire_price.py``) and
#: P-VL reads its five L1 price fields from ``output1``
#: (``tools/broker_probes/probes_venue_limits.py``, measured against the broker
#: on 2026-10-08). Reading ``output`` would never match, which is a band that
#: is permanently absent for a reason no log names.
BAND_PAYLOAD_MEMBER = "output1"


class BandLineError(RuntimeError):
    """A band payload or band line that cannot be used. Never routed around."""


def trading_date_text(day: date) -> str:
    """The producer's local KST calendar stamp for *day* (band plan §3.2).

    A LOCAL stamp, not a response field: ``FHMIF10000000`` carries no trading
    date, and the runtime binds the line's own ``trading_date`` rather than
    re-stamping it (band plan §3.3, review MEDIUM-1).
    """
    return day.strftime("%Y%m%d")


def band_values_from_payload(payload: Mapping[str, Any]) -> dict[str, str]:
    """The three band fields, as strings, or raise.

    Raises:
        BandLineError: the response member is missing, or any of the three
            fields is absent or empty. Plan §3.1 lists "필드 부재" as a band
            FAILURE: no line is written and ``band_fetch_failed`` is logged.
            Substituting a default here is the one fail-open this whole path
            is arranged to avoid — a wrong band believed.
    """
    member = payload.get(BAND_PAYLOAD_MEMBER)
    if not isinstance(member, Mapping):
        raise BandLineError(
            f"band response has no {BAND_PAYLOAD_MEMBER} mapping "
            f"(got {type(member).__name__})"
        )
    values: dict[str, str] = {}
    missing: list[str] = []
    for source, key in BAND_PAYLOAD_FIELDS:
        raw = member.get(source)
        text = "" if raw is None else str(raw).strip()
        if not text:
            missing.append(f"{source}={raw!r}")
        else:
            values[key] = text
    if missing:
        raise BandLineError(f"band response is missing {', '.join(missing)}")
    return values


def read_last_band_line(path: Path) -> dict[str, Any] | None:
    """The LAST line of *path*, parsed, or ``None``.

    The last one only — a reader never falls back to an earlier line (band plan
    §3.3, review LOW-1): falling back believes "a band that was once valid"
    instead of "the band that is valid now". Absence, an unparseable tail and
    an I/O error are all ``None``.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    try:
        parsed = json.loads(lines[-1])
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def reject_reason(
    line: Any, *, instrument: str, trading_date: str, open_ms: int
) -> str | None:
    """Why *line* is not a usable band for this session, or ``None``.

    Four clauses, and each one has a concrete input that makes it fire:

    * ``kind`` — a line of some other shape (a price line, a future
      ``cp3-band/2``) whose keys do not mean what this reader thinks.
    * ``instrument`` — the roll-day shape (band plan §3.4 G3): a session
      directory reused across a roll, so an ``A05610`` line sits under an
      ``A05611`` policy. The measured values make it silent rather than loud —
      ``A05610`` 987.46/1159.18 against ``A05611`` 990.48/1162.72 (P-VL
      2026-10-08) — so without this clause the session trades admissibly
      against another contract's band.
    * ``trading_date`` — yesterday's line left in a reused session directory
      (G2 ②). The producer's own ``refuse_if_journal_exists`` is the structural
      half; this is the read-side layer.
    * ``as_of_ms`` — a response taken BEFORE the open, which is the hour band
      plan §4.4a's residual risk ("the broker hands out yesterday's band") is
      largest. The producer refuses to fetch before the open; this says the
      runner does not have to trust that it did.
    """
    if not isinstance(line, Mapping):
        return "not_a_mapping"
    if line.get("kind") != BAND_LINE_KIND:
        return f"kind={line.get('kind')!r} is not {BAND_LINE_KIND!r}"
    if line.get("instrument") != instrument:
        return f"instrument={line.get('instrument')!r} is not {instrument!r}"
    if line.get("trading_date") != trading_date:
        return f"trading_date={line.get('trading_date')!r} is not {trading_date!r}"
    as_of_ms = line.get("as_of_ms")
    if not isinstance(as_of_ms, int) or isinstance(as_of_ms, bool):
        return f"as_of_ms={as_of_ms!r} is not an integer"
    if as_of_ms < open_ms:
        return f"as_of_ms={as_of_ms} is before the open ({open_ms})"
    return None


def session_open_ms(
    producer_config: Path, *, repo_root: Path, day: date
) -> tuple[int, str]:
    """``(epoch ms of *day*'s session open, that day's trading-date stamp)``.

    The open comes from the SAME settings the producer reads — its config's
    ``calendar_yaml`` / ``calendar_session_id`` / ``calendar_session_phase``,
    and that calendar's own window — so the runner is a second READER of one
    source of truth rather than a second source of it. ③ plan §3.5 is explicit
    that the runner must not grow its own copy of the session window; a literal
    ``08:45`` here would be exactly that.

    Read with ``yaml.safe_load`` rather than through
    :func:`~tools.tos_cp3.live_producer.config.load_config` on purpose: this
    function is imported by the runner's wait script and by the throwaway
    checkout the runner tests build, neither of which can carry the offline
    stack ``config`` pulls in. ``tests/tools/test_cp3_live_producer.py`` pins
    the answer against ``calendar.load_runtime_calendar``'s own window.

    Raises:
        BandLineError: the config or the calendar does not name exactly one
            window for that session id and phase.
    """
    data = yaml.safe_load(producer_config.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise BandLineError(f"{producer_config}: not a YAML mapping")
    try:
        calendar_value = str(data["calendar_yaml"])
        session_id = str(data["calendar_session_id"])
        phase = str(data["calendar_session_phase"])
    except KeyError as exc:
        raise BandLineError(
            f"{producer_config} does not carry {exc.args[0]!r}, so the session "
            "open cannot be read from the producer's own settings"
        ) from exc

    candidate = Path(calendar_value).expanduser()
    calendar_path = candidate if candidate.is_absolute() else repo_root / candidate
    calendar = yaml.safe_load(calendar_path.read_text(encoding="utf-8"))
    if not isinstance(calendar, dict):
        raise BandLineError(f"{calendar_path}: not a YAML mapping")
    sessions = calendar.get("sessions")
    entries = sessions.get(session_id) if isinstance(sessions, dict) else None
    windows = [
        entry
        for entry in (entries or [])
        if isinstance(entry, dict) and str(entry.get("phase")) == phase
    ]
    if len(windows) != 1:
        raise BandLineError(
            f"{calendar_path}: session {session_id!r} has {len(windows)} "
            f"{phase!r} window(s); exactly one is required"
        )
    hour_text, _, minute_text = str(windows[0]["start"]).partition(":")
    opened = datetime.combine(day, time(int(hour_text), int(minute_text)), tzinfo=KST)
    return int(opened.timestamp() * 1000), trading_date_text(day)
