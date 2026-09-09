"""Tests that ``_phi`` is a genuinely single-tick helper.

``_phi`` exists for callers that want features for one isolated tick. It builds
its own feature set per call, so it must NOT accumulate rolling state between
calls -- that is what ``make_phi`` is for. An earlier version of this pipeline
shared one module-level window here, which silently corrupted the rolling
volume feature; these tests pin the corrected contract.
"""

from __future__ import annotations

from typing import List, Tuple

import pytest

from pysrc import cppcore
from pysrc.main import (
    _feat_count,
    _feat_ratio_buys,
    _feat_ratio_sells,
    _phi,
    make_phi,
)

Trade = Tuple[float, float, bool]
Tick = List[Trade]

VOL_INDEX = 3


def _tick(buys: list[tuple[float, float]], sells: list[tuple[float, float]]) -> Tick:
    """Mirror main._to_tick: notional = round(price * amount, 2)."""
    out: Tick = []
    for price, amount in buys:
        out.append((float(price), round(float(price) * float(amount), 2), True))
    for price, amount in sells:
        out.append((float(price), round(float(price) * float(amount), 2), False))
    return out


def test_phi_agrees_with_individual_feature_helpers() -> None:
    tick = _tick(buys=[(1.0, 1.0), (1.0, 0.5)], sells=[(1.0, 2.0)])

    vec = _phi(tick)

    assert isinstance(vec, list) and len(vec) == 4
    assert vec[0] == pytest.approx(_feat_count(tick))
    assert vec[1] == pytest.approx(_feat_ratio_buys(tick))
    assert vec[2] == pytest.approx(_feat_ratio_sells(tick))

    # The volume entry must match a window that has seen only this tick.
    fresh_window = cppcore.FeatureVolumeWindow()
    assert vec[VOL_INDEX] == pytest.approx(fresh_window.compute_feature(tick))


def test_phi_does_not_accumulate_between_calls() -> None:
    t1 = _tick(buys=[(1.0, 1.0)], sells=[])
    t2 = _tick(buys=[], sells=[(1.0, 2.0)])
    t3 = _tick(buys=[(1.0, 3.0)], sells=[])

    # Each call is independent, so each volume equals that tick's own notional.
    assert _phi(t1)[VOL_INDEX] == pytest.approx(1.0)
    assert _phi(t2)[VOL_INDEX] == pytest.approx(2.0)
    assert _phi(t3)[VOL_INDEX] == pytest.approx(3.0)

    # Repeating a tick gives the same answer -- no residue from earlier calls.
    assert _phi(t1)[VOL_INDEX] == pytest.approx(1.0)


def test_make_phi_accumulates_where_phi_does_not() -> None:
    """The two helpers differ precisely in whether state carries over."""
    t1 = _tick(buys=[(1.0, 1.0)], sells=[])
    t2 = _tick(buys=[], sells=[(1.0, 2.0)])
    t3 = _tick(buys=[(1.0, 3.0)], sells=[])

    shared = make_phi()
    rolling = [shared(t)[VOL_INDEX] for t in (t1, t2, t3)]
    isolated = [_phi(t)[VOL_INDEX] for t in (t1, t2, t3)]

    assert rolling == pytest.approx([1.0, 3.0, 6.0])
    assert isolated == pytest.approx([1.0, 2.0, 3.0])
