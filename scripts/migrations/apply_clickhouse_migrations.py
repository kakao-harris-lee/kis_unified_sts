"""ClickHouse migration runner (idempotent, checksum-tracked)."""

from __future__ import annotations

import argparse
import hashlib
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)

VERSION_RE = re.compile(r"^(V\d+)__.*\.sql$")


class CHClientProtocol(Protocol):
    def execute(self, query: str, *args, **kwargs): ...


@dataclass(frozen=True)
class DiscoveredMigration:
    version: str
    path: Path
    sql: str
    checksum: str


class MigrationRunner:
    """Applies .sql files in order, tracks in kospi.schema_migrations."""

    def __init__(self, client: CHClientProtocol, migrations_dir: Path):
        self.client = client
        self.migrations_dir = Path(migrations_dir)

    def discover(self) -> list[DiscoveredMigration]:
        found: list[DiscoveredMigration] = []
        for p in sorted(self.migrations_dir.glob("V*.sql")):
            m = VERSION_RE.match(p.name)
            if not m:
                continue
            sql = p.read_text(encoding="utf-8")
            cksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
            found.append(
                DiscoveredMigration(version=m.group(1), path=p, sql=sql, checksum=cksum)
            )
        found.sort(key=lambda mig: int(mig.version[1:]))
        return found

    def _ensure_tracking_table(self) -> None:
        self.client.execute(
            "CREATE TABLE IF NOT EXISTS kospi.schema_migrations ("
            " version String, applied_at DateTime DEFAULT now(), checksum String"
            ") ENGINE = MergeTree() ORDER BY version"
        )

    def _already_applied(self) -> set[str]:
        rows = self.client.execute("SELECT version FROM kospi.schema_migrations") or []
        return {r[0] for r in rows}

    def apply_all(self) -> list[str]:
        self._ensure_tracking_table()
        applied_now: list[str] = []
        already = self._already_applied()
        for mig in self.discover():
            if mig.version in already:
                logger.info("skip %s (already applied)", mig.version)
                continue
            logger.info("applying %s (%s)", mig.version, mig.checksum[:8])
            for stmt in _split_sql(mig.sql):
                self.client.execute(stmt)
            self.client.execute(
                "INSERT INTO kospi.schema_migrations (version, checksum) VALUES",
                [(mig.version, mig.checksum)],
            )
            applied_now.append(mig.version)
        return applied_now


def _split_sql(sql: str) -> list[str]:
    """Naive split on `;` at line end. Rejects nested statements (good enough for DDL)."""
    parts = [p.strip() for p in sql.split(";")]
    return [p for p in parts if p]


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--migrations-dir", default="infra/clickhouse/migrations")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    from shared.db.client import get_clickhouse_client
    from shared.db.config import ClickHouseConfig  # type: ignore

    config = ClickHouseConfig.from_env()
    ch_client = get_clickhouse_client(config)
    sync_client = ch_client.get_sync_client()
    runner = MigrationRunner(
        client=sync_client, migrations_dir=Path(args.migrations_dir)
    )
    applied = runner.apply_all()
    print(f"applied: {applied}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
