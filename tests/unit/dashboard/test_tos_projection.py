from __future__ import annotations

import ast
import json
import logging
import re
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import BaseModel

from services.dashboard.app import create_app
from services.dashboard.routes import tos_projection

_ROUTE_MODULE = (
    Path(__file__).resolve().parents[3]
    / "services"
    / "dashboard"
    / "routes"
    / "tos_projection.py"
)

_VALID_PROJECTION: dict = {
    "schema_version": 1,
    "projection_generation": 17,
    "exported_at_monotonic_ns": 123456789,
    "non_authorizing": True,
    "runtime": {
        "cell_id": "cell-1",
        "runtime_generation": 3,
        "process_nonce": "abc123",
        "code_digest": "sha256:deadbeef",
    },
    "recovery": {"readiness_verdict": "READY", "reasons": []},
    "driver": {"wired": True, "halt_latched": None, "halt_reason": None},
    "time": {"health": "TRUSTED"},
    "currentness": {
        "pending_dimensions": ["CONTEXT", "CRITICAL_INPUT", "EGRESS_IDENTITY"],
        "last_assemble_complete": None,
    },
    "rcl": {"last_seq": None, "open_reservations": None},
    "inbox": {"unconsumed_count": None},
    "evidence": {
        "tip_seq_excluding_stm_alert": None,
        "chain_digest": None,
        "key_generation": None,
    },
    "release": {"admitted": None, "software_deployment_ok": None},
    "operations": {
        "schema_versions": {"evidence": 1, "rcl": 1, "inbox": None},
        "last_backup": {
            "generation": None,
            "age_monotonic_ns": None,
            "manifest_digest": None,
        },
        "key_continuity": None,
        "dependency_admission": None,
    },
    "alerts": {
        "unresolved_stm_alert_seqs": [],
        "delivery_owner": "legacy alert-manager (outside tos_runtime)",
    },
    "export": {"failures": 0, "last_error": None},
}


def _client(monkeypatch, tmp_path: Path, projection_path: Path | None = None):
    monkeypatch.setenv("DASHBOARD_DEV_MODE", "true")
    path = projection_path if projection_path is not None else tmp_path / "missing.json"
    monkeypatch.setenv("TOS_OPERATOR_PROJECTION_PATH", str(path))
    app = create_app()
    return TestClient(app)


def test_valid_projection_round_trips(monkeypatch, tmp_path):
    projection_path = tmp_path / "operator_projection.json"
    projection_path.write_text(json.dumps(_VALID_PROJECTION), encoding="utf-8")

    client = _client(monkeypatch, tmp_path, projection_path)
    response = client.get("/api/tos/projection")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert response.headers["cache-control"] == "no-store"
    assert body["reason"] is None
    assert body["age_seconds"] >= 0
    assert body["projection"]["schema_version"] == 1
    assert body["projection"]["projection_generation"] == 17
    assert body["projection"]["non_authorizing"] is True
    # (compose/_types.py) — a store whose ``PRAGMA user_version`` is not
    assert body["projection"]["operations"]["schema_versions"] == {
        "evidence": 1,
        "rcl": 1,
        "inbox": None,
    }
    assert body["projection"]["alerts"]["delivery_owner"] == (
        "legacy alert-manager (outside tos_runtime)"
    )


