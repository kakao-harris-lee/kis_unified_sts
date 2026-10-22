"""CP-3 ③ live producer on a STOCK symbol (rescope M2, 2026-10-22) — hermetic.

The futures behaviour is pinned by ``test_cp3_live_producer.py``; this file
pins what ``market: stock`` changes and nothing else:

* the stock quotation TR ``FHKST03010230`` is the one requested, GET-only and
  allowlisted, with the stock market division and no futures hour class;
* a recorded-shape ``FHKST03010230`` response parses into the same bar tuples
  the frame freezes;
* the seed never rolls, the Parquet layout says ``stock``, the stock query keys
  (not the futures ones) are read;
* a whole session over a stock calendar publishes lines whose fifteen fields
  equal B1a's ``produce_bars`` over the same frame.

No socket, no credential, no KIS call: the transport is ``httpx.MockTransport``
or an in-process fake, and the clock is fake.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
import yaml

from shared.collector.historical.ohlcv_parser import parse_ohlcv
from tools.broker_probes.common import (
    REAL_BASE_URL,
    SafetyViolation,
    assert_read_only_call,
)
from tools.tos_cp3 import quote_client
from tools.tos_cp3.live_producer import band_line as band_line_mod
from tools.tos_cp3.live_producer import band_probe
from tools.tos_cp3.live_producer import config as config_mod
from tools.tos_cp3.live_producer import frame as frame_mod
from tools.tos_cp3.live_producer import producer as producer_mod
from tools.tos_cp3.live_producer import real_quotes as real_quotes_mod
from tools.tos_cp3.live_producer.config import LiveProducerRefused
from tools.tos_cp3.minute_probe import frame as bars_to_frame
from tools.tos_cp3.produce_fields import (
    ContractSpecRegistry,
    load_strategy_inputs,
    produce_bars,
    resolve_contract_spec,
    resolve_open_anchor,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
STOCK_CONFIG = _REPO_ROOT / "config/tos_probes/cp3-live-producer-stock-005930.yaml"
FUTURES_CONFIG = _REPO_ROOT / "config/tos_probes/cp3-live-producer.yaml"
RECORDED = Path(__file__).parent / "fixtures/cp3_stock_005930_fhkst03010230_page.json"

SYMBOL = "005930"
#: Real 2026 trading days in the tenant calendar (10-09 is a holiday).
SEED_DAYS = [date(2026, 10, d) for d in (6, 7, 8, 12, 13, 14, 15, 16)]
TARGET = date(2026, 10, 19)
STOCK_SESSION_BARS = 380  # 09:00 .. 15:19 (15:20-15:30 is the closing auction)
TARGET_BARS = 40
TARGET_SESSION_END = "09:40"


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------


def _stock_data(**overrides: Any) -> dict:
    data = yaml.safe_load(STOCK_CONFIG.read_text(encoding="utf-8"))
    data.update(overrides)
    return data


def _write(tmp_path: Path, data: dict, name: str = "producer.yaml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def test_the_shipped_stock_config_loads_as_a_stock_market() -> None:
    config = config_mod.load_config(STOCK_CONFIG, repo_root=_REPO_ROOT)
    assert config.market == "stock"
    assert config.asset_class == "stock"
    assert config.front_month_product is None
    assert config.calendar_session_id == "krx-stock"
    assert config.open_anchor == "09:00"
    assert config.profile.credential_keys == (
        "KIS_STOCK_APP_KEY",
        "KIS_STOCK_APP_SECRET",
    )
    transport = config.transport
    assert transport["market"] == "stock"
    assert transport["initial_cursor"] == "153000"
    # The futures hour-class parameter has no meaning for the stock TR.
    assert "hour_cls_code" not in transport


def test_the_shipped_futures_config_keeps_its_futures_meaning() -> None:
    """The generalisation must not move a single futures value."""
    config = config_mod.load_config(FUTURES_CONFIG, repo_root=_REPO_ROOT)
    assert config.market == "futures"
    assert config.asset_class == "futures"
    assert config.front_month_product == "mini"
    assert config.open_anchor == "auto"
    assert config.contract_spec_block == "futures_contract_spec"
    assert config.transport["hour_cls_code"] == "60"
    assert config.transport["initial_cursor"] == ""
    assert config.profile.credential_keys == (
        "KIS_FUTURES_APP_KEY",
        "KIS_FUTURES_APP_SECRET",
    )


@pytest.mark.parametrize(
    ("overrides", "why"),
    [
        # an unknown market: nothing would select its TR
        ({"market": "bond"}, "not one of"),
        # a stock config naming a futures product would request every seed
        # day on a futures month
        ({"front_month_product": "mini"}, "does not roll"),
        # the futures era rule is 08:45 — wrong for a 09:00 stock open
        ({"open_anchor": "auto"}, "FUTURES era rule"),
        ({"open_anchor": "9h"}, "neither 'auto' nor HH:MM"),
        # the volume drop rule must be pinned for stock too
        ({"parser_env": {"KIS_FUTURES_HOUR_CLS_CODE": "60"}}, "must pin"),
    ],
)
def test_each_stock_config_incoherence_is_refused(
    tmp_path: Path, overrides: dict, why: str
) -> None:
    with pytest.raises(LiveProducerRefused, match=why):
        config_mod.load_config(
            _write(tmp_path, _stock_data(**overrides)), repo_root=_REPO_ROOT
        )


def test_a_futures_config_without_a_front_month_is_refused(tmp_path: Path) -> None:
    data = yaml.safe_load(FUTURES_CONFIG.read_text(encoding="utf-8"))
    data["front_month_product"] = None
    with pytest.raises(LiveProducerRefused, match="rolls"):
        config_mod.load_config(_write(tmp_path, data), repo_root=_REPO_ROOT)


def test_front_month_product_must_be_present_even_when_null(tmp_path: Path) -> None:
    data = _stock_data()
    del data["front_month_product"]
    with pytest.raises(LiveProducerRefused, match="missing key"):
        config_mod.load_config(_write(tmp_path, data), repo_root=_REPO_ROOT)


def test_the_stock_market_reads_only_the_stock_query_keys(tmp_path: Path) -> None:
    config = config_mod.load_config(STOCK_CONFIG, repo_root=_REPO_ROOT)
    asked: list[tuple[str, ...]] = []

    def reader(path: Path, *, keys: tuple[str, ...]) -> dict[str, str]:
        asked.append(keys)
        return dict.fromkeys(keys, "fake")

    environ: dict[str, str] = {}
    config_mod.read_query_credentials(config, reader=reader, environ=environ)
    assert asked == [("KIS_STOCK_APP_KEY", "KIS_STOCK_APP_SECRET")]
    assert set(environ) == {"KIS_STOCK_APP_KEY", "KIS_STOCK_APP_SECRET"}


def test_real_quotes_resolves_the_stock_credentials(monkeypatch) -> None:
    config = config_mod.load_config(STOCK_CONFIG, repo_root=_REPO_ROOT)
    seen: list[tuple[str, bool]] = []

    def resolve(asset: str, *, is_real: bool) -> Any:
        seen.append((asset, is_real))
        return SimpleNamespace(app_key="k", app_secret="s")

    monkeypatch.setattr(real_quotes_mod, "resolve_credentials", resolve)
    monkeypatch.setattr(real_quotes_mod, "Quotes", lambda *a, **k: (a, k))
    real_quotes_mod.real_quotes(config, log=None)
    assert seen == [("stock", True)]


RECORDED_BAND = (
    Path(__file__).parent / "fixtures/cp3_stock_005930_fhkst01010100_band.json"
)


def test_the_market_allowlist_keeps_each_market_to_its_own_trs() -> None:
    """PR #922 review LOW-4: a stock process cannot pass the gate with a futures TR."""
    stock = {entry.tr_id for entry in quote_client.market_allowlist("stock")}
    futures = {entry.tr_id for entry in quote_client.market_allowlist("futures")}
    assert stock == {"FHKST03010230", "FHKST01010100"}
    assert futures == {"FHKIF03020200", "FHMIF10000000"}
    with pytest.raises(SafetyViolation):
        assert_read_only_call(
            "GET",
            REAL_BASE_URL + quote_client.BAND_PATH,
            quote_client.BAND_TR,
            quote_client.market_allowlist("stock"),
        )


