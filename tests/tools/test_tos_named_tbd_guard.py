"""Focused tests for the tos_runtime named-TBD guard checker (W-A A-0 round 2)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "tools" / "tos_named_tbd_guard.py"


def _load_guard_module():
    spec = importlib.util.spec_from_file_location("tos_named_tbd_guard", _MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


guard = _load_guard_module()


def _write_config(path: Path, exempt_files: list[dict]) -> None:
    path.write_text(
        yaml.safe_dump({"exempt_files": exempt_files}, sort_keys=False),
        encoding="utf-8",
    )


def _write_unguarded_loader(scope_dir: Path, name: str = "some_loader.py") -> Path:
    """A synthetic file matching the candidate signature (reads YAML) with NO guard"""
    path = scope_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "import yaml\n"
        "\n"
        "def load_config(path):\n"
        "    raw = yaml.safe_load(path.read_text())\n"
        "    return raw['some_field']\n",
        encoding="utf-8",
    )
    return path


def _write_guarded_loader(scope_dir: Path, name: str = "some_loader.py") -> Path:
    path = scope_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "import yaml\n"
        "\n"
        "_TBD_STR = 'TBD'\n"
        "\n"
        "def load_config(path):\n"
        "    raw = yaml.safe_load(path.read_text())\n"
        "    value = raw['some_field']\n"
        "    if value == _TBD_STR:\n"
        "        raise ValueError('still TBD')\n"
        "    return value\n",
        encoding="utf-8",
    )
    return path


def _write_non_candidate(scope_dir: Path, name: str = "not_a_loader.py") -> Path:
    """A file that reads nothing from YAML at all -- never a candidate."""
    path = scope_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    return path


def test_class_a_unregistered_unguarded_candidate_is_a_violation(
    tmp_path: Path,
) -> None:
    scope_dir = tmp_path / "pkg"
    _write_unguarded_loader(scope_dir)
    config_path = tmp_path / "guard.yaml"
    _write_config(config_path, exempt_files=[])

    candidates, violations = guard.check(
        repo_root=tmp_path, scope_dir=scope_dir, config_path=config_path
    )
    assert candidates == ["pkg/some_loader.py"]
    assert len(violations) == 1
    assert "[unguarded]" in violations[0]
    assert "pkg/some_loader.py" in violations[0]


def test_the_load_bearing_mutation_a_brand_new_unguarded_loader_is_caught_with_no_list_update(
    tmp_path: Path,
) -> None:
    """THE mutation the re-review demanded: add a fake loader that was never on any"""
    scope_dir = tmp_path / "pkg"
    _write_guarded_loader(scope_dir, name="existing_loader.py")
    config_path = tmp_path / "guard.yaml"
    _write_config(config_path, exempt_files=[])

    candidates, violations = guard.check(
        repo_root=tmp_path, scope_dir=scope_dir, config_path=config_path
    )
    assert violations == []

    _write_unguarded_loader(scope_dir, name="brand_new_loader.py")
    candidates, violations = guard.check(
        repo_root=tmp_path, scope_dir=scope_dir, config_path=config_path
    )
    assert "pkg/brand_new_loader.py" in candidates
    assert any("brand_new_loader.py" in v for v in violations)


def test_guarded_candidate_passes(tmp_path: Path) -> None:
    scope_dir = tmp_path / "pkg"
    _write_guarded_loader(scope_dir)
    config_path = tmp_path / "guard.yaml"
    _write_config(config_path, exempt_files=[])

    candidates, violations = guard.check(
        repo_root=tmp_path, scope_dir=scope_dir, config_path=config_path
    )
    assert candidates == ["pkg/some_loader.py"]
    assert violations == []


def test_non_candidate_file_is_ignored(tmp_path: Path) -> None:
    scope_dir = tmp_path / "pkg"
    _write_non_candidate(scope_dir)
    config_path = tmp_path / "guard.yaml"
    _write_config(config_path, exempt_files=[])

    candidates, violations = guard.check(
        repo_root=tmp_path, scope_dir=scope_dir, config_path=config_path
    )
    assert candidates == []
    assert violations == []


def test_correctly_registered_exemption_passes(tmp_path: Path) -> None:
    scope_dir = tmp_path / "pkg"
    _write_unguarded_loader(scope_dir)
    config_path = tmp_path / "guard.yaml"
    _write_config(
        config_path,
        exempt_files=[
            {
                "path": "pkg/some_loader.py",
                "reason": "int-only field, no string leaf",
            }
        ],
    )

    candidates, violations = guard.check(
        repo_root=tmp_path, scope_dir=scope_dir, config_path=config_path
    )
    assert candidates == ["pkg/some_loader.py"]
    assert violations == []


def test_class_b_stale_registration_path_missing_is_a_violation(tmp_path: Path) -> None:
    scope_dir = tmp_path / "pkg"
    scope_dir.mkdir(parents=True)
    config_path = tmp_path / "guard.yaml"
    _write_config(
        config_path,
        exempt_files=[
            {"path": "pkg/does_not_exist.py", "reason": "some reason"},
        ],
    )

    _, violations = guard.check(
        repo_root=tmp_path, scope_dir=scope_dir, config_path=config_path
    )
    assert len(violations) == 1
    assert "[stale-registration]" in violations[0]
    assert "does not exist" in violations[0]


def test_class_c_stale_registration_no_longer_a_candidate_is_a_violation(
    tmp_path: Path,
) -> None:
    scope_dir = tmp_path / "pkg"
    _write_non_candidate(scope_dir, name="now_boring.py")
    config_path = tmp_path / "guard.yaml"
    _write_config(
        config_path,
        exempt_files=[
            {
                "path": "pkg/now_boring.py",
                "reason": "used to read YAML, no longer does",
            },
        ],
    )

    _, violations = guard.check(
        repo_root=tmp_path, scope_dir=scope_dir, config_path=config_path
    )
    assert len(violations) == 1
    assert "[stale-registration]" in violations[0]
    assert "no longer a named-TBD candidate" in violations[0]


def test_class_d_stale_exemption_now_guarded_is_a_violation(tmp_path: Path) -> None:
    scope_dir = tmp_path / "pkg"
    _write_guarded_loader(scope_dir, name="now_fixed.py")
    config_path = tmp_path / "guard.yaml"
    _write_config(
        config_path,
        exempt_files=[
            {"path": "pkg/now_fixed.py", "reason": "used to be unguarded"},
        ],
    )

    _, violations = guard.check(
        repo_root=tmp_path, scope_dir=scope_dir, config_path=config_path
    )
    assert len(violations) == 1
    assert "[stale-exemption]" in violations[0]
    assert "now references a guard idiom" in violations[0]


def test_class_e_missing_config_raises(tmp_path: Path) -> None:
    scope_dir = tmp_path / "pkg"
    scope_dir.mkdir(parents=True)
    with pytest.raises(guard.NamedTbdGuardConfigError, match="not found"):
        guard.check(
            repo_root=tmp_path,
            scope_dir=scope_dir,
            config_path=tmp_path / "does-not-exist.yaml",
        )


def test_class_e_unparseable_yaml_raises(tmp_path: Path) -> None:
    scope_dir = tmp_path / "pkg"
    scope_dir.mkdir(parents=True)
    config_path = tmp_path / "guard.yaml"
    config_path.write_text("not: valid: yaml: [[[", encoding="utf-8")
    with pytest.raises(guard.NamedTbdGuardConfigError, match="not valid YAML"):
        guard.check(repo_root=tmp_path, scope_dir=scope_dir, config_path=config_path)


def test_class_e_missing_exempt_files_key_raises(tmp_path: Path) -> None:
    scope_dir = tmp_path / "pkg"
    scope_dir.mkdir(parents=True)
    config_path = tmp_path / "guard.yaml"
    config_path.write_text(yaml.safe_dump({"other_key": []}), encoding="utf-8")
    with pytest.raises(guard.NamedTbdGuardConfigError, match="exempt_files"):
        guard.check(repo_root=tmp_path, scope_dir=scope_dir, config_path=config_path)


def test_class_e_malformed_entry_raises(tmp_path: Path) -> None:
    scope_dir = tmp_path / "pkg"
    scope_dir.mkdir(parents=True)
    config_path = tmp_path / "guard.yaml"
    _write_config(config_path, exempt_files=[{"path": "pkg/x.py"}])
    with pytest.raises(guard.NamedTbdGuardConfigError, match="non-blank"):
        guard.check(repo_root=tmp_path, scope_dir=scope_dir, config_path=config_path)


def test_class_e_duplicate_path_raises(tmp_path: Path) -> None:
    scope_dir = tmp_path / "pkg"
    scope_dir.mkdir(parents=True)
    config_path = tmp_path / "guard.yaml"
    _write_config(
        config_path,
        exempt_files=[
            {"path": "pkg/x.py", "reason": "a"},
            {"path": "pkg/x.py", "reason": "b"},
        ],
    )
    with pytest.raises(guard.NamedTbdGuardConfigError, match="duplicate"):
        guard.check(repo_root=tmp_path, scope_dir=scope_dir, config_path=config_path)


def test_main_check_flag_exits_nonzero_on_violation(tmp_path: Path, capsys) -> None:
    scope_dir = tmp_path / "pkg"
    _write_unguarded_loader(scope_dir)
    config_path = tmp_path / "guard.yaml"
    _write_config(config_path, exempt_files=[])

    rc = guard.main(
        [
            "--check",
            "--config",
            str(config_path),
            "--scope",
            str(scope_dir),
            "--root",
            str(tmp_path),
        ]
    )
    assert rc == 1
    out = capsys.readouterr().out
    assert "FAIL" in out


def test_main_check_flag_exits_zero_when_clean(tmp_path: Path, capsys) -> None:
    scope_dir = tmp_path / "pkg"
    _write_guarded_loader(scope_dir)
    config_path = tmp_path / "guard.yaml"
    _write_config(config_path, exempt_files=[])

    rc = guard.main(
        [
            "--check",
            "--config",
            str(config_path),
            "--scope",
            str(scope_dir),
            "--root",
            str(tmp_path),
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "PASS" in out


_REAL_TREE_CANDIDATE_FLOOR = 43


def test_check_real_config_and_scope_smoke() -> None:
    """The real ``config/tos_named_tbd_guard.yaml`` against the real"""
    candidates, violations = guard.check(
        repo_root=_REPO_ROOT,
        scope_dir=_REPO_ROOT / guard.DEFAULT_SCOPE,
        config_path=_REPO_ROOT / guard.DEFAULT_CONFIG,
    )
    assert violations == [], violations
    assert len(candidates) >= _REAL_TREE_CANDIDATE_FLOOR, (
        f"candidate count dropped to {len(candidates)}, below the floor of "
        f"{_REAL_TREE_CANDIDATE_FLOOR} — did _CANDIDATE_SIGNALS lose a signal?"
    )


def test_a_weakened_candidate_signature_drops_below_the_floor(monkeypatch) -> None:
    """THE mutation the floor above is proven against (round 3 re-review MEDIUM): with"""
    weakened = tuple(s for s in guard._CANDIDATE_SIGNALS if s != "load_yaml_document(")
    assert len(weakened) == len(guard._CANDIDATE_SIGNALS) - 1
    monkeypatch.setattr(guard, "_CANDIDATE_SIGNALS", weakened)

    candidates, violations = guard.check(
        repo_root=_REPO_ROOT,
        scope_dir=_REPO_ROOT / guard.DEFAULT_SCOPE,
        config_path=_REPO_ROOT / guard.DEFAULT_CONFIG,
    )
    assert [v for v in violations if "[stale-registration]" not in v] == [], violations
    assert len(candidates) < _REAL_TREE_CANDIDATE_FLOOR, (
        "weakening the candidate signature should have dropped the count below the "
        f"floor, but got {len(candidates)} -- the floor would not have caught this"
    )
