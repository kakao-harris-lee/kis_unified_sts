"""Unit tests for the tos completion-contract derived index generator
(``tools/tos_contract_index.py``).

The module under test lives outside the package tree (like its sibling
``tools/tos_contract_check.py``), so it is loaded directly from its file
path — these tests do not depend on ``tools`` being importable as a package.

Every fixture document below satisfies the four self-description fields
``tos_contract_check.ContractDoc`` requires to parse at all (version field,
errata-round marker, future-field declaration, currency-vocabulary
declaration) — otherwise construction itself raises ``ContractParseError``
before any of the index logic under test even runs.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO_ROOT / "tools" / "tos_contract_index.py"


def _load_index_module():
    spec = importlib.util.spec_from_file_location("tos_contract_index", _MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


tci = _load_index_module()
tcc = tci.tcc  # tos_contract_check, re-exposed via the module under test


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

#: Minimal self-description header satisfying ``ContractDoc``'s four required
#: fields (version / errata round / future-field / currency-vocab).
_MIN_HEADER = (
    "> **버전**: v1.0 (2026-01-01)\n"
    '> **미래 지향 필드**("재심 대상")\n'
    "> 「테스트」 어휘 스윕\n"
    "[v1.0 에라타 1차 — 테스트 시드]\n"
)


#: 헤더가 차지하는 물리 행 수 — 헤더 뒤에 붙는 `body` 의 n번째 행은 문서 전체에서
#: `_HEADER_LINE_COUNT + n` 번째 행이 된다(1-기반).  테스트는 이 헬퍼로 좌표를
#: 계산해, 헤더 문자열이 바뀌어도 하드코딩된 절대 행 번호가 깨지지 않게 한다.
_HEADER_LINE_COUNT = _MIN_HEADER.count("\n")


def _bl(body_line: int) -> int:
    """`body` 안의 1-기반 행 번호를 문서 전체의 1-기반 행 번호로 바꾼다."""
    return _HEADER_LINE_COUNT + body_line


def _doc(body: str, display_path: str = "fixture.md") -> tcc.ContractDoc:
    return tcc.ContractDoc(_MIN_HEADER + body, display_path)


def _init_git_repo(repo: Path) -> None:
    """Initialize a hermetic git repo in ``repo`` (for blob-id / grep tests)."""
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"], cwd=repo, check=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)


# ---------------------------------------------------------------------------
# derive_sections
# ---------------------------------------------------------------------------


def test_derive_sections_nests_deeper_headings_inside_shallower() -> None:
    """A level-3 section's range must extend through its level-4 children."""
    doc = _doc(
        "## 1. 최상위\n"
        "본문 1행\n"
        "### 1.1 하위\n"
        "본문 2행\n"
        "#### 1.1.1 더 하위\n"
        "본문 3행\n"
        "## 2. 다음 최상위\n"
        "본문 4행\n"
    )
    sections = tci.derive_sections(doc)
    top = next(s for s in sections if s.heading_text.startswith("1. "))
    child = next(s for s in sections if s.heading_text.startswith("1.1 "))
    assert top.number == "1"
    assert child.number == "1.1"
    # "## 2." 가 시작하는 행 직전까지 "## 1." 구간이어야 한다 (얕은 헤딩까지 포함).
    next_top = next(s for s in sections if s.heading_text.startswith("2. "))
    assert top.end_line == next_top.lineno - 1
    assert top.contains(child.lineno)


def test_derive_sections_excludes_headings_inside_code_fence() -> None:
    """A ``#`` inside a *well-paired* code fence is not a heading (검사기 규율과 동일)."""
    doc = _doc(
        "## 1. 진짜 헤딩\n"
        "```python\n"
        "# 이것은 파이썬 주석이지 헤딩이 아니다\n"
        "```\n"
        "## 2. 다음 진짜 헤딩\n"
    )
    sections = tci.derive_sections(doc)
    heading_texts = [s.heading_text for s in sections]
    assert "1. 진짜 헤딩" in heading_texts
    assert "2. 다음 진짜 헤딩" in heading_texts
    assert not any("파이썬 주석" in t for t in heading_texts)


# ---------------------------------------------------------------------------
# derive_definition — 3 규칙 (heading / table-row / prose-line-start)
# ---------------------------------------------------------------------------


