"""Tests for rolling-window feature state isolation.

``FeatureVolumeWindow`` accumulates across calls. These tests pin down the
contract that makes it safe to use: each ``make_phi()`` owns its own window, and
a sequence of ticks fed through one vectorizer produces the documented rolling
sum.
"""

from __future__ import annotations

from typing import List, Tuple

import pytest

from pysrc.main import make_phi

Trade = Tuple[float, float, bool]
Tick = List[Trade]

#: Index of the rolling-volume feature within the vector from ``make_phi``.
VOL_INDEX = 3

#: The C++ window spans this many ticks.
WINDOW = 5


def _tick_with_notional(notional: float) -> Tick:
    # price is irrelevant to the volume feature; notional is the middle element.
    return [(100.0, notional, True)]


def test_rolling_sum_matches_hand_computed_window() -> None:
    notionals = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
    # Sum of the trailing WINDOW entries at each step.
    expected = [10.0, 30.0, 60.0, 100.0, 150.0, 200.0]

    phi = make_phi()
    got = [phi(_tick_with_notional(v))[VOL_INDEX] for v in notionals]

    assert got == pytest.approx(expected, rel=1e-5)


def test_separate_vectorizers_do_not_share_state() -> None:
    notionals = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]

    first = [make_phi()(_tick_with_notional(v))[VOL_INDEX] for v in notionals]
    # A single vectorizer accumulates; one-shot vectorizers must not.
    assert first == pytest.approx(notionals, rel=1e-5)

    phi_a = make_phi()
    phi_b = make_phi()
    seq_a = [phi_a(_tick_with_notional(v))[VOL_INDEX] for v in notionals]
    seq_b = [phi_b(_tick_with_notional(v))[VOL_INDEX] for v in notionals]

    assert seq_a == pytest.approx(seq_b, rel=1e-5)


def test_window_forgets_ticks_beyond_its_span() -> None:
    phi = make_phi()
    for _ in range(WINDOW):
        phi(_tick_with_notional(100.0))

    # Push WINDOW zero-volume ticks; the window should have flushed entirely.
    for _ in range(WINDOW):
        latest = phi(_tick_with_notional(0.0))[VOL_INDEX]

    assert latest == pytest.approx(0.0, abs=1e-5)


def test_stateless_features_are_unaffected_by_call_order() -> None:
    phi = make_phi()
    tick = [(100.0, 5.0, True), (100.0, 5.0, False), (100.0, 5.0, True)]

    first = phi(tick)
    second = phi(tick)

    # count, ratio_buys, ratio_sells are pure; only the volume window moves.
    assert first[:VOL_INDEX] == pytest.approx(second[:VOL_INDEX], rel=1e-6)
    assert second[VOL_INDEX] > first[VOL_INDEX]
