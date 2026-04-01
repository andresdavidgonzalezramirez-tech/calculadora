# App unificada Bankenban + Panel

Aplicación FastAPI para predicción probabilística de fútbol, cálculo EV+, filtrado de picks y panel web integrado.

## Stack
- FastAPI + Uvicorn
- SQLAlchemy (PostgreSQL/SQLite)
- Motor probabilístico en `predictor.py`
- Frontend estático en `static/`

## Ejecución local
```bash
cp .env.example .env
export DATABASE_URL="sqlite:///./dev.db"
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Docker / EasyPanel
- Usa `Dockerfile` y `docker/entrypoint.sh`.
- La app respeta `PORT` (EasyPanel) y también `APP_PORT`.
- Health endpoint: `GET /health`.
- Variables críticas: `DATABASE_URL`.
- Rutas detrás de proxy:
  - `APP_ROOT_PATH` (o legado `ROOT_PATH`): prefijo ASGI usado por FastAPI cuando el proxy publica en subpath.
  - `FRONTEND_BASE_PATH`: prefijo usado por el frontend para llamar APIs (`/panel/*`, `/health`, etc).
  - Para dominio público en raíz, usar ambos vacíos (`""`).

### Build y run
```bash
docker build -t calculadora .
docker run --rm -p 8000:8000 --env-file .env calculadora
```

## Configuración productiva relevante
- Thresholds y riesgo en `settings.py` vía env:
  - `MIN_MODEL_PROBABILITY`, `MIN_EV`, `MIN_CONFIDENCE`
  - `KELLY_FRACTION`, `MAX_STAKE_UNITS`
- Calibración:
  - `CALIBRATION_METHOD` = `builtin|platt|isotonic`
  - `CALIBRATOR_PATH` con artefacto JSON serializado.

## Módulos nuevos
- `betting_math.py`: fórmulas EV, Kelly, implícita, BTTS Poisson y OU por Poisson total.
- `calibration.py`: Platt/Isotonic + Brier/LogLoss/Reliability.
- `risk.py`: evaluación de picks y stake conservador.
- `backtesting.py`: evaluación histórica y grid search de thresholds.
