import json
import os
import unittest

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

from app.aml_bot_api import (
    normalize_amlbot_response,
    normalize_koinkyt_response,
    symbol_to_aml_asset,
    symbol_to_koinkyt_params,
)


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

    def test_koinkyt_success_response_includes_score_signals_and_uid(self):
        result = normalize_koinkyt_response(
            {
                "id": "koinkyt-check-id",
                "blockchain": "trx",
                "token": "USDT",
                "risk_score": "0.04",
                "risk_score_grade": "low",
                "indirects": [{"type": "EXCHANGE_LICENSED"}],
                "link": "https://explorer.coinkyt.com/explorer/transaction?id=trx-txid",
            }
        )

        self.assertEqual(result["provider_status"], "success")
        self.assertEqual(result["uid"], "koinkyt-check-id")
        self.assertEqual(result["score"], "0.04")
        self.assertEqual(result["signals"]["risk_score_grade"], "low")
        self.assertEqual(
            result["report_url"],
            "https://explorer.coinkyt.com/explorer/transaction?id=trx-txid",
        )

    def test_koinkyt_retryable_http_error_is_checking(self):
        result = normalize_koinkyt_response(
            {
                "_http_status": 404,
                "error_code": "http_404",
                "error_message": "No data, please try again later",
            }
        )

        self.assertEqual(result["provider_status"], "checking")
        self.assertEqual(result["error_code"], "http_404")
        self.assertIsNone(result["score"])

    def test_koinkyt_transaction_not_found_is_retryable(self):
        result = normalize_koinkyt_response(
            {
                "_http_status": 404,
                "error_code": "http_404",
                "error_message": "Transaction not found",
            }
        )

        self.assertEqual(result["provider_status"], "checking")
        self.assertTrue(result["retryable"])
        self.assertIsNone(result["score"])

    def test_koinkyt_transport_error_is_checking(self):
        result = normalize_koinkyt_response(
            {
                "_transport_error": True,
                "error_code": "transport_error",
                "error_message": "timeout",
            }
        )

        self.assertEqual(result["provider_status"], "checking")
        self.assertTrue(result["retryable"])
        self.assertIsNone(result["score"])

    def test_koinkyt_missing_score_is_non_retryable_error(self):
        result = normalize_koinkyt_response(
            {
                "id": "koinkyt-check-id",
                "blockchain": "btc",
                "token": "",
                "link": "https://explorer.coinkyt.com/explorer/transaction?id=btc-txid",
            }
        )

        self.assertEqual(result["provider_status"], "error")
        self.assertEqual(result["error_code"], "missing_risk_score")
        self.assertFalse(result["retryable"])
        self.assertIsNone(result["score"])

    def test_koinkyt_symbol_mapping(self):
        self.assertEqual(symbol_to_koinkyt_params("BTC"), ("btc", ""))
        self.assertEqual(symbol_to_koinkyt_params("ETH-USDT"), ("eth", "USDT"))
        self.assertEqual(symbol_to_koinkyt_params("USDC"), ("trx", "USDC"))


if __name__ == "__main__":
    unittest.main()
