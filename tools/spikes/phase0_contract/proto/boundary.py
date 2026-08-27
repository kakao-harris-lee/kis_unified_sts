"""OD-3 경계의 **기계 강제** — T-77.

경계를 산문으로만 쓰면 그것이 선언층/평가층 간극의 다음 사례가 된다.
**OD-3 의 A·B·C 만** 실행으로 강제한다.

  ① (A) 프로토타입이 코퍼스·register 를 **열람하지 않는다**.  두 층이다:
        **⒜ 런타임 열람 가드**(`read_guard`) — 해석된 경로 **값**을 I/O 시점에
           판정한다.  문자열을 어떻게 조립했는지와 **무관**하다.
        **⒝ 정적 소스 스캔**(리터럴 + AST 합성) — 심층 방어.
  ② (C) 실행 중 파일 쓰기가 1 회라도 발생하면 실패 (탐지 + 차단).
        범위는 `GUARDED_ENTRY_POINTS` 로 노출한다 — **전부는 아니다.**
  ③ (B) 금지 아티팩트 5 종이 실행 후 존재하면 실패
  ④ (A 보조) 러너가 **예상 위치의 repo 안**에서 도는지(`locate_violation`).
        사본을 repo 밖에 두고 돌리면 ①⒝③ 의 기준점이 함께 이동해 경계 검사가
        무의미해지므로, 위치 자체를 관측 대상으로 고정한다.

**D(CI 미편입)·E(D0 승격 금지)에는 기계 검사가 없다.**  이 모듈은 그 둘을
강제하지 않으며, 강제한다고 적지도 않는다.

## v2.5 — 정적 스캔은 프록시였고, 프록시가 뚫렸다 (심판 F3)

v2.3 의 ①은 정적 스캔뿐이었고 심판이 **런타임 문자열 조립**으로 3종 전부
우회했다(`prefix+'spec/'` · `''.join(...)` · `chr(115)`).  상수 폴딩을 아무리
넓혀도 값이 런타임 입력에서 오면 접을 수 없다 — **정적 스캔으로 열람 금지를
강제하는 것 자체가 프록시**였다.

v2.5 는 강제를 **열람 시점의 경로 값**으로 옮긴다(⒜).  조립 방식과 무관하므로
제시된 3종 우회가 전부 red 가 된다.  정적 스캔(⒝)은 상수 전파·`str.join`·
`chr`·`%`·`.format` 까지 넓히되 **심층 방어로 격하**한다 — 접을 수 없는
구성이 남는다는 것을 부인하지 않는다.

## v2.6 — 강제의 정본은 이 모듈이 아니다 (심판 F3 critical)

`read_guard`/`write_guard` 는 `main()` 안에서 열리는 monkeypatch 다.  피검사
모듈의 **import 는 그보다 먼저** 일어나므로 모듈 레벨 문장은 가드 창 밖에서
돌았고, 심판은 그 창으로 실제 register 를 읽고도 전건 GREEN 을 재현했다.
또 `_io.open` 처럼 monkeypatch 가 닿지 않는 별칭이 남아 있었다.

**강제의 정본은 `audit_guard` 의 프로세스 전역 감사 hook 이다.**  이 모듈의 두
가드는 **심층 방어**로 남는다 — 차단 사유 문자열과 recorder 를 제공하고,
audit hook 이 보지 않는 진입점(예: 쓰기 모드 판정이 필요한 `os.fdopen`,
`os.write(fd>2)`)을 덮는다.  거꾸로 audit hook 이 덮고 이 층이 못 덮는 것도
있다(import 시점 · `_io.open` · 대소문자 변형).  **어느 층도 이미 열린 fd 로의
쓰기는 덮지 못한다.**

금지 리터럴은 **조각으로 합성**한다.  그러지 않으면 이 검사기 자신이 자기
스캔에 걸린다.  AST 스캔은 그 정의 대입만 좁게 면제하며(`TOKEN_DEFINITION_*`),
면제가 좁은지는 대조군이 관측한다.
"""

from __future__ import annotations

import ast
import builtins
import io
import os
import shutil
from collections.abc import Callable, Iterable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import audit_guard

