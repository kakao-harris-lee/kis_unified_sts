# TOS 로컬 병렬 작업 목록 — 운영자 로컬 머신용 (2026-10-23)

목적: deploy 호스트의 레인들이 맡지 않은 TOS 작업 중 **운영자 로컬 머신에서 따로 진행할 수 있는 것**을 한 곳에 모은다.
상위 계획은 [`2026-10-22-tos-rescope-plan.md`](2026-10-22-tos-rescope-plan.md) §2·§3 이고, 이 문서는 그 일정을 바꾸지 않는다.

## 1. 지금 누가 무엇을 하는가 (2026-10-23 기준 — 겹치지 않게)

| 작업 | 소유 | PR / 브랜치 | 상태 |
|---|---|---|---|
| M2 PR-3a 주식 MOCK 검증 게이트 (A) | deploy 호스트 오케스트레이터 (lane-927) | #932 `feature/cp3-stock-mock-order-verify` | Codex 1라운드 중 |
| M2 PR-3b 체결·finality·브로커 witness (A) | 오케스트레이터 (lane-3b) | `feature/cp3-stock-mock-fills-finality` (#932 위에 쌓음) | 구현 중 |
| M2 PR-3c 주식 MOCK 세션 운영 경로 (B) | 오케스트레이터 (lane-927) | #936 `feature/cp3-stock-ops` (#932 위) | 리뷰 중 |
| CI `tools/` mypy 차단 단계 | 오케스트레이터 (lane-tools-mypy) | `ci/mypy-tools` | 측정·구현 중 |
| M3 kill -9 복구 drill | 세션 dd | #934 `feature/m3-recovery-drill` | PR 열림 |
| M4 한 장 상태판 | 세션 dd | #935 `feature/tos-status-board` | PR 열림 |
| M1 tenant cron 상시화 준비 | 세션 dd | #933 `chore/cp3-cron-resident` | PR 열림 (설치는 운영자) |

위 작업의 파일은 로컬에서 고치지 않는다. 겹칠 수밖에 없으면 그 PR 에 코멘트로 알린다.

## 2. 로컬에서 할 수 있는 작업

### L1 — #911 · #912 포지션 분류 결함 (A 등급, 코드)

**무엇:** 이슈 두 건 모두 `RESULT_UNMATCHED` 결과의 수량이 포지션 관측과 ARE 판정 합계에서 **덜 세어지는** 문제다.
- #911: 미반영 결과가 UNKNOWN 으로 분류된다. UNKNOWN 은 반대쪽 확정 포지션과 상쇄되므로, 결과가 아예 없을 때(IN-FLIGHT)보다 합계가 작아질 수 있다.
- #912: 종결 CONSUMED 뒤에 도착한 체결(취소와 교차한 체결)은 런타임 리더가 버린다.

**왜 지금:** 리스크 한도 경로이고, PR-3b 가 실제 브로커 체결(취소 교차 포함)을 들여오기 시작한다. 주식 MOCK 이 체결을 내기 전에 닫는 것이 맞다.

**어디:**
- 커널: `tos/src/tos/position/predicates.py`(분류표 · `classify_sealed_sends`)
- 런타임: `tos/runtime/src/tos_runtime/riskstate/position.py`
- 근거 주석: `tos/src/tos/engine/core.py` RESULT_UNMATCHED 기록부(KW2b-#13)

**수용 기준** (이슈 본문 그대로):
- [ ] 직전 포지션 −10/0/+10 × 양방향에서, 미반영 결과의 수량이 «결과 없음» 상태보다 판정 합계를 낮추지 않음을 고정하는 테스트
- [ ] 종결 CONSUMED 뒤 UNMATCHED 체결 회귀 테스트(양방향). 현재 코드에서 red 여야 한다
- [ ] 버킷 선택 근거를 분류표 docstring 에 기재
- [ ] `tools/tos_redigest.py --write` 후 `--check` (트리 4개 자동 발견)

**PR:**
- 브랜치 `fix/tos-position-unmatched-bucket`, origin/main 에서 시작한다. 두 이슈를 한 PR 로 묶어도 된다(같은 분류표).
- A 등급이므로 Claude 쪽 리뷰 1회와 Codex(운영자 승인 범위)를 거친다. 머지는 리뷰 통과 + head green 일 때 `--match-head-commit` 으로 한다.

**겹침:** lane-3b 는 결과를 *만드는* 쪽(전송 어댑터 → 엔진 inbox · finality)이고, L1 은 결과를 *읽고 분류하는* 쪽이다. 파일은 겹치지 않을 것으로 본다. 겹치면 PR 코멘트로 알린다.

### L2 — 장중 GET 실측 (C 등급, 측정 기록)

장중에만 할 수 있다(10-23 금 15:30 까지, 또는 10-26 월 09:00~15:30). 실전 키로는 **GET 시세만** 한다(CLAUDE.md 비협상 — 실주문 경로 금지).

| # | 측정 | 명령 / 방법 | 확인할 것 |
|---|---|---|---|
| a | 주식 분봉 첫 페이지 커서 | 전용 원샷 프로브가 없다. `tools/tos_cp3/minute_probe.py` 는 PR-1(선물) 전용이라 `market: stock` 을 모른다. `tools/tos_cp3/quote_client.py` 의 stock 경로로 FHKST03010230 을 GET 1회 하는 임시 스크립트를 분리 워크트리에서 돌린다. 도구로 남길 가치가 있으면 별도 B 등급 PR 로 올린다. | `quote_initial_cursor: "153000"` 이 장중에 당일 최신 행부터 주는지, 페이지 이어짐이 맞는지 (#922 미측정 항목) |
| b | 005930 가격제한폭 · 호가단위 | `tools/tos_cp3/live_producer/band_probe.py --config <로컬 사본> --instrument 005930 --session-dir <임시 디렉터리>`. 먼저 `--confirm` 없이 돌려 출력을 본다. | `stck_mxpr/stck_llam/stck_sdpr`, `aspr_unit × 100` 이 주식 트리 호가단위 표의 해당 행과 같은지 (rc 0 + `band_tick_checked`) |
| c | VTS 잔고 조회 형태 | PR-3a 의 VTTC8434R 리더를 mock 키로 1회 (GET) | `rt_cd == "0"`, 응답 필드가 3a 의 가정과 같은지 (item 12 의 원천) |

규칙:
- 분리 워크트리에서 실행한다(`git worktree add --detach`). 프로브는 공유 체크아웃에서 돌리지 않는다.
- `--session-dir` 은 임시 경로로 한다. 실 상태 디렉터리(`~/.local/state/tos/**`)를 쓰지 않는다.
- 키는 env 로만 넘긴다. 커밋하지 않는다.
- `config/tos_probes/cp3-live-producer-stock-005930.yaml` 의 `env_file` 은 deploy 호스트 절대 경로(`/home/deploy/.../.env.real`)다.
  - 로컬에서는 이 파일을 임시 경로에 복사해 `env_file` 만 바꿔 쓴다. 사본은 커밋하지 않는다.
  - 같은 파일의 `market: stock` 일 때는 `KIS_STOCK_APP_KEY` / `KIS_STOCK_APP_SECRET` 두 개만 읽는다.

기록: `docs/broker-profiles/evidence/2026-10-2x-stock-005930-quote-band/README.md` 에 표 하나(R7: 명령 · 결과 숫자 · 로그 경로)로 남긴다.
- 불일치가 나오면 기록만 한다. 고칠 코드는 해당 PR 소유자에게 이슈로 넘긴다.

### L3 — KRX 호가가격단위 1차 출처 확정 (C 등급, 문서·설정 주석)

**무엇:** 주식 트리 `config/tos_runtime/cp3-setup-d-stock-005930/venue_constraint_policy.yaml` 의 `price_band_ticks` 7행은 현재 **grade C** 다(2023-01-25 단일 호가단위표, 2차 출처 한화 CS181_3p · 0 불일치). KRX 유가증권시장 업무규정 시행세칙의 해당 조문을 찾아 인용을 grade A 로 올린다.

**하는 것:**
- 헤더 주석의 출처 줄과 `residual_risks` 를 갱신한다. **값은 바꾸지 않는다.** 1차 출처와 다르면 값을 고치지 말고 이슈로 올린다.
- 증거 파일은 `docs/broker-profiles/evidence/` 아래에 둔다(선물 선례: `2026-10-08-krx-venue-limits/`).

**확인:** 주석만 바꿔도 트리 테스트와 digest 확인은 돌린다.
- `pytest tos/runtime/tests/compose/test_tenant_tree_stock.py`
- `python tools/tos_redigest.py --check`

**겹침:** #932 가 같은 트리를 고친다. #932 머지 뒤에 시작하거나, 머지 직전에 main 을 합친다.

## 3. 로컬이 아니라 deploy 호스트에서 할 것 (참고)

다음은 호스트의 cron · 상태 디렉터리 · 상주 런타임에 묶여 있어 로컬에서 하지 않는다.

| 작업 | 언제 | 비고 |
|---|---|---|
| 첫 실 MOCK 주식 세션 (M2 완료 판정: MOCK 체결 1건 + evidence 행) | #932 · PR-3b · #936 머지 뒤 첫 영업일 | 운영자 결정. `.env.mock` · 러너 env 템플릿(#936) |
| tenant cron 설치 | #933 머지 뒤, 10-27 목표 | 설치 명령은 #933 이 보고 |
| 11-11 롤 dry-run → 11-12 첫 실롤 | 11-11 / 11-12 | 런북 §7.2-e (#933) |
| SHORT tenant 켤지 | 운영자 결정 | rescope §6-4 |

## 4. 로컬 환경 준비

```bash
git clone git@github.com:kakao-harris-lee/kis_unified_sts.git && cd kis_unified_sts   # 또는 git pull
python3.11 -m venv .venv && . .venv/bin/activate        # CI 와 같은 3.11
pip install -e "./tos[test]" && pip install -e "./tos/runtime" --no-deps
pip install -e ".[dev]" import-linter "black==26.5.1" "mypy==2.3.1" "pytest-xdist==3.8.0"
python tools/tos_redigest.py --check                    # 설치 확인 — 트리 4개 OK 여야 한다
```

- 정확한 설치 순서는 `.github/workflows/tos-firewall.yml` 의 install 단계가 기준이다. 이 블록과 다르면 워크플로를 따른다.
- 워크트리에서 테스트할 때는 `PYTHONPATH=tos/runtime/src:tos/src` 를 준다. editable 설치가 다른 체크아웃을 가리킬 수 있기 때문이다.
- `.env*` · `.kis_token_*` 는 커밋 금지다(.gitignore). L2 키는 셸 env 로만 넘긴다.

## 5. 충돌을 막는 약속 (호스트 레인과 같은 규칙)

1. **digest 는 마지막에:** 런타임 src(`tos/src` · `tos/runtime/src`)를 바꾸는 PR 은 push 직전에 순서대로 한다.
   1. `git merge origin/main`(리베이스 금지)
   2. `tools/tos_redigest.py --write`
   3. `tools/tos_redigest.py --check`

   두 런타임 PR 중 **나중에 머지되는 쪽**이 다시 재도출한다.
2. **merge-tree 확인:** push 전에 `git merge-tree --write-tree origin/main HEAD` 가 깨끗해야 한다.
   - 10-22 에 두 레인이 같은 사고를 반대 방향으로 고쳤고, 각자 green 이었는데 합치면 red 였다.
3. **소유 표시:** 착수할 때 해당 이슈에 코멘트(«로컬에서 착수, 브랜치 X»)를 남긴다. 호스트 오케스트레이터가 같은 이슈를 레인에 배정하지 않게 하기 위해서다.
4. **머지 순서:** 머지 직후 그 PR 번호를 이슈나 PR 코멘트로 남긴다. 호스트 레인들은 main 을 합칠 때 그것을 보고 digest 를 재도출한다.
5. **전체 스위트는 CI 에 맡긴다.** 로컬에서는 바꾼 파일의 테스트만 돌린다.
