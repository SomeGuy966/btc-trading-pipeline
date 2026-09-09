# src/pysrc/benchmark.py
"""Benchmark C++ feature computation against an equivalent Python implementation.

Correctness first: both implementations are run over the same ticks and their
outputs compared, so the timing below is a comparison of two things that
actually compute the same values. Only then is throughput reported.

Note the C++ features use 32-bit ``float`` while Python uses 64-bit doubles, so
agreement is checked to a relative tolerance rather than bit-for-bit.
"""

from __future__ import annotations

import argparse
import random
import time
from collections import deque
from pathlib import Path
from typing import Callable, List, Optional, Sequence

from pysrc import cppcore
from pysrc.main import _to_tick, replay_ticks
from pysrc.model import Tick

#: Relative tolerance when comparing float32 C++ output to float64 Python.
REL_TOL = 1e-3

Phi = Callable[[Tick], List[float]]


# --------------------------------------------------------------------------- #
# Pure-Python reference implementations
# --------------------------------------------------------------------------- #


def py_count_trades(tick: Tick) -> float:
    return float(len(tick))


def py_ratio_buys(tick: Tick) -> float:
    if not tick:
        return 0.0
    return sum(1 for _, _, is_buy in tick if is_buy) / len(tick)


def py_ratio_sells(tick: Tick) -> float:
    if not tick:
        return 0.0
    return sum(1 for _, _, is_buy in tick if not is_buy) / len(tick)


class PyVolumeWindow:
    """Rolling sum of per-tick notional over the last ``window`` ticks."""

    def __init__(self, window: int = 5) -> None:
        self._window = window
        self._buf: deque[float] = deque()
        self._sum = 0.0

    def compute_feature(self, tick: Tick) -> float:
        volume = sum(notional for _, notional, _ in tick)
        self._buf.append(volume)
        self._sum += volume
        if len(self._buf) > self._window:
            self._sum -= self._buf.popleft()
        return self._sum


def make_python_phi() -> Phi:
    window = PyVolumeWindow()

    def phi(tick: Tick) -> List[float]:
        return [
            py_count_trades(tick),
            py_ratio_buys(tick),
            py_ratio_sells(tick),
            window.compute_feature(tick),
        ]

    return phi


def make_cpp_percall_phi() -> Phi:
    """Four separate C++ calls: one boundary crossing per feature, per tick."""
    count = cppcore.FeatureCountTrades()
    ratio_buys = cppcore.FeatureRatioBuys()
    ratio_sells = cppcore.FeatureRatioSells()
    window = cppcore.FeatureVolumeWindow()

    def phi(tick: Tick) -> List[float]:
        return [
            count.compute_feature(tick),
            ratio_buys.compute_feature(tick),
            ratio_sells.compute_feature(tick),
            window.compute_feature(tick),
        ]

    return phi


def make_cpp_batched_phi() -> Phi:
    """One C++ call per tick via FeatureSet. This is what the pipeline uses."""
    features = cppcore.FeatureSet()

    def phi(tick: Tick) -> List[float]:
        return list(features.compute(tick))

    return phi


# --------------------------------------------------------------------------- #
# Tick loading
# --------------------------------------------------------------------------- #


def load_replay_ticks(path: Path) -> List[Tick]:
    return [_to_tick(buys, sells) for buys, sells, _ in replay_ticks(path)]


def synthetic_ticks(n_ticks: int, trades_per_tick: int, seed: int = 7) -> List[Tick]:
    """Generate reproducible ticks so the benchmark runs with no recorded data."""
    rng = random.Random(seed)
    ticks: List[Tick] = []
    for _ in range(n_ticks):
        tick: Tick = []
        for _ in range(trades_per_tick):
            price = rng.uniform(90_000.0, 110_000.0)
            amount = rng.uniform(0.001, 0.5)
            tick.append((price, round(price * amount, 2), rng.random() < 0.5))
        ticks.append(tick)
    return ticks


# --------------------------------------------------------------------------- #
# Measurement
# --------------------------------------------------------------------------- #


def run_phi(phi_factory: Callable[[], Phi], ticks: Sequence[Tick]) -> List[List[float]]:
    phi = phi_factory()
    return [phi(tick) for tick in ticks]


def time_phi(
    phi_factory: Callable[[], Phi], ticks: Sequence[Tick], repeats: int
) -> float:
    """Best-of-``repeats`` wall time in seconds for one full pass over ticks."""
    best = float("inf")
    for _ in range(repeats):
        start = time.perf_counter()
        run_phi(phi_factory, ticks)
        best = min(best, time.perf_counter() - start)
    return best


def max_relative_difference(
    a: Sequence[Sequence[float]], b: Sequence[Sequence[float]]
) -> float:
    worst = 0.0
    for row_a, row_b in zip(a, b):
        for x, y in zip(row_a, row_b):
            scale = max(abs(x), abs(y), 1e-12)
            worst = max(worst, abs(x - y) / scale)
    return worst


def main(argv: Optional[List[str]] = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--replay", type=Path, help="benchmark over a recorded tick file")
    p.add_argument(
        "--ticks", type=int, default=5000, help="synthetic tick count (no --replay)"
    )
    p.add_argument(
        "--trades-per-tick", type=int, default=50, help="synthetic trades per tick"
    )
    p.add_argument("--repeats", type=int, default=5, help="timed passes, best wins")
    args = p.parse_args(argv)

    if args.replay is not None:
        ticks = load_replay_ticks(args.replay)
        source = str(args.replay)
    else:
        ticks = synthetic_ticks(args.ticks, args.trades_per_tick)
        source = f"synthetic ({args.trades_per_tick} trades/tick)"

    if not ticks:
        raise SystemExit("no ticks to benchmark")

    variants: List[tuple[str, Callable[[], Phi]]] = [
        ("Python", make_python_phi),
        ("C++ per-call", make_cpp_percall_phi),
        ("C++ batched", make_cpp_batched_phi),
    ]

    outputs = {name: run_phi(factory, ticks) for name, factory in variants}
    baseline = outputs["Python"]

    print("Feature computation")
    print(f"  source          {source}")
    print(f"  ticks           {len(ticks):,}")
    print(f"  trades          {sum(len(t) for t in ticks):,}")
    print(f"  repeats         {args.repeats} (best time reported)")
    print()

    print("  equivalence vs Python reference")
    ok = True
    for name, _ in variants[1:]:
        drift = max_relative_difference(outputs[name], baseline)
        verdict = "agree" if drift <= REL_TOL else "DISAGREE"
        ok = ok and drift <= REL_TOL
        print(f"    {name:<14} {verdict}  (max relative difference {drift:.2e})")
    if not ok:
        print(f"    WARNING: exceeds tolerance {REL_TOL:.0e}")
    print()

    timings = {
        name: time_phi(factory, ticks, args.repeats) for name, factory in variants
    }
    py_s = timings["Python"]

    print(f"  {'variant':<14} {'total':>10} {'per tick':>12} {'vs Python':>11}")
    for name, _ in variants:
        secs = timings[name]
        per_tick_us = secs / len(ticks) * 1e6
        rel = py_s / secs if secs > 0 else float("inf")
        print(
            f"  {name:<14} {secs * 1e3:>7.2f} ms {per_tick_us:>9.2f} us {rel:>10.2f}x"
        )

    print()
    percall = timings["C++ per-call"]
    batched = timings["C++ batched"]
    if batched > 0:
        print(f"  batching won {percall / batched:.2f}x over per-call C++")


if __name__ == "__main__":
    main()
