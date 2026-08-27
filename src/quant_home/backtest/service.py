from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from quant_home.backtest.config import BacktestConfig
from quant_home.backtest.engine import BacktestEngine
from quant_home.backtest.repository import BacktestRepository
from quant_home.backtest.types import StrategyKind
from quant_home.configurations.repository import ConfigurationRepository
from quant_home.jobs.runner import JobExecutionContext, JobRunner
from quant_home.jobs.types import JobStatus
from quant_home.market.candles import Candle
from quant_home.market.repository import CandleDownloader, CandleRepository


class DuplicateBacktest(Exception):
    """Raised when an identical configuration was already submitted."""


class InvalidBacktestDataset(Exception):
    """Raised when market data cannot safely be used for a backtest."""


@dataclass(frozen=True)
class BacktestJobSpec:
    session_factory: Callable[[], Session]
    downloader: CandleDownloader
    configuration_id: UUID
    configuration_version: int
    configuration_snapshot: dict[str, Any]
    configuration_hash: str
    kind: str = "backtest"

    def snapshot(self) -> dict[str, Any]:
        return {
            "configuration_id": str(self.configuration_id),
            "configuration_version": self.configuration_version,
            "configuration_hash": self.configuration_hash,
            "configuration_snapshot": self.configuration_snapshot,
        }

    async def run(self, context: JobExecutionContext) -> None:
        config = BacktestConfig.model_validate(self.configuration_snapshot)
        datasets: dict[StrategyKind, dict[str, tuple[Candle, ...]]] = {}
        fingerprints: dict[str, dict[str, dict[str, object]]] = {}
        total = sum(len(universe.symbols) for universe in config.universes.values())
        completed = 0

        context.stage(JobStatus.DOWNLOADING, progress=0.05)
        with self.session_factory() as db:
            candle_repository = CandleRepository(db, self.downloader)
            for kind in StrategyKind:
                universe = config.universes[kind.value]
                by_symbol: dict[str, tuple[Candle, ...]] = {}
                by_fingerprint: dict[str, dict[str, object]] = {}
                for weighted_symbol in universe.symbols:
                    await context.checkpoint()
                    dataset = candle_repository.ensure_range(
                        weighted_symbol.symbol,
                        universe.interval,
                        config.start_time,
                        config.end_time,
                    )
                    if not dataset.is_valid:
                        issue_codes = ", ".join(issue.code for issue in dataset.issues)
                        raise InvalidBacktestDataset(
                            f"Invalid candle dataset for {weighted_symbol.symbol} "
                            f"{universe.interval.value}: {issue_codes or 'incomplete range'}"
                        )
                    candles = tuple(
                        Candle(
                            open_time=self._utc(item.open_time),
                            open=item.open,
                            high=item.high,
                            low=item.low,
                            close=item.close,
                            volume=item.volume,
                            close_time=self._utc(item.close_time),
                        )
                        for item in sorted(dataset.candles, key=lambda item: item.open_time)
                    )
                    by_symbol[weighted_symbol.symbol] = candles
                    by_fingerprint[weighted_symbol.symbol] = {
                        "dataset_id": str(dataset.id),
                        "fingerprint": dataset.fingerprint,
                        "interval": dataset.interval,
                        "start": self._utc(dataset.start_time).isoformat(),
                        "end": self._utc(dataset.end_time).isoformat(),
                    }
                    completed += 1
                    context.set_progress(0.05 + (completed / total) * 0.45)
                datasets[kind] = by_symbol
                fingerprints[kind.value] = by_fingerprint

        await context.checkpoint()
        context.stage(JobStatus.VALIDATING, progress=0.55)
        if any(len(series) < 2 for group in datasets.values() for series in group.values()):
            raise InvalidBacktestDataset("Invalid candle dataset: at least two candles required")

        await context.checkpoint()
        context.stage(JobStatus.RUNNING, progress=0.65)
        result = BacktestEngine().run(config, datasets)

        await context.checkpoint()
        context.stage(JobStatus.AGGREGATING, progress=0.95)
        BacktestRepository(self.session_factory).save_completed(
            result,
            job_id=context.job_id,
            configuration_snapshot=self.configuration_snapshot,
            dataset_fingerprints=fingerprints,
        )

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class BacktestService:
    def __init__(
        self,
        db: Session,
        session_factory: Callable[[], Session],
        downloader: CandleDownloader,
        job_runner: JobRunner,
    ) -> None:
        self.db = db
        self.session_factory = session_factory
        self.downloader = downloader
        self.job_runner = job_runner

    async def create_run(
        self,
        configuration_id: UUID,
        *,
        version: int | None = None,
        confirm_duplicate: bool = False,
    ) -> UUID:
        stored = ConfigurationRepository(self.db).get(configuration_id, version)
        config = BacktestConfig.model_validate(stored.version.payload)
        snapshot = config.model_dump(mode="json")
        config_hash = self._configuration_hash(snapshot)
        if not confirm_duplicate and any(
            job.kind == "backtest"
            and job.payload.get("configuration_hash") == config_hash
            for job in self.job_runner.repository.list()
        ):
            raise DuplicateBacktest
        return await self.job_runner.submit(
            BacktestJobSpec(
                session_factory=self.session_factory,
                downloader=self.downloader,
                configuration_id=configuration_id,
                configuration_version=stored.version.version,
                configuration_snapshot=snapshot,
                configuration_hash=config_hash,
            )
        )

    @staticmethod
    def _configuration_hash(snapshot: dict[str, Any]) -> str:
        encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

