"""``KisQuoteObservationIntake`` tests — receipt-time stamping, phantom-churn dedup, token
lifecycle sharing, broker rejection/malformed-response refusals, negative-greps, and the two
#809 read-order consequences this intake carries until #810: its stamp reads STALE at every
spacing the 모의 quote rate limit admits, and an unconsumed quote is dropped rather than
re-served (TOS tick-source wave, W2 lane)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from tos.time import FreshnessVerdict, freshness_verdict
from tos_runtime.marketfeed.time_projection import _DELAY_BOUND_FIELDS
from tos_runtime.time.config import load_time_config
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


# ---------------------------------------------------------------------------
# the #809 read-order transition: fail-open (always source_age 0) -> fail-closed
# (STALE at every spacing the 모의 quote rate limit admits), plus the re-read gap
# — both until #810 anchors `as_of` on a reading taken after the response
# ---------------------------------------------------------------------------

#: The smallest request spacing the 모의 quote rate limit allows — 1.0 rps clean / 2.0 rps
#: throttled (probe P-13,
#: ``docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml:1840-1846``), which is why a
#: ``kis_quote`` deployment cannot USEFULLY shrink ``poll_interval_ms`` the way the journal one
#: did. ⚠ A BROKER floor, not a configured or enforced one: nothing in the loader refuses a
#: shorter value, so the claim below is scoped to the spacings this limit admits.
_MIN_QUOTE_SPACING_MS = 1_000

#: The APPROVED paper bounds, read from the deployed file rather than re-typed here — the claim
#: under test is about THOSE numbers, and a guard that reads a second copy of what it guards is
#: the repeated defect shape this repo already records. parents: [0]=kis_quote, [1]=transport,
#: [2]=tests, [3]=runtime, [4]=tos, [5]=repo root (the same walk
#: ``tests/compose/test_deploy_approved_values.py`` does).
_PAPER_TIME_YAML = (
    Path(__file__).resolve().parents[5]
    / "config"
    / "tos_runtime"
    / "paper"
    / "time.yaml"
)


def test_the_previous_pass_stamp_exceeds_the_budget_at_every_admissible_spacing(
    server: FakeKisServer,
) -> None:
    """Pins the ARITHMETIC — stamp age against the deployed budget, across the spacings the
    broker admits — not the scheduler's read order, which ``tests/marketfeed/test_scheduler.py``
    owns. Makes the #809 consequence for this intake EXPLICIT rather than leaving it to be
    discovered in a rehearsal (plan ``docs/plans/2026-09-27-tos-freshness-read-order-plan.md``
    §2.4; operator disposition §6.1-2 accepted it).

    ``wall_clock_now()`` returns the reading the LAST ``evaluate()`` cached, never a fresh one
    (``time/service.py:697-711``), and since #809 ``TickScheduler.tick_once`` polls the intake
    BEFORE that evaluation runs. So the reading this adapter stamps is the PREVIOUS pass's, and
    by the time the kernel judges the observation the anchor has moved on by one pass spacing:
    ``source_age`` ≈ the spacing, not the 0 the pre-#809 wiring notes claimed. Against the
    deployed paper bounds the freshness budget is 800 ms, and the 모의 quote rate limit puts
    the smallest usable spacing at 1000 ms — so nothing the broker admits is FRESH. That is a
    fail-OPEN (an unmeasured HTTP round trip read as age 0) becoming a fail-CLOSED conservative
    over-estimate; #810 is where the anchor is actually fixed. Paper pins ``intake_kind:
    journal``, so nothing is deployed on this path.

    ⚠ The floor is the broker's, not the config's: no loader refuses a shorter
    ``poll_interval_ms`` here, and below ~800 ms this arithmetic comes out FRESH (the broker
    throttles instead). So the assertion below is ``budget_ms < _MIN_QUOTE_SPACING_MS`` — every
    spacing the RATE LIMIT admits — never "this intake can never be fresh".
    """
    _set_token(server)
    _set_quote(server)
    intake, wall_clock, _, _ = _intake(server)

    # The pass reads the intake first (#809), so this stamp is the previous evaluation's reading.
    (observation,) = intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)
    assert observation.as_of_ms == wall_clock.wall_clock_now()

    # ... and only THEN does this pass's own evaluation move the anchor on.
    wall_clock.advance(_MIN_QUOTE_SPACING_MS)
    this_pass_reading = wall_clock.wall_clock_now()
    assert this_pass_reading is not None
    source_age = this_pass_reading - observation.as_of_ms
    assert source_age == _MIN_QUOTE_SPACING_MS  # not 0 — that was the pre-#809 claim

    config = load_time_config(_PAPER_TIME_YAML)
    delay_bounds = tuple(
        getattr(config, field_name) for field_name in _DELAY_BOUND_FIELDS
    )
    budget_ms = config.max_time_conservative_freshness_age_ms - sum(delay_bounds)
    # The bound, not just this one spacing: nothing the rate limit permits fits the budget.
    assert budget_ms < _MIN_QUOTE_SPACING_MS
    assert (
        freshness_verdict(
            source_age=source_age,
            delay_bounds=delay_bounds,
            max_age_bound=config.max_time_conservative_freshness_age_ms,
            future_tolerance=config.max_future_timestamp_tolerance_ms,
        )
        is FreshnessVerdict.STALE
    )


def test_an_unconsumed_quote_is_dropped_by_this_intake_not_re_read_next_pass(
    server: FakeKisServer,
) -> None:
    """The gap in the #809 re-read guarantee, for THIS intake — tracked in #810.

    :attr:`~tos_runtime.marketfeed.ports.TickOutcome.SKIPPED_TIME_NOT_EVALUATED` means the
    scheduler performed no ``store.put``, so ``latest_as_of`` did not advance and the next pass
    asks ``poll`` from the SAME mark. That buys a re-read only from an intake whose ``poll`` is a
    pure function of ``after_as_of_ms``. This one is not: it ignores the argument entirely and
    commits ``_last_content_digest`` BEFORE returning, so the observation the scheduler declined
    to consume is dropped here — the next pass sees "nothing new" until the PRICE changes, and
    ``SKIPPED_NO_OBSERVATION`` is what the scheduler gets.

    Pinned rather than left implicit because the reorder is what made it reachable (before #809
    a failed evaluation skipped the whole pass, poll included). #810 is where the intake is
    fixed; when it is, this test inverts — the second poll returns the observation again.
    """
    _set_token(server)
    _set_quote(server)
    intake, _, _, _ = _intake(server)

    # Pass 1: polled, then the pass's time evaluation failed — nothing consumed.
    (first,) = intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    # Pass 2 asks from the SAME unadvanced mark, and the quote has not moved.
    second = intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    assert second == ()  # NOT (first,) — #810
    # It was dropped by the dedup, not withheld by a skipped request: the GET really happened.
    assert len(server.requests_for(QUOTE_ROUTE)) == 2

    # And it stays dropped until the price moves, which is the only thing that revives it.
    _set_quote(server, stck_prpr="71400")
    (third,) = intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)
    assert third.raw_event_id != first.raw_event_id
