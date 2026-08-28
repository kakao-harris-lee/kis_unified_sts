"""Per-symbol volatility reference — BOTH sides of the VolatilityFilter compare.

Why this module exists
----------------------
``VolatilityFilter`` rejects a signal when ``current_atr > atr_90th_percentile``.
Historically *both* sides of that comparison were broken: the threshold
(``RiskStateSnapshot.atr_90th_percentile``) defaulted to ``0.0`` and had no
production writer, and no daemon supplied a live ATR.  ``0.0 > 0.0`` is false,
so the filter passed everything and looked harmless.

The dangerous "obvious fix" was to wire only the live ATR: ``atr > 0.0`` is true
for *every* reading, so the filter would have rejected every entry and halted
all trading silently.  The whole point of this module is to make that state
**unrepresentable** rather than merely discouraged:

* one value object, :class:`VolatilityReference`, carries the current ATR *and*
  its threshold together — a caller cannot hand the filter half of a comparison;
* one publisher writes both fields in the same snapshot, from the same ATR
  series, so the two sides can never come from different conventions
  (a percentile of ``atr_partial`` values compared against a streaming-backend
  ATR would be a units mismatch, not merely a wiring gap);
* the value object **refuses** a non-positive threshold at construction, so the
  precise historical landmine — a ``0.0`` threshold with a live ATR — cannot be
  built even by a future caller who has forgotten this file exists;
* an absent threshold is expressed as ``atr_percentile=None`` (warmup), which
  the filter treats as "skip, loudly", never as "reject".

Fail-open polarity
------------------
A missing, stale, or corrupt reference makes the filter **skip** with a
throttled warning.  That is the polarity every sibling snapshot-reading filter
in this chain already established (``PortfolioMddFilter``, ``MarginGateFilter``,
``LeverageFilter`` all pass on absent/stale/corrupt), and it is the only safe
choice here: fail-closed would reproduce the "silent total trading halt" this
change exists to prevent.  The opposite polarity in this layer belongs to
``has_open_position_provider`` (fail-CLOSED) and is specific to the
duplicate-entry guard, where uncertainty means "a position may already exist".

Why ``normalize_atr`` is deliberately NOT applied
-------------------------------------------------
``shared/risk/primitives/atr_read.py::normalize_atr`` re-expresses a possibly
ratio-form ATR in absolute price units using a magnitude heuristic (a reading
below ~0.5 is assumed to be a ratio and multiplied by the reference price).
That heuristic exists for call sites that must reconcile readings from
*different* conventions.  Here both operands come from one series produced by
one accessor, so the series is self-consistent and needs no reconciliation —
and applying the heuristic would actively corrupt it: a genuinely small
absolute ATR (a low-priced KRX name, or a very quiet bar) would be
misclassified as a ratio and inflated by the price, poisoning the sample window
and the percentile derived from it.

Redis layout (DB 1, per project convention)
-------------------------------------------
``risk:volatility:samples:{asset_class}:{symbol}``
    LIST of ATR readings, newest first, trimmed to ``window_samples``.  This is
    an accumulation snapshot, so it uses the 48 h TTL convention and survives a
    publisher restart — without it a restart would blank the threshold for a
    full warmup period in the middle of a session.

``risk:volatility:reference:{asset_class}``
    HASH, field = symbol, value = the JSON-encoded :class:`VolatilityReference`.
    24 h operational TTL.

Both key prefixes and both TTLs are configuration (see
:class:`VolatilityReferenceSettings`), not literals in a call site.
"""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, model_validator

from shared.risk.atr_percentile import DEFAULT_ATR_PERCENTILE, atr_percentile

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")

#: Default Redis key prefixes.  The published hash and the sample lists are
#: separate keys because they have different lifetimes (24 h operational vs
#: 48 h accumulation) and different shapes (hash vs list).
DEFAULT_REFERENCE_KEY_PREFIX = "risk:volatility:reference"
DEFAULT_SAMPLES_KEY_PREFIX = "risk:volatility:samples"

#: Repo TTL conventions (CLAUDE.md): 24 h operational, 48 h accumulation.
DEFAULT_REFERENCE_TTL_SECONDS = 86_400
DEFAULT_SAMPLES_TTL_SECONDS = 172_800

#: Seconds between two "reference unavailable" warnings for the same symbol.
#: Shared by the reader below and by :class:`VolatilityFilter` — see
#: :class:`SymbolWarningThrottle` for why both must use one interval.
DEFAULT_WARN_INTERVAL_SECONDS: float = 300.0


