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

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterable
from pathlib import Path

import pytest

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

#: Two PYTHONHASHSEED values MEASURED (2026-09-23) to produce different
#: ``VenueConstraintPolicy.canonical_digest`` values for the same file — see
#: :func:`test_venue_policy_canonical_digest_is_not_reproducible_across_processes`.
_SEED_A = "0"
_SEED_B = "3"


@pytest.fixture()
def pinned_hash_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin ``PYTHONHASHSEED`` for the render's subprocesses.

    ⚠ This is NOT how the shipped procedure is meant to work. It is here because of the
    measured defect pinned by
    :func:`test_venue_policy_canonical_digest_is_not_reproducible_across_processes`:
    ``VenueConstraintPolicy``'s canonical digest depends on frozenset iteration order, so the
    ``print-policy-digests`` → ``members`` → boot transcription only agrees when every process
    shares a hash seed. Without this fixture the happy-path tests below would be a coin flip.

    When that defect is fixed, this fixture should be deleted and the tests should pass
    without it — that deletion is the acceptance criterion for the fix.
    """
    monkeypatch.setenv("PYTHONHASHSEED", _SEED_A)


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


# ---------------------------------------------------------------------------
# Happy path — the coordinate slots, and only those, are filled
# ---------------------------------------------------------------------------


def test_render_fills_every_registered_coordinate_slot(
    tmp_path: Path, pinned_hash_seed: None
) -> None:
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


def test_render_derives_members_and_reads_them_back_activated(
    tmp_path: Path, pinned_hash_seed: None
) -> None:
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
    tmp_path: Path, pinned_hash_seed: None
) -> None:
    result = _render(tmp_path / "out")

    manifest_text = (result.out / rpc.RENDERED_NAME).read_text(encoding="utf-8")
    assert _FAKE_ACCOUNT not in manifest_text
    manifest = json.loads(manifest_text)
    assert manifest["account_fingerprint"] == result.account_fingerprint
    assert manifest["source_revision"] == _FAKE_REVISION
    assert manifest["direction"] == "LONG"


def test_render_writes_a_journal_the_marketfeed_config_points_at(
    tmp_path: Path, pinned_hash_seed: None
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


def test_direction_short_swaps_every_direction_bound_slot(
    tmp_path: Path, pinned_hash_seed: None
) -> None:
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


def test_check_passes_on_a_freshly_rendered_directory(
    tmp_path: Path, pinned_hash_seed: None
) -> None:
    out = tmp_path / "out"
    _render(out)
    assert rpc.check(_SOURCE, out) == []


# ---------------------------------------------------------------------------
# Design §2 guard table — one failing-input test per row
# ---------------------------------------------------------------------------


def test_guard_every_rule_anchor_occurs_exactly_once_in_the_committed_source() -> None:
    """Guard "칸마다 정확히 1회 매칭", positive half: the committed source must actually carry
    each anchor exactly once, or the render below refuses."""
    rules = rpc._coordinate_rules(
        account=_FAKE_ACCOUNT,
        instrument=_FAKE_INSTRUMENT,
        revision=_FAKE_REVISION,
        direction="LONG",
        journal_path=Path("/nowhere/journal.jsonl"),
    ) + (rpc._members_rule("members: x"),)
    for rule in rules:
        lines = (_SOURCE / rule.file).read_text(encoding="utf-8").split("\n")
        assert [line for line in lines if line == rule.anchor] == [
            rule.anchor
        ], f"{rule.key}: anchor {rule.anchor!r} does not occur exactly once in {rule.file}"


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
    grow silently."""
    assert set(rpc.COORDINATE_RULE_KEYS) == {
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


def test_guard_check_reports_an_edit_outside_a_coordinate_slot(
    tmp_path: Path, pinned_hash_seed: None
) -> None:
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


def test_guard_check_reports_an_unexpected_extra_file(
    tmp_path: Path, pinned_hash_seed: None
) -> None:
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
    tmp_path: Path, pinned_hash_seed: None
) -> None:
    """Guard "렌더가 저장소에 아무것도 남기지 않는다" (design §2, review-795 HIGH-3).

    Runs the REAL CLI inside a throwaway ``git clone`` of this repository and asserts
    ``git status --porcelain --ignored`` is byte-identical before and after. Bytecode is
    disabled in BOTH the script and its subprocesses (``PYTHONDONTWRITEBYTECODE=1`` + ``-B``)
    because ``__pycache__`` is gitignored and would otherwise show up under ``--ignored``.

    A mutation that removes the output-path check, or points the output inside the repo, makes
    new files appear here and turns this RED. The account used is the fake ``9999999999``.
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
            "PYTHONHASHSEED": _SEED_A,
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
# The measured defect this render cannot work around
# ---------------------------------------------------------------------------


def test_venue_policy_canonical_digest_is_not_reproducible_across_processes(
    tmp_path: Path,
) -> None:
    """**A measured defect, pinned so it cannot be forgotten (2026-09-23).**

    ``VenueConstraintPolicy._COVERED_FIELDS`` (``tos/src/tos/venue/records.py:406-416``)
    includes ``required_constraint_classes: frozenset[ConstraintClass]`` (``:424``) and
    ``shape_constraints``, whose four ``allowed_*`` members are frozensets (``:165-168``).
    ``covered_content()`` is ``model_dump(mode="json", …)``
    (``tos/src/tos/canonical/_base.py:187``), which renders a frozenset as a LIST in
    set-iteration order, and ``_encode`` treats a sequence as ORDER-SIGNIFICANT
    (``tos/src/tos/canonical/canonicalization.py:148-149,174-176``). ``ConstraintClass`` is a
    ``StrEnum`` (``tos/src/tos/venue/vocabulary.py:169``), so the order — and therefore the
    digest — follows the per-process string hash seed.

    Why it matters: the documented operator procedure is a CROSS-PROCESS transcription (run
    ``print-policy-digests``, copy the digests into ``safety_activation.yaml::members``, then
    boot, which recomputes them — ``compose/_venue_wiring.py:265-271``). A digest that changes
    per process makes that procedure unusable for this one kind. Every existing test computes
    and verifies inside ONE process (``tests/compose/test_deploy_policies.py``'s own
    ``_install_real_policies``: "the ``print-policy-digests`` step, done **in-process**"),
    which is why it was not caught before.

    **When the canonicalization is fixed this test goes RED — and that is the point.** Replace
    it with the equality assertion and delete the ``pinned_hash_seed`` fixture above.
    """
    source = _source_copy(tmp_path)
    path = source / "venue_constraint_policy.yaml"
    path.write_text(
        path.read_text(encoding="utf-8")
        .replace('  accounts: ["TBD"]', f'  accounts: ["{_FAKE_ACCOUNT}"]')
        .replace('  instruments: ["TBD"]', f'  instruments: ["{_FAKE_INSTRUMENT}"]'),
        encoding="utf-8",
    )

    def _digest(seed: str) -> str:
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-c",
                "import sys;from pathlib import Path;"
                "from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme;"
                "from tos_runtime.venue import load_venue_constraint_policy;"
                "p=load_venue_constraint_policy("
                "Path(sys.argv[1]), scheme=get_scheme(EV_L1_PROVISIONAL_VERSION));"
                "print(p.policy.canonical_digest)",
                str(path),
            ],
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

    assert _digest(_SEED_A) != _digest(_SEED_B), (
        "VenueConstraintPolicy.canonical_digest is now stable across hash seeds — the "
        "2026-09-23 defect appears to be fixed. Update this test to assert equality and "
        "delete the pinned_hash_seed fixture."
    )
    # Same seed twice: stable, so the instability is the seed and nothing else.
    assert _digest(_SEED_A) == _digest(_SEED_A)


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
    pinned_hash_seed: None,
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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pinned_hash_seed: None
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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pinned_hash_seed: None
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


def test_a_stale_working_directory_refuses_loudly_and_names_it(
    tmp_path: Path, pinned_hash_seed: None
) -> None:
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


def test_a_successful_render_is_only_visible_once_complete(
    tmp_path: Path, pinned_hash_seed: None
) -> None:
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


# ---------------------------------------------------------------------------
# The measured defect is a CLASS of models (review-797 MEDIUM-3)
# ---------------------------------------------------------------------------


_SET_COVERED_SCAN = """
import importlib, json, pkgutil, typing
import tos
from tos.canonical._base import DigestBoundArtifact

