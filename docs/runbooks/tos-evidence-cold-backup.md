# TOS 증거 콜드 백업 런북 — 설정 → 실행 → 검증 → 예약

- 대상: 증거 저장소를 포함한 durable set 다섯 파일의 **검증된 압축 콜드 사본**을 장 마감 뒤 쌓는다.
- 계획: `docs/plans/2026-09-29-tos-evidence-growth-and-purge-plan.md` §2 A3 ·
  운영자 처분 §6.1-1(2026-09-29 「트랙 A = A1 · A2 · A3 모두 착수」) · 착지 §7.1.18.
- 진입점: `tos_runtime` compose CLI 의 `cold-backup` 하위 명령.
- 관련 런북: `docs/runbooks/tos-paper-boot.md` §4-B(수동 1회성 `backup-set --archive-dir`) ·
  §4-A(증거 스키마 v1 → v2 마이그레이션).

## 0. 무엇이고 무엇이 아닌가

- **아무것도 지우지 않는다.** 라이브 파일도, 비압축 백업 트리도 **읽기만** 한다. 디스크는
  줄지 않는다. 쌓이는 것은 트랙 B 가 언젠가 지울 때 전제가 되는 **검증된 원본 사본**이다
  (ADR-002-016 §17 「independently verified snapshot … raw material」).
- **보존(retention) 손잡이가 없다. 누락이 아니라 결정이다.** `backup_set` 은 삭제하지 않고
  (「Never deleted, never overwritten」), 아카이브는 추가이며, **검증된 콜드 사본을 지우는
  것은 트랙 B** 다(계획 §4 — 전제 B-1…B-5 전부 미충족). 용량이 차면 답은 저장공간이지
  삭제 잡이 아니다(§6).
- **「압축했지만 검증 안 된」 상태는 만들어지지 않는다.** 모든 아카이브는 쓴 직후 되읽어
  압축 해제 → 매니페스트 동일성 → 파일별 digest 대조 → 증거 체인 `verify_or_raise` 까지
  통과해야 최종 이름을 얻는다. 실패하면 `.partial` 을 지우고 종료코드 1 로 끝난다.
- **`backup-set` 은 그대로다.** 대화형 1회성 백업은 종전과 동일하게 쓴다(`tos-paper-boot.md`
  §4-B). `cold-backup` 은 그 위에 **설정 기반 좌표 + 자동 세대 + 용량 바닥 + 보고서**를
  얹어 **무인 실행(cron)** 이 가능하게 만든 문이다.

## 1. 전제

1. **런타임이 정지해 있을 것.** `backup_set` 은 다른 프로세스가 연 sqlite 핸들을
   **기계적으로 탐지하지 못한다**(그 함수의 문서화된 전제). cron 으로 돌린다면 그 시각에
   `run` 이 떠 있지 않다는 것을 운영자가 보장해야 한다(§5).
2. **커스터디 루트.** 아카이브의 증거 체인 재검증이 서명 키를 읽는다. 준비는
   `tos-paper-boot.md` §1 과 동일하다.
3. **설정 파일 하나**(§2).
4. **분리 워크트리와 래퍼**(§4-2 · §4-3). 손으로 한 번 돌릴 때도 필요하다 — 이 명령은
   공용 체크아웃에서 돌리지 않는다(§4-1). 번호가 뒤에 있을 뿐 §3 보다 **먼저** 만든다.

## 2. 설정 — `evidence_cold_backup.yaml`

템플릿은 `tos/runtime/config/evidence_cold_backup.example.yaml`, paper 승인 사본은
`config/tos_runtime/paper/evidence_cold_backup.yaml` 이고 **세 경로가 전부 `null`** 이다.
호스트 좌표라 저장소가 알 수 없기 때문이고, 로더는 null 을 기본값으로 메우지 않고
**거부한다** — 짐작한 보관 경로는 콜드 백업이 없는 것보다 나쁘다. 있는 것처럼 보이기 때문이다.

채운 파일은 **저장소 밖**에 둔다. 권장 위치는 커스터디 옆이다:

⚠ **이 호스트에는 그 파일이 이미 채워진 채 있다**(`~/.local/state/tos/paper-ops/evidence_cold_backup.yaml`,
2026-10-03 · §4-5-1). 아래 `cat >` 를 그대로 붙여넣으면 **그것을 덮어쓴다** — 새 호스트를
세울 때의 예시로 읽고, 이 호스트에서는 값만 비교한다.

```bash
OPS=~/.local/state/tos/paper-ops          # 저장소 밖 · 호스트 로컬
mkdir -p "$OPS"
cat > "$OPS/evidence_cold_backup.yaml" <<'YAML'
backup_root: /home/deploy/.local/state/tos/paper-backups
archive_dir: /home/deploy/.local/state/tos/paper-cold
verify_root: /home/deploy/.local/state/tos/paper-verify
minimum_free_bytes: 53687091200     # 50 GiB — 이 호스트의 실제 여유로 정할 것
# xz_preset: 6                      # 생략 = DEFAULT_XZ_PRESET(6)
YAML
```

- ⛔ **렌더된 설정 디렉터리(`~/.config/tos/paper-config`)에 두지 않는다.**
  `scripts/tos/render_paper_config.py` 는 재렌더 때 그 디렉터리를 저장소 사본으로 **다시
  만든다** — 손으로 채운 값이 사라진다. `--config-dir` 는 그냥 이 운영 디렉터리를 가리킨다.
  이 파일이 이제 그 스크립트의 **원본 트리에 있으므로** 되돌림은 가설이 아니라 확정이고,
  `--check` 도 함께 깨진다 — 근거는 §4-5-1.
- **절대경로만.** `~` 전개도, 상대경로 해석도, 환경변수 치환도 하지 않는다. 전개를 하면
  보관 위치가 「누가 cron 을 돌렸는가」에 달린다.
- 세 경로 전부 **git 워크트리 안 · 라이브 `--data-dir` 안 · 그 위쪽**이면 거부된다.
  마지막 조건이 있는 이유: 콜드 보관소는 무한히 자라는데(보존 없음) 라이브 런타임과 같은
  서브트리를 쓰면 보관소가 차는 순간 런타임까지 같이 죽는다.
- `backup_root` 는 `backup-set --dest` 가 쓰고 `run --backup-root` 가 부팅 때 관측하는 그
  트리와 **같은 디렉터리**를 가리켜야 한다 — 세대 번호를 거기서 읽는다.
- 세 경로는 서로 **같거나 중첩될 수 없다**(같은 부모를 공유하는 것은 괜찮다). 중첩하면
  매체 분리가 조용히 무효가 되기 때문이다.
- `minimum_free_bytes` 는 **용량 경보**(계획 §5)다. **셋 모두**에 적용된다 — 같은 장치에
  얹힌 경로는 하나로 묶어 한 번만 센다. `archive_dir` 만 보면 **가장 빨리 자라는 트리**
  (`backup_root`, 비압축)를 놓친다. 기본값이 없다 — 승인되지 않은 한도를 결정된 값처럼
  적지 않는다. 0 도 거부한다(바닥이 아니라 경보를 끄는 값이다). 증가율은 계획 §1 실측으로
  원본 ≈200 MB/일 · 압축 뒤 ≈13 MB/일이다.

## 3. 실행

