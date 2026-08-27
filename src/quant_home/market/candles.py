from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class CandleInterval(StrEnum):
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    ONE_HOUR = "1h"
    FOUR_HOURS = "4h"
    ONE_DAY = "1d"

    @property
    def duration(self) -> timedelta:
        return {
            self.ONE_MINUTE: timedelta(minutes=1),
            self.FIVE_MINUTES: timedelta(minutes=5),
            self.FIFTEEN_MINUTES: timedelta(minutes=15),
            self.ONE_HOUR: timedelta(hours=1),
            self.FOUR_HOURS: timedelta(hours=4),
            self.ONE_DAY: timedelta(days=1),
        }[self]


class Candle(BaseModel):
    model_config = ConfigDict(frozen=True)

    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    close_time: datetime
