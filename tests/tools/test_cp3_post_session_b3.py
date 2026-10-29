"""CP-3 post-session B3 automation (``tools/tos_cp3/post_session_b3.py``).

The thing this module has to keep true is the fail-closed direction. Roadmap
§2-1 is read off ``unresolved``, and ``unresolved`` has a "good" value — ``0``.
So every way the comparison can fail to happen must leave a record that says
*that*, and must never leave something a reader can mistake for "0 unresolved".
Each test below is one of those ways.

No subprocess runs here: :func:`tools.tos_cp3.post_session_b3.run` takes its
step runner as an argument, and the tests pass fakes. The one end-to-end proof
— the session runner invoking this step after the stop and keeping its own exit
code — lives with the runner's other tests in
:mod:`tests.tools.test_cp3_bootproof`.
"""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path
from typing import Any

import pytest

from tools.tos_cp3 import post_session_b3 as psb
from tools.tos_cp3 import status_board as sb

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONFIG = _REPO_ROOT / psb.CONFIG_REL
_RUNNER = _REPO_ROOT / "tools" / "tos_cp3" / "runners" / "run_tenant_session.sh"

_SESSION_DAY = "2026-10-27"
_INSTRUMENT = "A05611"
_STITCH_DAYS = ("2026-10-22", "2026-10-23", "2026-10-26", "2026-10-27")


def _config(**overrides: Any) -> psb.B3Config:
    """The shipped config, with fields replaced — never a config written here.

    A test that invents its own config can pass while the shipped one is
    broken, which is the failure this file exists to catch.
    """
    return dataclasses.replace(psb.load_config(_CONFIG), **overrides)


@dataclasses.dataclass
class _Tree:
    session: Path
    leaf: Path
    producer: Path
    render: Path


def _tree(
    tmp_path: Path,
    *,
    days: tuple[str, ...] = _STITCH_DAYS,
    strategies: tuple[str, ...] = ("setup_d_long.strategy.yaml",),
) -> _Tree:
    """A tenant session directory with every input the six steps read."""
    session = tmp_path / "long-20261027"
    producer = session / "producer"
    (producer / "market").mkdir(parents=True)
    (producer / "producer-log.jsonl").write_text(
        '{"stage": "seed"}\n', encoding="utf-8"
    )
    (producer / "boot-journal-snapshot.json").write_text("[]", encoding="utf-8")
    (producer / "market" / "stitch.json").write_text(
        json.dumps({"symbol": _INSTRUMENT, "segments": [{"days": list(days)}]}),
        encoding="utf-8",
    )
    render = session / "config"
    (render / "strategies").mkdir(parents=True)
    for name in strategies:
        (render / "strategies" / name).write_text("id: x\n", encoding="utf-8")
    (render / "strategy_bindings.yaml").write_text("bindings: []\n", encoding="utf-8")
    leaf = tmp_path / "data" / _INSTRUMENT
    leaf.mkdir(parents=True)
    for store in ("marketfeed", "evidence", "inbox"):
        (leaf / f"{store}.sqlite3").write_bytes(b"")
    return _Tree(session=session, leaf=leaf, producer=producer, render=render)


def _plan(tree: _Tree, **overrides: Any) -> psb.Plan:
    kwargs: dict[str, Any] = {
        "session_dir": tree.session,
        "data_leaf": tree.leaf,
        "producer_session_dir": tree.producer,
        "render_out": tree.render,
        "instrument": _INSTRUMENT,
        "session_day": _SESSION_DAY,
        "config": _config(),
        "python": "/usr/bin/python3",
        "repo_root": _REPO_ROOT,
    }
    kwargs.update(overrides)
    return psb.plan_steps(**kwargs)


def _run(tree: _Tree, step_runner: Any, **overrides: Any) -> int:
    kwargs: dict[str, Any] = {
        "session_dir": tree.session,
        "data_leaf": tree.leaf,
        "producer_session_dir": tree.producer,
        "render_out": tree.render,
        "instrument": _INSTRUMENT,
        "session_day": _SESSION_DAY,
        "market": "futures",
        "config": _config(),
        "python": "/usr/bin/python3",
        "repo_root": _REPO_ROOT,
        "step_runner": step_runner,
    }
    kwargs.update(overrides)
    return psb.run(**kwargs)