def test_a_stock_band_read_requests_the_stock_tr_and_yields_the_three_values() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=RECORDED_BAND.read_bytes())

    quotes = _stock_quotes(handler)
    read = quotes.band(SYMBOL)
    (request,) = requests
    assert request.method == "GET"
    assert request.url.path == quote_client.STOCK_BAND_PATH
    assert request.headers["tr_id"] == quote_client.STOCK_BAND_TR == "FHKST01010100"
    assert dict(request.url.params) == {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": SYMBOL,
    }
    assert (
        read.raw_payload_digest
        == hashlib.sha256(RECORDED_BAND.read_bytes()).hexdigest()
    )
    assert band_line_mod.band_values_from_payload(read.payload, "stock") == {
        "upper": "351000",
        "lower": "189000",
        "basis": "270000",
    }
    # The futures shape cannot read it — the member and the field names differ.
    with pytest.raises(band_line_mod.BandLineError):
        band_line_mod.band_values_from_payload(read.payload)


def test_the_band_probe_writes_a_stock_band_line(tmp_path: Path) -> None:
    payload = json.loads(RECORDED_BAND.read_text(encoding="utf-8"))

    class FakeBandQuotes:
        http = None

        def band(self, symbol: str) -> quote_client.BandRead:
            assert symbol == SYMBOL
            return quote_client.BandRead(payload=payload, raw_payload_digest="d" * 64)

    session = tmp_path / "session"
    rc = band_probe.run(
        config_path=STOCK_CONFIG,
        instrument=SYMBOL,
        session_dir=session,
        target=TARGET,
        quotes_factory=lambda *_: FakeBandQuotes(),
        now=lambda: datetime(2026, 10, 19, 9, 1, tzinfo=producer_mod.KST),
    )
    assert rc == band_probe.RC_OK
    (line,) = [
        json.loads(text)
        for text in band_probe.band_journal_path(session)
        .read_text("utf-8")
        .splitlines()
        if text.strip()
    ]
    assert line["tr_id"] == "FHKST01010100"
    assert (line["upper"], line["lower"], line["basis"]) == (
        "351000",
        "189000",
        "270000",
    )
    assert line["instrument"] == SYMBOL
    assert line["trading_date"] == "20261019"


