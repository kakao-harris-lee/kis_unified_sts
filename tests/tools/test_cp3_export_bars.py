"""``tools/tos_cp3/export_bars.py`` — the host side of the ``/tos`` bar panel."""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from tools.tos_cp3 import export_bars as eb
from tools.tos_cp3 import inspect_session as ins

SESSION = "stock-r1-20261110"

_DOCUMENT: dict[str, Any] = {
    "session": SESSION,
    "instrument": "005930",
    "bars": [{"time_kst": "09:00", "flags": "--W-"}],
    "summary": {"bars": 1, "counted_bars": 0, "withheld_bars": 1},
}


def _runner_emitting(
    document: object, *, exit_code: int = 0, stderr: str = ""
) -> ins.Runner:
    """A run callable that returns ``document`` as the child's stdout."""

    def runner(argv: Sequence[str], env: Mapping[str, str]) -> ins.InspectRun:
        text = document if isinstance(document, str) else json.dumps(document)
        return ins.InspectRun(stdout=text, stderr=stderr, exit_code=exit_code)

    return runner


def _stub_child(monkeypatch: pytest.MonkeyPatch, document: object) -> None:
    """Make the CLI path run without a process, by replacing ``run`` itself."""
    real_run = ins.run

    def run(**kwargs: Any) -> ins.InspectRun:
        kwargs["runner"] = _runner_emitting(document)
        return real_run(**kwargs)

    monkeypatch.setattr(ins, "run", run)


@pytest.fixture
def session_tree(tmp_path: Path) -> Path:
    """A state root the resolver accepts, so only the export is under test."""
    state = tmp_path / "state"
    session = state / "cp3-sessions" / SESSION
    render = session / "render"
    (render / "strategies").mkdir(parents=True)
    (session / "journal.jsonl").write_text("{}\n", encoding="utf-8")
    (render / ins.RENDERED_MANIFEST_NAME).write_text(
        json.dumps({"instrument": "005930", "tree_id": "cp3-setup-d-stock-005930"}),
        encoding="utf-8",
    )
    (render / ins.STRATEGY_BINDINGS_FILE_NAME).write_text(
        "strategies: {}\n", encoding="utf-8"
    )
    (render / "strategies" / "d.strategy.yaml").write_text(
        "policy: {}\n", encoding="utf-8"
    )
    (state / "cp3-setup-d-stock-005930-data" / "005930").mkdir(parents=True)
    return state


def _export(
    tmp_path: Path,
    session_tree: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    document: object = None,
    out_dir: Path | None = None,
    exit_code: int = 0,
    stderr: str = "",
) -> Path:
    """Export with the inspection stubbed, returning the written path."""
    del monkeypatch
    return eb.export_bars(
        SESSION,
        out_dir=tmp_path / "projection" if out_dir is None else out_dir,
        state_dir=str(session_tree),
        runner=_runner_emitting(
            _DOCUMENT if document is None else document,
            exit_code=exit_code,
            stderr=stderr,
        ),
    )


