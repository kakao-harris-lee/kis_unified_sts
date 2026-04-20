import hashlib
from unittest.mock import MagicMock

from scripts.migrations.apply_clickhouse_migrations import (
    MigrationRunner,
)


def test_discover_migrations_orders_by_version(tmp_path):
    (tmp_path / "V2__later.sql").write_text("SELECT 1;")
    (tmp_path / "V1__first.sql").write_text("SELECT 2;")
    (tmp_path / "V10__tenth.sql").write_text("SELECT 3;")

    runner = MigrationRunner(client=MagicMock(), migrations_dir=tmp_path)
    result = runner.discover()

    assert [m.version for m in result] == ["V1", "V2", "V10"]


def test_apply_skips_already_applied(tmp_path):
    (tmp_path / "V1__first.sql").write_text(
        "CREATE TABLE foo (x Int32) ENGINE = MergeTree() ORDER BY x;"
    )
    client = MagicMock()
    # Return V1 as already applied
    client.execute.return_value = [("V1",)]
    runner = MigrationRunner(client=client, migrations_dir=tmp_path)
    applied = runner.apply_all()
    assert applied == []


def test_apply_executes_and_records(tmp_path):
    sql = "CREATE TABLE kospi.foo (x Int32) ENGINE = MergeTree() ORDER BY x;"
    (tmp_path / "V1__first.sql").write_text(sql)
    client = MagicMock()
    client.execute.return_value = []  # nothing applied yet
    runner = MigrationRunner(client=client, migrations_dir=tmp_path)
    applied = runner.apply_all()
    assert applied == ["V1"]

    # Verify execute called with the SQL and then INSERT into schema_migrations
    calls = [c.args[0] for c in client.execute.call_args_list]
    assert any("CREATE TABLE kospi.foo" in c for c in calls)
    assert any("INSERT INTO kospi.schema_migrations" in c for c in calls)


def test_checksum_stable(tmp_path):
    (tmp_path / "V1__first.sql").write_text("SELECT 1;")
    runner = MigrationRunner(client=MagicMock(), migrations_dir=tmp_path)
    migrations = runner.discover()
    expected = hashlib.sha256(b"SELECT 1;").hexdigest()
    assert migrations[0].checksum == expected
