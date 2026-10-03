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

## 4-5. 활성화 준비 상태 — 2026-10-03

A3 를 **한 줄 편집으로 켤 수 있는 상태**까지만 만들어 두고 멈춘 기록이다. 운영자 결정
두 개(용량 바닥 · 대상 data dir)가 열려 있는 동안에는 켜지 않는다. 아래 「무엇이 있나」는
이 호스트에 **실재**하고, 「무엇이 비어 있나」는 **일부러** 비어 있다.

### 4-5-1. 호스트에 있는 것

| 무엇 | 경로 | 모드 | 상태 |
|---|---|---|---|
| 인스턴스 설정 | `~/.local/state/tos/paper-ops/evidence_cold_backup.yaml` | `600` | 세 경로 채움 · 바닥 **null**(의도적 불활성) |
| 비압축 세대 | `~/.local/state/tos/paper-cold/backups` | `700` | 빈 디렉터리 |
| 콜드 보관소 | `~/.local/state/tos/paper-cold/archives` | `700` | 빈 디렉터리 |
| 검증 스크래치 | `~/.local/state/tos/paper-cold/verify` | `700` | 빈 디렉터리 |
| 분리 워크트리 | `~/.local/state/tos/measure/wt-cold` | — | detached `origin/main` |
| 야간 래퍼 | `~/.config/kis-probes/cold-backup-nightly.sh` | `700` | **crontab 에 없음** |
| 실행 로그(기본) | `~/.local/state/tos/cold-backup.log` | — | 아직 없음 |

⛔ **설정은 `~/.config/tos/paper-config` 에 두지 않았다.** §2 가 이미 권고한 바이고,
#840 이후로는 근거가 하나 더 구체적이다 — `evidence_cold_backup.yaml` 이 이제
`scripts/tos/render_paper_config.py` 의 **원본 트리**(`config/tos_runtime/paper/`)에 있다.
그래서 그 디렉터리에 손으로 채운 파일을 두면 두 가지가 **조용히** 일어난다:

1. 재렌더가 디렉터리를 통째로 갈아끼운다(`_publish` 가 이전 렌더를 옆으로 옮긴 뒤
   `rmtree` 한다). 채운 값이 저장소의 all-null 사본으로 **되돌아가고**, 그 다음 cron 은
   「`minimum_free_bytes` is still null」로 거부한다 — 아무도 아무것도 바꾸지 않았는데.
2. `--check` 는 렌더 디렉터리를 원본과 줄 단위로 대조하고, 원본에 없는 파일로 허용하는
   것은 `bootproof_journal.jsonl` 과 `RENDERED.json` **둘뿐**이다. 채운 줄마다
   「changed line is not a registered coordinate slot」이 뜬다.

로더는 어느 경로도 하드코딩하지 않는다 — `<--config-dir>/evidence_cold_backup.yaml` 을
읽을 뿐이므로 위치는 순전히 래퍼의 인자다.

### 4-5-2. 비어 있는 것 (운영자 결정 둘)

**(1) `minimum_free_bytes` — 값 미정.** 설정 파일에 `null` 로 남아 있고 로더가 거부한다.
기본값이 없는 것은 결정이다(§2). 지금 상태에서 래퍼를 돌리면 **정확히 이 줄**이 나온다:

```
cold-backup: refused — load_cold_backup_config: 'minimum_free_bytes' in /home/deploy/.local/state/tos/paper-ops/evidence_cold_backup.yaml is still null (named-TBD) — operator-fill it before scheduling a cold backup; this loader never invents a destination or a free-space floor
```

참고 수치(2026-10-03 실측): 이 호스트 `/` 여유 **357,771,644,928 B ≈ 333 GiB**.
계획 §1 실측 증가율은 원본 ≈200 MB/일 · 압축 뒤 ≈13 MB/일. 아래 사본 실측으로는
**한 번의 실행이 7,630,848 B** 를 쓴다(비압축 세대 + 아카이브 + 보고서, 7 MB 코퍼스 기준).

**(2) 대상 `--data-dir` — 미정이고, 지금은 고를 수 있는 것이 1회성 corpus 뿐이다.**
이 호스트에는 **상주 paper data dir 이 없다**(`docs/runbooks/tos-paper-boot.md` §4-A 적용
범위, 2026-10-02 실측). 디스크에 있는 durable set 은 2026-09-27/28 부팅증명 캠페인이
남긴 1회성 디렉터리 12개(`~/.local/state/tos/{realclock,t3}-*/data`)가 전부다. 즉
**대상은 상주 런타임이 한 번 돌아야 비로소 생긴다**; 그 전까지 고를 수 있는 것은 그
12개뿐이고, 어느 것을 쓸지는 운영자가 **이름으로** 지정한다(짐작 금지 — §4-A 와 같은 규칙).

