---
adjudicator: codex
verdict: needs-attention
reviewed_at_head: b5d2448a6b7de7bc0342ddafa216a46569c25453
reviewed_scope_digest: fab46e79666db30af9dbf23c8bc49292bf004a5440c0a6aaf59dbd4002dddb2c
job_id: review-mtljvycx-ouye7r
subcommand: adversarial-review (--wait · setsid pid 95648 · base 28475ca1^ · scope branch)
captured_at_utc: 2026-09-03T13:18:10Z
verdict_recovered_at_utc: 2026-09-03T13:23:17Z
recorded_at_utc: 2026-09-03T14:20Z (후속 세션 — 직전 세션은 verdict 회수 직후 API 529 로 종료)
lane: A (코드) — Phase 0 완료 계약 §12.3 절차표 9행 «codex-reviewer 적대적 코드 리뷰»
scope: git diff 28475ca1^ HEAD -- . ':!docs/plans' ':!docs/reviews'  (D0 구현 블록)
evidence: .omc/review/20260903-165133/evidence/{architecture,security,performance,style}.md
verbatim_sources: codex-result.json (구조화 출력) · codex-wait.out (렌더 스트림)
---

# Codex verdict — verbatim (structured output, 무편집)

```json
{"verdict":"needs-attention","summary":"출하 차단. D0-5가 대상 파일 부재에도 MET를 발화하고, 7/7 처분은 프로파일 구조가 아니라 저작자 UNBOUND 문장으로 결정된다. faea9720도 git 실패 시 무시 파일을 다시 포함하는 fail-open 폴백을 남겼다. 반면 cdd3c561 변수 변경은 동작 보존이며, 7개 tos/src 파일은 docstring/포매팅 외 AST 동일, 하니스 SHA는 실제값·워크플로·wfcanon·u17·계약·상위 계획 모두 059e13f2…로 일치한다. 위조 verdict 경로는 UNCHK-012, PR이 워크플로 정의를 통제하는 한계는 UNCHK-008, git 이력 신뢰는 UNCHK-023에 직접 포섭되는 pre-existing 등재 축이며 이번 범위의 하니스/워크플로 변경이 새로 열거나 넓히지는 않았다.","findings":[{"severity":"high","title":"D0-5 대상 파일 삭제가 전칭 우주에서 사라져 MET로 통과한다","body":"독립 재검증 결과, 7개 고정 사이트 중 파일이 없으면 `continue`로 결과에서 제거된다. `check_d1`은 남은 결과만 검사하고, 렌더러도 누락을 N/A로 표시하면서 UNDECIDED 집합에는 넣지 않아 `D0-5: MET`를 발화한다(3991-4020). `/definitely-not-a-repo`를 입력한 직접 호출도 `({}, ())`를 반환했다. 테스트 4331-4336은 이 fail-open을 정상 동작으로 고정한다. 계약 §7.4/§11은 정확히 7개 사이트 모두에 허용 처분을 요구하므로, 입력 부재가 완료값을 만드는 직접 위반이다.","file":"tools/tos_completion_status.py","line_start":3708,"line_end":3711,"confidence":0.99,"recommendation":"대상 파일 부재를 D-1 차단 finding 또는 UNDECIDED로 기록하고, MET 계산 전에 disposition 키 집합이 `D1_SITES`의 정확한 7개 이름과 일치함을 검사하라. 기존 누락 테스트는 red 대조군으로 뒤집어라."},{"severity":"high","title":"UNBOUND 산문이 구조 대조를 단락해 저작자가 D-1 처분을 선택한다","body":"계약 §7.4는 저작자는 K만 공급하고 처분은 K와 프로파일 우주의 관계로 파생하며, 저작자가 처분을 고르는 것은 자기신고라고 명시한다. 그러나 구현은 `not a profile key` 같은 문장을 먼저 검사해 즉시 UNBOUND를 반환한다. 직접 호출에서 문장 하나와 키 0개도 UNBOUND였고, 같은 문장에 실재 프로파일 키를 넣어도 결과가 불변이었다. HEAD의 7사이트도 전부 이 분기로 UNBOUND이며 프로파일 대조에 도달하지 않는다. 테스트 4292-4310과 4408-4424는 오히려 이 우선순위를 명시적으로 고정한다. UNCHK-015는 공급된 K의 의미 적절성 한계이지, K 없이 산문으로 처분을 선택하는 이 경로를 포섭하지 않는다.","file":"tools/tos_completion_status.py","line_start":3672,"line_end":3683,"confidence":0.98,"recommendation":"UNBOUND 문장을 처분 입력으로 사용하지 말고 docstring에서 명시적 후보 K를 추출한 뒤 프로파일 우주 부재를 교차 검증해 UNBOUND를 파생하라. 산문과 실재 키가 혼재하거나 후보 K가 없으면 차단하고, 위조 키·키 0개·혼재 키 대조군을 red로 추가하라. 사이트 단위로 혼합 처분을 표현할 수 없는 문제는 계약 에라타 대상으로 별도 기록하되 계약 본문은 이 변경에서 편집하지 마라."},{"severity":"medium","title":"git census 실패가 조용히 더 넓은 os.walk 우주로 전환된다","body":"faea9720의 정상 git 경로는 ignored 벤더를 제거하지만, git 실행 예외나 비정상 종료는 모두 None으로 접힌 뒤 1755-1771에서 `.gitignore`를 모르는 os.walk로 폴백한다. 이 우주는 ignored 파일의 클래스 정의를 `validate_broker_symbols_are_grounded`의 근거로 인정할 수 있어, 실제 배포 우주에 없는 등록 심볼이 grounded로 통과한다. 테스트 786-802가 git 없는 동일 레이아웃에서 ignored 파일까지 스캔됨을 확인하므로 폴백의 차이는 의도적이고 판정 출력에는 드러나지 않는다. 계약 §2 기준선이 미추적 open-trading-api를 `git ls-files`로 정의하므로 authoritative `--check`에서 다른 우주로 대체하는 것은 fail-open이다.","file":"tools/tos_spec_status.py","line_start":1711,"line_end":1721,"confidence":0.94,"recommendation":"판정을 내리는 `--check`에서는 git 부재·비정상 종료·디코딩 실패를 `StatusError`로 차단하라. os.walk는 명시적인 합성 코퍼스/비권위 모드에서만 허용하고, git nonzero와 ignored decoy class를 결합한 red 테스트를 추가하라."}],"next_steps":["D0-5 파일 부재와 UNBOUND 자기신고 두 경로를 먼저 fail-closed로 수정한 뒤 생성물을 재생성한다.","git 실패 대조군을 추가하고 `tos_spec_status.py --check`가 os.walk로 조용히 전환되지 않음을 검증한다.","수정 후 focused 테스트와 전체 필수 검사기를 쓰기 가능한 CI/임시 디렉터리 환경에서 재실행한다. 이번 세션의 pytest 재실행은 사용 가능한 임시 디렉터리가 없어 수행되지 못했다.",""]}
```

