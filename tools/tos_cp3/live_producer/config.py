"""Every tunable of ③, read from one YAML file. Nothing below is hardcoded.

CLAUDE.md's non-negotiable rule: thresholds, schedules and feature gates belong
in YAML, not in branches. δ (1.8 s) and G (10 s) are **operator-confirmed,
2026-10-14**; the PR-1 run (evidence
``docs/broker-profiles/evidence/2026-10-12-cp3-pr1-minute-probe/README.md``
§1.4) only proposed them and explicitly refused to let them be written into
code ("PR-2 가 이 값을 config 로 받아야 하며, 이 문서는 코드에 박는 것을 승인하지
않는다"). Confirmation does not change where they live: the YAML carries both
values with their evidence basis, and nothing here defaults them.

An UNKNOWN key is refused rather than ignored. A silently-ignored key is how a
typo in ``missing_no_successor_timeout_s`` becomes "G is whatever the default
was" with nothing saying so.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from tools.tos_cp3.produce_fields import DEFAULT_MIN_BARS_PER_DAY


class LiveProducerRefused(RuntimeError):
    """The producer refused to start, or refused to write. Never routed around."""


#: Keys the YAML must carry, with the Python type each is read as. There is no
#: default for any of them: a default here is a value nobody reviewed.
_REQUIRED: tuple[tuple[str, type], ...] = (
    ("env_file", str),
    ("token_cache_dir", str),
    ("strategy_yaml", str),
    ("calendar_yaml", str),
    ("execution_yaml", str),
    ("calendar_session_id", str),
    ("calendar_session_phase", str),
    ("front_month_product", str),
    ("first_poll_delay_s", float),
    ("missing_no_successor_timeout_s", float),
    ("repoll_pace_s", float),
    ("request_timeout_s", float),
    ("attempts", int),
    ("retry_pause_s", float),
    ("pace_s", float),
    ("max_pages", int),
    ("min_bars_per_day", int),
    ("max_seed_calendar_days", int),
    ("max_consecutive_produce_errors", int),
    ("max_consecutive_fetch_error_minutes", int),
)

#: Keys read as a list of ints rather than a scalar.
_REQUIRED_INT_LISTS: tuple[str, ...] = ("calendar_covered_years",)

#: The floor on ``request_timeout_s``. One second, because that is already
#: below any real KIS round trip (PR-1 measured the minute GET in the hundreds
#: of ms at best) and the band GET divides this number by four for its
#: per-phase inactivity guards. Checked here rather than clamped at the call
#: site: a clamp that raises a too-small value loosens the bound (review round
#: 2 item A).
MIN_REQUEST_TIMEOUT_S = 1.0

#: Keys that may be an int or ``null``, and whose default is ``null``. The
#: no-default rule above is about values that CHANGE what the producer does;
#: ``band_reread_minutes`` null is "do the one read §3.1 allows and nothing
#: more", which is the whole behaviour of every session before this key
#: existed. Still refused if present and not a positive int: a 0 would be a
#: re-read every boundary, which is a rate-limit question nobody answered.
_OPTIONAL_POSITIVE_INTS: tuple[str, ...] = ("band_reread_minutes",)


@dataclass(frozen=True)
class LiveProducerConfig:
    """The resolved configuration, plus the digest of the file it came from."""

    path: Path
    sha256: str
    env_file: Path
    token_cache_dir: Path
    strategy_yaml: Path
    calendar_yaml: Path
    execution_yaml: Path
    calendar_session_id: str
    calendar_session_phase: str
    #: The ``product`` argument of
    #: ``shared.instruments.futures.get_front_month_code``. It names each seed
    #: day's contract in the cross-contract seed (plan §3.2a) and is checked
    #: against ``--instrument`` at startup, so it is a setting rather than a
    #: literal: a producer pointed at the standard contract while the runner
    #: trades mini would otherwise splice against the wrong month.
    front_month_product: str
    #: δ — the first poll happens at ``bar boundary + first_poll_delay_s``.
    first_poll_delay_s: float
    #: G — re-poll until ``boundary + G`` before calling the minute late.
    missing_no_successor_timeout_s: float
    repoll_pace_s: float
    request_timeout_s: float
    attempts: int
    retry_pause_s: float
    pace_s: float
    max_pages: int
    min_bars_per_day: int
    max_seed_calendar_days: int
    max_consecutive_produce_errors: int
    #: Plan §3.5's second give-up, added after PR #904 review round 1 measured
    #: that the first one could not see a dead FEED at all:
    #: ``consecutive_produce_errors`` counts only ``ProduceFieldsError``, so a
    #: revoked token failed every poll of every minute and the session still
    #: ended rc 0 (measured: ``fetch_error`` 324, ``published`` 0, rc 0).
    #:
    #: Counted in MINUTES — boundaries at which no poll succeeded — and not in
    #: failed polls, for two reasons. A poll count is a function of
    #: :attr:`repoll_pace_s`: halving the pace would halve the wall-clock time
    #: to trip, with no operator intent anywhere. And "the feed gave us nothing
    #: for N minutes" is the question an operator actually has.
    #:
    #: ⚠ It counts FETCH failures only, never "the poll worked and had no row
    #: for that minute" (``no_raw_row_for_minute``). The genesis session is the
    #: concrete input for that distinction: 12:39-13:08 was 30 consecutive
    #: minutes of exactly that shape — a real lunch lull, ``fetch_error: 0``
    #: all day — so a counter that folded the two would abort a clean session
    #: every day the market goes quiet for half an hour.
    max_consecutive_fetch_error_minutes: int
    #: Years the tenant calendar is declared to cover. Not inferred from its
    #: holiday dates (review L4) and cross-checked against the file at load.
    calendar_covered_years: tuple[int, ...]
    #: Band re-read cadence in minutes, or ``None`` for "read once". ⚠
    #: **MEASUREMENT ONLY** (band plan §3.1, review HIGH-2): the runtime reads
    #: the band at ``boot`` and ``phase_change`` only, and the tenant calendar
    #: declares a single ``CONTINUOUS 08:45-15:45`` phase, so a line appended
    #: intraday cannot reach a decision before the close. Its only use is
    #: leaving evidence of an intraday widening in ``band.jsonl``. Reflecting
    #: an intraday widening in a DECISION needs a new runtime read trigger plus
    #: its own red proof, and that is outside the band plan (§L L4).
    band_reread_minutes: int | None
    #: The two parser env values the producer PINS (plan §3.3 L9). Bar size and
    #: the drop rule must not change quietly with the environment.
    parser_env: tuple[tuple[str, str], ...]

    @property
    def transport(self) -> dict[str, Any]:
        """The ``cfg`` mapping :class:`tools.tos_cp3.quote_client.Quotes` reads."""
        return {
            "attempts": self.attempts,
            "pace_s": self.pace_s,
            "retry_pause_s": self.retry_pause_s,
            "request_timeout_s": self.request_timeout_s,
            "max_pages": self.max_pages,
            "hour_cls_code": dict(self.parser_env)["KIS_FUTURES_HOUR_CLS_CODE"],
        }


def _resolve(repo_root: Path, value: str) -> Path:
    """Repo-relative paths resolve against the checkout; absolute ones stand."""
    candidate = Path(value).expanduser()
    return candidate if candidate.is_absolute() else repo_root / candidate


def _optional_positive_ints(path: Path, data: Mapping[str, Any]) -> dict[str, Any]:
    """Read every :data:`_OPTIONAL_POSITIVE_INTS` key: a positive int, or None.

    Absent and explicit ``null`` mean the same thing — the documented default.
    A present value that is not a positive int is a REFUSAL rather than a
    coerced one: ``band_reread_minutes: 0`` reads as "re-read every boundary",
    which is a rate-limit decision nobody made, and ``true`` is an int in
    Python and would mean "every minute".
    """
    resolved: dict[str, Any] = {}
    for name in _OPTIONAL_POSITIVE_INTS:
        entry = data.get(name)
        if entry is None:
            resolved[name] = None
            continue
        if isinstance(entry, bool) or not isinstance(entry, int) or entry < 1:
            raise LiveProducerRefused(
                f"{path}: {name}={entry!r} must be a positive integer or null "
                "(null = read once, band plan §3.1)"
            )
        resolved[name] = entry
    return resolved


def _assert_coherent(path: Path, values: dict[str, Any]) -> None:
    """Every refusal that reads MORE THAN ONE value, or a value against a
    constant this repo owns elsewhere.

    Split out of :func:`load_config` when the ``request_timeout_s`` floor
    took that function past ``config/tos_size_budget.yaml``'s 100-line
    function cap (PR #906 review round 2). The seam is one the function
    already had: everything above it reads and types ONE key at a time,
    and everything here is a relationship between keys.
    """
    if values["missing_no_successor_timeout_s"] <= values["first_poll_delay_s"]:
        raise LiveProducerRefused(
            f"{path}: G={values['missing_no_successor_timeout_s']} must exceed "
            f"δ={values['first_poll_delay_s']}; otherwise the re-poll window is "
            "empty and δ becomes a single blocking wait, which the PR-1 evidence "
            "§1.4 explicitly refuses (δ 를 단독 대기 시간으로 쓰면 안 된다)"
        )
    if values["missing_no_successor_timeout_s"] >= 60:
        raise LiveProducerRefused(
            f"{path}: G={values['missing_no_successor_timeout_s']} would overlap "
            "the next minute boundary (evidence §1.4 upper constraint)"
        )
    if values["request_timeout_s"] < MIN_REQUEST_TIMEOUT_S:
        raise LiveProducerRefused(
            f"{path}: request_timeout_s={values['request_timeout_s']} is below "
            f"{MIN_REQUEST_TIMEOUT_S}s. The band GET divides it by four for "
            "httpx's per-phase inactivity guards, and the minute path hands it "
            "to the client whole; a sub-second budget makes both meaningless "
            "against a real REST round trip. This refusal replaces the "
            "`max(0.001, ...)` clamp that used to sit in `quote_client.band` — "
            "a floor there RAISED the phase limits for a tiny budget and so "
            "loosened the bound it looked like it tightened (review round 2 "
            "item A, Codex MEDIUM)"
        )
    if values["max_consecutive_produce_errors"] < 1:
        raise LiveProducerRefused(
            f"{path}: max_consecutive_produce_errors must be >= 1 (plan §3.5)"
        )
    if values["max_consecutive_fetch_error_minutes"] < 1:
        raise LiveProducerRefused(
            f"{path}: max_consecutive_fetch_error_minutes must be >= 1 — a 0 "
            "would refuse on the first failed poll of the day, and a single "
            "transport failure costs that poll, not the session (plan §3.5)"
        )
    if values["min_bars_per_day"] != DEFAULT_MIN_BARS_PER_DAY:
        raise LiveProducerRefused(
            f"{path}: min_bars_per_day={values['min_bars_per_day']} but B1a's "
            f"DEFAULT_MIN_BARS_PER_DAY is {DEFAULT_MIN_BARS_PER_DAY}. Plan §3.2 "
            "requires 「밀도 게이트를 B1a 와 같게」 — the gate decides which days "
            "enter the frame, so a producer running a different one would seed "
            "from a different set of sessions than the offline run it is "
            "compared against, and the B3 join would diverge for a reason that "
            "looks like a field defect. The key stays in config (CLAUDE.md: "
            "thresholds belong in YAML) but B1a's constant is the only source "
            "of truth for its value (review M4)"
        )


def load_config(path: Path, *, repo_root: Path) -> LiveProducerConfig:
    """Read and validate the producer's YAML, or refuse."""
    raw_bytes = path.read_bytes()
    data = yaml.safe_load(raw_bytes.decode("utf-8"))
    if not isinstance(data, dict):
        raise LiveProducerRefused(f"{path}: not a YAML mapping")

    known = {name for name, _ in _REQUIRED} | set(_REQUIRED_INT_LISTS)
    known |= set(_OPTIONAL_POSITIVE_INTS) | {"parser_env"}
    unknown = sorted(set(data) - known)
    if unknown:
        raise LiveProducerRefused(
            f"{path}: unknown key(s) {unknown}. An ignored key is a setting the "
            "operator believes is in effect and is not"
        )
    missing = sorted(
        name
        for name in [n for n, _ in _REQUIRED] + list(_REQUIRED_INT_LISTS)
        if name not in data
    )
    if missing:
        raise LiveProducerRefused(f"{path}: missing key(s) {missing}")

    values: dict[str, Any] = {}
    for name, kind in _REQUIRED:
        try:
            values[name] = kind(data[name])
        except (TypeError, ValueError) as exc:
            raise LiveProducerRefused(
                f"{path}: {name}={data[name]!r} is not a {kind.__name__}"
            ) from exc
    for name in _REQUIRED_INT_LISTS:
        entries = data[name]
        if not isinstance(entries, list) or not entries:
            raise LiveProducerRefused(f"{path}: {name} must be a non-empty list")
        try:
            values[name] = tuple(sorted({int(entry) for entry in entries}))
        except (TypeError, ValueError) as exc:
            raise LiveProducerRefused(
                f"{path}: {name}={entries!r} is not a list of ints"
            ) from exc

    values.update(_optional_positive_ints(path, data))
    parser_env = data.get("parser_env")
    if not isinstance(parser_env, dict) or not parser_env:
        raise LiveProducerRefused(f"{path}: parser_env must be a non-empty mapping")
    pins = tuple(sorted((str(k), str(v)) for k, v in parser_env.items()))
    for required_pin in ("KIS_FUTURES_HOUR_CLS_CODE", "KIS_MINUTE_BAR_MIN_VOLUME"):
        if required_pin not in dict(pins):
            raise LiveProducerRefused(
                f"{path}: parser_env must pin {required_pin} — plan §3.3 L9 "
                "makes bar size and the volume drop rule config, not ambient env"
            )

    _assert_coherent(path, values)
    return LiveProducerConfig(
        path=path,
        sha256=hashlib.sha256(raw_bytes).hexdigest(),
        env_file=_resolve(repo_root, values.pop("env_file")),
        token_cache_dir=_resolve(repo_root, values.pop("token_cache_dir")),
        strategy_yaml=_resolve(repo_root, values.pop("strategy_yaml")),
        calendar_yaml=_resolve(repo_root, values.pop("calendar_yaml")),
        execution_yaml=_resolve(repo_root, values.pop("execution_yaml")),
        parser_env=pins,
        **values,
    )


def assert_env_pins(
    config: LiveProducerConfig, environ: MutableMapping[str, str]
) -> None:
    """Refuse to start when the environment contradicts a pin, then apply it.

    An already-set, DIFFERENT value is the failure this guards: a shell with
    ``KIS_MINUTE_BAR_MIN_VOLUME=0`` would make ``parse_ohlcv`` keep the
    zero-volume rows the pinned run drops, so the producer's frame and B1a's
    would silently disagree bar for bar. Unset is fine — the pin is then simply
    applied (the same rule PR-1's probe used).
    """
    for key, expected in config.parser_env:
        actual = environ.get(key)
        if actual is not None and actual != expected:
            raise LiveProducerRefused(
                f"parser env pin mismatch: {key}={actual!r} in the environment, "
                f"{expected!r} in {config.path}"
            )
        environ[key] = expected


def read_query_credentials(
    config: LiveProducerConfig,
    *,
    reader: Any,
    environ: MutableMapping[str, str],
) -> tuple[str, ...]:
    """Pull ONLY the two futures query secrets from the explicitly named file.

    Plan §3.4: nothing else from ``.env.real`` crosses into this process, and
    the runner/runtime environments never receive these two at all (PR-3 pins
    that). ``reader`` is
    :func:`shared.config.dotenv_guard.read_explicit_dotenv`, which refuses a
    relative path and does nothing at all in hermetic mode.
    """
    keys = ("KIS_FUTURES_APP_KEY", "KIS_FUTURES_APP_SECRET")
    values: Mapping[str, str] = reader(config.env_file, keys=keys)
    for key in keys:
        value = values.get(key)
        if not value:
            raise LiveProducerRefused(
                f"{config.env_file} does not supply {key}; the producer reads no "
                "other credential source"
            )
        environ[key] = value
    return keys
