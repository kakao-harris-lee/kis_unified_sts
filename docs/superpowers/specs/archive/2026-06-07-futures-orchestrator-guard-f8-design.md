# Futures Orchestrator Guard (F-8) — Design

**Status:** Approved (design) — 2026-06-07
**Scope unit:** F-8 of the futures-decoupling roadmap (Phase C safety precondition). Mirrors the stock M5e guard for futures. Docker deployment (no systemd).

---

## 1. Problem

The decoupled futures chain is now fully functional (F-1..F-7) but dormant. When an operator eventually cuts over — brings up the decoupled futures daemons (as docker-compose services) — the in-process orchestrator (`sts trade start --asset futures`, run by the `trader` container) would **also** trade futures, causing **double trading** (two systems on the same account). There is no guard to make the orchestrator stand down for futures, unlike stock (which has `STOCK_ORCHESTRATOR_ENABLED`, M5e).

## 2. Goal

Add a `FUTURES_ORCHESTRATOR_ENABLED` flag + guard so the orchestrator refuses `--asset futures` when disabled — the futures mirror of M5e. Default `true` (current behavior: orchestrator IS the futures path); the operator sets `false` at cutover so only the decoupled chain trades. Environment-agnostic (it gates the CLI command the `trader` container runs); paper/live distinction is unchanged (Docker env).

## 3. Approach (decided)

Mirror the stock guard (`cli/main.py::_stock_orchestrator_enabled`/`_stock_orchestrator_blocked` + the `trade_start` gate). Add parallel `_futures_orchestrator_enabled`/`_futures_orchestrator_blocked` (per-asset functions matching the existing codebase style — the stock guard already takes an `asset` arg and returns False for the other asset). **Guard only** — no systemd cleanup, no compose changes (deploying the decoupled daemons is F-9/operator).

## 4. Design

### 4.1 `cli/main.py`

```python
def _futures_orchestrator_enabled() -> bool:
    """The monolithic orchestrator runs futures only when explicitly enabled.

    Default ``True`` (the orchestrator IS today's futures path). The operator
    sets ``FUTURES_ORCHESTRATOR_ENABLED=false`` at the futures cutover so the
    orchestrator refuses futures — the decoupled chain (decision_engine →
    risk_filter → order_router) owns it, preventing double-trading on the same
    account. Rollback: set it back to ``true`` (``1``/``yes`` also accepted).
    """
    return os.getenv("FUTURES_ORCHESTRATOR_ENABLED", "true").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _futures_orchestrator_blocked(asset: str) -> bool:
    """True when the orchestrator must refuse this asset (futures + flag disabled)."""
    return asset == "futures" and not _futures_orchestrator_enabled()
```

### 4.2 `trade_start` gate

After the existing stock-blocked check (which `sys.exit(1)`s), add the futures-blocked check:
```python
    if _futures_orchestrator_blocked(asset):
        click.echo(
            "Error: the monolithic orchestrator no longer runs futures — futures "
            "trades via the decoupled chain (decision_engine → risk_filter → "
            "order_router).",
            err=True,
        )
        click.echo(
            "  Rollback to the orchestrator futures path: set "
            "FUTURES_ORCHESTRATOR_ENABLED=true.",
            err=True,
        )
        sys.exit(1)
```
`asset` is a single value, so at most one of the stock/futures blocks fires.

### 4.3 Docker usage (documentation, not code)

At cutover the operator sets `FUTURES_ORCHESTRATOR_ENABLED=false` in the `trader` service env (`docker-compose.yml`) and brings up the decoupled futures daemons as compose services. Default-true means **nothing changes until set** — the orchestrator keeps trading futures today. paper/live remains a Docker concern (`TRADING_MODE`/`KIS_REAL_TRADING` → `--paper`/`--live`), orthogonal to this guard.

## 5. Safety

- **Default-true → zero behavior change** until the operator sets it false at cutover.
- **Guard only blocks the orchestrator**, not the decoupled chain; double-trade prevention = operator sets the flag false AND runs the decoupled chain (the two halves of the cutover).
- No compose/systemd changes; nothing is deployed or enabled by F-8.

## 6. Testing

Mirror `tests/unit/test_cli_stock_guard.py` → `tests/unit/test_cli_futures_guard.py`:
- `_futures_orchestrator_enabled` default-true; false + case-insensitive; truthy set `{1,true,yes}`; non-truthy → False.
- `_futures_orchestrator_blocked` matrix: futures+disabled → True; stock → False (only futures blocked); default → False.
- `sts trade start --asset futures --paper` with `FUTURES_ORCHESTRATOR_ENABLED=false` → exit 1 + the decoupled-chain message + the `FUTURES_ORCHESTRATOR_ENABLED=true` rollback hint.
- Regression: `test_cli_stock_guard.py` unchanged + green (stock guard untouched).
- Full CI-parity gate; ruff/black.

## 7. Out of scope

- Removing vestigial `deploy/systemd/` files / correcting CLAUDE.md's systemd wording (operator chose guard-only).
- Adding the decoupled futures daemons to docker-compose (F-9 cutover).
- F-9 cutover runbook (Gate 1-3 + written approval).

## 8. Acceptance criteria

1. `FUTURES_ORCHESTRATOR_ENABLED` (default true) gates `sts trade start --asset futures`; false → exit 1 with a clear message + rollback hint.
2. Default-true preserves current orchestrator futures behavior; stock guard unchanged.
3. Tests mirror the stock guard; full gate green; ruff/black clean.
