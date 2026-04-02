# Auditoría forense Bankenban (2026-04-02)

## 1) Resumen ejecutivo
- El backend **procesa más jugadas** de las que el panel principal renderiza en listas top.
- Las jugadas visibles de referencia (`BTTS_YES`, `1X2_DRAW`) son un subconjunto de un conjunto mayor procesado y telemetrizado.
- Se confirmó que existen filtros/mecanismos de ocultación en frontend y backend (estado del fixture, math gating, publishable, panel constraints).
- Se aplicó corrección frontend para que se visualicen mercados `traceable_only` en secciones de mercados incompletos.

## 2) Diagnóstico forense del sistema completo
- Backend Python:
  - `predictor.calcular_partido` genera mercados modelados y agrega mercados detectados desde `families` / `market_catalog`.
  - `main.build_dashboard_payload` recalcula métricas y clasifica oportunidades en top/util/detectado.
- Panel:
  - consume `/panel/dashboard` y construye datasets `complete` vs `incomplete`.
  - anteriormente filtraba en `renderOpportunityList` casi siempre por `publishable`.
- Docker:
  - estructura estándar (`Dockerfile`, `docker-compose.yml`, entrypoint) sin cambios en esta intervención.

## 3) Fallas detectadas
- UI ocultaba en práctica mercados detectados no publicables en el renderizado de listas, incluso cuando estaban en payload.
- No se encontraron campos explícitos `requiredMarkets`, `markets_valid`, `selected_market_names`, `selected_market_labels` como contrato persistido/consumido en backend actual.
- El dashboard principal prioriza `publishable`, por diseño no representa el total bruto procesado.

## 4) Causas raíz
- Doble gating:
  1. backend (ev/edge/prob/calibration/readiness/family/status fixture),
  2. frontend (validOnly + publishable) para render.
- Ausencia de contrato normalizado en código para los campos de workflow nombrados en el requerimiento (`requiredMarkets`, etc.).

## 5) Riesgos críticos
- Riesgo de diagnóstico operativo incompleto: operador puede asumir que “no se calculó” cuando sí se calculó pero quedó `traceable_only`.
- Riesgo de trazabilidad parcial entre workflow externo y panel si se depende de nombres no normalizados.

## 6) Qué se corrigió exactamente
- Frontend `static/app.js`:
  - `renderOpportunityList` ahora acepta opción `allowTraceable`.
  - para secciones `*-incomplete` se permite renderizar mercados `traceable_only` (especialmente útiles para auditoría).

## 7) Qué se dejó intacto y por qué
- Lógica matemática de cálculo y calibración en backend: intacta para no alterar comportamiento de pricing/riesgo ya validado por tests.
- Restricciones del panel en backend (`panel_blocked`/`panel_block_reason`): intactas para mantener control operacional vigente.

## 8) Confirmación de credenciales
- No se modificaron credenciales, tokens, API keys ni variables sensibles.

## 9) Verificación de respeto a restricciones del panel
- Se verificó por tests que al deshabilitar `publish_value_allowed`, los picks core quedan bloqueados para publicación (`traceable_only` con razón de bloqueo).
- En `predictor` se mantienen marcas `panel_blocked` y selección de pick principal desde `allowed_markets`.

## 10) Verificación funcional completa
- Se validó flujo: fixture -> cálculo -> `market_breakdown` -> payload dashboard -> render frontend.
- Se validó explícitamente set forense:
  - `match_winner`: `1X2_HOME`, `1X2_DRAW`, `1X2_AWAY`
  - `totals_over_under_2_5`: `OVER_2_5`, `UNDER_2_5`
  - `both_teams_to_score`: `BTTS_YES`, `BTTS_NO`
  - `double_chance`: `DC_1X`, `DC_12`, `DC_X2`
- Resultado: backend procesa conjunto amplio; panel top renderiza subconjunto según reglas.

## 11) Código corregido
- `static/app.js`: soporte de render `traceable_only` en listas incompletas.
- `tests/test_predict_endpoint.py`: prueba forense de procesamiento completo vs subset visible dashboard.

## 12) Por qué ahora el sistema es más consistente
- La discrepancia “procesado vs visible” queda transparentada en UI para mercados incompletos.
- Se conserva control de publicación (restricciones panel) pero mejora la visibilidad forense de mercados detectados.
