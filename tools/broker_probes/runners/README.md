# Probe runners

Tracked runner **templates**. A template carries the guards and the call
shape; every instance value (symbol, times, window, pacing, credential file,
expected fingerprints) comes from the environment and has **no default**, so
an unset variable aborts the run instead of quietly inheriting somebody else's
trial.

They are tracked because the untracked ones cost measurements twice. The
2026-09-30 P-CA runner lived only in `~/.config/kis-probes/` and deleted
itself after its first run, so attempts 3 and 4 went out through a hand-made
copy and the review could not establish afterwards which script had actually
run (`docs/plans/2026-09-30-probe-transient-error-policy-plan.md` §2.2). The
2026-09-28 P-8 runner is simply gone, and the only surviving record of what it
decided is one line transcribed into the campaign README — a line that called
a `ConnectionError` a broker rejection and cancelled three of five trials
(§7.15).

`_common.sh` holds the guards both templates use: clean/detached/ancestor
checkout, required-env checking, the interpreter and module-provenance proof,
the `POLICY_VERSION` handshake, and the credential-file rule. It is sourced,
not executed. Nothing in it reads a `PCA_*` or `P8_*` variable — every
instance value arrives as an argument, including the NAME of the variable a
message should cite — so one runner cannot read the other's environment, and a
test pins that property.

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
what IT thinks the pay date is **before** anything else is spent, and aborts
when the two disagree. It is the **first** broker call of the slot — the
ksdinfo TRs need no holding, so a wrong pay date should cost one GET rather
than a balance walk on top of it:

```
probe --reference-only → compare → [pace] → holding check → [pace] → probe
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

Because the pre-check already made the call, the trial is run with
`--reference-rows-from <the pre-check's artifact>` instead of
`--reference-check`: it **adopts** that artifact's `reference_dates`,
`reference_window` and `mock_reference_support` observations verbatim, so the
trial artifact carries what it always carried and the broker is asked once per
slot. An extra observation records which artifact the rows came from, so an
adopted row is never mistaken for one the trial fetched.

The probe prints the rows on anchored lines and the runner reads only those:

```
REFERENCE_WINDOW=<F_DT>-<T_DT>
REFERENCE_STATUS=<one of OK NO_ROWS UNSUPPORTED TRANSIENT_STOP RATE_LIMITED>[:detail]
REFERENCE_ROWS=<n>
REFERENCE_ROW=<record_date>|<divi_pay_dt>     # both YYYYMMDD, digits only
```

Exactly one `REFERENCE_STATUS=` line is printed, on every path the probe can
leave by. Only `OK`, `NO_ROWS` and `UNSUPPORTED` let the trial start:

- `UNSUPPORTED` is the broker **answering** (HTTP 200, a real envelope) that
  it does not serve this TR. The path is healthy; the mock not supporting the
  reference TR must not block a trial.
- `ERROR` is a non-200 or a body that is not an envelope at all — a gateway
  page, say. `TRANSIENT_STOP` and `RATE_LIMITED` are the probe's own stops.
  All three mean the path is unhealthy right now, and the runner aborts
  rather than starting a 16-hour poll down it.
- A **missing** line aborts too: that is what a crash looks like from here.

A pre-check that printed a clean status and then **exited non-zero** is also
refused, the same rule the holding check applies to `HELD=`: the probe can
print its rows and still die writing the artifact.

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
issuer outside even that; a window that cannot contain anything is refused
before the call, including when only one end was overridden and the other was
derived.

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

## `run_p8.sh` — P-8 replace/amend semantics

Same checkout, interpreter, credential and `POLICY_VERSION` guards as
`run_p_ca.sh` (they are the shared ones in `_common.sh`). What is P-8's own is
the **trial series** and the rule that ends it.

