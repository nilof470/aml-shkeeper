
import json
from datetime import datetime, timedelta

from celery.utils.log import get_task_logger

from . import celery
from .config import config
from .models import Transactions, db
from .utils import skip_if_running
from .aml_bot_api import aml_check_transaction, aml_recheck_transaction, normalize_amlbot_response

logger = get_task_logger(__name__)


def _create_app_context():
    from app import create_app
    flask_app = create_app()
    context = flask_app.app_context()
    context.push()
    return flask_app, context


def _persist_normalized_result(check, result):
    normalized = normalize_amlbot_response(result)
    now = datetime.utcnow()
    check.attempts = int(check.attempts or 0) + 1
    check.provider_status = normalized['provider_status']
    check.uid = normalized['uid'] or check.uid
    check.raw_response_json = json.dumps(normalized['raw_response'], sort_keys=True)
    check.signals_json = json.dumps(normalized['signals'] or {}, sort_keys=True)
    check.report_url = normalized['report_url']
    check.error_code = normalized['error_code']
    check.error_message = normalized['error_message']
    check.asset = normalized['asset'] or check.asset
    check.network = normalized['network'] or check.network

    if normalized['provider_status'] == 'success' and normalized['score'] is not None:
        check.score = normalized['score']
        check.status = 'ready'
        check.next_retry_at = None
    elif normalized['provider_status'] == 'pending':
        check.status = 'rechecking'
        check.next_retry_at = now + timedelta(seconds=config['CHECK_RETRY_SECONDS'])
    else:
        if int(check.attempts or 0) >= int(config['RETRY_UNTIL_FAILED']):
            check.status = 'failed'
            check.next_retry_at = None
        else:
            check.status = 'pending'
            check.next_retry_at = now + timedelta(seconds=config['CHECK_RETRY_SECONDS'])

    if check.timeout_at is None:
        check.timeout_at = now + timedelta(seconds=config['CHECK_TIMEOUT_SECONDS'])


@celery.task(bind=True)
@skip_if_running
def check_transaction(self, check_id, account=None, txid=None):
    context = None
    try:
        _, context = _create_app_context()
        check = Transactions.query.get(check_id)
        if check is None and account and txid:
            check = Transactions.query.filter_by(address=account, tx_id=txid).first()
        if check is None:
            logger.warning(f'Cannot find AML check {check_id}')
            return False
        result = aml_check_transaction(check.crypto, check.address, check.tx_id)
        _persist_normalized_result(check, result)
        db.session.add(check)
        db.session.commit()
        return True
    finally:
        db.session.remove()
        db.engine.dispose()
        if context is not None:
            context.pop()


@celery.task(bind=True)
@skip_if_running
def recheck_transactions(self):
    context = None
    try:
        _, context = _create_app_context()
        pd = Transactions.query.filter_by(ttype = 'aml', status = 'rechecking').all()
        pd_pending = Transactions.query.filter_by(ttype = 'aml', status = 'pending').all()
    except:
        db.session.rollback()
        raise Exception(f"There was exception during query to the database, try again later")
    finally:
        db.session.remove()
        db.engine.dispose()
        if context is not None:
            context.pop()
 
    if pd:
        for tx in pd:
            recheck_transaction.delay(tx.id)
    if pd_pending:
        for tx in pd_pending:
            check_transaction.delay(tx.id)
    return True


@celery.task(bind=True)
@skip_if_running
def recheck_transaction(self, check_id, txid=None, account_address=None):
    context = None
    try:
        _, context = _create_app_context()
        check = Transactions.query.get(check_id)
        if check is None and txid and account_address:
            check = Transactions.query.filter_by(address=account_address, tx_id=txid).first()
        if not check:
            logger.warning(f'Cannot find AML check {check_id}')
            return False
        if not check.uid:
            return check_transaction.delay(check.id)
        result = aml_recheck_transaction(check.uid)
        _persist_normalized_result(check, result)
        db.session.add(check)
        db.session.commit()
        return True
    finally:
        db.session.remove()
        db.engine.dispose()
        if context is not None:
            context.pop()
        


@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(int(config['RECHECK_TXS_EVERY_SECONDS']), recheck_transactions.s())
