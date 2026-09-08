"""P6-d (§8-2): live-producer ↔ backtest-replay MarketContext field parity.

Why this file exists
--------------------
Every live ``MarketContext`` flows through the *canonical assembler*
:func:`shared.decision.context.build_market_context` (both the decoupled
``services/decision_engine/context_provider.py`` and the orchestrator
``shared/strategy/entry/setup_context_builder.py`` call it). The **backtest
replay** :class:`shared.backtest.market_context_replay.MarketContextReplay`
does NOT — it constructs ``MarketContext(...)`` directly, computing each field
from bar data.

That bypass is the parity hazard behind #533/#537: a field the replay computes
(``last_15min_high``/``last_15min_low``) was silently defaulted on the live side
to ``current_price``, collapsing Setup C's breakout range so it could NEVER
fire live while the replay happily produced breakouts (Setup D also fades a
15-min range, but self-computes it from closes and does NOT read
``ctx.last_15min_*`` — see ``_SETUP_READ_FIELDS`` below). The pre-existing
``tests/unit/strategy/test_setup_c_15min_range_wiring.py`` locks that ONE field
pair through the live engine; this file adds the *structural* contract so the
NEXT field added to one producer but not the other fails loudly, not silently.

The contract, in three layers:
  (a) FIELD-SET completeness — both producers must name every
      :data:`MARKET_CONTEXT_FIELDS` field explicitly (builder via its signature,
      replay via its constructor keywords). A new dataclass field breaks this
      until both sides are updated.
  (b) SETUP-READ value parity — for one synthetic bar, the fields Setup A/C/D
      actually consume are computed by the replay and, independently, by this
      test; feeding the test's values through the canonical builder must yield an
      identical MarketContext. Locks the ``last_15min`` PRIOR-15 off-by-one, the
      session-VWAP formula, ``today_open``/``prev_close`` session boundaries.
  (c) DEFAULT-POLICY contract — the remaining F-4 builder defaults (spread→1.0,
      atr_90th→atr_14*1.5) are pinned against the replay's behaviour:
      ``current_spread_ticks`` is a SHARED constant (1.0) on both sides;
      ``atr_90th_percentile`` is a DOCUMENTED divergence (the replay computes a
      data-driven value, the builder falls back to a default). ``vwap`` left
      that set at the F-9 cutover — it is REQUIRED of the builder and supplied
      by the live producers rather than defaulted — but live and replay still
      compute it DIFFERENTLY (typical-price/KST-session vs close/UTC-date); see
      the vwap section below for what is and is not asserted.

This test is NOT tautological: it never feeds one producer's output into the
other. The two code paths run independently on the same synthetic bars and are
compared against a hand-computed reference derived from those bars.
"""

from __future__ import annotations

import ast
import inspect
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from shared.backtest import market_context_replay as replay_mod
from shared.backtest.market_context_replay import (
    _STUB_SPREAD_TICKS,
    MarketContextReplay,
)
from shared.decision.context import (
    MARKET_CONTEXT_FIELDS,
    build_market_context,
)
from shared.decision.setups import event_reaction, gap_reversion, vwap_reversion
from shared.execution.contract_spec import ContractSpec

KST = ZoneInfo("Asia/Seoul")
SYMBOL = "A05603"

# ---------------------------------------------------------------------------
# Setup-read field contract
# ---------------------------------------------------------------------------
# The MarketContext fields Setup A / C / D actually consume (verified below by
# AST-extracting every ``ctx.<attr>`` access from the three setup modules).
# Method accesses expand to their backing fields:
#   minutes_since_open() / market_open_time() -> now, market_open_hour/minute
#   find_recent_event()                       -> scheduled_events, now
#
# Fields absent here are the F-4 "unused" trio that no setup reads
# (atr_90th_percentile, current_spread_ticks) plus vwap for A/C — locked
# independently by tests/unit/strategy/test_setup_ac_field_invariance.py. vwap
# IS read by Setup D, so it is in the parity set.
_SETUP_READ_FIELDS: frozenset[str] = frozenset(
    {
        "now",
        "symbol",
        "current_price",
        "atr_14",
        "prev_close",  # Setup A gap
        "today_open",  # Setup A gap
        "last_15min_high",  # Setup C breakout range (Setup D self-computes its own)
        "last_15min_low",  # Setup C breakout range (Setup D self-computes its own)
        "vwap",  # Setup D VWAP-stretch (z = (price - vwap) / atr)
        "macro_overnight",  # Setup A overnight bias
        "scheduled_events",  # Setup C event window
        "market_open_hour",  # all: minutes_since_open()
        "market_open_minute",  # all: minutes_since_open()
    }
)

