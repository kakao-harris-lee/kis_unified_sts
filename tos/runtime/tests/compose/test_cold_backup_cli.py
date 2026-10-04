"""``cold-backup`` subcommand tests (evidence growth plan §2 A3,
``docs/plans/2026-09-29-tos-evidence-growth-and-purge-plan.md``).

Unlike ``test_cli.py``, which monkeypatches every operations function and pins argument
parsing only, these drive the REAL
:func:`~tos_runtime.operations.cold_backup.cold_backup` against a real durable set — because
the thing this subcommand adds over ``backup-set --archive-dir`` is precisely that an operator
(or a cron line) supplies no coordinates beyond three directories, so the only way to show it
works is to let it do the whole run. The one substitution is the custody key source: a D4
custody root is this suite's heaviest fixture and contributes nothing to what is under test,
so :class:`FixedKeyProvider` stands in for it, exactly as ``test_cli.py``'s own archive tests
already substitute ``FileKeyProvider``.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest
from tos_runtime.compose import _backup_dispatch, cli
from tos_runtime.custody.ports import CustodyLoadRefused
from tos_runtime.evidence.store import EVIDENCE_SCHEMA_VERSION, EvidenceCorruption
from tos_runtime.operations import cold_backup as cold_backup_module
from tos_runtime.operations.backup_archive import BackupArchiveRefused
from tos_runtime.operations.backup_set import BackupSetRefused
from tos_runtime.operations.cold_backup import ColdBackupRefused, FilesystemFreeSpace
from tos_runtime.operations.key_rotation import KeyContinuityRefused
from tos_runtime.operations.schema_ledger import SchemaVersionRefused

from ..engine.conftest import FixedKeyProvider
from ..operations.test_backup_set import _build_live_set

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_CONFIG = """
backup_root: {backups}
archive_dir: {cold}
verify_root: {verify}
minimum_free_bytes: {floor}
xz_preset: 1
"""


def _prepare(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    floor: int = 1024,
    *,
    patch_key_provider: bool = True,
) -> Path:
    """A live set, a filled config directory, and (by default) a stand-in key provider.

    ``patch_key_provider=False`` leaves the REAL ``FileKeyProvider`` in place, for the one
    test that needs a genuine custody failure rather than a simulated one.
    """
    live_dir = tmp_path / "live"
    live_dir.mkdir()
    _build_live_set(live_dir, with_marketfeed=True)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "evidence_cold_backup.yaml").write_text(
        _CONFIG.format(
            backups=tmp_path / "backups",
            cold=tmp_path / "cold",
            verify=tmp_path / "verify",
            floor=floor,
        )
    )
    if patch_key_provider:
        monkeypatch.setattr(
            _backup_dispatch, "FileKeyProvider", lambda _root, **_kw: FixedKeyProvider()
        )
    return live_dir


def _argv(tmp_path: Path, live_dir: Path) -> list[str]:
    return [
        "cold-backup",
        "--data-dir",
        str(live_dir),
        "--config-dir",
        str(tmp_path / "config"),
        "--custody-root",
        str(tmp_path / "custody"),
    ]


def test_cold_backup_runs_the_whole_thing_from_three_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    live_dir = _prepare(tmp_path, monkeypatch)

    exit_code = cli.main(_argv(tmp_path, live_dir))

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "cold-backup: archived gen1" in out
    assert "read back and verified" in out
    assert (tmp_path / "cold" / "gen1.set.tar.xz").is_file()
    report_path = tmp_path / "cold" / "gen1.cold-backup.report.json"
    assert report_path.is_file()
    assert str(report_path) in out
    assert json.loads(report_path.read_text())["chain_verified"] is True


def test_a_second_run_needs_no_different_command_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The point of the subcommand: the Nth cron run is spelled exactly like the first. With
    ``backup-set`` the operator had to type an increasing ``--generation``."""
    live_dir = _prepare(tmp_path, monkeypatch)
    argv = _argv(tmp_path, live_dir)

    assert cli.main(argv) == 0
    assert cli.main(list(argv)) == 0

    out = capsys.readouterr().out
    assert "archived gen1" in out
    assert "archived gen2" in out


