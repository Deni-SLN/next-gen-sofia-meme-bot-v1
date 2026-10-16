from app.db.session import init_db

init_db()
print("DB initialized")

from fastapi.testclient import TestClient
from app.main import app

with TestClient(app) as c:
    r = c.get("/api/v1/bot/status")
    print("bot/status", r.status_code, r.json())

    r2 = c.get("/api/v1/portfolio/overview")
    print("portfolio/overview", r2.status_code)
    print("  ", r2.json())

    r3 = c.post("/api/v1/bot/start", json={"mode": "PAPER"})
    print("bot/start PAPER", r3.status_code, "status=", r3.json().get("status"), "mode=", r3.json().get("mode"))

    r4 = c.post("/api/v1/bot/start", json={"mode": "LIVE"})
    print("bot/start LIVE", r4.status_code, "code=", r4.json()["error"]["code"])

    r5 = c.get("/api/v1/signals")
    print("signals", r5.status_code, "total=", r5.json().get("total"))

    r6 = c.get("/api/v1/ai/agents")
    print("ai/agents", r6.status_code, "count=", len(r6.json().get("agents", [])))

    r7 = c.get("/api/v1/risk/config")
    print("risk/config", r7.status_code)

    r8 = c.get("/api/v1/performance/summary")
    print("performance/summary", r8.status_code, r8.json())
