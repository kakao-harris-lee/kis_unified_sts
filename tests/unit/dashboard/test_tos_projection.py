from __future__ import annotations

import ast
import json
import logging
import re
from pathlib import Path
from typing import get_args

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
    """Negative self-check for the removed subtraction.

    This router declares HEAD and nothing else, so the old helper's
    ``- {"HEAD", "OPTIONS"}`` reduced it to the **empty set** — which the
    GET-only assertion's own ``assert router_methods`` guard would have
    reported as "no routes registered", not as a read-only violation. Either
    way the explicit HEAD was invisible as what it is. It must now show up.
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


# The contract set, named here the way the other two readers name it: the
# runtime test parametrizes on both files and the UI loader selects between
# them. Pinning the set is what keeps the loop below from passing on zero
# matches — a glob that finds nothing iterates zero times and asserts nothing,
# so a fixture moved or renamed away from this directory would otherwise go
# silently green here while the other two readers go red. Adding a third
# fixture is a deliberate edit in all three readers, not a silent pickup.
SHARED_PROJECTION_FIXTURES = frozenset(
    {"operator-projection-v1.json", "operator-projection-v1-unknown.json"}
)


# What this test checks: the API accepts each shared fixture and mirrors it
# back byte-for-byte. The fixtures are OWNED by the producing distribution and
# live in its tree (`tos/runtime/tests/fixtures/`, review note e of #861): the
# document is produced by `tos_runtime.operator.projection`, and the planned
# repo split keeps `tos/` while removing this legacy runtime, so the readers
# point into `tos/` and never the reverse. The same files are read by the UI
# tests (`strategy-builder-ui/src/test/tosFixture.ts`) and by the runtime's
# `tos/runtime/tests/operator/test_projection.py::
# test_shared_product_contract_fixture`, which substitutes the fixture's own
# groups for the projection's readers and so proves assembler pass-through
# only — it never exercises the real `_operations_wiring` readers. The
# producer's actual key set is checked separately, from the producer source,
# by `test_protective_last_verdict_matches_the_producer_key_set` below.
# No imports cross the TOS boundary.
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
        is_reader = (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "_read_protective"
        )
        if not is_reader:
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

    The first assertion reads the producer source only, so it holds with or
    without the fix. Against the pre-fix DTO (``last_verdict: str | None``)
    this test fails where ``_ProtectiveVerdict`` is dereferenced — the class
    does not exist — and the end-to-end test below returns
    ``available=false``, ``reason="schema mismatch at protective.last_verdict:
    ValidationError"``.
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
    assert set(tos_projection._ProtectiveVerdict.model_fields) == producer_keys
    # The nested model must be what the field actually points at. `is not str`
    # would not do: `(str | None) is not str` is true, so the pre-fix
    # annotation passed that check.
    annotation = tos_projection._ProtectiveFacts.model_fields["last_verdict"].annotation
    assert tos_projection._ProtectiveVerdict in get_args(annotation), annotation
    assert type(None) in get_args(annotation), annotation


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
    """지적 2: inside a mapping the failing segment is a key from the file.

    ``operations.schema_versions`` is ``dict[str, int | None]``, so pydantic's
    raw ``loc`` ends in whatever key the file used. The location is resolved
    against the DTO and the key is replaced.
    """
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
        safety_mesh={
            "snapshot_generation": None,
            "services": {"spg": {"clear": "not-a-bool", "reasons": []}},
        },
    )
    path = tmp_path / "service-field.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    body = _client(monkeypatch, tmp_path, path).get("/api/tos/projection").json()

    assert body["available"] is False
    assert body["reason"].startswith(
        "schema mismatch at safety_mesh.services.<key>.clear"
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
    """지적 1 (2 회차): absent is the normal state outside a paper session.

    At WARNING an open tab wrote about 240 visible lines an hour for a state
    this PR's own docs call normal. INFO keeps the record without that: with
    no root handler configured (uvicorn declares only its own three
    loggers), an INFO from this module produces no output at all.
    """
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
    """The other side: a fault must stay visible.

    WARNING reaches the container's stderr through ``logging.lastResort``
    even with no handler on the root logger.
    """
    path = tmp_path / "a-directory.json"
    path.mkdir()
    body, record = _unavailable_log_record(monkeypatch, tmp_path, path, caplog)

    assert body["available"] is False
    assert record.levelno == logging.WARNING, record.levelname
    assert str(path) in record.getMessage()
    assert "cannot read projection" in record.getMessage()


def test_the_configured_root_logger_shows_warning_and_hides_info():
    """Pins the measured premise the level split rests on.

    Nothing in this app configures logging, and uvicorn's ``LOGGING_CONFIG``
    declares only ``uvicorn``/``uvicorn.error``/``uvicorn.access`` — so the
    root logger keeps no handler and level WARNING, and ``logging.lastResort``
    (stderr, WARNING) is what carries a record out.
    """
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
        # Start from a bare root, as a container does. pytest installs its own
        # root handlers, which is why this cannot be read off the live root.
        logging.root.handlers[:] = []
        logging.root.setLevel(logging.WARNING)
        logging.config.dictConfig(uvicorn.config.LOGGING_CONFIG)

        # The premise: uvicorn's config adds nothing to the root logger.
        assert logging.root.handlers == []
        assert logging.root.level == logging.WARNING
        module_logger = logging.getLogger(tos_projection.__name__)
        assert module_logger.handlers == []
        assert module_logger.propagate is True
        assert module_logger.getEffectiveLevel() == logging.WARNING

        # So a WARNING goes out through lastResort and an INFO goes nowhere.
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
    """The ``reason`` argument of an ``_unavailable`` call, positional or not.

    Requiring ``call.args`` (an earlier version of this check did) silently
    skipped every keyword-only call — the scan then counted fewer reasons and
    still passed its ``>= 5`` floor.
    """
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
    """Every reason an ``_unavailable`` call site can produce.

    The returned list has one entry per call site — no call site may be
    skipped, which is what makes this a completeness check rather than a
    sample.
    """
    tree = ast.parse(source)
    calls = _unavailable_calls(tree)
    prefixes = [_reason_prefix_of(_reason_literal(call)) for call in calls]
    assert len(prefixes) == len(calls), (len(prefixes), len(calls))
    return prefixes


def _unavailable_response_sites(source: str) -> set[str]:
    """Functions that build a ``TosProjectionResponse`` with ``available`` false.

    ``_unavailable`` is the only place allowed to: it is where the reason
    prefix and the log line live. A branch that returned the DTO directly
    would bypass the prefix set entirely, and the prefix scan above would
    never see it.
    """
    tree = ast.parse(source)
    owners: set[str] = set()
    # Both kinds: `ast.AsyncFunctionDef` is not a subclass of
    # `ast.FunctionDef`, and this route's endpoint is an `async def` — a
    # DTO built there would have been invisible to this guard.
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
            # A non-literal `available` is treated as a false path too: the
            # check cannot prove it is always true.
            if isinstance(available, ast.Constant) and available.value is True:
                continue
            owners.add(function.name)
    return owners


def test_every_emitted_reason_starts_with_a_pinned_prefix():
    """노트 f: the Python emitter and the TS matcher share one list.

    Completeness is read off the route source: every ``_unavailable(...)``
    call site's reason must begin with one of the pinned prefixes, so a new
    failure cause cannot be added without either reusing a prefix the UI
    already maps or updating the shared fixture (and with it the UI test).
    """
    prefixes = _reason_prefixes()
    emitted = _unavailable_reason_prefixes(_ROUTE_MODULE.read_text(encoding="utf-8"))

    assert len(emitted) >= 5, emitted
    for reason in emitted:
        assert any(
            reason.startswith(prefix) for prefix in prefixes
        ), f"{reason!r} matches no prefix in {_REASON_FIXTURE.name}: {prefixes}"


def test_only_unavailable_builds_an_unavailable_response():
    """The other half of completeness (지적 2, 2 회차).

    Scanning ``_unavailable`` call sites proves nothing if a branch can
    return ``TosProjectionResponse(available=False, ...)`` on its own.
    """
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

    # Keyed by value, not position: ast.walk order is not source order.
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
        while isinstance(target, tuple):  # ("dict"|"list", inner)
            target = target[1]
        if isinstance(target, type) and issubclass(target, BaseModel):
            names |= _dto_leaf_names(target)
    return names


def _ts_declared_identifiers(source: str) -> set[str]:
    """Property names declared anywhere in the TS contract file.

    Matches at a line start or after ``{``/``;``, because this file packs
    several properties onto one line — anchoring on ``^`` alone would see
    only the first of each line and report the rest as missing.
    """
    pattern = r"(?:^|[{;])\s*([A-Za-z_][A-Za-z0-9_]*)\??:"
    return set(re.findall(pattern, source, re.MULTILINE))


def test_every_dto_leaf_name_appears_in_the_ts_contract():
    """노트 c: the claim is a property, so check it as one.

    ``tos.ts`` says the Python DTO is its wire contract. The round-1 test
    backed that with four hand-listed leaves out of the DTO's full set; this
    walks the DTO instead, so a leaf added on the Python side and forgotten
    in TS fails here — in CI, which the TS suite is not (no node job).
    """
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
    """Red proof for 지적 2's residual: ``async def`` is a different node type.

    ``ast.AsyncFunctionDef`` does not subclass ``ast.FunctionDef``, and this
    route's endpoint is an ``async def`` — so a scan over ``FunctionDef``
    alone would have reported this module as clean.
    """
    assert _unavailable_response_sites(_ASYNC_RETURN_MODULE) == {
        "_unavailable",
        "get_tos_projection",
    }


def test_a_boolean_schema_version_is_rejected(monkeypatch, tmp_path):
    """노트 a: ``True != 1`` is False, so JSON ``true`` walked the version gate.

    pydantic then coerced it, and the document rendered as a valid v1
    projection. Reverting the ``type(...) is int`` clause makes this fail with
    ``available=true``.
    """
    payload = dict(_VALID_PROJECTION, schema_version=True)
    path = tmp_path / "boolean-version.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert '"schema_version": true' in path.read_text(encoding="utf-8")

    body = _client(monkeypatch, tmp_path, path).get("/api/tos/projection").json()

    assert body["available"] is False
    assert body["reason"] == "unsupported schema_version (expected 1, got bool)"
    assert body["projection"] is None
