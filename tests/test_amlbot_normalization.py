import json
import os
import unittest

os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:////tmp/aml_shkeeper_tests.sqlite"
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

from app.aml_bot_api import normalize_amlbot_response, symbol_to_aml_asset


class AmlBotNormalizationTestCase(unittest.TestCase):
    def test_success_response_includes_score_signals_and_uid(self):
        result = normalize_amlbot_response(
            {
                "result": True,
                "data": {
                    "status": "success",
                    "uid": "amlbot-check-id",
                    "riskscore": "0.04",
                    "signals": {"sanctions": 0.0, "mixer": 0.01},
                    "asset": "BTC",
                    "network": "BTC",
                    "report_url": "https://reports.example/1",
                },
            }
        )

        self.assertEqual(result["provider_status"], "success")
        self.assertEqual(result["uid"], "amlbot-check-id")
        self.assertEqual(result["score"], "0.04")
        self.assertEqual(result["signals"]["mixer"], 0.01)
        self.assertEqual(result["report_url"], "https://reports.example/1")

    def test_pending_response_is_not_success(self):
        result = normalize_amlbot_response(
            {"result": True, "data": {"status": "pending", "uid": "pending-id"}}
        )

        self.assertEqual(result["provider_status"], "pending")
        self.assertIsNone(result["score"])

    def test_provider_error_response_is_normalized(self):
        result = normalize_amlbot_response(
            {"result": False, "description": "provider unavailable", "code": "upstream_error"}
        )

        self.assertEqual(result["provider_status"], "error")
        self.assertEqual(result["error_code"], "upstream_error")
        self.assertEqual(result["error_message"], "provider unavailable")
        self.assertIsNone(result["score"])

    def test_btc_ltc_doge_are_supported_symbols(self):
        self.assertEqual(symbol_to_aml_asset("BTC"), "BTC")
        self.assertEqual(symbol_to_aml_asset("LTC"), "LTC")
        self.assertEqual(symbol_to_aml_asset("DOGE"), "DOGE")


if __name__ == "__main__":
    unittest.main()
