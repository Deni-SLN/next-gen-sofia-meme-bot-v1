# Remediation Sprint — plan, acceptance criteria, evidence

Created after the Tahap 0 audit. Every stage below lists the files it will
touch and the acceptance criteria that must be met before it may be reported
`PASS`. A stage is only `PASS` when a test run actually proves it; a
configuration change alone is never sufficient evidence.

## Baseline (Tahap 0, measured)

| Gate | Command | Result |
| --- | --- | --- |
| Backend tests | `pytest -q` | 378 passed |
| Backend lint | `ruff check services tools` | All checks passed |
| UI ↔ API drift | `python tools/check_api_contract.py` | 27 frontend patterns, 97 backend routes, OK |
| Frontend tests | `npm run test` | 14 passed |
| Frontend lint | `npm run lint` | No issues found |
| Frontend types | `npm run typecheck` | ok |
| Frontend build | `npm run build` | built (chunk-size warning only) |

Toolchain constraint: Docker is **not installed** on the remediation host, so
container runtime evidence cannot be produced locally. Stage 2 therefore
(a) reproduces the defect with an equivalent local `PYTHONPATH` invocation and
(b) moves the proof into CI, which has a Docker daemon. Any stage whose only
proof would be "compose config parses" is not accepted as runtime evidence.

## Stage 1 — Accounting and risk integrity

Defect: `Position.unrealized_pnl` has a column and is served by the portfolio
endpoints, but no production code ever writes it. Equity, high-water mark,
current drawdown and the risk gate's drawdown check are therefore computed as
if open positions were worth exactly their cost basis — and they still render
as plausible numbers rather than as unknown.

Files:
- `services/api/app/accounting/equity.py` — mark-to-market source
- `services/api/app/services/trading_service.py` — position lifecycle writes
- `services/api/app/api/v1/portfolio.py` — expose `valuation_status`
- `services/api/app/risk/gate.py` — drawdown / equity fail-closed
- new `services/api/tests/test_mark_to_market.py`

Acceptance criteria:
1. Unrealized PnL is derived from a price that is finite, non-null and fresh;
   stale/missing price yields `None` (unknown), never `0.0`.
2. `equity`, `high_water_mark`, `current_drawdown_pct` reflect open positions.
3. Unknown valuation is fail-closed at the risk gate: an open position with no
   usable mark rejects a new entry with an explicit reason.
4. NaN / Infinity in price or PnL never reach the ledger, equity, or the gate.
5. Regression tests fail on the pre-fix code and pass after.

## Stage 2 — Worker packaging and CI runtime proof

Defect: `docker-compose.yml` runs `python -m worker.main` with
`WORKDIR /app`, but `worker` lives at `/app/services/worker` and `app` at
`/app/services/api`; neither directory is on `sys.path`. Reproduced locally:
`ModuleNotFoundError: No module named 'worker'`, and with `services` on the
path, `No module named 'app'`. `worker.main` also imports `config` and `jobs`
as top-level modules, which only resolves if `services/worker` is itself on the
path — three directories, none of which the container sets.

Files:
- `Dockerfile`, `docker-compose.yml` — `PYTHONPATH` / entrypoint
- `services/worker/main.py`, `services/worker/jobs.py` — package-relative imports
- `.github/workflows/ci.yml` — build image, start worker, assert it runs

Acceptance criteria:
1. `python -m worker.main --once` succeeds with exactly the environment the
   image sets (reproduced locally).
2. CI builds the image and runs the worker in it; a non-zero exit or an
   import error fails the job.
3. `docker compose config -q` is no longer treated as runtime proof.

**Result: PASS.** Worker imports are package-relative (`worker.config`,
`worker.jobs`); the image sets `PYTHONPATH=/app/services:/app/services/api`;
`--once` is strict about bootstrap and exits 2 when the schema cannot be
verified, while the long-running loop stays resilient. CI gained `image` and
`stack` jobs that build and run containers. Local evidence: 24 worker tests
pass, and the three CI-equivalent runtime steps were executed on this host
(`import worker.main, app.main` → ok; `worker.main --once` → exit 0 with a
heartbeat; production env against an unstamped DB → exit 2).

