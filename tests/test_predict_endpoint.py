import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_predict_endpoint.db")
sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

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



def test_predict_normalizes_none_numeric_stats(monkeypatch):
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
    assert normalized.cf_home == 0
    assert normalized.ca_home == 0
    assert normalized.cf_away == 0
    assert normalized.ca_away == 0
    assert normalized.yf_home == 0
    assert normalized.yf_away == 0
    assert normalized.shots_home == 0
    assert normalized.shots_away == 0
    assert normalized.shots_on_target_home == 0
    assert normalized.shots_on_target_away == 0



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
