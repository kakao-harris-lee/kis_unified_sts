#!/usr/bin/env python3
"""tenant 세션이 이미 쥔 분봉을 호스트의 과거 저장소로 모은다 — 기본은 dry-run."""

from __future__ import annotations

import argparse
import fcntl
import json
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import IO, Any, get_args

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.storage.config import StorageConfig  # noqa: E402
from shared.storage.market_data_store import (  # noqa: E402
    AssetClass,
    MarketDataStoreError,
    ParquetMarketDataStore,
)
from tools.tos_cp3 import status_board  # noqa: E402
from tools.tos_cp3.produce_fields import DEFAULT_MIN_BARS_PER_DAY  # noqa: E402

__all__ = [
    "ACTION_KEPT",
    "ACTION_SAME",
    "ACTION_WRITE",
    "DUPLICATE_DISAGREE",
    "EXISTING_DISAGREE",
    "INGEST_LOCK_NAME",
    "READ_ERROR",
    "REFUSED_PREFIX",
    "SCHEMA",
    "SESSION_LOCK_NAME",
    "SKIPPED_LIVE",
    "STORE_ERROR",
    "BarKey",
    "Candidate",
    "IngestRefusal",
    "Plan",
    "Row",
    "apply",
    "collect",
    "default_data_root",
    "default_sessions_root",
    "main",
    "plan",
    "render_json",
    "render_text",
    "run",
]

SCHEMA = "tos-ingest-bars/1"

ASSET_CLASSES: tuple[AssetClass, ...] = get_args(AssetClass)

TIMEFRAME = "minute"

PRODUCER_MARKET_SUBDIR = ("producer", "market")

CODE_PREFIX = "code="

OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")

ACTION_WRITE = "write"
ACTION_SAME = "same"
ACTION_KEPT = "kept_existing"
REFUSED_PREFIX = "refused:"
DUPLICATE_DISAGREE = "duplicate_timestamps"
EXISTING_DISAGREE = "existing_disagrees"
STORE_ERROR = "store_error"
READ_ERROR = "read_error"

DAY_KEY_FORMAT = "%Y%m%d"

READ_ERRORS: tuple[type[BaseException], ...]
try:
    import duckdb
except ImportError:  # pragma: no cover - 리더가 없으면 저장소가 먼저 거부한다
    READ_ERRORS = ()
else:
    # SAFETY: 깨진 part 파일에 저장소 리더가 내는 예외는 이 둘이다 — 더 넓게 잡으면 질의 오타나 메모리 고갈 같은 우리 쪽 버그가 「그 칸만 거부」로 묻히고, 더 좁게 잡으면 트레이스백이 되어 남은 칸이 쓰이지도 보고되지도 않는다
    READ_ERRORS = (duckdb.InvalidInputException, duckdb.IOException)

SKIPPED_LIVE = "skipped:live"

INGEST_LOCK_NAME = ".ingest-bars.lock"

SESSION_LOCK_NAME = ".session.lock"

MISSING = "-"


class IngestRefusal(RuntimeError):
    """모을 수 없는 입력 — 조용히 덜 모으는 것보다 거부가 낫다."""


@dataclass(frozen=True, order=True)
class BarKey:
    """과거 저장소의 한 칸 — 자산군 · 코드 · 거래일."""

    asset_class: AssetClass
    code: str
    day: date


@dataclass(frozen=True)
class SessionDir:
    """세션 하나 — 이름이 말하는 날짜와 생산자 저장소의 자리."""

    name: str
    day_key: str
    mtime: float
    market_root: Path
    live: bool = False

    @property
    def rank(self) -> tuple[str, float, str]:
        """늦은 세션이 큰 값 — 사본 고르기의 순서."""
        return (self.day_key, self.mtime, self.name)


@dataclass(frozen=True)
class Candidate:
    """한 칸에 올릴 사본 — 어느 세션의 것이고 봉이 몇 개인가."""

    session: str
    rank: tuple[str, float, str]
    bars: int
    frame: Any
    copy_disagree: int = 0


