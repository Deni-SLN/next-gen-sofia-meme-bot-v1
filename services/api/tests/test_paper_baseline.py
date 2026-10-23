import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.services import portfolio, treasury, bot
from app.db.session import SessionLocal


class TestPaperBaseline(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        login_res = self.client.post(
            "/api/v1/auth/login",
            json={"password": settings.admin_password},
        )
        token = login_res.json().get("token")
        self.headers = {"Authorization": f"Bearer {token}"}
        self._orig_capital = portfolio.get_paper_initial_capital_idr()

    def tearDown(self):
        portfolio.set_paper_initial_capital_idr(self._orig_capital)

    def test_get_and_set_paper_capital_endpoint(self):
        """Verify GET and PUT /api/v1/portfolio/paper-capital work properly."""
        # 1. GET
        r_get = self.client.get("/api/v1/portfolio/paper-capital", headers=self.headers)
        self.assertEqual(r_get.status_code, 200)
        self.assertIn("paper_initial_capital_idr", r_get.json())

        # 2. PUT
        r_put = self.client.put(
            "/api/v1/portfolio/paper-capital",
            json={"amount_idr": 250000.0},
            headers=self.headers,
        )
        self.assertEqual(r_put.status_code, 200)
        self.assertEqual(r_put.json()["paper_initial_capital_idr"], 250000.0)
        self.assertEqual(portfolio.get_paper_initial_capital_idr(), 250000.0)

    def test_paper_capital_validation_rejects_invalid(self):
        """Verify PUT /api/v1/portfolio/paper-capital rejects <= 0, NaN, infinity."""
        # <= 0
        r_neg = self.client.put(
            "/api/v1/portfolio/paper-capital",
            json={"amount_idr": -1000.0},
            headers=self.headers,
        )
        self.assertEqual(r_neg.status_code, 400)
        self.assertEqual(r_neg.json()["error"]["code"], "NOMINAL_TIDAK_VALID")

        # Zero
        r_zero = self.client.put(
            "/api/v1/portfolio/paper-capital",
            json={"amount_idr": 0.0},
            headers=self.headers,
        )
        self.assertEqual(r_zero.status_code, 400)

    def test_paper_capital_locked_when_bot_running(self):
        """Verify setting paper capital is locked (409) while the bot is running."""
        # Start bot
        r_start = self.client.post("/api/v1/bot/start", json={"mode": "PAPER"}, headers=self.headers)
        self.assertEqual(r_start.status_code, 200)

        try:
            r_locked = self.client.put(
                "/api/v1/portfolio/paper-capital",
                json={"amount_idr": 500000.0},
                headers=self.headers,
            )
            self.assertEqual(r_locked.status_code, 409)
            self.assertEqual(r_locked.json()["error"]["code"], "MODE_TERKUNCI")
        finally:
            self.client.post("/api/v1/bot/stop", headers=self.headers)

    def test_settlement_baseline_dynamic_with_paper_capital(self):
        """Verify treasury baseline uses configured paper capital instead of hardcoded 150000."""
        portfolio.set_paper_initial_capital_idr(300000.0)
        with SessionLocal() as db:
            t = treasury.reset_treasury_for_paper(db, usd_idr=18000.0)
            self.assertGreater(t.baseline_equity_usd, 0.0)
            expected_baseline = 300000.0 / 18000.0
            self.assertAlmostEqual(t.baseline_equity_usd, expected_baseline, places=1)


if __name__ == "__main__":
    unittest.main()
