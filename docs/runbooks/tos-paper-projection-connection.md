# Paper operator projection 출력 연결

2026-10-06. CP-1 #861. 커널·거래 설정·durable set·cron은 변경하지 않는다.

## 연결 좌표

| 구간 | 설정 |
|---|---|
| host wrapper | `TOS_PAPER_PROJECTION_PATH` (기본 아래 파일) |
| producer 파일 | `/home/deploy/.local/state/tos/paper-projection/operator_projection.json` |
| Compose host directory | `TOS_OPERATOR_PROJECTION_DIR=/home/deploy/.local/state/tos/paper-projection` |
| dashboard 파일 | `TOS_OPERATOR_PROJECTION_PATH=/app/data/tos_runtime/operator_projection.json` |
| consumer | 인증된 `GET /api/tos/projection` → `/tos` |

host 사용자와 dashboard appuser는 모두 uid/gid 1000이다. 전용 디렉터리는
0700, producer는 기존 umask 077을 상속한다. dashboard에는 디렉터리를 `:ro`로
마운트한다. 기존 `data/tos_runtime`은 root 소유라 producer 쓰기 대상으로 사용하지 않는다.
파일 단독 bind는 atomic replace 이후 갱신을 보지 못하므로 사용하지 않는다.

## 재현 가능한 host 변경

비버전 host script 전체를 복제하지 않고 [정확한 패치](patches/tos-paper-projection.patch)를
버전 관리한다. 적용 전 preimage SHA-256과 정지 상태를 확인한다.

- `tos-paper-session.sh`: `fd554b2a3c1496d26c70dcce414ae529fec81f89abc131e41f7b4046aa0ab763`
- `tos_paper_session.py`: `21b583bdb72b178d1b1f568df78fc4dd5cd788dce893a086e634cd726665fe11`

스크립트를 private backup으로 복사하고 staging copy에 `git apply --check` 및
`git apply`를 수행한다. 적용한 사본에 다음 검증을 실행한다.

```bash
python scripts/tos/check_paper_projection_wiring.py /path/to/staged/scripts
```

검증은 path selection과 자식 CLI 인자만 확인한다. subprocess와 renderer는
대체되며 broker/runtime/알림은 실행하지 않는다. 추출 범위는 두 센티널
(`# Test/override sessions` · `GENESIS=no`)이 각각 정확히 한 번 나올 때만
성립하며, 하나라도 사라지면 스크립트는 운영 wrapper 전체를 실행하는 대신
`FAIL`로 멈춘다. 절대경로 가드는 상대 경로 사례 하나로 직접 밟아 확인하며, `abort`는 stub이
아니라 **래퍼 자신의 정의를 추출**해 쓴다(래퍼에서 `abort()`가 사라지면 FAIL;
종료코드 2와 메시지도 래퍼 것으로 단언한다). 일곱 선택 사례는 `PROJECTION_PATH`를
주입하므로 래퍼의 **기본값 상수**는 별도 사례로 본다 — 절대경로인지,
`operator_projection.json`으로 끝나는지, 세션 로컬이 아닌지,
`TOS_PAPER_PROJECTION_PATH`가 이기는지. 모든 판정은 예외로 올리므로
`python -O`에서도 무력화되지 않는다. 운영 설치는 정지 상태와 preimage를
다시 확인한 뒤 mode 0700으로 두 파일을 교체한다.

일반 실행은 기존 CLI `--projection-path`를 사용한다. selftest 또는 data-dir,
instrument, fake-date, worktree, calendar 우회가 설정된 세션은 무조건 session-local
파일로 출력한다. 명시적 projection override도 이 격리를 우회하지 못한다.
직접 driver를 호출할 때 projection 옵션을 생략하면 이전 동작을 유지한다.

## 적용·확인·복구

1. host 전용 디렉터리를 deploy 소유 0700으로 만든다.
2. `.env.paper`에 위 두 Compose 변수만 설정한다. 파일 내용이나 credential은 출력·커밋하지 않는다.
3. #861 코드로 `scripts/deploy_paper.sh --services "dashboard strategy-builder-ui" --no-cleanup -y`를
   실행한다. main 경로에서 실행해 기존 상대 경로 volume이 다른 worktree를 가리키지 않게 한다.
4. 실제 producer가 아직 실행되지 않았다면 `available=false`가 올바른 상태다.
   fixture를 운영 파일에 쓰거나 장 마감 후 검증용 거래 세션을 시작하지 않는다.
5. 다음 정상 paper 세션에서 projection generation 증가, API 값, UI freshness를 대조한다.
   종료 뒤 stale 전환, 재시작 후 generation/runtime identity 변화를 확인한다.
   이 관측 전에는 실제 세션 end-to-end 검증 완료로 표시하지 않는다.

복구: 정지 상태에서 backup wrapper/driver를 복원하고 조회 서비스의 이전 배포와
두 env 설정을 복원한다. runtime DB·custody·authority는 복구 대상이 아니다.

## 리뷰 상태

Claude 독립 리뷰를 요청했으나 주간 token 한도로 실행 불가. 사용자가 해당 제한을
확인했다. 독립 승인으로 기록하지 않는다. 작성자 자체 점검에서 invalid UTF-8의
500 응답, atomic replace 동안 age/content 세대 불일치, 미래 mtime의 잘못된 recent
표시를 수정하고 회귀 테스트 3개를 추가했다. 최종 코드 `bb394cb1`의 모든 CI가 통과했고 #861은 main `af43fd8a`에 병합됐다.
조회 서비스 배포 및 실제 브라우저 검증은 [배포 기록](../testing/2026-10-06-tos-control-plane.md)에 있다.
다음 정상 paper 세션의 실제 출력 갱신 관측은 남아 있다.
