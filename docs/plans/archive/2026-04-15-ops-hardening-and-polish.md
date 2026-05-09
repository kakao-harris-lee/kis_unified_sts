# Operational Hardening & Code Polish Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PR #120/#121 머지 이후 남은 3개 후속 작업군을 처리한다 — (1) 2026-04-14 mppo_best 덮어쓰기 사고 재발 방지(파일 권한 + 학습 스크립트 가드), (2) equity snapshot 크론 등록, (3) 코드 품질 polish(DB 비밀번호 하드코딩 제거, DRY 중복 제거, 문서화 갭, defensive guard).

**Architecture:** 각 phase는 독립 PR 단위로 실행 가능하도록 분리한다. Phase 1은 `scripts/training/train_rl.py`에 프로덕션 모델 경로 쓰기 차단 가드를 추가하고 운영 절차 문서화. Phase 2는 `scripts/cron/publish_equity_snapshot.sh` 등록을 사용자 승인 흐름으로 처리. Phase 3은 `shared/db/utils.py` 신규 + 기존 스크립트 리팩터링 + 1-line defensive guard.

**Tech Stack:** Python 3.11+, bash cron, filesystem permissions (chmod), pytest, 기존 `scripts/training/train_rl.py`·`shared/streaming/trading_state.py`·`shared/strategy/rl_model_helpers.py`

**Deferred out-of-scope:** Baseline `rl_mppo` 재학습은 `docs/plans/2026-04-15-rl-retraining-data-refresh.md` (별도 plan)에서 관리. 본 plan은 재학습을 건드리지 않는다.

---

## File Structure

**Phase 1 (Incident prevention)**
- Modify: `scripts/training/train_rl.py` — 프로덕션 모델 경로(`models/futures/rl/mppo_best/`) 쓰기 시 `--promote` 플래그 없으면 거부
- Create: `shared/ml/rl/model_paths.py` — 프로덕션/실험/challenger 경로 상수 + 가드 함수
- Create: `tests/unit/ml/rl/test_model_paths_guard.py` — 가드 회귀 테스트
- Modify (operational): `models/futures/rl/mppo_best/best_model.zip` 파일 권한 `r--r--r--` 적용 (수동 단계, 문서화만)

**Phase 2 (Crontab registration)**
- Modify: `docs/deployment.md` (또는 신규 `docs/operations/crontab.md`) — equity snapshot cron 등록 절차
- Manual step: `crontab -e`로 40 15 * * 1-5 엔트리 추가 (사용자 승인 후 실행)

**Phase 3 (Code polish)**
- Create: `shared/db/utils.py` — `clickhouse_client_from_env()` 공통 헬퍼
- Modify: `scripts/analysis/rl_backtest_2026q1.py` — 공통 헬퍼 사용, password default 제거
- Modify: `scripts/analysis/rl_backtest_with_mini_scaler.py` — 동일 리팩터링
- Modify: `shared/streaming/trading_state.py` — `publish_signal`, `publish_position_opened`, `publish_position_closed` 도스트링 추가
- Modify: `shared/strategy/rl_model_helpers.py:82` — `load_rl_scaler`에 `scaler_path` None 가드

---

## Phase 1 — Incident Prevention

### Task 1.1: 프로덕션 모델 경로 가드

**목적:** `scripts/training/train_rl.py`(및 hybrid 학습 스크립트)가 `models/futures/rl/mppo_best/` 경로에 best_model.zip을 쓰려고 하면 `--promote` 플래그 없이는 거부. 실험은 `mppo_challenger/`, `mppo_experiment_<tag>/` 경로로 강제.

