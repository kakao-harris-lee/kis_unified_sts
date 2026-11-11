"""`sts tos inspect` — the legacy-side driver: path resolution and child argv.

Roadmap ``docs/plans/2026-11-11-tos-platform-roadmap.md`` §P1. The driver
(:mod:`tools.tos_cp3.inspect_session`) may not import ``tos`` — the reverse
firewall (TOS-FW-R) — so the inspection itself runs as a child process and its
output table is pinned on the other side of that boundary, in
``tos/runtime/cp3/tests/test_cp3_inspect_session.py``, where the real DSL
evaluator and the real strategy loader are importable.

What is left for this suite is exactly what this module owns, and it is tested
**without starting a process**: the run callable is injected, so every test here
asserts the resolved paths, the child's argv and ``PYTHONPATH``, and each
refusal that must happen BEFORE a child is ever launched.

No session fixture is copied from a real state directory: the four paths a
session is resolved to are created in ``tmp_path`` with the names the runner
writes (``tools/tos_cp3/runners/run_tenant_session.sh``).
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from tools.tos_cp3 import inspect_session as ins
from tools.tos_cp3 import status_board as sb

SESSION = "stock-r1-20261110"
TREE_ID = "cp3-setup-d-stock-005930"
INSTRUMENT = "005930"
SESSIONS_SUBDIR = "cp3-sessions"


def _session_tree(
    tmp_path: Path, *, strategy_files: Sequence[str] = ("d.strategy.yaml",)
) -> Path:
    """A state root holding one recorded session and its tenant durable set."""
    state = tmp_path / "state"
    session = state / SESSIONS_SUBDIR / SESSION
    render = session / "render"
    (render / "strategies").mkdir(parents=True)
    (session / "journal.jsonl").write_text("{}\n", encoding="utf-8")
    (render / ins.RENDERED_MANIFEST_NAME).write_text(
        json.dumps({"instrument": INSTRUMENT, "tree_id": TREE_ID}), encoding="utf-8"
    )
    (render / ins.STRATEGY_BINDINGS_FILE_NAME).write_text(
        "strategies: {}\n", encoding="utf-8"
    )
    for name in strategy_files:
        (render / "strategies" / name).write_text("policy: {}\n", encoding="utf-8")
    (state / f"{TREE_ID}{ins.TENANT_DATA_PARENT_SUFFIX}" / INSTRUMENT).mkdir(
        parents=True
    )
    return state


def _resolve(state: Path, session: str = SESSION, **kwargs: object) -> ins.SessionPaths:
    """Resolve ``session`` against ``state`` with the production subdir name."""
    return ins.resolve_session(
        session,
        state_dir=state,
        sessions_subdir=SESSIONS_SUBDIR,
        **kwargs,  # type: ignore[arg-type]
    )


# ===========================================================================
# Resolution
# ===========================================================================


def test_a_session_name_resolves_to_its_four_paths(tmp_path: Path) -> None:
    """A bare name becomes journal + strategy + bindings + durable-set leaf."""
    state = _session_tree(tmp_path)
    paths = _resolve(state)
    assert paths.session_name == SESSION
    assert paths.journal_path == state / SESSIONS_SUBDIR / SESSION / "journal.jsonl"
    assert paths.strategy_path == (
        state / SESSIONS_SUBDIR / SESSION / "render" / "strategies" / "d.strategy.yaml"
    )
    assert paths.bindings_path == (
        state / SESSIONS_SUBDIR / SESSION / "render" / ins.STRATEGY_BINDINGS_FILE_NAME
    )
    assert paths.data_dir == state / f"{TREE_ID}-data" / INSTRUMENT
    assert (paths.instrument, paths.tree_id) == (INSTRUMENT, TREE_ID)


def test_a_path_resolves_without_the_state_root(tmp_path: Path) -> None:
    """A session given as a path is used as given — the name lookup is a fallback."""
    state = _session_tree(tmp_path)
    paths = _resolve(state, str(state / SESSIONS_SUBDIR / SESSION))
    assert paths.session_dir == state / SESSIONS_SUBDIR / SESSION


def test_the_data_dir_is_derived_from_the_manifest_not_the_session_name(
    tmp_path: Path,
) -> None:
    """``<state>/<tree_id>-data/<instrument>`` — both parts come from the manifest.

    The session directory is named ``stock-r1-…`` while the tree is
    ``cp3-setup-d-stock-005930``, so a derivation from the session name would
    point at a directory that does not exist.
    """
    state = _session_tree(tmp_path)
    assert TREE_ID not in SESSION
    assert _resolve(state).data_dir == state / f"{TREE_ID}-data" / INSTRUMENT


def test_an_explicit_data_dir_overrides_the_derivation(tmp_path: Path) -> None:
    """``--data-dir`` wins — the derivation is a convenience, not a contract."""
    state = _session_tree(tmp_path)
    elsewhere = tmp_path / "restored"
    elsewhere.mkdir()
    assert _resolve(state, data_dir=elsewhere).data_dir == elsewhere


def test_no_evidence_skips_the_durable_set_entirely(tmp_path: Path) -> None:
    """``--no-evidence`` needs no store on disk at all."""
    state = _session_tree(tmp_path)
    for path in sorted(
        (state / f"{TREE_ID}-data").rglob("*"), key=lambda p: -len(p.parts)
    ):
        path.rmdir()
    (state / f"{TREE_ID}-data").rmdir()
    assert _resolve(state, with_evidence=False).data_dir is None


@pytest.mark.parametrize(
    ("removed", "message"),
    [
        ("journal.jsonl", "no producer journal"),
        ("render/RENDERED.json", "render manifest is missing"),
        ("render/strategy_bindings.yaml", "no bindings file"),
    ],
)
def test_a_missing_session_artifact_refuses_by_name(
    tmp_path: Path, removed: str, message: str
) -> None:
    """Every artifact the inspection needs is named when absent, never inferred."""
    state = _session_tree(tmp_path)
    (state / SESSIONS_SUBDIR / SESSION / removed).unlink()
    with pytest.raises(ins.InspectRefusal, match=message):
        _resolve(state)


def test_a_missing_session_directory_names_where_it_looked(tmp_path: Path) -> None:
    """The refusal says which parent it searched, so a typo is self-diagnosing."""
    state = _session_tree(tmp_path)
    with pytest.raises(ins.InspectRefusal, match="no such session directory"):
        _resolve(state, "stock-r1-20261109")


def test_a_session_without_a_render_tree_refuses(tmp_path: Path) -> None:
    """Without the rendered tree the policy the session RAN cannot be read."""
    state = _session_tree(tmp_path)
    render = state / SESSIONS_SUBDIR / SESSION / "render"
    for path in sorted(render.rglob("*"), key=lambda p: -len(p.parts)):
        path.unlink() if path.is_file() else path.rmdir()
    render.rmdir()
    with pytest.raises(ins.InspectRefusal, match="kept no rendered tenant tree"):
        _resolve(state)


@pytest.mark.parametrize("names", [(), ("a.strategy.yaml", "b.strategy.yaml")])
def test_a_tree_without_exactly_one_strategy_refuses(
    tmp_path: Path, names: tuple[str, ...]
) -> None:
    """Which strategy a session ran is a fact of the render, so two is a refusal."""
    state = _session_tree(tmp_path, strategy_files=names)
    with pytest.raises(ins.InspectRefusal, match="strategy file"):
        _resolve(state)


@pytest.mark.parametrize("manifest", ['{"tree_id": "t"}', '{"instrument": "i"}', "[]"])
def test_a_manifest_missing_either_name_refuses(tmp_path: Path, manifest: str) -> None:
    """Instrument and tree id are READ from the manifest, never guessed."""
    state = _session_tree(tmp_path)
    (
        state / SESSIONS_SUBDIR / SESSION / "render" / ins.RENDERED_MANIFEST_NAME
    ).write_text(manifest, encoding="utf-8")
    with pytest.raises(ins.InspectRefusal):
        _resolve(state)


def test_a_missing_durable_set_leaf_refuses_with_the_two_ways_out(
    tmp_path: Path,
) -> None:
    """The refusal names ``--data-dir`` and ``--no-evidence`` rather than guessing."""
    state = _session_tree(tmp_path)
    (state / f"{TREE_ID}-data" / INSTRUMENT).rmdir()
    with pytest.raises(ins.InspectRefusal, match="--data-dir.*--no-evidence"):
        _resolve(state)


# ===========================================================================
# The child invocation
# ===========================================================================


def test_build_argv_is_the_child_module_with_every_resolved_path(
    tmp_path: Path,
) -> None:
    """The argv is exactly the core CLI's flags — nothing is passed positionally."""
    paths = _resolve(_session_tree(tmp_path))
    argv = ins.build_argv(
        paths, window_from="09:00", window_to="10:00", as_json=True, executable="/py"
    )
    assert argv == [
        "/py",
        "-P",
        "-m",
        "cp3.inspect_session",
        "--journal",
        str(paths.journal_path),
        "--strategy",
        str(paths.strategy_path),
        "--bindings",
        str(paths.bindings_path),
        "--session-name",
        SESSION,
        "--data-dir",
        str(paths.data_dir),
        "--from",
        "09:00",
        "--to",
        "10:00",
        "--json",
    ]