def test_the_document_lands_where_the_container_looks(
    tmp_path: Path, session_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``<projection dir>/bars/<session>.json`` — the route's own join."""
    path = _export(tmp_path, session_tree, monkeypatch)
    assert path == tmp_path / "projection" / eb.BARS_SUBDIR / f"{SESSION}.json"
    assert path.is_file()
    assert eb.document_path(tmp_path / "projection", SESSION) == path


def test_the_filename_comes_from_the_document_not_the_argument(
    tmp_path: Path, session_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The route asks by the session's own name, so that is what names the file."""
    path = _export(
        tmp_path,
        session_tree,
        monkeypatch,
        document={**_DOCUMENT, "session": "long-20261110"},
    )
    assert path.name == "long-20261110.json"


def test_the_modes_match_the_projection_file_the_container_already_reads(
    tmp_path: Path, session_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``0700`` directory, ``0600`` document — no new exposure on this mount."""
    path = _export(tmp_path, session_tree, monkeypatch)
    assert stat.S_IMODE(path.stat().st_mode) == eb.DOCUMENT_MODE == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == eb.DIR_MODE == 0o700


def test_an_unset_destination_refuses_rather_than_guessing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A document nobody mounts looks exactly like no document at all."""
    monkeypatch.delenv(eb.PROJECTION_DIR_ENV, raising=False)
    with pytest.raises(eb.ExportRefusal, match=eb.PROJECTION_DIR_ENV):
        eb.default_out_dir()


def test_the_destination_comes_from_the_projection_env_var(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The same variable the compose file pairs with the container's path."""
    monkeypatch.setenv(eb.PROJECTION_DIR_ENV, str(tmp_path / "p"))
    assert eb.default_out_dir() == tmp_path / "p"


def test_a_tilde_or_var_in_the_destination_is_expanded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``.env.paper`` writes an absolute path, but a ``~`` must not become a directory."""
    monkeypatch.setenv(eb.PROJECTION_DIR_ENV, "~/x")
    assert eb.default_out_dir() == Path.home() / "x"


def test_the_write_is_atomic_and_leaves_no_temp_file(
    tmp_path: Path, session_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A reader must never see a half-written document."""
    path = _export(tmp_path, session_tree, monkeypatch)
    siblings = sorted(entry.name for entry in path.parent.iterdir())
    assert siblings == [f"{SESSION}.json"]


def test_a_re_export_replaces_the_document_in_place(
    tmp_path: Path, session_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second export is the one the page then reads, with no leftovers."""
    first = _export(tmp_path, session_tree, monkeypatch)
    assert json.loads(first.read_text(encoding="utf-8"))["instrument"] == "005930"
    second = _export(
        tmp_path,
        session_tree,
        monkeypatch,
        document={**_DOCUMENT, "instrument": "101S6000"},
    )
    assert second == first
    assert json.loads(second.read_text(encoding="utf-8"))["instrument"] == "101S6000"
    assert sorted(entry.name for entry in first.parent.iterdir()) == [f"{SESSION}.json"]


def test_the_schema_version_is_stamped_on_the_document(
    tmp_path: Path, session_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The route checks it first, so an older document is refused, not guessed."""
    path = _export(tmp_path, session_tree, monkeypatch)
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["schema_version"] == eb.BARS_SCHEMA_VERSION == 1
    assert written["summary"] == _DOCUMENT["summary"]
    assert written["bars"] == _DOCUMENT["bars"]


def test_the_document_is_newline_terminated_utf8(
    tmp_path: Path, session_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A text artifact an operator may `tail`, not a stream of bytes."""
    path = _export(tmp_path, session_tree, monkeypatch)
    assert path.read_text(encoding="utf-8").endswith("}\n")


def test_a_refusing_inspection_refuses_the_export_and_carries_its_message(
    tmp_path: Path, session_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Writing a document for an inspection that failed would publish a lie."""
    with pytest.raises(eb.ExportRefusal, match="inspect refused: no such"):
        _export(
            tmp_path,
            session_tree,
            monkeypatch,
            document="",
            exit_code=2,
            stderr="inspect refused: no such session directory\n",
        )
    assert not (tmp_path / "projection" / eb.BARS_SUBDIR).exists()


@pytest.mark.parametrize(
    ("document", "match"),
    [
        ("{not json", "invalid JSON"),
        ([1, 2], "not a JSON object"),
        ({"bars": []}, "names no session"),
        ({"session": "", "bars": []}, "names no session"),
    ],
)
def test_an_unusable_inspection_document_refuses(
    tmp_path: Path,
    session_tree: Path,
    monkeypatch: pytest.MonkeyPatch,
    document: object,
    match: str,
) -> None:
    """Each shape the inspection could emit that has no filename or no content."""
    with pytest.raises(eb.ExportRefusal, match=match):
        _export(tmp_path, session_tree, monkeypatch, document=document)


def test_an_unwritable_destination_refuses_by_name(
    tmp_path: Path, session_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A read-only destination is an operator fact, not a traceback."""
    destination = tmp_path / "locked"
    destination.mkdir(mode=0o500)
    try:
        with pytest.raises(eb.ExportRefusal, match="cannot write the bars document"):
            _export(tmp_path, session_tree, monkeypatch, out_dir=destination)
    finally:
        destination.chmod(0o700)


def test_the_cli_reports_the_path_and_exits_zero(
    tmp_path: Path,
    session_tree: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The operator backfill path: one session, one line of output."""
    _stub_child(monkeypatch, _DOCUMENT)
    code = eb.main(
        [
            SESSION,
            "--out-dir",
            str(tmp_path / "projection"),
            "--state-dir",
            str(session_tree),
        ]
    )
    assert code == 0
    assert "bars" in capsys.readouterr().out


def test_the_cli_exits_two_on_a_refusal_with_the_message_on_stderr(
    tmp_path: Path,
    session_tree: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Non-zero so a caller (cron, the runner hook) can see it failed."""
    monkeypatch.delenv(eb.PROJECTION_DIR_ENV, raising=False)
    _stub_child(monkeypatch, _DOCUMENT)
    code = eb.main([SESSION, "--state-dir", str(session_tree)])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err.startswith("export-bars refused: ")


def test_the_exporter_imports_nothing_from_tos() -> None:
    """``tools/tos_firewall_check.py`` is the gate; this is a fast local echo."""
    source = (eb.REPO_ROOT / "tools" / "tos_cp3" / "export_bars.py").read_text(
        encoding="utf-8"
    )
    for line in source.splitlines():
        stripped = line.strip()
        assert not stripped.startswith(("import tos", "from tos ")), line
        assert not stripped.startswith(("import tos_runtime", "from tos_runtime")), line
        assert not stripped.startswith("from tos."), line


def test_the_exported_name_is_one_the_route_will_accept() -> None:
    """The two sides agree on the filename, or the page asks for a file that exists"""
    from services.dashboard.routes import tos_bars

    for name in (SESSION, "long-20261015", "short-20261110", "stock-r1-20261111"):
        assert tos_bars._SESSION_ID_PATTERN.match(name), name
    assert eb.document_path(Path("/p"), SESSION).name == f"{SESSION}.json"
    assert os.sep not in SESSION


def test_both_directories_end_up_narrow_not_just_the_leaf(
    tmp_path: Path, session_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``mkdir(mode=…)`` narrows only the leaf it creates; the parent got the default."""
    path = _export(tmp_path, session_tree, monkeypatch)
    assert stat.S_IMODE(path.parent.stat().st_mode) == eb.DIR_MODE
    assert stat.S_IMODE(path.parent.parent.stat().st_mode) == eb.DIR_MODE


@pytest.mark.parametrize("existing", [0o755, 0o777, 0o750])
def test_a_wider_existing_directory_is_repaired(
    tmp_path: Path,
    session_tree: Path,
    monkeypatch: pytest.MonkeyPatch,
    existing: int,
) -> None:
    """A ``bars/`` left world-readable by a restore or a hand-made mkdir is narrowed."""
    projection = tmp_path / "projection"
    (projection / eb.BARS_SUBDIR).mkdir(parents=True)
    (projection / eb.BARS_SUBDIR).chmod(existing)
    projection.chmod(existing)
    path = _export(tmp_path, session_tree, monkeypatch, out_dir=projection)
    assert stat.S_IMODE(path.parent.stat().st_mode) == eb.DIR_MODE
    assert stat.S_IMODE(projection.stat().st_mode) == eb.DIR_MODE


def test_a_narrower_existing_directory_is_left_alone(
    tmp_path: Path, session_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The repair only ever NARROWS — it must not grant itself write access."""
    destination = tmp_path / "readonly"
    destination.mkdir(mode=0o500)
    try:
        with pytest.raises(eb.ExportRefusal, match="cannot write the bars document"):
            _export(tmp_path, session_tree, monkeypatch, out_dir=destination)
        assert stat.S_IMODE(destination.stat().st_mode) == 0o500
    finally:
        destination.chmod(0o700)


def test_the_mode_holds_under_a_permissive_umask(
    tmp_path: Path, session_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The mode is asserted with chmod, so the process umask cannot widen it."""
    previous = os.umask(0o000)
    try:
        path = _export(tmp_path, session_tree, monkeypatch)
    finally:
        os.umask(previous)
    assert stat.S_IMODE(path.parent.stat().st_mode) == eb.DIR_MODE
    assert stat.S_IMODE(path.parent.parent.stat().st_mode) == eb.DIR_MODE
    assert stat.S_IMODE(path.stat().st_mode) == eb.DOCUMENT_MODE


@pytest.mark.parametrize(
    "name",
    [
        "../escape",
        "a/b",
        "has space",
        "dot.dot",
        "-leading",
        "a" * 65,
        "semi;colon",
        "\u0000null",
    ],
)
def test_a_session_name_outside_the_route_pattern_refuses_before_writing(
    tmp_path: Path,
    session_tree: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
) -> None:
    """The name is this document's FILENAME and the route's path segment."""
    with pytest.raises(eb.ExportRefusal, match="which is outside"):
        _export(
            tmp_path, session_tree, monkeypatch, document={**_DOCUMENT, "session": name}
        )
    assert not (tmp_path / "projection").exists()


def test_the_pattern_admits_the_names_the_runner_really_writes(
    tmp_path: Path, session_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard must not refuse a real session."""
    for name in ("stock-r1-20261110", "long-20261015", "short-20261110"):
        path = _export(
            tmp_path, session_tree, monkeypatch, document={**_DOCUMENT, "session": name}
        )
        assert path.name == f"{name}.json"


# --------------------------------------------------------------------------- #
# The explanation blocks — legibility plan §6 P2, items four and five
# --------------------------------------------------------------------------- #

_STRATEGY_YAML = """
policy:
  rules:
    - all_of:
        - left: {ref: [capsule, resolved_values, entry_window]}
          op: EQ
          right: {const: true}
      decision:
        kind: ACTION
        rationale: "R1-ENTRY-LONG: the entry window is open."
    - all_of:
        - left: {ref: [capsule, resolved_values, vwap_reverted]}
          op: EQ
          right: {const: true}
      decision:
        kind: FLAT
        rationale: "R2-EXIT-VWAP-REVERTED: price is back in the band."
  default:
    kind: NO_ACTION
    rationale: "R0-DEFAULT-NO-ACTION: no rule fired."
"""

_FIELDS_YAML = """
fields:
  - {name: close, op: bar.close}
  - {name: mso, op: session.minutes_since_open}
  - {name: entry_window, op: between, inputs: [mso], params: {lo: 15, hi: 345}}
  - {name: vwap_reverted, op: le, inputs: [close], params: {const: 0.2}}
publish:
  - {field: close, as: close_x100, scale: {mult: 100, round: half_up}}
  - {field: entry_window, as: entry_window}
  - {field: vwap_reverted, as: vwap_reverted}
"""

_CONSTRUCTION_YAML = 'price_field_key: "close_x100"\n'


def _tenant_content(
    session_tree: Path, *, market: str, direction: str = "LONG"
) -> None:
    """Give the stub session the tenant files the explanation reads."""
    render = session_tree / "cp3-sessions" / SESSION / "render"
    (render / "strategies" / "d.strategy.yaml").write_text(
        _STRATEGY_YAML, encoding="utf-8"
    )
    (render / "fields.yaml").write_text(_FIELDS_YAML, encoding="utf-8")
    (render / "construction.yaml").write_text(_CONSTRUCTION_YAML, encoding="utf-8")
    (render / "RENDER.yaml").write_text(
        f'tree_id: "t"\nmarket: "{market}"\ndirection:\n  value: "{direction}"\n',
        encoding="utf-8",
    )


def _exported(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_each_rules_own_sentence_rides_along_with_the_bars(
    tmp_path: Path, session_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """식별자 대신 문장을 — 그 세션이 실제로 쓴 트리에서 읽어서."""
    _tenant_content(session_tree, market="stock")
    document = _exported(_export(tmp_path, session_tree, monkeypatch))

    explain = document["explain"]
    assert document.get("explain_error") is None
    assert [rule["rule_id"] for rule in explain["rules"]] == [
        "R1-ENTRY-LONG",
        "R2-EXIT-VWAP-REVERTED",
    ]
    assert explain["rules"][0]["rationale"].endswith("the entry window is open.")
    assert explain["rules"][0]["fields"] == ["entry_window"]
    assert explain["default"]["rule_id"] == "R0-DEFAULT-NO-ACTION"
    # The field the rule reads, and the one THAT field stands on.
    assert explain["fields"]["entry_window"]["op"] == "between"
    assert explain["fields"]["mso"]["op"] == "session.minutes_since_open"


def test_a_tenant_tree_it_cannot_read_costs_the_explanation_not_the_bars(
    tmp_path: Path, session_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """설명이 없어도 바 문서는 나간다 — 페이지가 못 하는 건 바가 없을 때다.

    ``session_tree`` 는 ``fields.yaml`` 을 갖고 있지 않다(기본 상태). 그래도
    문서는 쓰이고, 왜 설명이 없는지를 문서가 스스로 말한다.
    """
    path = _export(tmp_path, session_tree, monkeypatch)
    document = _exported(path)
    assert document["bars"] == _DOCUMENT["bars"]
    assert document["explain"] is None
    assert "fields.yaml" in document["explain_error"]
    assert document.get("hypothetical_pnl") is None


def test_a_stock_tenant_gets_no_hypothetical_pnl(
    tmp_path: Path, session_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """실제로 거래하는 tenant 에 «또 하나의 손익» 을 두면 잘못 읽힌다."""
    _tenant_content(session_tree, market="stock")
    document = _exported(_export(tmp_path, session_tree, monkeypatch))
    assert document["market"] == "stock"
    assert document["decision_only"] is False
    assert "hypothetical_pnl" not in document


def test_a_decision_only_tenant_gets_one_built_from_its_own_contract(
    tmp_path: Path, session_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """배수는 설정에서, 가격 필드와 배율은 그 tenant 의 렌더 트리에서 읽는다."""
    _tenant_content(session_tree, market="futures")
    bars = [
        {
            "time_kst": "09:14",
            "decision_kind": "ACTION",
            "decision_rule_id": "R1-ENTRY-LONG",
            "counted": True,
            "fields": {"close_x100": 73_564},
        },
        {
            "time_kst": "09:50",
            "decision_kind": "FLAT",
            "decision_rule_id": "R2-EXIT-VWAP-REVERTED",
            "counted": True,
            "fields": {"close_x100": 73_858},
        },
    ]
    document = _exported(
        _export(
            tmp_path,
            session_tree,
            monkeypatch,
            document={**_DOCUMENT, "instrument": "A05612", "bars": bars},
        )
    )
    block = document["hypothetical_pnl"]
    assert document["decision_only"] is True
    assert block["hypothetical"] is True
    assert block["direction"] == "LONG"
    assert block["contract"] == "kospi200_mini"
    assert block["multiplier_krw_per_point"] == 50_000
    assert block["price_field"] == "close_x100"
    assert block["price_scale"] == 100
    assert block["totals"]["hypothetical_pnl_krw"] == "147000"
    assert "FILL_AT_DECISION_BAR_CLOSE" in block["assumptions"]


def test_a_short_tenants_block_is_the_mirror_of_the_longs(
    tmp_path: Path, session_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """방향은 렌더 매니페스트가 말한다 — LONG 으로 떨어지면 SHORT 성적이 뒤집힌다."""
    _tenant_content(session_tree, market="futures", direction="SHORT")
    bars = [
        {
            "time_kst": "09:14",
            "decision_kind": "ACTION",
            "decision_rule_id": "R1-ENTRY-SHORT",
            "counted": True,
            "fields": {"close_x100": 73_564},
        },
        {
            "time_kst": "09:50",
            "decision_kind": "FLAT",
            "decision_rule_id": "R2-EXIT-VWAP-REVERTED",
            "counted": True,
            "fields": {"close_x100": 73_858},
        },
    ]
    document = _exported(
        _export(
            tmp_path,
            session_tree,
            monkeypatch,
            document={**_DOCUMENT, "instrument": "A05612", "bars": bars},
        )
    )
    block = document["hypothetical_pnl"]
    assert block["direction"] == "SHORT"
    assert block["totals"]["hypothetical_pnl_krw"] == "-147000"


def test_a_contract_the_registry_does_not_know_is_named_not_guessed(
    tmp_path: Path, session_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """모르는 월물에 배수를 추측해 붙이면 그 수는 조용히 틀린다."""
    _tenant_content(session_tree, market="futures")
    document = _exported(
        _export(
            tmp_path,
            session_tree,
            monkeypatch,
            document={**_DOCUMENT, "instrument": "ZZZ999"},
        )
    )
    assert document["hypothetical_pnl"] is None
    assert document["hypothetical_pnl_error"] == "ValueError"
    # …and the explanation, which does not need the contract, is still there.
    assert document["explain"]["rules"]


def test_a_probe_rule_the_explanation_marks_is_the_one_the_total_skips(
    tmp_path: Path, session_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """화면이 «시험 진입» 이라 그린 규칙과 합계가 뺀 규칙이 **같아야** 한다.

    둘이 갈라지면 운영자가 보는 표시와 숫자가 서로 다른 말을 한다. 그래서 설명
    블록이 이미 낸 `probe` 플래그를 그대로 필터로 쓴다.
    """
    _tenant_content(session_tree, market="futures")
    render = session_tree / "cp3-sessions" / SESSION / "render"
    probing = _STRATEGY_YAML.replace(
        '"R1-ENTRY-LONG: the entry window is open."',
        '"R4-M2-PROBE-ENTRY-LONG: the M2 boundary probe."',
    )
    (render / "strategies" / "d.strategy.yaml").write_text(probing, encoding="utf-8")
    bars = [
        {
            "time_kst": "09:14",
            "decision_kind": "ACTION",
            "decision_rule_id": "R4-M2-PROBE-ENTRY-LONG",
            "counted": True,
            "fields": {"close_x100": 73_564},
        },
        {
            "time_kst": "09:50",
            "decision_kind": "FLAT",
            "decision_rule_id": "R2-EXIT-VWAP-REVERTED",
            "counted": True,
            "fields": {"close_x100": 73_858},
        },
    ]
    document = _exported(
        _export(
            tmp_path,
            session_tree,
            monkeypatch,
            document={**_DOCUMENT, "instrument": "A05612", "bars": bars},
        )
    )
    marked = [r["rule_id"] for r in document["explain"]["rules"] if r["probe"]]
    assert marked == ["R4-M2-PROBE-ENTRY-LONG"]

    block = document["hypothetical_pnl"]
    assert block["trades"] == []
    assert block["totals"]["hypothetical_pnl_krw"] is None
    assert [s["reason"] for s in block["skipped_decisions"]] == ["PROBE_ENTRY"]


def test_a_contract_spec_file_that_cannot_be_loaded_degrades_the_block(
    tmp_path: Path, session_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``ContractSpecRegistry.from_yaml`` 의 ``TypeError`` 가 수출을 죽이면 안 된다.

    그 생성자는 YAML 매핑을 ``**fields`` 로 펼치므로, `config/execution.yaml` 에
    키 하나가 늘거나 이름이 바뀌면 ``TypeError`` 다. 설명 블록 때문에 바를 잃는
    것은 이 설계가 명시적으로 피한 것이다.
    """
    _tenant_content(session_tree, market="futures")
    spec = tmp_path / "execution.yaml"
    spec.write_text(
        "futures_contract_spec:\n"
        "  kospi200_mini:\n"
        "    multiplier_krw_per_point: 50000\n"
        "    tick_size_points: 0.02\n"
        "    tick_value_krw: 1000\n"
        "    commission_rate: 0.00003\n"
        "    symbol_prefix: 'A05'\n"
        "    a_key_nobody_declared: 1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(eb, "CONTRACT_SPEC_CONFIG", spec)
    document = _exported(
        _export(
            tmp_path,
            session_tree,
            monkeypatch,
            document={**_DOCUMENT, "instrument": "A05612"},
        )
    )
    assert document["bars"] == _DOCUMENT["bars"]
    assert document["hypothetical_pnl"] is None
    assert document["hypothetical_pnl_error"] == "TypeError"


def test_a_publish_scale_that_is_not_a_positive_int_refuses_the_number(
    tmp_path: Path, session_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """배수를 모를 때 1 로 떨어지면 가상 손익이 **100배**가 된다.

    그리고 그것은 틀려 보이지 않는다 — 아주 좋은 날처럼 보인다. 그래서 떨어지지
    않고 거부하고, 수 대신 사유를 낸다.
    """
    _tenant_content(session_tree, market="futures")
    render = session_tree / "cp3-sessions" / SESSION / "render"
    (render / "fields.yaml").write_text(
        _FIELDS_YAML.replace("{mult: 100, round: half_up}", '{mult: "100"}'),
        encoding="utf-8",
    )
    document = _exported(
        _export(
            tmp_path,
            session_tree,
            monkeypatch,
            document={**_DOCUMENT, "instrument": "A05612"},
        )
    )
    assert document["hypothetical_pnl"] is None
    assert document["hypothetical_pnl_error"] == "ExplainRefusal"
    assert document["explain"]["rules"]


def test_an_unparseable_construction_file_never_fails_the_export(
    tmp_path: Path, session_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``yaml.YAMLError`` 가 밖으로 새면 바 문서가 통째로 안 써진다."""
    _tenant_content(session_tree, market="futures")
    render = session_tree / "cp3-sessions" / SESSION / "render"
    (render / "construction.yaml").write_text("price_field_key: [\n", encoding="utf-8")
    document = _exported(
        _export(
            tmp_path,
            session_tree,
            monkeypatch,
            document={**_DOCUMENT, "instrument": "A05612"},
        )
    )
    assert document["bars"] == _DOCUMENT["bars"]
    assert document["hypothetical_pnl"] is None
    assert document["hypothetical_pnl_error"] == "ExplainRefusal"


def test_no_explanation_block_carries_a_host_path(
    tmp_path: Path, session_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """두 블록은 브라우저로 간다 — 읽은 파일의 경로가 어느 키에도 없어야 한다."""
    _tenant_content(session_tree, market="futures")
    document = _exported(
        _export(
            tmp_path,
            session_tree,
            monkeypatch,
            document={**_DOCUMENT, "instrument": "A05612"},
        )
    )
    added = json.dumps(
        {
            key: document.get(key)
            for key in ("explain", "hypothetical_pnl", "market", "decision_only")
        },
        ensure_ascii=False,
    )
    assert str(tmp_path) not in added
    assert str(session_tree) not in added
