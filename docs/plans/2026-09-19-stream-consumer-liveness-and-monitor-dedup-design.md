# 스트림 소비자 생존 증명 + 모니터 데몬 중복 해소 — 설계

- 작성 2026-09-19 (KST)
- 상태: **설계, 착수 전 운영자 승인 대기**
- 선행: #739 (`f53d29b0`), #741 (`bcc01506`), #749 (`4471824a`), #750 (리뷰 중)
- 관련 이슈: #751, #752, #753

## 0. 한 줄

`shared/streaming/stage.py` 에 이미 있는 `MultiStreamStage` 는 **프로덕션 사용자가
0명**이고, 두 모니터 데몬은 그것을 손으로 다시 짰다. 그 중복이 #739·#741 의 수정을
두 번 쓰게 만들었고 — **공용 스테이지에는 끝내 도달하지 못했다**. 같은 결함이
`StreamStage` 를 쓰는 라이브 서비스 5개에 지금도 살아 있다.

## 1. 왜 지금인가 — 세 개의 실명 경로

이 데몬들은 **살아 있으면서 아무것도 소비하지 않는** 상태에 세 가지 서로 다른
경로로 도달한다. 2026-09-17~18 의 이틀 실명은 그중 첫 번째였을 뿐이다.

### 1.1 (해결됨) 스트림 키 소멸 → NOGROUP

24h TTL 로 스트림 키가 사라지면 `xreadgroup` 전체가 실패한다. #739 가 두 모니터에
복구 경로를 붙였고 프로덕션에서 실증했다.

### 1.2 (미해결) 조용한 핫 루프 — 공용 스테이지에 남아 있다

#741 이 두 모니터에서 고친 회귀는 이것이다: 읽기는 계속 실패하는데 그룹이 이미 전부
존재하면 백오프를 건너뛰고, DEBUG 라 로그도 0 — **33,746 reads/s, 로그 0줄**.
3분기 규칙(하나라도 생성→무대기 재시도 · 실패 있음→백오프 · 새로 만든 것 없음→백오프)
으로 해소했다.

**그 수정은 `shared/streaming/stage.py` 에 적용되지 않았다.** 네 군데가 그대로다:

| 위치 | 클래스 | 사용 서비스 |
| --- | --- | --- |
| `stage.py:337` | `StreamStage._claim_pending_messages` | risk_filter, order_router, stock_order_router, stock_risk_filter, news_scorer |
| `stage.py:449` | `StreamStage.run` | 〃 |
| `stage.py:569` | `MultiStreamStage._claim_pending_messages` | (없음) |
| `stage.py:695` | `MultiStreamStage.run` | (없음) |

네 곳 모두 같은 모양이다 — 복구 결과(`ConsumerGroupEnsure`)를 **버리고**,
`asyncio.sleep(0)` 후 `continue`, 로그 없음:

```python
except Exception as exc:
    if _is_nogroup_error(exc):
        for stream in self.input_streams:
            await _recover_missing_consumer_group(...)   # 결과를 읽지 않는다
        await asyncio.sleep(0)
        continue                                          # 백오프도 로그도 없다
```

즉 **라이브 서비스 5개가 09-17 과 같은 조용한 스핀에 여전히 노출돼 있다.**
중복이 아니었다면 한 번의 수정으로 끝났을 일이다. 이것이 중복 제거가 미용이 아니라
정합성 문제인 이유다.

### 1.3 (미해결) 소비 태스크의 조용한 사망

두 데몬 모두 이 구조다 (`futures_monitor/daemon.py:298`, `stock_monitor/daemon.py:377`):

```python
consumer = asyncio.create_task(self._consume_loop())
status   = asyncio.create_task(self._status_loop())
try:
    await self._stop.wait()
finally:
    consumer.cancel(); status.cancel()
    for t in (consumer, status):
        with contextlib.suppress(asyncio.CancelledError):
            await t
```

