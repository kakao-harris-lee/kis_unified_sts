"""Explicit per-package import lists for the closure children (TOS-FW-D: no dynamic import)."""

from __future__ import annotations

from collections.abc import Callable


def import_afg() -> None:
    """Import every module the ``afg`` closure canary measures."""
    import tos.afg  # noqa: F401
    import tos.afg._base  # noqa: F401
    import tos.afg.predicates  # noqa: F401
    import tos.afg.records  # noqa: F401
    import tos.afg.state  # noqa: F401
    import tos.afg.vocabulary  # noqa: F401


def import_afg_root() -> None:
    """Import the root package the ``afg`` leak canary plants into."""
    import tos.afg  # noqa: F401


def import_are() -> None:
    """Import every module the ``are`` closure canary measures."""
    import tos.are  # noqa: F401
    import tos.are._base  # noqa: F401
    import tos.are.predicates  # noqa: F401
    import tos.are.records  # noqa: F401
    import tos.are.state  # noqa: F401
    import tos.are.vocabulary  # noqa: F401


def import_are_root() -> None:
    """Import the root package the ``are`` leak canary plants into."""
    import tos.are  # noqa: F401


def import_authority() -> None:
    """Import every module the ``authority`` closure canary measures."""
    import tos.authority  # noqa: F401
    import tos.authority._base  # noqa: F401
    import tos.authority.predicates  # noqa: F401
    import tos.authority.records  # noqa: F401
    import tos.authority.state  # noqa: F401
    import tos.authority.vocabulary  # noqa: F401
    import tos.canonical  # noqa: F401
    import tos.ordering  # noqa: F401
    import tos.time  # noqa: F401


def import_authority_root() -> None:
    """Import the root package the ``authority`` leak canary plants into."""
    import tos.authority  # noqa: F401


def import_backtest() -> None:
    """Import every module the ``backtest`` closure canary measures."""
    import tos.backtest  # noqa: F401
    import tos.backtest._base  # noqa: F401
    import tos.backtest.bars  # noqa: F401
    import tos.backtest.calibration  # noqa: F401
    import tos.backtest.converter  # noqa: F401
    import tos.backtest.driver  # noqa: F401
    import tos.backtest.fills  # noqa: F401
    import tos.backtest.records  # noqa: F401
    import tos.backtest.resolver  # noqa: F401
    import tos.backtest.results  # noqa: F401
    import tos.backtest.scenarios  # noqa: F401
    import tos.backtest.vocabulary  # noqa: F401


def import_backtest_root() -> None:
    """Import the root package the ``backtest`` leak canary plants into."""
    import tos.backtest  # noqa: F401


def import_brokeradapter() -> None:
    """Import every module the ``brokeradapter`` closure canary measures."""
    import tos.brokeradapter  # noqa: F401
    import tos.brokeradapter.protocol  # noqa: F401
    import tos.brokeradapter.synthetic  # noqa: F401


def import_brokeradapter_root() -> None:
    """Import the root package the ``brokeradapter`` leak canary plants into."""
    import tos.brokeradapter  # noqa: F401


def import_brokercap() -> None:
    """Import every module the ``brokercap`` closure canary measures."""
    import tos.brokercap  # noqa: F401
    import tos.brokercap._base  # noqa: F401
    import tos.brokercap.predicates  # noqa: F401
    import tos.brokercap.records  # noqa: F401
    import tos.brokercap.routing  # noqa: F401
    import tos.brokercap.vocabulary  # noqa: F401


def import_brokercap_root() -> None:
    """Import the root package the ``brokercap`` leak canary plants into."""
    import tos.brokercap  # noqa: F401


def import_capsule() -> None:
    """Import every module the ``capsule`` closure canary measures."""
    import tos.capsule  # noqa: F401
    import tos.capsule.canonicalization  # noqa: F401
    import tos.capsule.capsule  # noqa: F401
    import tos.capsule.consistency_cut  # noqa: F401
    import tos.capsule.context_generation  # noqa: F401
    import tos.capsule.field_evaluation  # noqa: F401
    import tos.capsule.field_state  # noqa: F401
    import tos.capsule.lineage  # noqa: F401
    import tos.capsule.observation  # noqa: F401
    import tos.capsule.predicates  # noqa: F401
    import tos.capsule.snapshot  # noqa: F401


