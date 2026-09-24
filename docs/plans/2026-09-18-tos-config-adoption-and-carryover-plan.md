# TOS 설정값 채택 + §7.4/F 이월 처분 계획

- 작성: 2026-09-18 · 세션 모델 단독 저작(운영자 지시 2026-09-04)
- 선행: `run` 구동 아크 4항 착지(`docs/plans/2026-09-17-tos-run-boot-and-real-sources-arc-plan.md`) ·
  커널 라운드 #4 착지(`docs/plans/2026-09-17-tos-kernel-round-4-plan.md` §7)
- 운영자 지시(2026-09-18): **「미해소 5건부터 진행」 · 「후속 처분도 진행」 · 「설정값은 승인함」**
- 기준선: main `adaf0239` · 커널 **9537** · 런타임 **2462**

---

## 0. 승인이 무엇의 원천이 될 수 있는가 — 이 계획의 축

운영자가 「설정값은 승인함」이라고 했다. 그러나 **승인은 정책 값의 원천이 될 수 있어도 측정 값의
원천은 되지 못한다.** 이 아크가 내내 지킨 「원천 없는 수치는 `null`」을 승인으로 우회하면 그 규율은
사라진다. 따라서 남은 값을 **세 부류로 갈라** 다르게 처리한다.

| 부류 | 원천 | 이 계획의 처리 |
|---|---|---|
| **(가) 운영자 정책 판단** — scope(어느 계좌·종목), 임계값, 게이트 기준 | **승인 자체가 원천이다.** 정책은 측정 대상이 아니라 결정 대상 | 구체값을 제안하고 근거를 적어 채택. `approved_by` 에 2026-09-18 승인 기재 |
| **(나) 파생 digest** — `canonical_digest`, `*_id`, `activation_record_id` | 다른 승인 문서 + `safety_activation.yaml::members` 에서 **계산된다** | 승인 불필요. `print-policy-digests` 로 도출해 기입. **손으로 짓지 않는다** |
| **(다) 측정값** — 주식 가격대별 호가단위 표 | **브로커가 정한다.** 승인으로 만들 수 없다 | 승인 대상이 **아니다**. 실측 경로를 설계해 핸드오버. 그때까지 `null` 유지 |

**(다)를 (가)로 취급하는 것이 이 계획이 막으려는 단 하나의 실수다.** 커널 라운드 #4 §0.1 이 바로 그
경계에서 한 번 흔들렸고(「측정 원천 0건」이 틀렸던 건), `contract-keeper` 가 찾은 HIGH(`optional_str` 이
`"TBD"` 통과)는 그 경계를 **뒷문으로** 여는 경로였다.

### 0.1 실측 — 무엇이 얼마나 남았나

`docs/plans/2026-09-17-tos-deployment-instance-inventory.md` 와 `grep -n "TBD" config/tos_runtime/paper/*.yaml`.

- **부팅 차단 23종**: 인벤토리 §2 표에서 `**필수**` 로 마킹된 행을 **직접 센 값**
  (`awk '/^\| [0-9]+ \|/ && /\*\*필수\*\*/' | wc -l` → 23, `strategies/` 포함).
  이 중 채택된 것은 **4종**(`calendar`·`risk`·`venue_constraint_policy`·`order_construction_policy`).
  → **19종이 example 뿐**이다(`comm -23 <필수23> <채택6>` → 19).

  > 정정(2026-09-18, 조사 레인 지적): 이 절의 초고는 **「13종」**이라고 적었다. **틀렸다.**
  > 인벤토리 §2 요약 문단이 나열한 「무조건 호출 18종」 목록은 **이미 채택된 4종을 뺀 이름만**
  > 열거한 것인데, 그것을 총량으로 읽고 거기서 채택 6을 **또** 뺐다 — 이중 차감이다.
  > 채택 6종 중 2종(`action_flow_policy`·`aggregate_risk_policy`)은 「사실상 필수」 행이라 애초에
  > 필수 23 집합 밖이기도 하다. 작업량이 **1.5배**로 늘어난다.
- **`construction.yaml`**: 채택 인스턴스가 **아예 없다**(`config/tos_runtime/paper/` 에 부재).
  `run` 서브커맨드 전용 필수. 리프 7개 전부 `null`.
- **채택된 6종 안의 잔여 TBD**: `aggregate_risk_policy` 9 · `action_flow_policy` 8 ·
  `venue_constraint_policy` 4 · `order_construction_policy` 6 (+ 커널 #4 가 추가한 3키는 named-TBD 유지).
  `calendar.yaml`·`risk.yaml` 은 TBD **0**.
- **부류 비율(실측)**: 위 잔여 27개 중 **(나) 파생 digest 계열이 15개**(`canonical_digest`/`*_id`/
  `activation_record_id`), **(가) 정책 판단이 12개**(scope 계열 8 + `admitted_quantity_bases` +
  sizing `value` + OCP 3키 중 정책 성격인 것). **(다)는 0** — tick 표는 이 파일들 밖이다.

즉 **절반 이상이 승인이 아니라 계산으로 풀린다.** 이것이 이 계획의 작업량을 크게 줄인다.

### 0.1.1 조사 레인이 정정한 것 — (나)의 성격이 셋으로 갈린다

초고는 `canonical_digest`/`*_id`/`activation_record_id` 를 **하나의 (나)** 로 묶었다. 실측 결과
**셋이 다른 것**이었다. 이 구분이 작업량을 다시 줄인다.

| 실측 | 뜻 | 처리 |
|---|---|---|
| **`canonical_digest` 는 `"TBD"` 로 영구히 둬도 된다** — `check_canonical_digest`(`venue/_policy_primitives.py:241-247`)가 `TBD_DIGEST` 를 **항상 통과**시킨다 | 진짜 엄격 동등이 요구되는 곳은 **`safety_activation.yaml::members[].digest`** 다(`venue/activation.py:130-145`, exact match) | **채우지 않는다.** 정상 배포 형태는 「정책 파일의 `canonical_digest` 는 TBD, `members` 만 정확」 |
| **`activation_record_id` 는 죽은 리프다** — `grep -rn "activation_record_id" tos/runtime/src tos/src` → **프로덕션 0건**(배포 YAML 4곳과 테스트 픽스처에만 존재) | 활성화 판정은 `(kind, member_id, generation, digest)` **4-튜플로만** 이뤄지고 이 필드는 참여하지 않는다 | **채우지 않는다.** 파생되는 게 아니라 **아무도 읽지 않는다** |
| **`members[]` 4-튜플만이 실제 작업이다** | `print-policy-digests` 출력 3필드 + `kind`(enum 라벨을 사람이 전사) | **이것만 채운다** |

따라서 (나) 15개 중 **실제로 채워야 하는 것은 `safety_activation.yaml::members` 뿐**이다.

### 0.1.2 부류가 하나 더 있다 — **(라) 배포 환경 실측값**

`release.yaml::expected_code_digest` / `expected_dependency_set_digest` 는 **(가)가 아니다.**
운영자가 정하는 값이 아니라 **현재 설치된 소스트리·의존성 집합에서 실측**되는 값이다
(`print-digests` — **`print-policy-digests` 와 다른 서브커맨드다**, `operations.dependency_admission.
observe_runtime_artifact().source_tree_digest`).

(나)와도 다르다: (나)는 **다른 정책 문서**에서 파생되지만 (라)는 **배포 환경 자체**에서 파생된다.
파생 방향이 반대라 순서 의존도 반대다 — 정책 확정이 선행조건이 아니라 **설치 상태**가 선행조건이다.

**제안표에서 (라)를 (가)로 놓고 「운영자가 정한다」고 적으면 틀린다.**

### 0.1.4 ★ 실증된 부류 — **배포 example 을 복사하면 부팅이 거부된다**

잠재가 아니라 **이미 깨져 있다.** 팀리드가 직접 로드해 확인:

```
$ python -c "load_activation_members('tos/runtime/config/safety_activation.example.yaml')"
REFUSED: 'members' key is missing or still null (named-TBD) —
         an activation document must explicitly declare its member list, [] included
```

`safety_activation.yaml` 은 **네 곳**에서 읽힌다(`compose/_riskstate_wiring.py:72` ·
`_safety_wiring.py:99` · `_venue_wiring.py:109` · `venue/activation.py`). example 은 그중
**spg 소유 스키마(`activation:` 블록)만** 채우고 `venue/activation.py::load_activation_members`
가 요구하는 **`members:` 키가 아예 없다.**

**이 아크에서 이미 나온 부류다.** W2 의 `marketfeed.example.yaml` 이 `intake_kind` 를 빠뜨렸던 것과
같다 — **한 파일을 여러 로더가 읽는데 example 이 한쪽만 만족시킨다.** 그때 인스턴스만 고치고
부류를 닫지 않았다.

**기존 스모크 테스트 관례로는 이것이 안 잡힌다.** `test_shipped_example_file_is_all_null_and_
therefore_refuses` 는 「거부되는가」만 핀하는데, 이 파일은 **거부된다** — 다만 **틀린 이유로**
거부된다(「값이 전부 null 이라」가 아니라 「구조가 불완전해서」). 그 관례는 지금 3개 파일에만
붙어 있기도 하다(`grep -rln "shipped_example" tos/runtime/tests` → 3건).

**이 계획은 example 을 복사해 실파일을 만드는 계획이다.** 깨진 example 을 복사하면 그 결함이
배포 파일로 옮겨간다. 그러므로 **A-0b 에서 부류를 닫고** 값 저작을 시작한다.

### 0.1.3 ★ 잠재 부류 — 18종 로더가 `"TBD"` 를 막지 않는다

커널 라운드 #4 의 `contract-keeper` HIGH(`optional_str` 이 `"TBD"` 통과)는 **인스턴스였고 부류는
열려 있다.** 조사 실측:

- `null` 과 `"TBD"` 를 **둘 다** 거부하는 것은 **`construction.yaml` 로더와 `venue/_policy_primitives.py`
  둘뿐**이다 — 전자는 라운드 #4 이후 신설, 후자는 라운드 #4 가 직접 고친 파일.

  > 정정(fact-check 2026-09-18): **「`venue/_policy_primitives.py` 는 안전하다」는 파일 단위 뭉뚱그림이었다.**
  > 그 파일 안에 `require_str`(TBD 미검사)과 `require_filled_str`/`optional_str`(검사함)이 **공존**하고,
  > main 기준으로는 **미검사 쪽이 다수**였다(OCP 로더 12:1 · venue 4:1 · action_flow 4:3 · aggregate_risk 4:1).
  > A-0 라운드 2 가 24곳 중 14곳을 강한 쪽으로 교체해 **6:7 / 3:2 / 2:5 / 2:3** 이 됐고, 팀리드가 남은 13곳을
  > 확인한 결과 **enum 토큰이거나 `require_str` 직후 인라인 TBD 체크가 있다**(예:
  > `_order_construction_policy_loader.py:458-464` 의 `axes.value`). 즉 지금은 갭이 아니다.
  >
  > **다만 검사기의 한계가 여기서 드러난다** — `tos_named_tbd_guard.py` 는 파일이 가드 관용구를
  > **참조하는지**만 보므로, 한 파일 안에서 **일부 호출부만** 가드를 쓰는 상태를 구분하지 못한다.
  > 이번엔 결과적으로 안전하지만 **호출부 단위 보장이 아니다.** 등재하고 넘어간다.
- **라운드 #4 이전부터 있던 18종 로더는 `"TBD"` 문자열 검사 자체가 없다**(`_require`/`_require_str`/
  `require_str_field` 계열 — 예: `brokercap/scopes.py:277-282`). 지금 안전한 이유는 로더가 막아서가
  아니라 **example 에 `"TBD"` 관례가 아직 침투하지 않아서**다.

