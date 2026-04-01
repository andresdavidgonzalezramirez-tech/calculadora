from backtesting import ThresholdSet, evaluate_strategy, grid_search
from calibration import IsotonicCalibrator, PlattCalibrator, brier_score, log_loss, reliability_curve


def test_platt_and_isotonic_calibration():
    raw = [0.1, 0.2, 0.4, 0.7, 0.9]
    y = [0, 0, 1, 1, 1]
    platt = PlattCalibrator().fit(raw, y)
    iso = IsotonicCalibrator.fit(raw, y)
    assert 0 <= platt.predict(0.5) <= 1
    assert 0 <= iso.predict(0.5) <= 1


def test_calibration_metrics():
    y = [0, 1, 1, 0]
    p = [0.1, 0.8, 0.7, 0.4]
    assert brier_score(y, p) >= 0
    assert log_loss(y, p) >= 0
    assert len(reliability_curve(y, p, bins=4)) > 0


def test_backtesting_grid_search():
    rows = [
        {"prob": 0.61, "ev": 0.1, "confidence": 0.7, "odds": 1.9, "won": True, "stake": 1},
        {"prob": 0.52, "ev": 0.05, "confidence": 0.6, "odds": 2.1, "won": False, "stake": 1},
        {"prob": 0.40, "ev": -0.02, "confidence": 0.4, "odds": 2.5, "won": False, "stake": 1},
    ]
    out = evaluate_strategy(rows, ThresholdSet(min_prob=0.5, min_ev=0.0, min_confidence=0.5))
    assert out["bets"] == 2
    grid = grid_search(rows, [0.5, 0.6], [0.0], [0.5])
    assert len(grid) == 2