@dataclass(frozen=True)
class Row:
    """출력 표의 한 줄."""

    key: BarKey
    session: str
    candidate_bars: int
    existing_bars: int
    action: str
    existing_missing: int = 0
    existing_disagree: int = 0
    copy_disagree: int = 0
    detail: str = ""

    @property
    def refused(self) -> bool:
        return self.action.startswith(REFUSED_PREFIX)

    @property
    def has_candidate(self) -> bool:
        """사본을 고른 줄인가 — 사본 자체를 거부한 줄에는 셀 수가 없다."""
        return self.session != MISSING

    @property
    def resulting_bars(self) -> int:
        """이 조치 뒤 그 날이 쥐게 되는 봉 수."""
        return (
            self.candidate_bars if self.action == ACTION_WRITE else self.existing_bars
        )

    @property
    def thin(self) -> bool:
        """리플레이의 밀도 게이트 아래로 남는 날."""
        return self.resulting_bars < DEFAULT_MIN_BARS_PER_DAY


@dataclass(frozen=True)
class Plan:
    """한 번의 실행이 보는 전부 — 무엇을 어디서 어디로."""

    sessions_root: Path
    data_root: Path
    sessions: int
    rows: tuple[Row, ...]
    write: bool
    skipped: tuple[str, ...] = ()

    @property
    def totals(self) -> dict[str, int]:
        counted = {
            ACTION_WRITE: 0,
            ACTION_SAME: 0,
            ACTION_KEPT: 0,
            "refused": 0,
            "thin": 0,
            "copy_disagree": 0,
        }
        for row in self.rows:
            counted["refused" if row.refused else row.action] += 1
            if row.thin:
                counted["thin"] += 1
            if row.copy_disagree:
                counted["copy_disagree"] += 1
        return counted

    @property
    def exit_code(self) -> int:
        """거부가 하나라도 있으면 2 — 사본을 고르지 못한 날은 조용히 지나가지 않는다."""
        return 2 if self.totals["refused"] else 0


def default_sessions_root(
    config_path: Path = status_board.DEFAULT_CONFIG_PATH,
) -> Path:
    """세션 루트 — ``config/tos_status_board.yaml`` 의 상태 루트 아래 그 이름."""
    cfg = status_board.load_config(config_path)
    return cfg.state_dir / cfg.tenant_sessions_subdir


def default_data_root() -> Path:
    """과거 저장소 — ``config/storage.yaml::market_data.parquet.root``."""
    root = Path(StorageConfig.load_or_default().market_data.parquet.root)
    return root if root.is_absolute() else REPO_ROOT / root


def _looks_like_store(data_root: Path) -> bool:
    return any(
        (data_root / asset_class / TIMEFRAME).is_dir() for asset_class in ASSET_CLASSES
    )


def _producer_running(market_root: Path) -> bool:
    """도는 생산자가 세션 잠금을 쥐고 있는가 — 기다리지 않고, 없으면 만들지 않는다."""
    try:
        handle = (market_root / SESSION_LOCK_NAME).open("r", encoding="utf-8")
    except FileNotFoundError:
        return False
    except OSError:
        # SAFETY: 잠금 파일이 있는데 열리지 않으면(권한·I/O) 생산자가 도는지 알 수 없다 — 「안 돈다」로 보면 자라는 중인 세션의 반쯤 쓰인 하루가 과거 저장소에 굳는다
        return True
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
    except OSError:
        return True
    else:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return False
    finally:
        handle.close()


def _ingest_lock(data_root: Path) -> IO[str]:
    """쓰기 실행의 배타 잠금 — 겹치면 기다리지 않고 거부한다."""
    path = data_root / INGEST_LOCK_NAME
    handle = path.open("a", encoding="utf-8")
    try:
        # SAFETY: 겹친 두 쓰기 실행은 replace_minute_day 가 같은 날 디렉터리를 지우는 사이에 서로의 part 파일을 지운다 — 기다리는 대신 비켜나야 반쯤 쓰인 하루가 남지 않는다
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise IngestRefusal(
            f"{path}: 다른 수집 실행이 이 저장소를 쥐고 있다 ({exc}) — "
            "그 실행이 끝난 뒤에 다시 돈다"
        ) from exc
    return handle


