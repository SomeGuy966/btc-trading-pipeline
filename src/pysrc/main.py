# src/pysrc/main.py
"""Driver for the trading pipeline: live polling or offline replay.

Live mode polls the exchange and predicts the next one-tick return as it goes.
Replay mode reads a previously recorded tick file, which makes runs fast,
offline and reproducible.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Tuple

import numpy as np
from sklearn.linear_model import Lasso  # type: ignore

from pysrc import cppcore
from pysrc.model import OnlineLassoModel, Phi, Tick

#: Seconds between polls in live mode.
TICK_INTERVAL_SECONDS: float = 10.0

#: Number of (features, target) pairs the model trains on. The tick window holds
#: one more than this: at tick N the targets only run through N-1, so the extra
#: tick is the one being predicted.
TRAIN_WINDOW_TICKS: int = 10

_OUT_DIR = Path(__file__).resolve().parent
PREDICTIONS_PATH = _OUT_DIR / "predictions.txt"
TARGETS_PATH = _OUT_DIR / "targets.txt"

TradePair = Tuple[float, float]
#: One poll's worth of data: buy trades, sell trades, and the midprice proxy.
RawTick = Tuple[List[TradePair], List[TradePair], Optional[float]]


# These three features are pure functions of the tick they are handed, so a
# single shared instance of each is safe and avoids rebuilding them per call.
_COUNT = cppcore.FeatureCountTrades()
_RATIO_BUYS = cppcore.FeatureRatioBuys()
_RATIO_SELLS = cppcore.FeatureRatioSells()

_MODEL = OnlineLassoModel()


def make_phi() -> Phi:
    """Build a feature vectorizer owning its own rolling-window state.

    Uses the batched ``FeatureSet``, which computes all four features in one
    crossing of the Python/C++ boundary. Marshalling a tick's trade list costs
    considerably more than the arithmetic done on it, so calling the four
    features separately spends most of its time rebuilding the same vector --
    see ``pysrc/benchmark.py``.

    ``FeatureSet`` owns the stateful rolling window, so every pass over a tick
    sequence needs its own instance: sharing one would re-feed ticks it had
    already consumed and corrupt the window.
    """
    features = cppcore.FeatureSet()

    def phi(tick: Tick) -> List[float]:
        return list(features.compute(tick))

    return phi


def _feat_count(trades: Tick) -> float:
    return _COUNT.compute_feature(trades)


def _feat_ratio_buys(trades: Tick) -> float:
    return _RATIO_BUYS.compute_feature(trades)


def _feat_ratio_sells(trades: Tick) -> float:
    return _RATIO_SELLS.compute_feature(trades)


def _phi(tick: Tick) -> List[float]:
    """Feature vector for a single isolated tick.

    Builds a fresh feature set per call, so this is safe to call repeatedly.
    A *sequence* of ticks must instead share one ``make_phi()`` vectorizer for
    the rolling-window feature to be meaningful.
    """
    return make_phi()(tick)


def fit_and_predict(
    window_ticks: List[Tick], window_targets: List[float], current_mid: float
) -> tuple[float, Lasso, np.ndarray]:
    """Refit on the window and predict the next return."""
    next_mid, pred_ret = _MODEL.predict_next(
        make_phi, window_ticks, window_targets, current_mid
    )
    return next_mid, _MODEL.model, np.array([pred_ret])


def _append_float(path: Path | str, value: float) -> None:
    with Path(path).open("a") as fh:
        fh.write(f"{value}\n")


def _truncate_outputs() -> None:
    """Clear the output files so a run's analysis covers only that run."""
    for path in (PREDICTIONS_PATH, TARGETS_PATH):
        path.write_text("")


def _to_tick(buys: Iterable[TradePair], sells: Iterable[TradePair]) -> Tick:
    """Flatten buy/sell trades into (price, notional, is_buy) tuples."""
    out: Tick = []
    for price, amount in buys:
        out.append((price, round(price * amount, 2), True))
    for price, amount in sells:
        out.append((price, round(price * amount, 2), False))
    return out


# --------------------------------------------------------------------------- #
# Tick sources
# --------------------------------------------------------------------------- #


