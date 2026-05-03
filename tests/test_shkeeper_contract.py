import base64
import json
import os
import unittest

os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:////tmp/aml_shkeeper_contract_tests.sqlite"
os.environ.setdefault(
    "PROVIDERS",
    json.dumps(
        {
            "amlbot": {
                "state": "enabled",
                "access_id": "test-id",
                "access_key": "test-key",
                "access_point": "https://amlbot.example",
                "flow": "fast",
                "cryptos": {},
            }
        }
    ),
)

from app import create_app
from app.api import views
from app.models import db


def auth_header():
    token = base64.b64encode(b"shkeeper:shkeeper").decode("ascii")
    return {"Authorization": f"Basic {token}"}


class ShkeeperContractTestCase(unittest.TestCase):
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
            "deposit_id": "shkeeper-tx-101",
            "idempotency_key": "BTC:txid-101:shkeeper-tx-101",
            "crypto": "BTC",
            "txid": "txid-101",
            "address": "bc1qcontract",
            "amount_crypto": "0.25",
            "asset": "BTC",
            "network": "BTC",
            "direction": "deposit",
            "threshold": "0.10",
        }

    def test_post_checks_accepts_shkeeper_contract(self):
        response = self.client.post(
            "/api/v1/checks", json=self.payload(), headers=auth_header()
        )

        self.assertEqual(response.status_code, 201)
        for field in (
            "deposit_id",
            "idempotency_key",
            "provider",
            "provider_status",
            "score",
            "threshold",
            "uid",
            "asset",
            "network",
            "signals",
            "attempts",
            "next_retry_at",
            "timeout_at",
            "updated_at",
        ):
            self.assertIn(field, response.json)

    def test_duplicate_post_checks_returns_existing_state(self):
        first = self.client.post(
            "/api/v1/checks", json=self.payload(), headers=auth_header()
        )
        second = self.client.post(
            "/api/v1/checks", json=self.payload(), headers=auth_header()
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json["deposit_id"], self.payload()["deposit_id"])
        self.assertEqual(
            second.json["idempotency_key"], self.payload()["idempotency_key"]
        )


if __name__ == "__main__":
    unittest.main()