def test_build_argv_omits_the_flags_that_were_not_asked_for(tmp_path: Path) -> None:
    """An unset window or ``--no-evidence`` leaves the flag off, not empty."""
    paths = _resolve(_session_tree(tmp_path), with_evidence=False)
    argv = ins.build_argv(paths, executable="/py")
    assert "--data-dir" not in argv
    assert "--from" not in argv and "--to" not in argv and "--json" not in argv


def test_child_pythonpath_is_the_kernel_the_runtime_and_cp3s_parent() -> None:
    """``cp3`` is importable only with ``tos/runtime`` on the path, so all three go."""
    parts = ins.child_pythonpath(Path("/repo")).split(os.pathsep)
    assert parts == ["/repo/tos/src", "/repo/tos/runtime/src", "/repo/tos/runtime"]


def test_run_passes_the_argv_and_pythonpath_to_the_injected_runner(
    tmp_path: Path,
) -> None:
    """``run`` resolves, then hands ONE argv + env to the runner and returns its result."""
    state = _session_tree(tmp_path)
    seen: dict[str, object] = {}

    def runner(argv: Sequence[str], env: Mapping[str, str]) -> tuple[str, int]:
        seen["argv"] = list(argv)
        seen["env"] = dict(env)
        return "rendered table\n", 0

    text, code = ins.run(
        session=SESSION,
        state_dir=str(state),
        window_from="09:00",
        runner=runner,
    )
    assert (text, code) == ("rendered table\n", 0)
    argv = seen["argv"]
    assert isinstance(argv, list)
    assert argv[1:4] == ["-P", "-m", "cp3.inspect_session"]
    assert argv[-2:] == ["--from", "09:00"]
    env = seen["env"]
    assert isinstance(env, dict)
    assert env["PYTHONPATH"] == ins.child_pythonpath()
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"


