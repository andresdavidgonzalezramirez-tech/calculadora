from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from zoneinfo import ZoneInfo

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError
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


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("calculadora.api")

def normalize_path_prefix(raw_value: Optional[str]) -> str:
    value = (raw_value or "").strip()
    if not value or value == "/":
        return ""
    if not value.startswith("/"):
        value = f"/{value}"
    return value.rstrip("/")


def get_app_root_path() -> str:
    return normalize_path_prefix(os.getenv("APP_ROOT_PATH", os.getenv("ROOT_PATH", "")))


def get_frontend_base_path() -> str:
    return normalize_path_prefix(os.getenv("FRONTEND_BASE_PATH", get_app_root_path()))


def get_runtime_port() -> int:
    return int(os.getenv("PORT", os.getenv("APP_PORT", "8000")))


def create_app() -> FastAPI:
    api = FastAPI(title="Proyecto Apuestas Reales", version="4.3.0", root_path=get_app_root_path())
    init_db()
    return api


app = create_app()

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

STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    frontend_base_path = get_frontend_base_path()
    if frontend_base_path:
        app.mount(f"{frontend_base_path}/static", StaticFiles(directory=str(STATIC_DIR)), name="static-prefixed")


MARKET_FAMILY_RULES = [
    ("Double chance", ("DC_", "DOUBLE CHANCE", "DOBLE OPORTUNIDAD")),
    ("Exact score", ("EXACT SCORE", "EXACT_SCORE", "MARCADOR EXACTO", "CORRECT SCORE", "SCORE_EXACT")),
    ("Shots on target", ("SHOTONGOAL", "SHOTS ON TARGET", "SOT", "TIROS A PUERTA")),
    ("Corners", ("CORNER", "ESQUINA", "SAQUE DE ESQUINA")),
    ("Cards", ("CARD", "TARJET", "BOOKING", "YELLOW", "AMARILLA", "AMONEST")),
    ("Fouls", ("FOUL", "FALTA")),
    ("Offsides", ("OFFSIDE", "FUERA DE JUEGO")),
    ("Shots", ("SHOT", "TIRO")),
    ("BTTS", ("BTTS", "AMBOS", "BOTH TEAMS TO SCORE")),
    ("1X2", ("1X2", "MATCH_WINNER", "MATCH WINNER")),
    ("Goals", ("OVER", "UNDER", "TEAM_", "GOALS", "TOTAL_GOALS", "ASIAN", "HANDICAP", "GOAL")),
]
SECONDARY_FAMILIES = {"Corners", "Cards", "Shots", "Secondary"}
CORE_FAMILIES = {"1X2", "BTTS", "Double chance", "Goals"}
SECONDARY_VISIBLE_FAMILIES = {"Corners", "Cards"}
MIN_MODEL_PROBABILITY = float(os.getenv("MIN_MODEL_PROBABILITY", "0.20"))
MIN_SIGNAL_DELTA = 0.02
MIN_ACTIONABLE_ODDS = 1.05

VISIBLE_FIXTURE_STATUSES = {"NS"}
HIDDEN_FIXTURE_STATUSES = {"1H", "HT", "2H", "LIVE", "FT", "AET", "PEN", "CANC", "ABD", "PST"}
DISPLAY_TIMEZONE = ZoneInfo(os.getenv("DISPLAY_TIMEZONE", "Europe/Warsaw"))
INGEST_DEFAULT_TIMEZONE = ZoneInfo(os.getenv("INGEST_DEFAULT_TIMEZONE", "Europe/Warsaw"))
UTC_TIMEZONE = ZoneInfo("UTC")
VISIBILITY_FUTURE_WINDOW = timedelta(hours=int(os.getenv("VISIBILITY_FUTURE_WINDOW_HOURS", "72")))

DEFAULT_WORKFLOW_NAME = os.getenv("PANEL_WORKFLOW_NAME", "bankenban_ingest")


def normalize_fixture_status(status: Optional[str]) -> Optional[str]:
    if status is None:
        return None
    normalized = str(status).strip().upper()
    return normalized or None


def visible_fixture_status_expression():
    fixture_status_subquery = (
        select(Fixture.status_short)
        .where(Fixture.fixture_id == Prediction.fixture_id)
        .scalar_subquery()
    )
    return func.upper(func.trim(func.coalesce(fixture_status_subquery, Prediction.estado, "")))


def apply_visible_fixture_filter(stmt):
    status_expr = visible_fixture_status_expression()
    return stmt.where(status_expr.in_(VISIBLE_FIXTURE_STATUSES))


def fixture_datetime_expression():
    fixture_dt_subquery = (
        select(Fixture.fixture_datetime)
        .where(Fixture.fixture_id == Prediction.fixture_id)
        .scalar_subquery()
    )
    return func.coalesce(fixture_dt_subquery, Prediction.hora)


def apply_visibility_time_filter(stmt, reference_now_utc: datetime):
    fixture_dt_expr = fixture_datetime_expression()
    return stmt.where(
        fixture_dt_expr >= reference_now_utc,
        fixture_dt_expr <= (reference_now_utc + VISIBILITY_FUTURE_WINDOW),
    )


def resolve_dashboard_run_id(db: Session, explicit_run_id: Optional[int], workflow_name: str) -> Optional[int]:
    if explicit_run_id is not None and explicit_run_id > 0:
        return explicit_run_id
    return db.scalar(
        select(func.max(PredictionRun.run_id)).where(
            PredictionRun.workflow_name == workflow_name,
            PredictionRun.status == "completed",
        )
    )


def now_utc() -> datetime:
    return datetime.now(ZoneInfo("UTC"))


def coerce_utc_datetime(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            logger.debug("No se pudo parsear fixture datetime como ISO: %s", value)
            return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC_TIMEZONE)
    return value.astimezone(UTC_TIMEZONE)


