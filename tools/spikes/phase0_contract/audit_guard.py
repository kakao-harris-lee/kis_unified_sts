"""프로세스 전역 감사 hook — OD-3-A/C 강제의 **정본** (v2.7, 심판 F3+#3#4#6).

## 왜 이 파일이 `proto/` 밖의 최상위 모듈인가

v2.5 까지 열람·쓰기 가드는 `proto/boundary.py` 의 monkeypatch 였고 `main()`
안에서 열렸다.  피검사 모듈(`proto/*`)의 **import 는 그보다 먼저** 일어나므로
모듈 레벨 문장이 가드 창 **밖**에서 실행됐다.  심판은 그 창으로 실제 register
93,904 바이트를 읽고도 exit 0 · 전건 GREEN · 열람 기록 없음을 재현했다.

`sys.addaudithook` 은 인터프리터 수준에서 발화하므로 monkeypatch 로 갈아끼운
참조·별칭(`_io.open` 등)과 무관하다.  이 모듈은 **import 되는 순간** hook 을
설치하고, 러너는 `proto` 보다 **먼저** 이 모듈을 import 한다.

## v2.7 — 설치 지점을 모듈 본문 최상단으로 올렸다 (심판 #3 high)

v2.6 은 hook 을 파일 **끝**(:220)에서 설치했다.  그 앞의 모듈 본문 — 상수 대입,
클래스·함수 정의 — 은 무보호였고, "bootstrap 부터 armed" 라는 주장이 그만큼
넓지 않았다.  v2.7 은 hook 이 **참조하는 상태만** 앞에 두고 그 직후 설치한다.

**v2.8 정정 (심판 v2.7 #4).**  v2.7 은 여기에 "설치 앞의 실행 가능한 문장은
0 개" 라고 적었다.  그 진술은 **거짓**이었다 — 러너의 분류가 `ast.Assign` 을
우변과 무관하게 비실행문으로 세었기 때문에 나온 정의상의 산물이고, 실제로는
`frozenset(...)` · `threading.local()` · `.casefold()` 같은 **호출을 포함한 대입이
열한 개** 있다.  v2.8 은 우변에 실행 노드가 있으면 실행문으로 세고, 그 **개수를
설정(`anchor_prehook_executable`)에 핀으로 고정**한다.  구간은 `ast.unparse`
digest 로도 고정되므로 새 문장은 설정 diff 를 요구한다 — 실행문이 0 이라는
구조 요구사항은 없다.

설치 시점의 `sys.modules` 스냅샷을 남긴다(`bootstrap_witness`).  피검사 모듈이
그 스냅샷에 **없었음**을 러너가 검증하므로 "hook 이 서기 전에 proto 가 이미
로드됐다" 는 상태가 red 가 된다.

**주장의 정확한 한계** (`L-AUDIT-BOOTSTRAP` 으로 등재):
  - 이 모듈이 import 되기 **전에** 실행된 것 — 인터프리터 기동, `site`,
    러너 자신의 pre-hook 구간(`import audit_guard` 앞의 문장들) — 은 hook 밖이다.
    러너의 그 구간은 소스 digest 로 고정하고 동적 로드 호출을 fail-closed 로
    거부하지만, **그 구간이 armed 상태인 것은 아니다.**
  - 다른 진입점이 `proto` 를 먼저 import 한 뒤 이 모듈을 import 하면 스냅샷
    검증이 red 를 낸다 — 그것은 차단이 아니라 **사후 검출**이다.
  - **v2.9 정정 (심판 v2.8 #3)**: 위의 "실행문 개수" 는 러너의 분류가 보는
    정의역 안에서만 정직하다.  그 분류는 최상위 문장의 우변·데코레이터·기본
    인자만 걷고 **`ClassDef` 본문은 걷지 않는다.**  클래스 본문은 import 시
    즉시 실행되므로, pre-hook 구간에 클래스 본문을 두고 그 안에서 파일을 열면
    실행문 개수는 그대로다 (실측: `_io.FileIO(...).readall()` 로 register 15,736
    바이트를 읽어도 계수 1 불변).  `FileIO`·`readall` 은 금지 이름 목록에도
    없다.  그 형태를 잡는 층은 함께 갱신 가능한 구간 digest 와 소스 바이트·
    실행코드 앵커뿐이며(러너의 같은 취지 노트와 같은 3 종이다), 그것은 차단이
    아니라 고정이다.

## 이 층이 exit 에 닿는 방식과 그 **종단 한계**

이 모듈은 종료 코드를 결정하지 않는다.  기록(`blocked_*`·`probe_*`)과 정책
상태를 남길 뿐이고, 그것을 종료 판정에 싣는 것은 러너의 운영 게이트다.
**그 판정 지점 자체는 같은 프로세스 안에서 자기 절단을 검출할 수 없다** —
러너의 `L-EXIT-ROOT` 가 그 구조적 한계를 등재하며, 해소는 별도 프로세스의
외부 검증자뿐이고 설정 `deferred_owner_tracks`/`required_deferrals` 에 기록된
owner track 으로 이연됐다 (v2.9 — 트랙 값을 여기 리터럴로 적지 않는다.  v2.9
후속 정정: 러너는 그 두 줄의 일치만 보고 트랙 값 자체는 고정하지 않는다).
따라서 이 파일의 어떤 서술도 "여기 기록되면 반드시 비영 종료한다" 를 뜻하지
않는다.

## 정책은 설치가 아니라 **모듈 상태**다

audit hook 은 설계상 **해제할 수 없다**.  따라서 install/uninstall 이 아니라
모듈 레벨 정책 상태(`_READ_ARMED` · `_WRITE_ARMED`)를 hook 이 매 이벤트마다
참조한다.  둘 다 설치 시점부터 armed 이고 이 러너는 어느 쪽도 내리지 않는다.
러너의 운영 게이트가 종료 시점에 그 상태와 `probe_depth()` 를 다시 확인한다.

## 재진입 격리 (v2.7, 심판 #4 high)

v2.6 의 `_REENTRANT` 는 **모듈 전역 boolean** 이었다.  한 스레드가 `_enforce`
안에 있는 동안 다른 스레드의 watched event 가 전부 무시됐다.  v2.7 은 재진입
상태를 `threading.local` 로 격리한다 — 대조군이 "한 스레드의 재진입 상태를 켠
채 다른 스레드에서 코퍼스를 열면 차단된다" 를 실측한다.

또 `os.fsdecode(path)` 는 임의 `PathLike.__fspath__` — **사용자 콜백** — 을
부를 수 있었다.  hook 안에서 사용자 코드를 부르면 같은 스레드 재진입 창이
열린다.  v2.7 은 해석 대상 타입을 **정확 일치 화이트리스트**로 좁히고 그 밖의
객체는 판정하지 않고 **차단**한다 (fail-closed).

## 이 층이 덮지 **못하는** 것 (한계 — `L-AUDIT-SCOPE` 로 등재)

  - **이미 열린 fd 로의 read/write**.  `open` 이벤트는 여는 시점에만 발화하고
    `os.write(fd, ...)` 에는 감사 이벤트 자체가 없다.  fd 는 경로로 되돌릴 수
    없으므로 판정 대상이 아니다.
  - `mmap` 쓰기, C 확장이 libc 를 직접 부르는 경로, `subprocess` 로 띄운
    별도 프로세스, `ctypes` 직접 syscall.
  - 감사 이벤트 이름 목록(`READ_EVENTS`·`WRITE_EVENTS`)은 **열거**다.  열거 밖
    이벤트는 보지 않는다.  `open` 하나가 `builtins.open`·`io.open`·`os.open`·
    `_io.open`·`_io.FileIO`·`open_code` 를 전부 덮는다는 점이 이 열거가 짧아도
    되는 이유이며, 그 사실은 대조군이 실측한다.
  - **inode 별칭** (`L-INODE-ALIAS`).  아래 "정책 정의역" 참조.

## 정책 정의역 = **경로명** 이다 (v2.7, 심판 #6 medium — 선택지 (B))

`path_violation` 은 **해석된 경로명**의 순수 함수다.  보호 대상의 기존
hardlink 가 무해한 이름을 갖고 있으면 `resolve()` 로 원본 이름이 복원되지
않으므로 같은 inode 를 다른 이름으로 읽을 수 있다.

`st_dev`/`st_ino` 대조(선택지 (A))는 **이 프로토타입에서 성립하지 않는다**:
보호 대상의 canonical identity 집합을 만들려면 코퍼스 디렉터리를 열거해야 하고,
그 열거 자체가 OD-3-A 위반이다.  정책을 확장하는 대신 **정책을 경로명 차단으로
명시 축소**하고 그 한계를 `L-INODE-ALIAS` 로 등재한다.  과대주장하지 않는다.

## 경로 동치 (심판 F3 high)

`read_violation` 은 대소문자가 다른 경로를 통과시켰다(APFS 는 case-insensitive
이므로 `samefile=True` 인데 판정은 False).  여기서는 **casefold 정규화**로
비교한다.  case-sensitive 파일시스템에서는 이름만 같고 실제로 다른 디렉터리도
차단되는 과잉 차단이 되지만 fail-closed 방향이므로 그대로 둔다(`L-CASEFOLD`).
"""

