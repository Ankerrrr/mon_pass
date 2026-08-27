from typing import Any
from uuid import UUID

from pydantic import ValidationError

from quant_home.backtest.config import BacktestConfig
from quant_home.configurations.repository import (
    ConfigurationRepository,
    ConfigurationSnapshot,
)


class ConfigurationService:
    def __init__(self, repository: ConfigurationRepository) -> None:
        self.repository = repository

    def create(
        self, name: str, description: str | None, payload: dict[str, Any]
    ) -> ConfigurationSnapshot:
        return self.repository.create(name, description, self.validate(payload))

    def update(
        self,
        configuration_id: UUID,
        name: str,
        description: str | None,
        payload: dict[str, Any],
    ) -> ConfigurationSnapshot:
        return self.repository.update(
            configuration_id, name, description, self.validate(payload)
        )

    def clone(self, configuration_id: UUID, name: str) -> ConfigurationSnapshot:
        source = self.repository.get(configuration_id)
        return self.repository.create(
            name,
            source.version.description,
            dict(source.version.payload),
        )

    @staticmethod
    def validate(payload: dict[str, Any]) -> dict[str, Any]:
        return BacktestConfig.model_validate(payload).model_dump(mode="json")


__all__ = ["ConfigurationService", "ValidationError"]