def live_ticks(sandbox: bool, interval: float) -> Iterator[RawTick]:
    """Poll the exchange forever via the C++ client."""
    client = cppcore.DataClient()
    while True:
        yield client.get_data("btcusd", sandbox)
        time.sleep(interval)


def replay_ticks(path: Path) -> Iterator[RawTick]:
    """Replay ticks from a JSONL file written by ``record``."""
    with path.open() as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            buys = [(float(p), float(v)) for p, v in rec["buys"]]
            sells = [(float(p), float(v)) for p, v in rec["sells"]]
            mid = rec["mid"]
            yield buys, sells, (None if mid is None else float(mid))


def record(source: Iterator[RawTick], path: Path) -> Iterator[RawTick]:
    """Pass ticks through unchanged while appending each to a JSONL file."""
    with path.open("w") as fh:
        for buys, sells, mid in source:
            fh.write(
                json.dumps(
                    {
                        "buys": [list(b) for b in buys],
                        "sells": [list(s) for s in sells],
                        "mid": mid,
                    }
                )
                + "\n"
            )
            fh.flush()
            yield buys, sells, mid


# --------------------------------------------------------------------------- #
# Main loop
# --------------------------------------------------------------------------- #


def run(
    source: Iterable[RawTick],
    max_ticks: Optional[int] = None,
    verbose: bool = True,
) -> int:
    """Consume ticks, predict, and log predictions against realized returns.

    Returns the number of ticks processed.
    """
    _truncate_outputs()

    ticks: List[Tick] = []
    targets: List[float] = []
    prev_mid: Optional[float] = None
    predicted_ret: Optional[float] = None
    processed = 0

    for buys, sells, mid in source:
        if mid is None:
            continue
        processed += 1

        # Score the previous tick's prediction against what actually happened.
        if predicted_ret is not None and prev_mid is not None:
            realized_ret = (mid - prev_mid) / prev_mid
            _append_float(TARGETS_PATH, realized_ret)
            _append_float(PREDICTIONS_PATH, predicted_ret)
            if verbose:
                predicted_mid = round(prev_mid * (1.0 + predicted_ret), 2)
                print(f"tick {processed:>4}  predicted mid {predicted_mid:>12,.2f}")

        if verbose:
            print(f"tick {processed:>4}  actual mid    {mid:>12,.2f}")

        if prev_mid is not None:
            targets.append((mid - prev_mid) / prev_mid)
        ticks.append(_to_tick(buys, sells))
        prev_mid = mid

        # Trim to the training window: TRAIN_WINDOW_TICKS targets, one more tick.
        if len(ticks) > TRAIN_WINDOW_TICKS + 1:
            ticks.pop(0)
        if len(targets) > TRAIN_WINDOW_TICKS:
            targets.pop(0)

        if len(targets) >= TRAIN_WINDOW_TICKS:
            _, _, preds = fit_and_predict(ticks, targets, mid)
            predicted_ret = float(preds[0])

        if max_ticks is not None and processed >= max_ticks:
            break

    return processed


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    src = p.add_mutually_exclusive_group()
    src.add_argument("--replay", type=Path, help="replay ticks from a JSONL file")
    p.add_argument("--record", type=Path, help="write live ticks to a JSONL file")
    p.add_argument(
        "--max-ticks", type=int, default=None, help="stop after this many ticks"
    )
    p.add_argument(
        "--interval",
        type=float,
        default=TICK_INTERVAL_SECONDS,
        help="seconds between live polls",
    )
    p.add_argument(
        "--sandbox", action="store_true", help="use the exchange sandbox endpoint"
    )
    p.add_argument("--quiet", action="store_true", help="suppress per-tick output")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = _parse_args(argv)

    if args.replay is not None:
        if args.record is not None:
            raise SystemExit("--record cannot be combined with --replay")
        source: Iterator[RawTick] = replay_ticks(args.replay)
    else:
        source = live_ticks(sandbox=args.sandbox, interval=args.interval)
        if args.record is not None:
            source = record(source, args.record)

    processed = run(source, max_ticks=args.max_ticks, verbose=not args.quiet)
    print(f"\nprocessed {processed} ticks")
    print(f"predictions -> {PREDICTIONS_PATH}")
    print(f"targets     -> {TARGETS_PATH}")


if __name__ == "__main__":
    main()
