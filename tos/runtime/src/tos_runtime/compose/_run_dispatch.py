"""``tos_runtime.compose._run_dispatch`` — the ``run`` subcommand's own dispatch, split out of
``cli.py`` purely for that module's own size budget (``tools/tos_size_budget.py`` — module
ceiling 1000 lines); no behavioural difference from having this inline there (the SAME "split
purely for size budget" discipline :mod:`~tos_runtime.compose._types`/
:mod:`~tos_runtime.compose._engine_config` already document for themselves).

TOS ``run`` 구동 아크 plan (``docs/plans/2026-09-17-tos-run-boot-and-real-sources-arc-plan.md``)
§2 decisions 2/3, §4 W1 lane B — see ``cli.py``'s own module docstring for the full picture of
what ``run`` does now. ``cli.py`` imports :func:`dispatch_run`/:func:`install_run_stop_signal_handlers`
under their private (``_``-prefixed) names, so this split is invisible to anything outside this
package.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos_runtime.*`` only.
No ``shared.*``.
"""

from __future__ import annotations

import signal
import sys
from collections.abc import Callable
from typing import TYPE_CHECKING

from tos_runtime.compose._construction_config import (
    CONSTRUCTION_CONFIG_NAME,
    ConstructionConfigError,
    load_construction_config,
)
from tos_runtime.compose._marketfeed_wiring import MARKETFEED_CONFIG_NAME
from tos_runtime.compose.root import compose_paper_runtime
from tos_runtime.marketfeed.policy import CRITICAL_INPUT_POLICY_CONFIG_NAME

if TYPE_CHECKING:
    # TYPE_CHECKING-only: `cli.py` imports THIS module, so a top-level import here would be
    # circular. Postponed annotations (module docstring's own `from __future__ import
    # annotations`) mean the string form below is all mypy needs — the SAME pattern
    # `compose/_types.py` already uses for `VenueServiceStage`.
    from tos_runtime.compose.cli import Args

__all__ = ["dispatch_run", "install_run_stop_signal_handlers"]


def install_run_stop_signal_handlers() -> tuple[Callable[[], bool], Callable[[], None]]:
    """Install ``SIGINT``/``SIGTERM`` handlers for :func:`dispatch_run`'s own loop (plan §2
    decision 3: "Install SIGINT/SIGTERM handlers that flip the injected `stop` predicate so the
    loop exits cleanly (do not kill mid-tick)"). Returns ``(stop, restore)`` —
    :meth:`~tos_runtime.marketfeed.scheduler.TickScheduler.run_forever` checks ``stop()`` only
    BETWEEN passes (that method's own docstring), so a signal received mid-``tick_once`` still
    lets the in-flight tick finish before the loop exits; ``restore()`` puts back whatever
    handler was previously installed (Python's own default, ordinarily) so a caller — or a test
    driving several ``dispatch_run`` calls in one process — never leaks a stale handler.
    """
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
        for sig, handler in previous_handlers:
            signal.signal(sig, handler)

    return _stop, _restore


def dispatch_run(args: Args) -> int:
    """The ``run`` subcommand's own dispatch (TOS ``run`` 구동 아크 plan §2 decisions 2/3, §4 W1
    lanes A-C — ``cli.py``'s own module docstring has the full picture).

    Loads ``construction.yaml`` (fail-closed), composes the runtime, refuses when no tick
    source is wired, and otherwise drives :meth:`~tos_runtime.marketfeed.scheduler.TickScheduler
    .run_forever` until a ``SIGINT``/``SIGTERM`` requests a stop.

    Returns:
        ``0`` on a clean stop (signal received, loop exited); ``1`` on any refusal — a bad
        ``construction.yaml``, a ``compose_paper_runtime`` refusal (any of its documented
        exceptions — a fail-closed config loader deep in that call names its own file and key),
        or no wired tick source. Every refusal prints why to stderr before returning — this
        function catches broadly around the ``compose_paper_runtime`` call deliberately: that
        one call can raise any of a dozen-plus distinctly-named config/custody/policy loader
        exceptions across this codebase with no common base class (surveyed: none share an
        ancestor narrower than ``Exception``), and the point of this catch is to relay
        WHICHEVER one fired, verbatim, never to guess which subset to enumerate.
    """
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
    print("run: stopped (signal received).")
    return 0
