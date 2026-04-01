
import math
import re
from typing import Any, Dict, List, Optional, Tuple

MAX_GOALS = 10
MAX_EVENTS = 40
EPSILON = 1e-9
INTEGRITY_HIGH_ODD_THRESHOLD = 2.6
INTEGRITY_HIGH_MODEL_PROB_THRESHOLD = 0.62
INTEGRITY_SUSPICIOUS_EDGE_FLOOR = 0.10
INTEGRITY_SOFT_NEGATIVE_EDGE = -0.07

LEAGUE_BASELINES = {
    "goals_home": 1.38,
    "goals_away": 1.08,
    "corners_home": 5.25,
    "corners_away": 4.55,
    "yellow_home": 2.00,
    "yellow_away": 2.30,
    "shots_home": 11.7,
    "shots_away": 10.1,
    "shots_on_home": 4.2,
    "shots_on_away": 3.6,
}

MARKET_PROFILES = {
    "1X2_HOME": {"group": "1X2", "reliability": 0.78, "volatility": 0.58, "edge_threshold": 0.050},
    "1X2_DRAW": {"group": "1X2", "reliability": 0.66, "volatility": 0.80, "edge_threshold": 0.060},
    "1X2_AWAY": {"group": "1X2", "reliability": 0.77, "volatility": 0.60, "edge_threshold": 0.050},
    "DC_1X": {"group": "Doble oportunidad", "reliability": 0.94, "volatility": 0.24, "edge_threshold": 0.032},
    "DC_X2": {"group": "Doble oportunidad", "reliability": 0.93, "volatility": 0.26, "edge_threshold": 0.032},
    "DC_12": {"group": "Doble oportunidad", "reliability": 0.88, "volatility": 0.38, "edge_threshold": 0.038},
    "OVER15": {"group": "Goles", "reliability": 0.95, "volatility": 0.22, "edge_threshold": 0.030},
    "OVER25": {"group": "Goles", "reliability": 0.84, "volatility": 0.42, "edge_threshold": 0.038},
    "OVER35": {"group": "Goles", "reliability": 0.69, "volatility": 0.58, "edge_threshold": 0.050},
    "UNDER45": {"group": "Goles", "reliability": 0.94, "volatility": 0.20, "edge_threshold": 0.030},
    "BTTS_YES": {"group": "BTTS", "reliability": 0.77, "volatility": 0.46, "edge_threshold": 0.042},
    "O75_CORNERS": {"group": "Corners", "reliability": 0.87, "volatility": 0.32, "edge_threshold": 0.036},
    "O85_CORNERS": {"group": "Corners", "reliability": 0.80, "volatility": 0.40, "edge_threshold": 0.042},
    "O95_CORNERS": {"group": "Corners", "reliability": 0.72, "volatility": 0.50, "edge_threshold": 0.048},
    "O35_CARDS": {"group": "Tarjetas", "reliability": 0.88, "volatility": 0.32, "edge_threshold": 0.036},
    "O45_CARDS": {"group": "Tarjetas", "reliability": 0.80, "volatility": 0.40, "edge_threshold": 0.042},
    "SHOTS_HOME": {"group": "Tiros", "reliability": 0.63, "volatility": 0.56, "edge_threshold": 0.058},
    "SHOTS_AWAY": {"group": "Tiros", "reliability": 0.61, "volatility": 0.58, "edge_threshold": 0.058},
    "SOT_HOME": {"group": "Tiros a puerta", "reliability": 0.58, "volatility": 0.62, "edge_threshold": 0.062},
    "SOT_AWAY": {"group": "Tiros a puerta", "reliability": 0.57, "volatility": 0.63, "edge_threshold": 0.062},
    "CORNERS_HOME_OVER_3_5": {"group": "Corners equipo", "reliability": 0.82, "volatility": 0.37, "edge_threshold": 0.040},
    "CORNERS_HOME_OVER_4_5": {"group": "Corners equipo", "reliability": 0.76, "volatility": 0.45, "edge_threshold": 0.046},
    "CORNERS_AWAY_OVER_3_5": {"group": "Corners equipo", "reliability": 0.79, "volatility": 0.40, "edge_threshold": 0.042},
    "CORNERS_AWAY_OVER_4_5": {"group": "Corners equipo", "reliability": 0.72, "volatility": 0.48, "edge_threshold": 0.048},
    "CARDS_HOME_OVER_1_5": {"group": "Tarjetas equipo", "reliability": 0.83, "volatility": 0.36, "edge_threshold": 0.038},
    "CARDS_HOME_OVER_2_5": {"group": "Tarjetas equipo", "reliability": 0.74, "volatility": 0.46, "edge_threshold": 0.046},
    "CARDS_AWAY_OVER_1_5": {"group": "Tarjetas equipo", "reliability": 0.82, "volatility": 0.37, "edge_threshold": 0.040},
    "CARDS_AWAY_OVER_2_5": {"group": "Tarjetas equipo", "reliability": 0.73, "volatility": 0.47, "edge_threshold": 0.047},
    "TEAM_HOME_SCORE_YES": {"group": "Goles equipo", "reliability": 0.86, "volatility": 0.32, "edge_threshold": 0.035},
    "TEAM_AWAY_SCORE_YES": {"group": "Goles equipo", "reliability": 0.82, "volatility": 0.38, "edge_threshold": 0.040},
    "TEAM_HOME_OVER_0_5": {"group": "Goles equipo", "reliability": 0.87, "volatility": 0.31, "edge_threshold": 0.034},
    "TEAM_HOME_OVER_1_5": {"group": "Goles equipo", "reliability": 0.74, "volatility": 0.48, "edge_threshold": 0.046},
    "TEAM_AWAY_OVER_0_5": {"group": "Goles equipo", "reliability": 0.84, "volatility": 0.35, "edge_threshold": 0.038},
    "TEAM_AWAY_OVER_1_5": {"group": "Goles equipo", "reliability": 0.70, "volatility": 0.52, "edge_threshold": 0.050},
    "SHOTS_HOME_OVER_X": {"group": "Tiros equipo", "reliability": 0.64, "volatility": 0.54, "edge_threshold": 0.056},
    "SHOTS_AWAY_OVER_X": {"group": "Tiros equipo", "reliability": 0.62, "volatility": 0.56, "edge_threshold": 0.058},
    "SOT_HOME_OVER_X": {"group": "Tiros a puerta equipo", "reliability": 0.61, "volatility": 0.58, "edge_threshold": 0.058},
    "SOT_AWAY_OVER_X": {"group": "Tiros a puerta equipo", "reliability": 0.59, "volatility": 0.60, "edge_threshold": 0.060},
}

STABLE_MARKET_PRIORITY = {
    "DC_1X": 1.22,
    "DC_X2": 1.22,
    "OVER15": 1.24,
    "UNDER45": 1.20,
    "O75_CORNERS": 1.12,
    "O35_CARDS": 1.12,
}

PROBABILITY_FLOORS = {
    "strict": 0.64,
    "high": 0.60,
    "medium": 0.60,
}
MIN_RENDER_PROBABILITY = 0.60
MAX_ACCEPTABLE_VOLATILITY = 0.55


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, "", "null", "None"):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, "", "null", "None"):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _avg(values: List[Optional[float]], default: float) -> float:
    clean = [float(v) for v in values if v is not None]
    return sum(clean) / len(clean) if clean else default


def _nested(data: Dict[str, Any], path: List[str], default: Any = None) -> Any:
    cur: Any = data
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def _parse_avg_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", ".")
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _round_prob(prob: float) -> float:
    return round(_clamp(prob, 0.01, 0.99), 6)


def _form_factor(form: Optional[str], default: float = 1.0) -> float:
    if not form:
        return default
    mapping = {"W": 3, "D": 1, "L": 0}
    vals = [mapping[ch.upper()] for ch in str(form) if ch.upper() in mapping]
    if not vals:
        return default
    ppm = sum(vals) / len(vals)
    return _clamp(0.92 + (ppm / 3.0) * 0.14, 0.92, 1.06)


def poisson_pmf(lmbda: float, k: int) -> float:
    lmbda = max(0.01, lmbda)
    return math.exp(-lmbda) * (lmbda ** k) / math.factorial(k)


def poisson_dist(lmbda: float, max_k: int) -> List[float]:
    dist = [poisson_pmf(lmbda, k) for k in range(max_k + 1)]
    total = sum(dist)
    if total <= 0:
        return [0.0] * (max_k + 1)
    return [x / total for x in dist]


def prob_over_lambda(lmbda: float, threshold: float, max_k: int = MAX_EVENTS) -> float:
    target = math.floor(threshold) + 1
    dist = poisson_dist(lmbda, max_k)
    return sum(dist[target:])


def team_to_score_prob(lmbda: float) -> float:
    return 1.0 - math.exp(-max(0.01, lmbda))


def _extract_recent_results(recent: Any) -> List[Dict[str, Any]]:
    if isinstance(recent, list):
        return [x for x in recent if isinstance(x, dict)]
    return []


def _weighted_recent_metrics(recent: Any) -> Dict[str, float]:
    matches = _extract_recent_results(recent)[:6]
    if not matches:
        return {
            "matches": 0,
            "gf": 0.0,
            "ga": 0.0,
            "points_per_match": 0.0,
            "clean_sheet_rate": 0.0,
            "scored_rate": 0.0,
        }

    weights = [6, 5, 4, 3, 2, 1][: len(matches)]
    total_weight = float(sum(weights))
    gf = ga = pts = clean = scored = 0.0

    for item, w in zip(matches, weights):
        gs = _safe_float(item.get("goals_scored"), 0.0)
        gc = _safe_float(item.get("goals_conceded"), 0.0)
        result = str(item.get("result", "")).upper()

        gf += gs * w
        ga += gc * w
        if result == "W":
            pts += 3.0 * w
        elif result == "D":
            pts += 1.0 * w

        if gc <= 0:
            clean += 1.0 * w
        if gs >= 1:
            scored += 1.0 * w

    return {
        "matches": len(matches),
        "gf": gf / total_weight,
        "ga": ga / total_weight,
        "points_per_match": pts / total_weight,
        "clean_sheet_rate": clean / total_weight,
        "scored_rate": scored / total_weight,
    }


def _h2h_bias(head_to_head: Any, home_name: str, away_name: str) -> float:
    matches = _extract_recent_results(head_to_head)[:5]
    if not matches:
        return 0.0

    weights = [5, 4, 3, 2, 1][: len(matches)]
    total_weight = float(sum(weights))
    bias = 0.0

    for item, w in zip(matches, weights):
        home_team = str(item.get("home_team", ""))
        away_team = str(item.get("away_team", ""))
        hs = _safe_float(item.get("home_score"), 0.0)
        av = _safe_float(item.get("away_score"), 0.0)

        if home_team == home_name and away_team == away_name:
            bias += (hs - av) * w
        elif home_team == away_name and away_team == home_name:
            bias += (av - hs) * w

    return _clamp((bias / total_weight) * 0.035, -0.045, 0.045)


def _sample_size_factor(stats: Optional[Dict[str, Any]]) -> float:
    played_home = _parse_avg_number(_nested(stats or {}, ["fixtures", "played", "home"]))
    played_away = _parse_avg_number(_nested(stats or {}, ["fixtures", "played", "away"]))
    played_total = _parse_avg_number(_nested(stats or {}, ["fixtures", "played", "total"]))
    played = _avg([played_home, played_away, played_total], 0.0)
    return _clamp(played / 22.0, 0.25, 1.0)


def _league_goal_baselines(fixture: Dict[str, Any]) -> Dict[str, float]:
    gf_home = _safe_float(fixture.get("gf_home"), 0.0)
    ga_home = _safe_float(fixture.get("ga_home"), 0.0)
    gf_away = _safe_float(fixture.get("gf_away"), 0.0)
    ga_away = _safe_float(fixture.get("ga_away"), 0.0)

    base_home = _avg(
        [gf_home if gf_home > 0 else None, ga_away if ga_away > 0 else None, LEAGUE_BASELINES["goals_home"]],
        LEAGUE_BASELINES["goals_home"],
    )
    base_away = _avg(
        [gf_away if gf_away > 0 else None, ga_home if ga_home > 0 else None, LEAGUE_BASELINES["goals_away"]],
        LEAGUE_BASELINES["goals_away"],
    )

    return {
        "home": _clamp(base_home, 1.00, 1.90),
        "away": _clamp(base_away, 0.82, 1.60),
    }


def implied_prob(decimal_odds: Optional[float]) -> Optional[float]:
    if not decimal_odds or decimal_odds <= 1.0:
        return None
    return 1.0 / decimal_odds


