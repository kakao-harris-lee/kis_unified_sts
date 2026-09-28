"""``KisQuoteObservationIntake`` tests — the monotonic request anchor, phantom-churn dedup with
a deferred digest, token lifecycle sharing, broker rejection/malformed-response refusals,
negative-greps, and the arithmetic the anchor buys: an injected transport delay lands in
``source_age`` and decides FRESH/STALE against the deployed paper bounds (TOS tick-source wave,
W2 lane; issue #810, plan
``docs/plans/2026-09-28-tos-kis-quote-request-anchor-plan.md``).

``poll`` now returns :class:`~tos_runtime.marketfeed.ports.MonotonicAnchoredObservation` — no
wall-clock value at all — so every test that needs a ``RawObservation`` finalizes one the way the
scheduler does, through :func:`~tos_runtime.marketfeed.ports.anchor_observation`."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from tos.time import FreshnessVerdict, HealthState, freshness_verdict
from tos_runtime.marketfeed.ports import (
    MonotonicAnchoredObservation,
    RawObservation,
    anchor_observation,
)
from tos_runtime.marketfeed.time_projection import _DELAY_BOUND_FIELDS
from tos_runtime.time.config import load_time_config
from tos_runtime.time.service import TrustworthyTimeService
from tos_runtime.time.sources import LocalSystemClockReader, ProcessMonotonicSource
from tos_runtime.transport.kis_quote.adapter import (
    KisQuoteAdapterError,
    KisQuoteMalformedResponse,
    KisQuoteObservationIntake,
    KisQuoteRejected,
    TokenStale,
    build_quote_client,
)
from tos_runtime.transport.kis_quote.config import KisQuoteTransportConfig

from ..kis_mock._fake_kis_server import FakeKisServer
from ._fakes import (
    FakeMonotonicSource,
    InMemoryCredentialCustody,
    InMemoryEvidencePort,
    RecordingEvidenceSink,
)
from ._fakes import (
    runtime_identity as _runtime_identity,
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
    monotonic: Any = None,
    evidence: RecordingEvidenceSink | None = None,
    **config_overrides: Any,
) -> tuple[KisQuoteObservationIntake, Any, RecordingEvidenceSink]:
    """The intake under test. ``monotonic`` defaults to the controllable fake — the delay
    tests below pass a REAL :class:`~tos_runtime.time.sources.ProcessMonotonicSource`
    instead, because a fake that never moves cannot show a transport delay."""
    config = _config(server, **config_overrides)
    client = build_quote_client(config)
    monotonic = monotonic if monotonic is not None else FakeMonotonicSource()
    evidence = evidence if evidence is not None else RecordingEvidenceSink()
    intake = KisQuoteObservationIntake(
        config=config,
        client=client,
        custody=custody if custody is not None else _custody(),
        monotonic=monotonic,
        evidence_sink=evidence,
    )
    return intake, monotonic, evidence


#: The wall-clock instants these tests hand to :func:`anchor_observation` when they need a
#: finalized observation — the scheduler's job, performed explicitly here so this module tests
#: the adapter and not the mapping (``tests/time/test_service.py`` owns that).
_ANCHOR_AS_OF_MS = 1_700_000_000_000
_ANCHOR_RECEIVED_MS = _ANCHOR_AS_OF_MS + 40


def _anchor(
    pending: MonotonicAnchoredObservation, *, as_of_ms: int = _ANCHOR_AS_OF_MS
) -> RawObservation:
    """Finalize ``pending`` exactly as ``TickScheduler._anchor_polled`` does."""
    return anchor_observation(
        pending,
        as_of_ms=as_of_ms,
        received_ms=as_of_ms + (_ANCHOR_RECEIVED_MS - _ANCHOR_AS_OF_MS),
    )


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
    delay_s: float = 0.0,
) -> None:
    """Script the quote route. ``delay_s`` is the fake server's own transport delay — the
    injected round trip the #810 anchor tests measure."""
    output = {"stck_prpr": stck_prpr, "acml_vol": acml_vol}
    if extra_output:
        output.update(extra_output)
    server.set_response(
        route,
        status=200,
        body={"rt_cd": rt_cd, "msg1": "정상처리 되었습니다", "output": output},
        delay_s=delay_s,
    )


# ---------------------------------------------------------------------------
# happy path
# ---------------------------------------------------------------------------


