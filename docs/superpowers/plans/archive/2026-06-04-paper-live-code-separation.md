# Paper/Live Source-Code Separation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the repo-committed tooling that lets LIVE trading run only validated (annotated-tag) code from a separate clone, while paper/dev keeps tracking `main` — a preflight guardrail, a promotion helper, a live cron template, and an operator runbook.

**Architecture:** Two independent clones on one host: existing `kis_unified_sts` (paper/dev, `main`) and new `kis_unified_sts_live` (pinned to a validated annotated tag). LIVE trading runs via host venv + cron; a `live_preflight.sh` gate refuses to start unless the live clone is a clean annotated tag with the isolated live Redis (port 6382) configured + reachable. `promote_live.sh` moves the live clone to a new validated tag. Clone creation, `.env.live` secrets, and cron install are operator host steps documented in a runbook (never automated/committed).

**Tech Stack:** Bash (scripts), pytest + subprocess (tests for the scripts), git (tags/clones), cron (KST), Docker compose redis (per-env isolation 6381/6382).

**Spec:** `docs/superpowers/specs/2026-06-04-paper-live-code-separation-design.md`

**Branch:** `feat/paper-live-code-separation` (spec already committed here).

---

## File Structure

| Path | Responsibility | Action |
|---|---|---|
| `scripts/ops/live_preflight.sh` | Guardrail: refuse live start unless clean annotated tag + live Redis port configured/reachable | Create |
| `scripts/ops/promote_live.sh` | Promote a validated annotated tag into the live clone (fetch/checkout/deps/preflight) | Create |
| `tests/unit/ops/test_live_preflight.py` | Accept/reject cases for the guardrail | Create |
| `tests/unit/ops/test_promote_live.py` | Promote happy-path + rejects (lightweight/unknown) | Create |
| `tests/unit/ops/test_live_cron_template.py` | Lint the cron template (KST, preflight gate, live flags, no paper paths) | Create |
| `deploy/cron/kis-live.crontab.example` | Committed example LIVE crontab (operator installs on host) | Create |
| `docs/runbooks/paper-live-code-separation.md` | Operator runbook: clone, venv, .env.live, redis, cron, promote, rollback, verify | Create |
| `CLAUDE.md` | One-paragraph note: live runs validated tags from the live clone | Modify |

Notes:
- `tests/unit/ops/` is a new namespace dir — **do NOT add `__init__.py`** (repo uses namespace packages; sibling `__init__.py` caused collection collisions historically).
- Scripts must be committed with the executable bit set.

---

## Task 1: Live preflight guardrail (`live_preflight.sh`)

**Files:**
- Create: `scripts/ops/live_preflight.sh`
- Test: `tests/unit/ops/test_live_preflight.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/ops/test_live_preflight.py`:

```python
"""Tests for scripts/ops/live_preflight.sh (live validated-code guardrail)."""
from __future__ import annotations

import os
import socket
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PREFLIGHT = REPO / "scripts" / "ops" / "live_preflight.sh"

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
}


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True,
        env={**os.environ, **_GIT_ENV},
    )


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "live"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "f.txt").write_text("x")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    return repo


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _run(repo: Path, **env: str) -> subprocess.CompletedProcess:
    full = {
        **os.environ,
        "KIS_LIVE_PROJECT": str(repo),
        "LIVE_PREFLIGHT_CHECK_REDIS": "0",
        "REDIS_PORT": "6382",
        **env,
    }
    return subprocess.run(
        ["bash", str(PREFLIGHT)], capture_output=True, text=True, env=full
    )


def test_passes_on_clean_annotated_tag(tmp_path):
    repo = _make_repo(tmp_path)
    _git(repo, "tag", "-a", "v2026.06.04", "-m", "validated")
    r = _run(repo)
    assert r.returncode == 0, r.stderr


def test_fails_when_not_on_tag(tmp_path):
    repo = _make_repo(tmp_path)
    r = _run(repo)
    assert r.returncode != 0
    assert "annotated tag" in r.stderr


def test_fails_on_lightweight_tag(tmp_path):
    repo = _make_repo(tmp_path)
    _git(repo, "tag", "v-light")  # lightweight, not annotated
    r = _run(repo)
    assert r.returncode != 0
    assert "annotated tag" in r.stderr


def test_fails_when_dirty(tmp_path):
    repo = _make_repo(tmp_path)
    _git(repo, "tag", "-a", "v1", "-m", "v")
    (repo / "f.txt").write_text("changed")
    r = _run(repo)
    assert r.returncode != 0
    assert "dirty" in r.stderr


def test_fails_on_wrong_redis_port(tmp_path):
    repo = _make_repo(tmp_path)
    _git(repo, "tag", "-a", "v1", "-m", "v")
    r = _run(repo, REDIS_PORT="6381")  # paper's port -> isolation breach
    assert r.returncode != 0
    assert "isolation" in r.stderr.lower()


def test_fails_when_redis_unreachable(tmp_path):
    repo = _make_repo(tmp_path)
    _git(repo, "tag", "-a", "v1", "-m", "v")
    closed = str(_free_port())
    r = _run(
        repo,
        LIVE_PREFLIGHT_CHECK_REDIS="1",
        REDIS_PORT=closed,
        LIVE_EXPECT_REDIS_PORT=closed,
    )
    assert r.returncode != 0
    assert "not reachable" in r.stderr
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/unit/ops/test_live_preflight.py -q`
Expected: FAIL/ERROR — script does not exist yet (non-zero exit; tests error on missing `scripts/ops/live_preflight.sh`).