def _remove_overround_1x2(home: Optional[float], draw: Optional[float], away: Optional[float]) -> Dict[str, Optional[float]]:
    raw_home = implied_prob(home)
    raw_draw = implied_prob(draw)
    raw_away = implied_prob(away)
    valid = [x for x in [raw_home, raw_draw, raw_away] if x is not None]
    total = sum(valid)
    if total <= 0:
        return {"home": raw_home, "draw": raw_draw, "away": raw_away, "overround": None, "vigorish": None}
    return {
        "home": raw_home / total if raw_home is not None else None,
        "draw": raw_draw / total if raw_draw is not None else None,
        "away": raw_away / total if raw_away is not None else None,
        "overround": total,
        "vigorish": max(0.0, total - 1.0),
    }


def _shrink_towards_baseline(value: float, baseline: float, quality: float, sample_factor: float) -> float:
    strength = _clamp((quality * 0.50) + (sample_factor * 0.50), 0.15, 1.0)
    return baseline + (value - baseline) * strength


def _resolve_goal_metric(explicit: Any, fallback: Optional[float], baseline: float) -> float:
    explicit_num = _parse_avg_number(explicit)
    if explicit_num is not None and explicit_num > 0:
        return explicit_num
    if fallback is not None and fallback > 0:
        return fallback
    return baseline


def _resolve_optional_metric(explicit: Any, fallback: Optional[float]) -> Optional[float]:
    explicit_num = _parse_avg_number(explicit)
    if explicit_num is not None and explicit_num > 0:
        return explicit_num
    if fallback is not None and fallback > 0:
        return fallback
    return None


def _normalize_cards_metric(explicit: Any, fallback: Optional[float], stats: Optional[Dict[str, Any]]) -> Optional[float]:
    explicit_num = _parse_avg_number(explicit)
    if explicit_num is not None and explicit_num > 0:
        if explicit_num > 10:
            played_home = _parse_avg_number(_nested(stats or {}, ["fixtures", "played", "home"]))
            played_away = _parse_avg_number(_nested(stats or {}, ["fixtures", "played", "away"]))
            played_total = _parse_avg_number(_nested(stats or {}, ["fixtures", "played", "total"]))
            played = _avg([played_home, played_away, played_total], 0.0)
            if played > 0:
                return explicit_num / played
            return fallback
        return explicit_num
    if fallback is not None and fallback > 0:
        return fallback
    return None


def _resolve_form_factor(explicit: Any, fallback: float) -> float:
    explicit_num = _parse_avg_number(explicit)
    if explicit_num is None or explicit_num <= 0:
        return fallback
    if explicit_num <= 1.20:
        return _clamp(explicit_num, 0.88, 1.12)
    if explicit_num <= 3.0:
        return _clamp(0.92 + (explicit_num / 3.0) * 0.14, 0.92, 1.06)
    return fallback


def _dixon_coles_adjustment(i: int, j: int, lambda_home: float, lambda_away: float, rho: float) -> float:
    if i == 0 and j == 0:
        return 1.0 - (lambda_home * lambda_away * rho)
    if i == 0 and j == 1:
        return 1.0 + (lambda_home * rho)
    if i == 1 and j == 0:
        return 1.0 + (lambda_away * rho)
    if i == 1 and j == 1:
        return 1.0 - rho
    return 1.0


def score_matrix(home_lambda: float, away_lambda: float, rho: float = -0.05) -> List[List[float]]:
    home_dist = poisson_dist(home_lambda, MAX_GOALS)
    away_dist = poisson_dist(away_lambda, MAX_GOALS)

    matrix: List[List[float]] = []
    for i, hp in enumerate(home_dist):
        row = []
        for j, ap in enumerate(away_dist):
            tau = _dixon_coles_adjustment(i, j, home_lambda, away_lambda, rho)
            row.append(max(0.0, hp * ap * tau))
        matrix.append(row)

    total = sum(sum(row) for row in matrix)
    if total > 0:
        matrix = [[cell / total for cell in row] for row in matrix]
    return matrix


def outcome_probs(matrix: List[List[float]]) -> Dict[str, float]:
    home = draw = away = 0.0
    btts = over15 = over25 = over35 = under45 = 0.0

    for i, row in enumerate(matrix):
        for j, prob in enumerate(row):
            if i > j:
                home += prob
            elif i == j:
                draw += prob
            else:
                away += prob

            goals = i + j
            if i >= 1 and j >= 1:
                btts += prob
            if goals >= 2:
                over15 += prob
            if goals >= 3:
                over25 += prob
            if goals >= 4:
                over35 += prob
            if goals <= 4:
                under45 += prob

    return {
        "home": home,
        "draw": draw,
        "away": away,
        "btts": btts,
        "over15": over15,
        "over25": over25,
        "over35": over35,
        "under45": under45,
    }


def normalize_probs(home: float, draw: float, away: float) -> Tuple[float, float, float]:
    total = home + draw + away
    if total <= 0:
        return 0.38, 0.24, 0.38
    return home / total, draw / total, away / total


def _calibrated_binary_prob(prob: float, quality: float, floor: float = 0.08, ceiling: float = 0.92) -> float:
    p = _clamp(prob, EPSILON, 1.0 - EPSILON)
    logit = math.log(p / (1.0 - p))
    shrink = _clamp(0.48 + 0.42 * quality, 0.48, 0.90)
    adjusted = 1.0 / (1.0 + math.exp(-logit * shrink))
    mean_revert = 0.12 + (1.0 - quality) * 0.14
    adjusted = adjusted * (1.0 - mean_revert) + 0.50 * mean_revert
    return _clamp(adjusted, floor, ceiling)


def _calibrate_1x2(home: float, draw: float, away: float, quality: float) -> Tuple[float, float, float]:
    center_home = 0.40
    center_draw = 0.25
    center_away = 0.35

    shrink = _clamp(0.38 + 0.42 * quality, 0.38, 0.82)
    draw_shrink = _clamp(0.60 + 0.22 * quality, 0.60, 0.82)

    home = center_home + (home - center_home) * shrink
    draw = center_draw + (draw - center_draw) * draw_shrink
    away = center_away + (away - center_away) * shrink

    floor_main = 0.07 + (1.0 - quality) * 0.05
    floor_draw = 0.09 + (1.0 - quality) * 0.04
    ceiling_main = 0.88 - (1.0 - quality) * 0.05

    home = _clamp(home, floor_main, ceiling_main)
    draw = _clamp(draw, floor_draw, 0.42)
    away = _clamp(away, floor_main, ceiling_main)

    total = home + draw + away
    if total <= 0:
        return 0.40, 0.24, 0.36

    home /= total
    draw /= total
    away /= total

    home = _clamp(home, floor_main, ceiling_main)
    draw = _clamp(draw, floor_draw, 0.42)
    away = _clamp(away, floor_main, ceiling_main)

    total = home + draw + away
    return home / total, draw / total, away / total


def extract_team_stats(stats: Optional[Dict[str, Any]], side: str) -> Dict[str, Any]:
    stats = stats or {}

    goal_for_home = _parse_avg_number(_nested(stats, ["goals", "for", "average", "home"]))
    goal_for_away = _parse_avg_number(_nested(stats, ["goals", "for", "average", "away"]))
    goal_for_total = _parse_avg_number(_nested(stats, ["goals", "for", "average", "total"]))
    goal_against_home = _parse_avg_number(_nested(stats, ["goals", "against", "average", "home"]))
    goal_against_away = _parse_avg_number(_nested(stats, ["goals", "against", "average", "away"]))
    goal_against_total = _parse_avg_number(_nested(stats, ["goals", "against", "average", "total"]))

    corners_for_home = _parse_avg_number(_nested(stats, ["corners", "for", "average", "home"]))
    corners_for_away = _parse_avg_number(_nested(stats, ["corners", "for", "average", "away"]))
    corners_for_total = _parse_avg_number(_nested(stats, ["corners", "for", "average", "total"]))
    corners_against_home = _parse_avg_number(_nested(stats, ["corners", "against", "average", "home"]))
    corners_against_away = _parse_avg_number(_nested(stats, ["corners", "against", "average", "away"]))
    corners_against_total = _parse_avg_number(_nested(stats, ["corners", "against", "average", "total"]))

    shots_for_home = _parse_avg_number(_nested(stats, ["shots", "for", "average", "home"]))
    shots_for_away = _parse_avg_number(_nested(stats, ["shots", "for", "average", "away"]))
    shots_for_total = _parse_avg_number(_nested(stats, ["shots", "for", "average", "total"]))
    shots_on_home = _parse_avg_number(_nested(stats, ["shots", "on", "average", "home"]))
    shots_on_away = _parse_avg_number(_nested(stats, ["shots", "on", "average", "away"]))
    shots_on_total = _parse_avg_number(_nested(stats, ["shots", "on", "average", "total"]))

    yellow_home = _parse_avg_number(_nested(stats, ["cards", "yellow", "average", "home"]))
    yellow_away = _parse_avg_number(_nested(stats, ["cards", "yellow", "average", "away"]))
    yellow_total = _parse_avg_number(_nested(stats, ["cards", "yellow", "average", "total"]))

    if side == "home":
        gf = next((v for v in [goal_for_home, goal_for_total] if v is not None and v > 0), None)
        ga = next((v for v in [goal_against_home, goal_against_total] if v is not None and v > 0), None)
        cf = next((v for v in [corners_for_home, corners_for_total] if v is not None and v > 0), None)
        ca = next((v for v in [corners_against_home, corners_against_total] if v is not None and v > 0), None)
        shots = next((v for v in [shots_for_home, shots_for_total] if v is not None and v > 0), None)
        shots_on = next((v for v in [shots_on_home, shots_on_total] if v is not None and v > 0), None)
        yellow = next((v for v in [yellow_home, yellow_total] if v is not None and v > 0), None)
    else:
        gf = next((v for v in [goal_for_away, goal_for_total] if v is not None and v > 0), None)
        ga = next((v for v in [goal_against_away, goal_against_total] if v is not None and v > 0), None)
        cf = next((v for v in [corners_for_away, corners_for_total] if v is not None and v > 0), None)
        ca = next((v for v in [corners_against_away, corners_against_total] if v is not None and v > 0), None)
        shots = next((v for v in [shots_for_away, shots_for_total] if v is not None and v > 0), None)
        shots_on = next((v for v in [shots_on_away, shots_on_total] if v is not None and v > 0), None)
        yellow = next((v for v in [yellow_away, yellow_total] if v is not None and v > 0), None)

    sample_factor = _sample_size_factor(stats)

    return {
        "gf": _clamp(gf, 0.30, 3.10) if gf is not None else None,
        "ga": _clamp(ga, 0.30, 3.10) if ga is not None else None,
        "cf": _clamp(cf, 1.5, 9.2) if cf is not None else None,
        "ca": _clamp(ca, 1.5, 9.2) if ca is not None else None,
        "shots": _clamp(shots, 4.5, 20.5) if shots is not None else None,
        "shots_on": _clamp(shots_on, 1.0, 7.5) if shots_on is not None else None,
        "yellow": _clamp(yellow, 0.7, 5.0) if yellow is not None else None,
        "form_factor": _form_factor(stats.get("form")),
        "sample_factor": sample_factor,
    }


