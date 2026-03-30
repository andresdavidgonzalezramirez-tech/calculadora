# Auditoría técnica interna (resumen)

Este archivo resume hallazgos técnicos del motor de picks:

- `edge_principal` se calcula como `p_modelo - p_mercado_justa` y **no** como EV monetario.
- En telemetría del dashboard, para el mercado principal se asigna `ev = edge_principal`, lo que mezcla unidades de `edge` y `EV`.
- El `rank` mostrado en oportunidades usa `confianza` global del pick principal, incluso para mercados secundarios.
- El `score` mostrado en oportunidades usa `prob_apuesta` del pick principal, incluso cuando se lista otro mercado.
- Para 1X2 se usa fair probability sin overround, para mercados binarios se usa implícita cruda (`1/cuota`) como `probabilidad_justa`.
- Corner markets soportados actualmente: `over75`, `over85`, `over95` de corners totales.

Conclusión breve: el sistema es usable como generador de señales, pero no como motor de value betting auditado sin ajustes de transparencia y calibración estadística.