for mod in pkgutil.walk_packages(tos.__path__, prefix="tos."):
    try:
        importlib.import_module(mod.name)
    except Exception:
        pass


def subclasses(cls):
    for sub in cls.__subclasses__():
        yield sub
        yield from subclasses(sub)


def has_set(annotation, seen):
    origin = typing.get_origin(annotation)
    if origin in (set, frozenset):
        return True
    args = typing.get_args(annotation)
    if args:
        return any(has_set(a, seen) for a in args)
    if hasattr(annotation, "model_fields") and annotation not in seen:
        seen = seen | {annotation}
        return any(has_set(f.annotation, seen) for f in annotation.model_fields.values())
    return False


def direct_set(annotation):
    # A set the model owns DIRECTLY (not through a nested model) — the shape this probe can
    # populate with `model_construct` and therefore observe.
    origin = typing.get_origin(annotation)
    if origin in (set, frozenset):
        return True
    return any(direct_set(a) for a in typing.get_args(annotation))


# Five tokens whose set iteration order is essentially never the sorted one by chance; three
# independent draws make a coincidence (1/120 each) negligible.
PROBES = [
    ("zeta", "alpha", "omega", "beta", "kappa"),
    ("q9", "a1", "m5", "z0", "c3"),
    ("SESSION_PHASE", "ORDER_TYPE_TIF", "PRICE_TICK_LOT_QUANTITY", "AAA", "ZZZ"),
]


