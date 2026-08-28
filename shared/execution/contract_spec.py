"""Backward-compatible re-export of the contract-spec registry.

The implementation now lives in the broker-agnostic commons
:mod:`shared.instruments.contract_spec` (see the 2026-07-20 tos boundary /
import-firewall design, §3.4 / F6 REUSE-AFTER-REFACTOR). This thin module keeps
the historical import path ``shared.execution.contract_spec`` working for
existing runtime consumers.
"""

from __future__ import annotations

from shared.instruments.contract_spec import (
    ContractSpec,
    ContractSpecRegistry,
    resolve_contract_spec,
)

__all__ = ["ContractSpec", "ContractSpecRegistry", "resolve_contract_spec"]
