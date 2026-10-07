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

Firewall
--------
``tools/`` is inside the reverse scan of ``tools/tos_firewall_check.py``
(TOS-FW-R), so this module imports **nothing** from ``tos`` or
``tos_runtime``. The JSONL it writes is the only thing the ``tos``-side runner
(B1b) ever sees.

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
evaluated must never read as a passing gate. Concretely: on a 14:35 bar (past
``no_entry_after_minutes_since_open``) the setup returns at step 1, its
volatility window does not advance, and there is no ``hi_vol`` to report; we
emit ``hi_vol: false``. ``entry_window`` is ``false`` on the same bar, so the
tenant's entry rule (an AND over these fields plus a ``z_x1000`` comparison) is
unaffected, while the session-exit rules — which must keep working after the
entry cutoff — read only ``vwap_reverted``/``eod``/``z_x1000``, none of which
depend on a gate having been evaluated.

``stall_ok``/``reversal_ok`` are reached only on a bar that is in-window, has
usable inputs, passed ``hi_vol`` and is at a ``|z| >= extreme_atr_mult``
extreme; on every other bar they are ``false`` for the same fail-closed
reason.

Bars with no publishable ATR
----------------------------
When ``atr_14`` is 0 (a run of perfectly flat bars — 2 such bars in the real
101S6000 2025-12-01..2026-04-30 window) the extension ``z`` is undefined.
Those bars are **omitted** from the JSONL rather than filled with a sentinel,
and the lineage lists their ids and the reason. A sentinel would not be
fail-closed: the exact revert condition a LONG deployment compares is
``z_x1000 >= 0``, which a fabricated ``z_x1000 == 0`` satisfies. The same
applies to ``vwap <= 0`` and ``close <= 0`` (see :func:`_inputs_unusable`).
Omission is an output decision only — ``check()`` still runs on the bar, so
the causal deques advance exactly as they do in the legacy replay.