# Setup ``ctx`` method accesses → the backing MarketContext fields they read.
_METHOD_BACKING_FIELDS: dict[str, set[str]] = {
    "minutes_since_open": {"now", "market_open_hour", "market_open_minute"},
    "market_open_time": {"now", "market_open_hour", "market_open_minute"},
    "find_recent_event": {"scheduled_events", "now"},
}


def _ctx_attrs_read_by_setups() -> set[str]:
    """AST-extract every ``ctx.<attr>`` / ``context.<attr>`` name from the setups.

    This makes ``_SETUP_READ_FIELDS`` self-validating: if a setup starts reading a
    new MarketContext field, the guard test below fails until that field is added
    to the parity set (forcing an explicit decision, not a silent gap).
    """
    attrs: set[str] = set()
    for mod in (gap_reversion, event_reaction, vwap_reversion):
        tree = ast.parse(inspect.getsource(mod))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id in {"ctx", "context"}
            ):
                attrs.add(node.attr)
    return attrs


def _ctx_alias_bindings() -> list[str]:
    """Find every place a setup ALIASES the ``ctx`` param instead of reading it directly.

    ``_ctx_attrs_read_by_setups`` only sees ``ctx.<attr>`` / ``context.<attr>``
    where the receiver is the *bare* ``ctx``/``context`` Name. A setup that
    rebinds the context to another name (``mv = ctx; mv.vwap``), stashes it on
    ``self`` (``self._ctx = ctx``), or forwards it to a helper (``_read(ctx)``)
    would read fields through a binding the AST scan cannot see — making the
    coverage guard below pass *vacuously* (false green: a newly-read field would
    be invisible). This locks the current "read ``ctx.<field>`` directly only"
    pattern; any future aliasing trips the guard loudly. A full data-flow
    analysis is intentionally out of scope — we lock today's pattern and force a
    conscious decision (extend the scan, or refactor) when it changes.

    Note: aliasing via the *parameter name* itself (``def check(self, mv):``) is
    already caught by the existing ``assert consumed`` guard — that scan would
    then find zero ``ctx.<field>`` reads. This covers the remaining vectors where
    the param stays ``ctx`` but is re-bound / forwarded mid-body.
    """
    alias_names = {"ctx", "context"}
    bindings: list[str] = []
    for mod in (gap_reversion, event_reaction, vwap_reversion):
        mod_name = mod.__name__.rsplit(".", 1)[-1]
        tree = ast.parse(inspect.getsource(mod))
        for node in ast.walk(tree):
            # (1) Rebinding the whole context: ``mv = ctx``, ``self._ctx = ctx``,
            #     ``mv: X = ctx``, or the walrus ``(mv := ctx)``. Keyed on the RHS
            #     being a bare ctx/context Name (``x = ctx.attr`` is a field read,
            #     NOT an alias — its RHS is an Attribute, so it is ignored).
            value = None
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
                value = node.value
            if isinstance(value, ast.Name) and value.id in alias_names:
                bindings.append(
                    f"{mod_name}:{getattr(node, 'lineno', '?')} rebinds "
                    f"'{value.id}' to another binding"
                )
            # (2) Forwarding the bare context into a call: ``_read(ctx)``. Method
            #     calls ON ctx (``ctx.find_recent_event(...)``) are fine — there
            #     ctx is the receiver (Call.func is an Attribute), not an argument.
            if isinstance(node, ast.Call):
                for arg in (*node.args, *(kw.value for kw in node.keywords)):
                    if isinstance(arg, ast.Name) and arg.id in alias_names:
                        bindings.append(
                            f"{mod_name}:{getattr(node, 'lineno', '?')} forwards "
                            f"'{arg.id}' as a call argument"
                        )
    return bindings


