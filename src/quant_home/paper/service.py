from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from quant_home.backtest.config import BacktestConfig
from quant_home.configurations.repository import ConfigurationRepository
from quant_home.paper.models import PaperSession
from quant_home.paper.types import ConnectionState, PaperSessionStatus


class PaperTradingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def start(self, configuration_id: UUID, version: int | None = None) -> UUID:
        stored = ConfigurationRepository(self.db).get(configuration_id, version)
        config = BacktestConfig.model_validate(stored.version.payload)
        snapshot = config.model_dump(mode="json")
        ledgers = {}
        for strategy, allocation in (
            ("trend", config.allocations.trend),
            ("mean_reversion", config.allocations.mean_reversion),
            ("grid", config.allocations.grid),
        ):
            cash = config.initial_capital * allocation
            ledgers[strategy] = {"initial_cash": str(cash), "cash": str(cash), "positions": {}, "fills": []}
        item = PaperSession(
            configuration_id=configuration_id,
            configuration_version=stored.version.version,
            configuration_snapshot=snapshot,
            state_snapshot={
                "cash_reserve": str(config.initial_capital * config.allocations.cash_reserve),
                "ledgers": ledgers, "strategy_states": {}, "candles": {},
            },
            status=PaperSessionStatus.ACTIVE,
            connection_state=ConnectionState.STARTING,
        )
        self.db.add(item)
        self.db.commit()
        return item.id

    def stop(self, session_id: UUID) -> bool:
        item = self.db.get(PaperSession, session_id)
        if item is None:
            from quant_home.paper.repository import PaperSessionNotFound
            raise PaperSessionNotFound
        if item.status is not PaperSessionStatus.ACTIVE:
            return False
        item.status = PaperSessionStatus.STOPPED
        item.connection_state = ConnectionState.DISCONNECTED
        item.stopped_at = datetime.now(UTC)
        self.db.commit()
        return True

    def stop_all(self) -> int:
        active = list(self.db.scalars(select(PaperSession).where(PaperSession.status == PaperSessionStatus.ACTIVE)))
        stopped = sum(self.stop(item.id) for item in active)
        return stopped
