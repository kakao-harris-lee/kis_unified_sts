"""``write-standing-approval`` — Monday is one command, and it refuses every non-MOCK tree."""

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
            instance = os.path.relpath(
                (_TREES / tree / raw["instance_path"]).resolve(), path.parent
            )
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
    authority = yaml.safe_load((tree / "authority.yaml").read_text(encoding="utf-8"))
    configured = authority["standing_approval_max_uses_per_action"]
    assert [a.max_uses for a in approval.actions] == [configured, configured]
    out = capsys.readouterr().out
    assert approval.digest in out
    assert "#960" not in out


def test_the_stock_trees_use_count_is_one_per_regular_session_minute() -> None:
    """Operator directive 2026-11-18 — 390 = the 09:00-15:30 one-minute bars (6.5h x 60)."""
    authority = yaml.safe_load(
        (_TREES / "cp3-setup-d-stock-005930" / "authority.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert authority["standing_approval_max_uses_per_action"] == 390


def test_the_cli_flag_overrides_the_configured_use_count(tmp_path: Path) -> None:
    tree = _rendered_copy("cp3-setup-d-stock-005930", tmp_path)
    custody = tmp_path / "custody"
    assert main(_argv(tree, custody, "--max-uses-per-action", "3")) == 0
    approval = load_standing_approval(
        custody / STANDING_APPROVAL_RELPATH, expected_owner_uid=os.getuid()
    )
    assert [a.max_uses for a in approval.actions] == [3, 3]


def test_a_tree_without_the_key_keeps_the_single_use_default(tmp_path: Path) -> None:
    tree = _rendered_copy("cp3-setup-d-stock-005930", tmp_path)
    authority_path = tree / "authority.yaml"
    authority_path.write_text(
        "".join(
            line
            for line in authority_path.read_text(encoding="utf-8").splitlines(
                keepends=True
            )
            if not line.startswith("standing_approval_max_uses_per_action:")
        ),
        encoding="utf-8",
    )
    raw = yaml.safe_load(authority_path.read_text(encoding="utf-8"))
    assert "standing_approval_max_uses_per_action" not in raw

    custody = tmp_path / "custody"
    assert main(_argv(tree, custody)) == 0
    approval = load_standing_approval(
        custody / STANDING_APPROVAL_RELPATH, expected_owner_uid=os.getuid()
    )
    assert [a.max_uses for a in approval.actions] == [1, 1]


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
