"""``GET /api/tos/sessions/{id}/bars`` — the read-only per-bar read model."""

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
    """``data_dir`` and both ``path`` keys are dropped, not merely unrendered."""
    _write(bars_dir, SESSION, _VALID_DOCUMENT)
    body = _get(client)
    document = body["document"]
    assert "data_dir" not in document
    assert "path" not in document["strategy"]
    assert "path" not in document["bindings"]
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
    """The reason names the TYPE, never the value read from the file."""
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


@pytest.mark.parametrize(
    "session_id",
    ["", "a" * 65, "has space", "..", ".", "dot.dot", "semi;colon", "-leading"],
)
def test_a_session_id_outside_the_pattern_is_refused(
    bars_dir: Path, session_id: str
) -> None:
    """Refused by a positive pattern, so traversal cannot match by construction."""
    result = tos_bars._read_document(bars_dir, session_id)
    assert result.available is False
    assert result.reason is not None
    assert result.reason.startswith("invalid session id")
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
    """The reverse firewall, restated where a reader of this suite sees it."""
    for line in _ROUTE_MODULE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        assert not stripped.startswith(("import tos", "from tos ")), line
        assert not stripped.startswith(("import tos_runtime", "from tos_runtime")), line
        assert not stripped.startswith("from tos."), line


