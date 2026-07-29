"""Machine-readable probe register — the single source for the runbook table.

Sources of the probe set (canonical, 12 + 4 = 16):

* **12 canonical** — ``docs/plans/2026-07-29-tos-broker-capability-profile-kis-draft.md``
  §5 "측정 프로시저 제안" table (:225-238): P-1, P-2, P-5, P-5b, P-8, P-11,
  P-13, P-14, P-15, P-16, P-EXT, P-FQP.
* **4 census additions** — ``docs/plans/2026-07-29-tos-phase0-p02-execution-plan.md``
  §1 T2 (:34-38): N-15, N-16, N-17, N-18.

``bounds_keys`` cite ``tos-spec/src/part-1-foundation/verification/VERIFICATION-PROFILE-002.yaml``
key names verified by direct read (line numbers in :data:`BOUND_KEYS`).
``instance_fields`` cite paths in
``docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml`` as enumerated
in the draft memo §3.1 / §5.

Nothing here invents a value. A probe that cannot run in 모의투자 declares
``supported=False`` with the file:line evidence for *why*.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tools.broker_probes.common import ENV_MOCK, ENV_NONE, ENV_REAL

_VP = "tos-spec/src/part-1-foundation/verification/VERIFICATION-PROFILE-002.yaml"


@dataclass(frozen=True)
class BoundKey:
    """A Verification-Profile bound key a probe can supply evidence for."""

    key: str
    vp_line: int
    current_value: str
    semantics: str
    failure_response: str
    measurement_source: str
    owned_by_broker_profile: bool
    note: str = ""


#: The broker-related Verification-Profile keys enumerated in design #10
#: ``docs/plans/2026-07-25-tos-broker-capability-design.md`` :1168-1171 (the
#: "broker bounds 10키" of the P0-2 execution plan §1 T2 — 10 bullets, 11
#: distinct keys because ``B_external_activity_detect``/``_contain`` share one
#: bullet). Values/lines read directly from VERIFICATION-PROFILE-002.yaml.
BOUND_KEYS: dict[str, BoundKey] = {
    "B_external_activity_detect": BoundKey(
        "B_external_activity_detect",
        221,
        "null",
        "hard_maximum",
        "CONTAIN",
        "broker_capability_profile",
        True,
        "MEASURE. Poll-only broker => bounded by poll cadence (VP-002:222,225).",
    ),
    "B_external_activity_contain": BoundKey(
        "B_external_activity_contain",
        230,
        "1000",
        "hard_maximum",
        "CONTAIN",
        "reconciliation_log",
        False,
        "Our-side containment; already APPROVED. A probe can only falsify "
        "feasibility (detect+contain must fit inside the envelope), not set it.",
    ),
    "B_broker_query_consistency": BoundKey(
        "B_broker_query_consistency",
        752,
        "null",
        "broker_specific",
        "CONSERVATIVE_UNKNOWN",
        "broker_capability_profile",
        True,
        "'absence within it is not proof of non-existence' (VP-002:756).",
    ),
    "B_final_quantity_proof": BoundKey(
        "B_final_quantity_proof",
        716,
        "null",
        "broker_specific",
        "QUARANTINE_UNKNOWN",
        "broker_capability_profile",
        True,
        "Drives how long capacity stays RELEASE_PENDING_PROOF (VP-002:720).",
    ),
    "B_late_fill_observation": BoundKey(
        "B_late_fill_observation",
        725,
        "null",
        "broker_specific",
        "PROFILE_CONTRADICTORY",
        "broker_capability_profile",
        True,
        "Max credible interval for a late fill after a claimed terminal state "
        "(VP-002:729).",
    ),
    "B_rate_limit_recovery": BoundKey(
        "B_rate_limit_recovery",
        761,
        "null",
        "broker_specific",
        "RESTRICT_OR_CONTAIN",
        "broker_capability_profile",
        True,
        "Per broker, account, session and endpoint class (VP-002:762,765).",
    ),
    "B_protective_request_complete": BoundKey(
        "B_protective_request_complete",
        743,
        "null",
        "broker_specific",
        "CONTAIN",
        "broker_capability_profile",
        True,
        "Broker-dependent completion time for a protective action (VP-002:747).",
    ),
    "B_startup_reconciliation": BoundKey(
        "B_startup_reconciliation",
        239,
        "60000",
        "operational_target_and_hard_gate",
        "REMAIN_HALTED",
        "recovery_coordinator_log",
        False,
        "Our-side target, already APPROVED. Probes inform feasibility only.",
    ),
    "B_capability_claim_to_send": BoundKey(
        "B_capability_claim_to_send",
        194,
        "500",
        "hard_maximum",
        "QUARANTINE_UNKNOWN",
        "egress_journal_and_broker_transport_trace",
        False,
        "Egress-owned; not measurable from a broker probe.",
    ),
    "B_egress_hard_fence": BoundKey(
        "B_egress_hard_fence",
        203,
        "1000",
        "hard_maximum",
        "HALT",
        "egress_identity_route_session_and_broker_denial_log",
        False,
        "Egress-owned. A credential/session probe supplies only the broker-denial "
        "half of the evidence.",
    ),
    "B_venue_constraint_loss_detect": BoundKey(
        "B_venue_constraint_loss_detect",
        293,
        "2000",
        "source_specific_hard_maximum",
        "STOP_NEW_RISK",
        "venue_constraint_source_and_generation_trace",
        False,
        "Already APPROVED; broker-capability loss is one of its sources.",
    ),
}

#: Broker-touching keys OUTSIDE the design #10 ten-bullet enumeration. Listed so
#: the runbook does not silently over-claim coverage.
ADJACENT_BOUND_KEYS: dict[str, BoundKey] = {
    "B_protection_gap": BoundKey(
        "B_protection_gap",
        788,
        "null",
        "broker_specific",
        "CONTAIN",
        "protective_replacement_and_broker_log",
        False,
        "ADR-002-011 replacement; partially informed by P-8.",
    ),
    "B_protection_overlap": BoundKey(
        "B_protection_overlap",
        797,
        "null",
        "broker_specific",
        "CONTAIN",
        "protective_replacement_and_broker_log",
        False,
        "ADR-002-011 replacement; partially informed by P-8.",
    ),
    "B_non_trade_event_detect": BoundKey(
        "B_non_trade_event_detect",
        815,
        "null",
        "source_and_broker_specific",
        "CONTAIN",
        "reference_source_and_broker_capability_profile",
        True,
        "ADR-002-010. Corporate-action surface is absent from the repo "
        "(draft memo §3.1 row 12: grep 0 hits) — no probe defined.",
    ),
    "B_non_trade_reconcile": BoundKey(
        "B_non_trade_reconcile",
        833,
        "null",
        "source_and_broker_specific",
        "QUARANTINE_UNKNOWN",
        "reconciliation_and_broker_capability_profile",
        True,
        "ADR-002-010. Same gap as B_non_trade_event_detect.",
    ),
    "B_post_trade_effect_to_obligation_commit": BoundKey(
        "B_post_trade_effect_to_obligation_commit",
        662,
        "500",
        "hard_maximum",
        "STOP_NEW_RISK_AND_QUARANTINE_CAPACITY",
        "broker_effect_ptol_commit_and_rcl_capacity_trace",
        False,
        "Already APPROVED; our-side commit path.",
    ),
}


@dataclass(frozen=True)
class ProbeSpec:
    """Everything the runbook table and the CLI need to know about one probe."""

    probe_id: str
    title: str
    source: str
    kind: str  # ORDER | QUERY | AUTH | SESSION | MANUAL | SPEC_CROSSCHECK | REAL_READ_ONLY
    environment: str
    dimension: str
    bounds_keys: tuple[str, ...]
    instance_fields: tuple[str, ...]
    statistic: str
    risk: str  # LOW | MEDIUM | HIGH
    duration: str
    emits_orders: bool = False
    requires_confirm: bool = False
    supported: bool = True
    skip_reason: str = ""
    prerequisites: tuple[str, ...] = field(default_factory=tuple)
    entrypoint: str = ""  # "module:function"

    @property
    def command(self) -> str:
        flag = " --confirm" if self.requires_confirm else ""
        return f"python -m tools.broker_probes.run {self.probe_id}{flag}"


_S = ProbeSpec

PROBES: dict[str, ProbeSpec] = {
    # ---------------- canonical 12 (draft §5:225-238) ----------------
    "P-1": _S(
        probe_id="P-1",
        title="ORDER_IDENTITY — client-supplied order id field存否",
        source="draft §5:228",
        kind="SPEC_CROSSCHECK",
        environment=ENV_NONE,
        dimension="ORDER_IDENTITY",
        bounds_keys=(),
        instance_fields=("capabilities.client_generated_order_id.status",),
        statistic="categorical (UNSUPPORTED vs VERIFIED); no numeric bound",
        risk="LOW",
        duration="~0 (offline)",
        prerequisites=(
            "none — records code-observed request shape; authority is N-17",
        ),
        entrypoint="tools.broker_probes.probes_query:probe_p1",
    ),
    "P-2": _S(
        probe_id="P-2",
        title="SUBMISSION_IDEMPOTENCY — duplicate-body dedup window",
        source="draft §5:227",
        kind="ORDER",
        environment=ENV_MOCK,
        dimension="SUBMISSION_IDEMPOTENCY",
        bounds_keys=(),
        instance_fields=(
            "capabilities.submission_idempotency.status",
            "capabilities.submission_idempotency.deduplication_window_ms",
        ),
        statistic=(
            "2 ODNOs => no dedup (UNSUPPORTED, window undefined). 1 ODNO => "
            "bisect the send gap; report the LARGEST gap that still deduped as a "
            "lower bound and the smallest that did not as an upper bound."
        ),
        risk="HIGH",
        duration="~5 min",
        emits_orders=True,
        requires_confirm=True,
        prerequisites=(
            "모의투자 session open",
            "non-marketable limit price (--price-offset-pct) so nothing fills",
        ),
        entrypoint="tools.broker_probes.probes_order:probe_p2",
    ),
    "P-5": _S(
        probe_id="P-5",
        title="OPEN_ORDER_QUERY — accept→visible convergence latency",
        source="draft §5:229",
        kind="ORDER",
        environment=ENV_MOCK,
        dimension="OPEN_ORDER_QUERY",
        bounds_keys=("B_broker_query_consistency",),
        instance_fields=(
            "capabilities.open_order_query.eventual_consistency_bound_ms",
            "capabilities.open_order_query.status",
        ),
        statistic="hard maximum: ceil(max(t1-t0) x (1+margin)); N>=100 recommended",
        risk="HIGH",
        duration="~20 min at N=100",
        emits_orders=True,
        requires_confirm=True,
        prerequisites=(
            "모의투자 session open",
            "futures account (inquire-ccnl is futures-only)",
        ),
        entrypoint="tools.broker_probes.probes_order:probe_p5",
    ),
    "P-5b": _S(
        probe_id="P-5b",
        title="OPEN_ORDER_QUERY — continuation-key pagination behaviour",
        source="draft §5:230",
        kind="QUERY",
        environment=ENV_MOCK,
        dimension="OPEN_ORDER_QUERY",
        bounds_keys=("B_broker_query_consistency",),
        instance_fields=(
            "capabilities.open_order_query.completeness",
            "capabilities.open_order_query.pagination",
        ),
        statistic="categorical: page size, whether tr_cont/NK200 advances,完全性",
        risk="LOW",
        duration="~2 min",
        requires_confirm=True,
        prerequisites=(
            "enough historical orders in the query window to exceed one page "
            "(run after P-5); read-only otherwise",
            "--confirm gates broker contact for every networked probe, including "
            "read-only ones",
        ),
        entrypoint="tools.broker_probes.probes_order:probe_p5b",
    ),
    "P-8": _S(
        probe_id="P-8",
        title="REPLACE_OR_AMEND — RVSE_CNCL_DVSN_CD=01 semantics",
        source="draft §5:231",
        kind="ORDER",
        environment=ENV_MOCK,
        dimension="REPLACE_OR_AMEND",
        bounds_keys=("B_protective_request_complete",),
        instance_fields=(
            "capabilities.replace_semantics.mode",
            "capabilities.replace_semantics.status",
        ),
        statistic=(
            "categorical (ReplaceSemantics 5-value) + hard maximum on the "
            "old/new coexistence interval"
        ),
        risk="HIGH",
        duration="~10 min",
        emits_orders=True,
        requires_confirm=True,
        prerequisites=(
            "모의투자 session open",
            "P-5 first (needs a working inquire path to observe the ODNO pair)",
        ),
        entrypoint="tools.broker_probes.probes_order:probe_p8",
    ),
    "P-11": _S(
        probe_id="P-11",
        title="POSITIONS_BALANCES_MARGIN — fill→balance reflection lag",
        source="draft §5:236",
        kind="ORDER",
        environment=ENV_MOCK,
        dimension="POSITIONS_BALANCES_MARGIN",
        bounds_keys=("B_broker_query_consistency", "B_startup_reconciliation"),
        instance_fields=("capabilities.position_balance_margin.consistency_model",),
        statistic="hard maximum of (balance reflects fill) - (fill observed)",
        risk="HIGH",
        duration="~15 min",
        emits_orders=True,
        requires_confirm=True,
        prerequisites=(
            "an intentional FILL is required — pass --allow-fill explicitly",
            "STOCK asset only on mock: futures balance is unsupported on 모의 "
            "(shared/kis/client.py:1030-1032)",
        ),
        entrypoint="tools.broker_probes.probes_order:probe_p11",
    ),
    "P-13": _S(
        probe_id="P-13",
        title="RATE_LIMITS — stepwise ramp to first throttle + recovery time",
        source="draft §5:232",
        kind="QUERY",
        environment=ENV_MOCK,
        dimension="RATE_LIMITS",
        bounds_keys=("B_rate_limit_recovery",),
        instance_fields=(
            "capabilities.rate_limits.hard_limits",
            "capabilities.rate_limits.scope",
            "capabilities.rate_limits.sustained_and_burst_semantics",
        ),
        statistic=(
            "first-throttle rate = HIGHEST step sustained without a limit signal "
            "(a lower bound on the broker limit, never an exact quota). Recovery "
            "= max over repeats of (first success after throttle) - (throttle), "
            "then + margin."
        ),
        risk="MEDIUM",
        duration="~10 min",
        requires_confirm=True,
        prerequisites=(
            "paper trading stopped (the probe consumes the shared account quota)",
            "read-only endpoint class by default; submit/cancel classes need --confirm and are HIGH risk",
        ),
        entrypoint="tools.broker_probes.probes_auth:probe_p13",
    ),
    "P-14": _S(
        probe_id="P-14",
        title="SESSION_CONNECTION_MODEL — concurrent sessions + subscription cap",
        source="draft §5:233",
        kind="SESSION",
        environment=ENV_MOCK,
        dimension="SESSION_CONNECTION_MODEL",
        bounds_keys=(),
        instance_fields=(
            "capabilities.sessions.concurrent_sessions",
            "capabilities.sessions.subscription_limit",
        ),
        statistic=(
            "integer cap = highest count accepted; report the first rejected "
            "count and whether the rejection displaced an existing session"
        ),
        risk="HIGH",
        duration="~10 min",
        requires_confirm=True,
        prerequisites=(
            "all streaming workers stopped — the probe can displace live WS sessions",
            "Q-SESS-3 (draft §5:177): repeated reconnects can trigger a KIS account block; "
            "the probe stops at the first rejection and does not retry",
        ),
        entrypoint="tools.broker_probes.probes_auth:probe_p14",
    ),
    "P-15": _S(
        probe_id="P-15",
        title="CREDENTIALS_AUTHORIZATION — token reissue inside the 1-minute limit",
        source="draft §5:234",
        kind="AUTH",
        environment=ENV_MOCK,
        dimension="CREDENTIALS_AUTHORIZATION",
        bounds_keys=("B_egress_hard_fence",),
        instance_fields=(
            "capabilities.credentials_and_revocation.reissue_rejection_semantics",
        ),
        statistic="categorical: rejection HTTP status + msg_cd + msg1, verbatim",
        risk="HIGH",
        duration="~3 min",
        requires_confirm=True,
        prerequisites=(
            "paper trading stopped — a reissue can invalidate the token in use",
            "probe-private token cache (default) so the runtime cache file survives",
        ),
        entrypoint="tools.broker_probes.probes_auth:probe_p15",
    ),
    "P-16": _S(
        probe_id="P-16",
        title="BROKER_TIME — broker clock vs local KST skew",
        source="draft §5:235",
        kind="QUERY",
        environment=ENV_MOCK,
        dimension="BROKER_TIME",
        bounds_keys=(),
        instance_fields=(
            "capabilities.broker_time.timezone",
            "capabilities.broker_time.precision",
            "capabilities.broker_time.skew_bound_ms",
        ),
        statistic=(
            "signed skew: report max |skew| + margin as the bound and keep the "
            "sign distribution (a one-sided skew is a different hazard)"
        ),
        risk="LOW",
        duration="~5 min",
        requires_confirm=True,
        prerequisites=(
            "read-only quotations calls only",
            "--confirm gates broker contact for every networked probe, including "
            "read-only ones",
        ),
        entrypoint="tools.broker_probes.probes_query:probe_p16",
    ),
    "P-EXT": _S(
        probe_id="P-EXT",
        title="external_activity — manual HTS/MTS order detection latency",
        source="draft §5:237",
        kind="MANUAL",
        environment=ENV_MOCK,
        dimension="POSITIONS_BALANCES_MARGIN",
        bounds_keys=("B_external_activity_detect", "B_external_activity_contain"),
        instance_fields=(
            "external_activity.detection_bound_ms",
            "external_activity.containment_bound_ms",
        ),
        statistic=(
            "hard maximum of (first poll that observes the manual order) - "
            "(operator-recorded submit time). Bound is dominated by the poll "
            "interval, so record the interval alongside the value."
        ),
        risk="MEDIUM",
        duration="~15 min per trial, operator in the loop",
        requires_confirm=True,
        prerequisites=(
            "operator manually submits an order on HTS/MTS for the SAME 모의 account",
            "operator records the submit timestamp when the probe prompts",
        ),
        entrypoint="tools.broker_probes.probes_order:probe_pext",
    ),
    "P-FQP": _S(
        probe_id="P-FQP",
        title="final_quantity_proof — post-cancel late-event window",
        source="draft §5:238",
        kind="ORDER",
        environment=ENV_MOCK,
        dimension="CANCELLATION",
        bounds_keys=("B_final_quantity_proof", "B_late_fill_observation"),
        instance_fields=(
            "final_quantity_proof.recipes[]",
            "final_quantity_proof.late_event_window_ms",
        ),
        statistic=(
            "B_final_quantity_proof = hard maximum time to reach "
            "(final filled qty + zero remaining). B_late_fill_observation = hard "
            "maximum of any post-terminal quantity change observed across trials; "
            "if zero changes are observed the value is NOT 0 — it is 'not "
            "established', because absence is not proof (VP-002:756)."
        ),
        risk="HIGH",
        duration="~20 min",
        emits_orders=True,
        requires_confirm=True,
        prerequisites=("모의투자 session open", "run after P-5"),
        entrypoint="tools.broker_probes.probes_order:probe_pfqp",
    ),
    # ---------------- census additions 4 (plan §1 T2:34-38) ----------------
    "N-15": _S(
        probe_id="N-15",
        title="Token 1-minute reissue limit x invalidate→retry token blackout",
        source="plan §1 T2:35",
        kind="AUTH",
        environment=ENV_MOCK,
        dimension="CREDENTIALS_AUTHORIZATION",
        bounds_keys=("B_egress_hard_fence",),
        instance_fields=(
            "capabilities.credentials_and_revocation.token_blackout_window_ms",
            "capabilities.credentials_and_revocation.reissue_rejection_semantics",
        ),
        statistic=(
            "hard maximum blackout = max over trials of (first successful "
            "reissue) - (invalidate). Report the observed rejection code verbatim; "
            "a blackout shorter than the 1-minute documented limit means the "
            "limiter is not the binding constraint."
        ),
        risk="HIGH",
        duration="~5 min per trial (each trial burns a >=60s wait)",
        requires_confirm=True,
        prerequisites=(
            "ALL workers using this app key stopped — the app key is shared and "
            "the reissue limit is per app key",
            "combines with P-15; run them back to back",
        ),
        entrypoint="tools.broker_probes.probes_auth:probe_n15",
    ),
    "N-16": _S(
        probe_id="N-16",
        title="CTFN6118R night futures balance — response schema capture",
        source="plan §1 T2:36",
        kind="REAL_READ_ONLY",
        environment=ENV_REAL,
        dimension="POSITIONS_BALANCES_MARGIN",
        bounds_keys=(),
        instance_fields=("capabilities.position_balance_margin.schema_captured",),
        statistic="schema only: sorted key list of output1/output2 + rt_cd/msg_cd",
        risk="MEDIUM",
        duration="1 call",
        requires_confirm=True,
        prerequisites=(
            "REAL token (mock has no futures balance at all — "
            "shared/kis/client.py:1030-1032)",
            "night session window 18:00-05:00 KST (config/market_schedule.yaml:29-33)",
            "operator approval for a real-credential call; READ-ONLY, no order",
            "the follow-on config/kis/tr_ids.yaml edit is a SEPARATE commit",
        ),
        entrypoint="tools.broker_probes.probes_real:probe_n16",
    ),
    "N-17": _S(
        probe_id="N-17",
        title="Spec cross-check — order request fields / TIF values / RVSE_CNCL_DVSN_CD set",
        source="plan §1 T2:37",
        kind="SPEC_CROSSCHECK",
        environment=ENV_NONE,
        dimension="MARKET_INSTRUMENT_CONSTRAINTS",
        bounds_keys=(),
        instance_fields=(
            "capabilities.client_generated_order_id.status",
            "capabilities.command_construction_and_wire_semantics.field_inventory",
            "live_scope.time_in_force_values",
            "capabilities.replace_semantics.value_set",
        ),
        statistic="categorical; documentary cross-check, no measurement",
        risk="LOW",
        duration="~1 h desk work",
        supported=False,
        skip_reason=(
            "N-17 is a documentary cross-check, not a script. The instrument "
            "(kis-code-assistant-mcp vs manual official-doc reading) is operator "
            "decision D6 (plan §1 T3:49-50). Use the checklist in "
            "docs/runbooks/kis-capability-probes.md §7."
        ),
        entrypoint="",
    ),
    "N-18": _S(
        probe_id="N-18",
        title="REAL-token read-only trio (program-trade row cap / SOX notation / night code)",
        source="plan §1 T2:38",
        kind="REAL_READ_ONLY",
        environment=ENV_REAL,
        dimension="MARKET_INSTRUMENT_CONSTRAINTS",
        bounds_keys=(),
        instance_fields=(
            "capabilities.market_and_instrument_constraints.instrument_coverage",
        ),
        statistic="categorical: per-call row cap (integer), symbol notation, error text verbatim",
        risk="MEDIUM",
        duration="3 calls",
        requires_confirm=True,
        prerequisites=(
            "REAL futures token (these TRs are real-only — roadmap :340-341)",
            "READ-ONLY, enforced by allowlist; no order path exists in the module",
            "prior art: scripts/analysis/phase0_kis_probes.py (same 3 calls, no "
            "JSON evidence artifact) — left untouched",
        ),
        entrypoint="tools.broker_probes.probes_real:probe_n18",
    ),
}


def get(probe_id: str) -> ProbeSpec:
    key = probe_id.strip().upper().replace("_", "-")
    for candidate, spec in PROBES.items():
        if candidate.upper() == key:
            return spec
    raise KeyError(f"unknown probe {probe_id!r}. Known: {', '.join(sorted(PROBES))}")


def coverage_report() -> dict[str, object]:
    """Prove the 12 canonical + 4 census probes are all represented."""
    canonical = [p for p in PROBES.values() if p.source.startswith("draft")]
    census = [p for p in PROBES.values() if p.source.startswith("plan")]
    covered = {key for spec in PROBES.values() for key in spec.bounds_keys}
    return {
        "canonical_12": sorted(p.probe_id for p in canonical),
        "canonical_count": len(canonical),
        "census_4": sorted(p.probe_id for p in census),
        "census_count": len(census),
        "total": len(PROBES),
        "bound_keys_touched": sorted(covered),
        "bound_keys_not_touched": sorted(set(BOUND_KEYS) - covered),
        "order_emitting": sorted(p.probe_id for p in PROBES.values() if p.emits_orders),
        "unsupported": {
            p.probe_id: p.skip_reason for p in PROBES.values() if not p.supported
        },
    }