- [ ] **Step 3: Write the script**

Create `scripts/ops/live_preflight.sh`:

```bash
#!/usr/bin/env bash
# live_preflight.sh — refuse to start LIVE trading unless the live checkout is
# pinned to a CLEAN ANNOTATED git tag (= validated code) and the isolated live
# Redis is configured + reachable. Exits 0 only when all checks pass.
#
# Env:
#   KIS_LIVE_PROJECT            live clone dir (default: repo root of this script)
#   REDIS_PORT                  live Redis port from .env (must equal expected port)
#   LIVE_EXPECT_REDIS_PORT      expected live Redis port (default 6382)
#   REDIS_HOST                  default 127.0.0.1
#   LIVE_PREFLIGHT_CHECK_REDIS  1=check reachability (default), 0=skip
set -euo pipefail

DIR="${KIS_LIVE_PROJECT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
REDIS_HOST="${REDIS_HOST:-127.0.0.1}"
REDIS_PORT="${REDIS_PORT:-}"
EXPECT_REDIS_PORT="${LIVE_EXPECT_REDIS_PORT:-6382}"
CHECK_REDIS="${LIVE_PREFLIGHT_CHECK_REDIS:-1}"

fail() { echo "live-preflight: REFUSE — $1" >&2; exit 1; }

# 1) HEAD must be pinned to an ANNOTATED tag (a validated release).
annotated=""
while read -r t; do
  [ -n "$t" ] || continue
  if [ "$(git -C "$DIR" cat-file -t "refs/tags/$t" 2>/dev/null)" = "tag" ]; then
    annotated="$t"
    break
  fi
done < <(git -C "$DIR" tag --points-at HEAD 2>/dev/null)
[ -n "$annotated" ] || fail "HEAD is not pinned to an annotated tag (validated code required)"

# 2) Working tree must be clean (no edits after validation).
[ -z "$(git -C "$DIR" status --porcelain 2>/dev/null)" ] || fail "working tree is dirty"

# 3) Redis isolation: live .env must target the live port, not paper's.
[ "$REDIS_PORT" = "$EXPECT_REDIS_PORT" ] \
  || fail "REDIS_PORT='$REDIS_PORT' but expected live port $EXPECT_REDIS_PORT (Redis isolation)"

# 4) Live Redis reachable (TCP port open).
if [ "$CHECK_REDIS" = "1" ]; then
  if ! (exec 3<>"/dev/tcp/$REDIS_HOST/$REDIS_PORT") 2>/dev/null; then
    fail "live Redis $REDIS_HOST:$REDIS_PORT not reachable"
  fi
  exec 3>&- || true
fi

echo "live-preflight: OK — tag=$annotated (clean), redis=$REDIS_HOST:$REDIS_PORT"
```

- [ ] **Step 4: Make it executable**

