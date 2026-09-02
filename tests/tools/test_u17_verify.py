"""Battery for ``tools/u17-verify.sh`` — U-17 prevention-control evidence executor.

Phase B (2026-08-30) replaced the executor's E0 (judgment-root check-run universe)
derivation with the contract's current-generation path 1-R -> 2-S -> 3-C, added the
alpha (inclusion+identity) and beta (count-matching) independence axes, the four
documented-cap guards (1-R, the check-suites cap feeding alpha, the D-cap used by
alpha(ii), and the same-name-1000 cap on 3-C), and a completeness-certificate gate
in front of the single PREVENTION_ACTIVE emission point.

This battery drives the *unmodified* script end-to-end via ``U17_RESPONDER=file:<dir>``
(a fully offline GitHub-API fixture seam the script already supports) against a real,
throwaway git repository built per-test.  It does not mock git itself: P_first/P_last/
D derivation, the isolated-snapshot clone, and all ancestry checks run for real against
a two-commit repo (commit 1 lands the prevention-control artifact, commit 2 lands the
completion-config file that defines ``D``).

Each negative test starts from the golden (fully-compliant) fixture set and mutates
exactly one ingredient, so a positive-vs-negative *pair* exists for every new axis
(the project's stated control-group discipline for this file).
"""

from __future__ import annotations

import base64
import copy
import functools
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "tools" / "u17-verify.sh"
# The executor's WFCANON predicate needs PyYAML (absent from a bare system
# python3). Prefer the repo .venv when it exists (local dev); otherwise fall
# back to the interpreter running pytest itself — on CI that interpreter is
# the one `pip install -e ".[dev]"` ran under, and `pyyaml` is a base
# (non-dev) dependency in pyproject.toml, so it is present there too.
_VENV_PYBIN = REPO_ROOT / ".venv" / "bin" / "python"
PYBIN = str(_VENV_PYBIN) if _VENV_PYBIN.exists() else sys.executable
WORKFLOW_PATH = ".github/workflows/tos-gate.yml"
REAL_WORKFLOW_TEXT = (REPO_ROOT / WORKFLOW_PATH).read_text(encoding="utf-8")

PIN_OR = "kakao-harris-lee/kis_unified_sts"
TARGET_BRANCH = "main"
APPID = 15368
PIN_WFID = 225947999
HSHA = (
    "deadbeef" * 5
)  # 40 hex chars — the mocked PR head sha (need not be a real local commit)
TARGET_HEAD_SHA = "cafef00d" * 5
RUN_ID = 1000000001
SUITE_ID = 2000000001
CR_ID = 3000000001
MERGED_AT = "2026-08-15T00:00:00Z"
RULESET_ID = 42
RULESET_CREATED = "2026-08-01T00:00:00Z"
RULESET_UPDATED = "2026-08-01T00:00:00Z"


def _key(path: str) -> str:
    """Python port of the script's ``key()``: ``tr '/?=&' '____'``."""
    return path.translate(str.maketrans("/?=&", "____"))


def _b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


class Responder:
    """Writes ``U17_RESPONDER=file:<dir>`` fixtures matching the script's own key()."""

    def __init__(self, directory: Path) -> None:
        self.dir = directory
        self.dir.mkdir(parents=True, exist_ok=True)

    def _dump(self, obj: Any) -> str:
        if isinstance(obj, str):
            return obj
        return json.dumps(obj)

    def set(self, path: str, status: int | str, body: Any) -> None:
        k = _key(path)
        (self.dir / f"{k}.status").write_text(f"{status}\n", encoding="utf-8")
        (self.dir / f"{k}.body").write_text(self._dump(body), encoding="utf-8")

    def set_slurp(self, path: str, status: int | str, pages: list[Any]) -> None:
        k = _key(path)
        (self.dir / f"{k}.slurp.status").write_text(f"{status}\n", encoding="utf-8")
        (self.dir / f"{k}.slurp.body").write_text(json.dumps(pages), encoding="utf-8")


