"""Import-closure firewall test for the shared.determinism commons."""

import subprocess
import sys

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
