"""Worker packaging and scheduler regression (Tahap 2).

The defect: `docker-compose.yml` ran `python -m worker.main` from `WORKDIR
/app`, but `worker` lives at `/app/services/worker` and `app` at
`/app/services/api`. Neither directory was on `sys.path`, so the worker
container died at import. `docker compose config -q` validated the YAML and
called it a pass.

`test_import_paths_are_package_relative` is the guard: it fails if anyone
reintroduces a top-level `from config import` / `from jobs import`, because the
container only puts `services` and `services/api` on the path.
"""

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

WORKER_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = WORKER_DIR.parents[1]
WORKER_MODULES = sorted(WORKER_DIR.glob("*.py"))

# Spelled out deliberately. A mistyped provider variable is silently ignored by
# the settings layer, so a test that meant to go offline would quietly go live.
DEXSCREENER_ENV = "SOFIA_" + "DEXSCREENER_BASE_URL"
UNREACHABLE = "http://127.0.0.1:1"


def _container_env(**overrides) -> dict:
    """Environment for a child process that mimics the container.

    Starts from the real environment and pins exactly the two import roots the
    image sets, so the child resolves `worker` and `app` the way the container
    does and nothing else can paper over a packaging regression.
    """
    import os as _os

    env = _os.environ.copy()
    env["PYTHONPATH"] = _os.pathsep.join(
        [str(REPO_ROOT / "services"), str(REPO_ROOT / "services" / "api")]
    )
    env.update(overrides)
    return env


def test_offline_provider_override_actually_takes_effect():
    """Guard the guard: prove `SOFIA_DEXSCRENER_BASE_URL` is honoured.

    If the settings layer ever stops reading this variable, the offline tests
    below stop being offline and start hitting the real provider.
    """
    from app.core.config import Settings

    assert DEXSCREENER_ENV == "SOFIA_DEXSCREENER_BASE_URL"
    probe = _container_env(**{DEXSCREENER_ENV: UNREACHABLE, "SOFIA_ENV": "test"})
    assert probe[DEXSCREENER_ENV] == UNREACHABLE
    # And the settings class reads it, not just os.environ.
    restored = Settings.model_fields
    assert "dexscreener_base_url" in restored
    import os as _os

    previous = _os.environ.get(DEXSCREENER_ENV)
    _os.environ[DEXSCREENER_ENV] = UNREACHABLE
    try:
        assert Settings().dexscreener_base_url == UNREACHABLE
    finally:
        if previous is None:
            _os.environ.pop(DEXSCREENER_ENV, None)
        else:
            _os.environ[DEXSCREENER_ENV] = previous


# --------------------------- import shape ---------------------------


def test_worker_is_importable_as_a_package():
    import worker.jobs
    import worker.main

    assert worker.main.run_once is not None
    assert worker.jobs.job_discovery is not None


