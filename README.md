# BTC-USD Trading Research Pipeline

[![Pytest](https://github.com/SomeGuy966/btc-trading-pipeline/actions/workflows/pytest.yml/badge.svg)](https://github.com/SomeGuy966/btc-trading-pipeline/actions/workflows/pytest.yml)
[![Ruff + Mypy](https://github.com/SomeGuy966/btc-trading-pipeline/actions/workflows/ruffmypy.yml/badge.svg)](https://github.com/SomeGuy966/btc-trading-pipeline/actions/workflows/ruffmypy.yml)
[![C++ Tests](https://github.com/SomeGuy966/btc-trading-pipeline/actions/workflows/cpp-tests.yml/badge.svg)](https://github.com/SomeGuy966/btc-trading-pipeline/actions/workflows/cpp-tests.yml)
[![Clang Format & Tidy](https://github.com/SomeGuy966/btc-trading-pipeline/actions/workflows/clang-format-tidy.yml/badge.svg)](https://github.com/SomeGuy966/btc-trading-pipeline/actions/workflows/clang-format-tidy.yml)

A hybrid **C++/Python** pipeline that ingests live trade data from the Gemini exchange, computes
order-flow features in C++, runs online Lasso regression to predict short-horizon midprice returns,
and scores those predictions against realized returns.

This is a **research pipeline**: it produces and evaluates predictions. It does not place orders.

---

## Architecture

```mermaid
flowchart LR
    A[Gemini REST<br/>/v1/trades] --> B{Ingest}
    B -->|Python<br/>requests| C[Normalized tick<br/>buys / sells / mid]
    B -->|C++<br/>cpr + nlohmann| C
    C --> D[Feature computation<br/>C++ header-only]
    D -->|pybind11| E[Online Lasso<br/>rolling 10-tick window]
    E --> F[predictions.txt<br/>targets.txt]
    F --> G[Correlation analysis<br/>Pearson / MSE / MAE]
```

The C++ layer is compiled into a pybind11 extension module that the Python orchestration layer
imports directly — there is no serialization boundary or IPC between them.

---

## How it works

### 1 — Ingest

Two interchangeable implementations behind the same interface:

| Implementation | Stack |
| --- | --- |
| Python | `requests` against Gemini's `/v1/trades` REST endpoint |
| C++ | `cpr` + `nlohmann/json`, exposed to Python via pybind11 |

Each poll returns recent trades split into buy and sell sides. Midprice is approximated as the
mean of the highest buy price and the lowest sell price observed in the window.

### 2 — Features (C++)

Header-only classes implementing a shared `BaseFeature` interface. A tick is a vector of
`(price, notional, is_buy)` tuples:

| Feature | Description |
| --- | --- |
| `FeatureCountTrades` | Number of trades in the tick |
| `FeatureRatioBuys` | Share of trades on the buy side |
| `FeatureRatioSells` | Share of trades on the sell side |
| `FeatureVolumeWindow` | Summed notional over a rolling 5-tick window |

### 3 — Inference

Online Lasso over a rolling window of 10 ticks, refit on **every** tick.

Two details that are easy to get wrong and are handled explicitly:

- **Train/predict lag.** At time `t`, realized targets only exist through `t-1`. The model
  therefore trains on features from `t-10 … t-1` and predicts on the features at `t`.
- **Standardization scope.** Feature means and standard deviations are computed on the training
  window only, then applied to the prediction row — never fit on data that includes the row
  being predicted.

### 4 — Analysis

Predicted and realized returns are logged per tick. `evaluate_predictions.py` reports Pearson
correlation, MSE, and MAE over the aligned series.

---

## Quickstart

**Prerequisites:** Python 3.12 (with development headers), CMake, Ninja, GNU Make,
[Poetry](https://python-poetry.org/), [Conan](https://conan.io/), and a C++20 compiler.

```bash
make install     # conan install + poetry install
make build       # cmake configure + build the pybind module
make test        # C++ GoogleTest suite + pytest
make record      # capture a live session to ticks.jsonl
make replay      # re-run the pipeline offline from ticks.jsonl
make analyze     # correlation report over logged predictions
make benchmark   # C++ vs Python feature computation
```

`make run` does a bounded live run (20 ticks) if you want to watch it against
the real endpoint. Every entry point takes flags directly too:

```bash
python -m pysrc.main --replay ticks.jsonl --max-ticks 100 --quiet
python -m pysrc.benchmark --ticks 20000
```

---

## Reproducible runs

A live run is bounded by how fast the exchange produces data: at a 10-second
poll interval, the model needs ~2 minutes before it makes a first prediction.
That is a poor way to evaluate anything, so ticks can be recorded once and
replayed instantly:

```bash
make record    # ~10 minutes of live polling -> ticks.jsonl
make replay    # the same session, start to finish, in under a second
make analyze
```

Replay reads a JSONL file — one tick per line — and drives the identical code
path as live mode, so results are deterministic and require no network access.
This is also what the benchmark runs against.

## Benchmark

`pysrc/benchmark.py` compares three implementations of the same four features
and checks they produce identical values *before* reporting any timing, so the
comparison is between things that actually agree. The C++ features use 32-bit
floats against Python's 64-bit doubles, so agreement is asserted to a relative
tolerance rather than bit-for-bit.

```bash
make benchmark                             # synthetic ticks, no recording needed
python -m pysrc.benchmark --replay ticks.jsonl
```

20,000 ticks x 50 trades (1M trades), Apple M-series, best of 5 passes:

| variant | per tick | vs Python |
| --- | --- | --- |
| Python reference | 2.72 us | 1.00x |
| C++, one call per feature | 4.14 us | **0.66x — slower** |
| C++, batched via `FeatureSet` | **1.17 us** | **2.32x** |

The middle row is the interesting one. Calling the four C++ features separately
is *slower than pure Python*, because each call marshals the tick's trade list
across the pybind11 boundary again, and that marshalling costs far more than the
arithmetic it enables. Four crossings per tick, four conversions of the same
data.

Two changes fixed it:

- `compute_feature` takes its trades by `const&` instead of by value, removing a
  full copy per call.
- `FeatureSet` computes all four features in a single crossing, so a tick is
  converted once rather than four times.

That took the C++ path from **0.66x to 2.32x** against Python — a **3.5x**
improvement over the per-call version, and the reason `make_phi` uses
`FeatureSet` rather than the individual feature classes.

The lesson generalizes: at this granularity the boundary is the bottleneck, not
the compute. Moving more work per crossing beats optimizing what happens inside
one.

---

## Testing

**85 tests** — 56 `pytest`, 29 GoogleTest, all green in CI.

- Unit tests mock the HTTP layer with `MagicMock`, so the suite runs offline and deterministically
- The live-endpoint integration test validating Gemini's response schema is env-gated, keeping CI
  hermetic rather than dependent on a third-party service being reachable
- C++ tests cover feature edge cases: empty ticks, single-sided flow, and rolling-window rollover

```bash
make test                          # unit suites (C++ and Python)
RUN_INTEGRATION=1 poetry run pytest src/pysrc/test/slower_tests   # live-endpoint test
```

## Continuous integration

Four GitHub Actions workflows gate every pull request:

| Workflow | Checks |
| --- | --- |
| `pytest.yml` | Python unit tests |
| `ruffmypy.yml` | `ruff` lint + format, `mypy` strict type checking |
| `cpp-tests.yml` | GoogleTest C++ unit tests |
| `clang-format-tidy.yml` | `clang-format` + `clang-tidy` |

The Python package ships `py.typed` and passes `mypy` in strict mode.

---

## Layout

```
src/
├── cppsrc/                     # header-only C++ core
│   ├── base_feature.hpp        # abstract feature interface
│   ├── feature_*.hpp           # feature implementations
│   ├── feature_set.hpp         # all four features in one boundary crossing
│   ├── data_client.hpp         # C++ REST ingest (cpr + nlohmann/json)
│   ├── main.cpp                # pybind11 module definition
│   └── test/                   # GoogleTest suites
└── pysrc/                      # Python orchestration
    ├── data_client.py          # Python REST ingest
    ├── model.py                # online Lasso wrapper
    ├── main.py                 # tick loop: live, record, or replay
    ├── benchmark.py            # C++ vs Python feature timing
    ├── cppcore.pyi             # type stubs for the compiled extension
    ├── evaluate_predictions.py # correlation / MSE / MAE report
    └── test/                   # pytest suites
```

**Build:** CMake + Conan + Ninja for C++, Poetry for Python, orchestrated by a single Makefile.

---

## Design notes

**Why header-only C++.** Every feature lives entirely in a header, with `.cpp` files reserved for
tests and the pybind module definition. This trades compile time for a simpler build graph and
easier inlining across translation units — a reasonable trade at this scale.

**Why port ingest to C++.** The Python and C++ clients sit behind the same pybind interface, so
the orchestration layer is unchanged by the swap. This makes the two paths directly comparable and
keeps the option of moving more of the hot path across the boundary.

**Stateful features and matrix rebuilds.** `FeatureVolumeWindow` keeps a rolling
5-tick buffer, and the model rebuilds its design matrix on every tick. Sharing
one feature instance across rebuilds would re-feed ticks it had already
consumed, so the window would no longer mean "the last five ticks" at all. The
inference path therefore takes a *factory* rather than a feature function, and
builds a fresh feature set per matrix, feeding each tick exactly once in order.
`test_feature_state.py` pins this down, and the determinism test in
`test_model.py` is the regression guard: identical input must give identical
output, which only holds if no state survives between calls.

**Why online learning.** Market relationships are non-stationary. Refitting on a short rolling
window each tick adapts to regime changes, at the cost of higher variance in the fitted
coefficients — which is part of why Lasso's L1 penalty is a reasonable choice here.

## Limitations and next steps

Stated plainly, because they matter for interpreting any results:

- **REST polling, not WebSocket.** A 10-second poll interval means the feature set reflects
  coarse snapshots rather than true tick-level order flow.
- **Trade-derived midprice.** Without order book data, the midprice proxy is noisier than a true
  bid/ask mid.
- **Four features, linear model.** This is a baseline, not a competitive signal.
- **No execution modeling.** Predictions are scored on correlation with realized returns; there is
  no fill, fee, or slippage model, so these numbers are not a proxy for P&L.
