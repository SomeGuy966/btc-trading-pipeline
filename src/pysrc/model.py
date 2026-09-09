# src/pysrc/model.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List
import warnings

import numpy as np
from sklearn.linear_model import Lasso  # type: ignore
from sklearn.exceptions import ConvergenceWarning  # type: ignore


TradeTuple = tuple[float, float, bool]
Tick = list[TradeTuple]


@dataclass
class OnlineLassoModel:
    alpha: float = 1.0
    max_iter: int = 10000
    tol: float = 1e-6

    def __post_init__(self) -> None:
        # Keep the sklearn model inside so swapping implementations later is easier
        self._model = Lasso(alpha=self.alpha, max_iter=self.max_iter, tol=self.tol)

    def predict_next(
        self,
        phi: Callable[[Tick], List[float]],
        window_ticks: list[Tick],
        window_targets: list[float],
        current_mid: float,
    ) -> tuple[float, float]:
        if len(window_ticks) < 2 or len(window_targets) < 1:
            return round(current_mid, 2), 0.0

        X = np.array(
            [phi(window_ticks[i]) for i in range(0, len(window_ticks) - 1)], dtype=float
        )
        y = np.array(window_targets, dtype=float)
        X_test = np.array(phi(window_ticks[-1]), dtype=float).reshape(1, -1)

        if y.size < 2 or float(y.std()) < 1e-12:
            return round(current_mid, 2), 0.0

        # Centers each feature using the training window mean and scale by its std so columns are on a similar scale
        # Apply the same transform to X_test, and if a column std is 0 set it to 1 to avoid divide by zero
        mu = X.mean(axis=0)
        sigma = X.std(axis=0)
        sigma[sigma == 0.0] = 1.0
        Xn = (X - mu) / sigma
        X_test_n = (X_test - mu) / sigma

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=ConvergenceWarning)
            self._model.fit(Xn, y)

        pred_ret = float(self._model.predict(X_test_n)[0])
        next_mid = round(current_mid * (1.0 + pred_ret), 2)
        return next_mid, pred_ret
