# U-17 예방 통제 점검 — 운영자 재심사 기록 (addendum-7)

## §0 결속

| 항 | 값 |
| --- | --- |
| 대상 head | `d56785ab`(main == PR #639 병합 커밋) |
| `tools/u17-verify.sh` sha256 | `0b68ef856836380817dac179aee07e09276dbd9cb66feea9817c669bcdf9814e` |
| 계약 blob (`docs/plans/2026-08-12-tos-phase0-completion-contract-design.md`) | `0f8f35682f724c76d58d4b334fec3ecf47518e6f` |
| `tos-spec/src/part-1-foundation/decisions/D0A-PREVENTION-CONTROL.md` `operator_countersign` | `"chihun,lee 2026-08-28T05:23:48Z"`(그대로 인용 — 이 부속이 갱신하지 않는다) |
| 성격 | **운영자 재심사 기록** — 아래 §3 이유로 기계 상태를 바꾸지 않는다 |
| 착수 근거 | 운영자 결정 2026-09-02 「U-17 (b)② — 운영자 재심사 기록 저작」 |

이 문서는 `bash tools/u17-verify.sh`(gh 인증 하)의 두 라이브 평가 — PR #638 착지 직후(2026-09-02
~08:58Z, 로그 `u17_live2.log`) 및 §12.3.4-R 재핀(PR #639) 착지 후(~11:25Z, 로그 `u17_live3.log`) —
가 낸 동일한 `(b)②` 차단을 기록하고, 그 원인·수리 이력·기계 상태 불변의 근거를 계약 원문으로
증명한다. **verdict YAML·`operator_countersign` 항목을 포함하지 않는다.**

---

## §1 — 실측 원문

### 최종 상태값 (u17_live2.log·u17_live3.log 공통)

```text
u17_live_state=PREVENTION_ACTIVE
U17-fire PREVENTION_UNVERIFIED_REVISION: (b)② d=28475ca1ca82fe99054a2cc04cf1b58e4550097a head=21c47e42ff1487282ce2f9da0df11756ff146a3a 4단계 ∀-success 위배 — [(0, 100181808552, 'failure')] (∃-증인 금지 · 케이스 ③ «정본 fail + decoy success» 포함)
U17-α t_land = min{merged_at(착지 PR) : d∈D} = 2026-09-02T08:57:41Z  (서버 부여 값만 · 커밋 author/committer date 불신)
U17-α ruleset 21886181: ruleset 21886181 created_at=2026-08-30T23:51:12.269000+00:00 ≤ t_land ∧ updated_at=2026-09-02T08:57:40.403000+00:00 ≤ t_land
prevention_control_state=PREVENTION_UNVERIFIED_REVISION
reason=(b)② d=28475ca1ca82fe99054a2cc04cf1b58e4550097a head=21c47e42ff1487282ce2f9da0df11756ff146a3a 4단계 ∀-success 위배 — [(0, 100181808552, 'failure')] (∃-증인 금지 · 케이스 ③ «정본 fail + decoy success» 포함) [수집 1건 중 전순서 최소]
```

`u17_live2.log` 는 동일한 `(b)②` reason 을 낸다 — PR #639(§12.3.4-R 재핀)의 착지가 두 실행
사이에 있었음에도 값이 바뀌지 않았다. 이유는 §3.

### (b)② 4단 사다리 판정 과정 (u17_live3.log, 148–226행 발췌, verbatim)

```text
U17-C1R ①-R 1,000-런 상한 관측: 수집 런 수=1 · total_count=1
U17-C2S ②-S run→suite 사상: |S_R|=1  S_R=[91075486666]
U17-C3E ⑤ suite=91075486666 이름==tos-gate 인 check-run 수(동명 상한 관측대상)=1
U17-C3 ③-C 합집합 |E₀|=1 (S_R 전체 소비 완료 · 1,000-suite 잘림의 대상 아님 — GitHub 처방 이행)
U17-ALFA0 (limb③) check-suites 1,000-suite 상한 관측: 수집 수=7 · total_count=7
U17-ALFA1 S_A(포함 조건: head_sha==21c47e42ff1487282ce2f9da0df11756ff146a3a ∧ app.id==15368) = ["91075486666", "91075486707", "91075486743"]
U17-ALFA2 (i) S_R∖S_A = []
U17-ALFA3 (ii) S_A∖S_R = ["91075486707", "91075486743"] (각 원소 정체성 확인 필요 — «두 축 모두» 달라야 «타 워크플로»)
U17-ALFA3d ⓓ s=91075486707 1,000-결과 상한 관측: 수집 런 수=1 · total_count=1
U17-ALFA4 s=91075486707 정체성 판정=OTHER (workflow_id==343700405 ∨ path==.github/workflows/tos-gate.yml · check_suite_id==91075486707 귀속 확인 — 보수 방향: «타 워크플로» 이려면 두 축 모두 달라야 하고 둘 다 실재해야 한다)
U17-ALFA3d ⓓ s=91075486743 1,000-결과 상한 관측: 수집 런 수=1 · total_count=1
U17-ALFA4 s=91075486743 정체성 판정=OTHER (workflow_id==343700405 ∨ path==.github/workflows/tos-gate.yml · check_suite_id==91075486743 귀속 확인 — 보수 방향: «타 워크플로» 이려면 두 축 모두 달라야 하고 둘 다 실재해야 한다)
U17-ALFA5 α 축 통과: (i) S_R⊆S_A ∧ (ii) S_A∖S_R 전 원소 «확인된 타 워크플로»
U17-BETA0 β 계수 관측: {"left": 1, "right": 1, "missing_suite": 0}
U17-BETA1 β 축 통과: 좌=1 == 우=1
U17-CERT ⑥ 완전성 인증서: CERT_OK|{"cert": {"cap_R": {"observed": true, "count": 1, "total": 1}, "cap_E": {"observed": true}, "cap_S": {"observed": true, "count": 7, "total": 7}, "alpha": {"observed": true, "subset_ok": true, "identity_ok": true}, "beta": {"observed": true, "left": 1, "right": 1}, "cap_Rs": {"observed": true, "uses": 2}}, "delta": {"rules_branches": {"observed": true, "discriminated": true, "why": "partial last page(4<100)"}, "rulesets": {"observed": true, "discriminated": true, "why": "partial last page(2<100)"}, "pulls": {"observed": true, "discriminated": true, "why": "partial last page(1<100)"}}}
U17-fire PREVENTION_UNVERIFIED_REVISION: (b)② d=28475ca1ca82fe99054a2cc04cf1b58e4550097a head=21c47e42ff1487282ce2f9da0df11756ff146a3a 4단계 ∀-success 위배 — [(0, 100181808552, 'failure')] (∃-증인 금지 · 케이스 ③ «정본 fail + decoy success» 포함)
```

완전성 인증서(`CERT_OK`)가 모든 관측축을 `observed:true`로 낸 뒤에도 사다리 4단계가 유일한
check-run(`100181808552`, `conclusion=failure`)에서 걸린다 — 우주가 불완전해서가 아니라
**그 우주 안의 유일한 원소가 failure** 이기 때문이다.

---

## §2 — 원인과 수리 이력

- check-run `100181808552`(`tos-gate`, run `33609738138`)은 착지 PR **#638**(D0A-FIRST `28475ca1`
  포함)의 head `21c47e42`에서 실행됐고, 그 시점 `.github/workflows/tos-gate.yml`이 검증하던
  하니스 정본 sha는 pre-fix 세대 `1817c9ef…`였다.