def reference_key(asset_class: str, prefix: str = DEFAULT_REFERENCE_KEY_PREFIX) -> str:
    """Redis HASH key holding every symbol's published reference."""
    return f"{prefix}:{asset_class}"


def samples_key(
    asset_class: str, symbol: str, prefix: str = DEFAULT_SAMPLES_KEY_PREFIX
) -> str:
    """Redis LIST key holding one symbol's rolling ATR sample window."""
    return f"{prefix}:{asset_class}:{symbol}"


def _now_kst_naive() -> datetime:
    return datetime.now(KST).replace(tzinfo=None)


class SymbolWarningThrottle:
    """Per-symbol "warn at most once per interval" gate.

    Both the reader in this module and ``VolatilityFilter`` announce the same
    condition — "this symbol has no usable threshold" — one layer apart.  They
    share this gate rather than each keeping their own, because a throttle on
    only one of them is no throttle at all: an unthrottled provider warning
    fires per candidate and drowns out the filter's throttled one, which is the
    log-flood the filter's throttle exists to prevent.

    The gate must never degrade into silence: the first occurrence for a symbol
    always warns, and the warning re-fires once the interval elapses.  An
    operator who enabled the filter needs to keep seeing that it is passing
    blind, not see one line and assume the condition cleared.

    Args:
        interval_seconds: Minimum seconds between two warnings for one symbol.
        clock: "Now" provider; injectable for tests.
    """

    def __init__(
        self,
        interval_seconds: float = DEFAULT_WARN_INTERVAL_SECONDS,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._interval_seconds = interval_seconds
        self._clock = clock if clock is not None else _now_kst_naive
        self._last_warned_at: dict[str, datetime] = {}

    def should_warn(self, symbol: str) -> bool:
        """True when *symbol* is due a warning; records the emission if so."""
        now = self._clock()
        last = self._last_warned_at.get(symbol)
        if last is not None and (now - last).total_seconds() < self._interval_seconds:
            return False
        self._last_warned_at[symbol] = now
        return True


class VolatilityReferenceSettings(BaseModel):
    """Configuration for the volatility reference writer + reader.

    One block drives BOTH sides.  ``enabled`` is the single operator switch: it
    gates the publisher *and* the filter's provider wiring together, so an
    operator cannot arm one half of the comparison by editing one line.  The
    safe asymmetry is still tolerated — a running publisher with the filter
    unwired is inert, and a wired filter with no published data skips loudly.

    Defaults are deliberately inert (``enabled=False``): the stock chain is
    live production, so activation stays a separate operator decision.
    """

    enabled: bool = Field(
        default=False,
        description=(
            "Publish the per-symbol volatility reference AND wire it into the "
            "risk-filter chain. False (default) = writer dormant + filter inert "
            "(passes every signal), i.e. exactly today's behaviour."
        ),
    )
    percentile: float = Field(
        default=DEFAULT_ATR_PERCENTILE,
        gt=0.0,
        le=100.0,
        description=(
            "Upper-tail percentile of the ATR sample window used as the "
            "rejection threshold (90 = the historical atr_90th_percentile)."
        ),
    )
    window_samples: int = Field(
        default=240,
        gt=0,
        description=(
            "Rolling ATR sample window length. At the default 60 s publish "
            "cadence 240 samples ~= 4 h of session volatility."
        ),
    )
    min_samples: int = Field(
        default=60,
        gt=0,
        description=(
            "Samples required before a threshold is published at all. Below "
            "this the reference carries atr_percentile=null and the filter "
            "skips with a warning (warmup is permissive, never blocking)."
        ),
    )
    publish_interval_seconds: float = Field(
        default=60.0,
        gt=0.0,
        description=(
            "Minimum seconds between two publishes. The host service calls "
            "maybe_publish() every cycle; this throttles it independently of "
            "the host's own loop cadence."
        ),
    )
    stale_max_age_seconds: int = Field(
        default=900,
        gt=0,
        description=(
            "A reference whose asof_ts is missing / unparseable / older than "
            "this is treated as stale and the filter skips (positive-form "
            "staleness). Kept well above publish_interval_seconds so a single "
            "missed cycle does not blind the filter."
        ),
    )
    reference_key_prefix: str = Field(
        default=DEFAULT_REFERENCE_KEY_PREFIX,
        description="Redis HASH key prefix; the asset class is appended.",
    )
    samples_key_prefix: str = Field(
        default=DEFAULT_SAMPLES_KEY_PREFIX,
        description="Redis LIST key prefix; asset class + symbol are appended.",
    )
    reference_ttl_seconds: int = Field(
        default=DEFAULT_REFERENCE_TTL_SECONDS,
        gt=0,
        description="TTL on the published reference hash (24 h operational).",
    )
    samples_ttl_seconds: int = Field(
        default=DEFAULT_SAMPLES_TTL_SECONDS,
        gt=0,
        description="TTL on the ATR sample lists (48 h accumulation snapshot).",
    )

    @model_validator(mode="after")
    def _validate_window(self) -> VolatilityReferenceSettings:
        if self.min_samples > self.window_samples:
            raise ValueError(
                "min_samples must not exceed window_samples "
                f"(got min_samples={self.min_samples}, "
                f"window_samples={self.window_samples}); the threshold would "
                "never become available."
            )
        return self


@dataclass(frozen=True)
class VolatilityReference:
    """Both sides of the VolatilityFilter comparison for one symbol.

    Attributes:
        symbol: The instrument the reading belongs to.  ATR is in absolute
            price units, so a reference is only ever valid for its own symbol —
            comparing a KRW 500,000 stock's ATR against a KRW 5,000 stock's
            percentile would be meaningless, which is why this is per-symbol
            rather than the per-asset-class scalar it replaces.
        current_atr: The most recent ATR reading, from the same series the
            threshold was computed from.
        atr_percentile: The rejection threshold, or ``None`` during warmup
            (fewer than ``min_samples`` observations).  ``None`` means "no
            threshold known" → the filter skips.
        percentile: Which percentile ``atr_percentile`` is (observability).
        sample_size: How many samples the threshold was computed from.
        asof_ts: KST-naive ISO-8601 publish timestamp; drives staleness.

    Raises:
        ValueError: If ``atr_percentile`` is non-positive, or ``current_atr``
            is negative.  The non-positive threshold guard is the structural
            seal: ``atr_percentile=0.0`` is precisely the historical defect
            (every live ATR exceeds it → every entry rejected → all trading
            halted), so it is refused at construction rather than trusted to
            never be written.
    """

    symbol: str
    current_atr: float
    atr_percentile: float | None
    percentile: float
    sample_size: int
    asof_ts: str

    def __post_init__(self) -> None:
        if self.current_atr < 0.0:
            raise ValueError(
                f"current_atr must be >= 0, got {self.current_atr!r} "
                f"(symbol={self.symbol!r})"
            )
        if self.atr_percentile is not None and self.atr_percentile <= 0.0:
            raise ValueError(
                f"atr_percentile must be > 0 when present, got "
                f"{self.atr_percentile!r} (symbol={self.symbol!r}). A "
                "non-positive threshold makes every live ATR 'too volatile' "
                "and would reject every entry — use None to say 'no threshold "
                "known', which makes the filter skip instead."
            )

    @property
    def has_threshold(self) -> bool:
        """True when a usable rejection threshold is present."""
        return self.atr_percentile is not None

    def to_json(self) -> str:
        """Serialize for the Redis hash field."""
        return json.dumps(
            {
                "symbol": self.symbol,
                "current_atr": self.current_atr,
                "atr_percentile": self.atr_percentile,
                "percentile": self.percentile,
                "sample_size": self.sample_size,
                "asof_ts": self.asof_ts,
            },
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, raw: str | bytes) -> VolatilityReference:
        """Parse a published reference.

        Raises:
            ValueError: On malformed JSON, a non-object payload, missing or
                non-numeric fields, or a payload that violates the
                construction invariants above.  Callers resolve this to "no
                reference" (skip), never to a rejection.
        """
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"volatility reference is not valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(
                f"volatility reference must be a JSON object, got "
                f"{type(payload).__name__}"
            )

        threshold_raw = payload.get("atr_percentile")
        try:
            return cls(
                symbol=str(payload["symbol"]),
                current_atr=float(payload["current_atr"]),
                atr_percentile=(
                    None if threshold_raw is None else float(threshold_raw)
                ),
                percentile=float(payload.get("percentile", DEFAULT_ATR_PERCENTILE)),
                sample_size=int(payload.get("sample_size", 0)),
                asof_ts=str(payload.get("asof_ts", "")),
            )
        except (KeyError, TypeError) as exc:
            raise ValueError(f"volatility reference has a bad field: {exc}") from exc

    def is_stale(self, *, max_age_seconds: int, now: datetime | None = None) -> bool:
        """True when ``asof_ts`` is missing / unparseable / older than the bound.

        Positive-form staleness: an absent or malformed timestamp counts as
        stale, so a timestamp-less payload can never be mistaken for a fresh
        threshold.

        Deliberately a **pure predicate** — it does not log.  Announcing here
        would fire per candidate with no throttle and would drown out the
        throttled warning the reader emits for the same condition (which also
        quotes ``asof_ts``, so nothing is lost).
        """
        if not self.asof_ts:
            return True
        try:
            asof = datetime.fromisoformat(self.asof_ts)
        except ValueError:
            return True
        if asof.tzinfo is not None:
            asof = asof.astimezone(KST).replace(tzinfo=None)
        reference_now = now if now is not None else _now_kst_naive()
        return (reference_now - asof).total_seconds() > max_age_seconds