def test_absent_file_reports_unavailable(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    response = client.get("/api/tos/projection")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["reason"] == "projection file absent"
    assert body["projection"] is None


def test_broken_json_reports_unavailable(monkeypatch, tmp_path):
    projection_path = tmp_path / "broken.json"
    projection_path.write_text("{not valid json", encoding="utf-8")

    client = _client(monkeypatch, tmp_path, projection_path)
    response = client.get("/api/tos/projection")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["reason"] is not None
    assert "invalid json" in body["reason"]
    assert body["projection"] is None


def test_unsupported_schema_version_reports_unavailable(monkeypatch, tmp_path):
    payload = dict(_VALID_PROJECTION)
    payload["schema_version"] = 2
    projection_path = tmp_path / "future.json"
    projection_path.write_text(json.dumps(payload), encoding="utf-8")

    client = _client(monkeypatch, tmp_path, projection_path)
    response = client.get("/api/tos/projection")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert "unsupported schema_version" in body["reason"]
    assert body["projection"] is None


_TOS_PREFIX = "/api/tos"


def _declared_methods_under_prefix(routes, prefix: str) -> set[str]:
    """Union of the declared HTTP methods of every route under ``prefix``."""
    methods: set[str] = set()
    for route in routes:
        path = getattr(route, "path", None)
        if path is None or not path.startswith(prefix):
            continue
        methods |= set(getattr(route, "methods", set()) or set())
    return methods


def test_declared_methods_include_no_implicit_head_or_options():
    """Pins the framework behavior the GET-only check now relies on."""
    from fastapi import APIRouter

    probe = APIRouter(prefix="/api/tos", tags=["tos"])

    @probe.get("/framework-probe")
    async def _framework_probe() -> dict[str, bool]:
        return {"ok": True}

    assert _declared_methods_under_prefix(probe.routes, _TOS_PREFIX) == {"GET"}
    assert _declared_methods_under_prefix(create_app().routes, _TOS_PREFIX) == {"GET"}


def test_an_explicit_head_route_fails_the_get_only_check():
    """Negative self-check for the removed subtraction."""
    from fastapi import APIRouter

    poisoned = APIRouter(prefix="/api/tos", tags=["tos"])

    @poisoned.head("/head-canary")
    async def _head_canary() -> None:
        return None

    assert _declared_methods_under_prefix(poisoned.routes, _TOS_PREFIX) == {"HEAD"}


def test_route_is_get_only():
    app = create_app()

    app_methods = _declared_methods_under_prefix(app.routes, _TOS_PREFIX)
    assert app_methods, "expected at least one /api/tos route registered on the app"
    assert app_methods == {"GET"}

    router_methods = _declared_methods_under_prefix(tos_projection.router.routes, "")
    assert router_methods, "expected at least one route on tos_projection.router"
    assert router_methods == {"GET"}


def test_get_only_checker_detects_an_added_post():
    """Negative self-check: prove the checker actually catches a violation."""
    from fastapi import APIRouter

    poisoned = APIRouter(prefix="/api/tos", tags=["tos"])

    @poisoned.post("/mutation-canary")
    async def _mutation_canary() -> dict[str, bool]:
        return {"ok": True}

    methods = _declared_methods_under_prefix(poisoned.routes, _TOS_PREFIX)
    assert methods == {"POST"}
    assert methods != {"GET"}


def test_route_module_does_not_import_tos_or_tos_runtime():
    source = _ROUTE_MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(_ROUTE_MODULE))

    forbidden_roots = {"tos", "tos_runtime"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                assert (
                    root not in forbidden_roots
                ), f"forbidden import of {alias.name!r} in {_ROUTE_MODULE}"
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".")[0]
            assert (
                root not in forbidden_roots
            ), f"forbidden import-from {module!r} in {_ROUTE_MODULE}"


SHARED_PROJECTION_FIXTURES = frozenset(
    {"operator-projection-v1.json", "operator-projection-v1-unknown.json"}
)


def test_shared_projection_contract_fixtures(monkeypatch, tmp_path):
    fixture_dir = Path(__file__).resolve().parents[3] / "tos/runtime/tests/fixtures"
    matched = sorted(fixture_dir.glob("operator-projection-v1*.json"))
    assert {f.name for f in matched} == SHARED_PROJECTION_FIXTURES, (
        f"shared contract fixtures missing from {fixture_dir}: "
        f"found {sorted(f.name for f in matched)}"
    )
    for fixture in matched:
        payload = json.loads(fixture.read_text())
        projection_path = tmp_path / fixture.name
        projection_path.write_text(json.dumps(payload))
        body = (
            _client(monkeypatch, tmp_path, projection_path)
            .get("/api/tos/projection")
            .json()
        )
        assert body["available"] is True, body
        assert body["projection"] == payload


def test_missing_groups_remain_unknown_instead_of_empty_facts(monkeypatch, tmp_path):
    path = tmp_path / "minimal.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "projection_generation": 1,
                "exported_at_monotonic_ns": 1,
                "non_authorizing": True,
            }
        )
    )
    body = _client(monkeypatch, tmp_path, path).get("/api/tos/projection").json()
    assert body["available"] is True
    assert body["projection"]["alerts"] is None
    assert body["projection"]["release"] is None


