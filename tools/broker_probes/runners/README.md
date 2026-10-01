# Probe runners

Tracked runner **templates**. A template carries the guards and the call
shape; every instance value (symbol, times, window, pacing, credential file,
expected fingerprints) comes from the environment and has **no default**, so
an unset variable aborts the run instead of quietly inheriting somebody else's
trial.

They are tracked because the 2026-09-30 P-CA runner was not: it lived only in
`~/.config/kis-probes/` and deleted itself after its first run, so attempts 3
and 4 went out through a hand-made copy and the review could not establish
afterwards which script had actually run
(`docs/plans/2026-09-30-probe-transient-error-policy-plan.md` §2.2).

## `run_p_ca.sh` — P-CA corporate-action reflection

Run it **from a detached worktree**, never from a shared checkout: a parallel
lane moving the branch under a running probe is what stamped a non-`main`
`repo_commit` into the #793 artifacts. The script enforces this itself — clean
`git status --short`, detached `HEAD`, `HEAD` an ancestor of `origin/main` —
and refuses otherwise. `PCA_ALLOW_SHARED_CHECKOUT=1` skips those three checks
and logs a warning; use it only when the artifact's provenance does not matter.

```bash
# 1. a throwaway detached worktree on merged code
git -C /home/deploy/project/kis_unified_sts fetch -q origin
git -C /home/deploy/project/kis_unified_sts worktree add --detach \
    /home/deploy/.local/state/kis/wt-pca origin/main

# 2. the interpreter — the MAIN checkout's venv. A freshly added worktree has
#    no .venv, and installing one into it is not allowed (never pip install
#    into the shared root venv). The runner exports PYTHONPATH=$REPO itself and
#    then PROVES the tools.broker_probes it loads is the worktree's, because
#    `repo_commit` and the results directory follow the loaded module, not the
#    runner's $REPO.
export PCA_PYTHON=/home/deploy/project/kis_unified_sts/.venv/bin/python

# 3. the instance
export PCA_LOG=~/.config/kis-probes/p-ca-20261022.log
export PCA_CREDENTIAL_FILE=.env.mock   # relative -> this worktree, copied in if absent
                                      # absolute -> used as given, never copied, e.g.
                                      # ~/.config/kis-probes/backups/.env.mock.bak-20260915-mock-reapply
export PCA_KIS_ENV=mock                       # mock | real (real is GET-only here)
export PCA_SYMBOL=058610
export PCA_EVENT_CLASS=cash_dividend
export PCA_PAYABLE=2026-10-22T00:00:00+09:00  # ISO-8601 WITH offset, already past
export PCA_WINDOW_S=57600
export PCA_POLL_MS=30000
export PCA_PACE_S=1.5
export PCA_EXPECT_KEY_FP=<sha256(app key)[:12]>
export PCA_EXPECT_ACCOUNT_FP=<account_fingerprint(account no)>
export PCA_TOKEN_CACHE=~/.config/kis-probes/p-ca-20261022-token-cache
export PCA_EVIDENCE_DIR=/path/to/docs/broker-profiles/evidence/<campaign>
export PCA_NOTE="t3 P-CA trial 3: ..."

# optional
export PCA_REFERENCE_CHECK=1        # also GET the ksdinfo TR before polling — and,
                                    # for a cash dividend, compare the broker's
                                    # divi_pay_dt with PCA_PAYABLE first (see below)
export PCA_EFFECTIVE=...            # required for every class but cash_dividend,
                                    # and checked before anything touches the
                                    # broker (a space-separated ISO value is fine)
export PCA_CRON_MARK=run_p_ca_20261022   # remove this one crontab line when done

# optional, and only read when PCA_REFERENCE_CHECK=1 on a cash dividend
export PCA_RECORD_DATE=20260930          # YYYYMMDD — narrows the comparison to one
                                         # 기준일, and anchors F_DT on it;
                                         # unset = every row the broker returned
export PCA_ALLOW_PAYDATE_MISMATCH=1      # proceed on a mismatch, with a WARN
export PCA_REQUIRE_REFERENCE_ROW=1       # ABORT when the table returns no usable row

# 4. run it from the worktree's own copy — that is how it finds the checkout
/home/deploy/.local/state/kis/wt-pca/tools/broker_probes/runners/run_p_ca.sh
```

