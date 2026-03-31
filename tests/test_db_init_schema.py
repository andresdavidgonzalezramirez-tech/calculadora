import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_db_init_schema.db")
sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect, text

import db


def test_init_db_is_idempotent_and_keeps_required_schema():
    db.init_db()
    db.init_db()

    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())
    assert db.REQUIRED_TABLES.issubset(existing_tables)

    prediction_cols = {c["name"] for c in inspector.get_columns("predictions")}
    assert set(db.REQUIRED_PREDICTION_COLUMNS).issubset(prediction_cols)

    odds_cols = {c["name"] for c in inspector.get_columns("odds_snapshot")}
    assert set(db.REQUIRED_ODDS_SNAPSHOT_COLUMNS).issubset(odds_cols)

    alerts_cols = {c["name"] for c in inspector.get_columns("pricing_alerts")}
    assert set(db.REQUIRED_PRICING_ALERTS_COLUMNS).issubset(alerts_cols)

    indexes = {idx["name"] for table in db.REQUIRED_TABLES for idx in inspector.get_indexes(table)}
    assert set(db.REQUIRED_INDEXES).issubset(indexes)


def test_init_db_restores_missing_column_and_index():
    db.init_db()

    with db.engine.begin() as conn:
        conn.execute(text("DROP INDEX IF EXISTS ix_predictions_liga_id"))
        conn.execute(text("DROP TABLE IF EXISTS schema_autofix_probe"))
        conn.execute(text("CREATE TABLE schema_autofix_probe (id INTEGER PRIMARY KEY)"))

    db.ensure_table_columns("schema_autofix_probe", {"extra_col": "TEXT"})

    db.init_db()

    inspector = inspect(db.engine)
    probe_cols = {c["name"] for c in inspector.get_columns("schema_autofix_probe")}
    assert "extra_col" in probe_cols

    indexes = {idx["name"] for idx in inspector.get_indexes("predictions")}
    assert "ix_predictions_liga_id" in indexes