def import_capsule_root() -> None:
    """Import the root package the ``capsule`` leak canary plants into."""
    import tos.capsule  # noqa: F401


def import_cur() -> None:
    """Import every module the ``cur`` closure canary measures."""
    import tos.cur  # noqa: F401
    import tos.cur._base  # noqa: F401
    import tos.cur.predicates  # noqa: F401
    import tos.cur.records  # noqa: F401
    import tos.cur.state  # noqa: F401
    import tos.cur.vocabulary  # noqa: F401


def import_cur_root() -> None:
    """Import the root package the ``cur`` leak canary plants into."""
    import tos.cur  # noqa: F401


def import_dsl() -> None:
    """Import every module the ``dsl`` closure canary measures."""
    import tos.dsl  # noqa: F401
    import tos.dsl._base  # noqa: F401
    import tos.dsl.admissibility  # noqa: F401
    import tos.dsl.bounds  # noqa: F401
    import tos.dsl.candidate  # noqa: F401
    import tos.dsl.determinism  # noqa: F401
    import tos.dsl.evidence  # noqa: F401
    import tos.dsl.outcome  # noqa: F401
    import tos.dsl.proposal  # noqa: F401
    import tos.dsl.strategy  # noqa: F401
    import tos.dsl.vocabulary  # noqa: F401


def import_dsl_root() -> None:
    """Import the root package the ``dsl`` leak canary plants into."""
    import tos.dsl  # noqa: F401


def import_egress() -> None:
    """Import every module the ``egress`` closure canary measures."""
    import tos.egress  # noqa: F401
    import tos.egress._base  # noqa: F401
    import tos.egress.predicates  # noqa: F401
    import tos.egress.records  # noqa: F401
    import tos.egress.state  # noqa: F401
    import tos.egress.vocabulary  # noqa: F401


def import_egress_root() -> None:
    """Import the root package the ``egress`` leak canary plants into."""
    import tos.egress  # noqa: F401


def import_egressgw() -> None:
    """Import every module the ``egressgw`` closure canary measures."""
    import tos.egressgw  # noqa: F401
    import tos.egressgw._base  # noqa: F401
    import tos.egressgw.construction  # noqa: F401
    import tos.egressgw.gateway  # noqa: F401
    import tos.egressgw.mesh  # noqa: F401
    import tos.egressgw.records  # noqa: F401
    import tos.egressgw.seal  # noqa: F401
    import tos.egressgw.venuefacts  # noqa: F401
    import tos.egressgw.vocabulary  # noqa: F401


def import_egressgw_root() -> None:
    """Import the root package the ``egressgw`` leak canary plants into."""
    import tos.egressgw  # noqa: F401


def import_engine() -> None:
    """Import every module the ``engine`` closure canary measures."""
    import tos.engine  # noqa: F401
    import tos.engine._base  # noqa: F401
    import tos.engine.adapters  # noqa: F401
    import tos.engine.admission  # noqa: F401
    import tos.engine.core  # noqa: F401
    import tos.engine.orthostate_projection  # noqa: F401
    import tos.engine.pipeline  # noqa: F401
    import tos.engine.records  # noqa: F401
    import tos.engine.registry  # noqa: F401
    import tos.engine.sequencer  # noqa: F401
    import tos.engine.sink  # noqa: F401
    import tos.engine.standins  # noqa: F401
    import tos.engine.state  # noqa: F401
    import tos.engine.vocabulary  # noqa: F401


def import_engine_root() -> None:
    """Import the root package the ``engine`` leak canary plants into."""
    import tos.engine  # noqa: F401


def import_evidence() -> None:
    """Import every module the ``evidence`` closure canary measures."""
    import tos.canonical  # noqa: F401
    import tos.canonical.canonicalization  # noqa: F401
    import tos.evidence  # noqa: F401
    import tos.evidence.chain  # noqa: F401
    import tos.evidence.elements  # noqa: F401
    import tos.evidence.envelope  # noqa: F401
    import tos.evidence.gap  # noqa: F401
    import tos.evidence.ledger  # noqa: F401
    import tos.evidence.policy  # noqa: F401
    import tos.evidence.predicates  # noqa: F401
    import tos.evidence.receipt  # noqa: F401
    import tos.evidence.replay  # noqa: F401
    import tos.evidence.retention  # noqa: F401
    import tos.evidence.scrub  # noqa: F401