**Files:**
- Create: `shared/ml/rl/model_paths.py`
- Create: `tests/unit/ml/rl/test_model_paths_guard.py`
- Modify: `scripts/training/train_rl.py` (라인 ~253 save_dir 사용 지점)

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/unit/ml/rl/test_model_paths_guard.py
"""프로덕션 챔피언 경로 쓰기 가드 회귀 테스트.

CLAUDE.md / known_gaps.md: mppo_best/ 경로는 의도적 promote 시에만 쓰기 가능.
Hybrid 등 실험은 mppo_challenger/, mppo_experiment_*/로 한정.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from shared.ml.rl.model_paths import (
    PRODUCTION_CHAMPION_DIR,
    RLPathGuardError,
    check_save_path,
)


class TestCheckSavePath:
    def test_champion_path_rejected_without_promote(self):
        with pytest.raises(RLPathGuardError, match="production champion"):
            check_save_path(
                Path("models/futures/rl/mppo_best/"),
                promote=False,
            )

    def test_champion_path_allowed_with_promote(self):
        # Explicit opt-in must succeed (no exception)
        check_save_path(
            Path("models/futures/rl/mppo_best/"),
            promote=True,
        )

    def test_challenger_path_allowed(self):
        check_save_path(
            Path("models/futures/rl/mppo_challenger/"),
            promote=False,
        )

    def test_experiment_path_allowed(self):
        check_save_path(
            Path("models/futures/rl/mppo_experiment_hybrid_2026_04/"),
            promote=False,
        )

    def test_unknown_path_rejected(self):
        """예기치 않은 경로는 거부 (화이트리스트)."""
        with pytest.raises(RLPathGuardError, match="unknown"):
            check_save_path(
                Path("/tmp/random/path/"),
                promote=False,
            )

    def test_production_champion_dir_constant(self):
        assert PRODUCTION_CHAMPION_DIR == Path("models/futures/rl/mppo_best/")
```

Run: `pytest tests/unit/ml/rl/test_model_paths_guard.py -v` → FAIL (module doesn't exist).

- [ ] **Step 2: `shared/ml/rl/model_paths.py` 구현**

```python
"""RL model path constants + write guards.

Incident 2026-04-14 (see docs/data/known_gaps.md): experimental hybrid training
overwrote the production champion at models/futures/rl/mppo_best/best_model.zip.
This module centralizes path constants and write-path validation so the mistake
is structurally prevented.

