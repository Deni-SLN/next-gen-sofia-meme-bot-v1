import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings


class TestSignalsInsights(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        res = cls.client.post("/api/v1/auth/login", json={"username": "deni26", "password": "Ronaldo07@"})
        cls.token = res.json()["token"]
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    def test_signals_insights_all(self):
        resp = self.client.get("/api/v1/signals/insights", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("stocks", data)
        self.assertIn("crypto", data)
        self.assertEqual(len(data["stocks"]), 5)
        self.assertEqual(len(data["crypto"]), 5)

        # Verify stock items have required fields
        stock_tickers = [s["ticker"] for s in data["stocks"]]
        self.assertEqual(stock_tickers, ["BBCA", "BBRI", "TLKM", "ASII", "ANTM"])
        for stock in data["stocks"]:
            self.assertIn("name", stock)
            self.assertIn("current_price", stock)
            self.assertIn("action", stock)
            self.assertIn("entry_zone", stock)
            self.assertIn("tp_1", stock)
            self.assertIn("tp_2", stock)
            self.assertIn("stop_loss", stock)
            self.assertIn("risk_reward", stock)
            self.assertIn("catalyst", stock)
            self.assertIn("technical_summary", stock)
            self.assertIn("quality_badge", stock)
            self.assertIn("safety_score", stock)
            self.assertTrue(stock["detail_url"].startswith("/stocks?q="))

        # Verify crypto items have required fields
        crypto_symbols = [c["symbol"] for c in data["crypto"]]
        self.assertEqual(crypto_symbols, ["BTC", "ETH", "SOL", "SUI", "AVAX"])
        for coin in data["crypto"]:
            self.assertIn("name", coin)
            self.assertIn("current_price_usd", coin)
            self.assertIn("current_price_idr", coin)
            self.assertIn("action", coin)
            self.assertIn("entry_zone_usd", coin)
            self.assertIn("tp_1_usd", coin)
            self.assertIn("tp_2_usd", coin)
            self.assertIn("stop_loss_usd", coin)
            self.assertIn("risk_reward", coin)
            self.assertIn("catalyst", coin)
            self.assertIn("technical_summary", coin)
            self.assertIn("tier_badge", coin)
            self.assertIn("safety_score", coin)
            self.assertTrue(coin["detail_url"].startswith("/crypto?q="))

    def test_stock_insights_endpoint(self):
        resp = self.client.get("/api/v1/signals/stock-insights", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("stocks", data)
        self.assertEqual(len(data["stocks"]), 5)

    def test_crypto_insights_endpoint(self):
        resp = self.client.get("/api/v1/signals/crypto-insights", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("crypto", data)
        self.assertEqual(len(data["crypto"]), 5)

    def test_telegram_memecoin_signals_copy_wallet(self):
        resp = self.client.get("/api/v1/telegram/signals")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("signals", data)
        memecoins = [s for s in data["signals"] if s.get("is_memecoin")]
        self.assertGreaterEqual(len(memecoins), 4)
        for m in memecoins:
            self.assertTrue(bool(m.get("contract_address")), f"Missing CA for {m.get('ticker')}")
            self.assertTrue(bool(m.get("wallet_address")), f"Missing Wallet for {m.get('ticker')}")