def sorts_field(cls, name):
    \"\"\"Does this model's covered_content() emit `name` in sorted order? Observed, not
    inferred from whether an override exists.\"\"\"
    for probe in PROBES:
        try:
            instance = cls.model_construct(**{name: frozenset(probe)})
            emitted = instance.covered_content().get(name)
        except Exception:
            return None  # cannot observe this field here
        if not isinstance(emitted, list):
            return None
        if emitted != sorted(emitted):
            return False
    return True


total, sorted_models, unsorted_models, unobserved = 0, {}, {}, {}
for cls in set(subclasses(DigestBoundArtifact)):
    covered = getattr(cls, "_COVERED_FIELDS", None)
    if not covered:
        continue
    total += 1
    fields = [
        n
        for n in covered
        if (f := cls.model_fields.get(n)) and has_set(f.annotation, frozenset())
    ]
    if not fields:
        continue
    observable = [
        n for n in fields if direct_set(cls.model_fields[n].annotation)
    ]
    verdicts = {n: sorts_field(cls, n) for n in observable}
    if observable and all(v is True for v in verdicts.values()):
        sorted_models[cls.__name__] = sorted(observable)
    elif any(v is False for v in verdicts.values()):
        unsorted_models[cls.__name__] = sorted(fields)
    else:
        # Only reachable when NO owned set field can be observed directly (the set lives in a
        # nested model), so the sorting question is answered the same way: it does not sort.
        unsorted_models[cls.__name__] = sorted(fields)
        unobserved[cls.__name__] = sorted(set(fields) - set(observable))
