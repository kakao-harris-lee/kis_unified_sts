"""Market-structure store tests (hermetic, tmp_path-based)."""

import json
from datetime import UTC, date, datetime, time

import pandas as pd
import pytest

DAY_1 = date(2026, 7, 1)
DAY_2 = date(2026, 7, 2)
DAY_3 = date(2026, 7, 3)


def _store(tmp_path):
    from shared.storage import ParquetMarketStructureStore

    return ParquetMarketStructureStore(tmp_path / "market")


def _row(**overrides):
    row = {
        "asof_ts": datetime(2026, 7, 1, 18, 40),
        "coverage_ratio": 1.0,
        "fut_foreign_net_qty": -1250,
        "fut_close": 380.5,
        "basis_dev": -0.35,
        "usdkrw": 1391.5,
    }
    row.update(overrides)
    return row


def test_replace_day_and_read_range_roundtrip(tmp_path):
    store = _store(tmp_path)

    written = store.replace_day(
        DAY_1,
        "premarket",
        _row(asof_ts=datetime(2026, 7, 1, 8, 0)),
    )

    assert written == 1

    df = store.read_range(DAY_1, DAY_1)

    assert len(df) == 1
    record = df.iloc[0]
    assert record["trade_date"] == DAY_1
    assert record["snapshot"] == "premarket"
    assert pd.Timestamp(record["asof_ts"]) == pd.Timestamp("2026-07-01 08:00:00")
    assert bool(record["finalized"]) is False
    assert int(record["schema_version"]) == 1
    assert record["fut_foreign_net_qty"] == -1250
    assert record["fut_close"] == 380.5
    assert record["usdkrw"] == 1391.5


def test_replace_day_is_idempotent_per_snapshot(tmp_path):
    store = _store(tmp_path)

    store.replace_day(DAY_1, "close", _row(fut_foreign_net_qty=-100))
    store.replace_day(DAY_1, "close", _row(fut_foreign_net_qty=-200))

    day_dir = (
        tmp_path
        / "market"
        / "market_structure"
        / "daily"
        / "year=2026"
        / "day=2026-07-01"
    )
    assert len(list(day_dir.glob("*.parquet"))) == 1

    df = store.read_range(DAY_1, DAY_1)

    assert len(df) == 1
    assert df.iloc[0]["fut_foreign_net_qty"] == -200
    assert bool(df.iloc[0]["finalized"]) is True


def test_premarket_and_close_snapshots_are_separate(tmp_path):
    store = _store(tmp_path)

    store.replace_day(
        DAY_1,
        "premarket",
        _row(asof_ts=datetime(2026, 7, 1, 8, 0), usdkrw=1388.0),
    )
    store.replace_day(DAY_1, "close", _row(usdkrw=1391.5))
    # Replacing close again must leave the premarket row untouched.
    store.replace_day(DAY_1, "close", _row(usdkrw=1393.0))

    day_dir = store.dataset_dir / "year=2026" / "day=2026-07-01"
    assert len(list(day_dir.glob("*.parquet"))) == 2

    premarket = store.read_range(DAY_1, DAY_1, snapshot="premarket")
    close = store.read_range(DAY_1, DAY_1, snapshot="close")
    both = store.read_range(DAY_1, DAY_1)

    assert len(premarket) == 1
    assert premarket.iloc[0]["usdkrw"] == 1388.0
    assert len(close) == 1
    assert close.iloc[0]["usdkrw"] == 1393.0
    assert list(both["snapshot"]) == ["close", "premarket"]


def test_read_range_unions_unknown_extra_columns(tmp_path):
    store = _store(tmp_path)

    store.replace_day(DAY_1, "close", _row())
    store.replace_day(DAY_2, "close", _row(new_component=42.5))

    df = store.read_range(DAY_1, DAY_2)

    assert len(df) == 2
    assert "new_component" in df.columns
    by_day = df.set_index("trade_date")
    assert pd.isna(by_day.loc[DAY_1, "new_component"])
    assert by_day.loc[DAY_2, "new_component"] == 42.5


