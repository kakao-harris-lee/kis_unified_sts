"""The per-package import-closure policies the kernel canaries are driven from."""

from __future__ import annotations

from ._closure_policy import (
    BUILTIN,
    CLOCK,
    CLOCK_ATTR,
    ENV,
    ESCAPE,
    NETWORK,
    NETWORK_MODULES,
    NONDET,
    NONDETERMINISTIC_CALLS,
    RNG,
    ClosurePolicy,
    ScanSpec,
    names,
    nameset,
)

_OPS: frozenset[str] = frozenset(
    {
        "shared.execution",
        "shared.kis",
        "shared.streaming",
        "shared.llm",
        "shared.storage",
        "shared.backtest",
        "shared.config",
        "shared.config.secrets",
        "services",
        "cli",
        "numpy",
        "pandas",
    }
)

_OPS_PREFIXES: tuple[str, ...] = (
    "shared.execution.",
    "shared.kis.",
    "shared.streaming.",
    "shared.llm.",
    "shared.storage.",
    "shared.backtest.",
    "shared.config.",
    "services.",
    "cli.",
    "numpy.",
    "pandas.",
)

_DETERMINISM = frozenset({"shared.determinism"})
_DETERMINISM_PREFIX = ("shared.determinism.",)
_YAML = frozenset({"yaml"})
_YAML_PREFIX = ("yaml.",)


def _deny(
    *siblings: str,
    determinism: bool = True,
    yaml: bool = True,
    extra: tuple[str, ...] = (),
    prefix_siblings: tuple[str, ...] = (),
) -> tuple[frozenset[str], tuple[str, ...]]:
    """One package's (exact, prefix) denylist: the operational core plus its forbidden siblings."""
    exact = set(_OPS) | set(siblings) | set(extra)
    prefixes = list(_OPS_PREFIXES)
    if determinism:
        exact |= _DETERMINISM
        prefixes.extend(_DETERMINISM_PREFIX)
    if yaml:
        exact |= _YAML
        prefixes.extend(_YAML_PREFIX)
    prefixes.extend(f"{name}." for name in extra)
    prefixes.extend(f"{name}." for name in (prefix_siblings or siblings))
    return frozenset(exact), tuple(prefixes)


_SIMPLE = ScanSpec(categories=frozenset({ESCAPE, ENV, CLOCK}))
_NO_CLOCK = ScanSpec(categories=frozenset({ESCAPE, ENV}))
_ENV_ONLY = ScanSpec(categories=frozenset({ENV}))
_TIME = ScanSpec(categories=frozenset({ENV, CLOCK, CLOCK_ATTR}))
_CLOCK_AND_RNG = ScanSpec(categories=frozenset({ESCAPE, ENV, CLOCK, RNG}))
_RICH = ScanSpec(
    categories=frozenset({ESCAPE, ENV, CLOCK, RNG, NETWORK, NONDET, BUILTIN}),
    dynamic_calls=frozenset({"exec", "eval", "compile", "__import__"}),
)
_RICH_BACKTEST = ScanSpec(
    categories=_RICH.categories,
    dynamic_calls=_RICH.dynamic_calls,
    nondeterministic_calls=NONDETERMINISTIC_CALLS | {"shuffle", "sample"},
)
_RICH_EGRESSGW = ScanSpec(
    categories=_RICH.categories,
    dynamic_calls=_RICH.dynamic_calls,
    network_modules=NETWORK_MODULES | {"requests", "aiohttp", "httpx"},
)
_STDLIB_EGRESS = ScanSpec(
    categories=frozenset({ESCAPE, ENV, NETWORK}),
    network_modules=nameset(
        "socket ssl http urllib ftplib smtplib poplib imaplib telnetlib "
        "subprocess ctypes"
    ),
)


def _policy(deny, **kwargs) -> ClosurePolicy:
    """Build one policy from a ``_deny`` pair plus its declared facts."""
    exact, prefixes = deny
    return ClosurePolicy(deny_exact=exact, deny_prefixes=prefixes, **kwargs)