def _builder_marketcontext_threading() -> dict[str, set[str]]:
    """Map each kwarg of build_market_context's ``MarketContext(...)`` to the
    parameter Names threaded into that kwarg's value expression.

    Lets the field-threading test (F3) assert not merely that a parameter EXISTS
    on the signature, but that the builder actually PASSES it into the constructed
    dataclass and derives the field's value from the same-named parameter. The
    failure a name-only check misses: a new field given a dataclass default plus a
    no-op builder parameter that is never forwarded into ``MarketContext(...)``.
    """
    tree = ast.parse(inspect.getsource(build_market_context))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "MarketContext"
        ):
            return {
                kw.arg: {n.id for n in ast.walk(kw.value) if isinstance(n, ast.Name)}
                for kw in node.keywords
                if kw.arg is not None
            }
    raise AssertionError(
        "no MarketContext(...) construction found in build_market_context — "
        "the threading guard cannot introspect the builder's field fill"
    )


def _fcp_builder_call_kwargs() -> set[str]:
    """Keyword names the decoupled FuturesContextProvider passes to build_market_context.

    Post-F-9 the decoupled live producer threads a real session ``vwap`` and
    still omits atr_90th / spread (the F-4 builder defaults). This AST-pins that
    vwap IS passed, so removing it again — which would reopen the #533/#537-class
    Setup-D-inert gap — fails the contract test below.
    """
    from services.decision_engine import context_provider as fcp_mod

    tree = ast.parse(inspect.getsource(fcp_mod))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "build_market_context"
        ):
            return {kw.arg for kw in node.keywords if kw.arg is not None}
    raise AssertionError(
        "no build_market_context(...) call found in FuturesContextProvider — "
        "the decoupled-vwap-gap pin cannot introspect the provider"
    )


def _replay_constructor_kwargs() -> set[str]:
    """AST-extract the keyword names of the ``MarketContext(...)`` call in replay.

    The replay bypasses ``build_market_context`` and constructs the dataclass
    directly; this pins that construction to name every contract field.
    """
    tree = ast.parse(inspect.getsource(replay_mod))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "MarketContext"
        ):
            return {kw.arg for kw in node.keywords if kw.arg is not None}
    raise AssertionError(
        "no MarketContext(...) construction found in market_context_replay — "
        "the parity guard cannot introspect the replay's field fill"
    )


# ---------------------------------------------------------------------------
# (a) FIELD-SET completeness — structural guards
# ---------------------------------------------------------------------------


def test_builder_signature_threads_every_contract_field() -> None:
    """The canonical assembler exposes AND threads every MarketContext field.

    Two layers, because "the parameter exists" is not "the parameter is used":
      * signature — every field is a named parameter (a new field with no
        parameter would be silently defaulted for BOTH live producers); and
      * threading (F3) — the builder's ``return MarketContext(...)`` actually
        passes every contract field as a keyword, and each field's value
        references the same-named parameter. Guards the failure a name-only check
        misses: a new field added with a dataclass default plus a no-op parameter
        that is never forwarded into the constructed context (so the builder
        compiles, the signature check passes, yet the field is silently defaulted).
    """
    contract = set(MARKET_CONTEXT_FIELDS)

    params = set(inspect.signature(build_market_context).parameters)
    params.discard("config_path")  # builder-internal I/O knob, not a MC field
    assert params == contract, (
        "build_market_context parameters drifted from MarketContext fields: "
        f"missing={contract - params}, extra={params - contract}"
    )

    threading = _builder_marketcontext_threading()
    passed = set(threading)
    assert passed == contract, (
        "build_market_context's MarketContext(...) construction does not pass "
        "every contract field as a keyword: "
        f"missing={contract - passed}, extra={passed - contract}"
    )
    not_threaded = {
        field for field in contract if field not in threading.get(field, set())
    }
    assert not not_threaded, (
        "build_market_context names these fields in MarketContext(...) but never "
        "threads the same-named parameter into their value — a no-op parameter / "
        f"constant fill that would silently default the field: {not_threaded}"
    )


