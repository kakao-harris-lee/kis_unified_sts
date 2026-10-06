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
    assert body["projection"]["safety_mesh"]["services"]["spg"]["clear"] is None
    # ``OperationsFacts.schema_versions`` is declared ``dict[str, int | None]``
    # (compose/_types.py) — a store whose ``PRAGMA user_version`` is not
    # readable yet reports ``None`` for its own key, and that must survive.
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
    """Union of the declared HTTP methods of every route under ``prefix``.

    Nothing is subtracted. FastAPI's ``APIRoute`` stores exactly the methods
    the decorator declared — a GET-only route reports ``{"GET"}``, with no
    implicit ``HEAD``/``OPTIONS`` (asserted by
    ``test_declared_methods_include_no_implicit_head_or_options`` below). An
    earlier version of this helper subtracted ``{"HEAD", "OPTIONS"}``
    defensively, which meant an explicit ``@router.head`` would have passed
    the GET-only check — the guard would have admitted the very thing it
    names (plan §2 decision 8c pins the *whole* router to GET).

    Matches by ``path.startswith(prefix)`` rather than an exact path so a new
    route added anywhere under the prefix (not just at the one path this
    module happens to define today) is caught.
    """
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
    """Negative self-check for the removed subtraction (노트 b).

    With the old ``- {"HEAD", "OPTIONS"}`` this router reported ``{"GET"}``
    and passed. It must now be visible as a violation.
    """
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

    # Independent of the app's prefix/mounting: check the router object
    # itself, so a route added to `router` would be caught even if some
    # future app wiring changed how/where it's mounted.
    router_methods = _declared_methods_under_prefix(tos_projection.router.routes, "")
    assert router_methods, "expected at least one route on tos_projection.router"
    assert router_methods == {"GET"}


def test_get_only_checker_detects_an_added_post():
    """Negative self-check: prove the checker actually catches a violation.

    Builds a throwaway router with one POST endpoint under /api/tos/... and
    runs the same `_declared_methods_under_prefix` helper against it. If this
    assertion ever stopped failing, the positive checks above would be
    vacuous — this is the same idiom as the runtime's negative-grep
    self-tests (`tests/operator/test_no_write_port.py`).
    """
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


# What this test checks: the API accepts each shared fixture and mirrors it
# back byte-for-byte. The same files are read by the UI tests
# (`strategy-builder-ui/src/test/tosFixture.ts`) and by the runtime's
# `tos/runtime/tests/operator/test_projection.py::
# test_shared_product_contract_fixture`, which substitutes the fixture's own
# groups for the projection's readers and so proves assembler pass-through
# only — it never exercises the real `_operations_wiring` readers. The
# producer's actual key set is checked separately, from the producer source,
# by `test_protective_last_verdict_matches_the_producer_key_set` below.
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


_PRODUCER_SOURCE = (
    Path(__file__).resolve().parents[3]
    / "tos/runtime/src/tos_runtime/compose/_operations_wiring.py"
)


def _producer_last_verdict_keys() -> set[str]:
    """The ``protective.last_verdict`` keys the producer literally emits.

    Read from the producer's source with ``ast`` — never imported. The
    dashboard must not import ``tos_runtime`` (reverse-import firewall, and
    it is not installed in this virtualenv), but the file is in this
    repository and the repo split removes the legacy runtime rather than
    moving ``tos/`` (CLAUDE.md "tos Kernel Boundary"), so this path is not
    allowed to go missing: a missing file fails loudly instead of skipping.
    """
    assert _PRODUCER_SOURCE.exists(), f"producer source missing: {_PRODUCER_SOURCE}"
    tree = ast.parse(_PRODUCER_SOURCE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name == "_read_protective"):
            continue
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Dict):
                continue
            for key, value in zip(inner.keys, inner.values):
                is_verdict = (
                    isinstance(key, ast.Constant)
                    and key.value == "last_verdict"
                    and isinstance(value, ast.Dict)
                )
                if is_verdict:
                    return {
                        k.value
                        for k in value.keys
                        if isinstance(k, ast.Constant) and isinstance(k.value, str)
                    }
    raise AssertionError(
        "no 'last_verdict' object literal found in _read_protective — the "
        "producer's shape changed; re-derive this DTO against it"
    )


