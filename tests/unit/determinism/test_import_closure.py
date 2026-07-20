"""Import-closure firewall test for the shared.determinism commons.

Enforces the 2026-07-20 tos boundary / import-firewall design (§2.3 / §3.4):
``import shared.determinism`` must not transitively load any operations-only
package or MLflow/Optuna. Run in a fresh subprocess so the assertion reflects
the module's own closure, not modules already imported by the pytest session.
"""

import subprocess
import sys

# Packages that must never appear in shared.determinism's import closure
# (§2.3 forbidden operations-only packages + heavy tracking/optimization libs).
FORBIDDEN_MODULES = [
    "shared.execution",
    "shared.kis",
    "shared.streaming",
    "shared.llm",
    "shared.storage",
    "shared.backtest",
    "mlflow",
    "optuna",
]


def test_determinism_import_closure_is_clean():
    """A fresh ``import shared.determinism`` pulls in no forbidden package."""
    forbidden_literal = repr(FORBIDDEN_MODULES)
    script = (
        "import sys\n"
        "import shared.determinism  # noqa: F401\n"
        f"forbidden = {forbidden_literal}\n"
        "present = sorted(m for m in forbidden if m in sys.modules)\n"
        "print(','.join(present))\n"
        "sys.exit(1 if present else 0)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    leaked = result.stdout.strip()
    assert result.returncode == 0, (
        "shared.determinism import closure leaked forbidden modules: "
        f"{leaked}\nstderr:\n{result.stderr}"
    )


def test_determinism_submodules_closure_is_clean():
    """Importing the concrete submodules directly is also firewall-clean."""
    forbidden_literal = repr(FORBIDDEN_MODULES)
    script = (
        "import sys\n"
        "import shared.determinism.lookahead_guard  # noqa: F401\n"
        "import shared.determinism.replay  # noqa: F401\n"
        f"forbidden = {forbidden_literal}\n"
        "present = sorted(m for m in forbidden if m in sys.modules)\n"
        "print(','.join(present))\n"
        "sys.exit(1 if present else 0)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    leaked = result.stdout.strip()
    assert result.returncode == 0, (
        "shared.determinism submodule closure leaked forbidden modules: "
        f"{leaked}\nstderr:\n{result.stderr}"
    )