Policy:
- Champion (production): models/futures/rl/mppo_best/ — write only with explicit promote flag
- Challenger (pre-promotion): models/futures/rl/mppo_challenger/ — write anytime
- Experiment: models/futures/rl/mppo_experiment_<tag>/ — write anytime
- Any other path: rejected by guard
"""
from __future__ import annotations

from pathlib import Path


class RLPathGuardError(RuntimeError):
    """Raised when a training script attempts to write to a protected model path."""


PRODUCTION_CHAMPION_DIR = Path("models/futures/rl/mppo_best/")
CHALLENGER_DIR = Path("models/futures/rl/mppo_challenger/")
EXPERIMENT_PREFIX = "mppo_experiment_"


def check_save_path(save_dir: Path, *, promote: bool = False) -> None:
    """Validate that save_dir is an approved RL model write target.

    Args:
        save_dir: Directory where the training run will write best_model.zip.
        promote: True only when operator explicitly passes --promote at CLI.
                 Required to write to the production champion directory.

    Raises:
        RLPathGuardError: when write is not allowed.
    """
    resolved = Path(save_dir).resolve()
    champion_resolved = PRODUCTION_CHAMPION_DIR.resolve()
    challenger_resolved = CHALLENGER_DIR.resolve()

    if resolved == champion_resolved:
        if not promote:
            raise RLPathGuardError(
                f"Refusing to write to production champion path {save_dir}. "
                f"Use --promote to explicitly promote, or pick "
                f"{CHALLENGER_DIR} / {EXPERIMENT_PREFIX}<tag>/ for experiments."
            )
        return  # promoted — OK

    if resolved == challenger_resolved:
        return  # challenger — always OK

    if resolved.name.startswith(EXPERIMENT_PREFIX) and resolved.parent == champion_resolved.parent:
        return  # experiment — always OK

    raise RLPathGuardError(
        f"Unknown RL model save path: {save_dir}. Approved targets: "
        f"{PRODUCTION_CHAMPION_DIR} (with --promote), {CHALLENGER_DIR}, "
        f"or sibling {EXPERIMENT_PREFIX}<tag>/."
    )
```

Run tests: `pytest tests/unit/ml/rl/test_model_paths_guard.py -v` → 6 passed.

- [ ] **Step 3: 학습 스크립트에 가드 적용**

Open `scripts/training/train_rl.py`. Around line 253 (the `save_dir = Path(ConfigLoader.load(...))` line), add the guard call right after:

```python
from shared.ml.rl.model_paths import check_save_path, RLPathGuardError

save_dir = Path(ConfigLoader.load(config_path).get("training", {}).get(
    "save_dir", "./models/futures/rl/"
))
save_dir.mkdir(parents=True, exist_ok=True)

# Incident prevention: refuse to overwrite production champion without --promote
try:
    check_save_path(save_dir, promote=bool(getattr(args, "promote", False)))
except RLPathGuardError as e:
    logger.error(str(e))
    sys.exit(2)
```

Also add the CLI flag where argparse is defined (grep `add_argument` around line 503):

```python
parser.add_argument(
    "--promote",
    action="store_true",
    help="Allow writing to the production champion path (mppo_best/). "
         "Required only for intentional promotion; experiments must use "
         "mppo_challenger/ or mppo_experiment_<tag>/.",
)
```

- [ ] **Step 4: 운영 절차 문서 갱신**

Append to `docs/data/known_gaps.md` under the 2026-04-14 mppo_best incident section, "재발 방지 제안" subsection — replace "학습 스크립트에서 mppo_best/ 경로 write 시 경고/차단" line with:

```markdown
  - ✅ **Implemented (2026-04-15):** `shared/ml/rl/model_paths.py::check_save_path` —
    `scripts/training/train_rl.py`는 `mppo_best/` 경로에 쓰려면 `--promote` 플래그 필수.
    실험은 `mppo_challenger/` 또는 `mppo_experiment_<tag>/` 사용.
```

- [ ] **Step 5: 회귀 테스트 + 커밋**

```bash
cd /home/deploy/project/kis_unified_sts && source .venv/bin/activate
pytest tests/unit/ml/rl/ -q --no-header 2>&1 | tail -5
# 기존 RL 테스트 회귀 없는지 확인
```

```bash
git add shared/ml/rl/model_paths.py tests/unit/ml/rl/test_model_paths_guard.py \
        scripts/training/train_rl.py docs/data/known_gaps.md
git commit -m "feat(rl): guard training scripts from overwriting production champion path"
```

### Task 1.2: 파일 권한 하드닝 (운영 수동 단계)

**목적:** `models/futures/rl/mppo_best/best_model.zip`을 `r--r--r--`으로 잠가 실수로 덮어씌워지는 것을 OS 레벨에서도 차단. 의도적 promote 시에만 일시 해제.

**Note:** 이 단계는 파일시스템 변경이며 git-tracked가 아님. 문서화 + 운영 스크립트만 PR에 포함하고, 실제 chmod는 사용자 승인 후 수동 실행.

**Files:**
- Create: `scripts/ops/lock_champion_model.sh`
- Create: `scripts/ops/unlock_champion_model.sh`

- [ ] **Step 1: lock 스크립트 작성**

```bash
#!/bin/bash
# scripts/ops/lock_champion_model.sh
# Lock production RL champion model against accidental overwrite.
# Run after each intentional promote.
set -e

MODEL_FILE="/home/deploy/project/kis_unified_sts/models/futures/rl/mppo_best/best_model.zip"

if [ ! -f "$MODEL_FILE" ]; then
    echo "ERROR: $MODEL_FILE not found"
    exit 1
fi

chmod 0444 "$MODEL_FILE"
echo "Locked: $MODEL_FILE -> $(stat -c '%a %n' "$MODEL_FILE")"
```

- [ ] **Step 2: unlock 스크립트 작성**

```bash
#!/bin/bash
# scripts/ops/unlock_champion_model.sh
# Temporarily unlock production champion for intentional promote.
# MUST be followed by lock_champion_model.sh after promote succeeds.
set -e

MODEL_FILE="/home/deploy/project/kis_unified_sts/models/futures/rl/mppo_best/best_model.zip"

if [ ! -f "$MODEL_FILE" ]; then
    echo "ERROR: $MODEL_FILE not found"
    exit 1
fi

chmod 0644 "$MODEL_FILE"
echo "UNLOCKED (temporary): $MODEL_FILE -> $(stat -c '%a %n' "$MODEL_FILE")"
echo "IMPORTANT: re-lock with scripts/ops/lock_champion_model.sh after promote."
```

- [ ] **Step 3: 실행 가능하게 설정 + 운영 절차 문서**

```bash
chmod +x scripts/ops/lock_champion_model.sh scripts/ops/unlock_champion_model.sh
```

Append to `docs/data/known_gaps.md` 2026-04-14 incident section:

```markdown
  - ✅ **Implemented (2026-04-15):** `scripts/ops/lock_champion_model.sh` /
    `unlock_champion_model.sh` — 프로덕션 챔피언 파일 권한 관리.
    **운영 절차**: 배포 직후 `scripts/ops/lock_champion_model.sh` 실행.
    Promote 시만 `unlock_champion_model.sh` → 새 파일 복사 → `lock_champion_model.sh` 순서 준수.
```

- [ ] **Step 4: 커밋 (chmod 실행 자체는 운영 단계로 남김)**

```bash
git add scripts/ops/lock_champion_model.sh scripts/ops/unlock_champion_model.sh \
        docs/data/known_gaps.md
git commit -m "feat(ops): lock/unlock scripts for champion model file permissions"
```

- [ ] **Step 5: 사용자에게 수동 실행 요청**

운영 단계이므로 PR에 포함하지 않음. 사용자에게 다음 안내:

```
운영 단계:
  cd /home/deploy/project/kis_unified_sts
  ./scripts/ops/lock_champion_model.sh

이후 promote 필요 시:
  ./scripts/ops/unlock_champion_model.sh
  # 모델 교체
  ./scripts/ops/lock_champion_model.sh
```

---

## Phase 2 — Operational: Crontab Registration

### Task 2.1: Equity snapshot cron 등록

**목적:** PR #120에서 추가한 `scripts/cron/publish_equity_snapshot.sh`가 평일 15:40에 자동 실행되도록 crontab 등록. crontab은 운영 시스템 설정이므로 PR에 포함하지 않고 문서화 + 명령 준비만 PR에 넣는다.

**Files:**
- Create: `docs/operations/crontab.md` (기존 없다면 신규, 있다면 갱신)

- [ ] **Step 1: 현재 crontab 확인**

```bash
crontab -l 2>&1 | head -20
```

기존 항목 중 `publish_equity_snapshot.sh`가 이미 있는지 확인. 있다면 이 task는 skip.

- [ ] **Step 2: 운영 문서 작성**

Create `docs/operations/crontab.md`:

```markdown
# Crontab Operations

## Required crontab entries (deploy user)

Production crontab on the deploy server. Maintained manually — `scripts/cron/*.sh` are the scripts, this doc is the registration reference.

### RL / Paper Trading
- `55 8 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/rl_paper.sh start`
- `40 15 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/rl_paper.sh stop`

### Stock Trading Orchestrator
- `0 9 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/stock_trading.sh start`
- `0 16 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/stock_trading.sh stop`

### LLM Analysis
- `30 8 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/llm_premarket.sh`
- `0 21 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/llm_nightly.sh` (제거됨 — premarket이 대체)
- `30 15 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/llm_market_close.sh`
- `0 10,11,12,13,14,15 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/llm_intraday.sh`

### Capital Tracking (NEW — 2026-04-15)
- `40 15 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/publish_equity_snapshot.sh`
  - Purpose: daily equity snapshot to `trading:{asset}:equity_timeline` Redis sorted set
  - Introduced: PR #120 (Phase 3)

### Log Rotation
- `0 3 * * 0 find /home/deploy/project/kis_unified_sts/logs -name "*.log" -mtime +7 -exec gzip {} \;`
- `0 4 * * 0 find /home/deploy/project/kis_unified_sts/logs -name "*.log.gz" -mtime +30 -delete`

## Registration (manual)

1. Review the entries above
2. Edit crontab:
   ```
   crontab -e
   ```
3. Add any missing entries
4. Verify:
   ```
   crontab -l
   ```

## Verification after registration

For the equity snapshot entry, run the script once manually first:
```bash
/home/deploy/project/kis_unified_sts/scripts/cron/publish_equity_snapshot.sh
tail -20 /home/deploy/project/kis_unified_sts/logs/equity_snapshot_$(date +%Y%m%d).log
```
Expected: two "Published ... equity snapshot" lines (stock + futures) with no errors.
```

- [ ] **Step 3: 커밋**

```bash
git add docs/operations/crontab.md
git commit -m "docs(ops): document crontab including equity_snapshot entry (manual registration)"
```

- [ ] **Step 4: 사용자에게 등록 요청**

운영 단계 명시적으로 안내:

```
운영 단계:
  crontab -e
  # 다음 줄 추가:
  40 15 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/publish_equity_snapshot.sh

  crontab -l | grep equity_snapshot   # 등록 확인
```

---

## Phase 3 — Code Quality Polish

### Task 3.1: CLICKHOUSE_PASSWORD 기본값 제거 (TDD)

**목적:** `scripts/analysis/rl_backtest_2026q1.py` / `rl_backtest_with_mini_scaler.py`에서 `os.getenv("CLICKHOUSE_PASSWORD", "@1tidh6ls6ls")`의 하드코딩된 기본값 제거. 공통 helper로 통합.

**Files:**
- Create: `shared/db/utils.py`
- Create: `tests/unit/db/test_utils.py`
- Modify: `scripts/analysis/rl_backtest_2026q1.py`
- Modify: `scripts/analysis/rl_backtest_with_mini_scaler.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/unit/db/test_utils.py
"""shared.db.utils helpers — env-based ClickHouse client construction."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from shared.db.utils import clickhouse_client_from_env


