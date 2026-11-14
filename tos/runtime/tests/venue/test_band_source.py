"""``KisBandSourceReader`` — CP-3 band 원천 웨이브 plan §8 items 3, 4d (the timeout half) and 8"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

import pytest
from tos_runtime.custody.ports import CustodyError, CustodyScopeNotProvisioned
from tos_runtime.transport.kis_mock.client import (
    KisMockConnectionError,
    KisMockTimeoutError,
    RawResponse,
)
from tos_runtime.transport.kis_mock.token import TokenResponseError, TokenStale
from tos_runtime.transport.kis_quote.config import KisQuoteTransportConfig
from tos_runtime.venue.band_source import (
    VENUE_BAND_OBSERVED_KIND,
    KisBandSourceReader,
    KisQuoteGetBandSource,
    build_band_client,
)

from ._documents import (
    PVL_A05610_BASIS,
    PVL_A05610_LOWER,
    PVL_A05610_UPPER,
)

_TRADING_DATE = "20261008"
_SCALED_UPPER = 115918
_SCALED_LOWER = 98746
_SCALED_BASIS = 107332


def _transport_config(**overrides: Any) -> KisQuoteTransportConfig:
    base: dict[str, Any] = {
        "endpoint_rest_base": "http://127.0.0.1:1/",
        "quote_path": "/uapi/domestic-futureoption/v1/quotations/inquire-price",
        "token_path": "/oauth2/tokenP",
        "tr_id": "FHMIF10000000",
        "instrument": "A05610",
        "market_div_code": "F",
        "field_mapping": {"futs_prpr": "last_price"},
        "source_id": "kis-quote",
        "token_reissue_min_interval_s": 60,
        "request_timeout_s": 20.0,
        "allow_plaintext_for_tests": True,
        "app_key_min_request_interval_ms": 1,
        "app_key_request_wait_budget_ms": 60_000,
    }
    base.update(overrides)
    return KisQuoteTransportConfig(**base)


def _band_source(**overrides: Any) -> KisQuoteGetBandSource:
    base: dict[str, Any] = {
        "kind": "kis_quote_get",
        "tr_id": "FHMIF10000000",
        "instrument": "A05610",
        "upper_field": "futs_mxpr",
        "lower_field": "futs_llam",
        "basis_field": "futs_sdpr",
        "price_scale": 100,
        "timeout_ms": 5000,
        "bound": "trading_date_kst",
        "read_on": ("boot", "phase_change"),
        "failure": "unknown",
    }
    base.update(overrides)
    return KisQuoteGetBandSource(**base)


def _ok_body(
    *,
    upper: str = PVL_A05610_UPPER,
    lower: str = PVL_A05610_LOWER,
    basis: str | None = PVL_A05610_BASIS,
) -> dict[str, Any]:
    output: dict[str, Any] = {"futs_mxpr": upper, "futs_llam": lower}
    if basis is not None:
        output["futs_sdpr"] = basis
    return {"rt_cd": "0", "msg1": "정상처리 되었습니다.", "output": output}


class _FakeClient:
    """A ``get_quote``-shaped double. Records every call so the request's own shape (TR id,"""

    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.bodies: list[str] = []

    def get_quote(
        self,
        tr_id: str,
        query: str,
        *,
        access_token: str,  # noqa: ARG002 — part of the shape being doubled
        app_key: bytes,  # noqa: ARG002
        app_secret: bytes,  # noqa: ARG002
        path: str,
    ) -> RawResponse:
        self.calls.append({"tr_id": tr_id, "query": query, "path": path})
        nxt = self._responses.pop(0) if self._responses else None
        if isinstance(nxt, Exception):
            raise nxt
        if isinstance(nxt, RawResponse):
            self.bodies.append(nxt.text)
            return nxt
        assert isinstance(nxt, dict)
        text = json.dumps(nxt, sort_keys=True)
        self.bodies.append(text)
        return RawResponse(status=200, json=nxt, text=text)


class _FakeCredentials:
    def app_key(self) -> bytes:
        return b"key"

    def app_secret(self) -> bytes:
        return b"secret"


class _FakeSession:
    """A :class:`~tos_runtime.transport.kis_mock.credential_session.KisCredentialSession`"""

    def __init__(
        self,
        tokens: list[str | Exception] | None = None,
        *,
        credentials_error: Exception | None = None,
    ) -> None:
        self._tokens: list[str | Exception] = list(tokens or ["token-a"])
        self._credentials_error = credentials_error

    def ensure_token_string(self) -> str:
        value = self._tokens.pop(0) if len(self._tokens) > 1 else self._tokens[0]
        if isinstance(value, Exception):
            raise value
        return value

    @contextmanager
    def app_credentials(self) -> Iterator[_FakeCredentials]:
        if self._credentials_error is not None:
            raise self._credentials_error
        yield _FakeCredentials()


