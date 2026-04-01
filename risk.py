from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from betting_math import expected_value, implied_probability, kelly_fraction
from settings import DECISION_THRESHOLDS, RISK_CONFIG


@dataclass
class PickEvaluation:
    market_complete: bool
    recommended: bool
    implied_prob: Optional[float]
    ev: Optional[float]
    kelly: Optional[float]
    stake_units: Optional[float]


def evaluate_pick(probability: Optional[float], odds: Optional[float], confidence: float = 0.0, anomaly: bool = False) -> PickEvaluation:
    if probability is None or odds is None:
        return PickEvaluation(False, False, None, None, None, None)

    imp = implied_probability(odds)
    ev = expected_value(probability, odds)
    if imp is None or ev is None:
        return PickEvaluation(False, False, imp, ev, None, None)

    kf = kelly_fraction(probability, odds)
    stake = min((kf or 0.0) * RISK_CONFIG.kelly_fraction, RISK_CONFIG.max_stake_units)

    recommended = bool(
        probability >= DECISION_THRESHOLDS.min_model_probability
        and ev >= DECISION_THRESHOLDS.min_ev
        and confidence >= DECISION_THRESHOLDS.min_confidence
        and odds >= DECISION_THRESHOLDS.min_actionable_odds
        and not anomaly
    )
    return PickEvaluation(True, recommended, imp, ev, kf, round(stake, 4) if recommended and stake > 0 else None)
