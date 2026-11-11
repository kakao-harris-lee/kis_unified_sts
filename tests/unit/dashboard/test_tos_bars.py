"""``GET /api/tos/sessions/{id}/bars`` — the read-only per-bar read model.

Roadmap ``docs/plans/2026-11-11-tos-platform-roadmap.md`` §P1, second item.
Mirrors the discipline ``test_tos_projection.py`` already holds its sibling to:

* every failure is ``200`` + ``available=false`` + a ``reason``, never a 5xx;
* every ``reason`` prefix is pinned by the shared fixture the UI matcher also
  asserts (``tests/fixtures/tos/bars-reasons.json``);
* no ``reason`` and no response field carries a value read from the document —
  and, specific to this route, no response field carries a HOST PATH;
* the route imports no ``tos``/``tos_runtime`` (it cannot: the container holds
  neither the kernel code nor the state directories).

The one path segment a caller controls is the session id, so its validation is
tested as its own class of input rather than assumed.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.dashboard.routes import tos_bars

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ROUTE_MODULE = _REPO_ROOT / "services" / "dashboard" / "routes" / "tos_bars.py"
_REASONS_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "tos" / "bars-reasons.json"

SESSION = "stock-r1-20261110"

#: One valid document, in the exporter's own shape but two bars long. The field
#: set mirrors ``tools/tos_cp3/export_bars.py``'s output: the inspection's
#: ``--json`` document plus ``schema_version``, host paths included — so the
#: test proves the ROUTE drops them rather than relying on the exporter never
#: writing them.
_VALID_DOCUMENT: dict[str, Any] = {
    "schema_version": 1,
    "session": SESSION,
    "instrument": "005930",
    "data_dir": "/home/deploy/.local/state/tos/cp3-setup-d-stock-005930-data/005930",
    "strategy": {
        "path": "/home/deploy/.local/state/tos/cp3-sessions/x/render/strategies/a.yaml",
        "sha256": "df164ee2461aa133ac6506889cd53c3618134a42403e2c302128cb3c54fd3b00",
    },
    "bindings": {
        "path": "/home/deploy/.local/state/tos/cp3-sessions/x/render/bindings.yaml",
        "values": {"z_entry_max_x1000": -1800},
    },
    "window": {"from": "09:00", "to": "14:51"},
    "default": {"rule_id": "R0-DEFAULT-NO-ACTION", "decision_kind": "NO_ACTION"},
    "bars": [
        {
            "raw_event_id": "005930:1m:20261110T090000+0900",
            "as_of_ms": 1794268862186,
            "time_kst": "09:00",
            "time_source": "raw_event_id",
            "fields": {"close_x100": 19940000, "hi_vol": False},
            "env_values": {},
            "evaluation": "withheld",
            "counted": False,
            "flags": "--W-",
            "view_diff": {},
            "engine_shape": None,
            "decision_disagrees": False,
            "decision_rule_id": None,
            "decision_kind": None,
            "rules": [],
            "evidence": {
                "joined": True,
                "unjoined_reason": None,
                "event_id": "event-0c1d",
                "snapshot_id": "cis-cea0",
                "outcome_type": None,
                "withheld_reason": "TIME_NOT_ADMITTED",
                "halt_step": None,
                "halt_reason": None,
                "halt_detail": None,
                "value_view": {},
                "value_view_refusal": None,
            },
        },
        {
            "raw_event_id": "005930:1m:20261110T090100+0900",
            "as_of_ms": 1794268922132,
            "time_kst": "09:01",
            "time_source": "raw_event_id",
            "fields": {"close_x100": 19910000, "hi_vol": False},
            "env_values": {"close_x100": 19910000, "hi_vol": True},
            "evaluation": "engine_view",
            "counted": True,
            "flags": "V---",
            "view_diff": {"hi_vol": {"value_view": "true", "journal": "false"}},
            "engine_shape": "no_action",
            "decision_disagrees": False,
            "decision_rule_id": "R0-DEFAULT-NO-ACTION",
            "decision_kind": "NO_ACTION",
            "rules": [
                {
                    "label": "R1",
                    "rule_id": "R1-ENTRY-LONG",
                    "decision_kind": "ACTION",
                    "fired": False,
                    "compares": [
                        {
                            "index": 1,
                            "expression": "entry_window EQ true",
                            "left_value": "false",
                            "right_value": "true",
                            "passed": False,
                        }
                    ],
                }
            ],
            "evidence": {
                "joined": True,
                "event_id": "event-5c21",
                "snapshot_id": "cis-67d6",
                "outcome_type": "NoActionOutcome",
                "value_view": {"close_x100": 19910000, "hi_vol": True},
            },
        },
    ],
    "summary": {
        "bars": 2,
        "counted_bars": 1,
        "withheld_bars": 1,
        "substituted_bars": 0,
        "view_diff_bars": 1,
        "view_diff_fields": {"hi_vol": 1},
        "disagreement_bars": 0,
        "not_comparable_bars": 0,
        "rules": [
            {
                "label": "R1",
                "rule_id": "R1-ENTRY-LONG",
                "fired_bars": 0,
                "bars": 1,
                "fired_pct": 0.0,
                "compares": [
                    {
                        "index": 1,
                        "expression": "entry_window EQ true",
                        "failed_bars": 1,
                        "bars": 1,
                        "failed_pct": 100.0,
                    }
                ],
            }
        ],
        "decisions": {"R0-DEFAULT-NO-ACTION": 1},
        "evidence_outcomes": {"NoActionOutcome": 1, "TIME_NOT_ADMITTED": 1},
        "evidence_halts": {},
        "unjoined": {},
        "value_view_refused": {},
    },
}


@pytest.fixture
def bars_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the route at a ``bars/`` directory under ``tmp_path``."""
    projection = tmp_path / "tos_runtime" / "operator_projection.json"
    projection.parent.mkdir(parents=True)
    monkeypatch.setenv("TOS_OPERATOR_PROJECTION_PATH", str(projection))
    directory = projection.parent / "bars"
    directory.mkdir()
    return directory


