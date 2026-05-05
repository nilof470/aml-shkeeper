import base64
import json
import os
import unittest
from decimal import Decimal

os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:////tmp/aml_shkeeper_tests.sqlite"
os.environ.setdefault(
    "PROVIDERS",
    json.dumps(
        {
            "koinkyt": {
                "state": "enabled",
                "api_key": "test-key",
                "access_point": "https://koinkyt.example/openapi/v1",
                "risk_profile_ids": "",
                "cryptos": {},
            }
        }
    ),
)

from app import create_app
from app.api import views
from app.models import Transactions, db


def auth_header():
    token = base64.b64encode(b"shkeeper:shkeeper").decode("ascii")
    return {"Authorization": f"Basic {token}"}


class ChecksApiTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.drop_all()
        db.create_all()
        self.client = self.app.test_client()
        self.original_delay = views.check_transaction.delay
        views.check_transaction.delay = lambda *args, **kwargs: None

    def tearDown(self):
        views.check_transaction.delay = self.original_delay
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def payload(self):
        return {
            "deposit_id": "shkeeper-tx-1",
            "idempotency_key": "BTC:txid-1:shkeeper-tx-1",
            "crypto": "BTC",
            "txid": "txid-1",
            "address": "bc1qaddress",
            "amount_crypto": "0.25",
            "asset": "BTC",
            "network": "BTC",
            "direction": "deposit",
        }

    def test_duplicate_check_returns_existing_state(self):
        first = self.client.post("/api/v1/checks", json=self.payload(), headers=auth_header())
        second = self.client.post("/api/v1/checks", json=self.payload(), headers=auth_header())

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json["deposit_id"], "shkeeper-tx-1")
        self.assertEqual(second.json["idempotency_key"], "BTC:txid-1:shkeeper-tx-1")
        self.assertEqual(Transactions.query.count(), 1)

    def test_get_check_returns_normalized_shape(self):
        self.client.post("/api/v1/checks", json=self.payload(), headers=auth_header())

        response = self.client.get("/api/v1/checks/shkeeper-tx-1", headers=auth_header())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["provider"], "koinkyt")
        self.assertEqual(response.json["provider_status"], "pending")
        self.assertEqual(response.json["signals"], {})
        self.assertIn("updated_at", response.json)

    def test_post_checks_rejects_unsupported_crypto(self):
        payload = self.payload()
        payload["crypto"] = "DOGE"

        response = self.client.post("/api/v1/checks", json=payload, headers=auth_header())

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["status"], "error")
        self.assertEqual(response.json["msg"], "unsupported crypto")
        self.assertEqual(Transactions.query.count(), 0)

    def test_duplicate_check_returns_existing_even_if_crypto_now_unsupported(self):
        payload = self.payload()
        payload["crypto"] = "DOGE"
        existing = Transactions(
            deposit_id=payload["deposit_id"],
            idempotency_key=payload["idempotency_key"],
            tx_id=payload["txid"],
            status="pending",
            ttype="aml",
            provider="amlbot",
            provider_status="pending",
            crypto="DOGE",
            amount=Decimal("0.25"),
            address=payload["address"],
            asset="DOGE",
            network="DOGE",
            threshold=Decimal("0.10"),
        )
        db.session.add(existing)
        db.session.commit()

        response = self.client.post("/api/v1/checks", json=payload, headers=auth_header())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["deposit_id"], payload["deposit_id"])
        self.assertEqual(response.json["crypto"], "DOGE")
        self.assertEqual(Transactions.query.count(), 1)

    def test_legacy_duplicate_returns_existing_state(self):
        payload = {"hash": "legacy-tx", "account": "bc1qaddress", "amount": "0.25"}

        self.client.post("/BTC/check_tx", json=payload, headers=auth_header())
        response = self.client.post("/BTC/check_tx", json=payload, headers=auth_header())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["status"], "success")
        self.assertEqual(response.json["txid"], "legacy-tx")


if __name__ == "__main__":
    unittest.main()
