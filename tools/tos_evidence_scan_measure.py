#!/usr/bin/env python3
"""Preflight + watchdog driver for the evidence scan measurement (growth plan §2 A1-b)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import resource
import shlex
import shutil
import signal
import subprocess
import sys
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from pathlib import Path
from types import ModuleType
from zoneinfo import ZoneInfo

__all__ = [
    "AbortRecord",
    "CheckoutGuard",
    "CheckoutState",
    "GuardConfig",
    "HostReader",
    "HostSample",
    "MeasureAborted",
    "MeasureRefused",
    "MeasureSignalled",
    "MeasureStepFailed",
    "EarlierStep",
    "PreflightCheck",
    "PreflightRecord",
    "SizeEstimate",
    "earlier_step_mismatches",
    "read_checkout",
    "read_earlier_steps",
    "Step",
    "SyntheticDisposition",
    "StepResult",
    "abort_record_path",
    "decide_synthetic_disposition",
    "estimate_synthetic_size",
    "read_lock",
    "recorded_pass",
    "release_lock",
    "step_artifact_paths",
    "write_lock",
    "write_run_summary",
    "main",
    "move_step_artifacts_aside",
    "plan_steps",
    "preflight",
    "run_step",
]

_KST = ZoneInfo("Asia/Seoul")
_GB = 1024.0**3


DEFAULT_MIN_AVAILABLE_GB = 6.0

DEFAULT_MIN_SWAP_FREE_GB = 2.0

DEFAULT_ABORT_AVAILABLE_GB = 4.0

DEFAULT_ABORT_SWAP_FREE_GB = 1.0

DEFAULT_WATCH_INTERVAL_S = 5.0

DEFAULT_POLL_INTERVAL_S = 0.1

DEFAULT_HOST_READ_RETRIES = 1

DEFAULT_TERM_GRACE_S = 10.0

DEFAULT_DISK_HEADROOM_RATIO = 1.25

DEFAULT_INDEX_GROWTH_RATIO = 0.018

COMPETING_BUILD_PATTERN = "GradleWrapperMain|GradleWorkerMain|GradleDaemon"

COMPETING_MEASURE_PATTERN = (
    r"tos_evidence_scan_(measure|bench)\.py +(run|build|measure)\b"
)

_SEARCH_COMMANDS = frozenset({"pgrep", "grep", "egrep", "fgrep", "rg", "ugrep"})

_SHELL_PUNCTUATION = "\"'`;|&()<>{}$\n\t"

_SHELL_SEPARATORS = "`;|&()<>{}$\n"

_SHELLS = frozenset({"sh", "bash", "zsh", "dash", "ksh", "ash", "busybox"})

_COMMAND_PREFIXES = frozenset(
    {
        "!",
        "command",
        "do",
        "elif",
        "else",
        "env",
        "eval",
        "exec",
        "if",
        "nice",
        "nohup",
        "sudo",
        "then",
        "time",
        "until",
        "while",
        "xargs",
    }
)

_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

_ABORT_SAMPLE_TAIL = 10

_TOP_RSS_ROWS = 5

_TOP_RSS_ARGS_CHARS = 200

STEP_NAMES = ("build", "before", "after")

DEFAULT_GIT_TIMEOUT_S = 30.0

GIT_HARDENING_FLAGS = ("--no-optional-locks",)

CHILD_PYTHON_FLAGS = ("-I", "-S")


class MeasureRefused(RuntimeError):
    """Preflight said no, or an argument makes no sense. Nothing was started."""


class MeasureAborted(RuntimeError):
    """A guard fired while a child was running. The child was terminated and an"""


class MeasureSignalled(RuntimeError):
    """The driver itself was sent ``SIGTERM``/``SIGHUP``."""


class MeasureStepFailed(RuntimeError):
    """A child exited non-zero. The remaining steps do not run, the synthetic file is"""


def _now_kst() -> str:
    return datetime.now(_KST).isoformat(timespec="milliseconds")


def _load_bench_module(bench_path: Path) -> ModuleType:
    """Load the sibling bench as a module so the size estimate reuses ITS distribution"""
    import importlib.util

    if not bench_path.is_file():
        raise MeasureRefused(f"no bench module at {bench_path}")
    spec = importlib.util.spec_from_file_location(
        "tos_evidence_scan_bench_for_measure", bench_path
    )
    if spec is None or spec.loader is None:
        raise MeasureRefused(f"cannot load bench module from {bench_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _command_position_tokens(args: str) -> list[str]:
    """The tokens of ``args`` that sit where a COMMAND NAME goes."""
    sentinel = "\x00"
    for char in _SHELL_PUNCTUATION:
        args = args.replace(char, f" {sentinel} " if char in _SHELL_SEPARATORS else " ")
    tokens = args.split()
    out: list[str] = []
    at_command = True
    current_shell = False
    for token in tokens:
        if token == sentinel:
            at_command = True
            current_shell = False
            continue
        if at_command:
            if _ASSIGNMENT.match(token):
                continue
            base = os.path.basename(token)
            if base in _COMMAND_PREFIXES:
                continue
            out.append(token)
            current_shell = base in _SHELLS
            at_command = False
            continue
        if current_shell and token == "-c":
            at_command = True
    return out


def _is_searching_for_the_pattern(args: str) -> bool:
    """Whether a matched command line is a SEARCH for the marker rather than a build."""
    return any(
        os.path.basename(token) in _SEARCH_COMMANDS
        for token in _command_position_tokens(args)
    )


@dataclass(frozen=True)
class CompetingProcess:
    """One process a competition check matched, with enough of its command line to tell"""

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
    """Everything this driver knows about the machine, behind one injectable seam."""

    meminfo_path: Path = Path("/proc/meminfo")
    pgrep_argv: tuple[str, ...] = ("pgrep", "-af")
    ps_argv: tuple[str, ...] = ("ps", "-eo", "pid,rss,args", "--sort=-rss")
    proc_root: Path = Path("/proc")
    self_pid: int = field(default_factory=os.getpid)
    _cache: dict[str, object] = field(default_factory=dict, repr=False, compare=False)

    def meminfo(self) -> dict[str, int]:
        """``MemAvailable``/``SwapFree``/``SwapTotal`` in BYTES."""
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

    def _pgrep(self, pattern: str) -> list[tuple[int, str]]:
        """``pgrep -af <pattern>`` as ``(pid, args)`` pairs."""
        argv = (*self.pgrep_argv, pattern)
        try:
            completed = subprocess.run(
                argv, capture_output=True, text=True, check=False
            )
        except OSError as exc:
            raise MeasureRefused(f"cannot run {argv[0]}: {exc}") from exc
        if completed.returncode not in (0, 1):
            raise MeasureRefused(
                f"{argv[0]} exited {completed.returncode}: "
                f"{completed.stderr.strip() or '(no stderr)'}"
            )
        pairs: list[tuple[int, str]] = []
        for line in completed.stdout.splitlines():
            pid_text, _, args = line.strip().partition(" ")
            try:
                pairs.append((int(pid_text), args))
            except ValueError:
                continue
        return pairs

    def scan(
        self, patterns: Mapping[str, str]
    ) -> dict[str, tuple[CompetingProcess, ...]]:
        """Every named pattern, in ONE ``pgrep``, with this driver's own work excluded."""
        if not patterns:
            return {}
        combined = "|".join(f"({p})" for p in patterns.values())
        compiled = {name: re.compile(p) for name, p in patterns.items()}
        found: dict[str, list[CompetingProcess]] = {name: [] for name in patterns}
        mine = self._self_pid_chain()
        for pid, args in self._pgrep(combined):
            if pid in mine or _is_searching_for_the_pattern(args):
                continue
            if self._is_descendant_of(pid, mine):
                continue
            if self._has_pytest_ancestor(pid):
                continue
            for name, rx in compiled.items():
                if rx.search(args):
                    found[name].append(
                        CompetingProcess(
                            pid=pid,
                            pattern=patterns[name],
                            args=args[:_TOP_RSS_ARGS_CHARS],
                        )
                    )
        return {name: tuple(rows) for name, rows in found.items()}

    def competing_processes(self, pattern: str) -> tuple[CompetingProcess, ...]:
        """One pattern's matches. A thin wrapper over :meth:`scan` for single-pattern"""
        return self.scan({"only": pattern})["only"]

    def _ancestors(self, pid: int) -> list[int]:
        """``pid``'s ancestor chain, nearest first, bounded so a ``/proc`` oddity cannot"""
        chain: list[int] = []
        seen = {pid}
        current = pid
        for _ in range(64):
            parent = self._parent_pid(current)
            if parent is None or parent <= 0 or parent in seen:
                break
            chain.append(parent)
            seen.add(parent)
            current = parent
        return chain

    def _is_descendant_of(self, pid: int, forebears: frozenset[int]) -> bool:
        return any(ancestor in forebears for ancestor in self._ancestors(pid))

    def _has_pytest_ancestor(self, pid: int) -> bool:
        for ancestor in self._ancestors(pid):
            try:
                cmdline = (
                    (self.proc_root / str(ancestor) / "cmdline")
                    .read_bytes()
                    .replace(b"\0", b" ")
                    .decode("utf-8", "replace")
                )
            except OSError:
                continue
            if "pytest" in cmdline:
                return True
        return False

    def _self_pid_chain(self) -> frozenset[int]:
        cached = self._cache.get("self_pid_chain")
        if isinstance(cached, frozenset):
            return cached
        chain = {self.self_pid}
        pid = self.self_pid
        for _ in range(64):
            ppid = self._parent_pid(pid)
            if ppid is None or ppid in chain or ppid <= 0:
                break
            chain.add(ppid)
            pid = ppid
        frozen = frozenset(chain)
        self._cache["self_pid_chain"] = frozen
        return frozen

    def _parent_pid(self, pid: int) -> int | None:
        try:
            for line in (self.proc_root / str(pid) / "status").read_text().splitlines():
                if line.startswith("PPid:"):
                    return int(line.split()[1])
        except (OSError, ValueError, IndexError):
            return None
        return None

    def top_rss(self, rows: int = _TOP_RSS_ROWS) -> tuple[dict[str, object], ...]:
        """The heaviest processes on the host, for the record. Never a gate — the global"""
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
        """``VmHWM`` of a running child — the kernel's own high-water mark, so a single late"""
        try:
            for line in (self.proc_root / str(pid) / "status").read_text().splitlines():
                if line.startswith("VmHWM:"):
                    return int(line.split()[1]) * 1024
        except (OSError, ValueError, IndexError):
            return None
        return None

    def child_io(self, pid: int) -> dict[str, int]:
        """``/proc/<pid>/io`` of a running child: ``rchar``/``wchar`` are what the process"""
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
        scanned = self.scan(
            {"build": COMPETING_BUILD_PATTERN, "measure": COMPETING_MEASURE_PATTERN}
        )
        competing = scanned["build"] + scanned["measure"]
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


