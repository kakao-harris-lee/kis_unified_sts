from __future__ import annotations

import ast
import json
from pathlib import Path

from fastapi.testclient import TestClient

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
    assert response.headers["cache-control"] == "no-store"
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


_TOS_PREFIX = "/api/tos"
# FastAPI/Starlette do not implicitly add HEAD or OPTIONS to a route's
# `.methods` set (verified directly against the live app: a GET-only route
# reports `{"GET"}`, nothing more) — but the check strips them anyway so the
# assertion stays correct if that framework behavior ever changes.
_IMPLICIT_METHODS = {"HEAD", "OPTIONS"}


def _non_meta_methods_under_prefix(routes, prefix: str) -> set[str]:
    """Union of non-implicit HTTP methods for every route under ``prefix``.

    Matches by ``path.startswith(prefix)`` rather than an exact path so a new
    route added anywhere under the prefix (not just at the one path this
    module happens to define today) is caught — plan §2 decision 8c pins the
    *whole* router to GET, not one endpoint.
    """
    methods: set[str] = set()
    for route in routes:
        path = getattr(route, "path", None)
        if path is None or not path.startswith(prefix):
            continue
        methods |= set(getattr(route, "methods", set()) or set())
    return methods - _IMPLICIT_METHODS


def test_route_is_get_only():
    app = create_app()

    app_methods = _non_meta_methods_under_prefix(app.routes, _TOS_PREFIX)
    assert app_methods, "expected at least one /api/tos route registered on the app"
    assert app_methods == {"GET"}

    # Independent of the app's prefix/mounting: check the router object
    # itself, so a route added to `router` would be caught even if some
    # future app wiring changed how/where it's mounted.
    router_methods = _non_meta_methods_under_prefix(tos_projection.router.routes, "")
    assert router_methods, "expected at least one route on tos_projection.router"
    assert router_methods == {"GET"}


def test_get_only_checker_detects_an_added_post():
    """Negative self-check: prove the checker actually catches a violation.

    Builds a throwaway router with one POST endpoint under /api/tos/... and
    runs the same `_non_meta_methods_under_prefix` helper against it. If this
    assertion ever stopped failing, the positive checks above would be
    vacuous — this is the same idiom as the runtime's negative-grep
    self-tests (`tests/operator/test_no_write_port.py`).
    """
    from fastapi import APIRouter

    poisoned = APIRouter(prefix="/api/tos", tags=["tos"])

    @poisoned.post("/mutation-canary")
    async def _mutation_canary() -> dict[str, bool]:
        return {"ok": True}

    methods = _non_meta_methods_under_prefix(poisoned.routes, _TOS_PREFIX)
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


# These neutral JSON fixtures are also checked against the runtime producer and UI.
# No imports cross the TOS boundary.
def test_shared_projection_contract_fixtures(monkeypatch, tmp_path):
    fixture_dir = Path(__file__).resolve().parents[3] / "tests/fixtures/tos"
    for fixture in sorted(fixture_dir.glob("operator-projection-v1*.json")):
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
    assert body["projection"]["safety_mesh"] is None
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
        / "tests/fixtures/tos/operator-projection-v1.json"
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
        / "tests/fixtures/tos/operator-projection-v1.json"
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
