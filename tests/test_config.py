import importlib.util
import json
import os
import unittest
from pathlib import Path
from uuid import uuid4


CONFIG_PATH = Path(__file__).resolve().parents[1] / "app" / "config.py"


def load_config(env):
    original_env = os.environ.copy()
    try:
        for key in (
            "CURRENT_PROVIDER",
            "PROVIDERS",
            "KOINKYT_API_KEY",
            "KOINKYT_HOST",
            "KOINKYT_RISK_PROFILE_IDS",
            "AMLBOT_ACCESS_ID",
            "AMLBOT_ACCESS_KEY",
            "AMLBOT_ACCESS_POINT",
            "AMLBOT_FLOW",
        ):
            os.environ.pop(key, None)
        os.environ.update(env)
        spec = importlib.util.spec_from_file_location(
            f"aml_shkeeper_config_{uuid4().hex}", CONFIG_PATH
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.config
    finally:
        os.environ.clear()
        os.environ.update(original_env)


class ConfigTestCase(unittest.TestCase):
    def test_koinkyt_is_default_provider(self):
        config = load_config({"KOINKYT_API_KEY": "test-key"})

        self.assertEqual(config["CURRENT_PROVIDER"], "koinkyt")
        self.assertEqual(config["PROVIDERS"]["koinkyt"]["api_key"], "test-key")
        self.assertEqual(config["AVAILABLE_CRYPTO_LIST"], [
            "BTC",
            "ETH",
            "ETH-USDT",
            "ETH-USDC",
            "TRX",
            "USDT",
            "USDC",
        ])

    def test_old_amlbot_providers_env_does_not_break_koinkyt_default(self):
        config = load_config(
            {
                "KOINKYT_API_KEY": "test-key",
                "PROVIDERS": json.dumps(
                    {
                        "amlbot": {
                            "state": "enabled",
                            "access_id": "old-id",
                            "access_key": "old-key",
                            "access_point": "https://old.example",
                            "flow": "fast",
                            "cryptos": {},
                        }
                    }
                ),
            }
        )

        self.assertEqual(config["CURRENT_PROVIDER"], "koinkyt")
        self.assertIn("amlbot", config["PROVIDERS"])
        self.assertEqual(config["PROVIDERS"]["koinkyt"]["api_key"], "test-key")

    def test_explicit_amlbot_provider_keeps_legacy_default_config(self):
        config = load_config({"CURRENT_PROVIDER": "amlbot"})

        self.assertEqual(config["CURRENT_PROVIDER"], "amlbot")
        self.assertIn("BTC", config["AVAILABLE_CRYPTO_LIST"])
        self.assertIn("DOGE", config["AVAILABLE_CRYPTO_LIST"])
        self.assertEqual(config["PROVIDERS"]["amlbot"]["flow"], "fast")

    def test_koinkyt_risk_profile_ids_are_integer_list(self):
        config = load_config(
            {
                "KOINKYT_API_KEY": "test-key",
                "KOINKYT_RISK_PROFILE_IDS": "101, 202",
            }
        )

        self.assertEqual(
            config["PROVIDERS"]["koinkyt"]["risk_profile_ids"], [101, 202]
        )

    def test_koinkyt_risk_profile_ids_from_providers_are_integer_list(self):
        config = load_config(
            {
                "KOINKYT_API_KEY": "test-key",
                "PROVIDERS": json.dumps(
                    {
                        "koinkyt": {
                            "state": "enabled",
                            "api_key": "json-key",
                            "access_point": "https://koinkyt.example/openapi/v1",
                            "risk_profile_ids": "303,404",
                            "cryptos": {},
                        }
                    }
                ),
            }
        )

        self.assertEqual(
            config["PROVIDERS"]["koinkyt"]["risk_profile_ids"], [303, 404]
        )

    def test_unconfigured_unknown_provider_fails_clearly(self):
        with self.assertRaisesRegex(RuntimeError, "not configured"):
            load_config({"CURRENT_PROVIDER": "unknown"})


if __name__ == "__main__":
    unittest.main()