# ---------------------------------------------------------------------------
# the recorded-shape response through the real client
# ---------------------------------------------------------------------------


def _recorded() -> dict:
    return json.loads(RECORDED.read_text(encoding="utf-8"))


def _stock_quotes(handler: Any) -> Any:
    """A real ``Quotes`` over ``httpx.MockTransport`` with a stub auth manager."""
    config = config_mod.load_config(STOCK_CONFIG, repo_root=_REPO_ROOT)
    quotes = object.__new__(quote_client.Quotes)
    quotes.cfg = {**config.transport, "pace_s": 0.0, "retry_pause_s": 0.0}
    quotes.last = 0.0
    quotes.calls = 0
    quotes.recorder = SimpleNamespace(events=[])
    quotes.recorder.event = quotes.recorder.events.append
    quotes.http = httpx.Client(transport=httpx.MockTransport(handler))
    quotes.creds = SimpleNamespace(app_key="key", app_secret="secret")
    quotes.auth = SimpleNamespace(get_token=lambda: "token", invalidate=lambda: None)
    return quotes


def test_a_stock_page_requests_the_stock_tr_and_parses_the_recorded_response() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_recorded())

    quotes = _stock_quotes(handler)
    rows = quotes.page(SYMBOL, date(2026, 10, 21))

    (request,) = requests
    assert request.method == "GET"
    assert request.url.path == quote_client.STOCK_QUOTE_PATH
    assert request.headers["tr_id"] == quote_client.STOCK_TR == "FHKST03010230"
    params = dict(request.url.params)
    assert params["FID_COND_MRKT_DIV_CODE"] == "J"
    assert params["FID_INPUT_ISCD"] == SYMBOL
    assert params["FID_INPUT_DATE_1"] == "20261021"
    assert params["FID_INPUT_HOUR_1"] == "153000"
    assert "FID_HOUR_CLS_CODE" not in params
    # The request log names the TR actually sent, not the futures constant.
    (event,) = quotes.recorder.events
    assert event["tr_id"] == "FHKST03010230"
    assert event["path"] == quote_client.STOCK_QUOTE_PATH

    step = frame_mod.freeze_step(
        rows,
        day=date(2026, 10, 21),
        symbol=SYMBOL,
        last_frozen_minute=None,
        session_ended=False,
    )
    # 09:01-09:04 are complete (a later row exists); 09:05 is still open; the
    # previous day's 15:30 row is not this day's.
    assert [bar[1].strftime("%H:%M") for bar in step.newly_frozen] == [
        "09:01",
        "09:02",
        "09:03",
        "09:04",
    ]
    assert step.deferred == (datetime(2026, 10, 21, 9, 5),)
    first = step.newly_frozen[0]
    assert first[0] == SYMBOL
    assert first[2:] == (61000.0, 61500.0, 61000.0, 61300.0, 597158)