# 수용검사 (오케스트레이터 = Claude · 판정이 아니라 대조)

기각 가능 사유는 셋뿐이다(팬텀 file:line · 의도적 silenced · 비협상 규칙 배치). 아래 대조는
기각 여부와 pre-existing 분류만 정한다 — 게이트는 이 표가 아니라 Codex 의 새 approve 로만 열린다.

| # | sev | file:line 실재 | in-range(28475ca1^..HEAD) | 의도적 silenced | 비협상 규칙 배치 | 처분 |
|---|---|---|---|---|---|---|
| 1 | high | 실재 — `tools/tos_completion_status.py:3708-3711` `if not path.exists(): continue`; 렌더러 3996-4020 이 N/A 를 UNDECIDED 집합에 넣지 않고 `D0-5: MET` 발화 — 재현 확인 | in-range(D0-A 신규 파일) | 아니오 — docstring 이 «합성 코퍼스 편의»로 설명하나 권위 경로(실코퍼스 `--check`)에서 입력 부재→통과값이라 계약 §7.4/§11 위반. 설계 의도는 silenced 근거가 아니다 | 없음 | **채택** |
| 2 | high | 실재 — `tools/tos_completion_status.py:3672-3683` `_derive_d1_disposition` 이 `_D1_UNBOUND_RE` 를 우주 대조보다 먼저 평가; HEAD 7사이트 전부 `('UNBOUND', 'docstring 에 UNBOUND 선언 문언 존재')` 로 실측 | in-range | 아니오 — 코드 주석(:3585-3591)이 이 우선순위를 «저작자 결론 보호»로 명시하나, 계약 §7.4 :2698 「저작자가 처분을 고르면 그 자체가 자기신고」와 정면 충돌. 계약 원문 재독으로 Codex 독법 확인 | 없음 | **채택** |
| 3 | medium | 실재 — `tools/tos_spec_status.py:1711-1721` 예외·rc≠0·디코딩 실패 전부 `None` → 1755-1771 os.walk 폴백; 대조군 테스트 :786-802 가 폴백을 정상으로 고정 | in-range(faea9720) | 아니오 | 없음 | **채택** |

