# TOS — synthetic 트리의 체결 확증: 독립 venue 원장 (#1011)

- 날짜: 2026-10-31 · 저자: 세션 모델 단독 · 이슈: #1011 (선행 #1015 · review-1015 H1 · review-1007 M2)
- 리뷰 등급(구현 PR): **A** — RCL 용량 해제 경로. Claude 측 독립 리뷰 1회. Codex 는 운영자가 범위·비용을 승인할 때만.
- 상태: **운영자 결정 대기** (§6). 결정 전에는 구현하지 않는다.
- 완료 조건(`TOS_PAPER_READY` §2-1 관련): synthetic 트리에서 **진입 → 청산 → 다음 진입**이 한 프로세스에서, 그리고
  재기동 뒤에도 통과한다. 실주문 0.

## 1. 사실 (코드에서 측정, 2026-10-31 main `7cf9a07c`)

| # | 사실 | 위치 |
|---|---|---|
| F1 | synthetic 전송은 순수 함수다 — 「network 0 · credentials 0」, 「no clock, no RNG, no ambient state」, **받은 주문의 durable 기록이 없다** | `tos/src/tos/brokeradapter/synthetic.py` · `recon/witness_synthetic.py` docstring |
| F2 | 그래서 synthetic 트리의 유일한 증인 `SyntheticLedgerWitness` 는 **증거 저장소의 `EGRESS_RESULT_CONSUMED`/`RESULT_UNMATCHED` 행을 다시 읽는다** — `EVIDENCE_RECEIPT` 경로와 같은 저장소다 | `recon/witness_synthetic.py` |
| F3 | 그 스냅샷은 `independent_of_evidence_store=False`(기본값, fail-closed). 대조는 `permits_capacity_release=False`, 사유 `WITNESS_NOT_INDEPENDENT` | `recon/ports.py:144` · `recon/service.py:731-741` |
| F4 | release consumer 는 그것을 `CAPACITY_RELEASE_HELD` · `NOT_CORROBORATED` 로 남긴다 → 진입 예약은 `COMMITTED_UNBOUND` 에 머물고 `POSITION_CONSUMED` 에 가지 못한다 | `posttrade/release_consumer.py:437-444` · 시험 `test_compose_root.py::test_full_fill_hand_off_never_releases_rcl_capacity_end_to_end` |
| F5 | step 8 은 미해제 예약이 있는 scope 에 OPEN 을 거부하고, CLOSE 는 `POSITION_CONSUMED` 행이 정확히 하나일 때만 받는다 → **첫 진입 뒤 scope 봉인**(월물 잎이 바뀔 때까지) | `risk/ledger_stages.py` · #1015 시험 `test_synthetic_close_bound_inert.py` |
| F6 | POST_TRADE 현재성 차원은 최신 HELD 사유가 `NOT_CORROBORATED` 이면 **«진짜 대조 충돌»** 로 읽어 `False` 를 낸다. «증인이 독립이 아님»과 «충돌»이 같은 사유 문자열을 쓴다 | `posttrade/release_currentness.py:52,84` · `compose/_dimension_readers.py:705` |
| F7 | #1015 의 durable 진입 잔량 CLOSE 상한(`DurableEntryCloseBoundReader`)은 준비돼 있으나 F4 때문에 inert | `riskstate/close_bound.py` |
| F8 | 주식 트리(KIS mock)는 `KisStockBrokerWitness` 가 브로커 API 를 읽어 독립이다 — 같은 해제 경로가 동작한다(#1007) | `recon/witness_kis.py` |
| F9 | 운영 RCL(`cp3-setup-d-{long,short}-data/A05611`)은 `AdvanceAuthorityEpoch` 행뿐 — 아직 예약이 커밋된 적 없다 | review-1007 M2 실측 |

**결론.** 봉인은 버그가 아니라 W2-R 의 «정직 상태»가 의도한 결과다. 자기 저장소를 두 번 읽고 «확증»이라 하지
않는다는 규칙이 맞기 때문에, 고칠 것은 규칙이 아니라 **synthetic venue 에 독립된 기록이 없다는 사실**이다.
§2-1 무인 10 거래일(M4, 11-30~12-11) 안에서 LONG/SHORT 는 첫 진입 뒤 남은 날을 모두 DENY 로 보내게 되고, F6 때문에
그 scope 의 POST_TRADE 차원도 «충돌»로 남는다.

## 2. 선택지

| 안 | 내용 | 판단 |
|---|---|---|
| **A (추천)** | **synthetic venue 원장** — 전송 경계에서 synthetic 체결을 **별도 SQLite 파일**에 먼저 쓰고, 새 증인이 그 파일만 읽는다. 독립성은 «다른 파일 · 다른 쓰기 주체 · 증거 행에서 파생되지 않음»으로 구조적으로 참이 된다 | 규칙을 그대로 둔다. 대조가 실제로 잡는 것이 생긴다(§3.4) |
| B | 정책 예외 — transport 가 SYNTHETIC 이면 store-derived 증인의 확증을 받는다 | 대조가 공허해진다(자기 자신과 일치). 예외 분기가 KIS 경로로 새면 fail-open. **기각** |
| C | 현 상태 유지 + 런북에 «첫 진입 뒤 월물까지 봉인» 기록 | 안전하지만 M4 창에서 Setup D 가 하루 1회도 못 돈다. §2-1 의 «무인 운용»이 «무인 DENY»가 된다. **기각**(단, A 가 늦어지면 임시 상태) |
| D | 사유 분리만 — `WITNESS_NOT_INDEPENDENT` 를 F6 의 «충돌»에서 떼어 낸다 | 봉인은 그대로. A 와 함께 하는 작은 정정으로 §3.5 에 넣는다 |

## 3. 설계 (안 A)

### 3.1 venue 원장 — 무엇을, 어디에, 언제

- 새 모듈 `tos_runtime/venue_ledger/synthetic.py`(런타임만 — **커널 `tos/src` 변경 없음**).
- 파일: 데이터 잎 안 `venue_ledger.sqlite3`(0600, WAL) — `evidence.sqlite3`·`rcl.sqlite3` 와 **다른 파일**, 다른 연결.
- 행(append-only, 갱신 없음): `attempt_id` · `broker_execution_id` · `instrument` · `side` · `quantity` ·
  `filled_quantity` · `remaining_quantity` · `result_kind` · `trading_date`(KST, 신뢰 시계) · `written_seq`.
  키 `(trading_date, broker_execution_id)` UNIQUE — KIS ODNO 와 같은 정체성 규율(service.py 의 C-1 조인).
- **쓰는 때:** `SyntheticPaperTransport.send_once` 를 감싸는 런타임 래퍼 `RecordingSyntheticTransport` 가 커널 함수의
  결과를 받은 **직후, 반환하기 전**에 쓴다. 쓰기가 실패하면 결과를 반환하지 않고 전송 오류로 올린다 —
  «venue 는 받았는데 기록이 없다»를 만들지 않는다(KIS 에서 «브로커가 받았는데 응답을 못 받음»과 같은 모양으로
  기존 미확정 경로를 탄다).
- 같은 attempt 의 재송신(재기동 drill §2-3)은 synthetic 이 결정적이므로 같은 행을 다시 만든다 → UNIQUE 충돌은
  «이미 venue 에 있음»으로 읽고 **두 번째 체결을 만들지 않는다**(중복 송신 0 을 venue 쪽에서도 측정 가능).

### 3.2 증인

- 새 `SyntheticVenueLedgerWitness(BrokerWitness)` — `venue_ledger.sqlite3` 만 읽기 전용으로 연다(증거 저장소 핸들을
  받지 않는다 — 생성자 서명으로 강제).
- 스냅샷: `provenance="synthetic-venue-ledger"`, `independent_of_evidence_store=True`, `positions` 는 원장 체결의
  순합(scope 종목만), `positions_complete=True`(원장이 venue 의 전부이므로), `order_inquiry_date` = 당일.
- 기존 `SyntheticLedgerWitness` 는 지우지 않는다 — 원장이 없는 옛 잎·시험이 쓴다. compose 는 **트리 설정**
  (트리의 posttrade 설정에 새 키 `witness: synthetic_venue_ledger` — 정확한 파일은 P2 에서 기존 synthetic 트리 YAML 을
  읽고 정한다)로 고른다. 트리 이름 분기 없음. 키가 없으면 옛 증인(지금 동작, fail-closed).

### 3.3 효과 (바뀌는 것)

- synthetic FULL_FILL → 대조 MATCHED → `POSITION_CONSUMED`(진입) / `RELEASED`(청산). #1015 의 CLOSE 상한이 살아난다.
- `entry_discharge`(#966/#1007)의 «브로커 flat» 확인은 원장 순포지션 0 으로 성립한다.
- KIS 주식 경로: 변화 없음.

### 3.4 대조가 이제 실제로 잡는 것

- 증거 기록 직전 프로세스가 죽음 → 원장에는 체결, 증거에는 없음 → `ORPHAN_BROKER_ORDER` → HOLD(정상 fail-closed).
- 드라이버가 결과를 잘못 재주입(수량·종목 불일치) → 필드 충돌 → HOLD.
- 증거만 있고 원장에 없음(래퍼 우회) → 증인 부재 → HOLD.
  지금의 store-derived 증인은 이 셋을 구조적으로 볼 수 없다.

### 3.5 사유 분리 (안 D, 같은 PR)

- release consumer 가 `report.reason == WITNESS_NOT_INDEPENDENT` 이면 HOLD 사유를 새 값 `WITNESS_NOT_INDEPENDENT` 로
  남긴다. `release_currentness` 는 지금처럼 `NOT_CORROBORATED` 만 충돌로 읽는다 → 옛 잎의 «독립 아님»이 «충돌»로
  보고되지 않는다. 해제 판정은 바뀌지 않는다(어느 사유든 HOLD).

## 4. 순서

| PR | 내용 | 등급 |
|---|---|---|
| P1 | venue 원장 모듈 + 래퍼 + 증인 + 단위 시험(§5 ①~④) | A |
| P2 | compose 배선(설정 키) + 사유 분리(§3.5) + LONG/SHORT/paper 트리 YAML + digest 재도출 + compose e2e(§5 ⑤~⑦) | A |
| P3 | 런북: 원장 파일 위치·백업 대상 추가(콜드 백업)·되돌림 | C |

배포: 다음 잎(11-12 롤 뒤 새 월물)부터 켠다 — 옛 잎 A05611 은 예약이 없으므로(F9) 같은 잎에서 켜도 되지만, 롤과
겹치지 않게 **11-13 이후 첫 거래일**에 켠다. 목표: P1·P2 머지 11-10, 켬 11-13, M4 창(11-30) 전에 진입→청산 1회 실측.

## 5. 시험

1. 래퍼: 결과 반환 전 원장 행 존재 · 쓰기 실패 → 결과 미반환 · 같은 attempt 재송신 → 행 1개, 두 번째 체결 없음.
2. 증인: 증거 저장소 핸들 없이 생성 · `independent_of_evidence_store=True` · 다른 종목 행 무시 · 깨진 행 → `WitnessUnavailable`.
3. 대조: 원장 체결 + 증거 일치 → MATCHED · 원장만 → ORPHAN → HOLD · 수량 불일치 → 충돌 → HOLD.
4. 사유 분리: store-derived 증인 → HOLD 사유 `WITNESS_NOT_INDEPENDENT`, POST_TRADE 차원 `True`; 진짜 충돌 → `False` 유지.
5. compose e2e(synthetic): 진입 → `POSITION_CONSUMED` → CLOSE(#1015 상한 통과) → `RELEASED` → 다음 OPEN 허용.
   #1015 의 `test_synthetic_close_bound_inert.py` 는 **뒤집혀야** 한다(설정 키를 켠 트리에서) — 옛 증인 트리에서는 그대로.
6. 재기동: 체결 원장 기록 직후 `kill -9` → 재기동 → 중복 체결 0, 예약 HOLD 뒤 대조로 정상 진행.
7. 과청산: 진입 1 → CLOSE 2 → step 6 거부(#1015) · 원장 순포지션 음수 불가.

## 6. 운영자 결정

1. **안 A 채택 여부**(추천). 기각하면 C 로 두고 런북에 봉인을 적는다.
2. **독립성의 의미를 이것으로 인정하는가** — 같은 프로세스·같은 호스트의 다른 파일·다른 쓰기 주체를
   «evidence store 와 독립»으로 본다. 실제 브로커만큼 독립은 아니다(같은 코드가 둘 다 쓴다). 이 한계는
   `provenance="synthetic-venue-ledger"` 로 남겨 KIS 증인과 구분된다. 선물은 실주문이 영구 차단이라(CLAUDE.md)
   synthetic 이 선물의 최종 venue 다.
3. **켜는 날**: 11-13 이후 첫 거래일(추천) 또는 P2 머지 직후.

## 7. 하지 않는 것

- W2-R 규칙(store-derived 증인은 확증 불가) 완화 — 안 B.
- 커널 `tos.brokeradapter.synthetic` 변경 — 순수 함수로 둔다.
- 부분체결 synthetic 진입(review-1015 L2) — 지금 fill policy 가 1/1 이라 생기지 않는다. 생기면 #980 과 함께.
- 새 checker·레지스터(R5) — 원장은 venue 의 기록이지 판정 장치가 아니다.
