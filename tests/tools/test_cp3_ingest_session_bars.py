"""``tools/tos_cp3/ingest_session_bars.py`` — 세션 분봉을 과거 저장소로 모으기."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest

from shared.storage.market_data_store import (
    MarketDataStoreError,
    ParquetMarketDataStore,
)
from tools.tos_cp3 import ingest_session_bars as ing
from tools.tos_cp3.live_producer.sinks import acquire_session_lock
from tools.tos_cp3.produce_fields import DEFAULT_MIN_BARS_PER_DAY, load_bars

# SAFETY: 분봉은 전부 합성이고 저장소는 전부 tmp_path 안이다 — 실제 시세나 호스트의 data/ · ~/.local/state/tos 를 끌어오면 이 공개 저장소의 고정본에 시세 데이터가 실린다
STOCK, OTHER = "005930", "000660"
FRONT, NEXT = "A05612", "A05701"
D24, D25, D26 = dt.date(2026, 11, 24), dt.date(2026, 11, 25), dt.date(2026, 11, 26)

FULL_BARS = DEFAULT_MIN_BARS_PER_DAY + 51

CORRUPT_PART = b"not a parquet file"


def _rows(
    code: str, day: dt.date, bars: int, *, base: float = 100.0
) -> list[dict[str, Any]]:
    """09:00 부터 빈 분 없이 ``bars`` 개 — 값은 합성이다."""
    opening = dt.datetime.combine(day, dt.time(9, 0))
    return [
        {
            "code": code,
            "datetime": opening + dt.timedelta(minutes=index),
            "open": base + index * 0.1,
            "high": base + index * 0.1 + 1,
            "low": base + index * 0.1 - 1,
            "close": base + index * 0.1 + 0.5,
            "volume": 10 + index,
        }
        for index in range(bars)
    ]


def _pick(rows: list[dict[str, Any]], *indexes: int) -> list[dict[str, Any]]:
    """같은 봉들의 부분집합 — 겹치는 분은 값이 글자 그대로 일치한다."""
    return [rows[index] for index in indexes]


def _session_store(
    root: Path, session: str, *, asset_class: str
) -> ParquetMarketDataStore:
    """``<sessions>/<session>/producer/market`` 의 저장소 — 실제 세션과 같은 자리."""
    market = root / session / "producer" / "market"
    return ParquetMarketDataStore(root=market, asset_class=asset_class)


def _data_root(tmp_path: Path) -> Path:
    """저장소로 보이는 ``--data-root`` (두 자산군의 ``minute`` 디렉터리)."""
    data_root = tmp_path / "market"
    for asset_class in ing.ASSET_CLASSES:
        (data_root / asset_class / ing.TIMEFRAME).mkdir(parents=True)
    return data_root


def _day_dir(root: Path, code: str, day: dt.date) -> Path:
    """그 코드·날의 분봉 파티션 — 저장소가 part 파일을 두는 바로 그 디렉터리."""
    return (
        root
        / "stock"
        / ing.TIMEFRAME
        / f"code={code}"
        / f"year={day.year}"
        / f"month={day.month:02d}"
        / f"day={day.isoformat()}"
    )


def _listing(root: Path) -> dict[str, str]:
    """경로 → 내용 해시 (잠금 파일 제외). 봉이 바뀌었는지 보는 눈."""
    found: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.name == ing.INGEST_LOCK_NAME:
            continue
        key = str(path.relative_to(root))
        found[key] = (
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "dir"
        )
    return found


def _actions(text: str) -> dict[tuple[str, str], str]:
    """``--json`` 출력의 ``(코드, 날짜) → 조치``."""
    document = json.loads(text)
    return {(row["code"], row["day"]): row["action"] for row in document["rows"]}


def _rows_of(text: str) -> list[dict[str, Any]]:
    rows: Sequence[dict[str, Any]] = json.loads(text)["rows"]
    return list(rows)


@pytest.fixture
def sessions(tmp_path: Path) -> Iterator[Path]:
    """두 세션 — 늦은 세션이 그 날의 더 긴 사본을 쥔다."""
    root = tmp_path / "cp3-sessions"
    _session_store(root, "stock-r1-20261125", asset_class="stock").append_minute_bars(
        _rows(STOCK, D25, FULL_BARS - 1)
    )
    _session_store(root, "stock-r1-20261126", asset_class="stock").append_minute_bars(
        _rows(STOCK, D25, FULL_BARS)
    )
    yield root


def test_picks_the_longest_copy_across_sessions(sessions: Path, tmp_path: Path) -> None:
    """사본이 둘이면 봉이 많은 쪽 — 당일 사본은 종가 단일가 봉을 쥐지 않는다."""
    text, code = ing.run(
        sessions_root=sessions, data_root=_data_root(tmp_path), as_json=True
    )
    assert code == 0
    (row,) = _rows_of(text)
    assert row["session"] == "stock-r1-20261126"
    assert row["candidate_bars"] == FULL_BARS
    assert row["action"] == ing.ACTION_WRITE


def test_tie_on_bar_count_takes_the_later_session(tmp_path: Path) -> None:
    """봉 수가 같으면 세션 날짜가 늦은 쪽 — 결정론적이어야 한다."""
    root = tmp_path / "cp3-sessions"
    for session in ("stock-r1-20261124", "stock-r9-20261126", "stock-r1-20261125"):
        _session_store(root, session, asset_class="stock").append_minute_bars(
            _rows(STOCK, D24, FULL_BARS)
        )
    text, _code = ing.run(
        sessions_root=root, data_root=_data_root(tmp_path), as_json=True
    )
    (row,) = _rows_of(text)
    assert row["session"] == "stock-r9-20261126"


def test_dry_run_writes_nothing(sessions: Path, tmp_path: Path) -> None:
    """기본 동작은 dry-run — 목록도 해시도 그대로고 잠금 파일도 만들지 않는다."""
    data_root = _data_root(tmp_path)
    before = _listing(data_root)
    text, code = ing.run(sessions_root=sessions, data_root=data_root)
    assert code == 0
    assert ing.ACTION_WRITE in text
    assert _listing(data_root) == before
    assert not (data_root / ing.INGEST_LOCK_NAME).exists()


def test_write_then_second_run_is_a_no_op(sessions: Path, tmp_path: Path) -> None:
    """``--write`` 는 고른 날만 쓰고, 두 번째 실행은 ``same`` 이다."""
    data_root = _data_root(tmp_path)
    _text, code = ing.run(sessions_root=sessions, data_root=data_root, write=True)
    assert code == 0
    stored = ParquetMarketDataStore(root=data_root, asset_class="stock")
    assert len(stored.get_minute_bars(STOCK, start=D25, end=D25)) == FULL_BARS
    assert stored.get_minute_bars(STOCK, start=D24, end=D24).empty

    after_write = _listing(data_root)
    text, code = ing.run(
        sessions_root=sessions, data_root=data_root, write=True, as_json=True
    )
    assert code == 0
    assert _actions(text) == {(STOCK, D25.isoformat()): ing.ACTION_SAME}
    assert _listing(data_root) == after_write


def test_a_longer_existing_day_is_kept_byte_unchanged(tmp_path: Path) -> None:
    """저장소가 더 긴 하루를 쥐고 있으면 건드리지 않는다 — 덮으면 손실이다."""
    root = tmp_path / "cp3-sessions"
    _session_store(root, "stock-r1-20261126", asset_class="stock").append_minute_bars(
        _rows(STOCK, D25, FULL_BARS - 40)
    )
    data_root = _data_root(tmp_path)
    ParquetMarketDataStore(root=data_root, asset_class="stock").append_minute_bars(
        _rows(STOCK, D25, FULL_BARS)
    )
    before = _listing(data_root)

    text, code = ing.run(
        sessions_root=root, data_root=data_root, write=True, as_json=True
    )
    assert code == 0
    assert _actions(text) == {(STOCK, D25.isoformat()): ing.ACTION_KEPT}
    assert _listing(data_root) == before


def test_disagreeing_duplicate_timestamps_refuse_only_that_key(
    tmp_path: Path,
) -> None:
    """같은 분이 어긋나는 사본은 그 날을 거부한다 — 다른 날은 그대로 돈다."""
    root = tmp_path / "cp3-sessions"
    store = _session_store(root, "stock-r1-20261126", asset_class="stock")
    clashing = _rows(STOCK, D25, FULL_BARS)
    store.append_minute_bars(clashing)
    store.append_minute_bars([{**clashing[7], "close": clashing[7]["close"] + 5}])
    store.append_minute_bars(_rows(STOCK, D24, FULL_BARS))

    data_root = _data_root(tmp_path)
    text, code = ing.run(
        sessions_root=root, data_root=data_root, write=True, as_json=True
    )
    assert code == 2
    assert _actions(text) == {
        (STOCK, D24.isoformat()): ing.ACTION_WRITE,
        (STOCK, D25.isoformat()): f"{ing.REFUSED_PREFIX}{ing.DUPLICATE_DISAGREE}",
    }
    stored = ParquetMarketDataStore(root=data_root, asset_class="stock")
    assert len(stored.get_minute_bars(STOCK, start=D24, end=D24)) == FULL_BARS
    assert stored.get_minute_bars(STOCK, start=D25, end=D25).empty


def test_agreeing_duplicate_timestamps_are_deduped(tmp_path: Path) -> None:
    """값이 같은 중복 분은 하나로 접는다 — 거부가 아니다."""
    root = tmp_path / "cp3-sessions"
    store = _session_store(root, "stock-r1-20261126", asset_class="stock")
    rows = _rows(STOCK, D25, FULL_BARS)
    store.append_minute_bars(rows)
    store.append_minute_bars([rows[3], rows[9]])

    text, code = ing.run(
        sessions_root=root, data_root=_data_root(tmp_path), as_json=True
    )
    assert code == 0
    (row,) = _rows_of(text)
    assert row["candidate_bars"] == FULL_BARS


def test_futures_seed_days_land_under_their_own_contract(tmp_path: Path) -> None:
    """선물 시드 날은 그 날의 월물 코드 아래로 간다 — 월물을 섞지 않는다."""
    root = tmp_path / "cp3-sessions"
    store = _session_store(root, "long-20261126", asset_class="futures")
    store.append_minute_bars(_rows(FRONT, D25, FULL_BARS))
    store.append_minute_bars(_rows(NEXT, D24, FULL_BARS, base=200.0))

    data_root = _data_root(tmp_path)
    text, code = ing.run(
        sessions_root=root, data_root=data_root, write=True, as_json=True
    )
    assert code == 0
    assert _actions(text) == {
        (FRONT, D25.isoformat()): ing.ACTION_WRITE,
        (NEXT, D24.isoformat()): ing.ACTION_WRITE,
    }
    stored = ParquetMarketDataStore(root=data_root, asset_class="futures")
    assert len(stored.get_minute_bars(FRONT, start=D25, end=D25)) == FULL_BARS
    assert stored.get_minute_bars(FRONT, start=D24, end=D24).empty
    assert len(stored.get_minute_bars(NEXT, start=D24, end=D24)) == FULL_BARS


def test_since_and_until_narrow_the_days(tmp_path: Path) -> None:
    """``--since``/``--until`` 밖의 날은 계획에 들어오지 않는다."""
    root = tmp_path / "cp3-sessions"
    store = _session_store(root, "stock-r1-20261126", asset_class="stock")
    for day in (D24, D25, D26):
        store.append_minute_bars(_rows(STOCK, day, FULL_BARS))

    data_root = _data_root(tmp_path)
    text, code = ing.run(
        sessions_root=root, data_root=data_root, since=D25, until=D25, as_json=True
    )
    assert code == 0
    assert _actions(text) == {(STOCK, D25.isoformat()): ing.ACTION_WRITE}

    with pytest.raises(ing.IngestRefusal):
        ing.run(sessions_root=root, data_root=data_root, since=D26, until=D24)


def test_a_data_root_that_is_not_a_store_is_refused(
    sessions: Path, tmp_path: Path
) -> None:
    """저장소로 보이지 않는 ``--data-root`` 는 거부한다 — 오타가 둘째 저장소를 만든다."""
    typo = tmp_path / "markte"
    assert (
        ing.main(
            [
                "--sessions-root",
                str(sessions),
                "--data-root",
                str(typo),
                "--write",
            ]
        )
        == 2
    )
    assert not typo.exists()

    assert (
        ing.main(
            [
                "--sessions-root",
                str(sessions),
                "--data-root",
                str(typo),
                "--init",
                "--write",
            ]
        )
        == 0
    )
    assert (typo / "stock" / ing.TIMEFRAME / f"code={STOCK}").is_dir()


def test_dry_run_and_write_together_are_refused(sessions: Path, tmp_path: Path) -> None:
    """``--dry-run --write`` 는 모순이다 — 어느 쪽을 뜻했는지 묻지 않고 거부한다."""
    assert (
        ing.main(
            [
                "--sessions-root",
                str(sessions),
                "--data-root",
                str(_data_root(tmp_path)),
                "--dry-run",
                "--write",
            ]
        )
        == 2
    )


def _one_day(
    tmp_path: Path, *, session_rows: list[dict[str, Any]], held: list[dict]
) -> tuple[Path, Path]:
    """세션 하나 · 저장소에 이미 있는 하루 하나 — ``(세션 루트, 저장소 루트)``."""
    root = tmp_path / "cp3-sessions"
    _session_store(root, "stock-r1-20261126", asset_class="stock").append_minute_bars(
        session_rows
    )
    data_root = _data_root(tmp_path)
    ParquetMarketDataStore(root=data_root, asset_class="stock").append_minute_bars(held)
    return root, data_root


def test_a_candidate_missing_an_existing_minute_is_refused(tmp_path: Path) -> None:
    """후보가 더 길어도 기존 분 하나를 빼먹으면 거부다 — 봉 수만 보면 그 분이 사라진다."""
    full = _rows(STOCK, D25, 6)
    root, data_root = _one_day(tmp_path, session_rows=full[:3], held=_pick(full, 0, 5))
    before = _listing(data_root)

    text, code = ing.run(
        sessions_root=root, data_root=data_root, write=True, as_json=True
    )
    assert code == 2
    (row,) = _rows_of(text)
    assert row["action"] == f"{ing.REFUSED_PREFIX}{ing.EXISTING_DISAGREE}"
    assert (row["candidate_bars"], row["existing_bars"]) == (3, 2)
    assert (row["existing_missing"], row["existing_disagree"]) == (1, 0)
    assert _listing(data_root) == before


def test_an_agreeing_superset_is_written(tmp_path: Path) -> None:
    """기존 분을 전부 담고 값이 같은 더 긴 사본은 쓴다 — 결과는 후보 그대로다."""
    full = _rows(STOCK, D25, 3)
    root, data_root = _one_day(tmp_path, session_rows=full, held=_pick(full, 0, 1))

    text, code = ing.run(
        sessions_root=root, data_root=data_root, write=True, as_json=True
    )
    assert code == 0
    (row,) = _rows_of(text)
    assert row["action"] == ing.ACTION_WRITE
    assert (row["existing_missing"], row["existing_disagree"]) == (0, 0)

    stored = ParquetMarketDataStore(root=data_root, asset_class="stock")
    frame = stored.get_minute_bars(STOCK, start=D25, end=D25)
    assert [stamp.to_pydatetime() for stamp in frame["datetime"]] == [
        entry["datetime"] for entry in full
    ]
    for column in ("open", "high", "low", "close", "volume"):
        assert list(frame[column]) == [entry[column] for entry in full]


@pytest.mark.parametrize("column", ["open", "high", "low", "close", "volume"])
def test_one_disagreeing_overlapping_cell_is_refused(
    tmp_path: Path, column: str
) -> None:
    """겹치는 분 하나가 어긋나면 거부다 — 어느 쪽이 브로커 값인지 말할 수 없다."""
    full = _rows(STOCK, D25, 3)
    revised = {**full[1], column: full[1][column] + 1}
    root, data_root = _one_day(tmp_path, session_rows=full, held=[full[0], revised])
    before = _listing(data_root)

    text, code = ing.run(
        sessions_root=root, data_root=data_root, write=True, as_json=True
    )
    assert code == 2
    (row,) = _rows_of(text)
    assert row["action"] == f"{ing.REFUSED_PREFIX}{ing.EXISTING_DISAGREE}"
    assert (row["existing_missing"], row["existing_disagree"]) == (0, 1)
    assert _listing(data_root) == before


def test_copies_that_disagree_with_each_other_are_counted_not_refused(
    tmp_path: Path,
) -> None:
    """사본끼리 어긋난 분은 줄에 센다 — 고르는 규칙은 그대로고 거부하지 않는다."""
    root = tmp_path / "cp3-sessions"
    seed = _rows(STOCK, D25, 4)
    _session_store(root, "stock-r1-20261125", asset_class="stock").append_minute_bars(
        [seed[0], {**seed[1], "close": seed[1]["close"] + 0.05}, seed[2]]
    )
    _session_store(root, "stock-r1-20261126", asset_class="stock").append_minute_bars(
        seed
    )

    text, code = ing.run(
        sessions_root=root, data_root=_data_root(tmp_path), as_json=True
    )
    assert code == 0
    (row,) = _rows_of(text)
    assert row["session"] == "stock-r1-20261126"
    assert row["action"] == ing.ACTION_WRITE
    assert row["copy_disagree"] == 1
    assert json.loads(text)["totals"]["copy_disagree"] == 1


def test_a_session_whose_producer_holds_the_lock_is_skipped(tmp_path: Path) -> None:
    """생산자가 세션 잠금을 쥐고 있으면 그 세션의 사본은 전부 건너뛴다."""
    root = tmp_path / "cp3-sessions"
    live = "stock-r1-20261126"
    _session_store(root, live, asset_class="stock").append_minute_bars(
        _rows(STOCK, D25, FULL_BARS)
    )
    _session_store(root, "stock-r1-20261125", asset_class="stock").append_minute_bars(
        _rows(STOCK, D24, FULL_BARS)
    )
    handle = acquire_session_lock(root / live / "producer" / "market")
    try:
        text, code = ing.run(
            sessions_root=root, data_root=_data_root(tmp_path), today=D26, as_json=True
        )
    finally:
        handle.close()

    assert code == 0
    document = json.loads(text)
    assert document["skipped_sessions"] == [
        {"session": live, "action": ing.SKIPPED_LIVE}
    ]
    assert _actions(text) == {(STOCK, D24.isoformat()): ing.ACTION_WRITE}


def test_only_a_session_dated_today_is_probed_for_the_lock(tmp_path: Path) -> None:
    """지난 날짜의 세션은 떠보지 않는다 — 떠보는 공유 잠금이 부팅하는 생산자를 막는다."""
    root = tmp_path / "cp3-sessions"
    held = "stock-r1-20261125"
    _session_store(root, held, asset_class="stock").append_minute_bars(
        _rows(STOCK, D24, FULL_BARS)
    )
    data_root = _data_root(tmp_path)
    handle = acquire_session_lock(root / held / "producer" / "market")
    try:
        earlier, earlier_code = ing.run(
            sessions_root=root, data_root=data_root, today=D26, as_json=True
        )
        current, current_code = ing.run(
            sessions_root=root, data_root=data_root, today=D25, as_json=True
        )
    finally:
        handle.close()

    assert (earlier_code, current_code) == (0, 0)
    assert json.loads(earlier)["skipped_sessions"] == []
    assert _actions(earlier) == {(STOCK, D24.isoformat()): ing.ACTION_WRITE}
    assert json.loads(current)["skipped_sessions"] == [
        {"session": held, "action": ing.SKIPPED_LIVE}
    ]
    assert _actions(current) == {}


def test_an_unreadable_session_lock_counts_as_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """잠금 파일이 열리지 않으면 「안 돈다」가 아니다 — 알 수 없으면 건너뛴다."""
    root = tmp_path / "cp3-sessions"
    live = "stock-r1-20261126"
    _session_store(root, live, asset_class="stock").append_minute_bars(
        _rows(STOCK, D25, FULL_BARS)
    )
    lock = root / live / "producer" / "market" / ing.SESSION_LOCK_NAME
    lock.write_text("", encoding="utf-8")

    opener = Path.open

    def guarded(self: Path, *args: Any, **kwargs: Any) -> Any:
        if self.name == ing.SESSION_LOCK_NAME:
            raise PermissionError(13, "합성 권한 거부")
        return opener(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    text, code = ing.run(
        sessions_root=root, data_root=_data_root(tmp_path), today=D26, as_json=True
    )

    assert code == 0
    assert json.loads(text)["skipped_sessions"] == [
        {"session": live, "action": ing.SKIPPED_LIVE}
    ]
    assert _actions(text) == {}


def test_a_second_write_run_refuses_while_the_lock_is_held(
    sessions: Path, tmp_path: Path
) -> None:
    """쓰기 실행은 저장소 잠금을 배타로 잡는다 — 겹치면 기다리지 않고 거부다."""
    data_root = _data_root(tmp_path)
    before = _listing(data_root)
    handle = ing._ingest_lock(data_root)
    try:
        assert (
            ing.main(
                [
                    "--sessions-root",
                    str(sessions),
                    "--data-root",
                    str(data_root),
                    "--write",
                ]
            )
            == 2
        )
    finally:
        handle.close()
    assert _listing(data_root) == before


def test_a_store_error_leaves_the_other_keys_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """한 칸이 저장소에 거부당해도 남은 칸은 쓰고, 거부당한 칸을 그 줄에 적는다."""
    root = tmp_path / "cp3-sessions"
    store = _session_store(root, "stock-r1-20261126", asset_class="stock")
    store.append_minute_bars(_rows(STOCK, D24, FULL_BARS))
    store.append_minute_bars(_rows(STOCK, D25, FULL_BARS))

    original = ParquetMarketDataStore.replace_minute_day

    def flaky(self: Any, symbol: str, trading_day: Any, rows: Any) -> int:
        if trading_day == D24:
            raise MarketDataStoreError("합성 고장")
        return int(original(self, symbol, trading_day, rows))

    monkeypatch.setattr(ParquetMarketDataStore, "replace_minute_day", flaky)

    data_root = _data_root(tmp_path)
    text, code = ing.run(
        sessions_root=root, data_root=data_root, write=True, as_json=True
    )
    assert code == 2
    assert _actions(text) == {
        (STOCK, D24.isoformat()): f"{ing.REFUSED_PREFIX}{ing.STORE_ERROR}",
        (STOCK, D25.isoformat()): ing.ACTION_WRITE,
    }
    assert "합성 고장" in text
    stored = ParquetMarketDataStore(root=data_root, asset_class="stock")
    assert len(stored.get_minute_bars(STOCK, start=D25, end=D25)) == FULL_BARS
    assert stored.get_minute_bars(STOCK, start=D24, end=D24).empty


def test_an_oserror_after_the_day_was_removed_is_a_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """지우기 뒤의 ``OSError`` 도 그 칸만 거부다 — 그 날이 비었다는 것까지 줄에 적는다."""
    full = _rows(STOCK, D24, FULL_BARS)
    root = tmp_path / "cp3-sessions"
    store = _session_store(root, "stock-r1-20261126", asset_class="stock")
    store.append_minute_bars(full)
    store.append_minute_bars(_rows(STOCK, D25, FULL_BARS))

    data_root = _data_root(tmp_path)
    ParquetMarketDataStore(root=data_root, asset_class="stock").append_minute_bars(
        _pick(full, 0, 1)
    )

    original = ParquetMarketDataStore._append_bars

    def flaky(self: Any, timeframe: str, rows: Any) -> int:
        if D24 in set(rows["datetime"].dt.date):
            raise OSError(28, "합성 디스크 꽉 찼다")
        return int(original(self, timeframe, rows))

    monkeypatch.setattr(ParquetMarketDataStore, "_append_bars", flaky)

    text, code = ing.run(sessions_root=root, data_root=data_root, write=True)
    assert code == 2
    assert f"{ing.REFUSED_PREFIX}{ing.STORE_ERROR}" in text
    assert "합성 디스크 꽉 찼다" in text
    assert "기존 2 봉이 있던 그 날 디렉터리는 쓰기 전에 이미 지워졌다" in text
    assert text.startswith("분봉 수집 (write)")
    assert f"합계: {ing.ACTION_WRITE} 1 · " in text

    stored = ParquetMarketDataStore(root=data_root, asset_class="stock")
    assert len(stored.get_minute_bars(STOCK, start=D25, end=D25)) == FULL_BARS
    assert stored.get_minute_bars(STOCK, start=D24, end=D24).empty


def test_a_corrupt_existing_day_refuses_only_that_key(tmp_path: Path) -> None:
    """기존 저장소의 깨진 part 파일은 그 코드만 거부한다 — 다른 코드는 계속 쓴다."""
    root = tmp_path / "cp3-sessions"
    store = _session_store(root, "stock-r1-20261126", asset_class="stock")
    store.append_minute_bars(_rows(STOCK, D25, FULL_BARS))
    store.append_minute_bars(_rows(OTHER, D25, FULL_BARS, base=50.0))

    data_root = _data_root(tmp_path)
    ParquetMarketDataStore(root=data_root, asset_class="stock").append_minute_bars(
        _rows(STOCK, D25, 4)
    )
    corrupt = _day_dir(data_root, STOCK, D25)
    (corrupt / "part-x.parquet").write_bytes(CORRUPT_PART)
    before = _listing(corrupt)

    text, code = ing.run(
        sessions_root=root, data_root=data_root, write=True, as_json=True
    )
    assert code == 2
    assert _actions(text) == {
        (STOCK, D25.isoformat()): f"{ing.REFUSED_PREFIX}{ing.READ_ERROR}",
        (OTHER, D25.isoformat()): ing.ACTION_WRITE,
    }
    assert _listing(corrupt) == before
    stored = ParquetMarketDataStore(root=data_root, asset_class="stock")
    assert len(stored.get_minute_bars(OTHER, start=D25, end=D25)) == FULL_BARS


def test_a_corrupt_session_copy_refuses_the_whole_run(tmp_path: Path) -> None:
    """세션 사본이 깨졌으면 그 경로를 이름 불러 거부한다 — 트레이스백이 아니다."""
    root = tmp_path / "cp3-sessions"
    market = root / "stock-r1-20261126" / "producer" / "market"
    _session_store(root, "stock-r1-20261126", asset_class="stock").append_minute_bars(
        _rows(STOCK, D25, FULL_BARS)
    )
    (_day_dir(market, STOCK, D25) / "part-x.parquet").write_bytes(CORRUPT_PART)

    data_root = _data_root(tmp_path)
    with pytest.raises(ing.IngestRefusal) as refusal:
        ing.run(sessions_root=root, data_root=data_root, write=True)
    assert f"code={STOCK}" in str(refusal.value)

    assert (
        ing.main(
            [
                "--sessions-root",
                str(root),
                "--data-root",
                str(data_root),
                "--write",
            ]
        )
        == 2
    )


def test_replay_can_load_the_ingested_day(sessions: Path, tmp_path: Path) -> None:
    """모은 뒤에는 리플레이의 로더가 그 날을 밀도 게이트 아래로 버리지 않는다."""
    data_root = _data_root(tmp_path)
    _text, code = ing.run(sessions_root=sessions, data_root=data_root, write=True)
    assert code == 0

    frame, loaded = load_bars(
        data_root,
        asset_class="stock",
        symbol=STOCK,
        start=D25,
        end=D25,
        min_bars_per_day=DEFAULT_MIN_BARS_PER_DAY,
    )
    assert loaded == FULL_BARS
    assert len(frame) == FULL_BARS
    assert sorted({stamp.date() for stamp in frame["timestamp"]}) == [D25]
