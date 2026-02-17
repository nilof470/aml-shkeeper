
import time

from celery.schedules import crontab
from celery.utils.log import get_task_logger
import requests as rq

from . import celery
from .config import config
from .models import Transactions, db
from .utils import skip_if_running
from .aml_bot_api import aml_check_transaction, aml_recheck_transaction

logger = get_task_logger(__name__)

@celery.task(bind=True)
@skip_if_running
def check_transaction(self, symbol, account, txid):
    result = aml_check_transaction(symbol, account, txid)
    if (result['result']  and 
        result['data']['status'] == 'pending'and 
        'uid' in result['data'].keys()):
        status = 'rechecking'
        uid = result['data']['uid']
        score = -1
    elif (result['result']  and 
          'riskscore' in result['data'].keys() and
          'uid' in result['data'].keys() and
           result['data']['status'] == 'success'):
        status = 'ready'
        score = result['data']['riskscore']
        uid = result['data']['uid']
    else:
        logger.warning(f'Cannot update the transaction {txid}, something wrong - {result}')
        return False
    time.sleep(5)
    try:
        from app import create_app
        app = create_app()
        app.app_context().push()
        try:
            pd = Transactions.query.filter_by(address = account, tx_id = txid).first()
        except:
            db.session.rollback()
            raise Exception(f"There was exception during query to the database, try again later")
        pd.uid = uid
        pd.score = score
        pd.status = status
        with app.app_context():
            db.session.add(pd)
            db.session.commit()
            db.session.close()  

    finally:
        with app.app_context():
            db.session.remove()
            db.engine.dispose()


@celery.task(bind=True)
@skip_if_running
def recheck_transactions(self):
    try:
        from app import create_app
        app = create_app()
        app.app_context().push()
        pd = Transactions.query.filter_by(ttype = 'aml', status = 'rechecking').all()
        pd_pending = Transactions.query.filter_by(ttype = 'aml', status = 'pending').all()
    except:
        db.session.rollback()
        raise Exception(f"There was exception during query to the database, try again later")
    finally:
        with app.app_context():
            db.session.remove()
            db.engine.dispose()  
 
    if pd:
        for tx in pd:
            recheck_transaction.delay(tx.uid, tx.tx_id)
    if pd_pending:
        for tx in pd_pending:
            check_transaction.delay(tx.crypto, tx.address, tx.tx_id)
    return True


@celery.task(bind=True)
@skip_if_running
def recheck_transaction(self, uid, txid ):
    result = aml_recheck_transaction(uid, txid)
    if (result['result'] and 
        result['data']['status'] == 'pending'and 
        'uid' in result['data'].keys()):
        status = 'rechecking'
        uid = result['data']['uid']
        score = -1
    elif (result['result']  and 
          'riskscore' in result['data'].keys() and
          'uid' in result['data'].keys() and
          result['data']['status'] == 'success'):
        status = 'ready'
        score = result['data']['riskscore']
        uid = result['data']['uid']
    else:
        logger.warning(f'Cannot update the transaction {txid}, something wrong - {result}')
        return False
    
    try:
        pd = Transactions.query.filter_by( tx_id = txid).first() #address = address
    except:
        db.session.rollback()
        raise Exception(f"There was exception during query to the database, try again later")
    if not pd:
        logger.warning(f'Cannot find tx {txid} in DB')
        return False
    try:
        from app import create_app
        app = create_app()
        app.app_context().push()
        pd.uid = uid
        pd.score = score
        pd.status = status

        with app.app_context():
            db.session.add(pd)
            db.session.commit()
            db.session.close()  
    finally:
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
        


@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(int(config['RECHECK_TXS_EVERY_SECONDS']), recheck_transactions.s())


