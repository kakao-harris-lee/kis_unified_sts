"""Single-process unit tests for :mod:`tos.staterestore` (design #39 §8.1 inside leg).

These tests exercise the store and the reload path **within one process**: durable
round-trip, per-dimension transaction boundaries, the S-2 conservative fill, and the S-3
no-stale re-derivation. The real crash / real process boundary lives outside ``tos/``
(``tests/tos_l3/test_state_ev_004_crash_restart.py``), because oracle independence there
is bought structurally by the firewall's reverse rule (§5.2 alternative B / §5.3).

⚠ Authoring evidence; closes no EV.
"""
