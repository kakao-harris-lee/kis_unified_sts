# TOS 코드 절반 이하 — 안 쓰는 코드·안 터진 판정 장치·산문 걷어내기

- 작성: 2026-11-13 · 세션 모델 단독 저작 · 상태: 운영자 지시로 실행 중(계획 승인 위임, 메모리 11-11)
- 근거(운영자 2026-11-13): 「코드가 20만줄이 필요한 타당한 이유가 있어야해. 중복 개발, 불필요한 예외 로직등이
  너무 많다면 무가치해.」 · 「S1 진행해. S2 불필요하다고 보이는 판정 장치들 합치거나 제거도 진행해. 코드를 절반
  이하로 불필요한 문서와 주석 docstring 을 제거해. 개발 효율성을 확보해」
- 상위: [효용성·활용 방안](2026-11-13-tos-utility-and-usage.md) §2.2. CLAUDE.md R5(가드는 실제 사고 1건이 있어야
  둔다)·R6(판정 장치에 대한 판정 장치 금지)를 이미 있는 코드에 소급 적용한다.

## 1. 기준선 (2026-11-13 실측)

| 영역 | 전체 줄 | 실행 코드 | docstring | 주석 |
| --- | --- | --- | --- | --- |
| 커널 `tos/src` | 91.9k | 39.3k | 40.1k | 5.3k |
| 런타임 `tos/runtime/src` | 81.5k | 44.0k | 27.1k | 4.1k |
| `tools/tos_cp3` + `tools/tos_*.py` | 37.1k | — | — | — |
| 문서 `docs/` · `tos-spec/` · `tos-evidence/` | 127k · 66k · 25k | | | |
| 테스트 `tos/tests` · `tos/runtime/tests` · `tests/` | 130k · 121k · 105k | | | |

- 글자 그대로의 중복(6줄 창): 8%. 중복은 문제의 중심이 아니다.
- 정상 경로 e2e 테스트 두 개가 커널·런타임 문장의 66% 를 실행한다.
- 실제 증거 344만 행에서 거부(FLOW_HALTED)는 세 단계에서만 났다: 주문 구성 · 독립 승인 · 거래소 허용.
  끝까지 간 주문은 1건(11-13 주식 MOCK)이고, 5~14 단계와 verify 17 항목은 **승인 1 · 거부 0** 이 전 이력이다.
- 같은 사실을 세 번 판정한다: 흐름 단계 → verify 항목 → currentness 차원(21개 중 6개는 앞 단계 판정을 다시 읽고,
  4개는 정적 YAML 안전망, 3개는 설정 상수).
- `TIME_HEALTH_SNAPSHOT` 이 증거 행의 84%(290만 행, 8.3 GB) — 11-10 C: 가득 참 사고의 한 원인.

## 2. 지키는 것 (줄이지 않는다)

- 크래시 뒤 중복 주문 없음: `rcl`(duplicate_command) · `egress`(단일 사용) · `orthostate` · `staterestore` · `recon`
  · 복구 barrier 의 내용 · `TOS_PAPER_READY` 문장 3(drill 9/9, CI `tos-recovery-drill`).