class _FakeMonotonic:
    def __init__(self) -> None:
        self._now = 1_000

    def now_ms(self) -> int:
        self._now += 1
        return self._now


class _Sink:
    def __init__(self) -> None:
        self.rows: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, kind: str, fields: Mapping[str, Any]) -> None:
        self.rows.append((kind, dict(fields)))

    def only(self) -> dict[str, Any]:
        assert len(self.rows) == 1, self.rows
        kind, fields = self.rows[0]
        assert kind == VENUE_BAND_OBSERVED_KIND
        return fields


def _reader(
    responses: list[Any],
    *,
    tick_size: int | None = 2,
    band_source: KisQuoteGetBandSource | None = None,
    trading_date: Any = _TRADING_DATE,
    tokens: list[str | Exception] | None = None,
    sink: _Sink | None = None,
    credentials_error: Exception | None = None,
) -> tuple[KisBandSourceReader, _Sink, _FakeClient]:
    evidence = sink if sink is not None else _Sink()
    client = _FakeClient(responses)
    dates = trading_date if isinstance(trading_date, list) else [trading_date]
    session = _FakeSession(tokens, credentials_error=credentials_error)
    reader = KisBandSourceReader(
        band_source=band_source if band_source is not None else _band_source(),
        transport_config=_transport_config(),
        client=client,  # type: ignore[arg-type]
        credential_session=session,  # type: ignore[arg-type]
        monotonic=_FakeMonotonic(),
        evidence_sink=evidence,
        trading_date_reader=lambda: dates.pop(0) if len(dates) > 1 else dates[0],
        tick_size=tick_size,
    )
    return reader, evidence, client


class TestValidationSet:
    """Plan §4.2's validation set — one test per clause."""

    def test_the_measured_band_is_accepted(self) -> None:
        reader, sink, client = _reader([_ok_body()])

        observation = reader.read()

        assert observation is not None
        assert (observation.price_min, observation.price_max) == (
            _SCALED_LOWER,
            _SCALED_UPPER,
        )
        assert observation.basis == _SCALED_BASIS
        assert observation.trading_date == _TRADING_DATE
        assert observation.instrument == "A05610"
        assert client.calls == [
            {
                "tr_id": "FHMIF10000000",
                "query": "FID_COND_MRKT_DIV_CODE=F&FID_INPUT_ISCD=A05610",
                "path": "/uapi/domestic-futureoption/v1/quotations/inquire-price",
            }
        ]
        row = sink.only()
        assert row["outcome"] == "OBSERVED"
        assert row["band_digest"] == observation.record_digest
        assert (
            observation.raw_payload_digest
            == hashlib.sha256(client.bodies[0].encode("utf-8")).hexdigest()
        )
        assert row["narrowed_intraday"] is False
        assert row["critical_input_snapshot_digest_role"] == "stand-in"

    def test_a_non_integral_scaled_bound_is_refused_not_rounded(self) -> None:
        """Plan §4.2 "반올림 금지". ``1159.185 × 100 = 115918.5`` is not a whole number; a"""
        reader, sink, _ = _reader([_ok_body(upper="1159.185")])

        assert reader.read() is None
        assert sink.only()["reason"] == "non_integral_scale"

    @pytest.mark.parametrize("value", ["Infinity", "-Infinity", "NaN"])
    def test_a_non_finite_bound_is_refused_not_raised(self, value: str) -> None:
        """Independent review M1: ``Decimal`` accepts these, they survive the multiply and"""
        reader, sink, _ = _reader([_ok_body(upper=value)])

        assert reader.read() is None
        assert sink.only()["reason"] == "non_integral_scale"

    def test_an_absent_bound_field_is_refused(self) -> None:
        reader, sink, _ = _reader(
            [{"rt_cd": "0", "output": {"futs_llam": PVL_A05610_LOWER}}]
        )

        assert reader.read() is None
        assert sink.only()["reason"] == "non_integral_scale"

    @pytest.mark.parametrize(
        ("lower", "upper"),
        [
            (PVL_A05610_UPPER, PVL_A05610_LOWER),
            (PVL_A05610_UPPER, PVL_A05610_UPPER),
            ("0.00", PVL_A05610_UPPER),
            ("-10.00", PVL_A05610_UPPER),
        ],
    )
    def test_an_unordered_or_non_positive_band_is_refused(
        self, lower: str, upper: str
    ) -> None:
        reader, sink, _ = _reader([_ok_body(lower=lower, upper=upper)])

        assert reader.read() is None
        assert sink.only()["reason"] == "band_not_ordered"

    def test_a_band_off_the_policy_tick_grid_is_refused(self) -> None:
        """Plan §4.2/§3: a tree still carrying ``tick_size: 5`` is caught HERE. The measured"""
        reader, sink, _ = _reader([_ok_body()], tick_size=5)

        assert reader.read() is None
        row = sink.only()
        assert row["reason"] == "off_tick_grid"
        assert "115918" in row["detail"] and "98746" in row["detail"]

    def test_an_absent_tick_size_is_refused(self) -> None:
        reader, sink, _ = _reader([_ok_body()], tick_size=None)

        assert reader.read() is None
        assert sink.only()["reason"] == "tick_size_absent"

    def test_a_rejected_poll_is_refused(self) -> None:
        reader, sink, _ = _reader(
            [{"rt_cd": "1", "msg1": "조회할 자료가 없습니다.", "output": {}}]
        )

        assert reader.read() is None
        row = sink.only()
        assert row["reason"] == "rt_cd_not_ok"
        assert "rt_cd='1'" in row["detail"]

    def test_a_body_that_is_not_json_is_refused(self) -> None:
        reader, sink, _ = _reader(
            [RawResponse(status=500, json=None, text="<html>gateway</html>")]
        )

        assert reader.read() is None
        row = sink.only()
        assert row["reason"] == "malformed_response"
        assert row["detail"] == "status=500"

    def test_an_output_block_that_is_not_an_object_is_refused(self) -> None:
        reader, sink, _ = _reader([{"rt_cd": "0", "output": []}])

        assert reader.read() is None
        assert sink.only()["reason"] == "malformed_output"