#: 토큰은 `audit_guard` 가 **하나만** 정의한다 (v2.6).  가드의 정본이 감사
#: hook 으로 옮겨갔으므로 판정 재료도 거기서 파생해야 두 층이 드리프트하지
#: 않는다.  그 결과 이 파일에는 금지 토큰으로 접히는 리터럴이 남지 않아
#: AST 스캔 면제 지점도 `audit_guard.py` 하나로 좁아졌다.
_CORPUS_DIR = audit_guard.CORPUS_DIR
_REGISTER_PREFIX = audit_guard.REGISTER_PREFIX

#: OD-3-A — 이 토큰이 소스에 등장하면 코퍼스·register 를 읽는 코드다.
FORBIDDEN_SOURCE_TOKENS: tuple[str, ...] = (
    _CORPUS_DIR,
    _REGISTER_PREFIX + "002",
    _REGISTER_PREFIX + "DEV",
)

_SPEC = audit_guard.SPEC_DIR
_VERIFICATION = f"{_SPEC}/src/verification"

#: OD-3-B — 생성이 금지된 D0 아티팩트 5 종.
FORBIDDEN_ARTIFACTS: tuple[str, ...] = (
    "tools/tos_completion_status.py",
    f"{_SPEC}/src/TOS-COMPLETION-STATUS.md",
    f"{_VERIFICATION}/EVIDENCE-SURFACE-MAP.csv",
    f"{_VERIFICATION}/EVIDENCE-REQUIRED-KINDS.csv",
    f"{_VERIFICATION}/PHASE0-UNCHECKABLE-REGISTER.csv",
)

#: AST 스캔의 **유일한** 면제 지점 — 검사기는 자기가 찾는 토큰을 알아야 한다.
#: 파일 전체를 면제하지 않고 이 이름들에 대입되는 표현식만 면제한다.
#: v2.6: 토큰 정의가 `audit_guard.py` 로 옮겨가면서 면제 이름이 4 개에서
#: 2 개로 **좁아졌다** — 이 파일에는 접히는 리터럴이 더 이상 없다.
TOKEN_DEFINITION_SITE = "audit_guard.py"
TOKEN_DEFINITION_NAMES: frozenset[str] = frozenset({"CORPUS_DIR", "REGISTER_PREFIX"})

#: OD-3-A ⒜ — 열람 가드가 경로에서 찾는 표지.  `FORBIDDEN_SOURCE_TOKENS` 와
#: 같은 조각에서 파생하므로 둘이 따로 놀 수 없다.
_CORPUS_DIRNAME = audit_guard.CORPUS_DIRNAME

#: OD-3-A ⒜ 가드가 실제로 감싸는 열람 진입점.  **이 목록 밖은 덮지 못한다.**
#: 이 층은 이제 **심층 방어**다 — 정본은 `audit_guard` 의 프로세스 전역 hook 이며
#: 그쪽은 `_io.open` 같은 별칭과 import 시점까지 덮는다.
READ_GUARDED_ENTRY_POINTS: tuple[str, ...] = (
    "builtins.open",
    "io.open",
    "os.open",
    "Path.open",
    "Path.read_text",
    "Path.read_bytes",
    "os.listdir",
    "os.scandir",
)

#: OD-3-A ④ — 러너가 여기 있어야 한다.  repo 루트는 이 표지로 식별한다.
#:
#: v2.6: 표지가 `('.git', 'pyproject.toml')` 였고 **하나만 있어도 통과**했다.
#: `pyproject.toml` 은 repo 안에 이미 여러 개 있으므로(`tos/pyproject.toml`)
#: 가짜 루트를 만들 재료가 외부 준비물 없이 존재했다 — 심판이 그 재료로
#: 위치 검사를 무력화했다.  표지를 `.git` 하나로 좁힌다.
REPO_MARKERS: tuple[str, ...] = (".git",)
EXPECTED_RUNNER_RELPATH = "tools/spikes/phase0_contract/test_contracts.py"

_WRITE_FLAG_CHARS = frozenset("wax+")

