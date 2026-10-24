"""The RENDERED stock tenant tree boots ``--transport kis-mock`` offline (B2 · B3, 2026-10-24).

The 2026-10-24 dry-run of Monday's first MOCK session found two boot refusals that only an
off-repo render reaches, so this file renders for real — ``render_paper_config.render`` into
``tmp_path``, outside the repository, exactly as the tenant runner does — and boots the result:

* **B2.** ``broker_scopes.yaml::instance_path`` is committed relative to the committed file
  (``../../../docs/…``) and the loader resolves it against the directory it reads, which after
  a render is the output directory. The manifest slot now rewrites it to the same document in
  the source checkout. The #932 host facts (MOCK/REAL ``rest_base``) come from that file.
* **B3.** The tree's Order Construction Policy said ``_runtime.wire_codec: null``; a kis-mock
  boot requires ``kis-order-cash-v1``. Generation 4 declares it.

The boot runs in a subprocess (this legacy-side file may not import ``tos``/``tos_runtime``).
It follows the production compose path (``load_construction_config`` + ``compose_paper_runtime``
with ``TransportKind.KIS_MOCK``, the tree's own policies, the runtime's default providers) with
four test seams. Three are the ones ``tos/runtime/tests/compose/test_kis_mock_e2e_honesty.py``
uses: the MOCK_VTS document's ``rest_base`` and the sealed egress endpoint point at a
``127.0.0.1`` fake KIS server, and the session clock is a fixed Monday 10:00 KST. The fourth is
``release.yaml::expected_dependency_set_digest``, a property of the deploy host's interpreter
(``tools/tos_redigest.py``), set to this interpreter's measured value; the code digest is not
touched. ``kis_mock_transport.yaml``
is ``mode: dry_run``: no order POST is possible, and the tests assert none happened.

Two further blockers sat behind B2/B3:

* **B4** — fixed: ``safety_activation.yaml`` carried no ``approval_ids`` /
  ``compatibility_attestation_refs``, so SPG activation was DEFERRED, the safety mesh held, and
  every broker-reaching tick halted before step 1 (``LIVE_SCOPE_NOT_AUTHORIZED``). The operator
  approved the activation on 2026-10-24 (``docs/plans/2026-10-24-tos-stock-mock-activation-
  record.md``); the committed render now reaches step 4.
* **B5** — fixed: ``authority.yaml::containment_bound_ms`` was 1000 and nothing re-verified the
  Safety Authority witness between boot and the send boundary, so once a second had passed the
  witness stayed absent and CURRENTNESS was UNKNOWN. Operator decision 2026-10-24 (option A):
  a per-pass heartbeat (``tos_runtime/compose/_authority_heartbeat.py``) and this tree's bound at
  90000; the committed render now carries a signal past the first second.

The committed render with no approval stops exactly at step 4 (``INDEPENDENT_APPROVAL``); with an
approval for the attempt, all 17 verify items are SATISFIED and the dry-run send seals — nothing
staged in the copy.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT_DIR = _REPO_ROOT / "scripts" / "tos"
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import render_paper_config as rpc  # noqa: E402

_STOCK = _REPO_ROOT / "config" / "tos_runtime" / "cp3-setup-d-stock-005930"
_INSTANCE = (
    _REPO_ROOT / "docs" / "broker-profiles" / "KIS-BROKER-CAPABILITY-PROFILE-draft.yaml"
)
_FAKE_SERVER = (
    _REPO_ROOT
    / "tos"
    / "runtime"
    / "tests"
    / "transport"
    / "kis_mock"
    / "_fake_kis_server.py"
)
#: A fake 8-2 stock MOCK account — never a real one.
_ACCOUNT = "88888888-01"
_SYMBOL = "005930"

#: The B2 slot, pinned as the full tuple (the manifest is data; a key-name pin would let the
#: slot be re-aimed at another leaf of the same file).
_INSTANCE_SLOT = {
    "file": "broker_scopes.yaml",
    "key": "instance_path",
    "anchor": (
        "instance_path: ../../../docs/broker-profiles/"
        "KIS-BROKER-CAPABILITY-PROFILE-draft.yaml"
    ),
    "replacement": 'instance_path: "{value}"',
    "value": "broker_profile_instance_path",
}

# ---------------------------------------------------------------------------
# The subprocess driver. A string, not a module: files outside tos/ may not import tos.
# ---------------------------------------------------------------------------
_DRIVER = r"""
import dataclasses, importlib.util, json, stat, sys, time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import yaml
from tos_runtime.brokercap import load_broker_scopes
from tos_runtime.brokercap.instance import load_instance_documents
from tos_runtime.calendar.ports import FixedWallClockReference
from tos_runtime.compose import _transport_wiring
from tos_runtime.compose._construction_config import load_construction_config
from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.compose.root import compose_paper_runtime
from tos_runtime.operations.dependency_admission import observe_dependency_set_digest
from tos_runtime.transport.kis_mock.broker_facts import load_broker_facts_config