def is_fixture_visible(status: Optional[str], fixture_dt: Optional[datetime], reference_now_utc: datetime) -> bool:
    normalized_status = normalize_fixture_status(status)
    if normalized_status not in VISIBLE_FIXTURE_STATUSES:
        return False

    dt_utc = coerce_utc_datetime(fixture_dt)
    if dt_utc is not None:
        if dt_utc < reference_now_utc:
            return False
        if dt_utc > reference_now_utc + VISIBILITY_FUTURE_WINDOW:
            return False

    return True



def infer_market_family(code: Optional[str], market: Optional[str], family: Optional[str] = None) -> str:
    token = f"{family or ''} {code or ''} {market or ''}".upper()
    for family, keywords in MARKET_FAMILY_RULES:
        if any(keyword in token for keyword in keywords):
            return family
    return "Secondary"


def classify_market_level(
    model_prob: Optional[float],
    implied_prob: Optional[float],
    ev: Optional[float],
    odds: Optional[float],
) -> str:
    if model_prob is not None and (model_prob or 0) >= 0.50 and (ev is not None and ev > 0):
        return "top_opportunity"
    if model_prob is not None and (model_prob or 0) >= 0.40:
        return "mercado_util"
    if odds is not None:
        return "mercado_detectado"
    return "descartado"


def family_priority(family: str) -> str:
    if family in CORE_FAMILIES:
        return "core"
    if family in SECONDARY_VISIBLE_FAMILIES:
        return "secondary"
    return "experimental"


