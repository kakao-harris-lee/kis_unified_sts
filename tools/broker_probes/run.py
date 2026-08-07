"""CLI entrypoint for the KIS broker-capability probes.

    python -m tools.broker_probes.run --list
    python -m tools.broker_probes.run P-5 --symbol 101S6000 --confirm
    python -m tools.broker_probes.run --coverage

Every probe writes a JSON artifact under ``tools/broker_probes/results/``
(gitignored). See ``docs/runbooks/kis-capability-probes.md`` for the execution
order, preconditions, and how a result becomes an INSTANCE field value.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.broker_probes.common import (  # noqa: E402
    ENV_REAL,
    ProbeError,
    SafetyViolation,
    add_common_args,
    resolve_out_dir,
)
from tools.broker_probes.registry import PROBES, coverage_report, get  # noqa: E402

_ARG_ADDERS = {
    "tools.broker_probes.probes_order": "add_order_args",
    "tools.broker_probes.probes_auth": "add_auth_args",
    "tools.broker_probes.probes_query": "add_query_args",
    "tools.broker_probes.probes_real": "add_real_args",
    "tools.broker_probes.probes_balance": "add_balance_args",
    "tools.broker_probes.probes_real_order": "add_real_order_args",
}


def _print_table() -> None:
    header = f"{'ID':<7} {'KIND':<16} {'ENV':<10} {'RISK':<7} {'ORDER':<6} {'CONFIRM':<8} TITLE"
    print(header)
    print("-" * len(header))
    for spec in PROBES.values():
        mark = "n/a" if not spec.supported else ("yes" if spec.emits_orders else "no")
        print(
            f"{spec.probe_id:<7} {spec.kind:<16} {spec.environment:<10} "
            f"{spec.risk:<7} {mark:<6} {'yes' if spec.requires_confirm else 'no':<8} {spec.title}"
        )
    # These two lines were true of every probe until P-R5 existed. They are now
    # stated with the exception spelled out rather than left as a comforting
    # blanket claim: a reader who trusts the old wording would believe no probe
    # here can touch a real account.
    real_order_emitting = sorted(
        spec.probe_id
        for spec in PROBES.values()
        if spec.emits_orders and spec.environment == ENV_REAL
    )
    print(
        "\nORDER=yes probes are 모의투자-only and refuse to run without --confirm,\n"
        f"EXCEPT {', '.join(real_order_emitting) or '(none)'} — REAL MONEY. "
        "Every other REAL_PROD probe is\nread-only by construction (GET + allowlist)."
    )


def main(argv: list[str] | None = None) -> int:
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("probe_id", nargs="?", default=None)
    pre.add_argument("--list", action="store_true")
    pre.add_argument("--coverage", action="store_true")
    known, _rest = pre.parse_known_args(argv)

    if known.list or (not known.probe_id and not known.coverage):
        _print_table()
        return 0
    if known.coverage:
        print(json.dumps(coverage_report(), indent=2, ensure_ascii=False))
        return 0

    try:
        spec = get(known.probe_id)
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if not spec.supported:
        print(f"{spec.probe_id} is not a runnable script.\n\n  {spec.skip_reason}\n")
        return 0

    parser = argparse.ArgumentParser(
        prog=f"python -m tools.broker_probes.run {spec.probe_id}",
        description=f"{spec.title}\n\nsource: {spec.source}\nrisk: {spec.risk}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("probe_id", help=argparse.SUPPRESS)
    parser.add_argument("--list", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--coverage", action="store_true", help=argparse.SUPPRESS)
    add_common_args(parser)

    module_name, func_name = spec.entrypoint.split(":")
    module = importlib.import_module(module_name)
    adder = _ARG_ADDERS.get(module_name)
    if adder:
        getattr(module, adder)(parser)
    args = parser.parse_args(argv)

    print(f"\n=== {spec.probe_id} — {spec.title}")
    print(f"    source     : {spec.source}")
    print(
        f"    environment: {spec.environment}    risk: {spec.risk}    "
        f"emits_orders: {spec.emits_orders}"
    )
    if spec.bounds_keys:
        print(f"    feeds bounds: {', '.join(spec.bounds_keys)}")
    if spec.instance_fields:
        print(f"    INSTANCE    : {', '.join(spec.instance_fields)}")
    for item in spec.prerequisites:
        print(f"    prereq     : {item}")
    print()

    func = getattr(module, func_name)
    # Bound the salvage window to this call, so a run recovered on the failure path
    # below is provably one this probe built rather than a leftover from anything
    # earlier in the process.
    from tools.broker_probes.common import ProbeRun

    ProbeRun.reset_salvage()
    try:
        run = func(args)
    except SafetyViolation as exc:
        # Never write an artifact for a refused call: there is nothing to record
        # except the refusal, and an artifact would imply an observation happened.
        print(f"\nSAFETY VIOLATION — refused: {exc}", file=sys.stderr)
        return 3
    except ProbeError as exc:
        print(f"\nPRECONDITION NOT MET: {exc}", file=sys.stderr)
        return 4
    except Exception as exc:  # noqa: BLE001
        # A failed run is still evidence — a probe that could not complete must
        # leave a trace, otherwise a silent failure looks like "not yet run".
        #
        # The trace has to be the run the probe was actually building. Rebuilding a
        # blank one drops the credentials, observations and measurements already
        # collected, which is how the four N-15-20260729T06* artifacts ended up as
        # an exception string and nothing else — no account fingerprint, no record
        # of which token cache was in use, no partial timeline.
        failed = ProbeRun.salvage(spec.probe_id) or ProbeRun(
            probe_id=spec.probe_id,
            title=spec.title,
            mode="live" if getattr(args, "confirm", False) else "dry-run",
            environment=spec.environment,
            args=vars(args),
        )
        failed.error(f"{type(exc).__name__}: {exc}")
        failed.write(spec, resolve_out_dir(args))
        print(f"\nPROBE FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 5

    run.write(spec, resolve_out_dir(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