- 근본원인(commit `8199bb38`): `tools/tos_entry_harness.sh`의 `yaml_list`/`yaml_scalar` awk
  프로그램이 `exit`로 조기 종료 → 상류 `printf`(71,870바이트, Linux 파이프 용량 65,536)가 쓸
  바이트를 남긴 채 파이프가 닫혀 EPIPE → `set -o pipefail`이 그것을 파이프라인 실패로 승격 →
  `HARNESS_ABORTED`. mawk는 통과하고 gawk·one-true-awk는 떨어진다(ubuntu:24.04 대조군 확인).
  GitHub `ubuntu-latest`의 awk는 gawk — run `33609738138` 로그가 확증한다.
- 수리는 PR **#639**(base `main`, head `a9da27b0`, merged_at `2026-09-02T11:20:02Z`, 병합 커밋
  `d56785ab`)로 4커밋(C1~C4) 착지:
  - **C1** `8199bb38` — 하니스를 `exit` 대신 `done` 플래그 방식으로 고쳐 gawk EPIPE 제거(의미
    보존 패리티 708 비교·차이 0으로 실증) + sha 재핀 `1817c9ef…→059e13f2…`(lockstep: 계약 6자리
    + 상위 계획 2곳 + 워크플로 + `wfcanon-v222.py` + `u17-verify.sh` + `bound_set_digest`).
  - **C2** `cdecb692` — O-6 재결속(sha 재핀에 따른 결속 만료 해소).
  - **C3** `46467fa9` — Codex 레인 B 재심, verdict 스탬프 `20260902-195656`
    (`docs/reviews/phase0-completion-contract/20260902-195656/verdict.md`) — adjudicator
    `codex` · **approve** · findings 0(첫 잡 `review-mtjzg4yd-1w38uv`도 approve).
  - **C4** `a9da27b0` — `TOS-COMPLETION-STATUS.md` 재생성.