from __future__ import annotations

import os
import sys
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import (
    Path,
    PosixPath,
    PurePath,
    PurePosixPath,
    PureWindowsPath,
    WindowsPath,
)

# === bootstrap 구간 ==========================================================
# 여기부터 `sys.addaudithook(_hook)` 까지는 상수 대입과 정의만 둔다.  다만
# **그 대입 중 일부는 호출식을 평가한다** — 러너는 그것을 실행문으로 세고
# (v2.8 정정), 개수를 설정 핀 `anchor_prehook_executable` 에 고정하며 구간
# 전체를 `ast.unparse` digest 로도 고정한다.  실행문 0 은 요구사항이 아니다.
# 이 구간은 armed 가 **아니다** — 고정될 뿐 차단되지 않는다.

# .pyc 쓰기도 파일 쓰기다 (OD-3-C).  러너도 같은 줄을 두지만, 이 모듈이 다른
# 진입점에서 import 될 때를 위해 여기서도 세운다.
sys.dont_write_bytecode = True

#: 금지 토큰의 **정의 지점**.  AST 스캔의 유일한 면제 지점이며
#: (`boundary.TOKEN_DEFINITION_SITE`), 검사기·가드가 같은 조각에서 파생하므로
#: 둘이 따로 놀 수 없다.  리터럴로 적으면 이 파일 자신이 스캔에 걸린다.
CORPUS_DIR = "tos-" + "spec/"
REGISTER_PREFIX = "EVIDENCE-" + "REGISTER-"