def test_setups_do_not_alias_the_context() -> None:
    """Setups must read ``ctx.<field>`` directly — never alias/stash/forward ctx (F2).

    The field-coverage guard (``test_setup_read_field_list_covers_all_setup_consumption``)
    AST-scans for bare ``ctx.<attr>`` reads. If a setup aliased the context
    (``mv = ctx``), stashed it (``self._ctx = ctx``), or forwarded it into a
    helper, a newly-read field would be invisible to that scan and the coverage
    guard would pass vacuously. Locking the no-alias pattern keeps the parity
    contract from silently going blind.
    """
    aliases = _ctx_alias_bindings()
    assert not aliases, (
        "a setup aliases/forwards the MarketContext instead of reading "
        "ctx.<field> directly — the parity field-coverage scan can no longer see "
        "every read. Refactor to read fields directly, or extend the AST scan to "
        f"follow the alias, THEN update this guard: {aliases}"
    )


def test_replay_constructs_every_contract_field_explicitly() -> None:
    """The replay's direct MarketContext(...) names every contract field.

    This is the #533/#537 structural firewall: the replay computes fields from
    bars and constructs the dataclass directly, so a field it forgets would fall
    back to the dataclass default — exactly how last_15min collapsed live before.
    """
    kwargs = _replay_constructor_kwargs()
    assert kwargs == set(MARKET_CONTEXT_FIELDS), (
        "MarketContextReplay stopped populating a field the contract requires: "
        f"missing={set(MARKET_CONTEXT_FIELDS) - kwargs}, "
        f"extra={kwargs - set(MARKET_CONTEXT_FIELDS)}"
    )


def test_setup_read_fields_are_a_subset_of_the_contract() -> None:
    """Every field the setups actually read is inside the parity contract set."""
    assert set(MARKET_CONTEXT_FIELDS) >= _SETUP_READ_FIELDS


def test_setup_read_field_list_covers_all_setup_consumption() -> None:
    """AST proof that ``_SETUP_READ_FIELDS`` covers what A/C/D consume.

    Guards against a setup silently starting to read a MarketContext field that
    the parity value-check (below) does not yet cover.
    """
    contract = set(MARKET_CONTEXT_FIELDS)
    attrs = _ctx_attrs_read_by_setups()

    consumed: set[str] = {a for a in attrs if a in contract}
    for attr in attrs:
        consumed |= _METHOD_BACKING_FIELDS.get(attr, set())

    # Guard the fixture itself: the AST scan must find real consumption, else a
    # silent import/scan failure would make the subset check vacuously pass.
    assert consumed, "AST scan found no ctx.<field> reads in the setup modules"

    uncovered = consumed - _SETUP_READ_FIELDS
    assert not uncovered, (
        "setups now read MarketContext field(s) missing from the parity set — "
        f"add to _SETUP_READ_FIELDS and extend the value-parity test: {uncovered}"
    )


# ---------------------------------------------------------------------------
# Synthetic two-session bar fixture (independent reference for value parity)
# ---------------------------------------------------------------------------

_DAY1_BARS = 30  # session 1 (indices 0..29) — supplies prev_close only
_DAY2_BARS = 80  # session 2 (indices 30..109) — the bars replay yields
_PICK = 70  # bar index to assert on: in day2, past warmup(60), >=15 prior bars
_SPIKE_IDX = _PICK  # spike bar's high to make the off-by-one observable


