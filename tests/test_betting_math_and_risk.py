from betting_math import btts_from_poisson, expected_value, implied_probability, kelly_fraction, over_under_from_total_poisson
from risk import evaluate_pick


def test_core_math_formulas():
    assert round(implied_probability(2.0), 6) == 0.5
    assert round(expected_value(0.6, 2.0), 6) == 0.2
    assert round(kelly_fraction(0.6, 2.0), 6) == 0.2


def test_poisson_helpers():
    btts = btts_from_poisson(1.4, 1.1)
    assert 0 < btts < 1
    over25 = over_under_from_total_poisson(2.5, 2.5)
    assert 0 < over25 < 1


def test_risk_evaluation_recommended_pick():
    result = evaluate_pick(probability=0.62, odds=1.9, confidence=0.8, anomaly=False)
    assert result.market_complete is True
    assert result.recommended is True
    assert result.ev is not None and result.ev > 0
    assert result.stake_units is None or result.stake_units >= 0


def test_risk_blocks_anomaly():
    result = evaluate_pick(probability=0.7, odds=2.0, confidence=0.9, anomaly=True)
    assert result.recommended is False
