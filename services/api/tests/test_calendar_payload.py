import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.services import performance, stocks
from app.db.session import SessionLocal


class TestCalendarPayload(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        login_res = self.client.post(
            "/api/v1/auth/login",
            json={"password": settings.admin_password},
        )
        token = login_res.json().get("token")
        self.headers = {"Authorization": f"Bearer {token}"}

    def test_calendar_trade_limit_per_day(self):
        """Verify daily calendar endpoint respects trade_limit_per_day query parameter."""
        r = self.client.get(
            "/api/v1/performance/daily-calendar?mode=PAPER&trade_limit_per_day=10",
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("days", data)
        for day in data.get("days", []):
            self.assertLessEqual(len(day.get("trades", [])), 10)

    def test_chart_pnl_capped_at_200(self):
        """Verify PnL chart data caps points to prevent excessive payload."""
        with SessionLocal() as db:
            summary = performance.get_summary(db)
            self.assertIn("pnl_chart", summary)
            # Initial point + up to 200 trade points
            self.assertLessEqual(len(summary["pnl_chart"]), 201)

    def test_round_price_magnitude_handling(self):
        """Verify _round_price preserves decimal magnitude for tiny sub-cent meme tokens."""
        # Micro price (0.0000045) should NOT be rounded to 0.0
        p1 = stocks._round_price(0.0000045678)
        self.assertGreater(p1, 0.0)
        self.assertEqual(p1, 0.00000457)

        # Cent price (0.05432) rounds to 6 decimals
        p2 = stocks._round_price(0.05432)
        self.assertEqual(p2, 0.05432)

        # Standard price (123.456) rounds to 2 decimals
        p3 = stocks._round_price(123.456)
        self.assertEqual(p3, 123.46)

    def test_bollinger_lower_clamp_non_negative(self):
        """Verify Bollinger bands lower band clamps to 0.0, avoiding negative or artificial 0.01 floor."""
        # Test low price calculation
        history = [0.0001] * 20
        bb = stocks._compute_bollinger_bands(history, period=20, std_dev=2.0)
        self.assertGreaterEqual(bb["lower"], 0.0)


if __name__ == "__main__":
    unittest.main()