@dataclass(frozen=True)
class CheckoutState:
    """What git says about the tree this driver and its bench were loaded from."""

    at_kst: str
    repo_path: str
    repo_commit: str
    branch: str
    detached: bool
    clean: bool
    ancestor_of_origin_main: bool
    origin_main_present: bool
    origin_main_commit: str
    dirty_sample: str
    driver_path: str
    bench_path: str
    bench_sha256: str
    bench_in_repo: bool
    error: str = ""

    @property
    def ok(self) -> bool:
        return (
            not self.error
            and self.detached
            and self.clean
            and self.ancestor_of_origin_main
            and self.bench_in_repo
        )

    def failures(self) -> tuple[str, ...]:
        """Every reason this state is not acceptable, each naming what was measured."""
        if self.error:
            return (self.error,)
        reasons: list[str] = []
        if not self.detached:
            reasons.append(
                f"HEAD is attached to branch {self.branch!r} — a parallel lane can move it "
                "under a running measurement (plan §2 A1-c: it did, twice)"
            )
        if not self.clean:
            reasons.append(
                f"the tree is dirty (first line: {self.dirty_sample}) — the bench that runs "
                "would not be the bench any commit names"
            )
        if not self.origin_main_present:
            reasons.append(
                "origin/main is not present in this checkout — run 'git fetch origin' "
                "first; this driver does not fetch"
            )
        elif not self.ancestor_of_origin_main:
            reasons.append(
                f"HEAD ({self.repo_commit[:12]}) is not an ancestor of origin/main "
                f"({self.origin_main_commit[:12]}) — a measurement is evidence, and "
                "evidence is produced by merged code"
            )
        if not self.bench_in_repo:
            reasons.append(
                f"--bench {self.bench_path} resolves OUTSIDE the checkout {self.repo_path} "
                "— the checks above would then vouch for code that never ran"
            )
        return tuple(reasons)

    def summary(self) -> str:
        if self.error:
            return f"unreadable: {self.error}"
        return (
            f"{self.repo_path} at {self.repo_commit[:12]} "
            f"({'detached' if self.detached else f'on branch {self.branch}'}, "
            f"{'clean' if self.clean else 'DIRTY'}, "
            f"{'ancestor of' if self.ancestor_of_origin_main else 'NOT an ancestor of'} "
            f"origin/main)"
        )

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _sha256_of(path: Path) -> str:
    """The file's digest, or ``""`` when it cannot be read."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


class _GitUnavailable(RuntimeError):
    """git could not be asked at all — missing, unrunnable, or it never answered."""


def read_checkout(
    *,
    driver_path: Path,
    bench_path: Path,
    git: Sequence[str] = ("git",),
    timeout_s: float = DEFAULT_GIT_TIMEOUT_S,
) -> CheckoutState:
    """Ask git about the tree ``driver_path`` sits in, and hash ``bench_path``."""
    at_kst = _now_kst()
    bench_digest = _sha256_of(bench_path)
    repo_path = ""
    repo_commit = ""
    branch = ""
    detached = False
    clean = False
    ancestor = False
    origin_present = False
    origin_commit = ""
    dirty_sample = ""
    bench_in_repo = False

    def state(error: str = "") -> CheckoutState:
        return CheckoutState(
            at_kst=at_kst,
            repo_path=repo_path,
            repo_commit=repo_commit,
            branch=branch,
            detached=detached,
            clean=clean,
            ancestor_of_origin_main=ancestor,
            origin_main_present=origin_present,
            origin_main_commit=origin_commit,
            dirty_sample=dirty_sample,
            driver_path=str(driver_path),
            bench_path=str(bench_path),
            bench_sha256=bench_digest,
            bench_in_repo=bench_in_repo,
            error=error,
        )

    start = driver_path.parent if driver_path.is_file() else driver_path

    def run(*args: str, cwd: str = "") -> subprocess.CompletedProcess[str]:
        """One git call, bounded in time and insulated from the operator's config."""
        argv = [*git, *GIT_HARDENING_FLAGS, "-C", cwd or str(start), *args]
        try:
            return subprocess.run(
                argv, capture_output=True, text=True, check=False, timeout=timeout_s
            )
        except subprocess.TimeoutExpired as exc:
            raise _GitUnavailable(
                f"`{' '.join(args)}` did not answer within {timeout_s} s in "
                f"{cwd or start} — something is holding a lock, or the filesystem is not "
                "responding"
            ) from exc
        except OSError as exc:
            raise _GitUnavailable(f"cannot run {git[0]}: {exc}") from exc

    try:
        toplevel = run("rev-parse", "--show-toplevel")
        if toplevel.returncode != 0:
            return state(
                f"{start} is not inside a git checkout: "
                f"{toplevel.stderr.strip() or '(no stderr)'}"
            )
        repo_path = toplevel.stdout.strip()

        head = run("rev-parse", "HEAD", cwd=repo_path)
        if head.returncode != 0:
            return state(
                f"cannot read HEAD in {repo_path}: "
                f"{head.stderr.strip() or '(no stderr)'}"
            )
        repo_commit = head.stdout.strip()

        status = run("status", "--porcelain=v1", "-z", "-uall", cwd=repo_path)
        if status.returncode != 0:
            return state(
                f"cannot read the working tree state in {repo_path}: "
                f"{status.stderr.strip() or '(no stderr)'}"
            )
        entries = [e for e in status.stdout.split("\0") if e.strip()]
        clean = not entries
        dirty_sample = entries[0].strip() if entries else ""

        named = run("rev-parse", "--abbrev-ref", "HEAD", cwd=repo_path)
        if named.returncode != 0:
            return state(
                f"cannot read the branch name in {repo_path}: "
                f"{named.stderr.strip() or '(no stderr)'}"
            )
        branch = named.stdout.strip()
        detached = branch == "HEAD"

        origin = run("rev-parse", "--verify", "--quiet", "origin/main", cwd=repo_path)
        origin_present = origin.returncode == 0
        origin_commit = origin.stdout.strip()
        if origin_present:
            merge_base = run(
                "merge-base", "--is-ancestor", "HEAD", "origin/main", cwd=repo_path
            )
            if merge_base.returncode not in (0, 1):
                return state(
                    f"cannot tell whether HEAD is an ancestor of origin/main in "
                    f"{repo_path}: git merge-base exited {merge_base.returncode}: "
                    f"{merge_base.stderr.strip() or '(no stderr)'}"
                )
            ancestor = merge_base.returncode == 0
    except _GitUnavailable as exc:
        return state(str(exc))

    try:
        bench_in_repo = bench_path.resolve().is_relative_to(Path(repo_path).resolve())
    except OSError:
        bench_in_repo = False
    return state()