CORPUS_DIRNAME = CORPUS_DIR.rstrip("/")
SPEC_DIR = CORPUS_DIRNAME

_CORPUS_FOLDED = CORPUS_DIRNAME.casefold()
_REGISTER_FOLDED = REGISTER_PREFIX.casefold()

_WRITE_MODE_CHARS = frozenset("wax+")
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC

#: 열람 계열 — 코퍼스·register 경로면 arm 여부와 무관하게 차단 대상이다.
#: `open` 하나가 `builtins.open`/`io.open`/`os.open`/`_io.open`/`io.FileIO`/
#: `open_code` 전부에서 발화한다 (실측: 대조군 `T-77-AUDIT`).
READ_EVENTS: tuple[str, ...] = ("open", "os.listdir", "os.scandir")

#: 쓰기 계열 — 이 이름이 발화하면 그 자체가 쓰기다.
WRITE_EVENTS: tuple[str, ...] = (
    "os.rename",
    "os.remove",
    "os.rmdir",
    "os.mkdir",
    "os.truncate",
    "os.link",
    "os.symlink",
    "os.utime",
    "os.chmod",
    "os.chown",
    "shutil.copyfile",
    "shutil.copymode",
    "shutil.copystat",
    "shutil.copytree",
    "shutil.move",
    "shutil.rmtree",
    "shutil.unpack_archive",
)

