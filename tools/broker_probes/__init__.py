"""KIS Broker Capability Profile measurement probes (Phase-0 gate P0-2, T2).

Authoring-only package: nothing here runs as part of the trading runtime, and no
runtime module imports it. Probes are executed by an operator on the 모의투자
server (project memory ``verify-on-paper-server-not-local-cron``) and produce
JSON evidence artifacts under ``results/`` for the P0-2 approval chain.

Entry point: ``python -m tools.broker_probes.run --list``
Runbook: ``docs/runbooks/kis-capability-probes.md``
"""
