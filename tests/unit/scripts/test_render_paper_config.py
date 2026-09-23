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
        ("marketfeed.yaml", "account: null", "marketfeed.yaml::account"),
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