Run: `chmod +x scripts/ops/live_preflight.sh`

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/bin/pytest tests/unit/ops/test_live_preflight.py -q`
Expected: PASS (6 passed).

- [ ] **Step 6: Commit**

```bash
git add scripts/ops/live_preflight.sh tests/unit/ops/test_live_preflight.py
git commit -m "feat: add live preflight guardrail (validated-tag + clean + redis isolation)"
```

---

## Task 2: Promotion helper (`promote_live.sh`)

**Files:**
- Create: `scripts/ops/promote_live.sh`
- Test: `tests/unit/ops/test_promote_live.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/ops/test_promote_live.py`:

```python
"""Tests for scripts/ops/promote_live.sh (promote validated tag into live clone)."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PROMOTE = REPO / "scripts" / "ops" / "promote_live.sh"

_GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
}


def _git(cwd: Path, *args: str, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=capture, text=True,
        env={**os.environ, **_GIT_ENV},
    )


def _origin_and_live(tmp_path: Path):
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(origin, "init", "-q")
    (origin / "f.txt").write_text("x")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-qm", "init")
    _git(origin, "tag", "-a", "v1", "-m", "validated")  # annotated
    _git(origin, "tag", "v-light")  # lightweight
    live = tmp_path / "live"
    _git(tmp_path, "clone", "-q", str(origin), str(live))
    return origin, live


def _promote(live: Path, tag: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "KIS_LIVE_PROJECT": str(live), "PROMOTE_CHECK_REDIS": "0", "REDIS_PORT": "6382"}
    return subprocess.run(
        ["bash", str(PROMOTE), tag], capture_output=True, text=True, env=env
    )


def test_promote_checks_out_annotated_tag(tmp_path):
    _, live = _origin_and_live(tmp_path)
    r = _promote(live, "v1")
    assert r.returncode == 0, r.stderr
    head = _git(live, "rev-parse", "HEAD").stdout.strip()
    tag_commit = _git(live, "rev-list", "-n1", "v1").stdout.strip()
    assert head == tag_commit


def test_promote_rejects_lightweight_tag(tmp_path):
    _, live = _origin_and_live(tmp_path)
    r = _promote(live, "v-light")
    assert r.returncode != 0
    assert "annotated" in r.stderr


def test_promote_rejects_unknown_tag(tmp_path):
    _, live = _origin_and_live(tmp_path)
    r = _promote(live, "v-does-not-exist")
    assert r.returncode != 0
    assert "not found" in r.stderr


def test_promote_requires_tag_arg(tmp_path):
    _, live = _origin_and_live(tmp_path)
    env = {**os.environ, "KIS_LIVE_PROJECT": str(live)}
    r = subprocess.run(["bash", str(PROMOTE)], capture_output=True, text=True, env=env)
    assert r.returncode != 0
    assert "usage" in r.stderr.lower()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/unit/ops/test_promote_live.py -q`
Expected: FAIL/ERROR — `scripts/ops/promote_live.sh` does not exist.

- [ ] **Step 3: Write the script**

Create `scripts/ops/promote_live.sh`:

```bash
#!/usr/bin/env bash
# promote_live.sh — promote a validated ANNOTATED tag into the LIVE clone:
# fetch tags, checkout (detached), refresh deps, run the preflight guardrail.
# Refuses unknown or lightweight (non-annotated) tags.
#
# Usage: promote_live.sh <annotated-tag>
# Env:
#   KIS_LIVE_PROJECT     live clone dir (default /home/deploy/project/kis_unified_sts_live)
#   PROMOTE_CHECK_REDIS  pass-through to preflight reachability check (default 0 — infra
#                        may start after promotion); the tag/clean/port checks always run
set -euo pipefail

TAG="${1:-}"
[ -n "$TAG" ] || { echo "usage: promote_live.sh <annotated-tag>" >&2; exit 64; }
LIVE_DIR="${KIS_LIVE_PROJECT:-/home/deploy/project/kis_unified_sts_live}"
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[ -d "$LIVE_DIR/.git" ] || { echo "promote: '$LIVE_DIR' is not a git clone" >&2; exit 1; }

git -C "$LIVE_DIR" fetch --tags --prune origin >/dev/null 2>&1 || true

git -C "$LIVE_DIR" rev-parse "refs/tags/$TAG" >/dev/null 2>&1 \
  || { echo "promote: tag '$TAG' not found (push the tag to origin, then retry)" >&2; exit 1; }

[ "$(git -C "$LIVE_DIR" cat-file -t "refs/tags/$TAG")" = "tag" ] \
  || { echo "promote: '$TAG' is not an annotated tag (validated releases must be annotated)" >&2; exit 1; }

git -C "$LIVE_DIR" checkout --force --detach "refs/tags/$TAG" >/dev/null 2>&1

# Refresh deps into the live venv (idempotent; skipped if the venv does not exist yet).
if [ -x "$LIVE_DIR/.venv/bin/pip" ]; then
  "$LIVE_DIR/.venv/bin/pip" install -e "$LIVE_DIR" >/dev/null
fi

# The guardrail must pass after promotion (validates tag/clean/port; redis
# reachability gated by PROMOTE_CHECK_REDIS so promotion works before infra is up).
KIS_LIVE_PROJECT="$LIVE_DIR" \
  LIVE_PREFLIGHT_CHECK_REDIS="${PROMOTE_CHECK_REDIS:-0}" \
  REDIS_PORT="${REDIS_PORT:-6382}" \
  "$SELF_DIR/live_preflight.sh"

echo "promote: LIVE now pinned to $TAG"
```

- [ ] **Step 4: Make it executable**

Run: `chmod +x scripts/ops/promote_live.sh`

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv/bin/pytest tests/unit/ops/test_promote_live.py -q`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add scripts/ops/promote_live.sh tests/unit/ops/test_promote_live.py
git commit -m "feat: add promote_live.sh (tag-pinned live promotion + preflight)"
```

---

## Task 3: LIVE cron template (`deploy/cron/kis-live.crontab.example`)

**Files:**
- Create: `deploy/cron/kis-live.crontab.example`
- Test: `tests/unit/ops/test_live_cron_template.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/ops/test_live_cron_template.py`:

```python
"""Lint the committed LIVE crontab example."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CRON = REPO / "deploy" / "cron" / "kis-live.crontab.example"


