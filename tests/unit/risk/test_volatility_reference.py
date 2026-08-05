"""shared.risk.volatility_reference — the atomic volatility reference.

Hermetic: fakeredis (one shared server so the async publisher and the sync
reader really talk to each other), injected KST-naive clocks, no network.

What this file defends
----------------------
``VolatilityFilter`` used to take its two operands from two independently
wirable places: a ``current_atr_provider`` and
``RiskStateSnapshot.atr_90th_percentile``, the latter defaulting to ``0.0``
with no production writer.  Wiring only the ATR side made the comparison
``atr > 0.0`` — true for every reading — which would have rejected every entry
and halted all trading without a single error.

This module's job is to make that state **unrepresentable**, so the tests are
about impossibility as much as behaviour:

* a reference cannot be constructed with a non-positive threshold (the seal);
* "no threshold yet" is a distinct value (``None``) that means skip, not block;
* publisher and reader share one settings object, so they cannot drift onto
  different keys;
* every read failure resolves to "no reference" → the filter skips.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

import fakeredis
import fakeredis.aioredis
import pytest

from shared.risk.atr_percentile import atr_percentile
from shared.risk.volatility_reference import (
    VolatilityReference,
    VolatilityReferencePublisher,
    VolatilityReferenceSettings,
    build_volatility_reference_provider,
    reference_key,
    samples_key,
)

_ASSET = "stock"
_SYMBOL = "005930"
_NOW = datetime(2026, 8, 5, 10, 30, 0)

#: Deliberately hardcoded rather than derived from the key builders: an
#: independent anchor cannot drift in lockstep with the code it pins.
_EXPECTED_REFERENCE_KEY = "risk:volatility:reference:stock"
_EXPECTED_SAMPLES_KEY = "risk:volatility:samples:stock:005930"

_READER_LOGGER = "shared.risk.volatility_reference"


class _RaisingRedis:
    """Sync client whose every read fails (Redis outage)."""

    def hget(self, *_args, **_kwargs):
        raise RuntimeError("redis down")


def _settings(**overrides) -> VolatilityReferenceSettings:
    base = {
        "enabled": True,
        "percentile": 90.0,
        "window_samples": 10,
        "min_samples": 4,
        "publish_interval_seconds": 60.0,
        "stale_max_age_seconds": 900,
    }
    base.update(overrides)
    return VolatilityReferenceSettings(**base)


@pytest.fixture()
def server() -> fakeredis.FakeServer:
    return fakeredis.FakeServer()


@pytest.fixture()
def async_redis(server):
    return fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)


@pytest.fixture()
def sync_redis(server):
    return fakeredis.FakeRedis(server=server, decode_responses=True)


def _reference(**overrides) -> VolatilityReference:
    base = {
        "symbol": _SYMBOL,
        "current_atr": 3.0,
        "atr_percentile": 5.0,
        "percentile": 90.0,
        "sample_size": 10,
        "asof_ts": _NOW.isoformat(),
    }
    base.update(overrides)
    return VolatilityReference(**base)


# ---------------------------------------------------------------------------
# The seal: a zero / negative threshold is unconstructable
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("threshold", [0.0, -0.0, -1.0, -1e-9])
def test_non_positive_threshold_is_refused_at_construction(threshold) -> None:
    """The exact historical landmine cannot be built.

    ``atr_percentile=0.0`` combined with a live ATR is what rejects every
    entry.  Refusing it here means no future caller — publisher, test fixture,
    or hand-rolled provider — can reintroduce it, regardless of what they read
    about the old ``atr_90th_percentile`` field.
    """
    with pytest.raises(ValueError, match="atr_percentile must be > 0"):
        _reference(atr_percentile=threshold)


def test_absent_threshold_is_allowed_and_is_not_zero() -> None:
    """``None`` is the sanctioned way to say 'no threshold known'."""
    reference = _reference(atr_percentile=None)
    assert reference.atr_percentile is None
    assert reference.has_threshold is False


def test_present_threshold_reports_has_threshold() -> None:
    assert _reference(atr_percentile=5.0).has_threshold is True


def test_negative_current_atr_is_refused() -> None:
    with pytest.raises(ValueError, match="current_atr must be"):
        _reference(current_atr=-0.5)


def test_zero_current_atr_is_allowed() -> None:
    """A zero ATR is a legitimate (if unwarm) reading — it just never rejects."""
    assert _reference(current_atr=0.0).current_atr == 0.0


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def test_json_round_trip_preserves_both_sides() -> None:
    original = _reference()
    restored = VolatilityReference.from_json(original.to_json())
    assert restored == original


def test_json_round_trip_preserves_absent_threshold() -> None:
    original = _reference(atr_percentile=None)
    assert VolatilityReference.from_json(original.to_json()).atr_percentile is None


def test_from_json_accepts_bytes() -> None:
    original = _reference()
    assert VolatilityReference.from_json(original.to_json().encode()) == original


@pytest.mark.parametrize(
    ("payload", "label"),
    [
        ("not json at all", "garbage"),
        ("[1, 2, 3]", "non-object"),
        ('{"current_atr": 1.0}', "missing symbol"),
        ('{"symbol": "X", "current_atr": "abc"}', "non-numeric atr"),
        (
            '{"symbol": "X", "current_atr": 1.0, "atr_percentile": 0.0}',
            "zero threshold",
        ),
    ],
)
def test_corrupt_payload_raises_rather_than_yielding_a_bad_reference(
    payload, label
) -> None:
    """Corruption must never decode into a usable-looking reference.

    The zero-threshold row matters most: a poisoned or truncated payload that
    happens to carry ``atr_percentile: 0`` must not sail through parsing into
    a filter that then blocks everything.
    """
    with pytest.raises(ValueError):
        VolatilityReference.from_json(payload)


# ---------------------------------------------------------------------------
# Staleness (positive form: unknown counts as stale)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("age_seconds", [0, 60, 899, 900])
def test_reference_within_the_bound_is_fresh(age_seconds) -> None:
    reference = _reference(asof_ts=_NOW.isoformat())
    assert not reference.is_stale(
        max_age_seconds=900, now=_NOW + timedelta(seconds=age_seconds)
    )


@pytest.mark.parametrize("age_seconds", [901, 3600])
def test_reference_past_the_bound_is_stale(age_seconds) -> None:
    reference = _reference(asof_ts=_NOW.isoformat())
    assert reference.is_stale(
        max_age_seconds=900, now=_NOW + timedelta(seconds=age_seconds)
    )


@pytest.mark.parametrize("asof", ["", "not-a-timestamp"])
def test_missing_or_unparseable_asof_is_stale(asof) -> None:
    """Positive-form staleness: an unknown age is never trusted as fresh."""
    assert _reference(asof_ts=asof).is_stale(max_age_seconds=900, now=_NOW)


def test_tz_aware_asof_is_converted_to_kst_before_comparison() -> None:
    from zoneinfo import ZoneInfo

    aware = datetime(2026, 8, 5, 10, 30, tzinfo=ZoneInfo("Asia/Seoul"))
    reference = _reference(asof_ts=aware.isoformat())
    assert not reference.is_stale(max_age_seconds=900, now=_NOW + timedelta(seconds=10))


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def test_settings_default_to_inert() -> None:
    """The default must not change any live chain's behaviour."""
    assert VolatilityReferenceSettings().enabled is False


