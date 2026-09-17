"""``KisWitnessHttpClient`` tests — GET-only, headers preserved (mirrors
``tos/runtime/tests/transport/kis_mock/test_client.py``'s own shape for the sibling
order-transport client)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from tos_runtime.recon.witness_kis_client import (
    KisWitnessClientError,
    KisWitnessHttpClient,
)

from ._fake_kis_get_server import FakeKisGetServer

_PATH = "/uapi/domestic-stock/v1/trading/inquire-balance"


@pytest.fixture
def server() -> Iterator[FakeKisGetServer]:
    srv = FakeKisGetServer()
    srv.start()
    try:
        yield srv
    finally:
        srv.stop()


def _client(server: FakeKisGetServer) -> KisWitnessHttpClient:
    return KisWitnessHttpClient(
        rest_base=server.rest_base,
        request_timeout_s=2.0,
        allow_plaintext_for_tests=True,
    )


def test_get_returns_status_json_and_headers(server: FakeKisGetServer) -> None:
    server.queue_response(
        _PATH,
        status=200,
        body={"rt_cd": "0", "output1": []},
        headers={"tr_cont": "D"},
    )
    client = _client(server)
    response = client.get(_PATH, headers={"tr_id": "VTTC8434R"}, params={"CANO": "1"})
    assert response.status == 200
    assert response.json == {"rt_cd": "0", "output1": []}
    assert response.headers.get("tr_cont") == "D"


def test_get_sends_query_params_and_headers(server: FakeKisGetServer) -> None:
    server.queue_response(_PATH, status=200, body={"rt_cd": "0"})
    client = _client(server)
    client.get(
        _PATH,
        headers={"tr_id": "VTTC8434R", "authorization": "Bearer tok"},
        params={"CANO": "12345678", "CTX_AREA_FK100": ""},
    )
    [request] = server.requests_for(_PATH)
    assert request.query["CANO"] == "12345678"
    assert request.headers["tr_id"] == "VTTC8434R"
    assert request.headers["authorization"] == "Bearer tok"


def test_http_scheme_requires_the_test_only_flag(server: FakeKisGetServer) -> None:
    with pytest.raises(KisWitnessClientError, match="allow_plaintext_for_tests"):
        KisWitnessHttpClient(
            rest_base=server.rest_base,
            request_timeout_s=2.0,
            allow_plaintext_for_tests=False,
        )


def test_unsupported_scheme_is_refused() -> None:
    with pytest.raises(KisWitnessClientError, match="unsupported scheme"):
        KisWitnessHttpClient(
            rest_base="ftp://example.com",
            request_timeout_s=2.0,
            allow_plaintext_for_tests=True,
        )


def test_malformed_json_body_is_reported_as_no_json(server: FakeKisGetServer) -> None:
    server.queue_response(_PATH, status=200, body=None)
    client = _client(server)
    response = client.get(_PATH, headers={}, params={})
    assert response.json is None
