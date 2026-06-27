"""Research market-data CLI commands."""

import sys
from pathlib import Path

import click


@click.group("data")
def data_cmd():
    """Research market-data export and validation commands.

    \b
    Examples:
        sts data validate-parquet --root data/market
    """
    pass


def _resolve_parquet_export_root(out: str, *, asset: str, timeframe: str) -> Path:
    """Accept either data/market or data/market/<asset>/<timeframe>."""
    path = Path(out)
    if path.name == timeframe and path.parent.name == asset:
        return path.parent.parent
    return path


@data_cmd.command("validate-parquet")
@click.option(
    "--root", default=None, help="Parquet dataset root (default: storage config)"
)
@click.option(
    "--allow-empty",
    is_flag=True,
    help="Return success even when the dataset has no parquet files",
)
def data_validate_parquet(root: str | None, allow_empty: bool):
    """Validate the configured Parquet/DuckDB market-data dataset."""
    from shared.storage import ParquetMarketDataStore, StorageConfig

    if root is None:
        root = StorageConfig.load_or_default().market_data.parquet.root

    store = ParquetMarketDataStore(root)
    manifest = store.dataset_manifest()
    files = int(manifest.get("parquet_files", 0) or 0)
    rows = int(manifest.get("row_count", 0) or 0)

    click.echo(f"Parquet root: {manifest.get('root', root)}")
    click.echo(f"Files: {files}")
    click.echo(f"Rows: {rows}")
    if manifest.get("min_datetime") or manifest.get("max_datetime"):
        click.echo(
            f"Range: {manifest.get('min_datetime')} -> {manifest.get('max_datetime')}"
        )

    if files == 0 and not allow_empty:
        click.echo("Error: no parquet files found", err=True)
        sys.exit(1)