def build_dashboard_payload(rows: List[Prediction], limit: int) -> Dict[str, Any]:
    rows_sorted = sorted(rows, key=lambda item: item.hora or datetime.max.replace(tzinfo=timezone.utc))
    partidos = [serialize_prediction(row) for row in rows_sorted[:limit]]

    market_telemetry: Dict[str, Dict[str, Dict[str, Any]]] = {}
    all_opportunities: List[Dict[str, Any]] = []
    opportunities_ev: List[Dict[str, Any]] = []
    country_map: Dict[str, Dict[str, Any]] = {}
    match_radar: List[Dict[str, Any]] = []

    for row in rows_sorted:
        fixture_id = int(row.fixture_id)
        fixture_key = str(fixture_id)
        fixture_status_current = normalize_fixture_status(row.estado)
        market_telemetry[fixture_key] = {}

        breakdown = row.market_breakdown if isinstance(row.market_breakdown, list) else []
        included: List[Dict[str, Any]] = []
        excluded: List[Dict[str, Any]] = []
        detected_families = set()

        for index, item in enumerate(breakdown):
            if not isinstance(item, dict):
                continue

            model_prob = num_or_none(item.get("prob"), 6)
            raw_prob = num_or_none(item.get("raw_prob"), 6)
            calibrated_prob = num_or_none(item.get("calibrated_prob"), 6) or model_prob
            odds = num_or_none(item.get("cuota"), 4)
            implied_prob = num_or_none(item.get("probabilidad_implicita"), 6)
            edge = num_or_none(item.get("edge"), 6)
            ev = num_or_none(item.get("ev"), 6)
            calibration_status = str(item.get("calibration_status") or ("ready" if calibrated_prob is not None else "missing"))
            if implied_prob is None and odds is not None and odds > 1:
                implied_prob = round(1.0 / odds, 6)
            break_even_prob = round(1.0 / odds, 6) if odds is not None and odds > 1 else None
            market_fair_prob = num_or_none(item.get("probabilidad_justa"), 6) or implied_prob
            ev = round((calibrated_prob * odds) - 1.0, 6) if (calibrated_prob is not None and odds is not None) else None
            edge = round(calibrated_prob - implied_prob, 6) if (calibrated_prob is not None and implied_prob is not None) else None
            edge_price = round(calibrated_prob - break_even_prob, 6) if calibrated_prob is not None and break_even_prob is not None else None
            edge_market = round(calibrated_prob - market_fair_prob, 6) if calibrated_prob is not None and market_fair_prob is not None else None
            delta_prob = num_or_none(item.get("delta_prob"), 6)
            if delta_prob is None and calibrated_prob is not None and implied_prob is not None:
                delta_prob = round(calibrated_prob - implied_prob, 6)
            market_complete = bool(item.get("market_complete") and calibrated_prob is not None and odds is not None and implied_prob is not None and edge is not None and ev is not None)
            anomaly_flag = bool(calibrated_prob is not None and market_fair_prob is not None and abs(calibrated_prob - market_fair_prob) > 0.20)
            readiness = "ready" if market_complete else "incomplete"
            family = infer_market_family(item.get("code"), item.get("mercado"), item.get("family"))
            detected_families.add(family)
            fam_priority = family_priority(family)
            is_valid_signal = bool(
                calibrated_prob is not None
                and implied_prob is not None
                and abs(calibrated_prob - implied_prob) >= MIN_SIGNAL_DELTA
            )
            publish_allowed_base = bool(
                is_valid_signal
                and ev is not None and ev > 0
                and edge_price is not None and edge_price > 0
                and calibrated_prob is not None and calibrated_prob >= MIN_MODEL_PROBABILITY
                and readiness == "ready"
                and calibration_status == "ready"
                and family in {"1X2", "BTTS", "Double chance", "Goals", "Corners"}
            )
            hide = bool(
                ev is None or ev <= 0
                or edge_price is None or edge_price <= 0
                or not is_valid_signal
                or odds is None or odds <= MIN_ACTIONABLE_ODDS
                or calibration_status != "ready"
                or readiness != "ready"
                or anomaly_flag
                or fam_priority != "core"
            )
            publish_allowed = publish_allowed_base

            opportunity = {
                "fixture_id": fixture_id,
                "partido": f"{row.local or 'Local'} vs {row.visitante or 'Visitante'}",
                "pais": row.pais or "",
                "liga": row.liga or "",
                "hora": row.hora.isoformat() if row.hora else None,
                "fixture_status_current": fixture_status_current,
                "code": item.get("code") or f"MARKET_{index + 1}",
                "market": item.get("mercado") or item.get("code") or "N/D",
                "pick": item.get("jugada") or "N/D",
                "family": family,
                "line": num_or_none(item.get("line"), 2),
                "odds": odds,
                "model_prob": calibrated_prob,
                "raw_prob": raw_prob,
                "calibrated_prob": calibrated_prob,
                "calibration_status": calibration_status,
                "calibrator_version": item.get("calibrator_version"),
                "implied_prob": implied_prob,
                "market_fair_prob": market_fair_prob,
                "break_even_prob": break_even_prob,
                "delta_prob": delta_prob,
                "edge": edge,
                "edge_price": edge_price,
                "edge_market": edge_market,
                "ev": ev,
                "close_probability": num_or_none(item.get("close_probability"), 6) if calibrated_prob is not None else None,
                "market_complete": market_complete,
                "completeness_reason": None if market_complete else "missing_pricing_or_probability",
                "flags": {
                    "ev_plus": bool(ev is not None and ev > 0),
                    "value": bool(item.get("value") or (edge_price is not None and edge_price > 0)),
                    "strong_signal": str(item.get("signal_tier") or "").startswith("strong"),
                    "secondary_market": family in SECONDARY_FAMILIES,
                },
                "source": "market_breakdown",
                "reason_inclusion": "market_breakdown",
                "signal_tier": item.get("signal_tier"),
                "volatility": num_or_none(item.get("volatility"), 4),
                "fragility": num_or_none(item.get("fragility"), 4),
                "reliability": num_or_none(item.get("reliability"), 4),
                "stability": num_or_none(item.get("stability"), 4),
                "family_priority": fam_priority,
                "is_valid_signal": is_valid_signal,
                "signal_degenerate": not is_valid_signal,
            }
            opportunity["market_level"] = classify_market_level(model_prob, implied_prob, ev, odds)
            opportunity["visible_en_panel"] = not hide
            opportunity["recomendado"] = publish_allowed
            opportunity["arbitrage"] = bool(item.get("arbitrage") is True)
            opportunity["readiness"] = readiness
            opportunity["anomaly_flag"] = anomaly_flag
            opportunity["publish_allowed"] = publish_allowed
            opportunity["publish_allowed_base"] = publish_allowed_base
            opportunity["visibility_allowed"] = not hide
            opportunity["is_strong_pick"] = bool(calibrated_prob is not None and calibrated_prob >= MIN_MODEL_PROBABILITY)
            opportunity["is_positive_bet"] = bool(ev is not None and ev > 0)
            opportunity["is_recommended_pick"] = publish_allowed
            opportunity["probability_tier"] = (
                "elite" if calibrated_prob is not None and calibrated_prob >= 0.75
                else "high" if calibrated_prob is not None and calibrated_prob >= MIN_MODEL_PROBABILITY
                else "medium" if calibrated_prob is not None and calibrated_prob >= 0.50
                else "low"
            )
            opportunity["hidden_reason"] = None if opportunity["visibility_allowed"] else "hidden_by_math_gating"
            opportunity["blocking_reason"] = None if (publish_allowed and opportunity["visibility_allowed"]) else "math_gating_blocked"
            opportunity["label"] = (
                "Arbitraje detectado"
                if opportunity["arbitrage"]
                else "Pick calculado"
                if opportunity["recomendado"]
                else "Pricing incompleto"
                if not market_complete
                else "Mercado detectado"
            )

            market_telemetry[fixture_key][opportunity["code"]] = opportunity
            all_opportunities.append(opportunity)

            is_publishable = bool(opportunity["visibility_allowed"] and opportunity["publish_allowed"])
            opportunity["publishable"] = is_publishable

            if publish_allowed and is_publishable:
                opportunities_ev.append(opportunity)
                included.append(opportunity)
            else:
                if model_prob is None:
                    opportunity["reason_discard"] = "missing_model_probability"
                elif model_prob < MIN_MODEL_PROBABILITY:
                    opportunity["reason_discard"] = f"below_min_model_probability_{int(MIN_MODEL_PROBABILITY * 100)}"
                if not market_complete:
                    opportunity["reason_discard"] = "market_incomplete"
                excluded.append(opportunity)

        country = row.pais or "N/D"
        league = row.liga or "N/D"
        info = country_map.setdefault(country, {"pais": country, "partidos": 0, "ev_plus": 0, "value_bets": 0, "_ligas": {}})
        info["partidos"] += 1
        info["ev_plus"] += sum(1 for item in included if item["flags"]["ev_plus"])
        info["value_bets"] += sum(1 for item in included if item["flags"]["value"])
        league_info = info["_ligas"].setdefault(league, {"liga": league, "partidos": 0, "ev_plus": 0, "value_bets": 0})
        league_info["partidos"] += 1
        league_info["ev_plus"] += sum(1 for item in included if item["flags"]["ev_plus"])
        league_info["value_bets"] += sum(1 for item in included if item["flags"]["value"])

        match_radar.append({
            "fixture_id": fixture_id,
            "liga": row.liga or "",
            "pais": row.pais or "",
            "hora": row.hora.isoformat() if row.hora else None,
            "fixture_status_current": fixture_status_current,
            "equipos": {"local": row.local or "", "visitante": row.visitante or ""},
            "familias_detectadas": sorted(detected_families),
            "oportunidades_incluidas": included,
            "oportunidades_excluidas": excluded,
        })

    paises = []
    for country in sorted(country_map):
        item = country_map[country]
        leagues = sorted(item.pop("_ligas").values(), key=lambda league_row: league_row["liga"])
        item["ligas"] = leagues
        paises.append(item)

    opportunities_ev_sorted = sorted(opportunities_ev, key=lambda item: (item.get("close_probability") or -1, item.get("ev") or -999), reverse=True)[:limit]

    level_a_top_opportunities = sorted(
        [item for item in all_opportunities if item.get("market_level") == "top_opportunity" and item.get("recomendado")],
        key=lambda item: (item.get("close_probability") or -1, item.get("edge") or -999),
        reverse=True,
    )[:limit]
    level_b_useful_market = sorted(
        [item for item in all_opportunities if item.get("market_level") == "mercado_util" and item.get("recomendado")],
        key=lambda item: (item.get("close_probability") or -1, item.get("edge") or -999),
        reverse=True,
    )[:limit]
    level_c_detected_market = sorted(
        [item for item in all_opportunities if item.get("market_level") == "mercado_detectado"],
        key=lambda item: (item.get("close_probability") or -1, item.get("odds") or -999),
        reverse=True,
    )[:limit]

    families_payload: Dict[str, List[Dict[str, Any]]] = {}
    for item in all_opportunities:
        family = str(item.get("family") or "Secondary")
        families_payload.setdefault(family.lower(), []).append(item)
    top_by_family_sorted = {
        family: sorted(items, key=lambda item: (item.get("close_probability") or -1, item.get("ev") or -999), reverse=True)[:50]
        for family, items in families_payload.items()
    }

    summary = {
        "total_paises": len(paises),
        "total_ligas": len({(row.liga_id, row.liga) for row in rows_sorted}),
        "total_partidos_proximos": len(rows_sorted),
        "total_mercados_analizados": len(all_opportunities),
        "total_senales": sum(len(row.apuestas_fuertes or []) for row in rows_sorted),
        "total_oportunidades_ev_plus": len(opportunities_ev_sorted),
        "total_apuestas_fuertes": sum(1 for item in level_a_top_opportunities if item["flags"]["strong_signal"]),
        "total_value_bets": sum(1 for item in level_a_top_opportunities if item["flags"]["value"]),
    }

    return {
        "generated_at": utcnow().isoformat(),
        "partidos": partidos,
        "market_telemetry": market_telemetry,
        "oportunidades_ev": opportunities_ev_sorted,
        "top_opportunities": level_a_top_opportunities,
        "top_by_family": top_by_family_sorted,
        "market_levels": {
            "top_opportunities": level_a_top_opportunities,
            "mercado_util": level_b_useful_market,
            "mercado_detectado": level_c_detected_market,
        },
        "arbitrage_opportunities": [item for item in all_opportunities if item.get("arbitrage")][:limit],
        "apuestas_fuertes": [item for row in rows_sorted for item in (row.apuestas_fuertes or [])][:limit],
        "paises": paises,
        "match_radar": match_radar[:limit],
        "summary": summary,
        "families": families_payload,
        "corners_odds_available": bool(families_payload.get("corners")),
        "cards_odds_available": bool(families_payload.get("cards")),
        "filters": {
            "min_model_probability": MIN_MODEL_PROBABILITY,
        },
    }


def parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo:
            return value.astimezone(timezone.utc)
        localized = value.replace(tzinfo=INGEST_DEFAULT_TIMEZONE)
        return localized.astimezone(timezone.utc)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        raw = raw.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo:
                return dt.astimezone(timezone.utc)
            localized = dt.replace(tzinfo=INGEST_DEFAULT_TIMEZONE)
            return localized.astimezone(timezone.utc)
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

    cf_home: Optional[float] = None
    ca_home: Optional[float] = None
    cf_away: Optional[float] = None
    ca_away: Optional[float] = None

    yf_home: Optional[float] = None
    yf_away: Optional[float] = None

    shots_home: Optional[float] = None
    shots_away: Optional[float] = None
    shots_on_target_home: Optional[float] = None
    shots_on_target_away: Optional[float] = None

    form_home: float = 0
    form_away: float = 0
    data_quality: float = 0.8

    home_stats: Dict[str, Any] = Field(default_factory=dict)
    away_stats: Dict[str, Any] = Field(default_factory=dict)
    home_recent_form: List[Dict[str, Any]] = Field(default_factory=list)
    away_recent_form: List[Dict[str, Any]] = Field(default_factory=list)
    head_to_head: List[Dict[str, Any]] = Field(default_factory=list)
    odds: Dict[str, Any] = Field(default_factory=dict)
    market_catalog: Any = Field(default_factory=list)
    families: Dict[str, Any] = Field(default_factory=dict)
    feature_availability: Dict[str, Any] = Field(default_factory=dict)
    market_blocking_reasons: Dict[str, Any] = Field(default_factory=dict)
    advanced_sample_counts: Dict[str, Any] = Field(default_factory=dict)
    request_meta: Dict[str, Any] = Field(default_factory=dict)
    corners_publish_allowed: Optional[bool] = None
    cards_publish_allowed: Optional[bool] = None
    transport_allowed: Optional[bool] = None
    collection_meta: Dict[str, Any] = Field(default_factory=dict)
    candidate_picks: List[Dict[str, Any]] = Field(default_factory=list)

class IngestRunRequest(BaseModel):
    fixtures: List[FixtureInput] = Field(default_factory=list)
    workflow_name: str = "bankenban_ingest"
    trigger_type: str = "schedule"
    persist: bool = True


class PredictPickOut(BaseModel):
    fixture_id: int
    market_key: str
    market: str
    pick: str
    family: str = "Secondary"
    family_priority: str = "experimental"
    secondary_market: bool = True
    odds: Optional[float] = None
    implied_prob: Optional[float] = None
    calibrated_prob: Optional[float] = None
    edge_price: Optional[float] = None
    ev: Optional[float] = None
    confidence_score: float = 0.0
    market_complete: bool = False
    pricing_complete: bool = False
    readiness: str = "incomplete"
    anomaly_flag: bool = False
    evaluation_attempted: bool = True
    pick_status: Literal["publishable_core", "publishable_secondary", "traceable_only", "invalid"] = "invalid"
    rank_score: float = 0.0
    reason_discard: Optional[str] = None
    blocking_reason: Optional[str] = None
    contradiction_flags: List[str] = Field(default_factory=list)


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
    existing.market_breakdown = result.get("market_breakdown") or []

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


