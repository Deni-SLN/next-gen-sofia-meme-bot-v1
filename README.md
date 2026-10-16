# Next Gent Sofia Trade v1

Solana meme-coin intelligence and trading platform. **Analysis-first and PAPER
by default — live trading is disabled in V1.**

## Safety model

These are product rules, not configuration defaults. The API refuses to boot
when they are violated.

| Rule | Enforcement |
| --- | --- |
| Auth is on by default | `SOFIA_AUTH_DISABLED=true` is refused outside `development`/`test`/`local` |
| Live trading is off in V1 | `SOFIA_LIVE_TRADING_ENABLED=true` aborts startup |
| UNKNOWN is never PASS | Unverifiable on-chain checks (mint/freeze authority, holder concentration) hard-reject |
| An LLM cannot grant safety | Authority/holder facts come from Solana RPC; `ai_context` is narrative only |
| Missing data is not zero | Unreadable volume/pricing stays `None`; it is never coerced to `0.0` |

## Layout

```
apps/web/            React + Vite terminal UI (13 pages)
services/api/        FastAPI application (app.*)
services/worker/     Background scheduler (discovery, analysis, lifecycle)
migrations/          Alembic — owns the schema
tools/               check_api_contract.py (UI ↔ API drift gate)
scripts/backup.sh    backup / list / verified restore
docs/runbook.md      operations runbook
```

## Run it

```bash
python -m venv .venv && .venv\Scripts\activate     # Windows
pip install -e ".[dev]"
cp .env.example .env                                 # set an admin password hash
alembic upgrade head
uvicorn app.main:app --app-dir services/api --reload
```

Full stack (Postgres + API + worker + web):

```bash
export POSTGRES_PASSWORD='<strong password>'
docker compose up -d --build
```

See `docs/runbook.md` for operations, backup/restore, and troubleshooting.

## Verify

```bash
ruff check services tools        # lint
pytest -q                        # backend tests
python tools/check_api_contract.py   # every UI endpoint exists on the backend
cd apps/web && npx tsc --noEmit && npm run build
```

CI (`.github/workflows/ci.yml`) runs all four on every push.

## Configuration notes

- Env vars are prefixed `SOFIA_`; see `.env.example` for the full list.
- Generate an admin hash with `python -m app.cli.hash_password 'your-password'`.
- OpenRouter is free-first **and enforced backend-side**: a model is treated as
  free only when the provider explicitly says so. Unpriced or unreadable
  pricing fails closed. Paid models require explicit per-model approval via
  `POST /api/v1/ai/openrouter/approve-paid`.
- Alembic owns the schema. `init_db()` is a development convenience only.

## Status

State is evidence-based, not aspirational. "done" means the scope is implemented
**and** verified by a test or a runtime check.

| Phase | Scope | State | Evidence / gap |
| --- | --- | --- | --- |
| 1 | Foundation, auth, migrations | done | 30 auth tests, 13 migration tests |
| 2 | Market data, on-chain | done | 31 market + 18 on-chain tests |
| 3 | Analysis engine, risk, signals | done | 26 analysis + 19 provenance + 18 risk-gate tests |
| 4 | AI agent center + cross-provider fallback | done | All five registered agents have a prompt, an output contract and a production call site. Model validation runs before every request on every provider; structured output is schema-validated and a violation is recorded as a failure, not silence; the fallback chain and the model that actually answered are both audited. AI output is narrative only — it cannot reach accounting or the risk gate. |
| 5 | Terminal UI | done | 15 pages, all reading real APIs (no fake data). Wallet and Alerts pages render balances, reserve, transfer intents and alert delivery. |
| 6 | Paper trading, accounting | done | Entry path, risk gate, fills and ledger are real and tested. Open positions are marked to market, so equity and drawdown reflect them. TP/SL exits, idempotent two-phase close, and crash recovery are implemented (`position_manager`). See stage 4. |
| 6b | Wallet sweep (PRD v1.1 FR-TB-009) | **backend complete, live gate OFF** | On-chain SOL/USDC balances are produced by the worker and recorded; an UNKNOWN read never becomes a zero balance; the automatic 50% sweep fires on a profitable close with a dynamic reserve; manual withdrawal, the transaction state machine and 51 idempotency/reconciliation tests exist; Wallet UI shipped. Live on-chain transfer stays gated off — reaching `READY_TO_SIGN` still requires an explicit on-chain gate that V1 does not open. See stage 5. |
| 7 | Hardening & deployment | done | Runbook, verified backup/restore, CI. The `worker` container starts, and CI proves it by building the image and running the worker in it (stage 2). |
| 8 | Live readiness | **out of V1 scope by design** (PRD §19) | Requires a separate approval gate: live signer/adapter, destination allowlist, caps/cooldown, recovery drills, and explicit sign-off. Wallet on-chain sweep does not become available merely because live trading is ready. |

