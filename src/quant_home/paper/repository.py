from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from quant_home.paper.models import PaperSession, ProcessedPaperCandle
from quant_home.paper.types import ConnectionState, PaperSessionStatus


class PaperSessionNotFound(Exception):
    pass


class PaperRepository:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def get(self, session_id: UUID) -> PaperSession:
        with self.session_factory() as db:
            item = db.get(PaperSession, session_id)
            if item is None:
                raise PaperSessionNotFound
            self._normalize(item)
            db.expunge(item)
            return item

    def list(self) -> list[PaperSession]:
        with self.session_factory() as db:
            items = list(db.scalars(select(PaperSession).order_by(PaperSession.created_at.desc())))
            for item in items:
                self._normalize(item)
                db.expunge(item)
            return items

    def list_active(self) -> list[PaperSession]:
        return [item for item in self.list() if item.status is PaperSessionStatus.ACTIVE]

    def checkpoint(
        self, session_id: UUID, state: dict[str, Any], *, strategy: str,
        symbol: str, interval: str, open_time: datetime,
    ) -> bool:
        """Atomically checkpoint state; return False when the candle was already processed."""
        with self.session_factory() as db:
            identity = (session_id, strategy, symbol, interval, open_time)
            if db.get(ProcessedPaperCandle, identity) is not None:
                return False
            item = db.get(PaperSession, session_id)
            if item is None:
                raise PaperSessionNotFound
            if item.status is not PaperSessionStatus.ACTIVE:
                return False
            item.state_snapshot = state
            item.last_candle_at = open_time
            item.connection_state = ConnectionState.CONNECTED
            db.add(ProcessedPaperCandle(
                session_id=session_id, strategy=strategy, symbol=symbol,
                interval=interval, open_time=open_time,
            ))
            db.commit()
            return True

    def was_processed(self, session_id: UUID, strategy: str, event) -> bool:
        identity = (session_id, strategy, event.symbol, event.interval.value, event.candle.open_time)
        with self.session_factory() as db:
            return db.get(ProcessedPaperCandle, identity) is not None

    def latest_processed(
        self, session_id: UUID, symbol: str, interval: str
    ) -> datetime | None:
        with self.session_factory() as db:
            value = db.scalar(select(func.max(ProcessedPaperCandle.open_time)).where(
                ProcessedPaperCandle.session_id == session_id,
                ProcessedPaperCandle.symbol == symbol,
                ProcessedPaperCandle.interval == interval,
            ))
            if value is not None and value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value

    @staticmethod
    def _normalize(item: PaperSession) -> None:
        for field in ("created_at", "updated_at", "stopped_at", "last_candle_at"):
            value = getattr(item, field)
            if value is not None and value.tzinfo is None:
                setattr(item, field, value.replace(tzinfo=UTC))
