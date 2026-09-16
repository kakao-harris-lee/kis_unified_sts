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
(`tos/runtime/tests/compose/test_deploy_config.py`) and, once later waves
give `run` a real `ConstructionConfig`/risk-input/tick-source path (plan
§2.7 — `run` is currently blocked, see `cli.py`'s module docstring), by the
CLI's `run` entrypoint itself.

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
action amplification envelope). None of the three has an adopted value yet —
the proposal table is plan §6 ② — so no `paper/` instance exists for them and
a paper boot without them is refused unless the caller injects its own
providers (a test seam only). Even with them adopted, step 7 (action flow)
cannot GRANT today: the runtime has no durable per-root-cause duplicate /
replay counter (plan §7), so that decision stays `UNKNOWN` until an inbox
schema change lands.