def _record(tree: _Tree, config: psb.B3Config | None = None) -> dict[str, Any]:
    subdir = (config or _config()).subdir
    path = tree.session / subdir / "status.json"
    assert path.is_file(), f"no record at {path}"
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# the shipped config, and the two values it has to agree with
# ---------------------------------------------------------------------------


def test_the_shipped_config_loads_and_covers_the_futures_tenant() -> None:
    """The config under test is the one production reads, not a test fixture."""
    config = psb.load_config(_CONFIG)
    assert config.enabled is True
    assert "futures" in config.markets
    assert (_REPO_ROOT / config.legacy_strategy_yaml).is_file()


def test_the_configs_subdir_is_the_one_the_status_board_reads() -> None:
    """Two names for one directory is how a comparison that RAN reads as
    "결과 없음": the board looks under :data:`status_board.B3_SUBDIR` and the
    tool writes under the config's ``subdir``."""
    assert psb.load_config(_CONFIG).subdir == sb.B3_SUBDIR


def test_the_status_record_version_is_the_one_the_status_board_reads() -> None:
    """Same hinge, for the record's shape."""
    assert psb.STATUS_SCHEMA_VERSION in sb.B3_STATUS_SCHEMA_VERSIONS


def test_the_b3_budget_stays_under_the_runners_ceiling() -> None:
    """The budget is the config's; the runner's ``timeout`` is only the stop for
    a wedged interpreter. If the ceiling ever drops below the budget, the outer
    SIGKILL starts cutting off healthy runs — and a SIGKILLed run leaves
    ``verdict: running``, i.e. a blocked day for no reason."""
    found = re.search(
        r"B3_CEILING_S=\$\{CP3_B3_CEILING_S:-(\d+)\}", _RUNNER.read_text("utf-8")
    )
    assert found is not None, "the runner no longer carries a B3 ceiling"
    assert psb.load_config(_CONFIG).total_timeout_s < int(found.group(1))


def test_the_runner_keeps_its_own_exit_code_around_the_b3_step() -> None:
    """A text-level companion to the end-to-end proof in test_cp3_bootproof:
    the step's rc is logged and never read again. Pinned here because the
    regression is silent — a ``die`` or an ``exit $b3_rc`` would turn a failed
    comparison into a failed session, and the cron wrapper alerts on that."""
    text = _RUNNER.read_text("utf-8")
    code = [
        ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")
    ]
    uses = [ln for ln in code if "b3_rc" in ln]
    assert len(uses) == 2, uses  # the assignment and the log line
    assert any("b3_rc=$?" in ln for ln in uses), uses
    assert all("exit" not in ln and "die " not in ln for ln in uses), uses


# ---------------------------------------------------------------------------
# config refusals
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("enabled: true\n", "has no 'markets'"),
        ("[1, 2]\n", "is not a mapping"),
        (
            "enabled: true\nmarkets: []\nsubdir: b3\n"
            "legacy_strategy_yaml: x\ntotal_timeout_s: 1\n",
            "'markets' must be non-empty strings",
        ),
        (
            "enabled: true\nmarkets: [futures]\nsubdir: b3\n"
            "legacy_strategy_yaml: x\ntotal_timeout_s: true\n",
            "'total_timeout_s' must be int",
        ),
        (
            "enabled: true\nmarkets: [futures]\nsubdir: b3\n"
            "legacy_strategy_yaml: x\ntotal_timeout_s: 0\n",
            "'total_timeout_s' must be positive",
        ),
        (
            "enabled: true\nmarkets: [futures]\nsubdir: ../escape\n"
            "legacy_strategy_yaml: x\ntotal_timeout_s: 1\n",
            "single plain directory name",
        ),
        (
            "enabled: 1\nmarkets: [futures]\nsubdir: b3\n"
            "legacy_strategy_yaml: x\ntotal_timeout_s: 1\n",
            "'enabled' must be bool",
        ),
    ],
)
def test_red_a_config_that_cannot_be_trusted_is_refused(
    tmp_path: Path, body: str, expected: str
) -> None:
    """Every value is required and typed. ``total_timeout_s: true`` is the
    concrete input the bool/int check is for: ``isinstance(True, int)`` passes,
    and a one-second budget would cut off every step."""
    path = tmp_path / "b3.yaml"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(psb.PostSessionB3Error, match=re.escape(expected)):
        psb.load_config(path)


