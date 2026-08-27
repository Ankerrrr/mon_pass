from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
import time
from typing import Any

import httpx

from quant_home.market.candles import Candle, CandleInterval


class BinancePublicClient:
    def __init__(
        self,
        base_url: str = "https://api.binance.com",
        max_attempts: int = 3,
        max_retry_delay: float = 10.0,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.max_attempts = max_attempts
        self.max_retry_delay = max_retry_delay
        self.sleep = sleep
        self.client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
        )

    def exchange_info(self) -> dict[str, Any]:
        payload = self._get_json("/api/v3/exchangeInfo")
        if not isinstance(payload, dict):
            raise ValueError("Binance exchange info must be a JSON object")
        return payload

    def fetch_candles(
        self,
        symbol: str,
        interval: CandleInterval,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        cursor = start
        candles: dict[datetime, Candle] = {}
        while cursor < end:
            payload = self._get_json(
                "/api/v3/klines",
                params={
                    "symbol": symbol,
                    "interval": interval.value,
                    "startTime": int(cursor.timestamp() * 1000),
                    "endTime": int(end.timestamp() * 1000) - 1,
                    "limit": 1000,
                },
            )
            if not isinstance(payload, list):
                raise ValueError("Binance kline response must be a JSON array")
            page = [self._parse_candle(row) for row in payload]
            for candle in page:
                candles[candle.open_time] = candle
            if len(page) < 1000:
                break
            next_cursor = page[-1].open_time + interval.duration
            if next_cursor <= cursor:
                raise ValueError("Binance kline pagination did not advance")
            cursor = next_cursor
        return [candles[timestamp] for timestamp in sorted(candles)]

    @staticmethod
    def _parse_candle(row: list[Any]) -> Candle:
        if len(row) < 7:
            raise ValueError("Binance kline row is malformed")
        return Candle(
            open_time=datetime.fromtimestamp(row[0] / 1000, tz=UTC),
            open=Decimal(row[1]),
            high=Decimal(row[2]),
            low=Decimal(row[3]),
            close=Decimal(row[4]),
            volume=Decimal(row[5]),
            close_time=datetime.fromtimestamp(row[6] / 1000, tz=UTC),
        )

    def _get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        for attempt in range(self.max_attempts):
            try:
                response = self.client.get(path, params=params)
                if response.status_code == 429 or response.status_code >= 500:
                    response.raise_for_status()
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as exc:
                retryable = not isinstance(exc, httpx.HTTPStatusError) or (
                    exc.response.status_code == 429 or exc.response.status_code >= 500
                )
                if not retryable or attempt + 1 >= self.max_attempts:
                    raise
                retry_after = (
                    exc.response.headers.get("Retry-After")
                    if isinstance(exc, httpx.HTTPStatusError)
                    else None
                )
                fallback_delay = 0.25 * (2**attempt)
                try:
                    requested_delay = (
                        float(retry_after) if retry_after else fallback_delay
                    )
                except ValueError:
                    requested_delay = fallback_delay
                delay = min(max(0.0, requested_delay), self.max_retry_delay)
                self.sleep(delay)
        raise RuntimeError("unreachable")