def _two_session_rows() -> list[dict]:
    """Deterministic two-session 1-min OHLCV bars (no RNG — fully reproducible).

    A gentle zig-zag drift gives a non-flat session so VWAP != current_price.
    Bar ``_PICK`` gets an outsized ``high`` so the PRIOR-15 (exclusive) window
    provably differs from an inclusive window — that is the off-by-one lock.
    """
    rows: list[dict] = []

    def gen(day: int, n: int, start_price: float) -> None:
        price = start_price
        start = datetime(2026, 6, day, 9, 0, tzinfo=KST)
        for i in range(n):
            # Deterministic zig-zag: ±0.3 alternating, +0.1 net drift per bar.
            step = 0.3 if i % 2 == 0 else -0.2
            o = price
            c = round(o + step, 4)
            hi = round(max(o, c) + 0.25, 4)
            lo = round(min(o, c) - 0.25, 4)
            rows.append(
                {
                    "timestamp": start + timedelta(minutes=i),
                    "open": o,
                    "high": hi,
                    "low": lo,
                    "close": c,
                    "volume": 100 + i,  # strictly positive, varied → real VWAP
                }
            )
            price = c

    gen(25, _DAY1_BARS, 100.0)
    gen(26, _DAY2_BARS, rows[-1]["close"])

    # Make bar _PICK a clean upside spike so PRIOR-15 high (excl. current) is
    # strictly below the inclusive high — proves the exclusion is load-bearing.
    prior_high = max(r["high"] for r in rows[_SPIKE_IDX - 15 : _SPIKE_IDX])
    rows[_SPIKE_IDX]["high"] = round(prior_high + 5.0, 4)
    return rows


def _contract_spec() -> ContractSpec:
    return ContractSpec(
        name=SYMBOL,
        multiplier_krw_per_point=250000,
        tick_size_points=0.05,
        tick_value_krw=12500,
        commission_rate=0.0,
        symbol_prefix="A05",
    )


def _replay_ctx_at(rows: list[dict], idx: int):
    """Run the replay over ``rows`` and return the MarketContext for bar ``idx``."""
    df = pd.DataFrame(rows)
    replay = MarketContextReplay(
        df=df,
        symbol=SYMBOL,
        macro_snapshot=None,
        scheduled_events=[],
        contract_spec=_contract_spec(),
        # Pin the open anchor so the test is independent of config/market_schedule.yaml.
        market_open_hour=8,
        market_open_minute=45,
    )
    want_ts = int(rows[idx]["timestamp"].timestamp())
    for ctx in replay.iter_contexts():
        if int(ctx.now.timestamp()) == want_ts:
            return ctx
    raise AssertionError(f"replay did not yield a context for bar {idx}")


def _expected_session_vwap(rows: list[dict], idx: int, sess_start: int) -> float:
    """Independent session VWAP over bars [sess_start .. idx] (replay's formula)."""
    num = 0.0
    den = 0.0
    for r in rows[sess_start : idx + 1]:
        typical = (r["high"] + r["low"] + r["close"]) / 3.0
        num += typical * r["volume"]
        den += r["volume"]
    return num / den


# ---------------------------------------------------------------------------
# (b) SETUP-READ value parity — replay vs independent reference vs builder
# ---------------------------------------------------------------------------


def test_replay_derives_setup_read_fields_per_contract() -> None:
    """Replay computes each setup-read field exactly as an independent reference.

    Locks the field-derivation RULES that the live path must match: the
    ``last_15min`` PRIOR-15 (current-bar-excluded) window, the session-VWAP
    formula, and the ``today_open`` / ``prev_close`` session boundaries.
    """
    rows = _two_session_rows()
    ctx = _replay_ctx_at(rows, _PICK)

    i = _PICK
    sess_start = _DAY1_BARS  # day2 opens at index 30

    # current_price / today_open / prev_close — session boundaries.
    assert ctx.current_price == pytest.approx(rows[i]["close"])
    assert ctx.today_open == pytest.approx(rows[sess_start]["open"])
    assert ctx.prev_close == pytest.approx(rows[_DAY1_BARS - 1]["close"])

    # last_15min — PRIOR 15 bars [i-15, i-1], current bar EXCLUDED (#533/#537).
    prior_hi = max(r["high"] for r in rows[i - 15 : i])
    prior_lo = min(r["low"] for r in rows[i - 15 : i])
    assert ctx.last_15min_high == pytest.approx(prior_hi)
    assert ctx.last_15min_low == pytest.approx(prior_lo)

    # Off-by-one lock: an INCLUSIVE window would pick up the spike at bar i and
    # yield a strictly larger high — so the two are provably different here.
    inclusive_hi = max(r["high"] for r in rows[i - 15 : i + 1])
    assert inclusive_hi > prior_hi, "fixture spike misconfigured"
    assert ctx.last_15min_high != pytest.approx(inclusive_hi), (
        "replay included the current bar in last_15min_high — the #533/#537 "
        "off-by-one regression (breakout condition becomes unreachable)"
    )

    # vwap — data-driven session VWAP.
    assert ctx.vwap == pytest.approx(_expected_session_vwap(rows, i, sess_start))


