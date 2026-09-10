# src/pysrc/model.py
from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Callable, List

import numpy as np
from sklearn.exceptions import ConvergenceWarning  # type: ignore
from sklearn.linear_model import Lasso  # type: ignore

TradeTuple = tuple[float, float, bool]
Tick = list[TradeTuple]

#: Maps one tick to its feature vector. Instances may carry rolling state, so a
#: factory is used rather than a bare callable -- see ``predict_next``.
Phi = Callable[[Tick], List[float]]
PhiFactory = Callable[[], Phi]


@dataclass
class OnlineLassoModel:
    """Lasso refit on every tick over a rolling window of recent ticks."""

    alpha: float = 1.0
    max_iter: int = 10000
    tol: float = 1e-6

    def __post_init__(self) -> None:
        # Wrapped rather than subclassed so the estimator can be swapped later.
        self._model = Lasso(alpha=self.alpha, max_iter=self.max_iter, tol=self.tol)

    @property
    def model(self) -> Lasso:
        """The underlying estimator. Exposed for inspection, not mutation."""
        return self._model

    def predict_next(
        self,
        phi_factory: PhiFactory,
        window_ticks: list[Tick],
        window_targets: list[float],
        current_mid: float,
    ) -> tuple[float, float]:
        """Fit on the window's history and predict the next one-tick return.

        Returns ``(next_midprice, predicted_return)``. Falls back to the current
        midprice and a zero return when the window is too short or the targets
        carry no variance for Lasso to fit against.

        Feature state
        -------------
        Features may be stateful -- ``FeatureVolumeWindow`` keeps a rolling
        5-tick buffer -- and this method rebuilds the design matrix on every
        call. Reusing one feature instance across calls would therefore re-feed
        ticks it had already consumed, corrupting the rolling window. A fresh
        feature set is built per call via ``phi_factory`` and each tick in the
        window is fed exactly once, in order, so row ``i`` observes precisely
        ticks ``0..i``.
        """
        if len(window_ticks) < 2 or len(window_targets) < 1:
            return round(current_mid, 2), 0.0

        phi = phi_factory()
        rows = [phi(tick) for tick in window_ticks]

        X = np.array(rows[:-1], dtype=float)
        X_test = np.array(rows[-1], dtype=float).reshape(1, -1)
        y = np.array(window_targets, dtype=float)

        if y.size < 2 or float(y.std()) < 1e-12:
            return round(current_mid, 2), 0.0

        # Standardize on the training window only, then apply that same
        # transform to the prediction row. A zero-variance column is scaled by
        # 1 rather than dividing by zero.
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