def test_cron_example_exists_and_is_kst_preflight_gated():
    text = CRON.read_text(encoding="utf-8")
    # KST native (project rule: all cron is KST)
    assert "CRON_TZ=Asia/Seoul" in text
    # Every trade-start entry must be gated by the preflight guardrail
    assert "scripts/ops/live_preflight.sh" in text
    # Live flags + isolated live project, not paper
    assert "--live" in text and "--yes-live" in text
    assert "KIS_LIVE_PROJECT=/home/deploy/project/kis_unified_sts_live" in text
    # Must not point at the paper/dev clone
    assert "/home/deploy/project/kis_unified_sts/.venv" not in text
    assert "--paper" not in text


def test_every_trade_start_line_is_preflight_gated():
    for raw in CRON.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("#") or "trade start" not in line:
            continue
        assert "live_preflight.sh &&" in line, f"unguarded live trade start: {line}"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/unit/ops/test_live_cron_template.py -q`
Expected: FAIL — `deploy/cron/kis-live.crontab.example` does not exist.

- [ ] **Step 3: Write the cron template**

Create `deploy/cron/kis-live.crontab.example`:

```cron
# KIS Unified STS — LIVE trading crontab (host venv + cron, validated code only).
#
# Install on the host ONLY AFTER (see docs/runbooks/paper-live-code-separation.md):
#   1. Created the live clone /home/deploy/project/kis_unified_sts_live and pinned
#      it to a validated annotated tag (scripts/ops/promote_live.sh <tag>).
#   2. Built its .venv and wrote .env (= .env.live, with real KIS live credentials
#      and REDIS_PORT=6382, KIS_REAL_TRADING=true).
#   3. Started the live compose redis: docker compose --env-file .env.live up -d redis
#
# All times are KST. Each trade-start is gated by live_preflight.sh, which REFUSES
# to run unless the clone is a clean annotated tag with live Redis (6382) reachable.
CRON_TZ=Asia/Seoul
KIS_LIVE_PROJECT=/home/deploy/project/kis_unified_sts_live
KIS_LIVE_PYTHON=/home/deploy/project/kis_unified_sts_live/.venv/bin/python
KIS_LIVE_LOG=/home/deploy/project/kis_unified_sts_live/logs

