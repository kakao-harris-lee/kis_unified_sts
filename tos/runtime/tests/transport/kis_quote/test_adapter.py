"""``KisQuoteObservationIntake`` tests — receipt-time stamping, phantom-churn dedup, token
lifecycle sharing, broker rejection/malformed-response refusals, and negative-greps (TOS
tick-source wave, W2 lane)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from tos_runtime.transport.kis_quote.adapter import (
    KisQuoteAdapterError,
    KisQuoteMalformedResponse,
    KisQuoteObservationIntake,
    KisQuoteRejected,
    KisQuoteWallClockUntrusted,
    TokenStale,
    build_quote_client,
)
from tos_runtime.transport.kis_quote.config import KisQuoteTransportConfig

from ..kis_mock._fake_kis_server import FakeKisServer
from ._fakes import (
    FakeMonotonicSource,
    FakeWallClock,
    InMemoryCredentialCustody,
    RecordingEvidenceSink,
)

QUOTE_PATH = "/uapi/domestic-stock/v1/quotations/inquire-price"
TOKEN_PATH = "/oauth2/tokenP"
INSTRUMENT = "005930"
MARKET_DIV = "J"
QUOTE_QUERY = f"FID_COND_MRKT_DIV_CODE={MARKET_DIV}&FID_INPUT_ISCD={INSTRUMENT}"
QUOTE_ROUTE = f"{QUOTE_PATH}?{QUOTE_QUERY}"
APP_KEY_SCOPE = "kis_mock.app_key"
APP_SECRET_SCOPE = "kis_mock.app_secret"
APP_KEY = b"test-app-key"
APP_SECRET = b"super-secret-value-should-never-leak"


@pytest.fixture
def server() -> Iterator[FakeKisServer]:
    srv = FakeKisServer()
    srv.start()
    try:
        yield srv
    finally:
        srv.stop()


def _config(server: FakeKisServer, **overrides: Any) -> KisQuoteTransportConfig:
    base: dict[str, Any] = {
        "endpoint_rest_base": server.rest_base,
        "quote_path": QUOTE_PATH,
        "token_path": TOKEN_PATH,
        "tr_id": "FHKST01010100",
        "instrument": INSTRUMENT,
        "market_div_code": MARKET_DIV,
        "field_mapping": {"stck_prpr": "last_price", "acml_vol": "volume"},
        "source_id": "kis_quote_mock_stock",
        "token_reissue_min_interval_s": 60,
        "request_timeout_s": 2.0,
        "allow_plaintext_for_tests": True,
    }
    base.update(overrides)
    return KisQuoteTransportConfig(**base)


def _custody() -> InMemoryCredentialCustody:
    return InMemoryCredentialCustody(
        {APP_KEY_SCOPE: APP_KEY, APP_SECRET_SCOPE: APP_SECRET}
    )


def _intake(
    server: FakeKisServer,
    *,
    custody: InMemoryCredentialCustody | None = None,
    wall_clock: FakeWallClock | None = None,
    monotonic: FakeMonotonicSource | None = None,
    evidence: RecordingEvidenceSink | None = None,
    **config_overrides: Any,
) -> tuple[
    KisQuoteObservationIntake, FakeWallClock, FakeMonotonicSource, RecordingEvidenceSink
]:
    config = _config(server, **config_overrides)
    client = build_quote_client(config)
    wall_clock = wall_clock if wall_clock is not None else FakeWallClock()
    monotonic = monotonic if monotonic is not None else FakeMonotonicSource()
    evidence = evidence if evidence is not None else RecordingEvidenceSink()
    intake = KisQuoteObservationIntake(
        config=config,
        client=client,
        custody=custody if custody is not None else _custody(),
        monotonic=monotonic,
        time_service=wall_clock,
        evidence_sink=evidence,
    )
    return intake, wall_clock, monotonic, evidence


def _set_token(server: FakeKisServer, *, expires_in: int = 86400) -> None:
    server.set_response(
        TOKEN_PATH, status=200, body={"access_token": "tok-1", "expires_in": expires_in}
    )


def _set_quote(
    server: FakeKisServer,
    *,
    stck_prpr: str = "71300",
    acml_vol: int = 12345,
    rt_cd: str = "0",
    route: str = QUOTE_ROUTE,
    extra_output: dict[str, Any] | None = None,
) -> None:
    output = {"stck_prpr": stck_prpr, "acml_vol": acml_vol}
    if extra_output:
        output.update(extra_output)
    server.set_response(
        route,
        status=200,
        body={"rt_cd": rt_cd, "msg1": "정상처리 되었습니다", "output": output},
    )


# ---------------------------------------------------------------------------
# happy path
# ---------------------------------------------------------------------------


def test_first_poll_emits_one_observation_stamped_with_receipt_time(
    server: FakeKisServer,
) -> None:
    _set_token(server)
    _set_quote(server)
    intake, wall_clock, _, _ = _intake(server)

    observations = intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    assert len(observations) == 1
    obs = observations[0]
    assert obs.instrument == INSTRUMENT
    assert obs.source_id == "kis_quote_mock_stock"
    assert obs.fields == (("last_price", "71300"), ("volume", 12345))
    # Both as_of_ms and received_ms are the SAME wall-clock reading (module docstring — receipt
    # time, never a value read from the response body).
    assert obs.as_of_ms == wall_clock.wall_clock_now()
    assert obs.received_ms == obs.as_of_ms


def test_quote_get_carries_the_measured_header_shape(server: FakeKisServer) -> None:
    _set_token(server)
    _set_quote(server)
    intake, _, _, _ = _intake(server)
    intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    quote_requests = server.requests_for(QUOTE_ROUTE)
    assert len(quote_requests) == 1
    headers = quote_requests[0].headers
    assert headers["tr_id"] == "FHKST01010100"
    assert headers["custtype"] == "P"
    assert headers["authorization"] == "Bearer tok-1"
    assert headers["appkey"] == APP_KEY.decode()
    assert headers["appsecret"] == APP_SECRET.decode()


def test_token_is_reused_across_polls_within_its_lifetime(
    server: FakeKisServer,
) -> None:
    _set_token(server, expires_in=86400)
    _set_quote(server)
    intake, wall_clock, _, _ = _intake(server)

    intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)
    _set_quote(server, stck_prpr="71400")  # a genuinely new price for poll #2
    wall_clock.advance(1_000)
    intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    assert len(server.requests_for(TOKEN_PATH)) == 1
    assert len(server.requests_for(QUOTE_ROUTE)) == 2


# ---------------------------------------------------------------------------
# phantom-churn dedup (module docstring's central design decision)
# ---------------------------------------------------------------------------


def test_second_poll_with_identical_content_returns_nothing_new(
    server: FakeKisServer,
) -> None:
    _set_token(server)
    _set_quote(server)
    intake, wall_clock, _, _ = _intake(server)

    first = intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)
    assert len(first) == 1

    wall_clock.advance(500)
    # Same body served again — the market has not moved.
    second = intake.poll(instrument=INSTRUMENT, after_as_of_ms=first[0].as_of_ms)
    assert second == ()
    # The quote GET still happened (KIS has no "since" parameter — module docstring) —
    # only the EMISSION is suppressed, not the poll itself.
    assert len(server.requests_for(QUOTE_ROUTE)) == 2


def test_content_change_after_no_op_polls_emits_a_new_observation(
    server: FakeKisServer,
) -> None:
    _set_token(server)
    _set_quote(server)
    intake, wall_clock, _, _ = _intake(server)

    first = intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)
    wall_clock.advance(500)
    assert intake.poll(instrument=INSTRUMENT, after_as_of_ms=None) == ()

    wall_clock.advance(500)
    _set_quote(server, stck_prpr="71500")
    third = intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    assert len(third) == 1
    assert third[0].fields == (("last_price", "71500"), ("volume", 12345))
    assert third[0].as_of_ms > first[0].as_of_ms
    assert third[0].raw_event_id != first[0].raw_event_id


def test_two_emitted_observations_never_share_a_raw_event_id(
    server: FakeKisServer,
) -> None:
    _set_token(server)
    _set_quote(server, stck_prpr="71300")
    intake, wall_clock, _, _ = _intake(server)
    first = intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    wall_clock.advance(1_000)
    _set_quote(server, stck_prpr="71600")
    second = intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    wall_clock.advance(1_000)
    # Reverts to the FIRST price at a THIRD, later instant — a legitimate, distinct
    # observation (module docstring: content reappearing later is not a collision).
    _set_quote(server, stck_prpr="71300")
    third = intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    ids = {first[0].raw_event_id, second[0].raw_event_id, third[0].raw_event_id}
    assert len(ids) == 3


# ---------------------------------------------------------------------------
# instrument-scope refusal
# ---------------------------------------------------------------------------


def test_poll_for_a_different_instrument_refuses_with_zero_network(
    server: FakeKisServer,
) -> None:
    _set_token(server)
    _set_quote(server)
    intake, _, _, _ = _intake(server)

    with pytest.raises(KisQuoteAdapterError, match="005930"):
        intake.poll(instrument="000660", after_as_of_ms=None)

    assert server.all_requests == []


# ---------------------------------------------------------------------------
# wall-clock trust gate
# ---------------------------------------------------------------------------


def test_untrusted_wall_clock_refuses_rather_than_returning_nothing_new(
    server: FakeKisServer,
) -> None:
    _set_token(server)
    _set_quote(server)
    wall_clock = FakeWallClock(start_ms=None)
    intake, _, _, _ = _intake(server, wall_clock=wall_clock)

    with pytest.raises(KisQuoteWallClockUntrusted):
        intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    # The poll itself still happened — the network round trip already completed by the time the
    # clock gate is checked (module docstring: the reading is taken AFTER the response arrives).
    assert len(server.requests_for(QUOTE_ROUTE)) == 1


# ---------------------------------------------------------------------------
# broker rejection / malformed response (fail-closed on malformed input)
# ---------------------------------------------------------------------------


def test_broker_rejection_raises_kis_quote_rejected(server: FakeKisServer) -> None:
    _set_token(server)
    server.set_response(
        QUOTE_ROUTE,
        status=200,
        body={"rt_cd": "1", "msg1": "모의투자 조회 실패", "output": {}},
    )
    intake, _, _, _ = _intake(server)

    with pytest.raises(KisQuoteRejected, match="모의투자 조회 실패"):
        intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)


def test_non_json_body_refuses_the_whole_poll(server: FakeKisServer) -> None:
    _set_token(server)
    # set_response always serializes `body` as JSON via the fake server, so a genuinely
    # non-JSON body needs a raw route override — set_response with body=None sends an
    # empty payload, which the client's own `_do_request` treats as `json=None`.
    server.set_response(QUOTE_ROUTE, status=200, body=None)
    intake, _, _, _ = _intake(server)

    with pytest.raises(
        KisQuoteMalformedResponse, match="did not parse as a JSON object"
    ):
        intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)


def test_output_not_an_object_refuses(server: FakeKisServer) -> None:
    _set_token(server)
    server.set_response(
        QUOTE_ROUTE, status=200, body={"rt_cd": "0", "output": "not-an-object"}
    )
    intake, _, _, _ = _intake(server)

    with pytest.raises(KisQuoteMalformedResponse, match="not a JSON object"):
        intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)


def test_missing_mapped_field_refuses(server: FakeKisServer) -> None:
    _set_token(server)
    server.set_response(
        QUOTE_ROUTE,
        status=200,
        body={"rt_cd": "0", "output": {"stck_prpr": "71300"}},  # acml_vol missing
    )
    intake, _, _, _ = _intake(server)

    with pytest.raises(KisQuoteMalformedResponse, match="acml_vol"):
        intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)


def test_mapped_field_of_unsupported_type_refuses(server: FakeKisServer) -> None:
    _set_token(server)
    server.set_response(
        QUOTE_ROUTE,
        status=200,
        body={
            "rt_cd": "0",
            "output": {"stck_prpr": None, "acml_vol": 1},
        },
    )
    intake, _, _, _ = _intake(server)

    with pytest.raises(KisQuoteMalformedResponse, match="unsupported type"):
        intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)


# ---------------------------------------------------------------------------
# shared token lifecycle (step 0 measurement 2 — TokenStale propagates unchanged)
# ---------------------------------------------------------------------------


def test_stale_token_and_unelapsed_cooldown_raises_token_stale(
    server: FakeKisServer,
) -> None:
    _set_token(server, expires_in=1)
    _set_quote(server)
    # Token age/cooldown is governed by the injected MonotonicSource ONLY (adapter.py's own
    # "two clocks, two jobs" note) — advancing wall_clock here would change as_of_ms but would
    # NOT affect token staleness at all; this test advances the monotonic clock specifically to
    # pin that separation.
    intake, wall_clock, monotonic, evidence = _intake(
        server, token_reissue_min_interval_s=300
    )

    intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)  # issues the first token
    monotonic.advance(
        2_000
    )  # token (expires_in=1s) is now stale; cooldown (300s) not elapsed
    wall_clock.advance(2_000)

    with pytest.raises(TokenStale):
        intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    assert evidence.of_kind("TRANSPORT_TOKEN_STALE")


def test_token_reissues_once_cooldown_elapses(server: FakeKisServer) -> None:
    _set_token(server, expires_in=1)
    _set_quote(server)
    intake, wall_clock, monotonic, _ = _intake(server, token_reissue_min_interval_s=1)

    intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)
    monotonic.advance(2_000)  # both the token AND the cooldown have now elapsed
    wall_clock.advance(2_000)
    _set_quote(server, stck_prpr="71900")
    intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    assert len(server.requests_for(TOKEN_PATH)) == 2


def test_wall_clock_trust_and_token_pacing_are_fully_independent(
    server: FakeKisServer,
) -> None:
    """Pins the bug an earlier revision of this module had: deriving the token lifecycle's
    clock from wall_clock_now() made token pacing depend on wall-clock TRUST, which is wrong —
    a live token stays live even while wall-clock trust is degraded, because the two facts are
    unrelated (adapter.py module docstring's "two clocks, two jobs")."""
    _set_token(server, expires_in=86400)
    _set_quote(server)
    intake, wall_clock, monotonic, _ = _intake(server)

    intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)  # issues + caches the token

    # Wall-clock trust degrades — but the token is nowhere near expiry (expires_in=86400s) and
    # the monotonic clock has not moved, so ensure_token_string() must reuse the cached token
    # without ever needing a fresh wall-clock reading of its own.
    wall_clock.set(None)
    monotonic.advance(1_000)
    _set_quote(server, stck_prpr="72000")

    with pytest.raises(KisQuoteWallClockUntrusted):
        intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    # The failure is the OBSERVATION stamp's own guard, not a token-lifecycle failure — no
    # second token request happened, and the quote GET itself still succeeded.
    assert len(server.requests_for(TOKEN_PATH)) == 1
    assert len(server.requests_for(QUOTE_ROUTE)) == 2


