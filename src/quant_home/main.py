from fastapi import FastAPI

from quant_home.api import health
from quant_home.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Quant Home")
    app.state.settings = settings or Settings()
    app.include_router(health.router, prefix="/api")
    return app
