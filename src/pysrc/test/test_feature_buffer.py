import numpy as np
from pysrc.main import buffer


def test_buffer() -> None:
    ticks = [
        [(97381.02, 973.81, False)],
        [(97381.02, 973.81, False)],
        [(97381.02, 973.81, False)],
        [(97406.77, 10000.00, True)],
        [(97406.77, 12468.07, True)],
        [(97381.02, 973.8102, False)],
        [(97381.02, 973.8102, False)],
        [(97381.02, 973.8102, False)],
        [(97499.59, 10000.00, True)],
        [(97381.02, 973.8102, False)],
    ]
    targets = [
        0.001,
        -0.001,
        0.002,
        -0.002,
        0.0015,
        -0.0015,
        0.0005,
        -0.0005,
        -0.00077,
    ]
    assert len(ticks) - 1 == len(targets)

    next_midprice, model, predictions = buffer(ticks, targets, 97390.0)

    # sanity checks
    assert isinstance(next_midprice, float)
    assert next_midprice != 0.0
    assert hasattr(model, "coef_") and isinstance(model.coef_, np.ndarray)
    assert hasattr(model, "intercept_") and isinstance(model.intercept_, float)
    assert isinstance(predictions, np.ndarray) and predictions.shape == (1,)
