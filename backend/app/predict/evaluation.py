"""How a delay model WOULD be evaluated once real historical running data exists.

Nothing here is run on fabricated data to claim accuracy. The functions are tested with tiny hand-made
examples only to prove the maths is right. Until a real dataset is evaluated, EVALUATION_STATUS stays
NOT_EVALUATED and the app never shows probabilities.
"""
from __future__ import annotations

import math
from collections import defaultdict

EVALUATION_STATUS = "NOT_EVALUATED_NO_HISTORICAL_DATA"


def mae(pred: list[float], actual: list[float]) -> float:
    if not pred or len(pred) != len(actual):
        raise ValueError("need two equal, non-empty lists")
    return sum(abs(p - a) for p, a in zip(pred, actual)) / len(pred)


def rmse(pred: list[float], actual: list[float]) -> float:
    if not pred or len(pred) != len(actual):
        raise ValueError("need two equal, non-empty lists")
    return math.sqrt(sum((p - a) ** 2 for p, a in zip(pred, actual)) / len(pred))


def brier(prob: list[float], happened: list[bool]) -> float:
    """Mean squared error of probabilities for a yes/no event (0 = perfect)."""
    if not prob or len(prob) != len(happened) or any(not 0 <= p <= 1 for p in prob):
        raise ValueError("probabilities must be 0..1 and match outcomes")
    return sum((p - float(h)) ** 2 for p, h in zip(prob, happened)) / len(prob)


def interval_coverage(low: list[float], high: list[float], actual: list[float]) -> float:
    """Share of actual values that fell inside [low, high]. An 80% interval should cover ~80%."""
    if not low or not (len(low) == len(high) == len(actual)):
        raise ValueError("lists must match")
    return sum(l <= a <= h for l, h, a in zip(low, high, actual)) / len(actual)


def calibration_table(prob: list[float], happened: list[bool], bins: int = 5) -> list[dict]:
    """Predicted vs observed frequency per probability bin (reliability diagram data)."""
    b: dict[int, list] = defaultdict(list)
    for p, h in zip(prob, happened):
        b[min(int(p * bins), bins - 1)].append((p, h))
    return [{"bin": i, "mean_predicted": sum(p for p, _ in v) / len(v), "observed": sum(h for _, h in v) / len(v),
             "n": len(v)} for i, v in sorted(b.items())]


def by_group(records: list[dict], key: str) -> dict[str, dict]:
    """MAE/RMSE per train, route, season or lead time. records: {key, pred, actual}."""
    g: dict[str, list] = defaultdict(list)
    for r in records:
        g[str(r[key])].append(r)
    return {k: {"n": len(v), "mae": mae([r["pred"] for r in v], [r["actual"] for r in v]),
                "rmse": rmse([r["pred"] for r in v], [r["actual"] for r in v])} for k, v in g.items()}
