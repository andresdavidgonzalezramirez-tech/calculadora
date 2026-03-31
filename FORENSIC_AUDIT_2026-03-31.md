# Auditoría forense técnica — 2026-03-31

## 1. Inventario real del sistema

### Backend y motor cuantitativo
- **API/Backend**: `FastAPI` en `main.py`.
- **Persistencia**: SQLAlchemy ORM en `db.py`.
- **Motor predictivo**: `predictor.py`.
- **Frontend**: `static/index.html`, `static/app.js`, `static/styles.css`.
- **Workflow externo**: `JSON actual del workflow` (n8n / API-Football).

### Entidades SQL reales (ORM)
- `fixtures`, `predictions`, `prediction_runs`, `odds_snapshot`, `team_stats_cache`, `pricing_alerts`.
- Campos de `predictions` incluyen probabilidades y agregados para goles, corners, tarjetas, tiros y tiros a puerta (por equipo y totales cuando aplica).
- Campos de `odds_snapshot` contienen odds para 1X2, doble oportunidad, goles totales, BTTS, corners totales, tarjetas totales, tiros y tiros a puerta por equipo.

### Flujo de datos
1. Ingesta (`/ingest/run` o `/predict`) → guarda fixture, stats, odds snapshot.
2. `calcular_partido()` genera probabilidades, selección principal y señales.
3. `upsert_prediction()` persiste resultado y señales.
4. `/panel/dashboard` construye telemetría mercado-a-mercado para UI.

## 2. Mercados soportados vs omitidos

### Mercados realmente calculados y rankeados
- 1X2: `1X2_HOME`, `1X2_DRAW`, `1X2_AWAY`.
- Doble oportunidad: `DC_1X`, `DC_X2`, `DC_12`.
- Goles totales: `OVER15`, `OVER25`, `OVER35`, `UNDER45`.
- BTTS: `BTTS_YES`.
- Corners totales: `O75_CORNERS`, `O85_CORNERS`, `O95_CORNERS`.
- Tarjetas totales: `O35_CARDS`, `O45_CARDS`.
- Tiros por equipo (mercado agregado “altos”): `SHOTS_HOME`, `SHOTS_AWAY`.
- Tiros a puerta por equipo (mercado agregado “altos”): `SOT_HOME`, `SOT_AWAY`.

### Mercados calculados pero **no comercializados** como mercado en motor
- **Goles por equipo**: se calcula `gol_local`, `gol_visitante` (prob. de marcar), pero no existe mercado explícito `TEAM_TO_SCORE_YES/NO` en `markets[]`.
- **Métricas por equipo** de corners/tarjetas/tiros (`corners_local`, `tarjetas_local`, `tiros_local`, etc.) se guardan como features/resultados, pero no se convierten a mercados apostables “over por equipo con línea y cuota”.

### Mercados presentes en SQL/backend pero no expuestos como picks completos
- En `build_market_telemetry`, los markets de tiros/sot desde snapshot se agregan con `model_prob=None`, quedando incompletos (sin edge/ev robusto), por lo que no compiten bien en top EV.
- El frontend sí los muestra en panel de incompletos, pero no como oportunidades completas.

### Mercados faltantes o no implementados
- Hándicaps (asiáticos/europeos).
- Mercados por mitad (1ª/2ª parte).
- Under en corners/cards.
- BTTS NO.
- Team totals explícitos (goles/corners/cards/shots por equipo con líneas 0.5/1.5/2.5, etc.).
- Combinadas estructuradas.
- Mercados especiales derivados avanzados.

## 3. Errores detectados

1. **Error de modelado probabilístico en shots/sot**
   - Tipo: modelo superficial/heurístico lineal.
   - Ubicación: `predictor.py` (`SHOTS_*`, `SOT_*` usan baseline lineal transformado a pseudo-probabilidad).
   - Impacto: probabilidad no calibrada a línea real/umbral real de mercado.
   - Corrección: modelar por línea específica (Poisson/NegBin + calibración isotónica/platt por mercado).

2. **Cobertura incompleta de odds alias para tiros/SOT**
   - Tipo: mapeo incompleto.
   - Ubicación: `extract_odds()` alias para `shots_home`, `shots_away`, `sot_home`, `sot_away` muy estrechos.
   - Impacto: odds disponibles en payload pueden no resolverse, mercado pasa a incompleto (`missing_odds`).
   - Corrección: ampliar alias por proveedor/canonical dictionary.

3. **Mercados por equipo calculados pero no convertidos en picks**
   - Tipo: desconexión cálculo → mercado.
   - Ubicación: `calcular_partido()` calcula corners/cards/shots por equipo, pero sólo crea picks de totales (corners/cards) y “shots altos” sin línea explícita.
   - Impacto: omite jugadas potencialmente favorables (home over corners/cards/shots).
   - Corrección: generar mercados `TEAM_OVER_X` con thresholds y odds explícitas por equipo.