def test_protective_last_verdict_matches_the_producer_key_set():
    """지적 1 red proof: the DTO models every key the producer emits.

    Against the pre-fix DTO (``last_verdict: str | None``) this fails on the
    first assertion, and the end-to-end test below returns
    ``available=false, reason="schema mismatch at protective.last_verdict"``.
    """
    producer_keys = _producer_last_verdict_keys()

    assert producer_keys == {
        "derestriction_admissible",
        "capacity_exhausted",
        "classification",
        "unevaluated",
        "reasons",
        "protective_classification_digest",
    }, producer_keys
    verdict_model = tos_projection._ProtectiveFacts.model_fields["last_verdict"]
    assert set(tos_projection._ProtectiveVerdict.model_fields) == producer_keys
    assert verdict_model.annotation is not str


def test_a_real_producer_protective_verdict_round_trips(monkeypatch, tmp_path):
    """The populated verdict the producer emits after a processed tick.

    Shapes mirror ``tos_runtime.safety.protective.ProtectiveVerdict``: two
    tri-state booleans, a ``ProtectiveActionOutcome.value`` string (always
    ``None`` today), two ordered token lists, and a digest string.
    """
    verdict = {
        "derestriction_admissible": False,
        "capacity_exhausted": True,
        "classification": None,
        "unevaluated": ["correction_reversal_idempotent"],
        "reasons": ["derestriction_admissible", "capacity_exhausted"],
        "protective_classification_digest": "sha256:abc123",
    }
    assert set(verdict) == _producer_last_verdict_keys()
    payload = dict(_VALID_PROJECTION, protective={"last_verdict": verdict})
    path = tmp_path / "protective.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    body = _client(monkeypatch, tmp_path, path).get("/api/tos/projection").json()

    assert body["available"] is True, body
    assert body["projection"]["protective"]["last_verdict"] == verdict


def test_an_all_none_protective_verdict_stays_all_none(monkeypatch, tmp_path):
    verdict = dict.fromkeys(_producer_last_verdict_keys())
    payload = dict(_VALID_PROJECTION, protective={"last_verdict": verdict})
    path = tmp_path / "protective-null.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    body = _client(monkeypatch, tmp_path, path).get("/api/tos/projection").json()

    assert body["available"] is True, body
    assert body["projection"]["protective"]["last_verdict"] == verdict


def test_reason_lists_keep_absent_distinct_from_empty(monkeypatch, tmp_path):
    """지적 2: ``null`` is accepted, and an absent key stays ``null``, not ``[]``.

    An empty list is a fact ("evaluated, nothing to report"); absence is not.
    Defaulting to ``[]`` would render as 「없음」 on the page.
    """
    payload = dict(
        _VALID_PROJECTION,
        recovery={"readiness_verdict": "READY", "reasons": None},
        safety_mesh={
            "snapshot_generation": None,
            "services": {
                "spg": {"clear": None, "reasons": None},
                "wdr": {"clear": True},
            },
        },
    )
    path = tmp_path / "reasons.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    body = _client(monkeypatch, tmp_path, path).get("/api/tos/projection").json()

    assert body["available"] is True, body
    assert body["projection"]["recovery"]["reasons"] is None
    services = body["projection"]["safety_mesh"]["services"]
    assert services["spg"]["reasons"] is None
    # Absent, not explicitly null — still must not become [].
    assert services["wdr"]["reasons"] is None


def test_inner_facts_may_be_null_without_losing_the_document(monkeypatch, tmp_path):
    """노트 a: the four inner fields that became nullable, all set to ``null``."""
    payload = dict(
        _VALID_PROJECTION,
        safety_mesh={"snapshot_generation": None, "services": None},
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
    assert projection["safety_mesh"]["services"] is None
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
    """지적 3: pydantic's ``str(exc)`` carries ``input_value=...``.

    The response body is polled every 15 s by a browser, so the reason
    reports the failing location and the exception type only — the same
    reduction the invalid-JSON branch already made.
    """
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
