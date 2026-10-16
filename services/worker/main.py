"""Worker scheduler entrypoint.

Runs deterministic background jobs on configurable intervals. Failures in one
job never stop the scheduler. No live execution ever happens here.

Imports are package-relative (`worker.*`) and the runtime needs `services` and
`services/api` on `sys.path`, which is what the container sets via
`PYTHONPATH`. Previously this module imported `config` and `jobs` as top-level
modules, so it only resolved when `services/worker` itself was on the path -
one of three different directories, none of which the image configured. That
made `python -m worker.main` fail at import in the container.

Run with:
    python -m worker.main            # run loop
    python -m worker.main --once     # run every job once and exit
"""

import os
import sys
import time
from datetime import UTC, datetime

from app.core.config import settings
from app.db.session import SessionLocal
from worker.config import bootstrap, get_logger
from worker.jobs import (
    job_alerts,
    job_analysis,
    job_discovery,
    job_position_lifecycle,
    job_signal_evaluation,
    job_signal_lifecycle,
    job_wallet_balances,
)

log = get_logger("worker")

# Touched on every scheduler tick so a container healthcheck can tell a running
# scheduler from a process that started and then wedged.
HEARTBEAT_PATH = os.environ.get("SOFIA_WORKER_HEARTBEAT", "/tmp/sofia-worker.heartbeat")


def _heartbeat() -> None:
    try:
        with open(HEARTBEAT_PATH, "w", encoding="utf-8") as fh:
            fh.write(datetime.now(UTC).isoformat())
    except OSError as exc:  # a read-only /tmp must not kill the scheduler
        log.warning("could not write worker heartbeat: %s", exc)


def _safe(name, fn):
    try:
        result = fn()
        log.info("job %s -> %s", name, result)
        return result
    except Exception as e:  # noqa: BLE001 - never let one job kill the worker
        log.exception("job %s failed: %s", name, e)
        return None


def run_once() -> None:
    _heartbeat()
    _safe("discovery", lambda: job_discovery(SessionLocal))
    _safe("analysis", lambda: job_analysis(SessionLocal, use_ai=False))
    _safe("signal_lifecycle", lambda: job_signal_lifecycle(SessionLocal))
    # Exits run after signals so a position opened this tick is eligible, and
    # after evaluation so the ledger it reads is already written.
    _safe("position_lifecycle", lambda: job_position_lifecycle(SessionLocal))
    # Balances are read after exits, so a close that a sweep will act on has
    # already produced its ledger entry.
    _safe("wallet_balances", lambda: job_wallet_balances(SessionLocal))
    _safe("signal_evaluation", lambda: job_signal_evaluation(SessionLocal))
    _safe("alerts", lambda: job_alerts(SessionLocal))


def run_loop() -> None:
    last = {
        "discovery": 0.0,
        "analysis": 0.0,
        "lifecycle": 0.0,
        "exits": 0.0,
        "balances": 0.0,
        "evaluation": 0.0,
        "alerts": 0.0,
    }
    intervals = {
        "discovery": settings.worker_scanner_interval,
        "analysis": settings.worker_analysis_interval,
        "lifecycle": settings.worker_signal_eval_interval,
        "exits": settings.worker_signal_eval_interval,
        # Balances feed the sweep reserve, so they are refreshed more often
        # than the exits that consume them.
        "balances": max(15, settings.worker_signal_eval_interval // 2),
        "evaluation": settings.worker_signal_eval_interval * 5,
        "alerts": settings.worker_signal_eval_interval,
    }
    log.info("worker started with intervals %s", intervals)
    _heartbeat()
    while True:
        now = time.monotonic()
        _heartbeat()
        for name, fn in (
            ("discovery", lambda: job_discovery(SessionLocal)),
            ("analysis", lambda: job_analysis(SessionLocal, use_ai=False)),
            ("signal_lifecycle", lambda: job_signal_lifecycle(SessionLocal)),
            ("position_lifecycle", lambda: job_position_lifecycle(SessionLocal)),
            ("wallet_balances", lambda: job_wallet_balances(SessionLocal)),
            ("signal_evaluation", lambda: job_signal_evaluation(SessionLocal)),
            ("alerts", lambda: job_alerts(SessionLocal)),
        ):
            if now - last[name] >= intervals[name]:
                _safe(name, fn)
                last[name] = now
        time.sleep(min(intervals.values()))


def main() -> int:
    """Entrypoint. Returns a process exit code.

    `--once` is strict about bootstrap: if the schema is not reachable there is
    nothing to do and the process must say so with a non-zero exit rather than
    reporting success. The long-running loop stays resilient instead, because a
    worker that gives up during a database restart is worse than one that waits.
    """
    strict = "--once" in sys.argv
    try:
        bootstrap(strict=strict)
    except Exception as exc:  # noqa: BLE001
        if strict:
            log.exception("worker bootstrap failed")
            print(f"worker bootstrap failed: {exc}", file=sys.stderr)
            return 2
        log.exception("worker bootstrap failed; scheduler will retry on the next tick")
        return 0

    if strict:
        run_once()
        return 0
    run_loop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
