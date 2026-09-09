from __future__ import annotations

from typing import List, Tuple
from pathlib import Path

from pysrc.main import (
    _phi,
    _feat_count,
    _feat_ratio_buys,
    _feat_ratio_sells,
    _append_float,
)

Trade = Tuple[float, float, bool]
Tick = List[Trade]


def make_tick(raw: List[Tuple[float, float, bool]]) -> Tick:
    # ensure canonical (float, float, bool) tuples
    return [(float(p), float(v), bool(b)) for p, v, b in raw]


def test_phi_returns_four_floats() -> None:
    tick: Tick = make_tick([(100.0, 1.0, True), (101.0, 2.0, False)])
    vec = _phi(tick)
    assert isinstance(vec, list)
    assert len(vec) == 4
    assert all(isinstance(x, float) for x in vec)


def test_feat_count_matches_len() -> None:
    t0: Tick = make_tick([])
    t1: Tick = make_tick([(100.0, 1.0, True)])
    t3: Tick = make_tick([(100.0, 1.0, True), (101.0, 2.0, False), (102.0, 3.0, True)])
    assert _feat_count(t0) == 0.0
    assert _feat_count(t1) == 1.0
    assert _feat_count(t3) == 3.0


def test_ratio_buys_edge_cases() -> None:
    empty: Tick = make_tick([])
    all_buys: Tick = make_tick([(1.0, 1.0, True), (2.0, 1.0, True)])
    half: Tick = make_tick([(1.0, 1.0, True), (2.0, 1.0, False)])
    assert _feat_ratio_buys(empty) == 0.0
    assert _feat_ratio_buys(all_buys) == 1.0
    assert _feat_ratio_buys(half) == 0.5


def test_ratio_sells_edge_cases() -> None:
    empty: Tick = make_tick([])
    all_sells: Tick = make_tick([(1.0, 1.0, False), (2.0, 1.0, False)])
    half: Tick = make_tick([(1.0, 1.0, True), (2.0, 1.0, False)])
    assert _feat_ratio_sells(empty) == 0.0
    assert _feat_ratio_sells(all_sells) == 1.0
    assert _feat_ratio_sells(half) == 0.5


def test_append_float_appends_and_newlines(tmp_path: Path) -> None:
    p = tmp_path / "vals.txt"
    _append_float(str(p), 1.23)
    _append_float(str(p), -0.0045)
    content = p.read_text()

    # Ensure exactly two lines and each ends with a newline

    lines = content.splitlines()
    assert len(lines) == 2
    assert content.endswith("\n")

    # Values should be parseable as floats
    assert float(lines[0]) == 1.23
    assert float(lines[1]) == -0.0045