def test_first_poll_emits_one_pending_observation_bracketing_the_request(
    server: FakeKisServer,
) -> None:
    """#810: the poll hands back the two MONOTONIC instants its request spanned, and no
    wall-clock value at all — the anchor is the scheduler's to stamp."""
    _set_token(server)
    _set_quote(server)
    intake, monotonic, _ = _intake(server)

    observations = intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    assert len(observations) == 1
    pending = observations[0]
    assert isinstance(pending, MonotonicAnchoredObservation)
    assert pending.instrument == INSTRUMENT
    assert pending.source_id == "kis_quote_mock_stock"
    assert pending.fields == (("last_price", "71300"), ("volume", 12345))
    # The fake monotonic source does not move on its own, so both readings are its current
    # value: the ORDER is what this asserts, not a duration (the delay tests below measure one).
    assert pending.requested_monotonic_ms == monotonic.now_ms()
    assert pending.received_monotonic_ms >= pending.requested_monotonic_ms


def test_the_adapter_reads_no_wall_clock_anywhere(server: FakeKisServer) -> None:
    """The #810 fix, pinned STRUCTURALLY rather than by behaviour: no attribute named
    ``wall_clock_now``/``wall_clock_now_if_fresh`` is accessed anywhere in the adapter module.

    An AST walk, not a text grep: the module docstring legitimately NAMES ``wall_clock_now``
    when explaining why it is not called, and a grep would either fail on that sentence or be
    weakened until it stopped catching a real call. Mutation: put any wall-clock read back into
    ``poll`` -> red.
    """
    import ast

    from tos_runtime.transport.kis_quote import adapter as adapter_module

    tree = ast.parse(Path(adapter_module.__file__).read_text(encoding="utf-8"))
    accessed = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert not accessed & {"wall_clock_now", "wall_clock_now_if_fresh"}


def test_quote_get_carries_the_measured_header_shape(server: FakeKisServer) -> None:
    _set_token(server)
    _set_quote(server)
    intake, _, _ = _intake(server)
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
    intake, _, _ = _intake(server)

    intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)
    _set_quote(server, stck_prpr="71400")  # a genuinely new price for poll #2
    intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    assert len(server.requests_for(TOKEN_PATH)) == 1
    assert len(server.requests_for(QUOTE_ROUTE)) == 2


# ---------------------------------------------------------------------------
# phantom-churn dedup (module docstring's central design decision)
# ---------------------------------------------------------------------------


def test_second_poll_with_identical_content_returns_nothing_new_once_consumed(
    server: FakeKisServer,
) -> None:
    """The phantom-churn guarantee, after #810 made the digest deferred: it holds as soon as
    the first emission was CONSUMED, which the advanced ``after_as_of_ms`` is the signal for
    (module docstring's deferred-digest note)."""
    _set_token(server)
    _set_quote(server)
    intake, _, _ = _intake(server)

    first = intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)
    assert len(first) == 1
    consumed_as_of_ms = _anchor(first[0]).as_of_ms

    # Same body served again — the market has not moved, and the previous observation was
    # durably consumed (the store's high-water mark advanced to it).
    second = intake.poll(instrument=INSTRUMENT, after_as_of_ms=consumed_as_of_ms)
    assert second == ()
    # The quote GET still happened (KIS has no "since" parameter — module docstring) —
    # only the EMISSION is suppressed, not the poll itself.
    assert len(server.requests_for(QUOTE_ROUTE)) == 2


def test_content_change_after_no_op_polls_emits_a_new_observation(
    server: FakeKisServer,
) -> None:
    _set_token(server)
    _set_quote(server)
    intake, _, _ = _intake(server)

    first = intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)
    consumed_as_of_ms = _anchor(first[0]).as_of_ms
    assert intake.poll(instrument=INSTRUMENT, after_as_of_ms=consumed_as_of_ms) == ()

    _set_quote(server, stck_prpr="71500")
    third = intake.poll(instrument=INSTRUMENT, after_as_of_ms=consumed_as_of_ms)

    assert len(third) == 1
    assert third[0].fields == (("last_price", "71500"), ("volume", 12345))
    assert third[0].content_digest != first[0].content_digest