def serialize_prediction(p: Prediction, fixture_status_current: Optional[str] = None) -> Dict[str, Any]:
    status_current = normalize_fixture_status(fixture_status_current) or normalize_fixture_status(p.estado)

    payload = {
        "id": int(p.fixture_id),
        "fixture_id": int(p.fixture_id),
        "liga_id": int_or_none(p.liga_id),
        "ligaId": int_or_none(p.liga_id),
        "liga": none_if_missing(p.liga),
        "pais": none_if_missing(p.pais),
        "hora": p.hora.isoformat() if p.hora else None,
        "estado": none_if_missing(p.estado),
        "fixture_status_current": status_current,
        "fixtureStatusCurrent": status_current,
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


def _truthy_legacy(value: Any) -> bool:
    return bool(value is True or str(value).strip().lower() in {"1", "true", "yes"})


def _extract_candidate_picks(item: FixtureInput) -> List[Dict[str, Any]]:
    raw_candidates = item.candidate_picks if isinstance(item.candidate_picks, list) else []
    if raw_candidates:
        return [candidate for candidate in raw_candidates if isinstance(candidate, dict)]

    market_catalog = item.market_catalog if isinstance(item.market_catalog, list) else []
    catalog_candidates = [candidate for candidate in market_catalog if isinstance(candidate, dict)]
    if catalog_candidates:
        return catalog_candidates

    fallback: List[Dict[str, Any]] = []
    for key, odd_value in (item.odds or {}).items():
        fallback.append(
            {
                "market_key": str(key).upper(),
                "market": str(key).upper(),
                "pick": str(key).upper(),
                "odds": odd_value,
            }
        )
    return fallback


def _classify_pick(candidate: Dict[str, Any], fixture_id: int) -> PredictPickOut:
    odds = num_or_none(candidate.get("odds") or candidate.get("cuota"), 6)
    implied_prob = num_or_none(candidate.get("implied_prob"), 6)
    if implied_prob is None and odds is not None and odds > 1:
        implied_prob = round(1.0 / odds, 6)
    calibrated_prob = num_or_none(candidate.get("calibrated_prob") or candidate.get("prob") or candidate.get("model_prob"), 6)
    market_complete = bool(candidate.get("market_complete")) or bool(odds is not None and implied_prob is not None and calibrated_prob is not None)
    pricing_complete = bool(odds is not None and implied_prob is not None)
    readiness = str(candidate.get("readiness") or ("ready" if market_complete else "incomplete")).lower()
    anomaly_flag = bool(candidate.get("anomaly_flag"))
    edge_price = round(calibrated_prob - implied_prob, 6) if calibrated_prob is not None and implied_prob is not None else None
    ev = round((calibrated_prob * odds) - 1.0, 6) if calibrated_prob is not None and odds is not None else None
    family = infer_market_family(candidate.get("market_key") or candidate.get("code"), candidate.get("market"), candidate.get("family"))
    fam_priority = family_priority(family)
    secondary_market = bool(candidate.get("secondary_market", family in SECONDARY_FAMILIES))
    confidence_score = num_or_none(candidate.get("confidence_score") or candidate.get("confidence"), 4) or 0.0
    evaluation_attempted = bool(candidate.get("evaluation_attempted", True))

    mathematically_valid = bool(
        odds is not None
        and odds > MIN_ACTIONABLE_ODDS
        and implied_prob is not None
        and calibrated_prob is not None
        and market_complete
        and readiness == "ready"
        and not anomaly_flag
    )
    publishable_strict = bool(
        mathematically_valid
        and ev is not None and ev > 0
        and edge_price is not None and edge_price > 0
        and implied_prob is not None and calibrated_prob is not None and abs(calibrated_prob - implied_prob) >= MIN_SIGNAL_DELTA
    )
    if publishable_strict and fam_priority == "core" and not secondary_market:
        status = "publishable_core"
    elif publishable_strict:
        status = "publishable_secondary"
    elif fixture_id and (candidate.get("market_key") or candidate.get("code")) and evaluation_attempted:
        status = "traceable_only"
    else:
        status = "invalid"

    contradiction_flags: List[str] = []
    if _truthy_legacy(candidate.get("publish_allowed")) and ev is None:
        contradiction_flags.append("publish_allowed_without_ev")
    if _truthy_legacy(candidate.get("visible_en_panel")) and odds is None:
        contradiction_flags.append("visible_en_panel_without_odds")
    if _truthy_legacy(candidate.get("is_strong_pick")) and not market_complete:
        contradiction_flags.append("is_strong_pick_without_market_complete")
    if _truthy_legacy(candidate.get("recommended")) and (edge_price is None or edge_price <= 0):
        contradiction_flags.append("recommended_without_positive_edge")

    blocking_reason = None
    reason_discard = None
    if status in {"traceable_only", "invalid"}:
        reason_discard = "failed_publishable_rules"
        blocking_reason = "math_gating_blocked"

    core_bonus = 0.2 if status == "publishable_core" else 0.0
    anomaly_penalty = 1.0 if anomaly_flag else 0.0
    fragility_penalty = 0.8 if not pricing_complete else 0.0
    rank_score = round(
        ((ev or 0.0) * 100.0) + ((edge_price or 0.0) * 50.0) + (confidence_score * 10.0) + core_bonus - anomaly_penalty - fragility_penalty,
        4,
    )

    return PredictPickOut(
        fixture_id=fixture_id,
        market_key=str(candidate.get("market_key") or candidate.get("code") or "N/D"),
        market=str(candidate.get("market") or candidate.get("mercado") or "N/D"),
        pick=str(candidate.get("pick") or candidate.get("jugada") or "N/D"),
        family=family,
        family_priority=fam_priority,
        secondary_market=secondary_market,
        odds=odds,
        implied_prob=implied_prob,
        calibrated_prob=calibrated_prob,
        edge_price=edge_price,
        ev=ev,
        confidence_score=confidence_score,
        market_complete=market_complete,
        pricing_complete=pricing_complete,
        readiness=readiness,
        anomaly_flag=anomaly_flag,
        evaluation_attempted=evaluation_attempted,
        pick_status=status,
        rank_score=rank_score,
        reason_discard=reason_discard,
        blocking_reason=blocking_reason,
        contradiction_flags=contradiction_flags,
    )


def _predict_rich_response(payload: IngestRunRequest) -> Dict[str, Any]:
    fixtures_payload: List[Dict[str, Any]] = []
    for fixture in payload.fixtures:
        picks = [_classify_pick(candidate, fixture.fixture_id).model_dump() for candidate in _extract_candidate_picks(fixture)]
        picks_sorted = sorted(picks, key=lambda row: row.get("rank_score") or -999, reverse=True)
        fixtures_payload.append(
            {
                "fixture_id": fixture.fixture_id,
                "fixture_summary": {
                    "country": fixture.country,
                    "league_name": fixture.league_name,
                    "home_team_name": fixture.home_team_name,
                    "away_team_name": fixture.away_team_name,
                    "fixture_datetime": fixture.fixture_datetime,
                },
                "markets_evaluated": len(picks),
                "publishable_core": [pick for pick in picks if pick["pick_status"] == "publishable_core"],
                "publishable_secondary": [pick for pick in picks if pick["pick_status"] == "publishable_secondary"],
                "traceable_only": [pick for pick in picks if pick["pick_status"] == "traceable_only"],
                "invalid": [pick for pick in picks if pick["pick_status"] == "invalid"],
                "top_picks": picks_sorted[:10],
                "reasons_discard": sorted({pick["reason_discard"] for pick in picks if pick.get("reason_discard")}),
                "contradictions_detected": [pick for pick in picks if pick.get("contradiction_flags")],
                "family_summary": {
                    "families_with_publishable": sorted({pick["family"] for pick in picks if pick["pick_status"].startswith("publishable")}),
                    "families_empty": sorted({pick["family"] for pick in picks if not pick["pick_status"].startswith("publishable")}),
                },
            }
        )
    return {
        "workflow_name": payload.workflow_name,
        "fixtures_total": len(payload.fixtures),
        "fixtures": fixtures_payload,
    }


def _expected_type_for_validation_error(error_type: str) -> str:
    if error_type in {"float_type", "float_parsing", "int_type", "int_parsing"}:
        return "number"
    if error_type == "missing":
        return "required"
    return "valid_value"


def _format_pydantic_validation_error(exc: ValidationError) -> List[Dict[str, Any]]:
    invalid_fields: List[Dict[str, Any]] = []
    for error in exc.errors():
        loc = ".".join(str(part) for part in error.get("loc", ()))
        value = error.get("input")
        error_type = str(error.get("type", "unknown"))
        message = str(error.get("msg", "Validation error"))
        expected_type = _expected_type_for_validation_error(error_type)
        logger.warning(
            "Predict payload validation failed field=%s value=%r expected=%s error_type=%s message=%s",
            loc,
            value,
            expected_type,
            error_type,
            message,
        )
        invalid_fields.append(
            {
                "field": loc,
                "value": value,
                "expected": expected_type,
                "error_type": error_type,
                "message": message,
            }
        )
    return invalid_fields


def _validation_error_response(exc: ValidationError, message: str) -> JSONResponse:
    invalid_fields = _format_pydantic_validation_error(exc)
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "type": "validation_error",
                "message": message,
                "invalid_fields": invalid_fields,
            }
        },
    )


