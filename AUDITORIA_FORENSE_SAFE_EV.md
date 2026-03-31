# Auditoría forense y propuesta SAFE_EV_MODE

Este documento resume hallazgos técnicos de `predictor.py` y una propuesta de modo híbrido EV + seguridad.

## Hallazgos clave

- El sistema mezcla modelado probabilístico (Poisson + ajuste Dixon-Coles) con fuertes capas heurísticas y clamps.
- `MARKET_PROFILES` usa fiabilidad/volatilidad fijas sin evidencia de calibración empírica interna.
- El score de mercado incorpora edge de forma agresiva y permite picks con probabilidad moderada pero edge positivo.
- La etiqueta `value` no equivale a apuesta segura.
- Existen mecanismos de “suavizado” y “calibración” que pueden presentar probabilidades más estables de lo que respalda el dato.

## SAFE_EV_MODE (propuesta)

Parámetros recomendados:

- `safe_min_prob = 0.65`
- `safe_max_odds = 2.10`
- `safe_min_edge = 0.015`
- `safe_min_reliability = 0.80`
- `safe_max_volatility = 0.35`
- `safe_min_data_quality = 0.58`
- `safe_underdog_odds_floor = 2.20`
- `safe_allow_underdog_only_if_prob = 0.70`

Reglas:

1. Excluir pick si `prob < safe_min_prob`.
2. Excluir pick si `odds` existe y `odds > safe_max_odds`.
3. Excluir pick si `reliability < safe_min_reliability` o `volatility > safe_max_volatility`.
4. Excluir pick con `edge < safe_min_edge`.
5. Excluir underdogs (`odds >= safe_underdog_odds_floor`) salvo `prob >= safe_allow_underdog_only_if_prob` y `edge >= 0.03`.
6. Penalizar fuerte mercados de alta varianza incluso si pasan filtros.

Score híbrido sugerido:

```python
safe_score = (
    prob * 0.52
    + reliability * 0.18
    + stability * 0.16
    + min(max(edge, 0.0), 0.08) * 0.10
    - max(volatility - 0.30, 0.0) * 0.45
    - max((odd or 1.0) - 1.90, 0.0) * 0.18
)
```

Integración:

- Añadir `mode="EV_MODE" | "SAFE_EV_MODE"` a `calcular_partido`.
- Mantener `_build_market` y crear `_build_market_safe` o postfiltro `_apply_safe_ev_filters(markets)`.
- Selección de pick principal:
  - `EV_MODE`: lógica actual.
  - `SAFE_EV_MODE`: seleccionar desde mercados filtrados seguros; fallback explícito a “sin pick seguro”.

