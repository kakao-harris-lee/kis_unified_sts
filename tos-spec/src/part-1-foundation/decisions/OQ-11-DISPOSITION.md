# OQ-11 Disposition — Evidence Level to Surface Kind Mapping

> **Document class**: Non-normative decision record. This document does **not** amend
> `VER-002-001` or any RFC/ADR. It records an interpretation decision and its authority,
> so that a downstream non-normative plan can cite an approved reading instead of
> asserting one. No evidence state, ADR acceptance, or authorization changes.

```yaml
disposition: RESOLVED_MAPPING_APPROVED
bound_set_digest: 796ca1e0a5b7ff8499e38b5322ff579b63dc643b6af6ec9cf3483dbeacaf6919
bound_paths:            # repo 루트 기준 상대경로. `./` 접두 금지 (표기가 digest 에 실린다)
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
requesting_plan_version: v2.13
contract: 해당 계획 §12.3.1 (6e 산출 계약)
authority: 운영자 (this repository's corpus owner)

# 비결속 참고값 — 대조 대상이 아니다. 이 값이 달라도 결속은 유효하다
# 기입 규칙: 재결속 편집 직전 `git rev-parse HEAD` — 결속 대상(동결 커밋)이 아니라
# **결정 행위 시점의 repo 위치**다 (6e‴ 정정 기록 참조)
decided_at_head: 3134a87b6a44626f2dd5d79443e3f6de55de6b69
```

**결속의 의미**: `bound_set_digest` 는 위 `bound_paths` 의 **(경로, 내용) 쌍 집합**에
대한 해시다. 계획이 개정되거나 **문서가 추가·제거·개명되면** 값이 달라지므로,
이 판정을 인용하려는 쪽은 **인용 시점에 재계산해 대조**해야 한다.
불일치는 "이 판정이 그 내용을 승인했다"는 주장을 성립시키지 않는다.

```bash
printf '%s\0' <bound_paths> | LC_ALL=C sort -z -u \
  | xargs -0 shasum -a 256 | shasum -a 256 | cut -d' ' -f1
```

> **"내용만"이 아니다.** `shasum` 출력이 `<hash>  <경로>` 형태이므로 **경로 문자열이
> 다음 해시의 입력에 그대로 실린다.** 실측: 같은 파일을 `X` 로 쓸 때와 `./X` 로 쓸 때
> digest 가 다르다.
>
> **이것은 결함이 아니라 요구되는 성질이다** — 파일 목록 변경도 범위 변경이므로
> 개명·추가·제거가 결속을 깨야 한다. **대가는 표기 민감성**이며, `bound_paths` 를
> repo 루트 기준 상대경로로 고정해 거짓 불일치를 막는다.
>
> v2.4 초판이 이것을 **"내용만의 해시"** 라 불렀고 그것은 거짓이었다(Stop 게이트 5라운드).

> **`HEAD` 를 포함하지 않는다 — 의도적이다.** 레인 B 심판의 `plan_scope_digest` 는
> `HEAD` 를 포함해 **과잉 무효화 쪽**으로 붙인다(심사받지 않은 코드의 통과가 더 큰
> 비용이므로). **이 판정의 트레이드오프는 반대다** — 주장하는 것이 *계획 내용*에 대한
> 해석 승인이므로, `HEAD` 를 넣으면 **승인 대상과 무관한 변화**(다른 파일 커밋,
> 이 문서 자신의 커밋)에도 만료된다.
>
> `decided_at_head` 는 판정 당시 repo 위치를 남기는 참고값이며 **대조 대상이 아니다.**

