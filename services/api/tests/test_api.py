import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.db.session import init_db
from app.providers.llm.schemas import validate, SchemaError


class TestNextGenTSofiaTrade(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)
        res = cls.client.post("/api/v1/auth/login", json={"password": settings.admin_password})
        assert res.status_code == 200
        cls.token = res.json()["token"]
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_auth_invalid_password(self):
        r = self.client.post("/api/v1/auth/login", json={"password": "wrong-password"})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()["error"]["code"], "INVALID_PASSWORD")

    def test_unauthorized_access(self):
        r = self.client.get("/api/v1/bot/status")
        self.assertEqual(r.status_code, 401)

    def test_bot_lifecycle_and_activity_stream(self):
        self.client.post("/api/v1/portfolio/reset-paper", headers=self.headers)
        r_start = self.client.post("/api/v1/bot/start", json={"mode": "PAPER", "strategy_mode": "SAFE"}, headers=self.headers)
        self.assertEqual(r_start.status_code, 200)
        self.assertEqual(r_start.json()["status"], "running")
        self.assertEqual(r_start.json()["mode"], "PAPER")
        self.assertEqual(r_start.json()["strategy_mode"], "SAFE")
        self.assertEqual(r_start.json()["sniper_config"]["min_safety_score"], 82)

        # Switch to AGGRESSIVE mode (DexScreener + GMGN.ai New Meme Sniper)
        r_agg = self.client.put(
            "/api/v1/bot/config",
            json={"strategy_mode": "AGGRESSIVE", "apply_preset": True},
            headers=self.headers,
        )
        self.assertEqual(r_agg.status_code, 200)
        self.assertEqual(r_agg.json()["strategy_mode"], "AGGRESSIVE")
        self.assertEqual(r_agg.json()["tick_interval_ms"], 1200)
        self.assertEqual(r_agg.json()["auto_tp_pct"], 8.0)
        self.assertTrue(r_agg.json()["only_new_creations"])
        self.assertEqual(r_agg.json()["max_token_age_minutes"], 180)
        self.assertEqual(r_agg.json()["max_market_cap_usd"], 500000.0)

        # Verify BONK is strictly blocked when block_legacy_tokens=True (Aggressive mode rule)
        r_block_bonk = self.client.post(
            "/api/v1/memecoins/snipe",
            json={"symbol": "BONK", "amount_idr": 15000.0, "block_legacy_tokens": True, "mode": "PAPER"},
            headers=self.headers,
        )
        self.assertEqual(r_block_bonk.status_code, 400)
        self.assertEqual(r_block_bonk.json()["error"]["code"], "LEGACY_TOKEN_BLOCKED")

        # Verify live bot activity stream while running in AGGRESSIVE mode (fast-tracks to stage 4!)
        r_act = self.client.get("/api/v1/bot/activity?tick=true", headers=self.headers)
        self.assertEqual(r_act.status_code, 200)
        self.assertEqual(r_act.json()["status"], "running")
        self.assertEqual(r_act.json()["strategy_mode"], "AGGRESSIVE")
        self.assertIn("current_stage", r_act.json())
        self.assertGreaterEqual(len(r_act.json()["logs"]), 1)

        # Verify autonomous bot trading at Stage 4 (force_trade=true) NEVER buys BONK/PEPE/WIF
        r_auto = self.client.get("/api/v1/bot/activity?tick=true&force_trade=true", headers=self.headers)
        self.assertEqual(r_auto.status_code, 200)
        self.assertTrue(r_auto.json().get("trade_executed"))
        action_sym = str((r_auto.json().get("trade_action") or {}).get("symbol") or "").upper().split("/")[0]
        self.assertNotIn(action_sym, {"BONK", "PEPE", "WIF", "POPCAT", "DOGE", "SHIB"})

        # Reset strategy back to DEFAULT
        self.client.put("/api/v1/bot/config", json={"strategy_mode": "DEFAULT", "apply_preset": True}, headers=self.headers)

        # Verify LIVE mode bot start now succeeds 100% (no LIVE_NOT_CONFIGURED error)
        r_live = self.client.post("/api/v1/bot/start", json={"mode": "LIVE"}, headers=self.headers)
        self.assertEqual(r_live.status_code, 200)
        self.assertEqual(r_live.json()["status"], "running")
        self.assertEqual(r_live.json()["mode"], "LIVE")

        r_stop = self.client.post("/api/v1/bot/stop", headers=self.headers)
        self.assertEqual(r_stop.status_code, 200)
        self.assertEqual(r_stop.json()["status"], "stopped")

        # Verify stopping an already stopped bot is idempotent and returns 200 without BOT_NOT_RUNNING error
        r_stop_again = self.client.post("/api/v1/bot/stop", headers=self.headers)
        self.assertEqual(r_stop_again.status_code, 200)
        self.assertEqual(r_stop_again.json()["status"], "stopped")
        self.client.post("/api/v1/portfolio/reset-paper", headers=self.headers)

    def test_paper_150k_idr_live_market_snipe_and_clean_reset(self):
        # 1. Check live FX rate
        r_fx = self.client.get("/api/v1/memecoins/fx", headers=self.headers)
        self.assertEqual(r_fx.status_code, 200)
        self.assertGreater(r_fx.json()["usd_idr"], 10000.0)

        # 2. Reset Paper Account to Rp 150.000
        r_reset = self.client.post("/api/v1/portfolio/reset-paper", headers=self.headers)
        self.assertEqual(r_reset.status_code, 200)
        self.assertEqual(r_reset.json()["paper_initial_idr"], 150000.0)
        self.assertEqual(r_reset.json()["holdings"], [])
        self.assertAlmostEqual(r_reset.json()["paper_cash_idr"], 150000.0, delta=5.0)

        # 3. Snipe Rp 30.000 of PEPE using 100% live DexScreener price in PAPER mode
        r_snipe = self.client.post(
            "/api/v1/memecoins/snipe",
            json={"symbol": "PEPE", "amount_idr": 30000.0, "mode": "PAPER"},
            headers=self.headers,
        )
        self.assertEqual(r_snipe.status_code, 200)
        snipe_data = r_snipe.json()
        self.assertEqual(snipe_data["status"], "filled")
        self.assertGreater(snipe_data["entry_price"], 0.0)
        self.assertAlmostEqual(snipe_data["paper_cash_remaining_idr"], 120000.0, delta=15.0)

        # 4. Sell 50% of the holding at live market price and verify PnL chart
        sniped_symbol = snipe_data["symbol"]
        r_sell = self.client.post(
            "/api/v1/portfolio/sell",
            json={"symbol": sniped_symbol, "sell_pct": 50.0},
            headers=self.headers,
        )
        self.assertEqual(r_sell.status_code, 200)
        self.assertEqual(r_sell.json()["status"], "sold")

        # 5. Verify PnL chart has points starting from Rp 150.000
        r_perf = self.client.get("/api/v1/performance/summary", headers=self.headers)
        self.assertEqual(r_perf.status_code, 200)
        chart = r_perf.json().get("pnl_chart", [])
        self.assertGreaterEqual(len(chart), 2)
        self.assertEqual(chart[0]["equity_idr"], 150000.0)

        # 6. Click Reset Paper again and verify ALL holdings and trades are completely wiped and cash is Rp 150.000
        r_reset_final = self.client.post("/api/v1/portfolio/reset-paper", headers=self.headers)
        self.assertEqual(r_reset_final.status_code, 200)
        final_data = r_reset_final.json()
        self.assertEqual(final_data["holdings"], [])
        self.assertEqual(final_data["total_value"], 0.0)
        self.assertAlmostEqual(final_data["paper_cash_idr"], 150000.0, delta=5.0)
        self.assertAlmostEqual(final_data["total_equity_idr"], 150000.0, delta=5.0)

    def test_ai_risk_performance_wallets(self):
        r_ai = self.client.get("/api/v1/ai/agents", headers=self.headers)
        self.assertEqual(r_ai.status_code, 200)
        self.assertGreaterEqual(len(r_ai.json()["agents"]), 2)

        r_risk = self.client.put(
            "/api/v1/risk/config",
            json={"max_position_size_pct": 4.5},
            headers=self.headers,
        )
        self.assertEqual(r_risk.status_code, 200)
        self.assertEqual(r_risk.json()["max_position_size_pct"], 4.5)

        r_wal = self.client.get("/api/v1/wallets", headers=self.headers)
        self.assertEqual(r_wal.status_code, 200)
        self.assertEqual(r_wal.json()["gates"], ["main", "trading", "reserve"])
        wallets_list = r_wal.json()["wallets"]
        self.assertGreater(len(wallets_list), 0)

        # Verify changing wallet address works via PUT /api/v1/wallets/{id} and restore original address
        target_w = wallets_list[0]
        orig_addr = target_w["address"]
        new_addr = "9xCustomUpdatedSolanaWalletAddress123456789"
        r_upd = self.client.put(
            f"/api/v1/wallets/{target_w['id']}",
            json={"address": new_addr},
            headers=self.headers,
        )
        self.assertEqual(r_upd.status_code, 200)
        self.assertEqual(r_upd.json()["address"], new_addr)
        self.client.put(
            f"/api/v1/wallets/{target_w['id']}",
            json={"address": orig_addr},
            headers=self.headers,
        )

    def test_memecoin_sniper_pulse_and_rugshield(self):
        r_pulse = self.client.get("/api/v1/memecoins/pulse", headers=self.headers)
        self.assertEqual(r_pulse.status_code, 200)
        pulse_data = r_pulse.json()
        self.assertIn("new_creations", pulse_data)
        self.assertIn("final_stretch", pulse_data)
        self.assertIn("migrated", pulse_data)
        self.assertGreater(len(pulse_data["new_creations"]) + len(pulse_data["migrated"]), 0)

        r_rug_live = self.client.get("/api/v1/memecoins/rugcheck?q=WIF", headers=self.headers)
        self.assertEqual(r_rug_live.status_code, 200)
        live_audit = r_rug_live.json()
        self.assertTrue(live_audit.get("is_live_api"))
        self.assertIn("contract_clean", live_audit)
        self.assertIn("liq_mcap_ratio_pct", live_audit)
        self.assertIn("token_program", live_audit)
        self.assertIn("amm_pool_excluded_pct", live_audit)
        self.assertIn("position_sizing", live_audit)
        self.assertIn("external_links", live_audit)
        self.assertIn("axiom", live_audit["external_links"])
        self.assertIn("raydium", live_audit["external_links"])
        self.assertIn("birdeye", live_audit["external_links"])
        self.assertIn("rugcheck", live_audit["external_links"])
        self.assertIn("solscan", live_audit["external_links"])
        self.assertNotIn("SAFE TO SNIPE", live_audit["verdict"])

        r_rug_bad = self.client.get("/api/v1/memecoins/rugcheck?q=RUGDOGE/SOL", headers=self.headers)
        self.assertEqual(r_rug_bad.status_code, 200)
        self.assertLess(r_rug_bad.json()["safety_score"], 50)
        self.assertFalse(r_rug_bad.json()["contract_clean"])

        r_blocked = self.client.post(
            "/api/v1/memecoins/snipe",
            json={"symbol": "RUGDOGE/SOL", "amount_idr": 15000.0},
            headers=self.headers,
        )
        self.assertEqual(r_blocked.status_code, 400)
        self.assertEqual(r_blocked.json()["error"]["code"], "RUG_SHIELD_BLOCKED")


    def test_llm_schema_validator(self):
        spec = {
            "type": "object",
            "required": ["direction", "confidence"],
            "additional_properties": False,
            "properties": {
                "direction": {"type": "string", "max_length": 10},
                "confidence": {"type": "number"},
            },
        }
        self.assertEqual(validate({"direction": "long", "confidence": 0.9}, spec), [])
        violations = validate({"direction": 123}, spec)
        self.assertEqual(len(violations), 2)
        with self.assertRaises(SchemaError):
            validate({}, {"type": "invalid_type"})

    def test_auto_gas_topup_and_0500_wib_settlement_rules(self):
        # 1. Reset paper account & verify initial treasury state
        self.client.post("/api/v1/portfolio/reset-paper", headers=self.headers)
        r_treasury = self.client.get("/api/v1/wallets/treasury/summary", headers=self.headers)
        self.assertEqual(r_treasury.status_code, 200)
        t_data = r_treasury.json()
        self.assertEqual(t_data["profit_threshold_pct"], 40.0)
        self.assertGreaterEqual(t_data["gas_reserve_idr"], 4000.0)

        # 2. Test manual Gas Top-Up (+Rp 5.000)
        r_topup = self.client.post(
            "/api/v1/wallets/treasury/topup-gas",
            json={"amount_idr": 5000.0},
            headers=self.headers,
        )
        self.assertEqual(r_topup.status_code, 200)
        self.assertTrue(r_topup.json()["topup"]["topped_up"])
        self.assertGreater(r_topup.json()["topup"]["gas_reserve_idr"], 5000.0)

        # 3. Test 05:00 WIB Settlement when net profit <= 40% -> Must be PENDING
        r_settle_pending = self.client.post(
            "/api/v1/wallets/treasury/settle",
            json={"trigger": "manual_test"},
            headers=self.headers,
        )
        self.assertEqual(r_settle_pending.status_code, 200)
        pending_settlements = r_settle_pending.json().get("settlements", [])
        self.assertGreaterEqual(len(pending_settlements), 1)
        latest_settle = pending_settlements[0]
        self.assertEqual(latest_settle["status"], "pending")
        self.assertEqual(latest_settle["to_main_idr"], 0.0)

        # 4. Test 05:00 WIB Settlement when net profit > 40% (simulating +Rp 65.000 net profit > 40% of 150k)
        # 40% of 65.000 (Rp 26.000) -> Main Wallet; 60% (Rp 39.000) -> Modal + Gas
        r_settle_transferred = self.client.post(
            "/api/v1/wallets/treasury/settle",
            json={"trigger": "manual_test_profit_over_40", "simulate_net_profit_idr": 65000.0},
            headers=self.headers,
        )
        self.assertEqual(r_settle_transferred.status_code, 200)
        transferred_list = r_settle_transferred.json().get("settlements", [])
        self.assertGreaterEqual(len(transferred_list), 1)
        top_settle = transferred_list[0]
        self.assertEqual(top_settle["status"], "transferred")
        self.assertGreater(top_settle["to_main_idr"], 20000.0)
        self.assertGreater(top_settle["to_capital_idr"], 25000.0)

        # Clean up test settlement logs and reset paper account
        from app.db.session import SessionLocal
        from app.db.models import Settlement
        with SessionLocal() as db_s:
            db_s.query(Settlement).delete()
            db_s.commit()
        self.client.post("/api/v1/portfolio/reset-paper", headers=self.headers)

    def test_daily_calendar_pnl_by_mode(self):
        # 1. Query calendar with mode=PAPER
        r_paper = self.client.get("/api/v1/performance/daily-calendar?mode=PAPER", headers=self.headers)
        self.assertEqual(r_paper.status_code, 200)
        cal_paper = r_paper.json()
        self.assertEqual(cal_paper["mode"], "PAPER")
        self.assertIn("summary", cal_paper)
        self.assertIn("days", cal_paper)
        self.assertGreaterEqual(len(cal_paper["days"]), 28)

        # 2. Query calendar with mode=LIVE
        r_live = self.client.get("/api/v1/performance/daily-calendar?mode=LIVE", headers=self.headers)
        self.assertEqual(r_live.status_code, 200)
        cal_live = r_live.json()
        self.assertEqual(cal_live["mode"], "LIVE")

        # 3. Query calendar with mode=ALL
        r_all = self.client.get("/api/v1/performance/daily-calendar?mode=ALL", headers=self.headers)
        self.assertEqual(r_all.status_code, 200)
        cal_all = r_all.json()
        self.assertEqual(cal_all["mode"], "ALL")
        self.assertIn("month_label", cal_all)
        self.assertIn("usd_idr", cal_all)

    def test_live_trading_journal_four_cards_and_neonbase(self):
        # 1. Record a temporary live bot trade into Neonbase to test the 4 cards & table
        r_add = self.client.post(
            "/api/v1/journal/trades",
            json={
                "symbol": "TESTCOIN/SOL",
                "side": "sell",
                "quantity": 50000.0,
                "price": 0.002,
                "total": 100.0,
                "pnl": 20.0,
                "gas_fee_usd": 0.045,
                "dex_fee_usd": 0.25,
                "slippage_pct": 0.9,
                "chain": "Solana",
                "tx_hash": "test_neonbase_hash_999",
                "notes": "Verified Live Sniper Test",
            },
            headers=self.headers,
        )
        self.assertEqual(r_add.status_code, 200)
        new_id = r_add.json()["trade_id"]

        # 2. Fetch Live Trading Journal summary
        r = self.client.get("/api/v1/journal", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["mode"], "LIVE")

        # 3. Verify all 4 cards requested by user
        self.assertIn("initial_capital_usd", data)
        self.assertIn("initial_capital_idr", data)
        self.assertGreaterEqual(data["initial_capital_usd"], 0)

        self.assertIn("total_profit_usd", data)
        self.assertIn("total_profit_idr", data)
        self.assertGreaterEqual(data["total_profit_usd"], 20.0)

        self.assertIn("total_loss_usd", data)
        self.assertIn("total_loss_idr", data)
        self.assertGreaterEqual(data["total_loss_usd"], 0)

        self.assertIn("net_result_usd", data)
        self.assertIn("net_result_idr", data)
        expected_net = round(data["total_profit_usd"] - data["total_loss_usd"], 4)
        self.assertAlmostEqual(data["net_result_usd"], expected_net, places=2)

        # 4. Verify trades details (coin, quantity, price, fees, PnL)
        trades = data.get("trades", [])
        self.assertGreaterEqual(len(trades), 1)
        first = trades[0]
        self.assertIn("symbol", first)
        self.assertIn("quantity", first)
        self.assertIn("price", first)
        self.assertIn("dex_fee_usd", first)
        self.assertIn("gas_fee_usd", first)
        self.assertIn("total_fees_usd", first)
        self.assertIn("pnl_usd", first)
        self.assertIn("result", first)

        # 5. Filter by token
        r_filt = self.client.get("/api/v1/journal?q=TESTCOIN", headers=self.headers)
        self.assertEqual(r_filt.status_code, 200)
        filt_trades = r_filt.json()["trades"]
        self.assertEqual(len(filt_trades), 1)
        self.assertEqual(filt_trades[0]["symbol"], "TESTCOIN/SOL")

        # 6. Test 10 latest transactions limit constraint
        r_limit = self.client.get("/api/v1/journal?limit=5", headers=self.headers)
        self.assertEqual(r_limit.status_code, 200)
        self.assertLessEqual(len(r_limit.json()["trades"]), 5)

        # 7. Test Export to Excel (CSV with UTF-8 BOM for Microsoft Excel)
        r_excel = self.client.get("/api/v1/journal/export-excel", headers=self.headers)
        self.assertEqual(r_excel.status_code, 200)
        self.assertIn("text/csv", r_excel.headers.get("content-type", ""))
        self.assertIn("attachment; filename=", r_excel.headers.get("content-disposition", ""))
        self.assertTrue(r_excel.content.startswith(b"\xef\xbb\xbf"))
        csv_text = r_excel.content.decode("utf-8")
        self.assertIn("ID Transaksi", csv_text)
        self.assertIn("Koin / Token", csv_text)
        self.assertIn("Keuntungan / Kerugian ($)", csv_text)
        self.assertIn("Tx Hash Explorer", csv_text)

        # 8. Cleanup recorded test trade so database stays clean
        r_del = self.client.delete(f"/api/v1/journal/trades/{new_id}", headers=self.headers)
        self.assertEqual(r_del.status_code, 200)

    def test_live_mode_end_to_end_snipe_sell_and_pumpsniper_config(self):
        # 1. Test PumpSniper Terminal Config GET & PUT
        r_cfg = self.client.get("/api/v1/bot/config", headers=self.headers)
        self.assertEqual(r_cfg.status_code, 200)
        self.assertIn("relay_mode", r_cfg.json())

        r_upd_cfg = self.client.put(
            "/api/v1/bot/config",
            json={
                "relay_mode": "JITO_0SLOT",
                "jito_bribe_sol": 0.008,
                "min_bonding_curve_pct": 20.0,
                "max_dev_holding_pct": 4.0,
                "auto_tp_pct": 40.0,
                "auto_sl_pct": 12.0,
                "trailing_stop_enabled": True,
            },
            headers=self.headers,
        )
        self.assertEqual(r_upd_cfg.status_code, 200)
        self.assertEqual(r_upd_cfg.json()["relay_mode"], "JITO_0SLOT")
        self.assertEqual(r_upd_cfg.json()["auto_tp_pct"], 40.0)

        # 2. Create a temporary funded Live Wallet for testing
        r_create_w = self.client.post(
            "/api/v1/wallets",
            json={
                "name": "Temp Test Live Wallet",
                "address": "11111111111111111111111111111111",
                "chain": "Solana",
                "balance": 2.0,
                "token": "SOL",
                "gate": "trading",
            },
            headers=self.headers,
        )
        self.assertIn(r_create_w.status_code, (200, 201))
        temp_w_id = r_create_w.json()["id"]

        r_live_stat = self.client.get("/api/v1/wallets/live-status", headers=self.headers)
        self.assertEqual(r_live_stat.status_code, 200)
        self.assertGreater(r_live_stat.json()["live_cash_usd"], 0)

        from app.db.session import SessionLocal
        from app.db.models import Trade
        with SessionLocal() as db_check:
            max_id_before = max([t.id for t in db_check.query(Trade).all()] + [0])

        # 3. Execute a LIVE mode Snipe and verify tx_hash + live wallet balance deduction
        r_snipe_live = self.client.post(
            "/api/v1/memecoins/snipe",
            json={"symbol": "BONK", "amount_idr": 20000.0, "mode": "LIVE"},
            headers=self.headers,
        )
        self.assertEqual(r_snipe_live.status_code, 200)
        snipe_res = r_snipe_live.json()
        self.assertEqual(snipe_res["mode"], "LIVE")
        self.assertEqual(snipe_res["status"], "filled")
        self.assertTrue(len(snipe_res.get("tx_hash", "")) > 16)

        # 4. Execute a LIVE mode Sell (50%) and Panic Sell All (remaining 100%)
        sniped_sym = snipe_res["symbol"]
        r_sell_live = self.client.post(
            "/api/v1/portfolio/sell",
            json={"symbol": sniped_sym, "sell_pct": 50.0, "mode": "LIVE"},
            headers=self.headers,
        )
        self.assertEqual(r_sell_live.status_code, 200)
        self.assertEqual(r_sell_live.json()["mode"], "LIVE")
        self.assertTrue(len(r_sell_live.json().get("tx_hash", "")) > 16)

        r_panic = self.client.post(
            "/api/v1/portfolio/sell-all",
            json={"mode": "LIVE"},
            headers=self.headers,
        )
        self.assertEqual(r_panic.status_code, 200)
        self.assertEqual(r_panic.json()["status"], "liquidated_all")

        # 5. Clean up test LIVE trades & delete temporary test wallet
        with SessionLocal() as db_clean:
            for t in db_clean.query(Trade).filter(Trade.id > max_id_before).all():
                db_clean.delete(t)
            db_clean.commit()

        self.client.delete(f"/api/v1/wallets/{temp_w_id}", headers=self.headers)
        self.client.post("/api/v1/portfolio/reset-paper", headers=self.headers)

    def test_indonesian_news_feed_categories(self):
        import time
        now_ts = int(time.time())
        max_age_sec = 7 * 86400 + 120
        for cat in ("all", "crypto", "saham", "emas", "ekonomi", "teknologi"):
            r_news = self.client.get(f"/api/v1/news?category={cat}&limit=6&refresh=true", headers=self.headers)
            self.assertEqual(r_news.status_code, 200)
            payload = r_news.json()
            self.assertEqual(payload["category"], cat)
            self.assertEqual(payload["max_age_days"], 7)
            self.assertEqual(payload["sort_order"], "newest_first")
            articles = payload.get("articles", [])
            if articles:
                # Assert thumbnail image_url and direct link on each item
                for art in articles:
                    self.assertTrue(art["url"].startswith("http"))
                    self.assertTrue(art.get("image_url", "").startswith("http"))
                    self.assertLessEqual(now_ts - int(art["published_ts"]), max_age_sec)
                # Assert strictly sorted from newest to oldest
                timestamps = [int(a["published_ts"]) for a in articles]
                self.assertEqual(timestamps, sorted(timestamps, reverse=True))

    def test_idx_stock_analysis_endpoint(self):
        r_stock = self.client.get("/api/v1/stocks/analyze?q=BBRI&timeframe=1d", headers=self.headers)
        self.assertEqual(r_stock.status_code, 200)
        data = r_stock.json()
        self.assertEqual(data["code"], "BBRI")
        self.assertGreater(data["current_price"], 0)
        # Verify Overview & Truthful Latency Status (never falsely claiming REAL-TIME on delayed feed)
        self.assertIn("overview", data)
        self.assertIn(data["overview"]["feed_status"]["feed_badge"], ("DELAYED", "END-OF-DAY"))
        self.assertGreater(data["overview"]["ara_price"], data["overview"]["prev_close"])
        self.assertLess(data["overview"]["arb_price"], data["overview"]["prev_close"])
        # Verify IHSG
        self.assertIn("ihsg", data)
        self.assertGreater(data["ihsg"]["price"], 0)
        # Verify Technicals
        self.assertIn("technicals", data)
        self.assertIn("sma_20", data["technicals"])
        self.assertIn("ema_20", data["technicals"])
        self.assertIn("rsi_14", data["technicals"])
        self.assertIn("bollinger", data["technicals"])
        self.assertIn("atr_14", data["technicals"])
        # Verify Fundamentals & Banking Metrics for BBRI
        self.assertIn("fundamentals", data)
        self.assertEqual(data["fundamentals"]["data_status"], "VALID")
        self.assertTrue(data["fundamentals"]["is_bank"])
        self.assertIsNotNone(data["fundamentals"]["banking_metrics"])
        self.assertGreater(data["fundamentals"]["banking_metrics"]["nim_pct"], 0)
        self.assertGreater(data["fundamentals"]["banking_metrics"]["car_pct"], 10)
        # Verify Valuation (Bear / Base / Bull)
        self.assertIn("valuation", data)
        self.assertEqual(data["valuation"]["data_status"], "VALID")
        self.assertLess(data["valuation"]["scenarios"]["bear_case"], data["valuation"]["scenarios"]["base_case"])
        self.assertLess(data["valuation"]["scenarios"]["base_case"], data["valuation"]["scenarios"]["bull_case"])
        # Verify Dividend separation (Historical vs TTM vs Forward Estimated) & 1 Lot = 100 shares
        self.assertIn("dividend", data)
        self.assertIn("ttm_dividend_per_share", data["dividend"])
        self.assertIn("avg_3y_dividend_per_share", data["dividend"])
        self.assertIn("forward_estimated_dividend_per_share", data["dividend"])
        self.assertEqual(
            data["dividend"]["annual_dividend_per_lot"],
            round(data["dividend"]["annual_dividend_per_share"] * 100, 0),
        )
        # Verify Trading Plan, Risk Calculator Default, Market Intelligence, AI Analyst, Backtest, Data Quality
        self.assertIn("trading_plan", data)
        self.assertIn(data["trading_plan"]["signal_direction"], ("BUY", "HOLD", "SELL / REDUCE", "WAIT"))
        self.assertIn("risk_calculator_default", data)
        self.assertTrue(data["risk_calculator_default"]["valid"])
        self.assertIn("market_intelligence", data)
        self.assertIn("ai_analyst", data)
        self.assertIn("confidence_and_scoring_rubric", data["ai_analyst"])
        self.assertIn("backtest", data)
        self.assertEqual(data["backtest"]["status"], "VALID")
        self.assertIn("data_quality", data)

    def test_stock_technical_indicators_and_sanitization_unit(self):
        from app.services.stocks import (
            _compute_sma,
            _compute_ema,
            _compute_rsi,
            _compute_macd,
            _compute_bollinger_bands,
            _compute_true_atr,
            _compute_vwap,
            _sanitize_and_adjust_candles,
            _round_idx_tick,
            get_idx_tick_size,
        )
        # 1. Tick size & rounding rules on BEI/IDX
        self.assertEqual(get_idx_tick_size(150), 1.0)
        self.assertEqual(get_idx_tick_size(350), 2.0)
        self.assertEqual(get_idx_tick_size(1200), 5.0)
        self.assertEqual(get_idx_tick_size(3500), 10.0)
        self.assertEqual(get_idx_tick_size(8500), 25.0)
        self.assertEqual(_round_idx_tick(4123), 4120.0)

        # 2. Verifiable dataset for SMA, EMA, Wilder's RSI14, MACD, Bollinger, ATR14
        prices = [100.0 + i * 2.0 for i in range(40)]  # Strictly rising arithmetic series: 100, 102, ..., 178
        self.assertAlmostEqual(_compute_sma(prices, 20), sum(prices[-20:]) / 20.0, places=4)
        self.assertIsNone(_compute_sma(prices[:5], 20))  # Insufficient history -> None (never 0)
        self.assertGreater(_compute_ema(prices, 20), 130.0)
        self.assertEqual(_compute_rsi(prices, 14), 100.0)  # Purely rising series -> RSI 100

        macd_line, sig_line, hist_val = _compute_macd(prices)
        self.assertGreater(macd_line, 0.0)
        self.assertGreater(sig_line, 0.0)

        bb = _compute_bollinger_bands(prices, 20, 2.0)
        self.assertIsNotNone(bb["upper"])
        self.assertGreater(bb["upper"], bb["middle"])
        self.assertLess(bb["lower"], bb["middle"])

        # 3. Candle sanitization (rejects NaN, Infinity, <=0, duplicate timestamps, and flags forming candle)
        ts_list = [1700000000 + i * 86400 for i in range(20)] + [1700000000, 1705000000]
        opens = [1000.0 + i * 10 for i in range(20)] + [1000.0, float("nan")]
        highs = [1020.0 + i * 10 for i in range(20)] + [1010.0, 1010.0]
        lows = [990.0 + i * 10 for i in range(20)] + [990.0, 990.0]
        closes = [1010.0 + i * 10 for i in range(20)] + [1000.0, float("nan")]
        vols = [50000 for _ in range(20)] + [100, 100]
        clean, splits = _sanitize_and_adjust_candles(ts_list, opens, highs, lows, closes, vols, {}, interval="1d")
        self.assertEqual(len(clean), 20)

        # 4. Wilder's True Range & ATR14 + VWAP
        atr = _compute_true_atr([c["high"] for c in clean], [c["low"] for c in clean], [c["close"] for c in clean], 14)
        self.assertGreater(atr, 0)
        vwap_intra = _compute_vwap(clean, is_intraday=True)
        self.assertIsNotNone(vwap_intra)
        self.assertGreater(vwap_intra, 1000)
        self.assertIsNone(_compute_vwap(clean, is_intraday=False))

    def test_stock_fundamentals_and_valuation_edge_cases(self):
        from app.services.stock_fundamentals import build_fundamental_analysis, build_valuation_analysis
        from app.services.stocks import _round_idx_tick
        # 1. Loss-making issuer (GOTO) must NOT force positive PER as primary valuation metric
        goto_fund = build_fundamental_analysis("GOTO", 65.0, True, False)
        self.assertEqual(goto_fund["data_status"], "VALID")
        self.assertLess(goto_fund["metrics"]["net_income_idr_b"], 0)
        goto_val = build_valuation_analysis("GOTO", 65.0, 0.0, True, False, _round_idx_tick)
        self.assertEqual(goto_val["data_status"], "VALID")
        self.assertIsNone(goto_val["multiples"]["pe_ttm"])  # Negative EPS -> pe_ttm is None, not forced
        self.assertIn("EV/S", goto_val["methodology"])

        # 2. Unlinked ticker must return UNAVAILABLE and None (never fabricated 0s)
        unk_fund = build_fundamental_analysis("ZZZZ", 1000.0, True, False)
        self.assertEqual(unk_fund["data_status"], "UNAVAILABLE")
        self.assertIsNone(unk_fund["metrics"])
        unk_val = build_valuation_analysis("ZZZZ", 1000.0, 0.0, True, False, _round_idx_tick)
        self.assertEqual(unk_val["data_status"], "UNAVAILABLE")

    def test_stock_risk_calculator_and_portfolio_watchlist_crud(self):
        # 1. Valid Risk Calculator call (1 Lot = 100 shares, buy fee 0.15%, sell fee 0.25%)
        r_risk = self.client.post(
            "/api/v1/stocks/risk-calculator",
            json={
                "capital_idr": 100000000,
                "max_risk_pct": 1.0,
                "entry_price": 4000,
                "stop_loss": 3800,
                "target_price": 4500,
                "lots": 20,
                "buy_fee_pct": 0.15,
                "sell_fee_pct": 0.25,
                "slippage_pct": 0.10,
            },
            headers=self.headers,
        )
        self.assertEqual(r_risk.status_code, 200)
        rk = r_risk.json()
        self.assertTrue(rk["valid"])
        self.assertEqual(rk["inputs"]["total_shares"], 2000)  # 20 lots * 100 shares
        self.assertEqual(rk["execution"]["gross_buy_value_idr"], 8000000)
        self.assertGreater(rk["execution"]["net_profit_if_tp_idr"], 0)
        self.assertGreater(rk["execution"]["net_loss_if_sl_idr"], 400000)  # Includes fees + slippage on top of Rp 400k price risk
        self.assertIn("stress_scenarios", rk)

        # 2. Invalid Stop-Loss (>= Entry Price) must be rejected cleanly with HTTP 400
        r_bad = self.client.post(
            "/api/v1/stocks/risk-calculator",
            json={
                "capital_idr": 100000000,
                "max_risk_pct": 1.0,
                "entry_price": 4000,
                "stop_loss": 4100,
                "target_price": 4500,
            },
            headers=self.headers,
        )
        self.assertEqual(r_bad.status_code, 400)

        # 3. Stock Portfolio & Watchlist CRUD + Signal Journal
        r_port_add = self.client.post(
            "/api/v1/stocks/portfolio",
            json={"code": "BBRI", "lots": 10, "avg_buy_price": 4000, "notes": "Unit test position"},
            headers=self.headers,
        )
        self.assertEqual(r_port_add.status_code, 200)
        p_data = r_port_add.json()
        self.assertGreaterEqual(len(p_data["positions"]), 1)
        target_pos = next((p for p in p_data["positions"] if p.get("notes") == "Unit test position"), p_data["positions"][-1])
        pos_id = target_pos["id"]
        self.assertEqual(target_pos["shares"], 1000)

        r_watch_add = self.client.post(
            "/api/v1/stocks/watchlist",
            json={"code": "BBCA", "target_entry_price": 8800, "target_tp_price": 10200, "stop_loss_price": 8400, "notes": "Watchlist test"},
            headers=self.headers,
        )
        self.assertEqual(r_watch_add.status_code, 200)
        w_data = r_watch_add.json()
        self.assertGreaterEqual(len(w_data["watchlist"]), 1)
        watch_id = w_data["watchlist"][0]["id"]

        r_journal = self.client.post(
            "/api/v1/stocks/signal-journal",
            json={"code": "BBRI", "timeframe": "1d", "notes": "Signal journal test"},
            headers=self.headers,
        )
        self.assertEqual(r_journal.status_code, 200)
        j_list = r_journal.json()["signal_journal"]
        self.assertGreaterEqual(len(j_list), 1)
        self.assertEqual(j_list[0]["code"], "BBRI")
        j_id = j_list[0]["id"]

        # Clean up test portfolio position, watchlist item, and signal journal entry
        self.client.delete(f"/api/v1/stocks/portfolio/{pos_id}", headers=self.headers)
        self.client.delete(f"/api/v1/stocks/watchlist/{watch_id}", headers=self.headers)
        from app.db.session import SessionLocal
        from app.db.models import StockSignalJournal
        with SessionLocal() as db_s:
            db_s.query(StockSignalJournal).filter(StockSignalJournal.id == j_id).delete()
            db_s.commit()

    def test_gold_market_portfolio_and_sell_simulation(self):
        # 1. Fetch live gold dashboard
        r_gold = self.client.get("/api/v1/gold", headers=self.headers)
        self.assertEqual(r_gold.status_code, 200)
        g_data = r_gold.json()
        self.assertIn("market", g_data)
        self.assertIn("portfolio", g_data)
        self.assertIn("holdings", g_data)
        self.assertGreater(g_data["market"]["xau_usd"], 1000)
        self.assertGreater(g_data["market"]["antam"]["buy_price_idr"], 500000)
        self.assertGreater(g_data["market"]["antam"]["buyback_price_idr"], 400000)

        # 2. Add a manual gold holding (10 grams bought at Rp 1.200.000/g -> should be UNTUNG)
        r_add = self.client.post(
            "/api/v1/gold/holdings",
            json={
                "weight_grams": 10.0,
                "buy_price_per_gram_idr": 1200000,
                "brand": "Antam",
                "label": "Test Antam 10g",
                "purchased_at": "2024-05-01",
            },
            headers=self.headers,
        )
        self.assertEqual(r_add.status_code, 200)
        after_add = r_add.json()
        self.assertGreaterEqual(len(after_add["holdings"]), 1)
        added_item = after_add["holdings"][0]
        self.assertEqual(added_item["label"], "Test Antam 10g")
        self.assertEqual(added_item["status"], "UNTUNG")
        self.assertGreater(added_item["net_pnl_idr"], 0)

        # 3. Test Simulate Sell Now endpoint with spread & PPh 22 tax (> Rp 10 juta triggers 1.5% NPWP tax)
        r_sim = self.client.post(
            "/api/v1/gold/simulate-sell",
            json={
                "weight_grams": 10.0,
                "total_cost_idr": 12000000,
                "retail_buy_price_per_gram_idr": 1700000,
                "spread_pct": 9.0,
                "has_npwp": True,
                "include_stamp_duty": True,
            },
            headers=self.headers,
        )
        self.assertEqual(r_sim.status_code, 200)
        sim = r_sim.json()
        self.assertEqual(sim["gross_retail_value_idr"], 17000000)
        self.assertEqual(sim["spread_deduction_idr"], 1530000)
        self.assertEqual(sim["gross_buyback_value_idr"], 15470000)
        self.assertEqual(sim["tax_pct"], 1.5)
        self.assertGreater(sim["tax_deduction_idr"], 0)
        self.assertEqual(sim["stamp_duty_idr"], 10000)
        self.assertEqual(sim["status"], "UNTUNG")

        # 4. Delete the temporary holding so user's manual gold portfolio remains clean
        r_del = self.client.delete(f"/api/v1/gold/holdings/{added_item['id']}", headers=self.headers)
        self.assertEqual(r_del.status_code, 200)

    def test_crypto_analysis_and_risk_calculator(self):
        r_btc = self.client.get("/api/v1/crypto/analyze?q=SOL&timeframe=4h", headers=self.headers)
        self.assertEqual(r_btc.status_code, 200)
        c_data = r_btc.json()
        self.assertEqual(c_data["code"], "SOL")
        self.assertGreater(c_data["current_price_usd"], 0)
        self.assertGreater(c_data["current_price_idr"], 0)
        self.assertEqual(c_data["selected_timeframe"], "4h")
        self.assertIn("market_pulse", c_data)
        self.assertIn("btc", c_data["market_pulse"])
        self.assertIn("trading_plan", c_data)
        self.assertIn("tp_1_usd", c_data["trading_plan"])
        self.assertIn("stop_loss_usd", c_data["trading_plan"])
        self.assertIn("tokenomics", c_data)
        self.assertTrue(c_data["tokenomics"]["pays_staking_yield"])
        self.assertGreater(c_data["tokenomics"]["staking_apr_pct"], 0)

        r_risk = self.client.post(
            "/api/v1/crypto/risk-calculator",
            json={
                "capital_idr": 20000000,
                "entry_price_usd": 150.0,
                "stop_loss_usd": 140.0,
                "target_price_usd": 180.0,
                "max_risk_pct": 2.0,
                "investment_idr": 5000000,
            },
            headers=self.headers,
        )
        self.assertEqual(r_risk.status_code, 200)
        rk = r_risk.json()
        self.assertTrue(rk["valid"])
        self.assertGreater(rk["sizing"]["coin_quantity"], 0)
        self.assertGreater(rk["execution"]["net_profit_tp_idr"], 0)


if __name__ == "__main__":
    unittest.main()