def _session_dirs(sessions_root: Path, *, today: date) -> list[SessionDir]:
    """``<label>-YYYYMMDD`` 세션 디렉터리 전부 — 생산자 저장소를 쥔 것만."""
    today_key = today.strftime(DAY_KEY_FORMAT)
    try:
        entries = sorted(sessions_root.iterdir())
    except OSError as exc:
        raise IngestRefusal(
            f"{sessions_root}: 세션 루트를 열지 못했다 ({exc})"
        ) from exc
    found: list[SessionDir] = []
    for path in entries:
        matched = status_board._SESSION_DIR_RE.match(path.name)
        if matched is None or not path.is_dir():
            continue
        market_root = path.joinpath(*PRODUCER_MARKET_SUBDIR)
        if not market_root.is_dir():
            continue
        day_key = matched.group("day")
        # SAFETY: 오늘 날짜의 세션만 잠금을 떠본다 — 떠보는 쪽의 공유 flock 이 그 순간 부팅하는 생산자의 배타 flock 을 막아 생산자가 자기 세션을 거부하고, 지난 날짜의 세션은 애초에 살아 있을 수 없다
        live = day_key == today_key and _producer_running(market_root)
        found.append(
            SessionDir(
                name=path.name,
                day_key=day_key,
                mtime=path.stat().st_mtime,
                market_root=market_root,
                live=live,
            )
        )
    return found


def _codes(market_root: Path, asset_class: AssetClass) -> list[str]:
    base = market_root / asset_class / TIMEFRAME
    try:
        entries = sorted(base.iterdir())
    except OSError:
        return []
    return [
        entry.name.removeprefix(CODE_PREFIX)
        for entry in entries
        if entry.is_dir() and entry.name.startswith(CODE_PREFIX)
    ]


def _dedupe(frame: Any) -> Any | None:
    """같은 분이 두 번 있으면 하나로. 값이 어긋나면 ``None``."""
    duplicated = frame.duplicated(subset=["datetime"], keep=False)
    if bool(duplicated.any()):
        spread = frame[duplicated].groupby("datetime")[list(OHLCV_COLUMNS)].nunique()
        # SAFETY: 같은 분의 두 사본이 OHLCV 에서 어긋나면 어느 쪽이 브로커가 준 값인지 말할 수 없다 — 하나를 골라 쓰면 지어낸 봉이 과거 저장소에 남고 리플레이는 그것을 시장 역사로 읽는다
        if bool((spread > 1).to_numpy().any()):
            return None
    return frame.drop_duplicates(subset=["datetime"], keep="first").reset_index(
        drop=True
    )


def _day_frames(
    market_root: Path, *, asset_class: AssetClass, code: str
) -> Iterator[tuple[date, Any]]:
    """그 세션이 쥔 ``(거래일, 프레임)`` — 저장소 자신의 리더로 한 번에 읽는다."""
    store = ParquetMarketDataStore(root=market_root, asset_class=asset_class)
    try:
        frame = store.get_minute_bars(code)
    except READ_ERRORS as exc:
        # SAFETY: 세션 사본을 못 읽으면 그 코드의 어느 날이 그 안에 있었는지도 알 수 없다 — 트레이스백으로 터지면 그날 수집은 아무 칸도 올리지 않으므로, 읽지 못한 경로를 이름 부르고 거부한다
        where = market_root / asset_class / TIMEFRAME / f"{CODE_PREFIX}{code}"
        raise IngestRefusal(f"{where}: 세션 사본을 읽지 못했다 ({exc})") from exc
    if frame.empty:
        return
    for day, group in frame.groupby(frame["datetime"].dt.date, sort=True):
        yield day, group.reset_index(drop=True)


def _better(incumbent: Candidate | None, challenger: Candidate) -> bool:
    """사본을 바꿔 달 것인가."""
    if incumbent is None:
        return True
    # SAFETY: 봉이 더 많은 사본, 같으면 더 나중 세션의 사본을 고른다 — 당일 사본은 15:19 봉에서 끝나고 종가 단일가 봉은 다음 날 세션의 시드 사본에만 있다
    if challenger.bars != incumbent.bars:
        return challenger.bars > incumbent.bars
    return challenger.rank > incumbent.rank