def import_evidence_root() -> None:
    """Import the root package the ``evidence`` leak canary plants into."""
    import tos.evidence  # noqa: F401


def import_iap() -> None:
    """Import every module the ``iap`` closure canary measures."""
    import tos.iap  # noqa: F401
    import tos.iap._base  # noqa: F401
    import tos.iap.predicates  # noqa: F401
    import tos.iap.records  # noqa: F401
    import tos.iap.state  # noqa: F401
    import tos.iap.vocabulary  # noqa: F401


def import_iap_root() -> None:
    """Import the root package the ``iap`` leak canary plants into."""
    import tos.iap  # noqa: F401


def import_ioc() -> None:
    """Import every module the ``ioc`` closure canary measures."""
    import tos.ioc  # noqa: F401
    import tos.ioc._base  # noqa: F401
    import tos.ioc.predicates  # noqa: F401
    import tos.ioc.records  # noqa: F401
    import tos.ioc.state  # noqa: F401
    import tos.ioc.vocabulary  # noqa: F401


def import_ioc_root() -> None:
    """Import the root package the ``ioc`` leak canary plants into."""
    import tos.ioc  # noqa: F401


def import_marketfeed() -> None:
    """Import every module the ``marketfeed`` closure canary measures."""
    import tos.marketfeed  # noqa: F401
    import tos.marketfeed._base  # noqa: F401
    import tos.marketfeed.records  # noqa: F401
    import tos.marketfeed.resolver  # noqa: F401
    import tos.marketfeed.value  # noqa: F401
    import tos.marketfeed.vocabulary  # noqa: F401


def import_marketfeed_root() -> None:
    """Import the root package the ``marketfeed`` leak canary plants into."""
    import tos.marketfeed  # noqa: F401


def import_orthostate() -> None:
    """Import every module the ``orthostate`` closure canary measures."""
    import tos.orthostate  # noqa: F401
    import tos.orthostate._base  # noqa: F401
    import tos.orthostate.predicates  # noqa: F401
    import tos.orthostate.records  # noqa: F401
    import tos.orthostate.state  # noqa: F401
    import tos.orthostate.vocabulary  # noqa: F401


def import_orthostate_root() -> None:
    """Import the root package the ``orthostate`` leak canary plants into."""
    import tos.orthostate  # noqa: F401


def import_posttrade() -> None:
    """Import every module the ``posttrade`` closure canary measures."""
    import tos.posttrade  # noqa: F401
    import tos.posttrade._base  # noqa: F401
    import tos.posttrade.predicates  # noqa: F401
    import tos.posttrade.records  # noqa: F401
    import tos.posttrade.vocabulary  # noqa: F401


def import_posttrade_root() -> None:
    """Import the root package the ``posttrade`` leak canary plants into."""
    import tos.posttrade  # noqa: F401


def import_rcl() -> None:
    """Import every module the ``rcl`` closure canary measures."""
    import tos.canonical  # noqa: F401
    import tos.ordering  # noqa: F401
    import tos.rcl  # noqa: F401
    import tos.rcl._base  # noqa: F401
    import tos.rcl.authority  # noqa: F401
    import tos.rcl.commitlog  # noqa: F401
    import tos.rcl.predicates  # noqa: F401
    import tos.rcl.records  # noqa: F401
    import tos.rcl.state  # noqa: F401
    import tos.rcl.vector  # noqa: F401
    import tos.rcl.vocabulary  # noqa: F401


def import_rcl_root() -> None:
    """Import the root package the ``rcl`` leak canary plants into."""
    import tos.rcl  # noqa: F401


def import_recon() -> None:
    """Import every module the ``recon`` closure canary measures."""
    import tos.recon  # noqa: F401
    import tos.recon._base  # noqa: F401
    import tos.recon.predicates  # noqa: F401
    import tos.recon.records  # noqa: F401
    import tos.recon.state  # noqa: F401
    import tos.recon.vocabulary  # noqa: F401