def test_builder_reproduces_replay_context_from_same_inputs() -> None:
    """Feeding the replay-computed field values through the canonical assembler
    yields a MarketContext identical on every setup-read field.

    Non-tautological: the inputs handed to ``build_market_context`` are computed
    from the raw bars by this test (not lifted from the replay object), except
    ``atr_14`` / ``atr_90th_percentile`` which come from the shared indicator
    engine and are neutral to the field-fill contract (they are passed through
    both producers identically). The point is that the two INDEPENDENT code
    paths agree field-for-field on the setups' consumed inputs.
    """
    rows = _two_session_rows()
    ctx = _replay_ctx_at(rows, _PICK)

    i = _PICK
    sess_start = _DAY1_BARS

    built = build_market_context(
        now=ctx.now,
        symbol=SYMBOL,
        current_price=rows[i]["close"],
        prev_close=rows[_DAY1_BARS - 1]["close"],
        today_open=rows[sess_start]["open"],
        atr_14=ctx.atr_14,  # shared engine output — neutral to the field contract
        last_15min_high=max(r["high"] for r in rows[i - 15 : i]),
        last_15min_low=min(r["low"] for r in rows[i - 15 : i]),
        vwap=_expected_session_vwap(rows, i, sess_start),
        atr_90th_percentile=ctx.atr_90th_percentile,  # shared engine output
        current_spread_ticks=_STUB_SPREAD_TICKS,
        macro_overnight=None,
        scheduled_events=[],
        market_open_hour=8,
        market_open_minute=45,
    )

    for field_name in _SETUP_READ_FIELDS:
        built_val = getattr(built, field_name)
        replay_val = getattr(ctx, field_name)
        # Float fields (vwap, prices) may differ by accumulation order between the
        # replay's vectorised numpy sums and this test's scalar reference; the
        # CONTRACT is same-value, not bit-identical, so compare within tolerance.
        expected = (
            pytest.approx(replay_val) if isinstance(built_val, float) else replay_val
        )
        assert built_val == expected, (
            f"live↔replay divergence on setup-read field {field_name!r}: "
            f"builder={built_val!r} replay={replay_val!r}"
        )


# ---------------------------------------------------------------------------
# (c) DEFAULT-POLICY contract — F-4 builder defaults vs replay behaviour
# ---------------------------------------------------------------------------


#: A session VWAP distinct from ``current_price`` below — the builder no longer
#: defaults vwap, and a value equal to current_price would hide a regression
#: that reinstated the old fallback.
_MINIMAL_VWAP = 330.40


def _builder_minimal_kwargs() -> dict:
    """Minimal builder inputs (the two remaining F-4 default fields omitted).

    ``vwap`` is REQUIRED as of the F-9 cutover, so it is supplied here; only
    ``atr_90th_percentile`` and ``current_spread_ticks`` are still omitted to
    exercise the default policy.
    """
    return {
        "now": datetime(2026, 6, 26, 10, 0, tzinfo=KST),
        "symbol": SYMBOL,
        "current_price": 331.20,
        "prev_close": 331.00,
        "today_open": 331.10,
        "atr_14": 2.0,
        "vwap": _MINIMAL_VWAP,
        "last_15min_high": 332.0,
        "last_15min_low": 330.0,
        "market_open_hour": 8,  # pinned → no config/market_schedule.yaml I/O
        "market_open_minute": 45,
    }