def test_derive_definition_heading_rule_requires_backtick_wrap() -> None:
    """헤딩 규칙은 백틱으로 감싼 식별자만 정의로 인정한다 (§S-26 류 «인용만»은 배제)."""
    doc = _doc(
        "##### `U-9` — 정의 헤딩\n" "본문.\n" "### 11.1 다른 절 — 정본은 **§U-9** 다\n"
    )
    definition = tci.derive_definition(doc, "U-9", mention_lines=[_bl(1), _bl(3)])
    assert definition.status == "DEFINED"
    assert definition.line == _bl(1)
    assert definition.rule == "heading"


def test_derive_definition_table_row_rule() -> None:
    doc = _doc("| UNCHK-099 | 열2 | 열3 |\n" "|---|---|---|\n")
    definition = tci.derive_definition(doc, "UNCHK-099", mention_lines=[_bl(1)])
    assert definition.status == "DEFINED"
    assert definition.rule == "table-row"
    assert definition.line == _bl(1)


def test_derive_definition_prose_rule_requires_column_zero() -> None:
    """산문 규칙은 들여쓰기 없는 행두만 인정한다 — continuation 행의 우연한 어두는 배제."""
    doc = _doc(
        "S-9 **[신설]  진짜 정의 행.**\n"
        "     들여쓰기된 continuation 행에서 S-9 이 다시 나와도 정의가 아니다\n"
    )
    definition = tci.derive_definition(doc, "S-9", mention_lines=[_bl(1), _bl(2)])
    assert definition.status == "DEFINED"
    assert definition.rule == "prose-line-start"
    assert definition.line == _bl(1)


def test_derive_definition_ambiguous_when_two_candidates() -> None:
    """규칙에 맞는 후보가 2개 이상이면 하나를 임의로 고르지 않고 AMBIGUOUS 를 낸다."""
    doc = _doc(
        "S-5 **[정의 후보 1]**\n" "본문\n" "S-5 **[정의 후보 2 — 오염된 픽스처]**\n"
    )
    definition = tci.derive_definition(doc, "S-5", mention_lines=[_bl(1), _bl(3)])
    assert definition.status == "AMBIGUOUS"
    assert definition.candidates == [_bl(1), _bl(3)]
    assert definition.line is None


def test_derive_definition_none_when_only_mentioned() -> None:
    """언급은 있지만 세 규칙 중 어느 것도 맞지 않으면 NONE — 하나를 임의로 고르지 않는다."""
    doc = _doc("이 문단은 중간에서 U-3 을 그냥 언급할 뿐 정의하지 않는다.\n")
    definition = tci.derive_definition(doc, "U-3", mention_lines=[_bl(1)])
    assert definition.status == "NONE"
    assert definition.line is None
    assert definition.mention_count == 1


# ---------------------------------------------------------------------------
# locate_range
# ---------------------------------------------------------------------------


def test_locate_range_heading_spans_full_section() -> None:
    doc = _doc(
        "##### `U-9` — 헤딩\n" "본문 A\n" "##### `U-10` — 다음 헤딩\n" "본문 B\n"
    )
    sections = tci.derive_sections(doc)
    definition = tci.derive_definition(doc, "U-9", mention_lines=[_bl(1)])
    start, end, note = tci.locate_range(doc, sections, definition)
    assert (start, end) == (_bl(1), _bl(2))
    assert note == ""


def test_locate_range_prose_definition_is_single_line_with_caveat() -> None:
    """비-헤딩 정의는 구조적 블록 끝을 지어내지 않고 단일 행 + 한계 고지를 낸다."""
    doc = _doc("S-9 **[정의]**\n" "     continuation 행\n")
    sections = tci.derive_sections(doc)
    definition = tci.derive_definition(doc, "S-9", mention_lines=[_bl(1)])
    start, end, note = tci.locate_range(doc, sections, definition)
    assert (start, end) == (_bl(1), _bl(1))
    assert "단일 행" in note


# ---------------------------------------------------------------------------
# resolve_locate_target
# ---------------------------------------------------------------------------


def test_resolve_locate_target_rejects_unknown_identifier_family() -> None:
    """추적하지 않는 패밀리의 오타는 조용히 NONE 이 아니라 SystemExit 로 드러낸다."""
    doc = _doc("본문\n")
    sections = tci.derive_sections(doc)
    definitions = tci.derive_all_definitions(doc)
    with pytest.raises(SystemExit):
        tci.resolve_locate_target(doc, sections, definitions, "ZZZ-1")


