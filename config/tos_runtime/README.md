# config/tos_runtime/

Approved TOS runtime deployment values (not examples). Each file here is a
real value an operator has signed off on for a named environment
(`paper/`, later `live/`), distinct from the unapproved templates under
`tos/runtime/config/*.example.yaml`.

Every file here carries a header comment naming its approval provenance
(which plan/decision approved the value, and the date) — never add a value
here without that citation; an un-cited value belongs in an `.example.yaml`
until it is actually approved.

Everything else the runtime needs to boot (`time.yaml`, `authority.yaml`,
`risk.yaml`, safety-mesh policy documents, `release.yaml`, …) stays an
`.example.yaml` under `tos/runtime/config/` until the operator approves its
own value the same way `calendar.yaml` was approved here.

This directory is consumed today by the compose e2e test suite
(`tos/runtime/tests/compose/test_deploy_config.py`) **and, as of the TOS
`run` 구동 아크 wave (main `ae3c967c`), by the CLI's `run` entrypoint itself.**
`run` now actually composes and drives: `cli.py`'s `main()` dispatches to
`_run_dispatch.dispatch_run` (`compose/cli.py:801-802`), which loads
`construction.yaml` from `--config-dir` fail-closed, calls
`compose_paper_runtime` with it, refuses with a non-zero exit when
`composed.marketfeed is None` (no tick source wired), and otherwise drives
`composed.marketfeed.run_forever` until `SIGINT`/`SIGTERM` stops it
(`compose/_run_dispatch.py`). **That is the code path, not a deployment** —
composing still needs every approved value this directory exists to hold.

**W1 lane D inventory (2026-09-17,
`docs/plans/2026-09-17-tos-deployment-instance-inventory.md`, measured
against main `ae3c967c`)** measured the full gap between "6 files approved
here" and "`run` actually boots a deployment": `compose_paper_runtime` reads
exactly 30 fixed config-dir file names (plus the `strategies/` directory),
of which these 6 are approved and 24 exist only as
`tos/runtime/config/*.example.yaml`. Of those 24 unapproved names, 19
actually block boot (the loader is called unconditionally and raises on a
missing file) and 5 are genuine opt-in features that boot cleanly without
them at the `compose_paper_runtime` level (`strategy_bindings.yaml`,
`marketfeed.yaml` + `critical_input_policy.yaml` together, `nontrade.yaml`,
`kis_mock_transport.yaml` — the last only matters for `--transport
kis-mock`, not the default synthetic transport). Two of those five —
`marketfeed.yaml` + `critical_input_policy.yaml` — are opt-in at the
`compose_paper_runtime` level but de facto required to run `run` at all,
since `dispatch_run` itself refuses when they leave `composed.marketfeed`
`None`. A 31st name, `construction.yaml`, sits outside
`compose_paper_runtime`'s own 30 (that function takes `construction` as a
caller-supplied argument, never loading a file for it itself) but is
required by the `run` CLI specifically, and — like the other 24 — exists
only as an all-`null` example, with no approved instance in this directory
yet. The inventory's per-file table names, for every file, its loader
(function + file:line), whether it blocks boot or is optional at which
layer (with the file:line proving it), and what KIND of decision its value
needs (measured value / operator policy judgment / derived digest /
external approval document) — never inventing the value itself. Two more
names (`backtest_calibration.yaml`, `evidence_retention.yaml`) ship an
example file but have zero call sites anywhere under `compose/*.py` — they
are orphaned relative to boot, not blocking and not optional-features
either. Read that document before authoring any new `.yaml` here — it is
the current, measured map of what still blocks a real boot, and it records
which main commit it was measured against so a reader knows what it does
and does not cover (e.g. it says nothing about `kis_quote.yaml`/
`kis_witness.yaml` from concurrent unmerged lanes).

Two more governed files belong here once the operator adopts their values
(TOS venue constraint service plan, `docs/plans/2026-09-15-tos-venue-constraint-service-plan.md`
§6 ②, and spec decision `tos-spec/src/decision-records/DR-0002-*.md` §2.1):
`venue_constraint_policy.yaml` and `order_construction_policy.yaml`. Each is an
INSTANCE of the corresponding tos-spec template
(`tos-spec/src/part-1-foundation/verification/VENUE-CONSTRAINT-POLICY-template.yaml`,
`ORDER-CONSTRUCTION-POLICY-template.yaml`) — every template key present,
`status: ISSUED`, kernel-typed content under `_model_view`, runtime-only facts
under `_runtime` — and is active only when `safety_activation.yaml`'s `members:`
list names its exact `policy_id`/`policy_generation`/`canonical_digest`
(`tos-runtime print-policy-digests --config-dir <dir>` prints those digests;
the operator copies them by hand, the same way `release.yaml` digests are
filled). A numeric shape bound with no source stays `null` — never an
invented value — and the runtime then sends nothing: a null `max_quantity`
already denies at step 2 (incomplete venue quantity constraint) and a null
price band makes the kernel's order-shape admissibility `UNKNOWN`. The adopted
`paper/` instances (2026-09-16, plan §6 ②) ship exactly so, with
`scope.accounts`/`scope.instruments` left `TBD` for the operator to fill
(the loader refuses `TBD`); `tos/runtime/tests/compose/test_deploy_policies.py`
pins both the refusal and the fail-closed boot.

The risk state service wave (`docs/plans/2026-09-16-tos-risk-state-service-plan.md`,
DR-0003) adds three more governed files the compose root loads the same way:
`aggregate_risk_policy.yaml` and `action_flow_policy.yaml` (INSTANCES of
`AGGREGATE-RISK-POLICY-template.yaml` / `ACTION-FLOW-POLICY-template.yaml`,
activated through `safety_activation.yaml` `members:` of kinds
`AGGREGATE_RISK_POLICY` / `ACTION_FLOW_POLICY`; `print-policy-digests` prints
all four policy digests) and `risk.yaml` (the Adverse Scenario Set and the
action amplification envelope). All three were adopted by the operator on
2026-09-16 (plan §6 ②) and live under `paper/` with `account_scope` /
`instrument_scope` left `TBD` for the operator to fill (both loaders refuse
`TBD`); `tos/runtime/tests/compose/test_deploy_risk_policies.py` pins the
values and the fail-closed boot. A paper boot without the two policy files is
refused unless the caller injects its own providers (a test seam only). The
Hard Safety Envelope this deployment boots with must govern the policy's
dimension (`INSTRUMENT::LONG_SHORT_DELTA_DIRECTIONAL`, `envelope_max ≥ 1`) —
no paper `safety_envelope.yaml` is committed yet. Step 7 (action flow) can
GRANT since the action-flow observation wave
(`docs/plans/2026-09-16-tos-action-flow-observation-plan.md`): both
amplification axes are observed from durable evidence (kernel `DUPLICATE`
result dispositions; recovery-marker episodes, with the under-count limit
disclosed as `replays_definition`).
