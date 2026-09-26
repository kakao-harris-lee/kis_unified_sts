"""Tests for ``tools/tos_evidence_citation_check.py`` (carryover plan W-C C-3 / arc plan F-4)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tools import tos_evidence_citation_check as checker

T3 = checker.REPO_ROOT / "docs/broker-profiles/evidence/2026-09-11-p02-t3-campaign"


def _campaign(tmp_path: Path, readme: str, artifact: dict | None = None) -> Path:
    if artifact is not None:
        (tmp_path / "A-1.json").write_text(json.dumps(artifact), encoding="utf-8")
    path = tmp_path / "README.md"
    path.write_text(readme, encoding="utf-8")
    return path


_ARTIFACT = {
    "measurements": {
        "total": 25,
        "ratio": 0.5,
        "verdict": "OK",
        "flag": True,
        "absent": None,
        "pages": [20, 5],
        "rows": [{"qty": 1}],
    }
}


@pytest.mark.parametrize(
    "token",
    [
        "`A-1.json:measurements.total=25`",
        "`A-1.json:measurements.ratio=0.5`",
        "`A-1.json:measurements.verdict=OK`",
        "`A-1.json:measurements.flag=true`",
        "`A-1.json:measurements.absent=null`",
        "`A-1.json:measurements.pages=[20,5]`",
        "`A-1.json:measurements.pages[1]=5`",
        "`A-1.json:measurements.rows[0].qty=1`",
    ],
)
def test_resolving_citation_passes(tmp_path: Path, token: str) -> None:
    readme = _campaign(tmp_path, f"| row | {token} |\n", _ARTIFACT)
    count, failures = checker.check([readme])
    assert count == 1
    assert failures == []


@pytest.mark.parametrize(
    ("token", "reason"),
    [
        ("`A-1.json:measurements.total=26`", "artifact holds"),
        ("`A-1.json:measurements.flag=True`", "artifact holds"),
        ("`A-1.json:measurements.pdno=017670`", "does not exist"),
        ("`A-1.json:measurements.pages[2]=5`", "does not exist"),
        ("`A-1.json:measurements.total.x=1`", "does not exist"),
        ("`B-2.json:measurements.total=25`", "not found"),
    ],
)
def test_non_resolving_citation_fails_with_reason(
    tmp_path: Path, token: str, reason: str
) -> None:
    readme = _campaign(tmp_path, f"text {token} text\n", _ARTIFACT)
    count, failures = checker.check([readme])
    assert count == 1
    [failure] = failures
    assert reason in failure.reason
    assert failure.citation.line == 1


def test_unreadable_artifact_fails(tmp_path: Path) -> None:
    (tmp_path / "A-1.json").write_text("{not json", encoding="utf-8")
    readme = _campaign(tmp_path, "`A-1.json:x=1`\n")
    _count, [failure] = checker.check([readme])
    assert "not readable JSON" in failure.reason


def test_artifact_name_cannot_leave_the_readme_directory(tmp_path: Path) -> None:
    """Only bare file names are citation tokens — a path is not matched at all."""
    readme = _campaign(tmp_path, "`../A-1.json:measurements.total=25`\n", _ARTIFACT)
    assert checker.find_citations(readme) == []


def test_the_729_claim_would_have_failed(tmp_path: Path) -> None:
    """#729: the README attributed a holding (``017670``) to ``P-BAL-20260916T233126Z.json``,
    whose rows carry no ``pdno`` field. Written as a citation, that claim cannot pass.
    """
    artifact = "P-BAL-20260916T233126Z.json"
    shutil.copy(T3 / artifact, tmp_path / artifact)
    readme = _campaign(tmp_path, f"`{artifact}:observations[0].pdno=017670`\n")
    _count, [failure] = checker.check([readme])
    assert "does not exist" in failure.reason


def test_committed_evidence_readmes_resolve() -> None:
    """The committed READMEs — including the C-3 retrofit of the t3 campaign — all resolve."""
    readmes = checker.default_readmes(checker.REPO_ROOT)
    assert T3 / "README.md" in readmes
    count, failures = checker.check(readmes)
    assert failures == [], [f.render(checker.REPO_ROOT) for f in failures]
    assert count >= 8


def test_main_exit_codes(tmp_path: Path) -> None:
    good = _campaign(tmp_path, "`A-1.json:measurements.total=25`\n", _ARTIFACT)
    assert checker.main([str(good)]) == 0
    good.write_text("`A-1.json:measurements.total=1`\n", encoding="utf-8")
    assert checker.main([str(good)]) == 1
    assert checker.main([str(tmp_path / "missing.md")]) == 2
