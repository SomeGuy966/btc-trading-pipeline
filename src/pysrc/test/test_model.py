"""Contract tests for the online Lasso inference path."""

from __future__ import annotations

from typing import List, Tuple

import numpy as np
from sklearn.linear_model import Lasso  # type: ignore

from pysrc.main import fit_and_predict

Trade = Tuple[float, float, bool]
Tick = List[Trade]


def _tick(buys: list[tuple[float, float]], sells: list[tuple[float, float]]) -> Tick:
    out: Tick = []
    for price, amount in buys:
        out.append((float(price), round(float(price) * float(amount), 2), True))
    for price, amount in sells:
        out.append((float(price), round(float(price) * float(amount), 2), False))
    return out


def _window(n_ticks: int = 11) -> tuple[List[Tick], List[float], float]:
    """A window of n ticks with n-1 targets, matching how the model trains."""
    ticks: List[Tick] = []
    targets: List[float] = []
    prev_mid: float | None = None

    for i in range(n_ticks):
        ticks.append(_tick(buys=[(100.0 + i, float(i + 1))], sells=[(101.0 + i, 1.0)]))
        mid = 100.0 + i * 0.5 + (0.25 if i % 2 else 0.0)
        if prev_mid is not None:
            targets.append((mid - prev_mid) / prev_mid)
        prev_mid = mid

    return ticks, targets, prev_mid if prev_mid is not None else 100.0


def test_returns_expected_shapes_and_types() -> None:
    ticks, targets, mid = _window()
    next_mid, model, preds = fit_and_predict(ticks, targets, mid)

    assert isinstance(next_mid, float)
    assert isinstance(model, Lasso)
    assert hasattr(model, "coef_") and isinstance(model.coef_, np.ndarray)
    assert isinstance(preds, np.ndarray) and preds.shape == (1,)


def test_is_deterministic_across_repeated_calls() -> None:
    """Regression test for feature-state leakage.

    ``FeatureVolumeWindow`` is stateful. If one instance were shared across
    design-matrix builds, a second identical call would see a window already
    advanced by the first and return a different prediction. Identical output on
    repeat is what proves each build gets its own feature state.
    """
    ticks, targets, mid = _window()

    first = fit_and_predict(ticks, targets, mid)
    second = fit_and_predict(ticks, targets, mid)

    assert first[0] == second[0]
    assert float(first[2][0]) == float(second[2][0])


def test_short_window_falls_back_to_current_mid() -> None:
    ticks = [_tick([(100.0, 1.0)], [(101.0, 1.0)])]
    next_mid, model, preds = fit_and_predict(ticks, [], 100.5)

    assert next_mid == 100.5
    assert isinstance(model, Lasso)
    assert preds.shape == (1,)


def test_zero_variance_targets_fall_back_to_current_mid() -> None:
    """Lasso cannot fit a constant target series, so the model declines to guess."""
    ticks, _, mid = _window()
    flat_targets = [0.0] * (len(ticks) - 1)

    next_mid, _, preds = fit_and_predict(ticks, flat_targets, mid)

    assert next_mid == round(mid, 2)
    assert float(preds[0]) == 0.0
