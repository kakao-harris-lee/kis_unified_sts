"""The probe loader never walks parents, injects env or reads secrets in tests."""

from pathlib import Path

import pytest

from shared.config import dotenv_guard as guard


def test_hermetic_mode_never_reads_explicit_path(monkeypatch):
    monkeypatch.setattr(guard, "hermetic_mode_enabled", lambda: True)
    assert (
        guard.read_explicit_dotenv(Path("/does/not/exist/.env.real"), keys=["KEY"])
        == {}
    )


def test_only_selected_keys_without_interpolation_or_env_mutation(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(guard, "hermetic_mode_enabled", lambda: False)
    monkeypatch.setenv("OTHER_SECRET", "ambient")
    monkeypatch.delenv("PROBE_KEY", raising=False)
    source = tmp_path / ".env.real"
    source.write_text(
        "PROBE_KEY='literal ${OTHER_SECRET}'\nOTHER_SECRET=private\nEMPTY=\n"
    )
    values = guard.read_explicit_dotenv(source, keys=["PROBE_KEY", "EMPTY", "ABSENT"])
    assert values == {"PROBE_KEY": "literal ${OTHER_SECRET}"}
    import os

    assert "PROBE_KEY" not in os.environ
    assert os.environ["OTHER_SECRET"] == "ambient"


def test_no_relative_path_or_parent_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(guard, "hermetic_mode_enabled", lambda: False)
    with pytest.raises(ValueError, match="absolute"):
        guard.read_explicit_dotenv(Path(".env.real"), keys=["KEY"])
    (tmp_path / ".env.real").write_text("KEY=parent\n")
    nested = tmp_path / "worktree"
    nested.mkdir()
    with pytest.raises(FileNotFoundError):
        guard.read_explicit_dotenv(nested / ".env.real", keys=["KEY"])
