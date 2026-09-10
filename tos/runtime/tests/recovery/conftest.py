"""``tos/runtime/tests/recovery`` — hermetic fixtures for the TOS Phase 5 W1 recovery-barrier
suite.

Reuses the compose end-to-end suite's own config/custody/data fixtures and full-boot recipe
(:mod:`tos.runtime.tests.compose`) rather than re-typing them: this suite tests what happens
AROUND a real :func:`~tos_runtime.compose.root.compose_paper_runtime` boot (the recovery
barrier), not the boot machinery itself, which the compose suite already covers end to end. Also
reuses the lower-level ``inbox``/``evidence_store``/``key_provider`` fixtures from
:mod:`tos.runtime.tests.engine` for the unit-level (non-compose) tests that construct a durable
inbox/evidence store directly, mirroring ``tos/runtime/tests/engine/test_driver.py``'s own
crash-window technique.
"""

from __future__ import annotations

from ..compose import _fixtures as fx  # noqa: F401
from ..compose.conftest import (  # noqa: F401
    config_dir,
    custody_root,
    data_dir,
    write_approval_file,
)
from ..compose.test_compose_root import (  # noqa: F401
    _action_flow_inputs,
    _aggregate_inputs,
    _compose,
    _reach_trusted,
)
from ..engine.conftest import (  # noqa: F401
    SCHEME,
    FixedKeyProvider,
    emergency_log,
    evidence_store,
    inbox,
    key_provider,
    monotonic_source,
)
