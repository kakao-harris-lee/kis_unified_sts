"""``GET /api/tos/symbols/today`` — the read-only per-symbol operator rows."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.dashboard.routes import tos_symbols

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ROUTE_MODULE = _REPO_ROOT / "services" / "dashboard" / "routes" / "tos_symbols.py"
_REASONS_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "tos" / "symbols-reasons.json"

#: The shape ``tools/tos_cp3/export_symbols.py`` writes, as measured on the host
#: on 2026-11-22 against the 2026-11-20 sessions (the round trips recorded in the
#: usage plan §1). `test_cp3_export_symbols.py` builds the same shape from a
#: fixture leaf, so the two sides cannot drift without one of them going red.
_VALID_DOCUMENT: dict[str, Any] = {
    "schema_version": 1,
    "date": "2026-11-20",
    "generated_kst": "2026-11-20T15:41:02+09:00",
    "holding_basis": "TOS_LEDGER_FIFO_OPEN_LOTS",
    "symbols": [
        {
            "symbol": "005930",
            "tree_id": "cp3-setup-d-stock-005930",
            "session": {
                "name": "stock-r5-20261120",
                "status": "ENDED",
                "boot_at": "14:34:32",
                "end_at": "15:40:01",
                "run_rc": 0,
            },
            "buy": {
                "fills": 1,
                "quantity": "1",
                "last": {
                    "quantity": "1",
                    "order_price_krw": "181900",
                    "execution_price_krw": "181700",
                    "price_basis": "EXECUTION",
                    "broker_execution_id": "0000027053",
                    "time_kst": "14:36",
                    "time_basis": "ORDER_BAR",
                },
            },
            "sell": {
                "fills": 1,
                "quantity": "1",
                "last": {
                    "quantity": "1",
                    "order_price_krw": "183100",
                    "execution_price_krw": "183100",
                    "price_basis": "EXECUTION",
                    "broker_execution_id": "0000029505",
                    "time_kst": "15:16",
                    "time_basis": "ORDER_BAR",
                },
            },
            "holding": {
                "quantity": "0",
                "lots": 0,
                "basis": "TOS_LEDGER_FIFO_OPEN_LOTS",
            },
            "halt": {
                "error": None,
                "last_flow": {
                    "reason": "STAGE_DENIED",
                    "step": "CANDIDATE_COMMAND_CONSTRUCTION",
                    "time_kst": "15:18",
                },
                "last_withheld": {
                    "reason": "TIME_NOT_ADMITTED",
                    "step": "DECISION_WITHHELD",
                    "time_kst": "14:33",
                },
                "flow_counts": {"STAGE_DENIED": 3, "STAGE_UNKNOWN": 9},
            },
            "ticks": 46,
            "error": None,
        },
        {
            "symbol": "000660",
            "tree_id": "cp3-setup-d-stock-000660",
            "session": {
                "name": None,
                "status": None,
                "boot_at": None,
                "end_at": None,
                "run_rc": None,
            },
            "buy": {"fills": 0, "quantity": "0", "last": None},
            "sell": {"fills": 0, "quantity": "0", "last": None},
            "holding": {
                "quantity": "0",
                "lots": 0,
                "basis": "TOS_LEDGER_FIFO_OPEN_LOTS",
            },
            "halt": {
                "error": None,
                "last_flow": None,
                "last_withheld": None,
                "flow_counts": {},
            },
            "ticks": 0,
            "error": None,
        },
        {
            "symbol": "005380",
            "tree_id": "cp3-setup-d-stock-005380",
            "session": {
                "name": "stock-005380-r5-20261120",
                "status": "RUNNING",
                "boot_at": "14:33:29",
                "end_at": None,
                "run_rc": None,
            },
            "buy": {"fills": 0, "quantity": "0", "last": None},
            "sell": {"fills": 0, "quantity": "0", "last": None},
            "holding": {"quantity": None, "lots": None, "basis": None},
            "halt": {
                "error": "OperationalError",
                "last_flow": None,
                "last_withheld": None,
                "flow_counts": {},
            },
            "ticks": None,
            "error": "OperationalError",
        },
    ],
}


@pytest.fixture
def document(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The container-side document path, derived from the projection env var."""
    projection = tmp_path / "mount" / "operator_projection.json"
    projection.parent.mkdir(parents=True)
    monkeypatch.setenv("TOS_OPERATOR_PROJECTION_PATH", str(projection))
    directory = projection.parent / "symbols"
    directory.mkdir()
    return directory / "today.json"


def _write(path: Path, payload: object) -> Path:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def client() -> TestClient:
    """A client over just this router, so the test does not depend on auth wiring."""
    app = FastAPI()
    app.include_router(tos_symbols.router)
    return TestClient(app)