@dataclass(frozen=True)
class CheckoutGuard:
    """The preflight check and the per-child re-check, over one :class:`CheckoutState`."""

    driver_path: Path
    bench_path: Path
    enforced: bool = True
    git: tuple[str, ...] = ("git",)
    timeout_s: float = DEFAULT_GIT_TIMEOUT_S
    baseline: CheckoutState | None = None

    def read(self) -> CheckoutState:
        return read_checkout(
            driver_path=self.driver_path,
            bench_path=self.bench_path,
            git=self.git,
            timeout_s=self.timeout_s,
        )

    def with_baseline(self, state: CheckoutState | None = None) -> CheckoutGuard:
        """This guard with its baseline pinned — read now unless one is handed in."""
        return replace(self, baseline=state if state is not None else self.read())

    def drift(self, current: CheckoutState) -> str | None:
        """Why ``current`` is not the tree the baseline described, or ``None``."""
        if not self.enforced or self.baseline is None:
            return None
        if current.error:
            return f"the checkout could not be re-read: {current.error}"
        if current.repo_commit != self.baseline.repo_commit:
            return (
                f"HEAD moved from {self.baseline.repo_commit} to {current.repo_commit} "
                f"in {current.repo_path} while this measurement was running"
            )
        if not current.clean:
            return (
                f"the checkout {current.repo_path} went dirty while this measurement was "
                f"running (first line: {current.dirty_sample})"
            )
        if not current.ok:
            return (
                f"the checkout {current.repo_path} no longer satisfies what the preflight "
                "required: " + "; ".join(current.failures())
            )
        if current.bench_sha256 != self.baseline.bench_sha256:
            return (
                f"the bench {current.bench_path} changed while this measurement was "
                f"running: sha256 {self.baseline.bench_sha256[:12]} -> "
                f"{current.bench_sha256[:12]}"
            )
        return None

    def output_conflicts(self, paths: Mapping[str, Path]) -> tuple[str, ...]:
        """Which of ``paths`` would be written INTO the checkout without being ignored."""
        if self.baseline is None or self.baseline.error or not self.baseline.repo_path:
            return ()
        repo = Path(self.baseline.repo_path).resolve()
        reasons: list[str] = []
        for label, path in paths.items():
            try:
                resolved = path.resolve()
            except OSError as exc:  # pragma: no cover - resolve() is strict=False
                reasons.append(f"{label} {path} cannot be resolved: {exc}")
                continue
            if not resolved.is_relative_to(repo):
                continue
            argv = [
                *self.git,
                *GIT_HARDENING_FLAGS,
                "-C",
                str(repo),
                "check-ignore",
                "-q",
                "--",
                str(resolved),
            ]
            try:
                checked = subprocess.run(
                    argv,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=self.timeout_s,
                )
            except (subprocess.TimeoutExpired, OSError) as exc:
                reasons.append(
                    f"{label} {resolved} is inside the checkout and git check-ignore "
                    f"could not be run: {type(exc).__name__}: {exc}"
                )
                continue
            if checked.returncode == 0:
                continue
            if checked.returncode != 1:
                reasons.append(
                    f"{label} {resolved} is inside the checkout and git check-ignore "
                    f"exited {checked.returncode}: "
                    f"{checked.stderr.strip() or '(no stderr)'}"
                )
                continue
            reasons.append(
                f"{label} {resolved} is inside the checkout {repo} and is NOT gitignored "
                "— the run would dirty the tree it is measuring from (and `git add -A` "
                "would stage it). Put it outside the checkout, or add it to .gitignore"
            )
        return tuple(reasons)

    def record(self, current: CheckoutState) -> dict[str, object]:
        """The provenance block stamped into ``preflight.json``, every step artifact and"""
        data = current.as_dict()
        data["enforced"] = self.enforced
        data["allow_shared_checkout"] = not self.enforced
        data["baseline_commit"] = (
            self.baseline.repo_commit if self.baseline is not None else ""
        )
        data["baseline_bench_sha256"] = (
            self.baseline.bench_sha256 if self.baseline is not None else ""
        )
        data["child_python_flags"] = list(CHILD_PYTHON_FLAGS)
        data["git_timeout_s"] = self.timeout_s
        return data


ALLOW_SHARED_CHECKOUT_WARNING = (
    "--allow-shared-checkout: the detached / clean / ancestor-of-origin-main guard is OFF "
    "for this run, and so is the per-child re-check. Plan §2 A1-c exists because the 365- "
    "and 180-day measurements both ran from a shared checkout and the tree moved under "
    "both of them."
)


@dataclass(frozen=True)
class GuardConfig:
    """The four memory floors plus the watchdog's cadences and kill escalation."""

    min_available_bytes: int
    min_swap_free_bytes: int
    abort_available_bytes: int
    abort_swap_free_bytes: int
    watch_interval_s: float
    poll_interval_s: float
    term_grace_s: float
    host_read_retries: int
    watchdog_enabled: bool = True
    derivations: tuple[str, ...] = ()

    @classmethod
    def validated(
        cls,
        *,
        min_available_gb: float,
        min_swap_free_gb: float,
        abort_available_gb: float | None = None,
        abort_swap_free_gb: float | None = None,
        watch_interval_s: float = DEFAULT_WATCH_INTERVAL_S,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
        term_grace_s: float = DEFAULT_TERM_GRACE_S,
        host_read_retries: int = DEFAULT_HOST_READ_RETRIES,
        watchdog_enabled: bool = True,
    ) -> GuardConfig:
        """Build a config, deriving an unset abort floor from the matching start floor."""
        derivations: list[str] = []
        if abort_available_gb is None:
            abort_available_gb = min(DEFAULT_ABORT_AVAILABLE_GB, min_available_gb)
            if abort_available_gb != DEFAULT_ABORT_AVAILABLE_GB:
                derivations.append(
                    f"abort_available_gb derived as {abort_available_gb} (the default "
                    f"{DEFAULT_ABORT_AVAILABLE_GB} is above the start floor "
                    f"{min_available_gb} you set)"
                )
        elif abort_available_gb > min_available_gb:
            raise MeasureRefused(
                f"--abort-available-gb {abort_available_gb} is above --min-available-gb "
                f"{min_available_gb}: the watchdog would abort a run the preflight had just "
                "let start"
            )
        if abort_swap_free_gb is None:
            abort_swap_free_gb = min(DEFAULT_ABORT_SWAP_FREE_GB, min_swap_free_gb)
            if abort_swap_free_gb != DEFAULT_ABORT_SWAP_FREE_GB:
                derivations.append(
                    f"abort_swap_free_gb derived as {abort_swap_free_gb} (the default "
                    f"{DEFAULT_ABORT_SWAP_FREE_GB} is above the start floor "
                    f"{min_swap_free_gb} you set)"
                )
        elif abort_swap_free_gb > min_swap_free_gb:
            raise MeasureRefused(
                f"--abort-swap-free-gb {abort_swap_free_gb} is above --min-swap-free-gb "
                f"{min_swap_free_gb}: the watchdog would abort a run the preflight had just "
                "let start"
            )
        if watch_interval_s <= 0:
            raise MeasureRefused(
                f"--watch-interval-s must be > 0, got {watch_interval_s}"
            )
        if poll_interval_s <= 0:
            raise MeasureRefused(
                f"--poll-interval-s must be > 0, got {poll_interval_s}"
            )
        if poll_interval_s > watch_interval_s:
            raise MeasureRefused(
                f"--poll-interval-s {poll_interval_s} is above --watch-interval-s "
                f"{watch_interval_s}: the child would be reaped no sooner than the host is "
                "sampled, which is the wall-clock inflation the two cadences exist to avoid"
            )
        if term_grace_s < 0:
            raise MeasureRefused(f"--term-grace-s must be >= 0, got {term_grace_s}")
        if host_read_retries < 0:
            raise MeasureRefused(
                f"--host-read-retries must be >= 0, got {host_read_retries}"
            )
        return cls(
            min_available_bytes=int(min_available_gb * _GB),
            min_swap_free_bytes=int(min_swap_free_gb * _GB),
            abort_available_bytes=int(abort_available_gb * _GB),
            abort_swap_free_bytes=int(abort_swap_free_gb * _GB),
            watch_interval_s=watch_interval_s,
            poll_interval_s=poll_interval_s,
            term_grace_s=term_grace_s,
            host_read_retries=host_read_retries,
            watchdog_enabled=watchdog_enabled,
            derivations=tuple(derivations),
        )

    def in_run_breach(self, sample: HostSample) -> tuple[str, str] | None:
        """``(check, reason)`` for the first in-run floor ``sample`` crosses, else ``None``."""
        if sample.mem_available_bytes < self.abort_available_bytes:
            return (
                "mem_available",
                f"MemAvailable {sample.mem_available_bytes / _GB:.2f} GiB is below "
                f"the in-run floor {self.abort_available_bytes / _GB:.2f} GiB",
            )
        if sample.swap_free_bytes < self.abort_swap_free_bytes:
            return (
                "swap_free",
                f"SwapFree {sample.swap_free_bytes / _GB:.2f} GiB is below the in-run "
                f"floor {self.abort_swap_free_bytes / _GB:.2f} GiB",
            )
        if sample.competing:
            first = sample.competing[0]
            return (
                "competing_build",
                f"a competing process appeared: pid {first.pid} matching "
                f"{first.pattern!r} ({first.args})",
            )
        return None