def test_red_a_missing_config_is_refused_not_defaulted(tmp_path: Path) -> None:
    with pytest.raises(psb.PostSessionB3Error, match="config not found"):
        psb.load_config(tmp_path / "nope.yaml")


# ---------------------------------------------------------------------------
# the window
# ---------------------------------------------------------------------------


def test_the_window_starts_at_the_earliest_stitch_day(tmp_path: Path) -> None:
    """B1a/B2 run over the producer's frozen frame, so ``--start`` is the
    manifest's earliest day — the runbook's own rule — and ``--end`` is the
    session day."""
    plan = _plan(_tree(tmp_path))
    assert (plan.window_start, plan.window_end) == ("2026-10-22", _SESSION_DAY)


def test_the_earliest_day_is_taken_across_segments_not_the_first_listed(
    tmp_path: Path,
) -> None:
    """A roll day has two segments, and nothing promises their order."""
    tree = _tree(tmp_path)
    (tree.producer / "market" / "stitch.json").write_text(
        json.dumps(
            {
                "segments": [
                    {"contract": "A05612", "days": ["2026-10-27"]},
                    {"contract": "A05611", "days": ["2026-10-20", "2026-10-21"]},
                ]
            }
        ),
        encoding="utf-8",
    )
    assert _plan(tree).window_start == "2026-10-20"


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ('{"segments": []}', "lists no segment day"),
        ('{"segments": [{"days": []}]}', "lists no segment day"),
        ("[]", "is not an object"),
        ("not json", "unreadable"),
    ],
)
def test_red_a_manifest_with_no_usable_window_is_refused(
    tmp_path: Path, body: str, expected: str
) -> None:
    """A guessed window compares against the wrong bars, and the result would
    look like real divergence."""
    tree = _tree(tmp_path)
    (tree.producer / "market" / "stitch.json").write_text(body, encoding="utf-8")
    with pytest.raises(psb.PostSessionB3Error, match=expected):
        _plan(tree)


def test_red_a_frame_that_starts_after_the_session_day_is_refused(
    tmp_path: Path,
) -> None:
    """The one shape that is not a missing file and still cannot be compared:
    a manifest from a later session (a stale producer dir reused)."""
    tree = _tree(tmp_path, days=("2026-10-28",))
    with pytest.raises(psb.PostSessionB3Error, match="does not cover this session"):
        _plan(tree)


# ---------------------------------------------------------------------------
# the plan — the runbook's six commands
# ---------------------------------------------------------------------------


def test_the_plan_is_the_runbooks_six_steps_in_order(tmp_path: Path) -> None:
    plan = _plan(_tree(tmp_path))
    assert [step.name for step in plan.steps] == [
        "consumed-ids",
        "live-decisions",
        "b1a-fields",
        "b2-legacy",
        "b1b-tos",
        "b3-report",
    ]


def test_consumed_ids_is_given_the_boot_snapshot(tmp_path: Path) -> None:
    """``session_inputs.py`` REFUSES ``consumed-ids`` without it, and the
    reason is M5's: without the snapshot a pre-boot line silently joins the
    post-boot counts the criterion is read off."""
    step = next(s for s in _plan(_tree(tmp_path)).steps if s.name == "consumed-ids")
    assert "--boot-snapshot" in step.argv
    assert step.argv[step.argv.index("--boot-snapshot") + 1].endswith(
        "boot-journal-snapshot.json"
    )