```bash
# 1. a throwaway detached worktree on merged code
git -C /home/deploy/project/kis_unified_sts fetch -q origin
git -C /home/deploy/project/kis_unified_sts worktree add --detach \
    /home/deploy/.local/state/kis/wt-p8-run origin/main

# 2. the interpreter — the MAIN checkout's venv (a fresh worktree has no
#    .venv, and installing one into it is not allowed). The runner exports
#    PYTHONPATH itself and then PROVES the tools.broker_probes it loads is the
#    worktree's, because repo_commit and the results directory follow the
#    loaded module, not the runner's $REPO.
export P8_PYTHON=/home/deploy/project/kis_unified_sts/.venv/bin/python

# 3. the instance
export P8_LOG=~/.config/kis-probes/p8-20261005.log
export P8_CREDENTIAL_FILE=.env.mock   # relative -> this worktree, copied in if absent
                                      # absolute -> used as given, never copied
export P8_SYMBOL=A05610               # the mini near-month contract ON THE DAY
export P8_TRIALS=5                    # N>=5 is what mode_determination needs
export P8_QUANTITY=1
export P8_PRICE_OFFSET_PCT=10.0       # far from the touch: the order must REST
export P8_POLL_MS=200
export P8_PACE_S=1.1
export P8_VISIBILITY_TIMEOUT_S=30
export P8_INTER_TRIAL_S=1            # seconds; digits and at most one '.'
export P8_MAX_TRANSIENT_STOPS=2       # transport stops tolerated before giving up
export P8_EXPECT_KEY_FP=<sha256(futures app key)[:12]>
export P8_EXPECT_ACCOUNT_FP=<account_fingerprint(futures account no)>
export P8_TOKEN_CACHE=~/.config/kis-probes/p8-20261005-token-cache
export P8_EVIDENCE_DIR=/path/to/docs/broker-profiles/evidence/<campaign>
export P8_NOTE="t3 P-8 trials 3-5: ..."

# optional
export P8_ALLOW_SHARED_CHECKOUT=1     # skip the checkout guards, logged (#793)
export P8_CRON_MARK=run_p8_20261005   # remove this one crontab line when done
export P8_CANCEL_UNACCOUNTED=1        # see "The STOP rule" — off by default

# 4. run it from the worktree's own copy — that is how it finds the checkout
/home/deploy/.local/state/kis/wt-p8-run/tools/broker_probes/runners/run_p8.sh
```

### The STOP rule — four reasons, counted separately

The probe prints two anchored lines per trial, exactly one of each on every
path it can leave by, and the runner reads only those:

```
P8_STOP=<none | transient:transport | transient:ledger_throttle
       | order_state_unknown | query_unanswered | rate_limited | rejected
       | unknown | dry_run>
P8_COEXISTENCE=<measured | not_measured>
```

| token | what happened | the series |
| --- | --- | --- |
| `none` | the trial ran to its end (a REJECTED AMEND lands here — that is a replace-semantics observation) | continues |
| `transient:transport` | two consecutive transport failures on the **poll** GET (or a lost quote), after one retry a whole poll interval apart | **continues**, up to `P8_MAX_TRANSIENT_STOPS` |
| `transient:ledger_throttle` | the same, for two consecutive `EGW00215` | **continues**, same budget |
| `order_state_unknown` | a transport failure or `EGW00215` on the **submit or amend** — whether the broker accepted it is unknown | stops |
| `rate_limited` | HTTP 429 or `EGW00201`, on a poll **or on either order POST** — OUR call rate | stops |
| `query_unanswered` | the open-order surface refused every poll for the whole window, for a reason **other than** an empty book | stops |
| `rejected` | the broker refused the SUBMIT | stops |
| anything else, or no line at all | a state the probe did not name | stops |