POLICIES: dict[str, ClosurePolicy] = {}

POLICIES["afg"] = _policy(
    name="afg",
    child_imports=names(
        "tos.afg tos.afg._base tos.afg.predicates tos.afg.records tos.afg.state "
        "tos.afg.vocabulary"
    ),
    canary_imports=names("tos.afg"),
    planted=names(
        "shared.config numpy tos.protective tos.orthostate tos.ioc tos.iap "
        "tos.some_future_sibling"
    ),
    deny=_deny(),
    allowed_tos=nameset("tos tos.afg tos.canonical tos.ordering tos.rcl"),
    static_scan=True,
    expected_present=names("tos.canonical tos.ordering tos.rcl tos.afg"),
    allowed_canaries=names(
        "tos.afg tos.afg.predicates tos.canonical tos.canonical._base tos.ordering "
        "tos.rcl tos.rcl.vector"
    ),
    src_dirs=names("afg"),
    scan=_SIMPLE,
)

POLICIES["are"] = _policy(
    name="are",
    child_imports=names(
        "tos.are tos.are._base tos.are.predicates tos.are.records tos.are.state "
        "tos.are.vocabulary"
    ),
    canary_imports=names("tos.are"),
    planted=names(
        "shared.config tos.protective tos.spg tos.liveauth tos.authority "
        "tos.orthostate numpy"
    ),
    deny=_deny(
        *names(
            "tos.authority tos.brokercap tos.capsule tos.dsl tos.evidence "
            "tos.liveauth tos.orthostate tos.protective tos.recon tos.spg tos.time"
        ),
    ),
    expected_present=names("tos.canonical tos.ordering tos.rcl"),
    cleared_canaries=names(
        "tos.are tos.are.predicates tos.rcl tos.rcl.vector tos.canonical tos.ordering"
    ),
    src_dirs=names("are"),
    scan=_SIMPLE,
)

POLICIES["authority"] = _policy(
    name="authority",
    child_imports=names(
        "tos.authority tos.authority._base tos.authority.predicates "
        "tos.authority.records tos.authority.state tos.authority.vocabulary "
        "tos.canonical tos.ordering tos.time"
    ),
    canary_imports=names("tos.authority"),
    planted=names("shared.config tos.rcl tos.evidence tos.capsule numpy"),
    deny=_deny(
        *names("tos.capsule tos.evidence tos.rcl"),
    ),
    expected_present=names("tos.canonical tos.ordering tos.time"),
    cleared_canaries=names("tos.authority tos.time tos.canonical tos.ordering"),
    src_dirs=names("authority"),
    scan=_SIMPLE,
)