def test_live_decisions_is_given_the_boot_snapshot_too(tmp_path: Path) -> None:
    """**The measured blocker.** Without it ``live.jsonl`` spans the whole
    accumulating leaf and step 6 refuses: on the 10-28 LONG session's own
    stores, 1,939 of 2,348 live records named bars outside that session's
    frozen frame (``session_inputs.LiveScope`` carries the measurement). Scoped,
    the same run writes a summary — 409 bars, unresolved 0."""
    step = next(s for s in _plan(_tree(tmp_path)).steps if s.name == "live-decisions")
    assert "--boot-snapshot" in step.argv
    assert step.argv[step.argv.index("--boot-snapshot") + 1].endswith(
        "boot-journal-snapshot.json"
    )


def test_b1a_and_b2_read_the_producers_frozen_frame_with_the_same_manifest(
    tmp_path: Path,
) -> None:
    """§3.6: the offline three run over the frame the producer FROZE, not the
    legacy Parquet tree — and B3 compares the manifest digest, so both sides
    must be handed the same one."""
    tree = _tree(tmp_path)
    plan = _plan(tree)
    steps = {s.name: s for s in plan.steps}
    for name in ("b1a-fields", "b2-legacy"):
        argv = steps[name].argv
        assert argv[argv.index("--data-root") + 1] == str(tree.producer / "market")
        assert argv[argv.index("--stitch-manifest") + 1] == str(
            tree.producer / "market" / "stitch.json"
        )
        assert argv[argv.index("--start") + 1] == plan.window_start
        assert argv[argv.index("--end") + 1] == plan.window_end
        assert argv[argv.index("--strategy-yaml") + 1] == str(
            _REPO_ROOT / _config().legacy_strategy_yaml
        )


def test_b1b_uses_the_strategy_this_session_rendered(tmp_path: Path) -> None:
    """Neither committed copy can load this journal — the harness copy pins
    backtest coordinates, the tenant copy leaves them ``"TBD"`` — so B1b reads
    the rendered tree. That is also why this step cannot wait until the session
    directory is cleaned up."""
    tree = _tree(tmp_path)
    step = next(s for s in _plan(tree).steps if s.name == "b1b-tos")
    assert step.argv[step.argv.index("--strategy") + 1] == str(
        tree.render / "strategies" / "setup_d_long.strategy.yaml"
    )
    assert step.argv[step.argv.index("--bindings") + 1] == str(
        tree.render / "strategy_bindings.yaml"
    )
    env = dict(step.extra_env)
    assert env["PYTHONPATH"].split(":") == [
        str(_REPO_ROOT / "tos" / "src"),
        str(_REPO_ROOT / "tos" / "runtime" / "src"),
        str(_REPO_ROOT / "tos" / "runtime"),
    ]


def test_the_short_tree_needs_no_flag_of_its_own(tmp_path: Path) -> None:
    """The direction is not a parameter here: a rendered tree holds exactly one
    strategy, and taking the one that is there cannot disagree with the tree
    the session actually booted."""
    tree = _tree(tmp_path, strategies=("setup_d_short.strategy.yaml",))
    step = next(s for s in _plan(tree).steps if s.name == "b1b-tos")
    assert step.argv[step.argv.index("--strategy") + 1].endswith(
        "setup_d_short.strategy.yaml"
    )


@pytest.mark.parametrize("count", [0, 2])
def test_red_a_render_tree_without_exactly_one_strategy_is_refused(
    tmp_path: Path, count: int
) -> None:
    """Two is a render that did not do what it says; zero is a render that did
    not happen. Picking one of two would compare the wrong direction."""
    names = tuple(f"setup_d_{i}.strategy.yaml" for i in range(count))
    with pytest.raises(psb.PostSessionB3Error, match="exactly one"):
        _plan(_tree(tmp_path, strategies=names))


