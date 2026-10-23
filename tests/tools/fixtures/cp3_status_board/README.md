# tos_status_board fixture

`tests/tools/test_cp3_status_board.py` 가 쓰는 녹화 픽스처. 2026-10-23 10:46 KST 에 실제 상태
디렉터리(`~/.local/state/tos`)를 **읽기 전용**으로 열어 잘라 냈다.

- `state/` — 상태 루트의 축소판. 세션 4개(`long-20261015` ABORT + B3 · `long-20261022` 정상 종료 ·
  `long-20261023`/`short-20261023` 진행 중), 상주 paper 세션 2개, 크론 로그 끝줄.
  - `session.log` 는 생산자 summary 의 `futures/minute/…` 해시 줄만 뺐다. `journal.jsonl` 은 앞 20줄.
  - `producer-summary.json` 은 `market_sha256` 을, paper `report.json` 은 `samples` 를 뺐다.
  - `config/release.yaml` 은 `expected_code_digest:` 한 줄만 남겼다. B3 `summary.json` 은 상태판이
    읽는 키만 남겼다.
  - paper-ops pid 는 가짜 값(424201/424202)이다 — 테스트가 가짜 `/proc` 를 만든다.
- `stores/<leaf>/*.sql.gz` — 데이터 잎 세 저장소(evidence · inbox · marketfeed)의 SQL 덤프
  (`PRAGMA user_version` 포함). 날짜마다 처음 2틱 · 모든 NO_OUTCOME 틱 · PROPOSAL 2틱 · 마지막 1틱과
  그 틱들의 evidence seq 괄호 `(handling_started, consumed]` 안의 행, 그리고 `VENUE_BAND_OBSERVED` 행만
  남겼다. `TIME_HEALTH_SNAPSHOT` 은 상태판이 읽지 않아 뺐다.

마스킹: 상태 루트 경로 → `{STATE_DIR}`(테스트가 tmp 경로로 치환), `/home/deploy` → `/home/operator`,
모의 계좌번호 → `0000000000`. 행의 `entry_digest`/`chain_digest` 는 마스킹 전 바이트에 대한 값이라
재계산하면 맞지 않는다 — 상태판과 `session_inputs` 는 체인을 검증하지 않는다.
