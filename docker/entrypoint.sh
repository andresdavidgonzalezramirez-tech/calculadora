#!/usr/bin/env bash
set -euo pipefail

APP_HOST="${APP_HOST:-0.0.0.0}"
APP_PORT="${PORT:-${APP_PORT:-3000}}"
DB_WAIT_TIMEOUT="${DB_WAIT_TIMEOUT:-45}"
APP_MODULE="${APP_MODULE:-main:app}"

python - <<'PY'
import os
import time
from sqlalchemy import create_engine, text

url = os.getenv("DATABASE_URL", "")
timeout = int(os.getenv("DB_WAIT_TIMEOUT", "45"))

if not url:
    raise SystemExit("DATABASE_URL no definida")

engine = create_engine(url, future=True)
start = time.time()
while True:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        break
    except Exception as exc:
        if time.time() - start >= timeout:
            raise SystemExit(f"DB no disponible tras {timeout}s: {exc}")
        time.sleep(1)

from db import init_db
init_db()
print("DB lista y esquema inicializado")
PY

exec python -m uvicorn "$APP_MODULE" --host "$APP_HOST" --port "$APP_PORT" --proxy-headers --no-server-header
