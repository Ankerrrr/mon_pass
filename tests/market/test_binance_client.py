import httpx
import pytest
from datetime import UTC, datetime, timedelta

from quant_home.market.binance_client import BinancePublicClient
from quant_home.market.candles import CandleInterval


def test_transient_server_error_is_retried_with_bounded_backoff():
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, request=request)
        return httpx.Response(200, json={"symbols": []}, request=request)

    client = BinancePublicClient(
        transport=httpx.MockTransport(handler),
        sleep=delays.append,
    )

    assert client.exchange_info() == {"symbols": []}
    assert attempts == 2
    assert delays == [0.25]


def test_invalid_request_is_not_retried():
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(400, request=request)

    client = BinancePublicClient(
        transport=httpx.MockTransport(handler),
        sleep=lambda _: pytest.fail("permanent failures must not sleep"),
    )

    with pytest.raises(httpx.HTTPStatusError):
        client.exchange_info()

    assert attempts == 1


def test_candle_download_paginates_after_one_thousand_rows():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(minutes=1001)
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        start_ms = int(request.url.params["startTime"])
        end_ms = int(request.url.params["endTime"])
        rows = []
        current_ms = start_ms
        while current_ms <= end_ms and len(rows) < 1000:
            rows.append(
                [
                    current_ms,
                    "100",
                    "102",
                    "99",
                    "101",
                    "10",
                    current_ms + 59_999,
                ]
            )
            current_ms += 60_000
        return httpx.Response(200, json=rows, request=request)

    client = BinancePublicClient(transport=httpx.MockTransport(handler))

    candles = client.fetch_candles(
        "BTCUSDT", CandleInterval.ONE_MINUTE, start, end
    )

    assert len(candles) == 1001
    assert requests == 2


def test_malformed_retry_after_falls_back_and_excessive_delay_is_capped():
    headers = iter(["not-a-number", "999"])
    delays = []

    def handler(request: httpx.Request) -> httpx.Response:
        try:
            retry_after = next(headers)
        except StopIteration:
            return httpx.Response(200, json={"symbols": []}, request=request)
        return httpx.Response(
            429,
            headers={"Retry-After": retry_after},
            request=request,
        )

    client = BinancePublicClient(
        max_attempts=3,
        max_retry_delay=10,
        transport=httpx.MockTransport(handler),
        sleep=delays.append,
    )

    assert client.exchange_info() == {"symbols": []}
    assert delays == [0.25, 10]


def test_candle_download_preserves_raw_order_and_duplicates_for_validation():
    start = datetime(2026, 1, 1, tzinfo=UTC)

    def row(minutes: int):
        opened_ms = int((start + timedelta(minutes=minutes)).timestamp() * 1000)
        return [opened_ms, "100", "102", "99", "101", "10", opened_ms + 59_999]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[row(1), row(0), row(0)],
            request=request,
        )

    client = BinancePublicClient(transport=httpx.MockTransport(handler))

    candles = client.fetch_candles(
        "BTCUSDT",
        CandleInterval.ONE_MINUTE,
        start,
        start + timedelta(minutes=2),
    )

    assert [candle.open_time for candle in candles] == [
        start + timedelta(minutes=1),
        start,
        start,
    ]