# ---------------------------------------------------------------------------
# secret non-disclosure (measured convention: appkey/appsecret headers ride EVERY
# authenticated KIS call, not only the token request — shared/kis/auth.py's own
# get_auth_headers() shape; kis_mock's own post_order does the same. The pin this repo's
# CLAUDE.md discipline actually supports is therefore narrower than "only on the token
# request": the secret must appear ONLY in the header slot every measured call already
# uses, and NEVER in a query string, a request body, or any exception message.)
# ---------------------------------------------------------------------------


def test_app_secret_never_appears_in_the_quote_query_string_or_body(
    server: FakeKisServer,
) -> None:
    _set_token(server)
    _set_quote(server)
    intake, _, _, _ = _intake(server)
    intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    quote_request = server.requests_for(QUOTE_ROUTE)[0]
    assert APP_SECRET.decode() not in quote_request.path
    assert APP_SECRET not in quote_request.body


def test_app_secret_never_appears_in_a_raised_exception_message(
    server: FakeKisServer,
) -> None:
    _set_token(server)
    server.set_response(
        QUOTE_ROUTE, status=200, body={"rt_cd": "1", "msg1": "rejected", "output": {}}
    )
    intake, _, _, _ = _intake(server)

    with pytest.raises(KisQuoteRejected) as excinfo:
        intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)
    assert APP_SECRET.decode() not in str(excinfo.value)


