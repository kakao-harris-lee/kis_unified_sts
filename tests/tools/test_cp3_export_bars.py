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