- MOCK→REAL 폴백 금지(#998 `test_no_fallback_invariants.py`) · 실전 키 GET 전용 · `brokercap` — 문장 4, 비협상 규칙.
- 리스크 한도: `are`(aggregate risk) · `afg`(action flow) · `position`. `spg` 의 `envelope_max` 상한은 값으로 옮겨 남긴다.
- 실제로 거부를 낸 장치: `ioc`(구성) · `iap`(승인) · `venue`(거래소) · `time` · `marketfeed` · 결정 세대 핀(#1069) ·
  replay 대조(REPLAY_DIVERGED).
- B3 증인 `shared/decision/setups/vwap_reversion.py` 는 `TOS_PAPER_READY` 까지 바이트 동일(CLAUDE.md).

## 3. 단계

### S1 — 안 쓰는 코드·은퇴 도구·증거 부피 (진행 중)

| 레인 | 내용 | 등급 |
| --- | --- | --- |
| S1-a | 커널 `rlp` · `replacement` · `failuredomain` 삭제(런타임 도달 0, 커버리지 0%) + 그 테스트 | B |
| S1-b | `TIME_HEALTH_SNAPSHOT` 은 내용이 바뀔 때 + 설정 heartbeat 마다만 기록(평가 주기·신선도 판정은 그대로) | B |
| S1-c | B3 비교 파이프라인(`diff_decisions` · `emit_legacy_decisions` · `post_session_b3`)과 끝난 1회성 측정 도구 은퇴, 상태판 깨끗한 날 판정에서 B3 제거 — 로드맵 §7-3(P2 동등성 뒤 은퇴, #1065·#1066 로 충족) | B |

### S2 — 안 터진 판정 장치를 합치거나 지운다

판정 기준: (i) 출하 설정(`config/tos_runtime/*`)에서 상수이거나 입력원이 없다, (ii) §2 의 지킬 역할이 없다,
(iii) 같은 사실을 다른 곳이 이미 판정한다 — 셋 중 (ii)가 거짓이고 (i) 또는 (iii)이 참이면 지운다.

**S2-a 안전망(safety mesh) 제거 · 등급 A**

| 대상 | 이유 | 처분 |
| --- | --- | --- |
| `wdr`(편차) · `sir`(사고) | 판정 입력이 정적 YAML `members: []` — 항상 참 | 커널 패키지·런타임 서비스·verify 8·9·currentness 차원·`safety_{deviations,incidents}.yaml` 삭제. 통제된 종료의 «래치 먼저, 그다음 닫기» 순서는 런타임 평이한 코드로 남긴다 |
| `spg`(프로파일·활성화) | 정적 YAML 상수 | 삭제. 단 `HardSafetyEnvelope.envelope_max` → `are`/`riskstate` 설정 값으로 이전(리스크 상한 유지) |
| `protective` | 분류만 하고 막지 않는다 | 삭제(운영자 projection 칸 포함) |
| `liveauth` | `is_live(authorization=None)` 항상 False — 실주문 차단은 `brokercap`·transport 가 한다 | 삭제 |
| `hag`(이중 통제 재무장) | 재무장·정지 해제 기록 0 | 삭제. CLI 정지 해제는 가장 단순한 1인 확인으로 |
| `stm`(커널) | 경보 60건 전부 부팅 첫 관측 산물 | 커널 패키지 삭제, 런타임 `safety/monitoring` 축소판 하나만(증거 꼬리 정체·inbox 적체) |
| verify 7·8·9·10, currentness 4 차원(안전망), `_mesh_clear` | 위와 같음 | 삭제 또는 모니터링 하나로 |

**S2-b verify 항목·currentness 차원 합치기 · 등급 A (S2-a 머지 뒤)**

- verify 17 → 약 8: 남김 = 1(단일 사용 capability) · 5(live scope) · 6(브로커 분기) · 13 중 `mutation_fence_holds`
  · 16(currentness) · 17(실제 송신 바이트 일치). 2·3·4·11·12·14·15 는 앞 단계(3·8·13)의 판정과 같은 사실이라
  그 단계에 합친다.
- currentness 21 차원 → 앞 단계 재판정 6개와 설정 상수 3개를 뺀다(최소 차원 집합 `MANDATED_DIMENSION_FLOOR` 축소).

**S2-c 런타임으로 흡수·미사용 제거 · 등급 B (S2-a 와 병렬)**

- `nontrade` 커널·런타임·엔진 `_corporate_action` 삭제(입력원·`nontrade.yaml` 없음). 005930 실제 기업행위가 필요해지면
  그때 tenant 기능으로 다시 설계한다.
- `sci` → `tos_runtime.release`(배포 digest 거부 게이트만 남김), `sbr` → `tos_runtime.recovery`(레코드 + 술어 셋),
  `posttrade` 커널의 미사용 부분(약 80%) 삭제, `engine/standins.py` 삭제, 각 패키지 `__all__` 의 미사용 공개 함수 정리.

### S3 — 문서·명세 은퇴 (S2 와 병렬, 등급 B: CI 워크플로 변경)

- `tos-spec/`(66k) · `tos-evidence/`(25k) 전체, `tools/tos_spec_status.py` · `tos_evidence_run.py` ·
  `tos_profile_census.py` 와 그 테스트, mdBook·`tos_spec_status --check` CI 단계, `BROKER-TRANSPORT-SYMBOLS.{csv,md}`,
  명세 앵커 테스트(`sci/test_sci_anchor_drift.py` 등)를 지운다. 런타임·cron·배포는 둘 다 읽지 않는다(실측).
- docstring 문구를 단언하는 테스트(약 30곳, 행동을 시험하지 않음)를 지운다.
- `docs/` 역사 문서 삭제: 2026-07~09 RFC 설계 문서(약 4만 줄)를 포함한 `docs/plans` HISTORY 약 5.9만 줄, 은퇴한 레거시
  런북·루트 md, `broker-profiles/evidence/` 중 테스트 fixture(p02-t3) 밖의 캠페인. 남김 = 코드·CI 가 읽는 문서
  (`KIS-BROKER-CAPABILITY-PROFILE-draft.yaml` 등), 현재 런북(`tos-paper-boot` 외 6), CLAUDE.md 가 가리키는 현재 계획.
  코드가 경로를 읽는 계획 문서는 그 읽기를 지운 뒤에 지운다.
- 두 CLAUDE.md 와 `docs/INDEX.md`·`plans/INDEX.md` 정리.

### S4 — 산문 걷어내기 (마지막, 등급 B)

- 범위: `tos/src` · `tos/runtime/src` · `tools/tos_cp3` · `tools/tos_*.py` · 세 테스트 트리. `shared/` 는 건드리지 않는다.
- 규칙: docstring 은 **첫 줄만** 남긴다. 주석만 있는 줄은 지운다(`noqa`·`type:`·`pragma`·`fmt:`·`direct-core-call:`·shebang 만 남김).
  AST/토큰 기반 도구 `tools/strip_prose.py` 로 기계적으로 — 다시 돌려도 같은 결과(멱등).
- 같은 PR 에서: `black` · `tos_redigest --write`(네 `release.yaml`) · 크기 예산 예외 재측정(대부분 삭제) ·
  named-TBD 가드 재측정.
- 열린 PR 은 main 을 병합할 때 충돌 파일을 자기 쪽으로 받고 `strip_prose.py` 를 다시 돌린다.
- 남길 «왜» 는 짧은 한 줄 주석으로 다시 적는다 — 예: «bool 이어야 한다(int 1 은 EQ 에서 다르다)» 같이 틀리면 돈이
  나가는 비직관적 제약만. 계획·리뷰·사고 경위 인용은 git 이력으로 충분하다.

## 4. 목표 (측정으로만)

| 지표 | 기준선 | 목표 |
| --- | --- | --- |
| `tos/src` + `tos/runtime/src` + `tools/tos_*` 전체 줄 | 210.5k | **≤ 100k** |
| 문서 `docs/`+`tos-spec/`+`tos-evidence/` | 218k | ≤ 40k |
| verify 항목 · currentness 필수 차원 | 17 · 21 | ≤ 8 · ≤ 12 |
| 증거 행/세션(LONG) | 약 7만 | ≤ 1만 |
| 지킬 것 | drill 9/9 · #998 · e2e 주문 관통 | 그대로 green |

## 5. 위험과 대응

| 위험 | 대응 |
| --- | --- |
| 지운 장치가 실제로 막던 경우를 놓친다 | 지울 때마다 «출하 설정에서 상수»를 테스트 또는 실측으로 PR 본문에 보인다. e2e 주문 관통·drill·#998 은 매 PR green |
| 지속 잎(A05612·005930·paper)이 새 코드로 부팅·재생을 못 한다 | 각 S2 PR 은 실제 잎 **복사본**(읽기 전용 원본 → 스크래치)으로 부팅 재생을 확인한다. 안 되면 그 날 잎 archive → genesis(지우지 않는다) |
| 세션 중 배포 | 커널·런타임 PR 은 15:40 뒤 또는 휴장일에만 머지(매일 08:38 origin/main 으로 부팅) |
| 대형 PR 끼리 충돌 | 커널 레인 S2-a → S2-b 직렬, S2-c·S3 병렬, S4 는 모두 머지 뒤. digest·레지스터 충돌은 재도출로 푼다 |
| 호스트 메모리 | 전체 테스트는 `flock /tmp/claude-1000/tos-fullsuite.lock` 으로 한 번에 하나 |

## 6. 되돌리기

모든 삭제는 git 이력에 남는다. 레인별 PR 을 revert 하면 그 장치가 돌아온다. 잎은 archive 로만 옮긴다.