_READ_EVENT_SET = frozenset(READ_EVENTS)
_WRITE_EVENT_SET = frozenset(WRITE_EVENTS)
_WATCHED = _READ_EVENT_SET | _WRITE_EVENT_SET

#: **정확 일치** 화이트리스트.  `__fspath__` 는 사용자 콜백이므로 hook 안에서
#: 임의 객체에 대해 부를 수 없다 (심판 #4).  여기 없는 타입은 해석하지 않고
#: 차단한다 — 서브클래스도 `__fspath__` 를 덮어쓸 수 있으므로 `isinstance` 가
#: 아니라 `type(...) in` 으로 본다.
_SAFE_PATH_TYPES = frozenset(
    {
        str,
        bytes,
        Path,
        PosixPath,
        PurePath,
        PurePosixPath,
        PureWindowsPath,
        WindowsPath,
        os.DirEntry,
    }
)

#: 가드가 차단한 기록.  인가된 프로브 창 **밖**에서 쌓인 것이 헤드라인 신호다.
#: **러너의 운영 게이트가 이 목록을 exit status 에 직접 결속한다** (심판 #2).
#: v2.8: `probe_*` 도 더 이상 결속 밖이 아니다 — 토큰별 개수가 설정 앵커
#: `anchor_probe_records` 에 묶여 있어 인가된 창 안의 기록이 늘거나 줄어도 red 다.
blocked_reads: list[str] = []
blocked_writes: list[str] = []
probe_reads: list[str] = []
probe_writes: list[str] = []

#: 대조군이 **의도적으로** 창 밖에서 만든 뒤 `claim_operational_records()` 로
#: 이관한 기록.  운영 위반과 섞이지 않도록 분리하며, 이관은 개수가 정확히
#: 맞을 때만 성립한다 — 잉여 위반이 대조군 뒤에 숨는 경로를 막는다.
sanctioned_reads: list[str] = []

#: 인가된 프로브 창의 **고정 호출 지점** (v2.8, 심판 v2.7 #3).
#: `토큰 -> "파일:함수"`.  `probe_window()` 는 호출자 프레임에서 파생한 실제
#: 호출 지점이 이 표와 **일치할 때만** 기록을 프로브로 분류한다.  창 깊이만
#: 보던 v2.7 은 창이 열린 동안 **아무 코드의 아무 위반**이든 exit 결속에서
#: 이탈시켰다 — 분류의 근거를 깊이에서 **capability(토큰)+호출 지점**으로
#: 옮겼다.  이 표 자체는 값 앵커에 결속된다.
#:
#: **v2.9 정정 (심판 v2.8 #2)**: 이것은 통로를 닫지 않는다.  토큰은 이 표에
#: 그대로 적힌 공개 문자열이고 호출 지점은 `basename(co_filename):co_name`
#: 이라, `compile(src, "test_contracts.py", "exec")` 로 같은 이름의 함수를
#: 만들면 임의 코드가 인가 판정을 받는다.  한계는 `L-AUDIT-PROBE-THREAD`.
PROBE_SITES: dict[str, str] = {
    "t77-audit-battery": "test_contracts.py:t77_boundary",
    "t77-reentrant": "test_contracts.py:t77_boundary",
    "t77-cross-thread": "test_contracts.py:_cross_thread_probe",
    "t77-separation": "test_contracts.py:t77_boundary",
}