Phases 4–7 were previously marked "done" in this file. That claim was not
supported by the code and has been corrected; `docs/remediation_plan.md` tracks
each gap with its acceptance criteria.

### Test suites

Backend (`pytest`, `services/api/tests`):

| Suite | Tests | Covers |
| --- | --- | --- |
| `test_wallet_sweep.py` | 51 | §18.F sweep, state machine, idempotency, reconciliation |
| `test_llm_providers.py` | 43 | §18.C provider gate, free-only enforcement, structured output |
| `test_market_providers.py` | 31 | §18.A 429/5xx/schema/dedup, missing ≠ zero |
| `test_auth.py` | 30 | §18.G auth, roles, sessions |
| `test_analysis.py` | 26 | §18.B indicators, risk rules, scoring |
| `test_analysis_provenance.py` | 19 | §18.B determinism, re-derivable runs |
| `test_errors.py` | 19 | §18.G error envelope |
| `test_onchain.py` | 18 | §18.A on-chain facts, UNKNOWN ≠ PASS |
| `test_risk_gate.py` | 18 | §18.D risk gate |
| `test_secrets_and_metrics.py` | 20 | §18.C secret containment, §18.E reconciliation |
| `test_migrations.py` | 13 | §18.G schema at head |
| `test_e2e_flow.py` | 7 | §18.G operator flow |
| `test_api.py` | 14 | §18.G endpoints |
| `test_cleanup.py` | 21 | scoring / signal-gen / risk cleanup paths (not retention) |
| `test_accounting.py` + `test_accounting_ext.py` | 32 | §18.E equity, HWM, drawdown |
| `test_mark_to_market.py` | 43 | §11.2 position valuation: marks, stale/unknown, equity/HWM/drawdown, API contract |
| `test_paper_trading.py` | 6 | §18.D/§18.E paper lifecycle |
| `test_llm_fallback.py` | 10 | §18.C cross-provider fallback |
| `services/worker/tests/test_worker.py` | 24 | worker packaging, entrypoint, fail-closed bootstrap |
| `test_ui_contract.py` | 18 | field-level UI ↔ API drift, timeframe contracts |
| `test_position_lifecycle.py` | 43 | TP/SL, idempotent close, fill reconciliation, crash recovery |
| `test_wallet_and_alerts.py` | 37 | on-chain balances, UNKNOWN≠zero, auto-sweep trigger, Telegram alerts |
| `test_agent_pipeline.py` | 34 | every agent wired, model gate, output validation, AI/execution boundary |

Frontend (`npm run test`, `apps/web`):

| Suite | Tests | Covers |
| --- | --- | --- |
| `ui.test.tsx` | 17 | §18.G five distinct async states, missing ≠ zero |

**Totals: 585 backend + 17 frontend = 602 tests.**

### Gates

| Gate | Command |
| --- | --- |
| Backend tests | `pytest -q` |
| Backend lint | `ruff check services tools` |
| UI ↔ API drift | `python tools/check_api_contract.py` (paths) |
| UI ↔ API field drift | `pytest services/api/tests/test_ui_contract.py` |
| Frontend tests | `cd apps/web && npm run test` |
| Frontend lint | `cd apps/web && npm run lint` |
| Frontend types | `cd apps/web && npm run typecheck` |
| Frontend build | `cd apps/web && npm run build` |
| Worker starts | `PYTHONPATH="services;services/api" python -m worker.main --once` (Linux/macOS: `PYTHONPATH=services:services/api`) |
| Container runtime | `docker compose up -d --build && docker compose ps worker` |

CI runs all of these on every push, and additionally builds the image and starts
the worker and the API inside it. `docker compose config -q` only parses YAML —
a container that dies at import used to pass it.