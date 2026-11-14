"""``tos_runtime.compose`` — the ONE composition root (design #40 D1.1;"""

from __future__ import annotations

from tos_runtime.compose.root import (
    ComposedRuntime,
    ConstructionConfig,
    ReleaseAdmissionRefused,
    compose_paper_runtime,
)

__all__ = [
    "ComposedRuntime",
    "ConstructionConfig",
    "ReleaseAdmissionRefused",
    "compose_paper_runtime",
]