### The pay-date pre-check (#830)

With `PCA_REFERENCE_CHECK=1` on a `cash_dividend`, the runner asks the broker
what IT thinks the pay date is **before** the polling window is spent, and
aborts when the two disagree. The step costs one extra ksdinfo GET and runs
after the holding check:

```
holding check → [pace] → probe --reference-only → compare → [pace] → probe
```

`--reference-only` is the probe's own mode: one ksdinfo GET, no balance call,
no holding requirement, no polling, and a **future** `--payable-time` is
accepted there (nothing is paired against it). It writes a normal artifact,
which the runner copies to **`$PCA_EVIDENCE_DIR/reference-only/`** on the same
newer-than guard the trial artifact gets — so the pre-check leaves evidence
even when the comparison then aborts the run, without putting a lookup where a
`P-CA-*.json` glob of the evidence directory would read it as a completed
observation. (The artifact also carries `args.reference_only: true` and skips
each leg with a `REFERENCE_ONLY` reason, so a reader has three ways to tell
the two apart.) A copy that fails logs a WARN and does not count as done.

Because the pre-check already made the call, the trial itself is run **without**
`--reference-check`; the rows go into the trial's `--note`. One ksdinfo GET per
slot, not two.

The probe prints the rows on anchored lines and the runner reads only those:

```
REFERENCE_WINDOW=<F_DT>-<T_DT>
REFERENCE_STATUS=<one of OK NO_ROWS UNSUPPORTED TRANSIENT_STOP RATE_LIMITED>[:detail]
REFERENCE_ROWS=<n>
REFERENCE_ROW=<record_date>|<divi_pay_dt>     # both YYYYMMDD, digits only
```

Exactly one `REFERENCE_STATUS=` line is printed, on every path the probe can
leave by. `TRANSIENT_STOP` and `RATE_LIMITED` mean the path to the broker is
unhealthy right now, so the runner **aborts** rather than starting a 16-hour
poll down it — and so does a missing line, which is what a crash looks like
from here. Only `OK`, `NO_ROWS` and `UNSUPPORTED` let the trial start.

What the runner then does with the rows:

| outcome | default | override |
| --- | --- | --- |
| **any** candidate row's `divi_pay_dt` equals `PCA_PAYABLE`'s KST date | logged, run proceeds | — |
| candidate rows carry pay dates and **none** match | **ABORT**, every date seen is logged | `PCA_ALLOW_PAYDATE_MISMATCH=1` → WARN + proceed |
| no candidate row, or none with a `divi_pay_dt` | WARN + proceed (record-only) | `PCA_REQUIRE_REFERENCE_ROW=1` → ABORT |

"Any row", not "the latest row": the window reaches 180 days past the pay date,
so a quarterly payer's answer carries the next dividend too, and comparing
against the newest 기준일 aborted slots on a row that was never the trial's.
The same answer can also hold two rows under one 기준일 — cash and stock — of
which only the cash row has a `divi_pay_dt`.

`PCA_RECORD_DATE` (`YYYYMMDD`) narrows the candidates to one 기준일 and is
never required. When it is set the runner also sends `--reference-from` as
`PCA_RECORD_DATE − 1 day`, because the ksdinfo window filters on 기준일 and an
`F_DT` equal to it is a boundary, not a margin.

`PCA_PAYABLE` is converted to **KST** before its date is taken. The probe
accepts a non-KST offset on `--payable-time` (it warns rather than refusing),
and `2026-10-21T15:00:00Z` is the same instant as 2026-10-22 00:00 KST.

