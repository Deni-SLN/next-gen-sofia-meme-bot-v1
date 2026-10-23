import unittest
from unittest.mock import patch
from app.services import live_engine, journal
from app.db.session import SessionLocal


class TestSolanaSigning(unittest.TestCase):
    def test_generate_tx_hash_fail_closed_without_keypair(self):
        """Verify generate_tx_hash returns empty string when Solana keypair is absent."""
        with patch("app.services.live_engine._load_solana_keypair", return_value=None):
            sig = live_engine.generate_tx_hash("Solana")
            self.assertEqual(sig, "")

        # For EVM/Base, it is also not yet configured -> ""
        evm_sig = live_engine.generate_tx_hash("Base")
        self.assertEqual(evm_sig, "")

    def test_valid_solana_signature_validation(self):
        """Verify _valid_solana_signature properly validates base58 86-88 chars."""
        # Valid 88-char base58 signature
        valid_sig = "5VERv8NMvzbJMEkV8xnrLkEaWRtSz9CosKDYj7WNpyZwGP6UmR582ChkLJ33wgThKBRByKaz387bL1wWUUWMyjYZ"
        self.assertTrue(journal._valid_solana_signature(valid_sig))

        # Test signatures allowed in testing
        self.assertTrue(journal._valid_solana_signature("test_tx_hash_12345"))

        # Too short (invalid)
        self.assertFalse(journal._valid_solana_signature("short_hash"))

        # Empty
        self.assertFalse(journal._valid_solana_signature(""))
        self.assertFalse(journal._valid_solana_signature(None))

        # Invalid characters (0, O, I, l are NOT in Base58)
        invalid_chars = "0" * 88
        self.assertFalse(journal._valid_solana_signature(invalid_chars))

    def test_record_live_trade_rejects_empty_or_invalid_signature(self):
        """Verify record_live_trade strictly rejects LIVE Solana trades with invalid signature."""
        with SessionLocal() as db:
            # Empty signature -> rejects
            with self.assertRaises(ValueError) as ctx:
                journal.record_live_trade(
                    db,
                    {
                        "symbol": "TESTFAIL/SOL",
                        "side": "buy",
                        "quantity": 10.0,
                        "price": 1.0,
                        "chain": "Solana",
                        "tx_hash": "",
                    },
                )
            self.assertIn("TX_HASH_TIDAK_VALID", str(ctx.exception))

            # Non-base58 signature -> rejects
            with self.assertRaises(ValueError) as ctx2:
                journal.record_live_trade(
                    db,
                    {
                        "symbol": "TESTFAIL/SOL",
                        "side": "buy",
                        "quantity": 10.0,
                        "price": 1.0,
                        "chain": "Solana",
                        "tx_hash": "invalid_fake_hash_not_88_chars",
                    },
                )
            self.assertIn("TX_HASH_TIDAK_VALID", str(ctx2.exception))


if __name__ == "__main__":
    unittest.main()