def test_b3_joins_both_session_derived_inputs(tmp_path: Path) -> None:
    """``--consumed-ids`` scopes the comparison to the bars the runtime
    consumed and ``--live`` is what ``live_comparison`` is computed from.
    Without them B3 still writes a summary — of an offline replay nobody ran
    live — so their presence is the difference between measuring §2-1 and
    measuring nothing."""
    tree = _tree(tmp_path)
    plan = _plan(tree)
    argv = next(s for s in plan.steps if s.name == "b3-report").argv
    subdir = tree.session / _config().subdir
    assert argv[argv.index("--consumed-ids") + 1] == str(subdir / "consumed-ids.json")
    assert argv[argv.index("--live") + 1] == str(subdir / "live" / "live.jsonl")
    assert argv[argv.index("--out") + 1] == str(subdir / "report")
    assert plan.summary_path == subdir / "report" / "summary.json"


@pytest.mark.parametrize(
    "relative",
    [
        "producer/producer-log.jsonl",
        "producer/boot-journal-snapshot.json",
        "producer/market/stitch.json",
        "config/strategy_bindings.yaml",
    ],
)
def test_red_every_missing_session_input_is_named(
    tmp_path: Path, relative: str
) -> None:
    """The record is all an operator gets back, so a refusal says WHICH path."""
    tree = _tree(tmp_path)
    (tree.session / relative).unlink()
    with pytest.raises(
        psb.PostSessionB3Error, match=re.escape(relative.split("/")[-1])
    ):
        _plan(tree)


@pytest.mark.parametrize("store", ["marketfeed", "evidence", "inbox"])
def test_red_a_durable_leaf_missing_a_store_is_named(
    tmp_path: Path, store: str
) -> None:
    """All three are read: marketfeed for consumed ids, evidence for decisions,
    inbox for the key that joins a decision to its bar."""
    tree = _tree(tmp_path)
    (tree.leaf / f"{store}.sqlite3").unlink()
    with pytest.raises(psb.PostSessionB3Error, match=f"{store}.sqlite3"):
        _plan(tree)


def test_red_no_durable_leaf_at_all_is_named(tmp_path: Path) -> None:
    tree = _tree(tmp_path)
    for store in ("marketfeed", "evidence", "inbox"):
        (tree.leaf / f"{store}.sqlite3").unlink()
    tree.leaf.rmdir()
    with pytest.raises(psb.PostSessionB3Error, match="durable set leaf"):
        _plan(tree)


def test_red_a_missing_legacy_strategy_yaml_is_named(tmp_path: Path) -> None:
    """Config-driven, so a config pointing at nothing must refuse rather than
    hand ``--strategy-yaml`` a path that does not exist."""
    with pytest.raises(psb.PostSessionB3Error, match="setup_d_vwap_reversion.yaml"):
        _plan(_tree(tmp_path), repo_root=tmp_path / "elsewhere")


# ---------------------------------------------------------------------------
# the record — every way this can fail says so
# ---------------------------------------------------------------------------


class _FakeSteps:
    """A step runner that records calls and returns scripted codes."""

    def __init__(
        self, *, codes: dict[str, int] | None = None, writes_summary: bool = True
    ) -> None:
        self.codes = codes or {}
        self.writes_summary = writes_summary
        self.calls: list[str] = []
        self.records_seen: list[dict[str, Any]] = []
        self.summary_path: Path | None = None

    def __call__(
        self, step: psb.Step, *, log_dir: Path, cwd: Path, timeout_s: float
    ) -> tuple[int, float, Path]:
        self.calls.append(step.name)
        log_dir.mkdir(parents=True, exist_ok=True)
        log = log_dir / f"{step.name}.log"
        log.write_text(f"fake {step.name}\n", encoding="utf-8")
        record = (log_dir.parent / "status.json").read_text(encoding="utf-8")
        self.records_seen.append(json.loads(record))
        if step.name == "b3-report" and self.writes_summary:
            assert self.summary_path is not None
            self.summary_path.parent.mkdir(parents=True, exist_ok=True)
            self.summary_path.write_text(
                json.dumps({"summary_schema_version": 2, "unresolved": {"count": 0}}),
                encoding="utf-8",
            )
        return self.codes.get(step.name, 0), 0.5, log