**이 계획은 이 파일들에 값을 쓰는 계획이다.** 즉 내가 `"TBD"` 를 placeholder 로 쓰는 순간 **18종이
그것을 유효한 값으로 승인한다.** 그러므로 **A-0 에서 부류를 먼저 닫고** 값 저작을 시작한다
(§4 W-A). 「지적을 고쳤는가」가 아니라 「같은 지적이 또 나올 수 있는가」다.

### 0.2 순서 의존이 하나 있다

`admitted_quantity_bases` / sizing `value` 는 **전략 파일의 `quantity_basis` 가 먼저 정해져야** 한다
(인벤토리 §4). 그리고 파생 digest는 그 위의 정책 값이 확정된 **뒤에만** 계산된다. 따라서
**(가) → (나)** 순서는 뒤집을 수 없다.

---

## 1. 포함 · 제외

**포함**: §7.4 미해소 5건 · 후속 처분 F-1~F-4 · 설정값 채택((가)+(나)) · `run` 실부팅 도달.

**제외** (각각 한 줄 사유):

| 제외 | 사유 |
|---|---|
| **(다) tick 표 실값** | 브로커 측정값이다. 승인으로 만들지 않는다. 실측 경로 설계까지만(W-B3) |
| **F-3 별도 KIS 앱 등록** | 외부 등록 행위 — 코드가 아니라 운영자 계정 작업 |
| **Codex 부착** | 유료 외부 호출. 범위·비용 승인이 별도로 필요하다(§6 ①) |
| **실 모의 서버 실행** | 헤르메틱 테스트까지가 이 계획. 실행은 운영자 핸드오버 |
| **계약 문서** | byte-frozen · 부수 편집 금지 |
| Phase 3 §7.11 이월 | 이번에도 미선택 |

---

## 2. 결정

1. **웨이브 3개, 의존 순서대로.** W-A(설정값) → W-B(§7.4 잔여) → W-C(F 처분). W-B/W-C 는 서로
   독립이라 병렬 가능하나, W-A 는 `run` 부팅이라는 단일 종료조건을 가지므로 먼저 끝낸다.
2. **(가) 값은 제안과 채택을 한 커밋에 넣지 않는다.** 제안표를 먼저 문서로 내고, 그 문서를 근거로
   실파일을 채운다 — 이 저장소가 venue/OCP 에서 쓴 방식 그대로(`approved_by` 에 제안 문서를 인용).
   운영자의 2026-09-18 승인은 **제안표 전체에 대한 승인**으로 기록한다.
3. **(나) 는 손으로 적지 않는다.** `print-policy-digests` 출력을 그대로 옮기고, 옮긴 명령과 출력을
   커밋 메시지에 남긴다. 값이 맞는지는 `tos_contract_check.py` 와 부팅이 판정한다.
4. **안전 계열 값은 제안표에서 따로 표시한다.** Hard Safety Envelope · 리스크 한도 · 릴리스 게이트는
   틀리면 비싸다. 「승인함」을 받았어도 **운영자가 눈으로 확인할 자리를 만든다** — 구체값을 제시하되
   한 표에 모아 `⚠` 로 표시한다. 숙제를 돌려주지 않되 조용히 넘기지도 않는다.
5. **§7.4 ④(롤아웃 순서)는 런북으로 닫는다.** 실측 결과 **배포 스크립트가 아예 없다** —
   `apply_migrations` 호출부는 `compose/cli.py:844`(`migrate` 서브커맨드) 하나뿐이고 운영자 수동이다.
   즉 「스크립트가 순서를 지키는가」라는 질문 자체가 성립하지 않는다. `docs/runbooks/` 에 tos 운영
   런북이 **없으므로**(측정: `ls docs/runbooks/ | grep -i tos` → `tos-kis-mock-transport.md` 뿐) 새로 쓴다.
6. **F-2 는 코드 전에 결정이 먼저다.** 두 착지 레인의 계약이 합성되지 않는 문제이고, 얇은 어댑터로
   안 된다는 것이 이미 3중 확인됐다. **설계 결정을 문서로 먼저** 내고 그 다음에 코드.
7. **저작과 검토는 다른 패스.** 웨이브마다 `code-reviewer`(sonnet) + 변경 표면별 게이트.
   W-A 는 승인·정책 값이므로 `contract-keeper`, W-C 의 F-1 은 화해 경로라 `code-reviewer` 만.

---

## 3. 기각 대안

| 대안 | 기각 사유 |
|---|---|
| 「승인함」을 근거로 tick 표를 채운다 | **(다)를 (가)로 취급하는 것.** 이 계획 §0 의 축을 정면으로 깬다 |
| 파생 digest 를 손으로 계산해 적는다 | 도출 도구가 이미 있다(`print-policy-digests`). 손계산은 재현 불가능한 값을 만든다 |
| 19종을 한 커밋에 몰아서 채운다 | 부팅 실패 시 어느 값이 원인인지 분리되지 않는다. 파일 단위로 나눠 각 단계가 부팅 진척을 증명하게 한다 |
| F-2 를 어댑터로 우회 | 감쌀 대상이 없다 — adapter 가 **제2의 자격증명 로딩 경로**가 된다(아크 §7.2 F-2, 3중 확인) |
| §7.4 5건을 한 레인에 몰기 | 성격이 제각각이다(코드·런북·측정설계·운영자결정). 한 레인이 네 부류를 다 잘하지 못한다 |

---

## 4. 웨이브

### W-A — 설정값 채택 · 종료조건 = **`run` 이 실제 부팅한다**

| # | 내용 | 종료 조건 |
|---|---|---|
| **A-0** | **잠재 부류 닫기(§0.1.3).** 공용 `_require_str`/`require_str_field`/`_require` 계열에 named-TBD 거부 추가 — **값을 쓰기 전에** | `"TBD"` 를 넣으면 거부됨을 로더별로 핀 · 거부 코드를 지우면 red(뮤테이션) · 기존 부팅 무회귀 |
| **A-0b** | **실증 부류 닫기(§0.1.4).** `safety_activation.example.yaml` 에 `members:` 추가 + **모든 배포 example 이 자신을 읽는 *모든* 로더를 통과/거부하는지** 검사. 거부는 **이유까지** 핀 | 깨진 example **0** · 스모크가 「거부됨」이 아니라 **「올바른 이유로 거부됨」**을 핀 · 로더를 하나 더 추가해도 검사가 따라옴 |
| A-1 | **제안표 저작**(문서). (가) 정책값 + **19종** example-only 파일의 필수 리프. 값마다 **근거 한 줄**. 안전 계열은 `⚠` 표로 분리 | 저작한 값 **전부에 근거**가 붙어 있음 · (다) 부류 **0건** |
| A-2 | (가) 채택 — 실파일 기입. `approved_by` 에 「operator 2026-09-18 · 제안표 §n」 | `grep -n "TBD" config/tos_runtime/paper/*.yaml` 에서 (가) 계열 **0** |
| A-3 | (나) 파생 — `print-policy-digests` 출력을 기입 | digest 계열 **0** · 명령과 출력을 커밋 메시지에 인용 |
| A-4 | `construction.yaml` 신규 인스턴스 — `price_field_key`/`shape_price_field_key` 는 배포된 `critical_input_policy.yaml::fields[].field_key` 와 **일치해야** 한다(로더가 대조하지 않으므로 사람이 맞춰야 함) | 두 파일의 키가 실제로 일치함을 테스트로 핀 |
| A-5 | **부팅** — `run` 을 실제 데이터 디렉터리에 대고 구동 | **거부 없이 틱을 관측**하거나, 거부된다면 **어느 값 때문인지** 지목 |

**A-5 가 이 웨이브의 유일한 진짜 종료조건이다.** 나머지는 그 수단이다. 부팅이 안 되면 무엇이
모자란지가 결과물이다 — 「채웠다」가 아니라 「구동한다」로 판정한다.

### W-B — §7.4 잔여

| # | 내용 | 종료 조건 |
|---|---|---|
| B-1 | **① `committed_vector_json` 을 `verify_replay` 범위 안으로.** `payload_json` 에 싣고 `fold_reservations_from_entries`/`digest_of_reservation_map` 에 포함. **pre-K-4 엔트리 처리**가 핵심 설계점(그 엔트리에는 벡터가 없다 — 「없음」과 「빈 벡터」를 섞지 말 것) | 기존 로그가 재폴드되고 **기존 엔트리 판정 불변** · 벡터를 직접 변조하면 `verify_replay` 가 **잡는다**(뮤테이션) · KNOWN LIMITATION 주석 제거 |
| B-2 | **④ RCL v1→v2 운영 런북.** `docs/runbooks/tos-rcl-schema-migration.md` 신설. 순서(구버전 정지 → `migrate` → 신버전 기동) · 양방향 `SchemaVersionRefused` 의미 · 백업/롤백 | 런북의 명령이 **실제로 실행 가능**(복사해서 붙이면 돈다) · 배포 스크립트 부재를 명시 |
| B-3 | **② tick 표 실측 경로 설계.** GET-only 로 `FHKST01010100::output.aspr_unit` 을 가격대별로 수집하는 프로브 설계 + 핸드오버 문서. **실행은 운영자** | 어느 종목·어느 가격대를 몇 건 찍어야 표가 되는지가 **수치로** 적혀 있음 · GET-only 준수 · 배포 값은 여전히 `null` |

**②(=B-3)은 값을 채우지 않는다.** 이 웨이브가 내는 것은 표가 아니라 **표를 만들 수 있는 경로**다.

### W-C — 후속 처분 F

| # | 내용 | 종료 조건 |
|---|---|---|
| C-1 | **F-1 `broker_execution_id` 교차조회.** `ReconciliationService` 가 `attempt_id` 없이도 오더를 잇게 한다. 없으면 오더 축 재무장·캐파시티 해제가 **구조적으로 영구 차단**(아크 §0.4 인용) | 조인되는 경우 재무장 가능 · **조인 못 하는 경우는 여전히 fail-closed**(느슨해지지 않음을 뮤테이션으로) |
| C-2 | **F-2 토큰 소유권 결정(문서 먼저).** W2 `KisTokenLifecycle`(평문 미노출) vs W3 `KisWitnessTokenSession`(요청마다 평문 요구). KIS 가 매 인증 호출에 시크릿 헤더를 요구하므로 **평문은 어느 선택지에서도 요청마다 실체화된다** — 질문은 「누가 소유하고 얼마나 오래, 몇 군데서 로드하는가」 | 선택지 3개 이상과 각각의 노출 표면을 **줄 수로** 비교 · 결정 후 코드 |
| C-3 | **F-4 증거 README 인용 규율.** 값을 적을 때 `아티팩트:필드` 를 함께 적게 하는 규칙 + 가능하면 검사기 | 규칙이 **기존 증거 문서에 소급 적용 가능**한지 1건으로 시연 · #676→#729 재발 부류가 닫힘 |