def test_resolve_locate_target_section_number_lookup() -> None:
    doc = _doc("### 3.2 절번호 조회 대상\n" "본문\n")
    sections = tci.derive_sections(doc)
    definitions = tci.derive_all_definitions(doc)
    definition = tci.resolve_locate_target(doc, sections, definitions, "§3.2")
    assert definition.status == "DEFINED"
    assert definition.line == _bl(1)
    assert definition.rule == "heading"


# ---------------------------------------------------------------------------
# classify_citation — § 접두 요구 (2026-09-01 fail-open 회귀 수정 대조군)
#
# 팀장이 실측 지적한 결함: 섹션 «번호»를 맨 숫자로 찾으면 `devcontainers/ci@v0.3`
# 이 §0.3 을, `default=0.4` 가 §0.4 를 인용한 것으로 오판했다.  아래는 그
# 재발을 막는 양방향 대조군이다 — 음성(맨 숫자는 증거가 아니다) · 양성(`§` 접두
# 형태는 여전히 증거다).  식별자 축(고유 토큰)은 이 수정의 대상이 아니므로 별도
# 대조군으로 «영향 없음»을 확인한다.
# ---------------------------------------------------------------------------


def _hermetic_tools_repo(tmp_path: Path, tools_file_body: str) -> Path:
    """`tools/fake_probe.py` 하나만 든 최소 저장소 — grep 증거 채널 격리용.

    `git grep` 은 기본값에서 **추적된** 파일만 본다 — 커밋까지 해야
    `tools_file_body` 가 실제 검색 대상에 들어간다(빈 문자열이어도 커밋은
    유효하다).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    (repo / "tools").mkdir()
    (repo / "tools" / "fake_probe.py").write_text(tools_file_body, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)
    return repo


def test_classify_citation_bare_number_in_grep_is_not_evidence(tmp_path: Path) -> None:
    """`default=0.3` 류 맨 숫자는 더 이상 §0.3 의 증거가 아니다 (fail-open 수정)."""
    repo = _hermetic_tools_repo(tmp_path, "default = 0.3\n")
    doc = _doc("### 0.3 절 제목\n본문\n")
    section = tci.derive_sections(doc)[0]
    definitions = tci.derive_all_definitions(doc)
    citation = tci.classify_citation(section, definitions, commits=[], repo_root=repo)
    assert citation.status == "UNCITED"


def test_classify_citation_section_prefixed_grep_is_evidence(tmp_path: Path) -> None:
    """`§0.3` 처럼 실제로 `§` 가 붙은 형태는 여전히(그리고 이제야 정확히) 증거다."""
    repo = _hermetic_tools_repo(tmp_path, "# see §0.3 for detail\n")
    doc = _doc("### 0.3 절 제목\n본문\n")
    section = tci.derive_sections(doc)[0]
    definitions = tci.derive_all_definitions(doc)
    citation = tci.classify_citation(section, definitions, commits=[], repo_root=repo)
    assert citation.status == "LIVE"
    assert any("§0.3" in e for e in citation.evidence)


def test_classify_citation_bare_number_in_commit_message_is_not_evidence(
    tmp_path: Path,
) -> None:
    """커밋 메시지의 아무 `1` 도 §1 의 증거가 아니다 — grep 채널은 빈 저장소로 격리."""
    repo = _hermetic_tools_repo(tmp_path, "")
    doc = _doc("### 1. 절 제목\n본문\n")
    section = tci.derive_sections(doc)[0]
    definitions = tci.derive_all_definitions(doc)
    commits = [("abc1234", "fix: bump to version 1 for release")]
    citation = tci.classify_citation(section, definitions, commits, repo_root=repo)
    assert citation.status == "UNCITED"


def test_classify_citation_section_prefixed_commit_message_is_evidence(
    tmp_path: Path,
) -> None:
    repo = _hermetic_tools_repo(tmp_path, "")
    doc = _doc("### 1. 절 제목\n본문\n")
    section = tci.derive_sections(doc)[0]
    definitions = tci.derive_all_definitions(doc)
    commits = [("abc1234", "fix: update §1 handling")]
    citation = tci.classify_citation(section, definitions, commits, repo_root=repo)
    assert citation.status == "LIVE"
    assert any("§1" in e for e in citation.evidence)


def test_classify_citation_owned_identifier_is_unaffected_by_number_fix(
    tmp_path: Path,
) -> None:
    """고유 식별자 축(S-*)은 이 수정의 대상이 아니다 — 단어경계 grep 매치로 여전히 LIVE."""
    repo = _hermetic_tools_repo(tmp_path, "# references S-1 in a comment\n")
    doc = _doc("##### `S-1` — 정의 헤딩\n본문\n")
    section = tci.derive_sections(doc)[0]
    definitions = tci.derive_all_definitions(doc)
    citation = tci.classify_citation(section, definitions, commits=[], repo_root=repo)
    assert citation.status == "LIVE"
    assert any("S-1" in e for e in citation.evidence)


def test_classify_citation_no_discriminating_token_is_uncited(tmp_path: Path) -> None:
    """자기 식별자도 §번호도 없는 섹션은 검색할 게 없으므로 UNCITED — LIVE 를 후하게 주지 않는다."""
    repo = _hermetic_tools_repo(tmp_path, "")
    doc = _doc("이 섹션은 헤딩이 아니라 순수 산문이라 번호도 식별자도 없다.\n")
    definitions = tci.derive_all_definitions(doc)
    fake_section = tci.Section(
        lineno=_bl(1), level=0, heading_text="", raw_line="", end_line=_bl(1)
    )
    citation = tci.classify_citation(
        fake_section, definitions, commits=[], repo_root=repo
    )
    assert citation.status == "UNCITED"
    assert citation.tokens == []


# ---------------------------------------------------------------------------
# fence_parity_suspects
# ---------------------------------------------------------------------------


def test_fence_parity_suspects_detects_missing_close_marker() -> None:
    """닫힘 자리에 순수 ``` 가 아니라 또 다른 열림이 오면 의심 쌍으로 잡는다."""
    doc = _doc(
        "```text\n"
        "한 줄짜리 블록\n"
        "```text\n"  # 의도한 닫힘 대신 다시 열림을 써버린 결함 픽스처
        "다음 블록 내용\n"
        "```\n"
    )
    suspects = tci.fence_parity_suspects(doc)
    assert len(suspects) == 1
    open_l, close_l, content = suspects[0]
    assert (open_l, close_l) == (_bl(1), _bl(3))
    assert content == "```text"