def _init_repo(tmp_path: Path) -> tuple[Path, str]:
    """Build a 2-commit repo: c1 lands the prevention-control artifact, c2 lands
    config/tos_completion.yaml (D's sole element).  Returns (repo_dir, d_sha)."""
    repo = tmp_path / "repo"
    repo.mkdir()

    def run(*args: str) -> None:
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    run("init", "-q", "-b", "main")
    run("config", "user.email", "test@example.invalid")
    run("config", "user.name", "u17-test")
    run(
        "remote",
        "add",
        "origin",
        "https://github.com/kakao-harris-lee/kis_unified_sts.git",
    )

    pc_dir = repo / "tos-spec/src/part-1-foundation/decisions"
    pc_dir.mkdir(parents=True)
    (pc_dir / "D0A-PREVENTION-CONTROL.md").write_text(
        '# D0A-PREVENTION-CONTROL\n\noperator_countersign: "tester 2026-08-30T00:00:00Z"\n',
        encoding="utf-8",
    )
    run("add", "-A")
    run("commit", "-q", "-m", "c1: prevention-control artifact")

    cfg_dir = repo / "config"
    cfg_dir.mkdir()
    (cfg_dir / "tos_completion.yaml").write_text(
        "placeholder: true\n", encoding="utf-8"
    )
    run("add", "-A")
    run("commit", "-q", "-m", "c2: completion config (D)")

    d_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return repo, d_sha