class TestTradingDateStamp:
    """Plan §4.2 ⚠ — the stamp is LOCAL, and a read that cannot be stamped is refused."""

    def test_an_unavailable_trading_date_refuses_before_any_request(self) -> None:
        reader, sink, client = _reader([_ok_body()], trading_date=None)

        assert reader.read() is None
        assert sink.only()["reason"] == "trading_date_unavailable"
        assert client.calls == []


class TestTimeoutMs:
    """Plan §8 4d's other half — the policy's ``timeout_ms`` is what the band client is built"""

    def test_the_client_is_built_with_the_policy_timeout_not_the_transport_one(
        self,
    ) -> None:
        client = build_band_client(
            _transport_config(request_timeout_s=20.0), _band_source(timeout_ms=5000)
        )

        assert client._timeout_s == 5.0  # noqa: SLF001 — the pinned conversion

    def test_a_timed_out_get_is_a_named_refusal(self) -> None:
        reader, sink, _ = _reader([KisMockTimeoutError("timed out after 5.0s")])

        assert reader.read() is None
        row = sink.only()
        assert row["reason"] == "transport_error"
        assert "timed out" in row["detail"]

    def test_a_connection_failure_is_a_named_refusal(self) -> None:
        reader, sink, _ = _reader([KisMockConnectionError("connection reset")])

        assert reader.read() is None
        assert sink.only()["reason"] == "transport_error"

    def test_a_stale_token_is_a_named_refusal(self) -> None:
        reader, sink, _ = _reader([_ok_body()], tokens=[TokenStale("cooldown")])

        assert reader.read() is None
        assert sink.only()["reason"] == "token_stale"

    def test_an_unusable_token_response_is_a_named_refusal(self) -> None:
        """Plan §4.6 / independent review M1: ``KisTokenLifecycle`` raises this when the token"""
        reader, sink, _ = _reader(
            [_ok_body()], tokens=[TokenResponseError("missing access_token")]
        )

        assert reader.read() is None
        row = sink.only()
        assert row["reason"] == "token_response_invalid"
        assert "access_token" in row["detail"]

    def test_a_token_request_that_never_completed_is_a_named_refusal(self) -> None:
        """Same review finding: the token call uses the same HTTP client the quote does, so"""
        reader, sink, _ = _reader(
            [_ok_body()], tokens=[KisMockTimeoutError("token endpoint timed out")]
        )

        assert reader.read() is None
        row = sink.only()
        assert row["reason"] == "token_transport_error"
        assert "token endpoint" in row["detail"]