#: OD-3-C 가드가 실제로 감싸는 진입점.  **이 목록 밖은 덮지 못한다.**
GUARDED_ENTRY_POINTS: tuple[str, ...] = (
    "builtins.open",
    "io.open",
    "os.open",
    "os.fdopen",
    "os.write(fd>2)",
    "os.remove",
    "os.unlink",
    "os.rmdir",
    "os.mkdir",
    "os.makedirs",
    "os.truncate",
    "os.rename",
    "os.renames",
    "os.replace",
    "os.link",
    "os.symlink",
    "shutil.copy",
    "shutil.copyfile",
    "shutil.copy2",
    "shutil.copyfileobj",
    "shutil.copytree",
    "shutil.move",
    "shutil.rmtree",
    "shutil.make_archive",
    "Path.write_text",
    "Path.write_bytes",
    "Path.touch",
    "Path.mkdir",
    "Path.rmdir",
    "Path.unlink",
    "Path.rename",
    "Path.replace",
    "Path.symlink_to",
    "Path.hardlink_to",
)

_OS_BLOCKED = (
    "remove",
    "unlink",
    "rmdir",
    "mkdir",
    "makedirs",
    "truncate",
    "rename",
    "renames",
    "replace",
    "link",
    "symlink",
)
_SHUTIL_BLOCKED = (
    "copy",
    "copyfile",
    "copy2",
    "copyfileobj",
    "copytree",
    "move",
    "rmtree",
    "make_archive",
)
_PATH_BLOCKED = (
    "write_text",
    "write_bytes",
    "touch",
    "mkdir",
    "rmdir",
    "unlink",
    "rename",
    "replace",
    "symlink_to",
    "hardlink_to",
)


class BoundaryViolation(RuntimeError):
    """경계 위반.  탐지와 동시에 **차단**한다 (OD-3-C: 파일 쓰기 0)."""


@dataclass
class WriteRecorder:
    """차단된 쓰기 시도 기록."""

    attempts: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.attempts


@dataclass
class ReadRecorder:
    """차단된 코퍼스·register 열람 시도 기록 (OD-3-A ⒜)."""

    attempts: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.attempts


def scan_sources(sources: Mapping[str, str]) -> list[str]:
    """① 소스 텍스트에서 금지 토큰을 찾는다."""
    findings: list[str] = []
    for name, text in sources.items():
        for token in FORBIDDEN_SOURCE_TOKENS:
            if token in text:
                findings.append(f"{name}: 금지 토큰 {token!r}")
    return findings


#: 인자 없이 값이 결정되는 문자열 메서드.
_NULLARY_STR_METHODS = ("upper", "lower", "strip", "lstrip", "rstrip", "title")


def _const_call(node: ast.Call, env: Mapping[str, str]) -> str | None:
    """상수로 결정되는 호출을 접는다 — `chr` · `join` · `replace` · `format`.

    심판이 v2.3 을 뚫은 `''.join(('tos-','spec/'))` 와 `'tos-'+chr(115)+'pec/'`
    가 여기서 접힌다.
    """
    func = node.func
    if node.keywords:
        return None
    if isinstance(func, ast.Name) and func.id == "chr" and len(node.args) == 1:
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, int):
            try:
                return chr(arg.value)
            except (ValueError, OverflowError):
                return None
        return None
    if not isinstance(func, ast.Attribute):
        return None
    base = _const_str(func.value, env)
    if base is None:
        return None
    attr = func.attr
    if attr == "join" and len(node.args) == 1:
        seq = node.args[0]
        if not isinstance(seq, (ast.Tuple, ast.List, ast.Set)):
            return None
        parts = [_const_str(element, env) for element in seq.elts]
        if any(part is None for part in parts):
            return None
        return base.join(part for part in parts if part is not None)
    if attr == "replace" and len(node.args) == 2:
        old = _const_str(node.args[0], env)
        new = _const_str(node.args[1], env)
        if old is None or new is None:
            return None
        return base.replace(old, new)
    if attr == "format":
        parts = [_const_str(arg, env) for arg in node.args]
        if any(part is None for part in parts):
            return None
        try:
            return base.format(*parts)
        except (IndexError, KeyError, ValueError):
            return None
    if attr in _NULLARY_STR_METHODS and not node.args:
        return str(getattr(base, attr)())
    return None