@dataclass(frozen=True)
class SizeEstimate:
    """What ``build --days N`` is predicted to write, and how the prediction was made."""

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
    reference: Path | None,
    *,
    days: int,
    session_hours: float,
    reference_minutes: float,
    boot_once_max_rows: int,
    bench: ModuleType,
) -> SizeEstimate:
    """Predict the synthetic file's size from the reference distribution. See"""
    if reference is None:
        raise MeasureRefused("no --reference to size the synthetic file from")
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
    reference: Path | None,
    synthetic: Path,
    out_dir: Path,
    days: int,
    repeats: int,
    session_hours: float,
    reference_minutes: float,
    boot_once_max_rows: int,
    batch_rows: int,
) -> tuple[Step, ...]:
    """The child command lines, in the order they must run."""
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
    if "build" in ordered and reference is None:
        raise MeasureRefused("--reference is required to plan a build step")
    for name in ordered:
        argv: tuple[str, ...]
        if name == "build":
            argv = (
                python,
                *CHILD_PYTHON_FLAGS,
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
                *CHILD_PYTHON_FLAGS,
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


def step_artifact_paths(step: Step, *, out_dir: Path, days: int) -> tuple[Path, ...]:
    """Every file one step writes, in one place."""
    return tuple(
        dict.fromkeys(
            (
                step.stdout_path,
                step.stderr_path,
                out_dir / f"{step.name}-{days}d.json",
                out_dir / f"{step.name}-{days}d.time",
                out_dir / f"{step.name}-{days}d.resource.json",
            )
        )
    )


@dataclass(frozen=True)
class EarlierStep:
    """What an already-finished step of this same measurement says about its tree."""

    step: str
    path: str
    repo_commit: str
    bench_sha256: str
    problem: str = ""


def read_earlier_steps(
    out_dir: Path, *, days: int, planned: Sequence[str]
) -> tuple[EarlierStep, ...]:
    """The provenance blocks of the finished steps a resume would be building on."""
    found: list[EarlierStep] = []
    for name in STEP_NAMES:
        if name in planned:
            continue
        path = out_dir / f"{name}-{days}d.resource.json"
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            found.append(
                EarlierStep(
                    step=name,
                    path=str(path),
                    repo_commit="",
                    bench_sha256="",
                    problem=f"unreadable ({type(exc).__name__}: {exc})",
                )
            )
            continue
        block = payload.get("checkout") if isinstance(payload, dict) else None
        if not isinstance(block, dict) or not block.get("repo_commit"):
            found.append(
                EarlierStep(
                    step=name,
                    path=str(path),
                    repo_commit="",
                    bench_sha256="",
                    problem=(
                        "records no checkout provenance — it was produced before A1-c, "
                        "so which tree measured it cannot be established from the "
                        "artifact"
                    ),
                )
            )
            continue
        found.append(
            EarlierStep(
                step=name,
                path=str(path),
                repo_commit=str(block.get("repo_commit", "")),
                bench_sha256=str(block.get("bench_sha256", "")),
            )
        )
    return tuple(found)


def earlier_step_mismatches(
    earlier: Sequence[EarlierStep], *, current: CheckoutState
) -> tuple[str, ...]:
    """Why the finished steps and the tree about to run are not the same measurement."""
    reasons: list[str] = []
    for step in earlier:
        if step.problem:
            reasons.append(f"{step.step} ({step.path}) {step.problem}")
            continue
        if step.repo_commit != current.repo_commit:
            reasons.append(
                f"{step.step} was measured at {step.repo_commit[:12]} but this run would "
                f"use {current.repo_commit[:12]} — the two halves of the pair would not "
                "come from one tree"
            )
        elif step.bench_sha256 and step.bench_sha256 != current.bench_sha256:
            reasons.append(
                f"{step.step} was measured with bench sha256 {step.bench_sha256[:12]} but "
                f"this run would use {current.bench_sha256[:12]}"
            )
    return tuple(reasons)


def abort_record_path(out_dir: Path, *, step: str, days: int, run_id: str) -> Path:
    """Where one stop's ``ABORTED`` artifact goes — one file per (step, run)."""
    return out_dir / f"ABORTED-{step}-{days}d.{run_id}.json"


def move_step_artifacts_aside(
    step: Step, *, out_dir: Path, days: int, run_id: str
) -> list[Path]:
    """Rename a stopped step's files out of the way, keeping every byte."""
    moved: list[Path] = []
    for path in step_artifact_paths(step, out_dir=out_dir, days=days):
        if not path.exists():
            continue
        target = path.with_name(f"{path.stem}.{run_id}.aborted{path.suffix}")
        path.replace(target)
        moved.append(target)
    return moved


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
    checkout: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["argv"] = list(self.argv)
        data["max_rss_mb"] = round(self.max_rss_bytes / (1024.0 * 1024.0), 1)
        return data


@dataclass(frozen=True)
class AbortRecord:
    """What an ``ABORTED-<step>-<days>d.<run_id>.json`` holds — one per run, so a second"""

    run_id: str
    step: str
    days: int
    check: str
    reason: str
    at_kst: str
    elapsed_seconds: float
    signal_sent: str
    escalated_to_sigkill: bool
    returncode: int | None
    partial_resource: dict[str, object]
    last_samples: tuple[dict[str, object], ...]
    checkout: dict[str, object] = field(default_factory=dict)


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


def _returncode(status: int) -> int:
    """A wait status as a shell-style return code: ``-N`` for signal N, else the exit code."""
    if os.WIFSIGNALED(status):
        return -os.WTERMSIG(status)
    return os.WEXITSTATUS(status)


def _terminate(
    pid: int, *, grace_s: float, sleep: Callable[[float], None]
) -> tuple[bool, int, resource.struct_rusage]:
    """``SIGTERM``, then ``SIGKILL`` after ``grace_s``."""
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
    checkout: CheckoutGuard,
    reader: HostReader,
    run_id: str,
    days: int,
    out_dir: Path,
    log: Callable[[str], None],
    sampler: Callable[[int], HostSample] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> StepResult:
    """Run one child under the watchdog."""
    take = sampler or (lambda pid: reader.sample(child_pid=pid))
    watchdog_path = out_dir / "watchdog.jsonl"
    samples: list[dict[str, object]] = []
    last_io: dict[str, int] = {}
    last_io_at: float | None = None
    peak_rss_sampled = 0

    log(f"########## days={days} {step.name}")
    log(f"argv: {' '.join(step.argv)}")

    checkout_record: dict[str, object] = {}

    def write_prespawn_abort(check: str, reason: str) -> None:
        """An ``ABORTED`` artifact for a stop that happened BEFORE any child existed."""
        path = abort_record_path(out_dir, step=step.name, days=days, run_id=run_id)
        try:
            path.write_text(
                json.dumps(
                    asdict(
                        AbortRecord(
                            run_id=run_id,
                            step=step.name,
                            days=days,
                            check=check,
                            reason=reason,
                            at_kst=_now_kst(),
                            elapsed_seconds=0.0,
                            signal_sent="none — the child was never started",
                            escalated_to_sigkill=False,
                            returncode=None,
                            partial_resource={},
                            last_samples=(),
                            checkout=checkout_record,
                        )
                    ),
                    indent=2,
                ),
                encoding="utf-8",
            )
            log(f"wrote {path}")
        except Exception as write_exc:
            log(f"could not write the abort artifact: {write_exc!r}")

    try:
        current_checkout = checkout.read()
        checkout_record = checkout.record(current_checkout)
        drifted = checkout.drift(current_checkout)
    except BaseException as exc:
        reason = f"{type(exc).__name__}: {exc}"
        log(f"ABORT ({step.name}): {reason}")
        write_prespawn_abort(
            (
                "driver_signalled"
                if isinstance(exc, (MeasureSignalled, KeyboardInterrupt))
                else "driver_error"
            ),
            reason,
        )
        raise
    if drifted is not None:
        log(f"ABORT ({step.name}): {drifted}")
        write_prespawn_abort("checkout_drift", drifted)
        raise MeasureAborted(drifted)
    log(
        f"checkout ok: {current_checkout.repo_path} at "
        f"{current_checkout.repo_commit[:12]} · bench sha256 "
        f"{current_checkout.bench_sha256[:12]} · python flags "
        f"{' '.join(CHILD_PYTHON_FLAGS)}"
    )

    started_wall = time.monotonic()
    started_at = _now_kst()
    pid = _spawn(step.argv, step.stdout_path, step.stderr_path)

    def record(row: dict[str, object]) -> None:
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

    def record_sample(sample: HostSample) -> None:
        nonlocal last_io, last_io_at, peak_rss_sampled
        record(sample.as_dict())
        if sample.child_io:
            last_io = dict(sample.child_io)
            last_io_at = time.monotonic()
        if sample.child_peak_rss_bytes:
            peak_rss_sampled = max(peak_rss_sampled, sample.child_peak_rss_bytes)

    def write_abort(
        *,
        check: str,
        reason: str,
        escalated: bool,
        status: int,
        usage: resource.struct_rusage | None,
    ) -> None:
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
            returncode=_returncode(status),
            partial_resource={
                "max_rss_bytes": max(
                    (usage.ru_maxrss * 1024) if usage else 0, peak_rss_sampled
                ),
                "user_seconds": usage.ru_utime if usage else None,
                "system_seconds": usage.ru_stime if usage else None,
                "fs_inputs_blocks": usage.ru_inblock if usage else None,
                "fs_outputs_blocks": usage.ru_oublock if usage else None,
                "proc_io": dict(last_io),
                "proc_io_sample_age_seconds": (
                    round(time.monotonic() - last_io_at, 3)
                    if last_io_at is not None
                    else None
                ),
            },
            last_samples=tuple(samples[-_ABORT_SAMPLE_TAIL:]),
            checkout=checkout_record,
        )
        path = abort_record_path(out_dir, step=step.name, days=days, run_id=run_id)
        path.write_text(json.dumps(asdict(record_out), indent=2), encoding="utf-8")
        log(f"wrote {path}")
        for moved in move_step_artifacts_aside(
            step, out_dir=out_dir, days=days, run_id=run_id
        ):
            log(f"moved aside: {moved.name}")

    def abort(check: str, reason: str) -> None:
        log(f"ABORT ({step.name}): {reason}")
        escalated, status, usage = _terminate(
            pid, grace_s=guard.term_grace_s, sleep=sleep
        )
        write_abort(
            check=check,
            reason=reason,
            escalated=escalated,
            status=status,
            usage=usage,
        )
        raise MeasureAborted(reason)

    consecutive_read_failures = 0
    next_sample_at = started_wall
    try:
        while True:
            done, status, usage = os.wait4(pid, os.WNOHANG)
            if done == pid:
                wall = time.monotonic() - started_wall
                break
            now = time.monotonic()
            if now < next_sample_at:
                sleep(guard.poll_interval_s)
                continue
            next_sample_at = now + guard.watch_interval_s
            try:
                sample = take(pid)
            except MeasureRefused as exc:
                consecutive_read_failures += 1
                record(
                    {
                        "host_read_error": str(exc),
                        "consecutive": consecutive_read_failures,
                        "fatal": guard.watchdog_enabled,
                    }
                )
                log(f"host read failed ({consecutive_read_failures}): {exc}")
                if (
                    guard.watchdog_enabled
                    and consecutive_read_failures > guard.host_read_retries
                ):
                    abort(
                        "host_read",
                        f"the host could not be read {consecutive_read_failures} times in "
                        f"a row, so the guards are blind: {exc}",
                    )
                sleep(guard.poll_interval_s)
                continue
            consecutive_read_failures = 0
            record_sample(sample)
            if not guard.watchdog_enabled:
                continue
            breach = guard.in_run_breach(sample)
            if breach is None:
                continue
            done, status, usage = os.wait4(pid, os.WNOHANG)
            if done == pid:
                wall = time.monotonic() - started_wall
                log(
                    f"{step.name}: {breach[0]} tripped but the child had already exited — "
                    "completing the step instead of aborting it"
                )
                break
            abort(*breach)
    except MeasureAborted:
        raise
    except BaseException as exc:
        failed_usage: resource.struct_rusage | None
        try:
            failed_escalated, failed_status, failed_usage = _terminate(
                pid, grace_s=guard.term_grace_s, sleep=sleep
            )
        except ChildProcessError:
            failed_escalated, failed_status, failed_usage = (False, 0, None)
        try:
            write_abort(
                check=(
                    "driver_signalled"
                    if isinstance(exc, (MeasureSignalled, KeyboardInterrupt))
                    else "driver_error"
                ),
                reason=f"{type(exc).__name__}: {exc}",
                escalated=failed_escalated,
                status=failed_status,
                usage=failed_usage,
            )
        except Exception as write_exc:
            log(f"could not write the abort artifact: {write_exc!r}")
        raise

    signalled = os.WTERMSIG(status) if os.WIFSIGNALED(status) else None
    rusage_peak = usage.ru_maxrss * 1024
    result = StepResult(
        name=step.name,
        argv=step.argv,
        started_at_kst=started_at,
        finished_at_kst=_now_kst(),
        wall_seconds=wall,
        returncode=_returncode(status),
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
        checkout=checkout_record,
    )
    _write_resource_artifacts(result, out_dir=out_dir, days=days)
    log(
        f"{step.name}: rc={result.returncode} wall={result.wall_seconds:.2f}s "
        f"maxrss={result.max_rss_bytes / (1024 * 1024):.1f} MiB "
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
    """``<step>-Nd.time`` (GNU ``time -v`` field names) and ``<step>-Nd.resource.json``."""
    percent_cpu = (
        int(100.0 * (result.user_seconds + result.system_seconds) / result.wall_seconds)
        if result.wall_seconds > 0
        else 0
    )
    lines = [
        "# produced by tools/tos_evidence_scan_measure.py from os.wait4() rusage of this",
        "# child — GNU `time -v` field names, fields wait4 does not supply are omitted.",
        f"# repo_commit: {result.checkout.get('repo_commit', '')} "
        f"({result.checkout.get('repo_path', '')})",
        f"# bench sha256: {result.checkout.get('bench_sha256', '')}",
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


@dataclass(frozen=True)
class PreflightCheck:
    """One gate, its measured value and its floor. A refusal quotes this verbatim."""

    check: str
    ok: bool
    measured: str
    floor: str
    source: str
    detail: str = ""
    measured_bytes: int | None = None
    floor_bytes: int | None = None
    detail_bytes: int | None = None
    evaluated: bool = True


@dataclass(frozen=True)
class PreflightRecord:
    """Everything the preflight looked at, written to ``preflight.json`` whether it passed"""

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
    checkout: dict[str, object] = field(default_factory=dict)
    refusal: str | None = None

    def as_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["argv"] = list(self.argv)
        return data


@dataclass(frozen=True)
class SyntheticDisposition:
    """What to do with the synthetic file at the end of a run, and what to tell the"""

    action: str
    message: str


def _decimal_gb(size_bytes: int) -> str:
    """``size_bytes`` as decimal GB, which is the unit the growth plan is written in."""
    return f"{size_bytes / 1_000_000_000.0:.2f} GB"


def _rm_command(path: Path) -> str:
    """The deletion command, safe to paste."""
    return f"rm {shlex.quote(str(path))}"


def decide_synthetic_disposition(
    path: Path,
    *,
    remaining: Sequence[str],
    size_bytes: int,
    created_by_this_run: bool,
    before_measured: bool,
    after_measured: bool,
    keep_requested: bool = False,
    delete_on_success: bool = False,
) -> SyntheticDisposition:
    """Decide the fate of the synthetic file, and say it out loud in every case."""
    size = _decimal_gb(size_bytes)
    rm = _rm_command(path)
    missing = [
        name
        for name, measured in (("before", before_measured), ("after", after_measured))
        if not measured
    ]
    not_ours = "" if created_by_this_run else " It was not built by this run."

    if remaining:
        if "build" in remaining:
            return SyntheticDisposition(
                "keep-partial",
                f"KEPT synthetic {path} ({size}) — INCOMPLETE: the build step did not "
                "finish, so this file is a partial write, not a measurable one. It is "
                "kept so nothing is deleted behind your back; delete it before rebuilding "
                "(the bench refuses to overwrite an existing --out).",
            )
        built = (
            "the build it already paid for is not thrown away"
            if created_by_this_run
            else "this run did not build it either"
        )
        return SyntheticDisposition(
            "keep-resumable",
            f"KEPT synthetic {path} ({size}) — the run did not finish, so {built}. Once "
            f"the host recovers, resume with --steps {','.join(remaining)}, then delete "
            f"the file by hand: {rm}",
        )

    if keep_requested:
        unmeasured = (
            ""
            if not missing
            else f" ⚠ the pair is not measured yet — --steps {','.join(missing)} is still "
            "to run."
        )
        return SyntheticDisposition(
            "keep-requested",
            f"KEPT synthetic {path} ({size}) — --keep-synthetic.{not_ours}{unmeasured} "
            f"Delete it by hand when you are done with it: {rm}",
        )

    if missing:
        return SyntheticDisposition(
            "keep-unmeasured",
            f"KEPT synthetic {path} ({size}) — every planned step ran, but the pair is "
            f"NOT measured: --steps {','.join(missing)} has no result in this output "
            f"directory.{not_ours} Measure it with --steps {','.join(missing)}, then "
            f"delete the file by hand: {rm}",
        )

    if not created_by_this_run:
        if delete_on_success:
            return SyntheticDisposition(
                "delete",
                f"removed synthetic {path} ({size}) — --delete-synthetic-on-success, "
                "although this run did not build it",
            )
        return SyntheticDisposition(
            "keep-not-ours",
            f"KEPT synthetic {path} — not built by this run; delete it yourself when the "
            f"measurement is recorded: {rm} ({size}). Pass "
            "--delete-synthetic-on-success to have the driver do it.",
        )

    return SyntheticDisposition("delete", f"removed synthetic {path} ({size})")


def write_run_summary(
    out_dir: Path,
    *,
    run_id: str,
    days: int,
    argv: Sequence[str],
    planned: Sequence[str],
    completed: Sequence[str],
    remaining: Sequence[str],
    outcome: str,
    synthetic: Path,
    created_by_this_run: bool,
    exists_after_the_run: bool | None,
    size_bytes: int | None,
    disposition: SyntheticDisposition | None,
    refusal: str | None = None,
) -> Path:
    """``run-<days>d.<run_id>.summary.json`` — how this one run ended, in fields."""
    still_there = exists_after_the_run
    payload: dict[str, object] = {
        "run_id": run_id,
        "at_kst": _now_kst(),
        "tool": "tools/tos_evidence_scan_measure.py",
        "days": days,
        "argv": list(argv),
        "outcome": outcome,
        "refusal": refusal,
        "steps_planned": list(planned),
        "steps_completed": list(completed),
        "steps_remaining": list(remaining),
        "synthetic": {
            "path": str(synthetic),
            "created_by_this_run": created_by_this_run,
            "exists_after_the_run": still_there,
            "size_bytes": size_bytes,
            "action": None if disposition is None else disposition.action,
            "message": None if disposition is None else disposition.message,
            "delete_command": (
                _rm_command(synthetic) if still_there is not False else None
            ),
        },
        "abort_records": sorted(
            path.name for path in out_dir.glob(f"ABORTED-*-{days}d.{run_id}.json")
        ),
        "log": f"measure-{days}d.log",
    }
    path = out_dir / f"run-{days}d.{run_id}.summary.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


LOCK_NAME = ".measure.lock"


def read_lock(
    out_dir: Path, *, proc_root: Path = Path("/proc")
) -> dict[str, object] | None:
    """The live lock in ``out_dir``, or ``None`` when there is none."""
    path = out_dir / LOCK_NAME
    try:
        held = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(held, dict):
        return None
    pid = held.get("pid")
    if not isinstance(pid, int):
        return None
    try:
        cmdline = (
            (proc_root / str(pid) / "cmdline")
            .read_bytes()
            .replace(b"\0", b" ")
            .decode("utf-8", "replace")
        )
    except OSError:
        return None
    if str(held.get("argv0", "")) not in cmdline:
        return None
    return dict(held)


def write_lock(out_dir: Path, *, run_id: str, argv: Sequence[str]) -> Path:
    path = out_dir / LOCK_NAME
    path.write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "argv0": sys.argv[0] if sys.argv and sys.argv[0] else __file__,
                "run_id": run_id,
                "argv": list(argv),
                "at_kst": _now_kst(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def release_lock(out_dir: Path) -> None:
    """Remove this process's own lock. Another process's lock is left alone."""
    path = out_dir / LOCK_NAME
    try:
        held = json.loads(path.read_text())
    except (OSError, ValueError):
        return
    if held.get("pid") == os.getpid():
        path.unlink(missing_ok=True)


def _disk_free(path: Path) -> int:
    """Free bytes on the filesystem that will hold ``path``, walking up to the nearest"""
    probe = path if path.exists() else path.parent
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return shutil.disk_usage(probe).free


def preflight(
    *,
    run_id: str,
    guard: GuardConfig,
    checkout: CheckoutGuard,
    reader: HostReader,
    out_dir: Path,
    days: int,
    estimator: Callable[[], SizeEstimate] | None,
    expect_bytes: int | None,
    disk_headroom_ratio: float,
    index_growth_ratio: float,
    steps: Sequence[Step],
    argv: Sequence[str],
    synthetic: Path,
    warnings: Sequence[str] = (),
) -> PreflightRecord:
    """Check the host, write ``preflight.json``/``preflight.jsonl``, and refuse if anything"""
    out_dir.mkdir(parents=True, exist_ok=True)
    checks: list[PreflightCheck] = []
    build_planned = any(step.name == "build" for step in steps)
    synthetic_present = synthetic.exists()

    checkout_state = (
        checkout.baseline if checkout.baseline is not None else checkout.read()
    )
    checkout_record = checkout.record(checkout_state)
    checks.append(
        PreflightCheck(
            check="checkout_detached_and_clean",
            ok=checkout_state.ok,
            evaluated=checkout.enforced,
            measured=checkout_state.summary(),
            floor=(
                "a clean, detached worktree whose HEAD is an ancestor of origin/main, "
                "holding the --bench that will run"
                if checkout.enforced
                else "SKIPPED by --allow-shared-checkout"
            ),
            source=(
                "plan §2 A1-c (§7.1.16 F6): the 365- and 180-day runs both moved under "
                "themselves. Same discipline as tools/broker_probes/runners/run_p_ca.sh "
                "(#793). This driver never fetches — origin/main is read as it stands"
            ),
            detail=(
                "; ".join(checkout_state.failures())
                if checkout_state.failures()
                else f"bench {checkout_state.bench_path} sha256 "
                f"{checkout_state.bench_sha256[:12]}"
            ),
        )
    )

    earlier = read_earlier_steps(
        out_dir, days=days, planned=[step.name for step in steps]
    )
    earlier_problems = earlier_step_mismatches(earlier, current=checkout_state)
    checks.append(
        PreflightCheck(
            check="matches_earlier_steps",
            ok=not earlier_problems,
            evaluated=checkout.enforced and not checkout_state.error,
            measured=(
                "no finished step of this size is in this output directory"
                if not earlier
                else "; ".join(
                    f"{e.step} at {e.repo_commit[:12] or '(no provenance)'}"
                    for e in earlier
                )
            ),
            floor=(
                "every step of one size comes from one tree and one bench"
                if checkout.enforced and not checkout_state.error
                else "SKIPPED: "
                + (
                    "--allow-shared-checkout"
                    if not checkout.enforced
                    else "the checkout could not be read, so there is nothing to compare"
                )
            ),
            source=(
                "plan §2 A1-c, extended by review F1: the per-child re-check holds ONE "
                "run together and says nothing about the documented resume, which is a "
                "second process hours or weeks later"
            ),
            detail="; ".join(earlier_problems),
        )
    )

    output_problems = checkout.output_conflicts(
        {"--out-dir": out_dir, "--synthetic": synthetic}
    )
    checks.append(
        PreflightCheck(
            check="outputs_outside_the_checkout",
            ok=not output_problems,
            evaluated=not checkout_state.error and bool(checkout_state.repo_path),
            measured=(
                "out-dir and synthetic are outside the checkout, or gitignored"
                if not output_problems
                else "; ".join(output_problems)
            ),
            floor=(
                "nothing this run writes may dirty the checkout it measures from"
                if not checkout_state.error and checkout_state.repo_path
                else "SKIPPED: the checkout could not be located"
            ),
            source=(
                "review F5; unconditional like run_p_ca.sh's refusal to place a file "
                "where `git add -A` would stage it — the shared-checkout hatch is about "
                "where the CODE comes from, not a licence to write 53 GB into the repo"
            ),
            detail="",
        )
    )

    try:
        info: dict[str, int] | None = reader.meminfo()
        memory_error = ""
    except MeasureRefused as exc:
        info, memory_error = None, str(exc)

    if info is None:
        for label in ("mem_available", "swap_free"):
            checks.append(
                PreflightCheck(
                    check=label,
                    ok=False,
                    measured=f"unreadable: {memory_error}",
                    floor="the memory floors must be readable to be checked",
                    source="fail-closed: a preflight that cannot read memory has not checked it",
                )
            )
    else:
        checks.append(
            PreflightCheck(
                check="mem_available",
                ok=info["MemAvailable"] >= guard.min_available_bytes,
                measured=f"{info['MemAvailable'] / _GB:.2f} GiB",
                floor=f"{guard.min_available_bytes / _GB:.2f} GiB",
                measured_bytes=info["MemAvailable"],
                floor_bytes=guard.min_available_bytes,
                source="operator rule ~/.claude/CLAUDE.md 로컬 빌드 동시 실행 제한 (2026-09-25)",
            )
        )
        checks.append(
            PreflightCheck(
                check="swap_free",
                ok=info["SwapFree"] >= guard.min_swap_free_bytes,
                measured=f"{info['SwapFree'] / _GB:.2f} GiB",
                floor=f"{guard.min_swap_free_bytes / _GB:.2f} GiB",
                measured_bytes=info["SwapFree"],
                floor_bytes=guard.min_swap_free_bytes,
                source="same operator rule — the clause plan §7.1.7 deviation 11-b records as missing",
                detail=f"SwapTotal {info['SwapTotal'] / _GB:.2f} GiB",
                detail_bytes=info["SwapTotal"],
            )
        )

    labels = {
        "competing_build": COMPETING_BUILD_PATTERN,
        "competing_measurement": COMPETING_MEASURE_PATTERN,
    }
    try:
        scanned = reader.scan(labels)
        scan_error = ""
    except MeasureRefused as exc:
        scanned, scan_error = {}, str(exc)
    for label, pattern in labels.items():
        if scan_error:
            checks.append(
                PreflightCheck(
                    check=label,
                    ok=False,
                    measured=f"unreadable: {scan_error}",
                    floor="none running",
                    source="fail-closed: a check that could not run has not run",
                )
            )
            continue
        found = scanned[label]
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
                detail=f"pattern: {pattern}",
            )
        )

    if not build_planned and not synthetic_present:
        checks.append(
            PreflightCheck(
                check="synthetic_present",
                ok=False,
                measured=f"{synthetic} does not exist",
                floor="the file the measure steps read must already exist",
                source="this driver: --steps excludes build, so nothing would create it",
            )
        )
    if build_planned and synthetic_present:
        checks.append(
            PreflightCheck(
                check="synthetic_absent",
                ok=False,
                measured=f"{synthetic} already exists ({synthetic.stat().st_size} bytes)",
                floor="build writes a new file; the bench refuses to overwrite one",
                source=(
                    "this driver, mirroring tos_evidence_scan_bench.build_synthetic's own "
                    "refusal: failing here costs nothing, failing at step 1 leaves "
                    "artifacts that block the retry"
                ),
                detail="delete it, or drop build from --steps to measure the existing file",
            )
        )

    estimate: SizeEstimate | None = None
    estimate_error = ""
    already_refused = any(c.evaluated and not c.ok for c in checks)
    if build_planned and estimator is not None and not already_refused:
        try:
            estimate = estimator()
        except MeasureRefused as exc:
            estimate_error = str(exc)

    if estimate_error:
        checks.append(
            PreflightCheck(
                check="disk_free",
                ok=False,
                measured=f"cannot size the run: {estimate_error}",
                floor="the synthetic size must be predictable to check the disk",
                source="fail-closed",
            )
        )
    elif build_planned and estimate is None:
        checks.append(
            PreflightCheck(
                check="disk_free",
                ok=False,
                evaluated=False,
                measured="not evaluated",
                floor=f"{'; '.join(c.check for c in checks if c.evaluated and not c.ok)} already refused this run",
                source=(
                    "skipped deliberately: sizing the run means scanning the reference, "
                    "and the run is not going to start"
                ),
            )
        )
    else:
        if expect_bytes is not None:
            base_bytes = expect_bytes
            basis = (
                f"--expect-gb (operator-supplied) x --disk-headroom-ratio "
                f"{disk_headroom_ratio}"
            )
        elif build_planned:
            base_bytes = estimate.predicted_file_bytes if estimate else 0
            basis = f"predicted synthetic size x --disk-headroom-ratio {disk_headroom_ratio}"
        else:
            on_disk = synthetic.stat().st_size if synthetic_present else 0
            base_bytes = int(on_disk * index_growth_ratio)
            basis = (
                f"existing synthetic x --index-growth-ratio {index_growth_ratio} "
                f"x --disk-headroom-ratio {disk_headroom_ratio} (build not planned)"
            )
        required_bytes = int(base_bytes * disk_headroom_ratio)
        worst_free = min(_disk_free(out_dir), _disk_free(synthetic.parent))
        checks.append(
            PreflightCheck(
                check="disk_free",
                ok=worst_free >= required_bytes,
                measured=f"{worst_free / _GB:.2f} GiB free",
                floor=f"{required_bytes / _GB:.2f} GiB needed",
                measured_bytes=worst_free,
                floor_bytes=required_bytes,
                source=basis,
                detail=(
                    ""
                    if estimate is None
                    else (
                        f"predicted {estimate.predicted_file_bytes / _GB:.2f} GiB "
                        f"({estimate.predicted_rows} rows) from {estimate.reference}"
                    )
                ),
                detail_bytes=(
                    None if estimate is None else estimate.predicted_file_bytes
                ),
            )
        )

    existing = [
        str(p)
        for step in steps
        for p in step_artifact_paths(step, out_dir=out_dir, days=days)
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
            detail=(
                ""
                if not existing
                else "remove or rename these before rerunning: "
                + " ".join(sorted(set(existing)))
            ),
        )
    )

    held = read_lock(out_dir, proc_root=reader.proc_root)
    checks.append(
        PreflightCheck(
            check="output_dir_unlocked",
            ok=held is None,
            measured=(
                "no live lock"
                if held is None
                else f"pid {held.get('pid')} holds it (run {held.get('run_id')}, "
                f"since {held.get('at_kst')})"
            ),
            floor="no other run may hold this output directory",
            source=(
                "this driver: two runs sharing an --out-dir would interleave "
                "watchdog.jsonl and race on the step artifacts. A lock whose owner is gone "
                "is treated as absent, so a SIGKILLed run does not block the next one"
            ),
        )
    )

    top_rss = reader.top_rss()
    failed = [c for c in checks if c.evaluated and not c.ok]
    refusal = (
        None
        if not failed
        else " | ".join(
            f"{c.check}: measured {c.measured}, need {c.floor}"
            + (f" [{c.detail}]" if c.detail else "")
            for c in failed
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
            "poll_interval_s": guard.poll_interval_s,
            "term_grace_s": guard.term_grace_s,
            "host_read_retries": guard.host_read_retries,
            "disk_headroom_ratio": disk_headroom_ratio,
            "index_growth_ratio": index_growth_ratio,
        },
        estimate=asdict(estimate) if estimate else None,
        top_rss=top_rss,
        watchdog_enabled=guard.watchdog_enabled,
        warnings=tuple(warnings),
        steps_planned=tuple(s.name for s in steps),
        checkout=checkout_record,
        refusal=refusal,
    )
    payload = record.as_dict()
    (out_dir / "preflight.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    with (out_dir / "preflight.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")
    return record


def _add_guard_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--min-available-gb",
        type=float,
        default=DEFAULT_MIN_AVAILABLE_GB,
        help=(
            "Start floor on MemAvailable, in GiB (1024**3; /proc/meminfo reports KiB, "
            "the same binary base). Default from the operator's global build rule."
        ),
    )
    parser.add_argument(
        "--min-swap-free-gb",
        type=float,
        default=DEFAULT_MIN_SWAP_FREE_GB,
        help=(
            "Start floor on SwapFree, in GiB (same rule, same base). 0 opts out "
            "explicitly, e.g. a swapless host — the in-run floor then follows it down on "
            f"its own (default {DEFAULT_ABORT_SWAP_FREE_GB} GiB, capped at whatever you "
            "set here), so no second flag is needed."
        ),
    )
    parser.add_argument(
        "--abort-available-gb",
        type=float,
        default=None,
        help=(
            "In-run abort floor on MemAvailable, in GiB. Unset, it is "
            f"min({DEFAULT_ABORT_AVAILABLE_GB}, --min-available-gb) — the 2026-09-30 run's "
            "value (plan §7.1.2), never above the start floor."
        ),
    )
    parser.add_argument(
        "--abort-swap-free-gb",
        type=float,
        default=None,
        help=(
            "In-run abort floor on SwapFree, in GiB. Unset, it is "
            f"min({DEFAULT_ABORT_SWAP_FREE_GB}, --min-swap-free-gb). No external rule sets "
            "an in-run swap floor; this default is this driver's own."
        ),
    )
    parser.add_argument(
        "--watch-interval-s", type=float, default=DEFAULT_WATCH_INTERVAL_S
    )
    parser.add_argument(
        "--poll-interval-s",
        type=float,
        default=DEFAULT_POLL_INTERVAL_S,
        help=(
            "How often the child is reaped. Separate from --watch-interval-s so a step's "
            "wall clock is not rounded up to the next host sample."
        ),
    )
    parser.add_argument(
        "--host-read-retries",
        type=int,
        default=DEFAULT_HOST_READ_RETRIES,
        help=(
            "Consecutive host-read failures tolerated before the watchdog calls itself "
            "blind and stops the run."
        ),
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
        "--git-timeout-s",
        type=float,
        default=DEFAULT_GIT_TIMEOUT_S,
        help=(
            "Seconds any single git call in the checkout guard gets before it counts as "
            f"unanswerable (default {DEFAULT_GIT_TIMEOUT_S}, the value "
            "tools/tos_completion_status.py already uses). A timeout is a refusal, never "
            "a pass."
        ),
    )
    parser.add_argument(
        "--allow-shared-checkout",
        action="store_true",
        help=(
            "Run from a checkout that is NOT a clean detached worktree at an "
            "origin/main ancestor, and skip the per-child re-check. Everything is still "
            "measured and recorded. Plan §2 A1-c is what this flag turns off."
        ),
    )
    parser.add_argument(
        "--disk-headroom-ratio", type=float, default=DEFAULT_DISK_HEADROOM_RATIO
    )
    parser.add_argument(
        "--index-growth-ratio",
        type=float,
        default=DEFAULT_INDEX_GROWTH_RATIO,
        help=(
            "How much entries_kind_seq grows the file (plan §7.1.2 measured +1.8 %%). Sizes "
            "the disk check for a resume, where only the index is new."
        ),
    )
    parser.add_argument(
        "--expect-gb",
        type=float,
        default=None,
        help=(
            "Override the derived disk estimate with an explicit figure, in GiB "
            "(1024**3 — the same base the disk check prints in)."
        ),
    )