`_consume_loop` 안에서 `xreadgroup` 은 `try` 로 감싸여 있지만 **메시지 처리 후의
`xack` 은 아니다** (`futures_monitor/daemon.py:405`, `stock_monitor/daemon.py:494`).
Redis 가 한 번 끊기면 그 줄에서 예외가 나고 `_consume_loop` 태스크가 죽는다.
그때:

- `_stop` 은 세팅되지 않는다 → `run()` 은 `_stop.wait()` 에서 계속 대기.
- `_status_loop` 는 계속 돈다 → 컨테이너는 살아 있고 상태 키도 갱신된다.
- `run()` 의 지역 변수 `consumer` 가 태스크 참조를 붙들고 있으므로 **GC 가 되지
  않는다** → `Task.__del__` 의 *"Task exception was never retrieved"* 경고조차
  찍히지 않는다. 완전 무음이다.
- SIGTERM 이 와서야 `finally` 의 `await t` 가 원래 예외를 다시 던진다. 몇 시간 뒤,
  종료 오류로 위장한 채.

`RestartCount=0`, `state: running`, 상태 키 신선 — 09-17 과 **똑같은 지문**이다.
헬스체크로는 잡히지 않는다.

## 2. 왜 하트비트가 유일한 해법인가

정상 유휴 루프의 코드 경로는 이렇다 (`stage.py:441-471`, 모니터도 동형):

```
xreadgroup(block=2000) → 메시지 없음 → post_poll(0) → sleep(0) → continue
```

**이 경로에는 어떤 레벨의 로깅도 없다.** `consumer_group_already_present` 는
`recover_missing_consumer_group` 안에서만, 즉 읽기가 *이미 실패한 뒤에만* 발화한다.
따라서:

- `LOG_LEVEL=DEBUG` 를 켜도 유휴 생존 증거는 **생기지 않는다**. #756 이 필요한
  작업이긴 하지만 이 문제를 풀지는 못한다.
- 소비가 없는 조용한 세션은 "소비자가 건강했지만 트래픽이 없었다" 와 "소비자가
  죽어 있었다" 가 **로그상 완전히 동일**하다.

그래서 #750 의 관측 판정은 조용한 날을 `PARTIAL` 로 떨어뜨린다. 그것이 현재로서는
정직한 판정이다 — 그리고 하트비트가 생기는 순간 조용한 날이 다시 정당하게
`COMPLETE` 로 읽힌다. **#750 이 하트비트의 필요를 만든 것이 아니라, 드러낸 것이다.**

### 2.1 정정 — 생산자는 이 하트비트로 해결되지 않는다

**이 문서의 초판은 하트비트를 소비자 문제로만 다뤘다. 틀렸다.** #750 리뷰가 실측으로
지적했고, 확인했다. 두 침묵은 원인이 다르다.

| | 소비자 | 생산자(`futures-decision-engine`) |
| --- | --- | --- |
| 증명 줄 | `stream_message_processed` (`stage.py:175`) | setup-eval INFO |
| 발화 조건 | **메시지마다** | **상태가 바뀔 때만** — `setup_eval_throttle_key(name, outcome, reason)` (`shared/strategy/entry/setup_eval_publisher.py:140`) |
| 침묵의 의미 | 트래픽이 없었다 | **아무 정보 없음** |
| `stage.py` 경유 | 예 | **아니오** |

생산자는 `shared/streaming/stage.py` 를 지나가지 않는다. 그러므로 §3.1 의 하트비트를
넣어도 생산자에는 닿지 않는다. 그리고 생산자의 침묵은 설계상 억제된 것이라 어떤
시간 척도에서도 생존에 대해 말해 주는 바가 없다.

실측(세션 내 08:45–15:45, 2026-09-18 정본):

```
observed 10건 · 최악 간격 17,050s (4시간 44분)
blind    10건 · 최악 간격 24,785s   ← blind 를 합쳐도 최악 간격은 그대로 17,050s
세션 내 전체 줄 21건 · 최악 간격 17,050s
```

