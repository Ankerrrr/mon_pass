from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine

from quant_home.backtest.engine import BacktestResult
from quant_home.backtest.ledger import Ledger
from quant_home.backtest.types import Fill, StrategyKind
from quant_home.db import Base, create_session_factory


def completed_result(*, fingerprint: str = "a" * 64) -> BacktestResult:
    ledgers = {
        StrategyKind.TREND: Ledger(Decimal("400")),
        StrategyKind.MEAN_REVERSION: Ledger(Decimal("300")),
        StrategyKind.GRID: Ledger(Decimal("200")),
    }
    ledgers[StrategyKind.TREND].apply(
        Fill.buy(
            "BTCUSDT",
            quantity=Decimal("1"),
            price=Decimal("100"),
            fee=Decimal("0.10"),
            filled_at=datetime(2025, 1, 1, tzinfo=UTC),
            reason="trend entry",
        )
    )
    return BacktestResult(
        ledgers=ledgers,
        cash_reserve=Decimal("100"),
        fingerprint=fingerprint,
        engine_version="1",
    )


def repository():
    from quant_home.backtest.repository import BacktestRepository

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return BacktestRepository(create_session_factory(engine))


def test_save_completed_preserves_detached_immutable_snapshots():
    runs = repository()
    result = completed_result()
    configuration = {"initial_capital": "1000", "symbols": ["BTCUSDT"]}
    datasets = {"trend": {"BTCUSDT": "dataset-fingerprint"}}

    run_id = runs.save_completed(
        result,
        configuration_snapshot=configuration,
        dataset_fingerprints=datasets,
    )
    configuration["symbols"].append("ETHUSDT")
    datasets["trend"]["BTCUSDT"] = "changed"
    result.ledgers[StrategyKind.TREND].apply(
        Fill.sell(
            "BTCUSDT",
            quantity=Decimal("1"),
            price=Decimal("110"),
            fee=Decimal("0.10"),
            filled_at=datetime(2025, 1, 2, tzinfo=UTC),
        )
    )

    stored = runs.get(run_id)

    assert stored.configuration_snapshot == {
        "initial_capital": "1000",
        "symbols": ["BTCUSDT"],
    }
    assert stored.dataset_fingerprints == {
        "trend": {"BTCUSDT": "dataset-fingerprint"}
    }
    assert stored.result_snapshot["cash_reserve"] == "100"
    assert stored.result_snapshot["ledgers"]["trend"]["cash"] == "299.90"
    assert stored.result_snapshot["ledgers"]["trend"]["fills"] == [
        {
            "symbol": "BTCUSDT",
            "side": "buy",
            "quantity": "1",
            "price": "100",
            "fee": "0.10",
            "filled_at": "2025-01-01T00:00:00Z",
            "reason": "trend entry",
            "mode": "backtest",
        }
    ]
    assert stored.fingerprint == "a" * 64
    assert stored.engine_version == "1"
    assert stored.created_at.tzinfo is not None

    stored.result_snapshot["cash_reserve"] = "0"
    assert runs.get(run_id).result_snapshot["cash_reserve"] == "100"


def test_same_fingerprint_can_be_saved_as_distinct_runs():
    runs = repository()
    result = completed_result()

    first_id = runs.save_completed(
        result,
        configuration_snapshot={"confirmed": True},
        dataset_fingerprints={"trend": "one"},
    )
    second_id = runs.save_completed(
        result,
        configuration_snapshot={"confirmed": True},
        dataset_fingerprints={"trend": "one"},
    )

    assert first_id != second_id
    assert [run.id for run in runs.list()] == [second_id, first_id]


def test_completed_run_can_be_resolved_from_its_background_job():
    runs = repository()
    job_id = uuid4()

    run_id = runs.save_completed(
        completed_result(),
        job_id=job_id,
        configuration_snapshot={},
        dataset_fingerprints={},
    )

    assert runs.get_by_job(job_id).id == run_id


def test_invalid_result_is_not_partially_persisted():
    runs = repository()
    invalid = completed_result()
    invalid.ledgers.pop(StrategyKind.GRID)

    with pytest.raises(ValueError, match="all strategy ledgers"):
        runs.save_completed(
            invalid,
            configuration_snapshot={},
            dataset_fingerprints={},
        )

    assert runs.list() == []
