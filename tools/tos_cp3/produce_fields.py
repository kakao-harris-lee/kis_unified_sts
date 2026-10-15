#!/usr/bin/env python3
"""CP-3 B1a — shared indicator producer: Parquet minute bars → per-bar field JSONL.

What this is
------------
The upstream half of the CP-3 "same input, compare decisions" path
(``docs/plans/2026-10-07-tos-cp3-first-tenant-kickoff.md`` §3 B1a, §5 step 1).
The TOS kernel computes **no indicators** — every value it compares arrives as
a declared ``bool``/``int``/``str`` Critical Input field (floats are rejected:
``tos/src/tos/marketfeed/value.py``). So Setup D's band math has to run
upstream, and if it ran upstream as a *second* implementation the comparison
would measure the band formula instead of the policy (plan §2, closing
paragraph). This tool therefore **drives the legacy
:class:`~shared.decision.setups.vwap_reversion.SetupDVWAPReversion` bar by bar
and reads its own evaluation trace** (``setup.last_eval``) — it restates no
threshold and no formula.

What a line carries
-------------------
Five top-level keys — ``raw_event_id``, ``source_id``, ``instrument``,
``as_of_ms``, ``fields`` — which is exactly the required-key set of the only
JSONL observation reader in the repo
(``tos/runtime/src/tos_runtime/marketfeed/journal.py``; that reader refuses the
whole poll on a missing key).

``fields`` carries **the bar itself** (``open_x100``/``high_x100``/``low_x100``/
``close_x100``/``volume``/``session_token``) as well as the derived Setup D
inputs. The bar half is what lets B1b build a ``tos.backtest.Bar`` — which
requires open/high/low/close/volume/session_token with range validation — from
this file ALONE. Without it B1b would need its own path back to the Parquet
tree, which is precisely the second ingestion B1a exists to prevent.

Firewall
--------
``tools/`` is inside the reverse scan of ``tools/tos_firewall_check.py``
(TOS-FW-R), so this module imports **nothing** from ``tos`` or
``tos_runtime`` — including the journal's required-key set and ``Bar``'s field
names, which are mirrored here as literals and pinned by tests that say so.

Causality
---------
Every value is a function of bars at or before the bar it is stamped on:

* ``close``/``vwap``/``atr14`` come from ``MarketContextReplay``, whose VWAP is
  session-anchored up to and including the current bar and whose ATR is the
  trailing ``atr_partial`` series (``shared/backtest/market_context_replay.py``
  docstring). The replay's full-series ``atr_90th_percentile`` IS look-ahead —
  Setup D deliberately does not read it, and neither does this tool.
* ``hi_vol``/``stall_ok``/``reversal_ok`` come from the setup's own causal
  deques, which append the current bar only AFTER reading
  (``_vol_reference`` / ``_self_range`` / ``_trend_score``). We call
  ``check()`` exactly once per bar so those windows advance exactly as they do
  in the orchestrator, and we never touch them ourselves.

That is what the prefix test pins: fields for ``bars[:n]`` equal the first
``n``-worth of lines of fields for ``bars[:n+k]``.

Gate fields and "never evaluated"
---------------------------------
``check()`` returns early, so on a given bar the setup may never reach a gate.
``last_eval`` records a key only for a branch it actually took, and this tool
maps an ABSENT key to ``False`` — **fail-closed**: a bar whose gate was never
evaluated must never read as a passing gate.

This does not disturb a tenant policy, because the gate that rejected has its
OWN field false on that bar. On a 09:05 bar rejected for ``vol_below_gate``,
``entry_window`` is still **true** (the bar IS in the window) and ``hi_vol`` is
false, so the entry AND is false through ``hi_vol``. On a bar rejected for
``not_extreme``, ``stall_ok``/``reversal_ok`` are false *and* the ``z_x1000``
comparison is false. Only on a ``before_window``/``after_cutoff`` bar is
``entry_window`` itself false. The session-exit rules read only
``vwap_reverted``/``eod``/``z_x1000``, none of which depend on a gate having
been evaluated, so they keep working after the entry cutoff.

Bars with no publishable ATR
----------------------------
When ``atr_14`` is 0 (a run of perfectly flat bars) the extension ``z`` is
undefined. Those bars are **omitted** from the JSONL rather than filled with a
sentinel, and the lineage lists their ids and the reason. A sentinel would not
be fail-closed: a ``z_x1000 == 0`` reads as "at VWAP" to any band comparison.
The same applies to ``vwap <= 0`` and ``close <= 0`` (see
:func:`_inputs_unusable`); a non-finite input is a data defect and aborts the
run instead. Omission is an output decision only — ``check()`` still runs on
the bar, so the causal deques advance exactly as in the legacy replay.

Declared differences from the legacy strategy
---------------------------------------------
Ten, each recorded in the lineage sidecar under ``declared_differences`` with
its reason, so none is a silent divergence: D1 ``min_confidence`` (no published
field — the DSL has no arithmetic), D2 regime gates (adapter-level), D3
``vwap_reverted`` band form, D4 ``eod`` calendar helpers, D5 unevaluated gate
fields, D6 omitted bars, D7 moving-VWAP exit vs the legacy's frozen entry-time
target, D8 quantization, D9 ``trend_filter_enabled`` has no field (and the run
refuses while it is on), D10 the decision-6 ATR stop.

Usage
-----
::

    .venv/bin/python tools/tos_cp3/produce_fields.py \\
        --data-root /home/deploy/project/kis_unified_sts/data/market \\
        --symbol 101S6000 --start 2025-12-01 --end 2026-04-30 \\
        --strategy-yaml config/strategies/futures/setup_d_vwap_reversion.yaml \\
        --out /tmp/cp3-b1a-run1

Market data is gitignored and lives only in the primary checkout, hence
``--data-root`` is required and never defaulted to the current worktree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import statistics
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

#: Repo root of the checkout this file belongs to. Inserted at the FRONT of
#: ``sys.path`` so that an editable install of the primary checkout cannot
#: shadow this worktree's ``shared/`` (verified: without it, ``import shared``
#: resolves to whichever checkout pip installed, and the producer would then
#: run a different copy of the band math than the one under review).
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.backtest.market_context_replay import (  # noqa: E402
    MarketContextReplay,
)
from shared.decision.context import load_futures_open_from_config  # noqa: E402
from shared.decision.setups.vwap_reversion import (  # noqa: E402
    SetupDConfig,
    SetupDVWAPReversion,
)
from shared.determinism.replay import DEFAULT_WARMUP_BARS  # noqa: E402
from shared.instruments.contract_spec import (  # noqa: E402
    ContractSpec,
    ContractSpecRegistry,
    resolve_contract_spec,
)
from shared.storage.market_data_store import ParquetMarketDataStore  # noqa: E402
from shared.strategy.exit.setup_target_exit import (  # noqa: E402
    SetupTargetExitConfig,
)
from tools.tos_cp3 import TOS_CP3_VERSION  # noqa: E402
from tools.tos_cp3.stitch import (  # noqa: E402
    STITCH_FILENAME,
    StitchError,
    StitchJunction,
    StitchManifest,
    assert_recomputed,
    derive_junction,
    load_manifest,
    segment_offsets_x100,
    shift_price_x100,
)

#: Lineage schema version — separate from the tool version so a reader can
#: tell "values may differ" from "the sidecar is shaped differently".
LINEAGE_SCHEMA_VERSION = 2

#: Stable producer identity stamped on every line as ``source_id``.
SOURCE_ID = f"tos-cp3-b1a/{TOS_CP3_VERSION}"

#: The top-level keys every line carries. MIRRORS
#: ``tos/runtime/src/tos_runtime/marketfeed/journal.py::_REQUIRED_KEYS`` — the
#: import firewall forbids importing it from here, so the set is restated as a
#: literal and ``tests/tools/test_cp3_produce_fields.py`` pins it with the same
#: mirroring note. A missing key makes that reader refuse the whole poll.
JOURNAL_REQUIRED_KEYS = (
    "raw_event_id",
    "source_id",
    "instrument",
    "as_of_ms",
    "fields",
)

#: Output file names inside ``--out``.
FIELDS_FILENAME = "fields.jsonl"
LINEAGE_FILENAME = "lineage.json"

#: Price scale: index points → hundredths of an index point. Exact for the
#: KOSPI200 futures tick (0.05 pt → 5 units); :func:`_assert_scale_covers_tick`
#: refuses any contract whose tick is not an integer at this scale.
PRICE_SCALE = 100
#: ATR-unit scale for the VWAP extension ``z``: thousandths of one ATR.
Z_SCALE = 1000

#: The KST date from which the futures day session opens at 08:45 instead of
#: 09:00. Sourced from ``shared/backtest/market_context_replay.py`` (the
#: ``market_open_hour`` field comment), which states that a replay over
#: PRE-cutover data MUST use 09:00 or every open-relative window is shifted 15
#: minutes and the replayed signals no longer match the regime that produced
#: the published OOS numbers.
OPEN_ANCHOR_CUTOVER = date(2026, 6, 28)
#: The pre-cutover anchor that same comment names.
PRE_CUTOVER_OPEN = (9, 0)

#: Default density gate, matching
#: ``scripts/analysis/walkforward_setup_d_vwap_reversion.py``'s own default —
#: the OOS numbers this parity window is compared against were produced with
#: it. 0 is the explicit opt-out.
DEFAULT_MIN_BARS_PER_DAY = 330


class ProduceFieldsError(RuntimeError):
    """Raised when inputs cannot be turned into a trustworthy field stream."""


# ---------------------------------------------------------------------------
# Scaling
# ---------------------------------------------------------------------------


def scaled_int_half_up(value: float, scale: int) -> int:
    """Scale a MAGNITUDE by *scale* and round half-up to an ``int``.

    Used for prices and ATR, where the nearest representable value is what is
    wanted and no threshold comparison is made on the published integer.
    Half-up is monotone, so the OHLC relations a ``tos.backtest.Bar`` validates
    (``high >= low``, ``open``/``close`` inside the range) survive the scaling.

    Half-up rather than :func:`round` because ``round`` is banker's rounding,
    whose result depends on the parity of the neighbouring integer —
    deterministic, but not reproducible by a reader who reimplements the scale
    from the sidecar.
    """
    return int(math.floor(value * scale + 0.5))


def scaled_int_toward_zero(value: float, scale: int) -> int:
    """Scale a SIGNED, threshold-compared value and truncate toward zero.

    Used for ``z_x1000``. Two properties half-up does not have:

    * **Symmetric** — ``+1.7995`` and ``-1.7995`` become ``+1799`` and
      ``-1799``, whereas half-up maps them to ``1800`` and ``-1799``.
    * **Conservative at the trigger** — truncation toward zero means
      ``abs(z_x1000) >= scaled_int_toward_zero(extreme_atr_mult, 1000)`` holds
      only when ``abs(z) >= extreme_atr_mult`` really does, so a policy written
      on the integer **never fires where the legacy setup did not**. The price
      is that the published integer understates ``abs(z)`` by up to one unit
      (0.001 ATR); see declared difference D8.
    """
    return int(math.trunc(value * scale))


# ---------------------------------------------------------------------------
# Join keys
# ---------------------------------------------------------------------------
#
# ONE definition, shared with the B2 decision emitter
# (``tools/tos_cp3/emit_legacy_decisions.py``). B3 joins the two artifacts on
# ``raw_event_id``, so a second derivation on the other side — even an
# identical-looking one — is how the two files would come to disagree about
# which bar a line is about. B2 imports these; it does not restate them.


def derive_raw_event_id(symbol: str, bar_kst: datetime) -> str:
    """The join key for one replayed bar.

    ``<symbol>:1m:<YYYYmmddTHHMMSS±HHMM>``. The offset is part of the key so a
    naive and an aware stamp for the same wall-clock minute cannot collide, and
    the timeframe token says what a "bar" is here.
    """
    return f"{symbol}:1m:{bar_kst.strftime('%Y%m%dT%H%M%S%z')}"


def derive_as_of_ms(bar_kst: datetime) -> int:
    """Epoch milliseconds of the bar's LABELLED minute.

    The label, not label+60s: the session fields (``entry_window``, ``eod``)
    are computed on the label, so an end-of-bar stamp would desynchronise
    ``as_of_ms`` from them (a 15:15 bar would carry a 15:16 ``as_of_ms``).
    """
    return int(bar_kst.timestamp() * 1000)


def _assert_scale_covers_tick(spec: ContractSpec, scale: int) -> None:
    """Refuse a contract whose tick is not an integer at *scale*.

    A 0.05-point tick is 5 units at scale 100. A 0.025-point tick would be 2.5
    — the published integer could then not represent every tradable price, and
    two adjacent prices would collapse onto one value. Fail loudly instead.
    """
    ticks = spec.tick_size_points * scale
    if abs(ticks - round(ticks)) > 1e-9:
        raise ProduceFieldsError(
            f"tick_size_points={spec.tick_size_points} is not an integer at "
            f"scale {scale} ({ticks}); the integer encoding would lose "
            f"tradable prices for contract {spec.name!r}"
        )


# ---------------------------------------------------------------------------
# Inputs: strategy YAML
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StrategyInputs:
    """The strategy YAML resolved into everything the producer reads from it."""

    path: Path
    sha256: str
    asset_class: str
    entry_params: dict[str, Any]
    exit_params: dict[str, Any]
    entry_config: SetupDConfig
    exit_config: SetupTargetExitConfig
    vwap_revert_band: float
    vwap_revert_band_source: str


def load_strategy_inputs(path: Path) -> StrategyInputs:
    """Read the Setup D strategy YAML — every threshold/window comes from here."""
    raw_bytes = path.read_bytes()
    data = yaml.safe_load(raw_bytes.decode("utf-8")) or {}
    strategy = data.get("strategy")
    if not isinstance(strategy, dict):
        raise ProduceFieldsError(f"{path}: no top-level 'strategy' mapping")

    entry = strategy.get("entry") or {}
    exit_ = strategy.get("exit") or {}
    entry_type = entry.get("type")
    if entry_type != SetupDVWAPReversion.REGISTRY_NAME:
        raise ProduceFieldsError(
            f"{path}: strategy.entry.type is {entry_type!r}; this producer "
            f"only knows {SetupDVWAPReversion.REGISTRY_NAME!r}"
        )

    entry_params = dict(entry.get("params") or {})
    exit_params = dict(exit_.get("params") or {})
    # ``SetupDConfig`` is ServiceConfigBase (extra="ignore"), so the
    # adapter-only keys in this section (regime_gate, *_blocked_regimes, ...)
    # are dropped exactly as the decoupled decision_engine drops them.
    config = SetupDConfig(**{k: v for k, v in entry_params.items() if v is not None})

    # The trend gate is causal state inside check() with no published field and
    # no Critical Input declaration, so a run with it ON would emit a field set
    # that cannot reproduce the legacy decision. Refuse rather than ship a
    # quietly incomplete baseline (declared difference D9).
    if config.trend_filter_enabled:
        raise ProduceFieldsError(
            f"{path}: strategy.entry.params.trend_filter_enabled is true, but "
            "this producer publishes no trend field — the session-VWAP-drift "
            "gate is causal state inside check() with no Critical Input "
            "declaration yet, so the published field set could not reproduce "
            "the legacy decision. Publishing and declaring a trend field is "
            "the follow-up; until then this run refuses."
        )

    # The band-form premise of vwap_reverted (declared differences D3/D7): at
    # the fade trigger the VWAP-revert target IS the VWAP, which only holds
    # while the extension term beats the reward/risk floor.
    floor_mult = config.min_reward_risk * config.stop_atr_mult
    if not config.extreme_atr_mult > floor_mult:
        raise ProduceFieldsError(
            f"{path}: extreme_atr_mult={config.extreme_atr_mult} is not greater "
            f"than min_reward_risk*stop_atr_mult={floor_mult}; the "
            "vwap_reverted note's premise (the legacy revert target equals the "
            "session VWAP for every qualifying entry) does not hold, so the "
            "band form would be documented against a false statement"
        )

    # Build the legacy exit config itself rather than re-deriving the cutoff:
    # ``eod_close_time`` is its property. ``from_dict`` would do the same field
    # filtering but is deprecated (it warns on every call), so the known fields
    # are selected here and the class's own validate() is run.
    exit_config = SetupTargetExitConfig(
        **{
            key: value
            for key, value in exit_params.items()
            if key in SetupTargetExitConfig.__dataclass_fields__
        }
    )
    exit_config.validate()

    # Band parameter: its own key when the YAML declares one, else the
    # reversal-confirmation tolerance it currently borrows. Recorded either way
    # so a reader never has to guess which was in force.
    declared_band = exit_params.get("vwap_revert_band_atr_mult")
    if declared_band is not None:
        band = float(declared_band)
        band_source = "strategy.exit.params.vwap_revert_band_atr_mult"
    else:
        band = float(config.reversal_confirm_atr_mult)
        band_source = (
            "strategy.entry.params.reversal_confirm_atr_mult (fallback — the "
            "YAML declares no vwap_revert_band_atr_mult; giving the band its "
            "own key is a follow-up on the strategy file, not on this tool)"
        )

    return StrategyInputs(
        path=path,
        sha256=hashlib.sha256(raw_bytes).hexdigest(),
        asset_class=str(strategy.get("asset_class") or "futures"),
        entry_params=entry_params,
        exit_params=exit_params,
        entry_config=config,
        exit_config=exit_config,
        vwap_revert_band=band,
        vwap_revert_band_source=band_source,
    )


# ---------------------------------------------------------------------------
# Inputs: the open anchor
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OpenAnchor:
    """The futures open the replay stamps on every context, and where it came from."""

    hour: int
    minute: int
    source: str

    @property
    def kst(self) -> str:
        return f"{self.hour:02d}:{self.minute:02d}"


def resolve_open_anchor(
    *, cli_value: str, first_session: date, last_session: date
) -> OpenAnchor:
    """Resolve the open anchor from ``--market-open`` or the era rule.

    ``auto`` applies the rule stated in ``market_context_replay.py``: data
    before 2026-06-28 was produced when the futures day session opened at
    09:00, and replaying it at 08:45 shifts every open-relative window by 15
    minutes, so the replayed signals no longer match the regime that produced
    the published OOS numbers. A window that STRADDLES the cutover has no
    single correct anchor, so it is refused rather than silently given one.
    """
    if cli_value != "auto":
        try:
            parsed = datetime.strptime(cli_value, "%H:%M").time()
        except ValueError as exc:
            raise ProduceFieldsError(
                f"--market-open must be HH:MM or 'auto' (got {cli_value!r})"
            ) from exc
        return OpenAnchor(parsed.hour, parsed.minute, "cli")

    if last_session < OPEN_ANCHOR_CUTOVER:
        return OpenAnchor(PRE_CUTOVER_OPEN[0], PRE_CUTOVER_OPEN[1], "era-rule")
    if first_session >= OPEN_ANCHOR_CUTOVER:
        hour, minute = load_futures_open_from_config(
            str(REPO_ROOT / "config" / "market_schedule.yaml")
        )
        return OpenAnchor(hour, minute, "config")
    raise ProduceFieldsError(
        f"the window {first_session}..{last_session} straddles the "
        f"{OPEN_ANCHOR_CUTOVER} open-anchor cutover, and one anchor cannot be "
        "right for both eras (every minutes_since_open on one side would be "
        "shifted 15 minutes). Split the run, or pass --market-open explicitly."
    )


# ---------------------------------------------------------------------------
# Inputs: Parquet bars
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InputFile:
    """One Parquet partition file that fed this run."""

    path: str
    sha256: str
    size_bytes: int


def discover_input_files(
    data_root: Path, *, asset_class: str, symbol: str, start: date, end: date
) -> list[InputFile]:
    """List, in sorted order, the Parquet partitions inside ``[start, end]``.

    Mirrors ``ParquetMarketDataStore``'s partition layout
    (``<root>/<asset_class>/minute/code=<symbol>/year=/month=/day=``) so the
    lineage names the files the loader actually read.
    """
    base = data_root / asset_class / "minute" / f"code={symbol}"
    found: list[InputFile] = []
    for parquet in sorted(base.glob("year=*/month=*/day=*/*.parquet")):
        day_token = parquet.parent.name.removeprefix("day=")
        try:
            day = date.fromisoformat(day_token)
        except ValueError:
            continue
        if not (start <= day <= end):
            continue
        raw = parquet.read_bytes()
        found.append(
            InputFile(
                path=str(parquet.relative_to(data_root)),
                sha256=hashlib.sha256(raw).hexdigest(),
                size_bytes=len(raw),
            )
        )
    return found


def _apply_density_gate(df: Any, *, min_bars_per_day: int, loaded: int) -> Any:
    """Drop whole sessions thinner than *min_bars_per_day*. ONE body.

    Called by :func:`load_bars` (single contract) and by
    :func:`load_stitched_bars` (cross-contract, plan §3.2a). Shared rather than
    copied because the gate decides WHICH DAYS enter the frame: two copies
    could come to keep different sessions, and a producer seeded from a
    different set of sessions than the offline run it is compared against
    makes B3 diverge for a reason that looks like a field defect (plan §3.2
    「밀도 게이트를 B1a 와 같게」).

    Args:
        loaded: the PRE-gate row count, for the refusal message only.
    """
    if min_bars_per_day <= 0:
        return df
    bars_per_day = df.groupby(df["timestamp"].dt.date).size()
    healthy = set(bars_per_day[bars_per_day >= min_bars_per_day].index)
    gated = df[df["timestamp"].dt.date.map(lambda d: d in healthy)].reset_index(
        drop=True
    )
    if gated.empty:
        raise ProduceFieldsError(
            f"the --min-bars-per-day {min_bars_per_day} density gate dropped "
            f"every one of the {loaded} loaded bars"
        )
    return gated


def load_bars(
    data_root: Path,
    *,
    asset_class: str,
    symbol: str,
    start: date,
    end: date,
    min_bars_per_day: int,
) -> tuple[Any, int]:
    """Load minute bars through the project's Parquet store.

    Uses ``ParquetMarketDataStore`` — the very object
    ``shared.storage.market_data_store.load_market_bars_for_backtest`` builds
    via ``create_market_data_store`` — constructed with an explicit ``root``
    because the market-data tree is gitignored and lives only in the primary
    checkout (the configured ``StorageConfig`` root would point at the wrong
    checkout from a worktree). Same construction, and the same default
    ``min_bars_per_day``, as
    ``scripts/analysis/walkforward_setup_d_vwap_reversion.py::load_clean``.

    Returns the gated frame and the PRE-gate row count.
    """
    store = ParquetMarketDataStore(root=data_root, asset_class=asset_class)
    df = store.get_minute_bars(symbol, start=start, end=end)
    if df.empty:
        raise ProduceFieldsError(
            f"no {symbol} minute bars in {start}..{end} under {data_root}"
        )
    df = (
        df.rename(columns={"datetime": "timestamp"})
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    loaded = int(len(df))
    # ONE gate body, shared with the stitched loader (review MEDIUM-2). The
    # first cut copied these lines into a second function for the stitched
    # path and left this one in place, so the two could drift into keeping
    # different sessions — the exact divergence the gate exists to prevent.
    gated = _apply_density_gate(df, min_bars_per_day=min_bars_per_day, loaded=loaded)
    return gated, loaded


# ---------------------------------------------------------------------------
# Inputs: the cross-contract (month-stitch) seed — plan §3.2a
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StitchedInputs:
    """What reading a stitched window produced, beyond the frame itself."""

    manifest: StitchManifest
    #: Junctions re-derived from the stored UNADJUSTED partitions and asserted
    #: equal to the manifest's (plan §3.2a MEDIUM-3).
    recomputed: tuple[StitchJunction, ...]
    #: ``contract -> offset_x100`` actually applied to that segment's OHLC.
    offsets_x100: dict[str, int]
    #: Splice-day NEW-contract partitions, read for the recomputation only and
    #: deliberately NOT part of the frame (re-review N-3).
    recompute_input_files: list[InputFile]
    recompute_bars: int


def _segment_day_bars(
    data_root: Path, *, asset_class: str, contract: str, day: date
) -> Any:
    """One ``(contract, day)`` partition, as the project's own store reads it."""
    store = ParquetMarketDataStore(root=data_root, asset_class=asset_class)
    df = store.get_minute_bars(contract, start=day, end=day)
    if df.empty:
        raise ProduceFieldsError(
            f"the stitch manifest names ({contract}, {day}) but no bar is "
            f"stored for that pair under {data_root}"
        )
    return df.rename(columns={"datetime": "timestamp"})