**승격할 더 촘촘한 줄이 없다.** 2026-09-11 은 422줄로 촘촘해 보이지만 그중 374줄이
`prev_close: no daily bar data` — PR #668 이 이미 닫은 `no_prev_close` 결함의 증상이라
**main 에는 더 이상 존재하지 않는다**. 즉 09-18 이 건강한 생산자의 현재 모습이다.

따라서 **생산자는 자기 몫의 생존 발화가 따로 필요하다** — 평가 루프가 매 사이클
«돌았다»를 남기는 것. 그 전까지 #750 은 생산자를 신선도 채점에서 **이름을 명시해
면제**하고(임계값을 키우는 게 아니라), 수집 커버리지·맹목·무증거 규칙으로만 채점한다.
임계값을 18,000s 로 올리는 것은 "5시간에 한 번 증명했다"는, 운영상 의미 없는 구간을
세탁하는 것이고 — 17,050s 는 그 값의 95% 라 다음 조용한 구간에서 바로 또 넘는다.

## 3. 설계

### 3.1 한 곳에 넣는다 — `post_poll`

`post_poll(message_count)` 는 이미 존재하고, **유휴 폴링을 포함해 매 폴링마다**
호출된다 (`stage.py:467`, `714`; pending claim 경로도 `436`, `681`). 새 훅이 필요
없다. 기반 구현에 rate-limited 하트비트를 넣으면 `StreamStage` 를 쓰는 5개 서비스가
한 번에 증거를 갖는다.

```
shared/streaming/stage.py
  _emit_liveness(message_count)          # StreamStage / MultiStreamStage 공용
    - 마지막 발화로부터 heartbeat_interval_seconds 경과했을 때만
    - logger.info(format_audit_kv(
          event="stream_consumer_alive",
          consumer_group=..., streams=..., worker_id=...,
          polls=<구간 폴링 수>, messages=<구간 배달 수>,
          seconds_since_delivery=<마지막 배달로부터 경과>))
```

두 가지 성질이 중요하다:

1. **INFO 로 낸다.** DEBUG 는 배포 환경에서 도달 불가였다는 것이 #749 이전의 실제
   상태였고, 하트비트는 증거이지 진단이 아니다.
2. **폴링 수와 소비 수를 같이 싣는다.** `polls>0, messages=0` 은 "살아서 보고 있는데
   트래픽이 없다" 를, `polls=0` 은 애초에 하트비트가 안 나온다는 뜻이므로 부재 자체가
   신호다. #750 의 `observed` 패턴은 `stream_consumer_alive` 를 소비 증명이 아니라
   **생존 증명**으로 따로 잡는다 (§3.4).

`news_scorer` 는 `post_poll` 을 이미 오버라이드한다 (`main.py:221`) — 기반 구현을
`super().post_poll(...)` 로 부르게 하거나, 하트비트를 `post_poll` **호출부**(즉 `run()`
안)로 올려 오버라이드가 생존 증거를 조용히 없애지 못하게 한다. **후자를 택한다**:
서브클래스가 훅을 덮는 것만으로 관측이 사라지는 구조는 이 작업의 취지에 반한다.

### 3.2 설정 (CLAUDE.md: configuration-driven only)

하드코딩 금지. `config/` 의 스트리밍 설정에 넣고 `StreamStage.__init__` 이 읽는다.

| 키 | 기본 | 근거 |
| --- | --- | --- |
| `heartbeat_interval_seconds` | 60 | #750 의 `observation_max_gap_seconds: 1800` 보다 충분히 작아 한 번 걸러도 판정이 흔들리지 않는다. 6.5시간 세션에 ~390줄 — 무시 가능. |

두 값이 **서로를 알아야 한다**: 하트비트 간격이 관측 최대 갭보다 커지면 건강한
날이 `stale_observation` 으로 떨어진다. 설정에 그 관계를 주석으로 못박고, #750 의
테스트에 `heartbeat_interval_seconds < observation_max_gap_seconds` 를 단언하는
회귀 테스트를 둔다.