class TestClickhouseClientFromEnv:
    def test_uses_env_vars(self, monkeypatch):
        monkeypatch.setenv("CLICKHOUSE_HOST", "h")
        monkeypatch.setenv("CLICKHOUSE_PORT", "9999")
        monkeypatch.setenv("CLICKHOUSE_USER", "u")
        monkeypatch.setenv("CLICKHOUSE_PASSWORD", "p")
        with patch("clickhouse_connect.get_client") as mocked:
            clickhouse_client_from_env(database="test_db")
        mocked.assert_called_once_with(
            host="h", port=9999, user="u", password="p", database="test_db"
        )

    def test_defaults_password_to_empty(self, monkeypatch):
        monkeypatch.setenv("CLICKHOUSE_HOST", "h")
        monkeypatch.delenv("CLICKHOUSE_PASSWORD", raising=False)
        with patch("clickhouse_connect.get_client") as mocked:
            clickhouse_client_from_env(database="test_db")
        assert mocked.call_args.kwargs["password"] == ""

    def test_database_is_required(self):
        with pytest.raises(ValueError, match="database"):
            clickhouse_client_from_env(database="")
```

Run → FAIL (module doesn't exist).

- [ ] **Step 2: Create `shared/db/utils.py`**

```python
"""Shared ClickHouse helpers for analysis scripts.

Centralizes connection construction so scripts do not duplicate env-var
handling or hardcode fallback credentials. All values come from env; no
defaults for secrets.
"""
from __future__ import annotations