def _add_shared_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--reference",
        type=Path,
        default=None,
        help=(
            "The real evidence.sqlite3 whose distribution `build` replicates. Required "
            "only when --steps includes build; a measure-only resume never reads it."
        ),
    )
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
            "stays one file (plan §7.1.2), but only when this run built it AND both "
            "halves of the pair have a recorded result; otherwise it is kept and the run "
            "says why. Incompatible with --delete-synthetic-on-success."
        ),
    )
    run_parser.add_argument(
        "--delete-synthetic-on-success",
        action="store_true",
        help=(
            "On a RESUME, delete the synthetic file this run did not build, once every "
            "planned step has run. Default is to keep it and print the rm command: the "
            "file may be the operator's only copy, and the 180- and 270-day index-time "
            "file sizes are readable only because it survived (plan §7.1.15 · §7.1.23). "
            "Refused up front when --steps includes build, when --keep-synthetic is also "
            "passed, or when either half of the pair would be left unmeasured — that is, "
            "unless `before` and `after` are each in --steps or already have a "
            "<step>-<days>d.resource.json in --out-dir naming this same --synthetic."
        ),
    )

    pre_parser = sub.add_parser(
        "preflight", help="Run only the preflight and report — starts no child."
    )
    _add_shared_arguments(pre_parser)
    _add_guard_arguments(pre_parser)

    return parser