def _const_str(node: ast.AST, env: Mapping[str, str] | None = None) -> str | None:
    """상수로 결정되는 문자열 값을 접는다.  `env` 는 전파된 이름 -> 값이다.

    **접을 수 없는 구성이 남는다** — 런타임 입력(파일·환경변수·argv)에서 오는
    값은 원리적으로 접히지 않는다.  그래서 이 스캔은 열람 가드의 심층 방어이지
    OD-3-A 의 유일 강제가 아니다.
    """
    env = env or {}
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else None
    if isinstance(node, ast.Name):
        return env.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _const_str(node.left, env)
        right = _const_str(node.right, env)
        if left is None or right is None:
            return None
        return left + right
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        template = _const_str(node.left, env)
        if template is None:
            return None
        right = node.right
        items = right.elts if isinstance(right, (ast.Tuple, ast.List)) else [right]
        values = [_const_str(item, env) for item in items]
        if any(value is None for value in values):
            return None
        try:
            return template % tuple(values)
        except (TypeError, ValueError):
            return None
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            text = _const_str(value, env)
            if text is None:
                return None
            parts.append(text)
        return "".join(parts)
    if isinstance(node, ast.FormattedValue):
        # 변환·포맷스펙이 붙으면 값이 확정되지 않는다.
        if node.conversion not in (-1, None) or node.format_spec is not None:
            return None
        return _const_str(node.value, env)
    if isinstance(node, ast.Call):
        return _const_call(node, env)
    return None


def _fold_env(tree: ast.Module, filename: str) -> dict[str, str]:
    """이름 -> 상수 문자열 환경.  **단일 대입만** 신뢰하는 최소 상수 전파다.

    심판이 v2.3 을 뚫은 `prefix='tos-'; p=prefix+'spec/'` 가 여기서 접힌다.
    같은 이름이 두 번 이상 묶이면(재대입·`for`·함수 인자·튜플 언패킹) 값이
    확정되지 않으므로 **환경에서 뺀다** — 틀린 값으로 접느니 접지 않는다.

    토큰 정의 이름은 **정의 파일에서만** 제외한다.  검사기가 자기가 찾는 토큰을
    알아야 하기 때문이며, 면제를 그 파일·그 이름들로 좁게 유지한다.
    """
    bound: dict[str, list[ast.AST | None]] = {}

    def mark(name: str, value: ast.AST | None) -> None:
        bound.setdefault(name, []).append(value)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    mark(target.id, node.value)
                else:
                    # 튜플 언패킹 등 — 이름별 값을 특정할 수 없다.
                    for sub in ast.walk(target):
                        if isinstance(sub, ast.Name):
                            mark(sub.id, None)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            mark(node.target.id, node.value)
        elif isinstance(
            node, (ast.AugAssign, ast.For, ast.AsyncFor, ast.comprehension)
        ):
            target = getattr(node, "target", None)
            for sub in ast.walk(target) if target is not None else ():
                if isinstance(sub, ast.Name):
                    mark(sub.id, None)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs):
                mark(arg.arg, None)
            for extra in (args.vararg, args.kwarg):
                if extra is not None:
                    mark(extra.arg, None)

    skip = TOKEN_DEFINITION_NAMES if filename == TOKEN_DEFINITION_SITE else frozenset()
    env: dict[str, str] = {}
    for name, values in bound.items():
        if name in skip or len(values) != 1 or values[0] is None:
            continue
        folded = _const_str(values[0], {})
        if folded is not None:
            env[name] = folded
    return env


def _exempt_node_ids(tree: ast.Module, filename: str) -> set[int]:
    """토큰 정의 대입의 우변만 면제한다 (파일 전체 면제가 아니다)."""
    if filename != TOKEN_DEFINITION_SITE:
        return set()
    exempt: set[int] = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        names = {t.id for t in node.targets if isinstance(t, ast.Name)}
        if not names <= TOKEN_DEFINITION_NAMES or not names:
            continue
        for child in ast.walk(node.value):
            exempt.add(id(child))
    return exempt