POLICIES["backtest"] = _policy(
    name="backtest",
    child_imports=names(
        "tos.backtest tos.backtest._base tos.backtest.bars tos.backtest.calibration "
        "tos.backtest.converter tos.backtest.driver tos.backtest.fills "
        "tos.backtest.records tos.backtest.resolver tos.backtest.results "
        "tos.backtest.scenarios tos.backtest.vocabulary"
    ),
    canary_imports=names("tos.backtest"),
    planted=names(
        "shared.backtest shared.execution numpy pandas vectorbt tos.egress "
        "tos.brokercap tos.egressgw tos.future_sibling"
    ),
    deny=_deny(
        extra=("vectorbt",),
    ),
    allowed_tos=nameset(
        "tos tos.afg tos.are tos.backtest tos.canonical tos.capsule tos.cur tos.dsl "
        "tos.engine tos.evidence tos.ioc tos.nontrade tos.ordering tos.orthostate "
        "tos.rcl tos.time tos.venue"
    ),
    static_allowed=nameset(
        "tos tos.backtest tos.canonical tos.capsule tos.dsl tos.engine tos.ordering "
        "tos.rcl tos.time"
    ),
    static_scan=True,
    forbidden_siblings=names(
        "tos.authority tos.brokeradapter tos.brokercap tos.egress tos.egressgw "
        "tos.future_sibling tos.hag tos.iap tos.liveauth tos.posttrade tos.protective "
        "tos.recon tos.sbr tos.sci tos.sir tos.spg tos.stm tos.wdr"
    ),
    expected_present_mode="direct",
    allowed_canaries=names(
        "tos.backtest tos.backtest.driver tos.engine.sequencer tos.canonical"
    ),
    indirect_only=names("tos.are tos.afg tos.ioc tos.venue tos.cur tos.evidence"),
    namespace_forbidden=names(
        "run_commitment_flow run_decision_pipeline ProvisionalReservationLedger "
        "apply_egress_result apply_committed claim_capability compile_command "
        "permit_single_use vector_complete"
    ),
    namespace_all_submodules=True,
    src_dirs=names("backtest"),
    scan=_RICH_BACKTEST,
    suite_dir="backtest",
    submodule_dir="backtest",
    declared_submodules=names(
        "tos.backtest tos.backtest._base tos.backtest.bars tos.backtest.calibration "
        "tos.backtest.converter tos.backtest.driver tos.backtest.fills "
        "tos.backtest.records tos.backtest.resolver tos.backtest.results "
        "tos.backtest.scenarios tos.backtest.vocabulary"
    ),
)

POLICIES["brokeradapter"] = _policy(
    name="brokeradapter",
    child_imports=names(
        "tos.brokeradapter tos.brokeradapter.protocol tos.brokeradapter.synthetic"
    ),
    canary_imports=names("tos.brokeradapter"),
    planted=names("shared.kis numpy tos.egressgw tos.egress tos.future_sibling"),
    deny=_deny(),
    allowed_tos=nameset(
        "tos tos.brokeradapter tos.brokercap tos.canonical tos.engine tos.ordering"
    ),
    static_scan=True,
    forbidden_siblings=names(
        "tos.authority tos.backtest tos.egress tos.egressgw tos.future_sibling "
        "tos.hag tos.iap tos.liveauth tos.posttrade tos.protective tos.recon tos.sbr "
        "tos.sci tos.sir tos.spg tos.stm tos.wdr"
    ),
    allowed_canaries=names(
        "tos.brokeradapter tos.brokeradapter.synthetic tos.engine.records"
    ),
    bounded_by=names("tos.engine"),
    src_dirs=names("brokeradapter"),
    submodule_dir="brokeradapter",
    declared_submodules=names(
        "tos.brokeradapter tos.brokeradapter.protocol tos.brokeradapter.synthetic"
    ),
)

POLICIES["brokercap"] = _policy(
    name="brokercap",
    child_imports=names(
        "tos.brokercap tos.brokercap._base tos.brokercap.predicates "
        "tos.brokercap.records tos.brokercap.routing tos.brokercap.vocabulary"
    ),
    canary_imports=names("tos.brokercap"),
    planted=names("shared.config tos.liveauth tos.orthostate tos.recon numpy"),
    deny=_deny(
        *names(
            "tos.authority tos.capsule tos.dsl tos.evidence tos.liveauth "
            "tos.orthostate tos.rcl tos.recon tos.time"
        ),
    ),
    expected_present=names("tos.canonical tos.ordering"),
    cleared_canaries=names(
        "tos.brokercap tos.brokercap.predicates tos.canonical tos.ordering"
    ),
    src_dirs=names("brokercap"),
    scan=_SIMPLE,
)

POLICIES["capsule"] = _policy(
    name="capsule",
    child_imports=names(
        "tos.capsule tos.capsule.canonicalization tos.capsule.capsule "
        "tos.capsule.consistency_cut tos.capsule.context_generation "
        "tos.capsule.field_evaluation tos.capsule.field_state tos.capsule.lineage "
        "tos.capsule.observation tos.capsule.predicates tos.capsule.snapshot"
    ),
    canary_imports=names("tos.capsule"),
    planted=names("shared.llm numpy"),
    deny=_deny(
        determinism=False,
        yaml=False,
    ),
    cleared_canaries=names("tos.capsule"),
    src_dirs=names("capsule"),
    scan=_ENV_ONLY,
)

