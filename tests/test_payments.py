"""
Pruebas unitarias completas para el sistema de pagos y suscripciones de KogniTerm.
"""

import unittest
from fastapi.testclient import TestClient
from kogniterm.server.app import create_app
from kogniterm.server.payments.service import payment_service, AVAILABLE_PLANS
from kogniterm.server.payments.models import PlanTier, SubscriptionStatus, PaymentProvider


class TestPaymentsSystem(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.client = TestClient(self.app)
        payment_service._subscriptions_db.clear()
        payment_service._usage_db.clear()

    def test_list_plans(self):
        """Verifica que el catálogo de planes retorne los planes predefinidos."""
        response = self.client.get("/api/payments/plans")
        self.assertEqual(response.status_code, 200)
        plans = response.json()
        self.assertTrue(len(plans) >= 4)
        plan_ids = [p["id"] for p in plans]
        self.assertIn("plan_free", plan_ids)
        self.assertIn("plan_pro_monthly", plan_ids)
        self.assertIn("plan_pro_yearly", plan_ids)
        self.assertIn("plan_enterprise", plan_ids)

    def test_get_plan_by_id(self):
        """Verifica la consulta de detalles de un plan específico."""
        response = self.client.get("/api/payments/plans/plan_pro_monthly")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "Pro Monthly")
        self.assertEqual(data["tier"], PlanTier.PRO.value)
        self.assertEqual(data["price"], 19.99)

        # Plan inexistente
        response_404 = self.client.get("/api/payments/plans/plan_non_existent")
        self.assertEqual(response_404.status_code, 404)

    def test_get_default_subscription(self):
        """Verifica que un usuario nuevo reciba la suscripción Free por defecto."""
        headers = {"X-User-ID": "user_default_test"}
        response = self.client.get("/api/payments/subscription", headers=headers)
        self.assertEqual(response.status_code, 200)
        sub = response.json()
        self.assertEqual(sub["user_id"], "user_default_test")
        self.assertEqual(sub["plan_id"], "plan_free")
        self.assertEqual(sub["status"], SubscriptionStatus.ACTIVE.value)

    def test_create_checkout_session(self):
        """Prueba la creación de una sesión de checkout de pago."""
        headers = {"X-User-ID": "user_checkout_test"}
        payload = {
            "plan_id": "plan_pro_monthly",
            "success_url": "http://localhost:3000/success",
            "cancel_url": "http://localhost:3000/cancel",
            "customer_email": "test@kogniterm.com"
        }
        response = self.client.post("/api/payments/checkout", json=payload, headers=headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("checkout_url", data)
        self.assertIn("session_id", data)
        self.assertIn(data["provider"], [PaymentProvider.STRIPE.value, PaymentProvider.MOCK.value])

        # Comprobar que la suscripción se actualizó al plan Pro
        sub_resp = self.client.get("/api/payments/subscription", headers=headers)
        self.assertEqual(sub_resp.json()["plan_id"], "plan_pro_monthly")

    def test_cancel_subscription(self):
        """Prueba la cancelación de la suscripción activa."""
        headers = {"X-User-ID": "user_cancel_test"}
        response = self.client.post("/api/payments/subscription/cancel?at_period_end=true", headers=headers)
        self.assertEqual(response.status_code, 200)
        sub = response.json()
        self.assertTrue(sub["cancel_at_period_end"])

    def test_get_payment_methods(self):
        """Prueba la obtención de los métodos de pago guardados."""
        headers = {"X-User-ID": "user_methods_test"}
        # Asignar primero plan Pro para tener tarjeta en el mock
        payment_service.create_checkout_session("user_methods_test", type("Obj", (), {
            "plan_id": "plan_pro_monthly",
            "success_url": "http://localhost/success",
            "cancel_url": "http://localhost/cancel",
            "customer_email": "test@test.com"
        }))
        response = self.client.get("/api/payments/payment-methods", headers=headers)
        self.assertEqual(response.status_code, 200)
        methods = response.json()
        self.assertIsInstance(methods, list)
        self.assertTrue(len(methods) > 0)

    def test_get_payment_history(self):
        """Prueba la consulta del historial de facturación."""
        headers = {"X-User-ID": "user_history_test"}
        payment_service.create_checkout_session("user_history_test", type("Obj", (), {
            "plan_id": "plan_pro_monthly",
            "success_url": "http://localhost/success",
            "cancel_url": "http://localhost/cancel",
            "customer_email": "test@test.com"
        }))
        response = self.client.get("/api/payments/history", headers=headers)
        self.assertEqual(response.status_code, 200)
        history = response.json()
        self.assertIsInstance(history, list)
        self.assertTrue(len(history) > 0)

    def test_get_quota_usage(self):
        """Prueba la consulta de métricas de cuota de uso y consumo."""
        headers = {"X-User-ID": "user_quota_test"}
        response = self.client.get("/api/payments/quota", headers=headers)
        self.assertEqual(response.status_code, 200)
        quota = response.json()
        self.assertIn("tier", quota)
        self.assertIn("tokens_used_this_month", quota)
        self.assertIn("percentage_used", quota)
        self.assertIn("sessions_limit", quota)


if __name__ == "__main__":
    unittest.main()