_STOP_SIGNALS = (signal.SIGTERM, signal.SIGHUP)


def _install_signal_handlers() -> dict[int, object]:
    """Route ``SIGTERM``/``SIGHUP`` into the same path a crash takes, and return the"""

    def handler(signum: int, _frame: object) -> None:
        raise MeasureSignalled(
            f"received {signal.Signals(signum).name} — terminating the child and "
            "recording the stop"
        )

    previous: dict[int, object] = {}
    for signum in _STOP_SIGNALS:
        try:
            previous[signum] = signal.signal(signum, handler)
        except (ValueError, OSError):
            continue
    return previous


def _restore_signal_handlers(previous: dict[int, object]) -> None:
    for signum, handler in previous.items():
        try:
            signal.signal(signum, handler)  # type: ignore[arg-type]
        except (ValueError, OSError):
            continue


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


def _exists_or_unknown(path: Path) -> bool | None:
    """``True`` / ``False`` / ``None`` for "it is there" / "it is not" / "cannot tell"."""
    try:
        return path.exists()
    except OSError:
        return None


def _same_path(left: Path, right: Path) -> bool:
    """Whether two paths name the same file, symlinks and ``..`` resolved."""
    try:
        return left.resolve() == right.resolve()
    except OSError:  # pragma: no cover - resolve() on an unreadable parent
        return str(left) == str(right)


