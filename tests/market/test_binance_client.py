import httpx
import pytest

from quant_home.market.binance_client import BinancePublicClient


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
