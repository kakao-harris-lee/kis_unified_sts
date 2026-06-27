# Architecture Audit Parallel Investigation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:dispatching-parallel-agents for this investigation. This is a read-only architecture audit. Do not edit files. Return evidence-backed findings with exact file/line references.

**Goal:** Identify architecture violations and maintainability risks in the runtime trading pipeline, especially monolithic condition-heavy flow, code-listing style, and violations of stream-pipeline boundaries.

**Architecture:** Split the audit by independent runtime domains so agents can inspect in parallel without overlapping work. The coordinator integrates findings into a ranked remediation plan after all agents report back.

**Tech Stack:** Python async services, Redis streams and consumer groups, Docker Compose profiles, shared strategy/execution/storage modules.

---

## Global Rules For All Agents

- Work in `/Users/harris/Development/private/kis_unified_sts`.
- Read `AGENTS.md` and `CLAUDE.md` before inspecting subsystem files.
- Do not modify files, run formatters, or stage changes.
- Prefer `rg`, `nl -ba`, `sed`, `python3 -m compileall`, and small AST/read-only scripts.
- Findings must include:
  - Severity: `Critical`, `High`, `Medium`, or `Low`.
  - Exact file and one line reference.
  - Why it is an architecture problem.
  - Whether it violates stream-pipeline separation, single-responsibility boundaries, or configuration-driven rules.
  - A concrete remediation direction.
- Do not duplicate other agents' domains.
- Return a concise report with sections: `Findings`, `Evidence`, `Recommended Next Steps`, `Residual Questions`.

## Domain Split

### Agent A: Monolithic Orchestrator And Internal Pipeline

**Scope:**
- `services/trading/orchestrator.py`
- `services/trading/pipeline.py`
- Closely referenced helpers only when needed to understand a finding.

**Questions:**
- Is `TradingOrchestrator` acting as a single object that owns unrelated responsibilities?
- Are `asset_class`, `paper_trading`, `live`, `stock`, or `futures` conditionals being used as architecture routing instead of separate components?
- Is `TradingPipeline` a real data pipeline or only an interval scheduler over orchestrator methods?
- Which extraction points are lowest risk and highest leverage?

**Suggested Commands:**

```bash
python3 -c $'import ast,pathlib\np=pathlib.Path("services/trading/orchestrator.py"); t=ast.parse(p.read_text())\nrows=[]\nfor n in ast.walk(t):\n    if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):\n        end=getattr(n,"end_lineno",n.lineno); span=end-n.lineno+1\n        branches=sum(isinstance(x,(ast.If,ast.For,ast.AsyncFor,ast.While,ast.Try,ast.With,ast.AsyncWith,ast.Match,ast.BoolOp,ast.IfExp)) for x in ast.walk(n))\n        rows.append((span,branches,n.lineno,n.name))\nfor row in sorted(rows, reverse=True)[:40]: print(*row, sep="\\t")'
rg -n "asset_class|paper_trading|live|stock|futures|_handle_entry|_execute_entry|_process_filled|_kill_switch" services/trading/orchestrator.py
nl -ba services/trading/pipeline.py | sed -n '169,411p'
```

**Expected Output:**
- 5-8 ranked findings focused on monolith boundaries and internal pipeline shape.
- Explicit answer: whether current futures primary runtime violates stream-pipeline architecture.

### Agent B: Stock Decoupled Pipeline

**Scope:**
- `services/stock_strategy/main.py`
- `services/stock_strategy/daemon.py`
- `services/stock_risk_filter/main.py`
- `services/stock_order_router/main.py`
- `services/stock_exit/daemon.py`
- `services/stock_monitor/daemon.py`
- `docker-compose.yml` stock services section.

**Questions:**
- Does the stock path preserve `market:ticks -> candidate -> risk -> final -> fill -> monitor/exit` stage boundaries?
- Does `StockStrategyDaemon` contain too many policy roles in one evaluation loop?
- Are risk/order stages clean `StreamStage` consumers?
- Are exit and monitor timer/bridge loops acceptable exceptions or architecture debt?

**Suggested Commands:**

```bash
rg -n "signal\\.candidate\\.stock|signal\\.final\\.stock|order\\.fill\\.stock|market:ticks|StockStrategyDaemon|StreamStage|xreadgroup|xack|while not self\\._stop" services/stock_* shared/streaming docker-compose.yml
python3 -c $'import ast,pathlib\nfor path in ["services/stock_strategy/daemon.py","services/stock_exit/daemon.py","services/stock_monitor/daemon.py"]:\n p=pathlib.Path(path); t=ast.parse(p.read_text()); print("\\n"+path)\n rows=[]\n for n in ast.walk(t):\n  if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):\n   end=getattr(n,"end_lineno",n.lineno); span=end-n.lineno+1\n   branches=sum(isinstance(x,(ast.If,ast.For,ast.AsyncFor,ast.While,ast.Try,ast.With,ast.AsyncWith,ast.Match,ast.BoolOp,ast.IfExp)) for x in ast.walk(n))\n   rows.append((span,branches,n.lineno,n.name))\n for row in sorted(rows, reverse=True)[:20]: print(*row, sep="\\t")'
nl -ba docker-compose.yml | sed -n '190,264p'
```

