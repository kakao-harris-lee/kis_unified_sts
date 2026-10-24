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
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from tools.tos_cp3.produce_fields import DEFAULT_MIN_BARS_PER_DAY

#: ``quote_initial_cursor`` token: "the close of the day being fetched", from
#: the tenant calendar (:func:`tools.tos_cp3.live_producer.real_quotes.resolve_initial_cursor`).
QUOTE_CURSOR_SESSION_END = "session_end"


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
    ("market", str),
    ("open_anchor", str),
    ("contract_spec_block", str),
    ("quote_initial_cursor", str),
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
    ("band_max_response_bytes", int),
)

#: Keys read as a list of ints rather than a scalar.
_REQUIRED_INT_LISTS: tuple[str, ...] = ("calendar_covered_years",)

#: Keys that must be PRESENT but whose value may be ``null``. Present-and-null
#: is a statement ("this market has no front month"); an absent key is not.
_REQUIRED_NULLABLE_STR: tuple[str, ...] = ("front_month_product",)

#: Present for exactly the markets whose :attr:`MarketProfile.tick_ladder` is True,
#: absent for the rest (#929 review MEDIUM). The stock band probe compares the
#: broker's ``aspr_unit`` with the tick this file's ``price_band_ticks`` gives the
#: quoted price; futures has a flat tick and no such field to compare.
_MARKET_PATH_KEY = "venue_policy_yaml"


@dataclass(frozen=True)
class MarketProfile:
    """What the ``market`` key selects — protocol facts, not thresholds.

    The quotation TR / path / market-division code for each market live in
    :mod:`tools.tos_cp3.quote_client` next to the allowlist that gates them;
    this table holds only what the CONFIG layer must check or hand on.
    """

    #: The Parquet ``<root>/<asset_class>/minute/`` segment, and the
    #: ``tools.broker_probes.common.resolve_credentials`` asset name.
    asset_class: str
    #: The two REAL query secrets this market reads from ``env_file``.
    credential_keys: tuple[str, str]
    #: ``parser_env`` pins this market must carry.
    required_pins: tuple[str, ...]
    #: Whether the instrument rolls (a futures front month) — decides whether
    #: ``front_month_product`` must be set or must be ``null``.
    rolls: bool
    #: Whether the venue tick is a per-price ladder the band probe must check
    #: against the broker's ``aspr_unit`` — decides whether ``venue_policy_yaml``
    #: must be present.
    tick_ladder: bool = False


#: The two markets this producer serves. A stock symbol does not roll, reads
#: the STOCK query keys and has no futures hour-class parameter to pin.
MARKETS: dict[str, MarketProfile] = {
    "futures": MarketProfile(
        asset_class="futures",
        credential_keys=("KIS_FUTURES_APP_KEY", "KIS_FUTURES_APP_SECRET"),
        required_pins=("KIS_FUTURES_HOUR_CLS_CODE", "KIS_MINUTE_BAR_MIN_VOLUME"),
        rolls=True,
    ),
    "stock": MarketProfile(
        asset_class="stock",
        credential_keys=("KIS_STOCK_APP_KEY", "KIS_STOCK_APP_SECRET"),
        required_pins=("KIS_MINUTE_BAR_MIN_VOLUME",),
        rolls=False,
        tick_ladder=True,
    ),
}

#: The floor on ``request_timeout_s``. One second, because that is already
#: below any real KIS round trip (PR-1 measured the minute GET in the hundreds
#: of ms at best) and the band GET divides this number by four for its
#: per-phase inactivity guards. Checked here rather than clamped at the call
#: site: a clamp that raises a too-small value loosens the bound (review round
#: 2 item A).
MIN_REQUEST_TIMEOUT_S = 1.0