⛔ **공용 체크아웃(`/home/deploy/project/kis_unified_sts`)에서 돌리지 않는다.** 손으로 한 번
돌릴 때도 마찬가지다 — 병렬 레인이 그 체크아웃의 브랜치를 수시로 바꾸므로, 실 paper durable
set 과 커스터디 키를 **리뷰 전 코드**로 건드리게 된다(이유는 §4-1, 선례는 #793). 먼저 §4-2 의
분리 워크트리를 만들고, 그 다음 **§4-3 의 래퍼를 직접 실행**한다:

```bash
~/.local/state/tos/ops/cold-backup.sh
```

래퍼가 워크트리의 detached·clean 상태를 확인하고 커밋 SHA 를 찍은 뒤 실제 명령을 돈다.
좌표를 바꿔 한 번만 다르게 돌려야 한다면 래퍼를 복사해 고치고, **`cd` 대상은 여전히
워크트리**로 둔다:

```bash
WT=~/.local/state/tos/ops-worktree
cd "$WT"
PYTHONPATH="$WT/tos/src:$WT/tos/runtime/src" \
  /home/deploy/project/kis_unified_sts/.venv/bin/python -c \
  'import sys;from tos_runtime.compose.cli import main;sys.exit(main(sys.argv[1:]))' \
  cold-backup \
  --data-dir ~/.local/state/tos/paper-data \
  --config-dir ~/.local/state/tos/paper-ops \
  --custody-root ~/.local/state/tos/paper-custody
```

(인터프리터는 기본 체크아웃의 `.venv` 지만 `PYTHONPATH` 가 **절대경로로 워크트리**를 가리킨다
— 그러지 않으면 코드가 어느 트리에서 왔는지 알 수 없다.)

성공 출력은 stdout 한 줄이고 **모양**은 이렇다 — 아래 숫자와 멤버 수는 **실측이 아니라
자리표시자**다(바이트는 데이터에, 멤버 수는 그 data dir 에 `composite_state`/`marketfeed` 가
있는지에 달린다. §7.1.4 의 실 커스터디 왕복에서는 멤버가 **4** 였다 — 그 런타임이 composite 를
한 번도 쓰지 않았기 때문이다):

```
cold-backup: archived gen1 to <archive_dir>/gen1.set.tar.xz (<N> -> <M> bytes),
             read back and verified: <K> file digest(s) + evidence chain; report at
             <archive_dir>/gen1.cold-backup.report.json
```

- **세대는 자동이다.** `backup_root` 의 최고 세대 다음을 쓴다. 그래서 N 번째 cron 실행의
  명령줄이 첫 번째와 **글자 그대로 같다**(`backup-set` 은 `--generation` 을 손으로 올려야 했다).
- 보고서 `gen{N}.cold-backup.report.json` 이 아카이브 옆에 남는다. 세대·경로·압축 전후
  바이트·검증된 멤버 목록·체인 검증 여부·**파일시스템별 여유 공간(전/후, 장치 단위로 묶음)**·
  용량 바닥·바닥 미만 여부를 적는다.
- **보고서는 증거 행이 아니다.** 라이브 저장소는 닫혀 있어야 하고 바이트가 움직이면 안 되므로
  이 명령은 증거 체인에 append 하지 않는다. 운영 사실이 증거로 들어가는 기존 경로는
  **부팅 시 관측**(`compose/_operations_wiring._observe_backup` → `BACKUP_SET_OBSERVED`)
  하나뿐이고, 그 관측기에게 이 보고서까지 읽히는 것은 후속 과제로 등재했다(계획 §7.1.18).

## 4. 예약 — cron (데몬 없음 · **분리 워크트리에서만**)

데몬을 추가하지 않았다. 이 명령은 라이브 디렉터리에서 아무것도 열지 않고, 아무것도 붙들지
않으며, 끝나면 종료한다. 필요한 것은 crontab 한 줄이다 — 다만 **공용 체크아웃에서 돌리면
안 된다.**

### 4-1. 왜 공용 체크아웃이면 안 되는가

이 호스트의 공용 체크아웃(`/home/deploy/project/kis_unified_sts`)은 **병렬 레인이 수시로
브랜치를 바꾼다.** 17:50 에 어떤 레인이 피처 브랜치로 바꿔 두면 18:00 의 cron 은 **그
브랜치의 리뷰 전 코드**로 실 paper durable set 과 커스터디 키를 건드린다. 같은 규칙이 이미
프로브에 적용돼 있다 — `tools/broker_probes/runners/run_p_ca.sh` 와 프로젝트 메모리
「프로브는 분리 워크트리(origin/main)에서만」(#793 HIGH). 무인 실행은 프로브보다 더
그렇다: 아무도 보고 있지 않다.

### 4-2. 운영 워크트리 하나 만들기 (1회)

⛔ **2026-10-03 로 대체됨 — 실제 래퍼·cron 줄은 §4-5-3·§4-5-4 다.** 아래 §4-3 의 래퍼
(`~/.local/state/tos/ops/cold-backup.sh`)와 §4-2 의 워크트리(`~/.local/state/tos/ops-worktree`)는
**이 호스트에 만들지 않았다.** 아래 §4-4 의 cron 줄을 그대로 넣으면 없는 파일을 불러
**종료코드 127 로 조용히** 끝난다(리다이렉트가 그 줄마저 로그로 보낸다). 둘 다 cron 에
넣지 말 것 — §4-3 쪽 래퍼에는 **flock 도 텔레그램 경로도 없다.** 아래 세 절은 설계 근거
(왜 분리 워크트리인가 · 왜 가드가 cron 줄이 아니라 래퍼에 있는가)로 읽는다.

```bash
WT=~/.local/state/tos/ops-worktree
git -C /home/deploy/project/kis_unified_sts fetch -q origin
git -C /home/deploy/project/kis_unified_sts worktree add --detach "$WT" origin/main
```

- **detach 다.** 브랜치가 아니므로 누가 체크아웃을 옮겨도 이 트리는 움직이지 않는다.
- **`.venv` 는 만들지 않는다.** 분리 워크트리에 설치하지 않는 것이 이 저장소의 규율이고,
  인터프리터는 기본 체크아웃의 `.venv` 를 쓴다(아래 래퍼가 `PYTHONPATH` 로 **코드는
  워크트리에서** 읽게 강제한다 — 같은 함정을 `run_p_ca.sh` 가 이미 다룬다).
- 갱신은 **의도적으로만**: `git -C "$WT" fetch -q origin && git -C "$WT" checkout -q --detach origin/main`.
  오래된 채로 두는 것은 결함이 아니다 — 무인 작업이 리뷰된 코드에 고정돼 있다는 뜻이다.

### 4-3. 래퍼 (가드가 cron 줄이 아니라 여기에 있다)

⛔ **2026-10-03 로 대체됨 — 실제 래퍼·cron 줄은 §4-5-3·§4-5-4 다.** 아래 §4-3 의 래퍼
(`~/.local/state/tos/ops/cold-backup.sh`)와 §4-2 의 워크트리(`~/.local/state/tos/ops-worktree`)는
**이 호스트에 만들지 않았다.** 아래 §4-4 의 cron 줄을 그대로 넣으면 없는 파일을 불러
**종료코드 127 로 조용히** 끝난다(리다이렉트가 그 줄마저 로그로 보낸다). 둘 다 cron 에
넣지 말 것 — §4-3 쪽 래퍼에는 **flock 도 텔레그램 경로도 없다.** 아래 세 절은 설계 근거
(왜 분리 워크트리인가 · 왜 가드가 cron 줄이 아니라 래퍼에 있는가)로 읽는다.

```bash
cat > ~/.local/state/tos/ops/cold-backup.sh <<'SH'
#!/bin/sh
set -eu
WT=$HOME/.local/state/tos/ops-worktree
PY=/home/deploy/project/kis_unified_sts/.venv/bin/python   # 기본 체크아웃의 인터프리터

# 분리 상태가 아니면(= 브랜치 위면) 돌지 않는다. `symbolic-ref -q HEAD` 는 브랜치에서
# 성공하고 detached 에서 실패한다.
if git -C "$WT" symbolic-ref -q HEAD >/dev/null; then
  echo "cold-backup: refusing — $WT is on a branch, not detached" >&2; exit 1
fi
if [ -n "$(git -C "$WT" status --short)" ]; then
  echo "cold-backup: refusing — $WT is dirty" >&2; exit 1
fi
echo "cold-backup: worktree $WT at $(git -C "$WT" rev-parse HEAD)"

cd "$WT"
PYTHONPATH="$WT/tos/src:$WT/tos/runtime/src" "$PY" -c \
  'import sys;from tos_runtime.compose.cli import main;sys.exit(main(sys.argv[1:]))' \
  cold-backup \
  --data-dir "$HOME/.local/state/tos/paper-data" \
  --config-dir "$HOME/.local/state/tos/paper-ops" \
  --custody-root "$HOME/.local/state/tos/paper-custody"
SH
chmod 700 ~/.local/state/tos/ops/cold-backup.sh
```

`PYTHONPATH` 가 **절대경로로 워크트리를 가리킨다** — 인터프리터는 다른 트리에서 오므로,
그러지 않으면 가드가 「검증한」 트리와 **실제로 실행된 코드**가 달라질 수 있다
(`run_p_ca.sh` 의 같은 함정 주석 참조). 워크트리 커밋 SHA 를 매 실행 첫 줄에 찍는 것은
**기록**이고, 앞의 두 거부가 **방지**다.

### 4-4. crontab

⛔ **2026-10-03 로 대체됨 — 실제 래퍼·cron 줄은 §4-5-3·§4-5-4 다.** 아래 §4-3 의 래퍼
(`~/.local/state/tos/ops/cold-backup.sh`)와 §4-2 의 워크트리(`~/.local/state/tos/ops-worktree`)는
**이 호스트에 만들지 않았다.** 아래 §4-4 의 cron 줄을 그대로 넣으면 없는 파일을 불러
**종료코드 127 로 조용히** 끝난다(리다이렉트가 그 줄마저 로그로 보낸다). 둘 다 cron 에
넣지 말 것 — §4-3 쪽 래퍼에는 **flock 도 텔레그램 경로도 없다.** 아래 세 절은 설계 근거
(왜 분리 워크트리인가 · 왜 가드가 cron 줄이 아니라 래퍼에 있는가)로 읽는다.

```cron
CRON_TZ=Asia/Seoul
# 평일 18:00 KST — 런타임을 정지시킨 뒤에 돈다(§1 전제 1).
0 18 * * 1-5 $HOME/.local/state/tos/ops/cold-backup.sh >> $HOME/.local/state/tos/cold-backup.log 2>&1
```

- `CRON_TZ=Asia/Seoul` 는 이 저장소의 비협상 규칙이다(전역 메모리 「Cron 은 CRON_TZ=Asia/Seoul」).
- **시각은 「장 마감 뒤」가 아니라 「런타임 정지 뒤」로 고른다.** 선물 주간 세션은 15:45 KST 에
  끝나지만, 중요한 것은 sqlite 핸들이 전부 닫혔는가다. 18:00 은 그 여유를 둔 값이고,
  정지 절차가 바뀌면 이 줄도 같이 바꾼다. 런타임이 아직 떠 있으면 스냅숏이
  `snapshot failed — OperationalError: database is locked` 한 줄로 끝난다(§5) — 조용히
  반쪽짜리 백업을 만들지 않는다.
- 종료코드 0 = 아카이브가 존재하고 되읽혔고 전 멤버 digest 가 매니페스트와 일치했고 증거
  체인이 재검증됐다. 그 밖은 1 이고 stderr **한 줄**이 어느 단계에서 무엇이 일어났는지
  말한다(§5). **traceback 은 나오지 않는다.**

## 4-5. 활성화 준비 상태 — 2026-10-03

운영자 결정 두 개(용량 바닥 · 대상 data dir)가 2026-10-03 에 들어왔다. **남은 것은 둘이다** —
crontab 한 줄(운영자)과 2026-10-06 genesis(ops-paper 레인). 이 절은 호스트에 무엇이 있고,
켜는 데 무엇이 남았고, 사본에서 무엇을 확인했는지의 기록이다.

### 4-5-1. 호스트에 있는 것

| 무엇 | 경로 | 모드 | 상태 |
|---|---|---|---|
| 인스턴스 설정 | `~/.local/state/tos/paper-ops/evidence_cold_backup.yaml` | `600` | 세 경로 + **바닥 53687091200** 채움 |
| 비압축 세대 | `~/.local/state/tos/paper-cold/backups` | `700` | 빈 디렉터리 |
| 콜드 보관소 | `~/.local/state/tos/paper-cold/archives` | `700` | 빈 디렉터리 |
| 검증 스크래치 | `~/.local/state/tos/paper-cold/verify` | `700` | 빈 디렉터리 |
| **커스터디 루트** | `~/.local/state/tos/paper-custody` | `700` | `evidence.key` · `evidence.key.1`(둘 다 `600`) — **세대 1**. 없으면 프리플라이트가 `custody refused` 로 끊는다 |
| **락 파일** | `~/.config/kis-probes/cold-backup-nightly.lock` | `644` | 존재(0 B). `flock -n` 의 대상이고 내용은 쓰지 않는다 |
| **통지 자격증명** | `/home/deploy/project/kis_unified_sts/.env` 의 `TELEGRAM_BRIEFING_BOT_TOKEN` · `TELEGRAM_BRIEFING_CHAT_ID` | — | 래퍼가 **그 두 줄만** 읽는다. 없으면 실행은 계속되고 통지만 빠진다(로그에 한 줄) |
| 분리 워크트리 | `~/.local/state/tos/measure/wt-cold` | — | detached `origin/main` |
| 야간 래퍼 | `~/.config/kis-probes/cold-backup-nightly.sh` | `700` | **crontab 미등재** · sha256 `248b284c1e236f518c60a17526839fce35c3095d32d60074662a1ad3e494d576` |
| 래퍼 로그 | `~/.local/state/tos/cold-backup.log` | — | 아직 없음(래퍼가 소유) |
| cron 로그 | `~/.local/state/tos/cold-backup.cron.log` | — | 아직 없음. **비어 있는 것이 정상**(§4-5-3) |
| 증명 로그·보고서 | `~/.local/state/tos/measure/cold-a3/` | `700` | `selftest-20261003.log` + `gen{1..4}.cold-backup.report.json` (§4-5-5) |
| 대상 data dir | `~/.local/state/tos/paper-data` | — | **아직 없다** — 2026-10-06 genesis 예정 |
| ⛔ **이것이 아니다** | `~/.config/tos/paper-config/evidence_cold_backup.yaml` | `644` | 렌더가 만든 **all-null 쌍둥이**(저장소 템플릿과 바이트 동일, 2026-10-03 13:55 재렌더). 로더가 둘을 구별하는 수단은 **`--config-dir` 하나뿐**이다 |

래퍼의 첫 줄이 찍는 sha256 은 위 표의 값과 대조하라고 있는 것이다 — 값이 다르면 호스트
파일이 이 문서보다 새것이거나 그 반대다.

⛔ **설정은 `~/.config/tos/paper-config` 에 두지 않았다 — 인스턴스를 2026-10-03 에
`paper-ops` 에 둔 이유가 그것이다.** §2 가 **금지한** 바이고, #840 이후로는 근거가 하나 더
구체적이다 — `evidence_cold_backup.yaml` 이 이제 `scripts/tos/render_paper_config.py` 의
**원본 트리**(`config/tos_runtime/paper/`)에 있다. 위 표의 마지막 행이 그 결과이고, 그
디렉터리에 손으로 채운 파일을 두면 두 가지가 **조용히** 일어난다:

1. 재렌더가 디렉터리를 통째로 갈아끼운다(`_publish` 가 이전 렌더를 옆으로 옮긴 뒤
   `rmtree` 한다). 채운 값이 저장소의 all-null 사본으로 **되돌아가고**, 그 다음 cron 은
   「`minimum_free_bytes` is still null」로 거부한다 — 아무도 아무것도 바꾸지 않았는데.
2. `--check` 는 렌더 디렉터리를 원본과 줄 단위로 대조한다. 채운 줄은 `replace` 훅이면
   `…: changed line is not a registered coordinate slot (…)`, 순수 삽입·삭제면
   `…: line(s) N-M changed outside any coordinate slot (insert)` 로 **두 형태 중 하나**가
   된다. 원본에 없는 파일로 허용되는 것은 `bootproof_journal.jsonl` 과 `RENDERED.json`
   둘뿐이다.

로더는 어느 경로도 하드코딩하지 않는다 — `<--config-dir>/evidence_cold_backup.yaml` 을
읽을 뿐이므로 위치는 순전히 래퍼의 인자이고, 래퍼의 `COLD_CONFIG_DIR` 기본값이
`paper-ops` 를 가리킨다.

⚠ **단일 장치 배치 — 기록해 둔다.** 세 보관 경로와 (아직 없는) 라이브 data dir 이 **전부
같은 파일시스템**(`/dev/sdd`, 마운트 `/`)에 있다. 두 가지 대가가 따른다:

- `_free_space` 는 `st_dev` 로 묶으므로 세 루트의 바닥 검사가 **한 번의 측정**으로
  축약된다(보고서의 `free_space_*` 항목이 하나뿐인 이유다). 세 개의 독립된 여유처럼
  읽지 말 것.
- §6 이 권하는 조치 「오래된 아카이브를 **다른 매체로** 옮긴다」에 쓸 **매체가 지금은
  없다.** 바닥이 울리면 이 호스트에서 할 수 있는 것은 저장공간을 늘리는 쪽뿐이다.
  이 이탈은 계획 **§7.1.26 A3-F2** 에 등재했다.

여유 공간(측정값은 명령과 시각을 붙여 적는다):

```
$ df -B1 /home/deploy          # 2026-10-03 14:15:52 KST
/dev/sdd  1081101176832  668870635520  357238185984  66%  /
```

바닥 53687091200 B 까지의 여유는 ≈283 GiB 다. 한 번의 실행이 쓰는 양은 §4-5-5 의 실측으로
**7,630,848 ~ 7,651,328 B**(할당 기준, 보고서의 `free_space_before − free_space_after`)다.
그 수로 나눈 나눗셈은 **적지 않는다** — 1회성 corpus 한 벌(7 MB)을 반복해 뜬 수치라서
상주 런타임의 증가율(계획 §1: 원본 ≈200 MB/일)과 다르고, 둘을 곱해 「몇 년」을 만들면
측정하지 않은 것을 측정한 것처럼 적게 된다.

### 4-5-2. 운영자 결정 둘 — 2026-10-03 확정

**(1) `minimum_free_bytes` = 50 GB → `53687091200`.**

**단위 규약: 로더는 바이트 정수만 받는다.** `_require_free_bytes` 는 `int` 가 아니면
거부하고(`bool` 도 거부), `<= 0` 도 거부하며, 값을 `shutil.disk_usage(...).free` 와
**그대로** 비교한다. 접미사도, 단위 문자열도, 실수도 없다. 적힌 `53687091200` 은
**50 GiB**(50 × 1024³)이고 십진 GB 로는 53.69 GB 다 — 운영자 표기 「50 GB」를 GiB 기준으로
적으라는 지시에 따른 것이라 두 수를 설정 파일에도 함께 적어 두었다.

로드된 값 (2026-10-03, `load_cold_backup_config` 실행):

```
backup_root        : /home/deploy/.local/state/tos/paper-cold/backups
archive_dir        : /home/deploy/.local/state/tos/paper-cold/archives
verify_root        : /home/deploy/.local/state/tos/paper-cold/verify
minimum_free_bytes : 53687091200 B  = 50.0 GiB / 53.6870912 GB (decimal)   [type: int]
xz_preset          : 6 (파일에 없음 -> DEFAULT_XZ_PRESET)
```

**(2) 대상 `--data-dir` = `~/.local/state/tos/paper-data` — 상주 paper 런타임.**

그 디렉터리는 **첫 상주 세션의 genesis 가 만든다**(2026-10-06 화 예정, `ops-paper` 레인).
상주 운영 절차는 `docs/runbooks/tos-paper-boot.md` 에 들어간다 — 그 절은 **열려 있는 PR**
위에 있고(이 커밋 시점), 제목과 번호가 리뷰 중에 바뀔 수 있어 여기서는 **파일만** 가리킨다.
genesis 가 증거 저장소를 곧장 v2 로 만들기 때문에 아래 v1 전제는 이 대상에 해당하지 않는다.

⛔ **「런타임이 멎었다」는 이 문서가 보증할 수 있는 것이 아니다 — 운영자의 의무다.**
§1 전제 1 과 §4-4 가 말하는 기준은 「장 마감 뒤」가 아니라 **「런타임 정지 뒤」**이고,
`backup_set` 은 다른 프로세스가 연 sqlite 핸들을 **기계적으로 확인하지 못한다**(그 함수의
문서화된 전제). 상주 런타임은 아직 존재하지 않으므로 「15:45 에 멎는다」는 **계획이지
실측이 아니다.** 18:00 이라는 시각은 그 계획에 **여유를 둔 간격**일 뿐이다:

```
런타임 정지 ~15:45 KST  →  안전 마감 16:00  →  야간 백업 18:00   (여유 ≈2시간 15분)
```

정지 절차나 시각이 바뀌면 cron 줄도 같이 바꾼다. 매일 밤 실제로 닫혔는지는 사람이 본다:

```bash
fuser -v ~/.local/state/tos/paper-data/*.sqlite3     # 비어 있어야 한다
```

래퍼가 같은 검사를 실행 직전에 한 번 돌리지만(§4-5-4), 그것은 **한쪽 방향만** 말한다 —
열려 있는 것이 보이면 멈추고, 조용히 통과하는 것은 **증명이 아니다.** 런타임이 아직
떠 있으면 스냅숏이 `snapshot failed — OperationalError: database is locked` 한 줄로
끝난다(§5) — 조용히 반쪽짜리 백업을 만들지는 않는다.

⚠ **1회성 corpus 를 대상으로 고를 때만 해당하는 전제 — 그대로 남겨 둔다.** 이 호스트의
부팅증명 corpus 12개는 **전부 증거 스키마 v1** 이다(2026-10-03 읽기 전용 전수 조사,
`mode=ro&immutable=1`). `EVIDENCE_SCHEMA_VERSION` 이 2 이므로 아카이브의 체인 재검증이
거부한다:

```
cold-backup: archive failed — SchemaVersionRefused: evidence: on-disk schema user_version=1 is BEHIND this code's schema_version=2 — run the operator `migrate` CLI (tos_runtime.operations.schema_migrations.apply_migrations) before booting; boot never auto-applies a migration
```

그 경우에는 `docs/runbooks/tos-paper-boot.md` 의 `migrate` 절차를 **그 corpus 에** 먼저
돌려야 한다.

⚠ 위 줄에 대해 **두 가지를 기록해 둔다.** ① 접두가 `archive failed` 다 — 예외 이름이
`SchemaVersionRefused` 인데도 `_PASSTHROUGH_REFUSALS` 에 없어 환경 고장으로 분류된다.
조치(마이그레이션)는 §5 의 그 행이 가리키는 쪽과 같지만, 한 단어로는 「호스트가 깨졌다」로
읽힌다. **분류를 고치는 것은 이 PR 의 범위 밖**이라 §5 에 포인터를 달고 계획
§7.1.26 A3-F1 로 후속 등재했다. ② 이때 **비압축 스냅숏은 이미 떠 있다** — 그 세대의 백업은 완전하고,
잃은 것은 압축본뿐이다. 실측에서 `gen1/` 과 매니페스트가 남았고 `.tar.xz` 는 없었으며
`gen1.verify` 가 **남았다**(거부 원인의 증거). 다음 실행은 그 번호를 **건너뛰어** gen2 를
썼다.

### 4-5-3. 남은 것은 둘 — crontab 한 줄과 genesis

설정의 한 줄 편집은 **끝났다**(§4-5-2). 대상도 래퍼의 기본값으로 들어갔다. 남은 것은:

1. **crontab 한 줄** — 운영자가 넣는다. **이 작업은 crontab 을 건드리지 않았다.**
2. **2026-10-06 genesis** — `ops-paper` 레인의 첫 상주 세션이 대상 디렉터리를 만든다.

둘이 다 되면 **첫 실제 아카이브는 2026-10-06(화) 저녁 18:00 KST 실행**에서 나온다.
그 전까지 cron 을 넣어 두어도 되고, 그 밤들은 `PRE-GENESIS` 로 끝난다(§4-5-4).

```cron
CRON_TZ=Asia/Seoul
# 평일 18:00 KST — 상주 런타임 정지(계획 ~15:45) 뒤. 기준은 「장 마감」이 아니라
# 「런타임 정지」다(§1 전제 1 · §4-5-2) — 정지 절차가 바뀌면 이 줄도 같이 바꾼다.
0 18 * * 1-5 $HOME/.config/kis-probes/cold-backup-nightly.sh >> $HOME/.local/state/tos/cold-backup.cron.log 2>&1
```

- 대상이 래퍼의 기본값이라 cron 줄에 `COLD_DATA_DIR` 을 적지 않는다. 다른 트리를 한 번만
  겨눠야 한다면 그때만 줄 앞에 붙인다.
- **종료코드 0 의 이유는 「메일이 쌓이지 않게」가 아니다.** 위 리다이렉트가 stdout·stderr
  를 둘 다 파일로 보내므로 **cron 은 어떤 종료코드에서도 메일을 보내지 않는다** — 끌
  메일이 애초에 없다. 이유는 **종료코드 위생**이다: 「대상이 아직 없다」는 고장이 아니므로
  0 이어야 하고, 그래야 나중에 누가 이 줄을 감시 도구에 물렸을 때 10-06 전의 밤들이
  거짓 경보가 되지 않는다. **경보 경로는 텔레그램 하나뿐**이고(이 cron 줄 아래에서는
  그렇다), 그것이 §4-5-6 의 아침 확인이 필요한 이유다.
- §4-4 의 cron 줄과 **같은 것은 시각뿐이다**(그 절의 ⛔ 참조).

### 4-5-4. 래퍼가 하는 일 (`~/.config/kis-probes/cold-backup-nightly.sh`)

- `flock -n` — 겹치면 뒤에 온 쪽이 기다리지 않고 비켜난다(겹치면 둘이 같은 세대를
  할당받아 하나가 산출물 충돌로 거부된다). **비켜날 때도 텔레그램 한 줄을 보낸다** —
  비켜난 밤은 백업이 돈 밤이 아닌데, 조용히 0 으로 끝내면 「매일 밤 돌고 있다」와
  「매일 밤 비켜나고 있다」가 통지에서 똑같이 생긴다.
- `git fetch` 에 **`timeout 120`** 을 건다. 없으면 매달린 fetch 하나가 락을 쥔 채 남아
  그 다음 밤부터 **매일** SKIP 이 된다 — 한 번의 고장이 일정 전체를 조용히 멈추는 모양이다.
  시간 초과는 `refused` 다.
- `~/.local/state/tos/measure/wt-cold` 를 **detached `origin/main`** 으로 맞춘다. 갈아타기
  **전에** 브랜치 위인지·더티인지 보고(둘 다 거부), 갈아탄 **뒤에** 다시 본다. 매 실행
  첫 줄에 **래퍼 자신의 sha256**(§4-5-1 표와 대조), 둘째 줄에 **워크트리 커밋 SHA** 를
  찍는다. 인터프리터는 주 체크아웃의 `.venv` 지만(`[ -x ]` 로 먼저 확인한다) `PYTHONPATH`
  가 절대경로로 워크트리를 가리킨다(§4-3 의 같은 함정).
  ⚠ §4-2 는 워크트리 갱신을 「의도적으로만」 하라고 적는다. 이 래퍼는 매 실행
  `origin/main` 으로 맞춘다 — 지키려는 것(무인 실행이 리뷰 전 코드에 닿지 않는다)은 같고,
  `origin/main` 을 **명시적으로** 체크아웃하는 쪽이 오래된 채 두는 것보다 강한 보장이다.
- **열린 핸들 검사**를 실행 직전에 한 번 돌린다(`fuser "$DATA_DIR"/*.sqlite3`). 보이면
  `refused`. ⚠ 한쪽 방향만 말하는 검사이고(§4-5-2), `fuser` 가 없는 호스트에서는 **검사를
  돌리지 못했다고 로그에 적고 지나간다** — 못 돌린 검사를 통과로 적지 않는다.
- **대상이 아직 없는 창**: `COLD_DATA_DIR`(기본 `~/.local/state/tos/paper-data`)이 없고
  오늘이 `COLD_TARGET_BORN_ON`(기본 `2026-10-06`) **전**이면 `PRE-GENESIS`, 종료코드 0.
  `BORN_ON` **당일부터** 같은 부재는 `refused`, 종료코드 1 이다. 날짜 경계를 둔 이유:
  「없으면 조용히 0」을 날짜 없이 두면 genesis 이후 대상이 **사라진** 날에도 영원히
  초록으로 끝나 백업이 멈춘 것을 아무도 모른다.
  ⚠ **`COLD_TARGET_BORN_ON` 은 `YYYY-MM-DD` 여야 하고, 아니면 거부된다.** 형식(정규식)과
  달력 유효성(`date -d` 왕복)을 **둘 다** 본다 — `date -d` 혼자서는 `2026/10/06` 를 받아
  정규화해 버리고, 정규식 혼자서는 `2026-02-30` 을 통과시킨다. 검증이 없던 판에서는
  `2026/10/06` · `6-10-2026` · `TBD` 가 모두 오늘보다 「커서」 래퍼를 PRE-GENESIS
  종료코드 0 에 **영구히** 묶었다(§4-5-5 R3).
  대상 자리에 **일반 파일**이 있으면(`[ ! -d ]` 는 그것도 참이다) 「아직 없다」가 아니라
  오타이므로 날짜와 무관하게 `refused` 다.
- 인자는 `--selftest` 하나만 받는다. 그 밖의 인자는 **종료코드 2 로 멈춘다** — 오타 하나가
  진짜 백업을 일으키지 않게.
- **`.env` 에서 `TELEGRAM_BRIEFING_*` 두 줄만** 읽는다(전체 소싱도, 토큰 로깅도 없다).
  보낼 본문은 **보내든 안 보내든** 로그에 한 번 적힌다.
- **자기 자신을 지우지 않고 crontab 에도 손대지 않는다.** 반복 일정이라 disarm 이 없다.
- `COLD_NOTIFY=0` 은 **손으로 돌려 보는 dry 실행 전용**이다. cron 줄은 설정하지 않는다.

결말과 통지 — **다섯 가지이고, 통지가 가는 쪽과 안 가는 쪽을 섞지 않는다**:

| 결말 | 종료코드 | 조건 | 텔레그램 | 줄이 말하는 것 |
|---|---|---|---|---|
| `verdict` | 0 | CLI 가 0 | **보냄** | 아카이브가 존재·되읽힘·전 멤버 digest 일치·체인 재검증. 바닥 경고가 붙어도 **이 백업은 검증됐다** |
| `PRE-GENESIS` | 0 | 대상 부재 · `BORN_ON` 전 | **보냄** | 백업할 것이 없다. 결함이 아니라 일정 |
| `SKIP` | 0 | 락을 다른 실행이 보유 | **보냄** | **이 밤의 백업은 돌지 않았다.** 앞 실행이 매달렸는지 본다 |
| `refused` | 1 | `cold-backup: [<layer> ]refused — …` 또는 래퍼 자신의 거부 | **보냄** | 규칙이 아니라고 했고 **아무것도 쓰지 않았다**. 접두 단어로 §5 를 찾는다. ⛔ 「내일 다시」라고 적지 않는다 — `integrity refused` 는 재실행이 답이 아니다 |
| `failed` | 1 | `cold-backup: <stage> failed — …` | **보냄** | 실행은 적법했고 환경이 무너졌다. 호스트를 고친 뒤 다시 돈다(다음 세대로 간다) |
| `unclassified` | 1 | 위 어느 형태도 아닌 줄 | **보냄** | 래퍼가 모르는 형태다. 못 알아본 줄을 깨끗한 분류로 접어 넣지 않는다 |
| `ABORT` | **2** | 로그 디렉터리 생성 실패 · 락 파일 열기 실패 · mktemp 실패 · 인자 오류 | ⛔ **못 보냄** | 통지 수단 자체를 세우지 못한 경우다. stderr 한 줄이 전부이고 cron 리다이렉트가 그 줄을 `cold-backup.cron.log` 로 보낸다 — **§4-5-6 의 아침 확인이 이것을 잡는 유일한 수단이다** |

통지가 **빠질 수 있는** 두 경우도 적어 둔다: `.env` 의 briefing 두 줄이 없으면 실행은
계속되고 로그에 `notify skipped: briefing credentials not found` 가 남는다. curl 이
실패하면 `telegram notify FAILED` 가 남고 종료코드는 바뀌지 않는다. **둘 다 텔레그램에는
아무것도 가지 않는다** — 그래서 아침 확인이 통지의 대체가 아니라 **짝**이다.

### 4-5-5. 사본에서의 전 구간 증명 (2026-10-03)

**증거 파일**: `~/.local/state/tos/measure/cold-a3/selftest-20261003.log`(192줄) ·
같은 디렉터리의 `gen{1,2,3,4}.cold-backup.report.json`. 아래 표의 「줄」은 그 로그의
행 번호다. 보고서 JSON 에는 증거 내용이 들어가지 않는다 — 경로·바이트·멤버 이름·여유
공간뿐이다.

**사본 뜨는 법과 실 corpus 에 남은 것 — 나누어 적는다.** 대상은
`~/.local/state/tos/realclock-20260928T110001-LONG/data` 이고, 그 런의 `report.json` 이
`started_kst` 2026-09-28 11:00:01 · `ended_kst` 11:15:04 로 적어 둔 corpus 다. 사본은
WAL 조건에 기대지 않는 관용구로 떴다:

```bash
sqlite3 "file:$CORPUS/$f.sqlite3?mode=ro" ".backup '$COPY/$f.sqlite3'"
```

- **본체 네 파일은 바뀌지 않았다 — 해시로 증명된다.** 복사 전후 sha256 이 네 개 모두
  같았다(로그 92-95행 · 117-120행):
  `241d79d5…`(evidence) · `21b3d222…`(rcl) · `36ea8ae7…`(inbox) · `4efbae27…`(marketfeed).
- **⚠ 「한 바이트도 안 건드렸다」는 아니다. `-shm` 은 새로 쓰였다.** 이 관용구는
  `mode=ro` 이고 `immutable=1` 이 아니며, 읽기 전용 연결도 WAL 인덱스를 쓰기로 열기
  때문에 `-shm` 이 갱신된다 — `docs/runbooks/tos-paper-boot.md` §4-A-1 이 #843 F2 로
  실측해 둔 그대로다. 이 작업 뒤 네 `-shm` 의 mtime 은 **2026-10-03 14:13:00**
  (evidence `.189` · rcl `.261` · inbox `.277` · marketfeed `.289`)이고 크기는 32768 B 그대로다.
- **`-wal` 은 건드리지 않았다**: evidence 2026-09-29 23:47:50 · 나머지 셋 2026-10-02
  13:05:01, 전부 0 B — 이 작업보다 앞선다.
- **사이드카는 치우지 않았다.** 지우는 것은 실 paper 상태를 바꾸는 일이라 운영자 지시
  없이는 하지 않는다(§4-A-1 의 같은 판단). 치울 때의 조건도 거기에 있다.

| 실행 | 줄 | 무엇을 겨눴나 | 결과 |
|---|---|---|---|
| R1 | 2-10 | 대상 부재 · 오늘 2026-10-03 < `BORN_ON` 2026-10-06 (기본값) | `PRE-GENESIS` **rc=0** · 본문 로그에 기록 |
| R2 | 12-21 | 같은 부재 · `BORN_ON=2026-10-01`(이미 지남) | `REFUSED (wrapper)` **rc=1** — `…is on/after the configured genesis date … it is a missing target` |
| R3a | 23-32 | `COLD_TARGET_BORN_ON=2026/10/06` | `refused` **rc=1** — `is not YYYY-MM-DD` |
| R3b | 34-43 | `6-10-2026` | `refused` **rc=1** — 같은 줄 |
| R3c | 45-54 | `TBD` | `refused` **rc=1** — 같은 줄 |
| R3d | 56-65 | `2026-02-30`(형식은 맞고 달력에 없는 날) | `refused` **rc=1** — `is not a real calendar date` |
| R4 | 67-69 | 모르는 인자 `--selftst` | **rc=2**, 백업을 돌리지 않음 — `ABORT — unknown argument` |
| R5 | 71-80 | 대상 자리에 **일반 파일** | `refused` **rc=1** — `exists but is NOT a directory … This is a typo` |
| R6 | 82-88 | 락을 다른 프로세스가 보유 | `SKIP` **rc=0** · **텔레그램 본문 생성됨**(85행) |
| R7 | 90-124 | 새 사본(migrate 뒤) · **실 바닥 53687091200** | `verdict` **rc=0** · gen1 · 7,195,055 → 429,496 B (16.75×) · 멤버 4 + 체인 재검증 |
| R8 | 126-141 | 다음 세대 | `verdict` **rc=0** · gen2 · 429,380 B (16.76×) |
| R9 | 142-158 | 바닥 900 TiB | `refused` **rc=1** — `below the configured floor of 989560464998400; refused before anything is written`(149행), **아무것도 쓰지 않음** |
| R10 | 159-174 | 다음 세대 | `verdict` **rc=0** · gen3 · 427,860 B (16.82×) |
| R11 | 175-192 | 바닥 = 측정 여유 − 3 MB | `verdict` **rc=0** · gen4 + **바닥 경고**(184행) |

R9 는 「바닥을 터무니없이 높이면」 **프리플라이트 거부**(아무것도 안 씀)라는 것을 보인다.
경고 경로는 그것과 다르다 — 바닥이 실행 **전** 여유보다는 낮고 실행 **후** 여유보다는
높아야 나온다. R11 이 그 구간을 겨눈 것이고(한 번의 실행이 ≈7.6 MB 를 쓰므로 바닥을 측정
여유보다 3 MB 낮게 잡았다), 종료코드는 **0** 이며 보고서에
`"free_bytes_below_minimum_after": true` 가 남았다 — 검증된 백업을 경보 때문에 되돌리지
않는다(§6).

**산출물과 압축비** — 원본은 네 실행 모두 **7,195,055 B**(`source_bytes`, 멤버 4; 이
corpus 에 `composite_state` 가 없어 §7.1.4 의 실 커스터디 왕복과 같은 4 다):

| 세대 | `.tar.xz` | 압축비 | 바닥 | `below_floor_after` | 소비(할당) |
|---|---|---|---|---|---|
| gen1 (R7) | 429,496 B | 16.75× | 53687091200 | `false` | 7,630,848 B |
| gen2 (R8) | 429,380 B | 16.76× | 53687091200 | `false` | 7,630,848 B |
| gen3 (R10) | 427,860 B | 16.82× | 53687091200 | `false` | 7,651,328 B |
| gen4 (R11) | 427,800 B | 16.82× | 357244094784 | **`true`** | 7,634,944 B |

⚠ 「소비」는 **할당 기준**이다(보고서의 `free_space_before − free_space_after`). 아카이브
파일 크기의 합과 다른 이유는 비압축 세대·매니페스트·블록 반올림이 함께 들어가기 때문이고,
`du -sb` 의 **apparent size** 와도 다른 수다. 두 계열을 더하거나 비교하지 말 것.

**보관본 재검사(§7)도 돌렸다** — 새 압축 없이 `verify_archive` 로 왕복시켰고 통과했으며
검증 디렉터리는 지워졌다. ⚠ §7 의 스니펫은 **옛 경로 배치**(`paper-backups`/`paper-cold`/
`paper-verify`)로 적혀 있다. 이 호스트에서는 다음으로 바꿔 읽는다:
`archive` → `~/.local/state/tos/paper-cold/archives/gen{N}.set.tar.xz` ·
`manifest` → `~/.local/state/tos/paper-cold/backups/gen{N}.set.manifest.json` ·
`verify_dir` → `~/.local/state/tos/paper-cold/verify/gen{N}.recheck`(없는 경로여야 한다) ·
`custody` → `~/.local/state/tos/paper-custody`.

**텔레그램**은 `[SELFTEST]` 접두로 **한 번만** 실제 전송했다(디스포지션 전 라운드). 위
R1-R11 은 전부 `COLD_NOTIFY=0` 이라 전송하지 않았고, **보낼 본문은 로그에 그대로 적혔다**
(`--- telegram body ---` 블록). 예를 들어 R6 의 SKIP 본문은 85행이다.

사본과 스크래치 아카이브는 증명을 적은 뒤 **지웠다** — 이 라운드 37,694,331 B(apparent size,
`du -sb`: 사본 7,192,576 B · 콜드 트리 세 벌 + 설정 셋). 앞선 두 라운드의 44,270,537 B 와
14,817,944 B 도 같은 기준이다. **로그와 보고서 JSON 은 위 증거 경로에 남겼다.** 실 세 트리
(`paper-cold/{backups,archives,verify}`)는 이 전 과정에서 **비어 있는 채로 남았다**.

### 4-5-6. 다음날 아침 확인 (통지의 대체가 아니라 짝)

텔레그램이 조용한 데에는 두 가지 이유가 있다 — **잘 돌았다**와 **통지 자체가 못 갔다**
(종료코드 2 의 ABORT · briefing 자격증명 부재 · curl 실패 · cron 이 아예 안 뜸).
둘을 가르는 것은 아침의 세 명령이다.

```bash
# 1) 어젯밤 마지막 블록이 verdict 로 끝났는가
tail -n 40 ~/.local/state/tos/cold-backup.log
#    끝에 `=== cold-backup rc=0 class=verdict` 가 보여야 한다.
#    ⛔ 로그에 `SKIP —` 가 보이면 **백업은 돌지 않았다** — 종료코드 0 이어도 그렇다.
#    `PRE-GENESIS` 도 마찬가지다(2026-10-06 전에는 정상).

# 2) 평일마다 세대가 하나씩 늘었는가
ls -l ~/.local/state/tos/paper-cold/archives/
#    거래일 하루에 gen{N}.set.tar.xz + gen{N}.cold-backup.report.json 한 쌍.
#    번호가 건너뛰어 있으면 그 밤에 스냅숏이 중도 사망한 것이다(§5 — 지우지 말 것).

# 3) 마지막 보고서가 실제로 검증됐고 바닥 위인가
jq '{generation, archive_bytes, chain_verified, files_verified,
     minimum_free_bytes, free_bytes_below_minimum_after}' \
  "$(ls -t ~/.local/state/tos/paper-cold/archives/*.cold-backup.report.json | head -1)"
#    chain_verified=true · free_bytes_below_minimum_after=false 여야 한다.
#    후자가 true 면 **다음 실행이 거부된다** — 조치는 §6(저장공간).
```

로그가 **어제 날짜에서 멈춰 있고 아무 블록도 없으면** cron 이 뜨지 않은 것이다. 그때는
`~/.local/state/tos/cold-backup.cron.log`(비어 있는 것이 정상)와 `crontab -l` 을 본다.

## 5. 거부되거나 실패하면 무엇을 하는가

**두 가지를 구분해 적는다.** `refused` = **규칙이 아니라고 했고 아무것도 쓰지 않았다**.
`failed` = 실행은 적법했는데 **환경이 무너졌다**(런타임이 아직 핸들을 들고 있다 · 디스크가
찼다 · 커스터디를 못 읽는다 · 매니페스트가 안 열린다). 다음 조치가 다르기 때문에 한 단어로
뭉개지 않는다. 어느 쪽이든 **종료코드 1 · stderr 한 줄 · traceback 없음**이다.

| stderr 접두 | 뜻 | 조치 |
|---|---|---|
| `cold-backup: refused — … does not exist` | 설정 파일이 없다 | §2 로 만든다. `--config-dir` 가 **디렉터리**인지 확인(파일 경로가 아니다) |
| `… is still null (named-TBD)` | 설정이 안 채워졌다 | 호스트 좌표 셋 + 용량 바닥을 채운다. 저장소의 paper 사본은 원래 null 이다 |
| `… starts with '~' … no tilde expansion` | `~` 로 시작하는 경로를 적었다 | 실제 절대경로로 바꾼다. 이 로더는 `~` 를 전개하지 않는다 |
| `… is not an absolute path` | 상대경로를 적었다 | 절대경로로 바꾼다 |
| `… is inside the live data directory` / `CONTAINS the live data directory` / `is inside the git worktree` | 보관 경로가 있어서는 안 되는 자리다 | §2 의 경로 규칙대로 옮긴다 |
| `… below the configured floor` | 용량 바닥 미만 — **아무것도 쓰지 않았다** | §6 |
| `cold-backup: snapshot refused — …` | durable set 자체 문제(파일 부재 · 세대 역행) | `backup_root` 가 맞는 트리인지, `evidence`/`rcl`/`inbox` 가 있는지 확인 |
| `… is inside <other root>` / `are the same directory` | 세 트리가 겹친다 | §2 — 셋은 일부러 떼어 둔다 |
| `… exists and is not a directory` | 보관 경로 자리에 **파일**이 있다(오타) | 경로를 고친다. 스냅숏 전에 잡힌다 |
| `… the archive/report/verify scratch for generation N already exists` | 그 세대의 산출물이 이미 있다 | 보통은 일어나지 않는다(할당기가 콜드 보관소도 센다). 일어났다면 그 파일을 옮기거나 지우지 말고 **왜 있는지** 먼저 본다 |
| `cold-backup: archive refused — …` | 압축본이 되읽히지 않았다 **또는 검증 디렉터리가 이미 있다** | 아래 |
| `cold-backup: integrity refused — …` | ⛔ **아카이브의 증거 체인이 재검증되지 않았다** | **재실행이 답이 아니다** — 아래 「압축본을 신뢰하지 않는다」 |
| `cold-backup: custody refused — …` | 커스터디 키를 읽을 수 없거나 세대가 이어지지 않는다 | 경로·소유자·0600 모드·`evidence.key.<generation>` 존재 확인(§1). **스냅숏 전에** 잡힌다 |
| `cold-backup: snapshot failed — OperationalError: database is locked` | **런타임이 아직 떠 있다** — §1 전제 1 위반 | 런타임을 멈추고 다시 돌린다. cron 시각을 당겼는지 본다 |
| `cold-backup: snapshot failed — OSError: … No space left …` | 복사 도중 디스크가 찼다 | §6. 남은 `gen{N}/` 는 **지우지 않는다** — 다음 실행은 그 번호를 건너뛴다 |
| `cold-backup: archive failed — …` | 압축·검증 단계에서 환경이 무너졌다 | 비압축 스냅숏은 남아 있다. 원인을 고치고 다시 돌린다(다음 세대로 간다). ⚠ `SchemaVersionRefused` 가 이 접두로 나온다 — 환경 고장이 아니라 **대상이 구 스키마**라는 판정이고, 조치는 재실행이 아니라 `tos-paper-boot.md` 의 `migrate` 다(§4-5-2 · 계획 §7.1.26 A3-F1) |
| `cold-backup: failed — <ExcType>: …` | 단계 이름이 없는 형태 — 디스패치가 분류표의 어느 접두에도 못 넣은 예외다 | 위 행들과 같은 「환경」 취급이되, **예외 타입을 그대로 보고한다**. 분류표에 빠진 판정일 수 있다 |
| `cold-backup: config failed — …` | 설정 로더가 이 모듈이 모르는 방식으로 깨졌다 | 메시지의 예외 타입을 그대로 보고한다 — 결함일 수 있다 |

`archive refused` 일 때:

- **비압축 스냅숏은 그대로 남는다.** 그 세대의 백업은 완전하다 — 잃은 것은 압축본뿐이다.
- `verify_dir … already exists` 면 이전 실행이 남긴 `verify_root/gen{N}.verify` 를 확인하고
  (그 안의 압축 해제 사본이 **실패 원인의 증거**다) 치운 뒤 다시 돌린다. 이미 있는
  디렉터리로 읽어 들이기를 거부하는 이유는, 빠진 멤버를 오래된 파일이 가려 검증을 통과시킬
  수 있기 때문이다.
- digest 불일치(`archive refused`)·체인 실패(`integrity refused`)면 그 세대의 **압축본을
  신뢰하지 않는다**. 비압축 사본으로 `restore-drill` 을 돌려 원본 쪽이 멀쩡한지 먼저 가린다.
  **`integrity refused` 는 특히 재실행으로 지나가지 말 것** — 라이브 체인 자체가 의심된다는
  뜻일 수 있다.
- 같은 세대의 `.tar.xz` 가 이미 있으면 덮어쓰지 않고 거부한다. 재시도는 그 파일을 치우거나
  다음 세대로 간다.

**반쯤 쓰다 만 `gen{N}/` 를 발견했을 때** (스냅숏이 죽은 자리):

- **지우지 않는다.** 다음 실행은 그 번호를 **건너뛴다** — 세대 할당이 매니페스트뿐 아니라
  디렉터리도 센다. 한 번의 일시적 고장이 매일 밤 반복되는 거부로 굳는 일은 없다.
- 손으로 같은 번호를 다시 쓰려 하면(`backup-set --generation N`) 이름 붙은 거부가 나온다:
  `backup_set: … already exists … died part-way`. 내용을 확인한 뒤 **dest_dir 밖으로**
  옮기거나 그대로 둔다.

## 6. 용량 경보가 울리면

- **실행 전** 여유가 바닥 미만이면 아무것도 쓰지 않고 거부한다.
- 실행 **도중** 바닥을 지났으면 그 백업은 **끝까지 가고 검증까지 통과한 뒤** stderr 로
  `WARNING` 을 찍고 종료코드 0 으로 끝난다. 검증된 백업을 경보 때문에 되돌리지 않는다.
  보고서의 `free_bytes_below_minimum_after` 가 `true` 로 남고, **다음 실행이 거부된다.**
- **조치는 저장공간이다** — 디스크를 늘리거나, 오래된 아카이브를 **다른 매체로 옮긴다.**
  이 도구는 콜드 사본을 지우지 않고, 지우는 절차도 제공하지 않는다. 검증된 증거 사본의
  파기는 ADR-002-016 §17 의 대상(승인된 정책 · 실효적 이중 통제 · 범위 증명 · 만료된 보류 ·
  무결성 보존 툼스톤)이고, 계획 §4 트랙 B 가 열릴 때 다룬다.

## 7. 보관본 재검사 (새 압축 없이)

몇 달 묵은 콜드 사본이 아직 읽히는지 확인할 때는 새 백업을 만들지 않고 공개
`verify_archive` 를 쓴다:

```python
from pathlib import Path
from tos_runtime.custody.key_provider import FileKeyProvider
from tos_runtime.operations.backup_archive import verify_archive

verify_archive(
    Path("/home/deploy/.local/state/tos/paper-cold/gen1.set.tar.xz"),
    Path("/home/deploy/.local/state/tos/paper-backups/gen1.set.manifest.json"),
    Path("/home/deploy/.local/state/tos/paper-verify/gen1.recheck"),  # 없는 경로여야 한다
    key_provider=FileKeyProvider(Path("/home/deploy/.local/state/tos/paper-custody")),
)
```

통과하면 `ArchiveVerification` 을 돌려주고 검증 디렉터리를 지운다. 거부하면 그 디렉터리를
**남기고** 거부 메시지가 경로를 말한다. 검사는 셋이고 전부 fail-closed다: ① xz 스트림이
정확히 하나이고 끝까지 온전한가(무결성 검사 없는 컨테이너·뒤따르는 바이트·스트림 패딩 전부
거부) ② 멤버별 sha256 이 매니페스트와 같은가 ③ 증거 체인이 재검증되는가.
