# tos 세션 핸드오프 — 모의투자 운용 서버에서 개발 이어가기 (2026-09-23)

- 작성: 2026-09-23 · 세션 모델 단독 저작 · 대상 독자: 모의투자(paper) 서버에서 이 작업을 이어받는 사람/에이전트
- 기준 main: **`7aba8a0d`**(PR #786) + 게이트 활성화 PR(브랜치 `ci/tos-mypy-stage3-enable-arg-type`)
- 충돌 시 정본: 코드와 CI 워크플로 > 계획 문서 §7 착지 기록 > 이 문서. 프로브 실행은
  `docs/runbooks/kis-capability-probes.md` 가 정본이다.

## 0. 한 줄 요약

로컬 세션(2026-09-22~23)에서 **tos 테스트 트리 mypy 래칫 3단계(`arg-type` 773 → 0)** 와 **증거 결속의
값싼 tier 두 개**를 닫았다. 서버에서 이어갈 것은 (1) 래칫 마지막 단계 `unused-ignore` 8건 결정, (2)
**서버에서만 가능한** 모의투자 프로브 7건 실행, (3) 운영자 결정 3건 뒤의 `run` 실부팅 아크다.

## 1. 이 세션이 착지한 것

| PR | 내용 | main |
|---|---|---|
| #770 | P-CA `--event-class` 유효값 7종 + 드라이런 프리플라이트 런북 | `29f39fe6` |
| #774 | 증거 PACKAGE 단독 결속 4건 — `planned_unassigned_pairs` 753 → **749** | `ff3c04fd` |
| #775 · #781 | 3단계 계획 저작(fact-check 3라운드) · §5 운영자 처분 ①~④ 추천안 채택 | `b0aff438` · `534cb2da` |
| #778 #782 #783 #784 #786 | 래칫 3-a~3-e — `arg-type` 773 → 4 | `362b047b` … `7aba8a0d` |
| #785 | 커널 타입 위생 2종(운영자 ④) — `arg-type` 4 → 0 | `70ca43a1` |
| 게이트 켜기 | `tos-firewall.yml` 두 테스트 트리 스텝에서 `--disable-error-code=arg-type` 제거 + 계획 §7 착지 기록 + 이 문서 | (PR 번호는 머지 커밋 참조) |

상세는 `docs/plans/2026-09-22-tos-test-tree-mypy-ratchet-stage3-plan.md` **§7.1~7.5** 와
`docs/plans/2026-09-18-tos-test-tree-mypy-ratchet-plan.md` §7. 리뷰 판정은 전부 각 PR 코멘트에 있다.

## 2. 서버에서 시작하기 전 확인 (전부 필수)

1. `git fetch origin && git checkout main && git pull --ff-only` → `git log --oneline -1` 이 게이트 PR 의
   머지 커밋 이상인지.
2. 서버 메모리 파일이 있으면 먼저 읽는다: `/home/deploy/.claude/projects/-home-deploy-project-kis-unified-sts/memory/MEMORY.md`
   (루트 `CLAUDE.md` 가 지정). 로컬 세션의 메모리는 서버에 없다 — 이 문서 §5 가 그 요약이다.
3. **프록시 우회는 서버에 해당 없음.** 로컬에서 쓴 `~/.internal-bin/gh`(사내 프록시 차단 우회 래퍼)와
   `env -u HTTPS_PROXY … git push` 는 로컬 노트북 전용이다. 서버에선 그냥 `gh`·`git`.
4. mypy 는 **2.3.1 핀**(`.github/workflows/tos-firewall.yml`, `pip install "mypy==2.3.1"`). 다른 버전은 수치가
   다르다. `python -m mypy --version` 으로 확인.
5. **editable `.pth` 함정**: 워크트리에서 커널을 고치고 재면 `.pth` 가 가리키는 다른 체크아웃의 커널로 잰다.
   항상 `PYTHONPATH=tos/src:tos/runtime/src` 를 걸고 `python -c "import tos; print(tos.__file__)"` 로 확인.
   `pip install -e` 재설치는 해법이 아니라 원인이다(다른 워크트리의 설치를 덮어쓴다).
6. 풀스위트는 **한 번에 하나만**, 도는 동안 그 워크트리를 건드리지 않는다 — 릴리스 admission 이
   `code_digest` 로 소스 트리를 실측 해시하므로 실행 중 편집(뮤테이션 포함)은 수백 건 가짜 실패를 만든다.
   워크트리 두 곳에서 동시에 돌리면 디스크 경합으로 `test_drill.py` 등 15~24건 가짜 실패.

## 3. 측정 명령 (CI 와 동일)

```bash
# repo 루트, 루트 venv. 재기 전에 .mypy_cache 삭제.
rm -rf .mypy_cache
export PYTHONPATH=tos/src:tos/runtime/src

# 소스 스텝 2 — 포트/본문 불일치는 여기서만 드러난다 (계획 §7.3)
(cd tos && mypy src --ignore-missing-imports)                 # 0 / 264 files
mypy tos/runtime/src --ignore-missing-imports                  # 0 / 185 files

# 테스트 트리 스텝 2 — 게이트 활성화 후의 플래그 (arg-type 켜짐)
mypy tos/tests --ignore-missing-imports \
  --disable-error-code=no-untyped-def --disable-error-code=unused-ignore     # 0 / 579 files
mypy tos/runtime/tests --ignore-missing-imports \
  --disable-error-code=no-untyped-def --disable-error-code=unused-ignore     # 0 / 221 files

# 마지막 단계 입력 — unused-ignore 만 켜서 잰다 (2026-09-23: 커널 5 · 런타임 3)
mypy tos/tests --ignore-missing-imports --disable-error-code=no-untyped-def | grep -c unused-ignore
mypy tos/runtime/tests --ignore-missing-imports --disable-error-code=no-untyped-def | grep -c unused-ignore

# 거버넌스 게이트
python tools/tos_firewall_check.py && lint-imports
python tools/tos_contract_check.py && python tools/tos_contract_check.py --self-test
python tools/tos_completion_status.py --check        # GREEN · planned_unassigned_pairs=749
python tools/tos_spec_status.py --check              # PASS · profile_keys=164 · null=16
python tools/tos_size_budget.py --check

# 테스트 (파이프로 자르지 말 것 — 종료 코드가 가려진다. 요약 줄을 인용한다)
PYTHONPATH=tos/src python -m pytest tos/tests -q -p no:cacheprovider                    # 9539 passed
PYTHONPATH=tos/runtime/src:tos/src python -m pytest tos/runtime/tests -q -p no:cacheprovider   # 2620 passed
```

알려진 로드 플레이크(코드 결함 아님, 단독 재실행으로 판정): `tos/runtime/tests/compose/test_cli.py::
test_install_run_stop_signal_handlers_flips_stop_on_sigint_and_restores` · `test_drill.py` 계열.

## 4. 다음 작업 큐 (이 순서를 권한다)

### 4.1 래칫 마지막 단계 — `unused-ignore` 8건 (소형 계획 하나)

새 CI 플래그에서 `unused-ignore` 는 커널 5 · 런타임 3 이고, **zero-disable 에선 0** 이다. 즉 여덟은 전부
`# type: ignore[no-untyped-def]` 류 — CI 가 `no-untyped-def` 를 영구 유예(상위 계획 §6 ①)하는 한 CI 관점에선
영원히 unused. 결정은 둘 중 하나: (a) 여덟을 지우고 `unused-ignore` 를 켠다(CI 기준 — 로컬 zero-disable 에서
`no-untyped-def` 8건이 새로 보이게 됨) · (b) 켜지 않고 유예 3종 중 2종(`no-untyped-def`·`unused-ignore`)으로
종결 선언. **세션 모델이 소형 계획을 쓰고 운영자가 고른다.** 어느 쪽이든 PR 하나.

**2026-09-23 갱신:** 소형 계획은 씌었다 — `docs/plans/2026-09-23-tos-test-tree-mypy-ratchet-final-unused-ignore-plan.md`
(PR #788). 선택지는 (a)·(b) 에 **(c) 여덟 함수 애노테이션 후 (a)** 가 더해져 셋이고, 권고는 (a) 다. 위 문단의 「둘 중 하나」는
저작 시점 서술로 남긴다.

**2026-09-23 착지:** 운영자가 (a) 를 확정했고 PR #788 로 구현됨 — 여덟 줄 주석 삭제 · CI `unused-ignore` 활성화.
실측·뮤테이션 재현은 해당 계획 §8.1.

### 4.2 모의투자 서버 프로브 7건 — **서버에서만 가능**

`docs/runbooks/2026-09-10-p02-probe-handover-paper-server.md` 를 그대로 따른다(§1 실행 전 확인 → §2 실행
목록 → §3 중단 규칙 → §4 산출물). 개발 측 준비는 끝났다: 런북 유효값 · 드라이런 8개 명령 전건 통과 ·
P-CA `--event-class` 7종(#770) · 근월물 코드는 **실행 당일** `get_front_month_code(product="mini")` 로 다시
뽑는다. 필요한 것은 서버 접속과 장 시간뿐이다.

| 프로브 | 성격 |
|---|---|
| P-8 · P-15→N-15 · P-BAL · P-CA · P-EXT | 모의(MOCK) 5 |
| N-16 · N-18 | 실전 GET-only 2 |

**⚠ 서버에서 확인한 실상(2026-09-23 · 위 표는 로컬 저작 시점의 목록이고 t3 캠페인 README 가 정본).** 위 표의
일곱 항목(`P-15→N-15` 는 한 항목) 중 **네 항목 = 프로브 다섯 종(N-16 · N-18 · P-15 · N-15 · P-BAL)이 측정 완료**,
한 항목(P-CA)은 예약, 두 항목(P-8 · P-EXT)은 차단이다 — `docs/broker-profiles/evidence/2026-09-11-p02-t3-campaign/README.md`:

| 상태 | 프로브 | 근거 |
|---|---|---|
| 측정 완료(09-10~11) | N-16 · N-18 · P-15 · N-15(n=1) · P-BAL(모의 주식 2페이지 25행) | t3 README 「2026-09-10 야간」·「2026-09-11」 표 |
| 예약됨 | P-CA 2차 — SK하이닉스 `000660` 현금배당, **2026-09-30 00:20 KST 호스트 cron**(`~/.config/kis-probes/run-p-ca-20260930.sh`, 예전 계좌 `54e7f8a5d841` 가드 · 17:05 텔레그램 결과 보고 cron) | 1차(09-17 SK텔레콤)는 rate-limit CENSORED · 참조 TR 은 SUPPORTED |
| **차단** | **P-8 ×5 · P-EXT ×5** | 09-15 모의투자 재신청 후 새 계좌가 앱키에 **미연결** — 09-16 P-8 `인증 시점의 계좌번호와 요청 계좌번호가 일치하지 않습니다`, **09-23 재확인** P-BAL 새 주식 계좌 `OPSQ2000 INVALID_CHECK_ACNO` 변화 없음 · P-5b 새 선물 계좌 조회 `rt_cd=2`. 운영자가 KIS Developers 에서 연결 반영을 확인한 뒤에만 실행일을 잡는다 |

즉 서버에서 남은 실행은 **P-8 ×5 → P-EXT ×5**(순서 강제, 선물 정규장 08:45–15:45, P-EXT 는 운영자 MTS 동석) 둘뿐이며
둘 다 브로커 측 계좌 연결이 선행이다. 프로브 런북 §1 의 8항목 중 09-23 에 확인한 것은 1(체크아웃 clean `c2b9761f`) ·
2(`enabled: false`) · 3(`futures:live:suspended` 미설정) · 4(모의 선물 앱키 공유 컨테이너 0 — P-15/N-15 는 이날
실행 대상이 아니었으므로 참고) · 6(계좌 지문 `ee1bdb5f1ca2`/`46c39c54d3bb`) · 7(정규장 내) 과 근월물 `A05610` 이다.
5(환경변수 이름)와 8(안전 모델)은 러너 prereq 패널 출력으로만 확인했다.

닫히는 것: `+Broker` 증거 **71행**, 프로파일 null 키 **10 중 6**(나머지 4 는 프로브 단독으로 값이 서지 않는다
— `non_trade_*` 2 는 N-19+P-CA+Bounds-Approver 연언, `protection_gap/overlap` 2 는 별도 측정 설계).
**P-R5/P-R5-PRE(실전 주문)는 정책상 영구 금지** — 실행 목록에 없고 넣지 않는다.

### 4.3 운영자 결정 3건 (코드 레인 없음)

- **값 제안표 채택** — `docs/plans/2026-09-18-tos-config-value-proposal.md`(§6 ②, 채택 대기).
- **A-5 부팅 대상** — 로컬 헤르메틱 데이터 디렉터리까지인지, 모의 서버 핸드오버까지인지
  (`docs/plans/2026-09-18-tos-config-adoption-and-carryover-plan.md` §6 ④ · §7.6).
- **F-3 별도 KIS 앱 등록** — 읽기 전용 경로 자격증명 분리 여부(운영자 계정 작업).

### 4.4 그 다음 — `run` 실부팅 아크와 증거

- `run` 이 실제 데이터 디렉터리에 대고 부팅(A-5)해야 **RUNTIME/FAULT 증거 534쌍(미결속의 67%)** 이 닫힐
  수 있다. 파일·테스트로 닫히는 tier 는 이 세션에서 소진했다: 인용 테스트가 있는 ID 25 중 23 결속(#769
  #771), 소스가 substrate 로 자칭하는 PACKAGE 4 결속(#774). **남은 PACKAGE 96 / TEST 100 은 테스트를 새로
  써야 닫힌다** — 표면 결속은 「실재」만 주장하고 「검증됨」을 주장하지 않는다(#771 본문 §「진짜 질문」).
- 후속 처분 F-1(`ReconciliationService` 의 `broker_execution_id` 교차조회 — 없으면 오더 축 재무장 영구
  차단) · F-2(토큰 추상 충돌) · F-4(증거 README 에 아티팩트·필드 명시) —
  `docs/plans/2026-09-17-tos-run-boot-and-real-sources-arc-plan.md` §7.2.
- 커널 위생 부류 후속 후보: 「Protocol 의 평범한 속성 선언 vs frozen 구현」이 이번 단계에서 **다섯 번**
  나왔다(#785 2 + 3-e 포트 3). `tos/src`·`tos/runtime/src` 의 Protocol 전수를 한 번 훑는 소형 스윕이
  값어치가 있다(계획 §7.2).

  **2026-09-23 착지:** 스윕 완료 — `docs/plans/2026-09-23-tos-protocol-readonly-members-sweep-plan.md`
  (PR #790). Protocol 전수(75종/42파일) 중 평범한 멤버 7종/10개 전부 읽기전용 `@property` 로 전환, 그중
  2종은 실 구현이 frozen dataclass 라 구조적으로 이미 깨져 있던 결함(소비부 0 이라 CI 는 조용했음). 핀
  테스트 2파일 + 뮤테이션 ①②③ 전건 재현 + 커널 9542·런타임 2628 pytest 전건 pass.

## 5. 함정 요약 (로컬 메모리에서 옮김 — 서버엔 이 문서뿐)

- **GREEN ≠ 앵커가 옳다.** `tos_completion_status --check` 는 `파일:줄` 에 evidence_id 리터럴이 있는지만 본다.
  줄 수가 바뀐 파일의 앵커는 **각각 내용으로** 재유도한다. 일괄 오프셋은 같은 파일의 다른 표지 줄에
  걸려도 GREEN 이다(상위 계획 §5 8·9).
- **원장 CSV 를 파이썬으로 다시 쓰지 마라.** `csv.writer` 는 CRLF 로 전 파일을 재기입한다. 해당 줄만 문자열
  치환, 백업은 `cp -p`, 복원 검증은 `cmp`. `tos-spec/src/verification/*.csv` 는 BOM 없음·LF.
- **`__pycache__`·`.mypy_cache` 는 `(mtime, size)` 키잉** — 뮤테이션 전후로 둘 다 지운다. `cp -p` 로 복원.
- **`pytest | tail` 은 종료 코드를 가린다** — `pipefail` 또는 요약 줄 인용.
- **관측치를 불변식으로 승격하지 마라** — 계획 부록의 `assert len(...) == 206` 이 깨끗한 체크아웃에서 204 라
  죽었다(계획 §0.1 · §7.0).
- **저자 자기검증은 검증이 아니다** — 이 세션 리뷰가 잡은 저자 오류: 「cast 4건 전부 raises 안」(2건 밖) ·
  「TypedDict 1:1」(디폴트 파라미터 누락) · 계획의 분류기 결함 2건. 모든 PR 은 sonnet 리뷰 레인(저자와 다른
  패스)을 거치고 판정을 **PR 코멘트로** 남긴 뒤 머지한다(`~/.claude/review-lane.md` 규약 — 서버에 없으면
  형식은 각 PR 코멘트에서 그대로 베낀다).
- **strict 머지 정책** — main 이 움직이면 PR 은 BEHIND 가 된다. `gh pr update-branch <n>` 후 CI 재통과를
  기다려 `mergeStateStatus == CLEAN` 일 때만 머지. `gh pr checks --watch` 는 새 push 직후 옛 head 를 보고
  즉시 돌아온다 — `mergeStateStatus` 를 폴링한다.
- **한 워크트리 한 레인.** 다른 레인이 도는 워크트리에서 `git checkout --`·stash·뮤테이션을 하지 않는다.

## 6. 운영자 결정 대기 목록 (2026-09-23 시점)

| # | 항목 | 어디에 |
|---|---|---|
| 1 | ~~모의투자 프로브 7건~~ → **P-8 ×5 · P-EXT ×5 만 남음.** 운영자가 09-23 저녁 앱키 연결 확인을 통보했으나 같은 저녁 새 토큰 GET 재조회(주식)는 여전히 `INVALID_CHECK_ACNO`. **P-8 ×5 는 2026-09-28(월) 09:05 호스트 cron 예약** — 1회차가 연결 게이트(거부 시 중단). P-EXT MTS 동석 시각은 미정 | §4.2 · t3 README 「2026-09-23 저녁」 |
| 2 | ~~`unused-ignore` 8건 결정~~ → **운영자가 (a) 확정, PR #788 로 착지(2026-09-23)** — 계획 `docs/plans/2026-09-23-tos-test-tree-mypy-ratchet-final-unused-ignore-plan.md` §8.1 | §4.1 |
| 3 | ~~값 제안표 채택~~ → **제안값 그대로 채택(2026-09-23, ⚠ 4행 포함)** — 실파일 기입(A-2~A-5)은 별도 PR | 채택 계획 §7.6 |
| 4 | ~~A-5 부팅 대상~~ → **로컬 헤르메틱 데이터 디렉터리까지(2026-09-23)** | 채택 계획 §7.6 |
| 5 | F-3 별도 KIS 앱 등록 → **C-2(토큰 소유권 결정) 뒤에 판단(2026-09-23)** — C-2 문서는 세션 모델이 먼저 쓴다 | 채택 계획 §7.6 · §4 W-C |
