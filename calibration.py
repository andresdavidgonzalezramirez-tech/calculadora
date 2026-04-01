from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _clip(p: float, eps: float = 1e-6) -> float:
    return min(1 - eps, max(eps, p))


@dataclass
class PlattCalibrator:
    a: float = 1.0
    b: float = 0.0

    def fit(self, raw_probs: Iterable[float], y_true: Iterable[int], lr: float = 0.05, epochs: int = 300) -> "PlattCalibrator":
        xs = [math.log(_clip(p) / (1 - _clip(p))) for p in raw_probs]
        ys = [1.0 if int(y) == 1 else 0.0 for y in y_true]
        if not xs:
            return self

        a, b = self.a, self.b
        n = float(len(xs))
        for _ in range(epochs):
            grad_a = 0.0
            grad_b = 0.0
            for x, y in zip(xs, ys):
                pred = _sigmoid(a * x + b)
                err = pred - y
                grad_a += err * x
                grad_b += err
            a -= lr * (grad_a / n)
            b -= lr * (grad_b / n)

        self.a = a
        self.b = b
        return self

    def predict(self, prob: float) -> float:
        x = math.log(_clip(prob) / (1 - _clip(prob)))
        return _sigmoid(self.a * x + self.b)


@dataclass
class IsotonicCalibrator:
    thresholds: List[float]
    values: List[float]

    @staticmethod
    def fit(raw_probs: Iterable[float], y_true: Iterable[int]) -> "IsotonicCalibrator":
        pairs = sorted((float(p), float(int(y))) for p, y in zip(raw_probs, y_true))
        if not pairs:
            return IsotonicCalibrator([0.0, 1.0], [0.5, 0.5])

        blocks = [[p, p, y, 1] for p, y in pairs]
        i = 0
        while i < len(blocks) - 1:
            if blocks[i][2] / blocks[i][3] > blocks[i + 1][2] / blocks[i + 1][3]:
                blocks[i][1] = blocks[i + 1][1]
                blocks[i][2] += blocks[i + 1][2]
                blocks[i][3] += blocks[i + 1][3]
                del blocks[i + 1]
                if i > 0:
                    i -= 1
            else:
                i += 1

        thresholds, values = [], []
        for lo, hi, sum_y, count in blocks:
            thresholds.extend([lo, hi])
            v = sum_y / count
            values.extend([v, v])
        return IsotonicCalibrator(thresholds, values)

    def predict(self, prob: float) -> float:
        p = float(prob)
        for i in range(0, len(self.thresholds), 2):
            lo, hi = self.thresholds[i], self.thresholds[i + 1]
            if lo <= p <= hi:
                return self.values[i]
        return self.values[0] if p < self.thresholds[0] else self.values[-1]


def brier_score(y_true: Iterable[int], y_prob: Iterable[float]) -> float:
    ys = [float(int(v)) for v in y_true]
    ps = [float(p) for p in y_prob]
    if not ys:
        return 0.0
    return sum((p - y) ** 2 for y, p in zip(ys, ps)) / len(ys)


def log_loss(y_true: Iterable[int], y_prob: Iterable[float]) -> float:
    ys = [float(int(v)) for v in y_true]
    ps = [_clip(float(p)) for p in y_prob]
    if not ys:
        return 0.0
    return -sum(y * math.log(p) + (1 - y) * math.log(1 - p) for y, p in zip(ys, ps)) / len(ys)


def reliability_curve(y_true: Iterable[int], y_prob: Iterable[float], bins: int = 10) -> List[Dict[str, float]]:
    ys = [float(int(v)) for v in y_true]
    ps = [float(p) for p in y_prob]
    bucket: List[List[Tuple[float, float]]] = [[] for _ in range(bins)]
    for y, p in zip(ys, ps):
        idx = min(bins - 1, max(0, int(p * bins)))
        bucket[idx].append((y, p))

    curve = []
    for idx, b in enumerate(bucket):
        if not b:
            continue
        mean_y = sum(y for y, _ in b) / len(b)
        mean_p = sum(p for _, p in b) / len(b)
        curve.append({"bin": idx, "avg_pred": mean_p, "avg_true": mean_y, "count": len(b)})
    return curve


def save_calibrator(path: str, method: str, payload: Dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"method": method, "payload": payload}, indent=2), encoding="utf-8")


def load_calibrator(path: str):
    target = Path(path)
    if not target.exists():
        return None
    doc = json.loads(target.read_text(encoding="utf-8"))
    method = doc.get("method")
    payload = doc.get("payload", {})
    if method == "platt":
        return PlattCalibrator(a=float(payload.get("a", 1.0)), b=float(payload.get("b", 0.0)))
    if method == "isotonic":
        return IsotonicCalibrator(thresholds=payload.get("thresholds", [0.0, 1.0]), values=payload.get("values", [0.5, 0.5]))
    return None