@app.get("/")
def root():
    if STATIC_DIR.joinpath("index.html").exists():
        frontend_base_path = get_frontend_base_path()
        static_prefix = f"{frontend_base_path}/static" if frontend_base_path else "/static"
        html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        html = html.replace("__FRONTEND_BASE_PATH__", frontend_base_path)
        html = html.replace("__STATIC_STYLES_URL__", f"{static_prefix}/styles.css")
        html = html.replace("__STATIC_APP_URL__", f"{static_prefix}/app.js")
        return HTMLResponse(content=html)
    return {
        "status": "ok",
        "health": "/health",
        "ingest": "/ingest/run",
        "predict": "/predict",
        "panel_partidos": "/panel/partidos",
        "panel_apuestas_fuertes": "/panel/apuestas-fuertes",
        "panel_resumen": "/panel/resumen",
        "panel_dashboard": "/panel/dashboard",
        "predictions": "/predictions",
        "summary": "/summary",
        "alerts": "/alerts",
        "value_bets": "/value-bets",
    }


@app.exception_handler(HTTPException)
def http_exception_handler(_: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"type": "http_error", "detail": exc.detail}},
    )


@app.exception_handler(RequestValidationError)
def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": {"type": "validation_error", "detail": exc.errors()}},
    )


@app.exception_handler(ValidationError)
def pydantic_validation_exception_handler(_: Request, exc: ValidationError):
    return _validation_error_response(exc, "Payload inválido")


@app.exception_handler(Exception)
def unhandled_exception_handler(_: Request, exc: Exception):
    logger.exception("Unhandled server error")
    return JSONResponse(
        status_code=500,
        content={"error": {"type": "server_error", "detail": "Internal server error"}},
    )


