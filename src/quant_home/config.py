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