def test_spread_default_policy_is_shared_constant() -> None:
    """current_spread_ticks: replay stub == builder default (both 1.0).

    ``current_spread_ticks`` is uncomputable from the OHLCV-only stream, so BOTH
    producers use the same constant. Pins the two so a change to one is caught.
    """
    built_default = build_market_context(**_builder_minimal_kwargs())
    assert built_default.current_spread_ticks == 1.0
    assert built_default.current_spread_ticks == _STUB_SPREAD_TICKS


# ---------------------------------------------------------------------------
# vwap — required of the builder, live-supplied, still NOT replay-identical
# ---------------------------------------------------------------------------
# History: ``build_market_context`` used to fall back ``vwap := current_price``
# while the decoupled live producer ``FuturesContextProvider`` omitted vwap
# entirely, so Setup D's fade trigger ``z = (price - vwap)/atr`` collapsed to 0
# and Setup D could NEVER fire on the decoupled chain (#533/#537 silent inert,
# latent only because futures traded the orchestrator path). The predecessor of
# these tests pinned that gap and named the F-9 cutover as the moment to close
# it; it has been closed (plan 2026-09-08-setup-d-decoupled-port §3-B).
#
# What is NOT claimed here: that live and replay compute the same number. They
# do not, and the difference is structural, not a rounding artefact:
#   * PRICE TERM — the replay weights the TYPICAL price ``(H+L+C)/3``
#     (``market_context_replay`` ~:278), the live streaming engine weights the
#     candle CLOSE (``StreamingIndicatorEngine.on_tick`` feeds
#     ``candle.close`` into ``VWAPCalculator``).
#   * SESSION ANCHOR — the replay resets on the KST session date, the live
#     accumulator is keyed on the UTC calendar date
#     (``ts.strftime("%Y%m%d")``), so it resets at 09:00 KST — mid-session —
#     and is not seeded by parquet warm-up.
# Both are honest session VWAPs of the same tape; neither is derived from the
# other. Closing that gap is an engine change and out of this contract's scope.


def test_builder_honours_a_supplied_vwap() -> None:
    """The builder passes vwap through and never substitutes current_price."""
    built = build_market_context(**_builder_minimal_kwargs())
    assert built.vwap == _MINIMAL_VWAP
    assert built.vwap != built.current_price


def test_builder_has_no_vwap_fallback() -> None:
    """Omitting vwap is a loud TypeError, not a silently-defaulted context."""
    without_vwap = {k: v for k, v in _builder_minimal_kwargs().items() if k != "vwap"}
    with pytest.raises(TypeError):
        build_market_context(**without_vwap)


def test_decoupled_producer_threads_vwap_into_the_builder() -> None:
    """AST pin — the inverse of the pre-cutover assertion.

    Dropping the kwarg again would reopen the Setup-D-inert gap, so it fails
    here rather than going unnoticed until a shadow session produces nothing.
    """
    assert "vwap" in _fcp_builder_call_kwargs(), (
        "FuturesContextProvider no longer passes vwap to build_market_context — "
        "the decoupled Setup-D-inert gap has been reopened. It must source the "
        "engine's session VWAP (get_indicators()['vwap'])."
    )


def test_replay_vwap_is_data_driven_not_the_current_price() -> None:
    """The replay computes a real volume-weighted average, not a price echo."""
    rows = _two_session_rows()
    ctx = _replay_ctx_at(rows, _PICK)
    assert ctx.vwap != pytest.approx(ctx.current_price)


def test_atr_90th_default_is_scaled_but_replay_computes_percentile() -> None:
    """DOCUMENTED divergence: builder defaults atr_90th→atr_14*1.5; replay computes.

    No setup reads ``atr_90th_percentile`` (F-4 invariance), so the divergence is
    behaviourally inert today. Pinned so it stays a *known* difference: the
    builder scales atr_14, the replay takes the full-series 90th percentile.
    """
    built_default = build_market_context(**_builder_minimal_kwargs())
    assert built_default.atr_90th_percentile == pytest.approx(2.0 * 1.5)
