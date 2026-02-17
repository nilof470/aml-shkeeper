import os
import json


def get_providers_config():
    provides_config = json.loads(os.environ.get('PROVIDERS'))
    return provides_config

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
    'AVAILABLE_CRYPTO_LIST': ['ETH', 'TRX', 'ETH-USDC', 'ETH-USDT', 'USDT', 'USDC'],
    'CURRENT_PROVIDER':  os.environ.get('CURRENT_PROVIDER', 'amlbot'),
    'PROVIDERS': get_providers_config(),
}