#: 인가되지 않은 창을 연 시도.  창을 여는 것만으로도 관측되며 러너의 운영
#: 게이트가 exit 에 결속한다 — 열어 놓고 아무 위반도 하지 않아도 red 다.
unsanctioned_windows: list[str] = []

_READ_ARMED = True
_WRITE_ARMED = True

#: 프로브 창은 **스레드 지역**이다 (v2.8).  전역 깊이이던 시절 러너 자신이
#: 창 안에서 워커 스레드를 돌렸고, 그 시간에 **다른 스레드에서** 난 진짜
#: 위반이 프로브 버킷으로 새 exit 결속을 벗어났다.
_PROBE = threading.local()

#: 전 스레드 합계 — 종료 시점에 0 이 아니면 창이 열린 채 끝난 것이다.
_PROBE_DEPTH = 0
_PROBE_LOCK = threading.Lock()

#: 재진입 상태는 **스레드 지역**이다 (v2.7, 심판 #4).  전역 boolean 이던 시절
#: 한 스레드의 `_enforce` 진입이 프로세스 전체를 무장 해제했다.
_REENTRANT = threading.local()


class AuditViolation(RuntimeError):
    """감사 hook 이 **차단**한 경계 위반.  탐지와 차단이 같은 지점이다."""


def path_violation(path: object) -> str | None:
    """열람 대상의 **해석된 경로명**이 코퍼스·register 인지 판정한다.

    문자열을 어떻게 조립했는지와 **무관**하다 — 조립의 결과가 결국 값으로
    도착하기 때문이다.  대소문자는 casefold 로 정규화한다.

    **정의역은 경로명이다** — inode 별칭은 보지 않는다 (`L-INODE-ALIAS`).
    이 함수는 `stat`/`open` 을 부르지 않는 경로명 순수 함수이며, 그 사실을
    대조군이 이 파일의 AST 에서 파생해 관측한다.

    타입은 **정확 일치** 화이트리스트로 좁힌다.  `__fspath__` 는 사용자 콜백
    이므로 hook 안에서 임의 객체에 대해 부르면 재진입 창이 열린다 (심판 #4).
    화이트리스트 밖 객체는 판정하지 않고 **차단**한다 (fail-closed).

    `boundary.read_violation` 은 이 함수에 위임한다 — 구현이 하나뿐이므로
    두 층의 판정이 드리프트할 수 없다.
    """
    if isinstance(path, int) and not isinstance(path, bool):
        return None  # 이미 열린 fd 는 경로를 되돌릴 수 없다 (한계).
    if path is None:
        # `os.scandir()` 등의 기본 인자.  cwd 를 판정한다 — `os.getcwd` 는
        # 감사 이벤트를 내지 않고 사용자 콜백도 부르지 않는다.
        text: str = os.getcwd()
    elif type(path) in _SAFE_PATH_TYPES:
        try:
            text = os.fsdecode(path)
        except (TypeError, ValueError):
            return f"경로 해석 실패(fail-closed): {type(path).__name__}"
    else:
        return f"판정 불가 경로 타입(fail-closed): {type(path).__name__}"
    try:
        resolved = Path(text).resolve()
    except (OSError, ValueError, RuntimeError):
        resolved = Path(text)
    if any(part.casefold() == _CORPUS_FOLDED for part in resolved.parts):
        return f"코퍼스 디렉터리 접근: {resolved}"
    if resolved.name.casefold().startswith(_REGISTER_FOLDED):
        return f"register 파일 접근: {resolved}"
    return None


def _is_write_open(args: tuple) -> bool:
    """`open` 이벤트의 (path, mode, flags) 가 쓰기인지."""
    mode = args[1] if len(args) > 1 else None
    flags = args[2] if len(args) > 2 else None
    if isinstance(mode, str) and _WRITE_MODE_CHARS & set(mode):
        return True
    return isinstance(flags, int) and bool(flags & _WRITE_FLAGS)