Cells = dict[Any, set[tuple[Any, ...]]]


def _cells(frame: Any) -> Cells:
    """분 → 그 분에 실린 OHLCV 값들. 중복 분이 어긋나면 값이 둘 이상이다."""
    found: Cells = {}
    for record in frame[["datetime", *OHLCV_COLUMNS]].itertuples(index=False):
        stamp, *values = record
        found.setdefault(stamp, set()).add(tuple(values))
    return found


def _copy_disagreements(cells: Cells, pooled: Cells) -> int:
    """고른 사본이 같은 칸의 다른 사본과 어긋나는 분 수."""
    # SAFETY: 사본끼리 어긋나도 거부하지 않고 「봉이 많은 쪽, 같으면 나중 세션」(= 가장 나중 브로커 fetch)을 그대로 쓴다 — 브로커가 분봉을 정정하므로 거부는 멀쩡한 하루를 영구히 막고, 대신 어긋난 분 수를 줄마다 적어 조용히 고르지 않는다
    return sum(1 for stamp in cells if len(pooled.get(stamp, set())) > 1)


def collect(
    sessions_root: Path,
    *,
    since: date | None = None,
    until: date | None = None,
    today: date | None = None,
) -> tuple[list[SessionDir], dict[BarKey, Candidate], dict[BarKey, str]]:
    """세션 전부를 훑어 칸마다 사본 하나를 고른다. 거부한 칸은 따로 돌려준다."""
    sessions = _session_dirs(
        sessions_root, today=status_board.today_kst() if today is None else today
    )
    chosen: dict[BarKey, Candidate] = {}
    refused: dict[BarKey, str] = {}
    pooled: dict[BarKey, Cells] = {}
    for session in sessions:
        if session.live:
            # SAFETY: 도는 생산자의 세션은 아직 자라는 중이다 — 그 사본으로 결정하면 반쯤 쓰인 하루가 과거 저장소에 굳고, 생산자가 그 뒤에 쓴 분들은 다음 실행이 올 때까지 리플레이에 없다
            continue
        for asset_class in ASSET_CLASSES:
            for code in _codes(session.market_root, asset_class):
                for day, frame in _day_frames(
                    session.market_root, asset_class=asset_class, code=code
                ):
                    if since is not None and day < since:
                        continue
                    if until is not None and day > until:
                        continue
                    key = BarKey(asset_class, code, day)
                    deduped = _dedupe(frame)
                    if deduped is None:
                        refused[key] = DUPLICATE_DISAGREE
                        continue
                    bucket = pooled.setdefault(key, {})
                    for stamp, values in _cells(deduped).items():
                        bucket.setdefault(stamp, set()).update(values)
                    challenger = Candidate(
                        session=session.name,
                        rank=session.rank,
                        bars=int(len(deduped)),
                        frame=deduped,
                    )
                    if _better(chosen.get(key), challenger):
                        chosen[key] = challenger
    for key in refused:
        chosen.pop(key, None)
    for key, candidate in list(chosen.items()):
        chosen[key] = replace(
            candidate,
            copy_disagree=_copy_disagreements(_cells(candidate.frame), pooled[key]),
        )
    return sessions, chosen, refused


