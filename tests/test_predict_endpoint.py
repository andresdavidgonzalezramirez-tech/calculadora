import os
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_predict_endpoint.db")
sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import db
import main


class DummySession:
    pass


def base_fixture():
    return {
        "fixture_id": 1001,
        "league_id": 140,
        "league_name": "La Liga",
        "country": "Spain",
        "season": 2026,
        "fixture_datetime": "2026-04-01T18:00:00Z",
        "status_short": "NS",
        "home_team_id": 1,
        "away_team_id": 2,
        "home_team_name": "Home",
        "away_team_name": "Away",
    }


def _client_with_ingest_stub(monkeypatch):
    captured = {}

    def fake_ingest_run(payload, db):
        captured["payload"] = payload
        return {
            "fixtures_total": len(payload.fixtures),
            "processed": len(payload.fixtures),
            "skipped": 0,
        }

    monkeypatch.setattr(main, "ingest_run", fake_ingest_run)

    def override_get_db():
        yield DummySession()

    main.app.dependency_overrides[main.get_db] = override_get_db
    client = TestClient(main.app)
    return client, captured


def test_predict_accepts_valid_payload(monkeypatch):
    client, captured = _client_with_ingest_stub(monkeypatch)
    response = client.post("/predict", json={"fixtures": [base_fixture()]})

    assert response.status_code == 200
    assert response.json()["fixtures_total"] == 1
    assert captured["payload"].fixtures[0].fixture_id == 1001



def test_predict_accepts_none_advanced_numeric_stats_without_zero_fill(monkeypatch):
    client, captured = _client_with_ingest_stub(monkeypatch)
    fixture = base_fixture()
    for field in [
        "cf_home",
        "ca_home",
        "cf_away",
        "ca_away",
        "yf_home",
        "yf_away",
        "shots_home",
        "shots_away",
        "shots_on_target_home",
        "shots_on_target_away",
    ]:
        fixture[field] = None

    response = client.post("/predict", json={"fixtures": [fixture]})

    assert response.status_code == 200
    normalized = captured["payload"].fixtures[0]
    assert normalized.cf_home is None
    assert normalized.ca_home is None
    assert normalized.cf_away is None
    assert normalized.ca_away is None
    assert normalized.yf_home is None
    assert normalized.yf_away is None
    assert normalized.shots_home is None
    assert normalized.shots_away is None
    assert normalized.shots_on_target_home is None
    assert normalized.shots_on_target_away is None



def test_predict_incomplete_payload_returns_422(monkeypatch):
    client, _ = _client_with_ingest_stub(monkeypatch)
    fixture = base_fixture()
    fixture.pop("fixture_id")

    response = client.post("/predict", json={"fixtures": [fixture]})

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["type"] == "validation_error"
    fields = [item["field"] for item in payload["error"]["invalid_fields"]]
    assert "fixtures.0.fixture_id" in fields



def test_predict_invalid_numeric_type_returns_422(monkeypatch):
    client, _ = _client_with_ingest_stub(monkeypatch)
    fixture = base_fixture()
    fixture["cf_home"] = "abc"

    response = client.post("/predict", json={"fixtures": [fixture]})

    assert response.status_code == 422
    payload = response.json()
    assert payload["error"]["message"] == "Payload inválido para /predict"
    assert any(item["field"] == "fixtures.0.cf_home" for item in payload["error"]["invalid_fields"])


def _seed_prediction_with_status(
    session,
    fixture_id,
    status_short,
    market_breakdown,
    *,
    fixture_dt=None,
    league_id=140,
    league_name="La Liga",
    country="Spain",
):
    now = fixture_dt or datetime(2026, 4, 1, 18, 0, tzinfo=timezone.utc)
    session.merge(
        main.Fixture(
            fixture_id=fixture_id,
            league_id=league_id,
            league_name=league_name,
            country=country,
            season=2026,
            fixture_datetime=now,
            status_short=status_short,
            status_long=status_short,
            home_team_id=fixture_id + 10,
            home_team_name=f"Home {fixture_id}",
            away_team_id=fixture_id + 20,
            away_team_name=f"Away {fixture_id}",
            created_at=now,
            updated_at=now,
        )
    )
    session.merge(
        main.Prediction(
            fixture_id=fixture_id,
            liga_id=league_id,
            liga=league_name,
            pais=country,
            hora=now,
            estado=status_short,
            local=f"Home {fixture_id}",
            visitante=f"Away {fixture_id}",
            market_breakdown=market_breakdown,
            apuestas_fuertes=[],
            created_at=now,
            updated_at=now,
        )
    )


