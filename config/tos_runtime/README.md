# config/tos_runtime/

Approved TOS runtime deployment values (not examples). Each file here is a
real value an operator has signed off on for a named environment
(`paper/`, later `live/`), distinct from the unapproved templates under
`tos/runtime/config/*.example.yaml`.

Every file here carries a header comment naming its approval provenance
(which plan/decision approved the value, and the date) — never add a value
here without that citation; an un-cited value belongs in an `.example.yaml`
until it is actually approved.

**The `file:line` citations in those headers are a measurement, not a
guarantee.** Every one in the 18 files adopted 2026-09-23 was re-measured
against main `4d6bffc9` at adoption time (the 2026-09-17 inventory's own
numbers had already drifted by 2-18 lines for six loaders). They drift again
whenever the runtime source moves; read the function name next to the number,
and re-measure rather than trusting a stale line.

**Adopted here as of W-A / A-2 (2026-09-23) — 24 files.** The original 6
(`calendar.yaml`, `risk.yaml`, `aggregate_risk_policy.yaml`,
`action_flow_policy.yaml`, `venue_constraint_policy.yaml`,
`order_construction_policy.yaml`) plus the 18 the value proposal
(`docs/plans/2026-09-18-tos-config-value-proposal.md`, approved by the
operator 2026-09-18 and confirmed as-proposed 2026-09-23) supplied values for:

| adopted | files |
| --- | --- |
| 2026-09-12 | `calendar.yaml` |
| 2026-09-16 | `risk.yaml` · `aggregate_risk_policy.yaml` · `action_flow_policy.yaml` · `venue_constraint_policy.yaml` · `order_construction_policy.yaml` |
| 2026-09-23 (W-A / A-2) | `time.yaml` · `authority.yaml` · `release.yaml` · `currentness.yaml` · `currentness_dimensions.yaml` · `risk_attestations.yaml` · `egress_coordinates.yaml` · `broker_scopes.yaml` · `engine.yaml` · `engine_driver.yaml` · `coordinator_preconditions.yaml` · `finality.yaml` · `safety_envelope.yaml` · `safety_profile.yaml` · `safety_activation.yaml` · `safety_deviations.yaml` · `safety_incidents.yaml` · `monitor_coverage.yaml` |

**Adopted is not the same as loadable.** Every one of the 18 carries the
proposal §0 sentence in its own header — *this is a first-boot profile, not
an operational safety posture* — and **two** of them still keep a named-TBD
leaf the proposal's §6 "확인 불가 · 미확정" list refused to invent:

| file | leaf(s) still named-TBD | why |
| --- | --- | --- |
| `finality.yaml` | `value_date` · `source_revision` · `proof_recipe_id` | §6 1·2항 — no recommended value exists (the two that have a prior recommendation are grade **M**, "개발 측 값 제안 없음"; the third, `value_date`, has a grade-B recommendation whose basis is the KRX **stock** settlement date, which does not fit this deployment's `SYNTHETIC_FUTURES_ORDER` scope) |
| `safety_activation.yaml` | `members` | §3 [D] — derived from `print-policy-digests`, which refuses on the 2026-09-16 policies' operator-fill `scope.accounts` |

> **2026-09-23 update (W-A / A-5).** `finality.yaml`'s row shrank to
> `source_revision` alone (the other two were filled — see the boot-proof
> fixture paragraph below). `safety_activation.yaml::members` stays `null`
> here for a second, stronger reason than the one above: the deployment
> coordinates go INTO each `canonical_digest`, so the derived value is
> host-specific and cannot be committed at all. The render script derives it
> into the off-repo copy.

Two more that the first cut of this list counted as named-TBD were **filled
on 2026-09-23** under the operator's "추천 값이 있으면 활용" answer, from the
earlier value table `docs/plans/2026-09-12-tos-operator-value-proposals.md`:
`currentness.yaml::required_dimensions` (§2, the 21-member mandated floor)
and `monitor_coverage.yaml::bounds` (§4, 60000 / `[TRUSTED]` / 100, grade C).

Those two now load cleanly. The two files in the table above
(`finality.yaml`, `safety_activation.yaml`) still refuse, by design;
`tos/runtime/tests/compose/test_deploy_approved_values.py` pins each refusal
**by key name**, so filling one later is a deliberate act — and
`tos/runtime/tests/compose/_loader_probe.py` (runnable directly) prints the
whole PASS/REFUSE partition, which that same test pins by name.

**Boot-proof fixtures adopted 2026-09-23 (W-A / A-5, operator choice (가)** —
`docs/plans/2026-09-23-tos-paper-coordinates-and-first-boot-design.md` §3**).**
The four names this paragraph used to list as "still NOT adopted" now exist
here — `construction.yaml`, `strategies/bootproof_band.strategy.yaml`,
`marketfeed.yaml`, `critical_input_policy.yaml` — but they are **not approved
values**. Each carries, instead of the proposal §0 sentence, the fixture
sentence 「부팅 증명 픽스처 — 거래 전략 아님 · 대칭은 전략 제안 경로 착지 후 ·
운영자 선택 (가) 2026-09-23」. The value proposal tabulates no row for any of
them; they exist only to prove `run` boots and consumes a tick under the
`SYNTHETIC_FUTURES_ORDER` scope (no broker reach, zero real orders), and the
committed direction is LONG **only** because the current design can express
one direction per composition — `scope.action_classes` still authorizes both,
and the SHORT arm is produced by `scripts/tos/render_paper_config.py
--direction SHORT`, never by a second committed copy.

**Deployment coordinates are still never committed here.** The account and
the front-month contract code stay named-TBD in every file that carries them,
and `scripts/tos/render_paper_config.py` byte-copies this directory into an
**off-repo** directory and fills only those slots (design §2; runbook
`docs/runbooks/tos-paper-boot.md`). Every coordinate slot uses the SAME
named-TBD token `"TBD"`, and every one of them is refused by its own loader —
`tos/runtime/tests/compose/test_deploy_approved_values.py` pins each unrendered
slot by that refusal, key name included.

> **Correction (2026-09-24, review-797 HIGH-1).** The first cut of this
> paragraph claimed "the placeholder FORM differs per loader:
> `compose/_marketfeed_wiring.py`'s `_require_str` refuses `null` but **not**
> the string `"TBD"` (measured)". **That was false** — it was read off a
> message string, never measured by loading a file. `_require_str`
> (`_marketfeed_wiring.py:194-204`) calls `reject_named_tbd` at `:200-202`, and
> `_require_instruments` does the same per entry at `:228-232`; re-measured,
> all three marketfeed coordinate slots refuse `null`, `""` **and** `"TBD"`.
> That mechanical block landed in `d2a36d22` ("close the named-TBD bypass class
> mechanically, not by list", W-A A-0 round 2), an ancestor of `main`. Anyone
> who read the old sentence would have concluded that a named-TBD bypass was
> still open in that loader, or that leaving one open elsewhere was acceptable.
> `marketfeed.yaml`'s slots are now `"TBD"` like every other fixture file.

Also filled 2026-09-23: `finality.yaml::value_date` (`T+1`, operator decision 3
— 선물 일일정산, **not** the 2026-09-12 `T+2` whose basis is the KRX *stock*
settlement date) and `finality.yaml::proof_recipe_id` (an opaque boot-proof
token that asserts the ABSENCE of an approved recipe — ADR-002-030 §29 Q3 is
still an open question naming none), plus
`order_construction_policy.yaml`'s `admitted_quantity_bases` (`["RISK"]`, the
deployed strategy file's own basis — the condition sizing proposal §4 ② was
waiting for) and its `DIRECTION` axis (`LONG`). `finality.yaml::source_revision`
stays `null`: it is the deploy SHA, which a commit cannot contain, so the
render writes it.

**Operator decisions of 2026-09-23 closed two of the three blockers** the
first cut recorded. The boot label is **`paper`** (the value the venue/OCP
policies already declare; `critical_input_policy.yaml::environment` now matches
it), and the Hard Safety Envelope governs
`INSTRUMENT::LONG_SHORT_DELTA_DIRECTIONAL` with **`envelope_max = 1` contract**
— the bound `aggregate_risk_policy.yaml:74` had been asking for all along, equal
to that policy's own approved effective limit. `safety_envelope.yaml` and
`safety_profile.yaml` carry it as an **approved safety value**, not a fixture
(the profile must declare it too: `spg/predicates.py:278-283` refuses a profile
that omits an envelope-declared dimension, and `:274-277` refuses an empty
envelope outright — so the previous "both empty" state could not pass either).

**What still blocks a `run` boot (measured 2026-09-24, named in
`docs/runbooks/tos-paper-boot.md` §5):** a canonical digest is **not
reproducible across processes** whenever a covered field is a set —
`covered_content()`'s `model_dump(mode="json", …)` emits set-iteration order and
the canonicalizer treats a sequence as order-significant. Measured over the
kernel: **120** models declare `_COVERED_FIELDS`, **19** carry a set in covered
content, **6 of those already sort** via a `covered_content()` override (the
`cur`/`wdr`/`sir`/`rlp` families — `tos/src/tos/cur/records.py:44-49` states the
reason verbatim), and **13 do not**. `VenueConstraintPolicy` is the only one of
the 13 this deployment digests today, which is why it is the one that breaks the
"run `print-policy-digests`, copy the digests into
`safety_activation.yaml::members`" procedure visibly. ⚠ `CurrentnessPolicy
.required_dimensions` (adopted here since PR #794) *looks* affected by type but
is in the sorting six — measured stable; a static type scan over-reports, the
override is what decides.

This directory is consumed today by the compose e2e test suite
(`tos/runtime/tests/compose/test_deploy_config.py`,
`test_deploy_policies.py`, `test_deploy_risk_policies.py`,
`test_deploy_approved_values.py`) **and, as of the TOS
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
here" and "`run` actually boots a deployment". **Its counts are fixed at that
measurement point and are NOT rewritten by the 2026-09-23 adoption above** —
read "6 approved / 24 example-only / 19 boot-blocking" as the 2026-09-17
state, then apply the adoption table at the top of this file:
`compose_paper_runtime` reads
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
which main commit it was measured against (`ae3c967c`) so a reader knows
what it does and does not cover: `kis_witness.yaml` (W3, PR #726) landed on
main after that measurement point and is not covered, and `kis_quote.yaml`
(W2, PR #727) is still unmerged and is not covered either — neither gets a
row until the whole table is re-measured against a new commit.

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
