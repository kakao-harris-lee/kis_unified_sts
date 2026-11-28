"""The committed CP-3 stock tenant trees are exactly what the declared symbol list renders.

Plan: ``docs/plans/2026-11-27-tos-p4-position-fields-plan.md`` §4 row S6. The gate is
`test_the_committed_stock_trees_are_byte_identical_to_the_render`; everything else below is
either a named failing input for it or the proof that a FOURTH symbol is one list line.

This file lives in ``tests/tools/test_tos_*`` on purpose: that battery runs in the required
``tos-firewall`` check with NO path gating, while the legacy ``test`` workflow ignores
``**.md`` — a hand edit to a generated tree's ``README.md`` alone would otherwise reach main
with no check having read it. It may not import ``tos``/``tos_runtime`` (reverse firewall),
so runtime facts are measured in a subprocess, as ``tests/unit/scripts`` already does.
Nothing is written outside ``tmp_path`` and no real account number appears.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_DIR = _REPO_ROOT / "scripts" / "tos"
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import render_paper_config as rpc  # noqa: E402
import render_stock_tenant_trees as rst  # noqa: E402

_CONFIG_ROOT = _REPO_ROOT / "config" / "tos_runtime"
_LIST = _REPO_ROOT / rst.DEFAULT_LIST
_RUNNER = _REPO_ROOT / "tools" / "tos_cp3" / "runners" / "cp3_tenant_daily.sh"

#: The role sibling every fourth-symbol assertion below compares against.
_EXPERIMENT_A = "000660"
_EXPERIMENT_A_NAME = "SK하이닉스"

#: A symbol that is NOT deployed and is never written into the repository — the whole point
#: of the fourth-symbol tests is that nothing but a list line is needed, so no tree ships.
_FOURTH_SYMBOL = "000270"
_FOURTH_NAME = "기아"
_FOURTH_ROLE = "experiment-a"

#: A well-formed, deliberately fictional account coordinate for the render-then-load proof.
_FAKE_ACCOUNT = "8888888888"

_CLI_BOOTSTRAP = (
    "import sys;from tos_runtime.compose.cli import main;sys.exit(main(sys.argv[1:]))"
)

_LOAD_TREE = """
import sys
from pathlib import Path

from tos.dsl.serialization import parse_strategy
from tos.engine.admission import strategy_admissible
from tos_runtime.compose._marketfeed_wiring import load_position_context_config
from tos_runtime.strategy.bindings import (
    STRATEGY_BINDINGS_FILE_NAME,
    load_strategy_bindings,
)
from tos_runtime.strategy.loader import load_strategies
from tos_runtime.strategy.resolve import (
    _refuse_unresolvable_position_refs,
    _resolve_bindings_or_refuse,
)