**Expected Output:**
- Verdict on stock pipeline compliance.
- Specific debt items that can be refactored without changing trading behavior.
- Recommended extraction units for `StockStrategyDaemon`.

### Agent C: Futures Decoupled Pipeline And Cutover Readiness

**Scope:**
- `services/market_ingest/main.py`
- `services/decision_engine/main.py`
- `services/risk_filter/main.py`
- `services/order_router/main.py`
- `services/futures_monitor/daemon.py`
- `services/futures_monitor/main.py`
- `docs/runbooks/futures-pipeline-cutover-f9.md`
- `docker-compose.yml` futures services section.

**Questions:**
- Is the futures decoupled chain complete as a stream pipeline?
- During shadow and live cutover, where does it still depend on monolithic `trader-futures`?
- Are stream names, mode names, and paper/live semantics consistent across decision/risk/order/monitor?
- Does `order_router` combine too much execution, exit monitoring, and safety logic in one class?

**Suggested Commands:**

```bash
rg -n "signal\\.candidate\\.futures|signal\\.final\\.futures|order\\.fill\\.futures|raw_data|FUTURES_|shadow|paper|live|StreamStage|xreadgroup|PseudoOCO|PassiveMaker" services/market_ingest services/decision_engine services/risk_filter services/order_router services/futures_monitor docker-compose.yml docs/runbooks/futures-pipeline-cutover-f9.md
nl -ba docs/runbooks/futures-pipeline-cutover-f9.md | sed -n '37,115p'
nl -ba docker-compose.yml | sed -n '265,342p'
python3 -c $'import ast,pathlib\nfor path in ["services/decision_engine/main.py","services/order_router/main.py","services/futures_monitor/daemon.py"]:\n p=pathlib.Path(path); t=ast.parse(p.read_text()); print("\\n"+path)\n rows=[]\n for n in ast.walk(t):\n  if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):\n   end=getattr(n,"end_lineno",n.lineno); span=end-n.lineno+1\n   branches=sum(isinstance(x,(ast.If,ast.For,ast.AsyncFor,ast.While,ast.Try,ast.With,ast.AsyncWith,ast.Match,ast.BoolOp,ast.IfExp)) for x in ast.walk(n))\n   rows.append((span,branches,n.lineno,n.name))\n for row in sorted(rows, reverse=True)[:20]: print(*row, sep="\\t")'
```

**Expected Output:**
- Cutover readiness risks.
- Stream contract mismatches or naming/mode inconsistencies.
- Clear distinction between available decoupled chain and current primary runtime.

### Agent D: Shared Streaming Framework, Contracts, And Duplicated Loops

**Scope:**
- `shared/streaming/stage.py`
- `shared/streaming/consumer.py`
- `shared/streaming/publisher.py`
- `services/trading/stream_consumer_feed.py`
- Any direct `xreadgroup` or `xread` loops found under `services/`.

**Questions:**
- Is `StreamStage` the canonical stream consumer abstraction, and where is it bypassed?
- Are monitor/bridge daemons bypassing pending retry and reclaim behavior?
- Is `StreamConsumerFeed` a feed abstraction or a hidden processing stage?
- Are stream TTLs, ACK behavior, and poison-pill policies consistent?

**Suggested Commands:**

```bash
rg -n "xreadgroup|xread\\(|xack|xautoclaim|StreamStage|while not self\\._stop|while True|expire\\(" services shared/streaming
nl -ba shared/streaming/stage.py | sed -n '1,220p'
nl -ba services/trading/stream_consumer_feed.py | sed -n '1,245p'
```

**Expected Output:**
- Inventory of direct stream loops not using `StreamStage`.
- Policy gaps in retry/ACK/TTL behavior.
- Recommendation for whether to introduce `MultiStreamStage` or keep current loops.

## Coordinator Integration

After all agents return:

1. Deduplicate findings by root cause.
2. Rank by runtime risk and refactor leverage.
3. Produce a final architecture audit with:
   - Current architecture verdict.
   - Violations and borderline exceptions.
   - Safe refactor sequence.
   - Tests/verification commands for any follow-up implementation.
4. If implementation is requested later, create a separate implementation plan with disjoint write scopes.