def _existing_cells(
    data_root: Path, keys: Sequence[BarKey]
) -> tuple[dict[BarKey, Cells], dict[BarKey, str]]:
    """과거 저장소가 이미 쥔 분과 그 값 — 칸마다. 읽지 못한 칸은 따로 돌려준다."""
    days_by_code: dict[tuple[AssetClass, str], list[date]] = {}
    for key in keys:
        days_by_code.setdefault((key.asset_class, key.code), []).append(key.day)
    held: dict[BarKey, Cells] = {}
    unread: dict[BarKey, str] = {}
    for (asset_class, code), days in days_by_code.items():
        # SAFETY: 코드 디렉터리가 없으면 읽지 않는다 — 저장소 리더는 그때 자산군 전체를 훑으므로, 세션이 처음 쥔 코드 하나가 수만 개 Parquet 를 한 질의에 읽어 이 호스트의 메모리를 먹는다
        if not (data_root / asset_class / TIMEFRAME / f"{CODE_PREFIX}{code}").is_dir():
            continue
        store = ParquetMarketDataStore(root=data_root, asset_class=asset_class)
        try:
            frame = store.get_minute_bars(code, start=min(days), end=max(days))
        except READ_ERRORS as exc:
            # SAFETY: 깨진 part 파일 한 장은 그 코드의 기존 하루를 읽을 수 없게 한다 — 읽히지 않는 것을 「없다」로 보면 replace_minute_day 가 그 날 디렉터리를 지우고 멀쩡한 봉까지 어디에도 없는 채로 덮는다
            for day in days:
                unread[BarKey(asset_class, code, day)] = str(exc)
            continue
        if frame.empty:
            continue
        wanted = set(days)
        for day, group in frame.groupby(frame["datetime"].dt.date, sort=True):
            if day in wanted:
                held[BarKey(asset_class, code, day)] = _cells(group)
    return held, unread


def _against_existing(held: Cells, candidate: Candidate) -> tuple[int, int, int]:
    """``(후보에 없는 기존 분, 겹치는 분 중 어긋난 분, 후보가 새로 쥔 분)``."""
    # SAFETY: 양쪽 모두 저장소 리더가 같은 _normalize_frame 으로 돌려준 값(OHLC float64 · volume int64)이므로 정확 일치로 비교한다 — 허용오차를 두면 정정된 봉이 「같다」로 통과해 조용히 덮인다
    offered = _cells(candidate.frame)
    missing = sum(1 for stamp in held if stamp not in offered)
    disagree = sum(
        1
        for stamp, values in held.items()
        if stamp in offered and offered[stamp] != values
    )
    added = sum(1 for stamp in offered if stamp not in held)
    return missing, disagree, added


def _action(held: Cells, *, missing: int, disagree: int, added: int) -> str:
    """그 칸의 조치 — 기존 하루를 담고 있는 사본만 쓴다."""
    if not held:
        return ACTION_WRITE
    # SAFETY: replace_minute_day 는 그 날 디렉터리를 먼저 지우므로 봉 수만 보고 쓰면 더 긴 다른 출처의 사본이 기존 분과 종가 봉을 어디에도 없는 채로 지운다 — 기존 분 전부를 담고 겹치는 분이 전부 같은 사본만 쓴다
    if disagree or (missing and added):
        return f"{REFUSED_PREFIX}{EXISTING_DISAGREE}"
    if missing:
        return ACTION_KEPT
    return ACTION_WRITE if added else ACTION_SAME


def plan(
    sessions: Sequence[SessionDir],
    chosen: dict[BarKey, Candidate],
    refused: dict[BarKey, str],
    *,
    sessions_root: Path,
    data_root: Path,
    write: bool,
) -> Plan:
    """고른 사본을 저장소가 이미 쥔 것과 대어 보고 조치를 정한다."""
    keys = sorted({*chosen, *refused})
    existing, unread = _existing_cells(data_root, keys)
    rows: list[Row] = []
    for key in keys:
        held = existing.get(key, {})
        failure = unread.get(key)
        if failure is not None:
            rows.append(
                Row(
                    key=key,
                    session=MISSING,
                    candidate_bars=0,
                    existing_bars=0,
                    action=f"{REFUSED_PREFIX}{READ_ERROR}",
                    detail=failure,
                )
            )
            continue
        reason = refused.get(key)
        if reason is not None:
            rows.append(
                Row(
                    key=key,
                    session=MISSING,
                    candidate_bars=0,
                    existing_bars=len(held),
                    action=f"{REFUSED_PREFIX}{reason}",
                )
            )
            continue
        candidate = chosen[key]
        missing, disagree, added = _against_existing(held, candidate)
        rows.append(
            Row(
                key=key,
                session=candidate.session,
                candidate_bars=candidate.bars,
                existing_bars=len(held),
                action=_action(held, missing=missing, disagree=disagree, added=added),
                existing_missing=missing,
                existing_disagree=disagree,
                copy_disagree=candidate.copy_disagree,
            )
        )
    return Plan(
        sessions_root=sessions_root,
        data_root=data_root,
        sessions=len(sessions),
        rows=tuple(rows),
        write=write,
        skipped=tuple(session.name for session in sessions if session.live),
    )


