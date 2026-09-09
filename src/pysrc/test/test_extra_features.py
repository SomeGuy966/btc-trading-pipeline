from __future__ import annotations

import pytest
from typing import List, Tuple
from pysrc import intern

Trade = Tuple[float, float, bool]
Tick = List[Trade]


def make_tick(trades: Tick) -> Tick:
    return [(float(p), float(v), bool(b)) for p, v, b in trades]


# FeatureCountTrades


@pytest.mark.parametrize(
    "trades, expected",
    [
        ([], 0.0),
        ([(1, 10, True)], 1.0),
        ([(1, 10, True), (2, 5, False), (3, 2, True)], 3.0),
        ([*((i, 1, True) for i in range(20))], 20.0),
    ],
)
def test_count_trades_param(trades: Tick, expected: float) -> None:
    f = intern.FeatureCountTrades()
    assert f.compute_feature(make_tick(trades)) == pytest.approx(expected)


# FeatureRatioBuys


@pytest.mark.parametrize(
    "trades, expected",
    [
        ([], 0.0),  # empty implies 0.0
        ([(1, 1, True)], 1.0),  # all buys
        ([(1, 1, True), (2, 1, False)], 0.5),  # half buys
        ([(1, 1, True), (2, 1, True), (3, 1, False)], 2 / 3),  # mixed
    ],
)
def test_ratio_buys_param(trades: Tick, expected: float) -> None:
    f = intern.FeatureRatioBuys()
    assert f.compute_feature(make_tick(trades)) == pytest.approx(expected)


# FeatureRatioSells


@pytest.mark.parametrize(
    "trades, expected",
    [
        ([], 0.0),
        ([(1, 1, False)], 1.0),
        ([(1, 1, True), (2, 1, False)], 0.5),
    ],
)
def test_ratio_sells_param(trades: Tick, expected: float) -> None:
    f = intern.FeatureRatioSells()
    assert f.compute_feature(make_tick(trades)) == pytest.approx(expected)


# FeatureVolumeWindow (sliding sum over last 5 ticks)


def test_volume_window_rollover() -> None:
    f = intern.FeatureVolumeWindow()

    # volumes per tick: 1,2,3,4,5,6; rolling last-5 sums should be: 1,3,6,10,15,20
    ticks: List[Tick] = [
        make_tick([(100, 1, True)]),
        make_tick([(100, 2, True)]),
        make_tick([(100, 3, True)]),
        make_tick([(100, 4, True)]),
        make_tick([(100, 5, True)]),
        make_tick([(100, 6, True)]),
    ]
    expected: List[float] = [1, 3, 6, 10, 15, 20]
    for t, exp in zip(ticks, expected):
        assert f.compute_feature(t) == pytest.approx(exp)
