"""The KIS mock app key's cross-process request window, as tos_runtime's ``SharedAppKeyGate`` keeps it."""

# SAFETY: 이 파일은 tos_runtime/transport/kis_mock/{shared_pacer,file_lock}.py 의 재진술이다 — 방화벽이 import 를 막으므로(tos/CLAUDE.md), 저쪽이 바뀌면 여기도 같이 바꾸지 않으면 두 구현이 같은 app key 한도를 따로 센다

from __future__ import annotations

import fcntl
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TRANSPORT_YAML_ENV = "CP3_KIS_MOCK_TRANSPORT_YAML"

DEFAULT_WINDOW_MARGIN_S = 0.25

# SAFETY: 한 번의 허가 계산은 1.25s 를 넘지 않는다 — 이 상한은 다른 프로세스가 잠금을 쥐고 있는 시간을 위한 것이고, 모자라면 조용히 건너뛰는 대신 거절한다 (#1161)
LOCK_WAIT_S = 30.0

WINDOW_S = 1.0
PRIVATE_FILE_MODE = 0o600
_DIR_MODE = 0o700
_LOCK_POLL_S = 0.02


class SharedPaceUnavailable(RuntimeError):
    """This app key's shared window could not be read or entered. Nothing was sent."""


@dataclass(frozen=True)
class SharedPaceTerms:
    """What ``kis_mock_transport.yaml`` says about this app key's shared rate."""

    path: Path
    max_rps: float
    window_margin_s: float


def resolve_transport_yaml(flag: str | None) -> Path | None:
    """The tenant ``kis_mock_transport.yaml`` this run paces against, or ``None``."""
    raw = (flag if flag is not None else os.environ.get(TRANSPORT_YAML_ENV, "")).strip()
    return Path(raw).expanduser() if raw else None


