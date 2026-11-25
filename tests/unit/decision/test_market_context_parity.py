"""P6-d (§8-2): live-producer ↔ backtest-replay MarketContext field parity."""

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
from shared.decision.setups import vwap_reversion
from shared.execution.contract_spec import ContractSpec

KST = ZoneInfo("Asia/Seoul")
SYMBOL = "A05603"

_SETUP_READ_FIELDS: frozenset[str] = frozenset(
    {
        "now",
        "symbol",
        "current_price",
        "atr_14",
        "vwap",
        "market_open_hour",
        "market_open_minute",
    }
)

_METHOD_BACKING_FIELDS: dict[str, set[str]] = {
    "minutes_since_open": {"now", "market_open_hour", "market_open_minute"},
    "market_open_time": {"now", "market_open_hour", "market_open_minute"},
    "find_recent_event": {"scheduled_events", "now"},
}


def _ctx_attrs_read_by_setups() -> set[str]:
    """AST-extract every ``ctx.<attr>`` / ``context.<attr>`` name from Setup D."""
    attrs: set[str] = set()
    for mod in (vwap_reversion,):
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
    """Find every place a setup ALIASES the ``ctx`` param instead of reading it directly."""
    alias_names = {"ctx", "context"}
    bindings: list[str] = []
    for mod in (vwap_reversion,):
        mod_name = mod.__name__.rsplit(".", 1)[-1]
        tree = ast.parse(inspect.getsource(mod))
        for node in ast.walk(tree):
            value = None
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
                value = node.value
            if isinstance(value, ast.Name) and value.id in alias_names:
                bindings.append(
                    f"{mod_name}:{getattr(node, 'lineno', '?')} rebinds "
                    f"'{value.id}' to another binding"
                )
            if isinstance(node, ast.Call):
                for arg in (*node.args, *(kw.value for kw in node.keywords)):
                    if isinstance(arg, ast.Name) and arg.id in alias_names:
                        bindings.append(
                            f"{mod_name}:{getattr(node, 'lineno', '?')} forwards "
                            f"'{arg.id}' as a call argument"
                        )
    return bindings


def _builder_marketcontext_threading() -> dict[str, set[str]]:
    """Map each kwarg of build_market_context's ``MarketContext(...)`` to the"""
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


def _replay_constructor_kwargs() -> set[str]:
    """AST-extract the keyword names of the ``MarketContext(...)`` call in replay."""
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


def test_builder_signature_threads_every_contract_field() -> None:
    """The canonical assembler exposes AND threads every MarketContext field."""
    contract = set(MARKET_CONTEXT_FIELDS)

    params = set(inspect.signature(build_market_context).parameters)
    params.discard("config_path")
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
    """Setup D must read ``ctx.<field>`` directly — never alias/stash/forward ctx (F2)."""
    aliases = _ctx_alias_bindings()
    assert not aliases, (
        "a setup aliases/forwards the MarketContext instead of reading "
        "ctx.<field> directly — the parity field-coverage scan can no longer see "
        "every read. Refactor to read fields directly, or extend the AST scan to "
        f"follow the alias, THEN update this guard: {aliases}"
    )


def test_replay_constructs_every_contract_field_explicitly() -> None:
    """The replay's direct MarketContext(...) names every contract field."""
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
    """AST proof that ``_SETUP_READ_FIELDS`` covers what Setup D consumes."""
    contract = set(MARKET_CONTEXT_FIELDS)
    attrs = _ctx_attrs_read_by_setups()

    consumed: set[str] = {a for a in attrs if a in contract}
    for attr in attrs:
        consumed |= _METHOD_BACKING_FIELDS.get(attr, set())

    assert consumed, "AST scan found no ctx.<field> reads in the setup modules"

    uncovered = consumed - _SETUP_READ_FIELDS
    assert not uncovered, (
        "setups now read MarketContext field(s) missing from the parity set — "
        f"add to _SETUP_READ_FIELDS and extend the value-parity test: {uncovered}"
    )


_DAY1_BARS = 30
_DAY2_BARS = 80
_PICK = 70
_SPIKE_IDX = _PICK


