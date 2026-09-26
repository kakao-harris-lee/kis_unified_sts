#!/usr/bin/env python3
"""Evidence README citation checker (carryover plan W-C C-3 / arc plan F-4).

**The class this closes.** An evidence README states a value next to an artifact name, and the
value is not in that artifact: #676 attributed a holding to a ``P-BAL`` artifact whose
``observations`` carry no ``pdno``; #729 repeated it and added an average price that no artifact
contained at all. Both were caught by review, after the fact. The rule
(``docs/broker-profiles/evidence/CITATION-RULE.md``) is that a value stated in an evidence README
names **the artifact and the field** it came from, in one machine-checkable token::

    `P-BAL-20260911T002427Z.json:measurements.truncation_risk.page_size=20`

This tool resolves every such token: the artifact file must exist next to the README, the dotted
path must resolve inside its JSON (``name`` for keys, ``[n]`` for list indices), and the resolved
value must equal the stated one. A citation that does not resolve is a failure, never a skip.

**What it does not do.** It cannot find an *uncited* value in prose — that stays a review rule.
What it removes is the other half: once a value is cited, whether the citation is true is no
longer a matter of anyone re-reading the JSON.

Usage::

    python tools/tos_evidence_citation_check.py            # default README set
    python tools/tos_evidence_citation_check.py PATH...    # specific READMEs

Exit 0 when every citation resolves and matches, 1 otherwise, 2 on a usage error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

#: READMEs checked when no path is given — every evidence campaign README plus the tos one.
DEFAULT_GLOBS: tuple[str, ...] = (
    "docs/broker-profiles/evidence/*/README.md",
    "tos-evidence/**/README.md",
)

#: `` `<artifact>.json:<path>=<value>` `` — a single inline-code token. The artifact is a bare
#: file name (resolved next to the README, never a path that could leave its directory).
CITATION_RE = re.compile(
    r"`(?P<artifact>[A-Za-z0-9][A-Za-z0-9._-]*\.json)"
    r":(?P<path>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*|\[\d+\])*)"
    r"=(?P<value>[^`]*)`"
)

_SEGMENT_RE = re.compile(r"\.?([A-Za-z_][A-Za-z0-9_]*)|\[(\d+)\]")

_MISSING = object()


@dataclass(frozen=True)
class Citation:
    """One citation token found in a README."""

    readme: Path
    line: int
    artifact: str
    path: str
    value: str


@dataclass(frozen=True)
class Failure:
    """A citation that did not resolve or did not match."""

    citation: Citation
    reason: str

    def render(self, root: Path) -> str:
        c = self.citation
        try:
            where = c.readme.relative_to(root)
        except ValueError:
            where = c.readme
        return f"{where}:{c.line}: `{c.artifact}:{c.path}={c.value}` — {self.reason}"


def find_citations(readme: Path) -> list[Citation]:
    """Every citation token in ``readme``, with its 1-based line number."""
    found: list[Citation] = []
    for number, text in enumerate(readme.read_text(encoding="utf-8").splitlines(), 1):
        for match in CITATION_RE.finditer(text):
            found.append(
                Citation(
                    readme=readme,
                    line=number,
                    artifact=match.group("artifact"),
                    path=match.group("path"),
                    value=match.group("value"),
                )
            )
    return found


def resolve(document: Any, path: str) -> Any:
    """The value at dotted ``path`` inside ``document``, or ``_MISSING``."""
    current = document
    for key, index in _SEGMENT_RE.findall(path):
        if key:
            if not isinstance(current, dict) or key not in current:
                return _MISSING
            current = current[key]
        else:
            position = int(index)
            if not isinstance(current, list) or position >= len(current):
                return _MISSING
            current = current[position]
    return current


def render_value(value: Any) -> str:
    """How a resolved JSON value is written on the right of ``=``: strings verbatim, everything
    else as compact JSON (``true``, ``null``, ``25``, ``[20,5]``)."""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def check_citation(citation: Citation) -> Failure | None:
    """``None`` when ``citation`` resolves to exactly its stated value."""
    artifact = citation.readme.parent / citation.artifact
    if not artifact.is_file():
        return Failure(citation, "artifact file not found next to the README")
    try:
        document = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return Failure(citation, f"artifact is not readable JSON ({exc})")
    value = resolve(document, citation.path)
    if value is _MISSING:
        return Failure(citation, "field path does not exist in the artifact")
    rendered = render_value(value)
    if rendered != citation.value:
        return Failure(
            citation, f"artifact holds {rendered!r}, README states {citation.value!r}"
        )
    return None


def default_readmes(root: Path) -> list[Path]:
    """The README set checked when no path is given."""
    readmes: set[Path] = set()
    for pattern in DEFAULT_GLOBS:
        readmes.update(root.glob(pattern))
    return sorted(readmes)


def check(readmes: list[Path]) -> tuple[int, list[Failure]]:
    """``(citation_count, failures)`` over ``readmes``."""
    failures: list[Failure] = []
    count = 0
    for readme in readmes:
        for citation in find_citations(readme):
            count += 1
            failure = check_citation(citation)
            if failure is not None:
                failures.append(failure)
    return count, failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("readmes", nargs="*", type=Path, help="README files to check")
    args = parser.parse_args(argv)

    readmes = [p.resolve() for p in args.readmes] or default_readmes(REPO_ROOT)
    missing = [p for p in readmes if not p.is_file()]
    if missing:
        for path in missing:
            print(f"tos-evidence-citation: no such file: {path}", file=sys.stderr)
        return 2

    count, failures = check(readmes)
    for failure in failures:
        print(failure.render(REPO_ROOT))
    if failures:
        print(
            f"tos-evidence-citation: FAIL — {len(failures)} of {count} citation(s) "
            f"in {len(readmes)} README(s) do not resolve"
        )
        return 1
    print(
        f"tos-evidence-citation: PASS — {count} citation(s) in {len(readmes)} README(s) resolve"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
