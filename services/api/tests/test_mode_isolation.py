import unittest
from datetime import datetime, timezone
from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.models import PortfolioHolding, Trade
from app.services import portfolio, bot


class TestModeIsolation(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        # Clean up any test holdings
        self.db.query(PortfolioHolding).filter(
            PortfolioHolding.symbol.in_(["TEST_ISO_1", "TEST_ISO_2"])
        ).delete()
        self.db.commit()

    def tearDown(self):
        self.db.query(PortfolioHolding).filter(
            PortfolioHolding.symbol.in_(["TEST_ISO_1", "TEST_ISO_2"])
        ).delete()
        self.db.commit()
        self.db.close()

    def test_holding_mode_composite_unique(self):
        """Verify PortfolioHolding supports both PAPER and LIVE modes for the same symbol."""
        h_paper = PortfolioHolding(
            symbol="TEST_ISO_1",
            quantity=100.0,
            avg_entry_price=1.0,
            current_price=1.2,
            mode="PAPER",
        )
        h_live = PortfolioHolding(
            symbol="TEST_ISO_1",
            quantity=50.0,
            avg_entry_price=1.0,
            current_price=1.2,
            mode="LIVE",
        )
        self.db.add(h_paper)
        self.db.add(h_live)
        self.db.commit()

        # Both records should exist independently
        holdings = list(
            self.db.execute(
                select(PortfolioHolding).where(PortfolioHolding.symbol == "TEST_ISO_1")
            ).scalars().all()
        )
        self.assertEqual(len(holdings), 2)
        modes = {h.mode for h in holdings}
        self.assertEqual(modes, {"PAPER", "LIVE"})

    def test_reset_paper_account_preserves_live(self):
        """Verify reset_paper_account only wipes PAPER holdings, never LIVE holdings."""
        h_paper = PortfolioHolding(
            symbol="TEST_ISO_1",
            quantity=100.0,
            avg_entry_price=1.0,
            current_price=1.0,
            mode="PAPER",
        )
        h_live = PortfolioHolding(
            symbol="TEST_ISO_2",
            quantity=50.0,
            avg_entry_price=2.0,
            current_price=2.0,
            mode="LIVE",
        )
        self.db.add(h_paper)
        self.db.add(h_live)
        self.db.commit()

        # Reset paper account
        portfolio.reset_paper_account(self.db)

        # Paper holding must be deleted
        paper_check = self.db.execute(
            select(PortfolioHolding).where(
                PortfolioHolding.symbol == "TEST_ISO_1",
                PortfolioHolding.mode == "PAPER",
            )
        ).scalar_one_or_none()
        self.assertIsNone(paper_check)

        # LIVE holding must be completely preserved
        live_check = self.db.execute(
            select(PortfolioHolding).where(
                PortfolioHolding.symbol == "TEST_ISO_2",
                PortfolioHolding.mode == "LIVE",
            )
        ).scalar_one_or_none()
        self.assertIsNotNone(live_check)
        self.assertEqual(live_check.quantity, 50.0)

    def test_sell_all_holdings_filters_by_mode(self):
        """Verify sell_all_holdings respects the mode parameter."""
        h_paper = PortfolioHolding(
            symbol="TEST_ISO_1",
            quantity=10.0,
            avg_entry_price=0.5,
            current_price=0.5,
            mode="PAPER",
        )
        h_live = PortfolioHolding(
            symbol="TEST_ISO_2",
            quantity=20.0,
            avg_entry_price=0.5,
            current_price=0.5,
            mode="LIVE",
        )
        self.db.add(h_paper)
        self.db.add(h_live)
        self.db.commit()

        res = portfolio.sell_all_holdings(self.db, mode="PAPER")
        self.assertEqual(res["status"], "liquidated_all")

        # Live holding should still be in the database
        live_h = self.db.execute(
            select(PortfolioHolding).where(PortfolioHolding.symbol == "TEST_ISO_2")
        ).scalar_one_or_none()
        self.assertIsNotNone(live_h)

    def test_winrate_calculation_isolated_by_mode(self):
        """Verify winrate stats are calculated separately for PAPER and LIVE modes."""
        now = datetime.now(timezone.utc)
        t_paper = Trade(
            symbol="TEST_ISO_1",
            side="sell",
            quantity=10,
            price=1.0,
            pnl=5.0,
            mode="PAPER",
            status="closed",
            opened_at=now,
            closed_at=now,
        )
        t_live = Trade(
            symbol="TEST_ISO_2",
            side="sell",
            quantity=10,
            price=1.0,
            pnl=-3.0,
            mode="LIVE",
            status="closed",
            opened_at=now,
            closed_at=now,
        )
        self.db.add(t_paper)
        self.db.add(t_live)
        self.db.commit()

        stats_paper = bot.get_strategy_winrate_stats(self.db, mode="PAPER")
        stats_live = bot.get_strategy_winrate_stats(self.db, mode="LIVE")

        self.db.delete(t_paper)
        self.db.delete(t_live)
        self.db.commit()

        self.assertIn("SAFE", stats_paper)
        self.assertIn("SAFE", stats_live)
        self.assertIn("winrate_pct", stats_paper["SAFE"])
        self.assertIn("winrate_pct", stats_live["SAFE"])


if __name__ == "__main__":
    unittest.main()