def test_a_futures_page_is_unchanged_by_the_generalisation() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"rt_cd": "0", "output2": []})

    quotes = _stock_quotes(handler)
    quotes.cfg = {
        **config_mod.load_config(FUTURES_CONFIG, repo_root=_REPO_ROOT).transport,
        "pace_s": 0.0,
        "retry_pause_s": 0.0,
    }
    quotes.page("A05611", date(2026, 10, 21))
    (request,) = requests
    assert request.url.path == quote_client.QUOTE_PATH
    assert request.headers["tr_id"] == quote_client.TR
    params = dict(request.url.params)
    assert params["FID_COND_MRKT_DIV_CODE"] == "F"
    assert params["FID_HOUR_CLS_CODE"] == "60"
    assert params["FID_INPUT_HOUR_1"] == ""


def test_stock_history_walks_the_cursor_back_to_the_open() -> None:
    """Pages of the recorded rows, newest first, walked by the oldest stamp."""
    rows = [r for r in _recorded()["output2"] if r["stck_bsop_date"] == "20261021"]
    cursors: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params["FID_INPUT_HOUR_1"]
        cursors.append(cursor)
        page = [r for r in rows if r["stck_cntg_hour"] <= cursor][:3]
        return httpx.Response(200, json={"rt_cd": "0", "output2": page})

    quotes = _stock_quotes(handler)
    got = quote_client.select_day(
        quotes.history(SYMBOL, date(2026, 10, 21)), date(2026, 10, 21)
    )
    assert cursors == ["153000", "090300", "090100"]
    assert {r["stck_cntg_hour"] for r in got} == {
        "090100",
        "090200",
        "090300",
        "090400",
        "090500",
    }


# ---------------------------------------------------------------------------
# a whole stock session through the producer
# ---------------------------------------------------------------------------


def _stock_bars(day: date, *, count: int, base: float, width: float) -> list[tuple]:
    """``parse_ohlcv``-shaped bars at whole-KRW prices, inside the 6 % tolerance."""
    bars: list[tuple] = []
    previous = base
    for index in range(count):
        phase = index % 9
        close = float(round(base + width * (phase - 4)))
        stamp = datetime(day.year, day.month, day.day, 9, 0) + timedelta(minutes=index)
        bars.append(
            (
                SYMBOL,
                stamp,
                previous,
                max(previous, close) + 100.0,
                min(previous, close) - 100.0,
                close,
                1000 + index % 13,
            )
        )
        previous = close
    return bars