# ---------------------------------------------------------------------------
# host seal is structural, not documentation — a test that would pass if the seal were
# only a comment: build a REAL client/config pointed at the real domain and prove the
# LOADER itself refuses before any of this adapter's own code ever runs (the adapter has
# no independent host check of its own — it trusts the config loader entirely).
# ---------------------------------------------------------------------------


def test_config_loader_is_the_actual_host_seal_not_the_adapter(tmp_path: Path) -> None:
    from tos_runtime.transport.kis_quote.config import (
        KisQuoteTransportConfigError,
        load_kis_quote_transport_config,
    )

    raw_path = tmp_path / "kis_quote.yaml"
    import yaml

    raw_path.write_text(
        yaml.safe_dump(
            {
                "endpoint_rest_base": "https://openapi.koreainvestment.com:9443",
                "allow_plaintext_for_tests": False,
                "quote_path": QUOTE_PATH,
                "tr_id": "FHKST01010100",
                "market_div_code": MARKET_DIV,
                "instrument": INSTRUMENT,
                "token_path": TOKEN_PATH,
                "token_reissue_min_interval_s": 60,
                "field_mapping": {"stck_prpr": "last_price", "acml_vol": "volume"},
                "source_id": "kis_quote_mock_stock",
                "request_timeout_s": 2.0,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(KisQuoteTransportConfigError, match="REAL_PROD"):
        load_kis_quote_transport_config(
            raw_path,
            instance_mock_rest_base="https://openapivts.koreainvestment.com:29443",
            instance_real_rest_base="https://openapi.koreainvestment.com:9443",
        )
