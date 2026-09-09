from __future__ import annotations

from typing import List, Tuple
import numpy as np

from pysrc.main import fit_and_predict, buffer as buffer_fn

Trade = Tuple[float, float, bool]
Tick = List[Trade]


def _tick(buys: list[tuple[float, float]], sells: list[tuple[float, float]]) -> Tick:
    out: Tick = []
    for px, amt in buys:
        out.append((float(px), round(float(px) * float(amt), 2), True))
    for px, amt in sells:
        out.append((float(px), round(float(px) * float(amt), 2), False))
    return out


def _window_data(n_ticks: int = 10) -> tuple[List[Tick], List[float], float]:
    """
    Build a window with N ticks and N-1 targets (returns), which matches how the model trains
    """
    ticks: List[Tick] = []
    targets: List[float] = []
    prev_mid: float | None = None

    for i in range(n_ticks):
        # simple, deterministic volumes; price=1 so notional == amount
        ticks.append(_tick(buys=[(1.0, float(i + 1))], sells=[]))

        mid = 100.0 + i  # synthetic mid series
        if prev_mid is not None:
            targets.append((mid - prev_mid) / prev_mid)
        prev_mid = mid

    current_mid = prev_mid if prev_mid is not None else 100.0
    return ticks, targets, current_mid


def test_fit_and_predict_shapes_and_types() -> None:
    ticks, targets, mid = _window_data()
    next_mid, model, preds = fit_and_predict(ticks, targets, mid)
    assert isinstance(next_mid, float)

    assert hasattr(model, "coef_")
    assert isinstance(preds, np.ndarray) and preds.shape == (1,)


def test_buffer_alias_returns_same_contract() -> None:
    ticks, targets, mid = _window_data()
    next_mid, model, preds = buffer_fn(ticks, targets, mid)
    assert isinstance(next_mid, float)
    assert hasattr(model, "coef_")
    assert isinstance(preds, np.ndarray) and preds.shape == (1,)
