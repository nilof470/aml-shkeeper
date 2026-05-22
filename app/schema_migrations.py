from sqlalchemy import inspect, text


TRANSACTIONS_TABLE = "transactions"

TRANSACTIONS_COLUMNS = (
    ("deposit_id", "VARCHAR(120)"),
    ("idempotency_key", "VARCHAR(255)"),
    ("provider", "VARCHAR(30)"),
    ("provider_status", "VARCHAR(30)"),
    ("asset", "VARCHAR(30)"),
    ("network", "VARCHAR(30)"),
    ("threshold", "NUMERIC(7, 5)"),
    ("signals_json", "TEXT"),
    ("raw_response_json", "TEXT"),
    ("report_url", "VARCHAR(512)"),
    ("error_code", "VARCHAR(80)"),
    ("error_message", "TEXT"),
    ("next_retry_at", "DATETIME"),
    ("timeout_at", "DATETIME"),
    ("created_at", "DATETIME"),
)

TRANSACTIONS_INDEXES = (
    ("ix_transactions_deposit_id", "deposit_id", True),
    ("ix_transactions_idempotency_key", "idempotency_key", True),
)


def ensure_transactions_schema(db):
    """Apply additive schema updates for existing aml-shkeeper databases."""
    inspector = inspect(db.engine)
    if TRANSACTIONS_TABLE not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"]
        for column in inspector.get_columns(TRANSACTIONS_TABLE)
    }

    with db.engine.begin() as connection:
        for column, definition in TRANSACTIONS_COLUMNS:
            if column not in existing_columns:
                connection.execute(
                    text(
                        f"ALTER TABLE {TRANSACTIONS_TABLE} "
                        f"ADD COLUMN {column} {definition}"
                    )
                )
                existing_columns.add(column)

        existing_indexes = {
            index["name"]
            for index in inspect(connection).get_indexes(TRANSACTIONS_TABLE)
        }
        for index_name, column, unique in TRANSACTIONS_INDEXES:
            if column not in existing_columns or index_name in existing_indexes:
                continue
            unique_sql = "UNIQUE " if unique else ""
            connection.execute(
                text(
                    f"CREATE {unique_sql}INDEX {index_name} "
                    f"ON {TRANSACTIONS_TABLE} ({column})"
                )
            )