def apply(
    plan_result: Plan, chosen: dict[BarKey, Candidate], *, data_root: Path
) -> tuple[int, dict[BarKey, str]]:
    """``write`` 줄만 올린다. ``(올린 봉 수, 저장소가 거부한 칸)``."""
    written = 0
    failed: dict[BarKey, str] = {}
    for row in plan_result.rows:
        if row.action != ACTION_WRITE:
            continue
        store = ParquetMarketDataStore(root=data_root, asset_class=row.key.asset_class)
        try:
            written += store.replace_minute_day(
                row.key.code, row.key.day, chosen[row.key].frame
            )
        except (MarketDataStoreError, OSError) as exc:
            # SAFETY: 칸은 서로 독립이므로 한 칸의 저장소 거부로 멈추지 않는다 — 멈추면 남은 칸은 쓰이지도 보고되지도 않고 운영자는 그날 무엇이 안 올라갔는지 로그에서 알 수 없다
            failed[row.key] = _store_failure(exc, row)
    return written, failed


def _store_failure(exc: BaseException, row: Row) -> str:
    """저장소가 거부한 칸의 사유 — 봉을 쥐고 있던 하루면 이미 지워졌다고 적는다."""
    if not row.existing_bars:
        return str(exc)
    # SAFETY: replace_minute_day 는 쓰기 전에 그 날 디렉터리를 지우므로 쓰다가 실패한 칸은 봉을 쥐고 있던 하루가 빈 채로 남는다 — 줄에 적지 않으면 운영자는 다시 돌려야 하는 칸을 로그에서 가려낼 수 없다
    return (
        f"{exc} — 기존 {row.existing_bars} 봉이 있던 그 날 디렉터리는 쓰기 전에 "
        "이미 지워졌다, 이 칸은 다시 돌려야 한다"
    )


def _with_failures(plan_result: Plan, failed: dict[BarKey, str]) -> Plan:
    """저장소가 거부한 칸을 그 줄에 적는다 — 종료코드도 따라 2 가 된다."""
    rows = tuple(
        (
            replace(
                row,
                action=f"{REFUSED_PREFIX}{STORE_ERROR}",
                detail=failed[row.key],
            )
            if row.key in failed and row.action == ACTION_WRITE
            else row
        )
        for row in plan_result.rows
    )
    return replace(plan_result, rows=rows)


def _cell(value: int, *, blank: bool) -> str:
    return MISSING if blank else str(value)