def _get(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/tos/symbols/today")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    return response.json()


def test_a_valid_document_is_served_with_every_row(
    client: TestClient, document: Path
) -> None:
    """All three symbols reach the body — the plan's acceptance, at the wire."""
    _write(document, _VALID_DOCUMENT)
    body = _get(client)
    assert body["available"] is True
    assert body["reason"] is None
    served = body["document"]
    assert [row["symbol"] for row in served["symbols"]] == [
        "005930",
        "000660",
        "005380",
    ]
    assert served["date"] == "2026-11-20"
    assert served["holding_basis"] == "TOS_LEDGER_FIFO_OPEN_LOTS"
    assert body["age_seconds"] is not None and body["age_seconds"] >= 0


def test_a_traded_row_keeps_its_fills_prices_and_last_halt(
    client: TestClient, document: Path
) -> None:
    """The numbers an operator reads off the row survive the DTO verbatim."""
    _write(document, _VALID_DOCUMENT)
    row = _get(client)["document"]["symbols"][0]
    assert row["buy"]["fills"] == 1
    assert row["buy"]["last"]["execution_price_krw"] == "181700"
    assert row["buy"]["last"]["price_basis"] == "EXECUTION"
    assert row["buy"]["last"]["time_kst"] == "14:36"
    assert row["buy"]["last"]["time_basis"] == "ORDER_BAR"
    assert row["sell"]["last"]["broker_execution_id"] == "0000029505"
    assert row["holding"] == {
        "quantity": "0",
        "lots": 0,
        "basis": "TOS_LEDGER_FIFO_OPEN_LOTS",
    }
    assert row["halt"]["last_flow"]["reason"] == "STAGE_DENIED"
    assert row["halt"]["last_flow"]["time_kst"] == "15:18"
    assert row["halt"]["flow_counts"] == {"STAGE_DENIED": 3, "STAGE_UNKNOWN": 9}
    assert row["session"]["status"] == "ENDED"
    assert row["ticks"] == 46


def test_a_symbol_with_no_session_today_still_has_a_row(
    client: TestClient, document: Path
) -> None:
    """ "Not started today" is a null status, never a missing symbol.

    The acceptance is "all three symbols are visible on one screen", so a tenant
    that did not run must still be a row — dropping it would turn a quiet
    failure into an invisible one.
    """
    _write(document, _VALID_DOCUMENT)
    row = _get(client)["document"]["symbols"][1]
    assert row["symbol"] == "000660"
    assert row["session"]["status"] is None
    assert row["buy"]["fills"] == 0
    assert row["sell"]["last"] is None
    assert row["error"] is None


def test_a_row_whose_leaf_could_not_be_read_keeps_its_reduced_error(
    client: TestClient, document: Path
) -> None:
    """The exporter reduces the cause to a type name; the DTO carries it as such."""
    _write(document, _VALID_DOCUMENT)
    row = _get(client)["document"]["symbols"][2]
    assert row["error"] == "OperationalError"
    assert row["halt"]["error"] == "OperationalError"
    assert row["holding"]["quantity"] is None
    assert row["ticks"] is None


def test_no_host_path_reaches_the_body(client: TestClient, document: Path) -> None:
    """The exporter emits none, and nothing here adds one back."""
    _write(document, _VALID_DOCUMENT)
    assert "/home/deploy" not in json.dumps(_get(client))
    assert str(document) not in json.dumps(_get(client))


def test_a_missing_document_is_absent(client: TestClient, document: Path) -> None:
    """Before the first export there is no document, and that is a 200."""
    body = _get(client)
    assert (body["available"], body["document"]) == (False, None)
    assert body["reason"].startswith("symbols document absent")


def test_an_unreadable_document_names_permissions_not_the_data(
    client: TestClient, document: Path
) -> None:
    """A directory where a file belongs is the mount/uid hazard, not bad JSON."""
    document.mkdir()
    body = _get(client)
    assert body["available"] is False
    assert body["reason"].startswith("cannot read symbols document")


def test_invalid_json_is_reported_by_type(client: TestClient, document: Path) -> None:
    """The exception type, never the offending bytes."""
    _write(document, "{not json")
    body = _get(client)
    assert body["available"] is False
    assert body["reason"].startswith("invalid json")
    assert "not json" not in body["reason"]


def test_a_non_object_document_is_invalid_json(
    client: TestClient, document: Path
) -> None:
    """A JSON array parses but is not a document."""
    _write(document, [1, 2, 3])
    body = _get(client)
    assert body["available"] is False
    assert body["reason"] == "invalid json: top-level value is not an object"


def test_a_foreign_schema_version_is_unsupported(
    client: TestClient, document: Path
) -> None:
    """A version this reader does not understand is refused by type, not value."""
    _write(document, {**_VALID_DOCUMENT, "schema_version": 2})
    body = _get(client)
    assert body["available"] is False
    assert body["reason"].startswith("unsupported schema_version")
    assert "2" not in body["reason"].split("got")[1]


def test_a_boolean_schema_version_does_not_pass_as_one(
    client: TestClient, document: Path
) -> None:
    """``True == 1``, so ``isinstance`` would have admitted a JSON ``true``."""
    _write(document, {**_VALID_DOCUMENT, "schema_version": True})
    body = _get(client)
    assert body["available"] is False
    assert body["reason"].startswith("unsupported schema_version")
    assert "bool" in body["reason"]


def test_a_schema_mismatch_reports_only_the_exception_type(
    client: TestClient, document: Path
) -> None:
    """Pydantic's own message embeds the offending slice; this one must not."""
    _write(document, {**_VALID_DOCUMENT, "symbols": {"not": "a list"}})
    body = _get(client)
    assert body["available"] is False
    assert body["reason"].startswith("schema mismatch")
    assert "not" not in body["reason"]
    assert "a list" not in body["reason"]


def test_an_unknown_extra_key_is_ignored_not_rejected(
    client: TestClient, document: Path
) -> None:
    """An exporter-side field addition must not blank the page."""
    payload = {
        **_VALID_DOCUMENT,
        "a_future_key": {"x": 1},
        "symbols": [{**_VALID_DOCUMENT["symbols"][0], "a_future_row_key": 7}],
    }
    _write(document, payload)
    body = _get(client)
    assert body["available"] is True
    assert "a_future_key" not in body["document"]
    assert "a_future_row_key" not in body["document"]["symbols"][0]
    assert body["document"]["symbols"][0]["symbol"] == "005930"


def test_every_emitted_reason_prefix_is_in_the_shared_fixture() -> None:
    """The UI matcher asserts the same file, so an unlisted prefix fails there too."""
    listed = {
        entry["prefix"]
        for entry in json.loads(_REASONS_FIXTURE.read_text(encoding="utf-8"))["reasons"]
    }
    source = _ROUTE_MODULE.read_text(encoding="utf-8")
    emitted = {
        '"symbols document absent"',
        'f"cannot read symbols document',
        'f"invalid json',
        '"invalid json: top-level value is not an object"',
        'f"unsupported schema_version',
        'f"schema mismatch',
    }
    for literal in emitted:
        assert literal in source, f"reason literal vanished from the route: {literal}"
    assert listed == {
        "symbols document absent",
        "cannot read symbols document",
        "invalid json",
        "schema mismatch",
        "unsupported schema_version",
    }


def test_the_route_imports_nothing_from_tos() -> None:
    """The reverse firewall, restated where a reader of this suite sees it."""
    for line in _ROUTE_MODULE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        assert not stripped.startswith(("import tos", "from tos ")), line
        assert not stripped.startswith(("import tos_runtime", "from tos_runtime")), line
        assert not stripped.startswith("from tos."), line


def test_the_web_tier_never_reaches_a_broker() -> None:
    """No KIS call from the web tier — the holding is TOS's ledger, not a balance.

    Stated as a test rather than only as prose because the tempting next edit is
    "the page should show the real position too", which would put a broker read
    behind a browser poll.
    """
    source = _ROUTE_MODULE.read_text(encoding="utf-8").lower()
    for forbidden in ("shared.kis", "import requests", "import httpx", "aiohttp"):
        assert forbidden not in source, forbidden


def test_an_absent_document_logs_at_info_and_a_fault_at_warning(
    client: TestClient, document: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """No export yet is normal; an unreadable document is not."""
    with caplog.at_level(logging.INFO, logger=tos_symbols.logger.name):
        _get(client)
    assert [record.levelno for record in caplog.records] == [logging.INFO]

    caplog.clear()
    _write(document, "{not json")
    with caplog.at_level(logging.INFO, logger=tos_symbols.logger.name):
        _get(client)
    assert [record.levelno for record in caplog.records] == [logging.WARNING]


def test_the_route_is_registered_on_the_app() -> None:
    """A router nobody includes is a read model nobody can read."""
    from services.dashboard.app import create_app

    paths = {route.path for route in create_app().routes}  # type: ignore[attr-defined]
    assert "/api/tos/symbols/today" in paths
    assert "/api/tos/sessions/{session_id}/bars" in paths
    assert "/api/tos/projection" in paths


def test_the_document_lives_beside_the_bars_export(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Both readers derive from one env var, so they cannot land on two mounts."""
    from services.dashboard.routes import tos_bars

    projection = tmp_path / "mount" / "operator_projection.json"
    monkeypatch.setenv("TOS_OPERATOR_PROJECTION_PATH", str(projection))
    assert tos_symbols._document_path().parent.parent == tos_bars._bars_dir().parent
    assert tos_symbols._document_path() == projection.parent / "symbols" / "today.json"
