"""Hermetic tests for :mod:`tos_runtime.posttrade.config` (TOS Phase 5 W2-R independent-review
finding M2, 2026-09-10).

**Coverage gap this file closes.** Every existing test in this package constructs
:class:`~tos_runtime.posttrade.config.FinalityConfig` directly
(``test_finality.py``/``test_finality_witness.py``/``engine/_fixtures.py``) or writes an
already-filled YAML (``compose/conftest.py``) — nothing ever called
:func:`~tos_runtime.posttrade.config.load_finality_config` on a file carrying
``release_proof_wait_ms: null``/``0``/``true`` before this suite. Mutation (e) — replacing
``_require_positive_int`` with a literal ``60_000`` instead of raising on ``None`` — survived
every one of the 1052 tests in the runtime suite as a result. This file pins the named-TBD-null
refusal (plan §7 item 2's own operator-owned gate) and the type/positivity guards directly.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from tos_runtime.posttrade.config import FinalityConfigError, load_finality_config

_VALID_RAW: dict[str, object] = {
    "currency": "KRW",
    "value_date": "2026-09-09",
    "source_revision": "config-test-rev-1",
    "proof_recipe_id": "config-test-recipe-1",
    "release_proof_wait_ms": 60_000,
}


def _write(path: Path, raw: dict[str, object]) -> Path:
    file_path = path / "finality.yaml"
    file_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return file_path


def test_a_fully_valued_file_loads(tmp_path: Path) -> None:
    config = load_finality_config(_write(tmp_path, _VALID_RAW))
    assert config.release_proof_wait_ms == 60_000


def test_release_proof_wait_ms_null_is_named_tbd_refused(tmp_path: Path) -> None:
    raw = dict(_VALID_RAW, release_proof_wait_ms=None)
    with pytest.raises(FinalityConfigError, match="release_proof_wait_ms"):
        load_finality_config(_write(tmp_path, raw))


def test_release_proof_wait_ms_zero_is_refused(tmp_path: Path) -> None:
    """Zero is not a smaller bound, it is a silently-disabled one — same discipline as every
    other positive-int operator bound in this runtime (mirrors
    ``tos_runtime.compose._engine_wiring._require_positive_int``)."""
    raw = dict(_VALID_RAW, release_proof_wait_ms=0)
    with pytest.raises(FinalityConfigError, match="release_proof_wait_ms"):
        load_finality_config(_write(tmp_path, raw))


def test_release_proof_wait_ms_negative_is_refused(tmp_path: Path) -> None:
    raw = dict(_VALID_RAW, release_proof_wait_ms=-1)
    with pytest.raises(FinalityConfigError, match="release_proof_wait_ms"):
        load_finality_config(_write(tmp_path, raw))


def test_release_proof_wait_ms_bool_is_refused(tmp_path: Path) -> None:
    """``bool`` is an ``int`` subclass in Python -- ``True``/``False`` must not silently pass
    the int-type guard as ``1``/``0``."""
    raw = dict(_VALID_RAW, release_proof_wait_ms=True)
    with pytest.raises(FinalityConfigError, match="release_proof_wait_ms"):
        load_finality_config(_write(tmp_path, raw))


def test_release_proof_wait_ms_missing_key_is_refused(tmp_path: Path) -> None:
    raw = dict(_VALID_RAW)
    del raw["release_proof_wait_ms"]
    with pytest.raises(FinalityConfigError, match="release_proof_wait_ms"):
        load_finality_config(_write(tmp_path, raw))