def recorded_pass(out_dir: Path, *, step: str, days: int) -> Path | None:
    """The finished ``<step>-<days>d.resource.json`` in ``out_dir``, or ``None``."""
    path = out_dir / f"{step}-{days}d.resource.json"
    return path if path.exists() else None


def _measures_this_file(resource_path: Path, synthetic: Path) -> bool:
    """Whether that recorded pass was measured against THIS synthetic file."""
    try:
        payload = json.loads(resource_path.read_text())
    except (OSError, ValueError):
        return False
    argv = payload.get("argv") if isinstance(payload, dict) else None
    if not isinstance(argv, list) or "--db" not in argv:
        return False
    try:
        measured = Path(str(argv[argv.index("--db") + 1])).resolve()
    except (IndexError, OSError, ValueError):
        return False
    try:
        return measured == synthetic.resolve()
    except OSError:  # pragma: no cover - resolve() on a vanished parent
        return False


def _hold_stop_signals() -> frozenset[int] | None:
    """Block ``SIGTERM``/``SIGHUP`` for the duration of the end-of-run bookkeeping."""
    try:
        return frozenset(signal.pthread_sigmask(signal.SIG_BLOCK, _STOP_SIGNALS))
    except (AttributeError, ValueError, OSError):
        return None


def _release_stop_signals(previous: frozenset[int] | None) -> None:
    """Put back the mask :func:`_hold_stop_signals` replaced, delivering anything pending."""
    if previous is None:
        return
    try:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)
    except (ValueError, OSError):  # pragma: no cover - same tolerance as the block
        pass


def _run_outcome(failure: BaseException | None) -> str:
    """How a run ended, as one word for ``run-<days>d.<run_id>.summary.json``."""
    if failure is None:
        return "ok"
    for kind, name in (
        (MeasureAborted, "aborted"),
        (MeasureStepFailed, "step-failed"),
        (MeasureSignalled, "signalled"),
        (MeasureRefused, "refused"),
    ):
        if isinstance(failure, kind):
            return name
    return f"error ({type(failure).__name__})"