def test_min_samples_above_window_is_rejected() -> None:
    """A threshold that can never be reached is a misconfiguration, not a mode."""
    with pytest.raises(ValueError, match="min_samples"):
        VolatilityReferenceSettings(window_samples=10, min_samples=11)


def test_key_builders_match_the_documented_layout() -> None:
    settings = _settings()
    assert reference_key(_ASSET, settings.reference_key_prefix) == (
        _EXPECTED_REFERENCE_KEY
    )
    assert samples_key(_ASSET, _SYMBOL, settings.samples_key_prefix) == (
        _EXPECTED_SAMPLES_KEY
    )


# ---------------------------------------------------------------------------
# Publisher
# ---------------------------------------------------------------------------


def _publisher(async_redis, settings, readings_sequence, clock_times):
    """Publisher whose ATR readings and clock are driven by fixed sequences."""
    readings = iter(readings_sequence)
    times = iter(clock_times)
    return VolatilityReferencePublisher(
        redis=async_redis,
        asset_class=_ASSET,
        settings=settings,
        atr_provider=lambda: next(readings),
        clock=lambda: next(times),
    )


@pytest.mark.asyncio
async def test_warmup_publishes_the_current_atr_but_no_threshold(
    async_redis,
) -> None:
    """Below ``min_samples`` the reference carries atr_percentile=None.

    This is the state a freshly-enabled deployment sits in.  It must publish a
    reference (so the filter can tell "warming up" from "publisher dead") while
    withholding a threshold, because any threshold derived from 2 samples would
    be noise that blocks real entries.
    """
    settings = _settings(window_samples=10, min_samples=4)
    publisher = _publisher(
        async_redis,
        settings,
        [{_SYMBOL: 3.0}, {_SYMBOL: 3.5}],
        [_NOW, _NOW],
    )

    await publisher.publish_once()
    await publisher.publish_once()

    raw = await async_redis.hget(_EXPECTED_REFERENCE_KEY, _SYMBOL)
    reference = VolatilityReference.from_json(raw)
    assert reference.atr_percentile is None
    assert reference.has_threshold is False
    assert reference.current_atr == pytest.approx(3.5)
    assert reference.sample_size == 2