> **작성 순서에 대한 기록 (Stop 게이트 적발)**: 이 문서의 초판은 계획 v2.3 의 digest
> (`e1691b77…`)를 결속했는데, 그 직후 **계획에 결정 기록을 반영하는 편집이 이어져
> digest 가 바뀌었다.** 즉 **결속 규칙을 여기 써 넣고 곧바로 위반했다.**
>
> **결속은 결속 대상이 확정된 뒤에 한다** — 아티팩트를 먼저 쓰고 대상을 편집하면
> 그 결속은 **작성 시점에 이미 stale** 이다. 위 값은 계획이 확정된 뒤 재계산한 것이며,
> 이 문단은 같은 실수가 반복되지 않도록 남긴다.
>
> **같은 실수가 3회 반복됐고, 3회차에 원인이 드러났다.**
>
> | 회차 | 계기 | 저작자의 오진 |
> |---|---|---|
> | 1 | 결정 기록 편집 | "순서 문제" — 결속을 나중에 하면 된다 |
> | 2 | 헤더 버전·심사 이력 갱신 | "확정 판정의 근거 문제" — 독립 검사 후에 하면 된다 |
> | 3 | **계획이 자기 digest 를 본문에 적고 있었다** | **둘 다 아니었다** |
>
> **4회차 (Stop 게이트)**: 범위 밖으로 옮긴 뒤에도 결속이 깨졌다 — 결속식이 `HEAD` 를
> 포함했고 계획·이 문서가 **둘 다 미커밋**이라, **커밋하는 순간 무효**가 된다.
> **이 문서를 커밋하는 행위 자체가 그것을 유발한다.** 원인은 **과잉 결속**이었고,
> 교정은 `HEAD` 를 뺀 결속식으로의 축소다.
>
> **5회차 (Stop 게이트)**: 그 교정을 **"내용만의 해시"** 라 불렀고 **거짓이었다** —
> `shasum` 출력이 `<hash>  <경로>` 형태라 경로가 실린다(실측: `X` ≠ `./X`).
> **기제는 옳았고 이름이 틀렸다.** 경로 결속은 파일 목록 변경을 잡는 요구 성질이다.
> → `bound_set_digest`((경로, 내용) 쌍 집합)로 개명하고 표기를 repo 루트 상대경로로 고정.
>
> **네 번의 교정은 전부 "좁힘"이었다**: 값 갱신 → 순서 → 범위 밖 → 내용 한정.
> **매번 이전 교정이 원인을 잘못 짚었고, 매번 Stop 게이트가 잡았다.**
> 결속은 **"무엇에 대한 주장인가"와 정확히 같은 범위**여야 한다 — 넓으면 무의미하게
> 만료되고 좁으면 우회가 열린다.
>
> **재결속 기록 (6e′ — 2026-08-13)**: 레인 B v2.5 판정 finding #1 이 "계획 v2.5
> 편집으로 위 결속이 무효화됐다"를 적발했다(정본
> `docs/reviews/phase0-completion-contract/20260813-205553/verdict.md`). 계획은
> §12.3.2 순서 규칙(개정 → 동결 → 재결속 → 심사)대로 v2.6 을 저작하고
> `c8373de2` 로 동결했으며, 이 재결속은 그 **동결된 내용**에 대해 수행됐다 —
> 대상 확정 후 결속(3회차 교훈 준수).
>
> 매핑 내용(①②③)은 **무변경**이다 — 재결속은 같은 승인된 해석을 동결된
> v2.6 내용에 결속하는 행위이지 새 해석의 승인이 아니다. 이전 결속값은 이
> 문단이 역사로 보존한다:
> `bound_set_digest ac8d74ba18380ba41a63e1e86a5abf46796f4e8a05aa7a1adfe6f85256419c66`
> · `requesting_plan_version v2.4` ·
> `decided_at_head 2b7b2a209aefb9bd7186949f405f6418fd4902cd`.
>
> **권위 기록 (정직 표기 — D5 선례, `2026-08-07-tos-p02-d5-d6-decision-record.md`)**:
> 이 재결속은 운영자 지시로 수행됐다 — 세션이 동결 보고에 결속값 `328713aa…` 와
> 재결속 절차(갱신 필드 3종)를 명시했고, 운영자가 "진행"으로 승인했다(2026-08-13).
> **귀속은 대화 수준이며 리포-단독 재검증 불가**다. 운영자 countersign 은 이
> 파일에 대한 후속 기입으로 가능하며, 미행사는 거부가 아니다.