def test_run_refuses_before_launching_anything(tmp_path: Path) -> None:
    """A resolution refusal is exit 2 and the runner is never called."""

    def runner(argv: Sequence[str], env: Mapping[str, str]) -> tuple[str, int]:
        raise AssertionError("the child must not be launched on a refusal")

    text, code = ins.run(
        session="no-such-session", state_dir=str(tmp_path / "state"), runner=runner
    )
    assert code == 2
    assert text.startswith("inspect refused: ")


def test_run_reads_the_sessions_subdir_from_the_status_board_config(
    tmp_path: Path,
) -> None:
    """The session parent's name is config, not a literal in this module."""
    state = _session_tree(tmp_path)
    assert sb.load_config().tenant_sessions_subdir == SESSIONS_SUBDIR

    def runner(argv: Sequence[str], env: Mapping[str, str]) -> tuple[str, int]:
        return "\n".join(argv), 0

    text, code = ins.run(session=SESSION, state_dir=str(state), runner=runner)
    assert code == 0
    assert str(state / SESSIONS_SUBDIR / SESSION / "journal.jsonl") in text


# ===========================================================================
# The firewall, restated where a reader of this suite sees it
# ===========================================================================


def test_the_driver_imports_nothing_from_tos() -> None:
    """``tools/tos_firewall_check.py`` is the gate; this is a fast local echo.

    The whole reason this module shells out instead of calling the evaluator is
    that it may not import it, so a ``from tos…`` line added here must fail in
    the unit suite too — not only in the ``tos-firewall`` CI job.
    """
    source = (ins.REPO_ROOT / "tools" / "tos_cp3" / "inspect_session.py").read_text(
        encoding="utf-8"
    )
    for line in source.splitlines():
        stripped = line.strip()
        assert not stripped.startswith(("import tos", "from tos ")), line
        assert not stripped.startswith(("import tos_runtime", "from tos_runtime")), line
        assert not stripped.startswith("from tos."), line