def import_recon_root() -> None:
    """Import the root package the ``recon`` leak canary plants into."""
    import tos.recon  # noqa: F401


def import_staterestore() -> None:
    """Import every module the ``staterestore`` closure canary measures."""
    import tos.staterestore  # noqa: F401
    import tos.staterestore._l3_worker  # noqa: F401
    import tos.staterestore._wal  # noqa: F401
    import tos.staterestore.reload  # noqa: F401
    import tos.staterestore.store  # noqa: F401


def import_staterestore_root() -> None:
    """Import the root package the ``staterestore`` leak canary plants into."""
    import tos.staterestore  # noqa: F401


def import_time() -> None:
    """Import every module the ``time`` closure canary measures."""
    import tos.canonical  # noqa: F401
    import tos.ordering  # noqa: F401
    import tos.time  # noqa: F401
    import tos.time.domains  # noqa: F401
    import tos.time.elements  # noqa: F401
    import tos.time.ordering  # noqa: F401
    import tos.time.predicates  # noqa: F401
    import tos.time.snapshot  # noqa: F401


def import_time_root() -> None:
    """Import the root package the ``time`` leak canary plants into."""
    import tos.time  # noqa: F401


def import_venue() -> None:
    """Import every module the ``venue`` closure canary measures."""
    import tos.venue  # noqa: F401
    import tos.venue._base  # noqa: F401
    import tos.venue.predicates  # noqa: F401
    import tos.venue.records  # noqa: F401
    import tos.venue.state  # noqa: F401
    import tos.venue.vocabulary  # noqa: F401


def import_venue_root() -> None:
    """Import the root package the ``venue`` leak canary plants into."""
    import tos.venue  # noqa: F401


def import_workload() -> None:
    """Import every module the ``workload`` closure canary measures."""
    import tos.canonical  # noqa: F401
    import tos.workload  # noqa: F401
    import tos.workload.predicates  # noqa: F401
    import tos.workload.records  # noqa: F401


def import_workload_root() -> None:
    """Import the root package the ``workload`` leak canary plants into."""
    import tos.workload  # noqa: F401


def import_tos_engine() -> None:
    """Import ``tos.engine`` alone, to measure the closure it widens a bound by."""
    import tos.engine  # noqa: F401


IMPORTERS: dict[str, Callable[[], None]] = {
    "afg": import_afg,
    "afg:root": import_afg_root,
    "are": import_are,
    "are:root": import_are_root,
    "authority": import_authority,
    "authority:root": import_authority_root,
    "backtest": import_backtest,
    "backtest:root": import_backtest_root,
    "brokeradapter": import_brokeradapter,
    "brokeradapter:root": import_brokeradapter_root,
    "brokercap": import_brokercap,
    "brokercap:root": import_brokercap_root,
    "capsule": import_capsule,
    "capsule:root": import_capsule_root,
    "cur": import_cur,
    "cur:root": import_cur_root,
    "dsl": import_dsl,
    "dsl:root": import_dsl_root,
    "egress": import_egress,
    "egress:root": import_egress_root,
    "egressgw": import_egressgw,
    "egressgw:root": import_egressgw_root,
    "engine": import_engine,
    "engine:root": import_engine_root,
    "evidence": import_evidence,
    "evidence:root": import_evidence_root,
    "iap": import_iap,
    "iap:root": import_iap_root,
    "ioc": import_ioc,
    "ioc:root": import_ioc_root,
    "marketfeed": import_marketfeed,
    "marketfeed:root": import_marketfeed_root,
    "orthostate": import_orthostate,
    "orthostate:root": import_orthostate_root,
    "posttrade": import_posttrade,
    "posttrade:root": import_posttrade_root,
    "rcl": import_rcl,
    "rcl:root": import_rcl_root,
    "recon": import_recon,
    "recon:root": import_recon_root,
    "staterestore": import_staterestore,
    "staterestore:root": import_staterestore_root,
    "time": import_time,
    "time:root": import_time_root,
    "venue": import_venue,
    "venue:root": import_venue_root,
    "workload": import_workload,
    "workload:root": import_workload_root,
    "module:tos.engine": import_tos_engine,
}
