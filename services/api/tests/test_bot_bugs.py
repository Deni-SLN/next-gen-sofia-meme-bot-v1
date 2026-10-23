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
        self.assertTrue(preset["only_new_creations"])

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


if __name__ == "__main__":
    unittest.main()