The line between the first group and `order_state_unknown` is **"is an
order's state unknown"**, not "was it a POST". A lost quote leaves nothing
resting, so the next trial starts from a clean account. A lost submit or
amend may have been accepted and be resting right now under an ODNO the probe
never saw: before stopping, the probe walks the whole book and records what it
finds in `measurements.unaccounted_live_orders` as `FOUND`,
`FOUND_NOT_CANCELLED`, `NONE_FOUND` or `UNDETERMINED`. **Read that field
before scheduling P-8 again** — the runner says so on its last line whenever
such a stop happened. A walk that cannot answer cancels nothing and tells you
to check by hand.

Two things it will not do. It never touches a live row that does **not** match
this trial's order body (same symbol, same quantity, and the side and price
when the row carries them): that row belongs to another probe or to the
operator, it is reported as `foreign_live_rows_present`, and no flag
overrides that. And it does not cancel even a MATCHING row unless you ask:

```bash
export P8_CANCEL_UNACCOUNTED=1   # cancel rows that match this trial's body
```

The default is record-and-stop, because an orphan you are told about is a
bounded problem and a cancelled stranger is not. Without the flag the artifact
carries `cancel_odno_would_send` so you can do it by hand.

A `query_unanswered` stop is narrower than it sounds: this broker answers an
**empty result set** with a rejection shape (`rt_cd=7` / `KIOK0560`), and an
empty book is the ordinary end of a trial — both legs gone to a fill, or to a
resting price too close to the touch. That case measures nothing and does
**not** stop the series. Only a refusal the broker gave for some other reason
does.

A non-zero exit stops the series too, before the token is believed: the probe
can print a clean verdict and still die writing the artifact, and then an
order may be unaccounted for. Same rule `run_p_ca.sh` applies to `HELD=`.

Why the transport row is the point: on 2026-09-28 a five-trial series lost
trials 3, 4 and 5 to one `ConnectionError` in the middle of trial 2's
coexistence poll. The runner's verdict read

```
VERDICT: STOP: P-8 2/5 오류 1건(브로커 거부 포함) — 1/5 성공 후 중단(재시도 금지)
```

Nothing had been rejected, and the cleanup cancel issued seconds later
returned `rt_cd=0`. This runner's verdict line carries the four counts as
separate fields, so there is no field in which a transport stop and a
rejection can be added together:

```
VERDICT: <reason> | trials_run=n/N measured=n broker_rejections=n rate_limit_stops=n query_unanswered_stops=n order_state_unknown_stops=n transport_stops=n
```

`measured=n` counts only trials that actually produced a `coexistence_ms`. A
trial whose amend was rejected, whose amend issued no new ODNO, or whose poll
loop never got one `rt_cd=0` answer measured **nothing** — it prints
`P8_COEXISTENCE=not_measured` and does not count toward N≥5, even though it
did not stop.

It then says in so many words whether `N>=5` was reached, because
`capabilities.replace_semantics.mode` stays unwritten until five trials both
measured and agreed, and the runner is the only place that knows the count.

### Notes

- **Mock-only is enforced in code, not here.** Every P-8 order call passes
  `assert_mock_host()` and `assert_mock_trading_tr()`, and `_setup()` runs
  `assert_no_live_futures_config()` before the first socket. A bash guard
  would only be a second, weaker copy of a refusal that cannot be bypassed.
  There is no `P8_KIS_ENV`.
- **`P8_SYMBOL` is the near-month contract on the day it runs.** It is an
  instance value with no default for that reason — an expired contract is a
  rejection, not a measurement.
- Artifacts are copied to `P8_EVIDENCE_DIR` after each trial, and only when
  newer than what the results directory already held: a trial that wrote
  nothing must not copy somebody else's.
- The script **never deletes itself**. `P8_CRON_MARK` removes only the one
  matching `crontab -l` line, and only once a trial has actually run — an
  early ABORT leaves the schedule in place so the next slot can retry.
- Exit status: 0 when the series completed, non-zero when it stopped.
- Cron: set `CRON_TZ=Asia/Seoul`, and give the entry an absolute path plus the
  `P8_*` exports, `P8_PYTHON` included (a cron shell inherits almost nothing).