@pytest.mark.asyncio
async def test_threshold_appears_once_min_samples_is_reached(async_redis) -> None:
    """At/after ``min_samples`` the published threshold is the shared percentile.

    Pins the DRY link: the publisher's threshold is exactly
    ``atr_percentile(window, percentile)``, the same helper the backtest
    reference uses — not a second, independently drifting computation.
    """
    settings = _settings(window_samples=10, min_samples=4, percentile=90.0)
    series = [1.0, 2.0, 3.0, 8.0]
    publisher = _publisher(
        async_redis,
        settings,
        [{_SYMBOL: value} for value in series],
        [_NOW] * len(series),
    )

    for _ in series:
        await publisher.publish_once()

    reference = VolatilityReference.from_json(
        await async_redis.hget(_EXPECTED_REFERENCE_KEY, _SYMBOL)
    )
    assert reference.sample_size == 4
    assert reference.atr_percentile == pytest.approx(atr_percentile(series, 90.0))
    assert reference.current_atr == pytest.approx(8.0)


@pytest.mark.asyncio
async def test_sample_window_is_trimmed_to_window_samples(async_redis) -> None:
    """The window is bounded, so the reference tracks *recent* volatility."""
    settings = _settings(window_samples=5, min_samples=2)
    series = [float(i) for i in range(1, 13)]
    publisher = _publisher(
        async_redis,
        settings,
        [{_SYMBOL: value} for value in series],
        [_NOW] * len(series),
    )
    for _ in series:
        await publisher.publish_once()

    stored = await async_redis.lrange(_EXPECTED_SAMPLES_KEY, 0, -1)
    assert len(stored) == 5
    # Newest first (LPUSH), so the window is the last five readings.
    assert [float(v) for v in stored] == [12.0, 11.0, 10.0, 9.0, 8.0]

    reference = VolatilityReference.from_json(
        await async_redis.hget(_EXPECTED_REFERENCE_KEY, _SYMBOL)
    )
    assert reference.sample_size == 5
    assert reference.atr_percentile == pytest.approx(
        atr_percentile([8.0, 9.0, 10.0, 11.0, 12.0], 90.0)
    )


@pytest.mark.asyncio
async def test_both_keys_get_their_configured_ttl(async_redis) -> None:
    """No untethered keys: 24 h operational hash, 48 h accumulation list."""
    settings = _settings(reference_ttl_seconds=86_400, samples_ttl_seconds=172_800)
    publisher = _publisher(async_redis, settings, [{_SYMBOL: 3.0}], [_NOW])
    await publisher.publish_once()

    assert 0 < await async_redis.ttl(_EXPECTED_REFERENCE_KEY) <= 86_400
    assert 86_400 < await async_redis.ttl(_EXPECTED_SAMPLES_KEY) <= 172_800