def _row(bar: tuple) -> dict:
    """An ``FHKST03010230`` ``output2`` row — the recorded fixture's keys."""
    return {
        "stck_bsop_date": bar[1].strftime("%Y%m%d"),
        "stck_cntg_hour": bar[1].strftime("%H%M%S"),
        "stck_oprc": f"{bar[2]:.0f}",
        "stck_hgpr": f"{bar[3]:.0f}",
        "stck_lwpr": f"{bar[4]:.0f}",
        "stck_prpr": f"{bar[5]:.0f}",
        "cntg_vol": str(bar[6]),
    }


@dataclass
class StockMarket:
    sessions: dict[date, list[tuple]]

    def rows(self, day: date) -> list[dict]:
        return [_row(bar) for bar in self.sessions.get(day, [])]


class FakeClock:
    def __init__(self, start: datetime):
        self.moment = start.replace(tzinfo=producer_mod.KST)

    def now(self) -> datetime:
        return self.moment

    def sleep(self, seconds: float) -> None:
        self.moment += timedelta(seconds=max(0.0, seconds))


class FakeStockQuotes:
    """GET-only by construction. A row for minute ``m`` appears 1.1 s after ``m``."""

    def __init__(self, market: StockMarket, clock: FakeClock):
        self.market, self.clock = market, clock
        self.http = None
        self.last_received_kst = clock.now()
        self.requested: list[tuple[str, date]] = []

    def _visible(self, day: date) -> list[dict]:
        rows = self.market.rows(day)
        if day != TARGET:
            return rows
        now = self.clock.now().replace(tzinfo=None)
        return [
            row
            for row in rows
            if datetime.strptime(
                row["stck_bsop_date"] + row["stck_cntg_hour"], "%Y%m%d%H%M%S"
            )
            + timedelta(seconds=1.1)
            <= now
        ]

    def page(self, symbol: str, day: date, cursor: str = "") -> list[dict]:
        self.requested.append((symbol, day))
        self.clock.sleep(0.05)
        self.last_received_kst = self.clock.now()
        return self._visible(day)[-120:]

    def history(self, symbol: str, day: date) -> list[dict]:
        self.requested.append((symbol, day))
        self.clock.sleep(0.05)
        self.last_received_kst = self.clock.now()
        return self._visible(day)


