from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from quant_home.configurations.models import (
    StrategyConfiguration,
    StrategyConfigurationVersion,
)


class ConfigurationNotFound(Exception):
    pass


class ConfigurationNameConflict(Exception):
    pass


@dataclass(frozen=True)
class ConfigurationSnapshot:
    configuration: StrategyConfiguration
    version: StrategyConfigurationVersion


class ConfigurationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self) -> list[ConfigurationSnapshot]:
        configurations = self.db.scalars(
            select(StrategyConfiguration).order_by(StrategyConfiguration.created_at.desc())
        )
        return [self.get(item.id) for item in configurations]

    def get(self, configuration_id: UUID, version: int | None = None) -> ConfigurationSnapshot:
        configuration = self.db.get(StrategyConfiguration, configuration_id)
        if configuration is None:
            raise ConfigurationNotFound
        resolved_version = version or configuration.current_version
        snapshot = self.db.scalar(
            select(StrategyConfigurationVersion).where(
                StrategyConfigurationVersion.configuration_id == configuration_id,
                StrategyConfigurationVersion.version == resolved_version,
            )
        )
        if snapshot is None:
            raise ConfigurationNotFound
        return ConfigurationSnapshot(configuration, snapshot)

    def create(
        self,
        name: str,
        description: str | None,
        payload: dict[str, Any],
    ) -> ConfigurationSnapshot:
        configuration = StrategyConfiguration(name=name, current_version=1)
        version = StrategyConfigurationVersion(
            configuration=configuration,
            version=1,
            name=name,
            description=description,
            payload=payload,
        )
        self.db.add(configuration)
        self.db.add(version)
        self._commit()
        return ConfigurationSnapshot(configuration, version)

    def update(
        self,
        configuration_id: UUID,
        name: str,
        description: str | None,
        payload: dict[str, Any],
    ) -> ConfigurationSnapshot:
        current = self.get(configuration_id)
        next_version = current.configuration.current_version + 1
        current.configuration.name = name
        current.configuration.current_version = next_version
        version = StrategyConfigurationVersion(
            configuration_id=configuration_id,
            version=next_version,
            name=name,
            description=description,
            payload=payload,
        )
        self.db.add(version)
        self._commit()
        return ConfigurationSnapshot(current.configuration, version)

    def delete(self, configuration_id: UUID) -> None:
        configuration = self.db.get(StrategyConfiguration, configuration_id)
        if configuration is None:
            raise ConfigurationNotFound
        self.db.delete(configuration)
        self.db.commit()

    def _commit(self) -> None:
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConfigurationNameConflict from exc
