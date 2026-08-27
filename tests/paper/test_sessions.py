from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine

from quant_home.configurations.repository import ConfigurationRepository
from quant_home.db import Base, create_session_factory
from quant_home.paper.repository import PaperRepository
from quant_home.paper.runtime import PaperRuntime
from quant_home.paper.service import PaperTradingService
from quant_home.paper.types import PaperSessionStatus
from quant_home.market.candles import Candle, CandleInterval
from quant_home.market.stream import CandleClosed, ReconnectPolicy


def config_payload():
    start = datetime(2026, 1, 1, tzinfo=UTC)
    universe = {"symbols": [{"symbol": "BTCUSDT", "weight": "1"}]}
    return {
        "initial_capital": "10000", "start_time": start.isoformat(),
        "end_time": (start + timedelta(days=1)).isoformat(),
        "universes": {"trend": universe, "mean_reversion": universe, "grid": universe},
    }


def test_start_snapshots_configuration_and_creates_independent_ledgers():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = create_session_factory(engine)
    with sessions() as db:
        stored = ConfigurationRepository(db).create("paper", None, config_payload())
        session_id = PaperTradingService(db).start(stored.configuration.id)

    session = PaperRepository(sessions).get(session_id)
    assert session.status is PaperSessionStatus.ACTIVE
    assert session.configuration_snapshot["initial_capital"] == "10000"
    assert session.state_snapshot["ledgers"]["trend"]["cash"] == "4000.00"
    assert session.state_snapshot["ledgers"]["mean_reversion"]["cash"] == "3000.00"
    assert session.state_snapshot["ledgers"]["grid"]["cash"] == "2000.00"
    assert Decimal(session.state_snapshot["cash_reserve"]) == Decimal("1000")


def test_stop_is_idempotent_and_active_sessions_are_restart_discoverable():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = create_session_factory(engine)
    with sessions() as db:
        stored = ConfigurationRepository(db).create("paper", None, config_payload())
        service = PaperTradingService(db)
        session_id = service.start(stored.configuration.id)
        assert [item.id for item in PaperRepository(sessions).list_active()] == [session_id]
        service.stop(session_id)
        first_stopped_at = PaperRepository(sessions).get(session_id).stopped_at
        service.stop(session_id)

    stopped = PaperRepository(sessions).get(session_id)
    assert stopped.status is PaperSessionStatus.STOPPED
    assert stopped.stopped_at == first_stopped_at
    assert PaperRepository(sessions).list_active() == []


def test_runtime_processes_each_closed_candle_once():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    sessions = create_session_factory(engine)
    with sessions() as db:
        stored = ConfigurationRepository(db).create("runtime", None, config_payload())
        session_id = PaperTradingService(db).start(stored.configuration.id)
    at = datetime(2026, 1, 2, tzinfo=UTC)
    event = CandleClosed("BTCUSDT", CandleInterval.FOUR_HOURS, Candle(
        open_time=at, open=Decimal("100"), high=Decimal("102"), low=Decimal("99"),
        close=Decimal("101"), volume=Decimal("10"), close_time=at + timedelta(hours=4),
    ))
    runtime = PaperRuntime(session_id, PaperRepository(sessions))
    assert runtime.on_candle(event) == 1
    assert runtime.on_candle(event) == 0
    assert len(PaperRepository(sessions).get(session_id).state_snapshot["candles"]["trend:BTCUSDT"]) == 1
    assert ReconnectPolicy().next_delay(20) == 30.0