def test_two_emitted_observations_never_share_a_raw_event_id(
    server: FakeKisServer,
) -> None:
    _set_token(server)
    _set_quote(server, stck_prpr="71300")
    intake, _, _ = _intake(server)
    first = intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)
    first_as_of_ms = _ANCHOR_AS_OF_MS

    _set_quote(server, stck_prpr="71600")
    second = intake.poll(instrument=INSTRUMENT, after_as_of_ms=first_as_of_ms)
    second_as_of_ms = first_as_of_ms + 1_000

    # Reverts to the FIRST price at a THIRD, later instant — a legitimate, distinct
    # observation (module docstring: content reappearing later is not a collision).
    _set_quote(server, stck_prpr="71300")
    third = intake.poll(instrument=INSTRUMENT, after_as_of_ms=second_as_of_ms)
    third_as_of_ms = second_as_of_ms + 1_000

    ids = {
        _anchor(first[0], as_of_ms=first_as_of_ms).raw_event_id,
        _anchor(second[0], as_of_ms=second_as_of_ms).raw_event_id,
        _anchor(third[0], as_of_ms=third_as_of_ms).raw_event_id,
    }
    assert len(ids) == 3


# ---------------------------------------------------------------------------
# instrument-scope refusal
# ---------------------------------------------------------------------------


def test_poll_for_a_different_instrument_refuses_with_zero_network(
    server: FakeKisServer,
) -> None:
    _set_token(server)
    _set_quote(server)
    intake, _, _ = _intake(server)

    with pytest.raises(KisQuoteAdapterError, match="005930"):
        intake.poll(instrument="000660", after_as_of_ms=None)

    assert server.all_requests == []


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
    intake, _, _ = _intake(server)

    with pytest.raises(KisQuoteRejected, match="모의투자 조회 실패"):
        intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)


def test_non_json_body_refuses_the_whole_poll(server: FakeKisServer) -> None:
    _set_token(server)
    # set_response always serializes `body` as JSON via the fake server, so a genuinely
    # non-JSON body needs a raw route override — set_response with body=None sends an
    # empty payload, which the client's own `_do_request` treats as `json=None`.
    server.set_response(QUOTE_ROUTE, status=200, body=None)
    intake, _, _ = _intake(server)

    with pytest.raises(
        KisQuoteMalformedResponse, match="did not parse as a JSON object"
    ):
        intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)


def test_output_not_an_object_refuses(server: FakeKisServer) -> None:
    _set_token(server)
    server.set_response(
        QUOTE_ROUTE, status=200, body={"rt_cd": "0", "output": "not-an-object"}
    )
    intake, _, _ = _intake(server)

    with pytest.raises(KisQuoteMalformedResponse, match="not a JSON object"):
        intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)


def test_missing_mapped_field_refuses(server: FakeKisServer) -> None:
    _set_token(server)
    server.set_response(
        QUOTE_ROUTE,
        status=200,
        body={"rt_cd": "0", "output": {"stck_prpr": "71300"}},  # acml_vol missing
    )
    intake, _, _ = _intake(server)

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
    intake, _, _ = _intake(server)

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
    # Token age/cooldown is governed by the injected MonotonicSource (adapter.py's own "one
    # clock, two jobs" note) — the same source the request anchor reads, for two different
    # jobs.
    intake, monotonic, evidence = _intake(server, token_reissue_min_interval_s=300)

    intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)  # issues the first token
    monotonic.advance(
        2_000
    )  # token (expires_in=1s) is now stale; cooldown (300s) not elapsed

    with pytest.raises(TokenStale):
        intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    assert evidence.of_kind("TRANSPORT_TOKEN_STALE")


def test_token_reissues_once_cooldown_elapses(server: FakeKisServer) -> None:
    _set_token(server, expires_in=1)
    _set_quote(server)
    intake, monotonic, _ = _intake(server, token_reissue_min_interval_s=1)

    intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)
    monotonic.advance(2_000)  # both the token AND the cooldown have now elapsed
    _set_quote(server, stck_prpr="71900")
    intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    assert len(server.requests_for(TOKEN_PATH)) == 2


def test_token_pacing_never_depends_on_wall_clock_trust(server: FakeKisServer) -> None:
    """Pins the bug an earlier revision of this module had: deriving the token lifecycle's
    clock from ``wall_clock_now()`` made token pacing depend on wall-clock TRUST, which is
    wrong — a live token stays live even while wall-clock trust is degraded, because the two
    facts are unrelated (adapter.py module docstring's own note against reintroducing it).

    Since #810 this intake holds no wall-clock source at all, so the coupling is now
    structurally impossible rather than merely absent — what this test still pins is that a
    poll keeps working with no trusted time anywhere in sight, which is exactly the situation
    the scheduler's ``SKIPPED_TIME_UNANCHORED`` handles afterwards.
    """
    _set_token(server, expires_in=86400)
    _set_quote(server)
    intake, monotonic, _ = _intake(server)

    intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)  # issues + caches the token

    monotonic.advance(1_000)
    _set_quote(server, stck_prpr="72000")
    (pending,) = intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    assert pending.requested_monotonic_ms == 1_000
    # No second token request: the cached token (expires_in=86400s) is still live.
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
    intake, _, _ = _intake(server)
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
    intake, _, _ = _intake(server)

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
# the #810 request anchor, measured end to end against the fake KIS server:
# an injected transport delay lands in `source_age`, and decides FRESH/STALE
# against the DEPLOYED paper bounds. Inverts the two pins #811 left here —
# "STALE at every admissible spacing" and "an unconsumed quote is dropped".
# ---------------------------------------------------------------------------

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

