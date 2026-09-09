from __future__ import annotations

from typing import List, Tuple, TypeAlias
import pytest
from pysrc import cppcore


Trade: TypeAlias = Tuple[float, float, bool]


def make_tick(trades: List[Trade]) -> List[Trade]:
    """
    Helper to ensure all tuples are (float, float, bool).
    trades: list[tuple[float, float, bool]]
    """
    out = []
    for p, v, is_buy in trades:
        out.append((float(p), float(v), bool(is_buy)))
    return out


def test_sanity_feature_count_trades() -> None:
    f = cppcore.FeatureCountTrades()
    assert f.compute_feature([]) == pytest.approx(0.0)


def test_feature_count_trades_basic() -> None:
    f = cppcore.FeatureCountTrades()
    assert f.compute_feature(make_tick([])) == pytest.approx(0.0)
    assert f.compute_feature(make_tick([(1, 1, True)])) == pytest.approx(1.0)
    assert f.compute_feature(make_tick([(2, 1, False), (2, 2, True)])) == pytest.approx(
        2.0
    )


def test_feature_ratio_buys_basic() -> None:
    f = cppcore.FeatureRatioBuys()
    # empty outputs 0.0 by convention
    assert f.compute_feature(make_tick([])) == pytest.approx(0.0)
    # 1/2 buys
    assert f.compute_feature(make_tick([(1, 1, True), (1, 1, False)])) == pytest.approx(
        0.5
    )
    # all buys
    assert f.compute_feature(make_tick([(1, 1, True), (2, 1, True)])) == pytest.approx(
        1.0
    )


def test_feature_ratio_sells_basic() -> None:
    f = cppcore.FeatureRatioSells()
    # empty outputs 0.0 by convention
    assert f.compute_feature(make_tick([])) == pytest.approx(0.0)
    # 1/2 sells
    assert f.compute_feature(make_tick([(1, 1, True), (1, 1, False)])) == pytest.approx(
        0.5
    )
    # all sells
    assert f.compute_feature(
        make_tick([(1, 1, False), (2, 1, False)])
    ) == pytest.approx(1.0)


def test_feature_volume_window_sliding_sum_last_5_ticks() -> None:
    f = cppcore.FeatureVolumeWindow()

    # Each call is one tick; sum volumes over the last 5 ticks.
    t1 = make_tick([(100, 1, True)])  # volume 1
    t2 = make_tick([(101, 2, False)])  # volume 2
    t3 = make_tick([(102, 3, True)])  # volume 3
    t4 = make_tick([(103, 4, False)])  # volume 4
    t5 = make_tick([(104, 5, True)])  # volume 5
    t6 = make_tick([(105, 6, False)])  # volume 6

    assert f.compute_feature(t1) == pytest.approx(1.0)  # [1] -> 1
    assert f.compute_feature(t2) == pytest.approx(3.0)  # [1,2] -> 3
    assert f.compute_feature(t3) == pytest.approx(6.0)  # [1,2,3] -> 6
    assert f.compute_feature(t4) == pytest.approx(10.0)  # [1,2,3,4] -> 10
    assert f.compute_feature(t5) == pytest.approx(15.0)  # [1,2,3,4,5] -> 15
    assert f.compute_feature(t6) == pytest.approx(20.0)  # [2,3,4,5,6] -> 20

    # Another tick to ensure the window keeps rolling
    t7 = make_tick([(106, 10, True)])  # volume 10
    assert f.compute_feature(t7) == pytest.approx(28.0)  # [3,4,5,6,10] -> 28


def test_intern_module_loads() -> None:
    import importlib
    import os
    import sys

    # Add build/ so pytest can find the compiled pybind module
    sys.path.insert(0, os.path.abspath("build"))
    m = importlib.import_module("cppcore")
    assert hasattr(m, "DataClient")
    dc = m.DataClient()
    assert dc is not None