def _write(bars_dir: Path, session: str, payload: object) -> Path:
    path = bars_dir / f"{session}.json"
    text = payload if isinstance(payload, str) else json.dumps(payload)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def client() -> TestClient:
    """A client over just this router, so the test does not depend on auth wiring."""
    app = FastAPI()
    app.include_router(tos_bars.router)
    return TestClient(app)


def _get(client: TestClient, session: str = SESSION) -> dict[str, Any]:
    response = client.get(f"/api/tos/sessions/{session}/bars")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    return response.json()


# ===========================================================================
# The happy path
# ===========================================================================


def test_a_valid_document_is_served_with_its_summary(
    client: TestClient, bars_dir: Path
) -> None:
    """The document is mirrored, including every per-comparison number."""
    _write(bars_dir, SESSION, _VALID_DOCUMENT)
    body = _get(client)
    assert body["available"] is True
    assert body["reason"] is None
    assert body["session"] == SESSION
    document = body["document"]
    assert document["instrument"] == "005930"
    assert len(document["bars"]) == 2
    assert document["bars"][0]["flags"] == "--W-"
    assert document["bars"][1]["view_diff"] == {
        "hi_vol": {"value_view": "true", "journal": "false"}
    }
    assert document["summary"]["counted_bars"] == 1
    assert document["summary"]["rules"][0]["compares"][0]["failed_pct"] == 100.0
    assert document["window"] == {"from": "09:00", "to": "14:51"}
    assert body["age_seconds"] is not None and body["age_seconds"] >= 0


def test_no_host_path_reaches_the_body(client: TestClient, bars_dir: Path) -> None:
    """``data_dir`` and both ``path`` keys are dropped, not merely unrendered.

    The document on disk carries them (an operator artifact), but this body
    reaches a browser holding the dashboard API key in its bundle, so the
    deployment's filesystem layout must not travel with it.
    """
    _write(bars_dir, SESSION, _VALID_DOCUMENT)
    body = _get(client)
    document = body["document"]
    assert "data_dir" not in document
    assert "path" not in document["strategy"]
    assert "path" not in document["bindings"]
    # The parts that ARE the point survive.
    assert document["strategy"]["sha256"].startswith("df164ee2")
    assert document["bindings"]["values"] == {"z_entry_max_x1000": -1800}
    assert "/home/deploy" not in json.dumps(body)