def _stock_calendar(tmp_path: Path) -> Path:
    source = yaml.safe_load(
        (_REPO_ROOT / "config/tos_runtime/cp3-setup-d-long/calendar.yaml").read_text(
            encoding="utf-8"
        )
    )
    source["sessions"] = {
        "krx-stock": [
            {"phase": "CONTINUOUS", "start": "09:00", "end": TARGET_SESSION_END}
        ]
    }
    path = tmp_path / "calendar.yaml"
    path.write_text(yaml.safe_dump(source, allow_unicode=True), encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def market() -> StockMarket:
    sessions = {
        day: _stock_bars(
            day, count=STOCK_SESSION_BARS, base=61000.0, width=60.0 - 4 * index
        )
        for index, day in enumerate(SEED_DAYS)
    }
    sessions[TARGET] = _stock_bars(TARGET, count=TARGET_BARS, base=61000.0, width=90.0)
    return StockMarket(sessions)


@pytest.mark.serial
def test_a_stock_session_publishes_b1a_equal_lines_under_the_stock_layout(
    tmp_path: Path, market: StockMarket
) -> None:
    data = _stock_data(
        calendar_yaml=str(_stock_calendar(tmp_path)),
        env_file=str(tmp_path / "env"),
        token_cache_dir=str(tmp_path / "token-cache"),
    )
    config = config_mod.load_config(_write(tmp_path, data), repo_root=_REPO_ROOT)
    clock = FakeClock(datetime(TARGET.year, TARGET.month, TARGET.day, 8, 59, 30))
    quotes = FakeStockQuotes(market, clock)
    producer = producer_mod.LiveProducer(
        config=config,
        instrument=SYMBOL,
        target=TARGET,
        session_dir=tmp_path / "session",
        journal_path=tmp_path / "session" / "journal.jsonl",
        clock=producer_mod.Clock(now=clock.now, sleep=clock.sleep),
        quotes_factory=lambda _config, _log: quotes,
    )
    producer.boot()
    producer.run_session()
    summary = producer.finish()

    # Every request, seed walk included, named the symbol — no roll.
    assert {symbol for symbol, _ in quotes.requested} == {SYMBOL}
    assert producer.seed.contracts_used == (SYMBOL,)
    assert producer.anchor.kst == "09:00"
    assert producer.manifest.junctions == ()
    assert [s.contract for s in producer.manifest.segments] == [SYMBOL]

    market_root = tmp_path / "session" / "market"
    assert (market_root / "stock" / "minute" / f"code={SYMBOL}").is_dir()
    assert not (market_root / "futures").exists()

    rows = [
        json.loads(line)
        for line in producer.journal_path.read_text("utf-8").splitlines()
        if line.strip()
    ]
    assert rows, summary
    assert {row["instrument"] for row in rows} == {SYMBOL}
    assert all(row["raw_event_id"].startswith(f"{SYMBOL}:1m:") for row in rows)
    assert summary["counters"]["published"] == len(rows)

    # B1a over the SAME raw rows (seed days actually used + the target day).
    bars: list[tuple] = []
    for day in [*producer.seed.days_used, TARGET]:
        bars.extend(
            parse_ohlcv(SYMBOL, day.strftime("%Y%m%d"), {"output2": market.rows(day)})
        )
    reference = produce_bars(
        bars_to_frame(bars),
        symbol=SYMBOL,
        strategy=load_strategy_inputs(config.strategy_yaml),
        contract_spec=resolve_contract_spec(
            SYMBOL,
            ContractSpecRegistry.from_yaml(
                str(config.execution_yaml), block="stock_contract_spec"
            ),
        ),
        anchor=resolve_open_anchor(
            cli_value="09:00", first_session=TARGET, last_session=TARGET
        ),
    )
    expected = {r.raw_event_id: r.fields for r in reference.records}
    live = {row["raw_event_id"]: row["fields"] for row in rows}
    assert set(live) <= set(expected)
    assert {key for key in live if live[key] != expected[key]} == set()


def test_an_open_anchor_that_disagrees_with_the_calendar_is_refused(
    tmp_path: Path, market: StockMarket
) -> None:
    """``open_anchor`` 09:05 against a calendar opening at 09:00 → refused at boot."""
    data = _stock_data(
        calendar_yaml=str(_stock_calendar(tmp_path)),
        env_file=str(tmp_path / "env"),
        token_cache_dir=str(tmp_path / "token-cache"),
        open_anchor="09:05",
    )
    config = config_mod.load_config(_write(tmp_path, data), repo_root=_REPO_ROOT)
    clock = FakeClock(datetime(TARGET.year, TARGET.month, TARGET.day, 8, 59, 30))
    producer = producer_mod.LiveProducer(
        config=config,
        instrument=SYMBOL,
        target=TARGET,
        session_dir=tmp_path / "session",
        journal_path=tmp_path / "session" / "journal.jsonl",
        clock=producer_mod.Clock(now=clock.now, sleep=clock.sleep),
        quotes_factory=lambda _c, _l: FakeStockQuotes(market, clock),
    )
    with pytest.raises(LiveProducerRefused, match="open_anchor 09:05"):
        producer.boot()
    producer.finish()
