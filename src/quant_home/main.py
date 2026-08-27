from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select

from quant_home.api import auth, datasets, health, symbols
from quant_home.auth.models import Administrator
from quant_home.auth.passwords import hash_password
from quant_home.auth.service import LoginThrottle
from quant_home.config import Settings
from quant_home.db import Base, create_database_engine, create_session_factory
from quant_home.market.binance_client import BinancePublicClient
from quant_home.market.catalog import SymbolCatalog


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings()
    engine = create_database_engine(resolved_settings.database_url)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if resolved_settings.environment == "test":
            Base.metadata.create_all(engine)
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
        yield
        engine.dispose()

    app = FastAPI(title="Quant Home", lifespan=lifespan)
    app.state.settings = resolved_settings
    app.state.session_factory = session_factory
    app.state.login_throttle = LoginThrottle()
    binance_client = BinancePublicClient()
    app.state.symbol_catalog = SymbolCatalog(binance_client)
    app.state.candle_downloader = binance_client
    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(symbols.router, prefix="/api")
    app.include_router(datasets.router, prefix="/api")
    return app