def test_latest_resolves_to_the_most_recently_exported_document(
    client: TestClient, bars_dir: Path
) -> None:
    """``latest`` orders by export time, so the panel opens on today's session."""
    older = _write(bars_dir, "stock-r1-20261106", _VALID_DOCUMENT)
    newer = _write(bars_dir, SESSION, {**_VALID_DOCUMENT, "session": SESSION})
    os.utime(older, (1_000_000, 1_000_000))
    os.utime(newer, (2_000_000, 2_000_000))
    body = _get(client, tos_bars.LATEST)
    assert body["available"] is True
    assert body["session"] == SESSION


def test_latest_with_nothing_exported_is_absent_not_an_error(
    client: TestClient, bars_dir: Path
) -> None:
    """An empty directory is "no data yet", which is a 200."""
    body = _get(client, tos_bars.LATEST)
    assert (body["available"], body["document"]) == (False, None)
    assert body["reason"].startswith("bars document absent")


# ===========================================================================
# Every failure is a 200 with a pinned reason
# ===========================================================================


def test_a_missing_document_is_absent(client: TestClient, bars_dir: Path) -> None:
    """A session nobody exported yet."""
    body = _get(client)
    assert (body["available"], body["document"]) == (False, None)
    assert body["reason"].startswith("bars document absent")
    assert body["session"] == SESSION


def test_an_unreadable_document_names_permissions_not_the_data(
    client: TestClient, bars_dir: Path
) -> None:
    """A directory where a file belongs is the mount/uid hazard, not bad JSON."""
    (bars_dir / f"{SESSION}.json").mkdir()
    body = _get(client)
    assert body["available"] is False
    assert body["reason"].startswith("cannot read bars document")


def test_invalid_json_is_reported_by_type(client: TestClient, bars_dir: Path) -> None:
    """The exception type, never the offending bytes."""
    _write(bars_dir, SESSION, "{not json")
    body = _get(client)
    assert body["available"] is False
    assert body["reason"].startswith("invalid json")
    assert "not json" not in body["reason"]


def test_a_non_object_document_is_invalid_json(
    client: TestClient, bars_dir: Path
) -> None:
    """A top-level list is valid JSON and still not a document."""
    _write(bars_dir, SESSION, [1, 2, 3])
    body = _get(client)
    assert body["available"] is False
    assert body["reason"].startswith("invalid json")


@pytest.mark.parametrize(
    ("version", "type_name"),
    [(2, "int"), ("1", "str"), (None, "NoneType"), (True, "bool")],
)
def test_a_foreign_schema_version_is_unsupported(
    client: TestClient, bars_dir: Path, version: object, type_name: str
) -> None:
    """The reason names the TYPE, never the value read from the file.

    ``True`` is in here on purpose: ``True == 1``, so an ``isinstance`` gate
    would have let a JSON ``true`` render as a valid v1 document. ``"1"`` is the
    case that proves the value is not echoed — its type name carries no ``1``.
    """
    _write(bars_dir, SESSION, {**_VALID_DOCUMENT, "schema_version": version})
    body = _get(client)
    assert body["available"] is False
    assert body["reason"] == (
        f"unsupported schema_version (expected 1, got {type_name})"
    )


def test_a_schema_mismatch_reports_only_the_exception_type(
    client: TestClient, bars_dir: Path
) -> None:
    """Pydantic's own message embeds the offending input; this one does not."""
    _write(
        bars_dir,
        SESSION,
        {**_VALID_DOCUMENT, "bars": "a-secret-looking-string-not-a-list"},
    )
    body = _get(client)
    assert body["available"] is False
    assert body["reason"].startswith("schema mismatch")
    assert "a-secret-looking-string" not in body["reason"]


# ===========================================================================
# The caller-controlled path segment
# ===========================================================================