#: An injected transport delay comfortably past the deployed 800 ms budget (asserted below
#: against the loaded file, never assumed).
_SLOW_ROUND_TRIP_S = 1.0


def _paper_budget() -> tuple[Any, tuple[int, ...], int]:
    """``(time config, delay bounds, budget_ms)`` from the DEPLOYED paper ``time.yaml``.

    The budget is the kernel's own freshness arithmetic rearranged: ``freshness_verdict`` calls
    STALE when ``source_age + sum(delay_bounds) > max_age_bound``
    (``tos/src/tos/time/predicates.py``), so the age that still fits is
    ``max_age_bound - sum(delay_bounds)``.
    """
    config = load_time_config(_PAPER_TIME_YAML)
    delay_bounds = tuple(
        getattr(config, field_name) for field_name in _DELAY_BOUND_FIELDS
    )
    return (
        config,
        delay_bounds,
        (config.max_time_conservative_freshness_age_ms - sum(delay_bounds)),
    )


def _trusted_time_service(
    monotonic: ProcessMonotonicSource, config: Any
) -> TrustworthyTimeService:
    """A REAL :class:`~tos_runtime.time.service.TrustworthyTimeService` on the REAL local
    clock readers, driven to ``TRUSTED`` — not a double.

    The mapping under test is that service's own ``wall_clock_at_monotonic`` arithmetic
    (``tests/time/test_service.py`` pins its edges); re-implementing it in a fake here would
    make these tests pass whatever the real one does.
    """
    service = TrustworthyTimeService(
        monotonic=monotonic,
        references=(LocalSystemClockReader(),),
        config=config,
        identity=_runtime_identity(),
        evidence=InMemoryEvidencePort(),
    )
    service.start()
    service.evaluate()  # UNINITIALIZED -> SYNCHRONIZING
    service.evaluate()  # -> TRUSTED
    assert service.health_state is HealthState.TRUSTED
    return service


def _anchored_source_age(
    *, server: FakeKisServer, delay_s: float
) -> tuple[int, tuple[int, ...], Any, int]:
    """Run ONE real pass — evaluate, poll (with ``delay_s`` injected into the quote route),
    evaluate — and return ``(source_age, delay_bounds, time config, budget_ms)``.

    The order mirrors :meth:`~tos_runtime.marketfeed.scheduler.TickScheduler.tick_once`
    exactly: the intake is read FIRST (#809) and the pending observation is anchored against
    the reading THIS pass's own evaluation produced (#810).
    """
    config, delay_bounds, budget_ms = _paper_budget()
    monotonic = ProcessMonotonicSource()
    time_service = _trusted_time_service(monotonic, config)

    _set_token(server)
    _set_quote(server, delay_s=delay_s)
    intake, _, _ = _intake(server, monotonic=monotonic)

    (pending,) = intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)
    time_service.evaluate()  # the pass's own evaluation, AFTER the intake read

    as_of_ms = time_service.wall_clock_at_monotonic(pending.requested_monotonic_ms)
    received_ms = time_service.wall_clock_at_monotonic(pending.received_monotonic_ms)
    assert as_of_ms is not None and received_ms is not None
    observation = anchor_observation(
        pending, as_of_ms=as_of_ms, received_ms=received_ms
    )
    reading_ms = time_service.wall_clock_now()
    assert reading_ms is not None
    return reading_ms - observation.as_of_ms, delay_bounds, config, budget_ms