def load_shared_pace_terms(transport_yaml: Path) -> SharedPaceTerms:
    """Read ``shared_pacer_path`` / ``shared_max_rps`` / ``shared_window_margin_s``."""
    import yaml

    try:
        raw = yaml.safe_load(transport_yaml.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise SharedPaceUnavailable(
            f"{transport_yaml}: cannot be read ({exc})"
        ) from exc
    if not isinstance(raw, dict):
        raise SharedPaceUnavailable(f"{transport_yaml}: not a YAML mapping")
    path_value = raw.get("shared_pacer_path")
    rate_value = raw.get("shared_max_rps")
    if not isinstance(path_value, str) or not path_value:
        raise SharedPaceUnavailable(
            f"{transport_yaml}: shared_pacer_path is missing — this tenant does not "
            "declare a shared pace file, so this tool cannot share the app key's rate"
        )
    if not Path(path_value).is_absolute():
        raise SharedPaceUnavailable(
            f"{transport_yaml}: shared_pacer_path {path_value!r} is relative — the "
            "tenant processes and this tool must name the same file"
        )
    if not isinstance(rate_value, (int, float)) or isinstance(rate_value, bool):
        raise SharedPaceUnavailable(
            f"{transport_yaml}: shared_max_rps must be a number"
        )
    if rate_value <= 0:
        raise SharedPaceUnavailable(
            f"{transport_yaml}: shared_max_rps must be positive"
        )
    margin_value = raw.get("shared_window_margin_s", DEFAULT_WINDOW_MARGIN_S)
    if not isinstance(margin_value, (int, float)) or isinstance(margin_value, bool):
        raise SharedPaceUnavailable(
            f"{transport_yaml}: shared_window_margin_s must be a number"
        )
    if margin_value < 0:
        raise SharedPaceUnavailable(
            f"{transport_yaml}: shared_window_margin_s must be zero or positive"
        )
    return SharedPaceTerms(
        path=Path(path_value),
        max_rps=float(rate_value),
        window_margin_s=float(margin_value),
    )


class SharedAppKeyPace:
    """This app key's cross-process request gate (module docstring)."""

    def __init__(
        self,
        terms: SharedPaceTerms,
        *,
        now_epoch_s: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._path = terms.path
        self._lock_path = terms.path.with_name(terms.path.name + ".lock")
        self._min_interval_s = 1.0 / terms.max_rps
        self._window_grants = max(1, int(terms.max_rps))
        self._window_margin_s = terms.window_margin_s
        self._now = now_epoch_s or time.time
        self._sleep = sleep or time.sleep

    @property
    def path(self) -> Path:
        """The file holding this app key's last grant instants."""
        return self._path

    def acquire(self, *, wait_budget_s: float = LOCK_WAIT_S) -> None:
        """Wait for this app key's next cross-process slot, then return so the caller sends."""
        # SAFETY: 잠금은 `<pace>.lock` 의 flock(LOCK_EX) 여야 한다 — tos_runtime file_lock.py 가 쥐는 바로 그 파일이고, 다른 자리를 쥐면 두 구현이 서로를 기다리지 않는다
        _ensure_private_dir(self._lock_path.parent)
        fd = os.open(
            self._lock_path, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC, PRIVATE_FILE_MODE
        )
        try:
            self._flock_within_budget(fd, wait_budget_s)
            try:
                self._grant_within_budget(wait_budget_s)
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def _flock_within_budget(self, fd: int, wait_s: float) -> None:
        deadline = time.monotonic() + wait_s
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise SharedPaceUnavailable(
                        f"another process held {self._lock_path} for the whole "
                        f"{wait_s:.1f}s wait budget — nothing was sent"
                    ) from exc
                time.sleep(_LOCK_POLL_S)

    def _grant_within_budget(self, wait_budget_s: float) -> None:
        grants = self._read_grants()
        wait_s = self._wait_for_slot(grants, self._now())
        if wait_s > wait_budget_s:
            raise SharedPaceUnavailable(
                f"this app key's next shared slot is {wait_s:.3f}s away, past the "
                f"{wait_budget_s:.3f}s wait budget — nothing was sent"
            )
        if wait_s > 0:
            self._sleep(wait_s)
        kept = (*grants, self._now())[-self._window_grants :]
        # SAFETY: 줄마다 "%.6f" epoch 초 · 오래된 것 먼저 · 최대 int(max_rps) 줄 — tos_runtime 이 같은 파일에 쓰는 형식이고, 달라지면 tenant 세션과 이 도구가 서로의 허가를 못 읽어 한도를 두 번 쓴다
        _atomic_private_write(self._path, "".join(f"{grant:.6f}\n" for grant in kept))

    def _wait_for_slot(self, grants: tuple[float, ...], now: float) -> float:
        if not grants:
            return 0.0
        wait_s = max(0.0, grants[-1] + self._min_interval_s - now)
        if len(grants) >= self._window_grants:
            # SAFETY: 간격만 지키면 1초 창에 max_rps+1 건이 들어간다 (2.0 rps → t · t+0.5 · t+1.0) — 2026-11-23 EGW00201 의 원인이다
            oldest = grants[-self._window_grants]
            wait_s = max(wait_s, oldest + WINDOW_S + self._window_margin_s - now)
        return wait_s

    def _read_grants(self) -> tuple[float, ...]:
        try:
            raw = self._path.read_text(encoding="utf-8")
        except OSError:
            return ()
        try:
            grants = tuple(sorted(float(field) for field in raw.split()))
        except ValueError:
            return ()
        now = self._now()
        if any(grant > now + self._min_interval_s for grant in grants):
            return ()
        return grants[-self._window_grants :]


class SharedPacedCallPacer:
    """The probe client's own interval floor, with the app key's shared window behind it."""

    def __init__(
        self, inner: Any, pace: SharedAppKeyPace, *, wait_budget_s: float = LOCK_WAIT_S
    ) -> None:
        self._inner = inner
        self._pace = pace
        self._wait_budget_s = wait_budget_s

    @property
    def interval_s(self) -> float:
        """This tool's own floor between calls (the probe client reports it)."""
        return float(self._inner.interval_s)

    def wait(self) -> float:
        """This tool's floor first, then the app key's shared slot; return the release instant."""
        self._inner.wait()
        self._pace.acquire(wait_budget_s=self._wait_budget_s)
        return time.monotonic()

    def defer(self, seconds: float) -> None:
        """Push this tool's own next allowed call out (the shared window is unaffected)."""
        self._inner.defer(seconds)


def attach_shared_pace(client: Any, transport_yaml: str | None) -> Path | None:
    """Put the app key's shared window in front of ``client``'s calls; return the pace file."""
    resolved = resolve_transport_yaml(transport_yaml)
    if resolved is None:
        print(
            "WARNING: no shared pace file (--transport-yaml / "
            f"${TRANSPORT_YAML_ENV}) — this run does NOT share the KIS mock app "
            "key's rate limit with the running tenant sessions",
            file=sys.stderr,
        )
        return None
    terms = load_shared_pace_terms(resolved)
    client.pacer = SharedPacedCallPacer(client.pacer, SharedAppKeyPace(terms))
    return terms.path


def _ensure_private_dir(directory: Path) -> None:
    """Create ``directory`` 0700 if it is not there (it holds one app key's shared state)."""
    if directory.is_dir():
        return
    directory.mkdir(mode=_DIR_MODE, parents=True, exist_ok=True)
    try:
        os.chmod(directory, _DIR_MODE)
    except OSError:  # pragma: no cover - a directory we cannot chmod is still usable
        pass


def _atomic_private_write(path: Path, text: str) -> None:
    """Write ``text`` via tmp + rename, mode 0600 — a reader never sees half a file."""
    _ensure_private_dir(path.parent)
    tmp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    fd = os.open(
        tmp_path,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_CLOEXEC,
        PRIVATE_FILE_MODE,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_path, PRIVATE_FILE_MODE)
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
