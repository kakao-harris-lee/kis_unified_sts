"""``KisQuoteObservationIntake`` tests — the monotonic request anchor, phantom-churn dedup with"""

from __future__ import annotations

from collections.abc import Callable, Iterator
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
from tos_runtime.transport.kis_quote.adapter import (
    KIS_QUOTE_PACING_REFUSED_KIND,
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
    ScriptedClock,
    ScriptedMonotonicSource,
    ScriptedReferenceReader,
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
        "app_key_min_request_interval_ms": 1,
        "app_key_request_wait_budget_ms": 60_000,
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
    """The intake under test. ``monotonic`` defaults to the controllable fake — the delay"""
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
    on_request: Callable[[], None] | None = None,
) -> None:
    """Script the quote route. ``on_request`` runs inside the server's own quote handler,"""
    output = {"stck_prpr": stck_prpr, "acml_vol": acml_vol}
    if extra_output:
        output.update(extra_output)
    server.set_response(
        route,
        status=200,
        body={"rt_cd": rt_cd, "msg1": "정상처리 되었습니다", "output": output},
        on_request=on_request,
    )


def test_first_poll_emits_one_pending_observation_bracketing_the_request(
    server: FakeKisServer,
) -> None:
    """#810: the poll hands back the two MONOTONIC instants its request spanned, and no"""
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
    assert pending.requested_monotonic_ms == monotonic.now_ms()
    assert pending.received_monotonic_ms >= pending.requested_monotonic_ms


def test_a_refused_pacer_slot_is_nothing_new_with_one_evidence_row_and_no_get(
    server: FakeKisServer,
) -> None:
    """review-979 r1 LOW: like the band reader and the witness, a refused app-key slot (issue"""
    _set_token(server)
    _set_quote(server)
    intake, _, evidence = _intake(
        server,
        app_key_min_request_interval_ms=1_000,
        app_key_request_wait_budget_ms=500,
    )

    assert intake.poll(instrument=INSTRUMENT, after_as_of_ms=None) == ()
    assert server.requests_for(QUOTE_ROUTE) == []
    (row,) = evidence.of_kind(KIS_QUOTE_PACING_REFUSED_KIND)
    assert row["instrument"] == INSTRUMENT


def test_the_pacer_wait_stays_outside_the_request_anchor_span(
    server: FakeKisServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """review-979 r2 LOW-A: the token POST takes the app key's slot, so the quote GET waits a"""
    import tos_runtime.transport.kis_mock.pacer as pacer_module

    _set_token(server)
    _set_quote(server)
    intake, monotonic, _ = _intake(
        server,
        app_key_min_request_interval_ms=1_500,
        app_key_request_wait_budget_ms=3_000,
    )
    monkeypatch.setattr(
        pacer_module, "sleep", lambda seconds: monotonic.advance(round(seconds * 1000))
    )
    before = monotonic.now_ms()

    (pending,) = intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    assert pending.requested_monotonic_ms == before + 1_500
    assert pending.received_monotonic_ms - pending.requested_monotonic_ms == 0


def test_the_adapter_reads_no_wall_clock_anywhere(server: FakeKisServer) -> None:
    """The #810 fix, pinned STRUCTURALLY rather than by behaviour: no attribute named"""
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
    _set_quote(server, stck_prpr="71400")
    intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    assert len(server.requests_for(TOKEN_PATH)) == 1
    assert len(server.requests_for(QUOTE_ROUTE)) == 2


def test_second_poll_with_identical_content_returns_nothing_new_once_consumed(
    server: FakeKisServer,
) -> None:
    """The phantom-churn guarantee, after #810 made the digest deferred: it holds as soon as"""
    _set_token(server)
    _set_quote(server)
    intake, _, _ = _intake(server)

    first = intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)
    assert len(first) == 1
    consumed_as_of_ms = _anchor(first[0]).as_of_ms

    second = intake.poll(instrument=INSTRUMENT, after_as_of_ms=consumed_as_of_ms)
    assert second == ()
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

    _set_quote(server, stck_prpr="71300")
    third = intake.poll(instrument=INSTRUMENT, after_as_of_ms=second_as_of_ms)
    third_as_of_ms = second_as_of_ms + 1_000

    ids = {
        _anchor(first[0], as_of_ms=first_as_of_ms).raw_event_id,
        _anchor(second[0], as_of_ms=second_as_of_ms).raw_event_id,
        _anchor(third[0], as_of_ms=third_as_of_ms).raw_event_id,
    }
    assert len(ids) == 3