> **재결속 기록 (6e″ — 2026-08-14)**: 6e′ 로 v2.6 내용에 재결속된 승인은 레인 B
> v2.6 재심(`needs-attention`·신규 high 3, 정본
> `docs/reviews/phase0-completion-contract/20260813-233530/verdict.md`)의 3건을
> 반영한 **v2.7 개정으로 다시 만료**됐다 — 계획 §12.3.2 O-6 이 성문화한 대로,
> bound_paths 를 편집하는 모든 단계가 결속을 만료시키는 **정상 거동**이다.
> 계획은 같은 순서(개정 → 동결 `c645f7c6` → 재결속 → 심사)를 반복했고,
> 이 재결속은 그 **동결된 v2.7 내용**에 대해 수행됐다.
>
> 매핑 내용(①②③)은 이번에도 **무변경**이다. 이전 결속값은 이 문단이 역사로
> 보존한다:
> `bound_set_digest 328713aa20532b80aaaf9b1fdbdf5f6ca352036f20a135f0dc36e95c61b7d6f6`
> · `requesting_plan_version v2.6` ·
> `decided_at_head 843ecd02355271d17e21b535c962086c9367a9ea`.
>
> **권위 기록 (정직 표기 — 6e′ 과 동일 형식)**: 세션이 동결 보고에 결속값
> `ac515d85…` 와 갱신 필드 3종을 명시했고, 운영자가 "진행"으로 승인했다
> (2026-08-14). **귀속은 대화 수준이며 리포-단독 재검증 불가**다. countersign
> 미행사는 거부가 아니다.

> **재결속 기록 (6e‴ — 2026-08-14)**: 6e″ 로 v2.7 내용에 재결속된 승인은 레인 B
> v2.7 재심(`needs-attention`·잔여 우회 high 3, 정본
> `docs/reviews/phase0-completion-contract/20260814-110807/verdict.md`)의 3건을
> 반영한 **v2.8 개정으로 다시 만료**됐다 — 계획 O-6 이 성문화한 사이클 불변식
> 그대로다. 계획은 같은 순서(개정 → 동결 `03262ef7` → 재결속 → 심사)를 3회째
> 반복했고, 이 재결속은 그 **동결된 v2.8 내용**에 대해 수행됐다. 부수: v2.8 이
> 신설한 «진입 점검 레시피»의 실행 증거(`U15-ENTRY-CHECK.md`, 커밋 `ed11f68d`)가
> 동결과 이 재결속 사이에 기록됐다 — bound_paths 밖이라 결속에 영향 없다.
>
> 매핑 내용(①②③)은 이번에도 **무변경**이다. 이전 결속값은 이 문단이 역사로
> 보존한다:
> `bound_set_digest ac515d85d29bd31ea354f8440bd49b324b7ffb5a2c9d1928acb1b5974e47f43e`
> · `requesting_plan_version v2.7` ·
> `decided_at_head c645f7c6d338aa24ad2a600f68f8ecd663640713`.
>
> **권위 기록 (정직 표기 — 동일 형식)**: 세션이 동결 보고에 결속값 `2e965b11…`
> 와 갱신 필드 3종을 명시했고, 운영자가 "진행"으로 승인했다(2026-08-14).
> **귀속은 대화 수준이며 리포-단독 재검증 불가**다. countersign 미행사는
> 거부가 아니다.
>
> **`decided_at_head` 정정 (stop-time 심판 적발 — 2026-08-14)**: 6e‴ 초판은
> 이 필드에 동결 커밋 `03262ef7…` 을 적었으나, 필드의 정의는 "**판정 당시
> repo 위치**"이고 재결속 편집 시점의 실제 HEAD 는 `ed11f68d…`(실행 증거
> 커밋)였다. 6e′·6e″ 에서는 결정 시점 HEAD 와 동결 커밋이 **우연히 일치**해
> 이 오류 클래스가 관측 불가능했고, 이번 사이클에 증거 커밋이 동결과 재결속
> 사이에 끼면서 처음 드러났다. → `ed11f68d…` 로 정정하고 **기입 규칙을
> 성문화**한다: 재결속 편집 직전 `git rev-parse HEAD` 의 값(결속 대상이 아니라
> 결정 행위의 좌표). 정정은 이 필드가 비결속 참고값이므로 결속 유효성에 영향이
> 없고, v2.8 재심(판정 `20260814-160239`)이 이 정정 **이전의** 아티팩트를
> 심사했다는 사실도 함께 기록한다 — 심판이 대조한 것은 `bound_set_digest`
> 뿐이며 그 값은 불변이다. 부수: 정정 커밋 준비 중 세션이 전체 해시를
> 기억으로 기입했다가 실측(`git rev-parse`)과 불일치해 즉시 재정정했다 —
> 참조 해시는 항상 실측에서 복사한다(발명값 금지 규율의 재확인).

