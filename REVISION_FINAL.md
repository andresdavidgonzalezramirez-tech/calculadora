# Revision final de producción

## Hallazgos corregidos

1. **Persistencia incompleta en `predictions`**
   - Faltaban columnas que el predictor ya calculaba pero no se guardaban de forma consistente:
     - `over75_corners`
     - `stake_sugerido_unidades`
     - `market_stability`
     - `market_reliability`

2. **Inicialización de esquema insuficiente**
   - `init_db()` solo validaba tablas.
   - Ahora también asegura columnas críticas con `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`.

3. **Extracción de cuotas demasiado limitada**
   - El predictor no recorría listas anidadas de mercados/bookmakers.
   - Eso podía dejar la cuota principal en `0` o `null`, afectando:
     - probabilidad implícita
     - edge
     - value bets
     - stake sugerido

4. **CORS poco sólido para producción**
   - Ahora usa `CORS_ORIGINS` por variable de entorno.
   - Si no se define, queda `*`.

5. **Healthcheck ampliado**
   - Añade versión y orígenes CORS activos.

## Variables recomendadas en producción

- `DATABASE_URL`
- `CORS_ORIGINS=https://tu-panel.easypanel.host`

## Validación recomendada post-despliegue

1. abrir `/health`
2. abrir `/panel/partidos`
3. confirmar que algunos partidos traigan:
   - `cuota_principal`
   - `probabilidad_implicita_principal`
   - `edge_principal`
   - `apuestas_fuertes`
   - `stake_sugerido_unidades`
4. revisar que en PostgreSQL existan las nuevas columnas

## Nota

Si el proveedor origen no entrega cuotas para ciertos mercados, el sistema seguirá mostrando probabilidades del modelo, pero la parte de value bet dependerá de la cuota disponible.