def _active_probe_token() -> str | None:
    """**이 스레드**가 지금 들고 있는 인가된 프로브 토큰 (없으면 None)."""
    stack = getattr(_PROBE, "tokens", None)
    return stack[-1] if stack else None


def _record(reads: bool, text: str) -> None:
    """기록을 분류한다 — 인가된 토큰을 **이 스레드가** 들고 있을 때만 프로브다.

    v2.7 은 프로세스 전역 깊이로 분류해서 창이 열린 동안 다른 스레드의 위반도
    프로브가 됐고, 프로브 버킷은 exit 에 결속되지 않았다.  분류 근거를 토큰으로
    옮기고 토큰을 기록에 함께 실어 **어느 호출 지점 몫인지**를 남긴다 — 러너의
    운영 게이트는 그 **토큰별 개수**를 설정 앵커와 대조한다 (v2.9 정정, 심판
    v2.8 #2: v2.8 은 "identity 와 개수" 라고 적었으나 본문은 세지 않는다).
    """
    token = _active_probe_token()
    if token is None:
        (blocked_reads if reads else blocked_writes).append(text)
        return
    (probe_reads if reads else probe_writes).append(f"{token}\x1f{text}")


def _enforce(event: str, args: tuple) -> None:
    if _READ_ARMED:
        for arg in args:
            violation = path_violation(arg)
            if violation is None:
                continue
            record = f"{event}:{violation}"
            _record(True, record)
            raise AuditViolation(f"코퍼스·register 접근 차단: {record}")
    if not _WRITE_ARMED:
        return
    # 쓰기 계열 이벤트는 발화 자체가 쓰기다.  `open` 만 모드·플래그를 봐야 한다.
    if event not in _WRITE_EVENT_SET and not (event == "open" and _is_write_open(args)):
        return
    record = f"{event}:{args[0] if args else ''}"
    _record(False, record)
    raise AuditViolation(f"파일 쓰기 차단: {record}")


def _hook(event: str, args: tuple) -> None:
    """감사 hook 본체.  이름으로 조기 필터링한다 — 이벤트는 매우 잦다.

    재진입 상태는 **이 스레드에 한정**된다 — 다른 스레드는 그대로 무장 상태다.
    """
    if event not in _WATCHED:
        return
    if getattr(_REENTRANT, "active", False):
        return
    _REENTRANT.active = True
    try:
        _enforce(event, args)
    finally:
        _REENTRANT.active = False


#: 설치 **직전**의 `sys.modules` 스냅샷.  피검사 모듈이 여기 있으면 그 모듈의
#: 본문은 hook 밖에서 돌았다는 뜻이다 — 러너가 `bootstrap_witness()` 로 검증한다.
_ARMED_SNAPSHOT: frozenset[str] = frozenset(sys.modules)

sys.addaudithook(_hook)

# === bootstrap 끝 — 여기부터는 hook 이 armed 인 상태에서 실행된다 =============


def policy() -> dict[str, object]:
    """현재 정책 상태 — 보고용.  자기신고이므로 강제의 근거는 아니다.

    v2.8: `watched` 를 함께 보고한다.  `_hook` 의 조기 필터는 `_WATCHED` 인데
    v2.7 의 `policy()` 는 그것을 보지 않아서, `_WATCHED` 를 비워 강제를 전면
    해제해도 `armed=True` 를 계속 인쇄했다 (자기신고와 실제의 괴리).
    """
    return {
        "read_armed": _READ_ARMED,
        "write_armed": _WRITE_ARMED,
        "watched": len(_WATCHED),
        "probe_depth": _PROBE_DEPTH,
        "probe_sites": len(PROBE_SITES),
        "reentrancy": "thread-local",
        "read_events": READ_EVENTS,
        "write_events": WRITE_EVENTS,
    }