def test_read_range_filters_by_trade_date(tmp_path):
    store = _store(tmp_path)

    for day in (DAY_1, DAY_2, DAY_3):
        store.replace_day(day, "close", _row())

    assert list(store.read_range(DAY_2, DAY_2)["trade_date"]) == [DAY_2]
    assert list(store.read_range(start=DAY_2)["trade_date"]) == [DAY_2, DAY_3]
    assert list(store.read_range(end=DAY_1)["trade_date"]) == [DAY_1]
    assert len(store.read_range()) == 3
    assert store.read_range(date(2026, 8, 1), date(2026, 8, 31)).empty


def test_asof_ts_is_normalized_to_naive_kst(tmp_path):
    store = _store(tmp_path)

    # 09:40 UTC == 18:40 KST; tz-aware input must land as naive KST.
    store.replace_day(
        DAY_1,
        "close",
        _row(asof_ts=datetime(2026, 7, 1, 9, 40, tzinfo=UTC)),
    )
    # Naive input is assumed KST and passes through unchanged.
    store.replace_day(DAY_2, "close", _row(asof_ts=datetime(2026, 7, 2, 18, 40)))
    # Missing asof_ts defaults to "now" in naive KST.
    store.replace_day(DAY_3, "close", _row(asof_ts=None))

    df = store.read_range()

    stamps = [pd.Timestamp(value) for value in df["asof_ts"]]
    assert all(stamp.tzinfo is None for stamp in stamps)
    assert stamps[0] == pd.Timestamp("2026-07-01 18:40:00")
    assert stamps[1] == pd.Timestamp("2026-07-02 18:40:00")


def test_read_latest_prefers_finalized_rows(tmp_path):
    store = _store(tmp_path)

    store.replace_day(DAY_1, "close", _row(usdkrw=1391.5))
    store.replace_day(
        DAY_2,
        "premarket",
        _row(asof_ts=datetime(2026, 7, 2, 8, 0), usdkrw=1401.0),
    )

    latest = store.read_latest()
    assert latest is not None
    assert latest["trade_date"] == DAY_1
    assert latest["snapshot"] == "close"
    assert latest["asof_ts"] == datetime(2026, 7, 1, 18, 40)

    provisional = store.read_latest(snapshot="premarket", finalized_only=False)
    assert provisional is not None
    assert provisional["trade_date"] == DAY_2
    assert provisional["usdkrw"] == 1401.0

    assert store.read_latest(snapshot="premarket") is None


def test_read_latest_returns_none_on_empty_dataset(tmp_path):
    store = _store(tmp_path)

    assert store.read_latest() is None
    assert store.read_range().empty


def test_rejects_unknown_snapshot_and_mismatched_rows(tmp_path):
    from shared.storage import MarketStructureStoreError

    store = _store(tmp_path)

    with pytest.raises(MarketStructureStoreError, match="unknown snapshot"):
        store.replace_day(DAY_1, "intraday", _row())

    with pytest.raises(MarketStructureStoreError, match="unknown snapshot"):
        store.read_range(snapshot="intraday")

    with pytest.raises(MarketStructureStoreError, match="trade_date"):
        store.replace_day(DAY_1, "close", _row(trade_date=DAY_2))

    with pytest.raises(MarketStructureStoreError, match="snapshot"):
        store.replace_day(DAY_1, "close", _row(snapshot="premarket"))


def test_partition_layout_matches_convention(tmp_path):
    store = _store(tmp_path)

    store.replace_day(DAY_1, "close", _row())

    files = list((tmp_path / "market").rglob("*.parquet"))
    assert len(files) == 1
    parts = files[0].relative_to(tmp_path / "market").parts
    assert parts[0] == "market_structure"
    assert parts[1] == "daily"
    assert parts[2] == "year=2026"
    assert parts[3] == "day=2026-07-01"
    assert parts[4].startswith("part-")
    assert parts[4].endswith(".parquet")


def test_structured_values_are_json_encoded(tmp_path):
    store = _store(tmp_path)

    store.replace_day(
        DAY_1,
        "close",
        _row(coverage_ratio=0.875, missing_components=["prog_net_val", "sox_ret"]),
    )

    record = store.read_range(DAY_1, DAY_1).iloc[0]

    assert record["coverage_ratio"] == 0.875
    assert json.loads(record["missing_components"]) == ["prog_net_val", "sox_ret"]


