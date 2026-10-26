import unittest
from fastapi.testclient import TestClient
from app.main import app


class TestAutoEntry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        res = cls.client.post("/api/v1/auth/login", json={"username": "deni26", "password": "Ronaldo07@"})
        cls.token = res.json()["token"]
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    def test_auto_entry_status(self):
        resp = self.client.get("/api/v1/auto-entry/status", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("status", data)
        self.assertIn("entry_amount_idr", data)
        self.assertIn("max_entries", data)
        self.assertIn("slippage_pct", data)
        self.assertIn("total_entries_count", data)
        self.assertIn("entries_history", data)

    def test_auto_entry_update_config(self):
        resp = self.client.put(
            "/api/v1/auto-entry/config",
            json={
                "entry_amount_idr": 25000.0,
                "max_entries": 4,
                "slippage_pct": 1.5,
                "min_safety_score": 75,
                "mode": "PAPER",
            },
            headers=self.headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["entry_amount_idr"], 25000.0)
        self.assertEqual(data["max_entries"], 4)
        self.assertEqual(data["slippage_pct"], 1.5)
        self.assertEqual(data["min_safety_score"], 75)
        self.assertEqual(data["mode"], "PAPER")

    def test_auto_entry_start_and_stop(self):
        # 1. Start Auto Entry
        resp_start = self.client.post(
            "/api/v1/auto-entry/start",
            json={
                "entry_amount_idr": 20000.0,
                "max_entries": 3,
                "slippage_pct": 1.0,
                "mode": "PAPER",
            },
            headers=self.headers,
        )
        self.assertEqual(resp_start.status_code, 200)
        start_data = resp_start.json()
        self.assertIn(start_data["status"], ("RUNNING", "QUOTA_REACHED"))

        # 2. Stop Auto Entry
        resp_stop = self.client.post("/api/v1/auto-entry/stop", headers=self.headers)
        self.assertEqual(resp_stop.status_code, 200)
        self.assertEqual(resp_stop.json()["status"], "STOPPED")

    def test_auto_entry_reset_counter(self):
        resp = self.client.post("/api/v1/auto-entry/reset-counter", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_entries_count"], 0)
        self.assertEqual(data["total_spent_idr"], 0.0)
        self.assertEqual(data["entries_history"], [])

    def test_auto_entry_trigger_scan(self):
        # Trigger scan when standby
        resp_scan = self.client.post("/api/v1/auto-entry/trigger-scan", headers=self.headers)
        self.assertEqual(resp_scan.status_code, 200)
        data = resp_scan.json()
        self.assertIn("status", data)