def _two_session_rows() -> list[dict]:
    """Deterministic two-session 1-min OHLCV bars (no RNG — fully reproducible)."""
    rows: list[dict] = []

    def gen(day: int, n: int, start_price: float) -> None:
        price = start_price
        start = datetime(2026, 6, day, 9, 0, tzinfo=KST)
        for i in range(n):
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
                    "volume": 100 + i,
                }
            )
            price = c

    gen(25, _DAY1_BARS, 100.0)
    gen(26, _DAY2_BARS, rows[-1]["close"])

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


def test_replay_derives_its_fields_per_contract() -> None:
    """Replay computes each field exactly as an independent reference."""
    rows = _two_session_rows()
    ctx = _replay_ctx_at(rows, _PICK)

    i = _PICK
    sess_start = _DAY1_BARS

    assert ctx.current_price == pytest.approx(rows[i]["close"])
    assert ctx.today_open == pytest.approx(rows[sess_start]["open"])
    assert ctx.prev_close == pytest.approx(rows[_DAY1_BARS - 1]["close"])

    prior_hi = max(r["high"] for r in rows[i - 15 : i])
    prior_lo = min(r["low"] for r in rows[i - 15 : i])
    assert ctx.last_15min_high == pytest.approx(prior_hi)
    assert ctx.last_15min_low == pytest.approx(prior_lo)

    inclusive_hi = max(r["high"] for r in rows[i - 15 : i + 1])
    assert inclusive_hi > prior_hi, "fixture spike misconfigured"
    assert ctx.last_15min_high != pytest.approx(inclusive_hi), (
        "replay included the current bar in last_15min_high — the #533/#537 "
        "off-by-one regression (breakout condition becomes unreachable)"
    )

    assert ctx.vwap == pytest.approx(_expected_session_vwap(rows, i, sess_start))


def test_builder_reproduces_replay_context_from_same_inputs() -> None:
    """Feeding the replay-computed field values through the canonical assembler"""
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
        atr_14=ctx.atr_14,
        last_15min_high=max(r["high"] for r in rows[i - 15 : i]),
        last_15min_low=min(r["low"] for r in rows[i - 15 : i]),
        vwap=_expected_session_vwap(rows, i, sess_start),
        atr_90th_percentile=ctx.atr_90th_percentile,
        current_spread_ticks=_STUB_SPREAD_TICKS,
        macro_overnight=None,
        scheduled_events=[],
        market_open_hour=8,
        market_open_minute=45,
    )

    for field_name in _SETUP_READ_FIELDS:
        built_val = getattr(built, field_name)
        replay_val = getattr(ctx, field_name)
        expected = (
            pytest.approx(replay_val) if isinstance(built_val, float) else replay_val
        )
        assert built_val == expected, (
            f"live↔replay divergence on setup-read field {field_name!r}: "
            f"builder={built_val!r} replay={replay_val!r}"
        )


_MINIMAL_VWAP = 330.40


def _builder_minimal_kwargs() -> dict:
    """Minimal builder inputs (the two remaining F-4 default fields omitted)."""
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
        "market_open_hour": 8,
        "market_open_minute": 45,
    }


def test_spread_default_policy_is_shared_constant() -> None:
    """current_spread_ticks: replay stub == builder default (both 1.0)."""
    built_default = build_market_context(**_builder_minimal_kwargs())
    assert built_default.current_spread_ticks == 1.0
    assert built_default.current_spread_ticks == _STUB_SPREAD_TICKS


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


def test_replay_vwap_is_data_driven_not_the_current_price() -> None:
    """The replay computes a real volume-weighted average, not a price echo."""
    rows = _two_session_rows()
    ctx = _replay_ctx_at(rows, _PICK)
    assert ctx.vwap != pytest.approx(ctx.current_price)


def test_atr_90th_default_is_scaled_but_replay_computes_percentile() -> None:
    """DOCUMENTED divergence: builder defaults atr_90th→atr_14*1.5; replay computes."""
    built_default = build_market_context(**_builder_minimal_kwargs())
    assert built_default.atr_90th_percentile == pytest.approx(2.0 * 1.5)
