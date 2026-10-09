"""Unit tests for ``scripts/tos/render_paper_config.py`` (TOS paper 좌표 주입 스크립트).

Design: ``docs/plans/2026-09-23-tos-paper-coordinates-and-first-boot-design.md`` §2 — every
row of that section's 가드 table ("이것이 실패하는 구체적 입력") has a failing-input test here.

**These tests live under the LEGACY ``tests/`` tree on purpose** (design §4 item 1): the script
is outside ``tos/`` and is gated by the legacy ``test`` workflow, not by ``tos-gate``.

**No real account number ever appears here.** Every test drives the internal
:func:`render` with the fake value ``9999999999`` / ``99999999-99``; the CLI's own env-file
path is exercised only for its REFUSALS. The design's guard "계좌 원천이 모의 파일" is pinned by
``test_cli_refuses_an_env_file_that_is_not_env_mock``.

**Firewall**: this file is outside ``tos/`` and therefore must not import ``tos`` or
``tos_runtime`` (``tools/tos_firewall_check.py`` rule (e)/TOS-FW-R). Where a runtime fact is
needed it is measured through a SUBPROCESS, exactly as the script itself does.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_DIR = _REPO_ROOT / "scripts" / "tos"
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import render_paper_config as rpc  # noqa: E402

_SOURCE = _REPO_ROOT / "config" / "tos_runtime" / "paper"

#: A fake account, never a real one. Ten digits, the length the guard requires.
_FAKE_ACCOUNT = "9999999999"
#: The same fake account in the hyphenated shape ``.env.mock`` actually stores.
_FAKE_ACCOUNT_HYPHENATED = "99999999-99"
_FAKE_INSTRUMENT = "A05610"
_FAKE_REVISION = "0" * 40


def _render(
    out: Path, *, direction: str = "LONG", source: Path = _SOURCE
) -> rpc.RenderResult:
    return rpc.render(
        source,
        out,
        account=_FAKE_ACCOUNT,
        instrument=_FAKE_INSTRUMENT,
        revision=_FAKE_REVISION,
        direction=direction,
    )


def _source_copy(tmp_path: Path) -> Path:
    dest = tmp_path / "source"
    shutil.copytree(_SOURCE, dest)
    return dest


def _resident_manifest_dict() -> dict[str, Any]:
    """The committed resident ``RENDER.yaml``, as a plain mutable mapping."""
    raw = yaml.safe_load(
        (_SOURCE / rpc.RENDER_MANIFEST_NAME).read_text(encoding="utf-8")
    )
    assert isinstance(raw, dict)
    return raw


def _tree_with_manifest(
    parent: Path, manifest: dict[str, Any], *, name: str = "tree"
) -> Path:
    """A copy of the resident tree whose ``RENDER.yaml`` is replaced by ``manifest``.

    Design §4.2's tenant cases need a tree that declares ``declared``/``external`` modes, and
    no tenant manifest is committed yet (that is PR-B). Re-manifesting the resident VALUES is
    the smallest fixture that exercises the modes without inventing a second value tree.
    """
    tree = parent / name
    shutil.copytree(_SOURCE, tree)
    (tree / rpc.RENDER_MANIFEST_NAME).write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return tree


def _slot_index(manifest: dict[str, Any], file_name: str, key: str) -> int:
    for index, slot in enumerate(manifest["slots"]):
        if slot["file"] == file_name and slot["key"] == key:
            return index
    raise AssertionError(f"no slot {file_name}::{key} in the manifest")


# ---------------------------------------------------------------------------
# Happy path — the coordinate slots, and only those, are filled
# ---------------------------------------------------------------------------


def test_render_fills_every_registered_coordinate_slot(tmp_path: Path) -> None:
    result = _render(tmp_path / "out")

    assert set(result.rendered_keys) == set(rpc.COORDINATE_RULE_KEYS)
    text = (result.out / "construction.yaml").read_text(encoding="utf-8")
    assert f'account: "{_FAKE_ACCOUNT}"' in text
    assert f'instrument: "{_FAKE_INSTRUMENT}"' in text
    # No named-TBD placeholder survives on a VALUE line (the header comments explain the
    # convention and legitimately spell the token).
    value_lines = [
        line
        for line in text.split("\n")
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert not [line for line in value_lines if "TBD" in line], value_lines
    venue = (result.out / "venue_constraint_policy.yaml").read_text(encoding="utf-8")
    assert f'  accounts: ["{_FAKE_ACCOUNT}"]' in venue
    assert f'  instruments: ["{_FAKE_INSTRUMENT}"]' in venue
    finality = (result.out / "finality.yaml").read_text(encoding="utf-8")
    assert f'source_revision: "{_FAKE_REVISION}"' in finality


def test_render_derives_members_and_reads_them_back_activated(tmp_path: Path) -> None:
    """Design §2 step 6: ``members`` is DERIVED (never hand-written) and the render refuses
    unless a FRESH process re-deriving each policy's digest finds every member activated.
    """
    result = _render(tmp_path / "out")

    kinds = [kind for kind, _id, _gen, _digest in result.policy_digests]
    for mandatory in rpc.MANDATORY_POLICY_KINDS:
        assert mandatory in kinds
    activation = (result.out / "safety_activation.yaml").read_text(encoding="utf-8")
    assert "members: null" not in activation
    assert activation.count("resolved: true") == len(result.policy_digests)
    assert activation.count("immutable: true") == len(result.policy_digests)
    assert result.activation_check.startswith(f"ACTIVATED {len(result.policy_digests)}")


def test_rendered_manifest_carries_a_fingerprint_and_never_the_account(
    tmp_path: Path,
) -> None:
    result = _render(tmp_path / "out")

    manifest_text = (result.out / rpc.RENDERED_NAME).read_text(encoding="utf-8")
    assert _FAKE_ACCOUNT not in manifest_text
    manifest = json.loads(manifest_text)
    assert manifest["account_fingerprint"] == result.account_fingerprint
    assert manifest["source_revision"] == _FAKE_REVISION
    assert manifest["direction"] == "LONG"


def test_render_writes_a_journal_the_marketfeed_config_points_at(
    tmp_path: Path,
) -> None:
    """Design §4 item 5: the tick source is a render-time GENERATED local journal, never a
    network source and never a committed file."""
    result = _render(tmp_path / "out")

    assert result.journal_path.is_file()
    observation = json.loads(result.journal_path.read_text(encoding="utf-8").strip())
    assert observation["instrument"] == _FAKE_INSTRUMENT
    assert observation["as_of_ms"] == result.journal_as_of_ms
    assert set(observation["fields"]) == {"close", "lower_band", "upper_band"}
    marketfeed = (result.out / "marketfeed.yaml").read_text(encoding="utf-8")
    assert f'journal_path: "{result.journal_path}"' in marketfeed
    assert f'instruments: ["{_FAKE_INSTRUMENT}"]' in marketfeed


def test_direction_short_swaps_every_direction_bound_slot(tmp_path: Path) -> None:
    """Operator choice (가): the SHORT variant is produced by a render flag, never by a second
    committed copy. Every direction-bound slot moves together or the fixture is asymmetric.
    """
    result = _render(tmp_path / "out", direction="SHORT")

    construction = (result.out / "construction.yaml").read_text(encoding="utf-8")
    assert 'action_class: "NEW_SHORT"' in construction
    assert 'outbound_side: "SELL"' in construction
    ocp = (result.out / "order_construction_policy.yaml").read_text(encoding="utf-8")
    assert '        value: "SHORT"' in ocp
    strategy = (result.out / "strategies" / "bootproof_band.strategy.yaml").read_text(
        encoding="utf-8"
    )
    assert '          direction: "SHORT"' in strategy
    marketfeed = (result.out / "marketfeed.yaml").read_text(encoding="utf-8")
    assert 'direction: "SHORT"' in marketfeed
    # And nothing LONG-shaped survives anywhere the swap was supposed to reach.
    assert 'action_class: "NEW_LONG"' not in construction
    assert 'outbound_side: "BUY"' not in construction


def test_check_passes_on_a_freshly_rendered_directory(tmp_path: Path) -> None:
    out = tmp_path / "out"
    _render(out)
    assert rpc.check(_SOURCE, out) == []


# ---------------------------------------------------------------------------
# Design §2 guard table — one failing-input test per row
# ---------------------------------------------------------------------------


def test_guard_every_rule_anchor_occurs_exactly_once_in_the_committed_source() -> None:
    """Guard "칸마다 정확히 1회 매칭", positive half: the committed source must actually carry
    each anchor exactly once, or the render refuses.

    ⚠ **Retargeted at the MANIFEST** (PR #888 review L2). It used to build its anchors from
    ``_coordinate_rules``, which since the manifest landed is a transition reference nothing
    executes — so it was asserting something true of a table ``render()`` no longer reads. The
    anchors now come from ``RENDER.yaml`` itself, which is what ``render()`` and ``check()``
    both use. ``load_manifest`` validates template SHAPE but never opens the target file, so
    this is the only place "the anchor is really in the committed tree, exactly once" is
    checked before a render.
    """
    manifest = rpc.load_manifest(_SOURCE)
    anchored = [(slot.file, slot.rule_key, slot.anchor) for slot in manifest.slots]
    members = rpc._members_rule("members: x")
    anchored.append((members.file, members.key, members.anchor))
    for file_name, key, anchor in anchored:
        lines = (_SOURCE / file_name).read_text(encoding="utf-8").split("\n")
        assert [line for line in lines if line == anchor] == [
            anchor
        ], f"{key}: anchor {anchor!r} does not occur exactly once in {file_name}"


@pytest.mark.parametrize(
    ("file_name", "anchor", "key"),
    [
        (
            "venue_constraint_policy.yaml",
            '  accounts: ["TBD"]',
            "venue_constraint_policy.yaml::scope.accounts",
        ),
        ("construction.yaml", 'account: "TBD"', "construction.yaml::account"),
        ("marketfeed.yaml", 'account: "TBD"', "marketfeed.yaml::account"),
    ],
)
def test_guard_a_missing_anchor_refuses(
    tmp_path: Path, file_name: str, anchor: str, key: str
) -> None:
    """Guard "칸마다 정확히 1회 매칭": zero matches refuses, naming the rule and the anchor."""
    source = _source_copy(tmp_path)
    path = source / file_name
    lines = [
        line for line in path.read_text(encoding="utf-8").split("\n") if line != anchor
    ]
    path.write_text("\n".join(lines), encoding="utf-8")

    with pytest.raises(rpc.RenderError, match="matched 0 times"):
        _render(tmp_path / "out", source=source)


def test_guard_a_duplicated_anchor_refuses(tmp_path: Path) -> None:
    """Guard "칸마다 정확히 1회 매칭": two matches refuses too — a second, unnoticed slot would
    otherwise be filled (or silently skipped) depending on replacement order."""
    source = _source_copy(tmp_path)
    path = source / "construction.yaml"
    text = path.read_text(encoding="utf-8")
    path.write_text(text + '\naccount: "TBD"\n', encoding="utf-8")

    with pytest.raises(rpc.RenderError, match="matched 2 times"):
        _render(tmp_path / "out", source=source)


def test_guard_coordinate_rule_key_set_is_pinned() -> None:
    """Guard "좌표 칸만 바뀐다": the exact set of slots the script may rewrite, pinned by name.

    Adding a rule that rewrites a value nobody approved turns this RED — the rule table cannot
    grow silently.

    ⚠ **Retargeted at what ``render()`` actually writes** (PR #888 review L2). It used to pin
    ``COORDINATE_RULE_KEYS``, a transition reference nothing executes any more. The set now
    comes from the manifest ``render()`` reads PLUS the derived ``members`` key taken from
    :func:`render_paper_config._members_rule` itself — which makes this the only pin covering
    ``members``, since that slot is deliberately not in the manifest and therefore not in
    ``_EXPECTED_RESIDENT_SLOTS``.
    """
    rendered_keys = {slot.rule_key for slot in rpc.load_manifest(_SOURCE).slots}
    rendered_keys.add(rpc._members_rule("members: x").key)
    assert rendered_keys == {
        "venue_constraint_policy.yaml::scope.accounts",
        "venue_constraint_policy.yaml::scope.instruments",
        "order_construction_policy.yaml::scope.accounts",
        "order_construction_policy.yaml::scope.instruments",
        "order_construction_policy.yaml::_runtime.construction.axes.DIRECTION",
        "aggregate_risk_policy.yaml::account_scope",
        "aggregate_risk_policy.yaml::instrument_scope",
        "action_flow_policy.yaml::account_scope",
        "construction.yaml::account",
        "construction.yaml::instrument",
        "construction.yaml::action_class",
        "construction.yaml::outbound_side",
        "strategies/bootproof_band.strategy.yaml::policy.rules[0].decision.target.account",
        "strategies/bootproof_band.strategy.yaml::policy.rules[0].decision.target.instrument",
        "strategies/bootproof_band.strategy.yaml::policy.rules[0].decision.target.direction",
        "marketfeed.yaml::instruments",
        "marketfeed.yaml::account",
        "marketfeed.yaml::direction",
        "marketfeed.yaml::journal_path",
        "finality.yaml::source_revision",
        "safety_activation.yaml::members",
    }


def test_guard_check_reports_an_edit_outside_a_coordinate_slot(tmp_path: Path) -> None:
    """Guard "좌표 칸만 바뀐다", the ``--check`` half: a hand edit anywhere else is named."""
    out = tmp_path / "out"
    _render(out)
    calendar = out / "calendar.yaml"
    calendar.write_text(
        calendar.read_text(encoding="utf-8").replace(
            'tz_id: "Asia/Seoul"', 'tz_id: "UTC"'
        ),
        encoding="utf-8",
    )

    problems = rpc.check(_SOURCE, out)
    assert any("calendar.yaml" in problem for problem in problems), problems


def test_guard_check_reports_an_unexpected_extra_file(tmp_path: Path) -> None:
    out = tmp_path / "out"
    _render(out)
    (out / "smuggled.yaml").write_text("x: 1\n", encoding="utf-8")

    assert any("smuggled.yaml" in problem for problem in rpc.check(_SOURCE, out))


def test_guard_cli_refuses_an_env_file_that_is_not_env_mock(tmp_path: Path) -> None:
    """Guard "계좌 원천이 모의 파일" — the pin the design names explicitly:
    ``main(["--env-file", "<tmp>/.env"])`` → exit code 2.

    ``.env`` carries the REAL futures account, which this repo's non-negotiable rules keep off
    every order path. There is deliberately no test-only override flag."""
    env_path = tmp_path / ".env"
    env_path.write_text("KIS_FUTURES_ACCOUNT_NO=9999999999\n", encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        rpc.main(["--env-file", str(env_path), "--out", str(tmp_path / "out")])
    assert excinfo.value.code == 2


def test_guard_cli_refuses_env_real_too(tmp_path: Path) -> None:
    env_path = tmp_path / ".env.real"
    env_path.write_text("KIS_FUTURES_ACCOUNT_NO=9999999999\n", encoding="utf-8")

    with pytest.raises(SystemExit) as excinfo:
        rpc.main(["--env-file", str(env_path), "--out", str(tmp_path / "out")])
    assert excinfo.value.code == 2


@pytest.mark.parametrize("raw", ["999999999", "99999999999", "", "99999999-9"])
def test_guard_account_format_refuses_anything_but_ten_digits(raw: str) -> None:
    """Guard "계좌 형식": the hyphen is stripped, then the digit count must be exactly ten."""
    with pytest.raises(rpc.RenderError, match="account coordinate refused"):
        rpc.normalize_account(raw)


def test_guard_account_format_never_echoes_the_value() -> None:
    """A refusal message that printed the rejected value would leak an account number into
    logs — the one thing this script exists to avoid."""
    with pytest.raises(rpc.RenderError) as excinfo:
        rpc.normalize_account("12345678-9")
    assert "12345678" not in str(excinfo.value)


def test_account_is_normalized_to_digits_only_keeping_all_ten(tmp_path: Path) -> None:
    """The measured normalization (see :func:`render_paper_config.normalize_account`'s own
    docstring): no tos loader validates the FORMAT at all — they accept any non-empty,
    non-``"TBD"`` string — so the hyphen question is settled once, here, and the SAME string
    goes into every slot. Digits only, all ten: the trailing two are the product code that
    makes this the FUTURES account."""
    assert rpc.normalize_account(_FAKE_ACCOUNT_HYPHENATED) == _FAKE_ACCOUNT
    assert rpc.normalize_account(_FAKE_ACCOUNT) == _FAKE_ACCOUNT


def test_env_file_parsing_reads_only_the_one_key_and_never_os_environ(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Design §2 step 2: the file is parsed directly, so an ambient variable can neither
    supply nor override the coordinate, and ``os.environ`` is not polluted."""
    monkeypatch.setenv("KIS_FUTURES_ACCOUNT_NO", "1111111111")
    env_path = tmp_path / ".env.mock"
    env_path.write_text(
        "# comment\n"
        "KIS_STOCK_ACCOUNT_NO=0000000000\n"
        f"export KIS_FUTURES_ACCOUNT_NO='{_FAKE_ACCOUNT_HYPHENATED}'\n"
        "KIS_APP_SECRET=should-never-be-read\n",
        encoding="utf-8",
    )

    assert rpc.parse_account_from_env_file(env_path) == _FAKE_ACCOUNT_HYPHENATED
    assert os.environ["KIS_FUTURES_ACCOUNT_NO"] == "1111111111"


def test_env_file_parsing_refuses_a_missing_key(tmp_path: Path) -> None:
    env_path = tmp_path / ".env.mock"
    env_path.write_text("KIS_STOCK_ACCOUNT_NO=0000000000\n", encoding="utf-8")

    with pytest.raises(rpc.RenderError, match="is not set"):
        rpc.parse_account_from_env_file(env_path)


def test_guard_output_inside_the_repository_worktree_refuses(tmp_path: Path) -> None:
    """Guard "출력이 저장소 밖": one missing gitignore line would commit the account number."""
    with pytest.raises(rpc.RenderError, match="inside the repository worktree"):
        _render(_REPO_ROOT / "build" / "tos-paper-config")


def test_guard_output_directory_that_is_not_ours_refuses(tmp_path: Path) -> None:
    """A non-empty directory with no ``RENDERED.json`` is not one this script produced —
    refusing to ``rmtree`` it is the difference between a render and a data loss."""
    out = tmp_path / "out"
    out.mkdir()
    (out / "someone-elses-file.txt").write_text("keep me\n", encoding="utf-8")

    with pytest.raises(rpc.RenderError, match="refusing to overwrite"):
        _render(out)


def test_guard_render_leaves_the_repository_byte_identical(
    tmp_path: Path, requires_repo_checkout: None
) -> None:
    """Guard "렌더가 저장소에 아무것도 남기지 않는다" (design §2, review-795 HIGH-3).

    Runs the REAL CLI inside a throwaway ``git clone`` of this repository and asserts
    ``git status --porcelain --ignored`` is byte-identical before and after. Bytecode is
    disabled in BOTH the script and its subprocesses (``PYTHONDONTWRITEBYTECODE=1`` + ``-B``)
    because ``__pycache__`` is gitignored and would otherwise show up under ``--ignored``.

    A mutation that removes the output-path check, or points the output inside the repo, makes
    new files appear here and turns this RED. The account used is the fake ``9999999999``.

    ``requires_repo_checkout`` (``tests/conftest.py``) is the precondition: this needs a
    clonable work tree, and the ``Dockerfile.test`` image deliberately has none. It skips
    there and ONLY there — see ``tests/support/git_env.py`` for why a bare "no repo -> skip"
    would have been a hole on the real gates (#835).
    """
    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(_REPO_ROOT), str(clone)],
        check=True,
        capture_output=True,
    )
    # ⚠ A clone carries COMMITTED content only. Without this check the test would silently
    # exercise the committed script while the author edited an uncommitted one — passing for
    # a version nobody ran. (Measured: the mutation harness used to land this arc reported a
    # false GREEN for exactly this reason.) CI always has it committed, so this only ever
    # fires locally, which is precisely where it is needed.
    cloned_script = clone / "scripts" / "tos" / "render_paper_config.py"
    assert (
        cloned_script.read_bytes()
        == (_REPO_ROOT / "scripts" / "tos" / "render_paper_config.py").read_bytes()
    ), (
        "render_paper_config.py has uncommitted changes — this test would exercise the "
        "COMMITTED version and prove nothing about the edited one. Commit first."
    )
    # `.env.mock` is never committed; the CLI needs one with that exact basename.
    (clone / ".env.mock").write_text(
        f"KIS_FUTURES_ACCOUNT_NO='{_FAKE_ACCOUNT_HYPHENATED}'\n", encoding="utf-8"
    )

    def _status() -> str:
        return subprocess.run(
            ["git", "-C", str(clone), "status", "--porcelain", "--ignored"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    before = _status()
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            str(clone / "scripts" / "tos" / "render_paper_config.py"),
            "--out",
            str(tmp_path / "out"),
            "--env-file",
            str(clone / ".env.mock"),
            "--instrument",
            _FAKE_INSTRUMENT,
        ],
        capture_output=True,
        text=True,
        check=False,
        env={
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", str(tmp_path)),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )
    after = _status()

    assert after == before, (
        f"the render changed the repository:\n--- before ---\n{before}\n"
        f"--- after ---\n{after}\n--- stderr ---\n{completed.stderr}"
    )
    assert completed.returncode == 0, completed.stderr
    assert _FAKE_ACCOUNT not in completed.stdout
    assert "fingerprint=" in completed.stdout


# ---------------------------------------------------------------------------
# A failed render leaves nothing behind (review-797 MEDIUM-2)
# ---------------------------------------------------------------------------


#: Every point in :func:`render` AFTER the first account byte reaches the disk, as a
#: ``(name, install)`` pair. ``install`` monkeypatches ONE statement boundary to fail.
#:
#: The list is the whole protected window, in execution order — coordinate substitution, the
#: members write, the read-back, the fingerprint, the manifest write, and each of the three
#: renames inside the swap. The first cut of this suite injected at ``_verify_activation``
#: ALONE, which sat comfortably inside the ``try`` and therefore proved nothing about the
#: tail; the reviewer injected at the first uncovered statement and got a hidden
#: ``.paper-config.partial-<pid>`` holding seven account-bearing files.
def _fail_inside_apply_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail PART WAY through the first coordinate substitution — the account is on disk in
    some files but not others, which no whole-function hook can reproduce."""
    real = rpc._apply_rules

    def _partial(config_dir: Path, rules: Iterable[rpc.Rule]) -> None:
        ordered = list(rules)
        real(config_dir, ordered[:1])
        raise rpc.RenderError("injected: part way through coordinate substitution")

    monkeypatch.setattr(rpc, "_apply_rules", _partial)


def _fail_after_first_apply_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail on the SECOND ``_apply_rules`` call (the members write), after every coordinate
    slot is already filled."""
    real = rpc._apply_rules
    calls = {"n": 0}

    def _counted(config_dir: Path, rules: Iterable[rpc.Rule]) -> None:
        calls["n"] += 1
        if calls["n"] == 2:
            raise rpc.RenderError("injected: at the members write")
        real(config_dir, rules)

    monkeypatch.setattr(rpc, "_apply_rules", _counted)


def _fail_in_digests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        rpc,
        "_policy_digest_lines",
        lambda _dir: (_ for _ in ()).throw(
            rpc.RenderError("injected: at print-policy-digests")
        ),
    )


def _fail_in_verify(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        rpc,
        "_verify_activation",
        lambda *_a, **_k: (_ for _ in ()).throw(
            rpc.RenderError("injected: at the activation read-back")
        ),
    )


def _fail_in_fingerprint(monkeypatch: pytest.MonkeyPatch) -> None:
    """The FIRST statement the first cut left unprotected."""
    monkeypatch.setattr(
        rpc,
        "account_fingerprint",
        lambda _account: (_ for _ in ()).throw(
            RuntimeError("injected: while fingerprinting")
        ),
    )


def _fail_in_manifest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        rpc,
        "_write_rendered_manifest",
        lambda *_a, **_k: (_ for _ in ()).throw(
            OSError("injected: writing RENDERED.json (ENOSPC-shaped)")
        ),
    )


