"""tos — Trading Operating System kernel (greenfield boundary).

Governed by docs/plans/2026-07-20-tos-boundary-and-import-firewall-design.md.
Every module here (and under tos/tests) obeys the import allowlist enforced by
tools/tos_firewall_check.py (§3.2) and the repo-root .importlinter contract
(§3.3-②). This package is non-transmitting by construction (§4): no broker
credentials, routes, order-construction, or env-flag capability paths.

Concrete component modules (models/, capsule/, evidence/, harness/) are added
by the follow-on design documents (§2.4); this initial skeleton exists so the
firewall gate has a package to certify.
"""

from __future__ import annotations

__version__ = "0.0.1"

__all__ = ["__version__"]
