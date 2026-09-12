from __future__ import annotations

import ast
import json
from pathlib import Path

from fastapi.testclient import TestClient

from services.dashboard.app import create_app

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
    "safety_mesh": {
        "snapshot_generation": None,
        "services": {
            "spg": {"clear": None, "reasons": []},
            "wdr": {"clear": True, "reasons": []},
            "sir": {"clear": None, "reasons": ["no source"]},
            "stm": {"clear": None, "reasons": []},
        },
    },
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
    "protective": {"last_verdict": None},
    "operations": {
        "schema_versions": {"evidence": 1, "rcl": 1, "inbox": 1},
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
    assert body["reason"] is None
    assert body["age_seconds"] >= 0
    assert body["projection"]["schema_version"] == 1
    assert body["projection"]["projection_generation"] == 17
    assert body["projection"]["non_authorizing"] is True
    assert body["projection"]["safety_mesh"]["services"]["spg"]["clear"] is None
    assert body["projection"]["operations"]["schema_versions"] == {
        "evidence": 1,
        "rcl": 1,
        "inbox": 1,
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


def test_route_is_get_only():
    app = create_app()
    tos_routes = [
        route
        for route in app.routes
        if getattr(route, "path", None) == "/api/tos/projection"
    ]
    assert tos_routes, "expected /api/tos/projection to be registered"

    methods: set[str] = set()
    for route in tos_routes:
        methods |= set(getattr(route, "methods", set()) or set())

    assert methods == {"GET"}


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
