from __future__ import annotations

import os
from typing import Any, Dict, List

import pytest
import requests

# Skip by default; run only if you explicitly opt in
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION") != "1",
    reason="Set RUN_INTEGRATION=1 to run integration tests.",
)

API_ROOT = os.getenv("GEMINI_API_ROOT", "https://api.gemini.com/v1")
SYMBOL = os.getenv("GEMINI_SYMBOL", "btcusd")


def test_trades_endpoint_schema() -> None:
    url = f"{API_ROOT}/trades/{SYMBOL}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()

    data: List[Dict[str, Any]] = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0

    first = data[0]
    assert isinstance(first, dict)

    required_keys = {
        "timestamp",
        "timestampms",
        "tid",
        "price",
        "amount",
        "exchange",
        "type",
    }
    # Confirm required fields are present
    assert required_keys.issubset(first.keys())

    # Light type/value sanity checks (Gemini returns numeric fields as strings)
    # Convertibles:
    float(first["price"])
    float(first["amount"])
    int(first["timestamp"])
    int(first["timestampms"])
    int(first["tid"])
    assert first["type"] in {"buy", "sell"}
