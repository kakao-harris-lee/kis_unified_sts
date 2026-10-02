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

## 2. 설정 — `evidence_cold_backup.yaml`

템플릿은 `tos/runtime/config/evidence_cold_backup.example.yaml`, paper 승인 사본은
`config/tos_runtime/paper/evidence_cold_backup.yaml` 이고 **세 경로가 전부 `null`** 이다.
호스트 좌표라 저장소가 알 수 없기 때문이고, 로더는 null 을 기본값으로 메우지 않고
**거부한다** — 짐작한 보관 경로는 콜드 백업이 없는 것보다 나쁘다. 있는 것처럼 보이기 때문이다.

채운 파일은 **저장소 밖**에 둔다. 권장 위치는 커스터디 옆이다:

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

- **렌더된 설정 디렉터리(`~/.config/tos/paper-config`)에 두지 않는 쪽을 권한다.**
  `scripts/tos/render_paper_config.py` 는 재렌더 때 그 디렉터리를 저장소 사본으로 **다시
  만든다** — 손으로 채운 값이 사라진다. `--config-dir` 는 그냥 이 운영 디렉터리를 가리킨다.
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

```bash
cd /home/deploy/project/kis_unified_sts
DATA=~/.local/state/tos/paper-data        # 라이브 durable set
CUSTODY=~/.local/state/tos/paper-custody
OPS=~/.local/state/tos/paper-ops

PYTHONPATH=tos/src:tos/runtime/src .venv/bin/python -c \
  'import sys;from tos_runtime.compose.cli import main;sys.exit(main(sys.argv[1:]))' \
  cold-backup --data-dir "$DATA" --config-dir "$OPS" --custody-root "$CUSTODY"
```

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

## 5. 거부되거나 실패하면 무엇을 하는가

**두 가지를 구분해 적는다.** `refused` = **규칙이 아니라고 했고 아무것도 쓰지 않았다**.
`failed` = 실행은 적법했는데 **환경이 무너졌다**(런타임이 아직 핸들을 들고 있다 · 디스크가
찼다 · 커스터디를 못 읽는다 · 매니페스트가 안 열린다). 다음 조치가 다르기 때문에 한 단어로
뭉개지 않는다. 어느 쪽이든 **종료코드 1 · stderr 한 줄 · traceback 없음**이다.

| stderr 접두 | 뜻 | 조치 |
|---|---|---|
| `cold-backup: refused — … does not exist` | 설정 파일이 없다 | §2 로 만든다. `--config-dir` 가 **디렉터리**인지 확인(파일 경로가 아니다) |
| `… is still null (named-TBD)` | 설정이 안 채워졌다 | 호스트 좌표 셋 + 용량 바닥을 채운다. 저장소의 paper 사본은 원래 null 이다 |
| `… is not an absolute path` | `~` 나 상대경로를 적었다 | 실제 절대경로로 바꾼다 |
| `… is inside the live data directory` / `CONTAINS the live data directory` / `is inside the git worktree` | 보관 경로가 있어서는 안 되는 자리다 | §2 의 경로 규칙대로 옮긴다 |
| `… below the configured floor` | 용량 바닥 미만 — **아무것도 쓰지 않았다** | §6 |
| `cold-backup: snapshot refused — …` | durable set 자체 문제(파일 부재 · 세대 역행) | `backup_root` 가 맞는 트리인지, `evidence`/`rcl`/`inbox` 가 있는지 확인 |
| `… is inside <other root>` / `are the same directory` | 세 트리가 겹친다 | §2 — 셋은 일부러 떼어 둔다 |
| `… exists and is not a directory` | 보관 경로 자리에 **파일**이 있다(오타) | 경로를 고친다. 스냅숏 전에 잡힌다 |
| `cold-backup: archive refused — …` | 압축본이 되읽히지 않았다 **또는 검증 디렉터리가 이미 있다** | 아래 |
| `cold-backup: snapshot failed — OperationalError: database is locked` | **런타임이 아직 떠 있다** — §1 전제 1 위반 | 런타임을 멈추고 다시 돌린다. cron 시각을 당겼는지 본다 |
| `cold-backup: snapshot failed — OSError: … No space left …` | 복사 도중 디스크가 찼다 | §6. 남은 `gen{N}/` 는 **지우지 않는다** — 다음 실행은 그 번호를 건너뛴다 |
| `cold-backup: archive failed — …` | 압축·검증 단계에서 환경이 무너졌다 | 비압축 스냅숏은 남아 있다. 원인을 고치고 다시 돌린다(다음 세대로 간다) |
| `cold-backup: custody failed — …` | 커스터디 루트를 못 읽는다 | 경로·소유자·0600 모드 확인(§1). 스냅숏 전에 잡힌다 |
| `cold-backup: config failed — …` | 설정 로더가 이 모듈이 모르는 방식으로 깨졌다 | 메시지의 예외 타입을 그대로 보고한다 — 결함일 수 있다 |

`archive refused` 일 때:

- **비압축 스냅숏은 그대로 남는다.** 그 세대의 백업은 완전하다 — 잃은 것은 압축본뿐이다.
- `verify_dir … already exists` 면 이전 실행이 남긴 `verify_root/gen{N}.verify` 를 확인하고
  (그 안의 압축 해제 사본이 **실패 원인의 증거**다) 치운 뒤 다시 돌린다. 이미 있는
  디렉터리로 읽어 들이기를 거부하는 이유는, 빠진 멤버를 오래된 파일이 가려 검증을 통과시킬
  수 있기 때문이다.
- digest 불일치·체인 실패면 그 세대의 **압축본을 신뢰하지 않는다**. 비압축 사본으로
  `restore-drill` 을 돌려 원본 쪽이 멀쩡한지 먼저 가린다.
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