def test_projection_requires_existing_dashboard_auth(monkeypatch, tmp_path):
    monkeypatch.setenv("TOS_OPERATOR_PROJECTION_PATH", str(tmp_path / "missing.json"))
    client = TestClient(create_app(require_auth=True, api_key="test-projection-key"))
    assert client.get("/api/tos/projection").status_code == 401
    assert (
        client.get("/api/tos/projection", headers={"X-API-Key": "wrong"}).status_code
        == 401
    )
    response = client.get(
        "/api/tos/projection", headers={"X-API-Key": "test-projection-key"}
    )
    assert response.status_code == 200
    assert response.json()["available"] is False


def test_invalid_utf8_is_unavailable(monkeypatch, tmp_path):
    path = tmp_path / "projection.json"
    path.write_bytes(b"\xff\xfe")
    response = _client(monkeypatch, tmp_path, path).get("/api/tos/projection")
    assert response.status_code == 200
    assert response.json()["available"] is False
    assert response.json()["reason"].startswith("invalid json")


def test_future_mtime_is_unknown_age(monkeypatch, tmp_path):
    import os
    import time

    fixture = (
        Path(__file__).resolve().parents[3]
        / "tos/runtime/tests/fixtures/operator-projection-v1.json"
    )
    path = tmp_path / "projection.json"
    path.write_bytes(fixture.read_bytes())
    future = time.time() + 3600
    os.utime(path, (future, future))
    body = _client(monkeypatch, tmp_path, path).get("/api/tos/projection").json()
    assert body["available"] is True
    assert body["age_seconds"] is None


def test_atomic_replace_reads_age_and_payload_from_same_inode(monkeypatch, tmp_path):
    import os
    import time

    fixture = (
        Path(__file__).resolve().parents[3]
        / "tos/runtime/tests/fixtures/operator-projection-v1.json"
    )
    path = tmp_path / "projection.json"
    original = json.loads(fixture.read_text())
    original["projection_generation"] = 1
    path.write_text(json.dumps(original))
    old = time.time() - 120
    os.utime(path, (old, old))
    replacement = tmp_path / "replacement.json"
    newer = dict(original, projection_generation=2)
    replacement.write_text(json.dumps(newer))
    real_fstat = os.fstat

    def replace_after_open(fd):
        stat = real_fstat(fd)
        if replacement.exists():
            os.replace(replacement, path)
        return stat

    monkeypatch.setattr(tos_projection.os, "fstat", replace_after_open)
    body = tos_projection._read_projection(path)
    assert body.projection.projection_generation == 1
    assert body.age_seconds >= 120
    assert json.loads(path.read_text())["projection_generation"] == 2


def test_reason_lists_keep_absent_distinct_from_empty(monkeypatch, tmp_path):
    """지적 2: ``null`` is accepted, and an absent key stays ``null``, not ``[]``."""
    payload = dict(
        _VALID_PROJECTION,
        recovery={"readiness_verdict": "READY", "reasons": None},
    )
    path = tmp_path / "reasons.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    body = _client(monkeypatch, tmp_path, path).get("/api/tos/projection").json()

    assert body["available"] is True, body
    assert body["projection"]["recovery"]["reasons"] is None
    assert body["projection"]["driver"]["halt_reason"] is None


def test_inner_facts_may_be_null_without_losing_the_document(monkeypatch, tmp_path):
    """노트 a: the inner fields that became nullable, all set to ``null``."""
    payload = dict(
        _VALID_PROJECTION,
        currentness={"pending_dimensions": None, "last_assemble_complete": None},
        operations={
            "schema_versions": None,
            "last_backup": None,
            "key_continuity": None,
            "dependency_admission": None,
        },
    )
    path = tmp_path / "inner-null.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    body = _client(monkeypatch, tmp_path, path).get("/api/tos/projection").json()

    assert body["available"] is True, body
    projection = body["projection"]
    assert projection["currentness"]["pending_dimensions"] is None
    assert projection["operations"]["schema_versions"] is None
    assert projection["operations"]["last_backup"] is None


