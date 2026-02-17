from .db_import import db


class Transactions(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tx_id = db.Column(db.String(120))
    status = db.Column(db.String(10))
    ttype = db.Column(db.String(10))
    score = db.Column(db.Numeric(precision=7, scale=5), default=-1)
    crypto = db.Column(db.String(20))
    amount = db.Column(db.Numeric(precision=52, scale=26), default=0) 
    address = db.Column(db.String(70))
    uid = db.Column(db.String(30))
    data = db.Column(db.String(70))
    last_update = db.Column(db.DateTime, default=db.func.current_timestamp(),
                                        onupdate=db.func.current_timestamp()) 
    __table_args__ = (db.UniqueConstraint('id'), )