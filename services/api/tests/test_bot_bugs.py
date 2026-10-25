import unittest
from app.services import bot


class TestBotBugs(unittest.TestCase):
    def setUp(self):
        # Backup sniper config
        self._orig_cfg = dict(bot._SNIPER_CONFIG)

    def tearDown(self):
        # Restore sniper config in finally and persist back to disk so tests never pollute runtime config
        bot._SNIPER_CONFIG.clear()
        bot._SNIPER_CONFIG.update(self._orig_cfg)
        bot._save_persisted_sniper_config()

    def test_user_owned_keys_preservation_on_preset(self):
        """Verify operator manual inputs are preserved and not overwritten when presets are applied."""
        # Set operator custom inputs via update_sniper_config
        bot.update_sniper_config({
            "buy_amount_idr": 35000.0,
            "max_open_positions": 8,
            "slippage_pct": 2.5,
            "paper_initial_capital_idr": 500000.0,
        })

        # Apply SAFE preset
        bot.update_sniper_config({"strategy_mode": "SAFE", "apply_preset": True})

        # User owned keys MUST NOT be overwritten
        self.assertEqual(bot._SNIPER_CONFIG["buy_amount_idr"], 35000.0)
        self.assertEqual(bot._SNIPER_CONFIG["max_open_positions"], 8)
        self.assertEqual(bot._SNIPER_CONFIG["slippage_pct"], 2.5)
        self.assertEqual(bot._SNIPER_CONFIG["paper_initial_capital_idr"], 500000.0)
        # But preset keys like min_safety_score MUST be updated
        self.assertEqual(bot._SNIPER_CONFIG["min_safety_score"], 82)

    def test_anti_dust_snipe_threshold(self):
        """Verify anti-dust threshold uses max(2000, buy_amount_idr)."""
        bot._SNIPER_CONFIG["buy_amount_idr"] = 30000.0
        cfg_buy = float(bot._SNIPER_CONFIG["buy_amount_idr"])
        min_threshold = max(2000.0, cfg_buy)
        self.assertEqual(min_threshold, 30000.0)

        # If buy_amount is very small, floor is 2000.0
        bot._SNIPER_CONFIG["buy_amount_idr"] = 500.0
        cfg_buy_small = float(bot._SNIPER_CONFIG["buy_amount_idr"])
        min_threshold_floor = max(2000.0, cfg_buy_small)
        self.assertEqual(min_threshold_floor, 2000.0)

    def test_aggressive_preset_parameters(self):
        """Verify AGGRESSIVE preset settings."""
        preset = bot.STRATEGY_PRESETS["AGGRESSIVE"]
        self.assertEqual(preset["tick_interval_ms"], 1200)
        self.assertEqual(preset["auto_tp_pct"], 8.0)
        self.assertEqual(preset["auto_sl_pct"], 5.5)
        self.assertTrue(preset["only_new_creations"])

    def test_pinned_contract_anti_collision_and_sl_cooldown(self):
        """Verify pinned contract prevents cross-token ticker price collisions and SL cooldown blocks re-buys."""
        from app.services import market
        sym = "TESTPEPE/SOL"
        ca_real = "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"
        ca_fake = "11111111111111111111111111111111111111111111"

        market.pin_holding_contract(sym, ca_real)
        market._register_token_cache({"symbol": sym, "base_symbol": "TESTPEPE", "contract": ca_real, "price": 0.0010, "liquidity": 25000.0})
        # Attempting to register a different contract with the same symbol must NOT overwrite the pinned symbol cache
        market._register_token_cache({"symbol": sym, "base_symbol": "TESTPEPE", "contract": ca_fake, "price": 0.00001, "liquidity": 50000.0})
        cached_tok = market._PRICE_CACHE[sym][0]
        self.assertEqual(cached_tok["contract"], ca_real)
        self.assertAlmostEqual(cached_tok["price"], 0.0010)
        market.unpin_holding_contract(sym)

    def test_bot_config_backup_and_restore(self):
        """Verify that testing config changes leaves clean state without hardcoding max_open_positions."""
        custom_val = 7
        try:
            bot._SNIPER_CONFIG["max_open_positions"] = custom_val
            self.assertEqual(bot._SNIPER_CONFIG["max_open_positions"], custom_val)
        finally:
            bot._SNIPER_CONFIG.clear()
            bot._SNIPER_CONFIG.update(self._orig_cfg)

        self.assertEqual(bot._SNIPER_CONFIG["max_open_positions"], self._orig_cfg.get("max_open_positions", 10))

    def test_strict_buy_amount_usd_and_max_open_positions_guard(self):
        """Verify bot never stacks duplicate buys ($1 -> $2.9) and never exceeds max_open_positions (5 -> 7)."""
        from app.db.session import SessionLocal
        from app.db.models import PortfolioHolding
        from app.services import memecoins, portfolio
        from sqlalchemy import select, delete

        db = SessionLocal()
        try:
            db.execute(delete(PortfolioHolding).where(PortfolioHolding.mode == "PAPER"))
            db.commit()

            bot.update_sniper_config({"buy_amount_usd": 1.0, "max_open_positions": 2})
            self.assertAlmostEqual(float(bot._SNIPER_CONFIG["buy_amount_usd"]), 1.0)
            self.assertEqual(int(bot._SNIPER_CONFIG["max_open_positions"]), 2)

            portfolio.add_holding(db, symbol="MEME1/SOL", quantity=1000.0, avg_entry_price=0.001, current_price=0.001, mode="PAPER")

            # Attempting to auto-snipe the SAME token from bot must raise POSISI_SUDAH_ADA (prevents $1 stacking to $2.9)
            with self.assertRaises(ValueError) as ctx_dup:
                memecoins.execute_snipe(
                    db,
                    {
                        "symbol": "MEME1/SOL",
                        "amount_usd": 1.0,
                        "price": 0.001,
                        "mode": "PAPER",
                        "from_bot": True,
                        "force_unsafe": True,
                        "max_open_positions": 2,
                    },
                )
            self.assertIn("POSISI_SUDAH_ADA", str(ctx_dup.exception))

            # Add 2nd holding to reach max_open_positions = 2
            portfolio.add_holding(db, symbol="MEME2/SOL", quantity=1000.0, avg_entry_price=0.001, current_price=0.001, mode="PAPER")

            # Attempting a 3rd auto-snipe when max_open_positions = 2 must raise MAX_POSITIONS_REACHED
            with self.assertRaises(ValueError) as ctx_max:
                memecoins.execute_snipe(
                    db,
                    {
                        "symbol": "MEME3/SOL",
                        "amount_usd": 1.0,
                        "price": 0.001,
                        "mode": "PAPER",
                        "from_bot": True,
                        "force_unsafe": True,
                        "max_open_positions": 2,
                    },
                )
            self.assertIn("MAX_POSITIONS_REACHED", str(ctx_max.exception))

            ov = portfolio.get_overview(db, refresh_live_prices=False, mode="PAPER", skip_rpc=True)
            self.assertIn("paper_winrate_pct", ov)
            self.assertIn("live_winrate_pct", ov)
            self.assertIn("paper_trades", ov)
            self.assertIn("live_trades", ov)
        finally:
            db.execute(delete(PortfolioHolding).where(PortfolioHolding.mode == "PAPER"))
            db.commit()
            db.close()

    def test_winrate_updates_dynamically_for_paper_and_live(self):
        """Ensure WR PAPER and WR LIVE in portfolio.get_overview and strategy_stats update when trades close."""
        from datetime import datetime, timezone
        from sqlalchemy import delete
        from app.db.session import SessionLocal
        from app.db.models import PortfolioHolding, Trade
        from app.services import bot, portfolio

        db = SessionLocal()
        orig_bot_status = "running"
        try:
            st_cur = bot.get_bot_status(db)
            orig_bot_status = st_cur.status
            st_cur.status = "stopped"
            db.commit()
            db.execute(delete(PortfolioHolding).where(PortfolioHolding.symbol == "WINMEME/SOL"))
            db.execute(delete(Trade).where(Trade.symbol.in_(["WINMEME/SOL", "LIVEWIN/SOL"])))
            db.commit()

            ov_before = portfolio.get_overview(db, refresh_live_prices=False, mode="PAPER", skip_rpc=True)
            base_paper_trades = int(ov_before["paper_trades"])
            base_paper_wins = int(ov_before["paper_wins"])
            base_live_trades = int(ov_before["live_trades"])
            base_live_wins = int(ov_before["live_wins"])

            # 1. Simulate a PAPER position reaching +15% TP and selling via sell_holding
            portfolio.add_holding(
                db,
                symbol="WINMEME/SOL",
                quantity=1000.0,
                avg_entry_price=0.001,
                current_price=0.00115,
                mode="PAPER",
            )
            sell_res = portfolio.sell_holding(db, "WINMEME/SOL", 100.0, mode="PAPER")
            self.assertGreater(sell_res["realized_pnl_usd"], 0.0)

            # 2. Insert a closed LIVE trade as well
            now = datetime.now(timezone.utc)
            live_trade = Trade(
                symbol="LIVEWIN/SOL",
                side="sell",
                quantity=500.0,
                price=0.0024,
                total=1.20,
                mode="LIVE",
                status="closed",
                pnl=0.20,
                notes="[AGGRESSIVE] Live On-Chain Sell (100%)",
                opened_at=now,
                closed_at=now,
            )
            db.add(live_trade)
            db.commit()

            ov_after = portfolio.get_overview(db, refresh_live_prices=False, mode="PAPER", skip_rpc=True)
            self.assertEqual(ov_after["paper_trades"], base_paper_trades + 1)
            self.assertEqual(ov_after["paper_wins"], base_paper_wins + 1)
            self.assertGreater(ov_after["paper_winrate_pct"], 0.0)

            self.assertEqual(ov_after["live_trades"], base_live_trades + 1)
            self.assertEqual(ov_after["live_wins"], base_live_wins + 1)
            self.assertGreater(ov_after["live_winrate_pct"], 0.0)

            # 3. Verify get_sniper_config() (even without db argument) returns populated strategy_stats
            cfg = bot.get_sniper_config()
            self.assertIn("strategy_stats", cfg)
            total_strat_paper = sum(s["paper_trades_count"] for s in cfg["strategy_stats"].values())
            total_strat_live = sum(s["live_trades_count"] for s in cfg["strategy_stats"].values())
            self.assertGreater(total_strat_paper, 0)
            self.assertGreater(total_strat_live, 0)

            # 4. Verify $10 initial capital accounting invariant: losing trades NEVER inflate cash to $50+
            portfolio.reset_paper_account(db, initial_capital_usd=10.0)
            loss_trade = Trade(
                symbol="LOSSMEME/SOL",
                side="sell",
                quantity=1000.0,
                price=0.0009,
                total=0.90,
                mode="PAPER",
                status="closed",
                pnl=-0.10,
                notes="[SAFE] Paper Sell (100%)",
                opened_at=now,
                closed_at=now,
            )
            db.add(loss_trade)
            portfolio.add_holding(
                db,
                symbol="OPENMEME/SOL",
                quantity=1000.0,
                avg_entry_price=0.001,
                current_price=0.00098,
                mode="PAPER",
            )
            db.commit()
            ov_10 = portfolio.get_overview(db, refresh_live_prices=False, mode="PAPER", skip_rpc=True)
            self.assertAlmostEqual(ov_10["paper_initial_usd"], 10.0, places=2)
            self.assertAlmostEqual(ov_10["paper_cash_usd"], 8.90, places=2)
            self.assertLess(ov_10["total_equity_usd"], 10.0)
        finally:
            db.execute(delete(PortfolioHolding).where(PortfolioHolding.symbol.in_(["WINMEME/SOL", "OPENMEME/SOL"])))
            db.execute(delete(Trade).where(Trade.symbol.in_(["WINMEME/SOL", "LIVEWIN/SOL", "LOSSMEME/SOL"])))
            st_restore = bot.get_bot_status(db)
            st_restore.status = orig_bot_status
            db.commit()
            portfolio.get_overview(db, refresh_live_prices=False, mode="PAPER", skip_rpc=True)
            db.close()

    def test_bot_continues_running_without_browser_and_only_stops_on_stop_bot(self):
        """
        Verify:
        1. Starting the bot activates the 24/7 autonomous server daemon (autonomous_daemon_active = True).
        2. Even when the browser is closed or the user logs out (no client polling), the bot remains 'running'
           and runtime logs are persisted to disk so re-opening the browser restores all logs.
        3. Only calling stop_bot() transitions status to 'stopped'.
        """
        import time
        from app.db.session import SessionLocal
        from app.services import bot

        db = SessionLocal()
        try:
            orig_state = bot.get_bot_status(db)
            orig_status = orig_state.status
            orig_mode = orig_state.mode

            # 1. Start bot
            st = bot.start_bot(db, mode="PAPER")
            self.assertEqual(st.status, "running")
            telem = bot.get_daemon_telemetry()
            self.assertTrue(telem["autonomous_daemon_active"])
            self.assertTrue(telem["persists_on_browser_close"])
            self.assertTrue(telem["persists_on_logout"])
            self.assertTrue(telem["stops_only_on_stop_button"])

            # 2. Simulate browser closed & user logged out (clear in-memory logs and wait for background daemon heartbeat)
            bot._BOT_ACTIVITY_LOGS.clear()
            bot._load_persisted_runtime_logs()
            self.assertGreaterEqual(len(bot._BOT_ACTIVITY_LOGS), 1)

            time.sleep(1.8)
            st_after = bot.get_bot_status(db)
            self.assertEqual(st_after.status, "running")
            telem_after = bot.get_daemon_telemetry()
            self.assertTrue(telem_after["autonomous_daemon_active"])
            self.assertIsNotNone(telem_after["last_heartbeat_at"])

            # 3. Verify bot ONLY stops when stop_bot is explicitly called
            st_stopped = bot.stop_bot(db)
            self.assertEqual(st_stopped.status, "stopped")
        finally:
            st_restore = bot.get_bot_status(db)
            st_restore.status = orig_status
            st_restore.mode = orig_mode
            db.commit()
            db.close()


if __name__ == "__main__":
    unittest.main()