@app.get("/health")
def health(db: Session = Depends(get_db)):
    return {
        "status": "ok",
        "version": app.version,
        "root_path": app.root_path,
        "frontend_base_path": get_frontend_base_path(),
        "root_path_source": "APP_ROOT_PATH/ROOT_PATH",
        "app_root_path": get_app_root_path(),
        "frontend_base_path_expected": get_frontend_base_path(),
        "port": get_runtime_port(),
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
        persisted_predictions = int(
            db.scalar(
                select(func.count()).select_from(Prediction).where(Prediction.source_run_id == run.run_id)
            )
            or 0
        )
        logger.info(
            "Ingest finalizado run_id=%s total=%s procesados=%s omitidos=%s persistidos=%s",
            run.run_id,
            len(payload.fixtures),
            processed,
            skipped,
            persisted_predictions,
        )
        return {
            "run_id": run.run_id,
            "fixtures_total": len(payload.fixtures),
            "processed": processed,
            "skipped": skipped,
            "persisted": persisted_predictions,
            "count": len(results),
            "errors": errors[:10],
        }
    except Exception as exc:
        db.rollback()
        logger.exception("Error en ingest/run")
        raise HTTPException(status_code=500, detail="Error interno en ingest/run")


@app.post("/predict")
def predict_compat(payload: Any = Body(...), db: Session = Depends(get_db)):
    try:
        request = coerce_predict_payload(payload)
        response = ingest_run(request, db=db)
        response["classification"] = _predict_rich_response(request)
        return response
    except ValidationError as exc:
        return _validation_error_response(exc, "Payload inválido para /predict")


@app.post("/panel/cleanup-old-records")
def cleanup_old_records(
    keep_recent_hours: int = Query(24, ge=24, le=24 * 90),
    db: Session = Depends(get_db),
):
    cutoff = utcnow() - timedelta(hours=keep_recent_hours)
    old_run_ids = [
        run_id
        for (run_id,) in db.execute(
            select(PredictionRun.run_id).where(
                PredictionRun.finished_at.is_not(None),
                PredictionRun.finished_at < cutoff,
            )
        ).all()
    ]
    deleted_predictions = 0
    if old_run_ids:
        deleted_predictions = db.query(Prediction).filter(Prediction.source_run_id.in_(old_run_ids)).delete(synchronize_session=False)
    deleted_predictions_by_age = db.query(Prediction).filter(Prediction.updated_at.is_not(None), Prediction.updated_at < cutoff).delete(synchronize_session=False)
    deleted_predictions += int(deleted_predictions_by_age or 0)
    deleted_alerts = db.query(PricingAlert).filter(PricingAlert.created_at < cutoff).delete()
    deleted_runs = db.query(PredictionRun).filter(PredictionRun.finished_at.is_not(None), PredictionRun.finished_at < cutoff).delete()
    deleted_snapshots = db.query(OddsSnapshot).filter(OddsSnapshot.snapshot_at < cutoff).delete()
    db.commit()
    return {
        "cutoff": cutoff.isoformat(),
        "deleted": {
            "predictions": int(deleted_predictions or 0),
            "pricing_alerts": int(deleted_alerts or 0),
            "prediction_runs": int(deleted_runs or 0),
            "odds_snapshots": int(deleted_snapshots or 0),
        },
        "guardrails": "Predictions y fixtures recientes no se eliminan en esta limpieza.",
    }


@app.get("/predictions")
def get_predictions(
    liga_id: int = Query(0, ge=0),
    only_value: int = Query(0, ge=0, le=1),
    min_prob: int = Query(0, ge=0, le=100),
    limit: int = Query(200, ge=1, le=2000),
    visible_only: int = Query(0, ge=0, le=1),
    db: Session = Depends(get_db),
):
    reference_now_utc = now_utc()
    stmt = select(
        Prediction,
        visible_fixture_status_expression().label("fixture_status_current"),
        fixture_datetime_expression().label("fixture_datetime_current"),
    )
    if liga_id:
        stmt = stmt.where(Prediction.liga_id == liga_id)
    if only_value:
        stmt = stmt.where(Prediction.es_value_bet == 1)
    if min_prob > 0:
        stmt = stmt.where(Prediction.prob_apuesta >= (min_prob / 100.0))

    if visible_only:
        stmt = apply_visible_fixture_filter(stmt)
        stmt = apply_visibility_time_filter(stmt, reference_now_utc)

    stmt = stmt.order_by(asc(Prediction.hora), asc(Prediction.liga)).limit(limit)
    rows = db.execute(stmt).all()
    predictions: List[Dict[str, Any]] = []
    for prediction, fixture_status, fixture_dt in rows:
        if not is_fixture_visible(fixture_status, fixture_dt, reference_now_utc):
            continue
        predictions.append(serialize_prediction(prediction, fixture_status))
        if len(predictions) >= limit:
            break
    return {"predictions": predictions}


@app.get("/panel/partidos")
def panel_partidos(
    liga_id: int = Query(0, ge=0),
    only_value: int = Query(0, ge=0, le=1),
    min_prob: int = Query(0, ge=0, le=100),
    limit: int = Query(200, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    data = get_predictions(liga_id=liga_id, only_value=only_value, min_prob=min_prob, limit=limit, visible_only=1, db=db)
    return {"partidos": data["predictions"], "count": len(data["predictions"])}


@app.get("/panel/apuestas-fuertes")
def panel_apuestas_fuertes(
    min_prob: int = Query(70, ge=0, le=100),
    only_value: int = Query(0, ge=0, le=1),
    limit: int = Query(300, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    reference_now_utc = now_utc()
    stmt = apply_visible_fixture_filter(
        select(
            Prediction,
            visible_fixture_status_expression().label("fixture_status_current"),
            fixture_datetime_expression().label("fixture_datetime_current"),
        ).where(Prediction.prob_apuesta >= (min_prob / 100.0))
    )
    stmt = apply_visibility_time_filter(stmt, reference_now_utc)
    if only_value:
        stmt = stmt.where(Prediction.es_value_bet == 1)

    stmt = stmt.order_by(
        desc(Prediction.es_value_bet),
        desc(Prediction.edge_principal),
        desc(Prediction.prob_apuesta),
        desc(Prediction.confianza),
    ).limit(limit)

    rows = db.execute(stmt).all()
    apuestas = []
    for p, fixture_status, fixture_dt in rows:
        if not is_fixture_visible(fixture_status, fixture_dt, reference_now_utc):
            continue
        apuestas.append({
            "id": int(p.fixture_id),
            "partido": f"{p.local or ''} vs {p.visitante or ''}",
            "liga": p.liga or "",
            "hora": p.hora.isoformat() if p.hora else None,
            "fixture_status_current": normalize_fixture_status(fixture_status) or normalize_fixture_status(p.estado),
            "mercado": none_if_missing(p.mercado_principal),
            "jugada": none_if_missing(p.apuesta_principal),
            "probabilidad": pct_or_none(p.prob_apuesta, 0),
            "cuota": num_or_none(p.cuota_principal, 4),
            "edge": pct_or_none(p.edge_principal, 2),
            "value": bool(int(p.es_value_bet or 0)),
            "confianza": int_or_none(p.confianza),
        })

    return {"apuestas": apuestas}


@app.get("/panel/dashboard")
def panel_dashboard(
    request: Request,
    liga_id: int = Query(0, ge=0),
    only_value: int = Query(0, ge=0, le=1),
    run_id: Optional[int] = Query(None, ge=1),
    workflow_name: str = Query(DEFAULT_WORKFLOW_NAME, min_length=1),
    limit: int = Query(300, ge=1, le=3000),
    db: Session = Depends(get_db),
):
    logger.info(
        "Dashboard request path=%s query=%s run_id=%s workflow=%s limit=%s frontend_base_path=%s",
        request.url.path,
        str(request.url.query),
        run_id,
        workflow_name,
        limit,
        get_frontend_base_path(),
    )
    reference_now_utc = now_utc()
    selected_run_id = resolve_dashboard_run_id(db, run_id, workflow_name)
    stmt = select(
        Prediction,
        visible_fixture_status_expression().label("fixture_status_current"),
        fixture_datetime_expression().label("fixture_datetime_current"),
    )
    if selected_run_id is not None:
        stmt = stmt.where(Prediction.source_run_id == selected_run_id)
    if liga_id:
        stmt = stmt.where(Prediction.liga_id == liga_id)
    if only_value:
        stmt = stmt.where(Prediction.es_value_bet == 1)

    stmt = stmt.order_by(asc(Prediction.hora), asc(Prediction.liga)).limit(limit)
    rows = db.execute(stmt).all()
    visible_rows: List[Prediction] = []
    hidden_rows: List[Prediction] = []
    for prediction, fixture_status, fixture_dt in rows:
        prediction.estado = normalize_fixture_status(fixture_status) or prediction.estado
        if is_fixture_visible(fixture_status, fixture_dt, reference_now_utc):
            visible_rows.append(prediction)
        else:
            hidden_rows.append(prediction)

    payload_rows = visible_rows if visible_rows else [*visible_rows, *hidden_rows]
    payload = build_dashboard_payload(payload_rows[:limit], limit=limit)
    payload["selected_run_id"] = int(selected_run_id) if selected_run_id is not None else None
    payload["workflow_name"] = workflow_name
    payload["debug"] = {
        "run_id": int(selected_run_id) if selected_run_id is not None else None,
        "fixtures_total": len(rows),
        "fixtures_visible": len(visible_rows),
        "fixtures_hidden": len(hidden_rows),
        "processed": len(payload_rows),
        "skipped": max(0, len(rows) - len(payload_rows)),
    }
    logger.info(
        "Dashboard read path=%s root_path=%s run_id=%s workflow=%s queried=%s visible=%s hidden=%s returned=%s",
        request.url.path,
        app.root_path,
        payload["selected_run_id"],
        workflow_name,
        len(rows),
        len(visible_rows),
        len(hidden_rows),
        len(payload_rows[:limit]),
    )
    logger.debug(
        "Dashboard headers host=%s x_forwarded_prefix=%s x_forwarded_proto=%s",
        request.headers.get("host"),
        request.headers.get("x-forwarded-prefix"),
        request.headers.get("x-forwarded-proto"),
    )
    return payload


@app.get("/alerts")
def alerts(limit: int = Query(500, ge=1, le=5000), min_level: int = Query(1, ge=0, le=3), db: Session = Depends(get_db)):
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
    reference_now_utc = now_utc()
    stmt = apply_visible_fixture_filter(
        select(
            Prediction,
            visible_fixture_status_expression().label("fixture_status_current"),
            fixture_datetime_expression().label("fixture_datetime_current"),
        )
    )
    stmt = apply_visibility_time_filter(stmt, reference_now_utc)
    if liga_id:
        stmt = stmt.where(Prediction.liga_id == liga_id)
    if only_value:
        stmt = stmt.where(Prediction.es_value_bet == 1)

    rows = db.execute(stmt).all()
    visible_rows = [
        prediction
        for prediction, fixture_status, fixture_dt in rows
        if is_fixture_visible(fixture_status, fixture_dt, reference_now_utc)
    ]
    partidos = len(visible_rows)
    evaluados = sum(1 for r in visible_rows if (r.prob_apuesta or 0) > 0)
    con_cuota = sum(1 for r in visible_rows if (r.cuota_principal or 0) > 1.0)
    ligas = len({(int(r.liga_id or 0), r.liga or "") for r in visible_rows})
    value_bets = sum(1 for r in visible_rows if int(r.es_value_bet or 0) == 1)
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
def summary(liga_id: int = Query(0, ge=0), only_value: int = Query(0, ge=0, le=1), db: Session = Depends(get_db)):
    return panel_resumen(liga_id=liga_id, only_value=only_value, db=db)


@app.get("/value-bets")
def value_bets(min_prob: int = Query(70, ge=0, le=100), limit: int = Query(500, ge=1, le=2000), db: Session = Depends(get_db)):
    return panel_apuestas_fuertes(min_prob=min_prob, only_value=1, limit=limit, db=db)