class TestCustodyFailuresFoldToBandNone:
    """2026-10-15 plan §1 B2 / §L L1 — the leak this PR closes."""

    def test_an_unprovisioned_custody_scope_is_a_named_refusal(self) -> None:
        reader, sink, _ = _reader(
            [_ok_body()],
            credentials_error=CustodyScopeNotProvisioned("kis_mock.app_key"),
        )

        assert reader.read() is None
        row = sink.only()
        assert row["reason"] == "custody_error"
        assert "kis_mock.app_key" in row["detail"]

    def test_a_custody_failure_on_the_TOKEN_step_is_also_folded(self) -> None:
        """``KisTokenLifecycle._issue_token`` loads the SAME two scopes, so the leak has a"""
        reader, sink, _ = _reader(
            [_ok_body()], tokens=[CustodyError("manifest unreadable")]
        )

        assert reader.read() is None
        row = sink.only()
        assert row["reason"] == "token_custody_error"
        assert "manifest unreadable" in row["detail"]


class TestSourceContinuity:
    """ADR-002-019 §9 / plan §4.2 — new per boot, and NEW on a token reissue."""

    def test_two_readers_never_share_a_continuity_id(self) -> None:
        first, _, _ = _reader([_ok_body()])
        second, _, _ = _reader([_ok_body()])

        one, two = first.read(), second.read()

        assert one is not None and two is not None
        assert one.source_continuity_id != two.source_continuity_id

    def test_the_same_token_keeps_the_continuity_id(self) -> None:
        reader, _, _ = _reader([_ok_body(), _ok_body()], tokens=["token-a"])

        one, two = reader.read(), reader.read()

        assert one is not None and two is not None
        assert one.source_continuity_id == two.source_continuity_id

    def test_a_reissued_token_advances_the_continuity_id(self) -> None:
        reader, _, _ = _reader([_ok_body(), _ok_body()], tokens=["token-a", "token-b"])

        one, two = reader.read(), reader.read()

        assert one is not None and two is not None
        assert one.source_continuity_id != two.source_continuity_id


class TestSymmetricAboutBasis:
    """Plan §4.5 / module docstring — the field records SYMMETRY and claims nothing about"""

    def test_the_measured_band_is_symmetric_about_its_basis(self) -> None:
        reader, sink, _ = _reader([_ok_body()])

        observation = reader.read()

        assert observation is not None and observation.symmetric_about_basis is True
        assert sink.only()["symmetric_about_basis"] is True

    def test_an_asymmetric_band_is_still_used_but_recorded_false(self) -> None:
        reader, sink, _ = _reader([_ok_body(upper="1200.00")])

        observation = reader.read()

        assert observation is not None
        assert observation.symmetric_about_basis is False
        assert sink.only()["symmetric_about_basis"] is False

    def test_an_unusable_basis_leaves_the_field_unknown_without_dropping_the_band(
        self,
    ) -> None:
        reader, _, _ = _reader([_ok_body(basis=None)])

        observation = reader.read()

        assert observation is not None
        assert observation.basis is None
        assert observation.symmetric_about_basis is None


class TestNarrowedIntraday:
    """Plan §4.5 / §8 8 — the counter-observation to §2's monotonicity argument gets a row."""

    def test_a_same_day_narrowing_is_flagged(self) -> None:
        sink = _Sink()
        reader, _, _ = _reader(
            [_ok_body(), _ok_body(upper="1100.00", lower="1000.00")], sink=sink
        )

        reader.read()
        reader.read()

        assert [row[1]["narrowed_intraday"] for row in sink.rows] == [False, True]

    def test_a_same_day_widening_is_not_flagged(self) -> None:
        sink = _Sink()
        reader, _, _ = _reader(
            [_ok_body(), _ok_body(upper="1200.00", lower="900.00")], sink=sink
        )

        reader.read()
        reader.read()

        assert [row[1]["narrowed_intraday"] for row in sink.rows] == [False, False]

    def test_a_narrowing_across_trading_dates_is_not_flagged(self) -> None:
        """The flag is about §2's SAME-DAY monotonicity claim. Across a date the reference"""
        sink = _Sink()
        reader, _, _ = _reader(
            [_ok_body(), _ok_body(upper="1100.00", lower="1000.00")],
            trading_date=[_TRADING_DATE, "20261012"],
            sink=sink,
        )

        reader.read()
        reader.read()

        assert [row[1]["narrowed_intraday"] for row in sink.rows] == [False, False]