기각 0 · pre-existing 분리 0 · 채택 3/3.

## 계약 대조 메모(수용검사 근거 · 계약 무편집)

- §7.4 :2682-2823 — 「저작자는 **의존 키만 공급**하고, **처분은 검사기가 파생**한다」「UNBOUND = K 가 VER-002 의 키가 아님」
  「D-1 공급된 키 K 는 해당 docstring 본문에 리터럴로 등장」「UNDECIDED 는 D0-5 완료를 차단」.
  → finding 2 의 «UNBOUND 문언 우선 단락»은 K 없이 처분을 고르는 경로 = §7.4 가 금지한 자기신고. UNCHK-015 는
  «공급된 K 의 적절성» 한계이지 K 부재를 덮지 않는다(Codex body 와 일치).
- 완료 기준(v1.8) — 「7개 사이트 전부가 VALUED/BLOCKED/UNBOUND 중 하나를 배정받았을 때」 → finding 1 의
  «부재 사이트 제외 후 MET»는 7 미만으로 MET 를 만드는 vacuous truth.
- §2 기준선(open-trading-api 미추적 = `git ls-files` 정의) → finding 3 의 os.walk 대체는 권위 `--check` 에서 다른 우주.

## 수정 위임 (오케스트레이터는 직접 고치지 않는다)

| finding | 담당 레인 | 산출 |
|---|---|---|
| 1 + 2 | 실행 에이전트(Sonnet) — `tools/tos_completion_status.py` · `tests/tools/test_tos_completion_status.py` · D0-5 7 docstring(선언 행 추가 · docstring 전용) · `tos-spec/src/TOS-COMPLETION-STATUS.md` 재생성 · 에라타 후보 기록(계약 밖) | fail-closed 구조 파생 + red 대조군 |
| 3 | 실행 에이전트(Sonnet) — `tools/tos_spec_status.py` · `tests/tools/test_tos_spec_status.py` | 권위 경로 StatusError + 명시 walk 모드 + red 대조군 |

수정 후 **재심 필수** — 새 스탬프 + 이 파일(`.omc/review/20260903-165133/verdict.md`)을 Codex 에 지목해
해소 vs 회피(테스트 무력화·조건 완화·문구만 추가)를 1순위로 심사시킨다. 이 needs-attention 은 §12.3 9행의
기록 심판이며, Phase 0 완료 판정(§11) 은 이 레인의 approve 이전에는 인용할 수 없다.