args = json.loads(sys.argv[1])
render, data, custody = Path(args["render"]), Path(args["data"]), Path(args["custody"])
journal, band = Path(args["journal"]), Path(args["band"])
account, symbol = args["account"], args["symbol"]
order_path = "/uapi/domestic-stock/v1/trading/order-cash"
session = datetime(2026, 10, 26, 10, 0, tzinfo=ZoneInfo("Asia/Seoul"))
out = {}

# B2 — the RENDERED tree's own instance_path, loaded for real, before any patch.
scopes = load_broker_scopes(render / "broker_scopes.yaml", environment_label="paper")
docs = load_instance_documents(scopes.instance_path)
out["instance_path"] = str(scopes.instance_path)
out["rest_bases"] = {d.environment: d.rest_base for d in docs}

spec = importlib.util.spec_from_file_location("fake_kis_server", args["fake_server"])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module  # dataclass processing looks the module up by name
spec.loader.exec_module(module)
server = module.FakeKisServer()
server.start()
server.set_response("/oauth2/tokenP", status=200, body={"access_token": "t", "expires_in": 86400})
server.set_response(order_path, status=200, body={"rt_cd": "0", "msg1": "ok", "output": {"ODNO": "1"}})
server.require_account(account[:8], account[-2:])

real_loader = load_instance_documents
_transport_wiring.load_instance_documents = lambda path: tuple(
    dataclasses.replace(d, rest_base=server.rest_base) if d.environment == "MOCK_VTS" else d
    for d in real_loader(path)
)
egress = render / "egress_coordinates.yaml"
raw = yaml.safe_load(egress.read_text(encoding="utf-8"))
out["committed_egress_endpoint"] = raw["endpoint"]["value"]
raw["endpoint"]["value"] = server.rest_base + order_path
egress.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8")
# The dependency-set pin is a property of the deploy host's interpreter, not of the commit
# (tools/tos_redigest.py "Only expected_code_digest"): this interpreter's own value goes in.
# The code-digest pin is left exactly as committed.
release = render / "release.yaml"
lines = release.read_text(encoding="utf-8").split("\n")
hits = [i for i, line in enumerate(lines) if line.startswith("expected_dependency_set_digest:")]
assert len(hits) == 1, hits
lines[hits[0]] = f'expected_dependency_set_digest: "{observe_dependency_set_digest()}"'
release.write_text("\n".join(lines), encoding="utf-8")
transport = yaml.safe_load(Path(args["transport_template"]).read_text(encoding="utf-8"))
transport["endpoint_rest_base"] = server.rest_base
(render / "kis_mock_transport.yaml").write_text(yaml.safe_dump(transport), encoding="utf-8")

