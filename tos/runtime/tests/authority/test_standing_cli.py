"""``write-standing-approval`` — Monday is one command, and it refuses every non-MOCK tree.

Runs against copies of the committed tenant trees with the deployment coordinates the renderer
would fill (account / instrument), so the derived ``strategy_id`` is a real content digest of
the tree's own strategy. Nothing outside ``tmp_path`` is written.
"""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path

import pytest
import yaml
from tos_runtime.authority.standing import (
    STANDING_APPROVAL_RELPATH,
    load_standing_approval,
)
from tos_runtime.compose.cli import main

_REPO = Path(__file__).resolve().parents[4]
_TREES = _REPO / "config" / "tos_runtime"
_ACCOUNT = "50000000-01"
_INSTRUMENT = "005930"


def _rendered_copy(tree: str, tmp_path: Path) -> Path:
    """Copy ``tree`` and fill the coordinates the renderer fills (account / instrument)."""
    dest = tmp_path / tree
    shutil.copytree(_TREES / tree, dest)
    for path in dest.rglob("*.yaml"):
        text = path.read_text(encoding="utf-8")
        text = text.replace('accounts: ["TBD"]', f'accounts: ["{_ACCOUNT}"]')
        text = text.replace('instruments: ["TBD"]', f'instruments: ["{_INSTRUMENT}"]')
        text = text.replace(
            'account: &account "TBD"', f'account: &account "{_ACCOUNT}"'
        )
        text = text.replace(
            'instrument: &instrument "TBD"', f'instrument: &instrument "{_INSTRUMENT}"'
        )
        if path.name == "construction.yaml":
            text = text.replace('account: "TBD"', f'account: "{_ACCOUNT}"')
            text = text.replace('instrument: "TBD"', f'instrument: "{_INSTRUMENT}"')
        if path.name == "broker_scopes.yaml":
            raw = yaml.safe_load(text)
            instance = (_TREES / tree / raw["instance_path"]).resolve()
            text = text.replace(
                f"instance_path: {raw['instance_path']}", f"instance_path: {instance}"
            )
        path.write_text(text, encoding="utf-8")
    return dest


def _argv(config_dir: Path, custody_root: Path, *extra: str) -> list[str]:
    return [
        "write-standing-approval",
        "--config-dir",
        str(config_dir),
        "--custody-root",
        str(custody_root),
        "--environment-label",
        "paper",
        "--trading-date",
        "2026-10-26",
        *extra,
    ]


def test_writes_the_artifact_for_the_mock_stock_tree(tmp_path: Path, capsys) -> None:
    tree = _rendered_copy("cp3-setup-d-stock-005930", tmp_path)
    custody = tmp_path / "custody"
    assert main(_argv(tree, custody)) == 0

    path = custody / STANDING_APPROVAL_RELPATH
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    approval = load_standing_approval(path, expected_owner_uid=os.getuid())
    assert approval.trading_date == "20261026"
    assert approval.instrument == _INSTRUMENT
    assert approval.max_quantity == 1
    assert approval.strategy_id.startswith("astrat-")
    release = yaml.safe_load((tree / "release.yaml").read_text(encoding="utf-8"))
    assert approval.code_digest == release["expected_code_digest"]
    # entry = construction.yaml's own side; exit = the OCP's (CLOSE, LONG) shape and the
    # strategy's own CLOSE target direction — one use each.
    construction = yaml.safe_load(
        (tree / "construction.yaml").read_text(encoding="utf-8")
    )
    entry, exit_ = approval.actions
    assert (entry.position_effect, entry.direction, entry.side) == (
        "OPEN",
        "LONG",
        construction["outbound_side"],
    )
    assert (exit_.position_effect, exit_.direction) == ("CLOSE", "SHORT")
    assert exit_.side != entry.side
    assert [a.max_uses for a in approval.actions] == [1, 1]
    out = capsys.readouterr().out
    assert approval.digest in out
    assert "exit row cannot match until #960" in out


@pytest.mark.parametrize("tree", ["cp3-setup-d-long", "cp3-setup-d-short"])
def test_refuses_every_non_mock_tree_and_writes_nothing(
    tree: str, tmp_path: Path, capsys
) -> None:
    config_dir = _rendered_copy(tree, tmp_path)
    custody = tmp_path / "custody"
    assert main(_argv(config_dir, custody)) == 1
    assert "MOCK-only" in capsys.readouterr().err
    assert not (custody / STANDING_APPROVAL_RELPATH).exists()


def test_refuses_to_overwrite_without_replace(tmp_path: Path) -> None:
    tree = _rendered_copy("cp3-setup-d-stock-005930", tmp_path)
    custody = tmp_path / "custody"
    assert main(_argv(tree, custody)) == 0
    first = (custody / STANDING_APPROVAL_RELPATH).read_bytes()
    assert main(_argv(tree, custody, "--max-quantity", "2")) == 1
    assert (custody / STANDING_APPROVAL_RELPATH).read_bytes() == first
    assert main(_argv(tree, custody, "--actions", "entry", "--replace")) == 0
    approval = load_standing_approval(
        custody / STANDING_APPROVAL_RELPATH, expected_owner_uid=os.getuid()
    )
    assert [a.position_effect for a in approval.actions] == ["OPEN"]
