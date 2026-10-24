"""Builds the standing session approval source (:mod:`tos_runtime.authority.standing`) from
facts the composition root already owns — split out of ``root.py`` for the size budget.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from tos_runtime.authority.standing import StandingApprovalSource
from tos_runtime.brokercap import is_mock_order_class

__all__ = ["build_standing_approval"]


def build_standing_approval(
    boot: Any,
    construction_stage: Any,
    *,
    trading_date_reader: Callable[[], str | None],
    custody_root: Path,
    environment_label: str,
    uid: int,
) -> StandingApprovalSource:
    """The standing source for this compose root, bound (and evidenced) at boot when the
    artifact is already present.

    The MOCK gate closes over the boot-resolved active scope and INSTANCE document — the
    same two objects the gateway's item-6 skip is fed — and is re-evaluated on every call.
    """
    scope = boot.broker_scopes.active_scope
    instance = boot.instance_document
    source = StandingApprovalSource(
        custody_root,
        environment_label=environment_label,
        code_digest=boot.identity.code_digest or "",
        uid=uid,
        mock_class=lambda: is_mock_order_class(scope, instance),
        trading_date_reader=trading_date_reader,
        construction_reader=lambda: construction_stage.construction,
        rcl_log=boot.rcl.rcl_log,
        writer_epoch=boot.rcl.writer_epoch,
        evidence=boot.infra.evidence_store,
    )
    source.bind_at_boot()
    return source
