from typing import Literal

from pydantic import model_validator
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
    bind_host: str = "127.0.0.1"
    bind_port: int = 8000
    refresh_symbol_catalog_on_startup: bool | None = None

    @model_validator(mode="after")
    def lan_binding_requires_non_placeholder_admin_password(self):
        if self.bind_host not in {"127.0.0.1", "localhost", "::1"} and (
            not self.initial_admin_password
            or self.initial_admin_password == "change-this-password"
        ):
            raise ValueError(
                "LAN binding requires QUANT_HOME_INITIAL_ADMIN_PASSWORD "
                "to be set to a non-placeholder value"
            )
        return self
