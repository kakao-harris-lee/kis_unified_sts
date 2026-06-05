"""Phase4ExecutionConfig — wires PR #133/#135 sub-threshold YAML debt.

Closes the carried-forward notes:
  - PR #132 note: ``FillLogger`` defaults not YAML-wired (now wired via Phase4ExecutionConfig.final_stream_maxlen).
  - PR #133 note: ``DEFAULT_EOD_TIME = dt_time(15, 10)`` and
    ``PassiveMaker.timeout_seconds=30`` not in ``config/execution.yaml``.
  - PR #135 sub-threshold: same.

Loaded from ``config/execution.yaml`` under the ``phase4_execution`` section.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from shared.config.base import ServiceConfigBase


class Phase4ExecutionConfig(ServiceConfigBase):
    _default_config_file: ClassVar[str] = "execution.yaml"
    _default_section: ClassVar[str] = "phase4_execution"

    passive_timeout_seconds: int = Field(default=30, gt=0)
    eod_kst_hour: int = Field(default=15, ge=0, le=23)
    eod_kst_minute: int = Field(default=10, ge=0, le=59)
    base_quantity: int = Field(default=1, ge=1)
    final_stream_maxlen: int = Field(default=10_000, ge=100)
    xread_block_ms: int = Field(default=2000, ge=0)
    xread_batch_size: int = Field(default=10, ge=1)