#: Floor on ``band_max_response_bytes``. 1 KiB: a real ``FHMIF10000000`` body
#: is a few hundred bytes, so anything under this refuses the normal response
#: and turns the cap into a permanent band outage.
MIN_BAND_RESPONSE_BYTES = 1024


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
    #: ``futures`` or ``stock`` — selects the quotation TR, the credential pair,
    #: the Parquet asset class and whether the instrument rolls (:data:`MARKETS`).
    market: str
    #: ``auto`` (the futures era rule of ``produce_fields.resolve_open_anchor``)
    #: or ``HH:MM``. A stock session opens at 09:00 and has no era cutover, so
    #: the stock config names its open; boot asserts it equals the calendar's
    #: session start.
    open_anchor: str
    #: The top-level block of ``execution_yaml`` the contract spec is read from
    #: (``futures_contract_spec`` / ``stock_contract_spec``).
    contract_spec_block: str
    #: ``FID_INPUT_HOUR_1`` of the first page of a day. Futures sends ``""``
    #: (latest); the stock TR requires a time, so the stock config names the
    #: session close — as :data:`QUOTE_CURSOR_SESSION_END`, which the real
    #: transport resolves per fetched day from the calendar's window on that
    #: day (issue #924: an exam day closes at a different time, and a literal
    #: ``153000`` would cut its last hour off a seed day and the target day).
    quote_initial_cursor: str
    #: The ``product`` argument of
    #: ``shared.instruments.futures.get_front_month_code``. It names each seed
    #: day's contract in the cross-contract seed (plan §3.2a) and is checked
    #: against ``--instrument`` at startup, so it is a setting rather than a
    #: literal: a producer pointed at the standard contract while the runner
    #: trades mini would otherwise splice against the wrong month.
    front_month_product: str | None
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
    #: Hard cap on the band response the producer-side transport will read
    #: before giving up (band plan v3, 2026-10-16). Codex's round-4 F2
    #: measurement is the reason: a 48 MiB body was hashed and parsed inside a
    #: 0.2 s budget, so the TIME bound alone never saw it. The band GET streams
    #: and stops at this many bytes. A real ``FHMIF10000000`` body is a few
    #: hundred bytes, so this is an "obviously wrong" line, not a tuning knob.
    band_max_response_bytes: int
    #: The tenant tree's ``venue_constraint_policy.yaml`` — its
    #: ``price_band_ticks`` ladder and ``_runtime.price_scale`` — for markets whose
    #: tick is a ladder (``stock``); ``None`` for the rest (:data:`_MARKET_PATH_KEY`).
    venue_policy_yaml: Path | None
    #: The two parser env values the producer PINS (plan §3.3 L9). Bar size and
    #: the drop rule must not change quietly with the environment.
    parser_env: tuple[tuple[str, str], ...]

    @property
    def profile(self) -> MarketProfile:
        return MARKETS[self.market]

    @property
    def asset_class(self) -> str:
        return self.profile.asset_class

    @property
    def transport(self) -> dict[str, Any]:
        """The ``cfg`` mapping :class:`tools.tos_cp3.quote_client.Quotes` reads."""
        cfg: dict[str, Any] = {
            "market": self.market,
            "initial_cursor": self.quote_initial_cursor,
            "attempts": self.attempts,
            "pace_s": self.pace_s,
            "retry_pause_s": self.retry_pause_s,
            "request_timeout_s": self.request_timeout_s,
            "max_pages": self.max_pages,
            "max_response_bytes": self.band_max_response_bytes,
        }
        pins = dict(self.parser_env)
        if "KIS_FUTURES_HOUR_CLS_CODE" in pins:
            cfg["hour_cls_code"] = pins["KIS_FUTURES_HOUR_CLS_CODE"]
        return cfg


def _resolve(repo_root: Path, value: str) -> Path:
    """Repo-relative paths resolve against the checkout; absolute ones stand."""
    candidate = Path(value).expanduser()
    return candidate if candidate.is_absolute() else repo_root / candidate