Declared differences from the legacy strategy
---------------------------------------------
Recorded in the lineage sidecar under ``declared_differences`` (and summarized
in the plan's §4 결정 5/6) so none of them is a silent divergence:

``D1`` ``min_confidence`` (0.6 in the deployed YAML) has no field here: the DSL
       has no arithmetic and the Proposal has no numeric slot (plan §2
       DSL-G1/G5), so the confidence gate cannot be expressed as a comparison
       over published fields. The AND of the fields this tool publishes is
       therefore a SUPERSET of "legacy fired".
``D2`` ``short_blocked_regimes`` / ``long_blocked_regimes`` and the optional
       ``regime_gate`` are adapter-level gates, not part of
       ``SetupDVWAPReversion.check()``; they are out of scope by 결정 5.
``D3`` ``vwap_reverted`` has no exact direction-agnostic legacy equivalent —
       see :data:`_VWAP_REVERTED_NOTE`.
``D4`` ``eod`` compares the bar's KST time against
       ``strategy.exit.params.eod_close_{hour,minute}`` with ``>=``, the same
       comparison ``SetupTargetExit._should_eod_close`` makes. That method
       additionally consults ``is_trading_day_kst`` and ``effective_close_time``
       (half-day clamp); neither can move the 15:15 cutoff for bars that exist
       in a futures minute dataset (bars only exist on trading days, and 15:15
       is before the 15:45 calendar close), so they are not reproduced here.

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
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
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
from tools.tos_cp3 import TOS_CP3_VERSION  # noqa: E402

#: Lineage schema version — separate from the tool version so a reader can
#: tell "values may differ" from "the sidecar is shaped differently".
LINEAGE_SCHEMA_VERSION = 1

#: Output file names inside ``--out``.
FIELDS_FILENAME = "fields.jsonl"
LINEAGE_FILENAME = "lineage.json"

#: Price scale: index points → hundredths of an index point. Exact for the
#: KOSPI200 futures tick (0.05 pt → 5 units); :func:`_assert_scale_covers_tick`
#: refuses any contract whose tick is not an integer at this scale.
PRICE_SCALE = 100
#: ATR-unit scale for the VWAP extension ``z``: thousandths of one ATR.
Z_SCALE = 1000

_VWAP_REVERTED_NOTE = (
    "The legacy VWAP-revert target is the VWAP itself for every qualifying "
    "entry (target_distance = max(|entry-vwap|, min_reward_risk*stop_atr_mult"
    "*atr); at |z| >= extreme_atr_mult = 1.8 > min_reward_risk*stop_atr_mult "
    "= 1.5 the first term wins, so entry -/+ |entry-vwap| IS the vwap). "
    "'Price reached the VWAP' is direction-dependent (z >= 0 for a long fade, "
    "z <= 0 for a short fade) and cannot be one direction-agnostic bool, so "
    "this field is the direction-agnostic BAND form |z| <= "
    "reversal_confirm_atr_mult. A deployment that wants the exact legacy "
    "condition should compare z_x1000 directly (>= 0 for LONG, <= 0 for "
    "SHORT) — direction is static per render (plan 4 decision 4), so that "
    "exact form is available and is the recommended tenant policy."
)


class ProduceFieldsError(RuntimeError):
    """Raised when inputs cannot be turned into a trustworthy field stream."""


# ---------------------------------------------------------------------------
# Scaling
# ---------------------------------------------------------------------------


def scaled_int(value: float, scale: int) -> int:
    """Scale *value* by *scale* and round half-up to an ``int``.

    Half-up means ties go toward +infinity (``-0.5`` → ``0``). It is chosen
    over :func:`round` because ``round`` is banker's rounding, whose result
    depends on the parity of the neighbouring integer — deterministic, but not
    reproducible by a reader who reimplements the scale from the sidecar.
    """
    return int(math.floor(value * scale + 0.5))


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

    @property
    def eod_enabled(self) -> bool:
        return bool(self.exit_params.get("eod_close_enabled", True))

    @property
    def eod_time(self) -> time:
        """The EOD cutoff as ``SetupTargetExitConfig.eod_close_time`` builds it."""
        return time(
            int(self.exit_params.get("eod_close_hour", 15)),
            int(self.exit_params.get("eod_close_minute", 15)),
        )


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
    return StrategyInputs(
        path=path,
        sha256=hashlib.sha256(raw_bytes).hexdigest(),
        asset_class=str(strategy.get("asset_class") or "futures"),
        entry_params=entry_params,
        exit_params=exit_params,
        entry_config=config,
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


def load_bars(
    data_root: Path,
    *,
    asset_class: str,
    symbol: str,
    start: date,
    end: date,
    min_bars_per_day: int,
) -> Any:
    """Load minute bars through the project's Parquet store.

    Uses ``ParquetMarketDataStore`` — the very object
    ``shared.storage.market_data_store.load_market_bars_for_backtest`` builds
    via ``create_market_data_store`` — constructed with an explicit ``root``
    because the market-data tree is gitignored and lives only in the primary
    checkout (the configured ``StorageConfig`` root would point at the wrong
    checkout from a worktree). Same construction as
    ``scripts/analysis/walkforward_setup_d_vwap_reversion.py::load_clean``.
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
    if min_bars_per_day > 0:
        bars_per_day = df.groupby(df["timestamp"].dt.date).size()
        healthy = set(bars_per_day[bars_per_day >= min_bars_per_day].index)
        df = df[df["timestamp"].dt.date.map(lambda d: d in healthy)].reset_index(
            drop=True
        )
    return df


# ---------------------------------------------------------------------------
# Production
# ---------------------------------------------------------------------------

#: Published field order. Fixed so the JSONL is byte-stable.
FIELD_ORDER = (
    "close",
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
    """One published observation: a bar's integer/bool field set.

    ``bar_kst`` is carried for the lineage summary and for tests; it is NOT
    published — the wire form is exactly the four keys of
    :meth:`to_json_line`.
    """

    raw_event_id: str
    instrument: str
    as_of_ms: int
    fields: dict[str, int | bool]
    bar_kst: datetime

    def to_json_line(self) -> str:
        return json.dumps(
            {
                "raw_event_id": self.raw_event_id,
                "instrument": self.instrument,
                "as_of_ms": self.as_of_ms,
                "fields": self.fields,
            },
            separators=(",", ":"),
            ensure_ascii=True,
        )


def _assert_no_floats(fields: dict[str, int | bool], raw_event_id: str) -> None:
    """Guard the kernel's hard rule: a float field is rejected at the border.

    ``tos/src/tos/marketfeed/value.py`` drops a float outright, so a float
    leaking into this JSONL would show up as a silently missing field on the
    kernel side rather than as an error here. Concretely, this fires if a
    scaling helper is ever changed to return ``value * scale`` instead of an
    ``int``.
    """
    for key, value in fields.items():
        if isinstance(value, bool):
            continue
        if not isinstance(value, int):
            raise ProduceFieldsError(
                f"{raw_event_id}: field {key!r} is {type(value).__name__}, "
                f"not int/bool: {value!r}"
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
      ``atr_partial`` is 0 and ``z = (close - vwap) / atr`` is undefined. The
      real 101S6000 2025-12-01..2026-04-30 window contains 2 such bars.
    * ``vwap <= 0`` — at ``vwap == 0`` the extension degenerates to
      ``close / atr``, "a huge FABRICATED extreme" (``REQUIRES_VWAP``
      docstring); the replay never produces it (0 bars in the window above),
      but a future loader could.
    * ``close <= 0`` — ``check`` rejects ``no_price``.

    Publishing a sentinel instead would be worse than publishing nothing: the
    exact revert condition a LONG deployment compares is ``z_x1000 >= 0``, and
    a fabricated ``z_x1000 == 0`` satisfies it. A bar with no publishable ATR
    is therefore OMITTED (and counted in the lineage), not filled in.
    """
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


def produce_bars(
    df: Any,
    *,
    symbol: str,
    strategy: StrategyInputs,
    contract_spec: ContractSpec,
    market_open_hour: int,
    market_open_minute: int,
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
    """
    setup = SetupDVWAPReversion(config=strategy.entry_config)
    replay = MarketContextReplay(
        df=df,
        symbol=symbol,
        macro_snapshot=None,
        scheduled_events=[],
        contract_spec=contract_spec,
        market_open_hour=market_open_hour,
        market_open_minute=market_open_minute,
        min_volume=0,
    )
    revert_band = float(strategy.entry_config.reversal_confirm_atr_mult)
    eod_enabled = strategy.eod_enabled
    eod_cutoff = strategy.eod_time

    records: list[FieldRecord] = []
    omitted: list[tuple[str, str]] = []
    bars_replayed = 0
    for ctx in replay.iter_contexts():
        setup.check(ctx)
        ev = setup.last_eval
        bars_replayed += 1

        now: datetime = ctx.now
        as_of_ms = int(now.timestamp() * 1000)
        raw_event_id = f"{symbol}:1m:{now.strftime('%Y%m%dT%H%M%S%z')}"

        close = float(ctx.current_price)
        vwap = float(ctx.vwap)
        atr = float(ctx.atr_14)
        unusable = _inputs_unusable(close, vwap, atr)
        if unusable is not None:
            omitted.append((raw_event_id, unusable))
            continue

        # ONE definition of z, shared with check() (see the accessor's
        # docstring). Published on every bar because the session-exit fields
        # outlive the entry window, where check() returns early.
        z = SetupDVWAPReversion.vwap_extension_z(close, vwap, atr)
        z_x1000 = scaled_int(z, Z_SCALE)
        vwap_reverted = abs(z) <= revert_band
        fields: dict[str, int | bool] = {
            "close": scaled_int(close, PRICE_SCALE),
            "vwap_x100": scaled_int(vwap, PRICE_SCALE),
            "atr14_x100": scaled_int(atr, PRICE_SCALE),
            "z_x1000": z_x1000,
            "hi_vol": ev.get("hi_vol") is True,
            "stall_ok": ev.get("stall_ok") is True,
            "reversal_ok": ev.get("reversal_ok") is True,
            "entry_window": ev.get("entry_window") is True,
            "vwap_reverted": vwap_reverted,
            "eod": eod_enabled and now.time() >= eod_cutoff,
        }
        ordered = {key: fields[key] for key in FIELD_ORDER}
        _assert_no_floats(ordered, raw_event_id)
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
            f"no prior-session close, or {len(omitted)} unusable-input bars"
        )
    return ProducedBars(records=records, bars_replayed=bars_replayed, omitted=omitted)


def produce_records(
    df: Any,
    *,
    symbol: str,
    strategy: StrategyInputs,
    contract_spec: ContractSpec,
    market_open_hour: int,
    market_open_minute: int,
) -> list[FieldRecord]:
    """:func:`produce_bars` when only the emitted records are wanted."""
    return produce_bars(
        df,
        symbol=symbol,
        strategy=strategy,
        contract_spec=contract_spec,
        market_open_hour=market_open_hour,
        market_open_minute=market_open_minute,
    ).records


def render_jsonl(records: list[FieldRecord]) -> bytes:
    """Serialize *records* to the exact bytes written to disk."""
    return "".join(f"{record.to_json_line()}\n" for record in records).encode("utf-8")


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------


def _field_lineage(strategy: StrategyInputs) -> dict[str, dict[str, Any]]:
    """Per-field ``{unit, scale, formula_id, window_bars}`` plus its source.

    ``window_bars`` is the causal history each field reads, taken from the
    strategy YAML where the setup takes it. ``null`` means "not a fixed-length
    window" (session-anchored or single-bar).
    """
    cfg = strategy.entry_config
    yaml_ref = str(strategy.path)
    return {
        "close": {
            "unit": "index_point",
            "scale": PRICE_SCALE,
            "formula_id": "bar_close",
            "window_bars": 1,
            "source": "MarketContext.current_price (replayed bar close)",
        },
        "vwap_x100": {
            "unit": "index_point",
            "scale": PRICE_SCALE,
            "formula_id": "session_anchored_vwap_typical_price_volume_weighted",
            "window_bars": None,
            "source": (
                "shared/backtest/market_context_replay.py::iter_contexts "
                "(sum((h+l+c)/3 * v) / sum(v) from the session's first bar "
                "through this bar)"
            ),
        },
        "atr14_x100": {
            "unit": "index_point",
            "scale": PRICE_SCALE,
            "formula_id": "atr_partial_p14_backtest_indicator_engine",
            "window_bars": 14,
            "source": (
                "shared/indicators/engine.py::backtest_indicator_engine "
                "IndicatorSpec('atr_partial', period=14), trailing only"
            ),
        },
        "z_x1000": {
            "unit": "atr",
            "scale": Z_SCALE,
            "formula_id": "vwap_extension_z",
            "window_bars": None,
            "source": ("SetupDVWAPReversion.vwap_extension_z — (close - vwap) / atr14"),
        },
        "hi_vol": {
            "unit": "bool",
            "scale": 1,
            "formula_id": "causal_atr_percentile_regime_gate_pass",
            "window_bars": cfg.vol_window_bars,
            "source": (
                "SetupDVWAPReversion._vol_reference + check() step 3: "
                f"atr14 >= min_atr_ratio({cfg.min_atr_ratio}) * "
                f"percentile(trailing {cfg.vol_window_bars} past ATRs, "
                f"{cfg.vol_percentile}); PERMISSIVE (true) below "
                f"vol_warmup_bars({cfg.vol_warmup_bars}); false when the gate "
                f"was never evaluated on this bar. YAML: {yaml_ref}"
            ),
        },
        "stall_ok": {
            "unit": "bool",
            "scale": 1,
            "formula_id": "causal_recent_range_stall_guard_pass",
            "window_bars": cfg.range_window_bars,
            "source": (
                "SetupDVWAPReversion._self_range + check() step 5: spike "
                f"within stall_buffer_atr_mult({cfg.stall_buffer_atr_mult}) "
                f"* atr14 of the max/min of the prior "
                f"{cfg.range_window_bars} closes; PERMISSIVE (true) below "
                f"range_warmup_bars({cfg.range_warmup_bars}); false when the "
                "guard was never evaluated on this bar"
            ),
        },
        "reversal_ok": {
            "unit": "bool",
            "scale": 1,
            "formula_id": "reversal_confirmation_pass",
            "window_bars": 1,
            "source": (
                "check() step 6: price turned back toward VWAP versus the "
                "prior close and abs(prev_z) - abs(z) >= "
                f"reversal_confirm_atr_mult({cfg.reversal_confirm_atr_mult}); "
                f"enabled={cfg.reversal_confirm_enabled}, "
                f"requires_price_turn={cfg.reversal_confirm_requires_price_turn}"
                "; false when confirmation was never evaluated on this bar"
            ),
        },
        "entry_window": {
            "unit": "bool",
            "scale": 1,
            "formula_id": "minutes_since_open_within_entry_window",
            "window_bars": None,
            "source": (
                "check() step 1: "
                f"valid_minutes_min({cfg.valid_minutes_min}) <= "
                "minutes_since_open <= no_entry_after_minutes_since_open("
                f"{cfg.no_entry_after_minutes_since_open}), anchored on the "
                "configured futures open"
            ),
        },
        "vwap_reverted": {
            "unit": "bool",
            "scale": 1,
            "formula_id": "abs_z_le_reversal_confirm_atr_mult",
            "window_bars": None,
            "source": (
                f"abs(z) <= reversal_confirm_atr_mult"
                f"({cfg.reversal_confirm_atr_mult}). {_VWAP_REVERTED_NOTE}"
            ),
        },
        "eod": {
            "unit": "bool",
            "scale": 1,
            "formula_id": "bar_time_ge_eod_close_time",
            "window_bars": None,
            "source": (
                "bar KST time >= strategy.exit.params.eod_close_hour:minute "
                f"({strategy.eod_time.isoformat()}), the comparison "
                "shared/strategy/exit/setup_target_exit.py::_should_eod_close "
                f"makes; eod_close_enabled={strategy.eod_enabled}"
            ),
        },
    }


def _git_identity(repo_root: Path) -> dict[str, Any]:
    """Record the worktree's commit and whether it is dirty (provenance only)."""

    def run(args: list[str]) -> str | None:
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

    commit = run(["rev-parse", "HEAD"])
    status = run(["status", "--porcelain"])
    return {
        "repo_root": str(repo_root),
        "commit": commit or "unknown",
        "branch": run(["rev-parse", "--abbrev-ref", "HEAD"]) or "unknown",
        "dirty": bool(status) if status is not None else None,
    }


def build_lineage(
    *,
    produced: ProducedBars,
    jsonl_bytes: bytes,
    symbol: str,
    strategy: StrategyInputs,
    contract_spec: ContractSpec,
    data_root: Path,
    requested_start: date,
    requested_end: date,
    min_bars_per_day: int,
    bars_loaded: int,
    input_files: list[InputFile],
    market_open_hour: int,
    market_open_minute: int,
) -> dict[str, Any]:
    """Assemble the lineage sidecar.

    Deliberately carries **no run timestamp and no duration**: two runs over
    the same inputs must produce identical bytes, so that a changed lineage
    means changed inputs, parameters or code — never merely a re-run.
    """
    records = produced.records
    as_of_values = [record.as_of_ms for record in records]
    session_dates = sorted({record.bar_kst.date() for record in records})
    first_id = records[0].raw_event_id
    last_id = records[-1].raw_event_id
    return {
        "lineage_schema_version": LINEAGE_SCHEMA_VERSION,
        "tool": {
            "name": "tools/tos_cp3/produce_fields.py",
            "version": f"tos_cp3/{TOS_CP3_VERSION}",
            "git": _git_identity(REPO_ROOT),
        },
        "dataset": {
            "symbol": symbol,
            "instrument": symbol,
            "asset_class": strategy.asset_class,
            "timeframe": "minute",
            "data_root": str(data_root),
            "requested_start": requested_start.isoformat(),
            "requested_end": requested_end.isoformat(),
            "min_bars_per_day": min_bars_per_day,
            "bars_loaded": bars_loaded,
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
            "replay_warmup_bars_skipped": DEFAULT_WARMUP_BARS,
            "first_raw_event_id": first_id,
            "last_raw_event_id": last_id,
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
        },
        "strategy": {
            "path": str(strategy.path),
            "sha256": strategy.sha256,
            "entry_type": SetupDVWAPReversion.REGISTRY_NAME,
            "entry_params_yaml": strategy.entry_params,
            "exit_params_yaml": strategy.exit_params,
            "entry_params_used": strategy.entry_config.model_dump(mode="json"),
            "market_open_kst": f"{market_open_hour:02d}:{market_open_minute:02d}",
            "market_open_source": "config/market_schedule.yaml"
            "::market_schedule.futures.regular.open",
            "contract_spec": {
                "name": contract_spec.name,
                "multiplier_krw_per_point": contract_spec.multiplier_krw_per_point,
                "tick_size_points": contract_spec.tick_size_points,
                "tick_value_krw": contract_spec.tick_value_krw,
                "source": "config/execution.yaml::futures_contract_spec",
            },
        },
        "encoding": {
            "rounding": "half_up_toward_positive_infinity",
            "no_floats_in_fields": True,
            "field_order": list(FIELD_ORDER),
            "as_of_ms_semantics": (
                "epoch milliseconds of the bar's labelled KST minute — the "
                "same instant MarketContextReplay stamps on MarketContext.now "
                "and therefore the instant entry_window and eod are compared "
                "against. The dataset labels a minute bar with its opening "
                "minute; label+60s would be the wall-clock end of the bar but "
                "would desynchronise as_of_ms from the session fields computed "
                "on the label (a 15:15 bar would carry a 15:16 as_of_ms)."
            ),
        },
        "fields": _field_lineage(strategy),
        "declared_differences": [
            {
                "id": "D1",
                "item": "min_confidence",
                "value": strategy.entry_config.min_confidence,
                "note": (
                    "The legacy confidence gate has no published field: the "
                    "DSL has no arithmetic and the Proposal no numeric slot. "
                    "The AND of these fields is a SUPERSET of 'legacy fired'."
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
                    "Adapter-level gates outside SetupDVWAPReversion.check(); "
                    "out of scope by the kickoff plan 4 decision 5."
                ),
            },
            {
                "id": "D3",
                "item": "vwap_reverted",
                "value": strategy.entry_config.reversal_confirm_atr_mult,
                "note": _VWAP_REVERTED_NOTE,
            },
            {
                "id": "D4",
                "item": "eod",
                "value": strategy.eod_time.isoformat(),
                "note": (
                    "SetupTargetExit._should_eod_close additionally consults "
                    "is_trading_day_kst and effective_close_time (half-day "
                    "clamp); neither can move this cutoff for bars present in "
                    "a futures minute dataset, so they are not reproduced."
                ),
            },
            {
                "id": "D6",
                "item": "omitted bars",
                "value": len(produced.omitted),
                "note": (
                    "A bar whose atr/vwap/close cannot carry their published "
                    "meaning is evaluated (the causal deques advance as in the "
                    "legacy replay) but NOT emitted, because a sentinel "
                    "z_x1000 of 0 would satisfy the exact LONG revert "
                    "comparison z_x1000 >= 0. Ids and reasons are listed under "
                    "dataset.omitted_bars."
                ),
            },
            {
                "id": "D5",
                "item": "unevaluated gate fields",
                "value": ["hi_vol", "stall_ok", "reversal_ok"],
                "note": (
                    "False when check() returned before that gate ran — "
                    "fail-closed. entry_window is False on the same bars, so "
                    "the entry AND is unaffected, and the session-exit fields "
                    "(vwap_reverted, eod, z_x1000) never read these."
                ),
            },
        ],
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


def run(
    *,
    data_root: Path,
    symbol: str,
    start: date,
    end: date,
    strategy_yaml: Path,
    out_dir: Path,
    min_bars_per_day: int = 0,
) -> RunResult:
    """Produce the field JSONL and lineage sidecar for one dataset window."""
    strategy = load_strategy_inputs(strategy_yaml)
    registry = ContractSpecRegistry.from_yaml(str(REPO_ROOT / "config/execution.yaml"))
    contract_spec = resolve_contract_spec(symbol, registry)
    _assert_scale_covers_tick(contract_spec, PRICE_SCALE)
    market_open_hour, market_open_minute = load_futures_open_from_config(
        str(REPO_ROOT / "config/market_schedule.yaml")
    )

    input_files = discover_input_files(
        data_root,
        asset_class=strategy.asset_class,
        symbol=symbol,
        start=start,
        end=end,
    )
    df = load_bars(
        data_root,
        asset_class=strategy.asset_class,
        symbol=symbol,
        start=start,
        end=end,
        min_bars_per_day=min_bars_per_day,
    )
    produced = produce_bars(
        df,
        symbol=symbol,
        strategy=strategy,
        contract_spec=contract_spec,
        market_open_hour=market_open_hour,
        market_open_minute=market_open_minute,
    )
    records = produced.records
    jsonl_bytes = render_jsonl(records)
    lineage = build_lineage(
        produced=produced,
        jsonl_bytes=jsonl_bytes,
        symbol=symbol,
        strategy=strategy,
        contract_spec=contract_spec,
        data_root=data_root,
        requested_start=start,
        requested_end=end,
        min_bars_per_day=min_bars_per_day,
        bars_loaded=int(len(df)),
        input_files=input_files,
        market_open_hour=market_open_hour,
        market_open_minute=market_open_minute,
    )
    lineage_bytes = render_lineage(lineage)

    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / FIELDS_FILENAME
    lineage_path = out_dir / LINEAGE_FILENAME
    jsonl_path.write_bytes(jsonl_bytes)
    lineage_path.write_bytes(lineage_bytes)
    return RunResult(
        records=records,
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
            "CP-3 B1a — turn Parquet minute bars into the per-bar integer/bool "
            "Critical Input field JSONL plus a lineage sidecar, using the "
            "legacy Setup D implementation's own math."
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
        "--out", required=True, type=Path, help="Output directory for the two artifacts"
    )
    parser.add_argument(
        "--min-bars-per-day",
        type=int,
        default=0,
        help=(
            "Drop sessions with fewer bars than this before replay (0 = keep "
            "every session; recorded in the lineage either way)"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run(
            data_root=args.data_root,
            symbol=args.symbol,
            start=args.start,
            end=args.end,
            strategy_yaml=args.strategy_yaml,
            out_dir=args.out,
            min_bars_per_day=args.min_bars_per_day,
        )
    except ProduceFieldsError as exc:
        print(f"produce_fields: {exc}", file=sys.stderr)
        return 2

    lineage = result.lineage
    print(f"wrote {result.jsonl_path} ({lineage['output']['jsonl_lines']} lines)")
    print(f"wrote {result.lineage_path}")
    print(f"jsonl sha256: {lineage['output']['jsonl_sha256']}")
    print(
        "bars loaded/emitted: "
        f"{lineage['dataset']['bars_loaded']}/{lineage['dataset']['bars_emitted']}"
    )
    print(f"input parquet files: {lineage['dataset']['input_file_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