- PR #639의 head `a9da27b0`에서 `tos-gate`가 **최초로 success**(check-run id `100225459033`,
  run `33623414512`, 라이브 확인) — 동일 gawk 러너(`ubuntu-latest`) 위에서 ENTRY_OK.

---

## §3 — 왜 기계 상태가 불변인가

계약 §11 (b) 절, 사다리 4단계 원문(`docs/plans/2026-08-12-tos-phase0-completion-contract-design.md:7418-7420`):

> **4단계 — ∀-success**: **`∀ c ∈ C : c.conclusion == "success"`**. 하나라도 아니면
> **`PREVENTION_UNVERIFIED_REVISION`**(케이스 ③ «정본 fail + decoy success» 포함).

같은 절 서두(`:7054, 7057-7058`):

> **(b) 리비전 특정 — 사후·완료 판정** (§11)
> ```text
> ∀ d ∈ D:
>    ① gh api … repos/{o}/{r}/commits/{d}/pulls 로 **착지 PR 을 해석**  (host 결속·C6)
>         · PR 부재 · merged 아님 · base 가 target 이 아님  → UNVERIFIED_REVISION
>    ② 그 PR 의 **`head.sha`** 에 대해 «자격 있는 check-run 의 우주» `E₀` 를 파생한다
> ```

(b)②는 **착지 PR의 head.sha 위에서 그 시점 완결된 check-run 집합**을 판정한다. `d=28475ca1`
(D0A-FIRST)의 착지 PR은 **#638**이고 이미 병합됐으며 그 head `21c47e42`는 고정된 값이다.
GitHub은 과거 커밋 sha 위에서 완료된 check-run을 소급 변경하지 않으므로, 몇 번을 재조회해도
`(0, 100181808552, 'failure')`는 그대로 남는다. 즉 **PR #639의 수리·재승인은 PR #638의 head
위 판정에 아무 영향을 주지 않는다** — 이것이 §12.3.4-R 재핀 착지 전후(u17_live2.log·
u17_live3.log) 값이 동일했던 이유다.

α 축(연속성 소비자, `PREVENTION_CONTINUITY_UNVERIFIABLE`)에는 계약과 하니스 양쪽에 「운영자
재심사 경로(영구 차단 아님)」 문구가 명시로 붙어 있다(계약 `:7372-7373, 8163-8164, 8237,
8314` · `tools/u17-verify.sh:912`, `grep -n "운영자 재심사" tools/u17-verify.sh` 로 확인 —
매치는 `PREVENTION_CONTINUITY_UNVERIFIABLE` 케이스 한 곳뿐). **(b)②(`PREVENTION_UNVERIFIED_
REVISION`)에는 그런 조항이 없다** — 계약 전문에서 「운영자 재심사」가 등장하는 자리는 전부
α/연속성 소비자에 결부돼 있고(`:7372`의 «전이적 차단» 서술도 completed_at 미완결 limb의
비유이지 (b)②의 고유 조항이 아니다), (b)② 근처에는 재심사·해제 경로가 **문언으로 존재하지
않는다**.

**이 addendum은 기계 상태를 바꾸지 않는다.** `prevention_control_state`는 이 문서 작성 후에도
`PREVENTION_UNVERIFIED_REVISION`으로 남는다. 이 값이 바뀌는 경로는 계약 문언상 둘뿐이다:

1. 운영자가 완료-판단(completion-judgment) 시점에 이 문서화된 편차 — 「D0A-FIRST 착지 PR은
   pre-fix 하니스로 검증됐으나 그 결함은 이후 식별·수리·독립 재승인(Codex approve, findings 0)
   완료」 — 를 **수용**한다.
2. 운영자가 계약 (b)②의 판정 범위를 **개정**한다(예: 과거 리비전을 «당대 하니스» 대신 «최신
   하니스 재평가»로 판정하는 조항 신설).

---

## §4 — 운영자 결정 항목

이 문서는 승인·countersign·waiver가 아니며 추천을 담지 않는다. 남은 선택은 §3의 두 경로뿐이다.

1. **완료-판단 시점 수용** — 이 addendum을 근거로 (b)②의 이 편차(과거 pre-fix 하니스 실행
   결과)를 완료 판단에서 명시적으로 받아들인다.
2. **계약 (b)② 범위 개정** — 2026-09-02 운영자가 이미 거절했다. 재상정하려면 새 지시가
   필요하다.