Why the mode exists at all: on 2026-10-01 a pre-check of the next target was
refused `rc 4` before any reference GET, because `--payable-time` was in the
future — a rule written for the polling path. The same day's re-observation
got zero rows because the ksdinfo `F_DT`/`T_DT` window was anchored on the RUN
CLOCK, and the row's 기준일 had walked out of it overnight. The window is now
anchored on the operator's t0 as well as the run clock, spanning both, and the
lookback is sized for the 기준일→지급일 gap (120 days) rather than for
"recent" — every anchor the probe has is a time that FOLLOWS the record date
the window filters on, and 30 days excluded every annual dividend.
`--reference-from`/`--reference-to` (`YYYYMMDD`) override either end for an
issuer outside even that.

### The credential file

`PCA_CREDENTIAL_FILE` is read two ways:

- **Relative** (the documented case, `.env.mock`): resolved against the
  worktree. The name must be one `git check-ignore` accepts, and the runner
  refuses otherwise **before writing anything** — this repository ignores
  exact names (`.env`, `.env.mock`, `.env.real`, `.env.paper`, `.env.live`,
  `.env.production`, `.env.local`, `.env.*.local`), **not** a `.env.*` glob,
  so a name like `.env.mock.bak-20260915` would land a filled credential file
  where `git add -A` stages it. A freshly added worktree carries none of these
  files, so the runner copies it in from the **primary checkout** — located from the first entry of `git worktree list --porcelain`,
  never a hardcoded path, so it keeps working when the checkout moves. The copy
  is `install -m 600`, one log line names the source and destination **paths
  only**, and the run refuses when the file is in neither checkout, naming
  both. The copy persists; `.env.*` is gitignored, so it does not make the
  worktree dirty for the next run's clean-checkout guard.
- **Absolute** (e.g. the 2026-09-15 credential backup under `~/.config`): used
  exactly as given, never copied anywhere.

`PCA_EXPECT_ACCOUNT_FP` is what `tools/broker_probes/common.py::account_fingerprint`
prints for the account number in `PCA_CREDENTIAL_FILE`; `PCA_EXPECT_KEY_FP` is
`printf '%s' "$KIS_STOCK_APP_KEY" | sha256sum | cut -c1-12`. Both are checked
before the probe starts, because the 2026-09-23 `INVALID_CHECK_ACNO` outage was
a key paired with the wrong account, not a propagation delay.

Notes:

- The script **never deletes itself**. `PCA_CRON_MARK` removes only the one
  matching `crontab -l` line, and only after the probe has actually run — an
  early ABORT leaves the schedule in place so the next slot can retry.
- The holding check runs on the probe's own reader
  (`python -m tools.broker_probes.probes_ca --check-holding`), which pages
  through the balance and classifies the result. It prints exactly one of
  `HELD=<n>` (exit 0) or `HOLDING_QUERY_FAILED=<kind>:<detail>` (exit
  non-zero), and the runner parses only those two anchored forms. It does
  **not** use `shared/kis/client.py::get_stock_balance`, which returns `[]` on
  every failure and reads page 1 only — that is how the 09-30 10:58 attempt
  logged `held qty=0` for a query that had errored (a direct GET two minutes
  later showed qty 1), and how a holding on page 2 of the 25-row mock account
  would read as "not held".
- The artifact is copied to `PCA_EVIDENCE_DIR` only when it is newer than
  whatever the results directory already held. With the pay-date pre-check on,
  there are two such copies — the reference-only artifact and the trial's.
- The runner and the probe must be the same generation: the probe reports a
  `POLICY_VERSION` and the runner checks it against the version it was written
  for. A mismatch means the runner was copied out of a different tree, which
  is the 2026-09-30 mistake. (This replaced grepping `probes_ca.py` for
  substrings, which could not tell a fix from a mention and broke on renames.)
- `PCA_LOG`'s directory is created if missing, and the run aborts if it cannot
  be. The crontab entry is retired only once the probe has actually started.
- One `PCA_PACE_S` wait separates each pair of processes — holding check,
  pay-date pre-check, probe. They have independent pacers, so without it one
  process's first GET follows the previous one's last with no gap — the
  back-to-back pair that produced the 2026-09-17 `EGW00201` stop, which stays
  a no-retry stop.
- Cron: set `CRON_TZ=Asia/Seoul`, and give the entry an absolute path plus the
  `PCA_*` exports, `PCA_PYTHON` included (a cron shell inherits almost
  nothing).
