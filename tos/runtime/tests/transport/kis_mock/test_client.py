"""``KisMockHttpClient`` tests against a hermetic ``127.0.0.1`` fake KIS server."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest
from tos_runtime.transport.kis_mock.client import (
    KisMockClientError,
    KisMockConnectionError,
    KisMockHttpClient,
    KisMockTimeoutError,
    build_client,
)
from tos_runtime.transport.kis_mock.config import KisMockTransportConfig

from ._fake_kis_server import FakeKisServer


@pytest.fixture
def server() -> Iterator[FakeKisServer]:
    srv = FakeKisServer()
    srv.start()
    try:
        yield srv
    finally:
        srv.stop()


def _client(server: FakeKisServer, *, timeout_s: float = 2.0) -> KisMockHttpClient:
    return KisMockHttpClient(
        rest_base=server.rest_base,
        request_timeout_s=timeout_s,
        allow_plaintext_for_tests=True,
    )


def _config(**overrides: object) -> KisMockTransportConfig:
    base: dict[str, object] = {
        "mode": "dry_run",
        "endpoint_rest_base": "https://openapivts.koreainvestment.com:29443",
        "order_path": "/uapi/domestic-stock/v1/trading/order-cash",
        "token_path": "/oauth2/tokenP",
        "tr_id_buy": "VTTC0012U",
        "tr_id_sell": "VTTC0011U",
        "field_map": {
            "account": "CANO",
            "instrument": "PDNO",
            "quantity": "ORD_QTY",
            "price": "ORD_UNPR",
        },
        "static_body_fields": {
            "ACNT_PRDT_CD": "01",
            "ORD_DVSN": "00",
            "EXCG_ID_DVSN_CD": "KRX",
            "SLL_TYPE": "",
            "CNDT_PRIC": "",
        },
        "min_send_interval_ms": 1100,
        "token_reissue_min_interval_s": 60,
        "request_timeout_s": 3.0,
        "allow_plaintext_for_tests": False,
    }
    base.update(overrides)
    return KisMockTransportConfig(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# build_client — the one sanctioned way to construct a client for real use (review F3):
# always from a validated KisMockTransportConfig, never a caller-supplied URL.
# ---------------------------------------------------------------------------


def test_build_client_uses_the_configs_own_endpoint_and_timeout_and_plaintext_flag(
    server: FakeKisServer,
) -> None:
    config = _config(
        endpoint_rest_base=server.rest_base,
        allow_plaintext_for_tests=True,
        request_timeout_s=1.5,
    )
    client = build_client(config)
    assert isinstance(client, KisMockHttpClient)
    server.set_response(
        "/oauth2/tokenP", status=200, body={"access_token": "t", "expires_in": 1}
    )
    client.issue_token(b"k", b"s", path="/oauth2/tokenP")
    assert len(server.requests_for("/oauth2/tokenP")) == 1


def test_build_client_rejects_http_when_the_config_forbids_it() -> None:
    config = _config(
        endpoint_rest_base="http://127.0.0.1:1", allow_plaintext_for_tests=False
    )
    with pytest.raises(KisMockClientError, match="allow_plaintext_for_tests"):
        build_client(config)


# ---------------------------------------------------------------------------
# scheme guard
# ---------------------------------------------------------------------------


def test_https_scheme_is_accepted_without_the_test_flag() -> None:
    KisMockHttpClient(
        rest_base="https://example.invalid",
        request_timeout_s=1.0,
        allow_plaintext_for_tests=False,
    )


def test_http_scheme_without_the_test_flag_refuses() -> None:
    with pytest.raises(KisMockClientError, match="allow_plaintext_for_tests"):
        KisMockHttpClient(
            rest_base="http://127.0.0.1:1",
            request_timeout_s=1.0,
            allow_plaintext_for_tests=False,
        )


def test_unsupported_scheme_refuses() -> None:
    with pytest.raises(KisMockClientError, match="unsupported scheme"):
        KisMockHttpClient(
            rest_base="ftp://127.0.0.1:1",
            request_timeout_s=1.0,
            allow_plaintext_for_tests=True,
        )


# ---------------------------------------------------------------------------
# issue_token
# ---------------------------------------------------------------------------


def test_issue_token_performs_exactly_one_request(server: FakeKisServer) -> None:
    server.set_response(
        "/oauth2/tokenP",
        status=200,
        body={"access_token": "tok-1", "expires_in": 86400},
    )
    client = _client(server)
    body = client.issue_token(b"appkey-1", b"appsecret-1", path="/oauth2/tokenP")
    assert body == {"access_token": "tok-1", "expires_in": 86400}
    assert len(server.requests_for("/oauth2/tokenP")) == 1


def test_issue_token_sends_grant_type_and_credentials_in_the_body(
    server: FakeKisServer,
) -> None:
    import json

    server.set_response(
        "/oauth2/tokenP",
        status=200,
        body={"access_token": "tok-1", "expires_in": 86400},
    )
    client = _client(server)
    client.issue_token(b"my-app-key", b"my-app-secret", path="/oauth2/tokenP")
    (request,) = server.requests_for("/oauth2/tokenP")
    sent = json.loads(request.body)
    assert sent == {
        "grant_type": "client_credentials",
        "appkey": "my-app-key",
        "appsecret": "my-app-secret",
    }


def test_issue_token_with_a_non_json_body_raises_client_error(
    server: FakeKisServer,
) -> None:
    server.set_response("/oauth2/tokenP", status=200, body=None)
    client = _client(server)
    with pytest.raises(KisMockClientError, match="did not parse"):
        client.issue_token(b"k", b"s", path="/oauth2/tokenP")


# ---------------------------------------------------------------------------
# post_order
# ---------------------------------------------------------------------------


def test_post_order_performs_exactly_one_request(server: FakeKisServer) -> None:
    order_path = "/uapi/domestic-stock/v1/trading/order-cash"
    server.set_response(
        order_path,
        status=200,
        body={
            "rt_cd": "0",
            "msg_cd": "APBK0013",
            "msg1": "ok",
            "output": {"ODNO": "123"},
        },
    )
    client = _client(server)
    response = client.post_order(
        "VTTC0012U",
        b'{"CANO":"1"}',
        access_token="tok-1",
        app_key=b"appkey-1",
        app_secret=b"appsecret-1",
        path=order_path,
    )
    assert response.status == 200
    assert response.json is not None
    assert response.json["rt_cd"] == "0"
    assert len(server.requests_for(order_path)) == 1


def test_post_order_sends_the_expected_headers(server: FakeKisServer) -> None:
    order_path = "/uapi/domestic-stock/v1/trading/order-cash"
    server.set_response(
        order_path, status=200, body={"rt_cd": "0", "output": {"ODNO": "1"}}
    )
    client = _client(server)
    client.post_order(
        "VTTC0012U",
        b'{"CANO":"1"}',
        access_token="tok-1",
        app_key=b"appkey-1",
        app_secret=b"appsecret-1",
        path=order_path,
    )
    (request,) = server.requests_for(order_path)
    assert request.headers["tr_id"] == "VTTC0012U"
    assert request.headers["authorization"] == "Bearer tok-1"
    assert request.headers["appkey"] == "appkey-1"
    assert request.headers["appsecret"] == "appsecret-1"
    assert request.headers["custtype"] == "P"


def test_post_order_never_puts_the_app_secret_bytes_in_the_body(
    server: FakeKisServer,
) -> None:
    order_path = "/uapi/domestic-stock/v1/trading/order-cash"
    server.set_response(
        order_path, status=200, body={"rt_cd": "0", "output": {"ODNO": "1"}}
    )
    client = _client(server)
    body = b'{"CANO":"1"}'
    client.post_order(
        "VTTC0012U",
        body,
        access_token="tok-1",
        app_key=b"appkey-1",
        app_secret=b"super-secret-value",
        path=order_path,
    )
    (request,) = server.requests_for(order_path)
    assert b"super-secret-value" not in request.body


def test_post_order_returns_a_5xx_response_without_raising(
    server: FakeKisServer,
) -> None:
    order_path = "/uapi/domestic-stock/v1/trading/order-cash"
    server.set_response(order_path, status=503, body={"msg1": "internal error"})
    client = _client(server)
    response = client.post_order(
        "VTTC0012U",
        b"{}",
        access_token="tok-1",
        app_key=b"k",
        app_secret=b"s",
        path=order_path,
    )
    assert response.status == 503


def test_post_order_with_a_malformed_body_returns_json_none(
    server: FakeKisServer,
) -> None:
    order_path = "/uapi/domestic-stock/v1/trading/order-cash"
    server.set_response(order_path, status=200, body=None)
    client = _client(server)
    response = client.post_order(
        "VTTC0012U",
        b"{}",
        access_token="t",
        app_key=b"k",
        app_secret=b"s",
        path=order_path,
    )
    assert response.json is None


# ---------------------------------------------------------------------------
# fault mapping
# ---------------------------------------------------------------------------


def test_a_socket_timeout_raises_the_typed_timeout_error(server: FakeKisServer) -> None:
    order_path = "/uapi/domestic-stock/v1/trading/order-cash"
    server.set_response(order_path, status=200, body={"rt_cd": "0"}, delay_s=0.5)
    client = _client(server, timeout_s=0.05)
    with pytest.raises(KisMockTimeoutError):
        client.post_order(
            "VTTC0012U",
            b"{}",
            access_token="t",
            app_key=b"k",
            app_secret=b"s",
            path=order_path,
        )


def test_a_connection_reset_raises_the_typed_connection_error(
    server: FakeKisServer,
) -> None:
    order_path = "/uapi/domestic-stock/v1/trading/order-cash"
    server.set_response(order_path, status=200, body=None, reset=True)
    client = _client(server, timeout_s=2.0)
    with pytest.raises(KisMockConnectionError):
        client.post_order(
            "VTTC0012U",
            b"{}",
            access_token="t",
            app_key=b"k",
            app_secret=b"s",
            path=order_path,
        )


def test_a_connection_to_a_closed_port_raises_the_typed_connection_error() -> None:
    # Bind, discover the free port, then close it before connecting — the port is very likely
    # still refused right after close (no other process has had time to bind it).
    import socket

    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    _, port = probe.getsockname()
    probe.close()

    client = KisMockHttpClient(
        rest_base=f"http://127.0.0.1:{port}",
        request_timeout_s=1.0,
        allow_plaintext_for_tests=True,
    )
    with pytest.raises(KisMockConnectionError):
        client.post_order(
            "VTTC0012U",
            b"{}",
            access_token="t",
            app_key=b"k",
            app_secret=b"s",
            path="/x",
        )


# ---------------------------------------------------------------------------
# negative-grep — no retry/loop primitive anywhere in this module
# ---------------------------------------------------------------------------


def _retry_primitive_offenders(source: str) -> list[str]:
    tree = ast.parse(source)
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else None
            if isinstance(func, ast.Attribute):
                name = func.attr
            if name == "sleep":
                offenders.append(f"line {node.lineno}: sleep() call")
        elif isinstance(node, ast.Name) and "retry" in node.id.lower():
            offenders.append(f"line {node.lineno}: retry-named identifier {node.id!r}")
        elif isinstance(node, ast.arg) and "retry" in node.arg.lower():
            offenders.append(f"line {node.lineno}: retry-named argument {node.arg!r}")
        elif isinstance(node, ast.While):
            offenders.append(f"line {node.lineno}: while loop")
        elif (
            isinstance(node, ast.For)
            and isinstance(node.iter, ast.Call)
            and isinstance(node.iter.func, ast.Name)
            and node.iter.func.id == "range"
        ):
            offenders.append(f"line {node.lineno}: 'for ... in range(...)' loop")
    return offenders


def test_the_client_source_has_no_retry_or_loop_primitive() -> None:
    import tos_runtime.transport.kis_mock.client as client_module

    source = Path(client_module.__file__).read_text(encoding="utf-8")
    offenders = _retry_primitive_offenders(source)
    assert offenders == [], f"retry/resend primitives found in client.py: {offenders}"


def _code_only(source: str) -> str:
    """Strip every string literal (docstrings included) from ``source`` via the AST — a
    negative-grep must catch a real usage, not a docstring that merely *names* the forbidden
    thing (this module's own module docstring says "no ``os.environ``")."""
    tree = ast.parse(source)
    spans: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.end_lineno is None or node.lineno != node.end_lineno:
                continue  # multi-line string — handled by line-range blanking below
            spans.append((node.lineno, node.lineno))
    lines = source.splitlines(keepends=True)
    # Blank out every line that is entirely inside a string constant's own span, plus any
    # docstring (Expr-statement string) regardless of span, to keep this simple and conservative.
    for node in ast.walk(tree):
        if (
            isinstance(
                node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            )
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            doc_node = node.body[0]
            start = doc_node.lineno - 1
            end = (doc_node.end_lineno or doc_node.lineno) - 1
            for i in range(start, end + 1):
                lines[i] = "\n"
    return "".join(lines)


def test_the_client_source_imports_no_forbidden_names() -> None:
    import tos_runtime.transport.kis_mock.client as client_module

    source = Path(client_module.__file__).read_text(encoding="utf-8")
    code_only = _code_only(source)
    for forbidden in (
        "import requests",
        "import httpx",
        "os.environ",
        "os.getenv",
        "openapi.koreainvestment.com",
        "localhost",
    ):
        assert (
            forbidden not in code_only
        ), f"forbidden token {forbidden!r} found in client.py"
