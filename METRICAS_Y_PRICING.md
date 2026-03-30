# Métricas y pricing

## Definiciones oficiales

- **model_prob**: probabilidad del modelo para la selección del mercado.
- **implied_prob**: `1 / odds` (cuota decimal > 1).
- **fair_prob**: probabilidad sin margen de la casa.
  - En **1X2** se calcula con de-vig normalizado entre home/draw/away.
  - En mercados binarios o incompletos, si no están ambos lados del mercado, se deja en `null`.
- **delta_prob**: `model_prob - implied_prob`.
- **edge**: `model_prob - fair_prob`.
- **ev**: `odds * model_prob - 1`.

## Reglas de null y transparencia

Una métrica queda en `null` cuando no se puede calcular de forma seria:

- `fair_prob = null` si no hay pricing suficiente para de-vig.
- `edge = null` cuando `fair_prob` es `null`.
- `ev = null` cuando faltan `odds` o `model_prob`.

## pricing_complete

`pricing_complete = true` únicamente cuando existen:

- `odds`
- `model_prob`
- `implied_prob`
- `fair_prob`
- `edge`
- `ev`

Si `pricing_complete = false` no deben activarse badges de pricing (`EV+`, `Value`, `Strong signal`).

## Corners: estado actual y base extensible

Soportado en producción:

- Totales corners: over 7.5, 8.5, 9.5.

Estructura ya preparada para crecer:

- `totals`
- `team_totals`
- `handicap`
- `periods` (1T/2T)
- `race_to_x`

Persistencia preparada:

- `predictions.corners_markets` (JSON)
- `odds_snapshot.corners_lines` (JSON)

Los grupos no implementados aún se dejan vacíos explícitamente para evitar probabilidades inventadas.