### 3.3 알림 — 로그 파이프라인이 아니라 메트릭

저장소에 로그 기반 알림 파이프라인이 없다 (Loki/promtail 없음;
`monitoring/prometheus/alert_rules.yml` 의 7개 규칙은 전부 메트릭 기반). 새
파이프라인을 세우는 것은 이 작업의 범위를 훨씬 넘는다. 기존 자산에 맞는 길:

```
services/monitoring/metrics.py
  stream_consumer_last_message_timestamp_seconds{consumer_group, stream}   Gauge
  stream_consumer_polls_total{consumer_group, stream}                      Counter
```

`stream_exporter` 는 스트림 길이/최종 메시지 나이만 내보내고 **컨슈머 그룹은 다루지
않는다** — 그래서 지금은 "소비자가 소비했는가" 를 볼 메트릭 자체가 없다. 위 둘이면
규칙은 자명하다:

```yaml
- alert: StreamConsumerNotPolling
  expr: increase(stream_consumer_polls_total[5m]) == 0
  for: 5m
  labels: { severity: critical }
  annotations:
    summary: "{{ $labels.consumer_group }} 가 5분간 폴링하지 않았다"
    description: "컨테이너는 살아 있어도 소비 루프가 죽어 있을 수 있다 (2026-09-17 참조)."
```

`polls_total` 이 멈추는 것은 §1.2 의 핫 루프(폴링은 돌지만 읽기가 실패)와 §1.3 의
태스크 사망(폴링 자체가 멈춤)을 **구분**해 준다. 후자가 헬스체크가 못 잡던 바로 그
경우다.

> 범위 판단: 알림은 "크지 않으면 함께" 라는 조건부 요청이었다. 메트릭 2개 + 규칙
> 1~2개는 작다. 로그 파이프라인 구축은 크다. 전자만 한다.

### 3.4 #750 관측 설정 연동

`config/f9_observation.yaml` 의 각 소비자에 `liveness` 패턴군을 추가한다 —
`observed`(소비 증명) 와 **분리**한다. 소비 0건인 건강한 날은
`consumed=0, alive=true` 로 렌더링돼야 하고, 그것이 `COMPLETE` 의 정당한 근거가
된다. 두 개념을 한 패턴에 섞으면 #750 이 방금 닫은 결함이 되살아난다.

### 3.5 모니터 데몬 중복 해소

**두 모니터를 `MultiStreamStage` 위로 옮긴다.** 새 추상화를 만들지 않는다
(CLAUDE.md: 기존 모듈 재사용 우선). 옮기고 나면:

- `_consume_loop` 의 손수 짠 xreadgroup·ack·복구 전체가 사라진다 (두 파일 각 ~95줄).
- §1.2 의 3분기 규칙이 공용 스테이지 한 곳에만 존재한다.
- §1.3 의 태스크 사망은 `MultiStreamStage.run()` 의 `try/finally` 구조로 흡수되고,
  **추가로** `run()` 이 소비 태스크를 감독하도록 고친다 (아래).
- 도메인 로직(`handle_fill`/`handle_signal`, PnL, 포지션 복구)은 그대로 남는다 —
  두 자산의 차이는 전부 그쪽에 있고, 그것은 중복이 아니다.

`MultiStreamStage` 는 **먼저 §1.2 를 고친 뒤에** 채택 대상이 된다. 지금 상태로
옮기면 모니터가 이미 가진 수정을 잃는다 — 이것이 순서의 유일한 강제 조건이다.

### 3.6 태스크 감독

`run()` 이 `_stop.wait()` 만 기다리는 대신 세 대기 대상을 함께 감시한다:

```python
done, pending = await asyncio.wait(
    {consumer, status, asyncio.create_task(self._stop.wait())},
    return_when=asyncio.FIRST_COMPLETED,
)
```

