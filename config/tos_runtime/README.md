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
filled). A numeric shape bound with no source stays `null` — the kernel then
returns `UNKNOWN` for order-shape admissibility and nothing is sent — never an
invented value. Until the values are adopted, the only instances are the test
documents under `tos/runtime/tests/venue/_documents.py`.
