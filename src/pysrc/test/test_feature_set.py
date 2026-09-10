"""Tests for the batched FeatureSet binding.

``FeatureSet`` exists purely as an optimization: it computes the same four
features as the individual classes, in one crossing of the Python/C++ boundary
instead of four. Its whole justification is that it produces identical values,
so that equivalence is what these tests hold it to.
"""

from __future__ import annotations

from typing import List, Tuple

import pytest

from pysrc import cppcore

Trade = Tuple[float, float, bool]
Tick = List[Trade]

VOL_INDEX = 3
WINDOW = 5


def _tick(n_buys: int, n_sells: int, notional: float = 10.0) -> Tick:
    out: Tick = []
    out += [(100.0, notional, True)] * n_buys
    out += [(101.0, notional, False)] * n_sells
    return out


def test_compute_returns_four_values() -> None:
    result = cppcore.FeatureSet().compute(_tick(2, 1))

    assert len(result) == 4
    assert all(isinstance(x, float) for x in result)


def test_matches_individual_features_on_a_single_tick() -> None:
    tick = _tick(3, 1)

    batched = cppcore.FeatureSet().compute(tick)
    expected = [
        cppcore.FeatureCountTrades().compute_feature(tick),
        cppcore.FeatureRatioBuys().compute_feature(tick),
        cppcore.FeatureRatioSells().compute_feature(tick),
        cppcore.FeatureVolumeWindow().compute_feature(tick),
    ]

    assert batched == pytest.approx(expected, rel=1e-6)


def test_matches_individual_features_across_a_sequence() -> None:
    """The stateful window must track identically through a whole sequence."""
    ticks = [_tick(i % 3 + 1, i % 2, notional=float(i + 1)) for i in range(12)]

    feature_set = cppcore.FeatureSet()
    batched = [list(feature_set.compute(t)) for t in ticks]

    count = cppcore.FeatureCountTrades()
    ratio_buys = cppcore.FeatureRatioBuys()
    ratio_sells = cppcore.FeatureRatioSells()
    window = cppcore.FeatureVolumeWindow()
    separate = [
        [
            count.compute_feature(t),
            ratio_buys.compute_feature(t),
            ratio_sells.compute_feature(t),
            window.compute_feature(t),
        ]
        for t in ticks
    ]

    flat_batched = [v for row in batched for v in row]
    flat_separate = [v for row in separate for v in row]
    assert flat_batched == pytest.approx(flat_separate, rel=1e-6)


def test_instances_do_not_share_window_state() -> None:
    ticks = [_tick(1, 0, notional=float(i + 1)) for i in range(WINDOW + 2)]

    a = cppcore.FeatureSet()
    b = cppcore.FeatureSet()
    seq_a = [a.compute(t)[VOL_INDEX] for t in ticks]
    seq_b = [b.compute(t)[VOL_INDEX] for t in ticks]

    assert seq_a == pytest.approx(seq_b, rel=1e-6)


def test_handles_empty_tick() -> None:
    result = cppcore.FeatureSet().compute([])

    # No trades: zero count, both ratios zero by definition, zero volume.
    assert result == pytest.approx([0.0, 0.0, 0.0, 0.0])
