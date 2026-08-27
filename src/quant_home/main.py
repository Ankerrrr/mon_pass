from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from sqlalchemy import select

from quant_home.api import auth, backtests, configurations, datasets, health, jobs, symbols
from quant_home.auth.models import Administrator
from quant_home.auth.passwords import hash_password
from quant_home.auth.service import LoginThrottle
from quant_home.config import Settings
from quant_home.db import Base, create_database_engine, create_session_factory
from quant_home.market.binance_client import BinancePublicClient
from quant_home.market.catalog import SymbolCatalog
from quant_home.jobs.repository import JobRepository
from quant_home.jobs.runner import JobRunner


logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings()
    engine = create_database_engine(resolved_settings.database_url)
    session_factory = create_session_factory(engine)
    job_repository = JobRepository(session_factory)
    job_runner = JobRunner(
        job_repository,
        max_concurrency=resolved_settings.max_background_jobs,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if resolved_settings.environment == "test":
            Base.metadata.create_all(engine)
        job_repository.mark_interrupted_jobs()
        if (
            resolved_settings.initial_admin_username
            and resolved_settings.initial_admin_password
        ):
            with session_factory() as db:
                existing = db.scalar(select(Administrator).limit(1))
                if existing is None:
                    db.add(
                        Administrator(
                            username=resolved_settings.initial_admin_username,
                            password_hash=hash_password(
                                resolved_settings.initial_admin_password
                            ),
                        )
                    )
                    db.commit()
        should_refresh_catalog = (
            resolved_settings.refresh_symbol_catalog_on_startup is True
            or (
                resolved_settings.refresh_symbol_catalog_on_startup is None
                and resolved_settings.environment != "test"
            )
        )
        if should_refresh_catalog:
            try:
                app.state.symbol_catalog.refresh()
                app.state.symbol_catalog_error = None
            except Exception as exc:
                app.state.symbol_catalog_error = str(exc)
                logger.exception("Binance symbol catalog refresh failed")
        try:
            yield
        finally:
            app.state.market_client.close()
            engine.dispose()

    app = FastAPI(title="Quant Home", lifespan=lifespan)

    @app.middleware("http")
    async def defensive_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    app.state.settings = resolved_settings
    app.state.session_factory = session_factory
    app.state.login_throttle = LoginThrottle()
    binance_client = BinancePublicClient()
    app.state.market_client = binance_client
    app.state.symbol_catalog = SymbolCatalog(binance_client)
    app.state.symbol_catalog_error = None
    app.state.candle_downloader = binance_client
    app.state.job_repository = job_repository
    app.state.job_runner = job_runner
    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(symbols.router, prefix="/api")
    app.include_router(datasets.router, prefix="/api")
    app.include_router(configurations.router, prefix="/api")
    app.include_router(backtests.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    return app