> **재결속 기록 (6e⁗ — 2026-08-15)**: 6e‴ 로 v2.8 내용에 재결속된 승인은
> v2.9(레인 B v2.8 재심 잔여 2건 반영 — 판정 하니스·시점 blob 결속) 개정으로
> 만료됐고, v2.9 동결(`a6d928c5`) 직후 **stop-time 심판이 하니스의 미커밋 권위
> 위조 결함(ENTRY_OK/rc=0 위조 가능)을 적발**해 재결속 없이 v2.10 이 그것을
> 봉합했다(커밋-전용 소비 + R-0 확장, 결함·봉합 모두 실행 재현). 따라서 이
> 재결속은 **v2.9 를 건너뛰고** 동결된 **v2.10 내용**(`4fb03470`)에 대해
> 수행됐다 — 재결속 없는 중간 판은 승인 표면을 가진 적이 없다(O-6 정합).
> 하니스 실행 증거는 `docs/reviews/phase0-completion-contract/20260814-160239/
> U15-ENTRY-CHECK.md`(4-run·전부 프로그램 산출·rc=1·봉합 실증 포함, 커밋
> `2f88f49b`)에 있다.
>
> 매핑 내용(①②③)은 이번에도 **무변경**이다. 이전 결속값은 이 문단이 역사로
> 보존한다:
> `bound_set_digest 2e965b119df950837b40aedec3435d58d5b2b16a5f86c1ae9551d5ea010291b0`
> · `requesting_plan_version v2.8` ·
> `decided_at_head ed11f68d0dd814b47659d39cd29c0bf1a2b7b348`.
>
> **권위 기록 (정직 표기 — 동일 형식)**: 세션이 동결 보고에 결속값 `b0edb769…`
> 와 갱신 필드 3종을 명시했고, 운영자가 "진행"으로 승인했다(2026-08-15).
> `decided_at_head` 는 기입 규칙대로 재결속 편집 직전 실측 HEAD(`2f88f49b…`)다.
> **귀속은 대화 수준이며 리포-단독 재검증 불가**다. countersign 미행사는
> 거부가 아니다.

> **재결속 기록 (현행 사이클 — 2026-08-15, v2.11 내용)**: 직전 재결속(v2.10
> 내용, `ed5ce7ee`)의 승인은 레인 B v2.10 재심(잔여 high 2 — 착수 표면
> 미결속·U-16 merge-DAG 비유일, 정본
> `docs/reviews/phase0-completion-contract/20260815-040451/verdict.md`)을
> 반영한 **v2.11 개정으로 만료**됐다(O-6 정상 거동). 이 사이클에는 재결속과
> 별개로 **이 아티팩트 자신의 매핑 개정**(EV-L6 행 추가 — 운영자 지시,
> `ac38a89a`, 위 매핑 개정 기록)이 있었다 — 매핑 개정은 결속 필드를 건드리지
> 않았고, 이 재결속이 그 확장된 매핑을 **동결된 v2.11 내용**(`e582c01a`)에
> 결속하는 최초의 재결속이다. 가드 억제 실행 증거는
> `docs/reviews/phase0-completion-contract/20260815-040451/U15-ENTRY-CHECK.md`
> (커밋 `c9b6dc0d`)에 있다.
>
> 이전 결속값은 이 문단이 역사로 보존한다:
> `bound_set_digest b0edb769f7229b7377d4454856f06134843900deba7d733d643fa7ab6b0c3e22`
> · `requesting_plan_version v2.10` ·
> `decided_at_head 2f88f49bfd7bf0f407fe57fea5c687c59ac314c5`.
>
> **권위 기록 (정직 표기 — 동일 형식)**: 세션이 동결 보고에 결속값 `06cd99c1…`
> 와 갱신 필드 3종을 명시했고, 운영자가 "진행"으로 승인했다(2026-08-15).
> `decided_at_head` 는 기입 규칙대로 재결속 편집 직전 실측 HEAD(`c9b6dc0d…`)다.
> **귀속은 대화 수준이며 리포-단독 재검증 불가**다. countersign 미행사는
> 거부가 아니다.

