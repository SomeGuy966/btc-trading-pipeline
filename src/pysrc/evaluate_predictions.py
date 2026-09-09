# src/pysrc/evaluate_predictions.py
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Sequence, Tuple
import numpy as np

PRED_PATH = Path("src/pysrc/predictions.txt")
TGT_PATH = Path("src/pysrc/targets.txt")


def _read_numbers(path: Path) -> List[float]:
    vals: List[float] = []
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    with path.open("r") as fh:
        for line in fh:
            s = line.strip()
            if not s:
                continue
            try:
                vals.append(float(s))
            except ValueError:
                if not vals:
                    continue
                raise
    return vals


def _slice_to_float_arrays(
    preds: Sequence[float], tgts: Sequence[float], n: int
) -> tuple[np.ndarray, np.ndarray]:
    """Return first n elements of preds/tgts as float ndarrays"""
    p = np.asarray(preds[:n], dtype=float)
    y = np.asarray(tgts[:n], dtype=float)
    return p, y


def _has_variance(a: np.ndarray) -> bool:
    return float(np.std(a)) != 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze predictions vs. targets")
    parser.add_argument("--pred", default=str(PRED_PATH))
    parser.add_argument("--tgt", default=str(TGT_PATH))
    args = parser.parse_args()

    preds = _read_numbers(Path(args.pred))
    tgts = _read_numbers(Path(args.tgt))

    n = min(len(preds), len(tgts))
    if n == 0:
        print("No overlapping predictions/targets to analyze yet")
        return
    if len(preds) != len(tgts):
        print(
            f"Warning: truncating to common length {n} (preds={len(preds)}, tgts={len(tgts)})"
        )

    p, y = _slice_to_float_arrays(preds, tgts, n)

    if not (_has_variance(p) and _has_variance(y)):
        corr = float("nan")
    else:
        corr = float(np.corrcoef(p, y)[0, 1])
    mse = float(np.mean((p - y) ** 2))
    mae = float(np.mean(np.abs(p - y)))

    print("Analysis")
    print(f"Pairs:  {n}")
    print(f"Pearson: {corr:.4f}")
    print(f"MSE:     {mse:.6f}")
    print(f"MAE:     {mae:.6f}")


if __name__ == "__main__":
    main()
