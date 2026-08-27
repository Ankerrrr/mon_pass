from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import UTC
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from quant_home.backtest.engine import BacktestResult
from quant_home.backtest.models import BacktestRun
from quant_home.backtest.types import StrategyKind


class BacktestRunNotFound(Exception):
    pass


class BacktestRepository:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def save_completed(
        self,
        result: BacktestResult,
        *,
        configuration_snapshot: dict[str, Any],
        dataset_fingerprints: dict[str, Any],
    ) -> UUID:
        if set(result.ledgers) != set(StrategyKind):
            raise ValueError("completed result must contain all strategy ledgers")

        run = BacktestRun(
            configuration_snapshot=deepcopy(configuration_snapshot),
            dataset_fingerprints=deepcopy(dataset_fingerprints),
            result_snapshot=self._result_snapshot(result),
            engine_version=result.engine_version,
            fingerprint=result.fingerprint,
        )
        with self.session_factory() as db:
            db.add(run)
            try:
                db.commit()
            except Exception:
                db.rollback()
                raise
            return run.id

    def get(self, run_id: UUID) -> BacktestRun:
        with self.session_factory() as db:
            run = db.get(BacktestRun, run_id)
            if run is None:
                raise BacktestRunNotFound
            self._detach(db, run)
            return run

    def list(self) -> list[BacktestRun]:
        with self.session_factory() as db:
            runs = list(
                db.scalars(
                    select(BacktestRun).order_by(BacktestRun.created_at.desc())
                )
            )
            for run in runs:
                self._detach(db, run)
            return runs

    @staticmethod
    def _result_snapshot(result: BacktestResult) -> dict[str, Any]:
        return {
            "cash_reserve": str(result.cash_reserve),
            "ledgers": {
                kind.value: {
                    "initial_cash": str(ledger.initial_cash),
                    "cash": str(ledger.cash),
                    "fills": [fill.model_dump(mode="json") for fill in ledger.fills],
                }
                for kind, ledger in sorted(
                    result.ledgers.items(), key=lambda item: item[0].value
                )
            },
        }

    @staticmethod
    def _detach(db: Session, run: BacktestRun) -> None:
        if run.created_at.tzinfo is None:
            run.created_at = run.created_at.replace(tzinfo=UTC)
        else:
            run.created_at = run.created_at.astimezone(UTC)
        db.expunge(run)