def test_schema_versions_accepts_a_store_without_a_readable_version(
    monkeypatch, tmp_path
):
    """지적 6: producer declares ``dict[str, int | None]``."""
    payload = dict(
        _VALID_PROJECTION,
        operations=dict(
            _VALID_PROJECTION["operations"],
            schema_versions={"evidence": 1, "rcl": None, "inbox": None},
        ),
    )
    path = tmp_path / "schema-versions.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    body = _client(monkeypatch, tmp_path, path).get("/api/tos/projection").json()

    assert body["available"] is True, body
    assert body["projection"]["operations"]["schema_versions"] == {
        "evidence": 1,
        "rcl": None,
        "inbox": None,
    }


def test_schema_mismatch_reason_never_echoes_the_file_contents(monkeypatch, tmp_path):
    """지적 3: pydantic's ``str(exc)`` carries ``input_value=...``."""
    secret = "SENTINEL-/srv/private/custody/secret"
    payload = dict(_VALID_PROJECTION, projection_generation=secret)
    path = tmp_path / "mismatch.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    body = _client(monkeypatch, tmp_path, path).get("/api/tos/projection").json()

    assert body["available"] is False
    assert body["reason"].startswith("schema mismatch at projection_generation")
    assert secret not in body["reason"]
    assert "input_value" not in body["reason"]
    assert "SENTINEL" not in json.dumps(body)


def test_a_directory_in_place_of_the_file_is_not_a_format_error(monkeypatch, tmp_path):
    """지적 4: ``IsADirectoryError`` is a wiring fault, not malformed data."""
    path = tmp_path / "operator_projection.json"
    path.mkdir()

    body = _client(monkeypatch, tmp_path, path).get("/api/tos/projection").json()

    assert body["available"] is False
    assert body["reason"] == "cannot read projection: IsADirectoryError"
    assert body["projection"] is None


def test_an_unreadable_directory_is_not_a_format_error(monkeypatch, tmp_path):
    """지적 4: the runbook's first installation hazard — 0700 dir / uid mismatch."""
    import os as _os

    if _os.geteuid() == 0:
        import pytest

        pytest.skip("root bypasses directory permissions")

    locked = tmp_path / "locked"
    locked.mkdir()
    path = locked / "operator_projection.json"
    path.write_text(json.dumps(_VALID_PROJECTION), encoding="utf-8")
    locked.chmod(0o000)
    try:
        body = _client(monkeypatch, tmp_path, path).get("/api/tos/projection").json()
    finally:
        locked.chmod(0o700)

    assert body["available"] is False
    assert body["reason"] == "cannot read projection: PermissionError"
    assert body["projection"] is None


def test_response_never_carries_the_projection_filesystem_path(monkeypatch, tmp_path):
    """지적 10: the path is a server-side deployment detail."""
    projection_path = tmp_path / "operator_projection.json"
    projection_path.write_text(json.dumps(_VALID_PROJECTION), encoding="utf-8")
    client = _client(monkeypatch, tmp_path, projection_path)

    available = client.get("/api/tos/projection").json()
    assert "path" not in available
    assert str(projection_path) not in json.dumps(available)

    assert "path" not in tos_projection.TosProjectionResponse.model_fields

    missing_client = _client(monkeypatch, tmp_path, tmp_path / "gone.json")
    unavailable = missing_client.get("/api/tos/projection").json()
    assert "path" not in unavailable
    assert str(tmp_path) not in json.dumps(unavailable)


_REASON_FIXTURE = (
    Path(__file__).resolve().parents[3] / "tests/fixtures/tos/projection-reasons.json"
)


def _reason_prefixes() -> list[str]:
    payload = json.loads(_REASON_FIXTURE.read_text(encoding="utf-8"))
    return [entry["prefix"] for entry in payload["reasons"]]


def test_unsupported_schema_version_reason_never_echoes_the_value(
    monkeypatch, tmp_path
):
    """지적 1: the version field is read from the file like any other value."""
    secret = "SENTINEL-" + "x" * 300
    payload = dict(_VALID_PROJECTION, schema_version=secret)
    path = tmp_path / "version.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    body = _client(monkeypatch, tmp_path, path).get("/api/tos/projection").json()

    assert body["available"] is False
    assert body["reason"] == "unsupported schema_version (expected 1, got str)"
    assert "SENTINEL" not in json.dumps(body)