@pytest.mark.asyncio
async def test_unwarm_zero_atr_is_not_sampled(async_redis) -> None:
    """A cold engine reports 0.0; sampling it would depress the percentile.

    Worse, a window of zeros would produce a near-zero threshold, i.e. the very
    "reject everything" state this design exists to prevent — so the zero
    reading is dropped rather than recorded.
    """
    settings = _settings(min_samples=1)
    publisher = _publisher(
        async_redis,
        settings,
        [{_SYMBOL: 0.0}, {_SYMBOL: -1.0}, {"OTHER": float("nan")}],
        [_NOW, _NOW, _NOW],
    )

    assert await publisher.publish_once() == 0
    assert await publisher.publish_once() == 0
    assert await publisher.publish_once() == 0
    assert await async_redis.exists(_EXPECTED_REFERENCE_KEY) == 0
    assert await async_redis.exists(_EXPECTED_SAMPLES_KEY) == 0


@pytest.mark.asyncio
async def test_publish_is_throttled_to_the_configured_interval(async_redis) -> None:
    """Cadence is configuration, not an accident of the host loop's period."""
    settings = _settings(publish_interval_seconds=60.0, min_samples=1)
    publisher = _publisher(
        async_redis,
        settings,
        [{_SYMBOL: 3.0}, {_SYMBOL: 4.0}, {_SYMBOL: 5.0}],
        [_NOW, _NOW + timedelta(seconds=30), _NOW + timedelta(seconds=61)],
    )

    assert await publisher.maybe_publish() == 1  # first call always publishes
    assert await publisher.maybe_publish() == 0  # 30 s < 60 s → throttled
    assert await publisher.maybe_publish() == 1  # 61 s ≥ 60 s → publishes

    # A throttled call must not consume an ATR reading either: only the two
    # publishes sampled, so the window holds the 1st and 2nd readings.
    stored = await async_redis.lrange(_EXPECTED_SAMPLES_KEY, 0, -1)
    assert [float(v) for v in stored] == [4.0, 3.0]


class _ExplodingAtr:
    """An ATR reading whose coercion raises something ``_as_float`` won't catch."""

    def __float__(self) -> float:
        raise RuntimeError("indicator engine corrupted")


@pytest.mark.asyncio
async def test_a_raising_symbol_does_not_stop_the_others(async_redis) -> None:
    """Publishing is isolated per symbol; one bad reading is not an outage.

    With a 40-symbol stock universe, letting one poisoned reading abort the
    cycle would blind the volatility gate for every other symbol — and the
    filter's fail-open polarity would turn that into a silently ungated book.
    """
    settings = _settings(min_samples=1)
    publisher = _publisher(
        async_redis,
        settings,
        [{"BAD": _ExplodingAtr(), _SYMBOL: 3.0}],
        [_NOW],
    )
    assert await publisher.publish_once() == 1
    assert await async_redis.hget(_EXPECTED_REFERENCE_KEY, _SYMBOL)
    assert await async_redis.hget(_EXPECTED_REFERENCE_KEY, "BAD") is None


@pytest.mark.asyncio
async def test_a_raising_atr_provider_is_swallowed(async_redis) -> None:
    """The host service's loop must survive an indicator-engine hiccup."""

    def _boom():
        raise RuntimeError("engine exploded")

    publisher = VolatilityReferencePublisher(
        redis=async_redis,
        asset_class=_ASSET,
        settings=_settings(),
        atr_provider=_boom,
        clock=lambda: _NOW,
    )
    assert await publisher.publish_once() == 0


# ---------------------------------------------------------------------------
# Reader (the filter side)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publisher_and_reader_agree_end_to_end(async_redis, sync_redis) -> None:
    """The whole point: one publisher, one reader, both sides of the compare.

    Runs the real async publisher and the real sync reader against one Redis,
    with no hand-written payload in between — a key or encoding mismatch
    between the two would surface here rather than in production as a silently
    inert filter.
    """
    settings = _settings(window_samples=10, min_samples=4)
    series = [1.0, 2.0, 3.0, 8.0]
    publisher = _publisher(
        async_redis,
        settings,
        [{_SYMBOL: value} for value in series],
        [_NOW] * len(series),
    )
    for _ in series:
        await publisher.publish_once()

    provider = build_volatility_reference_provider(
        asset_class=_ASSET,
        settings=settings,
        redis_client=sync_redis,
        clock=lambda: _NOW + timedelta(seconds=30),
    )
    reference = provider(_SYMBOL)

    assert reference is not None
    assert reference.symbol == _SYMBOL
    assert reference.current_atr == pytest.approx(8.0)
    assert reference.atr_percentile == pytest.approx(atr_percentile(series, 90.0))


