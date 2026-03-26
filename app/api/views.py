import json
from decimal import Decimal

from flask import request, g
from flask import current_app as app


from ..config import config
from ..models import Transactions, db
from ..logging import logger
from ..aml_bot_api import get_min_check_amount, aml_check_transaction
from . import api
from ..tasks import check_transaction
from app import create_app



app = create_app()
app.app_context().push()


def add_transaction_to_db(hash, account, amount, symbol, internal_type=False):
        logger.info('Adding tx to DB')
        status = ''

        if float(amount) > float(get_min_check_amount(symbol)):
            check_transaction.delay(symbol, account, hash)
            ttype = 'aml'
            status = 'pending'
            score = -1
        else:
            logger.warning('Transaction amount is lower than min check amount in config. Adding it with min score')
            ttype = 'aml'
            status = 'ready'
            score = 0
        try:
    
            with app.app_context():
                db.session.add(Transactions(tx_id = hash,
                                            status = status,
                                            ttype = ttype,
                                            crypto = symbol,
                                            score = score,
                                            amount = amount,
                                            address = account))
        
                db.session.commit()
                db.session.close() 
        except:
            with app.app_context():
                db.session.remove()
                db.session.commit()
                db.session.close() 


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
            return {'status': 'error', 'msg': 'tx already in DB, use /get_score/<txid>' }
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
                    'aml_score': float(tx_data.score),
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
  
