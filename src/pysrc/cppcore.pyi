"""Type stubs for the compiled pybind11 extension.

The runtime module is built from ``src/cppsrc/main.cpp`` into
``src/pysrc/cppcore*.so``. These stubs let mypy check callers without requiring
a compiled build, and document the C++ surface exposed to Python.
"""

from typing import List, Optional, Tuple

#: (price, notional, is_buy)
Trade = Tuple[float, float, bool]
#: (price, amount)
TradePair = Tuple[float, float]

class BaseFeature:
    """Abstract base. Bound so derived classes can reference it; has no methods."""

class FeatureCountTrades(BaseFeature):
    def __init__(self) -> None: ...
    def compute_feature(self, data: List[Trade]) -> float: ...

class FeatureRatioBuys(BaseFeature):
    def __init__(self) -> None: ...
    def compute_feature(self, data: List[Trade]) -> float: ...

class FeatureRatioSells(BaseFeature):
    def __init__(self) -> None: ...
    def compute_feature(self, data: List[Trade]) -> float: ...

class FeatureVolumeWindow(BaseFeature):
    """Rolling 5-tick volume sum. Stateful: each call consumes one tick."""

    def __init__(self) -> None: ...
    def compute_feature(self, data: List[Trade]) -> float: ...

class FeatureSet:
    """All four features in one boundary crossing. Stateful: owns the window."""

    def __init__(self) -> None: ...
    def compute(self, data: List[Trade]) -> List[float]: ...

class DataClient:
    def __init__(self) -> None: ...
    def get_data(
        self, symbol: str = ..., sandbox: bool = ...
    ) -> Tuple[List[TradePair], List[TradePair], Optional[float]]: ...