⚠ **그리고 그 12개는 지금 코드로 콜드 백업할 수 없다 — 전부 증거 스키마 v1 이다.**
2026-10-03 읽기 전용 전수 조사(`mode=ro&immutable=1`):

```
realclock-20260927T123127-LONG   evidence=1      realclock-20260928T102001-SHORT  evidence=1
realclock-20260927T123909-SHORT  evidence=1      realclock-20260928T104001-LONG   evidence=1
realclock-20260927T155444-LONG   evidence=1      realclock-20260928T110001-LONG   evidence=1
realclock-20260927T225742-LONG   evidence=1      t3-20260927T145001               evidence=1
realclock-20260928T100001-LONG   evidence=1      t3-20260927T145237               evidence=1
t3-809-new-20260927T191215       evidence=1      t3-809-old-20260927T191029       evidence=1
```

`EVIDENCE_SCHEMA_VERSION` 은 **2** 이므로(계획 §2 A2), 아카이브의 증거 체인 재검증이
v1 파일을 열다 거부한다. 사본에서 실측한 줄은 이렇다:

```
cold-backup: archive failed — SchemaVersionRefused: evidence: on-disk schema user_version=1 is BEHIND this code's schema_version=2 — run the operator `migrate` CLI (tos_runtime.operations.schema_migrations.apply_migrations) before booting; boot never auto-applies a migration
```

**그러므로 대상 결정에는 순서가 딸려 온다**: 1회성 corpus 를 대상으로 고른다면 먼저
`tos-paper-boot.md` §4-A 의 `migrate` 를 **그 corpus 에** 돌려야 한다. 새로 부팅하는
상주 런타임을 대상으로 고른다면 genesis 가 곧장 v2 를 만들므로 이 단계가 없다.

⚠ 위 줄에 대해 **두 가지를 기록해 둔다.** ① 접두가 `archive failed` 다 — 예외 이름이
`SchemaVersionRefused` 인데도 `_PASSTHROUGH_REFUSALS` 에 없어 환경 고장으로 분류된다.
§5 의 `archive failed` 행이 안내하는 「원인을 고치고 다시 돌린다(다음 세대로 간다)」는 이
경우에 **맞는** 조치지만(마이그레이션이 곧 「원인을 고치는」 것이다), 한 단어로는
「호스트가 깨졌다」로 읽힌다. ② 이때 **비압축 스냅숏은 이미 떠 있다** — 그 세대의 백업은
완전하고, 잃은 것은 압축본뿐이다(§5 의 `archive refused` 항목과 같은 성질). 실측에서
`gen1/` 와 `gen1.set.manifest.json` 이 남았고 `.tar.xz` 는 없었으며 `gen1.verify` 가
**남았다**(거부 원인의 증거). 다음 실행은 그 번호를 **건너뛰어** gen2 를 썼다.

### 4-5-3. 활성화 — 한 줄 편집 + 한 줄 cron

**(1) 바닥 한 줄.** `~/.local/state/tos/paper-ops/evidence_cold_backup.yaml` 의 마지막
값만 바꾼다. 다른 줄은 손대지 않는다:

```diff
-minimum_free_bytes: null
+minimum_free_bytes: 53687091200     # 50 GiB — 운영자 승인값으로 대체할 것
```

**(2) 대상 한 줄.** cron 줄의 `COLD_DATA_DIR` 에 운영자가 **이름으로 지정한** 디렉터리를
적는다. 기본값은 일부러 없다 — 짐작한 대상은 「백업이 돌고 있다」처럼 보이면서 엉뚱한
트리를 뜬다.

**(3) crontab 한 줄.** 아래를 `crontab -e` 로 넣는다. **이 런북은 crontab 을 건드리지
않았다** — 등록은 운영자의 결정이다.

```cron
CRON_TZ=Asia/Seoul
# 평일 18:00 KST — 런타임을 정지시킨 뒤에 돈다(§1 전제 1). COLD_DATA_DIR 은 필수다.
0 18 * * 1-5 COLD_DATA_DIR=/home/deploy/.local/state/tos/<operator-named>/data $HOME/.config/kis-probes/cold-backup-nightly.sh >> $HOME/.local/state/tos/cold-backup.log 2>&1
```

§4-4 의 cron 줄과 다른 점은 둘뿐이다: 래퍼 경로가 `~/.config/kis-probes/` 이고(이 호스트의
무인 러너들이 모여 있는 자리 — `run-p8-*.sh` 와 같다), 대상 data dir 이 **환경변수**다.

### 4-5-4. 래퍼가 하는 일 (`~/.config/kis-probes/cold-backup-nightly.sh`)

