# Phase 0 Codex 심판 기록 보존소 (`docs/reviews/phase0-codex-records/`)

> **Document class**: 비규범 보존 기록. 판정을 새로 내리지 않으며 계약·검사기·기계 상태를 바꾸지 않는다.
> 각 스탬프 디렉터리의 내용은 `.omc/review/<stamp>/` 에서 **byte 그대로 복사**한 것이다(`*.pid` 제외).

## 왜 이 디렉터리인가

`docs/reviews/phase0-completion-contract/` 는 U-15 R-3 선택자의 우주다 — 그 디렉터리에서 «`verdict.md` 를 가진
사전순 마지막 스탬프» 가 **계약 판정**으로 읽히고 R-4/R-5 가 approve + `reviewed_plan_paths`(계약·개발계획 2건)를
요구한다. 레인 A(코드) 판정이나 사이트 독립 확인 판정을 거기에 `verdict.md` 로 넣으면 진입 판정(ENTRY)이 깨진다.
그래서 계약 판정이 아닌 심판 기록은 여기에 둔다. 마찬가지로 `docs/reviews/d1-no-dependency/` 는 계약 §7.4 D-4 (마)가
정한 «approve 인 사이트 독립 확인 기록» 전용이라, marketfeed 의 needs-attention 기록도 여기에 둔다.

## 결속에 대한 주의

- 레인 A approve(`20260904-155704`)의 `reviewed_scope_digest` 는 HEAD `c5550229` 의 **작업 트리 전체**에 결속된다.
  이 보존소를 추가하는 커밋은 레인 A 심사 범위(`':!docs/reviews'`) 밖의 docs 전용 변경이지만 트리 digest 는 바뀐다 —
  codex-gate 규율상 그 approve 를 «그 HEAD 에 대한 판정» 으로 읽어야 하며, 다음 코드 변경 때 재심한다. 재심 여부는 운영자 결정.
- 레인 B 계약 판정의 정본 `verdict.md` 는 `phase0-completion-contract/<stamp>/` 에 있고, 여기에는 그 심판의 원문 JSON ·
  focus · evidence 만 보존한다(`VERDICT-POINTER.md` 참조).

## 스탬프 색인

| 스탬프 | 레인 | 잡 | 판정 | 결속 head | 비고 |
|---|---|---|---|---|---|
| `20260902-174919` | B 재승인(main 착지) | review-mtjuycte-68jupi | approve | f49c3728 | 정본 verdict 는 계약 스탬프 dir · 여기엔 원문 |
| `20260902-195656` | B 재결속(sha 재핀) | review-mtjznj44-qzsjpk | approve | cdecb692 | 〃 |
| `20260903-165133` | **A 1차** (D0 블록 코드) | review-mtljvycx-ouye7r | needs-attention 3 | b5d2448a | F1 파일 부재 fail-open · F2 UNBOUND 산문 · F3 walk 폴백 |
| `20260904-001114` | A 재심 #1 | review-mtlo6mst-93vt2j | needs-attention 3 | 2e5edb4a | 1차 3건 해소 확인 · NONE/혼합 키 · docs/plans 결속 · 렌더러 7이름 |
| `20260904-100015` | A 재심 #2 | review-mtm957x1-fzj64e | needs-attention 1 | 26db89c9 | 7월 설계 문서 2건 레인 B 결속 부재 |
| `20260904-101247` | **B 측면**(7월 설계 문서 2건 · 15b65212) | review-mtm9fvsu-e0tyho | approve | 26db89c9 | plan_scope_digest f2d02c4f… |
| `20260904-101638` | A 재심 #3 | review-mtm9l68o-mpbdaq | **approve** (low 1) | 26db89c9 | C4 이후 무효 |
| `20260904-112156` | B 에라타 52차 | review-mtmbw5f3-xpo98b | needs-attention 1 | 091b0fad | 정본 verdict 는 계약 스탬프 dir |
| `20260904-114347` | B 에라타 53차 | review-mtmcoagb-uym46j | needs-attention 1 | d8ee64dd | 〃 |
| `20260904-115942` | B 에라타 54차 | review-mtmd8qat-c1u166 | needs-attention 1(«회피») | a311eac1 | 〃 |
| `20260904-131909-marketfeed` | **독립 확인**(§7.4 D-4 (마) 후보) | review-mtmg2lz7-88qdyb | needs-attention(claim 거짓) | c8209c34 | marketfeed 는 NONE 아님 → C4 재분류 |
| `20260904-132009` | B 에라타 55차 | review-mtmg49a4-g8ab13 | needs-attention 1 | c8209c34 | 정본 verdict 는 계약 스탬프 dir |
| `20260904-133500` | B 에라타 56차 | review-mtmgna46-osp4fm | **approve** | 48243cd2 | 〃 · R-3 최신 |
| `20260904-150103` | A 재심 #4 (C4) | review-mtmjt61i-d0f3oc | needs-attention 1 | 7bf83226 | (마) 기록 검증 느슨 |
| `20260904-154559` | A 재심 #5 (C5) | review-mtmlkbm4-t1ovxs | needs-attention 1 | 2c2bc607 | claim 포함 검사 |
| `20260904-155704` | **A 재심 #6 (C6)** | review-mtmnmhm1-pc6tnu | **approve · findings 0** | c5550229 | §12.3 절차표 9행 게이트 개방 · D0-5 MET 7/7 |

## 파일 구성(스탬프마다)

`verdict.md`(또는 `VERDICT-POINTER.md`) · `codex-result.json`(companion 구조화 출력 원문) · `codex-wait.out`(렌더 스트림) ·
`focus.txt`(디스패치 지시문) · `revision.txt`(디스패치 직전 결속값) · `job.txt` · `evidence/`(4렌즈 · verification-run · scope/lockstep patch ·
mutation log). `20260904-001114` 에는 OpenAI 장애 재시도 로그(`retry-loop.log` · attempt1/2 failed out)도 있다.