def _fail_at_nth_replace(monkeypatch: pytest.MonkeyPatch, n: int) -> None:
    """Fail at the n-th ``os.replace`` inside :func:`render_paper_config._publish`."""
    real = rpc.os.replace
    calls = {"n": 0}

    def _counted(src, dst, **kwargs):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] == n:
            raise OSError(f"injected: at os.replace call #{n}")
        return real(src, dst, **kwargs)

    monkeypatch.setattr(rpc.os, "replace", _counted)


def _fail_in_publish_rmtree(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail while removing the PREVIOUS render, after the swap already succeeded."""
    real = rpc.shutil.rmtree

    def _boom(path, *args, **kwargs):  # type: ignore[no-untyped-def]
        if rpc._REPLACED_KIND in Path(path).name and not kwargs.get("ignore_errors"):
            raise OSError("injected: removing the previous render")
        return real(path, *args, **kwargs)

    monkeypatch.setattr(rpc.shutil, "rmtree", _boom)


_FAILURE_POINTS: list[tuple[str, Callable[[pytest.MonkeyPatch], None]]] = [
    ("inside-coordinate-substitution", _fail_inside_apply_rules),
    ("at-the-members-write", _fail_after_first_apply_rules),
    ("at-print-policy-digests", _fail_in_digests),
    ("at-the-activation-read-back", _fail_in_verify),
    ("in-account-fingerprint", _fail_in_fingerprint),
    ("writing-RENDERED.json", _fail_in_manifest),
    # With a FRESH `out` the swap is a single rename (there is no previous render to move
    # aside), so that is the only rename this parametrization can reach. The other two
    # renames — the move-aside and the roll-back — exist only when `out` already holds a
    # render, and they are covered by
    # `test_a_failed_swap_rolls_the_previous_render_back` /
    # `test_a_failure_while_removing_the_previous_render_is_reported_not_swallowed`, where
    # "no account bytes anywhere" is deliberately NOT the assertion (the previous render
    # legitimately holds them).
    ("at-the-rename-of-the-swap", lambda mp: _fail_at_nth_replace(mp, 1)),
]


def _account_bearing_files(root: Path) -> list[str]:
    return sorted(
        str(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file()
        and _FAKE_ACCOUNT in path.read_text(encoding="utf-8", errors="ignore")
    )


def _working_dirs(parent: Path) -> list[str]:
    return sorted(p.name for p in parent.iterdir() if p.name.startswith("."))


@pytest.mark.parametrize(
    ("label", "install"), _FAILURE_POINTS, ids=[name for name, _ in _FAILURE_POINTS]
)
def test_a_failure_at_any_point_after_the_account_is_written_leaves_no_account_on_disk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    label: str,
    install: Callable[[pytest.MonkeyPatch], None],
) -> None:
    """**The universal claim, tested universally.**

    Every point after the first account byte reaches the disk is injected with a failure, and
    each must leave: no output directory, no working directory, and no file anywhere under the
    output's parent carrying the account.

    This replaces a single-point test whose name made the same universal claim while injecting
    at ONE statement well inside the protected window — the exact shape of defect this repo
    keeps hitting ("a guard that admits what it says it blocks"). The reviewer demonstrated
    the gap by injecting at the first uncovered statement.
    """
    out = tmp_path / "out"
    install(monkeypatch)

    with pytest.raises((rpc.RenderError, OSError, RuntimeError)):
        _render(out)

    assert not out.exists(), f"{label}: the failed render left {out} behind"
    assert _working_dirs(tmp_path) == [], f"{label}: working directory survived"
    assert _account_bearing_files(tmp_path) == [], f"{label}: account bytes survived"


def test_a_failure_while_removing_the_previous_render_is_reported_not_swallowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The one failure point where the render itself SUCCEEDED.

    After the swap, ``out`` is correct — but the directory holding the PREVIOUS render's
    account coordinate is still there. Silently returning would leave an account-bearing tree
    with no one told, so this raises, names the path, and the caller's cleanup removes it.
    """
    out = tmp_path / "out"
    _render(out)  # a previous render to be replaced
    _fail_in_publish_rmtree(monkeypatch)

    with pytest.raises(rpc.RenderError, match="PREVIOUS render could not be removed"):
        _render(out)

    # The new render is in place (the swap succeeded) and the predecessor is gone: the
    # caller's `except` removed it after the message named it.
    assert (out / rpc.RENDERED_NAME).is_file()
    assert _working_dirs(tmp_path) == []


def test_a_failed_swap_rolls_the_previous_render_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the swap fails midway, the PREVIOUS render must still be at ``out``.

    ``rmtree(out)`` followed by ``move(staging, out)`` — the obvious implementation — has a
    window where the old render is already destroyed and the new one is not yet there. The
    rename-aside/rename-in/remove ordering has no such window, and this proves it by failing
    the second rename.
    """
    out = tmp_path / "out"
    first = _render(out)
    before = (out / rpc.RENDERED_NAME).read_text(encoding="utf-8")

    _fail_at_nth_replace(monkeypatch, 2)
    with pytest.raises(OSError, match="injected"):
        rpc.render(
            _SOURCE,
            out,
            account=_FAKE_ACCOUNT,
            instrument=_FAKE_INSTRUMENT,
            revision="1" * 40,  # a DIFFERENT revision, so a swap would be visible
            direction="LONG",
        )

    assert (out / rpc.RENDERED_NAME).read_text(encoding="utf-8") == before
    assert first.revision == _FAKE_REVISION
    assert _working_dirs(tmp_path) == []


def test_a_stale_working_directory_refuses_loudly_and_names_it(tmp_path: Path) -> None:
    """A leftover from an earlier run must stop the next render and be named.

    The first cut made leftovers INVISIBLE: the name is hidden, it carries the producing pid,
    and the next render neither cleaned nor noticed it — strictly worse observability than
    before the staging directory existed. This refuses instead, and deliberately does NOT
    auto-delete: the directory may belong to a concurrent render, and deleting account-bearing
    data on a pid-liveness heuristic is the quiet behaviour this guard exists to prevent.
    """
    out = tmp_path / "out"
    stale = tmp_path / f".{out.name}.{rpc._STAGING_KIND}-999999"
    stale.mkdir()
    (stale / "venue_constraint_policy.yaml").write_text(
        f'accounts: ["{_FAKE_ACCOUNT}"]\n', encoding="utf-8"
    )

    with pytest.raises(
        rpc.RenderError, match="working directory from an earlier render"
    ):
        _render(out)

    # Refused, not deleted — the operator decides.
    assert stale.is_dir()
    assert not out.exists()


def test_a_successful_render_is_only_visible_once_complete(tmp_path: Path) -> None:
    """The moved-into-place directory always carries ``RENDERED.json``, so it can never be the
    "non-empty, no RENDERED.json" shape the overwrite guard permanently refuses — which is
    what makes a second render of the same target work."""
    out = tmp_path / "out"
    _render(out)
    assert (out / rpc.RENDERED_NAME).is_file()

    # Rendering again over a previous successful render is allowed, and leaves no staging.
    _render(out)
    assert (out / rpc.RENDERED_NAME).is_file()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["out"]


def test_env_file_parsing_strips_an_inline_comment_on_an_unquoted_value(
    tmp_path: Path,
) -> None:
    """review-797 LOW-4. ``normalize_account`` deletes every non-digit, so a trailing
    ``# opened 2026`` would contribute ITS digits to the account — silently producing a
    different, well-formed-looking 10-digit number. A quoted value keeps any ``#`` inside the
    quotes, which is the other half of this."""
    env_path = tmp_path / ".env.mock"
    env_path.write_text(
        f"KIS_FUTURES_ACCOUNT_NO={_FAKE_ACCOUNT}  # opened 2026, product 03\n",
        encoding="utf-8",
    )
    assert rpc.parse_account_from_env_file(env_path) == _FAKE_ACCOUNT

    quoted = tmp_path / "quoted" / ".env.mock"
    quoted.parent.mkdir()
    quoted.write_text(
        f"KIS_FUTURES_ACCOUNT_NO='{_FAKE_ACCOUNT_HYPHENATED}'  # note\n",
        encoding="utf-8",
    )
    assert rpc.parse_account_from_env_file(quoted) == _FAKE_ACCOUNT_HYPHENATED


def test_an_inline_comment_would_otherwise_have_corrupted_the_account() -> None:
    """The guard above is only worth having if the failure it prevents is real.

    Two shapes, and the SILENT one is why this matters:

    * a comment whose digits push the total past ten refuses — loudly, but with a digit count
      that makes no sense to whoever reads it;
    * a comment whose digits land the total exactly ON ten is **accepted**, yielding a
      well-formed, completely different account. An 8-digit CANO plus a `# 03` product-code
      note — a very plausible way to write that file — is exactly that case.
    """
    # Refuses, but for a reason the reader cannot connect to the comment.
    with pytest.raises(rpc.RenderError, match="got 12"):
        rpc.normalize_account(f"{_FAKE_ACCOUNT}  # 03")

    # The silent one: 8 digits + a 2-digit comment == a valid-looking, wrong account.
    cano_only = _FAKE_ACCOUNT[:8]
    corrupted = rpc.normalize_account(f"{cano_only}  # 03")
    assert corrupted == f"{cano_only}03"
    assert corrupted != _FAKE_ACCOUNT


#: One-liners that print a governed policy's ``canonical_digest``, each through the
#: runtime's OWN loader/wiring rather than a re-implementation. Keyed by the YAML the
#: digest is taken over.
_SEED_WITNESS_SCRIPTS: dict[str, str] = {
    # The model that actually blocked this deployment: review-797 measured
    # VenueConstraintPolicy as the only one of the then-13 unsorted models the paper
    # render digests, and the R0 render refused because of it (review-802 LOW-4).
    "venue_constraint_policy.yaml": (
        "import sys;from pathlib import Path;"
        "from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme;"
        "from tos_runtime.venue import"
        " VENUE_POLICY_CONFIG_NAME, load_venue_constraint_policy;"
        "print(load_venue_constraint_policy("
        "Path(sys.argv[1]) / VENUE_POLICY_CONFIG_NAME,"
        " scheme=get_scheme(EV_L1_PROVISIONAL_VERSION)).policy.canonical_digest)"
    ),
    # Kept alongside it: cheap, and it lost its own per-model sorter in the same
    # change, so it witnesses the hook from the other direction.
    "currentness.yaml": (
        "import sys;from pathlib import Path;"
        "from tos_runtime.compose._currentness_wiring import _build_currentness_policy;"
        "print(_build_currentness_policy(Path(sys.argv[1])).canonical_digest)"
    ),
}


@pytest.mark.parametrize("policy_file", sorted(_SEED_WITNESS_SCRIPTS))
def test_policy_digest_is_stable_across_hash_seeds(
    tmp_path: Path, policy_file: str
) -> None:
    """A DEPLOYED policy digests identically in two differently-seeded processes —
    the render-layer witness for the canonical set ordering restored on 2026-09-24
    (``docs/plans/2026-09-24-tos-canonical-set-order-plan.md``).

    The whole class of models is measured over six seeds by
    ``tests/tools/test_tos_canonical_set_order.py``; this one stays here because it runs
    a *rendered deployment's own* YAML through the *runtime's own* wiring, which that pin
    does not. It runs against a render rather than ``_SOURCE`` because the deployment
    coordinates in ``venue_constraint_policy.yaml`` are named-TBD until rendered, and the
    loader refuses a TBD scope before it ever computes a digest.
    """
    out = tmp_path / "out"
    _render(out)

    def _digest(seed: str) -> str:
        completed = subprocess.run(
            [sys.executable, "-B", "-c", _SEED_WITNESS_SCRIPTS[policy_file], str(out)],
            capture_output=True,
            text=True,
            check=True,
            env={
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "HOME": os.environ.get("HOME", "/tmp"),
                "PYTHONPATH": (
                    f"{_REPO_ROOT / 'tos' / 'src'}:"
                    f"{_REPO_ROOT / 'tos' / 'runtime' / 'src'}"
                ),
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONHASHSEED": seed,
            },
        )
        return completed.stdout.strip()

    first, second = _digest("0"), _digest("3")
    assert (
        first and first == second
    ), f"{policy_file} digests differently under two hash seeds: {first} != {second}"


# ---------------------------------------------------------------------------
# The per-tree render manifest (design 2026-10-09 §2.1 · §4.1 · §4.2)
# ---------------------------------------------------------------------------


def _slot_tuples(
    manifest: rpc.RenderManifest,
) -> tuple[tuple[str, str, str, str], ...]:
    return tuple(
        (slot.file, slot.rule_key, slot.anchor, slot.replacement)
        for slot in manifest.slots
    )


#: The RESIDENT tree's slots, pinned as FULL ``(file, key, anchor, replacement)`` tuples.
#:
#: **Why the whole tuple and not the key names** (design §2.1, re-review LOW). Once the slot
#: table is data, the renderer's old self-check (``rendered_keys`` vs ``COORDINATE_RULE_KEYS``)
#: compares the manifest to itself and cannot go red. A key-name pin would restore only part of
#: the force: a manifest that keeps the key ``construction.yaml::account`` while re-aiming its
#: anchor AND template at a different leaf passes template rules ①–④ and a key-name pin alike.
#: ``test_red_proof_a_re_aimed_slot_passes_the_shape_rules_and_only_this_pin_catches_it``
#: measures exactly that, so this literal's necessity is demonstrated rather than asserted.
_EXPECTED_RESIDENT_SLOTS: tuple[tuple[str, str, str, str], ...] = (
    (
        "venue_constraint_policy.yaml",
        "venue_constraint_policy.yaml::scope.accounts",
        '  accounts: ["TBD"]',
        '  accounts: ["{value}"]',
    ),
    (
        "venue_constraint_policy.yaml",
        "venue_constraint_policy.yaml::scope.instruments",
        '  instruments: ["TBD"]',
        '  instruments: ["{value}"]',
    ),
    (
        "order_construction_policy.yaml",
        "order_construction_policy.yaml::scope.accounts",
        '  accounts: ["TBD"]',
        '  accounts: ["{value}"]',
    ),
    (
        "order_construction_policy.yaml",
        "order_construction_policy.yaml::scope.instruments",
        '  instruments: ["TBD"]',
        '  instruments: ["{value}"]',
    ),
    (
        "order_construction_policy.yaml",
        "order_construction_policy.yaml::_runtime.construction.axes.DIRECTION",
        '        value: "LONG"',
        '        value: "{value}"',
    ),
    (
        "aggregate_risk_policy.yaml",
        "aggregate_risk_policy.yaml::account_scope",
        'account_scope: ["TBD"]',
        'account_scope: ["{value}"]',
    ),
    (
        "aggregate_risk_policy.yaml",
        "aggregate_risk_policy.yaml::instrument_scope",
        'instrument_scope: ["TBD"]',
        'instrument_scope: ["{value}"]',
    ),
    (
        "action_flow_policy.yaml",
        "action_flow_policy.yaml::account_scope",
        'account_scope: ["TBD"]',
        'account_scope: ["{value}"]',
    ),
    (
        "construction.yaml",
        "construction.yaml::account",
        'account: "TBD"',
        'account: "{value}"',
    ),
    (
        "construction.yaml",
        "construction.yaml::instrument",
        'instrument: "TBD"',
        'instrument: "{value}"',
    ),
    (
        "construction.yaml",
        "construction.yaml::action_class",
        'action_class: "NEW_LONG"',
        'action_class: "{value}"',
    ),
    (
        "construction.yaml",
        "construction.yaml::outbound_side",
        'outbound_side: "BUY"',
        'outbound_side: "{value}"',
    ),
    (
        "strategies/bootproof_band.strategy.yaml",
        "strategies/bootproof_band.strategy.yaml::policy.rules[0].decision.target.account",
        '          account: "TBD"',
        '          account: "{value}"',
    ),
    (
        "strategies/bootproof_band.strategy.yaml",
        "strategies/bootproof_band.strategy.yaml::policy.rules[0].decision.target.instrument",
        '          instrument: "TBD"',
        '          instrument: "{value}"',
    ),
    (
        "strategies/bootproof_band.strategy.yaml",
        "strategies/bootproof_band.strategy.yaml::policy.rules[0].decision.target.direction",
        '          direction: "LONG"',
        '          direction: "{value}"',
    ),
    (
        "marketfeed.yaml",
        "marketfeed.yaml::instruments",
        'instruments: ["TBD"]',
        'instruments: ["{value}"]',
    ),
    (
        "marketfeed.yaml",
        "marketfeed.yaml::account",
        'account: "TBD"',
        'account: "{value}"',
    ),
    (
        "marketfeed.yaml",
        "marketfeed.yaml::direction",
        'direction: "LONG"',
        'direction: "{value}"',
    ),
    (
        "marketfeed.yaml",
        "marketfeed.yaml::journal_path",
        'journal_path: "TBD"',
        'journal_path: "{value}"',
    ),
    (
        "finality.yaml",
        "finality.yaml::source_revision",
        "source_revision: null",
        'source_revision: "{value}"',
    ),
)


@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
def test_manifest_rules_equal_the_legacy_hardcoded_table(direction: str) -> None:
    """Design §4.1 item 1 — the TRANSITION pin.

    The rules the resident ``RENDER.yaml`` produces must be the same ``Rule`` tuple the
    hard-coded :func:`render_paper_config._coordinate_rules` produced, element for element, for
    BOTH directions (the SHORT half matters because four slots are direction-bound and only
    SHORT moves their bytes). This is what makes "the resident render did not change" a
    measurement; the byte-level proof against ``origin/main``'s renderer is in the PR body, and
    this pin is its committed, re-runnable half until the follow-up PR deletes
    ``_coordinate_rules``.
    """
    journal_path = Path("/nowhere/bootproof_journal.jsonl")
    legacy = rpc._coordinate_rules(
        account=_FAKE_ACCOUNT,
        instrument=_FAKE_INSTRUMENT,
        revision=_FAKE_REVISION,
        direction=direction,
        journal_path=journal_path,
    )
    from_manifest = rpc._slot_rules(
        rpc.load_manifest(_SOURCE),
        account=_FAKE_ACCOUNT,
        instrument=_FAKE_INSTRUMENT,
        revision=_FAKE_REVISION,
        direction=direction,
        journal_path=journal_path,
    )
    assert from_manifest == legacy


def test_resident_manifest_declares_the_resident_modes() -> None:
    """The resident tree keeps TODAY's behaviour: ``--direction`` substitutes, and the
    boot-proof journal is written by the renderer. A tenant tree declares the other two.
    """
    manifest = rpc.load_manifest(_SOURCE)
    assert manifest.tree_id == "paper"
    assert manifest.direction_mode == "substitute"
    assert manifest.direction_value is None
    assert manifest.journal_mode == "synthetic_bootproof"


def test_resident_manifest_slots_are_pinned_as_full_tuples() -> None:
    """Design §2.1's key-set pin, as full tuples. Adding, removing, reordering or re-aiming a
    resident slot turns this RED and requires the literal above to be edited."""
    assert _slot_tuples(rpc.load_manifest(_SOURCE)) == _EXPECTED_RESIDENT_SLOTS


def test_red_proof_a_re_aimed_slot_passes_the_shape_rules_and_only_this_pin_catches_it(
    tmp_path: Path,
) -> None:
    """**The red proof for the pin above, built so nothing else can mask it** (#838).

    The mutation keeps the slot's KEY (``construction.yaml::account``) and moves both its anchor
    and its template onto a different leaf of the same file. Three things are measured, in
    order, and the third is the only one that fires:

    1. the manifest LOADS — template rules ①–④ accept it, so they are not what would catch this;
    2. the set of rule KEYS is unchanged — a key-name pin would also not catch it;
    3. the full-tuple pin differs — which is why the literal carries anchors and templates.

    Without steps 1 and 2 this test would "pass" while some earlier guard did the work, and the
    literal's necessity would be unproven.
    """
    manifest = _resident_manifest_dict()
    index = _slot_index(manifest, "construction.yaml", "account")
    manifest["slots"][index]["anchor"] = 'instrument_class: "krx-index-futures"'
    manifest["slots"][index]["replacement"] = 'instrument_class: "{value}"'
    tree = _tree_with_manifest(tmp_path, manifest)

    loaded = rpc.load_manifest(tree)  # 1 — rules ①–④ do not refuse this

    assert {slot.rule_key for slot in loaded.slots} == {
        key for _file, key, _anchor, _replacement in _EXPECTED_RESIDENT_SLOTS
    }  # 2 — a key-name pin stays green
    assert _slot_tuples(loaded) != _EXPECTED_RESIDENT_SLOTS  # 3 — only this pin is red


# ---- template shape rules ①–④ (design §2.1) --------------------------------


def test_template_carrying_a_literal_value_is_refused(tmp_path: Path) -> None:
    """Rule ④'s reason for existing: a template that smuggles an approved-looking value past
    the closed value-source set. ``["{value}", "A05610"]`` would render the coordinate AND a
    hard-coded instrument nobody approved — exactly what ``COORDINATE_RULE_KEYS`` prevented
    while it was code."""
    manifest = _resident_manifest_dict()
    index = _slot_index(manifest, "marketfeed.yaml", "instruments")
    manifest["slots"][index]["replacement"] = 'instruments: ["{value}", "A05610"]'
    tree = _tree_with_manifest(tmp_path, manifest)

    with pytest.raises(rpc.RenderError, match="literal characters"):
        rpc.load_manifest(tree)


def test_template_with_a_mismatched_yaml_anchor_name_is_refused(tmp_path: Path) -> None:
    """Rule ④'s single exception, and its byte-identity condition.

    §2.2 collapses a tenant strategy's repeated coordinates onto one anchored line
    (``account: &account "TBD"``) plus aliases, so a template must be allowed to carry that one
    token. It must carry the SAME one: a template defining ``&acct`` where the file anchors
    ``&account`` renders a document whose every ``*account`` alias dangles.
    """
    manifest = _resident_manifest_dict()
    index = _slot_index(manifest, "construction.yaml", "account")
    manifest["slots"][index]["anchor"] = 'account: &account "TBD"'
    manifest["slots"][index]["replacement"] = 'account: &acct "{value}"'
    tree = _tree_with_manifest(tmp_path, manifest)

    with pytest.raises(rpc.RenderError, match="YAML anchor token differs"):
        rpc.load_manifest(tree)


def test_the_matching_yaml_anchor_token_is_accepted(tmp_path: Path) -> None:
    """The other half of the exception — without this, "refuses a mismatched anchor" would be
    satisfied by a rule that refuses EVERY anchor token, and §2.2's alias scheme could not be
    rendered at all."""
    manifest = _resident_manifest_dict()
    index = _slot_index(manifest, "construction.yaml", "account")
    manifest["slots"][index]["anchor"] = '          account: &account "TBD"'
    manifest["slots"][index]["replacement"] = '          account: &account "{value}"'
    tree = _tree_with_manifest(tmp_path, manifest)

    loaded = rpc.load_manifest(tree)
    assert loaded.slots[index].replacement == '          account: &account "{value}"'


@pytest.mark.parametrize(
    ("replacement", "match"),
    [
        ('account: "{value}{value}"', "exactly one"),
        ('account: "TBD"', "exactly one"),
        ('account: "{value}{other}"', "carries a brace"),
        ("tick_size: {value}", "key prefix"),
    ],
    ids=["two-placeholders", "no-placeholder", "second-brace", "re-aimed-key-prefix"],
)
def test_template_shape_rules_refuse(
    tmp_path: Path, replacement: str, match: str
) -> None:
    """Rules ①–③, one failing input each, and each matched on the message the rule it is
    aimed at produces — so a case that is caught by a DIFFERENT rule shows up as a failure
    rather than as a pass that proves nothing about the rule it is named for."""
    manifest = _resident_manifest_dict()
    index = _slot_index(manifest, "construction.yaml", "account")
    manifest["slots"][index]["replacement"] = replacement
    tree = _tree_with_manifest(tmp_path, manifest)

    with pytest.raises(rpc.RenderError, match=match):
        rpc.load_manifest(tree)


def test_a_yaml_anchor_token_that_is_not_immediately_after_the_key_is_refused(
    tmp_path: Path,
) -> None:
    """PR #888 review L1b — the red proof the anchor-token POSITION test was missing.

    Rule ④ allows one YAML anchor token, and :func:`render_paper_config._anchor_token` only
    recognises it when nothing but whitespace separates it from the colon. Drop that position
    test and this input is accepted: both sides report ``&account``, the tokens compare equal,
    and the residue is quotes and spaces. The rendered line would be
    ``account: "<value>" &account`` — not valid YAML, since an anchor may not trail the scalar
    it would name, so the whole document fails to parse at boot.
    """
    manifest = _resident_manifest_dict()
    index = _slot_index(manifest, "construction.yaml", "account")
    manifest["slots"][index]["anchor"] = '          account: &account "TBD"'
    manifest["slots"][index]["replacement"] = '          account: "{value}" &account'
    tree = _tree_with_manifest(tmp_path, manifest)

    with pytest.raises(rpc.RenderError, match="YAML anchor token differs"):
        rpc.load_manifest(tree)


def test_a_placeholder_inside_the_key_prefix_is_refused(tmp_path: Path) -> None:
    """PR #888 review L1a — the red proof the inside-prefix clause was missing.

    For an ORDINARY anchor the clause is unreachable: a placeholder inside the key makes the
    template's key prefix differ from the anchor's, so rule ③ refuses first. It becomes
    reachable exactly when the ANCHOR's own key carries the literal ``{value}`` — then both
    prefixes match, the tail is filler-only, and rule ④ sees nothing wrong.

    Measured with the clause disabled: this pair is ACCEPTED and the rendered line is
    ``  foo9999999999: ""`` — the account substituted into the KEY NAME, the leaf left empty.
    No committed YAML carries such a key, so the input is contrived; the clause is one
    comparison and the failure it prevents is silent, so it stays and this is its proof.
    """
    manifest = _resident_manifest_dict()
    index = _slot_index(manifest, "construction.yaml", "account")
    manifest["slots"][index]["anchor"] = '  foo{value}: ""'
    manifest["slots"][index]["replacement"] = '  foo{value}: ""'
    tree = _tree_with_manifest(tmp_path, manifest)

    with pytest.raises(rpc.RenderError, match="sits inside the key prefix"):
        rpc.load_manifest(tree)


# ---- manifest load refusals (design §4.2) ----------------------------------


def test_a_value_source_outside_the_closed_set_is_refused(tmp_path: Path) -> None:
    """Design §2.1: the value-source set is CLOSED. Opening it is how a manifest would start
    carrying values, which is what the whole shape-checking apparatus exists to prevent.
    """
    manifest = _resident_manifest_dict()
    manifest["slots"][0]["value"] = "tick_size"
    tree = _tree_with_manifest(tmp_path, manifest)

    with pytest.raises(rpc.RenderError, match="value source refused"):
        rpc.load_manifest(tree)


@pytest.mark.parametrize(
    ("section", "mode", "match"),
    [
        ("direction", "inherit", "direction.mode refused"),
        ("journal", "none", "journal.mode refused"),
    ],
)
def test_a_mode_outside_the_two_declared_ones_is_refused(
    tmp_path: Path, section: str, mode: str, match: str
) -> None:
    manifest = _resident_manifest_dict()
    manifest[section]["mode"] = mode
    tree = _tree_with_manifest(tmp_path, manifest)

    with pytest.raises(rpc.RenderError, match=match):
        rpc.load_manifest(tree)


def test_a_slot_whose_file_is_missing_from_the_tree_is_refused(tmp_path: Path) -> None:
    manifest = _resident_manifest_dict()
    manifest["slots"][0]["file"] = "no_such_policy.yaml"
    tree = _tree_with_manifest(tmp_path, manifest)

    with pytest.raises(rpc.RenderError, match="slot target missing"):
        rpc.load_manifest(tree)


def test_two_slots_sharing_a_key_are_refused(tmp_path: Path) -> None:
    """A copy-pasted slot would otherwise render twice and report one key — and the second
    application would refuse with "matched 0 times" far from the cause."""
    manifest = _resident_manifest_dict()
    manifest["slots"].append(copy.deepcopy(manifest["slots"][0]))
    tree = _tree_with_manifest(tmp_path, manifest)

    with pytest.raises(rpc.RenderError, match="duplicate slot key"):
        rpc.load_manifest(tree)


def test_a_tree_without_a_manifest_is_refused(tmp_path: Path) -> None:
    """Fail-closed: no manifest, no render. The alternative — falling back to the hard-coded
    resident table — would render a tenant tree with the resident tree's slots."""
    tree = _source_copy(tmp_path)
    (tree / rpc.RENDER_MANIFEST_NAME).unlink()

    with pytest.raises(rpc.RenderError, match="render manifest not found"):
        _render(tmp_path / "out", source=tree)


def test_a_substitute_mode_manifest_may_not_also_declare_a_direction(
    tmp_path: Path,
) -> None:
    """Two sources for one fact. In substitute mode the direction is ``--direction``; a
    manifest value could only agree or lie, and the lying case is silent."""
    manifest = _resident_manifest_dict()
    manifest["direction"]["value"] = "LONG"
    tree = _tree_with_manifest(tmp_path, manifest)

    with pytest.raises(rpc.RenderError, match="second source"):
        rpc.load_manifest(tree)


# ---- declared direction mode (design §2.3) ---------------------------------


def _declared_manifest(direction: str) -> dict[str, Any]:
    """The resident slots, re-declared the way a per-direction tenant tree will."""
    manifest = _resident_manifest_dict()
    manifest["tree_id"] = f"fixture-declared-{direction.lower()}"
    manifest["direction"] = {"mode": "declared", "value": direction}
    return manifest


def test_declared_mode_renders_and_leaves_the_direction_lines_untouched(
    tmp_path: Path,
) -> None:
    """The positive half, without which every refusal below could be satisfied by a mode that
    simply never renders.

    The committed tree is LONG and the manifest declares LONG: the direction slots are
    VERIFY-ONLY (replacement == anchor), so those lines come out byte-identical to the
    committed ones while the coordinate slots are filled as usual.
    """
    tree = _tree_with_manifest(tmp_path, _declared_manifest("LONG"))
    result = rpc.render(
        tree,
        tmp_path / "out",
        account=_FAKE_ACCOUNT,
        instrument=_FAKE_INSTRUMENT,
        revision=_FAKE_REVISION,
        direction="LONG",
    )

    assert result.tree_id == "fixture-declared-long"
    construction = (result.out / "construction.yaml").read_text(encoding="utf-8")
    assert 'action_class: "NEW_LONG"' in construction
    assert 'outbound_side: "BUY"' in construction
    assert f'account: "{_FAKE_ACCOUNT}"' in construction


def _drop_value_source(manifest: dict[str, Any], source: str) -> dict[str, Any]:
    """Remove EVERY slot drawing on ``source``.

    Not "the first one": ``direction`` has three slots in the resident table
    (``order_construction_policy.yaml``'s DIRECTION axis, the strategy rule, and
    ``marketfeed.yaml``), so dropping one leaves the source present and would measure nothing.
    """
    before = len(manifest["slots"])
    manifest["slots"] = [s for s in manifest["slots"] if s["value"] != source]
    assert len(manifest["slots"]) < before, f"no slot drew on {source!r}"
    return manifest


@pytest.mark.parametrize(
    "source", ["direction_action_class", "direction_side", "direction"]
)
def test_declared_mode_refuses_a_manifest_missing_a_direction_slot(
    tmp_path: Path, source: str
) -> None:
    """PR #888 review L3 — review H1's disposition had an unenforced PRECONDITION.

    The verify-only rules only check a direction if the slots are THERE. Delete them and a
    declared tree renders with no direction check at all: the five policy digests do not bind
    DIRECTION, so a SHORT tree under a LONG manifest activates, boots and refuses nothing.
    Measured before this guard existed — deleting the slots turned
    :func:`test_declared_mode_refuses_a_tree_whose_direction_lines_do_not_match` green.

    One parameter per direction-bound value source, because dropping any ONE of the three is
    enough to stop verifying that part of the direction; a guard that only noticed all three
    going missing would admit the two-thirds case.
    """
    tree = _tree_with_manifest(
        tmp_path, _drop_value_source(_declared_manifest("LONG"), source)
    )

    with pytest.raises(rpc.RenderError, match="EVERY direction-bound value source"):
        rpc.load_manifest(tree)


def test_substitute_mode_does_not_require_the_direction_slots(tmp_path: Path) -> None:
    """The other side of L3: the requirement is DECLARED-mode only.

    In substitute mode the direction is an argument, not a committed fact, so a tree that
    simply has no direction-bound leaf is legitimate. Without this, "refuses a missing
    direction slot" would be satisfied by a rule that refuses it everywhere and would quietly
    forbid a future substitute tree from existing.
    """
    tree = _tree_with_manifest(
        tmp_path, _drop_value_source(_resident_manifest_dict(), "direction")
    )

    loaded = rpc.load_manifest(tree)
    assert "direction" not in {slot.value for slot in loaded.slots}


def test_declared_mode_refuses_a_direction_flag_that_disagrees(tmp_path: Path) -> None:
    """Design §2.3: a per-direction tree is not re-pointed by a flag."""
    tree = _tree_with_manifest(tmp_path, _declared_manifest("LONG"))

    with pytest.raises(rpc.RenderError, match="declared-direction tree"):
        rpc.render(
            tree,
            tmp_path / "out",
            account=_FAKE_ACCOUNT,
            instrument=_FAKE_INSTRUMENT,
            revision=_FAKE_REVISION,
            direction="SHORT",
        )


def test_declared_mode_refuses_a_tree_whose_direction_lines_do_not_match(
    tmp_path: Path,
) -> None:
    """**Review H1's concrete failing input.** A tree declaring ``SHORT`` whose
    ``construction.yaml`` still carries the LONG tokens.

    Comparing the manifest against the flag alone would render this happily — the five digests
    do not bind DIRECTION (``_policy_digest_lines``' own docstring), so activation would pass
    and nothing would refuse. Keeping the direction slots in a declared manifest makes it
    "``action_class: "NEW_SHORT"`` matched 0 times" instead.

    The manifest here is INTERNALLY CONSISTENT (it declares SHORT and its direction anchors are
    the SHORT lines), so the self-consistency refusal below cannot be what fires — this
    measures the tree-vs-manifest check specifically. The mutation that turns it green is
    dropping the direction slots from the manifest, which is what review H1 named and what
    PR-B's per-tree direction-consistency test pins for the real tenant manifests.
    """
    manifest = _declared_manifest("SHORT")
    for file_name, key, long_token, short_token in (
        ("construction.yaml", "action_class", "NEW_LONG", "NEW_SHORT"),
        ("construction.yaml", "outbound_side", "BUY", "SELL"),
        ("marketfeed.yaml", "direction", "LONG", "SHORT"),
        (
            "order_construction_policy.yaml",
            "_runtime.construction.axes.DIRECTION",
            "LONG",
            "SHORT",
        ),
        (
            "strategies/bootproof_band.strategy.yaml",
            "policy.rules[0].decision.target.direction",
            "LONG",
            "SHORT",
        ),
    ):
        index = _slot_index(manifest, file_name, key)
        manifest["slots"][index]["anchor"] = manifest["slots"][index]["anchor"].replace(
            long_token, short_token
        )
    tree = _tree_with_manifest(tmp_path, manifest)

    with pytest.raises(rpc.RenderError, match="matched 0 times"):
        rpc.render(
            tree,
            tmp_path / "out",
            account=_FAKE_ACCOUNT,
            instrument=_FAKE_INSTRUMENT,
            revision=_FAKE_REVISION,
            direction="SHORT",
        )


def test_declared_mode_refuses_a_manifest_that_contradicts_its_own_direction(
    tmp_path: Path,
) -> None:
    """The other shape: a manifest declaring ``SHORT`` whose direction anchors are still the
    LONG lines. Rendering it would verify LONG lines under a SHORT declaration, so the
    declaration and the anchors must agree before the tree is ever read."""
    tree = _tree_with_manifest(tmp_path, _declared_manifest("SHORT"))

    with pytest.raises(rpc.RenderError, match="disagrees with itself"):
        rpc.render(
            tree,
            tmp_path / "out",
            account=_FAKE_ACCOUNT,
            instrument=_FAKE_INSTRUMENT,
            revision=_FAKE_REVISION,
            direction="SHORT",
        )


# ---- external journal mode (design §2.4 · §7) ------------------------------


def _external_manifest() -> dict[str, Any]:
    manifest = _resident_manifest_dict()
    manifest["tree_id"] = "fixture-external"
    manifest["journal"] = {"mode": "external"}
    return manifest


def _upstream_journal(path: Path) -> Path:
    """A stand-in for the ③ producer's output. The renderer never reads it — it only has to
    exist — but the shape is the real one so a loader downstream would accept it."""
    observation = {
        "raw_event_id": "upstream-1",
        "instrument": _FAKE_INSTRUMENT,
        "as_of_ms": 1_760_000_000_000,
        "fields": {
            "close": 4_499_000,
            "lower_band": 4_500_000,
            "upper_band": 4_520_000,
        },
        "source_id": "fixture-upstream",
        "received_ms": 1_760_000_000_000,
    }
    path.write_text(json.dumps(observation, sort_keys=True) + "\n", encoding="utf-8")
    return path


@pytest.fixture(scope="session")
def external_render(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, Path, Path]:
    """One ``external``-mode render, shared by the tests that only READ it.

    Session-scoped because a render runs two runtime subprocesses; the tests that mutate the
    output copy it first.
    """
    base = tmp_path_factory.mktemp("external")
    journal = _upstream_journal(base / "upstream.jsonl")
    tree = _tree_with_manifest(base, _external_manifest())
    out = base / "out"
    rpc.render(
        tree,
        out,
        account=_FAKE_ACCOUNT,
        instrument=_FAKE_INSTRUMENT,
        revision=_FAKE_REVISION,
        direction="LONG",
        journal_path=journal,
    )
    return tree, out, journal


def test_external_mode_refuses_without_a_journal_path(tmp_path: Path) -> None:
    """Design §2.4, fail-closed: no ③ output, no tenant render. The renderer must not fall back
    to inventing observations — the synthetic journal's ``close`` is a fixture constant, and a
    tenant deciding on it would be deciding on a made-up market."""
    tree = _tree_with_manifest(tmp_path, _external_manifest())

    with pytest.raises(rpc.RenderError, match="journal path required"):
        _render(tmp_path / "out", source=tree)


def test_external_mode_refuses_a_journal_path_that_does_not_exist(
    tmp_path: Path,
) -> None:
    tree = _tree_with_manifest(tmp_path, _external_manifest())

    with pytest.raises(rpc.RenderError, match="journal file not found"):
        rpc.render(
            tree,
            tmp_path / "out",
            account=_FAKE_ACCOUNT,
            instrument=_FAKE_INSTRUMENT,
            revision=_FAKE_REVISION,
            direction="LONG",
            journal_path=tmp_path / "absent.jsonl",
        )


def test_synthetic_mode_refuses_a_journal_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The mirror refusal, driven through the CLI so ``--journal-path``'s plumbing into
    :func:`render` is measured rather than assumed. The resident tree writes its own journal; a
    second one passed in would be a second source."""
    env_path = tmp_path / ".env.mock"
    env_path.write_text(
        f"KIS_FUTURES_ACCOUNT_NO='{_FAKE_ACCOUNT_HYPHENATED}'\n", encoding="utf-8"
    )

    code = rpc.main(
        [
            "--out",
            str(tmp_path / "out"),
            "--env-file",
            str(env_path),
            "--instrument",
            _FAKE_INSTRUMENT,
            "--journal-path",
            str(_upstream_journal(tmp_path / "upstream.jsonl")),
        ]
    )

    assert code == 1
    assert "journal path refused" in capsys.readouterr().err


def test_external_mode_writes_no_journal_and_points_at_the_upstream_one(
    external_render: tuple[Path, Path, Path],
) -> None:
    """Design §2.4: the renderer writes no journal in this mode, and the rendered
    ``marketfeed.yaml`` names the producer's file."""
    _tree, out, journal = external_render

    assert not (out / rpc.JOURNAL_NAME).exists()
    marketfeed = (out / "marketfeed.yaml").read_text(encoding="utf-8")
    assert f'journal_path: "{journal}"' in marketfeed
    manifest = json.loads((out / rpc.RENDERED_NAME).read_text(encoding="utf-8"))
    assert manifest["journal_path"] == str(journal)
    assert manifest["journal_as_of_ms"] is None


def test_check_is_clean_on_an_external_mode_render(
    external_render: tuple[Path, Path, Path],
) -> None:
    """Design §7: ``_GENERATED_NAMES`` used to be a constant that always required
    ``bootproof_journal.jsonl``, so ``--check`` reported "render artifact missing" against every
    correct external render. The required set now follows ``journal.mode``.

    This also covers the manifest's own copy: ``RENDER.yaml`` is byte-copied into the output
    (§7) and so must NOT be reported as an unexpected extra file.
    """
    tree, out, _journal = external_render

    assert rpc.check(tree, out) == []
    assert (out / rpc.RENDER_MANIFEST_NAME).is_file()


def test_check_still_catches_an_edit_outside_the_slots_in_external_mode(
    external_render: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """The red proof for the test above: a ``--check`` that reported nothing at all would also
    be "clean". A hand edit outside every registered slot is still named."""
    tree, rendered, _journal = external_render
    out = tmp_path / "out"
    shutil.copytree(rendered, out)
    calendar = out / "calendar.yaml"
    calendar.write_text(
        calendar.read_text(encoding="utf-8").replace(
            'tz_id: "Asia/Seoul"', 'tz_id: "UTC"'
        ),
        encoding="utf-8",
    )

    problems = rpc.check(tree, out)
    assert any("calendar.yaml" in problem for problem in problems), problems


def test_check_names_an_edit_to_the_copied_manifest(
    external_render: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """``RENDER.yaml`` is copied through and no slot is anchored in it — so an edit to the
    OUTPUT's copy is a change outside every coordinate slot and must be reported. Without this,
    "the manifest is copied through" would be indistinguishable from "the manifest is exempt
    from the check"."""
    tree, rendered, _journal = external_render
    out = tmp_path / "out"
    shutil.copytree(rendered, out)
    path = out / rpc.RENDER_MANIFEST_NAME
    path.write_text(
        path.read_text(encoding="utf-8").replace("fixture-external", "smuggled"),
        encoding="utf-8",
    )

    problems = rpc.check(tree, out)
    assert any(rpc.RENDER_MANIFEST_NAME in problem for problem in problems), problems


# ---- the 08:45 resident path (design §4.1 item 3) --------------------------


def test_the_resident_driver_invocation_needs_no_new_argument(tmp_path: Path) -> None:
    """Design §4.1 item 3, measured rather than reasoned.

    The host driver (``~/.config/kis-probes/tos_paper_session.py:306-316``) passes exactly
    ``--out --env-file --instrument --direction`` and relies on the DEFAULT ``--source``. This
    runs that same invocation and asserts the five keys the driver then reads
    (``:331-333,366-370``) are present — which is why ``paper/RENDER.yaml`` had to land in THIS
    PR rather than a later one: a default ``--source`` with no manifest next to it would refuse
    at 08:45 the morning after the merge.
    """
    env_path = tmp_path / ".env.mock"
    env_path.write_text(
        f"KIS_FUTURES_ACCOUNT_NO='{_FAKE_ACCOUNT_HYPHENATED}'\n", encoding="utf-8"
    )
    out = tmp_path / "out"

    code = rpc.main(
        [
            "--out",
            str(out),
            "--env-file",
            str(env_path),
            "--instrument",
            _FAKE_INSTRUMENT,
            "--direction",
            "LONG",
        ]
    )

    assert code == 0
    rendered = json.loads((out / rpc.RENDERED_NAME).read_text(encoding="utf-8"))
    for key in (
        "instrument",
        "journal_path",
        "activation_check",
        "source_revision",
        "rendered_at_kst",
    ):
        assert rendered.get(key), f"the driver reads {key!r} and it is missing or empty"
    assert rendered["instrument"] == _FAKE_INSTRUMENT
    assert Path(rendered["journal_path"]).is_file()