def _collect_odds_map(raw_odds: Any) -> Dict[str, Any]:
    if raw_odds is None:
        return {}
    if hasattr(raw_odds, "model_dump"):
        raw_odds = raw_odds.model_dump()

    normalized: Dict[str, Any] = {}

    def _slug(value: Any) -> str:
        return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")

    def _store(prefix: str, value: Any) -> None:
        key = prefix.lower().strip("_")
        if key:
            incoming = _safe_float(value, 0.0)
            existing = _safe_float(normalized.get(key), 0.0)
            if incoming > 1.0:
                if incoming >= existing:
                    normalized[key] = value
            elif key not in normalized:
                normalized[key] = value

    def _store_market_value(market_name: str, selection_name: str, odd_value: Any) -> None:
        market = _slug(market_name)
        selection = _slug(selection_name)
        if not market or not selection:
            return

        alias_map = {
            ("match_winner", "home"): ["home", "match_winner_home", "1x2_home", "match_result_home", "winner_home", "match_winner_1_home", "1"],
            ("match_winner", "draw"): ["draw", "match_winner_draw", "1x2_draw", "match_result_draw", "winner_draw", "match_winner_x_draw", "x"],
            ("match_winner", "away"): ["away", "match_winner_away", "1x2_away", "match_result_away", "winner_away", "match_winner_2_away", "2"],
            ("double_chance", "home/draw"): ["double_chance_1x", "dc_1x", "1x"],
            ("double_chance", "home_or_draw"): ["double_chance_1x", "dc_1x", "1x"],
            ("double_chance", "1x"): ["double_chance_1x", "dc_1x", "1x"],
            ("double_chance", "draw/away"): ["double_chance_x2", "dc_x2", "x2"],
            ("double_chance", "draw_or_away"): ["double_chance_x2", "dc_x2", "x2"],
            ("double_chance", "x2"): ["double_chance_x2", "dc_x2", "x2"],
            ("double_chance", "home/away"): ["double_chance_12", "dc_12", "12"],
            ("double_chance", "home_or_away"): ["double_chance_12", "dc_12", "12"],
            ("double_chance", "12"): ["double_chance_12", "dc_12", "12"],
            ("goals_over/under", "over_1.5"): ["over15", "over_1_5", "goals_over_1_5", "totals_over_1_5", "total_goals_over_1_5"],
            ("goals_over/under", "over_2.5"): ["over25", "over_2_5", "goals_over_2_5", "totals_over_2_5", "total_goals_over_2_5"],
            ("goals_over/under", "over_3.5"): ["over35", "over_3_5", "goals_over_3_5", "totals_over_3_5", "total_goals_over_3_5"],
            ("goals_over/under", "under_4.5"): ["under45", "under_4_5", "goals_under_4_5", "totals_under_4_5", "total_goals_under_4_5"],
            ("both_teams_to_score", "yes"): ["btts_yes", "both_teams_to_score_yes", "gg_yes", "btts", "both_teams_score_yes"],
            ("team_home_score", "yes"): ["team_home_score_yes", "home_team_to_score_yes", "home_score_yes"],
            ("team_away_score", "yes"): ["team_away_score_yes", "away_team_to_score_yes", "away_score_yes"],
        }

        aliases = alias_map.get((market, selection), [])
        for alias in aliases:
            _store(alias, odd_value)
            _store(f"{market}_{selection}_{alias}", odd_value)

        line_match = re.search(r"(?:over|más_de|mas_de|above|under)\s*_?(\d+(?:[._]\d+)?)", selection)
        if line_match:
            line_token = line_match.group(1).replace(".", "_")
            if "corner" in market:
                _store(f"corners_over_{line_token}", odd_value)
                if "home" in selection or "local" in selection:
                    _store(f"corners_home_over_{line_token}", odd_value)
                elif "away" in selection or "visitante" in selection:
                    _store(f"corners_away_over_{line_token}", odd_value)
            if any(token in market for token in ["card", "tarjet", "booking", "yellow"]):
                _store(f"cards_over_{line_token}", odd_value)
                if "home" in selection or "local" in selection:
                    _store(f"cards_home_over_{line_token}", odd_value)
                elif "away" in selection or "visitante" in selection:
                    _store(f"cards_away_over_{line_token}", odd_value)

    def _walk(prefix: str, obj: Any) -> None:
        if hasattr(obj, "model_dump"):
            obj = obj.model_dump()

        if isinstance(obj, dict):
            name = str(obj.get("name") or obj.get("label") or obj.get("key") or "").strip().lower()
            value = obj.get("value")
            if name and value is not None:
                slug = name.replace(" ", "_").replace("-", "_")
                _store(slug, value)
                if prefix:
                    _store(f"{prefix}_{slug}", value)

            values = obj.get("values")
            if name and isinstance(values, list):
                for item in values:
                    if hasattr(item, "model_dump"):
                        item = item.model_dump()
                    if not isinstance(item, dict):
                        continue
                    selection = item.get("value") or item.get("label") or item.get("name")
                    odd_value = item.get("odd")
                    if selection is not None and odd_value is not None:
                        _store_market_value(name, selection, odd_value)

            for k, v in obj.items():
                key = f"{prefix}_{k}" if prefix else str(k)
                _walk(key, v)
            return

        if isinstance(obj, list):
            for index, item in enumerate(obj):
                _walk(f"{prefix}_{index}" if prefix else str(index), item)
            return

        _store(prefix, obj)

    _walk("", raw_odds)
    return normalized



def _pick_odds(flat: Dict[str, Any], *aliases: str) -> Optional[float]:
    for alias in aliases:
        value = flat.get(alias.lower())
        odd = _safe_float(value, 0.0)
        if odd > 1.0:
            return odd
    return None


def _nested_bool(data: Dict[str, Any], path: List[str]) -> Optional[bool]:
    value = _nested(data, path, None)
    if isinstance(value, bool):
        return value
    return None


def _extract_threshold_odd(raw: Any) -> Dict[str, Optional[float]]:
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Optional[float]] = {}
    for key, value in raw.items():
        norm_key = str(key or "").strip().lower().replace(".", "_")
        odd = _safe_float(value, 0.0)
        if odd > 1.0:
            out[norm_key] = odd
    return out


def _threshold_aliases(key: str) -> List[str]:
    raw = str(key or "").strip().lower()
    normalized = raw.replace(".", "_").replace("-", "_").replace(" ", "_")
    aliases = {normalized}
    if normalized and normalized[0].isdigit():
        aliases.add(f"over_{normalized}")
        aliases.add(f"over{normalized}")
    return [alias for alias in aliases if alias]


def _prefix_threshold_keys(raw: Dict[str, Optional[float]], prefix: str) -> Dict[str, Optional[float]]:
    out: Dict[str, Optional[float]] = {}
    safe_prefix = str(prefix or "").strip().lower()
    if not safe_prefix:
        return out
    for key, value in raw.items():
        for alias in _threshold_aliases(key):
            out[f"{safe_prefix}_{alias}"] = value
    return out


def _extract_market_catalog_odds(raw_catalog: Any) -> Dict[str, Any]:
    if hasattr(raw_catalog, "model_dump"):
        raw_catalog = raw_catalog.model_dump()

    catalog = raw_catalog if isinstance(raw_catalog, list) else [raw_catalog]
    mapped: Dict[str, Any] = {}

    for item in catalog:
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        if not isinstance(item, dict):
            continue

        family = str(item.get("family") or item.get("group") or item.get("market_family") or "").lower()
        scope = str(item.get("scope") or item.get("team_scope") or item.get("side") or item.get("selection") or "").lower()
        line = str(item.get("line") or item.get("threshold") or item.get("total") or "").strip().replace(".", "_")
        odd = item.get("odd", item.get("odds", item.get("price")))
        odd_value = _safe_float(odd, 0.0)
        if odd_value <= 1.0:
            continue

        if "corner" in family and line:
            if "home" in scope:
                mapped[f"corners_home_over_{line}"] = odd_value
            elif "away" in scope:
                mapped[f"corners_away_over_{line}"] = odd_value
            else:
                mapped[f"corners_over_{line}"] = odd_value
        elif "card" in family and line:
            if "home" in scope:
                mapped[f"cards_home_over_{line}"] = odd_value
            elif "away" in scope:
                mapped[f"cards_away_over_{line}"] = odd_value
            else:
                mapped[f"cards_over_{line}"] = odd_value

    return mapped


def _line_and_direction_from_key(raw_key: str) -> Tuple[Optional[float], Optional[str]]:
    key = str(raw_key or "").lower().replace("-", "_")
    match = re.search(r"(over|under)[_\s]?(\d+(?:[_\.]\d+)?)", key)
    if not match:
        return None, None
    cleaned = match.group(2).replace("_", ".")
    try:
        return float(cleaned), match.group(1)
    except ValueError:
        return None, None


def _period_from_key(raw_key: str) -> str:
    key = raw_key.lower()
    if "first_half" in key or "1st_half" in key or "1h_" in key or key.startswith("1h"):
        return "1H"
    if "second_half" in key or "2nd_half" in key or "2h_" in key or key.startswith("2h"):
        return "2H"
    return "FT"