POLICIES["cur"] = _policy(
    name="cur",
    child_imports=names(
        "tos.cur tos.cur._base tos.cur.predicates tos.cur.records tos.cur.state "
        "tos.cur.vocabulary"
    ),
    canary_imports=names("tos.cur"),
    planted=names(
        "shared.config numpy tos.egress tos.venue tos.iap tos.capsule tos.sci "
        "tos.future_sibling"
    ),
    deny=_deny(),
    allowed_tos=nameset("tos tos.canonical tos.cur tos.ordering"),
    static_scan=True,
    forbidden_siblings=names(
        "tos.afg tos.are tos.authority tos.brokercap tos.capsule tos.dsl tos.egress "
        "tos.evidence tos.future_sibling tos.hag tos.iap tos.ioc tos.liveauth "
        "tos.nontrade tos.orthostate tos.posttrade tos.protective tos.ptf tos.rcl "
        "tos.recon tos.sbr tos.sci tos.sir tos.spg tos.stm tos.time tos.venue tos.wdr"
    ),
    expected_present=names("tos.canonical tos.ordering tos.cur"),
    allowed_canaries=names(
        "tos.cur tos.cur.predicates tos.canonical tos.canonical._base tos.ordering"
    ),
    namespace_forbidden=names(
        "QuorumCommitCertificate RestrictiveLatchState monotonic_denial_no_revival "
        "egress_currentness_active active_egress_currentness egress_currentness_ok"
    ),
    src_dirs=names("cur"),
    scan=_SIMPLE,
)

POLICIES["dsl"] = _policy(
    name="dsl",
    child_imports=names(
        "tos.dsl tos.dsl._base tos.dsl.admissibility tos.dsl.bounds tos.dsl.candidate "
        "tos.dsl.determinism tos.dsl.evidence tos.dsl.outcome tos.dsl.proposal "
        "tos.dsl.strategy tos.dsl.vocabulary"
    ),
    canary_imports=names("tos.dsl"),
    planted=names("shared.config tos.evidence numpy"),
    deny=_deny(
        *names("tos.evidence"),
        yaml=False,
    ),
    expected_present=names("tos.capsule.capsule"),
    cleared_canaries=names(
        "tos.dsl tos.dsl.evidence tos.capsule tos.capsule.capsule tos.canonical"
    ),
    src_dirs=names("dsl"),
    scan=_NO_CLOCK,
)

POLICIES["egress"] = _policy(
    name="egress",
    child_imports=names(
        "tos.egress tos.egress._base tos.egress.predicates tos.egress.records "
        "tos.egress.state tos.egress.vocabulary"
    ),
    canary_imports=names("tos.egress"),
    planted=names(
        "shared.config numpy tos.rcl tos.ioc tos.evidence tos.capsule tos.nt "
        "tos.future_sibling"
    ),
    deny=_deny(),
    allowed_tos=nameset("tos tos.canonical tos.egress tos.ordering"),
    static_scan=True,
    forbidden_siblings=names(
        "tos.afg tos.are tos.authority tos.brokercap tos.capsule tos.cur tos.dsl "
        "tos.evidence tos.future_sibling tos.hag tos.iap tos.ioc tos.liveauth "
        "tos.nontrade tos.nt tos.orthostate tos.posttrade tos.protective tos.rcl "
        "tos.recon tos.sbr tos.sci tos.sir tos.spg tos.stm tos.time tos.venue tos.wdr"
    ),
    expected_present=names("tos.canonical tos.ordering tos.egress"),
    allowed_canaries=names(
        "tos.egress tos.egress.predicates tos.canonical tos.canonical._base "
        "tos.ordering"
    ),
    namespace_forbidden=names(
        "claim_capability TransmissionCapability writer_fenced "
        "derived_command_conformance mutation_fence_holds EvidenceCommitReceipt "
        "Bindings"
    ),
    src_dirs=names("egress"),
    scan=_SIMPLE,
)