def render_text(plan_result: Plan) -> str:
    """사람이 읽는 표 — 자산군마다 한 덩이, 끝에 합계."""
    mode = "write" if plan_result.write else "dry-run"
    lines = [
        f"분봉 수집 ({mode}) · 세션 {plan_result.sessions} "
        f"(건너뜀 {len(plan_result.skipped)}) · 칸 {len(plan_result.rows)}",
        f"세션 루트 {plan_result.sessions_root}",
        f"저장소   {plan_result.data_root}",
        "",
    ]
    for name in plan_result.skipped:
        lines.append(f"{name} — {SKIPPED_LIVE} (생산자가 세션 잠금을 쥐고 있다)")
    if plan_result.skipped:
        lines.append("")
    for asset_class in ASSET_CLASSES:
        rows = [row for row in plan_result.rows if row.key.asset_class == asset_class]
        if not rows:
            continue
        lines.append(f"{asset_class} ({len(rows)})")
        lines.append(
            " ".join(
                [
                    "코드".ljust(10),
                    "날짜".ljust(10),
                    "세션".ljust(24),
                    "후보".rjust(6),
                    "기존".rjust(6),
                    "결손".rjust(6),
                    "어긋".rjust(6),
                    "사본차".rjust(6),
                    "조치",
                ]
            )
        )
        for row in rows:
            unknown = not row.has_candidate
            lines.append(
                " ".join(
                    [
                        row.key.code.ljust(10),
                        row.key.day.isoformat().ljust(10),
                        row.session.ljust(24),
                        _cell(row.candidate_bars, blank=unknown).rjust(6),
                        _cell(row.existing_bars, blank=False).rjust(6),
                        _cell(row.existing_missing, blank=unknown).rjust(6),
                        _cell(row.existing_disagree, blank=unknown).rjust(6),
                        _cell(row.copy_disagree, blank=unknown).rjust(6),
                        row.action,
                    ]
                )
            )
        lines.append("")

    totals = plan_result.totals
    lines.append(
        f"합계: {ACTION_WRITE} {totals[ACTION_WRITE]} · "
        f"{ACTION_SAME} {totals[ACTION_SAME]} · "
        f"{ACTION_KEPT} {totals[ACTION_KEPT]} · "
        f"refused {totals['refused']}"
    )
    lines.append(f"사본끼리 어긋난 분이 있는 칸: {totals['copy_disagree']}")
    for row in plan_result.rows:
        if row.detail:
            lines.append(
                f"  {row.key.asset_class} {row.key.code} "
                f"{row.key.day.isoformat()} — {row.detail}"
            )
    thin = [row for row in plan_result.rows if row.thin]
    lines.append(
        f"리플레이 밀도 게이트({DEFAULT_MIN_BARS_PER_DAY}) 아래로 남는 날: {len(thin)}"
    )
    for row in thin:
        lines.append(
            f"  {row.key.asset_class} {row.key.code} {row.key.day.isoformat()} "
            f"— {row.resulting_bars} 봉"
        )
    if not plan_result.write:
        lines.append("쓰지 않았다 — 쓰려면 `--write` 를 준다.")
    return "\n".join(lines) + "\n"


def render_json(plan_result: Plan) -> str:
    """기계용 — 같은 줄과 합계."""
    document = {
        "schema": SCHEMA,
        "write": plan_result.write,
        "sessions_root": str(plan_result.sessions_root),
        "data_root": str(plan_result.data_root),
        "sessions": plan_result.sessions,
        "min_bars_per_day": DEFAULT_MIN_BARS_PER_DAY,
        "skipped_sessions": [
            {"session": name, "action": SKIPPED_LIVE} for name in plan_result.skipped
        ],
        "rows": [
            {
                "asset_class": row.key.asset_class,
                "code": row.key.code,
                "day": row.key.day.isoformat(),
                "session": row.session,
                "candidate_bars": row.candidate_bars if row.has_candidate else None,
                "existing_bars": row.existing_bars,
                "existing_missing": row.existing_missing if row.has_candidate else None,
                "existing_disagree": (
                    row.existing_disagree if row.has_candidate else None
                ),
                "copy_disagree": row.copy_disagree if row.has_candidate else None,
                "resulting_bars": row.resulting_bars,
                "action": row.action,
                "detail": row.detail,
                "thin": row.thin,
            }
            for row in plan_result.rows
        ],
        "totals": plan_result.totals,
    }
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def run(
    *,
    sessions_root: Path | None = None,
    data_root: Path | None = None,
    since: date | None = None,
    until: date | None = None,
    today: date | None = None,
    write: bool = False,
    init: bool = False,
    as_json: bool = False,
    config_path: Path = status_board.DEFAULT_CONFIG_PATH,
) -> tuple[str, int]:
    """한 번의 실행 — 훑고, 대어 보고, (``write`` 면) 쓴다."""
    resolved_sessions = (
        default_sessions_root(config_path) if sessions_root is None else sessions_root
    )
    resolved_data = default_data_root() if data_root is None else data_root
    if since is not None and until is not None and since > until:
        raise IngestRefusal(f"--since {since} 가 --until {until} 보다 뒤다")
    if not resolved_sessions.is_dir():
        raise IngestRefusal(f"{resolved_sessions}: 그런 세션 루트가 없다")
    if not init and not _looks_like_store(resolved_data):
        # SAFETY: 오타 난 --data-root 는 둘째 저장소를 조용히 만든다 — 한 번 갈라지면 리플레이는 비어 보이는 쪽을 읽고 모은 날은 아무도 보지 않는 자리에 쌓인다
        expected = ", ".join(f"{name}/{TIMEFRAME}" for name in ASSET_CLASSES)
        raise IngestRefusal(
            f"{resolved_data}: 분봉 저장소로 보이지 않는다 ({expected} 가 없다) — "
            "새 저장소를 여는 것이 맞다면 --init 을 준다"
        )
    if not write:
        dry, _chosen = _planned(
            resolved_sessions, resolved_data, since, until, today, write
        )
        return _render(dry, as_json=as_json)
    resolved_data.mkdir(parents=True, exist_ok=True)
    handle = _ingest_lock(resolved_data)
    try:
        plan_result, chosen = _planned(
            resolved_sessions, resolved_data, since, until, today, write
        )
        _written, failed = apply(plan_result, chosen, data_root=resolved_data)
        if failed:
            plan_result = _with_failures(plan_result, failed)
    finally:
        handle.close()
    return _render(plan_result, as_json=as_json)


