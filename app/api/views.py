import json
from datetime import datetime, timedelta
from decimal import Decimal

from flask import request, g
from sqlalchemy import or_


from ..config import config
from ..models import Transactions, db
from ..logging import logger
from . import api, v1_api
from ..tasks import check_transaction


def add_transaction_to_db(hash, account, amount, symbol, internal_type=False):
    logger.info('Adding tx to DB')
    tx = Transactions(
        tx_id=hash,
        status='pending',
        provider=config['CURRENT_PROVIDER'],
        provider_status='pending',
        ttype='aml',
        crypto=symbol,
        amount=amount,
        address=account,
        threshold=Decimal(str(config['AML_DEFAULT_THRESHOLD'])),
        timeout_at=datetime.utcnow() + timedelta(seconds=config['CHECK_TIMEOUT_SECONDS']),
    )
    db.session.add(tx)
    db.session.commit()
    check_transaction.delay(tx.id)
    return tx


def _decimal_to_string(value):
    if value is None:
        return None
    return str(value)


def _datetime_to_string(value):
    if value is None:
        return None
    return value.isoformat()


def _json_object(value):
    if not value:
        return {}
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return {}


def _serialize_check(tx_data):
    return {
        'status': tx_data.status,
        'deposit_id': tx_data.deposit_id,
        'idempotency_key': tx_data.idempotency_key,
        'provider': tx_data.provider,
        'provider_status': tx_data.provider_status,
        'txid': tx_data.tx_id,
        'crypto': tx_data.crypto,
        'address': tx_data.address,
        'amount_crypto': _decimal_to_string(tx_data.amount),
        'score': _decimal_to_string(tx_data.score),
        'threshold': _decimal_to_string(tx_data.threshold),
        'uid': tx_data.uid,
        'asset': tx_data.asset,
        'network': tx_data.network,
        'signals': _json_object(tx_data.signals_json),
        'report_url': tx_data.report_url,
        'error_code': tx_data.error_code,
        'error_message': tx_data.error_message,
        'attempts': int(tx_data.attempts or 0),
        'next_retry_at': _datetime_to_string(tx_data.next_retry_at),
        'timeout_at': _datetime_to_string(tx_data.timeout_at),
        'updated_at': _datetime_to_string(tx_data.last_update),
    }


def _legacy_score(tx_data):
    if tx_data.score is None:
        return None
    return float(tx_data.score)


@api.post("/check_tx")
def check_tx(): 
    if g.symbol in config["AVAILABLE_CRYPTO_LIST"]:   
        try:
            tx_info = request.get_json(force=True)
        except Exception as e:
            raise Exception(f"Bad JSON in payout list: {e}")
        tx = Transactions.query.filter_by(tx_id = tx_info['hash']).first()
        if not tx:
            add_transaction_to_db(tx_info['hash'], tx_info['account'], tx_info['amount'], g.symbol, internal_type=False)
            logger.warning(F'Transaction {tx_info} has been added to DB')
            return get_score(tx_info['hash'])
        else:
            return get_score(tx_info['hash'])
    else:
        logger.warning(f'Request to unknown crypto {g.symbol}')
        return {'status': 'error', 'msg': 'unknown crypto' }


@api.get('/get_score/<txid>')
def get_score(txid):
    if g.symbol in config["AVAILABLE_CRYPTO_LIST"]:   
        tx_data = Transactions.query.filter_by(tx_id = txid).first()
        if tx_data:
            results = {'status': 'success', 
                    'txid': tx_data.tx_id, 
                    'aml_status': tx_data.status, 
                    'crypto': tx_data.crypto,
                    'aml_score': _legacy_score(tx_data),
                    'amount': tx_data.amount,
                    'address': tx_data.address,
                    }
            logger.warning(F'Have score, return {results}')
            return results
        else:
            logger.warning(F'TX {txid} cannot be found')
            return {'status': 'error', 'msg': 'txid not found'}
    else:
        logger.warning(f'Request to unknown crypto {g.symbol}')
        return {'status': 'error', 'msg': 'unknown crypto' }


@api.get('/dump')
def dump():
    transactions_info = {}
    tries = 3
    for i in range(tries):
        try:
            all_transactions = Transactions.query.all()
        except:
            if i < tries - 1: # i is zero indexed
                db.session.rollback()
                continue
            else:
                db.session.rollback()
                raise Exception(f"There was exception during query to the database, try again later")
        break
    for tx_data in all_transactions:
        transactions_info.update({tx_data.tx_id: {'txid': tx_data.tx_id, 
                    'aml_status': tx_data.status, 
                    'crypto': tx_data.crypto,
                    'aml_score': tx_data.score,
                    'amount': tx_data.amount,
                    'address': tx_data.address}})
    return transactions_info


@v1_api.post("/checks")
def create_check():
    try:
        tx_info = request.get_json(force=True)
    except Exception as e:
        raise Exception(f"Bad JSON in AML check request: {e}")

    required_fields = [
        'deposit_id',
        'idempotency_key',
        'crypto',
        'txid',
        'address',
        'amount_crypto',
        'asset',
        'network',
        'direction',
    ]
    missing = [field for field in required_fields if field not in tx_info]
    if missing:
        return {'status': 'error', 'msg': f"missing required fields: {', '.join(missing)}"}, 400

    existing = Transactions.query.filter(
        or_(
            Transactions.deposit_id == tx_info['deposit_id'],
            Transactions.idempotency_key == tx_info['idempotency_key'],
        )
    ).first()
    if existing:
        return _serialize_check(existing), 200

    if tx_info['crypto'] not in config['AVAILABLE_CRYPTO_LIST']:
        return {'status': 'error', 'msg': 'unsupported crypto'}, 400

    tx = Transactions(
        deposit_id=tx_info['deposit_id'],
        idempotency_key=tx_info['idempotency_key'],
        tx_id=tx_info['txid'],
        status='pending',
        ttype='aml',
        provider=config['CURRENT_PROVIDER'],
        provider_status='pending',
        crypto=tx_info['crypto'],
        amount=Decimal(str(tx_info['amount_crypto'])),
        address=tx_info['address'],
        asset=tx_info['asset'],
        network=tx_info['network'],
        threshold=Decimal(str(tx_info.get('threshold', config['AML_DEFAULT_THRESHOLD']))),
        timeout_at=datetime.utcnow() + timedelta(seconds=config['CHECK_TIMEOUT_SECONDS']),
    )
    db.session.add(tx)
    db.session.commit()
    check_transaction.delay(tx.id)
    return _serialize_check(tx), 201


@v1_api.get("/checks/<deposit_id>")
def get_check(deposit_id):
    tx = Transactions.query.filter_by(deposit_id=deposit_id).first()
    if not tx:
        return {'status': 'error', 'msg': 'deposit_id not found'}, 404
    return _serialize_check(tx)
  
