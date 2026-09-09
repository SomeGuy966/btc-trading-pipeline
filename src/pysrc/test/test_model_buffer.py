from __future__ import annotations

from typing import List, Tuple
import numpy as np
from sklearn.linear_model import Lasso  # type: ignore
from pysrc.main import buffer, fit_and_predict

Trade = Tuple[float, float, bool]
Tick = List[Trade]


def tick(buys: list[tuple[float, float]], sells: list[tuple[float, float]]) -> Tick:
    out: Tick = []
    for px, amt in buys:
        out.append((px, round(px * amt, 2), True))
    for px, amt in sells:
        out.append((px, round(px * amt, 2), False))
    return out


def window_fixture() -> tuple[List[Tick], List[float], float]:
    # 6 ticks with simple patterns and small returns
    ticks: List[Tick] = [
        tick([(100, 1)], [(101, 1)]),
        tick([(100, 2)], [(102, 2)]),
        tick([(99, 1)], [(101, 3)]),
        tick([(101, 1)], [(103, 1)]),
        tick([(102, 2)], [(104, 1)]),
        tick([(101, 1)], [(102, 1)]),
    ]
    targets: List[float] = [0.01, -0.005, 0.008, 0.004, -0.002]  # len = len(ticks) - 1
    current_mid: float = 102.0
    return ticks, targets, current_mid


def test_buffer_shapes_and_types() -> None:
    ticks, targets, mid = window_fixture()
    next_mid, model, preds = buffer(ticks, targets, mid)
    assert isinstance(next_mid, float)
    assert isinstance(model, Lasso)
    assert isinstance(preds, np.ndarray)
    assert preds.shape == (1,)


def test_fit_and_predict_shapes_and_types() -> None:
    ticks, targets, mid = window_fixture()
    next_mid, model, preds = fit_and_predict(ticks, targets, mid)
    assert isinstance(next_mid, float)
    assert isinstance(model, Lasso)
    assert preds.ndim == 1 and preds.size == 1


def test_fit_and_predict_is_deterministic() -> None:
    ticks, targets, mid = window_fixture()
    out1 = fit_and_predict(ticks, targets, mid)
    out2 = fit_and_predict(ticks, targets, mid)
    assert out1[0] == out2[0]
    assert float(out1[2][0]) == float(out2[2][0])


def test_buffer_handles_short_window() -> None:
    ticks: List[Tick] = [tick([(100, 1)], [(101, 1)])]
    targets: List[float] = []
    next_mid, model, preds = buffer(ticks, targets, 100.5)
    assert isinstance(next_mid, float)
    assert isinstance(model, Lasso)
    assert preds.shape == (1,)