def scan_sources_ast(sources: Mapping[str, str]) -> list[str]:
    """①-AST — 문자열 상수를 **합성**하는 표현식까지 평가해 금지 토큰을 찾는다.

    리터럴 스캔은 리터럴한 위반만 잡는다.  `Path('tos-' + 'spec')` 처럼 조각을
    이어붙이면 텍스트에는 조립된 형태가 없어 그대로 통과한다.  여기서는 AST 를
    접어 **값** 을 보고 판정한다.  파싱 실패는 조용한 통과가 아니라 실패다.
    """
    findings: set[str] = set()
    for name, text in sources.items():
        if not name.endswith(".py"):
            continue
        try:
            tree = ast.parse(text, filename=name)
        except SyntaxError as exc:
            findings.add(f"{name}: 파싱 실패로 AST 스캔 불가 ({exc})")
            continue
        exempt = _exempt_node_ids(tree, name)
        env = _fold_env(tree, name)
        for node in ast.walk(tree):
            # 순수 리터럴은 리터럴 스캔이 이미 본다.  여기서는 **합성**만 본다.
            if not isinstance(node, ast.expr) or isinstance(node, ast.Constant):
                continue
            if id(node) in exempt:
                continue
            value = _const_str(node, env)
            if value is None:
                continue
            for token in FORBIDDEN_SOURCE_TOKENS:
                if token in value:
                    findings.add(f"{name}:{node.lineno}: 합성된 금지 토큰 {token!r}")
    return sorted(findings)


def read_violation(path: object) -> str | None:
    """① ⒜ — 열람 대상의 **해석된 경로 값**이 코퍼스·register 인지 판정한다.

    경로 문자열을 어떻게 조립했는지와 **무관**하다.  정적 스캔을 우회하는
    런타임 조립(`prefix+'spec/'` · `''.join(...)` · `chr(115)`)은 여기서
    전부 잡힌다 — 조립의 결과가 결국 이 함수에 값으로 도착하기 때문이다.

    v2.6: 판정을 `audit_guard.path_violation` 에 **위임**한다.  이전에는 같은
    판정이 두 벌 존재했고 이 벌만 대소문자를 정규화하지 않아 case 변형 경로를
    통과시켰다(심판 F3).  구현을 하나로 접으면 그 드리프트가 표현 불가능해진다.
    """
    return audit_guard.path_violation(path)


#: 디렉터리형 `.git` 이 반드시 갖는 내부 구조.  존재만 보면 **빈 파일 하나로**
#: 통과했다 (심판 #5 medium).  worktree 의 `.git` 은 파일이므로 `is_dir` 요구는
#: 정상 worktree 를 깨뜨린다 — 그래서 형태별로 다른 구조를 요구한다.
GIT_DIR_REQUIRED: tuple[str, ...] = ("HEAD", "objects", "refs")

#: 파일형 `.git` (worktree·submodule) 의 gitdir 포인터 접두사.
GIT_FILE_PREFIX = "gitdir:"


@dataclass(frozen=True)
class FsProbe:
    """파일시스템 질의 seam — 대조군이 실물을 만들지 않고 주입할 수 있게 한다.

    `.git` 위조 대조군은 실물을 만들면 그 행위 자체가 OD-3-C 위반이므로
    `forbidden_artifacts_present` 와 같은 입력 seam 패턴을 쓴다 (`L-T77-SEAM`).
    """

    exists: Callable[[Path], bool]
    is_dir: Callable[[Path], bool]
    is_file: Callable[[Path], bool]
    read_text: Callable[[Path], str]


REAL_FS = FsProbe(
    exists=lambda path: path.exists(),
    is_dir=lambda path: path.is_dir(),
    is_file=lambda path: path.is_file(),
    read_text=lambda path: path.read_text(encoding="utf-8"),
)


