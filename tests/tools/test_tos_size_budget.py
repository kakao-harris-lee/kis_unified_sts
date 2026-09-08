"""Focused tests for the tos kernel size budget checker (Phase 1 작업 6).

One test per failure class the checker enforces -- (a) unregistered over-budget
target, (b) expired exception, (c) stale exception, (d) malformed entry / duplicate
decomposition_order, (e) missing/unparseable config, (f) registered ``measured``
drifted from the actual count -- each proven live on a synthetic fixture (a checker
that never goes red is a dead checker; see the module docstring of
``tools/tos_size_budget.py``), plus a control-group passing case, a
measurement-mechanics test for nested/method qualnames, and previously-untested red
paths (an unmeasurable AST node, an absent scope directory, an unparseable source
file, a symlink escaping ``--root``). The final test is a smoke test against the
real ``config/tos_size_budget.yaml`` / ``tos/src/tos`` tree.
"""

from __future__ import annotations

import ast
import datetime as dt
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "tools" / "tos_size_budget.py"


def _load_size_budget_module():
    spec = importlib.util.spec_from_file_location("tos_size_budget", _MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


sb = _load_size_budget_module()

TODAY = dt.date(2026, 9, 7)


def _write_config(path: Path, config: dict) -> None:
    path.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def _base_config(**overrides: object) -> dict:
    config = {
        "module_max_lines": 5,
        "function_max_lines": 3,
        "scope": ["pkg"],
        "exceptions": [],
    }
    config.update(overrides)
    return config


def _write_module_lines(path: Path, n_lines: int) -> None:
    """Write a module of exactly ``n_lines`` physical lines (simple statements)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"x{i} = {i}" for i in range(n_lines))
    path.write_text(body + "\n", encoding="utf-8")


def _write_function_module(path: Path, func_name: str, n_lines: int) -> None:
    """Write a module whose sole top-level function spans exactly ``n_lines`` lines.

    ``n_lines`` counts the ``def`` line itself, matching ``end_lineno - lineno + 1``.
    """
    if n_lines < 2:
        raise ValueError("n_lines must be >= 2 (def line + at least one body line)")
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"def {func_name}():"]
    lines += [f"    b{i} = {i}" for i in range(n_lines - 1)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _exception_entry(target: str, measured: int, **overrides: object) -> dict:
    entry = {
        "target": target,
        "measured": measured,
        "owner": "tos-kernel",
        "decomposition_order": 1,
        "expires_on": "2026-12-31",
        "note": "test fixture",
    }
    entry.update(overrides)
    return entry


# ---------------------------------------------------------------------------
# Control group: nothing over budget, no exceptions needed -> PASS.
# ---------------------------------------------------------------------------


def test_control_group_under_budget_passes(tmp_path: Path) -> None:
    _write_module_lines(tmp_path / "pkg" / "small.py", 3)  # under module_max_lines=5
    config_path = tmp_path / "budget.yaml"
    _write_config(config_path, _base_config())

    config, malformed = sb.load_config(config_path)
    assert malformed == []
    violations = sb.run_check(tmp_path, config, malformed, today=TODAY)
    assert violations == []

    rc = sb.main(
        [
            "--check",
            "--config",
            str(config_path),
            "--root",
            str(tmp_path),
            "--today",
            TODAY.isoformat(),
        ]
    )
    assert rc == 0


# ---------------------------------------------------------------------------
# (a) over-budget target with no exception entry.
# ---------------------------------------------------------------------------


def test_class_a_unregistered_over_budget_target(tmp_path: Path) -> None:
    _write_module_lines(tmp_path / "pkg" / "big.py", 6)  # over module_max_lines=5
    config_path = tmp_path / "budget.yaml"
    _write_config(config_path, _base_config())

    config, malformed = sb.load_config(config_path)
    violations = sb.run_check(tmp_path, config, malformed, today=TODAY)
    assert len(violations) == 1
    assert violations[0].startswith("[unregistered]")
    assert "pkg/big.py" in violations[0]

    rc = sb.main(
        [
            "--check",
            "--config",
            str(config_path),
            "--root",
            str(tmp_path),
            "--today",
            TODAY.isoformat(),
        ]
    )
    assert rc == 1


# ---------------------------------------------------------------------------
# (b) exception whose expires_on has passed -- fail-closed regardless of
# whether the target is still over budget.
# ---------------------------------------------------------------------------


def test_class_b_expired_exception(tmp_path: Path) -> None:
    _write_module_lines(tmp_path / "pkg" / "big.py", 6)
    config_path = tmp_path / "budget.yaml"
    _write_config(
        config_path,
        _base_config(
            exceptions=[
                _exception_entry("pkg/big.py", 6, expires_on="2026-01-01"),
            ]
        ),
    )

    config, malformed = sb.load_config(config_path)
    violations = sb.run_check(tmp_path, config, malformed, today=TODAY)
    assert len(violations) == 1
    assert violations[0].startswith("[expired]")
    assert "pkg/big.py" in violations[0]

    rc = sb.main(
        [
            "--check",
            "--config",
            str(config_path),
            "--root",
            str(tmp_path),
            "--today",
            TODAY.isoformat(),
        ]
    )
    assert rc == 1


# ---------------------------------------------------------------------------
# (c) stale exception -- target no longer exists, or is no longer over budget.
# The register must not rot: both are red.
# ---------------------------------------------------------------------------


def test_class_c_stale_exception(tmp_path: Path) -> None:
    # sub-case 1: registered target file no longer exists.
    (tmp_path / "pkg").mkdir(parents=True, exist_ok=True)
    # sub-case 2: registered target now measures under budget (shrunk since registration).
    # ``measured`` is kept at the file's *current* 3 lines so this case tests only the
    # class-(c) staleness axis in isolation — a registration whose ``measured`` still
    # matches the actual count but is simply no longer over budget. A registration whose
    # ``measured`` itself has drifted from the actual count is the separate class-(f) case
    # (test_class_f_measured_drift below).
    _write_module_lines(tmp_path / "pkg" / "shrunk.py", 3)  # under module_max_lines=5

    config_path = tmp_path / "budget.yaml"
    _write_config(
        config_path,
        _base_config(
            exceptions=[
                _exception_entry("pkg/gone.py", 6, decomposition_order=1),
                _exception_entry("pkg/shrunk.py", 3, decomposition_order=2),
            ]
        ),
    )

    config, malformed = sb.load_config(config_path)
    violations = sb.run_check(tmp_path, config, malformed, today=TODAY)
    assert len(violations) == 2
    kinds = {v.split("]")[0] for v in violations}
    assert kinds == {"[stale-missing", "[stale-under-budget"}

    rc = sb.main(
        [
            "--check",
            "--config",
            str(config_path),
            "--root",
            str(tmp_path),
            "--today",
            TODAY.isoformat(),
        ]
    )
    assert rc == 1


# ---------------------------------------------------------------------------
# (d) malformed exception entry, and a duplicate decomposition_order across
# two otherwise well-formed entries.
# ---------------------------------------------------------------------------


def test_class_d_malformed_entry(tmp_path: Path) -> None:
    config_path = tmp_path / "budget.yaml"
    entry = _exception_entry("pkg/big.py", 6)
    del entry["owner"]  # missing required field
    _write_config(config_path, _base_config(exceptions=[entry]))

    config, malformed = sb.load_config(config_path)
    assert config.exceptions == ()  # malformed entry excluded, not crashed on
    assert len(malformed) == 1
    assert malformed[0].startswith("[malformed-entry]")
    assert "owner" in malformed[0]


def test_class_d_duplicate_decomposition_order(tmp_path: Path) -> None:
    _write_module_lines(tmp_path / "pkg" / "big1.py", 6)
    _write_module_lines(tmp_path / "pkg" / "big2.py", 7)
    config_path = tmp_path / "budget.yaml"
    _write_config(
        config_path,
        _base_config(
            exceptions=[
                _exception_entry("pkg/big1.py", 6, decomposition_order=1),
                _exception_entry("pkg/big2.py", 7, decomposition_order=1),
            ]
        ),
    )

    config, malformed = sb.load_config(config_path)
    assert malformed == []
    violations = sb.run_check(tmp_path, config, malformed, today=TODAY)
    dup = [v for v in violations if v.startswith("[duplicate-order]")]
    assert len(dup) == 1

    rc = sb.main(
        [
            "--check",
            "--config",
            str(config_path),
            "--root",
            str(tmp_path),
            "--today",
            TODAY.isoformat(),
        ]
    )
    assert rc == 1


# ---------------------------------------------------------------------------
# (f) a registered `measured` that no longer matches the target's actual line
# count -- the register is a ratchet, not a decorative snapshot: growth (or
# shrinkage) under an unchanged `measured` must be visible, not silently green.
# ---------------------------------------------------------------------------


def test_class_f_measured_drift(tmp_path: Path) -> None:
    # big.py is written at 7 lines but registered as if it were still 6 -- the
    # registration is stale even though the target is (still, correctly) over budget
    # and (still, correctly) registered under a live decomposition_order.
    _write_module_lines(tmp_path / "pkg" / "big.py", 7)  # over module_max_lines=5
    config_path = tmp_path / "budget.yaml"
    _write_config(
        config_path,
        _base_config(exceptions=[_exception_entry("pkg/big.py", 6)]),
    )

    config, malformed = sb.load_config(config_path)
    violations = sb.run_check(tmp_path, config, malformed, today=TODAY)
    assert len(violations) == 1
    assert violations[0].startswith("[measured-drift]")
    assert "pkg/big.py" in violations[0]
    assert "registered 6" in violations[0]
    assert "actual 7" in violations[0]

    rc = sb.main(
        [
            "--check",
            "--config",
            str(config_path),
            "--root",
            str(tmp_path),
            "--today",
            TODAY.isoformat(),
        ]
    )
    assert rc == 1

    # Re-registering deliberately (measured corrected to the actual 7) clears the
    # drift -- the fix is a conscious edit to the register, not automatic.
    _write_config(
        config_path,
        _base_config(exceptions=[_exception_entry("pkg/big.py", 7)]),
    )
    config, malformed = sb.load_config(config_path)
    violations = sb.run_check(tmp_path, config, malformed, today=TODAY)
    assert violations == []

    rc = sb.main(
        [
            "--check",
            "--config",
            str(config_path),
            "--root",
            str(tmp_path),
            "--today",
            TODAY.isoformat(),
        ]
    )
    assert rc == 0


# ---------------------------------------------------------------------------
# (e) the config file itself is missing or unparseable -- never silently pass.
# ---------------------------------------------------------------------------


def test_class_e_missing_config_file(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.yaml"
    with pytest.raises(sb.SizeBudgetConfigError):
        sb.load_config(missing)

    rc = sb.main(["--check", "--config", str(missing), "--root", str(tmp_path)])
    assert rc == 1


def test_class_e_unparseable_config_file(tmp_path: Path) -> None:
    config_path = tmp_path / "budget.yaml"
    config_path.write_text("not: [valid: yaml: broken", encoding="utf-8")
    with pytest.raises(sb.SizeBudgetConfigError):
        sb.load_config(config_path)

    rc = sb.main(["--check", "--config", str(config_path), "--root", str(tmp_path)])
    assert rc == 1


def test_class_e_config_missing_required_top_level_key(tmp_path: Path) -> None:
    config_path = tmp_path / "budget.yaml"
    _write_config(
        config_path, {"module_max_lines": 5, "function_max_lines": 3}
    )  # no scope
    with pytest.raises(sb.SizeBudgetConfigError, match="scope"):
        sb.load_config(config_path)


# ---------------------------------------------------------------------------
# Function-length budget and AST measurement mechanics: nested functions and
# methods get "path::qualname" targets, decorators are excluded from the span.
# ---------------------------------------------------------------------------


def test_function_over_budget_and_qualname_nesting(tmp_path: Path) -> None:
    _write_function_module(tmp_path / "pkg" / "funcs.py", "long_function", 4)
    config_path = tmp_path / "budget.yaml"
    _write_config(config_path, _base_config())  # function_max_lines=3

    config, malformed = sb.load_config(config_path)
    violations = sb.run_check(tmp_path, config, malformed, today=TODAY)
    assert len(violations) == 1
    assert "pkg/funcs.py::long_function" in violations[0]


def test_measure_nested_and_method_qualnames(tmp_path: Path) -> None:
    source = (
        "class Outer:\n"
        "    def method(self):\n"
        "        def inner():\n"
        "            return 1\n"
        "        return inner()\n"
        "\n"
        "@staticmethod\n"
        "def decorated():\n"
        "    return 2\n"
    )
    path = tmp_path / "pkg" / "nested.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    config_path = tmp_path / "budget.yaml"
    _write_config(
        config_path, _base_config(function_max_lines=1000, module_max_lines=1000)
    )

    config, _ = sb.load_config(config_path)
    measured = sb.measure(tmp_path, config)
    targets = {m.target: m.lines for m in measured if m.kind == "function"}
    assert "pkg/nested.py::Outer.method" in targets
    assert "pkg/nested.py::Outer.method.inner" in targets
    # decorated() spans exactly its own def+body, decorator line excluded (lineno
    # points at "def decorated():", not at "@staticmethod").
    assert targets["pkg/nested.py::decorated"] == 2


# ---------------------------------------------------------------------------
# Previously-untested red paths (Low-2, Low-3): a fail-open skip, a missing scope
# directory, an unparseable source file, and a symlink escaping --root. All four
# must exit non-zero (or raise SizeBudgetConfigError directly) with a clear message
# -- never a silent skip or a bare, unexplained exception type.
# ---------------------------------------------------------------------------


def test_function_with_unmeasurable_end_lineno_raises_not_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(Low-2) A function whose ``end_lineno`` cannot be read is red, not silently skipped.

    This should not happen for anything ``ast.parse`` itself produces -- only a
    hand-mutated AST node lacks ``end_lineno`` -- so the fixture monkeypatches
    ``ast.parse`` (as seen by the checker module) to hand back a real parse tree with
    one function's ``end_lineno`` cleared, proving the measurement helper treats that
    as a hard failure rather than under-counting the module by silently dropping the
    function from measurement.
    """
    _write_function_module(tmp_path / "pkg" / "funcs.py", "some_func", 2)
    config_path = tmp_path / "budget.yaml"
    _write_config(config_path, _base_config())
    config, _ = sb.load_config(config_path)

    real_parse = sb.ast.parse

    def _parse_with_missing_end_lineno(*args: object, **kwargs: object) -> ast.Module:
        tree = real_parse(*args, **kwargs)
        for node in sb.ast.walk(tree):
            if isinstance(node, sb.ast.FunctionDef | sb.ast.AsyncFunctionDef):
                node.end_lineno = None
        return tree

    monkeypatch.setattr(sb.ast, "parse", _parse_with_missing_end_lineno)
    with pytest.raises(sb.SizeBudgetConfigError, match="end_lineno"):
        sb.measure(tmp_path, config)


def test_scope_directory_absent_raises_config_error(tmp_path: Path) -> None:
    """(Low-3) A configured scope directory that does not exist is a hard config error."""
    config_path = tmp_path / "budget.yaml"
    _write_config(config_path, _base_config(scope=["pkg_does_not_exist"]))
    config, malformed = sb.load_config(config_path)

    with pytest.raises(sb.SizeBudgetConfigError, match="scope directory not found"):
        sb.run_check(tmp_path, config, malformed, today=TODAY)

    rc = sb.main(
        [
            "--check",
            "--config",
            str(config_path),
            "--root",
            str(tmp_path),
            "--today",
            TODAY.isoformat(),
        ]
    )
    assert rc == 1


def test_unparseable_source_file_raises_config_error(tmp_path: Path) -> None:
    """(Low-3) A source file in scope that fails to parse is a hard config error, not a skip."""
    (tmp_path / "pkg").mkdir(parents=True, exist_ok=True)
    (tmp_path / "pkg" / "broken.py").write_text("def f(:\n    pass\n", encoding="utf-8")
    config_path = tmp_path / "budget.yaml"
    _write_config(config_path, _base_config())
    config, malformed = sb.load_config(config_path)

    with pytest.raises(sb.SizeBudgetConfigError, match="cannot parse"):
        sb.run_check(tmp_path, config, malformed, today=TODAY)

    rc = sb.main(
        [
            "--check",
            "--config",
            str(config_path),
            "--root",
            str(tmp_path),
            "--today",
            TODAY.isoformat(),
        ]
    )
    assert rc == 1


def test_symlink_escaping_root_raises_config_error(tmp_path: Path) -> None:
    """(Low-3) A scope-directory symlink that resolves outside --root fails closed.

    Previously ``_target_path`` let ``Path.relative_to``'s bare ``ValueError`` escape
    uncaught; this exercises the same scenario end to end through ``--check``.
    """
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    _write_module_lines(outside_dir / "external.py", 3)

    root = tmp_path / "root"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "link.py").symlink_to(outside_dir / "external.py")

    config_path = root / "budget.yaml"
    _write_config(config_path, _base_config())
    config, malformed = sb.load_config(config_path)

    with pytest.raises(sb.SizeBudgetConfigError, match="outside"):
        sb.run_check(root, config, malformed, today=TODAY)

    rc = sb.main(
        [
            "--check",
            "--config",
            str(config_path),
            "--root",
            str(root),
            "--today",
            TODAY.isoformat(),
        ]
    )
    assert rc == 1


# ---------------------------------------------------------------------------
# Smoke test: the real tree must pass --check against the committed register.
# ---------------------------------------------------------------------------


def test_check_real_config_smoke() -> None:
    result = subprocess.run(
        [sys.executable, str(_REPO_ROOT / "tools" / "tos_size_budget.py"), "--check"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
