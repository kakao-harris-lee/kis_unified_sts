# OQ-11 Disposition — Evidence Level to Surface Kind Mapping

> **Document class**: Non-normative decision record. This document does **not** amend
> `VER-002-001` or any RFC/ADR. It records an interpretation decision and its authority,
> so that a downstream non-normative plan can cite an approved reading instead of
> asserting one. No evidence state, ADR acceptance, or authorization changes.

```yaml
disposition: RESOLVED_MAPPING_APPROVED
bound_set_digest: ac8d74ba18380ba41a63e1e86a5abf46796f4e8a05aa7a1adfe6f85256419c66
bound_paths:            # repo 루트 기준 상대경로. `./` 접두 금지 (표기가 digest 에 실린다)
  - docs/plans/2026-08-12-tos-phase0-completion-contract-design.md
  - docs/plans/2026-08-11-tos-completion-development-plan.md
requesting_plan_version: v2.4
contract: 해당 계획 §12.3.1 (6e 산출 계약)
authority: 운영자 (this repository's corpus owner)

# 비결속 참고값 — 대조 대상이 아니다. 이 값이 달라도 결속은 유효하다
decided_at_head: 2b7b2a209aefb9bd7186949f405f6418fd4902cd
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

**접미 `+Broker` · `+Security` 는 kind 를 추가하지 않는다.** `VER-002-001` §5
Composite Notation(`:168`)이 "`+X` never replaces or lowers `EV-Ln`" 이라 규정하므로
접미는 **레벨을 수식**하지 kind 를 정하지 않는다. 접미가 부과하는 별도 의무는
요청 계획의 `UNCHK-016`(`+Security`)·`UNCHK-017`(`+Broker`)이 등재해 운반한다.

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
