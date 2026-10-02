# shellcheck shell=bash
#
# Shared helpers for the tracked probe runner TEMPLATES in this directory.
# Sourced, never executed; it has no shebang and is not marked executable.
#
# Why it exists: `run_p_ca.sh` (#825) and `run_p8.sh` (this PR) need the same
# guards — clean/detached/ancestor checkout, no instance defaults, a proven
# module path, a POLICY_VERSION handshake, a credential file that is copied in
# but never committed. Two copies of those would be two copies of a POLICY, and
# this harness has already paid for that once: the transient-error precedence
# lived in two places and had drifted, so a 429 body carrying EGW00215 bought a
# retry on one path and stopped the run at once on the other (#825 independent
# review F4). The guards here are the same kind of thing.
#
# Nothing in this file reads a PCA_* or P8_* variable. Every instance value
# arrives as an ARGUMENT, including the NAME of the variable a message should
# cite, so the two runners cannot leak into one another and a third runner
# needs no edit here.
#
# Globals this file sets, deliberately and by name (bash has no better way to
# hand several values back): REPO, MODULE_PATH, MODULE_POLICY, CRED_FILE,
# KEY_FP, ACCOUNT_FP. It reads none of the caller's.

#: Where log() tees to, "" until the caller says. Only this file touches it.
_PROBE_LOG_FILE=""

# $1 the runner's log path (may be empty — log() then only prints).
#
# A function rather than "assign the global yourself", because the assignment
# is READ here and WRITTEN there: shellcheck analysing a runner on its own
# cannot see the read and reports the write as unused (SC2034) — which is
# exactly what CI caught, while a local run that passed BOTH files resolved it
# and stayed green. A gate whose verdict depends on how many files you hand it
# is not a gate. With a setter there is no cross-file variable at all.
#
# Call it immediately after sourcing, before the first log() call, so even the
# first guard's ABORT lands in the file an operator will go looking in.
set_log_file() {
  _PROBE_LOG_FILE=$1
}

log() {
  _line="$(TZ=Asia/Seoul date '+%F %T') $*"
  printf '%s\n' "$_line"
  if [ -n "$_PROBE_LOG_FILE" ]; then
    printf '%s\n' "$_line" >>"$_PROBE_LOG_FILE"
  fi
  return 0
}

die() {
  log "ABORT: $1"
  exit "${2:-3}"
}

# --- the checkout ----------------------------------------------------------
#
# $1 the directory the running script sits in
# $2 "1" when the operator has overridden the guards, anything else otherwise
# $3 the NAME of that override variable, for the warning line
#
# Sets REPO and cd's into it.
#
# #793: a shared checkout lets a parallel lane move the branch under a running
# probe, and `repo_commit` is then stamped with a non-main commit. The three
# checks are clean `git status --short`, detached HEAD, and HEAD an ancestor of
# origin/main. They run BEFORE any credential file is sourced.
guard_checkout() {
  _script_dir=$1
  _allow_shared=$2
  _override_name=$3

  REPO=$(git -C "$_script_dir" rev-parse --show-toplevel 2>/dev/null) ||
    die "$_script_dir is not inside a git checkout"
  cd "$REPO" || exit 2

  if [ "$_allow_shared" = "1" ]; then
    log "WARN: $_override_name=1 — clean/detached/ancestor guards SKIPPED" \
      "by operator override; repo_commit in the artifact may not be an" \
      "origin/main commit (#793)"
  else
    _dirty=$(git -C "$REPO" status --short)
    [ -z "$_dirty" ] ||
      die "checkout $REPO is dirty; probes run from a clean detached worktree (#793). First line: $(printf '%s' "$_dirty" | head -1)"

    _branch=$(git -C "$REPO" rev-parse --abbrev-ref HEAD 2>/dev/null) ||
      die "cannot read HEAD in $REPO"
    [ "$_branch" = "HEAD" ] ||
      die "checkout $REPO is on branch '$_branch', not a detached worktree — a parallel lane can move it under a running probe (#793)"

    git -C "$REPO" rev-parse --verify --quiet origin/main >/dev/null ||
      die "origin/main is not present in $REPO — run 'git fetch origin' first"
    git -C "$REPO" merge-base --is-ancestor HEAD origin/main ||
      die "HEAD ($(git -C "$REPO" rev-parse --short HEAD)) is not an ancestor of origin/main — probe evidence must be produced by merged code (#793)"
  fi
  log "checkout ok: repo=$REPO repo_commit=$(git -C "$REPO" rev-parse HEAD)"
}

