import requests as rq
import hashlib

from .config import config

CURRENT_PROVIDER = config['CURRENT_PROVIDER']
PROVIDER_CONFIG = config['PROVIDERS'][CURRENT_PROVIDER]


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


def symbol_to_koinkyt_params(symbol):
    mapping = {
        'BTC': ('btc', ''),
        'ETH': ('eth', ''),
        'ETH-USDT': ('eth', 'USDT'),
        'ETH-USDC': ('eth', 'USDC'),
        'TRX': ('trx', ''),
        'USDT': ('trx', 'USDT'),
        'USDC': ('trx', 'USDC'),
    }
    try:
        return mapping[symbol]
    except KeyError:
        raise Exception(f"Cannot convert symbol to Koinkyt blockchain/token")


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


def normalize_koinkyt_response(response):
    if response.get('_transport_error') or response.get('_http_status', 200) >= 400:
        status = response.get('_http_status')
        error_text = str(response.get('error_message') or response)
        retryable = bool(response.get('_transport_error')) or status in (
            429,
            500,
            503,
        )
        if status == 404:
            retryable = 'try again later' in error_text.lower()
        return {
            'provider_status': 'checking' if retryable else 'error',
            'uid': response.get('id'),
            'score': None,
            'signals': {},
            'asset': None,
            'network': None,
            'report_url': response.get('link'),
            'raw_response': response,
            'error_code': response.get('error_code') or (
                f"http_{status}" if status else "transport_error"
            ),
            'error_message': response.get('error_message') or str(response),
            'retryable': retryable,
        }

    score = response.get('risk_score')
    signals = {}
    for field in (
        'risk_score_grade',
        'from_entity',
        'to_entity',
        'indirects',
        'alerts',
        'too_many_indirects',
    ):
        if response.get(field) is not None:
            signals[field] = response.get(field)

    if score is None:
        return {
            'provider_status': 'error',
            'uid': response.get('id'),
            'score': None,
            'signals': signals,
            'asset': None,
            'network': None,
            'report_url': response.get('link'),
            'raw_response': response,
            'error_code': response.get('error_code') or 'missing_risk_score',
            'error_message': (
                response.get('error_message') or 'Koinkyt response missing risk_score'
            ),
            'retryable': False,
        }

    return {
        'provider_status': 'success',
        'uid': response.get('id'),
        'score': score,
        'signals': signals,
        'asset': None,
        'network': None,
        'report_url': response.get('link'),
        'raw_response': response,
        'error_code': None,
        'error_message': None,
        'retryable': False,
    }


def normalize_provider_response(response):
    if CURRENT_PROVIDER == 'koinkyt':
        return normalize_koinkyt_response(response)
    return normalize_amlbot_response(response)

    
def get_min_check_amount(symbol):
    return float(config['PROVIDERS'][config['CURRENT_PROVIDER']]['cryptos'][symbol]['min_check_amount'])
   

def aml_check_transaction(symbol, address, txid):
    if CURRENT_PROVIDER == 'koinkyt':
        try:
            blockchain, token = symbol_to_koinkyt_params(symbol)
        except Exception as exc:
            return {
                '_http_status': 400,
                'error_code': 'unsupported_crypto',
                'error_message': str(exc),
            }
        api_key = PROVIDER_CONFIG.get('api_key', '')
        if not api_key:
            return {
                '_http_status': 401,
                'error_code': 'missing_api_key',
                'error_message': 'KOINKYT_API_KEY is not configured',
            }
        params = {
            'blockchain': blockchain,
            'token': token,
            'transaction': txid,
        }
        risk_profile_ids = PROVIDER_CONFIG.get('risk_profile_ids')
        if risk_profile_ids:
            params['risk_profile_ids'] = risk_profile_ids
        headers = {
            'accept': 'application/json',
            'X-API-Key': api_key,
        }
        try:
            response = rq.get(
                f"{PROVIDER_CONFIG['access_point'].rstrip('/')}/transaction",
                headers=headers,
                params=params,
                timeout=config['HTTP_TIMEOUT_SECONDS'],
            )
            try:
                data = response.json()
            except ValueError:
                data = {'error_message': response.text}
            if response.status_code >= 400:
                if isinstance(data, dict):
                    data['_http_status'] = response.status_code
                    data.setdefault('error_code', f"http_{response.status_code}")
                    data.setdefault('error_message', response.text)
                    return data
                return {
                    '_http_status': response.status_code,
                    'error_code': f"http_{response.status_code}",
                    'error_message': response.text,
                }
            return data
        except rq.RequestException as exc:
            return {
                '_transport_error': True,
                'error_code': 'transport_error',
                'error_message': str(exc),
            }

    ACCESS_URL = PROVIDER_CONFIG['access_point']
    ACCESS_KEY = PROVIDER_CONFIG['access_key']
    ACCESS_ID = PROVIDER_CONFIG['access_id']
    FLOW = PROVIDER_CONFIG['flow']
    token_string = f'{txid}:{ACCESS_KEY}:{ACCESS_ID}'
    token = str(hashlib.md5(token_string.encode()).hexdigest())
    payload = f'hash={txid}&address={address}&asset={symbol_to_aml_asset(symbol)}&direction=deposit&token={token}&accessId={ACCESS_ID}&locale=en_US&flow={FLOW}'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    try:
        response = rq.post(
            f'{ACCESS_URL}/',
            headers=headers,
            data=payload,
            timeout=config['HTTP_TIMEOUT_SECONDS'],
        )
        response.raise_for_status()
        return response.json()
    except rq.RequestException as exc:
        return {
            'result': False,
            'code': 'transport_error',
            'description': str(exc),
            '_transport_error': True,
        }


def aml_recheck_transaction(uid):
    if CURRENT_PROVIDER == 'koinkyt':
        return {
            '_transport_error': True,
            'error_code': 'unsupported_recheck',
            'error_message': 'Koinkyt recheck by uid is not supported; check by txid',
        }

    ACCESS_URL = PROVIDER_CONFIG['access_point']
    ACCESS_KEY = PROVIDER_CONFIG['access_key']
    ACCESS_ID = PROVIDER_CONFIG['access_id']
    token_string = f'{uid}:{ACCESS_KEY}:{ACCESS_ID}'
    token = str(hashlib.md5(token_string.encode()).hexdigest())
    payload = f'uid={uid}&accessId={ACCESS_ID}&token={token}'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    try:
        response = rq.post(
            f'{ACCESS_URL}/recheck',
            headers=headers,
            data=payload,
            timeout=config['HTTP_TIMEOUT_SECONDS'],
        )
        response.raise_for_status()
        return response.json()
    except rq.RequestException as exc:
        return {
            'result': False,
            'code': 'transport_error',
            'description': str(exc),
            '_transport_error': True,
        }
