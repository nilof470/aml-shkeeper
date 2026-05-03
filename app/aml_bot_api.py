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


def normalize_amlbot_response(response):
    data = response.get('data') or {}
    raw_status = data.get('status')
    result = bool(response.get('result'))

    if not result:
        return {
            'provider_status': 'error',
            'uid': data.get('uid') or response.get('uid'),
            'score': None,
            'signals': {},
            'asset': data.get('asset'),
            'network': data.get('network'),
            'report_url': data.get('report_url') or data.get('reportUrl') or data.get('url'),
            'raw_response': response,
            'error_code': response.get('code') or response.get('error_code') or data.get('code'),
            'error_message': response.get('description') or response.get('message') or str(response),
        }

    score = data.get('riskscore')
    if score is None:
        score = data.get('riskScore')
    if score is None:
        score = data.get('score')

    if raw_status == 'pending' or score is None:
        provider_status = 'pending' if raw_status in (None, 'pending') else raw_status
    elif raw_status == 'success':
        provider_status = 'success'
    else:
        provider_status = raw_status or 'success'

    return {
        'provider_status': provider_status,
        'uid': data.get('uid'),
        'score': score,
        'signals': data.get('signals') or data.get('risks') or data.get('risk') or {},
        'asset': data.get('asset'),
        'network': data.get('network'),
        'report_url': data.get('report_url') or data.get('reportUrl') or data.get('url'),
        'raw_response': response,
        'error_code': data.get('code') or response.get('code'),
        'error_message': data.get('description') or response.get('description'),
    }

    
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


def aml_recheck_transaction(uid):
    token_string = f'{uid}:{ACCESS_KEY}:{ACCESS_ID}'
    token = str(hashlib.md5(token_string.encode()).hexdigest())
    payload = f'uid={uid}&accessId={ACCESS_ID}&token={token}'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = rq.post(f'{ACCESS_URL}/recheck',headers=headers, data=payload) 
    response.raise_for_status()
    return response.json()
