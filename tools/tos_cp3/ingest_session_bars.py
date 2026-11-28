#!/usr/bin/env python3
"""tenant 세션이 이미 쥔 분봉을 호스트의 과거 저장소로 모은다 — 기본은 dry-run."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, get_args

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
    "REFUSED_PREFIX",
    "SCHEMA",
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


@dataclass(frozen=True)
class Row:
    """출력 표의 한 줄."""

    key: BarKey
    session: str
    candidate_bars: int
    existing_bars: int
    action: str

    @property
    def refused(self) -> bool:
        return self.action.startswith(REFUSED_PREFIX)

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

    @property
    def totals(self) -> dict[str, int]:
        counted = {
            ACTION_WRITE: 0,
            ACTION_SAME: 0,
            ACTION_KEPT: 0,
            "refused": 0,
            "thin": 0,
        }
        for row in self.rows:
            counted["refused" if row.refused else row.action] += 1
            if row.thin:
                counted["thin"] += 1
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


def _session_dirs(sessions_root: Path) -> list[SessionDir]:
    """``<label>-YYYYMMDD`` 세션 디렉터리 전부 — 생산자 저장소를 쥔 것만."""
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
        found.append(
            SessionDir(
                name=path.name,
                day_key=matched.group("day"),
                mtime=path.stat().st_mtime,
                market_root=market_root,
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
    frame = store.get_minute_bars(code)
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


def collect(
    sessions_root: Path,
    *,
    since: date | None = None,
    until: date | None = None,
) -> tuple[list[SessionDir], dict[BarKey, Candidate], dict[BarKey, str]]:
    """세션 전부를 훑어 칸마다 사본 하나를 고른다. 거부한 칸은 따로 돌려준다."""
    sessions = _session_dirs(sessions_root)
    chosen: dict[BarKey, Candidate] = {}
    refused: dict[BarKey, str] = {}
    for session in sessions:
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
    return sessions, chosen, refused


def _existing_bars(data_root: Path, keys: Sequence[BarKey]) -> dict[BarKey, int]:
    """과거 저장소가 이미 쥔 봉 수 — 칸마다."""
    days_by_code: dict[tuple[AssetClass, str], list[date]] = {}
    for key in keys:
        days_by_code.setdefault((key.asset_class, key.code), []).append(key.day)
    counted: dict[BarKey, int] = {}
    for (asset_class, code), days in days_by_code.items():
        # SAFETY: 코드 디렉터리가 없으면 읽지 않는다 — 저장소 리더는 그때 자산군 전체를 훑으므로, 세션이 처음 쥔 코드 하나가 수만 개 Parquet 를 한 질의에 읽어 이 호스트의 메모리를 먹는다
        if not (data_root / asset_class / TIMEFRAME / f"{CODE_PREFIX}{code}").is_dir():
            continue
        store = ParquetMarketDataStore(root=data_root, asset_class=asset_class)
        frame = store.get_minute_bars(code, start=min(days), end=max(days))
        if frame.empty:
            continue
        for day, group in frame.groupby(frame["datetime"].dt.date, sort=True):
            counted[BarKey(asset_class, code, day)] = int(group["datetime"].nunique())
    return counted


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
    existing = _existing_bars(data_root, keys)
    rows: list[Row] = []
    for key in keys:
        held = existing.get(key, 0)
        reason = refused.get(key)
        if reason is not None:
            rows.append(
                Row(
                    key=key,
                    session=MISSING,
                    candidate_bars=0,
                    existing_bars=held,
                    action=f"{REFUSED_PREFIX}{reason}",
                )
            )
            continue
        candidate = chosen[key]
        # SAFETY: replace_minute_day 는 그 날 디렉터리를 먼저 지운다 — 봉 수를 보지 않고 쓰면 늦게 뜬(부분) 세션의 짧은 사본이 이미 온전한 하루를 지우고 복구할 원본이 없다
        if candidate.bars > held:
            action = ACTION_WRITE
        elif candidate.bars == held:
            action = ACTION_SAME
        else:
            action = ACTION_KEPT
        rows.append(
            Row(
                key=key,
                session=candidate.session,
                candidate_bars=candidate.bars,
                existing_bars=held,
                action=action,
            )
        )
    return Plan(
        sessions_root=sessions_root,
        data_root=data_root,
        sessions=len(sessions),
        rows=tuple(rows),
        write=write,
    )


def apply(
    plan_result: Plan, chosen: dict[BarKey, Candidate], *, data_root: Path
) -> int:
    """``write`` 줄만 저장소에 올린다. 올린 봉 수를 돌려준다."""
    written = 0
    for row in plan_result.rows:
        if row.action != ACTION_WRITE:
            continue
        store = ParquetMarketDataStore(root=data_root, asset_class=row.key.asset_class)
        try:
            written += store.replace_minute_day(
                row.key.code, row.key.day, chosen[row.key].frame
            )
        except MarketDataStoreError as exc:
            raise IngestRefusal(
                f"{row.key.asset_class} {row.key.code} {row.key.day}: "
                f"저장소가 거부했다 ({exc})"
            ) from exc
    return written


def _cell(value: int, *, blank: bool) -> str:
    return MISSING if blank else str(value)


def render_text(plan_result: Plan) -> str:
    """사람이 읽는 표 — 자산군마다 한 덩이, 끝에 합계."""
    mode = "write" if plan_result.write else "dry-run"
    lines = [
        f"분봉 수집 ({mode}) · 세션 {plan_result.sessions} · "
        f"칸 {len(plan_result.rows)}",
        f"세션 루트 {plan_result.sessions_root}",
        f"저장소   {plan_result.data_root}",
        "",
    ]
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
                    "조치",
                ]
            )
        )
        for row in rows:
            lines.append(
                " ".join(
                    [
                        row.key.code.ljust(10),
                        row.key.day.isoformat().ljust(10),
                        row.session.ljust(24),
                        _cell(row.candidate_bars, blank=row.refused).rjust(6),
                        _cell(row.existing_bars, blank=False).rjust(6),
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
        "rows": [
            {
                "asset_class": row.key.asset_class,
                "code": row.key.code,
                "day": row.key.day.isoformat(),
                "session": row.session,
                "candidate_bars": None if row.refused else row.candidate_bars,
                "existing_bars": row.existing_bars,
                "resulting_bars": row.resulting_bars,
                "action": row.action,
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
    sessions, chosen, refused = collect(resolved_sessions, since=since, until=until)
    plan_result = plan(
        sessions,
        chosen,
        refused,
        sessions_root=resolved_sessions,
        data_root=resolved_data,
        write=write,
    )
    if write:
        apply(plan_result, chosen, data_root=resolved_data)
    text = render_json(plan_result) if as_json else render_text(plan_result)
    return text, plan_result.exit_code


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tools.tos_cp3.ingest_session_bars",
        description=(
            "tenant 세션이 쥔 분봉을 과거 저장소로 모은다. 기본은 dry-run 이고, "
            "쓰려면 --write 를 준다. 더 긴 하루를 더 짧은 하루로 덮지 않는다."
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