# Futures LIVE (Setup A/C) — start 5 min before open.
55 8 * * 1-5 cd $KIS_LIVE_PROJECT && set -a && . ./.env && set +a && bash scripts/ops/live_preflight.sh && /usr/bin/flock -nx /tmp/kis_live_futures.lock $KIS_LIVE_PYTHON -m cli.main trade start --asset futures --live --yes-live --daemon >> $KIS_LIVE_LOG/live_futures_$(date +\%Y\%m\%d).log 2>&1

# Futures LIVE watchdog — re-assert every 5 min during the session.
2-57/5 9-15 * * 1-5 cd $KIS_LIVE_PROJECT && set -a && . ./.env && set +a && bash scripts/ops/live_preflight.sh && /usr/bin/flock -nx /tmp/kis_live_futures.lock $KIS_LIVE_PYTHON -m cli.main trade start --asset futures --live --yes-live --single >> $KIS_LIVE_LOG/live_futures_watchdog_$(date +\%Y\%m\%d).log 2>&1
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/pytest tests/unit/ops/test_live_cron_template.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add deploy/cron/kis-live.crontab.example tests/unit/ops/test_live_cron_template.py
git commit -m "feat: add preflight-gated LIVE crontab example (KST, live clone)"
```

---

## Task 4: Operator runbook (`docs/runbooks/paper-live-code-separation.md`)

**Files:**
- Create: `docs/runbooks/paper-live-code-separation.md`

- [ ] **Step 1: Write the runbook**

Create `docs/runbooks/paper-live-code-separation.md`:

````markdown
# Runbook — Paper/Live Source-Code Separation

Design: `docs/superpowers/specs/2026-06-04-paper-live-code-separation-design.md`

LIVE trading runs only validated (annotated-tag) code from a **separate clone**.
paper/dev keeps tracking `main` in the existing checkout.

```
/home/deploy/project/kis_unified_sts        paper/dev — main (unchanged)
/home/deploy/project/kis_unified_sts_live   live — pinned to a validated tag
```

## 1. One-time: create the live clone (operator)

> Secrets (`.env.live`) are operator-owned. Do NOT commit them or hand them to tooling.

```bash
cd /home/deploy/project
git clone git@github.com:kakao-harris-lee/kis_unified_sts.git kis_unified_sts_live
cd kis_unified_sts_live
python3 -m venv .venv
.venv/bin/pip install -e .

# Live env: copy the template, fill REAL live KIS credentials.
cp .env.live.example .env
#   set KIS_FUTURES_APP_KEY/SECRET/ACCOUNT_NO (real), KIS_REAL_TRADING=true,
#   KIS_FUTURES_MARKET=real, REDIS_PORT=6382, RUNTIME_STORAGE_SQLITE_PATH=data/runtime/live/runtime.db
```

## 2. Start the isolated live Redis

```bash
cd /home/deploy/project/kis_unified_sts_live
docker compose --env-file .env up -d redis   # -> 127.0.0.1:6382, container kis_live-redis
```

## 3. Promote a validated build (paper -> live)

On the paper/dev checkout, after validation passes (backtest/Optuna, paper trading,
Phase 5 Gates, regime-gate counterfactual):

```bash
cd /home/deploy/project/kis_unified_sts
git tag -a v2026.06.04 -m "validated: <evidence / gate refs>"
git push origin v2026.06.04
```

Then promote into the live clone:

```bash
cd /home/deploy/project/kis_unified_sts_live
KIS_LIVE_PROJECT=$PWD scripts/ops/promote_live.sh v2026.06.04
```

`promote_live.sh` fetches the tag, checks it out (detached), refreshes the live venv,
and runs the preflight guardrail. It REFUSES lightweight/unknown tags.

## 4. Install the LIVE cron

> Only after Gate 1-3 pass + written approval. See `docs/runbooks/phase5-verification.md`.

Append `deploy/cron/kis-live.crontab.example` to the host crontab (`crontab -e`).
Every trade-start line is gated by `scripts/ops/live_preflight.sh`.

## 5. Verify

```bash
cd /home/deploy/project/kis_unified_sts_live
set -a && . ./.env && set +a
bash scripts/ops/live_preflight.sh   # expect: "live-preflight: OK — tag=... (clean), redis=127.0.0.1:6382"
git -C . describe --tags --exact-match HEAD   # must print the validated tag
```

If preflight prints `REFUSE`, live trading will NOT start — fix the cause:
- "not pinned to an annotated tag" -> run `promote_live.sh <tag>`
- "working tree is dirty" -> `git -C . restore .` (never hand-edit the live clone)
- "Redis ... isolation" -> `.env` `REDIS_PORT` must be `6382`
- "Redis ... not reachable" -> start the live compose redis (step 2)

## 6. Rollback

```bash
cd /home/deploy/project/kis_unified_sts_live
KIS_LIVE_PROJECT=$PWD scripts/ops/promote_live.sh <previous-validated-tag>
```

For an immediate halt independent of code: set the kill switch
`redis-cli -p 6382 -n 1 set futures:live:suspended 1` (see futures-paradigm-rollback runbook).

## Guarantees

- Live runs only clean, annotated-tag code (preflight refuses anything else).
- paper (6381) and live (6382) use separate Redis instances — no position/state collision.
- paper/dev checkout and its cron are unchanged; the existing live gates
  (`futures_live.enabled`, `futures:live:suspended`, `--yes-live`) still apply.
````

- [ ] **Step 2: Commit**

```bash
git add docs/runbooks/paper-live-code-separation.md
git commit -m "docs: add paper/live code-separation operator runbook"
```

---

## Task 5: Document the model in CLAUDE.md + final verification

**Files:**
- Modify: `CLAUDE.md` (add a note under the Dashboard/operations area)

- [ ] **Step 1: Add the note to CLAUDE.md**

Append a new `#### Paper/Live 소스 코드 분리` subsection at the END of the `#### 운영 대시보드 (Dashboard)` section in `CLAUDE.md` — i.e., immediately before the next `####`/`###` heading that follows the dashboard notes. Insert this block (verify the headings around the insertion point so it lands inside the Dashboard/operations area):