def probe_depth() -> int:
    """열려 있는 **인가된** 창의 전 스레드 합계.  종료 시 0 이 아니면 샌 것이다."""
    return _PROBE_DEPTH


def safe_path_types() -> tuple[str, ...]:
    """해석을 허용하는 경로 타입 목록 — 값 앵커의 대상이다.

    타입 객체가 아니라 이름으로 돌려준다: digest 가 `repr` 형식에 의존하지
    않게 하고, 목록이 좁아지는(=차단이 늘어나는) 편집도 넓어지는 편집도
    똑같이 관측되게 한다.
    """
    return tuple(sorted(item.__name__ for item in _SAFE_PATH_TYPES))


def armed() -> tuple[bool, bool]:
    """(열람 armed, 쓰기 armed) — 운영 게이트가 종료 시점에 다시 확인한다."""
    return _READ_ARMED, _WRITE_ARMED


def bootstrap_witness(names: Sequence[str]) -> list[str]:
    """설치 시점 `sys.modules` 에 `names` 접두사가 **없었음**을 검증한다.

    스냅샷이 비었거나 표준 모듈조차 없으면 스냅샷 자체가 위조된 것이므로
    fail-closed 로 findings 를 낸다.
    """
    findings: list[str] = []
    if not {"sys", "os", "builtins"} <= _ARMED_SNAPSHOT:
        findings.append("설치 시점 스냅샷이 실재 스냅샷이 아니다")
    for prefix in names:
        present = sorted(
            name
            for name in _ARMED_SNAPSHOT
            if name == prefix or name.startswith(prefix + ".")
        )
        if present:
            findings.append(f"hook 설치 전에 이미 로드됨: {present}")
    return findings


def snapshot_size() -> int:
    """설치 시점 스냅샷의 모듈 수 — 보고용."""
    return len(_ARMED_SNAPSHOT)


class _ProbeWindow:
    """`probe_window()` 가 돌려주는 창.  인가 판정은 **생성 시점**에 끝난다.

    인가되지 않은 창은 토큰을 밀지 않는다 — 그 창 안에서 난 기록은 전부 운영
    버킷에 남아 exit 에 결속된다.  그리고 창을 연 시도 자체가
    `unsanctioned_windows` 에 남아 별도 findings 가 된다.
    """

    def __init__(self, token: str, site: str) -> None:
        self.token = token
        self.site = site
        self.sanctioned = PROBE_SITES.get(token) == site

    def __enter__(self) -> list[str]:
        global _PROBE_DEPTH
        if not self.sanctioned:
            unsanctioned_windows.append(f"{self.token}@{self.site}")
            return probe_reads
        stack = getattr(_PROBE, "tokens", None)
        if stack is None:
            stack = []
            _PROBE.tokens = stack
        stack.append(self.token)
        with _PROBE_LOCK:
            _PROBE_DEPTH += 1
        return probe_reads

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        global _PROBE_DEPTH
        if not self.sanctioned:
            return False
        _PROBE.tokens.pop()
        with _PROBE_LOCK:
            _PROBE_DEPTH -= 1
        return False