4. **Telemetría de shots/sot sin `model_prob` desde snapshot**
   - Tipo: serialización incompleta para ranking.
   - Ubicación: `build_market_telemetry()` (`odds_map` coloca `model_prob=None` en shots/sot).
   - Impacto: quedan fuera del set EV+ completo aunque existan cuotas.
   - Corrección: mapear a probabilidad de modelo persistida o recomputar por línea.

5. **Posible exposición de secreto**
   - Tipo: seguridad operacional.
   - Ubicación: `JSON actual del workflow` contiene key API en texto claro.
   - Impacto: riesgo de abuso de cuota API y compromiso del pipeline.
   - Corrección: rotar credencial y mover a secreto gestionado.

## 4. Evidencia de omisión de jugadas

- El motor prioriza mercados con odds y edge calculables; todo lo que no tenga `model_prob` + `odds` + `implied_prob` + `edge` + `ev` cae a “incompleto”.
- El sistema detecta y conserva mercados incompletos, pero no los prioriza en top oportunidades.
- Corners/tarjetas por equipo: hay valores esperados por equipo, pero no hay catálogo de picks por equipo con odds asociadas.
- Team goals (`equipo marca`) se calcula internamente y se persiste, pero no se transforma en mercado publicado con su cuota.

## 5. Jugadas favorables encontradas (a nivel de arquitectura)

> Nota: sin dump de `predictions` + `odds_snapshot` real no se puede emitir lista definitiva partido-a-partido con cuotas actuales. Aun así, la arquitectura sugiere estas familias conservadoras como candidatas cuando exista edge positivo real:

1. **Doble oportunidad (DC_1X / DC_X2)**
   - Alta fiabilidad y baja volatilidad en perfiles de mercado.
   - Favorecido por `STABLE_MARKET_PRIORITY`.

2. **Over 1.5 goles / Under 4.5 goles**
   - Alta estabilidad relativa y edge thresholds más bajos.

3. **Over 7.5 corners / Over 3.5 tarjetas**
   - Considerados mercados “estables” dentro del motor actual.

4. **Mercados por equipo que deberían activarse (hoy omitidos parcialmente)**
   - Over córners local/visitante.
   - Over tarjetas local/visitante.
   - Team to score (sí/no) por equipo.
   - Team over 0.5/1.5 goles.

## 6. Sesgos de scoring y cobertura

- **Sesgo de cobertura**: sobrecubre 1X2/goles y totales; subcubre props por equipo en corners/cards/shots.
- **Sesgo de publicación**: el pipeline guarda métricas por equipo, pero la UI/ranking opera principalmente con mercados completos EV-ready.
- **EV vs seguridad**: el score mezcla probabilidad, edge, calidad, reliability y stability; además bonifica mercados estables. No es puramente EV, pero en UI el orden final prioriza EV y puede ocultar picks seguros con EV menor.
- **Underdogs**: no hay sesgo explícito pro-underdog; el sesgo dominante viene por disponibilidad de odds/model_prob y thresholds de edge.

## 7. Correcciones concretas

1. **Catálogo canónico de mercados**
   - Tabla SQL `market_catalog` con `market_code`, familia, tipo (total/team), lado (home/away), línea, estado UI, alias proveedor.

2. **Tabla normalizada de pricing por mercado**
   - `market_prices(fixture_id, market_code, line, side, odd, bookmaker_id, snapshot_at, source)`.

3. **Tabla de probabilidades de modelo por mercado**
   - `market_model_probs(fixture_id, market_code, line, side, model_prob, model_version, quality)`.

4. **Motor de props por equipo**
   - Añadir funciones para:
     - `team_goals_over_0_5/1_5/2_5`.
     - `team_corners_over_x`.
     - `team_cards_over_x`.
     - `team_shots_over_x` y `team_sot_over_x` con línea explícita.

5. **Ranking bicriterio**
   - Separar `value_score` y `safety_score`.
   - Modo conservador UI: ordenar por `safety_score` mínimo + edge positivo.

6. **Serialización completa**
   - Incluir siempre `line`, `side`, `threshold`, `model_prob`, `implied_prob`, `edge`, `ev`, `reliability`, `volatility`, `data_quality`, `completeness_reason`.

7. **UI de cobertura forense**
   - Panel “Mercados existentes vs publicados vs incompletos”.
   - Alertas de desalineación alias/JSON.

8. **Calibración real**
   - Sustituir heurísticas lineales en shots/sot por modelos count (Poisson/NegBin) y calibración por liga/temporada.

## 8. Veredicto técnico final

El sistema **sí es una plataforma avanzada**, no un script: tiene persistencia SQL, motor probabilístico multicapa, scoring compuesto, señalización e interfaz con telemetría. Sin embargo, presenta una brecha clara de **cobertura de mercados por equipo**: calcula varias señales útiles pero no las transforma de forma consistente en mercados apostables completos con línea/cuota/probabilidad/EV. Esto genera omisión de jugadas potencialmente favorables para el usuario, especialmente en props por equipo (corners, tarjetas, tiros, equipo marca).

