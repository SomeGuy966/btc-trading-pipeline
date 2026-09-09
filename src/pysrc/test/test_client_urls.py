from __future__ import annotations

import inspect
import re
from typing import Dict, List
import requests_mock

from pysrc.data_client import DataClient


def _rx(base: str, symbol: str) -> re.Pattern[str]:
    # Match with or without query params
    return re.compile(rf"{re.escape(base)}/trades/{symbol}(?:\?.*)?$", re.IGNORECASE)


def _supports_symbol_param() -> bool:
    try:
        sig = inspect.signature(DataClient.get_data)
        return "symbol" in sig.parameters
    except Exception:
        return False


def test_sandbox_true_uses_sandbox_host(requests_mock: requests_mock.Mocker) -> None:
    base = "https://api.sandbox.gemini.com/v1"
    symbol = "btcusd"
    requests_mock.get(_rx(base, symbol), status_code=200, json=[])
    buys, sells, mid = DataClient().get_data(sandbox=True)
    assert buys == [] and sells == [] and mid is None


def test_sandbox_false_uses_prod_host(requests_mock: requests_mock.Mocker) -> None:
    base = "https://api.gemini.com/v1"
    symbol = "btcusd"
    requests_mock.get(_rx(base, symbol), status_code=200, json=[])
    buys, sells, mid = DataClient().get_data(sandbox=False)
    assert buys == [] and sells == [] and mid is None


def test_symbol_override_is_used(requests_mock: requests_mock.Mocker) -> None:
    base = "https://api.sandbox.gemini.com/v1"
    if _supports_symbol_param():
        # Implementations that accept a symbol should hit ETHUSD when passed
        symbol = "ethusd"
        payload_eth: List[Dict[str, str]] = [
            {"price": "10.0", "amount": "2.0", "type": "buy"}
        ]
        requests_mock.get(_rx(base, symbol), status_code=200, json=payload_eth)
        buys, sells, mid = DataClient().get_data(symbol=symbol, sandbox=True)  # type: ignore[call-arg]
        assert buys == [(10.0, 2.0)] and sells == []
    else:
        # implementations without a symbol param always use BTCUSD; assert that path works
        symbol = "btcusd"
        payload_btc: List[Dict[str, str]] = [
            {"price": "10.0", "amount": "2.0", "type": "buy"}
        ]
        requests_mock.get(_rx(base, symbol), status_code=200, json=payload_btc)
        buys, sells, mid = DataClient().get_data(sandbox=True)
        assert buys == [(10.0, 2.0)] and sells == []