def test_unsupported_schema_version_reports_the_shape_of_a_structured_value(
    monkeypatch, tmp_path
):
    payload = dict(_VALID_PROJECTION, schema_version={"nested": "SENTINEL"})
    path = tmp_path / "version-object.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    body = _client(monkeypatch, tmp_path, path).get("/api/tos/projection").json()

    assert body["reason"] == "unsupported schema_version (expected 1, got dict)"
    assert "SENTINEL" not in json.dumps(body)


def test_schema_mismatch_location_never_echoes_a_mapping_key(monkeypatch, tmp_path):
    """지적 2: inside a mapping the failing segment is a key from the file."""
    hostile = "SENTINEL-/srv/private/custody/key"
    payload = dict(
        _VALID_PROJECTION,
        operations=dict(
            _VALID_PROJECTION["operations"],
            schema_versions={hostile: "not-an-int"},
        ),
    )
    path = tmp_path / "hostile-key.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    body = _client(monkeypatch, tmp_path, path).get("/api/tos/projection").json()

    assert body["available"] is False
    assert body["reason"].startswith(
        "schema mismatch at operations.schema_versions.<key>"
    )
    assert "SENTINEL" not in json.dumps(body)


def test_schema_mismatch_location_keeps_real_field_names_through_a_mapping(
    monkeypatch, tmp_path
):
    """The sanitizer must not flatten everything to ``<key>``."""
    payload = dict(
        _VALID_PROJECTION,
        operations={
            "schema_versions": {"evidence": "not-an-int"},
            "last_backup": None,
            "key_continuity": None,
            "dependency_admission": None,
        },
    )
    path = tmp_path / "service-field.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    body = _client(monkeypatch, tmp_path, path).get("/api/tos/projection").json()

    assert body["available"] is False
    assert body["reason"].startswith(
        "schema mismatch at operations.schema_versions.<key>"
    )


def _unavailable_log_record(monkeypatch, tmp_path, path, caplog):
    with caplog.at_level(logging.DEBUG, logger=tos_projection.__name__):
        body = _client(monkeypatch, tmp_path, path).get("/api/tos/projection").json()
    records = [r for r in caplog.records if r.name == tos_projection.__name__]
    assert records, caplog.text
    return body, records[-1]


def test_an_absent_projection_logs_the_path_at_info_not_warning(
    monkeypatch, tmp_path, caplog
):
    """지적 1 (2 회차): absent is the normal state outside a paper session."""
    projection_path = tmp_path / "gone.json"
    body, record = _unavailable_log_record(
        monkeypatch, tmp_path, projection_path, caplog
    )

    assert body["available"] is False
    assert record.levelno == logging.INFO, record.levelname
    message = record.getMessage()
    assert str(projection_path) in message
    assert "projection file absent" in message


def test_a_real_fault_logs_the_path_at_warning(monkeypatch, tmp_path, caplog):
    """The other side: a fault must stay visible."""
    path = tmp_path / "a-directory.json"
    path.mkdir()
    body, record = _unavailable_log_record(monkeypatch, tmp_path, path, caplog)

    assert body["available"] is False
    assert record.levelno == logging.WARNING, record.levelname
    assert str(path) in record.getMessage()
    assert "cannot read projection" in record.getMessage()


def test_the_configured_root_logger_shows_warning_and_hides_info():
    """Pins the measured premise the level split rests on."""
    import logging.config

    import uvicorn.config

    assert set(uvicorn.config.LOGGING_CONFIG["loggers"]) == {
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
    }
    assert "root" not in uvicorn.config.LOGGING_CONFIG

    saved_handlers = logging.root.handlers[:]
    saved_level = logging.root.level
    try:
        logging.root.handlers[:] = []
        logging.root.setLevel(logging.WARNING)
        logging.config.dictConfig(uvicorn.config.LOGGING_CONFIG)

        assert logging.root.handlers == []
        assert logging.root.level == logging.WARNING
        module_logger = logging.getLogger(tos_projection.__name__)
        assert module_logger.handlers == []
        assert module_logger.propagate is True
        assert module_logger.getEffectiveLevel() == logging.WARNING

        assert logging.lastResort is not None
        assert logging.lastResort.level == logging.WARNING
        assert module_logger.isEnabledFor(logging.WARNING) is True
        assert module_logger.isEnabledFor(logging.INFO) is False
    finally:
        logging.root.handlers[:] = saved_handlers
        logging.root.setLevel(saved_level)