소비 태스크가 예외로 끝나면 즉시 그것이 `done` 에 들어오고, 예외를 **회수해서 로그로
남긴 뒤** 프로세스를 종료한다. 컨테이너 재시작 정책이 되살리고, `RestartCount` 가
올라가므로 헬스체크와 사람 모두에게 보인다. 조용히 눈먼 채 살아 있는 것보다 낫다.

## 4. 순서와 위험

| # | 작업 | 위험 | 비고 |
| --- | --- | --- | --- |
| 1 | `stage.py` 4곳에 #741 3분기 규칙 적용 | **중** — 라이브 5개 서비스의 핫 루프 | 단독 PR. #741 의 테스트/뮤테이션을 그대로 이식. |
| 2 | 하트비트 + 메트릭 + 알림 규칙 | 낮 | 순수 추가. `run()` 안에서 발화(§3.1). **소비자 전용** — 생산자는 2b. |
| 2b | 생산자 평가 루프의 생존 발화 | 낮 | §2.1. `decision_engine` 쪽이며 `stage.py` 와 무관하다. 이것이 서기 전까지 #750 은 생산자를 신선도 채점에서 이름으로 면제한다. |
| 3 | `config/f9_observation.yaml` `liveness` 분리 | 낮 | #750 머지 후. 생산자 면제 해제도 여기서. |
| 4 | 모니터 2대 → `MultiStreamStage` | **높** — 도메인 로직 재배선 | 단독 PR. 1·2 가 먼저 머지된 뒤. |
| 5 | 태스크 감독(§3.6) | 중 | 4 와 같은 PR 이 자연스럽다. |

각 단계는 별도 브랜치·PR·리뷰. 1·2 는 병렬 가능, 4 는 반드시 그 뒤.

**되돌리기**: 1~3 은 순수 가산이거나 국소적이라 revert 가 안전하다. 4 는 두 데몬의
동작을 바꾸므로 paper 에서 한 세션 관측한 뒤 판단한다 (paper = VirtualBroker,
실주문 0 이므로 배포 자체의 위험은 낮다 — `paper-mode-low-caution`).

## 5. 검증

- 단계 1: #741 이 쓴 뮤테이션 5종을 `stage.py` 대상으로 재현. 특히 *"전부 EXISTED
  일 때 백오프를 건너뛴다"* 를 되살리면 테스트가 깨져야 한다.
- 단계 2: 유휴 루프만 도는 픽스처에서 `heartbeat_interval_seconds` 경과 후
  `stream_consumer_alive` 가 정확히 1회 나오는지, 그리고 rate limit 이 동작하는지.
- 단계 4: **프로덕션 실증**. #739 때와 같은 방식 — 빈 섀도 스트림(`xlen=0`,
  `pending=0` 를 **먼저 확인**)에 `XGROUP DESTROY` 로 NOGROUP 을 유도하고 같은 초에
  복구가 뜨는지, `monitor_stream_read_error` 가 0인지 본다. 재배포만으로는 검증
  불가다 — 기동 경로가 그룹을 다시 만들어 NOGROUP 자체가 안 난다.
- 단계 4 추가: `xack` 실패를 주입해 소비 태스크를 죽이고, §3.6 이 **프로세스를
  종료**시키는지 확인 (현재는 무음으로 계속 산다).

## 6. 하지 않는 것

- 로그 수집 파이프라인(Loki/promtail) 도입 — 범위 밖.
- `MultiStreamStage` 삭제. 사용자가 0명이지만 이 계획의 채택 대상이다. 단계 4 가
  무산되면 그때 #752 처럼 은퇴를 재론한다.
- 모니터의 도메인 로직 통합. 선물(승수·계약·setup_type)과 주식(수수료율·signal_id
  상관·strategy/name)의 차이는 실질이고, 억지로 합치면 자산별 코드가 `shared/` 로
  새어 들어간다 — CLAUDE.md 가 금지하는 방향이다.