def _as_float(raw: Any) -> float | None:
    """Coerce a Redis LIST member to a finite float, or ``None``.

    NaN and +/-inf are rejected rather than passed through: an infinite sample
    would drag the percentile to infinity (blocking nothing) and a NaN sample
    would silently shrink the effective window.
    """
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="replace")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


class VolatilityReferencePublisher:
    """Sample per-symbol ATR, keep a causal window, publish both sides.

    The publisher never computes ATR itself: it reads whatever the host
    service's already-running indicator engine reports, so there is exactly one
    ATR calculation in the process and the sampled series and the published
    ``current_atr`` are by construction the same convention.

    The rolling window lives in Redis rather than in memory so a container
    restart mid-session does not blank the threshold for a full warmup period.

    Args:
        redis: Async Redis client (``redis.asyncio`` / fakeredis compatible).
        asset_class: ``"futures"`` or ``"stock"`` — selects the key namespace.
        settings: The configuration block (see
            :class:`VolatilityReferenceSettings`).
        atr_provider: Zero-arg callable returning ``{symbol: current_atr}``.
            Non-positive or non-finite readings are dropped (an unwarm engine
            reports ``0.0``); a symbol with no usable reading is simply not
            sampled this cycle.
        clock: KST-naive "now" provider; injectable for tests.
    """

    def __init__(
        self,
        *,
        redis: Any,
        asset_class: str,
        settings: VolatilityReferenceSettings,
        atr_provider: Callable[[], Mapping[str, float]],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._redis = redis
        self._asset_class = asset_class
        self._settings = settings
        self._atr_provider = atr_provider
        self._clock = clock if clock is not None else _now_kst_naive
        self._last_publish: datetime | None = None

    @property
    def reference_key(self) -> str:
        return reference_key(self._asset_class, self._settings.reference_key_prefix)

    async def maybe_publish(self) -> int:
        """Publish if ``publish_interval_seconds`` has elapsed; else do nothing.

        Host services call this once per loop iteration.  Throttling here (not
        in the host) keeps the cadence a configuration value rather than an
        accident of whichever loop the publisher was hung on.

        Returns:
            Number of symbols published this call (``0`` when throttled).
        """
        now = self._clock()
        if self._last_publish is not None:
            elapsed = (now - self._last_publish).total_seconds()
            # A negative elapsed means the wall clock stepped backwards (NTP
            # correction). The stored timestamp is then meaningless, and
            # honouring it would suppress publishing for the whole size of the
            # step — the reference would go stale and the filter would fall
            # back to skipping. That failure is safe but silent, and inert-by-
            # accident is precisely the defect class this module closes, so a
            # backwards step publishes immediately instead of waiting out a
            # phantom interval.
            if 0.0 <= elapsed < self._settings.publish_interval_seconds:
                return 0
        return await self.publish_once(now=now)

    async def publish_once(self, *, now: datetime | None = None) -> int:
        """Sample every symbol, update its window, and publish its reference.

        Best-effort by contract: any failure is logged and swallowed so a
        Redis hiccup can never take down the host service's own loop.  A cycle
        that publishes nothing leaves the previous reference in place until it
        goes stale, at which point the filter skips.

        Returns:
            Number of symbols whose reference was published.
        """
        moment = now if now is not None else self._clock()
        try:
            readings = dict(self._atr_provider())
        except Exception:
            logger.exception(
                "volatility reference: ATR provider failed; skipping cycle"
            )
            return 0

        published = 0
        for symbol, raw_atr in readings.items():
            try:
                if await self._publish_symbol(str(symbol), raw_atr, moment):
                    published += 1
            except Exception:
                logger.exception(
                    "volatility reference: publish failed for %s; continuing",
                    symbol,
                )

        # The throttle clock advances only on a cycle that actually published.
        # A cold engine (every reading 0.0) therefore keeps retrying at the
        # host's own cadence instead of silently waiting out an interval it
        # never used — the market open is exactly when the reference is most
        # worth establishing early.
        if published:
            self._last_publish = moment
            try:
                await self._redis.expire(
                    self.reference_key, self._settings.reference_ttl_seconds
                )
            except Exception:
                logger.exception(
                    "volatility reference: TTL refresh failed for %s",
                    self.reference_key,
                )
        return published

    async def _publish_symbol(
        self, symbol: str, raw_atr: Any, moment: datetime
    ) -> bool:
        """Append one sample and publish that symbol's reference.

        Returns ``False`` (no publish) when the reading is unusable — an
        indicator engine that is not yet warm reports ``0.0``, and sampling
        that would poison the percentile with a floor of zeros.
        """
        current_atr = _as_float(raw_atr)
        if current_atr is None or current_atr <= 0.0:
            return False

        settings = self._settings
        list_key = samples_key(self._asset_class, symbol, settings.samples_key_prefix)
        await self._redis.lpush(list_key, repr(current_atr))
        await self._redis.ltrim(list_key, 0, settings.window_samples - 1)
        await self._redis.expire(list_key, settings.samples_ttl_seconds)

        raw_window = await self._redis.lrange(list_key, 0, settings.window_samples - 1)
        window = [
            value
            for value in (_as_float(item) for item in (raw_window or []))
            if value is not None and value > 0.0
        ]

        threshold: float | None = None
        if len(window) >= settings.min_samples:
            threshold = atr_percentile(window, settings.percentile)

        reference = VolatilityReference(
            symbol=symbol,
            current_atr=current_atr,
            atr_percentile=threshold,
            percentile=settings.percentile,
            sample_size=len(window),
            asof_ts=moment.isoformat(),
        )
        await self._redis.hset(self.reference_key, symbol, reference.to_json())
        return True


def build_volatility_reference_provider(
    *,
    asset_class: str,
    settings: VolatilityReferenceSettings,
    redis_client: Any | None = None,
    clock: Callable[[], datetime] | None = None,
    warn_interval_seconds: float = DEFAULT_WARN_INTERVAL_SECONDS,
) -> Callable[[str], VolatilityReference | None]:
    """Build the filter-side reader for the published reference.

    ``RiskFilterLayer.evaluate`` is synchronous, so the reader uses a sync
    Redis client created lazily on first use — the identical pattern
    :class:`~shared.risk.filters.margin_gate.MarginGateFilter` and
    :class:`~shared.risk.filters.portfolio_mdd.PortfolioMddFilter` use.  It only
    ever reads; the publisher owns every key.

    Every failure mode — Redis down, absent field, corrupt JSON, stale
    timestamp — resolves to ``None``, which the filter treats as "skip, with a
    throttled warning".  See the module docstring for why fail-open is the
    correct polarity here.

    Args:
        asset_class: Key namespace to read (``"futures"`` / ``"stock"``).
        settings: Same config block the publisher uses, so reader and writer
            cannot drift onto different keys.
        redis_client: Pre-built sync client (tests / callers that already have
            one). ``None`` builds one lazily from the runtime Redis URL.
        clock: KST-naive "now" provider for the staleness comparison and the
            warning throttle.
        warn_interval_seconds: Per-symbol warning throttle interval. Defaults
            to the same constant :class:`VolatilityFilter` uses, so the two
            layers cannot announce at mismatched rates.

    Returns:
        ``provider(symbol) -> VolatilityReference | None``.
    """
    key = reference_key(asset_class, settings.reference_key_prefix)
    now_fn = clock if clock is not None else _now_kst_naive
    client: Any = redis_client
    # Same per-symbol throttle the filter uses, at the same interval. A dead
    # publisher makes both layers announce the same condition once per
    # candidate; leaving this layer unthrottled would flood the log and defeat
    # the filter's throttle from below.
    throttle = SymbolWarningThrottle(warn_interval_seconds, clock=now_fn)

    def _read(symbol: str) -> VolatilityReference | None:
        nonlocal client
        try:
            if client is None:
                import redis as redis_lib

                from shared.config.runtime_defaults import redis_url_from_env

                client = redis_lib.Redis.from_url(
                    redis_url_from_env(), decode_responses=True
                )
            raw = client.hget(key, symbol)
            if not raw:
                return None
            reference = VolatilityReference.from_json(raw)
        except Exception as exc:  # noqa: BLE001 — every failure means "no reference"
            if throttle.should_warn(symbol):
                logger.warning(
                    "volatility reference read failed for %s (%s): %s", symbol, key, exc
                )
            return None

        if reference.is_stale(
            max_age_seconds=settings.stale_max_age_seconds, now=now_fn()
        ):
            if throttle.should_warn(symbol):
                logger.warning(
                    "volatility reference for %s is stale (asof=%s); filter will skip",
                    symbol,
                    reference.asof_ts,
                )
            return None
        return reference

    return _read