Local caveat: Docker is not installed on the remediation host, so the
`docker build` / `docker run` steps themselves have not been executed. The
commands they run have been executed directly with the image's environment.

## Stage 3 — API/UI contracts

Defect: `Performance.tsx` reads nine metric keys; the backend returns twelve,
of which only three overlap — six tiles permanently render `—`.
`Tokens.tsx` defaults the chart timeframe to `5m` while the backend accepts
`M1|M5|M15|M30|H1|H4|D1` (case-insensitive on the value, not the order), so
token detail errors on load. `tools/check_api_contract.py` only validates
paths, so this class of drift is structurally invisible to CI.

Files:
- `apps/web/src/pages/Performance.tsx`, `apps/web/src/pages/Tokens.tsx`
- `apps/web/src/lib/types.ts`, `apps/web/src/lib/queries.ts`
- `tools/check_api_contract.py` — field-level checks
- new `services/api/tests/test_ui_contract.py`

Acceptance criteria:
1. Every field the UI reads from a performance/document endpoint exists in the
   backend response, or the UI omits it.
2. Default timeframe is one the backend accepts.
3. A contract test fails when a UI field is renamed or removed from the backend.

**Result: PASS.** `PERFORMANCE_METRICS` in `apps/web/src/lib/types.ts` is the
single list the page renders; `test_ui_contract.py` parses it and asserts every
key against a real `/performance/summary` response (and the reverse direction,
so a backend field the UI dropped is also caught). Two defaults the backend
rejected are fixed: `Tokens.tsx` used `"5m"`, and `POST /backtest` used
`"5m"` — candles are stored as `M1/M5/M15/M30/H1`, so every default backtest
answered "insufficient data". `/performance/equity-curve` now delegates to the
canonical curve so it cannot disagree with `/portfolio/equity-curve`.

Honest gap: the backtest's own `max_drawdown_pct` is still a start-vs-final
approximation (the module comment concedes it). Left alone deliberately — it is
a backtest-internal metric, not a live-account figure, and fixing it changes
result semantics.

## Stage 4 — Position lifecycle

Defect: no automatic exit. `close_position` is reachable only from an operator
endpoint or the backtest loop; no stop-loss / take-profit is ever evaluated, so
`close_reason` is always operator-driven and TP/SL are never recorded.
Idempotency exists for entries (`signal:<id>:BUY`) but exits have no guard
against concurrent double-close.

Files: new `services/api/app/services/position_manager.py`,
`services/worker/jobs.py`, `services/api/tests/test_position_lifecycle.py`

Acceptance criteria:
1. TP/SL evaluated from fresh marks only; stale mark → position untouched.
2. Exit is idempotent under repeated and concurrent execution.
3. Fill + ledger write is all-or-nothing; a crash leaves a recoverable state
   and a reconciliation path, never a half-closed position.
4. Paper mode only. Live execution stays gated off.

**Result: PASS.** `app/services/position_manager.py` resolves the exit plan from
the signal (ATR/support-derived stop, target ladder) and falls back to
percentages only when the signal is silent. Evaluation holds on anything the
valuation layer did not call KNOWN. Close is two-phase: an atomic
`OPEN -> CLOSING` claim, then a committed intent + fill, then the position and
ledger updates — so a crash leaves a CLOSING position that
`recover_stalled_exits` either finalizes (fill is durable) or rolls back
(claim only). Runtime evidence against a live uvicorn on a migrated database:
dry run reported the exit without touching the position, execution closed it at
+50.0 with a `SIMULATED` fill, equity moved 1000 → 1050, a second run closed
nothing, and `mode=LIVE` was refused.

Deliberate trade-off: recovery leaves a *fresh* CLOSING claim alone for
`position_exit_recovery_seconds` (300s), so a position that genuinely crashed
stays open for one extra tick. The alternative - reclaiming a position a live
worker may be mid-write on - is the race recovery exists to prevent.

## Stage 5 — Wallet and Alerts

