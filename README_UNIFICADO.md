# App unificada Bankenban + Panel

Esta aplicación despliega **una sola instancia FastAPI** que integra:

- Motor Bankenban (`predictor.py`) para cálculo y scoring de mercados.
- API (`main.py`) para ingesta, predicción, alertas y resumen.
- Panel frontend estático (`static/index.html`, `static/app.js`, `static/styles.css`) servido por la misma app.

## Integración real de punta a punta

- `GET /` entrega el panel HTML (`static/index.html`).
- `GET /static/*` sirve los assets del panel (JS/CSS).
- El panel consume `GET /panel/dashboard` para cargar partidos, oportunidades EV+, radar de partido, familias y resumen.
- El endpoint `/panel/dashboard` se alimenta de `predictions.market_breakdown` y `predictions.apuestas_fuertes`, generados por el motor Bankenban durante `/ingest/run` o `/predict`.

## Estructura

- `main.py`, `predictor.py`, `db.py`: backend + motor Bankenban
- `static/`: panel integrado
- `Dockerfile`, `docker-compose.yml`: despliegue conjunto backend + panel

## Ejecución local

```bash
export DATABASE_URL="sqlite:///./dev.db"
uvicorn main:app --host 0.0.0.0 --port 8000
```

Abre `http://localhost:8000/` para el panel.