import os
from typing import Any


def clickhouse_client_from_env(*, database: str) -> Any:
    """Construct a clickhouse_connect.Client using CLICKHOUSE_* env vars.

    Args:
        database: ClickHouse database to connect to (required).

    Raises:
        ValueError: if database is empty.
        ImportError: if clickhouse_connect is not installed.
    """
    if not database:
        raise ValueError("database is required (non-empty)")

    import clickhouse_connect  # local import to avoid hard dep for tests

    return clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        user=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        database=database,
    )
```

- [ ] **Step 3: Test passes**

```bash
pytest tests/unit/db/test_utils.py -v
```
Expected: 3 passed.

- [ ] **Step 4: 분석 스크립트 리팩터링**

`scripts/analysis/rl_backtest_2026q1.py`:

```python
# BEFORE:
import clickhouse_connect
ch = clickhouse_connect.get_client(
    host=os.getenv("CLICKHOUSE_HOST", "localhost"),
    port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
    user=os.getenv("CLICKHOUSE_USER", "default"),
    password=os.getenv("CLICKHOUSE_PASSWORD", "@1tidh6ls6ls"),
    database="kospi",
)

# AFTER:
from shared.db.utils import clickhouse_client_from_env
ch = clickhouse_client_from_env(database="kospi")
```

Same replacement in `scripts/analysis/rl_backtest_with_mini_scaler.py`. Remove now-unused `clickhouse_connect` and `os` imports if they become orphan.

- [ ] **Step 5: 실행 확인 (scripts still work)**

```bash
source .venv/bin/activate
source .env  # ensure CLICKHOUSE_PASSWORD is in env
python scripts/analysis/rl_backtest_2026q1.py 2>&1 | tail -5
```
Expected: script still runs (may print backtest result, or error gracefully with env guidance if password missing — both OK). No `@1tidh6ls6ls` literal remains in code.

```bash
grep -rn "@1tidh6ls6ls" scripts/ shared/ services/ 2>/dev/null | head -5
```
Expected: zero matches.

- [ ] **Step 6: 커밋**

```bash
git add shared/db/utils.py tests/unit/db/test_utils.py \
        scripts/analysis/rl_backtest_2026q1.py \
        scripts/analysis/rl_backtest_with_mini_scaler.py