def test_absent_symbol_reads_as_no_reference(sync_redis) -> None:
    provider = build_volatility_reference_provider(
        asset_class=_ASSET, settings=_settings(), redis_client=sync_redis
    )
    assert provider("NOT_PUBLISHED") is None


def test_stale_reference_reads_as_no_reference(sync_redis) -> None:
    """Past the staleness bound the reader withholds the reference entirely.

    Returning a stale threshold would be worse than returning nothing: the
    filter would gate today's volatility against yesterday's distribution.
    """
    sync_redis.hset(
        _EXPECTED_REFERENCE_KEY,
        _SYMBOL,
        _reference(asof_ts=(_NOW - timedelta(hours=3)).isoformat()).to_json(),
    )
    provider = build_volatility_reference_provider(
        asset_class=_ASSET,
        settings=_settings(stale_max_age_seconds=900),
        redis_client=sync_redis,
        clock=lambda: _NOW,
    )
    assert provider(_SYMBOL) is None


def test_corrupt_payload_reads_as_no_reference(sync_redis) -> None:
    sync_redis.hset(_EXPECTED_REFERENCE_KEY, _SYMBOL, "{not json")
    provider = build_volatility_reference_provider(
        asset_class=_ASSET,
        settings=_settings(),
        redis_client=sync_redis,
        clock=lambda: _NOW,
    )
    assert provider(_SYMBOL) is None


def test_zero_threshold_on_the_wire_reads_as_no_reference(sync_redis) -> None:
    """Defence in depth for the landmine, on the read side too.

    Even if something outside this module ever writes ``atr_percentile: 0``,
    the reader refuses to hand it to the filter — so the "reject everything"
    state cannot be reached through the Redis surface either.
    """
    sync_redis.hset(
        _EXPECTED_REFERENCE_KEY,
        _SYMBOL,
        json.dumps(
            {
                "symbol": _SYMBOL,
                "current_atr": 3.0,
                "atr_percentile": 0.0,
                "percentile": 90.0,
                "sample_size": 99,
                "asof_ts": _NOW.isoformat(),
            }
        ),
    )
    provider = build_volatility_reference_provider(
        asset_class=_ASSET,
        settings=_settings(),
        redis_client=sync_redis,
        clock=lambda: _NOW,
    )
    assert provider(_SYMBOL) is None


def test_redis_error_reads_as_no_reference() -> None:
    """Fail-open: a Redis outage makes the filter skip, never block.

    Opposite polarity to ``has_open_position_provider`` (which fails CLOSED)
    and deliberately so — uncertainty about volatility is not a reason to stop
    trading, whereas uncertainty about an open position is a reason not to
    double up.
    """
    provider = build_volatility_reference_provider(
        asset_class=_ASSET, settings=_settings(), redis_client=_RaisingRedis()
    )
    assert provider(_SYMBOL) is None