def test_an_absent_document_logs_at_info_and_a_fault_at_warning(
    client: TestClient, bars_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A session nobody exported is normal; an unreadable one is not."""
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


def test_the_served_session_is_the_resolved_id_not_the_documents_own(
    client: TestClient, bars_dir: Path
) -> None:
    """``session`` is the id THIS ROUTE resolved, never file content."""
    hostile = "<img src=x onerror=alert(1)>"
    _write(bars_dir, SESSION, {**_VALID_DOCUMENT, "session": hostile})
    body = _get(client)
    assert body["available"] is True
    assert body["session"] == SESSION
    assert body["document"]["session"] == hostile


def test_latest_survives_a_document_vanishing_mid_listing(
    client: TestClient, bars_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An export replacing a document between ``iterdir`` and ``stat`` is not a 500."""
    _write(bars_dir, SESSION, _VALID_DOCUMENT)
    real_stat = Path.stat

    def vanishing(self: Path, *args: object, **kwargs: object) -> os.stat_result:
        if self.suffix == ".json":
            raise FileNotFoundError(2, "vanished", str(self))
        return real_stat(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "stat", vanishing)
    response = client.get(f"/api/tos/sessions/{tos_bars.LATEST}/bars")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["reason"].startswith("bars document absent")


def test_latest_ignores_a_leftover_temp_file(
    client: TestClient, bars_dir: Path
) -> None:
    """A ``SIGKILL``-ed export leaves ``.<name>.<rand>.tmp``; it is not a document."""
    _write(bars_dir, SESSION, _VALID_DOCUMENT)
    leftover = bars_dir / f".{SESSION}.json.abc123.tmp"
    leftover.write_text("half a document", encoding="utf-8")
    os.utime(leftover, (9_000_000, 9_000_000))
    body = _get(client, tos_bars.LATEST)
    assert body["available"] is True
    assert body["session"] == SESSION


# ---------------------------------------------------------------------------
# GET /api/tos/sessions — the listing the panel's picker reads.
# ---------------------------------------------------------------------------


def _list(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/tos/sessions")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    return response.json()


def test_the_listing_names_every_exported_session_newest_day_first(
    client: TestClient, bars_dir: Path
) -> None:
    """The order is day-descending, and stable inside a day."""
    for session in [
        "stock-r1-20261124",
        "long-20261125",
        "stock-000660-r1-20261125",
        "short-20261125",
        "stock-r1-20261125",
    ]:
        _write(bars_dir, session, _VALID_DOCUMENT)
    body = _list(client)
    assert body["available"] is True
    assert body["reason"] is None
    assert body["truncated"] is False
    assert [item["session"] for item in body["sessions"]] == [
        "long-20261125",
        "short-20261125",
        "stock-000660-r1-20261125",
        "stock-r1-20261125",
        "stock-r1-20261124",
    ]


@pytest.mark.parametrize(
    ("session", "expected"),
    [
        (
            "long-20261125",
            {
                "date": "2026-11-25",
                "kind": "futures",
                "direction": "LONG",
                "instrument": None,
                "run": None,
            },
        ),
        (
            "short-20261125",
            {
                "date": "2026-11-25",
                "kind": "futures",
                "direction": "SHORT",
                "instrument": None,
                "run": None,
            },
        ),
        (
            # The tenant whose name predates the per-symbol convention: the
            # name carries no instrument, so neither does the entry.
            "stock-r1-20261125",
            {
                "date": "2026-11-25",
                "kind": "stock",
                "direction": None,
                "instrument": None,
                "run": 1,
            },
        ),
        (
            "stock-000660-r1-20261123",
            {
                "date": "2026-11-23",
                "kind": "stock",
                "direction": None,
                "instrument": "000660",
                "run": 1,
            },
        ),
        (
            # An operator restart is run 2, and the picker must be able to tell
            # it from cron's run on the same day.
            "stock-005380-r2-20261123",
            {
                "date": "2026-11-23",
                "kind": "stock",
                "direction": None,
                "instrument": "005380",
                "run": 2,
            },
        ),
        (
            # A name this route will not claim to recognise is still listed:
            # the reader opens it fine.
            "experiment_a-20261125",
            {
                "date": "2026-11-25",
                "kind": "other",
                "direction": None,
                "instrument": None,
                "run": None,
            },
        ),
        (
            # Eight digits that are not a date. Listed, grouped as undated.
            "long-20261345",
            {
                "date": None,
                "kind": "futures",
                "direction": "LONG",
                "instrument": None,
                "run": None,
            },
        ),
        (
            # No trailing day at all.
            "scratch",
            {
                "date": None,
                "kind": "other",
                "direction": None,
                "instrument": None,
                "run": None,
            },
        ),
    ],
)
def test_the_listing_derives_each_entry_from_the_name_alone(
    client: TestClient, bars_dir: Path, session: str, expected: dict[str, object]
) -> None:
    """Kind, date, side, symbol and run come from the file name, never the file."""
    # The document says 005930 on every one of them; nothing may read it.
    _write(bars_dir, session, _VALID_DOCUMENT)
    body = _list(client)
    assert len(body["sessions"]) == 1
    entry = body["sessions"][0]
    assert entry["session"] == session
    assert {key: entry[key] for key in expected} == expected
    assert entry["age_seconds"] is not None and entry["age_seconds"] >= 0


def test_an_undated_session_sorts_after_every_dated_one(
    client: TestClient, bars_dir: Path
) -> None:
    """A name without a readable day must not float above today's sessions."""
    for session in ["scratch", "stock-r1-20261110", "long-20261125"]:
        _write(bars_dir, session, _VALID_DOCUMENT)
    body = _list(client)
    assert [item["session"] for item in body["sessions"]] == [
        "long-20261125",
        "stock-r1-20261110",
        "scratch",
    ]


def test_the_listing_opens_no_document(
    client: TestClient, bars_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A megabyte apiece, per page load, for one string each — so: never.

    Pinned by making every open from this module raise: the listing must still
    answer. A regression that started reading documents to recover the
    instrument would fail here instead of being discovered as a slow page.
    """
    _write(bars_dir, "stock-r1-20261125", _VALID_DOCUMENT)
    _write(bars_dir, "long-20261125", "{not json at all")

    def refuse(*args: object, **kwargs: object) -> object:
        raise AssertionError("the listing opened a document")

    monkeypatch.setattr(Path, "open", refuse)
    monkeypatch.setattr(tos_bars.json, "load", refuse)
    body = _list(client)
    assert [item["session"] for item in body["sessions"]] == [
        "long-20261125",
        "stock-r1-20261125",
    ]


def test_an_invalid_document_is_still_listed(
    client: TestClient, bars_dir: Path
) -> None:
    """The picker offers it; the reader then says WHY it cannot be rendered.

    Hiding it would leave an operator unable to tell "never exported" from
    "exported broken" — the second is the one worth looking at.
    """
    _write(bars_dir, "stock-r1-20261125", "{not json")
    body = _list(client)
    assert [item["session"] for item in body["sessions"]] == ["stock-r1-20261125"]
    assert _get(client, "stock-r1-20261125")["reason"].startswith("invalid json")


def test_the_listing_is_bounded_by_its_configured_cap(
    client: TestClient, bars_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The NEWEST survive the cap, and the body says the list is partial."""
    for day in range(10, 20):
        _write(bars_dir, f"stock-r1-202611{day}", _VALID_DOCUMENT)
    monkeypatch.setenv("TOS_BARS_SESSION_LIST_MAX", "3")
    body = _list(client)
    assert body["truncated"] is True
    assert [item["session"] for item in body["sessions"]] == [
        "stock-r1-20261119",
        "stock-r1-20261118",
        "stock-r1-20261117",
    ]

    monkeypatch.delenv("TOS_BARS_SESSION_LIST_MAX")
    whole = _list(client)
    assert whole["truncated"] is False
    assert len(whole["sessions"]) == 10


@pytest.mark.parametrize("raw", ["0", "-1", "nonsense", "3.5", " 12x"])
def test_a_cap_that_is_not_a_positive_integer_falls_back_loudly(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, raw: str
) -> None:
    """Silently ignoring the operator's value looks exactly like applying it."""
    monkeypatch.setenv("TOS_BARS_SESSION_LIST_MAX", raw)
    with caplog.at_level(logging.INFO, logger=tos_bars.logger.name):
        assert tos_bars._session_list_max() == tos_bars._DEFAULT_SESSION_LIST_MAX
    assert [record.levelno for record in caplog.records] == [logging.WARNING]


@pytest.mark.parametrize("raw", ["", "   "])
def test_an_empty_cap_is_no_opinion_rather_than_a_bad_one(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, raw: str
) -> None:
    """Compose passes the knob through as ``${VAR:-}``, so empty is the norm.

    Warning on it would put a line in the container's stderr on every page
    load of a stack that is configured exactly as shipped.
    """
    monkeypatch.setenv("TOS_BARS_SESSION_LIST_MAX", raw)
    with caplog.at_level(logging.INFO, logger=tos_bars.logger.name):
        assert tos_bars._session_list_max() == tos_bars._DEFAULT_SESSION_LIST_MAX
    assert caplog.records == []


def test_a_cap_set_to_a_number_is_applied_whatever_the_whitespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``.env`` values arrive with whatever the file had around them."""
    monkeypatch.setenv("TOS_BARS_SESSION_LIST_MAX", " 7 ")
    assert tos_bars._session_list_max() == 7


def test_the_cap_default_is_not_a_literal_in_a_branch() -> None:
    """Configuration-driven: the number has a name and an env override."""
    assert tos_bars._DEFAULT_SESSION_LIST_MAX > 0
    source = _ROUTE_MODULE.read_text(encoding="utf-8")
    assert 'os.environ.get("TOS_BARS_SESSION_LIST_MAX"' in source


def test_the_listing_never_offers_the_latest_sentinel_as_a_session(
    client: TestClient, bars_dir: Path
) -> None:
    """A file literally named ``latest.json`` is not an id the picker may hand back.

    It would otherwise be a second option carrying the sentinel's own value,
    and selecting it would resolve by mtime rather than to that file.
    """
    _write(bars_dir, tos_bars.LATEST, _VALID_DOCUMENT)
    _write(bars_dir, "stock-r1-20261125", _VALID_DOCUMENT)
    body = _list(client)
    assert [item["session"] for item in body["sessions"]] == ["stock-r1-20261125"]


@pytest.mark.parametrize(
    "name",
    [
        ".stock-r1-20261125.json.abc123.tmp",  # a SIGKILLed export's leftover
        "stock-r1-20261125.json.bak",
        "notes.txt",
        ".hidden.json",  # stem ".hidden" — leading dot, outside the pattern
        "has space.json",
        "..json",
    ],
)
def test_the_listing_skips_what_the_reader_would_refuse(
    client: TestClient, bars_dir: Path, name: str
) -> None:
    """Only names that pass ``_SESSION_ID_PATTERN`` reach the body."""
    (bars_dir / name).write_text("{}", encoding="utf-8")
    assert _list(client)["sessions"] == []


def test_a_subdirectory_is_not_a_session(client: TestClient, bars_dir: Path) -> None:
    """``stock-r1-20261125.json/`` as a directory is the mount hazard, not a session."""
    (bars_dir / "stock-r1-20261125.json").mkdir()
    assert _list(client)["sessions"] == []


def test_an_empty_directory_is_available_with_no_sessions(
    client: TestClient, bars_dir: Path
) -> None:
    """Nothing exported yet is a fact this route established, not a failure to."""
    body = _list(client)
    assert (body["available"], body["sessions"], body["reason"]) == (True, [], None)


def test_an_absent_directory_is_absent_not_an_error(
    client: TestClient, bars_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Before the first export ever ran. A 200, and INFO rather than WARNING."""
    bars_dir.rmdir()
    with caplog.at_level(logging.INFO, logger=tos_bars.logger.name):
        body = _list(client)
    assert (body["available"], body["sessions"]) == (False, [])
    assert body["reason"] == "bars directory absent"
    assert [record.levelno for record in caplog.records] == [logging.INFO]


def test_an_unlistable_directory_names_permissions_not_the_data(
    client: TestClient, bars_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A 0700 directory or a uid mismatch on the mount — never a 500."""

    def denied(*args: object, **kwargs: object) -> object:
        raise PermissionError(13, "denied")

    monkeypatch.setattr(Path, "iterdir", denied)
    body = _list(client)
    assert (body["available"], body["sessions"]) == (False, [])
    assert body["reason"] == "cannot list bars directory: PermissionError"


def test_the_listing_survives_a_document_vanishing_mid_listing(
    client: TestClient, bars_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An export replacing a document between ``iterdir`` and ``stat``."""
    _write(bars_dir, "stock-r1-20261125", _VALID_DOCUMENT)
    _write(bars_dir, "long-20261125", _VALID_DOCUMENT)
    real_stat = Path.stat
    vanished = bars_dir / "long-20261125.json"

    def vanishing(self: Path, *args: object, **kwargs: object) -> os.stat_result:
        if self == vanished:
            raise FileNotFoundError(2, "vanished", str(self))
        return real_stat(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "stat", vanishing)
    body = _list(client)
    assert body["available"] is True
    assert [item["session"] for item in body["sessions"]] == ["stock-r1-20261125"]


def test_the_listing_body_carries_no_host_path_and_no_file_content(
    client: TestClient, bars_dir: Path
) -> None:
    """``/tos`` is internet-facing: the listing may expose only names and times."""
    hostile = "<img src=x onerror=alert(1)>"
    _write(
        bars_dir,
        "stock-r1-20261125",
        {**_VALID_DOCUMENT, "session": hostile, "instrument": "SECRET"},
    )
    serialized = json.dumps(_list(client))
    assert hostile not in serialized
    assert "SECRET" not in serialized
    assert "/home/deploy" not in serialized
    assert str(bars_dir) not in serialized


def test_the_two_routes_do_not_shadow_each_other() -> None:
    """``/sessions`` is two segments; the reader's path is four."""
    from services.dashboard.app import create_app

    paths = {route.path for route in create_app().routes}  # type: ignore[attr-defined]
    assert "/api/tos/sessions" in paths
    assert "/api/tos/sessions/{session_id}/bars" in paths


def test_the_sentinel_still_reads_through_the_reader(
    client: TestClient, bars_dir: Path
) -> None:
    """The listing does not replace ``latest``; the panel opens on it."""
    _write(bars_dir, "stock-r1-20261125", _VALID_DOCUMENT)
    assert _get(client, tos_bars.LATEST)["session"] == "stock-r1-20261125"


# --------------------------------------------------------------------------- #
# The explanation blocks — legibility plan §6 P2, items four and five
# --------------------------------------------------------------------------- #

#: The two blocks ``tools/tos_cp3/export_bars.py`` adds, as measured on the host
#: on 2026-11-25 against ``long-20261125`` (the single R1 entry at 09:14 and its
#: R2 exit at 09:50, +2.94 points on the mini contract). The exporter's own
#: tests build the same shape, so neither side can drift alone.
_EXPLAIN: dict[str, Any] = {
    "schema": "tos-bars-explain/1",
    "probe_basis": "OPERATOR_RULE_MAP",
    "rules": [
        {
            "label": "R1",
            "rule_id": "R1-ENTRY-LONG",
            "decision_kind": "ACTION",
            "rationale": "R1-ENTRY-LONG: entry window open, high-volatility regime…",
            "target_rationale": "R1-ENTRY-LONG: open a new long…",
            "probe": False,
            "fields": ["entry_window", "hi_vol", "z_x1000"],
            "bindings": ["z_entry_max_x1000"],
        },
        {
            "label": "R4",
            "rule_id": "R4-M2-PROBE-ENTRY-LONG",
            "decision_kind": "ACTION",
            "rationale": "R4-M2-PROBE-ENTRY-LONG: M2 boundary probe, NOT a signal…",
            "target_rationale": None,
            "probe": True,
            "fields": ["entry_window"],
            "bindings": [],
        },
    ],
    "default": {
        "label": None,
        "rule_id": "R0-DEFAULT-NO-ACTION",
        "decision_kind": "NO_ACTION",
        "rationale": "R0-DEFAULT-NO-ACTION: no rule fired — hold exposure unchanged.",
        "probe": None,
        "fields": None,
        "bindings": None,
    },
    "fields": {
        "z_x1000": {
            "field": "z",
            "op": "ratio_z",
            "inputs": ["close", "vwap", "atr"],
            "params": None,
            "scale": {"mult": 1000, "round": "toward_zero"},
            "published_as": "z_x1000",
            "known": True,
        },
        "ghost": {"field": "ghost", "op": None, "known": False},
    },
}

_HYPOTHETICAL: dict[str, Any] = {
    "hypothetical": True,
    "direction": "LONG",
    "instrument": "A05612",
    "contract": "kospi200_mini",
    "multiplier_krw_per_point": 50000,
    "price_field": "close_x100",
    "price_scale": 100,
    "assumptions": [
        "FILL_AT_DECISION_BAR_CLOSE",
        "FILL_ALWAYS_ASSUMED",
        "NO_FEES",
        "NO_SLIPPAGE",
        "ONE_CONTRACT",
        "ONE_POSITION_AT_A_TIME",
    ],
    "trades": [
        {
            "entry_time_kst": "09:14",
            "entry_rule_id": "R1-ENTRY-LONG",
            "entry_price_points": "735.64",
            "exit_time_kst": "09:50",
            "exit_rule_id": "R2-EXIT-VWAP-REVERTED",
            "exit_price_points": "738.58",
            "points": "2.94",
            "hypothetical_pnl_krw": "147000",
            "forced_close": False,
            "forced_close_reason": None,
        }
    ],
    "totals": {
        "trades": 1,
        "wins": 1,
        "points": "2.94",
        "hypothetical_pnl_krw": "147000",
        "forced_closes": 0,
    },
    "unpriced_decisions": [],
}


def _explained(**overrides: Any) -> dict[str, Any]:
    return {
        **_VALID_DOCUMENT,
        "market": "futures",
        "decision_only": True,
        "explain": _EXPLAIN,
        "hypothetical_pnl": _HYPOTHETICAL,
        **overrides,
    }


def test_each_rules_sentence_and_probe_marker_reach_the_body(
    client: TestClient, bars_dir: Path
) -> None:
    """식별자 대신 문장 — 그리고 «시험 진입» 과 신호가 다른 줄이 되게."""
    _write(bars_dir, SESSION, _explained())
    explain = _get(client)["document"]["explain"]
    assert explain["schema"] == "tos-bars-explain/1"
    assert explain["probe_basis"] == "OPERATOR_RULE_MAP"
    assert [rule["probe"] for rule in explain["rules"]] == [False, True]
    assert explain["rules"][0]["rationale"].startswith("R1-ENTRY-LONG:")
    assert explain["rules"][0]["bindings"] == ["z_entry_max_x1000"]
    assert explain["default"]["rule_id"] == "R0-DEFAULT-NO-ACTION"


def test_the_field_block_keeps_the_name_fields_not_fields_underscore(
    client: TestClient, bars_dir: Path
) -> None:
    """DTO 안에서만 ``fields_`` 다 — 몸통은 내보내기가 쓴 이름 그대로여야 한다."""
    _write(bars_dir, SESSION, _explained())
    explain = _get(client)["document"]["explain"]
    assert "fields_" not in explain
    assert "schema_" not in explain
    assert explain["fields"]["z_x1000"]["op"] == "ratio_z"
    assert explain["fields"]["z_x1000"]["scale"] == {
        "mult": 1000,
        "round": "toward_zero",
    }
    # A name the catalog did not define says so rather than claiming an op.
    assert explain["fields"]["ghost"]["known"] is False
    assert explain["fields"]["ghost"]["op"] is None


def test_the_hypothetical_block_arrives_with_its_assumptions(
    client: TestClient, bars_dir: Path
) -> None:
    """수만 떼어 그릴 수 없게, 가정이 값과 함께 간다."""
    _write(bars_dir, SESSION, _explained())
    document = _get(client)["document"]
    assert document["decision_only"] is True
    assert document["market"] == "futures"
    block = document["hypothetical_pnl"]
    assert block["hypothetical"] is True
    assert "FILL_ALWAYS_ASSUMED" in block["assumptions"]
    assert block["multiplier_krw_per_point"] == 50000
    assert block["trades"][0]["points"] == "2.94"
    assert block["totals"]["hypothetical_pnl_krw"] == "147000"


def test_no_hypothetical_key_is_named_like_a_realized_one(
    client: TestClient, bars_dir: Path
) -> None:
    """실현 손익과 같은 키 이름이면 언젠가 합산된다 — DTO 에 그 이름이 없다.

    ``symbols/today.json`` 의 실현 손익은 ``pnl_krw`` 다. 이 블록의 수는 전부
    ``hypothetical_`` 를 달고 있어, 두 문서를 한 화면에서 합치는 코드가 이름만
    보고 섞을 수 없다.
    """
    assert "pnl_krw" not in tos_bars.HypotheticalTotals.model_fields
    assert "pnl_krw" not in tos_bars.HypotheticalTrade.model_fields
    _write(bars_dir, SESSION, _explained())
    block = _get(client)["document"]["hypothetical_pnl"]
    assert "pnl_krw" not in block["totals"]
    assert "pnl_krw" not in block["trades"][0]


def test_a_document_without_the_new_blocks_still_reads(
    client: TestClient, bars_dir: Path
) -> None:
    """현장 호환: 아직 옛 내보내기가 쓴 문서여도 바 패널은 그대로 뜬다."""
    _write(bars_dir, SESSION, _VALID_DOCUMENT)
    document = _get(client)["document"]
    assert document["explain"] is None
    assert document["hypothetical_pnl"] is None
    assert document["decision_only"] is None
    assert document["bars"]


def test_a_document_that_could_not_be_explained_says_why(
    client: TestClient, bars_dir: Path
) -> None:
    """설명이 없는 것과 «왜 없는지 모르는 것» 은 다르다."""
    _write(
        bars_dir,
        SESSION,
        _explained(explain=None, explain_error="fields.yaml 을 읽지 못했다: OSError"),
    )
    document = _get(client)["document"]
    assert document["explain"] is None
    assert document["explain_error"].startswith("fields.yaml")
    assert document["bars"]


def test_the_explanation_blocks_never_carry_a_path(
    client: TestClient, bars_dir: Path
) -> None:
    """두 블록은 브라우저로 간다. 문서가 경로를 들고 와도 DTO 가 모른다."""
    polluted = _explained()
    polluted["explain"] = {**_EXPLAIN, "source_path": "/home/deploy/secret.yaml"}
    _write(bars_dir, SESSION, polluted)
    body = json.dumps(_get(client), ensure_ascii=False)
    assert "/home/deploy/secret.yaml" not in body
    # The document's own pre-existing host paths stay dropped too.
    assert _VALID_DOCUMENT["data_dir"] not in body