- `flock -n` — 겹치면 뒤에 온 쪽이 기다리지 않고 비켜난다(겹치면 둘이 같은 세대를
  할당받아 하나가 산출물 충돌로 거부된다). 실측: `SKIP — another cold-backup run holds …`.
- `git fetch` 뒤 `~/.local/state/tos/measure/wt-cold` 를 **detached `origin/main`** 으로
  맞춘다. 갈아타기 **전에** 브랜치 위인지·더티인지 보고(둘 다 거부), 갈아탄 **뒤에** 다시
  본다. 매 실행 첫 줄에 커밋 SHA 를 찍는다. 인터프리터는 주 체크아웃의 `.venv` 지만
  `PYTHONPATH` 가 절대경로로 워크트리를 가리킨다(§4-3 의 같은 함정).
  ⚠ §4-2 는 워크트리 갱신을 「의도적으로만」 하라고 적는다. 이 래퍼는 매 실행 `origin/main`
  으로 맞춘다 — 지키려는 것(무인 실행이 리뷰 전 코드에 닿지 않는다)은 같고, `origin/main`
  을 **명시적으로** 체크아웃하는 쪽이 오래된 채 두는 것보다 강한 보장이다.
- **세 결말을 한 줄씩** 텔레그램 briefing 채널로 보낸다(`.env` 에서 `TELEGRAM_BRIEFING_*`
  **두 줄만** 읽는다; 전체 소싱도, 토큰 로깅도 없다). 분류는 #840 의 계약 그대로다:

  | 분류 | 조건 | 줄이 말하는 것 |
  |---|---|---|
  | `verdict` | 종료코드 0 | 아카이브가 존재·되읽힘·전 멤버 digest 일치·체인 재검증. 바닥 경고가 붙어도 **이 백업은 검증됐다** |
  | `refused` | `cold-backup: [<layer> ]refused — …` | 규칙이 아니라고 했고 **아무것도 쓰지 않았다**. 접두 단어로 §5 를 찾는다. ⛔ 「내일 다시」라고 적지 않는다 — `integrity refused` 는 재실행이 답이 아니다 |
  | `failed` | `cold-backup: <stage> failed — …` | 실행은 적법했고 환경이 무너졌다. 호스트를 고친 뒤 다시 돈다(다음 세대로 간다) |

  둘 다 아닌 줄은 `unclassified` 로 보고한다 — 못 알아본 줄을 깨끗한 분류로 접어 넣지
  않는다.
- **자기 자신을 지우지 않고 crontab 에도 손대지 않는다.** 반복 일정이라 disarm 이 없다.
- `COLD_DATA_DIR` 은 **필수**(기본값 없음). 없으면 래퍼 자신의 `refused` 로 끝난다:
  `REFUSED (wrapper) — COLD_DATA_DIR is unset — this wrapper has no default live data directory by decision`.
- `COLD_NOTIFY=0` 은 **손으로 돌려 보는 dry 실행 전용**이다. 전송을 건너뛸 때마다 로그에
  한 줄을 남긴다 — 알림이 조용한 이유가 「설정이 껐다」인지 「아무도 안 돌았다」인지
  나중에 구분할 수 있어야 하기 때문이다. cron 줄은 이것을 설정하지 않는다.

### 4-5-5. 사본에서의 전 구간 증명 (2026-10-03)

실 corpus 는 **읽기만** 했다. 대상은
`~/.local/state/tos/realclock-20260928T110001-LONG/data`(2026-09-28 11:00:01 부팅 ·
11:15:04 정지)이고, 사본은 WAL 조건에 기대지 않는 관용구로 떴다:

```bash
sqlite3 "file:$CORPUS/$f.sqlite3?mode=ro" ".backup '$COPY/$f.sqlite3'"
```

§4-A-1 이 남긴 교훈(「다음 조사는 먼저 해시를 뜬다」)대로 **복사 전후로 본체 네 파일의
sha256 을 떴고 네 개 모두 같았다** — 정황이 아니라 해시로 확인한 불변이다:

```
241d79d5…fd353b  evidence.sqlite3      36ea8ae7…d2b59a  inbox.sqlite3
21b3d222…9314d6  rcl.sqlite3           4efbae27…985d85  marketfeed.sqlite3
```

스크래치 설정은 **테스트 전용 바닥 1 GiB**(`minimum_free_bytes: 1073741824`)와 스크래치
세 경로를 썼다. 그 숫자는 승인된 운영 바닥이 아니며 실 설정으로 옮기지 않았다.

