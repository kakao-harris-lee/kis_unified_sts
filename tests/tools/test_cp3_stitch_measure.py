"""The committed S1a/S1b analysis tool — hermetic.

``tools/tos_cp3/stitch_measure.py`` exists so the evidence README's numbers
can be re-derived from the repo instead of from a scratch script nobody kept
(review LOW-4). These tests pin the two properties that make it trustworthy
without re-running the hours-long measurement: it reaches no transport, and
its raw-response reader resolves overlapping pages the way the derivation
assumed.
"""

from __future__ import annotations

import ast
import json
from datetime import date
from pathlib import Path

import pytest

from tools.tos_cp3 import stitch_measure

_REPO_ROOT = Path(__file__).resolve().parents[2]

#: Order paths, which must not be REACHABLE at all.
#:
#: ⚠ Deliberately does NOT list ``httpx`` / ``shared.kis`` /
#: ``tools.tos_cp3.quote_client``: those ARE in the closure, because the frame
#: helper the tool reuses (``minute_probe.frame``) lives beside the probe's
#: transport. The first cut of this list included them and went red on its
#: first run — the right disposition was to correct the tool's docstring and
#: split the claim in two (this list, plus
#: :func:`test_the_tool_constructs_no_transport_and_fetches_nothing`), not to
#: delete the test. A reachability list that quietly drops the entries that
#: fail is the "guard that admits what it names" shape.
FORBIDDEN = (
    "shared.execution.executor",
    "shared.execution.venue_router",
    "shared.execution.passive_maker",
    "shared.execution.pseudo_oco",
    "tools.broker_probes.probes_real_order",
    "tos",
    "tos_runtime",
)

#: Names that would mean this module itself talks to the broker.
TRANSPORT_CALL_SITES = ("Quotes", "resolve_credentials", "KISAuthManager")


def _module_source(name: str) -> str | None:
    base = _REPO_ROOT / Path(*name.split("."))
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    return None


def _import_closure(module_name: str) -> set[str]:
    """Static import walk, parent packages and relative imports included.

    Same shape as ``test_cp3_live_producer``'s walker, and for the same
    measured reason: the producer's ``shared.execution`` edge was reached
    through a parent ``__init__``, invisible to a walk that skipped them.
    """
    seen: set[str] = set()
    queue = [module_name]
    while queue:
        name = queue.pop()
        if not name or name in seen:
            continue
        seen.add(name)
        parts = name.split(".")
        queue.extend(".".join(parts[:depth]) for depth in range(1, len(parts)))
        source = _module_source(name)
        if source is None:
            continue
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                queue.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    prefix = parts[: len(parts) - node.level]
                    if _module_source(name) and (base := _REPO_ROOT / Path(*parts)):
                        if not base.is_dir():
                            prefix = parts[: max(0, len(parts) - node.level)]
                    root = ".".join([*prefix, node.module] if node.module else prefix)
                else:
                    root = node.module or ""
                queue.append(root)
                queue.extend(f"{root}.{alias.name}" for alias in node.names if root)
    return seen


@pytest.fixture(scope="module")
def closure() -> set[str]:
    return _import_closure("tools.tos_cp3.stitch_measure")


@pytest.mark.parametrize("forbidden", FORBIDDEN)
def test_the_measure_tool_reaches_no_order_path(
    forbidden: str, closure: set[str]
) -> None:
    offending = sorted(
        name
        for name in closure
        if name == forbidden or name.startswith(forbidden + ".")
    )
    assert not offending, offending
    # the walk really reached the tool's own dependencies
    assert "tools.tos_cp3.produce_fields" in closure
    assert "tools.tos_cp3.live_producer.stitch_seed" in closure
    # ...and really does see the transport it is NOT allowed to call, so the
    # split between this test and the next one is about a real edge.
    assert "tools.tos_cp3.quote_client" in closure


