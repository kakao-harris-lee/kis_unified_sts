"""``GET /api/tos/status`` — the read-only one-page status board."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.dashboard.routes import tos_status

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ROUTE_MODULE = _REPO_ROOT / "services" / "dashboard" / "routes" / "tos_status.py"
_REASONS_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "tos" / "status-reasons.json"

#: The shape ``tools/tos_cp3/export_status.py`` writes, as measured on the host
#: on 2026-11-25 against that day's five sessions (`sts tos status --json`, 11
#: issues, 0 blocks, the LONG tree's clean-day count at 5/5).
#: ``test_cp3_export_status.py`` builds the same shape from a recorded board, so
#: the two sides cannot drift without one of them going red.
_VALID_DOCUMENT: dict[str, Any] = {
    "schema_version": 1,
    "date": "2026-11-25",
    "generated_kst": "2026-11-25T19:22:04+09:00",
    "tenants": [
        {
            "name": "long-20261125",
            "label": "long",
            "tree_id": "cp3-setup-d-long",
            "market": "futures",
            "direction": "LONG",
            "instrument": "A05612",
            "status": "ENDED",
            "run_alive": False,
            "producer_alive": False,
            "boot_at": "08:46:08",
            "end_at": "15:50:01",
            "run_rc": 0,
            "producer_rc": 0,
            "ticks": 409,
            "issues": [
                {
                    "level": "확인",
                    "text": "MARKETFEED_PASS_OVERRUN 1행 — 최악 pass 1232ms > 창 500ms",
                }
            ],
        },
        {
            "name": "stock-r1-20261125",
            "label": "stock",
            "tree_id": "cp3-setup-d-stock-005930",
            "market": "stock",
            "direction": "LONG",
            "instrument": "005930",
            "status": "ENDED",
            "run_alive": False,
            "producer_alive": False,
            "boot_at": "09:01:12",
            "end_at": "15:35:02",
            "run_rc": 0,
            "producer_rc": 0,
            "ticks": 380,
            "issues": [],
        },
    ],
    "clean_streak": [
        {
            "label": "long",
            "days": 5,
            "target_days": 5,
            "window_days": 40,
            "met": True,
            "start": "2026-11-19",
            "window_start": "2026-11-19",
            "pending": None,
            "broke_on": None,
            "broke_reason": None,
            "calendar_version": "krx-2026.11",
            "error": None,
        }
    ],
    "paper": {
        "session": "2026-11-25-084505-LONG",
        "live_check": True,
        "runtime_alive": False,
        "driver_alive": False,
        "boot_ok": True,
        "report": {
            "verdict": "ok",
            "exit_code": 0,
            "stop_reason": "signal",
            "started_kst": "2026-11-25T08:45:05.768479+09:00",
            "ended_kst": "2026-11-25T15:45:02.223394+09:00",
            "events_consumed": 5018,
            "stale_withheld": 1,
            "stale_ratio": 0.0002,
        },
        "issues": [
            {
                "level": "확인",
                "text": "MARKETFEED_PASS_OVERRUN 5018행 — 최악 pass 2289ms",
            }
        ],
    },
    "issues": [
        {
            "level": "확인",
            "where": "long-20261125",
            "text": "MARKETFEED_PASS_OVERRUN 1행 — 최악 pass 1232ms > 창 500ms",
        },
        {
            "level": "확인",
            "where": "paper",
            "text": "MARKETFEED_PASS_OVERRUN 5018행 — 최악 pass 2289ms",
        },
    ],
    "blocked": 0,
    "checks": 2,
    "levels": {"blocked": "막힘", "check": "확인"},
}


@pytest.fixture
def document(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The container-side document path, derived from the projection env var."""
    projection = tmp_path / "mount" / "operator_projection.json"
    projection.parent.mkdir(parents=True)
    monkeypatch.setenv("TOS_OPERATOR_PROJECTION_PATH", str(projection))
    directory = projection.parent / "status"
    directory.mkdir()
    return directory / "board.json"


def _write(path: Path, payload: object) -> Path:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def client() -> TestClient:
    """A client over just this router, so the test does not depend on auth wiring."""
    app = FastAPI()
    app.include_router(tos_status.router)
    return TestClient(app)