def test_poll_for_a_different_instrument_refuses_with_zero_network(
    server: FakeKisServer,
) -> None:
    _set_token(server)
    _set_quote(server)
    intake, _, _ = _intake(server)

    with pytest.raises(KisQuoteAdapterError, match="005930"):
        intake.poll(instrument="000660", after_as_of_ms=None)

    assert server.all_requests == []


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
        body={"rt_cd": "0", "output": {"stck_prpr": "71300"}},
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


def test_stale_token_and_unelapsed_cooldown_raises_token_stale(
    server: FakeKisServer,
) -> None:
    _set_token(server, expires_in=1)
    _set_quote(server)
    intake, monotonic, evidence = _intake(server, token_reissue_min_interval_s=300)

    intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)
    monotonic.advance(2_000)

    with pytest.raises(TokenStale):
        intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    assert evidence.of_kind("TRANSPORT_TOKEN_STALE")


def test_token_reissues_once_cooldown_elapses(server: FakeKisServer) -> None:
    _set_token(server, expires_in=1)
    _set_quote(server)
    intake, monotonic, _ = _intake(server, token_reissue_min_interval_s=1)

    intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)
    monotonic.advance(2_000)
    _set_quote(server, stck_prpr="71900")
    intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    assert len(server.requests_for(TOKEN_PATH)) == 2


def test_token_pacing_never_depends_on_wall_clock_trust(server: FakeKisServer) -> None:
    """Pins the bug an earlier revision of this module had: deriving the token lifecycle's"""
    _set_token(server, expires_in=86400)
    _set_quote(server)
    intake, monotonic, _ = _intake(server)

    intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    monotonic.advance(1_000)
    _set_quote(server, stck_prpr="72000")
    (pending,) = intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    assert pending.requested_monotonic_ms == 1_000
    assert len(server.requests_for(TOKEN_PATH)) == 1
    assert len(server.requests_for(QUOTE_ROUTE)) == 2


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
                "app_key_min_request_interval_ms": 2000,
                "app_key_request_wait_budget_ms": 4000,
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


_PAPER_TIME_YAML = (
    Path(__file__).resolve().parents[5]
    / "config"
    / "tos_runtime"
    / "paper"
    / "time.yaml"
)


def _paper_budget() -> tuple[Any, tuple[int, ...], int]:
    """``(time config, delay bounds, budget_ms)`` from the DEPLOYED paper ``time.yaml``."""
    config = load_time_config(_PAPER_TIME_YAML)
    delay_bounds = tuple(
        getattr(config, field_name) for field_name in _DELAY_BOUND_FIELDS
    )
    return (
        config,
        delay_bounds,
        (config.max_time_conservative_freshness_age_ms - sum(delay_bounds)),
    )


_BUDGET_MS = _paper_budget()[2]

_SLOW_ROUND_TRIP_MS = 1_000


def _trusted_time_service(
    monotonic: ScriptedMonotonicSource, reader: ScriptedReferenceReader, config: Any
) -> TrustworthyTimeService:
    """A REAL :class:`~tos_runtime.time.service.TrustworthyTimeService`, driven to ``TRUSTED``"""
    service = TrustworthyTimeService(
        monotonic=monotonic,
        references=(reader,),
        config=config,
        identity=_runtime_identity(),
        evidence=InMemoryEvidencePort(),
    )
    service.start()
    service.evaluate()
    service.evaluate()
    assert service.health_state is HealthState.TRUSTED
    return service


