import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator, Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.types import JSON

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL es obligatoria")

IS_SQLITE = "sqlite" in DATABASE_URL.lower()
JSONType = JSON if IS_SQLITE else JSONB

engine = create_engine(
    DATABASE_URL,
    future=True,
    pool_pre_ping=not IS_SQLITE,
    pool_recycle=1800 if not IS_SQLITE else -1,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Fixture(Base):
    __tablename__ = "fixtures"

    fixture_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    league_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    league_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    country: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    season: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fixture_datetime: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    status_short: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    status_long: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    home_team_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    home_team_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    away_team_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    away_team_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    venue_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    venue_city: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class PredictionRun(Base):
    __tablename__ = "prediction_runs"

    run_id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    workflow_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trigger_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fixtures_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fixtures_processed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fixtures_skipped: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    api_requests_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Prediction(Base):
    __tablename__ = "predictions"

    fixture_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    liga_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    liga: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pais: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hora: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    estado: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    local: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    visitante: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    predicted_winner: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    prob_local: Mapped[Optional[float]] = mapped_column(Numeric(10, 6, asdecimal=False), nullable=True)
    prob_empate: Mapped[Optional[float]] = mapped_column(Numeric(10, 6, asdecimal=False), nullable=True)
    prob_visitante: Mapped[Optional[float]] = mapped_column(Numeric(10, 6, asdecimal=False), nullable=True)

    goles_local: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)
    goles_visitante: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)
    gol_local: Mapped[Optional[float]] = mapped_column(Numeric(10, 6, asdecimal=False), nullable=True)
    gol_visitante: Mapped[Optional[float]] = mapped_column(Numeric(10, 6, asdecimal=False), nullable=True)

    ambos_marcan: Mapped[Optional[float]] = mapped_column(Numeric(10, 6, asdecimal=False), nullable=True)
    over15: Mapped[Optional[float]] = mapped_column(Numeric(10, 6, asdecimal=False), nullable=True)
    over25: Mapped[Optional[float]] = mapped_column(Numeric(10, 6, asdecimal=False), nullable=True)
    over35: Mapped[Optional[float]] = mapped_column(Numeric(10, 6, asdecimal=False), nullable=True)

    corners_local: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)
    corners_visitante: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)
    corners_totales: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)
    over75_corners: Mapped[Optional[float]] = mapped_column(Numeric(10, 6, asdecimal=False), nullable=True)
    over85_corners: Mapped[Optional[float]] = mapped_column(Numeric(10, 6, asdecimal=False), nullable=True)
    over95_corners: Mapped[Optional[float]] = mapped_column(Numeric(10, 6, asdecimal=False), nullable=True)

    tarjetas_local: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)
    tarjetas_visitante: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)
    tarjetas_totales: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)
    over35_tarjetas: Mapped[Optional[float]] = mapped_column(Numeric(10, 6, asdecimal=False), nullable=True)
    over45_tarjetas: Mapped[Optional[float]] = mapped_column(Numeric(10, 6, asdecimal=False), nullable=True)

    tiros_local: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)
    tiros_visitante: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)
    puerta_local: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)
    puerta_visitante: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)

    apuesta_principal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mercado_principal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prob_apuesta: Mapped[Optional[float]] = mapped_column(Numeric(10, 6, asdecimal=False), nullable=True)
    cuota_principal: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)
    edge_principal: Mapped[Optional[float]] = mapped_column(Numeric(10, 6, asdecimal=False), nullable=True)
    es_value_bet: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    confianza: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    apuestas_fuertes: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)
    market_breakdown: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)

    posible_error_cuota: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    cuota_sospechosa: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    oportunidad_detectada: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    probabilidad_implicita_principal: Mapped[Optional[float]] = mapped_column(Numeric(10, 6, asdecimal=False), nullable=True)
    probabilidad_justa_principal: Mapped[Optional[float]] = mapped_column(Numeric(10, 6, asdecimal=False), nullable=True)
    overround_1x2: Mapped[Optional[float]] = mapped_column(Numeric(10, 6, asdecimal=False), nullable=True)
    vigorish_1x2: Mapped[Optional[float]] = mapped_column(Numeric(10, 6, asdecimal=False), nullable=True)

    data_quality: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stake_sugerido_unidades: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)
    market_stability: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)
    market_reliability: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)
    source_run_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class OddsSnapshot(Base):
    __tablename__ = "odds_snapshot"

    snapshot_id: Mapped[int] = mapped_column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    snapshot_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    bookmaker_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    bookmaker_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    home: Mapped[Optional[float]] = mapped_column("odds_home", Numeric(10, 4, asdecimal=False), nullable=True)
    draw: Mapped[Optional[float]] = mapped_column("odds_draw", Numeric(10, 4, asdecimal=False), nullable=True)
    away: Mapped[Optional[float]] = mapped_column("odds_away", Numeric(10, 4, asdecimal=False), nullable=True)

    over15: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)
    over25: Mapped[Optional[float]] = mapped_column("odds_over25", Numeric(10, 4, asdecimal=False), nullable=True)
    over35: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)
    under45: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)
    btts_yes: Mapped[Optional[float]] = mapped_column("odds_btts_yes", Numeric(10, 4, asdecimal=False), nullable=True)

    dc_1x: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)
    dc_x2: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)
    dc_12: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)

    over75_corners: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)
    over85_corners: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)
    over95_corners: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)

    over35_cards: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)
    over45_cards: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)

    shots_home: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)
    shots_away: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)
    sot_home: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)
    sot_away: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)

    raw_payload: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)