def test_a_run_that_completes_records_ok_and_points_at_the_summary(
    tmp_path: Path,
) -> None:
    tree = _tree(tmp_path)
    steps = _FakeSteps()
    steps.summary_path = _plan(tree).summary_path
    assert _run(tree, steps) == 0
    record = _record(tree)
    assert record["verdict"] == "ok"
    assert record["stage"] is None
    assert record["summary_json"] == str(steps.summary_path)
    assert record["window"] == {"start": "2026-10-22", "end": _SESSION_DAY}
    assert [s["name"] for s in record["steps"]] == steps.calls
    assert record["ended_at"] is not None


def test_the_record_exists_before_the_first_step_and_says_running(
    tmp_path: Path,
) -> None:
    """The one case no end-of-run write can cover: this process being killed.
    The record is written BEFORE step 1, so a SIGKILL leaves ``running`` — and
    the status board reads that as "did not finish", never as unresolved 0."""
    tree = _tree(tmp_path)
    steps = _FakeSteps()
    steps.summary_path = _plan(tree).summary_path
    _run(tree, steps)
    first = steps.records_seen[0]
    assert first["verdict"] == "running"
    assert first["steps"] == []
    assert first["ended_at"] is None
    assert first["window"] == {"start": "2026-10-22", "end": _SESSION_DAY}


def test_red_a_step_that_refuses_is_recorded_and_no_summary_is_invented(
    tmp_path: Path,
) -> None:
    """The headline failure: one step refuses, and what is left behind is a
    named stage — not a summary, and not silence."""
    tree = _tree(tmp_path)
    steps = _FakeSteps(codes={"b1a-fields": 2})
    assert _run(tree, steps) == 2
    record = _record(tree)
    assert record["verdict"] == "failed"
    assert record["stage"] == "b1a-fields"
    assert "exited 2" in record["reason"]
    # it stopped there — B2 and the report never ran
    assert steps.calls == ["consumed-ids", "live-decisions", "b1a-fields"]
    assert not _plan(tree).summary_path.exists()
    assert record["steps"][-1]["rc"] == 2


def test_red_all_steps_pass_but_no_summary_is_still_a_failure(
    tmp_path: Path,
) -> None:
    """``summary.json`` is the only thing that measures §2-1. Six zero exit
    codes without it is a tool that changed under us, and the record says so
    rather than reporting a comparison that produced nothing."""
    tree = _tree(tmp_path)
    assert _run(tree, _FakeSteps(writes_summary=False)) == 2
    record = _record(tree)
    assert record["verdict"] == "failed"
    assert record["stage"] == "b3-report"
    assert "is not there" in record["reason"]


def test_red_a_missing_input_is_recorded_as_failed_not_skipped(
    tmp_path: Path,
) -> None:
    """A session whose producer left no log cannot be compared. "Could not" is
    a failure, and "we chose not to" is a skip; conflating them would hide a
    broken producer behind a configuration note."""
    tree = _tree(tmp_path)
    (tree.producer / "producer-log.jsonl").unlink()
    steps = _FakeSteps()
    assert _run(tree, steps) == 2
    record = _record(tree)
    assert record["verdict"] == "failed"
    assert record["stage"] == "inputs"
    assert "producer-log.jsonl" in record["reason"]
    assert steps.calls == []


def test_a_disabled_config_is_recorded_as_skipped(tmp_path: Path) -> None:
    tree = _tree(tmp_path)
    steps = _FakeSteps()
    assert _run(tree, steps, config=_config(enabled=False)) == 3
    record = _record(tree)
    assert record["verdict"] == "skipped"
    assert "enabled is false" in record["reason"]
    assert steps.calls == []


def test_a_market_b3_does_not_cover_is_recorded_as_skipped(tmp_path: Path) -> None:
    """The stock mock-order tree (PR-3a) has no legacy Setup D replay, so the
    comparison would not refuse — it would report differences that are only the
    wrong strategy."""
    tree = _tree(tmp_path)
    steps = _FakeSteps()
    assert _run(tree, steps, market="stock") == 3
    record = _record(tree)
    assert record["verdict"] == "skipped"
    assert "'stock'" in record["reason"]
    assert steps.calls == []