facts = load_broker_facts_config(render / "broker_facts.yaml")
digits = account.replace("-", "")
server.set_response(
    facts.balance_path + "?" + urlencode(
        {"CANO": digits[:8], "ACNT_PRDT_CD": digits[8:], **dict(facts.balance_params)}
    ),
    status=200, body={"rt_cd": "0", "msg1": "-", "output1": []},
)
server.set_response(
    facts.quote_path + "?" + urlencode(
        {"FID_COND_MRKT_DIV_CODE": facts.quote_market_div_code, "FID_INPUT_ISCD": symbol}
    ),
    status=200, body={"rt_cd": "0", "output": {"temp_stop_yn": "N"}},
)
band.write_text(json.dumps(dict(args["band_line"], as_of_ms=int(time.time() * 1000))) + "\n")

runtime = compose_paper_runtime(
    render, data, custody, "paper",
    construction=load_construction_config(render / "construction.yaml"),
    transport_kind=TransportKind.KIS_MOCK,
    wall_clock=FixedWallClockReference(int(session.timestamp() * 1000)),
)
out["booted"] = True
captured = []
inner = runtime.marketfeed._driver.enqueue_and_run
def _spy(event):
    result = inner(event)
    captured.append((event, result))
    return result
runtime.marketfeed._driver.enqueue_and_run = _spy

time.sleep(args["idle_before_signal_s"])
now = int(time.time() * 1000)
journal.write_text(json.dumps(dict(args["row"], as_of_ms=now - 50, received_ms=now - 80)) + "\n")
out["tick"] = runtime.marketfeed.tick_once().outcome.value

