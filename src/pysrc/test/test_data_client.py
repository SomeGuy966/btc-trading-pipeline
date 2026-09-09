from __future__ import annotations

from typing import Any, TypedDict, cast
import importlib
import pytest
from unittest.mock import MagicMock
from _pytest.monkeypatch import MonkeyPatch


_data_client_mod = importlib.import_module("pysrc.data_client")
DataClient = cast(type[Any], getattr(_data_client_mod, "DataClient"))


class TradeMsg(TypedDict):
    type: str
    price: str
    amount: str


# Fixtures


@pytest.fixture
def client() -> Any:
    """Return a default-initialized DataClient for btcusd."""
    return DataClient()


@pytest.fixture
def sample_payload() -> list[TradeMsg]:
    """Example payload as returned by the Gemini API."""
    return [
        {"type": "buy", "price": "100.0", "amount": "0.5"},
        {"type": "sell", "price": "101.0", "amount": "0.4"},
        {"type": "buy", "price": "99.5", "amount": "1.2"},
        {"type": "sell", "price": "102.0", "amount": "0.3"},
    ]


# tests for _base_url


def test_base_url_returns_correct_endpoints(client: Any) -> None:
    assert client._base_url(sandbox=True) == "https://api.sandbox.gemini.com/v1"
    assert client._base_url(sandbox=False) == "https://api.gemini.com/v1"


# tests for _query_api


def test_query_api_builds_correct_url_and_returns_json(
    monkeypatch: MonkeyPatch, client: Any
) -> None:
    """Ensure _query_api hits correct URL and returns parsed JSON list."""
    fake_response = MagicMock()
    fake_json = [{"price": "100.0", "amount": "1.0", "type": "buy"}]
    fake_response.json.return_value = fake_json
    fake_response.raise_for_status.return_value = None

    session_get = MagicMock(return_value=fake_response)
    client._session.get = session_get

    out = client._query_api(sandbox=False)
    expected_url = "https://api.gemini.com/v1/trades/btcusd"
    session_get.assert_called_once_with(expected_url, timeout=10)
    assert out == fake_json


# tests for _parse_message


def test_parse_message_splits_buys_sells_and_computes_mid(
    sample_payload: list[TradeMsg],
) -> None:
    buys, sells, mid = DataClient._parse_message(sample_payload)

    # Check that we split correctly
    buy_prices = [p for p, _ in buys]
    sell_prices = [p for p, _ in sells]

    assert set(buy_prices) == {100.0, 99.5}
    assert set(sell_prices) == {101.0, 102.0}

    # Highest bid = 100.0, lowest ask = 101.0 -> mid = 100.5
    assert mid == 100.5


def test_parse_message_handles_only_buys() -> None:
    payload = [{"type": "buy", "price": "10", "amount": "1"}]
    buys, sells, mid = DataClient._parse_message(payload)
    assert buys == [(10.0, 1.0)]
    assert sells == []
    assert mid is None


def test_parse_message_handles_only_sells() -> None:
    payload = [{"type": "sell", "price": "20", "amount": "0.5"}]
    buys, sells, mid = DataClient._parse_message(payload)
    assert sells == [(20.0, 0.5)]
    assert buys == []
    assert mid is None


def test_parse_message_empty_list_returns_defaults() -> None:
    buys, sells, mid = DataClient._parse_message([])
    assert buys == []
    assert sells == []
    assert mid is None


# tests for get_data


def test_get_data_invokes_query_and_parse(
    monkeypatch: MonkeyPatch, client: Any, sample_payload: list[TradeMsg]
) -> None:
    """Ensure get_data calls _query_api and _parse_message and updates fields."""
    fake_buys = [(100.0, 1.0)]
    fake_sells = [(101.0, 2.0)]
    fake_mid = 100.5

    mock_query = MagicMock(return_value=sample_payload)
    mock_parse = MagicMock(return_value=(fake_buys, fake_sells, fake_mid))

    client._query_api = mock_query
    client._parse_message = mock_parse

    buys, sells, mid = client.get_data(sandbox=True)

    mock_query.assert_called_once_with(True)
    mock_parse.assert_called_once_with(sample_payload)

    assert buys == fake_buys
    assert sells == fake_sells
    assert mid == fake_mid

    # Check that internal fields are updated
    assert client.buys == fake_buys
    assert client.sells == fake_sells
    assert client.midprice == fake_mid


def test_get_data_integration_mock(monkeypatch: MonkeyPatch, client: Any) -> None:
    """Integration-style unit test ensuring session and parsing flow works end-to-end without real HTTP."""
    fake_json = [
        {"type": "buy", "price": "10.0", "amount": "1.0"},
        {"type": "sell", "price": "11.0", "amount": "2.0"},
    ]
    fake_response = MagicMock()
    fake_response.json.return_value = fake_json
    fake_response.raise_for_status.return_value = None

    monkeypatch.setattr(client._session, "get", MagicMock(return_value=fake_response))

    buys, sells, mid = client.get_data(sandbox=True)
    assert buys == [(10.0, 1.0)]
    assert sells == [(11.0, 2.0)]
    assert mid == 10.5
