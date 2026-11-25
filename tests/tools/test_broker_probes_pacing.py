"""Unit tests for order-probe call pacing (``tools/broker_probes/probes_order.py``)."""

from __future__ import annotations

import argparse
from typing import Any

import pytest

from tests.support.probe_auth import StubAuth, install_stub_auth
from tools.broker_probes import common, probes_order
from tools.broker_probes.common import ProbeCredentials, ProbeError, ProbeRun
from tools.broker_probes.probes_order import (
    DEFAULT_PACE_S,
    MockTradingClient,
    _CallPacer,
    add_order_args,
    effective_interval_ms,
    pace_interval_s,
)

_ACCOUNT = "1234567890"
_START = 1000.0
_RTT_S = 0.05


class _FakeTime:
    """Deterministic stand-in for the ``time`` module the probe harness sees."""

    def __init__(self, start: float = _START) -> None:
        self._now = start
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self._now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self._now += seconds

    def advance(self, seconds: float) -> None:
        """Move the clock without recording a sleep (simulates work happening)."""
        self._now += seconds


@pytest.fixture
def faketime(monkeypatch: pytest.MonkeyPatch) -> _FakeTime:
    fake = _FakeTime()
    monkeypatch.setattr(probes_order, "time", fake)
    monkeypatch.setattr(common, "time", fake)
    return fake


@pytest.fixture
def mock_creds() -> ProbeCredentials:
    return ProbeCredentials(
        app_key="test-key",
        app_secret="test-secret",
        account_no=_ACCOUNT,
        is_real=False,
        asset="futures",
    )


@pytest.fixture
def futures_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KIS_FUTURES_APP_KEY", "test-key")
    monkeypatch.setenv("KIS_FUTURES_APP_SECRET", "test-secret")
    monkeypatch.setenv("KIS_FUTURES_ACCOUNT_NO", _ACCOUNT)
    monkeypatch.delenv("KIS_TOKEN_CACHE_DIR", raising=False)


