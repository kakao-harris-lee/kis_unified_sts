"""``tos_runtime.compose._pending_dimensions`` unit tests (Phase 5 W3-b).

Covers the "leftover key" boot-refusal idiom (module docstring
``_READER_OWNED_DIMENSION_KEYS``, mirrored from
``tos_runtime.compose._egress_attestations``'s own ``_RETIRED_DERIVED_KEYS``):
once a dimension gets a real ``CurrentnessAssembler.dimension_readers`` entry
(Phase 5 plan §2 decision 3), a ``currentness_dimensions.yaml`` config that
still carries a block for it must refuse to load — a stale config must never
silently pretend to attest a value this runtime now derives on its own.

No pending-dimension-loader test file existed before Phase 5 W3-b (survey
``scratchpad/w3-survey.md`` §8: "pending-dimension 전용 테스트 파일은 없음").
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from tos.cur import DimensionKey
from tos_runtime.compose._pending_dimensions import (
    PENDING_DIMENSION_KEYS,
    PendingDimensionConfigError,
    load_pending_currentness_dimensions,
)


def _valid_block() -> dict:
    return {
        "bound_generation": 1,
        "bound_digest": "digest",
        "restrictive_floor": 0,
        "positively_established": True,
    }


def _write_full_config(path: Path, *, extra: dict | None = None) -> None:
    """Every :data:`PENDING_DIMENSION_KEYS` block filled in, plus any
    ``extra`` top-level keys the caller wants to additionally exercise
    (e.g. a retired/reader-owned key that should now be refused)."""
    content = {key.value: _valid_block() for key in PENDING_DIMENSION_KEYS}
    if extra:
        content.update(extra)
    path.write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")


def test_a_fully_valued_config_loads_one_spec_per_pending_key(tmp_path: Path) -> None:
    path = tmp_path / "currentness_dimensions.yaml"
    _write_full_config(path)
    specs = load_pending_currentness_dimensions(path)
    assert tuple(spec.dimension_key for spec in specs) == PENDING_DIMENSION_KEYS


def test_currentness_policy_is_no_longer_pending() -> None:
    """RED until the CURRENTNESS_POLICY currentness dimension reader lands
    (Phase 5 W3-b, "1차원=1커밋") — pinned here so the reader-landing commit
    has an explicit, mechanically-checkable target."""
    assert DimensionKey.CURRENTNESS_POLICY not in PENDING_DIMENSION_KEYS


def test_recovery_is_no_longer_pending() -> None:
    """RED until the RECOVERY currentness dimension reader lands (W1 barrier
    verdict, Phase 5 W3-b "1차원=1커밋")."""
    assert DimensionKey.RECOVERY not in PENDING_DIMENSION_KEYS


def test_trading_approval_is_no_longer_pending() -> None:
    """RED until the TRADING_APPROVAL currentness dimension reader lands
    (step 4's own recorded verdict, Phase 5 W3-b "1차원=1커밋")."""
    assert DimensionKey.TRADING_APPROVAL not in PENDING_DIMENSION_KEYS


def test_environment_scope_is_no_longer_pending() -> None:
    """RED until the ENVIRONMENT_SCOPE currentness dimension reader lands
    (``tos.brokercap.environment_binding_ok`` over the already-computed
    scope/evidence environment labels, Phase 5 W3-b "1차원=1커밋")."""
    assert DimensionKey.ENVIRONMENT_SCOPE not in PENDING_DIMENSION_KEYS


@pytest.mark.parametrize(
    "reader_owned_key",
    [
        DimensionKey.CURRENTNESS_POLICY,
        DimensionKey.RECOVERY,
        DimensionKey.TRADING_APPROVAL,
        DimensionKey.ENVIRONMENT_SCOPE,
    ],
)
def test_a_reader_owned_key_still_present_in_config_refuses_to_load(
    tmp_path: Path, reader_owned_key: DimensionKey
) -> None:
    """Once a dimension is reader-owned, a config that still carries a block
    for it must refuse to load — never silently ignored."""
    path = tmp_path / "currentness_dimensions.yaml"
    _write_full_config(path, extra={reader_owned_key.value: _valid_block()})
    with pytest.raises(PendingDimensionConfigError, match=reader_owned_key.value):
        load_pending_currentness_dimensions(path)
