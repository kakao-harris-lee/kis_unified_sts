"""The CP-3 STOCK tenant tree ``cp3-setup-d-stock-005930`` through the real renderer (M2).

Legacy side (``tests/``): this file may not import ``tos``/``tos_runtime``, so the runtime facts
are measured in a subprocess, as ``test_render_tenant_trees.py`` does. Nothing is written
outside ``tmp_path`` and no real account number appears.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_DIR = _REPO_ROOT / "scripts" / "tos"
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import render_paper_config as rpc  # noqa: E402

_STOCK = _REPO_ROOT / "config" / "tos_runtime" / "cp3-setup-d-stock-005930"
_LONG = _REPO_ROOT / "config" / "tos_runtime" / "cp3-setup-d-long"
_FAKE_ACCOUNT = "8888888888"
_SYMBOL = "005930"

_LOAD_STRATEGY = """
import json, sys
from pathlib import Path
from tos.dsl.serialization import parse_strategy
from tos.engine.admission import strategy_admissible
from tos_runtime.strategy.loader import load_strategies

loaded = load_strategies(
    Path(sys.argv[1]) / "strategies", parse=parse_strategy, admit=strategy_admissible
)
print(json.dumps([str(item.path.name) for item in loaded.strategies]))
"""


def _journal(tmp_path: Path) -> Path:
    path = tmp_path / "upstream_journal.jsonl"
    path.write_text('{"raw_event_id": "placeholder"}\n', encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.mktemp("stock-render")
    out = base / "out"
    rpc.render(
        _STOCK,
        out,
        account=_FAKE_ACCOUNT,
        instrument=_SYMBOL,
        revision="0" * 40,
        direction="LONG",
        journal_path=_journal(base),
    )
    return out


def test_the_stock_manifest_reads_the_stock_account_key() -> None:
    assert rpc.load_manifest(_STOCK).account_env_key == "KIS_STOCK_ACCOUNT_NO"
    # Absent `account` keeps the futures key — the three futures trees are unchanged.
    assert rpc.load_manifest(_LONG).account_env_key == rpc.ACCOUNT_ENV_KEY
    assert rpc.ACCOUNT_ENV_KEY == "KIS_FUTURES_ACCOUNT_NO"


def test_an_unlisted_account_key_is_refused(tmp_path: Path) -> None:
    tree = tmp_path / "tree"
    import shutil

    shutil.copytree(_STOCK, tree)
    manifest = tree / rpc.RENDER_MANIFEST_NAME
    text = manifest.read_text(encoding="utf-8").replace(
        'env_key: "KIS_STOCK_ACCOUNT_NO"', 'env_key: "KIS_FUTURES_APP_KEY"'
    )
    manifest.write_text(text, encoding="utf-8")
    with pytest.raises(rpc.RenderError, match="account.env_key refused"):
        rpc.load_manifest(tree)


def test_the_account_parser_reads_only_the_named_key(tmp_path: Path) -> None:
    env = tmp_path / ".env.mock"
    env.write_text(
        "KIS_FUTURES_ACCOUNT_NO=11111111-01\nKIS_STOCK_ACCOUNT_NO=22222222-01\n",
        encoding="utf-8",
    )
    assert rpc.parse_account_from_env_file(env) == "11111111-01"
    assert (
        rpc.parse_account_from_env_file(env, key="KIS_STOCK_ACCOUNT_NO")
        == "22222222-01"
    )
    env.write_text("KIS_FUTURES_ACCOUNT_NO=11111111-01\n", encoding="utf-8")
    with pytest.raises(rpc.RenderError, match="KIS_STOCK_ACCOUNT_NO is not set"):
        rpc.parse_account_from_env_file(env, key="KIS_STOCK_ACCOUNT_NO")


def test_the_cli_refuses_a_stock_tree_without_an_explicit_instrument(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The renderer's default instrument is the mini FUTURES front month — never a stock."""
    env = tmp_path / ".env.mock"
    env.write_text("KIS_STOCK_ACCOUNT_NO=22222222-01\n", encoding="utf-8")
    rc = rpc.main(
        [
            "--source",
            str(_STOCK),
            "--out",
            str(tmp_path / "out"),
            "--env-file",
            str(env),
            "--direction",
            "LONG",
            "--journal-path",
            str(_journal(tmp_path)),
        ]
    )
    assert rc == 1
    assert "must be given --instrument" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_the_stock_render_activates_five_policy_kinds(rendered: Path) -> None:
    payload = json.loads((rendered / rpc.RENDERED_NAME).read_text(encoding="utf-8"))
    assert {entry["kind"] for entry in payload["policy_digests"]} == {
        "VENUE_CONSTRAINT_POLICY",
        "ORDER_CONSTRUCTION_POLICY",
        "AGGREGATE_RISK_POLICY",
        "ACTION_FLOW_POLICY",
        "CRITICAL_INPUT_POLICY",
    }
    assert payload["activation_check"]
    assert payload["tree_id"] == "cp3-setup-d-stock-005930"
    assert payload["instrument"] == _SYMBOL
    assert _FAKE_ACCOUNT not in (rendered / rpc.RENDERED_NAME).read_text("utf-8")
    assert rpc.check(_STOCK, rendered) == []


def test_every_instrument_slot_carries_the_symbol(rendered: Path) -> None:
    for name, keys in (
        ("construction.yaml", ("instrument",)),
        ("marketfeed.yaml", ("instruments",)),
    ):
        document = yaml.safe_load((rendered / name).read_text(encoding="utf-8"))
        for key in keys:
            value = document[key]
            assert value in (_SYMBOL, [_SYMBOL]), (name, key, value)
    vcp = yaml.safe_load(
        (rendered / "venue_constraint_policy.yaml").read_text(encoding="utf-8")
    )
    assert vcp["scope"]["instruments"] == [_SYMBOL]
    assert vcp["_runtime"].get("band_source") is None


def test_the_rendered_stock_strategy_loads_through_the_production_loader(
    rendered: Path,
) -> None:
    completed = subprocess.run(
        [sys.executable, "-B", "-c", _LOAD_STRATEGY, str(rendered)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(_REPO_ROOT),
        env=rpc._subprocess_env(),
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == ["setup_d_long.strategy.yaml"]