git commit -m "refactor(db): centralize ClickHouse client construction; remove hardcoded password default"
```

### Task 3.2: `publish_signal` 도스트링 추가

**Files:**
- Modify: `shared/streaming/trading_state.py`

- [ ] **Step 1: 현재 publish_signal 찾기**

```bash
grep -n "def publish_signal\|def publish_position" shared/streaming/trading_state.py | head -5
```

- [ ] **Step 2: 도스트링 추가**

Replace the existing `def publish_signal(self, signal) -> None:` body start with:

```python
    def publish_signal(self, signal) -> None:
        """Push a trading signal to `trading:{asset}:signals` LIST.

        The signal's own timestamp is serialized (not wall-clock at publish time)
        so downstream consumers see the actual signal generation time. If the
        signal's timestamp is naive, it is assumed to be UTC (see _tz_aware_iso).

        TTL: LIST is capped at 200 entries and refreshed to STATUS_TTL_SECONDS
        on every write.
        """
        # ... existing body unchanged ...
```

Do the same light-touch for `publish_position_opened`, `publish_position_closed` — one-liner describing the source of timestamp.

- [ ] **Step 3: 회귀 확인 + 커밋**

```bash
pytest tests/unit/streaming/ -q --no-header 2>&1 | tail -3
```

```bash
git add shared/streaming/trading_state.py
git commit -m "docs(streaming): add docstrings to publish_signal / publish_position_* documenting timestamp source"
```

### Task 3.3: `load_rl_scaler` None defensive guard (TDD)

**Files:**
- Modify: `shared/strategy/rl_model_helpers.py` line ~82
- Test: append to existing `tests/unit/ml/rl/` test for rl_model_helpers (find it; if missing, create a minimal test)

- [ ] **Step 1: Find existing test file for rl_model_helpers**

```bash
find tests -name "*rl_model_helpers*" -o -name "*test_scaler*" 2>/dev/null | head -5
```

If none exists, create `tests/unit/ml/rl/test_rl_model_helpers.py`.

- [ ] **Step 2: 실패 테스트 작성**

Append (or create) test file:

```python
"""load_rl_scaler — defensive guard regression."""
from shared.strategy.rl_model_helpers import load_rl_scaler


def test_load_rl_scaler_accepts_none_path(tmp_path, monkeypatch):
    """Passing scaler_path=None (config key missing) must not crash with
    AttributeError: 'NoneType' object has no attribute 'strip'.
    """
    monkeypatch.delenv("RL_MPPO_SCALER_PATH", raising=False)
    monkeypatch.delenv("RL_MPPO_MODEL_PATH", raising=False)

    # Provide a bogus model_path (nonexistent) — guard should degrade gracefully,
    # not raise AttributeError on None.strip()
    result = load_rl_scaler(None, str(tmp_path / "nonexistent" / "model.zip"))
    assert result is None  # scaler not found → None
```

Run → may FAIL with AttributeError (or already defensively handled via `config.scaler_path: str = ""` default, in which case test passes but guards future callers).

- [ ] **Step 3: Fix line 82**

In `shared/strategy/rl_model_helpers.py`:

```python
    # BEFORE (line 82):
    elif scaler_path.strip():
        effective_path = scaler_path.strip()

    # AFTER:
    elif scaler_path and scaler_path.strip():
        effective_path = scaler_path.strip()