def _get(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/tos/status")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    return response.json()


def test_a_valid_board_is_served_whole(client: TestClient, document: Path) -> None:
    """The strip's four questions, all answered from one body."""
    _write(document, _VALID_DOCUMENT)
    body = _get(client)
    assert body["available"] is True
    assert body["reason"] is None
    served = body["document"]
    assert served["date"] == "2026-11-25"
    assert [t["name"] for t in served["tenants"]] == [
        "long-20261125",
        "stock-r1-20261125",
    ]
    assert served["blocked"] == 0
    assert served["checks"] == 2
    assert served["levels"] == {"blocked": "막힘", "check": "확인"}
    assert served["clean_streak"][0]["days"] == 5
    assert served["clean_streak"][0]["target_days"] == 5
    assert served["paper"]["boot_ok"] is True
    assert served["paper"]["report"]["verdict"] == "ok"


def test_the_issue_list_keeps_its_level_and_its_where(
    client: TestClient, document: Path
) -> None:
    """레벨도 문장도 상태판이 쓴 그대로다 — 웹에서 다시 판정하지 않는다."""
    _write(document, _VALID_DOCUMENT)
    issues = _get(client)["document"]["issues"]
    assert [issue["where"] for issue in issues] == ["long-20261125", "paper"]
    assert all(issue["level"] == "확인" for issue in issues)
    assert issues[0]["text"].startswith("MARKETFEED_PASS_OVERRUN")


def test_a_streak_that_could_not_be_counted_is_an_error_not_a_zero(
    client: TestClient, document: Path
) -> None:
    """셀 수 없는 누적은 ``error`` 다. 0 으로 그리면 «오늘까지 하나도 없다» 가 된다."""
    payload = json.loads(json.dumps(_VALID_DOCUMENT))
    payload["clean_streak"] = [
        {"label": "long", "days": None, "error": "FileNotFoundError"}
    ]
    _write(document, payload)
    streak = _get(client)["document"]["clean_streak"][0]
    assert streak["days"] is None
    assert streak["error"] == "FileNotFoundError"


def test_no_host_path_digest_or_commit_is_declared_on_the_dtos() -> None:
    """내보내기가 떼는 것들은 DTO 에 **이름조차 없다** — ``extra='ignore'`` 가 떨군다.

    이 페이지는 Cloudflare Access 뒤에서 인터넷에 열려 있고 앱 자체 인증이 없다.
    상태판 JSON 은 ``state_dir`` · 달력 경로 · ``expected_code_digest`` ·
    ``band_digest`` · ``repo_commit`` 을 들고 있으므로, 한 쪽이라도 DTO 에 다시
    선언되는 순간 조용히 브라우저로 나간다.
    """
    forbidden = {
        "state_dir",
        "calendar",
        "expected_code_digest",
        "band_digest",
        "repo_commit",
        "bootproof",
        "worktree_commit",
        "path",
    }
    seen: set[str] = set()

    def walk(model: type) -> None:
        for name, field in model.model_fields.items():
            seen.add(name)
            annotation = field.annotation
            for candidate in getattr(annotation, "__args__", ()) or ():
                inner = getattr(candidate, "__args__", (candidate,))[0]
                if isinstance(inner, type) and hasattr(inner, "model_fields"):
                    walk(inner)

    walk(tos_status.TosStatusDocument)
    assert seen & forbidden == set(), sorted(seen & forbidden)


def test_a_document_carrying_a_host_path_anyway_never_echoes_it(
    client: TestClient, document: Path
) -> None:
    """DTO 가 모르는 키는 몸통에 **안 실린다** — 문서가 들고 와도."""
    payload = json.loads(json.dumps(_VALID_DOCUMENT))
    payload["state_dir"] = "/home/deploy/.local/state/tos"
    payload["clean_streak"][0]["calendar"] = "/home/deploy/project/x/calendar.yaml"
    payload["tenants"][0]["expected_code_digest"] = "f" * 64
    _write(document, payload)

    body = json.dumps(_get(client), ensure_ascii=False)
    assert "/home/deploy" not in body
    assert "f" * 64 not in body


_REDACTION_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "tos" / "redaction-cases.json"


def _redaction_cases() -> dict[str, Any]:
    return json.loads(_REDACTION_FIXTURE.read_text(encoding="utf-8"))


def test_a_hand_written_document_carrying_a_path_does_not_pass_through(
    client: TestClient, document: Path
) -> None:
    """웹 계층은 내보내기가 옳았다는 가정 위에 서지 않는다.

    #1179: 내보내기가 지우기 전에는 러너의 ABORT 문장이 그대로 이 라우트를 타고
    브라우저까지 갔다. 내보내기를 고쳤지만, 그것이 **다시 틀렸을 때** 아무도
    눈치채지 못하는 구조는 그대로 두지 않는다.
    """
    payload = json.loads(json.dumps(_VALID_DOCUMENT))
    payload["issues"].append(
        {
            "level": "막힘",
            "where": "long-20261125",
            "text": "ABORT: cannot create data leaf "
            "/home/deploy/.local/state/tos/cp3-setup-d-long-data/A05612",
        }
    )
    payload["clean_streak"][0][
        "error"
    ] = "FileNotFoundError: '/home/deploy/project/x/calendar.yaml'"
    payload["tenants"][0]["issues"].append(
        {"level": "막힘", "text": "see ~/.local/state/tos/cp3-long.log"}
    )
    _write(document, payload)

    body = _get(client)
    assert body["available"] is True
    assert body["redacted"] is True
    rendered = json.dumps(body, ensure_ascii=False)
    for needle in ("/home", "/tmp", "~/", "state/tos"):
        assert needle not in rendered, needle
    # …사유는 남는다. 지우는 것이 숨기는 것이 되면 안 된다.
    assert "cannot create data leaf" in rendered
    assert "FileNotFoundError" in rendered


def test_an_account_shaped_value_does_not_pass_through(
    client: TestClient, document: Path
) -> None:
    payload = json.loads(json.dumps(_VALID_DOCUMENT))
    payload["issues"].append(
        {
            "level": "막힘",
            "where": "paper",
            "text": "INVALID_CHECK_ACNO 5020591501 / 12345678-01",
        }
    )
    _write(document, payload)
    body = _get(client)
    assert body["redacted"] is True
    rendered = json.dumps(body, ensure_ascii=False)
    assert "5020591501" not in rendered
    assert "12345678-01" not in rendered
    assert "INVALID_CHECK_ACNO" in rendered


def test_a_clean_document_is_not_reported_as_redacted(
    client: TestClient, document: Path
) -> None:
    """``redacted`` 가 늘 참이면 운영자가 그 신호를 읽지 않게 된다."""
    _write(document, _VALID_DOCUMENT)
    body = _get(client)
    assert body["available"] is True
    assert body["redacted"] is False
    # 멀쩡한 문장은 글자 그대로 남는다.
    assert body["document"]["issues"][0]["text"].startswith("MARKETFEED_PASS_OVERRUN")


def test_the_reader_agrees_with_the_exporter_on_every_shared_case(
    client: TestClient, document: Path
) -> None:
    """구현이 둘이라(``services/`` 는 ``tools/`` 를 import 못 한다) 표를 공유한다.

    두 쪽이 갈라지면 화면에 두 가지 «지움» 이 생기거나, 한쪽만 새기 시작한다.
    """
    cases = _redaction_cases()
    for case in cases["redacted"]:
        payload = json.loads(json.dumps(_VALID_DOCUMENT))
        payload["issues"] = [{"level": "확인", "where": "x", "text": case["input"]}]
        _write(document, payload)
        body = _get(client)
        assert body["redacted"] is True, case["why"]
        assert body["document"]["issues"][0]["text"] == case["expected"], case["why"]

    for case in cases["kept"]:
        payload = json.loads(json.dumps(_VALID_DOCUMENT))
        payload["issues"] = [{"level": "확인", "where": "x", "text": case["input"]}]
        _write(document, payload)
        body = _get(client)
        assert body["document"]["issues"][0]["text"] == case["input"], case["why"]
        assert body["redacted"] is False, case["why"]


def test_a_redacted_document_is_logged_so_the_exporter_bug_is_visible(
    client: TestClient, document: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """조용히 고쳐 주면 내보내기 버그가 영원히 안 보인다."""
    payload = json.loads(json.dumps(_VALID_DOCUMENT))
    payload["issues"] = [{"level": "막힘", "where": "x", "text": "/home/deploy/x"}]
    _write(document, payload)
    with caplog.at_level(logging.INFO, logger=tos_status.logger.name):
        _get(client)
    assert any(record.levelno == logging.WARNING for record in caplog.records)


def test_a_missing_document_is_unavailable_not_an_error(
    client: TestClient, document: Path
) -> None:
    """내보내기 전은 **정상 상태**다 — 5xx 로 보이면 안 된다(OBS-INV-003)."""
    assert not document.exists()
    body = _get(client)
    assert body["available"] is False
    assert body["reason"] == "status document absent"
    assert body["document"] is None


def test_an_unreadable_document_names_permissions_not_the_exporter(
    client: TestClient, document: Path
) -> None:
    """0700 마운트·uid 어긋남은 형식 문제가 아니다 — 운영자를 권한으로 보낸다."""
    _write(document, _VALID_DOCUMENT)
    document.chmod(0o000)
    try:
        body = _get(client)
    finally:
        document.chmod(0o600)
    assert body["available"] is False
    assert body["reason"] == "cannot read status document: PermissionError"


def test_invalid_json_is_reported_by_type_never_by_content(
    client: TestClient, document: Path
) -> None:
    """사유에 파일 조각이 실리면 안 된다 — 그 몸통은 브라우저로 간다."""
    _write(document, '{"schema_version": 1, "date": "SENTINEL-' + "x" * 200)
    body = _get(client)
    assert body["available"] is False
    assert body["reason"] == "invalid json: JSONDecodeError"
    assert "SENTINEL" not in json.dumps(body)


def test_an_unsupported_version_reports_the_type_never_the_value(
    client: TestClient, document: Path
) -> None:
    """``schema_version`` 도 파일에서 읽은 값이다 — 그대로 되비추지 않는다."""
    _write(document, dict(_VALID_DOCUMENT, schema_version="SENTINEL-" + "x" * 200))
    body = _get(client)
    assert body["available"] is False
    assert body["reason"] == "unsupported schema_version (expected 1, got str)"
    assert "SENTINEL" not in json.dumps(body)


def test_a_json_true_version_is_not_mistaken_for_one(
    client: TestClient, document: Path
) -> None:
    """``True == 1`` 이므로 ``type(...) is int`` 로 거른다."""
    _write(document, dict(_VALID_DOCUMENT, schema_version=True))
    body = _get(client)
    assert body["available"] is False
    assert body["reason"] == "unsupported schema_version (expected 1, got bool)"


def test_a_schema_mismatch_reports_the_exception_type_only(
    client: TestClient, document: Path
) -> None:
    """pydantic 의 ``str(exc)`` 는 ``input_value=…`` 로 파일 조각을 담는다."""
    _write(document, dict(_VALID_DOCUMENT, tenants="SENTINEL-" + "x" * 200))
    body = _get(client)
    assert body["available"] is False
    assert body["reason"].startswith("schema mismatch: ")
    assert "SENTINEL" not in json.dumps(body)


def test_a_top_level_array_is_invalid_json_not_a_crash(
    client: TestClient, document: Path
) -> None:
    _write(document, [1, 2, 3])
    body = _get(client)
    assert body["available"] is False
    assert body["reason"] == "invalid json: top-level value is not an object"


def _reason_prefixes() -> list[str]:
    payload = json.loads(_REASONS_FIXTURE.read_text(encoding="utf-8"))
    return [entry["prefix"] for entry in payload["reasons"]]


def test_every_pinned_reason_prefix_is_actually_reachable(
    client: TestClient, document: Path
) -> None:
    """픽스처는 UI 의 분기표이기도 하다 — 닿지 못하는 접두는 죽은 분기를 만든다."""
    observed: set[str] = set()

    observed.add(_get(client)["reason"])  # absent

    _write(document, "{not json")
    observed.add(_get(client)["reason"])

    _write(document, dict(_VALID_DOCUMENT, schema_version=2))
    observed.add(_get(client)["reason"])

    _write(document, dict(_VALID_DOCUMENT, tenants=5))
    observed.add(_get(client)["reason"])

    _write(document, _VALID_DOCUMENT)
    document.chmod(0o000)
    try:
        observed.add(_get(client)["reason"])
    finally:
        document.chmod(0o600)

    for prefix in _reason_prefixes():
        assert any(
            reason.startswith(prefix) for reason in observed if reason
        ), f"no observed reason starts with {prefix!r}: {sorted(observed)}"


def test_the_route_imports_nothing_from_tos() -> None:
    """The reverse firewall, restated where a reader of this suite sees it."""
    for line in _ROUTE_MODULE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        assert not stripped.startswith(("import tos", "from tos ")), line
        assert not stripped.startswith(("import tos_runtime", "from tos_runtime")), line
        assert not stripped.startswith("from tos."), line


def test_an_absent_document_logs_at_info_and_a_fault_at_warning(
    client: TestClient, document: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """No export yet is normal; an unreadable document is not."""
    with caplog.at_level(logging.INFO, logger=tos_status.logger.name):
        _get(client)
    assert [record.levelno for record in caplog.records] == [logging.INFO]

    caplog.clear()
    _write(document, "{not json")
    with caplog.at_level(logging.INFO, logger=tos_status.logger.name):
        _get(client)
    assert [record.levelno for record in caplog.records] == [logging.WARNING]


def test_the_route_is_registered_on_the_app() -> None:
    """A router nobody includes is a read model nobody can read."""
    from services.dashboard.app import create_app

    paths = {route.path for route in create_app().routes}  # type: ignore[attr-defined]
    assert "/api/tos/status" in paths


def test_the_document_lives_beside_the_other_exports(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """네 reader 가 한 env var 에서 나온다 — 서로 다른 mount 로 갈라질 수 없다."""
    from services.dashboard.routes import tos_bars

    projection = tmp_path / "mount" / "operator_projection.json"
    monkeypatch.setenv("TOS_OPERATOR_PROJECTION_PATH", str(projection))
    assert tos_status._document_path().parent.parent == tos_bars._bars_dir().parent
    assert tos_status._document_path() == projection.parent / "status" / "board.json"