def test_the_log_line_never_carries_projection_content(monkeypatch, tmp_path, caplog):
    secret = "SENTINEL-/srv/private/custody/secret"
    payload = dict(_VALID_PROJECTION, projection_generation=secret)
    path = tmp_path / "mismatch-log.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with caplog.at_level(logging.DEBUG, logger=tos_projection.__name__):
        _client(monkeypatch, tmp_path, path).get("/api/tos/projection")

    assert "SENTINEL" not in caplog.text


def _reason_literal(call: ast.Call) -> ast.expr:
    """The ``reason`` argument of an ``_unavailable`` call, positional or not."""
    if call.args:
        return call.args[0]
    for keyword in call.keywords:
        if keyword.arg == "reason":
            return keyword.value
    raise AssertionError(f"_unavailable call with no reason: {ast.dump(call)}")


def _reason_prefix_of(node: ast.expr) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr) and node.values:
        head = node.values[0]
        assert isinstance(head, ast.Constant), ast.dump(node)
        return str(head.value)
    raise AssertionError(f"unreadable reason expression: {ast.dump(node)}")


def _unavailable_calls(tree: ast.AST) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_unavailable"
    ]


def _unavailable_reason_prefixes(source: str) -> list[str]:
    """Every reason an ``_unavailable`` call site can produce."""
    tree = ast.parse(source)
    calls = _unavailable_calls(tree)
    prefixes = [_reason_prefix_of(_reason_literal(call)) for call in calls]
    assert len(prefixes) == len(calls), (len(prefixes), len(calls))
    return prefixes


def _unavailable_response_sites(source: str) -> set[str]:
    """Functions that build a ``TosProjectionResponse`` with ``available`` false."""
    tree = ast.parse(source)
    owners: set[str] = set()
    functions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    for function in functions:
        for node in ast.walk(function):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "TosProjectionResponse"
            ):
                continue
            available = next(
                (kw.value for kw in node.keywords if kw.arg == "available"), None
            )
            if isinstance(available, ast.Constant) and available.value is True:
                continue
            owners.add(function.name)
    return owners


def test_every_emitted_reason_starts_with_a_pinned_prefix():
    """노트 f: the Python emitter and the TS matcher share one list."""
    prefixes = _reason_prefixes()
    emitted = _unavailable_reason_prefixes(_ROUTE_MODULE.read_text(encoding="utf-8"))

    assert len(emitted) >= 5, emitted
    for reason in emitted:
        assert any(
            reason.startswith(prefix) for prefix in prefixes
        ), f"{reason!r} matches no prefix in {_REASON_FIXTURE.name}: {prefixes}"


def test_only_unavailable_builds_an_unavailable_response():
    """The other half of completeness (지적 2, 2 회차)."""
    owners = _unavailable_response_sites(_ROUTE_MODULE.read_text(encoding="utf-8"))
    assert owners == {"_unavailable"}, owners


_KEYWORD_CALL_MODULE = """
def _unavailable(reason, path, age_seconds=None, level=None):
    return TosProjectionResponse(available=False, reason=reason)


def _read(path):
    if path:
        return _unavailable("projection file absent", path)
    return _unavailable(reason="brand new cause nobody mapped", path=path)
"""

_ASYNC_RETURN_MODULE = """
def _unavailable(reason, path, age_seconds=None, level=None):
    return TosProjectionResponse(available=False, reason=reason)


async def get_tos_projection(response):
    return TosProjectionResponse(available=False, reason="from an async def")
"""

_DIRECT_RETURN_MODULE = """
def _unavailable(reason, path, age_seconds=None, level=None):
    return TosProjectionResponse(available=False, reason=reason)


def _read(path):
    return TosProjectionResponse(available=False, reason="bypassed the prefixes")
"""


def test_the_reason_scan_catches_a_keyword_only_call():
    """Red proof for the scan itself: this is what the old check skipped."""
    prefixes = _reason_prefixes()
    emitted = _unavailable_reason_prefixes(_KEYWORD_CALL_MODULE)

    assert "brand new cause nobody mapped" in emitted, emitted
    unmapped = [
        reason
        for reason in emitted
        if not any(reason.startswith(prefix) for prefix in prefixes)
    ]
    assert unmapped == ["brand new cause nobody mapped"], (emitted, unmapped)


