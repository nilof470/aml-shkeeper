import os
import json


KOINKYT_PROVIDER = 'koinkyt'
AMLBOT_PROVIDER = 'amlbot'
KOINKYT_AVAILABLE_CRYPTO_LIST = [
    'BTC',
    'ETH',
    'ETH-USDT',
    'ETH-USDC',
    'TRX',
    'USDT',
    'USDC',
]
AMLBOT_AVAILABLE_CRYPTO_LIST = [
    'BTC',
    'LTC',
    'DOGE',
    'ETH',
    'ETH-USDT',
    'ETH-USDC',
    'ETH-PYUSD',
    'TRX',
    'USDT',
    'USDC',
    'SOL',
    'SOLANA-USDT',
    'SOLANA-USDC',
    'SOLANA-PYUSD',
]


def koinkyt_risk_profile_ids():
    return parse_koinkyt_risk_profile_ids(os.environ.get("KOINKYT_RISK_PROFILE_IDS", ""))


def parse_koinkyt_risk_profile_ids(value):
    if not value:
        return []
    if isinstance(value, list):
        return [int(item) for item in value]
    return [
        int(item.strip())
        for item in str(value).replace(";", ",").split(",")
        if item.strip()
    ]


def koinkyt_provider_config():
    return {
        "state": "enabled",
        "api_key": os.environ.get("KOINKYT_API_KEY", ""),
        "access_point": os.environ.get(
            "KOINKYT_HOST", "https://explorer.coinkyt.com/openapi/v1"
        ),
        "risk_profile_ids": koinkyt_risk_profile_ids(),
        "cryptos": {},
    }


def amlbot_provider_config():
    return {
        "state": "enabled",
        "access_id": os.environ.get("AMLBOT_ACCESS_ID", ""),
        "access_key": os.environ.get("AMLBOT_ACCESS_KEY", ""),
        "access_point": os.environ.get(
            "AMLBOT_ACCESS_POINT", "https://extrnlapiendpoint.silencatech.com"
        ),
        "flow": os.environ.get("AMLBOT_FLOW", "fast"),
        "cryptos": {},
    }


def _merge_provider_config(providers_config, provider, default_config):
    provider_config = default_config
    configured_provider = providers_config.get(provider) or {}
    for key, value in configured_provider.items():
        if value not in (None, ""):
            provider_config[key] = value
    providers_config[provider] = provider_config


def get_providers_config(current_provider):
    providers = os.environ.get('PROVIDERS')
    if not providers:
        providers_config = {}
    else:
        providers_config = json.loads(providers)

    if current_provider == KOINKYT_PROVIDER:
        _merge_provider_config(
            providers_config, KOINKYT_PROVIDER, koinkyt_provider_config()
        )
        providers_config[KOINKYT_PROVIDER]["risk_profile_ids"] = (
            parse_koinkyt_risk_profile_ids(
                providers_config[KOINKYT_PROVIDER].get("risk_profile_ids")
            )
        )
    elif current_provider == AMLBOT_PROVIDER:
        _merge_provider_config(
            providers_config, AMLBOT_PROVIDER, amlbot_provider_config()
        )

    if current_provider not in providers_config:
        raise RuntimeError(f"AML provider '{current_provider}' is not configured")

    return providers_config

    # EXAMPLE
    # '{
	# 	"amlbot":{
	# 		"state": "enabled",  
	# 		"access_id": "XXXXX-YYYYY-WWWWWWW",
	# 		"access_key": "xxxxxxxx-eeeeeee-wwwwwwwwww-qqqqqqqqq-ddddddd",
	# 		"access_point": "https://extrnlapiendpoint.silencatech.com",
	# 		"flow": "fast",  
	# 		"cryptos": {
	# 			"ETH": {"min_check_amount": "0.001"},
	# 			"ETH-USDC": {"min_check_amount": "0.01"}, 
	# 			"ETH-USDT": {"min_check_amount": "0.01"}, 
	# 			"TRX": {"min_check_amount": "0.001"}, 
	# 			"BTC": {"min_check_amount": "0.00001"} 
	# 		} 
	# 	} 
	# }'


CURRENT_PROVIDER = os.environ.get('CURRENT_PROVIDER', KOINKYT_PROVIDER)
PROVIDERS_CONFIG = get_providers_config(CURRENT_PROVIDER)


def get_available_crypto_list(current_provider, providers_config):
    if current_provider == KOINKYT_PROVIDER:
        return KOINKYT_AVAILABLE_CRYPTO_LIST
    if current_provider == AMLBOT_PROVIDER:
        configured_cryptos = providers_config[AMLBOT_PROVIDER].get('cryptos') or {}
        return list(configured_cryptos.keys()) or AMLBOT_AVAILABLE_CRYPTO_LIST
    configured_cryptos = providers_config[current_provider].get('cryptos') or {}
    return list(configured_cryptos.keys())

config = {
    'DEBUG': os.environ.get('DEBUG', False),
    'LOGGING_LEVEL': os.environ.get('LOGGING_LEVEL', 'INFO'),
    'REDIS_HOST': os.environ.get('REDIS_HOST', 'localhost'),
    'SQLALCHEMY_DATABASE_URI' : os.environ.get('SQLALCHEMY_DATABASE_URI', "mariadb+pymysql://root:shkeeper@mariadb/aml-shkeeper?charset=utf8mb4"),
    'API_USERNAME': os.environ.get('AML_USERNAME', 'shkeeper'),
    'API_PASSWORD': os.environ.get('AML_PASSWORD', 'shkeeper'),
    'SHKEEPER_KEY': os.environ.get('SHKEEPER_BACKEND_KEY', 'shkeeper'),
    'SHKEEPER_HOST': os.environ.get('SHKEEPER_HOST', 'shkeeper:5000'),
    'RECHECK_TXS_EVERY_SECONDS': int(os.environ.get('RECHECK_TXS_EVERY_SECONDS', '120')),
    'AVAILABLE_CRYPTO_LIST': get_available_crypto_list(
        CURRENT_PROVIDER, PROVIDERS_CONFIG
    ),
    'CURRENT_PROVIDER': CURRENT_PROVIDER,
    'RETRY_UNTIL_FAILED': int(os.environ.get('RETRY_UNTIL_FAILED', '3')),
    'CHECK_TIMEOUT_SECONDS': int(os.environ.get('CHECK_TIMEOUT_SECONDS', '1800')),
    'CHECK_RETRY_SECONDS': int(os.environ.get('CHECK_RETRY_SECONDS', '120')),
    'HTTP_TIMEOUT_SECONDS': float(
        os.environ.get(
            'KOINKYT_REQUEST_TIMEOUT_SECONDS',
            os.environ.get('REQUESTS_TIMEOUT', '10'),
        )
    ),
    'AML_DEFAULT_THRESHOLD': os.environ.get('AML_DEFAULT_THRESHOLD', '0.10'),
    'PROVIDERS': PROVIDERS_CONFIG,
}