| 실행 | 설정 | 결과 | 줄 |
|---|---|---|---|
| 1 | 바닥 1 GiB, **v1 corpus** | `failed` · rc=1 | `cold-backup: archive failed — SchemaVersionRefused: … user_version=1 is BEHIND … schema_version=2` |
| — | — | 사본에 `migrate` | `migrate: evidence … — applied v1 -> v2 (v2)` (나머지 셋은 `nothing to do`) |
| 2 | 바닥 1 GiB | `verdict` · rc=0 · **gen2**(죽은 gen1 을 건너뜀) | `cold-backup: archived gen2 … (7195071 -> 427108 bytes), read back and verified: 4 file digest(s) + evidence chain` |
| 3 | 바닥 1 GiB | `verdict` · rc=0 · **gen3** | `cold-backup: archived gen3 … (7195071 -> 429432 bytes) … 4 file digest(s) + evidence chain` |
| 4 | 바닥 **900 TiB** | `refused` · rc=1 · **아무것도 쓰지 않음** | `cold-backup: refused — cold_backup: archive_dir+backup_root+verify_root at … has 357670219776 bytes free — below the configured floor of 989560464998400; refused before anything is written` |
| 5 | 바닥 = 측정 여유 − 3 MB | `verdict` · rc=0 · **gen4 + 바닥 경고** | 아래 |
| 6 | **실 호스트 설정**(바닥 null) | `refused` · rc=1 | §4-5-2 의 그 줄. 실 세 트리는 **그대로 비어 있었다** |

4번은 「바닥을 터무니없이 높이면」 **프리플라이트 거부**(아무것도 안 씀)라는 것을 보이고,
경고 경로는 그것과 다르다 — 바닥이 실행 **전** 여유보다는 낮고 실행 **후** 여유보다는
높아야 나온다. 5번이 그 구간을 겨눈 것이다(한 번의 실행이 7,630,848 B 를 쓰므로 바닥을
측정 여유보다 3 MB 낮게 잡았다):

```
cold-backup: archived gen4 to …/gen4.set.tar.xz (7195071 -> 427784 bytes), read back and verified: 4 file digest(s) + evidence chain; report at …/gen4.cold-backup.report.json
cold-backup: WARNING — archive_dir+backup_root+verify_root at …: 357667237888 bytes free (configured floor 357672761664). This backup is verified; the NEXT run will refuse. Nothing here deletes a cold copy (that is Track B, ADR-002-016 §17) — add storage or move archives to another medium
```

종료코드는 **0** 이고 보고서에 `"free_bytes_below_minimum_after": true` 가 남았다 —
검증된 백업을 경보 때문에 되돌리지 않는다(§6).

**산출물과 압축비** (원본 7,195,071 B · 멤버 4 — 이 corpus 에 `composite_state` 가 없어
§7.1.4 의 실 왕복과 같은 4 다):

| 세대 | `.tar.xz` | 압축비 | 보고서 | `below_floor_after` |
|---|---|---|---|---|
| gen2 | 427,108 B | 16.8× | 1,408 B | `false` |
| gen3 | 429,432 B | 16.8× | 1,408 B | `false` |
| gen4 | 427,784 B | 16.8× | 1,409 B | **`true`** |

**보관본 재검사(§7)도 돌렸다** — 새 압축 없이 `verify_archive` 로 gen2 를 왕복시켰고,
통과했으며 검증 디렉터리는 지워졌다:

```
generation 2 · 7195071 -> 427108 bytes (16.8x) · files_verified ('evidence','rcl','inbox','marketfeed') · verify dir left? False
```

**텔레그램**은 `[SELFTEST]` 접두로 **한 번만** 보냈다(1번 실행). 그 한 줄이 `failed` 분류를
실어 간 것은 위 v1 발견 때문이고, 나머지 실행은 `COLD_NOTIFY=0` 으로 전송을 건너뛰면서
보낼 내용을 로그에 그대로 남겼다. `verdict` 분류의 줄은 이 모양이다:

```
[SELFTEST] TOS cold-backup OK — cold-backup: archived gen4 … (7195071 -> 427784 bytes), read back and verified: 4 file digest(s) + evidence chain; report at …
⚠ cold-backup: WARNING — … 357667237888 bytes free (configured floor 357672761664). This backup is verified; the NEXT run will refuse. …
worktree /home/deploy/.local/state/tos/measure/wt-cold @ aae1cec6e73b · data-dir … · 로그 …
```

사본·스크래치 아카이브는 증명을 적은 뒤 **지웠다**(합계 44,286,049 B — 사본 7,192,576 B ·
콜드 트리 37,075,488 B · 로그 15,512 B · 설정 셋 2,473 B). 실 세 트리와 실 corpus 는
손대지 않았다.

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
| `cold-backup: archive failed — …` | 압축·검증 단계에서 환경이 무너졌다 | 비압축 스냅숏은 남아 있다. 원인을 고치고 다시 돌린다(다음 세대로 간다) |
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