print(
    json.dumps(
        {
            "total": total,
            "sorts_every_owned_set_field": sorted_models,
            "does_not_sort": unsorted_models,
            "not_directly_observable": unobserved,
        }
    )
)
"""


def _scan_set_covered_models() -> dict:
    completed = subprocess.run(
        [sys.executable, "-B", "-c", _SET_COVERED_SCAN],
        capture_output=True,
        text=True,
        check=True,
        env={
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", "/tmp"),
            "PYTHONPATH": str(_REPO_ROOT / "tos" / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )
    scan = json.loads(completed.stdout.strip().splitlines()[-1])
    assert isinstance(scan, dict), completed.stdout
    return scan


def test_set_covered_digest_instability_is_a_class_of_models_not_one_instance() -> None:
    """**The defect's SCOPE, pinned (measured 2026-09-24, review-797 MEDIUM-3 / round-2 LOW-2).**

    ``covered_content()``'s ``model_dump(mode="json", …)`` emits a set in set-iteration order
    and the canonicalizer treats a sequence as order-significant, so a canonical model with a
    set in covered content digests differently per process — UNLESS its ``covered_content()``
    sorts that field, which some families do for exactly this reason
    (``tos/src/tos/cur/records.py:44-49``, design #23 §3.1).

    **The partition is by OBSERVED SORTING, not by "overrides ``covered_content``"**
    (round-2 LOW-2). The first cut split on ``cls.covered_content is not base_impl``, which
    would file a *pass-through* override — ``super().covered_content()`` and nothing else — on
    the safe side; two such overrides already exist (``ExactTrialPlan``,
    ``ActiveSafetyIncidentSet``), harmless only because they own no set field today. Here each
    owned set field is populated through ``model_construct`` and the emitted list is checked
    against ``sorted(...)``, over three unrelated five-token probes so a coincidental sorted
    iteration (1/120 per probe) cannot pass.

    Pinning only ``VenueConstraintPolicy`` would let a fix to that one class turn the
    companion test GREEN and read as "fixed" while twelve other models stayed broken. This
    pins the partition BY NAME.

    It also records what it could NOT observe: seven models keep their set inside a NESTED
    model, which ``model_construct`` cannot populate from here. They are filed as
    "does not sort" — the conservative side, and the correct one, since none of them
    overrides ``covered_content()`` at all.
    """
    scan = _scan_set_covered_models()

    assert scan["total"] == 120, scan
    assert set(scan["sorts_every_owned_set_field"]) == {
        "CurrentnessPolicy",
        "RestrictiveFenceRecord",
        "SafetyDeviationPolicy",
        "SafetyIncidentPolicy",
        "TrialEvidencePackage",
        "TrialPolicy",
    }, scan
    assert set(scan["does_not_sort"]) == {
        "BrokerCapabilityProfile",
        "HumanApprovalRequest",
        "HumanAuthorityPolicy",
        "HumanDelegationRecord",
        "HumanHaltCommand",
        "LiveAuthorization",
        "OrderAdmissibilityDecision",
        "ReArmApprovalRecord",
        "RecoveryInventoryCut",
        "RecoveryObligation",
        "RecoveryReadinessDecision",
        "StatementCoverageManifest",
        "VenueConstraintPolicy",
    }, scan
    # 6 + 13 = the 19 models that carry a set in covered content at all.
    assert len(scan["sorts_every_owned_set_field"]) + len(scan["does_not_sort"]) == 19
    # The one this deployment actually digests today.
    assert "VenueConstraintPolicy" in scan["does_not_sort"]
    # Recorded, not asserted away: the set lives in a nested model for these.
    assert set(scan["not_directly_observable"]) == {
        "BrokerCapabilityProfile",
        "HumanApprovalRequest",
        "HumanDelegationRecord",
        "HumanHaltCommand",
        "LiveAuthorization",
        "OrderAdmissibilityDecision",
        "ReArmApprovalRecord",
    }, scan


def test_every_sorting_model_sorts_every_set_field_it_owns() -> None:
    """No PARTIAL sorter may hide in the safe group.

    A model that sorts four of its five set covered fields is still process-dependent, and the
    partition above would file it as safe if the check were per-model rather than per-field.
    The scan only admits a model when EVERY owned set field it can observe sorts; this pins the
    field lists so a newly added, unsorted field shows up here.
    """
    scan = _scan_set_covered_models()

    assert scan["sorts_every_owned_set_field"] == {
        "CurrentnessPolicy": ["required_dimensions"],
        "RestrictiveFenceRecord": ["affected_scope"],
        "SafetyDeviationPolicy": [
            "eligible_deviation_classes",
            "prohibited_deviation_classes",
            "required_compensating_control_classes",
            "required_evidence_levels",
            "scope_dimensions",
        ],
        "SafetyIncidentPolicy": ["authoritative_signal_classes"],
        "TrialEvidencePackage": ["present_element_classes"],
        "TrialPolicy": [
            "eligible_trial_classes",
            "prohibited_trial_classes",
            "required_evidence_classes",
            "scope_dimensions",
        ],
    }, scan


def test_currentness_policy_digest_is_stable_because_it_sorts(tmp_path: Path) -> None:
    """The measured counter-example to a type-only scan: the DEPLOYED ``currentness.yaml``
    builds a ``CurrentnessPolicy`` whose digest is IDENTICAL across hash seeds, because that
    class sorts its set covered field. Cited so the fix for the 13 does not re-derive it.
    """
    script = (
        "import sys;from pathlib import Path;"
        "from tos_runtime.compose._currentness_wiring import _build_currentness_policy;"
        "print(_build_currentness_policy(Path(sys.argv[1])).canonical_digest)"
    )

    def _digest(seed: str) -> str:
        completed = subprocess.run(
            [sys.executable, "-B", "-c", script, str(_SOURCE)],
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

    assert _digest(_SEED_A) == _digest(_SEED_B)