def probe_window(token: str) -> _ProbeWindow:
    """대조군 프로브 창 — **capability(토큰) + 고정 호출 지점**으로 인가한다.

    분리는 **진단 편의**가 아니다: `blocked_*` 만 exit 에 결속되므로 분류는
    **exit 결속 여부 그 자체**다 (v2.7 부터).  v2.8 은 창을 여는 것만으로 분류가
    바뀌던 통로에 값을 매겼다 — 토큰이 `PROBE_SITES` 에 있고 **실제 호출자
    프레임의 파일·함수**가 그 표와 일치할 때만 창이 인가된다.

    차단 자체는 창 안팎이 동일하다 — 창 안에서도 똑같이 `AuditViolation` 이 난다.
    인가된 창의 기록은 토큰이 함께 실려 남고, 러너의 운영 게이트가 그 **토큰별
    개수**를 설정 앵커(`anchor_probe_records`)와 대조한다.

    창은 **스레드 지역**이다 — 창을 연 스레드의 기록만 프로브가 되고 다른
    스레드의 위반은 그대로 운영 버킷에 남는다 (`L-AUDIT-PROBE-THREAD`).

    **v2.9 정정 (심판 v2.8 #2).**  v2.8 은 여기에 "그 **identity 와 개수**를
    대조한다" 고 적었다.  거짓이었다 — 게이트는 개수만 센다.  그리고 인가
    identity 는 공개 문자열 토큰과 `basename(co_filename):co_name` 뿐이라
    `compile()` 의 filename·함수명을 맞춘 임의 코드가 그대로 인가된다.  창이
    호출자에게 돌려주는 것도 **가변 `probe_reads` 그 자체**이므로, 사칭한 창에서
    같은 개수의 다른 내용으로 치환하면 `unsanctioned_windows` 와 개수 앵커가
    둘 다 침묵한다 (실측 확인).  한계는 `L-AUDIT-PROBE-THREAD` 에 등재했다.
    """
    frame = sys._getframe(1)
    site = f"{os.path.basename(frame.f_code.co_filename)}:{frame.f_code.co_name}"
    return _ProbeWindow(token, site)


def probe_record_counts() -> dict[str, tuple[int, int]]:
    """인가된 프로브 기록을 **토큰별 (열람, 쓰기) 개수**로 접는다.

    러너의 운영 게이트가 이 값을 설정 앵커와 대조하므로, 인가된 창 안에서
    기록이 하나라도 늘거나 줄면 종료 코드가 뒤집힌다.

    **개수만 센다** (v2.9 정정, 심판 v2.8 #2).  기록 **본문**은 어느 층도 보지
    않으므로 같은 개수의 내용 치환은 이 값을 움직이지 않는다.
    `L-AUDIT-PROBE-THREAD` 참조.
    """
    counts: dict[str, list[int]] = {}
    for records, index in ((probe_reads, 0), (probe_writes, 1)):
        for item in records:
            token = item.split("\x1f", 1)[0]
            counts.setdefault(token, [0, 0])[index] += 1
    return {token: (pair[0], pair[1]) for token, pair in sorted(counts.items())}


@contextmanager
def reentrancy_probe() -> Iterator[None]:
    """대조군 전용 — **이 스레드**의 재진입 상태를 켠 채로 블록을 실행한다.

    전역 boolean 이던 시절 이 상태는 프로세스 전체를 무장 해제했다.  스레드
    지역으로 옮긴 뒤 **다른 스레드가 그대로 차단되는지**를 대조군이 실측한다.
    """
    _REENTRANT.active = True
    try:
        yield
    finally:
        _REENTRANT.active = False


def reentrancy_is_thread_local() -> bool:
    """재진입 상태가 `threading.local` 인가 — 구조 파생(자기신고 아님)."""
    return isinstance(_REENTRANT, threading.local)


def reentrancy_active() -> bool:
    """**이 스레드**가 지금 hook 안에 있는가.

    대조군이 "사용자 콜백이 hook 안에서 불렸는가" 를 직접 관측하는 데 쓴다.
    """
    return bool(getattr(_REENTRANT, "active", False))


def claim_operational_records(count: int) -> list[str]:
    """창 밖 열람 기록 `count` 건을 대조군 몫으로 이관한다.

    **정확히** `count` 건일 때만 이관한다.  운영 위반이 하나라도 섞여 있으면
    개수가 어긋나 이관이 성립하지 않고, 그 기록은 그대로 남아 운영 게이트를
    발화시킨다 — 대조군 뒤에 위반을 숨기는 경로를 구조적으로 막는다.
    """
    if len(blocked_reads) != count:
        return []
    claimed = blocked_reads[:count]
    del blocked_reads[:count]
    sanctioned_reads.extend(claimed)
    return claimed
