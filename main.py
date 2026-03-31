from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session

from db import (
    Fixture,
    OddsSnapshot,
    Prediction,
    PredictionRun,
    PricingAlert,
    TeamStatsCache,
    get_db,
    init_db,
    utcnow,
)
from predictor import calcular_alerta_pricing, calcular_partido


app = FastAPI(title="Proyecto Apuestas Reales", version="4.2.0")

raw_origins = os.getenv("CORS_ORIGINS", "*").strip()
allow_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()] or ["*"]
allow_credentials = allow_origins != ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


def parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        raw = raw.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(raw)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def none_if_missing(value: Any) -> Any:
    if value in ("", None):
        return None
    return value


def pct_or_none(value: Any, digits: int = 2) -> Optional[float]:
    if value is None:
        return None
    try:
        return round(float(value) * 100, digits)
    except (TypeError, ValueError):
        return None


def num_or_none(value: Any, digits: Optional[int] = None) -> Optional[float]:
    if value is None:
        return None
    try:
        num = float(value)
        return round(num, digits) if digits is not None else num
    except (TypeError, ValueError):
        return None


def int_or_none(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class FixtureInput(BaseModel):
    fixture_id: int
    league_id: int = 0
    league_name: str = ""
    country: str = ""
    season: int = 0
    fixture_datetime: str = ""
    status_short: str = "NS"
    home_team_id: int = 0
    away_team_id: int = 0
    home_team_name: str = ""
    away_team_name: str = ""

    gf_home: float = 0
    ga_home: float = 0
    gf_away: float = 0
    ga_away: float = 0

    cf_home: float = 0
    ca_home: float = 0
    cf_away: float = 0
    ca_away: float = 0

    yf_home: float = 0
    yf_away: float = 0

    shots_home: float = 0
    shots_away: float = 0
    shots_on_target_home: float = 0
    shots_on_target_away: float = 0

    form_home: float = 0
    form_away: float = 0
    data_quality: float = 0.8

    home_stats: Dict[str, Any] = Field(default_factory=dict)
    away_stats: Dict[str, Any] = Field(default_factory=dict)
    home_recent_form: List[Dict[str, Any]] = Field(default_factory=list)
    away_recent_form: List[Dict[str, Any]] = Field(default_factory=list)
    head_to_head: List[Dict[str, Any]] = Field(default_factory=list)
    odds: Dict[str, Any] = Field(default_factory=dict)
    collection_meta: Dict[str, Any] = Field(default_factory=dict)


class IngestRunRequest(BaseModel):
    fixtures: List[FixtureInput] = Field(default_factory=list)
    workflow_name: str = "bankenban_ingest"
    trigger_type: str = "schedule"
    persist: bool = True


class PredictCompatRequest(BaseModel):
    fixtures: List[FixtureInput] = Field(default_factory=list)


def upsert_fixture(db: Session, item: FixtureInput) -> None:
    existing = db.get(Fixture, item.fixture_id)
    dt = parse_dt(item.fixture_datetime)

    if existing is None:
        db.add(
            Fixture(
                fixture_id=item.fixture_id,
                league_id=item.league_id,
                league_name=item.league_name,
                country=item.country,
                season=item.season,
                fixture_datetime=dt,
                status_short=item.status_short,
                status_long=item.status_short,
                home_team_id=item.home_team_id,
                home_team_name=item.home_team_name,
                away_team_id=item.away_team_id,
                away_team_name=item.away_team_name,
                created_at=utcnow(),
                updated_at=utcnow(),
            )
        )
        return

    existing.league_id = item.league_id
    existing.league_name = item.league_name
    existing.country = item.country
    existing.season = item.season
    existing.fixture_datetime = dt
    existing.status_short = item.status_short
    existing.status_long = item.status_short
    existing.home_team_id = item.home_team_id
    existing.home_team_name = item.home_team_name
    existing.away_team_id = item.away_team_id
    existing.away_team_name = item.away_team_name
    existing.updated_at = utcnow()


def store_stats_cache(db: Session, item: FixtureInput) -> None:
    for team_id, side_hint, payload in [
        (item.home_team_id, "home", item.home_stats),
        (item.away_team_id, "away", item.away_stats),
    ]:
        if not team_id or not isinstance(payload, dict) or not payload:
            continue

        stmt = select(TeamStatsCache).where(
            TeamStatsCache.team_id == team_id,
            TeamStatsCache.league_id == item.league_id,
            TeamStatsCache.season == item.season,
        )
        existing = db.execute(stmt).scalar_one_or_none()

        if existing is None:
            db.add(
                TeamStatsCache(
                    team_id=team_id,
                    league_id=item.league_id,
                    season=item.season,
                    stats=payload,
                    fetched_at=utcnow(),
                    expires_at=None,
                )
            )
        else:
            existing.stats = payload
            existing.fetched_at = utcnow()


def store_odds_snapshot(db: Session, item: FixtureInput) -> None:
    odds = item.odds or {}
    meta = item.collection_meta or {}

    db.add(
        OddsSnapshot(
            fixture_id=item.fixture_id,
            snapshot_at=utcnow(),
            bookmaker_id=meta.get("bookmaker_preferred"),
            bookmaker_name=meta.get("bookmaker_name"),
            home=odds.get("home"),
            draw=odds.get("draw"),
            away=odds.get("away"),
            over15=odds.get("over15"),
            over25=odds.get("over25"),
            over35=odds.get("over35"),
            under45=odds.get("under45"),
            btts_yes=odds.get("btts_yes"),
            dc_1x=odds.get("dc_1x"),
            dc_x2=odds.get("dc_x2"),
            dc_12=odds.get("dc_12"),
            over75_corners=odds.get("over75_corners"),
            over85_corners=odds.get("over85_corners"),
            over95_corners=odds.get("over95_corners"),
            over35_cards=odds.get("over35_cards"),
            over45_cards=odds.get("over45_cards"),
            shots_home=odds.get("shots_home"),
            shots_away=odds.get("shots_away"),
            sot_home=odds.get("sot_home"),
            sot_away=odds.get("sot_away"),
            raw_payload=odds,
        )
    )


def upsert_prediction(db: Session, result: Dict[str, Any], run_id: int) -> None:
    existing = db.get(Prediction, int(result["fixture_id"]))
    dt = parse_dt(result.get("hora"))

    if existing is None:
        existing = Prediction(fixture_id=int(result["fixture_id"]))
        db.add(existing)

    existing.liga_id = result.get("liga_id")
    existing.liga = result.get("liga")
    existing.pais = result.get("pais")
    existing.hora = dt
    existing.estado = result.get("estado")
    existing.local = result.get("local")
    existing.visitante = result.get("visitante")
    existing.predicted_winner = result.get("predicted_winner")

    existing.prob_local = result.get("prob_local")
    existing.prob_empate = result.get("prob_empate")
    existing.prob_visitante = result.get("prob_visitante")

    existing.goles_local = result.get("goles_local")
    existing.goles_visitante = result.get("goles_visitante")
    existing.gol_local = result.get("gol_local")
    existing.gol_visitante = result.get("gol_visitante")

    existing.ambos_marcan = result.get("ambos_marcan")
    existing.over15 = result.get("over15")
    existing.over25 = result.get("over25")
    existing.over35 = result.get("over35")

    existing.corners_local = result.get("corners_local")
    existing.corners_visitante = result.get("corners_visitante")
    existing.corners_totales = result.get("corners_totales")
    existing.over75_corners = result.get("over75_corners")
    existing.over85_corners = result.get("over85_corners")
    existing.over95_corners = result.get("over95_corners")

    existing.tarjetas_local = result.get("tarjetas_local")
    existing.tarjetas_visitante = result.get("tarjetas_visitante")
    existing.tarjetas_totales = result.get("tarjetas_totales")
    existing.over35_tarjetas = result.get("over35_tarjetas")
    existing.over45_tarjetas = result.get("over45_tarjetas")

    existing.tiros_local = result.get("tiros_local")
    existing.tiros_visitante = result.get("tiros_visitante")
    existing.puerta_local = result.get("puerta_local")
    existing.puerta_visitante = result.get("puerta_visitante")

    existing.apuesta_principal = result.get("apuesta_principal")
    existing.mercado_principal = result.get("mercado_principal")
    existing.prob_apuesta = result.get("prob_apuesta")
    existing.cuota_principal = result.get("cuota_principal")
    existing.edge_principal = result.get("edge_principal")
    existing.es_value_bet = int(result.get("es_value_bet", 0) or 0)
    existing.confianza = result.get("confianza")
    existing.apuestas_fuertes = result.get("apuestas_fuertes") or []

    existing.posible_error_cuota = int(result.get("posible_error_cuota", 0) or 0)
    existing.cuota_sospechosa = int(result.get("cuota_sospechosa", 0) or 0)
    existing.oportunidad_detectada = int(result.get("oportunidad_detectada", 0) or 0)
    existing.probabilidad_implicita_principal = result.get("probabilidad_implicita_principal")
    existing.probabilidad_justa_principal = result.get("probabilidad_justa_principal")
    existing.overround_1x2 = result.get("overround_1x2")
    existing.vigorish_1x2 = result.get("vigorish_1x2")

    existing.data_quality = result.get("data_quality")
    existing.model_version = result.get("model_version")
    existing.stake_sugerido_unidades = result.get("stake_sugerido_unidades")
    existing.market_stability = result.get("market_stability")
    existing.market_reliability = result.get("market_reliability")
    existing.source_run_id = run_id
    existing.updated_at = utcnow()
    if existing.created_at is None:
        existing.created_at = utcnow()


def store_pricing_alert(db: Session, result: Dict[str, Any], run_id: int) -> None:
    alert = calcular_alerta_pricing(result)
    db.add(
        PricingAlert(
            fixture_id=alert["fixture_id"],
            created_at=utcnow(),
            alert_level=alert["alert_level"],
            alert_title=alert["alert_title"],
            mercado=alert["mercado"],
            jugada=alert["jugada"],
            cuota=alert["cuota"],
            prob_modelo=alert["prob_modelo"],
            prob_implicita=alert["prob_implicita"],
            prob_justa=alert["prob_justa"],
            edge=alert["edge"],
            confianza=alert["confianza"],
            es_value_bet=int(alert.get("es_value_bet", 0) or 0),
            posible_error_cuota=int(alert.get("posible_error_cuota", 0) or 0),
            cuota_sospechosa=int(alert.get("cuota_sospechosa", 0) or 0),
            oportunidad_detectada=int(alert.get("oportunidad_detectada", 0) or 0),
            run_id=run_id,
            raw_payload=alert,
        )
    )


def serialize_prediction(p: Prediction) -> Dict[str, Any]:
    payload = {
        "id": int(p.fixture_id),
        "fixture_id": int(p.fixture_id),
        "liga_id": int_or_none(p.liga_id),
        "ligaId": int_or_none(p.liga_id),
        "liga": none_if_missing(p.liga),
        "pais": none_if_missing(p.pais),
        "hora": p.hora.isoformat() if p.hora else None,
        "estado": none_if_missing(p.estado),
        "local": none_if_missing(p.local),
        "visitante": none_if_missing(p.visitante),
        "predicted_winner": none_if_missing(p.predicted_winner),
        "predictedWinner": none_if_missing(p.predicted_winner),

        "prob_local": num_or_none(p.prob_local, 6),
        "prob_empate": num_or_none(p.prob_empate, 6),
        "prob_visitante": num_or_none(p.prob_visitante, 6),
        "probLocal": pct_or_none(p.prob_local, 0),
        "probEmpate": pct_or_none(p.prob_empate, 0),
        "probVisitante": pct_or_none(p.prob_visitante, 0),

        "goles_local": num_or_none(p.goles_local, 4),
        "goles_visitante": num_or_none(p.goles_visitante, 4),
        "golesLocal": num_or_none(p.goles_local, 4),
        "golesVisitante": num_or_none(p.goles_visitante, 4),

        "gol_local": num_or_none(p.gol_local, 6),
        "gol_visitante": num_or_none(p.gol_visitante, 6),
        "golLocal": pct_or_none(p.gol_local, 0),
        "golVisitante": pct_or_none(p.gol_visitante, 0),

        "ambos_marcan": num_or_none(p.ambos_marcan, 6),
        "ambosMarcan": pct_or_none(p.ambos_marcan, 0),
        "over15": pct_or_none(p.over15, 0),
        "over25": pct_or_none(p.over25, 0),
        "over35": pct_or_none(p.over35, 0),

        "corners_local": num_or_none(p.corners_local, 4),
        "corners_visitante": num_or_none(p.corners_visitante, 4),
        "corners_totales": num_or_none(p.corners_totales, 4),
        "cornersLocal": num_or_none(p.corners_local, 4),
        "cornersVisitante": num_or_none(p.corners_visitante, 4),
        "cornersTotales": num_or_none(p.corners_totales, 4),
        "over85_corners": num_or_none(p.over85_corners, 6),
        "over95_corners": num_or_none(p.over95_corners, 6),
        "over85Corners": pct_or_none(p.over85_corners, 0),
        "over75_corners": num_or_none(p.over75_corners, 6),
        "over75Corners": pct_or_none(p.over75_corners, 0),
        "over95Corners": pct_or_none(p.over95_corners, 0),

        "tarjetas_local": num_or_none(p.tarjetas_local, 4),
        "tarjetas_visitante": num_or_none(p.tarjetas_visitante, 4),
        "tarjetas_totales": num_or_none(p.tarjetas_totales, 4),
        "tarjetasLocal": num_or_none(p.tarjetas_local, 4),
        "tarjetasVisitante": num_or_none(p.tarjetas_visitante, 4),
        "tarjetasTotales": num_or_none(p.tarjetas_totales, 4),
        "over35_tarjetas": num_or_none(p.over35_tarjetas, 6),
        "over45_tarjetas": num_or_none(p.over45_tarjetas, 6),
        "over35Tarjetas": pct_or_none(p.over35_tarjetas, 0),
        "over45Tarjetas": pct_or_none(p.over45_tarjetas, 0),

        "tiros_local": num_or_none(p.tiros_local, 4),
        "tiros_visitante": num_or_none(p.tiros_visitante, 4),
        "tirosLocal": num_or_none(p.tiros_local, 4),
        "tirosVisitante": num_or_none(p.tiros_visitante, 4),
        "puerta_local": num_or_none(p.puerta_local, 4),
        "puerta_visitante": num_or_none(p.puerta_visitante, 4),
        "puertaLocal": num_or_none(p.puerta_local, 4),
        "puertaVisitante": num_or_none(p.puerta_visitante, 4),

        "apuesta_principal": none_if_missing(p.apuesta_principal),
        "mercado_principal": none_if_missing(p.mercado_principal),
        "apuestaPrincipal": none_if_missing(p.apuesta_principal),
        "mercadoPrincipal": none_if_missing(p.mercado_principal),

        "prob_apuesta": num_or_none(p.prob_apuesta, 6),
        "probApuesta": pct_or_none(p.prob_apuesta, 0),

        "cuota_principal": num_or_none(p.cuota_principal, 4),
        "cuotaPrincipal": num_or_none(p.cuota_principal, 4),
        "tiene_cuota_principal": bool((p.cuota_principal or 0) > 1.0),
        "tieneCuotaPrincipal": bool((p.cuota_principal or 0) > 1.0),

        "edge_principal": num_or_none(p.edge_principal, 6),
        "edgePrincipal": pct_or_none(p.edge_principal, 2),

        "es_value_bet": bool(int(p.es_value_bet or 0)),
        "esValueBet": bool(int(p.es_value_bet or 0)),
        "confianza": int_or_none(p.confianza),

        "posible_error_cuota": bool(int(p.posible_error_cuota or 0)),
        "cuota_sospechosa": bool(int(p.cuota_sospechosa or 0)),
        "oportunidad_detectada": bool(int(p.oportunidad_detectada or 0)),
        "posibleErrorCuota": bool(int(p.posible_error_cuota or 0)),
        "cuotaSospechosa": bool(int(p.cuota_sospechosa or 0)),
        "oportunidadDetectada": bool(int(p.oportunidad_detectada or 0)),

        "apuestas_fuertes": p.apuestas_fuertes or [],
        "apuestasFuertes": p.apuestas_fuertes or [],

        "probabilidad_implicita_principal": num_or_none(p.probabilidad_implicita_principal, 6),
        "probabilidad_justa_principal": num_or_none(p.probabilidad_justa_principal, 6),
        "overround_1x2": num_or_none(p.overround_1x2, 6),
        "vigorish_1x2": num_or_none(p.vigorish_1x2, 6),

        "data_quality": num_or_none(p.data_quality, 4),
        "model_version": none_if_missing(p.model_version),
        "modelVersion": none_if_missing(p.model_version),
        "stake_sugerido_unidades": num_or_none(p.stake_sugerido_unidades, 4),
        "stakeSugeridoUnidades": num_or_none(p.stake_sugerido_unidades, 4),
        "market_stability": num_or_none(p.market_stability, 4),
        "marketStability": num_or_none(p.market_stability, 4),
        "market_reliability": num_or_none(p.market_reliability, 4),
        "marketReliability": num_or_none(p.market_reliability, 4),
        "source_run_id": int_or_none(p.source_run_id),
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }
    return payload


def serialize_alert(a: PricingAlert) -> Dict[str, Any]:
    return {
        "id": int(a.alert_id),
        "fixtureId": int(a.fixture_id),
        "alertLevel": int(a.alert_level or 0),
        "alertTitle": a.alert_title or "",
        "mercado": a.mercado or "",
        "jugada": a.jugada or "",
        "cuota": num_or_none(a.cuota, 4),
        "probModelo": num_or_none(a.prob_modelo, 6),
        "probImplicita": num_or_none(a.prob_implicita, 6),
        "probJusta": num_or_none(a.prob_justa, 6),
        "edge": num_or_none(a.edge, 6),
        "confianza": int_or_none(a.confianza),
        "esValueBet": bool(int(a.es_value_bet or 0)),
        "posibleErrorCuota": bool(int(a.posible_error_cuota or 0)),
        "cuotaSospechosa": bool(int(a.cuota_sospechosa or 0)),
        "oportunidadDetectada": bool(int(a.oportunidad_detectada or 0)),
    }


def process_fixture(db: Session, item: FixtureInput, run_id: int) -> Dict[str, Any]:
    upsert_fixture(db, item)
    store_stats_cache(db, item)
    store_odds_snapshot(db, item)

    result = calcular_partido(item.model_dump())
    upsert_prediction(db, result, run_id)
    if int(result.get("alert_level", 0) or 0) > 0:
        store_pricing_alert(db, result, run_id)
    db.flush()
    return result


def coerce_predict_payload(payload: Any) -> IngestRunRequest:
    if isinstance(payload, IngestRunRequest):
        return payload

    if isinstance(payload, dict):
        if "fixtures" in payload and isinstance(payload["fixtures"], list):
            return IngestRunRequest(**payload)
        if "fixture_id" in payload:
            return IngestRunRequest(fixtures=[FixtureInput(**payload)], workflow_name="predict_compat", trigger_type="manual")

    if isinstance(payload, list):
        return IngestRunRequest(
            fixtures=[FixtureInput(**item) for item in payload],
            workflow_name="predict_compat",
            trigger_type="manual",
        )

    raise HTTPException(status_code=422, detail="Payload inválido. Usa {'fixtures': [...]} o un fixture único.")


@app.get("/")
def root():
    return {
        "status": "ok",
        "health": "/health",
        "ingest": "/ingest/run",
        "predict": "/predict",
        "panel_partidos": "/panel/partidos",
        "panel_apuestas_fuertes": "/panel/apuestas-fuertes",
        "panel_resumen": "/panel/resumen",
        "predictions": "/predictions",
        "summary": "/summary",
        "alerts": "/alerts",
        "value_bets": "/value-bets",
    }


@app.get("/health")
def health(db: Session = Depends(get_db)):
    return {
        "status": "ok",
        "version": app.version,
        "cors_origins": allow_origins,
        "fixtures": int(db.scalar(select(func.count()).select_from(Fixture)) or 0),
        "predictions": int(db.scalar(select(func.count()).select_from(Prediction)) or 0),
        "runs": int(db.scalar(select(func.count()).select_from(PredictionRun)) or 0),
        "oddsSnapshots": int(db.scalar(select(func.count()).select_from(OddsSnapshot)) or 0),
        "teamStatsCache": int(db.scalar(select(func.count()).select_from(TeamStatsCache)) or 0),
        "pricingAlerts": int(db.scalar(select(func.count()).select_from(PricingAlert)) or 0),
    }


@app.post("/ingest/run")
def ingest_run(payload: IngestRunRequest, db: Session = Depends(get_db)):
    run = PredictionRun(
        workflow_name=payload.workflow_name,
        trigger_type=payload.trigger_type,
        started_at=utcnow(),
        status="running",
        fixtures_total=len(payload.fixtures),
        fixtures_processed=0,
        fixtures_skipped=0,
        api_requests_used=0,
        notes="",
    )
    db.add(run)
    db.flush()

    processed = 0
    skipped = 0
    results: List[Dict[str, Any]] = []
    errors: List[str] = []

    try:
        for item in payload.fixtures:
            try:
                with db.begin_nested():
                    result = process_fixture(db, item, run.run_id)
                results.append(result)
                processed += 1
            except Exception as exc:
                skipped += 1
                errors.append(f"fixture_id={item.fixture_id}: {exc}")

        run.fixtures_processed = processed
        run.fixtures_skipped = skipped
        run.finished_at = utcnow()
        run.status = "completed" if processed > 0 else "failed"
        run.notes = " | ".join(errors[:10]) if errors else f"Procesados={processed}, omitidos={skipped}"

        db.commit()
        return {
            "run_id": run.run_id,
            "fixtures_total": len(payload.fixtures),
            "processed": processed,
            "skipped": skipped,
            "count": len(results),
            "errors": errors[:10],
        }
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error en ingest/run: {exc}")


@app.post("/predict")
def predict_compat(payload: Dict[str, Any], db: Session = Depends(get_db)):
    request = coerce_predict_payload(payload)
    response = ingest_run(request, db=db)
    return response


@app.get("/predictions")
def get_predictions(
    liga_id: int = Query(0),
    only_value: int = Query(0),
    min_prob: int = Query(0),
    limit: int = Query(1000),
    db: Session = Depends(get_db),
):
    stmt = select(Prediction)
    if liga_id:
        stmt = stmt.where(Prediction.liga_id == liga_id)
    if only_value:
        stmt = stmt.where(Prediction.es_value_bet == 1)
    if min_prob > 0:
        stmt = stmt.where(Prediction.prob_apuesta >= (min_prob / 100.0))

    stmt = stmt.order_by(asc(Prediction.hora), asc(Prediction.liga)).limit(limit)
    rows = db.execute(stmt).scalars().all()
    return {"predictions": [serialize_prediction(r) for r in rows]}


@app.get("/panel/partidos")
def panel_partidos(
    liga_id: int = Query(0),
    only_value: int = Query(0),
    min_prob: int = Query(0),
    limit: int = Query(1000),
    db: Session = Depends(get_db),
):
    data = get_predictions(liga_id=liga_id, only_value=only_value, min_prob=min_prob, limit=limit, db=db)
    return {"partidos": data["predictions"], "count": len(data["predictions"])}


@app.get("/panel/apuestas-fuertes")
def panel_apuestas_fuertes(
    min_prob: int = Query(70),
    only_value: int = Query(0),
    limit: int = Query(500),
    db: Session = Depends(get_db),
):
    stmt = select(Prediction).where(Prediction.prob_apuesta >= (min_prob / 100.0))
    if only_value:
        stmt = stmt.where(Prediction.es_value_bet == 1)

    stmt = stmt.order_by(
        desc(Prediction.es_value_bet),
        desc(Prediction.edge_principal),
        desc(Prediction.prob_apuesta),
        desc(Prediction.confianza),
    ).limit(limit)

    rows = db.execute(stmt).scalars().all()

    apuestas = []
    for p in rows:
        apuestas.append({
            "id": int(p.fixture_id),
            "partido": f"{p.local or ''} vs {p.visitante or ''}",
            "liga": p.liga or "",
            "hora": p.hora.isoformat() if p.hora else None,
            "mercado": none_if_missing(p.mercado_principal),
            "jugada": none_if_missing(p.apuesta_principal),
            "probabilidad": pct_or_none(p.prob_apuesta, 0),
            "cuota": num_or_none(p.cuota_principal, 4),
            "edge": pct_or_none(p.edge_principal, 2),
            "value": bool(int(p.es_value_bet or 0)),
            "confianza": int_or_none(p.confianza),
        })

    return {"apuestas": apuestas}


@app.get("/alerts")
def alerts(limit: int = Query(500), min_level: int = Query(1), db: Session = Depends(get_db)):
    stmt = (
        select(PricingAlert)
        .where(PricingAlert.alert_level >= min_level)
        .order_by(desc(PricingAlert.created_at), desc(PricingAlert.alert_level))
        .limit(limit)
    )
    rows = db.execute(stmt).scalars().all()
    return {"alerts": [serialize_alert(a) for a in rows]}


@app.get("/panel/resumen")
def panel_resumen(liga_id: int = Query(0), only_value: int = Query(0), db: Session = Depends(get_db)):
    stmt = select(Prediction)
    if liga_id:
        stmt = stmt.where(Prediction.liga_id == liga_id)
    if only_value:
        stmt = stmt.where(Prediction.es_value_bet == 1)

    rows = db.execute(stmt).scalars().all()
    partidos = len(rows)
    evaluados = sum(1 for r in rows if (r.prob_apuesta or 0) > 0)
    con_cuota = sum(1 for r in rows if (r.cuota_principal or 0) > 1.0)
    ligas = len({(int(r.liga_id or 0), r.liga or "") for r in rows})
    value_bets = sum(1 for r in rows if int(r.es_value_bet or 0) == 1)
    alertas = int(
        db.scalar(select(func.count()).select_from(PricingAlert).where(PricingAlert.alert_level >= 1)) or 0
    )

    return {
        "partidos": partidos,
        "ligas": ligas,
        "evaluados": evaluados,
        "conCuota": con_cuota,
        "valueBets": value_bets,
        "value_bets": value_bets,
        "alertas": alertas,
    }


@app.get("/summary")
def summary(liga_id: int = Query(0), only_value: int = Query(0), db: Session = Depends(get_db)):
    return panel_resumen(liga_id=liga_id, only_value=only_value, db=db)


@app.get("/value-bets")
def value_bets(min_prob: int = Query(70), limit: int = Query(500), db: Session = Depends(get_db)):
    return panel_apuestas_fuertes(min_prob=min_prob, only_value=1, limit=limit, db=db)
