# Runbook — Next Gent Sofia Trade v1 operations (Phase 7)

Operational procedures. Read the relevant section before acting; several
commands are destructive.

---

## 1. Start the stack

```bash
export POSTGRES_PASSWORD='<strong password>'
cp .env.example .env          # then edit
docker compose up -d --build
docker compose ps             # wait for api + web to become healthy
```

Verify:

```bash
curl -fsS http://localhost:8000/api/v1/health
# {"status":"ok","service":"Next Gent Sofia Trade v1","version":"1.0.0"}
```

The `migrate` service runs `alembic upgrade head` and must exit `0` before
`api`/`worker` start. If it fails, the database is at an unknown revision —
do not restart the app to "clear" it.

---

## 2. Health triage

| Symptom | Meaning | Action |
| --- | --- | --- |
| `/api/v1/health` 5xx | DB unreachable | Check `docker compose ps db`; the endpoint runs `SELECT 1` |
| `/api/v1/health` 200, pages empty | Schema migrated, no data yet | Trigger discovery: `POST /api/v1/discover/ingest` |
| API exits at startup | Safety guard tripped | Read the log line; see §3 |
| 401 on every request | Session missing/expired | Log in again; check `SOFIA_SESSION_TTL_SECONDS` |

---

## 3. Startup guards (intentional, do not "fix" by disabling)

The API refuses to boot when:

- `SOFIA_AUTH_DISABLED=true` outside `development` / `test` / `local`
- no admin credential is configured
- `SOFIA_LIVE_TRADING_ENABLED=true` (live trading is not a V1 capability)

These are PRD §16 requirements. Set a real `SOFIA_ADMIN_PASSWORD_HASH`
(`python -m app.cli.hash_password`) instead of disabling auth.

---

## 4. Backup

```bash
BACKUP_DIR=./backups ./scripts/backup.sh backup
BACKUP_DIR=./backups ./scripts/backup.sh list
```

Writes `sofia-<UTC timestamp>.dump` plus a `.sha256` sidecar. Schedule it
(daily at minimum) and copy archives off-host — an archive stored only on the
same volume is not a backup.

---

## 5. Restore (destructive)

```bash
BACKUP_DIR=./backups ./scripts/backup.sh restore ./backups/sofia-20250101T000000Z.dump
```

The script verifies the checksum first and requires the database name to be
typed as confirmation. After restoring, restart `api` and `worker` so pooled
connections are recycled:

```bash
docker compose restart api worker
curl -fsS http://localhost:8000/api/v1/health
```

---

## 6. Migrations

```bash
docker compose run --rm migrate            # upgrade to head
docker compose run --rm migrate alembic current
docker compose run --rm migrate alembic downgrade -1
```

Never call `init_db()` to "create tables" in an existing deployment — Alembic
owns schema. `init_db` only runs as a development convenience at startup.

---

## 7. Provider degradation

Market/on-chain providers fail independently; the pipeline degrades rather than
halting:

| Provider | Symptom | Effect |
| --- | --- | --- |
| DEX Screener down | `/api/v1/providers/status` not ok | No new pairs; existing analysis keeps running on stored candles |
| Solana RPC down | same, `solana_rpc` not ok | On-chain checks become **UNKNOWN**, which fails closed — tokens are rejected rather than passed |

UNKNOWN is never treated as PASS (FR-AE-004). A wave of REJECT decisions after
an RPC outage is expected behaviour, not a bug.

---

## 8. Kill the bot

```bash
curl -fsS -X POST http://localhost:8000/api/v1/bot/emergency-stop -H "Authorization: Bearer $TOKEN"
curl -fsS http://localhost:8000/api/v1/bot/status -H "Authorization: Bearer $TOKEN"
```

Use `pause`/`resume` for a controlled stop. `emergency-stop` also clears the
kill switch; clearing it requires explicit confirmation and is audited.

---

## 9. Rollback

1. Stop writes: `docker compose stop api worker`
2. Restore the last known-good archive (§5)
3. Deploy the previous image tag
4. `docker compose up -d api worker`
5. Confirm `/api/v1/health`, then `GET /api/v1/system/status`

---

## 10. Before calling it production

- [ ] `SOFIA_AUTH_DISABLED=false` and a real password hash is set
- [ ] `SOFIA_ENV` is not `development`
- [ ] `SOFIA_LIVE_TRADING_ENABLED=false` (V1 requirement, not a default you may flip)
- [ ] Database backups scheduled and one restore rehearsed
- [ ] Secrets supplied via environment, never committed