> **재결속 기록 (현행 사이클 — 2026-08-15, v2.12 내용)**: 직전 재결속(v2.11
> 내용, `3a53edb6`)의 승인은 레인 B v2.11 재심(신규 high 2·medium 1 — 대리
> 행위 억제·단수 본체 병존·K-14 대조군 부재, 정본
> `docs/reviews/phase0-completion-contract/20260815-092111/verdict.md`)을
> 반영한 **v2.12 개정으로 만료**됐다(O-6 정상 거동). 이 재결속은 동결된
> **v2.12 내용**(`cf9b0295`)에 대해 수행됐다. 실제-행위(D0A-FIRST) 억제 실행
> 증거는 `docs/reviews/phase0-completion-contract/20260815-092111/
> U15-ENTRY-CHECK.md`(커밋 `69d28002`)에 있다. **이번 재결속 전에 운영자가
> 재결속의 의미를 질의했고 세션이 설명했다** — 승인은 그 설명 후의 "진행"이다.
>
> 매핑 내용(①②③, EV-L6 확장분 포함)은 **무변경**이다. 이전 결속값은 이 문단이
> 역사로 보존한다:
> `bound_set_digest 06cd99c1fac2b63d97bb26b33a66f25e7a2badbb8f326d906a97de17c420d4f2`
> · `requesting_plan_version v2.11` ·
> `decided_at_head c9b6dc0d280f64ec8cb66a89346f6dc0b4f207f7`.
>
> **권위 기록 (정직 표기 — 동일 형식)**: 세션이 동결 보고에 결속값 `934516a6…`
> 와 갱신 필드 3종을 명시했고, 운영자가 재결속의 의미 설명을 받은 뒤 "진행"으로
> 승인했다(2026-08-15). `decided_at_head` 는 기입 규칙대로 재결속 편집 직전
> 실측 HEAD(`69d28002…`)다. **귀속은 대화 수준이며 리포-단독 재검증 불가**다.
> countersign 미행사는 거부가 아니다.

> **재결속 기록 (현행 사이클 — 2026-08-18, v2.13 내용)**: 직전 재결속(v2.12
> 내용, `a191910e`)의 승인은 레인 B v2.12 재심(신규 high 2·medium 1 — 비가드
> 착수+HEAD 동시성·reviewer→승인 조상 순서 미강제·원장 간선 결정성 부재, 정본
> `docs/reviews/phase0-completion-contract/20260815-144959/verdict.md`; 그 직전의
> `20260815-102037` 은 Codex 쿼터 소진 판정-불능 기록)을 반영한 **v2.13 개정으로
> 만료**됐다(O-6 정상 거동). 이 재결속은 동결된 **v2.13 내용**(`8a25c3c0`)에
> 대해 수행됐다. T-81 ⑬⑭⑮ 변이 실행 증거(PARENT_MISMATCH 관측·TRANSCRIPT_MISSING
> 실도달·검증자 우회 구성의 CORR(d) red)는
> `docs/reviews/phase0-completion-contract/20260815-144959/U15-ENTRY-CHECK.md`
> (커밋 `3134a87b`)에 있다.
>
> 매핑 내용(①②③, EV-L6 확장분 포함)은 **무변경**이다. 이전 결속값은 이 문단이
> 역사로 보존한다:
> `bound_set_digest 934516a67b52a9f8724c2516e8bfbccbb6da1a986674e2b540c08ca71853a03f`
> · `requesting_plan_version v2.12` ·
> `decided_at_head 69d280025d06318e0b5008adde3ba8a3b6c6eef9`.
>
> **권위 기록 (정직 표기 — 동일 형식)**: 세션이 동결 보고에 결속값 `796ca1e0…`
> 와 갱신 필드 3종을 명시했고, 운영자가 "진행"으로 승인했다(2026-08-18).
> `decided_at_head` 는 기입 규칙대로 재결속 편집 직전 실측 HEAD(`3134a87b…`)다.
> **귀속은 대화 수준이며 리포-단독 재검증 불가**다. countersign 미행사는
> 거부가 아니다.