def main(argv: list[str] | None = None, *, reader: HostReader | None = None) -> int:
    """Entry point."""
    raw = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(raw)
    out_dir: Path = args.out_dir
    run_id = uuid.uuid4().hex[:12]
    log_lines: list[str] = []

    def log(message: str) -> None:
        log_lines.append(message)
        print(message, flush=True)

    summary_written = False
    out_dir_ready = False
    planned_names: list[str] = []

    def emit_summary(
        *,
        outcome: str,
        planned: Sequence[str],
        completed: Sequence[str],
        remaining: Sequence[str],
        created_by_this_run: bool,
        exists_after_the_run: bool | None,
        size_bytes: int | None,
        disposition: SyntheticDisposition | None,
        refusal: str | None,
    ) -> Path | None:
        """Write this run's summary once, and never let that write mask a real failure."""
        nonlocal summary_written
        if summary_written or not out_dir_ready:
            return None
        try:
            path = write_run_summary(
                out_dir,
                run_id=run_id,
                days=args.days,
                argv=raw,
                planned=planned,
                completed=completed,
                remaining=remaining,
                outcome=outcome,
                synthetic=args.synthetic,
                created_by_this_run=created_by_this_run,
                exists_after_the_run=exists_after_the_run,
                size_bytes=size_bytes,
                disposition=disposition,
                refusal=refusal,
            )
        except Exception as summary_exc:
            log(f"could not write the run summary: {summary_exc!r}")
            return None
        summary_written = True
        return path

    previous_handlers = _install_signal_handlers()
    held_signals: frozenset[int] | None = None
    try:
        guard = GuardConfig.validated(
            min_available_gb=args.min_available_gb,
            min_swap_free_gb=args.min_swap_free_gb,
            abort_available_gb=args.abort_available_gb,
            abort_swap_free_gb=args.abort_swap_free_gb,
            watch_interval_s=args.watch_interval_s,
            poll_interval_s=args.poll_interval_s,
            term_grace_s=args.term_grace_s,
            host_read_retries=args.host_read_retries,
            watchdog_enabled=not args.no_watchdog,
        )
        if args.git_timeout_s <= 0:
            raise MeasureRefused(
                f"--git-timeout-s must be > 0, got {args.git_timeout_s}: a guard with no "
                "time to run is a guard that does not run"
            )
        checkout = CheckoutGuard(
            driver_path=Path(__file__).resolve(),
            bench_path=args.bench.resolve(),
            enforced=not args.allow_shared_checkout,
            timeout_s=args.git_timeout_s,
        ).with_baseline()

        warnings: list[str] = list(guard.derivations)
        if args.allow_shared_checkout:
            warnings.append(ALLOW_SHARED_CHECKOUT_WARNING)
            print(f"WARNING: {warnings[-1]}", file=sys.stderr)
        if not guard.watchdog_enabled:
            warnings.append(
                "--no-watchdog: the in-run memory/swap/co-tenant guard is OFF for this run. "
                "The 2026-09-30 00:24 KST earlyoom incident (plan §7.1.5) happened without it."
            )
            print(f"WARNING: {warnings[-1]}", file=sys.stderr)

        step_names = [s.strip() for s in args.steps.split(",") if s.strip()]
        if "build" in step_names and args.reference is None:
            raise MeasureRefused(
                "--reference is required when --steps includes build (it is the "
                "distribution the synthetic file replicates)"
            )
        if args.reference is not None and _same_path(args.synthetic, args.reference):
            raise MeasureRefused(
                f"--synthetic and --reference are the same file ({args.synthetic}): the "
                "synthetic file is a disposable replica of the reference, and this run "
                "may build onto it or delete it"
            )
        if args.command == "run" and args.delete_synthetic_on_success:
            if args.keep_synthetic:
                raise MeasureRefused(
                    "--keep-synthetic and --delete-synthetic-on-success ask for opposite "
                    "things; pass one"
                )
            if "build" in step_names:
                raise MeasureRefused(
                    "--delete-synthetic-on-success is for a RESUME and --steps includes "
                    f"build (got --steps {args.steps}): a run that builds the file "
                    "already deletes it when the pair is measured, so the flag only "
                    "reads as asking for something it is not doing"
                )
            unmeasured = [
                name
                for name in ("before", "after")
                if name not in step_names
                and not (
                    (recorded := recorded_pass(out_dir, step=name, days=args.days))
                    and _measures_this_file(recorded, args.synthetic)
                )
            ]
            if unmeasured:
                raise MeasureRefused(
                    "--delete-synthetic-on-success would delete an UNMEASURED pair: "
                    f"{' and '.join(unmeasured)} is neither in --steps {args.steps} nor "
                    f"already recorded for this file in {out_dir} "
                    f"({', '.join(f'{n}-{args.days}d.resource.json' for n in unmeasured)}"
                    " is absent, unreadable, or names a different --db). Deleting then "
                    "throws away the half the measurement still needs"
                )
        out_dir.mkdir(parents=True, exist_ok=True)
        out_dir_ready = True

        def estimator() -> SizeEstimate:
            """Deferred so the reference is scanned only when `build` is planned AND the"""
            return estimate_synthetic_size(
                args.reference,
                days=args.days,
                session_hours=args.session_hours,
                reference_minutes=args.reference_minutes,
                boot_once_max_rows=args.boot_once_max_rows,
                bench=_load_bench_module(args.bench),
            )

        steps = plan_steps(
            names=step_names,
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
        planned_names = [step.name for step in steps]
        reader = reader or HostReader()
        record = preflight(
            run_id=run_id,
            guard=guard,
            checkout=checkout,
            reader=reader,
            out_dir=out_dir,
            days=args.days,
            estimator=estimator,
            expect_bytes=None if args.expect_gb is None else int(args.expect_gb * _GB),
            disk_headroom_ratio=args.disk_headroom_ratio,
            index_growth_ratio=args.index_growth_ratio,
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
        failure: BaseException | None = None

        def _pass_is_recorded(step: str) -> bool:
            """Whether ``step`` has a result for THIS synthetic file in this directory."""
            if step in completed:
                return True
            recorded = recorded_pass(out_dir, step=step, days=args.days)
            return recorded is not None and _measures_this_file(
                recorded, args.synthetic
            )

        try:
            write_lock(out_dir, run_id=run_id, argv=raw)
            for step in steps:
                result = run_step(
                    step,
                    guard=guard,
                    checkout=checkout,
                    reader=reader,
                    run_id=run_id,
                    days=args.days,
                    out_dir=out_dir,
                    log=log,
                )
                if result.returncode != 0:
                    moved = move_step_artifacts_aside(
                        step, out_dir=out_dir, days=args.days, run_id=run_id
                    )
                    for path in moved:
                        log(f"moved aside: {path.name}")
                    stderr_note = next(
                        (str(m) for m in moved if m.name.endswith(".err")),
                        str(step.stderr_path),
                    )
                    raise MeasureStepFailed(
                        f"step {step.name!r} exited {result.returncode}; see {stderr_note}"
                    )
                completed.append(step.name)
        except BaseException as exc:
            failure = exc
            raise
        finally:
            held_signals = _hold_stop_signals()
            disposition = None
            remaining = [s.name for s in steps if s.name not in completed]
            synthetic_present = _exists_or_unknown(args.synthetic)
            synthetic_bytes: int | None = None
            if synthetic_present:
                try:
                    synthetic_bytes = args.synthetic.stat().st_size
                except OSError as stat_exc:
                    synthetic_present = None
                    log(f"could not stat the synthetic file: {stat_exc!r}")
            elif synthetic_present is None:
                log(f"could not tell whether {args.synthetic} is still there")
            if synthetic_bytes is not None:
                disposition = decide_synthetic_disposition(
                    args.synthetic,
                    remaining=remaining,
                    size_bytes=synthetic_bytes,
                    created_by_this_run=created_synthetic,
                    before_measured=_pass_is_recorded("before"),
                    after_measured=_pass_is_recorded("after"),
                    keep_requested=args.keep_synthetic,
                    delete_on_success=args.delete_synthetic_on_success,
                )
                if disposition.action == "delete":
                    try:
                        args.synthetic.unlink(missing_ok=True)
                        synthetic_present = False
                    except OSError as unlink_exc:
                        disposition = SyntheticDisposition(
                            "delete-failed",
                            f"COULD NOT remove synthetic {args.synthetic} "
                            f"({_decimal_gb(synthetic_bytes)}): {unlink_exc!r}. It is "
                            f"still on the host — delete it by hand: "
                            f"{_rm_command(args.synthetic)}",
                        )
                log(disposition.message)
            summary_path = emit_summary(
                outcome=_run_outcome(failure),
                planned=planned_names,
                completed=completed,
                remaining=remaining,
                created_by_this_run=created_synthetic,
                exists_after_the_run=synthetic_present,
                size_bytes=synthetic_bytes,
                disposition=disposition,
                refusal=(str(failure) if isinstance(failure, MeasureRefused) else None),
            )
            log(
                f"##### summary (run {run_id}): {_run_outcome(failure)} · "
                f"completed {','.join(completed) or 'none'} · "
                f"remaining {','.join(remaining) or 'none'}"
            )
            if disposition is not None:
                log(f"##### synthetic: {disposition.message}")
            if summary_path is not None:
                log(f"wrote {summary_path}")
            with (out_dir / f"measure-{args.days}d.log").open(
                "a", encoding="utf-8"
            ) as handle:
                handle.write(
                    f"##### run {run_id} · {_now_kst()} · argv: {' '.join(raw)}\n"
                )
                handle.write("\n".join(log_lines) + "\n")
            release_lock(out_dir)
        return 0
    except (
        MeasureRefused,
        MeasureAborted,
        MeasureStepFailed,
        MeasureSignalled,
    ) as exc:
        emit_summary(
            outcome=_run_outcome(exc),
            planned=planned_names,
            completed=[],
            remaining=list(planned_names),
            created_by_this_run=False,
            exists_after_the_run=_exists_or_unknown(args.synthetic),
            size_bytes=None,
            disposition=None,
            refusal=str(exc),
        )
        print(f"tos_evidence_scan_measure: {exc}", file=sys.stderr)
        return 1
    finally:
        _restore_signal_handlers(previous_handlers)
        _release_stop_signals(held_signals)


if __name__ == "__main__":
    raise SystemExit(main())
