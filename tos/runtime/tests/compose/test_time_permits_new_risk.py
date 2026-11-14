"""``tos_runtime.compose._wiring._time_permits_new_risk`` tests (re-review"""

from __future__ import annotations

from typing import NoReturn

import pytest
from tos_runtime.compose._wiring import _time_permits_new_risk
from tos_runtime.time.service import TimeServiceNotStarted

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


class _NotStartedTimeService:
    """Duck-typed double: only ``current_snapshot`` is called by"""

    def current_snapshot(self) -> NoReturn:
        raise TimeServiceNotStarted("no TimeHealthSnapshot has been evaluated yet")


class _BrokenTimeService:
    """A double whose ``current_snapshot`` raises an UNRELATED programming"""

    def current_snapshot(self) -> NoReturn:
        raise ValueError("injected unrelated error")


def test_not_started_service_yields_false() -> None:
    gate = _time_permits_new_risk(_NotStartedTimeService())
    assert gate() is False


def test_an_unrelated_exception_propagates_rather_than_returning_false() -> None:
    gate = _time_permits_new_risk(_BrokenTimeService())
    with pytest.raises(ValueError):
        gate()
