# src/pysrc/data_client.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List, Mapping, Tuple, cast

import requests

JSONRows = List[Mapping[str, Any]]


# Used by later steps; not consumed here directly.
TIME_BETWEEN_TICKS = 90  # seconds


@dataclass(init=False, frozen=True, slots=True)
class Row:
    side: str
    price: float
    amount: float

    def __init__(self, m: Mapping[str, Any]) -> None:
        side = str(m.get("type", "")).lower()
        price = float(m.get("price", "nan"))
        amount = float(m.get("amount", "nan"))
        object.__setattr__(self, "side", side)
        object.__setattr__(self, "price", price)
        object.__setattr__(self, "amount", amount)


class DataClient:
    """Minimal client for fetching and parsing recent trades for a symbol"""

    def __init__(
        self, symbol: str = "btcusd", session: requests.Session | None = None
    ) -> None:
        self.symbol = symbol
        self._session = session or requests.Session()
        self.buys: List[Tuple[float, float]] = []
        self.sells: List[Tuple[float, float]] = []
        # No mid until both best bid/ask are present.
        self.midprice: float | None = None

    def _base_url(self, sandbox: bool) -> str:
        return (
            "https://api.sandbox.gemini.com/v1"
            if sandbox
            else "https://api.gemini.com/v1"
        )

    @staticmethod
    def _rows_from_response(resp: requests.Response) -> JSONRows:
        """Return the response body as a list of mappings (typed for mypy)."""
        resp.raise_for_status()
        return cast(JSONRows, resp.json())

    def _query_api(self, sandbox: bool) -> JSONRows:
        url = f"{self._base_url(sandbox)}/trades/{self.symbol}"
        resp = self._session.get(url, timeout=10)
        return self._rows_from_response(resp)

    @staticmethod
    def _parse_message(
        rows: Iterable[Mapping[str, Any]],
    ) -> tuple[List[Tuple[float, float]], List[Tuple[float, float]], float | None]:
        """Split rows into buys/sells and compute midprice (avg of best bid/ask).
        Returns (buys, sells, mid). If either side is missing, mid is None.
        """
        buys: List[Tuple[float, float]] = []
        sells: List[Tuple[float, float]] = []
        highest_bid: float | None = None
        lowest_ask: float | None = None

        for r in (Row(m) for m in rows):
            if r.side == "buy":
                buys.append((r.price, r.amount))
                highest_bid = (
                    r.price if highest_bid is None else max(highest_bid, r.price)
                )
            elif r.side == "sell":
                sells.append((r.price, r.amount))
                lowest_ask = r.price if lowest_ask is None else min(lowest_ask, r.price)
            # Unknown sides are ignored.

        mid: float | None = None
        if highest_bid is not None and lowest_ask is not None:
            mid = (highest_bid + lowest_ask) / 2.0

        return buys, sells, mid

    def get_data(
        self, sandbox: bool
    ) -> tuple[List[Tuple[float, float]], List[Tuple[float, float]], float | None]:
        payload = self._query_api(sandbox)
        self.buys, self.sells, self.midprice = self._parse_message(payload)
        return self.buys, self.sells, self.midprice