def test_panel_dashboard_only_ns_future_and_multiple_markets(monkeypatch):
    fixed_now = datetime(2026, 3, 31, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(main, "now_utc", lambda: fixed_now)

    with db.SessionLocal() as session:
        session.query(main.Prediction).delete()
        session.query(main.Fixture).delete()

        _seed_prediction_with_status(
            session,
            fixture_id=2001,
            status_short="NS",
            fixture_dt=fixed_now + timedelta(hours=8),
            market_breakdown=[
                {"code": "OVER25", "mercado": "Goles", "jugada": "Over 2.5", "prob": 0.62, "cuota": 1.9, "probabilidad_implicita": 0.52, "edge": 0.10, "ev": 0.17, "market_complete": True},
                {"code": "O85_CORNERS", "mercado": "Corners", "jugada": "Over 8.5 corners", "prob": 0.61, "cuota": 2.0, "probabilidad_implicita": 0.50, "edge": 0.11, "ev": 0.16, "market_complete": True},
                {"code": "O35_CARDS", "mercado": "Tarjetas", "jugada": "Over 3.5 tarjetas", "prob": 0.58, "cuota": 1.88, "probabilidad_implicita": 0.53, "edge": 0.05, "ev": 0.09, "market_complete": True},
                {"code": "SHOTS_HOME", "mercado": "Shots", "jugada": "Home shots", "prob": 0.59, "cuota": 1.92, "probabilidad_implicita": 0.52, "edge": 0.07, "ev": 0.12, "market_complete": True},
                {"code": "SOT_AWAY", "mercado": "Shots on target", "jugada": "Away SOT", "prob": 0.57, "cuota": 1.93, "probabilidad_implicita": 0.51, "edge": 0.06, "ev": 0.10, "market_complete": True},
            ],
        )
        _seed_prediction_with_status(
            session,
            fixture_id=2002,
            status_short="LIVE",
            fixture_dt=fixed_now + timedelta(hours=3),
            market_breakdown=[
                {"code": "O35_CARDS", "mercado": "Tarjetas", "jugada": "Over 3.5 tarjetas", "prob": 0.60, "cuota": 1.95, "probabilidad_implicita": 0.51, "edge": 0.09, "ev": 0.15, "market_complete": True},
            ],
        )
        _seed_prediction_with_status(
            session,
            fixture_id=2003,
            status_short="FT",
            fixture_dt=fixed_now + timedelta(hours=4),
            market_breakdown=[
                {"code": "O85_CORNERS", "mercado": "Corners", "jugada": "Over 8.5 corners", "prob": 0.61, "cuota": 2.0, "probabilidad_implicita": 0.50, "edge": 0.11, "ev": 0.16, "market_complete": True},
            ],
        )
        _seed_prediction_with_status(
            session,
            fixture_id=2004,
            status_short="NS",
            fixture_dt=fixed_now + timedelta(hours=30),
            league_id=39,
            league_name="Premier League",
            country="England",
            market_breakdown=[
                {"code": "TEAM_HOME_OVER_0_5", "mercado": "Goles equipo", "jugada": "Home over 0.5", "prob": 0.65, "cuota": 1.70, "probabilidad_implicita": 0.58, "edge": 0.07, "ev": 0.11, "market_complete": True},
            ],
        )
        _seed_prediction_with_status(
            session,
            fixture_id=2005,
            status_short="NS",
            fixture_dt=fixed_now + timedelta(hours=80),
            market_breakdown=[
                {"code": "SOT_AWAY", "mercado": "Shots on target", "jugada": "Away SOT", "prob": 0.57, "cuota": 1.93, "probabilidad_implicita": 0.51, "edge": 0.06, "ev": 0.10, "market_complete": True},
            ],
        )
        session.commit()

    client = TestClient(main.app)
    response = client.get("/panel/dashboard?limit=100")
    assert response.status_code == 200
    payload = response.json()

    visible_fixture_ids = {match["fixture_id"] for match in payload["partidos"]}
    assert 2001 in visible_fixture_ids  # NS visible
    assert 2002 not in visible_fixture_ids  # LIVE hidden
    assert 2003 not in visible_fixture_ids  # FT hidden
    assert 2004 in visible_fixture_ids  # NS in another league visible
    assert 2005 not in visible_fixture_ids  # NS fuera de ventana oculta

    opportunity_fixture_ids = {opp["fixture_id"] for opp in payload["top_opportunities"]}
    assert 2001 in opportunity_fixture_ids
    assert 2002 not in opportunity_fixture_ids
    assert 2003 not in opportunity_fixture_ids
    assert 2004 in opportunity_fixture_ids
    assert 2005 not in opportunity_fixture_ids

    visible_codes = {(opp["fixture_id"], opp["code"]) for opp in payload["top_opportunities"]}
    assert (2001, "O85_CORNERS") in visible_codes
    assert (2001, "O35_CARDS") in visible_codes
    assert (2001, "SHOTS_HOME") in visible_codes
    assert (2001, "SOT_AWAY") in visible_codes

    total_leagues = payload["summary"]["total_ligas"]
    assert total_leagues >= 2


def test_parse_dt_treats_naive_input_as_warsaw_and_converts_to_utc():
    dt = main.parse_dt("2026-03-31T19:00:00")
    assert dt is not None
    assert dt.tzinfo == timezone.utc
    assert dt.isoformat() == "2026-03-31T17:00:00+00:00"


def test_parse_dt_keeps_explicit_utc_timestamp_stable():
    dt = main.parse_dt("2026-03-31T17:00:00Z")
    assert dt is not None
    assert dt.tzinfo == timezone.utc
    assert dt.isoformat() == "2026-03-31T17:00:00+00:00"
