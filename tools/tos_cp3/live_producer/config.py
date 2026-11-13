"""Every tunable of ③, read from one YAML file. Nothing below is hardcoded."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from tools.tos_cp3.produce_fields import DEFAULT_MIN_BARS_PER_DAY

QUOTE_CURSOR_SESSION_END = "session_end"


class LiveProducerRefused(RuntimeError):
    """The producer refused to start, or refused to write. Never routed around."""


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

_REQUIRED_INT_LISTS: tuple[str, ...] = ("calendar_covered_years",)

_REQUIRED_NULLABLE_STR: tuple[str, ...] = ("front_month_product",)

_MARKET_PATH_KEY = "venue_policy_yaml"


@dataclass(frozen=True)
class MarketProfile:
    """What the ``market`` key selects — protocol facts, not thresholds."""

    asset_class: str
    credential_keys: tuple[str, str]
    required_pins: tuple[str, ...]
    rolls: bool
    tick_ladder: bool = False


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

MIN_REQUEST_TIMEOUT_S = 1.0

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
    market: str
    open_anchor: str
    contract_spec_block: str
    quote_initial_cursor: str
    front_month_product: str | None
    first_poll_delay_s: float
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
    max_consecutive_fetch_error_minutes: int
    calendar_covered_years: tuple[int, ...]
    band_max_response_bytes: int
    venue_policy_yaml: Path | None
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
    """The ``market`` key and the keys whose meaning depends on it."""
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
    """Every refusal that reads MORE THAN ONE value, or a value against a"""
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
    """Refuse to start when the environment contradicts a pin, then apply it."""
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
    """Pull ONLY the market's two query secrets from the explicitly named file."""
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