def _anchored_source_age(
    *, server: FakeKisServer, transport_ms: int
) -> tuple[int, tuple[int, ...], Any, int]:
    """Run ONE pass — evaluate, poll (with ``transport_ms`` of round trip injected by the"""
    config, delay_bounds, budget_ms = _paper_budget()
    clock = ScriptedClock()
    monotonic = ScriptedMonotonicSource(clock)
    time_service = _trusted_time_service(
        monotonic, ScriptedReferenceReader(clock), config
    )

    _set_token(server)
    _set_quote(server, on_request=lambda: clock.advance(transport_ms))
    intake, _, _ = _intake(server, monotonic=monotonic)

    (pending,) = intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)
    assert (
        pending.received_monotonic_ms - pending.requested_monotonic_ms == transport_ms
    )
    time_service.evaluate()

    as_of_ms = time_service.wall_clock_at_monotonic(pending.requested_monotonic_ms)
    received_ms = time_service.wall_clock_at_monotonic(pending.received_monotonic_ms)
    assert as_of_ms is not None and received_ms is not None
    observation = anchor_observation(
        pending, as_of_ms=as_of_ms, received_ms=received_ms
    )
    reading_ms = time_service.wall_clock_now()
    assert reading_ms is not None
    return reading_ms - observation.as_of_ms, delay_bounds, config, budget_ms


@pytest.mark.parametrize(
    "transport_ms",
    [
        pytest.param(_BUDGET_MS + 1, id="one-ms-over-the-budget"),
        pytest.param(_SLOW_ROUND_TRIP_MS, id="well-over-the-budget"),
    ],
)
def test_an_injected_transport_delay_lands_in_source_age_and_reads_stale(
    server: FakeKisServer, transport_ms: int
) -> None:
    """**The inversion of #811's "STALE at every admissible spacing" pin.** Staleness is now"""
    source_age, delay_bounds, config, budget_ms = _anchored_source_age(
        server=server, transport_ms=transport_ms
    )

    assert source_age == transport_ms
    assert transport_ms > budget_ms
    assert (
        freshness_verdict(
            source_age=source_age,
            delay_bounds=delay_bounds,
            max_age_bound=config.max_time_conservative_freshness_age_ms,
            future_tolerance=config.max_future_timestamp_tolerance_ms,
        )
        is FreshnessVerdict.STALE
    )


@pytest.mark.parametrize(
    "transport_ms",
    [
        pytest.param(0, id="instant-round-trip"),
        pytest.param(_BUDGET_MS, id="exactly-at-the-budget"),
    ],
)
def test_a_quick_round_trip_reads_fresh_against_the_same_budget(
    server: FakeKisServer, transport_ms: int
) -> None:
    """The other half of the inversion — the one the old pin said was unreachable at any"""
    source_age, delay_bounds, config, budget_ms = _anchored_source_age(
        server=server, transport_ms=transport_ms
    )

    assert source_age == transport_ms
    assert source_age <= budget_ms
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
    """**The inversion of #811's dropped-quote pin.** A pass that polls and then declines to"""
    _set_token(server)
    _set_quote(server)
    intake, _, _ = _intake(server)

    (first,) = intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    (second,) = intake.poll(instrument=INSTRUMENT, after_as_of_ms=None)

    assert second.content_digest == first.content_digest
    assert second.fields == first.fields
    assert len(server.requests_for(QUOTE_ROUTE)) == 2

    consumed_as_of_ms = _anchor(second).as_of_ms
    assert intake.poll(instrument=INSTRUMENT, after_as_of_ms=consumed_as_of_ms) == ()
    assert len(server.requests_for(QUOTE_ROUTE)) == 3


def test_a_first_poll_from_an_already_advanced_mark_does_not_lose_the_emission(
    server: FakeKisServer,
) -> None:
    """The restart case: this process's FIRST poll is asked from a non-``None`` mark (the"""
    _set_token(server)
    _set_quote(server)
    intake, _, _ = _intake(server)

    (first,) = intake.poll(instrument=INSTRUMENT, after_as_of_ms=1_700_000_000_000)
    (second,) = intake.poll(instrument=INSTRUMENT, after_as_of_ms=1_700_000_000_000)

    assert second.content_digest == first.content_digest
