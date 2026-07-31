"""Asset-scoped probe token cache — two mock app keys must not share one file.

``shared/kis/auth.py::token_cache_path`` names the token file
``.kis_token_{real|mock}`` with no app-key discrimination, so stock and
futures credentials handed the same cache directory would share one bearer
token. The 2026-07-31 session ran a stock and a futures mock probe in
parallel and escaped only by timing (campaign README, latent-risk register).
``build_auth_config`` is the single construction site for probe auth
configs, and it must scope the directory by asset.
"""

from __future__ import annotations

from pathlib import Path

from tools.broker_probes import common as c


def _creds(asset: str, *, is_real: bool = False) -> c.ProbeCredentials:
    return c.ProbeCredentials(
        app_key=f"key-{asset}",
        app_secret=f"secret-{asset}",
        account_no="1234567890",
        is_real=is_real,
        asset=asset,
    )


def test_stock_and_futures_do_not_share_a_token_file(tmp_path: Path) -> None:
    stock = c.build_auth_config(_creds("stock"), tmp_path)
    futures = c.build_auth_config(_creds("futures"), tmp_path)

    assert stock.token_cache_path != futures.token_cache_path
    assert stock.token_cache_path.parent.name == "stock"
    assert futures.token_cache_path.parent.name == "futures"


def test_real_and_mock_stay_separate_within_an_asset(tmp_path: Path) -> None:
    mock = c.build_auth_config(_creds("futures", is_real=False), tmp_path)
    real = c.build_auth_config(_creds("futures", is_real=True), tmp_path)

    assert mock.token_cache_path.name == ".kis_token_mock"
    assert real.token_cache_path.name == ".kis_token_real"
    assert mock.token_cache_path != real.token_cache_path


def test_scoped_directory_is_created_under_the_requested_base(
    tmp_path: Path,
) -> None:
    c.build_auth_config(_creds("stock"), tmp_path)

    assert (tmp_path / "stock").is_dir()