def _day_partition_files(
    data_root: Path, *, asset_class: str, contract: str, day: date
) -> list[InputFile]:
    return discover_input_files(
        data_root, asset_class=asset_class, symbol=contract, start=day, end=day
    )


def load_stitched_bars(
    data_root: Path,
    *,
    asset_class: str,
    manifest: StitchManifest,
    min_bars_per_day: int,
) -> tuple[Any, int, list[InputFile], StitchedInputs]:
    """Read exactly the manifest's ``(contract, day)`` pairs and align them.

    Never a date-range glob (plan §3.2a 「구간에 적힌 (월물, 거래일) 쌍만 읽는다」):
    a session directory holds the previous month's partitions too, and a glob
    over the target symbol alone would silently drop them while a glob over the
    tree would silently duplicate the splice day.

    The previous month's OHLC is shifted by the manifest's integer ``c_x100``
    — volume is untouched — and the splice day's new-contract partition is read
    ONLY to recompute that constant.
    """
    import pandas as pd

    offsets = segment_offsets_x100(manifest)
    parts: list[Any] = []
    input_files: list[InputFile] = []
    loaded = 0
    for segment in manifest.segments:
        offset = offsets[segment.contract]
        for day in segment.days:
            frame = _segment_day_bars(
                data_root,
                asset_class=asset_class,
                contract=segment.contract,
                day=day,
            )
            loaded += int(len(frame))
            if offset:
                for column in ("open", "high", "low", "close"):
                    frame[column] = [
                        shift_price_x100(value, offset) for value in frame[column]
                    ]
            parts.append(frame)
            input_files.extend(
                _day_partition_files(
                    data_root,
                    asset_class=asset_class,
                    contract=segment.contract,
                    day=day,
                )
            )

    recomputed, recompute_files, recompute_bars = _recompute_junctions(
        data_root, asset_class=asset_class, manifest=manifest
    )
    assert_recomputed(manifest, recomputed)

    df = (
        pd.concat(parts, ignore_index=True)
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    df = _apply_density_gate(df, min_bars_per_day=min_bars_per_day, loaded=loaded)
    return (
        df,
        loaded,
        input_files,
        StitchedInputs(
            manifest=manifest,
            recomputed=tuple(recomputed),
            offsets_x100=offsets,
            recompute_input_files=recompute_files,
            recompute_bars=recompute_bars,
        ),
    )


def _recompute_junctions(
    data_root: Path, *, asset_class: str, manifest: StitchManifest
) -> tuple[list[StitchJunction], list[InputFile], int]:
    """Re-derive every junction from the stored UNADJUSTED bars."""
    recomputed: list[StitchJunction] = []
    files: list[InputFile] = []
    bars = 0
    for junction in manifest.junctions:
        old = _segment_day_bars(
            data_root,
            asset_class=asset_class,
            contract=junction.old_contract,
            day=junction.day,
        )
        new = _segment_day_bars(
            data_root,
            asset_class=asset_class,
            contract=junction.new_contract,
            day=junction.day,
        )
        bars += int(len(new))
        files.extend(
            _day_partition_files(
                data_root,
                asset_class=asset_class,
                contract=junction.new_contract,
                day=junction.day,
            )
        )
        recomputed.append(
            derive_junction(
                day=junction.day,
                old_contract=junction.old_contract,
                new_contract=junction.new_contract,
                old_bars=_as_parse_tuples(old, junction.old_contract),
                new_bars=_as_parse_tuples(new, junction.new_contract),
            )
        )
    return recomputed, files, bars


def _as_parse_tuples(df: Any, contract: str) -> list[tuple]:
    """A stored frame back in ``parse_ohlcv`` tuple shape, for the ``c`` math."""
    return [
        (contract, stamp.to_pydatetime(), 0.0, 0.0, 0.0, float(close), 0)
        for stamp, close in zip(df["timestamp"], df["close"])
    ]


def resolve_session_manifest(
    data_root: Path, *, symbol: str, stitch_manifest: Path | None
) -> StitchManifest | None:
    """The session-directory refusal rules of plan §3.2a (MEDIUM-1, N-2).

    ``stitch.json`` sits directly under the ``--data-root`` B1a and B2 are
    given, i.e. ``<session dir>/market/``. A run against that directory that
    does not pass the manifest would read only the target contract's
    partitions and silently produce a SHORTER frame than the producer's, so it
    is refused. A manifest describing another instrument is refused for the
    same reason: it would align the wrong segment.

    ⛔ Not implemented, by decision: "there are sibling ``code=`` directories,
    so this must be a stitched tree". The legacy ``data/market`` root always
    holds several contract months and the check would be a false positive on
    every legacy run (plan §9 MEDIUM-1).
    """
    manifest = load_manifest(stitch_manifest) if stitch_manifest else None
    in_session = data_root / STITCH_FILENAME
    if manifest is None and in_session.is_file():
        raise ProduceFieldsError(
            f"{in_session} exists but no --stitch-manifest was given. That file "
            "means the frame under this data root was assembled across contract "
            "months; reading it without the manifest would quietly load only "
            f"the {symbol} partitions and compare a short frame against the "
            "producer's stitched one (plan §3.2a 「세션 dir 거부 규칙」)"
        )
    if manifest is not None and manifest.symbol != symbol:
        raise ProduceFieldsError(
            f"{stitch_manifest} targets {manifest.symbol!r} but --symbol is "
            f"{symbol!r}. The manifest decides which segment is the reference "
            "for the back-adjust, so the wrong one aligns the wrong bars"
        )
    return manifest


# ---------------------------------------------------------------------------
# Production
# ---------------------------------------------------------------------------

#: Published field order. Fixed so the JSONL is byte-stable. The first six are
#: the bar itself (what B1b needs to build a ``tos.backtest.Bar``); the rest are
#: the derived Setup D inputs.
FIELD_ORDER = (
    "open_x100",
    "high_x100",
    "low_x100",
    "close_x100",
    "volume",
    "session_token",
    "vwap_x100",
    "atr14_x100",
    "z_x1000",
    "hi_vol",
    "stall_ok",
    "reversal_ok",
    "entry_window",
    "vwap_reverted",
    "eod",
)


@dataclass(frozen=True)
class FieldRecord:
    """One published observation: a bar's scalar field set.

    ``bar_kst`` is carried for the lineage summary and for tests; it is NOT
    published — the wire form is exactly :data:`JOURNAL_REQUIRED_KEYS`.
    """

    raw_event_id: str
    instrument: str
    as_of_ms: int
    fields: dict[str, int | bool | str]
    bar_kst: datetime

    def to_payload(self) -> dict[str, Any]:
        return {
            "raw_event_id": self.raw_event_id,
            "source_id": SOURCE_ID,
            "instrument": self.instrument,
            "as_of_ms": self.as_of_ms,
            "fields": self.fields,
        }

    def to_json_line(self) -> str:
        return json.dumps(self.to_payload(), separators=(",", ":"), ensure_ascii=True)


def _assert_scalar_fields(
    fields: dict[str, int | bool | str], raw_event_id: str
) -> None:
    """Guard the kernel's hard rule: a float field is rejected at the border.

    ``tos/src/tos/marketfeed/value.py`` drops a float outright, so a float
    leaking into this JSONL would show up as a silently missing field on the
    kernel side rather than as an error here. Concretely, this fires if a
    scaling helper is ever changed to return ``value * scale`` instead of an
    ``int``.
    """
    for key, value in fields.items():
        if isinstance(value, (bool, str)):
            continue
        if not isinstance(value, int):
            raise ProduceFieldsError(
                f"{raw_event_id}: field {key!r} is {type(value).__name__}, "
                f"not int/bool/str: {value!r}"
            )


#: How many omitted-bar ids the lineage lists before truncating (the count is
#: always exact; the id list is a sample above this many).
OMITTED_ID_LIST_CAP = 200


def _inputs_unusable(close: float, vwap: float, atr: float) -> str | None:
    """Name the reason this bar's ATR-scaled fields cannot be published.

    Returns ``None`` when ``close``/``vwap``/``atr`` can all carry their
    published meaning, else the reason. Each case is a value the setup's own
    docstrings call out as NOT a benign zero:

    * ``atr <= 0`` — a run of perfectly flat bars makes every true range 0, so
      ``atr_partial`` is 0 and ``z = (close - vwap) / atr`` is undefined.
    * ``vwap <= 0`` — at ``vwap == 0`` the extension degenerates to
      ``close / atr``, "a huge FABRICATED extreme" (``REQUIRES_VWAP``
      docstring).
    * ``close <= 0`` — ``check`` rejects ``no_price``.

    Publishing a sentinel instead would be worse than publishing nothing: a
    ``z_x1000`` of 0 reads as "at VWAP" to any band comparison. A bar with no
    publishable ATR is therefore OMITTED (and counted in the lineage).

    A NON-FINITE input is different in kind: NaN/inf is a defect in the Parquet
    tree, not a legitimately quiet bar, and counting it as an omission would
    hide a corrupted dataset behind a number that looks benign. It raises.
    """
    for name, value in (("close", close), ("vwap", vwap), ("atr_14", atr)):
        if not math.isfinite(value):
            raise ProduceFieldsError(
                f"non-finite {name}={value!r} in the replayed bar stream — the "
                "Parquet window is corrupt; omitting the bar would hide that"
            )
    if atr <= 0:
        return "atr_14 <= 0 (z is undefined)"
    if vwap <= 0:
        return "vwap <= 0 (z would be a fabricated extreme)"
    if close <= 0:
        return "close <= 0"
    return None


@dataclass(frozen=True)
class ProducedBars:
    """Emitted records plus the bars deliberately left unpublished."""

    records: list[FieldRecord]
    bars_replayed: int
    omitted: list[tuple[str, str]]  # (raw_event_id, reason)
    #: Bars replayed from a NON-target stitch segment (plan §3.2a). They
    #: advance the causal windows and are then dropped without a
    #: ``raw_event_id``: naming a previous-month bar after this symbol is
    #: precisely the label error the plan's 「라벨은 진실하게」 rule forbids, so
    #: they are COUNTED here and never listed by id.
    non_target_segment_bars: int = 0


def _bar_lookup(df: Any) -> dict[Any, tuple[float, float, float, float]]:
    """Map each bar timestamp to its ``(open, high, low, volume)``.

    ``MarketContext`` carries only the close, so the OHLCV half of a published
    line is read back from the frame the replay was built from. A duplicated
    timestamp would make that lookup ambiguous (the #516 minute-dedup defect),
    so it is refused rather than resolved arbitrarily.
    """
    import pandas as pd

    stamps = df["timestamp"]
    if stamps.duplicated().any():
        dupes = stamps[stamps.duplicated()].head(3).tolist()
        raise ProduceFieldsError(
            f"duplicate bar timestamps in the loaded window (e.g. {dupes}); the "
            "OHLCV lookup would be ambiguous — re-run the minute dedup"
        )
    return {
        pd.Timestamp(stamp): (float(bar_open), float(high), float(low), float(volume))
        for stamp, bar_open, high, low, volume in zip(
            stamps, df["open"], df["high"], df["low"], df["volume"]
        )
    }


def produce_bars(
    df: Any,
    *,
    symbol: str,
    strategy: StrategyInputs,
    contract_spec: ContractSpec,
    anchor: OpenAnchor,
    emit_days: frozenset[date] | None = None,
    observer: Callable[[datetime, Mapping[str, Any]], None] | None = None,
) -> ProducedBars:
    """Drive the legacy Setup D bar by bar and project its state into fields.

    ``check()`` is called exactly once per replayed bar — that single call is
    what advances the setup's causal ATR / close / VWAP windows, so calling it
    more or fewer times than the orchestrator would change ``hi_vol`` and
    ``stall_ok``. Nothing in this function recomputes a threshold or a formula
    that the setup owns.

    A bar whose inputs cannot carry their published meaning
    (:func:`_inputs_unusable`) is still EVALUATED — the legacy replay evaluates
    every bar, and the causal deques must advance identically — but is not
    emitted. Its id and reason go into the lineage.

    Args:
        emit_days: when given, only bars on these KST dates are EMITTED. Every
            other bar is still replayed — the whole point of a stitched seed is
            that the previous month's sessions advance ATR, the vol-window
            percentile and ``prev_close`` — but produces no record, because a
            previous-month bar carrying a ``raw_event_id`` named after this
            symbol would be a label error (plan §3.2a). ``None`` keeps the
            pre-stitch behaviour: every replayed bar is a candidate.
        observer: read-only hook called with ``(bar_kst, last_eval)`` after
            ``check()`` on EVERY replayed bar — the non-emitted previous-month
            bars included, which is the point: the causal ATR window is filled
            by bars this function does not publish, so a measurement of that
            window (``tools/tos_cp3/stitch_measure.py`` S1b, plan §3.2a's
            「``_atr_window`` 내용과 백분위 기준값」) cannot read it from the
            records. It observes the setup's own trace — nothing here is
            recomputed — and takes no part in the decision: it is handed a
            :class:`~types.MappingProxyType` over ``last_eval``, so a write
            raises instead of leaking into the next bar, and the returned
            records are identical with and without it
            (``tests/tools/test_cp3_produce_fields.py``).
    """
    import pandas as pd

    setup = SetupDVWAPReversion(config=strategy.entry_config)
    replay = MarketContextReplay(
        df=df,
        symbol=symbol,
        macro_snapshot=None,
        scheduled_events=[],
        contract_spec=contract_spec,
        market_open_hour=anchor.hour,
        market_open_minute=anchor.minute,
        min_volume=0,
    )
    ohlcv = _bar_lookup(df)
    revert_band = strategy.vwap_revert_band
    eod_enabled = strategy.exit_config.eod_close_enabled
    eod_cutoff = strategy.exit_config.eod_close_time

    records: list[FieldRecord] = []
    omitted: list[tuple[str, str]] = []
    bars_replayed = 0
    non_target = 0
    for ctx in replay.iter_contexts():
        setup.check(ctx)
        ev = setup.last_eval
        if observer is not None:
            # Read-only by construction, not by convention: the proxy raises on
            # any write, so "it takes no part in the decision" is enforced here
            # rather than only asserted in a test. The default path keeps the
            # `is not None` guard, so it allocates no proxy at all.
            observer(ctx.now, MappingProxyType(ev))
        bars_replayed += 1

        now: datetime = ctx.now
        if emit_days is not None and now.date() not in emit_days:
            # Replayed (the windows advanced on the check() above) and then
            # dropped BEFORE a join key is derived — see the docstring.
            non_target += 1
            continue
        as_of_ms = derive_as_of_ms(now)
        raw_event_id = derive_raw_event_id(symbol, now)

        close = float(ctx.current_price)
        vwap = float(ctx.vwap)
        atr = float(ctx.atr_14)
        unusable = _inputs_unusable(close, vwap, atr)
        if unusable is not None:
            omitted.append((raw_event_id, unusable))
            continue

        stamp = pd.Timestamp(now).tz_localize(None)
        if stamp not in ohlcv:
            raise ProduceFieldsError(
                f"{raw_event_id}: the replay yielded a bar with no row in the "
                "loaded frame — the OHLCV half cannot be published"
            )
        bar_open, bar_high, bar_low, bar_volume = ohlcv[stamp]
        for name, value in (
            ("open", bar_open),
            ("high", bar_high),
            ("low", bar_low),
            ("volume", bar_volume),
        ):
            if not math.isfinite(value):
                raise ProduceFieldsError(
                    f"{raw_event_id}: non-finite bar {name}={value!r}"
                )

        # ONE definition of z, shared with check() (see the accessor's
        # docstring). Published on every bar because the session-exit fields
        # outlive the entry window, where check() returns early.
        z = SetupDVWAPReversion.vwap_extension_z(close, vwap, atr)

        fields: dict[str, int | bool | str] = {
            "open_x100": scaled_int_half_up(bar_open, PRICE_SCALE),
            "high_x100": scaled_int_half_up(bar_high, PRICE_SCALE),
            "low_x100": scaled_int_half_up(bar_low, PRICE_SCALE),
            "close_x100": scaled_int_half_up(close, PRICE_SCALE),
            "volume": int(bar_volume),
            # Opaque session identifier — a tos Bar reads no market hours from
            # it. Futures is day-only, so the KST date IS the session.
            "session_token": now.date().isoformat(),
            "vwap_x100": scaled_int_half_up(vwap, PRICE_SCALE),
            "atr14_x100": scaled_int_half_up(atr, PRICE_SCALE),
            "z_x1000": scaled_int_toward_zero(z, Z_SCALE),
            "hi_vol": ev.get("hi_vol") is True,
            "stall_ok": ev.get("stall_ok") is True,
            "reversal_ok": ev.get("reversal_ok") is True,
            "entry_window": ev.get("entry_window") is True,
            "vwap_reverted": abs(z) <= revert_band,
            "eod": eod_enabled and now.time() >= eod_cutoff,
        }
        ordered = {name: fields[name] for name in FIELD_ORDER}
        _assert_scalar_fields(ordered, raw_event_id)
        records.append(
            FieldRecord(
                raw_event_id=raw_event_id,
                instrument=symbol,
                as_of_ms=as_of_ms,
                fields=ordered,
                bar_kst=now,
            )
        )
    if not records:
        raise ProduceFieldsError(
            "replay yielded no publishable bars: a window shorter than the "
            f"{DEFAULT_WARMUP_BARS}-bar replay warmup, a first session with "
            f"no prior-session close, {len(omitted)} unusable-input bars, or "
            f"{non_target} bars outside the stitch manifest's target segment"
        )
    return ProducedBars(
        records=records,
        bars_replayed=bars_replayed,
        omitted=omitted,
        non_target_segment_bars=non_target,
    )


def produce_records(
    df: Any,
    *,
    symbol: str,
    strategy: StrategyInputs,
    contract_spec: ContractSpec,
    anchor: OpenAnchor,
) -> list[FieldRecord]:
    """:func:`produce_bars` when only the emitted records are wanted."""
    return produce_bars(
        df,
        symbol=symbol,
        strategy=strategy,
        contract_spec=contract_spec,
        anchor=anchor,
    ).records


def render_jsonl(records: list[FieldRecord]) -> bytes:
    """Serialize *records* to the exact bytes written to disk."""
    return "".join(f"{record.to_json_line()}\n" for record in records).encode("utf-8")


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------

#: D7's measurement — how often an exit written on the moving session-VWAP
#: SIGN differs from the legacy exit's target price FROZEN at signal time.
#:
#: The generator is :func:`measure_moving_vs_frozen_exit` in THIS module, driven
#: by :data:`D7_GENERATOR_COMMAND`::
#:
#:     python tools/tos_cp3/produce_fields.py --measure-d7 \
#:         --data-root <root> --symbol 101S6000 \
#:         --start 2025-12-01 --end 2026-04-30 \
#:         --strategy-yaml config/strategies/futures/setup_d_vwap_reversion.yaml \
#:         --out <unused>
#:
#: which prints exactly this literal to stdout for pasting. It is restated here
#: rather than computed on every produce so a field run does not pay for a
#: second simulation; regenerate whenever the window, the anchor or the strategy
#: parameters change. (An earlier revision of this comment pointed at a
#: ``measure_d7.py`` script that was never written — the flag above is the
#: generator that actually exists.)
#:
#: Recorded in the lineage as ``declared_differences[D7].d7_measurement_generator``
#: so a reader of the sidecar can regenerate the number without reading this file.
D7_GENERATOR_COMMAND = "produce_fields.py --measure-d7"

D7_MEASUREMENT: dict[str, Any] = {
    "window": "101S6000 2025-12-05..2026-04-29",
    "market_open_kst": "09:00",
    "min_bars_per_day": DEFAULT_MIN_BARS_PER_DAY,
    "entries": 550,
    "earlier": 237,
    "earlier_frozen_never_reached_in_session": 47,
    "identical": 82,
    "later": 0,
    "later_moving_never_reached_in_session": 0,
    "never_either": 231,
    "median_lead_bars": 6,
    "max_lead_bars": 165,
    "lead_bars_measured_over": 190,
}


def _observed_range(records: list[FieldRecord], key: str) -> dict[str, Any]:
    """Observed value range for one field — min/max, true/false, or distinct."""
    values = [record.fields[key] for record in records]
    if isinstance(values[0], bool):
        true_count = sum(1 for value in values if value)
        return {"true": true_count, "false": len(values) - true_count}
    if isinstance(values[0], str):
        return {"distinct": len({str(value) for value in values})}
    numbers = [int(value) for value in values]  # type: ignore[arg-type]
    return {"min": min(numbers), "max": max(numbers)}


def _price_field(
    formula: str, parents: list[str], note: str, window_bars: int | None = 1
) -> dict[str, Any]:
    """Lineage entry shared by every ×100 price-like field."""
    return {
        "unit": "index_point",
        "scale": "hundredths",
        "multiplier": "100",
        "sign": "unsigned",
        "type": "int",
        "quantization": "half_up",
        "formula_id": formula,
        "window_bars": window_bars,
        "parents": parents,
        "source": note,
    }


def _bool_field(
    formula: str, parents: list[str], note: str, window_bars: int | None
) -> dict[str, Any]:
    """Lineage entry shared by every published boolean gate."""
    return {
        "unit": "bool",
        "scale": "none",
        "multiplier": "1",
        "sign": "unsigned",
        "type": "bool",
        "quantization": "exact",
        "formula_id": formula,
        "window_bars": window_bars,
        "parents": parents,
        "source": note,
    }


def _field_lineage(
    strategy: StrategyInputs, anchor: OpenAnchor, records: list[FieldRecord]
) -> dict[str, dict[str, Any]]:
    """Per-field provenance (ADR-002-018 §10 derived-Critical-Input lineage).

    Each entry carries the parent values it is derived from, the transform
    identity, the causal window it reads, the published type/sign, the
    unit/scale/multiplier triple in the shape
    ``config/tos_runtime/paper/critical_input_policy.yaml`` uses (a token for
    ``scale``, a number for ``multiplier``), and the range actually observed in
    this run.
    """
    cfg = strategy.entry_config
    bar_parents = ["parquet:minute_bar"]
    spec: dict[str, dict[str, Any]] = {
        "open_x100": _price_field("bar_open", bar_parents, "bar open, as loaded"),
        "high_x100": _price_field("bar_high", bar_parents, "bar high, as loaded"),
        "low_x100": _price_field("bar_low", bar_parents, "bar low, as loaded"),
        "close_x100": _price_field(
            "bar_close", bar_parents, "MarketContext.current_price (the bar close)"
        ),
        "volume": {
            "unit": "contract",
            "scale": "unit",
            "multiplier": "1",
            "sign": "unsigned",
            "type": "int",
            "quantization": "exact",
            "formula_id": "bar_volume",
            "window_bars": 1,
            "parents": bar_parents,
            "source": "bar volume, as loaded (already integral)",
        },
        "session_token": {
            "unit": "opaque_token",
            "scale": "none",
            "multiplier": "1",
            "sign": "unsigned",
            "type": "str",
            "quantization": "exact",
            "formula_id": "kst_session_date",
            "window_bars": None,
            "parents": ["bar:timestamp_kst"],
            "source": (
                "the bar's KST date. Futures is day-only, so the date IS the "
                "session; the token stays opaque (no market hours are read "
                "from it)"
            ),
        },
        "vwap_x100": _price_field(
            "session_anchored_vwap_typical_price_volume_weighted",
            ["parquet:minute_bar", "session_start_index"],
            "shared/backtest/market_context_replay.py::iter_contexts — "
            "sum((h+l+c)/3 * v) / sum(v) from the session's first bar through "
            "this bar",
            window_bars=None,
        ),
        "atr14_x100": _price_field(
            "atr_partial_p14_backtest_indicator_engine",
            bar_parents,
            "shared/indicators/engine.py::backtest_indicator_engine "
            "IndicatorSpec('atr_partial', period=14), trailing only",
            window_bars=14,
        ),
        "z_x1000": {
            "unit": "atr",
            "scale": "thousandths",
            "multiplier": "1000",
            "sign": "signed",
            "type": "int",
            "quantization": "truncate_toward_zero",
            "formula_id": "vwap_extension_z",
            "window_bars": None,
            "parents": ["close_x100", "vwap_x100", "atr14_x100"],
            "source": ("SetupDVWAPReversion.vwap_extension_z — (close - vwap) / atr14"),
        },
        "hi_vol": _bool_field(
            "causal_atr_percentile_regime_gate_pass",
            ["atr14_x100", "trailing_atr_window"],
            "SetupDVWAPReversion._vol_reference + check() step 3: "
            f"atr14 >= min_atr_ratio({cfg.min_atr_ratio}) * percentile(trailing "
            f"{cfg.vol_window_bars} past ATRs, {cfg.vol_percentile}); PERMISSIVE "
            f"(true) below vol_warmup_bars({cfg.vol_warmup_bars}); false when "
            "the gate was never evaluated on this bar",
            cfg.vol_window_bars,
        ),
        "stall_ok": _bool_field(
            "causal_recent_range_stall_guard_pass",
            ["close_x100", "trailing_close_window", "atr14_x100"],
            "SetupDVWAPReversion._self_range + check() step 5: the spike must be "
            f"within stall_buffer_atr_mult({cfg.stall_buffer_atr_mult}) * atr14 "
            f"of the max/min of the prior {cfg.range_window_bars} closes; "
            f"PERMISSIVE (true) below range_warmup_bars({cfg.range_warmup_bars}); "
            "false when the guard was never evaluated on this bar",
            cfg.range_window_bars,
        ),
        "reversal_ok": _bool_field(
            "reversal_confirmation_pass",
            ["close_x100", "prev_close", "vwap_x100", "atr14_x100"],
            "check() step 6: price turned back toward VWAP versus the prior "
            "close and abs(prev_z) - abs(z) >= reversal_confirm_atr_mult("
            f"{cfg.reversal_confirm_atr_mult}); "
            f"enabled={cfg.reversal_confirm_enabled}, "
            f"requires_price_turn={cfg.reversal_confirm_requires_price_turn}; "
            "false when confirmation was never evaluated on this bar",
            1,
        ),
        "entry_window": _bool_field(
            "minutes_since_open_within_entry_window",
            ["bar:timestamp_kst", "market_open_kst"],
            f"check() step 1: valid_minutes_min({cfg.valid_minutes_min}) <= "
            "minutes_since_open <= no_entry_after_minutes_since_open("
            f"{cfg.no_entry_after_minutes_since_open}), anchored on "
            f"{anchor.kst} ({anchor.source})",
            None,
        ),
        "vwap_reverted": _bool_field(
            "abs_z_le_vwap_revert_band",
            ["z_x1000"],
            f"abs(z) <= {strategy.vwap_revert_band}, from "
            f"{strategy.vwap_revert_band_source}. See declared differences D3 "
            "and D7",
            None,
        ),
        "eod": _bool_field(
            "bar_time_ge_eod_close_time",
            ["bar:timestamp_kst", "eod_close_time"],
            "bar KST time >= SetupTargetExitConfig.eod_close_time "
            f"({strategy.exit_config.eod_close_time.isoformat()}, built from "
            "strategy.exit.params by the legacy config class itself); "
            f"eod_close_enabled={strategy.exit_config.eod_close_enabled}",
            None,
        ),
    }
    for key, entry in spec.items():
        entry["range_observed"] = _observed_range(records, key)
    return spec


def _runtime_versions() -> dict[str, str]:
    """Interpreter and numeric-library versions (ADR-002-018 §10 lineage)."""

    def version(module_name: str) -> str:
        try:
            module = __import__(module_name)
        except ImportError:
            return "unavailable"
        return str(getattr(module, "__version__", "unknown"))

    return {
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "numpy": version("numpy"),
        "pandas": version("pandas"),
        "pyarrow": version("pyarrow"),
    }


def _git_identity(repo_root: Path) -> dict[str, Any]:
    """Record the worktree's commit and whether it is dirty (provenance only)."""

    def run_git(args: list[str]) -> str | None:
        try:
            done = subprocess.run(
                ["git", "-C", str(repo_root), *args],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return None
        return done.stdout.strip() if done.returncode == 0 else None

    commit = run_git(["rev-parse", "HEAD"])
    status = run_git(["status", "--porcelain"])
    return {
        "repo_root": str(repo_root),
        "commit": commit or "unknown",
        "branch": run_git(["rev-parse", "--abbrev-ref", "HEAD"]) or "unknown",
        "dirty": bool(status) if status is not None else None,
    }


def _declared_differences(
    strategy: StrategyInputs, produced: ProducedBars
) -> list[dict[str, Any]]:
    """The ten ways this field set is not the legacy strategy, each with a reason."""
    cfg = strategy.entry_config
    measurement = D7_MEASUREMENT
    return [
        {
            "id": "D1",
            "item": "min_confidence",
            "value": cfg.min_confidence,
            "note": (
                "The legacy confidence gate has no published field: the DSL has "
                "no arithmetic and the Proposal no numeric slot. The AND of "
                "these fields is a SUPERSET of 'legacy fired'."
            ),
        },
        {
            "id": "D2",
            "item": "regime gates",
            "value": {
                "long_blocked_regimes": strategy.entry_params.get(
                    "long_blocked_regimes"
                ),
                "short_blocked_regimes": strategy.entry_params.get(
                    "short_blocked_regimes"
                ),
                "regime_gate_enabled": bool(
                    (strategy.entry_params.get("regime_gate") or {}).get(
                        "enabled", False
                    )
                ),
            },
            "note": (
                "Adapter-level gates outside SetupDVWAPReversion.check(); out "
                "of scope by the kickoff plan §4 decision 5."
            ),
        },
        {
            "id": "D3",
            "item": "vwap_reverted is a band, not the legacy target",
            "value": {
                "band_atr_mult": strategy.vwap_revert_band,
                "source": strategy.vwap_revert_band_source,
            },
            "note": (
                "The legacy VWAP-revert target equals the session VWAP for "
                "every qualifying entry (target_distance = max(|entry-vwap|, "
                "min_reward_risk*stop_atr_mult*atr); at |z| >= extreme_atr_mult "
                f"({cfg.extreme_atr_mult}) the first term beats "
                f"{cfg.min_reward_risk * cfg.stop_atr_mult}, a premise this "
                "producer asserts at load time). But 'price reached the VWAP' "
                "is direction-dependent and cannot be one direction-agnostic "
                "bool, so this field is the direction-agnostic BAND form. It is "
                "NOT the legacy condition in either direction — see D7."
            ),
        },
        {
            "id": "D4",
            "item": "eod",
            "value": strategy.exit_config.eod_close_time.isoformat(),
            "note": (
                "Built by SetupTargetExitConfig itself from "
                "strategy.exit.params. SetupTargetExit._should_eod_close "
                "additionally consults is_trading_day_kst and "
                "effective_close_time, which clamps the cutoff to the calendar "
                "constant MARKET_CLOSE_TIME = 15:30 (shared/calendar.py). "
                "Neither can move this cutoff for bars present in a futures "
                "minute dataset (bars exist only on trading days, and the "
                "configured cutoff is before 15:30), so they are not reproduced."
            ),
        },
        {
            "id": "D5",
            "item": "unevaluated gate fields",
            "value": ["hi_vol", "stall_ok", "reversal_ok"],
            "note": (
                "False when check() returned before that gate ran — "
                "fail-closed. entry_window is NOT false on most of those bars: "
                "an in-window reject (vol_below_gate, not_extreme, "
                "still_trending_*, awaiting_reversal_confirm, low_confidence) "
                "keeps entry_window true. The entry AND is unaffected because "
                "the gate that rejected has its OWN field false — or, for "
                "not_extreme, because the |z_x1000| comparison is false. Only "
                "before_window / after_cutoff make entry_window itself false."
            ),
        },
        {
            "id": "D6",
            "item": "omitted bars",
            "value": len(produced.omitted),
            "note": (
                "A bar whose atr/vwap/close cannot carry their published "
                "meaning is evaluated (the causal deques advance as in the "
                "legacy replay) but NOT emitted, because a sentinel z_x1000 of "
                "0 reads as 'at VWAP' to any band comparison. Ids and reasons "
                "are listed under dataset.omitted_bars. A non-finite value "
                "aborts the run instead of being counted here."
            ),
        },
        {
            "id": "D7",
            "item": "moving session-VWAP sign exit vs the legacy frozen target",
            "value": measurement,
            "d7_measurement_generator": D7_GENERATOR_COMMAND,
            "note": (
                "An exit rule written on the published fields compares "
                "against the session VWAP as it MOVES bar by bar; the legacy "
                "exit (shared/strategy/exit/setup_target_exit.py) compares "
                "against a take_profit PRICE frozen on the signal at entry "
                "time. The MEASURED rule is the strongest moving form a "
                "deployment can write — the z-SIGN crossing (z_x1000 >= 0 for a "
                "long fade, <= 0 for a short), which is direction-specific and "
                "therefore not the published vwap_reverted field. On the parity "
                f"window ({measurement['window']}, anchor "
                f"{measurement['market_open_kst']}) that rule leaves earlier on "
                f"{measurement['earlier']} of {measurement['entries']} entries, "
                f"on the same bar for {measurement['identical']}, later on "
                f"{measurement['later']}, and neither reaches on "
                f"{measurement['never_either']}; median lead "
                f"{measurement['median_lead_bars']} bars, max "
                f"{measurement['max_lead_bars']} (over "
                f"{measurement['lead_bars_measured_over']} entries where both "
                "rules reached). The divergence of the direction-agnostic BAND "
                "field vwap_reverted itself (D3) is a DIFFERENT and so far "
                "UNMEASURED quantity — these counts must not be read as its "
                "error bar. Publishing the frozen target would need a per-entry "
                "price the DSL has no slot for (DSL-G5), so the difference is "
                "declared, not closed."
            ),
        },
        {
            "id": "D8",
            "item": "quantization",
            "value": {
                "prices": "half_up",
                "z_x1000": "truncate_toward_zero",
                "price_scale": PRICE_SCALE,
                "z_scale": Z_SCALE,
            },
            "note": (
                "Prices and ATR are magnitudes rounded half-up (monotone, so "
                "the Bar OHLC relations survive scaling); a published integer "
                f"differs from the real value by at most 0.5/{PRICE_SCALE} "
                "index point. z_x1000 truncates toward zero so it is symmetric "
                "about zero AND conservative at the trigger: abs(z_x1000) >= "
                "trunc(extreme_atr_mult*1000) holds only when abs(z) >= "
                "extreme_atr_mult really does, so a policy written on the "
                "integer NEVER fires where the legacy setup did not. The cost "
                f"is that abs(z) is understated by up to 1/{Z_SCALE} ATR, so a "
                "bar whose abs(z) sits in the last 0.001 ATR below the "
                "threshold reads as below it — the safe side."
            ),
        },
        {
            "id": "D9",
            "item": "trend_filter_enabled",
            "value": cfg.trend_filter_enabled,
            "note": (
                "The session-VWAP-drift gate is causal state inside check() "
                "with no published field and no Critical Input declaration. "
                "This producer REFUSES to run while it is enabled rather than "
                "emit a field set that cannot reproduce the legacy decision. It "
                "ships off in the YAML, so the refusal is latent today; "
                "enabling it is gated on publishing and declaring a trend field."
            ),
        },
        {
            "id": "D10",
            "item": "ATR stop (stop_atr_mult)",
            "value": cfg.stop_atr_mult,
            "note": (
                f"The legacy signal carries a {cfg.stop_atr_mult}x-ATR hard "
                "stop. It is OUT OF "
                "SCOPE for the first slice by operator decision (kickoff §4 "
                "decision 6): the DSL has no entry price and no numeric "
                "Proposal output, and protective classification is PAC's to "
                "make, not a strategy's to self-declare. An intended, approved "
                "difference — not an omission."
            ),
        },
    ]


def _stitch_lineage(
    stitch: StitchedInputs | None, non_target_segment_bars: int
) -> dict[str, Any] | None:
    """The cross-contract block both B1a and B2 record, or ``None``.

    Shared rather than restated on each side: the two sidecars are compared
    field by field, and two spellings of the same block is how they would come
    to disagree about a window they both read correctly.
    """
    if stitch is None:
        return None
    manifest = stitch.manifest
    return {
        "manifest_path": str(manifest.path) if manifest.path else None,
        "manifest_sha256": manifest.sha256,
        "method": manifest.method,
        "symbol": manifest.symbol,
        "segments": [segment.to_payload() for segment in manifest.segments],
        "junctions": [junction.to_payload() for junction in manifest.junctions],
        "recomputed_junctions": [item.to_payload() for item in stitch.recomputed],
        "offsets_x100": dict(sorted(stitch.offsets_x100.items())),
        # The splice day's NEW-contract partition. Read to re-derive c_x100 and
        # deliberately kept OUT of the frame: two contracts' bars on one minute
        # would hit the duplicate-timestamp refusal (plan §3.2a re-review N-3).
        "junction_recompute_only_input_files": [
            {"path": item.path, "sha256": item.sha256, "size_bytes": item.size_bytes}
            for item in stitch.recompute_input_files
        ],
        "junction_recompute_only_bars": stitch.recompute_bars,
        "target_days": [day.isoformat() for day in sorted(manifest.target_days)],
        "non_target_segment_bars_replayed_not_emitted": non_target_segment_bars,
        "source_sha256": dict(sorted(manifest.source_sha256.items())),
    }


def build_lineage(
    *,
    produced: ProducedBars,
    jsonl_bytes: bytes,
    symbol: str,
    strategy: StrategyInputs,
    contract_spec: ContractSpec,
    anchor: OpenAnchor,
    data_root: Path,
    requested_start: date,
    requested_end: date,
    min_bars_per_day: int,
    bars_loaded: int,
    bars_after_density_gate: int,
    warmup_skipped: int,
    first_session_dropped: int,
    input_files: list[InputFile],
    stitch: StitchedInputs | None = None,
) -> dict[str, Any]:
    """Assemble the lineage sidecar.

    Deliberately carries **no run timestamp and no duration**: two runs over
    the same inputs must produce identical bytes, so that a changed lineage
    means changed inputs, parameters or code — never merely a re-run.
    """
    records = produced.records
    session_dates = sorted({record.bar_kst.date() for record in records})
    as_of_values = [record.as_of_ms for record in records]

    dropped_before_replay = warmup_skipped + first_session_dropped
    if bars_after_density_gate - dropped_before_replay != produced.bars_replayed:
        raise ProduceFieldsError(
            "bar accounting does not reconcile: "
            f"{bars_after_density_gate} after the density gate minus "
            f"{dropped_before_replay} dropped before replay != "
            f"{produced.bars_replayed} replayed"
        )
    # The second half of the chain, which B2 has always asserted and this side
    # did not. It became load-bearing with the stitch segment counter (plan
    # §3.2a): a replayed bar now leaves by one of exactly three doors —
    # emitted, omitted as unusable, or dropped as non-target — and a counter
    # that misses one would publish a lineage whose own numbers do not add up
    # while B3 compared the file happily.
    accounted = len(records) + len(produced.omitted) + produced.non_target_segment_bars
    if accounted != produced.bars_replayed:
        raise ProduceFieldsError(
            f"{produced.bars_replayed} replayed != {len(records)} emitted + "
            f"{len(produced.omitted)} omitted + "
            f"{produced.non_target_segment_bars} non-target stitch-segment bars"
        )
    if bars_loaded > 0 and not input_files:
        raise ProduceFieldsError(
            f"{bars_loaded} bars were loaded but no Parquet partition was found "
            f"under {data_root} for {symbol} in "
            f"{requested_start}..{requested_end} — the lineage would claim an "
            "input list it does not have"
        )

    return {
        "lineage_schema_version": LINEAGE_SCHEMA_VERSION,
        "tool": {
            "name": "tools/tos_cp3/produce_fields.py",
            "version": f"tos_cp3/{TOS_CP3_VERSION}",
            "source_id": SOURCE_ID,
            "git": _git_identity(REPO_ROOT),
            "runtime": _runtime_versions(),
        },
        "common_mode": (
            "This is NOT independent corroboration of the band math. Both sides "
            "of the CP-3 comparison read ONE implementation — "
            "shared/decision/setups/vwap_reversion.py — which this producer "
            "drives bar by bar (reading SetupDVWAPReversion.last_eval and "
            "SetupDVWAPReversion.vwap_extension_z) rather than restating. A "
            "parity run therefore confirms the POLICY, not the indicator "
            "formulas: a defect in the shared implementation appears on both "
            "sides identically (ADR-002-018 §10)."
        ),
        "dataset": {
            "symbol": symbol,
            "instrument": symbol,
            "asset_class": strategy.asset_class,
            "timeframe": "minute",
            "data_root": str(data_root),
            "requested_start": requested_start.isoformat(),
            "requested_end": requested_end.isoformat(),
            "min_bars_per_day": min_bars_per_day,
            "min_volume": 0,
            "bars_loaded": bars_loaded,
            "bars_after_density_gate": bars_after_density_gate,
            "replay_warmup_bars_skipped": warmup_skipped,
            "first_session_bars_dropped_no_prior_close": first_session_dropped,
            "bars_replayed": produced.bars_replayed,
            "bars_emitted": len(records),
            "omitted_bars": {
                "count": len(produced.omitted),
                "reasons": sorted({reason for _, reason in produced.omitted}),
                "raw_event_ids": [
                    raw_event_id
                    for raw_event_id, _ in produced.omitted[:OMITTED_ID_LIST_CAP]
                ],
                "raw_event_ids_truncated": len(produced.omitted) > OMITTED_ID_LIST_CAP,
            },
            "session_dates": len(session_dates),
            "first_session_date": session_dates[0].isoformat(),
            "last_session_date": session_dates[-1].isoformat(),
            "first_raw_event_id": records[0].raw_event_id,
            "last_raw_event_id": records[-1].raw_event_id,
            "first_as_of_ms": as_of_values[0],
            "last_as_of_ms": as_of_values[-1],
            "input_files": [
                {
                    "path": item.path,
                    "sha256": item.sha256,
                    "size_bytes": item.size_bytes,
                }
                for item in input_files
            ],
            "input_file_count": len(input_files),
            # Plan §3.2a: part of B3's WINDOW IDENTITY, so it is present on
            # EVERY run. ``None`` means "no manifest" (a legacy data root) —
            # NOT "no splice": the producer writes ``stitch.json`` even on a
            # day with zero junctions, so a producer session is always
            # non-null and a legacy B2 paired with a stitched B1a is refused.
            "stitch_manifest_sha256": stitch.manifest.sha256 if stitch else None,
            "stitch": _stitch_lineage(stitch, produced.non_target_segment_bars),
        },
        "strategy": {
            "path": str(strategy.path),
            "sha256": strategy.sha256,
            "entry_type": SetupDVWAPReversion.REGISTRY_NAME,
            "entry_params_yaml": strategy.entry_params,
            "exit_params_yaml": strategy.exit_params,
            "entry_params_used": strategy.entry_config.model_dump(mode="json"),
            "vwap_revert_band": strategy.vwap_revert_band,
            "vwap_revert_band_source": strategy.vwap_revert_band_source,
            "market_open_kst": anchor.kst,
            "market_open_source": anchor.source,
            "contract_spec": {
                "name": contract_spec.name,
                "multiplier_krw_per_point": contract_spec.multiplier_krw_per_point,
                "tick_size_points": contract_spec.tick_size_points,
                "tick_value_krw": contract_spec.tick_value_krw,
                "source": "config/execution.yaml::futures_contract_spec",
            },
        },
        "encoding": {
            "journal_required_keys": list(JOURNAL_REQUIRED_KEYS),
            "journal_required_keys_source": (
                "mirrors tos/runtime/src/tos_runtime/marketfeed/journal.py"
                "::_REQUIRED_KEYS — restated as a literal because the import "
                "firewall forbids importing it from tools/"
            ),
            "no_floats_in_fields": True,
            "field_order": list(FIELD_ORDER),
            "as_of_ms_semantics": (
                "epoch milliseconds of the bar's labelled KST minute — the same "
                "instant MarketContextReplay stamps on MarketContext.now and "
                "therefore the instant entry_window and eod are compared "
                "against. The dataset labels a minute bar with its opening "
                "minute; label+60s would be the wall-clock end of the bar but "
                "would desynchronise as_of_ms from the session fields computed "
                "on the label (a 15:15 bar would carry a 15:16 as_of_ms)."
            ),
        },
        "fields": _field_lineage(strategy, anchor, records),
        "declared_differences": _declared_differences(strategy, produced),
        "output": {
            "jsonl": FIELDS_FILENAME,
            "jsonl_sha256": hashlib.sha256(jsonl_bytes).hexdigest(),
            "jsonl_bytes": len(jsonl_bytes),
            "jsonl_lines": len(records),
        },
    }


def render_lineage(lineage: dict[str, Any]) -> bytes:
    """Serialize the lineage sidecar to the exact bytes written to disk."""
    return (
        json.dumps(lineage, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    ).encode("utf-8")


# ---------------------------------------------------------------------------
# D7 measurement (moving VWAP vs the legacy frozen target)
# ---------------------------------------------------------------------------


def measure_moving_vs_frozen_exit(
    df: Any,
    *,
    symbol: str,
    strategy: StrategyInputs,
    contract_spec: ContractSpec,
    anchor: OpenAnchor,
) -> dict[str, Any]:
    """Measure D7: when does a moving-VWAP exit differ from the legacy target?

    For every bar the legacy setup FIRES on, walk the remaining bars of that
    session and record the first bar at which

    * the **frozen** rule triggers — the legacy ``take_profit`` price (fixed on
      the signal) is reached, exactly as ``SetupTargetExit`` compares it, and
    * the **moving** rule triggers — price is back at the session VWAP on the
      entry's side (``z >= 0`` for a long fade, ``z <= 0`` for a short), which
      is the strongest form a tenant policy can write on the published fields.

    Returns the counts the lineage's D7 entry quotes. Kept beside the producer
    rather than in a scratch script so the number in the sidecar can be
    regenerated by the same code that documents it: ``--measure-d7`` prints the
    :data:`D7_MEASUREMENT` literal from this function's output.

    The buckets are disjoint and exhaustive — ``earlier + identical + later +
    never_either == entries`` — and every lead is session-bounded, because the
    inner walk stops at the session boundary.
    """
    setup = SetupDVWAPReversion(config=strategy.entry_config)
    replay = MarketContextReplay(
        df=df,
        symbol=symbol,
        macro_snapshot=None,
        scheduled_events=[],
        contract_spec=contract_spec,
        market_open_hour=anchor.hour,
        market_open_minute=anchor.minute,
        min_volume=0,
    )

    contexts: list[Any] = []
    entries: list[tuple[int, str, float]] = []  # (index, direction, take_profit)
    for ctx in replay.iter_contexts():
        signal = setup.check(ctx)
        contexts.append(ctx)
        if signal is not None:
            entries.append((len(contexts) - 1, signal.direction, signal.take_profit))

    # Buckets are disjoint and exhaustive, and a "lead" is a number only when
    # BOTH rules triggered inside the session. The first draft measured the
    # frozen-never case to the end of the whole SERIES and reported a
    # 32591-bar maximum — not a quantity about any session.
    earlier = identical = later = never_either = 0
    earlier_frozen_never = later_moving_never = 0
    leads: list[int] = []
    for index, direction, take_profit in entries:
        session = contexts[index].now.date()
        frozen_at: int | None = None
        moving_at: int | None = None
        for offset in range(index + 1, len(contexts)):
            later_ctx = contexts[offset]
            if later_ctx.now.date() != session:
                break
            price = float(later_ctx.current_price)
            atr = float(later_ctx.atr_14)
            if frozen_at is None:
                reached = (
                    price >= take_profit
                    if direction == "long"
                    else price <= take_profit
                )
                if reached:
                    frozen_at = offset
            if moving_at is None and atr > 0:
                z_now = SetupDVWAPReversion.vwap_extension_z(
                    price, float(later_ctx.vwap), atr
                )
                reverted = z_now >= 0 if direction == "long" else z_now <= 0
                if reverted:
                    moving_at = offset
            if frozen_at is not None and moving_at is not None:
                break
        if frozen_at is None and moving_at is None:
            never_either += 1
        elif moving_at is None:
            later += 1
            later_moving_never += 1
        elif frozen_at is None:
            earlier += 1
            earlier_frozen_never += 1
        elif moving_at < frozen_at:
            earlier += 1
            leads.append(frozen_at - moving_at)
        elif moving_at == frozen_at:
            identical += 1
        else:
            later += 1

    return {
        "window": f"{symbol} {df['timestamp'].dt.date.iloc[0]}"
        f"..{df['timestamp'].dt.date.iloc[-1]}",
        "market_open_kst": anchor.kst,
        "min_bars_per_day": DEFAULT_MIN_BARS_PER_DAY,
        "entries": len(entries),
        "earlier": earlier,
        "earlier_frozen_never_reached_in_session": earlier_frozen_never,
        "identical": identical,
        "later": later,
        "later_moving_never_reached_in_session": later_moving_never,
        "never_either": never_either,
        "median_lead_bars": int(statistics.median(leads)) if leads else 0,
        "max_lead_bars": max(leads) if leads else 0,
        "lead_bars_measured_over": len(leads),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunResult:
    """What a completed run wrote, for the CLI summary and for tests."""

    records: list[FieldRecord]
    jsonl_bytes: bytes
    lineage: dict[str, Any]
    lineage_bytes: bytes
    jsonl_path: Path
    lineage_path: Path


def _bar_accounting(df: Any) -> tuple[int, int]:
    """Return (warmup bars skipped, first-session bars dropped for no prior close).

    ``MarketContextReplay`` yields from index ``DEFAULT_WARMUP_BARS`` onward and
    additionally skips every bar whose session has no previous session in the
    frame — which is exactly the first session date. Making both counts
    explicit is what lets ``gated - dropped == replayed`` be asserted rather
    than assumed.
    """
    total = int(len(df))
    warmup = min(DEFAULT_WARMUP_BARS, total)
    first_date = df["timestamp"].dt.date.iloc[0]
    first_session_bars = int((df["timestamp"].dt.date == first_date).sum())
    return warmup, max(0, first_session_bars - warmup)


@dataclass(frozen=True)
class LoadedWindow:
    """Everything resolved from the CLI arguments before any production."""

    strategy: StrategyInputs
    contract_spec: ContractSpec
    df: Any
    bars_loaded: int
    anchor: OpenAnchor
    input_files: list[InputFile]
    #: Present only for a stitched window (plan §3.2a); ``None`` otherwise.
    stitch: StitchedInputs | None = None

    @property
    def emit_days(self) -> frozenset[date] | None:
        """The days whose bars may be EMITTED, or ``None`` for every day."""
        return self.stitch.manifest.target_days if self.stitch else None

    @property
    def stitch_manifest_sha256(self) -> str | None:
        """The identity B3 compares. ``None`` = no manifest (legacy data root)."""
        return self.stitch.manifest.sha256 if self.stitch else None


def load_window(
    *,
    data_root: Path,
    symbol: str,
    start: date,
    end: date,
    strategy_yaml: Path,
    min_bars_per_day: int,
    market_open: str,
    stitch_manifest: Path | None = None,
) -> LoadedWindow:
    """Resolve strategy, contract, bars and open anchor for one window.

    Shared by :func:`run` and the ``--measure-d7`` path so the measurement is
    taken over exactly the window a produce would use — a second, slightly
    different loader here is how the number in the sidecar would come to
    describe a window nobody published.

    **It is also the ONE alignment function** (plan §3.2a HIGH-1). B2
    (``tools/tos_cp3/emit_legacy_decisions.py``) builds its frame through this
    very call and the live producer reuses the same helpers, so a stitched
    seed does not need three implementations to agree — there is one. Had the
    alignment been a B1a flag instead, every stitched session would have been
    an automatic B3 refusal on input digests and line counts.

    Args:
        stitch_manifest: path to a ``stitch.json``. With it, the frame is read
            from exactly the manifest's ``(contract, day)`` pairs, the older
            contract's OHLC is shifted by the integer ``c_x100``, and the
            constant is re-derived from the stored bars and asserted against
            the manifest.
    """
    strategy = load_strategy_inputs(strategy_yaml)
    registry = ContractSpecRegistry.from_yaml(str(REPO_ROOT / "config/execution.yaml"))
    contract_spec = resolve_contract_spec(symbol, registry)
    _assert_scale_covers_tick(contract_spec, PRICE_SCALE)

    try:
        manifest = resolve_session_manifest(
            data_root, symbol=symbol, stitch_manifest=stitch_manifest
        )
    except StitchError as exc:
        raise ProduceFieldsError(str(exc)) from exc

    if manifest is None:
        input_files = discover_input_files(
            data_root,
            asset_class=strategy.asset_class,
            symbol=symbol,
            start=start,
            end=end,
        )
        df, bars_loaded = load_bars(
            data_root,
            asset_class=strategy.asset_class,
            symbol=symbol,
            start=start,
            end=end,
            min_bars_per_day=min_bars_per_day,
        )
        stitch = None
    else:
        _assert_window_matches_manifest(manifest, start=start, end=end)
        try:
            df, bars_loaded, input_files, stitch = load_stitched_bars(
                data_root,
                asset_class=strategy.asset_class,
                manifest=manifest,
                min_bars_per_day=min_bars_per_day,
            )
        except StitchError as exc:
            raise ProduceFieldsError(str(exc)) from exc

    session_dates = df["timestamp"].dt.date
    anchor = resolve_open_anchor(
        cli_value=market_open,
        first_session=session_dates.iloc[0],
        last_session=session_dates.iloc[-1],
    )
    return LoadedWindow(
        strategy=strategy,
        contract_spec=contract_spec,
        df=df,
        bars_loaded=bars_loaded,
        anchor=anchor,
        input_files=input_files,
        stitch=stitch,
    )


def _assert_window_matches_manifest(
    manifest: StitchManifest, *, start: date, end: date
) -> None:
    """``--start``/``--end`` must be EXACTLY the manifest's span.

    The manifest, not the date range, selects the partitions — but the range
    is half of B3's window identity (``window_start`` / ``window_end``), so
    the declared window has to be true of the frame that was actually read.

    **Both directions are refused** (review LOW-1). Narrower was always
    refused: the manifest would reach outside the window it claims. Wider was
    accepted by the first cut and is just as wrong in the direction that
    matters — ``--start 2026-09-01`` over a manifest beginning 2026-10-02
    publishes a sidecar claiming a September window, and because B1a and B2
    take the SAME flag they would both claim it, so B3 compares two equal
    labels and never notices. The check has to be here or nowhere. There is no
    case for a wider window: with a manifest the span IS the manifest's, and a
    caller who wants a different one wants a different manifest.
    """
    days = manifest.all_days
    if (start, end) != (days[0], days[-1]):
        raise ProduceFieldsError(
            f"--start {start} --end {end} is not the stitch manifest's own span "
            f"{days[0]}..{days[-1]}. The declared window is half of what B3 "
            "compares and both sides take this same flag, so a window that is "
            "not exactly the manifest's would be agreed on by both and caught "
            "by neither"
        )


def render_d7_literal(measurement: dict[str, Any]) -> str:
    """Format a measurement as the :data:`D7_MEASUREMENT` literal to paste."""
    lines = ["D7_MEASUREMENT: dict[str, Any] = {"]
    for key, value in measurement.items():
        rendered = json.dumps(value, ensure_ascii=False)
        if key == "min_bars_per_day":
            rendered = "DEFAULT_MIN_BARS_PER_DAY"
        lines.append(f'    "{key}": {rendered},')
    lines.append("}")
    return "\n".join(lines)


def run(
    *,
    data_root: Path,
    symbol: str,
    start: date,
    end: date,
    strategy_yaml: Path,
    out_dir: Path,
    min_bars_per_day: int = DEFAULT_MIN_BARS_PER_DAY,
    market_open: str = "auto",
    stitch_manifest: Path | None = None,
) -> RunResult:
    """Produce the field JSONL and lineage sidecar for one dataset window."""
    window = load_window(
        data_root=data_root,
        symbol=symbol,
        start=start,
        end=end,
        strategy_yaml=strategy_yaml,
        min_bars_per_day=min_bars_per_day,
        market_open=market_open,
        stitch_manifest=stitch_manifest,
    )
    strategy = window.strategy
    contract_spec = window.contract_spec
    df = window.df
    bars_loaded = window.bars_loaded
    anchor = window.anchor
    input_files = window.input_files
    warmup_skipped, first_session_dropped = _bar_accounting(df)

    produced = produce_bars(
        df,
        symbol=symbol,
        strategy=strategy,
        contract_spec=contract_spec,
        anchor=anchor,
        emit_days=window.emit_days,
    )
    jsonl_bytes = render_jsonl(produced.records)
    lineage = build_lineage(
        produced=produced,
        jsonl_bytes=jsonl_bytes,
        symbol=symbol,
        strategy=strategy,
        contract_spec=contract_spec,
        anchor=anchor,
        data_root=data_root,
        requested_start=start,
        requested_end=end,
        min_bars_per_day=min_bars_per_day,
        bars_loaded=bars_loaded,
        bars_after_density_gate=int(len(df)),
        warmup_skipped=warmup_skipped,
        first_session_dropped=first_session_dropped,
        input_files=input_files,
        stitch=window.stitch,
    )
    lineage_bytes = render_lineage(lineage)

    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / FIELDS_FILENAME
    lineage_path = out_dir / LINEAGE_FILENAME
    jsonl_path.write_bytes(jsonl_bytes)
    lineage_path.write_bytes(lineage_bytes)
    return RunResult(
        records=produced.records,
        jsonl_bytes=jsonl_bytes,
        lineage=lineage,
        lineage_bytes=lineage_bytes,
        jsonl_path=jsonl_path,
        lineage_path=lineage_path,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="produce_fields",
        description=(
            "CP-3 B1a — turn Parquet minute bars into the per-bar Critical "
            "Input field JSONL plus a lineage sidecar, using the legacy Setup D "
            "implementation's own math."
        ),
    )
    parser.add_argument(
        "--data-root",
        required=True,
        type=Path,
        help=(
            "Market-data Parquet root (e.g. "
            "/home/deploy/project/kis_unified_sts/data/market). Required: the "
            "tree is gitignored and exists only in the primary checkout."
        ),
    )
    parser.add_argument(
        "--symbol", required=True, help="Instrument code, e.g. 101S6000"
    )
    parser.add_argument(
        "--start", required=True, type=date.fromisoformat, help="Inclusive KST date"
    )
    parser.add_argument(
        "--end", required=True, type=date.fromisoformat, help="Inclusive KST date"
    )
    parser.add_argument(
        "--strategy-yaml",
        required=True,
        type=Path,
        help="Setup D strategy YAML — the source of every threshold and window",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help=(
            "Output directory for the two artifacts. Required unless "
            "--measure-d7 is given, which writes nothing."
        ),
    )
    parser.add_argument(
        "--measure-d7",
        action="store_true",
        help=(
            "Do not produce fields: measure declared difference D7 (the moving "
            "session-VWAP sign exit vs the legacy frozen take-profit) over the "
            "same window and print the D7_MEASUREMENT literal to paste back "
            "into this module."
        ),
    )
    parser.add_argument(
        "--min-bars-per-day",
        type=int,
        default=DEFAULT_MIN_BARS_PER_DAY,
        help=(
            "Drop sessions with fewer bars than this before replay (default "
            f"{DEFAULT_MIN_BARS_PER_DAY}, matching the walk-forward script; 0 "
            "is the explicit opt-out). Recorded in the lineage either way."
        ),
    )
    parser.add_argument(
        "--market-open",
        default="auto",
        help=(
            "Futures open anchor as HH:MM, or 'auto' (default) for the era "
            f"rule: {PRE_CUTOVER_OPEN[0]:02d}:{PRE_CUTOVER_OPEN[1]:02d} for "
            f"data before {OPEN_ANCHOR_CUTOVER}, else "
            "config/market_schedule.yaml. A window straddling the cutover is "
            "refused."
        ),
    )
    parser.add_argument(
        "--stitch-manifest",
        type=Path,
        default=None,
        help=(
            "Path to a cross-contract seed manifest (stitch.json, plan 3.2a). "
            "With it the frame is read from exactly the manifest's "
            "(contract, day) pairs and the previous month's OHLC is shifted by "
            "the manifest's integer c_x100; the constant is re-derived from the "
            "stored bars and the run refuses if it disagrees. REQUIRED when a "
            "stitch.json sits directly under --data-root, and must match the "
            "B2 run this artifact is joined to."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.measure_d7:
        try:
            window = load_window(
                data_root=args.data_root,
                symbol=args.symbol,
                start=args.start,
                end=args.end,
                strategy_yaml=args.strategy_yaml,
                min_bars_per_day=args.min_bars_per_day,
                market_open=args.market_open,
                stitch_manifest=args.stitch_manifest,
            )
            measurement = measure_moving_vs_frozen_exit(
                window.df,
                symbol=args.symbol,
                strategy=window.strategy,
                contract_spec=window.contract_spec,
                anchor=window.anchor,
            )
        except ProduceFieldsError as exc:
            print(f"produce_fields: {exc}", file=sys.stderr)
            return 2
        print(render_d7_literal(measurement))
        print(
            "# paste the block above over D7_MEASUREMENT in "
            "tools/tos_cp3/produce_fields.py",
            file=sys.stderr,
        )
        return 0
    if args.out is None:
        parser.error("--out is required unless --measure-d7 is given")
    try:
        result = run(
            data_root=args.data_root,
            symbol=args.symbol,
            start=args.start,
            end=args.end,
            strategy_yaml=args.strategy_yaml,
            out_dir=args.out,
            min_bars_per_day=args.min_bars_per_day,
            market_open=args.market_open,
            stitch_manifest=args.stitch_manifest,
        )
    except ProduceFieldsError as exc:
        print(f"produce_fields: {exc}", file=sys.stderr)
        return 2

    lineage = result.lineage
    dataset = lineage["dataset"]
    print(f"wrote {result.jsonl_path} ({lineage['output']['jsonl_lines']} lines)")
    print(f"wrote {result.lineage_path}")
    print(f"jsonl sha256: {lineage['output']['jsonl_sha256']}")
    print(
        "bars loaded/gated/replayed/emitted/omitted: "
        f"{dataset['bars_loaded']}/{dataset['bars_after_density_gate']}/"
        f"{dataset['bars_replayed']}/{dataset['bars_emitted']}/"
        f"{dataset['omitted_bars']['count']}"
    )
    print(
        "open anchor: "
        f"{lineage['strategy']['market_open_kst']} "
        f"({lineage['strategy']['market_open_source']})"
    )
    print(f"input parquet files: {dataset['input_file_count']}")
    print(_stitch_summary_line(dataset))
    return 0


def _stitch_summary_line(dataset: dict[str, Any]) -> str:
    """One line naming the splice, so a stitched run is never mistaken for one."""
    stitch = dataset.get("stitch")
    if stitch is None:
        return "stitch: none (single-contract window)"
    segments = " + ".join(
        f"{segment['contract']}x{len(segment['days'])}"
        for segment in stitch["segments"]
    )
    junctions = [item["c_x100"] for item in stitch["junctions"]]
    return (
        f"stitch: {segments} | junction c_x100 {junctions} | "
        f"non-target bars replayed but not emitted "
        f"{stitch['non_target_segment_bars_replayed_not_emitted']}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