def git_marker_findings(root: Path, fs: FsProbe = REAL_FS) -> list[str]:
    """`root/.git` 이 **실재하는 git 표지**인지 구조로 판정한다 (v2.7, 심판 #5).

    v2.6 은 `exists()` 만 봤다.  빈 `.git` 파일 하나면 통과했고, `L-LOCATE-FORGE`
    는 "`.git` 디렉터리가 필요하다"고 적어 위조 비용을 **과대 서술**했다.

      - 디렉터리형: `HEAD`·`objects`·`refs` 가 있어야 한다.
      - 파일형(worktree·submodule): `gitdir: <경로>` 포인터여야 하고 그 대상에
        `HEAD` 가 있어야 한다.  `is_dir` 요구는 정상 worktree 를 깨뜨리므로
        형태별로 다른 구조를 요구한다.

    **여전히 막지 못하는 것**: 이 구조를 그대로 만들어 두는 적대적 준비.
    비용을 `.git` 빈 파일 1 개에서 "유효 구조 1 벌"로 올릴 뿐이다
    (`L-LOCATE-FORGE`).
    """
    dot_git = root / ".git"
    if not fs.exists(dot_git):
        return [f"repo 루트 표지(.git) 부재: {root}"]
    if fs.is_dir(dot_git):
        missing = [name for name in GIT_DIR_REQUIRED if not fs.exists(dot_git / name)]
        if missing:
            return [f".git 디렉터리에 git 내부 구조가 없다: 누락 {missing}"]
        return []
    if not fs.is_file(dot_git):
        return [".git 이 파일도 디렉터리도 아니다"]
    try:
        text = fs.read_text(dot_git).strip()
    except (OSError, UnicodeDecodeError) as exc:
        return [f".git 파일을 읽을 수 없다: {type(exc).__name__}"]
    if not text.startswith(GIT_FILE_PREFIX):
        return [f".git 파일이 gitdir 포인터가 아니다 ({len(text)}바이트)"]
    target = Path(text[len(GIT_FILE_PREFIX) :].strip())
    if not target.is_absolute():
        target = root / target
    if not fs.exists(target / "HEAD"):
        return ["gitdir 포인터 대상에 HEAD 가 없다"]
    return []


def repository_top_level(start: Path) -> Path | None:
    """`start` 에서 위로 올라가며 **처음 만나는 유효 git 루트**를 돌려준다.

    `git rev-parse --show-toplevel` 을 서브프로세스 없이 구조로 대체한다 —
    subprocess 는 어느 가드도 보지 못하는 표면이므로(`L-AUDIT-SCOPE`) 여기서
    쓰지 않는다.
    """
    for candidate in (start, *start.parents):
        if not git_marker_findings(candidate):
            return candidate
    return None


def locate_violation(runner: Path, repo_root: Path) -> list[str]:
    """④ — 러너가 **예상 위치의 repo 안**에서 도는지 관측한다.

    사본을 repo 밖에 두고 돌리면 ①⒝③ 의 기준점이 러너와 함께 이동해 경계
    검사가 자기상대적으로 참이 된다(심판 F3 부수 발견: repo 밖 실행에서도
    전건 GREEN).  위치를 관측 대상으로 고정해 그 이동을 red 로 만든다.

    v2.6 — 표지만 보는 검사는 **표지를 만들면 무력화**됐다 (심판 F3 high).
    두 겹을 더했다:
      ① 표지를 `.git` 존재로 좁힌다 (`REPO_MARKERS` 주석 참조).
      ② 예상 상대경로에 **실물이 있고 그것이 실행 중인 러너와 같은 파일**인지
         `os.path.samefile` 로 확인한다.

    v2.7 — ① 은 `exists()` 뿐이라 **빈 `.git` 파일 하나로 통과**했다 (심판 #5).
    세 겹을 더한다:
      ③ `.git` 의 **형태별 내부 구조**를 요구한다 (`git_marker_findings`).
      ④ 러너에서 위로 올라가 만나는 **실제 repository top-level** 이 기대 루트와
         같은지 확인한다 — 하위 디렉터리에 표지를 심어 루트를 옮기는 경로를 막는다.

    **완전 위조는 막지 못한다**: 유효한 `.git` 구조 한 벌을 만들고 러너 사본을
    예상 상대경로에 두면 이 검사는 통과한다.  위치 앵커는 *이동* 을 관측하는
    장치이지 적대적 준비를 이기는 장치가 아니다 (`L-LOCATE-FORGE`).
    """
    findings: list[str] = []
    findings.extend(git_marker_findings(repo_root))
    top = repository_top_level(runner.resolve().parent)
    if top is None:
        findings.append(f"러너 위쪽에 유효한 git 루트가 없다: {runner}")
    elif top.resolve() != repo_root.resolve():
        findings.append("실제 repository top-level 이 기대 루트와 다르다")
    try:
        rel = runner.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        findings.append(f"러너가 repo 루트 밖에 있다: {runner}")
        return findings
    if rel != EXPECTED_RUNNER_RELPATH:
        findings.append(f"러너 위치 이탈: {rel} != {EXPECTED_RUNNER_RELPATH}")
    expected = repo_root / EXPECTED_RUNNER_RELPATH
    try:
        if not os.path.samefile(expected, runner):
            findings.append(f"예상 경로의 파일이 실행 중인 러너와 다르다: {expected}")
    except OSError:
        findings.append(f"예상 경로에 러너 실물이 없다: {expected}")
    return findings