def _run_script(repo: Path, responder_dir: Path) -> subprocess.CompletedProcess:
    env = {
        "U17_RESPONDER": f"file:{responder_dir}",
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin",
        "U17_PYBIN": PYBIN,
    }
    return subprocess.run(
        ["bash", str(SCRIPT), str(repo)],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


def _state(result: subprocess.CompletedProcess) -> str | None:
    m = re.search(r"^prevention_control_state=(\S+)$", result.stdout, re.MULTILINE)
    return m.group(1) if m else None


def _reason(result: subprocess.CompletedProcess) -> str | None:
    m = re.search(r"^reason=(.*)$", result.stdout, re.MULTILINE)
    return m.group(1) if m else None


def run_step(name: str) -> dict:
    return {"name": name, "conclusion": "success"}


def _base_ingredients() -> dict:
    """The golden (fully-compliant) fixture ingredients. Mutate a deep copy for
    negative cases."""
    return {
        "appid": APPID,
        "wfid": PIN_WFID,
        "hsha": HSHA,
        "target_head_sha": TARGET_HEAD_SHA,
        "run": {
            "id": RUN_ID,
            "path": WORKFLOW_PATH,
            "head_sha": HSHA,
            "check_suite_id": SUITE_ID,
            "workflow_id": PIN_WFID,
            "run_attempt": 1,
        },
        "r_total_count": 1,
        "check_run": {
            "id": CR_ID,
            "name": "tos-gate",
            "status": "completed",
            "completed_at": "2026-08-15T00:05:00Z",
            "conclusion": "success",
            "head_sha": HSHA,
            "app": {"id": APPID},
            "check_suite": {"id": SUITE_ID},
            "details_url": f"https://github.com/{PIN_OR}/actions/runs/{RUN_ID}/job/1",
        },
        "e0_total_count": 1,
        "suite": {"id": SUITE_ID, "head_sha": HSHA, "app": {"id": APPID}},
        "sa_total_count": None,  # None => derive from [suite] + extra_sa_suites length
        "beta_ref_check_runs": None,  # None => reuse [check_run] as-is
        "beta_total_count": None,  # None => derive from beta_ref_check_runs length
        "extra_sa_suites": [],  # list of extra suite dicts for alpha(ii) tests
        "ddid_responses": {},  # suite_id -> {"status":.., "runs":[...], "total_count":..}
        "pulls_pad_count": 0,  # extra non-matching PRs to pad the last pulls page (delta axis test)
    }


def _materialize(tmp_path: Path, ing: dict) -> tuple[Path, Path]:
    repo, d_sha = _init_repo(tmp_path)
    resp = Responder(tmp_path / "resp")

    # ── single-object endpoints ────────────────────────────────────────────
    resp.set("apps/github-actions", 200, {"id": ing["appid"]})
    resp.set(f"repos/{PIN_OR}", 200, {"default_branch": TARGET_BRANCH})
    resp.set(
        f"repos/{PIN_OR}/actions/workflows/tos-gate.yml",
        200,
        {"id": ing["wfid"], "state": "active"},
    )
    resp.set(
        f"repos/{PIN_OR}/branches/{TARGET_BRANCH}/protection",
        404,
        {"message": "Branch not protected"},
    )
    rules_branches_list = [
        {
            "type": "required_status_checks",
            "ruleset_id": RULESET_ID,
            "parameters": {
                "strict_required_status_checks_policy": True,
                "required_status_checks": [
                    {"context": "tos-gate", "integration_id": ing["appid"]}
                ],
            },
        },
        {"type": "pull_request", "ruleset_id": RULESET_ID},
        {"type": "non_fast_forward", "ruleset_id": RULESET_ID},
        {"type": "deletion", "ruleset_id": RULESET_ID},
    ]
    rulesets_list = [
        {"id": RULESET_ID, "name": "gate", "target": "branch", "enforcement": "active"}
    ]
    resp.set(f"repos/{PIN_OR}/rules/branches/{TARGET_BRANCH}", 200, rules_branches_list)
    resp.set(f"repos/{PIN_OR}/rulesets", 200, rulesets_list)
    # ── (다) delta-observation upgrade (Phase B-2, defect 2): the (a) block's plain
    # single-shot fetches above stay the consumption source (unchanged); these
    # per_page=100 siblings feed only the completeness-certificate's (2)(2) axis.
    rb_page_path = f"repos/{PIN_OR}/rules/branches/{TARGET_BRANCH}?per_page=100"
    resp.set(rb_page_path, 200, rules_branches_list)
    resp.set_slurp(rb_page_path, 200, [rules_branches_list])
    resp.set(f"{rb_page_path}&page=2", 200, [])
    rs_page_path = f"repos/{PIN_OR}/rulesets?per_page=100"
    resp.set(rs_page_path, 200, rulesets_list)
    resp.set_slurp(rs_page_path, 200, [rulesets_list])
    resp.set(f"{rs_page_path}&page=2", 200, [])
    resp.set(
        f"repos/{PIN_OR}/rulesets/{RULESET_ID}",
        200,
        {
            "id": RULESET_ID,
            "enforcement": "active",
            "bypass_actors": [],
            "created_at": RULESET_CREATED,
            "updated_at": RULESET_UPDATED,
        },
    )
    resp.set(
        f"repos/{PIN_OR}/branches/{TARGET_BRANCH}",
        200,
        {"commit": {"sha": ing["target_head_sha"]}},
    )
    resp.set(
        f"repos/{PIN_OR}/contents/{WORKFLOW_PATH}?ref={ing['target_head_sha']}",
        200,
        {
            "encoding": "base64",
            "content": _b64(REAL_WORKFLOW_TEXT),
            "size": len(REAL_WORKFLOW_TEXT),
        },
    )
    resp.set(
        f"repos/{PIN_OR}/contents/{WORKFLOW_PATH}?ref={ing['hsha']}",
        200,
        {
            "encoding": "base64",
            "content": _b64(REAL_WORKFLOW_TEXT),
            "size": len(REAL_WORKFLOW_TEXT),
        },
    )
    resp.set(
        f"repos/{PIN_OR}/actions/runs/{RUN_ID}/jobs?filter=latest&per_page=100",
        200,
        {
            "jobs": [
                {
                    "name": "tos-gate",
                    "conclusion": "success",
                    "steps": [
                        run_step("tos-gate: verify harness sha256"),
                        run_step("tos-gate: run harness"),
                    ],
                }
            ]
        },
    )

    # ── (b)(1) pulls — bare array, no total_count => needs terminal probe ──
    pr = [
        {
            "merged_at": MERGED_AT,
            "base": {"ref": TARGET_BRANCH},
            "head": {"sha": ing["hsha"]},
        }
    ]
    pr = pr + [
        {
            "merged_at": None,
            "base": {"ref": TARGET_BRANCH},
            "head": {"sha": f"{i:040x}"},
        }
        for i in range(ing.get("pulls_pad_count", 0))
    ]
    pulls_path = f"repos/{PIN_OR}/commits/{d_sha}/pulls?per_page=100"
    resp.set(pulls_path, 200, pr)
    resp.set_slurp(pulls_path, 200, [pr])
    resp.set(f"{pulls_path}&page=2", 200, [])

    # ── 1-R: actions/workflows/{id}/runs?head_sha= — object+total_count ────
    runs_path = f"repos/{PIN_OR}/actions/workflows/{ing['wfid']}/runs?head_sha={ing['hsha']}&per_page=100"
    runs_body = {
        "total_count": ing["r_total_count"],
        "workflow_runs": ing["runs_list"] if "runs_list" in ing else [ing["run"]],
    }
    resp.set(runs_path, 200, runs_body)
    resp.set_slurp(runs_path, 200, [runs_body])

    # ── 3-C: check-suites/{s}/check-runs — object+total_count, per suite ───
    cc_path = (
        f"repos/{PIN_OR}/check-suites/{SUITE_ID}/check-runs?filter=all&per_page=100"
    )
    e0_runs = ing.get("e0_check_runs", [ing["check_run"]])
    cc_body = {"total_count": ing["e0_total_count"], "check_runs": e0_runs}
    resp.set(cc_path, 200, cc_body)
    resp.set_slurp(cc_path, 200, [cc_body])

    # ── alpha: commits/{sha}/check-suites — object+total_count ─────────────
    sa_suites = [ing["suite"]] + ing.get("extra_sa_suites", [])
    csa_path = f"repos/{PIN_OR}/commits/{ing['hsha']}/check-suites?per_page=100"
    sa_total_count = (
        ing["sa_total_count"] if ing["sa_total_count"] is not None else len(sa_suites)
    )
    csa_body = {"total_count": sa_total_count, "check_suites": sa_suites}
    resp.set(csa_path, 200, csa_body)
    resp.set_slurp(csa_path, 200, [csa_body])

    # ── alpha(ii)/D: actions/runs?check_suite_id= — only for extra suites ──
    for suite_id, spec in ing.get("ddid_responses", {}).items():
        dpath = f"repos/{PIN_OR}/actions/runs?check_suite_id={suite_id}&per_page=100"
        if spec.get("absent"):
            continue  # deliberately unregistered => ERR (network/auth failure simulation)
        dbody = {
            "total_count": spec.get("total_count", len(spec.get("runs", []))),
            "workflow_runs": spec.get("runs", []),
        }
        resp.set(dpath, spec.get("status", 200), dbody)
        resp.set_slurp(dpath, spec.get("status", 200), [dbody])

    # ── beta: commits/{sha}/check-runs — ref-level, object+total_count ─────
    beta_runs = (
        ing["beta_ref_check_runs"]
        if ing["beta_ref_check_runs"] is not None
        else [ing["check_run"]]
    )
    beta_total = (
        ing["beta_total_count"]
        if ing["beta_total_count"] is not None
        else len(beta_runs)
    )
    br_path = f"repos/{PIN_OR}/commits/{ing['hsha']}/check-runs?filter=all&per_page=100"
    br_body = {"total_count": beta_total, "check_runs": beta_runs}
    resp.set(br_path, 200, br_body)
    resp.set_slurp(br_path, 200, [br_body])
    # the PRE-Phase-B script unconditionally fetches a terminal probe page for this
    # endpoint even though it is object+total_count shaped (limb (2)(1) applies and the
    # probe goes unused) — harmless for the Phase B script, required for the old one.
    resp.set(f"{br_path}&page=2", 200, {"total_count": beta_total, "check_runs": []})

    return repo, resp.dir


# ──────────────────────────────────────────────────────────────────────────
# positive path
# ──────────────────────────────────────────────────────────────────────────


def test_positive_full_stack_reaches_active(tmp_path):
    repo, responder_dir = _materialize(tmp_path, _base_ingredients())
    result = _run_script(repo, responder_dir)
    assert _state(result) == "PREVENTION_ACTIVE", (
        f"expected ACTIVE, got {_state(result)!r} reason={_reason(result)!r}\n"
        f"--- stdout tail ---\n{result.stdout[-4000:]}"
    )
    assert result.returncode == 0

    # anti-phantom (positive direction): new-generation markers present
    for marker in ("U17-C1R", "U17-C2S", "U17-C3 ", "U17-ALFA", "U17-BETA", "U17-CERT"):
        assert marker in result.stdout, f"missing {marker!r} in transcript"

    # anti-phantom (negative direction): old E0-source call sites are gone
    assert (
        "U17-B2 " not in result.stdout
    ), "old commits/{sha}/check-runs E0-source capture tag resurfaced"
    assert (
        "U17-B2t " not in result.stdout
    ), "old terminal-probe capture tag for check-runs resurfaced"

    # commits/{sha}/check-runs must appear only inside the beta cross-check, never as E0 root
    check_runs_ref_query = (
        f"repos/{PIN_OR}/commits/{HSHA}/check-runs?filter=all&per_page=100"
    )
    assert check_runs_ref_query in result.stdout
    beta_idx = result.stdout.index("U17-BETA")
    ref_query_idx = result.stdout.index(check_runs_ref_query)
    # the ref-level check-runs query must be observably associated with beta, not upstream of it
    assert abs(ref_query_idx - beta_idx) < 4000


# ──────────────────────────────────────────────────────────────────────────
# negative axes — one mutation each from the golden ingredients
# ──────────────────────────────────────────────────────────────────────────


def test_negative_1R_cap_via_collected_count(tmp_path):
    ing = _base_ingredients()
    ing["runs_list"] = [dict(ing["run"], id=RUN_ID + i) for i in range(1000)]
    ing["r_total_count"] = 1000
    repo, responder_dir = _materialize(tmp_path, ing)
    result = _run_script(repo, responder_dir)
    assert _state(result) == "PREVENTION_UNVERIFIABLE"
    assert result.returncode != 0
    assert "1-R" in result.stdout or "①-R" in result.stdout


def test_negative_1R_cap_via_total_count_self_report(tmp_path):
    """Architecture note (discovered while wiring this test): the self-report
    disjunct (`total_count > 1000`) cannot be exercised in isolation at 1-R —
    PAGELIMB's own limb(1) (collected-count == total_count, mandatory for any
    object+total_count endpoint, u17-path.txt (2)(1)) already requires the two
    to agree before the 1-R cap check is even reached.  A 'total_count=1500
    but only 1 real element collected' fixture therefore fires PAGELIMB's own
    '열거 불완전' first (also a correct, if differently-labeled, block) rather
    than reaching the 1-R guard at all — this was the actual failure this test
    hit on its first run.  The only fixture that reaches the 1-R guard via the
    self-report disjunct is one where collected count and total_count agree
    (both >1000), at which point the two disjuncts necessarily co-fire.  Kept
    distinct from test_negative_1R_cap_via_collected_count (which pads to
    exactly 1000) by using a value clearly over the threshold (1500) to prove
    the '>' half of the fire message's disjunction is populated correctly."""
    ing = _base_ingredients()
    ing["runs_list"] = [dict(ing["run"], id=RUN_ID + i) for i in range(1500)]
    ing["r_total_count"] = 1500
    repo, responder_dir = _materialize(tmp_path, ing)
    result = _run_script(repo, responder_dir)
    assert _state(result) == "PREVENTION_UNVERIFIABLE"
    assert result.returncode != 0
    # reason-string assertion (control-group discipline): the pre-Phase-B script can
    # also land on UNVERIFIABLE here via an unrelated missing-fixture ERR, so state+rc
    # alone is a blind pass — pin it to the 1-R cap's own fire message.
    assert "1,000-결과 상한 도달" in result.stdout
    assert "total_count=1500" in result.stdout


def test_negative_5_same_name_cap(tmp_path):
    ing = _base_ingredients()
    ing["e0_check_runs"] = [dict(ing["check_run"], id=CR_ID + i) for i in range(1000)]
    ing["e0_total_count"] = 1000
    repo, responder_dir = _materialize(tmp_path, ing)
    result = _run_script(repo, responder_dir)
    assert _state(result) == "PREVENTION_UNVERIFIABLE"
    assert result.returncode != 0
    assert "동명" in result.stdout


def test_negative_alpha_i_subset_violation(tmp_path):
    ing = _base_ingredients()
    # S_A excludes the suite in S_R entirely (simulate check-suites listing a
    # different head_sha, so the alpha inclusion filter drops it)
    ing["suite"] = dict(ing["suite"], head_sha="0" * 40)
    repo, responder_dir = _materialize(tmp_path, ing)
    result = _run_script(repo, responder_dir)
    assert _state(result) == "PREVENTION_UNVERIFIABLE"
    assert result.returncode != 0
    assert "S_R" in result.stdout and "S_A" in result.stdout


def test_negative_alpha_ii_pinned_suite_masquerading(tmp_path):
    """The 'h7-5' control fixture: a pinned-workflow suite absent from 1-R's
    run set (i.e. 1-R under-enumerated) must block, not silently pass."""
    ing = _base_ingredients()
    extra_suite_id = SUITE_ID + 1
    ing["extra_sa_suites"] = [
        {"id": extra_suite_id, "head_sha": HSHA, "app": {"id": APPID}}
    ]
    ing["ddid_responses"] = {
        extra_suite_id: {
            "runs": [
                {
                    "id": RUN_ID + 999,
                    "path": WORKFLOW_PATH,  # matches pinned path => identity=PINNED
                    "head_sha": HSHA,
                    "workflow_id": PIN_WFID,
                }
            ]
        }
    }
    repo, responder_dir = _materialize(tmp_path, ing)
    result = _run_script(repo, responder_dir)
    assert _state(result) == "PREVENTION_UNVERIFIABLE"
    assert result.returncode != 0
    assert "과소 열거" in result.stdout


def test_negative_alpha_ii_other_workflow_confirmed_passes(tmp_path):
    """Control (positive-direction) pair for the above: a genuinely different
    workflow's suite in S_A minus S_R must NOT block."""
    ing = _base_ingredients()
    extra_suite_id = SUITE_ID + 2
    ing["extra_sa_suites"] = [
        {"id": extra_suite_id, "head_sha": HSHA, "app": {"id": APPID}}
    ]
    ing["ddid_responses"] = {
        extra_suite_id: {
            "runs": [
                {
                    "id": RUN_ID + 998,
                    "path": ".github/workflows/docker-test.yml",
                    "head_sha": HSHA,
                    "workflow_id": PIN_WFID + 1,
                }
            ]
        }
    }
    repo, responder_dir = _materialize(tmp_path, ing)
    result = _run_script(repo, responder_dir)
    assert _state(result) == "PREVENTION_ACTIVE", (
        f"expected ACTIVE (confirmed other-workflow must not block), got {_state(result)!r} "
        f"reason={_reason(result)!r}"
    )


def test_negative_alpha_ii_identity_query_unreachable(tmp_path):
    ing = _base_ingredients()
    extra_suite_id = SUITE_ID + 3
    ing["extra_sa_suites"] = [
        {"id": extra_suite_id, "head_sha": HSHA, "app": {"id": APPID}}
    ]
    ing["ddid_responses"] = {
        extra_suite_id: {"absent": True}
    }  # simulate network/auth failure
    repo, responder_dir = _materialize(tmp_path, ing)
    result = _run_script(repo, responder_dir)
    assert _state(result) == "PREVENTION_UNVERIFIABLE"
    assert result.returncode != 0
    # reason-string assertion (control-group discipline): pin this to the alpha(ii)/D
    # axis's own fire message so a pre-Phase-B script cannot pass by coincidentally
    # landing on UNVERIFIABLE via an unrelated missing fixture.
    assert "U17-ALFA" in result.stdout
    assert "α(ii)/ⓓ" in result.stdout and "네트워크/인증 오류" in result.stdout


def test_negative_alpha_ii_evidence_run_fields_absent(tmp_path):
    """Phase B-2 defect 1: a run with neither workflow_id nor path present must
    NOT be read as a confirmed 'other workflow' — that is the exact fail-open
    ('confirming nothing, then labeling it confirmed') the contract's K-10
    discipline forbids."""
    ing = _base_ingredients()
    extra_suite_id = SUITE_ID + 4
    ing["extra_sa_suites"] = [
        {"id": extra_suite_id, "head_sha": HSHA, "app": {"id": APPID}}
    ]
    ing["ddid_responses"] = {
        extra_suite_id: {
            "runs": [{"id": RUN_ID + 997, "head_sha": HSHA}]
        }  # no workflow_id, no path
    }
    repo, responder_dir = _materialize(tmp_path, ing)
    result = _run_script(repo, responder_dir)
    assert _state(result) == "PREVENTION_UNVERIFIABLE"
    assert result.returncode != 0
    assert "필드 부재" in result.stdout


def test_negative_alpha_ii_evidence_run_wrong_suite(tmp_path):
    """Phase B-2 defect 1: an evidence run whose own check_suite_id disagrees
    with the suite it was fetched for must fail-closed, not be trusted."""
    ing = _base_ingredients()
    extra_suite_id = SUITE_ID + 5
    ing["extra_sa_suites"] = [
        {"id": extra_suite_id, "head_sha": HSHA, "app": {"id": APPID}}
    ]
    ing["ddid_responses"] = {
        extra_suite_id: {
            "runs": [
                {
                    "id": RUN_ID + 996,
                    "path": ".github/workflows/docker-test.yml",
                    "head_sha": HSHA,
                    "workflow_id": PIN_WFID + 1,
                    "check_suite_id": extra_suite_id
                    + 12345,  # disagrees with the queried suite
                }
            ]
        }
    }
    repo, responder_dir = _materialize(tmp_path, ing)
    result = _run_script(repo, responder_dir)
    assert _state(result) == "PREVENTION_UNVERIFIABLE"
    assert result.returncode != 0
    assert "귀속 불일치" in result.stdout


def test_negative_beta_count_mismatch(tmp_path):
    ing = _base_ingredients()
    extra_cr = dict(ing["check_run"], id=CR_ID + 1)
    ing["beta_ref_check_runs"] = [
        ing["check_run"],
        extra_cr,
    ]  # ref sees 2, E0 only has 1
    ing["beta_total_count"] = 2
    repo, responder_dir = _materialize(tmp_path, ing)
    result = _run_script(repo, responder_dir)
    assert _state(result) == "PREVENTION_UNVERIFIABLE"
    assert result.returncode != 0
    assert "계수 불일치" in result.stdout


def test_negative_beta_missing_check_suite_id(tmp_path):
    ing = _base_ingredients()
    bad_cr = dict(ing["check_run"])
    bad_cr["check_suite"] = {}  # id absent -> must fail-closed, not be scoped out
    ing["beta_ref_check_runs"] = [bad_cr]
    repo, responder_dir = _materialize(tmp_path, ing)
    result = _run_script(repo, responder_dir)
    assert _state(result) == "PREVENTION_UNVERIFIABLE"
    assert result.returncode != 0
    assert "check_suite.id 부재" in result.stdout


def test_negative_delta_pulls_last_page_exactly_per_page(tmp_path):
    """Phase B-2 defect 2, certificate item (da): when pulls' last (and only)
    page has exactly per_page=100 elements, a silent server-side cap at that
    boundary is indistinguishable from genuine exhaustion — must block, even
    though the terminal probe (page=2) is empty and pagelimb's own limb(2)
    passes."""
    ing = _base_ingredients()
    ing["pulls_pad_count"] = 99  # 1 real PR + 99 padding = exactly 100
    repo, responder_dir = _materialize(tmp_path, ing)
    result = _run_script(repo, responder_dir)
    assert _state(result) == "PREVENTION_UNVERIFIABLE"
    assert result.returncode != 0
    assert "구별 불가" in result.stdout


def test_positive_delta_axis_observes_all_three_2b2_endpoints(tmp_path):
    """Confirms the (da) certificate item's population for all three (2)(2)
    endpoints (pulls, rules_branches, rulesets) on the golden path — pulls
    reuses the existing (b)(1) fetch, rules_branches/rulesets go through the
    newly-added paginate+slurp+terminal-probe+PAGELIMB upgrade."""
    repo, responder_dir = _materialize(tmp_path, _base_ingredients())
    result = _run_script(repo, responder_dir)
    assert (
        _state(result) == "PREVENTION_ACTIVE"
    ), f"got {_state(result)!r} reason={_reason(result)!r}\n{result.stdout[-3000:]}"
    for label in ("pulls", "rules_branches", "rulesets"):
        assert f'"{label}"' in result.stdout or "U17-DELTA" in result.stdout
    assert "U17-DELTA (다) 관측(target-scope)" in result.stdout
    assert re.search(r"U17-DELTA \(다\) pulls d=\S+:", result.stdout)


# ──────────────────────────────────────────────────────────────────────────
# completeness-certificate gate — unit-level (the gate is defense-in-depth;
# every fixture-reachable failure already fires+continues upstream of it, so
# driving the *whole script* into a state where the gate itself is the first
# to observe a problem is not reachable via black-box HTTP fixtures by design.
# These tests instead exercise the identical inline gate logic in isolation.)
# ──────────────────────────────────────────────────────────────────────────


@functools.lru_cache(maxsize=1)
def _gate_snippet() -> str:
    """Extracted lazily (first call happens inside a test, not at collection
    time) so that pointing SCRIPT at an older script generation — e.g. a
    control-group run against the pre-Phase-B u17-verify.sh, which has no such
    heredoc — fails only the gate tests that need it, instead of aborting
    collection for the whole module."""
    text = SCRIPT.read_text(encoding="utf-8")
    m = re.search(
        r"GATE_OUT=\$\(python3 - \"\$CERTF\" \"\$DELTA_CERT\" <<'PYCERT' 2>&1\n(.*?)\nPYCERT\n\)",
        text,
        re.DOTALL,
    )
    if not m:
        pytest.fail(
            "could not locate the two-argv certificate-gate python heredoc in "
            f"{SCRIPT} — this script generation may predate the Phase B/B-2 gate"
        )
    return m.group(1)


def _run_gate(cert: dict, delta: dict) -> subprocess.CompletedProcess:
    tmp_script = (
        "import json, sys, tempfile, os\n"
        f"cert = {cert!r}\n"
        f"delta = {delta!r}\n"
        "fd1, path1 = tempfile.mkstemp(); os.write(fd1, json.dumps(cert).encode()); os.close(fd1)\n"
        "fd2, path2 = tempfile.mkstemp(); os.write(fd2, json.dumps(delta).encode()); os.close(fd2)\n"
        "sys.argv = [sys.argv[0], path1, path2]\n" + _gate_snippet()
    )
    return subprocess.run(["python3", "-c", tmp_script], capture_output=True, text=True)


_FULL_CERT = {
    "cap_R": {"observed": True, "count": 1, "total": 1},
    "cap_S": {"observed": True, "count": 1, "total": 1},
    "cap_Rs": {"observed": True, "uses": 0},
    "cap_E": {"observed": True},
    "alpha": {"observed": True, "subset_ok": True, "identity_ok": True},
    "beta": {"observed": True, "left": 1, "right": 1},
}

_FULL_DELTA = {
    "pulls": {
        "observed": True,
        "discriminated": True,
        "why": "partial last page(1<100)",
    },
    "rules_branches": {
        "observed": True,
        "discriminated": True,
        "why": "partial last page(4<100)",
    },
    "rulesets": {
        "observed": True,
        "discriminated": True,
        "why": "partial last page(1<100)",
    },
}


def test_gate_accepts_complete_certificate():
    result = _run_gate(_FULL_CERT, _FULL_DELTA)
    assert result.returncode == 0
    assert "CERT_OK" in result.stdout


def test_gate_rejects_missing_key():
    cert = copy.deepcopy(_FULL_CERT)
    del cert["cap_Rs"]
    result = _run_gate(cert, _FULL_DELTA)
    assert result.returncode != 0
    assert "CERT_FAIL" in result.stdout
    assert "KeyError" in result.stdout


def test_gate_rejects_falsy_observed_instead_of_true():
    cert = copy.deepcopy(_FULL_CERT)
    cert["cap_E"]["observed"] = 1  # truthy but not `is True` — must still be rejected
    result = _run_gate(cert, _FULL_DELTA)
    assert result.returncode != 0
    assert "CERT_FAIL" in result.stdout


def test_gate_rejects_beta_mismatch():
    cert = copy.deepcopy(_FULL_CERT)
    cert["beta"]["left"] = 2
    result = _run_gate(cert, _FULL_DELTA)
    assert result.returncode != 0
    assert "CERT_FAIL" in result.stdout


def test_gate_rejects_alpha_not_ok():
    cert = copy.deepcopy(_FULL_CERT)
    cert["alpha"]["identity_ok"] = False
    result = _run_gate(cert, _FULL_DELTA)
    assert result.returncode != 0
    assert "CERT_FAIL" in result.stdout


def test_gate_rejects_missing_delta_key():
    delta = copy.deepcopy(_FULL_DELTA)
    del delta["rulesets"]
    result = _run_gate(_FULL_CERT, delta)
    assert result.returncode != 0
    assert "CERT_FAIL" in result.stdout
    assert "KeyError" in result.stdout


def test_gate_rejects_delta_observed_but_not_discriminated():
    """The (2)② full-page ambiguity case: observed=True but discriminated is absent
    (the endpoint's last page was exactly per_page — indistinguishable from a
    silent cap) must still block, not pass on 'observed' alone."""
    delta = copy.deepcopy(_FULL_DELTA)
    delta["pulls"] = {"observed": False, "why": "last page exactly per_page(100)"}
    result = _run_gate(_FULL_CERT, delta)
    assert result.returncode != 0
    assert "CERT_FAIL" in result.stdout


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