# --- instance values -------------------------------------------------------
#
# $@ variable names that must be set and non-empty.
#
# A template ships no instance defaults: an unset value is an ABORT, never a
# silent fallback to somebody else's trial.
require_env() {
  for _name in "$@"; do
    _value=$(printenv "$_name" || true)
    [ -n "$_value" ] ||
      die "required env $_name is unset — this template ships no instance defaults"
  done
}

# $1 the log path, $2 the NAME of the variable holding it.
#
# The probe's whole output is appended to this file. If the directory does not
# exist the redirection fails, bash never runs the probe, and every log() call
# has already been silently dropping its line — the "attempt vanished" shape
# these runners exist to prevent (#825 round-3 review F1). Make it real here,
# and fail loudly if it cannot be.
ensure_log_file() {
  mkdir -p -- "$(dirname -- "$1")" ||
    die "cannot create the directory for $2=$1"
  touch -- "$1" || die "$2 is not writable: $1"
}

# --- interpreter and module provenance -------------------------------------
#
# $1 the interpreter, $2 its variable NAME, $3 the module to import,
# $4 the POLICY_VERSION this runner was written for.
#
# Sets MODULE_PATH and MODULE_POLICY, and exports PYTHONPATH.
#
# The interpreter comes from somewhere else (the main checkout's .venv — a
# freshly added detached worktree has no .venv, and installing one into it is
# forbidden), so the code it LOADS has to be proven to be this checkout's.
# Without this the clean/detached/ancestor guards would vouch for a tree that
# never ran: `repo_commit` and the results directory both follow
# `common.py.__file__` (common.py:70,506,512), not $REPO, so an interpreter
# resolving tools.broker_probes from the main checkout would stamp the wrong
# commit and write the artifact where the runner does not look (#825 round-2
# review F1).
#
# The POLICY_VERSION comparison replaces grepping the probe source for
# substrings: a substring test cannot tell a fix from a mention (a plan quoting
# the literal is enough), and it breaks on a rename — failing a scheduled trial
# with "required fix not present" while the fix is right there (#825 round-3
# review F7). Both files live in this checkout, so a mismatch means the runner
# was COPIED OUT of a different tree, which is the 2026-09-30 mistake.
guard_python_module() {
  _py=$1
  _pyname=$2
  _module=$3
  _expect=$4

  [ -x "$_py" ] || die "$_pyname is not executable: $_py"

  _loaded=$(PYTHONPATH="$REPO" "$_py" -c \
    "import $_module as m; print(m.__file__); print(m.POLICY_VERSION)" 2>&1) ||
    die "cannot import tools.broker_probes from $REPO with $_py: $(printf '%s' "$_loaded" | tail -1 | cut -c1-160)"
  MODULE_PATH=$(printf '%s\n' "$_loaded" | sed -n '1p')
  MODULE_POLICY=$(printf '%s\n' "$_loaded" | sed -n '2p')
  case "$MODULE_PATH" in
  "$REPO"/*) log "probe module resolves inside the checkout: $MODULE_PATH" ;;
  *) die "probe module resolves OUTSIDE the checkout ($MODULE_PATH) — the guards above would vouch for code that never ran" ;;
  esac
  [ "$MODULE_POLICY" = "$_expect" ] ||
    die "policy version mismatch: this runner was written for '$_expect', the checkout's ${_module##*.}.py reports '$MODULE_POLICY' — runner and probe are from different trees" 4
  log "probe policy version $MODULE_POLICY matches this runner"
  export PYTHONPATH="$REPO${PYTHONPATH:+:$PYTHONPATH}"
}

# --- the credential file ---------------------------------------------------
#
# $1 the operator's credential-file value. Sets CRED_FILE.
#
# Operator directive 2026-10-01: "워크트리에 .env가 없으면 기본 디렉토리에서
# 복사해". A RELATIVE value (the documented case, e.g. .env.mock) is resolved
# against this worktree; a freshly added worktree carries none of the ignored
# env files, so it is copied from the PRIMARY checkout — the first entry of
# `git worktree list --porcelain`, never a hardcoded path, so this keeps
# working when the checkout moves. An ABSOLUTE path (e.g. the 2026-09-15
# credential backup under ~/.config) is used exactly as given and never copied.
#
# The copy is mode 600 and the log line carries PATHS ONLY — never a byte of
# the file. It persists in the worktree; the names accepted below are
# gitignored, so it does not make the checkout dirty for the next run's guard.
resolve_credential_file() {
  case "$1" in
  /*)
    CRED_FILE=$1
    [ -r "$CRED_FILE" ] ||
      die "credential file unreadable: $CRED_FILE (absolute path, used as given)"
    ;;
  *)
    CRED_FILE="$REPO/$1"
    # BEFORE anything is written. The repo ignores EXACT names (.env,
    # .env.mock, .env.real, .env.paper, .env.live, .env.production,
    # .env.local, .env.*.local) — not a `.env.*` glob, so `.env.mock.bak-…`,
    # the very name the README once suggested, is NOT ignored (#825 round-3
    # review F2). Copying a filled credential file onto an unignored path puts
    # it where `git add -A` would stage it: CLAUDE.md Non-Negotiable, "never
    # commit real credentials … or filled .env files". `git check-ignore`
    # answers for a path that does not exist yet, so the refusal costs nothing
    # and nothing is ever written to the wrong place.
    git -C "$REPO" check-ignore -q -- "$1" ||
      die "relative credential file '$1' is NOT gitignored in $REPO — refusing to place a filled credential file where 'git add -A' would stage it. Use an ignored name (.env.mock, .env.real, .env.paper, …) or give an absolute path outside the checkout"
    if [ ! -r "$CRED_FILE" ]; then
      _primary=$(git -C "$REPO" worktree list --porcelain |
        awk '/^worktree /{print substr($0, 10); exit}')
      [ -n "$_primary" ] ||
        die "cannot determine the primary checkout from 'git worktree list' in $REPO"
      _source="$_primary/$1"
      [ -r "$_source" ] ||
        die "credential file '$1' is in neither checkout — not at $CRED_FILE and not at $_source"
      install -m 600 "$_source" "$CRED_FILE" ||
        die "could not copy the credential file: $_source -> $CRED_FILE"
      log "credential file copied from the primary checkout: $_source -> $CRED_FILE (mode 600)"
    fi
    ;;
  esac
}

# --- credential identity ---------------------------------------------------
#
# $1 label ("stock"/"futures"), $2 the raw app key, $3 the expected
# fingerprint, $4 the credential file path (for the message). Sets KEY_FP.
#
# Checked before the probe starts, because the 2026-09-23 INVALID_CHECK_ACNO
# outage was a key paired with the wrong account, not a propagation delay.
check_key_fingerprint() {
  KEY_FP=$(printf '%s' "$2" | sha256sum | cut -c1-12)
  log "$1 app key fp=$KEY_FP (expect $3)"
  [ "$KEY_FP" = "$3" ] ||
    die "app key fingerprint mismatch — $4 is not the credential set this trial was planned against"
}

# $1 label, $2 the interpreter, $3 the NAME of the env var holding the account
# number, $4 the expected fingerprint. Sets ACCOUNT_FP.
#
# The account number is read from the environment inside the interpreter rather
# than passed as an argument: argv is world-readable in `ps`.
check_account_fingerprint() {
  ACCOUNT_FP=$("$2" -c "
import os
from tools.broker_probes.common import account_fingerprint
print(account_fingerprint(os.environ['$3']))") ||
    die "account fingerprint call failed"
  log "$1 account fingerprint=$ACCOUNT_FP (expect $4)"
  [ "$ACCOUNT_FP" = "$4" ] ||
    die "account fingerprint mismatch"
}

# --- artifacts -------------------------------------------------------------
#
# $1 the probe id prefix, e.g. P-CA or P-8. Prints the newest artifact path, or
# nothing.
#
# (shellcheck SC2012, info-level, is left standing: these names are generated
# by the harness as <ID>-<UTC timestamp>Z.json — no spaces, no newlines — and
# `find | sort` for a fixed pattern would be the more fragile of the two.)
newest_artifact() {
  # shellcheck disable=SC2012
  ls -t "$REPO"/tools/broker_probes/results/"$1"-*.json 2>/dev/null | head -1
}
