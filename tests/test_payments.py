import unittest
import os
import json
import tempfile
from pathlib import Path

from kogniterm.server.payments import (
    PaymentService,
    SubscriptionTier,
    PaymentProviderType,
    PaymentStatus
)

class TestPaymentSystem(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_file = Path(self.temp_dir.name) / "test_payments.json"
        os.environ["KOGNITERM_PAYMENTS_FILE"] = str(self.db_file)
        self.service = PaymentService()

    def tearDown(self):
        self.temp_dir.cleanup()
        if "KOGNITERM_PAYMENTS_FILE" in os.environ:
            del os.environ["KOGNITERM_PAYMENTS_FILE"]

    def test_get_plans(self):
        plans = self.service.get_plans()
        self.assertGreaterEqual(len(plans), 3)
        tier_names = [p.tier for p in plans]
        self.assertIn(SubscriptionTier.FREE, tier_names)
        self.assertIn(SubscriptionTier.PRO, tier_names)
        self.assertIn(SubscriptionTier.ENTERPRISE, tier_names)

    def test_default_user_subscription(self):
        user_id = "test_user_123"
        sub = self.service.get_user_subscription(user_id)
        self.assertEqual(sub.user_id, user_id)
        self.assertEqual(sub.tier, SubscriptionTier.FREE)
        self.assertEqual(sub.credits_remaining, 100)

    def test_create_mock_checkout_and_complete(self):
        user_id = "test_user_456"
        res = self.service.create_checkout_session(user_id=user_id, plan_id="pro_monthly", provider=PaymentProviderType.MOCK)
        self.assertIn("transaction_id", res)
        self.assertEqual(res["provider"], "mock")
        
        tx_id = res["transaction_id"]
        sub = self.service.complete_transaction(tx_id=tx_id)
        
        self.assertEqual(sub.tier, SubscriptionTier.PRO)
        self.assertEqual(sub.plan_id, "pro_monthly")
        self.assertGreater(sub.credits_remaining, 100)

if __name__ == "__main__":
    unittest.main()