POLICIES["egressgw"] = _policy(
    name="egressgw",
    child_imports=names(
        "tos.egressgw tos.egressgw._base tos.egressgw.construction "
        "tos.egressgw.gateway tos.egressgw.mesh tos.egressgw.records "
        "tos.egressgw.seal tos.egressgw.venuefacts tos.egressgw.vocabulary"
    ),
    canary_imports=names("tos.egressgw"),
    planted=names(
        "shared.config shared.execution numpy tos.brokeradapter tos.spg "
        "tos.future_sibling"
    ),
    deny=_deny(),
    allowed_tos=nameset(
        "tos tos.brokercap tos.canonical tos.cur tos.dsl tos.egress tos.egressgw "
        "tos.engine tos.ioc tos.ordering tos.rcl tos.venue"
    ),
    static_scan=True,
    forbidden_siblings=names(
        "tos.authority tos.backtest tos.brokeradapter tos.future_sibling tos.hag "
        "tos.iap tos.liveauth tos.posttrade tos.protective tos.recon tos.sbr tos.sci "
        "tos.sir tos.spg tos.stm tos.wdr"
    ),
    declared_but_not_taken=nameset("tos.capsule tos.evidence"),
    expected_present=names("tos.egress"),
    allowed_canaries=names(
        "tos.egressgw tos.egressgw.gateway tos.egress.predicates tos.ioc"
    ),
    bounded_by=names("tos.engine"),
    src_dirs=names("egressgw"),
    scan=_RICH_EGRESSGW,
    submodule_dir="egressgw",
    declared_submodules=names(
        "tos.egressgw tos.egressgw._base tos.egressgw.construction "
        "tos.egressgw.gateway tos.egressgw.mesh tos.egressgw.records "
        "tos.egressgw.seal tos.egressgw.venuefacts tos.egressgw.vocabulary"
    ),
    every_edge_is_taken=True,
)

POLICIES["engine"] = _policy(
    name="engine",
    child_imports=names(
        "tos.engine tos.engine._base tos.engine.adapters tos.engine.admission "
        "tos.engine.core tos.engine.orthostate_projection tos.engine.pipeline "
        "tos.engine.records tos.engine.registry tos.engine.sequencer tos.engine.sink "
        "tos.engine.standins tos.engine.state tos.engine.vocabulary"
    ),
    canary_imports=names("tos.engine"),
    planted=names(
        "shared.config shared.execution numpy tos.egress tos.brokercap tos.posttrade "
        "tos.brokeradapter tos.future_sibling"
    ),
    deny=_deny(),
    allowed_tos=nameset(
        "tos tos.afg tos.are tos.canonical tos.capsule tos.cur tos.dsl tos.engine "
        "tos.evidence tos.ioc tos.ordering tos.orthostate tos.rcl tos.time tos.venue"
    ),
    static_scan=True,
    forbidden_siblings=names(
        "tos.authority tos.brokeradapter tos.brokercap tos.egress tos.future_sibling "
        "tos.hag tos.iap tos.liveauth tos.posttrade tos.protective tos.recon tos.sbr "
        "tos.sci tos.sir tos.spg tos.stm tos.wdr"
    ),
    expected_present_mode="allowlist",
    allowed_canaries=names(
        "tos.engine tos.engine.sequencer tos.dsl.determinism tos.canonical"
    ),
    namespace_forbidden=names(
        "apply_committed apply_benefit claim_capability fold_commands compile_command "
        "permit_single_use risk_decision action_flow_decision vector_complete"
    ),
    namespace_all_submodules=True,
    src_dirs=names("engine"),
    scan=_RICH,
    submodule_dir="engine",
    declared_submodules=names(
        "tos.engine tos.engine._base tos.engine.adapters tos.engine.admission "
        "tos.engine.core tos.engine.orthostate_projection tos.engine.pipeline "
        "tos.engine.records tos.engine.registry tos.engine.sequencer tos.engine.sink "
        "tos.engine.standins tos.engine.state tos.engine.vocabulary"
    ),
)