class TeamStatsCache(Base):
    __tablename__ = "team_stats_cache"
    __table_args__ = (UniqueConstraint("team_id", "league_id", "season", name="team_stats_cache_team_id_league_id_season_key"),)

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    league_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False)
    stats: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)
    fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class PricingAlert(Base):
    __tablename__ = "pricing_alerts"

    alert_id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    fixture_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    alert_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    alert_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mercado: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    jugada: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cuota: Mapped[Optional[float]] = mapped_column(Numeric(10, 4, asdecimal=False), nullable=True)
    prob_modelo: Mapped[Optional[float]] = mapped_column(Numeric(10, 6, asdecimal=False), nullable=True)
    prob_implicita: Mapped[Optional[float]] = mapped_column(Numeric(10, 6, asdecimal=False), nullable=True)
    prob_justa: Mapped[Optional[float]] = mapped_column(Numeric(10, 6, asdecimal=False), nullable=True)
    edge: Mapped[Optional[float]] = mapped_column(Numeric(10, 6, asdecimal=False), nullable=True)
    confianza: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    es_value_bet: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    posible_error_cuota: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    cuota_sospechosa: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    oportunidad_detectada: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    run_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)


REQUIRED_TABLES = {
    "fixtures",
    "predictions",
    "prediction_runs",
    "odds_snapshot",
    "team_stats_cache",
    "pricing_alerts",
}

REQUIRED_PREDICTION_COLUMNS = {
    "over75_corners": "NUMERIC(10,6)",
    "stake_sugerido_unidades": "NUMERIC(10,4)",
    "market_stability": "NUMERIC(10,4)",
    "market_reliability": "NUMERIC(10,4)",
    "market_breakdown": "JSON" if IS_SQLITE else "JSONB",
}

