from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="QUANT_HOME_",
        env_file=".env",
        extra="ignore",
    )

    environment: Literal["test", "development", "production"] = "development"
    simulation_only: bool = True
    database_url: str = "postgresql+psycopg://quant:quant@db:5432/quant"
    initial_admin_username: str | None = None
    initial_admin_password: str | None = None
    https_enabled: bool = False
    session_cookie_name: str = "quant_home_session"
    max_background_jobs: int = 3