> **3회차까지의 진단 (보존)** — 근본 원인은 방향이었다. 계획이 자기
> `plan_scope_digest` 를 본문에 적으면
> **고정점이 없다** — 적는 행위가 값을 바꾸므로 갱신할 때마다 다시 틀린다.
> 1·2회차의 "갱신"은 그 구조를 놔둔 채 값만 쫓아간 것이라 애초에 수렴할 수 없었다.
>
> **교정**: 결속은 **아티팩트 → 계획** 한 방향이며, 계획은 이 문서를 **경로로만**
> 참조하고 결속값을 적지 않는다. 이 문서는 계획의 digest 범위 밖(`tos-spec/`)에
> 있으므로 자기 편집이 결속을 깨지 않는다 — **측정자를 피측정 범위 밖에 둔다.**
>
> 같은 원리가 이 저장소에 이미 있다: `codex-gate` 의 `.omc/` 가 digest 범위 밖인
> 이유가 "`verdict.md` 를 쓰는 행위가 digest 를 바꾸면 기록하는 순간 자기 자신을
> 무효화한다"이다. **선례가 있었고 세 번 틀린 뒤에 알아봤다.**

---

## ① 단독 `EV-Ln` 이 하위 레벨을 함의하는가

**아니오.**

`EV-L3` 단독 선언은 `EV-L1`·`EV-L2` 의 요구를 함의하지 않는다. 레벨 집합은
**합집합 규칙**으로 해석한다 — `minimum_evidence_level` 이 나열한 레벨 각각의 매핑을
합집합한 것이 그 evidence 의 하한이며, 나열되지 않은 레벨은 포함되지 않는다.

```
floor(e) = ⋃ { mapping(l) | l ∈ levels(e) }
```

**귀결을 숨기지 않는다**: 단독 `EV-L3` 인 행의 하한은 `{RUNTIME}` 이고,
`RUNTIME` 은 정규 서비스 레지스터 부재로 검증 불가(`UNVERIFIABLE`)이므로
**그 행에는 검증 가능한 하한 kind 가 하나도 없다.** 실측상 해당 형태의 행이
존재하며(`STATE-EV-004`, `status=READY`), 그 행은 요청 계획의 `FWD-a-0`
(검증 가능 쌍 0 = 불충족)을 통과하지 못한다.

**이 판정은 그 행을 통과시키지 않는다.** 별도 처분이 필요하며, 그것은 이 판정의
범위 밖이다 — 요청 계획이 명시적 제외와 계수로 다루거나, 해당 evidence 의
`minimum_evidence_level` 을 정정하거나, 둘 중 하나다.

## ② 레벨→kind 매핑의 승인 주체와 승인 여부

**승인 주체**: 이 저장소의 코퍼스 소유자(운영자). **승인 여부**: 승인.

승인의 성격을 정확히 적는다 — **이 매핑은 `VER-002-001` 에 명시 조항으로 존재하지
않는다.** 실측:

| 확인 | 결과 |
|---|---|
| `VER-002-001` 전문에 `surface_kind` 어휘 | **0건** |
| `VER-002-001` §5 (`:136-179`) 에 레벨→kind 매핑 조항 | **부재** |
| `tools/tos_spec_status.py` 의 `minimum_evidence_level` 검사 | **공백 여부만** (`:374-388`). `status` 와 달리 허용집합 상수 없음 |

**따라서 이 매핑은 규범 텍스트에서 도출된 해석이지 규범 조항의 인용이 아니다.**
"규범이 정한다"고 말할 수 없고, 동시에 "저작자 임의"도 아니다 — 도출 근거가
§5 의 레벨 정의문 자체에 있다(아래 ③).

**승인의 효력 범위**: 비규범 계획(`TOS-COMPLETION-STATUS` 계열)의 `floor` 도출에
한정한다. 이 승인은 `VER-002-001` 의 의미를 확장하지 않으며, 다른 소비자가
다른 매핑을 쓸 근거를 박탈하지도 않는다.

## ③ 승인된 매핑표 (정본)

