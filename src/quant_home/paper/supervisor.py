import asyncio
from datetime import UTC, datetime

from quant_home.backtest.config import BacktestConfig
from quant_home.market.binance_client import BinancePublicClient
from quant_home.market.stream import CandleClosed
from quant_home.paper.repository import PaperRepository
from quant_home.paper.runtime import PaperRuntime


class PaperSupervisor:
    """Low-frequency public-data supervisor; it has no authenticated exchange client."""

    def __init__(self, repository: PaperRepository, market: BinancePublicClient, poll_seconds: float = 15.0) -> None:
        self.repository = repository
        self.market = market
        self.poll_seconds = poll_seconds
        self._task: asyncio.Task[None] | None = None
        self.last_cycle_at: datetime | None = None
        self.last_error: str | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def poll_once(self) -> None:
        now = datetime.now(UTC)
        for session in self.repository.list_active():
            config = BacktestConfig.model_validate(session.configuration_snapshot)
            subscriptions = {
                (symbol.symbol, universe.interval)
                for universe in config.universes.values() for symbol in universe.symbols
            }
            runtime = PaperRuntime(session.id, self.repository)
            for symbol, interval in subscriptions:
                latest = self.repository.latest_processed(session.id, symbol, interval.value)
                start = latest + interval.duration if latest else now - interval.duration * 3
                if start >= now:
                    continue
                candles = await asyncio.to_thread(self.market.fetch_candles, symbol, interval, start, now)
                for candle in candles:
                    if candle.close_time <= now:
                        runtime.on_candle(CandleClosed(symbol, interval, candle))
        self.last_cycle_at = now
        self.last_error = None

    async def _run(self) -> None:
        while True:
            try:
                await self.poll_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_error = str(exc)
            await asyncio.sleep(self.poll_seconds)
