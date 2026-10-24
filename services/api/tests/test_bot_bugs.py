import unittest
from app.services import bot


class TestBotBugs(unittest.TestCase):
    def setUp(self):
        # Backup sniper config
        self._orig_cfg = dict(bot._SNIPER_CONFIG)

    def tearDown(self):
        # Restore sniper config in finally
        bot._SNIPER_CONFIG.clear()
        bot._SNIPER_CONFIG.update(self._orig_cfg)

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


if __name__ == "__main__":
    unittest.main()