def test_query_helper_exposes_market_structure_view(tmp_path):
    store = _store(tmp_path)

    store.replace_day(DAY_1, "premarket", _row(asof_ts=datetime(2026, 7, 1, 8, 0)))
    store.replace_day(DAY_1, "close", _row())

    df = store.query(
        "SELECT snapshot, count(*) AS n FROM market_structure "
        "GROUP BY snapshot ORDER BY snapshot"
    )

    assert list(df["snapshot"]) == ["close", "premarket"]
    assert list(df["n"]) == [1, 1]


def test_dataset_manifest_reports_trade_date_span(tmp_path):
    store = _store(tmp_path)

    empty_manifest = store.dataset_manifest()
    assert empty_manifest["parquet_files"] == 0
    assert empty_manifest["row_count"] == 0

    store.replace_day(DAY_1, "close", _row())
    store.replace_day(DAY_3, "close", _row())

    manifest = store.dataset_manifest()

    assert manifest["parquet_files"] == 2
    assert manifest["row_count"] == 2
    assert manifest["min_trade_date"] == "2026-07-01"
    assert manifest["max_trade_date"] == "2026-07-03"


def test_market_structure_config_defaults_and_cutoffs():
    from shared.storage import MarketStructureConfig

    config = MarketStructureConfig()

    assert config.storage.subdir == "market_structure/daily"
    assert config.storage.schema_version == 1
    assert config.snapshots.names == ["premarket", "close"]
    assert config.snapshots.finalized == ["close"]
    assert config.snapshots.cutoff_time("close") == time(18, 40)
    assert config.snapshots.cutoff_time("premarket") == time(8, 0)
    assert config.snapshots.cutoff_time("unknown") is None


def test_market_structure_config_matches_repo_yaml():
    from shared.storage import MarketStructureConfig

    config = MarketStructureConfig.from_yaml()

    assert config == MarketStructureConfig()


def test_market_structure_config_rejects_bad_snapshot_settings():
    from shared.storage import MarketStructureConfig

    with pytest.raises(ValueError, match="finalized"):
        MarketStructureConfig(snapshots={"names": ["premarket"], "finalized": ["eod"]})

    with pytest.raises(ValueError, match="HH:MM"):
        MarketStructureConfig(
            snapshots={"names": ["close"], "cutoffs_kst": {"close": "25:99"}}
        )

    with pytest.raises(ValueError, match="unique"):
        MarketStructureConfig(snapshots={"names": ["close", "close"]})


def test_market_structure_config_loads_from_custom_yaml(tmp_path):
    from shared.storage import MarketStructureConfig, ParquetMarketStructureStore

    config_path = tmp_path / "market_structure.yaml"
    config_path.write_text(
        "storage:\n"
        "  subdir: custom/structure\n"
        "  schema_version: 2\n"
        "snapshots:\n"
        "  names: [premarket, close, eod]\n"
        "  finalized: [close, eod]\n"
        "  cutoffs_kst:\n"
        '    eod: "19:30"\n',
        encoding="utf-8",
    )

    config = MarketStructureConfig.from_yaml(str(config_path))

    assert config.storage.subdir == "custom/structure"
    assert config.storage.schema_version == 2
    assert config.snapshots.names == ["premarket", "close", "eod"]

    store = ParquetMarketStructureStore(tmp_path / "market", config=config)
    store.replace_day(DAY_1, "eod", _row())

    record = store.read_range(DAY_1, DAY_1).iloc[0]
    assert record["snapshot"] == "eod"
    assert bool(record["finalized"]) is True
    assert int(record["schema_version"]) == 2
    assert store.dataset_dir == tmp_path / "market" / "custom" / "structure"


def test_create_market_structure_store_uses_storage_config(tmp_path):
    from shared.storage import (
        MarketDataStorageConfig,
        MarketStructureConfig,
        ParquetMarketDataConfig,
        StorageConfig,
        create_market_structure_store,
    )

    root = tmp_path / "market"
    storage_config = StorageConfig(
        market_data=MarketDataStorageConfig(
            source="parquet",
            parquet=ParquetMarketDataConfig(root=str(root)),
        )
    )

    store = create_market_structure_store(
        storage_config,
        config=MarketStructureConfig(),
    )
    store.replace_day(DAY_1, "close", _row())

    df = store.read_range(DAY_1, DAY_1)

    assert store.root == root
    assert len(df) == 1
    assert df.iloc[0]["trade_date"] == DAY_1