def read_prototype_sources(root: Path, extra: Iterable[Path] = ()) -> dict[str, str]:
    """스캔 대상 소스를 읽는다 (읽기는 허용된다)."""
    sources: dict[str, str] = {}
    for path in sorted(root.glob("*.py")):
        sources[path.name] = path.read_text(encoding="utf-8")
    for path in sorted(root.glob("*.yaml")):
        sources[path.name] = path.read_text(encoding="utf-8")
    for path in extra:
        sources[path.name] = path.read_text(encoding="utf-8")
    return sources


def forbidden_artifacts_present(
    exists: Callable[[str], bool], repo_root: Path
) -> list[str]:
    """③ 금지 아티팩트가 존재하는지."""
    return [
        f"금지 아티팩트 생성됨: {rel}"
        for rel in FORBIDDEN_ARTIFACTS
        if exists(str(repo_root / rel))
    ]


def _is_write_mode(mode: object) -> bool:
    if isinstance(mode, str):
        return bool(_WRITE_FLAG_CHARS & set(mode))
    if isinstance(mode, int):
        write_bits = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
        return bool(mode & write_bits)
    return False


@contextmanager
def read_guard():
    """① ⒜ 코퍼스·register **열람**을 탐지하고 차단한다 — **심층 방어**.

    강제 지점이 경로 **값**이므로 문자열 조립 방식과 무관하다 — v2.3 의 정적
    스캔이 뚫린 원인(프록시로 강제했다)을 구조적으로 제거한다.

    **정본은 이 가드가 아니라 `audit_guard` 의 프로세스 전역 hook 이다** (v2.6).
    이 층은 `main()` 안에서만 열리므로 import 시점을 덮지 못하고, 감싸는 범위도
    `READ_GUARDED_ENTRY_POINTS` 가 전부다 — 이미 열린 파일 객체·fd, C 확장의
    직접 read, `subprocess`, 가드 진입 **전에** 바인딩된 참조, `_io.open` 같은
    별칭은 덮지 못한다.  **전부 막았다고 주장하지 않는다.**
    """
    recorder = ReadRecorder()
    saved: list[tuple[object, str, object]] = []

    def _check(kind: str, path: object) -> None:
        violation = read_violation(path)
        if violation is None:
            return
        recorder.attempts.append(f"{kind}:{violation}")
        raise BoundaryViolation(f"코퍼스·register 열람 차단: {kind} -> {violation}")

    def _patch(owner: object, attr: str, replacement: object) -> None:
        if not hasattr(owner, attr):
            return
        saved.append((owner, attr, getattr(owner, attr)))
        setattr(owner, attr, replacement)

    real_open = builtins.open
    real_io_open = io.open
    real_os_open = os.open
    real_os_listdir = os.listdir
    real_os_scandir = os.scandir
    real_path_open = Path.open
    real_path_read_text = Path.read_text
    real_path_read_bytes = Path.read_bytes

    def guarded_open(file, *args, **kwargs):
        _check("open", file)
        return real_open(file, *args, **kwargs)

    def guarded_io_open(file, *args, **kwargs):
        _check("io.open", file)
        return real_io_open(file, *args, **kwargs)

    def guarded_os_open(path, *args, **kwargs):
        _check("os.open", path)
        return real_os_open(path, *args, **kwargs)

    def guarded_os_listdir(path=".", *args, **kwargs):
        _check("os.listdir", path)
        return real_os_listdir(path, *args, **kwargs)

    def guarded_os_scandir(path=".", *args, **kwargs):
        _check("os.scandir", path)
        return real_os_scandir(path, *args, **kwargs)

    def guarded_path_open(self, *args, **kwargs):
        _check("Path.open", self)
        return real_path_open(self, *args, **kwargs)

    def guarded_path_read_text(self, *args, **kwargs):
        _check("Path.read_text", self)
        return real_path_read_text(self, *args, **kwargs)

    def guarded_path_read_bytes(self, *args, **kwargs):
        _check("Path.read_bytes", self)
        return real_path_read_bytes(self, *args, **kwargs)

    _patch(builtins, "open", guarded_open)
    _patch(io, "open", guarded_io_open)
    _patch(os, "open", guarded_os_open)
    _patch(os, "listdir", guarded_os_listdir)
    _patch(os, "scandir", guarded_os_scandir)
    _patch(Path, "open", guarded_path_open)
    _patch(Path, "read_text", guarded_path_read_text)
    _patch(Path, "read_bytes", guarded_path_read_bytes)
    try:
        yield recorder
    finally:
        for owner, attr, original in reversed(saved):
            setattr(owner, attr, original)