def test_reader_warning_is_throttled_but_never_silenced(
    sync_redis, caplog: pytest.LogCaptureFixture
) -> None:
    """The reader throttles per symbol, at the same interval as the filter.

    Without this, a dead publisher makes the reader warn once per candidate,
    which floods the log and defeats the filter's own throttle from below.  The
    throttle must not degrade into silence either: an operator watching a long
    outage needs the warning to keep re-appearing, not to see one line and
    conclude the condition cleared.
    """
    sync_redis.hset(
        _EXPECTED_REFERENCE_KEY,
        _SYMBOL,
        _reference(asof_ts=(_NOW - timedelta(hours=3)).isoformat()).to_json(),
    )
    times = iter(
        [
            _NOW,  # 1st read: warns
            _NOW,  # (throttle clock for that warning)
            _NOW + timedelta(seconds=10),
            _NOW + timedelta(seconds=10),  # suppressed
            _NOW + timedelta(seconds=299),
            _NOW + timedelta(seconds=299),  # suppressed
            _NOW + timedelta(seconds=301),
            _NOW + timedelta(seconds=301),  # interval elapsed: warns again
        ]
    )
    provider = build_volatility_reference_provider(
        asset_class=_ASSET,
        settings=_settings(stale_max_age_seconds=900),
        redis_client=sync_redis,
        clock=lambda: next(times),
        warn_interval_seconds=300.0,
    )

    with caplog.at_level(logging.WARNING, logger=_READER_LOGGER):
        for _ in range(4):
            assert provider(_SYMBOL) is None  # stale every time

    messages = [r.getMessage() for r in caplog.records if r.name == _READER_LOGGER]
    assert len(messages) == 2, messages  # first + the one past the interval
    assert all(_SYMBOL in m for m in messages)


def test_reader_throttle_is_per_symbol(
    sync_redis, caplog: pytest.LogCaptureFixture
) -> None:
    """One blind symbol must not mask another's warning."""
    provider = build_volatility_reference_provider(
        asset_class=_ASSET,
        settings=_settings(),
        redis_client=_RaisingRedis(),
        clock=lambda: _NOW,
        warn_interval_seconds=300.0,
    )

    with caplog.at_level(logging.WARNING, logger=_READER_LOGGER):
        assert provider(_SYMBOL) is None
        assert provider("000660") is None

    messages = [r.getMessage() for r in caplog.records if r.name == _READER_LOGGER]
    assert len(messages) == 2
    assert any(_SYMBOL in m for m in messages)
    assert any("000660" in m for m in messages)


def test_is_stale_is_a_pure_predicate(caplog: pytest.LogCaptureFixture) -> None:
    """``is_stale`` must not log: it runs per candidate with no throttle.

    Its unparseable-timestamp case is still reported — by the reader's
    throttled warning, which quotes ``asof_ts`` — so nothing is lost.
    """
    reference = _reference(asof_ts="not-a-timestamp")
    with caplog.at_level(logging.WARNING):
        assert reference.is_stale(max_age_seconds=900, now=_NOW) is True
    assert [r for r in caplog.records if r.name == _READER_LOGGER] == []


@pytest.mark.asyncio
async def test_backwards_clock_step_publishes_instead_of_suppressing(
    async_redis,
) -> None:
    """An NTP step-back must not silently freeze publishing.

    With a plain ``elapsed < interval`` test, a clock correction of -1 h would
    suppress every publish for an hour; the reference would go stale and the
    filter would fall back to skipping. That failure is safe but silent, and
    inert-by-accident is exactly the defect class this module exists to close —
    so a negative elapsed publishes immediately rather than honouring a
    timestamp the clock jump made meaningless.
    """
    settings = _settings(publish_interval_seconds=60.0, min_samples=1)
    publisher = _publisher(
        async_redis,
        settings,
        [{_SYMBOL: 3.0}, {_SYMBOL: 4.0}],
        [_NOW, _NOW - timedelta(hours=1)],  # wall clock steps backwards
    )

    assert await publisher.maybe_publish() == 1
    assert await publisher.maybe_publish() == 1  # not suppressed

    stored = await async_redis.lrange(_EXPECTED_SAMPLES_KEY, 0, -1)
    assert [float(v) for v in stored] == [4.0, 3.0]


def test_reader_and_publisher_cannot_drift_onto_different_keys(sync_redis) -> None:
    """One settings object drives both sides' key names."""
    settings = _settings(reference_key_prefix="custom:vol:ref")
    publisher = VolatilityReferencePublisher(
        redis=object(),
        asset_class=_ASSET,
        settings=settings,
        atr_provider=dict,
    )
    sync_redis.hset(publisher.reference_key, _SYMBOL, _reference().to_json())

    provider = build_volatility_reference_provider(
        asset_class=_ASSET,
        settings=settings,
        redis_client=sync_redis,
        clock=lambda: _NOW,
    )
    assert publisher.reference_key == "custom:vol:ref:stock"
    assert provider(_SYMBOL) is not None