def test_the_tool_constructs_no_transport_and_fetches_nothing() -> None:
    """The transport is in the graph; this module never reaches for it.

    Checked on this module's own AST rather than on the closure, because the
    closure cannot express it: ``minute_probe`` carries both the frame helper
    this tool wants and the ``Quotes`` client it must not touch. Concrete
    failing input — add ``Quotes(creds, rec, cfg)`` anywhere below and this
    goes red.
    """
    source = (_REPO_ROOT / "tools" / "tos_cp3" / "stitch_measure.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    used = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} | {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    for name in TRANSPORT_CALL_SITES:
        assert name not in used, f"{name} appears in the measurement tool"
    fetches = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not fetches & {"page", "history", "get_token"}, sorted(fetches)
    # Exactly one name is taken from the module that holds the transport.
    from_probe = [
        sorted(alias.name for alias in node.names)
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "tools.tos_cp3.minute_probe"
    ]
    assert from_probe == [["frame"]], from_probe


def _event(symbol: str, day: str, rows: list[dict]) -> str:
    return json.dumps(
        {"params": {"FID_INPUT_ISCD": symbol, "FID_INPUT_DATE_1": day}, "rows": rows}
    )


def _row(day: str, hhmmss: str, close: str) -> dict:
    return {
        "stck_bsop_date": day,
        "stck_cntg_hour": hhmmss,
        "futs_oprc": close,
        "futs_hgpr": close,
        "futs_lwpr": close,
        "futs_prpr": close,
        "cntg_vol": "100",
    }


def test_the_raw_reader_keeps_the_latest_page_and_drops_other_days(
    tmp_path: Path,
) -> None:
    """Pages overlap and an intraday day is re-read; the LAST reading wins.

    Both halves are load-bearing. The probes paginate backwards, so a cursor
    minute arrives twice (evidence 2026-10-14 §2.1 measured the overlap as
    exactly the page-boundary count), and the PR-1 run re-read a growing day
    524 times. ``FID_PW_DATA_INCU_YN=Y`` also carries neighbouring days, which
    would silently join the wrong session's bars onto this one.
    """
    path = tmp_path / "requests.jsonl"
    path.write_text(
        "\n".join(
            [
                _event("A05611", "20261012", [_row("20261012", "090000", "400.00")]),
                # same minute, later response: the one that must survive
                _event("A05611", "20261012", [_row("20261012", "090000", "401.00")]),
                # a neighbouring day inside this day's response
                _event("A05611", "20261012", [_row("20261009", "090000", "399.00")]),
                _event("A05610", "20261008", [_row("20261008", "151900", "1049.00")]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    raw = stitch_measure.load_raw_rows([path])
    assert set(raw) == {
        ("A05611", date(2026, 10, 12)),
        ("A05610", date(2026, 10, 8)),
    }
    rows = raw[("A05611", date(2026, 10, 12))]
    assert len(rows) == 1, "the overlapping page was not de-duplicated"
    assert rows[0]["futs_prpr"] == "401.00", "an EARLIER reading survived"
    assert raw[("A05610", date(2026, 10, 8))][0]["stck_cntg_hour"] == "151900"


def test_the_tool_refuses_a_requests_file_that_is_not_there(tmp_path: Path) -> None:
    """Exit 2 with the path named, not a traceback or a silently empty run."""
    with pytest.raises(stitch_measure.StitchMeasureError, match="no such requests"):
        stitch_measure.load_raw_rows([tmp_path / "absent.jsonl"])
    assert (
        stitch_measure.main(
            [
                "--requests",
                str(tmp_path / "absent.jsonl"),
                "--out",
                str(tmp_path / "out"),
                "--symbol",
                "A05611",
                "--previous-symbol",
                "A05610",
                "--target",
                "2026-10-12",
                "--splice-day",
                "2026-10-08",
                "--previous-day",
                "2026-10-07",
                "--compare-day",
                "2026-10-12",
                "--c-x100",
                "344",
                "--spread-range-x100",
                "118",
            ]
        )
        == 2
    )
    assert not (tmp_path / "out").exists(), "a refused run still wrote artifacts"


def test_a_missing_session_is_named_rather_than_silently_skipped(
    tmp_path: Path,
) -> None:
    """A ``(symbol, day)`` the manifest needs but no response holds.

    The failure this prevents: measuring over whatever days happen to be in
    the file and reporting the result as if it covered the requested span.
    """
    path = tmp_path / "requests.jsonl"
    path.write_text(
        _event("A05611", "20261012", [_row("20261012", "090000", "400.00")]) + "\n",
        encoding="utf-8",
    )
    inputs = stitch_measure.Inputs(
        raw=stitch_measure.load_raw_rows([path]),
        symbol="A05611",
        previous_symbol="A05610",
        strategy=None,
        contract_spec=None,
        min_bars_per_day=330,
    )
    with pytest.raises(stitch_measure.StitchMeasureError, match="A05610 2026-10-08"):
        inputs.bars("A05610", date(2026, 10, 8))


def _cli_args(tmp_path: Path, requests: Path, out: Path) -> list[str]:
    return [
        "--requests", str(requests),
        "--out", str(out),
        "--symbol", "A05611",
        "--previous-symbol", "A05610",
        "--target", "2026-10-12",
        "--splice-day", "2026-10-08",
        "--previous-day", "2026-10-07",
        "--compare-day", "2026-10-12",
        "--c-x100", "344",
        "--spread-range-x100", "118",
    ]  # fmt: skip


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        (
            ["--day-not-measured", "2026-10-14", "--day-not-measured-reason", "open"],
            ("2026-10-14", "open"),
        ),
        ([], (None, None)),
    ],
)
def test_the_day_not_measured_flags_reach_the_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    flags: list[str],
    expected: tuple[str | None, str | None],
) -> None:
    """Both halves of the flag's purpose, in one pair.

    What it exists for: a comparison day the plan asks for and the run could
    not take must be NAMED in the artifact — an absent day that is not named
    reads as a day with no difference. The second case is the half that makes
    this PR's own artifact readable: with the flags omitted the field is
    ``null``, which is the positive claim "every day the plan asks for was
    measured", not merely a missing key.

    Scope: the CLI → :func:`measure_s1b` → artifact hop. The measurements
    themselves are stubbed — a real run is the hours-long one the README's §5
    reproduces — so this says nothing about the numbers.
    """
    requests = tmp_path / "requests.jsonl"
    requests.write_text(
        _event("A05611", "20261012", [_row("20261012", "090000", "400.00")]) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        stitch_measure,
        "measure_s1a",
        lambda *a, **k: {"flips_total": 0, "flip_margin_x100": {}},
    )
    monkeypatch.setattr(
        stitch_measure,
        "measure_s1b",
        lambda inputs, **kwargs: {
            "hi_vol_differences_total": 0,
            "day_not_measured": kwargs["day_not_measured"],
            "day_not_measured_reason": kwargs["day_not_measured_reason"],
        },
    )
    out = tmp_path / "out"
    assert stitch_measure.main(_cli_args(tmp_path, requests, out) + flags) == 0
    written = json.loads((out / "CP3-PR2B-S1b.json").read_text(encoding="utf-8"))
    assert (written["day_not_measured"], written["day_not_measured_reason"]) == expected


def test_the_output_is_byte_stable(tmp_path: Path) -> None:
    """Two renders of one payload are identical — no run timestamp inside.

    Same discipline as B1a's lineage: a changed artifact must mean changed
    inputs or code, never merely a re-run.
    """
    payload = {"b": 1, "a": [1, 2], "c": {"x": True}}
    assert stitch_measure.render(payload) == stitch_measure.render(payload)
    assert b"run_started" not in stitch_measure.render(payload)