POLICIES["evidence"] = _policy(
    name="evidence",
    child_imports=names(
        "tos.canonical tos.canonical.canonicalization tos.evidence tos.evidence.chain "
        "tos.evidence.elements tos.evidence.envelope tos.evidence.gap "
        "tos.evidence.ledger tos.evidence.policy tos.evidence.predicates "
        "tos.evidence.receipt tos.evidence.replay tos.evidence.retention "
        "tos.evidence.scrub"
    ),
    canary_imports=names("tos.evidence"),
    planted=names("shared.config tos.capsule"),
    deny=_deny(
        *names("tos.capsule"),
        determinism=False,
        yaml=False,
    ),
    cleared_canaries=names("tos.canonical tos.evidence"),
    src_dirs=names("evidence canonical"),
    scan=_ENV_ONLY,
)

POLICIES["iap"] = _policy(
    name="iap",
    child_imports=names(
        "tos.iap tos.iap._base tos.iap.predicates tos.iap.records tos.iap.state "
        "tos.iap.vocabulary"
    ),
    canary_imports=names("tos.iap"),
    planted=names("shared.config tos.rcl tos.dsl tos.orthostate tos.ioc numpy"),
    deny=_deny(
        *names(
            "tos.are tos.authority tos.brokercap tos.capsule tos.dsl tos.evidence "
            "tos.ioc tos.liveauth tos.orthostate tos.protective tos.rcl tos.recon "
            "tos.spg tos.time tos.venue"
        ),
    ),
    expected_present=names("tos.canonical tos.ordering"),
    cleared_canaries=names("tos.iap tos.iap.predicates tos.canonical tos.ordering"),
    src_dirs=names("iap"),
    scan=_SIMPLE,
)

POLICIES["ioc"] = _policy(
    name="ioc",
    child_imports=names(
        "tos.ioc tos.ioc._base tos.ioc.predicates tos.ioc.records tos.ioc.state "
        "tos.ioc.vocabulary"
    ),
    canary_imports=names("tos.ioc"),
    planted=names(
        "shared.config tos.are tos.dsl tos.capsule tos.brokercap tos.orthostate numpy"
    ),
    deny=_deny(
        *names(
            "tos.are tos.authority tos.brokercap tos.capsule tos.dsl tos.evidence "
            "tos.liveauth tos.orthostate tos.protective tos.recon tos.spg tos.time"
        ),
    ),
    expected_present=names("tos.canonical tos.ordering tos.rcl"),
    cleared_canaries=names(
        "tos.ioc tos.ioc.predicates tos.rcl tos.rcl.vector tos.canonical tos.ordering"
    ),
    src_dirs=names("ioc"),
    scan=_SIMPLE,
)

POLICIES["marketfeed"] = _policy(
    name="marketfeed",
    child_imports=names(
        "tos.marketfeed tos.marketfeed._base tos.marketfeed.records "
        "tos.marketfeed.resolver tos.marketfeed.value tos.marketfeed.vocabulary"
    ),
    canary_imports=names("tos.marketfeed"),
    planted=names(
        "shared.config shared.execution numpy tos.egress tos.brokercap tos.backtest "
        "tos.future_sibling"
    ),
    deny=_deny(),
    allowed_tos=nameset(
        "tos tos.afg tos.are tos.canonical tos.capsule tos.cur tos.dsl tos.engine "
        "tos.evidence tos.ioc tos.marketfeed tos.ordering tos.orthostate tos.rcl "
        "tos.time tos.venue"
    ),
    static_scan=True,
    forbidden_siblings=names(
        "tos.authority tos.backtest tos.brokeradapter tos.brokercap tos.egress "
        "tos.egressgw tos.future_sibling tos.hag tos.iap tos.liveauth tos.posttrade "
        "tos.protective tos.recon tos.sbr tos.sci tos.sir tos.spg tos.stm tos.wdr"
    ),
    expected_present_mode="allowlist",
    allowed_canaries=names(
        "tos.marketfeed tos.marketfeed.value tos.dsl.determinism tos.canonical"
    ),
    namespace_forbidden=names(
        "apply_committed claim_capability compile_command permit_single_use "
        "risk_decision action_flow_decision vector_complete send_once"
    ),
    namespace_all_submodules=True,
    src_dirs=names("marketfeed"),
    scan=_RICH,
    submodule_dir="marketfeed",
    declared_submodules=names(
        "tos.marketfeed tos.marketfeed._base tos.marketfeed.records "
        "tos.marketfeed.resolver tos.marketfeed.value tos.marketfeed.vocabulary"
    ),
)