def rows(kind):
    return [json.loads(r[0])["payload"] for r in runtime.evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = ? ORDER BY rowid", (kind,)).fetchall()]

out["first"] = {
    "halt_reasons": [r["halt_reason"] for r in rows("EVENT_CONSUMED")],
    "mesh_held": [h for r in rows("COORDINATOR_MESH_HELD") for h in r["held_services"]],
    "flow_halted_steps": [r["step"] for r in rows("FLOW_HALTED")],
}
if args["approve"] and captured:
    event, first = captured[-1]
    digest = first.pipeline.proposal.canonical_digest
    intent = runtime.construction_stage.construction.intent
    path = custody / "approvals" / f"{digest}.yaml"
    path.parent.mkdir(exist_ok=True)
    path.write_text(yaml.safe_dump({
        "decision_id": f"decision-{digest[:16]}", "decision_generation": 1,
        "request_id": f"request-{digest[:16]}", "request_digest": digest,
        "trading_approval_policy_id": "test-approval-policy",
        "trading_approval_policy_generation": 1,
        "trading_approval_policy_digest": "test-approval-policy-digest",
        "result": "APPROVE", "reason_codes": ["offline-boot-test"],
        "approved_intent_envelope_id": "test-intent-envelope",
        "approved_intent_envelope_digest": intent.canonical_digest,
        "max_decision_age_ms": None, "invalidation_generation": None,
        "supersedes_decision_id": None, "environment_label": "paper",
    }, sort_keys=False), encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    runtime.driver.enqueue_and_run(event)

out["verify_items"] = {r["item"]: r["outcome"] for r in rows("VERIFY_ITEM")}
out["send_refused"] = [r["item"] for r in rows("SEND_REFUSED")]
out["counts"] = {
    kind: len(rows(kind))
    for kind in ("SEND_SEALED", "TRANSPORT_DRY_RUN", "TRANSPORT_SEND", "BROKER_FACTS_OBSERVED")
}
out["order_posts"] = len(server.requests_for(order_path))
runtime.rcl_log.close()
runtime.evidence_store.close()
server.stop()
print(json.dumps(out))
"""

#: ``kis_mock_transport.yaml`` as runbook §7.2-f fills it (``mode`` is ``dry_run`` here);
#: ``endpoint_rest_base`` is set to the fake by the driver. ``ACNT_PRDT_CD`` is the account's
#: last two digits, as ``split_kis_account`` requires; ``price_scale`` is the tree's 100.
_TRANSPORT: dict[str, Any] = {
    "mode": "dry_run",
    "endpoint_rest_base": None,
    "order_path": "/uapi/domestic-stock/v1/trading/order-cash",
    "token_path": "/oauth2/tokenP",
    "tr_id_buy": "VTTC0012U",
    "tr_id_sell": "VTTC0011U",
    "field_map": {
        "account": "CANO",
        "instrument": "PDNO",
        "quantity": "ORD_QTY",
        "price": "ORD_UNPR",
    },
    "static_body_fields": {
        "ACNT_PRDT_CD": _ACCOUNT[-2:],
        "ORD_DVSN": "00",
        "EXCG_ID_DVSN_CD": "KRX",
        "SLL_TYPE": "",
        "CNDT_PRIC": "",
    },
    "price_scale": 100,
    "min_send_interval_ms": 2000,
    "token_reissue_min_interval_s": 60,
    "request_timeout_s": 10,
    "allow_plaintext_for_tests": True,
}

#: One ``cp3-band/1`` line for 005930 at 270,000원, ±30% — every bound on the KRX tick ladder.
_BAND_LINE = {
    "kind": "cp3-band/1",
    "source_id": "tos-cp3-live/0.1.0",
    "instrument": _SYMBOL,
    "trading_date": "20261026",
    "tr_id": "FHKST01010100",
    "upper": "351000",
    "lower": "189000",
    "basis": "270000",
    "raw_payload_digest": "0" * 64,
    "producer_continuity_id": "band-probe/1",
}

#: One live-producer row (the fifteen fields) on which Setup D R1 fires: every gate true and
#: ``z_x1000`` -2500 <= the binding's -1800. 270,000원 sits on the 500원 rung.
_SIGNAL_ROW = {
    "raw_event_id": f"{_SYMBOL}:1m:20261026T100000+0900",
    "source_id": "tos-cp3-live/0.1.0",
    "instrument": _SYMBOL,
    "fields": {
        "open_x100": 27050000,
        "high_x100": 27100000,
        "low_x100": 26950000,
        "close_x100": 27000000,
        "volume": 1000,
        "session_token": "2026-10-26",
        "vwap_x100": 27500000,
        "atr14_x100": 20000,
        "z_x1000": -2500,
        "hi_vol": True,
        "stall_ok": True,
        "reversal_ok": True,
        "entry_window": True,
        "vwap_reverted": False,
        "eod": False,
    },
}


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.mktemp("stock-mock-render")
    journal = base / "journal.jsonl"
    journal.write_text("", encoding="utf-8")
    (base / "producer").mkdir()  # the runner's producer session dir (band probe output)
    out = base / "render"
    rpc.render(
        _STOCK,
        out,
        account=_ACCOUNT,
        instrument=_SYMBOL,
        revision="0" * 40,
        direction="LONG",
        journal_path=journal,
        band_journal_path=base / "producer" / "band.jsonl",
    )
    return out


def _custody(root: Path) -> Path:
    """Runbook §7.2-f's custody block, with fake bytes."""
    root.mkdir(mode=0o700)
    (root / "approvals").mkdir(mode=0o700)
    scopes = {
        "read.principal": "read-principal-v1",
        "evidence.key": "evidence-key-v1",
        "replay.params": "replay-params-v1",
        "kis_mock.app_key": "kis-mock-order-paper",
        "kis_mock.app_secret": "kis-mock-order-paper",
    }
    for name in (*scopes, "evidence.key.1"):
        (root / name).write_bytes(f"test-secret-{name}".encode())
        (root / name).chmod(0o600)
    manifest = root / "custody.manifest.yaml"
    manifest.write_text(
        yaml.safe_dump(
            {
                "environment_label": "paper",
                "scopes": {
                    name: {
                        "file": name,
                        "principal": principal,
                        "expected_sha256": None,
                    }
                    for name, principal in scopes.items()
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    manifest.chmod(0o600)
    return root


def _replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, (path.name, old)
    path.write_text(text.replace(old, new), encoding="utf-8")


def _boot(
    rendered: Path,
    tmp_path: Path,
    *,
    approve: bool = False,
    idle_before_signal_s: float = 0.0,
) -> dict[str, Any]:
    """Copy the render, apply the named staging edits to the COPY only, boot, drive one row."""
    render = tmp_path / "render"
    shutil.copytree(rendered, render)
    marketfeed = yaml.safe_load((render / "marketfeed.yaml").read_text("utf-8"))
    vcp = yaml.safe_load((render / "venue_constraint_policy.yaml").read_text("utf-8"))
    transport = tmp_path / "kis_mock_transport.template.yaml"
    transport.write_text(yaml.safe_dump(_TRANSPORT), encoding="utf-8")
    data = tmp_path / "data" / _SYMBOL
    data.mkdir(parents=True, mode=0o700)
    args = {
        "render": str(render),
        "data": str(data),
        "custody": str(_custody(tmp_path / "custody")),
        "journal": marketfeed["journal_path"],
        "band": vcp["_runtime"]["band_source"]["band_journal_path"],
        "account": _ACCOUNT,
        "symbol": _SYMBOL,
        "fake_server": str(_FAKE_SERVER),
        "transport_template": str(transport),
        "band_line": _BAND_LINE,
        "row": _SIGNAL_ROW,
        "approve": approve,
        "idle_before_signal_s": idle_before_signal_s,
    }
    env = rpc._subprocess_env()
    env["PYTHONPATH"] = f"{_REPO_ROOT / 'tos' / 'src'}:{_REPO_ROOT / 'tos/runtime/src'}"
    completed = subprocess.run(
        [sys.executable, "-B", "-c", _DRIVER, json.dumps(args)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(tmp_path),
        env=env,
        timeout=300,
    )
    assert completed.returncode == 0, completed.stderr[-4000:]
    return json.loads(completed.stdout.strip().splitlines()[-1])


# ---------------------------------------------------------------------------
# B2 — the instance path
# ---------------------------------------------------------------------------


def test_the_stock_manifest_declares_the_instance_path_slot() -> None:
    slots = [
        {
            "file": s.file,
            "key": s.key,
            "anchor": s.anchor,
            "replacement": s.replacement,
            "value": s.value,
        }
        for s in rpc.load_manifest(_STOCK).slots
    ]
    assert slots[-1] == _INSTANCE_SLOT
    assert [s for s in slots if s["file"] == "broker_scopes.yaml"] == [_INSTANCE_SLOT]


def test_the_rendered_instance_path_is_the_source_checkouts_document(
    rendered: Path,
) -> None:
    """The measured failure first: the committed relative value, resolved where the loader
    resolves it (the rendered file's directory), names nothing. The render's value is the
    committed value resolved against the source — the repo's own document, byte-identical.
    """
    committed = yaml.safe_load((_STOCK / "broker_scopes.yaml").read_text("utf-8"))
    assert not (rendered / committed["instance_path"]).exists()

    value = yaml.safe_load((rendered / "broker_scopes.yaml").read_text("utf-8"))[
        "instance_path"
    ]
    assert Path(value).is_absolute()
    assert Path(value) == _INSTANCE.resolve()
    assert Path(value) == (_STOCK / committed["instance_path"]).resolve()
    assert rpc.check(_STOCK, rendered) == []


def test_a_source_whose_instance_document_is_missing_refuses_the_render(
    tmp_path: Path,
) -> None:
    """A copied tree whose ``../../../docs/…`` leads nowhere: refused before anything is
    written, naming the file — not a boot refusal at 08:55."""
    source = tmp_path / "a" / "b" / "tree"
    shutil.copytree(_STOCK, source)
    journal = tmp_path / "journal.jsonl"
    journal.write_text("", encoding="utf-8")
    out = tmp_path / "out"
    with pytest.raises(rpc.RenderError, match="broker profile instance file not found"):
        rpc.render(
            source,
            out,
            account=_ACCOUNT,
            instrument=_SYMBOL,
            revision="0" * 40,
            direction="LONG",
            journal_path=journal,
            band_journal_path=tmp_path / "band.jsonl",
        )
    assert not out.exists()


# ---------------------------------------------------------------------------
# The boot chain (B2 + B3 + B4 + B5 fixed)
# ---------------------------------------------------------------------------


def test_the_committed_render_boots_kis_mock_and_stops_exactly_at_step_4(
    rendered: Path, tmp_path: Path
) -> None:
    """B2 + B3: the committed render boots (it refused on both before). The #932 host facts
    come from the instance file the rendered path names, and the committed egress endpoint is
    the MOCK host's. B4: with the recorded activation the safety mesh is clear, so the tick gets
    past the Coordinator — and with no trading approval it stops exactly at step 4
    (``INDEPENDENT_APPROVAL``, UNKNOWN — fail-closed, not a DENY). Nothing sealed, no POST.
    """
    out = _boot(rendered, tmp_path)
    assert out["booted"] is True
    assert Path(out["instance_path"]) == _INSTANCE.resolve()
    assert "openapivts" in out["rest_bases"]["MOCK_VTS"]
    assert out["rest_bases"]["REAL_PROD"] != out["rest_bases"]["MOCK_VTS"]
    assert out["committed_egress_endpoint"].startswith(out["rest_bases"]["MOCK_VTS"])

    assert out["tick"] == "TICKED"
    assert out["first"]["mesh_held"] == []
    assert out["first"]["halt_reasons"] == ["STAGE_UNKNOWN"]
    assert out["first"]["flow_halted_steps"] == ["INDEPENDENT_APPROVAL"]
    assert out["verify_items"] == {}
    assert out["counts"]["SEND_SEALED"] == 0
    assert out["order_posts"] == 0


def test_with_an_approval_all_17_items_are_satisfied_and_the_dry_run_send_seals(
    rendered: Path, tmp_path: Path
) -> None:
    """The positive path, on the committed render: the attempt's approval is written
    for its own proposal digest and the same event is re-driven (B1 — the per-proposal file;
    the session-scoped standing approval is lane-approval's PR)."""
    out = _boot(
        rendered,
        tmp_path,
        approve=True,
    )
    assert len(out["verify_items"]) == 17
    assert set(out["verify_items"].values()) == {"SATISFIED"}, out["verify_items"]
    assert out["counts"]["BROKER_FACTS_OBSERVED"] == 1
    assert out["counts"]["SEND_SEALED"] == 1
    assert out["counts"]["TRANSPORT_DRY_RUN"] == 1
    assert out["counts"]["TRANSPORT_SEND"] == 0
    assert out["order_posts"] == 0


def test_b5_a_signal_after_a_second_of_idle_is_still_17_of_17(
    rendered: Path, tmp_path: Path
) -> None:
    """B5: before the fix this case was CURRENTNESS UNKNOWN (bound 1000, witness checked only at
    boot and at the send boundary). With the committed bound (90000) the same idle second is
    inside the window, so the send boundary's own witness call establishes SAFETY_AUTHORITY.
    The per-pass heartbeat that carries a whole morning is covered in
    ``tos/runtime/tests/compose/test_authority_heartbeat.py`` (this driver calls ``tick_once``,
    not ``run_forever``)."""
    out = _boot(
        rendered,
        tmp_path,
        approve=True,
        idle_before_signal_s=1.2,
    )
    assert out["verify_items"]["CURRENTNESS"] == "SATISFIED"
    assert set(out["verify_items"].values()) == {"SATISFIED"}, out["verify_items"]
    assert out["send_refused"] == []
    assert out["counts"]["SEND_SEALED"] == 1
    assert out["order_posts"] == 0