@contextmanager
def write_guard():
    """② 실행 중 파일 쓰기를 탐지하고 **차단**한다 — **심층 방어**.

    **정본은 `audit_guard` 의 프로세스 전역 hook 이다** (v2.6).  이 층은
    `main()` 안에서만 열리고 감싸는 범위는 `GUARDED_ENTRY_POINTS` 가 전부다.
    그 밖 — 이미 열린 파일 객체·fd 로의 쓰기, C 확장의 직접 write,
    `subprocess` 로 띄운 프로세스, 가드 진입 **전에** 바인딩된 함수 참조 — 은
    덮지 못한다.  **전부 막았다고 주장하지 않는다.**
    """
    recorder = WriteRecorder()
    saved: list[tuple[object, str, object]] = []

    def _block(kind: str, target: object):
        recorder.attempts.append(f"{kind}:{target}")
        raise BoundaryViolation(f"파일 쓰기 시도 차단: {kind} -> {target}")

    def _blocker(kind: str):
        def wrapper(*args, **kwargs):
            _block(kind, args[0] if args else "")

        return wrapper

    def _patch(owner: object, attr: str, replacement: object) -> None:
        if not hasattr(owner, attr):
            return
        saved.append((owner, attr, getattr(owner, attr)))
        setattr(owner, attr, replacement)

    real_open = builtins.open
    real_io_open = io.open
    real_os_open = os.open
    real_os_fdopen = os.fdopen
    real_os_write = os.write

    def guarded_open(file, mode="r", *args, **kwargs):
        if _is_write_mode(mode):
            _block("open", file)
        return real_open(file, mode, *args, **kwargs)

    def guarded_io_open(file, mode="r", *args, **kwargs):
        if _is_write_mode(mode):
            _block("io.open", file)
        return real_io_open(file, mode, *args, **kwargs)

    def guarded_os_open(path, flags, *args, **kwargs):
        if _is_write_mode(flags):
            _block("os.open", path)
        return real_os_open(path, flags, *args, **kwargs)

    def guarded_os_fdopen(fd, mode="r", *args, **kwargs):
        if _is_write_mode(mode):
            _block("os.fdopen", fd)
        return real_os_fdopen(fd, mode, *args, **kwargs)

    def guarded_os_write(fd, data, *args, **kwargs):
        # stdout/stderr 는 통과시킨다 — 보고 자체가 막히면 진단이 불가능하다.
        # 그 예외가 곧 이 가드의 seam 이며 한계로 명시한다.
        if fd not in (0, 1, 2):
            _block("os.write", fd)
        return real_os_write(fd, data, *args, **kwargs)

    _patch(builtins, "open", guarded_open)
    _patch(io, "open", guarded_io_open)
    _patch(os, "open", guarded_os_open)
    _patch(os, "fdopen", guarded_os_fdopen)
    _patch(os, "write", guarded_os_write)
    for attr in _OS_BLOCKED:
        _patch(os, attr, _blocker(f"os.{attr}"))
    for attr in _SHUTIL_BLOCKED:
        _patch(shutil, attr, _blocker(f"shutil.{attr}"))
    for attr in _PATH_BLOCKED:
        _patch(Path, attr, _blocker(f"Path.{attr}"))
    try:
        yield recorder
    finally:
        for owner, attr, original in reversed(saved):
            setattr(owner, attr, original)
