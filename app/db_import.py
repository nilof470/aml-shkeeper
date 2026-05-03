import os

import flask_sqlalchemy
from sqlalchemy.pool import NullPool


def _engine_options():
    uri = os.environ.get("SQLALCHEMY_DATABASE_URI", "")
    if uri.startswith("sqlite"):
        return {"poolclass": NullPool}
    return {
        "connect_args": {"connect_timeout": 60},
        "isolation_level": "READ COMMITTED",
        "poolclass": NullPool,
    }


db = flask_sqlalchemy.SQLAlchemy(engine_options=_engine_options())