POLICIES["orthostate"] = _policy(
    name="orthostate",
    child_imports=names(
        "tos.orthostate tos.orthostate._base tos.orthostate.predicates "
        "tos.orthostate.records tos.orthostate.state tos.orthostate.vocabulary"
    ),
    canary_imports=names("tos.orthostate"),
    planted=names(
        "shared.config tos.evidence tos.capsule tos.authority tos.liveauth tos.time "
        "numpy"
    ),
    deny=_deny(
        *names("tos.authority tos.capsule tos.dsl tos.evidence tos.liveauth tos.time"),
    ),
    expected_present=names("tos.canonical tos.ordering tos.rcl"),
    cleared_canaries=names(
        "tos.orthostate tos.rcl tos.rcl.predicates tos.canonical tos.ordering"
    ),
    src_dirs=names("orthostate"),
    scan=_SIMPLE,
)

POLICIES["posttrade"] = _policy(
    name="posttrade",
    child_imports=names(
        "tos.posttrade tos.posttrade._base tos.posttrade.predicates "
        "tos.posttrade.records tos.posttrade.vocabulary"
    ),
    canary_imports=names("tos.posttrade"),
    planted=names(
        "tos.capsule tos.evidence tos.time tos.dsl tos.rcl tos.authority tos.liveauth "
        "tos.orthostate tos.recon tos.brokercap tos.spg tos.protective tos.are "
        "tos.ioc tos.iap tos.sbr tos.venue tos.afg tos.hag tos.egress tos.nontrade "
        "tos.cur tos.some_future_sibling shared.config numpy"
    ),
    deny=_deny(),
    allowed_tos=nameset("tos tos.canonical tos.ordering tos.posttrade"),
    static_scan=True,
    forbidden_siblings=names(
        "tos.afg tos.are tos.authority tos.brokercap tos.capsule tos.cur tos.dsl "
        "tos.egress tos.evidence tos.hag tos.iap tos.ioc tos.liveauth tos.nontrade "
        "tos.orthostate tos.protective tos.rcl tos.recon tos.sbr "
        "tos.some_future_sibling tos.spg tos.time tos.venue"
    ),
    expected_present=names("tos.canonical tos.posttrade"),
    allowed_canaries=names(
        "tos.posttrade tos.posttrade.predicates tos.canonical tos.canonical._base "
        "tos.ordering tos.ordering._ordering"
    ),
    src_dirs=names("posttrade"),
    scan=_SIMPLE,
)

POLICIES["rcl"] = _policy(
    name="rcl",
    child_imports=names(
        "tos.canonical tos.ordering tos.rcl tos.rcl._base tos.rcl.authority "
        "tos.rcl.commitlog tos.rcl.predicates tos.rcl.records tos.rcl.state "
        "tos.rcl.vector tos.rcl.vocabulary"
    ),
    canary_imports=names("tos.rcl"),
    planted=names("shared.config tos.evidence tos.capsule numpy"),
    deny=_deny(
        *names("tos.capsule tos.evidence"),
    ),
    expected_present=names("tos.canonical tos.ordering"),
    cleared_canaries=names("tos.rcl tos.canonical tos.ordering"),
    src_dirs=names("rcl"),
    scan=_NO_CLOCK,
)

