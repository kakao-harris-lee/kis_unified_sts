"""``tos_runtime.compose._run_dispatch`` — the ``run`` subcommand's own dispatch, split out of"""

from __future__ import annotations

import signal
import sys
from collections.abc import Callable
from typing import TYPE_CHECKING

from tos_runtime.compose._broker_posttrade_wiring import close_fill_observer
from tos_runtime.compose._construction_config import (
    CONSTRUCTION_CONFIG_NAME,
    ConstructionConfigError,
    load_construction_config,
)
from tos_runtime.compose._marketfeed_wiring import MARKETFEED_CONFIG_NAME
from tos_runtime.compose.root import compose_paper_runtime
from tos_runtime.marketfeed.policy import CRITICAL_INPUT_POLICY_CONFIG_NAME

if TYPE_CHECKING:
    from tos_runtime.compose.cli import Args

__all__ = ["dispatch_run", "install_run_stop_signal_handlers"]


def install_run_stop_signal_handlers() -> tuple[Callable[[], bool], Callable[[], None]]:
    """Install ``SIGINT``/``SIGTERM`` handlers for :func:`dispatch_run`'s own loop (plan §2"""
    stop_requested = False

    def _stop() -> bool:
        return stop_requested

    def _handle_stop_signal(signum: int, frame: object | None) -> None:
        nonlocal stop_requested
        stop_requested = True

    previous_handlers = [
        (sig, signal.getsignal(sig)) for sig in (signal.SIGINT, signal.SIGTERM)
    ]
    for sig, _ in previous_handlers:
        signal.signal(sig, _handle_stop_signal)

    def _restore() -> None:
        if stop_requested:
            return
        for sig, handler in previous_handlers:
            signal.signal(sig, handler)

    return _stop, _restore


def dispatch_run(args: Args) -> int:
    """The ``run`` subcommand's own dispatch (TOS ``run`` 구동 아크 plan §2 decisions 2/3, §4 W1"""
    construction_path = args.config_dir / CONSTRUCTION_CONFIG_NAME
    try:
        construction = load_construction_config(construction_path)
    except ConstructionConfigError as exc:
        print(f"run: refused — {exc}", file=sys.stderr)
        return 1

    try:
        composed = compose_paper_runtime(
            args.config_dir,
            args.data_dir,
            args.custody_root,
            args.environment_label,
            construction=construction,
            transport_kind=args.transport,
            projection_path=args.projection_path,
            backup_root=args.backup_root,
        )
    except (
        Exception
    ) as exc:  # noqa: BLE001 - see docstring: no common exception base exists
        print(
            f"run: refused — compose_paper_runtime raised {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    if composed.marketfeed is None:
        print(
            "run: refused — composed.marketfeed is None: no tick source is wired. Both "
            f"{MARKETFEED_CONFIG_NAME!r} and {CRITICAL_INPUT_POLICY_CONFIG_NAME!r} must exist "
            "under --config-dir for tos_runtime.compose._marketfeed_wiring.build_tick_scheduler "
            "to build one. A composed runtime with no tick source has nothing for `run` to "
            "drive (plan §2 decision 3) — refusing rather than returning 0 and idling.",
            file=sys.stderr,
        )
        return 1

    stop, restore = install_run_stop_signal_handlers()
    try:
        composed.marketfeed.run_forever(stop=stop)
    finally:
        restore()
        close_fill_observer(composed)
    print("run: stopped (signal received).")
    return 0