REQUIRED_ODDS_SNAPSHOT_COLUMNS = {
    "bookmaker_id": "BIGINT",
    "bookmaker_name": "TEXT",
    "odds_home": "NUMERIC(10,4)",
    "odds_draw": "NUMERIC(10,4)",
    "odds_away": "NUMERIC(10,4)",
    "over15": "NUMERIC(10,4)",
    "odds_over25": "NUMERIC(10,4)",
    "over35": "NUMERIC(10,4)",
    "under45": "NUMERIC(10,4)",
    "odds_btts_yes": "NUMERIC(10,4)",
    "dc_1x": "NUMERIC(10,4)",
    "dc_x2": "NUMERIC(10,4)",
    "dc_12": "NUMERIC(10,4)",
    "over75_corners": "NUMERIC(10,4)",
    "over85_corners": "NUMERIC(10,4)",
    "over95_corners": "NUMERIC(10,4)",
    "over35_cards": "NUMERIC(10,4)",
    "over45_cards": "NUMERIC(10,4)",
    "shots_home": "NUMERIC(10,4)",
    "shots_away": "NUMERIC(10,4)",
    "sot_home": "NUMERIC(10,4)",
    "sot_away": "NUMERIC(10,4)",
    "raw_payload": "JSON" if IS_SQLITE else "JSONB",
}

REQUIRED_PRICING_ALERTS_COLUMNS = {
    "alert_title": "TEXT",
    "mercado": "TEXT",
    "jugada": "TEXT",
    "cuota": "NUMERIC(10,4)",
    "prob_modelo": "NUMERIC(10,6)",
    "prob_implicita": "NUMERIC(10,6)",
    "prob_justa": "NUMERIC(10,6)",
    "edge": "NUMERIC(10,6)",
    "confianza": "INTEGER",
    "es_value_bet": "INTEGER DEFAULT 0",
    "posible_error_cuota": "INTEGER DEFAULT 0",
    "cuota_sospechosa": "INTEGER DEFAULT 0",
    "oportunidad_detectada": "INTEGER DEFAULT 0",
    "run_id": "BIGINT",
    "raw_payload": "JSON" if IS_SQLITE else "JSONB",
}

REQUIRED_INDEXES = {
    "ix_fixtures_league_id": ("fixtures", ("league_id",)),
    "ix_fixtures_fixture_datetime": ("fixtures", ("fixture_datetime",)),
    "ix_fixtures_status_short": ("fixtures", ("status_short",)),
    "ix_predictions_liga_id": ("predictions", ("liga_id",)),
    "ix_predictions_hora": ("predictions", ("hora",)),
    "ix_odds_snapshot_fixture_id": ("odds_snapshot", ("fixture_id",)),
    "ix_odds_snapshot_snapshot_at": ("odds_snapshot", ("snapshot_at",)),
    "ix_pricing_alerts_fixture_id": ("pricing_alerts", ("fixture_id",)),
}


def validate_db_schema() -> None:
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    missing = sorted(REQUIRED_TABLES - existing)
    if missing:
        raise RuntimeError(f"Faltan tablas requeridas: {', '.join(missing)}")


def ensure_table_columns(table_name: str, required_columns: dict[str, str]) -> None:
    inspector = inspect(engine)
    existing_columns = {col["name"] for col in inspector.get_columns(table_name)}
    pending = [(name, definition) for name, definition in required_columns.items() if name not in existing_columns and definition]
    if not pending:
        return

    with engine.begin() as conn:
        for column_name, definition in pending:
            sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
            conn.execute(text(sql))


def ensure_prediction_columns() -> None:
    ensure_table_columns("predictions", REQUIRED_PREDICTION_COLUMNS)


def ensure_odds_snapshot_columns() -> None:
    ensure_table_columns("odds_snapshot", REQUIRED_ODDS_SNAPSHOT_COLUMNS)


def ensure_pricing_alerts_columns() -> None:
    ensure_table_columns("pricing_alerts", REQUIRED_PRICING_ALERTS_COLUMNS)


def ensure_required_indexes() -> None:
    inspector = inspect(engine)
    existing_indexes = {index["name"] for table in REQUIRED_TABLES for index in inspector.get_indexes(table)}
    with engine.begin() as conn:
        for index_name, (table_name, columns) in REQUIRED_INDEXES.items():
            if index_name in existing_indexes:
                continue
            joined_columns = ", ".join(columns)
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({joined_columns})"))


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_prediction_columns()
    ensure_odds_snapshot_columns()
    ensure_pricing_alerts_columns()
    ensure_required_indexes()
    validate_db_schema()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