```markdown
#### Paper/Live 소스 코드 분리

LIVE 트레이딩은 **검증된(annotated tag) 코드만** 실행한다. paper/dev는 기존 체크아웃
`/home/deploy/project/kis_unified_sts`에서 `main`을 계속 추적하고, LIVE는 **별도 clone**
`/home/deploy/project/kis_unified_sts_live`를 검증 tag에 고정(detached)해서 호스트 venv+cron으로
돈다. 승격=`scripts/ops/promote_live.sh <tag>`, 가드레일=`scripts/ops/live_preflight.sh`
(clean annotated tag + Redis 6382 격리 아니면 비기동 거부). Redis는 paper 6381 / live 6382로
분리. 상세: `docs/runbooks/paper-live-code-separation.md`, 설계:
`docs/superpowers/specs/2026-06-04-paper-live-code-separation-design.md`.
```

- [ ] **Step 2: Run the full ops test suite**

Run: `.venv/bin/pytest tests/unit/ops -q`
Expected: PASS (12 passed: 6 preflight + 4 promote + 2 cron).

- [ ] **Step 3: Verify scripts are tracked executable**

Run: `git ls-files -s scripts/ops/live_preflight.sh scripts/ops/promote_live.sh`
Expected: mode `100755` for both (executable bit set).

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: note paper/live code separation in CLAUDE.md"
```

---

## Self-Review (completed by plan author)

- **Spec coverage:** §4 layout → runbook+CLAUDE (T4/T5); §5/§6 isolation → preflight port check (T1) + runbook redis steps (T4); §7 promotion/rollback → promote_live.sh (T2) + runbook (T4); §8 guardrail → live_preflight.sh (T1); §9 cron → cron example (T3); §11 repo-vs-operator split → runbook explicitly marks operator-only secret steps (T4). All spec sections map to tasks.
- **Placeholders:** none — every script and test is complete inline.
- **Type/name consistency:** `live_preflight.sh` env names (`KIS_LIVE_PROJECT`, `REDIS_PORT`, `LIVE_EXPECT_REDIS_PORT`, `LIVE_PREFLIGHT_CHECK_REDIS`) are used identically across the script, its tests, `promote_live.sh`, the cron example, and the runbook. `promote_live.sh` calls its sibling `live_preflight.sh` (same dir), so tests exercise the real guardrail.
- **Scope:** single subsystem (live validated-code tooling); operator host steps are documentation, not code. One plan is appropriate.
- **Out of scope (deferred):** actually creating the live clone / `.env.live` / installing live cron (operator host actions with real secrets); compose-image-based live (spec Approach C).