**F-3(별도 KIS 앱 등록)은 운영자 계정 작업이라 코드 레인이 없다.** C-2 의 결정이 F-3 을 필요로 하는지
판정하고, 필요하면 그 근거를 문서로 남긴다.

---

## 5. 종료 조건 · 뮤테이션

**게이트**: 커널·런타임 스위트 · **`tests/tools/test_tos_*.py`**(커널 #4 에서 빠졌던 배터리 — 이번엔
명시한다) · `ruff`/`black`/`mypy` · `tos_firewall_check.py` + `lint-imports` · `tos_size_budget.py --check`
(신규 예외 0) · `tos_completion_status.py --check` GREEN · `tos_spec_status.py --check` PASS ·
`tos_contract_check.py` + `--self-test` · **계약 문서 무접촉**.

**커널 diff 0** — 이 계획은 설정·런타임·문서만 건드린다. 커널 변경이 필요해지면 **멈추고 보고**한다
(다음 커널 라운드 감이지 이 계획의 범위가 아니다).

| # | 뮤테이션 | 기대 |
|---|---|---|
| M1 | A-4 의 `price_field_key` 를 `critical_input_policy` 와 어긋나게 | 일치 핀 red |
| M2 | A-2 의 scope 를 빈 목록으로 | 부팅 거부(또는 정책 미적용이 드러남) |
| M3 | B-1 의 `committed_vector` 를 `payload_json` 에서 다시 제거 | 재폴드 테스트 red |
| M4 | B-1 에서 pre-K-4 엔트리를 「빈 벡터」로 읽도록 | 「없음 vs 빈 벡터」 구분 핀 red |
| M5 | C-1 의 `broker_execution_id` 조인을 제거 | 재무장 테스트 red |
| M6 | C-1 의 조인 실패 시 **통과**시키도록 | fail-closed 핀 red |
| M7 | A-3 의 digest 를 한 바이트 바꿈 | `tos_contract_check.py` 또는 부팅이 거부 |

**리뷰어는 최소 1건을 직접 실행한다.** 커널 라운드 #4 에서 저자의 「전건 red」보고가 틀렸고
(M7 실제 red 0), 검토 측 측정도 두 번 틀렸다 — **완료 보고는 증거가 아니다**(§7.5).

**워크트리 소유권**: 한 워크트리는 한 레인만. 행동 전에 에이전트 상태를 확인한다. idle 알림은
종료가 아니다.

---

## 6. 운영자 확인

1. **Codex 부착 여부**(§7.4 ⑤ 이월). B-1 은 **재폴드·변조탐지 경로**라 2026-09-11 지시가 Codex 범위로
   열어둔 「되돌리기 어려운 경로」에 해당할 수 있다. **유료 외부 호출이므로 범위·비용 승인 후에만**
   디스패치한다 — 기본값은 미부착이며, 이 계획은 미부착을 전제로 쓰였다.
2. **안전 계열 값**(A-1 의 `⚠` 표). 「설정값 승인」을 받았으나 Hard Safety Envelope·리스크 한도·릴리스
   게이트는 틀리면 비싸다. 제안표가 나오면 그 표만 한 번 봐주시길 — 숫자는 이쪽이 채운다.
3. **F-3 별도 KIS 앱 등록** 의사. C-2 의 결정이 이걸 요구하면 외부 등록이 필요하다.
4. **A-5 의 부팅 대상.** 로컬 헤르메틱 데이터 디렉터리까지인지, 모의 서버 핸드오버까지인지.
   이 계획은 **로컬까지**를 전제로 쓰였다(실 서버 실행은 §1 제외).

## 7. 착지 기록

**웨이브 완료 (2026-09-18).** 이 계획이 지시한 3레인 전부 착지했고, 그 과정에서 **게이트 구멍
두 개**가 드러나 별도 PR 로 닫혔다. 계획 문언은 위에 그대로 두고 여기에 덧붙인다.

### 7.1 착지한 것

| 레인 | PR | main | 무엇 |
|---|---|---|---|
| W-A A-0 | #735 | `52db671b` | 9개 로더에서 named-TBD 우회 **부류** 차단 |
| A-0b | #737 | `690c2c59` | 배포 example 이 두 번째 로더를 만족하지 않는 **부류** 차단 |
| B-2 | #738 | `33009f25` | §7.4 ④ RCL v1→v2 운영 런북 |
| (계획 자신) | #734 | `dbbef841` | 이 문서 + 값 제안표 |

웨이브에서 파생된 것:

| 건 | PR | main | 무엇 |
|---|---|---|---|
| 런북 색인 드리프트 | #740 | `a2c943cb` | `docs/runbooks/` 32개 중 12개만 등재돼 있었다 |
| 게이트 구멍 ① | #742 | `749185f7` | mypy 가 두 테스트 트리를 안 보고 있었다 |
| 게이트 구멍 ② | #743 | `104fce1a` | Black 도 같은 모양의 구멍을 갖고 있었다 |
| 래칫 계획 | #744 | `6846e293` | 남은 mypy 유예 10종의 해소 순서 |

### 7.2 A-0b 가 재심 4라운드를 돌았다 — 지적이 매번 조치 안에서 나왔다

| 라운드 | 판정 | 무엇이 나왔나 |
|---|---|---|
| 1차 | HIGH 1 | 레지스트리 주석이 **없는 커버리지를 있다고** 주장 |
| 재심 | HIGH 2 | 메타 테스트가 장부만 봄 · 빈 dict 사각지대 |
| 3차 | MEDIUM 1 · LOW 1 | no-op 콜러블 우회 · 중첩 빈 리스트 |
| 최종 | 지적 0 | — |

매번 **인스턴스가 아니라 부류를 닫는** 쪽으로 갔고, 그 과정에서 아무도 요구하지 않은 **두 번째
결손**(`evidence_retention` 무커버리지)과 **잘못된 옛 제외 사유**(`strategy_bindings` — 「파일이
선택적」과 「로더가 안 거부한다」는 다른 얘기였다)가 드러났다.

**마지막 둘은 고치지 않고 코드에 등재했다.** 완전 차단이 리뷰 규약 §5 가 금지한 새 검증 하네스를
요구하기 때문이다. 현재 악용 불가인 **전제까지** 적었다 — 전제가 바뀌는 순간을 알아채야 한다.

### 7.3 게이트 구멍 — 하나를 고친 뒤 같은 눈으로 전수를 훑은 것이 하나를 더 찾았다

