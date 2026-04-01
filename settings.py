from __future__ import annotations

import os
from dataclasses import dataclass


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class DecisionThresholds:
    min_model_probability: float = _env_float("MIN_MODEL_PROBABILITY", 0.20)
    min_signal_delta: float = _env_float("MIN_SIGNAL_DELTA", 0.02)
    min_actionable_odds: float = _env_float("MIN_ACTIONABLE_ODDS", 1.05)
    min_ev: float = _env_float("MIN_EV", 0.0)
    min_confidence: float = _env_float("MIN_CONFIDENCE", 0.0)
    max_market_volatility: float = _env_float("MAX_MARKET_VOLATILITY", 0.55)


@dataclass(frozen=True)
class RiskConfig:
    kelly_fraction: float = _env_float("KELLY_FRACTION", 0.25)
    max_stake_units: float = _env_float("MAX_STAKE_UNITS", 0.05)
    flat_stake_units: float = _env_float("FLAT_STAKE_UNITS", 0.01)


@dataclass(frozen=True)
class CalibrationConfig:
    method: str = os.getenv("CALIBRATION_METHOD", "builtin")
    artifact_path: str = os.getenv("CALIBRATOR_PATH", "./artifacts/calibrator.json")


DECISION_THRESHOLDS = DecisionThresholds()
RISK_CONFIG = RiskConfig()
CALIBRATION_CONFIG = CalibrationConfig()
