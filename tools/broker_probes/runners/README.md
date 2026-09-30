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

# 2. the instance
export PCA_LOG=~/.config/kis-probes/p-ca-20261022.log
export PCA_ENV_FILE=~/.config/kis-probes/backups/.env.mock.bak-20260915-mock-reapply
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
export PCA_REFERENCE_CHECK=1        # also GET the ksdinfo TR before polling
export PCA_EFFECTIVE=...            # required for every class but cash_dividend
                                    # (a space-separated ISO value is fine)
export PCA_CRON_MARK=run_p_ca_20261022   # remove this one crontab line when done

# 3. run it from the worktree's own copy — that is how it finds the checkout
/home/deploy/.local/state/kis/wt-pca/tools/broker_probes/runners/run_p_ca.sh
```

`PCA_EXPECT_ACCOUNT_FP` is what `tools/broker_probes/common.py::account_fingerprint`
prints for the account number in `PCA_ENV_FILE`; `PCA_EXPECT_KEY_FP` is
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
  whatever the results directory already held.
- Cron: set `CRON_TZ=Asia/Seoul`, and give the entry an absolute path plus the
  `PCA_*` exports (a cron shell inherits almost nothing).