@pytest.mark.parametrize("module", WORKER_MODULES, ids=lambda p: p.name)
def test_import_paths_are_package_relative(module):
    """No top-level `config` / `jobs` / `main` imports.

    The container resolves `worker.*` via `PYTHONPATH=/app/services`. A
    `from config import ...` only works when `services/worker` itself is on the
    path, which the image never sets - that is the bug this file exists for.
    """
    tree = ast.parse(module.read_text(encoding="utf-8"))
    forbidden = {"config", "jobs", "main"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "") not in forbidden, (
                f"{module.name} does `from {node.module} import ...`; "
                "worker modules must import via `worker.<module>`"
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in forbidden, (
                    f"{module.name} does `import {alias.name}`; use `import worker.<module>`"
                )


def test_dockerfile_sets_the_two_import_roots():
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "PYTHONPATH=" in dockerfile, "the image must put the import roots on PYTHONPATH"
    assert "/app/services/api" in dockerfile, "the API package root must be importable"
    # The services root is what makes `worker` itself importable.
    assert "/app/services" in dockerfile


def test_worker_compose_service_uses_the_package_entrypoint():
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "python\", \"-m\", \"worker.main" in compose.replace("'", '"')
    # A worker healthcheck is what turns "the container is up" into
    # "the scheduler is ticking".
    assert "SOFIA_WORKER_HEARTBEAT" in compose


def test_ci_builds_the_image_and_proves_the_worker_runs():
    """`docker compose config -q` parses YAML. It cannot tell that the worker
    container dies at import, which is exactly what happened. CI must build the
    image and start the worker in it."""
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "docker build" in ci, "CI must build the image"
    assert "worker.main --once" in ci, "CI must start the worker"
    assert "import worker.main" in ci, "CI must prove the worker package imports in the image"
    assert "imports ok" in ci, "the import check must assert, not just run"


def test_ci_does_not_treat_compose_validation_as_runtime_proof():
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "docker compose config -q" in ci, "compose validation is still useful"
    # ...but a job that only validates compose must not be the only proof.
    assert ci.count("docker run --rm") >= 2, (
        "compose validation alone is not runtime evidence; CI must actually run containers"
    )


# --------------------------- entrypoint behaviour ---------------------------


def test_main_once_returns_zero_and_writes_a_heartbeat(tmp_path, monkeypatch):
    """Entrypoint contract: exit 0 plus proof the scheduler ticked.

    `main()` reads `sys.argv` to choose between the one-shot run and the
    long-running loop, and the loop never returns - so the test has to say
    `--once` explicitly or it hangs rather than fails.

    The jobs are stubbed too. `job_discovery` runs `asyncio.run` inside a sync
    test, which the asyncio plugin in this suite does not cooperate with; the
    real end-to-end start is covered by the subprocess tests below, which run
    in a clean process.
    """
    import worker.main as wm

    heartbeat = tmp_path / "hb"
    monkeypatch.setattr(wm, "HEARTBEAT_PATH", str(heartbeat))
    monkeypatch.setattr(sys, "argv", ["worker.main", "--once"])
    monkeypatch.setattr(wm, "job_discovery", lambda f: {"ok": True, "stubbed": True})
    monkeypatch.setattr(wm, "job_analysis", lambda f, use_ai=False: {"ok": True, "stubbed": True})
    monkeypatch.setattr(wm, "job_signal_lifecycle", lambda f: {"ok": True, "stubbed": True})
    monkeypatch.setattr(wm, "job_signal_evaluation", lambda f: {"ok": True, "stubbed": True})
    assert not heartbeat.exists()

    assert wm.main() == 0
    assert heartbeat.exists(), "a completed run must prove the scheduler ticked"
    assert heartbeat.read_text(encoding="utf-8")


def test_main_without_once_enters_the_loop(tmp_path, monkeypatch):
    """Guards the branch the test above depends on: no `--once`, no return."""
    import worker.main as wm

    entered: list[str] = []
    monkeypatch.setattr(wm, "HEARTBEAT_PATH", str(tmp_path / "hb"))
    monkeypatch.setattr(sys, "argv", ["worker.main"])
    monkeypatch.setattr(wm, "run_loop", lambda: entered.append("loop"))
    assert wm.main() == 0
    assert entered == ["loop"]


def test_bootstrap_failure_is_fatal_in_once_mode(monkeypatch):
    """A worker that cannot reach the schema must not report success."""
    import worker.main as wm

    def _boom(strict: bool = False):
        raise RuntimeError("schema is behind")

    monkeypatch.setattr(sys, "argv", ["worker.main", "--once"])
    monkeypatch.setattr(wm, "bootstrap", _boom)
    monkeypatch.setattr(wm, "run_once", lambda: pytest.fail("must not run jobs after a failed bootstrap"))
    assert wm.main() == 2


def test_bootstrap_failure_is_survivable_in_loop_mode(monkeypatch):
    """The long-running worker retries rather than exiting on a DB restart."""
    import worker.main as wm

    calls: list[str] = []

    def _boom(strict: bool = False):
        calls.append("bootstrap")
        raise RuntimeError("db restarting")

    def _no_loop():
        raise AssertionError("run_loop must not be reached when bootstrap fails")

    monkeypatch.setattr(sys, "argv", ["worker.main"])
    monkeypatch.setattr(wm, "bootstrap", _boom)
    monkeypatch.setattr(wm, "run_loop", _no_loop)
    assert wm.main() == 0
    assert calls == ["bootstrap"]


def test_run_once_runs_every_job_and_survives_a_failing_one(monkeypatch):
    import worker.main as wm

    ran: list[str] = []
    monkeypatch.setattr(wm, "job_discovery", lambda f: ran.append("discovery") or {"ok": True})
    monkeypatch.setattr(wm, "job_analysis", lambda f, use_ai=False: ran.append("analysis") or {"ok": True})
    monkeypatch.setattr(wm, "job_signal_lifecycle", lambda f: ran.append("lifecycle") or {"ok": True})
    monkeypatch.setattr(wm, "job_signal_evaluation", lambda f: ran.append("evaluation") or {"ok": True})

    def _explode(factory):
        raise RuntimeError("provider down")

    monkeypatch.setattr(wm, "job_discovery", _explode)
    wm.run_once()

    # One dead job must not stop the others.
    assert ran == ["analysis", "lifecycle", "evaluation"]


def test_safe_returns_none_on_failure_and_the_result_on_success():
    import worker.main as wm

    assert wm._safe("x", lambda: {"ok": True}) == {"ok": True}

    def _boom():
        raise RuntimeError("nope")

    assert wm._safe("x", _boom) is None


# --------------------------- jobs against a real schema ---------------------------


def test_signal_lifecycle_is_a_noop_on_an_empty_book(db):
    from worker.jobs import job_signal_lifecycle

    result = job_signal_lifecycle(lambda: db)
    assert result["ok"] is True
    assert result["expired"] == 0
    assert result["processed"] == 0
    assert result["validated"] == 0, "nothing to validate on an empty book"


def test_signal_lifecycle_expires_stale_signals(db):
    from datetime import UTC, datetime, timedelta

    from app.models.analysis import AnalysisRun, Signal
    from app.models.market import Token, TokenPair
    from worker.jobs import job_signal_lifecycle

    token = Token(chain="solana", mint_address="MintExpiry111111111111111111111111111111", symbol="X")
    db.add(token)
    db.flush()
    pair = TokenPair(token_id=token.id, pair_address="p-expiry")
    db.add(pair)
    db.flush()
    run = AnalysisRun(
        token_id=token.id,
        pair_id=pair.id,
        engine_version="engine-v1",
        scoring_config_version="scoring-v1",
        decision="LONG_CANDIDATE",
        reasons=["test"],
        input_snapshot={},
        provider_versions={},
    )
    db.add(run)
    db.flush()
    db.add(
        Signal(
            analysis_run_id=run.id,
            token_id=token.id,
            pair_id=pair.id,
            mint_address=token.mint_address,
            signal_type="LONG",
            status="CREATED",
            decision="LONG_CANDIDATE",
            reasons=["test"],
            engine_version="engine-v1",
            strategy_version="v1",
            expires_at=datetime.now(UTC) - timedelta(minutes=5),
        )
    )
    db.commit()

    result = job_signal_lifecycle(lambda: db)
    assert result["expired"] == 1
    db.expire_all()
    assert db.query(Signal).one().status == "EXPIRED"

    # Re-running must not re-expire or mutate anything further.
    assert job_signal_lifecycle(lambda: db)["expired"] == 0


def test_signal_evaluation_is_idempotent(db):
    from app.models.analysis import SignalEvaluation
    from worker.jobs import job_signal_evaluation

    job_signal_evaluation(lambda: db)
    job_signal_evaluation(lambda: db)
    assert db.query(SignalEvaluation).count() == 0  # nothing to evaluate yet


def test_analysis_job_reports_success_on_an_empty_book(db):
    from worker.jobs import job_analysis

    result = job_analysis(lambda: db)
    assert result["ok"] is True and result["analyzed"] == 0 and result["narrated"] == 0


def test_discovery_job_reports_failure_instead_of_raising():
    """A dead provider must produce a failed result, not a crashed worker.

    Runs in its own process: the job calls `asyncio.run`, which does not
    cooperate with the asyncio plugin in this suite.
    """
    code = (
        "import json;"
        "from worker.config import bootstrap; bootstrap();"
        "from app.db.session import SessionLocal;"
        "from worker.jobs import job_discovery;"
        "print('RESULT', json.dumps(job_discovery(SessionLocal)))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO_ROOT),
        env=_container_env(
            **{
                "SOFIA_DATABASE_URL": f"sqlite:///{REPO_ROOT / 'data' / 'test_discovery_offline.db'}",
                "SOFIA_ENV": "development",
                # A closed loopback port: connection refused, no DNS, no egress.
                DEXSCREENER_ENV: UNREACHABLE,
            }
        ),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stderr
    line = [x for x in proc.stdout.splitlines() if x.startswith("RESULT")]
    assert line, f"job_discovery did not report a result:\n{proc.stdout}\n{proc.stderr}"
    payload = json.loads(line[0].split("RESULT", 1)[1])
    assert payload["ok"] is False
    assert payload["error"], "a failure must carry a reason, not an empty string"


def test_jobs_close_their_session(db):
    """A job that leaks a session exhausts the pool and wedges the worker."""
    from worker.jobs import job_analysis, job_signal_lifecycle

    created = []

    class Tracking:
        def __init__(self, session):
            self._session = session
            self.closed = False
            created.append(self)

        def __getattr__(self, item):
            return getattr(self._session, item)

        def close(self):
            self.closed = True
            self._session.close()

    job_analysis(lambda: Tracking(db))
    job_signal_lifecycle(lambda: Tracking(db))
    assert created and all(s.closed for s in created)


# --------------------------- container-equivalent invocation ---------------------------


def test_module_runs_with_only_the_container_import_roots(tmp_path):
    """Runs `python -m worker.main --once` with sys.path restricted to exactly
    what the image sets. This is the local equivalent of the container start the
    CI job performs; it fails if the import roots regress.

    Provider base URLs point at a closed loopback port, so the discovery job
    fails closed in seconds instead of reaching for the real DEX Screener.
    """
    db_path = tmp_path / "worker_smoke.db"
    env = _container_env(
        **{
            "SOFIA_DATABASE_URL": f"sqlite:///{db_path}",
            "SOFIA_ENV": "development",
            DEXSCREENER_ENV: UNREACHABLE,
            "SOFIA_SOLANA_RPC_URL": UNREACHABLE,
            "SOFIA_WORKER_HEARTBEAT": str(tmp_path / "hb"),
        }
    )
    proc = subprocess.run(
        [sys.executable, "-m", "worker.main", "--once"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, f"worker failed to start:\n{proc.stdout}\n{proc.stderr}"
    assert "No module named" not in proc.stderr, proc.stderr
    assert (tmp_path / "hb").exists(), "the worker must prove it ran"


def test_worker_refuses_to_start_against_a_stale_schema(tmp_path):
    """`--once` must not report success against a schema it cannot verify.

    `SOFIA_ENV=production` with an unstamped database is exactly the state the
    compose `migrate` step exists to prevent; if it ever reaches the worker the
    worker has to say so rather than run jobs against a missing column.
    """
    env = _container_env(
        **{
            "SOFIA_DATABASE_URL": f"sqlite:///{tmp_path / 'stale.db'}",
            "SOFIA_ENV": "production",
            "SOFIA_WORKER_HEARTBEAT": str(tmp_path / "hb2"),
        }
    )
    proc = subprocess.run(
        [sys.executable, "-m", "worker.main", "--once"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 2, f"expected a bootstrap failure exit code:\n{proc.stdout}\n{proc.stderr}"
    assert "alembic" in proc.stderr.lower()