def test_red_the_budget_stops_the_sequence_and_says_where(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The budget exists so this step cannot hold the cron wrapper's flock into
    the next day. When it runs out the record names the step that never
    started."""
    tree = _tree(tmp_path)
    clock = iter([0.0] + [1000.0] * 50)
    monkeypatch.setattr(psb.time, "monotonic", lambda: next(clock))
    steps = _FakeSteps()
    assert _run(tree, steps) == 2
    record = _record(tree)
    assert record["verdict"] == "failed"
    assert record["stage"] == "consumed-ids"
    assert "budget ran out" in record["reason"]
    assert steps.calls == []


def test_each_step_gets_only_the_time_the_budget_has_left(tmp_path: Path) -> None:
    """A step is handed the remaining budget, not the whole of it — otherwise
    six steps could take six budgets."""
    tree = _tree(tmp_path)
    seen: list[float] = []

    def runner(
        step: psb.Step, *, log_dir: Path, cwd: Path, timeout_s: float
    ) -> tuple[int, float, Path]:
        seen.append(timeout_s)
        log_dir.mkdir(parents=True, exist_ok=True)
        log = log_dir / f"{step.name}.log"
        log.write_text("x", encoding="utf-8")
        if step.name == "b3-report":
            path = _plan(tree).summary_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}", encoding="utf-8")
        return 0, 0.0, log

    assert _run(tree, runner) == 0
    assert seen == sorted(seen, reverse=True), seen
    assert max(seen) <= _config().total_timeout_s


def test_the_record_is_replaced_whole_and_leaves_no_partial_file(
    tmp_path: Path,
) -> None:
    """Atomic because the failure this record is for is the process not getting
    to finish: a half-written file would read as "unparseable", and the board
    would have to guess whether B3 ran."""
    tree = _tree(tmp_path)
    steps = _FakeSteps()
    steps.summary_path = _plan(tree).summary_path
    _run(tree, steps)
    subdir = tree.session / _config().subdir
    assert list(subdir.glob("status.json*")) == [subdir / "status.json"]


def test_a_step_log_is_kept_for_every_step_that_ran(tmp_path: Path) -> None:
    """The reason lines point at these, so they are part of the record."""
    tree = _tree(tmp_path)
    steps = _FakeSteps(codes={"b2-legacy": 1})
    _run(tree, steps)
    for entry in _record(tree)["steps"]:
        assert Path(entry["log"]).is_file(), entry


# ---------------------------------------------------------------------------
# the CLI
# ---------------------------------------------------------------------------


def test_red_a_session_day_that_is_not_a_date_is_refused(tmp_path: Path) -> None:
    """Exit 4 — the code for "there is no record", which is what this is: the
    day is in every path the record would be read against."""
    tree = _tree(tmp_path)
    rc = psb.main(
        [
            "--session-dir",
            str(tree.session),
            "--data-leaf",
            str(tree.leaf),
            "--producer-session-dir",
            str(tree.producer),
            "--render-out",
            str(tree.render),
            "--instrument",
            _INSTRUMENT,
            "--session-day",
            "27-10-2026",
            "--market",
            "futures",
        ]
    )
    assert rc == 4
    assert not (tree.session / _config().subdir).exists()


def test_red_a_missing_config_exits_four_with_no_record(tmp_path: Path) -> None:
    """The one path that leaves nothing on disk: without a config there is no
    ``subdir`` to write into. It exits 4, distinct from the 2 that means
    "there IS a record and it says failed"."""
    tree = _tree(tmp_path)
    rc = psb.main(
        [
            "--session-dir",
            str(tree.session),
            "--data-leaf",
            str(tree.leaf),
            "--producer-session-dir",
            str(tree.producer),
            "--render-out",
            str(tree.render),
            "--instrument",
            _INSTRUMENT,
            "--session-day",
            _SESSION_DAY,
            "--market",
            "futures",
            "--config",
            str(tmp_path / "nope.yaml"),
        ]
    )
    assert rc == 4
    assert not (tree.session / "b3").exists()