def _extract_dynamic_over_markets(flat: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    families = {
        "corners": ("corners", "corner"),
        "cards": ("cards", "card", "tarjet", "booking", "yellow", "amarilla"),
        "shots_on_target": ("shots_on_target", "sot", "shots_on", "tiros_a_puerta"),
        "shots": ("shots", "shot", "tiros"),
        "fouls": ("fouls", "foul", "faltas"),
        "offsides": ("offsides", "offside", "fuera_de_juego"),
    }

    for raw_key, raw_value in flat.items():
        odd = _safe_float(raw_value, 0.0)
        if odd <= 1.0:
            continue
        key = str(raw_key or "").lower()
        if "over" not in key and "under" not in key:
            continue
        line, direction = _line_and_direction_from_key(key)
        if line is None or line < 0.5:
            continue

        family = None
        for candidate, aliases in families.items():
            if any(alias in key for alias in aliases):
                family = candidate
                break
        if family is None:
            continue

        scope = "total"
        if "_home_" in key or key.startswith("home_") or "_local_" in key:
            scope = "home"
        elif "_away_" in key or key.startswith("away_") or "_visitante_" in key:
            scope = "away"

        out.append(
            {
                "family": family,
                "scope": scope,
                "line": line,
                "direction": direction or "over",
                "odd": odd,
                "period": _period_from_key(key),
                "source_key": key,
            }
        )
    return out


def extract_odds(fixture: Dict[str, Any]) -> Dict[str, Optional[float]]:
    sources = []
    flat: Dict[str, Any] = {}
    odds_obj = fixture.get("odds")
    if odds_obj:
        sources.append(odds_obj)
        if isinstance(odds_obj, dict):
            totals = odds_obj.get("totals") or {}
            goals = totals.get("goals") or {}
            corners = totals.get("corners") or {}
            cards = totals.get("cards") or {}
            fouls = totals.get("fouls") or {}
            offsides = totals.get("offsides") or {}
            shots_totals = totals.get("shots") or {}
            sot_totals = totals.get("shots_on_target") or {}

            if isinstance(goals, dict):
                flat.update(goals)
            if isinstance(corners, dict):
                flat.update(_prefix_threshold_keys(_extract_threshold_odd(corners), "corners"))
            if isinstance(cards, dict):
                flat.update(_prefix_threshold_keys(_extract_threshold_odd(cards), "cards"))
            if isinstance(fouls, dict):
                flat.update(_prefix_threshold_keys(_extract_threshold_odd(fouls), "fouls"))
            if isinstance(offsides, dict):
                flat.update(_prefix_threshold_keys(_extract_threshold_odd(offsides), "offsides"))
            if isinstance(shots_totals, dict):
                flat.update(_prefix_threshold_keys(_extract_threshold_odd(shots_totals), "shots"))
            if isinstance(sot_totals, dict):
                flat.update(_prefix_threshold_keys(_extract_threshold_odd(sot_totals), "shots_on_target"))

            home_shots = _nested(odds_obj, ["totals", "shots", "home_first_over", "odd"])
            away_shots = _nested(odds_obj, ["totals", "shots", "away_first_over", "odd"])
            home_sot = _nested(odds_obj, ["totals", "shots_on_target", "home_first_over", "odd"])
            away_sot = _nested(odds_obj, ["totals", "shots_on_target", "away_first_over", "odd"])
            if home_shots is not None:
                flat["shots_home"] = home_shots
            if away_shots is not None:
                flat["shots_away"] = away_shots
            if home_sot is not None:
                flat["sot_home"] = home_sot
            if away_sot is not None:
                flat["sot_away"] = away_sot

    for key in ["bookmakers", "markets", "odds_data", "market_odds"]:
        if fixture.get(key):
            sources.append(fixture.get(key))
    if fixture.get("market_catalog"):
        market_catalog_odds = _extract_market_catalog_odds(fixture.get("market_catalog"))
        flat.update(market_catalog_odds)
        sources.append(fixture.get("market_catalog"))

    top_level = {
        key: fixture.get(key)
        for key in [
            "home", "draw", "away", "home_odds", "draw_odds", "away_odds",
            "odds_home", "odds_draw", "odds_away", "match_winner_home", "match_winner_draw", "match_winner_away",
            "dc_1x", "dc_x2", "dc_12", "over15", "over25", "over35", "under45", "btts_yes",
            "over75_corners", "over85_corners", "over95_corners", "over35_cards", "over45_cards",
        ]
        if fixture.get(key) is not None
    }
    if top_level:
        sources.append(top_level)

    collection_meta = fixture.get("collection_meta")
    if collection_meta:
        sources.append(collection_meta)

    for source in sources:
        flat.update(_collect_odds_map(source))

    odds = {
        "home": _pick_odds(flat, "home", "home_odds", "odds_home", "match_winner_home", "1x2_home", "match_result_home", "winner_home", "match_winner_1_home"),
        "draw": _pick_odds(flat, "draw", "draw_odds", "odds_draw", "match_winner_draw", "1x2_draw", "match_result_draw", "winner_draw", "match_winner_x_draw"),
        "away": _pick_odds(flat, "away", "away_odds", "odds_away", "match_winner_away", "1x2_away", "match_result_away", "winner_away", "match_winner_2_away"),
        "over15": _pick_odds(flat, "over15", "over_1_5", "goals_over_1_5", "totals_over_1_5", "total_goals_over_1_5"),
        "over25": _pick_odds(flat, "over25", "over_2_5", "goals_over_2_5", "totals_over_2_5", "total_goals_over_2_5"),
        "over35": _pick_odds(flat, "over35", "over_3_5", "goals_over_3_5", "totals_over_3_5", "total_goals_over_3_5"),
        "under45": _pick_odds(flat, "under45", "under_4_5", "goals_under_4_5", "totals_under_4_5", "total_goals_under_4_5"),
        "btts_yes": _pick_odds(flat, "btts_yes", "both_teams_to_score_yes", "gg_yes", "btts", "both_teams_score_yes"),
        "dc_1x": _pick_odds(flat, "double_chance_1x", "dc_1x", "1x", "doublechance_1x"),
        "dc_x2": _pick_odds(flat, "double_chance_x2", "dc_x2", "x2", "doublechance_x2"),
        "dc_12": _pick_odds(flat, "double_chance_12", "dc_12", "12", "doublechance_12"),
        "over75_corners": _pick_odds(flat, "over75_corners", "corners_over_7_5", "over_7_5_corners", "total_corners_over_7_5", "corners_7_5"),
        "over85_corners": _pick_odds(flat, "over85_corners", "corners_over_8_5", "over_8_5_corners", "total_corners_over_8_5", "corners_8_5"),
        "over95_corners": _pick_odds(flat, "over95_corners", "corners_over_9_5", "over_9_5_corners", "total_corners_over_9_5", "corners_9_5"),
        "over35_cards": _pick_odds(flat, "over35_cards", "cards_over_3_5", "over_3_5_cards", "total_cards_over_3_5", "cards_3_5"),
        "over45_cards": _pick_odds(flat, "over45_cards", "cards_over_4_5", "over_4_5_cards", "total_cards_over_4_5", "cards_4_5"),
        "corners_home_over_3_5": _pick_odds(flat, "corners_home_over_3_5", "home_corners_over_3_5"),
        "corners_home_over_4_5": _pick_odds(flat, "corners_home_over_4_5", "home_corners_over_4_5"),
        "corners_away_over_3_5": _pick_odds(flat, "corners_away_over_3_5", "away_corners_over_3_5"),
        "corners_away_over_4_5": _pick_odds(flat, "corners_away_over_4_5", "away_corners_over_4_5"),
        "cards_home_over_1_5": _pick_odds(flat, "cards_home_over_1_5", "home_cards_over_1_5"),
        "cards_home_over_2_5": _pick_odds(flat, "cards_home_over_2_5", "home_cards_over_2_5"),
        "cards_away_over_1_5": _pick_odds(flat, "cards_away_over_1_5", "away_cards_over_1_5"),
        "cards_away_over_2_5": _pick_odds(flat, "cards_away_over_2_5", "away_cards_over_2_5"),
        "team_home_score_yes": _pick_odds(flat, "team_home_score_yes", "home_team_to_score_yes", "home_score_yes"),
        "team_away_score_yes": _pick_odds(flat, "team_away_score_yes", "away_team_to_score_yes", "away_score_yes"),
        "team_home_over_0_5": _pick_odds(flat, "team_home_over_0_5", "home_over_0_5_goals", "home_team_goals_over_0_5"),
        "team_home_over_1_5": _pick_odds(flat, "team_home_over_1_5", "home_over_1_5_goals", "home_team_goals_over_1_5"),
        "team_away_over_0_5": _pick_odds(flat, "team_away_over_0_5", "away_over_0_5_goals", "away_team_goals_over_0_5"),
        "team_away_over_1_5": _pick_odds(flat, "team_away_over_1_5", "away_over_1_5_goals", "away_team_goals_over_1_5"),
        "shots_home": _pick_odds(flat, "shots_home", "home_shots_over"),
        "shots_away": _pick_odds(flat, "shots_away", "away_shots_over"),
        "sot_home": _pick_odds(flat, "sot_home", "home_shots_on_target_over"),
        "sot_away": _pick_odds(flat, "sot_away", "away_shots_on_target_over"),
        "shots_home_over_x": _pick_odds(flat, "shots_home_over_x", "home_shots_over_x", "shots_home_over"),
        "shots_away_over_x": _pick_odds(flat, "shots_away_over_x", "away_shots_over_x", "shots_away_over"),
        "sot_home_over_x": _pick_odds(flat, "sot_home_over_x", "home_sot_over_x", "sot_home_over"),
        "sot_away_over_x": _pick_odds(flat, "sot_away_over_x", "away_sot_over_x", "sot_away_over"),
        "shots_home_line": _safe_float(flat.get("shots_home_line"), 0.0) or None,
        "shots_away_line": _safe_float(flat.get("shots_away_line"), 0.0) or None,
        "sot_home_line": _safe_float(flat.get("sot_home_line"), 0.0) or None,
        "sot_away_line": _safe_float(flat.get("sot_away_line"), 0.0) or None,
    }
    odds["dynamic_over_markets"] = _extract_dynamic_over_markets(flat)
    return odds


def _market_name(code: str, home_name: str, away_name: str) -> str:
    mapping = {
        "1X2_HOME": f"Gana {home_name}",
        "1X2_DRAW": "Empate",
        "1X2_AWAY": f"Gana {away_name}",
        "DC_1X": f"{home_name} o empate",
        "DC_X2": f"{away_name} o empate",
        "DC_12": "No empate",
        "OVER15": "Más de 1.5 goles",
        "OVER25": "Más de 2.5 goles",
        "OVER35": "Más de 3.5 goles",
        "UNDER45": "Menos de 4.5 goles",
        "BTTS_YES": "Ambos marcan",
        "O75_CORNERS": "Más de 7.5 corners",
        "O85_CORNERS": "Más de 8.5 corners",
        "O95_CORNERS": "Más de 9.5 corners",
        "O35_CARDS": "Más de 3.5 tarjetas",
        "O45_CARDS": "Más de 4.5 tarjetas",
        "SHOTS_HOME": f"{home_name} tiros altos",
        "SHOTS_AWAY": f"{away_name} tiros altos",
        "SOT_HOME": f"{home_name} tiros a puerta altos",
        "SOT_AWAY": f"{away_name} tiros a puerta altos",
        "CORNERS_HOME_OVER_3_5": f"{home_name} más de 3.5 corners",
        "CORNERS_HOME_OVER_4_5": f"{home_name} más de 4.5 corners",
        "CORNERS_AWAY_OVER_3_5": f"{away_name} más de 3.5 corners",
        "CORNERS_AWAY_OVER_4_5": f"{away_name} más de 4.5 corners",
        "CARDS_HOME_OVER_1_5": f"{home_name} más de 1.5 tarjetas",
        "CARDS_HOME_OVER_2_5": f"{home_name} más de 2.5 tarjetas",
        "CARDS_AWAY_OVER_1_5": f"{away_name} más de 1.5 tarjetas",
        "CARDS_AWAY_OVER_2_5": f"{away_name} más de 2.5 tarjetas",
        "TEAM_HOME_SCORE_YES": f"{home_name} marcará (sí)",
        "TEAM_AWAY_SCORE_YES": f"{away_name} marcará (sí)",
        "TEAM_HOME_OVER_0_5": f"{home_name} más de 0.5 goles",
        "TEAM_HOME_OVER_1_5": f"{home_name} más de 1.5 goles",
        "TEAM_AWAY_OVER_0_5": f"{away_name} más de 0.5 goles",
        "TEAM_AWAY_OVER_1_5": f"{away_name} más de 1.5 goles",
        "SHOTS_HOME_OVER_X": f"{home_name} tiros over X",
        "SHOTS_AWAY_OVER_X": f"{away_name} tiros over X",
        "SOT_HOME_OVER_X": f"{home_name} tiros a puerta over X",
        "SOT_AWAY_OVER_X": f"{away_name} tiros a puerta over X",
    }
    return mapping.get(code, code)


def _market_group(code: str) -> str:
    return MARKET_PROFILES.get(code, {}).get("group", "Otros")


def _market_reliability(code: str) -> float:
    return MARKET_PROFILES.get(code, {}).get("reliability", 0.65)


def _market_volatility(code: str) -> float:
    return MARKET_PROFILES.get(code, {}).get("volatility", 0.50)


def _market_edge_threshold(code: str) -> float:
    return MARKET_PROFILES.get(code, {}).get("edge_threshold", 0.05)


def _signal_bucket(edge: float, prob: float, stability: float, reliability: float, has_odds: bool) -> str:
    if not has_odds:
        if prob >= 0.68 and stability >= 0.60:
            return "model_strong"
        if prob >= 0.60:
            return "model"
        return "watch"

    if edge >= 0.060 and prob >= 0.52:
        return "strong_value"
    if edge >= 0.030 and prob >= 0.50:
        return "medium_value"
    if edge >= 0.015:
        return "low_value"
    if edge >= -0.010 and (prob >= 0.58 or (stability >= 0.62 and reliability >= 0.75)):
        return "lean"
    return "watch"


def _shots_data_quality(shots: Optional[float], shots_on: Optional[float], sample_factor: float, overall_quality: float) -> float:
    availability = 1.0 if (shots is not None and shots > 0 and shots_on is not None and shots_on > 0) else 0.0
    return _clamp(0.32 * availability + 0.30 * sample_factor + 0.38 * overall_quality, 0.0, 1.0)


def _confidence_from_signal(prob: float, quality: float, edge: float, reliability: float, stability: float) -> int:
    score = (
        prob * 100.0 * 0.38
        + quality * 22.0
        + max(edge, 0.0) * 115.0
        + reliability * 18.0
        + stability * 13.0
    )
    return int(round(_clamp(score, 45, 93)))


def _pricing_flags(model_prob: float, fair_market_prob: Optional[float], odd: Optional[float], code: str) -> Dict[str, Any]:
    if fair_market_prob is None or odd is None or odd <= 1.0:
        return {
            "edge": 0.0,
            "es_value_bet": False,
            "soft_value": False,
            "posible_error_cuota": False,
            "cuota_sospechosa": False,
            "oportunidad_detectada": False,
            "probabilidad_implicita": None,
            "probabilidad_justa": None,
        }

    edge = model_prob - fair_market_prob
    edge_threshold = _market_edge_threshold(code)
    soft_threshold = max(0.015, edge_threshold * 0.42)
    suspicious_gap = edge >= max(INTEGRITY_SUSPICIOUS_EDGE_FLOOR, edge_threshold * 2.1)
    high_odd = odd >= INTEGRITY_HIGH_ODD_THRESHOLD and model_prob >= INTEGRITY_HIGH_MODEL_PROB_THRESHOLD
    depressed_price = odd <= 1.35 and model_prob <= 0.58 and edge <= INTEGRITY_SOFT_NEGATIVE_EDGE

    return {
        "edge": edge,
        "es_value_bet": edge >= edge_threshold,
        "soft_value": edge >= soft_threshold,
        "posible_error_cuota": suspicious_gap or high_odd,
        "cuota_sospechosa": suspicious_gap or high_odd or depressed_price,
        "oportunidad_detectada": edge >= soft_threshold or suspicious_gap or high_odd,
        "probabilidad_implicita": 1.0 / odd,
        "probabilidad_justa": fair_market_prob,
    }


def _build_market(
    code: str,
    prob: float,
    odd: Optional[float],
    market_prob: Optional[float],
    quality: float,
    data_quality: float,
    home_name: str,
    away_name: str,
    line: Optional[float] = None,
    market_name_override: Optional[str] = None,
    market_group_override: Optional[str] = None,
) -> Dict[str, Any]:
    prob = _calibrated_binary_prob(prob, _clamp((quality * 0.68) + (data_quality * 0.32), 0.35, 1.0))
    reliability = _market_reliability(code)
    volatility = _market_volatility(code)
    stability = 1.0 - volatility
    pricing = _pricing_flags(prob, market_prob, odd, code)
    ease_bonus = STABLE_MARKET_PRIORITY.get(code, 1.0)
    has_odds = odd is not None and pricing["probabilidad_implicita"] is not None
    signal_tier = _signal_bucket(pricing["edge"], prob, stability, reliability, has_odds)

    odd_penalty = 0.0
    if odd is not None:
        odd_penalty = _clamp((odd - 1.70) * 0.06, 0.0, 0.22)

    fragility = _clamp(volatility * 0.60 + (1.0 - data_quality) * 0.40, 0.0, 1.0)
    close_probability = _clamp(
        prob * 0.60
        + reliability * 0.20
        + stability * 0.15
        + data_quality * 0.05
        - odd_penalty * 0.10,
        0.01,
        0.99,
    )

    score = (
        close_probability * 0.52
        + reliability * 0.18
        + stability * 0.16
        + data_quality * 0.10
        + max(min(pricing["edge"], 0.03), -0.015) * 0.10
        - odd_penalty * 0.14
        - fragility * 0.06
    ) * ease_bonus

    return {
        "code": code,
        "mercado": market_group_override or _market_group(code),
        "jugada": market_name_override or _market_name(code, home_name, away_name),
        "prob": prob,
        "cuota": odd,
        "edge": pricing["edge"],
        "es_value_bet": pricing["es_value_bet"],
        "soft_value": pricing["soft_value"],
        "posible_error_cuota": pricing["posible_error_cuota"],
        "cuota_sospechosa": pricing["cuota_sospechosa"],
        "oportunidad_detectada": pricing["oportunidad_detectada"],
        "probabilidad_implicita": pricing["probabilidad_implicita"],
        "probabilidad_justa": pricing["probabilidad_justa"],
        "reliability": reliability,
        "stability": stability,
        "data_quality": data_quality,
        "signal_tier": signal_tier,
        "score": score,
        "close_probability": close_probability,
        "volatility": volatility,
        "fragility": fragility,
        "line": line,
    }


def _infer_dynamic_line(metric: Optional[float], low: float, high: float, default: float) -> float:
    if metric is None:
        return default
    proposal = round((metric - 0.8) * 2.0) / 2.0
    return _clamp(proposal, low, high)


def _select_primary_bet(markets: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not markets:
        return {
            "code": "OVER15",
            "mercado": "Goles",
            "jugada": "Más de 1.5 goles",
            "prob": MIN_RENDER_PROBABILITY,
            "cuota": None,
            "edge": 0.0,
            "es_value_bet": False,
            "soft_value": False,
            "posible_error_cuota": False,
            "cuota_sospechosa": False,
            "oportunidad_detectada": False,
            "reliability": 0.80,
            "stability": 0.78,
            "data_quality": 0.50,
            "signal_tier": "watch",
            "score": 0.50,
            "close_probability": MIN_RENDER_PROBABILITY,
            "volatility": 0.50,
            "fragility": 0.50,
        }

    eligible = [
        m for m in markets
        if m.get("prob", 0.0) >= MIN_RENDER_PROBABILITY
        and m.get("stability", 0.0) >= 0.45
        and m.get("reliability", 0.0) >= 0.68
        and m.get("volatility", 1.0) <= MAX_ACCEPTABLE_VOLATILITY
        and m.get("data_quality", 0.0) >= 0.48
    ]

    safe_pool = [m for m in markets if m.get("prob", 0.0) >= MIN_RENDER_PROBABILITY]
    pool = eligible if eligible else safe_pool
    if not pool:
        return {
            "code": "NO_BET",
            "mercado": "Secondary",
            "jugada": "Sin pick >=60%",
            "prob": MIN_RENDER_PROBABILITY,
            "cuota": None,
            "edge": 0.0,
            "es_value_bet": False,
            "soft_value": False,
            "posible_error_cuota": False,
            "cuota_sospechosa": False,
            "oportunidad_detectada": False,
            "reliability": 0.0,
            "stability": 0.0,
            "data_quality": 0.0,
            "signal_tier": "watch",
            "score": 0.0,
            "close_probability": MIN_RENDER_PROBABILITY,
            "volatility": 1.0,
            "fragility": 1.0,
            "probabilidad_implicita": None,
            "probabilidad_justa": None,
        }
    return max(
        pool,
        key=lambda item: (
            item.get("close_probability", 0.0),
            item.get("prob", 0.0),
            item.get("reliability", 0.0),
            item.get("stability", 0.0),
            -item.get("volatility", 1.0),
            item.get("score", 0.0),
            max(min(item.get("edge", 0.0), 0.02), -0.02),
        ),
    )


def _strong_bets(markets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ordered = sorted(
        markets,
        key=lambda item: (
            item.get("close_probability", 0.0),
            item.get("prob", 0.0),
            item.get("reliability", 0.0),
            item.get("stability", 0.0),
            -item.get("volatility", 1.0),
            item.get("score", 0.0),
            max(min(item.get("edge", 0.0), 0.02), -0.02),
        ),
        reverse=True,
    )

    out: List[Dict[str, Any]] = []
    for item in ordered:
        odd_value = item.get("cuota")
        ev_value = (item.get("prob", 0.0) * odd_value - 1.0) if odd_value is not None else None
        hard_filters = [
            item.get("prob", 0.0) >= 0.50,
            item.get("close_probability", 0.0) >= 0.50,
            item.get("reliability", 0.0) >= 0.70,
            item.get("stability", 0.0) >= 0.46,
            item.get("volatility", 1.0) <= MAX_ACCEPTABLE_VOLATILITY,
            item.get("data_quality", 0.0) >= 0.50,
            item.get("fragility", 1.0) <= 0.56,
            odd_value is not None,
            ev_value is not None and ev_value > 0.0,
        ]
        if not all(hard_filters):
            continue

        close_prob = item.get("close_probability", 0.0)
        if close_prob >= 0.74:
            prob_class = "Muy alta probabilidad"
        elif close_prob >= 0.66:
            prob_class = "Alta probabilidad"
        elif close_prob >= 0.58:
            prob_class = "Probabilidad media"
        else:
            prob_class = "Riesgo alto"

        out.append(
            {
                "mercado": item["mercado"],
                "jugada": item["jugada"],
                "probabilidad": int(round(item["prob"] * 100)),
                "probabilidad_cierre": int(round(close_prob * 100)),
                "probabilidad_nivel": prob_class,
                "cuota": round(item["cuota"], 2) if item["cuota"] else None,
                "edge": round(item["edge"] * 100, 2),
                "value": bool(item["es_value_bet"] or item.get("soft_value")),
                "signal_tier": item.get("signal_tier", "watch"),
                "signal_label": prob_class,
                "posible_error_cuota": bool(item["posible_error_cuota"]),
                "cuota_sospechosa": bool(item["cuota_sospechosa"]),
                "oportunidad_detectada": bool(item["oportunidad_detectada"]),
                "stability": round(item["stability"], 4),
                "reliability": round(item["reliability"], 4),
                "volatility": round(item.get("volatility", 0.0), 4),
                "fragility": round(item.get("fragility", 0.0), 4),
                "score": round(item["score"], 4),
            }
        )
        if len(out) >= 6:
            break

    if out:
        return out

    fallback = [
        item for item in ordered
        if item.get("prob", 0.0) >= 0.50
        and item.get("cuota") is not None
        and (item.get("prob", 0.0) * item.get("cuota", 0.0) - 1.0) > 0.0
    ][:3]
    for item in fallback:
        out.append(
            {
                "mercado": item["mercado"],
                "jugada": item["jugada"],
                "probabilidad": int(round(item["prob"] * 100)),
                "probabilidad_cierre": int(round(item.get("close_probability", item["prob"]) * 100)),
                "probabilidad_nivel": "Probabilidad media",
                "cuota": round(item["cuota"], 2) if item["cuota"] else None,
                "edge": round(item["edge"] * 100, 2),
                "value": bool(item["es_value_bet"] or item.get("soft_value")),
                "signal_tier": "top_pick",
                "signal_label": "Top pick",
                "posible_error_cuota": bool(item.get("posible_error_cuota")),
                "cuota_sospechosa": bool(item.get("cuota_sospechosa")),
                "oportunidad_detectada": bool(item.get("oportunidad_detectada")),
                "stability": round(item["stability"], 4),
                "reliability": round(item["reliability"], 4),
                "volatility": round(item.get("volatility", 0.0), 4),
                "fragility": round(item.get("fragility", 0.0), 4),
                "score": round(item["score"], 4),
            }
        )
    return out


def _alert_level_from_best(best: Dict[str, Any]) -> int:
    edge = _safe_float(best.get("edge"), 0.0)
    prob = _safe_float(best.get("prob"), 0.0)
    if best.get("posible_error_cuota") or best.get("cuota_sospechosa"):
        return 3
    if best.get("es_value_bet") and edge >= 0.045 and prob >= 0.52:
        return 2
    if best.get("oportunidad_detectada") or edge >= 0.015 or best.get("signal_tier") in {"lean", "top_pick"}:
        return 1
    return 0


def _alert_title(level: int) -> str:
    if level == 3:
        return "Alerta roja"
    if level == 2:
        return "Alerta naranja"
    if level == 1:
        return "Alerta azul"
    return "Sin alerta"


def _stake_units(confianza: int, stability: float, edge: float, market_code: str, close_probability: float, reliability: float, fragility: float, data_quality: float) -> float:
    conservative_score = (
        close_probability * 0.42
        + (confianza / 100.0) * 0.18
        + stability * 0.15
        + reliability * 0.14
        + data_quality * 0.11
        - fragility * 0.18
        + max(min(edge, 0.02), -0.02) * 0.04
    )
    if market_code in STABLE_MARKET_PRIORITY:
        conservative_score += 0.03

    if close_probability < 0.60 or reliability < 0.68 or fragility > 0.58:
        return 0.0
    if conservative_score >= 0.78 and close_probability >= 0.72:
        return 1.5
    if conservative_score >= 0.68 and close_probability >= 0.66:
        return 1.0
    if conservative_score >= 0.60 and close_probability >= 0.60:
        return 0.5
    return 0.0


def calcular_alerta_pricing(prediction: Dict[str, Any]) -> Dict[str, Any]:
    level = _safe_int(prediction.get("alert_level"), 0)
    return {
        "fixture_id": _safe_int(prediction.get("fixture_id"), 0),
        "alert_level": level,
        "alert_title": prediction.get("alert_title", _alert_title(level)),
        "mercado": prediction.get("mercado_principal"),
        "jugada": prediction.get("apuesta_principal"),
        "cuota": prediction.get("cuota_principal"),
        "prob_modelo": prediction.get("prob_apuesta"),
        "prob_implicita": prediction.get("probabilidad_implicita_principal"),
        "prob_justa": prediction.get("probabilidad_justa_principal"),
        "edge": prediction.get("edge_principal"),
        "confianza": prediction.get("confianza"),
        "es_value_bet": prediction.get("es_value_bet", 0),
        "posible_error_cuota": prediction.get("posible_error_cuota", 0),
        "cuota_sospechosa": prediction.get("cuota_sospechosa", 0),
        "oportunidad_detectada": prediction.get("oportunidad_detectada", 0),
    }


def calcular_partido(f: Dict[str, Any]) -> Dict[str, Any]:
    home_name = str(f.get("home_team_name", "Local"))
    away_name = str(f.get("away_team_name", "Visitante"))

    home_stats = extract_team_stats(f.get("home_stats"), "home")
    away_stats = extract_team_stats(f.get("away_stats"), "away")

    gf_home = _resolve_goal_metric(f.get("gf_home"), home_stats["gf"], LEAGUE_BASELINES["goals_home"])
    ga_home = _resolve_goal_metric(f.get("ga_home"), home_stats["ga"], LEAGUE_BASELINES["goals_away"])
    gf_away = _resolve_goal_metric(f.get("gf_away"), away_stats["gf"], LEAGUE_BASELINES["goals_away"])
    ga_away = _resolve_goal_metric(f.get("ga_away"), away_stats["ga"], LEAGUE_BASELINES["goals_home"])

    cf_home = _resolve_optional_metric(f.get("cf_home"), home_stats["cf"])
    ca_home = _resolve_optional_metric(f.get("ca_home"), home_stats["ca"])
    cf_away = _resolve_optional_metric(f.get("cf_away"), away_stats["cf"])
    ca_away = _resolve_optional_metric(f.get("ca_away"), away_stats["ca"])

    yf_home = _normalize_cards_metric(f.get("yf_home"), home_stats["yellow"], f.get("home_stats"))
    yf_away = _normalize_cards_metric(f.get("yf_away"), away_stats["yellow"], f.get("away_stats"))

    shots_home = _resolve_optional_metric(f.get("shots_home"), home_stats["shots"])
    shots_away = _resolve_optional_metric(f.get("shots_away"), away_stats["shots"])
    sot_home = _resolve_optional_metric(f.get("shots_on_target_home"), home_stats["shots_on"])
    sot_away = _resolve_optional_metric(f.get("shots_on_target_away"), away_stats["shots_on"])

    form_home = _resolve_form_factor(f.get("form_home"), home_stats["form_factor"])
    form_away = _resolve_form_factor(f.get("form_away"), away_stats["form_factor"])

    odds = extract_odds(f)
    dynamic_over_markets = odds.get("dynamic_over_markets") if isinstance(odds.get("dynamic_over_markets"), list) else []
    input_corners_odds_available = any(
        odds.get(key) is not None
        for key in [
            "over75_corners",
            "over85_corners",
            "over95_corners",
            "corners_home_over_3_5",
            "corners_home_over_4_5",
            "corners_away_over_3_5",
            "corners_away_over_4_5",
        ]
    ) or any(str(item.get("family", "")).lower() == "corners" for item in dynamic_over_markets)
    input_cards_odds_available = any(
        odds.get(key) is not None
        for key in [
            "over35_cards",
            "over45_cards",
            "cards_home_over_1_5",
            "cards_home_over_2_5",
            "cards_away_over_1_5",
            "cards_away_over_2_5",
        ]
    ) or any(str(item.get("family", "")).lower() == "cards" for item in dynamic_over_markets)
    collection_meta = f.get("collection_meta") if isinstance(f.get("collection_meta"), dict) else {}
    feature_availability = {}
    if isinstance(collection_meta.get("feature_availability"), dict):
        feature_availability = collection_meta.get("feature_availability") or {}
    elif isinstance(f.get("feature_availability"), dict):
        feature_availability = f.get("feature_availability") or {}
    market_blocking_reasons = f.get("market_blocking_reasons") if isinstance(f.get("market_blocking_reasons"), dict) else {}

    goals_ready = f.get("goals_ready") if isinstance(f.get("goals_ready"), bool) else _nested_bool(feature_availability, ["goals", "ready"])
    publish_value_allowed = f.get("publish_value_allowed") if isinstance(f.get("publish_value_allowed"), bool) else _nested_bool(feature_availability, ["goals", "publish_allowed"])
    corners_ready = f.get("corners_ready") if isinstance(f.get("corners_ready"), bool) else _nested_bool(feature_availability, ["corners", "ready"])
    cards_ready = f.get("cards_ready") if isinstance(f.get("cards_ready"), bool) else _nested_bool(feature_availability, ["cards", "ready"])
    shots_total_ready = f.get("shots_total_ready") if isinstance(f.get("shots_total_ready"), bool) else _nested_bool(feature_availability, ["shots_total", "ready"])
    shots_on_target_ready = f.get("shots_on_target_ready") if isinstance(f.get("shots_on_target_ready"), bool) else _nested_bool(feature_availability, ["shots_on_target", "ready"])

    odds_presence = sum(1 for k in ["home", "draw", "away", "over25", "btts_yes"] if odds.get(k) is not None) / 5.0
    goals_presence = sum(1 for v in [f.get("gf_home"), f.get("ga_home"), f.get("gf_away"), f.get("ga_away"), home_stats.get("gf"), home_stats.get("ga"), away_stats.get("gf"), away_stats.get("ga")] if _parse_avg_number(v) is not None)
    goals_presence = _clamp(goals_presence / 8.0, 0.25, 1.0)
    corners_presence = sum(1 for v in [cf_home, ca_home, cf_away, ca_away] if v is not None) / 4.0
    cards_presence = sum(1 for v in [yf_home, yf_away] if v is not None) / 2.0
    shots_presence = sum(1 for v in [shots_home, shots_away, sot_home, sot_away] if v is not None) / 4.0
    recent_presence = 1.0 if (f.get("home_recent_form") or f.get("away_recent_form")) else 0.0
    h2h_presence = 1.0 if f.get("head_to_head") else 0.0

    explicit_quality = _parse_avg_number(f.get("data_quality"))
    observed_quality = _clamp(
        goals_presence * 0.42
        + odds_presence * 0.14
        + corners_presence * 0.10
        + cards_presence * 0.08
        + shots_presence * 0.10
        + recent_presence * 0.10
        + h2h_presence * 0.06,
        0.32,
        1.0,
    )
    base_quality = _clamp(explicit_quality if explicit_quality is not None else observed_quality, 0.32, 1.0)

    baselines = _league_goal_baselines(f)
    recent_home = _weighted_recent_metrics(f.get("home_recent_form"))
    recent_away = _weighted_recent_metrics(f.get("away_recent_form"))

    sample_blend_home = _avg([home_stats["sample_factor"], away_stats["sample_factor"]], 0.55)
    sample_blend_away = _avg([away_stats["sample_factor"], home_stats["sample_factor"]], 0.55)
    structural_quality = _clamp(base_quality * 0.56 + sample_blend_home * 0.22 + sample_blend_away * 0.22, 0.32, 1.0)

    home_attack_strength = _clamp(gf_home / max(0.55, baselines["home"]), 0.70, 1.55)
    away_defense_weakness = _clamp(ga_away / max(0.50, baselines["away"]), 0.70, 1.55)
    away_attack_strength = _clamp(gf_away / max(0.50, baselines["away"]), 0.70, 1.52)
    home_defense_weakness = _clamp(ga_home / max(0.55, baselines["home"]), 0.70, 1.55)

    home_recent_attack = _clamp(recent_home["gf"] / max(0.55, gf_home), 0.88, 1.12) if recent_home["matches"] else 1.0
    home_recent_defense = _clamp(recent_home["ga"] / max(0.50, ga_home), 0.88, 1.12) if recent_home["matches"] else 1.0
    away_recent_attack = _clamp(recent_away["gf"] / max(0.50, gf_away), 0.88, 1.12) if recent_away["matches"] else 1.0
    away_recent_defense = _clamp(recent_away["ga"] / max(0.50, ga_away), 0.88, 1.12) if recent_away["matches"] else 1.0

    recent_home_form = _clamp(0.95 + (recent_home["points_per_match"] / 3.0) * 0.08, 0.95, 1.03) if recent_home["matches"] else 1.0
    recent_away_form = _clamp(0.95 + (recent_away["points_per_match"] / 3.0) * 0.08, 0.95, 1.03) if recent_away["matches"] else 1.0

    h2h_shift = _h2h_bias(f.get("head_to_head"), home_name, away_name)

    lambda_home_raw = (
        baselines["home"]
        * home_attack_strength
        * away_defense_weakness
        * form_home
        * recent_home_form
        * home_recent_attack
        * (2.0 - away_recent_defense)
        * (1.01 + max(h2h_shift, 0.0))
    )
    lambda_away_raw = (
        baselines["away"]
        * away_attack_strength
        * home_defense_weakness
        * form_away
        * recent_away_form
        * away_recent_attack
        * (2.0 - home_recent_defense)
        * (0.995 + min(h2h_shift, 0.0))
    )

    lambda_home = _shrink_towards_baseline(lambda_home_raw, baselines["home"], structural_quality, sample_blend_home)
    lambda_away = _shrink_towards_baseline(lambda_away_raw, baselines["away"], structural_quality, sample_blend_away)

    baseline_total = baselines["home"] + baselines["away"]
    total_goals_raw = lambda_home + lambda_away
    total_goals = _shrink_towards_baseline(total_goals_raw, baseline_total, structural_quality, _avg([sample_blend_home, sample_blend_away], 0.55))
    total_goals = _clamp(total_goals, 1.55, 3.45)

    split_total = max(lambda_home + lambda_away, 0.20)
    lambda_home = total_goals * (lambda_home / split_total)
    lambda_away = total_goals * (lambda_away / split_total)

    lambda_home = _clamp(lambda_home, 0.45, 2.25)
    lambda_away = _clamp(lambda_away, 0.35, 1.95)

    lambda_gap = abs(lambda_home - lambda_away)
    if lambda_gap > 1.15:
        avg_total = (lambda_home + lambda_away) / 2.0
        leader = max(lambda_home, lambda_away)
        lagger = min(lambda_home, lambda_away)
        leader = leader - min(0.28, (lambda_gap - 1.15) * 0.22)
        lagger = lagger + min(0.18, (lambda_gap - 1.15) * 0.16)
        if lambda_home >= lambda_away:
            lambda_home, lambda_away = leader, lagger
        else:
            lambda_home, lambda_away = lagger, leader
        new_total = lambda_home + lambda_away
        if new_total > 0:
            factor = (avg_total * 2.0) / new_total
            lambda_home *= factor
            lambda_away *= factor

    rho = -0.07 if (lambda_home + lambda_away) <= 2.45 else -0.05
    matrix = score_matrix(lambda_home, lambda_away, rho=rho)
    outcomes = outcome_probs(matrix)

    home_win, draw, away_win = normalize_probs(outcomes["home"], outcomes["draw"], outcomes["away"])
    home_win, draw, away_win = _calibrate_1x2(home_win, draw, away_win, structural_quality)

    gol_local = _calibrated_binary_prob(team_to_score_prob(lambda_home), structural_quality, floor=0.10, ceiling=0.90)
    gol_visitante = _calibrated_binary_prob(team_to_score_prob(lambda_away), structural_quality, floor=0.10, ceiling=0.88)

    btts = _clamp(outcomes["btts"] * 0.76 + (gol_local * gol_visitante) * 0.24, 0.09, 0.84)
    over15 = _clamp(outcomes["over15"], 0.14, 0.92)
    over25 = _clamp(outcomes["over25"], 0.10, 0.84)
    over35 = _clamp(outcomes["over35"], 0.07, 0.72)
    under45 = _clamp(outcomes["under45"], 0.18, 0.94)

    corners_local = corners_visitante = corners_totales = None
    prob_over75_corners = prob_over85_corners = prob_over95_corners = None
    corners_quality = 0.0
    if any(v is not None for v in [cf_home, ca_home, cf_away, ca_away]):
        local_inputs = [v for v in [cf_home, ca_away] if v is not None and v > 0]
        away_inputs = [v for v in [cf_away, ca_home] if v is not None and v > 0]
        if local_inputs and away_inputs:
            corners_local_raw = sum(local_inputs) / len(local_inputs)
            corners_visitante_raw = sum(away_inputs) / len(away_inputs)
            corners_local = _clamp(corners_local_raw, 2.2, 7.8)
            corners_visitante = _clamp(corners_visitante_raw, 2.0, 7.3)
            corners_totales = _clamp(corners_local + corners_visitante, 5.5, 14.2)
            prob_over75_corners = _round_prob(prob_over_lambda(corners_totales, 7.5))
            prob_over85_corners = _round_prob(prob_over_lambda(corners_totales, 8.5))
            prob_over95_corners = _round_prob(prob_over_lambda(corners_totales, 9.5))
            corners_quality = _clamp(structural_quality * 0.74 + corners_presence * 0.26, 0.42, 1.0)

    tarjetas_local = tarjetas_visitante = tarjetas_totales = None
    prob_over35_tarjetas = prob_over45_tarjetas = None
    cards_quality = 0.0
    if yf_home is not None and yf_away is not None:
        tarjetas_local = _clamp(yf_home, 0.8, 4.0)
        tarjetas_visitante = _clamp(yf_away, 0.9, 4.3)
        tarjetas_totales = _clamp(tarjetas_local + tarjetas_visitante, 2.4, 8.0)
        prob_over35_tarjetas = _round_prob(prob_over_lambda(tarjetas_totales, 3.5))
        prob_over45_tarjetas = _round_prob(prob_over_lambda(tarjetas_totales, 4.5))
        cards_quality = _clamp(structural_quality * 0.72 + cards_presence * 0.28, 0.44, 1.0)

    shots_home_quality = _shots_data_quality(shots_home, sot_home, sample_blend_home, structural_quality)
    shots_away_quality = _shots_data_quality(shots_away, sot_away, sample_blend_away, structural_quality)

    tiros_local = tiros_visitante = puerta_local = puerta_visitante = None
    if shots_home is not None:
        tiros_local = _clamp(shots_home, 5.0, 18.5)
    if shots_away is not None:
        tiros_visitante = _clamp(shots_away, 4.8, 17.2)
    if sot_home is not None:
        puerta_local = _clamp(sot_home, 1.2, 6.8)
    if sot_away is not None:
        puerta_visitante = _clamp(sot_away, 1.0, 6.2)

    fouls_local = _resolve_optional_metric(f.get("fouls_home"), _parse_avg_number(_nested(f.get("home_stats") or {}, ["fouls", "for", "average", "home"])))
    fouls_visitante = _resolve_optional_metric(f.get("fouls_away"), _parse_avg_number(_nested(f.get("away_stats") or {}, ["fouls", "for", "average", "away"])))
    if fouls_local is None and tarjetas_local is not None:
        fouls_local = _clamp(tarjetas_local * 3.4 + 5.8, 6.0, 22.0)
    if fouls_visitante is None and tarjetas_visitante is not None:
        fouls_visitante = _clamp(tarjetas_visitante * 3.3 + 6.0, 6.0, 22.0)
    fouls_totales = (fouls_local + fouls_visitante) if (fouls_local is not None and fouls_visitante is not None) else None

    offsides_local = _resolve_optional_metric(f.get("offsides_home"), _parse_avg_number(_nested(f.get("home_stats") or {}, ["offsides", "for", "average", "home"])))
    offsides_visitante = _resolve_optional_metric(f.get("offsides_away"), _parse_avg_number(_nested(f.get("away_stats") or {}, ["offsides", "for", "average", "away"])))
    if offsides_local is None and puerta_local is not None:
        offsides_local = _clamp(puerta_local * 0.34 + 0.55, 0.5, 5.5)
    if offsides_visitante is None and puerta_visitante is not None:
        offsides_visitante = _clamp(puerta_visitante * 0.34 + 0.50, 0.5, 5.5)
    offsides_totales = (offsides_local + offsides_visitante) if (offsides_local is not None and offsides_visitante is not None) else None

    fair_1x2 = _remove_overround_1x2(odds.get("home"), odds.get("draw"), odds.get("away"))

    markets: List[Dict[str, Any]] = []
    markets.append(_build_market("1X2_HOME", home_win, odds.get("home"), fair_1x2.get("home"), structural_quality, structural_quality, home_name, away_name))
    markets.append(_build_market("1X2_DRAW", draw, odds.get("draw"), fair_1x2.get("draw"), structural_quality, structural_quality, home_name, away_name))
    markets.append(_build_market("1X2_AWAY", away_win, odds.get("away"), fair_1x2.get("away"), structural_quality, structural_quality, home_name, away_name))

    dc_1x = _clamp(home_win + draw, 0.18, 0.95)
    dc_x2 = _clamp(away_win + draw, 0.18, 0.95)
    dc_12 = _clamp(home_win + away_win, 0.20, 0.93)

    markets.append(_build_market("DC_1X", dc_1x, odds.get("dc_1x"), implied_prob(odds.get("dc_1x")), structural_quality, structural_quality, home_name, away_name))
    markets.append(_build_market("DC_X2", dc_x2, odds.get("dc_x2"), implied_prob(odds.get("dc_x2")), structural_quality, structural_quality, home_name, away_name))
    markets.append(_build_market("DC_12", dc_12, odds.get("dc_12"), implied_prob(odds.get("dc_12")), structural_quality, structural_quality, home_name, away_name))

    markets.append(_build_market("OVER15", over15, odds.get("over15"), implied_prob(odds.get("over15")), structural_quality, structural_quality, home_name, away_name))
    markets.append(_build_market("OVER25", over25, odds.get("over25"), implied_prob(odds.get("over25")), structural_quality, structural_quality, home_name, away_name))
    markets.append(_build_market("OVER35", over35, odds.get("over35"), implied_prob(odds.get("over35")), structural_quality, structural_quality, home_name, away_name))
    markets.append(_build_market("UNDER45", under45, odds.get("under45"), implied_prob(odds.get("under45")), structural_quality, structural_quality, home_name, away_name))
    markets.append(_build_market("BTTS_YES", btts, odds.get("btts_yes"), implied_prob(odds.get("btts_yes")), structural_quality, structural_quality, home_name, away_name))

    if corners_totales is not None and corners_ready is not False:
        markets.append(_build_market("O75_CORNERS", prob_over_lambda(corners_totales, 7.5), odds.get("over75_corners"), implied_prob(odds.get("over75_corners")), structural_quality, corners_quality, home_name, away_name))
        markets.append(_build_market("O85_CORNERS", prob_over_lambda(corners_totales, 8.5), odds.get("over85_corners"), implied_prob(odds.get("over85_corners")), structural_quality, corners_quality, home_name, away_name))
        markets.append(_build_market("O95_CORNERS", prob_over_lambda(corners_totales, 9.5), odds.get("over95_corners"), implied_prob(odds.get("over95_corners")), structural_quality, corners_quality, home_name, away_name))
    if corners_local is not None and corners_ready is not False:
        markets.append(_build_market("CORNERS_HOME_OVER_3_5", prob_over_lambda(corners_local, 3.5), odds.get("corners_home_over_3_5"), implied_prob(odds.get("corners_home_over_3_5")), structural_quality, corners_quality, home_name, away_name, line=3.5))
        markets.append(_build_market("CORNERS_HOME_OVER_4_5", prob_over_lambda(corners_local, 4.5), odds.get("corners_home_over_4_5"), implied_prob(odds.get("corners_home_over_4_5")), structural_quality, corners_quality, home_name, away_name, line=4.5))
    if corners_visitante is not None and corners_ready is not False:
        markets.append(_build_market("CORNERS_AWAY_OVER_3_5", prob_over_lambda(corners_visitante, 3.5), odds.get("corners_away_over_3_5"), implied_prob(odds.get("corners_away_over_3_5")), structural_quality, corners_quality, home_name, away_name, line=3.5))
        markets.append(_build_market("CORNERS_AWAY_OVER_4_5", prob_over_lambda(corners_visitante, 4.5), odds.get("corners_away_over_4_5"), implied_prob(odds.get("corners_away_over_4_5")), structural_quality, corners_quality, home_name, away_name, line=4.5))

    if tarjetas_totales is not None and cards_ready is not False:
        markets.append(_build_market("O35_CARDS", prob_over_lambda(tarjetas_totales, 3.5), odds.get("over35_cards"), implied_prob(odds.get("over35_cards")), structural_quality, cards_quality, home_name, away_name))
        markets.append(_build_market("O45_CARDS", prob_over_lambda(tarjetas_totales, 4.5), odds.get("over45_cards"), implied_prob(odds.get("over45_cards")), structural_quality, cards_quality, home_name, away_name))
    if tarjetas_local is not None and cards_ready is not False:
        markets.append(_build_market("CARDS_HOME_OVER_1_5", prob_over_lambda(tarjetas_local, 1.5), odds.get("cards_home_over_1_5"), implied_prob(odds.get("cards_home_over_1_5")), structural_quality, cards_quality, home_name, away_name, line=1.5))
        markets.append(_build_market("CARDS_HOME_OVER_2_5", prob_over_lambda(tarjetas_local, 2.5), odds.get("cards_home_over_2_5"), implied_prob(odds.get("cards_home_over_2_5")), structural_quality, cards_quality, home_name, away_name, line=2.5))
    if tarjetas_visitante is not None and cards_ready is not False:
        markets.append(_build_market("CARDS_AWAY_OVER_1_5", prob_over_lambda(tarjetas_visitante, 1.5), odds.get("cards_away_over_1_5"), implied_prob(odds.get("cards_away_over_1_5")), structural_quality, cards_quality, home_name, away_name, line=1.5))
        markets.append(_build_market("CARDS_AWAY_OVER_2_5", prob_over_lambda(tarjetas_visitante, 2.5), odds.get("cards_away_over_2_5"), implied_prob(odds.get("cards_away_over_2_5")), structural_quality, cards_quality, home_name, away_name, line=2.5))

    markets.append(_build_market("TEAM_HOME_SCORE_YES", gol_local, odds.get("team_home_score_yes"), implied_prob(odds.get("team_home_score_yes")), structural_quality, structural_quality, home_name, away_name))
    markets.append(_build_market("TEAM_AWAY_SCORE_YES", gol_visitante, odds.get("team_away_score_yes"), implied_prob(odds.get("team_away_score_yes")), structural_quality, structural_quality, home_name, away_name))
    markets.append(_build_market("TEAM_HOME_OVER_0_5", gol_local, odds.get("team_home_over_0_5"), implied_prob(odds.get("team_home_over_0_5")), structural_quality, structural_quality, home_name, away_name, line=0.5))
    markets.append(_build_market("TEAM_HOME_OVER_1_5", prob_over_lambda(lambda_home, 1.5), odds.get("team_home_over_1_5"), implied_prob(odds.get("team_home_over_1_5")), structural_quality, structural_quality, home_name, away_name, line=1.5))
    markets.append(_build_market("TEAM_AWAY_OVER_0_5", gol_visitante, odds.get("team_away_over_0_5"), implied_prob(odds.get("team_away_over_0_5")), structural_quality, structural_quality, home_name, away_name, line=0.5))
    markets.append(_build_market("TEAM_AWAY_OVER_1_5", prob_over_lambda(lambda_away, 1.5), odds.get("team_away_over_1_5"), implied_prob(odds.get("team_away_over_1_5")), structural_quality, structural_quality, home_name, away_name, line=1.5))

    if tiros_local is not None and shots_home_quality >= 0.45 and shots_total_ready is not False:
        markets.append(_build_market("SHOTS_HOME", 0.50 + ((tiros_local - LEAGUE_BASELINES["shots_home"]) / 20.0), odds.get("shots_home"), implied_prob(odds.get("shots_home")), structural_quality, shots_home_quality, home_name, away_name))
        shots_home_line = odds.get("shots_home_line") or _infer_dynamic_line(tiros_local, 6.5, 14.5, 9.5)
        markets.append(_build_market("SHOTS_HOME_OVER_X", prob_over_lambda(tiros_local, shots_home_line), odds.get("shots_home_over_x"), implied_prob(odds.get("shots_home_over_x")), structural_quality, shots_home_quality, home_name, away_name, line=shots_home_line))
    if puerta_local is not None and shots_home_quality >= 0.45 and shots_on_target_ready is not False:
        markets.append(_build_market("SOT_HOME", 0.50 + ((puerta_local - LEAGUE_BASELINES["shots_on_home"]) / 8.0), odds.get("sot_home"), implied_prob(odds.get("sot_home")), structural_quality, shots_home_quality, home_name, away_name))
        sot_home_line = odds.get("sot_home_line") or _infer_dynamic_line(puerta_local, 1.5, 5.5, 3.5)
        markets.append(_build_market("SOT_HOME_OVER_X", prob_over_lambda(puerta_local, sot_home_line), odds.get("sot_home_over_x"), implied_prob(odds.get("sot_home_over_x")), structural_quality, shots_home_quality, home_name, away_name, line=sot_home_line))

    if tiros_visitante is not None and shots_away_quality >= 0.45 and shots_total_ready is not False:
        markets.append(_build_market("SHOTS_AWAY", 0.50 + ((tiros_visitante - LEAGUE_BASELINES["shots_away"]) / 20.0), odds.get("shots_away"), implied_prob(odds.get("shots_away")), structural_quality, shots_away_quality, home_name, away_name))
        shots_away_line = odds.get("shots_away_line") or _infer_dynamic_line(tiros_visitante, 6.5, 13.5, 8.5)
        markets.append(_build_market("SHOTS_AWAY_OVER_X", prob_over_lambda(tiros_visitante, shots_away_line), odds.get("shots_away_over_x"), implied_prob(odds.get("shots_away_over_x")), structural_quality, shots_away_quality, home_name, away_name, line=shots_away_line))
    if puerta_visitante is not None and shots_away_quality >= 0.45 and shots_on_target_ready is not False:
        markets.append(_build_market("SOT_AWAY", 0.50 + ((puerta_visitante - LEAGUE_BASELINES["shots_on_away"]) / 8.0), odds.get("sot_away"), implied_prob(odds.get("sot_away")), structural_quality, shots_away_quality, home_name, away_name))
        sot_away_line = odds.get("sot_away_line") or _infer_dynamic_line(puerta_visitante, 1.5, 5.0, 3.0)
        markets.append(_build_market("SOT_AWAY_OVER_X", prob_over_lambda(puerta_visitante, sot_away_line), odds.get("sot_away_over_x"), implied_prob(odds.get("sot_away_over_x")), structural_quality, shots_away_quality, home_name, away_name, line=sot_away_line))

    for idx, dyn in enumerate(dynamic_over_markets):
        family = str(dyn.get("family") or "")
        scope = str(dyn.get("scope") or "total")
        period = str(dyn.get("period") or "FT")
        direction = str(dyn.get("direction") or "over").lower()
        line = _safe_float(dyn.get("line"), 0.0)
        odd = _safe_float(dyn.get("odd"), 0.0)
        if line < 0.5 or odd <= 1.0:
            continue

        base_lambda = None
        quality = structural_quality
        group = "Secondary"
        team_label = "total"
        if family == "corners":
            group = "Corners"
            quality = corners_quality if corners_quality > 0 else _clamp(structural_quality * 0.65 + corners_presence * 0.35, 0.35, 1.0)
            if scope == "home":
                base_lambda = corners_local
                team_label = home_name
            elif scope == "away":
                base_lambda = corners_visitante
                team_label = away_name
            else:
                base_lambda = corners_totales
        elif family == "cards":
            group = "Tarjetas"
            quality = cards_quality if cards_quality > 0 else _clamp(structural_quality * 0.65 + cards_presence * 0.35, 0.35, 1.0)
            if scope == "home":
                base_lambda = tarjetas_local
                team_label = home_name
            elif scope == "away":
                base_lambda = tarjetas_visitante
                team_label = away_name
            else:
                base_lambda = tarjetas_totales
        elif family == "shots":
            group = "Tiros"
            if scope == "home":
                base_lambda = tiros_local
                quality = shots_home_quality
                team_label = home_name
            elif scope == "away":
                base_lambda = tiros_visitante
                quality = shots_away_quality
                team_label = away_name
            else:
                base_lambda = (tiros_local + tiros_visitante) if (tiros_local is not None and tiros_visitante is not None) else None
                quality = _clamp((shots_home_quality + shots_away_quality) / 2.0, 0.0, 1.0)
        elif family == "shots_on_target":
            group = "Tiros a puerta"
            if scope == "home":
                base_lambda = puerta_local
                quality = shots_home_quality
                team_label = home_name
            elif scope == "away":
                base_lambda = puerta_visitante
                quality = shots_away_quality
                team_label = away_name
            else:
                base_lambda = (puerta_local + puerta_visitante) if (puerta_local is not None and puerta_visitante is not None) else None
                quality = _clamp((shots_home_quality + shots_away_quality) / 2.0, 0.0, 1.0)
        elif family == "fouls":
            group = "Faltas"
            quality = _clamp((cards_quality if cards_quality > 0 else structural_quality) * 0.78, 0.34, 1.0)
            if scope == "home":
                base_lambda = fouls_local
                team_label = home_name
            elif scope == "away":
                base_lambda = fouls_visitante
                team_label = away_name
            else:
                base_lambda = fouls_totales
        elif family == "offsides":
            group = "Offsides"
            quality = _clamp((max(shots_home_quality, 0.35) + max(shots_away_quality, 0.35)) / 2.0, 0.34, 1.0)
            if scope == "home":
                base_lambda = offsides_local
                team_label = home_name
            elif scope == "away":
                base_lambda = offsides_visitante
                team_label = away_name
            else:
                base_lambda = offsides_totales

        if base_lambda is None or base_lambda <= 0:
            continue

        period_factor = 0.46 if period == "1H" else 0.54 if period == "2H" else 1.0
        event_lambda = _clamp(base_lambda * period_factor, 0.05, 55.0)
        prob_over = _round_prob(prob_over_lambda(event_lambda, line))
        prob = prob_over if direction == "over" else _round_prob(1.0 - prob_over)
        family_token = family.upper()
        dir_token = "OVER" if direction == "over" else "UNDER"
        code = f"{family_token}_{scope.upper()}_{dir_token}_{str(line).replace('.', '_')}_{period}"
        period_label = "1T" if period == "1H" else "2T" if period == "2H" else "Partido"
        dir_label = "más de" if direction == "over" else "menos de"
        if scope == "total":
            pick = f"{group} total {dir_label} {line:.1f} ({period_label})"
        else:
            pick = f"{team_label} {dir_label} {line:.1f} {group.lower()} ({period_label})"

        markets.append(
            _build_market(
                code,
                prob,
                odd,
                implied_prob(odd),
                structural_quality,
                max(quality, 0.34),
                home_name,
                away_name,
                line=line,
                market_name_override=pick,
                market_group_override=group,
            )
        )

    families_payload: Dict[str, List[Dict[str, Any]]] = {}
    if input_corners_odds_available:
        families_payload.setdefault("corners", [])
    if input_cards_odds_available:
        families_payload.setdefault("cards", [])

    for item in markets:
        token = f"{item.get('code') or ''} {item.get('mercado') or ''} {item.get('jugada') or ''}".upper()
        family_key = "secondary"
        if "CORNER" in token or "ESQUINA" in token:
            family_key = "corners"
        elif any(k in token for k in ["CARD", "TARJET", "BOOKING", "YELLOW", "AMARILLA", "AMONEST"]):
            family_key = "cards"
        elif any(k in token for k in ["FOUL", "FALTA"]):
            family_key = "fouls"
        elif any(k in token for k in ["OFFSIDE", "FUERA DE JUEGO"]):
            family_key = "offsides"
        elif any(k in token for k in ["SHOTS ON TARGET", "SOT", "TIROS A PUERTA", "REMATES AL ARCO"]):
            family_key = "shots_on_target"
        elif "SHOT" in token or "TIRO" in token:
            family_key = "shots"
        elif any(k in token for k in ["DOUBLE CHANCE", "DOBLE OPORTUNIDAD", "DC_"]):
            family_key = "double_chance"
        elif any(k in token for k in ["EXACT SCORE", "MARCADOR EXACTO"]):
            family_key = "exact_score"
        elif "BTTS" in token or "AMBOS" in token:
            family_key = "btts"
        elif "1X2" in token:
            family_key = "1x2"
        elif any(key in token for key in ["GOAL", "GOLES", "SCORE", "OVER", "UNDER"]):
            family_key = "goals"
        families_payload.setdefault(family_key, []).append(
            {
                "code": item.get("code"),
                "market": item.get("mercado"),
                "pick": item.get("jugada"),
                "line": round(item["line"], 2) if item.get("line") is not None else None,
                "prob": round(item.get("prob", 0.0), 6) if item.get("prob") is not None else None,
                "odds": round(item.get("cuota"), 4) if item.get("cuota") else None,
            }
        )

    if input_corners_odds_available and not families_payload.get("corners"):
        fallback_odd = next(
            (
                odds.get(key)
                for key in [
                    "over75_corners",
                    "over85_corners",
                    "over95_corners",
                    "corners_home_over_3_5",
                    "corners_home_over_4_5",
                    "corners_away_over_3_5",
                    "corners_away_over_4_5",
                ]
                if odds.get(key) is not None
            ),
            None,
        )
        if fallback_odd is not None:
            families_payload["corners"] = [
                {
                    "code": "CORNERS_FALLBACK",
                    "market": "Corners",
                    "pick": "Corners available",
                    "line": None,
                    "prob": round(_round_prob(prob_over_lambda(corners_totales or LEAGUE_BASELINES["corners_home"] + LEAGUE_BASELINES["corners_away"], 7.5)), 6),
                    "odds": round(fallback_odd, 4),
                }
            ]

    if input_cards_odds_available and not families_payload.get("cards"):
        fallback_odd = next(
            (
                odds.get(key)
                for key in [
                    "over35_cards",
                    "over45_cards",
                    "cards_home_over_1_5",
                    "cards_home_over_2_5",
                    "cards_away_over_1_5",
                    "cards_away_over_2_5",
                ]
                if odds.get(key) is not None
            ),
            None,
        )
        if fallback_odd is not None:
            families_payload["cards"] = [
                {
                    "code": "CARDS_FALLBACK",
                    "market": "Cards",
                    "pick": "Cards available",
                    "line": None,
                    "prob": round(_round_prob(prob_over_lambda(tarjetas_totales or (LEAGUE_BASELINES["yellow_home"] + LEAGUE_BASELINES["yellow_away"]), 3.5)), 6),
                    "odds": round(fallback_odd, 4),
                }
            ]

    best = _select_primary_bet(markets)
    apuestas_fuertes = _strong_bets(markets)
    signal_count = len(apuestas_fuertes)
    value_count = sum(1 for item in apuestas_fuertes if item.get("signal_tier") in {"strong_value", "medium_value", "low_value"})
    integrity_alerts = sum(1 for item in apuestas_fuertes if item.get("posible_error_cuota") or item.get("cuota_sospechosa"))
    top_signal_label = apuestas_fuertes[0]["signal_label"] if apuestas_fuertes else "Seguimiento"
    best["signal_tier"] = apuestas_fuertes[0]["signal_tier"] if apuestas_fuertes else best.get("signal_tier", "watch")

    predicted_winner = (
        "LOCAL" if home_win >= away_win and home_win >= draw
        else "VISITANTE" if away_win >= home_win and away_win >= draw
        else "EMPATE"
    )

    confianza = _confidence_from_signal(best["prob"], best["data_quality"], best["edge"], best["reliability"], best["stability"])

    return {
        "fixture_id": int(f["fixture_id"]),
        "liga_id": int(f.get("league_id", 0) or 0),
        "liga": f.get("league_name", "Liga"),
        "pais": f.get("country", ""),
        "hora": str(f.get("hora") or f.get("fixture_datetime") or ""),
        "estado": f.get("status_short", "Programado"),
        "local": home_name,
        "visitante": away_name,
        "predicted_winner": predicted_winner,
        "prob_local": _round_prob(home_win),
        "prob_empate": _round_prob(draw),
        "prob_visitante": _round_prob(away_win),
        "goles_local": round(lambda_home, 4),
        "goles_visitante": round(lambda_away, 4),
        "gol_local": _round_prob(gol_local),
        "gol_visitante": _round_prob(gol_visitante),
        "ambos_marcan": _round_prob(btts),
        "over15": _round_prob(over15),
        "over25": _round_prob(over25),
        "over35": _round_prob(over35),
        "corners_local": round(corners_local, 3) if corners_local is not None else None,
        "corners_visitante": round(corners_visitante, 3) if corners_visitante is not None else None,
        "corners_totales": round(corners_totales, 3) if corners_totales is not None else None,
        "over75_corners": prob_over75_corners,
        "over85_corners": prob_over85_corners,
        "over95_corners": prob_over95_corners,
        "tarjetas_local": round(tarjetas_local, 3) if tarjetas_local is not None else None,
        "tarjetas_visitante": round(tarjetas_visitante, 3) if tarjetas_visitante is not None else None,
        "tarjetas_totales": round(tarjetas_totales, 3) if tarjetas_totales is not None else None,
        "over35_tarjetas": prob_over35_tarjetas,
        "over45_tarjetas": prob_over45_tarjetas,
        "tiros_local": round(tiros_local, 3) if tiros_local is not None else None,
        "tiros_visitante": round(tiros_visitante, 3) if tiros_visitante is not None else None,
        "puerta_local": round(puerta_local, 3) if puerta_local is not None else None,
        "puerta_visitante": round(puerta_visitante, 3) if puerta_visitante is not None else None,
        "apuesta_principal": best["jugada"],
        "mercado_principal": best["mercado"],
        "prob_apuesta": _round_prob(best["prob"]),
        "cuota_principal": round(best["cuota"], 2) if best["cuota"] else None,
        "edge_principal": round(best["edge"], 6),
        "es_value_bet": 1 if best["es_value_bet"] else 0,
        "confianza": confianza,
        "apuestas_fuertes": apuestas_fuertes,
        "posible_error_cuota": 1 if best["posible_error_cuota"] else 0,
        "cuota_sospechosa": 1 if best["cuota_sospechosa"] else 0,
        "oportunidad_detectada": 1 if best["oportunidad_detectada"] else 0,
        "probabilidad_implicita_principal": round(best["probabilidad_implicita"], 6) if best["probabilidad_implicita"] is not None else None,
        "probabilidad_justa_principal": round(best["probabilidad_justa"], 6) if best["probabilidad_justa"] is not None else None,
        "overround_1x2": round(fair_1x2["overround"], 6) if fair_1x2.get("overround") is not None else None,
        "vigorish_1x2": round(fair_1x2["vigorish"], 6) if fair_1x2.get("vigorish") is not None else None,
        "signal_count": signal_count,
        "value_count": value_count,
        "integrity_alerts": integrity_alerts,
        "top_signal_tier": best.get("signal_tier", "watch"),
        "top_signal_label": top_signal_label,
        "data_quality": round(structural_quality, 4),
        "model_version": "predictor_pro_v4_4_prob_first",
        "market_breakdown": [
            {
                "code": item["code"],
                "mercado": item["mercado"],
                "jugada": item["jugada"],
                "prob": round(item["prob"], 6),
                "cuota": round(item["cuota"], 4) if item.get("cuota") else None,
                "edge": round(item["edge"], 6),
                "line": round(item["line"], 2) if item.get("line") is not None else None,
                "reliability": round(item["reliability"], 4),
                "stability": round(item["stability"], 4),
                "signal_tier": item.get("signal_tier"),
                "value": bool(item.get("es_value_bet") or item.get("soft_value")),
                "probabilidad_implicita": round(item["probabilidad_implicita"], 6) if item.get("probabilidad_implicita") is not None else None,
                "probabilidad_justa": round(item["probabilidad_justa"], 6) if item.get("probabilidad_justa") is not None else None,
                "ev": round((item["cuota"] * item["prob"] - 1.0), 6) if item.get("cuota") else None,
                "market_complete": bool(item.get("cuota") and item.get("probabilidad_implicita") is not None),
                "close_probability": round(item.get("close_probability", item["prob"]), 6),
                "volatility": round(item.get("volatility", 0.0), 4),
                "fragility": round(item.get("fragility", 0.0), 4),
            }
            for item in markets
        ],
        "alert_level": _alert_level_from_best(best),
        "alert_title": _alert_title(_alert_level_from_best(best)),
        "stake_sugerido_unidades": _stake_units(confianza, best["stability"], best["edge"], best["code"], best.get("close_probability", best["prob"]), best["reliability"], best.get("fragility", 0.5), best["data_quality"]),
        "market_stability": round(best["stability"], 4),
        "market_reliability": round(best["reliability"], 4),
        "close_probability": round(best.get("close_probability", best["prob"]), 4),
        "market_volatility": round(best.get("volatility", 0.0), 4),
        "pick_fragility": round(best.get("fragility", 0.0), 4),
        "goals_ready": goals_ready,
        "publish_value_allowed": publish_value_allowed,
        "corners_ready": corners_ready,
        "cards_ready": cards_ready,
        "shots_total_ready": shots_total_ready,
        "shots_on_target_ready": shots_on_target_ready,
        "market_blocking_reasons": market_blocking_reasons,
        "families": families_payload,
        "corners_odds_available": bool(input_corners_odds_available),
        "cards_odds_available": bool(input_cards_odds_available),
    }