def _assert_market(path: Path, values: dict[str, Any]) -> None:
    """The ``market`` key and the keys whose meaning depends on it.

    Each refusal names an input that would otherwise run WRONG rather than
    fail: a stock config with a ``front_month_product`` would have the seed
    walk rename every past day's contract; a futures config without one has
    no rule for naming the month at all.
    """
    market = values["market"]
    if market not in MARKETS:
        raise LiveProducerRefused(
            f"{path}: market={market!r} is not one of {sorted(MARKETS)}"
        )
    product = values["front_month_product"]
    if MARKETS[market].rolls and not product:
        raise LiveProducerRefused(
            f"{path}: market={market!r} rolls, so front_month_product must name "
            "the product get_front_month_code is asked for"
        )
    if not MARKETS[market].rolls and product is not None:
        raise LiveProducerRefused(
            f"{path}: market={market!r} does not roll; front_month_product must "
            f"be null, not {product!r} — the seed walk would request every "
            "past day on a futures month instead of the symbol"
        )
    anchor = values["open_anchor"]
    if anchor != "auto":
        try:
            datetime.strptime(anchor, "%H:%M")
        except ValueError as exc:
            raise LiveProducerRefused(
                f"{path}: open_anchor={anchor!r} is neither 'auto' nor HH:MM"
            ) from exc
    elif market != "futures":
        raise LiveProducerRefused(
            f"{path}: open_anchor 'auto' is the FUTURES era rule (08:45 after "
            f"2026-06-28); market={market!r} must name its open as HH:MM"
        )


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
    if values["band_max_response_bytes"] < MIN_BAND_RESPONSE_BYTES:
        raise LiveProducerRefused(
            f"{path}: band_max_response_bytes={values['band_max_response_bytes']} "
            f"is below {MIN_BAND_RESPONSE_BYTES}. A real FHMIF10000000 body is a "
            "few hundred bytes, so a cap under that would refuse every real "
            "response and make the band permanently absent — a cap that denies "
            "the normal case is not a safety bound"
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

    known = (
        {name for name, _ in _REQUIRED}
        | set(_REQUIRED_INT_LISTS)
        | set(_REQUIRED_NULLABLE_STR)
        | {"parser_env", _MARKET_PATH_KEY}
    )
    unknown = sorted(set(data) - known)
    if unknown:
        raise LiveProducerRefused(
            f"{path}: unknown key(s) {unknown}. An ignored key is a setting the "
            "operator believes is in effect and is not"
        )
    missing = sorted(
        name
        for name in [n for n, _ in _REQUIRED]
        + list(_REQUIRED_INT_LISTS)
        + list(_REQUIRED_NULLABLE_STR)
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

    for name in _REQUIRED_NULLABLE_STR:
        values[name] = None if data[name] is None else str(data[name])

    parser_env = data.get("parser_env")
    if not isinstance(parser_env, dict) or not parser_env:
        raise LiveProducerRefused(f"{path}: parser_env must be a non-empty mapping")
    pins = tuple(sorted((str(k), str(v)) for k, v in parser_env.items()))
    _assert_market(path, values)
    for required_pin in MARKETS[values["market"]].required_pins:
        if required_pin not in dict(pins):
            raise LiveProducerRefused(
                f"{path}: parser_env must pin {required_pin} — plan §3.3 L9 "
                "makes bar size and the volume drop rule config, not ambient env"
            )

    _assert_coherent(path, values)
    ladder = MARKETS[values["market"]].tick_ladder
    venue_raw = data.get(_MARKET_PATH_KEY)
    if ladder and not isinstance(venue_raw, str):
        raise LiveProducerRefused(
            f"{path}: market={values['market']!r} has a per-price tick ladder, so "
            f"{_MARKET_PATH_KEY} must name the tree's venue_constraint_policy.yaml — "
            "the band probe checks the broker's aspr_unit against it"
        )
    if not ladder and _MARKET_PATH_KEY in data:
        raise LiveProducerRefused(
            f"{path}: market={values['market']!r} has a flat tick; "
            f"{_MARKET_PATH_KEY} must be absent (nothing reads it)"
        )
    return LiveProducerConfig(
        path=path,
        sha256=hashlib.sha256(raw_bytes).hexdigest(),
        env_file=_resolve(repo_root, values.pop("env_file")),
        token_cache_dir=_resolve(repo_root, values.pop("token_cache_dir")),
        strategy_yaml=_resolve(repo_root, values.pop("strategy_yaml")),
        calendar_yaml=_resolve(repo_root, values.pop("calendar_yaml")),
        execution_yaml=_resolve(repo_root, values.pop("execution_yaml")),
        parser_env=pins,
        venue_policy_yaml=(
            _resolve(repo_root, venue_raw) if isinstance(venue_raw, str) else None
        ),
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
    """Pull ONLY the market's two query secrets from the explicitly named file.

    Futures reads ``KIS_FUTURES_APP_KEY/SECRET``, stock reads
    ``KIS_STOCK_APP_KEY/SECRET`` (:data:`MARKETS`) — never both.
    Plan §3.4: nothing else from ``.env.real`` crosses into this process, and
    the runner/runtime environments never receive these two at all (PR-3 pins
    that). ``reader`` is
    :func:`shared.config.dotenv_guard.read_explicit_dotenv`, which refuses a
    relative path and does nothing at all in hermetic mode.
    """
    keys = config.profile.credential_keys
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
