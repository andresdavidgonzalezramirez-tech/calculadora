from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import product
from typing import Dict, Iterable, List


@dataclass(frozen=True)
class ThresholdSet:
    min_prob: float
    min_ev: float
    min_confidence: float


def _max_drawdown(curve: List[float]) -> float:
    peak = -10**9
    max_dd = 0.0
    for x in curve:
        peak = max(peak, x)
        max_dd = max(max_dd, peak - x)
    return max_dd


def evaluate_strategy(rows: Iterable[Dict], th: ThresholdSet) -> Dict[str, float]:
    selected = [
        r for r in rows
        if r.get("prob", 0) >= th.min_prob and r.get("ev", -999) >= th.min_ev and r.get("confidence", 0) >= th.min_confidence
    ]
    if not selected:
        return {"bets": 0, "roi": 0.0, "yield": 0.0, "hit_rate": 0.0, "drawdown": 0.0, "sharpe": 0.0}

    pnl = []
    bank = 0.0
    wins = 0
    for r in selected:
        stake = float(r.get("stake", 1.0))
        odd = float(r.get("odds", 0.0))
        won = bool(r.get("won", False))
        trade = stake * (odd - 1.0) if won else -stake
        if won:
            wins += 1
        bank += trade
        pnl.append(bank)

    stakes = sum(float(r.get("stake", 1.0)) for r in selected)
    avg_ret = bank / max(len(selected), 1)
    rets = []
    for i, val in enumerate(pnl):
        prev = pnl[i - 1] if i > 0 else 0.0
        rets.append(val - prev)
    var = sum((x - avg_ret) ** 2 for x in rets) / max(len(rets), 1)
    sharpe = (avg_ret / math.sqrt(var)) if var > 0 else 0.0

    return {
        "bets": len(selected),
        "roi": bank / max(stakes, 1e-9),
        "yield": bank / len(selected),
        "hit_rate": wins / len(selected),
        "drawdown": _max_drawdown(pnl),
        "sharpe": sharpe,
    }


def grid_search(rows: Iterable[Dict], prob_grid: List[float], ev_grid: List[float], conf_grid: List[float]) -> List[Dict]:
    rows = list(rows)
    result = []
    for p, e, c in product(prob_grid, ev_grid, conf_grid):
        th = ThresholdSet(p, e, c)
        metrics = evaluate_strategy(rows, th)
        result.append({"thresholds": th.__dict__, "metrics": metrics})
    return sorted(result, key=lambda x: (x["metrics"]["roi"], x["metrics"]["sharpe"]), reverse=True)