def _planned(
    sessions_root: Path,
    data_root: Path,
    since: date | None,
    until: date | None,
    today: date | None,
    write: bool,
) -> tuple[Plan, dict[BarKey, Candidate]]:
    sessions, chosen, refused = collect(
        sessions_root, since=since, until=until, today=today
    )
    return (
        plan(
            sessions,
            chosen,
            refused,
            sessions_root=sessions_root,
            data_root=data_root,
            write=write,
        ),
        chosen,
    )


def _render(plan_result: Plan, *, as_json: bool) -> tuple[str, int]:
    text = render_json(plan_result) if as_json else render_text(plan_result)
    return text, plan_result.exit_code


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tools.tos_cp3.ingest_session_bars",
        description=(
            "tenant 세션이 쥔 분봉을 과거 저장소로 모은다. 기본은 dry-run 이고, "
            "쓰려면 --write 를 준다. 이미 있는 하루는 그 분을 전부 담고 겹치는 "
            "분이 전부 같은 사본으로만 덮는다 — 봉 수만으로는 덮지 않는다."
        ),
    )
    parser.add_argument(
        "--sessions-root",
        type=Path,
        default=None,
        help="CP-3 세션 루트 (기본: config/tos_status_board.yaml 의 state_dir/cp3-sessions)",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="분봉 Parquet 저장소 (기본: config/storage.yaml 의 market_data.parquet.root)",
    )
    parser.add_argument(
        "--since",
        type=date.fromisoformat,
        default=None,
        help="이 거래일부터 (포함)",
    )
    parser.add_argument(
        "--until",
        type=date.fromisoformat,
        default=None,
        help="이 거래일까지 (포함)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="아무것도 쓰지 않는다 (기본 동작 — 명시용)",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="계획의 write 줄을 실제로 저장소에 올린다",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="--data-root 가 아직 분봉 저장소가 아니어도 허용한다 (새 저장소를 연다)",
    )
    parser.add_argument(
        "--config",
        dest="config_path",
        type=Path,
        default=status_board.DEFAULT_CONFIG_PATH,
        help="상태판 설정 YAML (세션 루트의 출처)",
    )
    parser.add_argument("--json", dest="as_json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """성공 ``0``, 거부 ``2``."""
    args = _parser().parse_args(argv)
    try:
        if args.dry_run and args.write:
            raise IngestRefusal("--dry-run 과 --write 를 함께 줄 수 없다")
        text, code = run(
            sessions_root=args.sessions_root,
            data_root=args.data_root,
            since=args.since,
            until=args.until,
            write=args.write,
            init=args.init,
            as_json=args.as_json,
            config_path=args.config_path,
        )
    except (IngestRefusal, MarketDataStoreError, OSError, ValueError) as exc:
        print(f"ingest-bars refused: {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(text)
    return code


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
