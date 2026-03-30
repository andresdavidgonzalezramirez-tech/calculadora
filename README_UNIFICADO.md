# App unificada

Este paquete une el backend `calculadora` y el frontend `panel` en una sola app FastAPI.

## Estructura
- `main.py`, `predictor.py`, `db.py`: backend original
- `static/`: frontend original (`index.html`, `app.js`, `styles.css`, etc.)

## Cambio mínimo aplicado
1. `main.py` ahora sirve la carpeta `static/` desde la misma app.
2. `static/config.js` queda configurado para usar la misma URL base por defecto (`""`).

## Ejecución
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Luego abre `http://localhost:8000/` para el panel y la misma app responderá `/panel/*` y `/health`.