| `EV-Ln` | `surface_kind` | `VER-002-001` §5 의 도출 근거 |
|---|---|---|
| `EV-L0` | `REVIEWER` | `:142` — "Every EV-L0 review **SHALL** record the reviewer's provenance … an EV-L0 record without reviewer provenance is not independent-review evidence" |
| `EV-L1` | `PACKAGE`, `TEST` | `:144-146` — Model/Property Verification. 검증 대상이 패키지 표면과 그 property 시험이다 |
| `EV-L2` | `FAULT` | `:148` — "**Component Fault Test**" (controlled failure injection) |
| `EV-L3` | `RUNTIME` | `:152` — "**Integrated System Fault Test**" (real persistence/identity/network) |
| `EV-L4` | `RUNTIME` | Broker Sandbox — 실행 표면이 L3 와 같은 종류다 |
| `EV-L5` | `RUNTIME` | Restricted Production — 동일 |
| `EV-L6` | `RUNTIME` | **[2026-08-15 확장]** `:166` — "Runtime monitoring continuously detects drift from verified assumptions" (Continuous Production Conformance, `:164`). 검증 표면이 **운영 중인 실 시스템**이므로 L3~L5 와 같은 종류다. 앵커는 확장 시점 실측(ANCHOR DRIFT 규율 — 기존 행의 앵커는 v2.4 저작 시점 기준이며 재작성하지 않는다) |

**접미 `+Broker` · `+Security` 는 kind 를 추가하지 않는다.** `VER-002-001` §5
Composite Notation(`:168`)이 "`+X` never replaces or lowers `EV-Ln`" 이라 규정하므로
접미는 **레벨을 수식**하지 kind 를 정하지 않는다. 접미가 부과하는 별도 의무는
요청 계획의 `UNCHK-016`(`+Security`)·`UNCHK-017`(`+Broker`)이 등재해 운반한다.

> **매핑 개정 기록 (2026-08-15 — EV-L6 행 추가)**: stop-time 심판이 "이 매핑이
> 인용 도출 범위(`VER-002-001` §5) 안에 정의된 **EV-L6** 을 누락한 채 현행
> 승인이 됐다"를 적발했다. 실측: EV-L6 은 §5 `:164`(Continuous Production
> Conformance)에 실재하고, 두 evidence register 의 `minimum_evidence_level`
> 사용은 **0건**(잠재 결함 — 현재 어떤 행의 floor 도 바뀌지 않는다), T-76 이
> 원시값 우주를 앵커하므로 미도입 상태가 고정돼 있었다.
>
> **권위**: 매핑 내용은 6e 이래 ①②③ 무변경 불변식으로 지켜온 운영자 승인
> 해석이며, 이 확장은 **운영자 지시**("운영자 소관: 매핑표 자체의 확장(EV-L6
> 행 추가)", 2026-08-15)로 수행됐다. **귀속은 대화 수준이며 리포-단독 재검증
> 불가**다(D5 선례 정직 표기). 행의 kind 도출(`RUNTIME`)은 표의 다른 행과 같은
> 방식으로 §5 원문에서 파생했고 근거를 인용했다 — 반증 가능하다.
>
> **이 확장이 바꾸지 않는 것**: 어떤 evidence 행의 상태·floor 도 이동하지
> 않는다(사용 0건 실측). ADR acceptance·live authorization 불변. 매핑 도메인이
> §5 레벨 우주(L0~L6)에 대해 **전역(total)이 됐다**는 것이 유일한 변화다.

**`Profile-dependent`** 는 이 매핑의 대상이 아니다. `VER-002-001` §5 가
"Missing resolution **is a blocker** and SHALL NOT default to the lowest level" 이라
명시하므로, 해석 없이 최저 레벨로 접는 것은 규범 위반이다 — 요청 계획은 이를
`K-13` 차단으로 처리한다.

---

## 이 판정이 부여하지 않는 것

- `VER-002-001` 또는 어떤 RFC/ADR 의 개정·비준
- Evidence row 의 상태 이동 (`STATE-EV-004` 를 포함해 어떤 행도 통과시키지 않는다)
- `restricted_live` / `production` 권한 변경 (둘 다 `NOT_AUTHORIZED` 불변)
- G1/G2/G3 중 어느 것의 충족
- 요청 계획의 레인 B 게이트 통과

**이 판정이 하는 일은 하나다**: 계획이 `floor` 를 도출할 때 **승인된 해석을 인용**할 수
있게 만든다. 그 전까지 계획은 승인되지 않은 자기 해석을 근거로 쓰고 있었고,
심판이 그것을 결함으로 지적했다.