A-0b 에서 테스트 **헬퍼**의 타입 결함이 **재심 3라운드와 CI 3회를 전부 통과**했다. 원인은
`tos-firewall` 의 mypy 가 `src` 만 보고 두 테스트 트리를 보지 않은 것이었다(#742 가 닫음).

그 뒤 같은 잡을 전수로 훑자 **Black 이 같은 모양의 구멍**을 갖고 있었다 — `tos/src tos/tests` 와
도구 하나만 검사하고 있었다(#743 이 닫음). 새로 덮이는 421 파일이 **이미 전부 클린**이었다: 구멍이
오래 열려 있었는데도 아무도 그 안에서 더럽히지 않았다. 반면 mypy 쪽에는 ~1.9천 건이 쌓여 있었다.

**두 구멍 다 파일 목록이나 카운트 래칫으로 닫지 않았다** — 전자는 이 웨이브에서만 세 번 당한
「레지스트리 + 고정 안 된 위성」의 재생산이고, 후자는 규약 §5 가 금지한 fingerprint 다. **에러 코드
단위 유예**를 택했다(#744 가 남은 순서를 정한다).

### 7.4 검토 측이 세 번 틀렸다

| 누가 | 무엇을 보고했나 | 실제 |
|---|---|---|
| 3차 재심(A-0b) | 「모든 뮤테이션 원복, clean」 | **원복 안 됨.** `backtest_calibration` 의 **실제 검사가 삭제된 상태**로 남아 있었다. 푸시된 커밋은 깨끗해 판정은 무효가 아니지만, 확인하지 않았다면 다음 커밋에 실려 실제 커버리지 회귀가 됐을 것이다 |
| 저자(A-0b) | 매 라운드 「mypy 클린」 | **범위가 CI 와 같은 src 뿐**이었다. 팀리드가 그것을 전체로 읽었고, 그래서 테스트 트리의 결함이 3라운드를 통과했다 |
| fact-check(#744) | 283 의 하위 분해 대체안(직접 일치 + 캐스케이드 + 무관) | **합이 안 맞았다.** 팀리드가 `comm` 으로 다시 재 **53 + 230** 으로 정정. ※ 이 수치는 리뷰어가 **팀리드에게 낸 보고**에만 있고 **PR 코멘트에는 없다** — 저장소·GitHub 기록으로는 대조 불가 |

**세 번째 행을 오해하지 말 것** — 283 을 「228 직접 + 2 캐스케이드」로 처음 틀리게 쪼갠 것은
**저자다**(재지 않고 다른 리뷰의 표본을 옮겨 적었다. §7.5 의 「표본을 성격으로 승격」 두 번째
항목이 그것이다). fact-check 는 그 오류를 HIGH 로 **정확히 잡아냈고**, 다만 자신이 내놓은
대체 수치에 내부 불일치가 있었다. 저자 오류를 검토 측 칸으로 옮기는 것이 아니다.

커널 라운드 #4 의 「저자만 의심하는 규약이 아니라 전원이 같은 검증을 받는 규약이어야 한다」가
이번에도 그대로 적용됐다. **매 라운드 워크트리 청결을 팀리드가 직접 재확인하는 것**이 이 웨이브에서
추가된 습관이다.

### 7.5 팀리드가 일곱 번 틀렸고, 뿌리는 하나다

| 부류 | 횟수 | 사례 |
|---|---|---|
| **부분을 전체로 읽음** | 5 | `grep \| head` 절단 3회 — 그중 하나가 **#740 의 HIGH**(「`STOCK_MARKET_DATA_SOURCE` 는 테스트에만 남았다」가 거짓이었고 프로덕션 호출부가 31건 중 **마지막 줄**이었다. PR 코멘트로 대조 가능) · `gh` 의 「볼 것 없음」과 「다 통과」가 둘 다 exit 0 인 것에 2회(**세션 내 사건 · PR 기록 없음**) |
| **표본을 성격으로 승격** | 2 | `arg-type` 833 을 「테스트 더블이 Protocol 미충족」으로 규정(실제 **9%**) · 재지 않은 하위 분해를 다른 리뷰에서 옮겨 적음 |

둘 다 **본 것보다 넓게 말한 것**이다. 다섯 중 둘, 둘 중 둘을 남이 잡았다.

**이 표 자체가 같은 함정을 안고 있다** — 위 7건 중 PR 코멘트로 대조 가능한 것은 일부이고,
나머지는 세션 안에서만 일어났다. 표시해 둔 것이 그 구분이다. **세션 안에만 있는 사건은 남에게는
없는 사건**이므로, 이 기록을 근거로 쓸 사람은 그 구분을 보고 써야 한다.

거기서 나온 규칙을 #744 문서 §1.2 에 남겼다: **합계를 비교하지 말고 집합을 빼라**(리뷰어가 `git
ls-files` 로 두 파일 집합을 빼서 421 대 423 을 잡았다) · **판정 근거가 되는 명령에서 절단하거나
stderr 를 가리지 마라**(zsh 변수 단어분할 실패가 `2>/dev/null` 에 가려져 「비용 0」으로 읽혔다).

### 7.6 §6 운영자 확인 처분 (2026-09-18)

이 계획 §6 의 4항은 웨이브 진행 중 다음과 같이 처분됐다.

1. **Codex 부착** — 미부착. 이 웨이브의 모든 심사는 Claude 측 레인(`code-reviewer` sonnet, 저자와
   다른 패스)이 했고, 되돌리기 어려운 경로에 해당하는 변경이 없었다.
2. **안전 계열 값** — 값 제안표(#734)는 **운영자 채택 대기**로 남아 있다. 이 웨이브는 값을 채우지
   않았다.
3. **F-3 별도 KIS 앱 등록** — 이 웨이브 범위 밖. 미착수.
4. **A-5 부팅 대상** — 이 웨이브 범위 밖. 미착수.

**2026-09-23 운영자 처분** (위 2·3·4 의 대기 상태를 닫는다 — 위 문장은 09-18 시점 서술로 남긴다):

- **② 값 제안표 — 제안값 그대로 채택.** `⚠` 4행 포함(`active_scope = SYNTHETIC_FUTURES_ORDER` ·
  `nonlive_broker_consuming.admitted = false` · `admission_result = ADMIT` + `restriction_present: false` ·
  `risk_attestations` 6개 `true`). 기각된 대안: `risk_attestations` 를 `false` 로 두는 더 좁은 태세.
- **③ F-3 — C-2 결정 후 판단.** C-2(F-2 토큰 소유권 결정 문서)가 아직 없다. 세션 모델이 C-2 를 먼저 쓰고,
  그 결정이 자격증명 분리를 요구할 때만 운영자가 별도 앱을 등록한다.
- **④ A-5 — 로컬 헤르메틱 데이터 디렉터리까지.** 이 계획의 전제 그대로. 모의 서버 핸드오버는 스코프 전환과
  `admitted = true` 별도 승인, C-2 가 선행이라 별도 계획으로 남긴다.

### 7.7 남은 것

- **mypy 래칫 1~3단계** — #744 문서가 순서를 정했다. 1단계(113건 + 죽은 억제 53건) 착수 중.
- ~~**값 제안표 채택** — §6 ② 운영자 결정 대기.~~ → **2026-09-23 채택 확정**(§7.6 「2026-09-23 운영자 처분」). 실파일 기입(A-2~A-5)은 별도 PR.
- **`docs/plans/` 미등재 29건** — INDEX 가 `## Active` 기반 큐레이션이라 곧 드리프트는 아니나,
  각 건의 활성/아카이브 판단은 하지 않았다.

### 7.8 W-A A-2~A-5 착지 (2026-09-23)

운영자 결정 2026-09-23: **(1) 제안표를 제안된 그대로 채택**한다(⚠ 행 4건 포함 —
`broker_scopes::active_scope = SYNTHETIC_FUTURES_ORDER` · `coordinator_preconditions::
nonlive_broker_consuming.admitted = false` · `release::admission_result = ADMIT` +
`restriction_present: false` · `risk_attestations` 6개 `attested: true`).
**(2) A-5 부팅 대상은 로컬 헤르메틱 데이터 디렉터리까지**(§6 4항 처분 — 모의 서버·외부 호출 없음).

#### A-2 — 18종 채택

`config/tos_runtime/paper/` 에 18개 파일 신설. 파일마다 (a) 승인 출처
(「operator 2026-09-18 설정값 승인 · 2026-09-23 제안표 채택 확정 · 제안표 §n」)와 (b) **제안표 §0
문장**(「이것은 첫 부팅 프로파일이지 운영 안전 태세가 아니다」)을 주석으로 박았다. 제안표 §0 이
「채택되는 각 파일에 이 문장을 주석으로 박는다」고 구속한 그대로다.

| 파일 | 제안표 절 |
|---|---|
| `time.yaml` | §2.1 [A] 9값 · §4.2 [O] 2값 · §4.3 |
| `authority.yaml` | §4.2 · §3(4행) · §4.3 |
| `release.yaml` | §4.1 ⚠ · §3(1행) [D] |
| `currentness.yaml` | §2.3 [A] · §6 6항(미확정) |
| `currentness_dimensions.yaml` | §4.3 |
| `risk_attestations.yaml` | §4.1 ⚠ |
| `egress_coordinates.yaml` | §0(범위) · §4.3 |
| `broker_scopes.yaml` | §4.1 ⚠ |
| `engine.yaml` | §2.2 [A] · §4.2 [O] |
| `engine_driver.yaml` | §4.2 ⚠ |
| `coordinator_preconditions.yaml` | §1 [S] ⚠ · §4.1 ⚠ |
| `finality.yaml` | §4.2 · §6 1·2항(미확정) |
| `safety_envelope.yaml` · `safety_profile.yaml` · `safety_activation.yaml` | §4.3 · §3(2·3행) |
| `safety_deviations.yaml` · `safety_incidents.yaml` | §4.3 |
| `monitor_coverage.yaml` | §4.3 · §6 5항(미확정) |

**제안표 §6 의 미확정 리프는 1차에서 채우지 않았다.** `currentness::required_dimensions` ·
`finality::value_date`/`source_revision`/`proof_recipe_id` · `monitor_coverage::bounds` 3값 —
전부 named-TBD `null` 로 두었고 그 로더들이 거부했다. 제안표 §6 말미가 「부팅이 이것들 때문에
막히면 그것이 A-5 의 결과물이다」라고 미리 적은 그대로다.
> **2차 갱신(아래 §7.8.2)**: 운영자 답변 2·3 으로 `currentness::required_dimensions` 와
> `monitor_coverage::bounds` 3값은 **채워졌다**(추천 출처 = 2026-09-12 값 제안표). `finality` 3값은
> 그대로 `null` 이다.

`finality::proof_recipe_id` 는 A-2 에서 **재측정**했다: ADR-002-030 §29 는 절 제목 자체가
"Open Implementation Questions" 이고 Q3 은 「Which finality recipes distinguish …?」라는 **열린
질문**이다. 승인된 식별자를 **하나도 명명하지 않는다.** 즉 찾지 못한 게 아니라 **아직 존재하지 않는다.**

#### A-3 — [D] 도출

**`print-digests` (성공).** 인자 없음. `release.yaml` 두 digest 에 전사.

```
$ PYTHONPATH=tos/src:tos/runtime/src .venv/bin/python \
    -c 'import sys;from tos_runtime.compose.cli import main;sys.exit(main(sys.argv[1:]))' print-digests
expected_code_digest: 0876c3e091df07119bdf0a80ae7e6b68ca337150225fe4292cf5dfc383e81260
expected_dependency_set_digest: 20559763a1132fc75f71f3d83e99512f4b0d9cdde9e0df61b54b9d2459f98d8b
python_version: 3.12.12
sqlite_version: 3.45.1
```

**`print-policy-digests --config-dir config/tos_runtime/paper` (거부).**

```
$ ... print-policy-digests --config-dir config/tos_runtime/paper
print-policy-digests: refused — config/tos_runtime/paper/venue_constraint_policy.yaml:
scope.accounts is still 'TBD'/empty (named-TBD) — fill the deployment coordinate before activation
(exit 1)
```

원인은 이 웨이브가 채택한 파일이 아니라 **2026-09-16 에 이미 채택된 4종의 운영자-기입 잔여 TBD** 다.
그 파일들 자신의 헤더가 「`scope.accounts` — the paper account number (**never committed here**)」라고
적고 있고, 제안표의 대상 범위는 「`paper/` 에 **아직 없는** 19종 + `construction.yaml`」이라 이
값들의 행이 **없다.** 따라서 `safety_activation.yaml::members` 도 도출할 수 없어 `null` 로 남겼다 —
`[]` 로 바꾸면 「아무것도 활성화되지 않았다」는 **다른 사실**을 주장하게 된다(example 주석의 금지 사항).

**§3 3행(「도출 절차 미확인」) 확정.** `envelope_digest`/`profile_digest`/`bundle_digest` 를
계산하는 서브커맨드는 **없다** — `print-policy-digests` 는 governed **policy** 문서 5종의
`policy_id`/`policy_generation`/`canonical_digest` 만 출력한다(`compose/cli.py:671`
`_dispatch_print_policy_digests` + `_cli_ops.py:91-145`). 커널 `ActivationRecord` 는 세 필드를
모두 `X | None` 로 선언하므로 **`null` 이 로드된다**(실측). 즉 이것은 「거부가 빠진 것」이 아니라
**「도출이 없는 것」**이다.

#### A-4 — `construction.yaml`: **채택하지 않았다**

제안표는 §0 에서 이 파일을 대상에 포함하지만 **7개 리프 어느 것에도 값을 주지 않는다**(§5.4 는
`price_field_key` 상관만 논한다). 그리고 `account`/`instrument` 는 venue/OCP 정책의
`scope.accounts`/`scope.instruments` 와 같아야 하는데, 그 값이 바로 위 A-3 을 막은
**「never committed here」 운영자 좌표**다. 지어내면 **조작된 계좌 좌표를 커밋된 배포 파일에 넣는
것**이 되므로 짓지 않았다.

제안표 §5.4 의 **두 갈래를 모두** 테스트로 고정했다
(`tos/runtime/tests/compose/test_deploy_approved_values.py::
test_construction_price_field_keys_match_the_deployed_critical_input_policy`):
둘 다 배포되면 `price_field_key`/`shape_price_field_key` 가 배포된 `critical_input_policy.yaml` 의
`fields[].field_key` 안에 있어야 하고, 둘 다 없으면 그것이 두 번째 갈래다 — **한쪽만 있는 상태는
즉시 red**. `skip` 이 아니라 assert 로 썼다(skip 은 정작 필요할 때 죽은 핀이 된다).

#### A-5 — 부팅 (로컬 헤르메틱)

```
$ rm -rf <scratchpad>/wa-boot && mkdir -p <scratchpad>/wa-boot/{data,custody}
$ PYTHONPATH=tos/src:tos/runtime/src .venv/bin/python \
    -c 'import sys;from tos_runtime.compose.cli import main;sys.exit(main(sys.argv[1:]))' \
    run --config-dir config/tos_runtime/paper \
        --data-dir <scratchpad>/wa-boot/data \
        --custody-root <scratchpad>/wa-boot/custody \
        --environment-label non-live-test
run: refused — construction config file not found: config/tos_runtime/paper/construction.yaml
EXIT=1
```

**거부 지점**: `compose/_run_dispatch.py:94-99`(`dispatch_run` 1단계) · 로더
`tos_runtime.compose._construction_config.load_construction_config`
(`compose/_construction_config.py:167`, 부재 검사는 `:104-105`) · 키 = 파일 자체.

`run` 은 1단계에서 멈추므로 **그 뒤 어디까지 막히는지는 순차 부팅으로 알 수 없다.** 그래서
**로더 전수 프로브**를 따로 돌려 잔여 차단을 전부 이름으로 측정했다(1차: 25건 중 **15 PASS** ·
2차 갱신 후 **17 PASS**). 그 프로브는 review-794 MEDIUM-4 지적에 따라
`tos/runtime/tests/compose/_loader_probe.py` 로 **커밋**됐고(직접 실행 가능),
`test_deploy_approved_values.py::test_loader_probe_partition_is_as_recorded` 가 분할을
**이름으로** 고정한다 — 이 수치가 다시 재현 불가가 되지 않는다:

| 남은 차단 | 부류 | 값의 소관 |
|---|---|---|
| ~~`currentness.yaml::required_dimensions`~~ | §6 6항 | **2차에서 해소** — 운영자 「그대로 사용」 |
| `finality.yaml::value_date`(그리고 `source_revision`·`proof_recipe_id`) | §6 1·2항 | 상위 승인 부재 |
| ~~`monitor_coverage.yaml::bounds` 3값~~ | §6 5항 | **2차에서 해소** — 2026-09-12 §4 추천값 |
| `safety_activation.yaml::members` | §3 [D] | **A-3 이 막혀 도출 불가** |
| `venue_constraint_policy::scope.accounts` · `order_construction_policy::scope.accounts` · `aggregate_risk_policy::instrument_scope` · `action_flow_policy::account_scope` | 2026-09-16 채택분의 잔여 TBD | **운영자 좌표**(제안표 범위 밖) |
| `construction.yaml` | 미채택 | 위 A-4 |
| `strategies/` | §6 7항 | 전략 DSL — 「부팅용으로 아무거나」 금지 |

**틱 원천 — §2 결정 3 의 그 거부에는 도달조차 하지 못했다.** `run` 이
`composed.marketfeed is None` 으로 거부하는 지점(`_run_dispatch.py:121-130`)은 1단계 뒤에 있다.
다만 **로컬 헤르메틱 틱 원천이 존재하는지**는 측정했다: **존재한다.**
`marketfeed.yaml::intake_kind: journal` 이 그것이고, 구현
(`tos_runtime/marketfeed/journal.py::JsonLinesObservationJournal`)은 `json`+`pathlib` 만 쓰며
**소켓을 열지 않고 시계도 읽지 않는다**(모듈 독스트링 + import 전수). 나머지 한 값 `kis_quote` 는
HTTP 폴러라 외부 호출이고, 이번 대상이 아니다. 즉 로컬 틱 원천을 켜는 데 필요한 것은
**`marketfeed.yaml` + `critical_input_policy.yaml` 채택 + 저널 파일** 뿐인데, 그 둘은 인벤토리
27/28 행(「compose 레벨 옵션 · `run` 레벨 사실상 필수」)이고 **제안표가 값을 주지 않는다**
(특히 `critical_input_policy::fields[].max_age_ms` 는 신선도 한도 — 안전 값이다). 그래서 채택하지
않았다.

**제안표 §5 주의 사항 확인**: `admitted_quantity_bases`(OCP)는 `["TBD"]` 그대로이고 전략 파일도
없으므로 **대조할 `quantity_basis` 자체가 없다.** 「부팅 성공 ≠ 주문 성공」은 이번에 검증할 수
있는 단계에 이르지 못했다 — 부팅부터 막혀 있다.

#### 7.8.1 테스트 · 게이트 (1차)

- 신규 `tos/runtime/tests/compose/test_deploy_approved_values.py` — 세 부류의 핀:
  ① 13개 로더가 **실제 배포 파일**을 로드 ② 승인값 1개를 `null` 로 되돌리는 **뮤테이션 13건이
  타입드 예외 + 키 이름까지** 요구(키 이름 매칭이 없으면 무관한 거부가 「가드가 작동했다」로 통과한다)
  ③ §6 미확정 리프는 **키 이름과 함께** 거부가 핀돼 있어 나중에 채우는 것이 반드시 의도적 행위가 된다.
  추가로 ⚠ 값 5건·교차 파일 정합 4건·§4.3 식별자/세대/빈목록 규칙을 고정.
- 기존 `test_deploy_config.py` 무회귀.
- 실행 뮤테이션 1건 직접 확인: `active_scope` → `MOCK_STOCK_ORDER` 로 바꾸니 핀 2건 **red**,
  원복 후 `diff` 로 청결 확인(§7.4 1행의 「원복 안 됨」 재발 방지).

#### 7.8.2 2차 (2026-09-23) — review-794 조치 + 운영자 답변 4건

PR #794 리뷰 판정 **HIGH 3 · MEDIUM 4 · LOW 3**(머지 불가)과 운영자 답변 4건을 같은 라운드에서
처분했다. 리뷰가 확인한 것(값 추적 전건 일치 · 안전 태세 결함 0 · 비밀/계좌번호 0 · digest 바이트
일치 · A-5 축자 재현 · 헤더 `file:line` 48/48 정확)은 **다시 받지 않았다.**

##### B1 — 좌표 주입 수단 서베이: **없다. 만들지 않았다.**

운영자 답변 1 은 「이 장비가 운영 장비. 여기 있는 `.env` 와 `.env.mock` 환경 파일을 그대로 활용」
이다. 즉 좌표(`construction.yaml::account`/`instrument` · 2026-09-16 채택분 4종의
`scope.accounts`/`scope.instruments`/`account_scope`/`instrument_scope`)는 **런타임에 이 호스트의
env 에서 와야 하고 커밋돼서는 안 된다.** 지시대로 **먼저 서베이**했다:

| 실측 | 결과 |
|---|---|
| `grep -rn "os.environ\|getenv" tos/runtime/src` | **프로덕션 사용 0건.** 히트 32건(`grep -rn … | wc -l`, 2026-09-23 재측정 — 초고의 「20건」은 재현되지 않았다)은 전부 독스트링·주석이 스스로 「no `os.environ`」이라고 적은 문장이고, `tokenize` 로 걸러 코드 토큰 0 을 리뷰가 확인했다 |
| `tools/tos_firewall_check.py` **TOS-FW-C** | `os.environ`/`os.getenv` 는 **AST 게이트가 금지**한다 — `from os import environ/getenv`(:515-526)와 속성 접근 `os.environ`(:539-551) 둘 다. 이 검사는 **스코프 무관**으로 `tos/` 전체에 걸린다(스코프 분기는 import 허용목록에만 적용 — `scope_for_tos_path`:360) |
| `grep -rn "expandvars\|\${" tos/runtime/src` · `dotenv`/`.env`/`env-file` | **0건.** 로더가 수행하는 유일한 치환은 `{environment_label}` 하나다(`broker_scopes` principal · `egress_coordinates.active_principal`) — 그것도 **CLI 인자**에서 온다 |
| `compose/root.py:180` | 「environment_label: Boot-argument environment label (**never `os.environ`** — D1.1)」 |
| 커스터디(호스트 로컬 · 비커밋) | `FileCustody` 는 `custody_root` + 매니페스트 + scope 파일로 **자격증명**을 읽는다. 그러나 **계좌번호는 의도적으로 커스터디 대상이 아니다**(review F2): `transport/kis_mock/adapter.py:37-41`·`codec.py:43-46`·`custody.manifest.example.yaml` 이 셋 다 「KIS account number is NOT a custody credential … it is the sealed outbound `account` coordinate」라고 적고, `PROVISIONED_SCOPES` 에 `kis_mock.account` 가 **없다** |

이 서베이 직후 main 에 착지한 **C-2 자격증명 소유권 결정**
(`docs/plans/2026-09-23-tos-kis-credential-ownership-decision-c2.md`, PR #792, 선택지 (C) 채택)이
같은 경계를 독립적으로 확인한다 — 그 문서가 다루는 custody 대상은 **앱키/시크릿**이고, 계좌
좌표는 여전히 그 모델 밖이다(`PROVISIONED_SCOPES` 에 계좌 scope 없음). 즉 B1 의 빈칸은 C-2 가
메우는 빈칸이 아니다.

**결론: 기존 수단이 없다.** 지시대로 **만들지 않고 멈췄다.** 설계 선택지는 아래와 같고, 설계는
세션 모델이 쓴다.

| 선택지 | 건드리는 파일 | 방화벽 함의 |
|---|---|---|
| **(가) 호스트 로컬 config-dir** — `--config-dir` 는 이미 CLI 인자다. 운영자가 좌표 포함 사본을 저장소 밖(예: `/etc/tos/paper/`)에 두고 그것을 가리킨다 | **코드 0줄.** 문서/런북만 | 없음 |
| | | ⚠ 대가: 부분 오버레이 수단이 없어 **파일 전체를 복제**해야 하고, 커밋된 핀이 실제 부팅하는 파일을 더 이상 기술하지 않는다 |
| **(나) 좌표 오버레이 파일** — `--config-dir` 안의 gitignore 된 한 파일(예: `deployment_coordinates.yaml`)에서 좌표만 읽어 해당 로더들에 주입 | `compose/_construction_config.py` · `venue/_venue_policy_loader.py` · `_order_construction_policy_loader.py` · `riskstate/_*_policy_loader.py` · `.gitignore` · example 신설 | **없음**(파일 읽기) — TOS-FW-C 와 무관 |
| | | ⚠ 대가: 「정책 문서의 scope 는 그 문서 안에 있다」는 현 모델이 깨진다. digest 대상 범위(`canonical_digest`/`members`)와의 관계를 먼저 정해야 한다 |
| **(다) 커스터디 스코프 확장** — `account` 를 `FileCustody` scope 로 승격(`custody_root` 는 이미 호스트 로컬·비커밋) | `custody/file_custody.py`(`PROVISIONED_SCOPES`) · 로더들 · 매니페스트 example · 런북 | **없음**(파일 읽기) |
| | | ⚠ 대가: **review F2 결정을 뒤집는다**(「계좌번호는 자격증명이 아니라 봉인된 outbound 좌표」). 그 결정을 바꾸는 것은 설계 PR 이지 구현이 아니다 |

**(라) `os.environ` 직접 읽기는 선택지가 아니다** — TOS-FW-C 가 AST 로 거부한다. `.env` 를
읽으려면 그 규칙 자체를 개정해야 하고, 그것은 경계 설계 변경이다.

**이 라운드에서 실 계좌번호는 커밋 파일·테스트·커밋 메시지 어디에도 쓰지 않았다.**
`.env.mock` 에 `KIS_FUTURES_ACCOUNT_NO` 키가 **존재한다는 사실만** 확인했다(키 이름만 grep,
값 미출력).

##### B2 · B3 — 채운 것과 채우지 않은 것

제안표 §7.2 표 참조. 요약: **채움 2건**(`currentness::required_dimensions` = 커널 floor 21키 ·
`monitor_coverage::bounds` = 60000/`["TRUSTED"]`/100, 둘 다 출처
`docs/plans/2026-09-12-tos-operator-value-proposals.md` §2·§4, 등급 C) · **추천값 없음 3건**
(`finality::proof_recipe_id`·`source_revision` 은 등급 M, `value_date` 는 추천값이 **있으나**
근거가 KRX **주식** 결제일이라 `SYNTHETIC_FUTURES_ORDER` 스코프와 어긋나 적용하지 않았다) ·
**미채택 2건**(`strategies/` · `marketfeed`+`critical_input_policy` — 양 표 모두 행이 없고,
좌표는 B1 에 걸린다).

> **제안표 §6 5항의 「상위 원천 미확인」은 이 재조사로 반증됐다** — 2026-09-12 값 제안표 §4 가
> 그 세 값을 정확히 제안하고 있었다. 「없다」고 적기 전에 더 이른 표를 찾지 않은 것이 1차의 누락이다.

##### A-3 · A-5 재실행 — 결과 불변

```
$ ... print-policy-digests --config-dir config/tos_runtime/paper
print-policy-digests: refused — config/tos_runtime/paper/venue_constraint_policy.yaml:
scope.accounts is still 'TBD'/empty (named-TBD) — fill the deployment coordinate before activation
(exit 1)

$ ... run --config-dir config/tos_runtime/paper --data-dir <fresh> --custody-root <fresh> \
      --environment-label non-live-test
run: refused — construction config file not found: config/tos_runtime/paper/construction.yaml
EXIT=1
```

둘 다 **B1 이 막은 그 좌표** 때문이다. 2차가 채운 값들은 거부 지점을 앞당기지도 미루지도 않았다 —
프로브 분할만 **15→17 PASS** 로 움직였고, 남은 8건은 전부 위 표의 이름 있는 차단이다.

##### 핀 강화 — 부류로 닫았다

review-794 HIGH-1/HIGH-2 는 「⚠ 값과 [A] 전사 bound 가 **값으로** 안 박혀 있다」였다. 리뷰어가
스크래치 사본에서 17종을 다른 값으로 바꿔도 스위트가 **전건 GREEN** 임을 실측했다 — 프로젝트
메모리의 「가드가 자기가 막는다고 말한 것을 허용한다」와 같은 모양이고 실패 모드가 침묵이다.

인스턴스(10건 추가)가 아니라 **부류**로 닫았다:

- 18종 **156 리프 전수**가 `_VALUE_PINS`(149) 또는 **사유가 붙은** `_UNPINNED_BY_DESIGN`(7 —
  `broker_scopes` 본문, byte-identity 핀이 값 핀보다 강하게 덮는다) 중 하나에 속해야 한다.
  둘 다 아니면 `test_every_adopted_leaf_is_pinned_or_explicitly_unpinned` 가 실패한다.
- 역방향 드리프트(없어진 리프를 가리키는 핀)도 실패한다.
- **게이트 자신이 죽은 검사가 아님**을 시험한다(스크래치 사본에 리프를 하나 더해 게이트가
  그것을 이름으로 보고하는지).
- `test_a_value_pin_actually_fires` 가 **실제 값 11종**을 「구조적으로 유효하지만 승인되지 않은」
  값으로 바꿔 핀이 살아 있음을 증명한다 — HIGH-1 의 `replay_window_events` `1000000`→`1`
  (여전히 양의 정수라 로더는 통과) 포함.
- 뮤테이션은 **텍스트 치환**으로 바꿨다. `yaml.safe_dump` 왕복은 헤더 주석을 날려 **출처 시험이
  먼저 터지는** 공허한 RED 를 만든다(review-794 방법론 주의).

#### 7.8.3 3차 (2026-09-23) — 좌표 렌더 + 첫 부팅 시도 (A-5 본체)

설계 `docs/plans/2026-09-23-tos-paper-coordinates-and-first-boot-design.md`(운영자 결정 1·3 ·
운영자 선택 (가))의 구현. 브랜치 `feat/tos-paper-render-and-first-boot`, main `b5bb5eb5` 기준.
런북 `docs/runbooks/tos-paper-boot.md`.

##### 착지물

| 항목 | 결과 |
|---|---|
| 렌더 스크립트 | `scripts/tos/render_paper_config.py` — 커밋된 `config/tos_runtime/paper` 를 저장소 밖으로 **바이트 복사**한 뒤 좌표 칸만 치환. tos 코드·방화벽 변경 **0**. `scripts/` 는 `tos`/`tos_runtime` 을 import 할 수 없으므로(TOS-FW-R) `print-policy-digests` 와 활성화 재확인은 **서브프로세스** |
| 단위 테스트 | `tests/unit/scripts/test_render_paper_config.py` — 28건. §2 가드 표 **전 행**에 실패하는 입력 테스트. 임시 `git clone` 안에서 실제 CLI 를 돌려 `git status --porcelain --ignored` 불변 단정(`PYTHONDONTWRITEBYTECODE=1` + `python -B`) 포함 |
| 부팅 증명 픽스처 | `construction.yaml` · `strategies/bootproof_band.strategy.yaml` · `marketfeed.yaml` · `critical_input_policy.yaml`. 파일마다 픽스처 헤더 문장. 값마다 file:line |
| 커밋 값 | `finality::value_date="T+1"` · `proof_recipe_id`(픽스처 토큰) · OCP `admitted_quantity_bases=["RISK"]` · `axes[DIRECTION]="LONG"` |
| 핀 갱신 | `_VALUE_PINS`(finality 2값) · 거부 핀(거부 키가 `value_date`→`source_revision` 으로 이동) · `_loader_probe` 프로브 2종 추가 → **18 PASS / 27**(이전 17/25) · 픽스처 4종 전 리프 핀 + 미렌더 좌표 칸을 **각자 로더의 거부로** 핀 |

##### 계좌 형식 — 실측 결론

**어떤 tos 로더도 계좌 형식을 검사하지 않는다.** 전부 「비어 있지 않고 `"TBD"` 가 아닌 문자열」
만 요구한다(`venue/_policy_primitives.py::require_singleton_list_str` ·
`riskstate/_action_flow_policy_loader.py:471-490` · `_aggregate_risk_policy_loader` ·
`compose/_construction_config.py::_require_str`). 강제되는 것은 **파일 간 동일성**뿐이다
(`compose/_venue_wiring.py:139-142` · `compose/_riskstate_wiring.py:86-89`).
따라서 하이픈 문제는 렌더가 **한 번** 정하고 모든 칸에 같은 문자열을 넣는다 —
**숫자만, 10자리 전부**(`shared/kis/client.py::_normalize_account` 「digits-only 10-char format」 ·
`tools/broker_probes/common.py` 의 `cano=[:8]`/`acnt_prdt_cd=[8:10]` 와 같은 형태). 뒤 두 자리는
상품코드라 그것을 버리면 「선물 계좌」라는 식별이 사라진다.
⚠ 미결로 남긴 지점: (아직 운영자 미승인인) KIS mock transport 제안표는 이 좌표를 **CANO 한 필드**
에 매핑하고 `ACNT_PRDT_CD` 를 별도 상수로 둔다(`docs/runbooks/tos-kis-mock-transport.md:97,101`).
그 매핑이 그대로 채택되면 좌표는 8자리 CANO 가 된다. SYNTHETIC 스코프에서는 브로커에 도달하지
않으므로 재렌더로 되돌릴 수 있다 — 조용히 선점하지 않고 명시해 둔다.

##### A-5 결과 — **부팅 미완 · 남은 거부 3건을 이름으로 지목**

1. ⛔ **`VenueConstraintPolicy.canonical_digest` 가 프로세스마다 다르다.**
   `_COVERED_FIELDS`(`tos/src/tos/venue/records.py:406-416`) 안의 frozenset 필드
   (`required_constraint_classes` `:424`, `shape_constraints` 의 `allowed_*` `:165-168`)가
   `covered_content()`(`tos/src/tos/canonical/_base.py:187`)의 `model_dump(mode="json")` 에서
   **집합 순회 순서 그대로의 리스트**가 되고, `_encode`(`canonicalization.py:148-149,174-176`)는
   시퀀스를 **순서 유의미**로 취급한다. `ConstraintClass` 는 `StrEnum`(`vocabulary.py:169`).
   → **§2 6항이 규정한 「`print-policy-digests` 출력을 `members` 에 전사한다」는 절차가 이
   한 종류에서 성립하지 않는다.** 나머지 4종(OCP/ARE/AFG/CIP)은 covered 필드에 집합이 없어 안정.
   기존 테스트가 전부 **한 프로세스 안에서** 계산·검증해 드러나지 않았다
   (`test_deploy_policies.py::_install_real_policies` 주석: "done **in-process**").
   렌더의 종료 검사를 **새 프로세스에서 정책을 재로드해 재확인**하도록 쓴 덕분에 즉시 잡혔다.
   정본 직렬화 변경은 설계 PR 사안이라 **고치지 않고 지목**하고,
   `test_venue_policy_canonical_digest_is_not_reproducible_across_processes` 로 결정적으로 고정했다.
2. `venue_constraint_policy.yaml:55` `environments: ["paper"]` ≠ 설계 §2 부팅 명령의
   `--environment-label non-live-test` → `VenuePolicyScopeMismatch`. `paper` 는
   `cli.py:215` `_LIVE_ENVIRONMENT_LABELS` 소속이라 라벨 선택은 운영자 결정.
3. `safety_envelope.yaml::governed_dimensions: []` ≠ `aggregate_risk_policy.yaml:74` 요구
   → `RiskPolicyScopeMismatch`. 그 파일 헤더가 「별도 안전 승인 사안」이라 적는다 — 안전 한도라
   채우지 않았다.

##### 양방향 증거 (§3 (가))

세 거부를 **진단으로만** 통과시킨 상태(해시 시드 고정 · 라벨 `paper` · 스크래치 사본에만 봉투
차원 1건 추가; 커밋 파일 불변)에서 LONG·SHORT **두 구성 모두** 동일하게:

- `run` 이 거부 없이 부팅 → `run_forever` → SIGTERM → `run: stopped (signal received).` **exit 0**
- 틱은 `SKIPPED_SESSION_CLOSED`(`phase='EXPIRED'`) — 값이 아니라 **캘린더**다
  (`calendar.yaml:36-40`: 08:45–15:45 KST + 9월 만기 이후 클래스 전체 EXPIRED, 클래스 단위 규칙)
- 같은 산출물을 만기 이전 장중 시각으로 구동 → `TICKED`, `marketfeed.sqlite3`
  `snapshots: 1 / preimages: 1`, 값 뷰 = 렌더 저널의 세 필드 그대로

**실 계좌번호는 커밋 파일·테스트·커밋 메시지·PR 어디에도 쓰지 않았다**(로그는 지문만;
기계 검사로 diff/커밋메시지/작업트리 전수 확인).


#### 7.8.4 4차 (2026-09-24) — review-797 조치 + 운영자 결정 2건 + 2차 부팅

PR #797 리뷰 판정 **HIGH 2 · MEDIUM 3 · LOW 6**(머지 불가)을 전건 처분하고, 같은 라운드에
**운영자 결정 2건**을 반영했다. 리뷰가 코드로 확인해 준 것(가드 6종 뮤테이션 6/6 RED ·
등록된 21키만 치환 · 계좌 유출 0 · 결함 ① 재현 · 결함 ② 재현 및 「첫 틱 가능일 10-01」
정정 · 죽은 핀이 진짜로 살아났다는 확인 · 인용 file:line 전건 확인)은 **다시 받지 않았다.**

##### HIGH-1 — **1차가 「실측」이라고 네 번 단언한 문장이 거짓이었다**

주장: 「`marketfeed` 로더의 `_require_str` 는 `null`/빈 문자열만 거부하고 문자열 `"TBD"` 는
거부하지 않는다(실측)」. **거짓이다.** 실제로 파일을 로드하지 않고 에러 메시지 문자열만
훑고 결론 낸 것이다. 재측정:

```
instruments  null / "" / "TBD"  -> 전부 REFUSED
account      null / "" / "TBD"  -> 전부 REFUSED
journal_path null / "" / "TBD"  -> 전부 REFUSED
```

`_marketfeed_wiring._require_str` 는 타입 검사 뒤 `reject_named_tbd` 를 부르고(:200-202),
`_require_instruments` 도 항목마다 부른다(:228-232). 그 기계적 차단은 `d2a36d22`
(「close the named-TBD bypass class mechanically, not by list」, W-A A-0 round 2 ·
origin/main 의 조상)가 이미 넣었다.

왜 나쁜가: 런타임 위험은 없었지만(`null` 도 거부되므로 결과는 안전했다) 이 문장이
**이미 머지된 안전 수정의 상태를 잘못 적었다** — `config/tos_runtime/README.md` 라는 내구
문서에서. 그것을 읽은 사람은 「그 로더의 named-TBD 우회가 아직 열려 있다」고 결론 내리거나
다른 로더에 같은 구멍을 남겨도 된다고 오독할 수 있다. 이 저장소가 기록해 둔 반복 결함
(「가드가 자기가 막는다고 말한 것을 허용한다」)의 거울상이다.

조치: 네 곳 정정 + 그 거짓이 유일한 근거였던 「placeholder 형태가 로더마다 다르다」 분류를
폐기하고 **좌표 칸을 전 파일 `"TBD"` 로 통일**(렌더 규칙·핀 동반). 로더 프로브 분할은
**18 PASS / 27** 그대로(거부 사유 문구만 바뀐다).

##### HIGH-2 · MEDIUM-1 — 부팅 라벨: **운영자 결정 = `paper`**

1차는 `critical_input_policy.yaml::environment` 에 `non-live-test` 를 두고 주석에
「런북이 강제하는 라벨은 `non-live-test`」라고 적었는데, **같은 PR 의 런북이 `paper` 로
부팅하고 있었다.** 무해한 불일치가 아니다 — 그 토큰은 발행되는 모든 스냅샷·캡슐의 covered
content 로 들어가고(`marketfeed/snapshot.py:283`), 로더는 그것을 `--environment-label` 과
**대조하지 않으므로** 부팅은 조용히 성공하고 증거만 틀린 라벨을 단다.

운영자 결정에 따라 `paper` 로 통일했다. 그 라벨이 `cli.py:215` `_LIVE_ENVIRONMENT_LABELS`
소속이라는 것과 **구체적 귀결**(`restore-drill` 이 이 라벨로 실행을 거부한다 — `cli.py:816`)을
런북에 적었다. 실제 주문 도달 여부는 라벨이 아니라 `broker_scopes.yaml::active_scope`
(`SYNTHETIC_FUTURES_ORDER`)가 정한다는 것도 같이 적었다.

##### 운영자 승인 — HSE 지배 차원 `envelope_max = 1`(계약)

요구는 이미 문서에 있었다(`aggregate_risk_policy.yaml:74`), 값 1 은 그 정책의 이미 승인된
유효 한도(`:111`)이자 OCP 사이징 `max_quantity: 1` 이다. `safety_envelope.yaml` 에 차원을,
`safety_profile.yaml` 에 같은 차원의 `profile_value: "1"` 을 함께 기입했다 —
`profile_within_envelope` 가 (a) **빈 봉투를 무권한으로 거부**하고(`spg/predicates.py:274-277`)
(b) 봉투 선언 차원을 프로파일이 **누락하면 거부**하기(`:278-283`) 때문이다.
**부수 실측: 1차의 「둘 다 빈」 상태는 그 술어를 어느 쪽으로도 통과할 수 없었다** — 「봉투가
0개를 선언하므로 프로파일도 0개가 유일하게 정합」이라던 1차 주석은 틀렸다.
경계는 `INCLUSIVE` 여야 한다 — EXCLUSIVE 면 `value == max` 가 거부돼 1 계약이 통과하지 못한다.

##### MEDIUM-2 — 실패한 렌더가 계좌가 채워진 디렉터리를 남기던 문제

결함 ① 때문에 **이 호스트에서 런북을 따르는 모든 운영자가 1회차에 그 상태에 도달했다**:
좌표가 채워졌는데 `RENDERED.json` 이 없는 디렉터리가 남고, 재실행은 「not empty and carries
no RENDERED.json」으로 **영구 거부**된다. 렌더를 **원자적**으로 바꿨다 — 형제 스테이징에서
조립하고 성공 시에만 이동, 어떤 실패(`KeyboardInterrupt` 포함)든 스테이징 삭제.
실측(아래 2차 부팅 R0): 실패 후 출력 경로도 부모 디렉터리도 **비어 있다.**

##### MEDIUM-3 — 결함 ① 범위: 리뷰의 「부류다」는 맞고 **예시는 틀렸다**

`_COVERED_FIELDS` 보유 모델 **120** 전수 스캔(재측정):

| 수 | 무엇 |
|---|---|
| 19 | covered content 에 집합 보유(중첩 포함) |
| **6** | 그중 **이미 `covered_content()` 를 오버라이드해 정렬한다** — `cur`/`wdr`/`sir`/`rlp` 계열. `tos/src/tos/cur/records.py:44-49` 가 이유를 그대로 적는다(설계 #23 §3.1) |
| **13** | 정렬하지 않는다 = digest 프로세스 의존. 이 배포가 오늘 digest 를 계산하는 것은 그중 `VenueConstraintPolicy` 하나 |

리뷰가 든 **`CurrentnessPolicy.required_dimensions` 는 그 6에 속해 영향이 없다** — 배포된
`currentness.yaml` 로 만든 digest 가 해시 시드 6개에서 **동일**함을 실측했다. 타입 스캔만
보면 과대 보고된다. **수정 패턴이 커널에 이미 있다**는 것이 후속 설계 PR 에 가장 쓸모 있는
사실이라 그것까지 적었다. 부류 전체(120/19/6/13)를 **이름으로** 고정하는 테스트를 추가했다.

##### LOW 1~6

인용 오귀속 정정(「production-shaped default」는 `test_run_e2e.py:58`) · `records.py:425` ·
`account_fingerprint` 가 **무염·가역**(10^10 입력)이므로 마스킹이 아니라 상관자임을 명시하고
저장소 밖 0700 밖으로 나가지 않게 유지 · `parse_account_from_env_file` 이 인라인 주석을
처리(따옴표 안의 `#` 은 값의 일부) · 「`tests/unit/scripts/` 신설」 문구 정정 ·
**활성화 기록이 방향을 결속하지 않는다**는 한계 명시(LONG·SHORT 렌더의 5종 digest 가 바이트
동일 — `_runtime.construction.axes` 는 정본 covered content 밖이다).

> LOW-4 조치 중 **테스트가 내 수정의 버그를 잡았다**: 따옴표 값 뒤에 주석이 오면
> (`KIS_...='<값>'  # note`) 첫 판이 따옴표를 벗기지 못했다. 닫는 따옴표까지를 값으로
> 취하도록 고쳤다. 동반 테스트는 이 가드가 막는 실패가 **진짜 조용하다**는 것도 보인다 —
> 8자리 + `# 03` 은 정확히 10자리가 되어 **형식이 멀쩡한 다른 계좌**로 통과한다.

##### 2차 부팅 (2026-09-24, 실 `.env.mock` · 라벨 `paper` · 런북 그대로)

LONG·SHORT **양쪽 동일**:

| 단계 | 결과 |
|---|---|
| R0 렌더(시드 미고정, 런북 그대로) | **거부 — 결함 ①**. `PolicyNotActivated … members[0]: digest '<A>' != '<B>'` |
| R0 뒤 잔여물 | **없음** — 출력 경로 부재, 부모 디렉터리 비어 있음(MEDIUM-2 확인) |
| R1 렌더(진단: 해시 시드 고정) | 성공 · `ACTIVATED 5 (re-derived in a fresh process)` · 계좌 미출력(지문만) |
| `--check` | exit 0 (좌표 칸 외 차이 0) |
| **B 부팅**(런북 §3 그대로, **스크래치 패치 없이**) | **부팅 성공** → `--- sending SIGTERM … ---` → `run: stopped (signal received).` **EXIT=0** |
| 지속 저장소 | `evidence.sqlite3 entries: 17` · `rcl.sqlite3 entries: 1` · `marketfeed.sqlite3` 생성(`snapshots: 0`) |
| 틱 | `phase='EXPIRED' is_open=False` → `SKIPPED_SESSION_CLOSED` |

**1차와의 차이: ②③이 커밋 파일로 닫혀, 스크래치 사본을 손대지 않고 부팅한다.**
남은 것은 ①(렌더가 정상 거부)과 ④(캘린더 만기 공백 — 별도 PR 소관, 이 PR 은 캘린더를
건드리지 않았다).

**실 계좌번호는 이번 라운드에도 커밋 파일·테스트·커밋 메시지 어디에도 쓰지 않았다**
(기계 검사로 diff/커밋메시지/작업트리 전수 확인).


#### 7.8.5 5차 (2026-09-24) — review-797 2차 조치 (HIGH 1 · LOW 3)

2차 리뷰 판정 **HIGH 1 · LOW 3**. 1차 지적 11건은 전부 종결로 확인됐고, 그중 MEDIUM-3 의
예시(`CurrentnessPolicy`)는 **리뷰어가 자기 지적을 철회**했다(우리 재측정이 맞았다).

##### HIGH — 원자적 렌더의 보호 구간이 꼬리 3문장을 덮지 못했다

4차에서 도입한 `try` 가 **지문 계산 직전에 끝나 있었다.** 그 뒤의
`account_fingerprint` · `RENDERED.json` 쓰기 · `rmtree(out)` · `shutil.move` 는 보호 밖이고,
리뷰어가 첫 미보호 문장에 실패를 주입해 **계좌가 든 파일 7개짜리
`.paper-config.partial-<pid>`** 를 실제로 남겼다.

더 나쁜 것은 **관측성이 1차보다 후퇴했다**는 점이다: 이름이 `.` 으로 시작해 `ls` 에 안
보이고, 이름에 PID 가 박혀 있어 다음 실행이 **치우지도 알아채지도 못한 채 조용히
성공**한다. 1차에는 적어도 다음 렌더가 「비어 있지 않고 `RENDERED.json` 이 없다」로 큰
소리로 거부하며 경로를 알려줬다.

그리고 **세 곳이 그럴 수 없다고 단언하고 있었다** — 코드 주석(「Every failure path,
including KeyboardInterrupt」) · 런북(운영자가 읽는 문서) · 전칭 테스트 이름
(`..._leaves_no_output_directory_and_no_account_on_disk`, 주입 지점은 보호 구간 안 하나뿐).
**이번 라운드에 HIGH-1 로 고친 것과 같은 형태**이고, 이 저장소가 기록해 둔 반복 결함
(「가드가 자기가 막는다고 말한 것을 허용한다」)의 또 한 사례다.

**새 정리 설계**

| | |
|---|---|
| 보호 구간 | 계좌 첫 바이트가 닿는 `_apply_rules` 부터 **교체 완료까지 전부** 한 `try`. `except BaseException` 이 스테이징과 `.replaced-<pid>` 를 **둘 다** 지운다 |
| 교체 | `rmtree(out)` → `move` 를 버리고 **이름 바꾸기 3단계**(`os.replace`; 두 경로가 `out` 의 형제라 같은 파일시스템 = rename 보장): ① 이전 렌더를 `.replaced-<pid>` 로 **옮긴다**(지우지 않는다) ② 스테이징을 비어 있는 `out` 으로 옮긴다(비지 않은 디렉터리 위로는 `ENOTEMPTY`) ③ 교체가 끝난 뒤에야 이전 렌더를 지운다 |
| 실패 처리 | ② 실패 → ①을 되돌리고 스테이징 삭제. ③ 실패 → 「렌더는 성공했고 `out` 은 올바르나 **이전** 렌더가 남았다」를 경로와 함께 **던진다**(계좌가 들었으므로 삼키지 않는다) |
| 잔여물 | 시작 시 형제 `.partial-*`/`.replaced-*` 가 있으면 **거부하고 경로를 알려 준다.** 자동 삭제 안 함 — 동시 렌더의 것일 수 있고, PID 생존은 PID 재사용 때문에 믿을 수 없으며, **계좌가 든 디렉터리를 추측으로 지우는 것**이 이 가드가 막으려는 바로 그 조용한 동작이다 |

**왜 「지우고 옮기기」가 아니라 「옮기고 지우기」인가**: `rmtree(out)` 과 `move` 사이에는
이전 렌더가 **이미 없는데 새 것도 아직 없는** 창이 있고, 거기서 중단되면 이전 렌더를
잃으면서 동시에 계좌가 든 스테이징이 남는다. rename 3단계에는 그 창이 없다.

**테스트**: 단일 주입 테스트를 **실패 지점 7종 파라미터화**로 교체했다 — 치환 도중(첫 규칙만
적용하고 실패) · members 쓰기 · `print-policy-digests` · 읽기-백 · **지문** ·
**`RENDERED.json` 쓰기** · **교체 rename**. 각 케이스가 「출력 디렉터리 없음 + 작업
디렉터리 없음 + 부모 아래 어느 파일에도 계좌 바이트 없음」을 단정한다. 이전 렌더가 있는
경우는 별도 2종(롤백 · 예측자 제거 실패 보고)으로 나눴다 — 거기서는 「계좌 바이트 0」이
성립할 수 없다(이전 렌더가 정당하게 갖고 있다).

**뮤테이션 6/6 RED**:

| # | 뮤테이션 | 결과 |
|---|---|---|
| n1 | `except` 를 지문 앞으로 올림(= 리뷰어가 찾은 그 결함) | **RED 3건** — 정확히 `in-account-fingerprint` · `writing-RENDERED.json` · `at-the-rename-of-the-swap` |
| n2 | `except` 의 두 `rmtree` 제거 | **RED 5건** |
| n3 | `_publish` 의 롤백 제거 | **RED 1건**(이전 렌더 소실) |
| n4 | 교체를 `rmtree(out)` → `move` 로 되돌림 | **RED 2건** |
| n5 | 잔여 작업 디렉터리 거부 제거 | **RED 1건** |
| n6 | 예측자 제거 실패를 삼킴 | **RED 1건** |

##### LOW 3건

- `safety_envelope.yaml` 의 `_runtime.unit` 인용 `:100` → **`:105`**(`:100` 은 `governed_scopes`).
- 부류 핀의 분할 기준을 **「오버라이드한다」에서 「실제로 정렬한다」(관측)**로 바꿨다.
  기존 기준(`cls.covered_content is not base_impl`)은 **패스스루 오버라이드**를 안전 쪽으로
  분류한다 — 그런 오버라이드가 이미 둘 있다(`ExactTrialPlan`·`ActiveSafetyIncidentSet`,
  지금은 집합 필드가 없어 무해). 이제 각 집합 covered 필드를 `model_construct` 로 채워
  **방출 결과가 `sorted(...)` 인지 관측**하고(서로 무관한 5토큰 조합 3회 — 우연히 정렬된
  순서가 나올 확률 1/120^3), **모델이 소유한 모든 집합 필드가 정렬될 때만** 안전 쪽으로
  분류한다(부분 정렬 방지). 직접 관측 불가(집합이 중첩 모델 안)인 7종은 그 사실을 따로
  기록하고 보수적으로 「정렬하지 않음」에 넣는다. 분할 결과는 **6/13 으로 동일**하다.
- 설계 §4 1항의 「`tests/unit/scripts/` 신설」 **원문 자리**에 §5 LOW-5 정정 포인터를 달았다.

##### 재부팅 확인 (원자적 렌더 변경 후, LONG·SHORT 동일)

R0(런북 그대로) = 결함 ① 로 정상 거부 · **잔여물 0** · R1(진단 시드) = `ACTIVATED 5` ·
`--check` exit 0 · **B 부팅 성공 → `run: stopped (signal received).` EXIT=0** ·
틱 = `SKIPPED_SESSION_CLOSED`(캘린더). 4차와 동일하다.


#### 7.8.6 6차 (2026-09-24) — main `5d618f1c` 병합 + 캘린더 수정(#799) 이후 재측정

PR #798(문서)·#799(캘린더 만기 롤) 머지로 main 이 `b5bb5eb5` → **`5d618f1c`** 로 움직여
브랜치에 병합했다.

##### 충돌 1건 — `docs/plans/INDEX.md`, 양쪽 의도 보존

main 은 새 계획 행(`2026-09-24-tos-canonical-set-order-plan.md`)을 추가하면서 이 설계의
행을 **옛 상태**("결정 확정 — 구현 미착수")로 들고 있었고, 우리 쪽은 같은 행을 착지 기록으로
갱신했다. **main 의 새 행 + 우리의 갱신된 행**을 둘 다 남겼다. 그 외 12개 파일은 자동 병합
(`test_deploy_approved_values.py` 포함 — main 의 캘린더/버전/digest 핀과 우리 픽스처·봉투·
프로파일·finality·marketfeed·CIP 핀이 서로 다른 줄이라 충돌 없음).

##### 코드 digest — main 과 **동일해야** 하고, 동일하다

이 브랜치는 `tos/src`·`tos/runtime/src` 의 `*.py` 를 **한 줄도 바꾸지 않는다**(바꾸는 것은
`config/`·`scripts/`·`tests/`·`docs/`뿐). 따라서 병합 뒤 `print-digests` 는 main 이 #799 에서
기록한 값과 같아야 한다 — 실측:

```
expected_code_digest: b9eda9bd69cb24cb694ea44f75f8f44bbef701c3991eb9e6feaee34763d33571
```

`config/tos_runtime/paper/release.yaml:57` 과 `_VALUE_PINS`
(`release.yaml::expected_code_digest`) 둘 다 정확히 이 값을 싣는다.

##### 로더 프로브 분할 — **변경 없음 (18 PASS / 27)**

main 의 변경은 캘린더 로더/월물 규칙과 버전 문자열이고, 프로브가 세는 것은 **좌표 미렌더
거부**다. `calendar.yaml` 은 병합 전후 모두 PASS 이므로 분할이 움직이지 않았다 — 핀을
건드릴 이유가 없다(움직였다면 그것이 바로 갱신 사유였을 것이다).

##### 캘린더 — #799 의 효과를 이 배포의 파일로 재측정

`calendar.yaml` `futures_expiry.krx-index-futures.months` 가 분기 `[3,6,9,12]` → **매월
`[1..12]`**, `calendar_version` 은 `krx-2026.09` → **`krx-2026.09.1`**(`time.yaml::
trading_calendar_version` 과 일치). 같은 파일로 실측(10:00 KST):

| 날짜 | expiry_date | expired | phase |
|---|---|---|---|
| 2026-09-11 | 2026-10-08 | False | **CONTINUOUS** |
| 2026-09-24 (오늘) | 2026-10-08 | False | **CLOSED** |
| 2026-09-28 | 2026-10-08 | False | **CONTINUOUS** |
| 2026-09-30 | 2026-10-08 | False | **CONTINUOUS** |
| 2026-10-01 | 2026-10-08 | False | **CONTINUOUS** |

4차 §7.8.4 가 기록한 「9월 만기(09-10) 이후 분기 내내 EXPIRED」는 **해소됐다.**

⚠ **다만 오늘(2026-09-24)은 틱을 소비할 수 없다 — 값 문제도 만기 문제도 아니고
`calendar.yaml:42` 의 휴장일(추석 연휴)이다.** 그래서 오늘은 08:45–15:45 창 자체가 없고,
실 시계 부팅의 phase 는 (EXPIRED 가 아니라) **CLOSED** 로 나온다. 다음 개장은
`boundary_value` 가 가리키는 **2026-09-28 08:45 KST**(09-25 추석 · 09-26 토 · 09-27 일).

##### 재부팅 (병합 후 · 실 `.env.mock` · 라벨 `paper` · LONG·SHORT 동일)

| 단계 | 결과 |
|---|---|
| R0 렌더(런북 그대로) | **거부 — 결함 ①**(커널 수정 전까지 예상된 상태) · **잔여물 0** |
| R1 렌더(진단 시드) | `ACTIVATED 5` · `--check` exit 0 |
| B 부팅 | **성공** → `run: stopped (signal received).` **EXIT=0** |
| T 틱(실 시계, 15:0x KST) | `phase='CLOSED' is_open=False` → `SKIPPED_SESSION_CLOSED` — **휴장일** |
| T 틱(주입 시계 2026-09-28 10:00 = 다음 개장) | **`TICKED`** · `value_view` = 렌더 저널의 세 필드 · `marketfeed.sqlite3` **snapshots: 1 / preimages: 1** |

즉 **틱을 막던 만기 공백은 #799 로 사라졌고**, 남은 것은 휴장일이라는 평범한 달력 사실뿐이다.

##### 스위트 (병합 후)

`tos/runtime/tests` **2978 passed**(우리 2947 + main 의 캘린더 테스트 31) ·
`tos/tests` **9542** · `tests/unit/scripts` **557** · 로더 프로브 **18/27** ·
거버넌스 6종 전부 PASS · mypy(`tos/tests` 581 · `tos/runtime/tests` 224 ·
`tos/runtime/src` 185 · 신규 2) 전부 Success · ruff/black clean.
