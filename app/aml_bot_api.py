import requests as rq
import hashlib

from .config import config

if config['CURRENT_PROVIDER'] == 'amlbot':
    ACCESS_URL = config['PROVIDERS']['amlbot']['access_point']
    ACCESS_KEY = config['PROVIDERS']['amlbot']['access_key']
    ACCESS_ID = config['PROVIDERS']['amlbot']['access_id']
    FLOW = config['PROVIDERS']['amlbot']['flow']
else:
    pass


def symbol_to_aml_asset(symbol):
    eth_list = ['ETH', 'ETH-USDT', 'ETH-USDC', 'ETH-PYUSD']
    trx_list = ['TRX', 'USDT', 'USDC']
    sol_list = ['SOL', 'SOLANA-USDT', 'SOLANA-USDC', 'SOLANA-PYUSD']
    btc_list = ['BTC', 'LTC', 'DOGE']

    if symbol in btc_list:
        asset = symbol
    elif symbol in eth_list:
        asset = 'ETH'
    elif symbol in trx_list:
        asset = 'TRX'
    elif symbol in sol_list:
        asset = 'SOL'
    else:
        raise Exception(f"Cannot convert symbol to asset")


    return asset

    


def get_min_check_amount(symbol):
    return float(config['PROVIDERS'][config['CURRENT_PROVIDER']]['cryptos'][symbol]['min_check_amount'])
   

def aml_check_transaction(symbol, address, txid):
    token_string = f'{txid}:{ACCESS_KEY}:{ACCESS_ID}'
    token = str(hashlib.md5(token_string.encode()).hexdigest())
    payload = f'hash={txid}&address={address}&asset={symbol_to_aml_asset(symbol)}&direction=deposit&token={token}&accessId={ACCESS_ID}&locale=en_US&flow={FLOW}'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = rq.post(f'{ACCESS_URL}/',headers=headers, data=payload) 
    response.raise_for_status()
    return response.json()


def aml_recheck_transaction(uid, txid):
    token_string = f'{txid}:{ACCESS_KEY}:{ACCESS_ID}'
    token = str(hashlib.md5(token_string.encode()).hexdigest())
    payload = f'uid={uid}&accessId={ACCESS_ID}&token={token}'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = rq.post(f'{ACCESS_URL}/recheck',headers=headers, data=payload) 
    response.raise_for_status()
    return response.json()