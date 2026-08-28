"""tos test package.

Marks ``tos/tests`` as a package so property-test modules can share strategies
via firewall-exempt **relative** imports (``from ._strategies import ...``). A
non-relative helper import (``from _strategies import ...``) would be a
TOS-FW-A violation; relative imports resolve within the kernel and are allowed
(tools/tos_firewall_check.py §3.3-①).
"""