@pytest.mark.parametrize(
    "session_id",
    ["", "a" * 65, "has space", "..", ".", "dot.dot", "semi;colon", "-leading"],
)
def test_a_session_id_outside_the_pattern_is_refused(
    bars_dir: Path, session_id: str
) -> None:
    """Refused by a positive pattern, so traversal cannot match by construction.

    Called directly rather than through the client because Starlette resolves
    some of these in the URL path before a handler sees them — the point here
    is that THIS function refuses them whatever reaches it.
    """
    result = tos_bars._read_document(bars_dir, session_id)
    assert result.available is False
    assert result.reason is not None
    assert result.reason.startswith("invalid session id")
    # Never echo the rejected id: it is caller-supplied and ends up in a browser.
    assert session_id not in result.reason or session_id == ""


def test_a_rejected_id_cannot_reach_a_file_outside_the_bars_dir(
    tmp_path: Path, bars_dir: Path
) -> None:
    """The refusal happens before any path is joined."""
    outside = tmp_path / "secret.json"
    outside.write_text(json.dumps(_VALID_DOCUMENT), encoding="utf-8")
    result = tos_bars._read_document(bars_dir, "../secret")
    assert result.available is False
    assert result.reason is not None
    assert result.reason.startswith("invalid session id")


@pytest.mark.parametrize(
    "session_id", ["stock-r1-20261110", "long-20261015", "a", "A9_b-c"]
)
def test_the_pattern_admits_real_session_names(bars_dir: Path, session_id: str) -> None:
    """The names the runner actually writes must not be refused."""
    result = tos_bars._read_document(bars_dir, session_id)
    assert result.reason is not None
    assert result.reason.startswith("bars document absent")


# ===========================================================================
# Shared contracts
# ===========================================================================


def test_every_emitted_reason_prefix_is_in_the_shared_fixture() -> None:
    """The UI matcher asserts the same file, so an unlisted prefix fails there too."""
    listed = {
        entry["prefix"]
        for entry in json.loads(_REASONS_FIXTURE.read_text(encoding="utf-8"))["reasons"]
    }
    source = _ROUTE_MODULE.read_text(encoding="utf-8")
    emitted = {
        '"bars document absent"',
        'f"cannot read bars document',
        'f"invalid json',
        '"invalid json: top-level value is not an object"',
        'f"unsupported schema_version',
        'f"schema mismatch',
        'f"invalid session id',
    }
    for literal in emitted:
        assert literal in source, f"reason literal vanished from the route: {literal}"
    assert listed == {
        "bars document absent",
        "cannot read bars document",
        "invalid json",
        "schema mismatch",
        "unsupported schema_version",
        "invalid session id",
    }


def test_the_route_imports_nothing_from_tos() -> None:
    """The reverse firewall, restated where a reader of this suite sees it.

    This container holds neither ``tos/`` nor the state directories, so the
    boundary is a file; an ``import tos`` here would be both a firewall
    violation and an ImportError at runtime.
    """
    for line in _ROUTE_MODULE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        assert not stripped.startswith(("import tos", "from tos ")), line
        assert not stripped.startswith(("import tos_runtime", "from tos_runtime")), line
        assert not stripped.startswith("from tos."), line


def test_an_absent_document_logs_at_info_and_a_fault_at_warning(
    client: TestClient, bars_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A session nobody exported is normal; an unreadable one is not.

    The panel can be left open, so the normal state must not fill the
    container's stderr — the same split the projection reader makes.
    """
    with caplog.at_level(logging.INFO, logger=tos_bars.logger.name):
        _get(client)
    assert [record.levelno for record in caplog.records] == [logging.INFO]

    caplog.clear()
    _write(bars_dir, SESSION, "{not json")
    with caplog.at_level(logging.INFO, logger=tos_bars.logger.name):
        _get(client)
    assert [record.levelno for record in caplog.records] == [logging.WARNING]


def test_the_route_is_registered_on_the_app() -> None:
    """A router nobody includes is a read model nobody can read."""
    from services.dashboard.app import create_app

    paths = {route.path for route in create_app().routes}  # type: ignore[attr-defined]
    assert "/api/tos/sessions/{session_id}/bars" in paths
    assert "/api/tos/projection" in paths