def test_the_response_scan_catches_a_direct_unavailable_return():
    """Red proof: a branch that skips ``_unavailable`` is named."""
    assert _unavailable_response_sites(_DIRECT_RETURN_MODULE) == {
        "_unavailable",
        "_read",
    }


def test_each_pinned_prefix_is_actually_reachable(monkeypatch, tmp_path):
    """The other direction: a prefix nobody emits would be dead UI mapping."""
    absent = tmp_path / "absent.json"

    unreadable = tmp_path / "a-directory.json"
    unreadable.mkdir()

    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")

    mismatched = tmp_path / "mismatched.json"
    mismatched.write_text(
        json.dumps(dict(_VALID_PROJECTION, projection_generation="nope")),
        encoding="utf-8",
    )

    future = tmp_path / "future.json"
    future.write_text(
        json.dumps(dict(_VALID_PROJECTION, schema_version=2)), encoding="utf-8"
    )

    observed = set()
    for path in (absent, unreadable, broken, mismatched, future):
        body = _client(monkeypatch, tmp_path, path).get("/api/tos/projection").json()
        assert body["available"] is False, (path.name, body)
        observed.add(body["reason"])

    for prefix in _reason_prefixes():
        assert any(
            reason.startswith(prefix) for reason in observed
        ), f"no observed reason starts with {prefix!r}: {sorted(observed)}"


_TS_CONTRACT = (
    Path(__file__).resolve().parents[3] / "strategy-builder-ui/src/lib/dashboard/tos.ts"
)


def _dto_leaf_names(model: type) -> set[str]:
    """Every field name reachable from a DTO model, at any depth."""
    names: set[str] = set()
    for name, field in model.model_fields.items():
        names.add(name)
        target = tos_projection._field_target(field.annotation)
        while isinstance(target, tuple):
            target = target[1]
        if isinstance(target, type) and issubclass(target, BaseModel):
            names |= _dto_leaf_names(target)
    return names


def _ts_declared_identifiers(source: str) -> set[str]:
    """Property names declared anywhere in the TS contract file."""
    pattern = r"(?:^|[{;])\s*([A-Za-z_][A-Za-z0-9_]*)\??:"
    return set(re.findall(pattern, source, re.MULTILINE))


def test_every_dto_leaf_name_appears_in_the_ts_contract():
    """노트 c: the claim is a property, so check it as one."""
    declared = _ts_declared_identifiers(_TS_CONTRACT.read_text(encoding="utf-8"))
    leaves = _dto_leaf_names(tos_projection.TosOperatorProjection)

    assert len(leaves) > 40, len(leaves)
    assert not leaves - declared, sorted(leaves - declared)


def test_the_ts_contract_scan_catches_a_dropped_leaf():
    """Red proof: drop one leaf from the TS text and the parity check fails."""
    source = _TS_CONTRACT.read_text(encoding="utf-8")
    assert "process_nonce" in _ts_declared_identifiers(source)

    without = source.replace("process_nonce?: string | null;", "", 1)
    assert "process_nonce" not in _ts_declared_identifiers(without)
    assert "process_nonce" in _dto_leaf_names(tos_projection.TosOperatorProjection)


def test_the_response_scan_sees_an_async_function():
    """Red proof for 지적 2's residual: ``async def`` is a different node type."""
    assert _unavailable_response_sites(_ASYNC_RETURN_MODULE) == {
        "_unavailable",
        "get_tos_projection",
    }


def test_a_boolean_schema_version_is_rejected(monkeypatch, tmp_path):
    """노트 a: ``True != 1`` is False, so JSON ``true`` walked the version gate."""
    payload = dict(_VALID_PROJECTION, schema_version=True)
    path = tmp_path / "boolean-version.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert '"schema_version": true' in path.read_text(encoding="utf-8")

    body = _client(monkeypatch, tmp_path, path).get("/api/tos/projection").json()

    assert body["available"] is False
    assert body["reason"] == "unsupported schema_version (expected 1, got bool)"
    assert body["projection"] is None