def test_an_injected_transport_delay_lands_in_source_age_and_reads_stale(
    server: FakeKisServer,
) -> None:
    """**The inversion of #811's "STALE at every admissible spacing" pin.** Staleness is now
    decided by THIS request's own round trip, not by the pass spacing: a 1000 ms transport
    delay injected into the fake KIS server's quote route shows up in ``source_age`` (which is
    what the previous anchor could not see at all), and 1000 > the deployed 800 ms budget, so
    the kernel's own predicate answers STALE.

    Mutations: anchor on the RESPONSE instant instead of the request -> ``source_age`` drops to
    ~0 and the STALE assertion goes red (that is the pre-#809 fail-open); drop the delay
    injection -> the ``>= delay`` assertion goes red.
    """
    delay_ms = int(_SLOW_ROUND_TRIP_S * 1000)
    source_age, delay_bounds, config, budget_ms = _anchored_source_age(
        server=server, delay_s=_SLOW_ROUND_TRIP_S
    )

    assert source_age >= delay_ms
    assert delay_ms > budget_ms  # the deployed numbers, not a chosen pair
    assert (
        freshness_verdict(
            source_age=source_age,
            delay_bounds=delay_bounds,
            max_age_bound=config.max_time_conservative_freshness_age_ms,
            future_tolerance=config.max_future_timestamp_tolerance_ms,
        )
        is FreshnessVerdict.STALE
    )


def test_a_quick_round_trip_reads_fresh_against_the_same_budget(
    server: FakeKisServer,
) -> None:
    """The other half of the inversion — the one the old pin said was unreachable at any
    spacing the broker admits. With no injected delay the round trip is a loopback GET, the
    age is a handful of milliseconds, and the SAME deployed budget answers FRESH.

    ⚠ This assertion is a real timing claim, not a mock: it fails if this host cannot
    complete a loopback GET plus two time evaluations inside the deployed 800 ms budget. That
    is an honest failure — the intake's freshness genuinely depends on the round trip now —
    and 800 ms is roughly two orders of magnitude of slack over the measured path.
    """
    source_age, delay_bounds, config, budget_ms = _anchored_source_age(
        server=server, delay_s=0.0
    )

    assert 0 <= source_age <= budget_ms
    assert (
        freshness_verdict(
            source_age=source_age,
            delay_bounds=delay_bounds,
            max_age_bound=config.max_time_conservative_freshness_age_ms,
            future_tolerance=config.max_future_timestamp_tolerance_ms,
        )
        is FreshnessVerdict.FRESH
    )


def test_an_unconsumed_quote_is_re_emitted_by_this_intake_on_the_next_pass(
    server: FakeKisServer,
) -> None:
    """**The inversion of #811's dropped-quote pin.** A pass that polls and then declines to
    consume (``SKIPPED_TIME_NOT_EVALUATED``/``SKIPPED_TIME_UNANCHORED`` — no ``store.put``, so
    ``latest_as_of`` does not move) leaves the next poll asking from the SAME mark. This intake
    now reads that mark as its consumption signal and holds its digest PENDING, so the same
    quote is emitted again instead of being dropped until the price changes.

    Mutation: commit the digest inside ``poll`` (the pre-#810 behaviour) -> the second poll
    returns ``()`` -> red.
    """
    _set_token(server)
    _set_quote(server)
    intake, _, _ = _intake(server)

    # Pass 1: polled, then the pass's time evaluation failed — nothing consumed.
    (first,) = intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    # Pass 2 asks from the SAME unadvanced mark, and the quote has not moved.
    (second,) = intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    assert second.content_digest == first.content_digest
    assert second.fields == first.fields
    # It was re-served by a REAL second request, never replayed from a cache.
    assert len(server.requests_for(QUOTE_ROUTE)) == 2

    # ...and the phantom-churn guarantee still holds once an emission IS consumed.
    consumed_as_of_ms = _anchor(second).as_of_ms
    assert intake.poll(instrument=INSTRUMENT, after_as_of_ms=consumed_as_of_ms) == ()
    assert len(server.requests_for(QUOTE_ROUTE)) == 3


def test_a_first_poll_from_an_already_advanced_mark_does_not_lose_the_emission(
    server: FakeKisServer,
) -> None:
    """The restart case: this process's FIRST poll is asked from a non-``None`` mark (the
    durable store already holds snapshots from a previous run). There is no pending digest to
    commit, and the emission must still survive the next pass's re-poll if it is not consumed.

    Mutation: treat "the mark is not None" as an advance on the first poll -> nothing changes
    here, but the guard below (the second poll re-emitting from the same mark) would still
    hold; the real mutation this catches is committing the digest eagerly -> red.
    """
    _set_token(server)
    _set_quote(server)
    intake, _, _ = _intake(server)

    (first,) = intake.poll(instrument=INSTRUMENT, after_as_of_ms=1_700_000_000_000)
    (second,) = intake.poll(instrument=INSTRUMENT, after_as_of_ms=1_700_000_000_000)

    assert second.content_digest == first.content_digest
