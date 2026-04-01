from __future__ import annotations

import math
from typing import Optional


def clamp_probability(value: float) -> float:
    if math.isnan(value) or math.isinf(value):
        raise ValueError("Probability cannot be NaN/inf")
    return max(0.0, min(1.0, value))


def implied_probability(odds: float) -> Optional[float]:
    if odds is None or odds <= 1.0 or math.isnan(odds) or math.isinf(odds):
        return None
    return 1.0 / odds


def expected_value(probability: float, odds: float) -> Optional[float]:
    ip = implied_probability(odds)
    if ip is None:
        return None
    p = clamp_probability(probability)
    return (p * odds) - 1.0


def kelly_fraction(probability: float, odds: float) -> Optional[float]:
    if odds is None or odds <= 1.0:
        return None
    p = clamp_probability(probability)
    b = odds - 1.0
    raw = ((p * odds) - 1.0) / b
    return max(0.0, raw)


def btts_from_poisson(lambda_home: float, lambda_away: float) -> float:
    lh = max(0.0, float(lambda_home))
    la = max(0.0, float(lambda_away))
    return 1 - math.exp(-lh) - math.exp(-la) + math.exp(-(lh + la))


def over_under_from_total_poisson(lambda_total: float, threshold: float, max_k: int = 20) -> float:
    if lambda_total < 0:
        raise ValueError("lambda_total must be non-negative")
    target = math.floor(threshold) + 1
    probs = [math.exp(-lambda_total) * (lambda_total ** k) / math.factorial(k) for k in range(max_k + 1)]
    total = sum(probs)
    if total <= 0:
        return 0.0
    probs = [p / total for p in probs]
    return sum(probs[target:])