def _args(**overrides: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "symbol": "101S6000",
        "asset": "futures",
        "confirm": False,
        "quantity": 1,
        "price_offset_pct": 10.0,
        "samples": 1,
        "margin_pct": 50.0,
        "poll_ms": 200.0,
        "gap_ms": 200.0,
        "inter_trial_s": 1.0,
        "settle_seconds": 2.0,
        "visibility_timeout_s": 30.0,
        "late_window_s": 120.0,
        "max_pages": 10,
        "allow_fill": False,
        "pace_s": DEFAULT_PACE_S,
        "token_cache_dir": None,
        "out_dir": None,
        "note": None,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def _client(
    creds: ProbeCredentials, pace_s: float = DEFAULT_PACE_S
) -> MockTradingClient:
    run = ProbeRun(probe_id="P-5", title="t", mode="live", environment="MOCK_VTS")
    return MockTradingClient(creds, StubAuth(), run, pace_s=pace_s)


def _tick_price(price: float) -> probes_order.TickPrice:
    """A resting price snapped the way the probes snap one (tick from the YAML SoT)."""
    return probes_order.snap_to_tick(
        price,
        probes_order._futures_tick("101S6000"),
        side="BUY",
        marketable=False,
    )


def _install_recorder(
    monkeypatch: pytest.MonkeyPatch, fake: _FakeTime, *, visible_odnos: set[str]
) -> list[dict[str, Any]]:
    """Replace the transport with a recorder; return the live call log."""
    calls: list[dict[str, Any]] = []

    def _recorder(
        _session: Any,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        timeout: float = 15.0,
    ) -> tuple[int, dict[str, Any], float, str]:
        calls.append({"url": url, "method": method, "released_at": fake.monotonic()})
        fake.advance(_RTT_S)
        if "quotations/inquire-price" in url:
            payload: dict[str, Any] = {"rt_cd": "0", "output1": {"futs_prpr": "340.00"}}
        elif "trading/order-rvsecncl" in url:
            payload = {"rt_cd": "0", "output": {"ODNO": "0000000782"}}
        elif "trading/order" in url:
            odno = f"{len(calls):010d}"
            payload = {"rt_cd": "0", "output": {"ODNO": odno}}
        elif "trading/inquire-ccnl" in url:
            payload = {
                "rt_cd": "0",
                "output1": [
                    {"odno": str(int(o)).rjust(10), "qty": "1"}
                    for o in sorted(visible_odnos)
                ],
            }
        else:  # pragma: no cover - an unrecognised path is a test bug, not a pass
            raise AssertionError(f"unexpected probe URL: {url}")
        return 200, payload, _RTT_S * 1000.0, "{}"

    monkeypatch.setattr(probes_order, "http_json", _recorder)
    return calls


def test_first_call_is_not_delayed(faketime: _FakeTime) -> None:
    """An empty pacer has no previous call to be too close to."""
    released = _CallPacer(1.1).wait()

    assert faketime.sleeps == []
    assert released == _START


def test_second_call_sleeps_only_the_remaining_time(faketime: _FakeTime) -> None:
    """The interval is measured from the previous call, not added to it."""
    pacer = _CallPacer(1.1)
    pacer.wait()
    faketime.advance(0.4)

    released = pacer.wait()

    assert faketime.sleeps == [pytest.approx(0.7)]
    assert released == pytest.approx(_START + 1.1)


def test_a_slow_previous_call_costs_no_extra_sleep(faketime: _FakeTime) -> None:
    """Pacing is a floor, not a tax: time already spent counts toward it."""
    pacer = _CallPacer(1.1)
    pacer.wait()
    faketime.advance(2.0)

    released = pacer.wait()

    assert faketime.sleeps == []
    assert released == pytest.approx(_START + 2.0)


def test_successive_releases_are_never_closer_than_the_interval(
    faketime: _FakeTime,
) -> None:
    pacer = _CallPacer(1.1)
    released = []
    for _ in range(5):
        released.append(pacer.wait())
        faketime.advance(0.05)

    gaps = [b - a for a, b in zip(released[:-1], released[1:], strict=True)]
    assert all(gap >= 1.1 - 1e-9 for gap in gaps), gaps


def test_zero_interval_disables_pacing(faketime: _FakeTime) -> None:
    pacer = _CallPacer(0.0)
    pacer.wait()
    pacer.wait()

    assert faketime.sleeps == []


def test_negative_interval_is_clamped_not_reversed(faketime: _FakeTime) -> None:
    """Fail-safe: a nonsense interval must not produce a negative sleep."""
    pacer = _CallPacer(-5.0)
    pacer.wait()
    pacer.wait()

    assert pacer.interval_s == 0.0
    assert faketime.sleeps == []


def test_quote_then_submit_is_paced(
    monkeypatch: pytest.MonkeyPatch, faketime: _FakeTime, mock_creds: ProbeCredentials
) -> None:
    """The exact pair that broke P-5: a quote read followed by an order submit."""
    calls = _install_recorder(monkeypatch, faketime, visible_odnos=set())
    client = _client(mock_creds)

    client.futures_last_price("101S6000")
    client.submit_futures(
        client.futures_order_body("101S6000", 1, _tick_price(306.0), "BUY")
    )

    assert [c["url"].rsplit("/", 1)[-1] for c in calls] == ["inquire-price", "order"]
    gap = calls[1]["released_at"] - calls[0]["released_at"]
    assert gap == pytest.approx(DEFAULT_PACE_S)


def test_every_call_type_goes_through_the_pacer(
    monkeypatch: pytest.MonkeyPatch, faketime: _FakeTime, mock_creds: ProbeCredentials
) -> None:
    """quote, submit, inquire, cancel — one choke point, so none can opt out."""
    calls = _install_recorder(monkeypatch, faketime, visible_odnos=set())
    client = _client(mock_creds)

    client.futures_last_price("101S6000")
    client.submit_futures(
        client.futures_order_body("101S6000", 1, _tick_price(306.0), "BUY")
    )
    client.inquire_futures("101S6000")
    client.cancel_futures("0000000002", 1)
    client.replace_futures("0000000002", 1, _tick_price(305.0))

    assert len(calls) == 5
    gaps = [
        b["released_at"] - a["released_at"]
        for a, b in zip(calls[:-1], calls[1:], strict=True)
    ]
    assert all(gap == pytest.approx(DEFAULT_PACE_S) for gap in gaps), gaps


def test_pace_s_argument_reaches_the_transport(
    monkeypatch: pytest.MonkeyPatch, faketime: _FakeTime, mock_creds: ProbeCredentials
) -> None:
    """A non-default interval must actually change the spacing, not just be stored."""
    calls = _install_recorder(monkeypatch, faketime, visible_odnos=set())
    client = _client(mock_creds, pace_s=3.0)

    client.futures_last_price("101S6000")
    client.futures_last_price("101S6000")

    assert calls[1]["released_at"] - calls[0]["released_at"] == pytest.approx(3.0)


def test_last_send_instant_before_any_request_is_refused(
    mock_creds: ProbeCredentials,
) -> None:
    """Fail-closed: no silent 0.0 that would read as a 1970-era timestamp."""
    with pytest.raises(ProbeError, match="before any request was issued"):
        _client(mock_creds).last_send_instant()


def test_submit_latency_window_excludes_the_pacing_sleep(
    monkeypatch: pytest.MonkeyPatch, faketime: _FakeTime, mock_creds: ProbeCredentials
) -> None:
    """``sent_at_monotonic`` is the released instant, not a pre-gate timestamp."""
    calls = _install_recorder(monkeypatch, faketime, visible_odnos=set())
    client = _client(mock_creds)

    client.futures_last_price("101S6000")
    quote_returned_at = faketime.monotonic()
    placed, _parsed, _ms = client.submit_futures(
        client.futures_order_body("101S6000", 1, _tick_price(306.0), "BUY")
    )

    assert placed is not None
    submit_released_at = calls[1]["released_at"]
    assert placed.sent_at_monotonic == pytest.approx(submit_released_at)
    assert faketime.sleeps == [pytest.approx(DEFAULT_PACE_S - _RTT_S)]
    assert placed.sent_at_monotonic - quote_returned_at == pytest.approx(
        DEFAULT_PACE_S - _RTT_S
    )
    assert placed.sent_at_monotonic != pytest.approx(quote_returned_at)


def test_p5_reports_the_effective_poll_granularity_and_an_uninflated_latency(
    monkeypatch: pytest.MonkeyPatch,
    faketime: _FakeTime,
    futures_env: None,
) -> None:
    """End-to-end P-5 against a stub transport: one trial, one convergent poll."""
    visible: set[str] = set()
    _install_recorder(monkeypatch, faketime, visible_odnos=visible)
    install_stub_auth(monkeypatch)

    visible.add("0000000002")

    run = probes_order.probe_p5(_args(confirm=True, samples=1))

    assert run.errors == []
    assert run.measurements["poll_granularity_ms"] == pytest.approx(1100.0)
    assert "EFFECTIVE" in run.measurements["granularity_note"]

    trials = [obs for obs in run.observations if "latency_ms" in obs]
    assert len(trials) == 1
    latency_ms = trials[0]["latency_ms"]
    expected_ms = (DEFAULT_PACE_S + _RTT_S) * 1000.0
    assert latency_ms == pytest.approx(expected_ms, abs=1.0)
    assert latency_ms != pytest.approx(expected_ms + DEFAULT_PACE_S * 1000.0, abs=1.0)


@pytest.mark.parametrize(
    ("poll_ms", "pace_s", "expected"),
    [
        (200.0, 1.1, 1100.0),
        (2000.0, 1.1, 2000.0),
        (1100.0, 1.1, 1100.0),
        (200.0, 0.0, 200.0),
    ],
)
def test_effective_interval_is_the_wider_of_request_and_pacing(
    poll_ms: float, pace_s: float, expected: float
) -> None:
    assert effective_interval_ms(poll_ms, _args(pace_s=pace_s)) == pytest.approx(
        expected
    )


def test_effective_interval_defaults_when_pace_s_is_absent() -> None:
    """Probe functions are also called with hand-built namespaces."""
    bare = argparse.Namespace(poll_ms=200.0)

    assert pace_interval_s(bare) == pytest.approx(DEFAULT_PACE_S)
    assert effective_interval_ms(200.0, bare) == pytest.approx(1100.0)


def test_p5_dry_run_quotes_the_effective_interval(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """A dry run must not advertise a poll rate the pacer will not permit."""
    monkeypatch.setattr(
        probes_order,
        "MockTradingClient",
        lambda *a, **k: pytest.fail("dry-run built a client"),
    )

    run = probes_order.probe_p5(_args(confirm=False, poll_ms=200.0))

    said = " ".join(str(obs.get("would_send", "")) for obs in run.observations)
    assert "1100.0ms" in said
    assert "200.0ms" not in said


def test_p2_records_the_gap_that_reached_the_wire(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """A dedup bracket built on a gap that never happened would be wrong."""
    monkeypatch.setattr(
        probes_order,
        "MockTradingClient",
        lambda *a, **k: pytest.fail("dry-run built a client"),
    )

    run = probes_order.probe_p2(_args(confirm=False, gap_ms=200.0))

    gaps = [obs["gap_ms"] for obs in run.observations if "gap_ms" in obs]
    assert gaps == [pytest.approx(1100.0)]


def test_pace_s_is_registered_with_the_measured_default() -> None:
    parser = argparse.ArgumentParser()
    add_order_args(parser)

    assert parser.parse_args([]).pace_s == pytest.approx(DEFAULT_PACE_S)
    assert parser.parse_args(["--pace-s", "2.5"]).pace_s == pytest.approx(2.5)


def test_pace_s_help_cites_the_measurement_not_a_guess() -> None:
    """The default is defensible only if the artifact behind it is named."""
    parser = argparse.ArgumentParser()
    add_order_args(parser)
    help_text = " ".join(
        action.help or "" for action in parser._actions if action.dest == "pace_s"
    )

    assert "P-13" in help_text
    assert "1.0 rps" in help_text and "2.0 rps" in help_text
    assert "EGW00201" in help_text


def test_setup_passes_pace_s_to_the_client(
    monkeypatch: pytest.MonkeyPatch, futures_env: None
) -> None:
    """The CLI value must reach the client, not stop at the namespace."""
    captured: dict[str, Any] = {}

    class _Recorder:
        def __init__(
            self,
            creds: Any,
            auth: Any,
            run: Any,
            timeout: float = 15.0,
            pace_s: float = -1.0,
        ) -> None:
            captured["pace_s"] = pace_s

    monkeypatch.setattr(probes_order, "MockTradingClient", _Recorder)
    install_stub_auth(monkeypatch)

    probes_order._setup(probes_order.get("P-5"), _args(confirm=True, pace_s=2.5))

    assert captured["pace_s"] == pytest.approx(2.5)