```

- [ ] **Step 4: Run test + regression**

```bash
pytest tests/unit/ml/rl/ -q --no-header 2>&1 | tail -5
```
Expected: all pass.

- [ ] **Step 5: 커밋**

```bash
git add shared/strategy/rl_model_helpers.py tests/unit/ml/rl/test_rl_model_helpers.py
git commit -m "fix(rl): defensive None guard in load_rl_scaler.scaler_path"
```

---

## Final

### Task 4: Full regression + PR

- [ ] **Step 1: 전체 관련 테스트**

```bash
cd /home/deploy/project/kis_unified_sts && source .venv/bin/activate
pytest tests/unit/db/ tests/unit/ml/rl/ tests/unit/streaming/ -q --no-header 2>&1 | tail -10
```

- [ ] **Step 2: Push + PR**

```bash
git push -u origin fix/ops-hardening-and-polish
gh pr create --base main --title "fix: ops hardening (model write guard, equity cron docs) + code polish" \
  --body "$(cat <<'EOF'
## Summary

Follow-ups after PR #120 / #121:

### Phase 1 — Incident prevention (mppo_best overwrite)
- `shared/ml/rl/model_paths.py::check_save_path` + CLI `--promote` flag
- `scripts/ops/{lock,unlock}_champion_model.sh` for file-permission hardening

### Phase 2 — Equity snapshot cron registration
- `docs/operations/crontab.md` listing all production cron entries
- Manual registration step documented, not applied to server in this PR

### Phase 3 — Code polish
- `shared/db/utils.py::clickhouse_client_from_env` — centralized ClickHouse connection
- Remove hardcoded password default from `rl_backtest_2026q1.py` and `rl_backtest_with_mini_scaler.py`
- `publish_signal` / `publish_position_*` docstrings clarifying timestamp source
- `load_rl_scaler` defensive None guard

## Test plan

- [x] Model path guard: 6 new unit tests
- [x] ClickHouse utils: 3 new unit tests
- [x] `load_rl_scaler` None defensive test: 1 new
- [x] No `@1tidh6ls6ls` literal remains in code (grep)
- [x] Full related regression passes
- [ ] **Operator step (post-merge):** run `scripts/ops/lock_champion_model.sh` to lock the restored champion
- [ ] **Operator step (post-merge):** `crontab -e` to add the `publish_equity_snapshot.sh` entry per `docs/operations/crontab.md`

## Deferred

Baseline RL retraining tracked separately in `docs/plans/2026-04-15-rl-retraining-data-refresh.md` — not included here.

🤖 Generated with [Claude Code](https://claude.ai/code)
EOF
)"
```

---

## Self-Review Checklist

- [x] Phase 1 Task 1.1 — write guard with TDD, 6 tests ✓
- [x] Phase 1 Task 1.2 — file permission scripts + docs ✓
- [x] Phase 2 — crontab registration documented (manual operator step) ✓
- [x] Phase 3 Task 3.1 — DRY extraction + password default removal + TDD ✓
- [x] Phase 3 Task 3.2 — docstrings only ✓
- [x] Phase 3 Task 3.3 — defensive guard with TDD ✓
- [x] All risky ops (chmod, crontab) kept as documented manual steps, NOT applied in PR ✓
- [x] RL retraining out of scope — pointer to existing plan ✓
- [x] Type consistency: `check_save_path` signature / `RLPathGuardError` / `PRODUCTION_CHAMPION_DIR` used consistently ✓
- [x] Each task ends with TDD + commit ✓

## Open Questions for Executor

1. **Promote flag threading for hybrid training**: is there another `train_rl_hybrid.py` or similar that also saves to `save_dir`? If yes, apply the same guard there too (check `scripts/training/` for multiple save sites).
2. **Existing crontab entries**: user may already have some cron entries; do not replace, only append missing ones.
3. **clickhouse_connect version**: if project uses a different client lib (e.g., `clickhouse_driver` for native 9000 port), adapt the helper accordingly. Verify by `grep clickhouse_connect scripts/`.