def test_fence_parity_suspects_empty_for_well_formed_fences() -> None:
    doc = _doc("```text\n한 줄\n```\n")
    assert tci.fence_parity_suspects(doc) == []


# ---------------------------------------------------------------------------
# git_blob_id / check_staleness — 실제 git 저장소가 필요한 경로
# ---------------------------------------------------------------------------


def test_check_staleness_positive_and_negative(tmp_path: Path) -> None:
    """같은 blob 이면 최신(rc 의미상 True), blob 이 바뀌면 STALE — 대조군 둘 다."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    contract = repo / "contract.md"
    contract.write_text(_MIN_HEADER + "## 1. 절\n본문\n", encoding="utf-8")

    report = tci.build_report(contract, repo, commits=5, argv_display="test")
    rendered = tci.render_markdown(report)
    out_path = repo / "index.md"
    out_path.write_text(rendered, encoding="utf-8")

    fresh, message = tci.check_staleness(out_path, contract, repo)
    assert fresh is True
    assert report.blob_id in message

    # 계약을 건드리지 않고 stale 을 모의한다 — 다른 사본을 --contract 로 지정.
    changed_copy = repo / "contract_changed.md"
    changed_copy.write_text(
        _MIN_HEADER + "## 1. 절\n본문이 바뀌었다\n", encoding="utf-8"
    )
    stale, stale_message = tci.check_staleness(out_path, changed_copy, repo)
    assert stale is False
    assert "STALE" in stale_message


def test_check_staleness_missing_output_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    contract = repo / "contract.md"
    contract.write_text(_MIN_HEADER + "## 1. 절\n본문\n", encoding="utf-8")

    fresh, message = tci.check_staleness(repo / "does-not-exist.md", contract, repo)
    assert fresh is False
    assert "없다" in message
