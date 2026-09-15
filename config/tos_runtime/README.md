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