tree = Path(sys.argv[1])
loaded = load_strategies(
    tree / "strategies", parse=parse_strategy, admit=strategy_admissible
)
_resolve_bindings_or_refuse(
    loaded, load_strategy_bindings(tree / STRATEGY_BINDINGS_FILE_NAME)
)
declared = load_position_context_config(tree)
enabled = declared is not None and declared.enabled
_refuse_unresolvable_position_refs(loaded, position_context_enabled=enabled)
names = sorted(entry.path.name for entry in loaded.strategies)
print("strategies", *names, "position_context", enabled)
"""


def _files(root: Path) -> list[str]:
    return sorted(
        str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()
    )


def _spec() -> rst.StockTenants:
    return rst.load_tenants(_LIST)


def _tmp_repo(tmp_path: Path) -> Path:
    """A throwaway checkout holding only what the generator reads and writes."""
    root = tmp_path / "repo"
    (root / "config").mkdir(parents=True)
    shutil.copytree(
        _REPO_ROOT / "config" / "tos_stock_tenants",
        root / "config" / "tos_stock_tenants",
    )
    trees = root / "config" / "tos_runtime"
    trees.mkdir()
    for tree in sorted(_CONFIG_ROOT.glob("cp3-setup-d-stock-*")):
        shutil.copytree(tree, trees / tree.name)
    return root


def _check_tmp_repo(root: Path) -> list[str]:
    spec = rst.load_tenants(root / rst.DEFAULT_LIST, repo_root=root)
    return rst.check(spec, committed_root=root / "config" / "tos_runtime")


def _runtime(args: list[str]) -> subprocess.CompletedProcess[str]:
    """The tos runtime CLI/loaders in a subprocess — this file may not import them."""
    return subprocess.run(
        [sys.executable, "-B", *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(_REPO_ROOT),
        env={
            "PATH": "/usr/bin:/bin",
            "PYTHONPATH": f"{_REPO_ROOT / 'tos' / 'src'}:"
            f"{_REPO_ROOT / 'tos' / 'runtime' / 'src'}",
            "PYTHONDONTWRITEBYTECODE": "1",
            "HOME": str(Path.home()),
        },
    )


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


def test_the_committed_stock_trees_are_byte_identical_to_the_render() -> None:
    """Every shipped `cp3-setup-d-stock-*` file, byte for byte, in both directions."""
    assert rst.check(_spec(), committed_root=_CONFIG_ROOT) == []


def test_the_render_covers_every_committed_stock_tree_and_file() -> None:
    """The gate above is only worth its name if it reads the whole tree set."""
    spec = _spec()
    committed = sorted(
        path.name for path in _CONFIG_ROOT.glob("cp3-setup-d-stock-*") if path.is_dir()
    )
    assert committed == sorted(
        rst.tree_name(spec, tenant.symbol) for tenant in spec.tenants
    )
    assert len(committed) >= 3, committed
    for tenant in spec.tenants:
        tree = _CONFIG_ROOT / rst.tree_name(spec, tenant.symbol)
        assert len(_files(tree)) >= 28, tree


def test_the_list_and_the_runner_symbol_list_are_the_same_set() -> None:
    """Two lists, one fact: a rendered tree nobody runs (or the reverse) is a silent gap."""
    found = re.search(
        r'^STOCK_SYMBOLS="([^"]+)"', _RUNNER.read_text(encoding="utf-8"), re.MULTILINE
    )
    assert found is not None, _RUNNER
    assert set(found.group(1).split()) == {tenant.symbol for tenant in _spec().tenants}


# ---------------------------------------------------------------------------
# Named failing inputs for that gate
# ---------------------------------------------------------------------------


def test_a_hand_edit_of_a_generated_tree_is_reported(tmp_path: Path) -> None:
    root = _tmp_repo(tmp_path)
    edited = (
        root
        / "config/tos_runtime"
        / f"cp3-setup-d-stock-{_EXPERIMENT_A}"
        / "strategy_bindings.yaml"
    )
    edited.write_text(
        edited.read_text(encoding="utf-8").replace(
            "take_profit_bp: 150", "take_profit_bp: 900"
        ),
        encoding="utf-8",
    )
    problems = _check_tmp_repo(root)
    assert len(problems) == 1, problems
    assert "strategy_bindings.yaml" in problems[0]


def test_a_layer_edit_without_a_re_render_is_reported(tmp_path: Path) -> None:
    """The other direction: the declaration moved and the committed tree did not."""
    root = _tmp_repo(tmp_path)
    layer = root / "config/tos_stock_tenants/layers/experiment-a/strategy_bindings.yaml"
    layer.write_text(
        layer.read_text(encoding="utf-8").replace(
            "stop_loss_bp: -100", "stop_loss_bp: -250"
        ),
        encoding="utf-8",
    )
    problems = _check_tmp_repo(root)
    assert len(problems) == 1, problems
    assert f"cp3-setup-d-stock-{_EXPERIMENT_A}/strategy_bindings.yaml" in problems[0]


def test_a_committed_tree_the_list_does_not_declare_is_reported(tmp_path: Path) -> None:
    root = _tmp_repo(tmp_path)
    listing = root / rst.DEFAULT_LIST
    text = listing.read_text(encoding="utf-8")
    dropped = '  - {symbol: "005380", name: "현대차", role: "experiment-b"}\n'
    assert dropped in text, "the list's line shape moved — update this test"
    listing.write_text(text.replace(dropped, ""), encoding="utf-8")
    problems = _check_tmp_repo(root)
    assert any(
        "cp3-setup-d-stock-005380" in problem and "does not declare" in problem
        for problem in problems
    ), problems


def test_an_undeclared_symbol_occurrence_in_the_base_tree_is_refused(
    tmp_path: Path,
) -> None:
    """A base file that starts naming the canary's symbol must be declared or refused.

    # SAFETY: without this scan the short occurrence table would be a claim rather than a
    # measurement, and the new occurrence would be COPIED into every sibling — a sibling
    # policy id, or a freshness declaration, silently carrying the canary's symbol.
    """
    root = _tmp_repo(tmp_path)
    spec = rst.load_tenants(root / rst.DEFAULT_LIST, repo_root=root)
    undeclared = root / "config/tos_runtime/cp3-setup-d-stock-005930/authority.yaml"
    undeclared.write_text(
        undeclared.read_text(encoding="utf-8") + "# 005930 종목 주석\n",
        encoding="utf-8",
    )
    with pytest.raises(rst.RenderError, match="authority.yaml"):
        rst.render_all(spec, tmp_path / "out")


def test_an_unknown_token_in_a_layer_is_refused(tmp_path: Path) -> None:
    root = _tmp_repo(tmp_path)
    layer = root / "config/tos_stock_tenants/layers/experiment-a/strategy_bindings.yaml"
    layer.write_text(
        layer.read_text(encoding="utf-8") + "# {{SECTOR}}\n", encoding="utf-8"
    )
    spec = rst.load_tenants(root / rst.DEFAULT_LIST, repo_root=root)
    with pytest.raises(rst.RenderError, match="SECTOR"):
        rst.render_all(spec, tmp_path / "out")


def test_write_reproduces_the_committed_trees_in_a_throwaway_checkout(
    tmp_path: Path,
) -> None:
    """`write()` over an edited checkout puts every tree back to the render."""
    root = _tmp_repo(tmp_path)
    trees = root / "config" / "tos_runtime"
    edited = trees / f"cp3-setup-d-stock-{_EXPERIMENT_A}" / "README.md"
    edited.write_text(
        edited.read_text(encoding="utf-8") + "\n손으로 쓴 줄\n", encoding="utf-8"
    )
    spec = rst.load_tenants(root / rst.DEFAULT_LIST, repo_root=root)
    written = rst.write(spec, committed_root=trees)
    assert sorted(written) == sorted(
        rst.tree_name(spec, tenant.symbol) for tenant in spec.tenants
    )
    assert _check_tmp_repo(root) == []


def test_rendering_over_the_base_tree_itself_is_refused(tmp_path: Path) -> None:
    """Writing into the base tree would delete the source this render reads.

    # SAFETY: `write()` stages in a temp directory and swaps; rendering straight into
    # `config/tos_runtime` would rmtree the canary's committed tree — which IS the base —
    # and then render the remaining tenants from the hole it left.
    """
    root = _tmp_repo(tmp_path)
    spec = rst.load_tenants(root / rst.DEFAULT_LIST, repo_root=root)
    with pytest.raises(rst.RenderError, match="over the base tree itself"):
        rst.render_all(spec, root / "config" / "tos_runtime")
    assert _check_tmp_repo(root) == []


@pytest.mark.parametrize(
    ("line", "why"),
    [
        ('  - {symbol: "000660", name: "중복", role: "canary"}\n', "declared twice"),
        ('  - {symbol: "00066", name: "다섯자리", role: "canary"}\n', "six digits"),
        (
            '  - {symbol: "123456", name: "역할없음", role: "experiment-c"}\n',
            "role refused",
        ),
    ],
)
def test_a_malformed_list_line_is_refused(tmp_path: Path, line: str, why: str) -> None:
    listing = tmp_path / "TENANTS.yaml"
    listing.write_text(_LIST.read_text(encoding="utf-8") + line, encoding="utf-8")
    with pytest.raises(rst.RenderError, match=why):
        rst.load_tenants(listing)


# ---------------------------------------------------------------------------
# A fourth symbol is one list line
# ---------------------------------------------------------------------------


@pytest.fixture
def fourth(tmp_path: Path) -> tuple[rst.StockTenants, Path, Path]:
    """One extra LINE appended to the shipped list, rendered into ``tmp_path``."""
    listing = tmp_path / "TENANTS.yaml"
    listing.write_text(
        _LIST.read_text(encoding="utf-8")
        + f'  - {{symbol: "{_FOURTH_SYMBOL}", name: "{_FOURTH_NAME}", '
        f'role: "{_FOURTH_ROLE}"}}\n',
        encoding="utf-8",
    )
    spec = rst.load_tenants(listing)
    rendered = rst.render_all(spec, tmp_path / "trees")
    return (
        spec,
        rendered[f"cp3-setup-d-stock-{_FOURTH_SYMBOL}"],
        rendered[f"cp3-setup-d-stock-{_EXPERIMENT_A}"],
    )


def test_a_fourth_symbol_renders_the_whole_tree_from_one_line(
    fourth: tuple[rst.StockTenants, Path, Path],
) -> None:
    """Same file set as its role sibling, and every file is that sibling's with the symbol
    moved — nothing else differs, which is what "adding a symbol is one line" means."""
    _spec_unused, tree, sibling = fourth
    assert _files(tree) == _files(sibling)
    for rel in _files(tree):
        want = (
            (sibling / rel)
            .read_text(encoding="utf-8")
            .replace(_EXPERIMENT_A, _FOURTH_SYMBOL)
            .replace(_EXPERIMENT_A_NAME, _FOURTH_NAME)
        )
        assert (tree / rel).read_text(encoding="utf-8") == want, rel
    assert (tree / "strategies" / "setup_d_long.strategy.yaml").is_file()


def test_a_fourth_symbol_changes_no_other_tree(
    fourth: tuple[rst.StockTenants, Path, Path],
) -> None:
    """The list line is additive: the three shipped trees render byte-identically beside it."""
    spec, _tree, _sibling = fourth
    assert rst.check(spec, committed_root=_CONFIG_ROOT) == [
        f"cp3-setup-d-stock-{_FOURTH_SYMBOL}: declared but not committed — run --write"
    ]


def test_a_fourth_symbols_tree_loads_through_the_real_loaders(
    fourth: tuple[rst.StockTenants, Path, Path], tmp_path: Path
) -> None:
    """The generated tree, coordinate-rendered, through the deployment's own loaders.

    Two reads, both in a subprocess: ``print-policy-digests`` loads the five governed policy
    documents (so the generated policy ids, scopes and field declarations are the loaders'
    verdict, not this test's), and the strategy/bindings/position-context path is the boot
    check that a role's knobs and its rules agree.
    """
    _spec_unused, tree, _sibling = fourth
    filled = tmp_path / "filled"
    shutil.copytree(tree, filled)
    rpc.apply_rules(
        filled,
        rpc._slot_rules(
            rpc.load_manifest(tree),
            account=_FAKE_ACCOUNT,
            instrument=_FOURTH_SYMBOL,
            revision="0" * 40,
            direction="LONG",
            journal_path=tmp_path / "journal.jsonl",
            band_journal_path=tmp_path / "band.jsonl",
            broker_profile_instance_path=rpc.resolve_broker_profile_instance_path(
                _CONFIG_ROOT / "cp3-setup-d-stock-005930"
            ),
        ),
    )

    digests = _runtime(
        ["-c", _CLI_BOOTSTRAP, "print-policy-digests", "--config-dir", str(filled)]
    )
    assert digests.returncode == 0, digests.stderr
    printed = {line.split()[0] for line in digests.stdout.splitlines() if line.strip()}
    assert set(rpc.MANDATORY_POLICY_KINDS) <= printed, digests.stdout
    assert f"cp3-setup-d-stock-{_FOURTH_SYMBOL}" in digests.stdout

    loaded = _runtime(["-c", _LOAD_TREE, str(filled)])
    assert loaded.returncode == 0, loaded.stderr
    assert (
        loaded.stdout.strip()
        == "strategies setup_d_long.strategy.yaml position_context True"
    )