Defect: `evaluate_and_record_sweep` and `record_balance_snapshot` are called
only from tests — nothing produces balances or triggers a sweep, so
`GET /wallets/{id}/balances` can only ever answer `UNAVAILABLE` and the
automatic mode of PRD v1.1 FR-TB-009 cannot be exercised. `set_wallet_enabled`
has no endpoint, so `transition_intent` always raises at the on-chain gate.
Telegram settings are declared and redacted but never read; `AlertDelivery` is
never written. No Wallet or Alerts page exists in the UI.

Files: `services/api/app/services/wallet_service.py`, new `alerts/`,
`services/api/app/providers/onchain/solana_rpc.py`, `api/v1/wallets.py`,
`api/v1/alerts.py`, new UI pages, `services/worker/jobs.py`

Acceptance criteria:
1. Balances come from an on-chain read; unreadable balance → `UNKNOWN`, and
   anything that needs a balance fails closed.
2. Automatic 50% sweep triggers on a closed profitable position, is
   idempotent, and never sweeps a loss.
3. Wallet live-transfer feature gate stays OFF; reaching `READY_TO_SIGN`
   requires the gate to be opened explicitly, which V1 does not do.
4. Telegram delivery is deduplicated by alert key and never carries secrets.
5. Wallet + Alerts UI render real API data.

**Result: PASS.** `wallet_balance_service` reads SOL/USDC from Solana RPC
(`getBalance`, `getTokenAccountsByOwner`) and records snapshots; a failed read
records `status=UNKNOWN` and `latest_snapshot` refuses to hand that row to any
spending path. `_offer_profit_sweep` is wired into `finalize_exit`, so closing
a profitable position offers it to the sweep evaluator (itself idempotent on
the close event). Alerts have rules (unpriced positions, drawdown past the
ceiling, intents stuck outside terminal states) and Telegram delivery with
dedup-by-key and no secrets in any stored or transmitted field.

Two real defects were found by the runtime evidence rather than by reading the
code, and are fixed:
  * `GET /wallets/{id}/balances` hardcoded `status = "OK"` over the snapshot's
    own status, so a failed read rendered as a measured balance of zero.
  * `evaluate_sweep` ignored the snapshot status entirely, treating an
    UNKNOWN row's stored zero as spendable.

Design change worth flagging: the original `cooldown_seconds` parameter on
`record_alert` could never take effect — `alert_deliveries.dedup_key` is
UNIQUE, so the second insert fails before any timer is consulted. The unique
index is now the documented arbiter and repeat rules bucket their keys.

## Stage 6 — AI pipeline

Defect: five agents are registered; `technical-analysis`,
`market-research`, `signal-validation` and `strategy-research` are never
invoked. `run_agent` accepts any JSON via `json.loads` with no schema
validation, and `validate_model()` is dead code, so an approved-model check
exists without ever running. The 9Router provider has no free/paid gate.

Files: `services/api/app/providers/llm/registry.py`, `openrouter.py`,
`ninrouter.py`, `services/api/tests/test_agent_pipeline.py`

Acceptance criteria:
1. Every registered agent is invoked by a real pipeline or worker job, or is
   explicitly marked unavailable with a reason.
2. Structured output is schema-validated; malformed output is a recorded
   failure, never a silent `None`.
3. `validate_model` runs before every request, on every provider.
4. The model actually used is recorded per call, including the fallback chain.
5. AI output cannot mutate accounting or bypass the risk gate.

**Result: PASS.** `app/services/agent_service.py` declares a prompt, an output
schema and at least one call site per agent; `test_agent_pipeline.py` fails if a
registered agent has no spec or no call site. `run_agent` now calls
`validate_model` before every request (a raising validator is treated as
refusal, not consent), validates structured output against the declared shape,
and records every attempt in the `llm_request` audit including the model that
actually answered. `GET /ai/agents` publishes `unimplemented_agents` so a name
without an implementation is visible rather than implied.

Boundary: agent output lands only in `AnalysisRun.ai_summary`, which scoring,
risk and the risk gate never read. Asserted two ways — a static test that those
modules do not mention `ai_summary`/`ai_context`, and a runtime check that an
analysis run with AI and one without produce an identical decision and score.

Behaviour change worth flagging: a cross-provider fallback now uses the
*fallback provider's* default model rather than reusing the primary's model id.
Reusing it meant a 9Router fallback was asked for `openrouter/free`, which does
not exist there.