POLICIES["recon"] = _policy(
    name="recon",
    child_imports=names(
        "tos.recon tos.recon._base tos.recon.predicates tos.recon.records "
        "tos.recon.state tos.recon.vocabulary"
    ),
    canary_imports=names("tos.recon"),
    planted=names("shared.config tos.rcl tos.orthostate tos.evidence numpy"),
    deny=_deny(
        *names(
            "tos.authority tos.capsule tos.dsl tos.evidence tos.liveauth "
            "tos.orthostate tos.rcl tos.time"
        ),
    ),
    expected_present=names("tos.canonical tos.ordering"),
    cleared_canaries=names("tos.recon tos.recon.predicates tos.canonical tos.ordering"),
    src_dirs=names("recon"),
    scan=_SIMPLE,
)

POLICIES["staterestore"] = _policy(
    name="staterestore",
    child_imports=names(
        "tos.staterestore tos.staterestore._l3_worker tos.staterestore._wal "
        "tos.staterestore.reload tos.staterestore.store"
    ),
    canary_imports=names("tos.staterestore"),
    planted=names("shared.config tos.evidence tos.liveauth numpy"),
    deny=_deny(
        *names("tos.authority tos.capsule tos.dsl tos.evidence tos.liveauth tos.time"),
    ),
    expected_present=names("tos.orthostate tos.rcl sqlite3"),
    src_dirs=names("staterestore"),
    scan=_STDLIB_EGRESS,
)

POLICIES["time"] = _policy(
    name="time",
    child_imports=names(
        "tos.canonical tos.ordering tos.time tos.time.domains tos.time.elements "
        "tos.time.ordering tos.time.predicates tos.time.snapshot"
    ),
    canary_imports=names("tos.time"),
    planted=names("shared.config tos.evidence tos.capsule numpy"),
    deny=_deny(
        *names("tos.capsule tos.evidence"),
        yaml=False,
    ),
    cleared_canaries=names("tos.canonical tos.ordering tos.time"),
    src_dirs=names("time ordering"),
    scan=_TIME,
)

POLICIES["venue"] = _policy(
    name="venue",
    child_imports=names(
        "tos.venue tos.venue._base tos.venue.predicates tos.venue.records "
        "tos.venue.state tos.venue.vocabulary"
    ),
    canary_imports=names("tos.venue"),
    planted=names("shared.config numpy tos.iap tos.sbr tos.dsl tos.pr"),
    deny=_deny(),
    allowed_tos=nameset("tos tos.canonical tos.ordering tos.venue"),
    static_scan=True,
    forbidden_siblings=names(
        "tos.afg tos.are tos.authority tos.brokercap tos.capsule tos.dsl tos.evidence "
        "tos.iap tos.ioc tos.liveauth tos.orthostate tos.pr tos.protective tos.rcl "
        "tos.recon tos.sbr tos.spg tos.time"
    ),
    expected_present=names("tos.canonical tos.ordering tos.venue"),
    allowed_canaries=names(
        "tos.venue tos.venue.predicates tos.canonical tos.canonical._base "
        "tos.ordering"
    ),
    src_dirs=names("venue"),
    scan=_SIMPLE,
)

POLICIES["workload"] = _policy(
    name="workload",
    child_imports=names(
        "tos.canonical tos.workload tos.workload.predicates tos.workload.records"
    ),
    canary_imports=names("tos.workload"),
    planted=names("shared.config tos.rcl tos.evidence numpy"),
    deny=_deny(
        *names(
            "tos.authority tos.capsule tos.egress tos.egressgw tos.evidence tos.rcl"
        ),
    ),
    expected_present=names("tos.canonical"),
    cleared_canaries=names("tos.workload tos.canonical"),
    src_dirs=names("workload"),
    scan=_CLOCK_AND_RNG,
)
