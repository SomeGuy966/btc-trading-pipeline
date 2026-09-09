# src/pysrc/main.py
from __future__ import annotations

import argparse
import time
from typing import List, Tuple, Protocol, Optional, cast

import numpy as np
from sklearn.linear_model import Lasso  # type: ignore

from pysrc import intern
from pysrc.data_client import DataClient
from pysrc.model import OnlineLassoModel
from pysrc.intern import DataClient as CppDataClient  # type: ignore[import-not-found]


TICK_INTERVAL_SECONDS: int = 10

# Types
TradeTuple = Tuple[float, float, bool]  # (price, notional, is_buy)
Tick = List[TradeTuple]


class _Feature(Protocol):
    def compute_feature(self, data: Tick) -> float: ...


_VOL_WIN: _Feature = cast(_Feature, intern.FeatureVolumeWindow())
_MODEL = OnlineLassoModel()


def _truncate_outputs() -> None:
    # Reset the files each run so the analysis is for this session only
    for p in ("src/pysrc/predictions.txt", "src/pysrc/targets.txt"):
        open(p, "w").close()


def _append_float(path: str, value: float) -> None:
    # Always end with a newline so line counters work
    with open(path, "a") as fh:
        fh.write(f"{value}\n")


def _fetch_last_tick(
    sandbox: bool,
) -> tuple[list[tuple[float, float]], list[tuple[float, float]], Optional[float]]:
    cli = CppDataClient()
    buys, sells, mid = cli.get_data("btcusd", sandbox)
    return buys, sells, mid


def _feat_count(trades: Tick) -> float:
    obj: _Feature = cast(_Feature, intern.FeatureCountTrades())
    return obj.compute_feature(trades)


def _feat_ratio_buys(trades: Tick) -> float:
    obj: _Feature = cast(_Feature, intern.FeatureRatioBuys())
    return obj.compute_feature(trades)


def _feat_ratio_sells(trades: Tick) -> float:
    obj: _Feature = cast(_Feature, intern.FeatureRatioSells())
    return obj.compute_feature(trades)


def _feat_vol5(trades: Tick) -> float:
    return _VOL_WIN.compute_feature(trades)


def _phi(tick: Tick) -> List[float]:
    # feature vector for one tick
    return [
        _feat_count(tick),
        _feat_ratio_buys(tick),
        _feat_ratio_sells(tick),
        _feat_vol5(tick),
    ]


def buffer(
    ticks: list[list[tuple[float, float, bool]]],
    targets: list[float],
    midprice: float,
) -> tuple[float, Lasso, np.ndarray]:
    next_mid, pred_ret = _MODEL.predict_next(_phi, ticks, targets, midprice)
    return next_mid, _MODEL._model, np.array([pred_ret])


def fit_and_predict(
    window_ticks: List[Tick], window_targets: List[float], current_mid: float
) -> tuple[float, Lasso, np.ndarray]:
    # same signature as before so existing tests keep working
    next_mid, pred_ret = _MODEL.predict_next(
        _phi, window_ticks, window_targets, current_mid
    )
    return next_mid, _MODEL._model, np.array([pred_ret])


def _to_tick(buys: list[tuple[float, float]], sells: list[tuple[float, float]]) -> Tick:
    out: Tick = []
    for px, amt in buys:
        out.append((px, round(px * amt, 2), True))
    for px, amt in sells:
        out.append((px, round(px * amt, 2), False))
    return out


def main() -> None:
    _truncate_outputs()

    t = 1
    ticks: List[Tick] = []
    targets: List[float] = []
    prev_mid: Optional[float] = None

    predicted_mid: Optional[float] = None
    predicted_ret: Optional[float] = None  # Log the raw predicted return for analysis

    while True:
        buys, sells, mid = _fetch_last_tick(sandbox=False)
        if mid is None:
            time.sleep(TICK_INTERVAL_SECONDS)
            continue

        print(f"\nTime = {t}")
        if predicted_ret is not None and prev_mid is not None:
            # Print a rounded mid for sanity but write the raw return to file
            print(f"Predicted midprice: {round(prev_mid * (1.0 + predicted_ret), 2)}")
            realized_ret = (mid - prev_mid) / prev_mid
            _append_float("src/pysrc/targets.txt", realized_ret)
            _append_float("src/pysrc/predictions.txt", float(predicted_ret))

        print(f"Actual midprice: {round(mid, 2)}")

        tick = _to_tick(buys, sells)

        if prev_mid is not None:
            targets.append((mid - prev_mid) / prev_mid)

        ticks.append(tick)
        prev_mid = mid
        t += 1

        if t >= 11:
            predicted_mid, _, preds = fit_and_predict(ticks, targets, prev_mid)
            predicted_ret = float(preds[0])
            ticks.pop(0)
            targets.pop(0)

        time.sleep(TICK_INTERVAL_SECONDS)


if __name__ == "__main__":
    _ = argparse.ArgumentParser(description="Online Lasso loop").parse_args([])
    main()
