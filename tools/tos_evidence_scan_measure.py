#!/usr/bin/env python3
"""Preflight + watchdog driver for the evidence scan measurement (growth plan §2 A1-b).

``tools/tos_evidence_scan_bench.py`` knows how to build a synthetic evidence file and time
the runtime's ``FROM entries WHERE kind ...`` shapes against it. It knows nothing about the
host it runs on. This module is the part that does: it **refuses to start** and **aborts
mid-run** when the machine cannot afford the measurement, and it writes the evidence of
having checked.

Why it exists (plan §7.1.7 deviations 11 and 11-b). The 2026-09-30 A1 run was driven by a
script that carried exactly these guards — and that script was never committed and is gone
from the host, so the plan had to withdraw the claim that "the next run is protected again".
The same round found the swap floor had been missing from those guards all along, which
matters because in the 2026-09-30 00:24 KST earlyoom incident (§7.1.5) the thing that hit
zero first was **swap**, not ``MemAvailable``. Both holes close by the guards living here,
in the tree, default-on, with tests.

What it drives (three child steps, matching ``~/.local/state/tos/measure/a1/`` naming so the
plan's tables stay comparable):

===========  ==============================================  ==========================
step         child command                                   artifacts
===========  ==============================================  ==========================
``build``    ``bench build --days N``                        ``build-Nd.json`` (the
                                                             child's own BuildReport on
                                                             stdout)
``before``   ``bench measure``                               ``before-Nd.json``
``after``    ``bench measure --create-index``                ``after-Nd.json``
===========  ==============================================  ==========================

There is no separate "build index" step because the bench does not offer one: index creation
lives inside ``measure --create-index`` (``create_kind_index`` then measure, in one child), so
the index build time is reported by the child on its own stdout and captured in
``after-Nd.out``. Every step additionally gets ``<step>-Nd.time`` (GNU ``time -v`` field names,
so an existing citation like "``before-90d.time`` の ``File system inputs``" keeps working) and
``<step>-Nd.resource.json`` (the same numbers structured, plus the child's ``/proc/<pid>/io``).

**Resource capture uses** ``os.wait4`` **, not** ``getrusage(RUSAGE_CHILDREN)`` **deltas.**
``RUSAGE_CHILDREN.ru_maxrss`` is a running maximum over every child reaped so far, so a
before/after difference attributes a step's peak RSS exactly only when that step raised the
maximum — for the ``measure`` steps, whose peak is well under ``build``'s, the difference is
zero and says nothing. ``os.wait4(pid, ...)`` returns the rusage of **that one child**, from
the same kernel counters GNU ``time -v`` reads, so every field below is per-step and exact.
That is a deliberate improvement on the mechanism A1-b was specified with, not a shortcut.

**Physical vs logical reads** (plan §7.1.2 said the measurement lacked this): ``ru_inblock``
gives what ``time -v`` calls "File system inputs" (512-byte blocks, block layer), and the
child's ``/proc/<pid>/io`` gives ``rchar`` (bytes the process asked for, page cache included)
next to ``read_bytes`` (bytes actually fetched from storage). The ``/proc`` numbers are the
last sample taken before the child exited, so each record carries its own
``sample_age_seconds`` — an unavoidable residual bounded by ``--watch-interval-s``, reported
rather than hidden.

Pure stdlib, and it imports nothing from ``tos``/``tos_runtime``: the import firewall
(``tools/tos_firewall_check.py`` rule (e)/TOS-FW-R) forbids anything outside ``tos/`` from
reaching in. It does load its sibling bench module by path, which is not a firewall concern
(``tools`` importing ``tools``) and is what keeps the disk estimate below tied to the bench's
own ``profile_kinds`` and drift guard instead of a second copy of the ``entries`` DDL.

Every threshold is an argument. The two that gate the START of a run come from the operator's
global rule; the rest are named below with their actual source, including the ones this
driver chose itself.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import shutil
import signal
import subprocess
import sys
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from types import ModuleType
from zoneinfo import ZoneInfo

__all__ = [
    "AbortRecord",
    "GuardConfig",
    "HostReader",
    "HostSample",
    "MeasureAborted",
    "MeasureRefused",
    "PreflightCheck",
    "PreflightRecord",
    "SizeEstimate",
    "Step",
    "SyntheticDisposition",
    "StepResult",
    "decide_synthetic_disposition",
    "estimate_synthetic_size",
    "main",
    "plan_steps",
    "preflight",
    "run_step",
]

_KST = ZoneInfo("Asia/Seoul")
_GB = 1024.0**3

# --------------------------------------------------------------------------------------
# Thresholds. Each default names where it comes from — an operator rule, a measurement in
# the plan, or this driver's own judgement. None of them is a bare literal in a branch.
# --------------------------------------------------------------------------------------

#: START floor on ``MemAvailable``. Source: operator rule in ``~/.claude/CLAUDE.md``,
#: section "로컬 빌드 동시 실행 제한" (2026-09-25): do not start when available is under 6 GB.
DEFAULT_MIN_AVAILABLE_GB = 6.0

#: START floor on ``SwapFree``. Source: the SAME operator rule, the clause that the lost
#: driver did not implement (plan §7.1.7 deviation 11-b): "**또는 Swap free 가 2GB 미만**
#: 이면 빌드를 시작하지 않는다". It is not decoration — in the §7.1.5 earlyoom incident swap
#: was the number at zero.
DEFAULT_MIN_SWAP_FREE_GB = 2.0

#: IN-RUN abort floor on ``MemAvailable``. Source: the value the 2026-09-30 run's (lost)
#: driver enforced, as recorded in plan §7.1.2 — "진행 중 < 4 GB 면 워치독이 해당 단계를
#: 중단". Kept so a rerun is comparable with that run.
DEFAULT_ABORT_AVAILABLE_GB = 4.0

#: IN-RUN abort floor on ``SwapFree``. **No external rule sets one** — the global rule speaks
#: only about starting. This is this driver's own value: half the start floor, the same
#: relationship the memory pair has (4 of 6). Stated as a choice, not dressed up as a rule.
DEFAULT_ABORT_SWAP_FREE_GB = 1.0

#: Seconds between host samples while a child runs. This driver's own value, matching the
#: cadence plan §7.1.5's "재발 방지" describes ("5 초마다").
DEFAULT_WATCH_INTERVAL_S = 5.0

#: Seconds a child gets after ``SIGTERM`` before ``SIGKILL``. This driver's own value: the
#: bench's steps hold an open sqlite connection and nothing else, so there is no long
#: unwind to wait for, but a hung interpreter must not keep the host under pressure either.
DEFAULT_TERM_GRACE_S = 10.0

#: Multiplier applied to the predicted synthetic size for the disk check. The prediction
#: covers the synthetic FILE only; the ``after`` step additionally creates
#: ``entries_kind_seq`` in place (+1.8 % of file size, measured at both 30 and 90 days —
#: plan §7.1.2) and sqlite needs transient room while building it. 1.25 is this driver's
#: own margin over that measurement.
DEFAULT_DISK_HEADROOM_RATIO = 1.25

#: Processes whose presence means "a heavy build is already running on this host". Source:
#: the global rule's own check, ``pgrep -af 'GradleWrapperMain|GradleWorkerMain'``, plus
#: ``GradleDaemon`` (the rule's separate instruction to look for leftover daemons).
COMPETING_BUILD_PATTERN = "GradleWrapperMain|GradleWorkerMain|GradleDaemon"

#: A second measurement of this kind already in flight. Two of these on one host is the
#: co-tenancy the whole preflight exists to prevent, and it would also race on the
#: synthetic file and the artifact names.
COMPETING_MEASURE_PATTERN = "tos_evidence_scan_(measure|bench)"

#: Commands whose mention of a pattern means they are LOOKING FOR it, not running it. The
#: global rule's own check ends in ``| grep -v pgrep`` for this reason, and the case is real:
#: the first live run of this preflight (2026-09-30) matched another agent session's
#: ``bash -c "... pgrep -f 'GradleWrapperMain|...' ..."``, whose command line contains the
#: marker only because it is searching for it.
#:
#: This skips a match, so it is worth being exact about what it can hide. Every pattern this
#: driver searches for is either a JVM main-class name or this tool's own filename, and a
#: shell that both runs ``pgrep`` and launches a build is not itself the heavy process — the
#: ``java`` (or ``python``) child it starts carries the marker on its own command line and is
#: matched on its own. What this cannot see is a build whose ONLY process is a shell whose
#: command line also contains ``grep``; there is no such thing for these markers.
_SEARCH_COMMANDS = frozenset({"pgrep", "grep", "egrep", "fgrep", "rg", "ugrep"})

#: How many of the most recent samples an abort record carries. Bounds artifact size; gates
#: nothing, which is why it is not an argument.
_ABORT_SAMPLE_TAIL = 10

#: How many processes the top-RSS record holds. The global rule asks for ``ps
#: --sort=-rss | head`` as a record of what else is on the host; it is context for reading a
#: run afterwards, not a gate.
_TOP_RSS_ROWS = 5

#: Longest command line kept in the top-RSS record. A JVM command line runs to kilobytes
#: (the 2026-09-30 host had one over 4 KB) and would otherwise dominate the artifact.
_TOP_RSS_ARGS_CHARS = 200

STEP_NAMES = ("build", "before", "after")


class MeasureRefused(RuntimeError):
    """Preflight said no, or an argument makes no sense. Nothing was started."""


class MeasureAborted(RuntimeError):
    """A guard fired while a child was running. The child was terminated and an
    ``ABORTED-<step>-<days>d.json`` artifact was written."""


def _now_kst() -> str:
    return datetime.now(_KST).isoformat(timespec="milliseconds")


def _load_bench_module(bench_path: Path) -> ModuleType:
    """Load the sibling bench as a module so the size estimate reuses ITS distribution
    reader (and therefore its ``entries`` shape drift guard) rather than carrying a second
    copy of the schema. ``tools`` importing ``tools`` is outside the firewall's concern;
    importing ``tos_runtime`` would not be."""
    import importlib.util

    if not bench_path.is_file():
        raise MeasureRefused(f"no bench module at {bench_path}")
    spec = importlib.util.spec_from_file_location(
        "tos_evidence_scan_bench_for_measure", bench_path
    )
    if spec is None or spec.loader is None:
        raise MeasureRefused(f"cannot load bench module from {bench_path}")
    module = importlib.util.module_from_spec(spec)
    # Registered BEFORE exec: `@dataclass` resolves annotations through
    # `sys.modules[cls.__module__]`, so a module that is not there yet makes every frozen
    # dataclass in the bench fail to build.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------------------
# Host observation
# --------------------------------------------------------------------------------------


def _is_searching_for_the_pattern(args: str) -> bool:
    """Whether a matched command line is a SEARCH for the marker rather than a build.

    See :data:`_SEARCH_COMMANDS` for why this exists and exactly what it can and cannot
    hide. Token-wise, not substring-wise, so a path like ``/opt/grepbuild/gradlew`` is still
    a build.
    """
    return any(
        os.path.basename(token) in _SEARCH_COMMANDS
        for token in args.replace("'", " ").split()
    )


@dataclass(frozen=True)
class CompetingProcess:
    """One process a competition check matched, with enough of its command line to tell
    the operator what to wait for."""

    pid: int
    pattern: str
    args: str


@dataclass(frozen=True)
class HostSample:
    """One observation of the host, taken before a run and repeatedly during one."""

    at_kst: str
    mem_available_bytes: int
    swap_free_bytes: int
    swap_total_bytes: int
    competing: tuple[CompetingProcess, ...] = ()
    child_peak_rss_bytes: int | None = None
    child_io: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "at_kst": self.at_kst,
            "mem_available_bytes": self.mem_available_bytes,
            "mem_available_gb": round(self.mem_available_bytes / _GB, 3),
            "swap_free_bytes": self.swap_free_bytes,
            "swap_free_gb": round(self.swap_free_bytes / _GB, 3),
            "swap_total_bytes": self.swap_total_bytes,
            "competing": [asdict(c) for c in self.competing],
            "child_peak_rss_bytes": self.child_peak_rss_bytes,
            "child_io": dict(self.child_io),
        }


@dataclass(frozen=True)
class HostReader:
    """Everything this driver knows about the machine, behind one injectable seam.

    The paths and command lines are constructor arguments so a test can point the reader at
    a fake ``/proc/meminfo`` and a fake ``pgrep`` and exercise each refusal for real, instead
    of patching module globals and proving only that the patch worked.
    """

    meminfo_path: Path = Path("/proc/meminfo")
    pgrep_argv: tuple[str, ...] = ("pgrep", "-af")
    ps_argv: tuple[str, ...] = ("ps", "-eo", "pid,rss,args", "--sort=-rss")
    proc_root: Path = Path("/proc")

    # -- memory ------------------------------------------------------------------------

    def meminfo(self) -> dict[str, int]:
        """``MemAvailable``/``SwapFree``/``SwapTotal`` in BYTES.

        Raises:
            MeasureRefused: the file is unreadable, or a field the guards need is missing.
                Fail closed: a preflight that cannot read memory has not checked memory.
        """
        try:
            text = self.meminfo_path.read_text()
        except OSError as exc:
            raise MeasureRefused(f"cannot read {self.meminfo_path}: {exc}") from exc
        values: dict[str, int] = {}
        for line in text.splitlines():
            name, _, rest = line.partition(":")
            parts = rest.split()
            if not parts:
                continue
            try:
                amount = int(parts[0])
            except ValueError:
                continue
            unit = parts[1].lower() if len(parts) > 1 else "b"
            values[name.strip()] = amount * 1024 if unit == "kb" else amount
        missing = [
            k for k in ("MemAvailable", "SwapFree", "SwapTotal") if k not in values
        ]
        if missing:
            raise MeasureRefused(
                f"{self.meminfo_path} has no {', '.join(missing)} — refusing rather than "
                "assuming a value for a field the memory guards are built on"
            )
        return values

    # -- competing processes -----------------------------------------------------------

    def competing_processes(self, pattern: str) -> tuple[CompetingProcess, ...]:
        """Processes matching ``pattern``, excluding this process and its own ancestors.

        The self-exclusion is by PID identity, walked up ``/proc/<pid>/status``'s ``PPid``
        chain: with :data:`COMPETING_MEASURE_PATTERN` the driver's own command line matches,
        and so does the shell that launched it. Excluding the chain removes exactly this
        invocation and leaves a genuinely concurrent second driver visible.
        """
        argv = (*self.pgrep_argv, pattern)
        try:
            # argv is a constructed list, never a shell string.
            completed = subprocess.run(
                argv, capture_output=True, text=True, check=False
            )
        except OSError as exc:
            raise MeasureRefused(f"cannot run {argv[0]}: {exc}") from exc
        # pgrep exits 1 for "no match" — that is not an error. Any other non-zero exit is.
        if completed.returncode not in (0, 1):
            raise MeasureRefused(
                f"{argv[0]} exited {completed.returncode}: "
                f"{completed.stderr.strip() or '(no stderr)'}"
            )
        mine = self._self_pid_chain()
        found: list[CompetingProcess] = []
        for line in completed.stdout.splitlines():
            pid_text, _, args = line.strip().partition(" ")
            try:
                pid = int(pid_text)
            except ValueError:
                continue
            if pid in mine or _is_searching_for_the_pattern(args):
                continue
            found.append(
                CompetingProcess(
                    pid=pid, pattern=pattern, args=args[:_TOP_RSS_ARGS_CHARS]
                )
            )
        return tuple(found)

    def _self_pid_chain(self) -> frozenset[int]:
        chain = {os.getpid()}
        pid = os.getpid()
        for _ in range(64):  # bounded: a runaway /proc must not hang the preflight
            ppid = self._parent_pid(pid)
            if ppid is None or ppid in chain or ppid <= 0:
                break
            chain.add(ppid)
            pid = ppid
        return frozenset(chain)

    def _parent_pid(self, pid: int) -> int | None:
        try:
            for line in (self.proc_root / str(pid) / "status").read_text().splitlines():
                if line.startswith("PPid:"):
                    return int(line.split()[1])
        except (OSError, ValueError, IndexError):
            return None
        return None

    # -- record-only observations --------------------------------------------------------

    def top_rss(self, rows: int = _TOP_RSS_ROWS) -> tuple[dict[str, object], ...]:
        """The heaviest processes on the host, for the record. Never a gate — the global
        rule asks for this so that a run can be read afterwards next to what else was
        resident (2026-09-30: a 16 GB python in another session)."""
        try:
            completed = subprocess.run(
                self.ps_argv, capture_output=True, text=True, check=False
            )
        except OSError as exc:
            return ({"error": f"cannot run {self.ps_argv[0]}: {exc}"},)
        out: list[dict[str, object]] = []
        for line in completed.stdout.splitlines()[1 : rows + 1]:
            parts = line.split(maxsplit=2)
            if len(parts) < 3:
                continue
            try:
                out.append(
                    {
                        "pid": int(parts[0]),
                        "rss_kb": int(parts[1]),
                        "args": parts[2][:_TOP_RSS_ARGS_CHARS],
                    }
                )
            except ValueError:
                continue
        return tuple(out)

    def child_peak_rss_bytes(self, pid: int) -> int | None:
        """``VmHWM`` of a running child — the kernel's own high-water mark, so a single late
        read reports the peak so far. ``None`` once the process is gone."""
        try:
            for line in (self.proc_root / str(pid) / "status").read_text().splitlines():
                if line.startswith("VmHWM:"):
                    return int(line.split()[1]) * 1024
        except (OSError, ValueError, IndexError):
            return None
        return None

    def child_io(self, pid: int) -> dict[str, int]:
        """``/proc/<pid>/io`` of a running child: ``rchar``/``wchar`` are what the process
        asked for (page cache included), ``read_bytes``/``write_bytes`` what the block layer
        actually moved. The gap between them is the physical-vs-logical distinction plan
        §7.1.2 recorded as missing."""
        try:
            text = (self.proc_root / str(pid) / "io").read_text()
        except OSError:
            return {}
        out: dict[str, int] = {}
        for line in text.splitlines():
            name, _, rest = line.partition(":")
            try:
                out[name.strip()] = int(rest.strip())
            except ValueError:
                continue
        return out

    def sample(self, *, child_pid: int | None = None) -> HostSample:
        info = self.meminfo()
        competing = self.competing_processes(
            COMPETING_BUILD_PATTERN
        ) + self.competing_processes(COMPETING_MEASURE_PATTERN)
        if child_pid is not None:
            competing = tuple(c for c in competing if c.pid != child_pid)
        return HostSample(
            at_kst=_now_kst(),
            mem_available_bytes=info["MemAvailable"],
            swap_free_bytes=info["SwapFree"],
            swap_total_bytes=info["SwapTotal"],
            competing=competing,
            child_peak_rss_bytes=(
                self.child_peak_rss_bytes(child_pid) if child_pid is not None else None
            ),
            child_io=self.child_io(child_pid) if child_pid is not None else {},
        )


# --------------------------------------------------------------------------------------
# Guards
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class GuardConfig:
    """The four memory floors plus the watchdog's cadence and kill escalation.

    Raises:
        MeasureRefused: on construction through :meth:`validated`, when an abort floor sits
            at or above the matching start floor. That combination is a guard that admits
            what it names: preflight would pass at exactly the level the watchdog is
            supposed to call fatal, so the first sample of a healthy run would abort it —
            or, read the other way, the start floor would be the real in-run floor and the
            abort floor decoration.
    """

    min_available_bytes: int
    min_swap_free_bytes: int
    abort_available_bytes: int
    abort_swap_free_bytes: int
    watch_interval_s: float
    term_grace_s: float
    watchdog_enabled: bool = True

    @classmethod
    def validated(
        cls,
        *,
        min_available_gb: float,
        min_swap_free_gb: float,
        abort_available_gb: float,
        abort_swap_free_gb: float,
        watch_interval_s: float,
        term_grace_s: float,
        watchdog_enabled: bool = True,
    ) -> GuardConfig:
        if abort_available_gb > min_available_gb:
            raise MeasureRefused(
                f"--abort-available-gb {abort_available_gb} is above --min-available-gb "
                f"{min_available_gb}: the watchdog would abort a run the preflight had just "
                "let start"
            )
        if abort_swap_free_gb > min_swap_free_gb:
            raise MeasureRefused(
                f"--abort-swap-free-gb {abort_swap_free_gb} is above --min-swap-free-gb "
                f"{min_swap_free_gb}: the watchdog would abort a run the preflight had just "
                "let start"
            )
        if watch_interval_s <= 0:
            raise MeasureRefused(
                f"--watch-interval-s must be > 0, got {watch_interval_s}"
            )
        if term_grace_s < 0:
            raise MeasureRefused(f"--term-grace-s must be >= 0, got {term_grace_s}")
        return cls(
            min_available_bytes=int(min_available_gb * _GB),
            min_swap_free_bytes=int(min_swap_free_gb * _GB),
            abort_available_bytes=int(abort_available_gb * _GB),
            abort_swap_free_bytes=int(abort_swap_free_gb * _GB),
            watch_interval_s=watch_interval_s,
            term_grace_s=term_grace_s,
            watchdog_enabled=watchdog_enabled,
        )

    def in_run_breach(self, sample: HostSample) -> tuple[str, str] | None:
        """``(check, reason)`` for the first in-run floor ``sample`` crosses, else ``None``.

        Every reason names the check and the measured value, so an abort artifact never
        says only "aborted".
        """
        if sample.mem_available_bytes < self.abort_available_bytes:
            return (
                "mem_available",
                f"MemAvailable {sample.mem_available_bytes / _GB:.2f} GB is below the "
                f"in-run floor {self.abort_available_bytes / _GB:.2f} GB",
            )
        if sample.swap_free_bytes < self.abort_swap_free_bytes:
            return (
                "swap_free",
                f"SwapFree {sample.swap_free_bytes / _GB:.2f} GB is below the in-run floor "
                f"{self.abort_swap_free_bytes / _GB:.2f} GB",
            )
        if sample.competing:
            first = sample.competing[0]
            return (
                "competing_build",
                f"a competing process appeared: pid {first.pid} matching "
                f"{first.pattern!r} ({first.args})",
            )
        return None


# --------------------------------------------------------------------------------------
# Size estimate — how big the synthetic file will be, derived, never guessed
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class SizeEstimate:
    """What ``build --days N`` is predicted to write, and how the prediction was made.

    Derivation, so a reader can check it rather than trust it:

    1. ``profile_kinds`` (the bench's own, so the ``entries`` shape drift guard applies)
       gives each kind's row count and ``payload_json`` byte total in the REFERENCE file.
    2. The bench replicates a kind ``days`` times when it holds at most
       ``--boot-once-max-rows`` rows (a once-per-boot record) and
       ``round(days * session_hours * 60 / reference_minutes)`` times otherwise. This module
       reapplies that rule; ``tests/tools/test_tos_evidence_scan_measure.py`` builds a real
       synthetic file and asserts :attr:`predicted_rows` equals the bench's own reported row
       count exactly, so the copy cannot drift silently.
    3. Rows carry more than payload (identifiers, two digests, sqlite page overhead). The
       ratio of those is measured from the reference file itself —
       ``reference_file_bytes / reference_payload_bytes`` — rather than assumed.

    Checked against the 2026-09-30 run's own artifact (``a1/build-30d.json``), from the same
    reference file: predicted rows 2,359,200 vs written 2,359,200 — **exact** — and predicted
    4,471,389,391 B vs written 4,373,725,184 B, i.e. **2.2 % high**. The estimate therefore
    errs toward refusing a marginal disk rather than filling it.
    """

    reference: str
    days: int
    reference_file_bytes: int
    reference_payload_bytes: int
    overhead_ratio: float
    recurring_repeats: int
    boot_repeats: int
    predicted_rows: int
    predicted_payload_bytes: int
    predicted_file_bytes: int
    source: str


def estimate_synthetic_size(
    reference: Path,
    *,
    days: int,
    session_hours: float,
    reference_minutes: float,
    boot_once_max_rows: int,
    bench: ModuleType,
) -> SizeEstimate:
    """Predict the synthetic file's size from the reference distribution. See
    :class:`SizeEstimate` for the derivation."""
    if days < 1:
        raise MeasureRefused(f"--days must be >= 1, got {days}")
    if reference_minutes <= 0:
        raise MeasureRefused(
            f"--reference-minutes must be > 0, got {reference_minutes}"
        )
    try:
        profiles = bench.profile_kinds(reference)
    except bench.BenchRefused as exc:
        raise MeasureRefused(f"reference unusable: {exc}") from exc

    recurring_repeats = round(days * session_hours * 60.0 / reference_minutes)
    boot_repeats = days
    predicted_rows = 0
    predicted_payload = 0
    reference_payload = 0
    for profile in profiles:
        reference_payload += profile.payload_bytes
        repeats = (
            boot_repeats if profile.rows <= boot_once_max_rows else recurring_repeats
        )
        predicted_rows += profile.rows * repeats
        predicted_payload += profile.payload_bytes * repeats

    reference_file_bytes = reference.stat().st_size
    overhead_ratio = (
        reference_file_bytes / reference_payload if reference_payload else 1.0
    )
    return SizeEstimate(
        reference=str(reference),
        days=days,
        reference_file_bytes=reference_file_bytes,
        reference_payload_bytes=reference_payload,
        overhead_ratio=overhead_ratio,
        recurring_repeats=recurring_repeats,
        boot_repeats=boot_repeats,
        predicted_rows=predicted_rows,
        predicted_payload_bytes=predicted_payload,
        predicted_file_bytes=int(predicted_payload * overhead_ratio),
        source="derived-from-reference-distribution",
    )


# --------------------------------------------------------------------------------------
# Steps
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Step:
    """One child process the driver runs, with where its output goes."""

    name: str
    argv: tuple[str, ...]
    stdout_path: Path
    stderr_path: Path


def plan_steps(
    *,
    names: Sequence[str],
    python: str,
    bench_path: Path,
    reference: Path,
    synthetic: Path,
    out_dir: Path,
    days: int,
    repeats: int,
    session_hours: float,
    reference_minutes: float,
    boot_once_max_rows: int,
    batch_rows: int,
) -> tuple[Step, ...]:
    """The child command lines, in the order they must run.

    ``before`` and ``after`` both write their measurement JSON through the bench's own
    ``--json-out``, which refuses to overwrite an earlier run's numbers; ``build`` has no
    such flag, so its stdout (a ``BuildReport`` JSON object) IS ``build-Nd.json``.
    """
    unknown = [n for n in names if n not in STEP_NAMES]
    if unknown:
        raise MeasureRefused(
            f"unknown step(s) {unknown}: choose from {', '.join(STEP_NAMES)}"
        )
    if not names:
        raise MeasureRefused("--steps selected nothing to run")
    ordered = [n for n in STEP_NAMES if n in names]
    bench = str(bench_path)
    steps: list[Step] = []
    for name in ordered:
        argv: tuple[str, ...]
        if name == "build":
            argv = (
                python,
                bench,
                "build",
                "--reference",
                str(reference),
                "--out",
                str(synthetic),
                "--days",
                str(days),
                "--session-hours",
                str(session_hours),
                "--reference-minutes",
                str(reference_minutes),
                "--boot-once-max-rows",
                str(boot_once_max_rows),
                "--batch-rows",
                str(batch_rows),
            )
            stdout_path = out_dir / f"build-{days}d.json"
        else:
            argv = (
                python,
                bench,
                "measure",
                "--db",
                str(synthetic),
                "--repeats",
                str(repeats),
                "--explain",
                "--json-out",
                str(out_dir / f"{name}-{days}d.json"),
            )
            if name == "after":
                argv = (*argv, "--create-index")
            stdout_path = out_dir / f"{name}-{days}d.out"
        steps.append(
            Step(
                name=name,
                argv=argv,
                stdout_path=stdout_path,
                stderr_path=out_dir / f"{name}-{days}d.err",
            )
        )
    return tuple(steps)


@dataclass(frozen=True)
class StepResult:
    """One step's outcome and its exact per-child resource usage."""

    name: str
    argv: tuple[str, ...]
    started_at_kst: str
    finished_at_kst: str
    wall_seconds: float
    returncode: int
    terminated_by_signal: int | None
    max_rss_bytes: int
    user_seconds: float
    system_seconds: float
    fs_inputs_blocks: int
    fs_outputs_blocks: int
    minor_faults: int
    major_faults: int
    voluntary_switches: int
    involuntary_switches: int
    proc_io: dict[str, int]
    proc_io_sample_age_seconds: float | None
    samples_taken: int

    def as_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["argv"] = list(self.argv)
        data["max_rss_mb"] = round(self.max_rss_bytes / (1024.0 * 1024.0), 1)
        return data


@dataclass(frozen=True)
class AbortRecord:
    """What an ``ABORTED-<step>-<days>d.json`` holds. A mid-run stop is never silent."""

    run_id: str
    step: str
    days: int
    check: str
    reason: str
    at_kst: str
    elapsed_seconds: float
    signal_sent: str
    escalated_to_sigkill: bool
    returncode: int
    #: How far the stopped child actually got — the numbers plan §7.1.2 could not cite for
    #: the aborted 365-day pass because nothing recorded them.
    partial_resource: dict[str, object]
    last_samples: tuple[dict[str, object], ...]


def _spawn(argv: Sequence[str], stdout_path: Path, stderr_path: Path) -> int:
    executable = argv[0]
    if not os.path.isabs(executable):
        resolved = shutil.which(executable)
        if resolved is None:
            raise MeasureRefused(f"cannot find {executable} on PATH")
        executable = resolved
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    file_actions = [
        (os.POSIX_SPAWN_OPEN, 1, str(stdout_path), flags, 0o644),
        (os.POSIX_SPAWN_OPEN, 2, str(stderr_path), flags, 0o644),
    ]
    return os.posix_spawn(executable, list(argv), os.environ, file_actions=file_actions)


def _terminate(
    pid: int, *, grace_s: float, sleep: Callable[[float], None]
) -> tuple[bool, int, resource.struct_rusage]:
    """``SIGTERM``, then ``SIGKILL`` after ``grace_s``.

    Returns ``(escalated, status, rusage)``. The rusage is the killed child's own, and it
    is returned rather than discarded because plan §7.1.2's complaint about the aborted
    365-day pass was precisely that it left no numbers behind: ``before-365d.time`` was
    0 bytes, ``before-365d.json`` never existed, and every figure the first draft cited
    for that pass had to be demoted to a hypothesis. A stopped step now reports how far it
    got.
    """
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        _, status, usage = os.wait4(pid, 0)
        return (False, status, usage)
    deadline = time.monotonic() + grace_s
    poll = min(0.05, grace_s) if grace_s > 0 else 0.0
    while time.monotonic() < deadline:
        done, status, usage = os.wait4(pid, os.WNOHANG)
        if done == pid:
            return (False, status, usage)
        if poll:
            sleep(poll)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    _, status, usage = os.wait4(pid, 0)
    return (True, status, usage)


def run_step(
    step: Step,
    *,
    guard: GuardConfig,
    reader: HostReader,
    run_id: str,
    days: int,
    out_dir: Path,
    log: Callable[[str], None],
    sampler: Callable[[int], HostSample] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> StepResult:
    """Run one child under the watchdog.

    The loop is single-threaded on purpose: the driver has nothing else to do while a child
    runs, and a thread would add a synchronization story to a component whose whole job is
    to be trustworthy. Samples go to ``watchdog.jsonl`` as they are taken, so an abort — or
    a kill of the driver itself — still leaves the series behind.

    Args:
        sampler: Overrides how a sample is taken, for tests that need a specific series.
            Production passes ``None`` and the injected :class:`HostReader` is used.

    Raises:
        MeasureAborted: a floor was crossed or a competing build appeared. The child is
            terminated and the abort artifact is written before this is raised.
    """
    take = sampler or (lambda pid: reader.sample(child_pid=pid))
    watchdog_path = out_dir / "watchdog.jsonl"
    samples: list[dict[str, object]] = []
    last_io: dict[str, int] = {}
    last_io_at: float | None = None
    peak_rss_sampled = 0

    log(f"########## days={days} {step.name}")
    log(f"argv: {' '.join(step.argv)}")
    started_wall = time.monotonic()
    started_at = _now_kst()
    pid = _spawn(step.argv, step.stdout_path, step.stderr_path)

    def record(sample: HostSample) -> None:
        nonlocal last_io, last_io_at, peak_rss_sampled
        row = sample.as_dict()
        row.update(
            {
                "run_id": run_id,
                "step": step.name,
                "days": days,
                "elapsed_seconds": round(time.monotonic() - started_wall, 3),
                "watchdog_enabled": guard.watchdog_enabled,
            }
        )
        samples.append(row)
        with watchdog_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
        if sample.child_io:
            last_io = dict(sample.child_io)
            last_io_at = time.monotonic()
        if sample.child_peak_rss_bytes:
            peak_rss_sampled = max(peak_rss_sampled, sample.child_peak_rss_bytes)

    def guard_or_abort(sample: HostSample) -> None:
        if not guard.watchdog_enabled:
            return
        breach = guard.in_run_breach(sample)
        if breach is None:
            return
        check, reason = breach
        log(f"ABORT ({step.name}): {reason}")
        escalated, status, usage = _terminate(
            pid, grace_s=guard.term_grace_s, sleep=sleep
        )
        record_out = AbortRecord(
            run_id=run_id,
            step=step.name,
            days=days,
            check=check,
            reason=reason,
            at_kst=_now_kst(),
            elapsed_seconds=round(time.monotonic() - started_wall, 3),
            signal_sent="SIGTERM",
            escalated_to_sigkill=escalated,
            returncode=-os.WTERMSIG(status) if os.WIFSIGNALED(status) else status,
            partial_resource={
                "max_rss_bytes": max(usage.ru_maxrss * 1024, peak_rss_sampled),
                "user_seconds": usage.ru_utime,
                "system_seconds": usage.ru_stime,
                "fs_inputs_blocks": usage.ru_inblock,
                "fs_outputs_blocks": usage.ru_oublock,
                "proc_io": dict(last_io),
                "proc_io_sample_age_seconds": (
                    round(time.monotonic() - last_io_at, 3)
                    if last_io_at is not None
                    else None
                ),
            },
            last_samples=tuple(samples[-_ABORT_SAMPLE_TAIL:]),
        )
        path = out_dir / f"ABORTED-{step.name}-{days}d.json"
        path.write_text(json.dumps(asdict(record_out), indent=2), encoding="utf-8")
        log(f"wrote {path}")
        raise MeasureAborted(reason)

    try:
        # One sample immediately, before the first wait: a child that finishes inside a
        # single interval still leaves a series behind, and a competing build that appeared
        # between preflight and spawn is caught here rather than a whole step later.
        first = take(pid)
        record(first)
        guard_or_abort(first)
        while True:
            done, status, usage = os.wait4(pid, os.WNOHANG)
            if done == pid:
                break
            sleep(guard.watch_interval_s)
            sample = take(pid)
            record(sample)
            guard_or_abort(sample)
    except MeasureAborted:
        raise
    except BaseException:
        # A driver that dies must not leave the child holding the host.
        try:
            _terminate(pid, grace_s=guard.term_grace_s, sleep=sleep)
        except ChildProcessError:
            pass
        raise

    wall = time.monotonic() - started_wall
    signalled = os.WTERMSIG(status) if os.WIFSIGNALED(status) else None
    returncode = -signalled if signalled is not None else os.WEXITSTATUS(status)
    rusage_peak = usage.ru_maxrss * 1024
    result = StepResult(
        name=step.name,
        argv=step.argv,
        started_at_kst=started_at,
        finished_at_kst=_now_kst(),
        wall_seconds=wall,
        returncode=returncode,
        terminated_by_signal=signalled,
        max_rss_bytes=max(rusage_peak, peak_rss_sampled),
        user_seconds=usage.ru_utime,
        system_seconds=usage.ru_stime,
        fs_inputs_blocks=usage.ru_inblock,
        fs_outputs_blocks=usage.ru_oublock,
        minor_faults=usage.ru_minflt,
        major_faults=usage.ru_majflt,
        voluntary_switches=usage.ru_nvcsw,
        involuntary_switches=usage.ru_nivcsw,
        proc_io=last_io,
        proc_io_sample_age_seconds=(
            round(time.monotonic() - last_io_at, 3) if last_io_at is not None else None
        ),
        samples_taken=len(samples),
    )
    _write_resource_artifacts(result, out_dir=out_dir, days=days)
    log(
        f"{step.name}: rc={result.returncode} wall={result.wall_seconds:.2f}s "
        f"maxrss={result.max_rss_bytes / (1024 * 1024):.1f}MB "
        f"fs_inputs={result.fs_inputs_blocks} blocks"
    )
    return result


def _format_elapsed(seconds: float) -> str:
    """GNU ``time``'s own ``h:mm:ss`` / ``m:ss.ss`` rendering, so the two are comparable."""
    hours, rest = divmod(seconds, 3600.0)
    minutes, secs = divmod(rest, 60.0)
    if hours >= 1:
        return f"{int(hours)}:{int(minutes):02d}:{int(secs):02d}"
    return f"{int(minutes)}:{secs:05.2f}"


def _write_resource_artifacts(result: StepResult, *, out_dir: Path, days: int) -> None:
    """``<step>-Nd.time`` (GNU ``time -v`` field names) and ``<step>-Nd.resource.json``.

    Two files rather than one because they answer different readers. The ``.time`` file
    keeps the plan's existing citations working — §7.1.2 quotes ``before-90d.time``'s
    ``File system inputs`` line — so the same grep must keep finding the same field name.
    The JSON carries what GNU ``time`` cannot: the child's ``/proc/<pid>/io``, and the age of
    that sample. Fields GNU ``time`` prints but ``wait4`` does not supply are OMITTED rather
    than zero-filled; a zero that means "not measured" is the kind of number this plan has
    already had to withdraw once.
    """
    percent_cpu = (
        int(100.0 * (result.user_seconds + result.system_seconds) / result.wall_seconds)
        if result.wall_seconds > 0
        else 0
    )
    lines = [
        "# produced by tools/tos_evidence_scan_measure.py from os.wait4() rusage of this",
        "# child — GNU `time -v` field names, fields wait4 does not supply are omitted.",
        f'\tCommand being timed: "{" ".join(result.argv)}"',
        f"\tUser time (seconds): {result.user_seconds:.2f}",
        f"\tSystem time (seconds): {result.system_seconds:.2f}",
        f"\tPercent of CPU this job got: {percent_cpu}%",
        "\tElapsed (wall clock) time (h:mm:ss or m:ss): "
        f"{_format_elapsed(result.wall_seconds)}",
        f"\tMaximum resident set size (kbytes): {result.max_rss_bytes // 1024}",
        f"\tMajor (requiring I/O) page faults: {result.major_faults}",
        f"\tMinor (reclaiming a frame) page faults: {result.minor_faults}",
        f"\tVoluntary context switches: {result.voluntary_switches}",
        f"\tInvoluntary context switches: {result.involuntary_switches}",
        f"\tFile system inputs: {result.fs_inputs_blocks}",
        f"\tFile system outputs: {result.fs_outputs_blocks}",
        f"\tExit status: {result.returncode}",
    ]
    (out_dir / f"{result.name}-{days}d.time").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    (out_dir / f"{result.name}-{days}d.resource.json").write_text(
        json.dumps(result.as_dict(), indent=2), encoding="utf-8"
    )


# --------------------------------------------------------------------------------------
# Preflight
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class PreflightCheck:
    """One gate, its measured value and its floor. A refusal quotes this verbatim."""

    check: str
    ok: bool
    measured: str
    floor: str
    source: str
    detail: str = ""


@dataclass(frozen=True)
class PreflightRecord:
    """Everything the preflight looked at, written to ``preflight.json`` whether it passed
    or refused — a refusal that leaves no artifact is indistinguishable from never having
    run (plan §7.1.2's complaint about citing session memory)."""

    run_id: str
    at_kst: str
    tool: str
    verdict: str
    argv: tuple[str, ...]
    checks: tuple[PreflightCheck, ...]
    thresholds: dict[str, object]
    estimate: dict[str, object] | None
    top_rss: tuple[dict[str, object], ...]
    watchdog_enabled: bool
    warnings: tuple[str, ...]
    steps_planned: tuple[str, ...]
    refusal: str | None = None

    def as_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["argv"] = list(self.argv)
        return data


@dataclass(frozen=True)
class SyntheticDisposition:
    """What to do with the synthetic file this run created, and what to tell the operator.

    ``action`` is one of ``delete`` / ``keep-partial`` / ``keep-resumable``.
    """

    action: str
    message: str


def decide_synthetic_disposition(
    path: Path, *, remaining: Sequence[str], size_bytes: int
) -> SyntheticDisposition:
    """Delete the synthetic file only when every planned step actually ran.

    Plan §7.1.2 keeps peak disk at one file by deleting each size's synthetic DB once its
    before/after pair is done. An abort is exactly when NOT to apply that: the watchdog
    fires because the host is short of MEMORY, and deleting a 53 GB file does nothing for
    memory while costing the operator the whole build (366 s at 365 days).

    Two unfinished cases, because they need different advice:

    * ``build`` still in ``remaining`` — the file is a PARTIAL write. It is not measurable
      and the bench refuses to overwrite an existing ``--out``, so the honest instruction is
      "delete it before rebuilding", not a resume that cannot work.
    * ``build`` done, a measure step left — the file is complete and the run really is
      resumable with ``--steps``.
    """
    size_gb = size_bytes / _GB
    if not remaining:
        return SyntheticDisposition("delete", f"removed synthetic {path}")
    if "build" in remaining:
        return SyntheticDisposition(
            "keep-partial",
            f"KEPT synthetic {path} ({size_gb:.2f} GB) — INCOMPLETE: the build step did not "
            "finish, so this file is a partial write, not a measurable one. It is kept so "
            "nothing is deleted behind your back; delete it before rebuilding (the bench "
            "refuses to overwrite an existing --out).",
        )
    return SyntheticDisposition(
        "keep-resumable",
        f"KEPT synthetic {path} ({size_gb:.2f} GB) — the run did not finish, so the build "
        "it already paid for is not thrown away. Once the host recovers, resume with "
        f"--steps {','.join(remaining)}, then delete the file by hand.",
    )


def _disk_free(path: Path) -> int:
    """Free bytes on the filesystem that will hold ``path``, walking up to the nearest
    directory that exists (the synthetic file's parent is often not created yet)."""
    probe = path if path.exists() else path.parent
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return shutil.disk_usage(probe).free


def preflight(
    *,
    run_id: str,
    guard: GuardConfig,
    reader: HostReader,
    out_dir: Path,
    days: int,
    estimate: SizeEstimate | None,
    expect_bytes: int | None,
    disk_headroom_ratio: float,
    steps: Sequence[Step],
    argv: Sequence[str],
    synthetic: Path,
    warnings: Sequence[str] = (),
) -> PreflightRecord:
    """Check the host, write ``preflight.json``/``preflight.jsonl``, and refuse if anything
    fails.

    Order matters only for readability — every check runs, so one artifact names every
    problem rather than making the operator fix them one refusal at a time.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    checks: list[PreflightCheck] = []

    info = reader.meminfo()
    checks.append(
        PreflightCheck(
            check="mem_available",
            ok=info["MemAvailable"] >= guard.min_available_bytes,
            measured=f"{info['MemAvailable'] / _GB:.2f} GB",
            floor=f"{guard.min_available_bytes / _GB:.2f} GB",
            source="operator rule ~/.claude/CLAUDE.md 로컬 빌드 동시 실행 제한 (2026-09-25)",
        )
    )
    checks.append(
        PreflightCheck(
            check="swap_free",
            ok=info["SwapFree"] >= guard.min_swap_free_bytes,
            measured=f"{info['SwapFree'] / _GB:.2f} GB",
            floor=f"{guard.min_swap_free_bytes / _GB:.2f} GB",
            source="same operator rule — the clause plan §7.1.7 deviation 11-b records as missing",
            detail=f"SwapTotal {info['SwapTotal'] / _GB:.2f} GB",
        )
    )

    for pattern, label in (
        (COMPETING_BUILD_PATTERN, "competing_build"),
        (COMPETING_MEASURE_PATTERN, "competing_measurement"),
    ):
        found = reader.competing_processes(pattern)
        checks.append(
            PreflightCheck(
                check=label,
                ok=not found,
                measured=(
                    "none"
                    if not found
                    else "; ".join(f"pid {p.pid} {p.args}" for p in found)
                ),
                floor="none running",
                source=(
                    "operator rule — 동시에 도는 무거운 빌드는 호스트 전체에서 1개"
                    if label == "competing_build"
                    else "this driver: two measurements would race on the host and on the artifacts"
                ),
            )
        )

    base_bytes = (
        expect_bytes
        if expect_bytes is not None
        else (estimate.predicted_file_bytes if estimate else 0)
    )
    required_bytes = int(base_bytes * disk_headroom_ratio)
    worst_free = min(_disk_free(out_dir), _disk_free(synthetic.parent))
    checks.append(
        PreflightCheck(
            check="disk_free",
            ok=worst_free >= required_bytes,
            measured=f"{worst_free / _GB:.2f} GB free",
            floor=f"{required_bytes / _GB:.2f} GB needed",
            source=(
                f"--expect-gb (operator-supplied) x --disk-headroom-ratio {disk_headroom_ratio}"
                if expect_bytes is not None
                else f"predicted synthetic size x --disk-headroom-ratio {disk_headroom_ratio}"
            ),
            detail=(
                ""
                if estimate is None
                else (
                    f"predicted {estimate.predicted_file_bytes / _GB:.2f} GB "
                    f"({estimate.predicted_rows} rows) from {estimate.reference}"
                )
            ),
        )
    )

    existing = [
        str(p)
        for step in steps
        for p in (
            step.stdout_path,
            step.stderr_path,
            out_dir / f"{step.name}-{days}d.json",
        )
        if p.exists()
    ]
    checks.append(
        PreflightCheck(
            check="artifacts_absent",
            ok=not existing,
            measured=(
                "none present" if not existing else "; ".join(sorted(set(existing)))
            ),
            floor="no step artifact may already exist",
            source=(
                "this driver, matching the bench's own --json-out rule: a measurement is "
                "evidence a plan cites, and a later run must not silently replace it"
            ),
        )
    )

    top_rss = reader.top_rss()
    failed = [c for c in checks if not c.ok]
    refusal = (
        None
        if not failed
        else " | ".join(
            f"{c.check}: measured {c.measured}, need {c.floor}" for c in failed
        )
    )
    record = PreflightRecord(
        run_id=run_id,
        at_kst=_now_kst(),
        tool="tools/tos_evidence_scan_measure.py",
        verdict="ok" if refusal is None else "refused",
        argv=tuple(argv),
        checks=tuple(checks),
        thresholds={
            "min_available_gb": guard.min_available_bytes / _GB,
            "min_swap_free_gb": guard.min_swap_free_bytes / _GB,
            "abort_available_gb": guard.abort_available_bytes / _GB,
            "abort_swap_free_gb": guard.abort_swap_free_bytes / _GB,
            "watch_interval_s": guard.watch_interval_s,
            "term_grace_s": guard.term_grace_s,
            "disk_headroom_ratio": disk_headroom_ratio,
        },
        estimate=asdict(estimate) if estimate else None,
        top_rss=top_rss,
        watchdog_enabled=guard.watchdog_enabled,
        warnings=tuple(warnings),
        steps_planned=tuple(s.name for s in steps),
        refusal=refusal,
    )
    payload = record.as_dict()
    (out_dir / "preflight.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    with (out_dir / "preflight.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")
    return record


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------


def _add_guard_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--min-available-gb",
        type=float,
        default=DEFAULT_MIN_AVAILABLE_GB,
        help="Start floor on MemAvailable (default from the operator's global build rule).",
    )
    parser.add_argument(
        "--min-swap-free-gb",
        type=float,
        default=DEFAULT_MIN_SWAP_FREE_GB,
        help="Start floor on SwapFree (same rule). 0 opts out explicitly, e.g. a swapless host.",
    )
    parser.add_argument(
        "--abort-available-gb",
        type=float,
        default=DEFAULT_ABORT_AVAILABLE_GB,
        help="In-run abort floor on MemAvailable (the 2026-09-30 run's value, plan §7.1.2).",
    )
    parser.add_argument(
        "--abort-swap-free-gb",
        type=float,
        default=DEFAULT_ABORT_SWAP_FREE_GB,
        help="In-run abort floor on SwapFree (this driver's own value; no rule sets one).",
    )
    parser.add_argument(
        "--watch-interval-s", type=float, default=DEFAULT_WATCH_INTERVAL_S
    )
    parser.add_argument("--term-grace-s", type=float, default=DEFAULT_TERM_GRACE_S)
    parser.add_argument(
        "--no-watchdog",
        action="store_true",
        help=(
            "Run WITHOUT the in-run guard. Preflight still runs. Recorded as a warning in "
            "preflight.json and printed on stderr — the 2026-09-30 00:24 incident is what "
            "this flag turns off."
        ),
    )
    parser.add_argument(
        "--disk-headroom-ratio", type=float, default=DEFAULT_DISK_HEADROOM_RATIO
    )
    parser.add_argument(
        "--expect-gb",
        type=float,
        default=None,
        help="Override the derived disk estimate with an explicit figure.",
    )


def _add_shared_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--synthetic", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--days", required=True, type=int)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--session-hours", type=float, default=7.0)
    parser.add_argument("--reference-minutes", type=float, default=15.0)
    parser.add_argument("--boot-once-max-rows", type=int, default=1)
    parser.add_argument("--batch-rows", type=int, default=10000)
    parser.add_argument("--steps", default=",".join(STEP_NAMES))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument(
        "--bench",
        type=Path,
        default=Path(__file__).resolve().parent / "tos_evidence_scan_bench.py",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Preflight + watchdog driver for the evidence scan measurement (growth plan "
            "§2 A1-b). Refuses to start, and aborts mid-run, when the host cannot afford it."
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="Preflight, then drive build/before/after.")
    _add_shared_arguments(run_parser)
    _add_guard_arguments(run_parser)
    run_parser.add_argument(
        "--keep-synthetic",
        action="store_true",
        help=(
            "Keep the synthetic file after the run. Default is to delete it so peak disk "
            "stays one file (plan §7.1.2); only a file this run created is ever deleted."
        ),
    )

    pre_parser = sub.add_parser(
        "preflight", help="Run only the preflight and report — starts no child."
    )
    _add_shared_arguments(pre_parser)
    _add_guard_arguments(pre_parser)

    return parser


def _print_preflight(record: PreflightRecord, *, log: Callable[[str], None]) -> None:
    for check in record.checks:
        mark = "ok " if check.ok else "NO "
        log(f"preflight {mark}{check.check}: {check.measured} (floor: {check.floor})")
        if check.detail:
            log(f"           {check.detail}")
    for row in record.top_rss:
        log(f"top-rss {row}")
    for warning in record.warnings:
        log(f"WARNING: {warning}")


def main(argv: list[str] | None = None, *, reader: HostReader | None = None) -> int:
    """Entry point.

    Args:
        reader: Where the host facts come from. Deliberately NOT a command-line option —
            the operator must not be able to point the guards at a friendlier ``/proc``
            from the shell. Tests pass one so that "does this refusal fire" is decided by
            the injected host and not by whatever else happens to be running.
    """
    raw = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(raw)
    out_dir: Path = args.out_dir
    run_id = uuid.uuid4().hex[:12]
    log_lines: list[str] = []

    def log(message: str) -> None:
        log_lines.append(message)
        print(message, flush=True)

    try:
        guard = GuardConfig.validated(
            min_available_gb=args.min_available_gb,
            min_swap_free_gb=args.min_swap_free_gb,
            abort_available_gb=args.abort_available_gb,
            abort_swap_free_gb=args.abort_swap_free_gb,
            watch_interval_s=args.watch_interval_s,
            term_grace_s=args.term_grace_s,
            watchdog_enabled=not args.no_watchdog,
        )
        warnings: list[str] = []
        if not guard.watchdog_enabled:
            warnings.append(
                "--no-watchdog: the in-run memory/swap/co-tenant guard is OFF for this run. "
                "The 2026-09-30 00:24 KST earlyoom incident (plan §7.1.5) happened without it."
            )
            print(f"WARNING: {warnings[-1]}", file=sys.stderr)

        bench = _load_bench_module(args.bench)
        out_dir.mkdir(parents=True, exist_ok=True)
        estimate = estimate_synthetic_size(
            args.reference,
            days=args.days,
            session_hours=args.session_hours,
            reference_minutes=args.reference_minutes,
            boot_once_max_rows=args.boot_once_max_rows,
            bench=bench,
        )
        steps = plan_steps(
            names=[s.strip() for s in args.steps.split(",") if s.strip()],
            python=args.python,
            bench_path=args.bench,
            reference=args.reference,
            synthetic=args.synthetic,
            out_dir=out_dir,
            days=args.days,
            repeats=args.repeats,
            session_hours=args.session_hours,
            reference_minutes=args.reference_minutes,
            boot_once_max_rows=args.boot_once_max_rows,
            batch_rows=args.batch_rows,
        )
        reader = reader or HostReader()
        record = preflight(
            run_id=run_id,
            guard=guard,
            reader=reader,
            out_dir=out_dir,
            days=args.days,
            estimate=estimate,
            expect_bytes=None if args.expect_gb is None else int(args.expect_gb * _GB),
            disk_headroom_ratio=args.disk_headroom_ratio,
            steps=steps,
            argv=raw,
            synthetic=args.synthetic,
            warnings=warnings,
        )
        _print_preflight(record, log=log)
        if record.refusal is not None:
            raise MeasureRefused(record.refusal)
        log(f"preflight ok (days={args.days}, run {run_id})")
        if args.command == "preflight":
            return 0

        created_synthetic = not args.synthetic.exists()
        completed: list[str] = []
        try:
            for step in steps:
                run_step(
                    step,
                    guard=guard,
                    reader=reader,
                    run_id=run_id,
                    days=args.days,
                    out_dir=out_dir,
                    log=log,
                )
                completed.append(step.name)
        finally:
            # Deleted only after every planned step actually ran (plan §7.1.2: peak disk is
            # one file). An abort is exactly when NOT to delete it: the watchdog fires
            # because the host is short of MEMORY, which throwing away a 53 GB / 366 s build
            # does nothing for.
            if (
                created_synthetic
                and not args.keep_synthetic
                and args.synthetic.exists()
            ):
                disposition = decide_synthetic_disposition(
                    args.synthetic,
                    remaining=[s.name for s in steps if s.name not in completed],
                    size_bytes=args.synthetic.stat().st_size,
                )
                if disposition.action == "delete":
                    args.synthetic.unlink()
                log(disposition.message)
            (out_dir / f"measure-{args.days}d.log").write_text(
                "\n".join(log_lines) + "\n", encoding="utf-8"
            )
        return 0
    except (MeasureRefused, MeasureAborted) as exc:
        print(f"tos_evidence_scan_measure: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