def test_a_missing_config_file_exits_one_and_names_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    live_dir = _prepare(tmp_path, monkeypatch)
    (tmp_path / "config" / "evidence_cold_backup.yaml").unlink()

    exit_code = cli.main(_argv(tmp_path, live_dir))

    assert exit_code == 1
    err = capsys.readouterr().err
    assert err.startswith("cold-backup: refused —")
    assert "evidence_cold_backup.yaml" in err
    # A refusal before anything is written: no snapshot, no archive.
    assert not (tmp_path / "backups").exists()
    assert not (tmp_path / "cold").exists()


def test_an_unfilled_config_exits_one_rather_than_backing_up_somewhere_invented(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The shipped ``config/tos_runtime/paper/evidence_cold_backup.yaml`` is in exactly this
    state until an operator fills it."""
    live_dir = _prepare(tmp_path, monkeypatch)
    (tmp_path / "config" / "evidence_cold_backup.yaml").write_text(
        "backup_root: null\narchive_dir: null\nverify_root: null\n"
        "minimum_free_bytes: null\n"
    )

    exit_code = cli.main(_argv(tmp_path, live_dir))

    assert exit_code == 1
    assert "still null (named-TBD)" in capsys.readouterr().err


#: One exemplar per LINE :data:`~tos_runtime.compose._backup_dispatch._REFUSAL_PREFIXES` can
#: produce. Seven types, seven prefixes (``custody refused`` is shared by two types, and
#: ``SchemaVersionRefused`` splits into two by ``direction``).
#:
#: The cases below are NOT a hand-kept parallel list: ``test_every_dispatch_row_has_a_case``
#: asserts this covers every row of that table, so adding a row without adding a case here is
#: red. The expected prefix stays a LITERAL on purpose — deriving it from the table too would
#: make the test agree with the code by construction and assert nothing.
_PREFIX_CASES: tuple[tuple[Exception, str], ...] = (
    (
        ColdBackupRefused("a destination is not somewhere a cold copy may live"),
        "cold-backup: refused —",
    ),
    (
        BackupSetRefused("a source file is absent"),
        "cold-backup: snapshot refused —",
    ),
    (
        BackupArchiveRefused("the archive does not hold what it claims to"),
        "cold-backup: archive refused —",
    ),
    (
        EvidenceCorruption("chain digest mismatch at seq 7"),
        "cold-backup: integrity refused —",
    ),
    (
        CustodyLoadRefused("no evidence.key.<generation> files found"),
        "cold-backup: custody refused —",
    ),
    (
        KeyContinuityRefused("HISTORY_UNVERIFIABLE"),
        "cold-backup: custody refused —",
    ),
    (
        SchemaVersionRefused(
            "evidence: on-disk schema user_version=1 is BEHIND this code's schema_version=2",
            direction="BEHIND",
        ),
        "cold-backup: migrate refused —",
    ),
    (
        SchemaVersionRefused(
            "evidence: on-disk schema user_version=3 is AHEAD of this code's schema_version=2",
            direction="AHEAD",
        ),
        "cold-backup: schema refused —",
    ),
)


def test_every_passthrough_verdict_has_a_dispatch_prefix() -> None:
    """The two tables must name the SAME types, and nothing enforced that before.

    A type added to ``_PASSTHROUGH_REFUSALS`` without a row in ``_REFUSAL_PREFIXES`` passes
    the whole suite and ships as ``cold-backup: failed — <ExcType>: …``: the verdict survives
    ``_stage`` intact and is then printed by the generic fallback, so the operator is sent to
    the "the host broke, re-run" row for something a re-run cannot fix. That is the exact
    live failure mode this PR was opened to remove, and it had been hand-synced four times
    (review round 2 F1 added three, this wave a fourth).

    Equality rather than ``<=``: today every routed type is also a passthrough type. If a
    verdict ever needs a prefix for the ``backup-set`` door only, split this into two
    assertions — do not delete it.
    """
    passthrough = set(cold_backup_module._PASSTHROUGH_REFUSALS)
    routed = {exc_type for exc_type, _ in _backup_dispatch._REFUSAL_PREFIXES}

    assert passthrough == routed


def _row_reached_by(exc: BaseException) -> type[BaseException] | None:
    """The row ``_refusal_line`` would actually use for ``exc`` — the FIRST isinstance match.

    Not ``type(exc)``: the table is matched by ``isinstance`` and two of its types are
    related (``CustodyLoadRefused`` is a ``CustodyError``), so an exemplar's own class is not
    the row it lands on.
    """
    for exc_type, _ in _backup_dispatch._REFUSAL_PREFIXES:
        if isinstance(exc, exc_type):
            return exc_type
    return None


def test_every_dispatch_row_has_a_case() -> None:
    """Every row of the dispatch table is REACHED by some case in :data:`_PREFIX_CASES`.

    Two defects at once, both silent. A row added without a case here means the parametrized
    test below quietly stops covering it. And a row that no exemplar can reach is a SHADOWED
    row — ``isinstance`` matching is ordered, so putting a base class above its subclass
    makes the lower one dead, and the operator gets the base class's prefix for a verdict
    that was given its own. Comparing reached-rows against the table catches both; comparing
    ``type(exc)`` would catch neither, and would itself be wrong here because
    ``CustodyLoadRefused`` lands on the ``CustodyError`` row.

    The input that makes this test fail, written down so the claim above is checkable:
    insert ``(RuntimeError, "refused")`` at the top of the table — every exemplar then
    reaches that one row and ``reached`` collapses to a single element (measured red). And
    what does NOT fail it: swapping ``KeyContinuityRefused`` and ``CustodyError``, because
    those two are unrelated classes (measured green) so that order shadows nothing. A test
    that went red on a harmless reorder would be pinning the table's spelling, not its
    meaning.
    """
    reached = {_row_reached_by(exc) for exc, _ in _PREFIX_CASES}
    routed = {exc_type for exc_type, _ in _backup_dispatch._REFUSAL_PREFIXES}

    assert reached == routed


#: The same exemplars, behind the OTHER door. Derived from :data:`_PREFIX_CASES` rather than
#: retyped: the property under test is that ``backup-set`` prints the SAME body as
#: ``cold-backup`` for the same verdict, so a second hand-kept list would be free to drift
#: into agreeing with nothing. Only the command name differs.
_BACKUP_SET_PREFIX_CASES: tuple[tuple[Exception, str], ...] = tuple(
    (refusal, expected.replace("cold-backup: ", "backup-set: ", 1))
    for refusal, expected in _PREFIX_CASES
)


@pytest.mark.parametrize(("refusal", "expected_prefix"), _BACKUP_SET_PREFIX_CASES)
def test_the_backup_set_door_routes_every_verdict_by_the_same_table(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    refusal: Exception,
    expected_prefix: str,
) -> None:
    """``backup-set --archive-dir`` reaches the same archive step, so it owes the same line.

    This door had NO stderr test at all (review round 2 finding 5). It was widened from
    ``except BackupArchiveRefused`` to the whole table, and nothing held that open: narrowing
    it back is invisible to the suite while the operator gets a traceback from one command
    and a routed one-line verdict from the other for the identical refusal.

    The input that makes this fail, so the claim is checkable: put ``BackupArchiveRefused``
    back as the sole ``except`` type in ``dispatch_backup_set`` — every other case then
    escapes as a traceback instead of a line (measured red).

    ``SchemaVersionRefused`` is covered in BOTH directions because this is the door where the
    two prescriptions differ and neither has an inner layer to name.
    """

    class _FakeManifest:
        generation = 1

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise refusal

    monkeypatch.setattr(
        _backup_dispatch, "backup_set", lambda *_a, **_kw: _FakeManifest()
    )
    monkeypatch.setattr(
        _backup_dispatch, "FileKeyProvider", lambda root, **_kw: ("keys", root)
    )
    monkeypatch.setattr(_backup_dispatch, "archive_backup_set", _raise)

    exit_code = cli.main(
        [
            "backup-set",
            "--data-dir",
            str(tmp_path / "data"),
            "--dest",
            str(tmp_path / "backups"),
            "--generation",
            "1",
            "--archive-dir",
            str(tmp_path / "cold"),
            "--verify-dir",
            str(tmp_path / "verify"),
            "--custody-root",
            str(tmp_path / "custody"),
        ]
    )

    assert exit_code == 1
    err = capsys.readouterr().err
    assert err.startswith(expected_prefix)
    assert "failed —" not in err
    assert "Traceback" not in err


def test_an_unclassified_direction_is_refused_rather_than_routed_to_ahead() -> None:
    """A direction nobody classified must stop, not quietly take the AHEAD row.

    The prefix used to be ``"migrate refused" if direction == "BEHIND" else "schema
    refused"``, so any third member of ``SchemaVersionDirection`` would have been prescribed
    "run the newer code or stop the lane" without anyone deciding that was right. The
    exhaustive ``match`` makes mypy reject an unhandled member at the gate; this test pins
    the RUNTIME half, which a type checker cannot reach — a value constructed past the
    annotation, which is exactly how such a value would arrive in practice.
    """
    unclassified = SchemaVersionRefused(
        "evidence: on-disk schema is SIDEWAYS of this code's schema_version=2",
        direction="SIDEWAYS",  # type: ignore[arg-type]
    )

    with pytest.raises(AssertionError):
        _backup_dispatch._schema_version_prefix(unclassified)


@pytest.mark.parametrize(("refusal", "expected_prefix"), _PREFIX_CASES)
def test_each_verdict_keeps_its_own_prefix_and_leaves_the_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    refusal: Exception,
    expected_prefix: str,
) -> None:
    """Seven verdict types, seven prefixes — a cron mail says which layer decided, or what the
    target needs, and the runbook §5 table routes by that word. ``integrity refused``
    especially must not read as ``failed``: "do not trust this copy" is not "re-run it".
    ``migrate refused`` and ``schema refused`` are the same shape one layer further out: the
    target disagrees about the schema, and no night of the same cron line changes that.
    """
    live_dir = _prepare(tmp_path, monkeypatch)

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise refusal

    monkeypatch.setattr(cold_backup_module, "archive_backup_set", _raise)

    exit_code = cli.main(_argv(tmp_path, live_dir))

    assert exit_code == 1
    err = capsys.readouterr().err
    assert err.startswith(expected_prefix)
    assert "failed —" not in err
    assert "Traceback" not in err
    assert (tmp_path / "backups" / "gen1.set.manifest.json").is_file()
    assert not (tmp_path / "cold" / "gen1.cold-backup.report.json").exists()


def _stamp_evidence_schema_version(live_dir: Path, version: int) -> None:
    """Put the live set's evidence file back at ``version`` on disk, nothing else.

    ``backup_set`` reads its evidence facts with a bare ``sqlite3.connect`` and never
    constructs a :class:`~tos_runtime.evidence.store.SqliteEvidenceStore`, so the snapshot
    still succeeds against an older schema. The archive's third check does construct one, out
    of the decompressed copy — which is where the refusal comes from, and why the whole
    durable set has already been copied by the time it arrives.
    """
    conn = sqlite3.connect(str(live_dir / "evidence.sqlite3"))
    try:
        conn.execute(f"PRAGMA user_version = {version}")
        conn.commit()
    finally:
        conn.close()


def test_an_older_evidence_schema_is_a_migrate_verdict_not_an_archive_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A real store one schema version behind, with nothing monkeypatched.

    This is the state measured on the deploy host: every boot-proof corpus there is at
    evidence schema v1 while ``EVIDENCE_SCHEMA_VERSION`` is 2 (runbook
    ``docs/runbooks/tos-evidence-cold-backup.md`` §4-5-2, the ⚠ paragraph, read-only survey
    2026-10-03), and
    the line it produced was ``cold-backup: archive failed — SchemaVersionRefused: …``. That
    prefix sent the operator to the ``archive failed`` row of the runbook's §5 table — "the
    host broke, fix it and re-run" — when re-running cannot change the on-disk schema. It is a
    verdict by :data:`~tos_runtime.operations.cold_backup._PASSTHROUGH_REFUSALS`'s own
    criterion, so it keeps its own prefix and the message names the action (plan §7.1.27
    A3-F1).
    """
    live_dir = _prepare(tmp_path, monkeypatch)
    _stamp_evidence_schema_version(live_dir, EVIDENCE_SCHEMA_VERSION - 1)

    exit_code = cli.main(_argv(tmp_path, live_dir))

    assert exit_code == 1
    err = capsys.readouterr().err
    assert err.startswith("cold-backup: migrate refused —")
    assert "failed —" not in err
    assert "Traceback" not in err
    assert len(err.strip().splitlines()) == 1
    # The message itself routes: the operator runs `migrate` on that data dir.
    assert "is BEHIND this code's schema_version" in err
    assert "`migrate` CLI" in err
    # Unchanged by this wave, and stated rather than assumed: the uncompressed snapshot is
    # already complete when the archive refuses, and the verify scratch is kept as the
    # evidence of why (runbook §4-5-2, the ⚠ paragraph and ①, measured on the host).
    assert (tmp_path / "backups" / "gen1" / "evidence.sqlite3").is_file()
    assert (tmp_path / "backups" / "gen1.set.manifest.json").is_file()
    assert (tmp_path / "verify" / "gen1.verify").is_dir()
    assert not (tmp_path / "cold" / "gen1.set.tar.xz").exists()
    assert not (tmp_path / "cold" / "gen1.cold-backup.report.json").exists()


def test_a_newer_evidence_schema_is_a_schema_verdict_not_a_migrate_instruction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The OTHER direction, end to end, with nothing monkeypatched.

    A store written by newer code than this runtime. It reaches the same exception type as
    the BEHIND case and used to reach the same prefix, which told the operator to run
    ``migrate`` — and ``apply_migrations`` refuses an AHEAD store before it writes anything
    (its own AHEAD guard in ``operations/schema_migrations.py``). So the instruction produced
    a second refusal every night, for ever. It is a verdict either way, which is why the type
    stays in the passthrough list, but it is NOT the same verdict, which is why the prefix
    now splits on ``direction``.
    """
    live_dir = _prepare(tmp_path, monkeypatch)
    _stamp_evidence_schema_version(live_dir, EVIDENCE_SCHEMA_VERSION + 1)

    exit_code = cli.main(_argv(tmp_path, live_dir))

    assert exit_code == 1
    err = capsys.readouterr().err
    assert err.startswith("cold-backup: schema refused —")
    # The BEHIND instruction must NOT appear: running `migrate` here is refused as well.
    assert "`migrate` CLI" not in err
    assert "is AHEAD of this code's schema_version" in err
    assert "failed —" not in err
    assert "Traceback" not in err
    assert len(err.strip().splitlines()) == 1
    # Same artifact retention as the BEHIND arm: the snapshot stage already finished.
    assert (tmp_path / "backups" / "gen1.set.manifest.json").is_file()
    assert (tmp_path / "verify" / "gen1.verify").is_dir()
    assert not (tmp_path / "cold" / "gen1.set.tar.xz").exists()
    assert not (tmp_path / "cold" / "gen1.cold-backup.report.json").exists()


def test_a_refusing_target_costs_one_full_generation_per_night(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """What an unattended lane actually accumulates while nobody acts on the verdict.

    The runbook says a refused night leaves the uncompressed generation behind and the next
    run takes the NEXT number. Stated in prose that is easy to believe and easy to be wrong
    about, so it is measured: two runs against the same stale target leave gen1 AND gen2, and
    neither produces an archive.
    """
    live_dir = _prepare(tmp_path, monkeypatch)
    _stamp_evidence_schema_version(live_dir, EVIDENCE_SCHEMA_VERSION - 1)

    assert cli.main(_argv(tmp_path, live_dir)) == 1
    assert cli.main(_argv(tmp_path, live_dir)) == 1

    assert (tmp_path / "backups" / "gen1" / "evidence.sqlite3").is_file()
    assert (tmp_path / "backups" / "gen2" / "evidence.sqlite3").is_file()
    assert sorted(p.name for p in (tmp_path / "cold").iterdir()) == []
    err = capsys.readouterr().err
    assert err.count("cold-backup: migrate refused —") == 2


def _free_space_stub(
    free_bytes: int,
) -> Callable[[Mapping[str, Path]], tuple[FilesystemFreeSpace, ...]]:
    def _stub(_roots: Mapping[str, Path]) -> tuple[FilesystemFreeSpace, ...]:
        return (
            FilesystemFreeSpace(
                roots=("archive_dir", "backup_root", "verify_root"),
                measured_path="/fake/root",
                free_bytes=free_bytes,
            ),
        )

    return _stub


def test_a_run_that_crosses_the_capacity_floor_warns_but_still_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    live_dir = _prepare(tmp_path, monkeypatch, floor=1_000_000)
    readings = iter([_free_space_stub(5_000_000), _free_space_stub(10)])
    monkeypatch.setattr(
        cold_backup_module, "_free_space", lambda roots: next(readings)(roots)
    )

    exit_code = cli.main(_argv(tmp_path, live_dir))

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "cold-backup: archived gen1" in captured.out
    assert "WARNING" in captured.err
    assert "the NEXT run will refuse" in captured.err
    assert (tmp_path / "cold" / "gen1.set.tar.xz").is_file()


def test_the_capacity_floor_refusal_exits_one_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    live_dir = _prepare(tmp_path, monkeypatch, floor=1_000_000)
    monkeypatch.setattr(cold_backup_module, "_free_space", _free_space_stub(10))

    exit_code = cli.main(_argv(tmp_path, live_dir))

    assert exit_code == 1
    err = capsys.readouterr().err
    assert err.startswith("cold-backup: refused —")
    assert "below the configured floor" in err
    assert not (tmp_path / "backups").exists()


# -- the §5 contract: every unattended failure is ONE line, never a traceback -


def _raise_locked(*_args: object, **_kwargs: object) -> None:
    raise sqlite3.OperationalError("database is locked")


def _raise_enospc(*_args: object, **_kwargs: object) -> None:
    raise OSError(28, "No space left on device")


@pytest.mark.parametrize(
    ("patched", "raises", "expected_prefix"),
    [
        (
            "backup_set",
            _raise_locked,
            "cold-backup: snapshot failed — OperationalError: database is locked",
        ),
        (
            "archive_backup_set",
            _raise_enospc,
            "cold-backup: archive failed — OSError:",
        ),
    ],
)
def test_an_environment_fault_prints_one_line_naming_the_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    patched: str,
    raises: object,
    expected_prefix: str,
) -> None:
    """The runbook §5 table promises the operator one line saying which layer stopped. Before
    this, the likeliest cron-time faults — the runtime still up, the disk full — were the ones
    that broke that promise, arriving as tracebacks."""
    live_dir = _prepare(tmp_path, monkeypatch)
    monkeypatch.setattr(cold_backup_module, patched, raises)

    exit_code = cli.main(_argv(tmp_path, live_dir))

    assert exit_code == 1
    err = capsys.readouterr().err
    assert err.startswith(expected_prefix)
    assert "Traceback" not in err
    assert len(err.strip().splitlines()) == 1


def test_a_real_unusable_custody_root_is_refused_before_the_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The REAL `FileKeyProvider`, over a custody root holding no keys — not a monkeypatched
    constructor. The previous version patched `FileKeyProvider` to raise, which the real
    constructor never does (it only stores fields), so it proved a branch that could not
    fire while the actual failure arrived after the whole set had been copied."""
    live_dir = _prepare(tmp_path, monkeypatch, patch_key_provider=False)
    (tmp_path / "custody").mkdir()

    exit_code = cli.main(_argv(tmp_path, live_dir))

    assert exit_code == 1
    err = capsys.readouterr().err
    assert err.startswith("cold-backup: custody refused —")
    assert "Traceback" not in err
    # Before the snapshot: nothing was copied.
    assert not (tmp_path / "backups").exists()
    assert not (tmp_path / "cold").exists()


def test_an_unparseable_config_prints_one_line_and_exits_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    live_dir = _prepare(tmp_path, monkeypatch)

    def _boom(_path: Path) -> None:
        raise RuntimeError("loader blew up in a way this module does not model")

    monkeypatch.setattr(_backup_dispatch, "load_cold_backup_config", _boom)

    exit_code = cli.main(_argv(tmp_path, live_dir))

    assert exit_code == 1
    assert capsys.readouterr().err.startswith(
        "cold-backup: config failed — RuntimeError:"
    )


def test_cold_backup_parses_into_its_own_args_object(tmp_path: Path) -> None:
    args = cli.parse_args(
        [
            "cold-backup",
            "--data-dir",
            str(tmp_path / "data"),
            "--config-dir",
            str(tmp_path / "config"),
            "--custody-root",
            str(tmp_path / "custody"),
        ]
    )

    assert isinstance(args, _backup_dispatch.ColdBackupArgs)
    assert args.data_dir == tmp_path / "data"
    assert args.config_dir == tmp_path / "config"
    assert args.custody_root == tmp_path / "custody"


def test_backup_set_still_takes_an_explicit_generation(tmp_path: Path) -> None:
    """``cold-backup`` is additive: the interactive one-off door is unchanged, including its
    hand-typed generation (TOS Phase 5 W4 decision 1, "세대는 호출자 지정")."""
    args = cli.parse_args(
        [
            "backup-set",
            "--data-dir",
            str(tmp_path / "data"),
            "--dest",
            str(tmp_path / "backups"),
            "--generation",
            "4",
        ]
    )

    assert isinstance(args, cli.BackupSetArgs)
    assert args.generation == 4
    assert args.archive_dir is None
